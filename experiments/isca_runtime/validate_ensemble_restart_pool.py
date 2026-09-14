"""Validate the decorrelated restart pool used by the paired P0 ensemble."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

import numpy as np
import xarray as xr


REQUIRED_POOL_VARIABLES = ("ps", "temp", "ucomp", "vcomp", "precipitation")
EXPECTED_SIZES = {"lon": 128, "lat": 64, "pfull": 40}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--members", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_restart(path: Path) -> dict[str, object]:
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
        required = ("./atmos_model.res", "./atmosphere.res.nc")
        missing = [name for name in required if name not in names]
        if missing:
            raise ValueError(f"restart archive is missing: {missing}")
        state_handle = archive.extractfile("./atmosphere.res.nc")
        if state_handle is None:
            raise ValueError("cannot read atmosphere.res.nc from restart archive")
        state_digest = hashlib.sha256()
        for block in iter(lambda: state_handle.read(1024 * 1024), b""):
            state_digest.update(block)
    return {
        "bytes": path.stat().st_size,
        "archive_sha256": sha256(path),
        "state_sha256": state_digest.hexdigest(),
        "archive_members": len(names),
    }


def validate_monthly(path: Path) -> dict[str, object]:
    with xr.open_dataset(path, decode_times=False) as dataset:
        missing = sorted(set(REQUIRED_POOL_VARIABLES) - set(dataset.data_vars))
        if missing:
            raise ValueError(f"missing variables: {missing}")
        wrong_sizes = {
            name: {"expected": expected, "found": dataset.sizes.get(name)}
            for name, expected in EXPECTED_SIZES.items()
            if dataset.sizes.get(name) != expected
        }
        if wrong_sizes:
            raise ValueError(f"unexpected dimensions: {wrong_sizes}")
        fingerprint = {}
        for variable in REQUIRED_POOL_VARIABLES:
            field = dataset[variable]
            if not bool(np.isfinite(field).all()):
                raise ValueError(f"{variable} contains NaN or infinity")
            fingerprint[variable] = {
                "mean": float(field.mean()),
                "std": float(field.std()),
                "min": float(field.min()),
                "max": float(field.max()),
                "units": field.attrs.get("units", ""),
            }
        return {"bytes": path.stat().st_size, "fingerprint": fingerprint}


def main() -> None:
    args = parse_args()
    records: dict[str, object] = {}
    errors: list[dict[str, object]] = []

    for member in range(1, args.members + 1):
        restart = args.experiment / "restarts" / f"res{member:04d}.tar.gz"
        monthly = args.experiment / f"run{member:04d}" / "pool_monthly.nc"
        current: dict[str, object] = {"member": member}
        for kind, path, validator in (
            ("restart", restart, validate_restart),
            ("monthly", monthly, validate_monthly),
        ):
            relative = str(path.relative_to(args.experiment))
            if not path.is_file() or path.stat().st_size == 0:
                errors.append({"member": member, "kind": kind, "file": relative, "error": "missing or empty"})
                continue
            try:
                current[kind] = validator(path)
            except Exception as error:
                errors.append({"member": member, "kind": kind, "file": relative, "error": str(error)})
        records[f"member_{member:02d}"] = current

    state_hashes = [
        record["restart"]["state_sha256"]
        for record in records.values()
        if "restart" in record
    ]
    states_unique = (
        len(state_hashes) == args.members
        and len(set(state_hashes)) == args.members
    )
    if not states_unique:
        errors.append(
            {
                "kind": "restart_state_uniqueness",
                "error": (
                    f"expected {args.members} unique atmosphere.res.nc states, "
                    f"found {len(set(state_hashes))}"
                ),
            }
        )
    complete = (
        not errors
        and len(records) == args.members
        and all("restart" in record and "monthly" in record for record in records.values())
        and states_unique
    )
    audit = {
        "complete": complete,
        "expected_members": args.members,
        "valid_restart_state_hashes": len(state_hashes),
        "unique_restart_state_hashes": len(set(state_hashes)),
        "errors": errors,
        "members": records,
        "design_note": (
            "Consecutive monthly control states are relabelled to the common March start. "
            "All four SST cases use the same restart for a given member, so factorial "
            "contrasts are paired; MJJ is the primary response window."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if not complete:
        raise SystemExit(f"ENSEMBLE_POOL_VALIDATION_FAILED see={args.output}")
    print(
        f"ENSEMBLE_POOL_VALIDATION_COMPLETE members={args.members} "
        f"unique_state_hashes={len(set(state_hashes))} output={args.output}"
    )


if __name__ == "__main__":
    main()
