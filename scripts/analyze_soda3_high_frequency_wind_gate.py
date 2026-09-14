#!/usr/bin/env python3
"""Add a strictly lagged five-day westerly-memory gate to SODA3 OHC models."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

RUNTIME_CACHE = Path("/private/tmp/codex_soda3_high_frequency_wind_gate_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_soda3_5day_ohc_geometry_coupling as base  # noqa: E402


DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_high_frequency_wind_gate"
PRIMARY_PREDICTIONS_CSV = DERIVED / "soda3_high_frequency_wind_gate_primary_loeo_predictions.csv"
DURABLE_PREDICTIONS_CSV = DERIVED / "soda3_high_frequency_wind_gate_durable_loeo_predictions.csv"
PRIMARY_SKILL_CSV = DERIVED / "soda3_high_frequency_wind_gate_primary_skill.csv"
DURABLE_SKILL_CSV = DERIVED / "soda3_high_frequency_wind_gate_durable_skill.csv"
COEFFICIENTS_CSV = DERIVED / "soda3_high_frequency_wind_gate_loeo_coefficients.csv"
EVENT_DELTAS_CSV = DERIVED / "soda3_high_frequency_wind_gate_event_brier_deltas.csv"
RISK_SET_CSV = DERIVED / "soda3_high_frequency_wind_gate_risk_set.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_high_frequency_wind_gate_diagnostics.json"
FIGURE_PNG = OUT / "soda3_high_frequency_wind_gate_skill.png"
REPORT_MD = OUT / "SODA3_HIGH_FREQUENCY_WIND_GATE_RESULT_CN.md"

RNG_SEED = 20260802
N_BOOTSTRAP = 10000
GATE_COLUMN = "lagged_positive_westerly_impulse15_nm2"

BASE_FEATURES = [
    "season_sin",
    "season_cos",
    "ohc300_positive_total_pj_m_15day",
    "ohc300_positive_total_pj_m_change15day",
]
GEOMETRY_FEATURES = [
    "ohc300_positive_east140w_fraction_15day",
    "ohc300_positive_east140w_fraction_change15day",
]
MODEL_FEATURES = {
    "heat_only": BASE_FEATURES,
    "ocean_geometry": BASE_FEATURES + GEOMETRY_FEATURES,
    "wind_memory": BASE_FEATURES + [GATE_COLUMN],
    "ocean_plus_wind": BASE_FEATURES + GEOMETRY_FEATURES + [GATE_COLUMN],
}


def add_strictly_lagged_wind_gate(indices: pd.DataFrame) -> pd.DataFrame:
    """Use the three completed pentads before t; never include stress at t."""
    pieces = []
    for year, group in indices.groupby("year", sort=True):
        current = group.sort_values("time").copy()
        stress = current["taux_central_180_220e_anom_nm2"].astype(float)
        completed_positive = stress.shift(1).clip(lower=0.0)
        completed_flag = stress.shift(1).gt(0.0).astype(float)
        current[GATE_COLUMN] = completed_positive.rolling(3, min_periods=3).mean()
        current["lagged_positive_westerly_pentads15"] = completed_flag.rolling(
            3, min_periods=3
        ).sum()
        current["lagged_mean_taux15_nm2"] = stress.shift(1).rolling(
            3, min_periods=3
        ).mean()
        current["wind_gate_latest_source_time"] = pd.to_datetime(current["time"]).shift(1)
        if current[GATE_COLUMN].dropna().lt(0.0).any():
            raise ValueError(f"Negative positive-westerly impulse in {year}")
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True).sort_values(["year", "time"])


def build_gated_risk(
    indices: pd.DataFrame,
    *,
    positive_count: int = base.ONSET_POSITIVE_COUNT,
    window_pentads: int = base.ONSET_WINDOW_PENTADS,
) -> pd.DataFrame:
    gate = add_strictly_lagged_wind_gate(indices)
    risk = base.build_risk_set(
        indices,
        positive_count=positive_count,
        window_pentads=window_pentads,
    )
    columns = [
        "year",
        "time",
        GATE_COLUMN,
        "lagged_positive_westerly_pentads15",
        "lagged_mean_taux15_nm2",
        "wind_gate_latest_source_time",
    ]
    output = risk.merge(
        gate[columns],
        on=["year", "time"],
        how="left",
        validate="one_to_one",
    )
    if output[columns[2:]].isna().any().any():
        raise ValueError("Missing lagged wind-memory values in risk set")
    latest = pd.to_datetime(output["wind_gate_latest_source_time"])
    forecast = pd.to_datetime(output["time"])
    lag_days = (forecast - latest).dt.days
    if not lag_days.between(4, 6).all():
        raise ValueError("The wind gate is not strictly one pentad behind forecast time")
    return output.sort_values(["year", "time"]).reset_index(drop=True)


def loeo(
    risk: pd.DataFrame,
    outcome_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_rows = []
    coefficient_rows = []
    years = sorted(risk["year"].unique())
    for held_year in years:
        train = risk.loc[risk["year"] != held_year]
        test = risk.loc[risk["year"] == held_year]
        train_weights = base.event_balancing_weights(train["year"])
        for model_name, features in MODEL_FEATURES.items():
            model = base.make_model()
            model.fit(
                train[features].to_numpy(dtype=float),
                train["onset_within_20day"].to_numpy(dtype=int),
                logistic__sample_weight=train_weights,
            )
            probability = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
            for row, value in zip(test.itertuples(), probability, strict=True):
                prediction_rows.append(
                    {
                        "outcome": outcome_label,
                        "time": row.time,
                        "year": int(row.year),
                        "observed_onset_within_20day": int(row.onset_within_20day),
                        "model": model_name,
                        "probability": float(value),
                    }
                )
            coefficients = model.named_steps["logistic"].coef_[0]
            for feature, coefficient in zip(features, coefficients, strict=True):
                coefficient_rows.append(
                    {
                        "outcome": outcome_label,
                        "held_year": int(held_year),
                        "model": model_name,
                        "feature": feature,
                        "standardized_logit_coefficient": float(coefficient),
                    }
                )
    return pd.DataFrame(prediction_rows), pd.DataFrame(coefficient_rows)


def event_brier_table(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model_name, year), event in predictions.groupby(["model", "year"]):
        observed = event["observed_onset_within_20day"].to_numpy(dtype=float)
        probability = event["probability"].to_numpy(dtype=float)
        rows.append(
            {
                "outcome": event["outcome"].iloc[0],
                "model": model_name,
                "year": int(year),
                "event_brier": float(np.mean((probability - observed) ** 2)),
            }
        )
    table = pd.DataFrame(rows)
    heat = table.loc[table["model"] == "heat_only", ["year", "event_brier"]].rename(
        columns={"event_brier": "heat_only_event_brier"}
    )
    ocean = table.loc[
        table["model"] == "ocean_geometry", ["year", "event_brier"]
    ].rename(columns={"event_brier": "ocean_geometry_event_brier"})
    table = table.merge(heat, on="year", validate="many_to_one").merge(
        ocean, on="year", validate="many_to_one"
    )
    table["delta_brier_vs_heat_only"] = (
        table["event_brier"] - table["heat_only_event_brier"]
    )
    table["delta_brier_vs_ocean_geometry"] = (
        table["event_brier"] - table["ocean_geometry_event_brier"]
    )
    return table.sort_values(["model", "year"]).reset_index(drop=True)


def bootstrap_mean_ci(values: np.ndarray, seed_offset: int) -> tuple[float, float]:
    rng = np.random.default_rng(RNG_SEED + seed_offset)
    draws = np.empty(N_BOOTSTRAP, dtype=float)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(values), len(values))
        draws[index] = float(np.mean(values[sample]))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def summarize_skill(
    predictions: pd.DataFrame,
    coefficients: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_table = event_brier_table(predictions)
    rows = []
    for model_index, (model_name, group) in enumerate(
        predictions.groupby("model", sort=False)
    ):
        weights = base.event_balancing_weights(group["year"])
        observed = group["observed_onset_within_20day"].to_numpy(dtype=int)
        probability = group["probability"].to_numpy(dtype=float)
        events = event_table.loc[event_table["model"] == model_name]
        delta_heat = events["delta_brier_vs_heat_only"].to_numpy(dtype=float)
        delta_ocean = events["delta_brier_vs_ocean_geometry"].to_numpy(dtype=float)
        heat_ci = bootstrap_mean_ci(delta_heat, model_index * 2)
        ocean_ci = bootstrap_mean_ci(delta_ocean, model_index * 2 + 1)
        gate_coefficients = coefficients.loc[
            coefficients["model"].eq(model_name)
            & coefficients["feature"].eq(GATE_COLUMN),
            "standardized_logit_coefficient",
        ].to_numpy(dtype=float)
        rows.append(
            {
                "model": model_name,
                "event_weighted_brier": base.weighted_brier(
                    observed, probability, weights
                ),
                "event_weighted_auc": float(
                    roc_auc_score(observed, probability, sample_weight=weights)
                ),
                "event_weighted_log_loss": float(
                    log_loss(
                        observed,
                        probability,
                        sample_weight=weights,
                        labels=[0, 1],
                    )
                ),
                "delta_brier_vs_heat_only": float(np.mean(delta_heat)),
                "delta_brier_vs_heat_ci_low": heat_ci[0],
                "delta_brier_vs_heat_ci_high": heat_ci[1],
                "delta_brier_vs_ocean_geometry": float(np.mean(delta_ocean)),
                "delta_brier_vs_ocean_ci_low": ocean_ci[0],
                "delta_brier_vs_ocean_ci_high": ocean_ci[1],
                "events_improved_vs_ocean_geometry": int(np.sum(delta_ocean < 0.0)),
                "events_total": len(delta_ocean),
                "wind_gate_coefficient_median": (
                    np.nan
                    if not len(gate_coefficients)
                    else float(np.median(gate_coefficients))
                ),
                "wind_gate_positive_fold_fraction": (
                    np.nan
                    if not len(gate_coefficients)
                    else float(np.mean(gate_coefficients > 0.0))
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("event_weighted_brier"), event_table


def set_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 8.5,
            "axes.linewidth": 0.8,
            "savefig.dpi": 320,
        }
    )


def plot_results(
    primary_skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    event_deltas: pd.DataFrame,
    gated_indices: pd.DataFrame,
    summaries: pd.DataFrame,
) -> None:
    set_style()
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.5), constrained_layout=True)

    comparisons = (
        (
            primary_skill,
            "wind_memory",
            "delta_brier_vs_heat_only",
            "delta_brier_vs_heat_ci_low",
            "delta_brier_vs_heat_ci_high",
            "#b2182b",
            "o",
            "30d: wind vs heat",
        ),
        (
            primary_skill,
            "ocean_plus_wind",
            "delta_brier_vs_ocean_geometry",
            "delta_brier_vs_ocean_ci_low",
            "delta_brier_vs_ocean_ci_high",
            "#b2182b",
            "s",
            "30d: ocean+wind vs ocean",
        ),
        (
            durable_skill,
            "wind_memory",
            "delta_brier_vs_heat_only",
            "delta_brier_vs_heat_ci_low",
            "delta_brier_vs_heat_ci_high",
            "#2166ac",
            "o",
            "60d: wind vs heat",
        ),
        (
            durable_skill,
            "ocean_plus_wind",
            "delta_brier_vs_ocean_geometry",
            "delta_brier_vs_ocean_ci_low",
            "delta_brier_vs_ocean_ci_high",
            "#2166ac",
            "s",
            "60d: ocean+wind vs ocean",
        ),
    )
    comparison_labels = []
    for y, (skill, model, value_column, low_column, high_column, color, marker, label) in enumerate(
        comparisons
    ):
        row = skill.loc[skill["model"] == model].iloc[0]
        value = float(row[value_column])
        errors = np.asarray(
            [
                [value - float(row[low_column])],
                [float(row[high_column]) - value],
            ]
        )
        axes[0].errorbar(
            value,
            y,
            xerr=errors,
            fmt=marker,
            color=color,
            capsize=4,
            ms=6,
        )
        comparison_labels.append(label)
    axes[0].axvline(0.0, color="0.25", lw=0.8)
    axes[0].set_yticks(np.arange(len(comparison_labels)), comparison_labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Paired LOEO Brier change")
    axes[0].set_title("a  Incremental predictive skill", loc="left", fontweight="bold")
    axes[0].text(0.02, 0.03, "Better ←", transform=axes[0].transAxes, color="0.35")
    axes[0].spines[["top", "right"]].set_visible(False)

    models = event_deltas.loc[event_deltas["model"] == "ocean_plus_wind"].copy()
    for outcome, color, marker, offset, label in (
        ("30day_episode", "#b2182b", "o", -0.11, "30-day"),
        ("60day_durable", "#2166ac", "s", 0.11, "60-day"),
    ):
        current = models.loc[models["outcome"] == outcome].sort_values("year")
        y = np.arange(len(current)) + offset
        axes[1].scatter(
            current["delta_brier_vs_ocean_geometry"],
            y,
            color=color,
            marker=marker,
            s=24,
            label=label,
            zorder=3,
        )
    years = sorted(models["year"].unique())
    axes[1].axvline(0.0, color="0.25", lw=0.8)
    axes[1].set_yticks(np.arange(len(years)), years)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Event Brier change vs ocean geometry")
    axes[1].set_title("b  Event-to-event stability", loc="left", fontweight="bold")
    axes[1].legend(frameon=False, fontsize=7.5, loc="lower right")
    axes[1].spines[["top", "right"]].set_visible(False)

    event = gated_indices.loc[gated_indices["year"] == 2023].sort_values("time")
    ocean_line = axes[2].plot(
        event["time"],
        event["ohc300_positive_east140w_fraction_15day"],
        color="#1b7837",
        lw=1.8,
        label="East-of-140°W heat fraction",
    )[0]
    axes[2].set_ylim(0.0, 1.0)
    axes[2].set_ylabel("East-of-140°W positive-OHC fraction", color="#1b7837")
    axes[2].tick_params(axis="y", colors="#1b7837")
    axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    wind_axis = axes[2].twinx()
    wind_line = wind_axis.plot(
        event["time"],
        event[GATE_COLUMN],
        color="#e08214",
        lw=1.5,
        label="Lagged 15-day westerly impulse",
    )[0]
    wind_axis.set_ylabel("Lagged positive stress impulse (N m$^{-2}$)", color="#e08214")
    wind_axis.tick_params(axis="y", colors="#e08214")
    row = summaries.loc[summaries["year"] == 2023].iloc[0]
    short_date = pd.Timestamp(row["coupling_onset_date"])
    durable_date = pd.Timestamp(row["sensitivity_8of12_durable_onset_date"])
    axes[2].axvline(short_date, color="#111111", lw=1.1)
    axes[2].axvline(durable_date, color="#2166ac", lw=1.1, ls="--")
    handles = [
        ocean_line,
        wind_line,
        mpl.lines.Line2D([], [], color="#111111", lw=1.1, label="30-day onset"),
        mpl.lines.Line2D(
            [], [], color="#2166ac", lw=1.1, ls="--", label="60-day onset"
        ),
    ]
    axes[2].legend(handles=handles, frameon=False, fontsize=7.1, loc="upper left")
    axes[2].set_title("c  2023 event sequence", loc="left", fontweight="bold")
    axes[2].spines["top"].set_visible(False)
    wind_axis.spines["top"].set_visible(False)

    fig.suptitle(
        "Does strictly lagged westerly memory improve SODA3 heat-based onset prediction?",
        fontsize=12.5,
        fontweight="bold",
    )
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    plt.close(fig)


def robust_increment(skill: pd.DataFrame) -> bool:
    row = skill.loc[skill["model"] == "ocean_plus_wind"].iloc[0]
    return bool(
        row["delta_brier_vs_ocean_ci_high"] < 0.0
        and row["events_improved_vs_ocean_geometry"] >= 7
        and row["wind_gate_positive_fold_fraction"] >= 0.75
    )


def write_report(
    primary_skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    event_deltas: pd.DataFrame,
    summaries: pd.DataFrame,
) -> None:
    primary_ocean = primary_skill.loc[primary_skill["model"] == "ocean_geometry"].iloc[0]
    primary_wind = primary_skill.loc[primary_skill["model"] == "wind_memory"].iloc[0]
    primary_both = primary_skill.loc[primary_skill["model"] == "ocean_plus_wind"].iloc[0]
    durable_ocean = durable_skill.loc[durable_skill["model"] == "ocean_geometry"].iloc[0]
    durable_wind = durable_skill.loc[durable_skill["model"] == "wind_memory"].iloc[0]
    durable_both = durable_skill.loc[durable_skill["model"] == "ocean_plus_wind"].iloc[0]
    primary_pass = robust_increment(primary_skill)
    durable_pass = robust_increment(durable_skill)
    if durable_pass:
        if durable_both["event_weighted_brier"] < durable_skill.loc[
            durable_skill["model"] == "heat_only", "event_weighted_brier"
        ].iloc[0]:
            judgment = (
                "严格滞后的15日西风冲量在海洋热量位置之外，通过了耐久接通的预设增量条件，"
                "且组合模型优于简单热量基线。它可作为候选高频大气门，但仍需独立风或对流资料复核。"
            )
        else:
            judgment = (
                "严格滞后的15日西风冲量通过了相对海洋位置模型的耐久接通增量条件，"
                "但组合模型仍不如更简单的仅热量基线。这说明高频风能够修正部分海洋位置误判，"
                "尚未形成总体更优的最终预测公式。"
            )
    elif primary_pass:
        judgment = (
            "高频西风门只通过30天短西风段检验，没有通过60天耐久接通检验。"
            "它应解释为短期风记忆或接通临近信号，而不是事件类型转变点。"
        )
    else:
        judgment = (
            "单一15日西风冲量没有在海洋热量位置之外形成稳定增量信息，不能作为通用接通开关。"
        )
    event_2023 = event_deltas.loc[
        (event_deltas["year"] == 2023)
        & (event_deltas["model"] == "ocean_plus_wind")
    ].set_index("outcome")
    short_2023 = float(
        event_2023.loc["30day_episode", "delta_brier_vs_ocean_geometry"]
    )
    durable_2023 = float(
        event_2023.loc["60day_durable", "delta_brier_vs_ocean_geometry"]
    )
    text = f"""# SODA3热含量加入五日西风持续性门：结果

