#!/usr/bin/env python3
"""Plot 2026 ERA5 expected atmospheric response lines.

This applies the Peng et al. (2025) expected-response logic to the current
2026 diagnosis: historical Niño-3 SST anomalies are regressed onto ERA5
atmospheric responses, then the 2026 observed response is compared with the
regression-expected response for the same SST forcing.
"""

from __future__ import annotations

import csv
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pandas as pd


ROOT = Path("/Users/daiyue/Documents/Maryland")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ERA5_SCRIPT = ROOT / "scripts/build_era5_2026_spatial_analysis.py"
DETREND_SCRIPT = ROOT / "scripts/build_and_plot_2026_detrended_diagnostics.py"
SST_RAW = ROOT / "data/interim/research_2026/current_2026_monthly_indices.csv"
SST_DETRENDED = ROOT / "data/interim/research_2026/current_2026_monthly_indices_detrended.csv"
OUT_CSV = ROOT / "data/derived/research_2026/current_2026_era5_expected_response_lines.csv"
OUT_DIR = ROOT / "outputs/research_2026/figures"

REFERENCE_START = 1982
REFERENCE_END = 2022
TARGET_YEAR = 2026
PERIOD = "AM_to_date"
PERIOD_LABEL = "Apr-May"
PERIOD_MONTHS = (4, 5)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
            "xtick.labelsize": 8.6,
            "ytick.labelsize": 8.6,
            "legend.fontsize": 8.2,
            "axes.linewidth": 0.8,
            "axes.unicode_minus": False,
        }
    )


def period_sst(path: Path) -> dict[int, float]:
    frame = pd.read_csv(path)
    subset = frame[
        frame["metric"].eq("ersstv5_sst")
        & frame["region"].eq("nino3")
        & frame["month"].isin(PERIOD_MONTHS)
    ].copy()
    grouped = subset.groupby("year")
    out: dict[int, float] = {}
    for year, group in grouped:
        months = set(group["month"].astype(int))
        if set(PERIOD_MONTHS).issubset(months):
            out[int(year)] = float(group["anomaly"].mean())
    return out


def weighted_region_time_series(da, region) -> pd.Series:
    sub = da.sel(lat=slice(region.lat_min, region.lat_max), lon=slice(region.lon_min, region.lon_max))
    weights = np.cos(np.deg2rad(sub.lat))
    values = sub.weighted(weights).mean(("lat", "lon"), skipna=True)
    index = pd.PeriodIndex(pd.to_datetime(values.time.values), freq="M")
    return pd.Series(values.values.astype(float), index=index)


def period_response_series(anom, era5_builder, response_key: str) -> dict[int, float]:
    if response_key == "u10_cwp":
        monthly = weighted_region_time_series(anom["u10"], era5_builder.REGIONS["cwp_160e_140w"])
    elif response_key == "soi_like_mslp":
        tahiti = weighted_region_time_series(anom["msl_hpa"], era5_builder.REGIONS["tahiti_proxy"])
        darwin = weighted_region_time_series(anom["msl_hpa"], era5_builder.REGIONS["darwin_proxy"])
        monthly = tahiti - darwin
    else:
        raise ValueError(response_key)

    out: dict[int, float] = {}
    for year in range(REFERENCE_START, REFERENCE_END + 1):
        periods = [pd.Period(f"{year}-{month:02d}", freq="M") for month in PERIOD_MONTHS]
        if all(period in monthly.index for period in periods):
            vals = [monthly.loc[period] for period in periods]
            if np.isfinite(vals).all():
                out[year] = float(np.mean(vals))

    periods_2026 = [pd.Period(f"{TARGET_YEAR}-{month:02d}", freq="M") for month in PERIOD_MONTHS]
    if all(period in monthly.index for period in periods_2026):
        vals = [monthly.loc[period] for period in periods_2026]
        if np.isfinite(vals).all():
            out[TARGET_YEAR] = float(np.mean(vals))
    return out


