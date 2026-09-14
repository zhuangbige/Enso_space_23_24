#!/usr/bin/env python3
"""Test whether SODA3 heat position adds skill for coupling-onset timing.

The unit of validation is an ENSO event, not a pentad.  The primary outcome
is the first central-Pacific westerly episode after 1 March that starts with
two positive-stress pentads and contains at least four positive pentads in
the following 30 days.  Models are evaluated by leave-one-event-out (LOEO)
validation, with event-balanced scores and event bootstrap uncertainty.

The baseline model uses season and total positive 0-300 m OHC.  Competing
models add one spatial descriptor at a time: the fraction of positive heat
east of 140W, the heat centroid, or the east-minus-west OHC gradient.  A
separate matched-pentad analysis asks whether pairs with similar date and
total heat but different heat position subsequently develop different
westerly stress.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_soda3_ohc_geometry_plot_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
INPUT_INDEX = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_5day_ohc_geometry_coupling_13events_jan_sep.csv"
)
INPUT_PROFILES = (
    ROOT
    / "data/interim/research_2026/soda3_5day_ohc_geometry/"
    "soda3_5day_ohc_profiles_13events_1982_2023_jan_sep.csv.gz"
)
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_5day_ohc_geometry_coupling"
PDF_DIR = ROOT / "output/pdf"

EVENT_YEARS = (
    1982,
    1986,
    1991,
    1994,
    1997,
    2002,
    2004,
    2006,
    2009,
    2015,
    2018,
    2019,
    2023,
)
PRIMARY_HORIZON_DAYS = 20
MIN_POSITIVE_HEAT_PJ_M = 0.25
ONSET_START_MONTH = 3
RISK_START_MONTH = 2
ONSET_POSITIVE_COUNT = 4
ONSET_WINDOW_PENTADS = 6
DURABLE_POSITIVE_COUNT = 8
DURABLE_WINDOW_PENTADS = 12
RNG_SEED = 20260802
N_BOOTSTRAP = 10000

EVENT_SUMMARY_CSV = DERIVED / "soda3_5day_ohc_geometry_event_onsets.csv"
RISK_SET_CSV = DERIVED / "soda3_5day_ohc_geometry_onset_risk_set.csv"
LOEO_CSV = DERIVED / "soda3_5day_ohc_geometry_loeo_predictions.csv"
COEFFICIENT_CSV = DERIVED / "soda3_5day_ohc_geometry_loeo_coefficients.csv"
SKILL_CSV = DERIVED / "soda3_5day_ohc_geometry_model_skill.csv"
DURABLE_LOEO_CSV = DERIVED / "soda3_5day_ohc_geometry_durable_loeo_predictions.csv"
DURABLE_SKILL_CSV = DERIVED / "soda3_5day_ohc_geometry_durable_model_skill.csv"
MATCHED_CSV = DERIVED / "soda3_5day_ohc_geometry_matched_pentads.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_5day_ohc_geometry_diagnostics.json"
FIG_MECHANISM_PNG = OUT / "soda3_5day_ohc_geometry_mechanism_events.png"
FIG_MECHANISM_PDF = PDF_DIR / "soda3_5day_ohc_geometry_mechanism_events.pdf"
FIG_TEST_PNG = OUT / "soda3_5day_ohc_geometry_skill_and_matches.png"
FIG_TEST_PDF = PDF_DIR / "soda3_5day_ohc_geometry_skill_and_matches.pdf"
REPORT_MD = OUT / "SODA3_OHC_GEOMETRY_COUPLING_RESULT_CN.md"


MODEL_FEATURES = {
    "season_only": ["season_sin", "season_cos"],
    "total_heat": [
        "season_sin",
        "season_cos",
        "ohc300_positive_total_pj_m_15day",
        "ohc300_positive_total_pj_m_change15day",
    ],
    "east_fraction": [
        "season_sin",
        "season_cos",
        "ohc300_positive_total_pj_m_15day",
        "ohc300_positive_total_pj_m_change15day",
        "ohc300_positive_east140w_fraction_15day",
        "ohc300_positive_east140w_fraction_change15day",
    ],
    "centroid": [
        "season_sin",
        "season_cos",
        "ohc300_positive_total_pj_m_15day",
        "ohc300_positive_total_pj_m_change15day",
        "ohc300_positive_centroid_deg_e_15day",
        "ohc300_positive_centroid_deg_e_change15day",
    ],
    "east_west_gradient": [
        "season_sin",
        "season_cos",
        "ohc300_positive_total_pj_m_15day",
        "ohc300_positive_total_pj_m_change15day",
        "ohc300_east_minus_west_gj_m2_15day",
        "ohc300_east_minus_west_gj_m2_change15day",
    ],
}

SPATIAL_LEVEL_FEATURE = {
    "east_fraction": "ohc300_positive_east140w_fraction_15day",
    "centroid": "ohc300_positive_centroid_deg_e_15day",
    "east_west_gradient": "ohc300_east_minus_west_gj_m2_15day",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-input", type=Path, default=INPUT_INDEX)
    parser.add_argument("--profile-input", type=Path, default=INPUT_PROFILES)
    return parser.parse_args()


def load_indices(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["time"])
    required = {
        "time",
        "year",
        "month",
        "ohc300_positive_total_pj_m_15day",
        "ohc300_positive_total_pj_m_change15day",
        "ohc300_positive_east140w_fraction_15day",
        "ohc300_positive_east140w_fraction_change15day",
        "ohc300_positive_centroid_deg_e_15day",
        "ohc300_positive_centroid_deg_e_change15day",
        "ohc300_east_minus_west_gj_m2_15day",
        "ohc300_east_minus_west_gj_m2_change15day",
        "taux_central_180_220e_anom_nm2",
        "taux_central_180_220e_anom_nm2_15day",
        "fraction_longitudes_at_least_90pct_valid",
    }
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"Missing index columns: {sorted(missing)}")
    if set(frame["year"].unique()) != set(EVENT_YEARS):
        raise ValueError(f"Unexpected event years: {sorted(frame['year'].unique())}")
    if frame.duplicated(["year", "time"]).any():
        raise ValueError("Duplicate event pentads")
    counts = frame.groupby("year")["time"].nunique()
    if not counts.between(53, 56).all():
        raise ValueError(f"Expected 53-56 Jan-Sep pentads: {counts.to_dict()}")
    for year, group in frame.groupby("year"):
        ordered = group.sort_values("time")
        gaps = ordered["time"].diff().dropna().dt.days
        if not gaps.between(4, 6).all():
            raise ValueError(f"Unexpected time gap in {year}: {gaps.tolist()}")
        if set(ordered["month"].unique()) != set(range(1, 10)):
            raise ValueError(f"Incomplete January-September coverage in {year}")
    if not frame["fraction_longitudes_at_least_90pct_valid"].between(0.98, 1.0).all():
        raise ValueError("Unexpected OHC missing-column fraction")
    day = frame["time"].dt.dayofyear.to_numpy(dtype=float)
    frame["season_sin"] = np.sin(2.0 * np.pi * day / 365.25)
    frame["season_cos"] = np.cos(2.0 * np.pi * day / 365.25)
    return frame.sort_values(["year", "time"]).reset_index(drop=True)


def coupling_onset(
    group: pd.DataFrame,
    *,
    positive_count: int = ONSET_POSITIVE_COUNT,
    window_pentads: int = ONSET_WINDOW_PENTADS,
) -> pd.Timestamp | None:
    """First post-February persistent central-Pacific westerly episode."""
    current = group.loc[group["month"] >= ONSET_START_MONTH].sort_values("time")
    values = current["taux_central_180_220e_anom_nm2"].to_numpy(dtype=float)
    times = pd.to_datetime(current["time"]).to_numpy()
    for index in range(len(values) - window_pentads + 1):
        window = values[index : index + window_pentads]
        if (
            window[0] > 0.0
            and window[1] > 0.0
            and int(np.sum(window > 0.0)) >= positive_count
        ):
            return pd.Timestamp(times[index])
    return None


def nearest_snapshot(group: pd.DataFrame, target: pd.Timestamp) -> pd.Series:
    distances = (pd.to_datetime(group["time"]) - target).abs()
    return group.loc[distances.idxmin()]


def event_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year, group in frame.groupby("year", sort=True):
        current = group.sort_values("time")
        onset = coupling_onset(current)
        onset_sensitive = coupling_onset(
            current,
            positive_count=3,
            window_pentads=4,
        )
        onset_durable = coupling_onset(
            current,
            positive_count=DURABLE_POSITIVE_COUNT,
            window_pentads=DURABLE_WINDOW_PENTADS,
        )
        reference_time = (
            onset - pd.Timedelta(days=20)
            if onset is not None
            else pd.Timestamp(year=int(year), month=8, day=31)
        )
        snapshot = nearest_snapshot(current, reference_time)
        rows.append(
            {
                "year": int(year),
                "coupling_onset_date": None if onset is None else onset.date().isoformat(),
                "coupling_onset_dayofyear": np.nan if onset is None else onset.dayofyear,
                "coupling_observed_by_sep": onset is not None,
                "sensitivity_3of4_onset_date": (
                    None if onset_sensitive is None else onset_sensitive.date().isoformat()
                ),
                "sensitivity_8of12_durable_onset_date": (
                    None if onset_durable is None else onset_durable.date().isoformat()
                ),
                "snapshot_date": pd.Timestamp(snapshot["time"]).date().isoformat(),
                "snapshot_lead_days": (
                    np.nan
                    if onset is None
                    else int((onset - pd.Timestamp(snapshot["time"])).days)
                ),
                "pre_onset_total_heat_pj_m": float(
                    snapshot["ohc300_positive_total_pj_m_15day"]
                ),
                "pre_onset_east_fraction": float(
                    snapshot["ohc300_positive_east140w_fraction_15day"]
                ),
                "pre_onset_centroid_deg_e": float(
                    snapshot["ohc300_positive_centroid_deg_e_15day"]
                ),
                "pre_onset_east_west_gradient_gj_m2": float(
                    snapshot["ohc300_east_minus_west_gj_m2_15day"]
                ),
            }
        )
    return pd.DataFrame(rows)


def add_future_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for _, group in frame.groupby("year", sort=True):
        current = group.sort_values("time").copy()
        stress = current["taux_central_180_220e_anom_nm2"].to_numpy(dtype=float)
        future = np.full(len(current), np.nan, dtype=float)
        for index in range(len(current)):
            values = stress[index + 1 : index + 5]
            if len(values) == 4:
                future[index] = float(np.mean(values))
        current["future20day_mean_taux_nm2"] = future
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True)


def build_risk_set(
    frame: pd.DataFrame,
    *,
    positive_count: int = ONSET_POSITIVE_COUNT,
    window_pentads: int = ONSET_WINDOW_PENTADS,
) -> pd.DataFrame:
    rows = []
    complete = add_future_outcomes(frame)
    for year, group in complete.groupby("year", sort=True):
        current = group.sort_values("time").copy()
        onset = coupling_onset(
            current,
            positive_count=positive_count,
            window_pentads=window_pentads,
        )
        last_predictor_time = pd.Timestamp(current["time"].max()) - pd.Timedelta(
            days=PRIMARY_HORIZON_DAYS
        )
        risk = current.loc[
            (current["month"] >= RISK_START_MONTH)
            & (current["time"] <= last_predictor_time)
        ].copy()
        if onset is not None:
            risk = risk.loc[risk["time"] < onset]
            lead = (onset - risk["time"]).dt.days
            risk["onset_within_20day"] = lead.between(1, PRIMARY_HORIZON_DAYS).astype(int)
            risk["days_to_onset"] = lead
        else:
            risk["onset_within_20day"] = 0
            risk["days_to_onset"] = np.nan
        risk["event_onset_date"] = pd.NaT if onset is None else onset
        rows.append(risk)
    output = pd.concat(rows, ignore_index=True)
    feature_union = sorted({item for values in MODEL_FEATURES.values() for item in values})
    output = output.dropna(subset=feature_union + ["future20day_mean_taux_nm2"])
    # Ratios and centroids are not physically meaningful when the positive
    # heat reservoir is essentially absent.  The fixed 0.25 PJ m-1 floor is
    # small relative to event values and was set before inspecting outcomes.
    output = output.loc[
        output["ohc300_positive_total_pj_m_15day"] >= MIN_POSITIVE_HEAT_PJ_M
    ].copy()
    if output.groupby("year")["onset_within_20day"].max().sum() < 5:
        raise ValueError("Too few events with a modeled coupling onset")
    return output.sort_values(["year", "time"]).reset_index(drop=True)


def event_balancing_weights(years: pd.Series) -> np.ndarray:
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


def loeo_predictions(risk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    coefficient_rows = []
    for held_year in sorted(risk["year"].unique()):
        train = risk.loc[risk["year"] != held_year]
        test = risk.loc[risk["year"] == held_year]
        train_weights = event_balancing_weights(train["year"])
        for model_name, features in MODEL_FEATURES.items():
            model = make_model()
            model.fit(
                train[features].to_numpy(dtype=float),
                train["onset_within_20day"].to_numpy(dtype=int),
                logistic__sample_weight=train_weights,
            )
            coefficients = model.named_steps["logistic"].coef_[0]
            for feature, coefficient in zip(features, coefficients, strict=True):
                coefficient_rows.append(
                    {
                        "held_year": int(held_year),
                        "model": model_name,
                        "feature": feature,
                        "standardized_logit_coefficient": float(coefficient),
                    }
                )
            probability = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
            for row, value in zip(test.itertuples(), probability, strict=True):
                rows.append(
                    {
                        "time": row.time,
                        "year": int(row.year),
                        "observed_onset_within_20day": int(row.onset_within_20day),
                        "model": model_name,
                        "probability": float(value),
                    }
                )
    return (
        pd.DataFrame(rows).sort_values(["model", "year", "time"]),
        pd.DataFrame(coefficient_rows).sort_values(["model", "held_year", "feature"]),
    )


def weighted_brier(y: np.ndarray, probability: np.ndarray, weight: np.ndarray) -> float:
    return float(np.average((probability - y) ** 2, weights=weight))


def model_skill(
    predictions: pd.DataFrame,
    coefficients: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    baseline = predictions.loc[predictions["model"] == "total_heat"].copy()
    baseline = baseline.rename(columns={"probability": "baseline_probability"})
    rng = np.random.default_rng(RNG_SEED)
    for model_name, group in predictions.groupby("model", sort=False):
        current = group.copy()
        weights = event_balancing_weights(current["year"])
        observed = current["observed_onset_within_20day"].to_numpy(dtype=int)
        probability = current["probability"].to_numpy(dtype=float)
        brier = weighted_brier(observed, probability, weights)
        auc = float(roc_auc_score(observed, probability, sample_weight=weights))
        logscore = float(
            log_loss(observed, probability, sample_weight=weights, labels=[0, 1])
        )
        merged = current.merge(
            baseline[["time", "year", "baseline_probability"]],
            on=["time", "year"],
            validate="one_to_one",
        )
        event_deltas = []
        for year, event in merged.groupby("year"):
            y_event = event["observed_onset_within_20day"].to_numpy(dtype=float)
            model_error = np.mean((event["probability"].to_numpy() - y_event) ** 2)
            base_error = np.mean(
                (event["baseline_probability"].to_numpy() - y_event) ** 2
            )
            event_deltas.append((int(year), float(model_error - base_error)))
        delta_values = np.asarray([item[1] for item in event_deltas], dtype=float)
        spatial_feature = SPATIAL_LEVEL_FEATURE.get(model_name)
        if spatial_feature is None:
            spatial_coefficients = np.array([], dtype=float)
        else:
            spatial_coefficients = coefficients.loc[
                coefficients["model"].eq(model_name)
                & coefficients["feature"].eq(spatial_feature),
                "standardized_logit_coefficient",
            ].to_numpy(dtype=float)
        bootstrap = np.empty(N_BOOTSTRAP, dtype=float)
        for index in range(N_BOOTSTRAP):
            sample = rng.integers(0, len(delta_values), len(delta_values))
            bootstrap[index] = float(np.mean(delta_values[sample]))
        rows.append(
            {
                "model": model_name,
                "loeo_event_weighted_brier": brier,
                "loeo_event_weighted_auc": auc,
                "loeo_event_weighted_log_loss": logscore,
                "delta_brier_vs_total_heat": float(np.mean(delta_values)),
                "delta_brier_ci_low": float(np.quantile(bootstrap, 0.025)),
                "delta_brier_ci_high": float(np.quantile(bootstrap, 0.975)),
                "events_improved_vs_total": int(np.sum(delta_values < 0.0)),
                "events_total": len(delta_values),
                "spatial_level_coefficient_median": (
                    np.nan
                    if not len(spatial_coefficients)
                    else float(np.median(spatial_coefficients))
                ),
                "spatial_positive_fold_fraction": (
                    np.nan
                    if not len(spatial_coefficients)
                    else float(np.mean(spatial_coefficients > 0.0))
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("loeo_event_weighted_brier")


def greedy_matched_pentads(risk: pd.DataFrame) -> pd.DataFrame:
    """Pair pentads across events by date and total OHC, not heat position."""
    current = risk.copy().reset_index(drop=True)
    heat = current["ohc300_positive_total_pj_m_15day"].to_numpy(dtype=float)
    current["heat_z"] = (heat - np.mean(heat)) / np.std(heat, ddof=1)
    current["row_id"] = np.arange(len(current))
    candidates = []
    for left in range(len(current)):
        for right in range(left + 1, len(current)):
            a = current.iloc[left]
            b = current.iloc[right]
            if int(a["year"]) == int(b["year"]):
                continue
            calendar_difference = abs(int(a["time"].dayofyear) - int(b["time"].dayofyear))
            heat_difference = abs(float(a["heat_z"]) - float(b["heat_z"]))
            fraction_difference = abs(
                float(a["ohc300_positive_east140w_fraction_15day"])
                - float(b["ohc300_positive_east140w_fraction_15day"])
            )
            if calendar_difference > 15 or heat_difference > 0.20 or fraction_difference < 0.05:
                continue
            score = calendar_difference / 15.0 + heat_difference / 0.20
            candidates.append((score, left, right))
    used: set[int] = set()
    selected = []
    for _, left, right in sorted(candidates):
        if left in used or right in used:
            continue
        used.update([left, right])
        a = current.iloc[left]
        b = current.iloc[right]
        if (
            float(a["ohc300_positive_east140w_fraction_15day"])
            >= float(b["ohc300_positive_east140w_fraction_15day"])
        ):
            high, low = a, b
        else:
            high, low = b, a
        selected.append(
            {
                "pair_id": len(selected) + 1,
                "event_pair": "-".join(map(str, sorted([int(high["year"]), int(low["year"])]))),
                "high_east_year": int(high["year"]),
                "high_east_time": high["time"],
                "low_east_year": int(low["year"]),
                "low_east_time": low["time"],
                "calendar_day_difference": abs(
                    int(high["time"].dayofyear) - int(low["time"].dayofyear)
                ),
                "total_heat_z_difference": abs(float(high["heat_z"]) - float(low["heat_z"])),
                "east_fraction_difference": float(
                    high["ohc300_positive_east140w_fraction_15day"]
                    - low["ohc300_positive_east140w_fraction_15day"]
                ),
                "centroid_difference_deg": float(
                    high["ohc300_positive_centroid_deg_e_15day"]
                    - low["ohc300_positive_centroid_deg_e_15day"]
                ),
                "future20day_taux_difference_nm2": float(
                    high["future20day_mean_taux_nm2"]
                    - low["future20day_mean_taux_nm2"]
                ),
                "onset20day_difference": int(high["onset_within_20day"])
                - int(low["onset_within_20day"]),
            }
        )
    if len(selected) < 10:
        raise ValueError(f"Only {len(selected)} matched pentad pairs were found")
    return pd.DataFrame(selected)


def matched_summary(matches: pd.DataFrame) -> dict[str, float | int | list[float]]:
    by_event_pair = matches.groupby("event_pair", as_index=False).agg(
        future_stress_difference=("future20day_taux_difference_nm2", "mean"),
        onset_difference=("onset20day_difference", "mean"),
    )
    rng = np.random.default_rng(RNG_SEED + 1)
    event_pairs = np.asarray(
        [[int(item) for item in label.split("-")] for label in by_event_pair["event_pair"]],
        dtype=int,
    )
    values = by_event_pair["future_stress_difference"].to_numpy(dtype=float)
    event_years = np.asarray(EVENT_YEARS, dtype=int)
    bootstrap = np.empty(N_BOOTSTRAP, dtype=float)
    for index in range(N_BOOTSTRAP):
        sampled = rng.choice(event_years, size=len(event_years), replace=True)
        counts = {year: int(np.sum(sampled == year)) for year in event_years}
        edge_weights = np.asarray(
            [counts[left] * counts[right] for left, right in event_pairs],
            dtype=float,
        )
        if edge_weights.sum() <= 0:
            bootstrap[index] = np.nan
        else:
            bootstrap[index] = float(np.average(values, weights=edge_weights))
    bootstrap = bootstrap[np.isfinite(bootstrap)]
    return {
        "matched_pentads": len(matches),
        "unique_event_pairs": len(by_event_pair),
        "higher_east_fraction_future_stress_mean_difference_nm2": float(
            by_event_pair["future_stress_difference"].mean()
        ),
        "higher_east_fraction_future_stress_ci": [
            float(np.quantile(bootstrap, 0.025)),
            float(np.quantile(bootstrap, 0.975)),
        ],
        "directional_fraction_future_stress_positive": float(
            (matches["future20day_taux_difference_nm2"] > 0.0).mean()
        ),
        "higher_east_fraction_onset_probability_difference": float(
            by_event_pair["onset_difference"].mean()
        ),
    }


def set_plot_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "savefig.dpi": 300,
        }
    )


def plot_mechanism(
    profiles_path: Path,
    indices: pd.DataFrame,
    summaries: pd.DataFrame,
) -> None:
    profiles = pd.read_csv(profiles_path, parse_dates=["time"])
    selected_years = [1997, 2004, 2015, 2023]
    set_plot_style()
    values = profiles.loc[
        profiles["year"].isin(selected_years), "ohc300_anom_jm2"
    ].to_numpy(dtype=float) / 1.0e9
    limit = max(0.5, np.ceil(np.nanquantile(np.abs(values), 0.98) * 4.0) / 4.0)
    fig = plt.figure(figsize=(10.0, 7.0), constrained_layout=True)
    fig.get_layout_engine().set(rect=(0.0, 0.0, 1.0, 0.91))
    grid = fig.add_gridspec(2, 4, height_ratios=[3.7, 1.35])
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    stress_values = indices.loc[
        indices["year"].isin(selected_years),
        "taux_central_180_220e_anom_nm2_15day",
    ].to_numpy(dtype=float)
    stress_limit = np.ceil(np.nanmax(np.abs(stress_values)) * 100.0) / 100.0
    image = None
    top_axes = []
    for column, year in enumerate(selected_years):
        current = profiles.loc[profiles["year"] == year].copy()
        pivot = current.pivot(index="time", columns="longitude_e", values="ohc300_anom_jm2")
        pivot = pivot.sort_index().sort_index(axis=1) / 1.0e9
        axis = fig.add_subplot(grid[0, column])
        top_axes.append(axis)
        image = axis.pcolormesh(
            pivot.columns,
            pivot.index,
            pivot.to_numpy(),
            cmap="RdBu_r",
            norm=norm,
            shading="nearest",
            rasterized=True,
        )
        axis.axvline(220.0, color="0.15", lw=0.9, ls="--")
        onset_value = summaries.loc[summaries["year"] == year, "coupling_onset_date"].iloc[0]
        durable_value = summaries.loc[
            summaries["year"] == year,
            "sensitivity_8of12_durable_onset_date",
        ].iloc[0]
        if pd.notna(onset_value):
            axis.axhline(pd.Timestamp(onset_value), color="#111111", lw=1.4)
        if pd.notna(durable_value):
            axis.axhline(
                pd.Timestamp(durable_value),
                color="#7b3294",
                lw=1.2,
                ls="--",
            )
        axis.set_title(str(year), fontweight="bold")
        axis.set_xlim(180, 280)
        axis.set_xticks([180, 220, 250, 280])
        axis.set_xticklabels(["180°", "140°W", "110°W", "80°W"])
        axis.yaxis.set_major_locator(mdates.MonthLocator())
        axis.yaxis.set_major_formatter(mdates.DateFormatter("%b"))
        axis.set_ylim(pd.Timestamp(year, 9, 30), pd.Timestamp(year, 1, 1))
        if column == 0:
            axis.set_ylabel("Calendar month")
        else:
            axis.set_yticklabels([])

        lower = fig.add_subplot(grid[1, column])
        event = indices.loc[indices["year"] == year].sort_values("time")
        lower.axhline(0.0, color="0.35", lw=0.7)
        lower.plot(
            event["time"],
            event["taux_central_180_220e_anom_nm2_15day"],
            color="#17689b",
            lw=1.4,
            label="Central τx",
        )
        if pd.notna(onset_value):
            lower.axvline(pd.Timestamp(onset_value), color="#111111", lw=1.2)
        if pd.notna(durable_value):
            lower.axvline(
                pd.Timestamp(durable_value),
                color="#7b3294",
                lw=1.1,
                ls="--",
            )
        lower.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        lower.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        lower.set_xlim(pd.Timestamp(year, 1, 1), pd.Timestamp(year, 9, 30))
        lower.set_ylim(-stress_limit, stress_limit)
        if column == 0:
            lower.set_ylabel("τx anomaly (N m$^{-2}$)")
        else:
            lower.set_yticklabels([])
        lower.spines[["top", "right"]].set_visible(False)
    if image is None:
        raise RuntimeError("No mechanism panels were drawn")
    colorbar = fig.colorbar(
        image,
        ax=top_axes,
        orientation="horizontal",
        pad=0.015,
        shrink=0.72,
    )
    colorbar.set_label("0-300 m OHC anomaly (GJ m$^{-2}$)")
    fig.suptitle(
        "Same total heat is not the same ocean state: eastward OHC geometry and westerly onset",
        fontsize=13,
        fontweight="bold",
        y=0.995,
    )
    fig.legend(
        handles=[
            mpl.lines.Line2D([], [], color="#111111", lw=1.4, label="30-day episode"),
            mpl.lines.Line2D(
                [], [], color="#7b3294", lw=1.2, ls="--", label="60-day durable onset"
            ),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.945),
        ncol=2,
        frameon=False,
    )
    fig.savefig(FIG_MECHANISM_PNG, bbox_inches="tight")
    fig.savefig(FIG_MECHANISM_PDF, bbox_inches="tight")
    plt.close(fig)


def plot_skill_and_matches(
    skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    matches: pd.DataFrame,
) -> None:
    set_plot_style()
    models = ["east_fraction", "centroid", "east_west_gradient"]
    labels = ["East-of-140°W\nfraction", "Heat centroid", "East-west\ngradient"]
    current = skill.set_index("model").loc[models]
    durable = durable_skill.set_index("model").loc[models]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.9), constrained_layout=True)
    y = np.arange(len(models))
    x = current["delta_brier_vs_total_heat"].to_numpy(dtype=float)
    xerr = np.vstack(
        [
            x - current["delta_brier_ci_low"].to_numpy(dtype=float),
            current["delta_brier_ci_high"].to_numpy(dtype=float) - x,
        ]
    )
    axes[0].axvline(0.0, color="0.3", lw=0.8)
    axes[0].errorbar(x, y, xerr=xerr, fmt="o", color="#8b1a1a", capsize=3)
    durable_x = durable["delta_brier_vs_total_heat"].to_numpy(dtype=float)
    durable_xerr = np.vstack(
        [
            durable_x - durable["delta_brier_ci_low"].to_numpy(dtype=float),
            durable["delta_brier_ci_high"].to_numpy(dtype=float) - durable_x,
        ]
    )
    axes[0].errorbar(
        durable_x,
        y + 0.12,
        xerr=durable_xerr,
        fmt="s",
        color="#2166ac",
        capsize=3,
        markersize=4.5,
    )
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("LOEO Brier change vs total-heat model")
    axes[0].set_title("a  Does heat position add out-of-event skill?", loc="left", fontweight="bold")
    axes[0].text(
        0.02,
        0.02,
        "Better ←",
        transform=axes[0].transAxes,
        color="0.3",
        va="bottom",
    )
    axes[0].text(
        0.30,
        0.78,
        "● 30-day episode",
        color="#8b1a1a",
        transform=axes[0].transAxes,
        va="top",
    )
    axes[0].text(
        0.66,
        0.78,
        "■ 60-day durable",
        color="#2166ac",
        transform=axes[0].transAxes,
        va="top",
    )
    axes[0].spines[["top", "right"]].set_visible(False)

    axes[1].axhline(0.0, color="0.3", lw=0.8)
    scatter = axes[1].scatter(
        matches["east_fraction_difference"],
        matches["future20day_taux_difference_nm2"],
        c=matches["onset20day_difference"],
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        s=28,
        edgecolor="white",
        linewidth=0.4,
        alpha=0.85,
    )
    axes[1].set_xlabel("East-of-140°W heat-fraction difference")
    axes[1].set_ylabel("Next-20-day τx difference (N m$^{-2}$)")
    axes[1].set_title("b  Matched date and total heat", loc="left", fontweight="bold")
    axes[1].spines[["top", "right"]].set_visible(False)
    colorbar = fig.colorbar(scatter, ax=axes[1], pad=0.02, fraction=0.05)
    colorbar.set_ticks([-1, 0, 1])
    colorbar.set_ticklabels(["lower", "same", "higher"])
    colorbar.set_label("20-day onset outcome for higher east fraction")
    fig.suptitle(
        "Two tests of the proposed oceanic transition coordinate",
        fontsize=12,
        fontweight="bold",
    )
    fig.savefig(FIG_TEST_PNG, bbox_inches="tight")
    fig.savefig(FIG_TEST_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(
    summaries: pd.DataFrame,
    skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    match_info: dict[str, object],
) -> None:
    best = skill.iloc[0]
    fraction = skill.loc[skill["model"] == "east_fraction"].iloc[0]
    durable_fraction = durable_skill.loc[
        durable_skill["model"] == "east_fraction"
    ].iloc[0]
    onsets = int(summaries["coupling_observed_by_sep"].sum())
    robust_fraction = (
        float(fraction["delta_brier_ci_high"]) < 0.0
        and int(fraction["events_improved_vs_total"]) >= 8
        and float(fraction["spatial_positive_fold_fraction"]) >= 0.75
    )
    conclusion = (
        "东移比例在逐事件外推中稳定优于仅用总暖量的模型，因此可作为当前样本内最有希望的耦合转变坐标。"
        if robust_fraction
        else "东移比例尚未在逐事件外推中稳定优于总暖量模型，因此目前不能把它写成普适阈值；结果应保留为候选机制。"
    )
    ci = match_info["higher_east_fraction_future_stress_ci"]
    text = f"""# SODA3五日热含量空间结构与海气接通时间：阶段结果

