#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data/raw/era5"
YEARS = [str(year) for year in range(1982, 2025)]
MONTHS = [f"{month:02d}" for month in range(1, 13)]
AREA = [30, -180, -30, 180]


REQUESTS = {
    "single_levels": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "target": "era5_monthly_single_levels_tropics_1982_2024.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "10m_u_component_of_wind",
                "mean_sea_level_pressure",
            ],
            "year": YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": AREA,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
    "pressure_levels": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "target": "era5_monthly_pressure_levels_tropics_1982_2024.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "u_component_of_wind",
                "divergence",
                "vertical_velocity",
            ],
            "pressure_level": ["200", "500", "850"],
            "year": YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": AREA,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
    "u850": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "target": "era5_monthly_u850_tropics_1982_2024.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": ["u_component_of_wind"],
            "pressure_level": ["850"],
            "year": YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": AREA,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
    "walker": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "target": "era5_monthly_walker_tropics_1982_2024.nc",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "divergence",
                "vertical_velocity",
            ],
            "pressure_level": ["200", "500"],
            "year": YEARS,
            "month": MONTHS,
            "time": ["00:00"],
            "area": AREA,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch ERA5 monthly means from Copernicus CDS.")
    parser.add_argument(
        "--request",
        choices=tuple(REQUESTS),
        default="single_levels",
        help="Which ERA5 request to run.",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTDIR)
    parser.add_argument("--dry-run", action="store_true", help="Print the CDS request without downloading.")
    parser.add_argument("--start-year", type=int, default=None, help="Optional first year override.")
    parser.add_argument("--end-year", type=int, default=None, help="Optional last year override.")
    args = parser.parse_args()

    spec = REQUESTS[args.request]
    request = {key: value for key, value in spec["request"].items()}
    if args.start_year is not None or args.end_year is not None:
        start_year = args.start_year if args.start_year is not None else int(YEARS[0])
        end_year = args.end_year if args.end_year is not None else int(YEARS[-1])
        request["year"] = [str(year) for year in range(start_year, end_year + 1)]
    target = args.output_dir / spec["target"]
    if args.start_year is not None or args.end_year is not None:
        suffix = f"{request['year'][0]}_{request['year'][-1]}"
        target = target.with_name(f"{target.stem}_{suffix}{target.suffix}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(spec["dataset"])
        print(target)
        print(request)
        return 0

    try:
        import cdsapi
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "cdsapi is not installed. Install it with `python3 -m pip install cdsapi`, "
            "then configure ~/.cdsapirc from your Copernicus CDS account."
        ) from exc

    try:
        client = cdsapi.Client()
    except Exception as exc:
        raise SystemExit(
            "CDS API credentials are missing or incomplete. Create ~/.cdsapirc from your "
            "Copernicus CDS account page, accept the ERA5 dataset licence on the CDS website, "
            "then rerun this script."
        ) from exc
    client.retrieve(str(spec["dataset"]), request, str(target))
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
