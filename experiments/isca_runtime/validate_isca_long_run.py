"""Validate a completed multi-month Isca experiment and write a JSON audit."""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

import numpy as np
import xarray as xr


REQUIRED_VARIABLES = (
    "t_surf",
    "precipitation",
    "olr",
    "u_10m",
    "v_10m",
    "flux_u",
    "ps",
)
EXPECTED_SIZES = {"lon": 128, "lat": 64, "pfull": 40}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def validate_month(path: Path) -> dict[str, object]:
    with xr.open_dataset(path, decode_times=False) as dataset:
        missing = sorted(set(REQUIRED_VARIABLES) - set(dataset.data_vars))
        if missing:
            raise ValueError(f"missing variables: {missing}")
        wrong_sizes = {
            name: {"expected": expected, "found": dataset.sizes.get(name)}
            for name, expected in EXPECTED_SIZES.items()
            if dataset.sizes.get(name) != expected
        }
        if wrong_sizes:
            raise ValueError(f"unexpected dimensions: {wrong_sizes}")
        ranges = {}
        for variable in REQUIRED_VARIABLES:
            field = dataset[variable]
            if not bool(np.isfinite(field).all()):
                raise ValueError(f"{variable} contains NaN or infinity")
            ranges[variable] = {
                "min": float(field.min()),
                "max": float(field.max()),
                "units": field.attrs.get("units", ""),
            }
        return {
            "bytes": path.stat().st_size,
            "sizes": {name: int(size) for name, size in dataset.sizes.items()},
            "ranges": ranges,
        }


def validate_restart(path: Path) -> dict[str, object]:
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
    required_members = ("./atmos_model.res", "./atmosphere.res.nc")
    missing = [name for name in required_members if name not in names]
    if missing:
        raise ValueError(f"restart archive is missing: {missing}")
    return {"bytes": path.stat().st_size, "members": len(names)}


def main() -> None:
    args = parse_args()
    errors: list[dict[str, object]] = []
    months: dict[str, object] = {}
    restarts: dict[str, object] = {}

    for month in range(1, args.months + 1):
        monthly_path = args.experiment / f"run{month:04d}" / "atmos_monthly.nc"
        restart_path = args.experiment / "restarts" / f"res{month:04d}.tar.gz"
        for kind, path, validator, target in (
            ("monthly", monthly_path, validate_month, months),
            ("restart", restart_path, validate_restart, restarts),
        ):
            key = str(path.relative_to(args.experiment))
            if not path.is_file() or path.stat().st_size == 0:
                errors.append({"kind": kind, "file": key, "error": "missing or empty"})
                continue
            try:
                target[key] = validator(path)
            except Exception as error:
                errors.append({"kind": kind, "file": key, "error": str(error)})

    audit = {
        "complete": not errors
        and len(months) == args.months
        and len(restarts) == args.months,
        "experiment": str(args.experiment),
        "expected_months": args.months,
        "valid_monthly_files": len(months),
        "valid_restarts": len(restarts),
        "errors": errors,
        "months": months,
        "restarts": restarts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not audit["complete"]:
        raise SystemExit(f"LONG_RUN_VALIDATION_FAILED see={args.output}")
    print(
        f"LONG_RUN_VALIDATION_COMPLETE months={len(months)} "
        f"restarts={len(restarts)} output={args.output}"
    )


if __name__ == "__main__":
    main()
