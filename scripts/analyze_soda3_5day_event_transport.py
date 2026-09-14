#!/usr/bin/env python3
"""Analyze SODA3 5-day warm-water transport pulses for four ENSO events.

The 5-day event-only records cannot define an independent climatology.
Therefore each within-month 5-day departure is anchored to the corresponding
1980-2024 detrended monthly anomaly from the full SODA3 analysis:

    anchored_5day = raw_5day - event_month_mean(raw_5day)
                    + full_record_monthly_anomaly

This preserves high-frequency pulses while retaining the common long-record
monthly reference.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


EVENT_YEARS = (1997, 2004, 2015, 2023)
EVENT_LABELS = {
    1997: "1997 EP",
    2004: "2004 CP",
    2015: "2015 EP",
    2023: "2023 EP-like",
}
GATE_LONGITUDES = np.arange(150.0, 241.0, 5.0)
INPUT_DIR = (
    ROOT / "data/interim/research_2026/soda3_5day_event_transport"
)
MONTHLY_TRANSPORT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_warm_transport_longitude_1980_2024.csv"
)
MONTHLY_INDEX_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_transition_process_indices_1980_2024.csv"
)

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_5day_transport"
OUT_PDF = ROOT / "output/pdf"
ANCHORED_CSV = OUT_DATA / "soda3_5day_event_transport_anchored.csv"
PULSE_CSV = OUT_DATA / "soda3_5day_event_transport_pulse_summary.csv"
LAG_CSV = OUT_DATA / "soda3_5day_wind_transport_lag_correlations.csv"
DIAGNOSTICS_JSON = OUT_DATA / "soda3_5day_event_transport_diagnostics.json"
FIGURE_PNG = OUT_DIR / "soda3_5day_warm_water_transport_pulses.png"
FIGURE_PDF = OUT_PDF / "soda3_5day_warm_water_transport_pulses.pdf"
SUMMARY_MD = OUT_DIR / "SODA3_5DAY_TRANSPORT_RESULTS_CN.md"

EARTH_RADIUS = 6_371_000.0
LAT_BOUNDS = (-5.0, 5.0)
CENTRAL_LON_BOUNDS = (180.0, 220.0)
LAGS = np.arange(-4, 5)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.8,
            "axes.titlesize": 9.8,
            "axes.labelsize": 8.9,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 7.4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pieces = []
    for year in EVENT_YEARS:
        path = INPUT_DIR / f"soda3_5day_transport_{year}_jan_jun.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        current = pd.read_csv(path, parse_dates=["time"])
        expected_times = 37 if year == 2004 else 36
        if current["time"].nunique() != expected_times:
            raise ValueError(
                f"{year}: expected {expected_times} times, "
                f"found {current['time'].nunique()}"
            )
        pieces.append(current)
    five_day = pd.concat(pieces, ignore_index=True).sort_values(
        ["time", "longitude_e"]
    )
    monthly_transport = pd.read_csv(
        MONTHLY_TRANSPORT_CSV,
        parse_dates=["time"],
    )
    monthly_indices = pd.read_csv(
        MONTHLY_INDEX_CSV,
        parse_dates=["time"],
    )
    return five_day, monthly_transport, monthly_indices


def anchor_to_monthly_baseline(
    five_day: pd.DataFrame,
    monthly_transport: pd.DataFrame,
    monthly_indices: pd.DataFrame,
) -> pd.DataFrame:
    frame = five_day.copy()
    for raw, monthly_anomaly, destination in (
        ("q20_pw", "q20_pw_anom", "q20_pw_anchored_anom"),
        (
            "warm_volume_transport_sv",
            "warm_volume_transport_sv_anom",
            "warm_volume_transport_sv_anchored_anom",
        ),
        (
            "warm_heat_section_gj_per_m",
            "warm_heat_section_gj_per_m_anom",
            "warm_heat_section_gj_per_m_anchored_anom",
        ),
    ):
        within_month_mean = frame.groupby(
            ["year", "month", "longitude_e"]
        )[raw].transform("mean")
        frame[f"{raw}_within_month_departure"] = (
            frame[raw] - within_month_mean
        )
        reference = monthly_transport[
            ["year", "month", "longitude_e", monthly_anomaly]
        ].rename(columns={monthly_anomaly: "_monthly_reference"})
        frame = frame.merge(
            reference,
            on=["year", "month", "longitude_e"],
            how="left",
            validate="many_to_one",
        )
        frame[destination] = (
            frame[f"{raw}_within_month_departure"]
            + frame["_monthly_reference"]
        )
        frame = frame.drop(columns="_monthly_reference")

    stress = (
        frame[
            ["time", "year", "month", "taux_central_nm2"]
        ]
        .drop_duplicates("time")
        .sort_values("time")
    )
    stress["taux_within_month_departure"] = (
        stress["taux_central_nm2"]
        - stress.groupby(["year", "month"])["taux_central_nm2"].transform(
            "mean"
        )
    )
    reference = monthly_indices[
        ["year", "month", "taux_central_nm2_anom"]
    ].rename(columns={"taux_central_nm2_anom": "_stress_reference"})
    stress = stress.merge(
        reference,
        on=["year", "month"],
        how="left",
        validate="many_to_one",
    )
    stress["taux_central_nm2_anchored_anom"] = (
        stress["taux_within_month_departure"]
        + stress["_stress_reference"]
    )
    frame = frame.drop(columns="taux_central_nm2").merge(
        stress[
            [
                "time",
                "taux_central_nm2",
                "taux_central_nm2_anchored_anom",
            ]
        ],
        on="time",
        how="left",
        validate="many_to_one",
    )
    return frame.sort_values(["time", "longitude_e"])


def central_area_m2() -> float:
    south, north = np.deg2rad(LAT_BOUNDS)
    west, east = np.deg2rad(CENTRAL_LON_BOUNDS)
    return EARTH_RADIUS**2 * (np.sin(north) - np.sin(south)) * (
        east - west
    )


def wide_timeseries(anchored: pd.DataFrame) -> pd.DataFrame:
    q = anchored.pivot(
        index="time",
        columns="longitude_e",
        values="q20_pw_anchored_anom",
    )
    output = (
        anchored[
            [
                "time",
                "year",
                "month",
                "day",
                "taux_central_nm2_anchored_anom",
            ]
        ]
        .drop_duplicates("time")
        .set_index("time")
        .sort_index()
    )
    for longitude in (180.0, 200.0, 220.0):
        output[f"q20_{int(longitude)}e_pw_anom"] = q[longitude]
    output["central_zonal_divergence_wm2_anom"] = (
        (q[220.0] - q[180.0]) * 1.0e15 / central_area_m2()
    )
    return output.reset_index()


def summarize_pulses(
    anchored: pd.DataFrame,
    wide: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for year in EVENT_YEARS:
        current = wide.loc[wide["year"].eq(year)].sort_values("time")
        dates = pd.DatetimeIndex(current["time"])
        if len(dates) < 2:
            continue
        median_days = float(
            np.median(np.diff(dates.values).astype("timedelta64[D]").astype(int))
        )
        row: dict[str, float | int | str] = {
            "event_year": year,
            "event_label": EVENT_LABELS[year],
            "n_5day_times": len(current),
            "median_interval_days": median_days,
        }
        for longitude in (180, 200, 220):
            column = f"q20_{longitude}e_pw_anom"
            peak_index = current[column].idxmax()
            row[f"q20_{longitude}e_peak_pw"] = current.loc[
                peak_index,
                column,
            ]
            row[f"q20_{longitude}e_peak_date"] = current.loc[
                peak_index,
                "time",
            ].strftime("%Y-%m-%d")
            row[f"q20_{longitude}e_positive_pw_days"] = float(
                np.sum(np.maximum(current[column], 0.0)) * median_days
            )
        stress_index = current["taux_central_nm2_anchored_anom"].idxmax()
        row["taux_peak_nm2"] = current.loc[
            stress_index,
            "taux_central_nm2_anchored_anom",
        ]
        row["taux_peak_date"] = current.loc[
            stress_index,
            "time",
        ].strftime("%Y-%m-%d")
        divergence_index = current[
            "central_zonal_divergence_wm2_anom"
        ].idxmax()
        row["central_divergence_peak_wm2"] = current.loc[
            divergence_index,
            "central_zonal_divergence_wm2_anom",
        ]
        row["central_divergence_peak_date"] = current.loc[
            divergence_index,
            "time",
        ].strftime("%Y-%m-%d")
        row["q220_to_q180_positive_transport_ratio"] = (
            row["q20_220e_positive_pw_days"]
            / row["q20_180e_positive_pw_days"]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def lag_correlations(wide: pd.DataFrame) -> pd.DataFrame:
    """Positive lag means wind stress leads heat transport."""
    rows = []
    for year in EVENT_YEARS:
        current = wide.loc[wide["year"].eq(year)].sort_values("time")
        wind = current["taux_central_nm2_anchored_anom"]
        for longitude in (180, 200, 220):
            transport = current[f"q20_{longitude}e_pw_anom"]
            for lag in LAGS:
                correlation = wind.corr(transport.shift(-lag))
                rows.append(
                    {
                        "event_year": year,
                        "longitude_e": longitude,
                        "lag_steps_wind_leads": int(lag),
                        "lag_days_wind_leads": int(lag * 5),
                        "correlation": correlation,
                    }
                )
    return pd.DataFrame(rows)


def plot_pulses(
    anchored: pd.DataFrame,
    wide: pd.DataFrame,
    pulses: pd.DataFrame,
) -> None:
    setup_style()
    figure, axes = plt.subplots(
        3,
        4,
        figsize=(13.0, 8.0),
        sharex="col",
    )
    figure.subplots_adjust(
        left=0.07,
        right=0.98,
        bottom=0.16,
        top=0.89,
        wspace=0.16,
        hspace=0.22,
    )

    q_color_limit = float(
        np.nanpercentile(
            np.abs(anchored["q20_pw_anchored_anom"]),
            98,
        )
    )
    q_line_limit = float(
        np.nanmax(
            np.abs(
                wide[
                    [
                        "q20_180e_pw_anom",
                        "q20_200e_pw_anom",
                        "q20_220e_pw_anom",
                    ]
                ].to_numpy(dtype=float)
            )
        )
        * 1.05
    )
    stress_limit = float(
        np.nanmax(np.abs(wide["taux_central_nm2_anchored_anom"])) * 1.05
    )
    q_color_limit = max(q_color_limit, 0.1)
    q_line_limit = max(q_line_limit, 0.1)
    stress_limit = max(stress_limit, 0.005)
    longitude_edges = np.r_[
        GATE_LONGITUDES - 2.5,
        GATE_LONGITUDES[-1] + 2.5,
    ]
    image = None
    line_colors = {
        180: "#5B4B9A",
        200: "#D17A22",
        220: "#B52D2D",
    }

    for column, year in enumerate(EVENT_YEARS):
        current = wide.loc[wide["year"].eq(year)].sort_values("time")
        dates = pd.DatetimeIndex(current["time"])
        axes[0, column].plot(
            dates,
            current["taux_central_nm2_anchored_anom"],
            color="#21618C",
            lw=1.4,
            marker="o",
            ms=2.7,
        )
        axes[0, column].fill_between(
            dates,
            0.0,
            current["taux_central_nm2_anchored_anom"],
            where=current["taux_central_nm2_anchored_anom"] > 0.0,
            color="#79A9C8",
            alpha=0.40,
        )
        axes[0, column].axhline(0.0, color="#666666", lw=0.7)
        axes[0, column].set_ylim(-stress_limit, stress_limit)
        axes[0, column].set_title(
            f"({chr(97 + column)}) {EVENT_LABELS[year]}",
            loc="left",
            fontweight="bold",
        )
        if column == 0:
            axes[0, column].set_ylabel(
                "Central-Pacific\nzonal stress anomaly\n(N m⁻²)"
            )

        for longitude in (180, 200, 220):
            axes[1, column].plot(
                dates,
                current[f"q20_{longitude}e_pw_anom"],
                color=line_colors[longitude],
                lw=1.25,
                label=(
                    "180°"
                    if longitude == 180
                    else f"{360 - longitude:.0f}°W"
                ),
            )
        axes[1, column].axhline(0.0, color="#666666", lw=0.7)
        axes[1, column].set_ylim(-q_line_limit, q_line_limit)
        if column == 0:
            axes[1, column].set_ylabel(
                ">20°C eastward\nheat transport\n(PW anomaly)"
            )
            axes[1, column].legend(
                frameon=False,
                ncol=3,
                loc="upper left",
            )

        event_transport = anchored.loc[anchored["year"].eq(year)]
        matrix = event_transport.pivot(
            index="time",
            columns="longitude_e",
            values="q20_pw_anchored_anom",
        ).reindex(columns=GATE_LONGITUDES)
        time_values = mdates.date2num(pd.DatetimeIndex(matrix.index))
        time_edges = np.r_[
            time_values[0] - 2.5,
            0.5 * (time_values[:-1] + time_values[1:]),
            time_values[-1] + 2.5,
        ]
        image = axes[2, column].pcolormesh(
            time_edges,
            longitude_edges,
            matrix.to_numpy(dtype=float).T,
            cmap="RdBu_r",
            norm=TwoSlopeNorm(
                vmin=-q_color_limit,
                vcenter=0.0,
                vmax=q_color_limit,
            ),
            shading="flat",
        )
        axes[2, column].axhline(
            180.0,
            color="white",
            lw=1.0,
            ls="--",
        )
        axes[2, column].set_yticks([150, 180, 210, 240])
        axes[2, column].set_yticklabels(
            ["150°E", "180°", "150°W", "120°W"]
        )
        axes[2, column].xaxis.set_major_locator(
            mdates.MonthLocator(interval=1)
        )
        axes[2, column].xaxis.set_major_formatter(
            mdates.DateFormatter("%b")
        )
        for row in range(3):
            axes[row, column].set_xlim(
                pd.Timestamp(year, 1, 1),
                pd.Timestamp(year, 6, 30),
            )
        axes[2, column].set_xlabel("Developing year")
        if column == 0:
            axes[2, column].set_ylabel("Longitude")
        for row in range(3):
            axes[row, column].grid(
                axis="x",
                color="#DDDDDD",
                lw=0.5,
            )

    figure.suptitle(
        "SODA3 5-day pulses: from westerly stress to eastward warm-water transport",
        fontsize=13.8,
        fontweight="bold",
        y=0.965,
    )
    colorbar_axis = figure.add_axes([0.25, 0.075, 0.50, 0.025])
    colorbar = figure.colorbar(
        image,
        cax=colorbar_axis,
        orientation="horizontal",
        extend="both",
    )
    colorbar.set_label("20°C-relative zonal heat-transport anomaly (PW)")
    figure.text(
        0.5,
        0.010,
        "5-day departures are anchored to the detrended 1980–2024 "
        "calendar-month anomaly; dashed line marks the dateline.",
        ha="center",
        fontsize=7.6,
        color="#4C4C4C",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def write_summary(
    pulses: pd.DataFrame,
    lags: pd.DataFrame,
) -> None:
    event_lines = []
    lag_lines = []
    for row in pulses.itertuples():
        event_lines.append(
            f"- {int(row.event_year)}：最大200°E输送"
            f"{row.q20_200e_peak_pw:+.2f} PW（{row.q20_200e_peak_date}）；"
            f"最大140°W输送{row.q20_220e_peak_pw:+.2f} PW"
            f"（{row.q20_220e_peak_date}）；"
            f"1–6月200°E正异常积分"
            f"{row.q20_200e_positive_pw_days:.1f} PW day；"
            f"140°W/日界线正输送比"
            f"{row.q220_to_q180_positive_transport_ratio:.2f}。"
        )
        current_200 = lags.loc[
            lags["event_year"].eq(row.event_year)
            & lags["longitude_e"].eq(200)
        ].sort_values("correlation", ascending=False)
        current_220 = lags.loc[
            lags["event_year"].eq(row.event_year)
            & lags["longitude_e"].eq(220)
        ].sort_values("correlation", ascending=False)
        best_200 = current_200.iloc[0]
        best_220 = current_220.iloc[0]
        lag_lines.append(
            f"- {int(row.event_year)}：风应力相对200°E/140°W输送的"
            f"最佳领先分别为"
            f"{int(best_200['lag_days_wind_leads']):+d}/"
            f"{int(best_220['lag_days_wind_leads']):+d}天，"
            f"r={best_200['correlation']:+.2f}/"
            f"{best_220['correlation']:+.2f}。"
        )

    text = f"""# SODA3 5日暖水输送脉冲分析

