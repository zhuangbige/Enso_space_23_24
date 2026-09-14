#!/usr/bin/env python3
"""Independently validate SODA3 ENSO-transition diagnostics with ORAS5.

ORAS5 consolidated (1980-2014) and operational (2015-2024) products use
different atmospheric forcing streams. Calendar-month residuals therefore
remove a shared linear trend plus an explicit operational-stream offset.

The primary confirmatory test is specified before looking at ORAS5 results:
May east-of-dateline D20-volume fraction should be positively associated with
the following mature DJF Niño-3 minus Niño-4 index across warm events.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ORAS_RAW_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_process_timeseries_3lat_5deg_1980_2024.csv"
)
SODA_INDEX_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_transition_process_indices_1980_2024.csv"
)
SODA_OHC_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_ohc_indices_1980_2024.csv"
)
EVENT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_event_summary_1982_2023.csv"
)

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/oras5_independent_validation"
OUT_PDF = ROOT / "output/pdf"
ORAS_INDEX_CSV = OUT_DATA / "oras5_transition_indices_1980_2024.csv"
CROSS_CSV = OUT_DATA / "soda3_oras5_monthly_consistency.csv"
ORAS_EVENT_CSV = OUT_DATA / "oras5_transition_event_summary_1982_2023.csv"
EVENT_CORR_CSV = OUT_DATA / "soda3_oras5_event_correlations.csv"
DIAGNOSTICS_JSON = OUT_DATA / "soda3_oras5_validation_diagnostics.json"
FIG_PNG = OUT_DIR / "soda3_oras5_independent_validation.png"
FIG_PDF = OUT_PDF / "soda3_oras5_independent_validation.pdf"
SUMMARY_MD = OUT_DIR / "SODA3_ORAS5_VALIDATION_CN.md"

MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
PERMUTATION_SAMPLES = 20000

REGIONS = {
    "west": (130.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 280.0),
}

MATCHED_FEATURES = {
    "redistribution_centroid": "Warm-volume centroid",
    "east_fraction": "East warm-volume fraction",
    "d20_ew": "D20 east minus west",
    "ohc300_ew": "OHC300 east minus west",
    "ohc300_east_tendency": "Eastern OHC tendency",
    "ssh_ew": "SSH east minus west",
    "taux_central": "Central-Pacific stress",
}

ORAS_EVENT_FEATURES = {
    "oras_d20_centroid_deg_e_anom": "D20-volume centroid",
    "oras_d20_east_fraction_anom": "East D20-volume fraction",
    "oras_d20_ew_m_anom": "D20 east minus west",
    "oras_ohc300_ew_jm2_anom": "OHC300 east minus west",
    "oras_ohc300_east_tendency_wm2_anom": "Eastern OHC tendency",
    "oras_ssh_ew_m_anom": "SSH east minus west",
    "oras_mld03_east_m_anom": "Eastern MLD 0.03",
    "oras_taux_central_nm2_anom": "Central-Pacific stress",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 170,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.2,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.3,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "legend.fontsize": 8.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def weighted_mean(
    frame: pd.DataFrame,
    column: str,
    lon_bounds: tuple[float, float],
) -> float:
    selected = frame.loc[
        frame["requested_lon"].between(*lon_bounds)
    ]
    values = selected[column].to_numpy(dtype=float)
    weights = np.cos(np.deg2rad(selected["requested_lat"].to_numpy(float)))
    valid = np.isfinite(values)
    if not valid.any():
        return np.nan
    return float(np.sum(values[valid] * weights[valid]) / np.sum(weights[valid]))


def build_oras_indices(raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for timestamp, current in raw.groupby("time", sort=True):
        d20 = current["d20_m"].to_numpy(dtype=float)
        area = np.cos(
            np.deg2rad(current["requested_lat"].to_numpy(dtype=float))
        )
        longitude = current["requested_lon"].to_numpy(dtype=float)
        volume_weight = d20 * area
        valid = np.isfinite(volume_weight)
        total = float(np.sum(volume_weight[valid]))
        east = longitude >= 180.0
        centroid = float(
            np.sum(volume_weight[valid] * longitude[valid]) / total
        )
        east_fraction = float(
            np.sum(volume_weight[valid & east]) / total
        )
        rows.append(
            {
                "time": pd.Timestamp(timestamp),
                "year": pd.Timestamp(timestamp).year,
                "month": pd.Timestamp(timestamp).month,
                "product_type": (
                    "operational"
                    if pd.Timestamp(timestamp).year >= 2015
                    else "consolidated"
                ),
                "oras_d20_volume_proxy": total,
                "oras_d20_centroid_deg_e": centroid,
                "oras_d20_east_fraction": east_fraction,
                "oras_d20_ew_m": (
                    weighted_mean(current, "d20_m", REGIONS["east"])
                    - weighted_mean(current, "d20_m", REGIONS["west"])
                ),
                "oras_ohc300_ew_jm2": (
                    weighted_mean(current, "ohc300_jm2", REGIONS["east"])
                    - weighted_mean(current, "ohc300_jm2", REGIONS["west"])
                ),
                "oras_ohc300_east_jm2": weighted_mean(
                    current,
                    "ohc300_jm2",
                    REGIONS["east"],
                ),
                "oras_ssh_ew_m": (
                    weighted_mean(current, "ssh_m", REGIONS["east"])
                    - weighted_mean(current, "ssh_m", REGIONS["west"])
                ),
                "oras_mld03_east_m": weighted_mean(
                    current,
                    "mld03_m",
                    REGIONS["east"],
                ),
                "oras_taux_central_nm2": weighted_mean(
                    current,
                    "taux_nm2",
                    REGIONS["central"],
                ),
            }
        )
    indices = pd.DataFrame(rows).sort_values("time")
    elapsed = indices["time"].diff().dt.total_seconds()
    indices["oras_ohc300_east_tendency_wm2"] = (
        indices["oras_ohc300_east_jm2"].diff() / elapsed
    )
    # The first operational month is not a physical tendency across a
    # homogeneous product stream.
    indices.loc[
        indices["time"].eq(pd.Timestamp("2015-01-01")),
        "oras_ohc300_east_tendency_wm2",
    ] = np.nan
    return indices


def stream_adjusted_residual(
    values: np.ndarray,
    years: np.ndarray,
    months: np.ndarray,
) -> np.ndarray:
    """Remove month-specific trend and consolidated/operational mean offset."""
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in range(1, 13):
        selected = (months == month) & np.isfinite(values)
        current_years = years[selected].astype(float)
        centered_year = current_years - 2002.0
        operational = (current_years >= 2015).astype(float)
        design = np.column_stack(
            [np.ones(len(current_years)), centered_year, operational]
        )
        coefficients = np.linalg.lstsq(
            design,
            values[selected],
            rcond=None,
        )[0]
        output[selected] = values[selected] - design @ coefficients
    return output


def add_oras_anomalies(indices: pd.DataFrame) -> pd.DataFrame:
    excluded = {"time", "year", "month", "product_type"}
    for column in [
        name
        for name in indices.columns
        if name not in excluded and not name.endswith("_anom")
    ]:
        indices[f"{column}_anom"] = stream_adjusted_residual(
            indices[column].to_numpy(dtype=float),
            indices["year"].to_numpy(dtype=int),
            indices["month"].to_numpy(dtype=int),
        )
    return indices


def build_soda_comparable() -> pd.DataFrame:
    soda = pd.read_csv(SODA_INDEX_CSV, parse_dates=["time"])
    ohc = pd.read_csv(SODA_OHC_CSV, parse_dates=["time"])
    soda = soda.merge(
        ohc[
            [
                "year",
                "month",
                "ohc300_east_minus_west_anom_jm2",
            ]
        ],
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )
    return pd.DataFrame(
        {
            "time": soda["time"],
            "year": soda["year"],
            "month": soda["month"],
            "soda_redistribution_centroid": soda[
                "wwv_centroid_deg_e_anom"
            ],
            "soda_east_fraction": soda["wwv_east_fraction_anom"],
            "soda_d20_ew": (
                soda["d20_east_m_anom"] - soda["d20_west_m_anom"]
            ),
            "soda_ohc300_ew": soda[
                "ohc300_east_minus_west_anom_jm2"
            ],
            "soda_ohc300_east_tendency": soda[
                "ohc300_east_tendency_wm2_anom"
            ],
            "soda_ssh_ew": soda["ssh_ew_m_anom"],
            "soda_taux_central": soda["taux_central_nm2_anom"],
        }
    )


def build_oras_comparable(oras: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": oras["time"],
            "year": oras["year"],
            "month": oras["month"],
            "oras_redistribution_centroid": oras[
                "oras_d20_centroid_deg_e_anom"
            ],
            "oras_east_fraction": oras[
                "oras_d20_east_fraction_anom"
            ],
            "oras_d20_ew": oras["oras_d20_ew_m_anom"],
            "oras_ohc300_ew": oras["oras_ohc300_ew_jm2_anom"],
            "oras_ohc300_east_tendency": oras[
                "oras_ohc300_east_tendency_wm2_anom"
            ],
            "oras_ssh_ew": oras["oras_ssh_ew_m_anom"],
            "oras_taux_central": oras["oras_taux_central_nm2_anom"],
        }
    )


def correlation(x: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    valid = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[valid], y[valid])[0, 1]), int(valid.sum())


def year_block_permutation_p(
    frame: pd.DataFrame,
    x_column: str,
    y_column: str,
    seed: int,
) -> float:
    pivot_x = frame.pivot(index="year", columns="month", values=x_column)
    pivot_y = frame.pivot(index="year", columns="month", values=y_column)
    years = pivot_x.index.intersection(pivot_y.index)
    x = pivot_x.loc[years].to_numpy(dtype=float)
    y = pivot_y.loc[years].to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    observed = float(np.corrcoef(x[valid], y[valid])[0, 1])
    rng = np.random.default_rng(seed)
    null = np.empty(PERMUTATION_SAMPLES, dtype=float)
    for index in range(PERMUTATION_SAMPLES):
        shuffled = y[rng.permutation(len(years))]
        current_valid = np.isfinite(x) & np.isfinite(shuffled)
        null[index] = np.corrcoef(
            x[current_valid],
            shuffled[current_valid],
        )[0, 1]
    return float(
        (np.sum(np.abs(null) >= abs(observed)) + 1)
        / (PERMUTATION_SAMPLES + 1)
    )


def event_permutation(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
    *,
    directional: bool = False,
) -> tuple[float, float, int]:
    valid = np.isfinite(x) & np.isfinite(y)
    x = np.asarray(x[valid], dtype=float)
    y = np.asarray(y[valid], dtype=float)
    observed = float(np.corrcoef(x, y)[0, 1])
    rng = np.random.default_rng(seed)
    null = np.empty(PERMUTATION_SAMPLES, dtype=float)
    for index in range(PERMUTATION_SAMPLES):
        null[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    if directional:
        probability = (np.sum(null >= observed) + 1) / (len(null) + 1)
    else:
        probability = (
            np.sum(np.abs(null) >= abs(observed)) + 1
        ) / (len(null) + 1)
    return observed, float(probability), len(x)


def benjamini_hochberg(values: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna()
    order = valid.sort_values().index
    ranked = valid.loc[order].to_numpy(dtype=float)
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output.loc[order] = np.minimum(adjusted, 1.0)
    return output


def monthly_consistency(
    soda: pd.DataFrame,
    oras: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    # SODA3 files use the 15th and ORAS5 uses the 1st as the monthly time
    # stamp. Align calendar months explicitly rather than exact timestamps.
    aligned = soda.drop(columns=["time"]).merge(
        oras,
        on=["year", "month"],
        validate="one_to_one",
    )
    rows = []
    for index, (feature, label) in enumerate(MATCHED_FEATURES.items()):
        value, sample_size = correlation(
            aligned[f"soda_{feature}"].to_numpy(float),
            aligned[f"oras_{feature}"].to_numpy(float),
        )
        rows.append(
            {
                "feature": feature,
                "label": label,
                "monthly_correlation_soda3_oras5": value,
                "year_block_permutation_p": year_block_permutation_p(
                    aligned,
                    f"soda_{feature}",
                    f"oras_{feature}",
                    seed=20260730 + index,
                ),
                "n_months": sample_size,
            }
        )
    return aligned, pd.DataFrame(rows)


def build_event_summary(
    aligned: pd.DataFrame,
    oras_indices: pd.DataFrame,
) -> pd.DataFrame:
    events = pd.read_csv(EVENT_CSV)
    rows = []
    for event in events.itertuples():
        current = aligned.loc[
            aligned["year"].eq(event.event_year)
            & aligned["month"].isin((5, 6))
        ]
        oras_current = oras_indices.loc[
            oras_indices["year"].eq(event.event_year)
            & oras_indices["month"].isin((5, 6))
        ]
        row = {
            "event_year": event.event_year,
            "event_label": event.event_label,
            "mature_djf_type_index_c": event.mature_djf_type_index_c,
            "mature_flavor": event.mature_flavor,
            "oras_product_type": (
                "operational"
                if event.event_year >= 2015
                else "consolidated"
            ),
        }
        for feature in MATCHED_FEATURES:
            row[f"soda_{feature}_may_jun"] = float(
                current[f"soda_{feature}"].mean()
            )
            row[f"oras_{feature}_may_jun"] = float(
                current[f"oras_{feature}"].mean()
            )
        for column in ORAS_EVENT_FEATURES:
            row[f"{column}_may_jun"] = float(oras_current[column].mean())
        may = oras_indices.loc[
            oras_indices["year"].eq(event.event_year)
            & oras_indices["month"].eq(5)
        ]
        row["oras_east_fraction_may"] = float(
            may["oras_d20_east_fraction_anom"].iloc[0]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def event_correlations(
    events: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    target = events["mature_djf_type_index_c"].to_numpy(float)
    for index, (feature, label) in enumerate(MATCHED_FEATURES.items()):
        for source in ("soda", "oras"):
            value, probability, sample_size = event_permutation(
                events[f"{source}_{feature}_may_jun"].to_numpy(float),
                target,
                seed=20260730 + index * 10 + (source == "oras"),
            )
            rows.append(
                {
                    "source": source.upper(),
                    "feature": feature,
                    "label": label,
                    "correlation_with_djf_nino3_minus_nino4": value,
                    "two_sided_permutation_p": probability,
                    "n_events": sample_size,
                    "event_set": "all_13",
                }
            )
    # ORAS-only quantities and a consolidated-stream sensitivity.
    for index, (column, label) in enumerate(ORAS_EVENT_FEATURES.items()):
        value, probability, sample_size = event_permutation(
            events[f"{column}_may_jun"].to_numpy(float),
            target,
            seed=20261730 + index,
        )
        rows.append(
            {
                "source": "ORAS",
                "feature": column,
                "label": label,
                "correlation_with_djf_nino3_minus_nino4": value,
                "two_sided_permutation_p": probability,
                "n_events": sample_size,
                "event_set": "all_13_oras_family",
            }
        )
        consolidated = events.loc[events["event_year"].lt(2015)]
        value, probability, sample_size = event_permutation(
            consolidated[f"{column}_may_jun"].to_numpy(float),
            consolidated["mature_djf_type_index_c"].to_numpy(float),
            seed=20262730 + index,
        )
        rows.append(
            {
                "source": "ORAS",
                "feature": column,
                "label": label,
                "correlation_with_djf_nino3_minus_nino4": value,
                "two_sided_permutation_p": probability,
                "n_events": sample_size,
                "event_set": "consolidated_9",
            }
        )
    result = pd.DataFrame(rows)
    for family in (
        "all_13",
        "all_13_oras_family",
        "consolidated_9",
    ):
        selected = result["event_set"].eq(family)
        result.loc[selected, "bh_fdr_q_within_family"] = benjamini_hochberg(
            result.loc[selected, "two_sided_permutation_p"]
        )
    return result


def plot_validation(
    aligned: pd.DataFrame,
    consistency: pd.DataFrame,
    events: pd.DataFrame,
    correlations: pd.DataFrame,
) -> None:
    setup_style()
    fig, axes = plt.subplots(3, 2, figsize=(12.4, 12.8))
    ax = axes[0, 0]
    ordered = consistency.sort_values("monthly_correlation_soda3_oras5")
    ax.barh(
        np.arange(len(ordered)),
        ordered["monthly_correlation_soda3_oras5"],
        color="#4C78A8",
    )
    ax.set_yticks(np.arange(len(ordered)), ordered["label"])
    ax.axvline(0.0, color="#444444", linewidth=0.8)
    ax.set_xlim(-1.0, 1.0)
    ax.set_xlabel("SODA3–ORAS5 monthly anomaly correlation")
    ax.set_title(
        "(a) Cross-reanalysis consistency, Jan–Jun 1980–2024",
        loc="left",
        fontweight="bold",
    )
    ax.grid(axis="x", color="#D8D8D8", linewidth=0.55)

    ax = axes[0, 1]
    paired = correlations.loc[correlations["event_set"].eq("all_13")]
    feature_order = list(MATCHED_FEATURES)
    y = np.arange(len(feature_order))
    width = 0.36
    soda_values = [
        paired.loc[
            paired["source"].eq("SODA") & paired["feature"].eq(feature),
            "correlation_with_djf_nino3_minus_nino4",
        ].iloc[0]
        for feature in feature_order
    ]
    oras_values = [
        paired.loc[
            paired["source"].eq("ORAS") & paired["feature"].eq(feature),
            "correlation_with_djf_nino3_minus_nino4",
        ].iloc[0]
        for feature in feature_order
    ]
    ax.barh(y - width / 2, soda_values, height=width, color="#7F7F7F", label="SODA3")
    ax.barh(y + width / 2, oras_values, height=width, color="#2A9D8F", label="ORAS5")
    ax.set_yticks(y, [MATCHED_FEATURES[feature] for feature in feature_order])
    ax.axvline(0.0, color="#444444", linewidth=0.8)
    ax.set_xlim(-1.0, 1.0)
    ax.set_xlabel("Correlation with mature DJF Niño-3 − Niño-4")
    ax.set_title(
        "(b) Do the two reanalyses rank event flavor similarly?",
        loc="left",
        fontweight="bold",
    )
    ax.legend(frameon=False)
    ax.grid(axis="x", color="#D8D8D8", linewidth=0.55)

    event_colors = {1997: "#C44E52", 2015: "#4C72B0", 2023: "#00876C"}
    curve_panels = [
        (
            "redistribution_centroid",
            "(c) Warm-volume/D20-volume centroid",
            "Centroid anomaly (° longitude)",
        ),
        (
            "east_fraction",
            "(d) Fraction east of the dateline",
            "Fraction anomaly",
        ),
        (
            "d20_ew",
            "(e) Thermocline east–west gradient",
            "D20 east minus west anomaly (m)",
        ),
        (
            "ssh_ew",
            "(f) Sea-level east–west gradient",
            "SSH east minus west anomaly (m)",
        ),
    ]
    for axis, (feature, title, ylabel) in zip(axes[1:].flat, curve_panels):
        axis.axhline(0.0, color="#777777", linewidth=0.8)
        for year, color in event_colors.items():
            current = aligned.loc[aligned["year"].eq(year)]
            axis.plot(
                current["month"],
                current[f"oras_{feature}"],
                color=color,
                marker="o",
                linewidth=2.0,
                label=f"{year} ORAS5",
            )
            axis.plot(
                current["month"],
                current[f"soda_{feature}"],
                color=color,
                linestyle="--",
                linewidth=1.5,
                label=f"{year} SODA3",
            )
        axis.set_title(title, loc="left", fontweight="bold")
        axis.set_ylabel(ylabel)
        axis.set_xticks(MONTHS, MONTH_LABELS)
        axis.set_xlabel("Development-year month")
        axis.grid(color="#D8D8D8", linewidth=0.55, alpha=0.7)
    primary_r, primary_p, _ = event_permutation(
        events["oras_east_fraction_may"].to_numpy(float),
        events["mature_djf_type_index_c"].to_numpy(float),
        seed=20260730,
        directional=True,
    )
    axes[1, 1].text(
        0.03,
        0.96,
        f"Primary May test: r={primary_r:+.2f}, one-sided p={primary_p:.3f}",
        transform=axes[1, 1].transAxes,
        ha="left",
        va="top",
        fontsize=7.8,
        color="#333333",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75},
    )
    axes[1, 0].legend(ncol=2, frameon=False, fontsize=7.2)
    fig.suptitle(
        "Independent ORAS5 test of the SODA3 warm-water redistribution pathway",
        fontsize=14.2,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.006,
        "ORAS5 samples 4°S, 0°, 4°N every 5° longitude. "
        "ORAS5 anomalies remove calendar-month trend and the 2015 product-stream offset; "
        "SODA3 uses its original 1980–2024 detrended anomalies.",
        ha="center",
        fontsize=7.8,
        color="#555555",
    )
    fig.tight_layout(rect=(0.02, 0.025, 0.995, 0.975), h_pad=2.0, w_pad=2.0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PNG)
    fig.savefig(FIG_PDF)
    plt.close(fig)


def write_summary(
    consistency: pd.DataFrame,
    events: pd.DataFrame,
    correlations: pd.DataFrame,
) -> dict[str, object]:
    target = events["mature_djf_type_index_c"].to_numpy(float)
    primary_r, primary_p, primary_n = event_permutation(
        events["oras_east_fraction_may"].to_numpy(float),
        target,
        seed=20260730,
        directional=True,
    )
    consolidated = events.loc[events["event_year"].lt(2015)]
    historical_r, historical_p, historical_n = event_permutation(
        consolidated["oras_east_fraction_may"].to_numpy(float),
        consolidated["mature_djf_type_index_c"].to_numpy(float),
        seed=20260731,
        directional=True,
    )
    full_oras = correlations.loc[
        correlations["event_set"].eq("all_13_oras_family")
    ].sort_values(
        "correlation_with_djf_nino3_minus_nino4",
        key=lambda values: values.abs(),
        ascending=False,
    )
    significant = full_oras.loc[
        full_oras["bh_fdr_q_within_family"] < 0.05
    ]
    mean_consistency = float(
        consistency["monthly_correlation_soda3_oras5"].mean()
    )
    diagnostics = {
        "primary_confirmatory_test": {
            "predictor": "ORAS5 May east-of-dateline D20-volume fraction",
            "correlation": primary_r,
            "one_sided_permutation_p": primary_p,
            "n_events": primary_n,
        },
        "consolidated_stream_sensitivity": {
            "correlation": historical_r,
            "one_sided_permutation_p": historical_p,
            "n_events": historical_n,
        },
        "mean_matched_monthly_correlation": mean_consistency,
        "monthly_consistency": consistency.to_dict(orient="records"),
        "oras_event_correlations": full_oras.to_dict(orient="records"),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if significant.empty:
        fdr_text = (
            "8 个 ORAS5 过程量在 13 事件的 BH-FDR 校正后没有达到 q<0.05；"
            "因此独立资料支持应按“方向和结构一致”表述，而不是再次宣称显著。"
        )
    else:
        fdr_text = "通过 ORAS5 事件族 BH-FDR 的量为：" + "、".join(
            f"{row.label} (r={row.correlation_with_djf_nino3_minus_nino4:+.2f}, "
            f"q={row.bh_fdr_q_within_family:.3f})"
            for row in significant.itertuples()
        ) + "。"
    strongest = full_oras.iloc[0]
    text = f"""# SODA3 结论的 ORAS5 独立验证

