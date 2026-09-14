#!/usr/bin/env python3
"""Compare 5-day central-Pacific wind stress with 140W Q20 transport.

Both fields are anchored to the same 1980--2023 detrended calendar-month
baseline.  Monthly Q20 anomalies retain exact month-length integration for the
reported Jan--Jun ZJ totals; 5-day departures resolve intramonth pulses.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MONTHLY_Q = (
    ROOT
    / "data/derived/research_2026/"
    / "enso_1997_2015_2023_warm_heat_fate_monthly.csv"
)
MONTHLY_WIND = (
    ROOT
    / "data/derived/research_2026/"
    / "soda3_transition_process_indices_1980_2024.csv"
)
FIVE_DAY = (
    ROOT
    / "data/derived/research_2026/"
    / "soda3_5day_event_transport_anchored.csv"
)
OUT = ROOT / "outputs/research_2026/soda3_wind_transport_comparison"
FIGURE_PNG = OUT / "soda3_wind_vs_140w_transport_5day_1997_2015_2023_cn.png"
FIGURE_PDF = OUT / "soda3_wind_vs_140w_transport_5day_1997_2015_2023_cn.pdf"
ALIGNED_CSV = (
    ROOT
    / "data/derived/research_2026/"
    / "soda3_wind_140w_transport_5day_aligned_b1980_2023.csv"
)
SUMMARY_CSV = (
    ROOT
    / "data/derived/research_2026/"
    / "soda3_wind_140w_transport_summary_b1980_2023.csv"
)

EVENTS = (1997, 2015, 2023)
BASELINE = (1980, 2023)
Q_RAW = "q20_140w_east_raw_pw"
WIND_RAW = "taux_central_nm2"
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


def same_month_detrended(values: np.ndarray, times: pd.DatetimeIndex) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    result = np.full(data.shape, np.nan, dtype=float)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    for month in range(1, 7):
        target = months == month
        baseline = (
            target
            & (years >= BASELINE[0])
            & (years <= BASELINE[1])
            & np.isfinite(data)
        )
        if baseline.sum() < 30:
            raise ValueError(f"Insufficient baseline records for month {month}")
        center_year = float(np.mean(years[baseline]))
        x = years[baseline] - center_year
        climatology = float(np.mean(data[baseline]))
        slope = float(np.sum(x * (data[baseline] - climatology)) / np.sum(x**2))
        result[target] = data[target] - climatology - slope * (years[target] - center_year)
    return result


def monthly_references() -> pd.DataFrame:
    q = pd.read_csv(MONTHLY_Q, parse_dates=["time"])
    wind = pd.read_csv(MONTHLY_WIND, parse_dates=["time"])
    q["q20_140w_anom_pw_b1980_2023"] = same_month_detrended(
        q[Q_RAW].to_numpy(dtype=float), pd.DatetimeIndex(q.time)
    )
    wind["taux_central_anom_nm2_b1980_2023"] = same_month_detrended(
        wind[WIND_RAW].to_numpy(dtype=float), pd.DatetimeIndex(wind.time)
    )
    reference = q[
        ["time", "year", "month", "q20_140w_anom_pw_b1980_2023"]
    ].merge(
        wind[["time", "taux_central_anom_nm2_b1980_2023"]],
        on="time",
        how="inner",
        validate="one_to_one",
    )
    return reference


def build_aligned() -> tuple[pd.DataFrame, pd.DataFrame]:
    reference = monthly_references()
    five = pd.read_csv(FIVE_DAY, parse_dates=["time"])
    five = five.loc[
        five.year.isin(EVENTS) & five.longitude_e.eq(220.0),
        ["time", "year", "month", "q20_pw", "taux_central_nm2"],
    ].copy()
    five = five.sort_values(["year", "time"])
    five["q20_within_month_departure_pw"] = (
        five.q20_pw - five.groupby(["year", "month"]).q20_pw.transform("mean")
    )
    five["taux_within_month_departure_nm2"] = (
        five.taux_central_nm2
        - five.groupby(["year", "month"]).taux_central_nm2.transform("mean")
    )
    aligned = five.merge(
        reference.drop(columns="time"),
        on=["year", "month"],
        how="left",
        validate="many_to_one",
    )
    aligned["q20_140w_5day_anchored_anom_pw"] = (
        aligned.q20_within_month_departure_pw
        + aligned.q20_140w_anom_pw_b1980_2023
    )
    aligned["taux_central_5day_anchored_anom_nm2"] = (
        aligned.taux_within_month_departure_nm2
        + aligned.taux_central_anom_nm2_b1980_2023
    )

    rows: list[dict[str, float | int | str]] = []
    for event in EVENTS:
        current = aligned.loc[aligned.year.eq(event)].sort_values("time")
        monthly = reference.loc[reference.year.eq(event)].sort_values("month")
        seconds = monthly.time.dt.days_in_month.to_numpy(dtype=float) * 86400.0
        cumulative = np.cumsum(
            monthly.q20_140w_anom_pw_b1980_2023.to_numpy(dtype=float)
            * seconds
            / 1.0e6
        )
        wind_peak = current.loc[
            current.taux_central_5day_anchored_anom_nm2.idxmax()
        ]
        q_peak = current.loc[current.q20_140w_5day_anchored_anom_pw.idxmax()]
        best_lag_days = 0
        best_correlation = -np.inf
        for lag_steps in range(-4, 5):
            correlation = current.taux_central_5day_anchored_anom_nm2.corr(
                current.q20_140w_5day_anchored_anom_pw.shift(-lag_steps)
            )
            if np.isfinite(correlation) and correlation > best_correlation:
                best_lag_days = lag_steps * 5
                best_correlation = float(correlation)
        rows.append(
            {
                "event_year": event,
                "jan_jun_q20_integral_zj_b1980_2023": float(cumulative[-1]),
                "jan_jun_q20_mean_pw_b1980_2023": float(
                    cumulative[-1] * 1.0e6 / seconds.sum()
                ),
                "jan_jun_taux_day_weighted_mean_nm2_b1980_2023": float(
                    np.average(
                        monthly.taux_central_anom_nm2_b1980_2023,
                        weights=seconds,
                    )
                ),
                "peak_5day_westerly_nm2": float(
                    wind_peak.taux_central_5day_anchored_anom_nm2
                ),
                "peak_5day_westerly_date": str(wind_peak.time.date()),
                "peak_5day_q20_pw": float(q_peak.q20_140w_5day_anchored_anom_pw),
                "peak_5day_q20_date": str(q_peak.time.date()),
                "zero_lag_correlation": float(
                    current.taux_central_5day_anchored_anom_nm2.corr(
                        current.q20_140w_5day_anchored_anom_pw
                    )
                ),
                "best_lag_days_wind_leads": best_lag_days,
                "best_lag_correlation": best_correlation,
            }
        )
    return aligned, pd.DataFrame(rows)


def style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#D8E2E8", linewidth=0.75, zorder=0)
    axis.axhline(0.0, color="#102A3C", linewidth=0.9, zorder=1)
    axis.tick_params(labelsize=9.5)


def make_figure(aligned: pd.DataFrame, summary: pd.DataFrame) -> None:
    configure_fonts()
    fig, axes = plt.subplots(
        2,
        3,
        figsize=(14.0, 7.0),
        sharey="row",
        constrained_layout=True,
    )
    for column, event in enumerate(EVENTS):
        current = aligned.loc[aligned.year.eq(event)].sort_values("time")
        color = COLORS[event]

        ax = axes[0, column]
        wind = current.taux_central_5day_anchored_anom_nm2.to_numpy(dtype=float)
        ax.plot(current.time, wind, color=color, linewidth=2.0, marker="o", markersize=3.4)
        ax.fill_between(current.time, 0.0, wind, where=wind > 0.0, color=color, alpha=0.20)
        ax.fill_between(current.time, 0.0, wind, where=wind < 0.0, color="#6E9FB7", alpha=0.16)
        peak = current.loc[current.taux_central_5day_anchored_anom_nm2.idxmax()]
        ax.annotate(
            f"最大西风 {peak.taux_central_5day_anchored_anom_nm2:.3f}",
            xy=(peak.time, peak.taux_central_5day_anchored_anom_nm2),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
            fontweight="bold",
            color=color,
        )
        ax.set_ylim(-0.06, 0.07)
        ax.set_title(str(event), fontsize=15, color=color)
        if column == 0:
            ax.set_ylabel(
                "中央太平洋纬向风应力异常\n" + r"(N m$^{-2}$；正值为西风)",
                fontsize=11,
            )
        style_axis(ax)

        ax = axes[1, column]
        transport = current.q20_140w_5day_anchored_anom_pw.to_numpy(dtype=float)
        ax.plot(current.time, transport, color=color, linewidth=2.2, marker="o", markersize=3.4)
        ax.fill_between(current.time, 0.0, transport, where=transport > 0.0, color=color, alpha=0.16)
        peak = current.loc[current.q20_140w_5day_anchored_anom_pw.idxmax()]
        ax.annotate(
            f"峰值 {peak.q20_140w_5day_anchored_anom_pw:.2f} PW",
            xy=(peak.time, peak.q20_140w_5day_anchored_anom_pw),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
            fontweight="bold",
            color=color,
        )
        total = summary.loc[summary.event_year.eq(event)].iloc[0]
        ax.text(
            0.03,
            0.91,
            f"Jan–Jun累计 {total.jan_jun_q20_integral_zj_b1980_2023:.2f} ZJ",
            transform=ax.transAxes,
            fontsize=9.2,
            fontweight="bold",
            color="#102A3C",
            va="top",
        )
        ax.set_ylim(-0.55, 1.72)
        if column == 0:
            ax.set_ylabel("140°W东向暖量输送异常\n(PW)", fontsize=11)
        ax.set_xlabel("发展年", fontsize=10.5)
        style_axis(ax)

        for target in (axes[0, column], axes[1, column]):
            target.set_xlim(pd.Timestamp(f"{event}-01-01"), pd.Timestamp(f"{event}-07-01"))
            target.xaxis.set_major_locator(mdates.MonthLocator())
            target.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    fig.suptitle(
        "中央太平洋风脉冲与跨140°W暖量输送：5日尺度对比",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.5,
        -0.015,
        "区域：5°S–5°N、180°–140°W；全部异常统一使用1980–2023同月去趋势气候态",
        ha="center",
        fontsize=10.2,
        color="#35576C",
    )
    fig.savefig(FIGURE_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def validate(aligned: pd.DataFrame, summary: pd.DataFrame) -> None:
    expected_rows = 36 * len(EVENTS)
    if len(aligned) != expected_rows:
        raise ValueError(f"Expected {expected_rows} 5-day rows, found {len(aligned)}")
    columns = [
        "q20_140w_5day_anchored_anom_pw",
        "taux_central_5day_anchored_anom_nm2",
    ]
    if aligned[columns].isna().any().any():
        raise ValueError("Missing aligned wind/transport values")
    expected_totals = {1997: 12.4318023464, 2015: 4.7633055923, 2023: 5.8939882285}
    totals = summary.set_index("event_year").jan_jun_q20_integral_zj_b1980_2023
    for event, target in expected_totals.items():
        if not np.isclose(totals.loc[event], target, atol=1.0e-8):
            raise ValueError(f"Unexpected integrated total for {event}: {totals.loc[event]}")
    if not FIGURE_PNG.exists() or not FIGURE_PDF.exists():
        raise FileNotFoundError("Wind-transport figure was not written")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    aligned, summary = build_aligned()
    make_figure(aligned, summary)
    validate(aligned, summary)
    aligned.to_csv(ALIGNED_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    print(ALIGNED_CSV)
    print(SUMMARY_CSV)
    print(FIGURE_PNG)
    print(FIGURE_PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
