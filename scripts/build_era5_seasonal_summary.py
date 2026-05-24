#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SINGLE = ROOT / "data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc"
PRESSURE = ROOT / "data/raw/era5/era5_monthly_pressure_levels_tropics_1982_2024.nc"
U850 = ROOT / "data/raw/era5/era5_monthly_u850_tropics_1982_2024.nc"
WALKER = ROOT / "data/raw/era5/era5_monthly_walker_tropics_1982_2024.nc"
OUT = ROOT / "data/derived/research/era5_seasonal_summary.csv"
COMPARABLE_YEARS = (1982, 1997, 2015)
SEASONS = {
    "AMJ": (4, 5, 6),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
    "DJF": (12, 13, 14),
}
REGIONS = {
    "cwp_160e_140w": (-5, 5, 160, 220),
    "tahiti_proxy": (-25, -10, 200, 220),
    "darwin_proxy": (-20, -5, 120, 140),
    "central_pacific_180_140w": (-5, 5, 180, 220),
    "eastern_pacific_140w_100w": (-5, 5, 220, 260),
    "maritime_continent_95e_150e": (-10, 10, 95, 150),
}


def _open_dataset(path: Path):
    import xarray as xr

    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return xr.open_dataset(path, engine="h5netcdf")
    except Exception:
        return xr.open_dataset(path)


def _time_coord(ds):
    for name in ("valid_time", "time", "date"):
        if name in ds.coords:
            return name
    raise ValueError("Cannot find ERA5 time coordinate.")


def _level_coord(ds):
    for name in ("pressure_level", "level", "isobaricInhPa"):
        if name in ds.coords:
            return name
    return None


def _var(ds, candidates: tuple[str, ...]):
    for name in candidates:
        if name in ds:
            return ds[name]
    raise ValueError(f"None of these variables were found: {candidates}. Available: {list(ds.data_vars)}")


def _normalize_lon(da):
    lon_name = "longitude" if "longitude" in da.coords else "lon"
    lon = da[lon_name]
    if float(lon.min()) < 0:
        da = da.assign_coords({lon_name: (lon % 360)}).sortby(lon_name)
    return da


