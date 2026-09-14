#!/usr/bin/env python3
"""Plot an equatorial ORAS5 D20 longitude-time Hovmöller diagram.

The figure uses the local CDS ORAS5 time-series transect at 0° latitude.
For every longitude and calendar month, D20 anomalies are calculated relative
to the 1980-2014 same-calendar-month climatology. A linear trend fitted over
1980-2014 for that longitude and calendar month is then removed from the full
1980-June 2026 record, matching the anomaly definition used in the report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = (
    ROOT
    / "data/interim/research_2026"
    / "oras5_d20_timeseries_equatorial_1960_202606.csv"
)
OUTPUT_DIR = ROOT / "outputs/research_2026/oras5_d20_hovmoller"
OUTPUT_STEM = "oras5_equatorial_d20_anomaly_hovmoller_1980_202606"
OUTPUT_CSV = (
    ROOT
    / "data/derived/research_2026"
    / "oras5_equatorial_d20_monthly_anomaly_1980_202606_detrended_1980_2014.csv"
)
OUTPUT_METADATA = OUTPUT_DIR / f"{OUTPUT_STEM}_metadata.json"

START = pd.Timestamp("1980-01-01")
END = pd.Timestamp("2026-06-01")
BASELINE_START = 1980
BASELINE_END = 2014
LON_START = 130.0
LON_END = 275.0

os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / "mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def format_longitude(value: float) -> str:
    """Format 0-360 longitudes using E/W labels."""
    lon = value % 360.0
    if np.isclose(lon, 180.0):
        return "180°"
    if lon < 180.0:
        return f"{lon:g}°E"
    return f"{360.0 - lon:g}°W"


def select_product_record(raw: pd.DataFrame) -> pd.DataFrame:
    """Use consolidated ORAS5 through 2014 and operational ORAS5 from 2015."""
    selected = raw.loc[
        ((raw["product_type"] == "consolidated") & (raw["year"] <= 2014))
        | ((raw["product_type"] == "operational") & (raw["year"] >= 2015))
    ].copy()
    selected["lon"] = selected["requested_lon"].astype(float) % 360.0
    selected = selected.loc[
        selected["time"].between(START, END)
        & selected["lon"].between(LON_START, LON_END)
    ].copy()
    return selected.sort_values(["lon", "time"])


def validate_input(data: pd.DataFrame) -> None:
    """Check coordinates, units, time coverage, and monthly completeness."""
    if data.empty:
        raise ValueError("No ORAS5 D20 records remain after selection")
    if not np.allclose(data["native_lat"].dropna().unique(), 0.0):
        raise ValueError("The selected ORAS5 D20 transect is not on the equator")
    if data.duplicated(["time", "lon"]).any():
        raise ValueError("Duplicate ORAS5 records exist for the same month and longitude")

    expected_time = pd.date_range(START, END, freq="MS")
    expected_count = len(expected_time)
    expected_lons = np.arange(LON_START, LON_END + 0.1, 5.0)
    actual_lons = np.sort(data["lon"].unique())
    if not np.array_equal(actual_lons, expected_lons):
        raise ValueError(
            f"Unexpected longitude grid: expected {expected_lons.tolist()}, "
            f"found {actual_lons.tolist()}"
        )

    for lon, group in data.groupby("lon"):
        if group["d20_m"].isna().any():
            raise ValueError(f"Missing D20 values at {format_longitude(lon)}")
        times = pd.DatetimeIndex(group["time"])
        if len(group) != expected_count or not times.equals(expected_time):
            raise ValueError(
                f"Incomplete monthly series at {format_longitude(lon)}: "
                f"{len(group)} records, expected {expected_count}"
            )

    d20_min = float(data["d20_m"].min())
    d20_max = float(data["d20_m"].max())
    if d20_min < 0.0 or d20_max > 400.0:
        raise ValueError(f"Implausible ORAS5 D20 range: {d20_min:.2f} to {d20_max:.2f} m")


def calculate_anomalies(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate same-month climatological and detrended D20 anomalies."""
    pieces: list[pd.DataFrame] = []
    for (lon, month), group in data.groupby(["lon", "month"], sort=True):
        group = group.sort_values("time").copy()
        baseline = group["year"].between(BASELINE_START, BASELINE_END)
        if int(baseline.sum()) != BASELINE_END - BASELINE_START + 1:
            raise ValueError(
                f"Expected 35 baseline years at {format_longitude(lon)}, month {month}; "
                f"found {int(baseline.sum())}"
            )

        climatology = float(group.loc[baseline, "d20_m"].mean())
        raw_anomaly = group["d20_m"].to_numpy(dtype=float) - climatology
        decimal_year = (
            group["year"].to_numpy(dtype=float)
            + (group["month"].to_numpy(dtype=float) - 0.5) / 12.0
        )
        slope, intercept = np.polyfit(
            decimal_year[baseline.to_numpy()],
            raw_anomaly[baseline.to_numpy()],
            1,
        )
        trend = slope * decimal_year + intercept

        group["d20_climatology_m"] = climatology
        group["d20_raw_anomaly_m"] = raw_anomaly
        group["d20_linear_trend_m"] = trend
        group["d20_detrended_anomaly_m"] = raw_anomaly - trend
        group["linear_trend_slope_m_per_year"] = float(slope)
        group["baseline_years"] = f"{BASELINE_START}-{BASELINE_END}"
        pieces.append(group)

    result = pd.concat(pieces, ignore_index=True)
    result = result.sort_values(["time", "lon"]).reset_index(drop=True)
    keep = [
        "time",
        "year",
        "month",
        "lon",
        "native_lat",
        "native_lon",
        "d20_m",
        "d20_climatology_m",
        "d20_raw_anomaly_m",
        "d20_linear_trend_m",
        "d20_detrended_anomaly_m",
        "linear_trend_slope_m_per_year",
        "baseline_years",
        "product_type",
    ]
    return result[keep]


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 10.0,
            "axes.titlesize": 14.0,
            "axes.labelsize": 11.0,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "axes.linewidth": 0.85,
            "axes.unicode_minus": False,
        }
    )


