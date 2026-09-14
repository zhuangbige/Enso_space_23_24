#!/usr/bin/env python3
"""Test whether western warm-reservoir release anticipates atmospheric coupling.

The ocean predictor is the strictly causal, trailing five-day tendency of the
SODA3 T>20 C warm-heat content in 5S-5N, 0-300 m, 160E-180E.  Positive
``reservoir_release`` means the western box is losing warm heat.  Two targets
are kept separate: a five-day SODA3 persistent-westerly onset and monthly
ERA5-u850/CPC-OLR wind, convection, and joint-coupling onsets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_soda3_release_coupling")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_5day_ohc_geometry_coupling as geometry  # noqa: E402


EVENTS = tuple(geometry.EVENT_YEARS)
HIGHLIGHTS = (1997, 2015, 2023)
HORIZON_DAYS = 20
RNG_SEED = 20260803
N_BOOTSTRAP = 10000

INDEX_CSV = geometry.INPUT_INDEX
BUDGET_CSV = ROOT / "data/derived/research_2026/soda3_warm_heat_160e_180e_budget.csv"
MONTHLY_CSV = ROOT / "data/derived/research_2026/enso_type_coupling_monthly_1982_2023.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_reservoir_release_coupling"
PDF_DIR = ROOT / "output/pdf"
FEATURE_CSV = DERIVED / "soda3_reservoir_release_coupling_features.csv"
HIGH_RISK_CSV = DERIVED / "soda3_reservoir_release_wind20d_risk.csv"
MONTHLY_RISK_CSV = DERIVED / "soda3_reservoir_release_monthly_risk.csv"
PREDICTION_CSV = DERIVED / "soda3_reservoir_release_coupling_loeo_predictions.csv"
SKILL_CSV = DERIVED / "soda3_reservoir_release_coupling_skill.csv"
BOOTSTRAP_CSV = DERIVED / "soda3_reservoir_release_coupling_bootstrap.csv"
COEFFICIENT_CSV = DERIVED / "soda3_reservoir_release_coupling_coefficients.csv"
EVENT_CSV = DERIVED / "soda3_reservoir_release_coupling_event_timeline.csv"
SENSITIVITY_CSV = DERIVED / "soda3_reservoir_release_onset_sensitivity.csv"
LAG_RISK_CSV = DERIVED / "soda3_reservoir_release_lag_scan_risk.csv"
LAG_PREDICTION_CSV = DERIVED / "soda3_reservoir_release_lag_scan_loeo_predictions.csv"
LAG_SKILL_CSV = DERIVED / "soda3_reservoir_release_lag_scan_skill.csv"
LAG_BOOTSTRAP_CSV = DERIVED / "soda3_reservoir_release_lag_scan_bootstrap.csv"
LAG_COEFFICIENT_CSV = DERIVED / "soda3_reservoir_release_lag_scan_coefficients.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_reservoir_release_coupling_diagnostics.json"
FIGURE_PNG = OUT / "soda3_reservoir_release_coupling.png"
FIGURE_PDF = PDF_DIR / "soda3_reservoir_release_coupling.pdf"
REPORT_MD = OUT / "SODA3_RESERVOIR_RELEASE_COUPLING_CN.md"


BASE_FEATURES = [
    "season_sin",
    "season_cos",
    "ohc300_positive_total_pj_m_15day",
    "ohc300_positive_total_pj_m_change15day",
]
MODEL_FEATURES = {
    "heat_state": BASE_FEATURES,
    "heat_plus_release": BASE_FEATURES + ["reservoir_release_15day_pw"],
    "heat_plus_wind_memory": BASE_FEATURES + ["prior_wind_memory_15day_nm2"],
    "heat_plus_release_and_wind": BASE_FEATURES
    + ["reservoir_release_15day_pw", "prior_wind_memory_15day_nm2"],
}
LAG_WINDOWS = ((0, 20), (20, 40), (40, 60))
LAG_MODEL_FEATURES = {
    "heat_state": BASE_FEATURES,
    **{
        f"heat_plus_release_{lower}_{upper}d": BASE_FEATURES
        + [f"reservoir_release_{lower}_{upper}d_pw"]
        for lower, upper in LAG_WINDOWS
    },
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.4,
            "axes.titlesize": 9.7,
            "axes.labelsize": 8.7,
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.4,
            "legend.fontsize": 6.9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_features() -> tuple[pd.DataFrame, dict[str, float]]:
    index = geometry.load_indices(INDEX_CSV)
    budget = pd.read_csv(BUDGET_CSV, parse_dates=["time"])
    selected = budget[
        ["time", "year", "box_h20_tendency_trailing5_pw"]
    ].copy()
    frame = index.merge(selected, on=["time", "year"], how="inner", validate="one_to_one")
    expected = budget[["time", "year"]].drop_duplicates().shape[0]
    if len(frame) != expected:
        raise ValueError(f"OHC-index/budget alignment mismatch: {len(frame)} != {expected}")
    pieces = []
    for year, event in frame.groupby("year", sort=True):
        current = event.sort_values("time").copy()
        current["reservoir_release_pw"] = -current["box_h20_tendency_trailing5_pw"]
        current["reservoir_release_15day_pw"] = (
            current["reservoir_release_pw"].rolling(3, min_periods=3).mean()
        )
        current["prior_wind_memory_15day_nm2"] = (
            current["taux_central_180_220e_anom_nm2"]
            .shift(1)
            .rolling(3, min_periods=3)
            .mean()
        )
        current["prior_wind_latest_source_time"] = current["time"].shift(1)
        pieces.append(current)
    output = pd.concat(pieces, ignore_index=True).sort_values(["year", "time"])
    lag = (
        output["time"] - pd.to_datetime(output["prior_wind_latest_source_time"])
    ).dt.days.dropna()
    if not lag.between(4, 6).all():
        raise ValueError("Prior wind memory is not strictly lagged")
    intervals = output.groupby("year")["time"].diff().dt.days.dropna()
    return output, {
        "n_events": int(output["year"].nunique()),
        "n_pentads": len(output),
        "interval_min_days": float(intervals.min()),
        "interval_median_days": float(intervals.median()),
        "interval_max_days": float(intervals.max()),
        "prior_wind_lag_median_days": float(lag.median()),
    }


def build_high_frequency_risk(features: pd.DataFrame) -> pd.DataFrame:
    full_index = geometry.load_indices(INDEX_CSV)
    onsets = {
        int(year): geometry.coupling_onset(event)
        for year, event in full_index.groupby("year", sort=True)
    }
    rows = []
    for year, event in features.groupby("year", sort=True):
        onset = onsets[int(year)]
        risk = event.loc[event["month"].ge(2)].copy()
        if onset is not None:
            risk = risk.loc[risk["time"] < onset]
            lead = (onset - risk["time"]).dt.days
            risk["outcome_value"] = lead.between(1, HORIZON_DAYS).astype(int)
            risk["days_to_onset"] = lead
        else:
            risk["outcome_value"] = 0
            risk["days_to_onset"] = np.nan
        risk["outcome"] = "wind20d"
        risk["event_onset_date"] = pd.NaT if onset is None else onset
        rows.append(risk)
    output = pd.concat(rows, ignore_index=True)
    required = sorted({item for values in MODEL_FEATURES.values() for item in values})
    output = output.dropna(subset=required + ["outcome_value"])
    if output.groupby("year")["outcome_value"].max().sum() < 5:
        raise ValueError("Too few high-frequency wind-onset events")
    return output.sort_values(["year", "time"]).reset_index(drop=True)


def monthly_outcome_flags(monthly: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "monthly_wind": monthly["u850_cwp_anom_ms"].gt(0.0),
        "monthly_convection": monthly["olr_cp_anom_wm2"].lt(0.0),
        "monthly_joint": monthly["u850_cwp_anom_ms"].gt(0.0)
        & monthly["olr_cp_anom_wm2"].lt(0.0),
    }


def build_monthly_risk(features: pd.DataFrame) -> pd.DataFrame:
    monthly = pd.read_csv(MONTHLY_CSV, parse_dates=["time"])
    monthly = monthly.loc[
        monthly["year"].isin(EVENTS) & monthly["month"].between(3, 6)
    ].copy()
    flags = monthly_outcome_flags(monthly)
    rows = []
    for outcome, flag in flags.items():
        current_monthly = monthly.copy()
        current_monthly["_active"] = flag.to_numpy(dtype=bool)
        first_lookup = (
            current_monthly.loc[current_monthly["_active"]]
            .groupby("year")["month"]
            .min()
            .to_dict()
        )
        for year in EVENTS:
            event_features = features.loc[features["year"].eq(year)].sort_values("time")
            event_months = current_monthly.loc[current_monthly["year"].eq(year)].sort_values("month")
            onset_month = first_lookup.get(year)
            for month_row in event_months.itertuples():
                month = int(month_row.month)
                if onset_month is not None and month > int(onset_month):
                    continue
                forecast_start = pd.Timestamp(year=year, month=month, day=1)
                available = event_features.loc[event_features["time"] < forecast_start]
                if available.empty:
                    continue
                snapshot = available.iloc[-1]
                row = snapshot.to_dict()
                row.update(
                    {
                        "time": forecast_start,
                        "snapshot_time": pd.Timestamp(snapshot["time"]),
                        "year": int(year),
                        "month": month,
                        "outcome": outcome,
                        "outcome_value": int(
                            onset_month is not None and month == int(onset_month)
                        ),
                        "event_onset_date": (
                            pd.NaT
                            if onset_month is None
                            else pd.Timestamp(year=year, month=int(onset_month), day=15)
                        ),
                    }
                )
                angle = 2.0 * np.pi * forecast_start.dayofyear / 365.25
                row["season_sin"] = np.sin(angle)
                row["season_cos"] = np.cos(angle)
                rows.append(row)
    output = pd.DataFrame(rows)
    required = sorted({item for values in MODEL_FEATURES.values() for item in values})
    output = output.dropna(subset=required + ["outcome_value"])
    for outcome, group in output.groupby("outcome"):
        if group.groupby("year")["outcome_value"].max().sum() < 5:
            raise ValueError(f"Too few monthly onset events for {outcome}")
        if not (pd.to_datetime(group["snapshot_time"]) < pd.to_datetime(group["time"])).all():
            raise ValueError(f"Monthly predictor leakage for {outcome}")
    return output.sort_values(["outcome", "year", "time"]).reset_index(drop=True)


def add_release_lag_windows(
    monthly_risk: pd.DataFrame, features: pd.DataFrame
) -> pd.DataFrame:
    """Add three pre-declared non-overlapping release windows before month start."""
    output = monthly_risk.copy()
    for lower, upper in LAG_WINDOWS:
        values = []
        counts = []
        for row in output.itertuples():
            event = features.loc[features["year"].eq(row.year)]
            start = pd.Timestamp(row.time) - pd.Timedelta(days=upper)
            end = pd.Timestamp(row.time) - pd.Timedelta(days=lower)
            selected = event.loc[
                event["time"].ge(start) & event["time"].lt(end),
                "reservoir_release_pw",
            ].dropna()
            values.append(float(selected.mean()) if not selected.empty else np.nan)
            counts.append(len(selected))
        output[f"reservoir_release_{lower}_{upper}d_pw"] = values
        output[f"reservoir_release_{lower}_{upper}d_n_pentads"] = counts
    required = sorted(
        {feature for model in LAG_MODEL_FEATURES.values() for feature in model}
    )
    output = output.dropna(subset=required).copy()
    for lower, upper in LAG_WINDOWS:
        if output[f"reservoir_release_{lower}_{upper}d_n_pentads"].lt(1).any():
            raise ValueError(f"Empty release lag window {lower}-{upper} days")
    return output.sort_values(["outcome", "year", "time"]).reset_index(drop=True)


def event_weights(years: pd.Series) -> np.ndarray:
    counts = years.value_counts()
    weights = years.map(lambda item: 1.0 / counts.loc[item]).to_numpy(dtype=float)
    return weights / np.mean(weights)


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "logistic",
                LogisticRegression(
                    C=1.0,
                    penalty="l2",
                    solver="lbfgs",
                    max_iter=5000,
                    random_state=RNG_SEED,
                ),
            ),
        ]
    )


def loeo(
    risk: pd.DataFrame,
    model_features: dict[str, list[str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    models = MODEL_FEATURES if model_features is None else model_features
    prediction_rows = []
    coefficient_rows = []
    for outcome, outcome_data in risk.groupby("outcome", sort=False):
        for held_year in sorted(outcome_data["year"].unique()):
            train = outcome_data.loc[outcome_data["year"].ne(held_year)]
            test = outcome_data.loc[outcome_data["year"].eq(held_year)]
            weights = event_weights(train["year"])
            for model_name, current_features in models.items():
                model = make_model()
                model.fit(
                    train[current_features].to_numpy(dtype=float),
                    train["outcome_value"].to_numpy(dtype=int),
                    logistic__sample_weight=weights,
                )
                probability = model.predict_proba(
                    test[current_features].to_numpy(dtype=float)
                )[:, 1]
                for row, value in zip(test.itertuples(), probability, strict=True):
                    prediction_rows.append(
                        {
                            "outcome": outcome,
                            "time": row.time,
                            "year": int(row.year),
                            "model": model_name,
                            "observed": int(row.outcome_value),
                            "probability": float(value),
                        }
                    )
                coefficients = model.named_steps["logistic"].coef_[0]
                for feature, coefficient in zip(
                    current_features, coefficients, strict=True
                ):
                    coefficient_rows.append(
                        {
                            "outcome": outcome,
                            "held_year": int(held_year),
                            "model": model_name,
                            "feature": feature,
                            "standardized_logit_coefficient": float(coefficient),
                        }
                    )
    return pd.DataFrame(prediction_rows), pd.DataFrame(coefficient_rows)


def score_predictions(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event_rows = []
    skill_rows = []
    for (outcome, model_name), group in predictions.groupby(["outcome", "model"]):
        weights = event_weights(group["year"])
        observed = group["observed"].to_numpy(dtype=int)
        probability = group["probability"].to_numpy(dtype=float)
        event_mse = []
        for year, event in group.groupby("year"):
            mse = float(
                np.mean(
                    (event["probability"].to_numpy() - event["observed"].to_numpy())
                    ** 2
                )
            )
            event_mse.append(mse)
            event_rows.append(
                {
                    "outcome": outcome,
                    "model": model_name,
                    "year": int(year),
                    "event_brier": mse,
                }
            )
        skill_rows.append(
            {
                "outcome": outcome,
                "model": model_name,
                "n_events": int(group["year"].nunique()),
                "n_forecasts": len(group),
                "event_equal_brier": float(np.mean(event_mse)),
                "event_equal_brier_skill_vs_climatology": float(
                    1.0
                    - np.mean(event_mse)
                    / np.average(
                        (observed - np.average(observed, weights=weights)) ** 2,
                        weights=weights,
                    )
                ),
                "event_weighted_auc": float(
                    roc_auc_score(observed, probability, sample_weight=weights)
                ),
                "event_weighted_logloss": float(
                    log_loss(
                        observed,
                        probability,
                        sample_weight=weights,
                        labels=[0, 1],
                    )
                ),
            }
        )
    event_table = pd.DataFrame(event_rows)
    baseline = event_table.loc[
        event_table["model"].eq("heat_state"),
        ["outcome", "year", "event_brier"],
    ].rename(columns={"event_brier": "baseline_event_brier"})
    event_table = event_table.merge(
        baseline, on=["outcome", "year"], validate="many_to_one"
    )
    event_table["delta_brier_vs_heat_state"] = (
        event_table["event_brier"] - event_table["baseline_event_brier"]
    )

    rng = np.random.default_rng(RNG_SEED)
    bootstrap_rows = []
    for (outcome, model_name), group in event_table.loc[
        ~event_table["model"].eq("heat_state")
    ].groupby(["outcome", "model"]):
        values = group["delta_brier_vs_heat_state"].to_numpy(dtype=float)
        draws = np.empty(N_BOOTSTRAP)
        for index in range(N_BOOTSTRAP):
            selected = rng.integers(0, len(values), len(values))
            draws[index] = float(np.mean(values[selected]))
        bootstrap_rows.append(
            {
                "outcome": outcome,
                "model": model_name,
                "n_events": len(values),
                "mean_delta_brier_vs_heat_state": float(np.mean(values)),
                "ci_low": float(np.quantile(draws, 0.025)),
                "ci_high": float(np.quantile(draws, 0.975)),
                "events_improved": int(np.sum(values < 0.0)),
                "event_improvement_fraction": float(np.mean(values < 0.0)),
            }
        )
    return pd.DataFrame(skill_rows), pd.DataFrame(bootstrap_rows), event_table


def first_positive_run(
    event: pd.DataFrame, column: str, run_length: int
) -> pd.Timestamp | None:
    current = event.loc[event["month"].ge(2)].sort_values("time")
    values = current[column].to_numpy(dtype=float)
    times = pd.DatetimeIndex(current["time"])
    for index in range(len(values) - run_length + 1):
        window = values[index : index + run_length]
        if np.isfinite(window).all() and np.all(window > 0.0):
            return pd.Timestamp(times[index])
    return None


def build_event_timeline(
    features: pd.DataFrame, monthly: pd.DataFrame, run_length: int = 3
) -> pd.DataFrame:
    full_index = geometry.load_indices(INDEX_CSV)
    flags = monthly_outcome_flags(monthly)
    joint = monthly.copy()
    joint["_active"] = flags["monthly_joint"].to_numpy(dtype=bool)
    convection = monthly.copy()
    convection["_active"] = flags["monthly_convection"].to_numpy(dtype=bool)
    rows = []
    for year in EVENTS:
        event = features.loc[features["year"].eq(year)]
        release_onset = first_positive_run(
            event, "reservoir_release_15day_pw", run_length
        )
        wind_onset = geometry.coupling_onset(
            full_index.loc[full_index["year"].eq(year)]
        )
        current_joint = joint.loc[joint["year"].eq(year) & joint["_active"]]
        current_convection = convection.loc[
            convection["year"].eq(year) & convection["_active"]
        ]
        joint_onset = (
            None
            if current_joint.empty
            else pd.Timestamp(
                year=year, month=int(current_joint["month"].min()), day=15
            )
        )
        convection_onset = (
            None
            if current_convection.empty
            else pd.Timestamp(
                year=year, month=int(current_convection["month"].min()), day=15
            )
        )
        rows.append(
            {
                "year": year,
                "release_onset_date": pd.NaT if release_onset is None else release_onset,
                "soda3_westerly_onset_date": pd.NaT if wind_onset is None else wind_onset,
                "monthly_convection_onset_midpoint": (
                    pd.NaT if convection_onset is None else convection_onset
                ),
                "monthly_joint_onset_midpoint": pd.NaT if joint_onset is None else joint_onset,
                "release_lead_to_wind_days": (
                    np.nan
                    if release_onset is None or wind_onset is None
                    else float((wind_onset - release_onset).days)
                ),
                "release_lead_to_convection_days": (
                    np.nan
                    if release_onset is None or convection_onset is None
                    else float((convection_onset - release_onset).days)
                ),
                "release_lead_to_joint_days": (
                    np.nan
                    if release_onset is None or joint_onset is None
                    else float((joint_onset - release_onset).days)
                ),
            }
        )
    return pd.DataFrame(rows)


def onset_sensitivity(features: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run_length in (2, 3, 4):
        table = build_event_timeline(features, monthly, run_length=run_length)
        for target in ("wind", "convection", "joint"):
            values = table[f"release_lead_to_{target}_days"].dropna().to_numpy(dtype=float)
            positive = int(np.sum(values > 0.0))
            rows.append(
                {
                    "release_run_length": run_length,
                    "target": target,
                    "n_events": len(values),
                    "median_lead_days": float(np.median(values)),
                    "positive_lead_events": positive,
                    "positive_lead_fraction": float(positive / len(values)),
                    "sign_test_one_sided_p": float(
                        binomtest(
                            positive, len(values), 0.5, alternative="greater"
                        ).pvalue
                    ),
                }
            )
    return pd.DataFrame(rows)


def day_of_year(series: pd.Series) -> np.ndarray:
    return pd.to_datetime(series).dt.dayofyear.to_numpy(dtype=float)


def plot_result(
    features: pd.DataFrame,
    timeline: pd.DataFrame,
    bootstrap: pd.DataFrame,
    coefficients: pd.DataFrame,
    lag_bootstrap: pd.DataFrame,
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.7, 8.3))
    figure.subplots_adjust(
        left=0.085, right=0.975, bottom=0.11, top=0.91, wspace=0.27, hspace=0.33
    )

    ax = axes[0, 0]
    ordered = timeline.sort_values("year").reset_index(drop=True)
    y = np.arange(len(ordered))
    markers = {
        "release_onset_date": ("Reservoir release", "o", "#2C7FB8"),
        "soda3_westerly_onset_date": ("Persistent westerlies", "D", "#B7352D"),
        "monthly_convection_onset_midpoint": ("OLR convection", "s", "#E58C2B"),
        "monthly_joint_onset_midpoint": ("Wind + OLR", "*", "#6A3D9A"),
    }
    for column, (label, marker, color) in markers.items():
        values = day_of_year(ordered[column])
        valid = np.isfinite(values)
        ax.scatter(
            values[valid],
            y[valid],
            marker=marker,
            s=31 if marker != "*" else 52,
            color=color,
            edgecolor="white",
            linewidth=0.45,
            label=label,
            zorder=4,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(ordered["year"].astype(str))
    for label in ax.get_yticklabels():
        if int(label.get_text()) in HIGHLIGHTS:
            label.set_fontweight("bold")
    ax.set_xlim(30, 200)
    ax.set_xticks([32, 60, 91, 121, 152, 182])
    ax.set_xticklabels(["Feb", "Mar", "Apr", "May", "Jun", "Jul"])
    ax.invert_yaxis()
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)
    ax.set_title("(a) Release often precedes wind, but not always convection", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=2, loc="lower right")

    ax = axes[0, 1]
    outcome_order = ["wind20d", "monthly_wind", "monthly_convection", "monthly_joint"]
    outcome_labels = ["Wind in 20 d", "Monthly wind", "Monthly OLR", "Wind + OLR"]
    model_order = [
        "heat_plus_release",
        "heat_plus_wind_memory",
        "heat_plus_release_and_wind",
    ]
    model_labels = ["+ release", "+ wind memory", "+ both"]
    model_colors = ["#2C7FB8", "#E58C2B", "#6A3D9A"]
    x = np.arange(len(outcome_order))
    width = 0.23
    lookup = bootstrap.set_index(["outcome", "model"])
    for index, (model, label, color) in enumerate(
        zip(model_order, model_labels, model_colors, strict=True)
    ):
        rows = lookup.loc[[(outcome, model) for outcome in outcome_order]]
        positions = x + (index - 1) * width
        mean = rows["mean_delta_brier_vs_heat_state"].to_numpy(dtype=float)
        low = rows["ci_low"].to_numpy(dtype=float)
        high = rows["ci_high"].to_numpy(dtype=float)
        ax.bar(positions, mean, width, color=color, label=label)
        ax.errorbar(
            positions,
            mean,
            yerr=[mean - low, high - mean],
            fmt="none",
            ecolor="#222222",
            capsize=2.5,
            lw=0.9,
        )
    ax.axhline(0.0, color="#222222", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(outcome_labels, rotation=15, ha="right")
    ax.set_ylabel("Event-mean Brier change vs heat-state base")
    ax.set_title("(b) Does release add cross-event onset skill?", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3, loc="lower left")
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    ax = axes[1, 0]
    monthly_outcomes = ["monthly_wind", "monthly_convection", "monthly_joint"]
    monthly_labels = ["Monthly wind", "Monthly OLR", "Wind + OLR"]
    lag_colors = {
        "monthly_wind": "#B7352D",
        "monthly_convection": "#E58C2B",
        "monthly_joint": "#6A3D9A",
    }
    lag_lookup = lag_bootstrap.set_index(["outcome", "model"])
    lag_x = np.arange(len(LAG_WINDOWS))
    offsets = [-0.10, 0.0, 0.10]
    for outcome, label, offset in zip(
        monthly_outcomes, monthly_labels, offsets, strict=True
    ):
        keys = [
            (outcome, f"heat_plus_release_{lower}_{upper}d")
            for lower, upper in LAG_WINDOWS
        ]
        rows = lag_lookup.loc[keys]
        position = lag_x + offset
        mean = rows["mean_delta_brier_vs_heat_state"].to_numpy(dtype=float)
        low = rows["ci_low"].to_numpy(dtype=float)
        high = rows["ci_high"].to_numpy(dtype=float)
        ax.errorbar(
            position,
            mean,
            yerr=[mean - low, high - mean],
            fmt="o-",
            color=lag_colors[outcome],
            capsize=3,
            ms=4.5,
            lw=1.1,
            label=label,
        )
    ax.axhline(0.0, color="#222222", lw=0.8)
    ax.set_xticks(lag_x)
    ax.set_xticklabels(["0-20 d", "20-40 d", "40-60 d"])
    ax.set_ylabel("Event-mean Brier change vs heat-state base")
    ax.set_title("(c) A 20-40 d candidate window appears, but CIs cross zero", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    ax = axes[1, 1]
    colors = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}
    for year in HIGHLIGHTS:
        event = features.loc[features["year"].eq(year)].sort_values("time")
        day = (event["time"] - pd.Timestamp(year=year, month=1, day=1)).dt.days
        ax.plot(
            day,
            event["reservoir_release_15day_pw"],
            color=colors[year],
            lw=1.35,
            label=str(year),
        )
        timeline_row = timeline.loc[timeline["year"].eq(year)].iloc[0]
        wind = timeline_row["soda3_westerly_onset_date"]
        joint = timeline_row["monthly_joint_onset_midpoint"]
        if pd.notna(wind):
            ax.scatter(
                (pd.Timestamp(wind) - pd.Timestamp(year=year, month=1, day=1)).days,
                0.0,
                marker="D",
                s=26,
                color=colors[year],
                edgecolor="white",
                linewidth=0.4,
                zorder=5,
            )
        if pd.notna(joint):
            ax.scatter(
                (pd.Timestamp(joint) - pd.Timestamp(year=year, month=1, day=1)).days,
                0.0,
                marker="*",
                s=55,
                color=colors[year],
                edgecolor="white",
                linewidth=0.4,
                zorder=5,
            )
    ax.axhline(0.0, color="#222222", lw=0.8)
    ax.set_xticks([0, 31, 59, 90, 120, 151, 181])
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"])
    ax.set_ylabel("15-day western-reservoir release (PW)")
    ax.set_title("(d) Same release sign does not guarantee atmospheric closure", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    figure.suptitle(
        "From SODA3 western-reservoir release to atmospheric coupling",
        fontsize=13.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "Positive release = declining T>20C heat content in 5S-5N, 0-300 m, 160E-180E. Monthly targets use pre-month predictors only; all scores are leave-one-event-out.",
        ha="center",
        fontsize=7.0,
        color="#555555",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def row_for(frame: pd.DataFrame, outcome: str, model: str) -> pd.Series:
    return frame.loc[frame["outcome"].eq(outcome) & frame["model"].eq(model)].iloc[0]


def main() -> int:
    features, feature_qa = load_features()
    high_risk = build_high_frequency_risk(features)
    monthly_risk = build_monthly_risk(features)
    risk = pd.concat([high_risk, monthly_risk], ignore_index=True, sort=False)
    predictions, coefficients = loeo(risk)
    skill, bootstrap, event_scores = score_predictions(predictions)
    lag_risk = add_release_lag_windows(monthly_risk, features)
    lag_predictions, lag_coefficients = loeo(
        lag_risk, model_features=LAG_MODEL_FEATURES
    )
    lag_skill, lag_bootstrap, lag_event_scores = score_predictions(lag_predictions)

    monthly = pd.read_csv(MONTHLY_CSV, parse_dates=["time"])
    monthly = monthly.loc[
        monthly["year"].isin(EVENTS) & monthly["month"].between(3, 6)
    ].copy()
    timeline = build_event_timeline(features, monthly)
    sensitivity = onset_sensitivity(features, monthly)

    release_rows = []
    for outcome in ("wind20d", "monthly_wind", "monthly_convection", "monthly_joint"):
        for model in ("heat_plus_release", "heat_plus_release_and_wind"):
            values = coefficients.loc[
                coefficients["outcome"].eq(outcome)
                & coefficients["model"].eq(model)
                & coefficients["feature"].eq("reservoir_release_15day_pw"),
                "standardized_logit_coefficient",
            ].to_numpy(dtype=float)
            release_rows.append(
                {
                    "outcome": outcome,
                    "model": model,
                    "median_standardized_release_coefficient": float(np.median(values)),
                    "positive_fold_fraction": float(np.mean(values > 0.0)),
                }
            )
    release_coefficient_summary = pd.DataFrame(release_rows)
    lag_release_rows = []
    for outcome in ("monthly_wind", "monthly_convection", "monthly_joint"):
        for lower, upper in LAG_WINDOWS:
            model = f"heat_plus_release_{lower}_{upper}d"
            feature = f"reservoir_release_{lower}_{upper}d_pw"
            values = lag_coefficients.loc[
                lag_coefficients["outcome"].eq(outcome)
                & lag_coefficients["model"].eq(model)
                & lag_coefficients["feature"].eq(feature),
                "standardized_logit_coefficient",
            ].to_numpy(dtype=float)
            lag_release_rows.append(
                {
                    "outcome": outcome,
                    "window_days": f"{lower}-{upper}",
                    "median_standardized_release_coefficient": float(np.median(values)),
                    "positive_fold_fraction": float(np.mean(values > 0.0)),
                }
            )
    lag_release_coefficient_summary = pd.DataFrame(lag_release_rows)

    diagnostics = {
        "events": list(EVENTS),
        "release_definition": "- trailing 5-day tendency of T>20C heat content in 5S-5N, 0-300m, 160E-180E; 15-day rolling mean",
        "targets": {
            "wind20d": "persistent SODA3 central-Pacific westerly onset within 20 days",
            "monthly_wind": "first March-June month with ERA5 u850 anomaly > 0",
            "monthly_convection": "first March-June month with CPC OLR anomaly < 0",
            "monthly_joint": "first March-June month with both conditions",
        },
        "quality_control": feature_qa,
        "release_coefficients": release_coefficient_summary.to_dict(orient="records"),
        "lag_windows_days": [list(item) for item in LAG_WINDOWS],
        "lag_release_coefficients": lag_release_coefficient_summary.to_dict(
            orient="records"
        ),
        "limits": [
            "SODA3 wind stress is an atmospheric forcing field, not an independent atmosphere model response.",
            "Monthly OLR timing is represented by the midpoint of the first qualifying month.",
            "LOEO is cross-event hindcast validation, not an operational forecast demonstration.",
        ],
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    features.to_csv(FEATURE_CSV, index=False)
    high_risk.to_csv(HIGH_RISK_CSV, index=False)
    monthly_risk.to_csv(MONTHLY_RISK_CSV, index=False)
    predictions.to_csv(PREDICTION_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    bootstrap.to_csv(BOOTSTRAP_CSV, index=False)
    coefficients.to_csv(COEFFICIENT_CSV, index=False)
    timeline.to_csv(EVENT_CSV, index=False)
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)
    lag_risk.to_csv(LAG_RISK_CSV, index=False)
    lag_predictions.to_csv(LAG_PREDICTION_CSV, index=False)
    lag_skill.to_csv(LAG_SKILL_CSV, index=False)
    lag_bootstrap.to_csv(LAG_BOOTSTRAP_CSV, index=False)
    lag_coefficients.to_csv(LAG_COEFFICIENT_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    plot_result(features, timeline, bootstrap, coefficients, lag_bootstrap)

    wind_release = row_for(bootstrap, "wind20d", "heat_plus_release")
    wind_both = row_for(bootstrap, "wind20d", "heat_plus_release_and_wind")
    convection_release = row_for(
        bootstrap, "monthly_convection", "heat_plus_release"
    )
    joint_release = row_for(bootstrap, "monthly_joint", "heat_plus_release")
    joint_both = row_for(
        bootstrap, "monthly_joint", "heat_plus_release_and_wind"
    )
    wind_skill = row_for(skill, "wind20d", "heat_plus_release")
    joint_skill = row_for(skill, "monthly_joint", "heat_plus_release")
    onset3 = sensitivity.loc[
        sensitivity["release_run_length"].eq(3)
    ].set_index("target")
    lag_convection = row_for(
        lag_bootstrap,
        "monthly_convection",
        "heat_plus_release_20_40d",
    )
    lag_joint = row_for(
        lag_bootstrap,
        "monthly_joint",
        "heat_plus_release_20_40d",
    )
    immediate_joint = row_for(
        lag_bootstrap,
        "monthly_joint",
        "heat_plus_release_0_20d",
    )
    immediate_convection_coefficient = release_coefficient_summary.loc[
        release_coefficient_summary["outcome"].eq("monthly_convection")
        & release_coefficient_summary["model"].eq("heat_plus_release")
    ].iloc[0]
    lag_convection_coefficient = lag_release_coefficient_summary.loc[
        lag_release_coefficient_summary["outcome"].eq("monthly_convection")
        & lag_release_coefficient_summary["window_days"].eq("20-40")
    ].iloc[0]

    report = rf"""# SODA3西部储库释热到大气接通的事件留一检验