## 方法

高频大气门定义为预测日前三个已经完成五日的正中太平洋纬向风应力冲量均值。该指标严格不含预测时次及未来风。比较仅热量、热量位置、热量加风记忆、热量位置加风记忆四个模型，按完整事件留一验证未来20天的30天西风段和60天耐久接通。

## 30天西风段

- 海洋位置模型Brier={primary_ocean['event_weighted_brier']:.4f}；只加入风记忆的模型Brier={primary_wind['event_weighted_brier']:.4f}；海洋位置加风记忆Brier={primary_both['event_weighted_brier']:.4f}。
- 风记忆模型相对仅热量基线的Brier变化为{primary_wind['delta_brier_vs_heat_only']:+.4f}，95%区间[{primary_wind['delta_brier_vs_heat_ci_low']:+.4f}, {primary_wind['delta_brier_vs_heat_ci_high']:+.4f}]。
- 海洋位置加风记忆相对海洋位置的Brier变化为{primary_both['delta_brier_vs_ocean_geometry']:+.4f}，95%区间[{primary_both['delta_brier_vs_ocean_ci_low']:+.4f}, {primary_both['delta_brier_vs_ocean_ci_high']:+.4f}]。
- {int(primary_both['events_improved_vs_ocean_geometry'])}/{int(primary_both['events_total'])}个有效事件得到改善；风门系数在{primary_both['wind_gate_positive_fold_fraction']:.0%}的留一训练折中为正。

