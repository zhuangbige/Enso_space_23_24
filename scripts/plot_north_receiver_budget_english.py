#!/usr/bin/env python3
"""Plot the English CT/CP northern receiver-box warm-heat budget."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STYLE_DIR = Path("/Users/daiyue/.codex/skills/climate-plotting/scripts")
sys.path.insert(0, str(STYLE_DIR))
from climate_plot_style import apply_climate_style  # noqa: E402


SOURCE = ROOT / "data/derived/research_2026/soda3_north_receiver_budget_summary.csv"
OUT_DIR = ROOT / "outputs/research_2026/figures"
PNG = OUT_DIR / "northern_receiver_warm_heat_budget_CT_CP_english.png"
PDF = OUT_DIR / "northern_receiver_warm_heat_budget_CT_CP_english.pdf"

PHASE = "mature_decay_Dec0_to_May1"
COMPONENTS = [
    ("south_q20_in", "5°N input"),
    ("zonal_convergence", r"Zonal convergence, $C_{x,N}$"),
    ("north_q20_in", "12°N input term"),
    ("surface_warm", "Surface warm-layer term"),
    ("residual_warm", "Residual"),
    ("storage_tendency", "Storage tendency"),
]
GROUPS = ("CT", "CP")
COLORS = {"CT": "#D97706", "CP": "#2F7FBA"}


def load_summary() -> dict[tuple[str, str], tuple[float, float, float, int]]:
    selected: dict[tuple[str, str], tuple[float, float, float, int]] = {}
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["phase"] != PHASE or row["contrast"] not in GROUPS:
                continue
            key = (row["contrast"], row["component"])
            selected[key] = (
                float(row["mean_zj"]),
                float(row["ci_low_zj"]),
                float(row["ci_high_zj"]),
                int(row["n_events"]),
            )
    missing = [(group, component) for group in GROUPS for component, _ in COMPONENTS if (group, component) not in selected]
    if missing:
        raise ValueError(f"Missing summary rows: {missing}")
    return selected


def signed(value: float) -> str:
    sign = "+" if value >= 0 else "−"
    return f"{sign}{abs(value):.2f}"


def main() -> None:
    summary = load_summary()
    apply_climate_style(base_font_size=12)
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 400,
        }
    )

    fig, ax = plt.subplots(figsize=(13.6, 6.45))
    fig.subplots_adjust(left=0.255, right=0.975, top=0.79, bottom=0.22)

    y = np.arange(len(COMPONENTS))[::-1]
    offsets = {"CT": +0.16, "CP": -0.16}

    for group in GROUPS:
        means = np.array([summary[(group, component)][0] for component, _ in COMPONENTS])
        lows = np.array([summary[(group, component)][1] for component, _ in COMPONENTS])
        highs = np.array([summary[(group, component)][2] for component, _ in COMPONENTS])
        y_group = y + offsets[group]
        errors = np.vstack([means - lows, highs - means])
        n_events = summary[(group, COMPONENTS[0][0])][3]
        ax.errorbar(
            means,
            y_group,
            xerr=errors,
            fmt="o",
            ms=9.5,
            mfc=COLORS[group],
            mec="white",
            mew=0.9,
            ecolor=COLORS[group],
            elinewidth=2.1,
            capsize=5.5,
            capthick=2.0,
            label=f"{group} (n={n_events})",
            zorder=4,
        )

        for index, (value, ypos) in enumerate(zip(means, y_group, strict=True)):
            # Separate the close-to-zero and close-positive pairs vertically.
            if group == "CT":
                dy = 0.17
                va = "bottom"
            else:
                dy = -0.17
                va = "top"
            dx = 0.09 if value >= -0.25 else 0.10
            ax.text(
                value + dx,
                ypos + dy,
                signed(value),
                color=COLORS[group],
                fontsize=12.2,
                fontweight="bold",
                ha="left",
                va=va,
                zorder=5,
            )

    ax.axvline(0, color="#102A43", linewidth=1.8, zorder=2)
    ax.set_xlim(-3.35, 5.05)
    ax.set_xticks(np.arange(-3, 6, 1))
    ax.set_yticks(y, [label for _, label in COMPONENTS])
    ax.set_ylim(-0.58, len(COMPONENTS) - 0.42)
    ax.set_xlabel("Cumulative anomalous warm-heat contribution (ZJ)", fontsize=13.5, fontweight="bold", color="#183B56", labelpad=12)
    ax.tick_params(axis="x", labelsize=11.5, colors="#334E68", length=0)
    ax.tick_params(axis="y", labelsize=13, colors="#102A43", length=0, pad=14)
    for label in ax.get_yticklabels():
        label.set_fontweight("bold")

    ax.grid(axis="x", color="#D9E2EC", linewidth=0.8, zorder=0)
    for boundary in np.arange(0.5, len(COMPONENTS) - 0.5, 1):
        ax.axhline(boundary, color="#E6ECF0", linewidth=0.8, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.text(
        0.055,
        0.93,
        "Northern receiver-box warm-heat budget",
        fontsize=22,
        fontweight="bold",
        color="#102A43",
        ha="left",
    )
    fig.text(
        0.055,
        0.872,
        "Cumulative anomalies, Dec(0)–May(+1)",
        fontsize=15,
        fontweight="bold",
        color="#486581",
        ha="left",
    )
    fig.text(
        0.055,
        0.823,
        "Receiver box: 5°–12°N, 140°W–80°W, 0–300 m",
        fontsize=12.2,
        color="#627D98",
        ha="left",
    )

    legend = fig.legend(
        loc="upper right",
        bbox_to_anchor=(0.967, 0.938),
        ncol=2,
        frameon=False,
        handletextpad=0.5,
        columnspacing=1.6,
        fontsize=13.2,
    )
    for text, group in zip(legend.get_texts(), GROUPS, strict=True):
        text.set_color(COLORS[group])
        text.set_fontweight("bold")

    fig.text(
        0.055,
        0.075,
        "Positive values add H₂₀ to the receiver box; negative values remove it. "
        "Dots show event means and whiskers show 95% event-bootstrap confidence intervals.",
        fontsize=10.3,
        color="#526675",
        ha="left",
    )
    fig.text(
        0.055,
        0.035,
        "Source: SODA3.15.2; CT and CP composites each contain four events.",
        fontsize=9.8,
        color="#6B7C89",
        ha="left",
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=400, facecolor="white", bbox_inches="tight")
    fig.savefig(PDF, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(PNG)
    print(PDF)


if __name__ == "__main__":
    main()
