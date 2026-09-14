#!/usr/bin/env python3
"""Diagnose five-day SODA3 OHC and wind-stress coupling in three events."""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_soda3_5day_ohc_plot_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT
    / "data/interim/research_2026/soda3_5day_ohc/"
    "soda3_5day_ohc_1997_2002_2023_jan_jun.csv"
)
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_ohc_minimal"

SUMMARY_CSV = DERIVED / "soda3_5day_ohc_coupling_event_summary.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_5day_ohc_coupling_diagnostics.json"
FIG_PNG = OUT / "soda3_5day_ohc_coupling_1997_2002_2023.png"
FIG_PDF = OUT / "soda3_5day_ohc_coupling_1997_2002_2023.pdf"
REPORT_MD = OUT / "SODA3_5DAY_OHC_COUPLING_RESULT_CN.md"

EVENT_YEARS = (1997, 2002, 2023)
EVENT_COLORS = {1997: "#b2182b", 2002: "#d99a20", 2023: "#2166ac"}


def load_data() -> pd.DataFrame:
    frame = pd.read_csv(INPUT, parse_dates=["time"])
    required = {
        "time",
        "year",
        "month",
        "ohc300_central_anom_gj_m2",
        "ohc300_central_anom_15day_gj_m2",
        "taux_central_180_220e_nm2",
        "taux_central_15day_nm2",
        "valid_column_fraction",
    }
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"Missing input columns: {sorted(missing)}")
    if set(frame["year"].unique()) != set(EVENT_YEARS):
        raise ValueError("Unexpected event years in five-day product")
    counts = frame.groupby("year")["time"].nunique()
    if not counts.eq(36).all():
        raise ValueError(f"Expected 36 pentads per event, found {counts.to_dict()}")
    if frame[list(required - {"time"})].isna().any().any():
        raise ValueError("Missing values in five-day OHC-coupling product")
    if not frame["valid_column_fraction"].between(0.99, 1.0).all():
        raise ValueError("Unexpected missing water columns")
    return frame.sort_values(["year", "time"]).reset_index(drop=True)


def first_two_pentad_westerly(group: pd.DataFrame) -> pd.Timestamp | None:
    values = group["taux_central_180_220e_nm2"].to_numpy(dtype=float)
    for index in range(len(values) - 1):
        if values[index] > 0.0 and values[index + 1] > 0.0:
            return pd.Timestamp(group.iloc[index]["time"])
    return None


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in frame.groupby("year", sort=True):
        spring = group.loc[group["month"].isin([3, 4])]
        may_june = group.loc[group["month"].isin([5, 6])]
        ohc_peak = spring.loc[
            spring["ohc300_central_anom_15day_gj_m2"].idxmax()
        ]
        stress_peak = may_june.loc[
            may_june["taux_central_15day_nm2"].idxmax()
        ]
        first_westerly = first_two_pentad_westerly(group)
        rows.append(
            {
                "year": int(year),
                "spring_ohc_peak_date": ohc_peak["time"].date().isoformat(),
                "spring_ohc_peak_gj_m2": float(
                    ohc_peak["ohc300_central_anom_15day_gj_m2"]
                ),
                "may_jun_stress_max_date": stress_peak["time"].date().isoformat(),
                "may_jun_stress_max_nm2": float(stress_peak["taux_central_15day_nm2"]),
                "days_stress_max_after_ohc_peak": int(
                    (stress_peak["time"] - ohc_peak["time"]).days
                ),
                "first_two_pentad_westerly_date": (
                    None if first_westerly is None else first_westerly.date().isoformat()
                ),
                "actual_westerly_stress_established": first_westerly is not None,
                "jan_jun_ohc_max_gj_m2": float(
                    group["ohc300_central_anom_15day_gj_m2"].max()
                ),
                "jan_jun_stress_max_nm2": float(group["taux_central_15day_nm2"].max()),
            }
        )
    return pd.DataFrame(rows)