## 问题与定义

本阶段不再增加外海盆指标，只检验一个海洋量：160°E—180°E、5°S—5°N、0—300 m内20°C以上暖层热含量的上一五日变化率。定义

\[
R_{{release}}=-\frac{{dH_{{20}}}}{{dt}},
\]

正值表示西部储库正在释热。预测量使用15日滑动平均；月尺度目标只使用月初以前的最后一个五日资料。

## 未来20天持续西风

- 在季节＋总暖量基准上加入释热量，事件平均Brier变化 `{wind_release['mean_delta_brier_vs_heat_state']:+.3f}`，95%区间 `[{wind_release['ci_low']:+.3f}, {wind_release['ci_high']:+.3f}]`，`{int(wind_release['events_improved'])}/13` 次事件改善。
- 加入释热后的LOEO AUC为 `{wind_skill['event_weighted_auc']:.2f}`。
- 同时控制严格滞后一五日的风记忆后，Brier变化 `{wind_both['mean_delta_brier_vs_heat_state']:+.3f}`，区间 `[{wind_both['ci_low']:+.3f}, {wind_both['ci_high']:+.3f}]`。

## OLR与完整海气接通

- 对首次OLR负异常月，加入释热的Brier变化 `{convection_release['mean_delta_brier_vs_heat_state']:+.3f}`，区间 `[{convection_release['ci_low']:+.3f}, {convection_release['ci_high']:+.3f}]`。
- 对首次“u850西风＋OLR负异常”月份，加入释热的Brier变化 `{joint_release['mean_delta_brier_vs_heat_state']:+.3f}`，区间 `[{joint_release['ci_low']:+.3f}, {joint_release['ci_high']:+.3f}]`，LOEO AUC `{joint_skill['event_weighted_auc']:.2f}`。
- 再控制风记忆后，完整接通的Brier变化 `{joint_both['mean_delta_brier_vs_heat_state']:+.3f}`，区间 `[{joint_both['ci_low']:+.3f}, {joint_both['ci_high']:+.3f}]`。