def fit_expected(x_by_year: dict[int, float], y_by_year: dict[int, float]) -> dict[str, object]:
    years = [year for year in range(REFERENCE_START, REFERENCE_END + 1) if year in x_by_year and year in y_by_year]
    x = np.asarray([x_by_year[year] for year in years], dtype=float)
    y = np.asarray([y_by_year[year] for year in years], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1])
    x_2026 = float(x_by_year[TARGET_YEAR])
    observed = float(y_by_year[TARGET_YEAR])
    expected = float(slope * x_2026 + intercept)
    ratio = float(observed / expected) if abs(expected) > 1.0e-10 else np.nan
    return {
        "years": years,
        "x": x,
        "y": y,
        "slope": float(slope),
        "intercept": float(intercept),
        "r": r,
        "nino3_2026": x_2026,
        "observed_2026": observed,
        "expected_2026": expected,
        "observed_over_expected": ratio,
        "residual": observed - expected,
    }


def build_results() -> list[dict[str, object]]:
    era5_builder = load_module(ERA5_SCRIPT, "era5_expected_builder")
    detrend_builder = load_module(DETREND_SCRIPT, "era5_expected_detrender")
    ds = era5_builder._open_inputs()
    raw_anom = era5_builder._monthly_anomalies(ds)
    det_anom = detrend_builder._detrended_era5_anomalies(ds)

    configs = [
        ("raw", "No detrend", SST_RAW, raw_anom),
        ("detrended", "Detrended", SST_DETRENDED, det_anom),
    ]
    responses = [
        ("u10_cwp", "ERA5 CWP u10", "m/s", "Central-west Pacific u10 anomaly (m/s)"),
        ("soi_like_mslp", "ERA5 SOI-like MSLP", "hPa", "Tahiti minus Darwin MSLP anomaly (hPa)"),
    ]

    rows: list[dict[str, object]] = []
    for kind, kind_label, sst_path, anom in configs:
        x_by_year = period_sst(sst_path)
        for response_key, response_label, unit, ylabel in responses:
            y_by_year = period_response_series(anom, era5_builder, response_key)
            result = fit_expected(x_by_year, y_by_year)
            result.update(
                {
                    "kind": kind,
                    "kind_label": kind_label,
                    "period": PERIOD,
                    "period_label": PERIOD_LABEL,
                    "response_key": response_key,
                    "response_label": response_label,
                    "unit": unit,
                    "ylabel": ylabel,
                    "regression_years": f"{REFERENCE_START}-{REFERENCE_END}",
                    "regression_n_years": len(result["years"]),
                }
            )
            rows.append(result)
    return rows


def write_table(rows: list[dict[str, object]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "kind",
        "period",
        "period_label",
        "response_key",
        "response_label",
        "unit",
        "nino3_2026",
        "observed_2026",
        "expected_2026",
        "observed_over_expected",
        "residual",
        "slope",
        "intercept",
        "r",
        "regression_years",
        "regression_n_years",
    ]
    with OUT_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})


