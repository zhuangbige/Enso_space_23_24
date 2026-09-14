#!/usr/bin/env python3
"""Test whether atmospheric decoupling is unusual given ocean state.

The script is deliberately event-conditional. It does not search for an
all-year El Niño onset predictor. It asks two narrower questions:

1. Given the March-April eastern-ocean state, how unusual was the mature
   atmospheric response of each warm event?
2. Do two literature-motivated spring candidates (western-Pacific WWV and
   east-minus-west SST gradient) explain mature coupling residuals across
   the 13 warm events?
"""

from __future__ import annotations

import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_ocean_conditioned_cache")
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
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from analyze_enso_type_coupling_efficiency import (  # noqa: E402
    EVENT_YEARS,
    benjamini_hochberg,
    bootstrap_correlation_ci,
    permutation_p,
)


DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/type_coupling"
PDF = ROOT / "output/pdf/enso_ocean_conditioned_decoupling.pdf"
PNG = OUT / "enso_ocean_conditioned_decoupling.png"
REPORT = OUT / "ENSO_OCEAN_CONDITIONED_DECOUPLING_CN.md"
EVENT_CSV = DERIVED / "enso_ocean_conditioned_decoupling_event_summary.csv"
CANDIDATE_CSV = DERIVED / "enso_decoupling_candidate_correlations.csv"

OCEAN_CSV = DERIVED / "enso_type_east_ocean_state_event_summary.csv"
SEASONAL_CSV = DERIVED / "enso_full_year_coupling_event_seasonal.csv"
ALL_YEAR_CSV = (
    DERIVED / "enso_full_year_coupling_all_year_seasonal_1982_2023.csv"
)
INPUT_CSV = DERIVED / "enso_dual_path_april_inputs_1982_2023.csv"

TARGETS = {
    "coupling_pattern_residual_z": "ERA5/GPCP combined",
    "ncep_coupling_pattern_residual_z": "NCEP wind-pressure",
    "precip_pattern_residual_z": "GPCP precipitation",
    "ncep_u_pattern_residual_z": "NCEP zonal wind",
}
SEASON_ORDER = ["AMJ", "JJA", "SON", "DJF"]


def detrended_z(frame: pd.DataFrame, column: str) -> pd.Series:
    x = np.column_stack(
        [
            np.ones(len(frame)),
            frame["year"].to_numpy(dtype=float) - 2002.5,
        ]
    )
    values = frame[column].to_numpy(dtype=float)
    coefficients = np.linalg.lstsq(x, values, rcond=None)[0]
    residual = values - x @ coefficients
    return pd.Series(
        residual / np.std(residual, ddof=x.shape[1]),
        index=frame.index,
    )


def ocean_conditioned_residual(
    frame: pd.DataFrame,
    response: str,
) -> pd.Series:
    output = pd.Series(np.nan, index=frame.index, dtype=float)
    for index, test in frame.iterrows():
        train = frame.loc[frame["year"].ne(test["year"])]
        x_train = np.column_stack(
            [
                np.ones(len(train)),
                train["east_ocean_state_z"].to_numpy(dtype=float),
            ]
        )
        coefficients = np.linalg.lstsq(
            x_train,
            train[response].to_numpy(dtype=float),
            rcond=None,
        )[0]
        fitted = x_train @ coefficients
        scale = float(
            np.std(
                train[response].to_numpy(dtype=float) - fitted,
                ddof=x_train.shape[1],
            )
        )
        x_test = np.asarray(
            [1.0, float(test["east_ocean_state_z"])]
        )
        output.loc[index] = (
            float(test[response]) - float(x_test @ coefficients)
        ) / scale
    return output


