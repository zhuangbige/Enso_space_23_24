#!/usr/bin/env python3
"""Replot the late-stage figures in the English ENSO report.

The script uses only the already-standardized January-June fields and tables.
It does not recompute anomalies, refit regressions, or construct an aggregate
similarity score.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


INPUT_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
TABLE_DIR = ROOT / "outputs/research_2026/revised_event_figures"
OUT_DIR = ROOT / "outputs/research_2026/report_visual_revision"
EXPECTED_CSV = TABLE_DIR / "ordinary_el_nino_expected_response.csv"
SIMILARITY_CSV = TABLE_DIR / "event_2026_taylor_similarity_to_2015_2023.csv"
ORAS5_D20_SERIES_CSV = ROOT / "data/interim/research_2026/oras5_d20_timeseries_equatorial_1960_202606.csv"
ORAS5_D20_ANOMALY_CSV = ROOT / "data/derived/research_2026/monthly_2026_oras5_d20_detrended_1980_2014.csv"

MONTHS = np.arange(1, 7)
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
EVENT_LABELS = {2015: "2015/16", 2023: "2023/24", 2026: "2026 developing state"}

INK = "#17212B"
MUTED = "#5C6773"
GRID = "#D9E0E6"
DEEP = "#C96555"
SHOAL = "#4F86B5"
WIND = "#246A92"
RAIN = "#2A7F68"
EXPECT = "#C84C43"
EVENT_2015 = "#2B6F9F"
EVENT_2023 = "#D47A39"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 320,
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 10.8,
            "axes.titlesize": 12.0,
            "axes.labelsize": 10.8,
            "xtick.labelsize": 9.3,
            "ytick.labelsize": 9.3,
            "axes.linewidth": 0.8,
            "axes.edgecolor": "#7A858F",
            "axes.unicode_minus": False,
        }
    )


def load_fields(year: int) -> dict[str, np.ndarray]:
    path = INPUT_DIR / f"monthly_{year}_detrended_fields_1980_2014.npz"
    with np.load(path) as archive:
        return {key: archive[key] for key in archive.files}


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.png", bbox_inches="tight", pad_inches=0.08, facecolor="white")
    fig.savefig(OUT_DIR / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.08, facecolor="white")


def format_lon(value: float) -> str:
    lon = value % 360
    if np.isclose(lon, 180):
        return "180"
    if lon < 180:
        return f"{lon:g}E"
    return f"{360 - lon:g}W"


def equatorial_mean(field: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mask = (lat >= -5) & (lat <= 5)
    weights = np.cos(np.deg2rad(lat[mask]))
    return np.average(field[:, mask, :], axis=1, weights=weights)


def area_mean(
    field: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    box: tuple[float, float, float, float],
) -> np.ndarray:
    lat0, lat1, lon0, lon1 = box
    lat_mask = (lat >= lat0) & (lat <= lat1)
    lon_mask = (lon >= lon0) & (lon <= lon1)
    subset = field[:, lat_mask, :][:, :, lon_mask]
    weights = np.cos(np.deg2rad(lat[lat_mask]))
    numerator = np.nansum(subset * weights[None, :, None], axis=(1, 2))
    denominator = np.sum(np.isfinite(subset) * weights[None, :, None], axis=(1, 2))
    return numerator / denominator


def plot_d20_wind(year: int, figure_number: int) -> None:
    fields = load_fields(year)
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    d20 = np.asarray(fields["d20"], dtype=float)
    lon = np.asarray(fields["lon"], dtype=float)
    lat = np.asarray(fields["lat"], dtype=float)
    u850 = equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
    u850_d20 = np.asarray([np.interp(d20_lon, lon, row) for row in u850])

    fig, axes = plt.subplots(2, 3, figsize=(13.4, 6.15), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.065, right=0.935, bottom=0.145, top=0.855, wspace=0.12, hspace=0.20)
    title = f"{EVENT_LABELS[year]} development: equatorial D20 and 850 hPa zonal wind"
    if year == 2026:
        title = "2026 January-June: equatorial D20 and 850 hPa zonal wind"
    fig.suptitle(title, fontsize=16.0, weight="bold", color=INK, y=0.955)

    legend_items = [
        Patch(facecolor=DEEP, label="Deeper thermocline (D20 > 0)"),
        Patch(facecolor=SHOAL, label="Shallower thermocline (D20 < 0)"),
        Line2D([0], [0], color=INK, lw=2.0, label="Equatorial u850"),
    ]
    fig.legend(
        handles=legend_items,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.915),
        ncol=3,
        frameon=False,
        fontsize=9.7,
        handlelength=2.1,
    )

    ticks = [130, 150, 180, 200, 220, 240, 260, 275]
    for index, ax in enumerate(axes.ravel()):
        row, col = divmod(index, 3)
        colors = np.where(d20[index] >= 0, DEEP, SHOAL)
        ax.set_facecolor("#FBFCFD")
        ax.bar(d20_lon, d20[index], width=3.7, color=colors, alpha=0.88, edgecolor="white", linewidth=0.25)
        ax.axhline(0, color="#5B6570", lw=0.75)
        ax.grid(axis="y", color=GRID, lw=0.55, alpha=0.8)
        ax.set_ylim(-60, 60)
        ax.set_xlim(130, 275)
        ax.set_yticks([-60, -30, 0, 30, 60])
        if col == 0:
            ax.set_ylabel("D20 anomaly (m)")
        ax.text(
            0.018,
            0.94,
            f"{MONTH_LABELS[index]} {year}",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=11.2,
            weight="bold",
            color=INK,
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.88},
            zorder=10,
        )

        wind_ax = ax.twinx()
        wind_line = wind_ax.plot(d20_lon, u850_d20[index], color=INK, lw=2.05, zorder=8)[0]
        wind_line.set_path_effects([path_effects.Stroke(linewidth=3.5, foreground="white"), path_effects.Normal()])
        wind_ax.set_ylim(-12, 12)
        wind_ax.set_yticks([-10, -5, 0, 5, 10])
        if col == 2:
            wind_ax.set_ylabel(r"u850 anomaly (m s$^{-1}$)")
        else:
            wind_ax.tick_params(labelright=False)
        wind_ax.spines["top"].set_visible(False)

        for boundary in [160, 180, 220, 260, 275]:
            ax.axvline(boundary, color="#87919A", lw=0.55, ls=(0, (2, 2)), zorder=0)
        if index == 0:
            # Stagger the two eastern labels because EP and FEP boundaries are
            # only 15 degrees apart in this compact three-column layout.
            for x, y, text, alignment in [
                (161.2, 49, "CWP", "left"),
                (181.2, 49, "Date line", "left"),
                (221.2, 49, "CP", "left"),
                (258.8, 49, "EP", "right"),
                (273.8, 39, "FEP", "right"),
            ]:
                ax.text(x, y, text, ha=alignment, fontsize=8.0, color=MUTED)

        if row == 0:
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xticks(ticks)
            ax.set_xticklabels([format_lon(tick) for tick in ticks])
            ax.set_xlabel("Longitude along the equator")
        ax.spines["top"].set_visible(False)

    fig.text(
        0.065,
        0.045,
        "Monthly detrended anomalies relative to 1980-2014. D20 is the ORAS5 20 °C isotherm depth; "
        "u850 is the ERA5 5°S-5°N mean. Positive u850 denotes westerly flow.",
        fontsize=8.9,
        color=MUTED,
    )
    save(fig, f"fig{figure_number:02d}_{year}_d20_u850_polished")
    plt.close(fig)


def build_2026_d20_section_table() -> pd.DataFrame:
    """Return baseline and detrended-event D20 depths for the section plot."""

    raw = pd.read_csv(ORAS5_D20_SERIES_CSV)
    raw = raw.loc[
        ((raw["product_type"].eq("consolidated")) & (raw["year"] <= 2014))
        | ((raw["product_type"].eq("operational")) & (raw["year"] >= 2015))
    ].copy()
    baseline = (
        raw.loc[raw["year"].between(1980, 2014) & raw["d20_m"].notna()]
        .groupby(["month", "requested_lon"], as_index=False)["d20_m"]
        .mean()
        .rename(columns={"requested_lon": "lon", "d20_m": "baseline_d20_m"})
    )
    anomaly = pd.read_csv(ORAS5_D20_ANOMALY_CSV)[
        ["month", "lon", "d20_detrended_anomaly_m"]
    ].copy()
    section = anomaly.merge(baseline, on=["month", "lon"], how="inner", validate="one_to_one")
    section = section.loc[section["lon"].between(135, 275)].copy()
    section["event_d20_m"] = section["baseline_d20_m"] + section["d20_detrended_anomaly_m"]
    if section.groupby("month")["lon"].size().nunique() != 1:
        raise ValueError("The D20 section must have the same longitude grid in every month")
    return section.sort_values(["month", "lon"])


def build_d20_section_from_fields(fields: dict[str, np.ndarray]) -> pd.DataFrame:
    """Combine a target event's detrended D20 anomaly with the monthly baseline."""

    raw = pd.read_csv(ORAS5_D20_SERIES_CSV)
    raw = raw.loc[
        ((raw["product_type"].eq("consolidated")) & (raw["year"] <= 2014))
        | ((raw["product_type"].eq("operational")) & (raw["year"] >= 2015))
    ].copy()
    baseline = (
        raw.loc[raw["year"].between(1980, 2014) & raw["d20_m"].notna()]
        .groupby(["month", "requested_lon"], as_index=False)["d20_m"]
        .mean()
        .rename(columns={"requested_lon": "lon", "d20_m": "baseline_d20_m"})
    )
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    d20 = np.asarray(fields["d20"], dtype=float)
    if d20.shape != (6, d20_lon.size):
        raise ValueError("Expected six monthly D20 profiles on the supplied longitude grid")
    anomaly = pd.DataFrame(
        {
            "month": np.repeat(MONTHS, d20_lon.size),
            "lon": np.tile(d20_lon, len(MONTHS)),
            "d20_detrended_anomaly_m": d20.reshape(-1),
        }
    )
    section = anomaly.merge(baseline, on=["month", "lon"], how="inner", validate="one_to_one")
    section = section.loc[section["lon"].between(135, 275)].copy()
    section["event_d20_m"] = section["baseline_d20_m"] + section["d20_detrended_anomaly_m"]
    expected_count = int(np.count_nonzero((d20_lon >= 135) & (d20_lon <= 275)))
    if not section.groupby("month")["lon"].size().eq(expected_count).all():
        raise ValueError("Baseline and target D20 grids do not align for every month")
    return section.sort_values(["month", "lon"])


