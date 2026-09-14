#!/usr/bin/env python3
"""Compare strong/moderate El Nino vertical temperature structures with 2026.

Historical composites use the local SODA3.15.2 January--June temperature
subset.  The real-time 2026 column uses NOAA/NCEP GODAS because the local SODA
archive ends in 2024.  Anomalies are computed within each product before the
fields are put on a common longitude/depth grid.

Outputs include JFM/AMJ and monthly four-column figures, a common-grid NetCDF,
event-level vertical metrics, and class-pattern similarity diagnostics.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/enso_strength_vertical_profiles_2026"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache"))

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle


SODA_FILE = (
    ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
GODAS_2026_FILE = (
    ROOT / "data/raw/godas/godas_pottmp_equatorial_2026_jan_jun.nc"
)
GODAS_CLIM_FILE = (
    ROOT / "data/raw/godas/godas_pottmp_climatology_equatorial_1991_2020.nc"
)

# Classification is based on the peak during the first development winter.
# The long 1986--88 event is therefore treated as moderate in its first winter;
# this choice must be included in the sensitivity analysis of a manuscript.
STRONG_YEARS = (1982, 1991, 1997, 2009, 2015, 2023)
MODERATE_YEARS = (1986, 1994, 2002)
GODAS_VALIDATION_YEARS = (1997, 2015, 2023, 2002)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SEASONS = {"JFM": (1, 2, 3), "AMJ": (4, 5, 6)}
SODA_BASELINE = (1980, 2024)
GODAS_BASELINE = (1991, 2020)
LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (121.0, 279.0)
WEST_CENTRAL_END = 210.0  # 150W
WEST_END = 160.0
MAX_DEPTH = 300.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--vlim",
        type=float,
        default=None,
        help="Symmetric anomaly color limit in degC; robust automatic if omitted.",
    )
    return parser.parse_args()


def open_dataset(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(path)
    for engine in ("h5netcdf", "netcdf4", "scipy"):
        try:
            return xr.open_dataset(path, engine=engine)
        except (ImportError, OSError, ValueError):
            continue
    raise OSError(f"Could not open {path} with an available xarray backend")


def validate_soda(ds: xr.Dataset) -> None:
    required = {"temp", "time", "depth", "lat", "lon"}
    missing = required.difference(set(ds.variables) | set(ds.coords))
    if missing:
        raise ValueError(f"SODA input is missing {sorted(missing)}")
    if ds.temp.dims != ("time", "depth", "lat", "lon"):
        raise ValueError(f"Unexpected SODA dimensions: {ds.temp.dims}")
    if ds.temp.attrs.get("units") != "degC":
        raise ValueError(f"Unexpected SODA units: {ds.temp.attrs.get('units')}")
    if not np.all(np.diff(ds.depth.values.astype(float)) > 0):
        raise ValueError("SODA depth must increase downward")
    if not np.all(np.diff(ds.lon.values.astype(float)) > 0):
        raise ValueError("SODA longitude must increase eastward")
    times = pd.DatetimeIndex(ds.time.values)
    if (times.year.min(), times.year.max()) != SODA_BASELINE:
        raise ValueError(
            f"Expected SODA {SODA_BASELINE}, got {times.year.min()}-{times.year.max()}"
        )
    if set(np.unique(times.month)) != set(MONTHS):
        raise ValueError("SODA subset must contain January--June only")


def validate_godas(obs: xr.Dataset, clim: xr.Dataset) -> None:
    for name, ds in (("2026", obs), ("climatology", clim)):
        required = {"pottmp", "time", "level", "lat", "lon"}
        missing = required.difference(set(ds.variables) | set(ds.coords))
        if missing:
            raise ValueError(f"GODAS {name} input is missing {sorted(missing)}")
        if ds.pottmp.attrs.get("units") != "K":
            raise ValueError(f"Unexpected GODAS {name} units")
        if not np.all(np.diff(ds.level.values.astype(float)) > 0):
            raise ValueError("GODAS depth must increase downward")
    if obs.sizes["time"] != 6:
        raise ValueError(f"Expected six 2026 GODAS months, got {obs.sizes['time']}")
    if clim.sizes["time"] != 12:
        raise ValueError("Expected twelve GODAS climatology months")


def fixed_mask_latitude_mean(
    da: xr.DataArray,
    *,
    vertical_dim: str,
    companion: xr.DataArray | None = None,
) -> xr.DataArray:
    selected = da.sel(lat=slice(*LAT_BOUNDS), lon=slice(120.0, 280.0))
    valid = selected.notnull().all(("time", vertical_dim))
    if companion is not None:
        other = companion.sel(lat=slice(*LAT_BOUNDS), lon=slice(120.0, 280.0))
        valid = valid & other.notnull().all(("time", vertical_dim))
    weights = np.cos(np.deg2rad(selected.lat)).broadcast_like(valid)
    weights = weights.where(valid, 0.0)
    result = selected.weighted(weights).mean("lat", skipna=True).load()
    return result


def soda_detrended_anomaly(temperature: xr.DataArray) -> xr.DataArray:
    """Remove each calendar month's 1980--2024 mean and linear trend."""
    values = temperature.values.astype(np.float64)
    times = pd.DatetimeIndex(temperature.time.values)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    output = np.full(values.shape, np.nan, dtype=np.float32)
    expected = SODA_BASELINE[1] - SODA_BASELINE[0] + 1
    for month in MONTHS:
        index = np.where(months == month)[0]
        if index.size != expected:
            raise ValueError(f"Month {month} has {index.size}, expected {expected}")
        x = years[index]
        xc = x - x.mean()
        field = values[index]
        finite = np.isfinite(field)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(field, axis=0),
            count,
            out=np.full(field.shape[1:], np.nan),
            where=count > 0,
        )
        denominator = np.nansum(finite * xc[:, None, None] ** 2, axis=0)
        slope = np.divide(
            np.nansum(xc[:, None, None] * (field - mean), axis=0),
            denominator,
            out=np.full(field.shape[1:], np.nan),
            where=denominator > 0,
        )
        output[index] = (
            field - mean[None, :, :] - slope[None, :, :] * xc[:, None, None]
        ).astype(np.float32)
    result = xr.DataArray(
        output,
        dims=temperature.dims,
        coords=temperature.coords,
        name="temperature_anomaly",
        attrs={
            "units": "degC",
            "baseline": f"{SODA_BASELINE[0]}-{SODA_BASELINE[1]}",
            "processing": "same-calendar-month mean and linear trend removed",
        },
    )
    return result


