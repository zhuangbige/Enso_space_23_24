#!/usr/bin/env python3
"""Plot ERA5-based 2026 meteorological diagnostics."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


INPUT = ROOT / "data/interim/research_2026/current_2026_era5_spatial_anomalies.npz"
OUT_DIR = ROOT / "outputs/research_2026/era5_spatial"
ANOMALY_NOTE = "Anomalies use 1982-2022 Jan-May monthly climatology."
PACIFIC_BOXES = {
    "Darwin": (-20, -5, 120, 140),
    "CWP": (-5, 5, 160, 220),
    "CP": (-5, 5, 180, 220),
    "EP": (-5, 5, 220, 260),
    "Tahiti": (-25, -10, 200, 220),
    "FEP": (-5, 5, 270, 280),
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


def subset(lon, lat, field, lon_min=120, lon_max=280, lat_min=-30, lat_max=30):
    lon_idx = np.where((lon >= lon_min) & (lon <= lon_max))[0]
    lat_idx = np.where((lat >= lat_min) & (lat <= lat_max))[0]
    return lon[lon_idx], lat[lat_idx], field[np.ix_(lat_idx, lon_idx)]


def format_axes(ax) -> None:
    ticks = [120, 160, 180, 200, 220, 240, 260, 280]
    ax.set_xlim(120, 280)
    ax.set_ylim(-30, 30)
    ax.set_xticks(ticks)
    ax.set_xticklabels([format_lon(tick) for tick in ticks])
    ax.set_yticks([-30, -15, 0, 15, 30])
    ax.set_yticklabels([format_lat(tick) for tick in [-30, -15, 0, 15, 30]])
    ax.axhline(0, color="0.2", linewidth=0.55)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def add_boxes(ax) -> None:
    for label, (lat0, lat1, lon0, lon1) in PACIFIC_BOXES.items():
        if lon1 < 120 or lon0 > 280:
            continue
        ax.plot([lon0, lon1, lon1, lon0, lon0], [lat0, lat0, lat1, lat1, lat0], color="0.16", lw=0.75)
        dx, dy = {
            "Tahiti": (1, 1),
            "Darwin": (1, 1),
            "FEP": (-8, 1),
            "CP": (1, 1),
            "EP": (1, 1),
            "CWP": (1, 1),
        }.get(label, (1, 1))
        ax.text(lon0 + dx, lat1 + dy, label, fontsize=6.7, color="0.16")


def add_vectors(ax, lon, lat, u, v, *, scale=48, key=False) -> None:
    xlon, ylat, uu = subset(lon, lat, u)
    _, _, vv = subset(lon, lat, v)
    q = ax.quiver(
        xlon[::5],
        ylat[::3],
        uu[::3, ::5],
        vv[::3, ::5],
        color="0.1",
        pivot="middle",
        width=0.0028,
        headwidth=3.2,
        scale=scale,
    )
    if key:
        ax.quiverkey(q, 0.82, 0.92, 4, "4 m/s", labelpos="E", coordinates="axes", fontproperties={"size": 8})


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.16)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.16)
    print(png)
    print(pdf)


def plot_surface(data) -> None:
    lon, lat = data["lon"], data["lat"]
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.0), constrained_layout=True)
    fig.suptitle("ERA5 2026 surface atmospheric response: wind and pressure", weight="bold")

    specs = [
        (axes[0, 0], "u10_MAM", "u10", "v10", "MAM 2026 ERA5 u10 + 10 m wind", "RdBu_r", -3, 3, "u10 anomaly (m/s)"),
        (axes[0, 1], "u10_AM_to_date", "u10", "v10", "Apr-May 2026 ERA5 u10 + 10 m wind", "RdBu_r", -3, 3, "u10 anomaly (m/s)"),
        (axes[1, 0], "msl_hpa_MAM", "u10", "v10", "MAM 2026 ERA5 MSLP + 10 m wind", "RdBu_r", -3, 3, "MSLP anomaly (hPa)"),
        (axes[1, 1], "msl_hpa_AM_to_date", "u10", "v10", "Apr-May 2026 ERA5 MSLP + 10 m wind", "RdBu_r", -3, 3, "MSLP anomaly (hPa)"),
    ]
    meshes = []
    for ax, field_key, u_prefix, v_prefix, title, cmap, vmin, vmax, label in specs:
        xlon, ylat, field = subset(lon, lat, data[field_key])
        mesh = ax.pcolormesh(xlon, ylat, field, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        meshes.append((mesh, label))
        period = "MAM" if "MAM" in field_key else "AM_to_date"
        add_vectors(ax, lon, lat, data[f"{u_prefix}_{period}"], data[f"{v_prefix}_{period}"], key=ax is axes[0, 1])
        format_axes(ax)
        add_boxes(ax)
        ax.set_title(title)

    fig.colorbar(meshes[0][0], ax=axes[0, :], label=meshes[0][1], shrink=0.96)
    fig.colorbar(meshes[2][0], ax=axes[1, :], label=meshes[2][1], shrink=0.96)
    fig.text(
        0.01,
        -0.015,
        f"ERA5 monthly means from CDS, 1 degree grid. {ANOMALY_NOTE} MAM=Mar-Apr-May; Apr-May is current AM-to-date.",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig8_2026_era5_surface_wind_pressure")
    plt.close(fig)


def plot_precip_pressurelevel(data) -> None:
    lon, lat = data["lon"], data["lat"]
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 7.0), constrained_layout=True)
    fig.suptitle("ERA5 2026 precipitation and 850 hPa circulation anomalies", weight="bold")

    specs = [
        (axes[0, 0], "tp_mm_day_MAM", "u850", "v850", "MAM 2026 ERA5 precipitation + 850 hPa wind", "BrBG", -5, 5, "Precipitation anomaly (mm/day)"),
        (axes[0, 1], "tp_mm_day_AM_to_date", "u850", "v850", "Apr-May 2026 ERA5 precipitation + 850 hPa wind", "BrBG", -5, 5, "Precipitation anomaly (mm/day)"),
        (axes[1, 0], "omega850_MAM", "u850", "v850", "MAM 2026 ERA5 omega850 + 850 hPa wind", "RdBu_r", -0.08, 0.08, "omega850 anomaly (Pa/s; + downward)"),
        (axes[1, 1], "omega850_AM_to_date", "u850", "v850", "Apr-May 2026 ERA5 omega850 + 850 hPa wind", "RdBu_r", -0.08, 0.08, "omega850 anomaly (Pa/s; + downward)"),
    ]
    meshes = []
    for ax, field_key, u_prefix, v_prefix, title, cmap, vmin, vmax, label in specs:
        xlon, ylat, field = subset(lon, lat, data[field_key])
        mesh = ax.pcolormesh(xlon, ylat, field, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        meshes.append((mesh, label))
        period = "MAM" if "MAM" in field_key else "AM_to_date"
        add_vectors(ax, lon, lat, data[f"{u_prefix}_{period}"], data[f"{v_prefix}_{period}"], scale=55, key=ax is axes[0, 1])
        format_axes(ax)
        add_boxes(ax)
        ax.set_title(title)

    fig.colorbar(meshes[0][0], ax=axes[0, :], label=meshes[0][1], shrink=0.96)
    fig.colorbar(meshes[2][0], ax=axes[1, :], label=meshes[2][1], shrink=0.96)
    fig.text(
        0.01,
        -0.015,
        f"ERA5 total precipitation monthly means are converted from m/day to mm/day. {ANOMALY_NOTE} Positive omega means downward motion; negative omega means upward motion.",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig9_2026_era5_precip_u850_omega")
    plt.close(fig)


def plot_hovmoller(data) -> None:
    lon = data["lon"]
    idx = np.where((lon >= 120) & (lon <= 280))[0]
    xlon = lon[idx]
    months = ["Jan", "Feb", "Mar", "Apr", "May"]

    fig, axes = plt.subplots(3, 1, figsize=(11.8, 7.8), constrained_layout=True)
    fig.suptitle("ERA5 equatorial longitude-time view: wind and rainfall response during 2026", weight="bold")
    panels = [
        (axes[0], data["u10_hov"][:, idx], "ERA5 u10 anomaly averaged over 5S-5N", "RdBu_r", -3, 3, "u10 (m/s; + westerly)"),
        (axes[1], data["u850_hov"][:, idx], "ERA5 u850 anomaly averaged over 5S-5N", "RdBu_r", -4, 4, "u850 (m/s; + westerly)"),
        (axes[2], data["tp_hov"][:, idx], "ERA5 precipitation anomaly averaged over 5S-5N", "BrBG", -4, 4, "precip (mm/day)"),
    ]
    for ax, field, title, cmap, vmin, vmax, label in panels:
        mesh = ax.pcolormesh(xlon, np.arange(len(months)), field, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        ax.set_title(title)
        ax.set_yticks(range(len(months)))
        ax.set_yticklabels(months)
        ticks = [120, 160, 180, 200, 220, 240, 260, 280]
        ax.set_xticks(ticks)
        ax.set_xticklabels([format_lon(tick) for tick in ticks])
        ax.set_xlim(120, 280)
        ax.set_ylabel("2026 month")
        ax.set_xlabel("Longitude")
        for x, text in [(180, "Date line"), (220, "CP"), (260, "EP"), (270, "FEP")]:
            ax.axvline(x, color="0.25", lw=0.55, ls="--")
            ax.text(x + 1, -0.35, text, fontsize=7, color="0.25")
        fig.colorbar(mesh, ax=ax, label=label)
    fig.text(
        0.01,
        -0.015,
        f"Hovmoller fields are monthly anomalies averaged over 5S-5N. {ANOMALY_NOTE}",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig10_2026_era5_equatorial_hovmoller")
    plt.close(fig)


def main() -> int:
    setup_style()
    data = np.load(INPUT, allow_pickle=True)
    plot_surface(data)
    plot_precip_pressurelevel(data)
    plot_hovmoller(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
