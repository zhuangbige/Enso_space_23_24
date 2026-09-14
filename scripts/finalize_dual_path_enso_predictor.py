#!/usr/bin/env python3
"""Evaluate a minimal dual-path predictor for mature El Nino flavor.

The analysis separates two physically motivated April pathways:

1. A deep-ocean transport-storage route represented by the March-April
   mean of SODA3 heat transport and D20 at 140W.
2. A surface-led far-eastern-Pacific (FEP) route represented by the FEP SST
   residual after removing the contemporaneous Nino3.4-related component.

All detrending, FEP regression, standardization and ridge fitting are repeated
inside each validation fold.  The fixed "dual route" is the maximum of the
two standardized route amplitudes.  It is deliberately simple and is tested
both in 13 independent warm episodes and in a chronological all-year
experiment from 2000 to 2023.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_dual_path_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((ROOT / "scripts").resolve()))

from analyze_soda3_transition_processes import (  # noqa: E402
    benjamini_hochberg,
    bootstrap_skill,
    paired_improvement_p,
)


BASE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
)
EVENT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_event_summary_1982_2023.csv"
)
BUDGET_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_mixed_layer_budget_indices_1980_2024.csv"
)
GATE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
)
D20_NC = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_d20_equatorial_jan_jun_1980_2024.nc"
)
ERSST_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "grl_fig4_same_source_monthly_sst_residual_ersstv5.csv"
)
OISST_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
ERA5_PRECIP = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_precip_tropics_1deg_1980_2026_jan_may.nc"
)
ERA5_SINGLE = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_single_levels_tropics_1982_2024.nc"
)
ERA5_COUPLING = (
    ROOT / "data/raw/era5/coupling_monthly_1deg"
)
ORAS_SKILL_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "oras5_d20_checkpoint_loeo_skill.csv"
)

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/final_dual_path_predictor"
OUT_PDF = ROOT / "output/pdf"

ANALYSIS_CSV = OUT_DATA / "enso_dual_path_april_inputs_1982_2023.csv"
EVENT_PRED_CSV = OUT_DATA / "enso_dual_path_event_loeo_predictions.csv"
EVENT_SKILL_CSV = OUT_DATA / "enso_dual_path_event_loeo_skill.csv"
ALL_YEAR_PRED_CSV = OUT_DATA / "enso_dual_path_all_year_walkforward_predictions.csv"
ALL_YEAR_SKILL_CSV = OUT_DATA / "enso_dual_path_all_year_walkforward_skill.csv"
EVENT_WALK_PRED_CSV = (
    OUT_DATA / "enso_dual_path_event_chronological_predictions.csv"
)
EVENT_WALK_SKILL_CSV = (
    OUT_DATA / "enso_dual_path_event_chronological_skill.csv"
)
BLOCK_SKILL_CSV = OUT_DATA / "enso_dual_path_time_block_skill.csv"
NESTED_CSV = OUT_DATA / "enso_dual_path_nested_event_predictions.csv"
MECHANISM_CSV = OUT_DATA / "enso_dual_path_mechanism_correlations.csv"
DIAGNOSTICS_JSON = OUT_DATA / "enso_dual_path_diagnostics.json"
FIGURE_PNG = OUT_DIR / "enso_dual_path_final_assessment.png"
FIGURE_PDF = OUT_PDF / "enso_dual_path_final_assessment.pdf"
REPORT_MD = OUT_DIR / "ENSO_DUAL_PATH_FINAL_ASSESSMENT_CN.md"

EVENT_YEARS = (
    1982,
    1986,
    1991,
    1994,
    1997,
    2002,
    2004,
    2006,
    2009,
    2015,
    2018,
    2019,
    2023,
)
EXTREME_YEARS = (1982, 1997, 2015)
RIDGE_ALPHA = 1.0
PERMUTATION_SAMPLES = 40_000

MODEL_FEATURES: dict[str, tuple[str, ...]] = {
    "SST persistence": ("sst_type",),
    "+ Q20 at 140W": ("sst_type", "q140"),
    "+ D20 at 140W": ("sst_type", "d20_140"),
    "+ deep TSI": ("sst_type", "deep_route"),
    "+ western WWV": ("sst_type", "wwv_west"),
    "+ FEP route (OISST)": ("sst_type", "surface_oisst"),
    "+ FEP route (ERSST)": ("sst_type", "surface_ersst"),
    "+ dual-route maximum": ("sst_type", "dual_route"),
    "+ dual-route maximum (ERSST)": ("sst_type", "dual_route_ersst"),
    "+ two routes separately": (
        "sst_type",
        "deep_route",
        "surface_oisst",
    ),
    "+ Bjerknes chain": ("sst_type", "bjerknes_chain"),
    "+ dual route + chain": (
        "sst_type",
        "dual_route",
        "bjerknes_chain",
    ),
}

NESTED_CANDIDATES = (
    "SST persistence",
    "+ Q20 at 140W",
    "+ D20 at 140W",
    "+ deep TSI",
    "+ western WWV",
    "+ FEP route (OISST)",
    "+ dual-route maximum",
    "+ two routes separately",
    "+ Bjerknes chain",
)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.6,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "legend.fontsize": 7.4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def weighted_box(
    field: xr.DataArray,
    lon0: float,
    lon1: float,
    lat0: float = -5.0,
    lat1: float = 5.0,
) -> xr.DataArray:
    rename = {}
    if "valid_time" in field.coords:
        rename["valid_time"] = "time"
    if "latitude" in field.coords:
        rename["latitude"] = "lat"
    if "longitude" in field.coords:
        rename["longitude"] = "lon"
    field = field.rename(rename)
    field = field.assign_coords(lon=field.lon % 360).sortby("lon").sortby("lat")
    subset = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if subset.sizes["lat"] == 0 or subset.sizes["lon"] == 0:
        raise ValueError(
            f"Empty box lat={lat0}:{lat1}, lon={lon0}:{lon1}"
        )
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def to_year_month(
    data: xr.DataArray,
    name: str,
) -> pd.DataFrame:
    time_name = "time" if "time" in data.coords else "valid_time"
    times = pd.DatetimeIndex(pd.to_datetime(data[time_name].values))
    return pd.DataFrame(
        {
            "year": times.year,
            "month": times.month,
            name: np.asarray(data.values, dtype=float),
        }
    )


def mar_apr_mean(
    frame: pd.DataFrame,
    value_columns: list[str],
) -> pd.DataFrame:
    current = frame.loc[
        frame["month"].isin((3, 4))
        & frame["year"].between(1982, 2023)
    ]
    counts = current.groupby("year")["month"].nunique()
    if not counts.eq(2).all():
        raise ValueError("Incomplete March-April input")
    return (
        current.groupby("year", as_index=False)[value_columns]
        .mean()
        .rename(columns={name: f"{name}_ma" for name in value_columns})
    )


def load_oisst_gradients() -> pd.DataFrame:
    frames = []
    for month, tag in ((3, "mar"), (4, "apr")):
        path = OISST_DIR / f"oisst_sst_tropics_1deg_{tag}_1982_2026.nc"
        with xr.open_dataset(path, engine="scipy") as dataset:
            sst = dataset["sst"].load()
        west = weighted_box(sst, 130.0, 160.0)
        east = weighted_box(sst, 220.0, 250.0)
        current = to_year_month(west, "sst_west_c")
        current["sst_east_c"] = np.asarray(east.values, dtype=float)
        current["month"] = month
        frames.append(current)
    return mar_apr_mean(
        pd.concat(frames, ignore_index=True),
        ["sst_west_c", "sst_east_c"],
    ).assign(
        sst_gradient_e_minus_w_c=lambda x:
        x["sst_east_c_ma"] - x["sst_west_c_ma"]
    )


def load_precip_gradient() -> pd.DataFrame:
    with xr.open_dataset(ERA5_PRECIP, engine="h5netcdf") as dataset:
        precip = dataset["tp"]
        times = pd.DatetimeIndex(pd.to_datetime(precip.valid_time.values))
        precip = precip.isel(
            valid_time=np.flatnonzero(
                times.month.isin((3, 4))
                & (times.year >= 1982)
                & (times.year <= 2023)
            )
        ).load()
    west = weighted_box(precip, 130.0, 160.0) * 1000.0
    east = weighted_box(precip, 220.0, 250.0) * 1000.0
    frame = to_year_month(west, "precip_west_mmday")
    frame["precip_east_mmday"] = np.asarray(east.values, dtype=float)
    return mar_apr_mean(
        frame,
        ["precip_west_mmday", "precip_east_mmday"],
    ).assign(
        precip_gradient_e_minus_w_mmday=lambda x:
        x["precip_east_mmday_ma"] - x["precip_west_mmday_ma"]
    )


def load_slp_gradient() -> pd.DataFrame:
    with xr.open_dataset(ERA5_SINGLE, engine="h5netcdf") as dataset:
        msl = dataset["msl"]
        times = pd.DatetimeIndex(pd.to_datetime(msl.valid_time.values))
        selected = np.flatnonzero(
            times.month.isin((3, 4))
            & (times.year >= 1982)
            & (times.year <= 2023)
        )
        msl = msl.isel(valid_time=selected).load() / 100.0
    west = weighted_box(msl, 130.0, 160.0)
    east = weighted_box(msl, 220.0, 250.0)
    frame = to_year_month(west, "slp_west_hpa")
    frame["slp_east_hpa"] = np.asarray(east.values, dtype=float)
    return mar_apr_mean(
        frame,
        ["slp_west_hpa", "slp_east_hpa"],
    ).assign(
        slp_drive_w_minus_e_hpa=lambda x:
        x["slp_west_hpa_ma"] - x["slp_east_hpa_ma"]
    )


def load_tau_index() -> pd.DataFrame:
    frames = []
    for month in (3, 4):
        parts = []
        for part in ("part01", "part02"):
            path = (
                ERA5_COUPLING
                / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            )
            with xr.open_dataset(path, engine="h5netcdf") as dataset:
                parts.append(dataset["avg_iews"].load())
        normalized = []
        for part in parts:
            rename = {
                "valid_time": "time",
                "latitude": "lat",
                "longitude": "lon",
            }
            part = part.rename(rename)
            part = part.assign_coords(lon=part.lon % 360).sortby("lon")
            normalized.append(part)
        field = xr.concat(normalized, dim="lon").sortby("lon")
        _, unique = np.unique(field.lon.values, return_index=True)
        field = field.isel(lon=np.sort(unique))
        index = weighted_box(field, 160.0, 220.0)
        current = to_year_month(index, "tau_cwp_nm2")
        current["month"] = month
        frames.append(current)
    return mar_apr_mean(
        pd.concat(frames, ignore_index=True),
        ["tau_cwp_nm2"],
    )


def load_wwv_west() -> pd.DataFrame:
    with xr.open_dataset(D20_NC, engine="h5netcdf") as dataset:
        d20 = dataset["d20"].sel(
            time=dataset.time.dt.month.isin((3, 4)),
            lat=slice(-5.0, 5.0),
            lon=slice(120.0, 190.0),
        ).load()
    lat = d20.lat.values.astype(float)
    lon = d20.lon.values.astype(float)
    dlat = float(np.median(np.diff(lat)))
    dlon = float(np.median(np.diff(lon)))
    radius = 6_371_000.0
    area = (
        radius**2
        * np.deg2rad(abs(dlat))
        * np.deg2rad(abs(dlon))
        * np.cos(np.deg2rad(lat))[:, None]
        * np.ones((1, len(lon)))
    )
    volume = np.nansum(
        d20.values.astype(float) * area[None, :, :],
        axis=(1, 2),
    ) / 1.0e14
    times = pd.DatetimeIndex(pd.to_datetime(d20.time.values))
    frame = pd.DataFrame(
        {
            "year": times.year,
            "month": times.month,
            "wwv_west_1e14m3": volume,
        }
    )
    return mar_apr_mean(frame, ["wwv_west_1e14m3"])


def build_analysis_table() -> pd.DataFrame:
    base = pd.read_csv(BASE_CSV)
    april = base.loc[
        base["month"].eq(4),
        [
            "year",
            "init_type_raw_c",
            "mature_djf_type_raw_c",
            "mature_djf_type_index_c",
            "mature_djf_nino34_c",
        ],
    ].copy()
    two_month_sst = mar_apr_mean(
        base[
            [
                "year",
                "month",
                "nino34_raw_c",
                "fep_raw_c",
            ]
        ],
        ["nino34_raw_c", "fep_raw_c"],
    )

    budget = pd.read_csv(BUDGET_CSV)
    q20 = mar_apr_mean(
        budget[["year", "month", "q20_220e_pw"]],
        ["q20_220e_pw"],
    )

    gate = pd.read_csv(GATE_CSV)
    d20 = mar_apr_mean(
        gate.loc[
            np.isclose(gate["longitude_e"], 220.0),
            ["year", "month", "d20_m"],
        ],
        ["d20_m"],
    )

    ersst = pd.read_csv(ERSST_CSV)
    ersst = mar_apr_mean(
        ersst[
            [
                "year",
                "month",
                "nino34_sst",
                "fep_sst",
            ]
        ].rename(
            columns={
                "nino34_sst": "ersst_nino34_raw_c",
                "fep_sst": "ersst_fep_raw_c",
            }
        ),
        ["ersst_nino34_raw_c", "ersst_fep_raw_c"],
    )

    table = april
    for frame in (
        two_month_sst,
        q20,
        d20,
        ersst,
        load_oisst_gradients(),
        load_precip_gradient(),
        load_slp_gradient(),
        load_tau_index(),
        load_wwv_west(),
    ):
        table = table.merge(frame, on="year", how="left", validate="one_to_one")

    expected_years = set(range(1982, 2024))
    if set(table["year"].astype(int)) != expected_years:
        raise ValueError("Analysis table does not contain 1982-2023")
    if table.duplicated("year").any():
        raise ValueError("Duplicate analysis years")
    if table.isna().any().any():
        missing = table.isna().sum()
        raise ValueError(f"Missing values:\n{missing[missing.gt(0)]}")
    return table.sort_values("year").reset_index(drop=True)


def fit_trend(
    years: np.ndarray,
    values: np.ndarray,
) -> tuple[float, float]:
    design = np.column_stack([np.ones(len(years)), years])
    intercept, slope = np.linalg.lstsq(design, values, rcond=None)[0]
    return float(intercept), float(slope)


def detrend_fold(
    years: np.ndarray,
    values: np.ndarray,
    test_year: float,
    test_value: float,
) -> tuple[np.ndarray, float]:
    intercept, slope = fit_trend(years, values)
    train = values - (intercept + slope * years)
    test = test_value - (intercept + slope * test_year)
    return train, float(test)


def standardized_fold(
    train: pd.DataFrame,
    test: pd.Series,
    column: str,
) -> tuple[np.ndarray, float]:
    years = train["year"].to_numpy(dtype=float)
    residual, test_residual = detrend_fold(
        years,
        train[column].to_numpy(dtype=float),
        float(test["year"]),
        float(test[column]),
    )
    scale = float(np.std(residual, ddof=1))
    if not np.isfinite(scale) or scale == 0.0:
        raise ValueError(f"Invalid scale for {column}")
    return residual / scale, float(test_residual / scale)


def fep_residual_fold(
    train: pd.DataFrame,
    test: pd.Series,
    nino_column: str,
    fep_column: str,
) -> tuple[np.ndarray, float]:
    nino_train, nino_test = standardized_fold(
        train,
        test,
        nino_column,
    )
    fep_train, fep_test = standardized_fold(
        train,
        test,
        fep_column,
    )
    design = np.column_stack([np.ones(len(train)), nino_train])
    intercept, slope = np.linalg.lstsq(design, fep_train, rcond=None)[0]
    residual = fep_train - (intercept + slope * nino_train)
    test_residual = float(fep_test - (intercept + slope * nino_test))
    scale = float(np.std(residual, ddof=1))
    if not np.isfinite(scale) or scale == 0.0:
        raise ValueError("Invalid FEP residual scale")
    return residual / scale, test_residual / scale


def fold_feature_values(
    train: pd.DataFrame,
    test: pd.Series,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    train_values: dict[str, np.ndarray] = {}
    test_values: dict[str, float] = {}

    primitives = {
        "sst_type": "init_type_raw_c",
        "q140": "q20_220e_pw_ma",
        "d20_140": "d20_m_ma",
        "sst_gradient": "sst_gradient_e_minus_w_c",
        "precip_gradient": "precip_gradient_e_minus_w_mmday",
        "slp_drive": "slp_drive_w_minus_e_hpa",
        "tau": "tau_cwp_nm2_ma",
        "wwv_west": "wwv_west_1e14m3_ma",
    }
    for name, column in primitives.items():
        train_values[name], test_values[name] = standardized_fold(
            train,
            test,
            column,
        )

    (
        train_values["surface_oisst"],
        test_values["surface_oisst"],
    ) = fep_residual_fold(
        train,
        test,
        "nino34_raw_c_ma",
        "fep_raw_c_ma",
    )
    (
        train_values["surface_ersst"],
        test_values["surface_ersst"],
    ) = fep_residual_fold(
        train,
        test,
        "ersst_nino34_raw_c_ma",
        "ersst_fep_raw_c_ma",
    )

    train_values["deep_route"] = 0.5 * (
        train_values["q140"] + train_values["d20_140"]
    )
    test_values["deep_route"] = 0.5 * (
        test_values["q140"] + test_values["d20_140"]
    )
    train_values["dual_route"] = np.maximum(
        train_values["deep_route"],
        train_values["surface_oisst"],
    )
    test_values["dual_route"] = max(
        test_values["deep_route"],
        test_values["surface_oisst"],
    )
    train_values["dual_route_ersst"] = np.maximum(
        train_values["deep_route"],
        train_values["surface_ersst"],
    )
    test_values["dual_route_ersst"] = max(
        test_values["deep_route"],
        test_values["surface_ersst"],
    )
    train_values["bjerknes_chain"] = np.mean(
        np.column_stack(
            [
                train_values["sst_gradient"],
                train_values["precip_gradient"],
                train_values["slp_drive"],
                train_values["tau"],
            ]
        ),
        axis=1,
    )
    test_values["bjerknes_chain"] = float(
        np.mean(
            [
                test_values["sst_gradient"],
                test_values["precip_gradient"],
                test_values["slp_drive"],
                test_values["tau"],
            ]
        )
    )
    train_values["coupling_deficit"] = (
        train_values["sst_gradient"] - train_values["tau"]
    )
    test_values["coupling_deficit"] = (
        test_values["sst_gradient"] - test_values["tau"]
    )
    return train_values, test_values


def predict_fold(
    train: pd.DataFrame,
    test: pd.Series,
    model: str,
    alpha: float = RIDGE_ALPHA,
) -> tuple[float, float]:
    if len(train) < 6:
        return np.nan, np.nan
    years = train["year"].to_numpy(dtype=float)
    target, observed = detrend_fold(
        years,
        train["mature_djf_type_raw_c"].to_numpy(dtype=float),
        float(test["year"]),
        float(test["mature_djf_type_raw_c"]),
    )
    train_features, test_features = fold_feature_values(train, test)
    names = MODEL_FEATURES[model]
    x_train = np.column_stack([train_features[name] for name in names])
    x_test = np.asarray([test_features[name] for name in names])
    coefficients = np.linalg.solve(
        x_train.T @ x_train + alpha * np.eye(len(names)),
        x_train.T @ target,
    )
    return float(x_test @ coefficients), observed


def event_loeo(table: pd.DataFrame) -> pd.DataFrame:
    event = table.loc[table["year"].isin(EVENT_YEARS)].copy()
    rows = []
    for year in EVENT_YEARS:
        train = event.loc[event["year"].ne(year)]
        test = event.loc[event["year"].eq(year)].iloc[0]
        for model in MODEL_FEATURES:
            predicted, observed = predict_fold(train, test, model)
            rows.append(
                {
                    "year": year,
                    "model": model,
                    "prediction_type_residual_c": predicted,
                    "observed_type_residual_c": observed,
                    "n_training_events": len(train),
                    "ridge_alpha": RIDGE_ALPHA,
                }
            )
    return pd.DataFrame(rows)


def all_year_walkforward(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in range(2000, 2024):
        train = table.loc[table["year"].lt(year)]
        test = table.loc[table["year"].eq(year)].iloc[0]
        for model in MODEL_FEATURES:
            predicted, observed = predict_fold(train, test, model)
            rows.append(
                {
                    "year": year,
                    "model": model,
                    "prediction_type_residual_c": predicted,
                    "observed_type_residual_c": observed,
                    "n_training_years": len(train),
                    "ridge_alpha": RIDGE_ALPHA,
                    "warm_event": year in EVENT_YEARS,
                }
            )
    return pd.DataFrame(rows)


def event_chronological(table: pd.DataFrame) -> pd.DataFrame:
    """Expanding-window type forecasts conditional on a warm event.

    The first six events (1982-2002) initialize the model.  Every subsequent
    event is predicted using only earlier warm events.  This is a stricter
    chronology check than LOEO, although it remains conditional on an
    independent first-stage forecast that the year will become an El Nino.
    """
    event = table.loc[table["year"].isin(EVENT_YEARS)].copy()
    rows = []
    for year in EVENT_YEARS:
        train = event.loc[event["year"].lt(year)]
        if len(train) < 6:
            continue
        test = event.loc[event["year"].eq(year)].iloc[0]
        for model in MODEL_FEATURES:
            predicted, observed = predict_fold(train, test, model)
            rows.append(
                {
                    "year": year,
                    "model": model,
                    "prediction_type_residual_c": predicted,
                    "observed_type_residual_c": observed,
                    "n_training_events": len(train),
                    "ridge_alpha": RIDGE_ALPHA,
                }
            )
    return pd.DataFrame(rows)


def skill_table(
    predictions: pd.DataFrame,
    *,
    family_label: str,
) -> pd.DataFrame:
    baseline = predictions.loc[
        predictions["model"].eq("SST persistence"),
        ["year", "prediction_type_residual_c"],
    ].rename(
        columns={"prediction_type_residual_c": "baseline_prediction_c"}
    )
    rows = []
    seed = 75_000
    for model in MODEL_FEATURES:
        current = predictions.loc[
            predictions["model"].eq(model),
            [
                "year",
                "prediction_type_residual_c",
                "observed_type_residual_c",
            ],
        ].merge(baseline, on="year", validate="one_to_one")
        observed = current["observed_type_residual_c"].to_numpy(dtype=float)
        predicted = current["prediction_type_residual_c"].to_numpy(dtype=float)
        reference = current["baseline_prediction_c"].to_numpy(dtype=float)
        rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
        reference_rmse = float(
            np.sqrt(np.mean((reference - observed) ** 2))
        )
        skill = 1.0 - rmse / reference_rmse
        if model == "SST persistence":
            p_value = ci_low = ci_high = np.nan
        else:
            p_value = paired_improvement_p(
                observed,
                predicted,
                reference,
                seed,
            )
            ci_low, ci_high = bootstrap_skill(
                observed,
                predicted,
                reference,
                seed + 5000,
            )
        rows.append(
            {
                "validation_family": family_label,
                "model": model,
                "n_test": len(current),
                "rmse_c": rmse,
                "baseline_rmse_c": reference_rmse,
                "rmse_skill_vs_sst_persistence": skill,
                "prediction_observation_r": float(
                    np.corrcoef(predicted, observed)[0, 1]
                ),
                "sign_accuracy": float(
                    np.mean(np.sign(predicted) == np.sign(observed))
                ),
                "one_sided_paired_improvement_p": p_value,
                "bootstrap_skill_ci_low": ci_low,
                "bootstrap_skill_ci_high": ci_high,
            }
        )
        seed += 1
    output = pd.DataFrame(rows)
    added = output["model"].ne("SST persistence")
    output.loc[
        added,
        "bh_fdr_q_across_preregistered_models",
    ] = benjamini_hochberg(
        output.loc[added, "one_sided_paired_improvement_p"]
    )
    return output


def warm_event_walkforward_skill(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    return skill_table(
        predictions.loc[predictions["warm_event"]].copy(),
        family_label="all-year-trained warm-event tests 2000-2023",
    )


def time_block_skill(predictions: pd.DataFrame) -> pd.DataFrame:
    blocks = (
        (2000, 2004),
        (2005, 2009),
        (2010, 2014),
        (2015, 2019),
        (2020, 2023),
    )
    rows = []
    for start, end in blocks:
        current = predictions.loc[predictions["year"].between(start, end)]
        skill = skill_table(
            current,
            family_label=f"{start}-{end}",
        )
        rows.append(skill)
    return pd.concat(rows, ignore_index=True)


def nested_event_selection(table: pd.DataFrame) -> pd.DataFrame:
    event = table.loc[table["year"].isin(EVENT_YEARS)].copy()
    rows = []
    for outer_year in EVENT_YEARS:
        outer_train = event.loc[event["year"].ne(outer_year)].copy()
        outer_test = event.loc[event["year"].eq(outer_year)].iloc[0]
        candidate_rmse: dict[str, float] = {}
        for model in NESTED_CANDIDATES:
            inner_errors = []
            for inner_year in outer_train["year"].astype(int):
                inner_train = outer_train.loc[
                    outer_train["year"].ne(inner_year)
                ]
                inner_test = outer_train.loc[
                    outer_train["year"].eq(inner_year)
                ].iloc[0]
                prediction, observed = predict_fold(
                    inner_train,
                    inner_test,
                    model,
                )
                inner_errors.append((prediction - observed) ** 2)
            candidate_rmse[model] = float(np.sqrt(np.mean(inner_errors)))
        selected = min(
            NESTED_CANDIDATES,
            key=lambda name: (
                candidate_rmse[name],
                NESTED_CANDIDATES.index(name),
            ),
        )
        prediction, observed = predict_fold(
            outer_train,
            outer_test,
            selected,
        )
        baseline, _ = predict_fold(
            outer_train,
            outer_test,
            "SST persistence",
        )
        rows.append(
            {
                "year": outer_year,
                "selected_model": selected,
                "prediction_type_residual_c": prediction,
                "observed_type_residual_c": observed,
                "baseline_prediction_c": baseline,
                "inner_selected_rmse_c": candidate_rmse[selected],
                "n_outer_training_events": len(outer_train),
            }
        )
    return pd.DataFrame(rows)


def nested_summary(nested: pd.DataFrame) -> dict[str, object]:
    observed = nested["observed_type_residual_c"].to_numpy(dtype=float)
    predicted = nested["prediction_type_residual_c"].to_numpy(dtype=float)
    baseline = nested["baseline_prediction_c"].to_numpy(dtype=float)
    rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
    baseline_rmse = float(np.sqrt(np.mean((baseline - observed) ** 2)))
    skill = 1.0 - rmse / baseline_rmse
    ci_low, ci_high = bootstrap_skill(
        observed,
        predicted,
        baseline,
        91_000,
    )
    return {
        "rmse_c": rmse,
        "baseline_rmse_c": baseline_rmse,
        "rmse_skill": skill,
        "prediction_observation_r": float(
            np.corrcoef(predicted, observed)[0, 1]
        ),
        "paired_improvement_p": paired_improvement_p(
            observed,
            predicted,
            baseline,
            92_000,
        ),
        "bootstrap_skill_ci_low": ci_low,
        "bootstrap_skill_ci_high": ci_high,
        "selected_model_counts": dict(
            Counter(nested["selected_model"].tolist())
        ),
    }


def full_sample_routes(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    years = output["year"].to_numpy(dtype=float)

    def residual(column: str) -> np.ndarray:
        intercept, slope = fit_trend(
            years,
            output[column].to_numpy(dtype=float),
        )
        values = output[column].to_numpy(dtype=float) - (
            intercept + slope * years
        )
        return values / np.std(values, ddof=1)

    q = residual("q20_220e_pw_ma")
    d20 = residual("d20_m_ma")
    nino = residual("nino34_raw_c_ma")
    fep = residual("fep_raw_c_ma")
    design = np.column_stack([np.ones(len(output)), nino])
    coef = np.linalg.lstsq(design, fep, rcond=None)[0]
    surface = fep - design @ coef
    surface = surface / np.std(surface, ddof=1)
    output["deep_route_full_z"] = 0.5 * (q + d20)
    output["q140_full_z"] = q
    output["d20_140_full_z"] = d20
    output["surface_route_full_z"] = surface
    output["dual_route_full_z"] = np.maximum(
        output["deep_route_full_z"],
        output["surface_route_full_z"],
    )
    output["wwv_west_full_z"] = residual("wwv_west_1e14m3_ma")
    output["tau_full_z"] = residual("tau_cwp_nm2_ma")
    output["sst_gradient_full_z"] = residual(
        "sst_gradient_e_minus_w_c"
    )
    output["coupling_deficit_full_z"] = (
        output["sst_gradient_full_z"] - output["tau_full_z"]
    )
    return output


def permutation_correlation(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    observed = float(np.corrcoef(x, y)[0, 1])
    x = x - x.mean()
    y = y - y.mean()
    denominator = np.sqrt(np.sum(x**2) * np.sum(y**2))
    rng = np.random.default_rng(seed)
    order = np.argsort(
        rng.random((PERMUTATION_SAMPLES, len(y))),
        axis=1,
    )
    null = y[order] @ x / denominator
    p = float(
        (np.sum(np.abs(null) >= abs(observed)) + 1)
        / (PERMUTATION_SAMPLES + 1)
    )
    return observed, p


def mechanism_correlations(table: pd.DataFrame) -> pd.DataFrame:
    event = full_sample_routes(table)
    event = event.loc[event["year"].isin(EVENT_YEARS)]
    targets = {
        "mature_type": "mature_djf_type_index_c",
        "spring_westerly": "tau_full_z",
        "spring_coupling_deficit": "coupling_deficit_full_z",
    }
    predictors = {
        "deep_TSI": "deep_route_full_z",
        "Q20_140W": "q140_full_z",
        "D20_140W": "d20_140_full_z",
        "surface_FEP": "surface_route_full_z",
        "dual_route": "dual_route_full_z",
        "western_WWV": "wwv_west_full_z",
        "spring_SST_gradient": "sst_gradient_full_z",
    }
    rows = []
    seed = 101_000
    for target_name, target_column in targets.items():
        for predictor_name, predictor_column in predictors.items():
            r_value, p_value = permutation_correlation(
                event[predictor_column].to_numpy(dtype=float),
                event[target_column].to_numpy(dtype=float),
                seed,
            )
            rows.append(
                {
                    "target": target_name,
                    "predictor": predictor_name,
                    "pearson_r": r_value,
                    "two_sided_permutation_p": p_value,
                    "n_events": len(event),
                }
            )
            seed += 1
    output = pd.DataFrame(rows)
    output["bh_fdr_q_within_target"] = (
        output.groupby("target", group_keys=False)[
            "two_sided_permutation_p"
        ].apply(benjamini_hochberg)
    )
    return output


def nonextreme_skill(
    table: pd.DataFrame,
    model: str,
) -> dict[str, float]:
    event = table.loc[
        table["year"].isin(EVENT_YEARS)
        & ~table["year"].isin(EXTREME_YEARS)
    ]
    rows = []
    for year in event["year"].astype(int):
        train = event.loc[event["year"].ne(year)]
        test = event.loc[event["year"].eq(year)].iloc[0]
        predicted, observed = predict_fold(train, test, model)
        baseline, _ = predict_fold(
            train,
            test,
            "SST persistence",
        )
        rows.append((predicted, observed, baseline))
    values = np.asarray(rows)
    predicted, observed, baseline = values.T
    rmse = np.sqrt(np.mean((predicted - observed) ** 2))
    baseline_rmse = np.sqrt(np.mean((baseline - observed) ** 2))
    return {
        "n_events": len(event),
        "rmse_skill": float(1.0 - rmse / baseline_rmse),
        "prediction_observation_r": float(
            np.corrcoef(predicted, observed)[0, 1]
        ),
    }


def plot_results(
    table: pd.DataFrame,
    event_predictions: pd.DataFrame,
    event_skill: pd.DataFrame,
    all_year_skill: pd.DataFrame,
    nested: pd.DataFrame,
) -> None:
    setup_style()
    routes = full_sample_routes(table)
    event = routes.loc[routes["year"].isin(EVENT_YEARS)].copy()
    colors = np.where(
        event["mature_djf_type_index_c"].to_numpy() >= 0,
        "#B43C2D",
        "#2A72A5",
    )
    fig, axes = plt.subplots(2, 3, figsize=(17.8, 8.6))
    fig.subplots_adjust(
        left=0.065,
        right=0.985,
        top=0.89,
        bottom=0.13,
        hspace=0.43,
        wspace=0.31,
    )

    axis = axes[0, 0]
    scatter = axis.scatter(
        event["deep_route_full_z"],
        event["surface_route_full_z"],
        c=event["mature_djf_type_index_c"],
        cmap="RdBu_r",
        norm=mpl.colors.TwoSlopeNorm(vmin=-0.7, vcenter=0, vmax=2.2),
        s=52,
        edgecolor="white",
        linewidth=0.7,
        zorder=3,
    )
    for row in event.itertuples():
        offset = (4, 4)
        if row.year in (1986, 1991, 2002, 2006, 2009, 2018):
            offset = (4, -10)
        axis.annotate(
            str(row.year),
            (row.deep_route_full_z, row.surface_route_full_z),
            xytext=offset,
            textcoords="offset points",
            fontsize=6.8,
        )
    axis.axhline(0, color="0.7", lw=0.7)
    axis.axvline(0, color="0.7", lw=0.7)
    axis.set_xlabel("Deep route: Q20 + D20 at 140°W (z)")
    axis.set_ylabel("Surface route: residual FEP SST (z)")
    axis.set_title("(a) Two physically distinct April routes", loc="left", weight="bold")
    colorbar = fig.colorbar(scatter, ax=axis, pad=0.02)
    colorbar.set_label("Mature DJF Niño3 - Niño4 (°C)")

    event_order = event_skill.sort_values(
        "rmse_skill_vs_sst_persistence",
        ascending=True,
    )
    event_order = event_order.loc[
        event_order["model"].isin(
            [
                "+ deep TSI",
                "+ FEP route (OISST)",
                "+ dual-route maximum",
                "+ two routes separately",
                "+ Bjerknes chain",
                "+ dual route + chain",
            ]
        )
    ]
    axis = axes[0, 1]
    y = np.arange(len(event_order))
    axis.barh(
        y,
        event_order["rmse_skill_vs_sst_persistence"],
        color=[
            "#A43E32" if "dual-route maximum" in model else "#D48A7D"
            for model in event_order["model"]
        ],
    )
    axis.axvline(0, color="0.25", lw=0.8)
    axis.set_yticks(y, event_order["model"])
    axis.set_xlabel("RMSE skill vs April SST type")
    axis.set_title("(b) Warm-event LOEO: N = 13", loc="left", weight="bold")
    axis.grid(axis="x", color="0.88", lw=0.6)
    axis.set_axisbelow(True)

    all_order = all_year_skill.loc[
        all_year_skill["model"].isin(event_order["model"])
    ].set_index("model").loc[event_order["model"]].reset_index()
    axis = axes[0, 2]
    axis.barh(
        y,
        all_order["rmse_skill_vs_sst_persistence"],
        color=[
            "#356F9B" if "dual-route maximum" in model else "#78A9C9"
            for model in all_order["model"]
        ],
    )
    axis.axvline(0, color="0.25", lw=0.8)
    axis.set_yticks(y, [])
    axis.set_xlabel("RMSE skill vs April SST type")
    axis.set_title(
        "(c) All-year walk-forward: 2000-2023",
        loc="left",
        weight="bold",
    )
    axis.grid(axis="x", color="0.88", lw=0.6)
    axis.set_axisbelow(True)

    axis = axes[1, 0]
    dual_pred = event_predictions.loc[
        event_predictions["model"].eq("+ dual-route maximum")
    ]
    axis.scatter(
        dual_pred["observed_type_residual_c"],
        dual_pred["prediction_type_residual_c"],
        c=colors,
        s=48,
        edgecolor="white",
        linewidth=0.7,
        zorder=3,
    )
    for row in dual_pred.itertuples():
        offset = (4, 4)
        if row.year in (1986, 1991, 2002, 2006, 2009, 2018):
            offset = (4, -10)
        axis.annotate(
            str(row.year),
            (row.observed_type_residual_c, row.prediction_type_residual_c),
            xytext=offset,
            textcoords="offset points",
            fontsize=6.8,
        )
    low = min(
        dual_pred["observed_type_residual_c"].min(),
        dual_pred["prediction_type_residual_c"].min(),
    ) - 0.15
    high = max(
        dual_pred["observed_type_residual_c"].max(),
        dual_pred["prediction_type_residual_c"].max(),
    ) + 0.15
    axis.plot([low, high], [low, high], color="0.25", lw=0.9)
    axis.set_xlim(low, high)
    axis.set_ylim(low, high)
    axis.set_xlabel("Observed detrended mature type (°C)")
    axis.set_ylabel("LOEO prediction (°C)")
    axis.set_title("(d) Fixed dual-route prediction", loc="left", weight="bold")

    axis = axes[1, 1]
    blocks = (
        (2000, 2004),
        (2005, 2009),
        (2010, 2014),
        (2015, 2019),
        (2020, 2023),
    )
    walk = pd.read_csv(ALL_YEAR_PRED_CSV)
    for model, color, marker in (
        ("+ deep TSI", "#B43C2D", "o"),
        ("+ dual-route maximum", "#2A72A5", "s"),
    ):
        values = []
        labels = []
        for start, end in blocks:
            current = walk.loc[walk["year"].between(start, end)]
            skill = skill_table(current, family_label="temporary")
            values.append(
                float(
                    skill.loc[
                        skill["model"].eq(model),
                        "rmse_skill_vs_sst_persistence",
                    ].iloc[0]
                )
            )
            labels.append(f"{start}\n-{str(end)[-2:]}")
        axis.plot(
            np.arange(len(values)),
            values,
            marker=marker,
            color=color,
            lw=1.6,
            label=model,
        )
    axis.axhline(0, color="0.25", lw=0.8)
    axis.set_xticks(np.arange(len(labels)), labels)
    axis.set_ylabel("Within-block RMSE skill")
    axis.set_title("(e) Skill is not stationary across eras", loc="left", weight="bold")
    axis.legend(frameon=False)
    axis.grid(axis="y", color="0.88", lw=0.6)

    axis = axes[1, 2]
    selected_counts = Counter(nested["selected_model"])
    names = list(NESTED_CANDIDATES)
    values = [selected_counts.get(name, 0) for name in names]
    axis.barh(
        np.arange(len(names)),
        values,
        color=[
            "#A43E32" if name == "+ dual-route maximum" else "#9A9A9A"
            for name in names
        ],
    )
    axis.set_yticks(np.arange(len(names)), names)
    axis.set_xlabel("Outer folds selected")
    axis.set_title(
        "(f) Nested selection favors TSI within this sample",
        loc="left",
        weight="bold",
    )
    axis.grid(axis="x", color="0.88", lw=0.6)
    axis.set_axisbelow(True)

    fig.suptitle(
        "Final assessment: a dual-path ENSO-type framework is explainable, "
        "but not yet an operational universal predictor",
        fontsize=14.5,
        weight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.035,
        "Predictand: detrended mature DJF OISST Niño3-Niño4. "
        "All fold-specific trends, FEP regressions, scales and ridge fits use "
        "training years only. Deep route uses SODA3; surface route uses OISST "
        "(ERSST sensitivity also tested).",
        ha="center",
        fontsize=8.0,
        color="0.32",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG)
    fig.savefig(FIGURE_PDF)
    plt.close(fig)


def write_report(
    event_skill: pd.DataFrame,
    chronological_skill: pd.DataFrame,
    all_year_skill: pd.DataFrame,
    warm_skill: pd.DataFrame,
    nested_result: dict[str, object],
    nonextreme_deep: dict[str, float],
    nonextreme_dual: dict[str, float],
    event_predictions: pd.DataFrame,
    mechanism: pd.DataFrame,
) -> None:
    def row(frame: pd.DataFrame, model: str) -> pd.Series:
        return frame.loc[frame["model"].eq(model)].iloc[0]

    deep_event = row(event_skill, "+ deep TSI")
    dual_event = row(event_skill, "+ dual-route maximum")
    dual_ersst = row(event_skill, "+ dual-route maximum (ERSST)")
    deep_chronological = row(chronological_skill, "+ deep TSI")
    dual_chronological = row(
        chronological_skill,
        "+ dual-route maximum",
    )
    deep_all = row(all_year_skill, "+ deep TSI")
    dual_all = row(all_year_skill, "+ dual-route maximum")
    dual_warm = row(warm_skill, "+ dual-route maximum")
    event_2023 = event_predictions.loc[
        event_predictions["year"].eq(2023)
        & event_predictions["model"].isin(
            [
                "+ deep TSI",
                "+ FEP route (OISST)",
                "+ dual-route maximum",
            ]
        ),
        ["model", "prediction_type_residual_c", "observed_type_residual_c"],
    ]
    prediction_text = "\n".join(
        f"- {item.model}: {item.prediction_type_residual_c:+.3f} °C"
        for item in event_2023.itertuples()
    )
    mech_type = mechanism.loc[mechanism["target"].eq("mature_type")]
    mech_text = "\n".join(
        f"- {item.predictor}: r={item.pearson_r:+.3f}, "
        f"q={item.bh_fdr_q_within_target:.3f}"
        for item in mech_type.itertuples()
    )

    report = f"""# ENSO分型双路径模型：最终审计

