#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.validation import compare_yearly_series, write_series_comparison  # noqa: E402


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def correlation(rows: list[dict[str, float | int]]) -> float:
    source = [float(row["source"]) for row in rows]
    raw = [float(row["raw"]) for row in rows]
    source_mean = sum(source) / len(source)
    raw_mean = sum(raw) / len(raw)
    numerator = sum((a - source_mean) * (b - raw_mean) for a, b in zip(source, raw))
    denominator = math.sqrt(sum((a - source_mean) ** 2 for a in source) * sum((b - raw_mean) ** 2 for b in raw))
    return numerator / denominator


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare raw OISST Nino-3 reconstruction to Peng 2025 Fig. 1 data.")
    parser.add_argument("--fig1", type=Path, default=Path("data/derived/peng2025_repro/tables/fig1_event_coupling.csv"))
    parser.add_argument("--raw", type=Path, default=Path("data/derived/raw_validation/oisst_nino3_jun_jan.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/raw_validation/oisst_vs_fig1_nino3.csv"))
    args = parser.parse_args()

    rows = compare_yearly_series(
        source_rows=read_rows(args.fig1),
        raw_rows=read_rows(args.raw),
        source_year_key="year",
        source_value_key="nino3",
        raw_year_key="event_year",
        raw_value_key="nino3_jun_jan_anomaly",
    )
    write_series_comparison(rows, args.output)
    highlighted = {1982, 1997, 2015, 2023}
    print(args.output)
    print(f"correlation={correlation(rows):.4f}")
    for row in rows:
        if row["year"] in highlighted:
            print(
                f"{row['year']}: fig1={row['source']:.3f}, "
                f"oisst={row['raw']:.3f}, diff={row['difference_raw_minus_source']:.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
