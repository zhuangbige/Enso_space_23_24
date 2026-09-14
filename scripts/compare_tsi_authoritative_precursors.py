#!/usr/bin/env python3
"""Compare the April TSI with a published pre-spring ENSO type precursor.

The comparison reproduces the Ludescher et al. (2023) December
DeltaT(WP-CP) definition with ERSSTv5 and a strictly trailing 30-year
climatology, then evaluates it on exactly the 13 warm events used by the
SODA3 analysis.  All regression preprocessing is refitted inside each
validation fold.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_precursor_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import binomtest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((ROOT / "scripts").resolve()))

from analyze_soda3_transition_processes import (  # noqa: E402
    benjamini_hochberg,
    bootstrap_skill,
    paired_improvement_p,
)
from finalize_dual_path_enso_predictor import (  # noqa: E402
    ANALYSIS_CSV,
    EVENT_YEARS,
    RIDGE_ALPHA,
    detrend_fold,
    fold_feature_values,
    standardized_fold,
    weighted_box,
)


ERSST_NC = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
INDEX_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ersstv5_ludescher_wp_cp_december_precursor_1981_2025.csv"
)
LOEO_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "tsi_authoritative_precursor_loeo_skill.csv"
)
CHRONO_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "tsi_authoritative_precursor_chronological_skill.csv"
)
CLASS_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "tsi_authoritative_precursor_classification.csv"
)
FIGURE_PDF = ROOT / "output/pdf/tsi_vs_authoritative_precursors.pdf"
FIGURE_PNG = (
    ROOT
    / "outputs/research_2026/final_dual_path_predictor/"
    "tsi_vs_authoritative_precursors.png"
)
REPORT_MD = (
    ROOT
    / "outputs/research_2026/final_dual_path_predictor/"
    "TSI_AUTHORITATIVE_COMPARISON_CN.md"
)


MODEL_FEATURES = {
    "April SST type": ("sst_type",),
    "Prior-Dec WP-CP": ("prior_dec",),
    "April SST + prior-Dec": ("sst_type", "prior_dec"),
    "April SST + TSI": ("sst_type", "deep_route"),
    "April SST + TSI + prior-Dec": (
        "sst_type",
        "deep_route",
        "prior_dec",
    ),
}


def build_prior_dec_index() -> pd.DataFrame:
    with xr.open_dataset(ERSST_NC, engine="h5netcdf") as dataset:
        sst = dataset["sst"].sel(
            time=dataset.time.dt.month == 12,
        )
        wp = weighted_box(sst, 120.0, 165.0).load()
        cp = weighted_box(sst, 165.0, 210.0).load()
    times = pd.DatetimeIndex(pd.to_datetime(wp.time.values))
    raw = np.asarray(wp.values - cp.values, dtype=float)
    rows = []
    for index, time in enumerate(times):
        year = int(time.year)
        previous = raw[
            (times.year >= year - 30)
            & (times.year <= year - 1)
        ]
        if len(previous) != 30:
            continue
        rows.append(
            {
                "december_year": year,
                "event_year": year + 1,
                "wp_minus_cp_raw_c": raw[index],
                "trailing_30yr_mean_c": float(np.mean(previous)),
                "prior_dec_wp_minus_cp_c": float(
                    raw[index] - np.mean(previous)
                ),
                "climatology_start": year - 30,
                "climatology_end": year - 1,
            }
        )
    return pd.DataFrame(rows)


def predict_fold(
    train: pd.DataFrame,
    test: pd.Series,
    model: str,
) -> tuple[float, float]:
    target, observed = detrend_fold(
        train["year"].to_numpy(dtype=float),
        train["mature_djf_type_raw_c"].to_numpy(dtype=float),
        float(test["year"]),
        float(test["mature_djf_type_raw_c"]),
    )
    train_features, test_features = fold_feature_values(train, test)
    (
        train_features["prior_dec"],
        test_features["prior_dec"],
    ) = standardized_fold(
        train,
        test,
        "prior_dec_wp_minus_cp_c",
    )
    names = MODEL_FEATURES[model]
    x_train = np.column_stack(
        [train_features[name] for name in names]
    )
    x_test = np.asarray([test_features[name] for name in names])
    coefficients = np.linalg.solve(
        x_train.T @ x_train
        + RIDGE_ALPHA * np.eye(len(names)),
        x_train.T @ target,
    )
    return float(x_test @ coefficients), observed


def predictions(
    event: pd.DataFrame,
    *,
    chronological: bool,
) -> pd.DataFrame:
    rows = []
    for year in EVENT_YEARS:
        if chronological:
            train = event.loc[event["year"].lt(year)]
            if len(train) < 6:
                continue
        else:
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
                }
            )
    return pd.DataFrame(rows)


def skill_table(
    prediction: pd.DataFrame,
    label: str,
) -> pd.DataFrame:
    baseline = prediction.loc[
        prediction["model"].eq("April SST type"),
        ["year", "prediction_type_residual_c"],
    ].rename(
        columns={"prediction_type_residual_c": "baseline_prediction_c"}
    )
    rows = []
    for index, model in enumerate(MODEL_FEATURES):
        current = prediction.loc[
            prediction["model"].eq(model)
        ].merge(
            baseline,
            on="year",
            validate="one_to_one",
        )
        observed = current["observed_type_residual_c"].to_numpy()
        predicted = current["prediction_type_residual_c"].to_numpy()
        reference = current["baseline_prediction_c"].to_numpy()
        rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
        baseline_rmse = float(
            np.sqrt(np.mean((reference - observed) ** 2))
        )
        if model == "April SST type":
            p_value = ci_low = ci_high = np.nan
        else:
            p_value = paired_improvement_p(
                observed,
                predicted,
                reference,
                180_000 + index,
            )
            ci_low, ci_high = bootstrap_skill(
                observed,
                predicted,
                reference,
                190_000 + index,
            )
        rows.append(
            {
                "validation": label,
                "model": model,
                "n_test": len(current),
                "rmse_c": rmse,
                "rmse_skill_vs_april_sst": 1.0 - rmse / baseline_rmse,
                "prediction_observation_r": float(
                    np.corrcoef(predicted, observed)[0, 1]
                ),
                "one_sided_paired_improvement_p": p_value,
                "bootstrap_skill_ci_low": ci_low,
                "bootstrap_skill_ci_high": ci_high,
            }
        )
    output = pd.DataFrame(rows)
    mask = output["model"].ne("April SST type")
    output.loc[mask, "bh_fdr_q"] = benjamini_hochberg(
        output.loc[mask, "one_sided_paired_improvement_p"]
    )
    return output


def classification_table(event: pd.DataFrame) -> pd.DataFrame:
    output = event[
        [
            "year",
            "mature_djf_type_index_c",
            "prior_dec_wp_minus_cp_c",
        ]
    ].copy()
    output["observed_sign"] = np.sign(
        output["mature_djf_type_index_c"]
    ).astype(int)
    output["predicted_sign"] = np.sign(
        output["prior_dec_wp_minus_cp_c"]
    ).astype(int)
    output["correct"] = output["observed_sign"].eq(
        output["predicted_sign"]
    )
    output["clear_type_abs_ge_0p2"] = (
        output["mature_djf_type_index_c"].abs().ge(0.2)
    )
    return output


def make_figure(
    event: pd.DataFrame,
    classification: pd.DataFrame,
    loeo_skill: pd.DataFrame,
    chronological_skill: pd.DataFrame,
) -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial"],
            "font.size": 9,
            "pdf.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.4, 4.9))
    fig.subplots_adjust(
        left=0.07,
        right=0.985,
        top=0.82,
        bottom=0.18,
        wspace=0.35,
    )

    axis = axes[0]
    colors = np.where(
        event["mature_djf_type_index_c"].ge(0),
        "#B43C2D",
        "#2A72A5",
    )
    axis.scatter(
        event["prior_dec_wp_minus_cp_c"],
        event["mature_djf_type_index_c"],
        c=colors,
        s=48,
        edgecolor="white",
        linewidth=0.7,
    )
    for row in event.itertuples():
        axis.annotate(
            str(row.year),
            (
                row.prior_dec_wp_minus_cp_c,
                row.mature_djf_type_index_c,
            ),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=6.8,
        )
    axis.axhline(0, color="0.55", lw=0.8)
    axis.axvline(0, color="0.55", lw=0.8)
    correlation = np.corrcoef(
        event["prior_dec_wp_minus_cp_c"],
        event["mature_djf_type_index_c"],
    )[0, 1]
    axis.set_xlabel("Prior-Dec ERSSTv5 ΔT(WP−CP) (°C)")
    axis.set_ylabel("Mature DJF Niño3−Niño4 (°C)")
    axis.set_title(
        f"(a) Published long-lead precursor\nN=13, r={correlation:+.2f}",
        loc="left",
        weight="bold",
    )

    keep = [
        "Prior-Dec WP-CP",
        "April SST + prior-Dec",
        "April SST + TSI",
        "April SST + TSI + prior-Dec",
    ]
    for axis, skill, title in (
        (axes[1], loeo_skill, "(b) Warm-event LOEO"),
        (
            axes[2],
            chronological_skill,
            "(c) Chronological 2004−2023",
        ),
    ):
        current = skill.set_index("model").loc[keep].reset_index()
        y = np.arange(len(current))
        axis.barh(
            y,
            current["rmse_skill_vs_april_sst"],
            color=[
                "#B43C2D" if "TSI" in name else "#7A9EB8"
                for name in current["model"]
            ],
        )
        axis.axvline(0, color="0.25", lw=0.8)
        axis.set_yticks(y, current["model"])
        axis.set_xlabel("RMSE skill vs April SST type")
        axis.set_title(title, loc="left", weight="bold")
        axis.grid(axis="x", color="0.88", lw=0.6)
        axis.set_axisbelow(True)

    clear = classification.loc[
        classification["clear_type_abs_ge_0p2"]
    ]
    fig.suptitle(
        "April transport–storage state adds information beyond a published "
        "pre-spring SST precursor",
        fontsize=13.5,
        weight="bold",
        y=0.96,
    )
    fig.text(
        0.5,
        0.045,
        "Prior-Dec precursor: ERSSTv5, 120°E–165°E minus "
        "165°E–150°W, 5°S–5°N, strictly trailing 30-year climatology. "
        f"Sign accuracy for clear local types: "
        f"{int(clear['correct'].sum())}/{len(clear)}.",
        ha="center",
        fontsize=7.8,
        color="0.3",
    )
    FIGURE_PDF.parent.mkdir(parents=True, exist_ok=True)
    FIGURE_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PDF)
    fig.savefig(FIGURE_PNG)
    plt.close(fig)


def write_report(
    event: pd.DataFrame,
    classification: pd.DataFrame,
    loeo_skill: pd.DataFrame,
    chronological_skill: pd.DataFrame,
) -> None:
    def row(frame: pd.DataFrame, model: str) -> pd.Series:
        return frame.loc[frame["model"].eq(model)].iloc[0]

    all_correct = int(classification["correct"].sum())
    clear = classification.loc[
        classification["clear_type_abs_ge_0p2"]
    ]
    clear_correct = int(clear["correct"].sum())
    all_p = binomtest(
        all_correct,
        len(classification),
        0.5,
        alternative="greater",
    ).pvalue
    clear_p = binomtest(
        clear_correct,
        len(clear),
        0.5,
        alternative="greater",
    ).pvalue
    correlation = np.corrcoef(
        event["prior_dec_wp_minus_cp_c"],
        event["mature_djf_type_index_c"],
    )[0, 1]
    prior = row(loeo_skill, "Prior-Dec WP-CP")
    tsi = row(loeo_skill, "April SST + TSI")
    combined = row(
        loeo_skill,
        "April SST + TSI + prior-Dec",
    )
    prior_chrono = row(
        chronological_skill,
        "Prior-Dec WP-CP",
    )
    tsi_chrono = row(
        chronological_skill,
        "April SST + TSI",
    )
    report = f"""# TSI与权威ENSO分型前兆的同样本比较