## 一句话结论

4月140°W输送—储存指数仍是目前最强的**经典海洋动力路线诊断量**；
加入FEP表面路线能修正2023这一特例，但没有在全部年份的严格时间递进
检验中形成稳定、普适的新增技巧。因此现在可以作结的是机制框架，
而不是一个已经可直接业务化的通用回归公式。

## 与权威研究相比，我们真正新增了什么

- Recharge oscillator和WWV研究已经证明赤道热含量是ENSO前兆；TSI并未
  发明新的热含量机制。
- WWB、热跃层反馈和ENSO diversity研究已经说明纬向输送与D20会影响
  EP/CP型态；TSI的新增点是把**140°W处的通过量Q20**与**到达后的
  D20储存**组合成同一4月检查点。
- Peng et al. (2025)、Kim et al. (2025)、Jiang et al. (2026)和
  Fan et al. (2026)共同说明2023不能只用经典西风-Bjerknes路线解释。
  本研究据此把FEP残差作为第二条表面路线，而不是继续向单一路线堆变量。
- Li et al. (2024)把大气Bjerknes反馈拆成SST梯度→降水加热梯度→
  SLP梯度→风应力。本研究按同一区域定义重建这条链，用于解释耦合状态，
  但没有把它误当成独立的海洋初始条件。

