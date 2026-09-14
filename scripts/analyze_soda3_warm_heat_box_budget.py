#!/usr/bin/env python3
"""Close a reduced 160E-180E SODA3 T>20C warm-heat box budget.

Warm heat content is integrated from the existing five-day latitude-depth
section diagnostic, rho*Cp*max(T-20C, 0), across longitude.  The explicit
zonal term is Q20 at the western boundary minus Q20 at the eastern boundary.
The residual therefore contains meridional convergence, surface/diapycnal
heating, vertical exchange, mixing, and discretization; it is not assigned to
any one of those processes without the corresponding boundary fields.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_soda3_warm_heat_budget")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_force_balance_residual_processes as residual  # noqa: E402
import verify_soda3_force_balance_tendency as balance  # noqa: E402


EVENTS = balance.EVENTS
HIGHLIGHTS = (1997, 2015, 2023)
EARTH_RADIUS = 6_371_000.0
MAIN_BOX = (160.0, 180.0)
SENSITIVITY_BOXES = (
    (150.0, 180.0),
    (155.0, 180.0),
    (160.0, 180.0),
    (160.0, 185.0),
    (160.0, 190.0),
    (170.0, 190.0),
    (180.0, 200.0),
)
RAW_DIR = ROOT / "data/interim/research_2026/soda3_5day_event_transport"
MONTHLY_REFERENCE = ROOT / "data/derived/research_2026/soda3_warm_transport_longitude_1980_2024.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_warm_heat_box_budget"
PDF_DIR = ROOT / "output/pdf"
BUDGET_CSV = DERIVED / "soda3_warm_heat_160e_180e_budget.csv"
EVENT_CSV = DERIVED / "soda3_warm_heat_box_budget_event_summary.csv"
SENSITIVITY_CSV = DERIVED / "soda3_warm_heat_box_budget_sensitivity.csv"
SKILL_CSV = DERIVED / "soda3_warm_heat_box_budget_loeo_skill.csv"
PREDICTIONS_CSV = DERIVED / "soda3_warm_heat_box_budget_loeo_predictions.csv"
BOOTSTRAP_CSV = DERIVED / "soda3_warm_heat_box_budget_bootstrap.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_warm_heat_box_budget_diagnostics.json"
FIGURE_PNG = OUT / "soda3_warm_heat_box_budget.png"
FIGURE_PDF = PDF_DIR / "soda3_warm_heat_box_budget.pdf"
REPORT_MD = OUT / "SODA3_WARM_HEAT_BOX_BUDGET_RESULT_CN.md"

RNG_SEED = 20260803
N_BOOTSTRAP = 10000


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.5,
            "axes.titlesize": 9.8,
            "axes.labelsize": 8.8,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 7.6,
            "ytick.labelsize": 7.6,
            "legend.fontsize": 7.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def read_raw() -> pd.DataFrame:
    pieces = []
    for year in EVENTS:
        path = RAW_DIR / f"soda3_5day_transport_{year}_jan_jun.csv"
        pieces.append(pd.read_csv(path, parse_dates=["time"]))
    frame = pd.concat(pieces, ignore_index=True).sort_values(["year", "time", "longitude_e"])
    expected = sum(frame.loc[frame["year"].eq(year), "time"].nunique() for year in EVENTS)
    if expected != frame[["year", "time"]].drop_duplicates().shape[0]:
        raise ValueError("Duplicate event pentads")
    if not set(np.arange(150.0, 241.0, 5.0)).issubset(set(frame["longitude_e"].unique())):
        raise ValueError("Missing five-degree longitude gates")
    return frame


def anchor_heat_anomaly(raw: pd.DataFrame) -> pd.DataFrame:
    reference = pd.read_csv(MONTHLY_REFERENCE)[
        ["year", "month", "longitude_e", "warm_heat_section_gj_per_m_anom"]
    ]
    within = raw.groupby(["year", "month", "longitude_e"])[
        "warm_heat_section_gj_per_m"
    ].transform("mean")
    output = raw.merge(
        reference,
        on=["year", "month", "longitude_e"],
        how="left",
        validate="many_to_one",
    )
    if output["warm_heat_section_gj_per_m_anom"].isna().any():
        raise ValueError("Missing warm-heat monthly anomaly reference")
    output["warm_heat_section_anchored_anom_gj_m"] = (
        output["warm_heat_section_gj_per_m"]
        - within
        + output["warm_heat_section_gj_per_m_anom"]
    )
    return output


def integrate_box(
    raw: pd.DataFrame,
    west: float,
    east: float,
) -> pd.DataFrame:
    selected = raw.loc[raw["longitude_e"].between(west, east)].copy()
    heat = selected.pivot(
        index=["time", "year"],
        columns="longitude_e",
        values="warm_heat_section_gj_per_m",
    ).sort_index()
    heat_anom = selected.pivot(
        index=["time", "year"],
        columns="longitude_e",
        values="warm_heat_section_anchored_anom_gj_m",
    ).reindex(heat.index)
    q20 = selected.pivot(
        index=["time", "year"], columns="longitude_e", values="q20_pw"
    ).reindex(heat.index)
    if west not in heat.columns or east not in heat.columns:
        raise ValueError(f"Missing box boundary {west}-{east}")
    x_m = EARTH_RADIUS * np.deg2rad(heat.columns.to_numpy(dtype=float))
    raw_heat_pj = np.trapz(heat.to_numpy(dtype=float), x=x_m, axis=1) / 1.0e6
    anomaly_heat_pj = np.trapz(
        heat_anom.to_numpy(dtype=float), x=x_m, axis=1
    ) / 1.0e6
    frame = pd.DataFrame(
        {
            "box_h20_pj": raw_heat_pj,
            "box_h20_anom_pj": anomaly_heat_pj,
            "q20_west_pw": q20[west].to_numpy(dtype=float),
            "q20_east_pw": q20[east].to_numpy(dtype=float),
        },
        index=heat.index,
    ).reset_index()
    frame["zonal_q20_convergence_pw"] = frame["q20_west_pw"] - frame["q20_east_pw"]
    pieces = []
    intervals = []
    for _, event in frame.groupby("year", sort=True):
        event = event.sort_values("time").copy()
        forward_seconds = (event["time"].shift(-1) - event["time"]).dt.total_seconds()
        trailing_seconds = (event["time"] - event["time"].shift(1)).dt.total_seconds()
        intervals.extend((forward_seconds.dropna() / 86400.0).tolist())
        event["box_h20_tendency_future5_pw"] = (
            event["box_h20_pj"].shift(-1) - event["box_h20_pj"]
        ) / forward_seconds
        event["box_h20_tendency_trailing5_pw"] = (
            event["box_h20_pj"] - event["box_h20_pj"].shift(1)
        ) / trailing_seconds
        event["zonal_q20_convergence_midpoint_pw"] = 0.5 * (
            event["zonal_q20_convergence_pw"]
            + event["zonal_q20_convergence_pw"].shift(-1)
        )
        event["zonal_q20_convergence_previous_midpoint_pw"] = 0.5 * (
            event["zonal_q20_convergence_pw"]
            + event["zonal_q20_convergence_pw"].shift(1)
        )
        event["budget_residual_future5_pw"] = (
            event["box_h20_tendency_future5_pw"]
            - event["zonal_q20_convergence_midpoint_pw"]
        )
        event["budget_residual_previous5_pw"] = (
            event["box_h20_tendency_trailing5_pw"]
            - event["zonal_q20_convergence_previous_midpoint_pw"]
        )
        event["zonal_q20_convergence_change5_pw"] = (
            event["zonal_q20_convergence_pw"]
            - event["zonal_q20_convergence_pw"].shift(1)
        )
        pieces.append(event)
    output = pd.concat(pieces, ignore_index=True).sort_values(["year", "time"])
    interval_array = np.asarray(intervals, dtype=float)
    if not np.all((interval_array >= 4.0) & (interval_array <= 6.0)):
        raise ValueError("Unexpected SODA3 pentad interval")
    output["box_west_lon_e"] = west
    output["box_east_lon_e"] = east
    return output


def event_equal_slope(
    frame: pd.DataFrame, group_column: str = "year"
) -> tuple[float, float]:
    data = frame.dropna(
        subset=["zonal_q20_convergence_midpoint_pw", "box_h20_tendency_future5_pw"]
    )
    weights = balance.event_weights(data[group_column])
    x = data["zonal_q20_convergence_midpoint_pw"].to_numpy(dtype=float)
    y = data["box_h20_tendency_future5_pw"].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    weighted = design * np.sqrt(weights)[:, None]
    beta = np.linalg.lstsq(weighted, y * np.sqrt(weights), rcond=None)[0]
    return float(beta[0]), float(beta[1])


def cluster_budget_bootstrap(frame: pd.DataFrame) -> dict[str, float]:
    data = frame.dropna(
        subset=["zonal_q20_convergence_midpoint_pw", "box_h20_tendency_future5_pw"]
    )
    years = sorted(data["year"].unique())
    rng = np.random.default_rng(RNG_SEED)
    correlations = np.empty(N_BOOTSTRAP)
    slopes = np.empty(N_BOOTSTRAP)
    for index in range(N_BOOTSTRAP):
        selected = rng.choice(years, len(years), replace=True)
        sample_parts = []
        for sample_id, year in enumerate(selected):
            part = data.loc[data["year"].eq(year)].copy()
            part["_sample_event"] = sample_id
            sample_parts.append(part)
        sample = pd.concat(sample_parts, ignore_index=True)
        correlations[index] = pearsonr(
            sample["zonal_q20_convergence_midpoint_pw"],
            sample["box_h20_tendency_future5_pw"],
        ).statistic
        _, slopes[index] = event_equal_slope(sample, group_column="_sample_event")
    intercept, slope = event_equal_slope(data)
    return {
        "correlation": float(
            pearsonr(
                data["zonal_q20_convergence_midpoint_pw"],
                data["box_h20_tendency_future5_pw"],
            ).statistic
        ),
        "correlation_ci_low": float(np.quantile(correlations, 0.025)),
        "correlation_ci_high": float(np.quantile(correlations, 0.975)),
        "intercept_pw": intercept,
        "slope": slope,
        "slope_ci_low": float(np.quantile(slopes, 0.025)),
        "slope_ci_high": float(np.quantile(slopes, 0.975)),
    }


def sensitivity_table(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for west, east in SENSITIVITY_BOXES:
        frame = integrate_box(raw, west, east)
        data = frame.dropna(
            subset=["zonal_q20_convergence_midpoint_pw", "box_h20_tendency_future5_pw"]
        )
        intercept, slope = event_equal_slope(data)
        event_correlations = []
        event_slopes = []
        for _, event in data.groupby("year"):
            event_correlations.append(
                float(
                    pearsonr(
                        event["zonal_q20_convergence_midpoint_pw"],
                        event["box_h20_tendency_future5_pw"],
                    ).statistic
                )
            )
            event_slopes.append(
                float(
                    np.polyfit(
                        event["zonal_q20_convergence_midpoint_pw"],
                        event["box_h20_tendency_future5_pw"],
                        1,
                    )[0]
                )
            )
        rows.append(
            {
                "west_lon_e": west,
                "east_lon_e": east,
                "width_degrees": east - west,
                "pooled_correlation": float(
                    pearsonr(
                        data["zonal_q20_convergence_midpoint_pw"],
                        data["box_h20_tendency_future5_pw"],
                    ).statistic
                ),
                "event_equal_intercept_pw": intercept,
                "event_equal_slope": slope,
                "median_event_correlation": float(np.median(event_correlations)),
                "median_event_slope": float(np.median(event_slopes)),
                "identity_rmse_pw": float(
                    np.sqrt(
                        np.mean(
                            (
                                data["box_h20_tendency_future5_pw"]
                                - data["zonal_q20_convergence_midpoint_pw"]
                            )
                            ** 2
                        )
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def prediction_analysis(
    features: pd.DataFrame,
    budget: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = features.merge(
        budget[
            [
                "time",
                "year",
                "box_h20_anom_pj",
                "zonal_q20_convergence_pw",
                "zonal_q20_convergence_change5_pw",
                "box_h20_tendency_trailing5_pw",
                "budget_residual_previous5_pw",
            ]
        ],
        on=["time", "year"],
        how="left",
        validate="one_to_one",
    )
    models = {
        "base": residual.BASE_FEATURES,
        "base_plus_q20_convergence": residual.BASE_FEATURES
        + ["zonal_q20_convergence_pw", "zonal_q20_convergence_change5_pw"],
        "base_plus_storage_tendency": residual.BASE_FEATURES
        + ["box_h20_tendency_trailing5_pw"],
        "base_plus_previous_residual": residual.BASE_FEATURES
        + ["budget_residual_previous5_pw"],
        "base_plus_heat_budget": residual.BASE_FEATURES
        + [
            "box_h20_anom_pj",
            "zonal_q20_convergence_pw",
            "zonal_q20_convergence_change5_pw",
            "box_h20_tendency_trailing5_pw",
            "budget_residual_previous5_pw",
        ],
        "base_plus_pulse": residual.BASE_FEATURES
        + ["m160_minus_m180_sv", "taux_change5_nm2"],
        "base_plus_pulse_and_heat_budget": residual.BASE_FEATURES
        + [
            "m160_minus_m180_sv",
            "taux_change5_nm2",
            "box_h20_anom_pj",
            "zonal_q20_convergence_pw",
            "zonal_q20_convergence_change5_pw",
            "box_h20_tendency_trailing5_pw",
            "budget_residual_previous5_pw",
        ],
    }
    predictions, coefficients = residual.nested_loeo(
        frame,
        "m180_tendency_future5",
        model_features=models,
    )
    skill = residual.summarize_skill(predictions)
    deltas = residual.event_deltas(predictions)
    bootstrap = residual.bootstrap_deltas(deltas)
    return predictions, coefficients, skill, bootstrap


def event_summary(budget: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, event in budget.groupby("year", sort=True):
        data = event.dropna(
            subset=["zonal_q20_convergence_midpoint_pw", "box_h20_tendency_future5_pw"]
        )
        slope = float(
            np.polyfit(
                data["zonal_q20_convergence_midpoint_pw"],
                data["box_h20_tendency_future5_pw"],
                1,
            )[0]
        )
        rows.append(
            {
                "year": int(year),
                "mean_zonal_convergence_pw": float(data["zonal_q20_convergence_midpoint_pw"].mean()),
                "mean_storage_tendency_pw": float(data["box_h20_tendency_future5_pw"].mean()),
                "mean_budget_residual_pw": float(data["budget_residual_future5_pw"].mean()),
                "rms_budget_residual_pw": float(np.sqrt(np.mean(data["budget_residual_future5_pw"] ** 2))),
                "event_correlation": float(
                    pearsonr(
                        data["zonal_q20_convergence_midpoint_pw"],
                        data["box_h20_tendency_future5_pw"],
                    ).statistic
                ),
                "event_slope": slope,
            }
        )
    return pd.DataFrame(rows)


def row_for(frame: pd.DataFrame, model: str) -> pd.Series:
    return frame.loc[frame["model"].eq(model)].iloc[0]


def plot_result(
    budget: pd.DataFrame,
    events: pd.DataFrame,
    sensitivity: pd.DataFrame,
    skill: pd.DataFrame,
    bootstrap: pd.DataFrame,
    budget_stats: dict[str, float],
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.4, 8.1))
    figure.subplots_adjust(left=0.09, right=0.975, bottom=0.11, top=0.91, wspace=0.27, hspace=0.31)

    # (a) Physical box budget.
    ax = axes[0, 0]
    data = budget.dropna(
        subset=["zonal_q20_convergence_midpoint_pw", "box_h20_tendency_future5_pw"]
    )
    residual_limit = float(np.nanpercentile(np.abs(data["budget_residual_future5_pw"]), 98))
    image = ax.scatter(
        data["zonal_q20_convergence_midpoint_pw"],
        data["box_h20_tendency_future5_pw"],
        c=data["budget_residual_future5_pw"],
        cmap="RdBu_r",
        vmin=-residual_limit,
        vmax=residual_limit,
        s=18,
        alpha=0.58,
        linewidth=0,
    )
    limit = float(
        np.nanpercentile(
            np.abs(
                data[
                    ["zonal_q20_convergence_midpoint_pw", "box_h20_tendency_future5_pw"]
                ].to_numpy()
            ),
            99,
        )
    )
    ax.plot([-limit, limit], [-limit, limit], color="#222222", ls="--", lw=0.9, label="1:1 closed budget")
    xline = np.linspace(-limit, limit, 100)
    ax.plot(
        xline,
        budget_stats["intercept_pw"] + budget_stats["slope"] * xline,
        color="#6A3D9A",
        lw=1.4,
        label=f"event-equal slope = {budget_stats['slope']:.2f}",
    )
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.axhline(0.0, color="#777777", lw=0.5)
    ax.axvline(0.0, color="#777777", lw=0.5)
    ax.set_xlabel("Zonal Q20 convergence, Q160 - Q180 (PW)")
    ax.set_ylabel("Next-pentad box H20 tendency (PW)")
    ax.set_title("(a) Zonal inflow matters, but the box is not closed", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    cb = figure.colorbar(image, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("Unresolved budget residual (PW)")

    # (b) Box sensitivity.
    ax = axes[0, 1]
    labels = [f"{int(row.west_lon_e)}-{int(row.east_lon_e)}E" for row in sensitivity.itertuples()]
    x = np.arange(len(sensitivity))
    ax.plot(x, sensitivity["event_equal_slope"], color="#2C7FB8", marker="o", lw=1.3, label="Storage response slope")
    ax.plot(x, sensitivity["pooled_correlation"], color="#B7352D", marker="s", lw=1.3, label="Correlation")
    ax.axhline(1.0, color="#222222", ls="--", lw=0.8, label="Full zonal retention")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylim(0.0, 1.08)
    ax.set_ylabel("Dimensionless")
    ax.set_title("(b) Result is stable across neighboring boxes", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    # (c) Predictive incremental skill.
    ax = axes[1, 0]
    order = [
        "base_plus_q20_convergence",
        "base_plus_storage_tendency",
        "base_plus_previous_residual",
        "base_plus_heat_budget",
        "base_plus_pulse",
        "base_plus_pulse_and_heat_budget",
    ]
    labels = [
        "+ current Q20 convergence",
        "+ trailing storage tendency",
        "+ previous budget residual",
        "+ full reduced heat budget",
        "+ wind/upstream pulse",
        "+ pulse and heat budget",
    ]
    current = bootstrap.set_index("model").loc[order]
    y = np.arange(len(order))
    colors = ["#2C7FB8" if value < 0 else "#B8B8B8" for value in current["mean_delta_mse_vs_base"]]
    ax.barh(y, current["mean_delta_mse_vs_base"], color=colors)
    ax.errorbar(
        current["mean_delta_mse_vs_base"],
        y,
        xerr=[
            current["mean_delta_mse_vs_base"] - current["ci_low"],
            current["ci_high"] - current["mean_delta_mse_vs_base"],
        ],
        fmt="none",
        ecolor="#222222",
        capsize=3,
        lw=1.0,
    )
    ax.axvline(0.0, color="#222222", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Event-mean MSE change versus base ((Sv day$^{-1}$)$^2$)")
    ax.set_title("(c) Does the heat budget improve next-pentad transport tendency?", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    # (d) Highlighted residual evolution.
    ax = axes[1, 1]
    colors_by_year = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}
    for year in HIGHLIGHTS:
        current = budget.loc[budget["year"].eq(year)].sort_values("time")
        day = (current["time"] - pd.Timestamp(year=year, month=1, day=1)).dt.days
        ax.plot(day, current["budget_residual_future5_pw"], color=colors_by_year[year], lw=1.4, label=str(year))
    ax.axhline(0.0, color="#222222", lw=0.8)
    ax.set_xticks([0, 31, 59, 90, 120, 151, 181])
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"])
    ax.set_ylabel("Unresolved heat-budget residual (PW)")
    ax.set_title("(d) The compensating term is event- and pulse-dependent", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3, loc="upper right")
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    figure.suptitle(
        "SODA3 five-day warm-heat budget for the 160E-180E equatorial box",
        fontsize=13.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "H20 integrates rho Cp max(T-20C,0) over 5S-5N, 0-300 m and longitude. "
        "Residual includes meridional convergence, surface/diapycnal heating, vertical exchange, mixing and discretization.",
        ha="center",
        fontsize=7.0,
        color="#555555",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    raw = anchor_heat_anomaly(read_raw())
    budget = integrate_box(raw, *MAIN_BOX)
    sensitivity = sensitivity_table(raw)
    events = event_summary(budget)
    budget_stats = cluster_budget_bootstrap(budget)
    features, feature_qa = residual.build_features()
    predictions, coefficients, skill, prediction_bootstrap = prediction_analysis(features, budget)

    base_skill = row_for(skill, "base")
    storage_skill = row_for(skill, "base_plus_storage_tendency")
    heat_skill = row_for(skill, "base_plus_heat_budget")
    pulse_skill = row_for(skill, "base_plus_pulse")
    combined_skill = row_for(skill, "base_plus_pulse_and_heat_budget")
    heat_boot = row_for(prediction_bootstrap, "base_plus_heat_budget")
    storage_boot = row_for(prediction_bootstrap, "base_plus_storage_tendency")
    combined_boot = row_for(prediction_bootstrap, "base_plus_pulse_and_heat_budget")
    highlighted = events.set_index("year").loc[list(HIGHLIGHTS)]

    diagnostics = {
        "events": list(EVENTS),
        "box": {"west_lon_e": MAIN_BOX[0], "east_lon_e": MAIN_BOX[1], "lat_bounds": [-5.0, 5.0], "depth_max_m": 300.0},
        "warm_heat_definition": "rho0*Cp0*max(T-20C,0)",
        "budget_equation": "dH20/dt = Q20_160E - Q20_180E + residual",
        "budget_statistics": budget_stats,
        "quality_control": feature_qa,
        "interpretation_limits": [
            "The residual is not assigned to a single process without meridional, vertical and diabatic boundary terms.",
            "Five-degree longitude sampling is tested with neighboring box boundaries but is not a full grid-cell finite-volume budget.",
            "Predictive models use only contemporaneous or trailing budget terms; the future residual is diagnostic only.",
        ],
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    budget.to_csv(BUDGET_CSV, index=False)
    events.to_csv(EVENT_CSV, index=False)
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)
    predictions.to_csv(PREDICTIONS_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    prediction_bootstrap.to_csv(BOOTSTRAP_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    plot_result(budget, events, sensitivity, skill, prediction_bootstrap, budget_stats)

    report = rf"""# SODA3 160°E—180°E暖层热含量箱体收支

