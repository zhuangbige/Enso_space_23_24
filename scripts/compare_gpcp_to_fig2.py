#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare raw GPCP precipitation summaries to Fig. 2 precipitation summaries.")
    parser.add_argument("--fig2", type=Path, default=Path("data/derived/peng2025_repro/tables/fig2_equatorial_summary.csv"))
    parser.add_argument("--gpcp", type=Path, default=Path("data/derived/raw_validation/gpcp_equatorial_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/raw_validation/gpcp_vs_fig2_precip.csv"))
    args = parser.parse_args()

    fig2 = [
        row for row in read_rows(args.fig2)
        if row["metric"] == "precip"
    ]
    gpcp_rows = read_rows(args.gpcp)
    gpcp_lookup = {
        (row["case"], row["region"], row["window"]): float(row["precip_anomaly"])
        for row in gpcp_rows
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "region",
                "window",
                "fig2_2023",
                "fig2_comparable",
                "fig2_difference_2023_minus_comparable",
                "gpcp_2023",
                "gpcp_comparable",
                "gpcp_difference_2023_minus_comparable",
            ]
        )
        for row in fig2:
            region = row["region"]
            window = row["window"]
            gpcp_2023 = gpcp_lookup[("2023", region, window)]
            gpcp_comparable = gpcp_lookup[("comparable", region, window)]
            writer.writerow(
                [
                    region,
                    window,
                    row["value_2023"],
                    row["value_comparable"],
                    row["difference_2023_minus_comparable"],
                    gpcp_2023,
                    gpcp_comparable,
                    gpcp_2023 - gpcp_comparable,
                ]
            )
    print(args.output)
    for row in read_rows(args.output):
        if row["region"] == "central_pacific_180_140w" and row["window"] == "jun_dec":
            print(
                "central Pacific Jun-Dec: "
                f"fig2_diff={float(row['fig2_difference_2023_minus_comparable']):.3f}, "
                f"gpcp_diff={float(row['gpcp_difference_2023_minus_comparable']):.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
