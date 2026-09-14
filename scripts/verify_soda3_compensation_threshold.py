#!/usr/bin/env python3
"""Verify a western-warm-water / wind compensation threshold with SODA3.

The analysis tests two distinct gates.

Ocean release gate
------------------
For 13 El Nino development years, event-only SODA3.15.2 five-day fields are
anchored to the detrended 1980-2024 monthly climatology already used by the
project.  A reduced-gravity-like acceleration proxy is then formed from the
west-to-central SSH drop and the central-Pacific wind-stress anomaly:

    A_pressure = g (SSH_W - SSH_C) / L
    A_wind     = tau_x / (rho H_20)
    A_net      = A_pressure + A_wind

This is deliberately called a forcing-balance *proxy*: nonlinear advection,
friction, meridional pressure gradients and baroclinic structure are not
closed.  Its sign is checked against the actually diagnosed 20 C-relative
eastward heat transport at the Date Line.

Atmospheric coupling gate
-------------------------
For the ten events with external daily ERA5 u10, the five-day central-minus-
western near-surface temperature gradient is tested against the ERA5 zonal-wind
response.  Event-wise leave-one-out validation and event-cluster bootstrap are
used throughout so adjacent pentads are never treated as independent events.
Because SODA3.15.2 is ERA5-forced, this is an external-field consistency check,
not a fully independent forcing validation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CACHE = Path("/private/tmp/codex_soda3_compensation_threshold")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import pearsonr, spearmanr


EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
ERA5_EVENTS = (1982, 1986, 1991, 1997, 2002, 2004, 2015, 2018, 2019, 2023)
HIGHLIGHT_EVENTS = (1997, 2015, 2023)

INPUT_DIR = ROOT / "data/interim/research_2026/soda3_5day_event_transport"
MONTHLY_TRANSPORT = ROOT / "data/derived/research_2026/soda3_warm_transport_longitude_1980_2024.csv"
MONTHLY_D20_SSH = ROOT / "data/derived/research_2026/soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
MONTHLY_PROCESS = ROOT / "data/derived/research_2026/soda3_transition_process_indices_1980_2024.csv"
ERA5_DAILY = ROOT / "data/derived/research_2026/era5_daily_u10_central_pacific_event_years.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_compensation_threshold"
OUT_PDF_DIR = ROOT / "output/pdf"
PENTAD_CSV = DERIVED / "soda3_compensation_threshold_pentads.csv"
SKILL_CSV = DERIVED / "soda3_compensation_threshold_loeo_skill.csv"
COEF_CSV = DERIVED / "soda3_compensation_threshold_loeo_coefficients.csv"
EVENT_CSV = DERIVED / "soda3_compensation_threshold_event_summary.csv"
BOOT_CSV = DERIVED / "soda3_compensation_threshold_bootstrap_summary.csv"
SENSITIVITY_CSV = DERIVED / "soda3_compensation_threshold_region_depth_sensitivity.csv"
DIAG_JSON = DERIVED / "soda3_compensation_threshold_diagnostics.json"
FIGURE_PNG = OUT_DIR / "soda3_compensation_threshold_verification.png"
FIGURE_PDF = OUT_PDF_DIR / "soda3_compensation_threshold_verification.pdf"
EVENT_FIGURE_PNG = OUT_DIR / "soda3_compensation_threshold_event_paths.png"
EVENT_FIGURE_PDF = OUT_PDF_DIR / "soda3_compensation_threshold_event_paths.pdf"
REPORT_MD = OUT_DIR / "SODA3_COMPENSATION_THRESHOLD_RESULT_CN.md"

G = 9.81
RHO0 = 1025.0
EARTH_RADIUS = 6_371_000.0
WEST_LONS = tuple(np.arange(150.0, 171.0, 5.0))
CENTRAL_LONS = tuple(np.arange(190.0, 211.0, 5.0))
WEST_CENTER = float(np.mean(WEST_LONS))
CENTRAL_CENTER = float(np.mean(CENTRAL_LONS))
DISTANCE_M = EARTH_RADIUS * np.deg2rad(CENTRAL_CENTER - WEST_CENTER)
RNG_SEED = 20260803
N_BOOTSTRAP = 6000
N_THRESHOLD_BOOTSTRAP = 1200


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
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 7.4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pieces: list[pd.DataFrame] = []
    for year in EVENTS:
        path = INPUT_DIR / f"soda3_5day_transport_{year}_jan_jun.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        current = pd.read_csv(path, parse_dates=["time"])
        required = {
            "q20_pw",
            "warm_heat_section_gj_per_m",
            "d20_m",
            "ssh_m",
            "sst_c",
            "taux_central_nm2",
            "longitude_e",
        }
        missing = required - set(current.columns)
        if missing:
            raise KeyError(f"{path} lacks {sorted(missing)}")
        if current.duplicated(["time", "longitude_e"]).any():
            raise ValueError(f"Duplicate time-longitude rows in {path}")
        if current["time"].nunique() not in {36, 37}:
            raise ValueError(f"Unexpected pentad count in {path}")
        pieces.append(current)
    five_day = pd.concat(pieces, ignore_index=True).sort_values(["time", "longitude_e"])
    monthly_transport = pd.read_csv(MONTHLY_TRANSPORT, parse_dates=["time"])
    monthly_d20_ssh = pd.read_csv(MONTHLY_D20_SSH, parse_dates=["time"])
    monthly_process = pd.read_csv(MONTHLY_PROCESS, parse_dates=["time"])
    era5 = pd.read_csv(ERA5_DAILY, parse_dates=["date"])
    return five_day, monthly_transport, monthly_d20_ssh, monthly_process, era5


def anchor_longitude_variable(
    frame: pd.DataFrame,
    monthly: pd.DataFrame,
    raw: str,
    monthly_anomaly: str,
    destination: str,
) -> pd.DataFrame:
    within = frame.groupby(["year", "month", "longitude_e"])[raw].transform("mean")
    reference = monthly[["year", "month", "longitude_e", monthly_anomaly]].rename(
        columns={monthly_anomaly: "_monthly_reference"}
    )
    output = frame.merge(
        reference,
        on=["year", "month", "longitude_e"],
        how="left",
        validate="many_to_one",
    )
    if output["_monthly_reference"].isna().any():
        raise ValueError(f"Missing monthly reference for {raw}")
    output[destination] = output[raw] - within + output["_monthly_reference"]
    return output.drop(columns="_monthly_reference")


def anchor_all(
    five_day: pd.DataFrame,
    monthly_transport: pd.DataFrame,
    monthly_d20_ssh: pd.DataFrame,
    monthly_process: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    frame = five_day.copy()
    for raw, monthly_anomaly, destination in (
        ("q20_pw", "q20_pw_anom", "q20_pw_anom"),
        (
            "warm_heat_section_gj_per_m",
            "warm_heat_section_gj_per_m_anom",
            "warm_heat_section_gj_per_m_anom",
        ),
    ):
        frame = anchor_longitude_variable(
            frame, monthly_transport, raw, monthly_anomaly, destination
        )
    for raw, monthly_anomaly, destination in (
        ("d20_m", "d20_m_anom", "d20_m_anom"),
        ("ssh_m", "ssh_m_anom", "ssh_m_anom"),
        ("sst_c", "sst_c_anom", "sst_c_anom"),
    ):
        frame = anchor_longitude_variable(
            frame, monthly_d20_ssh, raw, monthly_anomaly, destination
        )

    stress = (
        frame[["time", "year", "month", "taux_central_nm2"]]
        .drop_duplicates("time")
        .sort_values("time")
    )
    if len(stress) != frame["time"].nunique():
        raise ValueError("Wind stress is not unique per pentad")
    stress["_within"] = stress.groupby(["year", "month"])["taux_central_nm2"].transform("mean")
    reference = monthly_process[["year", "month", "taux_central_nm2_anom"]]
    stress = stress.merge(reference, on=["year", "month"], how="left", validate="many_to_one")
    if stress["taux_central_nm2_anom"].isna().any():
        raise ValueError("Missing monthly wind-stress anomaly reference")
    stress["taux_anom_nm2"] = (
        stress["taux_central_nm2"] - stress["_within"] + stress["taux_central_nm2_anom"]
    )
    frame = frame.drop(columns="taux_central_nm2").merge(
        stress[["time", "taux_central_nm2", "taux_anom_nm2"]],
        on="time",
        validate="many_to_one",
    )

    diagnostics: dict[str, float] = {}
    checks = (
        ("q20_pw_anom", monthly_transport, "q20_pw_anom"),
        ("warm_heat_section_gj_per_m_anom", monthly_transport, "warm_heat_section_gj_per_m_anom"),
        ("d20_m_anom", monthly_d20_ssh, "d20_m_anom"),
        ("ssh_m_anom", monthly_d20_ssh, "ssh_m_anom"),
        ("sst_c_anom", monthly_d20_ssh, "sst_c_anom"),
    )
    for variable, reference_frame, reference_variable in checks:
        reconstructed = frame.groupby(["year", "month", "longitude_e"])[variable].mean()
        target = (
            reference_frame.loc[reference_frame["year"].isin(EVENTS)]
            .set_index(["year", "month", "longitude_e"])[reference_variable]
            .reindex(reconstructed.index)
        )
        diagnostics[f"{variable}_monthly_reconstruction_max_abs_error"] = float(
            np.nanmax(np.abs(reconstructed.to_numpy() - target.to_numpy()))
        )
    stress_reconstructed = stress.groupby(["year", "month"])["taux_anom_nm2"].mean()
    stress_target = (
        monthly_process.loc[monthly_process["year"].isin(EVENTS)]
        .set_index(["year", "month"])["taux_central_nm2_anom"]
        .reindex(stress_reconstructed.index)
    )
    diagnostics["taux_monthly_reconstruction_max_abs_error"] = float(
        np.nanmax(np.abs(stress_reconstructed.to_numpy() - stress_target.to_numpy()))
    )
    return frame.sort_values(["time", "longitude_e"]), diagnostics


def gate_mean(frame: pd.DataFrame, values: str, longitudes: tuple[float, ...]) -> pd.Series:
    return (
        frame.loc[frame["longitude_e"].isin(longitudes)]
        .groupby("time")[values]
        .mean()
    )


def build_pentads(frame: pd.DataFrame, era5: pd.DataFrame) -> pd.DataFrame:
    unique = (
        frame[["time", "year", "month", "day", "taux_central_nm2", "taux_anom_nm2"]]
        .drop_duplicates("time")
        .set_index("time")
        .sort_index()
    )
    unique["ssh_w_anom_m"] = gate_mean(frame, "ssh_m_anom", WEST_LONS)
    unique["ssh_c_anom_m"] = gate_mean(frame, "ssh_m_anom", CENTRAL_LONS)
    unique["d20_wc_raw_m"] = gate_mean(frame, "d20_m", WEST_LONS + CENTRAL_LONS)
    unique["west_warm_section_anom_gj_m"] = gate_mean(
        frame, "warm_heat_section_gj_per_m_anom", WEST_LONS
    )
    unique["sst_w_anom_c"] = gate_mean(frame, "sst_c_anom", WEST_LONS)
    unique["sst_c_anom_c"] = gate_mean(frame, "sst_c_anom", CENTRAL_LONS)
    unique["sst_c_minus_w_anom_c"] = unique["sst_c_anom_c"] - unique["sst_w_anom_c"]
    for longitude in (180.0, 200.0, 220.0):
        current = (
            frame.loc[frame["longitude_e"].eq(longitude)]
            .set_index("time")
            .sort_index()
        )
        suffix = int(longitude)
        unique[f"q20_{suffix}e_raw_pw"] = current["q20_pw"]
        unique[f"q20_{suffix}e_anom_pw"] = current["q20_pw_anom"]
        unique[f"d20_{suffix}e_anom_m"] = current["d20_m_anom"]

    unique["ssh_w_minus_c_anom_m"] = unique["ssh_w_anom_m"] - unique["ssh_c_anom_m"]
    unique["pressure_accel_ms2"] = G * unique["ssh_w_minus_c_anom_m"] / DISTANCE_M
    effective_depth = unique["d20_wc_raw_m"].clip(60.0, 240.0)
    unique["wind_accel_ms2"] = unique["taux_anom_nm2"] / (RHO0 * effective_depth)
    unique["net_accel_ms2"] = unique["pressure_accel_ms2"] + unique["wind_accel_ms2"]
    unique["pressure_accel_1e8_ms2"] = unique["pressure_accel_ms2"] * 1.0e8
    unique["wind_accel_1e8_ms2"] = unique["wind_accel_ms2"] * 1.0e8
    unique["net_accel_1e8_ms2"] = unique["net_accel_ms2"] * 1.0e8
    day_of_year = unique.index.dayofyear.to_numpy(dtype=float)
    unique["season_sin"] = np.sin(2.0 * np.pi * day_of_year / 365.25)
    unique["season_cos"] = np.cos(2.0 * np.pi * day_of_year / 365.25)

    output = unique.reset_index()
    future_parts = []
    for _, event in output.groupby("year", sort=True):
        event = event.sort_values("time").copy()
        event["q180_future10_anom_pw"] = (
            event["q20_180e_anom_pw"].shift(-1) + event["q20_180e_anom_pw"].shift(-2)
        ) / 2.0
        event["q180_positive_now"] = (event["q20_180e_anom_pw"] > 0.0).astype(int)
        event["q180_positive_future10"] = (event["q180_future10_anom_pw"] > 0.0).astype(float)
        event.loc[event["q180_future10_anom_pw"].isna(), "q180_positive_future10"] = np.nan
        future_parts.append(event)
    output = pd.concat(future_parts, ignore_index=True).sort_values("time")

    era5_indexed = era5.set_index("date").sort_index()
    era5_rows = []
    for row in output.itertuples():
        if row.year not in ERA5_EVENTS:
            era5_rows.append((np.nan, np.nan, 0))
            continue
        dates = pd.date_range(row.time, periods=5, freq="D")
        selected = era5_indexed.reindex(dates)
        valid = int(selected["u10_anom_ms"].notna().sum())
        era5_rows.append(
            (
                float(selected["u10_anom_ms"].mean()),
                float(selected["u10_raw_ms"].mean()),
                valid,
            )
        )
    output[["era5_u10_anom_ms", "era5_u10_raw_ms", "era5_daily_count"]] = pd.DataFrame(
        era5_rows, index=output.index
    )
    output["era5_westerly_now"] = np.where(
        output["era5_u10_anom_ms"].notna(),
        (output["era5_u10_anom_ms"] > 0.0).astype(float),
        np.nan,
    )
    return output


def region_depth_sensitivity(anchored: pd.DataFrame, pentads: pd.DataFrame) -> pd.DataFrame:
    """Check that the zero-line result is not an artifact of one box or depth."""
    configurations = {
        "base_W150_170_C190_210": (tuple(np.arange(150.0, 171.0, 5.0)), tuple(np.arange(190.0, 211.0, 5.0))),
        "near_W150_170_C180_200": (tuple(np.arange(150.0, 171.0, 5.0)), tuple(np.arange(180.0, 201.0, 5.0))),
        "eastshift_W155_175_C195_215": (tuple(np.arange(155.0, 176.0, 5.0)), tuple(np.arange(195.0, 216.0, 5.0))),
        "narrow_W150_165_C185_200": (tuple(np.arange(150.0, 166.0, 5.0)), tuple(np.arange(185.0, 201.0, 5.0))),
    }
    base = pentads.set_index("time").sort_index()
    rows: list[dict[str, object]] = []
    for name, (west, central) in configurations.items():
        west_ssh = gate_mean(anchored, "ssh_m_anom", west)
        central_ssh = gate_mean(anchored, "ssh_m_anom", central)
        distance = EARTH_RADIUS * np.deg2rad(float(np.mean(central) - np.mean(west)))
        pressure = G * (west_ssh - central_ssh) / distance
        d20 = gate_mean(anchored, "d20_m", west + central).clip(60.0, 240.0)
        for depth_name, depth in (
            ("D20", d20),
            ("H100m", pd.Series(100.0, index=pressure.index)),
            ("H150m", pd.Series(150.0, index=pressure.index)),
            ("H200m", pd.Series(200.0, index=pressure.index)),
        ):
            current = pd.DataFrame(
                {
                    "pressure": pressure,
                    "wind": base["taux_anom_nm2"] / (RHO0 * depth),
                    "q": base["q20_180e_anom_pw"],
                }
            ).dropna()
            current["net"] = current["pressure"] + current["wind"]
            y = (current["q"] > 0.0).astype(int).to_numpy()
            predicted = (current["net"] > 0.0).astype(int).to_numpy()
            rows.append(
                {
                    "configuration": name,
                    "depth_assumption": depth_name,
                    "west_longitudes_e": " ".join(f"{value:g}" for value in west),
                    "central_longitudes_e": " ".join(f"{value:g}" for value in central),
                    "pressure_q_pearson_r": float(pearsonr(current["pressure"], current["q"]).statistic),
                    "net_q_pearson_r": float(pearsonr(current["net"], current["q"]).statistic),
                    "zero_line_accuracy": float(np.mean(predicted == y)),
                    "zero_line_balanced_accuracy": balanced_accuracy(y, predicted),
                    "n_pentads": len(current),
                }
            )
    return pd.DataFrame(rows)


def event_weights(years: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(years, dtype=int)
    unique, counts = np.unique(values, return_counts=True)
    lookup = {year: 1.0 / count for year, count in zip(unique, counts, strict=True)}
    weights = np.asarray([lookup[year] for year in values], dtype=float)
    return weights / np.mean(weights)


def weighted_mean_std(x: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.average(x, axis=0, weights=weights)
    variance = np.average((x - mean) ** 2, axis=0, weights=weights)
    scale = np.sqrt(np.maximum(variance, 1.0e-12))
    return mean, scale


def sigmoid(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def fit_ridge_logistic(
    x: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    ridge: float = 0.08,
) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), x])

    def objective(beta: np.ndarray) -> tuple[float, np.ndarray]:
        probability = sigmoid(design @ beta)
        eps = 1.0e-12
        loss = -np.sum(weights * (y * np.log(probability + eps) + (1.0 - y) * np.log(1.0 - probability + eps)))
        penalty = 0.5 * ridge * np.sum(beta[1:] ** 2)
        gradient = design.T @ (weights * (probability - y))
        gradient[1:] += ridge * beta[1:]
        return float(loss + penalty), gradient

    result = minimize(
        lambda beta: objective(beta)[0],
        np.zeros(design.shape[1]),
        jac=lambda beta: objective(beta)[1],
        method="L-BFGS-B",
    )
    if not result.success:
        raise RuntimeError(f"Logistic optimization failed: {result.message}")
    return np.asarray(result.x, dtype=float)


def weighted_auc(y: np.ndarray, probability: np.ndarray, weights: np.ndarray) -> float:
    positive = y == 1
    negative = y == 0
    if not positive.any() or not negative.any():
        return float("nan")
    p_scores = probability[positive][:, None]
    n_scores = probability[negative][None, :]
    pair_weight = weights[positive][:, None] * weights[negative][None, :]
    concordance = (p_scores > n_scores).astype(float) + 0.5 * (p_scores == n_scores)
    return float(np.sum(pair_weight * concordance) / np.sum(pair_weight))


MODEL_FEATURES = {
    "season_only": ["season_sin", "season_cos"],
    "wind_only": ["season_sin", "season_cos", "wind_accel_1e8_ms2"],
    "pressure_only": ["season_sin", "season_cos", "pressure_accel_1e8_ms2"],
    "physical_net": ["season_sin", "season_cos", "net_accel_1e8_ms2"],
    "pressure_plus_wind": [
        "season_sin",
        "season_cos",
        "pressure_accel_1e8_ms2",
        "wind_accel_1e8_ms2",
    ],
}


ERA5_MODEL_FEATURES = {
    "era5_wind_only": ["season_sin", "season_cos", "era5_u10_anom_ms"],
    "pressure_plus_era5_wind": [
        "season_sin",
        "season_cos",
        "pressure_accel_1e8_ms2",
        "era5_u10_anom_ms",
    ],
}


COUPLING_FEATURES = {
    "coupling_season_only": ["season_sin", "season_cos"],
    "coupling_sst_gradient": ["season_sin", "season_cos", "sst_c_minus_w_anom_c"],
}


def loeo_logistic(
    frame: pd.DataFrame,
    outcome: str,
    model_features: dict[str, list[str]],
    experiment: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = sorted({outcome} | {feature for features in model_features.values() for feature in features})
    data = frame.dropna(subset=required).copy()
    prediction_rows: list[dict[str, object]] = []
    coefficient_rows: list[dict[str, object]] = []
    for held_year in sorted(data["year"].unique()):
        train = data.loc[data["year"].ne(held_year)]
        test = data.loc[data["year"].eq(held_year)]
        train_weights = event_weights(train["year"])
        for model, features in model_features.items():
            x_train = train[features].to_numpy(dtype=float)
            x_test = test[features].to_numpy(dtype=float)
            mean, scale = weighted_mean_std(x_train, train_weights)
            x_train_z = (x_train - mean) / scale
            x_test_z = (x_test - mean) / scale
            beta = fit_ridge_logistic(
                x_train_z,
                train[outcome].to_numpy(dtype=float),
                train_weights,
            )
            probability = sigmoid(np.column_stack([np.ones(len(test)), x_test_z]) @ beta)
            for row, value in zip(test.itertuples(), probability, strict=True):
                prediction_rows.append(
                    {
                        "experiment": experiment,
                        "outcome": outcome,
                        "time": row.time,
                        "year": int(row.year),
                        "model": model,
                        "observed": int(getattr(row, outcome)),
                        "probability": float(value),
                    }
                )
            coefficient_rows.append(
                {
                    "experiment": experiment,
                    "outcome": outcome,
                    "held_year": int(held_year),
                    "model": model,
                    "feature": "intercept",
                    "standardized_logit_coefficient": float(beta[0]),
                }
            )
            for feature, coefficient in zip(features, beta[1:], strict=True):
                coefficient_rows.append(
                    {
                        "experiment": experiment,
                        "outcome": outcome,
                        "held_year": int(held_year),
                        "model": model,
                        "feature": feature,
                        "standardized_logit_coefficient": float(coefficient),
                    }
                )
    return pd.DataFrame(prediction_rows), pd.DataFrame(coefficient_rows)


def summarize_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (experiment, outcome, model), group in predictions.groupby(
        ["experiment", "outcome", "model"], sort=False
    ):
        weights = event_weights(group["year"])
        y = group["observed"].to_numpy(dtype=float)
        probability = group["probability"].to_numpy(dtype=float)
        rows.append(
            {
                "experiment": experiment,
                "outcome": outcome,
                "model": model,
                "n_events": int(group["year"].nunique()),
                "n_pentads": len(group),
                "event_equal_brier": float(np.average((probability - y) ** 2, weights=weights)),
                "event_equal_auc": weighted_auc(y, probability, weights),
            }
        )
    return pd.DataFrame(rows)


def cluster_bootstrap_brier_delta(
    predictions: pd.DataFrame,
    model: str,
    baseline: str,
    rng: np.random.Generator,
) -> dict[str, float]:
    current = predictions.loc[predictions["model"].isin([model, baseline])]
    pivot = current.pivot_table(
        index=["year", "time", "observed"], columns="model", values="probability"
    ).reset_index()
    event_deltas = []
    for year, event in pivot.groupby("year"):
        y = event["observed"].to_numpy(dtype=float)
        event_deltas.append(
            (
                int(year),
                float(np.mean((event[model].to_numpy() - y) ** 2) - np.mean((event[baseline].to_numpy() - y) ** 2)),
            )
        )
    deltas = np.asarray([value for _, value in event_deltas], dtype=float)
    bootstrap = np.empty(N_BOOTSTRAP, dtype=float)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(deltas), len(deltas))
        bootstrap[index] = float(np.mean(deltas[sample]))
    return {
        "delta_brier": float(np.mean(deltas)),
        "ci_low": float(np.quantile(bootstrap, 0.025)),
        "ci_high": float(np.quantile(bootstrap, 0.975)),
        "n_events_improved": int(np.sum(deltas < 0.0)),
        "n_events": len(deltas),
    }


def cluster_bootstrap_correlation(
    frame: pd.DataFrame,
    x: str,
    y: str,
    events: tuple[int, ...],
    rng: np.random.Generator,
) -> dict[str, float]:
    data = frame.loc[frame["year"].isin(events)].dropna(subset=[x, y]).copy()
    selected_events = sorted(data["year"].unique())
    pearson = float(pearsonr(data[x], data[y]).statistic)
    spearman = float(spearmanr(data[x], data[y]).statistic)
    bootstrap = np.full(N_BOOTSTRAP, np.nan)
    for index in range(N_BOOTSTRAP):
        sampled = rng.choice(selected_events, size=len(selected_events), replace=True)
        pieces = [data.loc[data["year"].eq(year)] for year in sampled]
        current = pd.concat(pieces, ignore_index=True)
        if current[x].nunique() > 1 and current[y].nunique() > 1:
            bootstrap[index] = pearsonr(current[x], current[y]).statistic
    valid = bootstrap[np.isfinite(bootstrap)]
    return {
        "pearson_r": pearson,
        "spearman_r": spearman,
        "ci_low": float(np.quantile(valid, 0.025)),
        "ci_high": float(np.quantile(valid, 0.975)),
        "n_events": len(selected_events),
        "n_pentads": len(data),
    }


def balanced_accuracy(y: np.ndarray, predicted: np.ndarray) -> float:
    positive = y == 1
    negative = y == 0
    sensitivity = np.mean(predicted[positive] == 1) if positive.any() else np.nan
    specificity = np.mean(predicted[negative] == 0) if negative.any() else np.nan
    return float(np.nanmean([sensitivity, specificity]))


def first_persistent(time: pd.Series, condition: pd.Series, run: int = 2) -> str:
    values = condition.fillna(False).to_numpy(dtype=bool)
    dates = pd.DatetimeIndex(time)
    for index in range(0, len(values) - run + 1):
        if values[index : index + run].all():
            return dates[index].strftime("%Y-%m-%d")
    return ""


def event_summary(frame: pd.DataFrame, coupling_threshold: float) -> pd.DataFrame:
    rows = []
    for year, event in frame.groupby("year", sort=True):
        event = event.sort_values("time")
        rows.append(
            {
                "event_year": int(year),
                "mean_west_warm_section_anom_gj_m": float(event["west_warm_section_anom_gj_m"].mean()),
                "mean_pressure_accel_1e8_ms2": float(event["pressure_accel_1e8_ms2"].mean()),
                "mean_wind_accel_1e8_ms2": float(event["wind_accel_1e8_ms2"].mean()),
                "mean_net_accel_1e8_ms2": float(event["net_accel_1e8_ms2"].mean()),
                "fraction_net_positive": float((event["net_accel_ms2"] > 0.0).mean()),
                "fraction_q180_anom_positive": float((event["q20_180e_anom_pw"] > 0.0).mean()),
                "first_two_pentad_net_positive": first_persistent(event["time"], event["net_accel_ms2"] > 0.0),
                "first_two_pentad_q180_positive": first_persistent(event["time"], event["q20_180e_anom_pw"] > 0.0),
                "mean_era5_u10_anom_ms": float(event["era5_u10_anom_ms"].mean()) if event["era5_u10_anom_ms"].notna().any() else np.nan,
                "first_coupling_gate": first_persistent(
                    event["time"],
                    (event["sst_c_minus_w_anom_c"] > coupling_threshold)
                    & (event["era5_u10_anom_ms"] > 0.0),
                ),
            }
        )
    return pd.DataFrame(rows)


def fit_coupling_threshold(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, float]:
    data = frame.loc[frame["year"].isin(ERA5_EVENTS)].dropna(
        subset=["sst_c_minus_w_anom_c", "era5_westerly_now"]
    )
    weights = event_weights(data["year"])
    x = data[["sst_c_minus_w_anom_c"]].to_numpy(dtype=float)
    mean, scale = weighted_mean_std(x, weights)
    beta = fit_ridge_logistic((x - mean) / scale, data["era5_westerly_now"].to_numpy(dtype=float), weights)
    raw_slope = beta[1] / scale[0]
    raw_intercept = beta[0] - beta[1] * mean[0] / scale[0]
    threshold = -raw_intercept / raw_slope if abs(raw_slope) > 1.0e-10 else np.nan

    events = sorted(data["year"].unique())
    samples = np.full(N_THRESHOLD_BOOTSTRAP, np.nan)
    slopes = np.full(N_THRESHOLD_BOOTSTRAP, np.nan)
    for index in range(N_THRESHOLD_BOOTSTRAP):
        selected = rng.choice(events, len(events), replace=True)
        pieces = []
        for sample_id, year in enumerate(selected):
            current = data.loc[data["year"].eq(year)].copy()
            current["_sample_event"] = sample_id
            pieces.append(current)
        boot = pd.concat(pieces, ignore_index=True)
        boot_weights = event_weights(boot["_sample_event"])
        bx = boot[["sst_c_minus_w_anom_c"]].to_numpy(dtype=float)
        bmean, bscale = weighted_mean_std(bx, boot_weights)
        by = boot["era5_westerly_now"].to_numpy(dtype=float)
        if np.unique(by).size < 2:
            continue
        bbeta = fit_ridge_logistic((bx - bmean) / bscale, by, boot_weights)
        bslope = bbeta[1] / bscale[0]
        bintercept = bbeta[0] - bbeta[1] * bmean[0] / bscale[0]
        slopes[index] = bslope
        if abs(bslope) > 1.0e-10:
            samples[index] = -bintercept / bslope
    valid = samples[np.isfinite(samples) & (np.abs(samples) < 5.0)]
    valid_slopes = slopes[np.isfinite(slopes)]
    return {
        "threshold_c": float(threshold),
        "threshold_ci_low_c": float(np.quantile(valid, 0.025)) if len(valid) else np.nan,
        "threshold_ci_high_c": float(np.quantile(valid, 0.975)) if len(valid) else np.nan,
        "raw_logit_slope_per_c": float(raw_slope),
        "positive_slope_bootstrap_fraction": float(np.mean(valid_slopes > 0.0)),
        "n_events": len(events),
        "n_pentads": len(data),
    }


def plot_main(frame: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.4, 8.2))
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.11, top=0.91, wspace=0.25, hspace=0.30)

    colors = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}
    ordinary = ~frame["year"].isin(HIGHLIGHT_EVENTS)
    axes[0, 0].scatter(
        frame.loc[ordinary, "pressure_accel_1e8_ms2"],
        frame.loc[ordinary, "wind_accel_1e8_ms2"],
        c=frame.loc[ordinary, "q20_180e_anom_pw"],
        cmap="RdBu_r",
        vmin=-1.2,
        vmax=1.2,
        s=14,
        alpha=0.36,
        linewidth=0,
    )
    for year in HIGHLIGHT_EVENTS:
        selected = frame.loc[frame["year"].eq(year)]
        axes[0, 0].plot(
            selected["pressure_accel_1e8_ms2"],
            selected["wind_accel_1e8_ms2"],
            color=colors[year],
            lw=1.0,
            alpha=0.75,
            label=str(year),
        )
        axes[0, 0].scatter(
            selected["pressure_accel_1e8_ms2"],
            selected["wind_accel_1e8_ms2"],
            c=selected["q20_180e_anom_pw"],
            cmap="RdBu_r",
            vmin=-1.2,
            vmax=1.2,
            s=24,
            edgecolor=colors[year],
            linewidth=0.55,
            zorder=3,
        )
    limits = np.nanpercentile(
        np.abs(frame[["pressure_accel_1e8_ms2", "wind_accel_1e8_ms2"]].to_numpy()), 99
    )
    xline = np.linspace(-limits, limits, 200)
    axes[0, 0].plot(xline, -xline, color="#111111", ls="--", lw=1.2, label="A_net = 0")
    axes[0, 0].axhline(0.0, color="#888888", lw=0.6)
    axes[0, 0].axvline(0.0, color="#888888", lw=0.6)
    axes[0, 0].set_xlabel("Eastward SSH-pressure acceleration  (10⁻⁸ m s⁻²)")
    axes[0, 0].set_ylabel("Wind-stress acceleration  (10⁻⁸ m s⁻²)")
    axes[0, 0].set_title("(a) Ocean-force balance vs Date-Line heat transport", loc="left", fontweight="bold")
    axes[0, 0].legend(frameon=False, ncol=4, loc="upper center")

    mechanism = frame.dropna(subset=["net_accel_1e8_ms2", "q180_positive_now"]).copy()
    mechanism["net_bin"] = pd.qcut(mechanism["net_accel_1e8_ms2"], 8, duplicates="drop")
    binned = mechanism.groupby("net_bin", observed=True).agg(
        net=("net_accel_1e8_ms2", "mean"),
        release=("q180_positive_now", "mean"),
        q=("q20_180e_anom_pw", "mean"),
        n=("q180_positive_now", "size"),
    )
    axes[0, 1].plot(binned["net"], binned["release"], marker="o", color="#6B3FA0", lw=1.8)
    axes[0, 1].axvline(0.0, color="#111111", ls="--", lw=1.1)
    axes[0, 1].axhline(0.5, color="#888888", ls=":", lw=0.8)
    axes[0, 1].set_ylim(-0.04, 1.04)
    axes[0, 1].set_xlabel("Net acceleration proxy  (10⁻⁸ m s⁻²)")
    axes[0, 1].set_ylabel("Fraction with positive Date-Line Q20 anomaly")
    axes[0, 1].set_title("(b) Release frequency across the proposed balance", loc="left", fontweight="bold")
    for x, y, n in zip(binned["net"], binned["release"], binned["n"], strict=True):
        axes[0, 1].annotate(f"n={int(n)}", (x, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=6.6)

    independent = frame.loc[frame["year"].isin(ERA5_EVENTS)].dropna(subset=["era5_u10_anom_ms"])
    scatter = axes[1, 0].scatter(
        independent["pressure_accel_1e8_ms2"],
        independent["era5_u10_anom_ms"],
        c=independent["q20_180e_anom_pw"],
        cmap="RdBu_r",
        vmin=-1.2,
        vmax=1.2,
        s=19,
        alpha=0.62,
        linewidth=0,
    )
    axes[1, 0].axhline(0.0, color="#555555", lw=0.7)
    axes[1, 0].axvline(0.0, color="#555555", lw=0.7)
    axes[1, 0].set_xlabel("SODA3 SSH-pressure acceleration  (10⁻⁸ m s⁻²)")
    axes[1, 0].set_ylabel("External ERA5 u10 anomaly  (m s⁻¹)")
    axes[1, 0].set_title("(c) External ERA5-wind sensitivity (10 events)", loc="left", fontweight="bold")
    colorbar = figure.colorbar(scatter, ax=axes[1, 0], fraction=0.046, pad=0.03)
    colorbar.set_label("Date-Line Q20 anomaly (PW; panels a, c)")

    coupling = independent.dropna(subset=["sst_c_minus_w_anom_c"])
    for year, event in coupling.groupby("year"):
        color = colors.get(int(year), "#A0A0A0")
        alpha = 0.80 if int(year) in HIGHLIGHT_EVENTS else 0.35
        axes[1, 1].scatter(
            event["sst_c_minus_w_anom_c"],
            event["era5_u10_anom_ms"],
            s=21 if int(year) in HIGHLIGHT_EVENTS else 14,
            color=color,
            alpha=alpha,
            linewidth=0,
        )
    threshold = float(diagnostics["coupling_threshold"]["threshold_c"])
    if np.isfinite(threshold):
        axes[1, 1].axvline(threshold, color="#6B3FA0", ls="--", lw=1.2, label=f"empirical P=0.5: {threshold:+.2f} °C")
    axes[1, 1].axhline(0.0, color="#555555", lw=0.7)
    axes[1, 1].axvline(0.0, color="#999999", lw=0.6)
    axes[1, 1].set_xlabel("Central-minus-western 5-m temperature anomaly (°C)")
    axes[1, 1].set_ylabel("ERA5 central-Pacific u10 anomaly (m s⁻¹)")
    axes[1, 1].set_title("(d) Surface-temperature-gradient gate for westerlies", loc="left", fontweight="bold")
    if np.isfinite(threshold):
        axes[1, 1].legend(frameon=False, loc="upper left")

    figure.suptitle(
        "SODA3 five-day verification of the warm-water / wind compensation hypothesis",
        fontsize=13.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "Anomalies: detrended 1980–2024 calendar-month baseline. ERA5 u10 is external, but SODA3.15.2 is ERA5-forced. "
        "The acceleration balance omits friction and nonlinear advection.",
        ha="center",
        fontsize=7.2,
        color="#555555",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def plot_event_paths(frame: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    setup_style()
    figure, axes = plt.subplots(3, 2, figsize=(11.2, 8.4), sharex="row")
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.11, top=0.91, wspace=0.20, hspace=0.28)
    colors = {
        "pressure": "#B7352D",
        "wind": "#176B87",
        "net": "#222222",
        "transport": "#6B3FA0",
        "sst": "#D97706",
        "era5": "#15803D",
    }
    threshold = float(diagnostics["coupling_threshold"]["threshold_c"])
    for row, year in enumerate(HIGHLIGHT_EVENTS):
        event = frame.loc[frame["year"].eq(year)].sort_values("time")
        dates = pd.DatetimeIndex(event["time"])
        axes[row, 0].plot(dates, event["pressure_accel_1e8_ms2"], color=colors["pressure"], lw=1.35, label="SSH pressure")
        axes[row, 0].plot(dates, event["wind_accel_1e8_ms2"], color=colors["wind"], lw=1.35, label="wind stress")
        axes[row, 0].plot(dates, event["net_accel_1e8_ms2"], color=colors["net"], lw=1.6, label="net proxy")
        axes[row, 0].axhline(0.0, color="#777777", lw=0.7)
        twin = axes[row, 0].twinx()
        twin.plot(dates, event["q20_180e_anom_pw"], color=colors["transport"], lw=1.05, alpha=0.78, label="Q20 at 180°")
        twin.axhline(0.0, color=colors["transport"], lw=0.55, alpha=0.45)
        axes[row, 0].set_ylabel(f"{year}\naccel. (10⁻⁸ m s⁻²)")
        twin.set_ylabel("")
        twin.tick_params(axis="y", colors=colors["transport"])

        axes[row, 1].plot(dates, event["sst_c_minus_w_anom_c"], color=colors["sst"], lw=1.45, label="SODA3 C−W T5")
        if np.isfinite(threshold):
            axes[row, 1].axhline(threshold, color=colors["sst"], ls="--", lw=0.8)
        axes[row, 1].axhline(0.0, color="#777777", lw=0.7)
        twin2 = axes[row, 1].twinx()
        twin2.plot(dates, event["era5_u10_anom_ms"], color=colors["era5"], lw=1.25, label="ERA5 u10")
        twin2.axhline(0.0, color=colors["era5"], lw=0.55, alpha=0.45)
        axes[row, 1].set_ylabel("")
        axes[row, 1].tick_params(axis="y", colors=colors["sst"])
        twin2.set_ylabel("ERA5 u10 anomaly (m s⁻¹)", color=colors["era5"])

        for axis in axes[row]:
            axis.xaxis.set_major_locator(mdates.MonthLocator())
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
            axis.grid(axis="x", color="#E2E2E2", lw=0.5)
    axes[0, 0].set_title("(a) Ocean release balance and observed Date-Line heat transport", loc="left", fontweight="bold")
    axes[0, 1].set_title("(b) Atmospheric gate: surface gradient and external ERA5 wind", loc="left", fontweight="bold")
    left_handles, left_labels = axes[0, 0].get_legend_handles_labels()
    q_handle = Line2D([], [], color=colors["transport"], lw=1.1, label="Q20 at 180° (PW)")
    axes[0, 0].legend(left_handles + [q_handle], left_labels + ["Q20 at 180° (PW)"], frameon=False, ncol=4, loc="upper left")
    t_handle = Line2D([], [], color=colors["sst"], lw=1.4, label="SODA3 C−W T5 (°C)")
    axes[0, 1].legend(handles=[t_handle], frameon=False, loc="upper left")
    axes[-1, 0].set_xlabel("Developing-year month")
    axes[-1, 1].set_xlabel("Developing-year month")
    figure.suptitle("Contrasting transition paths: 1997, 2015 and 2023", fontsize=13.0, fontweight="bold", y=0.965)
    figure.text(
        0.5,
        0.025,
        "Positive acceleration and Q20 indicate eastward release; positive ERA5 u10 indicates anomalous westerlies. "
        "The dashed orange line is an empirical, not universal, coupling threshold.",
        ha="center",
        fontsize=7.2,
        color="#555555",
    )
    figure.savefig(EVENT_FIGURE_PNG, bbox_inches="tight")
    figure.savefig(EVENT_FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    rng = np.random.default_rng(RNG_SEED)
    five_day, monthly_transport, monthly_d20_ssh, monthly_process, era5 = read_inputs()
    anchored, qa = anchor_all(five_day, monthly_transport, monthly_d20_ssh, monthly_process)
    pentads = build_pentads(anchored, era5)

    predictions = []
    coefficients = []
    for outcome, experiment in (
        ("q180_positive_now", "soda_internal_contemporaneous"),
        ("q180_positive_future10", "soda_internal_future10"),
    ):
        current_predictions, current_coefficients = loeo_logistic(
            pentads, outcome, MODEL_FEATURES, experiment
        )
        predictions.append(current_predictions)
        coefficients.append(current_coefficients)
    era5_predictions, era5_coefficients = loeo_logistic(
        pentads.loc[pentads["year"].isin(ERA5_EVENTS)],
        "q180_positive_future10",
        ERA5_MODEL_FEATURES,
        "era5_independent_future10",
    )
    coupling_predictions, coupling_coefficients = loeo_logistic(
        pentads.loc[pentads["year"].isin(ERA5_EVENTS)],
        "era5_westerly_now",
        COUPLING_FEATURES,
        "era5_atmospheric_coupling",
    )
    predictions.extend([era5_predictions, coupling_predictions])
    coefficients.extend([era5_coefficients, coupling_coefficients])
    all_predictions = pd.concat(predictions, ignore_index=True)
    all_coefficients = pd.concat(coefficients, ignore_index=True)
    skill = summarize_predictions(all_predictions)

    bootstrap_rows: list[dict[str, object]] = []
    comparisons = (
        ("soda_internal_contemporaneous", "pressure_plus_wind", "wind_only"),
        ("soda_internal_contemporaneous", "physical_net", "wind_only"),
        ("soda_internal_future10", "pressure_plus_wind", "wind_only"),
        ("soda_internal_future10", "physical_net", "wind_only"),
        ("era5_independent_future10", "pressure_plus_era5_wind", "era5_wind_only"),
        ("era5_atmospheric_coupling", "coupling_sst_gradient", "coupling_season_only"),
    )
    for experiment, model, baseline in comparisons:
        current = all_predictions.loc[all_predictions["experiment"].eq(experiment)]
        result = cluster_bootstrap_brier_delta(current, model, baseline, rng)
        bootstrap_rows.append(
            {
                "test": "brier_delta",
                "experiment": experiment,
                "model": model,
                "baseline": baseline,
                **result,
            }
        )

    correlations = {
        "west_heat_vs_pressure": cluster_bootstrap_correlation(
            pentads,
            "west_warm_section_anom_gj_m",
            "pressure_accel_1e8_ms2",
            EVENTS,
            rng,
        ),
        "west_heat_vs_soda_wind": cluster_bootstrap_correlation(
            pentads,
            "west_warm_section_anom_gj_m",
            "wind_accel_1e8_ms2",
            EVENTS,
            rng,
        ),
        "west_heat_vs_era5_wind": cluster_bootstrap_correlation(
            pentads,
            "west_warm_section_anom_gj_m",
            "era5_u10_anom_ms",
            ERA5_EVENTS,
            rng,
        ),
        "net_accel_vs_q180": cluster_bootstrap_correlation(
            pentads,
            "net_accel_1e8_ms2",
            "q20_180e_anom_pw",
            EVENTS,
            rng,
        ),
        "sst_gradient_vs_era5_wind": cluster_bootstrap_correlation(
            pentads,
            "sst_c_minus_w_anom_c",
            "era5_u10_anom_ms",
            ERA5_EVENTS,
            rng,
        ),
    }
    for name, result in correlations.items():
        bootstrap_rows.append(
            {
                "test": "cluster_correlation",
                "experiment": name,
                "model": "",
                "baseline": "",
                "delta_brier": np.nan,
                "ci_low": result["ci_low"],
                "ci_high": result["ci_high"],
                "n_events_improved": np.nan,
                "n_events": result["n_events"],
                "pearson_r": result["pearson_r"],
                "spearman_r": result["spearman_r"],
                "n_pentads": result["n_pentads"],
            }
        )
    bootstrap = pd.DataFrame(bootstrap_rows)

    coupling_threshold = fit_coupling_threshold(pentads, rng)
    event_table = event_summary(pentads, coupling_threshold["threshold_c"])
    sensitivity = region_depth_sensitivity(anchored, pentads)

    mechanism = pentads.dropna(subset=["q180_positive_now"])
    direct_sign = (mechanism["net_accel_ms2"] > 0.0).astype(int).to_numpy()
    observed = mechanism["q180_positive_now"].to_numpy(dtype=int)
    diagnostics: dict[str, object] = {
        "baseline": "1980-2024 calendar-month linear detrended",
        "events": list(EVENTS),
        "era5_events": list(ERA5_EVENTS),
        "west_longitudes_e": list(WEST_LONS),
        "central_longitudes_e": list(CENTRAL_LONS),
        "distance_m": DISTANCE_M,
        "n_pentads": int(len(pentads)),
        "n_era5_pentads": int(pentads["era5_u10_anom_ms"].notna().sum()),
        "direct_zero_balance_accuracy": float(np.mean(direct_sign == observed)),
        "direct_zero_balance_balanced_accuracy": balanced_accuracy(observed, direct_sign),
        "direct_zero_balance_positive_fraction": float(np.mean(direct_sign)),
        "observed_q180_positive_fraction": float(np.mean(observed)),
        "coupling_threshold": coupling_threshold,
        "correlations": correlations,
        "sensitivity": {
            "net_q_r_min": float(sensitivity["net_q_pearson_r"].min()),
            "net_q_r_max": float(sensitivity["net_q_pearson_r"].max()),
            "zero_line_balanced_accuracy_min": float(sensitivity["zero_line_balanced_accuracy"].min()),
            "zero_line_balanced_accuracy_max": float(sensitivity["zero_line_balanced_accuracy"].max()),
        },
        "quality_control": qa,
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pentads.to_csv(PENTAD_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    all_coefficients.to_csv(COEF_CSV, index=False)
    event_table.to_csv(EVENT_CSV, index=False)
    bootstrap.to_csv(BOOT_CSV, index=False)
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)
    DIAG_JSON.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")

    plot_main(pentads, diagnostics)
    plot_event_paths(pentads, diagnostics)

    def skill_value(experiment: str, model: str, column: str = "event_equal_brier") -> float:
        selected = skill.loc[skill["experiment"].eq(experiment) & skill["model"].eq(model), column]
        return float(selected.iloc[0])

    def comparison_value(experiment: str, model: str) -> pd.Series:
        selected = bootstrap.loc[
            bootstrap["test"].eq("brier_delta")
            & bootstrap["experiment"].eq(experiment)
            & bootstrap["model"].eq(model)
        ]
        return selected.iloc[0]

    now_add = comparison_value("soda_internal_contemporaneous", "pressure_plus_wind")
    future_add = comparison_value("soda_internal_future10", "pressure_plus_wind")
    era5_add = comparison_value("era5_independent_future10", "pressure_plus_era5_wind")
    coupling_add = comparison_value("era5_atmospheric_coupling", "coupling_sst_gradient")
    p_sign = all_coefficients.loc[
        all_coefficients["experiment"].eq("soda_internal_future10")
        & all_coefficients["model"].eq("pressure_plus_wind")
        & all_coefficients["feature"].eq("pressure_accel_1e8_ms2"),
        "standardized_logit_coefficient",
    ]
    w_sign = all_coefficients.loc[
        all_coefficients["experiment"].eq("soda_internal_future10")
        & all_coefficients["model"].eq("pressure_plus_wind")
        & all_coefficients["feature"].eq("wind_accel_1e8_ms2"),
        "standardized_logit_coefficient",
    ]

    report = f"""# SODA3西部暖水—风应力相抵消临界点验证

