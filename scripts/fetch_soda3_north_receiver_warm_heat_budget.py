#!/usr/bin/env python3
"""Extract the complete horizontal/surface H20 budget for the 5N--12N box.

The fixed receiver box is 5N--12N, 140W--80W and 0--300 m.  Monthly SODA3
tracer and velocity fields are streamed from APDRC in resumable year chunks.
The output contains H20 storage, eastward Q20 at 140W/80W, northward Q20 at
5N/12N, and both full and T(surface)>20C-gated net surface heating.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import netCDF4
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_chakravorty_transport_baseline as base  # noqa: E402
import fetch_soda3_three_box_warm_heat_budget as three_box  # noqa: E402


OUTPUT = ROOT / "data/derived/research_2026/soda3_north_receiver_budget_terms_1980_2022.csv"
TEST_OUTPUT = ROOT / "data/derived/research_2026/soda3_north_receiver_budget_terms_1980_1981_test.csv"
CHECKPOINT_ROOT = ROOT / "data/interim/research_2026/soda3_north_receiver_budget"

START_YEAR = 1980
END_YEAR = 2022
SOUTH = 5.0
NORTH = 12.0
WEST = 220.0
EAST = 280.0
DEPTH_MAX_M = 300.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Extract 1980--1981 only.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--chunk-years", type=int, default=5)
    return parser.parse_args()


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

    t_yslice = base.contiguous_slice(t_lat_all, SOUTH - 0.5, NORTH + 0.5)
    t_xslice = base.contiguous_slice(t_lon_all, WEST - 0.5, EAST + 0.5)
    t_lat = t_lat_all[t_yslice]
    t_lon = t_lon_all[t_xslice]
    temperature = base.clean(
        tracer.variables["temp"][tslice, zslice, t_yslice, t_xslice]
    )
    net_heating = base.clean(tracer.variables["nh"][tslice, t_yslice, t_xslice])
    if temperature.shape[0] != expected or net_heating.shape[0] != expected:
        raise ValueError("Unexpected number of time records")

    h_lat_mask = three_box.cell_selection(t_lat, SOUTH, NORTH)
    h_lon_mask = three_box.cell_selection(t_lon, WEST, EAST)
    h_lat = t_lat[h_lat_mask]
    h_lon = t_lon[h_lon_mask]
    box_temp = temperature[:, :, h_lat_mask, :][:, :, :, h_lon_mask]
    box_heat_flux = net_heating[:, h_lat_mask, :][:, :, h_lon_mask]
    rows: dict[str, np.ndarray] = {}
    rows["receiver_h20_zj"] = three_box.warm_heat_content_zj(
        box_temp,
        depth=depth,
        latitude=h_lat,
        longitude=h_lon,
    )
    all_pw, warm_pw, warm_fraction = three_box.surface_heat_terms(
        box_heat_flux,
        box_temp[:, 0, :, :],
        latitude=h_lat,
        longitude=h_lon,
    )
    rows["receiver_surface_all_pw"] = all_pw
    rows["receiver_surface_warm_pw"] = warm_pw
    rows["receiver_surface_warm_area_fraction"] = warm_fraction

    # Eastward Q20 at the west/east faces.  Native u latitude faces are
    # averaged to the tracer latitude centers inside 5N--12N.
    u_yslice = base.contiguous_slice(u_lat_all, SOUTH, NORTH)
    u_lat = u_lat_all[u_yslice]
    tracer_section_lat = h_lat
    if u_lat.size != tracer_section_lat.size + 1:
        raise ValueError("Unexpected latitude staggering on zonal gates")
    for label, gate in (("west", WEST), ("east", EAST)):
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
        rows[f"receiver_{label}_q20_east_pw"] = q20

    # Northward Q20 at 5N/12N.  At 5N northward flow enters the receiver;
    # at 12N northward flow leaves it, hence the negative inflow sign.
    v_xslice = base.contiguous_slice(u_lon_all, WEST, EAST)
    v_lon = u_lon_all[v_xslice]
    tracer_v_lon_mask = three_box.cell_selection(t_lon, WEST, EAST)
    tracer_v_lon = t_lon[tracer_v_lon_mask]
    if v_lon.size != tracer_v_lon.size + 1:
        raise ValueError("Unexpected longitude staggering on meridional gates")
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
        _, q20 = base.section_transports(
            boundary_temperature,
            inflow_sign * boundary_v,
            depth,
            base.meridional_section_width(tracer_v_lon, latitude),
        )
        rows[f"receiver_{label}_q20_in_pw"] = q20

    rows["receiver_zonal_convergence_pw"] = (
        rows["receiver_west_q20_east_pw"] - rows["receiver_east_q20_east_pw"]
    )
    rows["receiver_meridional_convergence_pw"] = (
        rows["receiver_south_q20_in_pw"] + rows["receiver_north_q20_in_pw"]
    )
    rows["receiver_resolved_warm_flux_pw"] = (
        rows["receiver_zonal_convergence_pw"]
        + rows["receiver_meridional_convergence_pw"]
        + rows["receiver_surface_warm_pw"]
    )

    years = np.arange(start_year, end_year + 1)
    times = pd.DatetimeIndex(
        [pd.Timestamp(int(year), calendar_month, 15) for year in years]
    )
    return pd.DataFrame(
        {"time": times, "year": years, "month": calendar_month, **rows}
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
    if not numeric["receiver_h20_zj"].between(0.0, 200.0).all():
        raise ValueError("H20 outside broad physical range")
    q_columns = [name for name in frame if "q20" in name and name.endswith("_pw")]
    if not (numeric[q_columns].abs() < 10.0).all().all():
        raise ValueError("Q20 outside broad physical range")
    surface_columns = [name for name in frame if "surface" in name and name.endswith("_pw")]
    if not (numeric[surface_columns].abs() < 2.0).all().all():
        raise ValueError("Surface heat flux outside broad physical range")
    fraction = numeric["receiver_surface_warm_area_fraction"]
    if not fraction.between(0.0, 1.0).all():
        raise ValueError("Warm-area fraction outside 0..1")


def main() -> int:
    args = parse_args()
    if args.chunk_years < 1:
        raise ValueError("--chunk-years must be positive")
    start_year = START_YEAR
    end_year = 1981 if args.test else END_YEAR
    destination = TEST_OUTPUT if args.test else OUTPUT
    checkpoint_dir = CHECKPOINT_ROOT / (
        "test_1980_1981" if args.test else "full_1980_2022"
    )
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not args.force:
        print(f"Already exists: {destination}", flush=True)
        return 0

    print(f"Opening tracer: {base.TRACER_URL}", flush=True)
    tracer = netCDF4.Dataset(base.TRACER_URL)
    print(f"Opening velocity: {base.VELOCITY_URL}", flush=True)
    velocity = netCDF4.Dataset(base.VELOCITY_URL)
    try:
        monthly_pieces: list[pd.DataFrame] = []
        for month in range(1, 13):
            month_path = checkpoint_dir / f"calendar_month_{month:02d}.csv"
            if month_path.exists() and not args.force:
                month_frame = pd.read_csv(month_path, parse_dates=["time"])
                print(f"Month {month:02d}: using checkpoint", flush=True)
            else:
                month_dir = checkpoint_dir / f"calendar_month_{month:02d}"
                month_dir.mkdir(parents=True, exist_ok=True)
                chunk_frames: list[pd.DataFrame] = []
                for first, last in base.year_chunks(start_year, end_year, args.chunk_years):
                    chunk_path = month_dir / f"{first}_{last}.csv"
                    if chunk_path.exists() and not args.force:
                        current = pd.read_csv(chunk_path, parse_dates=["time"])
                        print(
                            f"Month {month:02d}, {first}-{last}: using checkpoint",
                            flush=True,
                        )
                    else:
                        for attempt in range(1, 5):
                            try:
                                current = read_month_chunk(
                                    tracer,
                                    velocity,
                                    calendar_month=month,
                                    start_year=first,
                                    end_year=last,
                                )
                                break
                            except (OSError, RuntimeError):
                                if attempt == 4:
                                    raise
                                print(
                                    f"Month {month:02d}, {first}-{last}: retry {attempt}/4",
                                    flush=True,
                                )
                                time.sleep(2.0 * attempt)
                        current.to_csv(chunk_path, index=False, float_format="%.9g")
                        print(f"Month {month:02d}: fetched {first}-{last}", flush=True)
                    chunk_frames.append(current)
                month_frame = pd.concat(chunk_frames, ignore_index=True).sort_values("time")
                month_frame.to_csv(month_path, index=False, float_format="%.9g")
            monthly_pieces.append(month_frame)
    finally:
        tracer.close()
        velocity.close()

    output = pd.concat(monthly_pieces, ignore_index=True).sort_values("time").reset_index(drop=True)
    validate(output, start_year, end_year)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False, float_format="%.9g")
    print(f"Wrote {destination} ({len(output)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
