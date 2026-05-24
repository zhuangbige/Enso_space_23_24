#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import subtract_monthly_climatology_cube  # noqa: E402
from el_nino_decoupling.spatial import difference_grid, mean_grid, seasonal_grid_mean  # noqa: E402


UWND_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface/uwnd.sig995.mon.mean.nc"
SLP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface/slp.mon.mean.nc"
SEASONS = {"AMJ": (4, 5, 6), "JJA": (6, 7, 8)}
COMPARABLE_YEARS = (1982, 1997, 2015)


def read_anomaly_records(url: str, variable: str, args):
    import netCDF4
    import numpy as np

    dataset = netCDF4.Dataset(url)
    time_var = dataset.variables["time"]
    dates = netCDF4.num2date(
        time_var[:],
        units=time_var.units,
        calendar=getattr(time_var, "calendar", "standard"),
    )
    lat = dataset.variables["lat"][:]
    lon = dataset.variables["lon"][:]
    lat_idx = np.where((lat >= -30) & (lat <= 30))[0]
    lon_idx = np.where((lon >= 120) & (lon <= 280))[0]
    start_time = next(
        i for i, date in enumerate(dates) if date.year == args.start_year and date.month == 1
    )
    end_time = next(
        i for i, date in enumerate(dates) if date.year == args.end_year and date.month == 2
    )

    records = []
    for chunk_start in range(start_time, end_time + 1, args.chunk_months):
        chunk_end = min(chunk_start + args.chunk_months - 1, end_time)
        subset = dataset.variables[variable][
            chunk_start : chunk_end + 1,
            lat_idx[0] : lat_idx[-1] + 1,
            lon_idx[0] : lon_idx[-1] + 1,
        ]
        values = np.ma.filled(subset, np.nan)
        for offset, time_index in enumerate(range(chunk_start, chunk_end + 1)):
            date = dates[time_index]
            records.append(
                {
                    "year": int(date.year),
                    "month": int(date.month),
                    "values": values[offset].tolist(),
                }
            )
    dataset.close()
    anomalies = subtract_monthly_climatology_cube(
        records, args.reference_start, args.reference_end
    )
    return lat[lat_idx], lon[lon_idx], anomalies


def add_composites(output, prefix: str, records) -> None:
    import numpy as np

    for season, months in SEASONS.items():
        target = seasonal_grid_mean(records, 2023, months)
        comparable = mean_grid(
            [seasonal_grid_mean(records, year, months) for year in COMPARABLE_YEARS]
        )
        output[f"{prefix}_{season}_2023"] = np.array(target)
        output[f"{prefix}_{season}_comparable"] = np.array(comparable)
        output[f"{prefix}_{season}_difference"] = np.array(
            difference_grid(target, comparable)
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract Stage A AMJ/JJA NCEP fallback wind and SLP spatial composites."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/raw_validation/ncep_spatial_amj_jja.npz"),
    )
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--reference-start", type=int, default=1982)
    parser.add_argument("--reference-end", type=int, default=2022)
    parser.add_argument("--chunk-months", type=int, default=24)
    args = parser.parse_args()

    import numpy as np

    lat, lon, uwnd_records = read_anomaly_records(UWND_URL, "uwnd", args)
    slp_lat, slp_lon, slp_records = read_anomaly_records(SLP_URL, "slp", args)
    output = {"lat": lat, "lon": lon}
    if not (np.array_equal(lat, slp_lat) and np.array_equal(lon, slp_lon)):
        raise ValueError("NCEP uwnd and slp grids do not match")
    add_composites(output, "uwnd", uwnd_records)
    add_composites(output, "slp", slp_records)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
