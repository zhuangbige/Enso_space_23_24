#!/usr/bin/env python3
"""Extract compact SODA3.15.2 five-day equatorial wind-stress indices.

Only the surface zonal wind-stress field is read from the official SODA3
files.  The output is intentionally small and is used to distinguish
high-frequency westerly stress pulses from the monthly ENSO wind response.

The primary WWB box follows the commonly used western-equatorial-Pacific
window (5S-5N, 135E-180).  A central-Pacific box (5S-5N, 180-140W) is also
retained for sensitivity tests.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import h5py
import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_soda3_5day_event_transport import (  # noqa: E402
    ClassicNetCDFRemote,
    clean,
    contiguous_slice,
    import_fsspec,
    list_event_files,
    source_format,
)


EVENT_YEARS = (
    1982,
    1986,
    1991,
    1994,
    1997,
    2002,
    2004,
    2006,
    2009,
    2015,
    2018,
    2019,
    2023,
)
LAT_BOUNDS = (-5.0, 5.0)
WWB_LON_BOUNDS = (135.0, 180.0)
CENTRAL_LON_BOUNDS = (180.0, 220.0)
OUTPUT = (
    ROOT
    / "data/interim/research_2026/"
    "soda3_5day_wwb_stress_1982_2023_event_years.csv"
)
CACHE_DIR = OUTPUT.parent / "soda3_5day_wwb_stress_by_year"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(EVENT_YEARS))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def weighted_mean(
    field: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    *,
    lon_bounds: tuple[float, float],
) -> float:
    lat_mask = (lat >= LAT_BOUNDS[0]) & (lat <= LAT_BOUNDS[1])
    lon_mask = (lon >= lon_bounds[0]) & (lon <= lon_bounds[1])
    subset = field[np.ix_(lat_mask, lon_mask)]
    weights = np.cos(np.deg2rad(lat[lat_mask]))[:, None]
    valid = np.isfinite(subset)
    numerator = np.nansum(subset * weights)
    denominator = np.sum(valid * weights)
    if denominator == 0:
        return float("nan")
    return float(numerator / denominator)


def read_hdf5(
    url: str,
    cache: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fsspec = import_fsspec()
    remote = fsspec.open(
        url,
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            if "hdf_stress_grid" not in cache:
                lat_full = np.asarray(dataset["yu_ocean"][:], dtype=float)
                lon_full = np.asarray(dataset["xu_ocean"][:], dtype=float) % 360
                y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
                x_slice = contiguous_slice(
                    lon_full,
                    WWB_LON_BOUNDS[0],
                    CENTRAL_LON_BOUNDS[1],
                )
                cache["hdf_stress_grid"] = (
                    lat_full[y_slice],
                    lon_full[x_slice],
                    y_slice,
                    x_slice,
                )
            lat, lon, y_slice, x_slice = cache["hdf_stress_grid"]
            field = clean(dataset["taux"][0, y_slice, x_slice])
    finally:
        remote.close()
    return field, np.asarray(lat), np.asarray(lon)


def read_cdf2(
    url: str,
    session: requests.Session,
    cache: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    template = cache.get("template")
    dataset = ClassicNetCDFRemote(
        url,
        session=session,
        template=template if isinstance(template, ClassicNetCDFRemote) else None,
    )
    if template is None:
        cache["template"] = dataset
    if "cdf_stress_grid" not in cache:
        lat_full = dataset.read_coordinate("yu_ocean")
        lon_full = dataset.read_coordinate("xu_ocean") % 360
        y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
        x_slice = contiguous_slice(
            lon_full,
            WWB_LON_BOUNDS[0],
            CENTRAL_LON_BOUNDS[1],
        )
        cache["cdf_stress_grid"] = (
            lat_full[y_slice],
            lon_full[x_slice],
            y_slice,
            x_slice,
        )
    lat, lon, y_slice, x_slice = cache["cdf_stress_grid"]
    field = dataset.read_record_3d("taux", y_slice, x_slice)
    return field, np.asarray(lat), np.asarray(lon)


def process_year(
    year: int,
    files: list[tuple[pd.Timestamp, str]],
) -> pd.DataFrame:
    session = requests.Session()
    cache: dict[str, object] = {}
    rows: list[dict[str, object]] = []
    for index, (timestamp, url) in enumerate(files, 1):
        kind = cache.get("source_format")
        if kind is None:
            kind = source_format(url, session)
            cache["source_format"] = kind
        if kind == "hdf5":
            field, lat, lon = read_hdf5(url, cache)
        else:
            field, lat, lon = read_cdf2(url, session, cache)
        rows.append(
            {
                "time": timestamp,
                "year": year,
                "month": timestamp.month,
                "day": timestamp.day,
                "taux_wwb_135e_180_nm2": weighted_mean(
                    field,
                    lat,
                    lon,
                    lon_bounds=WWB_LON_BOUNDS,
                ),
                "taux_central_180_220e_nm2": weighted_mean(
                    field,
                    lat,
                    lon,
                    lon_bounds=CENTRAL_LON_BOUNDS,
                ),
                "source_url": url,
            }
        )
        print(
            f"{year}: stress {index}/{len(files)} ({timestamp.date()})",
            flush=True,
        )
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() and not args.force:
        existing = pd.read_csv(OUTPUT)
        present = set(existing["year"].unique())
    else:
        existing = pd.DataFrame()
        present = set()
    missing = [year for year in years if year not in present]
    if not missing:
        print(f"Already complete: {OUTPUT}")
        return 0
    files = list_event_files(missing)
    pieces = [existing] if not existing.empty else []
    for year in missing:
        cache_path = CACHE_DIR / f"soda3_5day_wwb_stress_{year}.csv"
        if cache_path.exists() and not args.force:
            year_frame = pd.read_csv(cache_path, parse_dates=["time"])
            if (
                len(year_frame) == len(files[year])
                and year_frame["time"].nunique() == len(files[year])
            ):
                print(f"Reusing {cache_path}", flush=True)
                pieces.append(year_frame)
                continue
        year_frame = process_year(year, files[year])
        year_frame.to_csv(cache_path, index=False)
        print(f"Cached {cache_path}", flush=True)
        pieces.append(year_frame)
    output = pd.concat(pieces, ignore_index=True).sort_values("time")
    if output.duplicated("time").any():
        raise ValueError("Duplicate five-day timestamps")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False)
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
