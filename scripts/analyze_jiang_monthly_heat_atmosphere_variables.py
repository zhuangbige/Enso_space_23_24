#!/usr/bin/env python3
"""Direct monthly comparison of existing ocean and atmosphere variables.

This analysis deliberately does not construct a coupling index, efficiency
ratio, empirical equation, or event-onset threshold.  It extracts the same
physical variables for each Jiang-aligned event from March through October:

* SODA3 0--300 m OHC anomaly in the central and eastern boxes;
* SODA3 anomalous eastward heat output at the central-box east face and
  anomalous heat input at the eastern-box west face;
* ERSSTv5 SST anomaly;
* GPCP precipitation anomaly;
* ERA5 eastward turbulent surface-stress anomaly.

SST, precipitation, and stress are first area-averaged over the two boxes and
then expressed as detrended same-calendar-month anomalies relative to
1982--2022.  The SODA3 anomaly columns retain their existing 1980--2022
same-calendar-month linear-expectation baseline.
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

BUDGET_FILE = DERIVED / "soda3_three_box_ohc_anomaly_budget_monthly.csv"
MANIFEST_FILE = DERIVED / "jiang2026_epcp_fep_event_manifest_1963_2023.csv"
SST_FILE = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
GPCP_FILE = ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc"
STRESS_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"

MONTHLY_FILE = DERIVED / "jiang_epcp_mar_oct_direct_physical_variables.csv"
PEAK_FILE = DERIVED / "jiang_epcp_mar_oct_direct_variable_monthly_extrema.csv"
MJJ_FILE = DERIVED / "jiang_epcp_mjj_direct_physical_variable_means.csv"
METADATA_FILE = DERIVED / "jiang_epcp_mar_oct_direct_physical_variables_metadata.json"
THREE_EVENT_FIGURE = OUT / "jiang_1997_2015_2023_mar_oct_direct_variables.png"
ALL_EVENT_FIGURE = OUT / "jiang_all_events_mar_oct_direct_variables.png"
REPORT_FILE = OUT / "JIANG_MAR_OCT_DIRECT_VARIABLE_ANALYSIS_CN.md"

EVENTS = (1982, 1986, 1987, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
FOCUS_EVENTS = (1997, 2015, 2023)
MONTHS = tuple(range(3, 11))
MONTH_LABELS = ("Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct")
REFERENCE_START = 1982
REFERENCE_END = 2022
BOXES = {
    "central": {"lat_min": -10.0, "lat_max": 5.0, "lon_min": 180.0, "lon_max": 220.0},
    "east": {"lat_min": -10.0, "lat_max": 5.0, "lon_min": 220.0, "lon_max": 280.0},
}
COLORS = {1997: "#D95F02", 2015: "#1B9E77", 2023: "#7B2CBF"}
GROUP_COLORS = {"EP": "#D95F02", "CP": "#2A9D8F", "2023": "#7B2CBF"}


def normalize_longitude(data: xr.DataArray, lon_name: str) -> xr.DataArray:
    lon = np.mod(data[lon_name], 360.0)
    normalized = data.assign_coords({lon_name: lon}).sortby(lon_name)
    _, unique_index = np.unique(normalized[lon_name].values, return_index=True)
    return normalized.isel({lon_name: np.sort(unique_index)})


def area_mean(
    data: xr.DataArray,
    *,
    lat_name: str,
    lon_name: str,
    bounds: dict[str, float],
) -> xr.DataArray:
    normalized = normalize_longitude(data, lon_name)
    selected = normalized.where(
        (normalized[lat_name] >= bounds["lat_min"])
        & (normalized[lat_name] <= bounds["lat_max"])
        & (normalized[lon_name] >= bounds["lon_min"])
        & (normalized[lon_name] <= bounds["lon_max"]),
        drop=True,
    )
    if selected.sizes.get(lat_name, 0) == 0 or selected.sizes.get(lon_name, 0) == 0:
        raise ValueError(f"Empty spatial selection for {bounds}")
    weights = np.cos(np.deg2rad(selected[lat_name]))
    return selected.weighted(weights).mean((lat_name, lon_name), skipna=True)


def detrended_monthly_anomaly(
    frame: pd.DataFrame,
    raw_column: str,
    anomaly_column: str,
) -> pd.DataFrame:
    output = frame.copy()
    output[anomaly_column] = np.nan
    for month in range(1, 13):
        reference = output.loc[
            output.month.eq(month)
            & output.year.between(REFERENCE_START, REFERENCE_END),
            ["year", raw_column],
        ].dropna()
        if len(reference) < 20:
            raise ValueError(f"Insufficient month-{month} reference data for {raw_column}")
        slope, intercept = np.polyfit(
            reference.year.to_numpy(dtype=float),
            reference[raw_column].to_numpy(dtype=float),
            1,
        )
        mask = output.month.eq(month)
        expected = slope * output.loc[mask, "year"].to_numpy(dtype=float) + intercept
        output.loc[mask, anomaly_column] = (
            output.loc[mask, raw_column].to_numpy(dtype=float) - expected
        )
    return output


def dataarray_to_frame(
    data: xr.DataArray,
    *,
    time_name: str,
    value_name: str,
) -> pd.DataFrame:
    frame = data.rename(value_name).to_dataframe().reset_index()
    frame["time"] = pd.to_datetime(frame[time_name])
    frame["year"] = frame.time.dt.year
    frame["month"] = frame.time.dt.month
    return frame[["time", "year", "month", value_name]].sort_values("time")


def extract_sst() -> pd.DataFrame:
    with xr.open_dataset(SST_FILE, decode_times=True) as dataset:
        pieces = []
        for box, bounds in BOXES.items():
            mean = area_mean(dataset["sst"], lat_name="lat", lon_name="lon", bounds=bounds)
            frame = dataarray_to_frame(
                mean,
                time_name="time",
                value_name=f"{box}_sst_raw_c",
            )
            frame = detrended_monthly_anomaly(
                frame,
                f"{box}_sst_raw_c",
                f"{box}_sst_anom_c",
            )
            pieces.append(frame)
    return pieces[0].merge(pieces[1], on=["time", "year", "month"], how="inner")


def extract_gpcp() -> pd.DataFrame:
    with xr.open_dataset(GPCP_FILE, decode_times=True) as dataset:
        pieces = []
        for box, bounds in BOXES.items():
            mean = area_mean(
                dataset["precip"], lat_name="lat", lon_name="lon", bounds=bounds
            )
            frame = dataarray_to_frame(
                mean,
                time_name="time",
                value_name=f"{box}_precip_raw_mm_day",
            )
            frame = detrended_monthly_anomaly(
                frame,
                f"{box}_precip_raw_mm_day",
                f"{box}_precip_anom_mm_day",
            )
            pieces.append(frame)
    return pieces[0].merge(pieces[1], on=["time", "year", "month"], how="inner")


def extract_stress() -> pd.DataFrame:
    monthly: list[xr.DataArray] = []
    for month in range(1, 13):
        parts = []
        for part in ("part01", "part02"):
            path = STRESS_DIR / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            with xr.open_dataset(path, decode_times=True) as dataset:
                parts.append(dataset["avg_iews"].load())
        combined = xr.concat(parts, dim="longitude")
        combined = normalize_longitude(combined, "longitude")
        monthly.append(combined)
    stress = xr.concat(monthly, dim="valid_time").sortby("valid_time")
    pieces = []
    for box, bounds in BOXES.items():
        mean = area_mean(
            stress,
            lat_name="latitude",
            lon_name="longitude",
            bounds=bounds,
        )
        frame = dataarray_to_frame(
            mean,
            time_name="valid_time",
            value_name=f"{box}_taux_raw_nm2",
        )
        frame = detrended_monthly_anomaly(
            frame,
            f"{box}_taux_raw_nm2",
            f"{box}_taux_anom_nm2",
        )
        pieces.append(frame)
    return pieces[0].merge(pieces[1], on=["time", "year", "month"], how="inner")


def extract_soda3() -> pd.DataFrame:
    columns = [
        "time",
        "year",
        "month",
        "central_ohc300_anom_zj",
        "east_ohc300_anom_zj",
        "central_east_theta_heat_in_corr_anom_pw",
        "east_west_theta_heat_in_corr_anom_pw",
    ]
    frame = pd.read_csv(BUDGET_FILE, usecols=columns, parse_dates=["time"])
    frame["central_eastward_heat_output_anom_pw"] = -frame[
        "central_east_theta_heat_in_corr_anom_pw"
    ]
    frame["east_west_boundary_heat_input_anom_pw"] = frame[
        "east_west_theta_heat_in_corr_anom_pw"
    ]
    return frame.drop(
        columns=[
            "central_east_theta_heat_in_corr_anom_pw",
            "east_west_theta_heat_in_corr_anom_pw",
        ]
    )


def event_groups() -> dict[int, str]:
    manifest = pd.read_csv(MANIFEST_FILE)
    selected = manifest.loc[manifest.event_year.isin(EVENTS)].copy()
    mapping = dict(zip(selected.event_year.astype(int), selected.mature_type_working))
    mapping[2023] = "2023"
    if set(mapping) != set(EVENTS):
        raise ValueError("Event manifest does not cover the analysis sample")
    return mapping


def build_monthly_table() -> pd.DataFrame:
    soda = extract_soda3()
    sst = extract_sst()
    precip = extract_gpcp()
    stress = extract_stress()
    # ERSST/GPCP/ERA5 use day 1 (with differing hours), while SODA uses day 15.
    # Year-month, rather than exact timestamp, is the physical merge key.
    sst = sst.drop(columns="time")
    precip = precip.drop(columns="time")
    stress = stress.drop(columns="time")
    merged = soda.merge(sst, on=["year", "month"], how="left")
    merged = merged.merge(precip, on=["year", "month"], how="left")
    merged = merged.merge(stress, on=["year", "month"], how="left")
    groups = event_groups()
    merged = merged.loc[merged.year.isin(EVENTS) & merged.month.isin(MONTHS)].copy()
    merged["event_year"] = merged.year.astype(int)
    merged["event_label"] = merged.event_year.map(lambda y: f"{y}/{str(y + 1)[-2:]}")
    merged["group"] = merged.event_year.map(groups)
    ordered = [
        "time",
        "event_year",
        "event_label",
        "group",
        "month",
        "central_ohc300_anom_zj",
        "east_ohc300_anom_zj",
        "central_eastward_heat_output_anom_pw",
        "east_west_boundary_heat_input_anom_pw",
        "central_sst_raw_c",
        "central_sst_anom_c",
        "east_sst_raw_c",
        "east_sst_anom_c",
        "central_precip_raw_mm_day",
        "central_precip_anom_mm_day",
        "east_precip_raw_mm_day",
        "east_precip_anom_mm_day",
        "central_taux_raw_nm2",
        "central_taux_anom_nm2",
        "east_taux_raw_nm2",
        "east_taux_anom_nm2",
    ]
    return merged[ordered].sort_values(["event_year", "month"]).reset_index(drop=True)


def build_extrema(monthly: pd.DataFrame) -> pd.DataFrame:
    definitions = {
        "central_ohc300_anom_zj": "maximum",
        "east_ohc300_anom_zj": "maximum",
        "central_eastward_heat_output_anom_pw": "maximum",
        "east_west_boundary_heat_input_anom_pw": "maximum",
        "central_sst_anom_c": "maximum",
        "east_sst_anom_c": "maximum",
        "central_precip_anom_mm_day": "maximum",
        "east_precip_anom_mm_day": "maximum",
        "central_taux_anom_nm2": "maximum",
        "east_taux_anom_nm2": "maximum",
    }
    rows: list[dict[str, object]] = []
    for event_year, event in monthly.groupby("event_year", sort=True):
        for variable, operation in definitions.items():
            values = event[variable]
            index = values.idxmax() if operation == "maximum" else values.idxmin()
            rows.append(
                {
                    "event_year": int(event_year),
                    "event_label": event.event_label.iloc[0],
                    "group": event.group.iloc[0],
                    "variable": variable,
                    "extreme": operation,
                    "month": int(monthly.loc[index, "month"]),
                    "value": float(monthly.loc[index, variable]),
                }
            )
    return pd.DataFrame(rows)


def build_mjj_means(monthly: pd.DataFrame) -> pd.DataFrame:
    variables = [
        "central_ohc300_anom_zj",
        "east_ohc300_anom_zj",
        "central_eastward_heat_output_anom_pw",
        "east_west_boundary_heat_input_anom_pw",
        "central_sst_anom_c",
        "east_sst_anom_c",
        "central_precip_anom_mm_day",
        "east_precip_anom_mm_day",
        "central_taux_anom_nm2",
        "east_taux_anom_nm2",
    ]
    selected = monthly.loc[monthly.month.between(5, 7)]
    output = (
        selected.groupby(["event_year", "event_label", "group"], as_index=False)[
            variables
        ]
        .mean()
        .sort_values("event_year")
        .reset_index(drop=True)
    )
    return output


def signed(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}"


def write_report(monthly: pd.DataFrame, mjj: pd.DataFrame) -> None:
    lines: list[str] = [
        "# Jiang事件3—10月：热量输送、海温、降水和风应力的直接比较",
        "",
        "## 分析约束",
        "",
        "- 本报告只使用已有物理量，不构造耦合指数、效率比、经验方程、阈值或人为定义的耦合形成月份。",
        "- 中箱为10°S–5°N、180°–140°W；东箱为10°S–5°N、140°W–80°W。",
        "- 海洋量来自SODA3：0–300 m OHC异常、中箱东边界向东热输出、东箱西边界热输入。",
        "- 表层量来自ERSSTv5 SST、GPCP降水和ERA5纬向表面风应力；正风应力异常表示东向/西风异常。",
        "- SODA3保留原预算中的1980—2022同月线性期望异常；ERSSTv5、GPCP和ERA5采用1982—2022同月区域线性期望异常。",
        "",
        "## 主要结果",
        "",
        "1. 2023年4—8月持续存在中箱向东热输出和东箱西边界输入；5—7月平均分别为+1.00和+1.13 PW，在全部事件中均仅次于1997。",
        "2. 2023年5—7月东箱SST异常平均+1.43°C，略高于1997的+1.41°C和2015的+1.28°C；但东箱OHC异常只有8.10 ZJ，明显低于1997的15.71 ZJ和2015的13.06 ZJ。东部表面很暖，但深层热储支撑较弱。",
        "3. 2023年5—7月中箱OHC异常只有1.34 ZJ，远低于1997的5.37 ZJ和2015的7.24 ZJ。中箱SST虽然逐月上升，但5—7月均低于1997/2015中的较强者。",
        "4. 2023年6月中箱降水异常仅+0.40 mm day⁻¹，而1997和2015分别为+4.12和+2.43；7月2023为+1.63，仍低于+2.66和+2.77。东箱降水在6—7月也同时偏弱。",
        "5. 2023年5—7月中箱东向表面风应力异常平均约+0.001 N m⁻²，显著小于1997和2015的约+0.017和+0.018 N m⁻²；直到8—9月才明显转为东向异常。",
        "6. 因而数据支持的表述是：2023年热量已经向东输送、东部SST也已升高，但中部深层热储不足，6—7月降水和中部西风响应没有同步达到1997/2015的幅度。这里描述的是变量的先后与强弱，不把它压缩为新的耦合指标。",
        "",
        "## 所有事件MJJ平均：海洋量",
        "",
        "|事件|类型|中箱OHC (ZJ)|东箱OHC (ZJ)|中箱向东输出 (PW)|东箱西侧输入 (PW)|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in mjj.itertuples(index=False):
        lines.append(
            "|"
            + "|".join(
                [
                    str(row.event_label),
                    "FEP-EP" if row.group == "2023" else str(row.group),
                    signed(float(row.central_ohc300_anom_zj)),
                    signed(float(row.east_ohc300_anom_zj)),
                    signed(float(row.central_eastward_heat_output_anom_pw), 3),
                    signed(float(row.east_west_boundary_heat_input_anom_pw), 3),
                ]
            )
            + "|"
        )

    lines.extend(
        [
            "",
            "## 所有事件MJJ平均：表层海气量",
            "",
            "|事件|中箱SST (°C)|东箱SST (°C)|中箱降水 (mm day⁻¹)|东箱降水 (mm day⁻¹)|中箱东向应力 (N m⁻²)|东箱东向应力 (N m⁻²)|",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in mjj.itertuples(index=False):
        lines.append(
            "|"
            + "|".join(
                [
                    str(row.event_label),
                    signed(float(row.central_sst_anom_c)),
                    signed(float(row.east_sst_anom_c)),
                    signed(float(row.central_precip_anom_mm_day)),
                    signed(float(row.east_precip_anom_mm_day)),
                    signed(float(row.central_taux_anom_nm2), 3),
                    signed(float(row.east_taux_anom_nm2), 3),
                ]
            )
            + "|"
        )

    for event_year in FOCUS_EVENTS:
        event = monthly.loc[monthly.event_year.eq(event_year)]
        lines.extend(
            [
                "",
                f"## {event_year}逐月：海洋量",
                "",
                "|月|中箱OHC (ZJ)|东箱OHC (ZJ)|中箱向东输出 (PW)|东箱西侧输入 (PW)|",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in event.itertuples(index=False):
            lines.append(
                "|"
                + "|".join(
                    [
                        MONTH_LABELS[int(row.month) - 3],
                        signed(float(row.central_ohc300_anom_zj)),
                        signed(float(row.east_ohc300_anom_zj)),
                        signed(float(row.central_eastward_heat_output_anom_pw), 3),
                        signed(float(row.east_west_boundary_heat_input_anom_pw), 3),
                    ]
                )
                + "|"
            )
        lines.extend(
            [
                "",
                f"## {event_year}逐月：表层海气量",
                "",
                "|月|中箱SST (°C)|东箱SST (°C)|中箱降水 (mm day⁻¹)|东箱降水 (mm day⁻¹)|中箱东向应力 (N m⁻²)|东箱东向应力 (N m⁻²)|",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in event.itertuples(index=False):
            lines.append(
                "|"
                + "|".join(
                    [
                        MONTH_LABELS[int(row.month) - 3],
                        signed(float(row.central_sst_anom_c)),
                        signed(float(row.east_sst_anom_c)),
                        signed(float(row.central_precip_anom_mm_day)),
                        signed(float(row.east_precip_anom_mm_day)),
                        signed(float(row.central_taux_anom_nm2), 3),
                        signed(float(row.east_taux_anom_nm2), 3),
                    ]
                )
                + "|"
            )

    lines.extend(
        [
            "",
            "## 逐事件观察",
            "",
            "- 1982：MJJ跨140°W输送中等，但中、东箱降水均为负异常，中箱东向应力接近零；成熟EP不等于发展期已形成强大气响应。",
            "- 1986：MJJ东传较弱，中、东箱SST和降水均为负异常，中箱应力为西向异常，属于明显较晚的发展。",
            "- 1987：跨140°W输送不强，但东箱OHC和中箱SST、降水、东向应力都较大；其表层海气状态不能仅由当期东向热输送解释。",
            "- 1991：两箱OHC均偏高、边界输送接近零；SST为正而降水偏弱，表现为热状态与对流响应不同步。",
            "- 1994：中箱东边界和东箱西边界均略呈反向，东箱SST及降水为负异常。",
            "- 1997：中箱东向输出和东箱输入最强；东箱OHC快速增加，6月以后降水与中箱东向应力同步增强，是最完整的同月演变。",
            "- 2002：有中等东传和正SST，但降水接近零或为负，应力较弱。",
            "- 2004：边界输送弱，东箱SST和降水为负，没有明显东部表层响应。",
            "- 2006：存在较弱东传，但SST、降水和应力整体接近零。",
            "- 2009：东传强度在历史事件中靠前，东箱SST为正，但降水和中箱应力仍弱；说明热量东传本身不足以保证强烈大气响应。",
            "- 2015：两箱OHC都高、东传持续，SST、降水和中箱东向应力均明显增强，但中箱应力的最大值出现在7月以后。",
            "- 2018：东传、SST、降水及应力均较弱。",
            "- 2019：跨140°W为反向异常，但中箱SST、降水和东向应力仍为正；大气状态显然还受箱外或先前条件影响。",
            "- 2023：东传仅次于1997，东箱SST很强，但两箱OHC均低于1997/2015，6—7月降水和中箱东向应力也偏弱；其特征是东部表面增暖先出现，中部大气响应较弱且较迟。",
            "",
            "## 解释边界",
            "",
            "- 上述结果是并列的时间演变证据，不把同月一致性表述成统计因果。",
            "- OHC与边界热输送来自海洋再分析，降水与风应力来自独立大气/观测资料；不同资料的空间分辨率不同，但均采用面积加权区域平均。",
            "- 中箱东边界输出与东箱西边界输入来自两个独立体积闭合箱，方向可相互验证，数值不要求完全相等。",
            "- 1987、2002、2004、2015等事件在此前完整箱体收支中有较大的未解析项，因此这里不对其垂向混合或次表层来源作额外归因。",
        ]
    )
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def add_zero(axis: plt.Axes) -> None:
    axis.axhline(0.0, color="#777777", linewidth=0.8, zorder=0)
    axis.grid(axis="y", color="#DDDDDD", linewidth=0.6)


def make_three_event_figure(monthly: pd.DataFrame) -> None:
    metrics = [
        (
            "central_ohc300_anom_zj",
            "east_ohc300_anom_zj",
            "0–300 m OHC anomaly (ZJ)",
            "OHC anomaly",
        ),
        (
            "central_eastward_heat_output_anom_pw",
            "east_west_boundary_heat_input_anom_pw",
            "Anomalous heat transport (PW)",
            "Across 140°W",
        ),
        ("central_sst_anom_c", "east_sst_anom_c", "SST anomaly (°C)", "SST"),
        (
            "central_precip_anom_mm_day",
            "east_precip_anom_mm_day",
            "Precipitation anomaly (mm day⁻¹)",
            "GPCP precipitation",
        ),
        (
            "central_taux_anom_nm2",
            "east_taux_anom_nm2",
            "Eastward surface-stress anomaly (N m⁻²)",
            "ERA5 surface stress",
        ),
    ]
    fig, axes = plt.subplots(5, 2, figsize=(13.5, 16), sharex=True)
    for row, (central_var, east_var, ylabel, row_name) in enumerate(metrics):
        for column, (variable, box_name) in enumerate(
            ((central_var, "Central box"), (east_var, "Eastern box"))
        ):
            axis = axes[row, column]
            for event_year in FOCUS_EVENTS:
                event = monthly.loc[monthly.event_year.eq(event_year)]
                axis.plot(
                    event.month,
                    event[variable],
                    marker="o",
                    markersize=4.5,
                    linewidth=2.0,
                    color=COLORS[event_year],
                    label=str(event_year),
                )
            add_zero(axis)
            axis.set_title(f"{row_name}: {box_name}", fontsize=12, weight="bold")
            if column == 0:
                axis.set_ylabel(ylabel, fontsize=10)
            axis.set_xticks(MONTHS, MONTH_LABELS)
    axes[0, 1].legend(loc="best", frameon=False, ncol=3)
    fig.suptitle(
        "1997, 2015 and 2023: direct monthly ocean–atmosphere variables",
        fontsize=18,
        weight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.975,
        "March–October; no composite coupling index. Positive stress is eastward/westerly anomaly.",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.tight_layout(rect=(0.02, 0.02, 0.995, 0.965))
    fig.savefig(THREE_EVENT_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def robust_limit(values: np.ndarray) -> float:
    finite = np.abs(np.asarray(values, dtype=float))
    finite = finite[np.isfinite(finite)]
    return float(np.nanpercentile(finite, 98.0))


def make_all_event_figure(monthly: pd.DataFrame) -> None:
    metrics = [
        ("central_ohc300_anom_zj", "east_ohc300_anom_zj", "OHC anomaly (ZJ)"),
        (
            "central_eastward_heat_output_anom_pw",
            "east_west_boundary_heat_input_anom_pw",
            "140°W heat transport anomaly (PW)",
        ),
        ("central_sst_anom_c", "east_sst_anom_c", "SST anomaly (°C)"),
        (
            "central_precip_anom_mm_day",
            "east_precip_anom_mm_day",
            "GPCP precipitation anomaly (mm day⁻¹)",
        ),
        (
            "central_taux_anom_nm2",
            "east_taux_anom_nm2",
            "ERA5 eastward stress anomaly (N m⁻²)",
        ),
    ]
    years = list(EVENTS)
    fig = plt.figure(figsize=(14.5, 20))
    grid = fig.add_gridspec(
        5,
        3,
        width_ratios=(1.0, 1.0, 0.035),
        left=0.12,
        right=0.965,
        top=0.965,
        bottom=0.04,
        hspace=0.22,
        wspace=0.10,
    )
    axes = np.empty((5, 2), dtype=object)
    for row, (central_var, east_var, unit_label) in enumerate(metrics):
        combined_values = monthly[[central_var, east_var]].to_numpy()
        limit = robust_limit(combined_values)
        norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
        images = []
        for column, (variable, box_name) in enumerate(
            ((central_var, "Central box"), (east_var, "Eastern box"))
        ):
            axis = fig.add_subplot(grid[row, column], sharex=axes[0, 0] if row else None)
            axes[row, column] = axis
            matrix = (
                monthly.pivot(index="event_year", columns="month", values=variable)
                .loc[years, list(MONTHS)]
                .to_numpy(dtype=float)
            )
            image = axis.imshow(matrix, cmap="RdBu_r", norm=norm, aspect="auto")
            images.append(image)
            axis.set_title(f"{box_name}: {unit_label}", fontsize=11.5, weight="bold")
            axis.set_xticks(np.arange(len(MONTHS)), MONTH_LABELS)
            axis.set_yticks(np.arange(len(years)))
            if column == 0:
                labels = []
                groups = []
                for year in years:
                    group = str(monthly.loc[monthly.event_year.eq(year), "group"].iloc[0])
                    labels.append(f"{year}  {'FEP-EP' if year == 2023 else group}")
                    groups.append(group)
                axis.set_yticklabels(labels, fontsize=9)
                for tick, group, year in zip(axis.get_yticklabels(), groups, years):
                    tick.set_color(GROUP_COLORS[group])
                    tick.set_weight("bold" if year == 2023 else "normal")
            else:
                axis.tick_params(axis="y", labelleft=False)
            target = years.index(2023)
            axis.add_patch(
                plt.Rectangle(
                    (-0.5, target - 0.5),
                    len(MONTHS),
                    1,
                    fill=False,
                    edgecolor=GROUP_COLORS["2023"],
                    linewidth=2.0,
                )
            )
            axis.set_xticks(np.arange(-0.5, len(MONTHS), 1), minor=True)
            axis.set_yticks(np.arange(-0.5, len(years), 1), minor=True)
            axis.grid(which="minor", color="white", linewidth=0.7)
            axis.tick_params(which="minor", bottom=False, left=False)
        colorbar_axis = fig.add_subplot(grid[row, 2])
        colorbar = fig.colorbar(images[-1], cax=colorbar_axis)
        colorbar.set_label(unit_label, fontsize=8)
        colorbar.ax.tick_params(labelsize=8)
    axes[-1, 0].set_xlabel("Developing-year month")
    axes[-1, 1].set_xlabel("Developing-year month")
    fig.suptitle(
        "Jiang-aligned events: March–October direct physical variables",
        fontsize=19,
        weight="bold",
        y=0.997,
    )
    fig.text(
        0.5,
        0.982,
        "Rows retain physical units; no coupling index or threshold is applied",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.savefig(ALL_EVENT_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def validate(monthly: pd.DataFrame) -> dict[str, object]:
    expected = len(EVENTS) * len(MONTHS)
    numeric = monthly.select_dtypes(include=[np.number])
    if len(monthly) != expected:
        raise ValueError(f"Expected {expected} event-month rows, found {len(monthly)}")
    if monthly.duplicated(["event_year", "month"]).any():
        raise ValueError("Duplicate event-month rows")
    if numeric.isna().any().any():
        missing = numeric.columns[numeric.isna().any()].tolist()
        raise ValueError(f"Missing numeric data in columns: {missing}")
    ranges = {
        column: [float(numeric[column].min()), float(numeric[column].max())]
        for column in numeric.columns
        if column not in {"event_year", "month"}
    }
    return {
        "n_rows": len(monthly),
        "n_events": int(monthly.event_year.nunique()),
        "months": list(MONTHS),
        "duplicate_event_month_rows": int(
            monthly.duplicated(["event_year", "month"]).sum()
        ),
        "numeric_nan_count": int(numeric.isna().sum().sum()),
        "ranges": ranges,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    monthly = build_monthly_table()
    diagnostics = validate(monthly)
    extrema = build_extrema(monthly)
    mjj = build_mjj_means(monthly)
    monthly.to_csv(MONTHLY_FILE, index=False, float_format="%.10g")
    extrema.to_csv(PEAK_FILE, index=False, float_format="%.10g")
    mjj.to_csv(MJJ_FILE, index=False, float_format="%.10g")
    make_three_event_figure(monthly)
    make_all_event_figure(monthly)
    write_report(monthly, mjj)
    metadata = {
        "analysis_scope": "Direct physical variables only; no new coupling index, ratio, threshold, or empirical equation.",
        "event_years": list(EVENTS),
        "focus_event_years": list(FOCUS_EVENTS),
        "developing_year_months": list(MONTHS),
        "boxes": BOXES,
        "sources": {
            "ohc_and_heat_transport": str(BUDGET_FILE),
            "sst": str(SST_FILE),
            "precipitation": str(GPCP_FILE),
            "surface_stress": str(STRESS_DIR),
        },
        "anomaly_baselines": {
            "soda3": "Existing 1980-2022 same-calendar-month linear expectation in source budget",
            "ersstv5_gpcp_era5": "1982-2022 same-calendar-month regional linear expectation",
        },
        "sign_conventions": {
            "central_eastward_heat_output_anom_pw": "positive means anomalous heat export eastward from central box",
            "east_west_boundary_heat_input_anom_pw": "positive means anomalous heat input to eastern box through its western face",
            "taux": "positive means anomalous eastward/westerly surface stress",
            "precipitation": "positive means wetter than expected",
        },
        "diagnostics": diagnostics,
    }
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {MONTHLY_FILE}")
    print(f"Wrote {PEAK_FILE}")
    print(f"Wrote {MJJ_FILE}")
    print(f"Wrote {METADATA_FILE}")
    print(f"Wrote {THREE_EVENT_FIGURE}")
    print(f"Wrote {ALL_EVENT_FIGURE}")
    print(f"Wrote {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
