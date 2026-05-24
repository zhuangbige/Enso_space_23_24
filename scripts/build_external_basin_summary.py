#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.raw_indices import seasonal_mean_by_months  # noqa: E402


SEASONS = {
    "AMJ": (4, 5, 6),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
    "DJF": (12, 13, 14),
}

COMPARABLE_YEARS = (1982, 1997, 2015)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def build_summary_rows(monthly_path: Path) -> list[dict[str, float | str]]:
    raw_rows = read_rows(monthly_path)
    regions = sorted({row["region"] for row in raw_rows})
    output = []
    for region in regions:
        records = [
            {"year": int(row["year"]), "month": int(row["month"]), "anomaly": float(row["anomaly"])}
            for row in raw_rows
            if row["region"] == region
        ]
        for season, months in SEASONS.items():
            try:
                value_2023 = seasonal_mean_by_months(records, 2023, months)
                comparable = mean([seasonal_mean_by_months(records, year, months) for year in COMPARABLE_YEARS])
            except KeyError:
                continue
            output.append(
                {
                    "region": region,
                    "season": season,
                    "value_2023": value_2023,
                    "value_comparable": comparable,
                    "difference_2023_minus_comparable": value_2023 - comparable,
                }
            )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build seasonal external-basin SST summary from monthly OISST indices.")
    parser.add_argument("--monthly", type=Path, default=Path("data/interim/raw_validation/oisst_external_basin_monthly.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/research/external_basin_seasonal_summary.csv"))
    args = parser.parse_args()

    rows = build_summary_rows(args.monthly)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["region", "season", "value_2023", "value_comparable", "difference_2023_minus_comparable"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)
    if not rows:
        print("No rows written. The monthly input probably does not yet include 2023 and comparable years for all seasons.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
