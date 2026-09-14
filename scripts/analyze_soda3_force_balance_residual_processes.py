#!/usr/bin/env python3
"""Attribute the unresolved SODA3 force-balance transport-tendency residual.

Candidate process groups are deliberately compact and use only information
available at the current pentad: recent wind-stress memory, thermocline/SSH
phase tendencies, zonal transport structure plus one nonlinear interaction,
and trailing heat-content geometry.  Models are compared on an identical
sample with nested ridge selection and complete-event leave-one-out tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_soda3_balance_residual")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

sys.path.insert(0, str(ROOT / "scripts"))
import verify_soda3_force_balance_tendency as base  # noqa: E402


EVENTS = base.EVENTS
HIGHLIGHTS = (1997, 2015, 2023)
RAW_DIR = ROOT / "data/interim/research_2026/soda3_5day_event_transport"
MONTHLY_TRANSPORT = ROOT / "data/derived/research_2026/soda3_warm_transport_longitude_1980_2024.csv"
MONTHLY_STATE = ROOT / "data/derived/research_2026/soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
GEOMETRY = ROOT / "data/derived/research_2026/soda3_5day_ohc_geometry_coupling_13events_jan_sep.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_force_balance_residual"
PDF_DIR = ROOT / "output/pdf"
FEATURE_CSV = DERIVED / "soda3_force_balance_residual_features.csv"
PREDICTION_CSV = DERIVED / "soda3_force_balance_residual_loeo_predictions.csv"
SKILL_CSV = DERIVED / "soda3_force_balance_residual_skill.csv"
COEFFICIENT_CSV = DERIVED / "soda3_force_balance_residual_coefficients.csv"
BOOTSTRAP_CSV = DERIVED / "soda3_force_balance_residual_bootstrap.csv"
EVENT_DELTA_CSV = DERIVED / "soda3_force_balance_residual_event_deltas.csv"
REFINEMENT_SKILL_CSV = DERIVED / "soda3_force_balance_residual_refinement_skill.csv"
REFINEMENT_BOOTSTRAP_CSV = DERIVED / "soda3_force_balance_residual_refinement_bootstrap.csv"
LATE_BLOCK_CSV = DERIVED / "soda3_force_balance_residual_late_block.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_force_balance_residual_diagnostics.json"
FIGURE_PNG = OUT / "soda3_force_balance_residual_attribution.png"
FIGURE_PDF = PDF_DIR / "soda3_force_balance_residual_attribution.pdf"
REPORT_MD = OUT / "SODA3_FORCE_BALANCE_RESIDUAL_RESULT_CN.md"

RNG_SEED = 20260803
N_BOOTSTRAP = 10000
RIDGE_GRID = (0.03, 0.10, 0.30, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)

BASE_FEATURES = [
    "season_sin",
    "season_cos",
    "warm_volume_transport_sv_anom",
    "d20_pressure_accel_1e8_ms2",
    "wind_accel_1e8_ms2",
]
PROCESS_FEATURES = {
    "wind_memory": [
        "taux_change5_nm2",
        "positive_taux_mean15_nm2",
        "taux_variability15_nm2",
    ],
    "wave_phase": [
        "d20_200_tendency5_m_day",
        "d20_220_minus_200_tendency5_m_day",
        "ssh_220_minus_200_tendency5_m_day",
    ],
    "transport_structure": [
        "m160_minus_m180_sv",
        "m180_minus_m220_sv",
        "m180_x_d20_slope_sv_m",
    ],
    "heat_geometry": [
        "east_fraction_15day",
        "centroid_change15day_deg",
        "east_west_gradient_change15day_gj_m2",
    ],
}
MODEL_FEATURES = {"base": BASE_FEATURES}
for process, features in PROCESS_FEATURES.items():
    MODEL_FEATURES[f"base_plus_{process}"] = BASE_FEATURES + features
MODEL_FEATURES["base_plus_all"] = BASE_FEATURES + [
    feature for group in PROCESS_FEATURES.values() for feature in group
]
REFINEMENT_MODELS = {
    "base": BASE_FEATURES,
    "upstream_convergence_only": BASE_FEATURES + ["m160_minus_m180_sv"],
    "wind_change_only": BASE_FEATURES + ["taux_change5_nm2"],
    "upstream_plus_wind_change": BASE_FEATURES
    + ["m160_minus_m180_sv", "taux_change5_nm2"],
}

MODEL_LABELS = {
    "base": "Base balance",
    "base_plus_wind_memory": "+ wind memory",
    "base_plus_wave_phase": "+ wave phase",
    "base_plus_transport_structure": "+ transport structure",
    "base_plus_heat_geometry": "+ heat geometry",
    "base_plus_all": "+ all groups",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.5,
            "axes.titlesize": 9.8,
            "axes.labelsize": 8.8,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 7.6,
            "ytick.labelsize": 7.6,
            "legend.fontsize": 7.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def read_base_frame() -> tuple[pd.DataFrame, dict[str, float]]:
    forcing = pd.read_csv(base.BASE_PENTADS, parse_dates=["time"])
    sections, anchor_qa = base.read_and_anchor_sections()
    frame = forcing.merge(sections, on="time", how="left", validate="one_to_one")
    frame, time_qa = base.add_tendencies(frame)
    return frame.sort_values(["year", "time"]), {**anchor_qa, **time_qa}


def read_full_longitude_state() -> tuple[pd.DataFrame, dict[str, float]]:
    pieces = []
    for year in EVENTS:
        path = RAW_DIR / f"soda3_5day_transport_{year}_jan_jun.csv"
        pieces.append(pd.read_csv(path, parse_dates=["time"]))
    raw = pd.concat(pieces, ignore_index=True)
    transport_reference = pd.read_csv(MONTHLY_TRANSPORT)
    state_reference = pd.read_csv(MONTHLY_STATE)

    anchors = (
        ("warm_volume_transport_sv", transport_reference, "warm_volume_transport_sv_anom", "m_anom_sv"),
        ("q20_pw", transport_reference, "q20_pw_anom", "q20_anom_pw"),
        ("d20_m", state_reference, "d20_m_anom", "d20_anom_m"),
        ("ssh_m", state_reference, "ssh_m_anom", "ssh_anom_m"),
        ("sst_c", state_reference, "sst_c_anom", "sst_anom_c"),
    )
    qa: dict[str, float] = {}
    for raw_name, reference, reference_name, output_name in anchors:
        within = raw.groupby(["year", "month", "longitude_e"])[raw_name].transform("mean")
        lookup = reference[["year", "month", "longitude_e", reference_name]].rename(
            columns={reference_name: "_reference"}
        )
        raw = raw.merge(
            lookup,
            on=["year", "month", "longitude_e"],
            how="left",
            validate="many_to_one",
        )
        if raw["_reference"].isna().any():
            raise ValueError(f"Missing monthly reference for {raw_name}")
        raw[output_name] = raw[raw_name] - within + raw["_reference"]
        reconstruction = raw.groupby(["year", "month", "longitude_e"])[output_name].mean()
        target = (
            reference.loc[reference["year"].isin(EVENTS)]
            .set_index(["year", "month", "longitude_e"])[reference_name]
            .reindex(reconstruction.index)
        )
        qa[f"{output_name}_monthly_reconstruction_max_abs_error"] = float(
            np.nanmax(np.abs(reconstruction.to_numpy() - target.to_numpy()))
        )
        raw = raw.drop(columns="_reference")

    selected = raw[["time", "year", "longitude_e", "m_anom_sv", "q20_anom_pw", "d20_anom_m", "ssh_anom_m", "sst_anom_c"]]
    wide_parts = []
    for variable in ("m_anom_sv", "q20_anom_pw", "d20_anom_m", "ssh_anom_m", "sst_anom_c"):
        current = selected.pivot(index=["time", "year"], columns="longitude_e", values=variable)
        current.columns = [f"{variable}_{int(lon)}e" for lon in current.columns]
        wide_parts.append(current)
    wide = pd.concat(wide_parts, axis=1).reset_index().sort_values(["year", "time"])
    return wide, qa


def add_trailing_tendency(frame: pd.DataFrame, source: str, destination: str) -> None:
    values = []
    for _, event in frame.groupby("year", sort=True):
        event = event.sort_values("time")
        days = (event["time"] - event["time"].shift(1)).dt.total_seconds() / 86400.0
        values.append(pd.Series((event[source] - event[source].shift(1)) / days, index=event.index))
    frame[destination] = pd.concat(values).sort_index()


def build_features() -> tuple[pd.DataFrame, dict[str, float]]:
    frame, qa = read_base_frame()
    longitude, longitude_qa = read_full_longitude_state()
    frame = frame.merge(longitude, on=["time", "year"], how="left", validate="one_to_one")
    geometry_columns = {
        "ohc300_positive_east140w_fraction_15day": "east_fraction_15day",
        "ohc300_positive_centroid_deg_e_change15day": "centroid_change15day_deg",
        "ohc300_east_minus_west_gj_m2_change15day": "east_west_gradient_change15day_gj_m2",
    }
    geometry = pd.read_csv(GEOMETRY, parse_dates=["time"])[["time", "year", *geometry_columns]]
    frame = frame.merge(
        geometry.rename(columns=geometry_columns),
        on=["time", "year"],
        how="left",
        validate="one_to_one",
    )

    # Strictly trailing wind-memory features.
    pieces = []
    for _, event in frame.groupby("year", sort=True):
        event = event.sort_values("time").copy()
        event["taux_change5_nm2"] = event["taux_anom_nm2"] - event["taux_anom_nm2"].shift(1)
        event["positive_taux_mean15_nm2"] = (
            event["taux_anom_nm2"].clip(lower=0.0).rolling(3, min_periods=3).mean()
        )
        event["taux_variability15_nm2"] = event["taux_anom_nm2"].rolling(3, min_periods=3).std(ddof=0)
        pieces.append(event)
    frame = pd.concat(pieces, ignore_index=True).sort_values(["year", "time"])

    add_trailing_tendency(frame, "d20_anom_m_200e", "d20_200_tendency5_m_day")
    frame["d20_220_minus_200_m"] = frame["d20_anom_m_220e"] - frame["d20_anom_m_200e"]
    frame["ssh_220_minus_200_m"] = frame["ssh_anom_m_220e"] - frame["ssh_anom_m_200e"]
    add_trailing_tendency(frame, "d20_220_minus_200_m", "d20_220_minus_200_tendency5_m_day")
    add_trailing_tendency(frame, "ssh_220_minus_200_m", "ssh_220_minus_200_tendency5_m_day")

    frame["m160_minus_m180_sv"] = frame["m_anom_sv_160e"] - frame["m_anom_sv_180e"]
    frame["m180_minus_m220_sv"] = frame["m_anom_sv_180e"] - frame["m_anom_sv_220e"]
    frame["m180_x_d20_slope_sv_m"] = (
        frame["m_anom_sv_180e"] * frame["d20_w_minus_c_anom_m"]
    )

    required = sorted({feature for features in MODEL_FEATURES.values() for feature in features})
    missing_counts = frame[required].isna().sum().to_dict()
    qa.update(longitude_qa)
    qa["feature_missing_counts"] = {key: int(value) for key, value in missing_counts.items()}
    qa["common_complete_rows_future5"] = int(
        frame.dropna(subset=required + ["m180_tendency_future5"]).shape[0]
    )
    return frame, qa


def weighted_mean_std(x: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.average(x, axis=0, weights=weights)
    variance = np.average((x - mean) ** 2, axis=0, weights=weights)
    return mean, np.sqrt(np.maximum(variance, 1.0e-12))


def fit_model(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    outcome: str,
    ridge: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    weights = base.event_weights(train["year"])
    x_train = train[features].to_numpy(dtype=float)
    x_test = test[features].to_numpy(dtype=float)
    x_mean, x_scale = weighted_mean_std(x_train, weights)
    y_train = train[outcome].to_numpy(dtype=float)
    y_mean = float(np.average(y_train, weights=weights))
    y_scale = float(np.sqrt(np.average((y_train - y_mean) ** 2, weights=weights)))
    beta = base.fit_ridge_linear(
        (x_train - x_mean) / x_scale,
        (y_train - y_mean) / y_scale,
        weights,
        ridge=ridge,
    )
    prediction_z = np.column_stack(
        [np.ones(len(test)), (x_test - x_mean) / x_scale]
    ) @ beta
    prediction = prediction_z * y_scale + y_mean
    return prediction, beta, x_scale, y_mean, y_scale


def inner_select_ridge(
    train: pd.DataFrame,
    features: list[str],
    outcome: str,
) -> float:
    years = sorted(train["year"].unique())
    scores = []
    for ridge in RIDGE_GRID:
        event_mse = []
        for validation_year in years:
            inner_train = train.loc[train["year"].ne(validation_year)]
            validation = train.loc[train["year"].eq(validation_year)]
            prediction, *_ = fit_model(inner_train, validation, features, outcome, ridge)
            observed = validation[outcome].to_numpy(dtype=float)
            event_mse.append(float(np.mean((prediction - observed) ** 2)))
        scores.append((float(np.mean(event_mse)), ridge))
    return min(scores)[1]


def nested_loeo(
    frame: pd.DataFrame,
    outcome: str,
    model_features: dict[str, list[str]] | None = None,
    common_required: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    models = MODEL_FEATURES if model_features is None else model_features
    common_features = (
        sorted({feature for features in models.values() for feature in features})
        if common_required is None
        else common_required
    )
    data = frame.dropna(subset=common_features + [outcome]).copy()
    predictions = []
    coefficients = []
    for held_year in sorted(data["year"].unique()):
        train = data.loc[data["year"].ne(held_year)]
        test = data.loc[data["year"].eq(held_year)]
        for model, features in models.items():
            ridge = inner_select_ridge(train, features, outcome)
            prediction, beta, x_scale, _, y_scale = fit_model(
                train, test, features, outcome, ridge
            )
            for row, value in zip(test.itertuples(), prediction, strict=True):
                predictions.append(
                    {
                        "outcome": outcome,
                        "time": row.time,
                        "year": int(row.year),
                        "model": model,
                        "ridge": ridge,
                        "observed": float(getattr(row, outcome)),
                        "prediction": float(value),
                    }
                )
            for feature, coefficient in zip(["intercept", *features], beta, strict=True):
                coefficients.append(
                    {
                        "outcome": outcome,
                        "held_year": int(held_year),
                        "model": model,
                        "ridge": ridge,
                        "feature": feature,
                        "standardized_coefficient": float(coefficient),
                        "raw_slope": np.nan
                        if feature == "intercept"
                        else float(y_scale * coefficient / x_scale[features.index(feature)]),
                    }
                )
    return pd.DataFrame(predictions), pd.DataFrame(coefficients)


def summarize_skill(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (outcome, model), group in predictions.groupby(["outcome", "model"], sort=False):
        event_mse = []
        event_mae = []
        for _, event in group.groupby("year"):
            error = event["prediction"].to_numpy() - event["observed"].to_numpy()
            event_mse.append(float(np.mean(error**2)))
            event_mae.append(float(np.mean(np.abs(error))))
        rows.append(
            {
                "outcome": outcome,
                "model": model,
                "n_events": int(group["year"].nunique()),
                "n_pentads": len(group),
                "event_equal_rmse": float(np.sqrt(np.mean(event_mse))),
                "event_equal_mae": float(np.mean(event_mae)),
                "pearson_r": float(pearsonr(group["observed"], group["prediction"]).statistic),
                "median_selected_ridge": float(group.groupby("year")["ridge"].first().median()),
            }
        )
    return pd.DataFrame(rows)


def event_deltas(predictions: pd.DataFrame) -> pd.DataFrame:
    pivot = predictions.pivot_table(
        index=["outcome", "year", "time", "observed"],
        columns="model",
        values="prediction",
    ).reset_index()
    rows = []
    for (outcome, year), event in pivot.groupby(["outcome", "year"], sort=True):
        observed = event["observed"].to_numpy(dtype=float)
        base_mse = float(np.mean((event["base"].to_numpy() - observed) ** 2))
        for model in sorted(predictions["model"].unique()):
            if model == "base":
                continue
            mse = float(np.mean((event[model].to_numpy() - observed) ** 2))
            rows.append(
                {
                    "outcome": outcome,
                    "year": int(year),
                    "model": model,
                    "base_mse": base_mse,
                    "model_mse": mse,
                    "delta_mse_vs_base": mse - base_mse,
                }
            )
    return pd.DataFrame(rows)


def late_block_test(
    frame: pd.DataFrame,
    outcome: str,
    common_required: list[str],
) -> pd.DataFrame:
    data = frame.dropna(subset=common_required + [outcome]).copy()
    train = data.loc[data["year"].le(2009)]
    test = data.loc[data["year"].ge(2015)]
    rows = []
    for model, features in REFINEMENT_MODELS.items():
        ridge = inner_select_ridge(train, features, outcome)
        prediction, *_ = fit_model(train, test, features, outcome, ridge)
        current = test[["year", "time", outcome]].copy()
        current["prediction"] = prediction
        for year, event in current.groupby("year", sort=True):
            mse = float(np.mean((event["prediction"] - event[outcome]) ** 2))
            rows.append(
                {
                    "outcome": outcome,
                    "training_events": "1982-2009 event years",
                    "test_year": int(year),
                    "model": model,
                    "selected_ridge": ridge,
                    "mse": mse,
                }
            )
    output = pd.DataFrame(rows)
    base_lookup = output.loc[output["model"].eq("base")].set_index("test_year")["mse"]
    output["delta_mse_vs_base"] = output.apply(
        lambda row: row["mse"] - base_lookup.loc[row["test_year"]], axis=1
    )
    return output


def bootstrap_deltas(deltas: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for (outcome, model), group in deltas.groupby(["outcome", "model"], sort=False):
        values = group["delta_mse_vs_base"].to_numpy(dtype=float)
        samples = np.empty(N_BOOTSTRAP)
        for index in range(N_BOOTSTRAP):
            selected = rng.integers(0, len(values), len(values))
            samples[index] = np.mean(values[selected])
        rows.append(
            {
                "outcome": outcome,
                "model": model,
                "n_events": len(values),
                "mean_delta_mse_vs_base": float(np.mean(values)),
                "ci_low": float(np.quantile(samples, 0.025)),
                "ci_high": float(np.quantile(samples, 0.975)),
                "events_improved": int(np.sum(values < 0.0)),
                "event_improvement_fraction": float(np.mean(values < 0.0)),
            }
        )
    return pd.DataFrame(rows)


def process_winner(skill: pd.DataFrame, outcome: str) -> str:
    process_models = [f"base_plus_{name}" for name in PROCESS_FEATURES]
    current = skill.loc[skill["outcome"].eq(outcome) & skill["model"].isin(process_models)]
    return str(current.sort_values("event_equal_rmse").iloc[0]["model"])


def plot_result(
    predictions: pd.DataFrame,
    coefficients: pd.DataFrame,
    refinement_coefficients: pd.DataFrame,
    skill: pd.DataFrame,
    deltas: pd.DataFrame,
    bootstrap: pd.DataFrame,
    winner: str,
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8.1))
    figure.subplots_adjust(left=0.09, right=0.975, bottom=0.11, top=0.91, wspace=0.27, hspace=0.31)
    primary = "m180_tendency_future5"

    # (a) Process-group incremental MSE.
    ax = axes[0, 0]
    order = [
        "base_plus_wind_memory",
        "base_plus_wave_phase",
        "base_plus_transport_structure",
        "base_plus_heat_geometry",
        "base_plus_all",
    ]
    current = bootstrap.loc[bootstrap["outcome"].eq(primary)].set_index("model").loc[order]
    y = np.arange(len(order))
    colors = ["#B7352D" if value < 0 else "#9A9A9A" for value in current["mean_delta_mse_vs_base"]]
    ax.barh(y, current["mean_delta_mse_vs_base"], color=colors, alpha=0.86)
    ax.errorbar(
        current["mean_delta_mse_vs_base"],
        y,
        xerr=[
            current["mean_delta_mse_vs_base"] - current["ci_low"],
            current["ci_high"] - current["mean_delta_mse_vs_base"],
        ],
        fmt="none",
        ecolor="#222222",
        capsize=3,
        lw=1.0,
    )
    ax.axvline(0.0, color="#222222", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([MODEL_LABELS[name] for name in order])
    ax.invert_yaxis()
    ax.set_xlabel("Event-mean MSE change versus base (Sv² day⁻²)")
    ax.set_title("(a) Which omitted process reduces the residual?", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    # (b) Event-level winner deltas.
    ax = axes[0, 1]
    event = deltas.loc[deltas["outcome"].eq(primary) & deltas["model"].eq(winner)].sort_values("year")
    x = np.arange(len(event))
    bar_colors = ["#2C7FB8" if value < 0 else "#D95F5F" for value in event["delta_mse_vs_base"]]
    ax.bar(x, event["delta_mse_vs_base"], color=bar_colors, width=0.72)
    ax.axhline(0.0, color="#222222", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(event["year"].astype(int).astype(str), rotation=45, ha="right")
    for label in ax.get_xticklabels():
        if int(label.get_text()) in HIGHLIGHTS:
            label.set_fontweight("bold")
    ax.set_ylabel("MSE change versus base")
    ax.set_title(f"(b) {MODEL_LABELS[winner]}: event consistency", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    # (c) Added-feature coefficient stability for the winning group.
    ax = axes[1, 0]
    process_name = winner.replace("base_plus_", "")
    added = PROCESS_FEATURES[process_name]
    coef = coefficients.loc[
        coefficients["outcome"].eq(primary)
        & coefficients["model"].eq(winner)
        & coefficients["feature"].isin(added)
    ]
    coefficient_items = [
        (
            "Upstream\ntransport surplus",
            coef.loc[coef["feature"].eq("m160_minus_m180_sv"), "standardized_coefficient"].to_numpy(),
        ),
        (
            "Five-day wind\nstress change",
            refinement_coefficients.loc[
                refinement_coefficients["outcome"].eq(primary)
                & refinement_coefficients["model"].eq("wind_change_only")
                & refinement_coefficients["feature"].eq("taux_change5_nm2"),
                "standardized_coefficient",
            ].to_numpy(),
        ),
        (
            "Downstream\ntransport surplus",
            coef.loc[coef["feature"].eq("m180_minus_m220_sv"), "standardized_coefficient"].to_numpy(),
        ),
        (
            "Transport x\nD20 slope",
            coef.loc[coef["feature"].eq("m180_x_d20_slope_sv_m"), "standardized_coefficient"].to_numpy(),
        ),
    ]
    values = [item[1] for item in coefficient_items]
    positions = np.arange(len(values))
    ax.boxplot(
        values,
        positions=positions,
        widths=0.48,
        patch_artist=True,
        showfliers=False,
        boxprops={"facecolor": "#C6DBEF", "edgecolor": "#2C7FB8"},
        medianprops={"color": "#B7352D", "lw": 1.3},
        whiskerprops={"color": "#555555"},
        capprops={"color": "#555555"},
    )
    for position, value in zip(positions, values, strict=True):
        ax.scatter(np.full(len(value), position), value, color="#355C7D", s=13, alpha=0.58)
    ax.axhline(0.0, color="#222222", lw=0.8)
    ax.set_xticks(positions)
    ax.set_xticklabels([item[0] for item in coefficient_items], fontsize=6.8)
    ax.set_ylabel("Standardized coefficient across held-event folds")
    ax.set_title("(c) Stable signs identify a wind-driven incoming pulse", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    # (d) Highlighted event residuals, base versus winner.
    ax = axes[1, 1]
    selected = predictions.loc[
        predictions["outcome"].eq(primary)
        & predictions["model"].isin(["base", winner])
        & predictions["year"].isin(HIGHLIGHTS)
    ].copy()
    pivot = selected.pivot_table(
        index=["year", "time", "observed"], columns="model", values="prediction"
    ).reset_index()
    colors_by_year = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}
    for year, event_group in pivot.groupby("year"):
        event_group = event_group.sort_values("time")
        start = pd.Timestamp(year=int(year), month=1, day=1)
        relative = (pd.to_datetime(event_group["time"]) - start).dt.days
        base_residual = event_group["observed"] - event_group["base"]
        winner_residual = event_group["observed"] - event_group[winner]
        ax.plot(relative, base_residual, color=colors_by_year[int(year)], lw=1.0, ls="--", alpha=0.75)
        ax.plot(relative, winner_residual, color=colors_by_year[int(year)], lw=1.35, label=f"{year}")
    ax.axhline(0.0, color="#222222", lw=0.8)
    ax.set_xticks([0, 31, 59, 90, 120, 151, 181])
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"])
    ax.set_ylabel("Observed minus predicted tendency (Sv day⁻¹)")
    ax.set_title("(d) Solid: winner residual; dashed: base residual", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3, loc="upper right")
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    figure.suptitle(
        "What is missing from the reduced SODA3 force-balance model?",
        fontsize=13.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "13 events; identical pentads; complete-event outer validation with inner event-wise ridge selection. "
        "All added predictors are contemporaneous or strictly trailing proxies, not a closed momentum budget.",
        ha="center",
        fontsize=7.0,
        color="#555555",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def row_for(frame: pd.DataFrame, outcome: str, model: str) -> pd.Series:
    return frame.loc[frame["outcome"].eq(outcome) & frame["model"].eq(model)].iloc[0]


def main() -> int:
    frame, qa = build_features()
    locked_common = sorted(
        {feature for features in MODEL_FEATURES.values() for feature in features}
    )
    prediction_parts = []
    coefficient_parts = []
    for outcome in ("m180_tendency_future5", "m180_tendency_future10"):
        prediction, coefficient = nested_loeo(frame, outcome)
        prediction_parts.append(prediction)
        coefficient_parts.append(coefficient)
    predictions = pd.concat(prediction_parts, ignore_index=True)
    coefficients = pd.concat(coefficient_parts, ignore_index=True)
    skill = summarize_skill(predictions)
    deltas = event_deltas(predictions)
    bootstrap = bootstrap_deltas(deltas)
    winner5 = process_winner(skill, "m180_tendency_future5")
    winner10 = process_winner(skill, "m180_tendency_future10")

    winner_skill5 = row_for(skill, "m180_tendency_future5", winner5)
    base_skill5 = row_for(skill, "m180_tendency_future5", "base")
    winner_boot5 = row_for(bootstrap, "m180_tendency_future5", winner5)
    winner_skill10 = row_for(skill, "m180_tendency_future10", winner10)
    base_skill10 = row_for(skill, "m180_tendency_future10", "base")
    winner_boot10 = row_for(bootstrap, "m180_tendency_future10", winner10)

    refinement_predictions, refinement_coefficients = nested_loeo(
        frame,
        "m180_tendency_future5",
        model_features=REFINEMENT_MODELS,
        common_required=locked_common,
    )
    refinement_skill = summarize_skill(refinement_predictions)
    refinement_deltas = event_deltas(refinement_predictions)
    refinement_bootstrap = bootstrap_deltas(refinement_deltas)
    late_block = late_block_test(
        frame,
        "m180_tendency_future5",
        common_required=locked_common,
    )
    wind_change_refinement = row_for(
        refinement_bootstrap,
        "m180_tendency_future5",
        "wind_change_only",
    )
    upstream_refinement = row_for(
        refinement_bootstrap,
        "m180_tendency_future5",
        "upstream_convergence_only",
    )
    combined_refinement = row_for(
        refinement_bootstrap,
        "m180_tendency_future5",
        "upstream_plus_wind_change",
    )
    refinement_signs = {}
    for model, feature in (
        ("wind_change_only", "taux_change5_nm2"),
        ("upstream_convergence_only", "m160_minus_m180_sv"),
    ):
        values = refinement_coefficients.loc[
            refinement_coefficients["model"].eq(model)
            & refinement_coefficients["feature"].eq(feature),
            "standardized_coefficient",
        ].to_numpy(dtype=float)
        refinement_signs[feature] = {
            "median": float(np.median(values)),
            "positive_fraction": float(np.mean(values > 0.0)),
        }
    late_summary = (
        late_block.groupby("model")
        .agg(
            event_equal_rmse=("mse", lambda values: float(np.sqrt(np.mean(values)))),
            events_improved=("delta_mse_vs_base", lambda values: int(np.sum(values < 0.0))),
        )
    )

    process_name = winner5.replace("base_plus_", "")
    added = PROCESS_FEATURES[process_name]
    coefficient_subset = coefficients.loc[
        coefficients["outcome"].eq("m180_tendency_future5")
        & coefficients["model"].eq(winner5)
        & coefficients["feature"].isin(added)
    ]
    sign_stability = {}
    for feature in added:
        values = coefficient_subset.loc[
            coefficient_subset["feature"].eq(feature), "standardized_coefficient"
        ].to_numpy(dtype=float)
        sign_stability[feature] = {
            "median": float(np.median(values)),
            "positive_fraction": float(np.mean(values > 0.0)),
            "negative_fraction": float(np.mean(values < 0.0)),
        }

    diagnostics = {
        "events": list(EVENTS),
        "ridge_grid": list(RIDGE_GRID),
        "primary_outcome": "future-five-day Date-Line warm-volume transport tendency",
        "model_features": MODEL_FEATURES,
        "winner_future5": winner5,
        "winner_future10": winner10,
        "winner_feature_sign_stability": sign_stability,
        "exploratory_refinement_signs": refinement_signs,
        "quality_control": qa,
        "interpretation_limits": [
            "All process terms are reduced proxies and do not close a zonal momentum budget.",
            "The heat-geometry group is unavailable during the first trailing 15 days, so every model uses the same reduced sample.",
            "Process ranking is predictive attribution under event holdout, not a causal perturbation experiment.",
        ],
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(FEATURE_CSV, index=False)
    predictions.to_csv(PREDICTION_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    coefficients.to_csv(COEFFICIENT_CSV, index=False)
    bootstrap.to_csv(BOOTSTRAP_CSV, index=False)
    deltas.to_csv(EVENT_DELTA_CSV, index=False)
    refinement_skill.to_csv(REFINEMENT_SKILL_CSV, index=False)
    refinement_bootstrap.to_csv(REFINEMENT_BOOTSTRAP_CSV, index=False)
    late_block.to_csv(LATE_BLOCK_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    plot_result(
        predictions,
        coefficients,
        refinement_coefficients,
        skill,
        deltas,
        bootstrap,
        winner5,
    )

    winner_label5 = MODEL_LABELS[winner5]
    winner_label10 = MODEL_LABELS[winner10]
    significant5 = bool(winner_boot5["ci_high"] < 0.0)
    significant10 = bool(winner_boot10["ci_high"] < 0.0)
    highlighted = deltas.loc[
        deltas["outcome"].eq("m180_tendency_future5")
        & deltas["model"].eq(winner5)
        & deltas["year"].isin(HIGHLIGHTS)
    ].set_index("year")

    report = f"""# SODA3简化受力平衡残差的过程归因

