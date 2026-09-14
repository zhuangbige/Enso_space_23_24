#!/usr/bin/env python3
"""Generate English, publication-style figures for the ENSO three-question deck."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "research_2026"
OUT = ROOT / "outputs" / "research_2026" / "three_paper_english_figures_20260811"

NAVY = "#0A2234"
BLUE = "#2F80B9"
ORANGE = "#E17600"
TEAL = "#168C82"
RED = "#BE3D3D"
PURPLE = "#7D57AF"
GRAY = "#7B8B99"
LIGHT_GRID = "#DCE4EA"
EVENT_COLORS = {1997: ORANGE, 2015: BLUE, 2023: TEAL}


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 18,
            "axes.labelsize": 19,
            "xtick.labelsize": 17,
            "ytick.labelsize": 17,
            "legend.fontsize": 18,
            "axes.edgecolor": NAVY,
            "axes.labelcolor": NAVY,
            "xtick.color": NAVY,
            "ytick.color": NAVY,
            "text.color": NAVY,
            "axes.linewidth": 1.0,
            "lines.linewidth": 2.2,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.dpi": 300,
        }
    )


def clean_axis(ax: plt.Axes, *, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color=LIGHT_GRID, linewidth=1.0)
    ax.set_axisbelow(True)


def save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)


def fmt_lon(value: float) -> str:
    lon = value % 360
    if lon == 180:
        return "180°"
    if lon < 180:
        return f"{lon:g}°E"
    return f"{360-lon:g}°W"


def plot_hovmoller() -> None:
    df = pd.read_csv(DATA / "soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv")
    years = [1997, 2015, 2023]
    vmax = float(np.nanquantile(np.abs(df["ohc300_anom_gjm2"]), 0.985))
    vmax = np.ceil(vmax * 10) / 10
    levels = np.linspace(-vmax, vmax, 17)

    fig, axes = plt.subplots(1, 3, figsize=(14.2, 5.6), sharex=True, sharey=True, constrained_layout=True)
    mesh = None
    for ax, year in zip(axes, years):
        sub = df[df["event_year"] == year]
        table = sub.pivot(index="relative_month", columns="lon_deg_e", values="ohc300_anom_gjm2").sort_index()
        x = table.columns.to_numpy(float)
        y = table.index.to_numpy(float)
        mesh = ax.contourf(x, y, table.to_numpy(float), levels=levels, cmap="RdBu_r", extend="both")
        ax.contour(x, y, table.to_numpy(float), levels=[0], colors=NAVY, linewidths=0.8, alpha=0.75)
        ax.axvline(220, color=NAVY, linestyle="--", linewidth=1.4)
        ax.axhline(0, color=NAVY, linestyle=":", linewidth=1.2)
        ax.axhline(5, color=NAVY, linestyle=":", linewidth=1.2)
        ax.text(0.5, 1.025, f"{year}/{str(year + 1)[-2:]}", transform=ax.transAxes, ha="center", va="bottom", fontsize=20, fontweight="bold")
        ax.set_xlim(130, 280)
        ax.set_xticks([130, 180, 220, 240, 280])
        ax.set_xticklabels([fmt_lon(v) for v in [130, 180, 220, 240, 280]], rotation=28, ha="right")
        ax.tick_params(length=4, width=1)
    axes[0].set_ylabel("Month relative to onset year")
    axes[0].set_yticks([-6, -3, 0, 3, 5, 8, 10])
    axes[0].set_yticklabels(["Jul −1", "Oct −1", "Jan 0", "Apr 0", "Jun 0", "Sep 0", "Nov 0"])
    cbar = fig.colorbar(mesh, ax=axes, orientation="horizontal", pad=0.10, shrink=0.72, aspect=35, ticks=np.linspace(-vmax, vmax, 5))
    cbar.set_label("0–300 m OHC anomaly (GJ m$^{-2}$)")
    cbar.ax.set_xticklabels([f"{v:.1f}" for v in np.linspace(-vmax, vmax, 5)])
    cbar.ax.tick_params(labelsize=17)
    save(fig, "q1_ohc300_hovmoller.png")


def plot_lagrangian_summary() -> None:
    df = pd.read_csv(DATA / "soda3_temp_anomaly_lagrangian_pilot_summary.csv")
    df["event"] = df["event"].astype(int)
    df = df.set_index("event").loc[[1997, 2015, 2023]].reset_index()
    colors = [EVENT_COLORS[y] for y in df["event"]]

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.9), constrained_layout=True)
    x = np.arange(len(df))
    vals = df["weighted_median_eastward_displacement_deg"].to_numpy()
    axes[0].bar(x, vals, width=0.62, color=colors)
    axes[0].set_xticks(x, df["event"].astype(str))
    axes[0].set_ylabel("Eastward displacement (°)")
    axes[0].set_ylim(0, 35)
    clean_axis(axes[0])
    for xi, value in zip(x, vals):
        axes[0].text(xi, value + 1.0, f"{value:.1f}°", ha="center", va="bottom", fontsize=18, fontweight="bold")

    vals2 = 100 * df["active_fraction_weight"].to_numpy()
    axes[1].bar(x, vals2, width=0.62, color=colors)
    axes[1].set_xticks(x, df["event"].astype(str))
    axes[1].set_ylabel("Active-trajectory release weight (%)")
    axes[1].set_ylim(0, 85)
    clean_axis(axes[1])
    for xi, value in zip(x, vals2):
        axes[1].text(xi, value + 2.0, f"{value:.0f}%", ha="center", va="bottom", fontsize=18, fontweight="bold")
    save(fig, "q1_lagrangian_summary.png")


def selected_event_table() -> pd.DataFrame:
    df = pd.read_csv(DATA / "nonh20_third_question_event_table.csv")
    return df[df["event_year"].isin([1997, 2015, 2023])].set_index("event_year").loc[[1997, 2015, 2023]].reset_index()


def plot_arrival_storage() -> None:
    df = selected_event_table()
    x = np.arange(len(df))
    width = 0.34
    fig, ax = plt.subplots(figsize=(9.5, 5.1), constrained_layout=True)
    a = ax.bar(x - width / 2, df["arrival_140w_heat_in_zj"], width, color=ORANGE, label="140°W inflow")
    b = ax.bar(x + width / 2, df["arrival_east_ohc_change_zj"], width, color=BLUE, label="Eastern-box OHC gain")
    ax.set_xticks(x, df["event_year"].astype(str))
    ax.set_ylabel("Jan–Jun cumulative energy (ZJ)")
    ax.set_ylim(0, 20)
    clean_axis(ax)
    ax.legend(frameon=False, loc="upper right", ncol=2)
    for bars in (a, b):
        for rect in bars:
            value = rect.get_height()
            ax.text(rect.get_x() + rect.get_width() / 2, value + 0.55, f"{value:.1f}", ha="center", fontsize=18, fontweight="bold")
    save(fig, "q1_arrival_storage.png")


def plot_fate_partition() -> None:
    df = selected_event_table()
    categories = [
        ("Eastern-box OHC loss", "decay_storage_loss_zj", NAVY),
        ("Westward return", "decay_westward_return_zj", BLUE),
        ("Northward export", "decay_northward_output_zj", ORANGE),
        ("Southward export", "decay_southward_output_zj", PURPLE),
        ("Surface heat loss", "decay_surface_loss_zj", RED),
        ("Budget residual", "decay_residual_zj", TEAL),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 5.7), sharex=True, sharey=True, constrained_layout=True)
    y = np.arange(len(categories))
    labels = [item[0] for item in categories]
    for ax, (_, row) in zip(axes, df.iterrows()):
        vals = np.array([row[col] for _, col, _ in categories], dtype=float)
        colors = [c for _, _, c in categories]
        ax.barh(y, vals, color=colors, height=0.66)
        ax.axvline(0, color=NAVY, linewidth=1.2)
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.set_xlim(-7.5, 24)
        ax.set_xticks([-5, 0, 5, 10, 15, 20])
        ax.text(0.5, 1.025, str(int(row["event_year"])), transform=ax.transAxes, ha="center", va="bottom", fontsize=20, fontweight="bold")
        clean_axis(ax, grid_axis="x")
        for yi, value in zip(y, vals):
            offset = 0.55 if value >= 0 else -0.55
            ax.text(value + offset, yi, f"{value:+.1f}", ha="left" if value >= 0 else "right", va="center", fontsize=17, fontweight="bold")
    axes[1].set_xlabel("Following Jan–May cumulative energy (ZJ)")
    save(fig, "q2_fate_partition.png")


def residualize(values: pd.Series, controls: pd.DataFrame | pd.Series | None) -> np.ndarray:
    y = np.asarray(values, dtype=float)
    if controls is None:
        return y - np.nanmean(y)
    x = np.asarray(controls, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    design = np.column_stack([np.ones(len(y)), x])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    return y - design @ coef


def scatter_with_fit(ax: plt.Axes, x: np.ndarray, y: np.ndarray, years: np.ndarray) -> None:
    other = ~np.isin(years, [1997, 2015, 2023])
    ax.scatter(x[other], y[other], s=58, color=GRAY, alpha=0.8, edgecolor="white", linewidth=0.7, zorder=3)
    for year in [1997, 2015, 2023]:
        mask = years == year
        ax.scatter(x[mask], y[mask], s=115, color=EVENT_COLORS[year], edgecolor="white", linewidth=1.0, zorder=4)
    slope, intercept = np.polyfit(x, y, 1)
    grid = np.linspace(np.nanmin(x), np.nanmax(x), 100)
    ax.plot(grid, slope * grid + intercept, color=NAVY, linewidth=2.3, zorder=2)
    ax.axhline(0, color=LIGHT_GRID, linewidth=1)
    ax.axvline(0, color=LIGHT_GRID, linewidth=1)
    clean_axis(ax)


def plot_early_north_to_ne() -> None:
    df = pd.read_csv(DATA / "nonh20_early_north_to_jiang_event_table.csv")
    years = df["year"].to_numpy(int)
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.0), constrained_layout=True)

    arrival = df["arrival_140w_jfm_zj"]
    x = residualize(df["north_output_jfm_zj"], arrival)
    y = residualize(df["ne925_mjj_ms"], arrival)
    scatter_with_fit(axes[0], x, y, years)
    axes[0].set_xlabel("JFM northward export residual (ZJ)")
    axes[0].set_ylabel("MJJ northeasterly residual (m s$^{-1}$)")
    axes[0].text(-0.13, 1.04, "(a)", transform=axes[0].transAxes, fontsize=19, fontweight="bold")

    selected = df[df["year"].isin([1997, 2015, 2023])].set_index("year").loc[[1997, 2015, 2023]]
    north_z = (df["north_output_jfm_zj"] - df["north_output_jfm_zj"].mean()) / df["north_output_jfm_zj"].std(ddof=1)
    early_ne_z = (df["early_ne850_jfm_ms"] - df["early_ne850_jfm_ms"].mean()) / df["early_ne850_jfm_ms"].std(ddof=1)
    plot_df = pd.DataFrame(
        {
            "year": df["year"],
            "JFM northward export": north_z,
            "JFM NE850": early_ne_z,
            "MJJ NE850": df["ne850_mjj_z"],
        }
    ).set_index("year").loc[[1997, 2015, 2023]]
    xpos = np.arange(3)
    width = 0.24
    bars = [
        ("JFM northward export", ORANGE, -width),
        ("JFM NE850", "#A9B6C0", 0.0),
        ("MJJ NE850", TEAL, width),
    ]
    for label, color, offset in bars:
        axes[1].bar(xpos + offset, plot_df[label], width=width, color=color, label=label)
    axes[1].axhline(0, color=NAVY, linewidth=1.1)
    axes[1].set_xticks(xpos, ["1997", "2015", "2023"])
    axes[1].set_ylabel("Standardized anomaly")
    axes[1].set_ylim(-2.7, 2.0)
    clean_axis(axes[1])
    axes[1].legend(frameon=False, loc="lower left", fontsize=15, ncol=1)
    axes[1].text(-0.13, 1.04, "(b)", transform=axes[1].transAxes, fontsize=19, fontweight="bold")
    save(fig, "q3_early_north_to_ne.png")


def plot_dynamic_chain() -> None:
    base = pd.read_csv(DATA / "nonh20_third_question_event_table.csv")
    jiang = pd.read_csv(DATA / "nonh20_early_north_to_jiang_event_table.csv")
    df = base.merge(jiang, left_on="event_year", right_on="year", how="inner")
    years = df["event_year"].to_numpy(int)
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 5.0), constrained_layout=True)

    x1 = residualize(df["ne850_mjj_z"], df["arrival_140w_jfm_zj"])
    y1 = residualize(df["tau_response_mjj_z"], df["arrival_140w_jfm_zj"])
    scatter_with_fit(axes[0], x1, y1, years)
    axes[0].set_xlabel("MJJ NE850 residual (SD)")
    axes[0].set_ylabel("Central zonal stress residual (SD)")

    x2 = residualize(df["u850_cwp_mj_ms"], None)
    y2 = residualize(df["decay_tau5n_westward_nm2"], None)
    scatter_with_fit(axes[1], x2, y2, years)
    axes[1].set_xlabel("MJJ central U850 (m s$^{-1}$)")
    axes[1].set_ylabel("Following 5°N stress (N m$^{-2}$)")

    x3 = residualize(df["decay_tau5n_westward_nm2"], df["arrival_140w_heat_in_zj"])
    y3 = residualize(df["decay_northward_output_zj"], df["arrival_140w_heat_in_zj"])
    scatter_with_fit(axes[2], x3, y3, years)
    axes[2].set_xlabel("Following 5°N stress residual\n(N m$^{-2}$)")
    axes[2].set_ylabel("Late northward export residual (ZJ)")
    for index, ax in enumerate(axes):
        ax.text(0.02, 0.98, f"({chr(97 + index)})", transform=ax.transAxes, ha="left", va="top", fontsize=19, fontweight="bold")
    save(fig, "q3_dynamic_chain.png")


def plot_thermo_and_return() -> None:
    df = pd.read_csv(DATA / "nonh20_third_question_event_table.csv")
    years = df["event_year"].to_numpy(int)
    arrival = df["arrival_140w_heat_in_zj"]
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.8), constrained_layout=True)

    x1 = residualize(df["decay_east_sst_anom_c"], arrival)
    y1 = residualize(df["decay_surface_loss_zj"], arrival)
    scatter_with_fit(axes[0], x1, y1, years)
    axes[0].set_xlabel("Eastern SST residual (°C)")
    axes[0].set_ylabel("Surface heat-loss residual (ZJ)")

    x2 = residualize(df["decay_tau5n_westward_nm2"], arrival)
    y2 = residualize(df["decay_westward_return_zj"], arrival)
    scatter_with_fit(axes[1], x2, y2, years)
    axes[1].set_xlabel("5°N stress residual (N m$^{-2}$)")
    axes[1].set_ylabel("Westward-return residual (ZJ)")
    for index, ax in enumerate(axes):
        ax.text(0.02, 0.98, f"({chr(97 + index)})", transform=ax.transAxes, ha="left", va="top", fontsize=19, fontweight="bold")
    save(fig, "q3_thermo_return.png")


def plot_loeo() -> None:
    df = pd.read_csv(DATA / "nonh20_third_question_loeo_models.csv").set_index("model_id")
    model_ids = ["north_arrival", "north_arrival_tau", "surface_arrival", "surface_arrival_sst"]
    labels = ["North | arrival only", "North | + 5°N stress", "Surface | arrival only", "Surface | + eastern SST"]
    vals = df.loc[model_ids, "loeo_rmse_z"].to_numpy(float)
    colors = ["#A9B6C0", ORANGE, "#A9B6C0", RED]
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(9.2, 4.7), constrained_layout=True)
    ax.barh(y, vals, color=colors, height=0.62)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Leave-one-event-out RMSE (SD)")
    clean_axis(ax, grid_axis="x")
    for yi, value in zip(y, vals):
        ax.text(value + 0.025, yi, f"{value:.2f}", va="center", fontsize=18, fontweight="bold")
    save(fig, "q3_loeo_rmse.png")


def main() -> None:
    apply_style()
    plot_hovmoller()
    plot_lagrangian_summary()
    plot_arrival_storage()
    plot_fate_partition()
    plot_early_north_to_ne()
    plot_dynamic_chain()
    plot_thermo_and_return()
    plot_loeo()


if __name__ == "__main__":
    main()