## 结论先行

本次检验支持“存在竞争”这个物理框架，但**没有支持一个可直接使用的、固定的零净动力临界点**。

- 西部暖层截面异常与向东SSH压力梯度的相关为 `{correlations['west_heat_vs_pressure']['pearson_r']:+.2f}`，事件聚类95%区间 `[{correlations['west_heat_vs_pressure']['ci_low']:+.2f}, {correlations['west_heat_vs_pressure']['ci_high']:+.2f}]`。
- 西部暖层与SODA3风应力异常的相关为 `{correlations['west_heat_vs_soda_wind']['pearson_r']:+.2f}`；与外部ERA5风异常的相关为 `{correlations['west_heat_vs_era5_wind']['pearson_r']:+.2f}`，区间 `[{correlations['west_heat_vs_era5_wind']['ci_low']:+.2f}, {correlations['west_heat_vs_era5_wind']['ci_high']:+.2f}]`。
- 净动力代理与日界线Q20异常的相关为 `{correlations['net_accel_vs_q180']['pearson_r']:+.2f}`，区间 `[{correlations['net_accel_vs_q180']['ci_low']:+.2f}, {correlations['net_accel_vs_q180']['ci_high']:+.2f}]`。
- 直接以 `A_net>0` 判定日界线Q20异常为正，平衡准确率只有 `{diagnostics['direct_zero_balance_balanced_accuracy']:.3f}`。这说明摩擦、平流、Kelvin波相位和暖量位置不能忽略。
- 改变东西箱位置并把有效深度改为100、150、200 m后，净动力—Q20相关范围为 `{diagnostics['sensitivity']['net_q_r_min']:+.2f}`—`{diagnostics['sensitivity']['net_q_r_max']:+.2f}`，零线平衡准确率范围为 `{diagnostics['sensitivity']['zero_line_balanced_accuracy_min']:.3f}`—`{diagnostics['sensitivity']['zero_line_balanced_accuracy_max']:.3f}`。

