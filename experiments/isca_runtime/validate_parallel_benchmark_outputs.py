"""Validate all six one-month concurrency benchmark outputs before P0 launch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_and_summarize_p0 import inspect_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for index in range(1, args.jobs + 1):
        member = 89 + index
        path = (
            args.data
            / f"isca_2023_ia0_fep0_m{member:02d}_t42"
            / "run0001"
            / "atmos_monthly.nc"
        )
        if not path.is_file() or path.stat().st_size == 0:
            errors.append({"member": member, "file": str(path), "error": "missing or empty"})
            continue
        try:
            metrics, metadata = inspect_file(path)
        except Exception as error:
            errors.append({"member": member, "file": str(path), "error": str(error)})
            continue
        records.append(
            {
                "member": member,
                "file": str(path),
                "bytes": path.stat().st_size,
                "metrics": metrics,
                "metadata": metadata,
            }
        )

    complete = len(records) == args.jobs and not errors
    audit = {
        "complete": complete,
        "expected_jobs": args.jobs,
        "valid_jobs": len(records),
        "errors": errors,
        "jobs": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if not complete:
        raise SystemExit(f"PARALLEL_OUTPUT_VALIDATION_FAILED see={args.output}")
    print(f"PARALLEL_OUTPUT_VALIDATION_COMPLETE jobs={args.jobs} output={args.output}")


if __name__ == "__main__":
    main()
