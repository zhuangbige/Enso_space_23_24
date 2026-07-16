#!/usr/bin/env python3
"""Plot 2026 Jan-May monthly SSTA/precip/D20 with ERA5 850 hPa wind.

Requested methods:
- SST: NOAA OISST, monthly anomaly, linearly detrended.
- Wind: ERA5 850 hPa u/v, monthly anomaly, linearly detrended.
- Precipitation: ERA5 total precipitation, monthly anomaly, linearly detrended.
- D20: ORAS5 equatorial depth of 20 C isotherm time-series, monthly anomaly,
  linearly detrended.

The requested anomaly/trend reference is 1980-2025. ERA5 and ORAS5 use that
period directly. OISST v2.1 starts after 1980, so Jan-May OISST fields use the
available same-month years in 1982-2025 and record that caveat in the output
metadata.
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


INPUT_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
ERA5_WIND = ROOT / "data/raw/era5/era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc"
ERA5_PRECIP = ROOT / "data/raw/era5/era5_monthly_precip_tropics_1deg_1980_2026_jan_may.nc"
ORAS5_D20 = ROOT / "data/interim/research_2026/oras5_d20_timeseries_equatorial_1960_202605.csv"

OUT_DIR = ROOT / "outputs/research_2026/monthly_panels_1980_2025_detrended"
DERIVED_NPZ = INPUT_DIR / "monthly_2026_detrended_fields_1980_2025.npz"
D20_OUT_CSV = ROOT / "data/derived/research_2026/monthly_2026_oras5_d20_detrended_1980_2025.csv"

BASELINE_START = 1980
BASELINE_END = 2025
BASELINE_TAG = "1980_2025"
TARGET_YEAR = 2026
EVENT_LABEL = "2026"
RUN_STEM = "2026"
MONTHS = [1, 2, 3, 4, 5]
MONTH_LABELS = ["January", "February", "March", "April", "May"]
MONTH_TAGS = ["JAN", "FEB", "MAR", "APR", "MAY"]


@dataclass(frozen=True)
class Box:
    label: str
    lat0: float
    lat1: float
    lon0: float
    lon1: float


PACIFIC_BOXES = [
    Box("CWP", -5, 5, 160, 220),
    Box("CP", -5, 5, 180, 220),
    Box("EP", -5, 5, 220, 260),
    Box("FEP", -5, 5, 270, 280),
    Box("Nino-3.4", -5, 5, 190, 240),
    Box("Nino-3", -5, 5, 210, 270),
]


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.4,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.2,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "axes.linewidth": 0.82,
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
    return f"{abs(value):g}{'N' if value > 0 else 'S'}"


def format_map_axes(ax: plt.Axes) -> None:
    xticks = [120, 140, 160, 180, 200, 220, 240, 260, 280]
    yticks = [-30, -15, 0, 15, 30]
    ax.set_xlim(120, 280)
    ax.set_ylim(-30, 30)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(tick) for tick in xticks])
    ax.set_yticks(yticks)
    ax.set_yticklabels([format_lat(tick) for tick in yticks])
    ax.axhline(0, color="0.2", lw=0.55)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def add_boxes(ax: plt.Axes, *, include_nino: bool = True) -> None:
    for box in PACIFIC_BOXES:
        if not include_nino and box.label.startswith("Nino"):
            continue
        if box.lon1 < 120 or box.lon0 > 280:
            continue
        ax.plot(
            [box.lon0, box.lon1, box.lon1, box.lon0, box.lon0],
            [box.lat0, box.lat0, box.lat1, box.lat1, box.lat0],
            color="0.15",
            lw=0.65,
        )
        dx, dy = {
            "FEP": (-8.5, 1.0),
            "Nino-3": (16.0, -4.8),
            "Nino-3.4": (1.0, 1.0),
        }.get(box.label, (1.0, 1.0))
        y_anchor = box.lat1 if dy >= 0 else box.lat0
        ax.text(box.lon0 + dx, y_anchor + dy, box.label, fontsize=5.9, color="0.15")


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
        ds = ds.assign_coords(lon=(ds["lon"] % 360)).sortby("lon")
    if "lat" in ds.coords:
        ds = ds.sortby("lat")
    if "time" in ds.coords:
        monthly_time = pd.to_datetime(ds["time"].values).to_period("M").to_timestamp()
        ds = ds.assign_coords(time=monthly_time)
    return ds


def open_netcdf(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    try:
        return xr.open_dataset(path, engine="h5netcdf")
    except OSError:
        # NOAA PSL NCSS writes these small OISST subsets as NetCDF classic,
        # while CDS ERA5 files are NetCDF4/HDF5. Try both without relying on
        # the broken local netCDF4 backend.
        return xr.open_dataset(path, engine="scipy")


def configure_run(
    target_year: int,
    event_label: str | None,
    output_dir: str | None,
    baseline_start: int,
    baseline_end: int,
) -> None:
    global BASELINE_START, BASELINE_END, BASELINE_TAG, TARGET_YEAR, EVENT_LABEL, RUN_STEM, OUT_DIR, DERIVED_NPZ, D20_OUT_CSV

    BASELINE_START = int(baseline_start)
    BASELINE_END = int(baseline_end)
    BASELINE_TAG = f"{BASELINE_START}_{BASELINE_END}"
    TARGET_YEAR = int(target_year)
    EVENT_LABEL = event_label or str(TARGET_YEAR)
    RUN_STEM = str(TARGET_YEAR)
    if output_dir:
        OUT_DIR = ROOT / output_dir
    elif TARGET_YEAR == 2026 and BASELINE_TAG == "1980_2025":
        OUT_DIR = ROOT / "outputs/research_2026/monthly_panels_1980_2025_detrended"
    else:
        safe_label = EVENT_LABEL.lower().replace("/", "_").replace(" ", "_")
        OUT_DIR = ROOT / f"outputs/research_2026/event_{safe_label}_monthly_panels_{BASELINE_TAG}_detrended"
    DERIVED_NPZ = INPUT_DIR / f"monthly_{RUN_STEM}_detrended_fields_{BASELINE_TAG}.npz"
    D20_OUT_CSV = ROOT / f"data/derived/research_2026/monthly_{RUN_STEM}_oras5_d20_detrended_{BASELINE_TAG}.csv"


def require_months(da: xr.DataArray, name: str) -> None:
    for month, label in zip(MONTHS, MONTH_LABELS):
        has_target = bool(((da.time.dt.year == TARGET_YEAR) & (da.time.dt.month == month)).any())
        if not has_target:
            raise ValueError(f"{name} is missing {label} {TARGET_YEAR}")


def decimal_year(time_coord: xr.DataArray) -> np.ndarray:
    return time_coord.dt.year.values.astype(float) + (time_coord.dt.month.values.astype(float) - 0.5) / 12.0


def linear_detrend_grid(values: np.ndarray, time: np.ndarray, fit_mask: np.ndarray) -> np.ndarray:
    original_shape = values.shape
    flat = values.reshape(values.shape[0], -1).astype(float)
    x = time[fit_mask].astype(float)
    y = flat[fit_mask, :]
    valid = np.isfinite(y)
    count = valid.sum(axis=0).astype(float)
    x2 = x[:, None]
    sum_x = (x2 * valid).sum(axis=0)
    sum_y = np.where(valid, y, 0.0).sum(axis=0)
    mean_x = np.divide(sum_x, count, out=np.full_like(count, np.nan), where=count > 2)
    mean_y = np.divide(sum_y, count, out=np.full_like(count, np.nan), where=count > 2)
    dx = np.where(valid, x2 - mean_x, 0.0)
    dy = np.where(valid, y - mean_y, 0.0)
    denom = (dx * dx).sum(axis=0)
    numer = (dx * dy).sum(axis=0)
    slope = np.divide(numer, denom, out=np.full_like(denom, np.nan), where=denom > 0)
    intercept = mean_y - slope * mean_x
    trend = time[:, None] * slope[None, :] + intercept[None, :]
    out = flat - trend
    out[:, count <= 2] = np.nan
    return out.reshape(original_shape)


def detrended_monthly_target(da: xr.DataArray, *, name: str, baseline_start: int, baseline_end: int) -> tuple[np.ndarray, str]:
    """Return target-year Jan-May anomalies after same-month linear detrending."""
    require_months(da, name)
    pieces: list[np.ndarray] = []
    baseline_notes: list[str] = []
    for month in MONTHS:
        monthly = da.where(da.time.dt.month == month, drop=True).sortby("time")
        years = monthly.time.dt.year.values.astype(int)
        fit_mask = (years >= baseline_start) & (years <= baseline_end)
        if fit_mask.sum() < 10:
            raise ValueError(f"{name} has too few baseline years for month={month}: {fit_mask.sum()}")
        target_mask = years == TARGET_YEAR
        if target_mask.sum() != 1:
            raise ValueError(f"{name} expected one target record for {TARGET_YEAR}-{month:02d}, found {target_mask.sum()}")
        clim = monthly.isel(time=np.where(fit_mask)[0]).mean("time", skipna=True)
        anom = monthly - clim
        arr = anom.transpose("time", "lat", "lon").values
        det = linear_detrend_grid(arr, decimal_year(monthly.time), fit_mask)
        pieces.append(det[np.where(target_mask)[0][0]].astype(np.float32))
        baseline_notes.append(f"{int(years[fit_mask].min())}-{int(years[fit_mask].max())}")
    return np.stack(pieces, axis=0), ", ".join(sorted(set(baseline_notes)))


def oisst_path(month: int) -> Path:
    tag = ["jan", "feb", "mar", "apr", "may"][month - 1]
    return INPUT_DIR / f"oisst_sst_tropics_1deg_{tag}_1982_2026.nc"


def open_oisst() -> xr.DataArray:
    arrays = []
    fallback = {
        4: ROOT / "data/interim/research_2026/oisst_event_spatial_tropics_apr_1982_2026_1deg.nc",
        5: ROOT / "data/interim/research_2026/oisst_event_spatial_tropics_may_1982_2026_1deg.nc",
    }
    for month in MONTHS:
        path = oisst_path(month)
        if not path.exists() and month in fallback and fallback[month].exists():
            path = fallback[month]
        ds = standardize(open_netcdf(path))
        arrays.append(ds["sst"])
    da = xr.concat(arrays, dim="time").sortby("time")
    da = da.sel(lat=slice(-30, 30), lon=slice(120, 280))
    return da


def open_era5() -> xr.Dataset:
    wind = standardize(open_netcdf(ERA5_WIND))
    precip = standardize(open_netcdf(ERA5_PRECIP))
    if "pressure_level" in wind.dims:
        wind = wind.sel(pressure_level=850).drop_vars("pressure_level")
    rename = {}
    if "u" in wind:
        rename["u"] = "u850"
    if "v" in wind:
        rename["v"] = "v850"
    wind = wind.rename(rename)
    if "tp" not in precip:
        raise ValueError(f"ERA5 precipitation file has no `tp`: {list(precip.data_vars)}")
    precip = precip.rename({"tp": "precip_mm_day"})
    precip["precip_mm_day"] = precip["precip_mm_day"] * 1000.0
    ds = xr.merge([wind[["u850", "v850"]], precip[["precip_mm_day"]]], compat="override")
    ds = ds.sel(lat=slice(-30, 30), lon=slice(120, 280))
    return ds


def build_fields() -> dict[str, object]:
    sst_da = open_oisst()
    era5 = open_era5()
    sst, sst_baseline = detrended_monthly_target(
        sst_da, name="OISST SST", baseline_start=BASELINE_START, baseline_end=BASELINE_END
    )
    u850, era5_baseline = detrended_monthly_target(
        era5["u850"], name="ERA5 u850", baseline_start=BASELINE_START, baseline_end=BASELINE_END
    )
    v850, _ = detrended_monthly_target(
        era5["v850"], name="ERA5 v850", baseline_start=BASELINE_START, baseline_end=BASELINE_END
    )
    precip, _ = detrended_monthly_target(
        era5["precip_mm_day"], name="ERA5 precipitation", baseline_start=BASELINE_START, baseline_end=BASELINE_END
    )
    d20_df = build_d20_fields()
    d20_lons = np.sort(d20_df["lon"].unique()).astype(float)
    d20 = (
        d20_df.pivot(index="month", columns="lon", values="d20_detrended_anomaly_m")
        .reindex(index=MONTHS, columns=d20_lons)
        .to_numpy(dtype=np.float32)
    )

    lon = era5.lon.values.astype(np.float32)
    lat = era5.lat.values.astype(np.float32)
    sst_lon = sst_da.lon.values.astype(np.float32)
    sst_lat = sst_da.lat.values.astype(np.float32)
    output: dict[str, object] = {
        "months": np.asarray(MONTH_LABELS),
        "month_numbers": np.asarray(MONTHS),
        "lat": lat,
        "lon": lon,
        "sst_lat": sst_lat,
        "sst_lon": sst_lon,
        "sst": sst,
        "u850": u850,
        "v850": v850,
        "precip": precip,
        "d20_lon": d20_lons.astype(np.float32),
        "d20": d20,
        "sst_baseline_used": np.asarray(sst_baseline),
        "era5_baseline_used": np.asarray(era5_baseline),
        "d20_baseline_used": np.asarray(f"{BASELINE_START}-{BASELINE_END}"),
        "method": np.asarray(
            "Monthly anomalies relative to same-month climatology, then linear trend over the baseline years removed."
        ),
    }
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DERIVED_NPZ, **output)
    return output


def build_d20_fields() -> pd.DataFrame:
    if not ORAS5_D20.exists():
        raise FileNotFoundError(f"Missing ORAS5 D20 input: {ORAS5_D20}")
    raw = pd.read_csv(ORAS5_D20, parse_dates=["time"])
    raw = raw.loc[
        ((raw["product_type"].eq("consolidated")) & (raw["year"] <= 2014))
        | ((raw["product_type"].eq("operational")) & (raw["year"] >= 2015))
    ].copy()
    raw = raw.loc[raw["d20_m"].notna()].copy()
    raw["lon"] = raw["requested_lon"].astype(float)

    rows: list[dict[str, object]] = []
    for (lon, month), group in raw.groupby(["lon", "month"]):
        if int(month) not in MONTHS:
            continue
        group = group.sort_values("time")
        base = group["year"].between(BASELINE_START, BASELINE_END)
        target = group["year"].eq(TARGET_YEAR)
        if base.sum() < 10 or target.sum() != 1:
            continue
        clim = float(group.loc[base, "d20_m"].mean())
        anomaly = group["d20_m"].to_numpy(dtype=float) - clim
        time = group["year"].to_numpy(dtype=float) + (group["month"].to_numpy(dtype=float) - 0.5) / 12.0
        x = time[base.to_numpy()]
        y = anomaly[base.to_numpy()]
        valid = np.isfinite(y)
        if valid.sum() < 10:
            continue
        slope, intercept = np.polyfit(x[valid], y[valid], 1)
        target_idx = np.where(target.to_numpy())[0][0]
        det = float(anomaly[target_idx] - (slope * time[target_idx] + intercept))
        rows.append(
            {
                "year": TARGET_YEAR,
                "month": int(month),
                "month_label": MONTH_LABELS[int(month) - 1],
                "lon": float(lon),
                "d20_detrended_anomaly_m": det,
                "d20_raw_anomaly_m": float(anomaly[target_idx]),
                "baseline_years": f"{BASELINE_START}-{BASELINE_END}",
                "n_baseline_years": int(base.sum()),
                "linear_trend_slope_m_per_year": float(slope),
                "source": "CDS ORAS5 time-series depth_of_20_c_isotherm along 0 degree latitude",
            }
        )
    out = pd.DataFrame(rows).sort_values(["month", "lon"])
    missing = set(MONTHS) - set(out["month"].unique())
    if missing:
        raise ValueError(f"ORAS5 D20 missing target months: {sorted(missing)}")
    D20_OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(D20_OUT_CSV, index=False)
    return out


def weighted_equatorial_mean(field: np.ndarray, lat: np.ndarray) -> np.ndarray:
    idx = np.where((lat >= -5) & (lat <= 5))[0]
    weights = np.cos(np.deg2rad(lat[idx])).astype(float)
    arr = field[:, idx, :]
    return np.average(arr, axis=1, weights=weights)


def interp_monthly_to_lons(field: np.ndarray, src_lon: np.ndarray, dst_lon: np.ndarray) -> np.ndarray:
    out = []
    for row in field:
        out.append(np.interp(dst_lon, src_lon, row))
    return np.asarray(out)


def add_vectors(ax: plt.Axes, lon: np.ndarray, lat: np.ndarray, u: np.ndarray, v: np.ndarray, *, key: bool) -> None:
    q = ax.quiver(
        lon[::5],
        lat[::3],
        u[::3, ::5],
        v[::3, ::5],
        color="0.1",
        pivot="middle",
        width=0.0027,
        headwidth=3.2,
        scale=52,
    )
    if key:
        ax.quiverkey(q, 0.84, 0.93, 4, "4 m/s", labelpos="E", coordinates="axes", fontproperties={"size": 7.5})


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.16)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.16)
    print(png)
    print(pdf)


def plot_monthly_map_group(
    fields: dict[str, object],
    *,
    variable: str,
    title: str,
    cmap: str,
    vmin: float,
    vmax: float,
    colorbar_label: str,
    stem: str,
) -> None:
    lon = np.asarray(fields["lon"], dtype=float)
    lat = np.asarray(fields["lat"], dtype=float)
    u = np.asarray(fields["u850"], dtype=float)
    v = np.asarray(fields["v850"], dtype=float)
    if variable == "sst":
        xlon = np.asarray(fields["sst_lon"], dtype=float)
        ylat = np.asarray(fields["sst_lat"], dtype=float)
    else:
        xlon = lon
        ylat = lat
    data = np.asarray(fields[variable], dtype=float)

    fig, axes = plt.subplots(2, 3, figsize=(14.2, 7.4), constrained_layout=True)
    fig.suptitle(title, weight="bold")
    axes_flat = axes.ravel()
    mesh = None
    for i, label in enumerate(MONTH_LABELS):
        ax = axes_flat[i]
        mesh = ax.pcolormesh(xlon, ylat, data[i], cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
        add_vectors(ax, lon, lat, u[i], v[i], key=(i == 1))
        format_map_axes(ax)
        add_boxes(ax, include_nino=variable == "sst")
        ax.set_title(f"{label} {TARGET_YEAR}")
    axes_flat[-1].axis("off")
    axes_flat[-1].text(
        0.0,
        0.82,
        "Method\n"
        "- Same-month climatology\n"
        "- Linear trend removed\n"
        "- Wind: ERA5 850 hPa\n"
        "- Region: 120E-80W, 30S-30N",
        fontsize=9,
        color="0.25",
        va="top",
    )
    assert mesh is not None
    fig.colorbar(mesh, ax=axes[:, :], label=colorbar_label, shrink=0.88, pad=0.015)
    if variable == "sst":
        note = (
            f"ERA5 wind baseline: {fields['era5_baseline_used']}. "
            f"OISST baseline: {fields['sst_baseline_used']} because OISST does not cover 1980-1981 same-month fields. "
            "All panels are monthly detrended anomalies."
        )
    else:
        note = (
            f"ERA5 precipitation/wind baseline: {fields['era5_baseline_used']}. "
            "All panels are monthly detrended anomalies."
        )
    fig.text(0.01, -0.01, note, fontsize=8.4, color="0.30")
    save(fig, stem)
    plt.close(fig)


def plot_d20_wind(fields: dict[str, object]) -> None:
    lon = np.asarray(fields["lon"], dtype=float)
    lat = np.asarray(fields["lat"], dtype=float)
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    d20 = np.asarray(fields["d20"], dtype=float)
    u_eq = weighted_equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
    u_eq_on_d20 = interp_monthly_to_lons(u_eq, lon, d20_lon)
    d20_lim = max(30.0, float(np.ceil(np.nanmax(np.abs(d20)) / 5.0) * 5.0))
    wind_lim = max(5.5, float(np.ceil(np.nanmax(np.abs(u_eq_on_d20)) * 1.12)))

    fig, axes = plt.subplots(5, 1, figsize=(12.4, 9.2), sharex=True, constrained_layout=True)
    fig.suptitle(
        f"{EVENT_LABEL} monthly ORAS5 equatorial D20 anomaly with ERA5 850 hPa zonal wind",
        weight="bold",
    )
    for i, (ax, label) in enumerate(zip(axes, MONTH_LABELS)):
        colors = np.where(d20[i] >= 0, "#b74134", "#2f6fab")
        ax.bar(d20_lon, d20[i], width=4.0, color=colors, alpha=0.72, edgecolor="none")
        ax.axhline(0, color="0.25", lw=0.8)
        ax.set_ylim(-d20_lim, d20_lim)
        ax.set_ylabel("D20 (m)")
        ax.set_title(f"{label} {TARGET_YEAR}", loc="left")
        ax2 = ax.twinx()
        ax2.plot(d20_lon, u_eq_on_d20[i], color="0.08", lw=1.35)
        ax2.fill_between(d20_lon, 0, u_eq_on_d20[i], color="0.08", alpha=0.10)
        ax2.axhline(0, color="0.45", lw=0.55, ls="--")
        ax2.set_ylim(-wind_lim, wind_lim)
        ax2.set_ylabel("u850 (m/s)")
        for x, text in [(160, "CWP"), (180, "Date line"), (220, "CP"), (260, "EP"), (275, "FEP")]:
            ax.axvline(x, color="0.3", lw=0.5, ls="--")
            if i == 0:
                ax.text(x + 1, 23.0, text, fontsize=7, color="0.28")
    axes[-1].set_xlim(130, 275)
    ticks = [130, 150, 170, 180, 200, 220, 240, 260, 275]
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels([format_lon(tick) for tick in ticks])
    axes[-1].set_xlabel("Longitude along equator")
    fig.text(
        0.01,
        -0.01,
        f"D20: ORAS5 time-series nearest native-grid points along 0° latitude, detrended against {BASELINE_START}-{BASELINE_END}. "
        f"Wind: ERA5 u850 averaged over 5S-5N, same detrending method. Positive u850 is westerly; positive D20 is deeper thermocline.",
        fontsize=8.4,
        color="0.30",
    )
    save(fig, f"fig_{RUN_STEM}_monthly_d20_u850_detrended_{BASELINE_TAG}")
    plt.close(fig)


def write_manifest(fields: dict[str, object]) -> None:
    rows = [
        {
            "output": str(DERIVED_NPZ),
            "description": f"Compiled {TARGET_YEAR} Jan-May detrended fields for monthly panel plots.",
            "baseline": f"ERA5/ORAS5 {BASELINE_START}-{BASELINE_END}; OISST effective {fields['sst_baseline_used']}",
        },
        {
            "output": str(D20_OUT_CSV),
            "description": f"ORAS5 equatorial D20 monthly detrended anomalies for Jan-May {TARGET_YEAR}.",
            "baseline": f"{BASELINE_START}-{BASELINE_END}",
        },
        {
            "output": str(OUT_DIR / f"fig_{RUN_STEM}_monthly_ssta_u850_detrended_{BASELINE_TAG}.png"),
            "description": "OISST SSTA + ERA5 u/v850 wind monthly panels.",
            "baseline": f"monthly climatology plus linear detrending; OISST effective {fields['sst_baseline_used']}",
        },
        {
            "output": str(OUT_DIR / f"fig_{RUN_STEM}_monthly_era5_precip_u850_detrended_{BASELINE_TAG}.png"),
            "description": "ERA5 precipitation + ERA5 u/v850 wind monthly panels.",
            "baseline": f"{BASELINE_START}-{BASELINE_END}",
        },
        {
            "output": str(OUT_DIR / f"fig_{RUN_STEM}_monthly_d20_u850_detrended_{BASELINE_TAG}.png"),
            "description": "ORAS5 equatorial D20 + ERA5 equatorial u850 monthly panels.",
            "baseline": f"{BASELINE_START}-{BASELINE_END}",
        },
    ]
    manifest = OUT_DIR / "manifest.csv"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot Jan-May monthly SSTA/precip/D20 + ERA5 u850 panels.")
    parser.add_argument("--target-year", type=int, default=2026)
    parser.add_argument("--event-label", default=None, help="Label used in figure titles and output directory.")
    parser.add_argument("--baseline-start", type=int, default=1980)
    parser.add_argument("--baseline-end", type=int, default=2025)
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory relative to repository root. Defaults to the original 2026 directory or an event-specific directory.",
    )
    args = parser.parse_args()
    configure_run(args.target_year, args.event_label, args.output_dir, args.baseline_start, args.baseline_end)

    setup_style()
    fields = build_fields()
    plot_monthly_map_group(
        fields,
        variable="sst",
        title=f"{EVENT_LABEL} monthly OISST SSTA with ERA5 850 hPa wind anomalies",
        cmap="RdBu_r",
        vmin=-2.5,
        vmax=2.5,
        colorbar_label="OISST SST anomaly (degC)",
        stem=f"fig_{RUN_STEM}_monthly_ssta_u850_detrended_{BASELINE_TAG}",
    )
    plot_monthly_map_group(
        fields,
        variable="precip",
        title=f"{EVENT_LABEL} monthly ERA5 precipitation with ERA5 850 hPa wind anomalies",
        cmap="BrBG",
        vmin=-5.0,
        vmax=5.0,
        colorbar_label="ERA5 precipitation anomaly (mm/day)",
        stem=f"fig_{RUN_STEM}_monthly_era5_precip_u850_detrended_{BASELINE_TAG}",
    )
    plot_d20_wind(fields)
    write_manifest(fields)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
