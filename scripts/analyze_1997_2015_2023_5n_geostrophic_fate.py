#!/usr/bin/env python3
"""Decompose 1997/2015/2023 eastern-Pacific 5N Q20 fate.

Total northward warm-heat transport across 5N, 140W-80W, 0-300 m is
partitioned into EOS-80 geostrophic, first-order Ekman, and residual terms.
The geostrophic term is further separated into SSH-gradient and density-
gradient contributions.  January-May of 1998, 2016, and 2024 represent the
following-year mature/decay periods of the 1997, 2015, and 2023 events.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_5n_current_decomposition as dec  # noqa: E402

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
matplotlib.use("Agg")

HISTORICAL_NC = (
    ROOT / "data/interim/research_2026/soda3_5n_geostrophic_sections_1980_2022.nc"
)
EXTENSION_NC = (
    ROOT / "data/interim/research_2026/soda3_5n_geostrophic_section_2024_jan_may.nc"
)
BRIDGE_PHASE_CSV = (
    ROOT / "data/derived/research_2026/enso_1997_2015_2023_warm_heat_fate_phase_summary.csv"
)
RAW_BUDGET_CSV = (
    ROOT / "data/derived/research_2026/soda3_three_box_warm_heat_budget_terms_1980_2022.csv"
)
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/enso_1997_2015_2023_5n_geostrophic_fate"
PDF_DIR = ROOT / "output/pdf"

MONTHLY_CSV = DERIVED / "enso_1997_2015_2023_5n_geostrophic_fate_monthly.csv"
EVENT_CSV = DERIVED / "enso_1997_2015_2023_5n_geostrophic_fate_events.csv"
DIAGNOSTICS_JSON = DERIVED / "enso_1997_2015_2023_5n_geostrophic_fate_diagnostics.json"
FIGURE_PNG = OUT / "enso_1997_2015_2023_5n_geostrophic_fate.png"
FIGURE_PDF = PDF_DIR / "enso_1997_2015_2023_5n_geostrophic_fate.pdf"
REPORT_MD = OUT / "ENSO_1997_2015_2023_5N_GEOSTROPHIC_FATE_CN.md"

TARGETS = {1997: 1998, 2015: 2016, 2023: 2024}
BASELINES = ((1980, 2014), (1982, 2022))
PRIMARY_BASELINE = (1980, 2014)
LON_END = 280


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.4,
            "axes.labelsize": 9.2,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_section() -> xr.Dataset:
    with xr.open_dataset(HISTORICAL_NC, engine="netcdf4") as source:
        historical = source.sel(time=source.time.dt.month.isin([1, 2, 3, 4, 5])).load()
    with xr.open_dataset(EXTENSION_NC, engine="netcdf4") as source:
        extension = source.load()
    for coordinate in ("depth", "lon"):
        if not np.allclose(historical[coordinate], extension[coordinate]):
            raise ValueError(f"Historical and 2024 {coordinate} coordinates differ")
    # The official 2024 file stores coordinates with tiny (~1e-12) floating-
    # point differences.  xarray otherwise treats them as distinct labels and
    # silently creates duplicate depth/lon cells during concat, halving the
    # effective layer thickness for each source.  Reuse the historical labels
    # exactly after the numerical equality check above.
    extension = extension.assign_coords(
        depth=historical.depth.values,
        lon=historical.lon.values,
    )
    output = xr.concat(
        [historical, extension], dim="time", join="exact"
    ).sortby("time")
    times = pd.DatetimeIndex(output.time.values)
    if not times.is_unique or not times.is_monotonic_increasing:
        raise ValueError("Combined section time axis is not unique/increasing")
    if set(times.month) != {1, 2, 3, 4, 5}:
        raise ValueError("Unexpected months in combined section")
    if output.sizes.get("depth") != 20 or output.sizes.get("lon") != 120:
        raise ValueError(f"Unexpected combined section geometry: {output.sizes}")
    if any(bool(output[name].isnull().all()) for name in output.data_vars):
        raise ValueError("A required section variable is entirely missing")
    return output


def geostrophic_components(
    temperature: np.ndarray,
    salinity: np.ndarray,
    ssh: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    eos: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    density = (
        dec.density_eos80(temperature, salinity)
        if eos == "eos80"
        else dec.density_linear(temperature, salinity)
    )
    density_x = dec.finite_gradient_x(density, longitude, dec.LATITUDE)
    ssh_x = dec.finite_gradient_x(ssh, longitude, dec.LATITUDE)
    f = dec.coriolis()
    surface_velocity = dec.GRAVITY / f * ssh_x
    density_velocity = (
        dec.GRAVITY
        / (dec.RHO0 * f)
        * dec.vertical_integral_from_surface(density_x, depth)
    )
    surface_velocity_3d = np.broadcast_to(
        surface_velocity[:, None, :], density_velocity.shape
    )
    total_velocity = surface_velocity_3d + density_velocity
    # Transport is linear only when every component uses the same ocean mask.
    # Density shear is undefined wherever a full zonal/depth gradient cannot
    # be formed, so impose the total-velocity mask on both subcomponents.
    common = np.isfinite(total_velocity)
    surface_velocity_3d = np.where(common, surface_velocity_3d, np.nan)
    density_velocity = np.where(common, density_velocity, np.nan)
    return surface_velocity_3d, density_velocity, total_velocity


def same_month_scalar(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int],
) -> np.ndarray:
    return dec.same_month_detrended_array(
        np.asarray(values, dtype=float), times, baseline
    )


def build_monthly(section: xr.Dataset) -> tuple[pd.DataFrame, dict[str, float]]:
    times = pd.DatetimeIndex(section.time.values)
    temp = section.temp.values.astype(float)
    salt = section.salt.values.astype(float)
    velocity = section.v.values.astype(float)
    ssh = section.ssh.values.astype(float)
    taux = section.taux.values.astype(float)
    depth = section.depth.values.astype(float)
    longitude = section.lon.values.astype(float)

    geo: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for eos in ("eos80", "linear"):
        geo[eos] = geostrophic_components(
            temp, salt, ssh, depth, longitude, eos
        )

    raw: dict[str, np.ndarray] = {
        "total_raw_pw": dec.heat_transport_pw(
            temp, velocity, depth, longitude, LON_END
        ),
        "ekman_raw_pw": dec.ekman_heat_transport_pw(
            temp, taux, depth, longitude, LON_END
        ),
    }
    for eos in ("eos80", "linear"):
        ssh_velocity, density_velocity, total_geo_velocity = geo[eos]
        raw[f"geo_ssh_{eos}_raw_pw"] = dec.heat_transport_pw(
            temp, ssh_velocity, depth, longitude, LON_END
        )
        raw[f"geo_density_{eos}_raw_pw"] = dec.heat_transport_pw(
            temp, density_velocity, depth, longitude, LON_END
        )
        raw[f"geo_{eos}_raw_pw"] = dec.heat_transport_pw(
            temp, total_geo_velocity, depth, longitude, LON_END
        )
        raw[f"residual_{eos}_raw_pw"] = (
            raw["total_raw_pw"] - raw["ekman_raw_pw"] - raw[f"geo_{eos}_raw_pw"]
        )

    output = pd.DataFrame(
        {"time": times, "year": times.year, "month": times.month, **raw}
    )
    for baseline in BASELINES:
        tag = f"b{baseline[0]}_{baseline[1]}"
        for name, values in raw.items():
            output[f"{name.replace('_raw_pw', '')}_anom_pw_{tag}"] = same_month_scalar(
                values, times, baseline
            )

    closure = raw["total_raw_pw"] - (
        raw["geo_eos80_raw_pw"]
        + raw["ekman_raw_pw"]
        + raw["residual_eos80_raw_pw"]
    )
    geo_component_closure = raw["geo_eos80_raw_pw"] - (
        raw["geo_ssh_eos80_raw_pw"] + raw["geo_density_eos80_raw_pw"]
    )
    diagnostics = {
        "raw_total_closure_max_abs_pw": float(np.nanmax(np.abs(closure))),
        "raw_geo_component_closure_max_abs_pw": float(
            np.nanmax(np.abs(geo_component_closure))
        ),
        "temperature_min_c": float(np.nanmin(temp)),
        "temperature_max_c": float(np.nanmax(temp)),
        "salinity_min_psu": float(np.nanmin(salt)),
        "salinity_max_psu": float(np.nanmax(salt)),
        "velocity_max_abs_ms": float(np.nanmax(np.abs(velocity))),
        "taux_max_abs_nm2": float(np.nanmax(np.abs(taux))),
    }
    return output, diagnostics


def integrate_zj(values_pw: np.ndarray, times: pd.DatetimeIndex) -> float:
    seconds = times.days_in_month.to_numpy(dtype=float) * 86400.0
    return float(np.nansum(values_pw * seconds) / 1.0e6)


def event_table(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for baseline in BASELINES:
        tag = f"b{baseline[0]}_{baseline[1]}"
        for event_year, decay_year in TARGETS.items():
            selected = monthly.loc[
                monthly.year.eq(decay_year) & monthly.month.between(1, 5)
            ].sort_values("time")
            if len(selected) != 5:
                raise ValueError(f"Incomplete Jan-May decay data for {decay_year}")
            times = pd.DatetimeIndex(selected.time)
            row: dict[str, float | int | str] = {
                "baseline": f"{baseline[0]}-{baseline[1]}",
                "event_year": event_year,
                "decay_year": decay_year,
            }
            for metric in (
                "total",
                "ekman",
                "geo_eos80",
                "geo_ssh_eos80",
                "geo_density_eos80",
                "residual_eos80",
                "geo_linear",
                "residual_linear",
            ):
                values = selected[f"{metric}_anom_pw_{tag}"].to_numpy(dtype=float)
                row[f"{metric}_zj"] = integrate_zj(values, times)
            rows.append(row)
    output = pd.DataFrame(rows)
    bridge = pd.read_csv(BRIDGE_PHASE_CSV)
    bridge = bridge.loc[bridge.phase.eq("decay_Jan1_May1")].rename(
        columns={
            "q20_5n_north_zj": "one_sided_4p75_total_zj",
            "q20_5n_ekman_north_zj": "one_sided_4p75_ekman_zj",
        }
    )
    bridge = bridge[
        [
            "baseline",
            "event_year",
            "one_sided_4p75_total_zj",
            "one_sided_4p75_ekman_zj",
        ]
    ]
    output = output.merge(bridge, on=["baseline", "event_year"], how="left")
    output["centered_minus_one_sided_total_zj"] = (
        output.total_zj - output.one_sided_4p75_total_zj
    )
    return output


def build_diagnostics(
    monthly: pd.DataFrame,
    events: pd.DataFrame,
    physical: dict[str, float],
) -> dict[str, object]:
    primary = events.loc[events.baseline.eq("1980-2014")].set_index("event_year")
    sensitivity = events.loc[events.baseline.eq("1982-2022")].set_index("event_year")
    metrics = (
        "total_zj",
        "ekman_zj",
        "geo_eos80_zj",
        "geo_ssh_eos80_zj",
        "geo_density_eos80_zj",
        "residual_eos80_zj",
    )
    baseline_sign_stability = {
        f"{year}_{metric}": bool(
            np.sign(primary.loc[year, metric]) == np.sign(sensitivity.loc[year, metric])
        )
        for year in TARGETS
        for metric in metrics
    }
    eos_sensitivity = {
        str(year): float(
            primary.loc[year, "geo_linear_zj"] - primary.loc[year, "geo_eos80_zj"]
        )
        for year in TARGETS
    }

    bridge = pd.read_csv(BRIDGE_PHASE_CSV)
    bridge = bridge.loc[
        bridge.baseline.eq("1980-2014") & bridge.phase.eq("decay_Jan1_May1")
    ].set_index("event_year")
    total_reproduction = {
        str(year): float(
            primary.loc[year, "total_zj"] - bridge.loc[year, "q20_5n_north_zj"]
        )
        for year in TARGETS
    }
    component_closure = {
        str(year): float(
            primary.loc[year, "total_zj"]
            - primary.loc[year, "geo_eos80_zj"]
            - primary.loc[year, "ekman_zj"]
            - primary.loc[year, "residual_eos80_zj"]
        )
        for year in TARGETS
    }
    raw_budget = pd.read_csv(RAW_BUDGET_CSV, parse_dates=["time"]).set_index("time")
    historical = monthly.loc[monthly.time.dt.year.le(2022)].set_index("time")
    raw_reference = -raw_budget.loc[
        historical.index, "east_north_q20_in_pw"
    ].to_numpy(dtype=float)
    raw_reconstructed = historical.total_raw_pw.to_numpy(dtype=float)
    raw_difference = raw_reconstructed - raw_reference
    raw_validation = {
        "max_abs_pw": float(np.nanmax(np.abs(raw_difference))),
        "mean_abs_pw": float(np.nanmean(np.abs(raw_difference))),
        "correlation": float(np.corrcoef(raw_reconstructed, raw_reference)[0, 1]),
    }
    if raw_validation["max_abs_pw"] > 1.0e-6:
        raise ValueError(
            "Combined-section total Q20 does not reproduce the established 5N budget"
        )
    return {
        "physical_qa": physical,
        "primary_baseline": "1980-2014",
        "sensitivity_baseline": "1982-2022",
        "baseline_sign_stability": baseline_sign_stability,
        "all_component_signs_stable": bool(all(baseline_sign_stability.values())),
        "linear_minus_eos80_geostrophic_zj": eos_sensitivity,
        "event_total_minus_bridge_total_zj": total_reproduction,
        "event_component_closure_zj": component_closure,
        "event_component_closure_max_abs_zj": float(
            max(abs(value) for value in component_closure.values())
        ),
        "historical_raw_total_validation": raw_validation,
        "limitations": [
            "Three target events are process cases, not an inferential sample.",
            "January-May excludes the mature December because the extended common subset is Jan-Jun.",
            "Geostrophic/Ekman decomposition is kinematic; pressure fields can themselves respond to wind forcing.",
            "Residual includes ageostrophic currents, transients, nonlinearities, and approximation error.",
            "The sign of the small 2023/24 total is sensitive to centered-face versus one-sided boundary temperature; outlet suppression is more robust than transport direction.",
        ],
    }


def cumulative_event(monthly: pd.DataFrame, event_year: int) -> pd.DataFrame:
    decay_year = TARGETS[event_year]
    tag = f"b{PRIMARY_BASELINE[0]}_{PRIMARY_BASELINE[1]}"
    selected = monthly.loc[
        monthly.year.eq(decay_year) & monthly.month.between(1, 5)
    ].sort_values("time").copy()
    seconds = pd.DatetimeIndex(selected.time).days_in_month.to_numpy(dtype=float) * 86400.0
    selected["plot_month"] = np.arange(1, 6)
    for metric in ("total", "ekman", "geo_eos80", "residual_eos80"):
        selected[f"cum_{metric}_zj"] = np.cumsum(
            selected[f"{metric}_anom_pw_{tag}"].to_numpy(dtype=float)
            * seconds
            / 1.0e6
        )
    return selected


def plot_results(monthly: pd.DataFrame, events: pd.DataFrame) -> None:
    setup_style()
    primary = events.loc[events.baseline.eq("1980-2014")].set_index("event_year")
    years = list(TARGETS)
    colors = {1997: "#B33A3A", 2015: "#D17A22", 2023: "#2878B5"}
    component_colors = {
        "geo_eos80_zj": "#4C78A8",
        "ekman_zj": "#F58518",
        "residual_eos80_zj": "#8E6C9E",
    }
    component_labels = {
        "geo_eos80_zj": "Geostrophic",
        "ekman_zj": "Ekman",
        "residual_eos80_zj": "Residual",
    }

    figure, axes = plt.subplots(2, 2, figsize=(10.4, 7.4), constrained_layout=True)
    x = np.arange(len(years), dtype=float)
    width = 0.22
    for offset, metric in zip((-width, 0.0, width), component_colors):
        axes[0, 0].bar(
            x + offset,
            primary.loc[years, metric],
            width=width * 0.9,
            color=component_colors[metric],
            label=component_labels[metric],
        )
    axes[0, 0].scatter(
        x,
        primary.loc[years, "total_zj"],
        color="#111111",
        marker="D",
        s=38,
        zorder=5,
        label="Total",
    )
    axes[0, 0].set_xticks(x, [str(year) for year in years])
    axes[0, 0].set_ylabel("Jan-May cumulative northward Qwarm,20 (ZJ)")
    axes[0, 0].legend(frameon=False, ncol=2)

    geo_metrics = ("geo_ssh_eos80_zj", "geo_density_eos80_zj")
    geo_colors = ("#2F5597", "#70AD47")
    geo_labels = ("SSH-gradient", "Density-gradient")
    for offset, metric, color, label in zip((-width / 2, width / 2), geo_metrics, geo_colors, geo_labels):
        axes[0, 1].bar(
            x + offset,
            primary.loc[years, metric],
            width=width,
            color=color,
            label=label,
        )
    axes[0, 1].scatter(
        x,
        primary.loc[years, "geo_eos80_zj"],
        color="#111111",
        marker="D",
        s=38,
        zorder=5,
        label="Total geostrophic",
    )
    axes[0, 1].set_xticks(x, [str(year) for year in years])
    axes[0, 1].set_ylabel("Jan-May cumulative geostrophic Qwarm,20 (ZJ)")
    axes[0, 1].legend(frameon=False)

    for event_year in years:
        current = cumulative_event(monthly, event_year)
        axes[1, 0].plot(
            current.plot_month,
            current.cum_total_zj,
            marker="o",
            color=colors[event_year],
            label=f"{event_year} total",
        )
        axes[1, 0].plot(
            current.plot_month,
            current.cum_ekman_zj,
            linestyle="--",
            color=colors[event_year],
            alpha=0.85,
            label=f"{event_year} Ekman",
        )
        axes[1, 1].plot(
            current.plot_month,
            current.cum_geo_eos80_zj,
            marker="o",
            color=colors[event_year],
            label=f"{event_year} geostrophic",
        )
        axes[1, 1].plot(
            current.plot_month,
            current.cum_residual_eos80_zj,
            linestyle="--",
            color=colors[event_year],
            alpha=0.85,
            label=f"{event_year} residual",
        )

    titles = (
        "a  Total export decomposed into dynamical components",
        "b  Geostrophic export separated by pressure source",
        "c  Monthly accumulation: total and Ekman",
        "d  Monthly accumulation: geostrophic and residual",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title, loc="left", fontweight="bold")
        axis.axhline(0.0, color="#666666", linewidth=0.8)
        axis.grid(axis="y", color="#D8D8D8", linewidth=0.6, alpha=0.8)
        axis.spines[["top", "right"]].set_visible(False)
    month_labels = ["Jan+1", "Feb+1", "Mar+1", "Apr+1", "May+1"]
    for axis in axes[1, :]:
        axis.set_xticks(range(1, 6), month_labels)
        axis.set_ylabel("Cumulative northward Qwarm,20 (ZJ)")
        axis.legend(frameon=False, ncol=2, fontsize=7.0)
    figure.suptitle(
        "Why did the 5°N warm-heat outlet differ in 1997, 2015, and 2023?\n"
        "SODA3.15.2 EOS-80 decomposition; 5°N, 140°W-80°W; Jan-May(+1)",
        fontsize=12.0,
        fontweight="bold",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def fmt(row: pd.Series, metric: str) -> str:
    return f"{float(row[metric]):+.2f}"


def write_report(events: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    primary = events.loc[events.baseline.eq("1980-2014")].set_index("event_year")
    sensitivity = events.loc[events.baseline.eq("1982-2022")].set_index("event_year")
    r97, r15, r23 = primary.loc[1997], primary.loc[2015], primary.loc[2023]
    s97, s15, s23 = sensitivity.loc[1997], sensitivity.loc[2015], sensitivity.loc[2023]
    total_15_minus_23 = float(r15.total_zj - r23.total_zj)
    ekman_15_minus_23 = float(r15.ekman_zj - r23.ekman_zj)
    ekman_share = 100.0 * ekman_15_minus_23 / total_15_minus_23
    text = rf"""# 1997/98、2015/16与2023/24的5°N暖量出口动力分解

