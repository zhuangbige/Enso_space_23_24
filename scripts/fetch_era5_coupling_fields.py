#!/usr/bin/env python3
"""Download monthly ERA5 fields for the minimal ENSO coupling closure.

The default Pacific domain is expressed in 0--360 longitude and is split at
the date line into two CDS requests.  Each request contains one calendar
month across all requested years, which keeps the batch resumable without
splitting variables that share a grid.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"
DATASET = "reanalysis-era5-single-levels-monthly-means"
VARIABLES = (
    "mean_eastward_turbulent_surface_stress",
    "mean_surface_net_short_wave_radiation_flux",
    "mean_surface_net_long_wave_radiation_flux",
    "mean_surface_latent_heat_flux",
    "mean_surface_sensible_heat_flux",
)


def _split_cds_areas(area: list[float]) -> list[tuple[str, list[float]]]:
    """Convert a user area to one or two CDS [N, W, S, E] areas.

    Longitudes may be supplied in either -180--180 or 0--360 notation.  A
    Pacific interval such as 120E--80W can therefore be written as
    ``[10, 120, -10, 280]`` or ``[10, 120, -10, -80]``.
    """

    if len(area) != 4:
        raise ValueError("area must contain north west south east")
    north, west, south, east = (float(value) for value in area)
    if north <= south:
        raise ValueError("area north must be greater than south")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("area latitudes must be within -90..90")

    if -180 <= west <= 180 and -180 <= east <= 180 and west <= east:
        return [("full", [north, west, south, east])]

    west360 = west % 360
    east360 = east % 360
    if east360 <= west360:
        east360 += 360
    span = east360 - west360
    if span <= 0 or span >= 360:
        raise ValueError("area longitude span must be between 0 and 360 degrees")

    boundaries = [west360]
    for boundary in (180.0, 360.0, 540.0):
        if west360 < boundary < east360:
            boundaries.append(boundary)
    boundaries.append(east360)

    pieces: list[tuple[str, list[float]]] = []
    for index, (left, right) in enumerate(zip(boundaries[:-1], boundaries[1:]), start=1):
        left_norm = left % 360
        right_norm = right % 360
        if left_norm == 180 and right > 180:
            cds_west = -180.0
        else:
            cds_west = left_norm if left_norm <= 180 else left_norm - 360
        if right_norm == 0 and right > left:
            cds_east = 180.0
        else:
            cds_east = right_norm if right_norm <= 180 else right_norm - 360
        if cds_east < cds_west:
            raise ValueError(f"failed to normalize longitude piece {left}..{right}")
        label = "full" if len(boundaries) == 2 else f"part{index:02d}"
        pieces.append((label, [north, cds_west, south, cds_east]))
    return pieces


def build_request(
    *,
    years: list[str],
    month: str,
    area: list[float],
    grid: float,
    variables: tuple[str, ...] | list[str] = VARIABLES,
) -> dict[str, object]:
    return {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": list(variables),
        "year": years,
        "month": [month],
        "time": ["00:00"],
        "area": area,
        "grid": [grid, grid],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def _target_path(
    output_dir: Path,
    *,
    area_label: str,
    month: str,
    start_year: int,
    end_year: int,
    grid: float,
) -> Path:
    grid_tag = str(grid).replace(".", "p")
    return output_dir / (
        f"era5_coupling_{area_label}_m{month}_{start_year}_{end_year}_{grid_tag}deg.nc"
    )


def _validate_download(
    path: Path, expected_years: int, expected_variables: int = len(VARIABLES)
) -> None:
    if not path.exists() or path.stat().st_size < 1024:
        raise RuntimeError(f"download is missing or too small: {path}")
    try:
        import xarray as xr
    except ModuleNotFoundError:
        return
    try:
        try:
            ds = xr.open_dataset(path, engine="netcdf4")
        except Exception:
            try:
                ds = xr.open_dataset(path, engine="h5netcdf")
            except Exception:
                ds = xr.open_dataset(path, engine="scipy")
        time_name = "valid_time" if "valid_time" in ds.dims else "time"
        if ds.sizes.get(time_name, 0) != expected_years:
            raise RuntimeError(
                f"unexpected time count in {path}: {ds.sizes.get(time_name, 0)} != {expected_years}"
            )
        if len(ds.data_vars) < expected_variables:
            raise RuntimeError(
                f"expected {expected_variables} fields in {path}, found {list(ds.data_vars)}"
            )
        ds.close()
    except Exception as exc:
        raise RuntimeError(f"download validation failed for {path}: {exc}") from exc


def retrieve(
    *,
    output_dir: Path,
    start_year: int,
    end_year: int,
    months: list[str],
    area: list[float],
    grid: float,
    dry_run: bool,
    force: bool,
    retries: int,
    variables: tuple[str, ...] | list[str] = VARIABLES,
) -> list[Path]:
    if start_year > end_year:
        raise ValueError("start-year must be <= end-year")
    years = [str(year) for year in range(start_year, end_year + 1)]
    areas = _split_cds_areas(area)
    output_dir.mkdir(parents=True, exist_ok=True)
    client = None
    outputs: list[Path] = []

    for month in months:
        if month not in {f"{value:02d}" for value in range(1, 13)}:
            raise ValueError(f"invalid month: {month}")
        for area_label, cds_area in areas:
            target = _target_path(
                output_dir,
                area_label=area_label,
                month=month,
                start_year=start_year,
                end_year=end_year,
                grid=grid,
            )
            outputs.append(target)
            request = build_request(
                years=years,
                month=month,
                area=cds_area,
                grid=grid,
                variables=variables,
            )
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
                    raise SystemExit(
                        "cdsapi is not installed. Install cdsapi>=0.7.7 and configure ~/.cdsapirc."
                    ) from exc
                client = cdsapi.Client()

            partial = target.with_suffix(target.suffix + ".part")
            if partial.exists():
                partial.unlink()
            last_error: Exception | None = None
            for attempt in range(1, retries + 1):
                try:
                    print(f"request month={month} area={cds_area} attempt={attempt}: {target}", flush=True)
                    client.retrieve(DATASET, request, str(partial))
                    _validate_download(partial, len(years), len(variables))
                    partial.replace(target)
                    print(target)
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - long batches must resume.
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
    parser = argparse.ArgumentParser(
        description="Download ERA5 monthly wind-stress and surface-flux fields for ENSO coupling."
    )
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--months",
        nargs="+",
        default=[f"{month:02d}" for month in range(1, 13)],
        help="Calendar months, for example --months 01 02 03.",
    )
    parser.add_argument(
        "--area",
        nargs=4,
        type=float,
        metavar=("NORTH", "WEST", "SOUTH", "EAST"),
        default=[10.0, 120.0, -10.0, 280.0],
        help="Domain in either -180..180 or 0..360 longitude notation.",
    )
    parser.add_argument("--grid", type=float, default=1.0)
    parser.add_argument(
        "--variables",
        nargs="+",
        default=list(VARIABLES),
        help="CDS variable names; defaults to zonal stress and four surface heat-flux components.",
    )
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
        months=[str(month).zfill(2) for month in args.months],
        area=list(args.area),
        grid=float(args.grid),
        dry_run=bool(args.dry_run),
        force=bool(args.force),
        retries=int(args.retries),
        variables=tuple(args.variables),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
