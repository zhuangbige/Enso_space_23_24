#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.analysis import response_strength_ratio  # noqa: E402


SEASON_ORDER = {"AMJ": 0, "JJA": 1, "SON": 2, "DJF": 3, "feb_may": 0, "jun_dec": 2, "jan_apr_next": 4}
ATMOSPHERIC_METRICS = {
    "cwp_u_ncep_sig995": {"use_absolute": False, "expected_response": "positive wind response"},
    "soi_like_ncep": {"use_absolute": True, "expected_response": "negative pressure-gradient response"},
    "gpcp_precip_central_pacific_180_140w": {"use_absolute": False, "expected_response": "positive central-Pacific rainfall response"},
    "gpcp_precip_eastern_pacific_140w_100w": {"use_absolute": False, "expected_response": "positive eastern-Pacific rainfall response"},
    "gpcp_precip_full_tropical_pacific_120e_80w": {"use_absolute": False, "expected_response": "positive basin rainfall response"},
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _as_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def _lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["metric"], row["season"]): row for row in rows}


def _seasonal_nino_ratio(lookup: dict[tuple[str, str], dict[str, str]], season: str) -> float | None:
    row = lookup.get(("nino3_sst_oisst", season))
    if not row:
        return None
    return response_strength_ratio(_as_float(row, "value_2023"), _as_float(row, "value_comparable"))


def _coupling_deficit(metric: str, row: dict[str, str]) -> float:
    difference = _as_float(row, "difference_2023_minus_comparable")
    if metric == "soi_like_ncep":
        return -difference
    return difference


def build_efficiency_rows(seasonal_path: Path) -> list[dict[str, float | str | None]]:
    rows = read_rows(seasonal_path)
    lookup = _lookup(rows)
    output = []
    for row in rows:
        metric = row["metric"]
        if metric not in ATMOSPHERIC_METRICS:
            continue
        season = row["season"]
        nino_ratio = _seasonal_nino_ratio(lookup, season)
        atmosphere_ratio = response_strength_ratio(
            _as_float(row, "value_2023"),
            _as_float(row, "value_comparable"),
            use_absolute=ATMOSPHERIC_METRICS[metric]["use_absolute"],
        )
        efficiency = None
        if nino_ratio not in (None, 0) and atmosphere_ratio is not None:
            efficiency = atmosphere_ratio / nino_ratio
        deficit = _coupling_deficit(metric, row)
        output.append(
            {
                "metric": metric,
                "season": season,
                "value_2023": _as_float(row, "value_2023"),
                "value_comparable": _as_float(row, "value_comparable"),
                "difference_2023_minus_comparable": _as_float(row, "difference_2023_minus_comparable"),
                "nino3_strength_ratio": nino_ratio,
                "atmospheric_response_ratio": atmosphere_ratio,
                "atmosphere_to_sst_efficiency": efficiency,
                "coupling_deficit": deficit,
                "expected_response": ATMOSPHERIC_METRICS[metric]["expected_response"],
            }
        )
    return sorted(output, key=lambda row: (row["metric"], SEASON_ORDER.get(str(row["season"]), 99)))


def build_phase_rows(efficiency_rows: list[dict[str, float | str | None]]) -> list[dict[str, float | str | None]]:
    output = []
    by_metric: dict[str, list[dict[str, float | str | None]]] = {}
    for row in efficiency_rows:
        by_metric.setdefault(str(row["metric"]), []).append(row)

    for metric, rows in sorted(by_metric.items()):
        season_rows = sorted(rows, key=lambda row: SEASON_ORDER.get(str(row["season"]), 99))
        deficits = [row for row in season_rows if float(row["coupling_deficit"]) < 0]
        if not deficits:
            first = None
            largest = None
        else:
            first = deficits[0]
            largest = min(deficits, key=lambda row: float(row["coupling_deficit"]))
        output.append(
            {
                "metric": metric,
                "first_deficit_window": first["season"] if first else "",
                "largest_deficit_window": largest["season"] if largest else "",
                "largest_deficit_value": largest["coupling_deficit"] if largest else "",
                "minimum_efficiency": min(
                    (
                        float(row["atmosphere_to_sst_efficiency"])
                        for row in season_rows
                        if row.get("atmosphere_to_sst_efficiency") is not None
                    ),
                    default="",
                ),
            }
        )
    return output


def write_rows(path: Path, rows: list[dict[str, float | str | None]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build seasonal asynchronous coupling diagnostics.")
    parser.add_argument("--seasonal", type=Path, default=Path("data/derived/research/seasonal_decoupling_first_pass.csv"))
    parser.add_argument("--efficiency-output", type=Path, default=Path("data/derived/research/asynchronous_coupling_efficiency.csv"))
    parser.add_argument("--phase-output", type=Path, default=Path("data/derived/research/asynchronous_coupling_phase_summary.csv"))
    args = parser.parse_args()

    efficiency_rows = build_efficiency_rows(args.seasonal)
    write_rows(
        args.efficiency_output,
        efficiency_rows,
        [
            "metric",
            "season",
            "value_2023",
            "value_comparable",
            "difference_2023_minus_comparable",
            "nino3_strength_ratio",
            "atmospheric_response_ratio",
            "atmosphere_to_sst_efficiency",
            "coupling_deficit",
            "expected_response",
        ],
    )
    phase_rows = build_phase_rows(efficiency_rows)
    write_rows(
        args.phase_output,
        phase_rows,
        ["metric", "first_deficit_window", "largest_deficit_window", "largest_deficit_value", "minimum_efficiency"],
    )
    print(args.efficiency_output)
    print(args.phase_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
