#!/usr/bin/env python3
"""Fetch compact ERA5 monthly fields for the 2026 ENSO/FEP diagnosis.

The request intentionally uses a 1 degree grid and only Jan-May for
1982-2022 plus 2026. That keeps the files small while providing an ERA5-native
monthly climatology for current-anomaly maps.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data/raw/era5"
CLIM_YEARS = [str(year) for year in range(1982, 2023)]
TARGET_YEARS = ["2026"]
YEARS = CLIM_YEARS + TARGET_YEARS
MONTHS = ["01", "02", "03", "04", "05"]
AREA = [30, -180, -30, 180]
GRID = [1.0, 1.0]


REQUESTS = {
    "single": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "target": "era5_monthly_single_tropics_1deg_1982_2022_2026_jan_may.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
                "mean_sea_level_pressure",
                "total_precipitation",
            ],
            "year": YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": AREA,
            "grid": GRID,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
    "pressure850": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "target": "era5_monthly_pressure850_tropics_1deg_1982_2022_2026_jan_may.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "u_component_of_wind",
                "v_component_of_wind",
                "vertical_velocity",
            ],
            "pressure_level": ["850"],
            "year": YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": AREA,
            "grid": GRID,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
}


def retrieve_one(name: str, output_dir: Path, *, dry_run: bool, force: bool) -> Path:
    spec = REQUESTS[name]
    target = output_dir / spec["target"]
    if target.exists() and not force:
        print(f"exists: {target}")
        return target

    if dry_run:
        print(spec["dataset"])
        print(target)
        print(spec["request"])
        return target

    try:
        import cdsapi
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "cdsapi is not installed in this Python environment. Use the system "
            "`python3` if it has cdsapi, or install cdsapi in the virtual environment."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client()
    client.retrieve(spec["dataset"], spec["request"], str(target))
    print(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch compact ERA5 monthly fields for 2026 diagnostics.")
    parser.add_argument("--request", choices=("single", "pressure850", "all"), default="all")
    parser.add_argument("--output-dir", type=Path, default=OUTDIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    names = ("single", "pressure850") if args.request == "all" else (args.request,)
    for name in names:
        retrieve_one(name, args.output_dir, dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