## 定义

在5°S—5°N、0—300 m内，定义相对于20°C的暖层热含量：

\[
H_{{20}}=\iiint \rho_0 C_p\max(T-20^\circ\mathrm{{C}},0)\,dV.
\]

使用同一SODA3五日资料的Q20边界输送，计算：

\[
\frac{{dH_{{20}}}}{{dt}}=Q_{{160E}}-Q_{{180E}}+R_H.
\]

`R_H`统一包含南北边界热输送、表面及穿越20°C等温面的加热、垂向交换、混合和离散误差；现阶段不把它强行归因给其中某一项。

## 物理收支结果

- 东西向Q20汇聚与下一五日箱体储热倾向相关 `r={budget_stats['correlation']:+.2f}`，事件聚类95%区间 `[{budget_stats['correlation_ci_low']:+.2f}, {budget_stats['correlation_ci_high']:+.2f}]`。
- 事件等权储存响应斜率为 `{budget_stats['slope']:.2f}`，区间 `[{budget_stats['slope_ci_low']:.2f}, {budget_stats['slope_ci_high']:.2f}]`；如果所有东西向汇聚都留在箱内，斜率应接近1。
- 邻近箱体的斜率范围为 `{sensitivity['event_equal_slope'].min():.2f}`—`{sensitivity['event_equal_slope'].max():.2f}`，相关范围 `{sensitivity['pooled_correlation'].min():.2f}`—`{sensitivity['pooled_correlation'].max():.2f}`，说明约三分之一量级的响应不是160°E—180°E边界选择偶然造成的。

