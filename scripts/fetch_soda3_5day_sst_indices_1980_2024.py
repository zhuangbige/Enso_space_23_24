#!/usr/bin/env python3
"""Extract five-day SODA3.15.2 Niño3.4 and far-east-Pacific SST indices.

Only the shallowest tracer-temperature level (about 5 m) in 5S-5N is read
from the official files.  HTTP byte ranges keep the transfer compact; the
global 285 MB source files are never downloaded in full.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from pathlib import Path
import sys

import h5py
import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_soda3_5day_event_transport import (  # noqa: E402
    BASE_URL,
    ClassicNetCDFRemote,
    clean,
    contiguous_slice,
    import_fsspec,
    source_format,
)


OUTPUT = (
    ROOT
    / "data/interim/research_2026/soda3_5day_sst/"
    "soda3_5day_nino34_fep_sst_1980_2024.csv"
)
CACHE_DIR = OUTPUT.parent / "by_year"
YEARS = tuple(range(1980, 2025))
LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (190.0, 280.0)
NINO34_BOUNDS = (190.0, 240.0)  # 170W-120W
FEP_BOUNDS = (270.0, 280.0)  # 90W-80W


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(YEARS))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-files", type=int)
    return parser.parse_args()


def list_files(years: list[int]) -> dict[int, list[tuple[pd.Timestamp, str]]]:
    response = requests.get(f"{BASE_URL}/", timeout=90)
    response.raise_for_status()
    pattern = re.compile(
        r"soda3\.15\.2_5dy_ocean_reg_"
        r"(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2})\.nc"
    )
    requested = set(years)
    found: dict[int, dict[str, tuple[pd.Timestamp, str]]] = {
        year: {} for year in years
    }
    for match in pattern.finditer(response.text):
        year = int(match.group("year"))
        if year not in requested:
            continue
        filename = match.group(0)
        timestamp = pd.Timestamp(
            year,
            int(match.group("month")),
            int(match.group("day")),
        )
        found[year][filename] = (timestamp, f"{BASE_URL}/{filename}")
    output = {year: sorted(values.values()) for year, values in found.items()}
    for year, values in output.items():
        minimum = 65 if year == 2024 else 70
        if len(values) < minimum:
            raise ValueError(f"Incomplete official five-day listing for {year}: {len(values)}")
    return output


def area_mean(
    field: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    lon_bounds: tuple[float, float],
) -> float:
    lat_mask = (lat >= LAT_BOUNDS[0]) & (lat <= LAT_BOUNDS[1])
    lon_mask = (lon >= lon_bounds[0]) & (lon <= lon_bounds[1])
    subset = field[np.ix_(lat_mask, lon_mask)]
    weights = np.cos(np.deg2rad(lat[lat_mask]))[:, None]
    valid = np.isfinite(subset)
    denominator = np.sum(valid * weights)
    if denominator == 0:
        return float("nan")
    return float(np.nansum(subset * weights) / denominator)


def initialize_cdf(
    url: str,
) -> tuple[ClassicNetCDFRemote, tuple[np.ndarray, np.ndarray, slice, slice]]:
    session = requests.Session()
    template = ClassicNetCDFRemote(url, session=session)
    lat_full = template.read_coordinate("yt_ocean")
    lon_full = template.read_coordinate("xt_ocean") % 360.0
    y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
    x_slice = contiguous_slice(lon_full, *LON_BOUNDS)
    return template, (lat_full[y_slice], lon_full[x_slice], y_slice, x_slice)


def read_cdf(
    timestamp: pd.Timestamp,
    url: str,
    template: ClassicNetCDFRemote,
    grid: tuple[np.ndarray, np.ndarray, slice, slice],
) -> dict[str, object]:
    session = requests.Session()
    dataset = ClassicNetCDFRemote(url, session=session, template=template)
    lat, lon, y_slice, x_slice = grid
    field = dataset.read_record_4d("temp", slice(0, 1), y_slice, x_slice)[0]
    return make_row(timestamp, url, field, lat, lon)


def read_hdf(timestamp: pd.Timestamp, url: str) -> dict[str, object]:
    fsspec = import_fsspec()
    remote = fsspec.open(
        url,
        "rb",
        block_size=2 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            lat_full = np.asarray(dataset["yt_ocean"][:], dtype=float)
            lon_full = np.asarray(dataset["xt_ocean"][:], dtype=float) % 360.0
            y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
            x_slice = contiguous_slice(lon_full, *LON_BOUNDS)
            field = clean(dataset["temp"][0, 0, y_slice, x_slice])
            lat = lat_full[y_slice]
            lon = lon_full[x_slice]
    finally:
        remote.close()
    return make_row(timestamp, url, field, lat, lon)


def make_row(
    timestamp: pd.Timestamp,
    url: str,
    field: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
) -> dict[str, object]:
    nino34 = area_mean(field, lat, lon, NINO34_BOUNDS)
    fep = area_mean(field, lat, lon, FEP_BOUNDS)
    if not (10.0 < nino34 < 35.0 and 8.0 < fep < 35.0):
        raise ValueError(f"Nonphysical surface temperature at {timestamp}: {nino34}, {fep}")
    return {
        "time": timestamp,
        "year": int(timestamp.year),
        "month": int(timestamp.month),
        "day": int(timestamp.day),
        "day_of_year": int(timestamp.dayofyear),
        "nino34_sst_c": nino34,
        "fep_sst_c": fep,
        "read_error": "",
        "source_url": url,
    }


def missing_row(timestamp: pd.Timestamp, url: str, error: Exception) -> dict[str, object]:
    return {
        "time": timestamp,
        "year": int(timestamp.year),
        "month": int(timestamp.month),
        "day": int(timestamp.day),
        "day_of_year": int(timestamp.dayofyear),
        "nino34_sst_c": np.nan,
        "fep_sst_c": np.nan,
        "read_error": f"{type(error).__name__}: {error}",
        "source_url": url,
    }


def process_year(
    year: int,
    files: list[tuple[pd.Timestamp, str]],
    *,
    workers: int,
    force: bool,
    max_files: int | None,
) -> pd.DataFrame:
    suffix = f"_first{max_files}" if max_files else ""
    cache_path = CACHE_DIR / f"soda3_5day_sst_{year}{suffix}.csv"
    selected = files[:max_files] if max_files else files
    if cache_path.exists() and not force:
        cached = pd.read_csv(cache_path, parse_dates=["time"])
        if len(cached) == len(selected) and cached["time"].nunique() == len(selected):
            print(f"{year}: reused {cache_path}", flush=True)
            return cached

    session = requests.Session()
    kind = source_format(selected[0][1], session)
    if kind == "cdf2":
        template, grid = initialize_cdf(selected[0][1])

        def reader(item: tuple[pd.Timestamp, str]) -> dict[str, object]:
            return read_cdf(item[0], item[1], template, grid)

    else:

        def reader(item: tuple[pd.Timestamp, str]) -> dict[str, object]:
            return read_hdf(item[0], item[1])

    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {executor.submit(reader, item): item for item in selected}
        for index, future in enumerate(as_completed(future_map), 1):
            item = future_map[future]
            timestamp = item[0]
            try:
                rows.append(future.result())
            except Exception as first_error:
                last_error: Exception = first_error
                recovered = False
                for _ in range(2):
                    try:
                        rows.append(reader(item))
                        recovered = True
                        break
                    except Exception as retry_error:
                        last_error = retry_error
                if not recovered:
                    print(
                        f"{year}: retained missing {timestamp.date()} ({last_error})",
                        flush=True,
                    )
                    rows.append(missing_row(timestamp, item[1], last_error))
            if index == 1 or index % 12 == 0 or index == len(selected):
                print(f"{year}: {index}/{len(selected)} ({timestamp.date()})", flush=True)
    output = pd.DataFrame(rows).sort_values("time")
    if output["time"].nunique() != len(selected):
        raise ValueError(f"Duplicate or missing timestamps for {year}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output.to_csv(cache_path, index=False, date_format="%Y-%m-%d")
    return output


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    files = list_files(years)
    pieces = []
    for year in years:
        pieces.append(
            process_year(
                year,
                files[year],
                workers=args.workers,
                force=args.force,
                max_files=args.max_files,
            )
        )
    combined = pd.concat(pieces, ignore_index=True).sort_values("time")
    if args.max_files is None and years == list(YEARS):
        if combined["time"].duplicated().any():
            raise ValueError("Duplicate timestamps in combined SODA3 index")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(OUTPUT, index=False, date_format="%Y-%m-%d")
        print(f"Wrote {OUTPUT}", flush=True)
    else:
        print(f"Validated {len(combined)} five-day records", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
