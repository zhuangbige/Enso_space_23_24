#!/usr/bin/env python3
"""Plot unified-baseline ERA5 OLR and CPC SOI report figures."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


INPUT_NPZ = (
    ROOT
    / "data/interim/research_2026/"
    "era5_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014.npz"
)
INPUT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "era5_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014.csv"
)
OUT_DIR = ROOT / "outputs/research_2026/report_era5_olr_soi_unified_climatology"

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
EVENT_COLORS = {2015: "#2B6F9F", 2023: "#D47A39", 2026: "#17212B"}
INK = "#17212B"
MUTED = "#5C6773"
GRID = "#D9E0E6"
ENHANCED = "#2B6F9F"
SUPPRESSED = "#C96555"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 320,
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 10.5,
            "axes.titlesize": 11.4,
            "axes.labelsize": 10.2,
            "xtick.labelsize": 8.8,
            "ytick.labelsize": 8.8,
            "axes.edgecolor": "#7A858F",
            "axes.linewidth": 0.8,
            "axes.unicode_minus": False,
        }
    )


def format_lon(value: float) -> str:
    lon = value % 360
    if np.isclose(lon, 180):
        return "180"
    if lon < 180:
        return f"{lon:g}E"
    return f"{360 - lon:g}W"


def format_lat(value: float) -> str:
    if np.isclose(value, 0):
        return "Eq"
    if value > 0:
        return f"{value:g}N"
    return f"{abs(value):g}S"


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        OUT_DIR / f"{stem}.png",
        bbox_inches="tight",
        pad_inches=0.08,
        facecolor="white",
    )
    fig.savefig(
        OUT_DIR / f"{stem}.pdf",
        bbox_inches="tight",
        pad_inches=0.08,
        facecolor="white",
    )


def add_region_boxes(ax, transform) -> None:
    specifications = [
        ("Indonesia", 120, 170, "#6B7F43"),
        ("CP", 170, 220, "#6A4C93"),
        ("ECP", 220, 250, "#B35C44"),
    ]
    for label, lon0, lon1, color in specifications:
        ax.add_patch(
            Rectangle(
                (lon0, -5),
                lon1 - lon0,
                10,
                transform=transform,
                fill=False,
                edgecolor=color,
                linewidth=1.1,
                zorder=5,
            )
        )
        ax.text(
            lon0 + 2,
            6.5,
            label,
            transform=transform,
            color=color,
            fontsize=7.4,
            weight="bold",
            zorder=6,
        )


def plot_monthly_olr_maps(data, year: int = 2026) -> None:
    if year not in EVENT_COLORS:
        raise ValueError(f"Unsupported event year: {year}")
    lon = np.asarray(data["lon"], dtype=float)
    lat = np.asarray(data["lat"], dtype=float)
    fields = np.asarray(data[f"olr_{year}"], dtype=float)
    fig, axes = plt.subplots(
        3,
        2,
        figsize=(12.2, 8.35),
        subplot_kw={"projection": ccrs.PlateCarree(central_longitude=180)},
    )
    fig.subplots_adjust(
        left=0.060,
        right=0.925,
        bottom=0.10,
        top=0.895,
        wspace=0.06,
        hspace=0.18,
    )
    fig.suptitle(
        f"January-June {year} ERA5 OLR anomalies",
        fontsize=16,
        weight="bold",
        color=INK,
        y=0.96,
    )
    data_crs = ccrs.PlateCarree()
    levels = np.arange(-30, 31, 5)
    contour = None
    for month_index, ax in enumerate(axes.flat):
        contour = ax.contourf(
            lon,
            lat,
            fields[month_index],
            levels=levels,
            cmap="RdBu_r",
            extend="both",
            transform=data_crs,
        )
        ax.set_extent([100, 280, -20, 20], crs=data_crs)
        ax.add_feature(
            cfeature.LAND.with_scale("110m"),
            facecolor="#DED8CD",
            edgecolor="none",
            zorder=3,
        )
        ax.coastlines(resolution="110m", color="#66717A", linewidth=0.55, zorder=4)
        ax.plot(
            [100, 280],
            [0, 0],
            color="#66717A",
            linewidth=0.55,
            transform=data_crs,
            zorder=4,
        )
        add_region_boxes(ax, data_crs)
        ax.set_title(f"{MONTH_LABELS[month_index]} {year}", weight="bold", color=INK)
        ax.set_xticks([120, 160, 200, 240, 280], crs=data_crs)
        ax.set_xticklabels([format_lon(value) for value in [120, 160, 200, 240, 280]])
        ax.set_yticks([-20, -10, 0, 10, 20], crs=data_crs)
        if month_index % 2 == 0:
            ax.set_yticklabels([format_lat(value) for value in [-20, -10, 0, 10, 20]])
        else:
            ax.set_yticklabels([])
        ax.tick_params(length=2.2, colors=MUTED)
        ax.spines["geo"].set_edgecolor("#8C979F")
        ax.spines["geo"].set_linewidth(0.70)

    colorbar_ax = fig.add_axes([0.942, 0.18, 0.018, 0.60])
    colorbar = fig.colorbar(contour, cax=colorbar_ax)
    colorbar.set_label(
        r"OLR anomaly (W m$^{-2}$)",
        fontsize=10,
    )
    fig.text(
        0.50,
        0.052,
        "Negative OLR denotes enhanced high-cloud/deep-convection signal; positive OLR denotes suppression.",
        ha="center",
        fontsize=9.1,
        color=MUTED,
    )
    fig.text(
        0.50,
        0.023,
        "ERA5 mean top net long-wave flux converted to OLR; 1980-2014 "
        "calendar-month climatology and same-month linear trend removed.",
        ha="center",
        fontsize=8.6,
        color=MUTED,
    )
    save(fig, f"fig07_{year}_monthly_era5_olr_anomalies")
    plt.close(fig)


def style_index_axis(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_title(title, weight="bold", color=INK)
    ax.set_facecolor("#FBFCFD")
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.85)
    ax.axhline(0, color="#68747E", linewidth=0.9)
    ax.set_xticks(range(1, 7))
    ax.set_xticklabels(MONTH_LABELS)
    ax.set_xlabel("Development month")
    ax.set_ylabel(ylabel)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_event_indices(table: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12.7, 6.75), sharex=True)
    fig.subplots_adjust(
        left=0.075,
        right=0.985,
        bottom=0.13,
        top=0.83,
        wspace=0.18,
        hspace=0.36,
    )
    fig.suptitle(
        "Atmospheric coupling indices during the three development periods",
        fontsize=16,
        weight="bold",
        color=INK,
        y=0.955,
    )
    fig.legend(
        handles=[
            plt.Line2D(
                [0],
                [0],
                color=EVENT_COLORS[year],
                lw=2.4,
                marker="o",
                label=f"{year}/{str(year + 1)[-2:]}" if year != 2026 else "2026",
            )
            for year in [2015, 2023, 2026]
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.90),
        ncol=3,
        frameon=False,
        fontsize=9.4,
    )

    specifications = [
        (
            axes[0, 0],
            "soi_standardized",
            "Traditional SOI",
            "Standard deviations",
            "Negative = El Niño-like Tahiti-Darwin pressure pattern",
        ),
        (
            axes[0, 1],
            "equatorial_soi_standardized",
            "Equatorial SOI",
            "Standard deviations",
            "Negative = El Niño-like equatorial pressure pattern",
        ),
        (
            axes[1, 0],
            "olr_central_pacific_170e_140w_wm2",
            "Central-Pacific OLR",
            r"OLR anomaly (W m$^{-2}$)",
            "Negative = enhanced central-Pacific convection",
        ),
        (
            axes[1, 1],
            "olr_cp_minus_indonesia_wm2",
            "CP-minus-Indonesia OLR contrast",
            r"OLR difference (W m$^{-2}$)",
            "Negative = convection shifted toward the central Pacific",
        ),
    ]
    for ax, column, title, ylabel, note in specifications:
        style_index_axis(ax, title, ylabel)
        for year in [2015, 2023, 2026]:
            subset = table.loc[table["year"].eq(year)].sort_values("month")
            ax.plot(
                subset["month"],
                subset[column],
                color=EVENT_COLORS[year],
                lw=2.25 if year == 2026 else 1.85,
                marker="o",
                markersize=5.2 if year == 2026 else 4.4,
                zorder=3,
            )
        ax.text(
            0.02,
            0.04,
            note,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=7.9,
            color=MUTED,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.84, "pad": 1.2},
        )
    for ax in axes[0, :]:
        ax.set_xlabel("")

    axes[0, 0].axhspan(-3.0, 0, color=ENHANCED, alpha=0.05, zorder=0)
    axes[0, 1].axhspan(-3.0, 0, color=ENHANCED, alpha=0.05, zorder=0)
    axes[1, 0].axhspan(-40.0, 0, color=ENHANCED, alpha=0.05, zorder=0)
    axes[1, 0].axhspan(0, 40.0, color=SUPPRESSED, alpha=0.04, zorder=0)
    axes[1, 1].axhspan(-60.0, 0, color=ENHANCED, alpha=0.05, zorder=0)

    fig.text(
        0.50,
        0.035,
        "SOI series: NOAA/CPC standardized monthly indices. OLR = -ERA5 mean top net long-wave "
        "radiation flux; anomalies use the 1980-2014 same-calendar-month climatology and trend. "
        "CP = 5°S-5°N, 170°E-140°W.",
        ha="center",
        fontsize=8.4,
        color=MUTED,
    )
    save(fig, "fig08_three_event_era5_olr_soi_indices")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot unified-baseline ERA5 OLR and CPC SOI report figures."
    )
    parser.add_argument(
        "--map-years",
        nargs="+",
        type=int,
        choices=sorted(EVENT_COLORS),
        default=[2026],
        help="Event years for the January-June OLR maps (default: 2026).",
    )
    parser.add_argument(
        "--skip-indices",
        action="store_true",
        help="Do not regenerate the three-event OLR/SOI index figure.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_style()
    data = np.load(INPUT_NPZ, allow_pickle=True)
    for year in args.map_years:
        plot_monthly_olr_maps(data, year)
    if not args.skip_indices:
        table = pd.read_csv(INPUT_CSV)
        plot_event_indices(table)
    print(OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