## 固定模型结果

- 深层TSI，13暖事件LOEO技巧：
  {deep_event.rmse_skill_vs_sst_persistence:+.1%}，
  r={deep_event.prediction_observation_r:+.3f}，
  q={deep_event.bh_fdr_q_across_preregistered_models:.3f}。
- 双路径最大值，13暖事件LOEO技巧：
  {dual_event.rmse_skill_vs_sst_persistence:+.1%}，
  r={dual_event.prediction_observation_r:+.3f}，
  q={dual_event.bh_fdr_q_across_preregistered_models:.3f}。
- 将FEP换为ERSST后，双路径技巧：
  {dual_ersst.rmse_skill_vs_sst_persistence:+.1%}。
- 剔除1982、1997、2015后，深层TSI技巧：
  {nonextreme_deep['rmse_skill']:+.1%}，
  r={nonextreme_deep['prediction_observation_r']:+.3f}；双路径技巧：
  {nonextreme_dual['rmse_skill']:+.1%}，
  r={nonextreme_dual['prediction_observation_r']:+.3f}。
- 只用过去暖事件、按时间预测2004—2023的7个后续事件：
  深层TSI技巧{deep_chronological.rmse_skill_vs_sst_persistence:+.1%}
  （r={deep_chronological.prediction_observation_r:+.3f}），
  双路径技巧{dual_chronological.rmse_skill_vs_sst_persistence:+.1%}
  （r={dual_chronological.prediction_observation_r:+.3f}）。
