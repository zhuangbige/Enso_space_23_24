#!/usr/bin/env python3
"""Reproduce the development-stage logic of Peng et al. (2025) with SODA3.

The local SODA3.15.2 upper-ocean temperature subset contains January--June
only.  This script therefore makes two honest, complementary products:

1. a Peng-style seasonal comparison for JFM and AMJ; and
2. a January--June monthly sequence that resolves the early-2023 timing.

Shading is potential-temperature anomaly (not vertically integrated OHC).
The black curve is the 20 degC isotherm from the displayed absolute field and
the grey dashed curve is the 1982--2022 climatological 20 degC isotherm.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig_peng2025_profiles"),
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    str(ROOT / "outputs/research_2026/cache_peng2025_profiles"),
)

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D


TEMP_FILE = (
    ROOT
    / "data/raw/soda3"
    / "soda3.15.2_equatorial_temp_jan1980_jan2024_peng_profiles.nc"
)
OUT_DIR = ROOT / "outputs/research_2026/soda3_peng2025_profile_comparison"

BASELINE = (1982, 2022)
TARGET_YEAR = 2023
COMPOSITE_YEARS = (1982, 1997, 2015)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SEASONS = {
    "JFM": (1, 2, 3),
    "AMJ": (4, 5, 6),
    "JAS": (7, 8, 9),
    "OND": (10, 11, 12),
}
PENG_STAGES = {
    "JFM": (1, 2, 3),
    "Apr–Oct": (4, 5, 6, 7, 8, 9, 10),
    "NDJ": (11, 12, 1),
}
LAT_BOUNDS = (-2.0, 2.0)
LON_BOUNDS = (120.0, 280.0)
FEP_BOUNDS = (270.0, 280.0)  # 90W--80W
RHO0 = 1025.0
CP0 = 3990.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=TEMP_FILE)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--vlim",
        type=float,
        default=5.0,
        help="Symmetric temperature-anomaly colour limit in degC.",
    )
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.0,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.2,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "axes.linewidth": 0.8,
            "axes.unicode_minus": False,
        }
    )


def open_dataset(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(f"Missing SODA3 input: {path}")
    try:
        return xr.open_dataset(path, engine="netcdf4")
    except (OSError, ImportError, ValueError):
        return xr.open_dataset(path, engine="scipy")


def validate_input(ds: xr.Dataset) -> None:
    required = {"temp", "time", "depth", "lat", "lon"}
    missing = required.difference(set(ds.variables) | set(ds.coords))
    if missing:
        raise ValueError(f"Temperature input is missing {sorted(missing)}")
    if ds.temp.dims != ("time", "depth", "lat", "lon"):
        raise ValueError(f"Unexpected dimensions: {ds.temp.dims}")
    if ds.temp.attrs.get("units") != "degC":
        raise ValueError(f"Unexpected temperature units: {ds.temp.attrs.get('units')}")
    if not np.all(np.diff(ds.depth.values.astype(float)) > 0):
        raise ValueError("Depth must increase downward")
    if not np.all(np.diff(ds.lon.values.astype(float)) > 0):
        raise ValueError("Longitude must increase eastward")
    years = ds.time.dt.year.values.astype(int)
    months = ds.time.dt.month.values.astype(int)
    if years.min() > BASELINE[0] or years.max() < TARGET_YEAR:
        raise ValueError(f"Insufficient time coverage: {years.min()}--{years.max()}")
    if set(np.unique(months)) != set(range(1, 13)):
        raise ValueError(f"Expected all calendar months, got {np.unique(months)}")
    for year in (*COMPOSITE_YEARS, TARGET_YEAR):
        if np.sum(years == year) != 12:
            raise ValueError(f"Expected twelve months for {year}")
    if np.sum(years == TARGET_YEAR + 1) < 1:
        raise ValueError("January 2024 is required for the 2023/24 NDJ stage")


def equatorial_mean_temperature(ds: xr.Dataset) -> xr.DataArray:
    selected = ds.temp.sel(
        lat=slice(LAT_BOUNDS[0], LAT_BOUNDS[1]),
        lon=slice(LON_BOUNDS[0], LON_BOUNDS[1]),
    )
    # A fixed full-depth/full-time ocean mask keeps each longitude's sampling
    # identical for anomalies, D20 and depth-integrated diagnostics.
    valid_column = selected.notnull().all(("time", "depth"))
    weights = np.cos(np.deg2rad(selected.lat)).broadcast_like(valid_column)
    weights = weights.where(valid_column, 0.0)
    result = selected.weighted(weights).mean("lat", skipna=True).load()
    result.name = "temperature"
    result.attrs.update(
        units="degC",
        long_name="2S--2N cosine-weighted SODA3 potential temperature",
    )
    return result


def build_monthly_climatology(temperature: xr.DataArray) -> xr.DataArray:
    years = temperature.time.dt.year
    baseline = temperature.where(
        (years >= BASELINE[0]) & (years <= BASELINE[1]), drop=True
    )
    expected = (BASELINE[1] - BASELINE[0] + 1) * 12
    if baseline.sizes["time"] != expected:
        raise ValueError(
            f"Baseline contains {baseline.sizes['time']} months; expected {expected}"
        )
    climatology = baseline.groupby("time.month").mean("time", skipna=True)
    climatology.name = "temperature_climatology"
    climatology.attrs.update(
        units="degC",
        baseline=f"{BASELINE[0]}-{BASELINE[1]}",
    )
    return climatology


def monthly_anomaly(
    temperature: xr.DataArray, climatology: xr.DataArray
) -> xr.DataArray:
    anomaly = temperature.groupby("time.month") - climatology
    anomaly.name = "temperature_anomaly"
    anomaly.attrs.update(
        units="degC",
        anomaly_definition=(
            f"Same-calendar-month anomaly from {BASELINE[0]}-{BASELINE[1]} climatology; "
            "not detrended"
        ),
    )
    return anomaly


def select_year_months(
    da: xr.DataArray, years: tuple[int, ...], months: tuple[int, ...]
) -> xr.DataArray:
    mask = da.time.dt.year.isin(years) & da.time.dt.month.isin(months)
    return da.where(mask, drop=True)


def event_mean(
    da: xr.DataArray, years: tuple[int, ...], months: tuple[int, ...]
) -> xr.DataArray:
    selected = select_year_months(da, years, months)
    expected = len(years) * len(months)
    if selected.sizes.get("time", 0) != expected:
        raise ValueError(
            f"Expected {expected} samples for years={years}, months={months}; "
            f"got {selected.sizes.get('time', 0)}"
        )
    return selected.mean("time", skipna=True)


def climatological_mean(
    climatology: xr.DataArray, months: tuple[int, ...]
) -> xr.DataArray:
    return climatology.sel(month=list(months)).mean("month", skipna=True)


def stage_mean(
    da: xr.DataArray,
    event_years: tuple[int, ...],
    stage: str,
) -> xr.DataArray:
    """Average a Peng stage, giving each event the same weight."""
    if stage not in PENG_STAGES:
        raise KeyError(f"Unknown stage: {stage}")
    months = PENG_STAGES[stage]
    event_fields: list[xr.DataArray] = []
    for event_year in event_years:
        if stage == "NDJ":
            mask = (
                ((da.time.dt.year == event_year) & da.time.dt.month.isin((11, 12)))
                | ((da.time.dt.year == event_year + 1) & (da.time.dt.month == 1))
            )
        else:
            mask = (da.time.dt.year == event_year) & da.time.dt.month.isin(months)
        selected = da.where(mask, drop=True)
        if selected.sizes.get("time", 0) != len(months):
            raise ValueError(
                f"Expected {len(months)} months for {event_year} {stage}; "
                f"got {selected.sizes.get('time', 0)}"
            )
        event_fields.append(selected.mean("time", skipna=True))
    return xr.concat(event_fields, dim="event").mean("event", skipna=True)


def depth_cell_thickness(depth: xr.DataArray, bottom: float = 300.0) -> xr.DataArray:
    z = depth.values.astype(float)
    if z[0] <= 0 or z[-1] >= bottom:
        raise ValueError(f"Unexpected upper-ocean depth coordinates: {z[[0, -1]]}")
    edges = np.empty(z.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (z[:-1] + z[1:])
    edges[-1] = bottom
    dz = np.diff(edges)
    if not np.isclose(dz.sum(), bottom):
        raise AssertionError("Depth weights do not sum to 300 m")
    return xr.DataArray(dz, dims=("depth",), coords={"depth": depth}, name="dz")


def fep_monthly_diagnostics(anomaly: xr.DataArray) -> pd.DataFrame:
    target = select_year_months(anomaly, (TARGET_YEAR,), MONTHS)
    fep = target.sel(lon=slice(FEP_BOUNDS[0], FEP_BOUNDS[1]))
    top = fep.isel(depth=0).mean("lon", skipna=True)
    dz = depth_cell_thickness(fep.depth)
    ohc = (fep * dz).sum("depth", skipna=True).mean("lon", skipna=True)
    ohc = ohc * RHO0 * CP0 / 1.0e9
    return pd.DataFrame(
        {
            "month": target.time.dt.month.values.astype(int),
            "fep_5m_temperature_anomaly_degC": top.values.astype(float),
            "fep_0_300m_ohc_anomaly_GJ_m2": ohc.values.astype(float),
        }
    )


def format_lon(value: float) -> str:
    longitude = value % 360.0
    if np.isclose(longitude, 180.0):
        return "180°"
    if longitude < 180.0:
        return f"{longitude:g}°E"
    return f"{360.0 - longitude:g}°W"


def format_axis(
    ax: plt.Axes,
    *,
    show_xlabel: bool,
    show_ylabel: bool,
) -> None:
    xticks = (120, 160, 180, 220, 240, 280)
    ax.set_xlim(*LON_BOUNDS)
    ax.set_ylim(300, 0)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(value) for value in xticks])
    ax.set_yticks((0, 50, 100, 150, 200, 250, 300))
    ax.tick_params(direction="out", length=2.7, width=0.7)
    if show_xlabel:
        ax.set_xlabel("Longitude")
    else:
        ax.tick_params(labelbottom=False)
    if show_ylabel:
        ax.set_ylabel("Depth (m)")
    else:
        ax.tick_params(labelleft=False)


def draw_section(
    ax: plt.Axes,
    anomaly: xr.DataArray,
    *,
    norm: TwoSlopeNorm,
    absolute_temperature: xr.DataArray | None,
    climatological_temperature: xr.DataArray | None,
) -> plt.collections.QuadMesh:
    mesh = ax.pcolormesh(
        anomaly.lon,
        anomaly.depth,
        anomaly,
        cmap="RdBu_r",
        norm=norm,
        shading="auto",
        rasterized=True,
        zorder=1,
    )
    ax.axvspan(
        FEP_BOUNDS[0],
        FEP_BOUNDS[1],
        facecolor="none",
        edgecolor="0.25",
        linewidth=0.65,
        linestyle=(0, (2, 2)),
        zorder=4,
    )
    if absolute_temperature is not None and climatological_temperature is not None:
        ax.contour(
            climatological_temperature.lon,
            climatological_temperature.depth,
            climatological_temperature,
            levels=[20.0],
            colors=["0.60"],
            linewidths=1.05,
            linestyles="--",
            zorder=5,
        )
        ax.contour(
            absolute_temperature.lon,
            absolute_temperature.depth,
            absolute_temperature,
            levels=[20.0],
            colors=["k"],
            linewidths=1.25,
            zorder=6,
        )
    return mesh


def add_isotherm_legend(
    fig: plt.Figure,
    *,
    x: float,
    y: float,
    location: str = "upper center",
    columns: int = 2,
) -> None:
    handles = (
        Line2D([0], [0], color="k", linewidth=1.25, label="Actual 20°C isotherm"),
        Line2D(
            [0],
            [0],
            color="0.60",
            linewidth=1.05,
            linestyle="--",
            label="1982–2022 climatological 20°C isotherm",
        ),
    )
    fig.legend(
        handles=handles,
        loc=location,
        bbox_to_anchor=(x, y),
        ncol=columns,
        frameon=False,
        fontsize=8.0,
        handlelength=2.4,
        columnspacing=1.8,
    )


def panel_letter(ax: plt.Axes, letter: str) -> None:
    ax.text(
        0.012,
        0.965,
        letter,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.5,
        fontweight="bold",
        color="k",
        zorder=10,
    )


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(png)
    print(pdf)
    return png, pdf


def plot_seasonal(
    temperature: xr.DataArray,
    anomaly: xr.DataArray,
    climatology: xr.DataArray,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(
        len(SEASONS), 3, figsize=(12.8, 10.4), sharex=True, sharey=True
    )
    fig.subplots_adjust(
        left=0.075,
        right=0.985,
        top=0.88,
        bottom=0.14,
        wspace=0.07,
        hspace=0.13,
    )
    fig.suptitle(
        "SODA3 equatorial Pacific temperature evolution: 2023 versus strong-event composite",
        fontsize=14.2,
        fontweight="bold",
        y=0.965,
    )
    column_titles = (
        "2023",
        "1982/1997/2015 composite",
        "2023 minus composite",
    )
    for col, title in enumerate(column_titles):
        axes[0, col].set_title(title, fontsize=10.8, fontweight="bold", pad=6)

    mesh = None
    letter_index = 0
    for row, (season, months) in enumerate(SEASONS.items()):
        target_anom = event_mean(anomaly, (TARGET_YEAR,), months)
        comp_anom = event_mean(anomaly, COMPOSITE_YEARS, months)
        target_abs = event_mean(temperature, (TARGET_YEAR,), months)
        comp_abs = event_mean(temperature, COMPOSITE_YEARS, months)
        clim_abs = climatological_mean(climatology, months)
        fields = (target_anom, comp_anom, target_anom - comp_anom)
        absolutes = (target_abs, comp_abs, None)
        clim_fields = (clim_abs, clim_abs, None)
        for col in range(3):
            ax = axes[row, col]
            mesh = draw_section(
                ax,
                fields[col],
                norm=norm,
                absolute_temperature=absolutes[col],
                climatological_temperature=clim_fields[col],
            )
            format_axis(
                ax,
                show_xlabel=row == len(SEASONS) - 1,
                show_ylabel=col == 0,
            )
            panel_letter(ax, chr(ord("a") + letter_index))
            letter_index += 1
            if col == 0:
                ax.text(
                    -0.14,
                    0.50,
                    season,
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    rotation=90,
                    fontsize=11.0,
                    fontweight="bold",
                )
    assert mesh is not None
    add_isotherm_legend(fig, x=0.5, y=0.930)
    cax = fig.add_axes((0.27, 0.067, 0.48, 0.018))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Potential-temperature anomaly (°C)")
    note = (
        "2°S–2°N cosine-weighted SODA3.15.2; anomalies from the 1982–2022 "
        "calendar-month climatology (no detrending). Black: actual 20°C isotherm; "
        "grey dashed: climatological 20°C isotherm; outlined strip: FEP (90°W–80°W)."
    )
    fig.text(0.012, 0.015, note, fontsize=7.6, color="0.28")
    stem = "fig_soda3_peng2025_jfm_amj_jas_ond_2023_vs_1982_1997_2015_profiles"
    return save_figure(fig, output_dir, stem)


def plot_monthly(
    temperature: xr.DataArray,
    anomaly: xr.DataArray,
    climatology: xr.DataArray,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(3, 6, figsize=(19.2, 8.0), sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.061,
        right=0.995,
        top=0.87,
        bottom=0.18,
        wspace=0.055,
        hspace=0.11,
    )
    fig.suptitle(
        "Monthly SODA3 equatorial Pacific temperature evolution during early 2023",
        fontsize=15.2,
        fontweight="bold",
        y=0.965,
    )
    row_labels = ("2023", "1982/1997/2015\ncomposite", "2023 − composite")
    mesh = None
    for col, (month, label) in enumerate(zip(MONTHS, MONTH_LABELS)):
        axes[0, col].set_title(label, fontsize=10.8, fontweight="bold", pad=5)
        target_anom = event_mean(anomaly, (TARGET_YEAR,), (month,))
        comp_anom = event_mean(anomaly, COMPOSITE_YEARS, (month,))
        target_abs = event_mean(temperature, (TARGET_YEAR,), (month,))
        comp_abs = event_mean(temperature, COMPOSITE_YEARS, (month,))
        clim_abs = climatological_mean(climatology, (month,))
        fields = (target_anom, comp_anom, target_anom - comp_anom)
        absolutes = (target_abs, comp_abs, None)
        clim_fields = (clim_abs, clim_abs, None)
        for row in range(3):
            ax = axes[row, col]
            mesh = draw_section(
                ax,
                fields[row],
                norm=norm,
                absolute_temperature=absolutes[row],
                climatological_temperature=clim_fields[row],
            )
            format_axis(
                ax,
                show_xlabel=row == 2,
                show_ylabel=col == 0,
            )
            panel_letter(ax, chr(ord("a") + row * len(MONTHS) + col))
            if col == 0:
                ax.text(
                    -0.24,
                    0.50,
                    row_labels[row],
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    rotation=90,
                    fontsize=9.0,
                    fontweight="bold",
                )
    assert mesh is not None
    cax = fig.add_axes((0.30, 0.083, 0.42, 0.025))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Potential-temperature anomaly (°C)")
    note = (
        "2°S–2°N cosine-weighted SODA3.15.2; anomalies from the 1982–2022 "
        "calendar-month climatology (no detrending). Black: actual 20°C isotherm; "
        "grey dashed: climatological 20°C isotherm; outlined strip: FEP (90°W–80°W)."
    )
    fig.text(0.010, 0.015, note, fontsize=7.5, color="0.28")
    stem = "fig_soda3_peng2025_jan_jun_2023_monthly_profile_evolution"
    return save_figure(fig, output_dir, stem)


def plot_peng_three_stage(
    temperature: xr.DataArray,
    anomaly: xr.DataArray,
    climatology: xr.DataArray,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    """Plot the JFM, April--October and NDJ sequence used in Peng Fig. 2."""
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(3, 3, figsize=(12.8, 8.7), sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.078,
        right=0.985,
        top=0.86,
        bottom=0.15,
        wspace=0.07,
        hspace=0.12,
    )
    fig.suptitle(
        "Peng et al. (2025)-style SODA3 equatorial Pacific temperature sequence",
        fontsize=14.2,
        fontweight="bold",
        y=0.965,
    )
    column_titles = (
        "2023/24",
        "1982/83, 1997/98, 2015/16 composite",
        "2023/24 minus composite",
    )
    for col, title in enumerate(column_titles):
        axes[0, col].set_title(title, fontsize=10.2, fontweight="bold", pad=6)

    mesh = None
    letter_index = 0
    for row, (stage, months) in enumerate(PENG_STAGES.items()):
        target_anom = stage_mean(anomaly, (TARGET_YEAR,), stage)
        comp_anom = stage_mean(anomaly, COMPOSITE_YEARS, stage)
        target_abs = stage_mean(temperature, (TARGET_YEAR,), stage)
        comp_abs = stage_mean(temperature, COMPOSITE_YEARS, stage)
        clim_abs = climatological_mean(climatology, months)
        fields = (target_anom, comp_anom, target_anom - comp_anom)
        absolutes = (target_abs, comp_abs, None)
        clim_fields = (clim_abs, clim_abs, None)
        for col in range(3):
            ax = axes[row, col]
            mesh = draw_section(
                ax,
                fields[col],
                norm=norm,
                absolute_temperature=absolutes[col],
                climatological_temperature=clim_fields[col],
            )
            format_axis(
                ax,
                show_xlabel=row == len(PENG_STAGES) - 1,
                show_ylabel=col == 0,
            )
            panel_letter(ax, chr(ord("a") + letter_index))
            letter_index += 1
            if col == 0:
                ax.text(
                    -0.145,
                    0.50,
                    stage,
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    rotation=90,
                    fontsize=10.2,
                    fontweight="bold",
                )
    assert mesh is not None
    add_isotherm_legend(fig, x=0.5, y=0.925)
    cax = fig.add_axes((0.27, 0.075, 0.48, 0.020))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Potential-temperature anomaly (°C)")
    note = (
        "2°S–2°N cosine-weighted SODA3.15.2; anomalies from the 1982–2022 "
        "calendar-month climatology (no detrending). Black: actual 20°C isotherm; "
        "grey dashed: climatological 20°C isotherm; outlined strip: FEP (90°W–80°W)."
    )
    fig.text(0.012, 0.016, note, fontsize=7.5, color="0.28")
    stem = "fig_soda3_peng2025_jfm_aproct_ndj_2023_vs_strong_event_composite"
    return save_figure(fig, output_dir, stem)


def main() -> None:
    args = parse_args()
    if args.vlim <= 0:
        raise ValueError("--vlim must be positive")
    setup_style()
    with open_dataset(args.input) as source:
        validate_input(source)
        temperature = equatorial_mean_temperature(source)
    climatology = build_monthly_climatology(temperature)
    anomaly = monthly_anomaly(temperature, climatology)

    finite = anomaly.sel(
        time=anomaly.time.dt.year.isin((*COMPOSITE_YEARS, TARGET_YEAR))
    ).values
    finite = finite[np.isfinite(finite)]
    print(
        "Temperature-anomaly diagnostics: "
        f"range=[{finite.min():.3f}, {finite.max():.3f}] degC, "
        f"p01={np.percentile(finite, 1):.3f}, p99={np.percentile(finite, 99):.3f}, "
        f"fraction beyond +/-{args.vlim:g} degC={np.mean(np.abs(finite) > args.vlim):.4f}"
    )
    print("2023 FEP diagnostics (2S--2N, 90W--80W):")
    print(fep_monthly_diagnostics(anomaly).to_string(index=False, float_format="%.3f"))

    plot_peng_three_stage(temperature, anomaly, climatology, args.output_dir, args.vlim)
    plot_seasonal(temperature, anomaly, climatology, args.output_dir, args.vlim)
    plot_monthly(temperature, anomaly, climatology, args.output_dir, args.vlim)


if __name__ == "__main__":
    main()
