#!/usr/bin/env python3
"""Render the three core figures for the minimal ENSO coupling closure."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs/research_2026/air_sea_coupling_minimal"
LINK_ORDER = (
    "atmospheric",
    "ocean_adjustment",
    "thermocline_feedback",
    "thermal_damping",
)
LINK_TITLES = {
    "atmospheric": "SST -> zonal wind stress",
    "ocean_adjustment": "Zonal wind stress -> D20 slope",
    "thermocline_feedback": "Eastern D20 -> Nino3 SST",
    "thermal_damping": "Nino3 SST -> net heat-flux damping",
}
EVENT_COLORS = {"1997/98": "#3B6FB6", "2015/16": "#2A9D6F", "2023/24": "#D1495B"}
EVENT_MARKERS = {"1997/98": "o", "2015/16": "s", "2023/24": "D"}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.titlesize": 11,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "figure.dpi": 120,
            "savefig.dpi": 320,
            "savefig.bbox": "tight",
        }
    )


def _save(fig: plt.Figure, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".png"), facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), facecolor="white")
    plt.close(fig)


def plot_event_realization(scores: pd.DataFrame, pseudo: pd.DataFrame, output: Path) -> None:
    primary = scores[
        (scores["product_combo"] == "OISST+ERA5")
        & (scores["event"].isin(EVENT_COLORS))
        & (scores["status"] == "complete_event")
    ].copy()
    all_values = np.concatenate(
        [
            pseudo["eta"].dropna().to_numpy(float),
            primary["ci_low"].dropna().to_numpy(float),
            primary["ci_high"].dropna().to_numpy(float),
        ]
    )
    lower = min(-0.5, float(np.nanquantile(all_values, 0.01)) - 0.15)
    upper = max(1.5, float(np.nanquantile(all_values, 0.99)) + 0.15)

    fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.1), sharey=True)
    rng = np.random.default_rng(20260716)
    for panel, (axis, link) in enumerate(zip(axes.flat, LINK_ORDER)):
        history = pseudo[pseudo["link"] == link]["eta"].dropna().to_numpy(float)
        jitter = rng.uniform(-0.12, 0.12, len(history))
        axis.scatter(jitter, history, s=15, color="#B8BEC7", alpha=0.65, linewidths=0, label="Historical pseudo-events")
        p05, p95 = np.quantile(history, [0.05, 0.95])
        axis.fill_between([-0.28, 0.28], p05, p95, color="#DDE2E8", alpha=0.55, zorder=0)
        axis.axhline(1, color="#333333", linewidth=1, linestyle="--", label="Historical realization (eta=1)")
        for index, event in enumerate(EVENT_COLORS, start=1):
            row = primary[(primary["link"] == link) & (primary["event"] == event)].iloc[0]
            eta = float(row["eta"])
            low = float(row["ci_low"])
            high = float(row["ci_high"])
            axis.errorbar(
                index,
                eta,
                yerr=[[eta - low], [high - eta]],
                fmt=EVENT_MARKERS[event],
                markersize=6.5,
                color=EVENT_COLORS[event],
                markeredgecolor="white",
                markeredgewidth=0.7,
                capsize=3,
                linewidth=1.2,
                label=event,
                zorder=3,
            )
            if bool(row["significantly_weakened"]):
                axis.text(index, high + 0.06 * (upper - lower), "*", ha="center", va="bottom", color=EVENT_COLORS[event], fontsize=14)
        axis.set_title(f"({chr(97 + panel)}) {LINK_TITLES[link]}", loc="left", weight="bold")
        axis.set_xticks([0, 1, 2, 3], ["History", "1997/98", "2015/16", "2023/24"], rotation=18)
        axis.set_xlim(-0.45, 3.45)
        axis.set_ylim(lower, upper)
        axis.grid(axis="y", color="#E6E8EB", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0, 0].set_ylabel("Event realization eta (unitless)")
    axes[1, 0].set_ylabel("Event realization eta (unitless)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    fig.legend(unique.values(), unique.keys(), loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 0.005))
    fig.suptitle("Realization of the four-link air-sea coupling chain", fontsize=14, weight="bold", y=0.985)
    fig.text(
        0.5,
        0.045,
        "Baseline: 1982-2022; event window: April-February. Error bars: 24-month block bootstrap 95% CI. * predefined weakening criterion met.",
        ha="center",
        fontsize=8.5,
        color="#4B5563",
    )
    fig.subplots_adjust(bottom=0.15, top=0.91, hspace=0.28, wspace=0.14)
    _save(fig, output)


def plot_monthly_observed_expected(diagnostics: pd.DataFrame, output: Path) -> None:
    target = diagnostics[
        (diagnostics["event"] == "2023/24") & (diagnostics["product_combo"] == "OISST+ERA5")
    ].copy()
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.4))
    for panel, (axis, link) in enumerate(zip(axes.flat, LINK_ORDER)):
        frame = target[target["link"] == link].sort_values("time")
        time = pd.to_datetime(frame["time"])
        observed = frame["observed_innovation"].to_numpy(float)
        expected = frame["expected_feedback"].to_numpy(float)
        residual = frame["residual"].to_numpy(float)
        axis.bar(time, residual, width=20, color=np.where(residual >= 0, "#A7D8D2", "#F4B6B2"), alpha=0.75, label="Residual")
        axis.plot(time, observed, color="#222222", marker="o", linewidth=1.8, markersize=4.2, label="Observed innovation")
        axis.plot(time, expected, color="#E07A25", marker="s", linewidth=1.6, markersize=3.8, label="Expected feedback")
        axis.axhline(0, color="#666666", linewidth=0.7)
        axis.set_title(f"({chr(97 + panel)}) {LINK_TITLES[link]}", loc="left", weight="bold")
        axis.set_ylabel(str(frame["target_units"].iloc[0]))
        axis.set_xticks(time, [value.strftime("%b") for value in time], rotation=0)
        axis.grid(axis="y", color="#E6E8EB", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle("2023/24 monthly observed versus historically expected feedback", fontsize=14, weight="bold", y=0.985)
    fig.text(
        0.5,
        0.05,
        "Innovation removes the fitted seasonal intercept and, where applicable, the previous-month persistence term.",
        ha="center",
        fontsize=8.5,
        color="#4B5563",
    )
    fig.subplots_adjust(bottom=0.14, top=0.91, hspace=0.31, wspace=0.22)
    _save(fig, output)


def plot_ocean_memory_forcing(memory: pd.DataFrame, output: Path) -> None:
    frame = memory[(memory["event"] == "2023/24") & (memory["link"] == "ocean_adjustment")].copy()
    frame = frame.sort_values("time")
    time = pd.to_datetime(frame["target_time"])
    memory_values = frame["memory_contribution"].to_numpy(float)
    wind_values = frame["expected_feedback"].to_numpy(float)
    intercept = frame["intercept"].to_numpy(float)
    actual = frame["actual_target"].to_numpy(float)
    predicted = frame["predicted_target"].to_numpy(float)

    fig, axes = plt.subplots(2, 1, figsize=(10.3, 7.0), sharex=True, gridspec_kw={"height_ratios": [1.35, 1]})
    width = 20
    axes[0].bar(time, memory_values, width=width, color="#3B6FB6", label="D20 persistence (ocean memory)")
    axes[0].bar(time, wind_values, width=width, bottom=memory_values, color="#E9A03B", label="Wind-stress feedback")
    axes[0].bar(time, intercept, width=width, bottom=memory_values + wind_values, color="#B8BEC7", label="Seasonal intercept")
    axes[0].plot(time, actual, color="#111111", marker="o", linewidth=1.8, label="Observed D20 slope")
    axes[0].plot(time, predicted, color="#7A3E9D", linestyle="--", marker="s", linewidth=1.4, label="Model prediction")
    axes[0].axhline(0, color="#666666", linewidth=0.7)
    axes[0].set_ylabel("D20 slope anomaly (m)")
    axes[0].set_title("(a) One-month D20 slope decomposition", loc="left", weight="bold")
    axes[0].grid(axis="y", color="#E6E8EB", linewidth=0.7)
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[0].legend(ncol=2, frameon=False, fontsize=8.3, loc="best")

    axes[1].plot(time, np.cumsum(memory_values), color="#3B6FB6", marker="o", linewidth=2, label="Cumulative memory")
    axes[1].plot(time, np.cumsum(wind_values), color="#E9A03B", marker="s", linewidth=2, label="Cumulative wind feedback")
    axes[1].axhline(0, color="#666666", linewidth=0.7)
    axes[1].set_ylabel("Running sum of monthly terms (m)")
    axes[1].set_title("(b) Running sum for relative-weight comparison", loc="left", weight="bold")
    axes[1].set_xticks(time, [value.strftime("%b\n%Y") if value.month == 1 else value.strftime("%b") for value in time])
    axes[1].grid(axis="y", color="#E6E8EB", linewidth=0.7)
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].legend(ncol=2, frameon=False, loc="best")
    fig.suptitle("Ocean memory versus contemporaneous wind forcing in 2023/24", fontsize=14, weight="bold", y=0.985)
    fig.text(
        0.5,
        0.02,
        "D20 slope = eastern (150W-100W) minus western (140E-170W) equatorial D20; positive values indicate a deeper eastern thermocline.",
        ha="center",
        fontsize=8.5,
        color="#4B5563",
    )
    fig.subplots_adjust(bottom=0.1, top=0.91, hspace=0.28)
    _save(fig, output)


def run(output_dir: Path) -> None:
    configure_style()
    table_dir = output_dir / "tables"
    figure_dir = output_dir / "figures"
    scores = pd.read_csv(table_dir / "coupling_event_scores.csv", parse_dates=["start", "end"])
    pseudo = pd.read_csv(table_dir / "historical_pseudo_event_eta.csv")
    diagnostics = pd.read_csv(
        table_dir / "coupling_event_monthly_diagnostics.csv", parse_dates=["time", "target_time"]
    )
    memory = pd.read_csv(table_dir / "coupling_memory_forcing.csv", parse_dates=["time", "target_time"])
    plot_event_realization(scores, pseudo, figure_dir / "fig1_event_link_realization")
    plot_monthly_observed_expected(diagnostics, figure_dir / "fig2_2023_monthly_observed_expected")
    plot_ocean_memory_forcing(memory, figure_dir / "fig3_2023_ocean_memory_vs_wind")
    print(figure_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.output_dir)
