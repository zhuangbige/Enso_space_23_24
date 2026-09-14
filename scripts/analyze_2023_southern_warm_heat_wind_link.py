#!/usr/bin/env python3
"""Diagnose the 2023 southern subsurface-warmth and wind-stress relationship.

The analysis deliberately separates four distinct statements:

1. a latitude-depth *configuration* (warmth concentrated south of the equator),
2. a direct surface-wind Ekman component at 5S,
3. the total SODA3 warm-water transport at 5S, and
4. the mass-balanced full-depth enthalpy transport at 10S.

That separation prevents a south-biased temperature pattern from being
misreported as proof of a net southward transport of the full upper ocean.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Iterable

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/enso_2023_southern_warm_heat_wind_link/mplconfig"),
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    str(ROOT / "outputs/research_2026/enso_2023_southern_warm_heat_wind_link/cache"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle

from climate_plot_style import add_panel_labels, apply_climate_style, save_figure


EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
HEAT_YEARS = np.arange(1980, 2025, dtype=int)
WIND_YEARS = np.arange(1982, 2025, dtype=int)
HEAT_BASELINE = (1980, 2024)
TRANSPORT_BASELINE = (1980, 2022)
WIND_BASELINE = (1982, 2024)

RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
OMEGA = 7.2921159e-5
DEPTH_INTERVAL = (150.0, 250.0)
SOUTH_BAND = (-15.0, -5.0)
SOUTH_INNER_BAND = (-10.0, -5.0)
SOUTH_OUTER_BAND = (-15.0, -10.0)
NORTH_BAND = (5.0, 15.0)
WINDOW_HALF_WIDTH = 10.0
BOOTSTRAP_DRAWS = 5_000
SEED = 20260818

CORE_SECTION = (
    ROOT
    / "data/interim/research_2026/soda3_meridional_sections_30s30n"
    / "soda3_warm_core_meridional_sections_1997_2015_2023_jan_jun_1980_2024.nc"
)
CORE_CACHE = (
    ROOT
    / "data/interim/research_2026/soda3_meridional_sections_30s30n"
    / "yearly_outer_band_cache"
)
FULL_CACHE = (
    ROOT
    / "data/interim/research_2026/soda3_full_pacific_meridional_sections"
    / "yearly_outer_longitude_sums"
)
EQUATORIAL_TEMP = (
    ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
PROCESS_FIELDS = (
    ROOT
    / "data/raw/soda3/soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
)
ERA5_TX_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"
OHC_BUDGET_MONTHLY = (
    ROOT
    / "data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_monthly.csv"
)
DERIVED_DIR = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/enso_2023_southern_warm_heat_wind_link"

CORE_ALL_CSV = DERIVED_DIR / "enso_2023_southern_warm_heat_wind_all_years.csv"
FULL_SENSITIVITY_CSV = (
    DERIVED_DIR / "enso_2023_southern_warm_heat_full_pacific_sensitivity.csv"
)
EVENT_CSV = DERIVED_DIR / "enso_1997_2015_2023_southern_warm_heat_wind_monthly.csv"
LAG_CSV = DERIVED_DIR / "enso_2023_southern_warm_heat_lag_relations.csv"
TRANSPORT10_CSV = DERIVED_DIR / "enso_1997_2015_2023_south_10s_transport_monthly.csv"
COUNTERFACTUAL_CSV = DERIVED_DIR / "enso_2023_south_5s_wind_counterfactual.csv"
DIAGNOSTICS_JSON = DERIVED_DIR / "enso_2023_southern_warm_heat_wind_diagnostics.json"

MECHANISM_PNG = OUT_DIR / "enso_2023_southern_warm_heat_wind_mechanism.png"
MECHANISM_PDF = OUT_DIR / "enso_2023_southern_warm_heat_wind_mechanism.pdf"
LAG_PNG = OUT_DIR / "enso_2023_southern_warm_heat_lag_and_counterfactual.png"
LAG_PDF = OUT_DIR / "enso_2023_southern_warm_heat_lag_and_counterfactual.pdf"
REPORT_MD = OUT_DIR / "ENSO_2023_SOUTHERN_WARM_HEAT_WIND_LINK_CN.md"


def require_files(paths: Iterable[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")


def layer_overlap_weights(depth: np.ndarray, lower: float, upper: float) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    if not np.all(np.diff(depth) > 0):
        raise ValueError("Depth coordinate must increase downward")
    edges = np.empty(depth.size + 1, dtype=float)
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    edges[0] = 0.0
    edges[-1] = 300.0
    return np.maximum(0.0, np.minimum(edges[1:], upper) - np.maximum(edges[:-1], lower))


def detrend_year_axis(
    values: np.ndarray,
    years: np.ndarray,
    *,
    baseline: tuple[int, int],
) -> np.ndarray:
    """Remove a linear expectation along axis 0 with NaN-safe grid fitting."""

    data = np.asarray(values, dtype=float)
    years = np.asarray(years, dtype=float)
    fit_year = (years >= baseline[0]) & (years <= baseline[1])
    if fit_year.sum() < 3:
        raise ValueError(f"Too few baseline years for {baseline}")
    selected = data[fit_year]
    x = years[fit_year]
    x_center = x - x.mean()
    finite = np.isfinite(selected)
    count = finite.sum(axis=0)
    mean = np.divide(
        np.nansum(selected, axis=0),
        count,
        out=np.full(data.shape[1:], np.nan),
        where=count > 0,
    )
    denominator = np.sum(finite * x_center.reshape((-1,) + (1,) * (data.ndim - 1)) ** 2, axis=0)
    numerator = np.nansum(
        (selected - mean)
        * x_center.reshape((-1,) + (1,) * (data.ndim - 1)),
        axis=0,
    )
    slope = np.divide(
        numerator,
        denominator,
        out=np.full(data.shape[1:], np.nan),
        where=denominator > 0,
    )
    apply_x = years - x.mean()
    return data - mean - apply_x.reshape((-1,) + (1,) * (data.ndim - 1)) * slope


def detrend_monthly_series(
    values: np.ndarray,
    years: np.ndarray,
    months: np.ndarray,
    *,
    baseline: tuple[int, int],
) -> np.ndarray:
    output = np.full(np.asarray(values).shape, np.nan, dtype=float)
    for month in MONTHS:
        indices = np.flatnonzero(months == month)
        output[indices] = detrend_year_axis(
            np.asarray(values)[indices],
            np.asarray(years)[indices],
            baseline=baseline,
        )
    return output


def weighted_depth_lat_mean(
    field: np.ndarray,
    *,
    depth_weights: np.ndarray,
    latitude: np.ndarray,
    latitude_bounds: tuple[float, float],
) -> float:
    mask = (latitude >= latitude_bounds[0]) & (latitude <= latitude_bounds[1])
    if not mask.any():
        raise ValueError(f"Latitude band is empty: {latitude_bounds}")
    selected = np.asarray(field, dtype=float)[:, mask]
    weights = depth_weights[:, None] * np.cos(np.deg2rad(latitude[mask]))[None, :]
    valid_weights = np.where(np.isfinite(selected), weights, np.nan)
    denominator = np.nansum(valid_weights)
    if denominator <= 0:
        return np.nan
    return float(np.nansum(selected * weights) / denominator)


def load_heat_indices() -> tuple[pd.DataFrame, xr.Dataset]:
    with xr.open_dataset(EQUATORIAL_TEMP, engine="netcdf4") as source:
        depth = source.depth.values.astype(float)
    with xr.open_dataset(CORE_SECTION, engine="netcdf4") as source:
        centers = source.window_center_lon.load()
        core_selected = source.load()
    depth_weights = layer_overlap_weights(depth, *DEPTH_INTERVAL)
    south_lat = -74.75 + 0.5 * np.arange(90, 140)
    north_lat = -74.75 + 0.5 * np.arange(160, 210)

    core_south: list[np.ndarray] = []
    core_north: list[np.ndarray] = []
    full_south: list[np.ndarray] = []
    full_north: list[np.ndarray] = []
    for year in HEAT_YEARS:
        with np.load(
            CORE_CACHE / f"soda3_warm_core_outer_sections_{year}_jan_jun.npz"
        ) as cache:
            if tuple(int(value) for value in cache["events"]) != EVENTS:
                raise ValueError(f"Unexpected core-cache events for {year}")
            core_south.append(cache["south_temp"].astype(float))
            core_north.append(cache["north_temp"].astype(float))
        with np.load(
            FULL_CACHE / f"soda3_full_pacific_outer_lon_sums_{year}_jan_jun.npz"
        ) as cache:
            numerator = cache["temperature_longitude_sum"].astype(float)
            denominator = cache["valid_longitude_count"].astype(float)
            average = np.divide(
                numerator,
                denominator,
                out=np.full(numerator.shape, np.nan),
                where=denominator > 0,
            )
            full_south.append(average[0])
            full_north.append(average[1])

    core_s = np.stack(core_south)
    core_n = np.stack(core_north)
    full_s = np.stack(full_south)
    full_n = np.stack(full_north)
    for event_index in range(len(EVENTS)):
        for month_index in range(len(MONTHS)):
            core_s[:, event_index, month_index] = detrend_year_axis(
                core_s[:, event_index, month_index],
                HEAT_YEARS,
                baseline=HEAT_BASELINE,
            )
            core_n[:, event_index, month_index] = detrend_year_axis(
                core_n[:, event_index, month_index],
                HEAT_YEARS,
                baseline=HEAT_BASELINE,
            )
    for month_index in range(len(MONTHS)):
        full_s[:, month_index] = detrend_year_axis(
            full_s[:, month_index], HEAT_YEARS, baseline=HEAT_BASELINE
        )
        full_n[:, month_index] = detrend_year_axis(
            full_n[:, month_index], HEAT_YEARS, baseline=HEAT_BASELINE
        )

    scale = RHO0 * CP0 / 1.0e6
    rows: list[dict[str, float | int | str]] = []

    def append_rows(
        south: np.ndarray,
        north: np.ndarray,
        window_reference: str,
        center_values: np.ndarray | None,
    ) -> None:
        for year_index, year in enumerate(HEAT_YEARS):
            for month_index, month in enumerate(MONTHS):
                south_field = south[year_index, month_index] * scale
                north_field = north[year_index, month_index] * scale
                h_s = weighted_depth_lat_mean(
                    south_field,
                    depth_weights=depth_weights,
                    latitude=south_lat,
                    latitude_bounds=SOUTH_BAND,
                )
                h_si = weighted_depth_lat_mean(
                    south_field,
                    depth_weights=depth_weights,
                    latitude=south_lat,
                    latitude_bounds=SOUTH_INNER_BAND,
                )
                h_so = weighted_depth_lat_mean(
                    south_field,
                    depth_weights=depth_weights,
                    latitude=south_lat,
                    latitude_bounds=SOUTH_OUTER_BAND,
                )
                h_n = weighted_depth_lat_mean(
                    north_field,
                    depth_weights=depth_weights,
                    latitude=north_lat,
                    latitude_bounds=NORTH_BAND,
                )
                rows.append(
                    {
                        "year": int(year),
                        "month": int(month),
                        "window_reference": window_reference,
                        "window_center_lon_e": (
                            200.0  # midpoint of the fixed 120E--80W sensitivity window
                            if center_values is None
                            else float(center_values[month_index])
                        ),
                        "heat_south_5_15s_mjm3": h_s,
                        "heat_south_5_10s_mjm3": h_si,
                        "heat_south_10_15s_mjm3": h_so,
                        "heat_north_5_15n_mjm3": h_n,
                        "southness_mjm3": h_s - h_n,
                    }
                )

    for event_index, event in enumerate(EVENTS):
        append_rows(
            core_s[:, event_index],
            core_n[:, event_index],
            str(event),
            centers.isel(event=event_index).values.astype(float),
        )
    append_rows(full_s, full_n, "full_120e_80w", None)
    return pd.DataFrame(rows), core_selected


def load_month_tau(month: int) -> xr.DataArray:
    pieces: list[xr.Dataset] = []
    for part in (1, 2):
        path = ERA5_TX_DIR / (
            f"era5_coupling_part0{part}_m{month:02d}_1982_2025_1p0deg.nc"
        )
        with xr.open_dataset(path, engine="netcdf4") as source:
            current = (
                source[["avg_iews"]]
                .rename(
                    {
                        "valid_time": "time",
                        "latitude": "lat",
                        "longitude": "lon",
                    }
                )
                .assign_coords(lon=lambda item: item.lon % 360.0)
                .sortby("lat")
                .sortby("lon")
                .load()
            )
        if part == 1:
            current = current.sel(lon=slice(None, 179.999))
        pieces.append(current)
    tau = xr.concat(pieces, dim="lon").sortby("lon").avg_iews
    tau = tau.sel(time=slice("1982-01-01", "2024-12-31"))
    if tau.attrs.get("units") not in {"N m**-2", "N m-2"}:
        raise ValueError(f"Unexpected ERA5 stress units: {tau.attrs.get('units')}")
    if not np.all(np.diff(tau.lat.values) > 0):
        raise ValueError("ERA5 latitude must increase after normalization")
    return tau


def weighted_map_mean(
    field: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
    *,
    lat_bounds: tuple[float, float],
    lon_bounds: tuple[float, float],
) -> float:
    lat_mask = (latitude >= lat_bounds[0]) & (latitude <= lat_bounds[1])
    lon_mask = (longitude >= lon_bounds[0]) & (longitude <= lon_bounds[1])
    selected = np.asarray(field)[np.ix_(lat_mask, lon_mask)]
    weights = np.cos(np.deg2rad(latitude[lat_mask]))[:, None]
    weights = np.broadcast_to(weights, selected.shape)
    denominator = np.nansum(np.where(np.isfinite(selected), weights, np.nan))
    return float(np.nansum(selected * weights) / denominator)


def build_wind_metrics(centers: xr.DataArray) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month_index, month in enumerate(MONTHS):
        tau = load_month_tau(month)
        years = pd.DatetimeIndex(tau.time.values).year.to_numpy(dtype=int)
        anomaly = detrend_year_axis(
            tau.values.astype(float), years, baseline=WIND_BASELINE
        )
        latitude = tau.lat.values.astype(float)
        longitude = tau.lon.values.astype(float)
        y_m = EARTH_RADIUS * np.deg2rad(latitude)
        partial_curl = -np.gradient(anomaly, y_m, axis=1)
        coriolis = 2.0 * OMEGA * np.sin(np.deg2rad(latitude))
        southward_ekman = np.full_like(anomaly, np.nan)
        valid_coriolis = np.abs(latitude) >= 2.0
        southward_ekman[:, valid_coriolis, :] = anomaly[:, valid_coriolis, :] / (
            RHO0 * coriolis[valid_coriolis][None, :, None]
        )
        for event_index, event in enumerate(EVENTS):
            center = float(centers.isel(event=event_index, month=month_index))
            lon_bounds = (center - WINDOW_HALF_WIDTH, center + WINDOW_HALF_WIDTH)
            for time_index, year in enumerate(years):
                rows.append(
                    {
                        "year": int(year),
                        "month": int(month),
                        "window_reference": str(event),
                        "taux_anom_nm2": weighted_map_mean(
                            anomaly[time_index],
                            latitude,
                            longitude,
                            lat_bounds=SOUTH_INNER_BAND,
                            lon_bounds=lon_bounds,
                        ),
                        "southward_ekman_m2s": weighted_map_mean(
                            southward_ekman[time_index],
                            latitude,
                            longitude,
                            lat_bounds=SOUTH_INNER_BAND,
                            lon_bounds=lon_bounds,
                        ),
                        "curl_from_taux_1e8_nm3": 1.0e8
                        * weighted_map_mean(
                            partial_curl[time_index],
                            latitude,
                            longitude,
                            lat_bounds=SOUTH_INNER_BAND,
                            lon_bounds=lon_bounds,
                        ),
                    }
                )
    return pd.DataFrame(rows)


def soda5s_absolute_transports(
    centers: xr.DataArray,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    with xr.open_dataset(EQUATORIAL_TEMP, engine="netcdf4") as temp_source, xr.open_dataset(
        PROCESS_FIELDS, engine="netcdf4"
    ) as process_source:
        temperature = temp_source.temp.load()
        velocity = process_source.v.load()
        stress = process_source.taux.load()
    times = pd.DatetimeIndex(temperature.time.values)
    if not times.equals(pd.DatetimeIndex(velocity.time.values)):
        raise ValueError("SODA3 temperature and process time axes differ")
    tracer_lat_index = int(np.argmin(np.abs(temperature.lat.values + 4.75)))
    velocity_lat_index = int(np.argmin(np.abs(velocity.u_lat.values + 5.0)))
    if not np.isclose(float(temperature.lat[tracer_lat_index]), -4.75):
        raise ValueError("Expected one-sided tracer latitude at 4.75S")
    if not np.isclose(float(velocity.u_lat[velocity_lat_index]), -5.0):
        raise ValueError("Expected velocity/stress gate at 5S")

    temp = temperature.isel(lat=tracer_lat_index).values.astype(float)
    raw_v = velocity.isel(u_lat=velocity_lat_index).values.astype(float)
    v_center = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
    raw_tau = stress.isel(u_lat=velocity_lat_index).values.astype(float)
    tau_center = 0.5 * (raw_tau[:, :-1] + raw_tau[:, 1:])
    depth = temperature.depth.values.astype(float)
    depth_edges = np.empty(depth.size + 1)
    depth_edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    depth_edges[0] = 0.0
    depth_edges[-1] = 300.0
    dz = np.diff(depth_edges)
    longitude = temperature.lon.values.astype(float)
    dlon = float(np.median(np.diff(longitude)))
    dx = EARTH_RADIUS * np.cos(np.deg2rad(-5.0)) * np.deg2rad(dlon)
    f = 2.0 * OMEGA * np.sin(np.deg2rad(-5.0))
    years = times.year.to_numpy(dtype=int)
    months = times.month.to_numpy(dtype=int)

    rows: list[dict[str, float | int | str]] = []
    absolute_fields: dict[str, np.ndarray] = {
        "temp": temp,
        "tau": tau_center,
        "longitude": longitude,
        "years": years,
        "months": months,
        "dx": np.asarray(dx),
    }
    for event_index, event in enumerate(EVENTS):
        q_total = np.full(len(times), np.nan)
        q_ekman = np.full(len(times), np.nan)
        for time_index, month in enumerate(months):
            center = float(centers.isel(event=event_index, month=month - 1))
            lon_mask = (
                (longitude >= center - WINDOW_HALF_WIDTH)
                & (longitude <= center + WINDOW_HALF_WIDTH)
            )
            warm = np.maximum(temp[time_index][:, lon_mask] - 20.0, 0.0)
            q_total[time_index] = (
                RHO0
                * CP0
                * np.nansum(
                    warm
                    * v_center[time_index][:, lon_mask]
                    * dz[:, None]
                    * dx
                )
                / 1.0e15
            )
            m_y = -tau_center[time_index, lon_mask] / (RHO0 * f)
            q_ekman[time_index] = (
                RHO0
                * CP0
                * np.nansum(
                    m_y * np.maximum(temp[time_index, 0, lon_mask] - 20.0, 0.0) * dx
                )
                / 1.0e15
            )
        total_anomaly = detrend_monthly_series(
            q_total,
            years,
            months,
            baseline=TRANSPORT_BASELINE,
        )
        ekman_anomaly = detrend_monthly_series(
            q_ekman,
            years,
            months,
            baseline=TRANSPORT_BASELINE,
        )
        for index in range(len(times)):
            rows.append(
                {
                    "time": times[index],
                    "year": int(years[index]),
                    "month": int(months[index]),
                    "window_reference": str(event),
                    "southward_q20_5s_total_pw": -float(total_anomaly[index]),
                    "southward_q20_5s_ekman_pw": -float(ekman_anomaly[index]),
                    "southward_q20_5s_residual_pw": -float(
                        total_anomaly[index] - ekman_anomaly[index]
                    ),
                    "q20_5s_total_absolute_north_pw": float(q_total[index]),
                    "q20_5s_ekman_absolute_north_pw": float(q_ekman[index]),
                }
            )
    return pd.DataFrame(rows), absolute_fields


def build_10s_transport() -> pd.DataFrame:
    monthly = pd.read_csv(OHC_BUDGET_MONTHLY, parse_dates=["time"])
    rows: list[dict[str, float | int]] = []
    for event in EVENTS:
        selected = monthly.loc[monthly.year.eq(event) & monthly.month.between(1, 6)]
        if len(selected) != 6:
            raise ValueError(f"Expected six 10S transport months for {event}")
        for _, current in selected.iterrows():
            row: dict[str, float | int] = {
                "year": int(event),
                "month": int(current.month),
            }
            total = 0.0
            for box in ("west", "central", "east"):
                value = -float(current[f"{box}_south_theta_heat_in_corr_anom_pw"])
                row[f"{box}_southward_theta_10s_pw"] = value
                total += value
            row["total_southward_theta_10s_pw"] = total
            rows.append(row)
    return pd.DataFrame(rows)


def calculate_counterfactual(
    centers: xr.DataArray,
    absolute: dict[str, np.ndarray],
) -> pd.DataFrame:
    temp = absolute["temp"]
    tau = absolute["tau"]
    longitude = absolute["longitude"]
    years = absolute["years"]
    months = absolute["months"]
    dx = float(absolute["dx"])
    f = 2.0 * OMEGA * np.sin(np.deg2rad(-5.0))

    expected = np.full_like(tau, np.nan, dtype=float)
    anomaly = np.full_like(tau, np.nan, dtype=float)
    for month in MONTHS:
        indices = np.flatnonzero(months == month)
        fit = indices[years[indices] <= TRANSPORT_BASELINE[1]]
        x = years[fit].astype(float)
        x_center = x - x.mean()
        y = tau[fit]
        finite = np.isfinite(y)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(y, axis=0),
            count,
            out=np.full(y.shape[1:], np.nan),
            where=count > 0,
        )
        denominator = np.sum(finite * x_center[:, None] ** 2, axis=0)
        slope = np.divide(
            np.nansum(x_center[:, None] * (y - mean), axis=0),
            denominator,
            out=np.full(y.shape[1:], np.nan),
            where=denominator > 0,
        )
        expected[indices] = mean + (years[indices, None] - x.mean()) * slope
        anomaly[indices] = tau[indices] - expected[indices]

    donor_indices = {
        donor: {month: int(np.flatnonzero((years == donor) & (months == month))[0]) for month in MONTHS}
        for donor in (1997, 2015)
    }
    rows: list[dict[str, float | int | str]] = []
    for month_index, month in enumerate(MONTHS):
        target_index = int(np.flatnonzero((years == 2023) & (months == month))[0])
        center = float(centers.sel(event=2023, month=month))
        lon_mask = (
            (longitude >= center - WINDOW_HALF_WIDTH)
            & (longitude <= center + WINDOW_HALF_WIDTH)
        )
        warm_surface = np.maximum(temp[target_index, 0, lon_mask] - 20.0, 0.0)
        scenarios = {
            "control_2023": tau[target_index, lon_mask],
            "tau_anomaly_removed": expected[target_index, lon_mask],
            "tau_anomaly_replaced_1997": expected[target_index, lon_mask]
            + anomaly[donor_indices[1997][month], lon_mask],
            "tau_anomaly_replaced_2015": expected[target_index, lon_mask]
            + anomaly[donor_indices[2015][month], lon_mask],
        }
        for scenario, scenario_tau in scenarios.items():
            m_y = -scenario_tau / (RHO0 * f)
            northward = (
                RHO0 * CP0 * np.nansum(m_y * warm_surface * dx) / 1.0e15
            )
            rows.append(
                {
                    "year": 2023,
                    "month": int(month),
                    "scenario": scenario,
                    "southward_ekman_q20_pw": -float(northward),
                }
            )
    return pd.DataFrame(rows)


def false_discovery_rate(p_values: np.ndarray) -> np.ndarray:
    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    ranked = p_values[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.minimum(adjusted, 1.0)
    return output


def bootstrap_correlation(
    x: np.ndarray,
    y: np.ndarray,
    *,
    rng: np.random.Generator,
) -> tuple[float, float]:
    n = len(x)
    draws = rng.integers(0, n, size=(BOOTSTRAP_DRAWS, n))
    correlations = np.full(BOOTSTRAP_DRAWS, np.nan)
    for index, draw in enumerate(draws):
        if np.nanstd(x[draw]) > 0 and np.nanstd(y[draw]) > 0:
            correlations[index] = stats.pearsonr(x[draw], y[draw]).statistic
    return tuple(float(value) for value in np.nanquantile(correlations, [0.025, 0.975]))


def build_lag_statistics(all_years: pd.DataFrame) -> pd.DataFrame:
    data = all_years.loc[all_years.window_reference.eq("2023")].copy()
    rng = np.random.default_rng(SEED)
    predictors = (
        "southward_ekman_m2s",
        "curl_from_taux_1e8_nm3",
        "southward_q20_5s_ekman_pw",
        "southward_q20_5s_total_pw",
    )
    rows: list[dict[str, float | int | str]] = []
    for predictor in predictors:
        for lag, target_months in ((0, MONTHS), (1, MONTHS[1:])):
            for target_month in target_months:
                predictor_month = target_month - lag
                x = data.loc[
                    data.month.eq(predictor_month), ["year", predictor]
                ].rename(columns={predictor: "x"})
                y = data.loc[
                    data.month.eq(target_month), ["year", "southness_mjm3"]
                ].rename(columns={"southness_mjm3": "y"})
                paired = x.merge(y, on="year", validate="one_to_one").dropna()
                pearson = stats.pearsonr(paired.x, paired.y)
                spearman = stats.spearmanr(paired.x, paired.y)
                ci_low, ci_high = bootstrap_correlation(
                    paired.x.to_numpy(), paired.y.to_numpy(), rng=rng
                )
                rows.append(
                    {
                        "predictor": predictor,
                        "lag_months": lag,
                        "predictor_month": predictor_month,
                        "target_month": target_month,
                        "n": len(paired),
                        "pearson_r": float(pearson.statistic),
                        "pearson_p": float(pearson.pvalue),
                        "pearson_ci_low": ci_low,
                        "pearson_ci_high": ci_high,
                        "spearman_r": float(spearman.statistic),
                        "spearman_p": float(spearman.pvalue),
                    }
                )
    output = pd.DataFrame(rows)
    output["pearson_q_fdr"] = false_discovery_rate(output.pearson_p.to_numpy())
    output["spearman_q_fdr"] = false_discovery_rate(output.spearman_p.to_numpy())
    return output


def add_target_standardization(all_years: pd.DataFrame) -> pd.DataFrame:
    output = all_years.copy()
    for column in (
        "southness_mjm3",
        "southward_ekman_m2s",
        "curl_from_taux_1e8_nm3",
        "southward_q20_5s_total_pw",
        "southward_q20_5s_ekman_pw",
    ):
        output[f"{column}_z_by_month"] = output.groupby(
            ["window_reference", "month"]
        )[column].transform(lambda values: (values - values.mean()) / values.std(ddof=1))
        output[f"{column}_percentile_by_month"] = output.groupby(
            ["window_reference", "month"]
        )[column].rank(pct=True) * 100.0
    return output


def plot_mechanism(
    core: xr.Dataset,
    events: pd.DataFrame,
    transport10: pd.DataFrame,
) -> None:
    apply_climate_style(10)
    fig = plt.figure(figsize=(13.6, 9.2))
    grid = fig.add_gridspec(2, 2, hspace=0.32, wspace=0.24)
    ax_section = fig.add_subplot(grid[0, 0])
    ax_southness = fig.add_subplot(grid[0, 1])
    ax_5s = fig.add_subplot(grid[1, 0])
    ax_10s = fig.add_subplot(grid[1, 1])

    field = (
        core.heat_content_density_anomaly.sel(event=2023, month=[1, 2]).mean("month")
    )
    mesh = ax_section.pcolormesh(
        core.lat,
        core.depth,
        field,
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-10.0, vcenter=0.0, vmax=10.0),
        shading="auto",
        rasterized=True,
    )
    ax_section.set_xlim(-25, 25)
    ax_section.set_ylim(300, 0)
    ax_section.set_xticks((-20, -10, 0, 10, 20))
    ax_section.set_xticklabels(("20S", "10S", "Eq", "10N", "20N"))
    ax_section.set_xlabel("Latitude")
    ax_section.set_ylabel("Depth (m)")
    ax_section.set_title("Jan-Feb 2023 subsurface warmth\n2023 warm-core longitude window")
    ax_section.add_patch(
        Rectangle(
            (-15, 150),
            10,
            100,
            fill=False,
            edgecolor="#222222",
            linewidth=1.4,
            linestyle="--",
        )
    )
    ax_section.text(-14.5, 244, "south box", fontsize=8, va="bottom")
    colorbar = fig.colorbar(mesh, ax=ax_section, orientation="horizontal", pad=0.16)
    colorbar.set_label("Heat-content density anomaly (MJ m$^{-3}$)")

    colors = {1997: "#2f6da5", 2015: "#d98c27", 2023: "#b23a3a"}
    for event in EVENTS:
        selected = events.loc[events.year.eq(event)].sort_values("month")
        ax_southness.plot(
            selected.month,
            selected.southness_mjm3,
            marker="o",
            color=colors[event],
            label=str(event),
        )
    ax_southness.axhline(0.0, color="0.45", linewidth=0.8)
    ax_southness.set_xticks(MONTHS, MONTH_LABELS)
    ax_southness.set_ylabel("Southness index (MJ m$^{-3}$)")
    ax_southness.set_title("2023 southern concentration is exceptional")
    ax_southness.legend(frameon=False, ncol=3, loc="upper right")
    target = events.loc[events.year.eq(2023)].sort_values("month")
    twin = ax_southness.twinx()
    twin.bar(
        target.month,
        target.curl_from_taux_1e8_nm3,
        width=0.42,
        color="#6b8e23",
        alpha=0.26,
        label=r"$-\partial\tau_x/\partial y$",
        zorder=0,
    )
    twin.set_ylabel(r"Partial stress curl ($10^{-8}$ N m$^{-3}$)", color="#556b2f")
    twin.tick_params(axis="y", colors="#556b2f")

    width = 0.24
    x = np.asarray(MONTHS, dtype=float)
    ax_5s.bar(
        x - width,
        target.southward_q20_5s_total_pw,
        width,
        color="#222222",
        label="Total Q20",
    )
    ax_5s.bar(
        x,
        target.southward_q20_5s_ekman_pw,
        width,
        color="#cc6677",
        label="Direct Ekman",
    )
    ax_5s.bar(
        x + width,
        target.southward_q20_5s_residual_pw,
        width,
        color="#4477aa",
        label="Non-Ekman residual",
    )
    ax_5s.axhline(0, color="0.3", linewidth=0.8)
    ax_5s.set_xticks(MONTHS, MONTH_LABELS)
    ax_5s.set_ylabel("Southward Q20 anomaly (PW)")
    ax_5s.set_title("At 5S, wind-driven southward flow is cancelled")
    ax_5s.legend(frameon=False, ncol=3, fontsize=8, loc="lower right")

    target10 = transport10.loc[transport10.year.eq(2023)].sort_values("month")
    box_colors = {"west": "#aa4499", "central": "#ddcc77", "east": "#44aa99"}
    offsets = {"west": -0.24, "central": 0.0, "east": 0.24}
    for box in ("west", "central", "east"):
        values = target10[f"{box}_southward_theta_10s_pw"].to_numpy()
        ax_10s.bar(
            np.asarray(MONTHS, dtype=float) + offsets[box],
            values,
            color=box_colors[box],
            label=box.capitalize(),
            width=0.22,
        )
    ax_10s.plot(
        MONTHS,
        target10.total_southward_theta_10s_pw,
        color="black",
        marker="o",
        linewidth=1.2,
        label="Total",
    )
    ax_10s.axhline(0, color="0.3", linewidth=0.8)
    ax_10s.set_xticks(MONTHS, MONTH_LABELS)
    ax_10s.set_ylabel("Southward enthalpy anomaly (PW)")
    ax_10s.set_title("At 10S, full-depth anomaly is mostly northward")
    ax_10s.legend(frameon=False, ncol=4, fontsize=8, loc="lower right")

    add_panel_labels((ax_section, ax_southness, ax_5s, ax_10s))
    fig.suptitle(
        "2023 southern subsurface warmth: wind imprint without net full-depth export",
        fontsize=15,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.01,
        0.006,
        "Positive transport values point south. Heat anomalies: SODA3 1980-2024 detrended; "
        "wind stress: ERA5 1982-2024 detrended. The 5S total uses the 4.75S tracer temperature "
        "on the equatorward side of the velocity face.",
        fontsize=8,
        color="0.30",
    )
    save_figure(fig, MECHANISM_PNG, dpi=300)
    save_figure(fig, MECHANISM_PDF, dpi=300)
    plt.close(fig)


def plot_lag_and_counterfactual(
    all_years: pd.DataFrame,
    counterfactual: pd.DataFrame,
    lag: pd.DataFrame,
) -> None:
    apply_climate_style(10)
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.3), constrained_layout=True)
    data = all_years.loc[all_years.window_reference.eq("2023")]
    pairs = ((1, 2), (2, 3))
    for axis, (predictor_month, target_month) in zip(axes[:2], pairs):
        x = data.loc[
            data.month.eq(predictor_month), ["year", "southward_ekman_m2s"]
        ].rename(columns={"southward_ekman_m2s": "x"})
        y = data.loc[
            data.month.eq(target_month), ["year", "southness_mjm3"]
        ].rename(columns={"southness_mjm3": "y"})
        paired = x.merge(y, on="year", validate="one_to_one")
        axis.scatter(paired.x, paired.y, s=24, color="0.55", alpha=0.72)
        target = paired.loc[paired.year.eq(2023)].iloc[0]
        axis.scatter(
            target.x,
            target.y,
            s=80,
            color="#b23a3a",
            edgecolor="white",
            linewidth=0.8,
            zorder=5,
            label="2023",
        )
        slope, intercept = np.polyfit(paired.x, paired.y, 1)
        xline = np.linspace(paired.x.min(), paired.x.max(), 100)
        axis.plot(xline, intercept + slope * xline, color="#333333", linewidth=1.1)
        relation = lag.loc[
            lag.predictor.eq("southward_ekman_m2s")
            & lag.lag_months.eq(1)
            & lag.predictor_month.eq(predictor_month)
            & lag.target_month.eq(target_month)
        ].iloc[0]
        axis.text(
            0.04,
            0.94,
            f"r = {relation.pearson_r:+.2f}\np = {relation.pearson_p:.3f}\nFDR q = {relation.pearson_q_fdr:.3f}",
            transform=axis.transAxes,
            ha="left",
            va="top",
        )
        axis.set_xlabel(f"{MONTH_LABELS[predictor_month - 1]} southward Ekman proxy (m$^2$ s$^{{-1}}$)")
        axis.set_ylabel(
            f"{MONTH_LABELS[target_month - 1]} southness index (MJ m$^{{-3}}$)"
        )
        axis.set_title(f"{MONTH_LABELS[predictor_month - 1]} wind -> {MONTH_LABELS[target_month - 1]} heat")
        axis.legend(frameon=False, loc="lower right")

    summary = (
        counterfactual.loc[counterfactual.month.isin((1, 2))]
        .groupby("scenario", as_index=False)
        .southward_ekman_q20_pw.mean()
    )
    order = (
        "control_2023",
        "tau_anomaly_removed",
        "tau_anomaly_replaced_1997",
        "tau_anomaly_replaced_2015",
    )
    labels = ("2023\ncontrol", "tau'\nremoved", "1997 tau'", "2015 tau'")
    values = [
        float(summary.loc[summary.scenario.eq(scenario), "southward_ekman_q20_pw"].iloc[0])
        for scenario in order
    ]
    axes[2].bar(
        np.arange(4),
        values,
        color=("#b23a3a", "#999999", "#2f6da5", "#d98c27"),
        width=0.72,
    )
    axes[2].axhline(0, color="0.3", linewidth=0.8)
    axes[2].set_xticks(np.arange(4), labels)
    axes[2].set_ylabel("Jan-Feb southward Ekman Q20 (PW)")
    axes[2].set_title("Fixed-2023-temperature wind counterfactual")
    add_panel_labels(axes)
    fig.suptitle(
        "Early wind leads the southern heat pattern, but only in the direct Ekman component",
        fontsize=14,
        fontweight="bold",
    )
    save_figure(fig, LAG_PNG, dpi=300)
    save_figure(fig, LAG_PDF, dpi=300)
    plt.close(fig)


def write_report(
    events: pd.DataFrame,
    all_years: pd.DataFrame,
    full_heat: pd.DataFrame,
    lag: pd.DataFrame,
    transport10: pd.DataFrame,
    counterfactual: pd.DataFrame,
) -> None:
    target = events.loc[events.year.eq(2023)].sort_values("month")
    jf = target.loc[target.month.isin((1, 2))]
    comparison = (
        events.loc[events.month.isin((1, 2))]
        .groupby("year", as_index=False)
        .agg(
            southness_mjm3=("southness_mjm3", "mean"),
            taux_anom_nm2=("taux_anom_nm2", "mean"),
            southward_ekman_m2s=("southward_ekman_m2s", "mean"),
            curl_from_taux_1e8_nm3=("curl_from_taux_1e8_nm3", "mean"),
            southward_q20_5s_total_pw=("southward_q20_5s_total_pw", "mean"),
            southward_q20_5s_ekman_pw=("southward_q20_5s_ekman_pw", "mean"),
            southward_q20_5s_residual_pw=("southward_q20_5s_residual_pw", "mean"),
        )
    )
    window = all_years.loc[
        all_years.window_reference.eq("2023")
        & all_years.year.eq(2023)
        & all_years.month.isin((1, 2))
    ]
    rank_heat = float(window.southness_mjm3_percentile_by_month.mean())
    rank_wind = float(window.southward_ekman_m2s_percentile_by_month.mean())
    full_target = full_heat.loc[
        full_heat.year.eq(2023) & full_heat.month.isin((1, 2))
    ]
    lag12 = lag.loc[
        lag.predictor.eq("southward_ekman_m2s")
        & lag.lag_months.eq(1)
        & lag.predictor_month.eq(1)
        & lag.target_month.eq(2)
    ].iloc[0]
    lag23 = lag.loc[
        lag.predictor.eq("southward_ekman_m2s")
        & lag.lag_months.eq(1)
        & lag.predictor_month.eq(2)
        & lag.target_month.eq(3)
    ].iloc[0]
    t10 = transport10.loc[
        transport10.year.eq(2023) & transport10.month.isin((1, 2))
    ].total_southward_theta_10s_pw.mean()
    cf = (
        counterfactual.loc[counterfactual.month.isin((1, 2))]
        .groupby("scenario")
        .southward_ekman_q20_pw.mean()
    )

    table_rows = []
    for _, row in comparison.iterrows():
        table_rows.append(
            f"| {int(row.year)} | {row.southness_mjm3:+.2f} | "
            f"{row.taux_anom_nm2:+.3f} | {row.southward_ekman_m2s:+.2f} | "
            f"{row.curl_from_taux_1e8_nm3:+.2f} | "
            f"{row.southward_q20_5s_total_pw:+.3f} | "
            f"{row.southward_q20_5s_ekman_pw:+.3f} |"
        )
    report = f"""# 2023年风异常与暖量南偏：动力诊断

