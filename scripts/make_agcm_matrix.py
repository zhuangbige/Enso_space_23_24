#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.experiments import build_agcm_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit the AGCM experiment matrix for the decoupling attribution study.")
    parser.add_argument("--include-optional", action="store_true", help="Include optional TNA and ISM/MC heating tests.")
    parser.add_argument("--format", choices=("markdown", "csv"), default="markdown", help="Output format.")
    args = parser.parse_args()

    experiments = build_agcm_matrix(include_optional=args.include_optional)
    if args.format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["id", "name", "sst_forcing", "purpose", "expected_signal", "optional"])
        for experiment in experiments:
            writer.writerow(
                [
                    experiment.id,
                    experiment.name,
                    experiment.sst_forcing,
                    experiment.purpose,
                    experiment.expected_signal,
                    experiment.optional,
                ]
            )
        return 0

    print("| ID | Experiment | SST forcing | Purpose |")
    print("|---|---|---|---|")
    for experiment in experiments:
        optional = " Optional." if experiment.optional else ""
        print(f"| `{experiment.id}` | {experiment.name}{optional} | {experiment.sst_forcing} | {experiment.purpose} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
