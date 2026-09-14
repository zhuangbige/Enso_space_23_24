#!/usr/bin/env python3
"""Fetch SODA3 fixed-depth boundary terms for a three-box enthalpy budget.

This is the non-H20 counterpart of ``fetch_soda3_three_box_warm_heat_budget``.
It integrates the complete 0--300 m section rather than applying a 20 degC
isotherm or temperature threshold.  The fixed boxes are west (160E--180E),
central (180E--220E), and east (220E--280E), all spanning 10S--5N.

For every face the output retains volume transport, heat transport relative
to 0 degC, wet section area, and the area integral of temperature.  A single
uniform normal-velocity correction is then applied to the four faces of each
box so that corrected net volume transport is exactly zero.  This makes the
*total* corrected heat convergence invariant to the arbitrary reference
temperature.  Individual face partitions remain reference dependent and are
therefore accompanied by corrected face-volume transports.
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
import fetch_soda3_three_box_warm_heat_budget as warm  # noqa: E402


OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_enthalpy_boundary_terms_1980_2022.csv"
)
TEST_OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_enthalpy_boundary_terms_1980_1981_test.csv"
)
CHECKPOINT_ROOT = (
    ROOT
    / "data/interim/research_2026/"
    "soda3_three_box_enthalpy_boundary_terms"
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
FACE_NAMES = ("west", "east", "south", "north")


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


def section_moments(
    temperature: np.ndarray,
    velocity: np.ndarray,
    depth: np.ndarray,
    horizontal_width: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Integrate full-depth section volume, heat, area, and temperature area.

    Parameters use arrays shaped ``(time, depth, horizontal)``.  Positive
    transport follows the native sign of ``velocity``.  Returned units are
    Sv, PW relative to 0 degC, m2, and degC m2, respectively.
    """
    temperature = np.asarray(temperature, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    depth = np.asarray(depth, dtype=float)
    horizontal_width = np.asarray(horizontal_width, dtype=float)
    if temperature.shape != velocity.shape:
        raise ValueError(
            f"Temperature/velocity section mismatch: {temperature.shape}, "
            f"{velocity.shape}"
        )
    if temperature.ndim != 3 or temperature.shape[1] != depth.size:
        raise ValueError("Section must be shaped (time, depth, horizontal)")
    if temperature.shape[2] != horizontal_width.size:
        raise ValueError("Horizontal width does not match section")

    dz = np.diff(base.depth_bounds(depth, DEPTH_MAX_M)).reshape(
        (1, depth.size, 1)
    )
    width = horizontal_width.reshape((1, 1, horizontal_width.size))
    element_area = dz * width
    valid = np.isfinite(temperature) & np.isfinite(velocity)
    volume_m3s = np.nansum(
        np.where(valid, velocity * element_area, np.nan), axis=(1, 2)
    )
    heat_w = RHO0_KG_M3 * CP0_J_KG_K * np.nansum(
        np.where(valid, velocity * temperature * element_area, np.nan),
        axis=(1, 2),
    )
    area_m2 = np.nansum(
        np.where(valid, np.broadcast_to(element_area, valid.shape), np.nan),
        axis=(1, 2),
    )
    temperature_area_cm2 = np.nansum(
        np.where(valid, temperature * element_area, np.nan), axis=(1, 2)
    )
    return (
        volume_m3s / 1.0e6,
        heat_w / 1.0e15,
        area_m2,
        temperature_area_cm2,
    )


def mass_balance_box_faces(
    faces: dict[str, dict[str, np.ndarray]],
) -> dict[str, np.ndarray]:
    """Correct four inward-positive faces to zero net volume transport.

    The same scalar normal-velocity correction is applied over the wet area
    of every face.  Heat transports are corrected consistently using each
    face's area integral of temperature.
    """
    missing = set(FACE_NAMES) - set(faces)
    if missing:
        raise KeyError(f"Missing box faces: {sorted(missing)}")
    volume_m3s = sum(np.asarray(faces[name]["volume_sv"]) for name in FACE_NAMES)
    volume_m3s = volume_m3s * 1.0e6
    total_area_m2 = sum(np.asarray(faces[name]["area_m2"]) for name in FACE_NAMES)
    correction_m_s = np.divide(
        volume_m3s,
        total_area_m2,
        out=np.full(volume_m3s.shape, np.nan, dtype=float),
        where=total_area_m2 > 0.0,
    )
    output: dict[str, np.ndarray] = {
        "mass_imbalance_sv": volume_m3s / 1.0e6,
        "total_face_area_m2": total_area_m2,
        "mass_correction_m_s": correction_m_s,
    }
    heat_sum = np.zeros(volume_m3s.shape, dtype=float)
    volume_sum = np.zeros(volume_m3s.shape, dtype=float)
    for name in FACE_NAMES:
        face = faces[name]
        corrected_volume_sv = (
            np.asarray(face["volume_sv"])
            - correction_m_s * np.asarray(face["area_m2"]) / 1.0e6
        )
        corrected_heat0_pw = (
            np.asarray(face["heat0_pw"])
            - RHO0_KG_M3
            * CP0_J_KG_K
            * correction_m_s
            * np.asarray(face["temperature_area_cm2"])
            / 1.0e15
        )
        output[f"{name}_volume_in_corr_sv"] = corrected_volume_sv
        output[f"{name}_heat0_in_corr_pw"] = corrected_heat0_pw
        heat_sum += corrected_heat0_pw
        volume_sum += corrected_volume_sv
    output["volume_convergence_corr_sv"] = volume_sum
    output["heat0_convergence_corr_pw"] = heat_sum
    return output


def _face(
    volume_sv: np.ndarray,
    heat0_pw: np.ndarray,
    area_m2: np.ndarray,
    temperature_area_cm2: np.ndarray,
    inward_sign: float,
) -> dict[str, np.ndarray]:
    """Orient native section transports positive into one box."""
    return {
        "volume_sv": inward_sign * volume_sv,
        "heat0_pw": inward_sign * heat0_pw,
        "area_m2": area_m2,
        "temperature_area_cm2": temperature_area_cm2,
    }


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
    t_xslice = base.contiguous_slice(t_lon_all, 159.5, 280.5)
    t_lat = t_lat_all[t_yslice]
    t_lon = t_lon_all[t_xslice]
    temperature = base.clean(
        tracer.variables["temp"][tslice, zslice, t_yslice, t_xslice]
    )
    if temperature.shape[0] != expected:
        raise ValueError("Unexpected number of tracer time records")

    h_lat_mask = warm.cell_selection(t_lat, SOUTH, NORTH)
    tracer_section_lat = t_lat[h_lat_mask]
    u_yslice = base.contiguous_slice(u_lat_all, SOUTH, NORTH)
    u_lat = u_lat_all[u_yslice]
    if u_lat.size != tracer_section_lat.size + 1:
        raise ValueError("Unexpected latitude staggering on zonal gates")

    zonal: dict[float, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    rows: dict[str, np.ndarray] = {}
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
        moments = section_moments(
            gate_temperature,
            gate_u,
            depth,
            base.zonal_section_width(tracer_section_lat),
        )
        zonal[gate] = moments
        label = f"{int(gate)}e"
        for metric, values in zip(
            ("volume_east_sv", "heat0_east_pw", "area_m2", "temperature_area_cm2"),
            moments,
            strict=True,
        ):
            rows[f"gate_{label}_{metric}"] = values

    v_xslice = base.contiguous_slice(u_lon_all, 160.0, 280.0)
    v_lon = u_lon_all[v_xslice]
    tracer_v_lon_mask = warm.cell_selection(t_lon, 160.0, 280.0)
    tracer_v_lon = t_lon[tracer_v_lon_mask]
    if v_lon.size != tracer_v_lon.size + 1:
        raise ValueError("Unexpected longitude staggering on meridional gates")
    boundary_data: dict[str, tuple[np.ndarray, np.ndarray, float]] = {}
    for label, latitude in (("south", SOUTH), ("north", NORTH)):
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
        boundary_data[label] = (boundary_temperature, boundary_v, latitude)

    for box, (west, east) in BOXES.items():
        west_moments = zonal[west]
        east_moments = zonal[east]
        faces = {
            "west": _face(*west_moments, inward_sign=1.0),
            "east": _face(*east_moments, inward_sign=-1.0),
        }
        xmask = warm.cell_selection(tracer_v_lon, west, east)
        box_lon = tracer_v_lon[xmask]
        for boundary_label, inward_sign in (("south", 1.0), ("north", -1.0)):
            boundary_temp, boundary_v, latitude = boundary_data[boundary_label]
            moments = section_moments(
                boundary_temp[:, :, xmask],
                boundary_v[:, :, xmask],
                depth,
                base.meridional_section_width(box_lon, latitude),
            )
            faces[boundary_label] = _face(*moments, inward_sign=inward_sign)
            for metric, values in zip(
                (
                    "volume_north_sv",
                    "heat0_north_pw",
                    "area_m2",
                    "temperature_area_cm2",
                ),
                moments,
                strict=True,
            ):
                rows[f"{box}_{boundary_label}_{metric}"] = values

        corrected = mass_balance_box_faces(faces)
        for metric, values in corrected.items():
            rows[f"{box}_{metric}"] = values

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
    for box in BOXES:
        closure = numeric[f"{box}_volume_convergence_corr_sv"].abs().max()
        if closure > 1.0e-9:
            raise ValueError(f"Corrected volume budget does not close for {box}: {closure}")
        if numeric[f"{box}_mass_correction_m_s"].abs().max() > 2.0:
            raise ValueError(f"Mass correction outside broad range for {box}")
    volume_columns = [name for name in numeric if name.endswith("_sv")]
    heat_columns = [name for name in numeric if name.endswith("_pw")]
    if not (numeric[volume_columns].abs() < 2000.0).all().all():
        raise ValueError("Volume transport outside broad range")
    if not (numeric[heat_columns].abs() < 200.0).all().all():
        raise ValueError("Heat transport outside broad range")


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
                        chunk.to_csv(chunk_path, index=False, float_format="%.10g")
                    chunk_frames.append(chunk)
                month_frame = pd.concat(chunk_frames, ignore_index=True).sort_values(
                    "time"
                )
                if len(month_frame) != end_year - start_year + 1:
                    raise ValueError(f"Month {month:02d} is incomplete")
                month_frame.to_csv(month_path, index=False, float_format="%.10g")
                print(f"Month {month:02d}: wrote monthly checkpoint", flush=True)
            monthly_pieces.append(month_frame)
    finally:
        tracer.close()
        velocity.close()

    output = pd.concat(monthly_pieces, ignore_index=True).sort_values("time")
    output = output.reset_index(drop=True)
    validate(output, start_year, end_year)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False, float_format="%.10g")
    print(f"Wrote {destination} ({len(output)} monthly rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