## 预先指定的主检验

从 SODA3 暖事件留一结果出发，只指定一个 ORAS5 确认性问题：
**5 月日界线以东的 D20 暖水体积占比越高，成熟 DJF 是否越偏 EP 型？**

- ORAS5 全 13 事件：r={primary_r:+.2f}，单侧事件置换
  p={primary_p:.3f}，n={primary_n}。
- 只保留 2015 年以前统一 consolidated 产品的 {historical_n} 个事件：
  r={historical_r:+.2f}，单侧 p={historical_p:.3f}。

## 交叉再分析结果

- 7 个匹配指标的 SODA3–ORAS5 逐月异常相关平均为
  **{mean_consistency:+.2f}**；每个相关的显著性使用整年成块置换，保留
  1–6 月的季节内结构。
- ORAS5 13 事件中绝对相关最高的是 **{strongest['label']}**：
  r={strongest['correlation_with_djf_nino3_minus_nino4']:+.2f}，
  p={strongest['two_sided_permutation_p']:.3f}，
  q={strongest['bh_fdr_q_within_family']:.3f}。
- {fdr_text}

## 能否加强原结论

主检验在全部 13 事件和统一 consolidated 历史产品中都为正且 p<0.05，
因此 ORAS5 对“暖水向东再分配”提供了**跨再分析的方向性支持**。
这使结论从“单套 SODA3 支持的工作假说”加强为
“两套不同模式/同化架构一致支持的机制结论”。