## 结论先行

2023年1—2月的南侧风异常与次表层暖量南偏存在明确对应，但证据不支持把它写成“整层暖量被净输送到南边”。更准确的过程图景是：

1. 暖核南侧5°—10°S出现强异常偏东风应力，产生直接向南的表层Ekman分量；
2. 同期`−∂τx/∂y`为正，在南半球对应偏下沉的风应力结构，有利于温跃层加深和次表层暖异常形成；
3. SODA3跨5°S的0—300 m总Q20异常仍为向北，说明非Ekman环流抵消了表层风驱南向分量；
4. 跨10°S的质量守恒整层焓输送在1—2月平均也为向北（南向符号下为 **{t10:+.3f} PW**）。

因此，报告中的“暖量偏南”首先是一个**温度/热含量空间配置和温跃层位移**，不能等同于整层暖水的净南向出口。

## 1. 1997、2015与2023的同口径对照（1—2月平均）

| 事件 | 南偏指数 (MJ m⁻³) | τx′ (N m⁻²) | 南向Ekman代理 (m² s⁻¹) | −∂τx/∂y (10⁻⁸ N m⁻³) | 5°S总Q20南向 (PW) | 5°S Ekman Q20南向 (PW) |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_rows)}

2023的南偏指数约为1997的 **{comparison.loc[comparison.year.eq(2023), 'southness_mjm3'].iloc[0] / comparison.loc[comparison.year.eq(1997), 'southness_mjm3'].iloc[0]:.1f} 倍**、2015的 **{comparison.loc[comparison.year.eq(2023), 'southness_mjm3'].iloc[0] / comparison.loc[comparison.year.eq(2015), 'southness_mjm3'].iloc[0]:.1f} 倍**。在1982—2024年的2023暖核经度窗中，2023年1—2月南偏指数的平均百分位为 **{rank_heat:.1f}%**，南向Ekman代理为 **{rank_wind:.1f}%**。

