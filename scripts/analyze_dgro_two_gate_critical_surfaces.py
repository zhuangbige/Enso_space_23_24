#!/usr/bin/env python3
"""Diagnose the two critical surfaces in a data-extended recharge oscillator.

The analysis is deliberately diagnostic, not a forecast.  It asks when an
observed event trajectory crosses (1) an ocean transport-acceleration surface
and (2) an atmospheric wind-stress surface.  The atmospheric surface is tested
twice: with total stress (literal cessation of easterlies) and with stress
anomaly (cessation of anomalous easterly suppression / coupling onset).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_dgro_two_gate")
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
import analyze_soda3_balance_transition_sequence as sequence  # noqa: E402
import verify_soda3_force_balance_tendency as balance  # noqa: E402


EVENTS = balance.EVENTS
HIGHLIGHTS = (1997, 2015, 2023)
RNG_SEED = 20260803
N_BOOTSTRAP = 10000

DERIVED = ROOT / "data/derived/research_2026"
WIND_LONG = DERIVED / "soda3_5day_ohc_geometry_coupling_13events_jan_sep.csv"
OUT = ROOT / "outputs/research_2026/dgro_two_gate_critical_surfaces"

PENTAD_CSV = DERIVED / "dgro_two_gate_critical_surface_pentads.csv"
EVENT_CSV = DERIVED / "dgro_two_gate_critical_surface_events.csv"
SKILL_CSV = DERIVED / "dgro_atmospheric_surface_loeo_skill.csv"
COEFFICIENT_CSV = DERIVED / "dgro_atmospheric_surface_loeo_coefficients.csv"
BOOTSTRAP_CSV = DERIVED / "dgro_atmospheric_surface_bootstrap.csv"
EQUATION_JSON = DERIVED / "dgro_two_gate_equations.json"
FIGURE_PNG = OUT / "dgro_two_gate_critical_surfaces.png"
FIGURE_SVG = OUT / "dgro_two_gate_critical_surfaces.svg"
REPORT_MD = OUT / "DGRO_TWO_GATE_CRITICAL_SURFACES_CN.md"


ATMOSPHERE_MODELS = {
    "season_only": ["season_sin", "season_cos"],
    "ro_sst": ["season_sin", "season_cos", "sst_c_anom_c"],
    "dgro_state": [
        "season_sin",
        "season_cos",
        "sst_c_anom_c",
        "sst_c_minus_w_anom_c",
        "west_warm_section_anom_gj_m",
        "warm_volume_transport_sv_anom",
        "d20_w_minus_c_anom_m",
    ],
}

TARGETS = {
    "stress_anomaly": "taux_anom_nm2",
    "total_stress": "taux_central_nm2",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Arial Unicode MS",
                "PingFang SC",
                "Hiragino Sans GB",
                "DejaVu Sans",
            ],
            "font.size": 8.5,
            "axes.titlesize": 10.0,
            "axes.labelsize": 8.9,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 7.6,
            "ytick.labelsize": 7.6,
            "legend.fontsize": 7.1,
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
        }
    )


def loeo_atmospheric_surfaces(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit event-independent diagnostic wind surfaces with LOEO ridge fits."""
    predictions: list[dict[str, object]] = []
    coefficients: list[dict[str, object]] = []
    for target_name, target in TARGETS.items():
        for model, features in ATMOSPHERE_MODELS.items():
            data = frame.dropna(subset=features + [target]).copy()
            for held_year in sorted(data["year"].unique()):
                train = data.loc[data["year"].ne(held_year)].copy()
                test = data.loc[data["year"].eq(held_year)].copy()
                weights = balance.event_weights(train["year"])
                x_train = train[features].to_numpy(dtype=float)
                x_test = test[features].to_numpy(dtype=float)
                x_mean, x_scale = balance.weighted_mean_std(x_train, weights)
                y_train = train[target].to_numpy(dtype=float)
                y_mean = float(np.average(y_train, weights=weights))
                y_scale = float(
                    np.sqrt(np.average((y_train - y_mean) ** 2, weights=weights))
                )
                beta = balance.fit_ridge_linear(
                    (x_train - x_mean) / x_scale,
                    (y_train - y_mean) / y_scale,
                    weights,
                )
                pred_z = np.column_stack(
                    [np.ones(len(test)), (x_test - x_mean) / x_scale]
                ) @ beta
                predicted = y_mean + y_scale * pred_z
                for row, value in zip(test.itertuples(), predicted, strict=True):
                    predictions.append(
                        {
                            "target_name": target_name,
                            "target": target,
                            "model": model,
                            "time": row.time,
                            "year": int(row.year),
                            "observed": float(getattr(row, target)),
                            "prediction": float(value),
                        }
                    )
                for feature, value in zip(["intercept"] + features, beta, strict=True):
                    coefficients.append(
                        {
                            "target_name": target_name,
                            "target": target,
                            "model": model,
                            "held_year": int(held_year),
                            "feature": feature,
                            "standardized_coefficient": float(value),
                        }
                    )
    return pd.DataFrame(predictions), pd.DataFrame(coefficients)


