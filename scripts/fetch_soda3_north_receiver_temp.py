#!/usr/bin/env python3
"""Fetch a compact SODA3.15.2 north-of-5N receiver temperature subset.

The subset is intentionally limited to the historical APDRC aggregation and
contains only January--July 1980--2022, 5--12N, 150W--80W and the upper
300 m.  It is used to test whether development-year northward Q20 across 5N
precedes warm-heat accumulation immediately north of the boundary.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/raw/soda3/soda3.15.2_north_receiver_temp_jan_jul_1980_2022.nc"
)
APDRC_URL = (
    "http://apdrc.soest.hawaii.edu:80/dods/public_data/"
    "SODA/soda_3.15.2/monthly_t"
)

START_YEAR = 1980
END_YEAR = 2022
MONTHS = tuple(range(1, 8))
LAT_BOUNDS = (5.0, 12.0)
LON_BOUNDS = (210.0, 280.0)
DEPTH_MAX_M = 300.0


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    index = np.flatnonzero((values >= lower) & (values <= upper))
    if index.size == 0 or not np.all(np.diff(index) == 1):
        raise ValueError(f"Cannot form contiguous slice for {lower}..{upper}")
    return slice(int(index[0]), int(index[-1]) + 1)


def fetch(test_only: bool = False) -> xr.DataArray:
    years = [START_YEAR] if test_only else list(range(START_YEAR, END_YEAR + 1))
    print(f"Opening {APDRC_URL}", flush=True)
    with netCDF4.Dataset(APDRC_URL) as source:
        depth = np.asarray(source.variables["lev"][:], dtype=np.float64)
        lat = np.asarray(source.variables["lat"][:], dtype=np.float64)
        lon = np.asarray(source.variables["lon"][:], dtype=np.float64)
        zslice = contiguous_slice(depth, 0.0, DEPTH_MAX_M)
        yslice = contiguous_slice(lat, *LAT_BOUNDS)
        xslice = contiguous_slice(lon, *LON_BOUNDS)
        print(
            f"subset depth={depth[zslice][0]:.2f}..{depth[zslice][-1]:.2f} "
            f"lat={lat[yslice][0]:.2f}..{lat[yslice][-1]:.2f} "
            f"lon={lon[xslice][0]:.2f}..{lon[xslice][-1]:.2f}",
            flush=True,
        )
        blocks: list[np.ndarray] = []
        times: list[pd.Timestamp] = []
        for year in years:
            start = (year - START_YEAR) * 12
            indices = [start + month - 1 for month in MONTHS]
            block = np.asarray(
                source.variables["temp"][indices, zslice, yslice, xslice],
                dtype=np.float32,
            )
            expected = (
                len(MONTHS),
                depth[zslice].size,
                lat[yslice].size,
                lon[xslice].size,
            )
            if block.shape != expected:
                raise ValueError(f"Unexpected {year} shape {block.shape}; expected {expected}")
            block[block < -1.0e10] = np.nan
            blocks.append(block)
            times.extend(pd.Timestamp(year, month, 15) for month in MONTHS)
            print(f"{year}: {block.nbytes / 2**20:.1f} MiB", flush=True)

    return xr.DataArray(
        np.concatenate(blocks, axis=0),
        dims=("time", "depth", "lat", "lon"),
        coords={
            "time": pd.DatetimeIndex(times),
            "depth": depth[zslice],
            "lat": lat[yslice],
            "lon": lon[xslice],
        },
        name="temp",
        attrs={"long_name": "SODA3 potential temperature", "units": "degC"},
    )


def write_output(field: xr.DataArray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = field.to_dataset()
    dataset.attrs.update(
        title="SODA3.15.2 north-of-5N warm-heat receiver temperature",
        source="SODA3.15.2 APDRC OPeNDAP monthly_t",
        subset=(
            "January-July 1980-2022; 5N-12N, 150W-80W, upper 300 m"
        ),
    )
    dataset.to_netcdf(
        path,
        engine="netcdf4",
        encoding={"temp": {"zlib": True, "complevel": 4, "dtype": "float32"}},
    )
    print(f"Wrote {path} ({path.stat().st_size / 2**20:.1f} MiB)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    destination = OUTPUT.with_name(OUTPUT.stem + "_test.nc") if args.test else OUTPUT
    if destination.exists() and not args.force:
        print(f"Already exists: {destination}")
        return 0
    write_output(fetch(test_only=args.test), destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