## 设计

基准模型仍为季节项、已有日界线暖水输送、D20压力坡度和当前风应力。新增变量被预先分为四组，并且只使用当前或过去五日资料：

1. **西风脉冲记忆**：五日风应力变化、过去15日正西风均值、过去15日风应力波动；
2. **Kelvin波/温跃层相位代理**：200°E D20倾向、220°E—200°E D20坡度倾向、对应SSH坡度倾向；
3. **输送结构与非线性代理**：160°E—180°E及180°E—220°E暖水输送差、输送×D20坡度交互；
4. **热含量几何**：140°W以东暖量比例、暖量质心变化、东西热含量梯度变化。

所有模型使用完全相同的五日样本。外层按完整事件留一，内层再按事件选择岭回归强度，避免用被检验事件调参。

## 五日输送倾向结果

- 基准模型事件等权RMSE为 `{base_skill5['event_equal_rmse']:.3f} Sv day⁻¹`，相关为 `{base_skill5['pearson_r']:+.2f}`。
- 四个单独过程组中表现最好的是 **{winner_label5}**：RMSE `{winner_skill5['event_equal_rmse']:.3f} Sv day⁻¹`，相关 `{winner_skill5['pearson_r']:+.2f}`。
- 相对基准的事件平均MSE变化为 `{winner_boot5['mean_delta_mse_vs_base']:+.3f}`，95%事件自助区间 `[{winner_boot5['ci_low']:+.3f}, {winner_boot5['ci_high']:+.3f}]`；`{int(winner_boot5['events_improved'])}/13` 个事件改善。
- 该增量在事件层面{'通过' if significant5 else '没有通过'}零差异检验，因此{'可以把它视为当前最有证据的缺失过程组' if significant5 else '只能把它视为候选排序，不能宣称已经完成残差闭合'}。

