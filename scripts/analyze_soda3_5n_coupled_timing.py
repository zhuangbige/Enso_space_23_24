#!/usr/bin/env python3
"""Resolve Dec-May timing from eastern warm storage to 5N transport components."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_air_sea_coupled_warm_heat_fate as coupling  # noqa: E402

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ATM_EVENT_CSV = coupling.EVENT_MONTHLY_CSV
DECOMP_MONTHLY_CSV = (
    ROOT / "data/derived/research_2026/soda3_5n_current_decomposition_monthly.csv"
)
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_5n_coupled_timing"
PDF_DIR = ROOT / "output/pdf"
SUMMARY_CSV = DERIVED / "soda3_5n_coupled_timing_summary.csv"
FIGURE_PNG = OUT / "soda3_5n_coupled_timing.png"
FIGURE_PDF = PDF_DIR / "soda3_5n_coupled_timing.pdf"
REPORT_MD = OUT / "SODA3_5N_COUPLED_TIMING_CN.md"

RELATIVE_MONTHS = tuple(range(11, 17))
MONTH_LABELS = ("Dec(0)", "Jan(+1)", "Feb", "Mar", "Apr", "May")
BOOTSTRAP = 20_000
SEED = 20260804
METRICS = {
    "east_h20_zj_anom": ("East H20", "ZJ"),
    "oisst_east_sst_anom": ("East SST", "°C"),
    "gpcp_east_precip_anom": ("East precipitation", "mm day$^{-1}$"),
    "tau_west_anom_nm2": ("5°N westward stress", "N m$^{-2}$"),
    "ekman_220_280e_anom_pw": ("Ekman Q20", "PW"),
    "geo_eos80_220_280e_anom_pw": ("Geostrophic Q20", "PW"),
    "total_220_280e_anom_pw": ("Total Q20", "PW"),
}


def load_aligned() -> pd.DataFrame:
    atmosphere = pd.read_csv(ATM_EVENT_CSV, parse_dates=["time"])
    decomposition = pd.read_csv(DECOMP_MONTHLY_CSV, parse_dates=["time"])
    keep = [
        "time",
        "total_220_280e_anom_pw",
        "geo_eos80_220_280e_anom_pw",
        "ekman_220_280e_anom_pw",
    ]
    output = atmosphere.merge(decomposition[keep], on="time", how="inner", validate="many_to_one")
    output = output.loc[output.relative_month.isin(RELATIVE_MONTHS)].copy()
    output["tau_west_anom_nm2"] = -output.tau5n_220_280e_anom_nm2
    counts = output.groupby(["event_class", "event_year"]).relative_month.nunique()
    if len(counts) != 8 or not counts.eq(6).all():
        raise ValueError("Incomplete eight-event Dec-May timing table")
    return output


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    for relative_month in RELATIVE_MONTHS:
        selected = frame.loc[frame.relative_month.eq(relative_month)]
        for metric in METRICS:
            boot = {}
            for group in ("CT", "CP"):
                values = selected.loc[selected.event_class.eq(group), metric].to_numpy(dtype=float)
                draws = rng.integers(0, len(values), size=(BOOTSTRAP, len(values)))
                boot[group] = values[draws].mean(axis=1)
                low, high = np.quantile(boot[group], [0.025, 0.975])
                rows.append(
                    {
                        "relative_month": relative_month,
                        "contrast": group,
                        "metric": metric,
                        "mean": float(values.mean()),
                        "ci_low": float(low),
                        "ci_high": float(high),
                        "ci_excludes_zero": bool(low > 0 or high < 0),
                    }
                )
            difference = boot["CT"] - boot["CP"]
            low, high = np.quantile(difference, [0.025, 0.975])
            rows.append(
                {
                    "relative_month": relative_month,
                    "contrast": "CT_minus_CP",
                    "metric": metric,
                    "mean": float(
                        selected.loc[selected.event_class.eq("CT"), metric].mean()
                        - selected.loc[selected.event_class.eq("CP"), metric].mean()
                    ),
                    "ci_low": float(low),
                    "ci_high": float(high),
                    "ci_excludes_zero": bool(low > 0 or high < 0),
                }
            )
    return pd.DataFrame(rows)


def series(summary: pd.DataFrame, metric: str) -> pd.DataFrame:
    return summary.loc[
        summary.contrast.eq("CT_minus_CP") & summary.metric.eq(metric)
    ].sort_values("relative_month")


def plot(summary: pd.DataFrame) -> None:
    coupling.setup_style()
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 6.8), constrained_layout=True)
    panels = (
        "east_h20_zj_anom",
        "oisst_east_sst_anom",
        "gpcp_east_precip_anom",
        "tau_west_anom_nm2",
        "ekman_220_280e_anom_pw",
        "total_220_280e_anom_pw",
    )
    x = np.arange(6)
    for index, (axis, metric) in enumerate(zip(axes.flat, panels)):
        selected = series(summary, metric)
        mean = selected["mean"].to_numpy()
        low = selected.ci_low.to_numpy()
        high = selected.ci_high.to_numpy()
        axis.axhline(0, color="0.4", lw=0.7)
        axis.fill_between(x, low, high, color="#C23B3B", alpha=0.20)
        axis.plot(
            x,
            mean,
            color="#C23B3B",
            marker="o",
            lw=1.8,
            label="Ekman" if metric == "ekman_220_280e_anom_pw" else None,
        )
        significant = selected.ci_excludes_zero.to_numpy(dtype=bool)
        axis.scatter(x[significant], mean[significant], color="#8B0000", s=24, zorder=3)
        axis.set_xticks(x, MONTH_LABELS, rotation=25)
        axis.set_ylabel(METRICS[metric][1])
        axis.set_title(
            f"{chr(97 + index)}) CT − CP: {METRICS[metric][0]}",
            loc="left",
            fontweight="bold",
        )
        axis.grid(axis="y", color="0.92", lw=0.5)
    geo = series(summary, "geo_eos80_220_280e_anom_pw")
    axis = axes[1, 1]
    axis.plot(x, geo["mean"], color="#6A51A3", marker="s", lw=1.5, label="Geostrophic")
    axis.fill_between(x, geo.ci_low, geo.ci_high, color="#6A51A3", alpha=0.12)
    axis.legend(frameon=False, loc="upper right")
    fig.suptitle(
        "Monthly ordering of the eastern-Pacific air-sea coupling and 5°N warm-heat exit",
        fontsize=12.8,
        fontweight="bold",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(summary: pd.DataFrame) -> None:
    def item(month: int, metric: str) -> pd.Series:
        return summary.loc[
            summary.relative_month.eq(month)
            & summary.contrast.eq("CT_minus_CP")
            & summary.metric.eq(metric)
        ].iloc[0]

    dec_h20 = item(11, "east_h20_zj_anom")
    dec_rain = item(11, "gpcp_east_precip_anom")
    jan_sst = item(12, "oisst_east_sst_anom")
    jan_total = item(12, "total_220_280e_anom_pw")
    feb_tau = item(13, "tau_west_anom_nm2")
    feb_ekman = item(13, "ekman_220_280e_anom_pw")
    mar_ekman = item(14, "ekman_220_280e_anom_pw")
    report = f"""# 东太平洋暖量—大气响应—5°N出口的逐月时序

