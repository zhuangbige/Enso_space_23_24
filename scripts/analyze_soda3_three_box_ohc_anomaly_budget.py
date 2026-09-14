#!/usr/bin/env python3
"""Analyze a mass-balanced, fixed-depth SODA3 OHC-anomaly budget.

The calculation replaces H20/Q20 with complete 0--300 m OHC and boundary
enthalpy transports.  Calendar-month climatology and linear trends are fitted
over 1980--2022.  The total transport convergence uses a mass-balanced four-
face correction and is independent of the chosen reference temperature.
Face-level partitions are exported at 0, 10, and 20 degC so their unavoidable
reference sensitivity is visible rather than hidden.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_chakravorty2021_soda3_baseline as legacy  # noqa: E402
import fetch_soda3_three_box_enthalpy_boundary_terms as fetch  # noqa: E402


BOUNDARY_HISTORICAL = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_enthalpy_boundary_terms_1980_2022.csv"
)
BOUNDARY_EXTENSION = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_enthalpy_budget_terms_2023_2024.csv"
)
OHC_MONTHLY = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_post_arrival_three_box_ohc_monthly.csv"
)
SURFACE_HISTORICAL = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_warm_heat_budget_terms_1980_2022.csv"
)
OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_three_box_ohc_anomaly_budget"
MONTHLY_OUTPUT = OUT_DATA / "soda3_three_box_ohc_anomaly_budget_monthly.csv"
EVENT_OUTPUT = OUT_DATA / "soda3_three_box_ohc_anomaly_budget_events.csv"
REFERENCE_OUTPUT = (
    OUT_DATA / "soda3_three_box_ohc_anomaly_face_reference_sensitivity.csv"
)
DIAGNOSTICS_OUTPUT = (
    OUT_DATA / "soda3_three_box_ohc_anomaly_budget_diagnostics.json"
)
REPORT_OUTPUT = OUT_DIR / "SODA3_THREE_BOX_OHC_ANOMALY_BUDGET_CN.md"
LAGRANGIAN_SUMMARY = (
    OUT_DATA / "soda3_temp_anomaly_lagrangian_pilot_summary.csv"
)
COUPLING_CHAIN = OUT_DATA / "soda3_ohc_only_three_event_coupling_chain.csv"

BOXES = tuple(fetch.BOXES)
OHC_BOXES = {"west": "西箱", "central": "中箱", "east": "东箱"}
FACES = fetch.FACE_NAMES
REFERENCES_C = (0.0, 10.0, 20.0)
BASELINE = (1980, 2022)
EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHT_EVENTS = (1997, 2015, 2023)
PHASES = {
    "arrival_Jan_Jun": (0, 1, 6),
    "post_Jul_Dec": (0, 7, 12),
    "decay_Jan_May_next": (1, 1, 5),
}


def centered_storage_tendency_pw(
    storage_zj: np.ndarray, times: pd.DatetimeIndex
) -> np.ndarray:
    values = np.asarray(storage_zj, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    seconds = (times[2:] - times[:-2]).total_seconds().to_numpy(dtype=float)
    output[1:-1] = (values[2:] - values[:-2]) * 1.0e6 / seconds
    return output


def same_month_detrended(values: np.ndarray, times: pd.DatetimeIndex) -> np.ndarray:
    return legacy.same_month_detrended(values, times, BASELINE)


def same_month_expected(values: np.ndarray, times: pd.DatetimeIndex) -> np.ndarray:
    """Return the calendar-month linear expectation fitted in BASELINE."""
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in range(1, 13):
        selected = (
            (times.month == month)
            & np.isfinite(values)
            & (times.year >= BASELINE[0])
            & (times.year <= BASELINE[1])
        )
        if selected.sum() < 3:
            continue
        years = times.year[selected].astype(float)
        design = np.column_stack([np.ones(selected.sum()), years])
        intercept, slope = np.linalg.lstsq(design, values[selected], rcond=None)[0]
        apply = (times.month == month) & np.isfinite(values)
        output[apply] = intercept + slope * times.year[apply].astype(float)
    return output


def smooth3(values: np.ndarray) -> np.ndarray:
    return (
        pd.Series(np.asarray(values, dtype=float))
        .rolling(3, center=True, min_periods=3)
        .mean()
        .to_numpy()
    )


def reference_heat_pw(
    heat0_pw: np.ndarray, volume_sv: np.ndarray, reference_c: float | np.ndarray
) -> np.ndarray:
    return np.asarray(heat0_pw, dtype=float) - (
        fetch.RHO0_KG_M3
        * fetch.CP0_J_KG_K
        * reference_c
        * np.asarray(volume_sv, dtype=float)
        * 1.0e6
        / 1.0e15
    )


def load_raw() -> pd.DataFrame:
    boundary = pd.read_csv(BOUNDARY_HISTORICAL, parse_dates=["time"])
    if BOUNDARY_EXTENSION.exists():
        extension = pd.read_csv(BOUNDARY_EXTENSION, parse_dates=["time"])
        boundary = pd.concat([boundary, extension], ignore_index=True)
        boundary = boundary.drop_duplicates("time", keep="last")
    boundary = boundary.sort_values("time").reset_index(drop=True)
    # The annual extension also carries surface fluxes for convenience.  Drop
    # them here so the dedicated surface merge below has one unsuffixed source.
    boundary = boundary.drop(
        columns=[f"{box}_surface_all_pw" for box in BOXES], errors="ignore"
    )

    surface = pd.read_csv(SURFACE_HISTORICAL, parse_dates=["time"])[
        ["time", *[f"{box}_surface_all_pw" for box in BOXES]]
    ]
    if BOUNDARY_EXTENSION.exists():
        extension_surface = pd.read_csv(
            BOUNDARY_EXTENSION, parse_dates=["time"]
        )[["time", *[f"{box}_surface_all_pw" for box in BOXES]]]
        surface = pd.concat([surface, extension_surface], ignore_index=True)
        surface = surface.drop_duplicates("time", keep="last")

    ohc_long = pd.read_csv(OHC_MONTHLY, parse_dates=["time"])
    ohc = ohc_long.pivot(
        index="time", columns="box", values="ohc300_abs_zj"
    ).reset_index()
    ohc = ohc.rename(columns={label: f"{box}_ohc300_abs_zj" for box, label in OHC_BOXES.items()})

    output = boundary.merge(surface, on="time", how="inner", validate="one_to_one")
    output = output.merge(ohc, on="time", how="inner", validate="one_to_one")
    output = output.sort_values("time").reset_index(drop=True)
    output["year"] = output.time.dt.year
    output["month"] = output.time.dt.month
    expected = pd.date_range(output.time.min().replace(day=1), output.time.max().replace(day=1), freq="MS") + pd.Timedelta(days=14)
    if not pd.DatetimeIndex(output.time).equals(expected):
        raise ValueError("Merged budget has an incomplete monthly axis")
    return output


def build_monthly(raw: pd.DataFrame) -> pd.DataFrame:
    output = raw.copy()
    times = pd.DatetimeIndex(output["time"])
    for box in BOXES:
        storage_anomaly = same_month_detrended(
            output[f"{box}_ohc300_abs_zj"].to_numpy(), times
        )
        output[f"{box}_ohc300_anom_zj"] = storage_anomaly
        tendency = centered_storage_tendency_pw(
            output[f"{box}_ohc300_abs_zj"].to_numpy(), times
        )
        output[f"{box}_storage_tendency_pw"] = tendency
        west_gate = int(fetch.BOXES[box][0])
        east_gate = int(fetch.BOXES[box][1])
        face_temperature_area = {
            "west": output[f"gate_{west_gate}e_temperature_area_cm2"].to_numpy(),
            "east": output[f"gate_{east_gate}e_temperature_area_cm2"].to_numpy(),
            "south": output[f"{box}_south_temperature_area_cm2"].to_numpy(),
            "north": output[f"{box}_north_temperature_area_cm2"].to_numpy(),
        }
        face_area = {
            "west": output[f"gate_{west_gate}e_area_m2"].to_numpy(),
            "east": output[f"gate_{east_gate}e_area_m2"].to_numpy(),
            "south": output[f"{box}_south_area_m2"].to_numpy(),
            "north": output[f"{box}_north_area_m2"].to_numpy(),
        }
        boundary_mean_temperature = sum(face_temperature_area.values()) / sum(
            face_area.values()
        )
        expected_boundary_temperature = same_month_expected(
            boundary_mean_temperature, times
        )
        output[f"{box}_boundary_mean_temperature_c"] = boundary_mean_temperature
        output[f"{box}_expected_boundary_temperature_c"] = (
            expected_boundary_temperature
        )
        for face in FACES:
            heat0 = output[f"{box}_{face}_heat0_in_corr_pw"].to_numpy()
            volume = output[f"{box}_{face}_volume_in_corr_sv"].to_numpy()
            theta = reference_heat_pw(
                heat0, volume, expected_boundary_temperature
            )
            theta_anomaly = same_month_detrended(theta, times)
            output[f"{box}_{face}_theta_heat_in_corr_pw"] = theta
            output[f"{box}_{face}_theta_heat_in_corr_anom_pw"] = theta_anomaly
            output[f"{box}_{face}_theta_heat_in_corr_sm3_pw"] = smooth3(
                theta_anomaly
            )
            for reference in REFERENCES_C:
                tag = int(reference)
                absolute = reference_heat_pw(heat0, volume, reference)
                output[f"{box}_{face}_heat{tag}_in_corr_pw"] = absolute
                anomaly = same_month_detrended(absolute, times)
                output[f"{box}_{face}_heat{tag}_in_corr_anom_pw"] = anomaly
                output[f"{box}_{face}_heat{tag}_in_corr_sm3_pw"] = smooth3(anomaly)

        convergence0 = output[f"{box}_heat0_convergence_corr_pw"].to_numpy()
        convergence_anom = same_month_detrended(convergence0, times)
        theta_sum = sum(
            output[f"{box}_{face}_theta_heat_in_corr_pw"] for face in FACES
        )
        # CSV checkpoint rounding leaves O(1e-9 PW) cancellation noise when
        # four large face transports are re-summed.
        if np.nanmax(np.abs(theta_sum - convergence0)) > 1.0e-7:
            raise ValueError(f"Theta face partition does not sum for {box}")
        theta_anomaly_sum = sum(
            output[f"{box}_{face}_theta_heat_in_corr_anom_pw"] for face in FACES
        )
        if np.nanmax(np.abs(theta_anomaly_sum - convergence_anom)) > 1.0e-7:
            raise ValueError(f"Theta anomaly partition does not sum for {box}")
        storage_anom = same_month_detrended(tendency, times)
        surface_anom = same_month_detrended(
            output[f"{box}_surface_all_pw"].to_numpy(), times
        )
        output[f"{box}_transport_convergence_anom_pw"] = convergence_anom
        output[f"{box}_storage_tendency_anom_pw"] = storage_anom
        output[f"{box}_surface_anom_pw"] = surface_anom
        output[f"{box}_residual_anom_pw"] = (
            storage_anom - convergence_anom - surface_anom
        )
        for component in (
            "transport_convergence",
            "storage_tendency",
            "surface",
            "residual",
        ):
            output[f"{box}_{component}_sm3_pw"] = smooth3(
                output[f"{box}_{component}_anom_pw"].to_numpy()
            )

        reconstructed = (
            output[f"{box}_transport_convergence_anom_pw"]
            + output[f"{box}_surface_anom_pw"]
            + output[f"{box}_residual_anom_pw"]
        )
        error = output[f"{box}_storage_tendency_anom_pw"] - reconstructed
        if np.nanmax(np.abs(error)) > 1.0e-12:
            raise ValueError(f"Anomaly budget does not close for {box}")
    return output


def integrate_zj(values_pw: pd.Series, times: pd.Series) -> float:
    timestamps = pd.DatetimeIndex(times)
    values = values_pw.to_numpy(dtype=float)
    if len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("Phase integration requires at least two finite values")
    seconds = (timestamps - timestamps[0]).total_seconds().to_numpy(dtype=float)
    return float(np.trapezoid(values, x=seconds) / 1.0e6)


def build_event_tables(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, float | int | str]] = []
    reference_rows: list[dict[str, float | int | str]] = []
    for event in EVENTS:
        for phase, (year_offset, month0, month1) in PHASES.items():
            target_year = event + year_offset
            selected = monthly.loc[
                monthly.year.eq(target_year)
                & monthly.month.between(month0, month1)
            ]
            if len(selected) != month1 - month0 + 1:
                continue
            for box in BOXES:
                record: dict[str, float | int | str] = {
                    "event_year": event,
                    "target_year": target_year,
                    "phase": phase,
                    "box": box,
                    "month_start": month0,
                    "month_end": month1,
                }
                record["storage_change_zj"] = float(
                    selected[f"{box}_ohc300_anom_zj"].iloc[-1]
                    - selected[f"{box}_ohc300_anom_zj"].iloc[0]
                )
                record["transport_convergence_zj"] = integrate_zj(
                    selected[f"{box}_transport_convergence_anom_pw"],
                    selected["time"],
                )
                record["surface_zj"] = integrate_zj(
                    selected[f"{box}_surface_anom_pw"], selected["time"]
                )
                record["residual_zj"] = (
                    float(record["storage_change_zj"])
                    - float(record["transport_convergence_zj"])
                    - float(record["surface_zj"])
                )
                record["monthly_residual_integral_zj"] = integrate_zj(
                    selected[f"{box}_residual_anom_pw"], selected["time"]
                )
                for face in FACES:
                    record[f"{face}_heat_in_zj_ref0"] = integrate_zj(
                        selected[f"{box}_{face}_heat0_in_corr_anom_pw"],
                        selected["time"],
                    )
                    record[f"{face}_theta_heat_in_zj"] = integrate_zj(
                        selected[f"{box}_{face}_theta_heat_in_corr_anom_pw"],
                        selected["time"],
                    )
                record["northward_output_zj"] = -float(
                    record["north_theta_heat_in_zj"]
                )
                record["southward_output_zj"] = -float(
                    record["south_theta_heat_in_zj"]
                )
                record["surface_loss_zj"] = -float(record["surface_zj"])
                rows.append(record)

                for reference in REFERENCES_C:
                    tag = int(reference)
                    ref_record: dict[str, float | int | str] = {
                        "event_year": event,
                        "target_year": target_year,
                        "phase": phase,
                        "box": box,
                        "reference_c": reference,
                    }
                    face_sum = 0.0
                    for face in FACES:
                        value = integrate_zj(
                            selected[f"{box}_{face}_heat{tag}_in_corr_anom_pw"],
                            selected["time"],
                        )
                        ref_record[f"{face}_heat_in_zj"] = value
                        face_sum += value
                    ref_record["transport_convergence_zj"] = face_sum
                    reference_rows.append(ref_record)
    return pd.DataFrame(rows), pd.DataFrame(reference_rows)


def diagnostics(monthly: pd.DataFrame, reference: pd.DataFrame) -> dict[str, object]:
    result: dict[str, object] = {
        "time_start": str(monthly.time.min().date()),
        "time_end": str(monthly.time.max().date()),
        "baseline": list(BASELINE),
        "events_available": sorted(
            int(year) for year in set(EVENTS) & set(monthly.year.unique())
        ),
        "budget_definition": "dOHC'/dt = corrected boundary enthalpy convergence' + surface heat flux' + residual'",
    }
    for box in BOXES:
        result[f"{box}_max_corrected_volume_error_sv"] = float(
            monthly[f"{box}_volume_convergence_corr_sv"].abs().max()
        )
        result[f"{box}_max_mass_correction_m_s"] = float(
            monthly[f"{box}_mass_correction_m_s"].abs().max()
        )
        if not reference.empty:
            spread = (
                reference.loc[reference.box.eq(box)]
                .groupby(["event_year", "phase"])["transport_convergence_zj"]
                .agg(lambda values: float(values.max() - values.min()))
            )
            result[f"{box}_max_total_reference_spread_zj"] = float(spread.max())
    return result


def write_report(events: pd.DataFrame, diag: dict[str, object]) -> None:
    lines = [
        "# SODA3 三箱固定层 OHC′ 预算（不用 H20）",
        "",
        "## 试验定义",
        "",
        "- 三个科学问题保持不变；这里只替换状态量和输送量。",
        "- 储存量：10°S–5°N、0–300 m 的完整 OHC′。",
        "- 边界量：四边完整焓输送，并对每个箱施加均匀法向速度修正，使净体积输送为零。",
        "- 海表量：完整净海表热通量，不再用 T>20°C 门控。",
        "- 残差：垂向/混合/扩散/同化增量与离散误差的合计，不能直接解释成单一物理过程。",
        "",
        "## 数值检查",
        "",
        f"- 时间范围：{diag['time_start']} 至 {diag['time_end']}；异常基准为 1980–2022 同月线性期望。",
    ]
    for box in BOXES:
        lines.append(
            f"- {box}：最大体积闭合误差 {diag[f'{box}_max_corrected_volume_error_sv']:.2e} Sv；"
            f"最大修正速度 {diag[f'{box}_max_mass_correction_m_s']:.4f} m s⁻¹；"
            f"总输送的 0/10/20°C 参考温度跨度 {diag.get(f'{box}_max_total_reference_spread_zj', float('nan')):.2e} ZJ。"
        )
    lines += [
        "",
        "## 三问题中的位置",
        "",
        "1. 问题一继续由无 H20 的 T′ 拉格朗日连通性回答；本预算的 140°W 西边界异常焓输入提供欧拉交叉验证。",
        "2. 问题二由东箱 Jul–Dec 与 Jan(+1)–May(+1) 的西/东/南/北边界、海表损失、储存变化和残差共同回答。",
        "3. 问题三仍需把这些暖量命运项与风应力、SLP、降水/OLR 等耦合演变相连；本预算只提供海洋侧被解释量。",
    ]
    if not events.empty:
        lines += ["", "## 事件积分（异常量，ZJ）", ""]
        for phase, label in (
            ("post_Jul_Dec", "Jul–Dec"),
            ("decay_Jan_May_next", "Jan(+1)–May(+1)"),
        ):
            east_post = events.loc[
                events.box.eq("east")
                & events.phase.eq(phase)
                & events.event_year.isin(HIGHLIGHT_EVENTS)
            ]
            for row in east_post.itertuples(index=False):
                lines.append(
                    f"- {row.event_year} 东箱 {label}：储存变化 {row.storage_change_zj:+.2f}，"
                    f"北向输出 {row.northward_output_zj:+.2f}，"
                    f"南向输出 {row.southward_output_zj:+.2f}，"
                    f"海表损失 {row.surface_loss_zj:+.2f}，残差 {row.residual_zj:+.2f}。"
                )
        lines += ["", "## 试验后对三个问题的更新", ""]
        arrival = events.loc[
            events.box.eq("east") & events.phase.eq("arrival_Jan_Jun")
        ].set_index("event_year")
        decay = events.loc[
            events.box.eq("east") & events.phase.eq("decay_Jan_May_next")
        ].set_index("event_year")
        if LAGRANGIAN_SUMMARY.exists():
            trajectories = pd.read_csv(LAGRANGIAN_SUMMARY).set_index("event")
            displacement = "/".join(
                f"{trajectories.loc[event, 'weighted_median_eastward_displacement_deg']:.1f}°"
                for event in HIGHLIGHT_EVENTS
            )
        else:
            displacement = "未读取"
        lines += [
            "### 问题一：是否到达、从哪里来？",
            "",
            f"- 1997/2015/2023 的正 T′ 粒子加权中位东向位移依次为 {displacement}；方向在垂向速度敏感性中保持为正。",
            "- 同一三例 Jan中–Jun中跨 140°W 进入东箱的动态参考异常焓分别为 "
            + "/".join(f"{arrival.loc[event, 'west_theta_heat_in_zj']:.2f}" for event in HIGHLIGHT_EVENTS)
            + " ZJ，东箱 OHC′ 增量分别为 "
            + "/".join(f"{arrival.loc[event, 'storage_change_zj']:.2f}" for event in HIGHLIGHT_EVENTS)
            + " ZJ。欧拉和拉格朗日证据都支持到达，但 1997 最强，2023 的到达不等于同等强的盆地深层支撑。",
            "",
            "### 问题二：到达后去了哪里？",
            "",
        ]
        for event in HIGHLIGHT_EVENTS:
            row = decay.loc[event]
            lines.append(
                f"- {event} Jan(+1)–May(+1)：东箱 OHC′ 减少 {-row.storage_change_zj:.2f} ZJ；"
                f"向西返回 {-row.west_theta_heat_in_zj:.2f}、北向输出 {row.northward_output_zj:.2f}、"
                f"南向输出 {row.southward_output_zj:.2f}、海表损失 {row.surface_loss_zj:.2f} ZJ；"
                f"闭合残差为 {row.residual_zj:+.2f} ZJ。"
            )
        lines += [
            "- 三例最大的已识别水平损失项都是向西返回，而不是5°N北向输出。北向输出与海表损失仍保持1997>2015>2023，但2023在完整OHC′意义下只是偏弱，并非近零。",
            "- 因而原H20结论要加限定：‘2023出口近闭合’只适用于20°C以上暖核；固定层总异常焓仍跨5°N输出。阈值与非阈值结果的共同稳健部分是排序，不是绝对开/闭标签。",
            "",
            "### 问题三：为什么相似FEP先暖会有不同命运？",
            "",
        ]
        if COUPLING_CHAIN.exists():
            chain = pd.read_csv(COUPLING_CHAIN).set_index("year")
            lines += [
                "- 既有独立耦合链中，1997/2015/2023 的5°N向西风应力异常为 "
                + "/".join(f"{chain.loc[event, 'tau5n_westward_mean_nm2']:.4f}" for event in HIGHLIGHT_EVENTS)
                + " N m⁻²；本次无H20北向输出同样依次减弱。",
                f"- 2023 的最弱标准化环节仍是 {chain.loc[2023, 'weakest_chain_link']}（{chain.loc[2023, 'weakest_chain_residual_z']:+.2f}σ），"
                "而1997/2015具有更强的次表层预置和风应力接通。新预算支持‘耦合强弱改变分配比例’，但没有把相关关系升级成单向因果。",
            ]
        lines += [
            "",
            "## 从Jiang等北太平洋海洋热浪预印本借鉴的组织方式",
            "",
            "[该预印本](https://doi.org/10.21203/rs.3.rs-7762242/v1)用三维粒子热预算拆分南北组分，并把风驱输送、海表热损失、SLP异常和SST反馈放在同一闭环中。当前三问可借鉴三点：",
            "",
            "1. 路径与收支分开但必须对接：粒子回答‘哪批暖异常到达’，闭合箱体回答‘到达后各项如何分配’。",
            "2. 区分建立与维持/衰减：Jan–Jun、Jul–Dec、Jan(+1)–May(+1)不再混成一个事件平均。",
            "3. 第三问用反馈环而非单向箭头：大气环流改变风驱输送和散热，SST/OHC状态又可能反作用于SLP/对流；本项目当前只有观测诊断和离线换风，尚未达到预印本式守恒拉格朗日热预算或耦合反事实。",
        ]
    lines += [
        "",
        "## 解释边界",
        "",
        "事件表的单边主值使用四边共用的“该箱同月预期边界温度”作为动态参考；因修正后四边净体积输送为零，这些主值之和严格等于总焓收敛，且不依赖摄氏温标零点。常规 0/10/20°C 单边值另表保留，用于展示其参考温度依赖，不能作为主结论。",
        "",
    ]
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    raw = load_raw()
    monthly = build_monthly(raw)
    events, reference = build_event_tables(monthly)
    diag = diagnostics(monthly, reference)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_OUTPUT, index=False, float_format="%.10g")
    events.to_csv(EVENT_OUTPUT, index=False, float_format="%.10g")
    reference.to_csv(REFERENCE_OUTPUT, index=False, float_format="%.10g")
    DIAGNOSTICS_OUTPUT.write_text(
        json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(events, diag)
    print(f"Wrote {MONTHLY_OUTPUT} ({len(monthly)} rows)")
    print(f"Wrote {EVENT_OUTPUT} ({len(events)} rows)")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
