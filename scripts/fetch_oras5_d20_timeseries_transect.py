#!/usr/bin/env python3
"""Fetch ORAS5 D20 equatorial time series for a Fig. 4-style transect.

The Jiang et al. (2026) GRL Fig. 4 thermocline panel uses ORAS5 D20
(`depth_of_20_c_isotherm`). Downloading the full gridded ORAS5 D20 record is
large, so this script uses the official CDS ORAS5 time-series product to fetch
nearest-native-grid point series along the equatorial Pacific.
"""

from __future__ import annotations

import argparse
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_RAW = ROOT / "data/raw/oras5_timeseries"
OUT_INTERIM = ROOT / "data/interim/research_2026"

DATASET = "reanalysis-oras5-timeseries"
VARIABLE = "depth_of_20_c_isotherm"
DEFAULT_END_DATE = "2026-06-01"


def _lon_label(lon: int) -> str:
    if lon == 180:
        return "180"
    if lon < 180:
        return f"{lon}E"
    return f"{360-lon}W"


def _query_lon(lon: int) -> int:
    """CDS time-series location lookup expects western longitudes as negatives."""
    return lon if lon <= 180 else lon - 360


def _download_one(lon: int, latitude: float, end_date: str, force: bool) -> Path:
    OUT_RAW.mkdir(parents=True, exist_ok=True)
    end_tag = end_date[:7].replace("-", "")
    target = OUT_RAW / f"oras5_d20_eq_{_lon_label(lon)}_1960_{end_tag}.zip"
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"exists: {target}")
        return target

    import cdsapi

    request = {
        "product_type": ["consolidated", "operational"],
        "variable": [VARIABLE],
        "date": f"1960-01-01/{end_date}",
        "location": {"latitude": latitude, "longitude": _query_lon(lon)},
        "data_format": "csv",
    }
    print(f"request lon={lon} query_lon={_query_lon(lon)} lat={latitude}: {target}", flush=True)
    cdsapi.Client().retrieve(DATASET, request, str(target))
    return target


def _read_zip_csv(path: Path, requested_lon: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with ZipFile(path) as zf:
        for name in zf.namelist():
            product = "operational" if "operational" in name else "consolidated"
            payload = zf.read(name)
            df = pd.read_csv(io.BytesIO(payload), parse_dates=["valid_time"])
            df["product_type"] = product
            df["requested_lon"] = requested_lon
            frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(
        columns={
            "valid_time": "time",
            "so20chgt": "d20_m",
            "latitude": "native_lat",
            "longitude": "native_lon",
        }
    )
    out["year"] = out["time"].dt.year
    out["month"] = out["time"].dt.month
    return out


def build_transect(longitudes: list[int], latitude: float, end_date: str, force: bool, workers: int) -> pd.DataFrame:
    frames = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(_download_one, lon, latitude, end_date, force): lon
            for lon in longitudes
        }
        for future in as_completed(futures):
            lon = futures[future]
            path = future.result()
            frames.append(_read_zip_csv(path, lon))

    all_data = pd.concat(frames, ignore_index=True)
    all_data = all_data.sort_values(["requested_lon", "time", "product_type"])
    valid_counts = all_data.groupby("requested_lon")["d20_m"].apply(lambda s: s.notna().sum())
    print("valid monthly counts by requested lon:")
    print(valid_counts.to_string())
    return all_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch ORAS5 D20 time series along the equatorial Pacific.")
    parser.add_argument("--latitude", type=float, default=0.0)
    parser.add_argument("--lon-start", type=int, default=130)
    parser.add_argument("--lon-end", type=int, default=280)
    parser.add_argument("--lon-step", type=int, default=5)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE, help="Inclusive final month as YYYY-MM-01.")
    parser.add_argument("--workers", type=int, default=4, help="Parallel CDS point requests; keep modest to avoid queue pressure.")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    longitudes = list(range(args.lon_start, args.lon_end + 1, args.lon_step))
    transect = build_transect(longitudes, args.latitude, args.end_date, args.force, args.workers)

    OUT_INTERIM.mkdir(parents=True, exist_ok=True)
    end_tag = args.end_date[:7].replace("-", "")
    out_path = OUT_INTERIM / f"oras5_d20_timeseries_equatorial_1960_{end_tag}.csv"
    transect.to_csv(out_path, index=False)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
