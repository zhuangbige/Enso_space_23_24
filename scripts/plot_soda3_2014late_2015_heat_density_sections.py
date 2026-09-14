#!/usr/bin/env python3
"""Plot late-2014 to June-2015 SODA3 heat-content-density sections."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/soda3_2014late_2015_heat_density_sections"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache"))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


INPUT = (
    ROOT
    / "data/raw/soda3"
    / "soda3.15.2_equatorial_temp_jan1980_jan2024_peng_profiles.nc"
)
DERIVED = (
    ROOT
    / "data/derived/research_2026"
    / "soda3_2014oct_2015jun_heat_content_density_anomaly_1980_2023_detrended.nc"
)
BASELINE = (1980, 2023)
START = "2014-10-01"
END = "2015-06-30"
RHO0 = 1025.0
CP0 = 3990.0
VLIM = 16.0


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.2,
            "axes.titlesize": 11.0,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def inspect_input(ds: xr.Dataset) -> None:
    required = {"temp", "time", "depth", "lat", "lon"}
    missing = required.difference(set(ds.data_vars) | set(ds.coords))
    if missing:
        raise ValueError(f"Input is missing {sorted(missing)}")
    if ds.temp.dims != ("time", "depth", "lat", "lon"):
        raise ValueError(f"Unexpected dimensions: {ds.temp.dims}")
    if ds.temp.attrs.get("units") != "degC":
        raise ValueError(f"Unexpected units: {ds.temp.attrs.get('units')}")
    years = ds.time.dt.year.values.astype(int)
    months = ds.time.dt.month.values.astype(int)
    complete = (years >= BASELINE[0]) & (years <= BASELINE[1])
    for month in range(1, 13):
        count = int(np.sum(complete & (months == month)))
        if count != BASELINE[1] - BASELINE[0] + 1:
            raise ValueError(f"Month {month} has {count} baseline samples")
    target = ds.temp.sel(time=slice(START, END))
    if target.sizes.get("time", 0) != 9:
        raise ValueError(f"Expected nine target months, got {target.sizes.get('time', 0)}")


def equatorial_mean(ds: xr.Dataset) -> xr.DataArray:
    selected = ds.temp
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


def detrended_same_month_anomaly(temperature: xr.DataArray) -> xr.DataArray:
    values = temperature.values.astype(np.float64)
    times = pd.DatetimeIndex(temperature.time.values)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    baseline_mask = (years >= BASELINE[0]) & (years <= BASELINE[1])
    output = np.full(values.shape, np.nan, dtype=np.float32)
    for month in range(1, 13):
        target_index = np.where(months == month)[0]
        baseline_index = np.where((months == month) & baseline_mask)[0]
        if baseline_index.size != BASELINE[1] - BASELINE[0] + 1:
            raise ValueError(f"Unexpected baseline count for month {month}")
        baseline_years = years[baseline_index]
        center = float(baseline_years.mean())
        x = baseline_years - center
        baseline_values = values[baseline_index]
        finite = np.isfinite(baseline_values)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(baseline_values, axis=0),
            count,
            out=np.full(baseline_values.shape[1:], np.nan),
            where=count > 0,
        )
        denominator = np.nansum(finite * x[:, None, None] ** 2, axis=0)
        slope = np.divide(
            np.nansum(x[:, None, None] * (baseline_values - mean), axis=0),
            denominator,
            out=np.full(mean.shape, np.nan),
            where=denominator > 0,
        )
        target_years = years[target_index]
        output[target_index] = (
            values[target_index]
            - mean[None, :, :]
            - slope[None, :, :] * (target_years[:, None, None] - center)
        ).astype(np.float32)
    result = xr.DataArray(
        output,
        dims=temperature.dims,
        coords=temperature.coords,
        name="temperature_anomaly",
        attrs={
            "units": "degC",
            "baseline": f"{BASELINE[0]}-{BASELINE[1]}",
            "definition": "same-calendar-month climatology and linear trend removed",
        },
    )
    return result


def build_target(temperature: xr.DataArray) -> xr.Dataset:
    anomaly = detrended_same_month_anomaly(temperature)
    selected_temperature = temperature.sel(time=slice(START, END))
    selected_anomaly = anomaly.sel(time=slice(START, END))
    heat_density = selected_anomaly * RHO0 * CP0 / 1.0e6
    heat_density.name = "heat_content_density_anomaly"
    heat_density.attrs.update(
        units="MJ m-3",
        long_name="Volumetric heat-content anomaly rho0*cp0*T_prime",
    )
    return xr.Dataset(
        {
            "temperature": selected_temperature.astype(np.float32),
            "temperature_anomaly": selected_anomaly.astype(np.float32),
            "heat_content_density_anomaly": heat_density.astype(np.float32),
        },
        attrs={
            "title": "Late-2014 to June-2015 SODA3 equatorial thermal-anomaly sections",
            "source": str(INPUT),
            "latitude_average": "2S to 2N cosine weighted",
            "anomaly_definition": (
                f"{BASELINE[0]}-{BASELINE[1]} same-calendar-month climatology "
                "and linear trend removed"
            ),
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
        },
    )


def format_lon(value: float) -> str:
    longitude = value % 360.0
    if np.isclose(longitude, 180.0):
        return "180°"
    return f"{longitude:g}°E" if longitude < 180.0 else f"{360.0 - longitude:g}°W"


def format_axis(ax: plt.Axes, *, show_xlabel: bool, show_ylabel: bool) -> None:
    ticks = (120, 160, 180, 220, 240, 280)
    ax.set_xlim(120, 280)
    ax.set_ylim(300, 0)
    ax.set_xticks(ticks)
    ax.set_xticklabels([format_lon(value) for value in ticks])
    ax.set_yticks((0, 50, 100, 150, 200, 250, 300))
    if show_xlabel:
        ax.set_xlabel("Longitude")
    else:
        ax.tick_params(labelbottom=False)
    if show_ylabel:
        ax.set_ylabel("Depth (m)")
    else:
        ax.tick_params(labelleft=False)


def save_figure(fig: plt.Figure, stem: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print(png)
    print(pdf)
    return png, pdf


def plot_sequence(
    dataset: xr.Dataset,
    *,
    indices: tuple[int, ...],
    rows: int,
    columns: int,
    title: str,
    stem: str,
    figsize: tuple[float, float],
) -> tuple[Path, Path]:
    if rows * columns != len(indices):
        raise ValueError("Panel geometry does not match selected months")
    norm = TwoSlopeNorm(vmin=-VLIM, vcenter=0.0, vmax=VLIM)
    fig, axes = plt.subplots(rows, columns, figsize=figsize, sharex=True, sharey=True)
    axes_array = np.asarray(axes).reshape(rows, columns)
    bottom = 0.18 if rows == 1 else 0.14
    fig.subplots_adjust(
        left=0.060,
        right=0.995,
        top=0.86,
        bottom=bottom,
        wspace=0.07,
        hspace=0.16,
    )
    fig.suptitle(title, fontsize=15.0, fontweight="bold", y=0.965)
    mesh = None
    for panel, index in enumerate(indices):
        row, column = divmod(panel, columns)
        ax = axes_array[row, column]
        field = dataset.heat_content_density_anomaly.isel(time=index)
        mesh = ax.pcolormesh(
            field.lon,
            field.depth,
            field,
            cmap="RdBu_r",
            norm=norm,
            shading="auto",
            rasterized=True,
        )
        time = pd.Timestamp(dataset.time.values[index])
        ax.set_title(time.strftime("%b %Y"), fontsize=11.0, fontweight="bold", pad=5)
        format_axis(
            ax,
            show_xlabel=row == rows - 1,
            show_ylabel=column == 0,
        )
        ax.text(
            0.012,
            0.965,
            chr(ord("a") + panel),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9.4,
            fontweight="bold",
        )
    assert mesh is not None
    colorbar_y = 0.065 if rows > 1 else 0.070
    cax = fig.add_axes((0.27, colorbar_y, 0.48, 0.025))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Heat-content density anomaly ρ₀CₚT′ (MJ m$^{-3}$)")
    note = (
        "2°S–2°N cosine-weighted SODA3.15.2; 1980–2023 same-calendar-month "
        "detrended anomalies; native depth levels; 120°E–80°W; fixed ±16 MJ m⁻³ scale."
    )
    fig.text(0.012, 0.015, note, fontsize=7.9, color="0.30")
    return save_figure(fig, stem)


def main() -> None:
    setup_style()
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)
    with xr.open_dataset(INPUT, engine="h5netcdf") as source:
        inspect_input(source)
        temperature = equatorial_mean(source)
    target = build_target(temperature)
    if target.sizes.get("time", 0) != 9:
        raise AssertionError("Target dataset does not contain nine months")

    values = target.heat_content_density_anomaly.values.astype(float)
    finite = values[np.isfinite(values)]
    print(
        "Heat-density diagnostics: "
        f"range=[{finite.min():.3f}, {finite.max():.3f}] MJ m-3, "
        f"fraction beyond +/-{VLIM:g}={np.mean(np.abs(finite) > VLIM):.4f}"
    )
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    target.to_netcdf(DERIVED, engine="h5netcdf")
    print(DERIVED)

    plot_sequence(
        target,
        indices=tuple(range(9)),
        rows=3,
        columns=3,
        title="October 2014–June 2015 equatorial SODA3 heat-content-density anomaly",
        stem="fig_soda3_2014oct_2015jun_heat_density_anomaly_sequence",
        figsize=(14.5, 11.4),
    )
    plot_sequence(
        target,
        indices=(0, 1, 2),
        rows=1,
        columns=3,
        title="Late-2014 preconditioning: SODA3 heat-content-density anomaly",
        stem="fig_soda3_2014ond_heat_density_anomaly_sections",
        figsize=(14.5, 4.8),
    )
    plot_sequence(
        target,
        indices=(3, 4, 5),
        rows=1,
        columns=3,
        title="Early-2015 evolution: SODA3 heat-content-density anomaly",
        stem="fig_soda3_2015jfm_heat_density_anomaly_sections",
        figsize=(14.5, 4.8),
    )
    plot_sequence(
        target,
        indices=(6, 7, 8),
        rows=1,
        columns=3,
        title="Spring-2015 evolution: SODA3 heat-content-density anomaly",
        stem="fig_soda3_2015amj_heat_density_anomaly_sections",
        figsize=(14.5, 4.8),
    )


if __name__ == "__main__":
    main()
