#!/usr/bin/env python3
"""Stream compact SODA3 5N sections for geostrophic/Ekman decomposition.

Only Dec-May, 0-300 m, 5N, and 140W-80W are retained.  Tracer fields are
averaged from the two cells straddling 5N; v and taux are averaged from their
native longitude faces to tracer-cell centers.  Calendar-month checkpoints
make the APDRC extraction resumable.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

import netCDF4
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_chakravorty_transport_baseline as base  # noqa: E402


MONTHS = (1, 2, 3, 4, 5, 12)
OUTPUT = ROOT / "data/interim/research_2026/soda3_5n_geostrophic_sections_1980_2022.nc"
TEST_OUTPUT = ROOT / "data/interim/research_2026/soda3_5n_geostrophic_sections_1980_test.nc"
CHECKPOINT = ROOT / "data/interim/research_2026/soda3_5n_geostrophic_sections"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Extract 1980 only.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--chunk-years", type=int, default=5)
    return parser.parse_args()


def fetch_month(
    tracer: netCDF4.Dataset,
    velocity: netCDF4.Dataset,
    month: int,
    start_year: int,
    end_year: int,
    chunk_years: int,
    chunk_checkpoint_dir: Path,
    force: bool,
) -> xr.Dataset:
    depth_all = np.asarray(tracer.variables["lev"][:], dtype=float)
    t_lat = np.asarray(tracer.variables["lat"][:], dtype=float)
    t_lon = np.asarray(tracer.variables["lon"][:], dtype=float) % 360.0
    u_lat = np.asarray(velocity.variables["lat"][:], dtype=float)
    u_lon = np.asarray(velocity.variables["lon"][:], dtype=float) % 360.0
    zslice = base.contiguous_slice(depth_all, 0.0, base.DEPTH_MAX_M)
    depth = depth_all[zslice]
    south, north = base.adjacent_indices(t_lat, 5.0)
    txslice = base.contiguous_slice(t_lon, 220.0, 280.0)
    tracer_lon = t_lon[txslice]
    v_yindex = base.exact_index(u_lat, 5.0)
    v_xslice = base.contiguous_slice(u_lon, 220.0, 280.0)

    chunks = []
    for first, last in base.year_chunks(start_year, end_year, chunk_years):
        chunk_checkpoint = (
            chunk_checkpoint_dir / f"month_{month:02d}_{first}_{last}.nc"
        )
        if chunk_checkpoint.exists() and not force:
            current = xr.open_dataset(chunk_checkpoint, engine="netcdf4").load()
            chunks.append(current)
            print(f"Month {month:02d}: using checkpoint {first}-{last}", flush=True)
            continue
        tslice = base.time_slice(first, last, month)
        expected = last - first + 1
        for attempt in range(1, 5):
            try:
                temp_pair = base.clean(
                    tracer.variables["temp"][
                        tslice, zslice, slice(south, north + 1), txslice
                    ]
                )
                salt_pair = base.clean(
                    tracer.variables["salt"][
                        tslice, zslice, slice(south, north + 1), txslice
                    ]
                )
                ssh_pair = base.clean(
                    tracer.variables["ssh"][
                        tslice, slice(south, north + 1), txslice
                    ]
                )
                raw_v = base.clean(
                    velocity.variables["v"][
                        tslice, zslice, slice(v_yindex, v_yindex + 1), v_xslice
                    ]
                )[:, :, 0, :]
                raw_taux = base.clean(
                    velocity.variables["taux"][
                        tslice, slice(v_yindex, v_yindex + 1), v_xslice
                    ]
                )[:, 0, :]
                break
            except (OSError, RuntimeError):
                if attempt == 4:
                    raise
                print(
                    f"Month {month:02d}: retry {first}-{last} "
                    f"after remote I/O failure ({attempt}/4)",
                    flush=True,
                )
                time.sleep(2.0 * attempt)
        if temp_pair.shape[0] != expected or raw_v.shape[0] != expected:
            raise ValueError(f"Month {month:02d} chunk {first}-{last} incomplete")
        temp = base.finite_mean(temp_pair, axis=2)
        salt = base.finite_mean(salt_pair, axis=2)
        ssh = base.finite_mean(ssh_pair, axis=1)
        v = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
        taux = 0.5 * (raw_taux[:, :-1] + raw_taux[:, 1:])
        if temp.shape != v.shape or temp.shape[2] != tracer_lon.size:
            raise ValueError("Tracer/velocity staggering conversion failed")
        times = pd.DatetimeIndex(
            [pd.Timestamp(year=year, month=month, day=15) for year in range(first, last + 1)]
        )
        current = xr.Dataset(
            {
                "temp": (("time", "depth", "lon"), temp.astype(np.float32)),
                "salt": (("time", "depth", "lon"), salt.astype(np.float32)),
                "v": (("time", "depth", "lon"), v.astype(np.float32)),
                "ssh": (("time", "lon"), ssh.astype(np.float32)),
                "taux": (("time", "lon"), taux.astype(np.float32)),
            },
            coords={"time": times, "depth": depth, "lon": tracer_lon},
        )
        chunk_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        current.to_netcdf(chunk_checkpoint, engine="netcdf4")
        chunks.append(current)
        print(f"Month {month:02d}: fetched {first}-{last}", flush=True)
    return xr.concat(chunks, dim="time").sortby("time")


def validate(dataset: xr.Dataset, start_year: int, end_year: int) -> None:
    expected = (end_year - start_year + 1) * len(MONTHS)
    if dataset.sizes.get("time") != expected:
        raise ValueError(f"Expected {expected} times, found {dataset.sizes.get('time')}")
    times = pd.DatetimeIndex(dataset.time.values)
    if not times.is_unique or not times.is_monotonic_increasing:
        raise ValueError("Time axis is not unique and increasing")
    if set(times.month) != set(MONTHS):
        raise ValueError("Unexpected calendar-month coverage")
    if dataset.sizes.get("depth") != 20 or dataset.sizes.get("lon") != 120:
        raise ValueError(f"Unexpected section geometry: {dataset.sizes}")
    if not (dataset.temp.min() > -3 and dataset.temp.max() < 40):
        raise ValueError("Temperature outside broad physical bounds")
    if not (dataset.salt.min() > 20 and dataset.salt.max() < 45):
        raise ValueError("Salinity outside broad physical bounds")
    if not (abs(dataset.v).max() < 5 and abs(dataset.taux).max() < 5):
        raise ValueError("Velocity/stress outside broad physical bounds")


def main() -> int:
    args = parse_args()
    start_year = 1980
    end_year = 1980 if args.test else 2022
    output = TEST_OUTPUT if args.test else OUTPUT
    checkpoint_dir = CHECKPOINT / ("test_1980" if args.test else "full_1980_2022")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.force:
        print(f"Already exists: {output}")
        return 0
    tracer = netCDF4.Dataset(base.TRACER_URL)
    velocity = netCDF4.Dataset(base.VELOCITY_URL)
    try:
        pieces = []
        for month in MONTHS:
            checkpoint = checkpoint_dir / f"month_{month:02d}.nc"
            if checkpoint.exists() and not args.force:
                current = xr.open_dataset(checkpoint, engine="netcdf4").load()
                print(f"Month {month:02d}: using checkpoint", flush=True)
            else:
                current = fetch_month(
                    tracer,
                    velocity,
                    month,
                    start_year,
                    end_year,
                    args.chunk_years,
                    checkpoint_dir / "chunks",
                    args.force,
                )
                current.to_netcdf(checkpoint, engine="netcdf4")
            pieces.append(current)
    finally:
        tracer.close()
        velocity.close()
    result = xr.concat(pieces, dim="time").sortby("time")
    result.attrs.update(
        {
            "source": "SODA3.15.2 APDRC monthly_t and monthly_u",
            "section": "5N, 140W-80W, 0-300 m",
            "staggering": "tracers averaged across 5N; v/taux averaged to tracer longitude centers",
        }
    )
    units = {"temp": "degC", "salt": "psu", "v": "m s-1", "ssh": "m", "taux": "N m-2"}
    for name, unit in units.items():
        result[name].attrs["units"] = unit
    validate(result, start_year, end_year)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_netcdf(output, engine="netcdf4")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