def godas_2026_anomaly(obs: xr.Dataset, clim: xr.Dataset) -> xr.DataArray:
    obs_temp = obs.pottmp.sel(level=slice(0.0, MAX_DEPTH))
    clim_temp = clim.pottmp.sel(level=slice(0.0, MAX_DEPTH))
    obs_mean = fixed_mask_latitude_mean(
        obs_temp, vertical_dim="level", companion=clim_temp
    )
    clim_mean = fixed_mask_latitude_mean(
        clim_temp, vertical_dim="level", companion=obs_temp
    )
    fields = []
    for index, month in enumerate(MONTHS):
        field = obs_mean.isel(time=index, drop=True) - clim_mean.isel(
            time=month - 1, drop=True
        )
        fields.append(field)
    result = xr.concat(fields, dim=obs_mean.time)
    result.name = "temperature_anomaly"
    result.attrs.update(
        units="degC",
        baseline=f"GODAS {GODAS_BASELINE[0]}-{GODAS_BASELINE[1]} monthly climatology",
        processing="2026 monthly GODAS potential temperature minus GODAS climatology",
    )
    return result


def godas_validation_path(year: int) -> Path:
    return ROOT / "data/raw/godas/validation" / f"godas_pottmp_equatorial_{year}_jan_jun.nc"


def common_grid(da: xr.DataArray, vertical_dim: str) -> xr.DataArray:
    target_lon = np.arange(LON_BOUNDS[0], LON_BOUNDS[1] + 0.1, 1.0)
    if vertical_dim == "depth":
        target_depth = da.depth.where(da.depth < MAX_DEPTH, drop=True).values
        result = da.sel(depth=slice(0.0, MAX_DEPTH)).interp(lon=target_lon)
    else:
        soda_depth = open_dataset(SODA_FILE).depth
        target_depth = soda_depth.where(soda_depth < MAX_DEPTH, drop=True).values
        result = da.interp(level=target_depth, lon=target_lon).rename(level="depth")
    result = result.assign_coords(depth=target_depth, lon=target_lon)
    return result


def select_year(da: xr.DataArray, year: int) -> xr.DataArray:
    selected = da.where(da.time.dt.year == year, drop=True)
    if selected.sizes.get("time", 0) != 6:
        raise ValueError(f"Expected six months for {year}")
    return selected