### 预先限定的滞后窗口扫描

- 20—40天前的释热对OLR对流启动给出候选改善：Brier变化 `{lag_convection['mean_delta_brier_vs_heat_state']:+.3f}`，区间 `[{lag_convection['ci_low']:+.3f}, {lag_convection['ci_high']:+.3f}]`，`{int(lag_convection['events_improved'])}/13` 次改善。
- 同一窗口对完整风＋OLR接通的变化只有 `{lag_joint['mean_delta_brier_vs_heat_state']:+.3f}`，区间 `[{lag_joint['ci_low']:+.3f}, {lag_joint['ci_high']:+.3f}]`。
- 0—20天前的释热反而使完整接通误差增加 `{immediate_joint['mean_delta_brier_vs_heat_state']:+.3f}`，区间 `[{immediate_joint['ci_low']:+.3f}, {immediate_joint['ci_high']:+.3f}]`。这表明海洋释热与完整大气接通并非同步过程。
- 对OLR目标，即时15日释热系数在 `{100*immediate_convection_coefficient['positive_fold_fraction']:.0f}%` 的留一折中为正，而20—40天窗口在 `{100*lag_convection_coefficient['positive_fold_fraction']:.0f}%` 的折中为正，说明系数符号随物理滞后发生反转。
- 三个窗口都属于预设的探索性分布滞后检验；候选20—40天窗口的区间仍跨零，不能当作已确定时滞。

