#!/usr/bin/env python3
"""Plot fixed 120E--80W SODA3 latitude-depth sections for ENSO events."""

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
    / "soda3_ohc_meridional_sections_full_pacific_120e80w_"
    "1997_2015_2023_1980_2024_detrended.nc"
)
OUT_DIR = (
    ROOT
    / "outputs/research_2026"
    / "soda3_full_pacific_meridional_sections_120e80w_1980_2024_detrended"
)
EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
BASELINE = (1980, 2024)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_FILE)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--vlim", type=float, default=6.0)
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.4,
            "axes.titlesize": 10.8,
            "axes.labelsize": 9.8,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "axes.linewidth": 0.84,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def format_lat(value: float) -> str:
    if np.isclose(value, 0.0):
        return "Eq"
    return f"{abs(value):.0f}°{'N' if value > 0 else 'S'}"


def validate(dataset: xr.Dataset) -> None:
    required = {
        "temperature_anomaly",
        "heat_content_density_anomaly",
        "valid_longitude_fraction",
        "event",
        "month",
        "depth",
        "lat",
    }
    missing = required.difference(set(dataset.variables) | set(dataset.coords))
    if missing:
        raise ValueError(f"Section input is missing {sorted(missing)}")
    expected_dims = ("event", "month", "depth", "lat")
    if dataset.heat_content_density_anomaly.dims != expected_dims:
        raise ValueError(
            f"Unexpected heat-density dimensions: {dataset.heat_content_density_anomaly.dims}"
        )
    if tuple(int(value) for value in dataset.event.values) != EVENTS:
        raise ValueError(f"Unexpected event coordinate: {dataset.event.values}")
    if tuple(int(value) for value in dataset.month.values) != MONTHS:
        raise ValueError(f"Unexpected month coordinate: {dataset.month.values}")
    if dataset.heat_content_density_anomaly.attrs.get("units") != "MJ m-3":
        raise ValueError("Unexpected heat-content-density units")
    if float(dataset.lat.min()) > -29.5 or float(dataset.lat.max()) < 29.5:
        raise ValueError("Latitude section does not span 30S--30N")
    if float(dataset.depth.max()) < 280.0:
        raise ValueError("Depth section does not span the upper 300 m")
    if not np.isclose(dataset.attrs.get("longitude_min_degrees_east"), 120.0):
        raise ValueError("Unexpected western longitude boundary")
    if not np.isclose(dataset.attrs.get("longitude_max_degrees_east"), 280.0):
        raise ValueError("Unexpected eastern longitude boundary")


def format_axis(ax: plt.Axes, *, row: int, col: int) -> None:
    xticks = (-30, -20, -10, 0, 10, 20, 30)
    ax.set_xlim(-30, 30)
    ax.set_ylim(300, 0)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lat(value) for value in xticks])
    ax.set_yticks((0, 50, 100, 150, 200, 250, 300))
    ax.axvline(0.0, color="0.35", linewidth=0.55, zorder=5)
    if row == 1:
        ax.set_xlabel("Latitude")
    else:
        ax.tick_params(labelbottom=False)
    if col == 0:
        ax.set_ylabel("Depth (m)")
    else:
        ax.tick_params(labelleft=False)


def plot_event(
    dataset: xr.Dataset,
    event: int,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    selected = dataset.sel(event=event)
    field = selected.heat_content_density_anomaly
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(2, 3, figsize=(13.8, 7.6), sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.065,
        right=0.988,
        top=0.865,
        bottom=0.18,
        wspace=0.08,
        hspace=0.28,
    )
    fig.suptitle(
        f"{event} January–June SODA3 full-Pacific meridional upper-ocean structure",
        fontsize=16.0,
        fontweight="bold",
        y=0.965,
    )
    mesh = None
    for index, ax in enumerate(axes.ravel()):
        row, col = divmod(index, 3)
        values = field.isel(month=index).values.astype(float)
        mesh = ax.pcolormesh(
            selected.lat,
            selected.depth,
            values,
            cmap="RdBu_r",
            norm=norm,
            shading="auto",
            rasterized=True,
            zorder=1,
        )
        ax.set_title(
            f"{MONTH_LABELS[index]} {event} · 120°E–80°W mean",
            fontsize=11.0,
            fontweight="bold",
            pad=5,
        )
        format_axis(ax, row=row, col=col)
    assert mesh is not None
    cax = fig.add_axes((0.24, 0.085, 0.52, 0.027))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Heat-content density anomaly ρ₀CₚT′ (MJ m$^{-3}$)")
    colorbar.set_ticks(np.linspace(-vlim, vlim, 7))
    note = (
        "30°S–30°N, 0–300 m; every panel uses the same 120°E–80°W longitude mean. "
        f"{BASELINE[0]}–{BASELINE[1]} same-calendar-month detrended anomalies; "
        "no contour or analysis-box overlays."
    )
    fig.text(0.012, 0.018, note, fontsize=8.2, color="0.30")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"fig_{event}_jan_jun_soda3_full_pacific_meridional_section_"
        f"120e80w_30s30n_{BASELINE[0]}_{BASELINE[1]}_detrended"
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
    clipped = np.mean(np.abs(values[finite]) > args.vlim)
    print(
        "Full-Pacific section diagnostics: "
        f"finite={finite.mean():.4f}, range=[{np.nanmin(values):.3f}, {np.nanmax(values):.3f}], "
        f"p02={np.nanquantile(values, 0.02):.3f}, p98={np.nanquantile(values, 0.98):.3f}, "
        f"fraction beyond color limit={clipped:.4f}",
        flush=True,
    )
    for event in EVENTS:
        plot_event(dataset, event, args.output_dir, args.vlim)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
