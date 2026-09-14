#!/usr/bin/env python3
"""Test a five-day SODA3 OHC-to-wind-stress transition across 13 warm events.

The analysis is deliberately event-level.  Pentads are used to locate the
spring ocean maximum and early-summer stress maximum, but they are not treated
as independent samples.  A continuous segmented regression is compared with a
linear model using nested leave-one-event-out validation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_soda3_5day_transition_plot_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT
    / "data/interim/research_2026/soda3_5day_ohc/"
    "soda3_5day_ohc_13events_1982_2023_jan_jun.csv"
)
MONTHLY_REFERENCE = ROOT / "data/derived/research_2026/soda3_ohc_indices_1980_2024.csv"
EVENT_CONTEXT = ROOT / "data/derived/research_2026/soda3_ohc_coupling_minimal_event_table.csv"
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_ohc_transition_13events"

EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
SUMMARY_CSV = DERIVED / "soda3_5day_ohc_transition_event_summary.csv"
LOEO_CSV = DERIVED / "soda3_5day_ohc_transition_loeo_predictions.csv"
STABILITY_CSV = DERIVED / "soda3_5day_ohc_transition_breakpoint_stability.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_5day_ohc_transition_diagnostics.json"
FIG_MAIN_PNG = OUT / "soda3_5day_ohc_transition_13events.png"
FIG_MAIN_PDF = OUT / "soda3_5day_ohc_transition_13events.pdf"
FIG_STABILITY_PNG = OUT / "soda3_5day_ohc_transition_stability.png"
FIG_STABILITY_PDF = OUT / "soda3_5day_ohc_transition_stability.pdf"
REPORT_MD = OUT / "SODA3_5DAY_OHC_TRANSITION_RESULT_CN.md"

RNG_SEED = 20260802
N_BOOTSTRAP = 3000
N_PERMUTATION = 50000


def load_and_validate() -> pd.DataFrame:
    frame = pd.read_csv(INPUT, parse_dates=["time"])
    required = {
        "time",
        "year",
        "month",
        "ohc300_central_anom_gj_m2",
        "ohc300_central_anom_15day_gj_m2",
        "taux_central_180_220e_nm2",
        "taux_central_15day_nm2",
        "valid_column_fraction",
    }
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"Missing columns: {sorted(missing)}")
    if set(frame["year"].unique()) != set(EVENT_YEARS):
        raise ValueError(f"Unexpected event years: {sorted(frame['year'].unique())}")
    if frame.duplicated(["year", "time"]).any():
        raise ValueError("Duplicate event timestamps")
    counts = frame.groupby("year")["time"].nunique()
    if not counts.between(35, 37).all():
        raise ValueError(f"Expected 35-37 pentads per year, found {counts.to_dict()}")
    if frame[list(required - {"time"})].isna().any().any():
        raise ValueError("Missing values in required five-day fields")
    if not frame["valid_column_fraction"].between(0.99, 1.0).all():
        raise ValueError("Unexpected missing central-Pacific water columns")
    for year, group in frame.groupby("year"):
        ordered = group.sort_values("time")
        gaps = ordered["time"].diff().dropna().dt.days
        if not gaps.between(4, 6).all():
            raise ValueError(f"Unexpected time gap for {year}: {gaps.tolist()}")
        if set(ordered["month"].unique()) != {1, 2, 3, 4, 5, 6}:
            raise ValueError(f"Incomplete Jan-Jun coverage for {year}")

    monthly = pd.read_csv(MONTHLY_REFERENCE)
    target = monthly.loc[
        monthly["year"].isin(EVENT_YEARS) & monthly["month"].between(1, 6),
        ["year", "month", "ohc300_central_anom_jm2"],
    ].copy()
    target["target_gj_m2"] = target["ohc300_central_anom_jm2"] / 1.0e9
    aggregated = (
        frame.groupby(["year", "month"], as_index=False)["ohc300_central_anom_gj_m2"]
        .mean()
        .rename(columns={"ohc300_central_anom_gj_m2": "five_day_mean_gj_m2"})
    )
    check = aggregated.merge(target, on=["year", "month"], validate="one_to_one")
    max_error = float(np.abs(check["five_day_mean_gj_m2"] - check["target_gj_m2"]).max())
    if max_error > 1.0e-8:
        raise ValueError(f"Monthly alignment error is {max_error}")
    frame.attrs["monthly_alignment_max_error_gj_m2"] = max_error
    return frame.sort_values(["year", "time"]).reset_index(drop=True)


def first_two_pentad_westerly(group: pd.DataFrame) -> pd.Timestamp | None:
    current = group.loc[group["month"].isin([5, 6])].sort_values("time")
    values = current["taux_central_180_220e_nm2"].to_numpy(dtype=float)
    for index in range(len(values) - 1):
        if values[index] > 0.0 and values[index + 1] > 0.0:
            return pd.Timestamp(current.iloc[index]["time"])
    return None


def summarize_events(frame: pd.DataFrame) -> pd.DataFrame:
    context = pd.read_csv(EVENT_CONTEXT)[
        [
            "year",
            "group",
            "mar_apr_fep_residual_c",
            "mature_djf_type_index_c",
            "positive_spring_fep_residual",
        ]
    ]
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby("year", sort=True):
        spring = group.loc[group["month"].isin([3, 4])]
        may_june = group.loc[group["month"].isin([5, 6])]
        ohc_peak = spring.loc[spring["ohc300_central_anom_15day_gj_m2"].idxmax()]
        stress_peak = may_june.loc[may_june["taux_central_15day_nm2"].idxmax()]
        onset = first_two_pentad_westerly(group)
        rows.append(
            {
                "year": int(year),
                "spring_ohc_peak_date": pd.Timestamp(ohc_peak["time"]).date().isoformat(),
                "spring_ohc_peak_gj_m2": float(ohc_peak["ohc300_central_anom_15day_gj_m2"]),
                "spring_ohc_positive_pentad_fraction": float(
                    (spring["ohc300_central_anom_15day_gj_m2"] > 0.0).mean()
                ),
                "may_jun_stress_max_date": pd.Timestamp(stress_peak["time"]).date().isoformat(),
                "may_jun_stress_max_nm2": float(stress_peak["taux_central_15day_nm2"]),
                "days_stress_max_after_ohc_peak": int(
                    (pd.Timestamp(stress_peak["time"]) - pd.Timestamp(ohc_peak["time"])).days
                ),
                "first_two_pentad_westerly_date": (
                    None if onset is None else onset.date().isoformat()
                ),
                "actual_westerly_stress_established_may_jun": onset is not None,
            }
        )
    return pd.DataFrame(rows).merge(context, on="year", validate="one_to_one")


def ols_fit(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(np.column_stack([np.ones(len(x)), x]), y, rcond=None)[0]


def ols_predict(coef: np.ndarray, x: np.ndarray) -> np.ndarray:
    return coef[0] + coef[1] * x


def hinge_design(x: np.ndarray, breakpoint: float) -> np.ndarray:
    return np.column_stack([np.ones(len(x)), x, np.maximum(0.0, x - breakpoint)])


def hinge_fit(x: np.ndarray, y: np.ndarray, breakpoint: float) -> np.ndarray:
    return np.linalg.lstsq(hinge_design(x, breakpoint), y, rcond=None)[0]


def hinge_predict(coef: np.ndarray, x: np.ndarray, breakpoint: float) -> np.ndarray:
    return hinge_design(x, breakpoint) @ coef


def breakpoint_candidates(x: np.ndarray, minimum_side: int = 3) -> np.ndarray:
    values = np.sort(np.unique(x))
    if len(values) < 2 * minimum_side + 1:
        return np.array([], dtype=float)
    mids = 0.5 * (values[:-1] + values[1:])
    output = [
        item
        for item in mids
        if np.sum(x <= item) >= minimum_side and np.sum(x > item) >= minimum_side
    ]
    return np.asarray(output, dtype=float)


def fixed_breakpoint_loeo_rmse(x: np.ndarray, y: np.ndarray, breakpoint: float) -> float:
    predictions = np.empty(len(x), dtype=float)
    for index in range(len(x)):
        keep = np.arange(len(x)) != index
        coef = hinge_fit(x[keep], y[keep], breakpoint)
        predictions[index] = hinge_predict(coef, x[index : index + 1], breakpoint)[0]
    return float(np.sqrt(np.mean((predictions - y) ** 2)))


def choose_breakpoint(x: np.ndarray, y: np.ndarray) -> float:
    candidates = breakpoint_candidates(x)
    if not len(candidates):
        raise ValueError("Too few unique values for a segmented model")
    scores = np.asarray([fixed_breakpoint_loeo_rmse(x, y, item) for item in candidates])
    return float(candidates[int(np.argmin(scores))])


def loeo_models(x: np.ndarray, y: np.ndarray, years: np.ndarray) -> tuple[pd.DataFrame, float]:
    rows = []
    outer_breakpoints = []
    for index, year in enumerate(years):
        keep = np.arange(len(x)) != index
        linear_coef = ols_fit(x[keep], y[keep])
        breakpoint = choose_breakpoint(x[keep], y[keep])
        piece_coef = hinge_fit(x[keep], y[keep], breakpoint)
        outer_breakpoints.append(breakpoint)
        rows.append(
            {
                "year": int(year),
                "observed_stress_max_nm2": float(y[index]),
                "linear_prediction_nm2": float(ols_predict(linear_coef, x[index : index + 1])[0]),
                "segmented_prediction_nm2": float(
                    hinge_predict(piece_coef, x[index : index + 1], breakpoint)[0]
                ),
                "training_mean_prediction_nm2": float(np.mean(y[keep])),
                "training_breakpoint_gj_m2": breakpoint,
            }
        )
    full_breakpoint = choose_breakpoint(x, y)
    return pd.DataFrame(rows), full_breakpoint


def permutation_pvalue(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> float:
    observed = abs(float(np.corrcoef(x, y)[0, 1]))
    exceed = 0
    for _ in range(N_PERMUTATION):
        shuffled = rng.permutation(y)
        exceed += abs(float(np.corrcoef(x, shuffled)[0, 1])) >= observed
    return float((exceed + 1) / (N_PERMUTATION + 1))


def bootstrap_statistics(
    x: np.ndarray,
    y: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    correlations: list[float] = []
    slopes: list[float] = []
    breakpoints: list[float] = []
    for _ in range(N_BOOTSTRAP):
        indices = rng.integers(0, len(x), len(x))
        xb = x[indices]
        yb = y[indices]
        if np.std(xb) <= 1.0e-12 or np.std(yb) <= 1.0e-12:
            continue
        correlations.append(float(np.corrcoef(xb, yb)[0, 1]))
        slopes.append(float(ols_fit(xb, yb)[1]))
        if len(np.unique(xb)) >= 7:
            try:
                breakpoints.append(choose_breakpoint(xb, yb))
            except ValueError:
                pass
    return np.asarray(correlations), np.asarray(slopes), np.asarray(breakpoints)


def model_diagnostics(summary: pd.DataFrame) -> tuple[dict[str, object], pd.DataFrame, np.ndarray]:
    x = summary["spring_ohc_peak_gj_m2"].to_numpy(dtype=float)
    y = summary["may_jun_stress_max_nm2"].to_numpy(dtype=float)
    years = summary["year"].to_numpy(dtype=int)
    rng = np.random.default_rng(RNG_SEED)
    pearson = stats.pearsonr(x, y)
    spearman = stats.spearmanr(x, y)
    permutation_p = permutation_pvalue(x, y, rng)
    boot_r, boot_slope, boot_breakpoints = bootstrap_statistics(x, y, rng)
    loeo, breakpoint = loeo_models(x, y, years)

    linear_coef = ols_fit(x, y)
    piece_coef = hinge_fit(x, y, breakpoint)
    linear_fit = ols_predict(linear_coef, x)
    piece_fit = hinge_predict(piece_coef, x, breakpoint)
    sse_linear = float(np.sum((y - linear_fit) ** 2))
    sse_piece = float(np.sum((y - piece_fit) ** 2))
    n = len(y)
    bic_linear = float(n * np.log(sse_linear / n) + 2 * np.log(n))
    bic_piece = float(n * np.log(sse_piece / n) + 4 * np.log(n))

    observed = loeo["observed_stress_max_nm2"].to_numpy(dtype=float)
    pred_linear = loeo["linear_prediction_nm2"].to_numpy(dtype=float)
    pred_piece = loeo["segmented_prediction_nm2"].to_numpy(dtype=float)
    pred_mean = loeo["training_mean_prediction_nm2"].to_numpy(dtype=float)
    rmse_linear = float(np.sqrt(np.mean((observed - pred_linear) ** 2)))
    rmse_piece = float(np.sqrt(np.mean((observed - pred_piece) ** 2)))
    rmse_mean = float(np.sqrt(np.mean((observed - pred_mean) ** 2)))
    improvement = float(100.0 * (rmse_linear - rmse_piece) / rmse_linear)

    outer_breakpoints = loeo["training_breakpoint_gj_m2"].to_numpy(dtype=float)
    bp_ci = np.quantile(boot_breakpoints, [0.05, 0.5, 0.95])
    x_range = float(np.ptp(x))
    stability = {
        "loeo_rmse_improvement_ge_10pct": improvement >= 10.0,
        "loeo_breakpoint_range_le_one_third_xrange": float(np.ptp(outer_breakpoints)) <= x_range / 3.0,
        "bootstrap_90pct_width_le_one_third_xrange": float(bp_ci[2] - bp_ci[0]) <= x_range / 3.0,
        "bic_improvement_ge_2": bic_linear - bic_piece >= 2.0,
    }
    accepted = all(stability.values())

    loeo_correlations = []
    for index in range(n):
        keep = np.arange(n) != index
        loeo_correlations.append(float(np.corrcoef(x[keep], y[keep])[0, 1]))
    without_1997 = years != 1997
    diagnostics: dict[str, object] = {
        "n_events": n,
        "n_events_with_two_pentad_actual_westerly": int(
            summary["actual_westerly_stress_established_may_jun"].sum()
        ),
        "events_with_two_pentad_actual_westerly": summary.loc[
            summary["actual_westerly_stress_established_may_jun"], "year"
        ].astype(int).tolist(),
        "primary_predictor": "Mar-Apr maximum 15-day 0-300 m OHC anomaly",
        "primary_outcome": "May-Jun maximum 15-day actual zonal wind stress",
        "pearson_r": float(pearson.statistic),
        "pearson_parametric_p": float(pearson.pvalue),
        "pearson_permutation_p": permutation_p,
        "pearson_bootstrap_95pct_ci": np.quantile(boot_r, [0.025, 0.975]).tolist(),
        "spearman_rho": float(spearman.statistic),
        "spearman_p": float(spearman.pvalue),
        "linear_slope_nm2_per_gj_m2": float(linear_coef[1]),
        "linear_slope_bootstrap_95pct_ci": np.quantile(boot_slope, [0.025, 0.975]).tolist(),
        "pearson_without_1997": float(np.corrcoef(x[without_1997], y[without_1997])[0, 1]),
        "pearson_loeo_range": [float(np.min(loeo_correlations)), float(np.max(loeo_correlations))],
        "candidate_breakpoint_gj_m2": breakpoint,
        "breakpoint_bootstrap_90pct_ci_gj_m2": bp_ci.tolist(),
        "breakpoint_loeo_range_gj_m2": [float(np.min(outer_breakpoints)), float(np.max(outer_breakpoints))],
        "linear_bic": bic_linear,
        "segmented_bic": bic_piece,
        "bic_linear_minus_segmented": bic_linear - bic_piece,
        "linear_loeo_rmse_nm2": rmse_linear,
        "segmented_nested_loeo_rmse_nm2": rmse_piece,
        "training_mean_loeo_rmse_nm2": rmse_mean,
        "segmented_rmse_improvement_percent": improvement,
        "linear_loeo_skill_vs_training_mean": 1.0 - (rmse_linear / rmse_mean) ** 2,
        "segmented_loeo_skill_vs_training_mean": 1.0 - (rmse_piece / rmse_mean) ** 2,
        "segmented_low_ohc_slope_nm2_per_gj_m2": float(piece_coef[1]),
        "segmented_high_ohc_slope_nm2_per_gj_m2": float(piece_coef[1] + piece_coef[2]),
        "threshold_stability_tests": stability,
        "stable_numerical_threshold_accepted": accepted,
        "bootstrap_replicates_used": int(len(boot_breakpoints)),
        "interpretation": (
            "stable numerical threshold" if accepted else "continuous ocean checkpoint; numerical breakpoint is not stable"
        ),
    }
    return diagnostics, loeo, boot_breakpoints


def calendar_day(month: int, day: int) -> int:
    return int(pd.Timestamp(2001, int(month), int(day)).dayofyear)


def interpolate_event_matrix(frame: pd.DataFrame, column: str) -> np.ndarray:
    days = np.arange(1, 182, dtype=float)
    rows = []
    for year in EVENT_YEARS:
        group = frame.loc[frame["year"].eq(year)].sort_values("time")
        x = np.asarray([calendar_day(row.month, row.day) for row in group.itertuples()], dtype=float)
        values = group[column].to_numpy(dtype=float)
        rows.append(np.interp(days, x, values, left=np.nan, right=np.nan))
    return np.asarray(rows)


def type_color(group: str) -> str:
    if group == "classic EP":
        return "#c43c39"
    if group == "CP":
        return "#2878b5"
    if "2023" in group:
        return "#e69f00"
    return "#777777"


def plot_main(frame: pd.DataFrame, summary: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.2,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    ohc = interpolate_event_matrix(frame, "ohc300_central_anom_15day_gj_m2")
    stress = interpolate_event_matrix(frame, "taux_central_15day_nm2")
    x = summary["spring_ohc_peak_gj_m2"].to_numpy(dtype=float)
    y = summary["may_jun_stress_max_nm2"].to_numpy(dtype=float)
    breakpoint = float(diagnostics["candidate_breakpoint_gj_m2"])
    linear_coef = ols_fit(x, y)
    piece_coef = hinge_fit(x, y, breakpoint)

    fig = plt.figure(figsize=(13.0, 8.0))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.12, 1.0], hspace=0.33, wspace=0.34)
    ax_ohc = fig.add_subplot(grid[0, 0])
    ax_stress = fig.add_subplot(grid[1, 0])
    ax_scatter = fig.add_subplot(grid[:, 1])

    ohc_limit = max(1.0, float(np.ceil(np.nanmax(np.abs(ohc)) * 4.0) / 4.0))
    stress_limit = max(0.04, float(np.ceil(np.nanmax(np.abs(stress)) * 100.0) / 100.0))
    extent = [1, 181, len(EVENT_YEARS) - 0.5, -0.5]
    image_ohc = ax_ohc.imshow(
        np.ma.masked_invalid(ohc), aspect="auto", extent=extent, cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-ohc_limit, vcenter=0.0, vmax=ohc_limit), interpolation="nearest"
    )
    image_stress = ax_stress.imshow(
        np.ma.masked_invalid(stress), aspect="auto", extent=extent, cmap="BrBG",
        norm=TwoSlopeNorm(vmin=-stress_limit, vcenter=0.0, vmax=stress_limit), interpolation="nearest"
    )
    month_starts = [1, 32, 60, 91, 121, 152]
    for axis in (ax_ohc, ax_stress):
        axis.set_xticks(month_starts, ["Jan", "Feb", "Mar", "Apr", "May", "Jun"])
        axis.set_yticks(np.arange(len(EVENT_YEARS)), [str(item) for item in EVENT_YEARS])
        axis.axvline(60, color="black", lw=0.8, ls="--", alpha=0.7)
        axis.axvline(121, color="black", lw=0.8, ls="--", alpha=0.7)
        axis.set_ylabel("Development year")
    ax_ohc.set_title("(a) 0–300 m OHC anomaly (15-day mean)", loc="left", fontweight="bold")
    ax_stress.set_title("(b) Actual zonal wind stress (15-day mean)", loc="left", fontweight="bold")
    ax_stress.set_xlabel("Calendar date")
    cb_ohc = fig.colorbar(image_ohc, ax=ax_ohc, fraction=0.032, pad=0.018)
    cb_ohc.ax.set_title("GJ m$^{-2}$", fontsize=8.0, pad=4)
    cb_stress = fig.colorbar(image_stress, ax=ax_stress, fraction=0.032, pad=0.018)
    cb_stress.ax.set_title("N m$^{-2}$", fontsize=8.0, pad=4)

    label_offsets = {
        1982: (5, 6), 1986: (-25, -9), 1991: (5, 7), 1994: (-26, 5),
        1997: (5, 4), 2002: (5, 4), 2004: (-33, 3), 2006: (-29, -13),
        2009: (5, 5), 2015: (5, 4), 2018: (5, -9), 2019: (5, 8),
        2023: (8, -13),
    }
    for row in summary.itertuples():
        color = type_color(row.group)
        marker = "o" if row.actual_westerly_stress_established_may_jun else "X"
        ax_scatter.scatter(
            row.spring_ohc_peak_gj_m2,
            row.may_jun_stress_max_nm2,
            s=72,
            marker=marker,
            color=color,
            edgecolor="white",
            linewidth=0.7,
            zorder=5,
        )
        weight = "bold" if row.positive_spring_fep_residual else "normal"
        ax_scatter.annotate(
            str(row.year),
            (row.spring_ohc_peak_gj_m2, row.may_jun_stress_max_nm2),
            xytext=label_offsets[row.year],
            textcoords="offset points",
            fontsize=8.2,
            fontweight=weight,
            color=color,
        )
    x_grid = np.linspace(float(x.min()) - 0.05, float(x.max()) + 0.05, 300)
    ax_scatter.plot(x_grid, ols_predict(linear_coef, x_grid), color="black", lw=1.8, label="Linear")
    ax_scatter.plot(
        x_grid,
        hinge_predict(piece_coef, x_grid, breakpoint),
        color="#7b3294",
        lw=1.7,
        ls="--",
        label="Segmented candidate",
    )
    bp_ci = diagnostics["breakpoint_bootstrap_90pct_ci_gj_m2"]
    ax_scatter.axvspan(float(bp_ci[0]), float(bp_ci[2]), color="#7b3294", alpha=0.10, lw=0)
    ax_scatter.axvline(breakpoint, color="#7b3294", lw=1.0, ls=":")
    ax_scatter.axhline(0.0, color="0.45", lw=0.8)
    ax_scatter.grid(color="0.90", lw=0.7)
    ax_scatter.set_xlabel("Mar–Apr maximum 15-day OHC anomaly (GJ m$^{-2}$)")
    ax_scatter.set_ylabel("May–Jun maximum 15-day zonal stress (N m$^{-2}$)")
    ax_scatter.set_title("(c) Event-level ocean checkpoint test", loc="left", fontweight="bold")
    ax_scatter.text(
        0.03,
        0.97,
        (
            f"Pearson r = {diagnostics['pearson_r']:.2f} "
            f"(permutation p = {diagnostics['pearson_permutation_p']:.3f})\n"
            f"LOEO RMSE: linear {diagnostics['linear_loeo_rmse_nm2']:.3f}, "
            f"segmented {diagnostics['segmented_nested_loeo_rmse_nm2']:.3f} N m$^{{-2}}$\n"
            f"candidate breakpoint {breakpoint:+.2f} GJ m$^{{-2}}$; "
            f"stable threshold: {'yes' if diagnostics['stable_numerical_threshold_accepted'] else 'no'}"
        ),
        transform=ax_scatter.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "0.8", "alpha": 0.92},
    )

    type_handles = [
        Line2D([], [], marker="o", ls="", color=type_color("classic EP"), label="classic EP"),
        Line2D([], [], marker="o", ls="", color=type_color("CP"), label="CP"),
        Line2D([], [], marker="o", ls="", color=type_color("other warm"), label="other warm"),
        Line2D([], [], marker="o", ls="", color=type_color("2023 weak-coupling EP"), label="2023 weak-coupling EP"),
        Line2D([], [], marker="o", ls="", color="black", markerfacecolor="white", label="2-pentad westerly"),
        Line2D([], [], marker="X", ls="", color="black", label="no 2-pentad westerly"),
    ]
    model_handles, model_labels = ax_scatter.get_legend_handles_labels()
    ax_scatter.legend(
        type_handles + model_handles,
        [item.get_label() for item in type_handles] + model_labels,
        loc="lower right",
        frameon=False,
        fontsize=8.0,
        ncol=2,
    )

    fig.suptitle(
        "SODA3 five-day transition test: spring central-Pacific heat and early-summer stress",
        fontsize=14.2,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.012,
        (
            "SODA3.15.2; 5°S–5°N, 180°–140°W. OHC: 0–300 m, detrended 1980–2024 monthly baseline. "
            "Bold year labels denote positive spring FEP residual. Pentads locate event metrics; n = 13 independent events."
        ),
        ha="center",
        va="bottom",
        fontsize=7.6,
        color="0.35",
    )
    fig.savefig(FIG_MAIN_PNG, dpi=320, bbox_inches="tight")
    fig.savefig(FIG_MAIN_PDF, bbox_inches="tight")
    plt.close(fig)


def plot_stability(
    loeo: pd.DataFrame,
    breakpoints: np.ndarray,
    diagnostics: dict[str, object],
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2))
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.18, top=0.82, wspace=0.28)
    axis = axes[0]
    axis.hist(breakpoints, bins=24, color="#9e77b7", alpha=0.70, edgecolor="white", density=True)
    y_top = axis.get_ylim()[1]
    outer = loeo["training_breakpoint_gj_m2"].to_numpy(dtype=float)
    axis.scatter(outer, np.full(len(outer), 0.03 * y_top), marker="|", s=150, color="black")
    axis.axvline(float(diagnostics["candidate_breakpoint_gj_m2"]), color="#7b3294", lw=1.5, ls="--")
    ci = diagnostics["breakpoint_bootstrap_90pct_ci_gj_m2"]
    axis.axvspan(float(ci[0]), float(ci[2]), color="#7b3294", alpha=0.10)
    axis.set_xlabel("Candidate OHC breakpoint (GJ m$^{-2}$)")
    axis.set_ylabel("Bootstrap density")
    axis.set_title("(a) Breakpoint stability", loc="left", fontweight="bold")
    axis.grid(axis="y", color="0.90", lw=0.7)

    axis = axes[1]
    observed = loeo["observed_stress_max_nm2"].to_numpy(dtype=float)
    linear = loeo["linear_prediction_nm2"].to_numpy(dtype=float)
    piece = loeo["segmented_prediction_nm2"].to_numpy(dtype=float)
    limits = [float(min(observed.min(), linear.min(), piece.min())) - 0.01, float(max(observed.max(), linear.max(), piece.max())) + 0.01]
    axis.plot(limits, limits, color="0.45", lw=1.0, ls=":")
    axis.scatter(observed, linear, s=45, color="black", label="Linear LOEO")
    axis.scatter(observed, piece, s=50, facecolors="none", edgecolors="#7b3294", linewidth=1.4, label="Nested segmented LOEO")
    stability_offsets = {1997: (4, 4), 2015: (4, 4), 2023: (-4, -14)}
    for row in loeo.itertuples():
        if row.year in {1997, 2015, 2023}:
            axis.annotate(str(row.year), (row.observed_stress_max_nm2, row.segmented_prediction_nm2), xytext=stability_offsets[row.year], textcoords="offset points", fontsize=8.0, color="#7b3294")
    axis.set_xlim(limits)
    axis.set_ylim(limits)
    axis.set_xlabel("Observed May–Jun stress maximum (N m$^{-2}$)")
    axis.set_ylabel("LOEO prediction (N m$^{-2}$)")
    axis.set_title("(b) Out-of-event prediction", loc="left", fontweight="bold")
    axis.grid(color="0.90", lw=0.7)
    axis.legend(frameon=False, fontsize=8.3)

    fig.suptitle("SODA3 OHC transition test: numerical-threshold robustness", fontsize=13.0, fontweight="bold")
    fig.savefig(FIG_STABILITY_PNG, dpi=320, bbox_inches="tight")
    fig.savefig(FIG_STABILITY_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(summary: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    rows = []
    for row in summary.itertuples():
        onset = row.first_two_pentad_westerly_date if pd.notna(row.first_two_pentad_westerly_date) else "未出现"
        rows.append(
            f"| {row.year} | {row.group} | {row.spring_ohc_peak_gj_m2:+.2f} | "
            f"{row.may_jun_stress_max_nm2:+.3f} | {onset} |"
        )
    accepted = bool(diagnostics["stable_numerical_threshold_accepted"])
    conclusion = (
        "分段阈值通过了预设的全部稳定性检验，可以暂时作为经验转变点，但仍不能解释为因果阈值。"
        if accepted
        else "分段阈值未通过预设稳定性检验，因此不报告普适数值阈值；更稳妥的表述是春季中太平洋OHC构成一个连续的海洋检查点。"
    )
    report = f"""# SODA3五日OHC—风应力转变检验：13个暖事件

