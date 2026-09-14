#!/usr/bin/env python3
"""Test whether the Q5N -> north H20 -> NE925 conclusion depends on timing.

The primary analysis used April--June source months and a one-month lead. This
script scans all available January--July month pairs, 1--6 month leads, and
several ENSO-season integrations.  Calendar-month detrended monthly series are
used throughout, so the scan does not reintroduce the seasonal cycle.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_maryland_h20_ne_timing_mpl")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyze_h20_outflow_ne_feedback import BASELINE, EVENT_YEARS, bh_fdr, setup_style


MONTHLY_INPUT = ROOT / "data/derived/research_2026/h20_outflow_ne_feedback_monthly_1982_2024.csv"
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/h20_outflow_ne_feedback"
PAIR_CSV = DERIVED / "h20_outflow_ne_time_window_sensitivity.csv"
EVENT_CSV = DERIVED / "h20_outflow_ne_event_window_sensitivity.csv"
FIG_PNG = OUT / "h20_outflow_ne_time_window_sensitivity.png"
FIG_PDF = OUT / "h20_outflow_ne_time_window_sensitivity.pdf"
REPORT = OUT / "H20_OUTFLOW_NE_TIME_WINDOW_SENSITIVITY_CN.md"

CONTROLS = ("nino34_raw_c", "sst_type_raw_c", "fep_raw_c")
N_PERMUTATIONS = 10_000
N_BOOTSTRAP = 10_000
RANDOM_SEED = 20260809
MONTH_LABELS = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul"}


def residual(values: np.ndarray, controls: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(values)), controls])
    coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    result = values - design @ coefficients
    scale = float(np.std(result, ddof=max(1, design.shape[1])))
    return result / scale if scale > 0 else result


def relationship(
    frame: pd.DataFrame,
    *,
    family: str,
    source_month: int,
    target_month: int,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...],
    seed: int,
) -> dict[str, float | int | str]:
    required = ["year", x_name, y_name, *controls]
    data = frame.dropna(subset=required).copy()
    control_values = data.loc[:, controls].to_numpy(dtype=float)
    x = residual(data[x_name].to_numpy(dtype=float), control_values)
    y = residual(data[y_name].to_numpy(dtype=float), control_values)
    observed = float(np.corrcoef(x, y)[0, 1])
    rng = np.random.default_rng(seed)
    permutation = np.empty(N_PERMUTATIONS, dtype=float)
    for index in range(N_PERMUTATIONS):
        permutation[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    p_value = float((np.sum(np.abs(permutation) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1))
    bootstrap = np.empty(N_BOOTSTRAP, dtype=float)
    for index in range(N_BOOTSTRAP):
        selected = rng.integers(0, len(x), len(x))
        bootstrap[index] = np.corrcoef(x[selected], y[selected])[0, 1]
    low, high = np.nanpercentile(bootstrap, [2.5, 97.5])
    return {
        "family": family,
        "source_month": source_month,
        "target_month": target_month,
        "lead_months": target_month - source_month,
        "x": x_name,
        "y": y_name,
        "controls": ";".join(controls),
        "n_years": len(data),
        "controlled_r": observed,
        "permutation_p": p_value,
        "bootstrap_ci_low": float(low),
        "bootstrap_ci_high": float(high),
    }


def build_pair_scan(monthly: pd.DataFrame) -> pd.DataFrame:
    monthly = monthly.loc[monthly.year.between(*BASELINE)].copy()
    lookup = monthly.set_index(["year", "month"])
    rows: list[dict[str, float | int | str]] = []
    counter = 0

    # A. One source-month Q5N versus cumulative H20 change through every later month.
    for source_month in range(1, 7):
        for target_month in range(source_month + 1, 8):
            samples = []
            for year in range(BASELINE[0], BASELINE[1] + 1):
                source = lookup.loc[(year, source_month)]
                target = lookup.loc[(year, target_month)]
                samples.append(
                    {
                        "year": year,
                        "q_source": source.q5n_total_anom_pw,
                        "dh_target": target.h20_north_anom_zj - source.h20_north_anom_zj,
                        "h_source": source.h20_north_anom_zj,
                        **{name: target[name] for name in CONTROLS},
                    }
                )
            rows.append(
                relationship(
                    pd.DataFrame(samples),
                    family="q_to_h20_change",
                    source_month=source_month,
                    target_month=target_month,
                    x_name="q_source",
                    y_name="dh_target",
                    controls=(*CONTROLS, "h_source"),
                    seed=RANDOM_SEED + counter,
                )
            )
            counter += 1

    # B. Earlier Q5N versus later Jiang NE925, across every available pair.
    for source_month in range(1, 7):
        for target_month in range(max(5, source_month), 8):
            samples = []
            for year in range(BASELINE[0], BASELINE[1] + 1):
                source = lookup.loc[(year, source_month)]
                target = lookup.loc[(year, target_month)]
                samples.append(
                    {
                        "year": year,
                        "q_source": source.q5n_total_anom_pw,
                        "ne_target": target.ne925_anom_ms,
                        **{name: target[name] for name in CONTROLS},
                    }
                )
            rows.append(
                relationship(
                    pd.DataFrame(samples),
                    family="q_to_ne",
                    source_month=source_month,
                    target_month=target_month,
                    x_name="q_source",
                    y_name="ne_target",
                    controls=CONTROLS,
                    seed=RANDOM_SEED + counter,
                )
            )
            counter += 1

    # C. Earlier north-side H20 versus later Jiang NE925.
    for source_month in range(1, 8):
        for target_month in range(max(5, source_month), 8):
            samples = []
            for year in range(BASELINE[0], BASELINE[1] + 1):
                source = lookup.loc[(year, source_month)]
                target = lookup.loc[(year, target_month)]
                samples.append(
                    {
                        "year": year,
                        "h_source": source.h20_north_anom_gjm2,
                        "ne_target": target.ne925_anom_ms,
                        **{name: target[name] for name in CONTROLS},
                    }
                )
            rows.append(
                relationship(
                    pd.DataFrame(samples),
                    family="h20_to_ne",
                    source_month=source_month,
                    target_month=target_month,
                    x_name="h_source",
                    y_name="ne_target",
                    controls=CONTROLS,
                    seed=RANDOM_SEED + counter,
                )
            )
            counter += 1

    # D. Reverse direction: NE925 at May/June versus same or later Q5N.
    for source_month in (5, 6):
        for target_month in range(source_month, 7):
            samples = []
            for year in range(BASELINE[0], BASELINE[1] + 1):
                source = lookup.loc[(year, source_month)]
                target = lookup.loc[(year, target_month)]
                sample = {
                    "year": year,
                    "ne_source": source.ne925_anom_ms,
                    "q_target": target.q5n_total_anom_pw,
                    **{name: target[name] for name in CONTROLS},
                }
                if target_month > source_month:
                    sample["q_initial"] = source.q5n_total_anom_pw
                samples.append(sample)
            controls = CONTROLS if target_month == source_month else (*CONTROLS, "q_initial")
            rows.append(
                relationship(
                    pd.DataFrame(samples),
                    family="ne_to_q",
                    source_month=source_month,
                    target_month=target_month,
                    x_name="ne_source",
                    y_name="q_target",
                    controls=controls,
                    seed=RANDOM_SEED + counter,
                )
            )
            counter += 1

    result = pd.DataFrame(rows)
    result["family_fdr_q"] = np.nan
    for _, index in result.groupby("family").groups.items():
        result.loc[index, "family_fdr_q"] = bh_fdr(result.loc[index, "permutation_p"].to_numpy(dtype=float))
    result["global_fdr_q"] = bh_fdr(result.permutation_p.to_numpy(dtype=float))
    return result


def integrate_q_zj(frame: pd.DataFrame) -> float:
    days = pd.to_datetime(frame.time).dt.days_in_month.to_numpy(dtype=float)
    return float(np.nansum(frame.q5n_total_anom_pw.to_numpy(dtype=float) * days * 86400.0 * 1.0e-6))


def simple_event_relationship(data: pd.DataFrame, x_name: str, y_name: str, seed: int) -> dict[str, float | int]:
    valid = data.dropna(subset=[x_name, y_name])
    x = valid[x_name].to_numpy(dtype=float)
    y = valid[y_name].to_numpy(dtype=float)
    observed = float(np.corrcoef(x, y)[0, 1])
    rng = np.random.default_rng(seed)
    permutation = np.empty(N_PERMUTATIONS, dtype=float)
    for index in range(N_PERMUTATIONS):
        permutation[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    p_value = float((np.sum(np.abs(permutation) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1))
    return {"n_events": len(valid), "pearson_r": observed, "permutation_p": p_value}


def build_event_scan(monthly: pd.DataFrame) -> pd.DataFrame:
    q_windows = {"JFM": (1, 2, 3), "FMA": (2, 3, 4), "MAM": (3, 4, 5), "AMJ": (4, 5, 6)}
    h_targets = {"Apr-Jan": 4, "May-Jan": 5, "Jun-Jan": 6, "Jul-Jan": 7}
    rows = []
    for q_label, q_months in q_windows.items():
        event_rows = []
        for year in EVENT_YEARS:
            current = monthly.loc[monthly.year.eq(year)]
            item: dict[str, float | int] = {
                "year": year,
                "q_zj": integrate_q_zj(current.loc[current.month.isin(q_months)]),
                "ne_mjj": float(current.loc[current.month.isin([5, 6, 7]), "ne925_anom_ms"].mean()),
            }
            if year <= BASELINE[1]:
                jan = float(current.loc[current.month.eq(1), "h20_north_anom_zj"].iloc[0])
                for target_label, target_month in h_targets.items():
                    target = float(current.loc[current.month.eq(target_month), "h20_north_anom_zj"].iloc[0])
                    item[f"h_{target_label}"] = target - jan
            event_rows.append(item)
        events = pd.DataFrame(event_rows)
        for target_label in h_targets:
            stats = simple_event_relationship(events, "q_zj", f"h_{target_label}", RANDOM_SEED + len(rows) + 1000)
            rows.append({"family": "event_q_to_h20", "source_window": q_label, "target_window": target_label, **stats})
        stats = simple_event_relationship(events, "q_zj", "ne_mjj", RANDOM_SEED + len(rows) + 1000)
        rows.append({"family": "event_q_to_ne", "source_window": q_label, "target_window": "MJJ NE925", **stats})
    result = pd.DataFrame(rows)
    result["family_fdr_q"] = np.nan
    for _, index in result.groupby("family").groups.items():
        result.loc[index, "family_fdr_q"] = bh_fdr(result.loc[index, "permutation_p"].to_numpy(dtype=float))
    return result


def heatmap(axis: plt.Axes, table: pd.DataFrame, family: str, source_months: list[int], target_months: list[int], title: str) -> None:
    current = table.loc[table.family.eq(family)].set_index(["source_month", "target_month"])
    grid = np.full((len(target_months), len(source_months)), np.nan)
    qgrid = np.full_like(grid, np.nan)
    for j, target in enumerate(target_months):
        for i, source in enumerate(source_months):
            if (source, target) in current.index:
                row = current.loc[(source, target)]
                grid[j, i] = row.controlled_r
                qgrid[j, i] = row.family_fdr_q
    image = axis.imshow(grid, cmap="RdBu_r", vmin=-0.7, vmax=0.7, origin="lower", aspect="auto")
    axis.set_xticks(range(len(source_months)), [MONTH_LABELS[item] for item in source_months])
    axis.set_yticks(range(len(target_months)), [MONTH_LABELS[item] for item in target_months])
    axis.set_xlabel("Source month")
    axis.set_ylabel("Target month")
    axis.set_title(title, loc="left", fontweight="bold")
    for j in range(len(target_months)):
        for i in range(len(source_months)):
            if np.isfinite(grid[j, i]):
                marker = "*" if qgrid[j, i] < 0.05 else ""
                color = "white" if abs(grid[j, i]) > 0.42 else "#202020"
                axis.text(i, j, f"{grid[j, i]:+.2f}{marker}", ha="center", va="center", fontsize=7.2, color=color)
    return image


def plot(pair_scan: pd.DataFrame) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.2, 8.1))
    image = heatmap(axes[0, 0], pair_scan, "q_to_h20_change", list(range(1, 7)), list(range(2, 8)), "a  Q5N → later north-box H20 change")
    heatmap(axes[0, 1], pair_scan, "q_to_ne", list(range(1, 7)), [5, 6, 7], "b  Q5N → later Jiang NE925")
    heatmap(axes[1, 0], pair_scan, "h20_to_ne", list(range(1, 8)), [5, 6, 7], "c  North-box H20 → later Jiang NE925")
    heatmap(axes[1, 1], pair_scan, "ne_to_q", [5, 6], [5, 6], "d  Reverse check: Jiang NE925 → Q5N")
    figure.suptitle("Does the outflow–northeasterly result depend on the selected months?", fontsize=12.2, fontweight="bold", y=0.995)
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.20, top=0.92, hspace=0.36, wspace=0.24)
    colorbar_axis = figure.add_axes([0.25, 0.065, 0.50, 0.026])
    colorbar = figure.colorbar(image, cax=colorbar_axis, orientation="horizontal")
    colorbar.set_label("Controlled correlation; * family-FDR q < 0.05")
    OUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIG_PNG, bbox_inches="tight")
    figure.savefig(FIG_PDF, bbox_inches="tight")
    plt.close(figure)


def write_report(pair_scan: pd.DataFrame, event_scan: pd.DataFrame) -> None:
    def best(family: str, positive: bool | None = None) -> pd.Series:
        current = pair_scan.loc[pair_scan.family.eq(family)]
        if positive is True:
            current = current.loc[current.controlled_r.gt(0)]
        elif positive is False:
            current = current.loc[current.controlled_r.lt(0)]
        return current.loc[current.controlled_r.abs().idxmax()]

    qh = best("q_to_h20_change")
    qne = best("q_to_ne")
    hne = best("h20_to_ne")
    reverse = best("ne_to_q")
    event_best = event_scan.loc[event_scan.family.eq("event_q_to_h20")].sort_values("permutation_p").iloc[0]
    lines = [
        "# 5°N暖量流出—东北风关系的时间窗口敏感性",
        "",
        "## 结论",
        "",
        "扫描月份和滞后后，时间选取会改变个别相关系数，但没有恢复“Q5N流出→北侧H20沉积→Jiang东北风”的完整链条。",
        "",
        "## 全年份月对月扫描（1982—2022）",
        "",
        f"- Q5N→H20变化的绝对最大格点为{MONTH_LABELS[int(qh.source_month)]}→{MONTH_LABELS[int(qh.target_month)]}：r={qh.controlled_r:+.2f}，family-FDR q={qh.family_fdr_q:.3f}。",
        f"- Q5N→NE925的绝对最大格点为{MONTH_LABELS[int(qne.source_month)]}→{MONTH_LABELS[int(qne.target_month)]}：r={qne.controlled_r:+.2f}，family-FDR q={qne.family_fdr_q:.3f}。",
        f"- H20→NE925的绝对最大格点为{MONTH_LABELS[int(hne.source_month)]}→{MONTH_LABELS[int(hne.target_month)]}：r={hne.controlled_r:+.2f}，family-FDR q={hne.family_fdr_q:.3f}。",
        f"- 反向NE925→Q5N的绝对最大格点为{MONTH_LABELS[int(reverse.source_month)]}→{MONTH_LABELS[int(reverse.target_month)]}：r={reverse.controlled_r:+.2f}，family-FDR q={reverse.family_fdr_q:.3f}。",
        "",
        "## ENSO事件季节窗口（探索性，样本12—13个）",
        "",
        f"- 最强Q5N累计→H20变化组合为{event_best.source_window}→{event_best.target_window}：r={event_best.pearson_r:+.2f}，p={event_best.permutation_p:.3f}，family-FDR q={event_best.family_fdr_q:.3f}。",
        "- 事件窗口结果用于判断长期累积可能性；样本很小，不能单独建立因果。",
        "",
        "## 判读边界",
        "",
        "- 月度H20接收侧只覆盖1—7月，因此不能检验成熟冬季到次年春季的接收区沉积；那属于第二问的成熟—衰减期放电，不是Jiang发展期东北风。",
        "- Q5N只是接收箱南边界输入，H20变化还包含北边界、东西边界、海表通量、混合和20°C阈值转换。",
        "- 所有月对月序列已经按日历月去趋势；相关控制目标月Niño-3.4、SST型态和FEP SST，Q→H20还控制源月初始H20。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    monthly = pd.read_csv(MONTHLY_INPUT, parse_dates=["time"])
    pair_scan = build_pair_scan(monthly)
    event_scan = build_event_scan(monthly)
    DERIVED.mkdir(parents=True, exist_ok=True)
    pair_scan.to_csv(PAIR_CSV, index=False, float_format="%.9g")
    event_scan.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    plot(pair_scan)
    write_report(pair_scan, event_scan)
    print(PAIR_CSV)
    print(EVENT_CSV)
    print(FIG_PNG)
    print(REPORT)


if __name__ == "__main__":
    main()
