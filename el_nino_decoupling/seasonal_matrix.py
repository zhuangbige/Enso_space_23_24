"""Seasonal coupling matrix utilities for the 2023/24 El Nino analysis."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def ratio_to_comparable(value_2023: float, value_comparable: float) -> float | None:
    """Return 2023/comparable ratio, preserving signs for response variables."""
    if value_comparable == 0:
        return None
    return value_2023 / value_comparable


def response_efficiency(
    response_ratio: float | None, sst_ratio: float | None
) -> float | None:
    """Normalize an atmospheric response ratio by same-season Pacific SST strength."""
    if response_ratio is None or sst_ratio in (None, 0):
        return None
    return response_ratio / sst_ratio


def build_matrix_records(
    rows: Iterable[dict[str, Any]],
    *,
    sst_metric: str = "nino3_sst",
) -> list[dict[str, Any]]:
    """Build season-variable matrix records with ratios and response efficiency."""
    base_rows = list(rows)
    sst_ratio_by_season: dict[str, float | None] = {}
    records: list[dict[str, Any]] = []

    for row in base_rows:
        ratio = ratio_to_comparable(
            float(row["value_2023"]), float(row["value_comparable"])
        )
        if row["metric"] == sst_metric:
            sst_ratio_by_season[str(row["season"])] = ratio

    for row in base_rows:
        season = str(row["season"])
        metric = str(row["metric"])
        ratio = ratio_to_comparable(
            float(row["value_2023"]), float(row["value_comparable"])
        )
        sst_ratio = sst_ratio_by_season.get(season)
        records.append(
            {
                "season": season,
                "metric": metric,
                "value_2023": float(row["value_2023"]),
                "value_comparable": float(row["value_comparable"]),
                "difference_2023_minus_comparable": float(row["value_2023"])
                - float(row["value_comparable"]),
                "ratio_to_comparable": ratio,
                "response_efficiency": 1.0
                if metric == sst_metric
                else response_efficiency(ratio, sst_ratio),
                "source_ids": str(row.get("source_ids", "")),
            }
        )
    return records
