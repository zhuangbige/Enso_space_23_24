#!/usr/bin/env python3
"""Test whether the full SST pattern mediates OHC--atmosphere coupling.

The analysis uses the project's fixed 13 warm events.  March--April central-
Pacific 0--300 m OHC is the subsurface precursor.  The surface mediator is the
May--June tropical-Pacific OISST field, represented by two training-only PCR
scores plus absolute-SST convective metrics.  May--June ERA5 u850, OLR,
precipitation, and zonal wind stress are the atmospheric responses.

All model comparisons are leave-one-event-out.  The primary PCR dimension
(two) and ridge penalty (one) are fixed before looking at the current results.
This is a small-sample observational mediation test, not a coupled-model causal
experiment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

RUNTIME = Path("/private/tmp/codex_surface_ohc_mediation")
RUNTIME.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, "/Users/daiyue/.codex/skills/climate-plotting/scripts")
from climate_plot_style import add_panel_labels, apply_climate_style  # noqa: E402


DERIVED = ROOT / "data/derived/research_2026"
OISST_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
ERA5_PRECIP_FILES = (
    ROOT / "data/raw/era5/era5_monthly_precip_tropics_1deg_1980_2026_jan_may.nc",
    ROOT / "data/raw/era5/era5_monthly_precip_tropics_1deg_1980_2026_jun.nc",
)
MONTHLY_CSV = DERIVED / "enso_type_coupling_monthly_1982_2023.csv"
EVENT_CSV = DERIVED / "enso_type_coupling_event_summary.csv"
OHC_EVENT_CSV = DERIVED / "third_question_coupled_attribution_event_table.csv"

OUT = ROOT / "outputs/research_2026/surface_sst_ohc_atmosphere_mediation"
EVENT_OUT = DERIVED / "surface_sst_ohc_atmosphere_mediation_event_table.csv"
PRED_OUT = DERIVED / "surface_sst_ohc_atmosphere_mediation_loeo_predictions.csv"
SKILL_OUT = DERIVED / "surface_sst_ohc_atmosphere_mediation_model_skill.csv"
INCREMENT_OUT = DERIVED / "surface_sst_ohc_atmosphere_mediation_increment_tests.csv"
SENSITIVITY_OUT = DERIVED / "surface_sst_ohc_atmosphere_mediation_sensitivity.csv"
DIAGNOSTICS_OUT = DERIVED / "surface_sst_ohc_atmosphere_mediation_diagnostics.json"
FIGURE_PNG = OUT / "fig_surface_sst_ohc_atmosphere_mediation.png"
FIGURE_PDF = OUT / "fig_surface_sst_ohc_atmosphere_mediation.pdf"
CONTEXT_PNG = OUT / "fig_may_june_sst_pattern_context_1997_2015_2023.png"
CONTEXT_PDF = OUT / "fig_may_june_sst_pattern_context_1997_2015_2023.pdf"
REPORT_MD = OUT / "SURFACE_SST_OHC_ATMOSPHERE_MEDIATION_CN.md"

EVENT_YEARS = np.asarray(
    [1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023],
    dtype=int,
)
MONTHS = (5, 6)
SST_BASELINE = (1982, 2024)
FIELD_BASELINE = (1980, 2024)
MAP_DOMAIN = (-15.0, 15.0, 120.0, 280.0)
PRIMARY_PCS = 2
PRIMARY_ALPHA = 1.0
WARM_THRESHOLD_C = 27.5
BOOTSTRAP_SAMPLES = 20_000
PERMUTATION_SAMPLES = 50_000
RNG_SEED = 20260816

GROUP_COLORS = {
    "classic EP": "#D55E00",
    "CP": "#009E73",
    "other warm": "#0072B2",
    "2023 weak-coupling EP": "#7A3DB8",
}

RESPONSE_META = {
    "atmosphere_composite_z": ("Atmosphere composite", "SD"),
    "u850_response_z": ("850-hPa westerly", "SD"),
    "convection_response_z": ("Convection (-OLR)", "SD"),
    "precip_response_z": ("Precipitation", "SD"),
    "tau_response_z": ("Eastward wind stress", "SD"),
}

MODEL_ORDER = [
    "Intercept only",
    "OHC only",
    "SST indices",
    "Full SST pattern",
    "Full SST pattern + OHC",
]
MODEL_COLORS = {
    "Intercept only": "#BDBDBD",
    "OHC only": "#4C78A8",
    "SST indices": "#72B7B2",
    "Full SST pattern": "#F58518",
    "Full SST pattern + OHC": "#7A3DB8",
}


def normalize_field(field: xr.DataArray) -> xr.DataArray:
    rename: dict[str, str] = {}
    if "valid_time" in field.coords:
        rename["valid_time"] = "time"
    if "latitude" in field.coords:
        rename["latitude"] = "lat"
    if "longitude" in field.coords:
        rename["longitude"] = "lon"
    field = field.rename(rename)
    field = field.assign_coords(lon=field.lon % 360.0).sortby("lon").sortby("lat")
    field = field.assign_coords(
        time=pd.to_datetime(field.time.values).to_period("M").to_timestamp()
    )
    return field


def weighted_box(
    field: xr.DataArray,
    lon0: float,
    lon1: float,
    lat0: float = -5.0,
    lat1: float = 5.0,
) -> xr.DataArray:
    subset = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(f"Empty box: lon={lon0}:{lon1}, lat={lat0}:{lat1}")
    return subset.weighted(np.cos(np.deg2rad(subset.lat))).mean(
        ("lat", "lon"), skipna=True
    )


def same_month_residual_1d(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int],
) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    result = np.full(values.shape, np.nan, dtype=float)
    for month in sorted(set(times.month.tolist())):
        selected = times.month == month
        fit = (
            selected
            & (times.year >= baseline[0])
            & (times.year <= baseline[1])
            & np.isfinite(values)
        )
        if fit.sum() < 20:
            raise ValueError(f"Too few baseline values for month {month}")
        slope, intercept = np.polyfit(times.year[fit].astype(float), values[fit], 1)
        valid = selected & np.isfinite(values)
        result[valid] = values[valid] - (
            intercept + slope * times.year[valid].astype(float)
        )
    return result


def detrend_same_month_grid(
    field: xr.DataArray,
    baseline: tuple[int, int],
) -> xr.DataArray:
    """Remove a same-month gridpoint linear fit without loading extra products."""
    values = np.asarray(field.values, dtype=np.float64)
    times = pd.DatetimeIndex(field.time.values)
    output = np.full(values.shape, np.nan, dtype=np.float32)
    for month in sorted(set(times.month.tolist())):
        selected = times.month == month
        fit = selected & (times.year >= baseline[0]) & (times.year <= baseline[1])
        fit_values = values[fit]
        fit_years = np.asarray(times.year[fit], dtype=float)
        center = float(fit_years.mean())
        x = fit_years - center
        finite = np.isfinite(fit_values)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(fit_values, axis=0),
            count,
            out=np.full(values.shape[1:], np.nan, dtype=float),
            where=count > 0,
        )
        centered = fit_values - mean
        slope_num = np.nansum(centered * x[:, None, None], axis=0)
        slope_den = np.sum(finite * x[:, None, None] ** 2, axis=0)
        slope = np.divide(
            slope_num,
            slope_den,
            out=np.full(values.shape[1:], np.nan, dtype=float),
            where=slope_den > 0,
        )
        target_years = np.asarray(times.year[selected], dtype=float)
        fitted = mean + (target_years - center)[:, None, None] * slope
        output[selected] = (values[selected] - fitted).astype(np.float32)
    return xr.DataArray(output, coords=field.coords, dims=field.dims, name="ssta")


def open_oisst_may_june() -> tuple[xr.DataArray, xr.DataArray]:
    pieces: list[xr.DataArray] = []
    for month, tag in ((5, "may"), (6, "jun")):
        path = OISST_DIR / f"oisst_sst_tropics_1deg_{tag}_1982_2026.nc"
        if not path.exists():
            raise FileNotFoundError(path)
        with xr.open_dataset(path, engine="scipy") as source:
            field = normalize_field(source["sst"].load())
        if str(field.attrs.get("units", "")).lower() not in {
            "degc",
            "degree_celsius",
            "degrees c",
        }:
            raise ValueError(f"Unexpected OISST unit in {path}: {field.attrs.get('units')}")
        if not np.all(pd.DatetimeIndex(field.time.values).month == month):
            raise ValueError(f"Unexpected months in {path}")
        pieces.append(field)
    raw = xr.concat(pieces, dim="time").sortby("time")
    anomaly = detrend_same_month_grid(raw, SST_BASELINE)
    return raw, anomaly


def composite_by_year(field: xr.DataArray) -> xr.DataArray:
    selected = field.sel(time=field.time.dt.year.isin(EVENT_YEARS))
    result = selected.groupby("time.year").mean("time", skipna=True)
    result = result.sel(year=EVENT_YEARS)
    if result.sizes["year"] != len(EVENT_YEARS):
        raise ValueError("Incomplete event SST composites")
    return result


def scalar_sst_features(raw: xr.DataArray, anomaly: xr.DataArray) -> pd.DataFrame:
    raw_event = composite_by_year(raw)
    anom_event = composite_by_year(anomaly)
    nino3 = weighted_box(anom_event, 210.0, 270.0)
    nino4 = weighted_box(anom_event, 160.0, 210.0)
    nino34 = weighted_box(anom_event, 190.0, 240.0)
    fep = weighted_box(anom_event, 270.0, 280.0)
    cp_abs = weighted_box(raw_event, 160.0, 220.0)

    equatorial = raw_event.sel(lat=slice(-5.0, 5.0), lon=slice(160.0, 280.0))
    area = np.cos(np.deg2rad(equatorial.lat)).broadcast_like(equatorial.isel(year=0))
    valid_area = area.where(np.isfinite(equatorial.isel(year=0)), 0.0)
    warm = equatorial >= WARM_THRESHOLD_C
    warm_fraction = (warm * valid_area).sum(("lat", "lon")) / valid_area.sum(
        ("lat", "lon")
    )
    excess = (equatorial - WARM_THRESHOLD_C).clip(min=0.0)
    lon2d = equatorial.lon.broadcast_like(equatorial.isel(year=0))
    excess_weight = excess * valid_area
    warm_centroid = (excess_weight * lon2d).sum(("lat", "lon")) / excess_weight.sum(
        ("lat", "lon")
    )

    return pd.DataFrame(
        {
            "year": EVENT_YEARS,
            "nino34_ssta_c": nino34.values,
            "nino3_minus_nino4_ssta_c": (nino3 - nino4).values,
            "fep_ssta_c": fep.values,
            "cp_absolute_sst_c": cp_abs.values,
            "warm_area_fraction_27p5": warm_fraction.values,
            "warm_excess_centroid_lon_e": warm_centroid.values,
        }
    )


def flattened_event_maps(
    raw: xr.DataArray,
    anomaly: xr.DataArray,
) -> tuple[np.ndarray, np.ndarray, xr.DataArray, xr.DataArray]:
    raw_event = composite_by_year(raw).sel(
        lat=slice(MAP_DOMAIN[0], MAP_DOMAIN[1]),
        lon=slice(MAP_DOMAIN[2], MAP_DOMAIN[3]),
    )
    anom_event = composite_by_year(anomaly).sel(
        lat=slice(MAP_DOMAIN[0], MAP_DOMAIN[1]),
        lon=slice(MAP_DOMAIN[2], MAP_DOMAIN[3]),
    )
    valid = np.isfinite(raw_event.values).all(axis=0) & np.isfinite(
        anom_event.values
    ).all(axis=0)
    if valid.sum() < 1000:
        raise ValueError(f"Too few valid SST grid cells: {valid.sum()}")
    lat_weights = np.sqrt(np.cos(np.deg2rad(raw_event.lat.values)))[:, None]
    weights = np.broadcast_to(lat_weights, valid.shape)[valid]
    raw_flat = raw_event.values[:, valid] * weights[None, :]
    anom_flat = anom_event.values[:, valid] * weights[None, :]
    if not np.isfinite(raw_flat).all() or not np.isfinite(anom_flat).all():
        raise ValueError("Non-finite flattened SST maps")
    return raw_flat, anom_flat, raw_event, anom_event


def load_precip_cp() -> pd.DataFrame:
    pieces: list[xr.DataArray] = []
    for path in ERA5_PRECIP_FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        with xr.open_dataset(path, engine="h5netcdf") as source:
            field = normalize_field(source["tp"].load())
        if field.attrs.get("units") != "m":
            raise ValueError(f"Unexpected ERA5 precipitation unit: {field.attrs.get('units')}")
        pieces.append(field)
    field = xr.concat(pieces, dim="time").sortby("time")
    times = pd.DatetimeIndex(field.time.values)
    keep = times.month.isin(MONTHS)
    field = field.isel(time=np.flatnonzero(keep))
    cp = weighted_box(field, 160.0, 220.0).values.astype(float) * 1000.0
    times = pd.DatetimeIndex(field.time.values)
    anomaly = same_month_residual_1d(cp, times, FIELD_BASELINE)
    return pd.DataFrame(
        {
            "year": times.year,
            "month": times.month,
            "precip_cp_anom_mmday": anomaly,
        }
    )


def build_atmosphere_event_table() -> pd.DataFrame:
    monthly = pd.read_csv(MONTHLY_CSV)
    monthly["time"] = pd.to_datetime(monthly["time"])
    times = pd.DatetimeIndex(monthly.time)
    monthly["tau_cwp_anom_nm2"] = same_month_residual_1d(
        monthly.tau_cwp_raw_nm2.to_numpy(dtype=float), times, (1982, 2023)
    )
    monthly = monthly.merge(
        load_precip_cp(), on=["year", "month"], how="left", validate="one_to_one"
    )
    monthly["convection_anom_wm2"] = -monthly.olr_cp_anom_wm2
    selected = monthly.loc[monthly.month.isin(MONTHS)].copy()
    annual = (
        selected.groupby("year", as_index=False)
        .agg(
            u850_response_ms=("u850_cwp_anom_ms", "mean"),
            convection_response_wm2=("convection_anom_wm2", "mean"),
            precip_response_mmday=("precip_cp_anom_mmday", "mean"),
            tau_response_nm2=("tau_cwp_anom_nm2", "mean"),
        )
        .sort_values("year")
    )
    baseline = annual.loc[annual.year.between(1982, 2023)]
    raw_columns = [
        "u850_response_ms",
        "convection_response_wm2",
        "precip_response_mmday",
        "tau_response_nm2",
    ]
    for column in raw_columns:
        scale = float(baseline[column].std(ddof=1))
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError(f"Invalid atmospheric response scale for {column}")
        annual[column.replace(
            "_ms", "_z"
        ).replace("_wm2", "_z").replace("_mmday", "_z").replace("_nm2", "_z")] = (
            annual[column] / scale
        )
    z_columns = [
        "u850_response_z",
        "convection_response_z",
        "precip_response_z",
        "tau_response_z",
    ]
    annual["atmosphere_composite_z"] = annual[z_columns].mean(axis=1)
    event = annual.loc[annual.year.isin(EVENT_YEARS)].copy()
    event = event.set_index("year").loc[EVENT_YEARS].reset_index()
    if event[list(RESPONSE_META)].isna().any().any():
        raise ValueError("Missing atmospheric response for an event")
    return event


def build_event_table(raw: xr.DataArray, anomaly: xr.DataArray) -> pd.DataFrame:
    group = pd.read_csv(EVENT_CSV)[["year", "group"]]
    ohc = pd.read_csv(OHC_EVENT_CSV)[
        ["year", "ohc300_central_ma_gj_m2", "east_ocean_state_z"]
    ]
    table = (
        pd.DataFrame({"year": EVENT_YEARS})
        .merge(group, on="year", validate="one_to_one")
        .merge(scalar_sst_features(raw, anomaly), on="year", validate="one_to_one")
        .merge(ohc, on="year", validate="one_to_one")
        .merge(build_atmosphere_event_table(), on="year", validate="one_to_one")
        .sort_values("year")
        .reset_index(drop=True)
    )
    if table.isna().any().any():
        raise ValueError(f"Missing event-table values:\n{table.loc[:, table.isna().any()]}")
    return table


def standardize_train_test(
    train: np.ndarray,
    test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    mean = train.mean(axis=0)
    scale = train.std(axis=0, ddof=1)
    scale = np.where(scale > 1.0e-12, scale, 1.0)
    return (train - mean) / scale, (test - mean) / scale


def pcr_features(
    map_values: np.ndarray | None,
    train_index: np.ndarray,
    test_index: np.ndarray,
    n_components: int,
) -> tuple[np.ndarray, np.ndarray]:
    if map_values is None or n_components == 0:
        return np.empty((len(train_index), 0)), np.empty((len(test_index), 0))
    train = map_values[train_index]
    test = map_values[test_index]
    center = train.mean(axis=0)
    _, _, vt = np.linalg.svd(train - center, full_matrices=False)
    count = min(n_components, vt.shape[0], len(train_index) - 2)
    if count < 1:
        raise ValueError("Insufficient training events for PCR")
    train_score = (train - center) @ vt[:count].T
    test_score = (test - center) @ vt[:count].T
    return standardize_train_test(train_score, test_score)


def fit_predict_ridge(
    y: np.ndarray,
    train_index: np.ndarray,
    test_index: np.ndarray,
    *,
    map_values: np.ndarray | None,
    extra_values: np.ndarray | None,
    n_components: int,
    alpha: float,
) -> np.ndarray:
    map_train, map_test = pcr_features(
        map_values, train_index, test_index, n_components
    )
    feature_train = map_train
    feature_test = map_test
    if extra_values is not None and extra_values.shape[1] > 0:
        extra_train, extra_test = standardize_train_test(
            extra_values[train_index], extra_values[test_index]
        )
        feature_train = np.column_stack([feature_train, extra_train])
        feature_test = np.column_stack([feature_test, extra_test])
    y_train = y[train_index]
    mean_y = float(y_train.mean())
    if feature_train.shape[1] == 0:
        return np.full(len(test_index), mean_y)
    penalty = alpha * np.eye(feature_train.shape[1])
    beta = np.linalg.solve(
        feature_train.T @ feature_train + penalty,
        feature_train.T @ (y_train - mean_y),
    )
    return mean_y + feature_test @ beta


def loeo_predictions(
    y: np.ndarray,
    *,
    map_values: np.ndarray | None = None,
    extra_values: np.ndarray | None = None,
    n_components: int = 0,
    alpha: float = PRIMARY_ALPHA,
) -> tuple[np.ndarray, np.ndarray]:
    prediction = np.full(len(y), np.nan, dtype=float)
    train_scale = np.full(len(y), np.nan, dtype=float)
    all_index = np.arange(len(y))
    for held in all_index:
        train = all_index[all_index != held]
        prediction[held] = fit_predict_ridge(
            y,
            train,
            np.asarray([held]),
            map_values=map_values,
            extra_values=extra_values,
            n_components=n_components,
            alpha=alpha,
        )[0]
        train_scale[held] = float(y[train].std(ddof=1))
    return prediction, train_scale


def bootstrap_mean_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    index = rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))
    means = values[index].mean(axis=1)
    return tuple(np.percentile(means, [2.5, 97.5]).tolist())


def exact_sign_flip_p(values: np.ndarray, alternative: str = "less") -> float:
    values = np.asarray(values, dtype=float)
    observed = float(values.mean())
    states = np.arange(2 ** len(values), dtype=np.uint32)[:, None]
    bits = (states >> np.arange(len(values), dtype=np.uint32)) & 1
    signs = np.where(bits == 1, 1.0, -1.0)
    null = (signs * values[None, :]).mean(axis=1)
    if alternative == "less":
        return float((np.sum(null <= observed) + 1) / (len(null) + 1))
    return float((np.sum(np.abs(null) >= abs(observed)) + 1) / (len(null) + 1))


def permutation_correlation_p(x: np.ndarray, y: np.ndarray, seed: int) -> float:
    observed = abs(float(np.corrcoef(x, y)[0, 1]))
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(PERMUTATION_SAMPLES):
        trial = abs(float(np.corrcoef(x, rng.permutation(y))[0, 1]))
        exceed += int(trial >= observed)
    return float((exceed + 1) / (PERMUTATION_SAMPLES + 1))


def freedman_lane_ohc_test(
    map_values: np.ndarray,
    surface_extra: np.ndarray,
    ohc: np.ndarray,
    y: np.ndarray,
    seed: int,
) -> tuple[float, float]:
    index = np.arange(len(y))
    map_score, _ = pcr_features(
        map_values, index, np.asarray([], dtype=int), PRIMARY_PCS
    )
    extra_z, _ = standardize_train_test(surface_extra, surface_extra[:0])
    ohc_z, _ = standardize_train_test(ohc[:, None], ohc[:0, None])
    reduced = np.column_stack([np.ones(len(y)), map_score, extra_z])
    full = np.column_stack([reduced, ohc_z])
    reduced_beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
    fitted = reduced @ reduced_beta
    residual = y - fitted
    observed_beta = float(np.linalg.lstsq(full, y, rcond=None)[0][-1])
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(PERMUTATION_SAMPLES):
        trial_y = fitted + rng.permutation(residual)
        trial_beta = float(np.linalg.lstsq(full, trial_y, rcond=None)[0][-1])
        exceed += int(abs(trial_beta) >= abs(observed_beta))
    return observed_beta, float((exceed + 1) / (PERMUTATION_SAMPLES + 1))


def run_models(
    table: pd.DataFrame,
    raw_maps: np.ndarray,
    anomaly_maps: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ohc = table[["ohc300_central_ma_gj_m2"]].to_numpy(dtype=float)
    sst_indices = table[
        [
            "nino34_ssta_c",
            "nino3_minus_nino4_ssta_c",
            "fep_ssta_c",
            "cp_absolute_sst_c",
            "warm_area_fraction_27p5",
            "warm_excess_centroid_lon_e",
        ]
    ].to_numpy(dtype=float)
    surface_extra = table[
        [
            "cp_absolute_sst_c",
            "warm_area_fraction_27p5",
            "warm_excess_centroid_lon_e",
        ]
    ].to_numpy(dtype=float)

    model_specs = {
        "Intercept only": (None, None, 0, PRIMARY_ALPHA),
        "OHC only": (None, ohc, 0, PRIMARY_ALPHA),
        "SST indices": (None, sst_indices, 0, PRIMARY_ALPHA),
        "Full SST pattern": (
            anomaly_maps,
            surface_extra,
            PRIMARY_PCS,
            PRIMARY_ALPHA,
        ),
        "Full SST pattern + OHC": (
            anomaly_maps,
            np.column_stack([surface_extra, ohc]),
            PRIMARY_PCS,
            PRIMARY_ALPHA,
        ),
    }
    predictions: list[dict[str, float | int | str]] = []
    skill_rows: list[dict[str, float | int | str]] = []
    increment_rows: list[dict[str, float | int | str]] = []
    sensitivity_rows: list[dict[str, float | int | str]] = []

    for response_offset, response in enumerate(RESPONSE_META):
        y = table[response].to_numpy(dtype=float)
        response_predictions: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for model, (maps, extras, components, alpha) in model_specs.items():
            predicted, scale = loeo_predictions(
                y,
                map_values=maps,
                extra_values=extras,
                n_components=components,
                alpha=alpha,
            )
            response_predictions[model] = (predicted, scale)
            error_z = (y - predicted) / scale
            rmse = float(np.sqrt(np.mean(error_z**2)))
            corr = float(np.corrcoef(y, predicted)[0, 1])
            skill_rows.append(
                {
                    "response": response,
                    "response_label": RESPONSE_META[response][0],
                    "model": model,
                    "n_events": len(table),
                    "loeo_rmse_sd": rmse,
                    "loeo_correlation": corr,
                    "loeo_mean_error_sd": float(error_z.mean()),
                    "n_pcs": components,
                    "ridge_alpha": alpha,
                }
            )
            for row, observed, expected, error, fold_scale in zip(
                table.itertuples(index=False), y, predicted, error_z, scale
            ):
                predictions.append(
                    {
                        "year": int(row.year),
                        "group": str(row.group),
                        "response": response,
                        "response_label": RESPONSE_META[response][0],
                        "model": model,
                        "observed": float(observed),
                        "predicted": float(expected),
                        "error_sd": float(error),
                        "training_response_sd": float(fold_scale),
                    }
                )

        surface_pred, surface_scale = response_predictions["Full SST pattern"]
        plus_pred, plus_scale = response_predictions["Full SST pattern + OHC"]
        surface_error = (y - surface_pred) / surface_scale
        plus_error = (y - plus_pred) / plus_scale
        delta_sq = plus_error**2 - surface_error**2
        ci_low, ci_high = bootstrap_mean_ci(
            delta_sq, RNG_SEED + 100 + response_offset
        )
        residual_ohc_r = float(np.corrcoef(surface_error, ohc[:, 0])[0, 1])
        conditional_beta, conditional_p = freedman_lane_ohc_test(
            anomaly_maps,
            surface_extra,
            ohc[:, 0],
            y,
            RNG_SEED + 200 + response_offset,
        )
        target_index = int(np.flatnonzero(table.year.to_numpy() == 2023)[0])
        target_residual = float(surface_error[target_index])
        target_plus_residual = float(plus_error[target_index])
        increment_rows.append(
            {
                "response": response,
                "response_label": RESPONSE_META[response][0],
                "surface_rmse_sd": float(np.sqrt(np.mean(surface_error**2))),
                "surface_plus_ohc_rmse_sd": float(np.sqrt(np.mean(plus_error**2))),
                "rmse_change_plus_ohc_minus_surface_sd": float(
                    np.sqrt(np.mean(plus_error**2))
                    - np.sqrt(np.mean(surface_error**2))
                ),
                "mean_squared_error_change": float(delta_sq.mean()),
                "mse_change_bootstrap_ci_low": ci_low,
                "mse_change_bootstrap_ci_high": ci_high,
                "exact_sign_flip_p_ohc_improves": exact_sign_flip_p(
                    delta_sq, alternative="less"
                ),
                "surface_residual_vs_ohc_r": residual_ohc_r,
                "surface_residual_vs_ohc_permutation_p": permutation_correlation_p(
                    surface_error,
                    ohc[:, 0],
                    RNG_SEED + 300 + response_offset,
                ),
                "conditional_ohc_beta_full_sample_ols": conditional_beta,
                "conditional_ohc_freedman_lane_p": conditional_p,
                "residual_2023_after_surface_sd": target_residual,
                "residual_2023_lower_rank": int(
                    stats.rankdata(surface_error, method="min")[target_index]
                ),
                "residual_2023_after_surface_plus_ohc_sd": target_plus_residual,
                "residual_2023_after_surface_plus_ohc_lower_rank": int(
                    stats.rankdata(plus_error, method="min")[target_index]
                ),
            }
        )

    composite = table.atmosphere_composite_z.to_numpy(dtype=float)
    for map_name, maps in (
        ("detrended_anomaly_map", anomaly_maps),
        ("raw_absolute_map", raw_maps),
    ):
        for components in (1, 2, 3):
            for alpha in (0.1, 1.0, 10.0):
                for add_ohc in (False, True):
                    extras = surface_extra
                    if add_ohc:
                        extras = np.column_stack([surface_extra, ohc])
                    predicted, scale = loeo_predictions(
                        composite,
                        map_values=maps,
                        extra_values=extras,
                        n_components=components,
                        alpha=alpha,
                    )
                    error = (composite - predicted) / scale
                    sensitivity_rows.append(
                        {
                            "map_definition": map_name,
                            "n_pcs": components,
                            "ridge_alpha": alpha,
                            "includes_ohc": add_ohc,
                            "loeo_rmse_sd": float(np.sqrt(np.mean(error**2))),
                            "loeo_correlation": float(
                                np.corrcoef(composite, predicted)[0, 1]
                            ),
                        }
                    )

    return (
        pd.DataFrame(predictions),
        pd.DataFrame(skill_rows),
        pd.DataFrame(increment_rows),
        pd.DataFrame(sensitivity_rows),
    )


def plot_main(
    table: pd.DataFrame,
    predictions: pd.DataFrame,
    skill: pd.DataFrame,
    increment: pd.DataFrame,
) -> None:
    apply_climate_style(base_font_size=10)
    plt.rcParams.update({"pdf.fonttype": 42, "axes.unicode_minus": False})
    fig = plt.figure(figsize=(15.5, 10.5))
    grid = fig.add_gridspec(
        2,
        2,
        left=0.075,
        right=0.98,
        top=0.90,
        bottom=0.10,
        hspace=0.34,
        wspace=0.28,
    )
    ax_skill = fig.add_subplot(grid[0, 0])
    ax_delta = fig.add_subplot(grid[0, 1])
    ax_scatter = fig.add_subplot(grid[1, 0])
    ax_resid = fig.add_subplot(grid[1, 1])

    responses = list(RESPONSE_META)
    plotted_models = MODEL_ORDER[1:]
    x = np.arange(len(responses))
    width = 0.18
    for offset, model in enumerate(plotted_models):
        current = skill.loc[skill.model.eq(model)].set_index("response").loc[responses]
        ax_skill.bar(
            x + (offset - 1.5) * width,
            current.loeo_rmse_sd,
            width=width,
            color=MODEL_COLORS[model],
            label=model,
        )
    ax_skill.axhline(
        float(
            skill.loc[
                skill.model.eq("Intercept only")
                & skill.response.eq("atmosphere_composite_z"),
                "loeo_rmse_sd",
            ].iloc[0]
        ),
        color="#777777",
        linestyle="--",
        linewidth=1.0,
        label="Intercept reference (composite)",
    )
    ax_skill.set_xticks(x, [RESPONSE_META[name][0] for name in responses], rotation=23, ha="right")
    ax_skill.set_ylabel("Leave-one-event-out RMSE (SD)")
    ax_skill.set_title("Out-of-event atmospheric-response skill")
    ax_skill.legend(frameon=False, ncol=2, fontsize=8)
    ax_skill.grid(axis="y", color="#DDDDDD", linewidth=0.6)

    inc = increment.set_index("response").loc[responses]
    y = np.arange(len(responses))
    values = inc.mean_squared_error_change.to_numpy(dtype=float)
    lower = values - inc.mse_change_bootstrap_ci_low.to_numpy(dtype=float)
    upper = inc.mse_change_bootstrap_ci_high.to_numpy(dtype=float) - values
    colors = np.where(values < 0, "#2A9D8F", "#C44E52")
    ax_delta.errorbar(
        values,
        y,
        xerr=np.vstack([lower, upper]),
        fmt="none",
        ecolor="#555555",
        capsize=3,
        linewidth=1.2,
    )
    ax_delta.scatter(values, y, c=colors, s=58, zorder=3)
    ax_delta.axvline(0.0, color="black", linewidth=0.8)
    ax_delta.set_yticks(y, [RESPONSE_META[name][0] for name in responses])
    ax_delta.invert_yaxis()
    ax_delta.set_xlabel("Change in squared LOEO error after adding OHC\n(negative = improvement)")
    ax_delta.set_title("Does OHC add information after the full SST pattern?")
    ax_delta.grid(axis="x", color="#DDDDDD", linewidth=0.6)

    primary = predictions.loc[
        predictions.response.eq("atmosphere_composite_z")
        & predictions.model.eq("Full SST pattern")
    ].set_index("year").loc[EVENT_YEARS]
    observed = primary.observed.to_numpy(dtype=float)
    expected = primary.predicted.to_numpy(dtype=float)
    limits = (
        float(min(observed.min(), expected.min()) - 0.25),
        float(max(observed.max(), expected.max()) + 0.25),
    )
    ax_scatter.plot(limits, limits, color="#777777", linestyle="--", linewidth=1.0)
    for year, obs, pred in zip(EVENT_YEARS, observed, expected):
        group = str(table.loc[table.year.eq(year), "group"].iloc[0])
        ax_scatter.scatter(
            pred,
            obs,
            s=78 if year in (1997, 2015, 2023) else 48,
            color=GROUP_COLORS[group],
            edgecolor="white",
            linewidth=0.7,
            zorder=3,
        )
        ax_scatter.annotate(
            str(year),
            (pred, obs),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
            fontweight="bold" if year in (1997, 2015, 2023) else "normal",
        )
    ax_scatter.set_xlim(limits)
    ax_scatter.set_ylim(limits)
    ax_scatter.set_xlabel("Expected response from full May-Jun SST pattern (SD)")
    ax_scatter.set_ylabel("Observed May-Jun atmospheric response (SD)")
    ax_scatter.set_title("Surface-expected versus observed coupled response")
    ax_scatter.grid(color="#E1E1E1", linewidth=0.6)

    residual = primary.error_sd.to_numpy(dtype=float)
    order = np.argsort(residual)
    ordered_years = EVENT_YEARS[order]
    ordered_values = residual[order]
    ordered_colors = [
        GROUP_COLORS[str(table.loc[table.year.eq(year), "group"].iloc[0])]
        for year in ordered_years
    ]
    ax_resid.bar(np.arange(len(order)), ordered_values, color=ordered_colors, width=0.72)
    ax_resid.axhline(0.0, color="black", linewidth=0.8)
    ax_resid.set_xticks(np.arange(len(order)), [str(year) for year in ordered_years], rotation=45)
    ax_resid.set_ylabel("Observed minus surface-expected response (SD)")
    ax_resid.set_title("Event atmospheric residual after controlling the SST pattern")
    ax_resid.grid(axis="y", color="#E1E1E1", linewidth=0.6)
    target_position = int(np.flatnonzero(ordered_years == 2023)[0])
    ax_resid.text(
        target_position,
        ordered_values[target_position] - 0.10,
        "2023",
        ha="center",
        va="top",
        color="#5E2A8A",
        fontweight="bold",
    )

    add_panel_labels([ax_skill, ax_delta, ax_scatter, ax_resid])
    fig.suptitle(
        "Does the full SST pattern mediate subsurface-OHC control of the atmosphere?",
        fontsize=17,
        fontweight="bold",
    )
    fig.text(
        0.075,
        0.035,
        "13 warm events; predictor: May-Jun OISST pattern (15°S-15°N, 120°E-80°W) plus absolute-SST convective metrics; "
        "OHC: Mar-Apr central-Pacific 0-300 m. PCR uses two training-only modes and ridge alpha=1. Atmospheric signs are positive for westerly, convection, rainfall and eastward stress.",
        fontsize=8.6,
        color="#555555",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, dpi=360, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def plot_context(anom_event: xr.DataArray) -> None:
    apply_climate_style(base_font_size=10)
    plt.rcParams.update({"pdf.fonttype": 42, "axes.unicode_minus": False})
    target = anom_event.sel(year=[1997, 2015, 2023])
    difference = target.sel(year=2023) - target.sel(year=2015)
    fields = [target.sel(year=1997), target.sel(year=2015), target.sel(year=2023), difference]
    titles = [
        "May-Jun 1997 SSTA",
        "May-Jun 2015 SSTA",
        "May-Jun 2023 SSTA",
        "2023 minus 2015 SSTA",
    ]
    limit = float(max(2.5, np.nanpercentile(np.abs(np.stack([f.values for f in fields])), 99)))
    fig, axes = plt.subplots(2, 2, figsize=(14.5, 7.8), sharex=True, sharey=True)
    mesh = None
    for ax, field, title in zip(axes.ravel(), fields, titles):
        mesh = ax.pcolormesh(
            field.lon,
            field.lat,
            field,
            cmap="RdBu_r",
            norm=TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit),
            shading="auto",
        )
        ax.add_patch(Rectangle((160, -5), 60, 10, fill=False, edgecolor="#222222", linewidth=1.2))
        ax.add_patch(Rectangle((270, -5), 10, 10, fill=False, edgecolor="#7A3DB8", linewidth=1.3))
        ax.text(161, 6.2, "CWP", fontsize=8, color="#222222")
        ax.text(270, 6.2, "FEP", fontsize=8, color="#7A3DB8")
        ax.set_title(title, fontweight="bold")
        ax.set_xlim(120, 280)
        ax.set_ylim(-15, 15)
        ax.set_xticks([120, 160, 200, 240, 280], ["120°E", "160°E", "160°W", "120°W", "80°W"])
        ax.set_yticks([-15, -5, 5, 15], ["15°S", "5°S", "5°N", "15°N"])
    for ax in axes[:, 0]:
        ax.set_ylabel("Latitude")
    for ax in axes[-1, :]:
        ax.set_xlabel("Longitude")
    add_panel_labels(list(axes.ravel()))
    colorbar_axis = fig.add_axes([0.29, 0.065, 0.42, 0.035])
    colorbar = fig.colorbar(mesh, cax=colorbar_axis, orientation="horizontal", extend="both")
    colorbar.set_label("OISST detrended anomaly (°C; 1982-2024 same-month baseline)")
    fig.suptitle("Surface-pattern context for the three highlighted warm events", fontsize=16, fontweight="bold")
    fig.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.19, hspace=0.25, wspace=0.10)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(CONTEXT_PNG, dpi=360, bbox_inches="tight")
    fig.savefig(CONTEXT_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(
    table: pd.DataFrame,
    skill: pd.DataFrame,
    increment: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    primary = increment.loc[increment.response.eq("atmosphere_composite_z")].iloc[0]
    skill_primary = skill.loc[skill.response.eq("atmosphere_composite_z")].set_index("model")
    pred = pd.read_csv(PRED_OUT)
    residuals = pred.loc[
        pred.response.eq("atmosphere_composite_z")
        & pred.model.eq("Full SST pattern")
    ].sort_values("error_sd")
    target = residuals.loc[residuals.year.eq(2023)].iloc[0]
    robust = sensitivity.loc[
        sensitivity.map_definition.eq("detrended_anomaly_map")
        & sensitivity.includes_ohc.eq(True)
    ]
    text = f"""# 完整SST空间型态对OHC—大气关系的中介检验