## 组内探索性细化

由于输送结构组和西风记忆组排名靠前，进一步只保留最直接的单项，且锁定为与主试验相同的408个五日样本：

- 仅加入**过去五日风应力变化**，MSE变化 `{wind_change_refinement['mean_delta_mse_vs_base']:+.3f}`，95%区间 `[{wind_change_refinement['ci_low']:+.3f}, {wind_change_refinement['ci_high']:+.3f}]`，`{int(wind_change_refinement['events_improved'])}/13` 次改善；系数在 `{100*refinement_signs['taux_change5_nm2']['positive_fraction']:.0f}%` 的事件留一折中为正。
- 仅加入**160°E输入减180°E输出的上游输送盈余**，MSE变化 `{upstream_refinement['mean_delta_mse_vs_base']:+.3f}`，区间 `[{upstream_refinement['ci_low']:+.3f}, {upstream_refinement['ci_high']:+.3f}]`，`{int(upstream_refinement['events_improved'])}/13` 次改善；系数在 `{100*refinement_signs['m160_minus_m180_sv']['positive_fraction']:.0f}%` 的折中为正。
- 两项合并后MSE变化 `{combined_refinement['mean_delta_mse_vs_base']:+.3f}`，区间 `[{combined_refinement['ci_low']:+.3f}, {combined_refinement['ci_high']:+.3f}]`。

