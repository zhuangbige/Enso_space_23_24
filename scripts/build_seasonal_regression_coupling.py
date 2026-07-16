#!/usr/bin/env python3
"""Build seasonal observed/expected coupling ratios using the paper's regression logic."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_era5_seasonal_summary import (  # noqa: E402
    _monthly_anomalies,
    _monthly_records,
    _open_dataset,
    _var,
)


ROOT = Path(__file__).resolve().parents[1]
SEASONS = {
    "AMJ": (4, 5, 6),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
    "DJF": (12, 13, 14),
}
TARGET_YEAR = 2023
REFERENCE_START = 1982
REFERENCE_END = 2022
MIN_REGRESSION_YEARS = 12

INPUTS = {
    "oisst": ROOT / "data/interim/raw_validation/oisst_nino3_monthly.csv",
    "era5_single": ROOT / "data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc",
    "gpcp": ROOT / "data/interim/raw_validation/gpcp_equatorial_monthly.csv",
    "olr": ROOT / "data/interim/raw_validation/olr_monthly.csv",
}
OUT_CSV = ROOT / "data/derived/research/seasonal_regression_expected_response.csv"
OUT_FIG = ROOT / "data/derived/research/seasonal_regression_coupling_ratios.png"
OUT_FIG_PDF = ROOT / "data/derived/research/seasonal_regression_coupling_ratios.pdf"


def _safe_ratio(observed: float, expected: float) -> float | None:
    if expected == 0 or math.isnan(expected):
        return None
    return observed / expected


def _seasonal_yearly_from_monthly(
    records: list[dict[str, float | int]],
    value_key: str,
    seasons: dict[str, tuple[int, ...]] = SEASONS,
) -> pd.DataFrame:
    """Return one anomaly value per event-year and season."""
    normalized = [
        {
            "year": int(row["year"]),
            "month": int(row["month"]),
            "anomaly": float(row[value_key]),
        }
        for row in records
        if row.get(value_key) not in ("", None)
    ]
    years = sorted({int(row["year"]) for row in normalized})
    output: list[dict[str, float | int | str]] = []
    for event_year in years:
        for season, months in seasons.items():
            try:
                value = _seasonal_mean_available(normalized, event_year, months)
            except KeyError:
                continue
            output.append({"event_year": event_year, "season": season, "value": value})
    return pd.DataFrame(output)


def _seasonal_mean_available(
    records: list[dict[str, float | int]], event_year: int, months: tuple[int, ...]
) -> float:
    lookup = {(int(row["year"]), int(row["month"])): float(row["anomaly"]) for row in records}
    values = []
    for month in months:
        year = event_year
        actual_month = month
        if month > 12:
            year += 1
            actual_month = month - 12
        value = lookup[(year, actual_month)]
        if not math.isnan(value):
            values.append(value)
    if not values:
        raise KeyError((event_year, months))
    return sum(values) / len(values)


def _read_oisst_nino3(path: Path) -> pd.DataFrame:
    rows = pd.read_csv(path).to_dict("records")
    return _seasonal_yearly_from_monthly(rows, "anomaly").rename(
        columns={"value": "nino3_sst_oisst"}
    )


def _read_gpcp_metric(path: Path, region: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    rows = raw.loc[raw["region"] == region].to_dict("records")
    return _seasonal_yearly_from_monthly(rows, "anomaly").rename(
        columns={"value": f"gpcp_precip_{region}"}
    )


def _read_olr_metric(path: Path, region: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["event_year", "season", f"olr_{region}"])
    raw = pd.read_csv(path)
    rows = raw.loc[raw["region"] == region].rename(
        columns={"olr_anomaly": "anomaly"}
    ).to_dict("records")
    return _seasonal_yearly_from_monthly(rows, "anomaly").rename(
        columns={"value": f"olr_{region}"}
    )


def _read_era5_metrics(path: Path) -> pd.DataFrame:
    single = _open_dataset(path)
    try:
        u10 = _var(single, ("u10", "10u", "10m_u_component_of_wind"))
        msl = _var(single, ("msl", "mean_sea_level_pressure")) / 100.0

        u10_records = _monthly_anomalies(
            _monthly_records(u10, "cwp_160e_140w"), REFERENCE_START, REFERENCE_END
        )
        tahiti = _monthly_anomalies(
            _monthly_records(msl, "tahiti_proxy"), REFERENCE_START, REFERENCE_END
        )
        darwin = _monthly_anomalies(
            _monthly_records(msl, "darwin_proxy"), REFERENCE_START, REFERENCE_END
        )
    finally:
        single.close()

    soi_records = []
    for left, right in zip(tahiti, darwin):
        soi_records.append(
            {
                "year": int(left["year"]),
                "month": int(left["month"]),
                "anomaly": float(left["anomaly"]) - float(right["anomaly"]),
            }
        )

    u10_df = _seasonal_yearly_from_monthly(u10_records, "anomaly").rename(
        columns={"value": "era5_u10_cwp_160e_140w"}
    )
    soi_df = _seasonal_yearly_from_monthly(soi_records, "anomaly").rename(
        columns={"value": "era5_soi_like_tahiti_minus_darwin"}
    )
    return u10_df.merge(soi_df, on=["event_year", "season"], how="outer")


def _merge_metrics(frames: list[pd.DataFrame]) -> pd.DataFrame:
    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on=["event_year", "season"], how="outer")
    return merged.sort_values(["event_year", "season"]).reset_index(drop=True)


def _linear_regression(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    slope, intercept = np.polyfit(x, y, 1)
    expected = slope * x + intercept
    residual = y - expected
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_value = float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else math.nan
    r_squared = math.nan if ss_tot == 0 else 1.0 - ss_res / ss_tot
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r": r_value,
        "r_squared": r_squared,
    }


def build_regression_rows(
    yearly: pd.DataFrame,
    *,
    reference_start: int = REFERENCE_START,
    reference_end: int = REFERENCE_END,
    target_year: int = TARGET_YEAR,
) -> list[dict[str, float | int | str | None]]:
    metrics = [
        col
        for col in yearly.columns
        if col not in {"event_year", "season", "nino3_sst_oisst"}
    ]
    output: list[dict[str, float | int | str | None]] = []
    for season in SEASONS:
        season_df = yearly.loc[yearly["season"] == season].copy()
        target = season_df.loc[season_df["event_year"] == target_year]
        if target.empty:
            continue
        nino_target = float(target.iloc[0]["nino3_sst_oisst"])
        for metric in metrics:
            fit_df = season_df.loc[
                (season_df["event_year"] >= reference_start)
                & (season_df["event_year"] <= reference_end),
                ["event_year", "nino3_sst_oisst", metric],
            ].dropna()
            if len(fit_df) < MIN_REGRESSION_YEARS:
                continue
            stats = _linear_regression(
                fit_df["nino3_sst_oisst"].to_numpy(dtype=float),
                fit_df[metric].to_numpy(dtype=float),
            )
            observed = float(target.iloc[0][metric])
            expected = stats["slope"] * nino_target + stats["intercept"]
            ratio = _safe_ratio(observed, expected)
            output.append(
                {
                    "metric": metric,
                    "season": season,
                    "target_year": target_year,
                    "nino3_2023": nino_target,
                    "observed_2023": observed,
                    "expected_from_regression": expected,
                    "residual_observed_minus_expected": observed - expected,
                    "coupling_ratio_observed_over_expected": ratio,
                    "slope": stats["slope"],
                    "intercept": stats["intercept"],
                    "r": stats["r"],
                    "r_squared": stats["r_squared"],
                    "regression_start_year": int(fit_df["event_year"].min()),
                    "regression_end_year": int(fit_df["event_year"].max()),
                    "regression_n_years": int(len(fit_df)),
                }
            )
    return output


def write_rows(path: Path, rows: list[dict[str, float | int | str | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "metric",
        "season",
        "target_year",
        "nino3_2023",
        "observed_2023",
        "expected_from_regression",
        "residual_observed_minus_expected",
        "coupling_ratio_observed_over_expected",
        "slope",
        "intercept",
        "r",
        "r_squared",
        "regression_start_year",
        "regression_end_year",
        "regression_n_years",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_rows(
    rows: list[dict[str, float | int | str | None]],
    output_png: Path,
    output_pdf: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = {
        "era5_u10_cwp_160e_140w": "ERA5 CWP u10",
        "era5_soi_like_tahiti_minus_darwin": "ERA5 SOI-like SLP",
        "gpcp_precip_central_pacific_180_140w": "GPCP CP rainfall",
        "olr_central_pacific_180_140w": "CPC OLR CP",
    }
    colors = {
        "era5_u10_cwp_160e_140w": "#c95a49",
        "era5_soi_like_tahiti_minus_darwin": "#3d6f82",
        "gpcp_precip_central_pacific_180_140w": "#4f79a8",
        "olr_central_pacific_180_140w": "#8a6bb1",
    }
    df = pd.DataFrame(rows)
    metrics = [metric for metric in labels if metric in set(df["metric"])]
    seasons = list(SEASONS)
    x = np.arange(len(seasons))
    width = 0.18

    fig, ax = plt.subplots(figsize=(11.8, 5.7))
    fig.patch.set_facecolor("#f7f3ea")
    ax.set_facecolor("#f7f3ea")
    ax.grid(axis="y", color="#d8d1c4", linewidth=0.8, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.axhline(1, color="#1f1f1f", linewidth=1.1)
    ax.axhline(0, color="#1f1f1f", linewidth=0.8, alpha=0.55)

    for index, metric in enumerate(metrics):
        values = []
        for season in seasons:
            subset = df.loc[(df["metric"] == metric) & (df["season"] == season)]
            if subset.empty:
                values.append(np.nan)
            else:
                values.append(
                    float(subset.iloc[0]["coupling_ratio_observed_over_expected"])
                )
        offset = (index - (len(metrics) - 1) / 2) * width
        ax.bar(
            x + offset,
            values,
            width=width,
            label=labels[metric],
            color=colors[metric],
            edgecolor="white",
            linewidth=0.6,
        )
        for xpos, value in zip(x + offset, values):
            if np.isfinite(value):
                va = "bottom" if value >= 0 else "top"
                y = value + (0.035 if value >= 0 else -0.035)
                ax.text(xpos, y, f"{value:.2f}", ha="center", va=va, fontsize=8.5)

    ax.set_xticks(x, seasons)
    ax.set_ylabel("Observed / regression-expected response")
    ax.set_title(
        "Seasonal atmospheric coupling ratios using Peng et al.-style expected response",
        loc="left",
        fontsize=13.5,
        fontweight="bold",
    )
    ax.text(
        0.0,
        -0.22,
        "Expected response is fitted separately for each season from historical Niño-3 SST anomalies "
        "and atmospheric anomalies. Regression years: 1982-2022 for ERA5/GPCP, 1997-2022 for CPC OLR. "
        "OLR is shown with its native sign; negative OLR means enhanced convection.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.2,
    )
    ax.legend(frameon=False, ncol=2, loc="upper right", fontsize=9.4)
    ax.set_ylim(-1.1, 1.45)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(output_pdf, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Use seasonal Niño-3 regressions to compute observed/expected atmospheric coupling ratios."
    )
    parser.add_argument("--oisst", type=Path, default=INPUTS["oisst"])
    parser.add_argument("--era5-single", type=Path, default=INPUTS["era5_single"])
    parser.add_argument("--gpcp", type=Path, default=INPUTS["gpcp"])
    parser.add_argument("--olr", type=Path, default=INPUTS["olr"])
    parser.add_argument("--output-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--output-fig", type=Path, default=OUT_FIG)
    parser.add_argument("--output-pdf", type=Path, default=OUT_FIG_PDF)
    args = parser.parse_args()

    frames = [
        _read_oisst_nino3(args.oisst),
        _read_era5_metrics(args.era5_single),
        _read_gpcp_metric(args.gpcp, "central_pacific_180_140w"),
        _read_olr_metric(args.olr, "central_pacific_180_140w"),
    ]
    yearly = _merge_metrics(frames)
    rows = build_regression_rows(yearly)
    write_rows(args.output_csv, rows)
    plot_rows(rows, args.output_fig, args.output_pdf)
    print(args.output_csv)
    print(args.output_fig)
    print(args.output_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
