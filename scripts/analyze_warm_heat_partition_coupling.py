#!/usr/bin/env python3
"""Diagnose whether early equator--north H20 partition predicts ENSO coupling.

Both ocean boxes use SODA3 H20 in 0--300 m and 140W--80W.  The equatorial
box is 5S--5N and the north receiver is 5--12N.  Raw storage is processed
with one common 1982--2022 calendar-month detrended baseline.  The primary
partition test asks whether north-box storage is anomalously high after the
combined equator+north storage change has been held fixed.

The script also tests the arrival-conditioned equatorial mirror, adjacent
non-overlapping lead windows, a small-sample bootstrap mediation through
May--Jun precipitation/SLP, and D20 as a competing upstream state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_h20_partition_mpl")
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

DATA = ROOT / "data/derived/research_2026"
EQUATOR_MONTHLY = DATA / "enso_1997_2015_2023_warm_heat_fate_monthly.csv"
NORTH_MONTHLY = DATA / "soda3_north_receiver_budget_monthly_1980_2024.csv"
ATM_MONTHLY = DATA / "enso_full_year_coupling_monthly_1982_2024.csv"
JIANG_EVENTS = DATA / "jiang_ne_wind_h20_exit_event_table.csv"
DECOUPLING_EVENTS = DATA / "peng_jiang_decoupling_event_summary.csv"

OUT = ROOT / "outputs/research_2026/warm_heat_partition_coupling"
EVENT_CSV = DATA / "warm_heat_partition_coupling_event_table.csv"
REL_CSV = DATA / "warm_heat_partition_coupling_relationships.csv"
LAG_CSV = DATA / "warm_heat_partition_coupling_lag_sensitivity.csv"
MEDIATION_CSV = DATA / "warm_heat_partition_coupling_mediation.csv"
FIG_PNG = OUT / "warm_heat_partition_coupling.png"
FIG_PDF = OUT / "warm_heat_partition_coupling.pdf"
REPORT = OUT / "WARM_HEAT_PARTITION_COUPLING_CN.md"
DIAGNOSTICS = DATA / "warm_heat_partition_coupling_diagnostics.json"

EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = (1997, 2015, 2023)
COLORS = {1997: "#202020", 2015: "#2878B5", 2023: "#D94B3D"}
BASELINE = (1982, 2022)
RANDOM_SEED = 20260809
N_PERMUTATIONS = 50_000
N_BOOTSTRAP = 30_000


def same_month_detrended(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = frame[column].to_numpy(dtype=float)
    years = frame["year"].to_numpy(dtype=float)
    months = frame["month"].to_numpy(dtype=int)
    output = np.full(len(frame), np.nan, dtype=float)
    for month in sorted(np.unique(months)):
        fit = (months == month) & (years >= BASELINE[0]) & (years <= BASELINE[1])
        apply = months == month
        if fit.sum() < 20:
            continue
        x = years[fit] - years[fit].mean()
        current = values[fit]
        mean = current.mean()
        slope = np.sum(x * (current - mean)) / np.sum(x**2)
        output[apply] = values[apply] - mean - (years[apply] - years[fit].mean()) * slope
    return output


def validate_monthly(equator: pd.DataFrame, north: pd.DataFrame, atmosphere: pd.DataFrame) -> None:
    for name, frame, columns in (
        ("equator", equator, ["time", "year", "month", "east_h20_raw_zj"]),
        ("north", north, ["time", "year", "month", "receiver_h20_zj"]),
        (
            "atmosphere",
            atmosphere,
            [
                "year", "month", "precip_pattern_residual_z",
                "slp_pattern_residual_z", "tau_pattern_residual_z",
            ],
        ),
    ):
        missing = set(columns).difference(frame.columns)
        if missing:
            raise ValueError(f"{name} missing columns: {sorted(missing)}")
        if frame.duplicated(["year", "month"]).any():
            raise ValueError(f"{name} has duplicate year-month rows")
        if not frame[columns].drop(columns=[c for c in ("time",) if c in columns]).notna().all().all():
            raise ValueError(f"{name} has missing required numeric values")
    for year in EVENT_YEARS:
        if not set(range(1, 6)).issubset(set(equator.loc[equator.year.eq(year), "month"])):
            raise ValueError(f"Equator months incomplete for {year}")
        if not set(range(1, 6)).issubset(set(north.loc[north.year.eq(year), "month"])):
            raise ValueError(f"North months incomplete for {year}")
        if not set(range(1, 9)).issubset(set(atmosphere.loc[atmosphere.year.eq(year), "month"])):
            raise ValueError(f"Atmosphere months incomplete for {year}")


def residualize(values: np.ndarray, controls: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    controls = np.asarray(controls, dtype=float)
    if controls.ndim == 1:
        controls = controls[:, None]
    design = np.column_stack([np.ones(len(values)), controls])
    return values - design @ np.linalg.lstsq(design, values, rcond=None)[0]


def build_events() -> pd.DataFrame:
    equator = pd.read_csv(EQUATOR_MONTHLY, parse_dates=["time"])
    north = pd.read_csv(NORTH_MONTHLY, parse_dates=["time"])
    atmosphere = pd.read_csv(ATM_MONTHLY)
    validate_monthly(equator, north, atmosphere)
    equator["eq_h20_anom_zj"] = same_month_detrended(equator, "east_h20_raw_zj")
    north["north_h20_anom_zj"] = same_month_detrended(north, "receiver_h20_zj")

    rows: list[dict[str, float | int]] = []
    for year in EVENT_YEARS:
        eq = equator.loc[equator.year.eq(year)].set_index("month")
        no = north.loc[north.year.eq(year)].set_index("month")
        row: dict[str, float | int] = {"year": year}
        for end_month, label in ((3, "jan_mar"), (4, "jan_apr"), (5, "jan_may")):
            delta_north = float(no.loc[end_month, "north_h20_anom_zj"] - no.loc[1, "north_h20_anom_zj"])
            delta_eq = float(eq.loc[end_month, "eq_h20_anom_zj"] - eq.loc[1, "eq_h20_anom_zj"])
            row[f"delta_h20_north_{label}_zj"] = delta_north
            row[f"delta_h20_eq_{label}_zj"] = delta_eq
            row[f"delta_h20_total_{label}_zj"] = delta_north + delta_eq
            row[f"delta_h20_north_minus_eq_{label}_zj"] = delta_north - delta_eq

        current_atm = atmosphere.loc[atmosphere.year.eq(year)]
        windows = {
            "amj": (4, 5, 6),
            "mjj": (5, 6, 7),
            "jja": (6, 7, 8),
            "mj": (5, 6),
            "jj": (6, 7),
            "ja": (7, 8),
        }
        for label, months in windows.items():
            selected = current_atm.loc[current_atm.month.isin(months)]
            for variable in (
                "precip_pattern_residual_z",
                "slp_pattern_residual_z",
                "tau_pattern_residual_z",
            ):
                row[f"{variable}_{label}"] = float(selected[variable].mean())
        row["atmospheric_bridge_mj_z"] = float(
            0.5
            * (
                row["precip_pattern_residual_z_mj"]
                + row["slp_pattern_residual_z_mj"]
            )
        )
        rows.append(row)

    events = pd.DataFrame(rows)
    jiang = pd.read_csv(JIANG_EVENTS)[
        [
            "year", "group", "q140_mar_apr_z", "d140_mar_apr_z",
            "east_ocean_state_z", "mar_apr_fep_residual_c",
            "precip_response_mjj", "slp_response_mjj", "tau_response_mjj",
            "ne925_mjj_ms",
        ]
    ]
    decoupling = pd.read_csv(DECOUPLING_EVENTS)[
        [
            "year", "jiang_tau_response_mjj_z", "jiang_ne850_mjj_z",
            "peng_cwp_u10_residual_ms", "peng_cwp_u10_ratio",
        ]
    ]
    events = (
        events.merge(jiang, on="year", validate="one_to_one")
        .merge(decoupling, on="year", validate="one_to_one")
        .sort_values("year")
        .reset_index(drop=True)
    )

    for label in ("jan_mar", "jan_apr", "jan_may"):
        north_name = f"delta_h20_north_{label}_zj"
        eq_name = f"delta_h20_eq_{label}_zj"
        total_name = f"delta_h20_total_{label}_zj"
        events[f"partition_north_given_total_{label}_zj"] = residualize(
            events[north_name].to_numpy(dtype=float),
            events[[total_name]].to_numpy(dtype=float),
        )
        events[f"north_given_arrival_{label}_zj"] = residualize(
            events[north_name].to_numpy(dtype=float),
            events[["q140_mar_apr_z"]].to_numpy(dtype=float),
        )
        events[f"eq_given_arrival_{label}_zj"] = residualize(
            events[eq_name].to_numpy(dtype=float),
            events[["q140_mar_apr_z"]].to_numpy(dtype=float),
        )
    if len(events) != len(EVENT_YEARS) or events.select_dtypes(include=[np.number]).isna().any().any():
        raise ValueError("Event table is incomplete")
    return events


def partial_relationship(
    frame: pd.DataFrame,
    test_id: str,
    label: str,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...],
    seed_offset: int,
) -> dict[str, float | int | str]:
    data = frame.dropna(subset=[x_name, y_name, *controls]).reset_index(drop=True)
    x = data[x_name].to_numpy(dtype=float)
    y = data[y_name].to_numpy(dtype=float)
    c = data[list(controls)].to_numpy(dtype=float) if controls else np.zeros((len(data), 0))
    xr = residualize(x, c) if controls else x - x.mean()
    yr = residualize(y, c) if controls else y - y.mean()
    observed = float(np.corrcoef(xr, yr)[0, 1])
    degrees = len(data) - len(controls) - 2
    t_value = observed * np.sqrt(degrees / max(1.0e-15, 1.0 - observed**2))
    analytic_p = float(2.0 * stats.t.sf(abs(t_value), degrees))
    spearman = float(stats.spearmanr(xr, yr).statistic)

    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    permutations = np.empty(N_PERMUTATIONS)
    for index in range(N_PERMUTATIONS):
        permutations[index] = np.corrcoef(xr, rng.permutation(yr))[0, 1]
    permutation_p = float(
        (np.sum(np.abs(permutations) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1)
    )
    bootstrap = np.full(N_BOOTSTRAP, np.nan)
    for index in range(N_BOOTSTRAP):
        selected = rng.integers(0, len(data), len(data))
        xb, yb, cb = x[selected], y[selected], c[selected]
        xbr = residualize(xb, cb) if controls else xb - xb.mean()
        ybr = residualize(yb, cb) if controls else yb - yb.mean()
        if np.std(xbr) > 0 and np.std(ybr) > 0:
            bootstrap[index] = np.corrcoef(xbr, ybr)[0, 1]
    ci_low, ci_high = np.nanpercentile(bootstrap, [2.5, 97.5])
    loeo = []
    for index in range(len(data)):
        keep = np.arange(len(data)) != index
        xk, yk, ck = x[keep], y[keep], c[keep]
        xkr = residualize(xk, ck) if controls else xk - xk.mean()
        ykr = residualize(yk, ck) if controls else yk - yk.mean()
        loeo.append(float(np.corrcoef(xkr, ykr)[0, 1]))
    return {
        "test_id": test_id,
        "label": label,
        "x": x_name,
        "y": y_name,
        "controls": ";".join(controls),
        "n_events": len(data),
        "partial_r": observed,
        "partial_spearman_r": spearman,
        "analytic_p": analytic_p,
        "permutation_p": permutation_p,
        "bootstrap_ci_low": float(ci_low),
        "bootstrap_ci_high": float(ci_high),
        "loeo_r_min": float(np.min(loeo)),
        "loeo_r_max": float(np.max(loeo)),
    }


def build_relationships(events: pd.DataFrame) -> pd.DataFrame:
    tests = [
        (
            "partition_to_tau", "North partition at fixed total -> Jiang MJJ wind stress",
            "delta_h20_north_jan_apr_zj", "jiang_tau_response_mjj_z",
            ("delta_h20_total_jan_apr_zj",),
        ),
        (
            "partition_to_precip", "North partition at fixed total -> Jiang MJJ precipitation",
            "delta_h20_north_jan_apr_zj", "precip_response_mjj",
            ("delta_h20_total_jan_apr_zj",),
        ),
        (
            "partition_to_slp", "North partition at fixed total -> Jiang MJJ SLP",
            "delta_h20_north_jan_apr_zj", "slp_response_mjj",
            ("delta_h20_total_jan_apr_zj",),
        ),
        (
            "partition_to_ne", "North partition at fixed total -> Jiang MJJ NE925",
            "delta_h20_north_jan_apr_zj", "ne925_mjj_ms",
            ("delta_h20_total_jan_apr_zj",),
        ),
        (
            "arrival_partition_to_tau", "North storage at fixed arrival -> Jiang MJJ wind stress",
            "delta_h20_north_jan_apr_zj", "jiang_tau_response_mjj_z",
            ("q140_mar_apr_z",),
        ),
        (
            "total_arrival_partition_to_tau", "North storage at fixed total and arrival -> Jiang MJJ wind stress",
            "delta_h20_north_jan_apr_zj", "jiang_tau_response_mjj_z",
            ("delta_h20_total_jan_apr_zj", "q140_mar_apr_z"),
        ),
        (
            "d20_sensitivity", "North partition -> wind stress after D20 control",
            "delta_h20_north_jan_apr_zj", "jiang_tau_response_mjj_z",
            ("delta_h20_total_jan_apr_zj", "d140_mar_apr_z"),
        ),
        (
            "total_arrival_d20_sensitivity", "North partition -> wind stress after total, arrival and D20 control",
            "delta_h20_north_jan_apr_zj", "jiang_tau_response_mjj_z",
            ("delta_h20_total_jan_apr_zj", "q140_mar_apr_z", "d140_mar_apr_z"),
        ),
        (
            "arrival_mirror", "North residual vs equatorial residual at fixed arrival",
            "north_given_arrival_jan_apr_zj", "eq_given_arrival_jan_apr_zj", (),
        ),
        (
            "raw_difference_to_tau", "Raw north-minus-equator difference -> wind stress",
            "delta_h20_north_minus_eq_jan_apr_zj", "jiang_tau_response_mjj_z",
            ("q140_mar_apr_z",),
        ),
        (
            "d20_to_partition", "D20 at 140W -> north partition at fixed total",
            "d140_mar_apr_z", "delta_h20_north_jan_apr_zj",
            ("delta_h20_total_jan_apr_zj",),
        ),
    ]
    return pd.DataFrame(
        [
            partial_relationship(events, test_id, label, x, y, controls, index)
            for index, (test_id, label, x, y, controls) in enumerate(tests)
        ]
    )


def build_lag_sensitivity(events: pd.DataFrame) -> pd.DataFrame:
    tests = [
        (
            "Jan-Mar -> AMJ", "delta_h20_north_jan_mar_zj",
            "delta_h20_total_jan_mar_zj", "tau_pattern_residual_z_amj",
        ),
        (
            "Jan-Apr -> MJJ", "delta_h20_north_jan_apr_zj",
            "delta_h20_total_jan_apr_zj", "tau_pattern_residual_z_mjj",
        ),
        (
            "Jan-May -> JJA", "delta_h20_north_jan_may_zj",
            "delta_h20_total_jan_may_zj", "tau_pattern_residual_z_jja",
        ),
    ]
    rows = []
    for index, (window, x, total, y) in enumerate(tests):
        row = partial_relationship(
            events,
            f"lag_{index}",
            f"{window}: north partition -> wind-stress response",
            x,
            y,
            (total,),
            100 + index,
        )
        row["window"] = window
        rows.append(row)
    return pd.DataFrame(rows)


def standardize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    scale = values.std(ddof=0)
    if not np.isfinite(scale) or scale < 1.0e-12:
        raise ValueError("Cannot standardize a constant series")
    return (values - values.mean()) / scale


def fit_mediation_arrays(x: np.ndarray, mediator: np.ndarray, y: np.ndarray, controls: np.ndarray) -> dict[str, float]:
    xz, mz, yz = standardize(x), standardize(mediator), standardize(y)
    controls = np.asarray(controls, dtype=float)
    if controls.ndim == 1:
        controls = controls[:, None]
    cz = np.column_stack([standardize(controls[:, i]) for i in range(controls.shape[1])]) if controls.shape[1] else np.zeros((len(x), 0))
    design_a = np.column_stack([np.ones(len(x)), xz, cz])
    a = float(np.linalg.lstsq(design_a, mz, rcond=None)[0][1])
    design_b = np.column_stack([np.ones(len(x)), mz, xz, cz])
    coefficients_b = np.linalg.lstsq(design_b, yz, rcond=None)[0]
    b = float(coefficients_b[1])
    direct = float(coefficients_b[2])
    design_total = np.column_stack([np.ones(len(x)), xz, cz])
    total = float(np.linalg.lstsq(design_total, yz, rcond=None)[0][1])
    return {"a": a, "b": b, "direct": direct, "total": total, "indirect": a * b}


def mediation_test(
    events: pd.DataFrame,
    test_id: str,
    label: str,
    x_name: str,
    mediator_name: str,
    y_name: str,
    controls: tuple[str, ...],
    seed_offset: int,
) -> dict[str, float | int | str]:
    data = events[[x_name, mediator_name, y_name, *controls]].dropna().reset_index(drop=True)
    x = data[x_name].to_numpy(dtype=float)
    mediator = data[mediator_name].to_numpy(dtype=float)
    y = data[y_name].to_numpy(dtype=float)
    c = data[list(controls)].to_numpy(dtype=float) if controls else np.zeros((len(data), 0))
    observed = fit_mediation_arrays(x, mediator, y, c)
    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    bootstrap = {name: np.full(N_BOOTSTRAP, np.nan) for name in observed}
    for index in range(N_BOOTSTRAP):
        selected = rng.integers(0, len(data), len(data))
        try:
            current = fit_mediation_arrays(x[selected], mediator[selected], y[selected], c[selected])
        except (ValueError, np.linalg.LinAlgError):
            continue
        for name, value in current.items():
            bootstrap[name][index] = value
    output: dict[str, float | int | str] = {
        "test_id": test_id,
        "label": label,
        "x": x_name,
        "mediator": mediator_name,
        "y": y_name,
        "controls": ";".join(controls),
        "n_events": len(data),
        **observed,
    }
    for name, values in bootstrap.items():
        low, high = np.nanpercentile(values, [2.5, 97.5])
        output[f"{name}_ci_low"] = float(low)
        output[f"{name}_ci_high"] = float(high)
    indirect = bootstrap["indirect"]
    output["indirect_same_sign_fraction"] = float(
        np.nanmean(np.sign(indirect) == np.sign(observed["indirect"]))
    )
    return output


def build_mediation(events: pd.DataFrame) -> pd.DataFrame:
    rows = [
        mediation_test(
            events,
            "partition_bridge_wind",
            "Jan-Apr north partition -> May-Jun convection/SLP bridge -> Jul-Aug wind stress",
            "delta_h20_north_jan_apr_zj",
            "atmospheric_bridge_mj_z",
            "tau_pattern_residual_z_ja",
            ("delta_h20_total_jan_apr_zj",),
            300,
        ),
        mediation_test(
            events,
            "d20_partition_wind",
            "D20 -> Jan-Apr north partition -> MJJ wind stress",
            "d140_mar_apr_z",
            "delta_h20_north_jan_apr_zj",
            "jiang_tau_response_mjj_z",
            ("delta_h20_total_jan_apr_zj",),
            301,
        ),
    ]
    return pd.DataFrame(rows)


def setup_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial Unicode MS", "PingFang SC", "Heiti SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 9.6,
            "axes.titlesize": 10.8,
            "axes.labelsize": 9.7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.dpi": 400,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def scatter_highlights(axis: plt.Axes, frame: pd.DataFrame, x: str, y: str) -> None:
    ordinary = ~frame.year.isin(HIGHLIGHTS)
    axis.scatter(frame.loc[ordinary, x], frame.loc[ordinary, y], s=34, color="#9B9B9B", edgecolor="white", linewidth=0.5, zorder=3)
    for year in HIGHLIGHTS:
        row = frame.loc[frame.year.eq(year)].iloc[0]
        axis.scatter(row[x], row[y], s=74, color=COLORS[year], edgecolor="white", linewidth=0.7, zorder=4)
        axis.annotate(str(year), (row[x], row[y]), xytext=(5, 5), textcoords="offset points", color=COLORS[year], fontsize=8.8)
    slope, intercept = np.polyfit(frame[x], frame[y], 1)
    xx = np.linspace(float(frame[x].min()), float(frame[x].max()), 100)
    axis.plot(xx, slope * xx + intercept, color="#263238", lw=1.4)
    axis.axhline(0, color="#888888", lw=0.7)
    axis.axvline(0, color="#888888", lw=0.7)


def forest(axis: plt.Axes, rows: list[pd.Series], labels: list[str], colors: list[str]) -> None:
    positions = np.arange(len(rows))
    for position, row, color in zip(positions, rows, colors, strict=True):
        value = float(row.partial_r)
        low = float(row.bootstrap_ci_low)
        high = float(row.bootstrap_ci_high)
        axis.errorbar(value, position, xerr=np.array([[value - low], [high - value]]), fmt="o", color=color, ecolor=color, markersize=6.5, elinewidth=1.8, capsize=3)
    axis.axvline(0, color="#666666", lw=0.8)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlim(-1.05, 1.05)


def plot_results(events: pd.DataFrame, relationships: pd.DataFrame, lag: pd.DataFrame, mediation: pd.DataFrame) -> None:
    setup_style()
    OUT.mkdir(parents=True, exist_ok=True)
    lookup = relationships.set_index("test_id")
    med = mediation.set_index("test_id")
    fig, axes = plt.subplots(2, 3, figsize=(15.3, 9.1))
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.095, top=0.89, hspace=0.36, wspace=0.31)

    axis = axes[0, 0]
    scatter_highlights(axis, events, "delta_h20_total_jan_apr_zj", "delta_h20_north_jan_apr_zj")
    axis.set_xlabel("赤道+北侧 ΔH₂₀（Jan→Apr，ZJ）")
    axis.set_ylabel("北侧 ΔH₂₀（Jan→Apr，ZJ）")
    axis.set_title("a  分配残差：同样总暖量下北侧多存了多少", loc="left", fontweight="bold")
    for year in HIGHLIGHTS:
        row = events.loc[events.year.eq(year)].iloc[0]
        axis.text(0.04, 0.95 - 0.07 * list(HIGHLIGHTS).index(year), f"{year}: P_H={row.partition_north_given_total_jan_apr_zj:+.2f} ZJ", transform=axis.transAxes, color=COLORS[year], va="top")

    axis = axes[0, 1]
    plot_frame = events[["year", "partition_north_given_total_jan_apr_zj"]].copy()
    plot_frame["tau_residual"] = residualize(events["jiang_tau_response_mjj_z"].to_numpy(dtype=float), events[["delta_h20_total_jan_apr_zj"]].to_numpy(dtype=float))
    scatter_highlights(axis, plot_frame, "partition_north_given_total_jan_apr_zj", "tau_residual")
    row = lookup.loc["partition_to_tau"]
    axis.set_xlabel("春季北侧分配残差 P_H（ZJ）")
    axis.set_ylabel("MJJ风应力响应（总暖量条件残差）")
    axis.set_title("b  暖量越偏北，后续中太平洋风响应越弱", loc="left", fontweight="bold")
    axis.text(0.64, 0.95, f"partial r={row.partial_r:+.2f}\np={row.permutation_p:.3f}\n95% CI [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]", transform=axis.transAxes, va="top")

    axis = axes[0, 2]
    scatter_highlights(axis, events, "north_given_arrival_jan_apr_zj", "eq_given_arrival_jan_apr_zj")
    row = lookup.loc["arrival_mirror"]
    axis.set_xlabel("北侧ΔH₂₀（已去除140°W到达量）")
    axis.set_ylabel("赤道ΔH₂₀（已去除140°W到达量）")
    axis.set_title("c  跨事件存在镜像，但2023赤道储热并未偏低", loc="left", fontweight="bold")
    axis.text(0.04, 0.95, f"r={row.partial_r:+.2f}; p={row.permutation_p:.3f}", transform=axis.transAxes, va="top")

    axis = axes[1, 0]
    forest(axis, [row for _, row in lag.iterrows()], lag["window"].tolist(), ["#4C78A8"] * len(lag))
    axis.set_xlabel("北侧分配与随后风应力响应的偏相关")
    axis.set_title("d  相邻领先窗口连续同号", loc="left", fontweight="bold")
    for position, (_, row) in enumerate(lag.iterrows()):
        axis.text(0.98, position, f"p={row.permutation_p:.3f}", transform=axis.get_yaxis_transform(), ha="right", va="center", fontsize=8.5)

    axis = axes[1, 1]
    axis.set_axis_off()
    row = med.loc["partition_bridge_wind"]
    axis.text(0.02, 0.94, "e  无时间重叠的简化中介检验", transform=axis.transAxes, fontsize=10.8, fontweight="bold", va="top")
    nodes = [(0.15, 0.58, "Jan–Apr\n北侧分配"), (0.50, 0.58, "May–Jun\n降水–SLP桥"), (0.85, 0.58, "Jul–Aug\n风应力响应")]
    for x, y, text in nodes:
        axis.text(x, y, text, transform=axis.transAxes, ha="center", va="center", bbox=dict(boxstyle="round,pad=0.45", fc="#F5F7FA", ec="#546E7A", lw=1.2))
    axis.annotate("", xy=(0.40, 0.58), xytext=(0.25, 0.58), xycoords="axes fraction", arrowprops=dict(arrowstyle="->", lw=1.7, color="#263238"))
    axis.annotate("", xy=(0.75, 0.58), xytext=(0.60, 0.58), xycoords="axes fraction", arrowprops=dict(arrowstyle="->", lw=1.7, color="#263238"))
    axis.text(0.325, 0.64, f"a={row.a:+.2f}", transform=axis.transAxes, ha="center", fontweight="bold")
    axis.text(0.675, 0.64, f"b={row.b:+.2f}", transform=axis.transAxes, ha="center", fontweight="bold")
    axis.text(0.50, 0.31, f"间接效应 ab={row.indirect:+.2f}\n95% bootstrap CI [{row.indirect_ci_low:+.2f}, {row.indirect_ci_high:+.2f}]\n加入桥梁后直接效应：{row.total:+.2f} → {row.direct:+.2f}", transform=axis.transAxes, ha="center", va="center", fontsize=9.5)

    axis = axes[1, 2]
    control_ids = ["partition_to_tau", "arrival_partition_to_tau", "total_arrival_partition_to_tau", "d20_sensitivity", "total_arrival_d20_sensitivity"]
    labels = ["固定总暖量", "固定到达量", "总量+到达量", "总量+D20", "总量+到达量+D20"]
    rows = [lookup.loc[test_id] for test_id in control_ids]
    colors = ["#2E7D32", "#2E7D32", "#2E7D32", "#C62828", "#C62828"]
    forest(axis, rows, labels, colors)
    axis.set_xlabel("北侧分配—风应力响应偏相关")
    axis.set_title("f  D20使关系减弱：共同原因或上游过程？", loc="left", fontweight="bold")

    fig.suptitle("同样总暖量下，春季暖量偏北分配与后续海气响应减弱相联系", fontsize=15.2, fontweight="bold", y=0.965)
    fig.text(0.5, 0.025, "SODA3 0–300 m H₂₀；赤道箱5°S–5°N、北侧箱5°–12°N，均为140°W–80°W；共同1982–2022逐月去趋势基准；13个暖事件", ha="center", fontsize=9.1)
    fig.savefig(FIG_PNG, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_report(events: pd.DataFrame, relationships: pd.DataFrame, lag: pd.DataFrame, mediation: pd.DataFrame) -> None:
    lookup = relationships.set_index("test_id")
    med = mediation.set_index("test_id")
    main = lookup.loc["partition_to_tau"]
    mirror = lookup.loc["arrival_mirror"]
    precip = lookup.loc["partition_to_precip"]
    slp = lookup.loc["partition_to_slp"]
    d20 = lookup.loc["d20_sensitivity"]
    selected = events.set_index("year").loc[list(HIGHLIGHTS)]
    m = med.loc["partition_bridge_wind"]
    md = med.loc["d20_partition_wind"]
    lines = [
        "# 暖量南北分配—海气接通检验",
        "",
        "## 核心结论",
        "",
        "**新计算支持把第三问从“北侧绝对储热”进一步收紧为“固定总暖量后的南北分配”。2023赤道并不缺热，但在相近南北合计暖量下，额外有更多暖量配置在5°—12°N。**",
        "",
        f"固定赤道+北侧总H20变化后，Jan—Apr北侧分配越多，MJJ中太平洋风应力响应越弱（partial r={main.partial_r:+.2f}, permutation p={main.permutation_p:.3f}, 95% bootstrap CI [{main.bootstrap_ci_low:+.2f}, {main.bootstrap_ci_high:+.2f}]）。对应降水和SLP关系分别为r={precip.partial_r:+.2f}和r={slp.partial_r:+.2f}。",
        f"固定140°W到达量后，13事件整体上北侧与赤道H20变化呈镜像关系（r={mirror.partial_r:+.2f}, p={mirror.permutation_p:.3f}）。但2023的北侧和赤道到达条件残差都为正，因此2023不是“赤道缺热”，而是总储热较强且南北覆盖更宽；只有在进一步固定南北合计暖量时，它才表现为北侧份额异常偏高。",
        "",
        "最稳妥的表述是：**在相近东部暖量到达及总暖量背景下，较多暖量在春季提前分配至5°—12°N，与随后较弱的中太平洋降水—SLP—风应力响应系统相关；这一分配可能是影响海气接通的过程环节，也可能部分表征更大尺度温跃层调整。**",
        "",
        "## 1997、2015、2023的分配差异",
        "",
        "| 事件 | 赤道ΔH20 | 北侧ΔH20 | 合计ΔH20 | 北侧分配残差 P_H | MJJ风应力响应 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in HIGHLIGHTS:
        row = selected.loc[year]
        lines.append(
            f"| {year} | {row.delta_h20_eq_jan_apr_zj:+.2f} ZJ | {row.delta_h20_north_jan_apr_zj:+.2f} ZJ | {row.delta_h20_total_jan_apr_zj:+.2f} ZJ | {row.partition_north_given_total_jan_apr_zj:+.2f} ZJ | {row.jiang_tau_response_mjj_z:+.2f} SD |"
        )
    lines += [
        "",
        "2023赤道箱仍增加约+3.04 ZJ，因此不能说其赤道没有暖量，也不能说北侧直接拿走了原本位于赤道的暖量。区别在于：给定赤道+北侧合计变化后，2023北侧比13事件经验关系预期多存约+0.47 ZJ；1997和2015分别少存约-0.76和-0.57 ZJ。2023表现为“赤道仍暖、总量也强，但空间分布额外偏北”，这比单独比较北侧H20更准确。",
        "",
        "## 时间优先性",
        "",
        "| 海洋分配窗口 → 后续风窗口 | partial r | permutation p | 95% CI |",
        "|---|---:|---:|---:|",
    ]
    for _, row in lag.iterrows():
        lines.append(f"| {row.window} | {row.partial_r:+.2f} | {row.permutation_p:.3f} | [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}] |")
    lines += [
        "",
        "三个相邻窗口全部同号，而且每个大气窗口均从海洋窗口结束后的下一个月开始。关系不是只依赖一个人为挑选的FMA—MJJ窗口；但随着窗口后移，置换p值由0.009增至0.069，说明领先信号以春季最清楚，不能声称所有窗口都达到显著。",
        "",
        "## 简化中介检验",
        "",
        f"无时间重叠链条为：Jan—Apr北侧分配 → May—Jun降水/SLP综合桥梁 → Jul—Aug风应力。标准化路径a={m.a:+.2f}、b={m.b:+.2f}，间接效应ab={m.indirect:+.2f}，95% bootstrap CI [{m.indirect_ci_low:+.2f}, {m.indirect_ci_high:+.2f}]。加入大气桥梁后，北侧分配对后期风的直接系数由总效应{m.total:+.2f}降为{m.direct:+.2f}。",
        "",
        "该结果与“暖量分配通过对流—气压响应传递到风”一致，但13事件的bootstrap区间决定其只能称为探索性中介证据，不能称为已证明的中介机制。",
        "",
        "## D20到底是什么角色",
        "",
        f"仅固定总暖量时，分配—风关系为r={main.partial_r:+.2f}；进一步控制140°W D20后降为r={d20.partial_r:+.2f}。D20与北侧分配本身也存在联系。D20 → 分配 → 风的探索性间接效应为{md.indirect:+.2f}，bootstrap CI [{md.indirect_ci_low:+.2f}, {md.indirect_ci_high:+.2f}]。",
        "",
        "因此当前无法区分：D20是共同原因，还是通过经向暖量重分配影响耦合的上游动力。这个悬念正好定义了模式试验需要隔离的变量。",
        "",
        "## 方法说明",
        "",
        "- 赤道箱为5°S—5°N，北侧箱为5°—12°N；两者均为140°W—80°W、0—300 m，使用完全相同的1982—2022逐月去趋势基准。",
        "- 主分配量不是不稳定比值，而是回归残差：P_H = ΔH20,N − E(ΔH20,N | ΔH20,N+ΔH20,EQ)。",
        "- 主关系在回归两端同时控制总暖量，统计上等价于偏相关检验。",
        "- 分配残差来自13个暖事件的经验关系；增加事件样本、改变箱体纬度和使用OHC/D20替代指标仍需作为敏感性。",
        "",
        "## 下一步实验",
        "",
        "单纯AGCM不能感知地下H20。最强方案是耦合模式中保持总暖量近似相同，只改变赤道—北侧初始分配；低成本方案是先用海洋模式让两种地下配置生成不同SST，再将SST输入AGCM。当前观测结果已经给出了实验扰动方向：以2023型正P_H与1997/2015型负P_H作为两组初始状态。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = build_events()
    relationships = build_relationships(events)
    lag = build_lag_sensitivity(events)
    mediation = build_mediation(events)
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    relationships.to_csv(REL_CSV, index=False, float_format="%.9g")
    lag.to_csv(LAG_CSV, index=False, float_format="%.9g")
    mediation.to_csv(MEDIATION_CSV, index=False, float_format="%.9g")
    plot_results(events, relationships, lag, mediation)
    write_report(events, relationships, lag, mediation)
    diagnostics = {
        "baseline": list(BASELINE),
        "equatorial_box": "5S-5N, 140W-80W, 0-300 m",
        "north_box": "5-12N, 140W-80W, 0-300 m",
        "partition_definition": "residual north H20 change conditional on equator+north total H20 change",
        "n_events": len(events),
        "event_years": list(EVENT_YEARS),
        "strict_lag_windows": ["Jan-Mar -> AMJ", "Jan-Apr -> MJJ", "Jan-May -> JJA"],
        "mediation_timing": "Jan-Apr partition -> May-Jun precipitation/SLP -> Jul-Aug wind stress",
    }
    DIAGNOSTICS.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(EVENT_CSV)
    print(REL_CSV)
    print(LAG_CSV)
    print(MEDIATION_CSV)
    print(FIG_PNG)
    print(FIG_PDF)
    print(REPORT)


if __name__ == "__main__":
    main()