def plot_2026_d20_cross_section(fields: dict[str, np.ndarray]) -> None:
    """Plot D20 as a true depth-longitude section with atmospheric arrows."""

    section = build_2026_d20_section_table()
    lon = np.asarray(fields["lon"], dtype=float)
    lat = np.asarray(fields["lat"], dtype=float)
    u850 = equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
    sample_lons = np.arange(145.0, 276.0, 20.0)

    fig, axes = plt.subplots(2, 3, figsize=(13.4, 7.2), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.14, top=0.83, wspace=0.08, hspace=0.14)
    fig.suptitle(
        "2026 January-June: equatorial thermocline section and 850 hPa zonal wind",
        fontsize=16.0,
        weight="bold",
        color=INK,
        y=0.965,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color="#7B858E", lw=1.8, ls="--", label="1980-2014 calendar-month D20"),
            Line2D([0], [0], color=INK, lw=2.35, label="Baseline + detrended 2026 D20 anomaly"),
            Patch(facecolor=DEEP, alpha=0.68, label="D20 deepening"),
            Patch(facecolor=SHOAL, alpha=0.68, label="D20 shoaling"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=4,
        frameon=False,
        fontsize=9.2,
        handlelength=2.5,
    )

    dense_lon = np.linspace(135, 275, 281)
    ticks = [140, 160, 180, 200, 220, 240, 260, 275]
    for index, ax in enumerate(axes.ravel()):
        month = index + 1
        monthly = section.loc[section["month"].eq(month)].sort_values("lon")
        base = np.interp(dense_lon, monthly["lon"], monthly["baseline_d20_m"])
        event = np.interp(dense_lon, monthly["lon"], monthly["event_d20_m"])

        ax.set_facecolor("#F7FBFD")
        ax.axhspan(-30, 0, color="#EEF3F6", zorder=0)
        ax.fill_between(dense_lon, 0, event, color="#F3C99E", alpha=0.13, zorder=0.5)
        ax.fill_between(dense_lon, event, 205, color="#BFD8E8", alpha=0.13, zorder=0.5)
        ax.fill_between(
            dense_lon,
            base,
            event,
            where=event >= base,
            color=DEEP,
            alpha=0.68,
            interpolate=True,
            zorder=3,
        )
        ax.fill_between(
            dense_lon,
            base,
            event,
            where=event < base,
            color=SHOAL,
            alpha=0.68,
            interpolate=True,
            zorder=3,
        )
        ax.plot(dense_lon, base, color="#7B858E", lw=1.65, ls="--", zorder=4)
        event_line = ax.plot(dense_lon, event, color=INK, lw=2.35, zorder=5)[0]
        event_line.set_path_effects([path_effects.Stroke(linewidth=3.7, foreground="white"), path_effects.Normal()])
        ax.axhline(0, color="#48545F", lw=0.85, zorder=6)
        ax.axvline(180, color="#929CA5", lw=0.65, ls=(0, (3, 3)), zorder=1)
        ax.grid(axis="y", color=GRID, lw=0.55, alpha=0.75)
        ax.set_xlim(135, 275)
        ax.set_ylim(205, -30)
        ax.set_yticks([0, 50, 100, 150, 200])
        if index % 3 == 0:
            ax.set_ylabel("Depth (m)")
        if index >= 3:
            ax.set_xticks(ticks)
            ax.set_xticklabels([format_lon(tick) for tick in ticks])
            ax.set_xlabel("Longitude along the equator")
        else:
            ax.tick_params(labelbottom=False)
        ax.text(
            0.02,
            0.95,
            f"{MONTH_LABELS[index]} 2026",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=11.2,
            weight="bold",
            color=INK,
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.86},
            zorder=12,
        )
        if index == 0:
            ax.text(137, -13, "Atmosphere", fontsize=7.8, color=MUTED, va="center")
            ax.text(181.5, 198, "Date line", fontsize=7.6, color=MUTED, ha="left", va="bottom")

        sample_u850 = np.interp(sample_lons, lon, u850[index])
        wind = ax.quiver(
            sample_lons,
            np.full_like(sample_lons, -14.0),
            sample_u850,
            np.zeros_like(sample_u850),
            angles="xy",
            scale_units="xy",
            scale=0.55,
            color=INK,
            width=0.0052,
            headwidth=4.2,
            headlength=5.0,
            headaxislength=4.4,
            pivot="mid",
            zorder=10,
        )
        key_background = plt.Rectangle(
            (0.78, 0.775),
            0.205,
            0.19,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor="#D1D8DE",
            lw=0.55,
            alpha=0.92,
            zorder=10.5,
        )
        ax.add_patch(key_background)
        key = ax.quiverkey(
            wind,
            0.875,
            0.865,
            4,
            r"4 m s$^{-1}$",
            coordinates="axes",
            labelpos="S",
            labelsep=0.04,
            fontproperties={"size": 7.6},
            color=INK,
        )
        key.set_zorder(12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.text(
        0.07,
        0.045,
        "The dashed curve is the ORAS5 1980-2014 calendar-month D20 mean. The solid curve adds the detrended "
        "2026 D20 anomaly to that baseline, so this is a single-isotherm displacement section rather than a full temperature section. "
        "Arrows show ERA5 u850 averaged over 5°S-5°N; eastward arrows denote westerly anomalies.",
        fontsize=8.7,
        color=MUTED,
    )
    save(fig, "fig09_2026_d20_cross_section_prototype")
    plt.close(fig)


def plot_2026_d20_geographic_cross_section(fields: dict[str, np.ndarray]) -> None:
    """Add explicit Pacific geography to the D20 displacement section."""

    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    section = build_2026_d20_section_table()
    lon = np.asarray(fields["lon"], dtype=float)
    lat = np.asarray(fields["lat"], dtype=float)
    u850 = equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
    sample_lons = np.arange(145.0, 276.0, 20.0)

    fig = plt.figure(figsize=(13.4, 7.25))
    grid = fig.add_gridspec(
        3,
        3,
        height_ratios=[0.45, 1.0, 1.0],
        left=0.07,
        right=0.985,
        bottom=0.085,
        top=0.885,
        wspace=0.08,
        hspace=0.16,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color="#7B858E", lw=1.8, ls="--", label="1980-2014 calendar-month D20"),
            Line2D([0], [0], color=INK, lw=2.35, label="Baseline + detrended 2026 D20 anomaly"),
            Patch(facecolor=DEEP, alpha=0.68, label="D20 deepening"),
            Patch(facecolor=SHOAL, alpha=0.68, label="D20 shoaling"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.985),
        ncol=4,
        frameon=False,
        fontsize=9.2,
        handlelength=2.5,
    )

    map_ax = fig.add_subplot(grid[0, :], projection=ccrs.PlateCarree(central_longitude=180))
    data_crs = ccrs.PlateCarree()
    map_ax.set_extent([120, 280, -13, 13], crs=data_crs)
    map_ax.set_facecolor("#DDECF4")
    map_ax.add_patch(
        Rectangle(
            (135, -5),
            140,
            10,
            transform=data_crs,
            facecolor="#7DB3CC",
            edgecolor="none",
            alpha=0.20,
            zorder=1,
        )
    )
    map_ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#D8D1C5", edgecolor="none", zorder=3)
    map_ax.coastlines(resolution="110m", color="#606A72", linewidth=0.75, zorder=4)
    map_ax.plot(
        [135, 275],
        [0, 0],
        transform=data_crs,
        color="#123E52",
        lw=2.8,
        solid_capstyle="round",
        zorder=5,
    )
    map_ax.scatter(
        [135, 275],
        [0, 0],
        transform=data_crs,
        s=28,
        facecolor="white",
        edgecolor="#123E52",
        linewidth=1.2,
        zorder=6,
    )
    map_ax.set_xticks([140, 180, 220, 260], crs=data_crs)
    map_ax.set_xticklabels([format_lon(value) for value in [140, 180, 220, 260]])
    map_ax.set_yticks([0], crs=data_crs)
    map_ax.set_yticklabels(["Equator"])
    map_ax.tick_params(labelsize=8.2, colors=MUTED, length=2.5)
    map_ax.spines["geo"].set_edgecolor("#8C979F")
    map_ax.spines["geo"].set_linewidth(0.75)

    axes: list[plt.Axes] = []
    for row in range(2):
        for col in range(3):
            shared = axes[0] if axes else None
            axes.append(fig.add_subplot(grid[row + 1, col], sharex=shared, sharey=shared))

    dense_lon = np.linspace(135, 275, 281)
    ticks = [140, 160, 180, 200, 220, 240, 260, 275]
    for index, ax in enumerate(axes):
        month = index + 1
        monthly = section.loc[section["month"].eq(month)].sort_values("lon")
        base = np.interp(dense_lon, monthly["lon"], monthly["baseline_d20_m"])
        event = np.interp(dense_lon, monthly["lon"], monthly["event_d20_m"])

        ax.set_facecolor("#F7FBFD")
        ax.axhspan(-30, 0, color="#EEF2F4", zorder=0)
        ax.fill_between(dense_lon, 0, event, color="#F4D2A9", alpha=0.30, zorder=0.5)
        ax.fill_between(dense_lon, event, 205, color="#BBD7E8", alpha=0.28, zorder=0.5)
        ax.fill_between(
            dense_lon,
            base,
            event,
            where=event >= base,
            color=DEEP,
            alpha=0.72,
            interpolate=True,
            zorder=3,
        )
        ax.fill_between(
            dense_lon,
            base,
            event,
            where=event < base,
            color=SHOAL,
            alpha=0.72,
            interpolate=True,
            zorder=3,
        )
        ax.plot(dense_lon, base, color="#7B858E", lw=1.6, ls="--", zorder=4)
        event_line = ax.plot(dense_lon, event, color=INK, lw=2.35, zorder=5)[0]
        event_line.set_path_effects([path_effects.Stroke(linewidth=3.7, foreground="white"), path_effects.Normal()])
        ax.axhline(0, color="#344650", lw=1.4, zorder=6)
        ax.grid(axis="both", color=GRID, lw=0.55, alpha=0.75)
        ax.set_xlim(135, 275)
        ax.set_ylim(205, -30)
        ax.set_yticks([0, 50, 100, 150, 200])
        if index % 3 == 0:
            ax.set_ylabel("Depth below sea surface (m)")
        if index >= 3:
            ax.set_xticks(ticks)
            ax.set_xticklabels([format_lon(tick) for tick in ticks])
            ax.set_xlabel("Longitude along the equator")
        else:
            ax.tick_params(labelbottom=False)
        ax.text(
            0.02,
            0.95,
            f"{MONTH_LABELS[index]} 2026",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=11.2,
            weight="bold",
            color=INK,
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.86},
            zorder=12,
        )
        sample_u850 = np.interp(sample_lons, lon, u850[index])
        wind = ax.quiver(
            sample_lons,
            np.full_like(sample_lons, -14.0),
            sample_u850,
            np.zeros_like(sample_u850),
            angles="xy",
            scale_units="xy",
            scale=0.55,
            color=INK,
            width=0.0052,
            headwidth=4.2,
            headlength=5.0,
            headaxislength=4.4,
            pivot="mid",
            zorder=10,
        )
        key_background = Rectangle(
            (0.78, 0.775),
            0.205,
            0.19,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor="#D1D8DE",
            lw=0.55,
            alpha=0.92,
            zorder=10.5,
        )
        ax.add_patch(key_background)
        key = ax.quiverkey(
            wind,
            0.875,
            0.865,
            4,
            r"4 m s$^{-1}$",
            coordinates="axes",
            labelpos="S",
            labelsep=0.04,
            fontproperties={"size": 7.6},
            color=INK,
        )
        key.set_zorder(12)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    save(fig, "fig09_2026_d20_geographic_section_clean")
    plt.close(fig)


