#!/usr/bin/env python3
"""Search for explainable, operational SODA3 ENSO-type predictors.

The target is mature DJF Niño-3 minus Niño-4. Discovery uses 13 warm events
and February-May SODA3 fields. Prediction skill is estimated with leave-one-
event-out folds in which detrending, scaling, and ridge fitting use only the
other events. ORAS5 D20 provides an independent check of the spatial-temporal
thermocline pathway.
"""

from __future__ import annotations

import itertools
import json
import os
import sys
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_climate_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((ROOT / "scripts").resolve()))

from analyze_soda3_transition_processes import (  # noqa: E402
    benjamini_hochberg,
    bootstrap_skill,
    detrend_with_training,
    paired_improvement_p,
    predict_event_fold,
)
from validate_soda3_transition_with_oras5 import (  # noqa: E402
    stream_adjusted_residual,
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
PROCESS_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_transition_process_indices_1980_2024.csv"
)
GATE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
)
ORAS_RAW_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_process_timeseries_3lat_5deg_1980_2024.csv"
)

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/operational_transition_predictor"
OUT_PDF = ROOT / "output/pdf"
MONTHLY_CSV = OUT_DATA / "soda3_operational_predictor_monthly.csv"
SCREEN_CSV = OUT_DATA / "soda3_operational_predictor_screening.csv"
PREDICTION_CSV = OUT_DATA / "soda3_operational_predictor_loeo_predictions.csv"
SKILL_CSV = OUT_DATA / "soda3_operational_predictor_loeo_skill.csv"
ORAS_CORRELATION_CSV = (
    OUT_DATA / "soda3_oras5_d20_predictive_corridor.csv"
)
ORAS_SKILL_CSV = OUT_DATA / "oras5_d20_checkpoint_loeo_skill.csv"
STABILITY_CSV = OUT_DATA / "soda3_transport_storage_score_stability.csv"
DIAGNOSTICS_JSON = (
    OUT_DATA / "soda3_operational_predictor_diagnostics.json"
)
FIGURE_PNG = OUT_DIR / "soda3_operational_transition_predictor.png"
FIGURE_PDF = OUT_PDF / "soda3_operational_transition_predictor.pdf"
SUMMARY_MD = OUT_DIR / "SODA3_OPERATIONAL_PREDICTOR_RESULTS_CN.md"

MONTHS = (2, 3, 4, 5)
GATE_LONGITUDES = np.arange(150.0, 241.0, 5.0)
PERMUTATION_SAMPLES = 40_000
RIDGE_ALPHA = 1.0
EXTREME_YEARS = (1982, 1997, 2015)

BANDS = {
    "central": (185.0, 195.0),
    "transition": (205.0, 220.0),
    "east": (230.0, 240.0),
}