## 科学问题

本阶段不再验证SODA3本身是否可靠，而是直接检验：**在总暖量相近时，暖量是否已经向140°W以东重新分配，能否解释随后20天中太平洋西风反馈是否接上。**

## 资料与判据

- 13个事件年：{', '.join(map(str, EVENT_YEARS))}；每年1—9月，五日分辨率。
- 海洋量：5°S—5°N、0—300 m OHC异常；统一锚定到既有1980—2024逐月去趋势气候态。
- 当总正OHC低于{MIN_POSITIVE_HEAT_PJ_M:.2f} PJ m⁻¹时不计算转变概率，避免在几乎没有正暖量时解释不稳定的比例和质心。
- 大气接通：3月以后首次出现连续两个正纬向风应力五日段，且随后30天六个五日段中至少四个为正。
- 验证：每次完整留出一个事件，禁止把相邻五日样本随机拆分到训练和验证中。
- 基线：季节位相 + 总正OHC；增量变量分别为140°W以东暖量比例、暖量质心、东西OHC梯度。

## 主要结果

- 13个事件中，有{onsets}个在9月底以前满足主接通判据。
- LOEO最小Brier模型为 `{best['model']}`，Brier={best['loeo_event_weighted_brier']:.4f}。
- 140°W以东暖量比例相对“仅总暖量”模型的Brier变化为 {fraction['delta_brier_vs_total_heat']:+.4f}，事件自助法95%区间为 [{fraction['delta_brier_ci_low']:+.4f}, {fraction['delta_brier_ci_high']:+.4f}]；{int(fraction['events_total'])}个具备有效暖量储库的留出事件中有{int(fraction['events_improved_vs_total'])}个改善。
- 该空间变量的标准化回归系数在{float(fraction['spatial_positive_fold_fraction']) * 100:.0f}%的留一训练折中为正，用于检查物理方向是否稳定。
- 为区分短脉冲与持续反馈，另用60天内12个五日段至少8个为正的耐久判据。该判据下2023年的接通从5月22日推迟到7月31日；东移比例的Brier变化为 {durable_fraction['delta_brier_vs_total_heat']:+.4f}，95%区间 [{durable_fraction['delta_brier_ci_low']:+.4f}, {durable_fraction['delta_brier_ci_high']:+.4f}]。
- 同日期、同总暖量的自然配对共{match_info['matched_pentads']}对，涉及{match_info['unique_event_pairs']}个事件组合。暖量更偏东的一方随后20天平均风应力差为 {match_info['higher_east_fraction_future_stress_mean_difference_nm2']:+.4f} N m⁻²，95%区间 [{ci[0]:+.4f}, {ci[1]:+.4f}]。

