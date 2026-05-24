"""Build the seasonal asynchronous-coupling matrix from derived diagnostics."""

from __future__ import annotations

import csv
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.seasonal_matrix import build_matrix_records


ROOT = Path(__file__).resolve().parents[1]
SEASONAL = ROOT / "data/derived/research/seasonal_decoupling_first_pass.csv"
EXTERNAL = ROOT / "data/derived/research/external_basin_seasonal_summary.csv"
GPCP = ROOT / "data/derived/research/gpcp_precip_seasonal_summary.csv"
OLR = ROOT / "data/derived/research/olr_seasonal_summary.csv"
ERA5 = ROOT / "data/derived/research/era5_seasonal_summary.csv"
OUT = ROOT / "data/derived/research/seasonal_asynchrony_matrix.csv"
FOUR_SEASONS = {"AMJ", "JJA", "SON", "DJF"}
METRIC_NAMES = {
    "nino3_sst_oisst": "nino3_sst",
    "cwp_u_ncep_sig995": "cwp_u",
    "soi_like_ncep": "soi_like",
}
SOURCE_IDS = {
    "nino3_sst": "D2",
    "cwp_u": "D4",
    "soi_like": "D4",
}


def _require_columns(df: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = columns - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")


def load_rows() -> list[dict[str, object]]:
    seasonal_df = pd.read_csv(SEASONAL)
    external_df = pd.read_csv(EXTERNAL)
    gpcp_df = pd.read_csv(GPCP) if GPCP.exists() else pd.DataFrame()
    olr_df = pd.read_csv(OLR) if OLR.exists() else pd.DataFrame()
    era5_df = pd.read_csv(ERA5) if ERA5.exists() else pd.DataFrame()
    _require_columns(
        seasonal_df, {"season", "metric", "value_2023", "value_comparable"}, SEASONAL
    )
    _require_columns(
        external_df, {"season", "region", "value_2023", "value_comparable"}, EXTERNAL
    )
    if not gpcp_df.empty:
        _require_columns(
            gpcp_df, {"season", "region", "value_2023", "value_comparable"}, GPCP
        )
    if not olr_df.empty:
        _require_columns(
            olr_df, {"season", "region", "value_2023", "value_comparable"}, OLR
        )
    if not era5_df.empty:
        _require_columns(
            era5_df, {"season", "metric", "value_2023", "value_comparable", "source_ids"}, ERA5
        )

    rows: list[dict[str, object]] = []
    for row in seasonal_df.to_dict("records"):
        if row["season"] not in FOUR_SEASONS or row["metric"] not in METRIC_NAMES:
            continue
        metric = METRIC_NAMES[str(row["metric"])]
        rows.append(
            {
                "season": row["season"],
                "metric": metric,
                "value_2023": row["value_2023"],
                "value_comparable": row["value_comparable"],
                "source_ids": SOURCE_IDS[metric],
            }
        )

    for row in external_df.to_dict("records"):
        if row["season"] not in FOUR_SEASONS:
            continue
        rows.append(
            {
                "season": row["season"],
                "metric": f"sst_{row['region']}",
                "value_2023": row["value_2023"],
                "value_comparable": row["value_comparable"],
                "source_ids": "D2",
            }
        )
    for row in gpcp_df.to_dict("records"):
        if row["season"] not in FOUR_SEASONS:
            continue
        rows.append(
            {
                "season": row["season"],
                "metric": f"precip_{row['region']}",
                "value_2023": row["value_2023"],
                "value_comparable": row["value_comparable"],
                "source_ids": "D3",
            }
        )
    for row in olr_df.to_dict("records"):
        if row["season"] not in FOUR_SEASONS:
            continue
        rows.append(
            {
                "season": row["season"],
                "metric": f"olr_{row['region']}",
                "value_2023": row["value_2023"],
                "value_comparable": row["value_comparable"],
                "source_ids": "D8",
            }
        )
    for row in era5_df.to_dict("records"):
        if row["season"] not in FOUR_SEASONS:
            continue
        rows.append(
            {
                "season": row["season"],
                "metric": row["metric"],
                "value_2023": row["value_2023"],
                "value_comparable": row["value_comparable"],
                "source_ids": row["source_ids"],
            }
        )
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records = build_matrix_records(load_rows(), sst_metric="nino3_sst")
    fieldnames = [
        "season",
        "metric",
        "value_2023",
        "value_comparable",
        "difference_2023_minus_comparable",
        "ratio_to_comparable",
        "response_efficiency",
        "source_ids",
    ]
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
