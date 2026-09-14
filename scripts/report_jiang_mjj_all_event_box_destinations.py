#!/usr/bin/env python3
"""Report every MJJ heat-budget pathway for the Jiang EP/CP event sample.

The input is the event-integrated two-box anomaly budget produced by
``analyze_jiang_epcp_two_box_heat_fate.py``.  This script changes the sign of
all boundary, surface, and unresolved terms to a common destination-oriented
convention:

    positive = heat leaves the named box
    negative = heat enters the named box

Storage change keeps its usual convention (positive = box heat gain).  The
resulting identity is

    -delta_OHC = W_out + E_out + S_out + N_out + surface_loss
                 + unresolved_loss.

The unresolved term is retained for closure but is never assigned to a
physical destination.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/jiang_epcp_two_box_heat_fate"

INPUT = DERIVED / "jiang_epcp_two_box_event_budgets.csv"
DETAIL_CSV = DERIVED / "jiang_epcp_mjj_all_event_box_destinations.csv"
GROUP_CSV = DERIVED / "jiang_epcp_mjj_box_destination_group_summary.csv"
REPORT_MD = OUT / "JIANG_EPCP_MJJ_ALL_EVENT_BOX_DESTINATIONS_CN.md"
FIGURE_PNG = OUT / "jiang_epcp_mjj_all_event_box_destinations.png"

PHASE = "development_MJJ"
BOX_ORDER = ("central", "east")
GROUP_ORDER = ("EP", "CP", "2023")

PATH_COLUMNS = (
    "westward_loss_zj",
    "eastward_loss_zj",
    "southward_loss_zj",
    "northward_loss_zj",
    "surface_loss_zj",
)
ALL_LOSS_COLUMNS = (*PATH_COLUMNS, "unresolved_loss_zj")
PATH_LABELS = {
    "westward_loss_zj": "向西",
    "eastward_loss_zj": "向东",
    "southward_loss_zj": "向南",
    "northward_loss_zj": "向北",
    "surface_loss_zj": "海表",
    "unresolved_loss_zj": "未解析",
}
GROUP_LABELS = {"EP": "历史 EP", "CP": "历史 CP", "2023": "2023 FEP-EP"}
BOX_LABELS = {"central": "中箱", "east": "东箱"}
FIGURE_BOX_LABELS = {"central": "Central box", "east": "Eastern box"}
COLORS = {"EP": "#D95F02", "CP": "#2A9D8F", "2023": "#7B2CBF"}


def build_destination_table() -> pd.DataFrame:
    data = pd.read_csv(INPUT)
    data = data.loc[data.phase.eq(PHASE)].copy()
    expected = 14 * 2
    if len(data) != expected:
        raise ValueError(f"Expected {expected} MJJ box records, found {len(data)}")

    output = data[
        ["event_year", "event_label", "group", "box", "storage_change_zj"]
    ].copy()
    output["storage_loss_zj"] = -data["storage_change_zj"]
    output["westward_loss_zj"] = -data["west_heat_in_zj"]
    output["eastward_loss_zj"] = -data["east_heat_in_zj"]
    output["southward_loss_zj"] = -data["south_heat_in_zj"]
    output["northward_loss_zj"] = -data["north_heat_in_zj"]
    output["surface_loss_zj"] = -data["surface_heat_in_zj"]
    output["unresolved_loss_zj"] = -data[
        "unresolved_storage_contribution_zj"
    ]
    output["closure_error_zj"] = output["storage_loss_zj"] - output[
        list(ALL_LOSS_COLUMNS)
    ].sum(axis=1)

    def dominant_outflow(row: pd.Series) -> tuple[str, float]:
        values = row[list(PATH_COLUMNS)].astype(float)
        positive = values.loc[values.gt(0)]
        if positive.empty:
            return "无净流出项", 0.0
        key = str(positive.idxmax())
        return PATH_LABELS[key], float(positive.max())

    def dominant_inflow(row: pd.Series) -> tuple[str, float]:
        values = row[list(PATH_COLUMNS)].astype(float)
        negative = values.loc[values.lt(0)]
        if negative.empty:
            return "无净流入项", 0.0
        key = str(negative.idxmin())
        return PATH_LABELS[key], float(-negative.min())

    outflow = output.apply(dominant_outflow, axis=1)
    inflow = output.apply(dominant_inflow, axis=1)
    output["dominant_resolved_outflow"] = [item[0] for item in outflow]
    output["dominant_resolved_outflow_zj"] = [item[1] for item in outflow]
    output["dominant_resolved_inflow"] = [item[0] for item in inflow]
    output["dominant_resolved_inflow_zj"] = [item[1] for item in inflow]
    output["unresolved_dominant_flag"] = output.unresolved_loss_zj.abs().gt(
        output[list(PATH_COLUMNS)].abs().max(axis=1)
    )
    return output.sort_values(["event_year", "box"]).reset_index(drop=True)


def build_group_summary(detail: pd.DataFrame) -> pd.DataFrame:
    metrics = ["storage_change_zj", *ALL_LOSS_COLUMNS]
    rows: list[dict[str, object]] = []
    for group in GROUP_ORDER:
        for box in BOX_ORDER:
            subset = detail.loc[detail.group.eq(group) & detail.box.eq(box)]
            row: dict[str, object] = {
                "group": group,
                "box": box,
                "n_events": len(subset),
            }
            for metric in metrics:
                row[f"mean_{metric}"] = float(subset[metric].mean())
            row["n_storage_loss"] = int(subset.storage_change_zj.lt(0).sum())
            row["n_eastward_loss"] = int(subset.eastward_loss_zj.gt(0).sum())
            row["n_westward_loss"] = int(subset.westward_loss_zj.gt(0).sum())
            row["n_surface_loss"] = int(subset.surface_loss_zj.gt(0).sum())
            row["n_unresolved_dominant"] = int(
                subset.unresolved_dominant_flag.sum()
            )
            rows.append(row)
    return pd.DataFrame(rows)


def format_signed(value: float) -> str:
    return f"{value:+.2f}"


def markdown_table(subset: pd.DataFrame) -> list[str]:
    lines = [
        "|事件|类型|ΔOHC|向西流失|向东流失|向南流失|向北流失|海表流失|未解析流失|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in subset.itertuples(index=False):
        lines.append(
            "|"
            + "|".join(
                [
                    str(row.event_label),
                    GROUP_LABELS[str(row.group)],
                    format_signed(float(row.storage_change_zj)),
                    format_signed(float(row.westward_loss_zj)),
                    format_signed(float(row.eastward_loss_zj)),
                    format_signed(float(row.southward_loss_zj)),
                    format_signed(float(row.northward_loss_zj)),
                    format_signed(float(row.surface_loss_zj)),
                    format_signed(float(row.unresolved_loss_zj)),
                ]
            )
            + "|"
        )
    return lines


def route_sentence(row: pd.Series) -> str:
    storage_word = "增储" if row.storage_change_zj >= 0 else "减储"
    residual_word = "未解析流失" if row.unresolved_loss_zj >= 0 else "未解析增储贡献"
    return (
        f"{storage_word} {abs(row.storage_change_zj):.2f} ZJ；"
        f"最大已解析流出为{row.dominant_resolved_outflow} "
        f"{row.dominant_resolved_outflow_zj:.2f} ZJ，"
        f"最大已解析流入/加热为{row.dominant_resolved_inflow} "
        f"{row.dominant_resolved_inflow_zj:.2f} ZJ；"
        f"{residual_word} {abs(row.unresolved_loss_zj):.2f} ZJ"
    )


def write_report(detail: pd.DataFrame, group: pd.DataFrame) -> None:
    lines: list[str] = [
        "# Jiang EP/CP 事件发展期 MJJ：中箱—东箱完整热量去向",
        "",
        "## 口径",
        "",
        "- 中箱：10°S–5°N，180°–140°W，0–300 m；东箱：10°S–5°N，140°W–80°W，0–300 m。",
        "- 时间窗为事件发展年 MJJ；数值是该窗口内积分热量，单位 ZJ。",
        "- ΔOHC 正值表示箱体增储、负值表示减储。其余各列统一为去向口径：正值表示热量从该箱流失，负值表示从该方向流入或由海表加热。",
        "- 闭合式：`−ΔOHC = 向西 + 向东 + 向南 + 向北 + 海表流失 + 未解析流失`。未解析项只用于闭合，不能解释为某个确定物理去向。",
        "- 中箱东边界和东箱西边界由两个箱独立体积校正，方向可以互相验证，但数值不要求完全相等。",
        "",
        "## 总体结论",
        "",
        "- 历史 EP 四个事件全部出现中箱向东输出和东箱从西侧输入；其中三个事件同时出现中箱减储。",
        "- 历史 CP 九个事件中，六个中箱向东输出，五个东箱从西侧输入，只有三个出现中箱减储。因此 EP/CP 改变的是路径出现概率和强度，不是硬性开关。",
        "- 东箱增储十分普遍：除 2019 外，其余十三个事件均增储，所以单看东箱 ΔOHC 不能区分 EP/CP；跨 140°W 的边界输送更有区分度。",
        "- 2023 中箱减储 2.18 ZJ、向东输出 5.39 ZJ；东箱增储 4.39 ZJ、从西侧输入 6.32 ZJ。海表在中箱反而贡献 0.27 ZJ 加热，因此中部偏冷不能归因于海表散热。",
        "",
        "## 分组平均",
        "",
        "|组别|箱体|n|ΔOHC|向西流失|向东流失|向南流失|向北流失|海表流失|未解析流失|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in group.itertuples(index=False):
        lines.append(
            "|"
            + "|".join(
                [
                    GROUP_LABELS[str(row.group)],
                    BOX_LABELS[str(row.box)],
                    str(int(row.n_events)),
                    format_signed(float(row.mean_storage_change_zj)),
                    format_signed(float(row.mean_westward_loss_zj)),
                    format_signed(float(row.mean_eastward_loss_zj)),
                    format_signed(float(row.mean_southward_loss_zj)),
                    format_signed(float(row.mean_northward_loss_zj)),
                    format_signed(float(row.mean_surface_loss_zj)),
                    format_signed(float(row.mean_unresolved_loss_zj)),
                ]
            )
            + "|"
        )

    for box in BOX_ORDER:
        lines.extend(
            [
                "",
                f"## {BOX_LABELS[box]}逐事件完整收支",
                "",
                *markdown_table(detail.loc[detail.box.eq(box)]),
            ]
        )

    lines.extend(["", "## 逐事件物理解读", ""])
    for year in sorted(detail.event_year.unique()):
        subset = detail.loc[detail.event_year.eq(year)].set_index("box")
        group_name = GROUP_LABELS[str(subset.iloc[0].group)]
        label = str(subset.iloc[0].event_label)
        lines.extend(
            [
                f"### {label}（{group_name}）",
                "",
                f"- 中箱：{route_sentence(subset.loc['central'])}。",
                f"- 东箱：{route_sentence(subset.loc['east'])}。",
                "",
            ]
        )

    lines.extend(
        [
            "## 解释边界",
            "",
            "- 本结果是欧拉箱体异常热量收支，回答热量经哪个边界进出，不追踪同一水团身份。",
            "- 较大的未解析项可能包含垂向交换、混合、扩散、同化增量和离散误差。1987 东箱、2002/2004/2015 中箱等事件必须连同该项一起解释。",
            "- 这里比较的是总热量 ZJ；东箱经向宽度大于中箱，因此不要把两箱总量差异直接解释为单位面积异常强弱。",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def make_figure(detail: pd.DataFrame) -> None:
    ordered_years = sorted(detail.event_year.unique())
    plot_columns = ["storage_change_zj", *ALL_LOSS_COLUMNS]
    labels = ["ΔOHC\n(+ gain)", "W loss", "E loss", "S loss", "N loss", "Surface\nloss", "Unresolved\nloss"]
    values = detail[plot_columns].to_numpy(dtype=float)
    limit = float(np.ceil(np.nanmax(np.abs(values))))
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)

    fig, axes = plt.subplots(1, 2, figsize=(17, 10.5), sharey=True)
    image = None
    for axis, box in zip(axes, BOX_ORDER, strict=True):
        subset = detail.loc[detail.box.eq(box)].set_index("event_year").loc[ordered_years]
        matrix = subset[plot_columns].to_numpy(dtype=float)
        image = axis.imshow(matrix, cmap="RdBu_r", norm=norm, aspect="auto")
        axis.set_title(
            f"{FIGURE_BOX_LABELS[box]}  MJJ heat budget",
            fontsize=16,
            weight="bold",
        )
        axis.set_xticks(np.arange(len(labels)), labels=labels, fontsize=10)
        axis.set_yticks(np.arange(len(ordered_years)))
        ylabels = [
            f"{year}  {('FEP-EP' if year == 2023 else subset.loc[year, 'group'])}"
            for year in ordered_years
        ]
        if axis is axes[0]:
            axis.set_yticklabels(ylabels, fontsize=10)
        else:
            axis.tick_params(axis="y", labelleft=False)
        axis.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
        axis.set_yticks(np.arange(-0.5, len(ordered_years), 1), minor=True)
        axis.grid(which="minor", color="white", linewidth=1.2)
        axis.tick_params(which="minor", bottom=False, left=False)

        for row_index, year in enumerate(ordered_years):
            group_name = str(subset.loc[year, "group"])
            if axis is axes[0]:
                axis.get_yticklabels()[row_index].set_color(COLORS[group_name])
                axis.get_yticklabels()[row_index].set_weight(
                    "bold" if year == 2023 else "normal"
                )
            for column_index, value in enumerate(matrix[row_index]):
                color = "white" if abs(value) > 0.55 * limit else "#202020"
                axis.text(
                    column_index,
                    row_index,
                    f"{value:+.1f}",
                    ha="center",
                    va="center",
                    fontsize=8.8,
                    color=color,
                    weight="bold" if year == 2023 else "normal",
                )
        target_index = ordered_years.index(2023)
        axis.add_patch(
            plt.Rectangle(
                (-0.5, target_index - 0.5),
                len(labels),
                1,
                fill=False,
                edgecolor=COLORS["2023"],
                linewidth=2.5,
            )
        )

    axes[0].set_ylabel("Event year and mature type", fontsize=12)
    fig.suptitle(
        "Event-by-event MJJ two-box heat destinations",
        fontsize=21,
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.945,
        "ΔOHC: positive = storage gain; all loss columns: positive = heat leaves the box (ZJ)",
        ha="center",
        fontsize=11,
        color="#444444",
    )
    if image is None:
        raise RuntimeError("No heatmap was created")
    colorbar_axis = fig.add_axes([0.30, 0.055, 0.40, 0.025])
    colorbar = fig.colorbar(image, cax=colorbar_axis, orientation="horizontal")
    colorbar.set_label("Integrated heat / storage change (ZJ)", fontsize=11)
    fig.subplots_adjust(left=0.10, right=0.985, top=0.90, bottom=0.16, wspace=0.10)
    fig.savefig(FIGURE_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)


def validate(detail: pd.DataFrame) -> None:
    if detail.isna().any().any():
        raise ValueError("Destination table contains missing values")
    max_error = float(detail.closure_error_zj.abs().max())
    if max_error > 1.0e-6:
        raise ValueError(f"Budget closure error is too large: {max_error:.3e} ZJ")
    if detail.duplicated(["event_year", "box"]).any():
        raise ValueError("Duplicate event-box records")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    detail = build_destination_table()
    validate(detail)
    group = build_group_summary(detail)
    detail.to_csv(DETAIL_CSV, index=False, float_format="%.10g")
    group.to_csv(GROUP_CSV, index=False, float_format="%.10g")
    write_report(detail, group)
    make_figure(detail)
    print(f"Wrote {DETAIL_CSV}")
    print(f"Wrote {GROUP_CSV}")
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {FIGURE_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