def build_event_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    ocean = pd.read_csv(OCEAN_CSV)
    seasonal = pd.read_csv(SEASONAL_CSV)
    inputs = pd.read_csv(INPUT_CSV)
    inputs["wwv_west_detrended_z"] = detrended_z(
        inputs, "wwv_west_1e14m3_ma"
    )
    inputs["spring_sst_gradient_detrended_z"] = detrended_z(
        inputs, "sst_gradient_e_minus_w_c"
    )
    candidate = inputs.loc[
        inputs["year"].isin(EVENT_YEARS),
        [
            "year",
            "wwv_west_detrended_z",
            "spring_sst_gradient_detrended_z",
        ],
    ]
    table = (
        seasonal.merge(ocean, on="year", validate="many_to_one")
        .merge(candidate, on="year", validate="many_to_one")
        .sort_values(["year", "season"])
        .reset_index(drop=True)
    )
    for season in SEASON_ORDER:
        mask = table["season"].eq(season)
        for response in TARGETS:
            name = f"{response}_given_ocean_z"
            table.loc[mask, name] = ocean_conditioned_residual(
                table.loc[mask].copy(), response
            )
            table.loc[mask, f"{name}_lower_rank"] = table.loc[
                mask, name
            ].rank(method="min", ascending=True)

    djf = table.loc[table["season"].eq("DJF")].copy()
    rows = []
    predictors = {
        "wwv_west_detrended_z": "Mar-Apr detrended western-Pacific WWV",
        "spring_sst_gradient_detrended_z": (
            "Mar-Apr detrended east-minus-west SST gradient"
        ),
    }
    for p_index, (predictor, predictor_label) in enumerate(
        predictors.items()
    ):
        x = djf[predictor].to_numpy(dtype=float)
        for t_index, (target, target_label) in enumerate(TARGETS.items()):
            y = djf[target].to_numpy(dtype=float)
            ci_low, ci_high = bootstrap_correlation_ci(
                x, y, 93_000 + 10 * p_index + t_index
            )
            rows.append(
                {
                    "predictor": predictor,
                    "predictor_label": predictor_label,
                    "target": target,
                    "target_label": target_label,
                    "n_events": len(djf),
                    "pearson_r": float(np.corrcoef(x, y)[0, 1]),
                    "spearman_r": float(stats.spearmanr(x, y).statistic),
                    "bootstrap_ci_low": ci_low,
                    "bootstrap_ci_high": ci_high,
                    "permutation_p": permutation_p(
                        x, y, 94_000 + 10 * p_index + t_index
                    ),
                }
            )
    correlations = pd.DataFrame(rows)
    correlations["bh_fdr_q"] = benjamini_hochberg(
        correlations["permutation_p"]
    )
    return table, correlations


