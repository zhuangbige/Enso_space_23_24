#!/usr/bin/env python3
"""Aggregate June 2026 ERA5T u10 from the public ARCO-ERA5 mirror.

This is a fallback for long CDS queues.  ARCO stores each hourly global field
as one Blosc-compressed Zarr v2 chunk.  The script downloads only u10 chunks,
extracts the Peng et al. (2025) CWP box, forms the exact hourly monthly mean,
and writes the same two 1-degree dateline pieces expected by the main analysis.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import sys
import threading
import time

import numpy as np
import requests
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data/raw/era5/peng_cwp_u10_monthly_1deg"
BASE_URL = (
    "https://storage.googleapis.com/gcp-public-data-arco-era5/ar/"
    "full_37-1h-0p25deg-chunk-1.zarr-v3/10m_u_component_of_wind"
)
DEPENDENCY_DIR = Path("/private/tmp/arco_era5_deps")
START_HOUR = 1_108_128  # Hours since 1900-01-01 at 2026-06-01 00 UTC.
N_HOURS = 30 * 24
FULL_SHAPE = (721, 1440)
_THREAD_LOCAL = threading.local()


def load_blosc_codec():
    """Import temporary numcodecs without replacing the active NumPy build."""

    if not DEPENDENCY_DIR.exists():
        raise SystemExit(
            "Temporary numcodecs dependency is missing; install zarr<3 into "
            f"{DEPENDENCY_DIR} first."
        )
    sys.path.insert(0, str(DEPENDENCY_DIR))
    from numcodecs import Blosc  # type: ignore[import-not-found]

    return Blosc(cname="lz4", clevel=5, shuffle=1, blocksize=0)


def session() -> requests.Session:
    value = getattr(_THREAD_LOCAL, "session", None)
    if value is None:
        value = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=2, max_retries=0)
        value.mount("https://", adapter)
        _THREAD_LOCAL.session = value
    return value


def fetch_hour(hour_index: int, codec, *, retries: int) -> np.ndarray:
    url = f"{BASE_URL}/{hour_index}.0.0"
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session().get(url, timeout=(20, 120))
            response.raise_for_status()
            decoded = codec.decode(response.content)
            field = np.frombuffer(decoded, dtype="<f4").reshape(FULL_SHAPE)
            return field
        except Exception as exc:  # noqa: BLE001 - remote fallback must retry.
            last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 15))
    raise RuntimeError(f"failed ARCO-ERA5T chunk {hour_index}") from last_error


def write_piece(path: Path, data: np.ndarray, latitude: np.ndarray, longitude: np.ndarray) -> None:
    dataset = xr.Dataset(
        data_vars={
            "u10": (
                ("valid_time", "latitude", "longitude"),
                data[np.newaxis].astype("float32"),
                {"long_name": "10 metre U wind component", "units": "m s**-1"},
            )
        },
        coords={
            "valid_time": np.asarray([np.datetime64("2026-06-01T00:00:00")]),
            "latitude": latitude.astype("float32"),
            "longitude": longitude.astype("float32"),
        },
        attrs={
            "source": "ARCO-ERA5 public mirror; ERA5T hourly analysis",
            "aggregation": "Arithmetic mean of all 720 hourly fields in June 2026",
            "retrieved": datetime.now().astimezone().isoformat(timespec="seconds"),
            "region_definition": "Peng et al. (2025) CWP: 5S-5N, 140E-160W",
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".arco.part")
    dataset.to_netcdf(partial, engine="h5netcdf")
    partial.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    outputs = [
        OUTPUT_DIR / "era5_peng_cwp_part01_m06_2026_2026_1p0deg.nc",
        OUTPUT_DIR / "era5_peng_cwp_part02_m06_2026_2026_1p0deg.nc",
    ]
    if all(path.exists() and path.stat().st_size >= 1024 for path in outputs) and not args.force:
        for path in outputs:
            print(f"exists: {path}")
        return 0

    codec = load_blosc_codec()
    latitude_full = np.linspace(90.0, -90.0, FULL_SHAPE[0])
    longitude_full = np.arange(FULL_SHAPE[1], dtype=float) * 0.25
    lat_idx = np.flatnonzero((latitude_full <= 5.0) & (latitude_full >= -5.0) & np.isclose(latitude_full % 1, 0))
    lon_idx = np.flatnonzero((longitude_full >= 140.0) & (longitude_full <= 200.0) & np.isclose(longitude_full % 1, 0))

    total = np.zeros((len(lat_idx), len(lon_idx)), dtype="float64")
    hours = list(range(START_HOUR, START_HOUR + N_HOURS))
    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(fetch_hour, hour, codec, retries=max(1, args.retries)): hour for hour in hours
        }
        for future in as_completed(futures):
            field = future.result()
            total += field[np.ix_(lat_idx, lon_idx)]
            completed += 1
            if completed % 60 == 0 or completed == N_HOURS:
                print(f"ARCO-ERA5T u10: {completed}/{N_HOURS} hours", flush=True)

    monthly = total / N_HOURS
    latitude = latitude_full[lat_idx]
    longitude = longitude_full[lon_idx]
    west = longitude <= 180.0
    east = longitude >= 180.0
    write_piece(outputs[0], monthly[:, west], latitude, longitude[west])
    write_piece(outputs[1], monthly[:, east], latitude, longitude[east] - 360.0)
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
