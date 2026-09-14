#!/usr/bin/env python3
"""Adapt Peng et al.'s expected-response calculation to the JJA growth stage.

The time window is deliberately JJA rather than Peng et al.'s June--January
window.  The Peng-style element retained here is the simple expected-response
calculation: each JJA atmospheric response is regressed only on JJA Nino-3
SSTA over 1982--2023.  Observed-minus-expected standardized residuals are used
for cross-event statistics.  Observed/expected ratios are retained as a 2023
diagnostic but are not used as the primary cross-event outcome because they
are singular when the expected response is close to zero.

The ocean predictor is the existing JFM off-equatorial 0--300 m OHC residual
after the three-band total OHC has been controlled.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/enso_3d_warm_heat_spreading_decoupling"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig_peng_style_jja"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache_peng_style_jja"))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib
import numpy as np
import pandas as pd
from scipy import stats


matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(ROOT / "scripts"))
from climate_plot_style import add_panel_labels, apply_climate_style, save_figure  # noqa: E402


MONTHLY_CSV = DERIVED / "enso_full_year_coupling_monthly_1982_2024.csv"
OCEAN_CSV = DERIVED / "enso_3d_warm_heat_spreading_event_metrics.csv"
EVENT_CSV = DERIVED / "enso_peng_style_jja_broadening_event_table.csv"
STATS_CSV = DERIVED / "enso_peng_style_jja_broadening_statistics.csv"
FITS_CSV = DERIVED / "enso_peng_style_jja_expected_response_fits.csv"
DIAGNOSTICS_JSON = DERIVED / "enso_peng_style_jja_broadening_diagnostics.json"
FIG_PNG = OUT_DIR / "enso_peng_style_jja_broadening_response_en.png"
FIG_PDF = OUT_DIR / "enso_peng_style_jja_broadening_response_en.pdf"
REPORT_MD = OUT_DIR / "PENG_STYLE_JJA_BROADENING_RESPONSE_CN.md"

EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = (1997, 2015, 2023)
COLORS = {1997: "#2f6da5", 2015: "#d98c27", 2023: "#b23a3a"}
CLIMATOLOGY_YEARS = (1982, 2022)
FIT_YEARS = (1982, 2023)
JJA_MONTHS = (6, 7, 8)
N_PERMUTATIONS = 10_000
N_BOOTSTRAP = 5_000
SEED = 20260818

PREDICTOR = {
    "source": "nino3_raw_c",
    "prefix": "nino3",
    "label": "Niño-3 SSTA",
    "unit": "degC",
}
RESPONSES = (
    {
        "source": "precip_tropical_pacific_raw_mmday",
        "prefix": "precip",
        "label": "Equatorial Pacific rainfall",
        "short_label": "Rainfall",
        "unit": "mm day-1",
        "group": "primary",
    },
    {
        "source": "slp_drive_w_minus_e_raw_hpa",
        "prefix": "slp_drive",
        "label": "West-minus-east SLP drive",
        "short_label": "SLP drive",
        "unit": "hPa",
        "group": "primary",
    },
    {
        "source": "tau_cwp_raw_nm2",
        "prefix": "wind_stress",
        "label": "Central-western Pacific zonal wind stress",
        "short_label": "Wind stress",
        "unit": "N m-2",
        "group": "primary",
    },
    {
        "source": "cwp_u_sig995",
        "prefix": "ncep_near_surface_wind",
        "label": "NCEP central-western Pacific near-surface wind",
        "short_label": "NCEP wind",
        "unit": "m s-1",
        "group": "peng_analog",
    },
    {
        "source": "minus_soi_like_ncep",
        "prefix": "ncep_minus_soi",
        "label": "NCEP minus-SOI-like pressure response",
        "short_label": "NCEP -SOI",
        "unit": "standardized index",
        "group": "peng_analog",
    },
)


def require_inputs() -> None:
    missing = [str(path) for path in (MONTHLY_CSV, OCEAN_CSV) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required input files: {missing}")


def fdr_bh(p_values: np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.minimum(adjusted, 1.0)
    return output


def build_jja_expected_response() -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = pd.read_csv(MONTHLY_CSV)
    required = [PREDICTOR["source"]] + [item["source"] for item in RESPONSES]
    required_columns = {"year", "month", *required}
    absent = sorted(required_columns.difference(monthly.columns))
    if absent:
        raise ValueError(f"Monthly coupling table lacks columns: {absent}")

    monthly = monthly.loc[
        monthly["year"].between(FIT_YEARS[0], FIT_YEARS[1]),
        ["year", "month", *required],
    ].copy()
    climatology_mask = monthly["year"].between(*CLIMATOLOGY_YEARS)
    climatology = monthly.loc[climatology_mask].groupby("month")[required].mean()
    for variable in required:
        monthly[f"{variable}_anom"] = (
            monthly[variable] - monthly["month"].map(climatology[variable])
        )

    jja_source = monthly.loc[monthly["month"].isin(JJA_MONTHS)].copy()
    month_counts = jja_source.groupby("year")["month"].nunique()
    expected_years = np.arange(FIT_YEARS[0], FIT_YEARS[1] + 1)
    if not month_counts.reindex(expected_years).eq(3).all():
        raise ValueError("Every fit year must contain June, July, and August")

    anomaly_columns = [f"{variable}_anom" for variable in required]
    jja = jja_source.groupby("year", as_index=False)[anomaly_columns].mean()
    jja = jja.rename(
        columns={
            f"{PREDICTOR['source']}_anom": "nino3_jja_anom_c",
            **{
                f"{item['source']}_anom": f"{item['prefix']}_jja_anom"
                for item in RESPONSES
            },
        }
    )

    x = jja["nino3_jja_anom_c"].to_numpy(dtype=float)
    fit_rows: list[dict[str, float | int | str]] = []
    for item in RESPONSES:
        prefix = item["prefix"]
        observed_name = f"{prefix}_jja_anom"
        expected_name = f"{prefix}_jja_expected"
        residual_name = f"{prefix}_jja_residual"
        residual_z_name = f"{prefix}_jja_residual_z"
        ratio_name = f"{prefix}_jja_observed_expected_ratio"
        y = jja[observed_name].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        expected = intercept + slope * x
        residual = y - expected
        residual_sigma = float(np.std(residual, ddof=2))
        jja[expected_name] = expected
        jja[residual_name] = residual
        jja[residual_z_name] = residual / residual_sigma
        jja[ratio_name] = np.divide(
            y,
            expected,
            out=np.full_like(y, np.nan),
            where=np.abs(expected) > 1.0e-12,
        )
        fit_rows.append(
            {
                "response": prefix,
                "response_label": item["label"],
                "group": item["group"],
                "unit": item["unit"],
                "fit_start_year": FIT_YEARS[0],
                "fit_end_year": FIT_YEARS[1],
                "n_years": len(jja),
                "slope_per_degC": float(slope),
                "intercept": float(intercept),
                "residual_sigma": residual_sigma,
                "fit_r": float(np.corrcoef(x, y)[0, 1]),
            }
        )

    primary_z = [
        f"{item['prefix']}_jja_residual_z"
        for item in RESPONSES
        if item["group"] == "primary"
    ]
    analog_z = [
        f"{item['prefix']}_jja_residual_z"
        for item in RESPONSES
        if item["group"] == "peng_analog"
    ]
    jja["primary_three_field_composite_residual_z"] = jja[primary_z].mean(axis=1)
    jja["ncep_peng_analog_composite_residual_z"] = jja[analog_z].mean(axis=1)
    jja["jja_nino3_ge_0p5"] = jja["nino3_jja_anom_c"] >= 0.5
    return jja, pd.DataFrame(fit_rows)


def build_event_table(jja: pd.DataFrame) -> pd.DataFrame:
    ocean = pd.read_csv(OCEAN_CSV)
    needed = [
        "year",
        "broadening_residual_full_gjm2_jfm",
        "total_full_0_300_gjm2_jfm",
    ]
    absent = sorted(set(needed).difference(ocean.columns))
    if absent:
        raise ValueError(f"Ocean event table lacks columns: {absent}")
    ocean = ocean.loc[ocean["year"].isin(EVENTS), needed].copy()
    output = ocean.merge(jja, on="year", how="left", validate="one_to_one")
    output = output.set_index("year").reindex(EVENTS).reset_index()
    if output.select_dtypes(include=[np.number]).isna().any().any():
        raise ValueError("Merged event table contains missing numeric values")
    return output


def relationship(
    table: pd.DataFrame,
    y_name: str,
    *,
    test_id: str,
    family: str,
    nino3_ge_0p5_only: bool = False,
    seed_offset: int = 0,
) -> dict[str, float | int | str | bool]:
    data = table.loc[table["jja_nino3_ge_0p5"]].copy() if nino3_ge_0p5_only else table.copy()
    x = data["broadening_residual_full_gjm2_jfm"].to_numpy(dtype=float)
    y = data[y_name].to_numpy(dtype=float)
    pearson = stats.pearsonr(x, y)
    rng = np.random.default_rng(SEED + seed_offset)
    permutation_r = np.empty(N_PERMUTATIONS, dtype=float)
    for index in range(N_PERMUTATIONS):
        permutation_r[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    permutation_p = float(
        (np.sum(np.abs(permutation_r) >= abs(pearson.statistic)) + 1)
        / (N_PERMUTATIONS + 1)
    )

    bootstrap_r = np.full(N_BOOTSTRAP, np.nan, dtype=float)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(data), len(data))
        if np.std(x[sample]) > 0 and np.std(y[sample]) > 0:
            bootstrap_r[index] = np.corrcoef(x[sample], y[sample])[0, 1]
    ci_low, ci_high = np.nanpercentile(bootstrap_r, [2.5, 97.5])

    leave_one_out = []
    if len(data) > 3:
        for omitted in range(len(data)):
            keep = np.arange(len(data)) != omitted
            leave_one_out.append(float(np.corrcoef(x[keep], y[keep])[0, 1]))
    return {
        "test_id": test_id,
        "family": family,
        "response_column": y_name,
        "nino3_ge_0p5_only": nino3_ge_0p5_only,
        "n_events": len(data),
        "pearson_r": float(pearson.statistic),
        "analytic_p": float(pearson.pvalue),
        "spearman_r": float(stats.spearmanr(x, y).statistic),
        "permutation_p": permutation_p,
        "bootstrap_ci_low": float(ci_low),
        "bootstrap_ci_high": float(ci_high),
        "loeo_r_min": float(np.min(leave_one_out)) if leave_one_out else np.nan,
        "loeo_r_max": float(np.max(leave_one_out)) if leave_one_out else np.nan,
    }


def build_statistics(table: pd.DataFrame) -> pd.DataFrame:
    definitions = [
        (
            "primary_composite_all",
            "primary_composite",
            "primary_three_field_composite_residual_z",
            False,
        ),
        ("precip_all", "primary_components", "precip_jja_residual_z", False),
        ("slp_drive_all", "primary_components", "slp_drive_jja_residual_z", False),
        ("wind_stress_all", "primary_components", "wind_stress_jja_residual_z", False),
        (
            "ncep_analog_composite_all",
            "ncep_analog_composite",
            "ncep_peng_analog_composite_residual_z",
            False,
        ),
        ("ncep_wind_all", "ncep_analog_components", "ncep_near_surface_wind_jja_residual_z", False),
        ("ncep_minus_soi_all", "ncep_analog_components", "ncep_minus_soi_jja_residual_z", False),
        (
            "primary_composite_nino3_ge_0p5",
            "warm_jja_sensitivity",
            "primary_three_field_composite_residual_z",
            True,
        ),
    ]
    rows = [
        relationship(
            table,
            y_name,
            test_id=test_id,
            family=family,
            nino3_ge_0p5_only=warm_only,
            seed_offset=index,
        )
        for index, (test_id, family, y_name, warm_only) in enumerate(definitions)
    ]
    output = pd.DataFrame(rows)
    output["permutation_q_fdr"] = np.nan
    for family in output["family"].unique():
        mask = output["family"].eq(family)
        output.loc[mask, "permutation_q_fdr"] = fdr_bh(
            output.loc[mask, "permutation_p"].to_numpy(dtype=float)
        )
    return output


def add_event_scatter(
    ax: plt.Axes,
    table: pd.DataFrame,
    statistics: pd.DataFrame,
    *,
    y_name: str,
    test_id: str,
    title: str,
    ylabel: str,
    stats_location: str,
) -> None:
    x = table["broadening_residual_full_gjm2_jfm"].to_numpy(dtype=float)
    y = table[y_name].to_numpy(dtype=float)
    years = table["year"].to_numpy(dtype=int)
    ax.scatter(x, y, s=48, color="#777777", edgecolor="white", linewidth=0.8, zorder=3)
    slope, intercept = np.polyfit(x, y, 1)
    grid = np.linspace(x.min() - 0.015, x.max() + 0.015, 100)
    ax.plot(grid, intercept + slope * grid, color="#333333", linewidth=1.5, zorder=2)
    for index, year in enumerate(years):
        if year in HIGHLIGHTS:
            color = COLORS[year]
            ax.scatter(
                x[index], y[index], s=82, color=color, edgecolor="white", linewidth=0.9, zorder=4
            )
            offset = (6, 5) if year != 2015 else (-28, 5)
            ax.annotate(
                str(year),
                (x[index], y[index]),
                xytext=offset,
                textcoords="offset points",
                color=color,
                fontweight="bold",
                fontsize=9,
            )
    row = statistics.loc[statistics["test_id"].eq(test_id)].iloc[0]
    if stats_location == "top_right":
        stats_x, stats_y, stats_ha, stats_va = 0.96, 0.96, "right", "top"
    elif stats_location == "bottom_left":
        stats_x, stats_y, stats_ha, stats_va = 0.04, 0.05, "left", "bottom"
    else:
        raise ValueError(f"Unknown stats location: {stats_location}")
    ax.text(
        stats_x,
        stats_y,
        f"r = {row.pearson_r:+.2f}\nperm. p = {row.permutation_p:.3f}\n"
        f"95% CI [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]",
        transform=ax.transAxes,
        ha=stats_ha,
        va=stats_va,
        fontsize=9,
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": "white",
            "edgecolor": "#c7c7c7",
            "alpha": 0.92,
        },
    )
    ax.axhline(0, color="#aaaaaa", linewidth=0.8, linestyle="--")
    ax.axvline(0, color="#dddddd", linewidth=0.8)
    ax.set_title(title, loc="left", pad=8)
    ax.set_xlabel("JFM off-equatorial OHC residual (GJ m$^{-2}$)")
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)


def make_figure(table: pd.DataFrame, statistics: pd.DataFrame) -> None:
    apply_climate_style(base_font_size=10)
    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.8))

    current = table.loc[table["year"].eq(2023)].iloc[0]
    items = [item for item in RESPONSES if item["group"] == "primary"]
    ratios = np.array(
        [current[f"{item['prefix']}_jja_observed_expected_ratio"] for item in items]
    ) * 100.0
    labels = [item["short_label"] for item in items]
    bar_colors = ["#d98c27", "#c85a4a", "#a72f35"]
    positions = np.arange(len(items))
    axes[0, 0].bar(positions, ratios, color=bar_colors, width=0.66)
    axes[0, 0].axhline(100, color="#333333", linewidth=1.2, linestyle="--")
    for position, value in zip(positions, ratios):
        axes[0, 0].text(position, value + 3.0, f"{value:.0f}%", ha="center", va="bottom", fontsize=9.5)
    axes[0, 0].text(
        0.98,
        0.95,
        f"2023 JJA Niño-3 = {current.nino3_jja_anom_c:+.2f} °C",
        transform=axes[0, 0].transAxes,
        ha="right",
        va="top",
        fontsize=9,
    )
    axes[0, 0].set_xticks(positions, labels)
    axes[0, 0].set_ylim(0, 122)
    axes[0, 0].set_ylabel("Observed / expected response (%)")
    axes[0, 0].set_title("2023 response was below the Niño-3-based expectation", loc="left", pad=8)
    axes[0, 0].spines[["top", "right"]].set_visible(False)

    add_event_scatter(
        axes[0, 1],
        table,
        statistics,
        y_name="primary_three_field_composite_residual_z",
        test_id="primary_composite_all",
        title="Broader early OHC tends to precede a weaker JJA response",
        ylabel="Three-field response residual (z)",
        stats_location="top_right",
    )

    forest_ids = ["primary_composite_all", "precip_all", "slp_drive_all", "wind_stress_all"]
    forest_labels = ["Three-field composite", "Rainfall", "SLP drive", "Wind stress"]
    forest = statistics.set_index("test_id").loc[forest_ids]
    y_positions = np.arange(len(forest_ids))[::-1]
    values = forest["pearson_r"].to_numpy(dtype=float)
    low = forest["bootstrap_ci_low"].to_numpy(dtype=float)
    high = forest["bootstrap_ci_high"].to_numpy(dtype=float)
    axes[1, 0].errorbar(
        values,
        y_positions,
        xerr=np.vstack([values - low, high - values]),
        fmt="o",
        color="#555555",
        ecolor="#999999",
        capsize=3,
        markersize=6,
    )
    axes[1, 0].scatter(values[1], y_positions[1], s=58, color="#b23a3a", zorder=4)
    axes[1, 0].axvline(0, color="#aaaaaa", linewidth=0.9, linestyle="--")
    axes[1, 0].set_yticks(y_positions, forest_labels)
    axes[1, 0].set_xlim(-1.05, 1.05)
    axes[1, 0].set_xlabel("Correlation with JFM OHC broadening residual")
    axes[1, 0].set_title("The cross-event signal is rainfall-dominated", loc="left", pad=8)
    axes[1, 0].spines[["top", "right", "left"]].set_visible(False)
    axes[1, 0].tick_params(axis="y", length=0)

    add_event_scatter(
        axes[1, 1],
        table,
        statistics,
        y_name="ncep_peng_analog_composite_residual_z",
        test_id="ncep_analog_composite_all",
        title="The closest Peng-variable analog is not robust across events",
        ylabel="NCEP wind and -SOI residual (z)",
        stats_location="bottom_left",
    )

    add_panel_labels(axes.ravel(), x=-0.09, y=1.035)
    fig.tight_layout(rect=[0.015, 0.015, 0.99, 0.90], h_pad=2.4, w_pad=2.0)
    fig.suptitle(
        "Peng-style JJA expected-response test",
        fontsize=15,
        fontweight="bold",
        y=0.975,
    )
    fig.text(
        0.5,
        0.942,
        "JJA atmospheric anomalies conditioned only on concurrent JJA Niño-3 SSTA; 13 warm events",
        ha="center",
        va="bottom",
        fontsize=10.5,
        color="#444444",
    )
    save_figure(fig, FIG_PNG, dpi=300)
    save_figure(fig, FIG_PDF, dpi=300)
    plt.close(fig)


def format_p(value: float) -> str:
    return "<0.001" if value < 0.001 else f"{value:.3f}"


def write_report(table: pd.DataFrame, statistics: pd.DataFrame, fits: pd.DataFrame) -> None:
    current = table.loc[table["year"].eq(2023)].iloc[0]
    primary = statistics.loc[statistics["test_id"].eq("primary_composite_all")].iloc[0]
    precip = statistics.loc[statistics["test_id"].eq("precip_all")].iloc[0]
    slp = statistics.loc[statistics["test_id"].eq("slp_drive_all")].iloc[0]
    wind = statistics.loc[statistics["test_id"].eq("wind_stress_all")].iloc[0]
    analog = statistics.loc[statistics["test_id"].eq("ncep_analog_composite_all")].iloc[0]
    warm = statistics.loc[
        statistics["test_id"].eq("primary_composite_nino3_ge_0p5")
    ].iloc[0]
    ratio_lines = []
    for item in RESPONSES:
        ratio = 100.0 * current[f"{item['prefix']}_jja_observed_expected_ratio"]
        residual = current[f"{item['prefix']}_jja_residual_z"]
        ratio_lines.append(
            f"- {item['label']}：观测/预期 = {ratio:+.1f}%，残差 = {residual:+.2f} z。"
        )

    fit_lines = []
    for row in fits.itertuples(index=False):
        fit_lines.append(
            f"- {row.response_label}：斜率 {row.slope_per_degC:+.4f} {row.unit}/°C，"
            f"截距 {row.intercept:+.4f} {row.unit}，残差标准差 {row.residual_sigma:.4f} {row.unit}。"
        )

    report = rf"""# Peng式JJA预期响应与早期OHC展宽