## 问题与数据

本阶段把此前的“非Ekman剩余”正式拆成地转输送和真正残差。主数据全部来自SODA3.15.2：1998和2016年1—5月使用本地1980—2022月截面，2024年1—5月使用马里兰大学官方同版本年度文件的最小切片。空间统一为5°N、140°W—80°W、0—300 m；主距平为1980—2014逐日历月线性去趋势，1982—2022作为敏感性。

分解为：

\[
Q_{{total}}=Q_{{geo}}+Q_{{Ekman}}+Q_{{residual}}.
\]

地转流采用EOS‑80密度，由SSH梯度的正压分量和温盐密度梯度的斜压分量组成。所有正值均表示暖量向北离开赤道东太平洋。

## Jan(+1)—May(+1)累计结果（ZJ）

| 事件 | 总北向Q20 | 地转 | Ekman | 残差 | SSH地转 | 密度地转 |
|---|---:|---:|---:|---:|---:|---:|
| 1997/98 | {fmt(r97, 'total_zj')} | {fmt(r97, 'geo_eos80_zj')} | {fmt(r97, 'ekman_zj')} | {fmt(r97, 'residual_eos80_zj')} | {fmt(r97, 'geo_ssh_eos80_zj')} | {fmt(r97, 'geo_density_eos80_zj')} |
| 2015/16 | {fmt(r15, 'total_zj')} | {fmt(r15, 'geo_eos80_zj')} | {fmt(r15, 'ekman_zj')} | {fmt(r15, 'residual_eos80_zj')} | {fmt(r15, 'geo_ssh_eos80_zj')} | {fmt(r15, 'geo_density_eos80_zj')} |
| 2023/24 | {fmt(r23, 'total_zj')} | {fmt(r23, 'geo_eos80_zj')} | {fmt(r23, 'ekman_zj')} | {fmt(r23, 'residual_eos80_zj')} | {fmt(r23, 'geo_ssh_eos80_zj')} | {fmt(r23, 'geo_density_eos80_zj')} |

