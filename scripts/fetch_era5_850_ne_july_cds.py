#!/usr/bin/env python3
"""Download July ERA5 850-hPa winds for the Jiang northeasterly box."""

from __future__ import annotations

from pathlib import Path

import cdsapi


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/raw/era5/era5_monthly_850_ne_box_july_1982_2024.nc"
)


def main() -> int:
    if OUTPUT.exists() and OUTPUT.stat().st_size > 10_000:
        print(f"Already present: {OUTPUT}")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": [
            "u_component_of_wind",
            "v_component_of_wind",
        ],
        "pressure_level": ["850"],
        "year": [str(year) for year in range(1982, 2025)],
        "month": ["07"],
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [10, -180, 0, -130],
        "grid": [1.0, 1.0],
    }
    cdsapi.Client().retrieve(
        "reanalysis-era5-pressure-levels-monthly-means",
        request,
        str(OUTPUT),
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
