#!/usr/bin/env python3
"""Plot Apr-May spatial comparisons for 2015/16, 2023/24, and 2026.

The figure family keeps the calendar window aligned with the current 2026
analysis: Apr-May of the event developing year. SST and rainfall use the NOAA
PSL THREDDS subsets downloaded for this purpose; ERA5 wind/pressure use local
ERA5 archives plus the compact 2026 CDS subset.
"""

from __future__ import annotations

from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


OUT_DIR = ROOT / "outputs/research_2026/figures"
DERIVED_DIR = ROOT / "data/derived/research_2026"

OISST_APR = ROOT / "data/interim/research_2026/oisst_event_spatial_tropics_apr_1982_2026_1deg.nc"
OISST_MAY = ROOT / "data/interim/research_2026/oisst_event_spatial_tropics_may_1982_2026_1deg.nc"
GPCP = ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc"
ERA5_FULL = ROOT / "data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc"
ERA5_2026_DIR = ROOT / "data/raw/era5/era5_monthly_single_tropics_1deg_1982_2022_2026_jan_may"
ERA5_2026_AVGUA = ERA5_2026_DIR / "data_stream-moda_stepType-avgua.nc"

REFERENCE_START = 1982
REFERENCE_END = 2022
EVENTS = [(2015, "2015/16"), (2023, "2023/24"), (2026, "2026")]

SST_BOXES = {
    "TIO": (-20, 20, 40, 110),
    "MC": (-10, 10, 95, 150),
    "WPWP": (-10, 10, 120, 160),
    "Nino-3.4": (-5, 5, 190, 240),
    "Nino-3": (-5, 5, 210, 270),
    "FEP": (-5, 5, 270, 280),
    "TNA": (0, 20, 300, 340),
}
PACIFIC_BOXES = {
    "WCP": (-5, 5, 140, 180),
    "CP": (-5, 5, 180, 220),
    "EP": (-5, 5, 220, 260),
    "FEP": (-5, 5, 270, 280),
}
WIND_BOXES = {
    "Darwin": (-20, -5, 120, 140),
    "CWP u10": (-5, 5, 160, 220),
    "Tahiti": (-25, -10, 200, 220),
}
BOX_LABEL_OFFSETS = {
    "Nino-3.4": (1.0, 1.0),
    "Nino-3": (20.0, -5.0),
    "FEP": (-8.0, 1.0),
    "TIO": (1.0, 1.0),
    "TNA": (1.0, 1.0),
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.5,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "axes.linewidth": 0.8,
            "axes.unicode_minus": False,
        }
    )


def format_lon(value: float) -> str:
    lon = value % 360
    if np.isclose(lon, 0):
        return "0"
    if np.isclose(lon, 180):
        return "180"
    if lon < 180:
        return f"{lon:g}E"
    return f"{360 - lon:g}W"


def format_lat(value: float) -> str:
    if np.isclose(value, 0):
        return "Eq"
    if value > 0:
        return f"{value:g}N"
    return f"{abs(value):g}S"


def format_map_axes(ax, lon_ticks, lat_ticks=(-30, -15, 0, 15, 30)) -> None:
    ax.set_yticks(lat_ticks)
    ax.set_yticklabels([format_lat(tick) for tick in lat_ticks])
    ax.set_xticks(lon_ticks)
    ax.set_xticklabels([format_lon(tick) for tick in lon_ticks])
    ax.axhline(0, color="0.22", linewidth=0.55)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def add_boxes(ax, boxes: dict[str, tuple[float, float, float, float]], lon_min: float, lon_max: float) -> None:
    for label, (lat0, lat1, x0, x1) in boxes.items():
        if x1 < lon_min or x0 > lon_max:
            continue
        x0_clip = max(x0, lon_min)
        x1_clip = min(x1, lon_max)
        ax.plot(
            [x0_clip, x1_clip, x1_clip, x0_clip, x0_clip],
            [lat0, lat0, lat1, lat1, lat0],
            color="0.12",
            linewidth=0.7,
        )
        dx, dy = BOX_LABEL_OFFSETS.get(label, (1.0, 1.0))
        y_anchor = lat1 if dy >= 0 else lat0
        ax.text(x0_clip + dx, y_anchor + dy, label, fontsize=6.1, color="0.12")