def class_monthly(da: xr.DataArray, years: tuple[int, ...]) -> xr.DataArray:
    events = [select_year(da, year).assign_coords(time=list(MONTHS)) for year in years]
    result = xr.concat(events, dim="event").mean("event", skipna=True)
    return result.rename(time="month")


def seasonal_from_monthly(da: xr.DataArray) -> xr.DataArray:
    fields = []
    for season, months in SEASONS.items():
        field = da.sel(month=list(months)).mean("month", skipna=True)
        fields.append(field.expand_dims(season=[season]))
    return xr.concat(fields, dim="season")


def event_seasonal(da: xr.DataArray, year: int) -> xr.DataArray:
    monthly = select_year(da, year).assign_coords(time=list(MONTHS)).rename(time="month")
    return seasonal_from_monthly(monthly)


def depth_thickness(depth: xr.DataArray) -> xr.DataArray:
    z = depth.values.astype(float)
    edges = np.empty(z.size + 1, dtype=float)
    edges[0] = 0.0
    edges[-1] = MAX_DEPTH
    edges[1:-1] = 0.5 * (z[:-1] + z[1:])
    dz = np.diff(edges)
    if np.any(dz <= 0) or not np.isclose(dz.sum(), MAX_DEPTH):
        raise ValueError("Invalid depth-cell thickness")
    return xr.DataArray(dz, dims="depth", coords={"depth": depth})


def positive_integral(
    field: xr.DataArray,
    *,
    lon_bounds: tuple[float, float],
    depth_bounds: tuple[float, float],
) -> float:
    subset = field.sel(
        lon=slice(lon_bounds[0], lon_bounds[1]),
        depth=slice(depth_bounds[0], depth_bounds[1]),
    )
    weights = depth_thickness(field.depth).sel(depth=subset.depth)
    return float(subset.clip(min=0.0).weighted(weights).sum(("depth", "lon")))


def signed_integral(
    field: xr.DataArray,
    *,
    lon_bounds: tuple[float, float],
    depth_bounds: tuple[float, float],
) -> float:
    subset = field.sel(
        lon=slice(lon_bounds[0], lon_bounds[1]),
        depth=slice(depth_bounds[0], depth_bounds[1]),
    )
    weights = depth_thickness(field.depth).sel(depth=subset.depth)
    return float(subset.weighted(weights).sum(("depth", "lon")))


def warm_centroid(field: xr.DataArray) -> tuple[float, float]:
    positive = field.clip(min=0.0)
    dz = depth_thickness(field.depth)
    weighted = positive * dz
    total = float(weighted.sum())
    if not np.isfinite(total) or total <= 0:
        return (math.nan, math.nan)
    lon = float((weighted * field.lon).sum() / total)
    depth = float((weighted * field.depth).sum() / total)
    return lon, depth


def vertical_metrics(seasonal: xr.DataArray) -> dict[str, float]:
    jfm = seasonal.sel(season="JFM")
    amj = seasonal.sel(season="AMJ")
    wc_jfm = jfm.sel(lon=slice(LON_BOUNDS[0], WEST_CENTRAL_END))
    x_jfm, _ = warm_centroid(jfm)
    x_amj, _ = warm_centroid(amj)
    _, reservoir_depth = warm_centroid(wc_jfm)
    east_upper_amj = positive_integral(
        amj, lon_bounds=(WEST_CENTRAL_END, LON_BOUNDS[1]), depth_bounds=(0, 100)
    )
    east_total_amj = positive_integral(
        amj, lon_bounds=(WEST_CENTRAL_END, LON_BOUNDS[1]), depth_bounds=(0, 300)
    )
    east_upper_change = signed_integral(
        amj, lon_bounds=(WEST_CENTRAL_END, LON_BOUNDS[1]), depth_bounds=(0, 100)
    ) - signed_integral(
        jfm, lon_bounds=(WEST_CENTRAL_END, LON_BOUNDS[1]), depth_bounds=(0, 100)
    )
    initial_deep_reservoir = positive_integral(
        jfm,
        lon_bounds=(LON_BOUNDS[0], WEST_CENTRAL_END),
        depth_bounds=(100, 300),
    )
    east_50_100 = float(
        amj.sel(
            lon=slice(WEST_CENTRAL_END, LON_BOUNDS[1]), depth=slice(50, 100)
        ).mean(skipna=True)
    )
    return {
        "jfm_warm_reservoir_depth_m": reservoir_depth,
        "warm_centroid_eastward_shift_deg": x_amj - x_jfm,
        "amj_east_upper100_positive_fraction": (
            east_upper_amj / east_total_amj if east_total_amj > 0 else math.nan
        ),
        "east_upper_release_efficiency_proxy": (
            east_upper_change / initial_deep_reservoir
            if initial_deep_reservoir > 0
            else math.nan
        ),
        "amj_east_50_100m_mean_anomaly_degC": east_50_100,
    }