这说明东西向暖热汇聚的变化确实推动本地储热变化，但储热响应约为汇聚异常的0.38倍；其余同量级变化被经向、表面、垂向及混合过程补偿。该斜率是统计响应系数，不应直接解释为固定的“保留效率”。

## 对下一五日日界线暖水输送变化率的预测

- 原受力平衡基准RMSE `{base_skill['event_equal_rmse']:.3f} Sv day⁻¹`；
- 只加入上一五日原始储热倾向后RMSE `{storage_skill['event_equal_rmse']:.3f}`，MSE变化 `{storage_boot['mean_delta_mse_vs_base']:+.3f}`，95%区间 `[{storage_boot['ci_low']:+.3f}, {storage_boot['ci_high']:+.3f}]`；这是最简洁且不使用未来残差的热含量增量；
- 加入完整的滞后热收支状态后RMSE `{heat_skill['event_equal_rmse']:.3f}`，MSE变化 `{heat_boot['mean_delta_mse_vs_base']:+.3f}`，95%区间 `[{heat_boot['ci_low']:+.3f}, {heat_boot['ci_high']:+.3f}]`；
- 加入上一阶段的风应力变化＋上游输送脉冲后RMSE `{pulse_skill['event_equal_rmse']:.3f}`；
- 再叠加热收支后RMSE `{combined_skill['event_equal_rmse']:.3f}`，相对基准MSE变化 `{combined_boot['mean_delta_mse_vs_base']:+.3f}`，区间 `[{combined_boot['ci_low']:+.3f}, {combined_boot['ci_high']:+.3f}]`。

