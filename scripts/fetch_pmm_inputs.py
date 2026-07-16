#!/usr/bin/env python3
"""Fetch OISST and ERA5 inputs for a local PMM-like EOF/index diagnostic."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlretrieve
from zipfile import ZipFile, is_zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/interim/research_2026/pmm_inputs"
ERA5_DIR = ROOT / "data/raw/era5"

OISST_BASE = "https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
MONTHS = [f"{month:02d}" for month in range(1, 13)]
MONTH_NAMES = {
    "01": "jan",
    "02": "feb",
    "03": "mar",
    "04": "apr",
    "05": "may",
    "06": "jun",
    "07": "jul",
    "08": "aug",
    "09": "sep",
    "10": "oct",
    "11": "nov",
    "12": "dec",
}


def oisst_target(month: str) -> Path:
    end_year = 2026 if int(month) <= 5 else 2025
    return OUT / f"oisst_sst_pmm_1deg_{MONTH_NAMES[month]}_1982_{end_year}.nc"


def oisst_url(month: str) -> str:
    end_year = 2026 if int(month) <= 5 else 2025
    query = {
        "var": "sst",
        "north": 30,
        "west": 120,
        "east": 280,
        "south": -20,
        "horizStride": 4,
        "time_start": f"1982-{month}-01T00:00:00Z",
        "time_end": f"{end_year}-{month}-01T00:00:00Z",
        "timeStride": 12,
        "accept": "netcdf",
    }
    return f"{OISST_BASE}?{urlencode(query)}"


ERA5_REQUESTS = {
    "history": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "target": "era5_monthly_10m_wind_pmm_1deg_1982_2025.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
            "year": [str(year) for year in range(1982, 2026)],
            "month": MONTHS,
            "time": ["00:00"],
            "area": [30, -180, -20, 180],
            "grid": [1.0, 1.0],
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
    "current_2026": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "target": "era5_monthly_10m_wind_pmm_1deg_2026_jan_may.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
            "year": ["2026"],
            "month": ["01", "02", "03", "04", "05"],
            "time": ["00:00"],
            "area": [30, -180, -20, 180],
            "grid": [1.0, 1.0],
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
}


def fetch_oisst(*, dry_run: bool, force: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for month in MONTHS:
        target = oisst_target(month)
        if target.exists() and target.stat().st_size > 0 and not force:
            print(f"exists: {target}")
            continue
        url = oisst_url(month)
        if dry_run:
            print(url)
            print(target)
            continue
        tmp = target.with_suffix(target.suffix + ".tmp")
        print(f"download OISST month={month}: {target}", flush=True)
        urlretrieve(url, tmp)
        tmp.replace(target)
        print(target)


def _extract_if_zip(path: Path) -> None:
    if not path.exists() or not is_zipfile(path):
        return
    out_dir = path.with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(path) as zf:
        zf.extractall(out_dir)
    print(f"extracted zip to: {out_dir}")


def fetch_era5(name: str, *, dry_run: bool, force: bool) -> None:
    spec = ERA5_REQUESTS[name]
    target = ERA5_DIR / spec["target"]
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"exists: {target}")
        _extract_if_zip(target)
        return
    if dry_run:
        print(spec["dataset"])
        print(target)
        print(spec["request"])
        return
    try:
        import cdsapi
    except ModuleNotFoundError as exc:
        raise SystemExit("cdsapi is not installed in this Python environment.") from exc
    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    print(f"download ERA5 {name}: {target}", flush=True)
    cdsapi.Client().retrieve(spec["dataset"], spec["request"], str(target))
    _extract_if_zip(target)
    print(target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch PMM diagnostic inputs.")
    parser.add_argument("--only", choices=("all", "oisst", "era5"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.only in {"all", "oisst"}:
        fetch_oisst(dry_run=args.dry_run, force=args.force)
    if args.only in {"all", "era5"}:
        fetch_era5("history", dry_run=args.dry_run, force=args.force)
        fetch_era5("current_2026", dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
