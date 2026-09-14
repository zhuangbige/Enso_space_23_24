#!/usr/bin/env python3
"""Build a local PMM-like index from OISST SST and ERA5 10 m wind EOFs.

This is a diagnostic PMM/NPMM-style product for the current project, not a
verbatim reproduction of the NOAA PMM index. To prevent the leading mode over
the tropical Pacific window from collapsing into ENSO, the script removes the
linear Niño-3.4 SST signal from SST, u10, and v10 anomalies before EOF analysis.
"""

from __future__ import annotations

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
from matplotlib.patches import Rectangle


INPUT = ROOT / "data/interim/research_2026/pmm_inputs"
ERA5_HISTORY = ROOT / "data/raw/era5/era5_monthly_10m_wind_pmm_1deg_1982_2025.nc"
ERA5_CURRENT = ROOT / "data/raw/era5/era5_monthly_10m_wind_pmm_1deg_2026_jan_may.nc"
OUT_DIR = ROOT / "outputs/research_2026/pmm_index"
DERIVED_DIR = ROOT / "data/derived/research_2026"
FIELDS_NPZ = ROOT / "data/interim/research_2026/pmm_inputs/pmm_eof_fields_1982_2025.npz"
INDEX_CSV = DERIVED_DIR / "pmm_like_index_oisst_era5_1982_2026.csv"
MANIFEST = OUT_DIR / "manifest.csv"

BASELINE_START = 1982
BASELINE_END = 2025
CURRENT_YEAR = 2026

LON_MIN = 120.0
LON_MAX = 280.0
LAT_MIN = -20.0
LAT_MAX = 30.0


@dataclass(frozen=True)
class Box:
    label: str
    lat0: float
    lat1: float
    lon0: float
    lon1: float


BOXES = [
    Box("PMM+", 10, 25, 200, 250),
    Box("Nino-3.4", -5, 5, 190, 240),
    Box("CWP", -5, 5, 160, 220),
    Box("FEP", -5, 5, 270, 280),
]


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 10.8,
            "axes.titlesize": 12.0,
            "axes.labelsize": 10.8,
            "xtick.labelsize": 9.6,
            "ytick.labelsize": 9.6,
            "legend.fontsize": 9.4,
            "axes.linewidth": 0.82,
            "axes.unicode_minus": False,
        }
    )


def open_netcdf(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return xr.open_dataset(path, engine="h5netcdf")
    except OSError:
        return xr.open_dataset(path, engine="scipy")


def standardize(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    if "valid_time" in ds.coords:
        rename["valid_time"] = "time"
    if "latitude" in ds.coords:
        rename["latitude"] = "lat"
    if "longitude" in ds.coords:
        rename["longitude"] = "lon"
    ds = ds.rename(rename)
    if "time" in ds.coords:
        ds = ds.assign_coords(time=pd.to_datetime(ds.time.values).to_period("M").to_timestamp())
    if "lon" in ds.coords:
        ds = ds.assign_coords(lon=(ds.lon % 360)).sortby("lon")
    if "lat" in ds.coords:
        ds = ds.sortby("lat")
    return ds


def format_lon(value: float) -> str:
    lon = value % 360
    if np.isclose(lon, 180):
        return "180"
    if lon < 180:
        return f"{lon:g}E"
    return f"{360 - lon:g}W"


def format_lat(value: float) -> str:
    if np.isclose(value, 0):
        return "Eq"
    return f"{abs(value):g}{'N' if value > 0 else 'S'}"


def format_axes(ax: plt.Axes) -> None:
    xticks = [120, 140, 160, 180, 200, 220, 240, 260, 280]
    yticks = [-20, -10, 0, 10, 20, 30]
    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(LAT_MIN, LAT_MAX)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(t) for t in xticks])
    ax.set_yticks(yticks)
    ax.set_yticklabels([format_lat(t) for t in yticks])
    ax.axhline(0, color="0.2", lw=0.55)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def add_boxes(ax: plt.Axes) -> None:
    for box in BOXES:
        ax.plot(
            [box.lon0, box.lon1, box.lon1, box.lon0, box.lon0],
            [box.lat0, box.lat0, box.lat1, box.lat1, box.lat0],
            color="0.15",
            lw=0.7,
        )
        ax.text(box.lon0 + 1.0, box.lat1 + 0.9, box.label, fontsize=6.2, color="0.15")