def plot_three_event_d20_geographic_sections(
    event_fields: dict[int, dict[str, np.ndarray]],
) -> None:
    """Plot the three comparison events in one geographic D20-section figure."""

    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    years = [2015, 2023, 2026]
    sections = {year: build_d20_section_from_fields(event_fields[year]) for year in years}
    fig = plt.figure(figsize=(13.4, 13.1))
    grid = fig.add_gridspec(
        9,
        3,
        height_ratios=[0.42, 1, 1, 0.20, 1, 1, 0.20, 1, 1],
        left=0.07,
        right=0.985,
        bottom=0.055,
        top=0.93,
        wspace=0.08,
        hspace=0.15,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color="#7B858E", lw=1.8, ls="--", label="1980-2014 calendar-month D20"),
            Line2D([0], [0], color=INK, lw=2.35, label="Baseline + detrended event D20 anomaly"),
            Patch(facecolor=DEEP, alpha=0.72, label="D20 deepening"),
            Patch(facecolor=SHOAL, alpha=0.72, label="D20 shoaling"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.985),
        ncol=4,
        frameon=False,
        fontsize=9.2,
        handlelength=2.5,
    )

    map_ax = fig.add_subplot(grid[0, :], projection=ccrs.PlateCarree(central_longitude=180))
    data_crs = ccrs.PlateCarree()
    map_ax.set_extent([120, 280, -13, 13], crs=data_crs)
    map_ax.set_facecolor("#DDECF4")
    map_ax.add_patch(
        Rectangle(
            (135, -5),
            140,
            10,
            transform=data_crs,
            facecolor="#7DB3CC",
            edgecolor="none",
            alpha=0.20,
            zorder=1,
        )
    )
    map_ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#D8D1C5", edgecolor="none", zorder=3)
    map_ax.coastlines(resolution="110m", color="#606A72", linewidth=0.75, zorder=4)
    map_ax.plot([135, 275], [0, 0], transform=data_crs, color="#123E52", lw=2.8, zorder=5)
    map_ax.scatter(
        [135, 275],
        [0, 0],
        transform=data_crs,
        s=28,
        facecolor="white",
        edgecolor="#123E52",
        linewidth=1.2,
        zorder=6,
    )
    map_ax.set_xticks([140, 180, 220, 260], crs=data_crs)
    map_ax.set_xticklabels([format_lon(value) for value in [140, 180, 220, 260]])
    map_ax.set_yticks([0], crs=data_crs)
    map_ax.set_yticklabels(["Equator"])
    map_ax.tick_params(labelsize=8.2, colors=MUTED, length=2.5)
    map_ax.spines["geo"].set_edgecolor("#8C979F")
    map_ax.spines["geo"].set_linewidth(0.75)

    plot_rows = [1, 2, 4, 5, 7, 8]
    axes: dict[tuple[int, int], plt.Axes] = {}
    first_axis = None
    for display_row, grid_row in enumerate(plot_rows):
        for col in range(3):
            ax = fig.add_subplot(grid[grid_row, col], sharex=first_axis, sharey=first_axis)
            if first_axis is None:
                first_axis = ax
            axes[(display_row, col)] = ax

    dense_lon = np.linspace(135, 275, 281)
    ticks = [140, 160, 180, 200, 220, 240, 260, 275]
    for event_index, year in enumerate(years):
        section = sections[year]
        fields = event_fields[year]
        lon = np.asarray(fields["lon"], dtype=float)
        lat = np.asarray(fields["lat"], dtype=float)
        u850 = equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
        sample_lons = np.arange(145.0, 276.0, 20.0)

        for month_index in range(6):
            local_row, col = divmod(month_index, 3)
            display_row = event_index * 2 + local_row
            ax = axes[(display_row, col)]
            month = month_index + 1
            monthly = section.loc[section["month"].eq(month)].sort_values("lon")
            base = np.interp(dense_lon, monthly["lon"], monthly["baseline_d20_m"])
            event = np.interp(dense_lon, monthly["lon"], monthly["event_d20_m"])

            ax.set_facecolor("#F7FBFD")
            ax.axhspan(-30, 0, color="#EEF2F4", zorder=0)
            ax.fill_between(dense_lon, 0, event, color="#F4D2A9", alpha=0.30, zorder=0.5)
            ax.fill_between(dense_lon, event, 205, color="#BBD7E8", alpha=0.28, zorder=0.5)
            ax.fill_between(
                dense_lon,
                base,
                event,
                where=event >= base,
                color=DEEP,
                alpha=0.72,
                interpolate=True,
                zorder=3,
            )
            ax.fill_between(
                dense_lon,
                base,
                event,
                where=event < base,
                color=SHOAL,
                alpha=0.72,
                interpolate=True,
                zorder=3,
            )
            ax.plot(dense_lon, base, color="#7B858E", lw=1.55, ls="--", zorder=4)
            event_line = ax.plot(dense_lon, event, color=INK, lw=2.25, zorder=5)[0]
            event_line.set_path_effects(
                [path_effects.Stroke(linewidth=3.55, foreground="white"), path_effects.Normal()]
            )
            ax.axhline(0, color="#344650", lw=1.35, zorder=6)
            ax.grid(axis="both", color=GRID, lw=0.5, alpha=0.72)
            ax.set_xlim(135, 275)
            ax.set_ylim(205, -30)
            ax.set_yticks([0, 50, 100, 150, 200])
            if col == 0:
                ax.set_ylabel("Depth (m)")
            else:
                ax.tick_params(labelleft=False)
            if local_row == 1:
                ax.set_xticks(ticks)
                ax.set_xticklabels([format_lon(tick) for tick in ticks])
                if event_index == 2:
                    ax.set_xlabel("Longitude along the equator")
            else:
                ax.tick_params(labelbottom=False)
            ax.text(
                0.02,
                0.94,
                MONTH_LABELS[month_index],
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=10.7,
                weight="bold",
                color=INK,
                bbox={"boxstyle": "round,pad=0.14", "facecolor": "white", "edgecolor": "none", "alpha": 0.86},
                zorder=12,
            )

            sample_u850 = np.interp(sample_lons, lon, u850[month_index])
            wind = ax.quiver(
                sample_lons,
                np.full_like(sample_lons, -14.0),
                sample_u850,
                np.zeros_like(sample_u850),
                angles="xy",
                scale_units="xy",
                scale=0.55,
                color=INK,
                width=0.0052,
                headwidth=4.2,
                headlength=5.0,
                headaxislength=4.4,
                pivot="mid",
                zorder=10,
            )
            key_background = Rectangle(
                (0.78, 0.775),
                0.205,
                0.19,
                transform=ax.transAxes,
                facecolor="white",
                edgecolor="#D1D8DE",
                lw=0.55,
                alpha=0.92,
                zorder=10.5,
            )
            ax.add_patch(key_background)
            key = ax.quiverkey(
                wind,
                0.875,
                0.865,
                4,
                r"4 m s$^{-1}$",
                coordinates="axes",
                labelpos="S",
                labelsep=0.04,
                fontproperties={"size": 7.3},
                color=INK,
            )
            key.set_zorder(12)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        block_top = axes[(event_index * 2, 0)].get_position().y1
        fig.text(
            0.07,
            block_top + 0.006,
            str(year),
            ha="left",
            va="bottom",
            fontsize=12.4,
            weight="bold",
            color=INK,
        )

    save(fig, "fig07_three_event_d20_geographic_sections_clean")
    plt.close(fig)


