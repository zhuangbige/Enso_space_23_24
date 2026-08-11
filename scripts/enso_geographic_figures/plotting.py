"""Shared publication-style map and export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import numpy as np

from .config import BOXES, COAST_COLOR, GRID_COLOR, LAND_COLOR


DATA_CRS = ccrs.PlateCarree()
MAP_CRS = ccrs.PlateCarree(central_longitude=180.0)
DEFAULT_EXTENT = (130.0, 280.0, -15.0, 12.0)


def apply_scientific_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10.5,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.fontsize": 9.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
        }
    )


def create_pacific_axes(
    fig: Figure,
    nrows: int,
    ncols: int,
    *,
    squeeze: bool = True,
) -> np.ndarray | Axes:
    return fig.subplots(
        nrows,
        ncols,
        squeeze=squeeze,
        subplot_kw={"projection": MAP_CRS},
    )


def format_pacific_axis(
    ax: Axes,
    *,
    extent: tuple[float, float, float, float] = DEFAULT_EXTENT,
    label_left: bool = False,
    label_bottom: bool = True,
) -> None:
    ax.set_extent(extent, crs=DATA_CRS)
    ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor=LAND_COLOR, zorder=5)
    ax.coastlines("110m", color=COAST_COLOR, linewidth=0.65, zorder=6)
    grid = ax.gridlines(
        crs=DATA_CRS,
        draw_labels=True,
        linewidth=0.45,
        color=GRID_COLOR,
        alpha=0.75,
        linestyle=":",
        xlocs=[140, 180, 220, 260, 280],
        ylocs=[-10, 0, 5, 10],
    )
    grid.top_labels = False
    grid.right_labels = False
    grid.left_labels = label_left
    grid.bottom_labels = label_bottom
    grid.xformatter = LONGITUDE_FORMATTER
    grid.yformatter = LATITUDE_FORMATTER
    grid.xlabel_style = {"size": 9}
    grid.ylabel_style = {"size": 9}


def draw_box_boundaries(ax: Axes, emphasize_gate: float | None = None) -> None:
    for name, (west, east, south, north) in BOXES.items():
        linewidth = 1.25 if name == "east" else 0.85
        rectangle = Rectangle(
            (west, south),
            east - west,
            north - south,
            fill=False,
            edgecolor="#20313D",
            linewidth=linewidth,
            linestyle="-" if name == "east" else "--",
            transform=DATA_CRS,
            zorder=9,
        )
        ax.add_patch(rectangle)
    if emphasize_gate is not None:
        ax.plot(
            [emphasize_gate, emphasize_gate],
            [-10.0, 5.0],
            color="#111820",
            linewidth=2.2,
            transform=DATA_CRS,
            zorder=10,
        )


def arrow_width_zj(value: float, max_abs: float) -> float:
    if max_abs <= 0:
        raise ValueError("max_abs must be positive")
    if value == 0:
        return 0.0
    return float(0.8 + 5.2 * np.sqrt(abs(value) / max_abs))


def symmetric_limit(values: Iterable[float], *, minimum: float = 1.0) -> float:
    array = np.asarray(list(values), dtype=float)
    finite = np.abs(array[np.isfinite(array)])
    if not finite.size:
        return minimum
    return float(max(minimum, np.nanpercentile(finite, 98)))


def add_panel_label(ax: Axes, label: str, *, color: str = "#101820") -> None:
    ax.text(
        0.018,
        0.96,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11.5,
        fontweight="bold",
        color=color,
        zorder=20,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.74, "pad": 1.5},
    )


def save_figure_pair(fig: Figure, stem: str, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png, pdf


apply_scientific_style()
