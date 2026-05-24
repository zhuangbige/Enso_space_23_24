#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.analysis import average_lon_time  # noqa: E402
from el_nino_decoupling.raw_indices import subtract_monthly_climatology_cube  # noqa: E402


GPCP_OPENDAP = "https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc"

REGIONS = {
    "western_central_pacific_140e_180": (140, 180),
    "central_pacific_180_140w": (180, 220),
    "eastern_pacific_140w_100w": (220, 260),
    "full_tropical_pacific_120e_80w": (120, 280),
}

WINDOWS = {
    "feb_may": [0, 1, 2, 3],
    "jun_dec": [4, 5, 6, 7, 8, 9, 10],
    "jan_apr_next": [11, 12, 13, 14],
}


def _event_month_records(anomalies: list[dict], event_year: int) -> list[dict]:
    selected = []
    for month in range(2, 13):
        selected.append(next(row for row in anomalies if row["year"] == event_year and row["month"] == month))
    for month in range(1, 5):
        selected.append(next(row for row in anomalies if row["year"] == event_year + 1 and row["month"] == month))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract equatorial GPCP precipitation anomalies via NOAA PSL OPeNDAP.")
    parser.add_argument("--url", default=GPCP_OPENDAP)
    parser.add_argument("--output", type=Path, default=Path("data/derived/raw_validation/gpcp_equatorial_summary.csv"))
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--reference-start", type=int, default=1982)
    parser.add_argument("--reference-end", type=int, default=2022)
    parser.add_argument("--target-year", type=int, default=2023)
    parser.add_argument("--comparable-years", type=int, nargs="*", default=[1982, 1997, 2015])
    args = parser.parse_args()

    import netCDF4
    import numpy as np

    dataset = netCDF4.Dataset(args.url)
    time_var = dataset.variables["time"]
    dates = netCDF4.num2date(time_var[:], units=time_var.units, calendar=getattr(time_var, "calendar", "standard"))
    lat = dataset.variables["lat"][:]
    lon = dataset.variables["lon"][:]
    lat_idx = np.where((lat >= -5) & (lat <= 5))[0]
    lon_idx = np.where((lon >= 120) & (lon <= 280))[0]
    start_time = next(i for i, date in enumerate(dates) if date.year == args.start_year and date.month == 1)
    end_time = next(i for i, date in enumerate(dates) if date.year == args.end_year + 1 and date.month == 4)

    records = []
    for time_index in range(start_time, end_time + 1):
        date = dates[time_index]
        subset = dataset.variables["precip"][time_index, lat_idx[0] : lat_idx[-1] + 1, lon_idx[0] : lon_idx[-1] + 1]
        # GPCP lat is north-to-south; average across the equatorial latitude band
        # before producing a longitude-time summary comparable to Fig. 2.
        values = np.nanmean(np.ma.filled(subset, np.nan), axis=0)
        records.append({"year": int(date.year), "month": int(date.month), "values": [values.tolist()]})
    dataset.close()

    anomalies = subtract_monthly_climatology_cube(records, args.reference_start, args.reference_end)
    event_cases = {
        str(args.target_year): [args.target_year],
        "comparable": args.comparable_years,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case", "region", "window", "precip_anomaly"])
        for case, years in event_cases.items():
            event_arrays = []
            for year in years:
                event_arrays.append([row["values"][0] for row in _event_month_records(anomalies, year)])
            case_values = np.nanmean(np.array(event_arrays), axis=0).T
            for region_name, (lon_min, lon_max) in REGIONS.items():
                for window_name, month_indices in WINDOWS.items():
                    writer.writerow(
                        [
                            case,
                            region_name,
                            window_name,
                            average_lon_time(
                                case_values,
                                lon=lon[lon_idx],
                                lon_min=lon_min,
                                lon_max=lon_max,
                                month_indices=month_indices,
                            ),
                        ]
                    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
