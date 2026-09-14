#!/usr/bin/env python3
"""Jiang-style SODA3 five-day lead-lag analysis for 1980-2024.

The calculation follows the SST-residual logic of Jiang et al. (2026):
FEP' = b * Nino3.4' + residual_FEP.  A 15-year trailing window is used for
lead-lag correlations.  Positive lag means residual FEP precedes Nino3.4.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_soda3_jiang_lag")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t as student_t


INPUT = (
    ROOT
    / "data/interim/research_2026/soda3_5day_sst/"
    "soda3_5day_nino34_fep_sst_1980_2024.csv"
)
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_jiang_5day_leadlag"

INDEX_CSV = DERIVED / "soda3_jiang_5day_nino34_residual_fep_1980_2024.csv"
CORR_CSV = DERIVED / "soda3_jiang_5day_leadlag_corr_trailing15.csv"
PEAK_CSV = DERIVED / "soda3_jiang_5day_peak_delay_trailing15.csv"
BOOT_CSV = DERIVED / "soda3_jiang_5day_selected_delay_bootstrap.csv"
SENSITIVITY_CSV = DERIVED / "soda3_jiang_5day_window_sensitivity.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_jiang_5day_leadlag_diagnostics.json"
FIGURE_PNG = OUT / "soda3_jiang_5day_leadlag_1980_2024.png"
FIGURE_SVG = OUT / "soda3_jiang_5day_leadlag_1980_2024.svg"
FIGURE_DELAY_PNG = OUT / "soda3_jiang_5day_peak_delay_sensitivity.png"
REPORT_MD = OUT / "SODA3_JIANG_5DAY_LEADLAG_RESULT_CN.md"

START_YEAR = 1980
END_YEAR = 2024
PRIMARY_WINDOW_YEARS = 15
LAGS = np.arange(-36, 37, dtype=int)  # +/-180 days, five-day steps
SMOOTH_PENTADS = 3  # 15-day mean, still sampled every five days
RNG_SEED = 20260803
N_BOOTSTRAP = 3000
SELECTED_END_YEARS = (1994, 2005, 2024)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 450,
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Arial Unicode MS",
                "PingFang SC",
                "Hiragino Sans GB",
                "DejaVu Sans",
            ],
            "font.size": 8.5,
            "axes.titlesize": 10.3,
            "axes.labelsize": 9.0,
            "axes.linewidth": 0.85,
            "xtick.labelsize": 7.7,
            "ytick.labelsize": 7.7,
            "legend.fontsize": 7.2,
            "contour.negative_linestyle": "solid",
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
        }
    )


def prepare_indices() -> tuple[pd.DataFrame, dict[str, float]]:
    raw = pd.read_csv(INPUT, parse_dates=["time"]).sort_values("time")
    required = {"time", "year", "nino34_sst_c", "fep_sst_c"}
    if not required.issubset(raw.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(raw.columns))}")
    if raw["time"].duplicated().any():
        raise ValueError("Duplicate five-day timestamps")
    years = sorted(raw["year"].unique())
    if years != list(range(START_YEAR, END_YEAR + 1)):
        raise ValueError(f"Unexpected year coverage: {years[0]}-{years[-1]}")

    missing_before = int(raw[["nino34_sst_c", "fep_sst_c"]].isna().any(axis=1).sum())
    if missing_before > 20:
        raise ValueError(f"Too many missing SODA3 pentads: {missing_before}")
    for column in ("nino34_sst_c", "fep_sst_c"):
        missing = raw[column].isna()
        run_id = missing.ne(missing.shift(fill_value=False)).cumsum()
        run_size = missing.groupby(run_id).transform("sum")
        interpolated = raw[column].interpolate(method="linear", limit_direction="both")
        raw.loc[missing & run_size.le(2), column] = interpolated.loc[
            missing & run_size.le(2)
        ]
    missing_after = int(raw[["nino34_sst_c", "fep_sst_c"]].isna().any(axis=1).sum())

    raw["day_of_year"] = raw["time"].dt.dayofyear
    raw["pentad_bin"] = ((raw["day_of_year"] - 1) // 5 + 1).clip(upper=73)
    climatology = raw.groupby("pentad_bin")[["nino34_sst_c", "fep_sst_c"]].mean()
    raw["nino34_anom_c"] = raw["nino34_sst_c"] - raw["pentad_bin"].map(
        climatology["nino34_sst_c"]
    )
    raw["fep_anom_c"] = raw["fep_sst_c"] - raw["pentad_bin"].map(
        climatology["fep_sst_c"]
    )

    decimal_year = raw["year"] + (raw["day_of_year"] - 0.5) / np.where(
        raw["time"].dt.is_leap_year, 366.0, 365.0
    )
    for source, target in (
        ("nino34_anom_c", "nino34_detrended_c"),
        ("fep_anom_c", "fep_detrended_c"),
    ):
        values = raw[source].to_numpy(dtype=float)
        valid = np.isfinite(values)
        coefficient = np.polyfit(decimal_year[valid], values[valid], 1)
        raw[target] = values - np.polyval(coefficient, decimal_year)

    x = raw["nino34_detrended_c"].to_numpy(dtype=float)
    y = raw["fep_detrended_c"].to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    slope = float(np.sum(x[valid] * y[valid]) / np.sum(x[valid] * x[valid]))
    raw["fep_expected_from_nino34_c"] = slope * raw["nino34_detrended_c"]
    raw["residual_fep_c"] = (
        raw["fep_detrended_c"] - raw["fep_expected_from_nino34_c"]
    )

    # A centered 15-day mean suppresses individual assimilation/weather noise,
    # while the lead-lag grid remains five-day rather than monthly.
    for source in ("nino34_detrended_c", "residual_fep_c"):
        raw[f"{source}_15day"] = raw[source].rolling(
            SMOOTH_PENTADS, center=True, min_periods=2
        ).mean()

    within_intervals = raw.groupby("year")["time"].diff().dt.days.dropna()
    counts = raw.groupby("year").size()
    qa = {
        "n_records": int(len(raw)),
        "n_years": int(raw["year"].nunique()),
        "minimum_records_per_year": int(counts.min()),
        "maximum_records_per_year": int(counts.max()),
        "records_2024": int(counts.get(2024, 0)),
        "source_pentads_interpolated": missing_before - missing_after,
        "source_pentads_remaining_missing": missing_after,
        "within_year_interval_min_days": float(within_intervals.min()),
        "within_year_interval_median_days": float(within_intervals.median()),
        "within_year_interval_max_days": float(within_intervals.max()),
        "fep_on_nino34_slope": slope,
        "nino34_range_c": [
            float(raw["nino34_sst_c"].min()),
            float(raw["nino34_sst_c"].max()),
        ],
        "fep_range_c": [float(raw["fep_sst_c"].min()), float(raw["fep_sst_c"].max())],
    }
    return raw, qa


def lagged_pairs(
    frame: pd.DataFrame,
    end_year: int,
    lag: int,
    window_years: int,
) -> pd.DataFrame:
    start_year = end_year - window_years + 1
    base_mask = frame["year"].between(start_year, end_year)
    pairs = pd.DataFrame(
        {
            "year": frame["year"],
            "residual": frame["residual_fep_c_15day"],
            # Positive lag: Nino3.4 is sampled later, so residual FEP leads.
            "nino34": frame["nino34_detrended_c_15day"].shift(-int(lag)),
        }
    ).loc[base_mask]
    return pairs.dropna()


def effective_p_value(x: np.ndarray, y: np.ndarray, correlation: float) -> tuple[float, float]:
    if len(x) < 8 or not np.isfinite(correlation):
        return np.nan, np.nan
    r1x = float(np.corrcoef(x[:-1], x[1:])[0, 1])
    r1y = float(np.corrcoef(y[:-1], y[1:])[0, 1])
    product = float(np.clip(r1x * r1y, -0.98, 0.98))
    neff = float(np.clip(len(x) * (1.0 - product) / (1.0 + product), 3.0, len(x)))
    denominator = max(1.0e-12, 1.0 - correlation**2)
    statistic = abs(correlation) * np.sqrt(max(1.0, neff - 2.0) / denominator)
    p_value = float(2.0 * student_t.sf(statistic, df=max(1.0, neff - 2.0)))
    return neff, p_value


def build_correlations(
    frame: pd.DataFrame,
    *,
    window_years: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    first_end = START_YEAR + window_years - 1
    for end_year in range(first_end, END_YEAR + 1):
        for lag in LAGS:
            pairs = lagged_pairs(frame, end_year, int(lag), window_years)
            x = pairs["residual"].to_numpy(dtype=float)
            y = pairs["nino34"].to_numpy(dtype=float)
            corr = float(np.corrcoef(x, y)[0, 1]) if len(pairs) >= 500 else np.nan
            neff, p_value = effective_p_value(x, y, corr)
            rows.append(
                {
                    "window_years": int(window_years),
                    "window_start_year": int(end_year - window_years + 1),
                    "window_end_year": int(end_year),
                    "lag_pentads": int(lag),
                    "lag_days": int(lag * 5),
                    "correlation": corr,
                    "n_pairs": int(len(pairs)),
                    "effective_n": neff,
                    "effective_p": p_value,
                    "sign_convention": "positive lag = residual FEP leads Nino3.4",
                }
            )
    correlations = pd.DataFrame(rows)
    peak_rows = []
    for end_year, current in correlations.groupby("window_end_year"):
        valid = current.dropna(subset=["correlation"])
        all_peak = valid.loc[valid["correlation"].idxmax()]
        positive = valid.loc[valid["lag_pentads"].ge(0)]
        fep_peak = positive.loc[positive["correlation"].idxmax()]
        negative = valid.loc[valid["lag_pentads"].le(0)]
        nino_peak = negative.loc[negative["correlation"].idxmax()]
        peak_rows.append(
            {
                "window_years": int(window_years),
                "window_start_year": int(all_peak["window_start_year"]),
                "window_end_year": int(end_year),
                "global_peak_lag_days": int(all_peak["lag_days"]),
                "global_peak_correlation": float(all_peak["correlation"]),
                "global_peak_effective_p": float(all_peak["effective_p"]),
                "fep_lead_peak_days": int(fep_peak["lag_days"]),
                "fep_lead_peak_correlation": float(fep_peak["correlation"]),
                "nino34_lead_peak_days": int(nino_peak["lag_days"]),
                "nino34_lead_peak_correlation": float(nino_peak["correlation"]),
            }
        )
    return correlations, pd.DataFrame(peak_rows)


def selected_bootstrap(frame: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for end_year in SELECTED_END_YEARS:
        start_year = end_year - PRIMARY_WINDOW_YEARS + 1
        years = np.arange(start_year, end_year + 1)
        lag_year_pairs: dict[int, dict[int, tuple[np.ndarray, np.ndarray]]] = {}
        for lag in LAGS:
            pairs = lagged_pairs(frame, end_year, int(lag), PRIMARY_WINDOW_YEARS)
            lag_year_pairs[int(lag)] = {}
            for year, group in pairs.groupby("year"):
                lag_year_pairs[int(lag)][int(year)] = (
                    group["residual"].to_numpy(dtype=float),
                    group["nino34"].to_numpy(dtype=float),
                )
        peak_samples = np.empty(N_BOOTSTRAP, dtype=float)
        corr_samples = np.empty(N_BOOTSTRAP, dtype=float)
        for index in range(N_BOOTSTRAP):
            selected = rng.choice(years, size=len(years), replace=True)
            correlations = []
            positive_lags = LAGS[LAGS >= 0]
            for lag in positive_lags:
                chunks = [lag_year_pairs[int(lag)].get(int(year)) for year in selected]
                chunks = [item for item in chunks if item is not None]
                if not chunks:
                    correlations.append(np.nan)
                    continue
                x = np.concatenate([item[0] for item in chunks])
                y = np.concatenate([item[1] for item in chunks])
                correlations.append(float(np.corrcoef(x, y)[0, 1]))
            values = np.asarray(correlations, dtype=float)
            best = int(np.nanargmax(values))
            peak_samples[index] = positive_lags[best] * 5.0
            corr_samples[index] = values[best]
        rows.append(
            {
                "window_start_year": int(start_year),
                "window_end_year": int(end_year),
                "n_bootstrap": N_BOOTSTRAP,
                "fep_lead_peak_days_median": float(np.median(peak_samples)),
                "fep_lead_peak_days_ci_low": float(np.quantile(peak_samples, 0.025)),
                "fep_lead_peak_days_ci_high": float(np.quantile(peak_samples, 0.975)),
                "peak_correlation_median": float(np.median(corr_samples)),
                "peak_correlation_ci_low": float(np.quantile(corr_samples, 0.025)),
                "peak_correlation_ci_high": float(np.quantile(corr_samples, 0.975)),
            }
        )
    return pd.DataFrame(rows)


def plot_main(correlations: pd.DataFrame, peaks: pd.DataFrame) -> None:
    setup_style()
    lags = np.sort(correlations["lag_days"].unique())
    years = np.sort(correlations["window_end_year"].unique())
    grid = (
        correlations.pivot(index="window_end_year", columns="lag_days", values="correlation")
        .reindex(index=years, columns=lags)
        .to_numpy()
    )
    p_grid = (
        correlations.pivot(index="window_end_year", columns="lag_days", values="effective_p")
        .reindex(index=years, columns=lags)
        .to_numpy()
    )

    figure, axes = plt.subplots(
        1,
        2,
        figsize=(8.8, 8.7),
        gridspec_kw={"width_ratios": [1.28, 0.72]},
        sharey=True,
    )
    figure.subplots_adjust(left=0.10, right=0.96, bottom=0.15, top=0.89, wspace=0.27)
    levels = np.linspace(-0.9, 0.9, 19)
    image = axes[0].contourf(
        lags, years, grid, levels=levels, cmap="RdBu_r", extend="both"
    )
    axes[0].contour(
        lags,
        years,
        grid,
        levels=[-0.6, -0.3, 0.3, 0.6],
        colors="#343434",
        linewidths=0.42,
        alpha=0.68,
    )
    # Effective-DOF significance is shown sparsely, not as independent-pentad p values.
    yy, xx = np.meshgrid(years, lags, indexing="ij")
    significant = np.isfinite(p_grid) & (p_grid < 0.05)
    sparse = significant & ((xx % 20) == 0) & ((yy % 2) == 0)
    axes[0].scatter(xx[sparse], yy[sparse], s=2.3, color="black", alpha=0.48, linewidth=0)
    axes[0].axvline(0.0, color="#202020", ls="--", lw=1.15)
    axes[0].plot(
        peaks["global_peak_lag_days"],
        peaks["window_end_year"],
        color="white",
        lw=2.3,
        alpha=0.95,
    )
    axes[0].plot(
        peaks["global_peak_lag_days"],
        peaks["window_end_year"],
        color="#111111",
        lw=0.8,
        marker="o",
        ms=2.5,
        label="最大相关滞后",
    )
    axes[0].set_xlim(-180, 180)
    axes[0].set_xticks(np.arange(-180, 181, 60))
    axes[0].set_xlabel("滞后时间（天）")
    axes[0].set_ylabel("15年滑动窗结束年份")
    axes[0].set_title(
        "(a) Niño3.4与残余FEP的领先—滞后相关",
        loc="left",
        fontweight="bold",
    )
    axes[0].text(-118, 1995.1, "Niño3.4领先", fontweight="bold", ha="center")
    axes[0].text(103, 1995.1, "残余FEP领先", fontweight="bold", ha="center")
    axes[0].legend(frameon=False, loc="upper left")

    scatter = axes[1].scatter(
        peaks["global_peak_lag_days"],
        peaks["window_end_year"],
        c=peaks["global_peak_correlation"],
        cmap="YlOrRd",
        vmin=0.2,
        vmax=0.75,
        s=30,
        edgecolor="white",
        linewidth=0.45,
        zorder=3,
    )
    axes[1].plot(
        peaks["global_peak_lag_days"],
        peaks["window_end_year"],
        color="#515151",
        lw=0.9,
        zorder=1,
    )
    axes[1].axvline(0.0, color="#202020", ls="--", lw=1.0)
    axes[1].axvspan(0.0, 180.0, color="#F5EBD8", alpha=0.48, zorder=0)
    axes[1].set_xlim(-180, 180)
    axes[1].set_xticks(np.arange(-180, 181, 60))
    axes[1].set_xlabel("最大相关对应延迟（天）")
    axes[1].set_title("(b) 延迟脊线", loc="left", fontweight="bold")
    cbar_ridge = figure.colorbar(scatter, ax=axes[1], orientation="horizontal", pad=0.08, fraction=0.045)
    cbar_ridge.set_label("峰值相关")

    for ax in axes:
        ax.set_ylim(1980, 2024.7)
        ax.set_yticks(np.arange(1980, 2025, 5))
        ax.axhspan(1980, 1993.5, color="#E8E8E8", alpha=0.95, zorder=8)
        ax.text(
            0.5,
            0.15,
            "SODA3始于1980：不足15年窗口",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=7.0,
            color="#666666",
            zorder=9,
        )
        ax.tick_params(direction="out", length=3.0)

    cbar = figure.colorbar(
        image,
        ax=axes[0],
        orientation="horizontal",
        pad=0.08,
        fraction=0.045,
        ticks=[-0.9, -0.6, -0.3, 0, 0.3, 0.6, 0.9],
    )
    cbar.set_label("相关系数")
    figure.suptitle(
        "Jiang方法的SODA3五日延迟图（1980—2024）",
        fontsize=13.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.10,
        0.025,
        "SODA3.15.2约5 m温度；Niño3.4=5°S–5°N,170°W–120°W；FEP=5°S–5°N,90°W–80°W。"
        "1980–2024五日气候态和线性趋势已去除，曲线先做15日平均。正滞后表示残余FEP领先。"
        "2024资料截至12月2日。黑点为考虑一阶自相关后的p<0.05稀疏标记。",
        fontsize=7.0,
        color="#4E4E4E",
        ha="left",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight", pad_inches=0.12)
    figure.savefig(FIGURE_SVG, bbox_inches="tight", pad_inches=0.12)
    plt.close(figure)


def plot_sensitivity(
    all_peaks: pd.DataFrame, bootstrap: pd.DataFrame, correlations: pd.DataFrame
) -> None:
    setup_style()
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4))
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.18, top=0.84, wspace=0.24)
    colors = {9: "#679AC1", 15: "#B33B2E"}
    for window, group in all_peaks.groupby("window_years"):
        axes[0].plot(
            group["window_end_year"],
            group["global_peak_lag_days"],
            color=colors[int(window)],
            lw=1.5,
            marker="o",
            ms=3,
            label=f"{int(window)}年滑动窗",
        )
    axes[0].axhline(0.0, color="#333333", ls="--", lw=0.9)
    axes[0].set_xlim(1988, 2024)
    axes[0].set_ylim(-185, 185)
    axes[0].set_xlabel("滑动窗结束年份")
    axes[0].set_ylabel("最大相关对应延迟（天）")
    axes[0].set_title("(a) 滑动窗长度敏感性", loc="left", fontweight="bold")
    axes[0].grid(color="#E6E6E6", lw=0.55)
    axes[0].legend(frameon=False)

    chosen_colors = {1994: "#5A7D9A", 2005: "#E28E2C", 2024: "#B7352D"}
    for year in SELECTED_END_YEARS:
        current = correlations.loc[correlations["window_end_year"].eq(year)]
        boot = bootstrap.loc[bootstrap["window_end_year"].eq(year)].iloc[0]
        axes[1].plot(
            current["lag_days"],
            current["correlation"],
            color=chosen_colors[year],
            lw=1.6,
            label=(
                f"{year}窗：FEP领先峰值"
                f"{boot['fep_lead_peak_days_median']:.0f}天 "
                f"[{boot['fep_lead_peak_days_ci_low']:.0f}, {boot['fep_lead_peak_days_ci_high']:.0f}]"
            ),
        )
    axes[1].axvline(0.0, color="#333333", ls="--", lw=0.9)
    axes[1].axhline(0.0, color="#777777", lw=0.55)
    axes[1].set_xlim(-180, 180)
    axes[1].set_xticks(np.arange(-180, 181, 60))
    axes[1].set_xlabel("滞后时间（天；正值为残余FEP领先）")
    axes[1].set_ylabel("相关系数")
    axes[1].set_title("(b) 三个时期的相关曲线", loc="left", fontweight="bold")
    axes[1].grid(color="#E6E6E6", lw=0.55)
    axes[1].legend(frameon=False, loc="best")
    figure.suptitle("SODA3五日延迟结果的稳健性检查", fontsize=12.2, fontweight="bold")
    figure.savefig(FIGURE_DELAY_PNG, bbox_inches="tight", pad_inches=0.10)
    plt.close(figure)


def direction_text(days: float) -> str:
    if days > 0:
        return f"残余FEP领先Niño3.4约{days:.0f}天"
    if days < 0:
        return f"Niño3.4领先残余FEP约{abs(days):.0f}天"
    return "两者近乎同步"


def main() -> int:
    frame, qa = prepare_indices()
    primary_corr, primary_peaks = build_correlations(
        frame, window_years=PRIMARY_WINDOW_YEARS
    )
    short_corr, short_peaks = build_correlations(frame, window_years=9)
    bootstrap = selected_bootstrap(frame)
    all_peaks = pd.concat([short_peaks, primary_peaks], ignore_index=True)

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(INDEX_CSV, index=False, date_format="%Y-%m-%d")
    primary_corr.to_csv(CORR_CSV, index=False)
    primary_peaks.to_csv(PEAK_CSV, index=False)
    bootstrap.to_csv(BOOT_CSV, index=False)
    all_peaks.to_csv(SENSITIVITY_CSV, index=False)

    plot_main(primary_corr, primary_peaks)
    plot_sensitivity(all_peaks, bootstrap, primary_corr)

    selected = primary_peaks.set_index("window_end_year").loc[list(SELECTED_END_YEARS)]
    recent = selected.loc[2024]
    recent_boot = bootstrap.set_index("window_end_year").loc[2024]
    positive_fraction = float(np.mean(primary_peaks["global_peak_lag_days"] > 0.0))
    recent_decade = primary_peaks.loc[primary_peaks["window_end_year"].ge(2015)]
    recent_positive_fraction = float(np.mean(recent_decade["global_peak_lag_days"] > 0.0))
    diagnostics = {
        "method": "Jiang et al. 2026 SST residual lead-lag logic",
        "data": "SODA3.15.2 five-day shallowest tracer temperature (~5 m)",
        "time": "1980-01 through 2024-12-02",
        "regions": {
            "nino34": "5S-5N, 170W-120W",
            "fep": "5S-5N, 90W-80W",
        },
        "primary_window_years": PRIMARY_WINDOW_YEARS,
        "lag_range_days": [-180, 180],
        "lag_step_days": 5,
        "smoothing_days": 15,
        "positive_lag": "residual FEP leads Nino3.4",
        "quality_control": qa,
        "positive_global_peak_fraction": positive_fraction,
        "positive_global_peak_fraction_2015_2024": recent_positive_fraction,
        "limitations": [
            "SODA3 begins in 1980, so a full 15-year trailing result starts in 1994.",
            "2024 contains 68 pentads and ends on 2 December, not 31 December.",
            "Correlation peak is a timing association, not a causal propagation speed.",
            "Five-day SODA3 is a reanalysis and the shallowest tracer temperature is about 5 m, not a skin SST product.",
        ],
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    selected_lines = []
    for year in SELECTED_END_YEARS:
        row = selected.loc[year]
        boot = bootstrap.set_index("window_end_year").loc[year]
        selected_lines.append(
            f"| {int(row['window_start_year'])}—{year} | "
            f"{direction_text(row['global_peak_lag_days'])} | "
            f"{row['global_peak_correlation']:.2f} | "
            f"{boot['fep_lead_peak_days_median']:.0f} "
            f"[{boot['fep_lead_peak_days_ci_low']:.0f}, {boot['fep_lead_peak_days_ci_high']:.0f}] |"
        )

    report = f"""# Jiang方法的SODA3五日延迟分析（1980—2024）

