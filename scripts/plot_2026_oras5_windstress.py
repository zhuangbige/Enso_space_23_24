#!/usr/bin/env python3
"""Plot 2026 Jan-May ORAS5 equatorial wind-stress anomalies.

Method:
- Data: CDS ORAS5 time-series zonal/meridional wind stress at nearest native
  grid points along 0 degrees latitude.
- Baseline: 1980-2025 same-month climatology.
- Trend: linear trend fitted over 1980-2025 for each calendar month and
  longitude, then removed from the monthly anomaly series.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


INPUT_CSV = ROOT / "data/interim/research_2026/oras5_windstress_timeseries_equatorial_1980_202605.csv"
OUT_DIR = ROOT / "outputs/research_2026/oras5_windstress"
DERIVED_CSV = ROOT / "data/derived/research_2026/monthly_2026_oras5_windstress_detrended_1980_2025.csv"
DERIVED_NPZ = ROOT / "data/interim/research_2026/monthly_panel_inputs/monthly_2026_oras5_windstress_detrended_1980_2025.npz"

BASELINE_START = 1980
BASELINE_END = 2025
TARGET_YEAR = 2026
MONTHS = [1, 2, 3, 4, 5]
MONTH_LABELS = ["January", "February", "March", "April", "May"]


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


def decimal_year(year: np.ndarray, month: np.ndarray) -> np.ndarray:
    return year.astype(float) + (month.astype(float) - 0.5) / 12.0


def detrended_target_rows(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.loc[
        ((raw["product_type"].eq("consolidated")) & (raw["year"] <= 2014))
        | ((raw["product_type"].eq("operational")) & (raw["year"] >= 2015))
    ].copy()
    raw = raw.sort_values(["requested_lon", "time"])

    rows: list[dict[str, object]] = []
    for (lon, month), group in raw.groupby(["requested_lon", "month"]):
        if month not in MONTHS:
            continue
        group = group.sort_values("time")
        base = group["year"].between(BASELINE_START, BASELINE_END)
        target = group["year"].eq(TARGET_YEAR)
        if int(base.sum()) < 10 or int(target.sum()) != 1:
            continue
        if group.loc[base, ["tau_x_n_m2", "tau_y_n_m2"]].notna().sum().sum() == 0:
            continue

        target_idx = np.where(target.to_numpy())[0][0]
        time = decimal_year(group["year"].to_numpy(dtype=float), group["month"].to_numpy(dtype=float))
        row: dict[str, object] = {
            "year": TARGET_YEAR,
            "month": int(month),
            "month_label": MONTH_LABELS[int(month) - 1],
            "lon": float(lon),
            "native_lon": float(group["native_lon"].iloc[target_idx]),
            "native_lat": float(group["native_lat"].iloc[target_idx]),
            "baseline_years": f"{BASELINE_START}-{BASELINE_END}",
            "n_baseline_years": int(base.sum()),
            "source": "CDS ORAS5 time-series zonal_wind_stress and meridional_wind_stress along 0 degree latitude",
        }
        for source_col, prefix in [("tau_x_n_m2", "tau_x"), ("tau_y_n_m2", "tau_y")]:
            values = group[source_col].to_numpy(dtype=float)
            clim = float(np.nanmean(values[base.to_numpy()]))
            anomaly = values - clim
            x = time[base.to_numpy()]
            y = anomaly[base.to_numpy()]
            valid = np.isfinite(x) & np.isfinite(y)
            if int(valid.sum()) < 10:
                row[f"{prefix}_detrended_anomaly_n_m2"] = np.nan
                row[f"{prefix}_raw_anomaly_n_m2"] = np.nan
                row[f"{prefix}_linear_trend_slope_n_m2_per_year"] = np.nan
                continue
            slope, intercept = np.polyfit(x[valid], y[valid], 1)
            row[f"{prefix}_detrended_anomaly_n_m2"] = float(anomaly[target_idx] - (slope * time[target_idx] + intercept))
            row[f"{prefix}_raw_anomaly_n_m2"] = float(anomaly[target_idx])
            row[f"{prefix}_linear_trend_slope_n_m2_per_year"] = float(slope)
        rows.append(row)

    out = pd.DataFrame(rows).sort_values(["month", "lon"])
    missing = set(MONTHS) - set(out["month"].unique())
    if missing:
        raise ValueError(f"ORAS5 wind stress missing target months: {sorted(missing)}")
    if out[["tau_x_detrended_anomaly_n_m2", "tau_y_detrended_anomaly_n_m2"]].isna().all(axis=None):
        raise ValueError("All ORAS5 wind-stress target anomalies are missing.")
    return out


def build_fields(out: pd.DataFrame) -> dict[str, np.ndarray]:
    lon = np.sort(out["lon"].unique()).astype(float)
    taux = (
        out.pivot(index="month", columns="lon", values="tau_x_detrended_anomaly_n_m2")
        .reindex(index=MONTHS, columns=lon)
        .to_numpy(dtype=np.float32)
    )
    tauy = (
        out.pivot(index="month", columns="lon", values="tau_y_detrended_anomaly_n_m2")
        .reindex(index=MONTHS, columns=lon)
        .to_numpy(dtype=np.float32)
    )
    valid_lon = ~(np.all(np.isnan(taux), axis=0) & np.all(np.isnan(tauy), axis=0))
    lon = lon[valid_lon]
    taux = taux[:, valid_lon]
    tauy = tauy[:, valid_lon]
    fields = {
        "lon": lon.astype(np.float32),
        "month_numbers": np.asarray(MONTHS, dtype=np.int16),
        "months": np.asarray(MONTH_LABELS),
        "tau_x": taux,
        "tau_y": tauy,
    }
    DERIVED_NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DERIVED_NPZ, **fields)
    return fields


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.16)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.16)
    print(png)
    print(pdf)


def symmetric_limit(*arrays: np.ndarray, floor: float, step: float) -> float:
    max_abs = max(float(np.nanmax(np.abs(arr))) for arr in arrays)
    return max(floor, float(np.ceil(max_abs / step) * step))


def add_region_marks(ax: plt.Axes, *, top_labels: bool, lon_min: float, lon_max: float) -> None:
    for x, text in [(160, "CWP"), (180, "Date line"), (220, "CP"), (260, "EP"), (275, "FEP")]:
        if x < lon_min or x > lon_max:
            continue
        ax.axvline(x, color="0.3", lw=0.5, ls="--")
        if top_labels:
            ax.text(x + 1, 0.88, text, fontsize=7, color="0.28", transform=ax.get_xaxis_transform())


def transect_ticks(lon: np.ndarray) -> list[int]:
    ticks = [130, 150, 170, 180, 200, 220, 240, 260, 270]
    return [tick for tick in ticks if lon.min() <= tick <= lon.max()]


def plot_monthly_transect(fields: dict[str, np.ndarray]) -> None:
    lon = fields["lon"].astype(float)
    taux = fields["tau_x"].astype(float)
    tauy = fields["tau_y"].astype(float)
    limit = symmetric_limit(taux, tauy, floor=0.08, step=0.02)

    fig, axes = plt.subplots(5, 1, figsize=(12.4, 9.2), sharex=True, constrained_layout=True)
    fig.suptitle("2026 monthly ORAS5 equatorial wind-stress anomalies", weight="bold")
    for i, (ax, label) in enumerate(zip(axes, MONTH_LABELS)):
        colors = np.where(taux[i] >= 0, "#b74134", "#2f6fab")
        ax.bar(lon, taux[i], width=4.0, color=colors, alpha=0.72, edgecolor="none", label="zonal stress")
        ax.plot(lon, tauy[i], color="#00766f", lw=1.45, marker="o", ms=2.5, label="meridional stress")
        ax.axhline(0, color="0.25", lw=0.8)
        ax.set_ylim(-limit, limit)
        ax.set_ylabel("N m$^{-2}$")
        ax.set_title(f"{label} {TARGET_YEAR}", loc="left")
        add_region_marks(ax, top_labels=(i == 0), lon_min=float(lon.min()), lon_max=float(lon.max()))
        if i == 0:
            ax.legend(loc="lower right", ncol=2, frameon=False, fontsize=8)
    axes[-1].set_xlim(float(lon.min()), float(lon.max()))
    ticks = transect_ticks(lon)
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels([format_lon(tick) for tick in ticks])
    axes[-1].set_xlabel("Longitude along equator")
    fig.text(
        0.01,
        -0.01,
        f"ORAS5 time-series nearest native-grid points along 0 deg latitude. "
        f"Anomalies use same-month climatology and linear detrending over {BASELINE_START}-{BASELINE_END}; "
        f"consolidated product through 2014 and operational product from 2015 onward. "
        f"Requested 120E-80W; valid ocean points span {format_lon(float(lon.min()))}-{format_lon(float(lon.max()))}. "
        "Positive zonal stress is eastward/westerly forcing.",
        fontsize=8.4,
        color="0.30",
    )
    save(fig, "fig_2026_monthly_oras5_equatorial_windstress_detrended_1980_2025")
    plt.close(fig)


def coordinate_edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    midpoint = (values[:-1] + values[1:]) / 2.0
    first = values[0] - (midpoint[0] - values[0])
    last = values[-1] + (values[-1] - midpoint[-1])
    return np.concatenate([[first], midpoint, [last]])


def plot_hovmoller(fields: dict[str, np.ndarray]) -> None:
    lon = fields["lon"].astype(float)
    taux = fields["tau_x"].astype(float)
    limit = symmetric_limit(taux, floor=0.08, step=0.02)
    lon_edges = coordinate_edges(lon)
    month_edges = np.arange(0, len(MONTHS) + 1)

    fig, ax = plt.subplots(figsize=(11.6, 4.8), constrained_layout=True)
    mesh = ax.pcolormesh(lon_edges, month_edges, taux, cmap="RdBu_r", vmin=-limit, vmax=limit, shading="auto")
    ax.set_yticks(np.arange(len(MONTHS)) + 0.5)
    ax.set_yticklabels(MONTH_LABELS)
    ax.set_xlim(float(lon.min()), float(lon.max()))
    ticks = transect_ticks(lon)
    ax.set_xticks(ticks)
    ax.set_xticklabels([format_lon(tick) for tick in ticks])
    ax.set_xlabel("Longitude along equator")
    ax.set_title("2026 ORAS5 equatorial zonal wind-stress anomaly", weight="bold")
    for x in [160, 180, 220, 260, 275]:
        ax.axvline(x, color="0.2", lw=0.55, ls="--")
    fig.colorbar(mesh, ax=ax, label="zonal wind-stress anomaly (N m$^{-2}$)", shrink=0.92)
    fig.text(
        0.01,
        -0.03,
        f"Same detrended anomaly method as monthly panels; baseline {BASELINE_START}-{BASELINE_END}. "
        "Positive values indicate eastward/westerly stress.",
        fontsize=8.4,
        color="0.30",
    )
    save(fig, "fig_2026_oras5_zonal_windstress_hovmoller_detrended_1980_2025")
    plt.close(fig)


def write_manifest() -> None:
    rows = [
        {
            "output": str(DERIVED_CSV),
            "description": "ORAS5 equatorial zonal and meridional wind-stress monthly detrended anomalies for Jan-May 2026.",
            "baseline": f"{BASELINE_START}-{BASELINE_END}",
        },
        {
            "output": str(DERIVED_NPZ),
            "description": "Compiled arrays used by ORAS5 wind-stress plots.",
            "baseline": f"{BASELINE_START}-{BASELINE_END}",
        },
        {
            "output": str(OUT_DIR / "fig_2026_monthly_oras5_equatorial_windstress_detrended_1980_2025.png"),
            "description": "Five monthly equatorial ORAS5 wind-stress transect panels.",
            "baseline": f"{BASELINE_START}-{BASELINE_END}",
        },
        {
            "output": str(OUT_DIR / "fig_2026_oras5_zonal_windstress_hovmoller_detrended_1980_2025.png"),
            "description": "Month-longitude Hovmoller of ORAS5 zonal wind-stress anomaly.",
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
    setup_style()
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing ORAS5 wind-stress input: {INPUT_CSV}")
    raw = pd.read_csv(INPUT_CSV, parse_dates=["time"])
    out = detrended_target_rows(raw)
    DERIVED_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(DERIVED_CSV, index=False)
    print(DERIVED_CSV)
    fields = build_fields(out)
    plot_monthly_transect(fields)
    plot_hovmoller(fields)
    write_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
