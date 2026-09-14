#!/usr/bin/env python3
"""Direct wind-coupling and heat-wind mismatch diagnostics.

Only existing physical variables are compared.  The script does not define a
coupling index, decoupling index, empirical equation, regression, threshold,
or onset date.  It uses:

* ERSSTv5 SST anomaly;
* GPCP precipitation anomaly;
* ERA5 eastward turbulent surface-stress anomaly;
* SODA3 central-box eastward heat output and box OHC anomalies.

The main spatial diagnostic is a March--October longitude-time view averaged
over the same 10S--5N latitude band as the two-box heat budget.  Direct paired
plots then show where heat transport and wind stress do or do not evolve
together.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/jiang_epcp_two_box_heat_fate"

SST_FILE = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
GPCP_FILE = ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc"
STRESS_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"
MONTHLY_FILE = DERIVED / "jiang_epcp_mar_oct_direct_physical_variables.csv"
MJJ_FILE = DERIVED / "jiang_epcp_mjj_direct_physical_variable_means.csv"

HOVMOLLER_FILE = DERIVED / "jiang_1997_2015_2023_mar_oct_sst_precip_stress_hovmoller.nc"
METADATA_FILE = DERIVED / "jiang_heat_wind_coupling_direct_metadata.json"
HOVMOLLER_FIGURE = OUT / "jiang_1997_2015_2023_wind_coupling_hovmoller.png"
FOCUS_TIMELINE_FIGURE = OUT / "jiang_1997_2015_2023_heat_wind_direct_timeline.png"
ALL_EVENT_PAIR_FIGURE = OUT / "jiang_all_events_mjj_heat_wind_direct_pairs.png"
REPORT_FILE = OUT / "JIANG_WIND_COUPLING_HEAT_WIND_DECOUPLING_DIRECT_CN.md"

FOCUS_EVENTS = (1997, 2015, 2023)
MONTHS = tuple(range(3, 11))
MONTH_LABELS = ("Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct")
REFERENCE_START = 1982
REFERENCE_END = 2022
LAT_MIN = -10.0
LAT_MAX = 5.0
LON_MIN = 120.0
LON_MAX = 280.0
EVENT_COLORS = {1997: "#D95F02", 2015: "#1B9E77", 2023: "#7B2CBF"}
GROUP_COLORS = {"EP": "#D95F02", "CP": "#2A9D8F", "2023": "#7B2CBF"}


def normalize_longitude(data: xr.DataArray, longitude: str) -> xr.DataArray:
    normalized = data.assign_coords({longitude: np.mod(data[longitude], 360.0)})
    normalized = normalized.sortby(longitude)
    _, indices = np.unique(normalized[longitude].values, return_index=True)
    return normalized.isel({longitude: np.sort(indices)})


def latitude_mean(
    data: xr.DataArray,
    *,
    latitude: str,
    longitude: str,
) -> xr.DataArray:
    normalized = normalize_longitude(data, longitude)
    selected = normalized.where(
        (normalized[latitude] >= LAT_MIN)
        & (normalized[latitude] <= LAT_MAX)
        & (normalized[longitude] >= LON_MIN)
        & (normalized[longitude] <= LON_MAX),
        drop=True,
    )
    if selected.sizes.get(latitude, 0) == 0 or selected.sizes.get(longitude, 0) == 0:
        raise ValueError("Empty longitude-time analysis domain")
    weights = np.cos(np.deg2rad(selected[latitude]))
    return selected.weighted(weights).mean(latitude, skipna=True)


def detrended_monthly_field_anomaly(
    data: xr.DataArray,
    *,
    time: str,
) -> xr.DataArray:
    """Subtract a 1982--2022 linear expectation separately for each month/lon."""
    outputs: list[xr.DataArray] = []
    time_values = pd.DatetimeIndex(data[time].values)
    for month in range(1, 13):
        month_mask = time_values.month == month
        month_data = data.isel({time: np.flatnonzero(month_mask)})
        month_times = pd.DatetimeIndex(month_data[time].values)
        reference_mask = (month_times.year >= REFERENCE_START) & (
            month_times.year <= REFERENCE_END
        )
        reference = month_data.isel({time: np.flatnonzero(reference_mask)})
        years = np.asarray(
            pd.DatetimeIndex(reference[time].values).year,
            dtype=float,
        )
        values = np.asarray(reference.to_numpy(), dtype=float)
        if values.shape[0] < 20:
            raise ValueError(f"Insufficient reference years for month {month}")
        slopes = np.full(values.shape[1], np.nan)
        intercepts = np.full(values.shape[1], np.nan)
        for longitude_index in range(values.shape[1]):
            series = values[:, longitude_index]
            finite = np.isfinite(series)
            if finite.sum() >= 20:
                slopes[longitude_index], intercepts[longitude_index] = np.polyfit(
                    years[finite], series[finite], 1
                )
        target_years = np.asarray(month_times.year, dtype=float)
        expected = (
            target_years[:, None] * slopes[None, :] + intercepts[None, :]
        )
        anomaly = month_data.copy(
            data=np.asarray(month_data.to_numpy(), dtype=float) - expected
        )
        outputs.append(anomaly)
    return xr.concat(outputs, dim=time).sortby(time)


def extract_sst_hovmoller() -> xr.DataArray:
    with xr.open_dataset(SST_FILE, decode_times=True) as dataset:
        mean = latitude_mean(dataset["sst"], latitude="lat", longitude="lon").load()
    anomaly = detrended_monthly_field_anomaly(mean, time="time")
    return anomaly.rename({"lon": "sst_lon"}).rename("sst_anomaly_c")


def extract_precip_hovmoller() -> xr.DataArray:
    with xr.open_dataset(GPCP_FILE, decode_times=True) as dataset:
        mean = latitude_mean(
            dataset["precip"], latitude="lat", longitude="lon"
        ).load()
    anomaly = detrended_monthly_field_anomaly(mean, time="time")
    return anomaly.rename({"lon": "precip_lon"}).rename(
        "precip_anomaly_mm_day"
    )


def load_stress() -> xr.DataArray:
    monthly: list[xr.DataArray] = []
    for month in range(1, 13):
        parts = []
        for part in ("part01", "part02"):
            path = STRESS_DIR / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            with xr.open_dataset(path, decode_times=True) as dataset:
                parts.append(dataset["avg_iews"].load())
        combined = xr.concat(parts, dim="longitude")
        monthly.append(normalize_longitude(combined, "longitude"))
    return xr.concat(monthly, dim="valid_time").sortby("valid_time")


def extract_stress_hovmoller() -> xr.DataArray:
    mean = latitude_mean(
        load_stress(), latitude="latitude", longitude="longitude"
    )
    anomaly = detrended_monthly_field_anomaly(mean, time="valid_time")
    return anomaly.rename(
        {"valid_time": "time", "longitude": "stress_lon"}
    ).rename("eastward_stress_anomaly_nm2")


def select_focus(data: xr.DataArray, *, time: str = "time") -> xr.DataArray:
    pieces = []
    for event_year in FOCUS_EVENTS:
        time_index = pd.DatetimeIndex(data[time].values)
        mask = (time_index.year == event_year) & np.isin(time_index.month, MONTHS)
        selected = data.isel({time: np.flatnonzero(mask)})
        if selected.sizes[time] != len(MONTHS):
            raise ValueError(f"Incomplete March-October field for {event_year}")
        selected = selected.assign_coords(
            {time: np.asarray(MONTHS, dtype=int)}
        ).rename({time: "month"})
        pieces.append(selected.expand_dims(event_year=[event_year]))
    return xr.concat(pieces, dim="event_year")


def build_hovmoller_dataset() -> xr.Dataset:
    sst = select_focus(extract_sst_hovmoller())
    precip = select_focus(extract_precip_hovmoller())
    stress = select_focus(extract_stress_hovmoller())
    dataset = xr.Dataset(
        {
            "sst_anomaly_c": sst,
            "precip_anomaly_mm_day": precip,
            "eastward_stress_anomaly_nm2": stress,
        }
    )
    dataset.attrs.update(
        {
            "analysis": "Direct physical fields; no coupling/decoupling index or threshold",
            "latitude_band": "10S-5N area-weighted mean",
            "anomaly_reference": "1982-2022 same-calendar-month linear expectation",
        }
    )
    return dataset


def longitude_labels(values: list[int]) -> list[str]:
    labels = []
    for value in values:
        if value < 180:
            labels.append(f"{value}°E")
        elif value == 180:
            labels.append("180°")
        else:
            labels.append(f"{360 - value}°W")
    return labels


def symmetric_limit(values: np.ndarray, percentile: float = 98.0) -> float:
    finite = np.abs(values[np.isfinite(values)])
    return float(np.percentile(finite, percentile))


def make_hovmoller_figure(dataset: xr.Dataset) -> None:
    variables = [
        ("sst_anomaly_c", "sst_lon", "ERSSTv5 SST anomaly", "°C", "RdBu_r"),
        (
            "precip_anomaly_mm_day",
            "precip_lon",
            "GPCP precipitation anomaly",
            "mm day⁻¹",
            "BrBG",
        ),
        (
            "eastward_stress_anomaly_nm2",
            "stress_lon",
            "ERA5 eastward surface-stress anomaly",
            "N m⁻²",
            "RdBu_r",
        ),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(16, 12), sharex="col", sharey=True)
    images = []
    for column, (variable, longitude, title, units, cmap) in enumerate(variables):
        values = np.asarray(dataset[variable].to_numpy(), dtype=float)
        limit = symmetric_limit(values)
        norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
        column_images = []
        for row, event_year in enumerate(FOCUS_EVENTS):
            axis = axes[row, column]
            field = dataset[variable].sel(event_year=event_year)
            image = axis.pcolormesh(
                dataset[longitude],
                dataset.month,
                field,
                shading="auto",
                cmap=cmap,
                norm=norm,
            )
            column_images.append(image)
            for boundary in (180.0, 220.0):
                axis.axvline(boundary, color="#222222", linewidth=0.8, linestyle="--")
            axis.set_ylim(10.5, 2.5)
            axis.set_yticks(MONTHS, MONTH_LABELS)
            axis.set_xlim(LON_MIN, LON_MAX)
            ticks = [120, 150, 180, 210, 240, 270]
            axis.set_xticks(ticks, longitude_labels(ticks))
            if row == 0:
                axis.set_title(title, fontsize=12.5, weight="bold")
            if column == 0:
                axis.set_ylabel(str(event_year), fontsize=13, weight="bold")
        images.append(column_images[-1])
        colorbar = fig.colorbar(
            column_images[-1],
            ax=axes[:, column],
            orientation="horizontal",
            fraction=0.028,
            pad=0.085,
        )
        colorbar.set_label(units, fontsize=9)
        colorbar.ax.tick_params(labelsize=8)
    fig.suptitle(
        "Longitude–time evolution of direct wind-coupling variables",
        fontsize=19,
        weight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.953,
        "10°S–5°N, March–October; dashed lines: 180° and 140°W; positive stress is eastward/westerly",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.91, bottom=0.16, hspace=0.11, wspace=0.12)
    fig.savefig(HOVMOLLER_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_focus_timeline_figure(monthly: pd.DataFrame) -> None:
    focus = monthly.loc[monthly.event_year.isin(FOCUS_EVENTS)].copy()
    heat_limit = max(2.1, float(focus.central_eastward_heat_output_anom_pw.max()) * 1.08)
    sst_limit = max(3.0, float(focus.east_sst_anom_c.max()) * 1.08)
    stress_low = min(-0.012, float(focus.central_taux_anom_nm2.min()) * 1.15)
    stress_high = max(0.045, float(focus.central_taux_anom_nm2.max()) * 1.15)
    fig, axes = plt.subplots(3, 2, figsize=(13, 11), sharex=True)
    for row, event_year in enumerate(FOCUS_EVENTS):
        event = focus.loc[focus.event_year.eq(event_year)]
        for column, (variable, ylabel, line_color, line_limit, title) in enumerate(
            (
                (
                    "central_eastward_heat_output_anom_pw",
                    "Eastward heat output (PW)",
                    "#D95F02",
                    heat_limit,
                    "Central-box eastward heat output",
                ),
                (
                    "east_sst_anom_c",
                    "Eastern-box SST anomaly (°C)",
                    "#B2182B",
                    sst_limit,
                    "Eastern-box SST",
                ),
            )
        ):
            axis = axes[row, column]
            stress_axis = axis.twinx()
            stress_axis.bar(
                event.month,
                event.central_taux_anom_nm2,
                width=0.55,
                color="#4C78A8",
                alpha=0.35,
                label="Central-box eastward stress",
                zorder=1,
            )
            axis.plot(
                event.month,
                event[variable],
                color=line_color,
                marker="o",
                linewidth=2.2,
                label=ylabel,
                zorder=3,
            )
            axis.axhline(0.0, color="#777777", linewidth=0.7)
            stress_axis.axhline(0.0, color="#4C78A8", linewidth=0.6, alpha=0.7)
            axis.set_ylim(min(-0.15, float(event[variable].min()) * 1.08), line_limit)
            stress_axis.set_ylim(stress_low, stress_high)
            axis.grid(axis="y", color="#DDDDDD", linewidth=0.6)
            axis.set_ylabel(ylabel, fontsize=9)
            if column == 1:
                stress_axis.set_ylabel("Eastward stress anomaly (N m⁻²)", fontsize=9)
            else:
                stress_axis.set_yticklabels([])
            axis.set_title(f"{event_year}: {title}", fontsize=11.5, weight="bold")
            axis.set_xticks(MONTHS, MONTH_LABELS)
            if row == 0 and column == 1:
                handles1, labels1 = axis.get_legend_handles_labels()
                handles2, labels2 = stress_axis.get_legend_handles_labels()
                axis.legend(
                    handles1 + handles2,
                    labels1 + labels2,
                    loc="upper left",
                    frameon=False,
                    fontsize=8,
                )
    fig.suptitle(
        "Direct monthly comparison: ocean heat/SST and central-Pacific wind stress",
        fontsize=17,
        weight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.950,
        "Bars and lines retain physical units; no heat–wind ratio or decoupling threshold",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.tight_layout(rect=(0.02, 0.02, 0.99, 0.915))
    fig.savefig(FOCUS_TIMELINE_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_all_event_pair_figure(mjj: pd.DataFrame) -> None:
    pairs = [
        (
            "central_eastward_heat_output_anom_pw",
            "central_taux_anom_nm2",
            "Central-box eastward heat output (PW)",
            "Central-box eastward stress anomaly (N m⁻²)",
        ),
        (
            "east_sst_anom_c",
            "central_taux_anom_nm2",
            "Eastern-box SST anomaly (°C)",
            "Central-box eastward stress anomaly (N m⁻²)",
        ),
        (
            "central_precip_anom_mm_day",
            "central_taux_anom_nm2",
            "Central-box precipitation anomaly (mm day⁻¹)",
            "Central-box eastward stress anomaly (N m⁻²)",
        ),
        (
            "east_ohc300_anom_zj",
            "central_taux_anom_nm2",
            "Eastern-box 0–300 m OHC anomaly (ZJ)",
            "Central-box eastward stress anomaly (N m⁻²)",
        ),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    for axis, (xvar, yvar, xlabel, ylabel) in zip(axes.ravel(), pairs, strict=True):
        for row in mjj.itertuples(index=False):
            group = str(row.group)
            marker = "*" if int(row.event_year) == 2023 else "s" if group == "EP" else "o"
            size = 190 if int(row.event_year) == 2023 else 65
            axis.scatter(
                getattr(row, xvar),
                getattr(row, yvar),
                s=size,
                marker=marker,
                color=GROUP_COLORS[group],
                edgecolor="white",
                linewidth=0.7,
                zorder=3,
            )
            axis.annotate(
                str(int(row.event_year)),
                (getattr(row, xvar), getattr(row, yvar)),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=8.5,
            )
        axis.axhline(0.0, color="#777777", linewidth=0.8)
        axis.axvline(0.0, color="#777777", linewidth=0.8)
        axis.grid(color="#E0E0E0", linewidth=0.6)
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
    legend_handles = [
        plt.Line2D([], [], marker="s", linestyle="", color=GROUP_COLORS["EP"], label="EP"),
        plt.Line2D([], [], marker="o", linestyle="", color=GROUP_COLORS["CP"], label="CP"),
        plt.Line2D([], [], marker="*", markersize=12, linestyle="", color=GROUP_COLORS["2023"], label="2023"),
    ]
    axes[0, 0].legend(handles=legend_handles, frameon=False, loc="best")
    fig.suptitle(
        "MJJ event-by-event direct pairs: ocean/precipitation versus wind stress",
        fontsize=17,
        weight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.945,
        "No fitted line, ratio, threshold or coupling classification is applied",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.tight_layout(rect=(0.02, 0.02, 0.99, 0.90))
    fig.savefig(ALL_EVENT_PAIR_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def signed(value: float, digits: int = 3) -> str:
    return f"{value:+.{digits}f}"


def write_report(monthly: pd.DataFrame, mjj: pd.DataFrame) -> None:
    lines: list[str] = [
        "# 风耦合与热量—风不同步：直接物理量分析",
        "",
        "## 分析原则",
        "",
        "- 不定义风耦合指数、热量—风脱耦指数、比值、回归方程或判定阈值。",
        "- 风耦合只通过已有变量的经度—时间共同演变来观察：ERSSTv5 SST、GPCP降水、ERA5纬向表面风应力。",
        "- 热量—风不同步只通过SODA3中箱向东热输出、东箱SST/OHC与中箱风应力的逐月并列来判断，不给事件贴新的类别标签。",
        "- 空间图使用10°S–5°N面积加权平均，时间为发展年3—10月；正风应力异常表示东向/西风异常。",
        "",
        "## 一、风耦合的直接演变",
        "",
        "### 1997",
        "",
        "- 4—6月暖SST由东部向中部扩展；6月中、东太平洋降水明显增强。",
        "- 6月中太平洋出现宽广而强的东向风应力异常；8—10月再次出现持续的东向风应力带。",
        "- 因而1997中可以直接看到SST、降水和东向风应力在6月及夏秋季共同增强，但7月风应力也有短暂减弱，说明风响应本身具有月际间歇性。",
        "",
        "### 2015",
        "",
        "- 中东太平洋SST从春季持续升高，暖区逐渐向西扩展。",
        "- 降水增强主要位于日界线附近及中太平洋；东向风应力在春季已有响应，6月减弱，7—10月重新增强。",
        "- 2015不是简单的同月同步：热输送在4—5月已较强，而最明显的中太平洋东向风应力出现在7月以后。",
        "",
        "### 2023",
        "",
        "- 3—5月东太平洋SST已经显著偏暖，但中太平洋SST仍弱；暖异常到6—8月才逐渐扩展进入中部。",
        "- 5—7月较强降水主要偏西，日界线以东的降水增强远弱于1997/2015。",
        "- 同期中太平洋东向风应力接近零或空间上不连续；较清楚的中太平洋东向风应力带到8—9月才形成。",
        "- 所以2023的直接特征是东部海温先升高，而中部降水与西风响应较弱、较晚。",
        "",
        "## 二、1997、2015、2023逐月热量与风应力",
        "",
        "|事件|月份|中箱向东热输出 (PW)|东箱SST (°C)|中箱降水 (mm day⁻¹)|中箱东向风应力 (N m⁻²)|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    focus = monthly.loc[
        monthly.event_year.isin(FOCUS_EVENTS) & monthly.month.between(4, 9)
    ]
    for row in focus.itertuples(index=False):
        lines.append(
            "|"
            + "|".join(
                [
                    str(int(row.event_year)),
                    MONTH_LABELS[int(row.month) - 3],
                    signed(float(row.central_eastward_heat_output_anom_pw)),
                    signed(float(row.east_sst_anom_c), 2),
                    signed(float(row.central_precip_anom_mm_day), 2),
                    signed(float(row.central_taux_anom_nm2), 3),
                ]
            )
            + "|"
        )

    lines.extend(
        [
            "",
            "直接对比可见：",
            "",
            "- 1997年4—6月中箱热输出由+1.30升至+1.98 PW，6月中箱风应力同时升至+0.037 N m⁻²。",
            "- 2015年4—5月热输出约+1.02 PW、风应力约+0.014至+0.015 N m⁻²；6月风减弱，7月风应力再增至+0.035 N m⁻²。",
            "- 2023年4—7月热输出一直维持+0.89至+1.10 PW，但5—7月中箱风应力只有约0至+0.001 N m⁻²；8月才升至+0.017 N m⁻²。",
            "- 因而2023年4—7月可以描述为热量持续向东输送、东箱持续增暖，但中太平洋风响应没有同步增强。这里的“不同步”是逐月事实描述，不是由阈值定义的新类别。",
            "",
            "## 三、全部事件MJJ直接并列",
            "",
            "|事件|类型|中箱向东热输出 (PW)|东箱SST (°C)|东箱OHC (ZJ)|中箱降水 (mm day⁻¹)|中箱东向风应力 (N m⁻²)|",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in mjj.itertuples(index=False):
        lines.append(
            "|"
            + "|".join(
                [
                    str(row.event_label),
                    "FEP-EP" if row.group == "2023" else str(row.group),
                    signed(float(row.central_eastward_heat_output_anom_pw)),
                    signed(float(row.east_sst_anom_c), 2),
                    signed(float(row.east_ohc300_anom_zj), 2),
                    signed(float(row.central_precip_anom_mm_day), 2),
                    signed(float(row.central_taux_anom_nm2), 3),
                ]
            )
            + "|"
        )

    lines.extend(
        [
            "",
            "## 四、其他事件说明热量与风不是一一对应",
            "",
            "- 2009：中箱向东输出+0.575 PW、东箱SST+0.56°C，但中箱风应力约为0。它与2023共同说明较强东传并不自动对应较强西风。",
            "- 1982：中箱向东输出+0.552 PW，但中箱风应力仅+0.001 N m⁻²，中、东箱降水仍为负异常。",
            "- 1987：中箱向东输出只有+0.225 PW，东箱SST+0.82°C，中箱风应力却达到+0.013 N m⁻²；当期风响应显然不能只由该边界热输送解释。",
            "- 2019：中箱东边界热输送为反向异常−0.215 PW，但中箱风应力仍为+0.009 N m⁻²。风场还可能保留先前海温、箱外对流或其他背景影响，本分析不进一步归因。",
            "- 1986：热输送较弱，同时中、东箱SST和降水为负，中箱风应力为西向异常，是海洋和大气均较弱的情况，不属于“有热无风”。",
            "",
            "## 当前可以成立的结论",
            "",
            "1. 风耦合不是连续平滑建立的；1997和2015也存在月际中断，但能形成较宽的中太平洋东向风应力带。",
            "2. 2023年东部SST和跨140°W热输送先增强，中太平洋降水与东向风应力到8—9月才较明显，因此其关键异常位于热力发展与中部风响应之间。",
            "3. 全部事件表明，同期热输送、东箱OHC或东箱SST都不能单独决定中太平洋风应力；2009、1987和2019是重要反例。",
            "4. 下一步若继续做机制归因，应直接检查2023年5—7月的对流位置、海平面气压和外部盆地背景，而不是先创造一个脱耦指数。",
            "",
            "## 解释边界",
            "",
            "- 这些结果展示共同演变与不同步，不建立统计因果。",
            "- 经度—时间场、箱平均量和热输送来自不同资料与分辨率，但都采用相同纬带并保持各自物理单位。",
            "- 非FEP事件的EP/CP标签仍沿用Jiang正文约束下的工作重建；不影响逐事件物理量本身。",
        ]
    )
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def validate(dataset: xr.Dataset, monthly: pd.DataFrame, mjj: pd.DataFrame) -> dict[str, object]:
    if monthly.duplicated(["event_year", "month"]).any():
        raise ValueError("Duplicate event-month rows")
    if monthly.select_dtypes(include=[np.number]).isna().any().any():
        raise ValueError("Missing numeric data in monthly direct-variable table")
    if mjj.event_year.nunique() != 14:
        raise ValueError("Incomplete MJJ event table")
    diagnostics: dict[str, object] = {
        "monthly_rows": len(monthly),
        "mjj_events": int(mjj.event_year.nunique()),
        "focus_events": list(FOCUS_EVENTS),
        "months": list(MONTHS),
        "field_ranges": {},
    }
    for variable in dataset.data_vars:
        values = np.asarray(dataset[variable].to_numpy(), dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"Non-finite longitude-time data in {variable}")
        diagnostics["field_ranges"][variable] = [
            float(values.min()),
            float(values.max()),
        ]
    return diagnostics


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dataset = build_hovmoller_dataset()
    monthly = pd.read_csv(MONTHLY_FILE)
    mjj = pd.read_csv(MJJ_FILE)
    diagnostics = validate(dataset, monthly, mjj)
    dataset.to_netcdf(HOVMOLLER_FILE)
    make_hovmoller_figure(dataset)
    make_focus_timeline_figure(monthly)
    make_all_event_pair_figure(mjj)
    write_report(monthly, mjj)
    metadata = {
        "scope": "Direct wind-coupling and heat-wind mismatch diagnostics only; no new index/equation/threshold.",
        "latitude_band": [LAT_MIN, LAT_MAX],
        "longitude_range": [LON_MIN, LON_MAX],
        "reference_years": [REFERENCE_START, REFERENCE_END],
        "sources": {
            "sst": str(SST_FILE),
            "precipitation": str(GPCP_FILE),
            "surface_stress": str(STRESS_DIR),
            "box_monthly_variables": str(MONTHLY_FILE),
            "mjj_event_means": str(MJJ_FILE),
        },
        "signs": {
            "surface_stress": "positive is eastward/westerly anomaly",
            "heat_output": "positive is eastward anomalous heat output from the central box",
        },
        "diagnostics": diagnostics,
    }
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {HOVMOLLER_FILE}")
    print(f"Wrote {METADATA_FILE}")
    print(f"Wrote {HOVMOLLER_FIGURE}")
    print(f"Wrote {FOCUS_TIMELINE_FIGURE}")
    print(f"Wrote {ALL_EVENT_PAIR_FIGURE}")
    print(f"Wrote {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