固定120°E—80°W全盆地平均时，2023年1—2月南偏指数只有 **{full_target.southness_mjm3.mean():+.2f} MJ m⁻³**，明显小于暖核随动窗口的 **{jf.southness_mjm3.mean():+.2f} MJ m⁻³**。因此风—暖量关系应解释为暖核附近的局地过程，而不是整个热带太平洋同步南移。

## 2. 时间关系

- 1月南向Ekman代理领先2月南偏指数：Pearson `r={lag12.pearson_r:+.2f}`，原始`p={lag12.pearson_p:.3f}`，FDR `q={lag12.pearson_q_fdr:.3f}`，bootstrap 95%区间`[{lag12.pearson_ci_low:+.2f}, {lag12.pearson_ci_high:+.2f}]`。
- 2月南向Ekman代理领先3月南偏指数：Pearson `r={lag23.pearson_r:+.2f}`，原始`p={lag23.pearson_p:.3f}`，FDR `q={lag23.pearson_q_fdr:.3f}`，bootstrap 95%区间`[{lag23.pearson_ci_low:+.2f}, {lag23.pearson_ci_high:+.2f}]`。
- 2023年3月以后τx′转为偏西，但南偏指数仍在3月达到峰值，支持“早期风建立、随后海洋结构维持”，不支持逐月同步平流解释。