def plot_three_event_d20_geographic_anomalies(
    event_fields: dict[int, dict[str, np.ndarray]],
) -> None:
    """Plot comparable equatorial D20 anomalies with a separate u850 strip."""

    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    years = [2015, 2023, 2026]
    fig = plt.figure(figsize=(13.4, 13.1))
    grid = fig.add_gridspec(
        9,
        3,
        height_ratios=[0.42, 1, 1, 0.20, 1, 1, 0.20, 1, 1],
        left=0.07,
        right=0.985,
        bottom=0.055,
        top=0.93,
        wspace=0.08,
        hspace=0.15,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color=INK, lw=2.35, label="Equatorial ORAS5 D20 anomaly"),
            Patch(facecolor=DEEP, alpha=0.72, label="Deepening (D20 > 0)"),
            Patch(facecolor=SHOAL, alpha=0.72, label="Shoaling (D20 < 0)"),
            Line2D(
                [0],
                [0],
                color=INK,
                lw=1.4,
                marker=">",
                markersize=6,
                label="ERA5 u850 anomaly (rightward = westerly)",
            ),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.985),
        ncol=4,
        frameon=False,
        fontsize=9.0,
        handlelength=2.4,
    )

    map_ax = fig.add_subplot(grid[0, :], projection=ccrs.PlateCarree(central_longitude=180))
    data_crs = ccrs.PlateCarree()
    map_ax.set_extent([120, 280, -13, 13], crs=data_crs)
    map_ax.set_facecolor("#DDECF4")
    map_ax.add_patch(
        Rectangle(
            (135, -5),
            140,
            10,
            transform=data_crs,
            facecolor="#7DB3CC",
            edgecolor="none",
            alpha=0.20,
            zorder=1,
        )
    )
    map_ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#D8D1C5", edgecolor="none", zorder=3)
    map_ax.coastlines(resolution="110m", color="#606A72", linewidth=0.75, zorder=4)
    map_ax.plot([135, 275], [0, 0], transform=data_crs, color="#123E52", lw=2.8, zorder=5)
    map_ax.scatter(
        [135, 275],
        [0, 0],
        transform=data_crs,
        s=28,
        facecolor="white",
        edgecolor="#123E52",
        linewidth=1.2,
        zorder=6,
    )
    map_ax.set_xticks([140, 180, 220, 260], crs=data_crs)
    map_ax.set_xticklabels([format_lon(value) for value in [140, 180, 220, 260]])
    map_ax.set_yticks([0], crs=data_crs)
    map_ax.set_yticklabels(["Equator"])
    map_ax.tick_params(labelsize=8.2, colors=MUTED, length=2.5)
    map_ax.spines["geo"].set_edgecolor("#8C979F")
    map_ax.spines["geo"].set_linewidth(0.75)

    plot_rows = [1, 2, 4, 5, 7, 8]
    anomaly_axes: dict[tuple[int, int], plt.Axes] = {}
    wind_axes: dict[tuple[int, int], plt.Axes] = {}
    first_anomaly_axis = None
    first_wind_axis = None
    for display_row, grid_row in enumerate(plot_rows):
        for col in range(3):
            cell = grid[grid_row, col].subgridspec(
                2,
                1,
                height_ratios=[0.23, 0.77],
                hspace=0.02,
            )
            wind_ax = fig.add_subplot(cell[0], sharex=first_wind_axis)
            anomaly_ax = fig.add_subplot(cell[1], sharex=first_anomaly_axis, sharey=first_anomaly_axis)
            if first_wind_axis is None:
                first_wind_axis = wind_ax
            if first_anomaly_axis is None:
                first_anomaly_axis = anomaly_ax
            wind_axes[(display_row, col)] = wind_ax
            anomaly_axes[(display_row, col)] = anomaly_ax

    dense_lon = np.linspace(135, 275, 281)
    sample_lons = np.arange(145.0, 276.0, 20.0)
    ticks = [140, 160, 180, 200, 220, 240, 260, 275]
    for event_index, year in enumerate(years):
        fields = event_fields[year]
        d20_lon = np.asarray(fields["d20_lon"], dtype=float)
        d20 = np.asarray(fields["d20"], dtype=float)
        lon = np.asarray(fields["lon"], dtype=float)
        lat = np.asarray(fields["lat"], dtype=float)
        u850 = equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)

        for month_index in range(6):
            local_row, col = divmod(month_index, 3)
            display_row = event_index * 2 + local_row
            anomaly_ax = anomaly_axes[(display_row, col)]
            wind_ax = wind_axes[(display_row, col)]

            anomaly = np.interp(dense_lon, d20_lon, d20[month_index])
            anomaly_ax.set_facecolor("#FBFCFD")
            anomaly_ax.fill_between(
                dense_lon,
                0,
                anomaly,
                where=anomaly >= 0,
                color=DEEP,
                alpha=0.72,
                interpolate=True,
                zorder=2,
            )
            anomaly_ax.fill_between(
                dense_lon,
                0,
                anomaly,
                where=anomaly < 0,
                color=SHOAL,
                alpha=0.72,
                interpolate=True,
                zorder=2,
            )
            anomaly_line = anomaly_ax.plot(dense_lon, anomaly, color=INK, lw=2.15, zorder=4)[0]
            anomaly_line.set_path_effects(
                [path_effects.Stroke(linewidth=3.35, foreground="white"), path_effects.Normal()]
            )
            anomaly_ax.axhline(0, color="#344650", lw=1.05, zorder=3)
            anomaly_ax.grid(axis="both", color=GRID, lw=0.5, alpha=0.72)
            anomaly_ax.set_xlim(135, 275)
            anomaly_ax.set_ylim(-65, 65)
            anomaly_ax.set_yticks([-60, -30, 0, 30, 60])
            if col == 0:
                anomaly_ax.set_ylabel("D20 anomaly (m)")
            else:
                anomaly_ax.tick_params(labelleft=False)
            if local_row == 1:
                anomaly_ax.set_xticks(ticks)
                anomaly_ax.set_xticklabels([format_lon(tick) for tick in ticks])
                if event_index == 2:
                    anomaly_ax.set_xlabel("Longitude along the equator")
            else:
                anomaly_ax.tick_params(labelbottom=False)
            anomaly_ax.spines["top"].set_visible(False)
            anomaly_ax.spines["right"].set_visible(False)

            wind_ax.set_facecolor("#EEF2F4")
            wind_ax.axhline(0, color="#AAB4BC", lw=0.65, zorder=1)
            sample_u850 = np.interp(sample_lons, lon, u850[month_index])
            wind = wind_ax.quiver(
                sample_lons,
                np.zeros_like(sample_lons),
                sample_u850,
                np.zeros_like(sample_u850),
                angles="xy",
                scale_units="xy",
                scale=0.55,
                color=INK,
                width=0.012,
                headwidth=4.2,
                headlength=5.0,
                headaxislength=4.4,
                pivot="mid",
                zorder=3,
            )
            wind_ax.set_xlim(135, 275)
            wind_ax.set_ylim(-1, 1)
            wind_ax.set_yticks([])
            wind_ax.tick_params(axis="x", bottom=False, labelbottom=False)
            for spine in wind_ax.spines.values():
                spine.set_visible(False)
            wind_ax.text(
                0.015,
                0.86,
                MONTH_LABELS[month_index],
                transform=wind_ax.transAxes,
                ha="left",
                va="top",
                fontsize=10.3,
                weight="bold",
                color=INK,
                bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.86},
                zorder=5,
            )
            if month_index == 0:
                key = wind_ax.quiverkey(
                    wind,
                    0.90,
                    0.82,
                    4,
                    r"4 m s$^{-1}$",
                    coordinates="axes",
                    labelpos="S",
                    labelsep=0.04,
                    fontproperties={"size": 7.0},
                    color=INK,
                )
                key.set_zorder(5)

        block_top = wind_axes[(event_index * 2, 0)].get_position().y1
        fig.text(
            0.07,
            block_top + 0.006,
            str(year),
            ha="left",
            va="bottom",
            fontsize=12.4,
            weight="bold",
            color=INK,
        )

    save(fig, "fig07_three_event_d20_geographic_anomalies_clean")
    plt.close(fig)


