#!/usr/bin/env python3
"""Decompose the reduced SODA3 warm-heat box residual for three key events."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_soda3_box_decomposition")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr


YEARS = (1997, 2015, 2023)
INTERIM = ROOT / "data/interim/research_2026/soda3_5day_box_budget_terms"
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_warm_heat_budget_decomposition"
PDF_DIR = ROOT / "output/pdf"
BUDGET_CSV = DERIVED / "soda3_warm_heat_160e_180e_budget.csv"
OUTPUT_CSV = DERIVED / "soda3_warm_heat_budget_decomposition_1997_2015_2023.csv"
SUMMARY_CSV = DERIVED / "soda3_warm_heat_budget_decomposition_event_summary.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_warm_heat_budget_decomposition_diagnostics.json"
FIGURE_PNG = OUT / "soda3_warm_heat_budget_decomposition.png"
FIGURE_PDF = PDF_DIR / "soda3_warm_heat_budget_decomposition.pdf"
REPORT_MD = OUT / "SODA3_WARM_HEAT_BUDGET_DECOMPOSITION_CN.md"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.5,
            "axes.titlesize": 9.6,
            "axes.labelsize": 8.7,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.0,
            "pdf.fonttype": 42,
        }
    )


def read_terms() -> pd.DataFrame:
    pieces = []
    for year in YEARS:
        path = INTERIM / f"soda3_5day_box_terms_{year}_jan_jun.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        pieces.append(pd.read_csv(path, parse_dates=["time"]))
    terms = pd.concat(pieces, ignore_index=True).sort_values(["year", "time"])
    if terms.duplicated(["year", "time"]).any():
        raise ValueError("Duplicate SODA3 box term records")
    if (terms["surface_valid_area_fraction"] < 0.999).any():
        raise ValueError("Incomplete surface heat-flux area")
    return terms


def build_decomposition() -> pd.DataFrame:
    budget = pd.read_csv(BUDGET_CSV, parse_dates=["time"])
    budget = budget.loc[budget["year"].isin(YEARS)].copy()
    terms = read_terms()
    pieces = []
    for year, event in terms.groupby("year", sort=True):
        event = event.sort_values("time").copy()
        event["meridional_convergence_midpoint_pw"] = 0.5 * (
            event["q20_meridional_convergence_pw"]
            + event["q20_meridional_convergence_pw"].shift(-1)
        )
        event["surface_heating_midpoint_pw"] = 0.5 * (
            event["surface_net_heating_pw"]
            + event["surface_net_heating_pw"].shift(-1)
        )
        pieces.append(event)
    terms = pd.concat(pieces, ignore_index=True)
    output = budget.merge(
        terms,
        on=["time", "year"],
        how="inner",
        validate="one_to_one",
    )
    expected = sum(budget.loc[budget["year"].eq(year), "time"].nunique() for year in YEARS)
    if len(output) != expected:
        raise ValueError(f"Budget/term time mismatch: {len(output)} != {expected}")
    output["explicit_non_zonal_pw"] = (
        output["meridional_convergence_midpoint_pw"]
        + output["surface_heating_midpoint_pw"]
    )
    output["remaining_unresolved_pw"] = (
        output["budget_residual_future5_pw"] - output["explicit_non_zonal_pw"]
    )
    output["reconstructed_storage_tendency_pw"] = (
        output["zonal_q20_convergence_midpoint_pw"]
        + output["meridional_convergence_midpoint_pw"]
        + output["surface_heating_midpoint_pw"]
        + output["remaining_unresolved_pw"]
    )
    error = (
        output["reconstructed_storage_tendency_pw"]
        - output["box_h20_tendency_future5_pw"]
    )
    if float(np.nanmax(np.abs(error))) > 1.0e-10:
        raise ValueError("Algebraic budget reconstruction failed")
    return output


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, event in frame.groupby("year", sort=True):
        data = event.dropna(
            subset=[
                "budget_residual_future5_pw",
                "explicit_non_zonal_pw",
                "remaining_unresolved_pw",
            ]
        )
        original_mse = float(np.mean(data["budget_residual_future5_pw"] ** 2))
        remaining_mse = float(np.mean(data["remaining_unresolved_pw"] ** 2))
        rows.append(
            {
                "year": int(year),
                "n_intervals": len(data),
                "mean_storage_tendency_pw": float(data["box_h20_tendency_future5_pw"].mean()),
                "mean_zonal_convergence_pw": float(data["zonal_q20_convergence_midpoint_pw"].mean()),
                "mean_meridional_convergence_pw": float(data["meridional_convergence_midpoint_pw"].mean()),
                "mean_surface_heating_pw": float(data["surface_heating_midpoint_pw"].mean()),
                "mean_remaining_unresolved_pw": float(data["remaining_unresolved_pw"].mean()),
                "original_residual_rms_pw": float(np.sqrt(original_mse)),
                "remaining_unresolved_rms_pw": float(np.sqrt(remaining_mse)),
                "mse_fraction_removed": 1.0 - remaining_mse / original_mse,
                "residual_explicit_correlation": float(
                    pearsonr(
                        data["budget_residual_future5_pw"],
                        data["explicit_non_zonal_pw"],
                    ).statistic
                ),
            }
        )
    return pd.DataFrame(rows)


def plot_result(frame: pd.DataFrame, summary: pd.DataFrame) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.4, 8.0))
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.11, top=0.91, wspace=0.27, hspace=0.32)
    colors = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}

    ax = axes[0, 0]
    clean = frame.dropna(subset=["budget_residual_future5_pw", "explicit_non_zonal_pw"])
    limit = float(
        np.nanpercentile(
            np.abs(clean[["budget_residual_future5_pw", "explicit_non_zonal_pw"]].to_numpy()),
            99,
        )
    )
    for year in YEARS:
        event = clean.loc[clean["year"].eq(year)]
        ax.scatter(
            event["explicit_non_zonal_pw"],
            event["budget_residual_future5_pw"],
            s=25,
            alpha=0.72,
            color=colors[year],
            edgecolor="white",
            linewidth=0.35,
            label=str(year),
        )
    ax.plot([-limit, limit], [-limit, limit], color="#222222", ls="--", lw=0.9)
    ax.axhline(0, color="#777777", lw=0.5)
    ax.axvline(0, color="#777777", lw=0.5)
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_xlabel("Meridional convergence + surface heating (PW)")
    ax.set_ylabel("Original non-zonal residual (PW)")
    ax.set_title("(a) How much of the residual is explicitly resolved?", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3, loc="upper left")

    ax = axes[0, 1]
    x = np.arange(len(summary))
    width = 0.34
    ax.bar(
        x - width / 2,
        summary["original_residual_rms_pw"],
        width,
        color="#9A9A9A",
        label="Before explicit terms",
    )
    ax.bar(
        x + width / 2,
        summary["remaining_unresolved_rms_pw"],
        width,
        color="#5B8DB8",
        label="After explicit terms",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(summary["year"].astype(str))
    ax.set_ylabel("RMS residual (PW)")
    ax.set_title("(b) Closure improvement is event dependent", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    ax = axes[1, 0]
    components = [
        ("mean_zonal_convergence_pw", "Zonal", "#5470A8"),
        ("mean_meridional_convergence_pw", "Meridional", "#5AAE61"),
        ("mean_surface_heating_pw", "Surface", "#E6AB02"),
        ("mean_remaining_unresolved_pw", "Remaining", "#B66D9B"),
    ]
    positive = np.zeros(len(summary))
    negative = np.zeros(len(summary))
    for column, label, color in components:
        values = summary[column].to_numpy(dtype=float)
        bottom = np.where(values >= 0, positive, negative)
        ax.bar(x, values, bottom=bottom, color=color, label=label)
        positive += np.where(values >= 0, values, 0.0)
        negative += np.where(values < 0, values, 0.0)
    ax.scatter(
        x,
        summary["mean_storage_tendency_pw"],
        color="#111111",
        marker="D",
        s=28,
        zorder=4,
        label="Observed dH20/dt",
    )
    ax.axhline(0, color="#222222", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(summary["year"].astype(str))
    ax.set_ylabel("January-June mean contribution (PW)")
    ax.set_title("(c) Mean storage is a four-term competition", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=2)

    ax = axes[1, 1]
    for year in YEARS:
        event = frame.loc[frame["year"].eq(year)].sort_values("time")
        day = (event["time"] - pd.Timestamp(year=year, month=1, day=1)).dt.days
        ax.plot(
            day,
            event["remaining_unresolved_pw"],
            color=colors[year],
            lw=1.35,
            label=str(year),
        )
    ax.axhline(0, color="#222222", lw=0.8)
    ax.set_xticks([0, 31, 59, 90, 120, 151, 181])
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"])
    ax.set_ylabel("Remaining unresolved term (PW)")
    ax.set_title("(d) Mixing/vertical/discretization term remains pulse-like", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    figure.suptitle(
        "Explicit decomposition of the SODA3 five-day 160°E-180°E warm-heat budget",
        fontsize=12.8,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "Positive surface net_heating is into the ocean. Remaining term includes vertical/diapycnal exchange, mixing and grid/discretization mismatch.",
        ha="center",
        fontsize=7.0,
        color="#555555",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    frame = build_decomposition()
    summary = summarize(frame)
    clean = frame.dropna(subset=["budget_residual_future5_pw", "explicit_non_zonal_pw", "remaining_unresolved_pw"])
    original_mse = float(np.mean(clean["budget_residual_future5_pw"] ** 2))
    remaining_mse = float(np.mean(clean["remaining_unresolved_pw"] ** 2))
    diagnostics = {
        "years": list(YEARS),
        "n_intervals": len(clean),
        "residual_explicit_correlation": float(
            pearsonr(clean["budget_residual_future5_pw"], clean["explicit_non_zonal_pw"]).statistic
        ),
        "original_residual_rms_pw": float(np.sqrt(original_mse)),
        "remaining_unresolved_rms_pw": float(np.sqrt(remaining_mse)),
        "mse_fraction_removed": 1.0 - remaining_mse / original_mse,
        "surface_flux_sign": "positive into ocean, following SODA net_heating convention",
        "remaining_terms": [
            "vertical and diapycnal heat exchange",
            "mixing/diffusion",
            "finite-volume and grid-staggering mismatch",
        ],
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    plot_result(frame, summary)

    table_lines = []
    for row in summary.itertuples():
        table_lines.append(
            f"| {row.year} | {row.mean_zonal_convergence_pw:+.2f} | "
            f"{row.mean_meridional_convergence_pw:+.2f} | "
            f"{row.mean_surface_heating_pw:+.2f} | "
            f"{row.mean_remaining_unresolved_pw:+.2f} | "
            f"{row.mean_storage_tendency_pw:+.2f} |"
        )
    report = rf"""# SODA3暖层箱体收支的显式残差分解

