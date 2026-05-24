#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import monthly_anomalies, seasonal_event_mean, weighted_region_mean  # noqa: E402


OISST_OPENDAP = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Nino-3 Jun-Jan SST anomalies from NOAA OISSTv2.1 via OPeNDAP.")
    parser.add_argument("--url", default=OISST_OPENDAP)
    parser.add_argument("--output", type=Path, default=Path("data/derived/raw_validation/oisst_nino3_jun_jan.csv"))
    parser.add_argument("--monthly-output", type=Path, default=Path("data/interim/raw_validation/oisst_nino3_monthly.csv"))
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--reference-start", type=int, default=1982)
    parser.add_argument("--reference-end", type=int, default=2022)
    parser.add_argument("--extra-next-year-months", type=int, default=2, help="Read this many months after end-year December.")
    args = parser.parse_args()

    import netCDF4
    import numpy as np

    dataset = netCDF4.Dataset(args.url)
    time_var = dataset.variables["time"]
    dates = netCDF4.num2date(time_var[:], units=time_var.units, calendar=getattr(time_var, "calendar", "standard"))
    lat = dataset.variables["lat"][:]
    lon = dataset.variables["lon"][:]
    lat_idx = np.where((lat >= -5) & (lat <= 5))[0]
    lon_idx = np.where((lon >= 210) & (lon <= 270))[0]
    start_time = next(i for i, date in enumerate(dates) if date.year == args.start_year and date.month == 1)
    end_time = next(i for i, date in enumerate(dates) if date.year == args.end_year + 1 and date.month == args.extra_next_year_months)

    records = []
    for time_index in range(start_time, end_time + 1):
        date = dates[time_index]
        for attempt in range(4):
            try:
                subset = dataset.variables["sst"][time_index, lat_idx[0] : lat_idx[-1] + 1, lon_idx[0] : lon_idx[-1] + 1]
                break
            except RuntimeError:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        values = np.ma.filled(subset, np.nan)
        records.append(
            {
                "year": int(date.year),
                "month": int(date.month),
                "value": weighted_region_mean(values, lat[lat_idx]),
            }
        )
    dataset.close()

    anomalies = monthly_anomalies(records, reference_start=args.reference_start, reference_end=args.reference_end)
    args.monthly_output.parent.mkdir(parents=True, exist_ok=True)
    with args.monthly_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["year", "month", "value", "anomaly"])
        writer.writeheader()
        writer.writerows(anomalies)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["event_year", "nino3_jun_jan_anomaly"])
        for event_year in range(args.start_year, args.end_year + 1):
            writer.writerow(
                [
                    event_year,
                    seasonal_event_mean(
                        anomalies,
                        event_year=event_year,
                        months=(6, 7, 8, 9, 10, 11, 12, 13),
                    ),
                ]
            )
    print(args.output)
    print(args.monthly_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
