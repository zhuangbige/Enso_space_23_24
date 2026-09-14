#!/usr/bin/env python3
"""Fetch a compact SODA3.15.2 equatorial upper-ocean temperature subset.

The APDRC OPeNDAP aggregation supplies 1980-2022.  The two most recent
baseline years are extracted from the official University of Maryland annual
files, which are downloaded one at a time to a temporary directory and removed
after the small subset is written.

Output:
  data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import requests
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/soda3"
OUTPUT = RAW_DIR / "soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"

APDRC_URL = "http://apdrc.soest.hawaii.edu:80/dods/public_data/SODA/soda_3.15.2/monthly_t"
UMD_TEMPLATE = (
    "https://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)

LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (120.0, 280.0)
DEPTH_MAX_M = 300.0
MONTHS = tuple(range(1, 7))


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    idx = np.flatnonzero((values >= lower) & (values <= upper))
    if idx.size == 0 or not np.all(np.diff(idx) == 1):
        raise ValueError(f"Cannot form contiguous slice for {lower}..{upper}")
    return slice(int(idx[0]), int(idx[-1]) + 1)


def fetch_apdrc(*, test_only: bool) -> xr.DataArray:
    print(f"Opening APDRC OPeNDAP: {APDRC_URL}", flush=True)
    with netCDF4.Dataset(APDRC_URL) as source:
        depth = np.asarray(source.variables["lev"][:], dtype=np.float64)
        lat = np.asarray(source.variables["lat"][:], dtype=np.float64)
        lon = np.asarray(source.variables["lon"][:], dtype=np.float64)
        zslice = contiguous_slice(depth, 0.0, DEPTH_MAX_M)
        yslice = contiguous_slice(lat, *LAT_BOUNDS)
        xslice = contiguous_slice(lon, *LON_BOUNDS)

        print(
            "APDRC grid subset:",
            f"depth={depth[zslice][0]:.3f}..{depth[zslice][-1]:.3f} m ({depth[zslice].size}),",
            f"lat={lat[yslice][0]:.2f}..{lat[yslice][-1]:.2f} ({lat[yslice].size}),",
            f"lon={lon[xslice][0]:.2f}..{lon[xslice][-1]:.2f} ({lon[xslice].size})",
            flush=True,
        )

        years = [1980] if test_only else list(range(1980, 2023))
        blocks: list[np.ndarray] = []
        times: list[pd.Timestamp] = []
        for year in years:
            start = (year - 1980) * 12
            block = np.asarray(
                source.variables["temp"][start : start + 6, zslice, yslice, xslice],
                dtype=np.float32,
            )
            if block.shape != (6, depth[zslice].size, lat[yslice].size, lon[xslice].size):
                raise ValueError(f"Unexpected APDRC block shape for {year}: {block.shape}")
            block[block < -1.0e10] = np.nan
            blocks.append(block)
            times.extend(pd.Timestamp(year, month, 15) for month in MONTHS)
            print(f"APDRC {year}: downloaded {block.nbytes / 2**20:.1f} MiB", flush=True)

    values = np.concatenate(blocks, axis=0)
    da = xr.DataArray(
        values,
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
    return da


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    existing = destination.stat().st_size if destination.exists() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    mode = "ab" if existing else "wb"
    with requests.get(url, stream=True, timeout=(30, 300), headers=headers) as response:
        response.raise_for_status()
        if existing and response.status_code != 206:
            existing = 0
            mode = "wb"
        expected = int(response.headers.get("Content-Length", "0")) + existing
        print(
            f"Downloading {url}\n  expected size: {expected / 2**30:.2f} GiB",
            flush=True,
        )
        written = existing
        next_report = ((written // (256 * 2**20)) + 1) * 256 * 2**20
        with destination.open(mode) as stream:
            for chunk in response.iter_content(chunk_size=8 * 2**20):
                if not chunk:
                    continue
                stream.write(chunk)
                written += len(chunk)
                if written >= next_report:
                    print(f"  downloaded {written / 2**30:.2f} GiB", flush=True)
                    next_report += 256 * 2**20
    if expected and destination.stat().st_size != expected:
        raise IOError(
            f"Download size mismatch for {url}: {destination.stat().st_size} != {expected}"
        )


def find_name(ds: xr.Dataset, candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in ds.coords or name in ds.dims:
            return name
    raise KeyError(f"None of {candidates} found. Coords={list(ds.coords)}, dims={list(ds.dims)}")


def extract_official_year(path: Path, year: int) -> xr.DataArray:
    with xr.open_dataset(path, engine="netcdf4", chunks=None) as ds:
        if "temp" not in ds:
            raise KeyError(f"No temp variable in {path}: {list(ds.data_vars)}")
        zname = find_name(ds, ("st_ocean", "depth", "lev", "LEV"))
        yname = find_name(ds, ("yt_ocean", "lat", "latitude"))
        xname = find_name(ds, ("xt_ocean", "lon", "longitude"))
        tname = find_name(ds, ("time", "TIME"))
        print(
            f"{year} official file dimensions: {dict(ds.sizes)}; "
            f"temp dims={ds['temp'].dims}",
            flush=True,
        )
        da = ds["temp"]
        if tname != "time":
            da = da.rename({tname: "time"})
        if zname != "depth":
            da = da.rename({zname: "depth"})
        if yname != "lat":
            da = da.rename({yname: "lat"})
        if xname != "lon":
            da = da.rename({xname: "lon"})
        da = da.assign_coords(lon=da.lon % 360).sortby("lon").sortby("lat")
        da = da.sel(depth=slice(0, DEPTH_MAX_M), lat=slice(*LAT_BOUNDS), lon=slice(*LON_BOUNDS))
        # The official annual files contain duplicated/invalid time coordinate
        # values.  Their 12 records are nevertheless ordered January-December,
        # so select January-June by record position and then assign valid dates.
        target = da.isel(time=slice(0, 6)).load()
        if target.sizes.get("time", 0) != 6:
            raise ValueError(f"Expected six records in {year}, found {target.sizes.get('time', 0)}")
        target = target.assign_coords(
            time=pd.DatetimeIndex([pd.Timestamp(year, month, 15) for month in MONTHS])
        )
        target.name = "temp"
        target.attrs.update(long_name="SODA3 potential temperature", units="degC")
        return target.astype(np.float32)


def harmonize_to_apdrc_grid(da: xr.DataArray, reference: xr.DataArray) -> xr.DataArray:
    if (
        da.sizes["depth"] == reference.sizes["depth"]
        and da.sizes["lat"] == reference.sizes["lat"]
        and da.sizes["lon"] == reference.sizes["lon"]
        and np.allclose(da.depth, reference.depth)
        and np.allclose(da.lat, reference.lat)
        and np.allclose(da.lon, reference.lon)
    ):
        return da.assign_coords(depth=reference.depth, lat=reference.lat, lon=reference.lon)
    print("Interpolating recent-year subset to the APDRC 0.5-degree grid", flush=True)
    return da.interp(
        depth=reference.depth,
        lat=reference.lat,
        lon=reference.lon,
        method="linear",
    ).astype(np.float32)


def write_output(da: xr.DataArray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ds = da.to_dataset()
    ds.attrs.update(
        title="SODA3.15.2 equatorial Pacific upper-ocean potential temperature",
        source="University of Maryland SODA3.15.2; APDRC OPeNDAP mirror for 1980-2022",
        subset="January-June, 1980-2024; 5S-5N, 120E-80W, upper 300 m",
    )
    encoding = {"temp": {"zlib": True, "complevel": 4, "dtype": "float32"}}
    ds.to_netcdf(path, engine="netcdf4", encoding=encoding)
    print(f"Wrote {path} ({path.stat().st_size / 2**20:.1f} MiB)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test",
        action="store_true",
        help="Read only January-June 1980 from APDRC and write a small test subset.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    test_path = RAW_DIR / "soda3.15.2_equatorial_temp_jan_jun_1980_test.nc"
    destination = test_path if args.test else OUTPUT
    if destination.exists() and not args.force:
        print(f"Already exists: {destination}", flush=True)
        return 0

    historical = fetch_apdrc(test_only=args.test)
    if args.test:
        write_output(historical, destination)
        return 0

    recent: list[xr.DataArray] = []
    for year in (2023, 2024):
        free_gib = shutil.disk_usage("/private/tmp").free / 2**30
        if free_gib < 5.0:
            raise OSError(f"Not enough temporary disk space before {year}: {free_gib:.1f} GiB")
        with tempfile.TemporaryDirectory(prefix=f"soda3_{year}_", dir="/private/tmp") as tmp:
            full_path = Path(tmp) / f"soda3.15.2_mn_ocean_reg_{year}.nc"
            download_file(UMD_TEMPLATE.format(year=year), full_path)
            extracted = extract_official_year(full_path, year)
            recent.append(harmonize_to_apdrc_grid(extracted, historical))
            print(f"{year}: extracted subset; temporary global file will be removed", flush=True)

    combined = xr.concat([historical, *recent], dim="time").sortby("time")
    expected = 45 * 6
    if combined.sizes["time"] != expected:
        raise ValueError(f"Expected {expected} monthly records, found {combined.sizes['time']}")
    write_output(combined, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