## 复核对象

Ludescher et al. (2023) 使用前一年12月
`ΔT(WP−CP)` 判断下一年事件偏EP还是CP，其中WP为
120°E–165°E、CP为165°E–150°W、纬度均为5°S–5°N，并用过去30年
滑动气候态。本复核使用ERSSTv5、严格只用预测时点之前30年，事件与
目标完全沿用本项目的13个暖事件和连续`Niño3−Niño4`型态指标。

## 结果

- `ΔT(WP−CP)`与成熟型态相关为r={correlation:+.3f}。
- 按正号预测EP、负号预测CP：13事件命中{all_correct}/13
  （单侧二项p={all_p:.3f}）；排除`|Niño3−Niño4|<0.2°C`的
  borderline事件后命中{clear_correct}/{len(clear)}
  （p={clear_p:.3f}）。
- 在连续型态的13事件LOEO中，单独的前期ΔT相对4月SST基准技巧为
  {prior.rmse_skill_vs_april_sst:+.1%}，而4月TSI为
  {tsi.rmse_skill_vs_april_sst:+.1%}；两者合并为
  {combined.rmse_skill_vs_april_sst:+.1%}。
- 真正按时间顺序预测2004—2023的7个后续暖事件时，前期ΔT技巧为
  {prior_chrono.rmse_skill_vs_april_sst:+.1%}，4月TSI为
  {tsi_chrono.rmse_skill_vs_april_sst:+.1%}。

