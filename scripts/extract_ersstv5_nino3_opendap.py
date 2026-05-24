#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import monthly_anomalies, seasonal_mean_by_months, weighted_region_mean  # noqa: E402


ERSSTV5_OPENDAP = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc"
SEASONS = {
    "AMJ": (4, 5, 6),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
    "DJF": (12, 13, 14),
}
COMPARABLE_YEARS = (1982, 1997, 2015)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract ERSSTv5 monthly Nino-3 anomalies for long-record robustness."
    )
    parser.add_argument("--url", default=ERSSTV5_OPENDAP)
    parser.add_argument(
        "--monthly-output",
        type=Path,
        default=Path("data/interim/raw_validation/ersstv5_nino3_monthly.csv"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/derived/research/ersstv5_nino3_seasonal_summary.csv"),
    )
    parser.add_argument("--start-year", type=int, default=1950)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--reference-start", type=int, default=1982)
    parser.add_argument("--reference-end", type=int, default=2022)
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
    lat_idx = np.where((lat >= -5) & (lat <= 5))[0]
    lon_idx = np.where((lon >= 210) & (lon <= 270))[0]
    start_time = next(i for i, date in enumerate(dates) if date.year == args.start_year and date.month == 1)
    end_time = next(i for i, date in enumerate(dates) if date.year == args.end_year and date.month == 12)

    for attempt in range(4):
        try:
            subset = dataset.variables["sst"][
                start_time : end_time + 1,
                lat_idx[0] : lat_idx[-1] + 1,
                lon_idx[0] : lon_idx[-1] + 1,
            ]
            break
        except RuntimeError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    cube = np.ma.filled(subset, np.nan)
    records = []
    for offset, time_index in enumerate(range(start_time, end_time + 1)):
        date = dates[time_index]
        values = cube[offset]
        records.append(
            {
                "year": int(date.year),
                "month": int(date.month),
                "value": weighted_region_mean(values, lat[lat_idx]),
            }
        )
    dataset.close()

    anomalies = monthly_anomalies(records, args.reference_start, args.reference_end)
    args.monthly_output.parent.mkdir(parents=True, exist_ok=True)
    with args.monthly_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["year", "month", "value", "anomaly"])
        writer.writeheader()
        writer.writerows(anomalies)

    rows = []
    for season, months in SEASONS.items():
        value_2023 = seasonal_mean_by_months(anomalies, 2023, months)
        comparable = _mean([seasonal_mean_by_months(anomalies, year, months) for year in COMPARABLE_YEARS])
        rows.append(
            {
                "season": season,
                "value_2023": value_2023,
                "value_comparable": comparable,
                "difference_2023_minus_comparable": value_2023 - comparable,
                "ratio_to_comparable": value_2023 / comparable if comparable else "",
                "source_ids": "D9",
            }
        )
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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

    print(args.monthly_output)
    print(args.summary_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
