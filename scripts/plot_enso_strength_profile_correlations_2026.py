#!/usr/bin/env python3
"""Relate early ENSO vertical-profile metrics to mature DJF amplitude.

Historical predictors are read from the SODA3 strength-profile analysis.
The outcome is the same-calendar-month linearly detrended OISST DJF
Nino-3.4 anomaly already stored in the project coupling table.  The 2026 GODAS
predictor is shown only as an x-position because its mature outcome is unknown.
"""

from __future__ import annotations

import itertools
import json
import math
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/enso_strength_vertical_profiles_2026"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig_correlations"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache_correlations"))

import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.pyplot as plt


METRICS_CSV = OUT_DIR / "vertical_profile_metrics.csv"
COUPLING_CSV = (
    ROOT
    / "data/derived/research_2026/enso_ocean_conditioned_decoupling_event_summary.csv"
)
POINTS_CSV = OUT_DIR / "vertical_profile_mature_intensity_correlation_points.csv"
STATS_CSV = OUT_DIR / "vertical_profile_mature_intensity_correlations.csv"
FIGURE_PNG = OUT_DIR / "fig_vertical_profile_metrics_vs_mature_nino34_2026.png"
FIGURE_PDF = OUT_DIR / "fig_vertical_profile_metrics_vs_mature_nino34_2026.pdf"
SUMMARY_JSON = OUT_DIR / "vertical_profile_mature_intensity_correlation_summary.json"

SEED = 20260818
N_BOOTSTRAP = 10_000

PREDICTORS = (
    {
        "id": "reservoir_depth",
        "column": "jfm_warm_reservoir_depth_m",
        "title": "Initial reservoir depth",
        "xlabel": "JFM positive-anomaly centroid depth (m)",
    },
    {
        "id": "eastward_transfer",
        "column": "warm_centroid_eastward_shift_deg",
        "title": "Eastward transfer",
        "xlabel": "JFM to AMJ centroid shift (degrees longitude)",
    },
    {
        "id": "east_50_100m_warming",
        "column": "amj_east_50_100m_mean_anomaly_degC",
        "title": "Eastern 50-100 m warming",
        "xlabel": "AMJ eastern-Pacific 50-100 m anomaly (degrees C)",
    },
)

CLASS_STYLE = {
    "strong": {"color": "#B33A3A", "marker": "o", "label": "Strong events"},
    "moderate": {"color": "#2C7FB8", "marker": "^", "label": "Moderate events"},
}


