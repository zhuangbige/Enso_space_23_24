#!/usr/bin/env python3
"""Fetch the minimal 2024 SODA3.15.2 5N section for fate decomposition.

The historical 1980-2022 section already exists locally.  This script reads
only January-May 2024 from the official University of Maryland annual file,
using HTTP byte ranges, and writes a compact NetCDF with temperature,
salinity, meridional current, SSH, and zonal wind stress over 5N,
140W-80W, 0-300 m.  Tracers/SSH are averaged across the two tracer rows that
straddle 5N, while v/taux are averaged from native longitude faces to tracer
longitude centers, matching fetch_soda3_5n_geostrophic_sections.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import h5py
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_chakravorty_transport_baseline as base  # noqa: E402
from fetch_soda3_equatorial_process_fields import import_fsspec  # noqa: E402


YEAR = 2024
MONTHS = (1, 2, 3, 4, 5)
OFFICIAL_URL = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_2024.nc"
)
REFERENCE = ROOT / "data/interim/research_2026/soda3_5n_geostrophic_sections_1980_2022.nc"
OUTPUT = ROOT / "data/interim/research_2026/soda3_5n_geostrophic_section_2024_jan_may.nc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    indices = np.flatnonzero((values >= lower) & (values <= upper))
    if indices.size == 0 or not np.all(np.diff(indices) == 1):
        raise ValueError(f"Cannot form contiguous slice for {lower}..{upper}")
    return slice(int(indices[0]), int(indices[-1]) + 1)


def exact_index(values: np.ndarray, target: float, tolerance: float = 0.01) -> int:
    index = int(np.argmin(np.abs(values - target)))
    if abs(float(values[index]) - target) > tolerance:
        raise ValueError(f"No coordinate near {target}; nearest={values[index]}")
    return index


def adjacent_indices(values: np.ndarray, boundary: float) -> tuple[int, int]:
    south = np.flatnonzero(values < boundary)
    north = np.flatnonzero(values > boundary)
    if south.size == 0 or north.size == 0:
        raise ValueError(f"Boundary {boundary} outside coordinate range")
    lower, upper = int(south[-1]), int(north[0])
    if not np.isclose(0.5 * (values[lower] + values[upper]), boundary, atol=0.01):
        raise ValueError("Tracer latitude pair does not straddle 5N")
    return lower, upper


def clean(values: np.ndarray) -> np.ndarray:
    output = np.asarray(values, dtype=np.float32)
    output[output <= -1.0e10] = np.nan
    return output


def finite_mean(values: np.ndarray, axis: int) -> np.ndarray:
    valid = np.isfinite(values)
    count = valid.sum(axis=axis)
    total = np.nansum(values, axis=axis)
    return np.divide(
        total,
        count,
        out=np.full(total.shape, np.nan, dtype=float),
        where=count > 0,
    )


def validate(output: xr.Dataset, reference: xr.Dataset) -> None:
    expected_times = pd.DatetimeIndex(
        [pd.Timestamp(YEAR, month, 15) for month in MONTHS]
    )
    if not pd.DatetimeIndex(output.time.values).equals(expected_times):
        raise ValueError("Unexpected extension time axis")
    if output.sizes != {"time": 5, "depth": 20, "lon": 120}:
        raise ValueError(f"Unexpected section geometry: {output.sizes}")
    if not np.allclose(output.depth, reference.depth) or not np.allclose(
        output.lon, reference.lon
    ):
        raise ValueError("2024 section does not match historical coordinates")
    if not (-3.0 < float(output.temp.min()) < float(output.temp.max()) < 40.0):
        raise ValueError("Temperature outside physical QA range")
    if not (20.0 < float(output.salt.min()) < float(output.salt.max()) < 45.0):
        raise ValueError("Salinity outside physical QA range")
    if float(abs(output.v).max()) >= 5.0 or float(abs(output.taux).max()) >= 5.0:
        raise ValueError("Velocity or wind stress outside physical QA range")
    if float(abs(output.ssh).max()) >= 5.0:
        raise ValueError("SSH outside physical QA range")
    if any(bool(output[name].isnull().all()) for name in output.data_vars):
        raise ValueError("A required 2024 variable is entirely missing")


def fetch() -> xr.Dataset:
    with xr.open_dataset(REFERENCE, engine="netcdf4") as reference_source:
        reference = reference_source.load()
    fsspec = import_fsspec()
    remote = fsspec.open(
        OFFICIAL_URL,
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            required = (
                "st_ocean",
                "yt_ocean",
                "xt_ocean",
                "yu_ocean",
                "xu_ocean",
                "temp",
                "salt",
                "ssh",
                "v",
                "taux",
            )
            missing = [name for name in required if name not in dataset]
            if missing:
                raise KeyError(f"Missing variables in official SODA3 file: {missing}")

            depth_all = np.asarray(dataset["st_ocean"][:], dtype=float)
            t_lat_all = np.asarray(dataset["yt_ocean"][:], dtype=float)
            t_lon_all = np.asarray(dataset["xt_ocean"][:], dtype=float) % 360.0
            u_lat_all = np.asarray(dataset["yu_ocean"][:], dtype=float)
            u_lon_all = np.asarray(dataset["xu_ocean"][:], dtype=float) % 360.0

            zslice = contiguous_slice(depth_all, 0.0, base.DEPTH_MAX_M)
            depth = depth_all[zslice]
            south, north = adjacent_indices(t_lat_all, 5.0)
            txslice = contiguous_slice(t_lon_all, 220.0, 280.0)
            tracer_lon = t_lon_all[txslice]
            v_yindex = exact_index(u_lat_all, 5.0)
            v_xslice = contiguous_slice(u_lon_all, 220.0, 280.0)

            time_slice = slice(0, len(MONTHS))
            temp_pair = clean(
                dataset["temp"][time_slice, zslice, slice(south, north + 1), txslice]
            )
            salt_pair = clean(
                dataset["salt"][time_slice, zslice, slice(south, north + 1), txslice]
            )
            ssh_pair = clean(
                dataset["ssh"][time_slice, slice(south, north + 1), txslice]
            )
            raw_v = clean(
                dataset["v"][
                    time_slice,
                    zslice,
                    slice(v_yindex, v_yindex + 1),
                    v_xslice,
                ]
            )[:, :, 0, :]
            raw_taux = clean(
                dataset["taux"][
                    time_slice,
                    slice(v_yindex, v_yindex + 1),
                    v_xslice,
                ]
            )[:, 0, :]
    finally:
        remote.close()

    temp = finite_mean(temp_pair, axis=2)
    salt = finite_mean(salt_pair, axis=2)
    ssh = finite_mean(ssh_pair, axis=1)
    v = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
    taux = 0.5 * (raw_taux[:, :-1] + raw_taux[:, 1:])
    times = pd.DatetimeIndex(
        [pd.Timestamp(YEAR, month, 15) for month in MONTHS]
    )
    output = xr.Dataset(
        {
            "temp": (("time", "depth", "lon"), temp.astype(np.float32)),
            "salt": (("time", "depth", "lon"), salt.astype(np.float32)),
            "v": (("time", "depth", "lon"), v.astype(np.float32)),
            "ssh": (("time", "lon"), ssh.astype(np.float32)),
            "taux": (("time", "lon"), taux.astype(np.float32)),
        },
        coords={"time": times, "depth": depth, "lon": tracer_lon},
        attrs={
            "source": "University of Maryland SODA3.15.2 official 2024 annual file",
            "section": "5N, 140W-80W, 0-300 m",
            "months": "January-May 2024",
            "staggering": "tracers averaged across 5N; v/taux averaged to tracer longitude centers",
        },
    )
    units = {
        "temp": "degC",
        "salt": "psu",
        "v": "m s-1",
        "ssh": "m",
        "taux": "N m-2",
    }
    for name, unit in units.items():
        output[name].attrs["units"] = unit
    validate(output, reference)
    return output


def main() -> int:
    args = parse_args()
    if OUTPUT.exists() and not args.force:
        print(f"Already exists: {OUTPUT}")
        return 0
    output = fetch()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_netcdf(OUTPUT, engine="netcdf4")
    print(output)
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
