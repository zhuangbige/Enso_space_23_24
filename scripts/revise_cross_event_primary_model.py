#!/usr/bin/env python3
"""Re-express the cross-event analysis as one primary multiple regression."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/enso_stat_revision/mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


EVENTS_CSV = Path(
    "/Users/daiyue/Documents/Maryland/data/derived/research_2026/"
    "enso_report_unified_1982_2024/"
    "enso_3d_warm_heat_spreading_event_metrics_1982_2024.csv"
)
OUT_DIR = Path("/private/tmp/enso_stat_revision")
FIGURE_PNG = OUT_DIR / "figure8_primary_model.png"
FIGURE_PDF = OUT_DIR / "figure8_primary_model.pdf"
STATS_JSON = OUT_DIR / "primary_model_statistics.json"
POINTS_CSV = OUT_DIR / "primary_model_partial_regression_points.csv"
SEED = 20260818
N_PERMUTATIONS = 100_000


def residualize(values: np.ndarray, control: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(values)), control])
    return values - design @ np.linalg.lstsq(design, values, rcond=None)[0]


def partial_correlation(
    predictor: np.ndarray, response: np.ndarray, control: np.ndarray
) -> float:
    x_residual = residualize(predictor, control)
    y_residual = residualize(response, control)
    return float(np.corrcoef(x_residual, y_residual)[0, 1])


def fisher_partial_r_ci(r_value: float, n: int, n_controls: int) -> tuple[float, float]:
    standard_error = 1.0 / np.sqrt(n - n_controls - 3)
    z_value = np.arctanh(r_value)
    z_critical = stats.norm.ppf(0.975)
    low, high = np.tanh(
        [z_value - z_critical * standard_error, z_value + z_critical * standard_error]
    )
    return float(low), float(high)


def fit_primary_model(
    response: np.ndarray, total_ohc: np.ndarray, contrast: np.ndarray
) -> dict[str, float]:
    design = np.column_stack([np.ones(len(response)), total_ohc, contrast])
    coefficients = np.linalg.lstsq(design, response, rcond=None)[0]
    fitted = design @ coefficients
    residuals = response - fitted
    degrees_of_freedom = len(response) - design.shape[1]
    residual_variance = float(residuals @ residuals / degrees_of_freedom)
    covariance = residual_variance * np.linalg.inv(design.T @ design)
    standard_errors = np.sqrt(np.diag(covariance))
    t_statistics = coefficients / standard_errors
    p_values = 2.0 * stats.t.sf(np.abs(t_statistics), degrees_of_freedom)
    t_critical = stats.t.ppf(0.975, degrees_of_freedom)
    confidence_low = coefficients - t_critical * standard_errors
    confidence_high = coefficients + t_critical * standard_errors
    return {
        "intercept": float(coefficients[0]),
        "beta_total": float(coefficients[1]),
        "beta_contrast": float(coefficients[2]),
        "se_beta_contrast": float(standard_errors[2]),
        "t_beta_contrast": float(t_statistics[2]),
        "p_analytic_two_sided": float(p_values[2]),
        "beta_contrast_ci_low": float(confidence_low[2]),
        "beta_contrast_ci_high": float(confidence_high[2]),
        "degrees_of_freedom": int(degrees_of_freedom),
    }


def freedman_lane_p_value(
    response: np.ndarray,
    total_ohc: np.ndarray,
    contrast: np.ndarray,
    observed_t: float,
) -> float:
    reduced_design = np.column_stack([np.ones(len(response)), total_ohc])
    full_design = np.column_stack([reduced_design, contrast])
    reduced_fitted = reduced_design @ np.linalg.lstsq(
        reduced_design, response, rcond=None
    )[0]
    reduced_residual = response - reduced_fitted
    inverse_xtx = np.linalg.inv(full_design.T @ full_design)
    projection = inverse_xtx @ full_design.T
    degrees_of_freedom = len(response) - full_design.shape[1]
    rng = np.random.default_rng(SEED)
    exceedances = 0
    completed = 0
    batch_size = 5_000
    while completed < N_PERMUTATIONS:
        current = min(batch_size, N_PERMUTATIONS - completed)
        permutations = np.array(
            [rng.permutation(len(response)) for _ in range(current)], dtype=int
        )
        permuted_responses = reduced_fitted[:, None] + reduced_residual[
            permutations
        ].T
        coefficients = projection @ permuted_responses
        fitted = full_design @ coefficients
        residuals = permuted_responses - fitted
        residual_variances = np.sum(residuals**2, axis=0) / degrees_of_freedom
        standard_errors = np.sqrt(residual_variances * inverse_xtx[2, 2])
        t_statistics = coefficients[2, :] / standard_errors
        exceedances += int(np.sum(np.abs(t_statistics) >= abs(observed_t)))
        completed += current
    return float((exceedances + 1) / (N_PERMUTATIONS + 1))


def leave_one_event_out_range(
    response: np.ndarray, total_ohc: np.ndarray, contrast: np.ndarray
) -> tuple[float, float]:
    values = []
    for index in range(len(response)):
        keep = np.arange(len(response)) != index
        values.append(
            partial_correlation(contrast[keep], response[keep], total_ohc[keep])
        )
    return float(min(values)), float(max(values))


def plot_partial_regression(
    events: pd.DataFrame,
    x_residual: np.ndarray,
    y_residual: np.ndarray,
    statistics: dict[str, float],
) -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "axes.edgecolor": "#2f2f2f",
            "axes.linewidth": 1.1,
            "xtick.labelsize": 10.5,
            "ytick.labelsize": 10.5,
            "axes.labelsize": 12.5,
        }
    )
    dpi = 360
    fig, ax = plt.subplots(figsize=(3359 / dpi, 1660 / dpi), dpi=dpi)
    grid = np.linspace(x_residual.min() - 0.03, x_residual.max() + 0.03, 240)
    slope, intercept = np.polyfit(x_residual, y_residual, 1)

    rng = np.random.default_rng(SEED + 500)
    bootstrap_lines = []
    for _ in range(2_000):
        sample = rng.integers(0, len(events), len(events))
        if np.unique(x_residual[sample]).size < 2:
            continue
        boot_slope, boot_intercept = np.polyfit(
            x_residual[sample], y_residual[sample], 1
        )
        bootstrap_lines.append(boot_slope * grid + boot_intercept)
    line_low, line_high = np.percentile(
        np.asarray(bootstrap_lines), [2.5, 97.5], axis=0
    )
    ax.fill_between(
        grid,
        line_low,
        line_high,
        color="#9aa0a6",
        alpha=0.20,
        linewidth=0,
        zorder=0,
    )
    ax.plot(grid, slope * grid + intercept, color="#2f2f2f", linewidth=2.2)

    colors = {1997: "#2f77b4", 2015: "#e08b19", 2023: "#c43c39"}
    highlights = set(colors)
    label_offsets = {
        1982: (-23, -2),
        1986: (-24, -2),
        1991: (6, -8),
        1994: (7, 5),
        1997: (7, 4),
        2002: (-24, -10),
        2004: (-32, 7),
        2006: (-25, 7),
        2009: (6, -9),
        2015: (7, -5),
        2018: (5, 9),
        2019: (6, 5),
        2023: (7, 5),
    }
    for index, year_value in enumerate(events["year"].to_numpy(dtype=int)):
        color = colors.get(year_value, "#737373")
        size = 92 if year_value in highlights else 58
        ax.scatter(
            x_residual[index],
            y_residual[index],
            s=size,
            color=color,
            edgecolor="white",
            linewidth=0.9,
            zorder=3,
        )
        ax.annotate(
            str(year_value),
            (x_residual[index], y_residual[index]),
            xytext=label_offsets[year_value],
            textcoords="offset points",
            color=color,
            fontsize=9.4 if year_value in highlights else 8.3,
            fontweight="bold" if year_value in highlights else "normal",
        )

    stats_text = (
        f"N = {len(events)}\n"
        f"Partial r = {statistics['partial_r']:+.2f}\n"
        f"95% CI = [{statistics['partial_r_ci_low']:+.2f}, "
        f"{statistics['partial_r_ci_high']:+.2f}]\n"
        f"Analytic p = {statistics['p_analytic_two_sided']:.3f}\n"
        f"Freedman-Lane p = {statistics['p_freedman_lane']:.3f}\n"
        f"Leave-one-event-out r = {statistics['loeo_r_min']:+.2f} to "
        f"{statistics['loeo_r_max']:+.2f}"
    )
    ax.text(
        0.97,
        0.96,
        stats_text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10.0,
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": "white",
            "edgecolor": "#bdbdbd",
            "alpha": 0.94,
        },
    )
    ax.axhline(0, color="#bdbdbd", linewidth=0.9, zorder=0)
    ax.axvline(0, color="#bdbdbd", linewidth=0.9, zorder=0)
    ax.grid(color="#ececec", linewidth=0.7, zorder=0)
    ax.set_xlabel(
        "JFM meridional heat-configuration contrast residual\n"
        "($D = H_{off}-H_E$; three-band mean OHC controlled; GJ m$^{-2}$)",
        labelpad=8,
    )
    ax.set_ylabel(
        "JJA pattern-adjusted coupling residual\n"
        "(three-band mean OHC controlled; z)",
        labelpad=8,
    )
    # The retained Word template crops a narrow title band and the rightmost
    # part of the source bitmap. Keep all analytical content inside the
    # uncropped region so the document layout can remain unchanged.
    fig.subplots_adjust(left=0.085, right=0.74, top=0.90, bottom=0.19)
    fig.savefig(FIGURE_PNG, dpi=dpi, facecolor="white")
    fig.savefig(FIGURE_PDF, facecolor="white")
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(EVENTS_CSV)
    response = events["coupling_pattern_residual_z_jja"].to_numpy(dtype=float)
    total_ohc = events["total_full_0_300_gjm2_jfm"].to_numpy(dtype=float)
    off_equatorial = events["offeq_full_0_300_gjm2_jfm"].to_numpy(dtype=float)
    equatorial = events["moving_eq_full_0_300_gjm2_jfm"].to_numpy(dtype=float)
    contrast = off_equatorial - equatorial

    model = fit_primary_model(response, total_ohc, contrast)
    partial_r = partial_correlation(contrast, response, total_ohc)
    partial_ci = fisher_partial_r_ci(partial_r, len(events), 1)
    permutation_p = freedman_lane_p_value(
        response,
        total_ohc,
        contrast,
        model["t_beta_contrast"],
    )
    loeo_low, loeo_high = leave_one_event_out_range(
        response, total_ohc, contrast
    )
    statistics = {
        **model,
        "n_events": int(len(events)),
        "partial_r": partial_r,
        "partial_r_ci_low": partial_ci[0],
        "partial_r_ci_high": partial_ci[1],
        "p_freedman_lane": permutation_p,
        "n_permutations": N_PERMUTATIONS,
        "loeo_r_min": loeo_low,
        "loeo_r_max": loeo_high,
    }

    x_residual = residualize(contrast, total_ohc)
    y_residual = residualize(response, total_ohc)
    points = pd.DataFrame(
        {
            "year": events["year"].to_numpy(dtype=int),
            "group": events["group"].astype(str),
            "jfm_three_band_mean_ohc_gjm2": total_ohc,
            "jfm_equatorial_ohc_gjm2": equatorial,
            "jfm_off_equatorial_ohc_gjm2": off_equatorial,
            "jfm_meridional_contrast_D_gjm2": contrast,
            "jfm_D_residual_after_mean_ohc_control_gjm2": x_residual,
            "jja_pattern_adjusted_coupling_z": response,
            "jja_coupling_residual_after_mean_ohc_control_z": y_residual,
        }
    )
    points.to_csv(POINTS_CSV, index=False)
    STATS_JSON.write_text(json.dumps(statistics, indent=2), encoding="utf-8")
    plot_partial_regression(events, x_residual, y_residual, statistics)
    print(json.dumps(statistics, indent=2))
    print(f"Figure: {FIGURE_PNG}")


if __name__ == "__main__":
    main()
