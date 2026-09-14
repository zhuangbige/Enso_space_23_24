#!/usr/bin/env python3
"""Close the SODA3 H20 budget north of the eastern equatorial Pacific.

The fixed receiver box is 5N--12N, 140W--80W and 0--300 m.  All explicit
terms use the sign convention positive into the box.  The analysis follows
the same calendar-month detrending, centered three-month smoothing, event
partition and phase windows as the existing CT/CP three-box budget.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_chakravorty2021_soda3_baseline as legacy  # noqa: E402


INPUT = ROOT / "data/derived/research_2026/soda3_north_receiver_budget_terms_1980_2022.csv"
EXTENSION = ROOT / "data/derived/research_2026/soda3_north_receiver_budget_terms_2023_2024.csv"
OLD_EAST = ROOT / "data/derived/research_2026/soda3_three_box_warm_heat_budget_terms_1980_2022.csv"
RECENT_5N = ROOT / "data/derived/research_2026/enso_1997_2015_2023_5n_geostrophic_fate_monthly.csv"
OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_north_receiver_budget"

MONTHLY_OUTPUT = OUT_DATA / "soda3_north_receiver_budget_monthly_1980_2024.csv"
EVENT_OUTPUT = OUT_DATA / "soda3_north_receiver_budget_event_cumulative.csv"
SUMMARY_OUTPUT = OUT_DATA / "soda3_north_receiver_budget_summary.csv"
DIAGNOSTICS_OUTPUT = OUT_DATA / "soda3_north_receiver_budget_diagnostics.json"
REPORT_OUTPUT = OUT_DIR / "SODA3_NORTH_RECEIVER_WARM_HEAT_BUDGET_CN.md"

BASELINE = (1980, 2022)
EVENTS = legacy.EVENTS
ADDITIONAL_EVENTS = (2015, 2023)
RELATIVE_MONTHS = legacy.RELATIVE_MONTHS
PHASES = {
    "development_Jun0_to_Nov0": (5, 10),
    "mature_decay_Dec0_to_May1": (11, 16),
    "jan1_to_may1": (12, 16),
}
COMPONENTS = (
    "zonal_convergence",
    "south_q20_in",
    "north_q20_in",
    "surface_warm",
    "surface_all",
    "residual_warm",
    "residual_all_surface",
    "storage_tendency",
)
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260809


def centered_storage_tendency_pw(
    storage_zj: np.ndarray,
    times: pd.DatetimeIndex,
) -> np.ndarray:
    values = np.asarray(storage_zj, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    seconds = (times[2:] - times[:-2]).total_seconds().to_numpy(dtype=float)
    output[1:-1] = (values[2:] - values[:-2]) * 1.0e6 / seconds
    return output


def process_series(values: np.ndarray, times: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    anomaly = legacy.same_month_detrended(values, times, BASELINE)
    smoothed = (
        pd.Series(anomaly)
        .rolling(window=3, center=True, min_periods=3)
        .mean()
        .to_numpy()
    )
    return anomaly, smoothed


def build_monthly(raw: pd.DataFrame) -> pd.DataFrame:
    output = raw.copy().sort_values("time").reset_index(drop=True)
    output["time"] = pd.to_datetime(output["time"])
    times = pd.DatetimeIndex(output["time"])
    expected = pd.date_range("1980-01-01", "2024-07-01", freq="MS") + pd.Timedelta(days=14)
    if not times.equals(expected):
        raise ValueError("Incomplete 1980--2022 monthly axis")

    output["receiver_storage_tendency_pw"] = centered_storage_tendency_pw(
        output["receiver_h20_zj"].to_numpy(), times
    )
    raw_metrics = (
        "receiver_h20_zj",
        "receiver_storage_tendency_pw",
        "receiver_west_q20_east_pw",
        "receiver_east_q20_east_pw",
        "receiver_south_q20_in_pw",
        "receiver_north_q20_in_pw",
        "receiver_zonal_convergence_pw",
        "receiver_meridional_convergence_pw",
        "receiver_surface_warm_pw",
        "receiver_surface_all_pw",
    )
    for source in raw_metrics:
        anomaly, smoothed = process_series(output[source].to_numpy(), times)
        short = source.removesuffix("_pw")
        output[f"{short}_anom"] = anomaly
        output[f"{short}_sm3"] = smoothed

    explicit_warm_anom = (
        output["receiver_zonal_convergence_anom"]
        + output["receiver_south_q20_in_anom"]
        + output["receiver_north_q20_in_anom"]
        + output["receiver_surface_warm_anom"]
    )
    explicit_warm_sm3 = (
        output["receiver_zonal_convergence_sm3"]
        + output["receiver_south_q20_in_sm3"]
        + output["receiver_north_q20_in_sm3"]
        + output["receiver_surface_warm_sm3"]
    )
    explicit_all_anom = (
        output["receiver_zonal_convergence_anom"]
        + output["receiver_south_q20_in_anom"]
        + output["receiver_north_q20_in_anom"]
        + output["receiver_surface_all_anom"]
    )
    explicit_all_sm3 = (
        output["receiver_zonal_convergence_sm3"]
        + output["receiver_south_q20_in_sm3"]
        + output["receiver_north_q20_in_sm3"]
        + output["receiver_surface_all_sm3"]
    )
    output["receiver_residual_warm_anom"] = (
        output["receiver_storage_tendency_anom"] - explicit_warm_anom
    )
    output["receiver_residual_warm_sm3"] = (
        output["receiver_storage_tendency_sm3"] - explicit_warm_sm3
    )
    output["receiver_residual_all_surface_anom"] = (
        output["receiver_storage_tendency_anom"] - explicit_all_anom
    )
    output["receiver_residual_all_surface_sm3"] = (
        output["receiver_storage_tendency_sm3"] - explicit_all_sm3
    )
    closure = output["receiver_storage_tendency_sm3"] - (
        explicit_warm_sm3 + output["receiver_residual_warm_sm3"]
    )
    if float(np.nanmax(np.abs(closure))) > 1.0e-12:
        raise ValueError("Processed receiver budget does not close")
    return output


def align_events(monthly: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "receiver_h20_zj_sm3",
        "receiver_west_q20_east_sm3",
        "receiver_east_q20_east_sm3",
        *[f"receiver_{component}_sm3" for component in COMPONENTS],
    ]
    event_groups = {**EVENTS, "additional": ADDITIONAL_EVENTS}
    indexed = monthly.set_index(pd.DatetimeIndex(monthly["time"]))
    rows: list[dict[str, object]] = []
    for event_class, event_years in event_groups.items():
        for event_year in event_years:
            for relative_month in RELATIVE_MONTHS:
                timestamp = pd.Timestamp(event_year, 1, 15) + pd.DateOffset(
                    months=int(relative_month)
                )
                row: dict[str, object] = {
                    "event_class": event_class,
                    "event_year": event_year,
                    "relative_month": int(relative_month),
                    "time": timestamp,
                    "days_in_month": timestamp.days_in_month,
                }
                for metric in metrics:
                    value = indexed.loc[timestamp, metric]
                    if not np.isfinite(value):
                        raise ValueError(f"Missing {metric} for {timestamp}")
                    row[metric] = float(value)
                rows.append(row)
    return pd.DataFrame(rows)


def cumulative_events(aligned: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    metrics = [
        "west_q20_east",
        "east_q20_east",
        *COMPONENTS,
    ]
    for (event_class, event_year), event in aligned.groupby(
        ["event_class", "event_year"], sort=True
    ):
        for phase, (start, end) in PHASES.items():
            selected = event.loc[event["relative_month"].between(start, end)].sort_values(
                "relative_month"
            )
            factor = selected["days_in_month"].to_numpy(dtype=float) * 86400.0 / 1.0e6
            for metric in metrics:
                column = f"receiver_{metric}_sm3"
                rows.append(
                    {
                        "event_class": event_class,
                        "event_year": int(event_year),
                        "phase": phase,
                        "component": metric,
                        "cumulative_zj": float(
                            np.sum(selected[column].to_numpy(dtype=float) * factor)
                        ),
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_summary(cumulative: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, object]] = []
    for phase in PHASES:
        for component in ("west_q20_east", "east_q20_east", *COMPONENTS):
            class_values: dict[str, np.ndarray] = {}
            for event_class, event_years in EVENTS.items():
                values = (
                    cumulative.loc[
                        (cumulative["event_class"] == event_class)
                        & (cumulative["phase"] == phase)
                        & (cumulative["component"] == component)
                    ]
                    .set_index("event_year")["cumulative_zj"]
                    .reindex(event_years)
                    .to_numpy(dtype=float)
                )
                if not np.isfinite(values).all():
                    raise ValueError(f"Incomplete {event_class}, {phase}, {component}")
                class_values[event_class] = values
                indices = rng.integers(
                    0, len(values), size=(BOOTSTRAP_SAMPLES, len(values))
                )
                boot = values[indices].mean(axis=1)
                lower, upper = np.quantile(boot, [0.025, 0.975])
                rows.append(
                    {
                        "contrast": event_class,
                        "phase": phase,
                        "component": component,
                        "n_events": len(values),
                        "mean_zj": float(values.mean()),
                        "ci_low_zj": float(lower),
                        "ci_high_zj": float(upper),
                    }
                )
            ct = class_values["CT"]
            cp = class_values["CP"]
            ct_indices = rng.integers(0, len(ct), size=(BOOTSTRAP_SAMPLES, len(ct)))
            cp_indices = rng.integers(0, len(cp), size=(BOOTSTRAP_SAMPLES, len(cp)))
            difference = ct[ct_indices].mean(axis=1) - cp[cp_indices].mean(axis=1)
            lower, upper = np.quantile(difference, [0.025, 0.975])
            rows.append(
                {
                    "contrast": "CT_minus_CP",
                    "phase": phase,
                    "component": component,
                    "n_events": len(ct) + len(cp),
                    "mean_zj": float(ct.mean() - cp.mean()),
                    "ci_low_zj": float(lower),
                    "ci_high_zj": float(upper),
                }
            )
    return pd.DataFrame(rows)


def summary_row(summary: pd.DataFrame, contrast: str, phase: str, component: str) -> pd.Series:
    selected = summary.loc[
        (summary["contrast"] == contrast)
        & (summary["phase"] == phase)
        & (summary["component"] == component)
    ]
    if len(selected) != 1:
        raise ValueError(f"Missing summary row: {contrast}, {phase}, {component}")
    return selected.iloc[0]


def format_summary(summary: pd.DataFrame, contrast: str, phase: str, component: str) -> str:
    row = summary_row(summary, contrast, phase, component)
    return (
        f"{row.mean_zj:+.2f} ZJ "
        f"[{row.ci_low_zj:+.2f}, {row.ci_high_zj:+.2f}]"
    )


def event_value(cumulative: pd.DataFrame, event_year: int, phase: str, component: str) -> float:
    selected = cumulative.loc[
        (cumulative["event_year"] == event_year)
        & (cumulative["phase"] == phase)
        & (cumulative["component"] == component)
    ]
    if len(selected) != 1:
        raise ValueError(f"Missing event value: {event_year}, {phase}, {component}")
    return float(selected.iloc[0]["cumulative_zj"])


def write_report(summary: pd.DataFrame, cumulative: pd.DataFrame, diagnostics: dict) -> None:
    phase = "mature_decay_Dec0_to_May1"
    lines = []
    for year in (1997, 2015, 2023):
        values = {
            component: event_value(cumulative, year, phase, component)
            for component in (
                "west_q20_east",
                "east_q20_east",
                "south_q20_in",
                "north_q20_in",
                "zonal_convergence",
                "surface_warm",
                "residual_warm",
                "storage_tendency",
            )
        }
        lines.append(
            f"- {year}/{year + 1}：5°N输入 {values['south_q20_in']:+.2f} ZJ，"
            f"12°N输入项 {values['north_q20_in']:+.2f} ZJ，纬向汇聚 "
            f"{values['zonal_convergence']:+.2f} ZJ（140°W东向项 "
            f"{values['west_q20_east']:+.2f}，80°W东向项 "
            f"{values['east_q20_east']:+.2f} ZJ），海表项 {values['surface_warm']:+.2f} ZJ，"
            f"残差 {values['residual_warm']:+.2f} ZJ，储量倾向积分 "
            f"{values['storage_tendency']:+.2f} ZJ。"
        )

    report = rf"""# SODA3北侧接收箱完整暖量预算

