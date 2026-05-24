#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import monthly_anomalies, seasonal_event_mean, weighted_region_mean  # noqa: E402


UWND_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface/uwnd.sig995.mon.mean.nc"
SLP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface/slp.mon.mean.nc"


def _read_region_series(url: str, variable: str, lat_min: float, lat_max: float, lon_min: float, lon_max: float, start_year: int, end_year: int) -> list[dict]:
    import netCDF4
    import numpy as np

    dataset = netCDF4.Dataset(url)
    time_var = dataset.variables["time"]
    dates = netCDF4.num2date(time_var[:], units=time_var.units, calendar=getattr(time_var, "calendar", "standard"))
    lat = dataset.variables["lat"][:]
    lon = dataset.variables["lon"][:]
    lat_idx = np.where((lat >= lat_min) & (lat <= lat_max))[0]
    lon_idx = np.where((lon >= lon_min) & (lon <= lon_max))[0]
    start_time = next(i for i, date in enumerate(dates) if date.year == start_year and date.month == 1)
    end_time = next(i for i, date in enumerate(dates) if date.year == end_year + 1 and date.month == 1)

    records = []
    for time_index in range(start_time, end_time + 1):
        date = dates[time_index]
        for attempt in range(4):
            try:
                subset = dataset.variables[variable][time_index, lat_idx[0] : lat_idx[-1] + 1, lon_idx[0] : lon_idx[-1] + 1]
                break
            except RuntimeError:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        values = np.ma.filled(subset, np.nan)
        records.append({"year": int(date.year), "month": int(date.month), "value": weighted_region_mean(values, lat[lat_idx])})
    dataset.close()
    return records


def _seasonal_series(records: list[dict], start_year: int, end_year: int, reference_start: int, reference_end: int) -> dict[int, float]:
    anomalies = monthly_anomalies(records, reference_start, reference_end)
    return {
        event_year: seasonal_event_mean(anomalies, event_year=event_year, months=(6, 7, 8, 9, 10, 11, 12, 13))
        for event_year in range(start_year, end_year + 1)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract NCEP atmospheric Jun-Jan u-wind and SOI-like SLP indices.")
    parser.add_argument("--output", type=Path, default=Path("data/derived/raw_validation/ncep_atmosphere_jun_jan.csv"))
    parser.add_argument("--monthly-output", type=Path, default=Path("data/interim/raw_validation/ncep_atmosphere_monthly.csv"))
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--reference-start", type=int, default=1982)
    parser.add_argument("--reference-end", type=int, default=2022)
    parser.add_argument("--extra-next-year-months", type=int, default=2)
    args = parser.parse_args()

    # Fig. 1 labels this as central-western Pacific u10. We use NCEP sig995 u-wind
    # over a CWP box as an independently available atmospheric proxy.
    read_end_year = args.end_year if args.extra_next_year_months <= 1 else args.end_year + 1
    cwp_u = _read_region_series(UWND_URL, "uwnd", -5, 5, 160, 220, args.start_year, read_end_year)
    tahiti_slp = _read_region_series(SLP_URL, "slp", -25, -10, 200, 220, args.start_year, read_end_year)
    darwin_slp = _read_region_series(SLP_URL, "slp", -20, -5, 120, 140, args.start_year, read_end_year)
    cwp_u_seasonal = _seasonal_series(cwp_u, args.start_year, args.end_year, args.reference_start, args.reference_end)
    tahiti_seasonal = _seasonal_series(tahiti_slp, args.start_year, args.end_year, args.reference_start, args.reference_end)
    darwin_seasonal = _seasonal_series(darwin_slp, args.start_year, args.end_year, args.reference_start, args.reference_end)
    cwp_u_anom = monthly_anomalies(cwp_u, args.reference_start, args.reference_end)
    tahiti_anom = monthly_anomalies(tahiti_slp, args.reference_start, args.reference_end)
    darwin_anom = monthly_anomalies(darwin_slp, args.reference_start, args.reference_end)

    args.monthly_output.parent.mkdir(parents=True, exist_ok=True)
    with args.monthly_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["year", "month", "cwp_u_sig995", "soi_like_tahiti_minus_darwin"])
        for u_row, tahiti_row, darwin_row in zip(cwp_u_anom, tahiti_anom, darwin_anom):
            writer.writerow(
                [
                    u_row["year"],
                    u_row["month"],
                    u_row["anomaly"],
                    tahiti_row["anomaly"] - darwin_row["anomaly"],
                ]
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["event_year", "cwp_u_sig995", "soi_like_tahiti_minus_darwin"])
        for year in range(args.start_year, args.end_year + 1):
            writer.writerow([year, cwp_u_seasonal[year], tahiti_seasonal[year] - darwin_seasonal[year]])
    print(args.output)
    print(args.monthly_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
