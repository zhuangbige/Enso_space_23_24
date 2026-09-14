#!/usr/bin/env python3
"""Download compact ERA5 hourly u10 for daily event-year wind-gate analysis.

Requests are split by calendar month and contain only the ten event years,
the central equatorial Pacific box, and a one-degree grid.  Files are
resumable and validated before a partial download replaces its target.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
DATASET = "reanalysis-era5-single-levels"
VARIABLE = "10m_u_component_of_wind"
EVENT_YEARS = (1982, 1986, 1991, 1997, 2002, 2004, 2015, 2018, 2019, 2023)
MONTHS = tuple(range(1, 10))
AREA = [5.0, -180.0, -5.0, -140.0]
GRID = [1.0, 1.0]
OUTPUT_DIR = ROOT / "data/raw/era5/daily_u10_central_pacific_event_years_1deg"


def build_request(years: list[int], month: int) -> dict[str, object]:
    return {
        "product_type": ["reanalysis"],
        "variable": [VARIABLE],
        "year": [str(year) for year in years],
        "month": [f"{month:02d}"],
        "day": [f"{day:02d}" for day in range(1, 32)],
        "time": [f"{hour:02d}:00" for hour in range(24)],
        "area": AREA,
        "grid": GRID,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def target_path(output_dir: Path, years: list[int], month: int) -> Path:
    year_tag = "_".join(str(year) for year in years)
    return output_dir / f"era5_daily_gate_hourly_u10_m{month:02d}_{year_tag}.nc"


def validate(path: Path, *, years: list[int], month: int) -> None:
    if not path.exists() or path.stat().st_size < 4096:
        raise RuntimeError(f"ERA5 download is missing or too small: {path}")
    import xarray as xr

    with xr.open_dataset(path, engine="h5netcdf") as dataset:
        time_name = "valid_time" if "valid_time" in dataset.coords else "time"
        latitude_name = "latitude" if "latitude" in dataset.coords else "lat"
        longitude_name = "longitude" if "longitude" in dataset.coords else "lon"
        if "u10" not in dataset.data_vars:
            raise RuntimeError(f"u10 is missing from {path}")
        times = dataset[time_name]
        if set(times.dt.year.values.astype(int)) != set(years):
            raise RuntimeError(f"Unexpected years in {path}")
        if set(times.dt.month.values.astype(int)) != {month}:
            raise RuntimeError(f"Unexpected months in {path}")
        expected_minimum = len(years) * 28 * 24
        expected_maximum = len(years) * 31 * 24
        if not expected_minimum <= dataset.sizes[time_name] <= expected_maximum:
            raise RuntimeError(f"Unexpected hourly count in {path}: {dataset.sizes[time_name]}")
        if dataset.sizes.get(latitude_name, 0) != 11:
            raise RuntimeError(f"Unexpected latitude count in {path}")
        if dataset.sizes.get(longitude_name, 0) != 41:
            raise RuntimeError(f"Unexpected longitude count in {path}")
        units = str(dataset["u10"].attrs.get("units", ""))
        if units not in {"m s**-1", "m s-1", "m/s"}:
            raise RuntimeError(f"Unexpected u10 units in {path}: {units}")


def retrieve(
    *,
    years: list[int],
    months: list[int],
    output_dir: Path,
    force: bool,
    dry_run: bool,
    retries: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    client = None
    for month in months:
        target = target_path(output_dir, years, month)
        request = build_request(years, month)
        if target.exists() and target.stat().st_size >= 4096 and not force:
            validate(target, years=years, month=month)
            print(f"exists: {target}", flush=True)
            continue
        if dry_run:
            print(json.dumps({"dataset": DATASET, "target": str(target), "request": request}, indent=2))
            continue
        if client is None:
            import cdsapi

            client = cdsapi.Client()
        partial = target.with_suffix(target.suffix + ".part")
        if partial.exists():
            partial.unlink()
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                print(f"request month={month:02d}, attempt={attempt}: {target}", flush=True)
                client.retrieve(DATASET, request, str(partial))
                validate(partial, years=years, month=month)
                partial.replace(target)
                print(f"complete: {target}", flush=True)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 - keep long downloads resumable.
                last_error = exc
                if partial.exists():
                    partial.unlink()
                if attempt < retries:
                    wait_seconds = min(10 * attempt, 30)
                    print(f"retry after CDS error: {exc}; waiting {wait_seconds}s", flush=True)
                    time.sleep(wait_seconds)
        if last_error is not None:
            raise RuntimeError(f"Failed ERA5 month {month:02d}") from last_error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(EVENT_YEARS))
    parser.add_argument("--months", nargs="+", type=int, default=list(MONTHS))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    months = sorted(set(args.months))
    if not years or not months or not set(months).issubset(MONTHS):
        raise ValueError("Years must be nonempty and months must be within 1-9")
    retrieve(
        years=years,
        months=months,
        output_dir=args.output_dir,
        force=args.force,
        dry_run=args.dry_run,
        retries=args.retries,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