## 方法改变

本结果完全撤掉此前的“海洋门”。延迟只按照Jiang et al.（2026）的SST残差方法定义：

`FEP'(t) = b × Niño3.4'(t) + residual FEP(t)`。

先由SODA3.15.2五日浅表层温度计算Niño3.4和FEP区域平均，扣除1980—2024五日气候态及线性趋势，再从FEP中去除与同期Niño3.4线性相关的部分。随后计算15年trailing window的领先—滞后相关：

`R(L) = corr[residual FEP(t), Niño3.4(t+L)]`。

因此 **L>0表示残余FEP领先Niño3.4**。为保留SODA3的高频优势并削弱单个同化周期噪声，序列先做15日平均，但每5天计算一个滞后；主分析范围取±180天，聚焦ENSO发展季而避免跨年季节循环主导峰值。

## 主要结果

- 15年窗所有可计算年份中，最大相关位于正滞后的比例为 **{positive_fraction:.0%}**；2015—2024结束窗中为 **{recent_positive_fraction:.0%}**。
- 最新2010—2024窗的全域峰值为 **L={recent['global_peak_lag_days']:.0f}天，r={recent['global_peak_correlation']:.2f}**，即 **{direction_text(recent['global_peak_lag_days'])}**。
- 仅在正滞后一侧做年份块bootstrap，2010—2024窗的FEP领先峰值中位数为 **{recent_boot['fep_lead_peak_days_median']:.0f}天**，95%区间 **[{recent_boot['fep_lead_peak_days_ci_low']:.0f}, {recent_boot['fep_lead_peak_days_ci_high']:.0f}]天**。区间宽度反映15年内事件差异，不能把单个峰值解释成固定传播时间。