## 3. 5°S输送分解

2023年1—2月平均：

- 直接Ekman Q20南向分量：**{jf.southward_q20_5s_ekman_pw.mean():+.3f} PW**；
- 0—300 m总Q20南向异常：**{jf.southward_q20_5s_total_pw.mean():+.3f} PW**；
- 非Ekman剩余：**{jf.southward_q20_5s_residual_pw.mean():+.3f} PW**。

正值表示向南。风驱分量确实向南，但总输送为负，表明次表层/非Ekman北向补偿更强。这里的5°S总输送使用流速面赤道侧4.75°S温度；正式论文应增加5.25°S温度居中敏感性。

## 4. 固定2023温度的风应力反事实

1—2月平均南向Ekman Q20：

- 2023控制：**{cf['control_2023']:+.3f} PW**；
- 去除2023风应力异常：**{cf['tau_anomaly_removed']:+.3f} PW**；
- 替换为1997风应力异常：**{cf['tau_anomaly_replaced_1997']:+.3f} PW**；
- 替换为2015风应力异常：**{cf['tau_anomaly_replaced_2015']:+.3f} PW**。

该试验只改变Ekman公式中的风应力并固定2023温度场，因此可以说明2023风异常对直接表层南向分量的贡献，但不能代表耦合海洋在风被替换后会如何重新调整。