def plot_panel(ax, row: dict[str, object], panel_label: str) -> None:
    x = row["x"]
    y = row["y"]
    slope = row["slope"]
    intercept = row["intercept"]
    x_2026 = row["nino3_2026"]
    observed = row["observed_2026"]
    expected = row["expected_2026"]
    ratio = row["observed_over_expected"]

    x_min = min(float(np.nanmin(x)), float(x_2026)) - 0.25
    x_max = max(float(np.nanmax(x)), float(x_2026)) + 0.25
    line_x = np.linspace(x_min, x_max, 200)
    line_y = slope * line_x + intercept

    ax.scatter(x, y, s=24, color="0.70", edgecolor="white", linewidth=0.45, zorder=2)
    ax.plot(line_x, line_y, color="#c8332d", ls="--", lw=1.4, zorder=1)
    ax.scatter([x_2026], [observed], s=72, color="#df3b2f", edgecolor="white", linewidth=0.7, zorder=4)
    ax.scatter([x_2026], [expected], s=86, facecolors="none", edgecolors="#c8332d", linewidth=1.6, zorder=5)
    ax.plot([x_2026, x_2026], [observed, expected], color="#c8332d", lw=1.2, ls=(0, (3, 2)), zorder=3)
    ax.axhline(0, color="0.55", lw=0.75)
    ax.axvline(0, color="0.55", lw=0.75)
    ax.grid(True, color="0.88", lw=0.6)
    ax.set_xlabel(f"{PERIOD_LABEL} Niño-3 SST anomaly (°C)")
    ax.set_ylabel(row["ylabel"])
    ax.set_title(f"{panel_label}. {row['kind_label']}: {row['response_label']}", loc="left", weight="bold")
    ax.text(
        0.03,
        0.95,
        f"Rexp = {slope:.2f} × Niño-3 {intercept:+.2f}\n"
        f"2026 obs/exp = {ratio:.2f}; r = {row['r']:.2f}",
        transform=ax.transAxes,
        va="top",
        fontsize=8.1,
        color="0.22",
        bbox={"facecolor": "white", "edgecolor": "0.82", "boxstyle": "round,pad=0.24", "alpha": 0.88},
    )
    ax.annotate(
        "expected",
        xy=(x_2026, expected),
        xytext=(x_2026 - 0.65, expected + 0.22 if expected >= observed else expected - 0.35),
        arrowprops={"arrowstyle": "->", "color": "#c8332d", "lw": 0.9},
        fontsize=7.8,
        color="#8f1d18",
    )
    ax.annotate(
        "observed",
        xy=(x_2026, observed),
        xytext=(x_2026 + 0.10, observed + 0.20 if observed >= expected else observed - 0.35),
        arrowprops={"arrowstyle": "->", "color": "0.2", "lw": 0.8},
        fontsize=7.8,
        color="0.18",
    )


def plot(rows: list[dict[str, object]]) -> None:
    setup_style()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    order = [
        ("raw", "u10_cwp"),
        ("raw", "soi_like_mslp"),
        ("detrended", "u10_cwp"),
        ("detrended", "soi_like_mslp"),
    ]
    lookup = {(row["kind"], row["response_key"]): row for row in rows}
    fig, axes = plt.subplots(2, 2, figsize=(12.6, 8.7), constrained_layout=False)
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.115, top=0.815, wspace=0.22, hspace=0.34)
    fig.suptitle("2026 expected atmospheric response from historical Niño-3 coupling", weight="bold", fontsize=14, y=0.975)
    labels = ["a", "b", "c", "d"]
    for ax, key, label in zip(axes.ravel(), order, labels, strict=True):
        plot_panel(ax, lookup[key], label)

    fig.text(
        0.5,
        0.925,
        "Gray dots: 1982-2022    Red markers: 2026 observed and expected",
        ha="center",
        va="center",
        fontsize=9.5,
        color="0.25",
    )
    fig.text(
        0.01,
        0.035,
        "Data: ERSSTv5 Niño-3 SST and ERA5 monthly means. Historical dots use Apr-May values for 1982-2022; red markers show 2026 Apr-May. "
        "Open red circles mark the response expected from the historical Niño-3 regression at the 2026 SST value.",
        fontsize=8.1,
        color="0.30",
    )
    for stem in ["fig4_2026_era5_expected_response_lines", "fig_2026_expected_response_lines"]:
        fig.savefig(OUT_DIR / f"{stem}.png", bbox_inches="tight", pad_inches=0.18)
        fig.savefig(OUT_DIR / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)


def main() -> int:
    rows = build_results()
    write_table(rows)
    plot(rows)
    print(OUT_CSV)
    print(OUT_DIR / "fig4_2026_era5_expected_response_lines.png")
    print(OUT_DIR / "fig4_2026_era5_expected_response_lines.pdf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
