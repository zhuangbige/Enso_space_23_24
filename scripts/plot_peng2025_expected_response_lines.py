#!/usr/bin/env python3
"""Plot Peng et al.-style expected atmospheric response lines.

The input table is the first-pass reproduction of the paper's Fig. 1 event
coupling diagnostics. It already contains Niño-3 SST anomalies, observed u10
and SOI anomalies, and their regression-expected values.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


INPUT = ROOT / "data/derived/peng2025_repro/tables/fig1_event_coupling.csv"
OUT_DIR = ROOT / "outputs/peng2025_repro/figures"
HIGHLIGHT_YEARS = [1982, 1997, 2015, 2023]


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8.5,
            "axes.linewidth": 0.85,
            "axes.unicode_minus": False,
        }
    )


def _fit_expected_line(df: pd.DataFrame, expected_col: str) -> tuple[float, float]:
    x = df["nino3"].to_numpy(dtype=float)
    y = df[expected_col].to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _annotate_years(ax, subset: pd.DataFrame, *, x_offset: float, y_offset: float) -> None:
    for row in subset.itertuples():
        ax.text(row.nino3 + x_offset, row.y_value + y_offset, str(int(row.year))[-2:], color="#c8332d", fontsize=8)


def plot_panel(
    ax,
    df: pd.DataFrame,
    *,
    observed_col: str,
    expected_col: str,
    ylabel: str,
    title: str,
    ratio_col: str,
    panel_label: str,
    expected_label_yoffset: float,
) -> None:
    slope, intercept = _fit_expected_line(df, expected_col)
    x_min = min(-2.1, float(df["nino3"].min()) - 0.25)
    x_max = max(2.8, float(df["nino3"].max()) + 0.25)
    x_line = np.linspace(x_min, x_max, 200)
    y_line = slope * x_line + intercept

    ax.scatter(df["nino3"], df[observed_col], s=28, color="0.72", edgecolor="white", linewidth=0.45, zorder=2, label="All years")
    ax.plot(x_line, y_line, color="#c8332d", ls="--", lw=1.6, zorder=1, label="Expected from historical regression")

    highlighted = df.loc[df["year"].isin(HIGHLIGHT_YEARS)].copy()
    highlighted["y_value"] = highlighted[observed_col]
    ax.scatter(
        highlighted["nino3"],
        highlighted[observed_col],
        s=58,
        color="#df3b2f",
        edgecolor="white",
        linewidth=0.65,
        zorder=3,
        label="Strong El Niño events",
    )
    _annotate_years(ax, highlighted, x_offset=0.04, y_offset=0.08 if expected_label_yoffset > 0 else -0.14)

    row_2023 = df.loc[df["year"].eq(2023)].iloc[0]
    x_2023 = float(row_2023["nino3"])
    y_obs = float(row_2023[observed_col])
    y_exp = float(row_2023[expected_col])
    ratio = float(row_2023[ratio_col])
    ax.scatter([x_2023], [y_exp], s=74, facecolors="none", edgecolors="#c8332d", linewidth=1.6, zorder=4)
    ax.plot([x_2023, x_2023], [y_obs, y_exp], color="#c8332d", lw=1.4, ls=(0, (3, 2)), zorder=3)
    ax.annotate(
        f"2023 expected\n{y_exp:.2f}",
        xy=(x_2023, y_exp),
        xytext=(x_2023 - 1.45, y_exp + expected_label_yoffset),
        arrowprops={"arrowstyle": "->", "color": "#c8332d", "lw": 1.0},
        fontsize=8.5,
        color="#8f1d18",
    )
    ax.annotate(
        f"observed / expected = {ratio:.2f}",
        xy=(x_2023, y_obs),
        xytext=(x_2023 - 1.62, y_obs - expected_label_yoffset * 0.45),
        arrowprops={"arrowstyle": "->", "color": "0.2", "lw": 0.9},
        fontsize=8.5,
        color="0.18",
    )

    ax.axhline(0, color="0.55", lw=0.75)
    ax.axvline(0, color="0.55", lw=0.75)
    ax.set_xlim(x_min, x_max)
    ax.set_xlabel("Niño-3 SST anomaly (°C)")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{panel_label}. {title}", loc="left", weight="bold")
    ax.grid(True, color="0.88", lw=0.6)
    ax.text(
        0.03,
        0.95,
        f"Expected = {slope:.2f} × Niño-3 {intercept:+.2f}",
        transform=ax.transAxes,
        va="top",
        fontsize=8.5,
        color="0.25",
        bbox={"facecolor": "white", "edgecolor": "0.85", "boxstyle": "round,pad=0.22", "alpha": 0.86},
    )


def main() -> int:
    setup_style()
    df = pd.read_csv(INPUT)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.7), constrained_layout=False)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.20, top=0.80, wspace=0.12)
    fig.suptitle("Historical expectation lines reveal weak 2023/24 atmospheric coupling", weight="bold", fontsize=14, y=0.96)

    plot_panel(
        axes[0],
        df,
        observed_col="uwind",
        expected_col="uwind_expected",
        ratio_col="uwind_coupling_ratio",
        ylabel="Equatorial Pacific u10 anomaly (m/s)",
        title="Surface westerly wind response",
        panel_label="a",
        expected_label_yoffset=0.72,
    )
    plot_panel(
        axes[1],
        df,
        observed_col="soi",
        expected_col="soi_expected",
        ratio_col="soi_coupling_ratio",
        ylabel="SOI anomaly",
        title="Pressure-gradient response",
        panel_label="b",
        expected_label_yoffset=-0.58,
    )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[:3], labels[:3], loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.895))
    fig.text(
        0.01,
        0.055,
        "Data: reproduced Peng et al. (2025) Fig. 1 coupling table. Gray dots are annual values; red dots mark 1982, 1997, 2015, and 2023. "
        "Open red circle marks the 2023 response expected from the historical Niño-3 regression.",
        fontsize=8.2,
        color="0.28",
    )

    for stem in ["fig_peng2025_expected_response_lines", "paper_style_expected_response_lines"]:
        fig.savefig(OUT_DIR / f"{stem}.png", bbox_inches="tight", pad_inches=0.18)
        fig.savefig(OUT_DIR / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.18)
    print(OUT_DIR / "fig_peng2025_expected_response_lines.png")
    print(OUT_DIR / "fig_peng2025_expected_response_lines.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
