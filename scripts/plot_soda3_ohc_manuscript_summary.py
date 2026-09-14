#!/usr/bin/env python3
"""Create manuscript figures for the OHC-only ENSO analysis."""

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


PHASE_CSV = ROOT / "data/derived/research_2026/soda3_ohc_only_phase_summary_13events.csv"
TYPE_CSV = ROOT / "data/derived/research_2026/soda3_ohc_only_ct_cp_summary.csv"
TYPE_COMPARE_CSV = ROOT / "data/derived/research_2026/soda3_ohc_vs_h20_ct_cp_comparison.csv"
OUT = ROOT / "outputs/research_2026/ohc_only_three_questions"
EVENT_FIGURE = OUT / "Fig02_OHC_event_storage_release_transport.png"
TYPE_FIGURE = OUT / "Fig03_OHC_CT_CP_comparison.png"

EVENTS = (1997, 2015, 2023)
COLORS = {1997: "#B62F3A", 2015: "#2B6F9F", 2023: "#D98218"}
REFERENCES = (0, 10, 20)


def style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="0.88", linewidth=0.7, zorder=0)
    axis.axhline(0.0, color="0.28", linewidth=0.9, zorder=1)
    axis.tick_params(labelsize=9)


def annotate_bars(axis: plt.Axes, bars, fmt="{:+.2f}") -> None:
    for bar in bars:
        height = float(bar.get_height())
        offset = 0.25 if height >= 0 else -0.38
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            height + offset,
            fmt.format(height),
            ha="center",
            va="bottom" if height >= 0 else "top",
            fontsize=8.4,
            fontweight="bold",
        )


