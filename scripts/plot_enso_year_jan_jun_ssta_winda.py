#!/usr/bin/env python3
"""Plot a selected year's January-June OISST SSTA and ERA5 wind anomalies.

Both fields are calculated as same-calendar-month residuals from a linear
least-squares fit over their requested baseline periods:

* OISST SST: 1982-2024 (OISST starts in late 1981)
* ERA5 850-hPa u/v wind: 1980-2024

The output uses the same Pacific domain, regional boxes, colour range, and
wind-vector reference as the revised ENSO event figures in this project.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


DEFAULT_TARGET_YEAR = 1996
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SST_BASELINE = (1982, 2024)
WIND_BASELINE = (1980, 2024)

INPUT_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
ERA5_JAN_MAY = ROOT / "data/raw/era5/era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc"
ERA5_JUNE = ROOT / "data/raw/era5/era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jun.nc"
DERIVED_DIR = ROOT / "data/derived/research_2026"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 320,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 11.4,
            "axes.titlesize": 13.5,
            "axes.labelsize": 11.5,
            "xtick.labelsize": 10.2,
            "ytick.labelsize": 10.2,
            "axes.linewidth": 0.9,
            "axes.unicode_minus": False,
        }
    )


def oisst_path(month: int) -> Path:
    tag = ("jan", "feb", "mar", "apr", "may", "jun")[month - 1]
    return INPUT_DIR / f"oisst_sst_tropics_1deg_{tag}_1982_2026.nc"


def standardize(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    if "valid_time" in ds.coords:
        rename["valid_time"] = "time"
    if "latitude" in ds.coords:
        rename["latitude"] = "lat"
    if "longitude" in ds.coords:
        rename["longitude"] = "lon"
    ds = ds.rename(rename)
    if "lon" in ds.coords:
        ds = ds.assign_coords(lon=(ds.lon % 360)).sortby("lon")
    if "lat" in ds.coords:
        ds = ds.sortby("lat")
    if "time" in ds.coords:
        monthly_time = pd.to_datetime(ds.time.values).to_period("M").to_timestamp()
        ds = ds.assign_coords(time=monthly_time)
    return ds


def open_oisst() -> xr.DataArray:
    arrays = []
    for month in MONTHS:
        path = oisst_path(month)
        if not path.exists():
            raise FileNotFoundError(path)
        # The compact OISST panel inputs are NetCDF3 files.  Selecting the
        # scipy backend avoids depending on the optional netCDF4 extension.
        arrays.append(
            standardize(xr.open_dataset(path, chunks=None, engine="scipy"))["sst"]
        )
    sst = xr.concat(arrays, dim="time").sortby("time")
    return sst.sel(lat=slice(-30, 30), lon=slice(120, 280))


def open_era5_wind() -> xr.Dataset:
    for path in (ERA5_JAN_MAY, ERA5_JUNE):
        if not path.exists():
            raise FileNotFoundError(path)
    wind = xr.concat(
        [
            standardize(xr.open_dataset(ERA5_JAN_MAY, chunks=None, engine="netcdf4")),
            standardize(xr.open_dataset(ERA5_JUNE, chunks=None, engine="netcdf4")),
        ],
        dim="time",
    ).sortby("time")
    if "pressure_level" in wind.dims:
        wind = wind.sel(pressure_level=850, drop=True)
    wind = wind.rename({"u": "u850", "v": "v850"})
    return wind[["u850", "v850"]].sel(lat=slice(-30, 30), lon=slice(120, 280))


def same_month_detrended_target(
    da: xr.DataArray,
    *,
    target_year: int,
    baseline: tuple[int, int],
) -> xr.DataArray:
    """Return Jan-Jun target residuals from same-month baseline linear fits."""
    pieces = []
    for month in MONTHS:
        monthly = da.where(da.time.dt.month == month, drop=True).sortby("time")
        years = monthly.time.dt.year.astype(float)
        base = monthly.where(
            (monthly.time.dt.year >= baseline[0]) & (monthly.time.dt.year <= baseline[1]),
            drop=True,
        )
        if base.sizes.get("time", 0) < 10:
            raise ValueError(f"Too few baseline records for month {month}: {base.sizes.get('time', 0)}")
        target = monthly.where(monthly.time.dt.year == target_year, drop=True)
        if target.sizes.get("time", 0) != 1:
            raise ValueError(f"Expected one record for {target_year}-{month:02d}")

        # xarray.polyfit skips missing ocean/land points and fits each grid
        # independently.  The residual includes removal of both the baseline
        # mean and its linear trend.
        fit = base.assign_coords(year=("time", base.time.dt.year.values.astype(float))).swap_dims({"time": "year"})
        coeff = fit.polyfit(dim="year", deg=1, skipna=True).polyfit_coefficients
        predicted = xr.polyval(xr.DataArray(float(target_year)), coeff)
        residual = target.isel(time=0, drop=True) - predicted
        residual = residual.expand_dims(
            time=[np.datetime64(f"{target_year}-{month:02d}-01", "ns")]
        )
        pieces.append(residual.astype(np.float32))
    return xr.concat(pieces, dim="time")


def format_lon(value: float) -> str:
    lon = value % 360
    if np.isclose(lon, 180):
        return "180°"
    if lon < 180:
        return f"{lon:g}°E"
    return f"{360 - lon:g}°W"


def format_lat(value: float) -> str:
    if np.isclose(value, 0):
        return "Eq"
    return f"{abs(value):g}°{'N' if value > 0 else 'S'}"


def format_axes(ax: plt.Axes, *, row: int, col: int) -> None:
    ax.set_xlim(120, 280)
    ax.set_ylim(-30, 30)
    ax.set_xticks([120, 160, 200, 240, 280])
    ax.set_yticks([-30, 0, 30])
    ax.set_xticklabels([format_lon(x) for x in [120, 160, 200, 240, 280]] if row == 1 else [])
    ax.set_yticklabels([format_lat(y) for y in [-30, 0, 30]] if col == 0 else [])
    ax.axhline(0, color="0.25", lw=0.65, zorder=3)
    if row == 1:
        ax.set_xlabel("Longitude")
    if col == 0:
        ax.set_ylabel("Latitude")
    ax.tick_params(length=3.5, width=0.85, pad=2.2)
    ax.set_box_aspect(0.375)


def add_regions(ax: plt.Axes) -> None:
    boxes = [
        ("EP", -5, 5, 220, 260, "#009E73", "-"),
        ("FEP", -5, 5, 270, 280, "#CC79A7", "-"),
        ("Niño-3.4", -5, 5, 190, 240, "#0072B2", "--"),
        ("Niño-3", -5, 5, 210, 270, "#D55E00", "-."),
    ]
    offsets = {
        "EP": (15.0, 1.4),
        "FEP": (-1.0, 1.4),
        "Niño-3": (23.0, -6.1),
        "Niño-3.4": (1.5, 1.4),
    }
    for label, lat0, lat1, lon0, lon1, color, linestyle in boxes:
        ax.plot(
            [lon0, lon1, lon1, lon0, lon0],
            [lat0, lat0, lat1, lat1, lat0],
            color=color,
            lw=1.25,
            ls=linestyle,
            zorder=6,
        )
        dx, dy = offsets[label]
        y0 = lat1 if dy >= 0 else lat0
        ax.text(
            lon0 + dx,
            y0 + dy,
            label,
            fontsize=8.0,
            weight="bold",
            color=color,
            bbox={"boxstyle": "round,pad=0.08", "facecolor": "white", "edgecolor": "none", "alpha": 0.76},
            zorder=7,
        )


def add_wind_vectors(
    ax: plt.Axes,
    lon: np.ndarray,
    lat: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
) -> None:
    x = lon[::7]
    y = lat[::5]
    uu = u[::5, ::7]
    vv = v[::5, ::7]
    ax.quiver(
        x,
        y,
        uu,
        vv,
        color="white",
        pivot="middle",
        width=0.0052,
        headwidth=3.8,
        headlength=4.7,
        headaxislength=4.3,
        scale=47,
        alpha=0.70,
        zorder=4,
    )
    q = ax.quiver(
        x,
        y,
        uu,
        vv,
        color="#111111",
        pivot="middle",
        width=0.0031,
        headwidth=3.6,
        headlength=4.7,
        headaxislength=4.3,
        scale=47,
        zorder=5,
    )
    background = Rectangle(
        (0.81, 0.015),
        0.185,
        0.255,
        transform=ax.transAxes,
        facecolor="white",
        edgecolor="0.28",
        linewidth=0.65,
        zorder=8,
    )
    ax.add_patch(background)
    key = ax.quiverkey(
        q,
        0.902,
        0.17,
        4.0,
        r"4 m s$^{-1}$",
        labelpos="S",
        coordinates="axes",
        labelsep=0.035,
        fontproperties={"size": 9.0},
    )
    key.set_zorder(10)


def area_mean(
    da: xr.DataArray,
    *,
    lat_bounds: tuple[float, float],
    lon_bounds: tuple[float, float],
) -> xr.DataArray:
    subset = da.sel(lat=slice(*lat_bounds), lon=slice(*lon_bounds))
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean(("lat", "lon"))


def save_derived(
    ssta: xr.DataArray,
    u850a: xr.DataArray,
    v850a: xr.DataArray,
    *,
    target_year: int,
) -> tuple[Path, Path]:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    baseline_tag = f"{SST_BASELINE[0]}_{SST_BASELINE[1]}"
    nc_path = DERIVED_DIR / f"{target_year}_jan_jun_oisst_ssta_era5_850_wind_anomalies_{baseline_tag}.nc"
    csv_path = DERIVED_DIR / f"{target_year}_jan_jun_ssta_wind_region_summary_{baseline_tag}.csv"
    ssta_store = ssta.rename({"lat": "sst_lat", "lon": "sst_lon"})
    u850a_store = u850a.rename({"lat": "wind_lat", "lon": "wind_lon"})
    v850a_store = v850a.rename({"lat": "wind_lat", "lon": "wind_lon"})
    ds = xr.Dataset(
        {
            "ssta": ssta_store,
            "u850a": u850a_store,
            "v850a": v850a_store,
        },
        attrs={
            "title": f"January-June {target_year} OISST SSTA and ERA5 850-hPa wind anomalies",
            "method": "Same-calendar-month residual from a linear fit over each source's baseline period.",
            "oisst_baseline": f"{SST_BASELINE[0]}-{SST_BASELINE[1]}",
            "era5_wind_baseline": f"{WIND_BASELINE[0]}-{WIND_BASELINE[1]}",
        },
    )
    ds["ssta"].attrs.update(units="degC", long_name="OISST sea-surface temperature anomaly")
    ds["u850a"].attrs.update(units="m s-1", long_name="ERA5 850-hPa zonal-wind anomaly")
    ds["v850a"].attrs.update(units="m s-1", long_name="ERA5 850-hPa meridional-wind anomaly")
    # Pin the time encoding for compatibility with the older xarray version
    # in the project's scientific environment.
    ds.to_netcdf(
        nc_path,
        engine="netcdf4",
        encoding={"time": {"units": "days since 1980-01-01", "dtype": "int32"}},
    )

    summary = pd.DataFrame(
        {
            "time": pd.to_datetime(ssta.time.values),
            "nino34_ssta_degC": area_mean(ssta, lat_bounds=(-5, 5), lon_bounds=(190, 240)).values,
            "nino3_ssta_degC": area_mean(ssta, lat_bounds=(-5, 5), lon_bounds=(210, 270)).values,
            "fep_ssta_degC": area_mean(ssta, lat_bounds=(-5, 5), lon_bounds=(270, 280)).values,
            "west_central_u850a_ms": area_mean(
                u850a, lat_bounds=(-5, 5), lon_bounds=(160, 220)
            ).values,
        }
    )
    summary.to_csv(csv_path, index=False, float_format="%.4f")
    return nc_path, csv_path


def plot(
    ssta: xr.DataArray,
    wind: xr.Dataset,
    *,
    target_year: int,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    setup_style()
    baseline_tag = f"{SST_BASELINE[0]}_{SST_BASELINE[1]}"
    out_dir = output_dir or (
        ROOT / f"outputs/research_2026/event_{target_year}_monthly_panels_{baseline_tag}_detrended"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 3, figsize=(13.6, 6.05), constrained_layout=True)
    fig.suptitle(
        f"{target_year} January–June: OISST SSTA with ERA5 850 hPa wind anomalies",
        fontsize=17.0,
        weight="bold",
        y=1.015,
    )
    mesh = None
    for i, ax in enumerate(axes.ravel()):
        row, col = divmod(i, 3)
        mesh = ax.pcolormesh(
            ssta.lon,
            ssta.lat,
            ssta.isel(time=i),
            cmap="RdBu_r",
            vmin=-2.5,
            vmax=2.5,
            shading="auto",
            rasterized=True,
        )
        add_wind_vectors(
            ax,
            wind.lon.values,
            wind.lat.values,
            wind.u850a.isel(time=i).values,
            wind.v850a.isel(time=i).values,
        )
        add_regions(ax)
        format_axes(ax, row=row, col=col)
        ax.set_title(f"{MONTH_LABELS[i]} {target_year}", weight="bold", pad=6)

    assert mesh is not None
    cbar = fig.colorbar(
        mesh,
        ax=axes.ravel().tolist(),
        orientation="horizontal",
        shrink=0.64,
        pad=0.045,
        aspect=42,
        ticks=[-2.5, -2, -1, 0, 1, 2, 2.5],
        extend="both",
    )
    cbar.set_label("OISST SST anomaly (°C)", fontsize=12.4)
    cbar.ax.tick_params(labelsize=10.8)
    fig.text(
        0.01,
        -0.025,
        "Monthly same-calendar-month detrended anomalies. "
        f"OISST baseline {SST_BASELINE[0]}–{SST_BASELINE[1]}; "
        f"ERA5 wind baseline {WIND_BASELINE[0]}–{WIND_BASELINE[1]}. "
        r"Each panel's wind-vector reference is 4 m s$^{-1}$.",
        fontsize=9.4,
        color="0.28",
    )

    png_path = out_dir / f"fig_{target_year}_jan_jun_oisst_ssta_era5_850_windA_{baseline_tag}.png"
    pdf_path = out_dir / f"fig_{target_year}_jan_jun_oisst_ssta_era5_850_windA_{baseline_tag}.pdf"
    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return png_path, pdf_path


def validate(ssta: xr.DataArray, wind: xr.Dataset) -> None:
    if ssta.sizes != {"time": 6, "lat": 60, "lon": 160}:
        raise ValueError(f"Unexpected SSTA dimensions: {dict(ssta.sizes)}")
    if wind.u850a.sizes != {"time": 6, "lat": 61, "lon": 161}:
        raise ValueError(f"Unexpected wind dimensions: {dict(wind.u850a.sizes)}")
    if not np.isfinite(wind[["u850a", "v850a"]].to_array()).all():
        raise ValueError("Unexpected missing values in ERA5 wind anomalies")
    if float(np.nanmax(np.abs(ssta.values))) > 8:
        raise ValueError("Implausible SSTA magnitude")
    if float(np.nanmax(np.abs(wind[["u850a", "v850a"]].to_array().values))) > 25:
        raise ValueError("Implausible wind-anomaly magnitude")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot January-June OISST SSTA with ERA5 850-hPa wind anomalies."
    )
    parser.add_argument("--target-year", type=int, default=DEFAULT_TARGET_YEAR)
    args = parser.parse_args()
    target_year = int(args.target_year)

    sst = open_oisst()
    era5 = open_era5_wind()
    ssta = same_month_detrended_target(sst, target_year=target_year, baseline=SST_BASELINE)
    u850a = same_month_detrended_target(
        era5.u850,
        target_year=target_year,
        baseline=WIND_BASELINE,
    )
    v850a = same_month_detrended_target(
        era5.v850,
        target_year=target_year,
        baseline=WIND_BASELINE,
    )
    wind = xr.Dataset({"u850a": u850a, "v850a": v850a})
    validate(ssta, wind)
    nc_path, csv_path = save_derived(ssta, u850a, v850a, target_year=target_year)
    png_path, pdf_path = plot(ssta, wind, target_year=target_year)
    print(f"SSTA range: {float(ssta.min(skipna=True)):.3f} to {float(ssta.max(skipna=True)):.3f} degC")
    print(
        "Wind anomaly component range: "
        f"{float(wind.to_array().min()):.3f} to {float(wind.to_array().max()):.3f} m s-1"
    )
    print(nc_path)
    print(csv_path)
    print(png_path)
    print(pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
