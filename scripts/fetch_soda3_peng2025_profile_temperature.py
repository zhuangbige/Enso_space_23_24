#!/usr/bin/env python3
"""Complete the local equatorial SODA3 temperature record for Peng-style profiles.

The project already stores January--June 1980--2024.  This script downloads
only July--December 1980--2022 from the APDRC OPeNDAP aggregation and reads
only July--December 2023 from the official UMD annual file by HTTP byte
ranges.  January 2024 is retained so the 2023/24 NDJ mean can be formed.

The output is deliberately limited to 2S--2N, 120E--80W and the upper 300 m.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
import io
from pathlib import Path

import h5py
import netCDF4
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
LOCAL_JAN_JUN = (
    ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
OUTPUT = (
    ROOT
    / "data/raw/soda3"
    / "soda3.15.2_equatorial_temp_jan1980_jan2024_peng_profiles.nc"
)
CACHE_DIR = ROOT / "data/interim/research_2026/soda3_peng2025_profile_temperature"
HISTORICAL_JUL_DEC_CACHE = CACHE_DIR / "apdrc_jul_dec_1980_2022.nc"
APDRC_URL = (
    "https://apdrc.soest.hawaii.edu/dods/public_data/"
    "SODA/soda_3.15.2/monthly_t"
)
UMD_2023_URL = (
    "https://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_2023.nc"
)

LAT_BOUNDS = (-2.0, 2.0)
LON_BOUNDS = (120.0, 280.0)
DEPTH_MAX_M = 300.0
HISTORICAL_YEARS = tuple(range(1980, 2023))


class HTTPRangeReader(io.RawIOBase):
    """Small seekable HTTP reader with an LRU byte-block cache for h5py."""

    def __init__(
        self,
        url: str,
        *,
        block_size: int = 8 * 2**20,
        max_blocks: int = 12,
        timeout: tuple[int, int] = (30, 180),
    ) -> None:
        super().__init__()
        self.url = url
        self.block_size = int(block_size)
        self.max_blocks = int(max_blocks)
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(
            total=8,
            connect=8,
            read=8,
            status=8,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(("HEAD", "GET")),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        response = self.session.head(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        length = response.headers.get("Content-Length")
        if length is None:
            raise IOError(f"Remote file has no Content-Length: {url}")
        self.size = int(length)
        self.position = 0
        self.cache: OrderedDict[int, bytes] = OrderedDict()
        self.bytes_downloaded = 0
        self.requests_made = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            target = offset
        elif whence == io.SEEK_CUR:
            target = self.position + offset
        elif whence == io.SEEK_END:
            target = self.size + offset
        else:
            raise ValueError(f"Unsupported whence={whence}")
        if target < 0:
            raise ValueError("Negative seek position")
        self.position = min(int(target), self.size)
        return self.position

    def _block(self, start: int) -> bytes:
        if start in self.cache:
            block = self.cache.pop(start)
            self.cache[start] = block
            return block
        end = min(start + self.block_size, self.size) - 1
        response = self.session.get(
            self.url,
            headers={"Range": f"bytes={start}-{end}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.status_code != 206:
            raise IOError(
                f"Server ignored byte range {start}-{end}: HTTP {response.status_code}"
            )
        block = response.content
        expected = end - start + 1
        if len(block) != expected:
            raise IOError(f"Short range response: {len(block)} != {expected}")
        self.cache[start] = block
        self.bytes_downloaded += len(block)
        self.requests_made += 1
        while len(self.cache) > self.max_blocks:
            self.cache.popitem(last=False)
        return block

    def read(self, size: int = -1) -> bytes:
        if self.position >= self.size:
            return b""
        if size is None or size < 0:
            size = self.size - self.position
        size = min(int(size), self.size - self.position)
        remaining = size
        parts: list[bytes] = []
        while remaining > 0:
            block_start = (self.position // self.block_size) * self.block_size
            block = self._block(block_start)
            offset = self.position - block_start
            count = min(remaining, len(block) - offset)
            if count <= 0:
                raise IOError("HTTP block reader made no progress")
            parts.append(block[offset : offset + count])
            self.position += count
            remaining -= count
        return b"".join(parts)

    def readinto(self, buffer: bytearray | memoryview) -> int:
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self) -> None:
        if not self.closed:
            self.session.close()
            self.cache.clear()
        super().close()


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    indices = np.flatnonzero((values >= lower) & (values <= upper))
    if indices.size == 0 or not np.all(np.diff(indices) == 1):
        raise ValueError(f"Cannot make a contiguous slice for {lower}..{upper}")
    return slice(int(indices[0]), int(indices[-1]) + 1)


def open_local() -> xr.DataArray:
    if not LOCAL_JAN_JUN.exists():
        raise FileNotFoundError(f"Missing local source: {LOCAL_JAN_JUN}")
    with xr.open_dataset(LOCAL_JAN_JUN, engine="netcdf4") as dataset:
        result = dataset.temp.sel(
            lat=slice(*LAT_BOUNDS),
            lon=slice(*LON_BOUNDS),
            depth=slice(0.0, DEPTH_MAX_M),
        ).load()
    return result.astype(np.float32)


def fetch_apdrc_july_december(reference: xr.DataArray) -> xr.DataArray:
    if HISTORICAL_JUL_DEC_CACHE.exists():
        print(f"Loading cached APDRC fields: {HISTORICAL_JUL_DEC_CACHE}", flush=True)
        with xr.open_dataset(HISTORICAL_JUL_DEC_CACHE, engine="netcdf4") as cached:
            result = cached.temp.load()
        return result.astype(np.float32)
    print(f"Opening APDRC OPeNDAP: {APDRC_URL}", flush=True)
    blocks: list[np.ndarray] = []
    times: list[pd.Timestamp] = []
    with netCDF4.Dataset(APDRC_URL) as source:
        depth = np.asarray(source.variables["lev"][:], dtype=float)
        latitude = np.asarray(source.variables["lat"][:], dtype=float)
        longitude = np.asarray(source.variables["lon"][:], dtype=float) % 360.0
        zslice = contiguous_slice(depth, 0.0, DEPTH_MAX_M)
        yslice = contiguous_slice(latitude, *LAT_BOUNDS)
        xslice = contiguous_slice(longitude, *LON_BOUNDS)
        if not (
            np.allclose(depth[zslice], reference.depth)
            and np.allclose(latitude[yslice], reference.lat)
            and np.allclose(longitude[xslice], reference.lon)
        ):
            raise ValueError("APDRC and local SODA3 grids differ")
        for year in HISTORICAL_YEARS:
            first = (year - 1980) * 12 + 6
            block = np.ma.filled(
                source.variables["temp"][first : first + 6, zslice, yslice, xslice],
                np.nan,
            ).astype(np.float32)
            block[(block < -10.0) | (block > 50.0)] = np.nan
            expected = (
                6,
                reference.sizes["depth"],
                reference.sizes["lat"],
                reference.sizes["lon"],
            )
            if block.shape != expected:
                raise ValueError(f"Unexpected APDRC block for {year}: {block.shape}")
            blocks.append(block)
            times.extend(pd.Timestamp(year, month, 15) for month in range(7, 13))
            print(f"APDRC July--December complete: {year}", flush=True)
    result = xr.DataArray(
        np.concatenate(blocks, axis=0),
        dims=("time", "depth", "lat", "lon"),
        coords={
            "time": pd.DatetimeIndex(times),
            "depth": reference.depth,
            "lat": reference.lat,
            "lon": reference.lon,
        },
        name="temp",
        attrs={"long_name": "SODA3 potential temperature", "units": "degC"},
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    result.to_dataset(name="temp").to_netcdf(
        HISTORICAL_JUL_DEC_CACHE,
        engine="netcdf4",
        encoding={"temp": {"zlib": True, "complevel": 4, "dtype": "float32"}},
    )
    print(f"Cached APDRC fields: {HISTORICAL_JUL_DEC_CACHE}", flush=True)
    return result


def read_official_2023_july_december(
    reference: xr.DataArray,
    *,
    test_only: bool,
) -> xr.DataArray:
    print(f"Opening official UMD SODA3 by byte ranges: {UMD_2023_URL}", flush=True)
    remote = HTTPRangeReader(UMD_2023_URL)
    try:
        with h5py.File(remote, "r") as source:
            temperature = source["temp"]
            depth = np.asarray(source["st_ocean"][:], dtype=float)
            latitude = np.asarray(source["yt_ocean"][:], dtype=float)
            longitude = np.asarray(source["xt_ocean"][:], dtype=float) % 360.0
            zslice = contiguous_slice(depth, 0.0, DEPTH_MAX_M)
            yslice = contiguous_slice(latitude, *LAT_BOUNDS)
            xslice = contiguous_slice(longitude, *LON_BOUNDS)
            if not (
                np.allclose(depth[zslice], reference.depth)
                and np.allclose(latitude[yslice], reference.lat)
                and np.allclose(longitude[xslice], reference.lon)
            ):
                raise ValueError("Official 2023 and local SODA3 grids differ")
            print(
                f"Official temp shape={temperature.shape}, chunks={temperature.chunks}; "
                f"subset=depth {reference.sizes['depth']}, lat {reference.sizes['lat']}, "
                f"lon {reference.sizes['lon']}",
                flush=True,
            )
            months = (7,) if test_only else tuple(range(7, 13))
            pieces: list[np.ndarray] = []
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            for month in months:
                cache_path = CACHE_DIR / f"official_2023_month_{month:02d}.npz"
                if cache_path.exists() and not test_only:
                    with np.load(cache_path) as cached:
                        block = cached["temp"].astype(np.float32)
                    print(f"Official 2023-{month:02d}: loaded cache", flush=True)
                else:
                    month_index = month - 1
                    block = np.asarray(
                        temperature[
                            month_index : month_index + 1,
                            zslice,
                            yslice,
                            xslice,
                        ],
                        dtype=np.float32,
                    )
                    block[(block < -10.0) | (block > 50.0)] = np.nan
                    if not test_only:
                        np.savez_compressed(cache_path, temp=block)
                    print(f"Official 2023-{month:02d}: extracted", flush=True)
                expected_shape = (
                    1,
                    reference.sizes["depth"],
                    reference.sizes["lat"],
                    reference.sizes["lon"],
                )
                if block.shape != expected_shape:
                    raise ValueError(
                        f"Unexpected official block for 2023-{month:02d}: {block.shape}"
                    )
                pieces.append(block)
            values = np.concatenate(pieces, axis=0)
    finally:
        downloaded = remote.bytes_downloaded / 2**20
        requests_made = remote.requests_made
        remote.close()
        print(
            f"Official byte-range transfer: {downloaded:.1f} MiB in "
            f"{requests_made} requests",
            flush=True,
        )
    return xr.DataArray(
        values,
        dims=("time", "depth", "lat", "lon"),
        coords={
            "time": pd.DatetimeIndex([pd.Timestamp(2023, month, 15) for month in months]),
            "depth": reference.depth,
            "lat": reference.lat,
            "lon": reference.lon,
        },
        name="temp",
        attrs={"long_name": "SODA3 potential temperature", "units": "degC"},
    )


def write_output(data: xr.DataArray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = data.to_dataset(name="temp")
    dataset.attrs.update(
        title="SODA3.15.2 equatorial temperature for Peng-style profile analysis",
        source=(
            "APDRC SODA3.15.2 monthly_t for 1980-2022; official UMD annual "
            "file for July-December 2023; existing project subset for "
            "January-June 2023 and January 2024"
        ),
        subset="January 1980-January 2024; 2S-2N, 120E-80W, upper 300 m",
    )
    encoding = {"temp": {"zlib": True, "complevel": 4, "dtype": "float32"}}
    dataset.to_netcdf(path, engine="netcdf4", encoding=encoding)
    print(f"Wrote {path} ({path.stat().st_size / 2**20:.1f} MiB)", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--test-official",
        action="store_true",
        help="Read only July 2023 by HTTP ranges and do not write the full output.",
    )
    args = parser.parse_args()
    local = open_local()
    if args.test_official:
        sample = read_official_2023_july_december(local, test_only=True)
        print(
            f"Test subset: shape={sample.shape}, finite={np.isfinite(sample).mean():.4f}, "
            f"range=[{np.nanmin(sample):.3f}, {np.nanmax(sample):.3f}] degC",
            flush=True,
        )
        return 0
    if args.output.exists() and not args.force:
        print(f"Already exists: {args.output}", flush=True)
        return 0

    local_history = local.where(local.time.dt.year <= 2022, drop=True)
    local_2023_jan_jun = local.where(local.time.dt.year == 2023, drop=True)
    local_2024_january = local.where(
        (local.time.dt.year == 2024) & (local.time.dt.month == 1), drop=True
    )
    historical_jul_dec = fetch_apdrc_july_december(local)
    official_2023_jul_dec = read_official_2023_july_december(local, test_only=False)
    combined = xr.concat(
        [
            local_history,
            historical_jul_dec,
            local_2023_jan_jun,
            official_2023_jul_dec,
            local_2024_january,
        ],
        dim="time",
    ).sortby("time")
    expected_time = pd.date_range("1980-01-01", "2024-01-01", freq="MS") + pd.Timedelta(
        days=14
    )
    actual_time = pd.DatetimeIndex(combined.time.values)
    if not actual_time.equals(expected_time):
        raise ValueError(
            f"Combined time axis is not continuous: {actual_time[0]}--{actual_time[-1]}, "
            f"n={len(actual_time)}"
        )
    if not np.isfinite(combined.values).any():
        raise ValueError("Combined output contains no finite temperature")
    write_output(combined.astype(np.float32), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