def standardize_lon_lat(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    if "latitude" in ds.coords:
        rename["latitude"] = "lat"
    if "longitude" in ds.coords:
        rename["longitude"] = "lon"
    if "valid_time" in ds.coords:
        rename["valid_time"] = "time"
    ds = ds.rename(rename)
    if "lon" in ds.coords:
        ds = ds.assign_coords(lon=(ds["lon"] % 360)).sortby("lon")
    if "lat" in ds.coords:
        ds = ds.sortby("lat")
    return ds


def apr_may_anomaly_from_two_month_files(path_apr: Path, path_may: Path, var: str) -> xr.DataArray:
    apr = standardize_lon_lat(xr.open_dataset(path_apr, engine="h5netcdf"))[var]
    may = standardize_lon_lat(xr.open_dataset(path_may, engine="h5netcdf"))[var]
    clim_apr = apr.sel(time=slice(f"{REFERENCE_START}-01-01", f"{REFERENCE_END}-12-31")).mean("time")
    clim_may = may.sel(time=slice(f"{REFERENCE_START}-01-01", f"{REFERENCE_END}-12-31")).mean("time")
    pieces = []
    for year, label in EVENTS:
        event = 0.5 * (
            (apr.sel(time=f"{year}-04-01") - clim_apr)
            + (may.sel(time=f"{year}-05-01") - clim_may)
        )
        event = event.expand_dims(event=[label])
        pieces.append(event)
    return xr.concat(pieces, dim="event")


def apr_may_anomaly_from_monthly_file(path: Path, var: str) -> xr.DataArray:
    ds = standardize_lon_lat(xr.open_dataset(path, engine="h5netcdf"))
    da = ds[var]
    clim = da.sel(time=slice(f"{REFERENCE_START}-01-01", f"{REFERENCE_END}-12-31")).groupby("time.month").mean("time")
    anom = da.groupby("time.month") - clim
    pieces = []
    for year, label in EVENTS:
        event = anom.sel(time=(anom.time.dt.year == year) & (anom.time.dt.month.isin([4, 5]))).mean("time")
        event = event.expand_dims(event=[label])
        pieces.append(event)
    return xr.concat(pieces, dim="event")


def open_era5_full_1deg() -> xr.Dataset:
    ds = standardize_lon_lat(xr.open_dataset(ERA5_FULL, engine="h5netcdf"))
    ds = ds[["u10", "msl"]].rename({"msl": "msl_hpa"})
    ds["msl_hpa"] = ds["msl_hpa"] / 100.0
    ds = ds.sel(lat=slice(-30, 30), lon=slice(120, 280))
    # The local archive is 0.25 degree. Use every fourth grid point so it
    # matches the compact 2026 1-degree product closely enough for visual comparison.
    ds = ds.isel(lat=slice(None, None, 4), lon=slice(None, None, 4))
    return ds


def open_era5_compact_2026() -> xr.Dataset:
    ds = standardize_lon_lat(xr.open_dataset(ERA5_2026_AVGUA, engine="h5netcdf"))
    ds = ds[["u10", "msl"]].rename({"msl": "msl_hpa"})
    ds["msl_hpa"] = ds["msl_hpa"] / 100.0
    return ds.sel(lat=slice(-30, 30), lon=slice(120, 280))


def era5_apr_may_anomaly() -> xr.Dataset:
    full = open_era5_full_1deg()
    compact = open_era5_compact_2026()

    full_clim = full.sel(time=slice(f"{REFERENCE_START}-01-01", f"{REFERENCE_END}-12-31")).groupby("time.month").mean("time")
    full_anom = full.groupby("time.month") - full_clim
    compact_clim = compact.sel(time=slice(f"{REFERENCE_START}-01-01", f"{REFERENCE_END}-12-31")).groupby("time.month").mean("time")
    compact_anom = compact.groupby("time.month") - compact_clim

    pieces = []
    for year, label in EVENTS:
        source = compact_anom if year == 2026 else full_anom
        event = source.sel(time=(source.time.dt.year == year) & (source.time.dt.month.isin([4, 5]))).mean("time")
        event = event.expand_dims(event=[label])
        pieces.append(event)
    return xr.concat(pieces, dim="event")


def subset(da: xr.DataArray, lon_min: float, lon_max: float, lat_min: float = -30, lat_max: float = 30) -> xr.DataArray:
    return da.sel(lon=slice(lon_min, lon_max), lat=slice(lat_min, lat_max))


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.16)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.16)
    print(png)
    print(pdf)


def plot_sst_precip(sst: xr.DataArray, precip: xr.DataArray) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12.8, 9.1), constrained_layout=True)
    fig.suptitle("Apr-May spatial anomalies: 2026 versus 2023/24 and 2015/16", weight="bold")

    for r, (_year, label) in enumerate(EVENTS):
        sst_event = subset(sst.sel(event=label), 40, 320)
        pr_event = subset(precip.sel(event=label), 120, 280)

        ax = axes[r, 0]
        mesh_sst = ax.pcolormesh(
            sst_event.lon,
            sst_event.lat,
            sst_event,
            cmap="RdBu_r",
            vmin=-2.5,
            vmax=2.5,
            shading="auto",
        )
        ax.set_title(f"{label} Apr-May OISST SST anomaly")
        ax.set_xlim(40, 320)
        ax.set_ylim(-30, 30)
        format_map_axes(ax, [40, 80, 120, 160, 200, 240, 280, 320])
        add_boxes(ax, SST_BOXES, 40, 320)

        ax = axes[r, 1]
        mesh_pr = ax.pcolormesh(
            pr_event.lon,
            pr_event.lat,
            pr_event,
            cmap="BrBG",
            vmin=-5,
            vmax=5,
            shading="auto",
        )
        ax.set_title(f"{label} Apr-May GPCP precipitation anomaly")
        ax.set_xlim(120, 280)
        ax.set_ylim(-30, 30)
        format_map_axes(ax, [120, 160, 200, 240, 280])
        add_boxes(ax, PACIFIC_BOXES, 120, 280)

    fig.colorbar(mesh_sst, ax=axes[:, 0], label="SST anomaly (deg C)", shrink=0.88)
    fig.colorbar(mesh_pr, ax=axes[:, 1], label="Precipitation anomaly (mm/day)", shrink=0.88)
    fig.text(
        0.01,
        -0.012,
        "Data: NOAA OISST v2.1 and GPCP monthly precipitation via NOAA PSL THREDDS NCSS. "
        "Anomalies use 1982-2022 same-calendar-month climatology; maps use Apr-May of each event developing year.",
        fontsize=8.3,
        color="0.28",
    )
    save(fig, "fig13_event_aligned_sst_precip_spatial_apr_may")
    plt.close(fig)