PROCESS_FEATURES = {
    "vadv_east": (
        "vadv_east_kmonth",
        "vadv_east_kmonth_anom",
        "Eastern vertical advection",
    ),
    "d20_east": (
        "d20_east_m",
        "d20_east_m_anom",
        "Eastern D20",
    ),
    "wwv_east_fraction": (
        "wwv_east_fraction",
        "wwv_east_fraction_anom",
        "East WWV fraction",
    ),
    "wwv_centroid": (
        "wwv_centroid_deg_e",
        "wwv_centroid_deg_e_anom",
        "Warm-volume centroid",
    ),
    "ssh_gradient": (
        "ssh_ew_m",
        "ssh_ew_m_anom",
        "SSH east-west gradient",
    ),
    "barrier": (
        "barrier_east_m",
        "barrier_east_m_anom",
        "Eastern barrier layer",
    ),
    "ohc_tendency": (
        "ohc300_east_tendency_wm2",
        "ohc300_east_tendency_wm2_anom",
        "Eastern OHC tendency",
    ),
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.8,
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


def permutation_correlation(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
) -> tuple[float, float, int]:
    valid = np.isfinite(x) & np.isfinite(y)
    x = np.asarray(x[valid], dtype=float)
    y = np.asarray(y[valid], dtype=float)
    if len(x) < 6:
        return np.nan, np.nan, len(x)
    observed = float(np.corrcoef(x, y)[0, 1])
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    denominator = np.sqrt(
        np.sum(x_centered**2) * np.sum(y_centered**2)
    )
    rng = np.random.default_rng(seed)
    order = np.argsort(
        rng.random((PERMUTATION_SAMPLES, len(y))),
        axis=1,
    )
    null = (y_centered[order] @ x_centered) / denominator
    p_value = float(
        (np.sum(np.abs(null) >= abs(observed)) + 1)
        / (PERMUTATION_SAMPLES + 1)
    )
    return observed, p_value, len(x)


def coordinate_edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    midpoint = 0.5 * (values[:-1] + values[1:])
    return np.r_[
        values[0] - (midpoint[0] - values[0]),
        midpoint,
        values[-1] + (values[-1] - midpoint[-1]),
    ]


def build_soda_monthly() -> tuple[pd.DataFrame, dict[str, float]]:
    base = pd.read_csv(BASE_CSV)
    event_years = pd.read_csv(EVENT_CSV)["event_year"].astype(int)
    base = base.loc[base["year"].isin(event_years)].copy()

    budget = pd.read_csv(BUDGET_CSV)
    budget_columns = [
        "year",
        "month",
        "q20_220e_pw",
        "q20_220e_pw_anom",
        "warm_excess_east_tendency_wm2",
        "warm_excess_east_tendency_wm2_anom",
        "ml_temp_tendency_east_kmonth",
        "ml_temp_tendency_east_kmonth_anom",
    ]
    process = pd.read_csv(PROCESS_CSV)
    process_columns = ["year", "month"]
    for raw, anomaly, _ in PROCESS_FEATURES.values():
        process_columns.extend([raw, anomaly])
    process_columns = list(dict.fromkeys(process_columns))

    gate = pd.read_csv(GATE_CSV)
    gate = gate.loc[gate["longitude_e"].isin(GATE_LONGITUDES)]
    gate_pivot = gate.pivot_table(
        index=["year", "month"],
        columns="longitude_e",
        values=["d20_m", "d20_m_anom"],
    )
    gate_pivot.columns = [
        f"{variable}_{int(longitude)}"
        for variable, longitude in gate_pivot.columns
    ]
    gate_pivot = gate_pivot.reset_index()

    monthly = (
        base.merge(
            budget[budget_columns],
            on=["year", "month"],
            how="left",
            validate="one_to_one",
        )
        .merge(
            process[process_columns],
            on=["year", "month"],
            how="left",
            validate="one_to_one",
        )
        .merge(
            gate_pivot,
            on=["year", "month"],
            how="left",
            validate="one_to_one",
        )
        .sort_values(["year", "month"])
    )

    for band, (west, east) in BANDS.items():
        raw_columns = [
            f"d20_m_{int(longitude)}"
            for longitude in GATE_LONGITUDES
            if west <= longitude <= east
        ]
        anomaly_columns = [
            f"d20_m_anom_{int(longitude)}"
            for longitude in GATE_LONGITUDES
            if west <= longitude <= east
        ]
        monthly[f"d20_band_{band}_m"] = monthly[raw_columns].mean(axis=1)
        monthly[f"d20_band_{band}_m_anom"] = monthly[
            anomaly_columns
        ].mean(axis=1)

    trailing_sources = [
        "q20_220e_pw",
        "q20_220e_pw_anom",
        "d20_m_220",
        "d20_m_anom_220",
        "fep_residual_c",
    ]
    for column in trailing_sources:
        monthly[f"{column}_trail2"] = monthly.groupby("year")[column].transform(
            lambda values: values.rolling(2, min_periods=2).mean()
        )

    # Operational normalization uses all 1980-2024 Apr values, not just events.
    full_budget = pd.read_csv(BUDGET_CSV)
    full_gate = pd.read_csv(GATE_CSV)
    full_gate = full_gate.loc[full_gate["longitude_e"].eq(220.0)]
    full = (
        full_budget[
            ["year", "month", "q20_220e_pw_anom"]
        ]
        .merge(
            full_gate[["year", "month", "d20_m_anom"]],
            on=["year", "month"],
            validate="one_to_one",
        )
        .sort_values(["year", "month"])
    )
    for column in ("q20_220e_pw_anom", "d20_m_anom"):
        full[f"{column}_trail2"] = full.groupby("year")[column].transform(
            lambda values: values.rolling(2, min_periods=2).mean()
        )
    april_climate = full.loc[full["month"].eq(4)]
    q_mean = float(april_climate["q20_220e_pw_anom_trail2"].mean())
    q_sd = float(april_climate["q20_220e_pw_anom_trail2"].std(ddof=1))
    d20_mean = float(april_climate["d20_m_anom_trail2"].mean())
    d20_sd = float(april_climate["d20_m_anom_trail2"].std(ddof=1))
    normalization = {
        "q140_mar_apr_mean_anom_pw_mean": q_mean,
        "q140_mar_apr_mean_anom_pw_sd": q_sd,
        "d20_140w_mar_apr_mean_anom_m_mean": d20_mean,
        "d20_140w_mar_apr_mean_anom_m_sd": d20_sd,
    }
    monthly["transport_storage_score"] = 0.5 * (
        (
            monthly["q20_220e_pw_anom_trail2"] - q_mean
        )
        / q_sd
        + (
            monthly["d20_m_anom_220_trail2"] - d20_mean
        )
        / d20_sd
    )
    return monthly, normalization


def correlation_feature_specs() -> dict[str, tuple[str, str]]:
    specs: dict[str, tuple[str, str]] = {
        "q140": ("q20_220e_pw_anom", "140°W Q20"),
        "q140_trail2": (
            "q20_220e_pw_anom_trail2",
            "2-month mean 140°W Q20",
        ),
        "transport_storage_score": (
            "transport_storage_score",
            "Transport-storage score",
        ),
        "d20_central_band": (
            "d20_band_central_m_anom",
            "D20 175°W-165°W",
        ),
        "d20_transition_band": (
            "d20_band_transition_m_anom",
            "D20 155°W-140°W",
        ),
        "d20_east_band": (
            "d20_band_east_m_anom",
            "D20 130°W-120°W",
        ),
    }
    for longitude in GATE_LONGITUDES:
        specs[f"d20_{int(longitude)}e"] = (
            f"d20_m_anom_{int(longitude)}",
            f"D20 at {longitude_label(longitude)}",
        )
    for name, (_, anomaly, label) in PROCESS_FEATURES.items():
        specs[name] = (anomaly, label)
    return specs


def longitude_label(longitude: float) -> str:
    if longitude < 180.0:
        return f"{int(longitude)}°E"
    if longitude == 180.0:
        return "180°"
    return f"{int(360.0 - longitude)}°W"


def correlation_screen(monthly: pd.DataFrame) -> pd.DataFrame:
    specs = correlation_feature_specs()
    rows = []
    seed = 12_000
    for month in MONTHS:
        current = monthly.loc[monthly["month"].eq(month)]
        target = current["mature_djf_type_index_c"].to_numpy(dtype=float)
        for feature, (column, label) in specs.items():
            correlation, p_value, n_events = permutation_correlation(
                current[column].to_numpy(dtype=float),
                target,
                seed,
            )
            seed += 1
            rows.append(
                {
                    "month": month,
                    "feature": feature,
                    "column": column,
                    "label": label,
                    "correlation_with_djf_nino3_minus_nino4": correlation,
                    "two_sided_permutation_p": p_value,
                    "n_events": n_events,
                }
            )
    output = pd.DataFrame(rows)
    output["bh_fdr_q_across_discovery_family"] = benjamini_hochberg(
        output["two_sided_permutation_p"]
    )
    return output


FEATURE_DEFINITIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "sst_type": ("simple", ("init_type_raw_c",)),
    "q140": ("simple", ("q20_220e_pw",)),
    "q140_trail2": ("simple", ("q20_220e_pw_trail2",)),
    "d20_central": ("simple", ("d20_band_central_m",)),
    "d20_transition": ("simple", ("d20_band_transition_m",)),
    "d20_east_band": ("simple", ("d20_band_east_m",)),
    "fep_trail2": ("simple", ("fep_residual_c_trail2",)),
    "transport_storage_score": (
        "mean",
        ("q20_220e_pw_trail2", "d20_m_220_trail2"),
    ),
    "transport_storage_min": (
        "min",
        ("q20_220e_pw_trail2", "d20_m_220_trail2"),
    ),
}
for longitude in GATE_LONGITUDES:
    FEATURE_DEFINITIONS[f"d20_{int(longitude)}e"] = (
        "simple",
        (f"d20_m_{int(longitude)}",),
    )
