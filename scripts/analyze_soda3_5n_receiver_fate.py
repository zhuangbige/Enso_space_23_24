#!/usr/bin/env python3
"""Diagnose whether Q20 crossing 5N remains in the northern receiver box.

The equatorial eastern-Pacific box ends at 5N.  A northward Q20 there is an
outflow from that box, but only an inflow to the adjacent 5--12N receiver.
This script compares the time-integrated 5N inflow with the receiver-box H20
change during Jan(+1)--May(+1) for the fixed Chakravorty CT/CP events.

Only receiver H20 and the southern-boundary Q20 are currently available.
The diagnosed ``other_net`` term therefore combines the 12N, 140W and 80W
boundaries, surface heat exchange, vertical/diapycnal exchange, mixing,
threshold conversion, assimilation increments and temporal discretization.
It is not interpreted as a single physical process.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/derived/research_2026/h20_outflow_ne_feedback_monthly_1982_2024.csv"
EVENT_OUTPUT = ROOT / "data/derived/research_2026/soda3_5n_receiver_fate_events.csv"
SUMMARY_OUTPUT = ROOT / "data/derived/research_2026/soda3_5n_receiver_fate_summary.csv"
REPORT_OUTPUT = (
    ROOT
    / "outputs/research_2026/h20_outflow_ne_feedback/"
    "SODA3_5N_RECEIVER_FATE_CN.md"
)

EVENTS = {
    "CT": (1982, 1986, 1997, 2006),
    "CP": (1991, 1994, 2002, 2004),
}
ADDITIONAL_EVENTS = (2015,)
METRICS = (
    "q5n_input_zj",
    "receiver_h20_change_zj",
    "other_net_pathways_zj",
)
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260809


def integrate_pw(times: pd.Series, values: pd.Series) -> float:
    """Trapezoidally integrate monthly PW values between timestamp centers."""
    seconds = times.astype("int64").to_numpy(dtype=float) / 1.0e9
    watts = values.to_numpy(dtype=float) * 1.0e15
    return float(np.trapz(watts, seconds) / 1.0e21)


def build_event_table(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    event_groups = {**EVENTS, "additional": ADDITIONAL_EVENTS}
    for event_class, event_years in event_groups.items():
        for event_year in event_years:
            receiver_year = event_year + 1
            selected = monthly.loc[
                (monthly["year"] == receiver_year)
                & monthly["month"].between(1, 5)
            ].sort_values("month")
            if selected["month"].tolist() != [1, 2, 3, 4, 5]:
                raise ValueError(f"Incomplete Jan--May sequence for {receiver_year}")
            required = ["q5n_total_anom_pw", "h20_north_anom_zj"]
            if selected[required].isna().any().any():
                raise ValueError(f"Missing receiver diagnostics for {receiver_year}")

            q5n_input = integrate_pw(selected["time"], selected["q5n_total_anom_pw"])
            h20_change = float(
                selected["h20_north_anom_zj"].iloc[-1]
                - selected["h20_north_anom_zj"].iloc[0]
            )
            rows.append(
                {
                    "event_class": event_class,
                    "event_year": event_year,
                    "receiver_year": receiver_year,
                    "window": "Jan15(+1)-May15(+1)",
                    "q5n_input_zj": q5n_input,
                    "receiver_h20_jan_zj": float(selected["h20_north_anom_zj"].iloc[0]),
                    "receiver_h20_may_zj": float(selected["h20_north_anom_zj"].iloc[-1]),
                    "receiver_h20_change_zj": h20_change,
                    "other_net_pathways_zj": h20_change - q5n_input,
                }
            )
    return pd.DataFrame(rows)


def percentile_interval(samples: np.ndarray) -> tuple[float, float]:
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return float(lower), float(upper)


def build_summary(events: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, float | int | str]] = []
    by_class: dict[str, pd.DataFrame] = {
        label: events.loc[events["event_class"] == label].reset_index(drop=True)
        for label in EVENTS
    }
    for metric in METRICS:
        for event_class, frame in by_class.items():
            values = frame[metric].to_numpy(dtype=float)
            indices = rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))
            boot = values[indices].mean(axis=1)
            lower, upper = percentile_interval(boot)
            rows.append(
                {
                    "contrast": event_class,
                    "metric": metric,
                    "n_events": len(values),
                    "mean_zj": float(values.mean()),
                    "ci_low_zj": lower,
                    "ci_high_zj": upper,
                }
            )

        ct = by_class["CT"][metric].to_numpy(dtype=float)
        cp = by_class["CP"][metric].to_numpy(dtype=float)
        ct_indices = rng.integers(0, len(ct), size=(BOOTSTRAP_SAMPLES, len(ct)))
        cp_indices = rng.integers(0, len(cp), size=(BOOTSTRAP_SAMPLES, len(cp)))
        boot_difference = ct[ct_indices].mean(axis=1) - cp[cp_indices].mean(axis=1)
        lower, upper = percentile_interval(boot_difference)
        rows.append(
            {
                "contrast": "CT_minus_CP",
                "metric": metric,
                "n_events": len(ct) + len(cp),
                "mean_zj": float(ct.mean() - cp.mean()),
                "ci_low_zj": lower,
                "ci_high_zj": upper,
            }
        )
    return pd.DataFrame(rows)


def value(summary: pd.DataFrame, contrast: str, metric: str) -> pd.Series:
    selected = summary.loc[
        (summary["contrast"] == contrast) & (summary["metric"] == metric)
    ]
    if len(selected) != 1:
        raise ValueError(f"Missing summary row: {contrast}, {metric}")
    return selected.iloc[0]


def write_report(events: pd.DataFrame, summary: pd.DataFrame) -> None:
    def formatted(contrast: str, metric: str) -> str:
        row = value(summary, contrast, metric)
        return (
            f"{row.mean_zj:+.2f} ZJ，95%区间 "
            f"[{row.ci_low_zj:+.2f}, {row.ci_high_zj:+.2f}]"
        )

    target_events = events.loc[events["event_year"].isin([1997, 2015])]
    target_lines = []
    for row in target_events.itertuples(index=False):
        target_lines.append(
            f"- {row.event_year}/{row.receiver_year}：5°N输入 {row.q5n_input_zj:+.2f} ZJ，"
            f"北侧箱H20变化 {row.receiver_h20_change_zj:+.2f} ZJ，"
            f"其他净通道 {row.other_net_pathways_zj:+.2f} ZJ。"
        )

    report = rf"""# 5°N出口之后：北侧接收箱的第二级暖量诊断