## 预注册式设定

- 海洋指标：3—4月最大15日平均0—300米OHC距平，5°S—5°N、180°—140°W。
- 大气指标：5—6月最大15日平均实际纬向风应力，同一区域；正值为实际西风应力。
- 独立样本是13个事件，不把五日时次当作独立样本。
- 比较普通线性模型与连续分段线性模型；分段模型的转折点在每个训练样本中重新选择，使用嵌套留一事件验证。

## 事件结果

| 年份 | 成熟期类型 | 春季OHC峰值（GJ m⁻²） | 初夏风应力最大值（N m⁻²） | 连续两个候实际西风起始 |
|---:|---|---:|---:|---|
{chr(10).join(rows)}

## 核心统计

- Pearson相关：r = {diagnostics['pearson_r']:.3f}；参数p = {diagnostics['pearson_parametric_p']:.4f}；事件置换p = {diagnostics['pearson_permutation_p']:.4f}。
- Spearman相关：ρ = {diagnostics['spearman_rho']:.3f}，p = {diagnostics['spearman_p']:.4f}。
- Pearson bootstrap 95%区间：{diagnostics['pearson_bootstrap_95pct_ci'][0]:.3f}至{diagnostics['pearson_bootstrap_95pct_ci'][1]:.3f}。
- 删除1997年后相关：r = {diagnostics['pearson_without_1997']:.3f}；逐事件删除后的相关范围为{diagnostics['pearson_loeo_range'][0]:.3f}至{diagnostics['pearson_loeo_range'][1]:.3f}。
- 线性模型LOEO RMSE：{diagnostics['linear_loeo_rmse_nm2']:.4f} N m⁻²。
- 嵌套分段模型LOEO RMSE：{diagnostics['segmented_nested_loeo_rmse_nm2']:.4f} N m⁻²，相对线性模型改善{diagnostics['segmented_rmse_improvement_percent']:.1f}% 。
- 最优候选转折点：{diagnostics['candidate_breakpoint_gj_m2']:+.3f} GJ m⁻²；bootstrap 90%区间为{diagnostics['breakpoint_bootstrap_90pct_ci_gj_m2'][0]:+.3f}至{diagnostics['breakpoint_bootstrap_90pct_ci_gj_m2'][2]:+.3f} GJ m⁻²。