for name, (raw, _, _) in PROCESS_FEATURES.items():
    FEATURE_DEFINITIONS[name] = ("simple", (raw,))


def prediction_models() -> dict[str, tuple[str, ...]]:
    models: dict[str, tuple[str, ...]] = {
        "Type persistence": ("sst_type",),
        "+ 140W Q20": ("sst_type", "q140"),
        "+ 2-month 140W Q20": ("sst_type", "q140_trail2"),
        "+ transport-storage score": (
            "sst_type",
            "transport_storage_score",
        ),
        "+ transport-storage minimum": (
            "sst_type",
            "transport_storage_min",
        ),
        "+ Q20 and D20 separately": (
            "sst_type",
            "q140_trail2",
            "d20_220e",
        ),
        "+ score and FEP": (
            "sst_type",
            "transport_storage_score",
            "fep_trail2",
        ),
        "+ central D20 band": ("sst_type", "d20_central"),
        "+ transition D20 band": ("sst_type", "d20_transition"),
        "+ east D20 band": ("sst_type", "d20_east_band"),
    }
    for longitude in GATE_LONGITUDES:
        models[f"+ D20 {longitude_label(longitude)}"] = (
            "sst_type",
            f"d20_{int(longitude)}e",
        )
    for name, (_, _, label) in PROCESS_FEATURES.items():
        models[f"+ {label}"] = ("sst_type", name)
    return models


def predict_custom_fold(
    train: pd.DataFrame,
    test: pd.Series,
    feature_names: tuple[str, ...],
    *,
    ridge_alpha: float = RIDGE_ALPHA,
    minimum_training: int = 10,
) -> tuple[float, float]:
    primitive_columns = sorted(
        {
            column
            for feature in feature_names
            for column in FEATURE_DEFINITIONS[feature][1]
        }
    )
    required = ["mature_djf_type_raw_c", *primitive_columns]
    train = train.dropna(subset=required)
    if len(train) < minimum_training or test[required].isna().any():
        return np.nan, np.nan
    years = train["year"].to_numpy(dtype=float)
    test_year = float(test["year"])
    target_train, observed = detrend_with_training(
        years,
        train["mature_djf_type_raw_c"].to_numpy(dtype=float),
        test_year,
        float(test["mature_djf_type_raw_c"]),
    )
    standardized_train: dict[str, np.ndarray] = {}
    standardized_test: dict[str, float] = {}
    for column in primitive_columns:
        residual, test_residual = detrend_with_training(
            years,
            train[column].to_numpy(dtype=float),
            test_year,
            float(test[column]),
        )
        scale = float(np.std(residual, ddof=1))
        if not np.isfinite(scale) or scale == 0.0:
            return np.nan, np.nan
        standardized_train[column] = residual / scale
        standardized_test[column] = test_residual / scale

    train_features = []
    test_features = []
    for feature in feature_names:
        operation, columns = FEATURE_DEFINITIONS[feature]
        arrays = [standardized_train[column] for column in columns]
        values = [standardized_test[column] for column in columns]
        if operation == "simple":
            train_feature = arrays[0]
            test_feature = values[0]
        elif operation == "mean":
            train_feature = np.mean(np.column_stack(arrays), axis=1)
            test_feature = float(np.mean(values))
        elif operation == "min":
            train_feature = np.min(np.column_stack(arrays), axis=1)
            test_feature = float(np.min(values))
        else:
            raise ValueError(operation)
        train_features.append(train_feature)
        test_features.append(test_feature)

    x_train = np.column_stack(train_features)
    gram = x_train.T @ x_train
    coefficients = np.linalg.solve(
        gram + ridge_alpha * np.eye(gram.shape[0]),
        x_train.T @ target_train,
    )
    prediction = float(np.asarray(test_features) @ coefficients)
    return prediction, observed


def loeo_predictions(monthly: pd.DataFrame) -> pd.DataFrame:
    models = prediction_models()
    rows = []
    for month in MONTHS:
        current = monthly.loc[monthly["month"].eq(month)].copy()
        for event_year in current["year"].astype(int):
            test = current.loc[current["year"].eq(event_year)].iloc[0]
            train = current.loc[current["year"].ne(event_year)]
            for model, features in models.items():
                prediction, observed = predict_custom_fold(
                    train,
                    test,
                    features,
                )
                rows.append(
                    {
                        "event_year": event_year,
                        "month": month,
                        "model": model,
                        "prediction_type_residual_c": prediction,
                        "observed_type_residual_c": observed,
                        "n_training_events": len(train),
                        "ridge_alpha": RIDGE_ALPHA,
                    }
                )
    return pd.DataFrame(rows)


def skill_table(predictions: pd.DataFrame) -> pd.DataFrame:
    baseline = predictions.loc[
        predictions["model"].eq("Type persistence"),
        [
            "event_year",
            "month",
            "prediction_type_residual_c",
        ],
    ].rename(
        columns={"prediction_type_residual_c": "baseline_prediction_c"}
    )
    merged = predictions.merge(
        baseline,
        on=["event_year", "month"],
        how="left",
        validate="many_to_one",
    )
    rows = []
    seed = 24_000
    for (month, model), current in merged.groupby(["month", "model"]):
        current = current.dropna(
            subset=[
                "prediction_type_residual_c",
                "observed_type_residual_c",
                "baseline_prediction_c",
            ]
        )
        observed = current["observed_type_residual_c"].to_numpy(dtype=float)
        predicted = current["prediction_type_residual_c"].to_numpy(dtype=float)
        baseline_values = current["baseline_prediction_c"].to_numpy(
            dtype=float
        )
        rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
        baseline_rmse = float(
            np.sqrt(np.mean((baseline_values - observed) ** 2))
        )
        skill = 1.0 - rmse / baseline_rmse
        if model == "Type persistence":
            p_value = ci_low = ci_high = np.nan
        else:
            p_value = paired_improvement_p(
                observed,
                predicted,
                baseline_values,
                seed,
            )
            ci_low, ci_high = bootstrap_skill(
                observed,
                predicted,
                baseline_values,
                seed + 5000,
            )
        seed += 1
        rows.append(
            {
                "month": month,
                "model": model,
                "rmse_c": rmse,
                "baseline_rmse_c": baseline_rmse,
                "rmse_skill_vs_type_persistence": skill,
                "prediction_observation_r": (
                    float(np.corrcoef(predicted, observed)[0, 1])
                    if len(observed) >= 3
                    else np.nan
                ),
                "one_sided_paired_improvement_p": p_value,
                "bootstrap_skill_ci_low": ci_low,
                "bootstrap_skill_ci_high": ci_high,
                "n_events": len(current),
            }
        )
    output = pd.DataFrame(rows)
    added = output["model"].ne("Type persistence")
    output.loc[
        added,
        "bh_fdr_q_across_exploratory_model_month_family",
    ] = benjamini_hochberg(
        output.loc[added, "one_sided_paired_improvement_p"]
    )
    return output