## 问题与设计

本检验使用固定的13次暖事件。海下层前兆为3—4月中太平洋0—300 m OHC；表层中介为5—6月OISST完整热带太平洋型态（15°S—15°N、120°E—80°W），并显式加入中西太平洋绝对SST、27.5°C以上暖区面积和暖区经度中心；大气响应为5—6月ERA5 850 hPa西风、负OLR、降水和东向风应力的标准化综合。

所有预测均为留一事件检验。空间场只在每个训练折内计算主成分，主分析预先固定2个主成分和岭参数1，避免13事件小样本下调参追结果。

## 主结果

- 仅OHC的综合响应LOEO RMSE为 **{skill_primary.loc['OHC only', 'loeo_rmse_sd']:.3f} SD**。
- SST箱区指标模型为 **{skill_primary.loc['SST indices', 'loeo_rmse_sd']:.3f} SD**。
- 完整SST型态模型为 **{skill_primary.loc['Full SST pattern', 'loeo_rmse_sd']:.3f} SD**。
- 完整SST型态加入OHC后为 **{skill_primary.loc['Full SST pattern + OHC', 'loeo_rmse_sd']:.3f} SD**，RMSE变化为 **{primary.rmse_change_plus_ohc_minus_surface_sd:+.3f} SD**。
- 加入OHC后的逐事件平方误差平均变化为 **{primary.mean_squared_error_change:+.3f}**，事件bootstrap 95%区间 **[{primary.mse_change_bootstrap_ci_low:+.3f}, {primary.mse_change_bootstrap_ci_high:+.3f}]**，改善方向的精确符号翻转p={primary.exact_sign_flip_p_ohc_improves:.3f}。
- 控制完整表层型态后的OHC条件系数为 **{primary.conditional_ohc_beta_full_sample_ols:+.3f}**，Freedman—Lane p={primary.conditional_ohc_freedman_lane_p:.3f}。
- 2023的表层条件大气残差为 **{target.error_sd:+.2f} SD**，从弱到强排名 **{int(primary.residual_2023_lower_rank)}/13**。

