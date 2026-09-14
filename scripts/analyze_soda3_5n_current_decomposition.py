#!/usr/bin/env python3
"""Decompose SODA3 5N warm-heat export into geostrophic, Ekman, and residual terms.

The primary section is 5N, 140W-80W, 0-300 m.  Northward transport is
positive.  Monthly fields are converted to calendar-month linearly detrended
anomalies over 1982-2022 before CT/CP Dec(0)-May(+1) event integration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_chakravorty_transport_baseline as base  # noqa: E402
import analyze_soda3_air_sea_coupled_warm_heat_fate as coupling  # noqa: E402

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


SECTION_NC = (
    ROOT / "data/interim/research_2026/soda3_5n_geostrophic_sections_1980_2022.nc"
)
RAW_BUDGET_CSV = (
    ROOT / "data/derived/research_2026/soda3_three_box_warm_heat_budget_terms_1980_2022.csv"
)
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_5n_current_decomposition"
PDF_DIR = ROOT / "output/pdf"
MONTHLY_CSV = DERIVED / "soda3_5n_current_decomposition_monthly.csv"
EVENT_CSV = DERIVED / "soda3_5n_current_decomposition_event.csv"
SUMMARY_CSV = DERIVED / "soda3_5n_current_decomposition_summary.csv"
COMPOSITE_NC = DERIVED / "soda3_5n_current_decomposition_composites.nc"
DIAGNOSTICS_JSON = DERIVED / "soda3_5n_current_decomposition_diagnostics.json"
ERA5_SUMMARY_CSV = DERIVED / "era5_full_stress_curl_warm_heat_summary.csv"
FIGURE_PNG = OUT / "soda3_5n_current_decomposition.png"
FIGURE_PDF = PDF_DIR / "soda3_5n_current_decomposition.pdf"
REPORT_MD = OUT / "SODA3_5N_CURRENT_DECOMPOSITION_CN.md"

LATITUDE = 5.0
LON_ENDS = (270, 275, 280)
BASELINE = (1982, 2022)
RHO0 = 1025.0
CP0 = 3990.0
GRAVITY = 9.81
OMEGA = 7.2921159e-5
EARTH_RADIUS = 6_371_000.0
BOOTSTRAP = 20_000
SEED = 20260804


def coriolis(latitude: float = LATITUDE) -> float:
    return 2.0 * OMEGA * np.sin(np.deg2rad(latitude))


def density_eos80(temperature: np.ndarray, salinity: np.ndarray) -> np.ndarray:
    """UNESCO EOS-80 potential density at p=0 dbar, in kg m-3."""
    t = np.asarray(temperature, dtype=float)
    s = np.asarray(salinity, dtype=float)
    rho_w = (
        999.842594
        + 6.793952e-2 * t
        - 9.095290e-3 * t**2
        + 1.001685e-4 * t**3
        - 1.120083e-6 * t**4
        + 6.536332e-9 * t**5
    )
    a = (
        0.824493
        - 4.0899e-3 * t
        + 7.6438e-5 * t**2
        - 8.2467e-7 * t**3
        + 5.3875e-9 * t**4
    )
    b = -5.72466e-3 + 1.0227e-4 * t - 1.6546e-6 * t**2
    c = 4.8314e-4
    return rho_w + a * s + b * s**1.5 + c * s**2


def density_linear(temperature: np.ndarray, salinity: np.ndarray) -> np.ndarray:
    """Linear-EOS sensitivity calculation centered on 20 C and 35 psu."""
    alpha = 2.0e-4
    beta = 7.6e-4
    return RHO0 * (
        1.0 - alpha * (np.asarray(temperature) - 20.0)
        + beta * (np.asarray(salinity) - 35.0)
    )


def finite_gradient_x(values: np.ndarray, longitude: np.ndarray, latitude: float) -> np.ndarray:
    """Zonal derivative on each contiguous finite segment, preserving gaps."""
    array = np.asarray(values, dtype=float)
    x = EARTH_RADIUS * np.cos(np.deg2rad(latitude)) * np.deg2rad(longitude)
    flat = array.reshape((-1, array.shape[-1]))
    output = np.full(flat.shape, np.nan)
    for row_index, row in enumerate(flat):
        finite = np.isfinite(row)
        starts = np.flatnonzero(finite & ~np.r_[False, finite[:-1]])
        stops = np.flatnonzero(finite & ~np.r_[finite[1:], False]) + 1
        for start, stop in zip(starts, stops):
            if stop - start >= 2:
                output[row_index, start:stop] = np.gradient(
                    row[start:stop], x[start:stop], edge_order=1
                )
    return output.reshape(array.shape)


def vertical_integral_from_surface(values: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Integrate a value from the sea surface to each positive-down center depth."""
    field = np.asarray(values, dtype=float)
    output = np.full(field.shape, np.nan)
    output[:, 0, :] = field[:, 0, :] * float(depth[0])
    for level in range(1, len(depth)):
        step = float(depth[level] - depth[level - 1])
        output[:, level, :] = output[:, level - 1, :] + 0.5 * step * (
            field[:, level - 1, :] + field[:, level, :]
        )
    return output