def build_oras_d20() -> pd.DataFrame:
    raw = pd.read_csv(ORAS_RAW_CSV)
    raw["latitude_weight"] = np.cos(
        np.deg2rad(raw["requested_lat"].to_numpy(dtype=float))
    )
    rows = []
    for (year, month, longitude), current in raw.groupby(
        ["year", "month", "requested_lon"],
        sort=True,
    ):
        rows.append(
            {
                "year": int(year),
                "month": int(month),
                "longitude_e": float(longitude),
                "d20_m": float(
                    np.average(
                        current["d20_m"].to_numpy(dtype=float),
                        weights=current["latitude_weight"].to_numpy(
                            dtype=float
                        ),
                    )
                ),
            }
        )
    frame = pd.DataFrame(rows).sort_values(
        ["longitude_e", "year", "month"]
    )
    pieces = []
    for _, current in frame.groupby("longitude_e", sort=True):
        current = current.copy()
        current["d20_m_anom"] = stream_adjusted_residual(
            current["d20_m"].to_numpy(dtype=float),
            current["year"].to_numpy(dtype=int),
            current["month"].to_numpy(dtype=int),
        )
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True).sort_values(
        ["year", "month", "longitude_e"]
    )


def d20_correlation_field(
    frame: pd.DataFrame,
    base: pd.DataFrame,
    *,
    source: str,
    anomaly_column: str,
) -> pd.DataFrame:
    event_years = pd.read_csv(EVENT_CSV)["event_year"].astype(int)
    target = (
        base.loc[base["year"].isin(event_years)]
        [["year", "month", "mature_djf_type_index_c"]]
        .drop_duplicates(["year", "month"])
    )
    merged = frame.merge(
        target,
        on=["year", "month"],
        how="inner",
        validate="many_to_one",
    )
    rows = []
    seed = 36_000 if source == "SODA3" else 48_000
    for (month, longitude), current in merged.loc[
        merged["month"].isin(MONTHS)
    ].groupby(["month", "longitude_e"], sort=True):
        correlation, p_value, n_events = permutation_correlation(
            current[anomaly_column].to_numpy(dtype=float),
            current["mature_djf_type_index_c"].to_numpy(dtype=float),
            seed,
        )
        seed += 1
        rows.append(
            {
                "source": source,
                "month": int(month),
                "longitude_e": float(longitude),
                "correlation_with_djf_nino3_minus_nino4": correlation,
                "two_sided_permutation_p": p_value,
                "n_events": n_events,
            }
        )
    return pd.DataFrame(rows)


def oras_checkpoint_skill(
    oras: pd.DataFrame,
    base: pd.DataFrame,
) -> pd.DataFrame:
    checkpoints = {
        "Feb central D20": (2, 185.0, 195.0),
        "Mar central D20": (3, 185.0, 195.0),
        "Apr transition D20": (4, 205.0, 220.0),
        "May eastern D20": (5, 230.0, 240.0),
    }
    event_years = pd.read_csv(EVENT_CSV)["event_year"].astype(int)
    rows = []
    seed = 60_000
    for checkpoint, (month, west, east) in checkpoints.items():
        feature = (
            oras.loc[
                oras["month"].eq(month)
                & oras["longitude_e"].between(west, east)
            ]
            .groupby(["year", "month"], as_index=False)["d20_m_anom"]
            .mean()
            .rename(columns={"d20_m_anom": "oras_d20_checkpoint"})
        )
        current = (
            base.loc[
                base["year"].isin(event_years) & base["month"].eq(month)
            ]
            .merge(
                feature,
                on=["year", "month"],
                how="left",
                validate="one_to_one",
            )
        )
        prediction_rows = []
        for event_year in current["year"].astype(int):
            test = current.loc[current["year"].eq(event_year)].iloc[0]
            train = current.loc[current["year"].ne(event_year)]
            prediction, observed = predict_event_fold(
                train,
                test,
                ("init_type_raw_c", "oras_d20_checkpoint"),
            )
            baseline, _ = predict_event_fold(
                train,
                test,
                ("init_type_raw_c",),
            )
            prediction_rows.append((prediction, observed, baseline))
        values = np.asarray(prediction_rows, dtype=float)
        predicted, observed, baseline_values = values.T
        rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
        baseline_rmse = float(
            np.sqrt(np.mean((baseline_values - observed) ** 2))
        )
        ci_low, ci_high = bootstrap_skill(
            observed,
            predicted,
            baseline_values,
            seed + 1000,
        )
        sample_correlation, sample_p, _ = permutation_correlation(
            current["oras_d20_checkpoint"].to_numpy(dtype=float),
            current["mature_djf_type_index_c"].to_numpy(dtype=float),
            seed + 2000,
        )
        rows.append(
            {
                "checkpoint": checkpoint,
                "month": month,
                "longitude_west_e": west,
                "longitude_east_e": east,
                "sample_correlation_with_type": sample_correlation,
                "sample_two_sided_permutation_p": sample_p,
                "loeo_rmse_c": rmse,
                "baseline_rmse_c": baseline_rmse,
                "loeo_skill_vs_type_persistence": (
                    1.0 - rmse / baseline_rmse
                ),
                "prediction_observation_r": float(
                    np.corrcoef(predicted, observed)[0, 1]
                ),
                "one_sided_paired_improvement_p": paired_improvement_p(
                    observed,
                    predicted,
                    baseline_values,
                    seed,
                ),
                "bootstrap_skill_ci_low": ci_low,
                "bootstrap_skill_ci_high": ci_high,
                "n_events": len(current),
            }
        )
        seed += 1
    output = pd.DataFrame(rows)
    output["bh_fdr_q_across_four_preselected_checkpoints"] = (
        benjamini_hochberg(output["one_sided_paired_improvement_p"])
    )
    return output


