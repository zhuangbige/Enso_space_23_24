#!/usr/bin/env python3
"""Plot 30S--30N mean SODA3 longitude-depth sections without overlays."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


INPUT_FILE = (
    ROOT
    / "data/derived/research_2026"
    / "soda3_ohc_lon_depth_sections_30s30n_1997_2015_2023_1980_2024_detrended.nc"
)
OUT_DIR = (
    ROOT
    / "outputs/research_2026"
    / "soda3_ohc_lon_depth_sections_30s30n_1980_2024_detrended"
)
EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_FILE)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--vlim", type=float, default=16.0)
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.2,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "axes.linewidth": 0.82,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def format_lon(value: float) -> str:
    longitude = value % 360.0
    if np.isclose(longitude, 180.0):
        return "180°"
    if longitude < 180.0:
        return f"{longitude:g}°E"
    return f"{360.0 - longitude:g}°W"


def validate(dataset: xr.Dataset) -> None:
    required = {"heat_content_density_anomaly", "time", "depth", "lon"}
    missing = required.difference(set(dataset.variables) | set(dataset.coords))
    if missing:
        raise ValueError(f"Section input is missing {sorted(missing)}")
    field = dataset.heat_content_density_anomaly
    if field.dims != ("time", "depth", "lon"):
        raise ValueError(f"Unexpected section dimensions: {field.dims}")
    if field.attrs.get("units") != "MJ m-3":
        raise ValueError(f"Unexpected units: {field.attrs.get('units')}")
    if str(dataset.attrs.get("latitude_average", "")).find("30S to 30N") < 0:
        raise ValueError("Input is not the 30S--30N latitude-mean product")
    years = tuple(int(value) for value in np.unique(dataset.time.dt.year.values))
    months = tuple(int(value) for value in np.unique(dataset.time.dt.month.values))
    if years != EVENTS or months != MONTHS:
        raise ValueError(f"Unexpected event/time coordinates: years={years}, months={months}")


def format_axis(
    ax: plt.Axes,
    *,
    show_xlabel: bool,
    show_ylabel: bool,
) -> None:
    xticks = (120, 160, 180, 220, 240, 280)
    ax.set_xlim(120, 280)
    ax.set_ylim(300, 0)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(value) for value in xticks])
    ax.set_yticks((0, 50, 100, 150, 200, 250, 300))
    if show_xlabel:
        ax.set_xlabel("Longitude")
    else:
        ax.tick_params(labelbottom=False)
    if show_ylabel:
        ax.set_ylabel("Depth (m)")
    else:
        ax.tick_params(labelleft=False)


def draw(
    ax: plt.Axes,
    field: xr.DataArray,
    norm: TwoSlopeNorm,
) -> plt.collections.QuadMesh:
    # Intentionally no contour lines, boxes, or other black overlays.
    return ax.pcolormesh(
        field.lon,
        field.depth,
        field,
        cmap="RdBu_r",
        norm=norm,
        shading="auto",
        rasterized=True,
    )


def save(fig: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(png)
    print(pdf)
    return png, pdf


def plot_event(
    dataset: xr.Dataset,
    event: int,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    selected = dataset.where(dataset.time.dt.year == event, drop=True)
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(2, 3, figsize=(14.4, 8.0), sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.06,
        right=0.99,
        top=0.88,
        bottom=0.18,
        wspace=0.08,
        hspace=0.20,
    )
    fig.suptitle(
        f"{event} January–June SODA3 upper-ocean heat-content structure: 30°S–30°N mean",
        fontsize=16,
        fontweight="bold",
        y=0.965,
    )
    mesh = None
    for index, ax in enumerate(axes.ravel()):
        row, col = divmod(index, 3)
        mesh = draw(
            ax,
            selected.heat_content_density_anomaly.isel(time=index),
            norm,
        )
        format_axis(ax, show_xlabel=row == 1, show_ylabel=col == 0)
        ax.set_title(f"{MONTH_LABELS[index]} {event}", fontsize=12, fontweight="bold", pad=5)
    assert mesh is not None
    cax = fig.add_axes((0.24, 0.09, 0.52, 0.025))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Heat-content density anomaly ρ₀CₚT′ (MJ m$^{-3}$)")
    note = (
        "30°S–30°N cosine-latitude-weighted mean; 1980–2024 same-calendar-month "
        "detrended anomalies. Continuous native SODA depth levels; 120°E–80°W."
    )
    fig.text(0.012, 0.014, note, fontsize=8.1, color="0.30")
    stem = (
        f"fig_{event}_jan_jun_soda3_ohc_lon_depth_section_"
        "30s30n_mean_1980_2024_detrended"
    )
    return save(fig, output_dir, stem)


def plot_combined(
    dataset: xr.Dataset,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(
        len(EVENTS),
        len(MONTHS),
        figsize=(20.4, 9.2),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    fig.subplots_adjust(
        left=0.060,
        right=0.995,
        top=0.89,
        bottom=0.17,
        wspace=0.07,
        hspace=0.15,
    )
    fig.suptitle(
        "January–June 30°S–30°N mean SODA3 upper-ocean heat-content structure: 1997, 2015, and 2023",
        fontsize=17,
        fontweight="bold",
        y=0.965,
    )
    mesh = None
    for row, event in enumerate(EVENTS):
        selected = dataset.where(dataset.time.dt.year == event, drop=True)
        for col, month_label in enumerate(MONTH_LABELS):
            ax = axes[row, col]
            mesh = draw(
                ax,
                selected.heat_content_density_anomaly.isel(time=col),
                norm,
            )
            format_axis(
                ax,
                show_xlabel=row == len(EVENTS) - 1,
                show_ylabel=col == 0,
            )
            if row == 0:
                ax.set_title(month_label, fontsize=11, fontweight="bold", pad=5)
            if col == 0:
                ax.set_ylabel(f"{event}\nDepth (m)", fontsize=9.5, fontweight="bold")
    assert mesh is not None
    cax = fig.add_axes((0.26, 0.085, 0.50, 0.024))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Heat-content density anomaly ρ₀CₚT′ (MJ m$^{-3}$)")
    note = (
        "30°S–30°N cosine-latitude-weighted mean; 1980–2024 same-calendar-month "
        "detrended anomalies. Continuous native SODA depth levels; 120°E–80°W."
    )
    fig.text(0.012, 0.014, note, fontsize=8.1, color="0.30")
    stem = (
        "fig_1997_2015_2023_jan_jun_soda3_ohc_lon_depth_sections_"
        "30s30n_mean_1980_2024_detrended"
    )
    return save(fig, output_dir, stem)


def main() -> int:
    args = parse_args()
    if args.vlim <= 0:
        raise ValueError("--vlim must be positive")
    setup_style()
    with xr.open_dataset(args.input, engine="netcdf4") as source:
        validate(source)
        dataset = source.load()
    values = dataset.heat_content_density_anomaly.values.astype(float)
    finite = np.isfinite(values)
    clipped = np.mean(np.abs(values[finite]) > args.vlim)
    print(
        "30S-30N longitude-depth diagnostics: "
        f"finite={finite.mean():.4f}, range=[{np.nanmin(values):.3f}, {np.nanmax(values):.3f}], "
        f"p02={np.nanquantile(values, 0.02):.3f}, p98={np.nanquantile(values, 0.98):.3f}, "
        f"fraction beyond color limit={clipped:.4f}",
        flush=True,
    )
    for event in EVENTS:
        plot_event(dataset, event, args.output_dir, args.vlim)
    plot_combined(dataset, args.output_dir, args.vlim)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