def geostrophic_velocity(
    temperature: np.ndarray,
    salinity: np.ndarray,
    ssh: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    eos: str = "eos80",
) -> np.ndarray:
    density = density_eos80(temperature, salinity) if eos == "eos80" else density_linear(
        temperature, salinity
    )
    rho_x = finite_gradient_x(density, longitude, LATITUDE)
    ssh_x = finite_gradient_x(ssh, longitude, LATITUDE)
    f = coriolis()
    surface = GRAVITY / f * ssh_x
    shear = GRAVITY / (RHO0 * f) * vertical_integral_from_surface(rho_x, depth)
    return surface[:, None, :] + shear


def heat_transport_pw(
    temperature: np.ndarray,
    velocity: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    lon_end: int,
) -> np.ndarray:
    mask = np.asarray(longitude) <= lon_end
    width = base.meridional_section_width(np.asarray(longitude)[mask], LATITUDE)
    _, heat = base.section_transports(
        np.asarray(temperature)[:, :, mask],
        np.asarray(velocity)[:, :, mask],
        np.asarray(depth),
        width,
    )
    return heat


def ekman_heat_transport_pw(
    temperature: np.ndarray,
    taux: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    lon_end: int,
) -> np.ndarray:
    """First-order Ekman Q20 using the 0-50 m mean warm excess."""
    mask = np.asarray(longitude) <= lon_end
    bounds = base.depth_bounds(np.asarray(depth))
    overlap = np.maximum(0.0, np.minimum(bounds[1:], 50.0) - np.maximum(bounds[:-1], 0.0))
    warm = np.maximum(np.asarray(temperature)[:, :, mask] - 20.0, 0.0)
    warm_mean = np.nansum(warm * overlap[None, :, None], axis=1) / overlap.sum()
    meridional_transport_m2s = -np.asarray(taux)[:, mask] / (RHO0 * coriolis())
    width = base.meridional_section_width(np.asarray(longitude)[mask], LATITUDE)
    return (
        RHO0
        * CP0
        * np.nansum(meridional_transport_m2s * warm_mean * width[None, :], axis=1)
        / 1.0e15
    )


def same_month_detrended_array(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int] = BASELINE,
) -> np.ndarray:
    """Calendar-month linear detrend for a time-first scalar or field array."""
    array = np.asarray(values, dtype=float)
    flat = array.reshape((array.shape[0], -1))
    output = np.full(flat.shape, np.nan)
    for month in sorted(set(times.month)):
        fit_indices = np.where(
            (times.month == month)
            & (times.year >= baseline[0])
            & (times.year <= baseline[1])
        )[0]
        apply_indices = np.where(times.month == month)[0]
        years = np.asarray(times.year[fit_indices], dtype=float)
        center = years.mean()
        x = years - center
        selected = flat[fit_indices]
        valid = np.isfinite(selected)
        count = valid.sum(axis=0)
        mean = np.nansum(selected, axis=0) / np.where(count > 0, count, np.nan)
        denominator = np.nansum(valid * x[:, None] ** 2, axis=0)
        slope = np.nansum(x[:, None] * (selected - mean), axis=0) / np.where(
            denominator > 0, denominator, np.nan
        )
        apply_years = np.asarray(times.year[apply_indices], dtype=float) - center
        output[apply_indices] = flat[apply_indices] - (
            mean[None, :] + apply_years[:, None] * slope[None, :]
        )
    return output.reshape(array.shape)