## 控制体与符号

接收箱固定为5°N—12°N、140°W—80°W、0—300 m。所有项以进入箱体为正：

\[
\frac{{dH_{{20,N}}}}{{dt}}
=C_{{x,N}}+F_{{5N}}+F_{{12N}}+Q_{{surface,N}}+R_N.
\]

`F5N>0`表示暖量从赤道东箱进入北侧箱；`F12N<0`表示继续跨12°N向北输出；`Cx<0`表示纬向辐散；表面项为负表示海洋向大气净失热。残差包含垂向/跨20°C面交换、混合扩散、同化增量及月平均离散。

## CT/CP成熟—衰减期 Dec(0)—May(+1)

| 项目 | CT | CP | CT−CP |
|---|---:|---:|---:|
| 5°N输入 | {format_summary(summary, 'CT', phase, 'south_q20_in')} | {format_summary(summary, 'CP', phase, 'south_q20_in')} | {format_summary(summary, 'CT_minus_CP', phase, 'south_q20_in')} |
| 12°N输入项 | {format_summary(summary, 'CT', phase, 'north_q20_in')} | {format_summary(summary, 'CP', phase, 'north_q20_in')} | {format_summary(summary, 'CT_minus_CP', phase, 'north_q20_in')} |
| 纬向汇聚 | {format_summary(summary, 'CT', phase, 'zonal_convergence')} | {format_summary(summary, 'CP', phase, 'zonal_convergence')} | {format_summary(summary, 'CT_minus_CP', phase, 'zonal_convergence')} |
| 海表暖层项 | {format_summary(summary, 'CT', phase, 'surface_warm')} | {format_summary(summary, 'CP', phase, 'surface_warm')} | {format_summary(summary, 'CT_minus_CP', phase, 'surface_warm')} |
| 剩余项 | {format_summary(summary, 'CT', phase, 'residual_warm')} | {format_summary(summary, 'CP', phase, 'residual_warm')} | {format_summary(summary, 'CT_minus_CP', phase, 'residual_warm')} |
| 储量倾向积分 | {format_summary(summary, 'CT', phase, 'storage_tendency')} | {format_summary(summary, 'CP', phase, 'storage_tendency')} | {format_summary(summary, 'CT_minus_CP', phase, 'storage_tendency')} |

