#!/usr/bin/env python3
"""Leave-one-event-out test of SODA3 warm-water transport gates."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((ROOT / "scripts").resolve()))

from analyze_soda3_transition_processes import (  # noqa: E402
    benjamini_hochberg,
    bootstrap_skill,
    paired_improvement_p,
    predict_event_fold,
)


BASE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
)
INDEX_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_mixed_layer_budget_indices_1980_2024.csv"
)
EVENT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_event_summary_1982_2023.csv"
)
OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_next_stage"
PREDICTION_CSV = OUT_DATA / "soda3_gate_loeo_predictions.csv"
SKILL_CSV = OUT_DATA / "soda3_gate_loeo_skill.csv"
SUMMARY_MD = OUT_DIR / "SODA3_GATE_PREDICTABILITY_CN.md"

MODELS = {
    "Type persistence": ("init_type_raw_c",),
    "+ dateline transport": (
        "init_type_raw_c",
        "q20_dateline_pw_anom",
    ),
    "+ 160W transport": (
        "init_type_raw_c",
        "q20_200e_pw_anom",
    ),
    "+ 140W transport": (
        "init_type_raw_c",
        "q20_220e_pw_anom",
    ),
    "+ eastern warm tendency": (
        "init_type_raw_c",
        "warm_excess_east_tendency_wm2_anom",
    ),
}


def build_monthly() -> pd.DataFrame:
    base = pd.read_csv(BASE_CSV)
    event_years = pd.read_csv(EVENT_CSV)["event_year"].astype(int)
    base = base.loc[base["year"].isin(event_years)].copy()
    indices = pd.read_csv(INDEX_CSV)
    columns = [
        "year",
        "month",
        "q20_dateline_pw_anom",
        "q20_200e_pw_anom",
        "q20_220e_pw_anom",
        "warm_excess_east_tendency_wm2_anom",
    ]
    return base.merge(
        indices[columns],
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )


def predictions(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month in range(2, 7):
        current = monthly.loc[monthly["month"].eq(month)].copy()
        for event_year in current["year"].astype(int):
            test = current.loc[current["year"].eq(event_year)].iloc[0]
            train = current.loc[current["year"].ne(event_year)]
            for model, features in MODELS.items():
                prediction, observed = predict_event_fold(
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
                    }
                )
    return pd.DataFrame(rows)


def skill_table(prediction: pd.DataFrame) -> pd.DataFrame:
    baseline = prediction.loc[
        prediction["model"].eq("Type persistence"),
        [
            "event_year",
            "month",
            "prediction_type_residual_c",
        ],
    ].rename(
        columns={"prediction_type_residual_c": "baseline_prediction_c"}
    )
    merged = prediction.merge(
        baseline,
        on=["event_year", "month"],
        how="left",
        validate="many_to_one",
    )
    rows = []
    seed = 8100
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
        rmse_skill = 1.0 - rmse / baseline_rmse
        if model == "Type persistence":
            p_value = np.nan
            ci_low = np.nan
            ci_high = np.nan
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
                seed + 1000,
            )
        seed += 1
        rows.append(
            {
                "month": month,
                "model": model,
                "rmse_c": rmse,
                "baseline_rmse_c": baseline_rmse,
                "rmse_skill_vs_type_persistence": rmse_skill,
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
        "bh_fdr_q_across_added_model_month_family",
    ] = benjamini_hochberg(
        output.loc[added, "one_sided_paired_improvement_p"]
    )
    return output


def write_summary(skill: pd.DataFrame) -> None:
    gate = skill.loc[skill["model"].eq("+ 140W transport")].sort_values(
        "month"
    )
    lines = "\n".join(
        f"- {int(row.month)}月：RMSE skill="
        f"{row.rmse_skill_vs_type_persistence:+.3f}，"
        f"p={row.one_sided_paired_improvement_p:.3f}，"
        f"q={row.bh_fdr_q_across_added_model_month_family:.3f}，"
        f"95% bootstrap区间"
        f"[{row.bootstrap_skill_ci_low:+.3f}, "
        f"{row.bootstrap_skill_ci_high:+.3f}]。"
        for row in gate.itertuples()
    )
    best = gate.sort_values(
        "rmse_skill_vs_type_persistence",
        ascending=False,
    ).iloc[0]
    text = f"""# 140°W暖水闸门的留一事件预测检验

## 设计

13个暖事件逐一留出；每一折只用其余12个事件去趋势、标准化和训练。
基线为当月已经存在的Niño3−Niño4型态，新增量分别为日界线、160°W、
140°W暖水输送或东部暖含量倾向。预测目标为成熟DJF Niño3−Niño4。

## 140°W结果

{lines}

最佳结果出现在{int(best['month'])}月，skill=
{best['rmse_skill_vs_type_persistence']:+.3f}，但没有通过配对改进检验。
所有新增模型×月份统一FDR后均不显著。

## 解释

140°W输送是目前最强的机制分型指标，但尚未证明它在小样本留一预测中
提供独立于当月SST型态的稳定增量。报告中应写“有潜力的过程预测因子”
或“动力检查点”，不能写成“已显著提高预测技巧”。

这项阴性结果不否定机制：13个事件、强EP事件较少，且140°W输送与当月
SST型态共享信息。要证明预测价值，需要扩大事件/集合样本，或把它用于
实时概率更新而不是单一线性点预测。

## 文件

- 留一预测：`{PREDICTION_CSV}`
- 技巧表：`{SKILL_CSV}`
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(text, encoding="utf-8")


def main() -> int:
    monthly = build_monthly()
    prediction = predictions(monthly)
    skill = skill_table(prediction)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    prediction.to_csv(PREDICTION_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    write_summary(skill)
    print(f"Wrote {PREDICTION_CSV}", flush=True)
    print(f"Wrote {SKILL_CSV}", flush=True)
    print(f"Wrote {SUMMARY_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
