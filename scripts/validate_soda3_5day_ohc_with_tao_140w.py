#!/usr/bin/env python3
"""Validate SODA3 five-day upper-ocean heat timing with TAO at 0N, 140W.

TAO is a single equatorial mooring, whereas the SODA3 index is averaged over
5S-5N, 180-140W.  The comparison therefore tests sign, event ranking, and
timing rather than equality of amplitude.  A TAO 0-300 m heat-content value is
only formed when the observed profile reaches 300 m; long vertical gaps are
not filled and the incomplete 2023 profile is reported as missing.
"""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_maryland_tao_ohc_cache")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TAO_TEMPERATURE = (
    ROOT / "data/raw/tao_0n140w/tao_0n140w_daily_temperature.csv"
)
SODA_FIVE_DAY = (
    ROOT
    / "data/interim/research_2026/soda3_5day_ohc/"
    "soda3_5day_ohc_13events_1982_2023_jan_jun.csv"
)
SODA_EVENT_SUMMARY = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_5day_ohc_transition_event_summary.csv"
)

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/tao_soda3_ohc_timing_validation"
PDF_DIR = ROOT / "output/pdf"

TAO_DAILY = DERIVED / "tao_0n140w_ohc300_daily_anomalies.csv"
ALIGNED = DERIVED / "tao_soda3_ohc_timing_aligned_1997_2015_2023.csv"
SUMMARY = DERIVED / "tao_soda3_ohc_timing_summary_1997_2015_2023.csv"
PNG = OUT / "tao_soda3_ohc_timing_validation.png"
PDF = PDF_DIR / "tao_soda3_ohc_timing_validation.pdf"
REPORT = OUT / "TAO_SODA3_OHC_TIMING_VALIDATION_CN.md"

EVENTS = (1997, 2015, 2023)
RHO = 1025.0
CP = 3990.0
BASELINE_START = 1983
BASELINE_END = 2024
MIN_PROFILE_LEVELS = 6
MIN_MONTHLY_PROFILE_DAYS = 10
MIN_ROLLING_DAYS = 10


def read_tao_temperature() -> pd.DataFrame:
    frame = pd.read_csv(TAO_TEMPERATURE, skiprows=[1])
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame["date"] = frame["time"].dt.tz_localize(None).dt.floor("D")
    return frame.loc[
        frame["T_20"].notna()
        & frame["QT_5020"].between(1, 3)
        & frame["depth"].between(0.0, 300.0)
    ].copy()


