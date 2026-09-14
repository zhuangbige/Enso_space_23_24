#!/usr/bin/env python3
"""Compare monthly 140W Q20 transport rate and its Jan--Jun integral."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


INPUT = (
    ROOT
    / "data/derived/research_2026/"
    / "enso_1997_2015_2023_warm_heat_fate_monthly.csv"
)
OUT = ROOT / "outputs/research_2026/soda3_140w_transport_rate_timing"
FIGURE_PNG = OUT / "soda3_140w_transport_rate_and_cumulative_1997_2015_2023_cn.png"
FIGURE_PDF = OUT / "soda3_140w_transport_rate_and_cumulative_1997_2015_2023_cn.pdf"
SUMMARY_CSV = (
    ROOT
    / "data/derived/research_2026/"
    / "soda3_140w_transport_rate_timing_1997_2015_2023.csv"
)

EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
RATE_COLUMN = "q20_140w_east_pw_anom_b1980_2014"
COLORS = {1997: "#B3212D", 2015: "#2878B5", 2023: "#E07A00"}


def configure_fonts() -> None:
    candidates = (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    )
    family = "DejaVu Sans"
    for path in candidates:
        if path.exists():
            fm.fontManager.addfont(path)
            family = fm.FontProperties(fname=path).get_name()
            break
    plt.rcParams.update(
        {
            "font.family": family,
            "axes.unicode_minus": False,
            "axes.titleweight": "bold",
            "axes.labelcolor": "#102A3C",
            "text.color": "#102A3C",
            "xtick.color": "#35576C",
            "ytick.color": "#35576C",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_and_calculate() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(INPUT, parse_dates=["time"])
    required = {"time", "year", "month", RATE_COLUMN}
    if not required.issubset(raw.columns):
        raise KeyError(f"Missing columns: {sorted(required - set(raw.columns))}")
    monthly = raw.loc[
        raw.year.isin(EVENTS) & raw.month.isin(MONTHS),
        ["time", "year", "month", RATE_COLUMN],
    ].copy()
    monthly = monthly.sort_values(["year", "month"]).reset_index(drop=True)
    if not monthly.groupby("year").size().eq(6).all():
        raise ValueError("Each event must contain six complete Jan--Jun records")
    monthly["days_in_month"] = monthly.time.dt.days_in_month
    monthly["monthly_heat_zj"] = (
        monthly[RATE_COLUMN] * monthly.days_in_month * 86400.0 / 1.0e6
    )
    monthly["cumulative_heat_zj"] = monthly.groupby("year")["monthly_heat_zj"].cumsum()

    rows: list[dict[str, float | int | str]] = []
    for event, group in monthly.groupby("year", sort=True):
        group = group.sort_values("month")
        total_seconds = float((group.days_in_month * 86400.0).sum())
        total_zj = float(group.monthly_heat_zj.sum())
        mean_pw = total_zj * 1.0e6 / total_seconds
        peak_index = group[RATE_COLUMN].idxmax()
        peak = group.loc[peak_index]
        early_zj = float(group.loc[group.month <= 3, "monthly_heat_zj"].sum())
        late_zj = float(group.loc[group.month >= 4, "monthly_heat_zj"].sum())
        half_month = int(
            group.loc[group.cumulative_heat_zj.ge(0.5 * total_zj), "month"].iloc[0]
        )
        rows.append(
            {
                "event_year": int(event),
                "jan_jun_integral_zj": total_zj,
                "jan_jun_mean_rate_pw": mean_pw,
                "peak_monthly_rate_pw": float(peak[RATE_COLUMN]),
                "peak_month": int(peak.month),
                "peak_month_label": MONTH_LABELS[int(peak.month) - 1],
                "peak_to_mean_ratio": float(peak[RATE_COLUMN] / mean_pw),
                "jan_mar_integral_zj": early_zj,
                "apr_jun_integral_zj": late_zj,
                "apr_jun_fraction": late_zj / total_zj,
                "month_reaching_half_total": half_month,
                "june_integral_zj": float(
                    group.loc[group.month.eq(6), "monthly_heat_zj"].iloc[0]
                ),
                "june_fraction": float(
                    group.loc[group.month.eq(6), "monthly_heat_zj"].iloc[0] / total_zj
                ),
            }
        )
    summary = pd.DataFrame(rows)
    return monthly, summary


def style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#D8E2E8", linewidth=0.85, zorder=0)
    axis.tick_params(labelsize=11)


def make_figure(monthly: pd.DataFrame, summary: pd.DataFrame) -> None:
    configure_fonts()
    fig, axes = plt.subplots(2, 1, figsize=(10.8, 8.2), sharex=True, constrained_layout=True)
    ax = axes[0]
    for event in EVENTS:
        group = monthly.loc[monthly.year.eq(event)].sort_values("month")
        ax.plot(
            group.month,
            group[RATE_COLUMN],
            color=COLORS[event],
            linewidth=2.8,
            marker="o",
            markersize=6.5,
            label=str(event),
            zorder=3,
        )
        peak = group.loc[group[RATE_COLUMN].idxmax()]
        ax.annotate(
            f"{peak[RATE_COLUMN]:.2f} PW",
            xy=(peak.month, peak[RATE_COLUMN]),
            xytext=(0, 11),
            textcoords="offset points",
            ha="center",
            fontsize=9.5,
            fontweight="bold",
            color=COLORS[event],
        )
    ax.axhline(0.0, color="#102A3C", linewidth=1.0)
    ax.set_ylabel("跨140°W东向暖量输送速率（PW）", fontsize=12)
    ax.set_title("a  相同总量可以来自完全不同的输送速率和时序", loc="left", fontsize=14)
    ax.legend(frameon=False, ncol=3, fontsize=10.5, loc="upper left")
    style_axis(ax)

    ax = axes[1]
    for event in EVENTS:
        group = monthly.loc[monthly.year.eq(event)].sort_values("month")
        ax.plot(
            group.month,
            group.cumulative_heat_zj,
            color=COLORS[event],
            linewidth=2.8,
            marker="o",
            markersize=6.5,
            label=str(event),
            zorder=3,
        )
        final = group.iloc[-1]
        ax.text(
            final.month + 0.08,
            final.cumulative_heat_zj,
            f"{final.cumulative_heat_zj:.2f} ZJ",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=COLORS[event],
        )
    ax.axhline(0.0, color="#102A3C", linewidth=1.0)
    ax.set_ylabel("Jan—Jun累计输入（ZJ）", fontsize=12)
    ax.set_xlabel("发展年月份", fontsize=12)
    ax.set_title("b  柱状图中的数值是速率按实际月秒数积分后的终值", loc="left", fontsize=14)
    ax.set_xticks(MONTHS, MONTH_LABELS)
    ax.set_xlim(0.8, 6.65)
    style_axis(ax)

    mean_text = []
    for event in EVENTS:
        row = summary.loc[summary.event_year.eq(event)].iloc[0]
        mean_text.append(
            f"{event}: 平均 {row.jan_jun_mean_rate_pw:.2f} PW；"
            f"峰值 {row.peak_monthly_rate_pw:.2f} PW（{row.peak_month_label}）；"
            f"Apr–Jun占 {row.apr_jun_fraction:.0%}"
        )
    fig.suptitle(
        "暖量到达量相近，不代表输送速率与到达时序相同",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.5,
        -0.025,
        "\n".join(mean_text),
        ha="center",
        va="top",
        fontsize=10.2,
        linespacing=1.45,
        color="#35576C",
    )
    fig.savefig(FIGURE_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def validate(monthly: pd.DataFrame, summary: pd.DataFrame) -> None:
    if monthly[[RATE_COLUMN, "monthly_heat_zj", "cumulative_heat_zj"]].isna().any().any():
        raise ValueError("Missing transport values")
    expected = {1997: 12.1267562, 2015: 3.29874319, 2023: 3.91408523}
    actual = summary.set_index("event_year").jan_jun_integral_zj
    for event, target in expected.items():
        if not np.isclose(actual.loc[event], target, atol=5.0e-7):
            raise ValueError(f"Integrated value mismatch for {event}: {actual.loc[event]}")
    if not FIGURE_PNG.exists() or not FIGURE_PDF.exists():
        raise FileNotFoundError("Transport-rate figure was not written")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    monthly, summary = load_and_calculate()
    make_figure(monthly, summary)
    validate(monthly, summary)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(SUMMARY_CSV)
    print(FIGURE_PNG)
    print(FIGURE_PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