def summarize_skill(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (target_name, model), group in predictions.groupby(
        ["target_name", "model"], sort=False
    ):
        weights = balance.event_weights(group["year"])
        observed = group["observed"].to_numpy(dtype=float)
        predicted = group["prediction"].to_numpy(dtype=float)
        error = predicted - observed
        rows.append(
            {
                "target_name": target_name,
                "model": model,
                "n_events": int(group["year"].nunique()),
                "n_pentads": len(group),
                "event_equal_rmse_nm2": float(
                    np.sqrt(np.average(error**2, weights=weights))
                ),
                "event_equal_mae_nm2": float(
                    np.average(np.abs(error), weights=weights)
                ),
                "pearson_r": float(pearsonr(observed, predicted).statistic),
                "zero_sign_accuracy": float(
                    np.average((observed > 0.0) == (predicted > 0.0), weights=weights)
                ),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_model_delta(predictions: pd.DataFrame) -> pd.DataFrame:
    """Event-cluster bootstrap: DGRO state surface versus SST-only RO surface."""
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for target_name, current in predictions.groupby("target_name"):
        selected = current.loc[current["model"].isin(["ro_sst", "dgro_state"])]
        pivot = selected.pivot_table(
            index=["year", "time", "observed"], columns="model", values="prediction"
        ).reset_index()
        event_delta = []
        for _, event in pivot.groupby("year"):
            observed = event["observed"].to_numpy(dtype=float)
            event_delta.append(
                float(
                    np.mean((event["dgro_state"].to_numpy() - observed) ** 2)
                    - np.mean((event["ro_sst"].to_numpy() - observed) ** 2)
                )
            )
        values = np.asarray(event_delta, dtype=float)
        samples = np.empty(N_BOOTSTRAP)
        for index in range(N_BOOTSTRAP):
            chosen = rng.integers(0, len(values), len(values))
            samples[index] = np.mean(values[chosen])
        rows.append(
            {
                "target_name": target_name,
                "comparison": "dgro_state_minus_ro_sst_mse",
                "mean_delta_mse": float(np.mean(values)),
                "ci_low": float(np.quantile(samples, 0.025)),
                "ci_high": float(np.quantile(samples, 0.975)),
                "events_improved": int(np.sum(values < 0.0)),
                "n_events": len(values),
            }
        )
    return pd.DataFrame(rows)


def fit_full_equation(
    frame: pd.DataFrame, target: str, features: list[str]
) -> dict[str, object]:
    """Return a reproducible standardized zero-surface equation."""
    data = frame.dropna(subset=features + [target]).copy()
    weights = balance.event_weights(data["year"])
    x = data[features].to_numpy(dtype=float)
    y = data[target].to_numpy(dtype=float)
    x_mean, x_scale = balance.weighted_mean_std(x, weights)
    y_mean = float(np.average(y, weights=weights))
    y_scale = float(np.sqrt(np.average((y - y_mean) ** 2, weights=weights)))
    beta = balance.fit_ridge_linear(
        (x - x_mean) / x_scale, (y - y_mean) / y_scale, weights
    )
    raw_slopes = y_scale * beta[1:] / x_scale
    raw_intercept = y_mean + y_scale * beta[0] - float(np.sum(raw_slopes * x_mean))
    return {
        "target": target,
        "features": features,
        "equation": "(y-y_mean)/y_scale = beta0 + sum(beta_i*(x_i-x_mean_i)/x_scale_i)",
        "zero_surface_rhs": float(-y_mean / y_scale),
        "y_mean": y_mean,
        "y_scale": y_scale,
        "standardized_intercept": float(beta[0]),
        "standardized_coefficients": {
            feature: float(value) for feature, value in zip(features, beta[1:], strict=True)
        },
        "x_mean": {
            feature: float(value) for feature, value in zip(features, x_mean, strict=True)
        },
        "x_scale": {
            feature: float(value) for feature, value in zip(features, x_scale, strict=True)
        },
        "raw_intercept": float(raw_intercept),
        "raw_coefficients": {
            feature: float(value)
            for feature, value in zip(features, raw_slopes, strict=True)
        },
        "n_events": int(data["year"].nunique()),
        "n_pentads": len(data),
    }


def persistent_positive_onset(
    event: pd.DataFrame,
    column: str,
    *,
    start_month: int = 3,
    window: int = 6,
) -> pd.Timestamp | None:
    """Existing coupling rule: first 2 positive, at least 4 of next 6 positive."""
    current = event.loc[event["time"].dt.month >= start_month].sort_values("time")
    values = current[column].to_numpy(dtype=float)
    times = pd.DatetimeIndex(current["time"])
    for index in range(len(values) - window + 1):
        part = values[index : index + window]
        if (
            np.isfinite(part).all()
            and np.all(part[:2] > 0.0)
            and int(np.sum(part > 0.0)) >= 4
        ):
            return pd.Timestamp(times[index])
    return None


def persistent_joint_onset(
    event: pd.DataFrame, ocean: str, atmosphere: str
) -> pd.Timestamp | None:
    current = event.copy()
    current["_joint"] = np.where(
        current[ocean].notna() & current[atmosphere].notna(),
        ((current[ocean] > 0.0) & (current[atmosphere] > 0.0)).astype(float),
        np.nan,
    )
    return persistent_positive_onset(current, "_joint")


def date_or_nat(value: pd.Timestamp | None) -> pd.Timestamp:
    return pd.NaT if value is None else pd.Timestamp(value)


def rms_about_zero(values: pd.Series, years: pd.Series) -> float:
    mask = values.notna()
    weights = balance.event_weights(years.loc[mask])
    x = values.loc[mask].to_numpy(dtype=float)
    return float(np.sqrt(np.average(x**2, weights=weights)))


def build_gate_frame(
    frame: pd.DataFrame, predictions: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, float]]:
    output = frame.copy()
    for target_name in TARGETS:
        selected = predictions.loc[
            predictions["target_name"].eq(target_name)
            & predictions["model"].eq("dgro_state"),
            ["time", "year", "prediction"],
        ].rename(columns={"prediction": f"{target_name}_dgro_prediction_nm2"})
        output = output.merge(selected, on=["time", "year"], how="left", validate="one_to_one")

    scales = {
        "ocean_observed": rms_about_zero(
            output["observed_transport_tendency_sv_day"], output["year"]
        ),
        "ocean_reduced_ro": rms_about_zero(
            output["loeo_balance_signal_sv_day"], output["year"]
        ),
        "stress_anomaly": rms_about_zero(output["taux_anom_nm2"], output["year"]),
        "total_stress": rms_about_zero(output["taux_central_nm2"], output["year"]),
    }
    # The physical gate is the observed dM/dt sign.  The reduced-RO score is a
    # reconstruction of that gate and is retained separately so model error is
    # never mistaken for the observed transition itself.
    output["ocean_gate_z"] = (
        output["observed_transport_tendency_sv_day"] / scales["ocean_observed"]
    )
    output["ocean_reduced_ro_gate_z"] = (
        output["loeo_balance_signal_sv_day"] / scales["ocean_reduced_ro"]
    )
    output["atmos_anomaly_gate_z"] = output["taux_anom_nm2"] / scales["stress_anomaly"]
    output["atmos_total_gate_z"] = output["taux_central_nm2"] / scales["total_stress"]
    output["atmos_anomaly_dgro_gate_z"] = (
        output["stress_anomaly_dgro_prediction_nm2"] / scales["stress_anomaly"]
    )
    output["atmos_total_dgro_gate_z"] = (
        output["total_stress_dgro_prediction_nm2"] / scales["total_stress"]
    )
    output["joint_distance_anomaly"] = np.hypot(
        output["ocean_gate_z"], output["atmos_anomaly_gate_z"]
    )
    output["joint_distance_total"] = np.hypot(
        output["ocean_gate_z"], output["atmos_total_gate_z"]
    )
    output["joint_distance_dgro_anomaly"] = np.hypot(
        output["ocean_gate_z"], output["atmos_anomaly_dgro_gate_z"]
    )
    for column in (
        "ocean_gate_z",
        "atmos_anomaly_gate_z",
        "atmos_total_gate_z",
    ):
        output[f"{column}_15day"] = output.groupby("year", sort=False)[column].transform(
            lambda values: values.rolling(3, min_periods=2).mean()
        )
    return output, scales


def build_event_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in EVENTS:
        event = frame.loc[frame["year"].eq(year)].sort_values("time").copy()
        ocean_onset, ocean_confirm = sequence.first_positive_run(
            event, "loeo_balance_signal_sv_day", 3
        )
        observed_ocean, observed_ocean_confirm = sequence.observed_transport_episode(
            event, 3
        )
        anomaly_onset = persistent_positive_onset(event, "taux_anom_nm2")
        anomaly_surface_onset = persistent_positive_onset(
            event, "stress_anomaly_dgro_prediction_nm2"
        )
        total_onset = persistent_positive_onset(event, "taux_central_nm2")
        total_surface_onset = persistent_positive_onset(
            event, "total_stress_dgro_prediction_nm2"
        )
        total_positive = event.loc[event["taux_central_nm2"].gt(0.0), "time"]
        joint_anomaly = persistent_joint_onset(
            event, "observed_transport_tendency_sv_day", "taux_anom_nm2"
        )
        joint_total = persistent_joint_onset(
            event, "observed_transport_tendency_sv_day", "taux_central_nm2"
        )
        joint_reduced_ro_anomaly = persistent_joint_onset(
            event, "loeo_balance_signal_sv_day", "taux_anom_nm2"
        )
        search = event.loc[event["time"].dt.month >= 2].dropna(
            subset=["joint_distance_anomaly", "joint_distance_total"]
        )
        closest_anomaly = search.loc[search["joint_distance_anomaly"].idxmin()]
        closest_total = search.loc[search["joint_distance_total"].idxmin()]
        row = {
            "year": int(year),
            "ocean_surface_onset": date_or_nat(ocean_onset),
            "ocean_surface_confirmation": date_or_nat(ocean_confirm),
            "observed_transport_acceleration_onset": date_or_nat(observed_ocean),
            "observed_transport_acceleration_confirmation": date_or_nat(
                observed_ocean_confirm
            ),
            "anomaly_westerly_gate_onset": date_or_nat(anomaly_onset),
            "anomaly_dgro_surface_onset": date_or_nat(anomaly_surface_onset),
            "total_wind_reversal_persistent_onset": date_or_nat(total_onset),
            "total_dgro_surface_onset": date_or_nat(total_surface_onset),
            "first_single_total_stress_positive": (
                pd.NaT if total_positive.empty else pd.Timestamp(total_positive.iloc[0])
            ),
            "joint_ocean_anomaly_gate_onset": date_or_nat(joint_anomaly),
            "joint_ocean_total_gate_onset": date_or_nat(joint_total),
            "joint_reduced_ro_anomaly_gate_onset": date_or_nat(
                joint_reduced_ro_anomaly
            ),
            "closest_joint_anomaly_date": pd.Timestamp(closest_anomaly["time"]),
            "closest_joint_anomaly_distance": float(
                closest_anomaly["joint_distance_anomaly"]
            ),
            "closest_joint_total_date": pd.Timestamp(closest_total["time"]),
            "closest_joint_total_distance": float(closest_total["joint_distance_total"]),
            "maximum_total_stress_nm2": float(event["taux_central_nm2"].max()),
        }
        for label, start, end in (
            ("ocean_confirm_to_anomaly_gate_days", ocean_confirm, anomaly_onset),
            ("observed_transport_confirm_to_anomaly_gate_days", observed_ocean_confirm, anomaly_onset),
            ("ocean_confirm_to_total_reversal_days", ocean_confirm, total_onset),
        ):
            row[label] = (
                np.nan if start is None or end is None else float((end - start).days)
            )
        rows.append(row)
    return pd.DataFrame(rows)


def coefficient_stability(coefficients: pd.DataFrame) -> pd.DataFrame:
    selected = coefficients.loc[coefficients["model"].eq("dgro_state")]
    return (
        selected.groupby(["target_name", "feature"])["standardized_coefficient"]
        .agg(
            median="median",
            minimum="min",
            maximum="max",
            positive_fraction=lambda x: float(np.mean(x > 0.0)),
        )
        .reset_index()
    )


def plot_results(
    frame: pd.DataFrame,
    events: pd.DataFrame,
    predictions: pd.DataFrame,
    skill: pd.DataFrame,
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.4))
    figure.subplots_adjust(
        left=0.08, right=0.975, bottom=0.105, top=0.90, wspace=0.24, hspace=0.31
    )
    colors = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}

    def state_panel(ax: plt.Axes, ycol: str, title: str, ylabel: str) -> None:
        ax.axhline(0.0, color="#252525", lw=0.85)
        ax.axvline(0.0, color="#252525", lw=0.85)
        ax.axvspan(0.0, 5.0, color="#EAF4E6", alpha=0.42, zorder=0)
        for year in HIGHLIGHTS:
            event = frame.loc[frame["year"].eq(year)].dropna(
                subset=["ocean_gate_z_15day", ycol]
            )
            ax.plot(
                event["ocean_gate_z_15day"],
                event[ycol],
                color=colors[year],
                lw=1.45,
                alpha=0.90,
                label=str(year),
            )
            ax.scatter(
                event["ocean_gate_z_15day"], event[ycol], color=colors[year], s=10, zorder=3
            )
            for month in (2, 4, 6):
                point = event.loc[event["month"].eq(month)].head(1)
                if not point.empty:
                    ax.text(
                        float(point["ocean_gate_z_15day"].iloc[0]),
                        float(point[ycol].iloc[0]),
                        f"{month}月",
                        color=colors[year],
                        fontsize=6.3,
                        ha="left",
                        va="bottom",
                    )
        ax.set_xlabel(r"海洋门 $G_O$（15日平均；$dM/dt=0$ 为临界面）")
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.grid(color="#E5E5E5", lw=0.5)
        ax.legend(frameon=False, ncol=3, loc="best")

    state_panel(
        axes[0, 0],
        "atmos_anomaly_gate_z_15day",
        "(a) 异常风门：海洋先过线，大气随后是否接上",
        r"异常风门 $G_A'$（标准化；$τ_x'=0$）",
    )
    state_panel(
        axes[0, 1],
        "atmos_total_gate_z_15day",
        "(b) 总风门：实际东风通常没有停止",
        r"总风门 $G_A$（标准化；$τ_x=0$）",
    )

    ax = axes[1, 0]
    years = events["year"].to_numpy(dtype=int)
    lags = events[
        "observed_transport_confirm_to_anomaly_gate_days"
    ].to_numpy(dtype=float)
    x = np.arange(len(years))
    ax.axhline(0.0, color="#333333", lw=0.8)
    bars = ax.bar(x, lags, color="#739FC3", width=0.72)
    for index, (bar, year) in enumerate(zip(bars, years, strict=True)):
        if year in HIGHLIGHTS:
            bar.set_color(colors[year])
        if np.isfinite(lags[index]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                lags[index] + (3 if lags[index] >= 0 else -3),
                f"{lags[index]:.0f}",
                ha="center",
                va="bottom" if lags[index] >= 0 else "top",
                fontsize=6.5,
            )
    ax.set_xticks(x)
    ax.set_xticklabels(years.astype(str), rotation=45, ha="right")
    ax.set_ylabel("观测海洋门确认日至异常西风门建立（天）")
    ax.set_title("(c) 两道门之间的事件依赖滞后", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#E5E5E5", lw=0.55)

    ax = axes[1, 1]
    markers = {"stress_anomaly": "o", "total_stress": "s"}
    plot_colors = {"stress_anomaly": "#6A3D9A", "total_stress": "#238B45"}
    for target_name in TARGETS:
        current = predictions.loc[
            predictions["target_name"].eq(target_name)
            & predictions["model"].eq("dgro_state")
        ]
        label_name = "异常风应力" if target_name == "stress_anomaly" else "总风应力"
        r = skill.loc[
            skill["target_name"].eq(target_name) & skill["model"].eq("dgro_state"),
            "pearson_r",
        ].iloc[0]
        ax.scatter(
            current["observed"],
            current["prediction"],
            s=16,
            alpha=0.40,
            marker=markers[target_name],
            color=plot_colors[target_name],
            linewidth=0,
            label=f"{label_name}（r={r:.2f}）",
        )
    limit = float(
        np.nanpercentile(
            np.abs(predictions.loc[predictions["model"].eq("dgro_state"), ["observed", "prediction"]]),
            99,
        )
    )
    ax.plot([-limit, limit], [-limit, limit], color="#222222", ls="--", lw=0.8)
    ax.axhline(0.0, color="#777777", lw=0.55)
    ax.axvline(0.0, color="#777777", lw=0.55)
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_xlabel("观测风应力（N m⁻²）")
    ax.set_ylabel("留一事件重建（N m⁻²）")
    ax.set_title("(d) 扩展RO状态能否重建大气临界面", loc="left", fontweight="bold")
    ax.grid(color="#E5E5E5", lw=0.5)
    ax.legend(frameon=False, loc="upper left")

    figure.suptitle(
        "扩展Recharge Oscillator的双临界面检验：不是预测，而是定位转变",
        fontsize=13.2,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "SODA3五日资料，13次暖事件，月气候态与线性趋势基准1980–2024。"
        "海洋面为留一事件D20–风–已有输送平衡；大气面为同期诊断回归。",
        ha="center",
        fontsize=7.2,
        color="#555555",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_SVG, bbox_inches="tight")
    plt.close(figure)


def date_text(value: object) -> str:
    return "未出现" if pd.isna(value) else pd.Timestamp(value).strftime("%Y-%m-%d")


def main() -> int:
    frame, _, qa = sequence.build_balance_frame()
    predictions, coefficients = loeo_atmospheric_surfaces(frame)
    skill = summarize_skill(predictions)
    bootstrap = bootstrap_model_delta(predictions)
    gate_frame, scales = build_gate_frame(frame, predictions)
    event_table = build_event_table(gate_frame)
    stability = coefficient_stability(coefficients)

    ocean_features = balance.MODEL_FEATURES["d20_balance"]
    equations = {
        "purpose": "diagnostic zero surfaces, not a forecast",
        "ocean_gate": fit_full_equation(
            frame, "m180_tendency_future5", ocean_features
        ),
        "atmosphere_anomaly_gate": fit_full_equation(
            frame, "taux_anom_nm2", ATMOSPHERE_MODELS["dgro_state"]
        ),
        "atmosphere_total_gate": fit_full_equation(
            frame, "taux_central_nm2", ATMOSPHERE_MODELS["dgro_state"]
        ),
        "gate_scales": scales,
        "quality_control": qa,
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    gate_frame.to_csv(PENTAD_CSV, index=False, date_format="%Y-%m-%d")
    event_table.to_csv(EVENT_CSV, index=False, date_format="%Y-%m-%d")
    skill.to_csv(SKILL_CSV, index=False)
    coefficients.merge(
        stability,
        on=["target_name", "feature"],
        how="left",
        validate="many_to_one",
    ).to_csv(COEFFICIENT_CSV, index=False)
    bootstrap.to_csv(BOOTSTRAP_CSV, index=False)
    EQUATION_JSON.write_text(
        json.dumps(equations, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    plot_results(gate_frame, event_table, predictions, skill)

    anomaly_skill = skill.loc[
        skill["target_name"].eq("stress_anomaly")
        & skill["model"].eq("dgro_state")
    ].iloc[0]
    total_skill = skill.loc[
        skill["target_name"].eq("total_stress")
        & skill["model"].eq("dgro_state")
    ].iloc[0]
    anomaly_boot = bootstrap.loc[bootstrap["target_name"].eq("stress_anomaly")].iloc[0]
    total_boot = bootstrap.loc[bootstrap["target_name"].eq("total_stress")].iloc[0]
    lag_values = event_table[
        "observed_transport_confirm_to_anomaly_gate_days"
    ].dropna().to_numpy(dtype=float)
    persistent_total_count = int(event_table["total_wind_reversal_persistent_onset"].notna().sum())
    single_total_count = int(event_table["first_single_total_stress_positive"].notna().sum())
    joint_anomaly_count = int(event_table["joint_ocean_anomaly_gate_onset"].notna().sum())
    ocean_skill_frame = gate_frame.dropna(
        subset=[
            "observed_transport_tendency_sv_day",
            "loeo_balance_signal_sv_day",
        ]
    )
    ocean_reconstruction_r = float(
        pearsonr(
            ocean_skill_frame["observed_transport_tendency_sv_day"],
            ocean_skill_frame["loeo_balance_signal_sv_day"],
        ).statistic
    )

    selected_rows = []
    for year in HIGHLIGHTS:
        row = event_table.loc[event_table["year"].eq(year)].iloc[0]
        selected_rows.append(
            f"| {year} | {date_text(row['observed_transport_acceleration_confirmation'])} | "
            f"{date_text(row['anomaly_westerly_gate_onset'])} | "
            f"{row['observed_transport_confirm_to_anomaly_gate_days'] if pd.notna(row['observed_transport_confirm_to_anomaly_gate_days']) else '—'} | "
            f"{date_text(row['total_wind_reversal_persistent_onset'])} | "
            f"{date_text(row['closest_joint_anomaly_date'])}（d={row['closest_joint_anomaly_distance']:.2f}） |"
        )

    report = f"""# 扩展Recharge Oscillator双临界面实验

## 研究对象

本实验不预测厄尔尼诺，而是用现有SODA3五日资料检验你提出的“双临界点”是否能被定位。扩展RO写成两个门：

- **海洋门** `G_O=0`：日界线暖水体积输送由减速转为加速，即 `dM/dt=0`；`G_O>0` 表示暖量开始持续向东释放。
- **大气门**有两个不等价定义：`G_A'=tau_x'=0` 是风应力异常由东风异常转为西风异常；`G_A=tau_x=0` 是总东风真正停止或反转。
- 某次事件的“转变点”不是一个固定OHC数值，而是该事件轨迹穿过两个零曲面的时刻；五日离散资料中用持续过线日和距离原点最近日表示。

物理海洋门直接用观测到的 `dM/dt` 符号定位；同时用扩展RO的D20坡度、风应力、已有输送与季节项重建这个门，以检验理论公式能否独立找回日期。大气面采用中央SST、西—中SST梯度、西部暖含量、日界线输送、D20坡度与季节项。两个重建面都做了留一事件检验，因此不是用同一事件拟合自己。

## 核心结果

### 1. 物理上有效的第二道门是异常风门，不是总风归零

13次事件中，持续 `tau_x>0` 的总风反转出现 **{persistent_total_count}/13** 次；即便只要求一个五日点为正，也只有 **{single_total_count}/13** 次。换言之，厄尔尼诺暖量向东释放和海气耦合并不要求平均东风真正停止。

因此你说的“东风停止临界点”需要改写为：**异常东风抑制何时消失，或西风异常何时建立**。这仍是明确的受力门槛，但门槛是 `tau_x'=0`，不是 `tau_x=0`。

### 2. 两道门可以建立，但没有一个跨事件固定常数

海洋门之后到异常风门建立的可判定事件滞后中位数为 **{np.median(lag_values):.0f}天**，范围 **{np.min(lag_values):.0f}至{np.max(lag_values):.0f}天**。两门同时保持正值的情况在 **{joint_anomaly_count}/13** 次事件中可识别。事件间滞后很大，说明临界点是多元状态曲面的交会，而不是“西部热含量达到X就必然转换”的单阈值。

| 事件 | 海洋门确认 | 异常风门建立 | 滞后/天 | 持续总风反转 | 离双零点最近的五日 |
|---:|---|---|---:|---|---|
{chr(10).join(selected_rows)}

### 3. 扩展状态能描述大气面，但目前只支持“诊断曲面”

扩展RO对观测海洋门 `dM/dt` 的留一事件重建相关为 **r={ocean_reconstruction_r:.2f}**，但它把1997年的持续过线放到5月底，并且没有找回2015年的稳定过线。因此，**海洋临界日目前能从SODA3输送倾向直接识别，但不能只靠简化RO方程对所有事件可靠反演**。这一区别不能省略。

异常风应力的留一事件重建相关为 **r={anomaly_skill['pearson_r']:.2f}**，零点符号正确率 **{anomaly_skill['zero_sign_accuracy']:.0%}**；总风应力为 **r={total_skill['pearson_r']:.2f}**，符号正确率 **{total_skill['zero_sign_accuracy']:.0%}**。

总风的高符号正确率没有判别价值，因为样本几乎全为负值；它只再次说明“总风归零”不是有效分类门。

相对只含SST与季节项的RO基线，加入热含量—输送—D20状态后，异常风面的事件平均MSE变化为 **{anomaly_boot['mean_delta_mse']:+.5f} N²m⁻⁴**，95%事件自助区间 **[{anomaly_boot['ci_low']:+.5f}, {anomaly_boot['ci_high']:+.5f}]**，{int(anomaly_boot['events_improved'])}/13次改善；总风面为 **{total_boot['mean_delta_mse']:+.5f}**，区间 **[{total_boot['ci_low']:+.5f}, {total_boot['ci_high']:+.5f}]**。

这一步回答的是“现有状态能否定义边界”，不回答“未来何时跨越”。如果区间跨零，就只能说多变量曲面在物理上可定义，尚不能声称扩展量稳定提高大气面的泛化重建。

## 数学表达

两个经验零曲面均写成

`(Y-Ybar)/sigma_Y = beta_0 + sum[beta_i (X_i-Xbar_i)/sigma_i] = 0`。

- 海洋门的 `Y=dM/dt`，输入为季节项、已有输送、D20压力梯度代理和风应力加速度代理。
- 大气异常门的 `Y=tau_x'`，输入为季节项、中央SST异常、西—中SST梯度、西部热含量、日界线输送和D20坡度。
- 两者同时为零给出你设想的多元临界交线；某一事件轨迹距离 `(0,0)` 最近的位置是其离散资料中的候选转变点。

完整系数、均值和尺度保存在 `{EQUATION_JSON}`，所以公式可以逐项复算。

## 能作出的结论

1. **可以建立双临界面，并用现有数据定位每次事件何时穿越。**
2. **不能把它压缩成一个固定的“受力平衡热含量值”。** 同一暖含量可对应不同D20坡度、已有输送和大气状态。
3. **2023的关键不是平均东风必须归零，而是海洋门先开后，异常风门迟开。** 这正是海气脱耦窗口。
4. 目前属于观测约束下的诊断性证明；要称为动力学因果临界点，还需要在简化模式或耦合模式中跨曲面做扰动实验。

## 输出

- 主图：`{FIGURE_PNG}` 与 `{FIGURE_SVG}`
- 13事件临界日期表：`{EVENT_CSV}`
- 五日门变量：`{PENTAD_CSV}`
- 留一事件技巧：`{SKILL_CSV}`
- 方程系数：`{EQUATION_JSON}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
