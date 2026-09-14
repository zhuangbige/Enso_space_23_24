#!/usr/bin/env python3
"""Compare FEP warming with subsurface heat redistribution in three ENSO events.

This is a calendar-month adaptation of the Jiang et al. (2026) decomposition:

    T_FEP' = a_m + b_m T_N34' + T_R

where the regression is estimated separately for January through June over
1982-2024.  OISST supplies SST indices so the new calculation stays consistent
with the report, while SODA3.15.2 supplies 0-300 m ocean heat content and D20.

The diagnostic "oceanic transition month" is the first of two consecutive
months for which both east-minus-west OHC and east-minus-west D20 anomalies are
positive.  This is an operational comparison metric, not a formal ENSO index.
"""

from __future__ import annotations

import json
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
from matplotlib.lines import Line2D


TEMP_FILE = (
    ROOT
    / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
OHC_FILE = (
    ROOT
    / "data/interim/research_2026/soda3_ohc/"
    "soda3_ohc_0_100_0_300_1980_2024.nc"
)
OISST_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"

DERIVED_DIR = ROOT / "data/derived/research_2026"
FIGURE_DIR = ROOT / "outputs/research_2026/soda3_fep_transition"
PDF_DIR = ROOT / "output/pdf"

D20_FILE = DERIVED_DIR / "soda3_d20_equatorial_jan_jun_1980_2024.nc"
SUMMARY_FILE = DERIVED_DIR / "jiang_fep_soda3_transition_1997_2015_2023.csv"
REGRESSION_FILE = DERIVED_DIR / "jiang_fep_calendar_month_regression_1982_2024.csv"
DIAGNOSTIC_FILE = DERIVED_DIR / "jiang_fep_soda3_transition_diagnostics.json"
FIGURE_PNG = FIGURE_DIR / "jiang_fep_soda3_ohc_d20_1997_2015_2023.png"
FIGURE_PDF = PDF_DIR / "jiang_fep_soda3_ohc_d20_1997_2015_2023.pdf"

EVENTS = (1997, 2015, 2023)
MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SODA_BASELINE = (1980, 2024)
SST_BASELINE = (1982, 2024)

RHO0 = 1025.0
CP0 = 3990.0

REGIONS = {
    "west": (130.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 270.0),
    "fep": (270.0, 280.0),
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 170,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.5,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.8,
            "ytick.labelsize": 8.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def same_month_residual(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int],
) -> np.ndarray:
    """Remove the baseline same-calendar-month mean and linear trend."""
    data = np.asarray(values, dtype=np.float64)
    out = np.full(data.shape, np.nan, dtype=np.float32)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    for month in MONTHS:
        target = months == month
        fit = (
            target
            & (years >= baseline[0])
            & (years <= baseline[1])
        )
        if fit.sum() < 20:
            raise ValueError(f"Too few baseline records for month {month}")
        fit_values = data[fit]
        fit_years = years[fit]
        center = float(np.mean(fit_years))
        x = fit_years - center
        finite = np.isfinite(fit_values)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(fit_values, axis=0),
            count,
            out=np.full(data.shape[1:], np.nan, dtype=np.float64),
            where=count > 0,
        )
        slope_num = np.nansum((fit_values - mean) * x.reshape((-1,) + (1,) * (data.ndim - 1)), axis=0)
        slope_den = np.sum(
            finite * (x.reshape((-1,) + (1,) * (data.ndim - 1)) ** 2),
            axis=0,
        )
        slope = np.divide(
            slope_num,
            slope_den,
            out=np.full(data.shape[1:], np.nan, dtype=np.float64),
            where=slope_den > 0,
        )
        target_years = years[target]
        fitted = (
            mean
            + (target_years - center).reshape((-1,) + (1,) * (data.ndim - 1))
            * slope
        )
        out[target] = (data[target] - fitted).astype(np.float32)
    return out


