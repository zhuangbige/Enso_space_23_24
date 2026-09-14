#!/usr/bin/env python3
"""Run the next-stage observational factorial matrix for ENSO type transition.

This script is deliberately narrower than a general prediction model.  It
fits three small ridge response surfaces to the 13 warm events and evaluates
counterfactual grids around the 2023 event while excluding 2023 from the
surface fit:

1. NPMM x high-frequency westerly wind bursts (WWB);
2. Indo-Atlantic heating x residual far-eastern-Pacific (FEP) warming;
3. April eastward ocean heat gate x a westerly-versus-northeasterly wind
   regime.

The outputs are observationally constrained sensitivity experiments, not
dynamical-model causal integrations.  Interaction uncertainty is estimated
with event bootstrap, and out-of-sample usefulness is checked with leave-one-
event-out validation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

RUNTIME_CACHE = Path(
    "/private/tmp/codex_maryland_enso_next_factorial_cache"
)
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/perturbation_attribution"
PDF_DIR = ROOT / "output/pdf"

EVENT_CSV = DERIVED / "enso_ne_wind_bridge_event_indices.csv"
PREDICTION_CSV = DERIVED / "enso_next_factorial_matrix_predictions.csv"
INTERACTION_CSV = DERIVED / "enso_next_factorial_interactions.csv"
SKILL_CSV = DERIVED / "enso_next_factorial_loeo_skill.csv"
ROBUSTNESS_CSV = DERIVED / "enso_next_factorial_robustness.csv"
DIAGNOSTICS_JSON = DERIVED / "enso_next_factorial_diagnostics.json"
FIGURE = OUT / "fig5_next_factorial_experiment_matrix"

RIDGE_ALPHA = 1.0
BOOTSTRAP_SAMPLES = 10_000
RANDOM_SEED = 20260731
LEVELS = (-1.0, 0.0, 1.0)
TARGETS = (
    "coupling_mjj",
    "mature_ec_flavor",
    "mature_box_type",
)


@dataclass(frozen=True)
class MatrixSpec:
    matrix_id: str
    title: str
    controls: tuple[str, ...]
    factor_columns: tuple[str, ...]
    feature_names: tuple[str, ...]
    interaction_label: str


SPECS = {
    "A_NPMM_x_WWB": MatrixSpec(
        matrix_id="A_NPMM_x_WWB",
        title="NPMM × high-frequency WWB",
        controls=(
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
            "indo_atlantic_total_heating",
        ),
        factor_columns=("npmm_fma", "wwb_stochastic_impulse"),
        feature_names=(
            "ocean_gate",
            "early_ec",
            "residual_fep",
            "indo_atlantic",
            "npmm",
            "wwb",
            "npmm_x_wwb",
        ),
        interaction_label="NPMM × WWB",
    ),
    "B_IA_x_FEP": MatrixSpec(
        matrix_id="B_IA_x_FEP",
        title="Indo-Atlantic heating × residual FEP",
        controls=(
            "east_ocean_state_z",
            "early_ec_apr",
            "npmm_fma",
        ),
        factor_columns=(
            "indo_atlantic_total_heating",
            "fep_residual_mjj",
        ),
        feature_names=(
            "ocean_gate",
            "early_ec",
            "npmm",
            "indo_atlantic",
            "residual_fep",
            "ia_x_fep",
        ),
        interaction_label="Indo-Atlantic × residual FEP",
    ),
    "C_OCEAN_x_WIND": MatrixSpec(
        matrix_id="C_OCEAN_x_WIND",
        title="April ocean gate × wind regime",
        controls=(
            "early_ec_apr",
            "fep_residual_mjj",
            "indo_atlantic_total_heating",
        ),
        factor_columns=(
            "east_ocean_state_z",
            "wwb_stochastic_impulse",
            "ne850_mjj",
        ),
        feature_names=(
            "early_ec",
            "residual_fep",
            "indo_atlantic",
            "ocean_gate",
            "wwb",
            "northeasterly_intrusion",
            "ocean_x_wwb",
            "ocean_x_northeasterly",
        ),
        interaction_label=(
            "Ocean × favorable-wind regime "
            "(Ocean×WWB − Ocean×NE)"
        ),
    ),
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.5,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def standardization(
    train: pd.DataFrame,
    columns: tuple[str, ...],
) -> tuple[dict[str, float], dict[str, float]]:
    means = {column: float(train[column].mean()) for column in columns}
    scales = {column: float(train[column].std(ddof=1)) for column in columns}
    invalid = [
        column
        for column, value in scales.items()
        if not np.isfinite(value) or value == 0
    ]
    if invalid:
        raise ValueError(f"Degenerate standardization: {invalid}")
    return means, scales


def z_frame(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    means: dict[str, float],
    scales: dict[str, float],
) -> pd.DataFrame:
    output = frame.copy()
    for column in columns:
        output[column] = (
            output[column].astype(float) - means[column]
        ) / scales[column]
    return output


def build_features(
    frame_z: pd.DataFrame,
    matrix_id: str,
) -> pd.DataFrame:
    if matrix_id == "A_NPMM_x_WWB":
        output = pd.DataFrame(
            {
                "ocean_gate": frame_z["east_ocean_state_z"],
                "early_ec": frame_z["early_ec_apr"],
                "residual_fep": frame_z["fep_residual_mjj"],
                "indo_atlantic": frame_z[
                    "indo_atlantic_total_heating"
                ],
                "npmm": frame_z["npmm_fma"],
                "wwb": frame_z["wwb_stochastic_impulse"],
            },
            index=frame_z.index,
        )
        output["npmm_x_wwb"] = output["npmm"] * output["wwb"]
        return output
    if matrix_id == "B_IA_x_FEP":
        output = pd.DataFrame(
            {
                "ocean_gate": frame_z["east_ocean_state_z"],
                "early_ec": frame_z["early_ec_apr"],
                "npmm": frame_z["npmm_fma"],
                "indo_atlantic": frame_z[
                    "indo_atlantic_total_heating"
                ],
                "residual_fep": frame_z["fep_residual_mjj"],
            },
            index=frame_z.index,
        )
        output["ia_x_fep"] = (
            output["indo_atlantic"] * output["residual_fep"]
        )
        return output
    if matrix_id == "C_OCEAN_x_WIND":
        output = pd.DataFrame(
            {
                "early_ec": frame_z["early_ec_apr"],
                "residual_fep": frame_z["fep_residual_mjj"],
                "indo_atlantic": frame_z[
                    "indo_atlantic_total_heating"
                ],
                "ocean_gate": frame_z["east_ocean_state_z"],
                "wwb": frame_z["wwb_stochastic_impulse"],
                "northeasterly_intrusion": frame_z["ne850_mjj"],
            },
            index=frame_z.index,
        )
        output["ocean_x_wwb"] = (
            output["ocean_gate"] * output["wwb"]
        )
        output["ocean_x_northeasterly"] = (
            output["ocean_gate"]
            * output["northeasterly_intrusion"]
        )
        return output
    raise KeyError(matrix_id)


def make_scenario_rows(
    event_2023_z: pd.DataFrame,
    matrix_id: str,
) -> pd.DataFrame:
    rows = []
    if matrix_id == "A_NPMM_x_WWB":
        for npmm in LEVELS:
            for wwb in LEVELS:
                row = event_2023_z.iloc[0].copy()
                row["npmm_fma"] = npmm
                row["wwb_stochastic_impulse"] = wwb
                row["factor_1_level"] = npmm
                row["factor_2_level"] = wwb
                rows.append(row)
    elif matrix_id == "B_IA_x_FEP":
        for ia in LEVELS:
            for fep in LEVELS:
                row = event_2023_z.iloc[0].copy()
                row["indo_atlantic_total_heating"] = ia
                row["fep_residual_mjj"] = fep
                row["factor_1_level"] = ia
                row["factor_2_level"] = fep
                rows.append(row)
    elif matrix_id == "C_OCEAN_x_WIND":
        for ocean in LEVELS:
            for wind in LEVELS:
                row = event_2023_z.iloc[0].copy()
                row["east_ocean_state_z"] = ocean
                row["wwb_stochastic_impulse"] = wind
                row["ne850_mjj"] = -wind
                row["factor_1_level"] = ocean
                row["factor_2_level"] = wind
                rows.append(row)
    else:
        raise KeyError(matrix_id)
    output = pd.DataFrame(rows).reset_index(drop=True)
    output["matrix_id"] = matrix_id
    output["cell_id"] = [
        f"{matrix_id}_{a:+.0f}_{b:+.0f}"
        for a, b in zip(
            output["factor_1_level"],
            output["factor_2_level"],
            strict=True,
        )
    ]
    return output


def fit_point_and_bootstrap(
    table: pd.DataFrame,
    spec: MatrixSpec,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = table.loc[table["year"].ne(2023)].copy()
    event_2023 = table.loc[table["year"].eq(2023)].copy()
    raw_columns = tuple(
        dict.fromkeys((*spec.controls, *spec.factor_columns, *TARGETS))
    )
    means, scales = standardization(train, raw_columns)
    train_z = z_frame(train, raw_columns, means, scales)
    event_z = z_frame(event_2023, raw_columns, means, scales)
    scenarios = make_scenario_rows(event_z, spec.matrix_id)
    x_train = build_features(train_z, spec.matrix_id)
    x_scenario = build_features(scenarios, spec.matrix_id)

    point_predictions: dict[str, np.ndarray] = {}
    point_coefficients: dict[str, float] = {}
    for target in TARGETS:
        model = Ridge(alpha=RIDGE_ALPHA).fit(
            x_train[list(spec.feature_names)].to_numpy(dtype=float),
            train_z[target].to_numpy(dtype=float),
        )
        prediction_z = model.predict(
            x_scenario[list(spec.feature_names)].to_numpy(dtype=float)
        )
        point_predictions[target] = (
            means[target] + prediction_z * scales[target]
        )
        coefficients = dict(
            zip(spec.feature_names, model.coef_, strict=True)
        )
        if spec.matrix_id == "C_OCEAN_x_WIND":
            point_coefficients[target] = float(
                coefficients["ocean_x_wwb"]
                - coefficients["ocean_x_northeasterly"]
            )
        else:
            point_coefficients[target] = float(
                coefficients[spec.feature_names[-1]]
            )

    rng = np.random.default_rng(RANDOM_SEED)
    prediction_samples = {
        target: np.empty(
            (BOOTSTRAP_SAMPLES, len(scenarios)),
            dtype=float,
        )
        for target in TARGETS
    }
    coefficient_samples = {
        target: np.empty(BOOTSTRAP_SAMPLES, dtype=float)
        for target in TARGETS
    }
    for iteration in range(BOOTSTRAP_SAMPLES):
        indices = rng.integers(0, len(train_z), len(train_z))
        sampled_x = x_train.iloc[indices]
        for target in TARGETS:
            model = Ridge(alpha=RIDGE_ALPHA).fit(
                sampled_x[list(spec.feature_names)].to_numpy(dtype=float),
                train_z[target].iloc[indices].to_numpy(dtype=float),
            )
            predicted_z = model.predict(
                x_scenario[list(spec.feature_names)].to_numpy(dtype=float)
            )
            prediction_samples[target][iteration] = (
                means[target] + predicted_z * scales[target]
            )
            coefficients = dict(
                zip(spec.feature_names, model.coef_, strict=True)
            )
            if spec.matrix_id == "C_OCEAN_x_WIND":
                coefficient_samples[target][iteration] = (
                    coefficients["ocean_x_wwb"]
                    - coefficients["ocean_x_northeasterly"]
                )
            else:
                coefficient_samples[target][iteration] = coefficients[
                    spec.feature_names[-1]
                ]

    prediction_rows = []
    neutral_index = int(
        scenarios.index[
            scenarios["factor_1_level"].eq(0)
            & scenarios["factor_2_level"].eq(0)
        ][0]
    )
    for cell_index, scenario in scenarios.iterrows():
        for target in TARGETS:
            samples = prediction_samples[target][:, cell_index]
            low, high = np.percentile(samples, (2.5, 97.5))
            delta_samples = (
                samples - prediction_samples[target][:, neutral_index]
            )
            delta_low, delta_high = np.percentile(
                delta_samples,
                (2.5, 97.5),
            )
            point_delta = (
                point_predictions[target][cell_index]
                - point_predictions[target][neutral_index]
            )
            prediction_rows.append(
                {
                    "matrix_id": spec.matrix_id,
                    "matrix_title": spec.title,
                    "cell_id": scenario["cell_id"],
                    "factor_1_level_sd": scenario["factor_1_level"],
                    "factor_2_level_sd": scenario["factor_2_level"],
                    "target": target,
                    "prediction_raw": point_predictions[target][
                        cell_index
                    ],
                    "bootstrap_ci_low_raw": float(low),
                    "bootstrap_ci_high_raw": float(high),
                    "delta_from_neutral_raw": float(point_delta),
                    "delta_bootstrap_ci_low_raw": float(delta_low),
                    "delta_bootstrap_ci_high_raw": float(delta_high),
                    "probability_above_zero": float(
                        np.mean(samples > 0)
                    ),
                    "training_excludes_2023": True,
                    "ridge_alpha": RIDGE_ALPHA,
                }
            )
    interaction_rows = []
    for target in TARGETS:
        samples = coefficient_samples[target]
        low, high = np.percentile(samples, (2.5, 97.5))
        point = point_coefficients[target]
        interaction_rows.append(
            {
                "matrix_id": spec.matrix_id,
                "matrix_title": spec.title,
                "interaction": spec.interaction_label,
                "target": target,
                "interaction_coefficient_response_sd": point,
                "bootstrap_ci_low": float(low),
                "bootstrap_ci_high": float(high),
                "bootstrap_sign_probability": float(
                    max(np.mean(samples > 0), np.mean(samples < 0))
                ),
                "bootstrap_samples": BOOTSTRAP_SAMPLES,
                "ridge_alpha": RIDGE_ALPHA,
            }
        )
    return pd.DataFrame(prediction_rows), pd.DataFrame(interaction_rows)


def extract_interaction_coefficient(
    table: pd.DataFrame,
    spec: MatrixSpec,
    target: str,
    *,
    alpha: float,
) -> float:
    raw_columns = tuple(
        dict.fromkeys((*spec.controls, *spec.factor_columns, target))
    )
    means, scales = standardization(table, raw_columns)
    table_z = z_frame(table, raw_columns, means, scales)
    features = build_features(table_z, spec.matrix_id)
    model = Ridge(alpha=alpha).fit(
        features[list(spec.feature_names)].to_numpy(dtype=float),
        table_z[target].to_numpy(dtype=float),
    )
    coefficients = dict(
        zip(spec.feature_names, model.coef_, strict=True)
    )
    if spec.matrix_id == "C_OCEAN_x_WIND":
        return float(
            coefficients["ocean_x_wwb"]
            - coefficients["ocean_x_northeasterly"]
        )
    return float(coefficients[spec.feature_names[-1]])


def build_robustness(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    samples = {
        "exclude_2023": table.loc[table["year"].ne(2023)].copy(),
        "exclude_2023_and_classic_extremes": table.loc[
            ~table["year"].isin((1982, 1997, 2015, 2023))
        ].copy(),
    }
    for sample_name, sample in samples.items():
        for alpha in (0.25, 0.5, 1.0, 2.0, 5.0):
            for spec in SPECS.values():
                for target in TARGETS:
                    rows.append(
                        {
                            "sample": sample_name,
                            "n_events": len(sample),
                            "ridge_alpha": alpha,
                            "matrix_id": spec.matrix_id,
                            "target": target,
                            "interaction_coefficient_response_sd": (
                                extract_interaction_coefficient(
                                    sample,
                                    spec,
                                    target,
                                    alpha=alpha,
                                )
                            ),
                        }
                    )
    return pd.DataFrame(rows)


def fit_predict_fold(
    train: pd.DataFrame,
    test: pd.DataFrame,
    spec: MatrixSpec,
    target: str,
    *,
    include_factors: bool,
) -> float:
    raw_columns = tuple(
        dict.fromkeys((*spec.controls, *spec.factor_columns, target))
    )
    means, scales = standardization(train, raw_columns)
    train_z = z_frame(train, raw_columns, means, scales)
    test_z = z_frame(test, raw_columns, means, scales)
    x_train = build_features(train_z, spec.matrix_id)
    x_test = build_features(test_z, spec.matrix_id)
    if include_factors:
        features = spec.feature_names
    else:
        features = spec.feature_names[: len(spec.controls)]
    model = Ridge(alpha=RIDGE_ALPHA).fit(
        x_train[list(features)].to_numpy(dtype=float),
        train_z[target].to_numpy(dtype=float),
    )
    prediction_z = float(
        model.predict(x_test[list(features)].to_numpy(dtype=float))[0]
    )
    return means[target] + prediction_z * scales[target]


def build_loeo_skill(
    table: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for spec in SPECS.values():
        for target in TARGETS:
            observed = []
            base_prediction = []
            full_prediction = []
            for year in table["year"]:
                train = table.loc[table["year"].ne(year)].copy()
                test = table.loc[table["year"].eq(year)].copy()
                observed.append(float(test[target].iloc[0]))
                base_prediction.append(
                    fit_predict_fold(
                        train,
                        test,
                        spec,
                        target,
                        include_factors=False,
                    )
                )
                full_prediction.append(
                    fit_predict_fold(
                        train,
                        test,
                        spec,
                        target,
                        include_factors=True,
                    )
                )
            observed_array = np.asarray(observed)
            base_array = np.asarray(base_prediction)
            full_array = np.asarray(full_prediction)
            base_rmse = float(
                np.sqrt(np.mean((observed_array - base_array) ** 2))
            )
            full_rmse = float(
                np.sqrt(np.mean((observed_array - full_array) ** 2))
            )
            rows.append(
                {
                    "matrix_id": spec.matrix_id,
                    "matrix_title": spec.title,
                    "target": target,
                    "n_events": len(observed_array),
                    "base_controls": "; ".join(spec.controls),
                    "full_features": "; ".join(spec.feature_names),
                    "base_rmse": base_rmse,
                    "full_rmse": full_rmse,
                    "incremental_rmse_skill": 1.0
                    - full_rmse / base_rmse,
                    "full_prediction_correlation": float(
                        np.corrcoef(observed_array, full_array)[0, 1]
                    ),
                }
            )
    return pd.DataFrame(rows)


def classify_type_cells(predictions: pd.DataFrame) -> pd.DataFrame:
    output = predictions.copy()
    output["joint_type_class"] = ""
    output["joint_type_robust"] = False
    mask = output["matrix_id"].eq("C_OCEAN_x_WIND")
    cells = output.loc[mask, "cell_id"].unique()
    for cell in cells:
        current = output.loc[
            output["cell_id"].eq(cell)
            & output["target"].isin(
                ("mature_ec_flavor", "mature_box_type")
            )
        ]
        point = current.set_index("target")["prediction_raw"]
        low = current.set_index("target")["bootstrap_ci_low_raw"]
        high = current.set_index("target")["bootstrap_ci_high_raw"]
        if (point > 0).all():
            label = "EP-consistent"
            robust = bool((low > 0).all())
        elif (point < 0).all():
            label = "CP-consistent"
            robust = bool((high < 0).all())
        else:
            label = "metric-disagreement"
            robust = False
        output.loc[output["cell_id"].eq(cell), "joint_type_class"] = (
            label
        )
        output.loc[output["cell_id"].eq(cell), "joint_type_robust"] = (
            robust
        )
    return output


def add_heatmap(
    axis: plt.Axes,
    frame: pd.DataFrame,
    target: str,
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    delta_from_neutral: bool,
    panel_label: str,
) -> None:
    current = frame.loc[frame["target"].eq(target)].copy()
    pivot = current.pivot(
        index="factor_1_level_sd",
        columns="factor_2_level_sd",
        values="prediction_raw",
    ).reindex(index=LEVELS, columns=LEVELS)
    values = pivot.to_numpy(dtype=float)
    if delta_from_neutral:
        neutral = float(pivot.loc[0.0, 0.0])
        values = values - neutral
    vmax = max(float(np.nanmax(np.abs(values))), 0.01)
    image = axis.imshow(
        values,
        origin="lower",
        cmap="RdBu_r",
        vmin=-vmax,
        vmax=vmax,
        aspect="equal",
    )
    axis.set_xticks(range(3), ["−1", "0", "+1"])
    axis.set_yticks(range(3), ["−1", "0", "+1"])
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.set_title(title, loc="left", fontweight="bold", pad=8)
    axis.text(
        -0.18,
        1.08,
        panel_label,
        transform=axis.transAxes,
        fontsize=11,
        fontweight="bold",
    )
    for row in range(3):
        for column in range(3):
            value = values[row, column]
            color = "white" if abs(value) > 0.58 * vmax else "#1f2937"
            axis.text(
                column,
                row,
                f"{value:+.2f}",
                ha="center",
                va="center",
                fontsize=8.2,
                fontweight="bold",
                color=color,
            )
            record = current.loc[
                current["factor_1_level_sd"].eq(LEVELS[row])
                & current["factor_2_level_sd"].eq(LEVELS[column])
            ].iloc[0]
            if delta_from_neutral:
                crosses_zero = bool(
                    record["delta_bootstrap_ci_low_raw"] <= 0
                    <= record["delta_bootstrap_ci_high_raw"]
                )
            else:
                crosses_zero = bool(
                    record["bootstrap_ci_low_raw"] <= 0
                    <= record["bootstrap_ci_high_raw"]
                )
            if crosses_zero:
                axis.plot(
                    column + 0.32,
                    row + 0.32,
                    marker="x",
                    color="#111827",
                    markersize=4,
                    markeredgewidth=0.9,
                )
    colorbar = plt.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    if delta_from_neutral:
        colorbar.set_label("Change from neutral cell (raw units)")
    elif target == "mature_box_type":
        colorbar.set_label("Niño3 − Niño4 (°C)")
    else:
        colorbar.set_label("E/C flavor coordinate")


def plot_matrix(predictions: pd.DataFrame) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(9.2, 7.9))
    add_heatmap(
        axes[0, 0],
        predictions.loc[
            predictions["matrix_id"].eq("A_NPMM_x_WWB")
        ],
        "coupling_mjj",
        title="Atmospheric connection: NPMM × WWB",
        xlabel="High-frequency WWB level (training SD)",
        ylabel="NPMM level (training SD)",
        delta_from_neutral=True,
        panel_label="a",
    )
    add_heatmap(
        axes[0, 1],
        predictions.loc[
            predictions["matrix_id"].eq("B_IA_x_FEP")
        ],
        "coupling_mjj",
        title="Atmospheric connection: remote heating × FEP",
        xlabel="Residual FEP level (training SD)",
        ylabel="Indo-Atlantic heating (training SD)",
        delta_from_neutral=True,
        panel_label="b",
    )
    matrix_c = predictions.loc[
        predictions["matrix_id"].eq("C_OCEAN_x_WIND")
    ]
    add_heatmap(
        axes[1, 0],
        matrix_c,
        "mature_ec_flavor",
        title="Mature type: E/C flavor coordinate",
        xlabel="Wind regime (− adverse, + favorable)",
        ylabel="April eastward ocean gate (training SD)",
        delta_from_neutral=False,
        panel_label="c",
    )
    add_heatmap(
        axes[1, 1],
        matrix_c,
        "mature_box_type",
        title="Mature type: Niño3 − Niño4",
        xlabel="Wind regime (− adverse, + favorable)",
        ylabel="April eastward ocean gate (training SD)",
        delta_from_neutral=False,
        panel_label="d",
    )
    figure.suptitle(
        "Next-stage factorial sensitivity around the 2023 event",
        fontsize=14,
        fontweight="bold",
        y=0.985,
    )
    figure.text(
        0.5,
        0.01,
        (
            "Ridge response surfaces are trained on 12 warm events "
            "(2023 excluded). X marks a cell whose 95% event-bootstrap "
            "interval includes zero. These are observational sensitivity "
            "experiments, not dynamical-model causal integrations."
        ),
        ha="center",
        va="bottom",
        fontsize=7.5,
        color="#4b5563",
        wrap=True,
    )
    figure.subplots_adjust(
        left=0.09,
        right=0.96,
        bottom=0.09,
        top=0.91,
        wspace=0.32,
        hspace=0.34,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE.with_suffix(".png"), bbox_inches="tight")
    figure.savefig(FIGURE.with_suffix(".pdf"), bbox_inches="tight")
    figure.savefig(
        PDF_DIR / "enso_next_factorial_experiment_matrix.pdf",
        bbox_inches="tight",
    )
    plt.close(figure)


def main() -> None:
    if not EVENT_CSV.exists():
        raise FileNotFoundError(EVENT_CSV)
    table = pd.read_csv(EVENT_CSV)
    required = {
        "year",
        "east_ocean_state_z",
        "early_ec_apr",
        "fep_residual_mjj",
        "indo_atlantic_total_heating",
        "npmm_fma",
        "wwb_stochastic_impulse",
        "ne850_mjj",
        *TARGETS,
    }
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    if table[list(required)].isna().any().any():
        raise ValueError("Event table contains missing required values")

    prediction_parts = []
    interaction_parts = []
    for spec in SPECS.values():
        predictions, interactions = fit_point_and_bootstrap(table, spec)
        prediction_parts.append(predictions)
        interaction_parts.append(interactions)
    predictions = classify_type_cells(
        pd.concat(prediction_parts, ignore_index=True)
    )
    interactions = pd.concat(interaction_parts, ignore_index=True)
    skill = build_loeo_skill(table)
    robustness = build_robustness(table)

    predictions.to_csv(PREDICTION_CSV, index=False)
    interactions.to_csv(INTERACTION_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    robustness.to_csv(ROBUSTNESS_CSV, index=False)
    plot_matrix(predictions)

    matrix_c = predictions.loc[
        predictions["matrix_id"].eq("C_OCEAN_x_WIND")
        & predictions["target"].eq("mature_ec_flavor")
    ]
    class_counts = (
        matrix_c["joint_type_class"].value_counts().to_dict()
    )
    robust_counts = (
        matrix_c.groupby("joint_type_class")["joint_type_robust"]
        .sum()
        .astype(int)
        .to_dict()
    )
    diagnostics = {
        "event_count": int(len(table)),
        "training_event_count_for_2023_surfaces": int(
            table["year"].ne(2023).sum()
        ),
        "training_excludes_2023": True,
        "ridge_alpha": RIDGE_ALPHA,
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "factorial_cells": int(
            predictions[["matrix_id", "cell_id"]]
            .drop_duplicates()
            .shape[0]
        ),
        "type_cell_class_counts": class_counts,
        "robust_type_cell_counts": robust_counts,
        "robustness_rows": int(len(robustness)),
        "interpretation_guardrail": (
            "Observationally constrained ridge response surfaces; "
            "dynamical model perturbations are required for causal claims."
        ),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