def style_cartesian_axis(ax: plt.Axes) -> None:
    ax.set_facecolor("#FBFCFD")
    ax.grid(True, color=GRID, lw=0.6, alpha=0.85)
    ax.axhline(0, color="#707B85", lw=0.75)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_expected_response(expected: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13.4, 6.35), sharex=True, sharey="row")
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.145, top=0.82, wspace=0.10, hspace=0.18)
    fig.suptitle(
        "Observed and Niño3-conditioned atmospheric responses",
        fontsize=16.0,
        weight="bold",
        color=INK,
        y=0.96,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], color=WIND, marker="o", lw=2.2, label="Observed CWP u10"),
            Line2D([0], [0], color=RAIN, marker="o", lw=2.2, label="Observed CP precipitation"),
            Line2D([0], [0], color=EXPECT, marker="s", lw=1.8, ls="--", label="SST-conditioned expectation"),
            Patch(facecolor="#DCE2E7", alpha=0.9, label="Observed-minus-expected gap"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.905),
        ncol=4,
        frameon=False,
        fontsize=9.2,
    )

    specifications = [
        ("cwp_u10", r"CWP u10 (m s$^{-1}$)", WIND),
        ("cp_precip", r"CP precipitation (mm day$^{-1}$)", RAIN),
    ]
    panel_letters = "abcdef"
    for row, (response, ylabel, observed_color) in enumerate(specifications):
        for column, year in enumerate([2015, 2023, 2026]):
            ax = axes[row, column]
            style_cartesian_axis(ax)
            subset = expected.loc[
                expected["response"].eq(response) & expected["target_year"].eq(year)
            ].sort_values("month")
            observed = subset["observed"].to_numpy(float)
            anticipated = subset["expected"].to_numpy(float)
            ax.fill_between(MONTHS, observed, anticipated, color="#DCE2E7", alpha=0.9, zorder=1)
            ax.plot(MONTHS, observed, color=observed_color, marker="o", ms=5.2, lw=2.2, zorder=3)
            ax.plot(MONTHS, anticipated, color=EXPECT, marker="s", ms=4.6, lw=1.75, ls="--", zorder=3)
            residual = float(subset["residual"].mean())
            callout_fill = "#E7F1F7" if residual >= 0 else "#F8E9E6"
            callout_color = WIND if residual >= 0 else EXPECT
            ax.text(
                0.035,
                0.06,
                f"Jan-Jun mean gap  {residual:+.2f}",
                transform=ax.transAxes,
                ha="left",
                va="bottom",
                fontsize=8.7,
                weight="bold",
                color=callout_color,
                bbox={"boxstyle": "round,pad=0.24", "facecolor": callout_fill, "edgecolor": "none", "alpha": 0.96},
            )
            ax.text(
                0.02,
                0.97,
                panel_letters[row * 3 + column],
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=10.2,
                weight="bold",
                color=MUTED,
            )
            if row == 0:
                ax.set_title(EVENT_LABELS[year], fontsize=12.0, weight="bold", color=INK, pad=7)
            if column == 0:
                ax.set_ylabel(ylabel)
            ax.set_xticks(MONTHS)
            ax.set_xticklabels(MONTH_LABELS)
            if row == 1:
                ax.set_xlabel("Development month")

    fig.text(
        0.075,
        0.045,
        "Calendar-month expectations are regressions on detrended Niño3 SST fitted over 1982-2014; "
        "2015, 2023, and 2026 are excluded from fitting.",
        fontsize=8.9,
        color=MUTED,
    )
    save(fig, "fig10_observed_expected_polished")
    plt.close(fig)


