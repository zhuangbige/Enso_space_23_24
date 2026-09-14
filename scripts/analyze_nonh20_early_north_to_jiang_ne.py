#!/usr/bin/env python3
"""Test whether early fixed-layer northward heat routing precedes Jiang NE winds.

The predictor is the mass-balanced 0--300 m anomalous-enthalpy transport
leaving the eastern equatorial Pacific across 5N.  January--March (JFM) is
the primary strictly leading window; January--April (JFMA) is a sensitivity
window.  The atmospheric target is the May--July Jiang-box northeasterly
residual.  No H20 or Q20 quantity is used in the calculation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/nonh20_early_north_to_jiang"

BUDGET_MONTHLY = DATA / "soda3_three_box_ohc_anomaly_budget_monthly.csv"
JIANG_EVENTS = DATA / "jiang_ne_wind_h20_exit_event_table.csv"
BRIDGE_EVENTS = DATA / "enso_ne_wind_bridge_event_indices.csv"
ATMOS_EVENTS = DATA / "h20_outflow_ne_feedback_event_table.csv"
EARLY_NE_MONTHLY = DATA / "era5_jiang_ne850_monthly_1982_2024_jan_jul.csv"
PROCESS_MONTHLY = DATA / "soda3_ohc_only_monthly_1980_2024.csv"

EVENT_OUTPUT = DATA / "nonh20_early_north_to_jiang_event_table.csv"
RELATION_OUTPUT = DATA / "nonh20_early_north_to_jiang_relationships.csv"
DIAGNOSTICS_OUTPUT = DATA / "nonh20_early_north_to_jiang_diagnostics.json"
REPORT_OUTPUT = OUT / "NONH20_EARLY_NORTH_TO_JIANG_CN.md"

EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = (1997, 2015, 2023)
WINDOWS = {"JFM": (1, 2, 3), "JFMA": (1, 2, 3, 4), "FMA": (2, 3, 4)}
N_PERMUTATIONS = 20_000
N_BOOTSTRAP = 10_000
RANDOM_SEED = 20260811


def integrate_zj(frame: pd.DataFrame, column: str) -> float:
    times = pd.DatetimeIndex(frame["time"])
    if len(times) < 2 or not times.is_monotonic_increasing:
        raise ValueError("Integration window must contain ordered monthly samples")
    seconds = (times - times[0]).total_seconds().to_numpy(dtype=float)
    values = frame[column].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"Non-finite values in {column}")
    return float(np.trapezoid(values, x=seconds) / 1.0e6)


def residualize(values: np.ndarray, controls: np.ndarray | None) -> np.ndarray:
    y = np.asarray(values, dtype=float)
    if controls is None or np.asarray(controls).size == 0:
        return y - float(np.mean(y))
    x = np.asarray(controls, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    design = np.column_stack([np.ones(len(y)), x])
    return y - design @ np.linalg.lstsq(design, y, rcond=None)[0]


def correlation(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.corrcoef(np.asarray(x, dtype=float), np.asarray(y, dtype=float))[0, 1])


def build_early_ne() -> pd.DataFrame:
    """Reproduce the Jiang residual definition for January--April NE850."""
    frame = pd.read_csv(EARLY_NE_MONTHLY, parse_dates=["time"])
    frame["ne850_ad_ms"] = np.nan
    for _, group in frame.groupby("month"):
        values = group["ne850_jiang_box_ms"].to_numpy(dtype=float)
        anomaly = values - float(np.mean(values))
        x = group["year"].to_numpy(dtype=float)
        x = x - float(np.mean(x))
        anomaly = anomaly - x * float(np.sum(x * anomaly) / np.sum(x**2))
        frame.loc[group.index, "ne850_ad_ms"] = anomaly

    frame["ne850_residual_ms"] = np.nan
    for _, group in frame.groupby("month"):
        design = np.column_stack(
            [
                np.ones(len(group)),
                group["year"].to_numpy(dtype=float) - 2003.0,
                group["nino34_raw_c"].to_numpy(dtype=float),
                group["sst_type_raw_c"].to_numpy(dtype=float),
            ]
        )
        values = group["ne850_ad_ms"].to_numpy(dtype=float)
        frame.loc[group.index, "ne850_residual_ms"] = (
            values - design @ np.linalg.lstsq(design, values, rcond=None)[0]
        )
    return frame


def build_early_stress() -> pd.DataFrame:
    """Calendar-month detrended local 5N westward stress, 1980--2022 baseline."""
    frame = pd.read_csv(PROCESS_MONTHLY, parse_dates=["time"])
    frame["tau5n_ad_nm2"] = np.nan
    for _, group in frame.groupby("month"):
        baseline = group.loc[group["year"].between(1980, 2022)]
        design = np.column_stack(
            [np.ones(len(baseline)), baseline["year"].to_numpy(dtype=float)]
        )
        coefficients = np.linalg.lstsq(
            design,
            baseline["tau5n_westward_raw_nm2"].to_numpy(dtype=float),
            rcond=None,
        )[0]
        apply = np.column_stack(
            [np.ones(len(group)), group["year"].to_numpy(dtype=float)]
        )
        frame.loc[group.index, "tau5n_ad_nm2"] = (
            group["tau5n_westward_raw_nm2"].to_numpy(dtype=float)
            - apply @ coefficients
        )
    return frame


def build_event_table() -> pd.DataFrame:
    monthly = pd.read_csv(BUDGET_MONTHLY, parse_dates=["time"])
    early_ne = build_early_ne()
    early_stress = build_early_stress()
    rows: list[dict[str, float | int]] = []
    for event in EVENTS:
        row: dict[str, float | int] = {"year": event}
        for label, months in WINDOWS.items():
            key = label.lower()
            selected = monthly.loc[
                monthly["year"].eq(event) & monthly["month"].isin(months)
            ].sort_values("time")
            if len(selected) != len(months):
                raise ValueError(f"Incomplete {label} fixed-layer budget for {event}")
            row[f"north_output_{key}_zj"] = -integrate_zj(
                selected, "east_north_theta_heat_in_corr_anom_pw"
            )
            row[f"arrival_140w_{key}_zj"] = integrate_zj(
                selected, "east_west_theta_heat_in_corr_anom_pw"
            )
            wind = early_ne.loc[
                early_ne["year"].eq(event) & early_ne["month"].isin(months)
            ]
            stress = early_stress.loc[
                early_stress["year"].eq(event) & early_stress["month"].isin(months)
            ]
            row[f"early_ne850_{key}_ms"] = float(wind["ne850_residual_ms"].mean())
            row[f"early_tau5n_{key}_nm2"] = float(stress["tau5n_ad_nm2"].mean())
        rows.append(row)

    table = pd.DataFrame(rows)
    jiang = pd.read_csv(JIANG_EVENTS)[
        ["year", "ne925_mjj_ms", "ne850_mjj"]
    ]
    bridge = pd.read_csv(BRIDGE_EVENTS)[
        [
            "year",
            "ne850_mjj_z",
            "fep_residual_mjj_z",
            "d140_mar_apr_z",
            "east_ocean_state_z_z",
            "precip_dipole_mjj_z",
            "tau_response_mjj_z",
        ]
    ]
    # This source file also contains legacy warm-threshold columns, but only
    # independent OISST/precipitation/SLP diagnostics are selected here.
    atmosphere = pd.read_csv(ATMOS_EVENTS)[
        [
            "year",
            "sst_north_mjj_c",
            "sst_eq_minus_north_mjj_c",
            "precip_north_mjj_mmday",
            "precip_dipole_mjj_mmday",
            "slp_gradient_mjj_hpa",
        ]
    ]
    table = table.merge(jiang, on="year", validate="one_to_one")
    table = table.merge(bridge, on="year", validate="one_to_one")
    table = table.merge(atmosphere, on="year", validate="one_to_one")
    table = table.sort_values("year").reset_index(drop=True)
    if tuple(table["year"]) != EVENTS or table.isna().any().any():
        raise ValueError("Incomplete merged 13-event table")
    return table


def relationship(
    table: pd.DataFrame,
    *,
    test_id: str,
    label: str,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...],
    seed: int,
) -> dict[str, object]:
    x = table[x_name].to_numpy(dtype=float)
    y = table[y_name].to_numpy(dtype=float)
    control = table[list(controls)].to_numpy(dtype=float) if controls else None
    xr = residualize(x, control)
    yr = residualize(y, control)
    observed = correlation(xr, yr)
    rank_r = correlation(pd.Series(xr).rank().to_numpy(), pd.Series(yr).rank().to_numpy())

    rng = np.random.default_rng(seed)
    permutations = np.empty(N_PERMUTATIONS)
    for index in range(N_PERMUTATIONS):
        permutations[index] = correlation(xr, rng.permutation(yr))
    permutation_p = float(
        (np.sum(np.abs(permutations) >= abs(observed)) + 1)
        / (N_PERMUTATIONS + 1)
    )

    bootstrap = np.full(N_BOOTSTRAP, np.nan)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(table), len(table))
        sampled_control = control[sample] if control is not None else None
        bootstrap[index] = correlation(
            residualize(x[sample], sampled_control),
            residualize(y[sample], sampled_control),
        )
    finite = bootstrap[np.isfinite(bootstrap)]
    low, high = np.percentile(finite, [2.5, 97.5])

    loeo = []
    for omitted in range(len(table)):
        keep = np.arange(len(table)) != omitted
        kept_control = control[keep] if control is not None else None
        loeo.append(
            correlation(
                residualize(x[keep], kept_control),
                residualize(y[keep], kept_control),
            )
        )
    return {
        "test_id": test_id,
        "label": label,
        "x": x_name,
        "y": y_name,
        "controls": "+".join(controls) if controls else "none",
        "n_events": len(table),
        "partial_r": observed,
        "partial_spearman_r": rank_r,
        "permutation_p": permutation_p,
        "bootstrap_ci_low": float(low),
        "bootstrap_ci_high": float(high),
        "loeo_min_r": float(np.min(loeo)),
        "loeo_max_r": float(np.max(loeo)),
    }


def build_relationships(table: pd.DataFrame) -> pd.DataFrame:
    specs = [
        (
            "jfm_north_to_ne925",
            "JFM north output -> MJJ NE925 at fixed JFM arrival",
            "north_output_jfm_zj",
            "ne925_mjj_ms",
            ("arrival_140w_jfm_zj",),
        ),
        (
            "jfm_north_to_ne850",
            "JFM north output -> MJJ NE850 at fixed JFM arrival",
            "north_output_jfm_zj",
            "ne850_mjj_z",
            ("arrival_140w_jfm_zj",),
        ),
        (
            "jfm_north_to_ne850_early_atmos",
            "JFM north output -> MJJ NE850 beyond early NE and stress",
            "north_output_jfm_zj",
            "ne850_mjj_z",
            (
                "arrival_140w_jfm_zj",
                "early_ne850_jfm_ms",
                "early_tau5n_jfm_nm2",
            ),
        ),
        (
            "jfm_north_to_ne850_fep",
            "JFM north output -> MJJ NE850 at fixed arrival and FEP",
            "north_output_jfm_zj",
            "ne850_mjj_z",
            ("arrival_140w_jfm_zj", "fep_residual_mjj_z"),
        ),
        (
            "jfm_north_to_ne850_d140",
            "JFM north output -> MJJ NE850 at fixed arrival and D140",
            "north_output_jfm_zj",
            "ne850_mjj_z",
            ("arrival_140w_jfm_zj", "d140_mar_apr_z"),
        ),
        (
            "jfm_north_to_ne850_east_state",
            "JFM north output -> MJJ NE850 at fixed arrival and east state",
            "north_output_jfm_zj",
            "ne850_mjj_z",
            ("arrival_140w_jfm_zj", "east_ocean_state_z_z"),
        ),
        (
            "jfma_north_to_ne850",
            "JFMA north output -> MJJ NE850 at fixed JFMA arrival",
            "north_output_jfma_zj",
            "ne850_mjj_z",
            ("arrival_140w_jfma_zj",),
        ),
        (
            "jfm_north_to_north_sst",
            "JFM north output -> MJJ north SST",
            "north_output_jfm_zj",
            "sst_north_mjj_c",
            ("arrival_140w_jfm_zj",),
        ),
        (
            "jfm_north_to_rain_dipole",
            "JFM north output -> MJJ precipitation dipole",
            "north_output_jfm_zj",
            "precip_dipole_mjj_z",
            ("arrival_140w_jfm_zj",),
        ),
        (
            "jfm_north_to_slp_gradient",
            "JFM north output -> MJJ north-minus-equator SLP",
            "north_output_jfm_zj",
            "slp_gradient_mjj_hpa",
            ("arrival_140w_jfm_zj",),
        ),
        (
            "jfm_north_to_tau_response",
            "JFM north output -> MJJ central zonal-stress response",
            "north_output_jfm_zj",
            "tau_response_mjj_z",
            ("arrival_140w_jfm_zj",),
        ),
    ]
    rows = [
        relationship(
            table,
            test_id=test_id,
            label=label,
            x_name=x_name,
            y_name=y_name,
            controls=controls,
            seed=RANDOM_SEED + index * 101,
        )
        for index, (test_id, label, x_name, y_name, controls) in enumerate(specs)
    ]
    return pd.DataFrame(rows)


def write_report(table: pd.DataFrame, relationships: pd.DataFrame) -> None:
    rel = relationships.set_index("test_id")
    cases = table.set_index("year").loc[list(HIGHLIGHTS)]

    def line(test_id: str) -> str:
        row = rel.loc[test_id]
        return (
            f"r={row.partial_r:+.2f}，置换p={row.permutation_p:.3f}，"
            f"bootstrap 95%区间[{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]，"
            f"留一范围[{row.loeo_min_r:+.2f}, {row.loeo_max_r:+.2f}]"
        )

    lines = [
        "# 早期北向异常焓输出是否衔接Jiang型东北风",
        "",
        "## 结论",
        "",
        "固定0—300 m、质量守恒的异常焓预算支持一条值得保留的海洋先行路径：发展年1—3月从东部赤道箱跨5°N的北向输出越强，随后5—7月Jiang区东北风异常越强。该关系不是由2023单点或早期风持续性单独造成，但D140控制会明显削弱关系，因此目前只能称领先观测证据，不能称已经闭合的因果机制。",
        "",
        "## 主要检验",
        "",
        f"- JFM北向输出→MJJ NE925，控制JFM 140°W到达：{line('jfm_north_to_ne925')}。",
        f"- JFM北向输出→MJJ NE850，控制JFM 140°W到达：{line('jfm_north_to_ne850')}。",
        f"- 再控制JFM已有东北风和局地5°N应力：{line('jfm_north_to_ne850_early_atmos')}。",
        f"- 再控制FEP residual：{line('jfm_north_to_ne850_fep')}。",
        f"- 再控制140°W温跃层状态：{line('jfm_north_to_ne850_d140')}。",
        "",
        "## 三个事件",
        "",
        "| 事件 | JFM北向输出 | JFM 140°W到达 | JFM早期NE850 | MJJ NE925 | MJJ NE850 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for event, row in cases.iterrows():
        lines.append(
            f"| {event} | {row.north_output_jfm_zj:+.2f} ZJ | "
            f"{row.arrival_140w_jfm_zj:+.2f} ZJ | {row.early_ne850_jfm_ms:+.2f} m s⁻¹ | "
            f"{row.ne925_mjj_ms:+.2f} m s⁻¹ | {row.ne850_mjj_z:+.2f} SD |"
        )
    lines += [
        "",
        "2023在JFM已有+0.95 ZJ北向输出，而1997和2015分别为-0.71和-1.08 ZJ；2023的JFM东北风残差仍为负，但到MJJ转为最强正异常。这种时间排序支持‘海洋路由先变化、东北风随后建立’，而不是简单的大气持续性。",
        "",
        "## 尚未闭合的中间桥",
        "",
        f"- JFM北向输出→MJJ北侧SST：{line('jfm_north_to_north_sst')}。",
        f"- JFM北向输出→MJJ降水偶极：{line('jfm_north_to_rain_dipole')}。",
        f"- JFM北向输出→MJJ南北SLP梯度：{line('jfm_north_to_slp_gradient')}。",
        "",
        "宽区域北侧SST、降水偶极和SLP梯度没有形成稳定的逐环中介。因此当前不能写成‘暖量北移→北侧增暖→降水/气压响应→东北风’已经被证明。更稳妥的表述是：早期北向路由是东北风建立前的海洋预条件或其伴随指标；D140/压力场可能同时控制北向流和后续耦合。",
        "",
        "## 对第三问的用法",
        "",
        "把它作为发展期的候选前置门：到达东部的异常焓若在JFM提前向5°N以北泄出，赤道暖量组织和随后大气响应可能改变；MJJ东北风再进一步压低中太平洋西风。局地因果桥仍需逐月空间SST/降水图或固定总热量的模式扰动确认。",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    table = build_event_table()
    relationships = build_relationships(table)
    diagnostics = {
        "events": list(EVENTS),
        "primary_predictor": "JFM 0-300 m mass-balanced northward anomalous-enthalpy output across 5N",
        "primary_target": "MJJ Jiang-box northeasterly residual",
        "h20_or_q20_used": False,
        "permutations": N_PERMUTATIONS,
        "bootstraps": N_BOOTSTRAP,
        "causal_status": "strictly leading observational association; mediator not closed",
    }
    DATA.mkdir(parents=True, exist_ok=True)
    table.to_csv(EVENT_OUTPUT, index=False, float_format="%.10g")
    relationships.to_csv(RELATION_OUTPUT, index=False, float_format="%.10g")
    DIAGNOSTICS_OUTPUT.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(table, relationships)
    print(f"Wrote {EVENT_OUTPUT} ({len(table)} events)")
    print(f"Wrote {RELATION_OUTPUT} ({len(relationships)} tests)")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
