#!/usr/bin/env python3
"""Add ERA5 westerly-wind and OLR responses to the FEP-SODA3 event diagnosis.

Atmospheric closure is diagnosed operationally as the first of two consecutive
January-June months with positive central-western Pacific u850 anomalies and
negative central-Pacific OLR anomalies.  Positive u850 denotes anomalous
westerlies; negative OLR denotes enhanced deep convection.
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

from analyze_jiang_soda3_transition import (
    D20_FILE,
    EVENTS,
    MONTH_LABELS,
    MONTHS,
    OHC_FILE,
    PDF_DIR,
    REGRESSION_FILE,
    SUMMARY_FILE,
    build_fep_decomposition,
    longitude_label,
    rounded_limit,
    same_month_residual,
    setup_style,
    weighted_box_mean,
    weighted_lat_mean,
)


ERA5_U850_FILES = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc",
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jun.nc",
)
ERA5_OLR_DIR = ROOT / "data/raw/era5/olr_monthly_1deg_1980_2026"

DERIVED_DIR = ROOT / "data/derived/research_2026"
FIGURE_DIR = ROOT / "outputs/research_2026/soda3_fep_transition"

ATMOS_FILE = (
    DERIVED_DIR
    / "era5_u850_olr_equatorial_jan_jun_1980_2024_anomalies.nc"
)
EXTENDED_CSV = (
    DERIVED_DIR
    / "jiang_fep_soda3_atmospheric_closure_1997_2015_2023.csv"
)
EXTENDED_JSON = (
    DERIVED_DIR
    / "jiang_fep_soda3_atmospheric_closure_diagnostics.json"
)
FIGURE_PNG = (
    FIGURE_DIR
    / "jiang_fep_soda3_u850_olr_1997_2015_2023.png"
)
FIGURE_PDF = (
    PDF_DIR
    / "jiang_fep_soda3_u850_olr_1997_2015_2023.pdf"
)

BASELINE = (1980, 2024)
CWP_WIND_BOUNDS = (160.0, 220.0)
CP_OLR_BOUNDS = (170.0, 220.0)
INDONESIA_OLR_BOUNDS = (120.0, 170.0)

OCEAN_COLOR = "#009E73"
ATMOS_COLOR = "#7B3294"


def standardize_field(da: xr.DataArray) -> xr.DataArray:
    rename = {}
    if "valid_time" in da.coords:
        rename["valid_time"] = "time"
    if "latitude" in da.coords:
        rename["latitude"] = "lat"
    if "longitude" in da.coords:
        rename["longitude"] = "lon"
    da = da.rename(rename)
    da = da.assign_coords(lon=da.lon % 360).sortby("lon").sortby("lat")
    da = da.assign_coords(
        time=pd.to_datetime(da.time.values).to_period("M").to_timestamp()
    )
    return da


def open_u850() -> xr.DataArray:
    parts: list[xr.DataArray] = []
    for path in ERA5_U850_FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        with xr.open_dataset(path, engine="netcdf4", chunks=None) as ds:
            current = ds["u"]
            if "pressure_level" in current.dims:
                current = current.sel(pressure_level=850, drop=True)
            parts.append(standardize_field(current.load()))
    u850 = xr.concat(parts, dim="time").sortby("time")
    if u850.get_index("time").duplicated().any():
        raise ValueError("Duplicate ERA5 u850 monthly timestamps")
    return u850.sel(lat=slice(-5.0, 5.0), lon=slice(120.0, 280.0))


def open_olr() -> xr.DataArray:
    monthly: list[xr.DataArray] = []
    for month in MONTHS:
        parts: list[xr.DataArray] = []
        for side in ("west", "east"):
            path = (
                ERA5_OLR_DIR
                / f"era5_olr_{side}_m{month:02d}_1980_2026_1deg.nc"
            )
            if not path.exists():
                raise FileNotFoundError(path)
            with xr.open_dataset(path, engine="netcdf4", chunks=None) as ds:
                if "avg_tnlwrf" not in ds:
                    raise KeyError(f"avg_tnlwrf not found in {path}")
                # ERA5 vertical radiative fluxes are positive downward.
                parts.append(standardize_field((-ds["avg_tnlwrf"]).load()))
        combined = xr.concat(parts, dim="lon").sortby("lon")
        _, unique_indices = np.unique(combined.lon.values, return_index=True)
        combined = combined.isel(lon=np.sort(unique_indices))
        monthly.append(combined)
    olr = xr.concat(monthly, dim="time").sortby("time")
    if olr.get_index("time").duplicated().any():
        raise ValueError("Duplicate ERA5 OLR monthly timestamps")
    return olr.sel(lat=slice(-5.0, 5.0), lon=slice(120.0, 280.0))


def build_atmospheric_dataset() -> xr.Dataset:
    u850 = open_u850()
    olr = open_olr()
    if not np.array_equal(u850.time.values, olr.time.values):
        raise ValueError("ERA5 u850 and OLR times do not align")
    if not np.array_equal(u850.lat.values, olr.lat.values):
        raise ValueError("ERA5 u850 and OLR latitude grids do not align")
    if not np.array_equal(u850.lon.values, olr.lon.values):
        raise ValueError("ERA5 u850 and OLR longitude grids do not align")

    times = pd.DatetimeIndex(pd.to_datetime(u850.time.values))
    u850_anomaly = same_month_residual(u850.values, times, BASELINE)
    olr_anomaly = same_month_residual(olr.values, times, BASELINE)
    keep = (times.year >= BASELINE[0]) & (times.year <= BASELINE[1])
    result = xr.Dataset(
        {
            "u850_anomaly_detrended": (
                ("time", "lat", "lon"),
                u850_anomaly[keep],
            ),
            "olr_anomaly_detrended": (
                ("time", "lat", "lon"),
                olr_anomaly[keep],
            ),
        },
        coords={
            "time": u850.time.values[keep],
            "lat": u850.lat,
            "lon": u850.lon,
        },
        attrs={
            "title": "ERA5 equatorial Pacific u850 and OLR anomalies",
            "source": "ERA5 monthly means",
            "anomaly_definition": (
                "1980-2024 same-calendar-month climatology and "
                "same-calendar-month linear trend removed"
            ),
            "olr_conversion": (
                "OLR = -1 times ERA5 mean top net long-wave radiation flux"
            ),
        },
    )
    result["u850_anomaly_detrended"].attrs.update(
        units="m s-1",
        long_name="Detrended same-calendar-month 850 hPa zonal-wind anomaly",
        sign_convention="positive denotes anomalous westerlies",
    )
    result["olr_anomaly_detrended"].attrs.update(
        units="W m-2",
        long_name="Detrended same-calendar-month outgoing longwave radiation anomaly",
        sign_convention="negative denotes enhanced deep convection",
    )
    ATMOS_FILE.parent.mkdir(parents=True, exist_ok=True)
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
    result.to_netcdf(ATMOS_FILE, engine="netcdf4", encoding=encoding)
    return result


def first_two_months(condition: np.ndarray) -> int | None:
    condition = np.asarray(condition, dtype=bool)
    for index in range(condition.size - 1):
        if condition[index] and condition[index + 1]:
            return index + 1
    return None


def build_extended_summary(
    atmosphere: xr.Dataset,
) -> tuple[pd.DataFrame, dict[int, dict[str, int | None]]]:
    if not SUMMARY_FILE.exists():
        raise FileNotFoundError(SUMMARY_FILE)
    summary = pd.read_csv(SUMMARY_FILE)
    u850 = atmosphere["u850_anomaly_detrended"]
    olr = atmosphere["olr_anomaly_detrended"]
    timing: dict[int, dict[str, int | None]] = {}
    additional_rows: list[dict[str, float | int | bool]] = []

    for year in EVENTS:
        event_u = u850.where(u850.time.dt.year == year, drop=True)
        event_o = olr.where(olr.time.dt.year == year, drop=True)
        if event_u.sizes["time"] != 6 or event_o.sizes["time"] != 6:
            raise ValueError(f"Incomplete ERA5 January-June fields for {year}")
        u850_cwp = weighted_box_mean(
            event_u,
            *CWP_WIND_BOUNDS,
        ).values
        olr_cp = weighted_box_mean(
            event_o,
            *CP_OLR_BOUNDS,
        ).values
        olr_indonesia = weighted_box_mean(
            event_o,
            *INDONESIA_OLR_BOUNDS,
        ).values

        event_summary = summary.loc[
            summary["event_year"].eq(year)
        ].sort_values("month")
        if len(event_summary) != 6:
            raise ValueError(f"Incomplete prior event summary for {year}")
        residual = event_summary["fep_residual_c"].to_numpy(dtype=float)
        ocean = event_summary["oceanic_transition_month"].iloc[0]
        ocean_month = None if pd.isna(ocean) else int(ocean)
        fep_onset = first_two_months(residual > 0)
        atmosphere_month = first_two_months(
            (u850_cwp > 0) & (olr_cp < 0)
        )
        full_connection = (
            None
            if ocean_month is None or atmosphere_month is None
            else max(ocean_month, atmosphere_month)
        )
        timing[year] = {
            "persistent_positive_fep_residual_month": fep_onset,
            "oceanic_transition_month": ocean_month,
            "atmospheric_closure_month": atmosphere_month,
            "full_ocean_atmosphere_connection_month": full_connection,
        }

        for index, month in enumerate(MONTHS):
            additional_rows.append(
                {
                    "event_year": year,
                    "month": month,
                    "u850_cwp_160e_140w_ms": float(u850_cwp[index]),
                    "olr_cp_170e_140w_wm2": float(olr_cp[index]),
                    "olr_indonesia_120e_170e_wm2": float(
                        olr_indonesia[index]
                    ),
                    "olr_cp_minus_indonesia_wm2": float(
                        olr_cp[index] - olr_indonesia[index]
                    ),
                    "persistent_positive_fep_residual_month": fep_onset,
                    "atmospheric_closure_month": atmosphere_month,
                    "full_ocean_atmosphere_connection_month": full_connection,
                    "atmospheric_closure_flag": bool(
                        atmosphere_month is not None
                        and month == atmosphere_month
                    ),
                    "full_connection_flag": bool(
                        full_connection is not None
                        and month == full_connection
                    ),
                }
            )

    additions = pd.DataFrame(additional_rows)
    extended = summary.merge(
        additions,
        on=["event_year", "month"],
        how="left",
        validate="one_to_one",
    )
    return extended, timing


def event_field(
    field: xr.DataArray,
    year: int,
) -> xr.DataArray:
    selected = field.where(
        (field.time.dt.year == year) & field.time.dt.month.isin(MONTHS),
        drop=True,
    )
    if selected.sizes["time"] != 6:
        raise ValueError(f"Incomplete event field for {year}")
    return selected


def add_timing_lines(
    axis: plt.Axes,
    *,
    ocean_month: int | None,
    atmosphere_month: int | None,
    orientation: str,
) -> None:
    if orientation == "vertical":
        if ocean_month is not None:
            axis.axvline(
                ocean_month,
                color=OCEAN_COLOR,
                lw=1.25,
                ls="--",
                zorder=7,
            )
        if atmosphere_month is not None:
            offset = 0.045 if atmosphere_month == ocean_month else 0.0
            axis.axvline(
                atmosphere_month + offset,
                color=ATMOS_COLOR,
                lw=1.35,
                ls=(0, (1.5, 1.5)),
                zorder=8,
            )
    else:
        if ocean_month is not None:
            axis.axhline(
                ocean_month - 1,
                color=OCEAN_COLOR,
                lw=1.15,
                ls="--",
                zorder=7,
            )
        if atmosphere_month is not None:
            offset = 0.06 if atmosphere_month == ocean_month else 0.0
            axis.axhline(
                atmosphere_month - 1 + offset,
                color=ATMOS_COLOR,
                lw=1.25,
                ls=(0, (1.5, 1.5)),
                zorder=8,
            )


def format_hov_axis(
    axis: plt.Axes,
    *,
    row: int,
    show_months: bool,
) -> None:
    axis.set_xlim(130, 280)
    axis.set_ylim(5, 0)
    axis.set_yticks(np.arange(6))
    axis.set_yticklabels(MONTH_LABELS if show_months else [])
    ticks = [130, 160, 180, 220, 250, 270, 280]
    axis.set_xticks(
        ticks,
        [longitude_label(value) for value in ticks] if row == 2 else [],
    )
    axis.tick_params(axis="x", rotation=25)
    for boundary in (180, 220, 270):
        axis.axvline(boundary, color="0.25", lw=0.6, ls=":")


def plot_extended(
    atmosphere: xr.Dataset,
    extended: pd.DataFrame,
    timing: dict[int, dict[str, int | None]],
) -> None:
    fep, _ = build_fep_decomposition()
    with xr.open_dataset(OHC_FILE, chunks=None) as ds:
        ohc = (
            ds["ohc_300m_anomaly_detrended"]
            .where(ds.time.dt.month.isin(MONTHS), drop=True)
            .sel(lat=slice(-5.0, 5.0))
            .load()
        )
    with xr.open_dataset(D20_FILE, chunks=None) as ds:
        d20 = ds["d20_anomaly_detrended"].load()
    u850 = atmosphere["u850_anomaly_detrended"]
    olr = atmosphere["olr_anomaly_detrended"]

    zonal = {
        "ohc": weighted_lat_mean(ohc) / 1.0e9,
        "d20": weighted_lat_mean(d20),
        "u850": weighted_lat_mean(u850),
        "olr": weighted_lat_mean(olr),
    }
    event_arrays = {
        name: {
            year: event_field(field, year)
            for year in EVENTS
        }
        for name, field in zonal.items()
    }
    limits = {
        "ohc": min(
            6.0,
            rounded_limit(
                np.concatenate(
                    [data.values.ravel() for data in event_arrays["ohc"].values()]
                ),
                0.5,
                2.0,
            ),
        ),
        "d20": min(
            60.0,
            rounded_limit(
                np.concatenate(
                    [data.values.ravel() for data in event_arrays["d20"].values()]
                ),
                5.0,
                20.0,
            ),
        ),
        "u850": min(
            10.0,
            rounded_limit(
                np.concatenate(
                    [data.values.ravel() for data in event_arrays["u850"].values()]
                ),
                1.0,
                3.0,
            ),
        ),
        "olr": min(
            60.0,
            rounded_limit(
                np.concatenate(
                    [data.values.ravel() for data in event_arrays["olr"].values()]
                ),
                5.0,
                20.0,
            ),
        ),
    }
    levels = {
        name: np.linspace(-limit, limit, 17)
        for name, limit in limits.items()
    }

    event_fep = fep.loc[
        fep["year"].isin(EVENTS) & fep["month"].isin(MONTHS)
    ]
    sst_values = event_fep[
        ["fep_total_ssta_c", "fep_nino34_related_c", "fep_residual_c"]
    ].to_numpy()
    sst_limit = min(3.5, rounded_limit(sst_values, 0.5, 1.5))

    fig, axes = plt.subplots(
        3,
        5,
        figsize=(17.8, 9.8),
        gridspec_kw={"width_ratios": [1.02, 1.2, 1.2, 1.2, 1.2]},
    )
    fig.subplots_adjust(
        left=0.053,
        right=0.992,
        top=0.872,
        bottom=0.192,
        hspace=0.28,
        wspace=0.18,
    )

    meshes: dict[str, object] = {}
    field_order = ("ohc", "d20", "u850", "olr")
    for row, year in enumerate(EVENTS):
        line_axis = axes[row, 0]
        event = event_fep.loc[event_fep["year"].eq(year)].sort_values("month")
        x = event["month"].to_numpy()
        line_axis.plot(
            x,
            event["fep_total_ssta_c"],
            color="#222222",
            lw=2.0,
            marker="o",
            ms=4.0,
        )
        line_axis.plot(
            x,
            event["fep_nino34_related_c"],
            color="#D55E00",
            lw=1.55,
            marker="s",
            ms=3.4,
        )
        line_axis.plot(
            x,
            event["fep_residual_c"],
            color="#0072B2",
            lw=1.55,
            marker="^",
            ms=3.6,
        )
        line_axis.axhline(0, color="0.45", lw=0.75)
        line_axis.set_xlim(0.75, 6.25)
        line_axis.set_ylim(-sst_limit, sst_limit)
        line_axis.set_xticks(MONTHS, MONTH_LABELS if row == 2 else [])
        line_axis.set_ylabel("SST anomaly (°C)")
        line_axis.grid(axis="y", color="0.89", lw=0.65)
        line_axis.text(
            0.025,
            0.92,
            str(year),
            transform=line_axis.transAxes,
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

        ocean_month = timing[year]["oceanic_transition_month"]
        atmosphere_month = timing[year]["atmospheric_closure_month"]
        add_timing_lines(
            line_axis,
            ocean_month=ocean_month,
            atmosphere_month=atmosphere_month,
            orientation="vertical",
        )

        for column, name in enumerate(field_order, start=1):
            axis = axes[row, column]
            data = event_arrays[name][year]
            mesh = axis.contourf(
                data.lon,
                np.arange(6),
                data.values,
                levels=levels[name],
                cmap="RdBu_r",
                extend="both",
            )
            axis.contour(
                data.lon,
                np.arange(6),
                data.values,
                levels=[0],
                colors="0.20",
                linewidths=0.7,
            )
            meshes[name] = mesh
            format_hov_axis(axis, row=row, show_months=column == 1)
            add_timing_lines(
                axis,
                ocean_month=ocean_month,
                atmosphere_month=atmosphere_month,
                orientation="horizontal",
            )

    titles = (
        "(a) FEP decomposition",
        "(b) 0-300 m OHC",
        "(c) D20",
        "(d) ERA5 u850",
        "(e) ERA5 OLR",
    )
    for column, title in enumerate(titles):
        axes[0, column].set_title(title, weight="bold")
    axes[2, 0].set_xlabel("Development-year month")
    for column in range(1, 5):
        axes[2, column].set_xlabel("Longitude")
    axes[0, 1].set_ylabel("Calendar month")
    axes[1, 1].set_ylabel("Calendar month")
    axes[2, 1].set_ylabel("Calendar month")

    handles = [
        Line2D(
            [0],
            [0],
            color="#222222",
            marker="o",
            lw=2.0,
            ms=4,
            label="Total FEP",
        ),
        Line2D(
            [0],
            [0],
            color="#D55E00",
            marker="s",
            lw=1.55,
            ms=3.5,
            label="Niño-3.4-related",
        ),
        Line2D(
            [0],
            [0],
            color="#0072B2",
            marker="^",
            lw=1.55,
            ms=3.7,
            label="Residual FEP",
        ),
        Line2D(
            [0],
            [0],
            color=OCEAN_COLOR,
            ls="--",
            lw=1.3,
            label="Oceanic transition",
        ),
        Line2D(
            [0],
            [0],
            color=ATMOS_COLOR,
            ls=(0, (1.5, 1.5)),
            lw=1.4,
            label="Atmospheric closure",
        ),
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.919),
        ncol=5,
        frameon=False,
        handlelength=2.4,
        columnspacing=1.45,
    )

    colorbar_labels = {
        "ohc": "OHC (GJ m$^{-2}$)",
        "d20": "D20 (m; + deeper)",
        "u850": "u850 (m s$^{-1}$; + westerly)",
        "olr": "OLR (W m$^{-2}$; − convection)",
    }
    fig.canvas.draw()
    for column, name in enumerate(field_order, start=1):
        position = axes[2, column].get_position()
        color_axis = fig.add_axes(
            [position.x0, 0.094, position.width, 0.017]
        )
        colorbar = fig.colorbar(
            meshes[name],
            cax=color_axis,
            orientation="horizontal",
        )
        colorbar.set_ticks(np.linspace(-limits[name], limits[name], 5))
        colorbar.set_label(colorbar_labels[name])

    fig.suptitle(
        "FEP-to-EP transition requires both subsurface redistribution and atmospheric closure",
        fontsize=14.4,
        weight="bold",
        y=0.976,
    )
    fig.text(
        0.5,
        0.013,
        "OISST FEP: 1982-2024; SODA3.15.2 OHC/D20 and ERA5 u850/OLR: "
        "1980-2024 same-month detrended anomalies; all Hovmöller fields are 5°S-5°N means.\n"
        "Oceanic transition: two months with east-minus-west OHC and D20 > 0. "
        "Atmospheric closure: two months with CWP u850 > 0 and central-Pacific OLR < 0. "
        "Both are operational diagnostics.",
        ha="center",
        va="bottom",
        fontsize=7.45,
        color="0.31",
    )

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG)
    fig.savefig(FIGURE_PDF)
    plt.close(fig)


def month_descriptor(month: int | None) -> dict[str, int | str] | None:
    if month is None:
        return None
    return {"month": month, "month_name": MONTH_LABELS[month - 1]}


def validate_atmosphere(atmosphere: xr.Dataset) -> dict[str, object]:
    u850 = atmosphere["u850_anomaly_detrended"]
    olr = atmosphere["olr_anomaly_detrended"]
    if atmosphere.sizes != {
        "time": 270,
        "lat": 11,
        "lon": 161,
    }:
        raise ValueError(f"Unexpected atmospheric dimensions: {atmosphere.sizes}")
    if bool(u850.isnull().any()) or bool(olr.isnull().any()):
        raise ValueError("Missing values in ERA5 equatorial atmospheric fields")
    if float(np.abs(u850).max()) > 20.0:
        raise ValueError("u850 anomaly exceeds physical QA range")
    if float(np.abs(olr).max()) > 130.0:
        raise ValueError("OLR anomaly exceeds physical QA range")

    checks: dict[str, object] = {}
    for name, field in (
        ("u850", u850),
        ("olr", olr),
    ):
        index = weighted_lat_mean(field).mean("lon", skipna=True).to_series()
        monthly_checks = {}
        for month in MONTHS:
            current = index[index.index.month == month]
            slope = float(
                np.polyfit(
                    current.index.year.astype(float),
                    current.to_numpy(dtype=float),
                    1,
                )[0]
            )
            monthly_checks[str(month)] = {
                "mean": float(current.mean()),
                "trend_per_year": slope,
            }
        checks[name] = {
            "range": [
                float(field.min(skipna=True)),
                float(field.max(skipna=True)),
            ],
            "same_month_residual_checks": monthly_checks,
        }
    return checks


def main() -> int:
    setup_style()
    for path in (OHC_FILE, D20_FILE, SUMMARY_FILE, REGRESSION_FILE):
        if not path.exists():
            raise FileNotFoundError(path)

    atmosphere = build_atmospheric_dataset()
    qa = validate_atmosphere(atmosphere)
    extended, timing = build_extended_summary(atmosphere)
    extended.to_csv(EXTENDED_CSV, index=False, float_format="%.6f")
    plot_extended(atmosphere, extended, timing)

    diagnostics = {
        "events": list(EVENTS),
        "baseline": list(BASELINE),
        "wind_metric": {
            "variable": "ERA5 850 hPa zonal wind",
            "region": "5S-5N, 160E-140W",
            "positive_sign": "anomalous westerlies",
        },
        "convection_metric": {
            "variable": "ERA5 outgoing longwave radiation",
            "region": "5S-5N, 170E-140W",
            "negative_sign": "enhanced high-cloud/deep-convection signal",
        },
        "atmospheric_closure_definition": (
            "First of two consecutive January-June months with CWP u850 > 0 "
            "and central-Pacific OLR < 0"
        ),
        "timing": {
            str(year): {
                name: month_descriptor(month)
                for name, month in event_timing.items()
            }
            for year, event_timing in timing.items()
        },
        "qa": qa,
        "outputs": {
            "atmospheric_netcdf": str(ATMOS_FILE),
            "extended_event_csv": str(EXTENDED_CSV),
            "figure_png": str(FIGURE_PNG),
            "figure_pdf": str(FIGURE_PDF),
        },
    }
    EXTENDED_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(ATMOS_FILE)
    print(EXTENDED_CSV)
    print(EXTENDED_JSON)
    print(FIGURE_PNG)
    print(FIGURE_PDF)
    for year in EVENTS:
        print(year, timing[year])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
