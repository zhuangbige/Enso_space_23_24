#!/usr/bin/env python3
"""Test whether the inferred weak poleward H20 exit depends on north boundary.

The script streams compact SODA3.15.2 monthly sections at 10N, 12N and 15N,
computes northward Q20 = rho0*cp*integral[v*max(T-20C, 0)] dA, removes the
1980--2022 calendar-month linear climatology/trend, applies the same centered
three-month smoothing as the receiver-box budget, and integrates Dec(0)--
May(+1) using each month's actual number of seconds.

Historical data (1980--2022) come from the APDRC monthly OPeNDAP aggregates.
The 2023/24 extension comes from the official University of Maryland annual
SODA3.15.2 files.  Positive values are northward (out of a 5N--latitude box).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import h5py
import netCDF4
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_chakravorty_transport_baseline as base  # noqa: E402


OUT_RAW = ROOT / "data/derived/research_2026/soda3_north_boundary_q20_10_12_15_raw.csv"
OUT_MONTHLY = ROOT / "data/derived/research_2026/soda3_north_boundary_q20_10_12_15_monthly.csv"
OUT_EVENTS = ROOT / "data/derived/research_2026/soda3_north_boundary_q20_10_12_15_events.csv"
OUT_SUMMARY = ROOT / "data/derived/research_2026/soda3_north_boundary_q20_10_12_15_summary.csv"
CHECKPOINT = ROOT / "data/interim/research_2026/soda3_north_boundary_sensitivity"

LATITUDES = (10.0, 12.0, 15.0)
WEST = 220.0
EAST = 280.0
DEPTH_MAX_M = 300.0
BASELINE = (1980, 2022)
START_YEAR = 1980
END_YEAR = 2022
RECENT_MONTHS = {2023: tuple(range(1, 13)), 2024: tuple(range(1, 8))}
ANNUAL_URL = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)
PHASE_START = 11
PHASE_END = 16
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260809
EVENTS = {
    "CT": (1982, 1986, 1997, 2006),
    "CP": (1991, 1994, 2002, 2004),
}


def import_fsspec():
    import fsspec

    return fsspec


def same_month_detrended(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int] = BASELINE,
) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in range(1, 13):
        selected = (
            (times.month == month)
            & np.isfinite(values)
            & (times.year >= baseline[0])
            & (times.year <= baseline[1])
        )
        years = times.year[selected].astype(float)
        design = np.column_stack([np.ones(selected.sum()), years])
        intercept, slope = np.linalg.lstsq(design, values[selected], rcond=None)[0]
        apply = (times.month == month) & np.isfinite(values)
        output[apply] = values[apply] - (
            intercept + slope * times.year[apply].astype(float)
        )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--chunk-years", type=int, default=15)
    parser.add_argument(
        "--historical-only",
        action="store_true",
        help="Use 1980--2022 only; sufficient for CT/CP and 1997/2015 sensitivity.",
    )
    return parser.parse_args()


def historical_month(
    tracer: netCDF4.Dataset,
    velocity: netCDF4.Dataset,
    month: int,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    t_depth = np.asarray(tracer.variables["lev"][:], dtype=float)
    t_lat = np.asarray(tracer.variables["lat"][:], dtype=float)
    t_lon = np.asarray(tracer.variables["lon"][:], dtype=float) % 360.0
    v_depth = np.asarray(velocity.variables["lev"][:], dtype=float)
    v_lat = np.asarray(velocity.variables["lat"][:], dtype=float)
    v_lon = np.asarray(velocity.variables["lon"][:], dtype=float) % 360.0
    if not np.allclose(t_depth, v_depth):
        raise ValueError("Tracer and velocity depth grids differ")

    zslice = base.contiguous_slice(t_depth, 0.0, DEPTH_MAX_M)
    depth = t_depth[zslice]
    tslice = base.time_slice(start_year, end_year, month)
    t_yslice = base.contiguous_slice(t_lat, min(LATITUDES) - 0.5, max(LATITUDES) + 0.5)
    t_xslice = base.contiguous_slice(t_lon, WEST - 0.5, EAST + 0.5)
    local_t_lat = t_lat[t_yslice]
    local_t_lon = t_lon[t_xslice]
    temperature = base.clean(tracer.variables["temp"][tslice, zslice, t_yslice, t_xslice])

    v_xslice = base.contiguous_slice(v_lon, WEST, EAST)
    local_v_lon = v_lon[v_xslice]
    tracer_lon_mask = (local_t_lon >= WEST) & (local_t_lon <= EAST)
    section_lon = local_t_lon[tracer_lon_mask]
    if local_v_lon.size != section_lon.size + 1:
        raise ValueError("Unexpected longitude staggering")

    rows: dict[str, np.ndarray] = {}
    for latitude in LATITUDES:
        below_global, above_global = base.adjacent_indices(t_lat, latitude)
        below = int(np.flatnonzero(np.isclose(local_t_lat, t_lat[below_global]))[0])
        above = int(np.flatnonzero(np.isclose(local_t_lat, t_lat[above_global]))[0])
        boundary_temperature = 0.5 * (
            temperature[:, :, below, :][:, :, tracer_lon_mask]
            + temperature[:, :, above, :][:, :, tracer_lon_mask]
        )
        yindex = base.exact_index(v_lat, latitude)
        raw_v = base.clean(
            velocity.variables["v"][tslice, zslice, slice(yindex, yindex + 1), v_xslice]
        )[:, :, 0, :]
        boundary_v = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
        _, q20 = base.section_transports(
            boundary_temperature,
            boundary_v,
            depth,
            base.meridional_section_width(section_lon, latitude),
        )
        rows[f"q20_north_{int(latitude)}n_pw"] = q20

    years = np.arange(start_year, end_year + 1)
    return pd.DataFrame(
        {
            "time": [pd.Timestamp(int(year), month, 15) for year in years],
            "year": years,
            "month": month,
            **rows,
        }
    )


def fetch_historical(force: bool, chunk_years: int) -> pd.DataFrame:
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    targets = [
        CHECKPOINT / f"historical_m{month:02d}_{first}_{last}.csv"
        for month in range(1, 13)
        for first, last in base.year_chunks(START_YEAR, END_YEAR, chunk_years)
    ]
    if not force and all(target.exists() for target in targets):
        return (
            pd.concat([pd.read_csv(target, parse_dates=["time"]) for target in targets], ignore_index=True)
            .sort_values("time")
            .reset_index(drop=True)
        )
    tracer = netCDF4.Dataset(base.TRACER_URL)
    velocity = netCDF4.Dataset(base.VELOCITY_URL)
    pieces: list[pd.DataFrame] = []
    try:
        for month in range(1, 13):
            month_parts: list[pd.DataFrame] = []
            for first, last in base.year_chunks(START_YEAR, END_YEAR, chunk_years):
                target = CHECKPOINT / f"historical_m{month:02d}_{first}_{last}.csv"
                if target.exists() and not force:
                    current = pd.read_csv(target, parse_dates=["time"])
                else:
                    for attempt in range(1, 5):
                        try:
                            current = historical_month(tracer, velocity, month, first, last)
                            break
                        except (OSError, RuntimeError):
                            if attempt == 4:
                                raise
                            time.sleep(2.0 * attempt)
                    current.to_csv(target, index=False)
                month_parts.append(current)
            pieces.append(pd.concat(month_parts, ignore_index=True))
            print(f"historical month {month:02d} complete", flush=True)
    finally:
        tracer.close()
        velocity.close()
    return pd.concat(pieces, ignore_index=True).sort_values("time").reset_index(drop=True)


def recent_year(year: int, months: tuple[int, ...]) -> pd.DataFrame:
    fsspec = import_fsspec()
    remote = fsspec.open(
        ANNUAL_URL.format(year=year),
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as ds:
            depth_all = np.asarray(ds["st_ocean"][:], dtype=float)
            t_lat = np.asarray(ds["yt_ocean"][:], dtype=float)
            t_lon = np.asarray(ds["xt_ocean"][:], dtype=float) % 360.0
            v_lat = np.asarray(ds["yu_ocean"][:], dtype=float)
            v_lon = np.asarray(ds["xu_ocean"][:], dtype=float) % 360.0
            zslice = base.contiguous_slice(depth_all, 0.0, DEPTH_MAX_M)
            depth = depth_all[zslice]
            t_yslice = base.contiguous_slice(t_lat, min(LATITUDES) - 0.5, max(LATITUDES) + 0.5)
            t_xslice = base.contiguous_slice(t_lon, WEST - 0.5, EAST + 0.5)
            local_t_lat = t_lat[t_yslice]
            local_t_lon = t_lon[t_xslice]
            time_slice = slice(months[0] - 1, months[-1])
            temperature = base.clean(ds["temp"][time_slice, zslice, t_yslice, t_xslice])

            v_xslice = base.contiguous_slice(v_lon, WEST, EAST)
            local_v_lon = v_lon[v_xslice]
            tracer_lon_mask = (local_t_lon >= WEST) & (local_t_lon <= EAST)
            section_lon = local_t_lon[tracer_lon_mask]
            rows: dict[str, np.ndarray] = {}
            for latitude in LATITUDES:
                below_global, above_global = base.adjacent_indices(t_lat, latitude)
                below = int(np.flatnonzero(np.isclose(local_t_lat, t_lat[below_global]))[0])
                above = int(np.flatnonzero(np.isclose(local_t_lat, t_lat[above_global]))[0])
                boundary_temperature = 0.5 * (
                    temperature[:, :, below, :][:, :, tracer_lon_mask]
                    + temperature[:, :, above, :][:, :, tracer_lon_mask]
                )
                yindex = base.exact_index(v_lat, latitude)
                raw_v = base.clean(
                    ds["v"][time_slice, zslice, slice(yindex, yindex + 1), v_xslice]
                )[:, :, 0, :]
                boundary_v = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
                _, q20 = base.section_transports(
                    boundary_temperature,
                    boundary_v,
                    depth,
                    base.meridional_section_width(section_lon, latitude),
                )
                rows[f"q20_north_{int(latitude)}n_pw"] = q20
    finally:
        remote.close()
    return pd.DataFrame(
        {
            "time": [pd.Timestamp(year, month, 15) for month in months],
            "year": year,
            "month": months,
            **rows,
        }
    )


def fetch_recent(force: bool) -> pd.DataFrame:
    pieces = []
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    for year, months in RECENT_MONTHS.items():
        target = CHECKPOINT / f"recent_{year}.csv"
        if target.exists() and not force:
            current = pd.read_csv(target, parse_dates=["time"])
        else:
            current = recent_year(year, months)
            current.to_csv(target, index=False)
        pieces.append(current)
        print(f"recent {year} complete", flush=True)
    return pd.concat(pieces, ignore_index=True)


def process(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    output = raw.sort_values("time").reset_index(drop=True).copy()
    output["time"] = pd.to_datetime(output["time"])
    times = pd.DatetimeIndex(output["time"])
    expected = pd.date_range("1980-01-01", times[-1].replace(day=1), freq="MS") + pd.Timedelta(days=14)
    if not times.equals(expected):
        raise ValueError("Incomplete monthly time axis")

    for latitude in LATITUDES:
        source = f"q20_north_{int(latitude)}n_pw"
        anomaly = same_month_detrended(output[source].to_numpy(), times, BASELINE)
        output[f"{source}_anom"] = anomaly
        output[f"{source}_sm3"] = pd.Series(anomaly).rolling(3, center=True, min_periods=3).mean()

    indexed = output.set_index(times)
    additional = tuple(
        year for year in (2015, 2023)
        if pd.Timestamp(year + 1, 5, 15) <= times[-1]
    )
    event_groups = {**EVENTS, "additional": additional}
    event_rows: list[dict[str, object]] = []
    for event_class, years in event_groups.items():
        for event_year in years:
            selected_times = [
                pd.Timestamp(event_year, 1, 15) + pd.DateOffset(months=offset)
                for offset in range(PHASE_START, PHASE_END + 1)
            ]
            selected = indexed.loc[selected_times]
            factor = pd.DatetimeIndex(selected.index).days_in_month.to_numpy(dtype=float) * 86400.0 / 1.0e6
            for latitude in LATITUDES:
                source = f"q20_north_{int(latitude)}n_pw_sm3"
                event_rows.append(
                    {
                        "event_class": event_class,
                        "event_year": event_year,
                        "phase": "mature_decay_Dec0_to_May1",
                        "latitude": latitude,
                        "northward_cumulative_zj": float(np.sum(selected[source].to_numpy() * factor)),
                    }
                )
    events = pd.DataFrame(event_rows)

    rng = np.random.default_rng(RANDOM_SEED)
    summary_rows: list[dict[str, object]] = []
    for latitude in LATITUDES:
        for event_class, years in EVENTS.items():
            values = (
                events.loc[
                    (events.event_class == event_class) & (events.latitude == latitude)
                ]
                .set_index("event_year")["northward_cumulative_zj"]
                .reindex(years)
                .to_numpy(dtype=float)
            )
            idx = rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))
            boot = values[idx].mean(axis=1)
            low, high = np.quantile(boot, [0.025, 0.975])
            summary_rows.append(
                {
                    "event_class": event_class,
                    "latitude": latitude,
                    "n_events": len(values),
                    "mean_northward_zj": float(values.mean()),
                    "ci_low_zj": float(low),
                    "ci_high_zj": float(high),
                }
            )
    return output, events, pd.DataFrame(summary_rows)


def main() -> None:
    args = parse_args()
    if OUT_RAW.exists() and not args.force and not args.historical_only:
        raw = pd.read_csv(OUT_RAW, parse_dates=["time"])
    else:
        historical = fetch_historical(args.force, args.chunk_years)
        if args.historical_only:
            raw = historical.sort_values("time").reset_index(drop=True)
        else:
            recent = fetch_recent(args.force)
            raw = pd.concat([historical, recent], ignore_index=True).sort_values("time").reset_index(drop=True)
        OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(
            OUT_RAW if not args.historical_only else OUT_RAW.with_name("soda3_north_boundary_q20_10_12_15_raw_1980_2022.csv"),
            index=False,
        )
    monthly, events, summary = process(raw)
    monthly.to_csv(OUT_MONTHLY, index=False)
    events.to_csv(OUT_EVENTS, index=False)
    summary.to_csv(OUT_SUMMARY, index=False)
    print(summary.to_string(index=False), flush=True)
    print(events.loc[events.event_year.isin([1997, 2015, 2023])].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