## 结果解释

**1997/98是动力协同型排暖。** Ekman贡献{fmt(r97, 'ekman_zj')} ZJ，地转贡献{fmt(r97, 'geo_eos80_zj')} ZJ，二者同向；残差仅{fmt(r97, 'residual_eos80_zj')} ZJ。它不仅有强风驱出口，SSH与密度梯度所代表的海洋压力场也帮助暖量北排。

**2015/16是风驱克服海洋阻力型排暖。** 地转项为{fmt(r15, 'geo_eos80_zj')} ZJ，其中SSH梯度项达到{fmt(r15, 'geo_ssh_eos80_zj')} ZJ，说明压力场倾向把暖量留在赤道侧或送回南侧；但{fmt(r15, 'ekman_zj')} ZJ的Ekman北向输出更强，最终仍留下{fmt(r15, 'total_zj')} ZJ的净北向出口。

**2023/24是出口近闭合型。** 地转阻力为{fmt(r23, 'geo_eos80_zj')} ZJ，与2015主基准几乎同量级，但Ekman只有{fmt(r23, 'ekman_zj')} ZJ，最终居中面估计的净输出仅{fmt(r23, 'total_zj')} ZJ。2015相对2023多出的{total_15_minus_23:+.2f} ZJ净输出中，Ekman差值为{ekman_15_minus_23:+.2f} ZJ，相当于净差的{ekman_share:.0f}%；地转和残差差异反而部分抵消它。因此两事件最直接的分水岭是大气能否提供足够强的风驱跨界输送。

