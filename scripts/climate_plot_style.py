"""Compact, manuscript-friendly Matplotlib helpers for climate figures."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt


DEFAULT_DIVERGING = "RdBu_r"


def apply_climate_style(base_font_size: int = 10) -> None:
    """Apply deterministic defaults suitable for paper and presentation figures."""

    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": base_font_size,
            "axes.titlesize": base_font_size + 1,
            "axes.labelsize": base_font_size,
            "xtick.labelsize": base_font_size - 1,
            "ytick.labelsize": base_font_size - 1,
            "legend.fontsize": base_font_size - 1,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.6,
            "patch.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def add_panel_labels(
    axes: Sequence[plt.Axes],
    *,
    x: float = 0.02,
    y: float = 0.98,
) -> None:
    """Add a, b, c panel labels to axes."""

    for index, axis in enumerate(axes):
        axis.text(
            x,
            y,
            f"{chr(97 + index)}",
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontweight="bold",
            fontsize=plt.rcParams["font.size"] + 1,
        )


def save_figure(fig: plt.Figure, path: str | Path, *, dpi: int = 300) -> Path:
    """Create the parent directory and save a tightly bounded figure."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, bbox_inches="tight", pad_inches=0.08)
    return output