## 一句话结果

把时间固定在我们关心的JJA发展期，只采用Peng等人的“一元SST预期响应”算法后，JFM离赤道OHC展宽与随后JJA三项综合大气响应残差的相关为 **r={primary.pearson_r:+.2f}**（13次事件，置换p={format_p(primary.permutation_p)}，bootstrap 95%区间[{primary.bootstrap_ci_low:+.2f}, {primary.bootstrap_ci_high:+.2f}]）。方向仍然是“越宽，后续响应越弱”，但强度和稳健性明显弱于此前控制SST强度、EP–CP型态和趋势的版本（此前约r=-0.81）。

更重要的是，这个相关主要来自降水，而不是风和气压三者共同提供同等强度的证据。因此它适合写成**补充敏感性检验**，不适合替代当前主结果。

## 这是不是Peng原文的时间平均

不是。本版本按你的要求使用JJA，不采用Peng原文的6月至次年1月。保留下来的只有核心计算形式：

\[
A_{{\mathrm{{JJA}},y}}=a+b\,\mathrm{{Ni\tilde{{n}}o3}}_{{\mathrm{{JJA}},y}}+\epsilon_y.
\]

其中回归样本为1982—2023年全部42年，和Peng公开代码一样使用整段样本直接拟合，不做EP–CP型态控制、长期趋势控制或逐年留一预测。