def make_event_figure() -> None:
    phase = pd.read_csv(PHASE_CSV)
    phase = phase.loc[phase.baseline.eq("1980-2014") & phase.event_year.isin(EVENTS)]
    development = phase.loc[phase.phase.eq("development_Jan0_Jun0")].set_index("event_year")
    decay = phase.loc[phase.phase.eq("decay_Jan1_May1")].set_index("event_year")
    x = np.arange(len(EVENTS))
    event_colors = [COLORS[year] for year in EVENTS]

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.4), constrained_layout=True)
    ax = axes[0, 0]
    values = [development.loc[year, "east_ohc300_change_zj"] for year in EVENTS]
    bars = ax.bar(x, values, width=0.62, color=event_colors, zorder=2)
    annotate_bars(ax, bars)
    ax.set_xticks(x, EVENTS)
    ax.set_ylabel("East-box OHC change (ZJ)")
    ax.set_title("a  Development: heat stored east of 140°W")
    style_axis(ax)

    ax = axes[0, 1]
    losses = [-decay.loc[year, "east_ohc300_change_zj"] for year in EVENTS]
    surface = [decay.loc[year, "east_surface_loss_zj"] for year in EVENTS]
    width = 0.34
    bars1 = ax.bar(x - width / 2, losses, width, color=event_colors, zorder=2, label="OHC decrease")
    bars2 = ax.bar(x + width / 2, surface, width, color="white", edgecolor=event_colors, linewidth=1.8, zorder=2, label="Surface heat loss")
    annotate_bars(ax, bars1)
    annotate_bars(ax, bars2)
    ax.set_xticks(x, EVENTS)
    ax.set_ylabel("Heat release/loss (ZJ)")
    ax.set_title("b  Following Jan–May: storage release")
    ax.legend(frameon=False, fontsize=8.5)
    style_axis(ax)

    for panel, metric, title in (
        ((1, 0), "qvt_5n_north_tref{reference:02d}_zj", "c  Total 5°N heat transport"),
        ((1, 1), "qekman_5n_north_tref{reference:02d}_zj", "d  First-order Ekman contribution"),
    ):
        ax = axes[panel]
        for index, year in enumerate(EVENTS):
            values = np.array(
                [decay.loc[year, metric.format(reference=reference)] for reference in REFERENCES],
                dtype=float,
            )
            ax.vlines(index, values.min(), values.max(), color=COLORS[year], linewidth=5, alpha=0.72, zorder=2)
            ax.scatter(
                np.full(len(REFERENCES), index),
                values,
                color=COLORS[year],
                edgecolor="white",
                linewidth=0.6,
                s=38,
                zorder=3,
            )
            ax.scatter(index, values[1], marker="D", color="black", s=24, zorder=4)
        ax.set_xticks(x, EVENTS)
        ax.set_ylabel("Northward heat transport (ZJ)")
        ax.set_title(title)
        style_axis(ax)
    axes[1, 0].text(
        0.02,
        0.04,
        "Colored range: Tref = 0, 10, 20°C; black diamond: 10°C",
        transform=axes[1, 0].transAxes,
        fontsize=7.7,
        color="0.30",
    )
    axes[1, 1].text(
        0.02,
        0.04,
        "Positive values denote northward export",
        transform=axes[1, 1].transAxes,
        fontsize=7.7,
        color="0.30",
    )
    fig.suptitle(
        "Eastern-Pacific 0–300 m OHC: arrival, release and 5°N redistribution",
        fontsize=14,
        fontweight="bold",
    )
    fig.savefig(EVENT_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def type_metric(table: pd.DataFrame, event_class: str, phase: str, metric: str) -> pd.Series:
    return table.loc[
        table.event_class.eq(event_class)
        & table.phase.eq(phase)
        & table.metric.eq(metric)
    ].iloc[0]


def make_type_figure() -> None:
    types = pd.read_csv(TYPE_CSV)
    compare = pd.read_csv(TYPE_COMPARE_CSV)
    classes = ("CT", "CP")
    colors = {"CT": "#B62F3A", "CP": "#2B6F9F"}
    x = np.arange(2)
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.3), constrained_layout=True)

    ax = axes[0]
    means, lows, highs = [], [], []
    for event_class in classes:
        row = type_metric(types, event_class, "development_Jan0_Jun0", "east_ohc300_change_zj")
        means.append(row["mean"])
        lows.append(row["mean"] - row["ci95_low"])
        highs.append(row["ci95_high"] - row["mean"])
    bars = ax.bar(x, means, color=[colors[c] for c in classes], width=0.58, zorder=2)
    ax.errorbar(x, means, yerr=np.vstack([lows, highs]), fmt="none", ecolor="black", capsize=4, linewidth=1.1, zorder=3)
    annotate_bars(ax, bars)
    ax.set_xticks(x, ["Cold-tongue (CT)", "Central-Pacific (CP)"])
    ax.set_ylabel("East-box OHC change (ZJ)")
    ax.set_title("a  Development Jan–Jun")
    style_axis(ax)

    ax = axes[1]
    positions = {("CT", "total"): -0.18, ("CT", "ekman"): 0.18, ("CP", "total"): 0.82, ("CP", "ekman"): 1.18}
    for class_index, event_class in enumerate(classes):
        for label, quantity, marker in (
            ("total", "5n_northward_transport", "o"),
            ("ekman", "5n_ekman_transport", "s"),
        ):
            row = compare.loc[
                compare.event_class.eq(event_class)
                & compare.phase.eq("decay_Jan1_May1")
                & compare.quantity.eq(quantity)
            ].iloc[0]
            values = np.array([row.ohc_tref0_mean_zj, row.ohc_tref10_mean_zj, row.ohc_tref20_mean_zj])
            xpos = positions[(event_class, label)]
            ax.vlines(xpos, values.min(), values.max(), color=colors[event_class], linewidth=5, alpha=0.72, zorder=2)
            ax.scatter(xpos, values[1], marker=marker, color="black", s=38, zorder=3)
    ax.set_xticks(x, ["CT", "CP"])
    ax.set_ylabel("Northward 5°N heat transport (ZJ)")
    ax.set_title("b  Following Jan–May transport")
    ax.scatter([], [], marker="o", color="black", label="Total vT")
    ax.scatter([], [], marker="s", color="black", label="Ekman")
    ax.legend(frameon=False, fontsize=8.5)
    style_axis(ax)
    fig.suptitle(
        "CT–CP contrast in the OHC-only framework (four events per class)",
        fontsize=13.5,
        fontweight="bold",
    )
    fig.text(
        0.5,
        -0.02,
        "Error bars in (a): event-bootstrap 95% interval. Colored ranges in (b): Tref = 0, 10 and 20°C.",
        ha="center",
        fontsize=8,
        color="0.30",
    )
    fig.savefig(TYPE_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    make_event_figure()
    make_type_figure()
    print(EVENT_FIGURE)
    print(TYPE_FIGURE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