- 2000—2023全部年份时间递进中，深层TSI技巧为
  {deep_all.rmse_skill_vs_sst_persistence:+.1%}
  （r={deep_all.prediction_observation_r:+.3f}），双路径最大值为
  {dual_all.rmse_skill_vs_sst_persistence:+.1%}
  （r={dual_all.prediction_observation_r:+.3f}）；均没有超过4月SST基准。
- 在上述时间递进预测中只抽取暖事件，技巧：
  {dual_warm.rmse_skill_vs_sst_persistence:+.1%}，
  r={dual_warm.prediction_observation_r:+.3f}。

## 2023是否被第二路径救回

2023的留一事件观测目标为
{event_2023.observed_type_residual_c.iloc[0]:+.3f} °C。不同固定模型预测为：

{prediction_text}

如果双路径模型明显改善2023而全部年份技巧没有同步提高，正确解释是：
FEP路线对2023具有案例解释力，但目前样本不足以证明它是稳定的通用
预测增量。

## 机制相关

13个暖事件中，各路线与成熟型态的关系为：

{mech_text}

这些相关用于机制定位，不等于因果效应。尤其OISST FEP与OISST成熟目标
共享SST资料，必须同时报告ERSST敏感性。

## 嵌套选择

外层逐事件留出、内层再做留一选择后，整体技巧为
{nested_result['rmse_skill']:+.1%}，预测—观测相关为
{nested_result['prediction_observation_r']:+.3f}，
bootstrap区间为
[{nested_result['bootstrap_skill_ci_low']:+.1%},
 {nested_result['bootstrap_skill_ci_high']:+.1%}]。

