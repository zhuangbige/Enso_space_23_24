#!/usr/bin/env python3
"""Diagnose SODA3 heat storage and redistribution before ENSO events.

This script extends the EP/CP transition analysis with three complementary
questions:

1. Is warm water merely stored in the basin, or has it shifted eastward?
2. Which monthly-mean heat-budget proxies favor eastern-Pacific warming?
3. Do any SODA3 quantities improve leakage-free forecasts of the following
   DJF Niño-3 minus Niño-4 index beyond persistence of the initial SST pattern?

The advection terms are diagnostics from monthly means, not an exact closed
ocean heat budget. Their residual contains unresolved transients, mixing,
entrainment, diffusion, and assimilation increments.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


TEMP_NC = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
PROCESS_NC = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
)
OHC_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_ohc_indices_1980_2024.csv"
)
MONTHLY_BASE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
)
EVENT_BASE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_event_summary_1982_2023.csv"
)

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_fep_transition"
OUT_PDF = ROOT / "output/pdf"
INDEX_CSV = OUT_DATA / "soda3_transition_process_indices_1980_2024.csv"
EVENT_CSV = OUT_DATA / "soda3_process_event_summary_1982_2023.csv"
CORR_CSV = OUT_DATA / "soda3_process_event_correlations.csv"
PRED_CSV = OUT_DATA / "soda3_process_walkforward_predictions_2000_2023.csv"
SKILL_CSV = OUT_DATA / "soda3_process_walkforward_skill_2000_2023.csv"
LOEO_PRED_CSV = OUT_DATA / "soda3_process_event_loeo_predictions.csv"
LOEO_SKILL_CSV = OUT_DATA / "soda3_process_event_loeo_skill.csv"
DIAGNOSTICS_JSON = OUT_DATA / "soda3_process_diagnostics.json"
EVENT_PNG = OUT_DIR / "soda3_process_diagnostics_1997_2015_2023.png"
EVENT_PDF = OUT_PDF / "soda3_process_diagnostics_1997_2015_2023.pdf"
EVIDENCE_PNG = OUT_DIR / "soda3_process_full_event_evidence.png"
EVIDENCE_PDF = OUT_PDF / "soda3_process_full_event_evidence.pdf"
SUMMARY_MD = OUT_DIR / "SODA3_PROCESS_RESULTS_CN.md"

MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
BASELINE = (1980, 2024)
TEST_YEARS = (2000, 2023)
RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
SECONDS_PER_MONTH = 30.4375 * 86400.0
BOOTSTRAP_SAMPLES = 5000
PERMUTATION_SAMPLES = 20000
RIDGE_ALPHA = 1.0

# Longitude ranges are in degrees east.
REGIONS = {
    "west": (130.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 280.0),
}

FEATURE_LABELS = {
    "wwv_centroid_deg_e": "Warm-volume centroid",
    "wwv_east_fraction": "East WWV fraction",
    "ohc300_east_tendency_wm2": "Eastern OHC tendency",
    "hadv_east_kmonth": "Horizontal advection",
    "vadv_east_kmonth": "Vertical advection",
    "surface_heating_east_kmonth": "Surface heating",
    "barrier_east_m": "Barrier-layer thickness",
    "ssh_ew_m": "SSH east minus west",
    "taux_central_nm2": "Central-Pacific stress",
    "u_50_150_central_ms": "Subsurface eastward current",
}

MODEL_FEATURES = {
    "Type persistence": ("init_type_raw_c",),
    "+ WWV centroid": ("init_type_raw_c", "wwv_centroid_deg_e"),
    "+ east WWV fraction": ("init_type_raw_c", "wwv_east_fraction"),
    "+ OHC tendency": ("init_type_raw_c", "ohc300_east_tendency_wm2"),
    "+ horizontal advection": ("init_type_raw_c", "hadv_east_kmonth"),
    "+ vertical advection": ("init_type_raw_c", "vadv_east_kmonth"),
    "+ surface heating": ("init_type_raw_c", "surface_heating_east_kmonth"),
    "+ barrier layer": ("init_type_raw_c", "barrier_east_m"),
    "+ SSH gradient": ("init_type_raw_c", "ssh_ew_m"),
    "+ zonal stress": ("init_type_raw_c", "taux_central_nm2"),
    "+ subsurface current": ("init_type_raw_c", "u_50_150_central_ms"),
    "Ocean redistribution": (
        "init_type_raw_c",
        "wwv_centroid_deg_e",
        "ssh_ew_m",
        "u_50_150_central_ms",
    ),
    "Heat-budget proxies": (
        "init_type_raw_c",
        "ohc300_east_tendency_wm2",
        "hadv_east_kmonth",
        "vadv_east_kmonth",
        "surface_heating_east_kmonth",
    ),
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 170,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.2,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.3,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "legend.fontsize": 8.1,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def cell_areas(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Spherical area for a regular lat-lon grid."""
    dlat = float(np.median(np.diff(lat)))
    dlon = float(np.median(np.diff(lon)))
    south = np.deg2rad(lat - dlat / 2.0)
    north = np.deg2rad(lat + dlat / 2.0)
    area_lat = EARTH_RADIUS**2 * (np.sin(north) - np.sin(south))
    return area_lat[:, None] * np.deg2rad(dlon) * np.ones((1, len(lon)))