## 当前判断

结果不支持“完整海表状态已经把OHC信息全部中介掉”。加入OHC后综合响应的留一误差明显下降，但逐事件误差差的95%区间略跨零、符号翻转p=0.088，因此跨事件增量属于**有方向一致性的支持证据，而不是5%水平的决定性证据**；全样本条件系数显著只作为辅助证据，不能替代留一事件结果。

2023尤其关键：完整SST型态单独会预期较强的大气响应，但实测综合响应明显更弱；加入较低的春季中太平洋OHC后，2023残差仍为 **{primary.residual_2023_after_surface_plus_ohc_sd:+.2f} SD**，从弱到强仍排 **{int(primary.residual_2023_after_surface_plus_ohc_lower_rank)}/13**。因此2023的弱响应不能由海表型态或春季OHC中的任一项单独解释。

目前更准确的机制表述是：**海表空间型态提供大气热力强迫，次表层OHC仍提供额外的海洋预置和动力背景；二者共同约束大气响应，但2023在同时控制两者后仍存在异常弱的耦合效率。** OHC的统计增量不代表大气直接感受海下层，它也可能编码温跃层、未来海表持续性以及此前风场的共同状态。

## 稳健性与边界

- 1—3个主成分、岭参数0.1—10以及原始绝对SST场均已作为敏感性；加入OHC的综合响应RMSE范围为 **{robust.loeo_rmse_sd.min():.3f}—{robust.loeo_rmse_sd.max():.3f} SD**。
- OISST型态距平使用1982—2024同月线性去趋势；绝对SST对流量保留真实背景态。
- ERA5降水单位从m day⁻¹转换为mm day⁻¹，所有箱平均采用cos纬度权重。
- 只有13次事件，因此留一事件技能、整事件bootstrap和置换检验优先于样本内R²。
- 这是观测中介检验，仍不能替代“固定海表、交换次表层初值”的OGCM试验和“固定次表层、交换SST型态”的AGCM试验。