因此，资料支持的是**临界带/分界面**，而不是“西太平洋OHC达到某个数值就必然抵消”的单一阈值。

## 海洋释放门

使用13次暖事件、1—6月五日资料。压力项由150°—170°E与190°—210°E的SSH异常差计算；风项为180°—140°W的SODA3风应力异常除以20°C暖层有效深度。实际响应为日界线20°C相对热输送Q20。

### 同期机制识别

- 仅风模型Brier：`{skill_value('soda_internal_contemporaneous', 'wind_only'):.4f}`。
- 压力+风模型Brier：`{skill_value('soda_internal_contemporaneous', 'pressure_plus_wind'):.4f}`。
- 相对仅风变化：`{now_add['delta_brier']:+.4f}`，事件聚类95%区间 `[{now_add['ci_low']:+.4f}, {now_add['ci_high']:+.4f}]`。

### 提前10日外推

- 仅风模型Brier：`{skill_value('soda_internal_future10', 'wind_only'):.4f}`。
- 压力+风模型Brier：`{skill_value('soda_internal_future10', 'pressure_plus_wind'):.4f}`。
- 相对仅风变化：`{future_add['delta_brier']:+.4f}`，95%区间 `[{future_add['ci_low']:+.4f}, {future_add['ci_high']:+.4f}]`。
- 压力项在 `{100.0 * np.mean(p_sign > 0.0):.0f}%` 的留一折中为正，风项在 `{100.0 * np.mean(w_sign > 0.0):.0f}%` 的留一折中为正。