## 5. 最稳妥的机制表述

> 2023年1—2月，暖核南侧异常偏东风应力产生了显著的南向表层Ekman分量，并伴随南半球偏下沉的纬向应力梯度结构；这可能参与建立或加强南侧温跃层加深和150—250 m暖异常。然而，跨5°S和10°S的整层总热输送并未同步转为净南向，说明2023的“暖量南偏”主要表现为垂向/经向结构重组，而不是整层暖水的单向南逃。

## 数据和口径

- SODA3.15.2：暖核随动纬度—深度剖面、5°S总流速和风应力、三箱10°S质量守恒焓输送；
- ERA5：月平均纬向湍流表面应力；
- 暖量南偏：150—250 m、5°—15°S减5°—15°N，暖核中心±10°经度；
- 距平：剖面1980—2024；SODA3输送1980—2022外推；ERA5风应力1982—2024；均为同历月线性去趋势；
- `−∂τx/∂y`只是完整风应力旋度的纬向应力分量。当前缺少2023年同域τy，因此没有把它称为完整Ekman pumping。

## 产物

- 主图：`{MECHANISM_PNG}`
- 滞后与反事实图：`{LAG_PNG}`
- 全年份月表：`{CORE_ALL_CSV}`
- 全盆地敏感性：`{FULL_SENSITIVITY_CSV}`
- 三事件月表：`{EVENT_CSV}`
- 滞后统计：`{LAG_CSV}`
- 10°S输送表：`{TRANSPORT10_CSV}`
- 反事实表：`{COUNTERFACTUAL_CSV}`
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def validate_outputs(
    all_years: pd.DataFrame,
    full_heat: pd.DataFrame,
    events: pd.DataFrame,
    transport10: pd.DataFrame,
    counterfactual: pd.DataFrame,
) -> dict[str, object]:
    expected_all = len(WIND_YEARS) * len(MONTHS) * len(EVENTS)
    if len(all_years) != expected_all:
        raise ValueError(f"Unexpected all-year row count: {len(all_years)} != {expected_all}")
    if len(events) != len(EVENTS) * len(MONTHS):
        raise ValueError("Unexpected event row count")
    if len(full_heat) != len(HEAT_YEARS) * len(MONTHS):
        raise ValueError("Unexpected full-Pacific sensitivity row count")
    if len(transport10) != len(EVENTS) * len(MONTHS):
        raise ValueError("Unexpected 10S row count")
    if len(counterfactual) != len(MONTHS) * 4:
        raise ValueError("Unexpected counterfactual row count")
    numeric = all_years.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        raise ValueError(f"Missing values in all-year output: {numeric.columns[numeric.isna().any()].tolist()}")
    closure = np.nanmax(
        np.abs(
            events.southward_q20_5s_total_pw
            - events.southward_q20_5s_ekman_pw
            - events.southward_q20_5s_residual_pw
        )
    )
    if closure > 1.0e-10:
        raise ValueError(f"5S decomposition does not close: {closure}")
    target = events.loc[events.year.eq(2023) & events.month.isin((1, 2))]
    return {
        "analysis_version": "20260818_v1",
        "heat_baseline": list(HEAT_BASELINE),
        "transport_baseline": list(TRANSPORT_BASELINE),
        "wind_baseline": list(WIND_BASELINE),
        "all_year_rows": len(all_years),
        "event_rows": len(events),
        "full_pacific_rows": len(full_heat),
        "transport10_rows": len(transport10),
        "counterfactual_rows": len(counterfactual),
        "max_5s_decomposition_error_pw": float(closure),
        "2023_jf_southness_mjm3": float(target.southness_mjm3.mean()),
        "2023_jf_southward_ekman_m2s": float(target.southward_ekman_m2s.mean()),
        "2023_jf_partial_curl_1e8_nm3": float(target.curl_from_taux_1e8_nm3.mean()),
        "2023_jf_southward_q20_5s_total_pw": float(target.southward_q20_5s_total_pw.mean()),
        "2023_jf_southward_q20_5s_ekman_pw": float(target.southward_q20_5s_ekman_pw.mean()),
        "2023_jf_southward_q20_5s_residual_pw": float(target.southward_q20_5s_residual_pw.mean()),
        "transport_sign_convention": "positive southward",
        "curl_definition": "ERA5 zonal-stress contribution -d(tau_x)/dy; not full stress curl",
        "5s_temperature_face": "one-sided tracer temperature at 4.75S",
    }