## 判断

{conclusion}

只有1997年在5—6月出现了连续两个候的实际西风应力。2015年虽然春季OHC峰值达到{summary.loc[summary['year'].eq(2015), 'spring_ohc_peak_gj_m2'].iloc[0]:+.2f} GJ m⁻²，风应力仍未转正；删除1997年后相关降至r = {diagnostics['pearson_without_1997']:.3f}。这说明OHC可以描述海洋为耦合准备到什么程度，但仅凭OHC还不能可靠预测大气一定会接上。当前样本也不足以对“是否出现实际西风”拟合二元阈值，因为13个事件中只有一个正例。

这项检验回答的是“春季海洋热状态能否区分随后风应力接上的强弱”，不是证明OHC直接造成西风。SODA3中的风应力是再分析系统采用的大气强迫场，并非独立于海洋分析的观测，因此任何稳定关系最终仍需用TAO等独立资料核对关键事件的日期。
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    frame = load_and_validate()
    summary = summarize_events(frame)
    diagnostics, loeo, breakpoints = model_diagnostics(summary)
    diagnostics["data_source"] = "SODA3.15.2 five-day reanalysis"
    diagnostics["domain"] = "5S-5N, 180-140W; 0-300 m"
    diagnostics["monthly_alignment_max_error_gj_m2"] = frame.attrs[
        "monthly_alignment_max_error_gj_m2"
    ]
    diagnostics["stress_independence_caveat"] = (
        "SODA3 zonal wind stress is an atmospheric forcing field, not an independent response observation."
    )

    summary.to_csv(SUMMARY_CSV, index=False)
    loeo.to_csv(LOEO_CSV, index=False)
    pd.DataFrame({"bootstrap_breakpoint_gj_m2": breakpoints}).to_csv(STABILITY_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_main(frame, summary, diagnostics)
    plot_stability(loeo, breakpoints, diagnostics)
    write_report(summary, diagnostics)
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    for path in (SUMMARY_CSV, LOEO_CSV, STABILITY_CSV, DIAGNOSTICS_JSON, FIG_MAIN_PNG, FIG_MAIN_PDF, FIG_STABILITY_PNG, FIG_STABILITY_PDF, REPORT_MD):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
