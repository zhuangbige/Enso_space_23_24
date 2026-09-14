#!/usr/bin/env python3
"""Reproduce the Chakravorty et al. (2021) Fig. 8 logic with SODA3.15.2.

The analysis deliberately separates two products:

1. a paper-comparable, standardized D20 warm-volume transport diagnostic;
2. an unstandardized Q20 heat-transport anomaly diagnostic in PW.

It uses only the published event partition that overlaps SODA3 (four CT and
four CP events), removes each calendar month's linear climatology/trend,
applies a centered three-month running mean, and estimates uncertainty by
resampling whole events rather than treating months as independent samples.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


INPUT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_chakravorty_transport_baseline_1980_2022.csv"
)
EXISTING_TRANSPORT_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_warm_transport_longitude_1980_2024.csv"
)
EXISTING_WWV_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_transition_process_indices_1980_2024.csv"
)
OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/chakravorty2021_soda3_baseline"
OUT_PDF = ROOT / "output/pdf"

PROCESSED_CSV = OUT_DATA / "chakravorty2021_soda3_monthly_processed_1980_2022.csv"
EVENT_ALIGNED_CSV = OUT_DATA / "chakravorty2021_soda3_event_aligned_members.csv"
COMPOSITE_CSV = OUT_DATA / "chakravorty2021_soda3_composite_legacy_events.csv"
PHASE_CSV = OUT_DATA / "chakravorty2021_soda3_phase_summary.csv"
DIFFERENCE_CSV = OUT_DATA / "chakravorty2021_soda3_ct_minus_cp_phase_differences.csv"
DIAGNOSTICS_JSON = OUT_DATA / "chakravorty2021_soda3_diagnostics.json"
FIGURE_PNG = OUT_DIR / "chakravorty2021_fig8_logic_soda3.png"
FIGURE_PDF = OUT_PDF / "chakravorty2021_fig8_logic_soda3.pdf"
SUMMARY_MD = OUT_DIR / "CHAKRAVORTY2021_SODA3_BASELINE_CN.md"

BASELINE = (1980, 2022)
RELATIVE_MONTHS = np.arange(-6, 17)
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260803

EVENTS = {
    "CT": (1982, 1986, 1997, 2006),
    "CP": (1991, 1994, 2002, 2004),
}

RAW_METRICS = {
    "zt170_sv": "zonal_170e_10s5n_warm_volume_sv",
    "mt5n_sv": "meridional_5n_equatorward_warm_volume_sv",
    "mt10s_sv": "meridional_10s_equatorward_warm_volume_sv",
    "wwv": "wwv_5s5n_120e80w_1e14m3",
    "zt170_q20": "zonal_170e_10s5n_q20_pw",
    "mt5n_q20": "meridional_5n_equatorward_q20_pw",
    "mt10s_q20": "meridional_10s_equatorward_q20_pw",
}

STANDARDIZED_METRICS = {
    "zt170_sv_z": "ZT 170°E",
    "mt5n_sv_z": "MT 5°N",
    "mt10s_sv_z": "MT 10°S",
    "wwv_z": "WWV TPO",
}

Q20_METRICS = {
    "zt170_q20_sm3": "ZT 170°E",
    "mt5n_q20_sm3": "MT 5°N",
    "mt10s_q20_sm3": "MT 10°S",
}

COLORS = {
    "ZT 170°E": "#222222",
    "MT 5°N": "#D55E00",
    "MT 10°S": "#009E73",
    "WWV TPO": "#3366CC",
}

PHASES = {
    "preconditioning_Jul-1_to_May0": (-6, 4),
    "development_Jun0_to_Nov0": (5, 10),
    "mature_decay_Dec0_to_May1": (11, 16),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_CSV)
    parser.add_argument("--bootstrap-samples", type=int, default=BOOTSTRAP_SAMPLES)
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.4,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 8.0,
            "lines.linewidth": 1.9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def same_month_detrended(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int] = BASELINE,
) -> np.ndarray:
    """Remove a calendar-month-specific linear climatology and trend."""
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in range(1, 13):
        selected = (
            (times.month == month)
            & np.isfinite(values)
            & (times.year >= baseline[0])
            & (times.year <= baseline[1])
        )
        if selected.sum() < 3:
            continue
        years = times.year[selected].astype(float)
        design = np.column_stack([np.ones(selected.sum()), years])
        intercept, slope = np.linalg.lstsq(
            design,
            values[selected],
            rcond=None,
        )[0]
        apply = (times.month == month) & np.isfinite(values)
        output[apply] = values[apply] - (
            intercept + slope * times.year[apply].astype(float)
        )
    return output


def process_monthly(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    required = {"time", "year", "month", *RAW_METRICS.values()}
    missing = required - set(raw.columns)
    if missing:
        raise KeyError(f"Missing input columns: {sorted(missing)}")
    output = raw.copy().sort_values("time").reset_index(drop=True)
    output["time"] = pd.to_datetime(output["time"])
    times = pd.DatetimeIndex(output["time"])
    expected = pd.date_range("1980-01-01", "2022-12-01", freq="MS") + pd.Timedelta(
        days=14
    )
    if not times.equals(expected):
        raise ValueError("Input does not contain the complete 1980-2022 monthly axis")

    standard_deviations: dict[str, float] = {}
    for short_name, source_name in RAW_METRICS.items():
        anomaly = same_month_detrended(output[source_name].to_numpy(), times)
        smoothed = (
            pd.Series(anomaly)
            .rolling(window=3, center=True, min_periods=3)
            .mean()
            .to_numpy()
        )
        standard_deviation = float(np.nanstd(smoothed, ddof=1))
        if not np.isfinite(standard_deviation) or standard_deviation <= 0.0:
            raise ValueError(f"Invalid standard deviation for {short_name}")
        output[f"{short_name}_anom"] = anomaly
        output[f"{short_name}_sm3"] = smoothed
        output[f"{short_name}_z"] = smoothed / standard_deviation
        standard_deviations[short_name] = standard_deviation
    return output, standard_deviations


def event_matrix(
    processed: pd.DataFrame,
    event_years: tuple[int, ...],
    metric: str,
) -> np.ndarray:
    indexed = processed.set_index(pd.DatetimeIndex(processed["time"]))
    rows: list[np.ndarray] = []
    for event_year in event_years:
        timestamps = pd.DatetimeIndex(
            [
                pd.Timestamp(event_year, 1, 15) + pd.DateOffset(months=int(offset))
                for offset in RELATIVE_MONTHS
            ]
        )
        if not timestamps.isin(indexed.index).all():
            absent = timestamps[~timestamps.isin(indexed.index)]
            raise ValueError(f"Missing event months for {event_year}: {list(absent)}")
        rows.append(indexed.loc[timestamps, metric].to_numpy(dtype=float))
    matrix = np.vstack(rows)
    if not np.isfinite(matrix).all():
        raise ValueError(f"Non-finite composite values for {metric}")
    return matrix


def bootstrap_composites(
    processed: pd.DataFrame,
    bootstrap_samples: int,
) -> pd.DataFrame:
    if bootstrap_samples < 100:
        raise ValueError("At least 100 bootstrap samples are required")
    metrics = [
        *STANDARDIZED_METRICS,
        *Q20_METRICS,
        "wwv_sm3",
    ]
    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, float | int | str]] = []
    for event_class, event_years in EVENTS.items():
        for metric in metrics:
            matrix = event_matrix(processed, event_years, metric)
            draw_indices = rng.integers(
                0,
                matrix.shape[0],
                size=(bootstrap_samples, matrix.shape[0]),
            )
            bootstrap_means = matrix[draw_indices, :].mean(axis=1)
            mean = matrix.mean(axis=0)
            low, high = np.quantile(bootstrap_means, [0.025, 0.975], axis=0)
            for index, relative_month in enumerate(RELATIVE_MONTHS):
                rows.append(
                    {
                        "event_class": event_class,
                        "event_years": ",".join(map(str, event_years)),
                        "n_events": len(event_years),
                        "relative_month": int(relative_month),
                        "metric": metric,
                        "mean": float(mean[index]),
                        "ci_low": float(low[index]),
                        "ci_high": float(high[index]),
                        "ci_excludes_zero": bool(
                            low[index] > 0.0 or high[index] < 0.0
                        ),
                    }
                )
    return pd.DataFrame(rows)


def event_aligned_table(processed: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        *STANDARDIZED_METRICS,
        *Q20_METRICS,
        "wwv_sm3",
    ]
    indexed = processed.set_index(pd.DatetimeIndex(processed["time"]))
    rows: list[dict[str, float | int | str | pd.Timestamp]] = []
    for event_class, event_years in EVENTS.items():
        for event_year in event_years:
            for relative_month in RELATIVE_MONTHS:
                timestamp = pd.Timestamp(event_year, 1, 15) + pd.DateOffset(
                    months=int(relative_month)
                )
                row: dict[str, float | int | str | pd.Timestamp] = {
                    "event_class": event_class,
                    "event_year": event_year,
                    "relative_month": int(relative_month),
                    "time": timestamp,
                }
                for metric in metrics:
                    row[metric] = float(indexed.loc[timestamp, metric])
                rows.append(row)
    return pd.DataFrame(rows)


def phase_summary(processed: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        *STANDARDIZED_METRICS,
        *Q20_METRICS,
        "wwv_sm3",
    ]
    rows: list[dict[str, float | int | str]] = []
    for event_class, years in EVENTS.items():
        for metric in metrics:
            matrix = event_matrix(processed, years, metric)
            for phase, (start, end) in PHASES.items():
                selected = (RELATIVE_MONTHS >= start) & (RELATIVE_MONTHS <= end)
                event_means = matrix[:, selected].mean(axis=1)
                rows.append(
                    {
                        "event_class": event_class,
                        "event_years": ",".join(map(str, years)),
                        "n_events": len(years),
                        "phase": phase,
                        "metric": metric,
                        "mean": float(event_means.mean()),
                        "event_std": float(event_means.std(ddof=1)),
                        "min_event": float(event_means.min()),
                        "max_event": float(event_means.max()),
                    }
                )
    return pd.DataFrame(rows)


def phase_difference_bootstrap(
    processed: pd.DataFrame,
    bootstrap_samples: int,
) -> pd.DataFrame:
    metrics = [
        *STANDARDIZED_METRICS,
        *Q20_METRICS,
        "wwv_sm3",
    ]
    rng = np.random.default_rng(RANDOM_SEED + 1)
    rows: list[dict[str, float | int | str | bool]] = []
    for metric in metrics:
        ct_matrix = event_matrix(processed, EVENTS["CT"], metric)
        cp_matrix = event_matrix(processed, EVENTS["CP"], metric)
        for phase, (start, end) in PHASES.items():
            selected = (RELATIVE_MONTHS >= start) & (RELATIVE_MONTHS <= end)
            ct_values = ct_matrix[:, selected].mean(axis=1)
            cp_values = cp_matrix[:, selected].mean(axis=1)
            ct_draw = rng.integers(
                0,
                ct_values.size,
                size=(bootstrap_samples, ct_values.size),
            )
            cp_draw = rng.integers(
                0,
                cp_values.size,
                size=(bootstrap_samples, cp_values.size),
            )
            differences = (
                ct_values[ct_draw].mean(axis=1)
                - cp_values[cp_draw].mean(axis=1)
            )
            low, high = np.quantile(differences, [0.025, 0.975])
            rows.append(
                {
                    "contrast": "CT_minus_CP",
                    "ct_n": ct_values.size,
                    "cp_n": cp_values.size,
                    "phase": phase,
                    "metric": metric,
                    "difference": float(ct_values.mean() - cp_values.mean()),
                    "ci_low": float(low),
                    "ci_high": float(high),
                    "ci_excludes_zero": bool(low > 0.0 or high < 0.0),
                }
            )
    return pd.DataFrame(rows)


def composite_series(
    composites: pd.DataFrame,
    event_class: str,
    metric: str,
) -> pd.DataFrame:
    selected = composites[
        (composites["event_class"] == event_class)
        & (composites["metric"] == metric)
    ].sort_values("relative_month")
    if len(selected) != len(RELATIVE_MONTHS):
        raise ValueError(f"Incomplete composite for {event_class}, {metric}")
    return selected


def decorate_time_axis(axis: plt.Axes) -> None:
    labels = [
        (pd.Timestamp(2000, 1, 1) + pd.DateOffset(months=int(month))).strftime("%b")[0]
        for month in RELATIVE_MONTHS
    ]
    axis.set_xlim(RELATIVE_MONTHS[0], RELATIVE_MONTHS[-1])
    axis.set_xticks(RELATIVE_MONTHS)
    axis.set_xticklabels(labels)
    axis.axvspan(10.5, 13.5, color="#E8D7B9", alpha=0.42, lw=0, zorder=0)
    axis.axvline(-0.5, color="0.55", lw=0.75, ls=":", zorder=1)
    axis.axvline(11.5, color="0.55", lw=0.75, ls=":", zorder=1)
    axis.axhline(0.0, color="0.45", lw=0.75, zorder=1)
    axis.grid(axis="y", color="0.90", lw=0.6)
    axis.text(-3.0, -0.15, "Year −1", transform=axis.get_xaxis_transform(), ha="center")
    axis.text(5.5, -0.15, "Year 0", transform=axis.get_xaxis_transform(), ha="center")
    axis.text(14.0, -0.15, "Year +1", transform=axis.get_xaxis_transform(), ha="center")


def plot_figure(composites: pd.DataFrame) -> None:
    setup_style()
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(11.2, 7.0),
        sharex=True,
        constrained_layout=True,
    )
    figure.get_layout_engine().set(w_pad=0.06, h_pad=0.08, wspace=0.08, hspace=0.10)
    wwv_axes: list[plt.Axes] = []

    for column, event_class in enumerate(("CT", "CP")):
        top = axes[0, column]
        for metric, label in STANDARDIZED_METRICS.items():
            series = composite_series(composites, event_class, metric)
            linestyle = "--" if label == "WWV TPO" else "-"
            top.plot(
                RELATIVE_MONTHS,
                series["mean"],
                color=COLORS[label],
                ls=linestyle,
                label=label,
                zorder=3,
            )
            significant = series["ci_excludes_zero"].to_numpy(dtype=bool)
            top.scatter(
                RELATIVE_MONTHS[significant],
                series.loc[significant, "mean"],
                s=9,
                color=COLORS[label],
                edgecolors="white",
                linewidths=0.25,
                zorder=4,
            )
        top.set_title(
            f"{event_class} El Niño — published overlap events (n=4)",
            loc="left",
            fontweight="bold",
        )
        top.set_ylabel("Standardized anomaly (σ)" if column == 0 else "")
        decorate_time_axis(top)

        bottom = axes[1, column]
        for metric, label in Q20_METRICS.items():
            series = composite_series(composites, event_class, metric)
            bottom.plot(
                RELATIVE_MONTHS,
                series["mean"],
                color=COLORS[label],
                label=label,
                zorder=3,
            )
            significant = series["ci_excludes_zero"].to_numpy(dtype=bool)
            bottom.scatter(
                RELATIVE_MONTHS[significant],
                series.loc[significant, "mean"],
                s=9,
                color=COLORS[label],
                edgecolors="white",
                linewidths=0.25,
                zorder=4,
            )
        bottom.set_ylabel("Q20 transport anomaly (PW)" if column == 0 else "")
        decorate_time_axis(bottom)
        wwv_axis = bottom.twinx()
        wwv_axes.append(wwv_axis)
        wwv = composite_series(composites, event_class, "wwv_sm3")
        wwv_axis.plot(
            RELATIVE_MONTHS,
            wwv["mean"],
            color=COLORS["WWV TPO"],
            ls="--",
            lw=1.8,
            label="WWV TPO",
            zorder=2,
        )
        wwv_axis.set_ylabel(
            "WWV anomaly ($10^{14}$ m³)" if column == 1 else "",
            color=COLORS["WWV TPO"],
        )
        wwv_axis.tick_params(axis="y", colors=COLORS["WWV TPO"])
        if column == 0:
            wwv_axis.tick_params(right=False, labelright=False)
        wwv_axis.grid(False)

    top_limit = max(
        2.0,
        float(
            np.ceil(
                composites[composites["metric"].isin(STANDARDIZED_METRICS)][
                    "mean"
                ].abs().max()
                * 5.0
            )
            / 5.0
        ),
    )
    q20_limit = max(
        0.2,
        float(
            np.ceil(
                composites[composites["metric"].isin(Q20_METRICS)]["mean"].abs().max()
                * 10.0
            )
            / 10.0
        ),
    )
    wwv_limit = max(
        0.5,
        float(
            np.ceil(
                composites[composites["metric"] == "wwv_sm3"]["mean"].abs().max()
                * 10.0
            )
            / 10.0
        ),
    )
    for axis in axes[0, :]:
        axis.set_ylim(-top_limit, top_limit)
    for axis in axes[1, :]:
        axis.set_ylim(-q20_limit, q20_limit)
    for axis in wwv_axes:
        axis.set_ylim(-wwv_limit, wwv_limit)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="outside upper center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.5, 1.01),
    )
    figure.suptitle(
        "SODA3.15.2 reproduction of the Chakravorty et al. (2021) transport logic",
        fontsize=12.4,
        fontweight="bold",
        y=1.045,
    )
    figure.text(
        0.01,
        -0.012,
        "Eastward/equatorward positive; 3-month mean. Dots: 95% event-bootstrap CI excludes zero. "
        "Bottom row is unstandardized detrended transport, not raw total heat transport.",
        fontsize=7.8,
        color="0.30",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight", facecolor="white")
    figure.savefig(FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def validate_against_existing(processed: pd.DataFrame) -> dict[str, float | int]:
    output: dict[str, float | int] = {
        "q20_comparison_rows": 0,
        "wwv_comparison_rows": 0,
    }
    if EXISTING_TRANSPORT_CSV.exists():
        existing = pd.read_csv(EXISTING_TRANSPORT_CSV, parse_dates=["time"])
        existing = existing[np.isclose(existing["longitude_e"], 170.0)][
            ["time", "q20_pw"]
        ]
        raw = processed[
            ["time", "zonal_170e_5s5n_q20_pw"]
        ].merge(existing, on="time", how="inner")
        difference = raw["zonal_170e_5s5n_q20_pw"] - raw["q20_pw"]
        output.update(
            q20_comparison_rows=int(len(raw)),
            q20_170e_5s5n_max_abs_difference_pw=float(difference.abs().max()),
            q20_170e_5s5n_correlation=float(
                raw[["zonal_170e_5s5n_q20_pw", "q20_pw"]].corr().iloc[0, 1]
            ),
        )
    if EXISTING_WWV_CSV.exists():
        existing_wwv = pd.read_csv(EXISTING_WWV_CSV, parse_dates=["time"])[
            ["time", "wwv_1e14m3"]
        ]
        wwv = processed[
            ["time", "wwv_5s5n_120e80w_1e14m3"]
        ].merge(existing_wwv, on="time", how="inner")
        wwv_difference = (
            wwv["wwv_5s5n_120e80w_1e14m3"] - wwv["wwv_1e14m3"]
        )
        output.update(
            wwv_comparison_rows=int(len(wwv)),
            wwv_max_abs_difference_1e14m3=float(wwv_difference.abs().max()),
            wwv_correlation=float(
                wwv[["wwv_5s5n_120e80w_1e14m3", "wwv_1e14m3"]]
                .corr()
                .iloc[0, 1]
            ),
        )
    return output


def metric_peak(
    composites: pd.DataFrame,
    event_class: str,
    metric: str,
    mode: str,
) -> tuple[int, float]:
    series = composite_series(composites, event_class, metric)
    values = series["mean"].to_numpy()
    index = int(np.argmax(values) if mode == "max" else np.argmin(values))
    return int(series.iloc[index]["relative_month"]), float(values[index])


def write_report(
    composites: pd.DataFrame,
    phases: pd.DataFrame,
    differences: pd.DataFrame,
    diagnostics: dict[str, object],
) -> None:
    def phase_value(event_class: str, phase: str, metric: str) -> float:
        selected = phases[
            (phases["event_class"] == event_class)
            & (phases["phase"] == phase)
            & (phases["metric"] == metric)
        ]
        return float(selected.iloc[0]["mean"])

    def difference_value(phase: str, metric: str) -> tuple[float, float, float, bool]:
        selected = differences[
            (differences["phase"] == phase)
            & (differences["metric"] == metric)
        ].iloc[0]
        return (
            float(selected["difference"]),
            float(selected["ci_low"]),
            float(selected["ci_high"]),
            bool(selected["ci_excludes_zero"]),
        )

    ct_wwv_month, ct_wwv_peak = metric_peak(composites, "CT", "wwv_sm3", "max")
    cp_wwv_month, cp_wwv_peak = metric_peak(composites, "CP", "wwv_sm3", "max")
    ct_mt_month, ct_mt_min = metric_peak(composites, "CT", "mt5n_q20_sm3", "min")
    ct_development_zonal = phase_value(
        "CT", "development_Jun0_to_Nov0", "zt170_q20_sm3"
    )
    cp_development_zonal = phase_value(
        "CP", "development_Jun0_to_Nov0", "zt170_q20_sm3"
    )
    ct_development_wwv = phase_value(
        "CT", "development_Jun0_to_Nov0", "wwv_sm3"
    )
    cp_development_wwv = phase_value(
        "CP", "development_Jun0_to_Nov0", "wwv_sm3"
    )
    ct_decay_north = phase_value(
        "CT", "mature_decay_Dec0_to_May1", "mt5n_q20_sm3"
    )
    cp_decay_north = phase_value(
        "CP", "mature_decay_Dec0_to_May1", "mt5n_q20_sm3"
    )
    wwv_difference = difference_value(
        "development_Jun0_to_Nov0", "wwv_sm3"
    )
    zonal_difference = difference_value(
        "development_Jun0_to_Nov0", "zt170_q20_sm3"
    )
    north_difference = difference_value(
        "mature_decay_Dec0_to_May1", "mt5n_q20_sm3"
    )
    cp_wwv_members = phases[
        (phases["event_class"] == "CP")
        & (phases["phase"] == "development_Jun0_to_Nov0")
        & (phases["metric"] == "wwv_sm3")
    ].iloc[0]

    text = f"""# Chakravorty et al. (2021) 的 SODA3 基线复现：暖水去哪了

