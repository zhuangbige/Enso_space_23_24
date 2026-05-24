#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def save(fig: plt.Figure, name: str) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(ASSET_DIR / name, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def style_axes(ax, title: str, ylabel: str | None = None) -> None:
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#d8d1c4", linewidth=0.8, alpha=0.8)
    ax.tick_params(axis="both", labelsize=9)


def coupling_bars() -> None:
    rows = [row for row in read_csv(ROOT / "data/derived/peng2025_repro/tables/fig1_event_coupling.csv") if row["highlight"] == "True"]
    years = [row["year"] for row in rows]
    u = [float(row["uwind_coupling_ratio"]) for row in rows]
    soi = [float(row["soi_coupling_ratio"]) for row in rows]

    x = np.arange(len(years))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    fig.patch.set_facecolor("#f7f3ea")
    ax.set_facecolor("#f7f3ea")
    ax.bar(x - width / 2, u, width, label="u10 coupling ratio", color="#cc5a43")
    ax.bar(x + width / 2, soi, width, label="SOI coupling ratio", color="#2f6f73")
    ax.axhline(1, color="#2b2b2b", linewidth=1.2)
    ax.set_xticks(x, years)
    ax.set_ylim(0, 2.1)
    style_axes(ax, "Paper Fig. 1 table: 2023/24 atmospheric coupling was only about one-third of expectation", "Observed / expected")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    for xpos, value in zip(x - width / 2, u):
        ax.text(xpos, value + 0.04, f"{value:.2f}", ha="center", fontsize=8)
    for xpos, value in zip(x + width / 2, soi):
        ax.text(xpos, value + 0.04, f"{value:.2f}", ha="center", fontsize=8)
    save(fig, "coupling_ratios.png")


def seasonal_decoupling() -> None:
    rows = read_csv(ROOT / "data/derived/research/seasonal_decoupling_first_pass.csv")
    seasons = ["AMJ", "JJA", "SON", "DJF"]
    metrics = {
        "nino3_sst_oisst": ("Niño-3 SST", "#cc5a43"),
        "cwp_u_ncep_sig995": ("CWP u proxy", "#2f6f73"),
        "soi_like_ncep": ("SOI-like proxy", "#4a5f99"),
    }
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    fig.patch.set_facecolor("#f7f3ea")
    ax.set_facecolor("#f7f3ea")
    for metric, (label, color) in metrics.items():
        values = []
        for season in seasons:
            row = next(row for row in rows if row["metric"] == metric and row["season"] == season)
            values.append(float(row["difference_2023_minus_comparable"]))
        ax.plot(seasons, values, marker="o", linewidth=2.5, markersize=7, label=label, color=color)
    ax.axhline(0, color="#2b2b2b", linewidth=1)
    style_axes(ax, "Seasonal split: Pacific warming starts early, but wind and pressure responses lag far behind", "2023 minus 1982/1997/2015 composite")
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    save(fig, "seasonal_decoupling.png")


def external_basin_bars() -> None:
    rows = read_csv(ROOT / "data/derived/research/external_basin_seasonal_summary.csv")
    regions = [
        ("tropical_north_atlantic", "Tropical North Atlantic"),
        ("western_pacific_warm_pool", "W. Pacific warm pool"),
        ("maritime_continent", "Maritime Continent"),
        ("tropical_indian_ocean", "Tropical Indian Ocean"),
    ]
    seasons = ["AMJ", "JJA"]
    x = np.arange(len(regions))
    width = 0.34
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    fig.patch.set_facecolor("#f7f3ea")
    ax.set_facecolor("#f7f3ea")
    for offset, season, color in [(-width / 2, "AMJ", "#cc5a43"), (width / 2, "JJA", "#2f6f73")]:
        values = []
        for region, _ in regions:
            row = next(row for row in rows if row["region"] == region and row["season"] == season)
            values.append(float(row["difference_2023_minus_comparable"]))
        ax.bar(x + offset, values, width, label=season, color=color)
        for xpos, value in zip(x + offset, values):
            ax.text(xpos, value + 0.035, f"{value:.2f}", ha="center", fontsize=8)
    ax.axhline(0, color="#2b2b2b", linewidth=1)
    ax.set_xticks(x, [label for _, label in regions], rotation=15, ha="right")
    ax.set_ylim(0, 1.55)
    style_axes(ax, "New diagnostic: 2023 spring-summer extra-Pacific warmth was unusually strong", "SST anomaly difference (°C)")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    save(fig, "external_basin_bars.png")


def validation_summary() -> None:
    labels = ["OISST vs Fig.1\nNiño-3 corr.", "NCEP u vs Fig.1\ncorr.", "NCEP SOI-like\nvs Fig.1 corr."]
    values = [0.9999, 0.9583, 0.9914]
    colors = ["#cc5a43", "#2f6f73", "#4a5f99"]
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    fig.patch.set_facecolor("#f7f3ea")
    ax.set_facecolor("#f7f3ea")
    bars = ax.bar(np.arange(len(labels)), values, color=colors, width=0.55)
    ax.set_ylim(0.9, 1.01)
    ax.set_xticks(np.arange(len(labels)), labels)
    style_axes(ax, "Raw-product checks reproduce the paper-level signal", "Correlation")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.002, f"{value:.4f}", ha="center", fontsize=9)
    save(fig, "validation_summary.png")


def main() -> int:
    coupling_bars()
    seasonal_decoupling()
    external_basin_bars()
    validation_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
