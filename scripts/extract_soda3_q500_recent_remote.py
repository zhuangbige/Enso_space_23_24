#!/usr/bin/env python3
"""Extract 2023-2024 eastern-Pacific H20 and fixed-depth OHC by HTTP ranges.

The official SODA3 annual files are about 2.9 GB each.  This script opens the
remote HDF5/NetCDF4 files through fsspec and requests only the chunked
temperature planes needed for 5S-5N, 140W-80W and the upper 500 m.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fsspec
import h5py
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_east_h20_q300_q500_recent_2023_2024.csv"
)
URL_TEMPLATE = (
    "https://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)

RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
LAT_RANGE = (-5.0, 5.0)
LON_RANGE = (220.0, 280.0)


def depth_overlap(depth: np.ndarray, maximum: float) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    bounds = np.empty(depth.size + 1, dtype=float)
    bounds[0] = 0.0
    bounds[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    bounds[-1] = depth[-1] + 0.5 * (depth[-1] - depth[-2])
    return np.maximum(
        0.0,
        np.minimum(bounds[1:], maximum) - np.maximum(bounds[:-1], 0.0),
    )


def grid_cell_areas(latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    latitude = np.asarray(latitude, dtype=float)
    longitude = np.asarray(longitude, dtype=float)
    dlat = float(np.median(np.diff(latitude)))
    dlon = float(np.median(np.diff(longitude)))
    south = np.deg2rad(latitude - dlat / 2.0)
    north = np.deg2rad(latitude + dlat / 2.0)
    strip = EARTH_RADIUS**2 * (np.sin(north) - np.sin(south))
    return strip[:, None] * np.deg2rad(dlon) * np.ones((1, longitude.size))


def compute_metrics(
    temperature: np.ndarray,
    depth: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> tuple[float, float, float, float, float, float]:
    temperature = np.asarray(temperature, dtype=float)
    temperature[(temperature < -10.0) | (temperature > 50.0)] = np.nan
    area = grid_cell_areas(latitude, longitude)
    dz300 = depth_overlap(depth, 300.0)[:, None, None]
    dz500 = depth_overlap(depth, 500.0)[:, None, None]
    warm = np.maximum(temperature - 20.0, 0.0)
    factor = RHO0 * CP0
    h20_zj = factor * np.nansum(warm * dz300 * area[None, :, :]) / 1.0e21
    q300_zj = factor * np.nansum(temperature * dz300 * area[None, :, :]) / 1.0e21
    q500_zj = factor * np.nansum(temperature * dz500 * area[None, :, :]) / 1.0e21
    domain_area = float(np.sum(area))
    h20_jm2 = h20_zj * 1.0e21 / domain_area
    q300_jm2 = q300_zj * 1.0e21 / domain_area
    q500_jm2 = q500_zj * 1.0e21 / domain_area
    return h20_zj, q300_zj, q500_zj, h20_jm2, q300_jm2, q500_jm2


def extract_year(year: int) -> pd.DataFrame:
    url = URL_TEMPLATE.format(year=year)
    print(f"Opening remote SODA3 file by HTTP ranges: {year}", flush=True)
    with fsspec.open(
        url,
        mode="rb",
        block_size=16 * 2**20,
        cache_type="readahead",
    ).open() as remote:
        with h5py.File(remote, mode="r") as source:
            depth_all = np.asarray(source["st_ocean"][:], dtype=float)
            lat_all = np.asarray(source["yt_ocean"][:], dtype=float)
            lon_all = np.asarray(source["xt_ocean"][:], dtype=float) % 360.0
            # Include the first centre below 500 m as well: its upper part can
            # overlap 0-500 m, and it is needed to locate the exact interface
            # bracketing 500 m.
            first_below = int(np.searchsorted(depth_all, 500.0, side="right"))
            zidx = np.arange(0, min(first_below + 1, depth_all.size))
            yidx = np.flatnonzero(
                (lat_all > LAT_RANGE[0]) & (lat_all < LAT_RANGE[1])
            )
            xidx = np.flatnonzero(
                (lon_all > LON_RANGE[0]) & (lon_all < LON_RANGE[1])
            )
            if not (
                np.all(np.diff(zidx) == 1)
                and np.all(np.diff(yidx) == 1)
                and np.all(np.diff(xidx) == 1)
            ):
                raise ValueError("Requested SODA3 subset is not contiguous")
            zslice = slice(int(zidx[0]), int(zidx[-1]) + 1)
            yslice = slice(int(yidx[0]), int(yidx[-1]) + 1)
            xslice = slice(int(xidx[0]), int(xidx[-1]) + 1)
            depth = depth_all[zslice]
            latitude = lat_all[yslice]
            longitude = lon_all[xslice]
            print(
                f"  grid: {depth.size} levels to {depth[-1]:.1f} m, "
                f"{latitude.size} latitudes, {longitude.size} longitudes",
                flush=True,
            )
            rows: list[dict[str, float | int | str]] = []
            for month_index in range(12):
                # HDF5 chunks span the global horizontal plane, but selecting
                # one month/depth at a time still avoids downloading other
                # variables and all unused months/depths.
                temperature = np.asarray(
                    source["temp"][month_index, zslice, yslice, xslice],
                    dtype=float,
                )
                values = compute_metrics(
                    temperature, depth, latitude, longitude
                )
                rows.append(
                    {
                        "time": str(pd.Timestamp(year, month_index + 1, 15).date()),
                        "year": year,
                        "month": month_index + 1,
                        "east_h20_0_300_raw_zj": values[0],
                        "east_q300_raw_zj": values[1],
                        "east_q500_raw_zj": values[2],
                        "east_h20_0_300_raw_jm2": values[3],
                        "east_q300_raw_jm2": values[4],
                        "east_q500_raw_jm2": values[5],
                    }
                )
                print(f"  {year}-{month_index + 1:02d}: extracted", flush=True)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    pieces = [extract_year(year) for year in args.years]
    output = pd.concat(pieces, ignore_index=True).sort_values("time")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, float_format="%.10g")
    print(f"Wrote {args.output} ({len(output)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