## 第一阶段做了什么

这一步只复现论文 Figure 8 的过程逻辑，不引入 TSI、NMME 或预报比较。使用 SODA3.15.2 月资料（1980–2022），计算：

- 170°E、10°S–5°N，从海表到逐月 D20 的暖水体积输送；东向为正；
- 5°N 和 10°S、140°E–80°W，从海表到逐月 D20 的经向暖水体积输送；向赤道为正、向极为负；
- 5°S–5°N、120°E–80°W 的 WWV；
- 同一截面的 Q20，即 $\\rho c_p u(T-20)^+$ 或 $\\rho c_p v(T-20)^+$，单位 PW，作为“究竟带走多少暖热量”的扩展。

所有序列逐日历月去线性气候态/趋势，再做居中 3 个月滑动平均。标准化图只用于和原论文比较；下排保留 PW 和 $10^{{14}}$ m³ 的物理量。事件严格冻结为论文与 SODA3 重叠的分组：CT={EVENTS['CT']}，CP={EVENTS['CP']}，每组仅 4 个事件。95% 区间按整场事件自助法计算（{diagnostics['bootstrap_samples']:,} 次），没有把相邻月份当成独立样本。

## 复现判断

- CT 合成的 WWV 最大正异常为 {ct_wwv_peak:+.2f} × $10^{{14}}$ m³，出现在相对月份 {ct_wwv_month:+d}；CP 的相应峰值为 {cp_wwv_peak:+.2f} × $10^{{14}}$ m³（相对月份 {cp_wwv_month:+d}）。
- 发展阶段（Jun[0]–Nov[0]）WWV 的 CT/CP 平均异常为 {ct_development_wwv:+.2f}/{cp_development_wwv:+.2f} × $10^{{14}}$ m³；CP 四个事件的阶段均值范围仍为 {cp_wwv_members['min_event']:+.2f} 至 {cp_wwv_members['max_event']:+.2f}。CT−CP 差为 {wwv_difference[0]:+.2f}，95% 事件 bootstrap 区间 [{wwv_difference[1]:+.2f}, {wwv_difference[2]:+.2f}]。
- 同一阶段 170°E Q20 的 CT/CP 平均异常为 {ct_development_zonal:+.2f}/{cp_development_zonal:+.2f} PW；CT−CP 差为 {zonal_difference[0]:+.2f} PW，95% 区间 [{zonal_difference[1]:+.2f}, {zonal_difference[2]:+.2f}]。两组都出现东向输送，不能把它写成 CT 独有。
- 成熟—衰减阶段（Dec[0]–May[+1]），5°N 向赤道为正的 Q20 异常在 CT/CP 中分别为 {ct_decay_north:+.2f}/{cp_decay_north:+.2f} PW；CT−CP 差为 {north_difference[0]:+.2f} PW，95% 区间 [{north_difference[1]:+.2f}, {north_difference[2]:+.2f}]。CT 最强的北侧向极排放为 {ct_mt_min:+.2f} PW（相对月份 {ct_mt_month:+d}）；负号正是“暖量离开赤道带”的方向。