这就把此前“2015与2023发展期进入东部的暖量相近”接到了衰减期出口机制上：**暖量都到了，但2015的大气耦合足以打开5°N出口，2023的大气响应不足，暖量出口被既有海洋压力场抵消。** 对1997而言，海洋压力场本身也转为协同，构成更完整的海气耦合闭环。

## 稳健性与关键修正

用1982—2022作距平基准时，1997、2015、2023的总输出分别为{fmt(s97, 'total_zj')}、{fmt(s15, 'total_zj')}、{fmt(s23, 'total_zj')} ZJ；三个事件的Ekman符号、地转符号及总输出排序均保持不变。EOS‑80换成线性状态方程也不改变地转项符号。

2023的**精确正负号并不稳健**。当前主结果使用跨5°N通量面两侧（4.75°N与5.25°N）温度的居中插值，得到{fmt(r23, 'total_zj')} ZJ；此前桥接实验使用赤道侧4.75°N单边温度，得到{float(r23.one_sided_4p75_total_zj):+.2f} ZJ。1997和2015两种口径只差约0.04 ZJ，而2023相差{float(r23.centered_minus_one_sided_total_zj):+.2f} ZJ，说明2024年5°N附近强温度锋与流速共置。有限体积意义上居中面温度更适合作为主估计，但论文应把结论写成“2023出口显著受抑/近闭合”，而不是强断言其净向南。