## 文件

- 主图：`{FIGURE_PNG}`
- SST型态图：`{CONTEXT_PNG}`
- 事件表：`{EVENT_OUT}`
- 留一预测：`{PRED_OUT}`
- 模型技能：`{SKILL_OUT}`
- OHC增量检验：`{INCREMENT_OUT}`
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    raw, anomaly = open_oisst_may_june()
    raw_maps, anomaly_maps, _, anomaly_event = flattened_event_maps(raw, anomaly)
    table = build_event_table(raw, anomaly)
    predictions, skill, increment, sensitivity = run_models(
        table, raw_maps, anomaly_maps
    )

    table.to_csv(EVENT_OUT, index=False, float_format="%.8f")
    predictions.to_csv(PRED_OUT, index=False, float_format="%.8f")
    skill.to_csv(SKILL_OUT, index=False, float_format="%.8f")
    increment.to_csv(INCREMENT_OUT, index=False, float_format="%.8f")
    sensitivity.to_csv(SENSITIVITY_OUT, index=False, float_format="%.8f")

    plot_main(table, predictions, skill, increment)
    plot_context(anomaly_event)
    write_report(table, skill, increment, sensitivity)

    diagnostics = {
        "event_years": EVENT_YEARS.tolist(),
        "n_events": int(len(table)),
        "months": list(MONTHS),
        "sst_baseline": list(SST_BASELINE),
        "atmosphere_baseline": list(FIELD_BASELINE),
        "map_domain": {
            "lat": [MAP_DOMAIN[0], MAP_DOMAIN[1]],
            "lon": [MAP_DOMAIN[2], MAP_DOMAIN[3]],
        },
        "valid_map_cells": int(anomaly_maps.shape[1]),
        "primary_pcs": PRIMARY_PCS,
        "primary_ridge_alpha": PRIMARY_ALPHA,
        "warm_threshold_c": WARM_THRESHOLD_C,
        "all_event_values_finite": bool(table.select_dtypes(include=[np.number]).notna().all().all()),
        "output_files": [
            str(EVENT_OUT),
            str(PRED_OUT),
            str(SKILL_OUT),
            str(INCREMENT_OUT),
            str(SENSITIVITY_OUT),
            str(FIGURE_PNG),
            str(FIGURE_PDF),
            str(CONTEXT_PNG),
            str(CONTEXT_PDF),
            str(REPORT_MD),
        ],
    }
    DIAGNOSTICS_OUT.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Surface-SST/OHC atmosphere mediation analysis complete")
    print(skill.loc[skill.response.eq("atmosphere_composite_z")].to_string(index=False))
    print(increment.to_string(index=False))
    print(FIGURE_PNG)
    print(CONTEXT_PNG)


if __name__ == "__main__":
    main()
