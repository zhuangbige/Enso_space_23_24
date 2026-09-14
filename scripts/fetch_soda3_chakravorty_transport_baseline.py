#!/usr/bin/env python3
"""Extract the compact SODA3 indices needed to reproduce Chakravorty Fig. 8.

This script streams small OPeNDAP slices from the APDRC SODA3.15.2 monthly
aggregations.  It does not download or retain the full four-dimensional ocean
fields.  The output contains monthly, absolute warm-water diagnostics for:

* WWV over 5S-5N, 120E-80W;
* eastward transport across 170E, 10S-5N;
* equatorward transport across 5N and 10S, 140E-80W; and
* Q20 heat transports relative to 20 degC for the same sections.

Warm-volume transports are integrated from the surface to the locally and
linearly interpolated, time-varying 20 degC isotherm.  Sign conventions match
Chakravorty et al. (2021): eastward and equatorward transports are positive.

The APDRC aggregation currently spans January 1980-December 2022.  Calendar
months are checkpointed separately so an interrupted extraction can resume.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_chakravorty_transport_baseline_1980_2022.csv"
)
TEST_OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_chakravorty_transport_baseline_1980_1981_test.csv"
)
CHECKPOINT_DIR = (
    ROOT
    / "data/interim/research_2026/"
    "soda3_chakravorty_transport_baseline"
)

TRACER_URL = (
    "https://apdrc.soest.hawaii.edu/dods/public_data/"
    "SODA/soda_3.15.2/monthly_t"
)
VELOCITY_URL = (
    "https://apdrc.soest.hawaii.edu/dods/public_data/"
    "SODA/soda_3.15.2/monthly_u"
)

SOURCE_START_YEAR = 1980
SOURCE_END_YEAR = 2022
DEPTH_MAX_M = 300.0
EARTH_RADIUS_M = 6_371_000.0
RHO0_KG_M3 = 1025.0
CP0_J_KG_K = 3990.0
FILL_THRESHOLD = -1.0e10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test",
        action="store_true",
        help="Extract 1980-1981 only and write a separate test CSV.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace checkpoints and the destination if they exist.",
    )
    parser.add_argument(
        "--chunk-years",
        type=int,
        default=5,
        help="Number of years per OPeNDAP request (default: 5).",
    )
    return parser.parse_args()


def clean(values: np.ndarray) -> np.ndarray:
    """Convert a netCDF masked/fill array to finite float32 plus NaNs."""
    if np.ma.isMaskedArray(values):
        output = np.asarray(values.filled(np.nan), dtype=np.float32)
    else:
        output = np.asarray(values, dtype=np.float32)
    output[output <= FILL_THRESHOLD] = np.nan
    return output


def finite_mean(values: np.ndarray, axis: int) -> np.ndarray:
    """NaN-aware mean without warnings for all-land grid cells."""
    valid = np.isfinite(values)
    count = np.sum(valid, axis=axis)
    total = np.nansum(values, axis=axis)
    return np.divide(
        total,
        count,
        out=np.full(total.shape, np.nan, dtype=float),
        where=count > 0,
    )


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    indices = np.flatnonzero((values >= lower) & (values <= upper))
    if indices.size == 0 or not np.all(np.diff(indices) == 1):
        raise ValueError(f"Cannot form contiguous slice for {lower}..{upper}")
    return slice(int(indices[0]), int(indices[-1]) + 1)


def exact_index(values: np.ndarray, target: float, tolerance: float = 0.01) -> int:
    index = int(np.argmin(np.abs(values - target)))
    if abs(float(values[index]) - target) > tolerance:
        raise ValueError(f"No grid point near {target}; nearest={values[index]}")
    return index


def adjacent_indices(values: np.ndarray, boundary: float) -> tuple[int, int]:
    lower = np.flatnonzero(values < boundary)
    upper = np.flatnonzero(values > boundary)
    if lower.size == 0 or upper.size == 0:
        raise ValueError(f"Boundary {boundary} is outside coordinate range")
    left = int(lower[-1])
    right = int(upper[0])
    if not np.isclose(0.5 * (values[left] + values[right]), boundary, atol=0.01):
        raise ValueError(
            f"Tracer cells {values[left]}, {values[right]} do not straddle {boundary}"
        )
    return left, right


def depth_bounds(depth: np.ndarray, maximum: float = DEPTH_MAX_M) -> np.ndarray:
    bounds = np.empty(depth.size + 1, dtype=float)
    bounds[0] = 0.0
    bounds[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    bounds[-1] = min(maximum, depth[-1] + 0.5 * (depth[-1] - depth[-2]))
    if np.any(np.diff(bounds) <= 0.0):
        raise ValueError("Non-increasing depth-cell bounds")
    return bounds


def d20_from_temperature(temperature: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Linearly interpolate D20 for arrays shaped (time, depth, ...)."""
    temperature = np.asarray(temperature, dtype=float)
    if temperature.ndim < 2 or temperature.shape[1] != depth.size:
        raise ValueError("Temperature depth dimension does not match coordinate")
    crossing = (
        (temperature[:, :-1, ...] >= 20.0)
        & (temperature[:, 1:, ...] < 20.0)
    )
    has_crossing = crossing.any(axis=1)
    index = np.argmax(crossing, axis=1)
    gather = index[:, None, ...]
    t0 = np.take_along_axis(temperature, gather, axis=1)[:, 0, ...]
    t1 = np.take_along_axis(temperature, gather + 1, axis=1)[:, 0, ...]
    z0 = depth[index]
    z1 = depth[index + 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        d20 = z0 + (20.0 - t0) * (z1 - z0) / (t1 - t0)
    d20 = np.where(has_crossing, d20, np.nan)
    valid_surface = np.isfinite(temperature[:, 0, ...])
    d20 = np.where(
        (~has_crossing) & valid_surface & (temperature[:, -1, ...] >= 20.0),
        DEPTH_MAX_M,
        d20,
    )
    d20 = np.where(
        (~has_crossing) & valid_surface & (temperature[:, 0, ...] < 20.0),
        0.0,
        d20,
    )
    return np.clip(d20, 0.0, DEPTH_MAX_M)


def layer_overlap(d20: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Thickness of every model layer located above a column-specific D20."""
    bounds = depth_bounds(depth)
    top = bounds[:-1].reshape((1, depth.size) + (1,) * (d20.ndim - 1))
    bottom = bounds[1:].reshape((1, depth.size) + (1,) * (d20.ndim - 1))
    return np.maximum(
        0.0,
        np.minimum(bottom, d20[:, None, ...]) - top,
    )


def grid_cell_areas(latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    dlat = float(np.median(np.diff(latitude)))
    dlon = float(np.median(np.diff(longitude)))
    south = np.deg2rad(latitude - dlat / 2.0)
    north = np.deg2rad(latitude + dlat / 2.0)
    meridional_factor = EARTH_RADIUS_M**2 * (np.sin(north) - np.sin(south))
    return meridional_factor[:, None] * np.deg2rad(dlon) * np.ones(
        (1, longitude.size)
    )


def zonal_section_width(latitude: np.ndarray) -> np.ndarray:
    dlat = float(np.median(np.diff(latitude)))
    return np.full(latitude.size, EARTH_RADIUS_M * np.deg2rad(dlat))


def meridional_section_width(longitude: np.ndarray, latitude: float) -> np.ndarray:
    dlon = float(np.median(np.diff(longitude)))
    return np.full(
        longitude.size,
        EARTH_RADIUS_M * np.cos(np.deg2rad(latitude)) * np.deg2rad(dlon),
    )


def section_transports(
    temperature: np.ndarray,
    velocity: np.ndarray,
    depth: np.ndarray,
    horizontal_width: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return D20 warm-volume transport (Sv) and Q20 heat transport (PW)."""
    if temperature.shape != velocity.shape:
        raise ValueError(
            f"Temperature/velocity section mismatch: {temperature.shape}, {velocity.shape}"
        )
    d20 = d20_from_temperature(temperature, depth)
    overlap = layer_overlap(d20, depth)
    width = horizontal_width.reshape((1, 1, horizontal_width.size))
    valid = np.isfinite(temperature) & np.isfinite(velocity)
    volume_m3s = np.nansum(
        np.where(valid, velocity * overlap * width, np.nan),
        axis=(1, 2),
    )
    dz = np.diff(depth_bounds(depth)).reshape((1, depth.size, 1))
    warm_excess = np.where(valid, np.maximum(temperature - 20.0, 0.0), np.nan)
    heat_w = RHO0_KG_M3 * CP0_J_KG_K * np.nansum(
        velocity * warm_excess * dz * width,
        axis=(1, 2),
    )
    return volume_m3s / 1.0e6, heat_w / 1.0e15


def time_slice(start_year: int, end_year: int, calendar_month: int) -> slice:
    start = (start_year - SOURCE_START_YEAR) * 12 + calendar_month - 1
    stop = (end_year - SOURCE_START_YEAR + 1) * 12
    return slice(start, stop, 12)


def year_chunks(
    start_year: int,
    end_year: int,
    chunk_years: int,
) -> list[tuple[int, int]]:
    if chunk_years < 1:
        raise ValueError("chunk_years must be positive")
    chunks: list[tuple[int, int]] = []
    current = start_year
    while current <= end_year:
        chunk_end = min(end_year, current + chunk_years - 1)
        chunks.append((current, chunk_end))
        current = chunk_end + 1
    return chunks


def read_month(
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

    zslice = contiguous_slice(t_depth_all, 0.0, DEPTH_MAX_M)
    depth = t_depth_all[zslice]
    tslice = time_slice(start_year, end_year, calendar_month)
    expected = end_year - start_year + 1

    # WWV: exact Chakravorty tropical Pacific domain.
    eq_yslice = contiguous_slice(t_lat_all, -5.0, 5.0)
    basin_xslice = contiguous_slice(t_lon_all, 120.0, 280.0)
    eq_lat = t_lat_all[eq_yslice]
    basin_lon = t_lon_all[basin_xslice]
    temp_eq = clean(
        tracer.variables["temp"][tslice, zslice, eq_yslice, basin_xslice]
    )
    if temp_eq.shape[0] != expected:
        raise ValueError(f"Expected {expected} years, received {temp_eq.shape[0]}")
    d20_eq = d20_from_temperature(temp_eq, depth)
    wwv_m3 = np.nansum(
        d20_eq * grid_cell_areas(eq_lat, basin_lon)[None, :, :],
        axis=(1, 2),
    )

    # 170E: tracer temperatures straddle the velocity face; u is averaged
    # from velocity-grid latitude corners to tracer latitude centers.
    z_t_yslice = contiguous_slice(t_lat_all, -10.0, 5.0)
    z_lat = t_lat_all[z_t_yslice]
    z_left, z_right = adjacent_indices(t_lon_all, 170.0)
    temp_zonal_pair = clean(
        tracer.variables["temp"][
            tslice,
            zslice,
            z_t_yslice,
            slice(z_left, z_right + 1),
        ]
    )
    temp_zonal = finite_mean(temp_zonal_pair, axis=3)
    u_yslice = contiguous_slice(u_lat_all, -10.0, 5.0)
    u_xindex = exact_index(u_lon_all, 170.0)
    raw_u = clean(
        velocity.variables["u"][
            tslice,
            zslice,
            u_yslice,
            slice(u_xindex, u_xindex + 1),
        ]
    )[:, :, :, 0]
    u_zonal = 0.5 * (raw_u[:, :, :-1] + raw_u[:, :, 1:])
    if z_lat.size + 1 != raw_u.shape[2]:
        raise ValueError("Unexpected latitude staggering at 170E")
    z_volume, z_q20 = section_transports(
        temp_zonal,
        u_zonal,
        depth,
        zonal_section_width(z_lat),
    )
    eq_section = z_lat >= -5.0
    z_eq_volume, z_eq_q20 = section_transports(
        temp_zonal[:, :, eq_section],
        u_zonal[:, :, eq_section],
        depth,
        zonal_section_width(z_lat[eq_section]),
    )

    # Meridional sections: v is averaged from longitude corners to tracer
    # cell centers.  Convert the native northward-positive sign to the
    # paper's equatorward-positive convention.
    m_xslice = contiguous_slice(t_lon_all, 140.0, 280.0)
    m_lon = t_lon_all[m_xslice]
    v_xslice = contiguous_slice(u_lon_all, 140.0, 280.0)

    meridional: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for label, boundary, sign in (
        ("5n", 5.0, -1.0),
        ("10s", -10.0, 1.0),
    ):
        south, north = adjacent_indices(t_lat_all, boundary)
        temp_pair = clean(
            tracer.variables["temp"][
                tslice,
                zslice,
                slice(south, north + 1),
                m_xslice,
            ]
        )
        temp_boundary = finite_mean(temp_pair, axis=2)
        v_yindex = exact_index(u_lat_all, boundary)
        raw_v = clean(
            velocity.variables["v"][
                tslice,
                zslice,
                slice(v_yindex, v_yindex + 1),
                v_xslice,
            ]
        )[:, :, 0, :]
        v_boundary = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
        if v_boundary.shape[2] != m_lon.size:
            raise ValueError(f"Unexpected longitude staggering at {boundary}")
        volume, q20 = section_transports(
            temp_boundary,
            sign * v_boundary,
            depth,
            meridional_section_width(m_lon, boundary),
        )
        meridional[label] = volume, q20

    years = np.arange(start_year, end_year + 1)
    times = pd.DatetimeIndex(
        [pd.Timestamp(int(year), calendar_month, 15) for year in years]
    )
    return pd.DataFrame(
        {
            "time": times,
            "year": years,
            "month": calendar_month,
            "wwv_5s5n_120e80w_1e14m3": wwv_m3 / 1.0e14,
            "zonal_170e_10s5n_warm_volume_sv": z_volume,
            "zonal_170e_10s5n_q20_pw": z_q20,
            "zonal_170e_5s5n_warm_volume_sv": z_eq_volume,
            "zonal_170e_5s5n_q20_pw": z_eq_q20,
            "meridional_5n_equatorward_warm_volume_sv": meridional["5n"][0],
            "meridional_5n_equatorward_q20_pw": meridional["5n"][1],
            "meridional_10s_equatorward_warm_volume_sv": meridional["10s"][0],
            "meridional_10s_equatorward_q20_pw": meridional["10s"][1],
        }
    )


def validate(output: pd.DataFrame, start_year: int, end_year: int) -> None:
    expected = (end_year - start_year + 1) * 12
    if len(output) != expected:
        raise ValueError(f"Expected {expected} rows, found {len(output)}")
    times = pd.DatetimeIndex(output["time"])
    if not times.is_unique or not times.is_monotonic_increasing:
        raise ValueError("Time coordinate is not unique and increasing")
    expected_times = pd.date_range(
        f"{start_year}-01-01", f"{end_year}-12-01", freq="MS"
    ) + pd.Timedelta(days=14)
    if not times.equals(expected_times):
        raise ValueError("Monthly time coordinate is incomplete")
    numeric = output.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        missing = numeric.columns[numeric.isna().any()].tolist()
        raise ValueError(f"Missing monthly diagnostics: {missing}")
    if not output["wwv_5s5n_120e80w_1e14m3"].between(10.0, 40.0).all():
        raise ValueError("WWV is outside broad physical QA range")
    transport_columns = [name for name in output if name.endswith("_sv")]
    if not (numeric[transport_columns].abs() < 500.0).all().all():
        raise ValueError("Warm-volume transport exceeds broad QA range")
    heat_columns = [name for name in output if name.endswith("_pw")]
    if not (numeric[heat_columns].abs() < 10.0).all().all():
        raise ValueError("Q20 heat transport exceeds broad QA range")


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

    checkpoint_dir = CHECKPOINT_DIR / (
        "test_1980_1981" if args.test else "full_1980_2022"
    )
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    print(f"Opening APDRC tracer aggregation: {TRACER_URL}", flush=True)
    tracer = netCDF4.Dataset(TRACER_URL)
    print(f"Opening APDRC velocity aggregation: {VELOCITY_URL}", flush=True)
    velocity = netCDF4.Dataset(VELOCITY_URL)
    try:
        pieces: list[pd.DataFrame] = []
        for month in range(1, 13):
            checkpoint = checkpoint_dir / f"calendar_month_{month:02d}.csv"
            if checkpoint.exists() and not args.force:
                current = pd.read_csv(checkpoint, parse_dates=["time"])
                print(f"Month {month:02d}: using {checkpoint}", flush=True)
            else:
                month_dir = checkpoint_dir / f"calendar_month_{month:02d}"
                month_dir.mkdir(parents=True, exist_ok=True)
                chunk_pieces: list[pd.DataFrame] = []
                for chunk_start, chunk_end in year_chunks(
                    start_year,
                    end_year,
                    args.chunk_years,
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
                            f"Month {month:02d}: extracting "
                            f"{chunk_start}-{chunk_end}",
                            flush=True,
                        )
                        chunk = read_month(
                            tracer,
                            velocity,
                            calendar_month=month,
                            start_year=chunk_start,
                            end_year=chunk_end,
                        )
                        chunk.to_csv(
                            chunk_path,
                            index=False,
                            float_format="%.9g",
                        )
                    chunk_pieces.append(chunk)
                current = pd.concat(chunk_pieces, ignore_index=True).sort_values(
                    "time"
                )
                if len(current) != end_year - start_year + 1:
                    raise ValueError(
                        f"Month {month:02d} has {len(current)} rows; "
                        f"expected {end_year - start_year + 1}"
                    )
                current.to_csv(checkpoint, index=False, float_format="%.9g")
                print(f"Month {month:02d}: wrote checkpoint", flush=True)
            pieces.append(current)
    finally:
        tracer.close()
        velocity.close()

    output = pd.concat(pieces, ignore_index=True).sort_values("time")
    output = output.reset_index(drop=True)
    validate(output, start_year, end_year)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False, float_format="%.9g")
    print(f"Wrote {destination} ({len(output)} monthly rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