def plot_staged_coupling(
    fields: dict[str, np.ndarray],
    expected: pd.DataFrame,
    year: int = 2026,
    *,
    pdf_only: bool = False,
) -> None:
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    d20 = np.asarray(fields["d20"], dtype=float)
    west_d20 = np.nanmean(d20[:, (d20_lon >= 130) & (d20_lon <= 180)], axis=1)
    east_d20 = np.nanmean(d20[:, (d20_lon >= 220) & (d20_lon <= 275)], axis=1)
    nino3 = area_mean(
        np.asarray(fields["sst"], dtype=float),
        np.asarray(fields["sst_lat"], dtype=float),
        np.asarray(fields["sst_lon"], dtype=float),
        (-5, 5, 210, 270),
    )
    u10 = expected.loc[
        expected["target_year"].eq(year) & expected["response"].eq("cwp_u10")
    ].sort_values("month")
    precipitation = expected.loc[
        expected["target_year"].eq(year) & expected["response"].eq("cp_precip")
    ].sort_values("month")

    fig, axes = plt.subplots(4, 1, figsize=(13.4, 7.25), sharex=True)
    fig.subplots_adjust(left=0.11, right=0.985, bottom=0.13, top=0.80, hspace=0.18)
    titles = {
        2015: "2015 January-June: strongly coupled tropical Pacific development",
        2023: "2023 January-June: ocean-led development with limited atmospheric coupling",
        2026: "2026 January-June: staged establishment of tropical Pacific coupling",
    }
    fig.suptitle(
        titles[year],
        fontsize=16.0,
        weight="bold",
        color=INK,
        y=0.965,
    )

    stage_bands_by_year = {
        2015: [
            (0.5, 2.5, "#EAF2F7", "JAN-FEB", "Strong westerlies; basin-scale thermocline tilt"),
            (2.5, 4.5, "#FBF0E4", "MAR-APR", "Surface-atmosphere amplification"),
            (4.5, 6.5, "#EAF4EA", "MAY-JUN", "Deep-convective strengthening"),
        ],
        2023: [
            (0.5, 2.5, "#EAF2F7", "JAN-FEB", "Eastern deepening; wind-convection mismatch"),
            (2.5, 4.5, "#FBF0E4", "MAR-APR", "Surface warming; modest westerly response"),
            (4.5, 6.5, "#EAF4EA", "MAY-JUN", "Partial convective recovery"),
        ],
        2026: [
            (0.5, 2.5, "#EAF2F7", "JAN-FEB", "Eastern warming; wind-convection mismatch"),
            (2.5, 4.5, "#FBF0E4", "MAR-APR", "Westerly and thermocline adjustment"),
            (4.5, 6.5, "#EAF4EA", "MAY-JUN", "Convective recovery"),
        ],
    }
    stage_bands = stage_bands_by_year[year]
    for ax in axes:
        style_cartesian_axis(ax)
        for left, right, color, _period, _label in stage_bands:
            ax.axvspan(left, right, color=color, zorder=0)
        ax.axvline(2.5, color="#9AA4AD", lw=0.75, ls=(0, (3, 3)))
        ax.axvline(4.5, color="#9AA4AD", lw=0.75, ls=(0, (3, 3)))
        ax.set_xlim(0.8, 6.2)

    axis_box = axes[0].get_position()
    for left, right, color, period, label in stage_bands:
        center = (left + right) / 2
        figure_x = axis_box.x0 + ((center - 0.8) / (6.2 - 0.8)) * axis_box.width
        fig.text(
            figure_x,
            0.875,
            period,
            ha="center",
            va="center",
            fontsize=8.4,
            weight="bold",
            color=MUTED,
        )
        fig.text(
            figure_x,
            0.845,
            label,
            ha="center",
            va="center",
            fontsize=8.8,
            color=INK,
            bbox={"boxstyle": "round,pad=0.20", "facecolor": color, "edgecolor": "none", "alpha": 1.0},
        )

    axes[0].plot(MONTHS, west_d20, color=SHOAL, marker="o", ms=5.0, lw=2.15, label="Western D20")
    axes[0].plot(MONTHS, east_d20, color=DEEP, marker="o", ms=5.0, lw=2.15, label="Eastern D20")
    axes[0].set_ylabel("D20 anomaly (m)")
    axes[0].set_ylim(-30, 55)
    axes[0].set_title("a  Thermocline adjustment", loc="left", fontsize=11.6, weight="bold", color=INK)
    axes[0].legend(loc="lower left", ncol=2, frameon=False, fontsize=8.8)

    axes[1].plot(MONTHS, nino3, color=DEEP, marker="o", ms=5.0, lw=2.2)
    axes[1].set_ylabel("Niño3 SSTA (°C)")
    axes[1].set_ylim(-0.1, 1.85)
    axes[1].set_title("b  Eastern-Pacific surface warming", loc="left", fontsize=11.6, weight="bold", color=INK)

    axes[2].fill_between(MONTHS, u10["observed"], u10["expected"], color="#DCE2E7", alpha=0.9)
    axes[2].plot(MONTHS, u10["observed"], color=WIND, marker="o", ms=5.0, lw=2.2, label="Observed")
    axes[2].plot(MONTHS, u10["expected"], color=EXPECT, marker="s", ms=4.5, lw=1.75, ls="--", label="SST-conditioned expectation")
    axes[2].set_ylabel(r"CWP u10 (m s$^{-1}$)")
    axes[2].set_ylim(-2.1, 4.1)
    axes[2].set_title("c  Near-surface zonal-wind response", loc="left", fontsize=11.6, weight="bold", color=INK)
    axes[2].legend(loc="upper left", ncol=2, frameon=False, fontsize=8.8)

    axes[3].fill_between(
        MONTHS,
        precipitation["observed"],
        precipitation["expected"],
        color="#DCE2E7",
        alpha=0.9,
    )
    axes[3].plot(MONTHS, precipitation["observed"], color=RAIN, marker="o", ms=5.0, lw=2.2)
    axes[3].plot(MONTHS, precipitation["expected"], color=EXPECT, marker="s", ms=4.5, lw=1.75, ls="--")
    axes[3].set_ylabel(r"CP precip. (mm day$^{-1}$)")
    axes[3].set_ylim(-2.6, 4.8)
    axes[3].set_title("d  Deep-convective response", loc="left", fontsize=11.6, weight="bold", color=INK)
    axes[3].set_xticks(MONTHS)
    axes[3].set_xticklabels(MONTH_LABELS)
    axes[3].set_xlabel(f"{year} calendar month")

    fig.text(
        0.11,
        0.045,
        "All variables retain physical units. Stage bands summarize the observed sequence and are not formal regime indices. "
        "SST-conditioned expectations use the 1982-2014 calendar-month regressions.",
        fontsize=8.8,
        color=MUTED,
    )
    stem = f"fig11_{year}_coupling_sequence_polished"
    if pdf_only:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(OUT_DIR / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.08, facecolor="white")
    else:
        save(fig, stem)
    plt.close(fig)