def daily_ohc300(temperature: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date, group in temperature.groupby("date"):
        profile = (
            group.groupby("depth", as_index=False)["T_20"]
            .mean()
            .sort_values("depth")
        )
        minimum_depth = float(profile["depth"].min())
        maximum_depth = float(profile["depth"].max())
        if (
            len(profile) < MIN_PROFILE_LEVELS
            or minimum_depth > 10.0
            or maximum_depth < 300.0
        ):
            continue
        depth = profile["depth"].to_numpy(dtype=float)
        temp = profile["T_20"].to_numpy(dtype=float)
        if depth[0] > 0.0:
            depth = np.r_[0.0, depth]
            temp = np.r_[temp[0], temp]
        heat = RHO * CP * np.trapz(temp, depth)
        rows.append(
            {
                "date": date,
                "ohc300_j_m2": heat,
                "n_valid_levels": len(profile),
                "minimum_depth_m": minimum_depth,
                "maximum_depth_m": maximum_depth,
            }
        )
    result = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    result["year"] = result["date"].dt.year
    result["month"] = result["date"].dt.month
    return result


def add_detrended_monthly_anomaly(ohc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = (
        ohc.groupby(["year", "month"])
        .agg(
            monthly_ohc300_j_m2=("ohc300_j_m2", "mean"),
            complete_profile_days=("date", "nunique"),
        )
        .reset_index()
    )
    baseline = monthly.loc[
        monthly["year"].between(BASELINE_START, BASELINE_END)
        & monthly["complete_profile_days"].ge(MIN_MONTHLY_PROFILE_DAYS)
    ]
    parameters: dict[int, tuple[float, float, int]] = {}
    for month, group in baseline.groupby("month"):
        if group["year"].nunique() < 12:
            continue
        slope, intercept = np.polyfit(
            group["year"].to_numpy(dtype=float) - 2003.5,
            group["monthly_ohc300_j_m2"].to_numpy(dtype=float),
            1,
        )
        parameters[int(month)] = (
            float(slope),
            float(intercept),
            int(group["year"].nunique()),
        )

    result = ohc.copy()
    expected = []
    baseline_years = []
    for year, month in zip(result["year"], result["month"]):
        values = parameters.get(int(month))
        if values is None:
            expected.append(np.nan)
            baseline_years.append(0)
        else:
            slope, intercept, n_years = values
            expected.append(slope * (float(year) - 2003.5) + intercept)
            baseline_years.append(n_years)
    result["detrended_monthly_expected_j_m2"] = expected
    result["baseline_years_for_calendar_month"] = baseline_years
    result["ohc300_anom_gj_m2"] = (
        result["ohc300_j_m2"]
        - result["detrended_monthly_expected_j_m2"]
    ) / 1.0e9
    return result, monthly


def event_aligned(tao: pd.DataFrame, soda: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in EVENTS:
        index = pd.date_range(f"{year}-01-01", f"{year}-06-30", freq="D")
        tao_event = (
            tao.loc[tao["year"].eq(year), ["date", "ohc300_anom_gj_m2"]]
            .drop_duplicates("date")
            .set_index("date")["ohc300_anom_gj_m2"]
            .reindex(index)
        )
        tao_smooth = tao_event.rolling(
            15, center=True, min_periods=MIN_ROLLING_DAYS
        ).mean()
        tao_count = tao_event.notna().astype(float).rolling(
            15, center=True, min_periods=1
        ).sum()

        soda_event = soda.loc[soda["year"].eq(year)].copy()
        soda_event = soda_event.set_index("time").sort_index()
        soda_ohc = (
            soda_event["ohc300_central_anom_15day_gj_m2"]
            .reindex(index)
            .interpolate(method="time", limit_area="inside")
        )
        soda_stress = (
            soda_event["taux_central_15day_nm2"]
            .reindex(index)
            .interpolate(method="time", limit_area="inside")
        )
        event = pd.DataFrame(
            {
                "date": index,
                "year": year,
                "tao_ohc300_anom_daily_gj_m2": tao_event.to_numpy(),
                "tao_ohc300_anom_15day_gj_m2": tao_smooth.to_numpy(),
                "tao_complete_profiles_in_15day_window": tao_count.to_numpy(),
                "soda3_ohc300_anom_15day_gj_m2": soda_ohc.to_numpy(),
                "soda3_taux_15day_nm2": soda_stress.to_numpy(),
            }
        )
        rows.append(event)
    return pd.concat(rows, ignore_index=True)


def summarize_events(
    aligned: pd.DataFrame,
    event_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for year in EVENTS:
        event = aligned.loc[aligned["year"].eq(year)].copy()
        spring = event.loc[event["date"].dt.month.isin([3, 4])]
        tao_spring = spring.dropna(
            subset=["tao_ohc300_anom_15day_gj_m2"]
        )
        soda_spring = spring.dropna(
            subset=["soda3_ohc300_anom_15day_gj_m2"]
        )
        common = spring.dropna(
            subset=[
                "tao_ohc300_anom_15day_gj_m2",
                "soda3_ohc300_anom_15day_gj_m2",
            ]
        )
        soda_row = event_summary.loc[event_summary["year"].eq(year)].iloc[0]
        row: dict[str, object] = {
            "year": year,
            "tao_complete_profile_days_jan_jun": int(
                event["tao_ohc300_anom_daily_gj_m2"].notna().sum()
            ),
            "tao_15day_values_mar_apr": int(len(tao_spring)),
            "soda3_spring_peak_date": soda_spring.loc[
                soda_spring["soda3_ohc300_anom_15day_gj_m2"].idxmax(),
                "date",
            ].date(),
            "soda3_spring_peak_gj_m2": float(
                soda_spring["soda3_ohc300_anom_15day_gj_m2"].max()
            ),
            "may_jun_stress_max_date": soda_row["may_jun_stress_max_date"],
            "may_jun_stress_max_nm2": float(soda_row["may_jun_stress_max_nm2"]),
            "actual_westerly_established": bool(
                soda_row["actual_westerly_stress_established_may_jun"]
            ),
        }
        if tao_spring.empty:
            row.update(
                {
                    "tao_spring_peak_date": pd.NA,
                    "tao_spring_peak_gj_m2": np.nan,
                    "tao_peak_minus_soda3_days": np.nan,
                    "mar_apr_daily_shape_r": np.nan,
                    "common_days_for_shape_r": 0,
                    "tao_status": "unavailable: profile did not reach 300 m",
                }
            )
        else:
            tao_peak = tao_spring.loc[
                tao_spring["tao_ohc300_anom_15day_gj_m2"].idxmax()
            ]
            soda_peak = soda_spring.loc[
                soda_spring["soda3_ohc300_anom_15day_gj_m2"].idxmax()
            ]
            correlation = (
                float(
                    np.corrcoef(
                        common["tao_ohc300_anom_15day_gj_m2"],
                        common["soda3_ohc300_anom_15day_gj_m2"],
                    )[0, 1]
                )
                if len(common) >= 10
                else np.nan
            )
            row.update(
                {
                    "tao_spring_peak_date": tao_peak["date"].date(),
                    "tao_spring_peak_gj_m2": float(
                        tao_peak["tao_ohc300_anom_15day_gj_m2"]
                    ),
                    "tao_peak_minus_soda3_days": int(
                        (tao_peak["date"] - soda_peak["date"]).days
                    ),
                    "mar_apr_daily_shape_r": correlation,
                    "common_days_for_shape_r": int(len(common)),
                    "tao_status": "available",
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def make_figure(aligned: pd.DataFrame, summary: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "pdf.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(
        3,
        2,
        figsize=(11.4, 9.0),
        gridspec_kw={"width_ratios": [1.38, 1.0], "hspace": 0.34, "wspace": 0.20},
    )
    tao_color = "#D55E00"
    soda_color = "#0072B2"
    stress_color = "#2A7F62"

    for row_index, year in enumerate(EVENTS):
        event = aligned.loc[aligned["year"].eq(year)].copy()
        result = summary.loc[summary["year"].eq(year)].iloc[0]
        heat_axis, stress_axis = axes[row_index]
        for axis in (heat_axis, stress_axis):
            axis.axvspan(
                pd.Timestamp(f"{year}-03-01"),
                pd.Timestamp(f"{year}-04-30"),
                color="#F4E4C1",
                alpha=0.45,
                lw=0,
            )
            axis.axvspan(
                pd.Timestamp(f"{year}-05-01"),
                pd.Timestamp(f"{year}-06-30"),
                color="#DDECDD",
                alpha=0.50,
                lw=0,
            )
            axis.grid(axis="y", color="0.90", lw=0.7)
            axis.set_xlim(
                pd.Timestamp(f"{year}-01-01"),
                pd.Timestamp(f"{year}-06-30"),
            )
            axis.xaxis.set_major_locator(mdates.MonthLocator())
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
            if row_index < 2:
                axis.tick_params(axis="x", labelbottom=False)

        heat_axis.axhline(0, color="0.35", lw=0.8)
        heat_axis.plot(
            event["date"],
            event["soda3_ohc300_anom_15day_gj_m2"],
            color=soda_color,
            lw=2.0,
            label="SODA3 region (5S-5N, 180-140W)",
        )
        if result["tao_status"] == "available":
            heat_axis.plot(
                event["date"],
                event["tao_ohc300_anom_15day_gj_m2"],
                color=tao_color,
                lw=2.0,
                label="TAO local (0N, 140W)",
            )
            tao_peak = pd.Timestamp(result["tao_spring_peak_date"])
            soda_peak = pd.Timestamp(result["soda3_spring_peak_date"])
            heat_axis.axvline(tao_peak, color=tao_color, ls=":", lw=1.0)
            heat_axis.axvline(soda_peak, color=soda_color, ls=":", lw=1.0)
            heat_axis.text(
                0.985,
                0.05,
                f"Mar-Apr shape r = {result['mar_apr_daily_shape_r']:.2f}\n"
                f"TAO peak lag = {int(result['tao_peak_minus_soda3_days']):+d} d",
                transform=heat_axis.transAxes,
                ha="right",
                va="bottom",
                fontsize=8,
                color="0.25",
            )
        else:
            heat_axis.text(
                0.50,
                0.72,
                "TAO 0-300 m OHC unavailable\n2023 profiles reached only 180 m",
                transform=heat_axis.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="0.35",
                bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "0.75"},
            )
        heat_axis.set_ylim(-1.0, 5.1)
        heat_axis.set_ylabel("OHC anomaly (GJ m$^{-2}$)")
        heat_axis.set_title(f"{year}: observed ocean heat checkpoint", loc="left", fontweight="bold")

        stress_axis.axhline(0, color="0.25", lw=0.9)
        stress_axis.plot(
            event["date"],
            event["soda3_taux_15day_nm2"],
            color=stress_color,
            lw=2.0,
        )
        stress_axis.set_ylim(-0.09, 0.025)
        stress_axis.set_ylabel("Zonal wind stress (N m$^{-2}$)")
        coupling_text = (
            "Sustained actual westerly established"
            if result["actual_westerly_established"]
            else "No sustained actual westerly"
        )
        stress_axis.text(
            0.985,
            0.08,
            f"{coupling_text}\nMay-Jun max = {result['may_jun_stress_max_nm2']:+.3f}",
            transform=stress_axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            color="0.25",
        )
        stress_axis.set_title("Subsequent atmospheric response", loc="left", fontweight="bold")

        if row_index == 0:
            heat_axis.legend(loc="upper left", frameon=False, fontsize=8)

    for axis in axes[-1]:
        axis.set_xlabel("Calendar month")

    fig.suptitle(
        "Independent TAO check of the SODA3 five-day ocean-heat checkpoint",
        fontsize=14,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.008,
        "TAO: quality flags 1-3, complete profiles to 300 m, 15-day mean with >=10 observed days. "
        "SODA3: 15-day mean. Shading: Mar-Apr (ocean checkpoint), May-Jun (coupling response).",
        ha="center",
        va="bottom",
        fontsize=7.5,
        color="0.35",
    )
    fig.subplots_adjust(
        left=0.075,
        right=0.985,
        top=0.925,
        bottom=0.085,
        hspace=0.34,
        wspace=0.20,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=300, bbox_inches="tight")
    fig.savefig(PDF, bbox_inches="tight")
    plt.close(fig)


def format_date(value: object) -> str:
    return "-" if pd.isna(value) else str(value)


def write_report(summary: pd.DataFrame, monthly: pd.DataFrame) -> None:
    baseline = monthly.loc[
        monthly["year"].between(BASELINE_START, BASELINE_END)
        & monthly["month"].between(1, 6)
        & monthly["complete_profile_days"].ge(MIN_MONTHLY_PROFILE_DAYS)
    ]
    baseline_counts = baseline.groupby("month")["year"].nunique()
    event_1997 = summary.loc[summary["year"].eq(1997)].iloc[0]
    event_2015 = summary.loc[summary["year"].eq(2015)].iloc[0]
    rows = []
    for _, event in summary.iterrows():
        correlation = (
            "-"
            if pd.isna(event["mar_apr_daily_shape_r"])
            else f"{event['mar_apr_daily_shape_r']:+.2f}"
        )
        lag = (
            "-"
            if pd.isna(event["tao_peak_minus_soda3_days"])
            else f"{int(event['tao_peak_minus_soda3_days']):+d} d"
        )
        rows.append(
            "| "
            + " | ".join(
                [
                    str(int(event["year"])),
                    format_date(event["soda3_spring_peak_date"]),
                    format_date(event["tao_spring_peak_date"]),
                    lag,
                    correlation,
                    f"{event['may_jun_stress_max_nm2']:+.3f}",
                    "是" if event["actual_westerly_established"] else "否",
                ]
            )
            + " |"
        )
    report = f"""# TAO 对 SODA3 五日热含量转折点的独立观测核验

## 目的

检验 SODA3 得出的春季上层海洋热含量峰值是否有独立锚系观测支持，
并把海洋预条件与随后 5-6 月大气西风响应放在同一时间轴上。TAO 是
0°N、140°W 单点，SODA3 是 5°S-5°N、180°-140°W 区域平均，因此只检验
符号、事件排序和峰值先后，不要求振幅相等。

## 方法

- TAO 日温度剖面只保留质量标志 1-3；剖面必须从 10 m 以内延伸到
  300 m，并至少有 {MIN_PROFILE_LEVELS} 个有效深度。热含量按
  `rho*Cp*integral(T dz)` 计算，`rho={RHO:.0f} kg m-3`、
  `Cp={CP:.0f} J kg-1 K-1`。
- 气候态与趋势统一用 {BASELINE_START}-{BASELINE_END} 年：对每个日历月的
  月平均热含量拟合线性趋势，再从逐日值中扣除该事件年份的月预期值。
  每个月至少要有 {MIN_MONTHLY_PROFILE_DAYS} 个完整日剖面才进入基准期拟合；
  1-6 月各月可用基准年数为 {int(baseline_counts.min())}-{int(baseline_counts.max())} 年。
- TAO 与 SODA3 都用 15 日滑动平均；TAO 每个窗口至少要求
  {MIN_ROLLING_DAYS} 个完整日剖面。曲线相关只描述同一事件 3-4 月的
  形状一致性，因日值有强自相关，不把它当成独立样本显著性检验。

## 结果

| 年份 | SODA3春季峰值 | TAO春季峰值 | TAO相对滞后 | 3-4月曲线r | 5-6月最大风应力 | 持续实际西风 |
|---:|:---:|:---:|---:|---:|---:|:---:|
{chr(10).join(rows)}

1. **1997 的海洋信号得到较强支持。** TAO 0°N、140°W 的完整 0-300 m
   热含量在 3-4 月与 SODA3 区域曲线相关为
   {event_1997['mar_apr_daily_shape_r']:+.2f}，峰值晚约
   {int(event_1997['tao_peak_minus_soda3_days'])} 天；两者
   都把 1997 排在 2015 之前。随后 5-6 月 SODA3 实际风应力转为并维持
   西风，符合强海气耦合的 EP 发展。
2. **2015 的“海洋已准备好、风没有接上”不是由 SODA3 单独制造的。**
   TAO 同样记录到明显正热含量异常，春季峰值约为
   {event_2015['tao_spring_peak_gj_m2']:.2f} GJ m-2；TAO 与 SODA3
   曲线相关为 {event_2015['mar_apr_daily_shape_r']:+.2f}。可是 5-6 月最大区域实际风
   应力仍为负，没有形成持续西风。因此 2015 是当前主线中最重要的
   反例：海洋暖量是必要背景，但并不充分决定大气 Bjerknes 反馈接通。
3. **2023 不能用这根锚系做 0-300 m 热含量核验。** 该年 1-6 月观测最深
   只有 180 m；报告保留缺测，不向 300 m 外推。SODA3 给出较弱的春季
   正热含量和持续偏东风，但这一年的热含量振幅仍属于再分析证据，不能
   标成 TAO 已验证。

## 对“转变点”的含义

这一步支持把转变点写成**连续的海洋检查点加后续大气门控**，而不是一条
普适热含量阈值。1997 与 2015 都有独立观测支持的强正热含量，但只有
1997 随后出现持续实际西风；所以类型分岔不能只由热含量大小决定。
下一步最有信息量的简洁检验不是加入更多指数，而是在相同热含量条件下，
比较风应力何时由负转正、能否连续维持，以及这一差异是否能在更多完整
TAO 剖面年份中复现。

## 局限

- TAO 单点不能重建 SODA3 的 5°S-5°N 全断面，也不能验证区域绝对振幅。
- 1997 完整 300 m 剖面止于 4 月中旬；峰值日期可核验，但不能用该站
  追踪 5-6 月热含量演变。
- 2023 的深层缺测使三事件完全对称的观测比较无法成立。
- 这里使用的后续风应力仍来自 SODA3 表面强迫；TAO 风的跨年代同站资料
  需要另行补齐后才能称为完全独立的“海洋加大气”联合验证。

## 数据来源

- NOAA/NDBC TAO 数据下载与质量码说明：
  https://tao.ndbc.noaa.gov/data-download/download-readme.shtml
- NOAA/PMEL ERDDAP：
  https://data.pmel.noaa.gov/pmel/erddap/index.html
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    temperature = read_tao_temperature()
    raw_ohc = daily_ohc300(temperature)
    tao, monthly = add_detrended_monthly_anomaly(raw_ohc)
    soda = pd.read_csv(SODA_FIVE_DAY)
    soda["time"] = pd.to_datetime(soda["time"])
    event_summary = pd.read_csv(SODA_EVENT_SUMMARY)
    aligned = event_aligned(tao, soda)
    summary = summarize_events(aligned, event_summary)

    tao.to_csv(TAO_DAILY, index=False)
    aligned.to_csv(ALIGNED, index=False)
    summary.to_csv(SUMMARY, index=False)
    make_figure(aligned, summary)
    write_report(summary, monthly)

    print(summary.to_string(index=False))
    print(PNG)
    print(PDF)
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
