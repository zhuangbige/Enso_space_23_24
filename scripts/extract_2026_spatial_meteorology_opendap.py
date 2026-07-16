#!/usr/bin/env python3
"""Extract 2026 spatial meteorology fields for ENSO/FEP diagnostics.

The output is intentionally compact: it stores only current 2026 anomaly maps
and equatorial Hovmoller slices needed for the paper-style quick-look figures.
Monthly anomaly fields use a 1982-2022 monthly climatology. CPC OLR is already
an anomaly product, so it is averaged directly over the selected periods.

Use ``--detrend`` to remove a 1982-2022 linear trend from monthly anomaly
fields before storing the 2026 maps. For CPC OLR daily anomaly fields, the
trend is fit directly to the 1982-2022 daily anomaly series.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
import time

import numpy as np


OISST_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
GPCP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc"
NCEP_U850_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/pressure/uwnd.mon.mean.nc"
NCEP_V850_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/pressure/vwnd.mon.mean.nc"
NCEP_SLP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface/slp.mon.mean.nc"
CPC_OLR_ANOM_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_blended_olr-2.5deg/olr.day.anom.nc"

REFERENCE_START = 1982
REFERENCE_END = 2022
MONTHLY_PERIODS = {
    "JAN": ((2026, 1),),
    "FEB": ((2026, 2),),
    "MAR": ((2026, 3),),
    "APR": ((2026, 4),),
    "MAY": ((2026, 5),),
    "JFM": ((2026, 1), (2026, 2), (2026, 3)),
    "FMA": ((2026, 2), (2026, 3), (2026, 4)),
    "MAM": ((2026, 3), (2026, 4), (2026, 5)),
    "AM_to_date": ((2026, 4), (2026, 5)),
}
NCEP_PERIODS = {
    "JAN": ((2026, 1),),
    "FEB": ((2026, 2),),
    "JF": ((2026, 1), (2026, 2)),
}
OLR_PERIODS = {
    "MAM": (datetime(2026, 3, 1), datetime(2026, 5, 31)),
    "AM_to_date": (datetime(2026, 4, 1), datetime(2026, 5, 31)),
    "AMJ_to_0615": (datetime(2026, 4, 1), datetime(2026, 6, 15)),
}


def _ym_key(year: int, month: int) -> int:
    return int(year) * 100 + int(month)


def _month_label(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%b").upper()


def _decimal_year(year: int, month: int, day: int = 15) -> float:
    return float(year) + (float(month) - 0.5 + (float(day) - 15.0) / 30.4375) / 12.0


def _select_lat_lon(lat, lon, lat_min: float, lat_max: float, lon_min: float, lon_max: float):
    lat_idx = np.where((lat >= lat_min) & (lat <= lat_max))[0]
    lon_idx = np.where((lon >= lon_min) & (lon <= lon_max))[0]
    if len(lat_idx) == 0 or len(lon_idx) == 0:
        raise ValueError("Spatial selection is empty")
    return lat_idx, lon_idx


def _sort_lat(lat: np.ndarray, fields: dict[str, np.ndarray]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    order = np.argsort(lat)
    if np.array_equal(order, np.arange(len(lat))):
        return lat, fields
    sorted_fields = {}
    for key, value in fields.items():
        arr = np.asarray(value)
        if arr.ndim == 1:
            sorted_fields[key] = arr
        elif arr.ndim == 2:
            sorted_fields[key] = arr[order, :]
        elif arr.ndim == 3:
            sorted_fields[key] = arr[:, order, :]
        else:
            sorted_fields[key] = arr
    return lat[order], sorted_fields


def _read_time(ds):
    import netCDF4

    time_var = ds.variables["time"]
    return netCDF4.num2date(
        time_var[:],
        units=time_var.units,
        calendar=getattr(time_var, "calendar", "standard"),
    )


def _slice_with_retry(var, indexer, attempts: int = 4):
    last_error = None
    for attempt in range(attempts):
        try:
            return var[indexer]
        except RuntimeError as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise last_error


def _target_months(periods: dict[str, tuple[tuple[int, int], ...]]) -> set[tuple[int, int]]:
    months: set[tuple[int, int]] = set()
    for members in periods.values():
        months.update(members)
    return months


def _nanmean_stack(arrays: list[np.ndarray]) -> np.ndarray:
    stack = np.stack(arrays)
    valid = np.isfinite(stack)
    sums = np.where(valid, stack, 0.0).sum(axis=0)
    counts = valid.sum(axis=0)
    return np.divide(
        sums,
        counts,
        out=np.full(stack.shape[1:], np.nan, dtype=np.float32),
        where=counts > 0,
    ).astype(np.float32)


def _accumulate_linear_fit(
    arr: np.ndarray,
    x: float,
    count: np.ndarray,
    sum_x: np.ndarray,
    sum_y: np.ndarray,
    sum_xx: np.ndarray,
    sum_xy: np.ndarray,
) -> None:
    valid = np.isfinite(arr)
    count += valid.astype(np.float64)
    sum_x += np.where(valid, x, 0.0)
    sum_y += np.where(valid, arr, 0.0)
    sum_xx += np.where(valid, x * x, 0.0)
    sum_xy += np.where(valid, x * arr, 0.0)


def _finish_linear_fit(
    count: np.ndarray,
    sum_x: np.ndarray,
    sum_y: np.ndarray,
    sum_xx: np.ndarray,
    sum_xy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    denom = count * sum_xx - sum_x * sum_x
    slope = np.divide(
        count * sum_xy - sum_x * sum_y,
        denom,
        out=np.full_like(count, np.nan, dtype=np.float64),
        where=(count > 2) & (np.abs(denom) > 0),
    )
    mean_x = np.divide(sum_x, count, out=np.full_like(count, np.nan, dtype=np.float64), where=count > 2)
    mean_y = np.divide(sum_y, count, out=np.full_like(count, np.nan, dtype=np.float64), where=count > 2)
    intercept = mean_y - slope * mean_x
    return slope.astype(np.float32), intercept.astype(np.float32)


def _read_monthly_anomalies(
    *,
    url: str,
    variable: str,
    periods: dict[str, tuple[tuple[int, int], ...]],
    lat_bounds: tuple[float, float] = (-30, 30),
    lon_bounds: tuple[float, float] = (40, 340),
    level_hpa: float | None = None,
    chunk_months: int = 12,
    detrend: bool = False,
    spatial_stride: int = 1,
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], str]:
    import netCDF4

    ds = netCDF4.Dataset(url)
    try:
        dates = _read_time(ds)
        lat = np.asarray(ds.variables["lat"][:], dtype=float)
        lon = np.asarray(ds.variables["lon"][:], dtype=float)
        lat_idx, lon_idx = _select_lat_lon(lat, lon, *lat_bounds, *lon_bounds)
        if spatial_stride < 1:
            raise ValueError("spatial_stride must be >= 1")
        lat_step = int(spatial_stride)
        lon_step = int(spatial_stride)
        if spatial_stride > 1:
            lat_idx = lat_idx[::lat_step]
            lon_idx = lon_idx[::lon_step]
        lat_sub = lat[lat_idx]
        lon_sub = lon[lon_idx]
        target_months = _target_months(periods)
        first_key = _ym_key(REFERENCE_START, 1)
        last_key = max(_ym_key(year, month) for year, month in target_months)
        start = next(i for i, date in enumerate(dates) if _ym_key(date.year, date.month) >= first_key)
        end_candidates = [i for i, date in enumerate(dates) if _ym_key(date.year, date.month) <= last_key]
        if not end_candidates:
            raise ValueError(f"No available dates in {url} before requested target period")
        end = end_candidates[-1]

        level_index = None
        if level_hpa is not None:
            levels = np.asarray(ds.variables["level"][:], dtype=float)
            level_index = int(np.argmin(np.abs(levels - level_hpa)))
            if abs(float(levels[level_index]) - level_hpa) > 1:
                raise ValueError(f"Could not find requested level {level_hpa} hPa in {url}")

        sample_shape = (len(lat_idx), len(lon_idx))
        clim_sum = {month: np.zeros(sample_shape, dtype=np.float64) for month in range(1, 13)}
        clim_count = {month: np.zeros(sample_shape, dtype=np.float64) for month in range(1, 13)}
        target_raw: dict[tuple[int, int], np.ndarray] = {}

        nc_var = ds.variables[variable]
        for chunk_start in range(start, end + 1, chunk_months):
            chunk_end = min(chunk_start + chunk_months - 1, end)
            if level_index is None:
                indexer = (
                    slice(chunk_start, chunk_end + 1),
                    slice(lat_idx[0], lat_idx[-1] + 1, lat_step),
                    slice(lon_idx[0], lon_idx[-1] + 1, lon_step),
                )
            else:
                indexer = (
                    slice(chunk_start, chunk_end + 1),
                    level_index,
                    slice(lat_idx[0], lat_idx[-1] + 1, lat_step),
                    slice(lon_idx[0], lon_idx[-1] + 1, lon_step),
                )
            cube = _slice_with_retry(nc_var, indexer)
            cube = np.ma.filled(cube, np.nan).astype(np.float32)

            for offset, time_index in enumerate(range(chunk_start, chunk_end + 1)):
                date = dates[time_index]
                arr = cube[offset]
                if REFERENCE_START <= int(date.year) <= REFERENCE_END:
                    valid = np.isfinite(arr)
                    clim_sum[int(date.month)] += np.where(valid, arr, 0.0)
                    clim_count[int(date.month)] += valid.astype(float)
                if (int(date.year), int(date.month)) in target_months:
                    target_raw[(int(date.year), int(date.month))] = arr.astype(np.float32)

        climatology = {
            month: np.divide(
                clim_sum[month],
                clim_count[month],
                out=np.full(sample_shape, np.nan, dtype=np.float64),
                where=clim_count[month] > 0,
            ).astype(np.float32)
            for month in range(1, 13)
        }

        slope = None
        intercept = None
        if detrend:
            count = np.zeros(sample_shape, dtype=np.float64)
            sum_x = np.zeros(sample_shape, dtype=np.float64)
            sum_y = np.zeros(sample_shape, dtype=np.float64)
            sum_xx = np.zeros(sample_shape, dtype=np.float64)
            sum_xy = np.zeros(sample_shape, dtype=np.float64)
            trend_end_candidates = [
                i for i, date in enumerate(dates) if _ym_key(date.year, date.month) <= _ym_key(REFERENCE_END, 12)
            ]
            trend_end = trend_end_candidates[-1]
            for chunk_start in range(start, trend_end + 1, chunk_months):
                chunk_end = min(chunk_start + chunk_months - 1, trend_end)
                if level_index is None:
                    indexer = (
                        slice(chunk_start, chunk_end + 1),
                        slice(lat_idx[0], lat_idx[-1] + 1, lat_step),
                        slice(lon_idx[0], lon_idx[-1] + 1, lon_step),
                    )
                else:
                    indexer = (
                        slice(chunk_start, chunk_end + 1),
                        level_index,
                        slice(lat_idx[0], lat_idx[-1] + 1, lat_step),
                        slice(lon_idx[0], lon_idx[-1] + 1, lon_step),
                    )
                cube = _slice_with_retry(nc_var, indexer)
                cube = np.ma.filled(cube, np.nan).astype(np.float32)
                for offset, time_index in enumerate(range(chunk_start, chunk_end + 1)):
                    date = dates[time_index]
                    if REFERENCE_START <= int(date.year) <= REFERENCE_END:
                        arr = cube[offset] - climatology[int(date.month)]
                        _accumulate_linear_fit(
                            arr,
                            _decimal_year(int(date.year), int(date.month)),
                            count,
                            sum_x,
                            sum_y,
                            sum_xx,
                            sum_xy,
                        )
            slope, intercept = _finish_linear_fit(count, sum_x, sum_y, sum_xx, sum_xy)

        fields: dict[str, np.ndarray] = {}
        for year, month in sorted(target_months):
            if (year, month) in target_raw:
                anomaly = (target_raw[(year, month)] - climatology[month]).astype(np.float32)
                if detrend and slope is not None and intercept is not None:
                    anomaly = (anomaly - (slope * _decimal_year(year, month) + intercept)).astype(np.float32)
                fields[_month_label(year, month)] = anomaly

        for period, members in periods.items():
            labels = [_month_label(year, month) for year, month in members]
            if all(label in fields for label in labels):
                fields[period] = _nanmean_stack([fields[label] for label in labels])

        lat_sorted, fields = _sort_lat(lat_sub, fields)
        units = getattr(nc_var, "units", "")
        return lat_sorted, lon_sub, fields, units
    finally:
        ds.close()


def _read_olr_anomaly_periods(
    *,
    url: str,
    lat_bounds: tuple[float, float] = (-30, 30),
    lon_bounds: tuple[float, float] = (40, 340),
    chunk_days: int = 31,
    detrend: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], str, str]:
    import netCDF4

    ds = netCDF4.Dataset(url)
    try:
        dates = _read_time(ds)
        lat = np.asarray(ds.variables["lat"][:], dtype=float)
        lon = np.asarray(ds.variables["lon"][:], dtype=float)
        lat_idx, lon_idx = _select_lat_lon(lat, lon, *lat_bounds, *lon_bounds)
        lat_sub = lat[lat_idx]
        lon_sub = lon[lon_idx]
        latest = dates[-1]

        slope = None
        intercept = None
        if detrend:
            trend_start = next(
                i for i, date in enumerate(dates) if _ym_key(date.year, date.month) >= _ym_key(REFERENCE_START, 1)
            )
            trend_end = max(
                i for i, date in enumerate(dates) if _ym_key(date.year, date.month) <= _ym_key(REFERENCE_END, 12)
            )
            sample_shape = (len(lat_idx), len(lon_idx))
            count = np.zeros(sample_shape, dtype=np.float64)
            sum_x = np.zeros(sample_shape, dtype=np.float64)
            sum_y = np.zeros(sample_shape, dtype=np.float64)
            sum_xx = np.zeros(sample_shape, dtype=np.float64)
            sum_xy = np.zeros(sample_shape, dtype=np.float64)
            nc_var = ds.variables["olr"]
            for chunk_start in range(trend_start, trend_end + 1, chunk_days):
                chunk_end = min(chunk_start + chunk_days - 1, trend_end)
                cube = _slice_with_retry(
                    nc_var,
                    (
                        slice(chunk_start, chunk_end + 1),
                        slice(lat_idx[0], lat_idx[-1] + 1),
                        slice(lon_idx[0], lon_idx[-1] + 1),
                    ),
                )
                cube = np.ma.filled(cube, np.nan).astype(np.float32)
                for offset, time_index in enumerate(range(chunk_start, chunk_end + 1)):
                    date = dates[time_index]
                    _accumulate_linear_fit(
                        cube[offset],
                        _decimal_year(int(date.year), int(date.month), int(date.day)),
                        count,
                        sum_x,
                        sum_y,
                        sum_xx,
                        sum_xy,
                    )
            slope, intercept = _finish_linear_fit(count, sum_x, sum_y, sum_xx, sum_xy)

        start = next(i for i, date in enumerate(dates) if date >= min(start for start, _ in OLR_PERIODS.values()))
        end = max(i for i, date in enumerate(dates) if date <= max(min(end, latest) for _, end in OLR_PERIODS.values()))

        sample_shape = (len(lat_idx), len(lon_idx))
        sums = {period: np.zeros(sample_shape, dtype=np.float64) for period in OLR_PERIODS}
        counts = {period: np.zeros(sample_shape, dtype=np.float64) for period in OLR_PERIODS}
        nc_var = ds.variables["olr"]
        for chunk_start in range(start, end + 1, chunk_days):
            chunk_end = min(chunk_start + chunk_days - 1, end)
            cube = _slice_with_retry(
                nc_var,
                (
                    slice(chunk_start, chunk_end + 1),
                    slice(lat_idx[0], lat_idx[-1] + 1),
                    slice(lon_idx[0], lon_idx[-1] + 1),
                ),
            )
            cube = np.ma.filled(cube, np.nan).astype(np.float32)
            for offset, time_index in enumerate(range(chunk_start, chunk_end + 1)):
                date = dates[time_index]
                arr = cube[offset]
                if detrend and slope is not None and intercept is not None:
                    arr = (arr - (slope * _decimal_year(int(date.year), int(date.month), int(date.day)) + intercept)).astype(np.float32)
                valid = np.isfinite(arr)
                for period, (period_start, period_end) in OLR_PERIODS.items():
                    adjusted_end = min(period_end, latest)
                    if period_start <= date <= adjusted_end:
                        sums[period] += np.where(valid, arr, 0.0)
                        counts[period] += valid.astype(float)

        fields = {
            period: np.divide(
                sums[period],
                counts[period],
                out=np.full(sample_shape, np.nan, dtype=np.float64),
                where=counts[period] > 0,
            ).astype(np.float32)
            for period in OLR_PERIODS
        }
        fields = {key: value for key, value in fields.items() if np.isfinite(value).any()}
        lat_sorted, fields = _sort_lat(lat_sub, fields)
        units = getattr(nc_var, "units", "")
        return lat_sorted, lon_sub, fields, units, str(latest)[:10]
    finally:
        ds.close()


def _equatorial_hovmoller(fields: dict[str, np.ndarray], lat: np.ndarray, month_labels: Iterable[str]) -> np.ndarray:
    lat_idx = np.where((lat >= -5) & (lat <= 5))[0]
    weights = np.cos(np.deg2rad(lat[lat_idx])).astype(np.float64)
    rows = []
    for label in month_labels:
        arr = fields[label][lat_idx, :]
        valid = np.isfinite(arr)
        weighted = np.where(valid, arr, 0.0) * weights[:, None]
        denom = np.where(valid, weights[:, None], 0.0).sum(axis=0)
        rows.append(np.divide(weighted.sum(axis=0), denom, out=np.full(arr.shape[1], np.nan), where=denom > 0))
    return np.asarray(rows, dtype=np.float32)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract 2026 spatial SST, rainfall, OLR, wind, and SLP anomaly fields.")
    parser.add_argument("--output", type=Path, default=Path("data/interim/research_2026/current_2026_spatial_meteorology.npz"))
    parser.add_argument("--detrend", action="store_true", help="Remove the 1982-2022 linear trend from anomaly fields.")
    parser.add_argument(
        "--oisst-stride",
        type=int,
        default=1,
        help="Read every Nth OISST grid point. Use 4 for an about-1-degree quick product.",
    )
    parser.add_argument("--skip-olr", action="store_true", help="Skip CPC OLR daily anomalies for faster SST/GPCP/NCEP products.")
    args = parser.parse_args()

    print("Reading OISST SST...", flush=True)
    sst_lat, sst_lon, sst_fields, sst_units = _read_monthly_anomalies(
        url=OISST_URL,
        variable="sst",
        periods=MONTHLY_PERIODS,
        chunk_months=12,
        detrend=args.detrend,
        spatial_stride=args.oisst_stride,
    )
    print("Reading GPCP precipitation...", flush=True)
    precip_lat, precip_lon, precip_fields, precip_units = _read_monthly_anomalies(
        url=GPCP_URL,
        variable="precip",
        periods=MONTHLY_PERIODS,
        chunk_months=24,
        detrend=args.detrend,
    )
    print("Reading NCEP 850 hPa u...", flush=True)
    wind_lat, wind_lon, u850_fields, u850_units = _read_monthly_anomalies(
        url=NCEP_U850_URL,
        variable="uwnd",
        periods=NCEP_PERIODS,
        level_hpa=850,
        chunk_months=24,
        detrend=args.detrend,
    )
    print("Reading NCEP 850 hPa v...", flush=True)
    v_lat, v_lon, v850_fields, v850_units = _read_monthly_anomalies(
        url=NCEP_V850_URL,
        variable="vwnd",
        periods=NCEP_PERIODS,
        level_hpa=850,
        chunk_months=24,
        detrend=args.detrend,
    )
    print("Reading NCEP SLP...", flush=True)
    slp_lat, slp_lon, slp_fields, slp_units = _read_monthly_anomalies(
        url=NCEP_SLP_URL,
        variable="slp",
        periods=NCEP_PERIODS,
        chunk_months=24,
        detrend=args.detrend,
    )
    if not (np.array_equal(wind_lat, v_lat) and np.array_equal(wind_lon, v_lon)):
        raise ValueError("NCEP u850 and v850 grids do not match")
    if not (np.array_equal(wind_lat, slp_lat) and np.array_equal(wind_lon, slp_lon)):
        raise ValueError("NCEP wind and SLP grids do not match")

    if args.skip_olr:
        olr_lat = np.asarray([], dtype=np.float32)
        olr_lon = np.asarray([], dtype=np.float32)
        olr_fields: dict[str, np.ndarray] = {}
        olr_units = ""
        olr_latest = ""
    else:
        print("Reading CPC OLR anomaly...", flush=True)
        olr_lat, olr_lon, olr_fields, olr_units, olr_latest = _read_olr_anomaly_periods(
            url=CPC_OLR_ANOM_URL,
            detrend=args.detrend,
        )

    month_labels = ["JAN", "FEB", "MAR", "APR", "MAY"]
    output: dict[str, object] = {
        "sst_lat": sst_lat,
        "sst_lon": sst_lon,
        "precip_lat": precip_lat,
        "precip_lon": precip_lon,
        "ncep_lat": wind_lat,
        "ncep_lon": wind_lon,
        "olr_lat": olr_lat,
        "olr_lon": olr_lon,
        "sst_hov_months": np.asarray(month_labels),
        "precip_hov_months": np.asarray(month_labels),
        "sst_equatorial_hov": _equatorial_hovmoller(sst_fields, sst_lat, month_labels),
        "precip_equatorial_hov": _equatorial_hovmoller(precip_fields, precip_lat, month_labels),
        "sst_units": np.asarray(sst_units),
        "precip_units": np.asarray(precip_units),
        "u850_units": np.asarray(u850_units),
        "v850_units": np.asarray(v850_units),
        "slp_units": np.asarray(slp_units),
        "olr_units": np.asarray(olr_units),
        "olr_latest_date": np.asarray(olr_latest),
        "reference_period": np.asarray(
            f"{REFERENCE_START}-{REFERENCE_END} monthly climatology"
            + (", linear trend removed" if args.detrend else "")
        ),
        "data_sources": np.asarray(
            [
                OISST_URL,
                GPCP_URL,
                NCEP_U850_URL,
                NCEP_V850_URL,
                NCEP_SLP_URL,
                CPC_OLR_ANOM_URL,
            ]
        ),
    }
    for key, value in sst_fields.items():
        output[f"sst_{key}"] = value
    for key, value in precip_fields.items():
        output[f"precip_{key}"] = value
    for key, value in u850_fields.items():
        output[f"u850_{key}"] = value
    for key, value in v850_fields.items():
        output[f"v850_{key}"] = value
    for key, value in slp_fields.items():
        output[f"slp_{key}"] = value
    for key, value in olr_fields.items():
        output[f"olr_{key}"] = value

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
