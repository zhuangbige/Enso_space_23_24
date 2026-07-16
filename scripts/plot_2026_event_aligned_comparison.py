#!/usr/bin/env python3
"""Compare 2026 with calendar-aligned historical strong El Niño events.

Event years follow Peng et al. (2025): 1982, 1997, 2015, and 2023, with
2026 added as the current event. All comparisons use the same developing-year
months available for 2026, especially Jan-May and Apr-May.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path("/Users/daiyue/Documents/Maryland")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


MONTHLY = ROOT / "data/interim/research_2026/current_2026_monthly_indices.csv"
GPCP_SPATIAL = ROOT / "data/interim/research_2026/current_2026_spatial_meteorology.npz"
ERA5_FULL = ROOT / "data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc"
ERA5_2026 = ROOT / "data/raw/era5/era5_monthly_single_tropics_1deg_1982_2022_2026_jan_may/data_stream-moda_stepType-avgua.nc"
OUT_DIR = ROOT / "outputs/research_2026/figures"
OUT_CSV = ROOT / "data/derived/research_2026/event_aligned_2026_comparison.csv"

EVENT_YEARS = [1982, 1997, 2015, 2023, 2026]
EVENT_LABELS = {
    1982: "1982/83",
    1997: "1997/98",
    2015: "2015/16",
    2023: "2023/24",
    2026: "2026",
}
REFERENCE_START = 1982
REFERENCE_END = 2022
MONTHS = [1, 2, 3, 4, 5]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May"]
APR_MAY = [4, 5]


@dataclass(frozen=True)
class Region:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


REGIONS = {
    "cwp": Region(-5, 5, 160, 220),
    "darwin": Region(-20, -5, 120, 140),
    "tahiti": Region(-25, -10, 200, 220),
}


COLORS = {
    1982: "#8b8b8b",
    1997: "#5b6f95",
    2015: "#6d9f71",
    2023: "#d9793d",
    2026: "#d8322a",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.5,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 8.8,
            "ytick.labelsize": 8.8,
            "legend.fontsize": 8.0,
            "axes.linewidth": 0.85,
            "axes.unicode_minus": False,
        }
    )


def monthly_metric(frame: pd.DataFrame, metric: str, region: str) -> pd.DataFrame:
    out = frame[frame["metric"].eq(metric) & frame["region"].eq(region)][["year", "month", "anomaly"]].copy()
    out["year"] = out["year"].astype(int)
    out["month"] = out["month"].astype(int)
    return out


def value_lookup(frame: pd.DataFrame) -> dict[tuple[int, int], float]:
    return {(int(row.year), int(row.month)): float(row.anomaly) for row in frame.itertuples()}


def period_mean(lookup: dict[tuple[int, int], float], year: int, months: list[int]) -> float:
    vals = [lookup.get((year, month), np.nan) for month in months]
    return float(np.nanmean(vals))


def _weighted_grid_mean(field: np.ndarray, lat: np.ndarray, lon: np.ndarray, region: Region) -> float:
    lat_idx = np.where((lat >= region.lat_min) & (lat <= region.lat_max))[0]
    lon_idx = np.where((lon >= region.lon_min) & (lon <= region.lon_max))[0]
    arr = np.asarray(field[np.ix_(lat_idx, lon_idx)], dtype=float)
    weights = np.cos(np.deg2rad(lat[lat_idx])).astype(float)
    valid = np.isfinite(arr)
    numerator = np.where(valid, arr, 0.0) * weights[:, None]
    denominator = np.where(valid, weights[:, None], 0.0).sum()
    return float(numerator.sum() / denominator) if denominator > 0 else np.nan


def fill_2026_gpcp_from_spatial(gpcp_cp: dict[tuple[int, int], float]) -> None:
    """Fill April-May 2026 GPCP values from the local spatial cache.

    The monthly index table was created before the latest GPCP spatial cache
    and may only contain Jan-Mar 2026. The spatial cache contains April and May
    maps, so use the same central-Pacific box to keep the event comparison
    month-aligned through May 2026.
    """
    if not GPCP_SPATIAL.exists():
        return
    data = np.load(GPCP_SPATIAL)
    lat = data["precip_lat"].astype(float)
    lon = data["precip_lon"].astype(float)
    cp = Region(-5, 5, 180, 220)
    month_to_key = {4: "precip_APR", 5: "precip_MAY"}
    for month, key in month_to_key.items():
        if key in data.files:
            gpcp_cp[(2026, month)] = _weighted_grid_mean(data[key], lat, lon, cp)


def monthly_fep_residual(frame: pd.DataFrame) -> dict[tuple[int, int], float]:
    n34 = value_lookup(monthly_metric(frame, "ersstv5_sst", "nino34"))
    fep = value_lookup(monthly_metric(frame, "ersstv5_sst", "fep"))
    out: dict[tuple[int, int], float] = {}
    for month in MONTHS:
        years = [
            year
            for year in range(REFERENCE_START, REFERENCE_END + 1)
            if np.isfinite(n34.get((year, month), np.nan)) and np.isfinite(fep.get((year, month), np.nan))
        ]
        x = np.asarray([n34[(year, month)] for year in years], dtype=float)
        y = np.asarray([fep[(year, month)] for year in years], dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        for year in EVENT_YEARS:
            if (year, month) in n34 and (year, month) in fep:
                out[(year, month)] = float(fep[(year, month)] - (slope * n34[(year, month)] + intercept))
    return out


def period_fep_residual(frame: pd.DataFrame, year: int, months: list[int]) -> float:
    n34 = value_lookup(monthly_metric(frame, "ersstv5_sst", "nino34"))
    fep = value_lookup(monthly_metric(frame, "ersstv5_sst", "fep"))
    hist_years = [
        y
        for y in range(REFERENCE_START, REFERENCE_END + 1)
        if all((y, month) in n34 and (y, month) in fep for month in months)
    ]
    x = np.asarray([period_mean(n34, y, months) for y in hist_years], dtype=float)
    yv = np.asarray([period_mean(fep, y, months) for y in hist_years], dtype=float)
    slope, intercept = np.polyfit(x, yv, 1)
    return float(period_mean(fep, year, months) - (slope * period_mean(n34, year, months) + intercept))


def _standardize_era5(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    if "valid_time" in ds.coords:
        rename["valid_time"] = "time"
    if "latitude" in ds.coords:
        rename["latitude"] = "lat"
    if "longitude" in ds.coords:
        rename["longitude"] = "lon"
    ds = ds.rename(rename)
    ds = ds.assign_coords(lon=(ds["lon"] % 360)).sortby("lon").sortby("lat")
    if "msl" in ds:
        ds["msl_hpa"] = ds["msl"] / 100.0
    return ds


def _weighted_region_series(ds: xr.Dataset, variable: str, region: Region) -> pd.Series:
    sub = ds[variable].sel(lat=slice(region.lat_min, region.lat_max), lon=slice(region.lon_min, region.lon_max))
    weights = np.cos(np.deg2rad(sub.lat))
    values = sub.weighted(weights).mean(("lat", "lon"), skipna=True)
    index = pd.PeriodIndex(pd.to_datetime(values.time.values), freq="M")
    return pd.Series(values.values.astype(float), index=index)


def _monthly_anomaly_series(raw: pd.Series, baseline_years: tuple[int, int] = (REFERENCE_START, REFERENCE_END)) -> pd.Series:
    by_month = raw.groupby(raw.index.month)
    clim = {
        month: vals[(vals.index.year >= baseline_years[0]) & (vals.index.year <= baseline_years[1])].mean()
        for month, vals in by_month
    }
    return pd.Series([raw.loc[idx] - clim[idx.month] for idx in raw.index], index=raw.index)


def build_era5_2026_series() -> dict[str, dict[tuple[int, int], float]]:
    compact = _standardize_era5(xr.open_dataset(ERA5_2026)[["u10", "msl"]])
    try:
        series_compact = {
            "era5_cwp_u10": _monthly_anomaly_series(_weighted_region_series(compact, "u10", REGIONS["cwp"])),
            "msl_tahiti": _monthly_anomaly_series(_weighted_region_series(compact, "msl_hpa", REGIONS["tahiti"])),
            "msl_darwin": _monthly_anomaly_series(_weighted_region_series(compact, "msl_hpa", REGIONS["darwin"])),
        }
    finally:
        compact.close()

    out = {"era5_cwp_u10": {}, "era5_soi_like_mslp": {}}
    for month in MONTHS:
        key = pd.Period(f"2026-{month:02d}", freq="M")
        if key not in series_compact["era5_cwp_u10"].index:
            continue
        out["era5_cwp_u10"][(2026, month)] = float(series_compact["era5_cwp_u10"].loc[key])
        out["era5_soi_like_mslp"][(2026, month)] = float(
            series_compact["msl_tahiti"].loc[key] - series_compact["msl_darwin"].loc[key]
        )
    return out


def build_era5_all_years_series() -> dict[str, dict[tuple[int, int], float]]:
    """Return full ERA5 monthly anomaly series for 1982-2024.

    This is used for the historical expected-response regression and keeps the
    large ERA5 file read to a single pass.
    """
    full = _standardize_era5(xr.open_dataset(ERA5_FULL)[["u10", "msl"]])
    try:
        u10 = _monthly_anomaly_series(_weighted_region_series(full, "u10", REGIONS["cwp"]))
        tahiti = _monthly_anomaly_series(_weighted_region_series(full, "msl_hpa", REGIONS["tahiti"]))
        darwin = _monthly_anomaly_series(_weighted_region_series(full, "msl_hpa", REGIONS["darwin"]))
    finally:
        full.close()
    out = {"era5_cwp_u10": {}, "era5_soi_like_mslp": {}}
    for idx in u10.index:
        out["era5_cwp_u10"][(idx.year, idx.month)] = float(u10.loc[idx])
        out["era5_soi_like_mslp"][(idx.year, idx.month)] = float(tahiti.loc[idx] - darwin.loc[idx])
    return out


def build_event_table() -> pd.DataFrame:
    frame = pd.read_csv(MONTHLY)
    nino3 = value_lookup(monthly_metric(frame, "ersstv5_sst", "nino3"))
    nino34 = value_lookup(monthly_metric(frame, "ersstv5_sst", "nino34"))
    fep = value_lookup(monthly_metric(frame, "ersstv5_sst", "fep"))
    gpcp_cp = value_lookup(monthly_metric(frame, "gpcp_precip", "central_pacific_180_140w"))
    fill_2026_gpcp_from_spatial(gpcp_cp)
    fep_res_monthly = monthly_fep_residual(frame)
    era5_all = build_era5_all_years_series()
    era5_2026 = build_era5_2026_series()
    era5 = {"era5_cwp_u10": {}, "era5_soi_like_mslp": {}}
    for metric in era5:
        for year in EVENT_YEARS:
            source = era5_2026[metric] if year == 2026 else era5_all[metric]
            for month in MONTHS:
                if (year, month) in source:
                    era5[metric][(year, month)] = source[(year, month)]

    monthly_rows: list[dict[str, object]] = []
    for year in EVENT_YEARS:
        for month in MONTHS:
            monthly_rows.append(
                {
                    "event_year": year,
                    "event_label": EVENT_LABELS[year],
                    "month": month,
                    "month_label": MONTH_LABELS[month - 1],
                    "nino3_sst": nino3.get((year, month), np.nan),
                    "nino34_sst": nino34.get((year, month), np.nan),
                    "fep_sst": fep.get((year, month), np.nan),
                    "fep_residual": fep_res_monthly.get((year, month), np.nan),
                    "gpcp_cp_precip": gpcp_cp.get((year, month), np.nan),
                    "era5_cwp_u10": era5["era5_cwp_u10"].get((year, month), np.nan),
                    "era5_soi_like_mslp": era5["era5_soi_like_mslp"].get((year, month), np.nan),
                    "era5_note": "2026 uses compact 1-degree CDS subset; historical events use local ERA5 0.25-degree archive.",
                }
            )

    rows: list[dict[str, object]] = list(monthly_rows)

    # Apr-May expected-response diagnostics.
    for metric in ["era5_cwp_u10", "era5_soi_like_mslp", "gpcp_cp_precip"]:
        hist_years = [
            year
            for year in range(REFERENCE_START, REFERENCE_END + 1)
            if all((year, month) in nino3 for month in APR_MAY)
        ]
        if metric.startswith("era5"):
            response = era5[metric]
            response_hist = era5_all[metric]
        else:
            response = gpcp_cp
            response_hist = gpcp_cp
        common = [
            year
            for year in hist_years
            if all((year, month) in response_hist and np.isfinite(response_hist[(year, month)]) for month in APR_MAY)
        ]
        x = np.asarray([period_mean(nino3, year, APR_MAY) for year in common], dtype=float)
        y = np.asarray([period_mean(response_hist, year, APR_MAY) for year in common], dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        for year in EVENT_YEARS:
            value = period_mean(response, year, APR_MAY)
            expected = float(slope * period_mean(nino3, year, APR_MAY) + intercept)
            rows.append(
                {
                    "event_year": year,
                    "event_label": EVENT_LABELS[year],
                    "month": 45,
                    "month_label": "Apr-May",
                    "diagnostic": f"{metric}_expected_response",
                    "observed": value,
                    "expected": expected,
                    "observed_over_expected": value / expected if abs(expected) > 1.0e-10 else np.nan,
                    "observed_minus_expected": value - expected,
                    "regression_years": f"{REFERENCE_START}-{REFERENCE_END}",
                    "regression_n_years": len(common),
                }
            )

    for year in EVENT_YEARS:
        rows.append(
            {
                "event_year": year,
                "event_label": EVENT_LABELS[year],
                "month": 45,
                "month_label": "Apr-May",
                "diagnostic": "apr_may_summary",
                "nino3_sst": period_mean(nino3, year, APR_MAY),
                "nino34_sst": period_mean(nino34, year, APR_MAY),
                "fep_sst": period_mean(fep, year, APR_MAY),
                "fep_residual": period_fep_residual(frame, year, APR_MAY),
                "gpcp_cp_precip": period_mean(gpcp_cp, year, APR_MAY),
                "era5_cwp_u10": period_mean(era5["era5_cwp_u10"], year, APR_MAY),
                "era5_soi_like_mslp": period_mean(era5["era5_soi_like_mslp"], year, APR_MAY),
            }
        )

    return pd.DataFrame(rows)


def plot_sst_trajectory(table: pd.DataFrame) -> Path:
    setup_style()
    monthly = table[table["month"].isin(MONTHS)].copy()
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.5), sharex=True)
    panels = [
        ("nino3_sst", "Niño-3 SST", "SST anomaly (°C)"),
        ("fep_sst", "Far-eastern Pacific SST", "SST anomaly (°C)"),
        ("fep_residual", "FEP residual", "Residual SST (°C)"),
    ]
    for ax, (col, title, ylabel) in zip(axes, panels, strict=True):
        for year in EVENT_YEARS:
            subset = monthly[monthly["event_year"].eq(year)].sort_values("month")
            lw = 2.5 if year == 2026 else 1.6
            alpha = 1.0 if year == 2026 else 0.78
            ax.plot(
                subset["month"],
                subset[col],
                marker="o",
                ms=4.2,
                lw=lw,
                alpha=alpha,
                color=COLORS[year],
                label=EVENT_LABELS[year],
            )
        ax.axhline(0, color="0.55", lw=0.8)
        ax.set_title(title, loc="left", weight="bold")
        ax.set_ylabel(ylabel)
        ax.set_xticks(MONTHS)
        ax.set_xticklabels(MONTH_LABELS)
        ax.grid(True, color="0.88", lw=0.6)
    axes[0].legend(loc="upper left", frameon=False, ncol=1)
    fig.suptitle("Event-aligned SST development: 2026 versus strong El Niño events", weight="bold", y=0.98)
    fig.text(
        0.01,
        0.035,
        "All events use the same developing-year Jan-May months. FEP residual = FEP SST minus the component linearly expected from Niño-3.4 for each calendar month.",
        fontsize=8.2,
        color="0.30",
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    out = OUT_DIR / "fig5_2026_event_aligned_sst_trajectory.png"
    fig.savefig(out, bbox_inches="tight", pad_inches=0.18)
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return out


def plot_atmosphere_trajectory(table: pd.DataFrame) -> Path:
    setup_style()
    monthly = table[table["month"].isin(MONTHS)].copy()
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.5), sharex=True)
    panels = [
        ("era5_cwp_u10", "ERA5 CWP u10", "u10 anomaly (m/s)"),
        ("era5_soi_like_mslp", "ERA5 SOI-like pressure", "Tahiti-Darwin MSLP (hPa)"),
        ("gpcp_cp_precip", "GPCP central-Pacific rainfall", "Rainfall anomaly (mm/day)"),
    ]
    for ax, (col, title, ylabel) in zip(axes, panels, strict=True):
        for year in EVENT_YEARS:
            subset = monthly[monthly["event_year"].eq(year)].sort_values("month")
            lw = 2.5 if year == 2026 else 1.6
            alpha = 1.0 if year == 2026 else 0.78
            ax.plot(
                subset["month"],
                subset[col],
                marker="o",
                ms=4.2,
                lw=lw,
                alpha=alpha,
                color=COLORS[year],
                label=EVENT_LABELS[year],
            )
        ax.axhline(0, color="0.55", lw=0.8)
        ax.set_title(title, loc="left", weight="bold")
        ax.set_ylabel(ylabel)
        ax.set_xticks(MONTHS)
        ax.set_xticklabels(MONTH_LABELS)
        ax.grid(True, color="0.88", lw=0.6)
    axes[0].legend(loc="upper left", frameon=False, ncol=1)
    fig.suptitle("Event-aligned atmospheric response: same Jan-May window", weight="bold", y=0.98)
    fig.text(
        0.01,
        0.035,
        "ERA5 2026 uses the compact 1-degree CDS subset; historical events use the local 0.25-degree ERA5 archive. GPCP is used for rainfall.",
        fontsize=8.2,
        color="0.30",
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    out = OUT_DIR / "fig6_2026_event_aligned_atmosphere_trajectory.png"
    fig.savefig(out, bbox_inches="tight", pad_inches=0.18)
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return out


def plot_apr_may_matrix(table: pd.DataFrame) -> Path:
    setup_style()
    summary = table[table.get("diagnostic", "").eq("apr_may_summary")].copy()
    expected = table[table.get("diagnostic", "").astype(str).str.endswith("_expected_response")].copy()
    ratio_lookup = {
        (int(row.event_year), str(row.diagnostic).replace("_expected_response", "")): float(row.observed_over_expected)
        for row in expected.itertuples()
    }

    rows = [
        ("Niño-3 SST", "nino3_sst", "°C", 0.0, -0.5, 2.0),
        ("FEP residual", "fep_residual", "°C", 0.0, -0.8, 1.0),
        ("u10 obs/exp", "era5_cwp_u10", "x", 1.0, -0.5, 2.5),
        ("SOI-like obs/exp", "era5_soi_like_mslp", "x", 1.0, -0.5, 2.5),
        ("GPCP CP obs/exp", "gpcp_cp_precip", "x", 1.0, -0.5, 2.5),
    ]
    values = np.full((len(rows), len(EVENT_YEARS)), np.nan)
    labels = [["" for _ in EVENT_YEARS] for _ in rows]
    for j, year in enumerate(EVENT_YEARS):
        row = summary[summary["event_year"].eq(year)].iloc[0]
        values[0, j] = float(row["nino3_sst"])
        labels[0][j] = f"{values[0, j]:.2f}"
        values[1, j] = float(row["fep_residual"])
        labels[1][j] = f"{values[1, j]:+.2f}"
        for i, metric in enumerate(["era5_cwp_u10", "era5_soi_like_mslp", "gpcp_cp_precip"], start=2):
            ratio = ratio_lookup.get((year, metric), np.nan)
            values[i, j] = ratio
            labels[i][j] = f"{ratio:.2f}x" if np.isfinite(ratio) else "NA"

    fig, ax = plt.subplots(figsize=(9.8, 5.2))
    # Row-wise centered values: raw anomaly rows centered at 0, ratio rows centered at 1.
    display = np.vstack([values[0], values[1], values[2] - 1.0, values[3] - 1.0, values[4] - 1.0])
    im = ax.imshow(display, cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-1.5, vcenter=0, vmax=1.5), aspect="auto")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, labels[i][j], ha="center", va="center", fontsize=9, color="0.10")
    ax.set_xticks(range(len(EVENT_YEARS)))
    ax.set_xticklabels([EVENT_LABELS[y] for y in EVENT_YEARS])
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([row[0] for row in rows])
    ax.tick_params(length=0)
    ax.set_title("Apr-May comparison: same developing-season window", weight="bold", pad=14)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for x in np.arange(-0.5, len(EVENT_YEARS), 1):
        ax.axvline(x, color="white", lw=1.4)
    for y in np.arange(-0.5, len(rows), 1):
        ax.axhline(y, color="white", lw=1.4)
    cbar = fig.colorbar(im, ax=ax, shrink=0.82, pad=0.02)
    cbar.set_label("relative color scale: warm/stronger red, cool/weaker blue")
    fig.text(
        0.01,
        0.035,
        "Rows 1-2 are anomalies; rows 3-5 are observed / expected ratios from 1982-2022 Apr-May Niño-3 regressions. "
        "All values use the event developing year Apr-May.",
        fontsize=8.2,
        color="0.30",
    )
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    out = OUT_DIR / "fig7_2026_event_apr_may_summary_matrix.png"
    fig.savefig(out, bbox_inches="tight", pad_inches=0.18)
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table = build_event_table()
    table.to_csv(OUT_CSV, index=False)
    outputs = [
        plot_sst_trajectory(table),
        plot_atmosphere_trajectory(table),
        plot_apr_may_matrix(table),
    ]
    print(OUT_CSV)
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
