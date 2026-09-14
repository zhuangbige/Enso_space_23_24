#!/usr/bin/env python3
"""Distinguish D20 -> warm-heat partition from partition -> D20.

The analysis uses three strictly ordered two-month transitions and controls
the earlier value of the response (a small-sample cross-lag design):

* Jan-Feb -> Mar-Apr
* Feb-Mar -> Apr-May
* Mar-Apr -> May-Jun

D20 is SODA3 equatorial D20 at 140W.  Warm-heat partition is the north-box
share of cumulative H20 change after equator+north total change is removed.
All ocean series use a common 1982--2022 calendar-month detrended baseline.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_d20_partition_direction_mpl")
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

from analyze_warm_heat_partition_coupling import (  # noqa: E402
    BASELINE,
    COLORS,
    EVENT_YEARS,
    HIGHLIGHTS,
    N_BOOTSTRAP,
    RANDOM_SEED,
    residualize,
    same_month_detrended,
    partial_relationship,
    mediation_test,
)


DATA = ROOT / "data/derived/research_2026"
EQUATOR = DATA / "enso_1997_2015_2023_warm_heat_fate_monthly.csv"
NORTH = DATA / "soda3_north_receiver_budget_monthly_1980_2024.csv"
D20_GATE = DATA / "soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
JIANG = DATA / "jiang_ne_wind_h20_exit_event_table.csv"

OUT = ROOT / "outputs/research_2026/d20_partition_direction"
EVENT_CSV = DATA / "d20_partition_direction_event_table.csv"
REL_CSV = DATA / "d20_partition_direction_relationships.csv"
MEDIATION_CSV = DATA / "d20_partition_direction_mediation.csv"
FIG_PNG = OUT / "d20_partition_direction.png"
FIG_PDF = OUT / "d20_partition_direction.pdf"
REPORT = OUT / "D20_PARTITION_DIRECTION_CN.md"
DIAGNOSTICS = DATA / "d20_partition_direction_diagnostics.json"


def validate_inputs(equator: pd.DataFrame, north: pd.DataFrame, d20: pd.DataFrame) -> None:
    for name, frame, columns in (
        ("equator", equator, ["year", "month", "east_h20_raw_zj"]),
        ("north", north, ["year", "month", "receiver_h20_zj"]),
        ("D20", d20, ["year", "month", "longitude_e", "d20_m"]),
    ):
        missing = set(columns).difference(frame.columns)
        if missing:
            raise ValueError(f"{name} missing {sorted(missing)}")
        if frame.duplicated(["year", "month"]).any():
            raise ValueError(f"{name} duplicate year-month records")
    for year in EVENT_YEARS:
        for name, frame in (("equator", equator), ("north", north), ("D20", d20)):
            months = set(frame.loc[frame.year.eq(year), "month"])
            if not set(range(1, 7)).issubset(months):
                raise ValueError(f"{name} lacks Jan-Jun for {year}")


def month_zscore(frame: pd.DataFrame, column: str) -> np.ndarray:
    output = np.full(len(frame), np.nan)
    for month, group in frame.groupby("month"):
        fit = group.year.between(BASELINE[0], BASELINE[1])
        mean = float(group.loc[fit, column].mean())
        scale = float(group.loc[fit, column].std(ddof=1))
        output[group.index] = (group[column] - mean) / scale
    return output


def build_events() -> pd.DataFrame:
    equator = pd.read_csv(EQUATOR)
    north = pd.read_csv(NORTH)
    d20 = pd.read_csv(D20_GATE)
    d20 = d20.loc[np.isclose(d20.longitude_e, 220.0)].copy().reset_index(drop=True)
    validate_inputs(equator, north, d20)
    equator["eq_h20_anom_zj"] = same_month_detrended(equator, "east_h20_raw_zj")
    north["north_h20_anom_zj"] = same_month_detrended(north, "receiver_h20_zj")
    d20["d20_anom_m"] = same_month_detrended(d20, "d20_m")
    d20["d20_z"] = month_zscore(d20, "d20_anom_m")
    monthly = (
        equator[["year", "month", "eq_h20_anom_zj"]]
        .merge(north[["year", "month", "north_h20_anom_zj"]], on=["year", "month"], validate="one_to_one")
        .merge(d20[["year", "month", "d20_anom_m", "d20_z"]], on=["year", "month"], validate="one_to_one")
    )
    monthly = monthly.loc[monthly.month.between(1, 6)].copy()

    rows: list[dict[str, float | int]] = []
    for year in EVENT_YEARS:
        current = monthly.loc[monthly.year.eq(year)].set_index("month")
        row: dict[str, float | int] = {"year": year}
        for end in range(2, 7):
            north_change = float(current.loc[end, "north_h20_anom_zj"] - current.loc[1, "north_h20_anom_zj"])
            eq_change = float(current.loc[end, "eq_h20_anom_zj"] - current.loc[1, "eq_h20_anom_zj"])
            row[f"delta_north_jan_to_m{end}_zj"] = north_change
            row[f"delta_eq_jan_to_m{end}_zj"] = eq_change
            row[f"delta_total_jan_to_m{end}_zj"] = north_change + eq_change
        for label, months in {
            "jf": (1, 2),
            "fm": (2, 3),
            "ma": (3, 4),
            "am": (4, 5),
            "mj": (5, 6),
        }.items():
            row[f"d20_{label}_z"] = float(current.loc[list(months), "d20_z"].mean())
            row[f"d20_{label}_m"] = float(current.loc[list(months), "d20_anom_m"].mean())
        rows.append(row)
    events = pd.DataFrame(rows)

    # Preserve the paper's 13-event definition of partition at each cutoff.
    for end in range(2, 7):
        north_name = f"delta_north_jan_to_m{end}_zj"
        total_name = f"delta_total_jan_to_m{end}_zj"
        residual = residualize(
            events[north_name].to_numpy(dtype=float),
            events[[total_name]].to_numpy(dtype=float),
        )
        events[f"partition_jan_to_m{end}_zj"] = residual
        events[f"partition_jan_to_m{end}_z"] = (
            residual - residual.mean()
        ) / residual.std(ddof=0)

    jiang = pd.read_csv(JIANG)[
        [
            "year", "group", "q140_mar_apr_z", "tau_response_mjj",
            "precip_response_mjj", "slp_response_mjj", "ne925_mjj_ms",
        ]
    ]
    events = events.merge(jiang, on="year", validate="one_to_one").sort_values("year").reset_index(drop=True)
    if len(events) != len(EVENT_YEARS) or events.select_dtypes(include=[np.number]).isna().any().any():
        raise ValueError("D20-partition event table is incomplete")
    return events


def build_relationships(events: pd.DataFrame) -> pd.DataFrame:
    tests = [
        (
            "d20_jf_to_partition_apr", "D20 JF -> partition Jan-Apr | partition Jan-Feb",
            "d20_jf_z", "partition_jan_to_m4_z", ("partition_jan_to_m2_z",),
        ),
        (
            "partition_feb_to_d20_ma", "Partition Jan-Feb -> D20 MA | D20 JF",
            "partition_jan_to_m2_z", "d20_ma_z", ("d20_jf_z",),
        ),
        (
            "d20_fm_to_partition_may", "D20 FM -> partition Jan-May | partition Jan-Mar",
            "d20_fm_z", "partition_jan_to_m5_z", ("partition_jan_to_m3_z",),
        ),
        (
            "partition_mar_to_d20_am", "Partition Jan-Mar -> D20 AM | D20 FM",
            "partition_jan_to_m3_z", "d20_am_z", ("d20_fm_z",),
        ),
        (
            "d20_ma_to_partition_jun", "D20 MA -> partition Jan-Jun | partition Jan-Apr",
            "d20_ma_z", "partition_jan_to_m6_z", ("partition_jan_to_m4_z",),
        ),
        (
            "partition_apr_to_d20_mj", "Partition Jan-Apr -> D20 MJ | D20 MA",
            "partition_jan_to_m4_z", "d20_mj_z", ("d20_ma_z",),
        ),
        (
            "partition_apr_to_tau_after_early_d20", "Partition Jan-Apr -> MJJ wind stress | D20 JF and early partition",
            "partition_jan_to_m4_z", "tau_response_mjj", ("d20_jf_z", "partition_jan_to_m2_z"),
        ),
        (
            "partition_apr_to_tau_after_early_d20_arrival", "Partition Jan-Apr -> MJJ wind stress | early D20, early partition and arrival",
            "partition_jan_to_m4_z", "tau_response_mjj", ("d20_jf_z", "partition_jan_to_m2_z", "q140_mar_apr_z"),
        ),
        (
            "early_d20_to_tau", "D20 JF -> MJJ wind stress | early partition",
            "d20_jf_z", "tau_response_mjj", ("partition_jan_to_m2_z",),
        ),
        (
            "partition_to_tau_after_concurrent_d20", "Partition Jan-Apr -> MJJ wind stress | concurrent D20 MA",
            "partition_jan_to_m4_z", "tau_response_mjj", ("d20_ma_z",),
        ),
        (
            "concurrent_d20_partition", "Concurrent D20 MA vs partition Jan-Apr",
            "d20_ma_z", "partition_jan_to_m4_z", (),
        ),
    ]
    return pd.DataFrame(
        [
            partial_relationship(events, test_id, label, x, y, controls, 500 + index)
            for index, (test_id, label, x, y, controls) in enumerate(tests)
        ]
    )


def build_mediation(events: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            mediation_test(
                events,
                "early_d20_partition_wind",
                "D20 JF -> partition Jan-Apr -> MJJ wind stress",
                "d20_jf_z",
                "partition_jan_to_m4_z",
                "tau_response_mjj",
                ("partition_jan_to_m2_z",),
                700,
            )
        ]
    )


def setup_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial Unicode MS", "PingFang SC", "Heiti SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 9.8,
            "axes.titlesize": 10.8,
            "axes.labelsize": 9.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.dpi": 400,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def relationship_residuals(events: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    controls = tuple(str(row.controls).split(";")) if isinstance(row.controls, str) and row.controls else ()
    output = events[["year"]].copy()
    x = events[row.x].to_numpy(dtype=float)
    y = events[row.y].to_numpy(dtype=float)
    if controls:
        c = events[list(controls)].to_numpy(dtype=float)
        output["x"] = residualize(x, c)
        output["y"] = residualize(y, c)
    else:
        output["x"] = x - x.mean()
        output["y"] = y - y.mean()
    return output


def scatter(
    axis: plt.Axes,
    frame: pd.DataFrame,
    title: str,
    xlabel: str,
    ylabel: str,
    row: pd.Series,
    stats_x: float = 0.04,
) -> None:
    ordinary = ~frame.year.isin(HIGHLIGHTS)
    axis.scatter(frame.loc[ordinary, "x"], frame.loc[ordinary, "y"], s=34, color="#999999", edgecolor="white", linewidth=0.5)
    for year in HIGHLIGHTS:
        point = frame.loc[frame.year.eq(year)].iloc[0]
        axis.scatter(point.x, point.y, s=72, color=COLORS[year], edgecolor="white", linewidth=0.7, zorder=4)
        axis.annotate(str(year), (point.x, point.y), xytext=(5, 5), textcoords="offset points", color=COLORS[year], fontsize=8.8)
    slope, intercept = np.polyfit(frame.x, frame.y, 1)
    xx = np.linspace(float(frame.x.min()), float(frame.x.max()), 100)
    axis.plot(xx, slope * xx + intercept, color="#263238", lw=1.4)
    axis.axhline(0, color="#888888", lw=0.7)
    axis.axvline(0, color="#888888", lw=0.7)
    axis.set_title(title, loc="left", fontweight="bold")
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.text(stats_x, 0.95, f"partial r={row.partial_r:+.2f}\np={row.permutation_p:.3f}", transform=axis.transAxes, va="top")


def forest(axis: plt.Axes, rows: list[pd.Series], labels: list[str], colors: list[str]) -> None:
    for position, (row, label, color) in enumerate(zip(rows, labels, colors, strict=True)):
        value = float(row.partial_r)
        low, high = float(row.bootstrap_ci_low), float(row.bootstrap_ci_high)
        axis.errorbar(value, position, xerr=np.array([[value - low], [high - value]]), fmt="o", color=color, ecolor=color, capsize=3, elinewidth=1.8, markersize=6.5)
        axis.text(0.98, position, f"p={row.permutation_p:.3f}", transform=axis.get_yaxis_transform(), ha="right", va="center", fontsize=8.3)
    axis.axvline(0, color="#666666", lw=0.8)
    axis.set_yticks(np.arange(len(rows)), labels)
    axis.invert_yaxis()
    axis.set_xlim(-1.05, 1.05)


def plot_results(events: pd.DataFrame, relationships: pd.DataFrame, mediation: pd.DataFrame) -> None:
    setup_style()
    OUT.mkdir(parents=True, exist_ok=True)
    lookup = relationships.set_index("test_id")
    med = mediation.iloc[0]
    fig, axes = plt.subplots(2, 3, figsize=(15.2, 8.8))
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.10, top=0.885, hspace=0.37, wspace=0.31)

    axis = axes[0, 0]
    month_x = np.arange(2, 7)
    for year in HIGHLIGHTS:
        row = events.loc[events.year.eq(year)].iloc[0]
        partition = [row[f"partition_jan_to_m{month}_z"] for month in month_x]
        axis.plot(month_x, partition, color=COLORS[year], marker="o", lw=1.8, label=f"{year} partition")
    axis.axhline(0, color="#777777", lw=0.7)
    axis.set_xticks(month_x, ["Feb", "Mar", "Apr", "May", "Jun"])
    axis.set_ylabel("累计北侧分配残差（标准化）")
    axis.set_title("a  2023的正分配异常在春季形成", loc="left", fontweight="bold")
    axis.legend(frameon=False, fontsize=8.2)

    row = lookup.loc["d20_jf_to_partition_apr"]
    scatter(
        axes[0, 1], relationship_residuals(events, row),
        "b  早期D20能否预测后期partition？",
        "Jan–Feb D20（去除早期partition）",
        "Jan–Apr partition（条件残差）",
        row,
    )
    row = lookup.loc["partition_feb_to_d20_ma"]
    scatter(
        axes[0, 2], relationship_residuals(events, row),
        "c  早期partition能否预测后期D20？",
        "Jan–Feb partition（去除早期D20）",
        "Mar–Apr D20（条件残差）",
        row,
    )

    axis = axes[1, 0]
    forward_ids = ["d20_jf_to_partition_apr", "d20_fm_to_partition_may", "d20_ma_to_partition_jun"]
    reverse_ids = ["partition_feb_to_d20_ma", "partition_mar_to_d20_am", "partition_apr_to_d20_mj"]
    rows = [lookup.loc[item] for pair in zip(forward_ids, reverse_ids, strict=True) for item in pair]
    labels = ["D20 JF→P Apr", "P Feb→D20 MA", "D20 FM→P May", "P Mar→D20 AM", "D20 MA→P Jun", "P Apr→D20 MJ"]
    colors = ["#7B1FA2", "#00838F"] * 3
    forest(axis, rows, labels, colors)
    axis.set_xlabel("交叉滞后偏相关")
    axis.set_title("d  三组窗口没有给出稳定单向领先", loc="left", fontweight="bold")

    row = lookup.loc["partition_apr_to_tau_after_early_d20_arrival"]
    scatter(
        axes[1, 1], relationship_residuals(events, row),
        "e  控制早期D20和到达量后，partition仍连接风响应",
        "Jan–Apr partition（去除早期D20/partition与到达量）",
        "MJJ风应力响应（条件残差）",
        row,
        stats_x=0.66,
    )

    axis = axes[1, 2]
    axis.set_axis_off()
    axis.text(0.02, 0.94, "f  D20→partition→风：未闭合", transform=axis.transAxes, va="top", fontsize=10.8, fontweight="bold")
    nodes = [(0.16, 0.59, "Jan–Feb\nD20"), (0.50, 0.59, "Jan–Apr\npartition"), (0.84, 0.59, "May–Jul\n风应力")]
    for x, y, text in nodes:
        axis.text(x, y, text, transform=axis.transAxes, ha="center", va="center", bbox=dict(boxstyle="round,pad=0.45", fc="#F5F7FA", ec="#546E7A", lw=1.2))
    axis.annotate("", xy=(0.40, 0.59), xytext=(0.26, 0.59), xycoords="axes fraction", arrowprops=dict(arrowstyle="->", lw=1.6))
    axis.annotate("", xy=(0.74, 0.59), xytext=(0.60, 0.59), xycoords="axes fraction", arrowprops=dict(arrowstyle="->", lw=1.6))
    axis.text(0.33, 0.65, f"a={med.a:+.2f}", transform=axis.transAxes, ha="center", fontweight="bold")
    axis.text(0.67, 0.65, f"b={med.b:+.2f}", transform=axis.transAxes, ha="center", fontweight="bold")
    axis.text(0.50, 0.32, f"间接效应={med.indirect:+.2f}\n95% CI [{med.indirect_ci_low:+.2f}, {med.indirect_ci_high:+.2f}]\n同号bootstrap比例={med.indirect_same_sign_fraction:.2f}", transform=axis.transAxes, ha="center", va="center")

    fig.suptitle("D20与暖量分配共享春季演变，但现有事件样本未证明D20单向驱动partition", fontsize=15, fontweight="bold", y=0.962)
    fig.text(0.5, 0.026, "SODA3 D20：0°, 140°W；partition：140°W–80°W赤道+北侧H₂₀中北侧条件份额；共同1982–2022基准；13个暖事件", ha="center", fontsize=9.1)
    fig.savefig(FIG_PNG, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_report(events: pd.DataFrame, relationships: pd.DataFrame, mediation: pd.DataFrame) -> None:
    r = relationships.set_index("test_id")
    m = mediation.iloc[0]
    selected = events.set_index("year").loc[list(HIGHLIGHTS)]
    lines = [
        "# D20与暖量空间分配：谁领先谁？",
        "",
        "## 结论",
        "",
        "**当前13事件交叉滞后检验没有证明“早期D20单向驱动后续暖量偏北分配”，也没有证明相反方向。D20与partition更像共享同一春季调整过程；其中partition是距离后续海气响应更近的统计表征。**",
        "",
        f"主窗口Jan—Feb → Mar—Apr中，D20预测后期partition、同时控制早期partition后的偏相关为r={r.loc['d20_jf_to_partition_apr'].partial_r:+.2f}（p={r.loc['d20_jf_to_partition_apr'].permutation_p:.3f}）；反向partition预测后期D20、控制早期D20后为r={r.loc['partition_feb_to_d20_ma'].partial_r:+.2f}（p={r.loc['partition_feb_to_d20_ma'].permutation_p:.3f}）。两者都不稳健。",
        f"但Jan—Apr partition在控制Jan—Feb D20、早期partition和Mar—Apr到达量后，仍对应较弱的MJJ风应力响应（r={r.loc['partition_apr_to_tau_after_early_d20_arrival'].partial_r:+.2f}, p={r.loc['partition_apr_to_tau_after_early_d20_arrival'].permutation_p:.3f}）。因此早期D20并未替代partition对后续耦合效率的信息。",
        "",
        "## 三组交叉滞后窗口",
        "",
        "| 方向 | partial r | permutation p | 95% CI |",
        "|---|---:|---:|---:|",
    ]
    ids = [
        "d20_jf_to_partition_apr", "partition_feb_to_d20_ma",
        "d20_fm_to_partition_may", "partition_mar_to_d20_am",
        "d20_ma_to_partition_jun", "partition_apr_to_d20_mj",
    ]
    for test_id in ids:
        row = r.loc[test_id]
        lines.append(f"| {row.label} | {row.partial_r:+.2f} | {row.permutation_p:.3f} | [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}] |")
    lines += [
        "",
        "如果D20是稳定上游原因，三组D20→partition关系应连续同号且强于反向路径；实际结果没有出现这种结构。个别反向窗口较强，但也不跨窗口稳定，因此不能据此改写成partition驱动D20。",
        "",
        "## 探索性D20中介路径",
        "",
        f"路径D20(JF) → partition(Jan—Apr) → wind(MJJ)得到a={m.a:+.2f}、b={m.b:+.2f}、间接效应ab={m.indirect:+.2f}，95% bootstrap CI [{m.indirect_ci_low:+.2f}, {m.indirect_ci_high:+.2f}]。区间跨零，因此D20→partition→大气的中介链尚未闭合。",
        "",
        "## 三事件的时间位置",
        "",
        "| 事件 | D20 JF | partition Jan→Feb | D20 MA | partition Jan→Apr | MJJ风应力响应 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in HIGHLIGHTS:
        row = selected.loc[year]
        lines.append(f"| {year} | {row.d20_jf_z:+.2f} SD | {row.partition_jan_to_m2_z:+.2f} SD | {row.d20_ma_z:+.2f} SD | {row.partition_jan_to_m4_z:+.2f} SD | {row.tau_response_mjj:+.2f} |")
    lines += [
        "",
        "2023早期D20并不深，但到Mar—Apr有所增加，同时累计partition由中等正值进一步发展为明显正异常。1997则是D20很深、partition持续偏南/偏赤道；2015的早期partition为正，但到4月转为负。三个案例符合D20与partition共同演化，但不足以决定因果箭头。",
        "",
        "## 论文中应如何写",
        "",
        "推荐：空间分配效应与大尺度温跃层结构并不独立；交叉滞后检验尚未识别稳定单向关系，表明D20和partition可能是同一春季海洋调整的相互关联表现。partition在控制早期D20后仍保留对后续风应力响应的信息，因此可作为温跃层动力状态映射到海气接通效率上的近端可观测表征。",
        "",
        "不推荐：D20已经被证明通过北向暖量分配造成海气响应减弱。",
        "",
        "## 下一步",
        "",
        "观测统计已经接近样本上限。下一步最有增量的不是继续换窗口，而是用海洋动力诊断分解D20—partition共同变化：检查SSH/压力梯度、地转经向输送、风驱Ekman输送和边界波传播；决定性因果证据仍需要耦合模式中独立扰动D20斜率与暖量南北分配。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = build_events()
    relationships = build_relationships(events)
    mediation = build_mediation(events)
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    relationships.to_csv(REL_CSV, index=False, float_format="%.9g")
    mediation.to_csv(MEDIATION_CSV, index=False, float_format="%.9g")
    plot_results(events, relationships, mediation)
    write_report(events, relationships, mediation)
    diagnostics = {
        "d20_location": "0N, 140W",
        "partition_definition": "cumulative north H20 change residual conditional on equator+north total H20 change",
        "baseline": list(BASELINE),
        "cross_lag_transitions": ["JF -> MA", "FM -> AM", "MA -> MJ"],
        "n_events": len(events),
        "event_years": list(EVENT_YEARS),
        "interpretation": "Cross-lag associations do not identify a stable one-way D20-partition direction.",
    }
    DIAGNOSTICS.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(EVENT_CSV)
    print(REL_CSV)
    print(MEDIATION_CSV)
    print(FIG_PNG)
    print(FIG_PDF)
    print(REPORT)


if __name__ == "__main__":
    main()