def plot_hovmoller(data: pd.DataFrame) -> tuple[Path, Path, float]:
    field = (
        data.pivot(index="time", columns="lon", values="d20_detrended_anomaly_m")
        .sort_index()
        .sort_index(axis=1)
    )
    if field.isna().any().any():
        raise ValueError("The Hovmöller field contains missing values")

    times = pd.DatetimeIndex(field.index)
    longitudes = field.columns.to_numpy(dtype=float)
    values = field.to_numpy(dtype=float)

    robust_limit = float(np.nanpercentile(np.abs(values), 99.0))
    color_limit = max(30.0, float(np.ceil(robust_limit / 5.0) * 5.0))

    setup_style()
    fig, ax = plt.subplots(figsize=(9.2, 12.0), constrained_layout=False)
    row = np.arange(len(times), dtype=float)
    mesh = ax.pcolormesh(
        longitudes,
        row,
        values,
        cmap="RdBu_r",
        vmin=-color_limit,
        vmax=color_limit,
        shading="nearest",
        rasterized=True,
    )

    ax.set_xlim(LON_START - 2.5, LON_END + 2.5)
    ax.set_ylim(len(times) - 0.5, -0.5)
    xticks = [130, 150, 170, 180, 200, 220, 240, 260, 275]
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_longitude(value) for value in xticks])
    ax.set_xlabel("Longitude along the equator")

    tick_dates = list(pd.date_range("1980-01-01", "2025-01-01", freq="5YS"))
    tick_dates.append(END)
    tick_positions = [int(np.where(times == date)[0][0]) for date in tick_dates]
    tick_labels = [date.strftime("%Y") for date in tick_dates[:-1]] + ["Jun 2026"]
    ax.set_yticks(tick_positions)
    ax.set_yticklabels(tick_labels)
    ax.set_ylabel("Time")

    for xpos in [180, 220, 240]:
        ax.axvline(xpos, color="white", lw=0.55, alpha=0.34)
    for ypos in tick_positions:
        ax.axhline(ypos, color="0.15", lw=0.35, alpha=0.22)

    ax.set_title(
        "Equatorial Pacific ORAS5 D20 anomaly, January 1980–June 2026",
        weight="bold",
        pad=17,
    )
    ax.text(
        0.5,
        1.006,
        "Monthly 20 °C isotherm-depth anomaly at 0°; "
        "1980–2014 same-calendar-month climatology and linear trend removed",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.3,
        color="0.30",
    )

    colorbar = fig.colorbar(mesh, ax=ax, orientation="vertical", pad=0.025, shrink=0.96)
    colorbar.set_label("D20 anomaly (m)")
    colorbar.ax.text(
        0.5,
        1.015,
        "Deeper",
        transform=colorbar.ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#9D3F35",
    )
    colorbar.ax.text(
        0.5,
        -0.025,
        "Shallower",
        transform=colorbar.ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.5,
        color="#346D9A",
    )

    fig.text(
        0.105,
        0.018,
        "Source: Copernicus Climate Change Service / ECMWF ORAS5 time-series "
        "(depth_of_20_c_isotherm). Positive values indicate thermocline deepening.",
        ha="left",
        va="bottom",
        fontsize=8.4,
        color="0.32",
    )
    fig.subplots_adjust(left=0.105, right=0.875, top=0.94, bottom=0.07)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUTPUT_DIR / f"{OUTPUT_STEM}.png"
    pdf = OUTPUT_DIR / f"{OUTPUT_STEM}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.18)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return png, pdf, color_limit


def main() -> int:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing ORAS5 input: {INPUT_CSV}")

    raw = pd.read_csv(INPUT_CSV, parse_dates=["time"])
    selected = select_product_record(raw)
    validate_input(selected)
    anomalies = calculate_anomalies(selected)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    anomalies.to_csv(OUTPUT_CSV, index=False, date_format="%Y-%m-%d")
    png, pdf, color_limit = plot_hovmoller(anomalies)

    metadata = {
        "source": "CDS ORAS5 time-series",
        "variable": "depth_of_20_c_isotherm",
        "latitude": "0 degrees",
        "longitude_range": "130E-85W",
        "longitude_step_degrees": 5,
        "time_range": "1980-01 to 2026-06",
        "record_count": int(len(anomalies)),
        "month_count": int(anomalies["time"].nunique()),
        "longitude_count": int(anomalies["lon"].nunique()),
        "anomaly_method": (
            "At each longitude and calendar month, subtract the 1980-2014 "
            "climatology and remove the linear trend fitted over 1980-2014."
        ),
        "positive_sign": "D20 deepening",
        "negative_sign": "D20 shoaling",
        "color_limit_m": color_limit,
        "input": str(INPUT_CSV),
        "derived_csv": str(OUTPUT_CSV),
        "png": str(png),
        "pdf": str(pdf),
    }
    OUTPUT_METADATA.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"records={len(anomalies)}")
    print(f"months={anomalies['time'].nunique()}")
    print(f"longitudes={anomalies['lon'].nunique()}")
    print(
        "anomaly_range_m="
        f"{anomalies['d20_detrended_anomaly_m'].min():.2f},"
        f"{anomalies['d20_detrended_anomaly_m'].max():.2f}"
    )
    print(f"color_limit_m={color_limit:.1f}")
    print(OUTPUT_CSV)
    print(png)
    print(pdf)
    print(OUTPUT_METADATA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
