#!/usr/bin/env python3
"""Plot paper-style 2026 meteorological maps for ENSO/FEP diagnostics."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


INPUT = ROOT / "data/interim/research_2026/current_2026_spatial_meteorology.npz"
OUT_DIR = ROOT / "outputs/research_2026/spatial_meteorology"
ANOMALY_NOTE = "Anomalies use the 1982-2022 monthly climatology."
EXTRA_SST_NOTE = ""

SST_BOXES = {
    "TIO": (-20, 20, 40, 110),
    "MC": (-10, 10, 95, 150),
    "WPWP": (-10, 10, 120, 160),
    "Nino-3.4": (-5, 5, 190, 240),
    "Nino-3": (-5, 5, 210, 270),
    "FEP": (-5, 5, 270, 280),
    "TNA": (0, 20, 300, 340),
}
PACIFIC_BOXES = {
    "WCP": (-5, 5, 140, 180),
    "CP": (-5, 5, 180, 220),
    "EP": (-5, 5, 220, 260),
    "FEP": (-5, 5, 270, 280),
}
WIND_SLP_BOXES = {
    "Darwin": (-20, -5, 120, 140),
    "CWP u": (-5, 5, 160, 220),
    "Tahiti": (-25, -10, 200, 220),
}
BOX_LABEL_OFFSETS = {
    "Nino-3.4": (1.0, 1.0),
    "Nino-3": (20.0, -5.0),
    "FEP": (-8.0, 1.0),
    "TIO": (1.0, 1.0),
    "TNA": (1.0, 1.0),
}


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
            "axes.linewidth": 0.85,
            "axes.unicode_minus": False,
        }
    )


def format_lon(value: float) -> str:
    lon = value % 360
    if np.isclose(lon, 0):
        return "0"
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


def format_map_axes(ax, lon_ticks, lat_ticks=(-30, -15, 0, 15, 30)) -> None:
    ax.set_yticks(lat_ticks)
    ax.set_yticklabels([format_lat(tick) for tick in lat_ticks])
    ax.set_xticks(lon_ticks)
    ax.set_xticklabels([format_lon(tick) for tick in lon_ticks])
    ax.axhline(0, color="0.2", linewidth=0.55)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def add_boxes(ax, boxes: dict[str, tuple[float, float, float, float]], lon_min: float, lon_max: float) -> None:
    for label, (lat0, lat1, x0, x1) in boxes.items():
        if x1 < lon_min or x0 > lon_max:
            continue
        x0_clip = max(x0, lon_min)
        x1_clip = min(x1, lon_max)
        ax.plot(
            [x0_clip, x1_clip, x1_clip, x0_clip, x0_clip],
            [lat0, lat0, lat1, lat1, lat0],
            color="0.15",
            linewidth=0.75,
        )
        dx, dy = BOX_LABEL_OFFSETS.get(label, (1.0, 1.0))
        y_anchor = lat1 if dy >= 0 else lat0
        ax.text(x0_clip + dx, y_anchor + dy, label, fontsize=6.5, color="0.15")


def subset(lon, lat, field, lon_min: float, lon_max: float, lat_min: float = -30, lat_max: float = 30):
    lon_idx = np.where((lon >= lon_min) & (lon <= lon_max))[0]
    lat_idx = np.where((lat >= lat_min) & (lat <= lat_max))[0]
    return lon[lon_idx], lat[lat_idx], field[np.ix_(lat_idx, lon_idx)]


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.16)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.16)
    print(png)
    print(pdf)


def plot_sst_precip_maps(data) -> None:
    sst_lon = data["sst_lon"]
    sst_lat = data["sst_lat"]
    precip_lon = data["precip_lon"]
    precip_lat = data["precip_lat"]

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 7.2), constrained_layout=True)
    fig.suptitle("2026 spring spatial anomalies: eastern-Pacific SST warming versus rainfall response", weight="bold")

    panels = [
        (axes[0, 0], sst_lon, sst_lat, data["sst_MAM"], "MAM 2026 OISST SST anomaly", "RdBu_r", -2.5, 2.5, "deg C", SST_BOXES, [40, 80, 120, 160, 200, 240, 280, 320]),
        (axes[0, 1], sst_lon, sst_lat, data["sst_AM_to_date"], "Apr-May 2026 OISST SST anomaly", "RdBu_r", -2.5, 2.5, "deg C", SST_BOXES, [40, 80, 120, 160, 200, 240, 280, 320]),
        (axes[1, 0], precip_lon, precip_lat, data["precip_MAM"], "MAM 2026 GPCP precipitation anomaly", "BrBG", -5, 5, "mm/day", PACIFIC_BOXES, [120, 160, 200, 240, 280]),
        (axes[1, 1], precip_lon, precip_lat, data["precip_AM_to_date"], "Apr-May 2026 GPCP precipitation anomaly", "BrBG", -5, 5, "mm/day", PACIFIC_BOXES, [120, 160, 200, 240, 280]),
    ]

    row_meshes = []
    for ax, lon, lat, field, title, cmap, vmin, vmax, _label, boxes, ticks in panels:
        lon_min, lon_max = min(ticks), max(ticks)
        xlon, ylat, values = subset(lon, lat, field, lon_min, lon_max)
        mesh = ax.pcolormesh(xlon, ylat, values, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(-30, 30)
        ax.set_title(title)
        format_map_axes(ax, ticks)
        add_boxes(ax, boxes, lon_min, lon_max)
        row_meshes.append(mesh)

    fig.colorbar(row_meshes[0], ax=axes[0, :], label="SST anomaly (deg C)", shrink=0.96)
    fig.colorbar(row_meshes[2], ax=axes[1, :], label="Precipitation anomaly (mm/day)", shrink=0.96)
    fig.text(
        0.01,
        -0.015,
        f"{ANOMALY_NOTE} {EXTRA_SST_NOTE}SST: NOAA OISST v2.1; precipitation: GPCP monthly, both available through May 2026.",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig4_2026_sst_precip_spatial")
    plt.close(fig)


def plot_wind_slp_maps(data) -> None:
    lon = data["ncep_lon"]
    lat = data["ncep_lat"]
    lon_min, lon_max = 120, 280
    xlon, ylat, _ = subset(lon, lat, data["u850_JAN"], lon_min, lon_max)

    fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.0), constrained_layout=True)
    fig.suptitle("2026 early-year lower-tropospheric wind and pressure anomalies", weight="bold")

    panel_specs = [
        ("JAN", axes[0, 0], "u850 anomaly and 850 hPa wind vectors: Jan 2026", data["u850_JAN"], -6, 6, "m/s"),
        ("FEB", axes[0, 1], "u850 anomaly and 850 hPa wind vectors: Feb 2026", data["u850_FEB"], -6, 6, "m/s"),
        ("JAN", axes[1, 0], "SLP anomaly and 850 hPa wind vectors: Jan 2026", data["slp_JAN"], -5, 5, "hPa"),
        ("FEB", axes[1, 1], "SLP anomaly and 850 hPa wind vectors: Feb 2026", data["slp_FEB"], -5, 5, "hPa"),
    ]
    meshes = []
    for month, ax, title, field, vmin, vmax, label in panel_specs:
        _, _, values = subset(lon, lat, field, lon_min, lon_max)
        _, _, u = subset(lon, lat, data[f"u850_{month}"], lon_min, lon_max)
        _, _, v = subset(lon, lat, data[f"v850_{month}"], lon_min, lon_max)
        mesh = ax.pcolormesh(xlon, ylat, values, cmap="RdBu_r", vmin=vmin, vmax=vmax, shading="auto")
        meshes.append((mesh, label))
        ax.set_title(title)
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(-30, 30)
        format_map_axes(ax, [120, 160, 200, 240, 280])
        add_boxes(ax, WIND_SLP_BOXES, lon_min, lon_max)

        step_y = 3
        step_x = 5
        q = ax.quiver(
            xlon[::step_x],
            ylat[::step_y],
            u[::step_y, ::step_x],
            v[::step_y, ::step_x],
            color="0.1",
            pivot="middle",
            width=0.0028,
            headwidth=3.2,
            scale=55,
        )
        if ax is axes[0, 1]:
            ax.quiverkey(q, 0.84, 0.91, 4, "4 m/s", labelpos="E", coordinates="axes", fontproperties={"size": 8})

    fig.colorbar(meshes[0][0], ax=axes[0, :], label="u850 anomaly (m/s)", shrink=0.96)
    fig.colorbar(meshes[2][0], ax=axes[1, :], label="SLP anomaly (hPa)", shrink=0.96)
    fig.text(
        0.01,
        -0.015,
        f"NCEP/NCAR monthly pressure-level winds and SLP are currently available through February 2026. {ANOMALY_NOTE}",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig5_2026_ncep_wind_slp_spatial")
    plt.close(fig)


def plot_olr_maps(data) -> None:
    lon = data["olr_lon"]
    lat = data["olr_lat"]
    latest = str(data["olr_latest_date"])
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 3.9), constrained_layout=True)
    fig.suptitle("2026 convection proxy: CPC OLR anomaly maps", weight="bold")

    specs = [
        (axes[0], data["olr_MAM"], "MAM 2026 CPC OLR anomaly"),
        (axes[1], data["olr_AMJ_to_0615"], f"AMJ-to-{latest[5:]} CPC OLR anomaly"),
    ]
    mesh = None
    for ax, field, title in specs:
        xlon, ylat, values = subset(lon, lat, field, 120, 280)
        mesh = ax.pcolormesh(xlon, ylat, values, cmap="RdBu_r", vmin=-25, vmax=25, shading="auto")
        ax.set_title(title)
        ax.set_xlim(120, 280)
        ax.set_ylim(-30, 30)
        format_map_axes(ax, [120, 160, 200, 240, 280])
        add_boxes(ax, PACIFIC_BOXES, 120, 280)
    fig.colorbar(mesh, ax=axes[:], label="OLR anomaly (W m$^{-2}$; positive = suppressed convection)", shrink=0.96)
    fig.text(
        0.01,
        -0.035,
        f"CPC blended OLR is a daily anomaly product; fields here are period means. {ANOMALY_NOTE} Positive OLR means weaker high-cloud/deep-convection signal.",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig6_2026_olr_convection_spatial")
    plt.close(fig)


def plot_hovmoller(data) -> None:
    sst_lon = data["sst_lon"]
    precip_lon = data["precip_lon"]
    sst_months = [str(x) for x in data["sst_hov_months"]]
    precip_months = [str(x) for x in data["precip_hov_months"]]

    sst_idx = np.where((sst_lon >= 120) & (sst_lon <= 280))[0]
    precip_idx = np.where((precip_lon >= 120) & (precip_lon <= 280))[0]
    sst_hov = data["sst_equatorial_hov"][:, sst_idx]
    precip_hov = data["precip_equatorial_hov"][:, precip_idx]

    fig, axes = plt.subplots(2, 1, figsize=(11.8, 6.2), constrained_layout=True)
    fig.suptitle("2026 equatorial longitude-time evolution: SST warms before rainfall response catches up", weight="bold")

    mesh = axes[0].pcolormesh(sst_lon[sst_idx], np.arange(len(sst_months)), sst_hov, cmap="RdBu_r", vmin=-2, vmax=2, shading="auto")
    axes[0].set_title("OISST equatorial SST anomaly averaged over 5S-5N")
    axes[0].set_yticks(range(len(sst_months)))
    axes[0].set_yticklabels([m.title() for m in sst_months])
    axes[0].set_xlim(120, 280)
    axes[0].set_xticks([120, 160, 180, 200, 220, 240, 260, 280])
    axes[0].set_xticklabels([format_lon(x) for x in [120, 160, 180, 200, 220, 240, 260, 280]])
    axes[0].set_ylabel("2026 month")
    axes[0].set_xlabel("Longitude")
    for x, label in [(180, "Date line"), (220, "CP"), (260, "EP"), (270, "FEP")]:
        axes[0].axvline(x, color="0.25", lw=0.55, ls="--")
        axes[0].text(x + 1, -0.35, label, fontsize=7, color="0.25")
    fig.colorbar(mesh, ax=axes[0], label="SST anomaly (deg C)")

    mesh = axes[1].pcolormesh(precip_lon[precip_idx], np.arange(len(precip_months)), precip_hov, cmap="BrBG", vmin=-4, vmax=4, shading="auto")
    axes[1].set_title("GPCP equatorial precipitation anomaly averaged over 5S-5N")
    axes[1].set_yticks(range(len(precip_months)))
    axes[1].set_yticklabels([m.title() for m in precip_months])
    axes[1].set_xlim(120, 280)
    axes[1].set_xticks([120, 160, 180, 200, 220, 240, 260, 280])
    axes[1].set_xticklabels([format_lon(x) for x in [120, 160, 180, 200, 220, 240, 260, 280]])
    axes[1].set_ylabel("2026 month")
    axes[1].set_xlabel("Longitude")
    for x, label in [(180, "Date line"), (220, "CP"), (260, "EP"), (270, "FEP")]:
        axes[1].axvline(x, color="0.25", lw=0.55, ls="--")
        axes[1].text(x + 1, -0.35, label, fontsize=7, color="0.25")
    fig.colorbar(mesh, ax=axes[1], label="Precipitation anomaly (mm/day)")
    fig.text(
        0.01,
        -0.02,
        f"Both Hovmoller panels are averaged over 5S-5N. {ANOMALY_NOTE} {EXTRA_SST_NOTE}",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig7_2026_equatorial_sst_precip_hovmoller")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    global INPUT, OUT_DIR, ANOMALY_NOTE, EXTRA_SST_NOTE
    parser = argparse.ArgumentParser(description="Plot 2026 spatial meteorology diagnostics.")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--anomaly-note", default=ANOMALY_NOTE)
    parser.add_argument("--extra-sst-note", default=EXTRA_SST_NOTE)
    args = parser.parse_args(argv)
    INPUT = args.input
    OUT_DIR = args.out_dir
    ANOMALY_NOTE = args.anomaly_note
    EXTRA_SST_NOTE = args.extra_sst_note

    setup_style()
    data = np.load(INPUT, allow_pickle=True)
    plot_sst_precip_maps(data)
    plot_wind_slp_maps(data)
    if "olr_MAM" in data.files and "olr_AMJ_to_0615" in data.files:
        plot_olr_maps(data)
    else:
        print("Skipping OLR map: OLR fields are not present in the input NPZ.")
    plot_hovmoller(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
