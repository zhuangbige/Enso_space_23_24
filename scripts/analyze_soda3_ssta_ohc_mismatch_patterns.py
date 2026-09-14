#!/usr/bin/env python3
"""Diagnose recurring SSTA--OHC evolution patterns across SODA3 warm events.

This is a downstream analysis of the harmonized event-month table produced by
``analyze_soda3_all_warm_event_ssta_ohc_mismatch.py``.  It separates the mere
occurrence of a surface-warm/column-cold month from what happens immediately
afterward, and tests whether sustained surface--column agreement during the
development season is related to mature Niño-3.4 amplitude.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/soda3_ssta_ohc_pattern_analysis"
DERIVED_DIR = ROOT / "data/derived/research_2026"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "font_cache"))

import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


MONTHLY_FILE = (
    DERIVED_DIR / "soda3_all_warm_event_fep_ssta_ohc_monthly_1982_2024.csv"
)
EVENT_FILE = DERIVED_DIR / "enso_type_coupling_event_summary.csv"
METRICS_FILE = DERIVED_DIR / "soda3_ssta_ohc_pattern_metrics_1982_2024.csv"
CORRELATION_FILE = DERIVED_DIR / "soda3_ssta_ohc_pattern_correlations_1982_2024.csv"
REPORT_FILE = OUT_DIR / "SODA3_SSTA_OHC_PATTERN_ANALYSIS_CN.md"

FEP = "fep_90W_80W"
EAST = "east_140W_80W"
MISMATCH_EVENTS = (1982, 2002, 2004, 2006, 2023)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
GROUP_COLORS = {
    "classic EP": "#D1495B",
    "CP": "#247BA0",
    "other warm": "#718096",
    "2023 weak-coupling EP": "#7B2CBF",
}
TRAJECTORY_COLORS = {
    1982: "#E07A1F",
    2002: "#4C78A8",
    2004: "#7F8C8D",
    2006: "#2A9D8F",
    2023: "#7B2CBF",
}
PROCESS_LABELS = {
    "early_conversion": "early conversion",
    "late_conversion": "late conversion",
    "late_reversal": "late reversal",
    "aborted_warm_spell": "aborted warm spell",
    "isolated_surface_pulse": "isolated surface pulse",
    "no_mismatch": "no mismatch",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.4,
            "axes.titlesize": 10.8,
            "axes.labelsize": 9.8,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def longest_true_run(values: pd.Series) -> int:
    best = 0
    current = 0
    for value in values.astype(bool):
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def first_positive_month(values: pd.Series, months: pd.Series) -> float:
    selected = months.loc[values.gt(0.0)]
    return np.nan if selected.empty else float(selected.iloc[0])


def classify_mismatch(
    first_month: float,
    converted_next_month: bool,
    joint_positive_before: int,
) -> str:
    if not np.isfinite(first_month):
        return "no_mismatch"
    if converted_next_month:
        return "early_conversion" if first_month <= 3 else "late_conversion"
    if joint_positive_before >= 2:
        return "late_reversal"
    if joint_positive_before == 1:
        return "aborted_warm_spell"
    return "isolated_surface_pulse"


def build_metrics(monthly: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    primary = monthly.loc[monthly.primary_sample].copy()
    for (region, year), event in primary.groupby(["region", "year"], sort=True):
        event = event.sort_values("month").reset_index(drop=True)
        if event.month.astype(int).tolist() != list(range(1, 7)):
            raise ValueError(f"Incomplete January--June sequence: {region}, {year}")

        joint = event.ssta_c.gt(0.0) & event.ohc300_gj_m2.gt(0.0)
        mismatch = event.ssta_c.gt(0.0) & event.ohc300_gj_m2.lt(0.0)
        mismatch_indices = np.flatnonzero(mismatch.to_numpy())
        first_index = None if len(mismatch_indices) == 0 else int(mismatch_indices[0])
        first_month = np.nan if first_index is None else float(event.month.iloc[first_index])
        has_next = first_index is not None and first_index < len(event) - 1
        converted = bool(has_next and joint.iloc[first_index + 1])
        joint_before = 0 if first_index is None else int(joint.iloc[:first_index].sum())
        process = classify_mismatch(first_month, converted, joint_before)

        if first_index is None:
            mismatch_ssta = np.nan
            mismatch_ohc = np.nan
            mismatch_contrast = np.nan
            next_ssta_change = np.nan
            next_ohc_change = np.nan
        else:
            mismatch_ssta = float(event.ssta_c.iloc[first_index])
            mismatch_ohc = float(event.ohc300_gj_m2.iloc[first_index])
            mismatch_contrast = float(event.standardized_contrast.iloc[first_index])
            if has_next:
                next_ssta_change = float(
                    event.ssta_c.iloc[first_index + 1] - event.ssta_c.iloc[first_index]
                )
                next_ohc_change = float(
                    event.ohc300_gj_m2.iloc[first_index + 1]
                    - event.ohc300_gj_m2.iloc[first_index]
                )
            else:
                next_ssta_change = np.nan
                next_ohc_change = np.nan

        first_ssta = first_positive_month(event.ssta_c, event.month)
        first_ohc = first_positive_month(event.ohc300_gj_m2, event.month)
        june = event.loc[event.month.eq(6)].iloc[0]
        rows.append(
            {
                "region": region,
                "year": int(year),
                "first_positive_ssta_month": first_ssta,
                "first_positive_ohc_month": first_ohc,
                "ohc_minus_ssta_first_positive_lag_months": (
                    np.nan if not np.isfinite(first_ssta + first_ohc) else first_ohc - first_ssta
                ),
                "has_ssta_positive_ohc_negative_month": bool(mismatch.any()),
                "first_mismatch_month": first_month,
                "first_mismatch_ssta_c": mismatch_ssta,
                "first_mismatch_ohc300_gj_m2": mismatch_ohc,
                "first_mismatch_standardized_contrast": mismatch_contrast,
                "next_month_ssta_change_c": next_ssta_change,
                "next_month_ohc_change_gj_m2": next_ohc_change,
                "converted_to_joint_positive_next_month": converted,
                "joint_positive_months_before_mismatch": joint_before,
                "mismatch_process_type": process,
                "joint_positive_month_count": int(joint.sum()),
                "longest_joint_positive_run_months": longest_true_run(joint),
                "jan_jun_positive_product_sum": float(
                    (
                        event.ssta_c.clip(lower=0.0)
                        * event.ohc300_gj_m2.clip(lower=0.0)
                    ).sum()
                ),
                "jan_jun_mean_ssta_c": float(event.ssta_c.mean()),
                "jan_jun_mean_ohc300_gj_m2": float(event.ohc300_gj_m2.mean()),
                "june_ssta_c": float(june.ssta_c),
                "june_ohc300_gj_m2": float(june.ohc300_gj_m2),
                "june_joint_warmth_z": float((june.ssta_z + june.ohc300_z) / 2.0),
            }
        )

    metrics = pd.DataFrame(rows)
    event_columns = [
        "year",
        "group",
        "mature_djf_nino34_c",
        "mature_djf_type_index_c",
        "mar_apr_ocean_penetration_z",
        "mar_apr_fep_residual_c",
        "may_jun_intensity_coupling_residual_z",
        "may_jun_pattern_coupling_residual_z",
        "weakest_chain_link",
        "weakest_chain_residual_z",
    ]
    return (
        metrics.merge(events[event_columns], on="year", how="left", validate="many_to_one")
        .sort_values(["region", "year"])
        .reset_index(drop=True)
    )


def permutation_spearman(
    x: pd.Series,
    y: pd.Series,
    *,
    seed: int,
    permutations: int = 100_000,
) -> tuple[int, float, float]:
    valid = x.notna() & y.notna()
    x_rank = x.loc[valid].rank(method="average").to_numpy(dtype=float)
    y_rank = y.loc[valid].rank(method="average").to_numpy(dtype=float)
    x_centered = x_rank - x_rank.mean()
    y_centered = y_rank - y_rank.mean()
    denominator = np.sqrt(np.sum(x_centered**2) * np.sum(y_centered**2))
    observed = float(np.sum(x_centered * y_centered) / denominator)

    rng = np.random.default_rng(seed)
    order = np.argsort(rng.random((permutations, len(y_centered))), axis=1)
    permuted = y_centered[order]
    simulated = (permuted @ x_centered) / denominator
    p_value = float((1 + np.count_nonzero(np.abs(simulated) >= abs(observed))) / (permutations + 1))
    return len(x_rank), observed, p_value


def build_correlations(metrics: pd.DataFrame) -> pd.DataFrame:
    candidates = {
        "joint_positive_month_count": "Number of co-positive months",
        "longest_joint_positive_run_months": "Longest co-positive run",
        "jan_jun_positive_product_sum": "Integrated positive SSTA×OHC",
        "jan_jun_mean_ssta_c": "January--June mean SSTA",
        "jan_jun_mean_ohc300_gj_m2": "January--June mean OHC",
        "june_ssta_c": "June SSTA",
        "june_ohc300_gj_m2": "June OHC",
        "june_joint_warmth_z": "June joint warmth score",
    }
    rows: list[dict[str, object]] = []
    for region_index, region in enumerate((FEP, EAST)):
        data = metrics.loc[metrics.region.eq(region)]
        for metric_index, (column, label) in enumerate(candidates.items()):
            n, rho, p_value = permutation_spearman(
                data[column],
                data.mature_djf_nino34_c,
                seed=202308 + region_index * 100 + metric_index,
            )
            rows.append(
                {
                    "region": region,
                    "predictor": column,
                    "predictor_label": label,
                    "outcome": "mature_djf_nino34_c",
                    "n_events": n,
                    "spearman_rho": rho,
                    "permutation_p_two_sided": p_value,
                    "n_permutations": 100_000,
                }
            )
    return pd.DataFrame(rows)


def save_figure(fig: plt.Figure, stem: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    return png, pdf


def plot_mismatch_trajectories(
    monthly: pd.DataFrame,
    metrics: pd.DataFrame,
) -> tuple[Path, Path]:
    data = monthly.loc[
        monthly.primary_sample
        & monthly.region.eq(FEP)
        & monthly.year.isin(MISMATCH_EVENTS)
    ].copy()
    lookup = metrics.loc[metrics.region.eq(FEP)].set_index("year")

    fig, axes = plt.subplots(2, 3, figsize=(13.4, 8.3), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    for axis in axes_flat[:5]:
        axis.axhspan(0.0, 2.5, xmin=0.0, xmax=0.367, color="#F6E8C3", alpha=0.55, zorder=0)
        axis.axhspan(0.0, 2.5, xmin=0.367, xmax=1.0, color="#DDEFD9", alpha=0.55, zorder=0)
        axis.axhline(0.0, color="0.35", linewidth=0.8, zorder=1)
        axis.axvline(0.0, color="0.35", linewidth=0.8, zorder=1)
        axis.grid(color="white", linewidth=0.8, zorder=0)
        axis.set_xlim(-0.9, 1.55)
        axis.set_ylim(-1.8, 2.4)
        axis.set_xticks(np.arange(-0.5, 1.6, 0.5))
        axis.set_yticks(np.arange(-1.5, 2.1, 0.5))

    for axis, year in zip(axes_flat[:5], MISMATCH_EVENTS):
        event = data.loc[data.year.eq(year)].sort_values("month").reset_index(drop=True)
        color = TRAJECTORY_COLORS[year]
        x = event.ohc300_gj_m2.to_numpy()
        y = event.ssta_c.to_numpy()
        for index in range(5):
            axis.annotate(
                "",
                xy=(x[index + 1], y[index + 1]),
                xytext=(x[index], y[index]),
                arrowprops={
                    "arrowstyle": "-|>",
                    "color": color,
                    "linewidth": 1.5,
                    "shrinkA": 3,
                    "shrinkB": 3,
                    "mutation_scale": 9,
                },
                zorder=3,
            )
        axis.scatter(x, y, s=39, color=color, edgecolor="white", linewidth=0.7, zorder=4)
        for month_index, (x_value, y_value) in enumerate(zip(x, y), start=1):
            axis.annotate(
                str(month_index),
                (x_value, y_value),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7.2,
                color="0.16",
                zorder=5,
            )
        row = lookup.loc[year]
        process = PROCESS_LABELS[str(row.mismatch_process_type)]
        axis.set_title(
            f"{year}  |  mature Niño-3.4 {row.mature_djf_nino34_c:.2f} °C\n{process}",
            color=color if year == 2023 else "0.13",
            fontweight="bold" if year == 2023 else "normal",
            pad=6,
        )

    note = axes_flat[5]
    note.axis("off")
    note.text(
        0.04,
        0.93,
        "How to read",
        transform=note.transAxes,
        fontsize=12.5,
        fontweight="bold",
        va="top",
    )
    note.text(
        0.04,
        0.82,
        "Numbers mark Jan–Jun.\nArrows show month-to-month evolution.",
        transform=note.transAxes,
        fontsize=9.4,
        va="top",
        linespacing=1.45,
    )
    note.legend(
        handles=[
            Patch(facecolor="#F6E8C3", edgecolor="none", label="SSTA > 0, OHC < 0"),
            Patch(facecolor="#DDEFD9", edgecolor="none", label="SSTA > 0, OHC > 0"),
            Line2D([0], [0], color=TRAJECTORY_COLORS[2023], marker="o", label="2023 trajectory"),
        ],
        loc="center left",
        bbox_to_anchor=(0.02, 0.48),
        frameon=False,
        borderaxespad=0.0,
    )
    note.text(
        0.04,
        0.20,
        "The key split occurs after the mismatch:\n1982/2023 move into the co-warm quadrant;\n2002/2004/2006 move back toward cooling.",
        transform=note.transAxes,
        fontsize=9.2,
        va="top",
        linespacing=1.45,
    )

    fig.supxlabel("FEP 0–300 m OHC anomaly (GJ m$^{-2}$)", y=0.045)
    fig.supylabel("FEP OISST SSTA (°C)", x=0.035)
    fig.suptitle(
        "The same surface–column mismatch can lead to opposite outcomes",
        fontsize=15.5,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.943,
        "FEP = 5°S–5°N, 90°W–80°W; common 1982–2024 detrended monthly baseline and ocean footprint",
        ha="center",
        fontsize=9.1,
        color="0.33",
    )
    fig.subplots_adjust(left=0.075, right=0.985, top=0.885, bottom=0.10, wspace=0.16, hspace=0.26)
    return save_figure(fig, "fig_fep_mismatch_event_phase_trajectories")


def add_linear_fit(axis: plt.Axes, x: np.ndarray, y: np.ndarray) -> None:
    if np.unique(x).size < 2:
        return
    slope, intercept = np.polyfit(x, y, 1)
    grid = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), 100)
    axis.plot(grid, slope * grid + intercept, color="0.35", linestyle="--", linewidth=1.0, zorder=1)


def annotate_events(
    axis: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    years: np.ndarray,
    *,
    predictor: str,
) -> None:
    special_offsets = {
        "longest_joint_positive_run_months": {
            1986: (5, 11),
            1994: (5, -7),
            2006: (5, -9),
            2018: (5, 1),
        },
        "june_joint_warmth_z": {
            1986: (5, -10),
            1994: (-24, -9),
            2002: (5, 6),
            2018: (5, 4),
        },
    }
    for index, (x_value, y_value, year) in enumerate(zip(x, y, years)):
        dx = 4
        dy = 5 if index % 2 == 0 else -9
        dx, dy = special_offsets.get(predictor, {}).get(int(year), (dx, dy))
        if year == 2023:
            dx, dy = 6, -12
        axis.annotate(
            str(int(year)),
            (x_value, y_value),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=7.1,
            color="#5B1789" if year == 2023 else "0.25",
        )


def plot_persistence_relationships(
    metrics: pd.DataFrame,
    correlations: pd.DataFrame,
) -> tuple[Path, Path]:
    data = metrics.loc[metrics.region.eq(FEP)].sort_values("year").copy()
    correlation_lookup = correlations.loc[correlations.region.eq(FEP)].set_index("predictor")
    years = data.year.to_numpy(dtype=int)
    outcome = data.mature_djf_nino34_c.to_numpy(dtype=float)
    colors = [GROUP_COLORS.get(group, "#718096") for group in data.group]
    edgecolors = ["#4A125E" if year == 2023 else "white" for year in years]
    linewidths = [2.2 if year == 2023 else 0.8 for year in years]

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.5), sharey=True)
    specifications = [
        (
            "longest_joint_positive_run_months",
            "Longest consecutive co-positive run (months)",
            "Persistence matters more than first-positive order",
        ),
        (
            "june_joint_warmth_z",
            "June joint warmth = mean(SSTA z, OHC z)",
            "By June, surface–column agreement tracks mature strength",
        ),
    ]
    for axis, (column, xlabel, title) in zip(axes, specifications):
        x = data[column].to_numpy(dtype=float)
        add_linear_fit(axis, x, outcome)
        axis.scatter(
            x,
            outcome,
            s=58,
            c=colors,
            edgecolors=edgecolors,
            linewidths=linewidths,
            zorder=3,
        )
        annotate_events(axis, x, outcome, years, predictor=column)
        row = correlation_lookup.loc[column]
        axis.text(
            0.03,
            0.96,
            f"Spearman ρ = {row.spearman_rho:.2f}\npermutation p = {row.permutation_p_two_sided:.3f}",
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=8.8,
            bbox={"facecolor": "white", "edgecolor": "0.82", "boxstyle": "round,pad=0.3"},
        )
        axis.set_xlabel(xlabel)
        axis.set_title(title, fontweight="bold", pad=8)
        axis.grid(color="0.90", linewidth=0.7)
    axes[0].set_ylabel("Mature DJF Niño-3.4 anomaly (°C)")
    axes[0].set_xlim(-0.35, 4.45)
    axes[0].set_xticks(range(5))

    fig.suptitle(
        "Sustained co-warming, not mismatch amplitude, organizes the event sample",
        fontsize=15.2,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.925,
        "13 warm events; FEP January–June development versus mature-season Niño-3.4",
        ha="center",
        fontsize=9.2,
        color="0.33",
    )
    legend_handles = [
        Line2D([0], [0], marker="o", linestyle="none", color=color, label=group, markersize=7)
        for group, color in GROUP_COLORS.items()
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
        ncol=4,
        frameon=False,
    )
    fig.text(
        0.985,
        0.02,
        "Exploratory, unadjusted tests; n = 13",
        ha="right",
        fontsize=7.8,
        color="0.42",
    )
    fig.subplots_adjust(left=0.08, right=0.985, top=0.84, bottom=0.18, wspace=0.18)
    return save_figure(fig, "fig_fep_joint_warming_persistence_vs_mature_nino34")


def format_mismatch_table(fep: pd.DataFrame) -> list[str]:
    selected = fep.loc[fep.has_ssta_positive_ohc_negative_month].sort_values("year")
    lines = [
        "| Event | Mismatch month | SSTA | OHC | Next-month ΔSSTA | Next-month ΔOHC | Evolution | Mature Niño-3.4 |",
        "|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for row in selected.itertuples(index=False):
        lines.append(
            "| "
            f"{row.year} | {MONTH_LABELS[int(row.first_mismatch_month) - 1]} | "
            f"{row.first_mismatch_ssta_c:+.3f} °C | "
            f"{row.first_mismatch_ohc300_gj_m2:+.3f} GJ m⁻² | "
            f"{row.next_month_ssta_change_c:+.3f} °C | "
            f"{row.next_month_ohc_change_gj_m2:+.3f} GJ m⁻² | "
            f"{PROCESS_LABELS[row.mismatch_process_type]} | "
            f"{row.mature_djf_nino34_c:.3f} °C |"
        )
    return lines


def write_report(metrics: pd.DataFrame, correlations: pd.DataFrame) -> Path:
    fep = metrics.loc[metrics.region.eq(FEP)].copy()
    east = metrics.loc[metrics.region.eq(EAST)].copy()
    fep_corr = correlations.loc[correlations.region.eq(FEP)].set_index("predictor")
    east_corr = correlations.loc[correlations.region.eq(EAST)].set_index("predictor")
    converted = fep.loc[
        fep.has_ssta_positive_ohc_negative_month
        & fep.converted_to_joint_positive_next_month
    ]
    failed = fep.loc[
        fep.has_ssta_positive_ohc_negative_month
        & ~fep.converted_to_joint_positive_next_month
    ]
    lag_lookup = fep.set_index("year").ohc_minus_ssta_first_positive_lag_months

    run_row = fep_corr.loc["longest_joint_positive_run_months"]
    june_row = fep_corr.loc["june_joint_warmth_z"]
    east_june_row = east_corr.loc["june_joint_warmth_z"]
    lines = [
        "# SODA3 暖事件 SSTA–OHC 演变规律",
        "",
        "## 核心发现",
        "",
        "**是否出现过 SSTA > 0、OHC < 0 并不能区分强弱事件；异号后的一个月是否转为表层与海洋热含量共同增暖，才是这组事件中更清楚的分水岭。**",
        "",
        f"FEP 的 5 次异号事件中，只有 {', '.join(str(value) for value in converted.year.astype(int))} 在下个月转入共同正异常；它们成熟期 Niño-3.4 平均为 {converted.mature_djf_nino34_c.mean():.3f} °C。其余 {', '.join(str(value) for value in failed.year.astype(int))} 没有完成这种转换，成熟期平均仅 {failed.mature_djf_nino34_c.mean():.3f} °C。样本只有 2 对 3，应该视为过程线索，而不是显著性结论。",
        "",
        "## 五次异号事件的后续命运",
        "",
        *format_mismatch_table(fep),
        "",
        "- 2023 是唯一一次“早期、幅度足够明显、次月完成转换，并持续共同为正到 6 月”的事件。",
        "- 1982 也完成次月转换，但异号发生在 5 月，而且当月 OHC 仅略低于零，因此更像晚季、临界值附近的表层领先。",
        "- 2006 的 2 月异号比 2023 更强，但 3 月 SSTA 与 OHC 都下降，说明异号幅度本身不预示后续增强。",
        "- 2002 是已有共同增暖之后的晚季反转；2004 是短暂共同增暖的失败；2006 更接近孤立的表层暖脉冲。",
        "",
        "## 13 次事件中的统计规律",
        "",
        f"- 最长连续共同正异常月数与成熟期 Niño-3.4 呈中等正相关：Spearman ρ={run_row.spearman_rho:.3f}，置换 p={run_row.permutation_p_two_sided:.4f}。",
        f"- 6 月表层–OHC 联合暖度与成熟期强度的联系更强：ρ={june_row.spearman_rho:.3f}，置换 p={june_row.permutation_p_two_sided:.4f}。",
        f"- 把区域扩展到 140°W–80°W 后，6 月联合暖度关系仍存在且更强：ρ={east_june_row.spearman_rho:.3f}，置换 p={east_june_row.permutation_p_two_sided:.4f}。这说明“晚春至初夏能否形成一致暖态”较稳健，但具体哪些月份出现异号对区域边界敏感。",
        "",
        "## 对强暖事件的补充比较",
        "",
        f"首次转正顺序并不统一：1982 的 OHC 比 SSTA 晚 {lag_lookup.loc[1982]:.0f} 个月，1997 早 {-lag_lookup.loc[1997]:.0f} 个月，2015 同月，2023 晚 {lag_lookup.loc[2023]:.0f} 个月。因此不能把“表层先暖”本身当作强东部型事件的必要条件。更一致的共同特征是随后形成并维持表层–上层海洋同号暖异常。",
        "",
        "## 当前最值得检验的机制假说",
        "",
        "2023 的特殊性可以表述为：**远东太平洋表层先响应，而 0–300 m 热含量在约一个月内快速追上；2006 等失败事件没有发生这种向整层共同增暖的转换。** 下一步应比较 2023 与 2006 在 2–3 月的经向/纬向热输送、温跃层深度和表面热通量，判断 OHC 的追赶来自水平热平流、下沉 Kelvin 波，还是局地通量。",
        "",
        "## 限制",
        "",
        "- 样本只有 13 次，异号子样本只有 5 次；相关检验是探索性的，未作多重比较校正。",
        "- 1982 和 2023 的异号 OHC 都靠近零线，结论应同时参考原始幅度、空间图和同产品 SODA 表层温度。",
        "- 这些结果描述事件演变，不单独证明因果机制。",
        "",
        f"数据行数核验：FEP={len(fep)} 个事件，broader East={len(east)} 个事件。",
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    setup_style()
    monthly = pd.read_csv(MONTHLY_FILE)
    events = pd.read_csv(EVENT_FILE)
    if set(monthly.month.unique()) != set(range(1, 7)):
        raise ValueError("Monthly input is not restricted to January--June")
    if int(events.year.nunique()) != 13:
        raise ValueError("Expected 13 primary warm events")

    metrics = build_metrics(monthly, events)
    correlations = build_correlations(metrics)
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(METRICS_FILE, index=False)
    correlations.to_csv(CORRELATION_FILE, index=False)
    trajectory_png, trajectory_pdf = plot_mismatch_trajectories(monthly, metrics)
    relationship_png, relationship_pdf = plot_persistence_relationships(metrics, correlations)
    report = write_report(metrics, correlations)

    fep_mismatch = metrics.loc[
        metrics.region.eq(FEP) & metrics.has_ssta_positive_ohc_negative_month,
        [
            "year",
            "first_mismatch_month",
            "first_mismatch_ssta_c",
            "first_mismatch_ohc300_gj_m2",
            "next_month_ssta_change_c",
            "next_month_ohc_change_gj_m2",
            "converted_to_joint_positive_next_month",
            "mismatch_process_type",
            "mature_djf_nino34_c",
        ],
    ]
    print(fep_mismatch.to_string(index=False))
    print(correlations.loc[correlations.region.eq(FEP)].to_string(index=False))
    for path in (
        METRICS_FILE,
        CORRELATION_FILE,
        trajectory_png,
        trajectory_pdf,
        relationship_png,
        relationship_pdf,
        report,
    ):
        print(path)


if __name__ == "__main__":
    main()