def _region_mean(da, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> float:
    da = _normalize_lon(da)
    lat_name = "latitude" if "latitude" in da.coords else "lat"
    lon_name = "longitude" if "longitude" in da.coords else "lon"
    lat = da[lat_name]
    lat_slice = slice(lat_max, lat_min) if float(lat[0]) > float(lat[-1]) else slice(lat_min, lat_max)
    subset = da.sel({lat_name: lat_slice, lon_name: slice(lon_min, lon_max)})
    weights = math.pi / 180
    del weights
    import numpy as np

    coslat = np.cos(np.deg2rad(subset[lat_name]))
    return float(subset.weighted(coslat).mean((lat_name, lon_name), skipna=True).values)


def _monthly_records(da, region_name: str) -> list[dict[str, float | int]]:
    time_name = _time_coord(da.to_dataset(name="tmp"))
    lat_min, lat_max, lon_min, lon_max = REGIONS[region_name]
    output = []
    for index in range(da.sizes[time_name]):
        slice_da = da.isel({time_name: index})
        stamp = da[time_name].values[index]
        year = int(str(stamp)[:4])
        month = int(str(stamp)[5:7])
        output.append({"year": year, "month": month, "value": _region_mean(slice_da, lat_min, lat_max, lon_min, lon_max)})
    return output


def _monthly_anomalies(records: list[dict[str, float | int]], reference_start: int, reference_end: int) -> list[dict[str, float | int]]:
    by_month: dict[int, list[float]] = {}
    for row in records:
        if reference_start <= int(row["year"]) <= reference_end:
            by_month.setdefault(int(row["month"]), []).append(float(row["value"]))
    clim = {month: sum(values) / len(values) for month, values in by_month.items()}
    return [{**row, "anomaly": float(row["value"]) - clim[int(row["month"])]} for row in records]


def _seasonal_mean(records: list[dict[str, float | int]], event_year: int, months: tuple[int, ...]) -> float:
    lookup = {(int(row["year"]), int(row["month"])): float(row["anomaly"]) for row in records}
    values = []
    for month in months:
        year = event_year
        actual_month = month
        if month > 12:
            year += 1
            actual_month = month - 12
        values.append(lookup[(year, actual_month)])
    return sum(values) / len(values)


def _seasonal_rows(metric: str, records: list[dict[str, float | int]], source_ids: str) -> list[dict[str, float | str]]:
    anomalies = records if records and "anomaly" in records[0] else _monthly_anomalies(records, 1982, 2022)
    rows = []
    for season, months in SEASONS.items():
        value_2023 = _seasonal_mean(anomalies, 2023, months)
        comparable_values = [_seasonal_mean(anomalies, year, months) for year in COMPARABLE_YEARS]
        comparable = sum(comparable_values) / len(comparable_values)
        rows.append(
            {
                "metric": metric,
                "season": season,
                "value_2023": value_2023,
                "value_comparable": comparable,
                "difference_2023_minus_comparable": value_2023 - comparable,
                "ratio_to_comparable": value_2023 / comparable if comparable else "",
                "source_ids": source_ids,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ERA5 seasonal wind/SLP/Walker diagnostics.")
    parser.add_argument("--single-levels", type=Path, default=SINGLE)
    parser.add_argument("--pressure-levels", type=Path, default=PRESSURE)
    parser.add_argument("--u850", type=Path, default=U850)
    parser.add_argument("--walker", type=Path, default=WALKER)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    rows = []
    single = _open_dataset(args.single_levels)
    u10 = _var(single, ("u10", "10u", "10m_u_component_of_wind"))
    msl = _var(single, ("msl", "mean_sea_level_pressure")) / 100.0
    rows.extend(_seasonal_rows("era5_u10_cwp_160e_140w", _monthly_records(u10, "cwp_160e_140w"), "D5"))
    tahiti = _monthly_anomalies(_monthly_records(msl, "tahiti_proxy"), 1982, 2022)
    darwin = _monthly_anomalies(_monthly_records(msl, "darwin_proxy"), 1982, 2022)
    soi_records = []
    for left, right in zip(tahiti, darwin):
        soi_records.append(
            {
                "year": left["year"],
                "month": left["month"],
                "anomaly": float(left["anomaly"]) - float(right["anomaly"]),
            }
        )
    rows.extend(_seasonal_rows("era5_soi_like_tahiti_minus_darwin", soi_records, "D5"))
    single.close()

    pressure_path = args.pressure_levels if args.pressure_levels.exists() else args.u850
    if pressure_path.exists():
        pressure = _open_dataset(pressure_path)
        level_name = _level_coord(pressure)
        if level_name is None:
            raise ValueError("ERA5 pressure-level file has no pressure level coordinate.")
        u = _var(pressure, ("u", "u_component_of_wind"))
        rows.extend(_seasonal_rows("era5_u850_cwp_160e_140w", _monthly_records(u.sel({level_name: 850}), "cwp_160e_140w"), "D6"))
        pressure.close()

    walker_path = args.pressure_levels if args.pressure_levels.exists() else args.walker
    if walker_path.exists():
        walker = _open_dataset(walker_path)
        level_name = _level_coord(walker)
        if level_name is None:
            raise ValueError("ERA5 Walker file has no pressure level coordinate.")
        div = _var(walker, ("d", "divergence"))
        omega = _var(walker, ("w", "vertical_velocity"))
        rows.extend(_seasonal_rows("era5_div200_central_pacific_180_140w", _monthly_records(div.sel({level_name: 200}), "central_pacific_180_140w"), "D6"))
        rows.extend(_seasonal_rows("era5_div200_maritime_continent_95e_150e", _monthly_records(div.sel({level_name: 200}), "maritime_continent_95e_150e"), "D6"))
        rows.extend(_seasonal_rows("era5_omega500_central_pacific_180_140w", _monthly_records(omega.sel({level_name: 500}), "central_pacific_180_140w"), "D6"))
        walker.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "metric",
                "season",
                "value_2023",
                "value_comparable",
                "difference_2023_minus_comparable",
                "ratio_to_comparable",
                "source_ids",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
