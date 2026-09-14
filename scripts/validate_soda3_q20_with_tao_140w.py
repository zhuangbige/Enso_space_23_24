#!/usr/bin/env python3
"""Observational checkpoint for the SODA3 140W transport/storage signals.

This script compares the SODA3 5S-5N section-integrated Q20 and equatorial
D20 at 140W with independent TAO mooring observations at 0N, 140W.  TAO
cannot observe the full meridional section transport, so the current-based
quantities are explicitly treated as local equatorial proxies rather than
as an observational reconstruction of SODA3 Q20.
"""

from __future__ import annotations

import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_tao_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/tao_0n140w"
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/final_dual_path_predictor"
PDF = ROOT / "output/pdf/tao_140w_observational_checkpoint.pdf"

MONTHLY_CSV = DERIVED / "tao_140w_monthly_observation_proxies.csv"
PAIR_CSV = DERIVED / "tao_140w_pairwise_anomalies.csv"
SKILL_CSV = DERIVED / "tao_140w_soda3_agreement.csv"
EVENT_CSV = DERIVED / "tao_140w_event_checkpoint.csv"
REPORT = OUT / "TAO_140W_OBSERVATIONAL_VALIDATION_CN.md"
PNG = OUT / "tao_140w_observational_checkpoint.png"

SODA_Q20 = DERIVED / "soda3_mixed_layer_budget_indices_1980_2024.csv"
SODA_D20 = DERIVED / "soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
EVENT_INPUT = DERIVED / "enso_dual_path_april_inputs_1982_2023.csv"

EVENT_YEARS = [
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
]


def read_tao(name: str) -> pd.DataFrame:
    frame = pd.read_csv(RAW / name, skiprows=[1])
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame["year"] = frame["time"].dt.year
    frame["month"] = frame["time"].dt.month
    frame["day"] = frame["time"].dt.floor("D")
    return frame


def monthly_profiles(
    name: str,
    value: str,
    quality: str,
    *,
    maximum_depth: float = 200.0,
) -> dict[tuple[int, int], pd.DataFrame]:
    frame = read_tao(name)
    frame = frame.loc[
        frame[value].notna()
        & frame[quality].between(1, 3)
        & frame["depth"].between(0, maximum_depth)
    ].copy()
    depth_means = (
        frame.groupby(["year", "month", "depth"])
        .agg(value=(value, "mean"), valid_days=("day", "nunique"))
        .reset_index()
    )
    depth_means = depth_means.loc[depth_means["valid_days"].ge(5)]
    return {
        (int(year), int(month)): group.sort_values("depth").reset_index(
            drop=True
        )
        for (year, month), group in depth_means.groupby(["year", "month"])
    }


def current_proxies(
    current_profiles: dict[tuple[int, int], pd.DataFrame],
    temperature_profiles: dict[tuple[int, int], pd.DataFrame],
    prefix: str,
) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for (year, month), profile in current_profiles.items():
        profile = profile.loc[profile["depth"].le(120.0)].copy()
        if (
            len(profile) < 3
            or profile["depth"].min() > 30.0
            or profile["depth"].max() < 120.0
        ):
            continue
        depth = profile["depth"].to_numpy(dtype=float)
        current = profile["value"].to_numpy(dtype=float)
        depth_mean = float(
            np.trapz(current, depth) / (depth[-1] - depth[0])
        )
        row: dict[str, float | int] = {
            "year": year,
            "month": month,
            f"{prefix}_upper_current_cm_s": depth_mean,
            f"{prefix}_n_current_levels": len(depth),
        }
        temperature = temperature_profiles.get((year, month))
        if temperature is not None:
            temperature = temperature.loc[
                temperature["depth"].le(200.0)
            ]
            if (
                len(temperature) >= 4
                and temperature["depth"].min() <= depth.min()
                and temperature["depth"].max() >= depth.max()
            ):
                interpolated = np.interp(
                    depth,
                    temperature["depth"].to_numpy(dtype=float),
                    temperature["value"].to_numpy(dtype=float),
                )
                heat_weight = np.maximum(interpolated - 20.0, 0.0)
                row[f"{prefix}_local_q20_proxy_c_m2_s"] = float(
                    np.trapz((current / 100.0) * heat_weight, depth)
                )
        rows.append(row)
    return pd.DataFrame(rows)