内层模型入选次数：
`{json.dumps(nested_result['selected_model_counts'], ensure_ascii=False)}`

内层在绝大多数外层折中选择深层TSI，说明在当前样本与候选集合内选择
较稳定；但这仍是同一13事件内部的嵌套重采样，不能代替新事件或新资料
的外部验证。

## 可以写进论文的结论

1. 3—4月跨过140°W的暖水输送与当地D20储存联合，是经典EP路线的
   高优先级动力检查点。
2. ORAS5独立支持4月155°—140°W D20转变带。新增TAO 0°、140°W
   现场观测中，SODA3 Q20与current-meter、ADCP局地暖水输送代理的
   3—4月逐年相关分别为+0.906和+0.859；TAO与SODA3 D20相关为
   +0.906。TAO是单点，支持赤道流核与储存信号，但不能完整验证
   5°S—5°N断面积分。
3. 2023代表FEP表面先行/弱经典耦合路线，说明TSI不是充分条件。
4. 最小可证伪框架是“深层路线或FEP表面路线”，大气Bjerknes链决定
   随后的放大效率。

## 不能写的结论

1. 不能声称TSI或双路径指数已经是普适业务预测器。
2. 不能只报告13事件中的最高技巧而省略非极端和全部年份检验。
3. 不能把同一海洋再分析中的Q20和D20当作两套独立资料；TAO核验也
   不能被写成完整断面热输送的直接观测。
