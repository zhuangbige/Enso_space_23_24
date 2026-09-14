#!/usr/bin/env python3
"""Diagnose the two-stage atmospheric path from Jiang NE winds to 5N H20 export.

The analysis deliberately separates:

1. the MJJ development gate: Jiang-box (3--7N, 180E--130W) 925-hPa
   northeasterly residual and the equatorial central-Pacific surface westerly;
2. the following Jan--May discharge gate: local 5N westward stress and the
   Ekman/geostrophic/residual components of northward Q20.

The equatorial Hovmoller panels use calendar-month detrended ERA5 u10
anomalies in physical units.  The event-level central-Pacific u10 index is
additionally residualized month by month against year, Nino-3.4 SST and the
east-minus-central SST pattern, so the scatter tests the wind response beyond
event amplitude and SST pattern.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_maryland_jiang_two_stage_mpl")
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


ERA5_WIND = ROOT / "data/raw/era5/era5_monthly_10m_wind_pmm_1deg_1982_2025.nc"
COUPLING = ROOT / "data/derived/research_2026/enso_full_year_coupling_monthly_1982_2024.csv"
BASE_EVENTS = ROOT / "data/derived/research_2026/jiang_ne_wind_h20_exit_event_table.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/jiang_two_stage_coupling_path"
EVENT_TABLE = DERIVED / "jiang_two_stage_coupling_event_table.csv"
RELATIONSHIPS = DERIVED / "jiang_two_stage_coupling_relationships.csv"
HOV_TABLE = DERIVED / "jiang_two_stage_equatorial_u10_hovmoller.csv"
DIAGNOSTICS = DERIVED / "jiang_two_stage_coupling_diagnostics.json"
HOV_PNG = OUT / "jiang_two_stage_equatorial_u10_evolution.png"
HOV_PDF = OUT / "jiang_two_stage_equatorial_u10_evolution.pdf"
CHAIN_PNG = OUT / "jiang_two_stage_coupling_to_h20_export.png"
CHAIN_PDF = OUT / "jiang_two_stage_coupling_to_h20_export.pdf"
REPORT = OUT / "JIANG_TWO_STAGE_COUPLING_PATH_CN.md"

EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHT_YEARS = (1997, 2015, 2023)
COLORS = {1997: "#202020", 2015: "#2878b5", 2023: "#df5b3f"}
RANDOM_SEED = 20260808
N_PERMUTATIONS = 50_000
N_BOOTSTRAP = 20_000


def style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.2,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 8.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def normalize(dataset: xr.Dataset) -> xr.Dataset:
    rename = {
        old: new
        for old, new in (("valid_time", "time"), ("latitude", "lat"), ("longitude", "lon"))
        if old in dataset.coords
    }
    output = dataset.rename(rename)
    return output.assign_coords(lon=output.lon % 360.0).sortby(["lat", "lon"])


def detrend_same_month(values: np.ndarray, times: pd.DatetimeIndex) -> np.ndarray:
    """Calendar-month anomaly with a linear trend removed at every grid point."""
    array = np.asarray(values, dtype=float)
    output = np.full_like(array, np.nan, dtype=float)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    for month in range(1, 13):
        index = np.where(months == month)[0]
        current = array[index]
        anomaly = current - np.nanmean(current, axis=0, keepdims=True)
        x = years[index] - np.mean(years[index])
        denominator = float(np.sum(x**2))
        slope = np.nansum(x.reshape((-1,) + (1,) * (array.ndim - 1)) * anomaly, axis=0) / denominator
        output[index] = anomaly - x.reshape((-1,) + (1,) * (array.ndim - 1)) * slope
    return output


def load_equatorial_u10() -> tuple[xr.DataArray, pd.DataFrame]:
    """Return detrended equatorial u10 anomaly and the central-Pacific index."""
    with xr.open_dataset(ERA5_WIND) as raw:
        dataset = normalize(raw).sel(time=slice("1982-01-01", "2024-12-31"))
        field = dataset.u10.sel(lat=slice(-5.0, 5.0), lon=slice(130.0, 280.0))
        weights = np.cos(np.deg2rad(field.lat))
        zonal = field.weighted(weights).mean("lat", skipna=True).load()
        central = field.sel(lon=slice(160.0, 220.0)).weighted(weights).mean(("lat", "lon"), skipna=True).load()

    times = pd.DatetimeIndex(zonal.time.values)
    zonal_anomaly = detrend_same_month(zonal.values, times)
    hov = xr.DataArray(
        zonal_anomaly,
        dims=("time", "lon"),
        coords={"time": zonal.time, "lon": zonal.lon},
        name="equatorial_u10_anom_ms",
        attrs={
            "units": "m s-1",
            "definition": "5S-5N latitude-weighted mean; 1982-2024 calendar-month anomaly and linear detrend",
        },
    )

    central_frame = pd.DataFrame(
        {
            "year": times.year,
            "month": times.month,
            "u10_central_raw_ms": central.values.astype(float),
        }
    )
    central_frame["u10_central_anom_ms"] = detrend_same_month(
        central_frame.u10_central_raw_ms.to_numpy(), times
    )
    coupling = pd.read_csv(
        COUPLING,
        usecols=["year", "month", "nino34_raw_c", "sst_type_raw_c"],
    )
    central_frame = central_frame.merge(coupling, on=["year", "month"], validate="one_to_one")
    central_frame["u10_central_residual_ms"] = np.nan
    for month, group in central_frame.groupby("month"):
        design = np.column_stack(
            [
                np.ones(len(group)),
                group.year.to_numpy(dtype=float) - 2003.0,
                group.nino34_raw_c.to_numpy(dtype=float),
                group.sst_type_raw_c.to_numpy(dtype=float),
            ]
        )
        values = group.u10_central_anom_ms.to_numpy(dtype=float)
        coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
        central_frame.loc[group.index, "u10_central_residual_ms"] = values - design @ coefficients
    return hov, central_frame


def build_hov_table(hov: xr.DataArray) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for year in HIGHLIGHT_YEARS:
        times = pd.date_range(f"{year}-06-01", f"{year + 1}-05-01", freq="MS")
        selected = hov.sel(time=times)
        frame = selected.to_dataframe().reset_index()
        lookup = {time: index for index, time in enumerate(times)}
        frame["event_year"] = year
        frame["relative_month"] = [lookup[pd.Timestamp(value)] for value in frame.time]
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def build_event_table(central: pd.DataFrame) -> pd.DataFrame:
    events = pd.read_csv(BASE_EVENTS)
    seasonal = (
        central.loc[central.month.isin([5, 6, 7])]
        .groupby("year", as_index=False)
        .agg(
            u10_central_mjj_anom_ms=("u10_central_anom_ms", "mean"),
            u10_central_mjj_residual_ms=("u10_central_residual_ms", "mean"),
        )
    )
    output = events.merge(seasonal, on="year", validate="one_to_one")
    output = output.loc[output.year.isin(EVENT_YEARS)].sort_values("year").reset_index(drop=True)
    if len(output) != len(EVENT_YEARS):
        raise ValueError("Incomplete 13-event table")
    return output


def permutation_p(x: np.ndarray, y: np.ndarray, seed: int) -> float:
    observed = abs(float(np.corrcoef(x, y)[0, 1]))
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(N_PERMUTATIONS):
        count += abs(float(np.corrcoef(x, rng.permutation(y))[0, 1])) >= observed
    return float((count + 1) / (N_PERMUTATIONS + 1))


def bootstrap_ci(x: np.ndarray, y: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = np.full(N_BOOTSTRAP, np.nan)
    for index in range(N_BOOTSTRAP):
        selected = rng.integers(0, len(x), len(x))
        if np.std(x[selected]) > 0 and np.std(y[selected]) > 0:
            samples[index] = np.corrcoef(x[selected], y[selected])[0, 1]
    return tuple(float(value) for value in np.nanpercentile(samples, [2.5, 97.5]))


def bh_fdr(p_values: np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.minimum(adjusted, 1.0)
    return output


def relationships(events: pd.DataFrame) -> pd.DataFrame:
    tests = [
        ("ne_to_u10", "MJJ NE925 -> MJJ central-Pacific u10", "ne925_mjj_ms", "u10_central_mjj_residual_ms"),
        ("stress_to_u10", "MJJ Jiang-box westward stress -> central-Pacific u10", "westward_taux_jiang_mjj_nm2", "u10_central_mjj_residual_ms"),
        ("u10_to_decay_stress", "MJJ central-Pacific u10 -> following local 5N westward stress", "u10_central_mjj_residual_ms", "westward_taux_decay_all_nm2"),
        ("u10_to_ekman", "MJJ central-Pacific u10 -> following 5N Ekman Q20", "u10_central_mjj_residual_ms", "q5n_ekman_jan_may1_zj"),
        ("u10_to_geo", "MJJ central-Pacific u10 -> following 5N geostrophic Q20", "u10_central_mjj_residual_ms", "q5n_geo_eos80_jan_may1_zj"),
        ("u10_to_total", "MJJ central-Pacific u10 -> following total 5N Q20", "u10_central_mjj_residual_ms", "q5n_total_jan_may1_zj"),
        ("decay_stress_to_ekman", "Following local 5N westward stress -> Ekman Q20", "westward_taux_decay_all_nm2", "q5n_ekman_jan_may1_zj"),
        ("geo_to_total", "Following geostrophic Q20 -> total 5N Q20", "q5n_geo_eos80_jan_may1_zj", "q5n_total_jan_may1_zj"),
    ]
    rows = []
    for index, (test_id, label, x_name, y_name) in enumerate(tests):
        x = events[x_name].to_numpy(dtype=float)
        y = events[y_name].to_numpy(dtype=float)
        pearson = stats.pearsonr(x, y)
        spearman = stats.spearmanr(x, y)
        low, high = bootstrap_ci(x, y, RANDOM_SEED + index)
        loeo = []
        for held in range(len(x)):
            keep = np.arange(len(x)) != held
            loeo.append(float(np.corrcoef(x[keep], y[keep])[0, 1]))
        rows.append(
            {
                "test_id": test_id,
                "label": label,
                "x": x_name,
                "y": y_name,
                "n_events": len(x),
                "pearson_r": float(pearson.statistic),
                "parametric_p": float(pearson.pvalue),
                "permutation_p": permutation_p(x, y, RANDOM_SEED + index),
                "bootstrap_ci_low": low,
                "bootstrap_ci_high": high,
                "spearman_r": float(spearman.statistic),
                "loeo_r_min": float(np.min(loeo)),
                "loeo_r_max": float(np.max(loeo)),
            }
        )
    output = pd.DataFrame(rows)
    output["bh_fdr_q"] = bh_fdr(output.permutation_p.to_numpy(dtype=float))
    return output


def longitude_label(value: float) -> str:
    if np.isclose(value, 180.0):
        return "180°"
    if value < 180.0:
        return f"{int(value)}°E"
    return f"{int(360 - value)}°W"


def plot_hovmoller(hov_frame: pd.DataFrame, events: pd.DataFrame) -> None:
    style()
    figure, axes = plt.subplots(1, 3, figsize=(12.4, 5.7), sharex=True, sharey=True)
    levels = np.linspace(-4.0, 4.0, 17)
    norm = TwoSlopeNorm(vmin=-4.0, vcenter=0.0, vmax=4.0)
    month_labels = ["Jun(0)", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan(+1)", "Feb", "Mar", "Apr", "May"]
    image = None
    for axis, year in zip(axes, HIGHLIGHT_YEARS, strict=True):
        current = hov_frame.loc[hov_frame.event_year.eq(year)]
        pivot = current.pivot(index="relative_month", columns="lon", values="equatorial_u10_anom_ms")
        image = axis.contourf(pivot.columns, pivot.index, pivot.values, levels=levels, cmap="RdBu_r", norm=norm, extend="both")
        axis.contour(pivot.columns, pivot.index, pivot.values, levels=[-2, 0, 2], colors=["#3d6da8", "#555555", "#a43a35"], linewidths=[0.6, 0.8, 0.6])
        axis.axvline(180.0, color="#555555", linewidth=0.8, linestyle=":")
        axis.axvline(220.0, color="#555555", linewidth=0.8, linestyle=":")
        axis.axvline(250.0, color="#555555", linewidth=0.8, linestyle=":")
        axis.axhline(1.5, color="#222222", linewidth=0.9, linestyle="--")
        axis.axhline(6.5, color="#222222", linewidth=0.9, linestyle="--")
        row = events.loc[events.year.eq(year)].iloc[0]
        axis.set_title(
            f"{year}/{str(year + 1)[-2:]}\nNE925={row.ne925_mjj_ms:+.2f} m s$^{{-1}}$; Q$_{{total}}$={row.q5n_total_jan_may1_zj:+.2f} ZJ",
            fontweight="bold",
        )
        axis.set_ylim(11, 0)
        axis.set_yticks(range(12), month_labels)
        axis.set_xticks([130, 160, 180, 220, 250, 280], [longitude_label(x) for x in [130, 160, 180, 220, 250, 280]], rotation=25)
        axis.grid(False)
    axes[0].set_ylabel("Month relative to development year")
    figure.suptitle("Equatorial surface-wind evolution links the Jiang development gate to later discharge", y=0.985, fontweight="bold", fontsize=12.0)
    figure.supxlabel("Longitude", y=0.155)
    figure.subplots_adjust(left=0.07, right=0.99, top=0.84, bottom=0.25, wspace=0.08)
    color_axis = figure.add_axes([0.18, 0.065, 0.64, 0.045])
    cbar = figure.colorbar(image, cax=color_axis, orientation="horizontal")
    cbar.set_label("ERA5 equatorial u10 anomaly (m s$^{-1}$; red = westerly)")
    OUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(HOV_PNG, bbox_inches="tight")
    figure.savefig(HOV_PDF, bbox_inches="tight")
    plt.close(figure)


def scatter(
    axis: plt.Axes,
    events: pd.DataFrame,
    stats_row: pd.Series,
    xlabel: str,
    ylabel: str,
    title: str,
    stats_location: tuple[float, float] = (0.03, 0.96),
) -> None:
    x = events[stats_row.x].to_numpy(dtype=float)
    y = events[stats_row.y].to_numpy(dtype=float)
    axis.scatter(x, y, s=34, color="#b8b8b8", edgecolor="white", linewidth=0.5, zorder=2)
    coefficients = np.polyfit(x, y, 1)
    xx = np.linspace(np.min(x), np.max(x), 100)
    axis.plot(xx, np.polyval(coefficients, xx), color="#222222", linewidth=1.3, zorder=1)
    for year in HIGHLIGHT_YEARS:
        row = events.loc[events.year.eq(year)].iloc[0]
        axis.scatter(row[stats_row.x], row[stats_row.y], s=58, color=COLORS[year], edgecolor="white", linewidth=0.7, zorder=3)
        axis.annotate(str(year), (row[stats_row.x], row[stats_row.y]), xytext=(5, 4), textcoords="offset points", color=COLORS[year], fontweight="bold", fontsize=8.0)
    axis.set_title(title, loc="left", fontweight="bold", fontsize=9.6)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.text(
        stats_location[0],
        stats_location[1],
        f"r={stats_row.pearson_r:+.2f}, permutation p={stats_row.permutation_p:.3f}\n95% bootstrap [{stats_row.bootstrap_ci_low:+.2f}, {stats_row.bootstrap_ci_high:+.2f}]",
        transform=axis.transAxes,
        va="top",
        fontsize=8.0,
    )
    axis.axhline(0, color="#777777", linewidth=0.7)
    axis.axvline(0, color="#777777", linewidth=0.7)


def plot_chain(events: pd.DataFrame, relation: pd.DataFrame) -> None:
    style()
    lookup = relation.set_index("test_id")
    figure, axes = plt.subplots(2, 2, figsize=(11.0, 8.1))
    scatter(
        axes[0, 0], events, lookup.loc["ne_to_u10"],
        "MJJ Jiang-box NE925 residual (m s$^{-1}$)",
        "MJJ central-Pacific u10 residual (m s$^{-1}$)",
        "a  Jiang northeasterlies suppress\nthe development-stage westerly",
        stats_location=(0.03, 0.47),
    )
    scatter(
        axes[0, 1], events, lookup.loc["u10_to_ekman"],
        "MJJ central-Pacific u10 residual (m s$^{-1}$)",
        "Following Jan–May 5°N Ekman Q20 (ZJ)",
        "b  The coupled westerly projects\nonto the later Ekman branch",
    )
    scatter(
        axes[1, 0], events, lookup.loc["u10_to_total"],
        "MJJ central-Pacific u10 residual (m s$^{-1}$)",
        "Following Jan–May total 5°N Q20 (ZJ)",
        "c  The total outlet is not determined\nby wind coupling alone",
    )

    axis = axes[1, 1]
    selected = events.set_index("year").loc[list(HIGHLIGHT_YEARS)]
    x = np.arange(len(HIGHLIGHT_YEARS))
    width = 0.23
    components = [
        ("q5n_ekman_jan_may1_zj", "Ekman", "#d95f4c"),
        ("q5n_geo_eos80_jan_may1_zj", "Geostrophic", "#3b78b8"),
        ("q5n_residual_eos80_jan_may1_zj", "Residual", "#7c7c7c"),
    ]
    for offset, (column, label, color) in enumerate(components):
        axis.bar(x + (offset - 1) * width, selected[column], width=width, color=color, label=label)
    axis.scatter(x, selected.q5n_total_jan_may1_zj, s=68, marker="D", color="#111111", label="Total", zorder=4)
    axis.axhline(0, color="#555555", linewidth=0.8)
    axis.set_xticks(x, [str(year) for year in HIGHLIGHT_YEARS])
    axis.set_ylabel("Following Jan–May 5°N Q20 (ZJ)")
    axis.set_title("d  Net export is the sum of atmospheric and oceanic gates", loc="left", fontweight="bold")
    axis.legend(frameon=False, ncol=2, loc="upper right")
    axis.text(
        0.03,
        0.96,
        f"u10 → geostrophic: r={lookup.loc['u10_to_geo'].pearson_r:+.2f}\n"
        f"geostrophic → total: r={lookup.loc['geo_to_total'].pearson_r:+.2f}",
        transform=axis.transAxes,
        va="top",
        fontsize=8.0,
    )
    figure.suptitle("Two-stage coupling path: development suppression, then 5°N warm-heat discharge", fontweight="bold", fontsize=12.2, y=0.995)
    figure.tight_layout(rect=(0, 0, 1, 0.97), h_pad=2.2, w_pad=1.8)
    OUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(CHAIN_PNG, bbox_inches="tight")
    figure.savefig(CHAIN_PDF, bbox_inches="tight")
    plt.close(figure)


def multiple_regression(events: pd.DataFrame) -> dict[str, float]:
    y = events.q5n_total_jan_may1_zj.to_numpy(dtype=float)
    y_standard = (y - np.mean(y)) / np.std(y, ddof=1)
    predictors = events[["u10_central_mjj_residual_ms", "q5n_geo_eos80_jan_may1_zj"]].to_numpy(dtype=float)
    predictors = (predictors - np.mean(predictors, axis=0)) / np.std(predictors, axis=0, ddof=1)
    design = np.column_stack([np.ones(len(events)), predictors])
    coefficients = np.linalg.lstsq(design, y_standard, rcond=None)[0]
    fitted = design @ coefficients
    r_squared = 1.0 - np.sum((y_standard - fitted) ** 2) / np.sum((y_standard - np.mean(y_standard)) ** 2)
    loeo_predictions = np.full(len(events), np.nan)
    for held in range(len(events)):
        train = np.arange(len(events)) != held
        beta = np.linalg.lstsq(design[train], y_standard[train], rcond=None)[0]
        loeo_predictions[held] = design[held] @ beta
    loeo_r = float(np.corrcoef(loeo_predictions, y_standard)[0, 1])
    return {
        "standardized_beta_u10": float(coefficients[1]),
        "standardized_beta_geostrophic": float(coefficients[2]),
        "in_sample_r_squared": float(r_squared),
        "loeo_prediction_r": loeo_r,
    }


def write_report(events: pd.DataFrame, relation: pd.DataFrame, regression: dict[str, float]) -> None:
    lookup = relation.set_index("test_id")
    lines = [
        "# Jiang东北风—海气耦合—5°N H20出口：逐月衔接结果",
        "",
        "## 核心结论",
        "",
        "Jiang型东北风与5°N暖量出口之间不是同一股风从发展期持续到衰减期，而是两个阶段的风门。MJJ东北风首先压低中太平洋赤道西风，使海气正反馈较难接通；已经形成的中太平洋西风随后投影到次年局地5°N向西应力和Ekman暖量输出。总出口仍需与地转压力项相加，因此海气耦合只直接约束Ekman支路，不单独决定净出口。",
        "",
        "## 13事件定量证据",
        "",
        f"- NE925与中太平洋u10残差：r={lookup.loc['ne_to_u10'].pearson_r:+.2f}，置换p={lookup.loc['ne_to_u10'].permutation_p:.3f}。",
        f"- Jiang区向西海面应力与中太平洋u10残差：r={lookup.loc['stress_to_u10'].pearson_r:+.2f}，置换p={lookup.loc['stress_to_u10'].permutation_p:.3f}。",
        f"- 中太平洋u10残差与次年局地5°N向西应力：r={lookup.loc['u10_to_decay_stress'].pearson_r:+.2f}，置换p={lookup.loc['u10_to_decay_stress'].permutation_p:.3f}。",
        f"- 中太平洋u10残差与次年Ekman Q20：r={lookup.loc['u10_to_ekman'].pearson_r:+.2f}，置换p={lookup.loc['u10_to_ekman'].permutation_p:.3f}。",
        f"- 中太平洋u10残差与次年地转Q20：r={lookup.loc['u10_to_geo'].pearson_r:+.2f}，置换p={lookup.loc['u10_to_geo'].permutation_p:.3f}。",
        f"- 中太平洋u10残差与次年总Q20：r={lookup.loc['u10_to_total'].pearson_r:+.2f}，置换p={lookup.loc['u10_to_total'].permutation_p:.3f}。",
        "",
        "风耦合与Ekman项有关、与地转项无关，这是总出口关系被削弱的原因。把MJJ u10残差和次年地转Q20同时放入两变量诊断回归，总出口的样本内R²为"
        f"{regression['in_sample_r_squared']:.2f}，留一预测相关为{regression['loeo_prediction_r']:+.2f}；标准化系数分别为u10 {regression['standardized_beta_u10']:+.2f}、地转项 {regression['standardized_beta_geostrophic']:+.2f}。该回归用于说明两项互补，不能解释为独立因果效应。",
        "",
        "## 三个事件",
        "",
        "| 事件 | MJJ NE925 | MJJ中太平洋u10残差 | 次年Ekman Q20 | 次年地转Q20 | 次年总Q20 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in HIGHLIGHT_YEARS:
        row = events.loc[events.year.eq(year)].iloc[0]
        lines.append(
            f"| {year} | {row.ne925_mjj_ms:+.2f} m s⁻¹ | {row.u10_central_mjj_residual_ms:+.2f} m s⁻¹ | "
            f"{row.q5n_ekman_jan_may1_zj:+.2f} ZJ | {row.q5n_geo_eos80_jan_may1_zj:+.2f} ZJ | {row.q5n_total_jan_may1_zj:+.2f} ZJ |"
        )
    lines += [
        "",
        "1997和2015的MJJ赤道西风残差均约+1.4 m s⁻¹，2023为-0.55 m s⁻¹；这与2023较强Jiang型东北风相一致。2015与2023的地转项同为约-1.27 ZJ，因而二者总出口差异主要来自Ekman分支；1997的地转项为正，使强Ekman输出没有被压力项抵消。",
        "",
        "## 对第三个问题的更新答案",
        "",
        "可以把耦合链条收束为：",
        "",
        "```text",
        "FEP与降水偶极",
        "      ↓",
        "MJJ Jiang区东北风/向西应力",
        "      ↓  抑制",
        "中太平洋赤道西风和Bjerknes反馈",
        "      ↓  跨季节投影",
        "次年5°N局地向西应力 → Ekman H20北向输出",
        "                         + 地转压力项",
        "                         = 总H20出口",
        "```",
        "",
        "因此，东北风是发展期海气耦合的抑制门；局地5°N风应力是后期Ekman放电门；SSH/密度决定的地转项是净出口能否真正打开的海洋门。",
        "",
        "## 证据边界",
        "",
        "1. 只有13个事件，相关和回归均为事件级诊断；置换、bootstrap和留一检验只能约束稳健性，不能替代耦合模式实验。",
        "2. MJJ西风与次年Ekman输出的跨季节关系不表示同一阵风持续存在；它反映事件耦合状态的阶段衔接。",
        "3. Ekman Q20直接使用风应力计算，局地应力—Ekman关系包含定义上的机械联系；真正独立的证据是发展期ERA5风与后期SODA3诊断之间的跨产品联系。",
        "4. Hovmöller使用物理u10距平；散点使用去除Niño-3.4和SST型态后的u10残差，两者用途不同，不能把颜色数值直接当作散点横坐标。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    hov, central = load_equatorial_u10()
    hov_frame = build_hov_table(hov)
    events = build_event_table(central)
    relation = relationships(events)
    regression = multiple_regression(events)
    hov_frame.to_csv(HOV_TABLE, index=False, float_format="%.9g")
    events.to_csv(EVENT_TABLE, index=False, float_format="%.9g")
    relation.to_csv(RELATIONSHIPS, index=False, float_format="%.9g")
    DIAGNOSTICS.write_text(json.dumps(regression, indent=2), encoding="utf-8")
    plot_hovmoller(hov_frame, events)
    plot_chain(events, relation)
    write_report(events, relation, regression)
    print(EVENT_TABLE)
    print(RELATIONSHIPS)
    print(HOV_PNG)
    print(CHAIN_PNG)
    print(REPORT)


if __name__ == "__main__":
    main()
