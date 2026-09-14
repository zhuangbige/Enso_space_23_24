#!/usr/bin/env python3
"""Plot continuous January--June upper-ocean heat-content sections.

Because vertically integrated OHC has no depth coordinate, the section shading
uses heat-content density anomaly rho0*cp0*T' (MJ m-3) on the native SODA depth
levels.  No vertical bins or horizontal budget boxes are applied.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


TEMP_FILE = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
OUT_DIR = ROOT / "outputs/research_2026/soda3_ohc_vertical_sections_1980_2024_detrended"
DERIVED_NC = (
    ROOT
    / "data/derived/research_2026"
    / "soda3_ohc_vertical_sections_continuous_1997_2015_2023_1980_2024_detrended.nc"
)

EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
BASELINE = (1980, 2024)
LAT_BOUNDS = (-5.0, 5.0)
RHO0 = 1025.0
CP0 = 3990.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, nargs="+", default=list(EVENTS))
    parser.add_argument(
        "--vlim",
        type=float,
        default=16.0,
        help="Symmetric heat-content-density color limit in MJ m-3.",
    )
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--derived-nc", type=Path, default=DERIVED_NC)
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.2,
            "axes.titlesize": 10.6,
            "axes.labelsize": 9.4,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "axes.linewidth": 0.82,
            "axes.unicode_minus": False,
        }
    )


def open_dataset(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    try:
        return xr.open_dataset(path, engine="netcdf4")
    except (OSError, ValueError):
        return xr.open_dataset(path, engine="scipy")


def validate_input(ds: xr.Dataset) -> None:
    required = {"temp", "time", "depth", "lat", "lon"}
    missing = required.difference(set(ds.variables) | set(ds.coords))
    if missing:
        raise ValueError(f"Temperature input is missing: {sorted(missing)}")
    if ds.temp.dims != ("time", "depth", "lat", "lon"):
        raise ValueError(f"Unexpected temperature dimensions: {ds.temp.dims}")
    if ds.temp.attrs.get("units") != "degC":
        raise ValueError(f"Unexpected temperature units: {ds.temp.attrs.get('units')}")
    depth = ds.depth.values.astype(float)
    lat = ds.lat.values.astype(float)
    lon = ds.lon.values.astype(float)
    if not np.all(np.diff(depth) > 0):
        raise ValueError("Depth must increase downward")
    if not np.all(np.diff(lat) > 0) or not np.all(np.diff(lon) > 0):
        raise ValueError("Latitude and longitude must be increasing")
    if depth[0] > 10.0 or depth[-1] < 280.0:
        raise ValueError(f"Input does not span the upper 300 m: {depth[[0, -1]]}")
    years = ds.time.dt.year.values.astype(int)
    months = ds.time.dt.month.values.astype(int)
    if years.min() > BASELINE[0] or years.max() < BASELINE[1]:
        raise ValueError(
            f"Input span {years.min()}-{years.max()} does not cover baseline "
            f"{BASELINE[0]}-{BASELINE[1]}"
        )
    if set(np.unique(months)) != set(MONTHS):
        raise ValueError(f"Expected January--June only, got months {np.unique(months)}")


def equatorial_mean_temperature(ds: xr.Dataset) -> xr.DataArray:
    selected = ds.temp.where(
        (ds.lat >= LAT_BOUNDS[0]) & (ds.lat <= LAT_BOUNDS[1]), drop=True
    )
    # Use a time- and depth-invariant full-column ocean mask so the vertical
    # section and its depth integral sample the same latitude cells.
    valid_column = selected.notnull().all(("time", "depth"))
    weights = np.cos(np.deg2rad(selected.lat)).broadcast_like(valid_column)
    weights = weights.where(valid_column, 0.0)
    result = selected.weighted(weights).mean("lat", skipna=True)
    result.attrs.update(
        units="degC",
        long_name="Cosine-latitude-weighted equatorial potential temperature",
    )
    return result


def detrended_same_month_anomaly(da: xr.DataArray) -> xr.DataArray:
    """Remove each calendar month's configured mean and linear trend."""
    values = da.values.astype(np.float64)
    times = pd.DatetimeIndex(da.time.values)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    output = np.full(values.shape, np.nan, dtype=np.float32)
    for month in MONTHS:
        index = np.where(months == month)[0]
        fit_index = np.where(
            (months == month)
            & (years >= BASELINE[0])
            & (years <= BASELINE[1])
        )[0]
        expected = BASELINE[1] - BASELINE[0] + 1
        if fit_index.size != expected:
            raise ValueError(
                f"Unexpected baseline sample count for month {month}: {fit_index.size}"
            )
        x_fit = years[fit_index]
        center = float(x_fit.mean())
        xc_fit = x_fit - center
        fit_values = values[fit_index]
        finite = np.isfinite(fit_values)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(fit_values, axis=0),
            count,
            out=np.full(fit_values.shape[1:], np.nan),
            where=count > 0,
        )
        denominator = np.nansum(finite * xc_fit[:, None, None] ** 2, axis=0)
        slope = np.divide(
            np.nansum(xc_fit[:, None, None] * (fit_values - mean), axis=0),
            denominator,
            out=np.full(fit_values.shape[1:], np.nan),
            where=denominator > 0,
        )
        selected = values[index]
        xc_target = years[index] - center
        output[index] = (
            selected
            - mean[None, :, :]
            - slope[None, :, :] * xc_target[:, None, None]
        ).astype(np.float32)
    result = xr.DataArray(
        output,
        dims=da.dims,
        coords=da.coords,
        name="temperature_anomaly",
        attrs={
            "units": "degC",
            "long_name": "Detrended same-calendar-month equatorial potential-temperature anomaly",
            "baseline": f"{BASELINE[0]}-{BASELINE[1]}",
        },
    )
    return result