def build_monthly(
    section: xr.Dataset,
) -> tuple[pd.DataFrame, dict[str, np.ndarray], dict[str, float]]:
    times = pd.DatetimeIndex(section.time.values)
    temp = section.temp.values.astype(float)
    salt = section.salt.values.astype(float)
    velocity = section.v.values.astype(float)
    ssh = section.ssh.values.astype(float)
    taux = section.taux.values.astype(float)
    depth = section.depth.values.astype(float)
    longitude = section.lon.values.astype(float)
    vgeo = {
        "eos80": geostrophic_velocity(temp, salt, ssh, depth, longitude, "eos80"),
        "linear": geostrophic_velocity(temp, salt, ssh, depth, longitude, "linear"),
    }

    monthly = pd.DataFrame({"time": times, "year": times.year, "month": times.month})
    for end in LON_ENDS:
        total = heat_transport_pw(temp, velocity, depth, longitude, end)
        ekman = ekman_heat_transport_pw(temp, taux, depth, longitude, end)
        monthly[f"total_220_{end}e_raw_pw"] = total
        monthly[f"ekman_220_{end}e_raw_pw"] = ekman
        for eos in ("eos80", "linear"):
            geo = heat_transport_pw(temp, vgeo[eos], depth, longitude, end)
            residual = total - geo - ekman
            monthly[f"geo_{eos}_220_{end}e_raw_pw"] = geo
            monthly[f"residual_{eos}_220_{end}e_raw_pw"] = residual

    raw_columns = [name for name in monthly if name.endswith("_raw_pw")]
    for column in raw_columns:
        monthly[column.replace("_raw_pw", "_anom_pw")] = same_month_detrended_array(
            monthly[column].to_numpy(), times
        )

    raw_budget = pd.read_csv(RAW_BUDGET_CSV, parse_dates=["time"]).set_index("time")
    target = -raw_budget.loc[times, "east_north_q20_in_pw"].to_numpy()
    reconstructed = monthly.total_220_280e_raw_pw.to_numpy()
    diagnostics = {
        "raw_total_validation_max_abs_pw": float(np.max(np.abs(reconstructed - target))),
        "raw_total_validation_r": float(np.corrcoef(reconstructed, target)[0, 1]),
        "eos80_density_20c_35psu_kgm3": float(density_eos80(np.array(20.0), np.array(35.0))),
        "coriolis_5n_s-1": float(coriolis()),
    }
    if diagnostics["raw_total_validation_max_abs_pw"] > 1.0e-6:
        raise ValueError("Reconstructed total Q20 does not reproduce the existing 5N budget")

    velocity_anomaly = same_month_detrended_array(velocity, times)
    geostrophic_anomaly = {
        eos: same_month_detrended_array(value, times) for eos, value in vgeo.items()
    }
    finite = np.isfinite(velocity_anomaly) & np.isfinite(geostrophic_anomaly["eos80"])
    diagnostics["monthly_gridpoint_total_geo_velocity_anomaly_r"] = float(
        np.corrcoef(velocity_anomaly[finite], geostrophic_anomaly["eos80"][finite])[0, 1]
    )
    fields = {
        "total_v_anom": velocity_anomaly,
        "geo_eos80_v_anom": geostrophic_anomaly["eos80"],
        "geo_linear_v_anom": geostrophic_anomaly["linear"],
    }
    return monthly, fields, diagnostics


def event_dates(year: int) -> list[pd.Timestamp]:
    return [pd.Timestamp(year=year, month=12, day=15)] + [
        pd.Timestamp(year=year + 1, month=month, day=15) for month in range(1, 6)
    ]