## 方法

SODA3官方5日文件只提取0–300 m、5°S–5°N、150°E–120°W的温度、纬向
流速和风应力。由于这里只下载4个事件，不能用它们自身定义气候态。
因此每个5日值先减去该事件该月的5日均值，再加回1980–2024完整月资料
的同月去趋势异常。

## 代表事件的输送峰值

{chr(10).join(event_lines)}

EP/EP-like事件的140°W/日界线正输送比分别为1.20、1.61和1.03，
而2004 CP为0.70。这个比值不是严格的守恒“效率”，因为中间还存在
经向输送和局地动力调整；但它清楚地区分了“暖水越过日界线”与
“暖水继续穿过140°W进入东部”。

## 风—海洋时差

正领先表示中太平洋西风应力先发生、暖水输送后响应：

{chr(10).join(lag_lines)}

四个事件样本不足以对领先相关做显著性推断；它的用途是定位过程窗口，
不是建立新的统计定律。是否由Kelvin波传播造成，还应结合D20/SSH的
5日经度—时间传播速度验证。

## 解释边界

- 5日资料能够区分“整月持续输送”和“少数强脉冲造成的月平均”。
- `u*max(T-20°C,0)`是20°C相对热输送，不等于完整盆地热收支。
- 绝对输送积分同时受事件强度影响，因此EP/CP比较还应看
  140°W/日界线输送比，而不能只比较PW day的大小。