表中12°N采用入箱符号，因此负数才表示暖量继续向北离开接收箱。纬向汇聚只表示140°W输入减80°W输出，不能自动解释为某一侧的最终出口。

## 直接判断

- CT从5°N获得+2.74 ZJ异常输入，但12°N项仅-0.06 ZJ且区间跨零，因此暖量没有形成可辨识的“5°N进入后继续跨12°N北逃”。
- CT纬向汇聚为-1.65 ZJ；分开两个边界后，140°W东向项为负、80°W项接近零，说明主要是暖量从北侧箱向西返回140°W以西，而不是继续向东穿过80°W。
- CT北侧海表项为-1.70 ZJ，表明海气散热与向西再分配量级相近。残差+1.27 ZJ部分回补这些显式损失，最终北侧储量倾向仍为+0.60 ZJ。
- CP方向不同：5°N项为-0.96 ZJ，表示北侧暖量向南返回赤道东箱；同时140°W提供东向输入。因此CT/CP差异不是“北侧储不储热”的简单二分，而是北侧环流方向发生了重组。

## 代表事件

{chr(10).join(lines)}

## QA

- 完整月份：{diagnostics['n_months']}；
- 5°N接收箱输入与旧东箱5°N流出符号反转后的最大绝对差：{diagnostics['q5n_crosscheck_max_abs_pw']:.3e} PW；
- 2024年5°N原始Q20与独立地转分解输入的最大绝对差：{diagnostics['recent_q5n_crosscheck_max_abs_pw']:.3e} PW；
- 处理后预算最大代数闭合误差：{diagnostics['processed_closure_max_abs_pw']:.3e} PW；
- 主暖层表面项与全表面项的CT−CP差异敏感性见汇总CSV，二者均保留，避免把低于20°C表层的加热误计入H20。