**结论：SODA3 重现了 CT 的“WWV 增长—北侧向极排放”时序，但没有重现“CP 几乎没有 recharge–discharge”的二元结论。** 发展期 WWV 和 170°E Q20 的 CT−CP 区间都跨零；三个关键对比中，只有成熟—衰减期 5°N 北侧排放的组间差异不跨零。因而这一步最稳健的类型差别是“向北排放多少”，不是“有没有暖水充值”。在这 4+4 个重叠事件中，更合适的工作假说是“共同机制、强度和路径分配不同”，而非机制有/无。

这些结果还没有回答真正的新问题——暖热量离开 170°E 之后，在中、东太平洋被储存、向北/向南排放，还是由表面通量和混合耗散。那需要下一步的分箱收支闭合。

## 与原论文一致和不同之处

一致：相同的截面、纬度/经度范围、D20 上积分、输送正号、逐月去季节/趋势、3 个月平滑，以及论文公布的 CT/CP 事件分组。

不同：原论文使用 SODA2.1.6（1958–2008）并以 8+8 个事件合成；这里使用 SODA3.15.2（1980–2022），只能用重叠的 4+4 个事件。因此这是一项“同逻辑、不同 SODA 版本”的可重复性检验，不应称为逐像素复刻。原论文只展示标准化输送；这里新增了 Q20 的 PW 量纲，但明确放在独立一排，避免把新增诊断混入复现。