def pattern_metrics(target: xr.DataArray, reference: xr.DataArray) -> dict[str, float]:
    x = target.values.astype(float).ravel()
    y = reference.values.astype(float).ravel()
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    xm = x.mean()
    ym = y.mean()
    sx = x.std()
    sy = y.std()
    correlation = float(np.mean((x - xm) * (y - ym)) / (sx * sy))
    centered_rmsd = float(np.sqrt(np.mean(((x - xm) - (y - ym)) ** 2)))
    rmsd = float(np.sqrt(np.mean((x - y) ** 2)))
    return {
        "pattern_correlation": correlation,
        "centered_rmsd_degC": centered_rmsd,
        "rmsd_degC": rmsd,
        "target_std_degC": float(sx),
        "reference_std_degC": float(sy),
        "n_points": int(valid.sum()),
    }


def format_lon(value: float) -> str:
    value %= 360.0
    if np.isclose(value, 180.0):
        return "180°"
    if value < 180.0:
        return f"{value:g}°E"
    return f"{360.0 - value:g}°W"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.2,
            "axes.titlesize": 10.8,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "axes.linewidth": 0.8,
            "axes.unicode_minus": False,
        }
    )


def draw_field(
    ax: plt.Axes,
    field: xr.DataArray,
    *,
    norm: TwoSlopeNorm,
    panel_label: str,
    show_xlabel: bool,
    show_ylabel: bool,
) -> plt.collections.QuadMesh:
    mesh = ax.pcolormesh(
        field.lon,
        field.depth,
        field,
        cmap="RdBu_r",
        norm=norm,
        shading="auto",
        rasterized=True,
    )
    ax.contour(
        field.lon,
        field.depth,
        field,
        levels=[-1.0, 1.0],
        colors=["#24599a", "#9e1f21"],
        linewidths=0.65,
        linestyles=["--", "-"],
        alpha=0.9,
    )
    ax.axvline(WEST_END, color="0.35", linestyle=(0, (2, 2)), linewidth=0.7)
    ax.axvline(WEST_CENTRAL_END, color="0.35", linestyle=(0, (2, 2)), linewidth=0.7)
    ax.add_patch(
        Rectangle(
            (WEST_CENTRAL_END, 50),
            LON_BOUNDS[1] - WEST_CENTRAL_END,
            50,
            fill=False,
            edgecolor="#202020",
            linewidth=1.1,
            linestyle=(0, (4, 2)),
            zorder=8,
        )
    )
    ax.set_xlim(*LON_BOUNDS)
    ax.set_ylim(MAX_DEPTH, 0)
    xticks = (121, 160, 180, 210, 240, 279)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(value) for value in xticks])
    ax.set_yticks((0, 50, 100, 150, 200, 250, 300))
    ax.tick_params(direction="out", length=2.8, width=0.7)
    if show_xlabel:
        ax.set_xlabel("Longitude")
    else:
        ax.tick_params(labelbottom=False)
    if show_ylabel:
        ax.set_ylabel("Depth (m)")
    else:
        ax.tick_params(labelleft=False)
    ax.text(
        0.012,
        0.966,
        panel_label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontweight="bold",
        fontsize=9.5,
        color="black",
    )
    return mesh