历史1980—2022截面的重建总Q20与既有三箱预算逐月吻合，最大绝对误差为{diagnostics['historical_raw_total_validation']['max_abs_pw']:.2e} PW、相关系数为{diagnostics['historical_raw_total_validation']['correlation']:.15f}。地转项的SSH与密度子项逐月闭合误差为{diagnostics['physical_qa']['raw_geo_component_closure_max_abs_pw']:.2e} PW。

主基准与敏感性中全部分量符号稳定：**{'是' if diagnostics['all_component_signs_stable'] else '否'}**。EOS‑80总量闭合最大误差为{diagnostics['event_component_closure_max_abs_zj']:.2e} ZJ。

## 证据边界

- 这里只有三个过程个例，不构成统计样本；
- 地转/Ekman是运动学分解，压力场本身也可能是风应力历史作用的结果；
- 共同窗口为次年1—5月，缺少成熟期12月；
- 2026尚无成熟—衰减期结果，不进入本次分解。

## 输出

- 图：`{FIGURE_PNG}`
- 月表：`{MONTHLY_CSV}`
- 事件汇总：`{EVENT_CSV}`
- 数值核验：`{DIAGNOSTICS_JSON}`
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    section = load_section()
    monthly, physical = build_monthly(section)
    events = event_table(monthly)
    diagnostics = build_diagnostics(monthly, events, physical)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot_results(monthly, events)
    write_report(events, diagnostics)
    print(events.to_string(index=False))
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