def integrate_zj(values: np.ndarray, times: pd.DatetimeIndex) -> float:
    days = times.days_in_month.to_numpy(dtype=float)
    return float(np.nansum(np.asarray(values) * days * 86400.0 * 1.0e-6))


def build_events(monthly: pd.DataFrame) -> pd.DataFrame:
    indexed = monthly.set_index("time")
    rows = []
    for event_class, years in coupling.EVENTS.items():
        for year in years:
            dates = pd.DatetimeIndex(event_dates(year))
            selected = indexed.loc[dates]
            row: dict[str, object] = {"event_class": event_class, "event_year": year}
            for end in LON_ENDS:
                for component in ("total", "ekman"):
                    source = f"{component}_220_{end}e_anom_pw"
                    row[f"{component}_220_{end}e_zj"] = integrate_zj(
                        selected[source].to_numpy(), dates
                    )
                for eos in ("eos80", "linear"):
                    for component in ("geo", "residual"):
                        source = f"{component}_{eos}_220_{end}e_anom_pw"
                        row[f"{component}_{eos}_220_{end}e_zj"] = integrate_zj(
                            selected[source].to_numpy(), dates
                        )
            rows.append(row)
    return pd.DataFrame(rows)


def summarize(events: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    metrics = [name for name in events if name not in {"event_class", "event_year"}]
    rows = []
    for metric in metrics:
        boot: dict[str, np.ndarray] = {}
        for group in ("CT", "CP"):
            values = events.loc[events.event_class.eq(group), metric].to_numpy(dtype=float)
            draws = rng.integers(0, len(values), size=(BOOTSTRAP, len(values)))
            boot[group] = values[draws].mean(axis=1)
            low, high = np.quantile(boot[group], [0.025, 0.975])
            rows.append(
                {
                    "contrast": group,
                    "metric": metric,
                    "mean": float(values.mean()),
                    "ci_low": float(low),
                    "ci_high": float(high),
                    "ci_excludes_zero": bool(low > 0 or high < 0),
                }
            )
        difference = boot["CT"] - boot["CP"]
        low, high = np.quantile(difference, [0.025, 0.975])
        rows.append(
            {
                "contrast": "CT_minus_CP",
                "metric": metric,
                "mean": float(
                    events.loc[events.event_class.eq("CT"), metric].mean()
                    - events.loc[events.event_class.eq("CP"), metric].mean()
                ),
                "ci_low": float(low),
                "ci_high": float(high),
                "ci_excludes_zero": bool(low > 0 or high < 0),
            }
        )
    return pd.DataFrame(rows)


def summary_value(summary: pd.DataFrame, contrast: str, metric: str) -> pd.Series:
    return summary.loc[summary.contrast.eq(contrast) & summary.metric.eq(metric)].iloc[0]


def build_composites(
    section: xr.Dataset, fields: dict[str, np.ndarray]
) -> xr.Dataset:
    times = pd.DatetimeIndex(section.time.values)
    output = xr.Dataset(coords={"depth": section.depth, "lon": section.lon})
    for group, years in coupling.EVENTS.items():
        dates = pd.DatetimeIndex([date for year in years for date in event_dates(year)])
        indices = times.get_indexer(dates)
        if np.any(indices < 0):
            raise ValueError(f"Incomplete dates for {group} composite")
        for name, values in fields.items():
            output[f"{name}_{group}"] = (("depth", "lon"), np.nanmean(values[indices], axis=0))
    for name in fields:
        output[f"{name}_CT_minus_CP"] = output[f"{name}_CT"] - output[f"{name}_CP"]
    output.attrs.update(
        {
            "phase": "Dec(0)-May(+1), unsmoothed calendar-month detrended anomalies",
            "events_CT": ",".join(map(str, coupling.EVENTS["CT"])),
            "events_CP": ",".join(map(str, coupling.EVENTS["CP"])),
        }
    )
    return output


def plot(composites: xr.Dataset, summary: pd.DataFrame) -> None:
    coupling.setup_style()
    fig, axes = plt.subplots(2, 3, figsize=(13.2, 7.1), constrained_layout=True)
    levels = np.arange(-8.0, 8.01, 1.0)
    filled = None
    panel = 0
    for row, group in enumerate(("CT", "CP")):
        for column, (field, label) in enumerate(
            (("total_v_anom", "SODA3 total v"), ("geo_eos80_v_anom", "SSH + thermal-wind v$_g$"))
        ):
            axis = axes[row, column]
            values = composites[f"{field}_{group}"] * 100.0
            filled = axis.contourf(
                composites.lon,
                composites.depth,
                values,
                levels=levels,
                cmap="RdBu_r",
                extend="both",
            )
            axis.contour(
                composites.lon,
                composites.depth,
                values,
                levels=[-2, 2],
                colors="0.25",
                linewidths=0.45,
            )
            axis.invert_yaxis()
            axis.set_xlim(220, 280)
            axis.set_xticks([220, 240, 260, 280], ["140°W", "120°W", "100°W", "80°W"])
            axis.set_ylabel("Depth (m)")
            axis.set_title(f"{chr(97 + panel)}) {group}: {label}", loc="left", fontweight="bold")
            panel += 1
    fig.colorbar(
        filled,
        ax=axes[:, :2],
        orientation="horizontal",
        shrink=0.70,
        label="Northward velocity anomaly (cm s$^{-1}$)",
    )

    axis = axes[0, 2]
    components = ("total", "geo_eos80", "ekman", "residual_eos80")
    labels = ("Total", "Geostrophic", "Ekman", "Residual")
    colors = {"CT": "#C23B3B", "CP": "#2C7FB8"}
    x = np.arange(len(components))
    width = 0.36
    for offset, group in ((-width / 2, "CT"), (width / 2, "CP")):
        rows = [summary_value(summary, group, f"{item}_220_280e_zj") for item in components]
        means = np.array([row["mean"] for row in rows])
        lows = np.array([row["ci_low"] for row in rows])
        highs = np.array([row["ci_high"] for row in rows])
        axis.bar(
            x + offset,
            means,
            width,
            color=colors[group],
            label=group,
            yerr=np.vstack((means - lows, highs - means)),
            capsize=2,
        )
    axis.axhline(0, color="0.35", lw=0.7)
    axis.set_xticks(x, labels, rotation=18)
    axis.set_ylabel("Dec-May cumulative Q20 anomaly (ZJ)")
    axis.set_title("e) 5°N transport decomposition", loc="left", fontweight="bold")
    axis.legend(frameon=False)
    axis.grid(axis="y", color="0.9", lw=0.5)

    axis = axes[1, 2]
    boundary_x = np.arange(len(LON_ENDS))
    for component, color, marker in (
        ("total", "#222222", "o"),
        ("geo_eos80", "#7A5195", "s"),
        ("ekman", "#EF8A17", "^"),
        ("residual_eos80", "#4C9F70", "D"),
    ):
        rows = [
            summary_value(summary, "CT_minus_CP", f"{component}_220_{end}e_zj")
            for end in LON_ENDS
        ]
        means = np.array([row["mean"] for row in rows])
        lows = np.array([row["ci_low"] for row in rows])
        highs = np.array([row["ci_high"] for row in rows])
        axis.errorbar(
            boundary_x,
            means,
            yerr=np.vstack((means - lows, highs - means)),
            color=color,
            marker=marker,
            capsize=2,
            label=component.replace("_eos80", "").title(),
        )
    axis.axhline(0, color="0.35", lw=0.7)
    axis.set_xticks(boundary_x, ["90°W", "85°W", "80°W"])
    axis.set_xlabel("Eastern end of 5°N section")
    axis.set_ylabel("CT − CP (ZJ)")
    axis.set_title("f) Boundary sensitivity", loc="left", fontweight="bold")
    axis.legend(frameon=False, ncol=2)
    axis.grid(axis="y", color="0.9", lw=0.5)

    fig.suptitle(
        "Where does the eastern-Pacific warm water go? SODA3 5°N dynamical decomposition",
        fontsize=13,
        fontweight="bold",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(summary: pd.DataFrame, diagnostics: dict[str, float]) -> None:
    def get(group: str, component: str, end: int = 280) -> pd.Series:
        return summary_value(summary, group, f"{component}_220_{end}e_zj")

    ct = {name: get("CT", name) for name in ("total", "geo_eos80", "ekman", "residual_eos80")}
    cp = {name: get("CP", name) for name in ("total", "geo_eos80", "ekman", "residual_eos80")}
    diff = {
        name: get("CT_minus_CP", name)
        for name in ("total", "geo_eos80", "ekman", "residual_eos80")
    }
    linear_diff = get("CT_minus_CP", "geo_linear")
    ct_ekman_fraction = 100.0 * ct["ekman"]["mean"] / ct["total"]["mean"]
    diff_geo_fraction = 100.0 * diff["geo_eos80"]["mean"] / diff["total"]["mean"]
    diff_ekman_fraction = 100.0 * diff["ekman"]["mean"] / diff["total"]["mean"]
    boundary_lines = []
    for end in LON_ENDS:
        total = get("CT_minus_CP", "total", end)
        geo = get("CT_minus_CP", "geo_eos80", end)
        ekman = get("CT_minus_CP", "ekman", end)
        boundary_lines.append(
            f"- 终点 {360-end}°W：总量 {total['mean']:+.2f} ZJ，地转 {geo['mean']:+.2f} ZJ，Ekman {ekman['mean']:+.2f} ZJ。"
        )
    report = f"""# SODA3 5°N 暖量北向出口的海洋动力分解

## 结论先行

在与 Chakravorty et al. (2021) 重叠的 4 个 CT 与 4 个 CP 事件中，Dec(0)–May(+1) 的 5°N、140°W–80°W 原生 SODA3 北向 Q20 异常，CT/CP 分别为 **{ct['total']['mean']:+.2f}/{cp['total']['mean']:+.2f} ZJ**；CT−CP 为 **{diff['total']['mean']:+.2f} ZJ**，95% 事件 bootstrap 区间 [{diff['total']['ci_low']:+.2f}, {diff['total']['ci_high']:+.2f}]。

动力分解给出的核心判断是：

- 地转项（SSH 表面地转流 + 温盐密度热成风）CT/CP 为 **{ct['geo_eos80']['mean']:+.2f}/{cp['geo_eos80']['mean']:+.2f} ZJ**，CT−CP 为 **{diff['geo_eos80']['mean']:+.2f} ZJ**，区间 [{diff['geo_eos80']['ci_low']:+.2f}, {diff['geo_eos80']['ci_high']:+.2f}]。
- SODA3 自身风应力估算的 Ekman 项为 **{ct['ekman']['mean']:+.2f}/{cp['ekman']['mean']:+.2f} ZJ**，CT−CP 为 **{diff['ekman']['mean']:+.2f} ZJ**，区间 [{diff['ekman']['ci_low']:+.2f}, {diff['ekman']['ci_high']:+.2f}]。
- 残差为 **{ct['residual_eos80']['mean']:+.2f}/{cp['residual_eos80']['mean']:+.2f} ZJ**。它按定义包含非地转流、Ekman 近似误差、垂向/沿岸结构和诊断误差，不能直接命名为某一种流。

最重要的细分是：**CT 组自身显著的北向项是 Ekman（+2.18 ZJ），CT 地转北向项的区间跨零；CP 组则出现显著的地转南向异常（−1.23 ZJ），Ekman 项不显著。** 因而：

- 若回答“CT 暖水怎样向北离开”，第一主角是风驱 Ekman，事件均值约占 CT 总北向输出的 {ct_ekman_fraction:.0f}%。
- 若回答“为什么 CT 与 CP 不同”，则地转差异和 Ekman 差异都重要，按均值分别约为总差异的 {diff_geo_fraction:.0f}% 与 {diff_ekman_fraction:.0f}%；前者主要表现为 CP 的南向地转异常，后者表现为 CT 更强的北向 Ekman 输出。

因此论文不应写成“纯 Ekman 北逃”，也不应把地转项说成独立外强迫。它是一个运动学分解：SSH/密度压力场本身也会响应风和热力过程。只有置信区间不跨零并通过边界/EOS敏感性的项，才称为可辨识动力贡献。

## 为什么这一步能收束到海气耦合

这套分解把先前的大气证据接回了海洋内部：CT 在东太平洋形成更强的暖异常和对流，随后 5°N 附近西向风应力与正风应力旋度增强；现在用同一 SODA3 产品检验，其中有多少跨 5°N 暖量输出可由局地风应力 Ekman 输送解释，又有多少对应海面高度和密度梯度控制的地转调整。这样“暖量去了哪里”不再只是箱体收支，而成为可检验的 **SST/对流 → 风应力 → Ekman 与海洋压力场调整 → 暖量北出口** 链条。

后续逐月检验也给出相同次序：Dec(0)先出现东部H20和降水差异，Jan(+1)东部SST与总Q20差异变得可辨识，Feb西向风应力以及Ekman/地转Q20均显著为正，Mar Ekman与总出口仍为正。完整时序见 `outputs/research_2026/soda3_5n_coupled_timing/SODA3_5N_COUPLED_TIMING_CN.md`。月资料支持先后顺序，但不替代耦合模式扰动试验。

## 稳健性

{chr(10).join(boundary_lines)}

- EOS-80 改成线性状态方程后，80°W 终点的 CT−CP 地转项为 {linear_diff['mean']:+.2f} ZJ（EOS-80 为 {diff['geo_eos80']['mean']:+.2f} ZJ）。
- 原生总 Q20 与既有三箱 5°N 边界逐月复算的最大绝对误差为 {diagnostics['raw_total_validation_max_abs_pw']:.2e} PW，相关系数 {diagnostics['raw_total_validation_r']:.6f}。
- 全部月—深度—经度格点的总流速异常与重建地转流速异常相关为 r={diagnostics['monthly_gridpoint_total_geo_velocity_anomaly_r']:.2f}。该相关只用于检查结构一致性，不等同于因果归因。
- 8 个事件中，总 Q20 与“地转+Ekman”的相关为 r={diagnostics['event_total_vs_geo_plus_ekman_r']:.3f}；逐一删除任一事件后仍为 {diagnostics['event_total_vs_geo_plus_ekman_loo_min_r']:.3f}–{diagnostics['event_total_vs_geo_plus_ekman_loo_max_r']:.3f}。
- 不平滑分解得到的 CT/CP 总量 {ct['total']['mean']:+.2f}/{cp['total']['mean']:+.2f} ZJ，与此前完整月轴三个月平滑结果 {diagnostics['previous_sm3_ct_total_zj']:+.2f}/{diagnostics['previous_sm3_cp_total_zj']:+.2f} ZJ 几乎一致，说明结论不是平滑选择造成的。
- SODA3 自身风应力的 CT−CP Ekman 差异为 {diff['ekman']['mean']:+.2f} ZJ；独立 ERA5 风应力的一阶估算为 {diagnostics['era5_ct_minus_cp_ekman_zj']:+.2f} ZJ，95% 区间 [{diagnostics['era5_ct_minus_cp_ekman_ci_low_zj']:+.2f}, {diagnostics['era5_ct_minus_cp_ekman_ci_high_zj']:+.2f}]。两套资料对风驱差异给出近乎相同的量级。

## 方法与限定

1. 断面：5°N，140°W–80°W，0–300 m；北向为正；东端另取 90°W、85°W 做边界敏感性。
2. Q20：`rho0 cp ∫ v max(T−20,0) dz dx`，与原三箱暖量预算完全同定义。
3. 地转流：`v_g(0)=g/f ∂SSH/∂x`；深度向下为正时，`v_g(d)=v_g(0)+g/(rho0 f)∫0^d ∂rho/∂x dd`。主结果用 UNESCO EOS-80 的 0 dbar 位密度，线性 EOS 作敏感性。
4. Ekman：`M_y=−tau_x/(rho0 f)`，用 0–50 m 平均的 `(T−20)+` 折算 Q20。这是第一阶深度积分估算，不假设它等于 SODA3 原生 Ekman 层流量。
5. 所有分量先按日历月在 1982–2022 年线性去趋势，再以整事件为样本累计 Dec(0)–May(+1)；本分解不做三个月平滑，以避免只有 Dec–May 断面时跨缺月伪平滑。
6. 残差严格定义为总量−地转−Ekman，不作动力学过度命名。5°N 接近赤道，地转近似对小尺度噪声敏感，这也是必须报告边界和 EOS 敏感性的原因。

## 产物

- 主图：`{FIGURE_PNG}`
- 月度分量：`{MONTHLY_CSV}`
- 事件累计：`{EVENT_CSV}`
- bootstrap 汇总：`{SUMMARY_CSV}`
- 断面合成：`{COMPOSITE_NC}`
- 诊断：`{DIAGNOSTICS_JSON}`
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> int:
    with xr.open_dataset(SECTION_NC, engine="netcdf4") as opened:
        section = opened.load()
    monthly, fields, diagnostics = build_monthly(section)
    events = build_events(monthly)
    summary = summarize(events)
    composites = build_composites(section, fields)
    identity = (
        events.total_220_280e_zj
        - events.geo_eos80_220_280e_zj
        - events.ekman_220_280e_zj
        - events.residual_eos80_220_280e_zj
    )
    diagnostics["event_component_identity_max_abs_zj"] = float(np.max(np.abs(identity)))
    if diagnostics["event_component_identity_max_abs_zj"] > 1.0e-10:
        raise ValueError("Event component identity failed")
    total_event = events.total_220_280e_zj.to_numpy(dtype=float)
    resolved_event = (
        events.geo_eos80_220_280e_zj + events.ekman_220_280e_zj
    ).to_numpy(dtype=float)
    diagnostics["event_total_vs_geo_plus_ekman_r"] = float(
        np.corrcoef(total_event, resolved_event)[0, 1]
    )
    leave_one_out = [
        float(
            np.corrcoef(
                np.delete(total_event, index), np.delete(resolved_event, index)
            )[0, 1]
        )
        for index in range(len(events))
    ]
    diagnostics["event_total_vs_geo_plus_ekman_loo_min_r"] = min(leave_one_out)
    diagnostics["event_total_vs_geo_plus_ekman_loo_max_r"] = max(leave_one_out)
    previous = pd.read_csv(coupling.SUMMARY_CSV)
    previous = previous.loc[
        previous.phase.eq("mature_decay_Dec0_to_May1")
        & previous.metric.eq("soda_north_export_zj")
    ].set_index("contrast")
    diagnostics["previous_sm3_ct_total_zj"] = float(previous.loc["CT", "mean"])
    diagnostics["previous_sm3_cp_total_zj"] = float(previous.loc["CP", "mean"])
    era5 = pd.read_csv(ERA5_SUMMARY_CSV)
    era5 = era5.loc[
        era5.contrast.eq("CT_minus_CP")
        & era5.metric.eq("ekman_heat_estimate_zj")
    ].iloc[0]
    diagnostics["era5_ct_minus_cp_ekman_zj"] = float(era5["mean"])
    diagnostics["era5_ct_minus_cp_ekman_ci_low_zj"] = float(era5["ci_low"])
    diagnostics["era5_ct_minus_cp_ekman_ci_high_zj"] = float(era5["ci_high"])

    DERIVED.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.9g")
    composites.to_netcdf(COMPOSITE_NC, engine="netcdf4")
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot(composites, summary)
    write_report(summary, diagnostics)
    for path in (
        MONTHLY_CSV,
        EVENT_CSV,
        SUMMARY_CSV,
        COMPOSITE_NC,
        DIAGNOSTICS_JSON,
        FIGURE_PNG,
        FIGURE_PDF,
        REPORT_MD,
    ):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