## 外部ERA5一致性复核

十个事件用ERA5逐日10 m纬向风替换SODA3风应力。预测未来10日日界线Q20正异常。需要注意，SODA3.15.2使用ERA5大气强迫，所以这属于外部场一致性复核，而不是完全独立的风强迫验证。

- ERA5仅风Brier：`{skill_value('era5_independent_future10', 'era5_wind_only'):.4f}`。
- 加入SODA3压力梯度后Brier：`{skill_value('era5_independent_future10', 'pressure_plus_era5_wind'):.4f}`。
- Brier变化：`{era5_add['delta_brier']:+.4f}`，95%区间 `[{era5_add['ci_low']:+.4f}, {era5_add['ci_high']:+.4f}]`。

只有当外部资料复核也稳定改善，并进一步得到TAO等独立观测支持时，才可把“压力克服风阻力”写成可移植预测门；否则它只能作为机制图像。

## 第二道大气耦合门

五日中央减西部近表层温度异常与ERA5 u10的相关为 `{correlations['sst_gradient_vs_era5_wind']['pearson_r']:+.2f}`，事件聚类95%区间 `[{correlations['sst_gradient_vs_era5_wind']['ci_low']:+.2f}, {correlations['sst_gradient_vs_era5_wind']['ci_high']:+.2f}]`。