## 科学解释

前一年12月的WP−CP梯度是“是否处于西部充热、适合未来EP发展”的
远期背景量；文献本身也指出，之后若春季WWE不足，原本预测为EP的事件
仍可转为CP。4月TSI测量的是这段不确定性已经实现到何种程度：
暖水是否穿过140°W，以及到达后D20是否加深。因此两者不是互相替代，
而是时间上前后相接：

`前期充热背景 → 春季风事件/海洋调整 → 140°W输送与储存 → 成熟型态`

当前同样本结果支持把TSI称为“春季更新量”，不能声称它取代了已有的
长期前兆；反过来，前期SST梯度也不能取代春季海洋动力状态。
"""
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> int:
    index = build_prior_dec_index()
    INDEX_CSV.parent.mkdir(parents=True, exist_ok=True)
    index.to_csv(INDEX_CSV, index=False)
    table = pd.read_csv(ANALYSIS_CSV)
    event = table.loc[table["year"].isin(EVENT_YEARS)].merge(
        index[
            [
                "event_year",
                "prior_dec_wp_minus_cp_c",
            ]
        ].rename(columns={"event_year": "year"}),
        on="year",
        validate="one_to_one",
    )

    loeo_predictions = predictions(event, chronological=False)
    loeo_skill = skill_table(
        loeo_predictions,
        "13 warm-event LOEO",
    )
    loeo_skill.to_csv(LOEO_CSV, index=False)

    chrono_predictions = predictions(event, chronological=True)
    chronological_skill = skill_table(
        chrono_predictions,
        "warm-event chronological 2004-2023",
    )
    chronological_skill.to_csv(CHRONO_CSV, index=False)

    classification = classification_table(event)
    classification.to_csv(CLASS_CSV, index=False)
    make_figure(
        event,
        classification,
        loeo_skill,
        chronological_skill,
    )
    write_report(
        event,
        classification,
        loeo_skill,
        chronological_skill,
    )
    print(f"Wrote {INDEX_CSV}")
    print(f"Wrote {LOEO_CSV}")
    print(f"Wrote {CHRONO_CSV}")
    print(f"Wrote {FIGURE_PDF}")
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
