from __future__ import annotations

import csv
from pathlib import Path


def compare_yearly_series(
    source_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    source_year_key: str,
    source_value_key: str,
    raw_year_key: str,
    raw_value_key: str,
) -> list[dict[str, float | int]]:
    raw_lookup = {int(row[raw_year_key]): float(row[raw_value_key]) for row in raw_rows}
    output = []
    for row in source_rows:
        year = int(row[source_year_key])
        if year not in raw_lookup:
            continue
        source_value = float(row[source_value_key])
        raw_value = raw_lookup[year]
        output.append(
            {
                "year": year,
                "source": source_value,
                "raw": raw_value,
                "difference_raw_minus_source": raw_value - source_value,
            }
        )
    return output


def write_series_comparison(rows: list[dict[str, float | int]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["year", "source", "raw", "difference_raw_minus_source"])
        writer.writeheader()
        writer.writerows(rows)