## 月异常和季节平均

1. 对Niño-3及每个大气量，先减去1982—2022年各同历月气候态；
2. 对6、7、8月异常取平均，得到每年的JJA异常；
3. 用42个年份拟合上式；
4. 预期响应为 \(\hat A_y=a+b\,\mathrm{{Ni\tilde{{n}}o3}}_y\)；
5. 用于跨事件相关的量为标准化差值：

\[
R_y=\frac{{A_y-\hat A_y}}{{\sigma_\epsilon}}.
\]

\(R_y>0\) 表示大气响应强于相同JJA Niño-3条件下的线性预期，\(R_y<0\) 表示弱于预期。它表示相对响应效率，不表示该年没有形成El Niño耦合。

## 三项主响应

- GPCP赤道太平洋降水；
- ERA5西减东海平面气压驱动；
- ERA5中西太平洋纬向风应力。

三项分别回归并标准化后等权平均：

\[
C_{{\mathrm{{Peng-JJA}}}}=\frac{{R_{{P}}+R_{{SLP}}+R_{{\tau}}}}{{3}}.
\]

这就是主散点图的纵轴。横轴仍是原来的JFM 0—300 m离赤道OHC残差：先用南、北两侧OHC平均表示离赤道暖量，再剔除三纬带总OHC的线性影响。因此本轮没有在纵轴上再控制一次总OHC。