## 结论

逐月结果支持“上游热状态先出现，动力出口随后建立”的次序，但月资料不能证明月内因果：

1. **Dec(0)：暖量与对流差异先出现。** CT−CP东部H20为 {dec_h20['mean']:+.2f} ZJ，95%区间 [{dec_h20['ci_low']:+.3f}, {dec_h20['ci_high']:+.2f}]，下界仅略高于零；东部降水为 {dec_rain['mean']:+.2f} mm/day，区间 [{dec_rain['ci_low']:+.2f}, {dec_rain['ci_high']:+.2f}]。
2. **Jan(+1)：SST和总出口变得可辨识。** CT−CP东部SST为 {jan_sst['mean']:+.2f} °C，区间 [{jan_sst['ci_low']:+.2f}, {jan_sst['ci_high']:+.2f}]；总Q20为 {jan_total['mean']:+.3f} PW，区间 [{jan_total['ci_low']:+.3f}, {jan_total['ci_high']:+.3f}]。
3. **Feb：风应力与两个动力分量同时可辨识。** CT−CP向西应力为 {feb_tau['mean']:+.4f} N/m²，区间 [{feb_tau['ci_low']:+.4f}, {feb_tau['ci_high']:+.4f}]；Ekman Q20为 {feb_ekman['mean']:+.3f} PW，区间 [{feb_ekman['ci_low']:+.3f}, {feb_ekman['ci_high']:+.3f}]。地转Q20同月也显著为正。
4. **Mar：风驱出口仍在释放暖量。** Ekman差异为 {mar_ekman['mean']:+.3f} PW，区间 [{mar_ekman['ci_low']:+.3f}, {mar_ekman['ci_high']:+.3f}]；总出口仍显著为正。

## 如何写进文章

可以写成：CT事件在成熟期先建立更大的东太平洋暖量和对流异常，随后一至两个月内5°N西向风应力及北向Ekman/总暖量输送变得统计可辨识；CP没有形成同样的东部链条。地转差异在Jan–Feb同时出现，说明压力场调整参与型态差异。这里支持的是月尺度时间顺序和物理一致性，不是耦合模式扰动试验意义上的严格因果。

置信区间以4个CT和4个CP整事件bootstrap计算；深色点表示逐月CT−CP区间不跨零。输入全部是1982–2022日历月线性去趋势、未做三个月平滑的异常。
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> int:
    aligned = load_aligned()
    summary = summarize(aligned)
    DERIVED.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.9g")
    plot(summary)
    write_report(summary)
    for path in (SUMMARY_CSV, FIGURE_PNG, FIGURE_PDF, REPORT_MD):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