## 时间顺序

- 以连续3个五日时次的15日释热平均为正定义“持续释热”，其领先持续西风的中位数为 `{onset3.loc['wind', 'median_lead_days']:.0f}` 天，`{int(onset3.loc['wind', 'positive_lead_events'])}/{int(onset3.loc['wind', 'n_events'])}` 次方向为正。
- 对OLR对流接通，中位领先 `{onset3.loc['convection', 'median_lead_days']:.0f}` 天；对风＋OLR完整接通，中位领先 `{onset3.loc['joint', 'median_lead_days']:.0f}` 天。
- 这些日期是描述性事件节点；真正的预测判断以上面的LOEO Brier变化和区间为准。

三次关键事件进一步说明释热与大气接通不是同一个节点：按连续3个五日时次的定义，1997和2015的持续释热分别比风＋OLR接通晚约14天和10天；2023却早约103天。也就是说，1997/2015中大气反馈已在强持续释热形成前接上，而2023中海洋很早进入释热状态，大气仍延迟三个多月。

## 当前结论

西部储库释热的方向对未来20天西风在所有留一折中均为正，但它没有稳定降低跨事件预测误差；对完整风＋OLR接通也没有独立增益。因此，它目前是**海洋释放阶段指标**，还不是完整海气耦合预测指标。结果支持“两道门”：第一道是暖量释放和动力启动，第二道是对流在合适的20—40天候选滞后内组织并与西风共位。第二道门仍未被当前单一热含量量闭合，这正是2023与1997/2015分开的地方。
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