## 42年预期响应拟合系数

{chr(10).join(fit_lines)}

## 跨13次事件的结果

| JJA响应量 | Pearson r | 置换p | bootstrap 95%区间 | 逐事件剔除r范围 |
|---|---:|---:|---:|---:|
| 三项综合 | {primary.pearson_r:+.3f} | {primary.permutation_p:.4f} | [{primary.bootstrap_ci_low:+.3f}, {primary.bootstrap_ci_high:+.3f}] | [{primary.loeo_r_min:+.3f}, {primary.loeo_r_max:+.3f}] |
| 降水 | {precip.pearson_r:+.3f} | {precip.permutation_p:.4f} | [{precip.bootstrap_ci_low:+.3f}, {precip.bootstrap_ci_high:+.3f}] | [{precip.loeo_r_min:+.3f}, {precip.loeo_r_max:+.3f}] |
| SLP驱动 | {slp.pearson_r:+.3f} | {slp.permutation_p:.4f} | [{slp.bootstrap_ci_low:+.3f}, {slp.bootstrap_ci_high:+.3f}] | [{slp.loeo_r_min:+.3f}, {slp.loeo_r_max:+.3f}] |
| 风应力 | {wind.pearson_r:+.3f} | {wind.permutation_p:.4f} | [{wind.bootstrap_ci_low:+.3f}, {wind.bootstrap_ci_high:+.3f}] | [{wind.loeo_r_min:+.3f}, {wind.loeo_r_max:+.3f}] |
| NCEP风与-SOI近似综合 | {analog.pearson_r:+.3f} | {analog.permutation_p:.4f} | [{analog.bootstrap_ci_low:+.3f}, {analog.bootstrap_ci_high:+.3f}] | [{analog.loeo_r_min:+.3f}, {analog.loeo_r_max:+.3f}] |