4. 不能把相关走廊解释成固定经度阈值或已证明的因果转折点。

## 最终最小模型

先区分路径，再判断反馈：

`Route_A = mean[z(Q20_140W), z(D20_140W)]`

`Route_B = z(FEP_residual)`

`EP_potential = max(Route_A, Route_B)`

其中Route_A高表示经典东输—储存路线；Route_B高而Route_A弱表示
2023式FEP先行路线。降水梯度、SLP梯度和风应力链只负责判断这个
海洋/表面势能能否转化为强耦合增长，不再作为与初始海洋状态等价的
平行变量。
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    table = build_analysis_table()
    table.to_csv(ANALYSIS_CSV, index=False)

    event_predictions = event_loeo(table)
    event_predictions.to_csv(EVENT_PRED_CSV, index=False)
    event_skill = skill_table(
        event_predictions,
        family_label="13 warm-event LOEO",
    )
    event_skill.to_csv(EVENT_SKILL_CSV, index=False)

    all_year_predictions = all_year_walkforward(table)
    all_year_predictions.to_csv(ALL_YEAR_PRED_CSV, index=False)
    all_year_skill = skill_table(
        all_year_predictions,
        family_label="all-year walk-forward 2000-2023",
    )
    all_year_skill.to_csv(ALL_YEAR_SKILL_CSV, index=False)

    chronological_predictions = event_chronological(table)
    chronological_predictions.to_csv(EVENT_WALK_PRED_CSV, index=False)
    chronological_skill = skill_table(
        chronological_predictions,
        family_label=(
            "warm-event chronological forecast 2004-2023, "
            "trained on earlier warm events"
        ),
    )
    chronological_skill.to_csv(EVENT_WALK_SKILL_CSV, index=False)

    block = time_block_skill(all_year_predictions)
    block.to_csv(BLOCK_SKILL_CSV, index=False)

    nested = nested_event_selection(table)
    nested.to_csv(NESTED_CSV, index=False)
    nested_result = nested_summary(nested)

    mechanism = mechanism_correlations(table)
    mechanism.to_csv(MECHANISM_CSV, index=False)

    nonextreme_deep = nonextreme_skill(table, "+ deep TSI")
    nonextreme_dual = nonextreme_skill(
        table,
        "+ dual-route maximum",
    )

    event_2023 = event_predictions.loc[
        event_predictions["year"].eq(2023)
    ].set_index("model")
    oras = pd.read_csv(ORAS_SKILL_CSV)
    oras_april = oras.loc[
        oras["checkpoint"].eq("Apr transition D20")
    ].iloc[0]
    diagnostics = {
        "method": {
            "target": "detrended mature DJF OISST Nino3 minus Nino4",
            "deep_route": "Mar-Apr SODA3 Q20 and D20 at 140W",
            "surface_route": (
                "Mar-Apr FEP SST residual after fold-specific removal "
                "of contemporaneous Nino3.4"
            ),
            "validation": (
                "fold-specific detrending, FEP regression, scaling and "
                "ridge fitting"
            ),
            "ridge_alpha": RIDGE_ALPHA,
        },
        "event_loeo": {
            row["model"]: {
                "rmse_skill": row["rmse_skill_vs_sst_persistence"],
                "prediction_observation_r": row[
                    "prediction_observation_r"
                ],
                "fdr_q": row["bh_fdr_q_across_preregistered_models"],
            }
            for _, row in event_skill.loc[
                event_skill["model"].ne("SST persistence")
            ].iterrows()
        },
        "all_year_walkforward": {
            row["model"]: {
                "rmse_skill": row["rmse_skill_vs_sst_persistence"],
                "prediction_observation_r": row[
                    "prediction_observation_r"
                ],
                "fdr_q": row["bh_fdr_q_across_preregistered_models"],
            }
            for _, row in all_year_skill.loc[
                all_year_skill["model"].ne("SST persistence")
            ].iterrows()
        },
        "event_chronological": {
            row["model"]: {
                "rmse_skill": row["rmse_skill_vs_sst_persistence"],
                "prediction_observation_r": row[
                    "prediction_observation_r"
                ],
                "fdr_q": row["bh_fdr_q_across_preregistered_models"],
            }
            for _, row in chronological_skill.loc[
                chronological_skill["model"].ne("SST persistence")
            ].iterrows()
        },
        "nested_event_selection": nested_result,
        "deep_route_nonextreme": nonextreme_deep,
        "dual_route_nonextreme": nonextreme_dual,
        "event_2023": {
            model: {
                "prediction_c": float(
                    event_2023.loc[
                        model,
                        "prediction_type_residual_c",
                    ]
                ),
                "observed_c": float(
                    event_2023.loc[
                        model,
                        "observed_type_residual_c",
                    ]
                ),
            }
            for model in (
                "+ deep TSI",
                "+ FEP route (OISST)",
                "+ dual-route maximum",
            )
        },
        "oras5_independent_april_d20": {
            "sample_r": float(
                oras_april["sample_correlation_with_type"]
            ),
            "loeo_skill": float(
                oras_april["loeo_skill_vs_type_persistence"]
            ),
            "fdr_q": float(
                oras_april[
                    "bh_fdr_q_across_four_preselected_checkpoints"
                ]
            ),
        },
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    plot_results(
        table,
        event_predictions,
        event_skill,
        all_year_skill,
        nested,
    )
    warm_skill = warm_event_walkforward_skill(all_year_predictions)
    write_report(
        event_skill,
        chronological_skill,
        all_year_skill,
        warm_skill,
        nested_result,
        nonextreme_deep,
        nonextreme_dual,
        event_predictions,
        mechanism,
    )
    print(f"Wrote {ANALYSIS_CSV}")
    print(f"Wrote {EVENT_SKILL_CSV}")
    print(f"Wrote {EVENT_WALK_SKILL_CSV}")
    print(f"Wrote {ALL_YEAR_SKILL_CSV}")
    print(f"Wrote {DIAGNOSTICS_JSON}")
    print(f"Wrote {FIGURE_PDF}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