def load_sst() -> xr.DataArray:
    pieces: list[xr.DataArray] = []
    for path in sorted(INPUT.glob("oisst_sst_pmm_1deg_*.nc")):
        ds = standardize(open_netcdf(path))
        if "sst" not in ds:
            raise ValueError(f"Missing `sst` in {path}")
        pieces.append(ds["sst"])
    if len(pieces) != 12:
        raise ValueError(f"Expected 12 OISST monthly files, found {len(pieces)}")
    sst = xr.concat(pieces, dim="time").sortby("time")
    return sst.sel(lat=slice(LAT_MIN, LAT_MAX), lon=slice(LON_MIN, LON_MAX))


def load_wind(target_lat: xr.DataArray, target_lon: xr.DataArray) -> xr.Dataset:
    hist = standardize(open_netcdf(ERA5_HISTORY))
    current = standardize(open_netcdf(ERA5_CURRENT))
    ds = xr.concat([hist, current], dim="time").sortby("time")
    rename = {}
    if "u10" not in ds and "u" in ds:
        rename["u"] = "u10"
    if "v10" not in ds and "v" in ds:
        rename["v"] = "v10"
    ds = ds.rename(rename)
    ds = ds[["u10", "v10"]].sel(lat=slice(LAT_MIN, LAT_MAX), lon=slice(LON_MIN, LON_MAX))
    return ds.interp(lat=target_lat, lon=target_lon)


def decimal_year(time: xr.DataArray) -> np.ndarray:
    return time.dt.year.values.astype(float) + (time.dt.month.values.astype(float) - 0.5) / 12.0


def detrend_grid(values: np.ndarray, time: np.ndarray, fit_mask: np.ndarray) -> np.ndarray:
    shape = values.shape
    flat = values.reshape(values.shape[0], -1).astype(float)
    x = time[fit_mask]
    y = flat[fit_mask]
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
    return out.reshape(shape)


def monthly_anomaly_detrend(da: xr.DataArray, train_mask: np.ndarray) -> xr.DataArray:
    climatology = da.isel(time=np.where(train_mask)[0]).groupby("time.month").mean("time", skipna=True)
    anom = da.groupby("time.month") - climatology
    arr = anom.transpose("time", "lat", "lon").values
    det = detrend_grid(arr, decimal_year(anom.time), train_mask)
    return xr.DataArray(det.astype(np.float32), coords=anom.transpose("time", "lat", "lon").coords, dims=("time", "lat", "lon"))


def area_mean(da: xr.DataArray, *, lat0: float, lat1: float, lon0: float, lon1: float) -> xr.DataArray:
    sub = da.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    weights = np.cos(np.deg2rad(sub.lat))
    return sub.weighted(weights).mean(("lat", "lon"), skipna=True)


def remove_linear_index(da: xr.DataArray, index: xr.DataArray, train_mask: np.ndarray) -> xr.DataArray:
    x = index.values.astype(float)
    y = da.transpose("time", "lat", "lon").values.astype(float)
    flat = y.reshape(y.shape[0], -1)
    xt = x[train_mask]
    yt = flat[train_mask]
    valid = np.isfinite(yt) & np.isfinite(xt[:, None])
    denom = np.where(valid, xt[:, None] ** 2, 0.0).sum(axis=0)
    numer = np.where(valid, yt * xt[:, None], 0.0).sum(axis=0)
    beta = np.divide(numer, denom, out=np.zeros_like(denom), where=denom > 0)
    resid = flat - x[:, None] * beta[None, :]
    resid[:, denom == 0] = np.nan
    resid = resid.reshape(y.shape)
    return xr.DataArray(resid.astype(np.float32), coords=da.transpose("time", "lat", "lon").coords, dims=("time", "lat", "lon"))


def build_matrix(fields: list[xr.DataArray], train_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], list[float]]:
    lat = fields[0].lat.values.astype(float)
    weights = np.sqrt(np.cos(np.deg2rad(lat)))[:, None]
    matrices = []
    masks = []
    stds = []
    for da in fields:
        arr = da.transpose("time", "lat", "lon").values.astype(float)
        valid = np.isfinite(arr[train_mask]).all(axis=0)
        std = float(np.nanstd(arr[train_mask][:, valid]))
        weight_grid = np.broadcast_to(weights, arr.shape[1:])
        weighted = (arr[:, valid] * weight_grid[valid][None, :]).astype(float)
        matrix = weighted / std
        train_mean = np.nanmean(matrix[train_mask], axis=0)
        matrix = matrix - train_mean[None, :]
        matrices.append(matrix)
        masks.append(valid)
        stds.append(std)
    x_all = np.concatenate(matrices, axis=1)
    x_train = x_all[train_mask]
    return x_all, x_train, masks, stds