- 仅季节模型Brier：`{skill_value('era5_atmospheric_coupling', 'coupling_season_only'):.4f}`。
- 加入温度梯度Brier：`{skill_value('era5_atmospheric_coupling', 'coupling_sst_gradient'):.4f}`。
- Brier变化：`{coupling_add['delta_brier']:+.4f}`，95%区间 `[{coupling_add['ci_low']:+.4f}, {coupling_add['ci_high']:+.4f}]`。
- 经验50%西风概率阈值为 `{coupling_threshold['threshold_c']:+.2f} °C`，事件自助区间 `[{coupling_threshold['threshold_ci_low_c']:+.2f}, {coupling_threshold['threshold_ci_high_c']:+.2f}] °C`；斜率为正的自助样本比例 `{100.0 * coupling_threshold['positive_slope_bootstrap_fraction']:.1f}%`。

如果阈值区间很宽或跨越不合理范围，就不能把该数值当作普适常数，只能把温度梯度视作概率性门。

## 科学判断

1. “西部暖水既增加东向释放势能，又可能维持不利风场”的双重作用可以分开检验；不能把暖量本身直接当作风的机械原因。
2. 海洋释放首先取决于压力项与风项的竞争，但零和线不是完整动力临界点。
3. 即使暖量已经东传，仍需中央—西部表面温度梯度足以促使对流和西风东移，才能完成第二道大气门。
4. 本结果是再分析观测约束下的诊断验证，不是因果扰动实验。严格因果仍需要固定海洋初态、单独改变风应力或西部热含量的敏感性试验。

## 输出

- 主图：`{FIGURE_PDF}`
- 1997/2015/2023路径图：`{EVENT_FIGURE_PDF}`
- 五日诊断表：`{PENTAD_CSV}`
- 留一评分：`{SKILL_CSV}`
- 事件摘要：`{EVENT_CSV}`
- 自助检验：`{BOOT_CSV}`
- 区域与有效深度敏感性：`{SENSITIVITY_CSV}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