## QA

- 完整月数：{diagnostics['n_months']}；无缺月、无重复月；
- WWV 与文件夹内已有独立计算比较：n={diagnostics['wwv_comparison_rows']}，r={diagnostics.get('wwv_correlation', float('nan')):.8f}，最大绝对差={diagnostics.get('wwv_max_abs_difference_1e14m3', float('nan')):.2e}（$10^{{14}}$ m³）；
- 170°E、5°S–5°N Q20 与既有暖输送文件比较：n={diagnostics['q20_comparison_rows']}，r={diagnostics.get('q20_170e_5s5n_correlation', float('nan')):.8f}，最大绝对差={diagnostics.get('q20_170e_5s5n_max_abs_difference_pw', float('nan')):.2e} PW；
- 图中两类事件使用同一纵轴；点表示事件自助区间不跨零，不等价于“机制已证明”。

## 下一步入口

下一步不去扫“最佳经度”，而是把热量去向写成固定控制体：西部蓄水库（160°E–180°E）、中太平洋通道（180°E–140°W）、东太平洋受热区（140°W–80°W），分别计算 $dH_{{20}}/dt$、东西边界 Q20、5°N/10°S 经向 Q20、表面热通量和剩余项。这样才能把“170°E 有输送”升级为“哪部分到了东部，哪部分从南北边界离开，哪部分留在海洋里”。