其中降水单项关系最强（r={precip.pearson_r:+.2f}）；SLP和风应力只有同方向的弱到中等关系。最接近Peng原始变量的NCEP近地面风与-SOI综合仅为r={analog.pearson_r:+.2f}，没有形成稳健的跨事件支撑。

只保留JJA Niño-3已达到0.5°C的6次事件，三项综合相关为r={warm.pearson_r:+.2f}（置换p={format_p(warm.permutation_p)}）。这个结果方向更强，但样本只有6个，应只作为预先可解释的阈值敏感性，不宜作为主证据。

## 2023年的具体结果

- JJA Niño-3异常：{current.nino3_jja_anom_c:+.2f}°C；
- JFM离赤道OHC展宽残差：{current.broadening_residual_full_gjm2_jfm:+.3f} GJ m⁻²；
- 三项综合预期响应残差：{current.primary_three_field_composite_residual_z:+.2f} z；
- NCEP风与-SOI近似综合残差：{current.ncep_peng_analog_composite_residual_z:+.2f} z。

各分量：

{chr(10).join(ratio_lines)}

2023在所有五个大气量上都弱于该JJA Niño-3对应的线性预期。因此，这一算法仍支持“2023发展期的海气响应效率偏低”；它不等于说2023成熟期仍处于脱耦状态。