def main() -> int:
    require_files(
        (
            CORE_SECTION,
            EQUATORIAL_TEMP,
            PROCESS_FIELDS,
            OHC_BUDGET_MONTHLY,
        )
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    heat, core = load_heat_indices()
    full_heat = heat.loc[heat.window_reference.eq("full_120e_80w")].copy()
    wind = build_wind_metrics(core.window_center_lon)
    transport5, absolute = soda5s_absolute_transports(core.window_center_lon)
    transport10 = build_10s_transport()
    counterfactual = calculate_counterfactual(core.window_center_lon, absolute)

    all_years = (
        heat.loc[heat.window_reference.ne("full_120e_80w")]
        .merge(wind, on=["year", "month", "window_reference"], validate="many_to_one")
        .merge(
            transport5,
            on=["year", "month", "window_reference"],
            validate="one_to_one",
        )
    )
    all_years = all_years.loc[all_years.year.between(1982, 2024)].copy()
    all_years = add_target_standardization(all_years)
    events = pd.concat(
        [
            all_years.loc[
                all_years.year.eq(event)
                & all_years.window_reference.eq(str(event))
            ]
            for event in EVENTS
        ],
        ignore_index=True,
    ).sort_values(["year", "month"])
    events = events.merge(transport10, on=["year", "month"], validate="one_to_one")
    lag = build_lag_statistics(all_years)

    diagnostics = validate_outputs(
        all_years, full_heat, events, transport10, counterfactual
    )
    all_years.to_csv(CORE_ALL_CSV, index=False)
    full_heat.to_csv(FULL_SENSITIVITY_CSV, index=False)
    events.to_csv(EVENT_CSV, index=False)
    lag.to_csv(LAG_CSV, index=False)
    transport10.to_csv(TRANSPORT10_CSV, index=False)
    counterfactual.to_csv(COUNTERFACTUAL_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    plot_mechanism(core, events, transport10)
    plot_lag_and_counterfactual(all_years, counterfactual, lag)
    write_report(events, all_years, full_heat, lag, transport10, counterfactual)

    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    for path in (
        CORE_ALL_CSV,
        FULL_SENSITIVITY_CSV,
        EVENT_CSV,
        LAG_CSV,
        TRANSPORT10_CSV,
        COUNTERFACTUAL_CSV,
        DIAGNOSTICS_JSON,
        MECHANISM_PNG,
        MECHANISM_PDF,
        LAG_PNG,
        LAG_PDF,
        REPORT_MD,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