def eof_from_matrix(x_all: np.ndarray, x_train: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    u, s, vt = np.linalg.svd(x_train, full_matrices=False)
    eof = vt[0]
    pc_train = u[:, 0] * s[0]
    pc_all = x_all @ eof
    mean = pc_train.mean()
    std = pc_train.std(ddof=1)
    return eof, (pc_all - mean) / std, float((s[0] ** 2) / np.sum(s**2))


def regression_pattern(da: xr.DataArray, pc: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    arr = da.transpose("time", "lat", "lon").values.astype(float)
    flat = arr.reshape(arr.shape[0], -1)
    x = pc[train_mask].astype(float)
    y = flat[train_mask]
    valid = np.isfinite(y)
    denom = np.where(valid, x[:, None] ** 2, 0.0).sum(axis=0)
    numer = np.where(valid, y * x[:, None], 0.0).sum(axis=0)
    beta = np.divide(numer, denom, out=np.full_like(denom, np.nan), where=denom > 0)
    return beta.reshape(arr.shape[1:]).astype(np.float32)


def orient_positive_ne_pacific(pc: np.ndarray, pattern_sst: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, int]:
    lat_mask = (lat >= 10) & (lat <= 25)
    lon_mask = (lon >= 200) & (lon <= 250)
    val = np.nanmean(pattern_sst[np.ix_(lat_mask, lon_mask)])
    sign = 1 if val >= 0 else -1
    return pc * sign, sign


def compute() -> dict[str, object]:
    sst_raw = load_sst()
    wind_raw = load_wind(sst_raw.lat, sst_raw.lon)
    common_time = np.intersect1d(sst_raw.time.values, wind_raw.time.values)
    sst_raw = sst_raw.sel(time=common_time)
    wind_raw = wind_raw.sel(time=common_time)
    train_mask = (sst_raw.time.dt.year.values >= BASELINE_START) & (sst_raw.time.dt.year.values <= BASELINE_END)
    if train_mask.sum() != 44 * 12:
        raise ValueError(f"Expected 528 training months, found {train_mask.sum()}")

    sst = monthly_anomaly_detrend(sst_raw, train_mask)
    u10 = monthly_anomaly_detrend(wind_raw["u10"], train_mask)
    v10 = monthly_anomaly_detrend(wind_raw["v10"], train_mask)
    nino34 = area_mean(sst, lat0=-5, lat1=5, lon0=190, lon1=240)
    sst_res = remove_linear_index(sst, nino34, train_mask)
    u10_res = remove_linear_index(u10, nino34, train_mask)
    v10_res = remove_linear_index(v10, nino34, train_mask)

    x_all, x_train, _, _ = build_matrix([sst_res, u10_res, v10_res], train_mask)
    _, pc_joint, variance_joint = eof_from_matrix(x_all, x_train)
    sst_joint = regression_pattern(sst_res, pc_joint, train_mask)
    u_joint = regression_pattern(u10_res, pc_joint, train_mask)
    v_joint = regression_pattern(v10_res, pc_joint, train_mask)
    pc_joint, sign_joint = orient_positive_ne_pacific(pc_joint, sst_joint, sst_raw.lat.values, sst_raw.lon.values)
    sst_joint *= sign_joint
    u_joint *= sign_joint
    v_joint *= sign_joint

    x_all_sst, x_train_sst, _, _ = build_matrix([sst_res], train_mask)
    _, pc_sst, variance_sst = eof_from_matrix(x_all_sst, x_train_sst)
    sst_only = regression_pattern(sst_res, pc_sst, train_mask)
    pc_sst, sign_sst = orient_positive_ne_pacific(pc_sst, sst_only, sst_raw.lat.values, sst_raw.lon.values)
    sst_only *= sign_sst

    out = {
        "time": pd.to_datetime(sst_raw.time.values),
        "lat": sst_raw.lat.values.astype(np.float32),
        "lon": sst_raw.lon.values.astype(np.float32),
        "pc_joint": pc_joint.astype(np.float32),
        "pc_sst": pc_sst.astype(np.float32),
        "nino34_removed_index": nino34.values.astype(np.float32),
        "sst_joint": sst_joint,
        "u_joint": u_joint,
        "v_joint": v_joint,
        "sst_only": sst_only,
        "variance_joint": variance_joint,
        "variance_sst": variance_sst,
    }
    FIELDS_NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        FIELDS_NPZ,
        time=np.asarray(out["time"], dtype="datetime64[ns]"),
        lat=out["lat"],
        lon=out["lon"],
        pc_joint=out["pc_joint"],
        pc_sst=out["pc_sst"],
        nino34_removed_index=out["nino34_removed_index"],
        sst_joint=out["sst_joint"],
        u_joint=out["u_joint"],
        v_joint=out["v_joint"],
        sst_only=out["sst_only"],
        variance_joint=np.asarray(variance_joint),
        variance_sst=np.asarray(variance_sst),
        method=np.asarray("Monthly anomalies, linear detrending, and linear Niño-3.4 removal before EOF."),
    )
    write_index(out)
    return out


def write_index(out: dict[str, object]) -> None:
    rows = []
    for t, pcj, pcs, n34 in zip(out["time"], out["pc_joint"], out["pc_sst"], out["nino34_removed_index"]):
        timestamp = pd.Timestamp(t)
        rows.append(
            {
                "time": timestamp.strftime("%Y-%m-%d"),
                "year": timestamp.year,
                "month": timestamp.month,
                "pmm_joint_sst_wind": float(pcj),
                "pmm_sst_only": float(pcs),
                "nino34_detrended_anomaly_used_for_removal": float(n34),
                "unit": "standardized index",
                "method": "OISST SST + ERA5 10m wind EOF; monthly anomalies detrended; linear Nino-3.4 signal removed.",
            }
        )
    INDEX_CSV.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(INDEX_CSV)


def add_vectors(ax: plt.Axes, lon: np.ndarray, lat: np.ndarray, u: np.ndarray, v: np.ndarray) -> None:
    q = ax.quiver(
        lon[::5],
        lat[::3],
        u[::3, ::5],
        v[::3, ::5],
        color="0.1",
        pivot="middle",
        width=0.0026,
        headwidth=3.0,
        scale=9,
    )
    # Match the monthly map convention: whiten a compact lower-right area,
    # then draw the reference arrow and its magnitude inside the panel.
    ax.add_patch(
        Rectangle(
            (0.79, 0.015),
            0.205,
            0.255,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor="0.28",
            linewidth=0.65,
            zorder=8,
        )
    )
    key_artist = ax.quiverkey(
        q,
        0.892,
        0.17,
        0.8,
        r"0.8 m s$^{-1}$",
        labelpos="S",
        coordinates="axes",
        labelsep=0.035,
        fontproperties={"size": 8.0},
    )
    key_artist.set_zorder(10)


def plot_patterns(out: dict[str, object]) -> None:
    lat = np.asarray(out["lat"], dtype=float)
    lon = np.asarray(out["lon"], dtype=float)
    time = pd.to_datetime(out["time"])
    pc_joint = np.asarray(out["pc_joint"], dtype=float)
    pc_sst = np.asarray(out["pc_sst"], dtype=float)
    variance_joint = float(out["variance_joint"])
    variance_sst = float(out["variance_sst"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Match the report's full-width, moderately wide figure system.  The maps
    # stay large; only surplus vertical whitespace is removed.
    fig = plt.figure(figsize=(13.8, 7.1), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.72])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, :])
    fig.suptitle("PMM-like EOF diagnostics from OISST SST and ERA5 10 m wind", fontsize=16.0, weight="bold")

    mesh1 = ax1.pcolormesh(lon, lat, out["sst_joint"], cmap="RdBu_r", vmin=-0.6, vmax=0.6, shading="auto")
    add_vectors(ax1, lon, lat, out["u_joint"], out["v_joint"])
    format_axes(ax1)
    add_boxes(ax1)
    ax1.set_title(f"(a) Joint SST + wind EOF1 regression ({variance_joint*100:.1f}% variance)")
    fig.colorbar(mesh1, ax=ax1, label="SST regression (degC / std index)", shrink=0.84)

    mesh2 = ax2.pcolormesh(lon, lat, out["sst_only"], cmap="RdBu_r", vmin=-0.6, vmax=0.6, shading="auto")
    format_axes(ax2)
    add_boxes(ax2)
    ax2.set_title(f"(b) SST-only EOF1 regression ({variance_sst*100:.1f}% variance)")
    fig.colorbar(mesh2, ax=ax2, label="SST regression (degC / std index)", shrink=0.84)

    ax3.axhline(0, color="0.25", lw=0.7)
    ax3.plot(time, pc_joint, color="#1f4e79", lw=0.75, alpha=0.62, label="Joint SST+wind PMM-like index")
    ax3.plot(time, pd.Series(pc_joint).rolling(5, center=True, min_periods=2).mean(), color="#1f4e79", lw=1.9)
    ax3.plot(time, pc_sst, color="#b35c2e", lw=0.68, alpha=0.45, label="SST-only EOF index")
    ax3.plot(time, pd.Series(pc_sst).rolling(5, center=True, min_periods=2).mean(), color="#b35c2e", lw=1.45)
    ax3.axvspan(pd.Timestamp("2026-01-01"), pd.Timestamp("2026-05-31"), color="#d8322a", alpha=0.12)
    ax3.set_ylabel("Standardized index")
    ax3.set_xlabel("Time")
    ax3.set_title("(c) Monthly PMM-like index, positive sign = warm NE Pacific SST pattern")
    ax3.legend(loc="upper left", ncol=2, frameon=False)
    ax3.set_xlim(pd.Timestamp("1982-01-01"), pd.Timestamp("2026-06-01"))

    fig.text(
        0.01,
        -0.01,
        "Method: OISST v2.1 SST and ERA5 10 m wind, 120E-80W and 20S-30N, 1 degree grid. "
        "Monthly anomalies are computed against 1982-2025, linearly detrended, and linearly regressed on Niño-3.4 before EOF analysis. "
        r"The joint panel's wind-vector reference is 0.8 m s$^{-1}$. "
        "This is a local PMM-like diagnostic, not the official NOAA PMM index.",
        fontsize=8.3,
        color="0.30",
    )
    save(fig, "fig_pmm_like_eof_patterns_and_index")
    plt.close(fig)