## 60天耐久接通

- 海洋位置模型Brier={durable_ocean['event_weighted_brier']:.4f}；只加入风记忆的模型Brier={durable_wind['event_weighted_brier']:.4f}；海洋位置加风记忆Brier={durable_both['event_weighted_brier']:.4f}。
- 风记忆模型相对仅热量基线的Brier变化为{durable_wind['delta_brier_vs_heat_only']:+.4f}，95%区间[{durable_wind['delta_brier_vs_heat_ci_low']:+.4f}, {durable_wind['delta_brier_vs_heat_ci_high']:+.4f}]；海洋位置加风记忆相对仅热量基线仍为{durable_both['delta_brier_vs_heat_only']:+.4f}。
- 海洋位置加风记忆相对海洋位置的Brier变化为{durable_both['delta_brier_vs_ocean_geometry']:+.4f}，95%区间[{durable_both['delta_brier_vs_ocean_ci_low']:+.4f}, {durable_both['delta_brier_vs_ocean_ci_high']:+.4f}]。
- {int(durable_both['events_improved_vs_ocean_geometry'])}/{int(durable_both['events_total'])}个有效事件得到改善；风门系数在{durable_both['wind_gate_positive_fold_fraction']:.0%}的留一训练折中为正。

## 2023个例

2023年海洋位置加风记忆相对海洋位置的事件Brier变化：30天目标{short_2023:+.4f}，60天目标{durable_2023:+.4f}。30天西风段起始于{summaries.loc[summaries['year'].eq(2023), 'coupling_onset_date'].iloc[0]}，60天耐久接通起始于{summaries.loc[summaries['year'].eq(2023), 'sensitivity_8of12_durable_onset_date'].iloc[0]}。