- 只有四个事件，因此事件类型的总体统计仍以13事件月资料和ORAS5
  独立验证为主。

## 文件

- 高频派生序列：`{ANCHORED_CSV}`
- 峰值表：`{PULSE_CSV}`
- 领先相关：`{LAG_CSV}`
- 图：`{FIGURE_PDF}`
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(text, encoding="utf-8")


def validate(
    anchored: pd.DataFrame,
    pulses: pd.DataFrame,
) -> None:
    if anchored.duplicated(["time", "longitude_e"]).any():
        raise ValueError("Duplicate 5-day time-longitude rows")
    if set(anchored["year"].unique()) != set(EVENT_YEARS):
        raise ValueError("Unexpected event years")
    if len(pulses) != len(EVENT_YEARS):
        raise ValueError("Pulse summary does not contain all events")
    for year in EVENT_YEARS:
        current = anchored.loc[anchored["year"].eq(year)]
        if set(current["longitude_e"].unique()) != set(GATE_LONGITUDES):
            raise ValueError(f"{year}: incomplete longitude gates")
        monthly = current.groupby(["month", "longitude_e"])[
            "q20_pw_anchored_anom"
        ].mean()
        if not np.isfinite(monthly).all():
            raise ValueError(f"{year}: non-finite anchored monthly transport")


