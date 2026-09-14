#!/usr/bin/env python3
"""Test whether early eastern-Pacific warm-heat fate can precede decoupling.

The source variable is the anomalous Jan--Apr H20 change in the SODA3
receiver box north of the eastern equatorial Pacific (5--12N, 140W--80W,
0--300 m).  The main atmospheric targets are Jiang-type May--Jul central
Pacific precipitation, SLP and surface-wind-stress responses.  Mar--Apr
eastward Q20 across 140W is held fixed so that the test asks where warm heat
is stored after comparable arrival, rather than whether warm heat arrived.

The script deliberately separates a strict lead test (Jan--Apr ocean state
versus May--Jul atmosphere) from overlapping AMJ/MJJ associations that can
contain atmosphere-to-ocean feedback.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_early_fate_decoupling_mpl")
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt


DATA = ROOT / "data/derived/research_2026"
RECEIVER = DATA / "soda3_north_receiver_budget_monthly_1980_2024.csv"
OUTFLOW = DATA / "h20_outflow_ne_feedback_event_table.csv"
JIANG = DATA / "jiang_ne_wind_h20_exit_event_table.csv"
DECOUPLING = DATA / "peng_jiang_decoupling_event_summary.csv"
LONG_REL = DATA / "h20_outflow_ne_feedback_relationships.csv"

OUT_DATA = DATA
OUT = ROOT / "outputs/research_2026/early_warm_heat_fate_to_decoupling"
EVENT_CSV = OUT_DATA / "early_warm_heat_fate_to_decoupling_event_table.csv"
REL_CSV = OUT_DATA / "early_warm_heat_fate_to_decoupling_relationships.csv"
WINDOW_CSV = OUT_DATA / "early_warm_heat_fate_to_decoupling_window_sensitivity.csv"
CONTROL_CSV = OUT_DATA / "early_warm_heat_fate_to_decoupling_control_sensitivity.csv"
FIG_PNG = OUT / "early_warm_heat_fate_to_decoupling.png"
FIG_PDF = OUT / "early_warm_heat_fate_to_decoupling.pdf"
REPORT = OUT / "EARLY_WARM_HEAT_FATE_TO_DECOUPLING_CN.md"
DIAGNOSTICS = OUT_DATA / "early_warm_heat_fate_to_decoupling_diagnostics.json"

EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = (1997, 2015, 2023)
COLORS = {1997: "#202020", 2015: "#2474B5", 2023: "#D84A3A"}
RANDOM_SEED = 20260809
N_PERMUTATIONS = 50_000
N_BOOTSTRAP = 30_000


def validate_inputs(receiver: pd.DataFrame, outflow: pd.DataFrame, jiang: pd.DataFrame, decoupling: pd.DataFrame) -> None:
    required_receiver = {
        "time", "year", "month", "receiver_h20_zj_anom",
        "receiver_zonal_convergence_anom", "receiver_south_q20_in_anom",
        "receiver_north_q20_in_anom", "receiver_surface_warm_anom",
        "receiver_residual_warm_anom", "receiver_storage_tendency_anom",
    }
    missing = required_receiver.difference(receiver.columns)
    if missing:
        raise ValueError(f"Receiver columns missing: {sorted(missing)}")
    times = pd.DatetimeIndex(receiver["time"])
    if not times.is_monotonic_increasing or not times.is_unique:
        raise ValueError("Receiver time axis must be sorted and unique")
    expected = pd.date_range("1980-01-01", "2024-07-01", freq="MS") + pd.Timedelta(days=14)
    if not times.equals(expected):
        raise ValueError("Receiver time axis is not complete from Jan 1980 to Jul 2024")
    if receiver.loc[receiver.year.eq(2023), "month"].nunique() != 12:
        raise ValueError("2023 receiver budget is incomplete")
    for name, frame in (("outflow", outflow), ("Jiang", jiang), ("decoupling", decoupling)):
        years = tuple(frame.loc[frame.year.isin(EVENT_YEARS), "year"].astype(int).sort_values())
        if years != EVENT_YEARS:
            raise ValueError(f"{name} event years are incomplete: {years}")


def integrate_zj(frame: pd.DataFrame, column: str) -> float:
    seconds = pd.to_datetime(frame.time).dt.days_in_month.to_numpy(dtype=float) * 86400.0
    return float(np.sum(frame[column].to_numpy(dtype=float) * seconds) / 1.0e6)


def build_events() -> pd.DataFrame:
    receiver = pd.read_csv(RECEIVER, parse_dates=["time"])
    outflow = pd.read_csv(OUTFLOW)
    jiang = pd.read_csv(JIANG)
    decoupling = pd.read_csv(DECOUPLING)
    validate_inputs(receiver, outflow, jiang, decoupling)

    receiver_rows: list[dict[str, float | int]] = []
    for year in EVENT_YEARS:
        current = receiver.loc[receiver.year.eq(year)].set_index("month", drop=False)
        row: dict[str, float | int] = {"year": year}
        jan = float(current.loc[1, "receiver_h20_zj_anom"])
        for month, label in ((3, "mar"), (4, "apr"), (5, "may"), (6, "jun")):
            row[f"north_h20_change_jan_{label}_zj"] = float(
                current.loc[month, "receiver_h20_zj_anom"] - jan
            )
        row["north_h20_mjj_zj"] = float(
            current.loc[[5, 6, 7], "receiver_h20_zj_anom"].mean()
        )
        fma = current.loc[[2, 3, 4]].copy()
        term_map = {
            "north_budget_zonal_fma_zj": "receiver_zonal_convergence_anom",
            "north_budget_south5n_fma_zj": "receiver_south_q20_in_anom",
            "north_budget_north12n_fma_zj": "receiver_north_q20_in_anom",
            "north_budget_surface_fma_zj": "receiver_surface_warm_anom",
            "north_budget_residual_fma_zj": "receiver_residual_warm_anom",
            "north_budget_storage_fma_zj": "receiver_storage_tendency_anom",
        }
        for output, source in term_map.items():
            row[output] = integrate_zj(fma, source)
        receiver_rows.append(row)

    receiver_events = pd.DataFrame(receiver_rows)
    outflow_keep = outflow[
        ["year", "group", "q5n_fma_zj", "q5n_amj_zj", "q5n_ekman_amj_zj", "ne925_mjj_ms"]
    ].copy()
    outflow_keep["q5n_nonekman_amj_zj"] = (
        outflow_keep["q5n_amj_zj"] - outflow_keep["q5n_ekman_amj_zj"]
    )
    jiang_keep = jiang[
        [
            "year", "q140_mar_apr_z", "d140_mar_apr_z", "east_ocean_state_z",
            "mar_apr_fep_residual_c", "precip_response_mjj", "slp_response_mjj",
            "tau_response_mjj",
        ]
    ]
    decoupling_keep = decoupling[
        [
            "year", "peng_cwp_u10_ratio", "peng_cwp_u10_residual_ms",
            "jiang_ne850_mjj_z", "jiang_tau_response_mjj_z",
            "mjj_composite_coupling_z",
        ]
    ]
    events = (
        receiver_events.merge(outflow_keep, on="year", validate="one_to_one")
        .merge(jiang_keep, on="year", validate="one_to_one")
        .merge(decoupling_keep, on="year", validate="one_to_one")
        .sort_values("year")
        .reset_index(drop=True)
    )
    events["peng_wind_decoupling_ms"] = -events["peng_cwp_u10_residual_ms"]
    events["jiang_stress_decoupling_z"] = -events["jiang_tau_response_mjj_z"]
    events["mjj_decoupling_z"] = -events["mjj_composite_coupling_z"]
    if len(events) != len(EVENT_YEARS) or events.isna().any().any():
        raise ValueError("Merged event table is incomplete")
    return events


def residualize(values: np.ndarray, controls: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    controls = np.asarray(controls, dtype=float)
    if controls.ndim == 1:
        controls = controls[:, None]
    design = np.column_stack([np.ones(len(values)), controls])
    return values - design @ np.linalg.lstsq(design, values, rcond=None)[0]


def partial_stat(
    frame: pd.DataFrame,
    test_id: str,
    label: str,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...],
    seed_offset: int,
) -> dict[str, float | int | str]:
    columns = [x_name, y_name, *controls]
    data = frame.dropna(subset=columns).reset_index(drop=True)
    x = data[x_name].to_numpy(dtype=float)
    y = data[y_name].to_numpy(dtype=float)
    c = data[list(controls)].to_numpy(dtype=float) if controls else np.zeros((len(data), 0))
    xr = residualize(x, c) if controls else x - x.mean()
    yr = residualize(y, c) if controls else y - y.mean()
    observed = float(np.corrcoef(xr, yr)[0, 1])
    spearman = float(stats.spearmanr(xr, yr).statistic)
    degrees = len(data) - len(controls) - 2
    t_value = observed * np.sqrt(degrees / max(1.0e-15, 1.0 - observed**2))
    analytic_p = float(2.0 * stats.t.sf(abs(t_value), df=degrees))

    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    permuted = np.empty(N_PERMUTATIONS, dtype=float)
    for index in range(N_PERMUTATIONS):
        permuted[index] = np.corrcoef(xr, rng.permutation(yr))[0, 1]
    permutation_p = float(
        (np.sum(np.abs(permuted) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1)
    )

    bootstrap = np.full(N_BOOTSTRAP, np.nan, dtype=float)
    for index in range(N_BOOTSTRAP):
        selected = rng.integers(0, len(data), len(data))
        xb = x[selected]
        yb = y[selected]
        cb = c[selected]
        xbr = residualize(xb, cb) if controls else xb - xb.mean()
        ybr = residualize(yb, cb) if controls else yb - yb.mean()
        if np.std(xbr) > 0 and np.std(ybr) > 0:
            bootstrap[index] = np.corrcoef(xbr, ybr)[0, 1]
    low, high = np.nanpercentile(bootstrap, [2.5, 97.5])

    loeo = []
    for index in range(len(data)):
        keep = np.arange(len(data)) != index
        xk = x[keep]
        yk = y[keep]
        ck = c[keep]
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
        "bootstrap_ci_low": float(low),
        "bootstrap_ci_high": float(high),
        "loeo_r_min": float(np.min(loeo)),
        "loeo_r_max": float(np.max(loeo)),
    }


def bh_fdr(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = np.minimum.accumulate((ranked * len(values) / np.arange(1, len(values) + 1))[::-1])[::-1]
    output = np.empty_like(values)
    output[order] = np.minimum(adjusted, 1.0)
    return output


def build_relationships(events: pd.DataFrame) -> pd.DataFrame:
    controls = ("q140_mar_apr_z",)
    tests = [
        (
            "lead_h20_to_tau", "Jan-Apr north H20 change -> MJJ central wind-stress response",
            "north_h20_change_jan_apr_zj", "jiang_tau_response_mjj_z", controls,
        ),
        (
            "lead_h20_to_precip", "Jan-Apr north H20 change -> MJJ precipitation response",
            "north_h20_change_jan_apr_zj", "precip_response_mjj", controls,
        ),
        (
            "lead_h20_to_slp", "Jan-Apr north H20 change -> MJJ SLP response",
            "north_h20_change_jan_apr_zj", "slp_response_mjj", controls,
        ),
        (
            "lead_h20_to_ne", "Jan-Apr north H20 change -> MJJ Jiang NE925",
            "north_h20_change_jan_apr_zj", "ne925_mjj_ms", controls,
        ),
        (
            "lead_flux_to_tau", "FMA one-sided Q5N -> MJJ wind-stress response",
            "q5n_fma_zj", "jiang_tau_response_mjj_z", controls,
        ),
        (
            "overlap_h20_to_peng", "Jan-Jun north H20 change -> Peng wind decoupling",
            "north_h20_change_jan_jun_zj", "peng_wind_decoupling_ms", controls,
        ),
        (
            "overlap_q_to_ne", "AMJ total Q5N -> MJJ Jiang NE925",
            "q5n_amj_zj", "ne925_mjj_ms", controls,
        ),
        (
            "overlap_nonekman_to_peng", "AMJ non-Ekman Q5N -> Peng wind decoupling",
            "q5n_nonekman_amj_zj", "peng_wind_decoupling_ms", controls,
        ),
    ]
    relationships = pd.DataFrame(
        [
            partial_stat(events, test_id, label, x, y, control, index)
            for index, (test_id, label, x, y, control) in enumerate(tests)
        ]
    )
    lead = relationships.test_id.str.startswith("lead_h20_to_")
    relationships["family_fdr_q"] = np.nan
    relationships.loc[lead, "family_fdr_q"] = bh_fdr(
        relationships.loc[lead, "permutation_p"].to_numpy(dtype=float)
    )
    return relationships


def build_window_sensitivity(events: pd.DataFrame) -> pd.DataFrame:
    windows = [
        ("Jan-Mar", "north_h20_change_jan_mar_zj"),
        ("Jan-Apr", "north_h20_change_jan_apr_zj"),
        ("Jan-May", "north_h20_change_jan_may_zj"),
        ("Jan-Jun", "north_h20_change_jan_jun_zj"),
    ]
    rows = []
    for index, (window, x) in enumerate(windows):
        row = partial_stat(
            events,
            f"window_{window.lower().replace('-', '_')}",
            f"{window} north H20 change -> MJJ wind-stress response",
            x,
            "jiang_tau_response_mjj_z",
            ("q140_mar_apr_z",),
            100 + index,
        )
        row["window"] = window
        rows.append(row)
    return pd.DataFrame(rows)


def build_control_sensitivity(events: pd.DataFrame) -> pd.DataFrame:
    controls = [
        ("None", ()),
        ("Q140 arrival", ("q140_mar_apr_z",)),
        ("East-ocean state", ("east_ocean_state_z",)),
        ("Q140 + FEP residual", ("q140_mar_apr_z", "mar_apr_fep_residual_c")),
        ("D20 at 140W", ("d140_mar_apr_z",)),
        ("Q140 + east-ocean state", ("q140_mar_apr_z", "east_ocean_state_z")),
    ]
    rows = []
    for index, (name, control) in enumerate(controls):
        row = partial_stat(
            events,
            f"control_{index}",
            f"Jan-Apr north H20 change -> MJJ wind-stress response | {name}",
            "north_h20_change_jan_apr_zj",
            "jiang_tau_response_mjj_z",
            control,
            200 + index,
        )
        row["control_set"] = name
        rows.append(row)
    return pd.DataFrame(rows)


def setup_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial Unicode MS", "PingFang SC", "Heiti SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.dpi": 400,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def add_highlight_scatter(axis: plt.Axes, frame: pd.DataFrame, x: str, y: str) -> None:
    ordinary = ~frame.year.isin(HIGHLIGHTS)
    axis.scatter(
        frame.loc[ordinary, x], frame.loc[ordinary, y], s=38,
        color="#9B9B9B", edgecolor="white", linewidth=0.6, zorder=3,
    )
    for year in HIGHLIGHTS:
        row = frame.loc[frame.year.eq(year)].iloc[0]
        axis.scatter(row[x], row[y], s=78, color=COLORS[year], edgecolor="white", linewidth=0.8, zorder=4)
        axis.annotate(str(year), (row[x], row[y]), xytext=(5, 5), textcoords="offset points", color=COLORS[year], fontsize=9)
    slope, intercept = np.polyfit(frame[x], frame[y], 1)
    xx = np.linspace(float(frame[x].min()), float(frame[x].max()), 100)
    axis.plot(xx, slope * xx + intercept, color="#263238", lw=1.5)
    axis.axhline(0, color="#888888", lw=0.7)
    axis.axvline(0, color="#888888", lw=0.7)


def plot_results(events: pd.DataFrame, relationships: pd.DataFrame, windows: pd.DataFrame) -> None:
    setup_style()
    OUT.mkdir(parents=True, exist_ok=True)
    lookup = relationships.set_index("test_id")
    figure, axes = plt.subplots(2, 2, figsize=(13.2, 9.2))
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.10, top=0.89, hspace=0.34, wspace=0.28)

    # Panel a: the budget establishes where the early receiver storage came from.
    axis = axes[0, 0]
    selected = events.set_index("year").loc[list(HIGHLIGHTS)]
    x = np.arange(3)
    components = [
        ("north_budget_south5n_fma_zj", "5°N输入", "#D95F02"),
        ("north_budget_zonal_fma_zj", "纬向辐合", "#4C78A8"),
        ("north_budget_surface_fma_zj", "海表热通量", "#59A14F"),
        ("north_budget_north12n_fma_zj", "12°N边界", "#B279A2"),
        ("north_budget_residual_fma_zj", "剩余项", "#9C755F"),
    ]
    positive = np.zeros(3)
    negative = np.zeros(3)
    for column, label, color in components:
        values = selected[column].to_numpy(dtype=float)
        bottoms = np.where(values >= 0, positive, negative)
        axis.bar(x, values, bottom=bottoms, width=0.62, color=color, label=label)
        positive += np.where(values >= 0, values, 0.0)
        negative += np.where(values < 0, values, 0.0)
    axis.scatter(x, selected["north_budget_storage_fma_zj"], marker="D", s=46, color="#111111", label="预算储量倾向", zorder=5)
    for index, year in enumerate(HIGHLIGHTS):
        delta = selected.loc[year, "north_h20_change_jan_apr_zj"]
        axis.text(index, max(positive[index], selected.loc[year, "north_budget_storage_fma_zj"]) + 0.10, f"ΔH₂₀={delta:+.2f}", ha="center", fontsize=9, fontweight="bold", color=COLORS[year])
    axis.axhline(0, color="#555555", lw=0.8)
    axis.set_xticks(x, [str(year) for year in HIGHLIGHTS])
    axis.set_ylabel("FMA累计暖量异常（ZJ）")
    axis.set_title("a  2023在MJJ之前已向北侧接收箱异常储热", loc="left", fontweight="bold")
    axis.legend(frameon=False, ncol=2, fontsize=8.2, loc="lower left")

    # Panel b: arrival-conditioned wind-stress response.
    axis = axes[0, 1]
    control = events[["q140_mar_apr_z"]].to_numpy(dtype=float)
    scatter = events[["year"]].copy()
    scatter["x"] = residualize(events["north_h20_change_jan_apr_zj"].to_numpy(dtype=float), control)
    scatter["y"] = residualize(events["jiang_tau_response_mjj_z"].to_numpy(dtype=float), control)
    add_highlight_scatter(axis, scatter, "x", "y")
    row = lookup.loc["lead_h20_to_tau"]
    axis.set_xlabel("北侧ΔH₂₀（Jan→Apr；已去除140°W到达量）")
    axis.set_ylabel("MJJ中太平洋风应力响应（条件残差）")
    axis.set_title("b  相同到达量下，北侧储热越强，风应力响应越弱", loc="left", fontweight="bold")
    axis.text(0.04, 0.95, f"partial r={row.partial_r:+.2f}\npermutation p={row.permutation_p:.3f}\n95% CI [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]", transform=axis.transAxes, va="top", fontsize=9)

    # Panel c: the atmospheric bridge begins with a weaker precipitation response.
    axis = axes[1, 0]
    scatter["y"] = residualize(events["precip_response_mjj"].to_numpy(dtype=float), control)
    add_highlight_scatter(axis, scatter, "x", "y")
    row = lookup.loc["lead_h20_to_precip"]
    axis.set_xlabel("北侧ΔH₂₀（Jan→Apr；已去除140°W到达量）")
    axis.set_ylabel("MJJ降水响应（条件残差）")
    axis.set_title("c  北侧储热同时对应更弱的对流/降水响应", loc="left", fontweight="bold")
    axis.text(0.04, 0.95, f"partial r={row.partial_r:+.2f}\npermutation p={row.permutation_p:.3f}\n95% CI [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]", transform=axis.transAxes, va="top", fontsize=9)

    # Panel d: time-order and direction audit.
    axis = axes[1, 1]
    labels = windows["window"].tolist() + ["FMA Q₅N→τ", "AMJ Q₅N→NE\n(时间重叠)"]
    values = windows["partial_r"].tolist() + [
        float(lookup.loc["lead_flux_to_tau", "partial_r"]),
        float(lookup.loc["overlap_q_to_ne", "partial_r"]),
    ]
    lows = windows["bootstrap_ci_low"].tolist() + [
        float(lookup.loc["lead_flux_to_tau", "bootstrap_ci_low"]),
        float(lookup.loc["overlap_q_to_ne", "bootstrap_ci_low"]),
    ]
    highs = windows["bootstrap_ci_high"].tolist() + [
        float(lookup.loc["lead_flux_to_tau", "bootstrap_ci_high"]),
        float(lookup.loc["overlap_q_to_ne", "bootstrap_ci_high"]),
    ]
    positions = np.arange(len(labels))
    colors = ["#4C78A8"] * 4 + ["#9B9B9B", "#D95F02"]
    for value, position, low, high, color in zip(values, positions, lows, highs, colors, strict=True):
        axis.errorbar(
            value,
            position,
            xerr=np.array([[value - low], [high - value]]),
            fmt="o",
            color=color,
            ecolor=color,
            markersize=7,
            elinewidth=2,
            capsize=3,
            zorder=4,
        )
    axis.axvline(0, color="#666666", lw=0.8)
    axis.set_yticks(positions, labels)
    axis.invert_yaxis()
    axis.set_xlim(-1.05, 1.05)
    axis.set_xlabel("与后续大气响应的偏相关")
    axis.set_title("d  领先证据在4月形成；同期关系仍可能含反向反馈", loc="left", fontweight="bold")

    figure.suptitle("暖量命运可能参与2023海气脱耦：关键不是到达量，而是MJJ之前储存在哪里", fontsize=15, fontweight="bold", y=0.965)
    figure.text(0.5, 0.025, "SODA3 H₂₀北侧接收箱：5°–12°N, 140°W–80°W, 0–300 m；13个暖事件；主检验控制Mar–Apr跨140°W暖量到达", ha="center", fontsize=9.2, color="#333333")
    figure.savefig(FIG_PNG, bbox_inches="tight", facecolor="white")
    figure.savefig(FIG_PDF, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def write_report(events: pd.DataFrame, relationships: pd.DataFrame, windows: pd.DataFrame, controls: pd.DataFrame) -> None:
    lookup = relationships.set_index("test_id")
    main = lookup.loc["lead_h20_to_tau"]
    precip = lookup.loc["lead_h20_to_precip"]
    slp = lookup.loc["lead_h20_to_slp"]
    ne = lookup.loc["lead_h20_to_ne"]
    flux = lookup.loc["lead_flux_to_tau"]
    overlap = lookup.loc["overlap_q_to_ne"]
    selected = events.set_index("year").loc[list(HIGHLIGHTS)]
    lines = [
        "# 早期暖量命运是否影响海气脱耦",
        "",
        "## 结论",
        "",
        "**现在可以把原先的否定结论改为：该假设获得了值得继续检验的领先观测证据，但尚未形成因果闭环。**",
        "",
        f"在控制Mar—Apr跨140°W暖量到达后，Jan—Apr北侧接收箱H20异常增长越强，MJJ中太平洋风应力响应越弱（partial r={main.partial_r:+.2f}, permutation p={main.permutation_p:.3f}, 95% bootstrap CI [{main.bootstrap_ci_low:+.2f}, {main.bootstrap_ci_high:+.2f}]）。逐事件留一检验范围为[{main.loeo_r_min:+.2f}, {main.loeo_r_max:+.2f}]，说明关系不是由2023一个点单独制造。",
        f"同一早期北侧储热还对应更弱的MJJ降水响应（r={precip.partial_r:+.2f}, p={precip.permutation_p:.3f}）和SLP响应（r={slp.partial_r:+.2f}, p={slp.permutation_p:.3f}）。它与Jiang型NE925的正关系为r={ne.partial_r:+.2f}，但p={ne.permutation_p:.3f}，尚未达到稳健事件尺度显著性。",
        "",
        "因此最合理的当前解释是：**暖量在到达东太平洋后，如果在发展年早期更多进入并储存在5°N以北，而不是维持赤道—中太平洋的集中暖结构，后续深对流、气压和西风应力响应可能更弱，从而提高脱耦概率。**",
        "",
        "## 2023为什么关键",
        "",
        "| 事件 | 北侧H20 Jan→Apr | FMA 5°N输入 | FMA纬向辐合 | FMA海表项 | MJJ风应力响应 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in HIGHLIGHTS:
        row = selected.loc[year]
        lines.append(
            f"| {year} | {row.north_h20_change_jan_apr_zj:+.2f} ZJ | {row.north_budget_south5n_fma_zj:+.2f} ZJ | {row.north_budget_zonal_fma_zj:+.2f} ZJ | {row.north_budget_surface_fma_zj:+.2f} ZJ | {row.jiang_tau_response_mjj_z:+.2f} SD |"
        )
    lines += [
        "",
        "2023北侧H20从1月到4月增加+0.77 ZJ；1997和2015反而分别减少-0.27和-0.29 ZJ。2023的FMA北侧预算中，5°N输入为+0.61 ZJ、纬向辐合为+0.34 ZJ、海表项为+0.29 ZJ，12°N边界为-0.30 ZJ、剩余项为-0.11 ZJ，合计储量倾向+0.84 ZJ。预算项使用实际月秒数积分；它与月中Jan→Apr储量差的0.06 ZJ差异来自中心差分与积分窗口错位，不是空间预算不闭合。",
        "",
        "## 为什么这次方向没有再搞反",
        "",
        "- 原因窗：Jan(0)—Apr(0)北侧H20异常增长。",
        "- 结果窗：May(0)—Jul(0)降水、SLP和风应力响应。",
        "- 条件变量：Mar—Apr跨140°W暖量到达，保证比较的是相近到达背景下的不同路由。",
        "- AMJ Q5N与MJJ东北风的关系单列为反馈证据，不用于证明海洋先触发大气。",
        "",
        "## 领先关系与反馈关系",
        "",
        f"严格领先的FMA单断面Q5N本身不能稳健解释MJJ风应力响应（r={flux.partial_r:+.2f}, p={flux.permutation_p:.3f}）；真正有信息的是北侧箱体最终储存了多少。这说明“命运”不能只用某一条边界通量表示，还必须看接收箱储量及其他边界。",
        f"AMJ总Q5N与MJJ东北风关系较强（r={overlap.partial_r:+.2f}, p={overlap.permutation_p:.3f}），但两个时间窗重叠。已有逐月检验还显示同期NE→Q5N关系强于Q5N→下一月NE，因此这部分只能解释为双向反馈或共同驱动，不能当作海洋先行证据。",
        "",
        "## 时间窗敏感性",
        "",
        "| 海洋窗口 | 与MJJ风应力响应的偏相关 | permutation p | 95% CI |",
        "|---|---:|---:|---:|",
    ]
    for _, row in windows.iterrows():
        lines.append(
            f"| {row.window} | {row.partial_r:+.2f} | {row.permutation_p:.3f} | [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}] |"
        )
    lines += [
        "",
        "信号在Jan—Mar尚弱，到Jan—Apr明显增强，时间顺序与“4月前海洋配置影响MJJ大气响应”一致。Jan—May和Jan—Jun包含越来越多的大气响应期，只作为持续性敏感性。",
        "",
        "## 控制变量敏感性",
        "",
        "| 控制集合 | partial r | permutation p |",
        "|---|---:|---:|",
    ]
    for _, row in controls.iterrows():
        lines.append(f"| {row.control_set} | {row.partial_r:+.2f} | {row.permutation_p:.3f} |")
    lines += [
        "",
        "控制140°W到达量或东部综合海洋状态时，关系仍为负；但单独控制140°W D20后明显减弱。这说明D20大尺度温跃层结构可能是共同原因，也可能正是“暖量空间配置”路径的一部分。仅凭观测回归不能区分这两种解释。",
        "",
        "## 当前能说和不能说",
        "",
        "可以说：2023在严重脱耦之前已出现异常早的北侧暖量储存；跨事件中，这种北侧储热在相同到达背景下稳健对应更弱的后续风应力、降水和SLP响应。暖量命运影响脱耦因此成为一个有数据支持的候选机制。",
        "",
        "不能说：北侧H20已经被证明直接造成东北风或海气脱耦。北侧SST、降水偶极子和NE风之间的完整中介链尚未闭合，且D20共同控制仍是竞争解释。",
        "",
        "## 下一步决定性实验",
        "",
        "做固定总暖量的AGCM/耦合敏感性试验：保持赤道东太平洋总到达量和SST大尺度幅度相近，只改变暖量/暖SST在赤道带与5°—12°N之间的分配。若北移配置能够系统性减弱中太平洋降水、SLP梯度和西风响应，才可把当前统计链推进为机制证据。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = build_events()
    relationships = build_relationships(events)
    windows = build_window_sensitivity(events)
    controls = build_control_sensitivity(events)
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    relationships.to_csv(REL_CSV, index=False, float_format="%.9g")
    windows.to_csv(WINDOW_CSV, index=False, float_format="%.9g")
    controls.to_csv(CONTROL_CSV, index=False, float_format="%.9g")
    plot_results(events, relationships, windows)
    write_report(events, relationships, windows, controls)
    diagnostics = {
        "receiver_box": "5-12N, 140W-80W, 0-300 m",
        "receiver_anomaly_baseline": "calendar-month detrended 1980-2022",
        "strict_lead_ocean_window": "Jan-Apr(0)",
        "atmospheric_target_window": "May-Jul(0)",
        "primary_control": "Mar-Apr Q20 arrival across 140W",
        "n_events": len(events),
        "event_years": list(EVENT_YEARS),
        "time_weighting": "actual calendar-month seconds for PW-to-ZJ integration",
        "note": "AMJ/MJJ associations overlap and are classified as feedback, not initiation.",
    }
    DIAGNOSTICS.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(EVENT_CSV)
    print(REL_CSV)
    print(WINDOW_CSV)
    print(CONTROL_CSV)
    print(FIG_PNG)
    print(FIG_PDF)
    print(REPORT)


if __name__ == "__main__":
    main()