参考：[Chakravorty et al. (2021), JGR Oceans, doi:10.1029/2020JC017075](https://doi.org/10.1029/2020JC017075)
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(args.input)
    raw = pd.read_csv(args.input, parse_dates=["time"])
    processed, standard_deviations = process_monthly(raw)
    aligned = event_aligned_table(processed)
    composites = bootstrap_composites(processed, args.bootstrap_samples)
    phases = phase_summary(processed)
    differences = phase_difference_bootstrap(processed, args.bootstrap_samples)

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    processed.to_csv(PROCESSED_CSV, index=False, float_format="%.9g")
    aligned.to_csv(EVENT_ALIGNED_CSV, index=False, float_format="%.9g")
    composites.to_csv(COMPOSITE_CSV, index=False, float_format="%.9g")
    phases.to_csv(PHASE_CSV, index=False, float_format="%.9g")
    differences.to_csv(DIFFERENCE_CSV, index=False, float_format="%.9g")
    plot_figure(composites)

    validation = validate_against_existing(processed)
    diagnostics: dict[str, object] = {
        "source": str(args.input),
        "baseline": list(BASELINE),
        "n_months": int(len(processed)),
        "events": {key: list(value) for key, value in EVENTS.items()},
        "bootstrap_samples": int(args.bootstrap_samples),
        "random_seed": RANDOM_SEED,
        "standard_deviations": standard_deviations,
        **validation,
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_report(composites, phases, differences, diagnostics)
    print(f"Wrote {PROCESSED_CSV}", flush=True)
    print(f"Wrote {EVENT_ALIGNED_CSV}", flush=True)
    print(f"Wrote {COMPOSITE_CSV}", flush=True)
    print(f"Wrote {PHASE_CSV}", flush=True)
    print(f"Wrote {DIFFERENCE_CSV}", flush=True)
    print(f"Wrote {FIGURE_PNG}", flush=True)
    print(f"Wrote {FIGURE_PDF}", flush=True)
    print(f"Wrote {SUMMARY_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
