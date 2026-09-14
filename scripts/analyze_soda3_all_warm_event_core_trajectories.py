#!/usr/bin/env python3
"""Track January--June warm-anomaly cores for all 13 warm events."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/soda3_all_warm_event_core_trajectories"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache"))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import analyze_soda3_warm_anomaly_centroid_trajectories as centroid
import plot_soda3_monthly_ohc_vertical_sections as vertical


EVENT_FILE = ROOT / "data/derived/research_2026/enso_type_coupling_event_summary.csv"
EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
GROUP_COLORS = {
    "classic EP": "#D55E00",
    "CP": "#009E73",
    "other warm": "#0072B2",
    "2023 weak-coupling EP": "#7A3DB8",
}
GROUP_LABELS = {
    "classic EP": "Classic EP",
    "CP": "CP",
    "other warm": "Other warm",
    "2023 weak-coupling EP": "2023 weak-coupling EP",
}
HIGHLIGHT_COLORS = {1997: "#0072B2", 2015: "#D55E00", 2023: "#7A3DB8"}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def load_event_manifest() -> pd.DataFrame:
    manifest = pd.read_csv(EVENT_FILE)[["year", "group"]].copy()
    manifest["year"] = manifest.year.astype(int)
    if tuple(manifest.year) != EVENTS:
        raise ValueError(f"Unexpected 13-event sample: {tuple(manifest.year)}")
    missing_groups = set(manifest.group).difference(GROUP_COLORS)
    if missing_groups:
        raise ValueError(f"Unknown event groups: {sorted(missing_groups)}")
    return manifest


def build_heat_density(events: tuple[int, ...]) -> xr.Dataset:
    with vertical.open_dataset(vertical.TEMP_FILE) as source:
        vertical.validate_input(source)
        equatorial = vertical.equatorial_mean_temperature(source).load()
    anomaly = vertical.detrended_same_month_anomaly(equatorial)
    diagnostics = vertical.build_diagnostics(anomaly, list(events))
    diagnostics.attrs["event_sample"] = "13 warm development years"
    return diagnostics


def build_centroid_table(dataset: xr.Dataset, manifest: pd.DataFrame) -> pd.DataFrame:
    field = dataset.heat_content_density_anomaly
    cell_area = centroid.geometry_weights(field)
    groups = dict(zip(manifest.year, manifest.group))
    records: list[dict[str, object]] = []
    for event in EVENTS:
        for month in MONTHS:
            selected = field.where(
                (field.time.dt.year == event) & (field.time.dt.month == month),
                drop=True,
            )
            if selected.sizes.get("time", 0) != 1:
                raise ValueError(f"Expected one field for {event}-{month:02d}")
            metrics = centroid.weighted_centroid(selected.isel(time=0), cell_area)
            records.append(
                {
                    "event": event,
                    "group": groups[event],
                    "month": month,
                    "month_label": MONTH_LABELS[month - 1],
                    **metrics,
                }
            )
    table = pd.DataFrame(records).sort_values(["event", "month"]).reset_index(drop=True)
    expected = len(EVENTS) * len(MONTHS)
    if len(table) != expected:
        raise AssertionError(f"Expected {expected} rows, got {len(table)}")
    return table


def build_event_summary(table: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for event in EVENTS:
        selected = table.loc[table.event.eq(event)].sort_values("month")
        january = selected.iloc[0]
        june = selected.iloc[-1]
        records.append(
            {
                "event": event,
                "group": january.group,
                "january_lon_e": january.centroid_lon_e,
                "january_depth_m": january.centroid_depth_m,
                "june_lon_e": june.centroid_lon_e,
                "june_depth_m": june.centroid_depth_m,
                "jan_to_jun_eastward_displacement_deg": (
                    june.centroid_lon_e - january.centroid_lon_e
                ),
                "jan_to_jun_upward_displacement_m": (
                    january.centroid_depth_m - june.centroid_depth_m
                ),
                "positive_section_heat_change_pj_per_m": (
                    june.positive_section_heat_pj_per_m
                    - january.positive_section_heat_pj_per_m
                ),
            }
        )
    return pd.DataFrame(records)


def format_lon(value: float) -> str:
    return centroid.format_lon(value)


def format_phase_axis(
    ax: plt.Axes,
    *,
    show_xlabel: bool,
    show_ylabel: bool,
) -> None:
    longitude_ticks = (120, 180, 240, 280)
    ax.set_xlim(120, 280)
    ax.set_ylim(235, 35)
    ax.set_xticks(longitude_ticks)
    ax.set_xticklabels([format_lon(value) for value in longitude_ticks])
    ax.set_yticks((50, 100, 150, 200))
    ax.grid(True, color="0.89", linewidth=0.6)
    if show_xlabel:
        ax.set_xlabel("Warm-centroid longitude")
    else:
        ax.tick_params(labelbottom=False)
    if show_ylabel:
        ax.set_ylabel("Depth (m)")
    else:
        ax.tick_params(labelleft=False)


def draw_monthly_path(
    ax: plt.Axes,
    selected: pd.DataFrame,
    *,
    color: str,
    annotate_months: bool,
    line_width: float,
    alpha: float,
    marker_size: float,
    zorder: int,
) -> None:
    selected = selected.sort_values("month")
    ax.plot(
        selected.centroid_lon_e,
        selected.centroid_depth_m,
        color=color,
        linewidth=line_width,
        alpha=alpha,
        zorder=zorder,
    )
    for first, second in zip(selected.iloc[:-1].itertuples(), selected.iloc[1:].itertuples()):
        ax.annotate(
            "",
            xy=(second.centroid_lon_e, second.centroid_depth_m),
            xytext=(first.centroid_lon_e, first.centroid_depth_m),
            arrowprops={
                "arrowstyle": "-|>",
                "color": color,
                "lw": max(0.8, line_width - 0.25),
                "alpha": alpha,
                "mutation_scale": 8,
                "shrinkA": 5,
                "shrinkB": 5,
            },
            zorder=zorder + 1,
        )
    ax.scatter(
        selected.centroid_lon_e,
        selected.centroid_depth_m,
        s=marker_size,
        color=color,
        edgecolor="white",
        linewidth=0.7,
        alpha=alpha,
        zorder=zorder + 2,
    )
    if annotate_months:
        for row in selected.itertuples():
            ax.text(
                row.centroid_lon_e,
                row.centroid_depth_m,
                str(row.month),
                ha="center",
                va="center",
                fontsize=6.5,
                fontweight="bold",
                color="white",
                zorder=zorder + 3,
            )


def save_figure(fig: plt.Figure, stem: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print(png)
    print(pdf)
    return png, pdf


def plot_small_multiples(table: pd.DataFrame) -> tuple[Path, Path]:
    fig, axes = plt.subplots(3, 5, figsize=(17.0, 10.5), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.058, right=0.985, top=0.88, bottom=0.105, wspace=0.10, hspace=0.23)
    fig.suptitle(
        "January–June warm-anomaly core trajectories across 13 warm events",
        fontsize=16.0,
        fontweight="bold",
        y=0.975,
    )
    flat = axes.ravel()
    for index, event in enumerate(EVENTS):
        ax = flat[index]
        selected = table.loc[table.event.eq(event)].sort_values("month")
        group = str(selected.group.iloc[0])
        color = GROUP_COLORS[group]
        draw_monthly_path(
            ax,
            selected,
            color=color,
            annotate_months=True,
            line_width=1.8,
            alpha=0.95,
            marker_size=46.0,
            zorder=2,
        )
        row, column = divmod(index, 5)
        format_phase_axis(
            ax,
            show_xlabel=row == 2,
            show_ylabel=column == 0,
        )
        ax.set_title(
            f"{event}  |  {GROUP_LABELS[group]}",
            color=color,
            fontsize=9.4,
            fontweight="bold",
            pad=4,
        )

    legend_ax = flat[13]
    legend_ax.axis("off")
    handles = [
        Line2D([0], [0], color=color, marker="o", linewidth=2.0, label=GROUP_LABELS[group])
        for group, color in GROUP_COLORS.items()
    ]
    legend_ax.legend(handles=handles, title="Event group", loc="center", frameon=False, fontsize=9.5)
    legend_ax.text(
        0.5,
        0.18,
        "Numbers 1–6 denote months\nArrows show centroid movement",
        transform=legend_ax.transAxes,
        ha="center",
        va="center",
        fontsize=9.0,
        color="0.30",
    )
    method_ax = flat[14]
    method_ax.axis("off")
    method_ax.text(
        0.5,
        0.56,
        "Warm core = positive-anomaly weighted centroid\n"
        "Common domain: 120°E–80°W, 0–300 m\n"
        "Common baseline: 1980–2024 detrended\n"
        "No longitude or depth bins",
        transform=method_ax.transAxes,
        ha="center",
        va="center",
        fontsize=9.1,
        color="0.28",
        linespacing=1.5,
    )
    note = (
        "Centroid weights: max(q′,0)×native layer thickness×zonal cell width; "
        "q′=ρ₀CₚT′ from 5°S–5°N cosine-weighted SODA3.15.2. "
        "Anomalies are 1980–2024 same-calendar-month detrended; domain 120°E–80°W, 0–300 m; no bins."
    )
    fig.text(0.012, 0.025, note, fontsize=8.1, color="0.30")
    return save_figure(fig, "fig_soda3_13_warm_events_jan_jun_core_trajectory_small_multiples")


def plot_overview(table: pd.DataFrame, summary: pd.DataFrame) -> tuple[Path, Path]:
    fig, (phase_ax, scatter_ax) = plt.subplots(1, 2, figsize=(13.8, 6.1))
    fig.subplots_adjust(left=0.075, right=0.975, top=0.86, bottom=0.18, wspace=0.26)
    fig.suptitle(
        "Warm-core redistribution during the development phase of 13 warm events",
        fontsize=15.0,
        fontweight="bold",
        y=0.965,
    )

    for event in EVENTS:
        selected = table.loc[table.event.eq(event)].sort_values("month")
        if event in HIGHLIGHT_COLORS:
            continue
        draw_monthly_path(
            phase_ax,
            selected,
            color="0.68",
            annotate_months=False,
            line_width=1.0,
            alpha=0.62,
            marker_size=19.0,
            zorder=1,
        )
    for event, color in HIGHLIGHT_COLORS.items():
        selected = table.loc[table.event.eq(event)].sort_values("month")
        draw_monthly_path(
            phase_ax,
            selected,
            color=color,
            annotate_months=True,
            line_width=2.4,
            alpha=1.0,
            marker_size=62.0,
            zorder=5,
        )
        last = selected.iloc[-1]
        phase_ax.text(
            last.centroid_lon_e + 2.0,
            last.centroid_depth_m,
            str(event),
            color=color,
            fontsize=8.8,
            fontweight="bold",
            va="center",
        )
    format_phase_axis(phase_ax, show_xlabel=True, show_ylabel=True)
    phase_ax.set_title("a  All trajectories; 1997, 2015 and 2023 highlighted")

    for group, group_table in summary.groupby("group", sort=False):
        color = GROUP_COLORS[group]
        scatter_ax.scatter(
            group_table.jan_to_jun_eastward_displacement_deg,
            group_table.jan_to_jun_upward_displacement_m,
            s=68,
            color=color,
            edgecolor="white",
            linewidth=0.8,
            label=GROUP_LABELS[group],
            zorder=3,
        )
        for row in group_table.itertuples():
            weight = "bold" if row.event in HIGHLIGHT_COLORS else "normal"
            scatter_ax.annotate(
                str(row.event),
                (row.jan_to_jun_eastward_displacement_deg, row.jan_to_jun_upward_displacement_m),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7.8,
                fontweight=weight,
                color="0.18",
            )
    scatter_ax.axhline(0.0, color="0.55", linewidth=0.8, linestyle="--")
    scatter_ax.axvline(0.0, color="0.55", linewidth=0.8, linestyle="--")
    scatter_ax.grid(True, color="0.90", linewidth=0.65)
    scatter_ax.set_xlabel("January-to-June eastward centroid displacement (° longitude)")
    scatter_ax.set_ylabel("January-to-June upward centroid displacement (m)")
    scatter_ax.set_title("b  Net displacement by event")
    scatter_ax.margins(x=0.08, y=0.12)
    scatter_ax.legend(loc="best", frameon=False, fontsize=8.1)

    note = (
        "Positive heat-content-density anomaly centroid; 5°S–5°N, 120°E–80°W, 0–300 m. "
        "Displacement describes bulk redistribution and does not by itself track a single water parcel."
    )
    fig.text(0.012, 0.035, note, fontsize=8.0, color="0.30")
    return save_figure(fig, "fig_soda3_13_warm_events_core_trajectory_overview")


def print_summary(summary: pd.DataFrame) -> None:
    columns = [
        "event",
        "group",
        "jan_to_jun_eastward_displacement_deg",
        "jan_to_jun_upward_displacement_m",
        "positive_section_heat_change_pj_per_m",
    ]
    print(summary[columns].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nLargest eastward displacement:")
    print(
        summary.nlargest(5, "jan_to_jun_eastward_displacement_deg")[columns[:4]].to_string(
            index=False,
            float_format=lambda value: f"{value:.3f}",
        )
    )
    print("\nLargest upward displacement:")
    print(
        summary.nlargest(5, "jan_to_jun_upward_displacement_m")[columns[:4]].to_string(
            index=False,
            float_format=lambda value: f"{value:.3f}",
        )
    )


def main() -> None:
    setup_style()
    manifest = load_event_manifest()
    dataset = build_heat_density(EVENTS)
    table = build_centroid_table(dataset, manifest)
    summary = build_event_summary(table)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = OUT_DIR / "soda3_13_warm_events_monthly_core_centroids.csv"
    summary_path = OUT_DIR / "soda3_13_warm_events_core_displacement_summary.csv"
    table.to_csv(monthly_path, index=False, float_format="%.6f")
    summary.to_csv(summary_path, index=False, float_format="%.6f")
    plot_small_multiples(table)
    plot_overview(table, summary)
    print_summary(summary)
    print(monthly_path)
    print(summary_path)


if __name__ == "__main__":
    main()
