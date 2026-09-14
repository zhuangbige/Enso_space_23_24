#!/usr/bin/env python3
"""Extract monthly SODA3 terms for a fixed three-box H20 heat budget.

The boxes are fixed before looking at results:

* west reservoir: 160E-180E;
* central pathway: 180E-220E (140W);
* eastern Pacific: 220E-280E (80W);
* common latitude range: 10S-5N; upper 300 m.

For every month this script streams compact APDRC OPeNDAP slices and saves:
H20 storage, zonal Q20 convergence, north/south Q20 convergence, and both
full and T(surface)>20C-gated surface net heating.  Full four-dimensional
fields are never retained.  Calendar months and year chunks are checkpointed.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import netCDF4
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_chakravorty_transport_baseline as base  # noqa: E402


OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_warm_heat_budget_terms_1980_2022.csv"
)
TEST_OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_warm_heat_budget_terms_1980_1981_test.csv"
)
CHECKPOINT_ROOT = (
    ROOT
    / "data/interim/research_2026/"
    "soda3_three_box_warm_heat_budget"
)

TRACER_URL = base.TRACER_URL
VELOCITY_URL = base.VELOCITY_URL
SOURCE_START_YEAR = 1980
SOURCE_END_YEAR = 2022
SOUTH = -10.0
NORTH = 5.0
DEPTH_MAX_M = 300.0
RHO0_KG_M3 = 1025.0
CP0_J_KG_K = 3990.0

BOXES = {
    "west": (160.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 280.0),
}
ZONAL_GATES = (160.0, 180.0, 220.0, 280.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test",
        action="store_true",
        help="Extract 1980-1981 only and write a separate test CSV.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--chunk-years",
        type=int,
        default=10,
        help="Years per OPeNDAP request (default: 10).",
    )
    return parser.parse_args()


def cell_selection(
    values: np.ndarray,
    lower_boundary: float,
    upper_boundary: float,
) -> np.ndarray:
    """Select tracer cell centers between two velocity-grid boundaries."""
    selected = (values > lower_boundary) & (values < upper_boundary)
    if not selected.any():
        raise ValueError(f"No tracer cells inside {lower_boundary}..{upper_boundary}")
    return selected


def warm_heat_content_zj(
    temperature: np.ndarray,
    *,
    depth: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> np.ndarray:
    """H20 = integral rho*Cp*max(T-20C, 0) dV, returned in ZJ."""
    dz = np.diff(base.depth_bounds(depth, DEPTH_MAX_M)).reshape(
        (1, depth.size, 1, 1)
    )
    area = base.grid_cell_areas(latitude, longitude).reshape(
        (1, 1, latitude.size, longitude.size)
    )
    warm_excess = np.where(
        np.isfinite(temperature),
        np.maximum(temperature - 20.0, 0.0),
        np.nan,
    )
    heat_j = RHO0_KG_M3 * CP0_J_KG_K * np.nansum(
        warm_excess * dz * area,
        axis=(1, 2, 3),
    )
    return heat_j / 1.0e21


def surface_heat_terms(
    heat_flux: np.ndarray,
    surface_temperature: np.ndarray,
    *,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return all-surface PW, warm-layer-effective PW and warm area fraction."""
    if heat_flux.shape != surface_temperature.shape:
        raise ValueError("Surface heat flux and temperature shapes differ")
    area = base.grid_cell_areas(latitude, longitude)[None, :, :]
    valid = np.isfinite(heat_flux) & np.isfinite(surface_temperature)
    warm = valid & (surface_temperature > 20.0)
    all_w = np.nansum(np.where(valid, heat_flux * area, np.nan), axis=(1, 2))
    warm_w = np.nansum(np.where(warm, heat_flux * area, np.nan), axis=(1, 2))
    valid_area = np.nansum(np.where(valid, area, np.nan), axis=(1, 2))
    warm_area = np.nansum(np.where(warm, area, np.nan), axis=(1, 2))
    fraction = np.divide(
        warm_area,
        valid_area,
        out=np.full(warm_area.shape, np.nan, dtype=float),
        where=valid_area > 0.0,
    )
    return all_w / 1.0e15, warm_w / 1.0e15, fraction