def make_figure(frame: pd.DataFrame, summary: pd.DataFrame) -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.3,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 300,
        }
    )
    fig, axes = plt.subplots(3, 1, figsize=(10.8, 8.2), sharex=False)
    fig.subplots_adjust(left=0.10, right=0.89, top=0.89, bottom=0.12, hspace=0.24)

    for row_index, (axis, year) in enumerate(zip(axes, EVENT_YEARS, strict=True)):
        group = frame.loc[frame["year"].eq(year)].copy()
        wind_axis = axis.twinx()
        summary_row = summary.loc[summary["year"].eq(year)].iloc[0]

        axis.plot(
            group["time"],
            group["ohc300_central_anom_gj_m2"],
            color="#b2182b",
            alpha=0.28,
            lw=0.9,
        )
        axis.plot(
            group["time"],
            group["ohc300_central_anom_15day_gj_m2"],
            color="#b2182b",
            lw=2.0,
            label="0-300 m OHC anomaly (15-day mean)",
        )
        wind_axis.plot(
            group["time"],
            group["taux_central_180_220e_nm2"],
            color="#2166ac",
            alpha=0.25,
            lw=0.9,
        )
        wind_axis.plot(
            group["time"],
            group["taux_central_15day_nm2"],
            color="#2166ac",
            lw=1.8,
            ls="--",
            label="zonal wind stress (15-day mean)",
        )
        axis.axhline(0.0, color="#b2182b", lw=0.6, alpha=0.5)
        wind_axis.axhline(0.0, color="#2166ac", lw=0.8, alpha=0.8)
        axis.axvspan(
            pd.Timestamp(year, 3, 1),
            pd.Timestamp(year, 4, 30),
            color="#eee4ca",
            alpha=0.55,
            zorder=-3,
        )

        ohc_date = pd.Timestamp(summary_row["spring_ohc_peak_date"])
        stress_date = pd.Timestamp(summary_row["may_jun_stress_max_date"])
        axis.scatter(
            [ohc_date],
            [summary_row["spring_ohc_peak_gj_m2"]],
            marker="v",
            s=55,
            color="#b2182b",
            edgecolor="white",
            linewidth=0.6,
            zorder=5,
        )
        wind_axis.scatter(
            [stress_date],
            [summary_row["may_jun_stress_max_nm2"]],
            marker="^",
            s=55,
            color="#2166ac",
            edgecolor="white",
            linewidth=0.6,
            zorder=5,
        )

        axis.set_ylim(-0.25, 2.20)
        wind_axis.set_ylim(-0.115, 0.030)
        axis.set_title(f"({chr(97 + row_index)}) {year}", loc="left", fontweight="bold")
        axis.grid(axis="x", color="0.90", lw=0.7)
        axis.xaxis.set_major_locator(mdates.MonthLocator())
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        axis.set_xlim(pd.Timestamp(year, 1, 1), pd.Timestamp(year, 6, 30))
        axis.tick_params(axis="y", colors="#b2182b")
        wind_axis.tick_params(axis="y", colors="#2166ac")
        westerly_text = (
            "none by Jun"
            if pd.isna(summary_row["first_two_pentad_westerly_date"])
            else pd.Timestamp(summary_row["first_two_pentad_westerly_date"]).strftime("%d %b")
        )
        axis.text(
            0.015,
            0.90,
            (
                f"spring OHC peak {summary_row['spring_ohc_peak_gj_m2']:+.2f} GJ m$^{{-2}}$ "
                f"({ohc_date:%d %b}); actual westerly stress: {westerly_text}"
            ),
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=8.1,
            color=EVENT_COLORS[year],
        )
        if row_index == 1:
            axis.set_ylabel("0-300 m OHC anomaly (GJ m$^{-2}$)", color="#b2182b")
            wind_axis.set_ylabel("SODA3 zonal wind stress (N m$^{-2}$)", color="#2166ac")
        if row_index < 2:
            axis.tick_params(axis="x", labelbottom=False)
        else:
            axis.set_xlabel("Development-year date")

    handles_left, labels_left = axes[0].get_legend_handles_labels()
    wind_handle = mpl.lines.Line2D([], [], color="#2166ac", ls="--", lw=1.8)
    fig.legend(
        [handles_left[0], wind_handle],
        [labels_left[0], "zonal wind stress (15-day mean)"],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.925),
        ncol=2,
        frameon=False,
    )
    fig.suptitle(
        "SODA3 five-day test: central-Pacific subsurface heat and surface-stress coupling",
        fontsize=13.5,
        fontweight="bold",
        y=0.975,
    )
    fig.text(
        0.5,
        0.018,
        (
            "SODA3.15.2, 5S-5N, 180-140W. Thin: five-day values; thick: 15-day means. "
            "Positive stress is actual westerly stress.\n"
            "Five-day OHC anomalies are aligned to the 1980-2024 detrended monthly baseline."
        ),
        ha="center",
        va="bottom",
        fontsize=7.5,
        color="0.35",
    )
    fig.savefig(FIG_PNG, dpi=300)
    fig.savefig(FIG_PDF)
    plt.close(fig)