def build_diagnostics(anomaly: xr.DataArray, events: list[int]) -> xr.Dataset:
    event_mask = anomaly.time.dt.year.isin(events) & anomaly.time.dt.month.isin(MONTHS)
    selected = anomaly.where(event_mask, drop=True)
    expected = len(events) * len(MONTHS)
    if selected.sizes.get("time") != expected:
        raise ValueError(f"Expected {expected} event months, got {selected.sizes.get('time', 0)}")

    heat_density = selected * (RHO0 * CP0 / 1.0e6)
    heat_density.name = "heat_content_density_anomaly"
    heat_density.attrs.update(
        units="MJ m-3",
        long_name="Volumetric heat-content anomaly rho0*cp0*T_prime",
    )

    result = xr.Dataset(
        data_vars={
            "temperature_anomaly": selected.astype(np.float32),
            "heat_content_density_anomaly": heat_density.astype(np.float32),
        },
        coords={
            "time": selected.time,
            "depth": selected.depth,
            "lon": selected.lon,
        },
        attrs={
            "title": "SODA3.15.2 equatorial upper-ocean heat-content vertical diagnostics",
            "source": str(TEMP_FILE),
            "events": ", ".join(str(value) for value in events),
            "months": "January-June",
            "latitude_average": f"{LAT_BOUNDS[0]:g} to {LAT_BOUNDS[1]:g} degrees north, cosine weighted",
            "anomaly_definition": (
                f"{BASELINE[0]}-{BASELINE[1]} same-calendar-month climatology and linear trend removed"
            ),
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
        },
    )
    return result


def format_lon(value: float) -> str:
    longitude = value % 360.0
    if np.isclose(longitude, 180.0):
        return "180°"
    if longitude < 180.0:
        return f"{longitude:g}°E"
    return f"{360.0 - longitude:g}°W"


def format_section_axis(
    ax: plt.Axes,
    *,
    show_xlabel: bool,
    show_ylabel: bool,
    compact_longitude: bool = False,
) -> None:
    xticks = (120, 180, 240, 280) if compact_longitude else (120, 160, 180, 220, 240, 280)
    ax.set_xlim(120, 280)
    ax.set_ylim(300, 0)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(value) for value in xticks])
    ax.set_yticks((0, 50, 100, 150, 200, 250, 300))
    if show_xlabel:
        ax.set_xlabel("Longitude")
        if compact_longitude:
            ax.tick_params(axis="x", labelsize=7.1, pad=1.8)
    else:
        ax.tick_params(labelbottom=False)
    if show_ylabel:
        ax.set_ylabel("Depth (m)")
    else:
        ax.tick_params(labelleft=False)


def draw_section(
    ax: plt.Axes,
    field: xr.DataArray,
    *,
    norm: TwoSlopeNorm,
) -> plt.collections.QuadMesh:
    mesh = ax.pcolormesh(
        field.lon,
        field.depth,
        field,
        cmap="RdBu_r",
        norm=norm,
        shading="auto",
        rasterized=True,
        zorder=1,
    )
    return mesh


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print(png)
    print(pdf)
    return png, pdf