def plot_2026_focus(out: dict[str, object]) -> None:
    time = pd.to_datetime(out["time"])
    frame = pd.DataFrame({"time": time, "joint": out["pc_joint"], "sst": out["pc_sst"]})
    current = frame[(frame["time"].dt.year == CURRENT_YEAR) & (frame["time"].dt.month <= 5)].copy()
    labels = current["time"].dt.strftime("%b")
    x = np.arange(len(current))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10.8, 4.55), constrained_layout=True)
    ax.axhline(0, color="0.25", lw=0.75)
    ax.bar(x - 0.18, current["joint"], width=0.36, color="#1f4e79", label="Joint SST+wind")
    ax.bar(x + 0.18, current["sst"], width=0.36, color="#b35c2e", label="SST-only")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Standardized index")
    ax.set_title("2026 Jan-May PMM-like index", fontsize=16.0, weight="bold")
    ax.legend(frameon=False)
    ymin = min(0.0, float(current[["joint", "sst"]].min().min()))
    ymax = max(0.0, float(current[["joint", "sst"]].max().max()))
    ax.set_ylim(ymin - 0.18 * max(1.0, abs(ymin)), ymax + 0.22 * max(1.0, abs(ymax)))
    for xi, y in zip(x - 0.18, current["joint"]):
        ax.text(xi, y + (0.08 if y >= 0 else -0.14), f"{y:.2f}", ha="center", va="bottom" if y >= 0 else "top", fontsize=9.6)
    for xi, y in zip(x + 0.18, current["sst"]):
        ax.text(xi, y + (0.08 if y >= 0 else -0.14), f"{y:.2f}", ha="center", va="bottom" if y >= 0 else "top", fontsize=9.6)
    fig.text(
        0.01,
        -0.02,
        "Positive sign is oriented to warm NE Pacific SST. Same preprocessing as EOF figure.",
        fontsize=8.2,
        color="0.30",
    )
    save(fig, "fig_pmm_like_index_2026_jan_may")
    plt.close(fig)


def save(fig: plt.Figure, stem: str) -> None:
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.16)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.16)
    print(png)
    print(pdf)


def write_manifest() -> None:
    rows = [
        {"output": str(FIELDS_NPZ), "description": "EOF fields and PC series for local PMM-like diagnostic."},
        {"output": str(INDEX_CSV), "description": "Monthly PMM-like joint SST+wind and SST-only standardized indices."},
        {"output": str(OUT_DIR / "fig_pmm_like_eof_patterns_and_index.png"), "description": "Joint SST+wind EOF, SST-only EOF, and full index time series."},
        {"output": str(OUT_DIR / "fig_pmm_like_index_2026_jan_may.png"), "description": "2026 Jan-May index focus plot."},
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(MANIFEST)


def main() -> int:
    setup_style()
    out = compute()
    plot_patterns(out)
    plot_2026_focus(out)
    write_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
