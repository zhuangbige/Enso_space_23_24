#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import weighted_region_mean  # noqa: E402


OLR_ANOM_OPENDAP = "https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_blended_olr-2.5deg/olr.day.anom.nc"
REGIONS = {
    "western_central_pacific_140e_180": (-5, 5, 140, 180),
    "central_pacific_180_140w": (-5, 5, 180, 220),
    "eastern_pacific_140w_100w": (-5, 5, 220, 260),
    "full_tropical_pacific_120e_80w": (-5, 5, 120, 280),
    "maritime_continent_95e_150e": (-10, 10, 95, 150),
}
SEASONS = {
    "AMJ": (4, 5, 6),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
    "DJF": (12, 13, 14),
}
COMPARABLE_YEARS = (1997, 2015)


def _mean(values: list[float]) -> float:
    valid = [value for value in values if not math.isnan(float(value))]
    if not valid:
        return math.nan
    return sum(valid) / len(valid)


def _seasonal_mean_skip_nan(records: list[dict[str, float | int]], event_year: int, months: tuple[int, ...]) -> float:
    values = []
    lookup = {(int(row["year"]), int(row["month"])): float(row["anomaly"]) for row in records}
    for month in months:
        year = event_year
        actual_month = month
        if month > 12:
            year += 1
            actual_month = month - 12
        value = lookup[(year, actual_month)]
        if not math.isnan(value):
            values.append(value)
    if not values:
        return math.nan
    return sum(values) / len(values)


def _region_indices(lat, lon, bounds):
    import numpy as np

    lat_min, lat_max, lon_min, lon_max = bounds
    lat_idx = np.where((lat >= lat_min) & (lat <= lat_max))[0]
    lon_idx = np.where((lon >= lon_min) & (lon <= lon_max))[0]
    return lat_idx, lon_idx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract CPC Blended OLR monthly anomaly indices from daily OPeNDAP data."
    )
    parser.add_argument("--url", default=OLR_ANOM_OPENDAP)
    parser.add_argument(
        "--monthly-output",
        type=Path,
        default=Path("data/interim/raw_validation/olr_monthly.csv"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/derived/research/olr_seasonal_summary.csv"),
    )
    parser.add_argument("--start-year", type=int, default=1997)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()

    import netCDF4
    import numpy as np

    dataset = netCDF4.Dataset(args.url)
    time_var = dataset.variables["time"]
    dates = netCDF4.num2date(
        time_var[:],
        units=time_var.units,
        calendar=getattr(time_var, "calendar", "standard"),
    )
    lat = dataset.variables["lat"][:]
    lon = dataset.variables["lon"][:]
    start_time = next(i for i, date in enumerate(dates) if date.year == args.start_year and date.month == 1)
    end_time = next(i for i, date in enumerate(dates) if date.year == args.end_year and date.month == 2)
    all_lat_idx = np.where((lat >= -10) & (lat <= 10))[0]
    all_lon_idx = np.where((lon >= 95) & (lon <= 280))[0]
    lat_subset = lat[all_lat_idx]
    lon_subset = lon[all_lon_idx]
    region_indices = {name: _region_indices(lat_subset, lon_subset, bounds) for name, bounds in REGIONS.items()}

    monthly_values: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    current = start_time
    while current <= end_time:
        current_year = dates[current].year
        block_end = current
        while block_end + 1 <= end_time and dates[block_end + 1].year == current_year:
            block_end += 1
        for attempt in range(4):
            try:
                cube = dataset.variables["olr"][
                    current : block_end + 1,
                    all_lat_idx[0] : all_lat_idx[-1] + 1,
                    all_lon_idx[0] : all_lon_idx[-1] + 1,
                ]
                break
            except RuntimeError:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        cube = np.ma.filled(cube, np.nan)
        for offset, time_index in enumerate(range(current, block_end + 1)):
            date = dates[time_index]
            for region, (lat_idx, lon_idx) in region_indices.items():
                values = cube[offset, lat_idx[0] : lat_idx[-1] + 1, lon_idx[0] : lon_idx[-1] + 1]
                monthly_values[(region, int(date.year), int(date.month))].append(
                    weighted_region_mean(values, lat_subset[lat_idx])
                )
        current = block_end + 1
    dataset.close()

    monthly_rows = [
        {
            "region": region,
            "year": year,
            "month": month,
            "olr_anomaly": _mean(values),
            "source_ids": "D8",
        }
        for (region, year, month), values in sorted(monthly_values.items())
    ]
    args.monthly_output.parent.mkdir(parents=True, exist_ok=True)
    with args.monthly_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["region", "year", "month", "olr_anomaly", "source_ids"])
        writer.writeheader()
        writer.writerows(monthly_rows)

    summary_rows = []
    for region in sorted(REGIONS):
        records = [
            {"year": row["year"], "month": row["month"], "anomaly": row["olr_anomaly"]}
            for row in monthly_rows
            if row["region"] == region
        ]
        for season, months in SEASONS.items():
            try:
                value_2023 = _seasonal_mean_skip_nan(records, 2023, months)
                comparable = _mean([_seasonal_mean_skip_nan(records, year, months) for year in COMPARABLE_YEARS])
            except KeyError:
                continue
            summary_rows.append(
                {
                    "region": region,
                    "season": season,
                    "value_2023": value_2023,
                    "value_comparable": comparable,
                    "difference_2023_minus_comparable": value_2023 - comparable,
                    "ratio_to_comparable": value_2023 / comparable if comparable else "",
                    "source_ids": "D8",
                    "note": "OLR anomaly; positive means less convection, negative means enhanced convection.",
                }
            )
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "region",
                "season",
                "value_2023",
                "value_comparable",
                "difference_2023_minus_comparable",
                "ratio_to_comparable",
                "source_ids",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(args.monthly_output)
    print(args.summary_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
