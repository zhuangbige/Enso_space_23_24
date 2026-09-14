#!/usr/bin/env python3
"""Plot January--June SODA3 longitude-depth sections for five latitude bands."""

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
    / "soda3_ohc_lon_depth_sections_five_latbands_1997_2015_2023_1980_2024_detrended.nc"
)
OUT_DIR = (
    ROOT
    / "outputs/research_2026"
    / "soda3_ohc_lon_depth_sections_five_latbands_1980_2024_detrended"
)
EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
BAND_ORDER = (
    "north_15_30",
    "north_5_15",
    "equatorial_5s_5n",
    "south_5_15",
    "south_15_30",
)


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
            "font.size": 8.8,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.0,
            "xtick.labelsize": 7.6,
            "ytick.labelsize": 7.6,
            "axes.linewidth": 0.78,
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
    required = {
        "heat_content_density_anomaly",
        "band_label",
        "band",
        "time",
        "depth",
        "lon",
    }
    missing = required.difference(set(dataset.variables) | set(dataset.coords))
    if missing:
        raise ValueError(f"Five-band input is missing {sorted(missing)}")
    field = dataset.heat_content_density_anomaly
    if field.dims != ("band", "time", "depth", "lon"):
        raise ValueError(f"Unexpected dimensions: {field.dims}")
    if tuple(str(value) for value in dataset.band.values) != BAND_ORDER:
        raise ValueError(f"Unexpected band order: {dataset.band.values}")
    if field.attrs.get("units") != "MJ m-3":
        raise ValueError(f"Unexpected units: {field.attrs.get('units')}")
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


def plot_event(
    dataset: xr.Dataset,
    event: int,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(
        len(BAND_ORDER),
        len(MONTHS),
        figsize=(20.4, 13.0),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    fig.subplots_adjust(
        left=0.075,
        right=0.995,
        top=0.91,
        bottom=0.13,
        wspace=0.07,
        hspace=0.15,
    )
    fig.suptitle(
        f"{event} January–June SODA3 upper-ocean heat-content structure by latitude band",
        fontsize=17,
        fontweight="bold",
        y=0.975,
    )
    selected_time = dataset.where(dataset.time.dt.year == event, drop=True)
    mesh = None
    for row, band in enumerate(BAND_ORDER):
        selected = selected_time.sel(band=band)
        label = str(dataset.band_label.sel(band=band).item())
        for col, month_label in enumerate(MONTH_LABELS):
            ax = axes[row, col]
            # Intentionally no black contours, boxes, or other field overlays.
            mesh = ax.pcolormesh(
                selected.lon,
                selected.depth,
                selected.heat_content_density_anomaly.isel(time=col),
                cmap="RdBu_r",
                norm=norm,
                shading="auto",
                rasterized=True,
            )
            format_axis(
                ax,
                show_xlabel=row == len(BAND_ORDER) - 1,
                show_ylabel=col == 0,
            )
            if row == 0:
                ax.set_title(month_label, fontsize=11.2, fontweight="bold", pad=5)
            if col == 0:
                ax.set_ylabel(f"{label}\nDepth (m)", fontsize=9.2, fontweight="bold")
    assert mesh is not None
    cax = fig.add_axes((0.27, 0.055, 0.48, 0.022))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Heat-content density anomaly ρ₀CₚT′ (MJ m$^{-3}$)")
    colorbar.set_ticks(np.linspace(-vlim, vlim, 9))
    note = (
        "Rows are cosine-latitude-weighted means over valid ocean cells; 1980–2024 "
        "same-calendar-month detrended anomalies. Continuous native SODA depth levels; "
        "120°E–80°W; common color scale. Sparse coastal/deep cells below 30% band coverage are masked."
    )
    fig.text(0.012, 0.012, note, fontsize=8.2, color="0.30")
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"fig_{event}_jan_jun_soda3_ohc_lon_depth_sections_"
        "five_latbands_1980_2024_detrended"
    )
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(png)
    print(pdf)
    return png, pdf


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
    print(
        "Five-band plot diagnostics: "
        f"finite={finite.mean():.4f}, range=[{np.nanmin(values):.3f}, {np.nanmax(values):.3f}], "
        f"fraction beyond color limit={np.mean(np.abs(values[finite]) > args.vlim):.4f}",
        flush=True,
    )
    for event in EVENTS:
        plot_event(dataset, event, args.output_dir, args.vlim)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