def save_both(fig: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    return png, pdf


def plot_seasonal(
    fields: xr.DataArray,
    *,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(2, 4, figsize=(17.2, 8.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.063, right=0.99, top=0.84, bottom=0.18, wspace=0.075, hspace=0.13)
    fig.suptitle(
        "Equatorial Pacific vertical heat-reservoir structure: ENSO strength classes and 2026",
        y=0.965,
        fontsize=15.0,
        fontweight="bold",
    )
    titles = (
        f"Strong composite\nSODA3, n={len(STRONG_YEARS)}",
        f"Moderate composite\nSODA3, n={len(MODERATE_YEARS)}",
        "Strong minus moderate\nSODA3",
        "2026\nGODAS real-time",
    )
    for col, title in enumerate(titles):
        axes[0, col].set_title(title, fontweight="bold", pad=7)
    mesh = None
    letter = 0
    for row, season in enumerate(SEASONS):
        for col, category in enumerate(fields.category.values):
            mesh = draw_field(
                axes[row, col],
                fields.sel(season=season, category=category),
                norm=norm,
                panel_label=f"{chr(ord('a') + letter)}",
                show_xlabel=row == 1,
                show_ylabel=col == 0,
            )
            letter += 1
            if col == 0:
                axes[row, col].text(
                    -0.18,
                    0.5,
                    season,
                    transform=axes[row, col].transAxes,
                    rotation=90,
                    ha="center",
                    va="center",
                    fontsize=12.0,
                    fontweight="bold",
                )
    assert mesh is not None
    cax = fig.add_axes((0.29, 0.083, 0.43, 0.025))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Potential-temperature anomaly (°C)")
    note = (
        "Historical: SODA3.15.2 5°S–5°N, 1980–2024 same-month mean/trend removed. "
        "2026: NOAA GODAS 5°S–5°N anomaly from its 1991–2020 climatology (cross-product column). "
        f"Strong={STRONG_YEARS}; moderate={MODERATE_YEARS}. Dashed box: eastern Pacific 50–100 m."
    )
    fig.text(0.012, 0.018, note, fontsize=7.6, color="0.28")
    return save_both(
        fig,
        output_dir,
        "fig_jfm_amj_strong_moderate_difference_2026_vertical_temperature",
    )


def plot_monthly(
    fields: xr.DataArray,
    *,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(6, 4, figsize=(16.5, 19.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.065, right=0.99, top=0.925, bottom=0.095, wspace=0.075, hspace=0.11)
    fig.suptitle(
        "January–June vertical evolution: ENSO strength classes and 2026",
        y=0.985,
        fontsize=15.5,
        fontweight="bold",
    )
    titles = (
        "Strong composite (SODA3)",
        "Moderate composite (SODA3)",
        "Strong minus moderate",
        "2026 (GODAS real-time)",
    )
    for col, title in enumerate(titles):
        axes[0, col].set_title(title, fontweight="bold", pad=6)
    mesh = None
    letter = 0
    for row, (month, label) in enumerate(zip(MONTHS, MONTH_LABELS)):
        for col, category in enumerate(fields.category.values):
            mesh = draw_field(
                axes[row, col],
                fields.sel(month=month, category=category),
                norm=norm,
                panel_label=f"{chr(ord('a') + letter)}",
                show_xlabel=row == 5,
                show_ylabel=col == 0,
            )
            letter += 1
            if col == 0:
                axes[row, col].text(
                    -0.18,
                    0.5,
                    label,
                    transform=axes[row, col].transAxes,
                    rotation=90,
                    ha="center",
                    va="center",
                    fontsize=10.8,
                    fontweight="bold",
                )
    assert mesh is not None
    cax = fig.add_axes((0.29, 0.041, 0.43, 0.012))
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal", extend="both")
    colorbar.set_label("Potential-temperature anomaly (°C)")
    note = (
        "Historical SODA3 anomalies remove the 1980–2024 same-month mean and trend; "
        "2026 GODAS anomalies use the 1991–2020 GODAS monthly climatology. "
        "Dashed box marks the eastern-Pacific 50–100 m discriminator."
    )
    fig.text(0.012, 0.011, note, fontsize=7.6, color="0.28")
    return save_both(
        fig,
        output_dir,
        "fig_jan_jun_strong_moderate_difference_2026_vertical_temperature",
    )


def robust_vlim(*arrays: xr.DataArray) -> float:
    values = np.concatenate(
        [np.abs(array.values[np.isfinite(array.values)]) for array in arrays]
    )
    percentile = float(np.quantile(values, 0.985))
    return max(2.0, math.ceil(percentile * 2.0) / 2.0)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    setup_style()

    soda_ds = open_dataset(SODA_FILE)
    godas_obs = open_dataset(GODAS_2026_FILE)
    godas_clim = open_dataset(GODAS_CLIM_FILE)
    validate_soda(soda_ds)
    validate_godas(godas_obs, godas_clim)

    soda_temperature = fixed_mask_latitude_mean(
        soda_ds.temp, vertical_dim="depth"
    )
    soda_anomaly = common_grid(soda_detrended_anomaly(soda_temperature), "depth")
    godas_anomaly = common_grid(godas_2026_anomaly(godas_obs, godas_clim), "level")
    godas_monthly = godas_anomaly.assign_coords(time=list(MONTHS)).rename(time="month")

    strong_monthly = class_monthly(soda_anomaly, STRONG_YEARS)
    moderate_monthly = class_monthly(soda_anomaly, MODERATE_YEARS)
    difference_monthly = strong_monthly - moderate_monthly
    categories = ("strong", "moderate", "strong_minus_moderate", "2026")
    monthly_fields = xr.concat(
        [strong_monthly, moderate_monthly, difference_monthly, godas_monthly],
        dim=pd.Index(categories, name="category"),
    )
    seasonal_fields = xr.concat(
        [
            seasonal_from_monthly(strong_monthly),
            seasonal_from_monthly(moderate_monthly),
            seasonal_from_monthly(difference_monthly),
            seasonal_from_monthly(godas_monthly),
        ],
        dim=pd.Index(categories, name="category"),
    )

    vlim = args.vlim if args.vlim is not None else robust_vlim(monthly_fields)
    if not 2.0 <= vlim <= 12.0:
        raise ValueError(f"Implausible automatic color limit: {vlim}")

    # Event-level metrics expose small-n spread behind the composites.
    metric_rows: list[dict[str, float | int | str]] = []
    for class_name, years in (("strong", STRONG_YEARS), ("moderate", MODERATE_YEARS)):
        for year in years:
            metrics = vertical_metrics(event_seasonal(soda_anomaly, year))
            metric_rows.append(
                {"event_year": year, "class": class_name, "source": "SODA3", **metrics}
            )
    for class_name in ("strong", "moderate"):
        metrics = vertical_metrics(seasonal_fields.sel(category=class_name))
        metric_rows.append(
            {
                "event_year": 0,
                "class": f"{class_name}_composite",
                "source": "SODA3",
                **metrics,
            }
        )
    metric_rows.append(
        {
            "event_year": 2026,
            "class": "target",
            "source": "GODAS",
            **vertical_metrics(seasonal_fields.sel(category="2026")),
        }
    )
    metrics_frame = pd.DataFrame(metric_rows)
    metrics_path = args.output_dir / "vertical_profile_metrics.csv"
    metrics_frame.to_csv(metrics_path, index=False)

    similarity_rows = []
    for month in MONTHS:
        for class_name in ("strong", "moderate"):
            row = pattern_metrics(
                monthly_fields.sel(category="2026", month=month),
                monthly_fields.sel(category=class_name, month=month),
            )
            similarity_rows.append(
                {
                    "period": MONTH_LABELS[month - 1],
                    "reference_class": class_name,
                    **row,
                }
            )
    for season in SEASONS:
        for class_name in ("strong", "moderate"):
            row = pattern_metrics(
                seasonal_fields.sel(category="2026", season=season),
                seasonal_fields.sel(category=class_name, season=season),
            )
            similarity_rows.append(
                {"period": season, "reference_class": class_name, **row}
            )
    for class_name in ("strong", "moderate"):
        row = pattern_metrics(
            seasonal_fields.sel(category="2026"),
            seasonal_fields.sel(category=class_name),
        )
        similarity_rows.append(
            {"period": "JFM+AMJ", "reference_class": class_name, **row}
        )
    similarity_frame = pd.DataFrame(similarity_rows)
    similarity_path = args.output_dir / "vertical_profile_pattern_similarity.csv"
    similarity_frame.to_csv(similarity_path, index=False)

    trajectory_rows = []
    for category in ("strong", "moderate", "2026"):
        for month in MONTHS:
            field = monthly_fields.sel(category=category, month=month)
            longitude, depth = warm_centroid(field)
            trajectory_rows.append(
                {
                    "category": category,
                    "month": month,
                    "month_label": MONTH_LABELS[month - 1],
                    "warm_centroid_longitude_degE": longitude,
                    "warm_centroid_depth_m": depth,
                    "east_50_100m_mean_anomaly_degC": float(
                        field.sel(
                            lon=slice(WEST_CENTRAL_END, LON_BOUNDS[1]),
                            depth=slice(50, 100),
                        ).mean(skipna=True)
                    ),
                }
            )
    trajectory_frame = pd.DataFrame(trajectory_rows)
    trajectory_path = args.output_dir / "monthly_warm_centroid_trajectory.csv"
    trajectory_frame.to_csv(trajectory_path, index=False)

    # Independent cross-product check at selected overlapping event years.
    validation_rows = []
    for year in GODAS_VALIDATION_YEARS:
        path = godas_validation_path(year)
        if not path.exists():
            continue
        validation_obs = open_dataset(path)
        if validation_obs.sizes.get("time", 0) != 6:
            raise ValueError(f"Expected six GODAS validation months for {year}")
        validation_godas = common_grid(
            godas_2026_anomaly(validation_obs, godas_clim), "level"
        ).assign_coords(time=list(MONTHS)).rename(time="month")
        validation_soda = select_year(soda_anomaly, year).assign_coords(
            time=list(MONTHS)
        ).rename(time="month")
        for period, godas_field, soda_field in (
            ("Jan-Jun", validation_godas, validation_soda),
            (
                "JFM",
                validation_godas.sel(month=[1, 2, 3]).mean("month"),
                validation_soda.sel(month=[1, 2, 3]).mean("month"),
            ),
            (
                "AMJ",
                validation_godas.sel(month=[4, 5, 6]).mean("month"),
                validation_soda.sel(month=[4, 5, 6]).mean("month"),
            ),
        ):
            validation_rows.append(
                {
                    "event_year": year,
                    "period": period,
                    **pattern_metrics(godas_field, soda_field),
                }
            )
        validation_obs.close()
    validation_frame = pd.DataFrame(validation_rows)
    validation_path = args.output_dir / "soda3_godas_overlap_validation.csv"
    validation_frame.to_csv(validation_path, index=False)

    derived = xr.Dataset(
        {
            "monthly_temperature_anomaly": monthly_fields.astype(np.float32),
            "seasonal_temperature_anomaly": seasonal_fields.astype(np.float32),
        },
        attrs={
            "title": "Strong/moderate El Nino vertical profiles and 2026 real-time comparison",
            "historical_source": str(SODA_FILE),
            "target_source": str(GODAS_2026_FILE),
            "target_climatology_source": str(GODAS_CLIM_FILE),
            "strong_years": ",".join(map(str, STRONG_YEARS)),
            "moderate_years": ",".join(map(str, MODERATE_YEARS)),
            "latitude_average": "5S-5N cosine weighted with fixed full-column mask",
            "cross_product_warning": (
                "Historical columns are SODA3 detrended anomalies; 2026 is a GODAS "
                "anomaly from the GODAS 1991-2020 climatology. Pattern similarity is "
                "more robust than direct amplitude difference across products."
            ),
        },
    )
    derived.monthly_temperature_anomaly.attrs.update(units="degC")
    derived.seasonal_temperature_anomaly.attrs.update(units="degC")
    derived_path = args.output_dir / "vertical_profile_comparison_fields.nc"
    derived.to_netcdf(derived_path, engine="h5netcdf")

    seasonal_paths = plot_seasonal(
        seasonal_fields, output_dir=args.output_dir, vlim=vlim
    )
    monthly_paths = plot_monthly(
        monthly_fields, output_dir=args.output_dir, vlim=vlim
    )

    summary = {
        "color_limit_degC": vlim,
        "seasonal_figure_png": str(seasonal_paths[0]),
        "seasonal_figure_pdf": str(seasonal_paths[1]),
        "monthly_figure_png": str(monthly_paths[0]),
        "monthly_figure_pdf": str(monthly_paths[1]),
        "derived_netcdf": str(derived_path),
        "metrics_csv": str(metrics_path),
        "similarity_csv": str(similarity_path),
        "trajectory_csv": str(trajectory_path),
        "cross_product_validation_csv": str(validation_path),
        "strong_years": list(STRONG_YEARS),
        "moderate_years": list(MODERATE_YEARS),
    }
    summary_path = args.output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print("\nSimilarity")
    print(similarity_frame.to_string(index=False))
    print("\nComposite and target metrics")
    print(metrics_frame[metrics_frame.event_year.isin((0, 2026))].to_string(index=False))

    soda_ds.close()
    godas_obs.close()
    godas_clim.close()


if __name__ == "__main__":
    main()