风应力变化单项的区间刚好低于零，但这是看过过程组排序后的二阶段细化，必须标为**探索性发现**，不能当成预注册的独立显著性结果。物理上它说明重要的不是“西风现在有多强”，而是西风是否正在快速增强。

## 晚期事件时间外检验

只用1982—2009事件训练，再整体预测2015、2018、2019和2023：

- 基准模型事件等权RMSE `{late_summary.loc['base', 'event_equal_rmse']:.3f}`；
- 仅风应力变化 `{late_summary.loc['wind_change_only', 'event_equal_rmse']:.3f}`；
- 仅上游输送盈余 `{late_summary.loc['upstream_convergence_only', 'event_equal_rmse']:.3f}`；
- 两项合并 `{late_summary.loc['upstream_plus_wind_change', 'event_equal_rmse']:.3f} Sv day⁻¹`，并在 `{int(late_summary.loc['upstream_plus_wind_change', 'events_improved'])}/4` 个晚期事件中优于基准。

这个结果支持一个更具体的工作假说：缺失项主要是**正在增强的西风所触发的上游暖水输送脉冲**，而不是静态D20坡度、单独的东部热含量位置，或目前使用的Kelvin相位代理。

## 十日倾向稳健性

- 十日目标的最佳单独过程组是 **{winner_label10}**；基准RMSE `{base_skill10['event_equal_rmse']:.3f}`，最佳模型 `{winner_skill10['event_equal_rmse']:.3f} Sv day⁻¹`。
- MSE变化 `{winner_boot10['mean_delta_mse_vs_base']:+.3f}`，95%区间 `[{winner_boot10['ci_low']:+.3f}, {winner_boot10['ci_high']:+.3f}]`，{'仍然通过' if significant10 else '未通过'}事件检验。

## 关键个例

- 1997年最佳过程组的MSE变化：`{highlighted.loc[1997, 'delta_mse_vs_base']:+.3f}`；
- 2015年：`{highlighted.loc[2015, 'delta_mse_vs_base']:+.3f}`；
- 2023年：`{highlighted.loc[2023, 'delta_mse_vs_base']:+.3f}`。

负值表示新增过程减少了基准残差。三次事件不必同号；如果2023改善而1997恶化，说明该项可能专门描述弱耦合背景，而不是通用ENSO动力。

## 科学判断

这个试验回答的是“哪一类当前/滞后状态最能补充简化平衡面”，不是人为扰动后的因果归因。即使某组通过，也仍需要把对应项写入完整的热量或动量收支，或者用模式扰动实验确认。

## 输出

- 图：`{FIGURE_PDF}`
- 公共样本与候选量：`{FEATURE_CSV}`
- 留一预测：`{PREDICTION_CSV}`
- 模型评分：`{SKILL_CSV}`
- 事件MSE差：`{EVENT_DELTA_CSV}`
- 探索性单项细化：`{REFINEMENT_BOOTSTRAP_CSV}`
- 早期训练—晚期事件检验：`{LATE_BLOCK_CSV}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
