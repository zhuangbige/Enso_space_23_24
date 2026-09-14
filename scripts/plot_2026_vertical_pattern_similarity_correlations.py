#!/usr/bin/env python3
"""Plot 2026 vertical-profile similarity to strong and moderate composites."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/enso_strength_vertical_profiles_2026"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig_similarity"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache_similarity"))

import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.pyplot as plt


INPUT_CSV = OUT_DIR / "vertical_profile_pattern_similarity.csv"
SUMMARY_CSV = OUT_DIR / "vertical_profile_pattern_similarity_plot_values.csv"
FIGURE_PNG = OUT_DIR / "fig_2026_vertical_pattern_similarity_strong_vs_moderate.png"
FIGURE_PDF = OUT_DIR / "fig_2026_vertical_pattern_similarity_strong_vs_moderate.pdf"
MONTHLY_FIGURE_PNG = OUT_DIR / "fig_2026_vertical_pattern_similarity_monthly_only.png"
MONTHLY_FIGURE_PDF = OUT_DIR / "fig_2026_vertical_pattern_similarity_monthly_only.pdf"

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SUMMARY_PERIODS = ("JFM", "AMJ", "JFM+AMJ")
COLORS = {"strong": "#B33A3A", "moderate": "#2C7FB8"}
LABELS = {
    "strong": "Strong-event composite",
    "moderate": "Moderate-event composite",
}


def load_similarity() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(INPUT_CSV)
    frame = pd.read_csv(INPUT_CSV)
    required = {"period", "reference_class", "pattern_correlation", "n_points"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    expected = {(period, group) for period in (*MONTHS, *SUMMARY_PERIODS) for group in COLORS}
    observed = set(zip(frame.period, frame.reference_class))
    if expected.difference(observed):
        raise ValueError(f"Missing period/class rows: {sorted(expected.difference(observed))}")
    selected = frame.loc[
        frame.period.isin((*MONTHS, *SUMMARY_PERIODS))
        & frame.reference_class.isin(COLORS)
    ].copy()
    if selected.pattern_correlation.isna().any():
        raise ValueError("Pattern correlations contain missing values")
    return selected


def lookup(frame: pd.DataFrame, period: str, group: str) -> float:
    row = frame.loc[
        frame.period.eq(period) & frame.reference_class.eq(group),
        "pattern_correlation",
    ]
    if len(row) != 1:
        raise ValueError(f"Expected one value for {period}/{group}")
    return float(row.iloc[0])


def build_plot_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period in (*MONTHS, *SUMMARY_PERIODS):
        strong = lookup(frame, period, "strong")
        moderate = lookup(frame, period, "moderate")
        rows.append(
            {
                "period": period,
                "strong_pattern_correlation": strong,
                "moderate_pattern_correlation": moderate,
                "strong_minus_moderate_gap": strong - moderate,
            }
        )
    return pd.DataFrame(rows)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 9.7,
            "axes.titlesize": 11.5,
            "axes.labelsize": 10.0,
            "axes.linewidth": 0.9,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def draw_monthly_panel(ax_month: plt.Axes, frame: pd.DataFrame) -> None:
    x = np.arange(len(MONTHS), dtype=float)
    ax_month.axvspan(-0.45, 2.5, color="#E8F0F7", alpha=0.72, zorder=0)
    ax_month.axvspan(2.5, 5.45, color="#F8E9E7", alpha=0.72, zorder=0)
    ax_month.text(1.0, 0.955, "JFM", ha="center", va="top", color="#4E6E87", fontsize=9.2)
    ax_month.text(4.0, 0.955, "AMJ", ha="center", va="top", color="#8C4D48", fontsize=9.2)

    monthly_values: dict[str, np.ndarray] = {}
    for group in ("strong", "moderate"):
        values = np.array([lookup(frame, period, group) for period in MONTHS])
        monthly_values[group] = values
        ax_month.plot(
            x,
            values,
            color=COLORS[group],
            marker="o" if group == "strong" else "^",
            markersize=7.2,
            linewidth=2.25,
            markeredgecolor="white",
            markeredgewidth=0.75,
            label=LABELS[group],
            zorder=3,
        )
        for index, value in enumerate(values):
            offset = 0.038 if group == "strong" else -0.052
            va = "bottom" if group == "strong" else "top"
            ax_month.text(
                index,
                value + offset,
                f"{value:.2f}",
                ha="center",
                va=va,
                fontsize=8.0,
                color=COLORS[group],
            )

    ax_month.axvline(2.5, color="#555555", linestyle=(0, (3, 3)), linewidth=1.0)
    ax_month.fill_between(
        x[3:],
        monthly_values["moderate"][3:],
        monthly_values["strong"][3:],
        color="#8E5A91",
        alpha=0.10,
        zorder=1,
    )
    ax_month.axhline(0.0, color="#777777", linewidth=0.8)
    ax_month.set_xticks(x)
    ax_month.set_xticklabels(MONTHS)
    ax_month.set_xlim(-0.45, 5.45)
    ax_month.set_ylim(-0.18, 1.0)
    ax_month.set_ylabel("Spatial pattern correlation with 2026")
    ax_month.set_xlabel("Calendar month of the developing year")
    ax_month.grid(axis="y", color="#DDDDDD", linewidth=0.7)
    ax_month.spines[["top", "right"]].set_visible(False)
    ax_month.legend(loc="lower left", frameon=False, fontsize=9.0)


def plot_monthly_only(frame: pd.DataFrame) -> None:
    setup_style()
    fig, axis = plt.subplots(figsize=(7.9, 4.75))
    draw_monthly_panel(axis, frame)
    fig.subplots_adjust(left=0.105, right=0.985, top=0.975, bottom=0.15)
    fig.savefig(
        MONTHLY_FIGURE_PNG,
        dpi=320,
        bbox_inches="tight",
        pad_inches=0.08,
        facecolor="white",
    )
    fig.savefig(
        MONTHLY_FIGURE_PDF,
        bbox_inches="tight",
        pad_inches=0.08,
        facecolor="white",
    )
    plt.close(fig)


def plot(frame: pd.DataFrame, table: pd.DataFrame) -> None:
    setup_style()
    fig, (ax_month, ax_summary) = plt.subplots(
        1,
        2,
        figsize=(11.8, 5.25),
        gridspec_kw={"width_ratios": [1.72, 1.0]},
    )

    draw_monthly_panel(ax_month, frame)
    ax_month.text(
        -0.055,
        1.025,
        "a",
        transform=ax_month.transAxes,
        ha="left",
        va="bottom",
        fontweight="bold",
        fontsize=11.5,
    )

    summary_labels = ("JFM", "AMJ", "Jan-Jun\ncombined")
    y = np.arange(len(SUMMARY_PERIODS))[::-1]
    bar_height = 0.27
    for group, offset in (("strong", bar_height / 2), ("moderate", -bar_height / 2)):
        values = np.array([lookup(frame, period, group) for period in SUMMARY_PERIODS])
        bars = ax_summary.barh(
            y + offset,
            values,
            height=bar_height,
            color=COLORS[group],
            alpha=0.92,
            label=LABELS[group],
        )
        for bar, value in zip(bars, values):
            x_text = value + 0.025 if value >= 0 else value - 0.025
            ax_summary.text(
                x_text,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.2f}",
                ha="left" if value >= 0 else "right",
                va="center",
                fontsize=8.6,
                color=COLORS[group],
                fontweight="bold",
            )
    ax_summary.axvline(0.0, color="#777777", linewidth=0.8)
    ax_summary.set_yticks(y)
    ax_summary.set_yticklabels(summary_labels)
    ax_summary.set_xlim(-0.18, 1.0)
    ax_summary.set_xlabel("Spatial pattern correlation")
    ax_summary.text(
        -0.075,
        1.025,
        "b",
        transform=ax_summary.transAxes,
        ha="left",
        va="bottom",
        fontweight="bold",
        fontsize=11.5,
    )
    ax_summary.grid(axis="x", color="#DDDDDD", linewidth=0.7)
    ax_summary.spines[["top", "right"]].set_visible(False)

    fig.subplots_adjust(left=0.075, right=0.98, top=0.95, bottom=0.15, wspace=0.28)
    fig.savefig(FIGURE_PNG, dpi=320, bbox_inches="tight", pad_inches=0.12, facecolor="white")
    fig.savefig(FIGURE_PDF, bbox_inches="tight", pad_inches=0.12, facecolor="white")
    plt.close(fig)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_similarity()
    table = build_plot_table(frame)
    table.to_csv(SUMMARY_CSV, index=False)
    plot(frame, table)
    plot_monthly_only(frame)
    print(FIGURE_PNG)
    print(FIGURE_PDF)
    print(MONTHLY_FIGURE_PNG)
    print(MONTHLY_FIGURE_PDF)
    print(SUMMARY_CSV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