## 收支式

对5°S—5°N、0—300 m、160°E—180°E的20°C以上暖层热含量，使用：

\[
\frac{{dH_{{20}}}}{{dt}}=
C_x+C_y+Q_{{surface}}+R_{{remain}}.
\]

其中 `Cx` 是160°E输入减180°E输出，`Cy` 是5°S输入减5°N输出，表面项使用SODA3 `net_heating`（正值加热海洋）。`Rremain`仍包含垂向/跨等温面交换、混合扩散和网格离散不闭合。

## 结果

- 原非东西向残差与显式的“经向收敛＋表面加热”相关 `{diagnostics['residual_explicit_correlation']:+.2f}`。
- 原残差RMS为 `{diagnostics['original_residual_rms_pw']:.2f} PW`，加入两项后剩余 `{diagnostics['remaining_unresolved_rms_pw']:.2f} PW`；MSE移除比例为 `{100*diagnostics['mse_fraction_removed']:+.1f}%`。
- 因而，显式两项是否真正改善闭合必须按上面的符号判断；负的移除比例表示它们虽然物理存在，但现有五度边界/五日离散还不能把残差可靠归因完。

| 年份 | 东西汇聚 | 经向汇聚 | 表面加热 | 剩余项 | 储热倾向 |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_lines)}

