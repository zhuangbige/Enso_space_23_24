#!/usr/bin/env python3
"""Download compact daily TAO temperature and wind-stress subsets by year.

The subset is limited to the equator, 180E-140W, January-June.  Year-wise
files keep the download resumable and avoid requesting the full global moored
buoy archive.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/tao_central_equator"
BASE = "https://data.pmel.noaa.gov/pmel/erddap/tabledap"
DEFAULT_YEARS = (1997, 2015, 2023)
LONGITUDES = (180, 190, 205, 220)

DATASETS = {
    "temperature": (
        "pmelTaoDyT",
        "station,longitude,latitude,time,depth,T_20,QT_5020,ST_6020",
    ),
    "wind_stress": (
        "pmelTaoDyTau",
        "station,longitude,latitude,time,depth,TX_442,TY_443,QTAU_5440",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument("--all-years", action="store_true", help="Use 1983-2024")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def build_url(
    dataset: str,
    variables: str,
    year: int,
    longitude: int,
    *,
    temperature: bool,
) -> str:
    query = (
        f"{variables}"
        f"&longitude={longitude}"
        "&latitude=0"
        f"&time>={year}-01-01T00:00:00Z"
        f"&time<={year}-06-30T23:59:59Z"
    )
    if temperature:
        query += "&depth<=300"
    encoded = quote(query, safe=",&=-:")
    return f"{BASE}/{dataset}.csv?{encoded}"


def download(url: str, target: Path) -> None:
    temporary = target.with_suffix(target.suffix + ".tmp")
    with requests.get(url, timeout=300, stream=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "csv" not in content_type and "octet-stream" not in content_type:
            raise RuntimeError(f"Unexpected content type {content_type} for {url}")
        with temporary.open("wb") as stream:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    stream.write(chunk)
    if temporary.stat().st_size < 80:
        raise RuntimeError(f"Downloaded response is unexpectedly small: {temporary}")
    temporary.replace(target)


def main() -> int:
    args = parse_args()
    years = list(range(1983, 2025)) if args.all_years else sorted(set(args.years))
    OUT.mkdir(parents=True, exist_ok=True)
    for year in years:
        for longitude in LONGITUDES:
            for label, (dataset, variables) in DATASETS.items():
                target = OUT / (
                    f"tao_0n_{longitude}e_{label}_{year}_jan_jun.csv"
                )
                if target.exists() and target.stat().st_size > 80 and not args.force:
                    print(f"exists: {target}", flush=True)
                    continue
                url = build_url(
                    dataset,
                    variables,
                    year,
                    longitude,
                    temperature=label == "temperature",
                )
                print(f"download: {label} {year} {longitude}E", flush=True)
                download(url, target)
                print(
                    f"wrote: {target} ({target.stat().st_size / 1024:.1f} KiB)",
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
