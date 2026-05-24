#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import monthly_anomalies, weighted_region_mean_timeseries  # noqa: E402
from el_nino_decoupling.regions import get_region  # noqa: E402


OISST_OPENDAP = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
DEFAULT_REGIONS = ["tropical_indian_ocean", "maritime_continent", "western_pacific_warm_pool", "tropical_north_atlantic"]


def chunk_ranges(start: int, end: int, size: int) -> list[tuple[int, int]]:
    ranges = []
    current = start
    while current <= end:
        chunk_end = min(current + size - 1, end)
        ranges.append((current, chunk_end))
        current = chunk_end + 1
    return ranges


def read_region_timeseries(dataset, variable: str, lat, lon, region, start_time: int, end_time: int):
    import numpy as np

    lat_idx = np.where((lat >= region.lat_min) & (lat <= region.lat_max))[0]
    lon_idx = np.where((lon >= region.lon_min) & (lon <= region.lon_max))[0]
    for attempt in range(4):
        try:
            subset = dataset.variables[variable][
                start_time : end_time + 1,
                lat_idx[0] : lat_idx[-1] + 1,
                lon_idx[0] : lon_idx[-1] + 1,
            ]
            break
        except RuntimeError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return weighted_region_mean_timeseries(np.ma.filled(subset, np.nan), lat[lat_idx])


def read_region_timeseries_chunked(dataset, variable: str, lat, lon, region, start_time: int, end_time: int, chunk_months: int):
    values = []
    for chunk_start, chunk_end in chunk_ranges(start_time, end_time, chunk_months):
        values.extend(read_region_timeseries(dataset, variable, lat, lon, region, chunk_start, chunk_end))
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract external-basin OISST indices via NOAA PSL OPeNDAP.")
    parser.add_argument("--url", default=OISST_OPENDAP)
    parser.add_argument("--regions", nargs="*", default=DEFAULT_REGIONS)
    parser.add_argument("--output", type=Path, default=Path("data/interim/raw_validation/oisst_external_basin_monthly.csv"))
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--reference-start", type=int, default=1982)
    parser.add_argument("--reference-end", type=int, default=2022)
    parser.add_argument(
        "--chunk-months",
        type=int,
        default=12,
        help="Months per OPeNDAP request. Keep modest because large remote slices can return invalid all-zero arrays.",
    )
    args = parser.parse_args()

    import netCDF4

    dataset = netCDF4.Dataset(args.url)
    time_var = dataset.variables["time"]
    dates = netCDF4.num2date(time_var[:], units=time_var.units, calendar=getattr(time_var, "calendar", "standard"))
    lat = dataset.variables["lat"][:]
    lon = dataset.variables["lon"][:]
    start_time = next(i for i, date in enumerate(dates) if date.year == args.start_year and date.month == 1)
    end_time = next(i for i, date in enumerate(dates) if date.year == args.end_year + 1 and date.month == 2)

    event_dates = dates[start_time : end_time + 1]
    raw_records = {}
    for region_id in args.regions:
        region = get_region(region_id)
        values = read_region_timeseries_chunked(dataset, "sst", lat, lon, region, start_time, end_time, args.chunk_months)
        raw_records[region_id] = [
            {
                "year": int(date.year),
                "month": int(date.month),
                "value": value,
            }
            for date, value in zip(event_dates, values)
        ]
    dataset.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "year", "month", "sst", "anomaly"])
        for region_id, records in raw_records.items():
            anomalies = monthly_anomalies(records, args.reference_start, args.reference_end)
            for row in anomalies:
                writer.writerow([region_id, row["year"], row["month"], row["value"], row["anomaly"]])
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