def read_month_chunk(
    tracer: netCDF4.Dataset,
    velocity: netCDF4.Dataset,
    *,
    calendar_month: int,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    t_depth_all = np.asarray(tracer.variables["lev"][:], dtype=float)
    t_lat_all = np.asarray(tracer.variables["lat"][:], dtype=float)
    t_lon_all = np.asarray(tracer.variables["lon"][:], dtype=float) % 360.0
    u_depth_all = np.asarray(velocity.variables["lev"][:], dtype=float)
    u_lat_all = np.asarray(velocity.variables["lat"][:], dtype=float)
    u_lon_all = np.asarray(velocity.variables["lon"][:], dtype=float) % 360.0
    if not np.allclose(t_depth_all, u_depth_all):
        raise ValueError("Tracer and velocity depth grids differ")

    zslice = base.contiguous_slice(t_depth_all, 0.0, DEPTH_MAX_M)
    depth = t_depth_all[zslice]
    tslice = base.time_slice(start_year, end_year, calendar_month)
    expected = end_year - start_year + 1

    # One tracer block supplies H20, surface heating and temperatures on all
    # boundary faces.  The half-degree halo straddles 160E/280E and 10S/5N.
    t_yslice = base.contiguous_slice(t_lat_all, SOUTH - 0.5, NORTH + 0.5)
    t_xslice = base.contiguous_slice(t_lon_all, 159.5, 280.5)
    t_lat = t_lat_all[t_yslice]
    t_lon = t_lon_all[t_xslice]
    temperature = base.clean(
        tracer.variables["temp"][tslice, zslice, t_yslice, t_xslice]
    )
    net_heating = base.clean(
        tracer.variables["nh"][tslice, t_yslice, t_xslice]
    )
    if temperature.shape[0] != expected or net_heating.shape[0] != expected:
        raise ValueError("Unexpected number of time records")

    h_lat_mask = cell_selection(t_lat, SOUTH, NORTH)
    h_lat = t_lat[h_lat_mask]
    rows: dict[str, np.ndarray] = {}

    # Storage and surface terms for each non-overlapping tracer-cell box.
    for box, (west, east) in BOXES.items():
        xmask = cell_selection(t_lon, west, east)
        box_lon = t_lon[xmask]
        box_temp = temperature[:, :, h_lat_mask, :][:, :, :, xmask]
        box_heat_flux = net_heating[:, h_lat_mask, :][:, :, xmask]
        rows[f"{box}_h20_zj"] = warm_heat_content_zj(
            box_temp,
            depth=depth,
            latitude=h_lat,
            longitude=box_lon,
        )
        all_pw, warm_pw, warm_fraction = surface_heat_terms(
            box_heat_flux,
            box_temp[:, 0, :, :],
            latitude=h_lat,
            longitude=box_lon,
        )
        rows[f"{box}_surface_all_pw"] = all_pw
        rows[f"{box}_surface_warm_pw"] = warm_pw
        rows[f"{box}_surface_warm_area_fraction"] = warm_fraction

    # Eastward Q20 at fixed longitude gates.  The 5S-5N values are retained
    # only as a cross-check against the pre-existing independent calculation.
    u_yslice = base.contiguous_slice(u_lat_all, SOUTH, NORTH)
    u_lat = u_lat_all[u_yslice]
    tracer_section_lat = t_lat[h_lat_mask]
    if u_lat.size != tracer_section_lat.size + 1:
        raise ValueError("Unexpected latitude staggering on zonal gates")
    eq_mask = (tracer_section_lat >= -5.0) & (tracer_section_lat <= 5.0)
    for gate in ZONAL_GATES:
        left_global, right_global = base.adjacent_indices(t_lon_all, gate)
        left = int(np.flatnonzero(np.isclose(t_lon, t_lon_all[left_global]))[0])
        right = int(np.flatnonzero(np.isclose(t_lon, t_lon_all[right_global]))[0])
        gate_temperature = 0.5 * (
            temperature[:, :, h_lat_mask, left]
            + temperature[:, :, h_lat_mask, right]
        )
        u_xindex = base.exact_index(u_lon_all, gate)
        raw_u = base.clean(
            velocity.variables["u"][
                tslice,
                zslice,
                u_yslice,
                slice(u_xindex, u_xindex + 1),
            ]
        )[:, :, :, 0]
        gate_u = 0.5 * (raw_u[:, :, :-1] + raw_u[:, :, 1:])
        _, q20 = base.section_transports(
            gate_temperature,
            gate_u,
            depth,
            base.zonal_section_width(tracer_section_lat),
        )
        _, q20_eq = base.section_transports(
            gate_temperature[:, :, eq_mask],
            gate_u[:, :, eq_mask],
            depth,
            base.zonal_section_width(tracer_section_lat[eq_mask]),
        )
        gate_label = f"{int(gate)}e"
        rows[f"q20_{gate_label}_10s5n_pw"] = q20
        rows[f"q20_{gate_label}_5s5n_pw"] = q20_eq

    # Northward v is positive natively.  At 10S this is box inflow; at 5N
    # box inflow is southward, so its sign is reversed.
    v_xslice = base.contiguous_slice(u_lon_all, 160.0, 280.0)
    v_lon = u_lon_all[v_xslice]
    tracer_v_lon_mask = cell_selection(t_lon, 160.0, 280.0)
    tracer_v_lon = t_lon[tracer_v_lon_mask]
    if v_lon.size != tracer_v_lon.size + 1:
        raise ValueError("Unexpected longitude staggering on meridional gates")

    boundary_data: dict[str, tuple[np.ndarray, np.ndarray, float]] = {}
    for label, latitude, inflow_sign in (
        ("south", SOUTH, 1.0),
        ("north", NORTH, -1.0),
    ):
        below_global, above_global = base.adjacent_indices(t_lat_all, latitude)
        below = int(np.flatnonzero(np.isclose(t_lat, t_lat_all[below_global]))[0])
        above = int(np.flatnonzero(np.isclose(t_lat, t_lat_all[above_global]))[0])
        boundary_temperature = 0.5 * (
            temperature[:, :, below, :][:, :, tracer_v_lon_mask]
            + temperature[:, :, above, :][:, :, tracer_v_lon_mask]
        )
        v_yindex = base.exact_index(u_lat_all, latitude)
        raw_v = base.clean(
            velocity.variables["v"][
                tslice,
                zslice,
                slice(v_yindex, v_yindex + 1),
                v_xslice,
            ]
        )[:, :, 0, :]
        boundary_v = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
        boundary_data[label] = (boundary_temperature, inflow_sign * boundary_v, latitude)

    for box, (west, east) in BOXES.items():
        xmask = cell_selection(tracer_v_lon, west, east)
        box_lon = tracer_v_lon[xmask]
        meridional_sum = np.zeros(expected, dtype=float)
        for boundary_label, (boundary_temp, boundary_v, latitude) in boundary_data.items():
            _, q20 = base.section_transports(
                boundary_temp[:, :, xmask],
                boundary_v[:, :, xmask],
                depth,
                base.meridional_section_width(box_lon, latitude),
            )
            rows[f"{box}_{boundary_label}_q20_in_pw"] = q20
            meridional_sum += q20
        rows[f"{box}_meridional_convergence_pw"] = meridional_sum

    for box, (west, east) in BOXES.items():
        west_gate = rows[f"q20_{int(west)}e_10s5n_pw"]
        east_gate = rows[f"q20_{int(east)}e_10s5n_pw"]
        rows[f"{box}_zonal_convergence_pw"] = west_gate - east_gate
        rows[f"{box}_resolved_warm_flux_pw"] = (
            rows[f"{box}_zonal_convergence_pw"]
            + rows[f"{box}_meridional_convergence_pw"]
            + rows[f"{box}_surface_warm_pw"]
        )

    years = np.arange(start_year, end_year + 1)
    times = pd.DatetimeIndex(
        [pd.Timestamp(int(year), calendar_month, 15) for year in years]
    )
    return pd.DataFrame(
        {
            "time": times,
            "year": years,
            "month": calendar_month,
            **rows,
        }
    )


def validate(frame: pd.DataFrame, start_year: int, end_year: int) -> None:
    expected_rows = (end_year - start_year + 1) * 12
    if len(frame) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, found {len(frame)}")
    times = pd.DatetimeIndex(frame["time"])
    expected_times = pd.date_range(
        f"{start_year}-01-01", f"{end_year}-12-01", freq="MS"
    ) + pd.Timedelta(days=14)
    if not times.equals(expected_times) or not times.is_unique:
        raise ValueError("Monthly time coordinate is incomplete")
    numeric = frame.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        raise ValueError(
            f"Missing values: {numeric.columns[numeric.isna().any()].tolist()}"
        )
    h20_columns = [name for name in frame if name.endswith("_h20_zj")]
    if not (numeric[h20_columns].gt(0.0) & numeric[h20_columns].lt(200.0)).all().all():
        raise ValueError("H20 outside broad physical range")
    q20_columns = [name for name in frame if "q20" in name and name.endswith("_pw")]
    if not (numeric[q20_columns].abs() < 10.0).all().all():
        raise ValueError("Q20 outside broad physical range")
    surface_columns = [name for name in frame if "surface" in name and name.endswith("_pw")]
    if not (numeric[surface_columns].abs() < 2.0).all().all():
        raise ValueError("Surface heat input outside broad physical range")
    fraction_columns = [name for name in frame if name.endswith("warm_area_fraction")]
    if not (
        (numeric[fraction_columns] >= 0.0)
        & (numeric[fraction_columns] <= 1.0)
    ).all().all():
        raise ValueError("Warm surface area fraction outside 0..1")


def main() -> int:
    args = parse_args()
    if args.chunk_years < 1:
        raise ValueError("--chunk-years must be positive")
    start_year = SOURCE_START_YEAR
    end_year = 1981 if args.test else SOURCE_END_YEAR
    destination = TEST_OUTPUT if args.test else OUTPUT
    if destination.exists() and not args.force:
        print(f"Already exists: {destination}", flush=True)
        return 0

    checkpoint_dir = CHECKPOINT_ROOT / (
        "test_1980_1981" if args.test else "full_1980_2022"
    )
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    print(f"Opening APDRC tracer aggregation: {TRACER_URL}", flush=True)
    tracer = netCDF4.Dataset(TRACER_URL)
    print(f"Opening APDRC velocity aggregation: {VELOCITY_URL}", flush=True)
    velocity = netCDF4.Dataset(VELOCITY_URL)
    try:
        monthly_pieces: list[pd.DataFrame] = []
        for month in range(1, 13):
            month_path = checkpoint_dir / f"calendar_month_{month:02d}.csv"
            if month_path.exists() and not args.force:
                month_frame = pd.read_csv(month_path, parse_dates=["time"])
                print(f"Month {month:02d}: using monthly checkpoint", flush=True)
            else:
                month_dir = checkpoint_dir / f"calendar_month_{month:02d}"
                month_dir.mkdir(parents=True, exist_ok=True)
                chunk_frames: list[pd.DataFrame] = []
                for chunk_start, chunk_end in base.year_chunks(
                    start_year, end_year, args.chunk_years
                ):
                    chunk_path = month_dir / f"{chunk_start}_{chunk_end}.csv"
                    if chunk_path.exists() and not args.force:
                        chunk = pd.read_csv(chunk_path, parse_dates=["time"])
                        print(
                            f"Month {month:02d}, {chunk_start}-{chunk_end}: "
                            "using checkpoint",
                            flush=True,
                        )
                    else:
                        print(
                            f"Month {month:02d}: extracting {chunk_start}-{chunk_end}",
                            flush=True,
                        )
                        chunk = read_month_chunk(
                            tracer,
                            velocity,
                            calendar_month=month,
                            start_year=chunk_start,
                            end_year=chunk_end,
                        )
                        chunk.to_csv(chunk_path, index=False, float_format="%.9g")
                    chunk_frames.append(chunk)
                month_frame = pd.concat(chunk_frames, ignore_index=True).sort_values(
                    "time"
                )
                if len(month_frame) != end_year - start_year + 1:
                    raise ValueError(f"Month {month:02d} is incomplete")
                month_frame.to_csv(month_path, index=False, float_format="%.9g")
                print(f"Month {month:02d}: wrote monthly checkpoint", flush=True)
            monthly_pieces.append(month_frame)
    finally:
        tracer.close()
        velocity.close()

    output = pd.concat(monthly_pieces, ignore_index=True).sort_values("time")
    output = output.reset_index(drop=True)
    validate(output, start_year, end_year)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False, float_format="%.9g")
    print(f"Wrote {destination} ({len(output)} monthly rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