def main() -> int:
    five_day, monthly_transport, monthly_indices = read_inputs()
    anchored = anchor_to_monthly_baseline(
        five_day,
        monthly_transport,
        monthly_indices,
    )
    wide = wide_timeseries(anchored)
    pulses = summarize_pulses(anchored, wide)
    lags = lag_correlations(wide)
    validate(anchored, pulses)

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    anchored.to_csv(ANCHORED_CSV, index=False)
    pulses.to_csv(PULSE_CSV, index=False)
    lags.to_csv(LAG_CSV, index=False)
    plot_pulses(anchored, wide, pulses)
    write_summary(pulses, lags)

    diagnostics = {
        "dataset": "SODA3.15.2 official 5-day regridded ocean files",
        "event_years": list(EVENT_YEARS),
        "domain": "5S-5N, 150E-120W, 0-300 m",
        "anchor": (
            "Within-event-month 5-day departure plus the corresponding "
            "1980-2024 detrended monthly anomaly"
        ),
        "n_rows": len(anchored),
        "outputs": {
            "anchored_csv": str(ANCHORED_CSV),
            "pulse_csv": str(PULSE_CSV),
            "lag_csv": str(LAG_CSV),
            "figure_pdf": str(FIGURE_PDF),
            "summary_md": str(SUMMARY_MD),
        },
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {ANCHORED_CSV}", flush=True)
    print(f"Wrote {PULSE_CSV}", flush=True)
    print(f"Wrote {FIGURE_PDF}", flush=True)
    print(f"Wrote {SUMMARY_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