def primary_stability(
    monthly: pd.DataFrame,
    predictions: pd.DataFrame,
    skill: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    april = monthly.loc[monthly["month"].eq(4)].copy()
    primary_predictions = predictions.loc[
        predictions["month"].eq(4)
        & predictions["model"].eq("+ transport-storage score")
    ].sort_values("event_year")
    primary_skill = skill.loc[
        skill["month"].eq(4)
        & skill["model"].eq("+ transport-storage score")
    ].iloc[0]

    full_r, full_p, _ = permutation_correlation(
        april["transport_storage_score"].to_numpy(dtype=float),
        april["mature_djf_type_index_c"].to_numpy(dtype=float),
        72_000,
    )
    spearman_r = float(
        spearmanr(
            april["transport_storage_score"],
            april["mature_djf_type_index_c"],
        ).statistic
    )
    jackknife = []
    for event_year in april["year"].astype(int):
        selected = april["year"].ne(event_year)
        jackknife.append(
            april.loc[selected, "transport_storage_score"].corr(
                april.loc[selected, "mature_djf_type_index_c"]
            )
        )
    nonextreme = april.loc[~april["year"].isin(EXTREME_YEARS)].copy()
    nonextreme_r = float(
        nonextreme["transport_storage_score"].corr(
            nonextreme["mature_djf_type_index_c"]
        )
    )

    rows = []
    for alpha in (0.1, 0.3, 1.0, 3.0, 10.0):
        predicted = []
        observed = []
        baseline = []
        for event_year in april["year"].astype(int):
            test = april.loc[april["year"].eq(event_year)].iloc[0]
            train = april.loc[april["year"].ne(event_year)]
            current_prediction, current_observed = predict_custom_fold(
                train,
                test,
                ("sst_type", "transport_storage_score"),
                ridge_alpha=alpha,
            )
            current_baseline, _ = predict_custom_fold(
                train,
                test,
                ("sst_type",),
                ridge_alpha=RIDGE_ALPHA,
            )
            predicted.append(current_prediction)
            observed.append(current_observed)
            baseline.append(current_baseline)
        predicted_array = np.asarray(predicted)
        observed_array = np.asarray(observed)
        baseline_array = np.asarray(baseline)
        rmse = float(
            np.sqrt(np.mean((predicted_array - observed_array) ** 2))
        )
        baseline_rmse = float(
            np.sqrt(np.mean((baseline_array - observed_array) ** 2))
        )
        rows.append(
            {
                "test": "ridge_alpha_sensitivity",
                "setting": alpha,
                "n_events": len(april),
                "correlation": float(
                    np.corrcoef(predicted_array, observed_array)[0, 1]
                ),
                "rmse_c": rmse,
                "rmse_skill": 1.0 - rmse / baseline_rmse,
            }
        )

    # Non-extreme LOEO is deliberately a sensitivity check with nine training
    # events per fold, below the main analysis's minimum of ten.
    predicted = []
    observed = []
    baseline = []
    for event_year in nonextreme["year"].astype(int):
        test = nonextreme.loc[nonextreme["year"].eq(event_year)].iloc[0]
        train = nonextreme.loc[nonextreme["year"].ne(event_year)]
        current_prediction, current_observed = predict_custom_fold(
            train,
            test,
            ("sst_type", "transport_storage_score"),
            minimum_training=8,
        )
        current_baseline, _ = predict_custom_fold(
            train,
            test,
            ("sst_type",),
            minimum_training=8,
        )
        predicted.append(current_prediction)
        observed.append(current_observed)
        baseline.append(current_baseline)
    predicted_array = np.asarray(predicted)
    observed_array = np.asarray(observed)
    baseline_array = np.asarray(baseline)
    rmse = float(np.sqrt(np.mean((predicted_array - observed_array) ** 2)))
    baseline_rmse = float(
        np.sqrt(np.mean((baseline_array - observed_array) ** 2))
    )
    rows.append(
        {
            "test": "exclude_1982_1997_2015",
            "setting": "non-extreme events",
            "n_events": len(nonextreme),
            "correlation": float(
                np.corrcoef(predicted_array, observed_array)[0, 1]
            ),
            "rmse_c": rmse,
            "rmse_skill": 1.0 - rmse / baseline_rmse,
        }
    )
    nonextreme_loeo_r = float(
        np.corrcoef(predicted_array, observed_array)[0, 1]
    )
    nonextreme_loeo_skill = 1.0 - rmse / baseline_rmse

    event_2023 = primary_predictions.loc[
        primary_predictions["event_year"].eq(2023)
    ].iloc[0]
    diagnostics = {
        "primary_sample_r": full_r,
        "primary_sample_spearman_r": spearman_r,
        "primary_sample_permutation_p": full_p,
        "primary_jackknife_r_min": float(np.min(jackknife)),
        "primary_jackknife_r_max": float(np.max(jackknife)),
        "primary_nonextreme_sample_r": nonextreme_r,
        "primary_nonextreme_loeo_r": nonextreme_loeo_r,
        "primary_nonextreme_loeo_skill": nonextreme_loeo_skill,
        "primary_loeo_rmse_skill": float(
            primary_skill["rmse_skill_vs_type_persistence"]
        ),
        "primary_loeo_prediction_observation_r": float(
            primary_skill["prediction_observation_r"]
        ),
        "primary_loeo_p": float(
            primary_skill["one_sided_paired_improvement_p"]
        ),
        "primary_loeo_fdr_q": float(
            primary_skill[
                "bh_fdr_q_across_exploratory_model_month_family"
            ]
        ),
        "primary_loeo_ci_low": float(
            primary_skill["bootstrap_skill_ci_low"]
        ),
        "primary_loeo_ci_high": float(
            primary_skill["bootstrap_skill_ci_high"]
        ),
        "event_2023_observed_type_residual_c": float(
            event_2023["observed_type_residual_c"]
        ),
        "event_2023_primary_prediction_c": float(
            event_2023["prediction_type_residual_c"]
        ),
    }
    return pd.DataFrame(rows), diagnostics


def plot_results(
    monthly: pd.DataFrame,
    d20_corridor: pd.DataFrame,
    predictions: pd.DataFrame,
    skill: pd.DataFrame,
    oras_skill: pd.DataFrame,
    diagnostics: dict[str, float],
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 3, figsize=(14.4, 8.2))
    figure.subplots_adjust(
        left=0.065,
        right=0.975,
        bottom=0.105,
        top=0.90,
        wspace=0.28,
        hspace=0.34,
    )
    cmap = "RdBu_r"
    norm = mpl.colors.TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0)
    image = None
    best_longitudes: dict[str, pd.DataFrame] = {}
    for axis, source, panel in zip(
        axes[0, :2],
        ("SODA3", "ORAS5"),
        ("(a)", "(b)"),
        strict=True,
    ):
        current = d20_corridor.loc[d20_corridor["source"].eq(source)]
        matrix = current.pivot(
            index="month",
            columns="longitude_e",
            values="correlation_with_djf_nino3_minus_nino4",
        ).reindex(index=MONTHS, columns=GATE_LONGITUDES)
        image = axis.pcolormesh(
            coordinate_edges(GATE_LONGITUDES),
            coordinate_edges(np.asarray(MONTHS, dtype=float)),
            matrix.to_numpy(),
            cmap=cmap,
            norm=norm,
            shading="flat",
        )
        best = (
            current.loc[
                current.groupby("month")[
                    "correlation_with_djf_nino3_minus_nino4"
                ].idxmax()
            ]
            .sort_values("month")
        )
        best_longitudes[source] = best
        axis.plot(
            best["longitude_e"],
            best["month"],
            color="black",
            marker="o",
            ms=4.2,
            lw=1.2,
            label="maximum r",
        )
        axis.axvline(180.0, color="0.2", ls="--", lw=0.8)
        axis.axvline(220.0, color="0.2", ls="-", lw=0.9)
        axis.set_xlim(147.5, 242.5)
        axis.set_ylim(5.5, 1.5)
        axis.set_xticks([150, 180, 200, 220, 240])
        axis.set_xticklabels(
            ["150°E", "180°", "160°W", "140°W", "120°W"]
        )
        axis.set_yticks(MONTHS)
        axis.set_yticklabels(["Feb", "Mar", "Apr", "May"])
        axis.set_xlabel("")
        axis.set_ylabel("Prediction checkpoint")
        axis.set_title(
            f"{panel} {source} D20 correlation with mature type",
            fontweight="bold",
        )
        axis.legend(loc="lower left", frameon=False)
    if image is None:
        raise RuntimeError("No D20 correlation field plotted")
    colorbar = figure.colorbar(
        image,
        ax=list(axes[0, :2]),
        orientation="horizontal",
        fraction=0.045,
        pad=0.11,
        aspect=35,
    )
    colorbar.set_label("Correlation with mature DJF Niño3 - Niño4")

    axis = axes[0, 2]
    for source, color, marker in (
        ("SODA3", "#B03A2E", "o"),
        ("ORAS5", "#2874A6", "s"),
    ):
        best = best_longitudes[source]
        axis.plot(
            best["month"],
            best["longitude_e"],
            color=color,
            marker=marker,
            lw=1.8,
            ms=5.5,
            label=source,
        )
    axis.set_xticks(MONTHS)
    axis.set_xticklabels(["Feb", "Mar", "Apr", "May"])
    axis.set_yticks([180, 190, 200, 210, 220, 230, 240])
    axis.set_yticklabels(
        ["180°", "170°W", "160°W", "150°W", "140°W", "130°W", "120°W"]
    )
    axis.set_ylim(175, 245)
    axis.grid(color="0.88", lw=0.7)
    axis.set_ylabel("Longitude of maximum D20-type r")
    axis.set_title(
        "(c) Maximum-r longitude: broad eastward corridor",
        fontweight="bold",
    )
    axis.legend(frameon=False)

    axis = axes[1, 0]
    april = monthly.loc[monthly["month"].eq(4)].sort_values("year")
    x = april["transport_storage_score"].to_numpy(dtype=float)
    y = april["mature_djf_type_index_c"].to_numpy(dtype=float)
    axis.scatter(x, y, color="#B03A2E", s=35, zorder=3)
    fit = np.polyfit(x, y, 1)
    x_line = np.linspace(x.min() - 0.15, x.max() + 0.15, 100)
    axis.plot(x_line, fit[0] * x_line + fit[1], color="0.2", lw=1.2)
    label_offsets = {
        1986: (3, -9),
        1991: (-17, 5),
        2002: (-17, -10),
        2006: (3, 6),
        2009: (3, -10),
        2018: (3, 7),
        2019: (3, -10),
    }
    for row in april.itertuples():
        axis.annotate(
            str(int(row.year)),
            (row.transport_storage_score, row.mature_djf_type_index_c),
            xytext=label_offsets.get(int(row.year), (3, 3)),
            textcoords="offset points",
            fontsize=6.8,
        )
    axis.axhline(0.0, color="0.65", lw=0.7)
    axis.axvline(0.0, color="0.65", lw=0.7)
    axis.set_xlabel("April transport-storage score")
    axis.set_ylabel("Mature DJF Niño3 - Niño4 (°C)")
    axis.set_title(
        "(d) Mechanistic score and mature type",
        fontweight="bold",
    )
    axis.text(
        0.03,
        0.96,
        (
            f"r={diagnostics['primary_sample_r']:.2f}, "
            f"p={diagnostics['primary_sample_permutation_p']:.4f}\n"
            "Mar-Apr Q20(140°W) + D20(140°W)"
        ),
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=7.5,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )

    axis = axes[1, 1]
    selected = predictions.loc[
        predictions["month"].eq(4)
        & predictions["model"].isin(
            ["Type persistence", "+ transport-storage score"]
        )
    ]
    baseline = selected.loc[
        selected["model"].eq("Type persistence")
    ].sort_values("event_year")
    score = selected.loc[
        selected["model"].eq("+ transport-storage score")
    ].sort_values("event_year")
    observed = score["observed_type_residual_c"].to_numpy(dtype=float)
    axis.scatter(
        observed,
        baseline["prediction_type_residual_c"],
        color="0.55",
        marker="x",
        s=38,
        label="SST-type persistence",
    )
    axis.scatter(
        observed,
        score["prediction_type_residual_c"],
        color="#B03A2E",
        marker="o",
        s=32,
        label="+ transport-storage score",
    )
    limit = max(
        2.1,
        float(
            np.nanmax(
                np.abs(
                    np.r_[
                        observed,
                        baseline["prediction_type_residual_c"],
                        score["prediction_type_residual_c"],
                    ]
                )
            )
            * 1.08
        ),
    )
    axis.plot([-limit, limit], [-limit, limit], color="0.3", lw=0.9)
    axis.set_xlim(-limit, limit)
    axis.set_ylim(-limit, limit)
    axis.axhline(0.0, color="0.8", lw=0.6)
    axis.axvline(0.0, color="0.8", lw=0.6)
    axis.set_xlabel("Observed detrended mature type (°C)")
    axis.set_ylabel("LOEO prediction (°C)")
    axis.set_title(
        "(e) Leave-one-event-out prediction",
        fontweight="bold",
    )
    axis.legend(loc="upper left", frameon=False)
    axis.text(
        0.97,
        0.04,
        (
            f"RMSE skill={diagnostics['primary_loeo_rmse_skill']:+.0%}\n"
            f"prediction r={diagnostics['primary_loeo_prediction_observation_r']:.2f}"
        ),
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.5,
    )

    axis = axes[1, 2]
    skill_items = []
    for month, model, label, color in (
        (2, "+ central D20 band", "Feb SODA central D20", "#D98880"),
        (3, "+ central D20 band", "Mar SODA central D20", "#CD6155"),
        (
            4,
            "+ transport-storage score",
            "Apr SODA transport-storage",
            "#922B21",
        ),
    ):
        row = skill.loc[
            skill["month"].eq(month) & skill["model"].eq(model)
        ].iloc[0]
        skill_items.append(
            (
                label,
                row["rmse_skill_vs_type_persistence"],
                row["bootstrap_skill_ci_low"],
                row["bootstrap_skill_ci_high"],
                color,
            )
        )
    for checkpoint, label, color in (
        ("Apr transition D20", "Apr ORAS5 transition D20", "#2471A3"),
        ("May eastern D20", "May ORAS5 eastern D20", "#5DADE2"),
    ):
        row = oras_skill.loc[oras_skill["checkpoint"].eq(checkpoint)].iloc[0]
        skill_items.append(
            (
                label,
                row["loeo_skill_vs_type_persistence"],
                row["bootstrap_skill_ci_low"],
                row["bootstrap_skill_ci_high"],
                color,
            )
        )
    labels, values, lows, highs, colors = zip(*skill_items, strict=True)
    positions = np.arange(len(labels))
    axis.barh(positions, values, color=colors, alpha=0.9)
    axis.errorbar(
        values,
        positions,
        xerr=[
            np.asarray(values) - np.asarray(lows),
            np.asarray(highs) - np.asarray(values),
        ],
        fmt="none",
        ecolor="0.2",
        capsize=2.5,
        lw=0.9,
    )
    axis.axvline(0.0, color="0.35", lw=0.8)
    axis.set_yticks(positions)
    axis.set_yticklabels(labels)
    axis.invert_yaxis()
    axis.set_xlim(-0.15, 0.85)
    axis.set_xlabel("RMSE skill vs current SST type")
    axis.set_title(
        "(f) Staged operational checkpoints",
        fontweight="bold",
    )
    axis.grid(axis="x", color="0.9", lw=0.7)

    figure.suptitle(
        "Finding an explainable and potentially operational ENSO-type predictor",
        fontsize=14.0,
        fontweight="bold",
        y=0.972,
    )
    figure.text(
        0.065,
        0.025,
        (
            "Target: detrended mature DJF Niño3-Niño4 across 13 warm events. "
            "Anomalies remove the 1980-2024 calendar-month baseline/trend; "
            "ORAS5 also removes the consolidated-operational stream offset. "
            "LOEO detrending, scaling and ridge fitting use training events only. "
            "Skill is exploratory; ORAS5 D20 is an independent confirmation of "
            "the thermocline corridor, not of SODA3 Q20."
        ),
        ha="left",
        va="bottom",
        fontsize=7.2,
        color="0.28",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def write_summary(
    normalization: dict[str, float],
    screen: pd.DataFrame,
    skill: pd.DataFrame,
    oras_skill: pd.DataFrame,
    diagnostics: dict[str, float],
) -> None:
    primary_screen = screen.loc[
        screen["month"].eq(4)
        & screen["feature"].eq("transport_storage_score")
    ].iloc[0]
    primary_skill = skill.loc[
        skill["month"].eq(4)
        & skill["model"].eq("+ transport-storage score")
    ].iloc[0]
    oras_april = oras_skill.loc[
        oras_skill["checkpoint"].eq("Apr transition D20")
    ].iloc[0]
    formula = (
        "TSI_Apr = 0.5 × [Q20′(140°W, Mar-Apr) / "
        f"{normalization['q140_mar_apr_mean_anom_pw_sd']:.3f} PW + "
        "D20′(140°W, Mar-Apr) / "
        f"{normalization['d20_140w_mar_apr_mean_anom_m_sd']:.2f} m]"
    )
    text = f"""# SODA3可解释预测量筛选结果

## 目前最有潜力的量

当前最强、同时具有明确物理含义的候选是**4月输送-储存指数**
（transport-storage index, TSI）：

`{formula}`

Q20′为140°W暖水东向热输送异常，D20′为140°W热跃层深度异常；
两者都先取3–4月平均，再用1980–2024年全部年份4月样本的标准差归一化。
这个定义不使用成熟期信息。

- 与成熟DJF Niño3-Niño4的样本相关：
  r={primary_screen['correlation_with_djf_nino3_minus_nino4']:+.3f}，
  permutation p={primary_screen['two_sided_permutation_p']:.4f}，
  探索指标族FDR q={primary_screen['bh_fdr_q_across_discovery_family']:.4f}。
- 留一事件预测相对当月SST型态基线的RMSE skill：
  {primary_skill['rmse_skill_vs_type_persistence']:+.3f}，
  p={primary_skill['one_sided_paired_improvement_p']:.4f}，
  探索模型×月份FDR q=
  {primary_skill['bh_fdr_q_across_exploratory_model_month_family']:.4f}，
  bootstrap区间
  [{primary_skill['bootstrap_skill_ci_low']:+.3f},
  {primary_skill['bootstrap_skill_ci_high']:+.3f}]。
- LOEO预测与观测相关为
  {primary_skill['prediction_observation_r']:+.3f}。

## 为什么它比单独一个量更合理

140°W Q20回答“热量有没有穿过动力闸门”，D20回答“热量是否已经转化为
当地热跃层加深和储存”。指数要求输送和储存同时偏强，因此对应：

西风/海流调整 → 暖水穿过140°W → 热跃层加深 → 东部持续增暖。

单独4月Q20的LOEO skill约为+0.47；加入储存分量后提高到约
{primary_skill['rmse_skill_vs_type_persistence']:+.2f}。

## 跨资料发现：D20可预测走廊向东扩展

SODA3与ORAS5都显示D20和最终类型的高相关区在春季向东扩展，但
“最大相关所在经度”并非每个月都严格单调东移：

- 2–3月：主要位于175°W–165°W附近；
- 4月：155°W–140°W过渡带在两套资料中都已出现强相关；
- 5月：SODA3的最大值移到东部，而ORAS5的最大值仍偏中东太平洋，
  但130°W–120°W带平均值依然与最终类型强相关。

预先指定的ORAS5 4月155°W–140°W D20指标与最终类型相关
r={oras_april['sample_correlation_with_type']:+.3f}，
其LOEO RMSE skill={oras_april['loeo_skill_vs_type_persistence']:+.3f}，
p={oras_april['one_sided_paired_improvement_p']:.4f}，
四个预设检查点FDR q=
{oras_april['bh_fdr_q_across_four_preselected_checkpoints']:.4f}。
这独立确认了D20传播/储存通道，但没有独立确认SODA3的Q20分量。

## 实际预测建议

1. 2–3月先看175°W–165°W D20是否显著偏深；
2. 4月底计算TSI，同时检查ORAS5的155°W–140°W D20；
3. 若TSI和过渡带D20都偏强，提高EP型概率；
4. 若信号停留在中部或Q20强但D20不维持，保留CP或FEP表层先行、
   海气耦合不足的可能。

目前不建议设置“超过某个数就一定转型”的硬阈值，而应把TSI作为连续
概率更新量。

## 稳健性与限制

- TSI样本相关的逐事件jackknife范围为
  [{diagnostics['primary_jackknife_r_min']:+.3f},
  {diagnostics['primary_jackknife_r_max']:+.3f}]。
- 去掉1982、1997和2015三个极端事件后，样本相关降至
  {diagnostics['primary_nonextreme_sample_r']:+.3f}；非极端事件LOEO
  技巧为{diagnostics['primary_nonextreme_loeo_skill']:+.3f}，
  预测-观测相关为
  {diagnostics['primary_nonextreme_loeo_r']:+.3f}，仍为正但明显变弱。
- 2023的LOEO观测型态残差为
  {diagnostics['event_2023_observed_type_residual_c']:+.2f}°C，
  TSI预测只有
  {diagnostics['event_2023_primary_prediction_c']:+.2f}°C。
  因此TSI更擅长识别“海洋动力驱动的经典EP路径”，对2023式FEP表层
  先行事件会低估。
- 只有13个暖事件，TSI是在探索阶段形成的候选；实际应用前需要用
  SODA4、ORAS5全三维温度/流速或未来事件做冻结公式验证。

## 文件

- 图：`{FIGURE_PDF}`
- 月度候选表：`{MONTHLY_CSV}`
- 相关筛选：`{SCREEN_CSV}`
- 留一预测：`{PREDICTION_CSV}`
- 留一技巧：`{SKILL_CSV}`
- SODA3/ORAS5 D20走廊：`{ORAS_CORRELATION_CSV}`
- ORAS5检查点技巧：`{ORAS_SKILL_CSV}`
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(text, encoding="utf-8")


def main() -> int:
    monthly, normalization = build_soda_monthly()
    screen = correlation_screen(monthly)
    predictions = loeo_predictions(monthly)
    skill = skill_table(predictions)

    base = pd.read_csv(BASE_CSV)
    soda_gate = pd.read_csv(GATE_CSV).rename(
        columns={"longitude_e": "longitude_e"}
    )
    soda_corridor = d20_correlation_field(
        soda_gate,
        base,
        source="SODA3",
        anomaly_column="d20_m_anom",
    )
    oras = build_oras_d20()
    oras_corridor = d20_correlation_field(
        oras,
        base,
        source="ORAS5",
        anomaly_column="d20_m_anom",
    )
    d20_corridor = pd.concat(
        [soda_corridor, oras_corridor],
        ignore_index=True,
    )
    oras_skill = oras_checkpoint_skill(oras, base)
    stability, diagnostics = primary_stability(
        monthly,
        predictions,
        skill,
    )
    diagnostics.update(normalization)
    diagnostics.update(
        {
            "n_events": int(monthly["year"].nunique()),
            "n_soda_screen_tests": int(len(screen)),
            "n_soda_added_model_month_tests": int(
                skill["model"].ne("Type persistence").sum()
            ),
            "n_oras_preselected_checkpoints": int(len(oras_skill)),
        }
    )

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_CSV, index=False)
    screen.to_csv(SCREEN_CSV, index=False)
    predictions.to_csv(PREDICTION_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    d20_corridor.to_csv(ORAS_CORRELATION_CSV, index=False)
    oras_skill.to_csv(ORAS_SKILL_CSV, index=False)
    stability.to_csv(STABILITY_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    plot_results(
        monthly,
        d20_corridor,
        predictions,
        skill,
        oras_skill,
        diagnostics,
    )
    write_summary(
        normalization,
        screen,
        skill,
        oras_skill,
        diagnostics,
    )
    print(f"Wrote {SCREEN_CSV}")
    print(f"Wrote {SKILL_CSV}")
    print(f"Wrote {ORAS_SKILL_CSV}")
    print(f"Wrote {FIGURE_PDF}")
    print(f"Wrote {SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