## 为什么必须增加第二级预算

5°N北向Q20是暖量离开赤道东太平洋箱体的出口，但同时是5°—12°N北侧箱体的入口。它不能直接等同于暖量已经离开热带太平洋。北侧接收箱固定为5.25°—11.25°N、140°W—80°W、0—300 m。

当前可直接计算：

\[
G_{{other}}=\Delta H_{{20,N}}-\int Q_{{5N}}\,dt.
\]

其中，`G_other`合并12°N、140°W和80°W边界输送、海表热通量、垂向/跨20°C面交换、混合、同化增量及时间离散。它不是一种已识别物理过程。

## CT/CP成熟—衰减期结果

时间严格取Jan(+1)月中到May(+1)月中，Q20按实际时间间隔作梯形积分。

- CT的5°N输入：{formatted('CT', 'q5n_input_zj')}；CP：{formatted('CP', 'q5n_input_zj')}；CT−CP：{formatted('CT_minus_CP', 'q5n_input_zj')}。
- CT北侧箱H20变化：{formatted('CT', 'receiver_h20_change_zj')}；CP：{formatted('CP', 'receiver_h20_change_zj')}。CT虽有显著北向输入，但北侧箱平均几乎没有净储热。
- CT其他净通道：{formatted('CT', 'other_net_pathways_zj')}；CP：{formatted('CP', 'other_net_pathways_zj')}；CT−CP：{formatted('CT_minus_CP', 'other_net_pathways_zj')}。

这说明CT中越过5°N的异常暖量主要没有表现为5°—12°N接收箱的净H20增长，而是被其他边界、海表或内部交换抵消。现有资料尚不能区分其中多少继续跨12°N、多少沿东西方向再分配、多少通过海表散失、多少经垂向和阈值转换离开H20定义。

## 代表事件

{chr(10).join(target_lines)}
- 2023/2024不进入接收箱结果，因为当前SODA3北侧三维温度子集只到2022年；不能用缺测把2023写成“留在北侧”或“继续排出”。

## 与早春时间窗口结果的统一解释

全年份扫描显示，Feb Q5N到Mar北侧H20变化、Mar Q5N到Apr北侧H20变化为正，事件尺度JFM输入与Jan—May储热变化也相关。这表示早春某些暖量脉冲可以先在北侧短暂积累。这里的成熟—衰减期合成进一步显示，这种积累不是最终归宿：在CT事件Jan—May尺度上，北侧箱平均储量几乎不增长，其他净通道为负。

因此完整表述应是：5°N首先承担赤道东箱向副热带接收区的跨箱转移；部分早春暖量可暂存于北侧，但成熟—衰减期CT合成中，大部分异常输入继续通过尚未显式分解的边界、海表或内部过程离开接收箱。

## 证据边界

- 这是异常量收支，不追踪同一水团；需要粒子或被动示踪才能回答拉格朗日路径。
- 接收箱尚未闭合全部边界，`G_other`只能作为待分解净项。
- CT和CP各4个事件，区间按整事件bootstrap计算，不能把月数当独立样本。
- Jan—May月中窗口与原Dec—May东箱预算不完全相同，数值不能逐项直接相减。
"""
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text(report, encoding="utf-8")


def main() -> None:
    monthly = pd.read_csv(INPUT, parse_dates=["time"])
    events = build_event_table(monthly)
    summary = build_summary(events)
    EVENT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(EVENT_OUTPUT, index=False, float_format="%.8f")
    summary.to_csv(SUMMARY_OUTPUT, index=False, float_format="%.8f")
    write_report(events, summary)
    print(EVENT_OUTPUT)
    print(SUMMARY_OUTPUT)
    print(REPORT_OUTPUT)


if __name__ == "__main__":
    main()