def vertical_thickness(depth: np.ndarray, maximum: float = 300.0) -> np.ndarray:
    bounds = np.empty(len(depth) + 1, dtype=float)
    bounds[0] = 0.0
    bounds[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    bounds[-1] = min(maximum, depth[-1] + 0.5 * (depth[-1] - depth[-2]))
    return np.diff(bounds)


def weighted_mean_2d(
    field: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    lon_bounds: tuple[float, float],
) -> float:
    selected_lon = (lon >= lon_bounds[0]) & (lon <= lon_bounds[1])
    values = field[:, selected_lon]
    weights = cell_areas(lat, lon[selected_lon])
    valid = np.isfinite(values)
    return float(np.nansum(values * weights) / np.nansum(weights * valid))


def weighted_mean_3d(
    field: np.ndarray,
    depth: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    lon_bounds: tuple[float, float],
    depth_bounds: tuple[float, float],
) -> float:
    selected_z = (depth >= depth_bounds[0]) & (depth <= depth_bounds[1])
    selected_lon = (lon >= lon_bounds[0]) & (lon <= lon_bounds[1])
    values = field[np.ix_(selected_z, np.ones(len(lat), dtype=bool), selected_lon)]
    dz = vertical_thickness(depth)[selected_z]
    horizontal = cell_areas(lat, lon[selected_lon])
    weights = dz[:, None, None] * horizontal[None, :, :]
    valid = np.isfinite(values)
    return float(np.nansum(values * weights) / np.nansum(weights * valid))


def same_month_residual(
    values: np.ndarray,
    times: pd.DatetimeIndex,
) -> np.ndarray:
    """Remove the 1980-2024 calendar-month climatology and linear trend."""
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in MONTHS:
        selected = (times.month == month) & np.isfinite(values)
        baseline = (
            selected
            & (times.year >= BASELINE[0])
            & (times.year <= BASELINE[1])
        )
        years = times.year[baseline].astype(float)
        fit_values = values[baseline]
        design = np.column_stack([np.ones(len(years)), years])
        intercept, slope = np.linalg.lstsq(design, fit_values, rcond=None)[0]
        output[selected] = (
            values[selected]
            - (intercept + slope * times.year[selected].astype(float))
        )
    return output


def d20_and_sharpness(
    temperature: np.ndarray,
    depth: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Linearly interpolate D20 and the local vertical temperature gradient."""
    crossing = (temperature[:-1] >= 20.0) & (temperature[1:] < 20.0)
    has_crossing = crossing.any(axis=0)
    index = np.argmax(crossing, axis=0)
    t0 = np.take_along_axis(
        temperature,
        index[None, :, :],
        axis=0,
    )[0]
    t1 = np.take_along_axis(
        temperature,
        (index + 1)[None, :, :],
        axis=0,
    )[0]
    z0 = depth[index]
    z1 = depth[index + 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        d20 = z0 + (20.0 - t0) * (z1 - z0) / (t1 - t0)
        sharpness = (t0 - t1) / (z1 - z0) * 100.0
    d20 = np.where(has_crossing, d20, np.nan)
    d20 = np.where((~has_crossing) & (temperature[-1] >= 20.0), 300.0, d20)
    d20 = np.where(temperature[0] < 20.0, 0.0, d20)
    sharpness = np.where(has_crossing, sharpness, np.nan)
    return d20, sharpness


def derive_temperature_indices(dataset: xr.Dataset) -> pd.DataFrame:
    times = pd.DatetimeIndex(dataset.time.values)
    depth = dataset.depth.values.astype(float)
    lat = dataset.lat.values.astype(float)
    lon = dataset.lon.values.astype(float)
    areas = cell_areas(lat, lon)
    rows: list[dict[str, float | int | pd.Timestamp]] = []
    for time_index, timestamp in enumerate(times):
        temperature = dataset.temp.isel(time=time_index).values.astype(float)
        d20, sharpness = d20_and_sharpness(temperature, depth)
        volume_by_lon = np.nansum(d20 * areas, axis=0)
        total_volume = float(np.nansum(volume_by_lon))
        east = lon >= 180.0
        centroid = float(np.nansum(volume_by_lon * lon) / total_volume)
        rows.append(
            {
                "time": timestamp,
                "year": timestamp.year,
                "month": timestamp.month,
                "wwv_1e14m3": total_volume / 1.0e14,
                "wwv_centroid_deg_e": centroid,
                "wwv_east_fraction": float(
                    np.nansum(volume_by_lon[east]) / total_volume
                ),
                "d20_west_m": weighted_mean_2d(
                    d20, lat, lon, REGIONS["west"]
                ),
                "d20_east_m": weighted_mean_2d(
                    d20, lat, lon, REGIONS["east"]
                ),
                "thermocline_sharpness_east_k100m": weighted_mean_2d(
                    sharpness, lat, lon, REGIONS["east"]
                ),
            }
        )
    return pd.DataFrame(rows)


def interpolate_velocity_to_tracer(
    velocity: np.ndarray,
    u_lat: np.ndarray,
    u_lon: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
) -> np.ndarray:
    if (
        velocity.shape[-2:] == (len(lat) + 1, len(lon) + 1)
        and np.allclose(0.5 * (u_lat[:-1] + u_lat[1:]), lat)
        and np.allclose(0.5 * (u_lon[:-1] + u_lon[1:]), lon)
    ):
        return 0.25 * (
            velocity[:, :-1, :-1]
            + velocity[:, 1:, :-1]
            + velocity[:, :-1, 1:]
            + velocity[:, 1:, 1:]
        )
    raise ValueError("Velocity and tracer grids are not the expected staggered pair")


def derive_process_indices(
    temperature_dataset: xr.Dataset,
    process_dataset: xr.Dataset,
) -> pd.DataFrame:
    times = pd.DatetimeIndex(temperature_dataset.time.values)
    process_times = pd.DatetimeIndex(process_dataset.time.values)
    if not times.equals(process_times):
        raise ValueError("Temperature and process-file times do not match")
    depth = temperature_dataset.depth.values.astype(float)
    lat = temperature_dataset.lat.values.astype(float)
    lon = temperature_dataset.lon.values.astype(float)
    u_lat = process_dataset.u_lat.values.astype(float)
    u_lon = process_dataset.u_lon.values.astype(float)
    lon_radians = np.deg2rad(lon)
    lat_radians = np.deg2rad(lat)
    rows: list[dict[str, float | int | pd.Timestamp]] = []
    for time_index, timestamp in enumerate(times):
        temperature = (
            temperature_dataset.temp.isel(time=time_index).values.astype(float)
        )
        u = interpolate_velocity_to_tracer(
            process_dataset.u.isel(time=time_index).values.astype(float),
            u_lat,
            u_lon,
            lat,
            lon,
        )
        v = interpolate_velocity_to_tracer(
            process_dataset.v.isel(time=time_index).values.astype(float),
            u_lat,
            u_lon,
            lat,
            lon,
        )
        wt = process_dataset.wt.isel(time=time_index).values.astype(float)
        dtdlambda = np.gradient(temperature, lon_radians, axis=2)
        dtdx = dtdlambda / (
            EARTH_RADIUS * np.cos(lat_radians)[None, :, None]
        )
        dtdy = np.gradient(temperature, lat_radians, axis=1) / EARTH_RADIUS
        dtdz = np.gradient(temperature, depth, axis=0)
        horizontal_advection = -(u * dtdx + v * dtdy) * SECONDS_PER_MONTH
        # SODA dia-surface velocity is positive upward; depth is positive down.
        vertical_advection = wt * dtdz * SECONDS_PER_MONTH

        net_heating = (
            process_dataset.net_heating.isel(time=time_index).values.astype(float)
        )
        mixed_layer = (
            process_dataset.mlt.isel(time=time_index).values.astype(float)
        )
        density_layer = (
            process_dataset.mlp.isel(time=time_index).values.astype(float)
        )
        surface_tendency = (
            net_heating
            / (RHO0 * CP0 * np.maximum(density_layer, 5.0))
            * SECONDS_PER_MONTH
        )
        ssh = process_dataset.ssh.isel(time=time_index).values.astype(float)
        taux_u = process_dataset.taux.isel(time=time_index).values.astype(float)
        taux = 0.25 * (
            taux_u[:-1, :-1]
            + taux_u[1:, :-1]
            + taux_u[:-1, 1:]
            + taux_u[1:, 1:]
        )
        # Barrier-layer thickness is the positive separation between the
        # temperature-defined isothermal layer and density-defined mixed layer.
        barrier = np.maximum(mixed_layer - density_layer, 0.0)
        rows.append(
            {
                "time": timestamp,
                "year": timestamp.year,
                "month": timestamp.month,
                "hadv_east_kmonth": weighted_mean_3d(
                    horizontal_advection,
                    depth,
                    lat,
                    lon,
                    REGIONS["east"],
                    (5.0, 100.0),
                ),
                "vadv_east_kmonth": weighted_mean_3d(
                    vertical_advection,
                    depth,
                    lat,
                    lon,
                    REGIONS["east"],
                    (5.0, 100.0),
                ),
                "surface_heating_east_kmonth": weighted_mean_2d(
                    surface_tendency, lat, lon, REGIONS["east"]
                ),
                "net_heating_east_wm2": weighted_mean_2d(
                    net_heating, lat, lon, REGIONS["east"]
                ),
                "barrier_east_m": weighted_mean_2d(
                    barrier, lat, lon, REGIONS["east"]
                ),
                "ssh_ew_m": (
                    weighted_mean_2d(ssh, lat, lon, REGIONS["east"])
                    - weighted_mean_2d(ssh, lat, lon, REGIONS["west"])
                ),
                "taux_central_nm2": weighted_mean_2d(
                    taux, lat, lon, REGIONS["central"]
                ),
                "u_50_150_central_ms": weighted_mean_3d(
                    u,
                    depth,
                    lat,
                    lon,
                    REGIONS["central"],
                    (50.0, 150.0),
                ),
                "wt_50_150_east_ms": weighted_mean_3d(
                    wt,
                    depth,
                    lat,
                    lon,
                    REGIONS["east"],
                    (50.0, 150.0),
                ),
            }
        )
        if (time_index + 1) % 30 == 0 or time_index + 1 == len(times):
            print(f"Processed {time_index + 1}/{len(times)} months", flush=True)
    return pd.DataFrame(rows)


def add_ohc_tendency(indices: pd.DataFrame) -> pd.DataFrame:
    ohc = pd.read_csv(OHC_CSV, parse_dates=["time"]).sort_values("time")
    seconds = ohc["time"].diff().dt.total_seconds()
    ohc["ohc300_east_tendency_wm2"] = (
        ohc["ohc300_east_jm2"].diff() / seconds
    )
    ohc["ohc300_ew_tendency_wm2"] = (
        ohc["ohc300_east_minus_west_anom_jm2"].diff() / seconds
    )
    ohc["year"] = ohc["time"].dt.year
    ohc["month"] = ohc["time"].dt.month
    return indices.merge(
        ohc[
            [
                "year",
                "month",
                "ohc300_east_tendency_wm2",
                "ohc300_ew_tendency_wm2",
            ]
        ],
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )


def add_fixed_anomalies(indices: pd.DataFrame) -> pd.DataFrame:
    times = pd.DatetimeIndex(indices["time"])
    excluded = {"time", "year", "month"}
    raw_columns = [
        column
        for column in indices.columns
        if column not in excluded and not column.endswith("_anom")
    ]
    for column in raw_columns:
        indices[f"{column}_anom"] = same_month_residual(
            indices[column].to_numpy(dtype=float),
            times,
        )
    return indices


def fit_trend(
    years: np.ndarray,
    values: np.ndarray,
) -> tuple[float, float]:
    design = np.column_stack([np.ones(len(years)), years])
    intercept, slope = np.linalg.lstsq(design, values, rcond=None)[0]
    return float(intercept), float(slope)


def detrend_with_training(
    train_years: np.ndarray,
    train_values: np.ndarray,
    test_year: float,
    test_value: float,
) -> tuple[np.ndarray, float]:
    intercept, slope = fit_trend(train_years, train_values)
    train_residual = train_values - (intercept + slope * train_years)
    test_residual = test_value - (intercept + slope * test_year)
    return train_residual, float(test_residual)


def predict_fold(
    train: pd.DataFrame,
    test: pd.Series,
    features: tuple[str, ...],
) -> tuple[float, float]:
    required = ["mature_djf_type_raw_c", *features]
    train = train.dropna(subset=required)
    if len(train) < 15 or test[required].isna().any():
        return np.nan, np.nan
    years = train["year"].to_numpy(dtype=float)
    test_year = float(test["year"])
    target_train, observed = detrend_with_training(
        years,
        train["mature_djf_type_raw_c"].to_numpy(dtype=float),
        test_year,
        float(test["mature_djf_type_raw_c"]),
    )
    train_columns = []
    test_values = []
    for feature in features:
        residual, test_residual = detrend_with_training(
            years,
            train[feature].to_numpy(dtype=float),
            test_year,
            float(test[feature]),
        )
        scale = float(np.std(residual, ddof=1))
        if not np.isfinite(scale) or scale == 0:
            return np.nan, np.nan
        train_columns.append(residual / scale)
        test_values.append(test_residual / scale)
    design = np.column_stack(
        [np.ones(len(train)), np.column_stack(train_columns)]
    )
    coefficients = np.linalg.lstsq(design, target_train, rcond=None)[0]
    prediction = float(np.dot(np.r_[1.0, test_values], coefficients))
    return prediction, observed


def walk_forward_predictions(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in MONTHS:
        current = monthly.loc[monthly["month"].eq(month)].sort_values("year")
        for year in range(TEST_YEARS[0], TEST_YEARS[1] + 1):
            test_rows = current.loc[current["year"].eq(year)]
            if test_rows.empty:
                continue
            test = test_rows.iloc[0]
            train = current.loc[current["year"].lt(year)]
            for model, features in MODEL_FEATURES.items():
                prediction, observed = predict_fold(train, test, features)
                rows.append(
                    {
                        "year": year,
                        "month": month,
                        "model": model,
                        "prediction_type_residual_c": prediction,
                        "observed_type_residual_c": observed,
                        "n_training_years": len(train),
                    }
                )
    return pd.DataFrame(rows)


def predict_event_fold(
    train: pd.DataFrame,
    test: pd.Series,
    features: tuple[str, ...],
) -> tuple[float, float]:
    """Ridge prediction after fold-specific detrending and scaling."""
    required = ["mature_djf_type_raw_c", *features]
    train = train.dropna(subset=required)
    if len(train) < 10 or test[required].isna().any():
        return np.nan, np.nan
    years = train["year"].to_numpy(dtype=float)
    test_year = float(test["year"])
    target_train, observed = detrend_with_training(
        years,
        train["mature_djf_type_raw_c"].to_numpy(dtype=float),
        test_year,
        float(test["mature_djf_type_raw_c"]),
    )
    train_columns = []
    test_values = []
    for feature in features:
        residual, test_residual = detrend_with_training(
            years,
            train[feature].to_numpy(dtype=float),
            test_year,
            float(test[feature]),
        )
        scale = float(np.std(residual, ddof=1))
        if not np.isfinite(scale) or scale == 0:
            return np.nan, np.nan
        train_columns.append(residual / scale)
        test_values.append(test_residual / scale)
    x_train = np.column_stack(train_columns)
    gram = x_train.T @ x_train
    coefficients = np.linalg.solve(
        gram + RIDGE_ALPHA * np.eye(gram.shape[0]),
        x_train.T @ target_train,
    )
    return float(np.asarray(test_values) @ coefficients), observed


def event_loeo_predictions(
    monthly: pd.DataFrame,
    event_years: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    event_monthly = monthly.loc[monthly["year"].isin(event_years)]
    for month in MONTHS:
        current = event_monthly.loc[event_monthly["month"].eq(month)]
        for year in event_years:
            test = current.loc[current["year"].eq(year)].iloc[0]
            train = current.loc[current["year"].ne(year)]
            for model, features in MODEL_FEATURES.items():
                prediction, observed = predict_event_fold(
                    train,
                    test,
                    features,
                )
                rows.append(
                    {
                        "year": year,
                        "month": month,
                        "model": model,
                        "prediction_type_residual_c": prediction,
                        "observed_type_residual_c": observed,
                        "n_training_events": len(train),
                        "ridge_alpha": RIDGE_ALPHA,
                    }
                )
    return pd.DataFrame(rows)


def paired_improvement_p(
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
    seed: int,
) -> float:
    improvement = (baseline - observed) ** 2 - (predicted - observed) ** 2
    observed_mean = float(np.mean(improvement))
    rng = np.random.default_rng(seed)
    signs = rng.choice(
        (-1.0, 1.0),
        size=(PERMUTATION_SAMPLES, len(improvement)),
    )
    null = np.mean(signs * improvement[None, :], axis=1)
    return float((np.sum(null >= observed_mean) + 1) / (len(null) + 1))


def bootstrap_skill(
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
    seed: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = rng.integers(
        0,
        len(observed),
        size=(BOOTSTRAP_SAMPLES, len(observed)),
    )
    rmse = np.sqrt(
        np.mean((predicted[samples] - observed[samples]) ** 2, axis=1)
    )
    base_rmse = np.sqrt(
        np.mean((baseline[samples] - observed[samples]) ** 2, axis=1)
    )
    skill = 1.0 - rmse / base_rmse
    return tuple(np.nanpercentile(skill, [2.5, 97.5]).astype(float))


def benjamini_hochberg(values: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna()
    if valid.empty:
        return output
    order = valid.sort_values().index
    ranked = valid.loc[order].to_numpy(dtype=float)
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output.loc[order] = np.minimum(adjusted, 1.0)
    return output


def summarize_skill(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in MONTHS:
        subset = predictions.loc[predictions["month"].eq(month)]
        baseline = subset.loc[
            subset["model"].eq("Type persistence"),
            ["year", "prediction_type_residual_c"],
        ].rename(columns={"prediction_type_residual_c": "baseline"})
        for model_index, model in enumerate(MODEL_FEATURES):
            current = subset.loc[
                subset["model"].eq(model),
                [
                    "year",
                    "prediction_type_residual_c",
                    "observed_type_residual_c",
                ],
            ].merge(baseline, on="year", validate="one_to_one")
            current = current.replace([np.inf, -np.inf], np.nan).dropna()
            observed = current["observed_type_residual_c"].to_numpy(float)
            predicted = current["prediction_type_residual_c"].to_numpy(float)
            persistence = current["baseline"].to_numpy(float)
            rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
            base_rmse = float(np.sqrt(np.mean((persistence - observed) ** 2)))
            skill = 1.0 - rmse / base_rmse
            lower, upper = bootstrap_skill(
                observed,
                predicted,
                persistence,
                seed=20260730 + month * 100 + model_index,
            )
            rows.append(
                {
                    "month": month,
                    "model": model,
                    "n_test": len(current),
                    "rmse_c": rmse,
                    "persistence_rmse_c": base_rmse,
                    "rmse_skill_vs_persistence": skill,
                    "skill_ci_2p5": lower,
                    "skill_ci_97p5": upper,
                    "correlation": float(
                        np.corrcoef(predicted, observed)[0, 1]
                    ),
                    "sign_accuracy": float(
                        np.mean(np.sign(predicted) == np.sign(observed))
                    ),
                    "paired_improvement_p_one_sided": (
                        np.nan
                        if model == "Type persistence"
                        else paired_improvement_p(
                            observed,
                            predicted,
                            persistence,
                            seed=20260730 + month * 100 + model_index,
                        )
                    ),
                }
            )
    result = pd.DataFrame(rows)
    tested = result["model"].ne("Type persistence")
    result.loc[tested, "bh_fdr_q_across_model_month_tests"] = (
        benjamini_hochberg(
            result.loc[tested, "paired_improvement_p_one_sided"]
        )
    )
    return result


def permutation_correlation(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
) -> tuple[float, float, int]:
    valid = np.isfinite(x) & np.isfinite(y)
    x = np.asarray(x[valid], dtype=float)
    y = np.asarray(y[valid], dtype=float)
    correlation = float(np.corrcoef(x, y)[0, 1])
    rng = np.random.default_rng(seed)
    null = np.empty(PERMUTATION_SAMPLES, dtype=float)
    for index in range(PERMUTATION_SAMPLES):
        null[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    p_value = float(
        (np.sum(np.abs(null) >= abs(correlation)) + 1)
        / (PERMUTATION_SAMPLES + 1)
    )
    return correlation, p_value, len(x)


def build_event_evidence(
    indices: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(EVENT_BASE_CSV)
    rows = []
    for event in events.itertuples():
        subset = indices.loc[
            indices["year"].eq(event.event_year)
            & indices["month"].isin((5, 6))
        ]
        row = {
            "event_year": event.event_year,
            "event_label": event.event_label,
            "mature_djf_type_index_c": event.mature_djf_type_index_c,
            "mature_flavor": event.mature_flavor,
        }
        for feature in FEATURE_LABELS:
            row[f"{feature}_may_jun_anom"] = float(
                subset[f"{feature}_anom"].mean()
            )
        rows.append(row)
    event_frame = pd.DataFrame(rows)
    correlation_rows = []
    for feature_index, (feature, label) in enumerate(FEATURE_LABELS.items()):
        correlation, p_value, sample_size = permutation_correlation(
            event_frame[f"{feature}_may_jun_anom"].to_numpy(float),
            event_frame["mature_djf_type_index_c"].to_numpy(float),
            seed=20260730 + feature_index,
        )
        correlation_rows.append(
            {
                "feature": feature,
                "label": label,
                "correlation_with_djf_nino3_minus_nino4": correlation,
                "two_sided_permutation_p": p_value,
                "n_events": sample_size,
            }
        )
    correlations = pd.DataFrame(correlation_rows)
    correlations["bh_fdr_q_across_ten_predictors"] = benjamini_hochberg(
        correlations["two_sided_permutation_p"]
    )
    return event_frame, correlations


def plot_event_processes(indices: pd.DataFrame) -> None:
    setup_style()
    events = {1997: "#C44E52", 2015: "#4C72B0", 2023: "#00876C"}
    panels = [
        (
            "wwv_centroid_deg_e_anom",
            "(a) Eastward shift of warm-water volume",
            "Centroid anomaly (° longitude)",
        ),
        (
            "wwv_east_fraction_anom",
            "(b) Warm-volume fraction east of the dateline",
            "Fraction anomaly",
        ),
        (
            "ohc300_east_tendency_wm2_anom",
            "(c) Eastern upper-ocean heat-content tendency",
            "OHC tendency anomaly (W m$^{-2}$)",
        ),
        (
            "hadv_east_kmonth_anom",
            "(d) Eastern horizontal-advection proxy",
            "Temperature tendency anomaly (K month$^{-1}$)",
        ),
        (
            "vadv_east_kmonth_anom",
            "(e) Eastern vertical-advection proxy",
            "Temperature tendency anomaly (K month$^{-1}$)",
        ),
        (
            "surface_heating_east_kmonth_anom",
            "(f) Eastern surface-heating proxy",
            "Temperature tendency anomaly (K month$^{-1}$)",
        ),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(10.2, 10.4), sharex=True)
    for axis, (column, title, ylabel) in zip(axes.flat, panels):
        axis.axhline(0.0, color="#777777", linewidth=0.8)
        for year, color in events.items():
            subset = indices.loc[indices["year"].eq(year)]
            axis.plot(
                subset["month"],
                subset[column],
                color=color,
                marker="o",
                linewidth=2.0,
                markersize=4.2,
                label=str(year),
            )
        axis.set_title(title, loc="left", fontweight="bold")
        axis.set_ylabel(ylabel)
        axis.grid(color="#D8D8D8", linewidth=0.55, alpha=0.65)
    for axis in axes[-1]:
        axis.set_xticks(MONTHS, MONTH_LABELS)
        axis.set_xlabel("Development-year calendar month")
    axes[0, 0].legend(ncol=3, frameon=False, loc="best")
    fig.suptitle(
        "SODA3 heat storage and redistribution before EP-like events",
        fontsize=14,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.008,
        "Same-calendar-month 1980–2024 climatology and linear trend removed. "
        "Advection uses monthly means and is a process proxy, not a closed heat budget.",
        ha="center",
        fontsize=8.0,
        color="#555555",
    )
    fig.tight_layout(rect=(0.02, 0.035, 0.995, 0.97))
    EVENT_PNG.parent.mkdir(parents=True, exist_ok=True)
    EVENT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(EVENT_PNG)
    fig.savefig(EVENT_PDF)
    plt.close(fig)


def plot_full_evidence(
    event_frame: pd.DataFrame,
    correlations: pd.DataFrame,
    skill: pd.DataFrame,
    loeo_skill: pd.DataFrame,
) -> None:
    setup_style()
    fig = plt.figure(figsize=(13.5, 10.0))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=(1.25, 1.0),
        height_ratios=(1.18, 1.0),
        hspace=0.36,
        wspace=0.34,
    )
    ax_heat = fig.add_subplot(grid[0, 0])
    feature_columns = [
        f"{feature}_may_jun_anom" for feature in FEATURE_LABELS
    ]
    matrix = event_frame[feature_columns].to_numpy(float)
    matrix = (matrix - np.nanmean(matrix, axis=0)) / np.nanstd(
        matrix, axis=0, ddof=1
    )
    image = ax_heat.imshow(
        matrix,
        aspect="auto",
        cmap="RdBu_r",
        vmin=-2.4,
        vmax=2.4,
    )
    ax_heat.set_yticks(
        np.arange(len(event_frame)),
        event_frame["event_label"],
    )
    ax_heat.set_xticks(
        np.arange(len(FEATURE_LABELS)),
        [
            "WWV\ncenter",
            "East\nWWV",
            "OHC\ntend.",
            "H adv.",
            "V adv.",
            "Qnet",
            "Barrier",
            "SSH E-W",
            "Stress",
            "U sub.",
        ],
        rotation=35,
        ha="right",
    )
    ax_heat.set_title(
        "(a) Standardized May–June process anomalies by warm event",
        loc="left",
        fontweight="bold",
    )

    ax_corr = fig.add_subplot(grid[0, 1])
    ordered = correlations.sort_values(
        "correlation_with_djf_nino3_minus_nino4"
    )
    colors = np.where(
        ordered["bh_fdr_q_across_ten_predictors"] < 0.05,
        "#B2182B",
        "#7F8C8D",
    )
    ax_corr.barh(
        np.arange(len(ordered)),
        ordered["correlation_with_djf_nino3_minus_nino4"],
        color=colors,
    )
    ax_corr.set_yticks(np.arange(len(ordered)), ordered["label"])
    ax_corr.axvline(0.0, color="#333333", linewidth=0.8)
    ax_corr.set_xlim(-1.0, 1.0)
    ax_corr.set_xlabel("Correlation with mature DJF Niño-3 − Niño-4")
    ax_corr.set_title(
        "(b) Full 13-event associations",
        loc="left",
        fontweight="bold",
    )
    ax_corr.text(
        0.99,
        0.02,
        "red: BH-FDR q < 0.05",
        transform=ax_corr.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.8,
        color="#555555",
    )
    ax_corr.grid(axis="x", color="#D8D8D8", linewidth=0.55, alpha=0.65)

    def draw_skill(
        axis: plt.Axes,
        current_skill: pd.DataFrame,
        title: str,
        *,
        show_labels: bool,
    ):
        nonbaseline = current_skill.loc[
            current_skill["model"].ne("Type persistence")
        ].copy()
        model_order = [
            model for model in MODEL_FEATURES if model != "Type persistence"
        ]
        pivot = nonbaseline.pivot(
            index="model",
            columns="month",
            values="rmse_skill_vs_persistence",
        ).reindex(model_order)
        current_image = axis.imshow(
            pivot.to_numpy(),
            aspect="auto",
            cmap="RdBu_r",
            vmin=-0.5,
            vmax=0.5,
        )
        axis.set_yticks(
            np.arange(len(pivot.index)),
            pivot.index if show_labels else [],
        )
        axis.set_xticks(np.arange(6), MONTH_LABELS)
        axis.set_xlabel("Initialization month")
        axis.set_title(title, loc="left", fontweight="bold", fontsize=9.5)
        for row_index, model in enumerate(pivot.index):
            for column_index, month in enumerate(MONTHS):
                value = pivot.loc[model, month]
                current = nonbaseline.loc[
                    nonbaseline["model"].eq(model)
                    & nonbaseline["month"].eq(month)
                ].iloc[0]
                marker = (
                    "*"
                    if current["bh_fdr_q_across_model_month_tests"] < 0.05
                    else ""
                )
                axis.text(
                    column_index,
                    row_index,
                    f"{value:+.2f}{marker}",
                    ha="center",
                    va="center",
                    fontsize=6.3,
                    color=(
                        "white"
                        if np.isfinite(value) and abs(value) > 0.32
                        else "#222222"
                    ),
                )
        return current_image

    ax_skill = fig.add_subplot(grid[1, 0])
    draw_skill(
        ax_skill,
        skill,
        "(c) All-year walk-forward skill",
        show_labels=True,
    )
    ax_loeo = fig.add_subplot(grid[1, 1])
    draw_skill(
        ax_loeo,
        loeo_skill,
        "(d) El Niño-event leave-one-out skill",
        show_labels=False,
    )
    fig.suptitle(
        "Can SODA3 identify the transition from warm-water recharge to EP growth?",
        fontsize=14.2,
        fontweight="bold",
        y=0.992,
    )
    fig.text(
        0.5,
        0.006,
        "* denotes BH-FDR q < 0.05 within each 72-test family. "
        "Positive values improve on same-sample SST-pattern persistence; "
        "both panels use a common −0.5 to +0.5 scale.",
        ha="center",
        fontsize=8.0,
        color="#555555",
    )
    fig.subplots_adjust(left=0.17, right=0.97, top=0.95, bottom=0.055)
    EVIDENCE_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(EVIDENCE_PNG)
    fig.savefig(EVIDENCE_PDF)
    plt.close(fig)


def write_summary(
    indices: pd.DataFrame,
    event_frame: pd.DataFrame,
    correlations: pd.DataFrame,
    skill: pd.DataFrame,
    loeo_skill: pd.DataFrame,
) -> dict[str, object]:
    best_correlation = correlations.iloc[
        correlations[
            "correlation_with_djf_nino3_minus_nino4"
        ].abs().argmax()
    ]
    tested = skill.loc[skill["model"].ne("Type persistence")]
    best_skill = tested.sort_values(
        "rmse_skill_vs_persistence",
        ascending=False,
    ).iloc[0]
    robust_correlations = correlations.loc[
        correlations["bh_fdr_q_across_ten_predictors"] < 0.05
    ]
    robust_skill = tested.loc[
        tested["bh_fdr_q_across_model_month_tests"] < 0.05
    ]
    tested_loeo = loeo_skill.loc[
        loeo_skill["model"].ne("Type persistence")
    ]
    best_loeo = tested_loeo.sort_values(
        "rmse_skill_vs_persistence",
        ascending=False,
    ).iloc[0]
    robust_loeo = tested_loeo.loc[
        tested_loeo["bh_fdr_q_across_model_month_tests"] < 0.05
    ]
    selected_2023 = indices.loc[indices["year"].eq(2023)]
    selected_1997 = indices.loc[indices["year"].eq(1997)]
    diagnostics = {
        "baseline": list(BASELINE),
        "event_count": len(event_frame),
        "walkforward_years": list(TEST_YEARS),
        "best_event_correlation": best_correlation.to_dict(),
        "best_walkforward_skill": best_skill.to_dict(),
        "best_event_loeo_skill": best_loeo.to_dict(),
        "fdr_significant_event_correlations": robust_correlations.to_dict(
            orient="records"
        ),
        "fdr_significant_walkforward_tests": robust_skill.to_dict(
            orient="records"
        ),
        "fdr_significant_event_loeo_tests": robust_loeo.to_dict(
            orient="records"
        ),
        "event_2023_may_june": {
            feature: float(
                selected_2023.loc[
                    selected_2023["month"].isin((5, 6)),
                    f"{feature}_anom",
                ].mean()
            )
            for feature in FEATURE_LABELS
        },
        "event_1997_may_june": {
            feature: float(
                selected_1997.loc[
                    selected_1997["month"].isin((5, 6)),
                    f"{feature}_anom",
                ].mean()
            )
            for feature in FEATURE_LABELS
        },
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if robust_correlations.empty:
        correlation_sentence = (
            "10 个预先指定的过程量中，没有一个在 13 个事件上通过 "
            "BH-FDR 0.05；因此事件相关只能当作候选机制，不能当作已确认因果。"
        )
    else:
        items = "、".join(
            f"{row.label} (r={row.correlation_with_djf_nino3_minus_nino4:+.2f}, "
            f"q={row.bh_fdr_q_across_ten_predictors:.3f})"
            for row in robust_correlations.itertuples()
        )
        correlation_sentence = f"通过 BH-FDR 0.05 的事件关系为：{items}。"
    if robust_skill.empty:
        skill_sentence = (
            f"所有新增模型在 {len(tested)} 个模型×月份检验的 BH-FDR "
            "校正后均未达到 "
            "q<0.05；当前不能声称它们稳定提高了类型预测。"
        )
    else:
        items = "、".join(
            f"{MONTH_LABELS[row.month-1]} {row.model} "
            f"(skill={row.rmse_skill_vs_persistence:+.2f}, "
            f"q={row.bh_fdr_q_across_model_month_tests:.3f})"
            for row in robust_skill.itertuples()
        )
        skill_sentence = f"通过 BH-FDR 0.05 的预测改进为：{items}。"
    if robust_loeo.empty:
        loeo_sentence = (
            f"暖事件条件下的最佳候选是 "
            f"**{MONTH_LABELS[int(best_loeo['month'])-1]} 的 "
            f"{best_loeo['model']}**（skill="
            f"{best_loeo['rmse_skill_vs_persistence']:+.2f}，"
            f"单项 p={best_loeo['paired_improvement_p_one_sided']:.3f}），"
            f"但在 {len(tested_loeo)} 个模型×月份检验校正后 "
            f"q={best_loeo['bh_fdr_q_across_model_month_tests']:.3f}，"
            "因此是值得扩大样本验证的候选信号，而不是已确认技巧。"
        )
    else:
        items = "、".join(
            f"{MONTH_LABELS[row.month-1]} {row.model} "
            f"(skill={row.rmse_skill_vs_persistence:+.2f}, "
            f"q={row.bh_fdr_q_across_model_month_tests:.3f})"
            for row in robust_loeo.itertuples()
        )
        loeo_sentence = f"暖事件留一检验中通过 BH-FDR 的组合为：{items}。"
    text = f"""# SODA3 热含量—再分配—东部放大分析

## 这一步回答什么

单看 FEP 海温异常，只能看到东端已经暖了多少；SODA3 可以把问题拆成：

1. **蓄积**：整个热带太平洋 20°C 以上暖水体积（WWV）有多少；
2. **再分配**：暖水体积重心和日界线以东的占比是否向东移动；
3. **东部放大/抑制**：水平输送、上升流相关垂直平流、表面净加热分别是否有利于东部增暖；
4. **记忆与屏障**：SSH 东西差、次表层东向流、混合层/障碍层是否帮助暖水保持并传播；
5. **预测检验**：这些量能否在只使用此前年份训练的条件下，优于当月 Niño-3−Niño-4 类型持续性。

## 统一计算口径

- 数据：SODA3.15.2，1980–2024 年 1–6 月，5°S–5°N、120°E–80°W、上层 300 m。
- 气候态：全部量统一使用 **1980–2024 同月气候态并去除同月线性趋势**。
- 成熟类型目标：下一成熟 DJF 的 OISST Niño-3−Niño-4；正值为相对 EP-like，负值为相对 CP-like。
- 事件证据：NOAA ONI 定义的 13 个暖事件，使用 5–6 月平均过程异常。
- 预测证据：2000–2023 逐年向前检验；每一折只用目标年以前资料估计趋势、标准差和回归。
- 条件预测：对 13 个暖事件逐一留出，使用另外 12 个暖事件训练固定
  α=1 的岭回归；趋势和标准差也只在每一折训练集内估计。
- 水平平流代理：`−(u∂T/∂x + v∂T/∂y)`；垂直平流代理：
  `w∂T/∂z`（SODA `wt` 向上为正、深度向下为正）；表面受热代理：
  `Qnet/(ρCp·max(MLD,5 m))`。

## 目前结果

- 13 事件中绝对相关最高的候选量是 **{best_correlation['label']}**：
  r={best_correlation['correlation_with_djf_nino3_minus_nino4']:+.2f}，
  双侧置换 p={best_correlation['two_sided_permutation_p']:.3f}，
  BH-FDR q={best_correlation['bh_fdr_q_across_ten_predictors']:.3f}。
- {correlation_sentence}
- 逐年预测的表面最佳组合是 **{MONTH_LABELS[int(best_skill['month'])-1]} 的 {best_skill['model']}**：
  相对类型持续性的 RMSE skill=
  {best_skill['rmse_skill_vs_persistence']:+.2f}，95% bootstrap 区间
  [{best_skill['skill_ci_2p5']:+.2f}, {best_skill['skill_ci_97p5']:+.2f}]，
  q={best_skill['bh_fdr_q_across_model_month_tests']:.3f}。
- {skill_sentence}
- {loeo_sentence}

## 怎样理解“转变点”

最合理的工作定义不是一个固定 FEP 阈值，而是一个**连续门槛**：
西部已有暖水储备之后，暖水体积重心、日界线以东 WWV 占比和 SSH 东西差首先显示
**热量是否真的完成向东再分配**；随后，东部垂直平流异常和障碍层显示
**上升流冷却是否减弱、表层暖异常能否被保留**。这两组信号同时成立时，
FEP 暖异常才更可能发展成 EP 型。

本次结果并不支持把表面净热通量或月平均水平平流当成主要“开关”：
表面受热与 EP 程度为负相关（r={float(correlations.loc[correlations['feature'].eq('surface_heating_east_kmonth'), 'correlation_with_djf_nino3_minus_nino4'].iloc[0]):+.2f}，
q={float(correlations.loc[correlations['feature'].eq('surface_heating_east_kmonth'), 'bh_fdr_q_across_ten_predictors'].iloc[0]):.3f}），
更像对海洋增暖的阻尼；水平平流的事件相关很弱
（r={float(correlations.loc[correlations['feature'].eq('hadv_east_kmonth'), 'correlation_with_djf_nino3_minus_nino4'].iloc[0]):+.2f}）。
因此当前数据支持的“转变点”更接近**暖水东移 + 垂直冷却减弱/屏障增强**，
而不是“FEP 到达某个固定温度”。

三次代表事件也符合这一分层：1997 年 5–6 月暖水重心东移
{diagnostics['event_1997_may_june']['wwv_centroid_deg_e']:+.2f}°、东侧 WWV 占比异常
{diagnostics['event_1997_may_june']['wwv_east_fraction']:+.3f}、SSH 东西差异常
{diagnostics['event_1997_may_june']['ssh_ew_m']:+.3f} m；2023 年对应值只有
{diagnostics['event_2023_may_june']['wwv_centroid_deg_e']:+.2f}°、
{diagnostics['event_2023_may_june']['wwv_east_fraction']:+.3f} 和
{diagnostics['event_2023_may_june']['ssh_ew_m']:+.3f} m。2023 虽然最终仍为 EP-like，
但早夏的海洋再分配明显弱于 1997，解释了它不是同等级的强东部发展。

## 必须保留的限制

- `-u·∇T`、`w∂T/∂z` 和 `Qnet/(ρCp h)` 用的是月平均场，是**过程代理量**；
  月平均乘积不等于瞬变协方差，且没有显式闭合混合、卷入、扩散和资料同化增量。
- SODA3.15.2 由 ERA5 强迫，所以海洋量与 ERA5 风/通量不是独立资料验证。
- 事件只有 13 个，多重检验校正后的结果优先于单个最好看的相关系数。
- 预测增益必须看逐年外推，而不能用全时段回归拟合优度代替。

## 数据与方法出处

- SODA 官方说明：<https://www.soda.umd.edu/>（SODA3.15.2、ERA5 强迫、
  1980–2024；并给出 Carton, Chepurin & Chen 2018 的正式引用）。
- APDRC 变量说明：<https://apdrc.soest.hawaii.edu/datadoc/soda_3.15.2.php>
  （`temp/wt/ssh/mlt/mlp/net_heating/u/v/taux` 的定义与单位）。
- 建议引用：Carton, J. A., G. A. Chepurin, and L. Chen (2018),
  *SODA3: A New Ocean Climate Reanalysis*, Journal of Climate, 31,
  6967–6983, doi:10.1175/JCLI-D-18-0149.1。

## 输出

- 过程指标：`{INDEX_CSV}`
- 事件表：`{EVENT_CSV}`
- 事件相关：`{CORR_CSV}`
- 逐年预测：`{PRED_CSV}`
- 预测技巧：`{SKILL_CSV}`
- 暖事件留一预测：`{LOEO_PRED_CSV}`
- 暖事件留一技巧：`{LOEO_SKILL_CSV}`
- 三事件过程图：`{EVENT_PDF}`
- 全事件与预测检验图：`{EVIDENCE_PDF}`
"""
    SUMMARY_MD.write_text(text, encoding="utf-8")
    return diagnostics


def main() -> None:
    for path in (TEMP_NC, PROCESS_NC, OHC_CSV, MONTHLY_BASE_CSV, EVENT_BASE_CSV):
        if not path.exists():
            raise FileNotFoundError(path)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)

    with xr.open_dataset(TEMP_NC) as temperature_dataset, xr.open_dataset(
        PROCESS_NC
    ) as process_dataset:
        temperature = derive_temperature_indices(temperature_dataset)
        processes = derive_process_indices(temperature_dataset, process_dataset)
    indices = temperature.merge(
        processes,
        on=["time", "year", "month"],
        validate="one_to_one",
    )
    indices = add_ohc_tendency(indices)
    indices = add_fixed_anomalies(indices)
    indices.to_csv(INDEX_CSV, index=False)

    event_frame, correlations = build_event_evidence(indices)
    event_frame.to_csv(EVENT_CSV, index=False)
    correlations.to_csv(CORR_CSV, index=False)

    base_monthly = pd.read_csv(MONTHLY_BASE_CSV)
    raw_features = ["year", "month", *FEATURE_LABELS]
    monthly = base_monthly.merge(
        indices[raw_features],
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )
    predictions = walk_forward_predictions(monthly)
    skill = summarize_skill(predictions)
    event_years = (
        pd.read_csv(EVENT_BASE_CSV)["event_year"].astype(int).tolist()
    )
    loeo_predictions = event_loeo_predictions(monthly, event_years)
    loeo_skill = summarize_skill(loeo_predictions)
    predictions.to_csv(PRED_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    loeo_predictions.to_csv(LOEO_PRED_CSV, index=False)
    loeo_skill.to_csv(LOEO_SKILL_CSV, index=False)

    plot_event_processes(indices)
    plot_full_evidence(event_frame, correlations, skill, loeo_skill)
    diagnostics = write_summary(
        indices,
        event_frame,
        correlations,
        skill,
        loeo_skill,
    )
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {INDEX_CSV}", flush=True)
    print(f"Wrote {EVENT_PDF}", flush=True)
    print(f"Wrote {EVIDENCE_PDF}", flush=True)
    print(f"Wrote {SUMMARY_MD}", flush=True)


if __name__ == "__main__":
    main()