def require_files() -> None:
    missing = [str(path) for path in (METRICS_CSV, COUPLING_CSV) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing inputs: {missing}")


def build_points() -> tuple[pd.DataFrame, pd.Series]:
    metrics = pd.read_csv(METRICS_CSV)
    history = metrics.loc[metrics["class"].isin(CLASS_STYLE)].copy()
    target = metrics.loc[
        metrics["class"].eq("target") & metrics["event_year"].eq(2026)
    ]
    if len(target) != 1:
        raise ValueError("Expected exactly one 2026 target row")

    coupling = pd.read_csv(COUPLING_CSV)
    mature = coupling.loc[
        coupling["season"].eq("DJF"),
        ["year", "mature_djf_nino34_c"],
    ].drop_duplicates("year")
    points = history.merge(
        mature,
        left_on="event_year",
        right_on="year",
        how="left",
        validate="one_to_one",
    )
    needed = [item["column"] for item in PREDICTORS] + ["mature_djf_nino34_c"]
    if len(points) != 9 or points[needed].isna().any().any():
        raise ValueError("The expected nine historical events are not complete")
    return points.sort_values("event_year").reset_index(drop=True), target.iloc[0]


def rank_average(values: np.ndarray) -> np.ndarray:
    return pd.Series(values).rank(method="average").to_numpy(dtype=float)


def pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    xc = np.asarray(x, dtype=float) - np.mean(x)
    yc = np.asarray(y, dtype=float) - np.mean(y)
    denominator = np.sqrt(np.sum(xc**2) * np.sum(yc**2))
    return float(np.sum(xc * yc) / denominator)


def exact_permutation_matrix(n: int) -> np.ndarray:
    count = math.factorial(n)
    flattened = np.fromiter(
        (index for order in itertools.permutations(range(n)) for index in order),
        dtype=np.int16,
        count=count * n,
    )
    return flattened.reshape(count, n)


def exact_permutation_p(
    x: np.ndarray, y: np.ndarray, permutations: np.ndarray
) -> tuple[float, float]:
    xc = x - np.mean(x)
    yc = y - np.mean(y)
    denominator = np.sqrt(np.sum(xc**2) * np.sum(yc**2))
    observed = float(np.sum(xc * yc) / denominator)
    permuted = yc[permutations] @ xc / denominator
    p_value = float(np.mean(np.abs(permuted) >= abs(observed) - 1.0e-14))
    return observed, p_value


def bootstrap_regression(
    x: np.ndarray, y: np.ndarray, grid: np.ndarray, seed: int
) -> tuple[np.ndarray, np.ndarray, tuple[float, float]]:
    rng = np.random.default_rng(seed)
    lines: list[np.ndarray] = []
    correlations: list[float] = []
    for _ in range(N_BOOTSTRAP):
        draw = rng.integers(0, len(x), len(x))
        xb = x[draw]
        yb = y[draw]
        if np.unique(xb).size < 2 or np.std(yb) == 0:
            continue
        slope, intercept = np.polyfit(xb, yb, 1)
        lines.append(slope * grid + intercept)
        correlations.append(pearson_r(xb, yb))
    line_array = np.asarray(lines)
    low, high = np.percentile(line_array, [2.5, 97.5], axis=0)
    ci = tuple(float(value) for value in np.percentile(correlations, [2.5, 97.5]))
    return low, high, ci


def fdr_bh(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * len(p) / np.arange(1, len(p) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.minimum(adjusted, 1.0)
    return output


def compute_statistics(points: pd.DataFrame) -> pd.DataFrame:
    y = points["mature_djf_nino34_c"].to_numpy(dtype=float)
    permutations = exact_permutation_matrix(len(points))
    rows = []
    for item in PREDICTORS:
        x = points[item["column"]].to_numpy(dtype=float)
        pearson, permutation_p = exact_permutation_p(x, y, permutations)
        spearman = pearson_r(rank_average(x), rank_average(y))
        grid = np.linspace(x.min(), x.max(), 200)
        _, _, ci = bootstrap_regression(
            x, y, grid, SEED + len(rows) * 101
        )
        rows.append(
            {
                "predictor_id": item["id"],
                "predictor_column": item["column"],
                "n_events": len(points),
                "pearson_r": pearson,
                "spearman_r": spearman,
                "exact_permutation_p": permutation_p,
                "bootstrap_r_ci_low": ci[0],
                "bootstrap_r_ci_high": ci[1],
            }
        )
    result = pd.DataFrame(rows)
    result["fdr_q"] = fdr_bh(result["exact_permutation_p"].to_numpy())
    return result


def add_event_labels(axis: plt.Axes, points: pd.DataFrame, x_column: str) -> None:
    # Offsets are panel-specific because nine labels otherwise collide in the small sample.
    offsets = {
        "jfm_warm_reservoir_depth_m": {
            1982: (5, 5), 1986: (5, -13), 1991: (5, 5), 1994: (-28, -13),
            1997: (5, -12), 2002: (5, 5), 2009: (-28, 5), 2015: (5, 5), 2023: (-30, 5),
        },
        "warm_centroid_eastward_shift_deg": {
            1982: (5, 5), 1986: (5, -13), 1991: (5, 5), 1994: (5, 5),
            1997: (5, -13), 2002: (5, 5), 2009: (-28, 5), 2015: (5, 5), 2023: (5, 5),
        },
        "amj_east_50_100m_mean_anomaly_degC": {
            1982: (5, 5), 1986: (5, -13), 1991: (5, 5), 1994: (5, -13),
            1997: (-28, -13), 2002: (5, 5), 2009: (5, 5), 2015: (-28, 5), 2023: (5, 5),
        },
    }
    for _, row in points.iterrows():
        event_year = int(row["event_year"])
        axis.annotate(
            str(event_year),
            (float(row[x_column]), float(row["mature_djf_nino34_c"])),
            xytext=offsets[x_column][event_year],
            textcoords="offset points",
            fontsize=7.7,
            color=CLASS_STYLE[str(row["class"])]["color"],
            zorder=5,
        )


def plot(points: pd.DataFrame, target: pd.Series, statistics: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 9.5,
            "axes.titlesize": 11.5,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.9,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.65), sharey=True)
    y = points["mature_djf_nino34_c"].to_numpy(dtype=float)
    stats_lookup = statistics.set_index("predictor_id")

    for panel_index, (axis, item) in enumerate(zip(axes, PREDICTORS)):
        x = points[item["column"]].to_numpy(dtype=float)
        span = max(float(np.ptp(x)), 1.0)
        grid = np.linspace(x.min() - 0.04 * span, x.max() + 0.04 * span, 250)
        low, high, _ = bootstrap_regression(
            x, y, grid, SEED + panel_index * 101
        )
        slope, intercept = np.polyfit(x, y, 1)
        axis.fill_between(
            grid,
            low,
            high,
            color="#A8A8A8",
            alpha=0.24,
            linewidth=0,
            zorder=0,
        )
        axis.plot(grid, slope * grid + intercept, color="#303030", linewidth=1.6)

        for event_class, style in CLASS_STYLE.items():
            selected = points.loc[points["class"].eq(event_class)]
            axis.scatter(
                selected[item["column"]],
                selected["mature_djf_nino34_c"],
                s=52,
                marker=style["marker"],
                color=style["color"],
                edgecolor="white",
                linewidth=0.7,
                label=style["label"],
                zorder=3,
            )
        add_event_labels(axis, points, item["column"])

        target_x = float(target[item["column"]])
        axis.axvline(
            target_x,
            color="#6A3D9A",
            linestyle=(0, (4, 3)),
            linewidth=1.5,
            zorder=1,
        )
        axis.text(
            target_x,
            2.66,
            "2026 x-position",
            ha="right" if target_x > np.median(x) else "left",
            va="top",
            rotation=90,
            fontsize=8.2,
            color="#6A3D9A",
        )

        row = stats_lookup.loc[item["id"]]
        stats_x = 0.96 if panel_index == 0 else 0.04
        stats_ha = "right" if panel_index == 0 else "left"
        axis.text(
            stats_x,
            0.96,
            f"N = {int(row.n_events)}\n"
            f"Pearson r = {row.pearson_r:+.2f}\n"
            f"Exact perm. p = {row.exact_permutation_p:.3f}\n"
            f"FDR q = {row.fdr_q:.3f}",
            transform=axis.transAxes,
            ha=stats_ha,
            va="top",
            fontsize=8.4,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "white",
                "edgecolor": "#C9C9C9",
                "alpha": 0.82,
            },
            zorder=2,
        )
        axis.set_title(f"{chr(97 + panel_index)}  {item['title']}", loc="left", fontweight="bold")
        axis.set_xlabel(item["xlabel"])
        axis.grid(color="#E8E8E8", linewidth=0.7)
        axis.set_ylim(0.72, 2.72)
        axis.spines[["top", "right"]].set_visible(False)

    axes[0].set_ylabel("Mature DJF Niño-3.4 anomaly (degrees C)")
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(
        plt.Line2D([0], [0], color="#6A3D9A", linestyle=(0, (4, 3)), linewidth=1.5)
    )
    labels.append("2026 predictor only")
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.855),
        ncol=3,
        frameon=False,
    )
    fig.suptitle(
        "Early vertical heat structure versus mature ENSO amplitude",
        x=0.07,
        y=0.985,
        ha="left",
        fontsize=15.5,
        fontweight="bold",
    )
    fig.text(
        0.07,
        0.92,
        "Historical events: SODA3 JFM-AMJ predictors and detrended OISST DJF Niño-3.4; 2026 GODAS is not included in the fits",
        ha="left",
        va="top",
        fontsize=9.4,
        color="#555555",
    )
    fig.text(
        0.5,
        0.012,
        "Gray shading: event-bootstrap 95% regression interval. Exploratory N=9 comparison; association does not imply causation or a 2026/27 forecast.",
        ha="center",
        va="bottom",
        fontsize=8.2,
        color="#555555",
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.745, bottom=0.19, wspace=0.24)
    fig.savefig(FIGURE_PNG, dpi=320, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    require_files()
    points, target = build_points()
    statistics = compute_statistics(points)
    points.to_csv(POINTS_CSV, index=False)
    statistics.to_csv(STATS_CSV, index=False)
    plot(points, target, statistics)
    summary = {
        "figure_png": str(FIGURE_PNG),
        "figure_pdf": str(FIGURE_PDF),
        "points_csv": str(POINTS_CSV),
        "statistics_csv": str(STATS_CSV),
        "n_historical_events": len(points),
        "target_year": 2026,
        "target_outcome_used_in_fit": False,
        "statistics": statistics.to_dict(orient="records"),
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
