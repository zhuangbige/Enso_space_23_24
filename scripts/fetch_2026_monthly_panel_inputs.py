#!/usr/bin/env python3
"""Fetch missing inputs for 2026 monthly SSTA/precip/D20 + wind panels.

The plotting script can use the existing local ORAS5 equatorial D20 time
series, but the requested 1980-2025 detrended baseline needs a longer ERA5
Jan-May record and OISST Jan-May spatial fields than the compact quick-look
cache used earlier in the project.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlretrieve
from zipfile import ZipFile, is_zipfile


ROOT = Path(__file__).resolve().parents[1]
OISST_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
ERA5_DIR = ROOT / "data/raw/era5"

MONTHS = ["01", "02", "03", "04", "05"]
MONTH_NAMES = {
    "01": "jan",
    "02": "feb",
    "03": "mar",
    "04": "apr",
    "05": "may",
}

OISST_BASE = "https://psl.noaa.gov/thredds/ncss/grid/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc"
OISST_YEARS = (1982, 2026)
ERA5_YEARS = [str(year) for year in range(1980, 2027)]
ERA5_AREA = [30, -180, -30, 180]
ERA5_GRID = [1.0, 1.0]

ERA5_REQUESTS = {
    "pressure850_wind": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "target": "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": ["u_component_of_wind", "v_component_of_wind"],
            "pressure_level": ["850"],
            "year": ERA5_YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": ERA5_AREA,
            "grid": ERA5_GRID,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
    "single_precip": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "target": "era5_monthly_precip_tropics_1deg_1980_2026_jan_may.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": ["total_precipitation"],
            "year": ERA5_YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": ERA5_AREA,
            "grid": ERA5_GRID,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
}


def oisst_target(month: str) -> Path:
    return OISST_DIR / f"oisst_sst_tropics_1deg_{MONTH_NAMES[month]}_{OISST_YEARS[0]}_{OISST_YEARS[1]}.nc"


def oisst_url(month: str) -> str:
    start_year, end_year = OISST_YEARS
    query = {
        "var": "sst",
        "north": 30,
        "west": 120,
        "east": 280,
        "south": -30,
        "horizStride": 4,
        "time_start": f"{start_year}-{month}-01T00:00:00Z",
        "time_end": f"{end_year}-{month}-01T00:00:00Z",
        "timeStride": 12,
        "accept": "netcdf",
    }
    return f"{OISST_BASE}?{urlencode(query)}"


def fetch_oisst(*, dry_run: bool, force: bool) -> list[Path]:
    OISST_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for month in MONTHS:
        target = oisst_target(month)
        outputs.append(target)
        if target.exists() and target.stat().st_size > 0 and not force:
            print(f"exists: {target}")
            continue
        url = oisst_url(month)
        if dry_run:
            print(url)
            print(target)
            continue
        tmp = target.with_suffix(target.suffix + ".tmp")
        print(f"download OISST {month}: {target}", flush=True)
        urlretrieve(url, tmp)
        tmp.replace(target)
        print(target)
    return outputs


def _extract_if_zip(path: Path) -> None:
    if not path.exists() or not is_zipfile(path):
        return
    out_dir = path.with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(path) as zf:
        zf.extractall(out_dir)
    print(f"extracted zip to: {out_dir}")


def fetch_era5(name: str, *, dry_run: bool, force: bool) -> Path:
    spec = ERA5_REQUESTS[name]
    target = ERA5_DIR / spec["target"]
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"exists: {target}")
        _extract_if_zip(target)
        return target
    if dry_run:
        print(spec["dataset"])
        print(target)
        print(spec["request"])
        return target

    try:
        import cdsapi
    except ModuleNotFoundError as exc:
        raise SystemExit("cdsapi is not installed in this Python environment.") from exc

    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    print(f"download ERA5 {name}: {target}", flush=True)
    cdsapi.Client().retrieve(spec["dataset"], spec["request"], str(target))
    _extract_if_zip(target)
    print(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch inputs for 2026 monthly panel plots.")
    parser.add_argument("--only", choices=("all", "oisst", "era5"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.only in {"all", "oisst"}:
        fetch_oisst(dry_run=args.dry_run, force=args.force)
    if args.only in {"all", "era5"}:
        fetch_era5("pressure850_wind", dry_run=args.dry_run, force=args.force)
        fetch_era5("single_precip", dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