## 当前判断

{conclusion}

更具体地说，暖量向东分配对“未来20—30天会不会出现一段西风异常”有方向一致但不确定的提示；一旦把目标改为能维持约60天的反馈，加入东移比例反而使Brier由 {float(durable_skill.loc[durable_skill['model'].eq('total_heat'), 'loeo_event_weighted_brier'].iloc[0]):.4f} 增至 {durable_fraction['loeo_event_weighted_brier']:.4f}。因此，**热含量位置更像短期触发条件或可激发性指标，而不是决定大气反馈能否持续的开关。**

2023年尤其说明这一点：5月22日前后出现满足30天判据的西风异常段，但6—7月中断；直到7月31日才满足60天耐久判据。同期暖量已经明显偏东，所以“海洋已到位”仍不足以保证大气连续接上。

这里检验的是“海洋预条件是否提高大气接通概率”，不是证明因果。若空间结构能稳定增加逐事件预测能力，下一步才值得用风应力替换或扰动实验检验事件类型能否被真正转换；若不能，则应停止继续搜索热含量阈值，转向Jiang所强调的FEP—经向降水偶极—东北风大气桥梁。

## 输出

- 事件接通表：`{EVENT_SUMMARY_CSV.name}`
- 逐五日LOEO概率：`{LOEO_CSV.name}`
- LOEO系数稳定性：`{COEFFICIENT_CSV.name}`
- 模型评分：`{SKILL_CSV.name}`
- 60天耐久性评分：`{DURABLE_SKILL_CSV.name}`
- 同热量配对：`{MATCHED_CSV.name}`
- 机制图：`{FIG_MECHANISM_PNG.name}`
- 技能与配对检验图：`{FIG_TEST_PNG.name}`
"""
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    indices = load_indices(args.index_input)
    summaries = event_summary(indices)
    risk = build_risk_set(indices)
    predictions, coefficients = loeo_predictions(risk)
    skill = model_skill(predictions, coefficients)
    durable_risk = build_risk_set(
        indices,
        positive_count=DURABLE_POSITIVE_COUNT,
        window_pentads=DURABLE_WINDOW_PENTADS,
    )
    durable_predictions, durable_coefficients = loeo_predictions(durable_risk)
    durable_skill = model_skill(durable_predictions, durable_coefficients)
    matches = greedy_matched_pentads(risk)
    match_info = matched_summary(matches)
    diagnostics = {
        "event_years": list(EVENT_YEARS),
        "primary_onset_definition": {
            "search_start_month": ONSET_START_MONTH,
            "first_two_pentads_positive": True,
            "positive_pentads_in_30_days": ONSET_POSITIVE_COUNT,
            "window_pentads": ONSET_WINDOW_PENTADS,
        },
        "risk_start_month": RISK_START_MONTH,
        "forecast_horizon_days": PRIMARY_HORIZON_DAYS,
        "minimum_positive_heat_pj_m": MIN_POSITIVE_HEAT_PJ_M,
        "risk_rows": len(risk),
        "events_with_primary_onset": int(summaries["coupling_observed_by_sep"].sum()),
        "durable_onset_definition": {
            "positive_pentads": DURABLE_POSITIVE_COUNT,
            "window_pentads": DURABLE_WINDOW_PENTADS,
        },
        "events_with_durable_onset": int(
            summaries["sensitivity_8of12_durable_onset_date"].notna().sum()
        ),
        "matched_analysis": match_info,
    }
    summaries.to_csv(EVENT_SUMMARY_CSV, index=False)
    risk.to_csv(RISK_SET_CSV, index=False)
    predictions.to_csv(LOEO_CSV, index=False)
    coefficients.to_csv(COEFFICIENT_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    durable_predictions.to_csv(DURABLE_LOEO_CSV, index=False)
    durable_skill.to_csv(DURABLE_SKILL_CSV, index=False)
    matches.to_csv(MATCHED_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    plot_mechanism(args.profile_input, indices, summaries)
    plot_skill_and_matches(skill, durable_skill, matches)
    write_report(summaries, skill, durable_skill, match_info)
    print(skill.to_string(index=False))
    print("\nDurable 8-of-12 sensitivity")
    print(durable_skill.to_string(index=False))
    print(json.dumps(match_info, indent=2, ensure_ascii=False))
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