## 为什么跨事件不用观测/预期比值

Peng原文的观测/预期百分比适合其筛选出的强事件和较长平均窗，但在本研究13个事件的JJA中，有些年份Niño-3接近零甚至为负，回归预期值也接近零。此时哪怕很小的观测异常也会产生几十倍、上千倍的比值。例如2004年JJA Niño-3仅约+0.05°C，所以比值会数值爆炸。

因此图a保留2023的Peng式百分比以便直观解释；跨事件图b—d统一使用 \(A-\hat A\) 的标准化残差。这里不是改变物理问题，而是避免零分母造成的统计伪信号。

## 当前汇报建议

主文仍保留此前的型态调整后结果，并把本轮结果放在稳健性或方法对照页：

> When the expected JJA atmospheric response is estimated using a Peng-style univariate Niño-3 regression, the cross-event relationship remains negative but weakens (r={primary.pearson_r:+.2f}) and is dominated by rainfall. Thus, meridional OHC spreading is consistent with reduced development-stage response efficiency, although the evidence is sensitive to how the atmospheric expectation is defined.

不要把本轮写成“复现了Peng原文结论”，应写成“Peng-style JJA adaptation”，因为时间窗、响应区域和资料并不完全相同。

## 输出文件

- 英文图：`{FIG_PNG}`
- 矢量图：`{FIG_PDF}`
- 13事件完整量：`{EVENT_CSV}`
- 统计检验：`{STATS_CSV}`
- 42年拟合系数：`{FITS_CSV}`
- 诊断信息：`{DIAGNOSTICS_JSON}`
- 计算代码：`{Path(__file__).resolve()}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    require_inputs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    jja, fits = build_jja_expected_response()
    event_table = build_event_table(jja)
    statistics = build_statistics(event_table)
    event_table.to_csv(EVENT_CSV, index=False)
    statistics.to_csv(STATS_CSV, index=False)
    fits.to_csv(FITS_CSV, index=False)

    current = event_table.loc[event_table["year"].eq(2023)].iloc[0]
    diagnostics = {
        "method_name": "Peng-style JJA adaptation",
        "climatology_years": list(CLIMATOLOGY_YEARS),
        "fit_years": list(FIT_YEARS),
        "months": list(JJA_MONTHS),
        "event_years": list(EVENTS),
        "n_fit_years": len(jja),
        "n_events": len(event_table),
        "primary_response_components": [
            item["prefix"] for item in RESPONSES if item["group"] == "primary"
        ],
        "ratio_warning": (
            "Observed/expected ratios are diagnostic only because the expected "
            "response approaches zero in weak-JJA-Nino3 events."
        ),
        "year_2023": {
            "nino3_jja_anom_c": float(current["nino3_jja_anom_c"]),
            "primary_composite_residual_z": float(
                current["primary_three_field_composite_residual_z"]
            ),
            "ncep_analog_composite_residual_z": float(
                current["ncep_peng_analog_composite_residual_z"]
            ),
        },
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    make_figure(event_table, statistics)
    write_report(event_table, statistics, fits)

    primary = statistics.loc[statistics["test_id"].eq("primary_composite_all")].iloc[0]
    print(f"Primary composite: r={primary.pearson_r:+.4f}, permutation p={primary.permutation_p:.4f}")
    print(f"2023 primary residual: {current.primary_three_field_composite_residual_z:+.4f} z")
    print(FIG_PNG)
    print(REPORT_MD)


if __name__ == "__main__":
    main()