def make_figure(
    event: pd.DataFrame,
    correlations: pd.DataFrame,
) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9,
            "pdf.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.6))
    djf = event.loc[event["season"].eq("DJF")].copy()

    axis = axes[0, 0]
    non2023 = djf.loc[djf["year"].ne(2023)]
    axis.scatter(
        non2023["east_ocean_state_z"],
        non2023["coupling_pattern_residual_z"],
        color="0.45",
        s=42,
        zorder=3,
    )
    point2023 = djf.loc[djf["year"].eq(2023)].iloc[0]
    axis.scatter(
        [point2023["east_ocean_state_z"]],
        [point2023["coupling_pattern_residual_z"]],
        color="#2166ac",
        edgecolor="white",
        linewidth=0.8,
        s=85,
        zorder=4,
    )
    x = non2023["east_ocean_state_z"].to_numpy(dtype=float)
    y = non2023["coupling_pattern_residual_z"].to_numpy(dtype=float)
    coefficients = np.polyfit(x, y, 1)
    line_x = np.linspace(float(djf["east_ocean_state_z"].min()) - 0.1,
                         float(djf["east_ocean_state_z"].max()) + 0.1, 100)
    axis.plot(line_x, np.polyval(coefficients, line_x), color="0.25", lw=1.2)
    for _, row in djf.iterrows():
        axis.annotate(
            str(int(row["year"])),
            (row["east_ocean_state_z"], row["coupling_pattern_residual_z"]),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7,
        )
    axis.axhline(0, color="0.65", lw=0.8)
    axis.set(
        title="(a) Mature coupling given the spring eastern-ocean state",
        xlabel="Mar-Apr Q20/D20 eastern-ocean state (z)",
        ylabel="DJF pattern-adjusted coupling residual (z)",
    )
    axis.grid(color="0.9", lw=0.7)

    axis = axes[0, 1]
    values = [
        point2023[f"{target}_given_ocean_z"] for target in TARGETS
    ]
    ranks = [
        int(point2023[f"{target}_given_ocean_z_lower_rank"])
        for target in TARGETS
    ]
    labels = ["ERA/GPCP", "NCEP", "GPCP P", "NCEP U"]
    colors = ["#2166ac" if value < 0 else "#b2182b" for value in values]
    bars = axis.bar(np.arange(4), values, color=colors, width=0.65)
    axis.axhline(0, color="0.25", lw=0.8)
    axis.set_xticks(np.arange(4), labels)
    axis.set_ylabel("2023 observed minus ocean-state expectation (z)")
    axis.set_title("(b) 2023 is the weakest event after ocean-state adjustment")
    for bar, value, rank in zip(bars, values, ranks):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value / 2.0,
            f"{value:+.2f}\nrank {rank}/13",
            ha="center",
            va="center",
            fontsize=8,
            color="white",
            fontweight="bold",
        )
    axis.grid(axis="y", color="0.9", lw=0.7)

    axis = axes[1, 0]
    matrix = (
        correlations.pivot(
            index="predictor_label",
            columns="target_label",
            values="pearson_r",
        )
        .reindex(
            [
                "Mar-Apr detrended western-Pacific WWV",
                "Mar-Apr detrended east-minus-west SST gradient",
            ]
        )
        .reindex(columns=list(TARGETS.values()))
    )
    q_matrix = (
        correlations.pivot(
            index="predictor_label",
            columns="target_label",
            values="bh_fdr_q",
        )
        .reindex(matrix.index)
        .reindex(columns=matrix.columns)
    )
    image = axis.imshow(
        matrix.to_numpy(dtype=float),
        cmap="RdBu_r",
        vmin=-0.8,
        vmax=0.8,
        aspect="auto",
    )
    axis.set_xticks(
        np.arange(4),
        ["ERA/GPCP", "NCEP", "GPCP P", "NCEP U"],
    )
    axis.set_yticks(
        np.arange(2),
        ["Western WWV", "E-W SST gradient"],
    )
    for row in range(2):
        for column in range(4):
            axis.text(
                column,
                row,
                f"r={matrix.iloc[row, column]:+.2f}\n"
                f"q={q_matrix.iloc[row, column]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
            )
    axis.set_title("(c) No universal decoupling predictor survives FDR")
    colorbar = fig.colorbar(image, ax=axis, shrink=0.84, pad=0.03)
    colorbar.set_label("Pearson r")

    axis = axes[1, 1]
    all_year = pd.read_csv(ALL_YEAR_CSV)
    y2023 = (
        all_year.loc[all_year["year"].eq(2023)]
        .set_index("season")
        .reindex(SEASON_ORDER)
    )
    series = [
        (
            "ERA5/GPCP combined",
            "coupling_pattern_residual_z_lower_percentile",
            "#2166ac",
        ),
        (
            "NCEP wind-pressure",
            "ncep_coupling_pattern_residual_z_lower_percentile",
            "#4d4d4d",
        ),
        (
            "GPCP precipitation",
            "precip_pattern_residual_z_lower_percentile",
            "#1b9e77",
        ),
        (
            "NCEP zonal wind",
            "ncep_u_pattern_residual_z_lower_percentile",
            "#d95f02",
        ),
    ]
    for label, column, color in series:
        axis.plot(
            np.arange(4),
            100.0 * y2023[column],
            marker="o",
            label=label,
            color=color,
        )
    axis.axhspan(0, 10, color="#dbe9f6", alpha=0.8)
    axis.set_xticks(np.arange(4), SEASON_ORDER)
    axis.set_ylim(0, 100)
    axis.set_ylabel("2023 lower-tail percentile among 42 years (%)")
    axis.set_title("(d) Wind mismatch precedes mature convective mismatch")
    axis.legend(frameon=False, fontsize=7.5, ncol=2)
    axis.grid(color="0.9", lw=0.7)

    fig.suptitle(
        "Oceanic EP establishment does not guarantee a normal atmospheric response",
        fontsize=13.5,
        fontweight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.012,
        "All atmospheric residuals already control Niño3.4 amplitude and "
        "Niño3-Niño4 pattern using 1982-2014 calendar-month relationships. "
        "Event-conditioned fits are leave-one-event-out.",
        ha="center",
        fontsize=7.4,
        color="0.35",
    )
    fig.tight_layout(rect=[0.02, 0.045, 0.99, 0.96])
    OUT.mkdir(parents=True, exist_ok=True)
    PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PDF, dpi=300, bbox_inches="tight")
    fig.savefig(PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_report(
    event: pd.DataFrame,
    correlations: pd.DataFrame,
) -> None:
    djf = event.loc[event["season"].eq("DJF")].copy()
    y2023 = djf.loc[djf["year"].eq(2023)].iloc[0]
    wwv = correlations.loc[
        correlations["predictor"].eq("wwv_west_detrended_z")
    ].set_index("target")
    gradient = correlations.loc[
        correlations["predictor"].eq(
            "spring_sst_gradient_detrended_z"
        )
    ].set_index("target")
    text = f"""# 给定海洋状态后的ENSO脱耦检验

## 问题

春季140°W Q20和D20与成熟EP/CP型态有强联系，但这不意味着大气反馈
必然接上。本检验先用OISST、GPCP和ERA5得到已经控制Niño3.4幅度及
`Niño3-Niño4`空间型态的耦合残差，再问：给定3—4月东部海洋状态，
2023成熟期的大气响应是否仍异常？

## 2023的事件内位置

在13个暖事件中，2023给定春季东部海洋状态后的DJF残差为：

- ERA5/GPCP综合：
  {y2023.coupling_pattern_residual_z_given_ocean_z:+.2f} z，
  从弱到强排名
  {int(y2023.coupling_pattern_residual_z_given_ocean_z_lower_rank)}/13；
- NCEP风压综合：
  {y2023.ncep_coupling_pattern_residual_z_given_ocean_z:+.2f} z，
  排名
  {int(y2023.ncep_coupling_pattern_residual_z_given_ocean_z_lower_rank)}/13；
- GPCP降水：
  {y2023.precip_pattern_residual_z_given_ocean_z:+.2f} z，
  排名
  {int(y2023.precip_pattern_residual_z_given_ocean_z_lower_rank)}/13；
- NCEP中太平洋纬向风：
  {y2023.ncep_u_pattern_residual_z_given_ocean_z:+.2f} z，
  排名
  {int(y2023.ncep_u_pattern_residual_z_given_ocean_z_lower_rank)}/13。

这说明2023并非“海洋没有建立EP信号”，而是在一个已经相当向东的
海洋状态上，大气响应远弱于暖事件经验关系。第一名结果只表示本13
事件样本的下尾，不等于总体重现期。

## 两个文献候选量能否作通用脱耦指标

3—4月西太平洋WWV先用1982—2023全部年份线性趋势去除。它与DJF
型态调整后残差的相关为：

- ERA5/GPCP综合 r=
  {wwv.loc['coupling_pattern_residual_z', 'pearson_r']:+.2f}，
  FDR q={wwv.loc['coupling_pattern_residual_z', 'bh_fdr_q']:.2f}；
- NCEP风压综合 r=
  {wwv.loc['ncep_coupling_pattern_residual_z', 'pearson_r']:+.2f}，
  q={wwv.loc['ncep_coupling_pattern_residual_z', 'bh_fdr_q']:.2f}。

春季东减西SST梯度与两套综合残差的相关为
{gradient.loc['coupling_pattern_residual_z', 'pearson_r']:+.2f}和
{gradient.loc['ncep_coupling_pattern_residual_z', 'pearson_r']:+.2f}；
八个候选关系均未通过FDR。

因此，多年拉尼娜后的西部暖水与西向延伸增暖是解释2023/2009路径的
有力机制，但当前13事件样本不支持把单独WWV或春季SST梯度升格为通用
脱耦预测量。

## 结论边界

1. 140°W Q20/D20回答“海洋异常有没有向东输送并储存”；
2. SST型态调整后的降水、SLP和风残差回答“大气有没有按通常效率接上”；
3. 2023在两个坐标上分别是“较强东部海洋状态”和“极弱成熟大气响应”；
4. 目前找到的是可靠的分型海洋量，但尚未找到跨事件稳定的单一脱耦
   前兆。外部海盆加热、FEP经向对流偶极、背景暖化和西部非线性冷却
   需要显式加入，且因果判断要依靠AGCM/耦合敏感性试验。

## 文件

- 事件表：`{EVENT_CSV.relative_to(ROOT)}`
- 候选量相关：`{CANDIDATE_CSV.relative_to(ROOT)}`
- 图：`{PDF.relative_to(ROOT)}`
"""
    REPORT.write_text(text, encoding="utf-8")


def main() -> None:
    event, correlations = build_event_table()
    OUT.mkdir(parents=True, exist_ok=True)
    EVENT_CSV.parent.mkdir(parents=True, exist_ok=True)
    event.to_csv(EVENT_CSV, index=False)
    correlations.to_csv(CANDIDATE_CSV, index=False)
    make_figure(event, correlations)
    make_report(event, correlations)
    print(correlations.to_string(index=False))
    print()
    print(
        event.loc[
            event["year"].eq(2023),
            [
                "season",
                *[
                    f"{target}_given_ocean_z"
                    for target in TARGETS
                ],
            ],
        ].to_string(index=False)
    )
    print(f"\n{REPORT}\n{PDF}")


if __name__ == "__main__":
    main()