def plot_taylor_similarity(similarity: pd.DataFrame) -> None:
    layer_order = ["Tropical-Pacific SST", "850 hPa zonal wind", "Precipitation", "Equatorial D20"]
    titles = {
        "Tropical-Pacific SST": "a  Tropical-Pacific SST",
        "850 hPa zonal wind": "b  850 hPa zonal wind",
        "Precipitation": "c  Precipitation",
        "Equatorial D20": "d  Equatorial D20",
    }
    units = {
        "Tropical-Pacific SST": "°C",
        "850 hPa zonal wind": r"m s$^{-1}$",
        "Precipitation": r"mm day$^{-1}$",
        "Equatorial D20": "m",
    }

    fig, axes = plt.subplots(2, 2, figsize=(10.8, 8.4), subplot_kw={"projection": "polar"})
    fig.subplots_adjust(left=0.06, right=0.94, bottom=0.13, top=0.82, wspace=0.28, hspace=0.42)
    fig.suptitle(
        "Layer-resolved similarity of 2026 to the reference events",
        fontsize=16.0,
        weight="bold",
        color=INK,
        y=0.965,
    )
    fig.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=EVENT_2015, markeredgecolor="white", markersize=8, label="2015/16"),
            Line2D([0], [0], marker="s", color="none", markerfacecolor=EVENT_2023, markeredgecolor="white", markersize=8, label="2023/24"),
            Line2D([0], [0], marker="*", color="none", markerfacecolor=INK, markeredgecolor=INK, markersize=10, label="2026 reference"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.905),
        ncol=3,
        frameon=False,
        fontsize=9.5,
    )

    correlations = np.array([1.0, 0.9, 0.7, 0.5, 0.3])
    theta_ticks = np.arccos(correlations)
    theta_grid = np.linspace(0, np.arccos(0.25), 180)
    radius_grid = np.linspace(0, 1.25, 180)
    theta_mesh, radius_mesh = np.meshgrid(theta_grid, radius_grid)
    normalized_crmsd = np.sqrt(1 + radius_mesh**2 - 2 * radius_mesh * np.cos(theta_mesh))

    for ax, layer in zip(axes.ravel(), layer_order):
        subset = similarity.loc[similarity["layer"].eq(layer)].sort_values("candidate_year")
        ax.set_theta_zero_location("E")
        ax.set_theta_direction(1)
        ax.set_thetamin(0)
        ax.set_thetamax(float(np.degrees(np.arccos(0.25))))
        ax.set_ylim(0, 1.25)
        ax.set_xticks(theta_ticks)
        ax.set_xticklabels([f"r={value:.1f}" for value in correlations], fontsize=8.1, color=MUTED)
        ax.set_yticks([0.5, 0.75, 1.0, 1.25])
        ax.set_yticklabels(["0.50", "0.75", "1.00", "1.25"], fontsize=7.8, color=MUTED)
        ax.set_rlabel_position(120)
        ax.grid(color=GRID, lw=0.65)
        ax.spines["polar"].set_color("#9AA4AD")
        contours = ax.contour(
            theta_mesh,
            radius_mesh,
            normalized_crmsd,
            levels=[0.25, 0.5, 0.75, 1.0],
            colors="#C6CED5",
            linewidths=0.55,
            linestyles="dotted",
        )
        ax.clabel(contours, inline=True, fontsize=6.5, fmt="%.2f", colors="#8A949D")
        ax.scatter(0, 1, marker="*", s=95, color=INK, edgecolor="white", linewidth=0.7, zorder=5)

        for _, row in subset.iterrows():
            candidate_year = int(row["candidate_year"])
            color = EVENT_2015 if candidate_year == 2015 else EVENT_2023
            marker = "o" if candidate_year == 2015 else "s"
            theta = float(np.arccos(np.clip(row["pattern_correlation"], -1, 1)))
            radius = float(row["standard_deviation_ratio"])
            ax.scatter(theta, radius, marker=marker, s=72, color=color, edgecolor="white", linewidth=0.9, zorder=6)
            label = f"{row['centered_rmsd']:.2f} {units[layer]}"
            ax.annotate(
                label,
                xy=(theta, radius),
                xytext=(5, 7 if candidate_year == 2015 else -13),
                textcoords="offset points",
                fontsize=7.4,
                weight="bold",
                color=color,
                bbox={"boxstyle": "round,pad=0.14", "facecolor": "white", "edgecolor": "none", "alpha": 0.84},
            )
        ax.set_title(titles[layer], fontsize=11.5, weight="bold", color=INK, pad=19)

    fig.text(
        0.5,
        0.075,
        "Azimuth gives pattern correlation; radius gives the candidate-to-2026 standard-deviation ratio. "
        "Dotted contours are normalized centered RMS difference; labels beside points report centered RMSD in physical units.",
        ha="center",
        fontsize=8.7,
        color=MUTED,
    )
    fig.text(
        0.5,
        0.045,
        "Each field is evaluated independently over January-June. No cross-variable similarity score or subjective weighting is used.",
        ha="center",
        fontsize=8.7,
        color=MUTED,
    )
    save(fig, "fig12_layer_resolved_taylor_diagrams")
    plt.close(fig)


def main() -> int:
    setup_style()
    expected = pd.read_csv(EXPECTED_CSV)
    event_fields = {year: load_fields(year) for year in [2015, 2023, 2026]}
    for figure_number, year in zip([7, 8, 9], [2015, 2023, 2026]):
        plot_d20_wind(year, figure_number)
    plot_three_event_d20_geographic_anomalies(event_fields)
    fields_2026 = event_fields[2026]
    plot_expected_response(expected)
    plot_staged_coupling(fields_2026, expected, year=2026)
    print(OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