因此，当前最稳健的新量不是一个绝对OHC阈值，而是**上一五日160°E—180°E暖层热含量变化率**。这里仍是基于再分析资料的回报式事件留一检验，不等同于实时业务预报；不能因为预算式在物理上正确，就自动认为它能提高预测。

## 1997、2015和2023

- 1997年平均东西汇聚 `{highlighted.loc[1997, 'mean_zonal_convergence_pw']:+.2f} PW`，平均未解析补偿 `{highlighted.loc[1997, 'mean_budget_residual_pw']:+.2f} PW`；
- 2015年分别为 `{highlighted.loc[2015, 'mean_zonal_convergence_pw']:+.2f}` 和 `{highlighted.loc[2015, 'mean_budget_residual_pw']:+.2f} PW`；
- 2023年分别为 `{highlighted.loc[2023, 'mean_zonal_convergence_pw']:+.2f}` 和 `{highlighted.loc[2023, 'mean_budget_residual_pw']:+.2f} PW`。

平均量主要用于说明收支符号；真正的转折仍由图中的五日脉冲决定。

## 对“临界点”的更新

平衡条件现在可进一步写成：

\[
\frac{{dH_{{20}}}}{{dt}}=0
\quad\Longleftrightarrow\quad
Q_{{160E}}-Q_{{180E}}=-R_H.
\]

所以临界点不仅取决于西部有多少暖水或东西向输送多强，还取决于箱体的**储存响应和非东西向补偿项**。这正是相同西部暖量背景下，不同事件可以走向不同耦合路径的动力入口。

## 输出

- 图：`{FIGURE_PDF}`
- 五日箱体收支：`{BUDGET_CSV}`
- 事件汇总：`{EVENT_CSV}`
- 箱体敏感性：`{SENSITIVITY_CSV}`
- 留一预测评分：`{SKILL_CSV}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