def compute_d20(temperature: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Linearly interpolate the first downward crossing of 20 degC."""
    temp = np.asarray(temperature, dtype=np.float32)
    temp[temp < -1.0e10] = np.nan
    crossing = (
        np.isfinite(temp[:, :-1])
        & np.isfinite(temp[:, 1:])
        & (temp[:, :-1] > 20.0)
        & (temp[:, 1:] <= 20.0)
    )
    first = np.argmax(crossing, axis=1)
    has_crossing = np.any(crossing, axis=1)
    index = first[:, None, :, :]
    t0 = np.take_along_axis(temp[:, :-1], index, axis=1)[:, 0]
    t1 = np.take_along_axis(temp[:, 1:], index, axis=1)[:, 0]
    z0 = depth[first]
    z1 = depth[first + 1]
    denominator = t1 - t0
    d20 = z0 + (20.0 - t0) * (z1 - z0) / denominator
    d20[~has_crossing | ~np.isfinite(d20)] = np.nan
    return d20.astype(np.float32)


def weighted_lat_mean(field: xr.DataArray) -> xr.DataArray:
    subset = field.sel(lat=slice(-5.0, 5.0))
    return subset.weighted(np.cos(np.deg2rad(subset.lat))).mean("lat", skipna=True)


def weighted_box_mean(field: xr.DataArray, lon0: float, lon1: float) -> xr.DataArray:
    subset = field.sel(lat=slice(-5.0, 5.0), lon=slice(lon0, lon1))
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def build_d20_dataset() -> xr.Dataset:
    if not TEMP_FILE.exists():
        raise FileNotFoundError(TEMP_FILE)
    with xr.open_dataset(TEMP_FILE, chunks=None) as source:
        temp = source["temp"].load()
    times = pd.DatetimeIndex(pd.to_datetime(temp.time.values))
    d20_values = compute_d20(temp.values, temp.depth.values)
    anomaly_values = same_month_residual(
        d20_values,
        times,
        SODA_BASELINE,
    )
    result = xr.Dataset(
        {
            "d20": (("time", "lat", "lon"), d20_values),
            "d20_anomaly_detrended": (
                ("time", "lat", "lon"),
                anomaly_values,
            ),
        },
        coords={
            "time": temp.time,
            "lat": temp.lat,
            "lon": temp.lon,
        },
        attrs={
            "title": "SODA3.15.2 equatorial Pacific D20",
            "source": "SODA3.15.2 potential temperature",
            "method": "First downward 20 degC crossing, linearly interpolated between depth centers",
            "anomaly_definition": (
                "1980-2024 same-calendar-month climatology and "
                "same-calendar-month linear trend removed"
            ),
        },
    )
    result["d20"].attrs.update(units="m", long_name="Depth of the 20 degC isotherm")
    result["d20_anomaly_detrended"].attrs.update(
        units="m",
        long_name="Detrended same-calendar-month D20 anomaly",
    )
    D20_FILE.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        name: {
            "zlib": True,
            "complevel": 4,
            "shuffle": True,
            "dtype": "float32",
            "_FillValue": np.float32(-1.0e20),
        }
        for name in result.data_vars
    }
    result.to_netcdf(D20_FILE, engine="netcdf4", encoding=encoding)
    return result


def oisst_path(month: int) -> Path:
    tag = ("jan", "feb", "mar", "apr", "may", "jun")[month - 1]
    return OISST_DIR / f"oisst_sst_tropics_1deg_{tag}_1982_2026.nc"


def open_oisst() -> xr.DataArray:
    pieces: list[xr.DataArray] = []
    for month in MONTHS:
        path = oisst_path(month)
        if not path.exists():
            raise FileNotFoundError(path)
        with xr.open_dataset(path, chunks=None) as ds:
            da = ds["sst"].load()
        rename = {}
        if "latitude" in da.coords:
            rename["latitude"] = "lat"
        if "longitude" in da.coords:
            rename["longitude"] = "lon"
        if "valid_time" in da.coords:
            rename["valid_time"] = "time"
        da = da.rename(rename)
        da = da.assign_coords(lon=da.lon % 360).sortby("lon").sortby("lat")
        da = da.assign_coords(
            time=pd.to_datetime(da.time.values).to_period("M").to_timestamp()
        )
        pieces.append(da)
    return xr.concat(pieces, dim="time").sortby("time")


def build_fep_decomposition() -> tuple[pd.DataFrame, pd.DataFrame]:
    sst = open_oisst()
    n34_raw = weighted_box_mean(sst, 190.0, 240.0).to_series()
    fep_raw = weighted_box_mean(sst, 270.0, 280.0).to_series()
    times = pd.DatetimeIndex(n34_raw.index)
    n34_anom = same_month_residual(
        n34_raw.to_numpy(),
        times,
        SST_BASELINE,
    )
    fep_anom = same_month_residual(
        fep_raw.to_numpy(),
        times,
        SST_BASELINE,
    )
    frame = pd.DataFrame(
        {
            "time": times,
            "year": times.year,
            "month": times.month,
            "nino34_ssta_c": n34_anom,
            "fep_total_ssta_c": fep_anom,
        }
    )
    expected = np.full(len(frame), np.nan, dtype=np.float64)
    residual = np.full(len(frame), np.nan, dtype=np.float64)
    regression_rows: list[dict[str, float | int]] = []
    for month in MONTHS:
        mask = (
            frame["month"].eq(month)
            & frame["year"].between(*SST_BASELINE)
            & frame["nino34_ssta_c"].notna()
            & frame["fep_total_ssta_c"].notna()
        )
        x = frame.loc[mask, "nino34_ssta_c"].to_numpy(dtype=float)
        y = frame.loc[mask, "fep_total_ssta_c"].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        pred_fit = intercept + slope * x
        ss_total = float(np.sum((y - y.mean()) ** 2))
        r_squared = 1.0 - float(np.sum((y - pred_fit) ** 2)) / ss_total
        target = frame["month"].eq(month)
        expected[target] = (
            intercept
            + slope * frame.loc[target, "nino34_ssta_c"].to_numpy(dtype=float)
        )
        residual[target] = (
            frame.loc[target, "fep_total_ssta_c"].to_numpy(dtype=float)
            - expected[target]
        )
        regression_rows.append(
            {
                "month": month,
                "month_name": MONTH_LABELS[month - 1],
                "intercept_c": float(intercept),
                "slope_fep_per_nino34": float(slope),
                "r_squared": r_squared,
                "n_years": int(mask.sum()),
                "baseline_start": SST_BASELINE[0],
                "baseline_end": SST_BASELINE[1],
            }
        )
    frame["fep_nino34_related_c"] = expected
    frame["fep_residual_c"] = residual
    return frame, pd.DataFrame(regression_rows)


def first_persistent_positive(values_a: np.ndarray, values_b: np.ndarray) -> int | None:
    condition = (
        np.isfinite(values_a)
        & np.isfinite(values_b)
        & (values_a > 0)
        & (values_b > 0)
    )
    for index in range(len(condition) - 1):
        if condition[index] and condition[index + 1]:
            return index + 1
    return None


def longitude_label(value: float) -> str:
    if np.isclose(value, 180):
        return "180°"
    if value < 180:
        return f"{value:g}°E"
    return f"{360 - value:g}°W"


def build_summary(
    fep: pd.DataFrame,
    ohc: xr.DataArray,
    d20: xr.DataArray,
) -> tuple[pd.DataFrame, dict[int, int | None]]:
    rows: list[dict[str, float | int | str | bool | None]] = []
    transition_months: dict[int, int | None] = {}
    for year in EVENTS:
        sst_event = (
            fep.loc[fep["year"].eq(year) & fep["month"].isin(MONTHS)]
            .sort_values("month")
            .reset_index(drop=True)
        )
        ohc_event = ohc.where(
            (ohc.time.dt.year == year) & ohc.time.dt.month.isin(MONTHS),
            drop=True,
        )
        d20_event = d20.where(
            (d20.time.dt.year == year) & d20.time.dt.month.isin(MONTHS),
            drop=True,
        )
        if len(sst_event) != 6 or ohc_event.sizes["time"] != 6 or d20_event.sizes["time"] != 6:
            raise ValueError(f"Incomplete January-June data for {year}")
        regional: dict[str, dict[str, np.ndarray]] = {"ohc": {}, "d20": {}}
        for name, (lon0, lon1) in REGIONS.items():
            regional["ohc"][name] = weighted_box_mean(ohc_event, lon0, lon1).values
            regional["d20"][name] = weighted_box_mean(d20_event, lon0, lon1).values
        ohc_contrast = regional["ohc"]["east"] - regional["ohc"]["west"]
        d20_contrast = regional["d20"]["east"] - regional["d20"]["west"]
        transition = first_persistent_positive(ohc_contrast, d20_contrast)
        transition_months[year] = transition
        for index, month in enumerate(MONTHS):
            row: dict[str, float | int | str | bool | None] = {
                "event_year": year,
                "month": month,
                "month_name": MONTH_LABELS[index],
                "nino34_ssta_c": float(sst_event.loc[index, "nino34_ssta_c"]),
                "fep_total_ssta_c": float(sst_event.loc[index, "fep_total_ssta_c"]),
                "fep_nino34_related_c": float(
                    sst_event.loc[index, "fep_nino34_related_c"]
                ),
                "fep_residual_c": float(sst_event.loc[index, "fep_residual_c"]),
                "ohc300_east_minus_west_gj_m2": float(ohc_contrast[index] / 1.0e9),
                "d20_east_minus_west_m": float(d20_contrast[index]),
                "oceanic_transition_month": transition,
                "oceanic_transition_flag": bool(
                    transition is not None and month == transition
                ),
            }
            for name in REGIONS:
                row[f"ohc300_{name}_anom_gj_m2"] = float(
                    regional["ohc"][name][index] / 1.0e9
                )
                row[f"d20_{name}_anom_m"] = float(regional["d20"][name][index])
            rows.append(row)
    return pd.DataFrame(rows), transition_months


def rounded_limit(values: np.ndarray, step: float, floor: float) -> float:
    finite = np.abs(values[np.isfinite(values)])
    if finite.size == 0:
        return floor
    robust = float(np.nanpercentile(finite, 98))
    return max(floor, float(np.ceil(robust / step) * step))


def plot_comparison(
    fep: pd.DataFrame,
    ohc_zonal: xr.DataArray,
    d20_zonal: xr.DataArray,
    transitions: dict[int, int | None],
) -> None:
    event_ohc: dict[int, xr.DataArray] = {}
    event_d20: dict[int, xr.DataArray] = {}
    for year in EVENTS:
        event_ohc[year] = ohc_zonal.where(
            (ohc_zonal.time.dt.year == year)
            & ohc_zonal.time.dt.month.isin(MONTHS),
            drop=True,
        ) / 1.0e9
        event_d20[year] = d20_zonal.where(
            (d20_zonal.time.dt.year == year)
            & d20_zonal.time.dt.month.isin(MONTHS),
            drop=True,
        )

    ohc_pool = np.concatenate([data.values.ravel() for data in event_ohc.values()])
    d20_pool = np.concatenate([data.values.ravel() for data in event_d20.values()])
    ohc_limit = min(6.0, rounded_limit(ohc_pool, 0.5, 2.0))
    d20_limit = min(60.0, rounded_limit(d20_pool, 5.0, 20.0))
    ohc_levels = np.linspace(-ohc_limit, ohc_limit, 17)
    d20_levels = np.linspace(-d20_limit, d20_limit, 17)

    event_fep = fep.loc[
        fep["year"].isin(EVENTS) & fep["month"].isin(MONTHS)
    ]
    sst_values = event_fep[
        ["fep_total_ssta_c", "fep_nino34_related_c", "fep_residual_c"]
    ].to_numpy()
    sst_limit = min(3.5, rounded_limit(sst_values, 0.5, 1.5))

    fig, axes = plt.subplots(
        3,
        3,
        figsize=(12.8, 9.8),
        gridspec_kw={"width_ratios": [1.02, 1.38, 1.38]},
        constrained_layout=False,
    )
    fig.subplots_adjust(
        left=0.073,
        right=0.982,
        top=0.875,
        bottom=0.19,
        hspace=0.28,
        wspace=0.19,
    )

    ohc_mesh = None
    d20_mesh = None
    for row, year in enumerate(EVENTS):
        line_ax, ohc_ax, d20_ax = axes[row]
        event = event_fep.loc[event_fep["year"].eq(year)].sort_values("month")
        x = event["month"].to_numpy()
        line_ax.plot(
            x,
            event["fep_total_ssta_c"],
            color="#222222",
            lw=2.1,
            marker="o",
            ms=4.2,
            label="Total FEP",
        )
        line_ax.plot(
            x,
            event["fep_nino34_related_c"],
            color="#D55E00",
            lw=1.65,
            marker="s",
            ms=3.5,
            label="Niño-3.4-related",
        )
        line_ax.plot(
            x,
            event["fep_residual_c"],
            color="#0072B2",
            lw=1.65,
            marker="^",
            ms=3.8,
            label="Residual FEP",
        )
        line_ax.axhline(0, color="0.45", lw=0.75)
        line_ax.set_xlim(0.75, 6.25)
        line_ax.set_ylim(-sst_limit, sst_limit)
        line_ax.set_xticks(MONTHS, MONTH_LABELS if row == 2 else [])
        line_ax.set_ylabel("SST anomaly (°C)")
        line_ax.grid(axis="y", color="0.89", lw=0.65)

        transition = transitions[year]
        if transition is not None:
            line_ax.axvline(
                transition,
                color="#009E73",
                lw=1.25,
                ls="--",
                zorder=0,
            )
            line_ax.text(
                transition + 0.08,
                -sst_limit * 0.86,
                f"ocean shift: {MONTH_LABELS[transition - 1]}",
                color="#007A58",
                fontsize=7.5,
                rotation=90,
                va="bottom",
            )

        y = np.arange(6)
        ohc_data = event_ohc[year]
        d20_data = event_d20[year]
        ohc_mesh = ohc_ax.contourf(
            ohc_data.lon,
            y,
            ohc_data.values,
            levels=ohc_levels,
            cmap="RdBu_r",
            extend="both",
        )
        ohc_ax.contour(
            ohc_data.lon,
            y,
            ohc_data.values,
            levels=[0],
            colors="0.20",
            linewidths=0.75,
        )
        d20_mesh = d20_ax.contourf(
            d20_data.lon,
            y,
            d20_data.values,
            levels=d20_levels,
            cmap="RdBu_r",
            extend="both",
        )
        d20_ax.contour(
            d20_data.lon,
            y,
            d20_data.values,
            levels=[0],
            colors="0.20",
            linewidths=0.75,
        )
        for ax in (ohc_ax, d20_ax):
            for boundary in (180, 220, 270):
                ax.axvline(boundary, color="0.25", lw=0.65, ls=":")
            if transition is not None:
                ax.axhline(
                    transition - 1,
                    color="#007A58",
                    lw=1.1,
                    ls="--",
                )
            ax.set_xlim(130, 280)
            ax.set_ylim(5, 0)
            ax.set_yticks(y, MONTH_LABELS)
            ticks = [130, 160, 180, 220, 250, 270, 280]
            ax.set_xticks(
                ticks,
                [longitude_label(value) for value in ticks] if row == 2 else [],
            )
            ax.tick_params(axis="x", rotation=25)
        ohc_ax.set_ylabel("Calendar month")
        d20_ax.set_yticklabels([])
        line_ax.text(
            0.025,
            0.92,
            str(year),
            transform=line_ax.transAxes,
            ha="left",
            va="top",
            fontsize=10.5,
            weight="bold",
            color="#263746",
            bbox={
                "boxstyle": "round,pad=0.15",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.80,
            },
        )

    axes[0, 0].set_title("(a) FEP decomposition", weight="bold")
    axes[0, 1].set_title("(b) 0-300 m OHC anomaly", weight="bold")
    axes[0, 2].set_title("(c) D20 anomaly", weight="bold")
    axes[2, 0].set_xlabel("Development-year month")
    axes[2, 1].set_xlabel("Longitude")
    axes[2, 2].set_xlabel("Longitude")

    line_handles = [
        Line2D([0], [0], color="#222222", marker="o", lw=2.1, ms=4, label="Total FEP"),
        Line2D([0], [0], color="#D55E00", marker="s", lw=1.65, ms=3.5, label="Niño-3.4-related"),
        Line2D([0], [0], color="#0072B2", marker="^", lw=1.65, ms=3.8, label="Residual FEP"),
        Line2D([0], [0], color="#007A58", ls="--", lw=1.25, label="Oceanic-transition diagnostic"),
    ]
    fig.legend(
        handles=line_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.919),
        ncol=4,
        frameon=False,
        handlelength=2.4,
        columnspacing=1.6,
    )

    assert ohc_mesh is not None and d20_mesh is not None
    cax_ohc = fig.add_axes([0.397, 0.095, 0.238, 0.018])
    cax_d20 = fig.add_axes([0.726, 0.095, 0.238, 0.018])
    cb_ohc = fig.colorbar(ohc_mesh, cax=cax_ohc, orientation="horizontal")
    cb_d20 = fig.colorbar(d20_mesh, cax=cax_d20, orientation="horizontal")
    cb_ohc.set_ticks(np.linspace(-ohc_limit, ohc_limit, 5))
    cb_d20.set_ticks(np.linspace(-d20_limit, d20_limit, 5))
    cb_ohc.set_label("OHC anomaly (GJ m$^{-2}$)")
    cb_d20.set_label("D20 anomaly (m; positive = deeper)")

    fig.suptitle(
        "FEP warming is not the transition itself: subsurface heat redistribution separates events",
        fontsize=14.2,
        weight="bold",
        y=0.976,
    )
    fig.text(
        0.5,
        0.014,
        "OISST FEP decomposition: 1982-2024 same-month detrended anomalies; "
        "SODA3.15.2 OHC/D20: 1980-2024 same-month detrended anomalies; 5°S-5°N mean.\n"
        "Dashed green line: first of two consecutive months with positive "
        "east-minus-west OHC and D20 anomalies (operational diagnostic).",
        ha="center",
        va="bottom",
        fontsize=7.6,
        color="0.32",
    )

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG)
    fig.savefig(FIGURE_PDF)
    plt.close(fig)


def main() -> int:
    setup_style()
    d20_dataset = build_d20_dataset()
    fep, regression = build_fep_decomposition()

    if not OHC_FILE.exists():
        raise FileNotFoundError(OHC_FILE)
    with xr.open_dataset(OHC_FILE, chunks=None) as ds:
        ohc = (
            ds["ohc_300m_anomaly_detrended"]
            .where(ds.time.dt.month.isin(MONTHS), drop=True)
            .sel(lat=slice(-5.0, 5.0))
            .load()
        )

    d20_anomaly = d20_dataset["d20_anomaly_detrended"]
    summary, transitions = build_summary(fep, ohc, d20_anomaly)

    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_FILE, index=False, float_format="%.6f")
    regression.to_csv(REGRESSION_FILE, index=False, float_format="%.6f")

    ohc_zonal = weighted_lat_mean(ohc)
    d20_zonal = weighted_lat_mean(d20_anomaly)
    plot_comparison(fep, ohc_zonal, d20_zonal, transitions)

    diagnostics = {
        "events": list(EVENTS),
        "soda_baseline": list(SODA_BASELINE),
        "sst_baseline": list(SST_BASELINE),
        "fep_formula": "FEP' = a_month + b_month * Nino3.4' + residual_FEP",
        "transition_definition": (
            "First of two consecutive January-June months with both "
            "east-minus-west OHC300 and east-minus-west D20 anomalies > 0"
        ),
        "transition_months": {
            str(year): (
                None
                if month is None
                else {"month": month, "month_name": MONTH_LABELS[month - 1]}
            )
            for year, month in transitions.items()
        },
        "ranges": {
            "d20_m": [
                float(d20_dataset["d20"].min(skipna=True)),
                float(d20_dataset["d20"].max(skipna=True)),
            ],
            "d20_anomaly_m": [
                float(d20_anomaly.min(skipna=True)),
                float(d20_anomaly.max(skipna=True)),
            ],
            "ohc300_event_zonal_anomaly_gj_m2": [
                float(
                    weighted_lat_mean(
                        ohc.where(ohc.time.dt.year.isin(EVENTS), drop=True)
                    ).min(skipna=True)
                    / 1.0e9
                ),
                float(
                    weighted_lat_mean(
                        ohc.where(ohc.time.dt.year.isin(EVENTS), drop=True)
                    ).max(skipna=True)
                    / 1.0e9
                ),
            ],
        },
        "outputs": {
            "d20_netcdf": str(D20_FILE),
            "event_summary_csv": str(SUMMARY_FILE),
            "fep_regression_csv": str(REGRESSION_FILE),
            "figure_png": str(FIGURE_PNG),
            "figure_pdf": str(FIGURE_PDF),
        },
    }
    DIAGNOSTIC_FILE.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(D20_FILE)
    print(SUMMARY_FILE)
    print(REGRESSION_FILE)
    print(DIAGNOSTIC_FILE)
    print(FIGURE_PNG)
    print(FIGURE_PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