def plot_era5(era5: xr.Dataset) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12.6, 8.7), constrained_layout=True)
    fig.suptitle("Apr-May ERA5 spatial anomalies: low-level wind and pressure comparison", weight="bold")

    for r, (_year, label) in enumerate(EVENTS):
        event = era5.sel(event=label)
        u10 = subset(event["u10"], 120, 280)
        msl = subset(event["msl_hpa"], 120, 280)

        ax = axes[r, 0]
        mesh_u = ax.pcolormesh(u10.lon, u10.lat, u10, cmap="RdBu_r", vmin=-3, vmax=3, shading="auto")
        ax.set_title(f"{label} Apr-May ERA5 u10 anomaly")
        ax.set_xlim(120, 280)
        ax.set_ylim(-30, 30)
        format_map_axes(ax, [120, 160, 200, 240, 280])
        add_boxes(ax, WIND_BOXES, 120, 280)

        ax = axes[r, 1]
        mesh_p = ax.pcolormesh(msl.lon, msl.lat, msl, cmap="RdBu_r", vmin=-3, vmax=3, shading="auto")
        ax.set_title(f"{label} Apr-May ERA5 mean sea-level pressure anomaly")
        ax.set_xlim(120, 280)
        ax.set_ylim(-30, 30)
        format_map_axes(ax, [120, 160, 200, 240, 280])
        add_boxes(ax, WIND_BOXES, 120, 280)

    fig.colorbar(mesh_u, ax=axes[:, 0], label="u10 anomaly (m/s; positive = westerly)", shrink=0.88)
    fig.colorbar(mesh_p, ax=axes[:, 1], label="MSLP anomaly (hPa)", shrink=0.88)
    fig.text(
        0.01,
        -0.012,
        "Data: ERA5 monthly means from Copernicus CDS. 2015/2023 use the local 0.25-degree ERA5 archive sampled to 1 degree; "
        "2026 uses the compact 1-degree CDS subset. Anomalies use 1982-2022 same-calendar-month climatology.",
        fontsize=8.3,
        color="0.28",
    )
    save(fig, "fig14_event_aligned_era5_u10_mslp_spatial_apr_may")
    plt.close(fig)


def write_summary(sst: xr.DataArray, precip: xr.DataArray, era5: xr.Dataset) -> None:
    rows = []
    boxes = {
        "nino3_sst": ("sst", sst, (-5, 5, 210, 270), "deg C"),
        "fep_sst": ("sst", sst, (-5, 5, 270, 280), "deg C"),
        "cp_precip": ("precip", precip, (-5, 5, 180, 220), "mm/day"),
        "cwp_u10": ("u10", era5["u10"], (-5, 5, 160, 220), "m/s"),
        "soi_like_mslp": ("msl_hpa", era5["msl_hpa"], None, "hPa"),
    }
    for _year, label in EVENTS:
        for metric, (_var, da, region, unit) in boxes.items():
            if metric == "soi_like_mslp":
                tahiti = da.sel(event=label, lat=slice(-25, -10), lon=slice(200, 220)).mean().item()
                darwin = da.sel(event=label, lat=slice(-20, -5), lon=slice(120, 140)).mean().item()
                value = tahiti - darwin
            else:
                lat0, lat1, lon0, lon1 = region
                value = da.sel(event=label, lat=slice(lat0, lat1), lon=slice(lon0, lon1)).mean().item()
            rows.append((label, metric, value, unit))
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    path = DERIVED_DIR / "event_aligned_spatial_apr_may_summary.csv"
    with path.open("w", encoding="utf-8") as f:
        f.write("event,metric,value,unit\n")
        for row in rows:
            f.write(f"{row[0]},{row[1]},{row[2]:.6f},{row[3]}\n")
    print(path)


def main() -> int:
    setup_style()
    sst = apr_may_anomaly_from_two_month_files(OISST_APR, OISST_MAY, "sst")
    precip = apr_may_anomaly_from_monthly_file(GPCP, "precip")
    era5 = era5_apr_may_anomaly()
    plot_sst_precip(sst, precip)
    plot_era5(era5)
    write_summary(sst, precip, era5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
