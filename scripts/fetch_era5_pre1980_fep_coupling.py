#!/usr/bin/env python3
"""Fetch compact ERA5 MJJ fields used to compare Jiang FEP-dominant events.

The request follows Jiang et al. (2026): monthly ERA5 fields over 1960--2024.
Only May--July, 15S--15N, and a 1-degree grid are retrieved.  Pressure-level
and single-level fields are kept in separate requests because they live in
different CDS datasets/grids.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile, is_zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "era5" / "pre1980_fep_mjj_1deg"
YEARS = [str(year) for year in range(1960, 2025)]
MONTHS = ["05", "06", "07"]
AREA = [15, -180, -15, 180]
GRID = [1.0, 1.0]


REQUESTS = {
    "pressure925": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "variables": ["u_component_of_wind", "v_component_of_wind"],
        "extra": {"pressure_level": ["925"]},
    },
    "surface": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "variables": [
            "total_precipitation",
            "mean_sea_level_pressure",
            "mean_eastward_turbulent_surface_stress",
        ],
        "extra": {},
    },
}


def build_request(kind: str, month: str) -> dict[str, object]:
    cfg = REQUESTS[kind]
    request: dict[str, object] = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": cfg["variables"],
        "year": YEARS,
        "month": [month],
        "time": ["00:00"],
        "area": AREA,
        "grid": GRID,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    request.update(cfg["extra"])
    return request


def _validate_netcdf(path: Path, expected_vars: int) -> set[str]:
    import xarray as xr

    if not path.exists() or path.stat().st_size < 1024:
        raise RuntimeError(f"missing or too-small download: {path}")
    errors = []
    for engine in ("h5netcdf", "scipy"):
        try:
            ds = xr.open_dataset(path, engine=engine)
            time_name = "valid_time" if "valid_time" in ds.dims else "time"
            if ds.sizes.get(time_name, 0) != len(YEARS):
                raise RuntimeError(
                    f"unexpected time count {ds.sizes.get(time_name, 0)} != {len(YEARS)}"
                )
            if len(ds.data_vars) < expected_vars:
                raise RuntimeError(
                    f"expected at least {expected_vars} variables, found {list(ds.data_vars)}"
                )
            variables = set(ds.data_vars)
            print(
                f"validated {path.name}: engine={engine}, dims={dict(ds.sizes)}, "
                f"vars={list(ds.data_vars)}"
            )
            ds.close()
            return variables
        except Exception as exc:  # pragma: no cover - depends on local engines
            errors.append(f"{engine}: {exc}")
    raise RuntimeError("; ".join(errors))


def validate(path: Path, expected_vars: int) -> None:
    if is_zipfile(path):
        extract_dir = path.with_suffix("")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with ZipFile(path) as archive:
            archive.extractall(extract_dir)
        files = sorted(extract_dir.glob("*.nc"))
        if not files:
            raise RuntimeError(f"zip archive contains no NetCDF files: {path}")
        found: set[str] = set()
        for file in files:
            found.update(_validate_netcdf(file, 1))
        # CDS may add scalar metadata variables, so require at least the
        # requested physical fields across all step-type files.
        if len(found) < expected_vars:
            raise RuntimeError(
                f"expected at least {expected_vars} variables across {path}, found {sorted(found)}"
            )
        return
    _validate_netcdf(path, expected_vars)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    client = None
    for month in MONTHS:
        for kind, cfg in REQUESTS.items():
            suffix = ".zip" if kind == "surface" else ".nc"
            target = OUT / f"era5_{kind}_m{month}_1960_2024_1deg{suffix}"
            request = build_request(kind, month)
            if args.dry_run:
                print(
                    json.dumps(
                        {"dataset": cfg["dataset"], "request": request, "target": str(target)},
                        indent=2,
                    )
                )
                continue
            if target.exists() and target.stat().st_size >= 1024 and not args.force:
                validate(target, len(cfg["variables"]))
                continue
            if client is None:
                import cdsapi

                client = cdsapi.Client()
            tmp = target.with_suffix(target.suffix + ".part")
            if tmp.exists():
                tmp.unlink()
            print(f"retrieving {cfg['dataset']} month={month} -> {target}", flush=True)
            client.retrieve(cfg["dataset"], request, str(tmp))
            tmp.replace(target)
            validate(target, len(cfg["variables"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
