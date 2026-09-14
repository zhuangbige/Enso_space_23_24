#!/usr/bin/env python3
"""Fetch compact ORAS5 process time series across the tropical Pacific.

The CDS ORAS5 time-series product returns the nearest native-grid point for a
requested location. This script samples three tropical latitudes and 5-degree
longitudes, which is sufficient for an independent, lightweight validation of
SODA3 warm-water redistribution diagnostics without downloading global ORAS5
fields.
"""

from __future__ import annotations

import argparse
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/oras5_process_timeseries"
OUT_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_process_timeseries_3lat_5deg_1980_2024.csv"
)
DATASET = "reanalysis-oras5-timeseries"
VARIABLES = [
    "depth_of_20_c_isotherm",
    "ocean_heat_content_for_the_upper_300m",
    "sea_surface_height",
    "mixed_layer_depth_0_03",
    "zonal_wind_stress",
]
DATE_RANGE = "1980-01-01/2024-12-01"
DEFAULT_LATITUDES = (-4.0, 0.0, 4.0)
DEFAULT_LONGITUDES = tuple(range(130, 281, 5))

COLUMN_RENAME = {
    "valid_time": "time",
    "so20chgt": "d20_m",
    "sohtc300": "ohc300_jm2",
    "sossheig": "ssh_m",
    "somxl030": "mld03_m",
    "sozotaux": "taux_nm2",
    "latitude": "native_lat",
    "longitude": "native_lon",
}


def coordinate_label(value: float, *, latitude: bool) -> str:
    suffix = (
        ("S" if value < 0 else "N")
        if latitude
        else ("W" if value < 0 else "E")
    )
    return f"{abs(value):g}{suffix}".replace(".", "p")


def query_longitude(longitude_east: int) -> int:
    return longitude_east if longitude_east <= 180 else longitude_east - 360


def target_path(latitude: float, longitude_east: int) -> Path:
    lat_label = coordinate_label(latitude, latitude=True)
    query_lon = query_longitude(longitude_east)
    lon_label = coordinate_label(query_lon, latitude=False)
    return RAW_DIR / f"oras5_process_{lat_label}_{lon_label}_1980_2024.zip"


def download_one(
    latitude: float,
    longitude_east: int,
    *,
    force: bool,
    retries: int = 3,
) -> Path:
    target = target_path(latitude, longitude_east)
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"exists: {target.name}", flush=True)
        return target
    import cdsapi

    request = {
        "product_type": ["consolidated", "operational"],
        "variable": VARIABLES,
        "date": DATE_RANGE,
        "location": {
            "latitude": latitude,
            "longitude": query_longitude(longitude_east),
        },
        "data_format": "csv",
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            print(
                f"request lat={latitude:+g} lon={longitude_east:03d} "
                f"attempt={attempt}",
                flush=True,
            )
            cdsapi.Client(quiet=True).retrieve(DATASET, request, str(target))
            return target
        except Exception as exc:  # keep the batch resumable
            last_error = exc
            if attempt == retries:
                break
            wait_seconds = 20 * attempt
            print(
                f"retry lat={latitude:+g} lon={longitude_east}: "
                f"{exc}; wait {wait_seconds}s",
                flush=True,
            )
            time.sleep(wait_seconds)
    raise RuntimeError(
        f"ORAS5 download failed at {latitude}, {longitude_east}"
    ) from last_error


def read_point(
    path: Path,
    requested_lat: float,
    requested_lon: int,
) -> pd.DataFrame:
    frames = []
    with ZipFile(path) as archive:
        for name in archive.namelist():
            product_type = (
                "operational" if "operational" in name else "consolidated"
            )
            frame = pd.read_csv(
                io.BytesIO(archive.read(name)),
                parse_dates=["valid_time"],
            ).rename(columns=COLUMN_RENAME)
            frame["product_type"] = product_type
            frames.append(frame)
    output = pd.concat(frames, ignore_index=True)
    output["requested_lat"] = requested_lat
    output["requested_lon"] = requested_lon
    output["native_lon"] = output["native_lon"] % 360.0
    output["year"] = output["time"].dt.year
    output["month"] = output["time"].dt.month
    required = {
        "time",
        "d20_m",
        "ohc300_jm2",
        "ssh_m",
        "mld03_m",
        "taux_nm2",
        "native_lat",
        "native_lon",
    }
    missing = required - set(output)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    locations = [
        (latitude, longitude)
        for latitude in DEFAULT_LATITUDES
        for longitude in DEFAULT_LONGITUDES
    ]
    if args.dry_run:
        print(f"{len(locations)} point requests")
        print(f"variables: {VARIABLES}")
        print(f"date: {DATE_RANGE}")
        print(f"output: {OUT_CSV}")
        return 0

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(
                download_one,
                latitude,
                longitude,
                force=args.force,
            ): (latitude, longitude)
            for latitude, longitude in locations
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            latitude, longitude = futures[future]
            path = future.result()
            frames.append(read_point(path, latitude, longitude))
            print(
                f"complete {completed}/{len(locations)}: "
                f"lat={latitude:+g}, lon={longitude}",
                flush=True,
            )

    data = pd.concat(frames, ignore_index=True).sort_values(
        ["requested_lat", "requested_lon", "time", "product_type"]
    )
    if data.duplicated(["requested_lat", "requested_lon", "time"]).any():
        raise ValueError("Duplicate ORAS5 point-time records")
    expected = len(locations) * 45 * 12
    if len(data) != expected:
        raise ValueError(f"Expected {expected} rows, found {len(data)}")
    for column in (
        "d20_m",
        "ohc300_jm2",
        "ssh_m",
        "mld03_m",
        "taux_nm2",
    ):
        if data[column].notna().sum() == 0:
            raise ValueError(f"No finite values for {column}")
    data.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV} ({OUT_CSV.stat().st_size / 2**20:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
