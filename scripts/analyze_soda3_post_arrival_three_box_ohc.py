#!/usr/bin/env python3
"""Compare post-arrival three-box 0--300 m OHC in 1997, 2015 and 2023.

The arrival result is taken from the existing Jan(0)--Jun(0) 140W H20-flux
diagnostic.  This script asks what ocean heat state exists immediately after
that arrival phase.  The primary post-arrival window is Jul(0)--Sep(0), with
May--Jul and Aug--Oct retained as sensitivity windows.

Raw OHC is the fixed-depth heat content relative to 0 degC already stored in
the local SODA3.15.2 OHC file.  Because the three longitude boxes have unequal
areas, the primary absolute comparison is area-mean OHC (GJ m-2).  Integrated
reservoir energy (ZJ) is also exported, but is not used to compare box warmth.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


INPUT_NC = (
    ROOT
    / "data/interim/research_2026/soda3_ohc/"
    / "soda3_ohc_0_100_0_300_1980_2024.nc"
)
ARRIVAL_CSV = (
    ROOT
    / "data/derived/research_2026/"
    / "enso_1997_2015_2023_warm_heat_fate_phase_summary.csv"
)
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_post_arrival_three_box_ohc"
MONTHLY_CSV = DERIVED / "soda3_post_arrival_three_box_ohc_monthly.csv"
SUMMARY_CSV = DERIVED / "soda3_post_arrival_three_box_ohc_summary.csv"
SENSITIVITY_CSV = DERIVED / "soda3_post_arrival_three_box_ohc_window_sensitivity.csv"
DOMAIN_SENSITIVITY_CSV = DERIVED / "soda3_post_arrival_three_box_ohc_domain_sensitivity.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_post_arrival_three_box_ohc_diagnostics.json"
FIGURE_PNG = OUT / "soda3_post_arrival_three_box_ohc_comparison_cn.png"
FIGURE_PDF = OUT / "soda3_post_arrival_three_box_ohc_comparison_cn.pdf"
HOVMOLLER_PNG = OUT / "soda3_ohc300_absolute_hovmoller_1997_2015_2023_cn.png"
HOVMOLLER_PDF = OUT / "soda3_ohc300_absolute_hovmoller_1997_2015_2023_cn.pdf"
HOVMOLLER_CSV = DERIVED / "soda3_ohc300_absolute_hovmoller_1997_2015_2023.csv"
ANOMALY_HOVMOLLER_PNG = OUT / "soda3_ohc300_anomaly_hovmoller_1997_2015_2023_cn.png"
ANOMALY_HOVMOLLER_PDF = OUT / "soda3_ohc300_anomaly_hovmoller_1997_2015_2023_cn.pdf"
ANOMALY_HOVMOLLER_CSV = DERIVED / "soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv"

EVENTS = (1997, 2015, 2023)
BASELINE = (1980, 2014)
LAT_BOUNDS = (-10.0, 5.0)
BOXES = {
    "西箱": (160.0, 180.0),
    "中箱": (180.0, 220.0),
    "东箱": (220.0, 280.0),
}
WINDOWS = {
    "early_Jan_Feb": (1, 2),
    "post_May_Jul": (5, 7),
    "post_Jul_Sep": (7, 9),
    "post_Aug_Oct": (8, 10),
    "mature_Oct_Nov": (10, 11),
}
PRIMARY_WINDOW = "post_Jul_Sep"
EARTH_RADIUS_M = 6_371_000.0
EVENT_COLORS = {1997: "#A61E2D", 2015: "#2574A9", 2023: "#E07A00"}
BOX_COLORS = {"西箱": "#355F73", "中箱": "#2E86AB", "东箱": "#E07A00"}


def configure_fonts() -> None:
    candidates = (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    )
    family = "DejaVu Sans"
    for path in candidates:
        if path.exists():
            fm.fontManager.addfont(path)
            family = fm.FontProperties(fname=path).get_name()
            break
    plt.rcParams.update(
        {
            "font.family": family,
            "axes.unicode_minus": False,
            "axes.titleweight": "bold",
            "axes.labelcolor": "#102A3C",
            "text.color": "#102A3C",
            "xtick.color": "#35576C",
            "ytick.color": "#35576C",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def coordinate_bounds(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size < 2 or not np.all(np.diff(values) > 0):
        raise ValueError("Coordinates must be one-dimensional and increasing")
    bounds = np.empty(values.size + 1, dtype=float)
    bounds[1:-1] = 0.5 * (values[:-1] + values[1:])
    bounds[0] = values[0] - 0.5 * (values[1] - values[0])
    bounds[-1] = values[-1] + 0.5 * (values[-1] - values[-2])
    return bounds


def cell_areas(latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    lat_bounds = np.deg2rad(np.clip(coordinate_bounds(latitude), -90.0, 90.0))
    lon_bounds = np.deg2rad(coordinate_bounds(longitude))
    meridional = np.sin(lat_bounds[1:]) - np.sin(lat_bounds[:-1])
    zonal = np.diff(lon_bounds)
    return (EARTH_RADIUS_M**2) * meridional[:, None] * zonal[None, :]


def same_month_detrended(values: np.ndarray, times: pd.DatetimeIndex) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    result = np.full(data.shape, np.nan, dtype=float)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    baseline_mask = (years >= BASELINE[0]) & (years <= BASELINE[1])
    for month in range(1, 13):
        target = months == month
        baseline = target & baseline_mask & np.isfinite(data)
        if baseline.sum() < 20:
            raise ValueError(f"Insufficient baseline values for month {month}")
        center_year = float(np.mean(years[baseline]))
        x = years[baseline] - center_year
        climatology = float(np.mean(data[baseline]))
        slope = float(np.sum(x * (data[baseline] - climatology)) / np.sum(x**2))
        result[target] = data[target] - climatology - slope * (years[target] - center_year)
    return result


def derive_monthly(
    lat_bounds: tuple[float, float] = LAT_BOUNDS,
) -> tuple[pd.DataFrame, dict[str, float]]:
    with xr.open_dataset(INPUT_NC, engine="netcdf4", chunks=None) as dataset:
        required = {"ohc_300m", "time", "lat", "lon"}
        if not required.issubset(set(dataset.variables)):
            raise KeyError(f"Missing variables: {sorted(required - set(dataset.variables))}")
        field = dataset["ohc_300m"].sel(lat=slice(*lat_bounds)).load()
        times = pd.DatetimeIndex(field.time.values)
        if times.min().year > 1980 or times.max() < pd.Timestamp("2023-12-01"):
            raise ValueError("OHC record does not cover the requested baseline and events")
        if field.attrs.get("units") != "J m-2":
            raise ValueError(f"Unexpected OHC units: {field.attrs.get('units')}")

        rows: list[dict[str, float | int | str | pd.Timestamp]] = []
        wet_area: dict[str, float] = {}
        completeness: dict[str, float] = {}
        for box, (lon0, lon1) in BOXES.items():
            subset = field.sel(lon=slice(lon0, lon1))
            area = xr.DataArray(
                cell_areas(subset.lat.values, subset.lon.values),
                dims=("lat", "lon"),
                coords={"lat": subset.lat, "lon": subset.lon},
            )
            fixed_wet = subset.notnull().all("time")
            valid_fraction = subset.notnull().mean(("lat", "lon"))
            completeness[box] = float(valid_fraction.min().values)
            wet_area[box] = float(area.where(fixed_wet).sum().values)
            total_j = (subset.where(fixed_wet) * area.where(fixed_wet)).sum(
                ("lat", "lon"), skipna=True
            )
            mean_jm2 = total_j / wet_area[box]
            for timestamp, mean_value, total_value in zip(
                times,
                mean_jm2.values,
                total_j.values,
                strict=True,
            ):
                rows.append(
                    {
                        "time": timestamp,
                        "year": int(timestamp.year),
                        "month": int(timestamp.month),
                        "box": box,
                        "ohc300_abs_gjm2": float(mean_value / 1.0e9),
                        "ohc300_abs_zj": float(total_value / 1.0e21),
                        "wet_area_1e12_m2": wet_area[box] / 1.0e12,
                    }
                )

    monthly = pd.DataFrame(rows).sort_values(["box", "time"]).reset_index(drop=True)
    for box in BOXES:
        target = monthly.box.eq(box)
        box_times = pd.DatetimeIndex(monthly.loc[target, "time"])
        monthly.loc[target, "ohc300_anom_gjm2"] = same_month_detrended(
            monthly.loc[target, "ohc300_abs_gjm2"].to_numpy(), box_times
        )
        monthly.loc[target, "ohc300_anom_zj"] = same_month_detrended(
            monthly.loc[target, "ohc300_abs_zj"].to_numpy(), box_times
        )
    diagnostics = {
        "n_months": int(monthly.time.nunique()),
        "time_start": str(pd.to_datetime(monthly.time).min().date()),
        "time_end": str(pd.to_datetime(monthly.time).max().date()),
        "latitude_bounds": list(lat_bounds),
        "minimum_valid_cell_fraction": min(completeness.values()),
        **{f"wet_area_{box}_1e12_m2": area / 1.0e12 for box, area in wet_area.items()},
    }
    return monthly, diagnostics


def period_mean(monthly: pd.DataFrame, event: int, first: int, last: int) -> pd.DataFrame:
    selected = monthly.loc[
        monthly.year.eq(event) & monthly.month.between(first, last)
    ]
    if selected.groupby("box").size().min() != last - first + 1:
        raise ValueError(f"Incomplete {event} window {first}-{last}")
    return (
        selected.groupby("box", sort=False)[
            ["ohc300_abs_gjm2", "ohc300_abs_zj", "ohc300_anom_gjm2", "ohc300_anom_zj"]
        ]
        .mean()
        .reset_index()
    )


def build_summaries(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    arrival = pd.read_csv(ARRIVAL_CSV)
    arrival = arrival.loc[
        arrival.baseline.eq("1980-2014")
        & arrival.phase.eq("development_Jan0_Jun0")
        & arrival.event_year.isin(EVENTS),
        ["event_year", "q20_140w_east_zj", "east_h20_change_zj"],
    ].set_index("event_year")
    rows: list[dict[str, float | int | str]] = []
    sensitivity_rows: list[dict[str, float | int | str]] = []
    for event in EVENTS:
        early = period_mean(monthly, event, *WINDOWS["early_Jan_Feb"]).set_index("box")
        for window, bounds in WINDOWS.items():
            state = period_mean(monthly, event, *bounds).set_index("box")
            for box in BOXES:
                record = {
                    "event_year": event,
                    "window": window,
                    "box": box,
                    "month_start": bounds[0],
                    "month_end": bounds[1],
                    "q20_140w_input_Jan_Jun_zj": float(arrival.loc[event, "q20_140w_east_zj"]),
                    "east_h20_change_Jan_Jun_zj": float(arrival.loc[event, "east_h20_change_zj"]),
                }
                for metric in (
                    "ohc300_abs_gjm2",
                    "ohc300_abs_zj",
                    "ohc300_anom_gjm2",
                    "ohc300_anom_zj",
                ):
                    record[metric] = float(state.loc[box, metric])
                    record[f"change_from_Jan_Feb_{metric}"] = float(
                        state.loc[box, metric] - early.loc[box, metric]
                    )
                rows.append(record)

            east = state.loc["东箱"]
            west = state.loc["西箱"]
            central = state.loc["中箱"]
            sensitivity_rows.append(
                {
                    "event_year": event,
                    "window": window,
                    "east_minus_west_abs_gjm2": float(
                        east.ohc300_abs_gjm2 - west.ohc300_abs_gjm2
                    ),
                    "east_minus_west_anom_gjm2": float(
                        east.ohc300_anom_gjm2 - west.ohc300_anom_gjm2
                    ),
                    "east_fraction_absolute_total": float(
                        east.ohc300_abs_zj
                        / (
                            east.ohc300_abs_zj
                            + central.ohc300_abs_zj
                            + west.ohc300_abs_zj
                        )
                    ),
                    "east_abs_gjm2": float(east.ohc300_abs_gjm2),
                    "west_abs_gjm2": float(west.ohc300_abs_gjm2),
                    "east_anom_gjm2": float(east.ohc300_anom_gjm2),
                    "west_anom_gjm2": float(west.ohc300_anom_gjm2),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(sensitivity_rows)


def annotate_heatmap(axis: plt.Axes, values: np.ndarray, fmt: str) -> None:
    midpoint = 0.5 * (np.nanmin(values) + np.nanmax(values))
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            color = "white" if value > midpoint else "#102A3C"
            axis.text(
                column,
                row,
                format(value, fmt),
                ha="center",
                va="center",
                fontsize=13,
                fontweight="bold",
                color=color,
            )


def style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#D9E3E8", linewidth=0.8, zorder=0)
    axis.tick_params(labelsize=10)


def make_figure(monthly: pd.DataFrame, summary: pd.DataFrame) -> None:
    configure_fonts()
    post = summary.loc[summary.window.eq(PRIMARY_WINDOW)].copy()
    event_labels = [str(event) for event in EVENTS]
    boxes = list(BOXES)
    abs_matrix = np.array(
        [
            [
                post.loc[
                    post.event_year.eq(event) & post.box.eq(box), "ohc300_abs_gjm2"
                ].iloc[0]
                for box in boxes
            ]
            for event in EVENTS
        ]
    )
    anom_matrix = np.array(
        [
            [
                post.loc[
                    post.event_year.eq(event) & post.box.eq(box), "ohc300_anom_gjm2"
                ].iloc[0]
                for box in boxes
            ]
            for event in EVENTS
        ]
    )

    fig, axes = plt.subplots(2, 2, figsize=(13.0, 8.4), constrained_layout=True)
    ax = axes[0, 0]
    image = ax.imshow(abs_matrix, cmap="YlOrBr", aspect="auto")
    annotate_heatmap(ax, abs_matrix, ".2f")
    ax.set_xticks(range(len(boxes)), boxes, fontsize=12, fontweight="bold")
    ax.set_yticks(range(len(EVENTS)), event_labels, fontsize=12, fontweight="bold")
    ax.set_title("a  到达后的OHC绝对状态（Jul–Sep）", loc="left", fontsize=14)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.045, pad=0.025)
    colorbar.set_label(r"0–300 m OHC（GJ m$^{-2}$，参考0°C）", fontsize=10)

    ax = axes[0, 1]
    vmax = max(0.1, float(np.nanmax(np.abs(anom_matrix))))
    image = ax.imshow(anom_matrix, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    midpoint = 0.0
    for row in range(anom_matrix.shape[0]):
        for column in range(anom_matrix.shape[1]):
            value = anom_matrix[row, column]
            color = "white" if abs(value) > 0.55 * vmax else "#102A3C"
            ax.text(
                column,
                row,
                f"{value:+.2f}",
                ha="center",
                va="center",
                fontsize=13,
                fontweight="bold",
                color=color,
            )
    ax.set_xticks(range(len(boxes)), boxes, fontsize=12, fontweight="bold")
    ax.set_yticks(range(len(EVENTS)), event_labels, fontsize=12, fontweight="bold")
    ax.set_title("b  到达后的OHC异常（Jul–Sep）", loc="left", fontsize=14)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.045, pad=0.025)
    colorbar.set_label(r"1980–2014同月去趋势异常（GJ m$^{-2}$）", fontsize=10)

    ax = axes[1, 0]
    for event in EVENTS:
        event_data = monthly.loc[
            monthly.year.eq(event) & monthly.month.between(1, 11)
        ].pivot(index="month", columns="box", values="ohc300_abs_gjm2")
        contrast = event_data["东箱"] - event_data["西箱"]
        ax.plot(
            contrast.index,
            contrast.values,
            color=EVENT_COLORS[event],
            linewidth=2.4,
            marker="o",
            markersize=4.5,
            label=str(event),
        )
    ax.axvspan(1, 6, color="#2E86AB", alpha=0.08, label="暖量到达阶段")
    ax.axvspan(7, 9, color="#E07A00", alpha=0.10, label="到达后比较窗")
    ax.set_xticks(range(1, 12), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"])
    ax.set_ylabel(r"东箱 − 西箱 OHC（GJ m$^{-2}$）")
    ax.set_title("c  东西绝对OHC差随时间演变", loc="left", fontsize=14)
    ax.legend(frameon=False, ncol=3, fontsize=9, loc="best")
    style_axis(ax)

    ax = axes[1, 1]
    x = np.arange(len(boxes), dtype=float)
    width = 0.23
    for index, event in enumerate(EVENTS):
        values = [
            post.loc[
                post.event_year.eq(event) & post.box.eq(box),
                "change_from_Jan_Feb_ohc300_abs_gjm2",
            ].iloc[0]
            for box in boxes
        ]
        bars = ax.bar(
            x + (index - 1) * width,
            values,
            width=width,
            color=EVENT_COLORS[event],
            label=str(event),
            zorder=2,
        )
        for bar, value in zip(bars, values, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + (0.015 if value >= 0 else -0.025),
                f"{value:+.2f}",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=8.5,
                fontweight="bold",
                rotation=90,
            )
    ax.axhline(0.0, color="#102A3C", linewidth=1.0)
    ax.set_xticks(x, boxes, fontsize=11, fontweight="bold")
    ax.set_ylabel(r"Jul–Sep 减 Jan–Feb（GJ m$^{-2}$）")
    ax.set_title("d  到达后相对年初的OHC变化", loc="left", fontsize=14)
    ax.legend(frameon=False, ncol=3, fontsize=9)
    style_axis(ax)

    fig.suptitle(
        "暖量越过140°W之后：1997、2015与2023的三箱OHC状态",
        fontsize=18,
        fontweight="bold",
    )
    fig.savefig(FIGURE_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_absolute_hovmoller() -> pd.DataFrame:
    """Draw a common-scale longitude-time view of raw 0--300 m OHC."""
    configure_fonts()
    with xr.open_dataset(INPUT_NC, engine="netcdf4", chunks=None) as dataset:
        field = dataset["ohc_300m"].sel(
            lat=slice(*LAT_BOUNDS), lon=slice(130.0, 280.0)
        )
        latitude_weights = np.cos(np.deg2rad(field.lat))
        zonal = field.weighted(latitude_weights).mean("lat", skipna=True) / 1.0e9
        zonal = zonal.load()

    longitude = zonal.lon.values.astype(float)
    relative_month = np.arange(-6, 11, dtype=int)
    panels: dict[int, np.ndarray] = {}
    rows: list[dict[str, float | int | str]] = []
    for event in EVENTS:
        selected = zonal.sel(
            time=slice(f"{event - 1}-07-01", f"{event}-11-30")
        )
        if selected.sizes.get("time") != relative_month.size:
            raise ValueError(
                f"Expected {relative_month.size} Hovmoller months for {event}, "
                f"found {selected.sizes.get('time')}"
            )
        values = selected.values.astype(float)
        if values.shape != (relative_month.size, longitude.size):
            raise ValueError(f"Unexpected Hovmoller shape for {event}: {values.shape}")
        panels[event] = values
        for month_index, timestamp in enumerate(pd.DatetimeIndex(selected.time.values)):
            for lon_index, lon in enumerate(longitude):
                rows.append(
                    {
                        "event_year": event,
                        "relative_month": int(relative_month[month_index]),
                        "time": timestamp,
                        "lon_deg_e": float(lon),
                        "ohc300_abs_gjm2": float(values[month_index, lon_index]),
                    }
                )

    levels = np.arange(18.0, 30.01, 0.5)
    contour_levels = np.arange(20.0, 30.1, 2.0)
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(14.2, 6.9),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    contour = None
    for axis, event in zip(axes, EVENTS, strict=True):
        values = panels[event]
        contour = axis.contourf(
            longitude,
            relative_month,
            values,
            levels=levels,
            cmap="YlOrRd",
            extend="both",
        )
        axis.contour(
            longitude,
            relative_month,
            values,
            levels=contour_levels,
            colors="#5B4636",
            linewidths=0.65,
            alpha=0.72,
        )
        axis.axhspan(6, 8, color="#2E86AB", alpha=0.07, zorder=3)
        axis.axhline(0, color="#102A3C", linestyle="--", linewidth=1.15, zorder=4)
        axis.axhline(6, color="#102A3C", linestyle="--", linewidth=1.15, zorder=4)
        for gate, color, linewidth in (
            (180.0, "#35576C", 0.9),
            (220.0, "#E07A00", 1.35),
            (270.0, "#35576C", 0.9),
        ):
            axis.axvline(gate, color=color, linestyle=":", linewidth=linewidth, zorder=4)
        axis.text(131.5, 0.18, "Jan 0", fontsize=9, color="#102A3C", va="bottom")
        axis.text(131.5, 6.18, "Jul 0", fontsize=9, color="#102A3C", va="bottom")
        axis.set_title(f"{event}/{str(event + 1)[-2:]}", fontsize=15, fontweight="bold")
        axis.set_xlim(130.0, 280.0)
        axis.set_ylim(-6, 10)
        axis.set_xticks(
            [130, 150, 180, 210, 240, 270, 280],
            ["130°E", "150°E", "180°", "150°W", "120°W", "90°W", "80°W"],
            rotation=34,
        )
        axis.tick_params(labelsize=10)
    axes[0].set_yticks(
        [-6, -4, -2, 0, 2, 4, 6, 8, 10],
        ["Jul −1", "Sep −1", "Nov −1", "Jan 0", "Mar 0", "May 0", "Jul 0", "Sep 0", "Nov 0"],
    )
    axes[0].set_ylabel("相对发展年的月份", fontsize=12)
    for axis in axes:
        axis.set_xlabel("经度", fontsize=11)
    if contour is None:
        raise RuntimeError("Hovmoller contour was not created")
    colorbar = fig.colorbar(
        contour,
        ax=axes,
        orientation="horizontal",
        fraction=0.065,
        pad=0.08,
        aspect=44,
    )
    colorbar.set_label(r"0–300 m OHC绝对值（GJ m$^{-2}$，参考0°C）", fontsize=11)
    fig.suptitle(
        "赤道太平洋0–300 m OHC绝对状态演变（10°S–5°N）",
        fontsize=18,
        fontweight="bold",
    )
    fig.savefig(HOVMOLLER_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(HOVMOLLER_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return pd.DataFrame(rows)


def make_anomaly_hovmoller() -> pd.DataFrame:
    """Draw the matching 1980--2014 detrended calendar-month OHC anomaly."""
    configure_fonts()
    with xr.open_dataset(INPUT_NC, engine="netcdf4", chunks=None) as dataset:
        field = dataset["ohc_300m"].sel(
            lat=slice(*LAT_BOUNDS), lon=slice(130.0, 280.0)
        )
        latitude_weights = np.cos(np.deg2rad(field.lat))
        zonal = field.weighted(latitude_weights).mean("lat", skipna=True) / 1.0e9
        zonal = zonal.load()

    times = pd.DatetimeIndex(zonal.time.values)
    longitude = zonal.lon.values.astype(float)
    raw = zonal.values.astype(float)
    anomaly = np.column_stack(
        [same_month_detrended(raw[:, index], times) for index in range(raw.shape[1])]
    )
    relative_month = np.arange(-6, 11, dtype=int)
    panels: dict[int, np.ndarray] = {}
    rows: list[dict[str, float | int | str]] = []
    for event in EVENTS:
        target = (times >= pd.Timestamp(f"{event - 1}-07-01")) & (
            times <= pd.Timestamp(f"{event}-11-30")
        )
        values = anomaly[target]
        event_times = times[target]
        if values.shape != (relative_month.size, longitude.size):
            raise ValueError(f"Unexpected anomaly Hovmoller shape for {event}: {values.shape}")
        panels[event] = values
        for month_index, timestamp in enumerate(event_times):
            for lon_index, lon in enumerate(longitude):
                rows.append(
                    {
                        "event_year": event,
                        "relative_month": int(relative_month[month_index]),
                        "time": timestamp,
                        "lon_deg_e": float(lon),
                        "ohc300_anom_gjm2": float(values[month_index, lon_index]),
                    }
                )

    levels = np.arange(-3.5, 3.51, 0.5)
    contour_levels = np.arange(-3.0, 3.1, 1.0)
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(14.2, 6.9),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    contour = None
    for axis, event in zip(axes, EVENTS, strict=True):
        values = panels[event]
        contour = axis.contourf(
            longitude,
            relative_month,
            values,
            levels=levels,
            cmap="RdBu_r",
            extend="both",
        )
        axis.contour(
            longitude,
            relative_month,
            values,
            levels=contour_levels,
            colors="#5B646A",
            linewidths=0.62,
            alpha=0.76,
        )
        axis.contour(
            longitude,
            relative_month,
            values,
            levels=[0.0],
            colors="#394850",
            linewidths=1.05,
        )
        axis.axhspan(6, 8, color="#E07A00", alpha=0.055, zorder=3)
        axis.axhline(0, color="#102A3C", linestyle="--", linewidth=1.15, zorder=4)
        axis.axhline(6, color="#102A3C", linestyle="--", linewidth=1.15, zorder=4)
        for gate, color, linewidth in (
            (180.0, "#35576C", 0.9),
            (220.0, "#E07A00", 1.35),
            (270.0, "#35576C", 0.9),
        ):
            axis.axvline(gate, color=color, linestyle=":", linewidth=linewidth, zorder=4)
        axis.text(131.5, 0.18, "Jan 0", fontsize=9, color="#102A3C", va="bottom")
        axis.text(131.5, 6.18, "Jul 0", fontsize=9, color="#102A3C", va="bottom")
        axis.set_title(f"{event}/{str(event + 1)[-2:]}", fontsize=15, fontweight="bold")
        axis.set_xlim(130.0, 280.0)
        axis.set_ylim(-6, 10)
        axis.set_xticks(
            [130, 150, 180, 210, 240, 270, 280],
            ["130°E", "150°E", "180°", "150°W", "120°W", "90°W", "80°W"],
            rotation=34,
        )
        axis.tick_params(labelsize=10)
    axes[0].set_yticks(
        [-6, -4, -2, 0, 2, 4, 6, 8, 10],
        ["Jul −1", "Sep −1", "Nov −1", "Jan 0", "Mar 0", "May 0", "Jul 0", "Sep 0", "Nov 0"],
    )
    axes[0].set_ylabel("相对发展年的月份", fontsize=12)
    for axis in axes:
        axis.set_xlabel("经度", fontsize=11)
    if contour is None:
        raise RuntimeError("Anomaly Hovmoller contour was not created")
    colorbar = fig.colorbar(
        contour,
        ax=axes,
        orientation="horizontal",
        fraction=0.065,
        pad=0.08,
        aspect=44,
    )
    colorbar.set_label(
        r"0–300 m OHC异常（GJ m$^{-2}$；1980–2014同月气候态和趋势已去除）",
        fontsize=11,
    )
    fig.suptitle(
        "赤道太平洋0–300 m OHC异常演变（10°S–5°N）",
        fontsize=18,
        fontweight="bold",
    )
    fig.savefig(ANOMALY_HOVMOLLER_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(ANOMALY_HOVMOLLER_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return pd.DataFrame(rows)


def validate_outputs(
    monthly: pd.DataFrame,
    summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    diagnostics: dict[str, float | int | str],
) -> dict[str, float | int | str | bool | list[float]]:
    if monthly.isna().any().any():
        missing = monthly.columns[monthly.isna().any()].tolist()
        raise ValueError(f"Missing values in monthly output: {missing}")
    expected_rows = 540 * len(BOXES)
    if len(monthly) != expected_rows:
        raise ValueError(f"Expected {expected_rows} monthly rows, found {len(monthly)}")
    if not monthly.ohc300_abs_gjm2.between(10.0, 45.0).all():
        raise ValueError("Absolute 0-300 m OHC falls outside the physical audit range")
    if not np.isfinite(summary.select_dtypes(include=[np.number])).all().all():
        raise ValueError("Non-finite values in summary")
    primary = sensitivity.loc[sensitivity.window.eq(PRIMARY_WINDOW)].set_index("event_year")
    diagnostics.update(
        {
            "baseline": list(BASELINE),
            "latitude_bounds": list(LAT_BOUNDS),
            "boxes_degrees_east": {key: list(value) for key, value in BOXES.items()},
            "primary_post_arrival_window": PRIMARY_WINDOW,
            "absolute_ohc_reference": "0 degC",
            "primary_comparison": "area-mean OHC because box areas differ",
            "east_abs_gjm2_JAS": [float(primary.loc[event, "east_abs_gjm2"]) for event in EVENTS],
            "west_abs_gjm2_JAS": [float(primary.loc[event, "west_abs_gjm2"]) for event in EVENTS],
            "east_anom_gjm2_JAS": [float(primary.loc[event, "east_anom_gjm2"]) for event in EVENTS],
            "west_anom_gjm2_JAS": [float(primary.loc[event, "west_anom_gjm2"]) for event in EVENTS],
            "figure_exists": FIGURE_PNG.exists() and FIGURE_PDF.exists(),
        }
    )
    return diagnostics


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    monthly, diagnostics = derive_monthly()
    summary, sensitivity = build_summaries(monthly)
    equatorial_monthly, _ = derive_monthly((-5.0, 5.0))
    _, equatorial_sensitivity = build_summaries(equatorial_monthly)
    domain_sensitivity = pd.concat(
        [
            sensitivity.assign(latitude_band="10S–5N"),
            equatorial_sensitivity.assign(latitude_band="5S–5N"),
        ],
        ignore_index=True,
    )
    make_figure(monthly, summary)
    hovmoller = make_absolute_hovmoller()
    anomaly_hovmoller = make_anomaly_hovmoller()
    diagnostics = validate_outputs(monthly, summary, sensitivity, diagnostics)
    primary_domain = domain_sensitivity.loc[
        domain_sensitivity.window.eq(PRIMARY_WINDOW)
    ]
    east_order_by_domain = {
        band: group.sort_values("east_abs_gjm2", ascending=False).event_year.astype(int).tolist()
        for band, group in primary_domain.groupby("latitude_band")
    }
    diagnostics["domain_sensitivity_east_absolute_order"] = east_order_by_domain
    diagnostics["domain_sensitivity_same_east_order"] = (
        len({tuple(value) for value in east_order_by_domain.values()}) == 1
    )
    monthly.to_csv(MONTHLY_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)
    domain_sensitivity.to_csv(DOMAIN_SENSITIVITY_CSV, index=False)
    hovmoller.to_csv(HOVMOLLER_CSV, index=False)
    anomaly_hovmoller.to_csv(ANOMALY_HOVMOLLER_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(MONTHLY_CSV)
    print(SUMMARY_CSV)
    print(SENSITIVITY_CSV)
    print(DOMAIN_SENSITIVITY_CSV)
    print(HOVMOLLER_CSV)
    print(ANOMALY_HOVMOLLER_CSV)
    print(DIAGNOSTICS_JSON)
    print(FIGURE_PNG)
    print(FIGURE_PDF)
    print(HOVMOLLER_PNG)
    print(HOVMOLLER_PDF)
    print(ANOMALY_HOVMOLLER_PNG)
    print(ANOMALY_HOVMOLLER_PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
