#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.catalog import list_datasets


def main() -> int:
    parser = argparse.ArgumentParser(description="List data sources for the 2023/24 El Nino decoupling study.")
    parser.add_argument("--priority", choices=("core", "expansion", "paper"), help="Filter by dataset priority.")
    parser.add_argument("--format", choices=("markdown", "csv"), default="markdown", help="Output format.")
    args = parser.parse_args()

    datasets = list_datasets(priority=args.priority)
    if args.format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["id", "name", "priority", "coverage", "resolution", "variables", "official_url", "research_use"])
        for dataset in datasets:
            writer.writerow(
                [
                    dataset.id,
                    dataset.name,
                    dataset.priority,
                    dataset.temporal_coverage,
                    dataset.resolution,
                    ";".join(dataset.variables),
                    dataset.official_url,
                    dataset.research_use,
                ]
            )
        return 0

    print("| ID | Dataset | Priority | Coverage | Research use |")
    print("|---|---|---|---|---|")
    for dataset in datasets:
        print(
            f"| `{dataset.id}` | [{dataset.name}]({dataset.official_url}) | "
            f"{dataset.priority} | {dataset.temporal_coverage} | {dataset.research_use} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
