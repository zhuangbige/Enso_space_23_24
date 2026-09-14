#!/usr/bin/env python3
"""Compare threshold H20 with fixed-depth 0-500 m upper-ocean heat content.

Storage definitions are evaluated over the same eastern equatorial Pacific
box (5S-5N, 140W-80W):

  H20  = rho Cp integral max(T-20 C, 0) dV over 0-300 m
  Q500 = rho Cp integral T dV over 0-500 m

Q500 is named after the formula in the supplied screenshot.  It is a
fixed-depth upper-ocean heat-content measure, not a 20 C-isotherm-bounded
quantity.  All comparisons use same-calendar-month detrended anomalies, so
the arbitrary zero of Celsius does not affect the anomaly results.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
APDRC_URL = "http://apdrc.soest.hawaii.edu:80/dods/public_data/SODA/soda_3.15.2/monthly_t"
RECENT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_east_h20_q300_q500_recent_2023_2024.csv"
)
HISTORICAL_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_east_h20_q300_q500_historical_1980_2022.csv"
)
COMBINED_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_east_h20_q300_q500_monthly_1980_2024.csv"
)
PHASE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_h20_q500_three_event_phase_sensitivity.csv"
)
EVENT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_h20_q500_13event_development_sensitivity.csv"
)
SUMMARY_JSON = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_h20_q500_sensitivity_summary.json"
)
OUT_DIR = ROOT / "outputs/research_2026/h20_q500_sensitivity"
FIGURE_PNG = OUT_DIR / "h20_q500_storage_sensitivity.png"
FIGURE_PDF = OUT_DIR / "h20_q500_storage_sensitivity.pdf"

RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
BASELINE = (1980, 2014)
EVENTS = (1997, 2015, 2023)
EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    selected = np.flatnonzero((values > lower) & (values < upper))
    if selected.size == 0 or not np.all(np.diff(selected) == 1):
        raise ValueError(f"No contiguous grid cells in {lower}..{upper}")
    return slice(int(selected[0]), int(selected[-1]) + 1)


def depth_overlap(depth: np.ndarray, maximum: float) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    bounds = np.empty(depth.size + 1, dtype=float)
    bounds[0] = 0.0
    bounds[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    bounds[-1] = depth[-1] + 0.5 * (depth[-1] - depth[-2])
    return np.maximum(
        0.0,
        np.minimum(bounds[1:], maximum) - np.maximum(bounds[:-1], 0.0),
    )


def grid_cell_areas(latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    latitude = np.asarray(latitude, dtype=float)
    longitude = np.asarray(longitude, dtype=float)
    dlat = float(np.median(np.diff(latitude)))
    dlon = float(np.median(np.diff(longitude)))
    south = np.deg2rad(latitude - dlat / 2.0)
    north = np.deg2rad(latitude + dlat / 2.0)
    strip = EARTH_RADIUS**2 * (np.sin(north) - np.sin(south))
    return strip[:, None] * np.deg2rad(dlon) * np.ones((1, longitude.size))


def compute_metrics(
    temperature: np.ndarray,
    depth: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> pd.DataFrame:
    temperature = np.asarray(temperature, dtype=float)
    temperature[(temperature < -10.0) | (temperature > 50.0)] = np.nan
    area = grid_cell_areas(latitude, longitude)
    dz300 = depth_overlap(depth, 300.0)[None, :, None, None]
    dz500 = depth_overlap(depth, 500.0)[None, :, None, None]
    warm = np.maximum(temperature - 20.0, 0.0)
    factor = RHO0 * CP0
    h20_zj = factor * np.nansum(warm * dz300 * area[None, None, :, :], axis=(1, 2, 3)) / 1.0e21
    q300_zj = factor * np.nansum(temperature * dz300 * area[None, None, :, :], axis=(1, 2, 3)) / 1.0e21
    q500_zj = factor * np.nansum(temperature * dz500 * area[None, None, :, :], axis=(1, 2, 3)) / 1.0e21
    domain_area = float(np.sum(area))
    return pd.DataFrame(
        {
            "east_h20_0_300_raw_zj": h20_zj,
            "east_q300_raw_zj": q300_zj,
            "east_q500_raw_zj": q500_zj,
            "east_h20_0_300_raw_jm2": h20_zj * 1.0e21 / domain_area,
            "east_q300_raw_jm2": q300_zj * 1.0e21 / domain_area,
            "east_q500_raw_jm2": q500_zj * 1.0e21 / domain_area,
        }
    )


def fetch_historical() -> pd.DataFrame:
    import netCDF4

    print(f"Opening APDRC SODA3 monthly temperature: {APDRC_URL}", flush=True)
    source = netCDF4.Dataset(APDRC_URL)
    try:
        depth_all = np.asarray(source.variables["lev"][:], dtype=float)
        lat_all = np.asarray(source.variables["lat"][:], dtype=float)
        lon_all = np.asarray(source.variables["lon"][:], dtype=float) % 360.0
        # Keep the first centre below 500 m so layer interfaces bracket the
        # requested fixed-depth boundary exactly.
        first_below = int(np.searchsorted(depth_all, 500.0, side="right"))
        zslice = slice(0, min(first_below + 1, depth_all.size))
        yslice = contiguous_slice(lat_all, -5.0, 5.0)
        xslice = contiguous_slice(lon_all, 220.0, 280.0)
        depth = depth_all[zslice]
        latitude = lat_all[yslice]
        longitude = lon_all[xslice]
        print(
            f"Subset: {depth.size} levels to {depth[-1]:.1f} m, "
            f"{latitude.size} latitudes, {longitude.size} longitudes",
            flush=True,
        )
        pieces: list[pd.DataFrame] = []
        for start_year in range(1980, 2023, 5):
            end_year = min(start_year + 4, 2022)
            start_index = (start_year - 1980) * 12
            stop_index = (end_year - 1980 + 1) * 12
            block = np.asarray(
                source.variables["temp"][start_index:stop_index, zslice, yslice, xslice],
                dtype=float,
            )
            metrics = compute_metrics(block, depth, latitude, longitude)
            times = pd.DatetimeIndex(
                [
                    pd.Timestamp(year, month, 15)
                    for year in range(start_year, end_year + 1)
                    for month in range(1, 13)
                ]
            )
            if len(metrics) != len(times):
                raise ValueError("Historical SODA3 block has an unexpected time size")
            metrics.insert(0, "month", times.month)
            metrics.insert(0, "year", times.year)
            metrics.insert(0, "time", times)
            pieces.append(metrics)
            print(f"  computed {start_year}-{end_year}", flush=True)
    finally:
        source.close()
    output = pd.concat(pieces, ignore_index=True).sort_values("time")
    HISTORICAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(HISTORICAL_CSV, index=False, float_format="%.10g")
    print(f"Wrote {HISTORICAL_CSV}", flush=True)
    return output


def same_month_detrended(
    values: np.ndarray, times: pd.DatetimeIndex
) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in range(1, 13):
        fit = (
            (times.month == month)
            & (times.year >= BASELINE[0])
            & (times.year <= BASELINE[1])
            & np.isfinite(values)
        )
        apply = (times.month == month) & np.isfinite(values)
        x = times.year[fit].astype(float)
        design = np.column_stack([np.ones(fit.sum()), x])
        intercept, slope = np.linalg.lstsq(design, values[fit], rcond=None)[0]
        output[apply] = values[apply] - (
            intercept + slope * times.year[apply].astype(float)
        )
    return output


def add_anomalies(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy().sort_values("time").reset_index(drop=True)
    output["time"] = pd.to_datetime(output["time"])
    times = pd.DatetimeIndex(output.time)
    for metric in ("east_h20_0_300", "east_q300", "east_q500"):
        output[f"{metric}_anom_zj"] = same_month_detrended(
            output[f"{metric}_raw_zj"].to_numpy(dtype=float), times
        )
        output[f"{metric}_anom_jm2"] = same_month_detrended(
            output[f"{metric}_raw_jm2"].to_numpy(dtype=float), times
        )
    return output


def phase_selection(table: pd.DataFrame, event_year: int, phase: str) -> pd.DataFrame:
    if phase == "development_Jan0_Jun0":
        selected = table.loc[
            table.year.eq(event_year) & table.month.between(1, 6)
        ]
    elif phase == "development_Jun0_Nov0":
        selected = table.loc[
            table.year.eq(event_year) & table.month.between(6, 11)
        ]
    elif phase == "decay_Jan1_May1":
        selected = table.loc[
            table.year.eq(event_year + 1) & table.month.between(1, 5)
        ]
    elif phase == "mature_decay_Dec0_May1":
        selected = table.loc[
            (table.year.eq(event_year) & table.month.eq(12))
            | (table.year.eq(event_year + 1) & table.month.between(1, 5))
        ]
    else:
        raise KeyError(phase)
    return selected.sort_values("time")


def build_phase_table(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str | bool]] = []
    phases = (
        "development_Jan0_Jun0",
        "development_Jun0_Nov0",
        "decay_Jan1_May1",
        "mature_decay_Dec0_May1",
    )
    for event_year in EVENTS:
        for phase in phases:
            selected = phase_selection(table, event_year, phase)
            if selected.empty:
                raise ValueError(f"No data for {event_year} {phase}")
            h20 = float(
                selected.east_h20_0_300_anom_zj.iloc[-1]
                - selected.east_h20_0_300_anom_zj.iloc[0]
            )
            q300 = float(
                selected.east_q300_anom_zj.iloc[-1]
                - selected.east_q300_anom_zj.iloc[0]
            )
            q500 = float(
                selected.east_q500_anom_zj.iloc[-1]
                - selected.east_q500_anom_zj.iloc[0]
            )
            rows.append(
                {
                    "event_year": event_year,
                    "phase": phase,
                    "start": selected.time.iloc[0],
                    "end": selected.time.iloc[-1],
                    "h20_change_zj": h20,
                    "q300_change_zj": q300,
                    "q500_change_zj": q500,
                    "q500_minus_h20_zj": q500 - h20,
                    "same_sign_h20_q500": bool(np.sign(h20) == np.sign(q500)),
                }
            )
    return pd.DataFrame(rows)


def build_event_table(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for event_year in EVENT_YEARS:
        selected = phase_selection(table, event_year, "development_Jan0_Jun0")
        rows.append(
            {
                "event_year": event_year,
                "h20_change_zj": float(
                    selected.east_h20_0_300_anom_zj.iloc[-1]
                    - selected.east_h20_0_300_anom_zj.iloc[0]
                ),
                "q300_change_zj": float(
                    selected.east_q300_anom_zj.iloc[-1]
                    - selected.east_q300_anom_zj.iloc[0]
                ),
                "q500_change_zj": float(
                    selected.east_q500_anom_zj.iloc[-1]
                    - selected.east_q500_anom_zj.iloc[0]
                ),
            }
        )
    return pd.DataFrame(rows)


def correlation(x: pd.Series, y: pd.Series) -> float:
    return float(np.corrcoef(x.to_numpy(dtype=float), y.to_numpy(dtype=float))[0, 1])


def build_summary(
    monthly: pd.DataFrame,
    phases: pd.DataFrame,
    events: pd.DataFrame,
) -> dict[str, object]:
    dev = phases.loc[phases.phase.eq("development_Jan0_Jun0")].set_index("event_year")
    decay = phases.loc[phases.phase.eq("decay_Jan1_May1")].set_index("event_year")
    monthly_core = monthly.loc[
        monthly.year.between(1980, 2024),
        ["east_h20_0_300_anom_zj", "east_q300_anom_zj", "east_q500_anom_zj"],
    ].dropna()
    h15, h23 = float(dev.loc[2015, "h20_change_zj"]), float(dev.loc[2023, "h20_change_zj"])
    q15, q23 = float(dev.loc[2015, "q500_change_zj"]), float(dev.loc[2023, "q500_change_zj"])
    return {
        "storage_definitions": {
            "h20": "rho0*Cp*integral(max(T-20C,0)dV), 0-300 m",
            "q500": "rho0*Cp*integral(T dV), 0-500 m",
            "domain": "5S-5N, 140W-80W",
            "anomaly": "same-calendar-month linear detrend, 1980-2014",
        },
        "monthly_anomaly_correlations": {
            "h20_vs_q300": correlation(
                monthly_core.east_h20_0_300_anom_zj,
                monthly_core.east_q300_anom_zj,
            ),
            "h20_vs_q500": correlation(
                monthly_core.east_h20_0_300_anom_zj,
                monthly_core.east_q500_anom_zj,
            ),
            "q300_vs_q500": correlation(
                monthly_core.east_q300_anom_zj,
                monthly_core.east_q500_anom_zj,
            ),
        },
        "monthly_standard_deviation_zj": {
            "h20": float(monthly_core.east_h20_0_300_anom_zj.std(ddof=1)),
            "q300": float(monthly_core.east_q300_anom_zj.std(ddof=1)),
            "q500": float(monthly_core.east_q500_anom_zj.std(ddof=1)),
        },
        "event_development_correlations_13events": {
            "pearson_h20_vs_q500": correlation(events.h20_change_zj, events.q500_change_zj),
            "spearman_h20_vs_q500": correlation(
                events.h20_change_zj.rank(), events.q500_change_zj.rank()
            ),
        },
        "development_2015_2023_closeness": {
            "h20_absolute_difference_zj": abs(h15 - h23),
            "h20_fraction_of_pair_mean": abs(h15 - h23) / np.mean(np.abs([h15, h23])),
            "q500_absolute_difference_zj": abs(q15 - q23),
            "q500_fraction_of_pair_mean": abs(q15 - q23) / np.mean(np.abs([q15, q23])),
        },
        "development_order": {
            "h20_descending": dev.h20_change_zj.sort_values(ascending=False).index.astype(int).tolist(),
            "q500_descending": dev.q500_change_zj.sort_values(ascending=False).index.astype(int).tolist(),
        },
        "decay_order_most_negative_first": {
            "h20": decay.h20_change_zj.sort_values().index.astype(int).tolist(),
            "q500": decay.q500_change_zj.sort_values().index.astype(int).tolist(),
        },
        "all_three_event_phase_signs_match": bool(phases.same_sign_h20_q500.all()),
    }


def plot_results(phases: pd.DataFrame, events: pd.DataFrame) -> None:
    os.environ.setdefault(
        "MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig")
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.2,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    colors = {"H20": "#2C7FB8", "Q500": "#D95F0E"}
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.0), constrained_layout=True)
    x = np.arange(len(EVENTS), dtype=float)
    width = 0.36
    for axis, phase, title in (
        (axes[0], "development_Jan0_Jun0", "a  Development: Jan(0) to Jun(0)"),
        (axes[1], "decay_Jan1_May1", "b  Decay: Jan(+1) to May(+1)"),
    ):
        selected = phases.loc[phases.phase.eq(phase)].set_index("event_year").loc[list(EVENTS)]
        axis.bar(x - width / 2, selected.h20_change_zj, width, color=colors["H20"], label="H20 (0-300 m)")
        axis.bar(x + width / 2, selected.q500_change_zj, width, color=colors["Q500"], label="Q500 (0-500 m)")
        axis.axhline(0.0, color="#555555", linewidth=0.8)
        axis.set_xticks(x, [str(year) for year in EVENTS])
        axis.set_ylabel("Storage-anomaly change (ZJ)")
        axis.set_title(title, loc="left", fontweight="bold")
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.6)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8)

    axes[2].scatter(events.h20_change_zj, events.q500_change_zj, color="#999999", s=28)
    for row in events.itertuples(index=False):
        if row.event_year in EVENTS:
            color = {1997: "#B33A3A", 2015: "#D17A22", 2023: "#2878B5"}[row.event_year]
            axes[2].scatter(row.h20_change_zj, row.q500_change_zj, color=color, s=52, zorder=3)
            offset = {1997: (4, 4), 2015: (-38, -14), 2023: (6, 6)}[row.event_year]
            axes[2].annotate(str(row.event_year), (row.h20_change_zj, row.q500_change_zj), xytext=offset, textcoords="offset points", color=color, fontweight="bold")
    slope, intercept = np.polyfit(events.h20_change_zj, events.q500_change_zj, 1)
    line_x = np.linspace(events.h20_change_zj.min(), events.h20_change_zj.max(), 100)
    axes[2].plot(line_x, intercept + slope * line_x, color="#333333", linewidth=1.0)
    r = correlation(events.h20_change_zj, events.q500_change_zj)
    axes[2].text(0.03, 0.96, f"r = {r:.2f}; n = {len(events)}", transform=axes[2].transAxes, va="top")
    axes[2].axhline(0.0, color="#BBBBBB", linewidth=0.7)
    axes[2].axvline(0.0, color="#BBBBBB", linewidth=0.7)
    axes[2].set_xlabel("H20 Jan-Jun change (ZJ)")
    axes[2].set_ylabel("Q500 Jan-Jun change (ZJ)")
    axes[2].set_title("c  Thirteen warm events", loc="left", fontweight="bold")
    axes[2].grid(color="#E0E0E0", linewidth=0.6)
    axes[2].spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "Storage-definition sensitivity: threshold H20 versus fixed-depth Q500\n"
        "SODA3.15.2; 5S-5N, 140W-80W; 1980-2014 calendar-month detrended anomalies",
        fontweight="bold",
        fontsize=11.4,
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def validate_against_existing(monthly: pd.DataFrame) -> dict[str, float]:
    existing_path = (
        ROOT
        / "data/derived/research_2026/"
        "enso_1997_2015_2023_warm_heat_fate_monthly.csv"
    )
    existing = pd.read_csv(existing_path, parse_dates=["time"])
    merged = monthly[["time", "east_h20_0_300_raw_zj"]].merge(
        existing[["time", "east_h20_raw_zj"]], on="time", how="inner"
    )
    difference = merged.east_h20_0_300_raw_zj - merged.east_h20_raw_zj
    return {
        "n_months": int(len(merged)),
        "correlation": correlation(
            merged.east_h20_0_300_raw_zj, merged.east_h20_raw_zj
        ),
        "max_absolute_difference_zj": float(np.max(np.abs(difference))),
        "mean_absolute_difference_zj": float(np.mean(np.abs(difference))),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-historical", action="store_true")
    parser.add_argument("--skip-plot", action="store_true")
    parser.add_argument("--recent-csv", type=Path, default=RECENT_CSV)
    args = parser.parse_args()
    if HISTORICAL_CSV.exists() and not args.force_historical:
        historical = pd.read_csv(HISTORICAL_CSV, parse_dates=["time"])
        print(f"Using cached {HISTORICAL_CSV}", flush=True)
    else:
        historical = fetch_historical()
    if not args.recent_csv.exists():
        raise FileNotFoundError(
            f"Recent extraction is missing: {args.recent_csv}. "
            "Run extract_soda3_q500_recent_remote.py first."
        )
    recent = pd.read_csv(args.recent_csv, parse_dates=["time"])
    combined = pd.concat([historical, recent], ignore_index=True).sort_values("time")
    combined = combined.drop_duplicates("time", keep="last").reset_index(drop=True)
    expected = pd.date_range("1980-01-01", "2024-12-01", freq="MS") + pd.Timedelta(days=14)
    if not pd.DatetimeIndex(combined.time).equals(expected):
        raise ValueError("Combined 1980-2024 monthly time axis is incomplete")
    monthly = add_anomalies(combined)
    phases = build_phase_table(monthly)
    events = build_event_table(monthly)
    summary = build_summary(monthly, phases, events)
    summary["validation_against_existing_h20"] = validate_against_existing(monthly)
    COMBINED_CSV.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(COMBINED_CSV, index=False, float_format="%.10g")
    phases.to_csv(PHASE_CSV, index=False, float_format="%.10g")
    events.to_csv(EVENT_CSV, index=False, float_format="%.10g")
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not args.skip_plot:
        plot_results(phases, events)
    print("\nThree-event phase sensitivity (ZJ):")
    print(phases.to_string(index=False))
    print("\nSummary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {SUMMARY_JSON}")
    if not args.skip_plot:
        print(f"Wrote {FIGURE_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