def d20_monthly() -> pd.DataFrame:
    frame = read_tao("tao_0n140w_daily_d20.csv")
    frame = frame.loc[
        frame["ISO_6"].notna() & frame["QI_5006"].between(1, 3)
    ].copy()
    output = (
        frame.groupby(["year", "month"])
        .agg(
            tao_d20_m=("ISO_6", "mean"),
            tao_d20_valid_days=("day", "nunique"),
        )
        .reset_index()
    )
    return output.loc[output["tao_d20_valid_days"].ge(10)].copy()


def remove_month_and_trend(
    frame: pd.DataFrame,
    column: str,
) -> np.ndarray:
    year = frame["year"].to_numpy(dtype=float)
    months = pd.get_dummies(
        frame["month"].astype(int),
        prefix="month",
        drop_first=True,
        dtype=float,
    ).to_numpy()
    design = np.column_stack(
        [
            np.ones(len(frame)),
            year - np.mean(year),
            months,
        ]
    )
    value = frame[column].to_numpy(dtype=float)
    coefficients = np.linalg.lstsq(design, value, rcond=None)[0]
    return value - design @ coefficients


def permutation_p(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
    repetitions: int = 20_000,
) -> float:
    observed = abs(float(np.corrcoef(x, y)[0, 1]))
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(repetitions):
        permuted = rng.permutation(y)
        exceed += abs(float(np.corrcoef(x, permuted)[0, 1])) >= observed
    return (exceed + 1.0) / (repetitions + 1.0)


def correlation_ci(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
    repetitions: int = 20_000,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repetitions):
        index = rng.integers(0, len(x), len(x))
        if np.std(x[index]) == 0 or np.std(y[index]) == 0:
            continue
        estimates.append(float(np.corrcoef(x[index], y[index])[0, 1]))
    return tuple(np.quantile(estimates, [0.025, 0.975]))


