"""Validate dates, state uniqueness, and final monthly files for March pool."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from pathlib import Path

from validate_ensemble_restart_pool import validate_monthly, validate_restart


EXPECTED_DATE = (2023, 3, 1, 0, 0, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--members", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def restart_date(path: Path) -> tuple[int, ...]:
    with tarfile.open(path, "r:gz") as archive:
        handle = archive.extractfile("./atmos_model.res")
        if handle is None:
            raise ValueError("cannot read atmos_model.res")
        first = handle.readline().decode("ascii")
    values = tuple(int(value) for value in re.findall(r"\d+", first)[:6])
    if len(values) != 6:
        raise ValueError(f"cannot parse restart date from {first!r}")
    return values


def main() -> None:
    args = parse_args()
    pool = args.data / "isca_control_march_pool_t42"
    records: dict[str, object] = {}
    errors: list[dict[str, object]] = []
    state_hashes: list[str] = []

    for member in range(1, args.members + 1):
        restart = pool / "restarts" / f"res{member:04d}.tar.gz"
        monthly = (
            args.data
            / f"isca_control_march_pool_m{member:02d}_t42"
            / "run0003"
            / "pool_monthly.nc"
        )
        current: dict[str, object] = {"member": member}
        try:
            if not restart.is_file() or restart.stat().st_size == 0:
                raise ValueError("missing or empty restart")
            restart_record = validate_restart(restart)
            date = restart_date(restart)
            if date != EXPECTED_DATE:
                raise ValueError(f"expected date {EXPECTED_DATE}, found {date}")
            restart_record["model_date"] = date
            current["restart"] = restart_record
            state_hashes.append(str(restart_record["state_sha256"]))
        except Exception as error:
            errors.append({"member": member, "kind": "restart", "error": str(error)})
        try:
            if not monthly.is_file() or monthly.stat().st_size == 0:
                raise ValueError("missing or empty final monthly output")
            current["monthly"] = validate_monthly(monthly)
        except Exception as error:
            errors.append({"member": member, "kind": "monthly", "error": str(error)})
        records[f"member_{member:02d}"] = current

    states_unique = (
        len(state_hashes) == args.members
        and len(set(state_hashes)) == args.members
    )
    if not states_unique:
        errors.append(
            {
                "kind": "restart_state_uniqueness",
                "error": f"expected {args.members} unique states, found {len(set(state_hashes))}",
            }
        )
    complete = not errors and states_unique and len(records) == args.members
    audit = {
        "complete": complete,
        "expected_members": args.members,
        "expected_model_date": EXPECTED_DATE,
        "valid_state_hashes": len(state_hashes),
        "unique_state_hashes": len(set(state_hashes)),
        "errors": errors,
        "members": records,
        "design_note": (
            "Independent monthly seeds were relabelled to 2022-12-01 and each "
            "integrated through the same December-February climatological SST/ice. "
            "All retained restarts are genuine 2023-03-01 states."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if not complete:
        raise SystemExit(f"MARCH_POOL_VALIDATION_FAILED see={args.output}")
    print(
        f"MARCH_POOL_VALIDATION_COMPLETE members={args.members} "
        f"unique_states={len(set(state_hashes))} output={args.output}"
    )


if __name__ == "__main__":
    main()
