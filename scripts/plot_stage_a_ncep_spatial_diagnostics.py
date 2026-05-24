#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
NCEP = ROOT / "data/interim/raw_validation/ncep_spatial_amj_jja.npz"
OUT = ROOT / "data/derived/research/stage_a_amj_jja_ncep_wind_slp.png"
SEASONS = ("AMJ", "JJA")
BOXES = {
    "CWP u": (-5, 5, 160, 220),
    "Tahiti": (-25, -10, 200, 220),
    "Darwin": (-20, -5, 120, 140),
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
    if lon == 180:
        return "180"
    if lon < 180:
        return f"{lon:g}E"
    return f"{360 - lon:g}W"


def _format_axes(ax) -> None:
    ax.set_ylim(-30, 30)
    ax.set_yticks([-30, -15, 0, 15, 30])
    ticks = [120, 160, 200, 240, 280]
    ax.set_xticks(ticks)
    ax.set_xticklabels([_format_lon(tick) for tick in ticks])
    ax.axhline(0, color="0.2", linewidth=0.5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def _add_boxes(ax) -> None:
    for label, (lat0, lat1, x0, x1) in BOXES.items():
        ax.plot([x0, x1, x1, x0, x0], [lat0, lat0, lat1, lat1, lat0], color="black", linewidth=0.7)
        ax.text(x0 + 1, lat1 + 1, label, fontsize=6, color="black")


def main() -> int:
    _style()
    data = np.load(NCEP)
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 5.8), constrained_layout=True)
    for col, season in enumerate(SEASONS):
        ax = axes[0, col]
        mesh = ax.pcolormesh(
            data["lon"],
            data["lat"],
            data[f"uwnd_{season}_difference"],
            cmap="RdBu_r",
            vmin=-4,
            vmax=4,
            shading="auto",
        )
        ax.set_title(f"{season} NCEP sig995 u: 2023 minus comparable")
        _format_axes(ax)
        _add_boxes(ax)
        fig.colorbar(mesh, ax=ax, label="m/s")

        ax = axes[1, col]
        mesh = ax.pcolormesh(
            data["lon"],
            data["lat"],
            data[f"slp_{season}_difference"],
            cmap="RdBu_r",
            vmin=-3,
            vmax=3,
            shading="auto",
        )
        ax.set_title(f"{season} NCEP SLP: 2023 minus comparable")
        _format_axes(ax)
        _add_boxes(ax)
        fig.colorbar(mesh, ax=ax, label="hPa")

    fig.suptitle("Stage A quick-look: NCEP fallback wind and pressure asynchrony")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