## 证据边界

- 这是欧拉异常预算，不追踪同一团水；
- 残差按定义闭合，不能当作独立物理验证；
- CT和CP各4个事件，区间按整事件bootstrap；
- 12°N输出若不显著，不能据此断言暖量停留，因为纬向、海表和残差仍可移走H20。
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text(report, encoding="utf-8")


def main() -> None:
    raw = pd.concat(
        [
            pd.read_csv(INPUT, parse_dates=["time"]),
            pd.read_csv(EXTENSION, parse_dates=["time"]),
        ],
        ignore_index=True,
    ).sort_values("time").reset_index(drop=True)
    monthly = build_monthly(raw)
    aligned = align_events(monthly)
    cumulative = cumulative_events(aligned)
    summary = bootstrap_summary(cumulative)

    old = pd.read_csv(OLD_EAST, parse_dates=["time"])
    crosscheck = raw[["time", "receiver_south_q20_in_pw"]].merge(
        old[["time", "east_north_q20_in_pw"]], on="time", validate="one_to_one"
    )
    q5n_error = (
        crosscheck["receiver_south_q20_in_pw"]
        + crosscheck["east_north_q20_in_pw"]
    )
    processed_closure = monthly["receiver_storage_tendency_sm3"] - (
        monthly["receiver_zonal_convergence_sm3"]
        + monthly["receiver_south_q20_in_sm3"]
        + monthly["receiver_north_q20_in_sm3"]
        + monthly["receiver_surface_warm_sm3"]
        + monthly["receiver_residual_warm_sm3"]
    )
    recent = pd.read_csv(RECENT_5N, parse_dates=["time"])
    recent_crosscheck = raw[["time", "receiver_south_q20_in_pw"]].merge(
        recent[["time", "total_raw_pw"]], on="time", validate="one_to_one"
    )
    diagnostics = {
        "n_months": len(monthly),
        "baseline": list(BASELINE),
        "receiver_box": "5N-12N, 140W-80W, 0-300m",
        "q5n_crosscheck_max_abs_pw": float(np.nanmax(np.abs(q5n_error))),
        "q5n_crosscheck_correlation": float(
            np.corrcoef(
                crosscheck["receiver_south_q20_in_pw"],
                -crosscheck["east_north_q20_in_pw"],
            )[0, 1]
        ),
        "recent_q5n_crosscheck_max_abs_pw": float(
            np.nanmax(
                np.abs(
                    recent_crosscheck["receiver_south_q20_in_pw"]
                    - recent_crosscheck["total_raw_pw"]
                )
            )
        ),
        "processed_closure_max_abs_pw": float(np.nanmax(np.abs(processed_closure))),
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
    }

    monthly.to_csv(MONTHLY_OUTPUT, index=False, float_format="%.9g")
    cumulative.to_csv(EVENT_OUTPUT, index=False, float_format="%.9g")
    summary.to_csv(SUMMARY_OUTPUT, index=False, float_format="%.9g")
    DIAGNOSTICS_OUTPUT.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(summary, cumulative, diagnostics)
    print(MONTHLY_OUTPUT)
    print(EVENT_OUTPUT)
    print(SUMMARY_OUTPUT)
    print(DIAGNOSTICS_OUTPUT)
    print(REPORT_OUTPUT)


if __name__ == "__main__":
    main()