三次事件揭示的是三条不同收支路径：

- **1997**：180°E向东输出显著大于160°E输入，`Cx=-0.66 PW`，西部箱体快速释热；非东西向过程只补回约`+0.40 PW`，所以净储热倾向仍为`-0.26 PW`。这与强烈向东释放的海洋阶段一致。
- **2023**：也存在净向东输出（`Cx=-0.42 PW`），但经向收敛、表面加热及剩余项合计约`+0.35 PW`，几乎把它抵消，最终只剩`-0.07 PW`的弱释热。这正是“暖量能过日界线，但箱体状态接近补偿平衡”的例子。
- **2015**：东西向净项接近零，主要负项反而是经向辐散（`Cy=-0.22 PW`）；因此它不能用1997式的强东西向释放来概括。

## 科学含义

临界条件不再是单一“西部暖水=西风”平衡，而是：

\[
C_x+C_y+Q_{{surface}}+R_{{remain}}=0.
\]

对这个**西部储库箱体**而言，`dH20/dt<0`通常表示释热，其中一部分可能继续向东输送，并不等于厄尔尼诺条件变差。真正需要预测的是：东西向释放能否超过经向补偿、表面加热和垂向/混合回补。只有这些项同时被约束，才可能把临界带收紧成可预测的转折面。
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