def write_report(summary: pd.DataFrame) -> None:
    rows = []
    for _, row in summary.iterrows():
        westerly = (
            "未出现"
            if pd.isna(row["first_two_pentad_westerly_date"])
            else row["first_two_pentad_westerly_date"]
        )
        rows.append(
            "| {year} | {date} | {ohc:+.2f} | {stress_date} | {stress:+.3f} | {westerly} |".format(
                year=int(row["year"]),
                date=row["spring_ohc_peak_date"],
                ohc=row["spring_ohc_peak_gj_m2"],
                stress_date=row["may_jun_stress_max_date"],
                stress=row["may_jun_stress_max_nm2"],
                westerly=westerly,
            )
        )
    report = f"""# SODA3五日热含量—海气耦合初步结果

## 设定

- SODA3.15.2五日温度场；5°S–5°N、180°–140°W、0—300米OHC。
- 同一SODA3文件中的纬向表面风应力；正值表示实际西风应力。
- 仅分析1997、2002和2023年1—6月，不增加其他候选变量。
- OHC五日距平对齐到1980—2024年月气候态及同月去趋势基线；每月五日平均严格等于原月平均OHC距平。

## 结果

| 事件 | 3—4月OHC峰值日期 | OHC峰值（GJ m⁻²） | 5—6月风应力最大日期 | 最大风应力（N m⁻²） | 连续两个候实际西风 |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

1997年在3月底至4月初形成约+2.00 GJ m⁻²的中太平洋次表层热量峰，约两个月后风应力在6月初短暂转为实际西风。2002年春季OHC峰值只有+0.38 GJ m⁻²；2023年虽在4月下旬达到+0.65 GJ m⁻²，但两年截至6月底都没有形成连续两个候的实际西风应力。

## 阶段判断

五日资料把月平均结论进一步细化为：**3月底—4月的中太平洋热量幅度，是随后能否发生强风应力松弛的候选海洋检查点；真正的实际西风建立可晚约1—2个月。**

但这仍不是一个已证明的普适阈值。三例中可以看出“1997高而持续、2002和2023不足”，不能仅凭三例宣布+1 GJ m⁻²为临界值。SODA3风应力来自其大气强迫，因此后续若需要独立验证，应只使用TAO日资料核对时间，而不改变当前SODA3主分析。
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    frame = load_data()
    summary = summarize(frame)
    summary.to_csv(SUMMARY_CSV, index=False)
    diagnostics = {
        "data_source": "SODA3.15.2 five-day reanalysis",
        "domain": "5S-5N, 180-140W, 0-300 m",
        "n_pentads_per_event": 36,
        "event_summary": summary.to_dict(orient="records"),
        "interpretation_limit": (
            "Three cases locate a late-March/April ocean checkpoint but cannot establish "
            "a universal numerical OHC threshold. SODA3 wind stress is a forcing field, "
            "not an independent atmospheric observation."
        ),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_figure(frame, summary)
    write_report(summary)
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {DIAGNOSTICS_JSON}")
    print(f"Wrote {FIG_PNG}")
    print(f"Wrote {FIG_PDF}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