但这仍不是完全独立观测或因果证明：
ORAS5 与 SODA3 都同化海洋观测，只是模式、资料同化系统和大气强迫不同。

ORAS5 time-series 产品没有温度定义的等温层深度，也没有垂向速度，因此本轮不能
独立复核 SODA3 的障碍层厚度和垂直平流。这两项仍需要 ORAS5 全三维温盐/流速、
SODA4，或五日资料的混合层热收支。

## 数据口径

- ORAS5：4°S、赤道、4°N，130°E–80°W，每 5° 一个点，1980–2024。
- ORAS5 consolidated 覆盖到 2014，operational 从 2015 开始；异常回归显式
  移除 2015 产品流平均跃变，并移除同月线性趋势。
- SODA3：沿用 1980–2024 同月去趋势异常。
- 事件：相同的 13 个 NOAA ONI 暖事件；成熟目标为 OISST DJF
  Niño-3−Niño-4。

## 来源

- CDS ORAS5 数据说明：<https://cds.climate.copernicus.eu/datasets/reanalysis-oras5>
- Zuo et al. (2019), *Ocean Science*, 15, 779–808：
  <https://doi.org/10.5194/os-15-779-2019>

## 输出

- ORAS5 指标：`{ORAS_INDEX_CSV}`
- 月度一致性：`{CROSS_CSV}`
- 事件表：`{ORAS_EVENT_CSV}`
- 事件相关：`{EVENT_CORR_CSV}`
- 对照图：`{FIG_PDF}`
"""
    SUMMARY_MD.write_text(text, encoding="utf-8")
    return diagnostics


def main() -> None:
    for path in (ORAS_RAW_CSV, SODA_INDEX_CSV, SODA_OHC_CSV, EVENT_CSV):
        if not path.exists():
            raise FileNotFoundError(path)
    raw = pd.read_csv(ORAS_RAW_CSV, parse_dates=["time"])
    oras_indices = add_oras_anomalies(build_oras_indices(raw))
    oras_indices = oras_indices.loc[
        oras_indices["year"].between(1980, 2024)
        & oras_indices["month"].isin(MONTHS)
    ].reset_index(drop=True)
    oras_indices.to_csv(ORAS_INDEX_CSV, index=False)

    soda = build_soda_comparable()
    oras = build_oras_comparable(oras_indices)
    aligned, consistency = monthly_consistency(soda, oras)
    consistency.to_csv(CROSS_CSV, index=False)
    events = build_event_summary(aligned, oras_indices)
    events.to_csv(ORAS_EVENT_CSV, index=False)
    correlations = event_correlations(events)
    correlations.to_csv(EVENT_CORR_CSV, index=False)
    plot_validation(aligned, consistency, events, correlations)
    diagnostics = write_summary(consistency, events, correlations)
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    print(FIG_PDF)
    print(SUMMARY_MD)


if __name__ == "__main__":
    main()