def pairwise_agreement(
    monthly: pd.DataFrame,
    soda: pd.DataFrame,
    observation_column: str,
    soda_column: str,
    metric: str,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    common = monthly[["year", "month", observation_column]].merge(
        soda[["year", "month", soda_column]],
        on=["year", "month"],
        how="inner",
    )
    common = common.dropna().loc[lambda x: x["month"].isin([3, 4])]
    common = common.sort_values(["year", "month"]).reset_index(drop=True)
    common["obs_residual"] = remove_month_and_trend(
        common, observation_column
    )
    common["soda_residual"] = remove_month_and_trend(common, soda_column)
    annual = (
        common.groupby("year")
        .agg(
            observation_anomaly=("obs_residual", "mean"),
            soda3_anomaly=("soda_residual", "mean"),
            n_months=("month", "nunique"),
        )
        .reset_index()
    )
    annual["metric"] = metric
    annual["observation_column"] = observation_column
    annual["soda3_column"] = soda_column
    x = annual["soda3_anomaly"].to_numpy(dtype=float)
    y = annual["observation_anomaly"].to_numpy(dtype=float)
    correlation = float(np.corrcoef(x, y)[0, 1])
    ci_low, ci_high = correlation_ci(x, y, seed)
    result: dict[str, float | int | str] = {
        "metric": metric,
        "observation_column": observation_column,
        "soda3_column": soda_column,
        "window": "March-April annual mean",
        "n_years": len(annual),
        "first_year": int(annual["year"].min()),
        "last_year": int(annual["year"].max()),
        "correlation_r": correlation,
        "bootstrap_ci_low": ci_low,
        "bootstrap_ci_high": ci_high,
        "two_sided_year_permutation_p": permutation_p(x, y, seed + 1000),
        "slope_obs_per_soda_unit": float(stats.linregress(x, y).slope),
    }
    return annual, result


def event_checkpoint(
    pairwise: pd.DataFrame,
    event: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    target = event[
        ["year", "mature_djf_type_index_c"]
    ].drop_duplicates()
    for metric, group in pairwise.groupby("metric"):
        subset = group.merge(target, on="year", how="inner")
        subset = subset.loc[subset["year"].isin(EVENT_YEARS)]
        if len(subset) < 5:
            continue
        rows.append(
            {
                "metric": metric,
                "n_warm_events_with_tao": len(subset),
                "first_event": int(subset["year"].min()),
                "last_event": int(subset["year"].max()),
                "tao_proxy_vs_mature_type_r": float(
                    np.corrcoef(
                        subset["observation_anomaly"],
                        subset["mature_djf_type_index_c"],
                    )[0, 1]
                ),
                "soda3_signal_vs_mature_type_r": float(
                    np.corrcoef(
                        subset["soda3_anomaly"],
                        subset["mature_djf_type_index_c"],
                    )[0, 1]
                ),
            }
        )
    return pd.DataFrame(rows)


def standardize(values: pd.Series) -> pd.Series:
    return (values - values.mean()) / values.std(ddof=0)


def make_figure(
    pairwise: pd.DataFrame,
    agreement: pd.DataFrame,
) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "pdf.fonttype": 42,
        }
    )
    colors = {
        "TAO current-meter local Q20 proxy": "#0072B2",
        "TAO ADCP local Q20 proxy": "#D55E00",
        "TAO current-meter upper current": "#56B4E9",
        "TAO ADCP upper current": "#E69F00",
        "TAO D20": "#009E73",
    }
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.0))
    for axis, metric in zip(
        axes.flat[:3],
        [
            "TAO current-meter local Q20 proxy",
            "TAO ADCP local Q20 proxy",
            "TAO D20",
        ],
    ):
        data = pairwise.loc[pairwise["metric"].eq(metric)].copy()
        row = agreement.loc[agreement["metric"].eq(metric)].iloc[0]
        x = standardize(data["soda3_anomaly"])
        y = standardize(data["observation_anomaly"])
        axis.axhline(0, color="0.8", lw=0.8)
        axis.axvline(0, color="0.8", lw=0.8)
        axis.scatter(
            x,
            y,
            s=34,
            color=colors[metric],
            edgecolor="white",
            linewidth=0.5,
            zorder=3,
        )
        slope, intercept = np.polyfit(x, y, 1)
        grid = np.linspace(x.min() - 0.2, x.max() + 0.2, 100)
        axis.plot(grid, intercept + slope * grid, color="0.18", lw=1.2)
        for _, point in data.iterrows():
            if int(point["year"]) in [1997, 2015, 2023]:
                axis.annotate(
                    str(int(point["year"])),
                    (
                        (point["soda3_anomaly"] - data["soda3_anomaly"].mean())
                        / data["soda3_anomaly"].std(ddof=0),
                        (
                            point["observation_anomaly"]
                            - data["observation_anomaly"].mean()
                        )
                        / data["observation_anomaly"].std(ddof=0),
                    ),
                    xytext=(4, 3),
                    textcoords="offset points",
                    fontsize=7,
                )
        axis.set_title(
            f"{metric}\n"
            f"r = {row.correlation_r:.2f}, "
            f"95% CI [{row.bootstrap_ci_low:.2f}, "
            f"{row.bootstrap_ci_high:.2f}], n = {int(row.n_years)}"
        )
        axis.set_xlabel("SODA3 standardized Mar-Apr anomaly")
        axis.set_ylabel("TAO standardized Mar-Apr anomaly")

    bar_axis = axes.flat[3]
    plot_data = agreement.sort_values("correlation_r")
    y_position = np.arange(len(plot_data))
    bar_colors = [colors[metric] for metric in plot_data["metric"]]
    bar_axis.barh(
        y_position,
        plot_data["correlation_r"],
        color=bar_colors,
        alpha=0.88,
    )
    lower = plot_data["correlation_r"] - plot_data["bootstrap_ci_low"]
    upper = plot_data["bootstrap_ci_high"] - plot_data["correlation_r"]
    bar_axis.errorbar(
        plot_data["correlation_r"],
        y_position,
        xerr=np.vstack([lower, upper]),
        fmt="none",
        ecolor="0.2",
        capsize=3,
        lw=1,
    )
    bar_axis.axvline(0, color="0.35", lw=0.8)
    bar_axis.set_xlim(-0.25, 1.0)
    bar_axis.set_yticks(y_position)
    bar_axis.set_yticklabels(
        plot_data["metric"].str.replace("TAO ", "", regex=False),
        fontsize=8,
    )
    bar_axis.set_xlabel("Pairwise Mar-Apr correlation")
    bar_axis.set_title("Independent observational agreement")
    bar_axis.grid(axis="x", color="0.9", lw=0.7)

    fig.suptitle(
        "SODA3 140W transport/storage signals checked against "
        "TAO mooring observations",
        fontsize=14,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.012,
        "TAO is a point mooring at 0N, 140W; current-based panels "
        "test the equatorial-current component, not the full 5S-5N "
        "section-integrated heat transport.",
        ha="center",
        fontsize=8,
        color="0.32",
    )
    fig.tight_layout(rect=[0.02, 0.04, 0.99, 0.95])
    PDF.parent.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(PDF, dpi=300, bbox_inches="tight")
    fig.savefig(PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_report(
    agreement: pd.DataFrame,
    event: pd.DataFrame,
) -> None:
    by_metric = agreement.set_index("metric")

    def sentence(metric: str) -> str:
        row = by_metric.loc[metric]
        return (
            f"- **{metric}**：r = {row.correlation_r:+.2f}，"
            f"95% bootstrap CI [{row.bootstrap_ci_low:+.2f}, "
            f"{row.bootstrap_ci_high:+.2f}]，"
            f"逐年置换 p = {row.two_sided_year_permutation_p:.4f}，"
            f"n = {int(row.n_years)} 年"
            f"（{int(row.first_year)}–{int(row.last_year)}）。"
        )

    event_lines = []
    for _, row in event.iterrows():
        event_lines.append(
            f"- {row['metric']}：只有 {int(row.n_warm_events_with_tao)} "
            f"个暖事件有可用观测；TAO量与成熟型指数 r = "
            f"{row.tao_proxy_vs_mature_type_r:+.2f}，"
            f"SODA3对应量 r = "
            f"{row.soda3_signal_vs_mature_type_r:+.2f}。"
        )
    text = f"""# TAO 0°N, 140°W 对 SODA3 关键量的独立观测核验

## 核验问题

SODA3 的 140°W、5°S–5°N 截面上层暖水输送 `Q20`，以及赤道
`D20`，是否只是再分析产品内部的统计信号？本检验改用 NOAA/PMEL
TAO 锚系的日资料。所有比较都只用共同可用的 3–4 月，并分别去掉
日历月平均和线性趋势，再按年平均；显著性通过整年标签置换评估。

## 主要结果

{sentence("TAO current-meter local Q20 proxy")}
{sentence("TAO ADCP local Q20 proxy")}
{sentence("TAO current-meter upper current")}
{sentence("TAO ADCP upper current")}
{sentence("TAO D20")}

## 怎样解释

1. **若两套流速仪的局地热权重代理都与 SODA3 Q20 同号且显著**，
   就说明 SODA3 捕捉到的至少不是纯粹的模式伪信号：赤道 140°W
   上层东向流及其携带的 20°C 以上暖水确实有独立观测对应。
2. **这仍不等于完整验证 Q20**。TAO 是 0°N 单点，SODA3 Q20 是
   5°S–5°N、0–300 m 截面积分。单点观测不能恢复经向结构，也不能
   排除 SODA3 对断面宽度、深层流或缺测期的偏差。
3. **D20 是更直接的同变量核验**：若 TAO 与 SODA3 D20 一致，
   可以把“储存/热跃层深度”证据等级放得高于只有产品间比较的量。

## 暖事件子样本（只作描述）

{chr(10).join(event_lines) if event_lines else "- 可用暖事件不足 5 个，不计算事件相关。"}

事件子样本很小且缺测不是随机的，因此不能把这里的事件相关当作新的
预测技巧检验。预测性能仍以严格的留一事件、时间顺序和全年度走步检验
为准。

## 证据等级

- **可写成观测支持**：3–4 月 140°W 赤道上层流/局地暖水输送代理与
  SODA3 Q20 的共同变化；TAO 与 SODA3 D20 的共同变化。
- **只能写成再分析诊断**：完整 5°S–5°N Q20 断面及其绝对量值。
- **仍不能写成业务模型**：TAO 缺测多、事件样本小，而且该量只在已知
  暖事件条件下用于类型更新，不能单独预测厄尔尼诺是否发生。

## 数据来源与可复现文件

- TAO 日流速（current meter 与 ADCP）、温度剖面及 D20：NOAA/PMEL
  ERDDAP，质量标志 1–3；每个深度每月不少于 5 个有效日，D20 每月
  不少于 10 个有效日。
- 局地 Q20 代理：在可用流速层上积分
  `u × max(T−20°C, 0)`，上限 120 m；它没有乘密度、热容或断面宽度，
  因而只比较异常的共同变化。
- 月度代理：`{MONTHLY_CSV.relative_to(ROOT)}`
- 配对异常：`{PAIR_CSV.relative_to(ROOT)}`
- 统计汇总：`{SKILL_CSV.relative_to(ROOT)}`
- 暖事件描述：`{EVENT_CSV.relative_to(ROOT)}`
- 图：`{PDF.relative_to(ROOT)}`
"""
    REPORT.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    temperature = monthly_profiles(
        "tao_0n140w_daily_temperature.csv",
        "T_20",
        "QT_5020",
    )
    current = current_proxies(
        monthly_profiles(
            "tao_0n140w_daily_current.csv",
            "U_320",
            "QCS_5300",
        ),
        temperature,
        "current_meter",
    )
    adcp = current_proxies(
        monthly_profiles(
            "tao_0n140w_daily_adcp.csv",
            "u_1205",
            "QU_5205",
        ),
        temperature,
        "adcp",
    )
    monthly = current.merge(
        adcp,
        on=["year", "month"],
        how="outer",
    ).merge(
        d20_monthly(),
        on=["year", "month"],
        how="outer",
    )
    monthly = monthly.sort_values(["year", "month"])
    monthly.to_csv(MONTHLY_CSV, index=False)

    soda_q20 = pd.read_csv(SODA_Q20)
    soda_d20 = pd.read_csv(SODA_D20)
    soda_d20 = soda_d20.loc[
        np.isclose(soda_d20["longitude_e"], 220.0)
    ].copy()
    definitions = [
        (
            "TAO current-meter local Q20 proxy",
            "current_meter_local_q20_proxy_c_m2_s",
            soda_q20,
            "q20_220e_pw",
        ),
        (
            "TAO ADCP local Q20 proxy",
            "adcp_local_q20_proxy_c_m2_s",
            soda_q20,
            "q20_220e_pw",
        ),
        (
            "TAO current-meter upper current",
            "current_meter_upper_current_cm_s",
            soda_q20,
            "q20_220e_pw",
        ),
        (
            "TAO ADCP upper current",
            "adcp_upper_current_cm_s",
            soda_q20,
            "q20_220e_pw",
        ),
        (
            "TAO D20",
            "tao_d20_m",
            soda_d20,
            "d20_m",
        ),
    ]
    pairwise_frames = []
    agreement_rows = []
    for index, definition in enumerate(definitions):
        pairwise, agreement = pairwise_agreement(
            monthly,
            definition[2],
            definition[1],
            definition[3],
            definition[0],
            52_000 + index,
        )
        pairwise_frames.append(pairwise)
        agreement_rows.append(agreement)
    pairwise = pd.concat(pairwise_frames, ignore_index=True)
    agreement = pd.DataFrame(agreement_rows)
    event = event_checkpoint(pairwise, pd.read_csv(EVENT_INPUT))
    pairwise.to_csv(PAIR_CSV, index=False)
    agreement.to_csv(SKILL_CSV, index=False)
    event.to_csv(EVENT_CSV, index=False)
    make_figure(pairwise, agreement)
    make_report(agreement, event)
    print(agreement.to_string(index=False))
    print()
    print(event.to_string(index=False))
    print(f"\n{REPORT}")
    print(PDF)


if __name__ == "__main__":
    main()
