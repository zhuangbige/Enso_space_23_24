#!/usr/bin/env python3
"""Download ERA5 monthly 10 m wind for the Peng et al. (2025) CWP box.

Peng et al. define the central-western Pacific (CWP) wind response as
5S--5N, 140E--160W.  The box crosses the date line, so each calendar-month
request is split into 140E--180 and 180--160W pieces.  Files are deliberately
kept month-specific and resumable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data/raw/era5/peng_cwp_u10_monthly_1deg"
DATASET = "reanalysis-era5-single-levels-monthly-means"
VARIABLES = ("10m_u_component_of_wind",)
AREAS = (
    ("part01", [5.0, 140.0, -5.0, 180.0]),
    ("part02", [5.0, -180.0, -5.0, -160.0]),
)


def build_request(*, years: list[str], month: str, area: list[float], grid: float) -> dict[str, object]:
    return {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": list(VARIABLES),
        "year": years,
        "month": [month],
        "time": ["00:00"],
        "area": area,
        "grid": [grid, grid],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def target_path(
    output_dir: Path,
    *,
    area_label: str,
    month: str,
    start_year: int,
    end_year: int,
    grid: float,
) -> Path:
    grid_tag = str(grid).replace(".", "p")
    return output_dir / f"era5_peng_cwp_{area_label}_m{month}_{start_year}_{end_year}_{grid_tag}deg.nc"


def validate_download(path: Path, *, expected_years: int) -> None:
    if not path.exists() or path.stat().st_size < 1024:
        raise RuntimeError(f"download is missing or too small: {path}")
    try:
        import xarray as xr
    except ModuleNotFoundError:
        return
    try:
        dataset = xr.open_dataset(path, engine="h5netcdf")
        time_name = "valid_time" if "valid_time" in dataset.dims else "time"
        if dataset.sizes.get(time_name, 0) != expected_years:
            raise RuntimeError(
                f"unexpected time count in {path}: {dataset.sizes.get(time_name, 0)} != {expected_years}"
            )
        missing = {"u10"}.difference(dataset.data_vars)
        if missing:
            raise RuntimeError(f"missing ERA5 variables in {path}: {sorted(missing)}")
        dataset.close()
    except Exception as exc:
        raise RuntimeError(f"download validation failed for {path}: {exc}") from exc


def retrieve(
    *,
    output_dir: Path,
    start_year: int,
    end_year: int,
    months: list[str],
    parts: list[str],
    grid: float,
    dry_run: bool,
    force: bool,
    retries: int,
) -> list[Path]:
    if start_year > end_year:
        raise ValueError("start-year must be <= end-year")
    valid_months = {f"{month:02d}" for month in range(1, 13)}
    normalized_months = [str(month).zfill(2) for month in months]
    invalid = sorted(set(normalized_months).difference(valid_months))
    if invalid:
        raise ValueError(f"invalid months: {invalid}")
    valid_parts = {label for label, _ in AREAS}
    invalid_parts = sorted(set(parts).difference(valid_parts))
    if invalid_parts:
        raise ValueError(f"invalid parts: {invalid_parts}")
    selected_areas = [(label, area) for label, area in AREAS if label in parts]

    years = [str(year) for year in range(start_year, end_year + 1)]
    output_dir.mkdir(parents=True, exist_ok=True)
    client = None
    outputs: list[Path] = []
    for month in normalized_months:
        for area_label, area in selected_areas:
            target = target_path(
                output_dir,
                area_label=area_label,
                month=month,
                start_year=start_year,
                end_year=end_year,
                grid=grid,
            )
            outputs.append(target)
            request = build_request(years=years, month=month, area=area, grid=grid)
            if target.exists() and target.stat().st_size >= 1024 and not force:
                print(f"exists: {target}")
                continue
            if dry_run:
                print(json.dumps({"dataset": DATASET, "target": str(target), "request": request}, indent=2))
                continue

            if client is None:
                try:
                    import cdsapi
                except ModuleNotFoundError as exc:
                    raise SystemExit("cdsapi is not installed; install cdsapi>=0.7.7 and configure ~/.cdsapirc") from exc
                client = cdsapi.Client()

            partial = target.with_suffix(target.suffix + ".part")
            if partial.exists():
                partial.unlink()
            last_error: Exception | None = None
            for attempt in range(1, retries + 1):
                try:
                    print(f"request month={month} area={area} attempt={attempt}: {target}", flush=True)
                    client.retrieve(DATASET, request, str(partial))
                    validate_download(partial, expected_years=len(years))
                    partial.replace(target)
                    print(target)
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - make long CDS batches resumable.
                    last_error = exc
                    if partial.exists():
                        partial.unlink()
                    if attempt < retries:
                        wait_seconds = min(10 * attempt, 30)
                        print(f"retry after CDS error: {exc}; waiting {wait_seconds}s", flush=True)
                        time.sleep(wait_seconds)
            if last_error is not None:
                raise RuntimeError(f"failed to download {target}") from last_error
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--months", nargs="+", default=["01", "02", "03", "04", "05", "06"])
    parser.add_argument(
        "--parts",
        nargs="+",
        choices=[label for label, _ in AREAS],
        default=[label for label, _ in AREAS],
        help="Dateline-split regions to retrieve (default: both).",
    )
    parser.add_argument("--grid", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    retrieve(
        output_dir=args.output_dir,
        start_year=args.start_year,
        end_year=args.end_year,
        months=list(args.months),
        parts=list(args.parts),
        grid=float(args.grid),
        dry_run=bool(args.dry_run),
        force=bool(args.force),
        retries=int(args.retries),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