## 判断

{judgment}

这一步检验的是“已经发生的短期西风是否在海洋准备度之外具有前兆信息”。即使通过，也不能用来证明西风脉冲的因果性；若仅对30天目标有效，尤其要避免把自相关造成的临近识别写成类型转换机制。
"""
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    indices = base.load_indices(base.INPUT_INDEX)
    gated_indices = add_strictly_lagged_wind_gate(indices)
    summaries = base.event_summary(indices)
    primary_risk = build_gated_risk(indices)
    durable_risk = build_gated_risk(
        indices,
        positive_count=base.DURABLE_POSITIVE_COUNT,
        window_pentads=base.DURABLE_WINDOW_PENTADS,
    )
    primary_predictions, primary_coefficients = loeo(primary_risk, "30day_episode")
    durable_predictions, durable_coefficients = loeo(durable_risk, "60day_durable")
    primary_skill, primary_events = summarize_skill(
        primary_predictions, primary_coefficients
    )
    durable_skill, durable_events = summarize_skill(
        durable_predictions, durable_coefficients
    )
    coefficients = pd.concat(
        [primary_coefficients, durable_coefficients], ignore_index=True
    )
    event_deltas = pd.concat([primary_events, durable_events], ignore_index=True)
    primary_predictions.to_csv(PRIMARY_PREDICTIONS_CSV, index=False)
    durable_predictions.to_csv(DURABLE_PREDICTIONS_CSV, index=False)
    primary_skill.to_csv(PRIMARY_SKILL_CSV, index=False)
    durable_skill.to_csv(DURABLE_SKILL_CSV, index=False)
    coefficients.to_csv(COEFFICIENTS_CSV, index=False)
    event_deltas.to_csv(EVENT_DELTAS_CSV, index=False)
    pd.concat(
        [
            primary_risk.assign(outcome="30day_episode"),
            durable_risk.assign(outcome="60day_durable"),
        ],
        ignore_index=True,
    ).to_csv(RISK_SET_CSV, index=False)
    diagnostics = {
        "gate_definition": (
            "mean positive central-Pacific stress anomaly over the three completed "
            "pentads before forecast time; excludes forecast pentad"
        ),
        "gate_units": "N m-2",
        "primary_risk_rows": len(primary_risk),
        "durable_risk_rows": len(durable_risk),
        "primary_events": sorted(primary_risk["year"].unique().tolist()),
        "durable_events": sorted(durable_risk["year"].unique().tolist()),
        "minimum_source_lag_days": int(
            (
                pd.to_datetime(primary_risk["time"])
                - pd.to_datetime(primary_risk["wind_gate_latest_source_time"])
            ).dt.days.min()
        ),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    plot_results(primary_skill, durable_skill, event_deltas, gated_indices, summaries)
    write_report(primary_skill, durable_skill, event_deltas, summaries)
    print("Primary 30-day episode")
    print(primary_skill.to_string(index=False))
    print("\nDurable 60-day onset")
    print(durable_skill.to_string(index=False))
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