def plot_event(ds: xr.Dataset, event: int, output_dir: Path, vlim: float) -> tuple[Path, Path]:
    event_ds = ds.where(ds.time.dt.year == event, drop=True)
    if event_ds.sizes.get("time") != len(MONTHS):
        raise ValueError(f"Expected six months for {event}")
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(2, 3, figsize=(14.4, 8.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.06, right=0.99, top=0.88, bottom=0.18, wspace=0.08, hspace=0.20)
    fig.suptitle(
        f"{event} January–June equatorial SODA3 upper-ocean heat-content structure",
        fontsize=16,
        fontweight="bold",
        y=0.965,
    )
    mesh = None
    for index, (ax, month_label) in enumerate(zip(axes.ravel(), MONTH_LABELS)):
        row, col = divmod(index, 3)
        mesh = draw_section(
            ax,
            event_ds.heat_content_density_anomaly.isel(time=index),
            norm=norm,
        )
        format_section_axis(
            ax,
            show_xlabel=row == 1,
            show_ylabel=col == 0,
        )
        ax.set_title(f"{month_label} {event}", fontsize=12.0, fontweight="bold", pad=5)
    assert mesh is not None
    cax = fig.add_axes((0.24, 0.090, 0.52, 0.025))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Heat-content density anomaly ρ₀CₚT′ (MJ m$^{-3}$)")
    note = (
        f"5°S–5°N cosine-weighted mean; {BASELINE[0]}–{BASELINE[1]} "
        "same-calendar-month detrended anomalies. "
        "Continuous native SODA depth levels; longitude range 120°E–80°W."
    )
    fig.text(0.012, 0.014, note, fontsize=8.1, color="0.30")
    stem = (
        f"fig_{event}_jan_jun_soda3_ohc_vertical_section_"
        f"{BASELINE[0]}_{BASELINE[1]}_detrended"
    )
    return save_figure(fig, output_dir, stem)


def plot_combined(
    ds: xr.Dataset,
    events: list[int],
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(
        len(events),
        len(MONTHS),
        figsize=(21.0, 9.2),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    fig.subplots_adjust(
        left=0.060,
        right=0.995,
        top=0.89,
        bottom=0.17,
        wspace=0.12,
        hspace=0.15,
    )
    fig.suptitle(
        "January–June equatorial SODA3 upper-ocean heat-content structure: 1997, 2015, and 2023",
        fontsize=17,
        fontweight="bold",
        y=0.965,
    )
    mesh = None
    for row, event in enumerate(events):
        event_ds = ds.where(ds.time.dt.year == event, drop=True)
        for col, month_label in enumerate(MONTH_LABELS):
            ax = axes[row, col]
            mesh = draw_section(
                ax,
                event_ds.heat_content_density_anomaly.isel(time=col),
                norm=norm,
            )
            format_section_axis(
                ax,
                show_xlabel=row == len(events) - 1,
                show_ylabel=col == 0,
                compact_longitude=True,
            )
            if row == 0:
                ax.set_title(month_label, fontsize=11.0, fontweight="bold", pad=5)
            if col == 0:
                ax.set_ylabel(f"{event}\nDepth (m)", fontsize=9.5, fontweight="bold")
    assert mesh is not None
    cax = fig.add_axes((0.26, 0.085, 0.50, 0.024))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Heat-content density anomaly ρ₀CₚT′ (MJ m$^{-3}$)")
    note = (
        f"5°S–5°N cosine-weighted mean; {BASELINE[0]}–{BASELINE[1]} "
        "same-calendar-month detrended anomalies. "
        "Continuous native SODA depth levels; longitude range 120°E–80°W."
    )
    fig.text(0.012, 0.014, note, fontsize=8.1, color="0.30")
    stem = (
        "fig_1997_2015_2023_jan_jun_soda3_ohc_vertical_sections_"
        f"{BASELINE[0]}_{BASELINE[1]}_detrended"
    )
    return save_figure(fig, output_dir, stem)


def save_diagnostics(ds: xr.Dataset, nc_path: Path) -> None:
    nc_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(nc_path, engine="netcdf4")
    print(nc_path)


def main() -> None:
    args = parse_args()
    events = [int(value) for value in args.events]
    if len(set(events)) != len(events):
        raise ValueError("--events contains duplicates")
    if args.vlim <= 0:
        raise ValueError("--vlim must be positive")
    setup_style()
    with open_dataset(TEMP_FILE) as source:
        validate_input(source)
        equatorial = equatorial_mean_temperature(source).load()
    anomaly = detrended_same_month_anomaly(equatorial)
    diagnostics = build_diagnostics(anomaly, events)

    heat_density = diagnostics.heat_content_density_anomaly.values.astype(float)
    clipped = np.mean(np.abs(heat_density[np.isfinite(heat_density)]) > args.vlim)
    print(
        "Diagnostics: "
        f"finite={np.isfinite(heat_density).mean():.4f}, "
        f"range=[{np.nanmin(heat_density):.3f}, {np.nanmax(heat_density):.3f}] MJ m-3, "
        f"fraction beyond color limit={clipped:.4f}"
    )

    save_diagnostics(diagnostics, args.derived_nc)
    for event in events:
        plot_event(diagnostics, event, args.output_dir, args.vlim)
    plot_combined(diagnostics, events, args.output_dir, args.vlim)


if __name__ == "__main__":
    main()
