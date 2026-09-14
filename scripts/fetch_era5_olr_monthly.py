#!/usr/bin/env python3
"""Download January-June ERA5 monthly OLR inputs for 1980-2026.

ERA5's mean top net long-wave radiation flux is positive downward, so the
processing script converts it to conventional positive-upward OLR by changing
the sign. Requests are split by calendar month and at the date line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data/raw/era5/olr_monthly_1deg_1980_2026"
DATASET = "reanalysis-era5-single-levels-monthly-means"
VARIABLE = "mean_top_net_long_wave_radiation_flux"
START_YEAR = 1980
END_YEAR = 2026
MONTHS = tuple(f"{month:02d}" for month in range(1, 7))
AREAS = {
    "west": [20.0, 100.0, -20.0, 180.0],
    "east": [20.0, -180.0, -20.0, -80.0],
}


def request(month: str, area: list[float]) -> dict[str, object]:
    return {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": [VARIABLE],
        "year": [str(year) for year in range(START_YEAR, END_YEAR + 1)],
        "month": [month],
        "time": ["00:00"],
        "area": area,
        "grid": [1.0, 1.0],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def target(month: str, label: str) -> Path:
    return OUTPUT_DIR / (
        f"era5_olr_{label}_m{month}_{START_YEAR}_{END_YEAR}_1deg.nc"
    )


def validate(path: Path) -> None:
    if not path.exists() or path.stat().st_size < 1024:
        raise RuntimeError(f"download is missing or too small: {path}")
    import xarray as xr

    try:
        ds = xr.open_dataset(path, engine="h5netcdf")
    except Exception:
        ds = xr.open_dataset(path)
    time_name = "valid_time" if "valid_time" in ds.dims else "time"
    expected = END_YEAR - START_YEAR + 1
    if ds.sizes.get(time_name, 0) != expected:
        raise RuntimeError(
            f"{path} has {ds.sizes.get(time_name, 0)} times; expected {expected}"
        )
    names = set(ds.data_vars)
    if not ({"avg_tnlwrf", "mtnlwrf", VARIABLE, "var235040"} & names):
        raise RuntimeError(f"OLR flux variable not found in {path}: {sorted(names)}")
    ds.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = None
    for month in MONTHS:
        for label, area in AREAS.items():
            output = target(month, label)
            payload = request(month, area)
            if output.exists() and output.stat().st_size >= 1024 and not args.force:
                validate(output)
                print(f"exists: {output}")
                continue
            if args.dry_run:
                print(
                    json.dumps(
                        {
                            "dataset": DATASET,
                            "target": str(output),
                            "request": payload,
                        },
                        indent=2,
                    )
                )
                continue
            if client is None:
                import cdsapi

                client = cdsapi.Client()
            partial = output.with_suffix(".nc.part")
            if partial.exists():
                partial.unlink()
            last_error: Exception | None = None
            for attempt in range(1, args.retries + 1):
                try:
                    print(
                        f"request month={month} area={label} attempt={attempt}",
                        flush=True,
                    )
                    client.retrieve(DATASET, payload, str(partial))
                    validate(partial)
                    partial.replace(output)
                    print(output)
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - resumable batch
                    last_error = exc
                    if partial.exists():
                        partial.unlink()
                    if attempt < args.retries:
                        wait_seconds = min(10 * attempt, 30)
                        print(
                            f"retry after CDS error: {exc}; "
                            f"waiting {wait_seconds}s",
                            flush=True,
                        )
                        time.sleep(wait_seconds)
            if last_error is not None:
                raise RuntimeError(f"failed to download {output}") from last_error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
