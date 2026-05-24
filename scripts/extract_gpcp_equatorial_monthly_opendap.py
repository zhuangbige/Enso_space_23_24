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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract monthly equatorial GPCP precipitation anomalies via NOAA PSL OPeNDAP."
    )
    parser.add_argument("--url", default=GPCP_OPENDAP)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/raw_validation/gpcp_equatorial_monthly.csv"),
    )
    parser.add_argument("--start-year", type=int, default=1982)
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
    lon_idx = np.where((lon >= 120) & (lon <= 280))[0]
    start_time = next(
        i for i, date in enumerate(dates) if date.year == args.start_year and date.month == 1
    )
    end_time = next(
        i for i, date in enumerate(dates) if date.year == args.end_year and date.month == 2
    )

    records = []
    for time_index in range(start_time, end_time + 1):
        date = dates[time_index]
        subset = dataset.variables["precip"][
            time_index,
            lat_idx[0] : lat_idx[-1] + 1,
            lon_idx[0] : lon_idx[-1] + 1,
        ]
        values = np.nanmean(np.ma.filled(subset, np.nan), axis=0)
        records.append(
            {
                "year": int(date.year),
                "month": int(date.month),
                "values": [[float(value)] for value in values.tolist()],
            }
        )
    dataset.close()

    anomalies = subtract_monthly_climatology_cube(
        records, args.reference_start, args.reference_end
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "year", "month", "precip", "anomaly"])
        for raw_row, anomaly_row in zip(records, anomalies):
            for region_name, (lon_min, lon_max) in REGIONS.items():
                writer.writerow(
                    [
                        region_name,
                        raw_row["year"],
                        raw_row["month"],
                        average_lon_time(
                            raw_row["values"],
                            lon=lon[lon_idx],
                            lon_min=lon_min,
                            lon_max=lon_max,
                            month_indices=[0],
                        ),
                        average_lon_time(
                            anomaly_row["values"],
                            lon=lon[lon_idx],
                            lon_min=lon_min,
                            lon_max=lon_max,
                            month_indices=[0],
                        ),
                    ]
                )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
