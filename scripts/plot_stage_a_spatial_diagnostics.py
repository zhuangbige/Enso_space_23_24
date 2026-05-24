#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OISST = ROOT / "data/interim/raw_validation/oisst_spatial_amj_jja.npz"
GPCP = ROOT / "data/interim/raw_validation/gpcp_spatial_amj_jja.npz"
OUT = ROOT / "data/derived/research/stage_a_amj_jja_sst_precip.png"
SEASONS = ("AMJ", "JJA")
SST_BOXES = {
    "Nino-3": (-5, 5, 210, 270),
    "TNA": (0, 20, 300, 340),
    "TIO": (-20, 20, 40, 110),
    "MC": (-10, 10, 95, 150),
    "WPWP": (-10, 10, 120, 160),
}
PRECIP_BOXES = {
    "WCP": (-5, 5, 140, 180),
    "CP": (-5, 5, 180, 220),
    "EP": (-5, 5, 220, 260),
}


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 250,
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.linewidth": 0.8,
        }
    )


def _format_lon(value: float) -> str:
    lon = value % 360
    if lon == 0:
        return "0"
    if lon == 180:
        return "180"
    if lon < 180:
        return f"{lon:g}E"
    return f"{360 - lon:g}W"


def _format_axes(ax, lon_ticks) -> None:
    ax.set_ylim(-30, 30)
    ax.set_yticks([-30, -15, 0, 15, 30])
    ax.set_xticks(lon_ticks)
    ax.set_xticklabels([_format_lon(tick) for tick in lon_ticks])
    ax.axhline(0, color="0.2", linewidth=0.5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def _add_boxes(ax, boxes: dict[str, tuple[float, float, float, float]], lon_min: float, lon_max: float) -> None:
    for label, (lat0, lat1, x0, x1) in boxes.items():
        if x1 < lon_min or x0 > lon_max:
            continue
        x0_clip = max(x0, lon_min)
        x1_clip = min(x1, lon_max)
        ax.plot([x0_clip, x1_clip, x1_clip, x0_clip, x0_clip], [lat0, lat0, lat1, lat1, lat0], color="black", linewidth=0.7)
        ax.text(x0_clip + 1, lat1 + 1, label, fontsize=6, color="black")


def main() -> int:
    _style()
    sst = np.load(OISST)
    precip = np.load(GPCP)

    fig, axes = plt.subplots(2, 2, figsize=(11, 5.8), constrained_layout=True)
    for col, season in enumerate(SEASONS):
        ax = axes[0, col]
        mesh = ax.pcolormesh(
            sst["lon"],
            sst["lat"],
            sst[f"{season}_difference"],
            cmap="RdBu_r",
            vmin=-2.0,
            vmax=2.0,
            shading="auto",
        )
        ax.set_title(f"{season} SST: 2023 minus comparable")
        _format_axes(ax, [40, 80, 120, 160, 200, 240, 280, 320])
        _add_boxes(ax, SST_BOXES, 40, 340)
        fig.colorbar(mesh, ax=ax, label="deg C")

        ax = axes[1, col]
        mesh = ax.pcolormesh(
            precip["lon"],
            precip["lat"],
            precip[f"{season}_difference"],
            cmap="BrBG",
            vmin=-4.0,
            vmax=4.0,
            shading="auto",
        )
        ax.set_title(f"{season} GPCP precip: 2023 minus comparable")
        _format_axes(ax, [120, 160, 200, 240, 280])
        _add_boxes(ax, PRECIP_BOXES, 120, 280)
        fig.colorbar(mesh, ax=ax, label="mm/day")

    fig.suptitle("Stage A quick-look: developing-season SST and precipitation asynchrony")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