| 15年窗口 | 全域最大相关方向 | 峰值r | 正滞后峰值bootstrap中位数[95%区间]/天 |
|---|---|---:|---:|
{chr(10).join(selected_lines)}

## 图的读法

- 左图沿用Jiang Fig. 4的“年份—滞后时间”结构，色阶为相关系数；白边黑线是每个15年窗的最大相关脊线。
- 右图直接把脊线抽出来。零线右侧表示残余FEP先变化，左侧表示Niño3.4先变化。
- 1980—1993留灰不是缺图，而是SODA3从1980开始，无法构成完整15年窗口；正式结果从1994开始。补充图给出9年窗敏感性，可提前到1988，但统计更不稳定。

## 科学边界

这里得到的“延迟”是两个SST模态的统计相位差，不是暖水平流时间、Kelvin波传播时间，也不直接代表大气耦合延迟。它最适合回答Jiang的问题：远东太平洋的独立暖异常在不同年代是领先还是滞后于盆地尺度Niño3.4演变。

## 输出

- Jiang风格主图：`{FIGURE_PNG}`
- 滑动窗敏感性图：`{FIGURE_DELAY_PNG}`
- 五日指数与残余：`{INDEX_CSV}`
- 完整相关矩阵：`{CORR_CSV}`
- 逐窗峰值延迟：`{PEAK_CSV}`
- 选定时期bootstrap：`{BOOT_CSV}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
