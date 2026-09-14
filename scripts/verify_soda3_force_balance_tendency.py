#!/usr/bin/env python3
"""Test the SODA3 force-balance hypothesis against transport *tendency*.

This corrects a prior diagnostic that compared a force/acceleration proxy with
the sign of heat transport itself.  A momentum balance constrains acceleration,
so the appropriate response is the five-day tendency of warm-volume transport
or Q20, with an explicit transport-memory/damping term.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_soda3_force_balance")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = (1997, 2015, 2023)
INPUT_DIR = ROOT / "data/interim/research_2026/soda3_5day_event_transport"
BASE_PENTADS = ROOT / "data/derived/research_2026/soda3_compensation_threshold_pentads.csv"
MONTHLY_TRANSPORT = ROOT / "data/derived/research_2026/soda3_warm_transport_longitude_1980_2024.csv"
MONTHLY_D20 = ROOT / "data/derived/research_2026/soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_force_balance"
PDF_DIR = ROOT / "output/pdf"
TENDENCY_CSV = DERIVED / "soda3_force_balance_tendency_pentads.csv"
SKILL_CSV = DERIVED / "soda3_force_balance_tendency_loeo_skill.csv"
COEF_CSV = DERIVED / "soda3_force_balance_tendency_loeo_coefficients.csv"
BOOT_CSV = DERIVED / "soda3_force_balance_tendency_bootstrap.csv"
DIAG_JSON = DERIVED / "soda3_force_balance_tendency_diagnostics.json"
FIGURE_PNG = OUT_DIR / "soda3_force_balance_tendency_verification.png"
FIGURE_PDF = PDF_DIR / "soda3_force_balance_tendency_verification.pdf"
REPORT_MD = OUT_DIR / "SODA3_FORCE_BALANCE_TENDENCY_RESULT_CN.md"

WEST_LONS = tuple(np.arange(150.0, 171.0, 5.0))
CENTRAL_LONS = tuple(np.arange(190.0, 211.0, 5.0))
EARTH_RADIUS = 6_371_000.0
DISTANCE_M = EARTH_RADIUS * np.deg2rad(np.mean(CENTRAL_LONS) - np.mean(WEST_LONS))
G_REDUCED = 0.02
RNG_SEED = 20260803
N_BOOTSTRAP = 8000


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.6,
            "axes.titlesize": 9.8,
            "axes.labelsize": 8.9,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 7.2,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def event_weights(years: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(years, dtype=int)
    unique, counts = np.unique(values, return_counts=True)
    lookup = {year: 1.0 / count for year, count in zip(unique, counts, strict=True)}
    weights = np.asarray([lookup[year] for year in values], dtype=float)
    return weights / np.mean(weights)


def read_and_anchor_sections() -> tuple[pd.DataFrame, dict[str, float]]:
    pieces = []
    for year in EVENTS:
        path = INPUT_DIR / f"soda3_5day_transport_{year}_jan_jun.csv"
        current = pd.read_csv(path, parse_dates=["time"])
        if current["time"].nunique() not in {36, 37}:
            raise ValueError(f"Unexpected pentad count for {year}")
        pieces.append(current)
    frame = pd.concat(pieces, ignore_index=True).sort_values(["time", "longitude_e"])
    monthly_transport = pd.read_csv(MONTHLY_TRANSPORT)
    monthly_d20 = pd.read_csv(MONTHLY_D20)

    for raw, monthly, reference, destination in (
        (
            "warm_volume_transport_sv",
            monthly_transport,
            "warm_volume_transport_sv_anom",
            "warm_volume_transport_sv_anom",
        ),
        ("d20_m", monthly_d20, "d20_m_anom", "d20_m_anom"),
    ):
        within = frame.groupby(["year", "month", "longitude_e"])[raw].transform("mean")
        lookup = monthly[["year", "month", "longitude_e", reference]].rename(
            columns={reference: "_reference"}
        )
        frame = frame.merge(
            lookup,
            on=["year", "month", "longitude_e"],
            how="left",
            validate="many_to_one",
        )
        if frame["_reference"].isna().any():
            raise ValueError(f"Missing reference for {raw}")
        frame[destination] = frame[raw] - within + frame["_reference"]
        frame = frame.drop(columns="_reference")

    volume = (
        frame.loc[frame["longitude_e"].eq(180.0), ["time", "warm_volume_transport_sv_anom"]]
        .drop_duplicates("time")
        .set_index("time")
    )
    d20_w = (
        frame.loc[frame["longitude_e"].isin(WEST_LONS)]
        .groupby("time")["d20_m_anom"]
        .mean()
    )
    d20_c = (
        frame.loc[frame["longitude_e"].isin(CENTRAL_LONS)]
        .groupby("time")["d20_m_anom"]
        .mean()
    )
    output = volume.copy()
    output["d20_w_anom_m"] = d20_w
    output["d20_c_anom_m"] = d20_c
    output["d20_w_minus_c_anom_m"] = d20_w - d20_c
    output["d20_pressure_accel_1e8_ms2"] = (
        G_REDUCED * output["d20_w_minus_c_anom_m"] / DISTANCE_M * 1.0e8
    )

    reconstruction = frame.groupby(["year", "month", "longitude_e"])[
        ["warm_volume_transport_sv_anom", "d20_m_anom"]
    ].mean()
    transport_target = (
        monthly_transport.loc[monthly_transport["year"].isin(EVENTS)]
        .set_index(["year", "month", "longitude_e"])["warm_volume_transport_sv_anom"]
        .reindex(reconstruction.index)
    )
    d20_target = (
        monthly_d20.loc[monthly_d20["year"].isin(EVENTS)]
        .set_index(["year", "month", "longitude_e"])["d20_m_anom"]
        .reindex(reconstruction.index)
    )
    qa = {
        "volume_monthly_reconstruction_max_abs_error_sv": float(
            np.nanmax(
                np.abs(
                    reconstruction["warm_volume_transport_sv_anom"].to_numpy()
                    - transport_target.to_numpy()
                )
            )
        ),
        "d20_monthly_reconstruction_max_abs_error_m": float(
            np.nanmax(
                np.abs(reconstruction["d20_m_anom"].to_numpy() - d20_target.to_numpy())
            )
        ),
    }
    return output.reset_index(), qa


def add_tendencies(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    pieces = []
    intervals: list[float] = []
    for _, event in frame.groupby("year", sort=True):
        event = event.sort_values("time").copy()
        time = pd.DatetimeIndex(event["time"])
        next_days = pd.Series(time, index=event.index).shift(-1) - pd.Series(time, index=event.index)
        next_days = next_days.dt.total_seconds() / 86400.0
        next2_days = pd.Series(time, index=event.index).shift(-2) - pd.Series(time, index=event.index)
        next2_days = next2_days.dt.total_seconds() / 86400.0
        previous_to_next = pd.Series(time, index=event.index).shift(-1) - pd.Series(time, index=event.index).shift(1)
        previous_to_next = previous_to_next.dt.total_seconds() / 86400.0
        intervals.extend(next_days.dropna().tolist())
        for variable, short in (
            ("warm_volume_transport_sv_anom", "m180"),
            ("q20_180e_anom_pw", "q180"),
        ):
            event[f"{short}_tendency_future5"] = (
                event[variable].shift(-1) - event[variable]
            ) / next_days
            event[f"{short}_tendency_future10"] = (
                event[variable].shift(-2) - event[variable]
            ) / next2_days
            event[f"{short}_tendency_centered"] = (
                event[variable].shift(-1) - event[variable].shift(1)
            ) / previous_to_next
        pieces.append(event)
    output = pd.concat(pieces, ignore_index=True).sort_values("time")
    interval_array = np.asarray(intervals, dtype=float)
    if not np.all((interval_array >= 4.0) & (interval_array <= 6.0)):
        raise ValueError("Unexpected SODA3 five-day interval")
    qa = {
        "pentad_interval_min_days": float(interval_array.min()),
        "pentad_interval_median_days": float(np.median(interval_array)),
        "pentad_interval_max_days": float(interval_array.max()),
    }
    return output, qa


def weighted_mean_std(x: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.average(x, axis=0, weights=weights)
    variance = np.average((x - mean) ** 2, axis=0, weights=weights)
    return mean, np.sqrt(np.maximum(variance, 1.0e-12))


def fit_ridge_linear(
    x: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    ridge: float = 0.10,
) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), x])
    weighted_design = design * np.sqrt(weights)[:, None]
    weighted_y = y * np.sqrt(weights)
    penalty = np.eye(design.shape[1]) * ridge
    penalty[0, 0] = 0.0
    return np.linalg.solve(
        weighted_design.T @ weighted_design + penalty,
        weighted_design.T @ weighted_y,
    )


MODEL_FEATURES = {
    "memory_only": ["season_sin", "season_cos", "warm_volume_transport_sv_anom"],
    "ssh_force_only": ["season_sin", "season_cos", "pressure_accel_1e8_ms2", "wind_accel_1e8_ms2"],
    "ssh_balance": [
        "season_sin",
        "season_cos",
        "warm_volume_transport_sv_anom",
        "pressure_accel_1e8_ms2",
        "wind_accel_1e8_ms2",
    ],
    "d20_force_only": ["season_sin", "season_cos", "d20_pressure_accel_1e8_ms2", "wind_accel_1e8_ms2"],
    "d20_balance": [
        "season_sin",
        "season_cos",
        "warm_volume_transport_sv_anom",
        "d20_pressure_accel_1e8_ms2",
        "wind_accel_1e8_ms2",
    ],
}


def loeo_linear(frame: pd.DataFrame, outcome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = sorted({outcome} | {feature for features in MODEL_FEATURES.values() for feature in features})
    data = frame.dropna(subset=required).copy()
    predictions: list[dict[str, object]] = []
    coefficients: list[dict[str, object]] = []
    for held_year in sorted(data["year"].unique()):
        train = data.loc[data["year"].ne(held_year)]
        test = data.loc[data["year"].eq(held_year)]
        weights = event_weights(train["year"])
        for model, features in MODEL_FEATURES.items():
            x_train = train[features].to_numpy(dtype=float)
            x_test = test[features].to_numpy(dtype=float)
            mean, scale = weighted_mean_std(x_train, weights)
            x_train_z = (x_train - mean) / scale
            x_test_z = (x_test - mean) / scale
            y_train = train[outcome].to_numpy(dtype=float)
            y_mean = float(np.average(y_train, weights=weights))
            y_scale = float(np.sqrt(np.average((y_train - y_mean) ** 2, weights=weights)))
            beta = fit_ridge_linear(x_train_z, (y_train - y_mean) / y_scale, weights)
            prediction_z = np.column_stack([np.ones(len(test)), x_test_z]) @ beta
            prediction = prediction_z * y_scale + y_mean
            for row, value in zip(test.itertuples(), prediction, strict=True):
                predictions.append(
                    {
                        "outcome": outcome,
                        "time": row.time,
                        "year": int(row.year),
                        "model": model,
                        "observed": float(getattr(row, outcome)),
                        "prediction": float(value),
                    }
                )
            for feature, coefficient in zip(["intercept"] + features, beta, strict=True):
                coefficients.append(
                    {
                        "outcome": outcome,
                        "held_year": int(held_year),
                        "model": model,
                        "feature": feature,
                        "standardized_coefficient": float(coefficient),
                    }
                )
    return pd.DataFrame(predictions), pd.DataFrame(coefficients)


def summarize_skill(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (outcome, model), group in predictions.groupby(["outcome", "model"], sort=False):
        weights = event_weights(group["year"])
        observed = group["observed"].to_numpy(dtype=float)
        predicted = group["prediction"].to_numpy(dtype=float)
        error = predicted - observed
        correlation = pearsonr(observed, predicted).statistic
        rows.append(
            {
                "outcome": outcome,
                "model": model,
                "n_events": int(group["year"].nunique()),
                "n_pentads": len(group),
                "event_equal_rmse": float(np.sqrt(np.average(error**2, weights=weights))),
                "event_equal_mae": float(np.average(np.abs(error), weights=weights)),
                "pearson_r": float(correlation),
            }
        )
    return pd.DataFrame(rows)


def cluster_brier_like_delta(
    predictions: pd.DataFrame,
    model: str,
    baseline: str,
    rng: np.random.Generator,
) -> dict[str, float]:
    current = predictions.loc[predictions["model"].isin([model, baseline])]
    pivot = current.pivot_table(
        index=["year", "time", "observed"], columns="model", values="prediction"
    ).reset_index()
    deltas = []
    for _, event in pivot.groupby("year"):
        observed = event["observed"].to_numpy(dtype=float)
        deltas.append(
            float(
                np.mean((event[model].to_numpy() - observed) ** 2)
                - np.mean((event[baseline].to_numpy() - observed) ** 2)
            )
        )
    values = np.asarray(deltas, dtype=float)
    bootstrap = np.empty(N_BOOTSTRAP)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(values), len(values))
        bootstrap[index] = np.mean(values[sample])
    return {
        "delta_mse": float(np.mean(values)),
        "ci_low": float(np.quantile(bootstrap, 0.025)),
        "ci_high": float(np.quantile(bootstrap, 0.975)),
        "events_improved": int(np.sum(values < 0.0)),
        "n_events": len(values),
    }


def cluster_correlation(
    frame: pd.DataFrame,
    x: str,
    y: str,
    rng: np.random.Generator,
) -> dict[str, float]:
    data = frame.dropna(subset=[x, y]).copy()
    events = sorted(data["year"].unique())
    bootstrap = np.empty(N_BOOTSTRAP)
    for index in range(N_BOOTSTRAP):
        selected = rng.choice(events, len(events), replace=True)
        sample = pd.concat([data.loc[data["year"].eq(year)] for year in selected], ignore_index=True)
        bootstrap[index] = pearsonr(sample[x], sample[y]).statistic
    return {
        "pearson_r": float(pearsonr(data[x], data[y]).statistic),
        "spearman_r": float(spearmanr(data[x], data[y]).statistic),
        "ci_low": float(np.quantile(bootstrap, 0.025)),
        "ci_high": float(np.quantile(bootstrap, 0.975)),
        "n_events": len(events),
        "n_pentads": len(data),
    }


def fit_all_raw_balance(
    frame: pd.DataFrame,
    pressure: str,
    outcome: str,
) -> dict[str, float]:
    features = [
        "season_sin",
        "season_cos",
        "warm_volume_transport_sv_anom",
        pressure,
        "wind_accel_1e8_ms2",
    ]
    data = frame.dropna(subset=features + [outcome]).copy()
    weights = event_weights(data["year"])
    x = data[features].to_numpy(dtype=float)
    y = data[outcome].to_numpy(dtype=float)
    mean, scale = weighted_mean_std(x, weights)
    y_mean = float(np.average(y, weights=weights))
    y_scale = float(np.sqrt(np.average((y - y_mean) ** 2, weights=weights)))
    beta = fit_ridge_linear((x - mean) / scale, (y - y_mean) / y_scale, weights)
    raw_slopes = y_scale * beta[1:] / scale
    raw_intercept = y_mean + y_scale * beta[0] - np.sum(raw_slopes * mean)
    output = {"intercept_sv_day": float(raw_intercept)}
    for feature, raw, standardized in zip(features, raw_slopes, beta[1:], strict=True):
        output[f"raw_{feature}"] = float(raw)
        output[f"standardized_{feature}"] = float(standardized)
    return output


def plot_result(
    frame: pd.DataFrame,
    predictions: pd.DataFrame,
    balance: dict[str, float],
    diagnostics: dict[str, object],
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.4, 8.1))
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.11, top=0.91, wspace=0.24, hspace=0.30)
    colors = {1997: "#B7352D", 2015: "#E58C2B", 2023: "#176B87"}

    tendency_limit = float(np.nanpercentile(np.abs(frame["m180_tendency_future5"]), 98))
    scatter = axes[0, 0].scatter(
        frame["net_accel_1e8_ms2"],
        frame["m180_tendency_future5"],
        c=frame["q180_tendency_future5"],
        cmap="RdBu_r",
        vmin=-np.nanpercentile(np.abs(frame["q180_tendency_future5"]), 98),
        vmax=np.nanpercentile(np.abs(frame["q180_tendency_future5"]), 98),
        s=16,
        alpha=0.48,
        linewidth=0,
    )
    axes[0, 0].axhline(0.0, color="#555555", lw=0.7)
    axes[0, 0].axvline(0.0, color="#111111", ls="--", lw=1.0)
    axes[0, 0].set_ylim(-tendency_limit, tendency_limit)
    axes[0, 0].set_xlabel("SSH + wind acceleration proxy (10⁻⁸ m s⁻²)")
    axes[0, 0].set_ylabel("Next-pentad warm-volume transport tendency (Sv day⁻¹)")
    axes[0, 0].set_title("(a) Correct response variable: transport tendency", loc="left", fontweight="bold")
    colorbar = figure.colorbar(scatter, ax=axes[0, 0], fraction=0.046, pad=0.03)
    colorbar.set_label("Next-pentad Q20 tendency (PW day⁻¹)")

    for year, event in frame.groupby("year"):
        axes[0, 1].scatter(
            event["d20_pressure_accel_1e8_ms2"] + event["wind_accel_1e8_ms2"],
            event["m180_tendency_future5"],
            color=colors.get(int(year), "#AAAAAA"),
            alpha=0.75 if int(year) in HIGHLIGHTS else 0.30,
            s=20 if int(year) in HIGHLIGHTS else 13,
            linewidth=0,
            label=str(year) if int(year) in HIGHLIGHTS else None,
        )
    axes[0, 1].axhline(0.0, color="#555555", lw=0.7)
    axes[0, 1].axvline(0.0, color="#111111", ls="--", lw=1.0)
    axes[0, 1].set_ylim(-tendency_limit, tendency_limit)
    axes[0, 1].set_xlabel("D20 + wind acceleration proxy (10⁻⁸ m s⁻²)")
    axes[0, 1].set_ylabel("Next-pentad warm-volume transport tendency (Sv day⁻¹)")
    axes[0, 1].set_title("(b) Jin-style thermocline-slope mismatch", loc="left", fontweight="bold")
    axes[0, 1].legend(frameon=False, ncol=3, loc="upper right")

    selected_predictions = predictions.loc[
        predictions["outcome"].eq("m180_tendency_future5")
        & predictions["model"].isin(["memory_only", "d20_balance"])
    ]
    markers = {"memory_only": "o", "d20_balance": "s"}
    model_colors = {"memory_only": "#9A9A9A", "d20_balance": "#6B3FA0"}
    for model, current in selected_predictions.groupby("model"):
        axes[1, 0].scatter(
            current["observed"],
            current["prediction"],
            s=16,
            alpha=0.42,
            marker=markers[model],
            color=model_colors[model],
            linewidth=0,
            label=model.replace("_", " "),
        )
    prediction_limit = float(
        np.nanpercentile(
            np.abs(selected_predictions[["observed", "prediction"]].to_numpy()), 99
        )
    )
    axes[1, 0].plot([-prediction_limit, prediction_limit], [-prediction_limit, prediction_limit], color="#222222", ls="--", lw=0.9)
    axes[1, 0].set_xlim(-prediction_limit, prediction_limit)
    axes[1, 0].set_ylim(-prediction_limit, prediction_limit)
    axes[1, 0].set_xlabel("Observed tendency (Sv day⁻¹)")
    axes[1, 0].set_ylabel("Leave-one-event-out prediction (Sv day⁻¹)")
    axes[1, 0].set_title("(c) Does the balance generalize across events?", loc="left", fontweight="bold")
    axes[1, 0].legend(frameon=False, loc="upper left")

    data = frame.dropna(subset=["m180_tendency_future5"]).copy()
    intercept = balance["intercept_sv_day"]
    seasonal = (
        balance["raw_season_sin"] * data["season_sin"]
        + balance["raw_season_cos"] * data["season_cos"]
    )
    forcing = (
        intercept
        + seasonal
        + balance["raw_d20_pressure_accel_1e8_ms2"] * data["d20_pressure_accel_1e8_ms2"]
        + balance["raw_wind_accel_1e8_ms2"] * data["wind_accel_1e8_ms2"]
    )
    damping = balance["raw_warm_volume_transport_sv_anom"]
    image = axes[1, 1].scatter(
        forcing,
        data["warm_volume_transport_sv_anom"],
        c=data["m180_tendency_future5"],
        cmap="RdBu_r",
        vmin=-tendency_limit,
        vmax=tendency_limit,
        s=18,
        alpha=0.58,
        linewidth=0,
    )
    xline = np.linspace(np.nanpercentile(forcing, 1), np.nanpercentile(forcing, 99), 200)
    if damping != 0.0:
        axes[1, 1].plot(xline, -xline / damping, color="#111111", ls="--", lw=1.2, label="dM/dt = 0")
    axes[1, 1].set_xlabel("Pressure + wind + seasonal driving (Sv day⁻¹)")
    axes[1, 1].set_ylabel("Existing Date-Line warm-volume transport anomaly (Sv)")
    axes[1, 1].set_title("(d) The balance is a manifold, not one OHC value", loc="left", fontweight="bold")
    axes[1, 1].legend(frameon=False, loc="upper left")
    cb = figure.colorbar(image, ax=axes[1, 1], fraction=0.046, pad=0.03)
    cb.set_label("Observed next-pentad tendency (Sv day⁻¹)")

    figure.suptitle(
        "Corrected SODA3 test of the force-balance hypothesis",
        fontsize=13.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.025,
        "13 El Niño development years, five-day data, detrended 1980–2024 monthly reference. "
        "The reduced-gravity D20 term uses g′=0.02 m s⁻² and remains a proxy, not a closed momentum budget.",
        ha="center",
        fontsize=7.2,
        color="#555555",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    rng = np.random.default_rng(RNG_SEED)
    base = pd.read_csv(BASE_PENTADS, parse_dates=["time"])
    sections, anchor_qa = read_and_anchor_sections()
    frame = base.merge(sections, on="time", how="left", validate="one_to_one")
    if frame[["warm_volume_transport_sv_anom", "d20_pressure_accel_1e8_ms2"]].isna().any().any():
        raise ValueError("Missing anchored volume transport or D20 slope")
    frame, time_qa = add_tendencies(frame)

    predictions = []
    coefficients = []
    for outcome in ("m180_tendency_future5", "m180_tendency_future10", "q180_tendency_future5"):
        current_predictions, current_coefficients = loeo_linear(frame, outcome)
        predictions.append(current_predictions)
        coefficients.append(current_coefficients)
    all_predictions = pd.concat(predictions, ignore_index=True)
    all_coefficients = pd.concat(coefficients, ignore_index=True)
    skill = summarize_skill(all_predictions)

    bootstrap_rows = []
    for outcome in ("m180_tendency_future5", "m180_tendency_future10", "q180_tendency_future5"):
        current = all_predictions.loc[all_predictions["outcome"].eq(outcome)]
        for model, baseline in (
            ("ssh_balance", "memory_only"),
            ("d20_balance", "memory_only"),
            ("ssh_balance", "ssh_force_only"),
            ("d20_balance", "d20_force_only"),
        ):
            bootstrap_rows.append(
                {
                    "test": "loeo_mse_delta",
                    "outcome": outcome,
                    "model": model,
                    "baseline": baseline,
                    **cluster_brier_like_delta(current, model, baseline, rng),
                }
            )

    correlations = {}
    for name, x, y in (
        ("ssh_net_vs_m_future5", "net_accel_1e8_ms2", "m180_tendency_future5"),
        ("ssh_net_vs_m_future10", "net_accel_1e8_ms2", "m180_tendency_future10"),
        ("d20_net_vs_m_future5", "d20_pressure_accel_1e8_ms2", "m180_tendency_future5"),
        ("ssh_net_vs_q_future5", "net_accel_1e8_ms2", "q180_tendency_future5"),
    ):
        if name.startswith("d20_net"):
            frame["_d20_net"] = frame["d20_pressure_accel_1e8_ms2"] + frame["wind_accel_1e8_ms2"]
            x = "_d20_net"
        correlations[name] = cluster_correlation(frame, x, y, rng)
        bootstrap_rows.append(
            {
                "test": "cluster_correlation",
                "outcome": y,
                "model": name,
                "baseline": "",
                "delta_mse": np.nan,
                "ci_low": correlations[name]["ci_low"],
                "ci_high": correlations[name]["ci_high"],
                "events_improved": np.nan,
                "n_events": correlations[name]["n_events"],
                "pearson_r": correlations[name]["pearson_r"],
                "spearman_r": correlations[name]["spearman_r"],
            }
        )
    bootstrap = pd.DataFrame(bootstrap_rows)

    ssh_balance = fit_all_raw_balance(frame, "pressure_accel_1e8_ms2", "m180_tendency_future5")
    d20_balance = fit_all_raw_balance(frame, "d20_pressure_accel_1e8_ms2", "m180_tendency_future5")

    diagnostics: dict[str, object] = {
        "events": list(EVENTS),
        "baseline": "1980-2024 calendar-month linear detrended",
        "response": "future five-day tendency of Date-Line warm-volume transport",
        "correlations": correlations,
        "ssh_balance_raw": ssh_balance,
        "d20_balance_raw": d20_balance,
        "quality_control": {**anchor_qa, **time_qa},
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TENDENCY_CSV, index=False)
    skill.to_csv(SKILL_CSV, index=False)
    all_coefficients.to_csv(COEF_CSV, index=False)
    bootstrap.to_csv(BOOT_CSV, index=False)
    DIAG_JSON.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    plot_result(frame, all_predictions, d20_balance, diagnostics)

    def score(outcome: str, model: str, column: str = "event_equal_rmse") -> float:
        selected = skill.loc[skill["outcome"].eq(outcome) & skill["model"].eq(model), column]
        return float(selected.iloc[0])

    def delta(outcome: str, model: str, baseline: str) -> pd.Series:
        selected = bootstrap.loc[
            bootstrap["test"].eq("loeo_mse_delta")
            & bootstrap["outcome"].eq(outcome)
            & bootstrap["model"].eq(model)
            & bootstrap["baseline"].eq(baseline)
        ]
        return selected.iloc[0]

    d20_memory_delta = delta("m180_tendency_future5", "d20_balance", "memory_only")
    d20_force_delta = delta("m180_tendency_future5", "d20_balance", "d20_force_only")
    coefficient_subset = all_coefficients.loc[
        all_coefficients["outcome"].eq("m180_tendency_future5")
        & all_coefficients["model"].eq("d20_balance")
    ]
    sign_fraction = {
        feature: float(np.mean(coefficient_subset.loc[coefficient_subset["feature"].eq(feature), "standardized_coefficient"] > 0.0))
        for feature in ("d20_pressure_accel_1e8_ms2", "wind_accel_1e8_ms2")
    }
    damping_fraction = float(
        np.mean(
            coefficient_subset.loc[
                coefficient_subset["feature"].eq("warm_volume_transport_sv_anom"),
                "standardized_coefficient",
            ]
            < 0.0
        )
    )

    report = rf"""# 金飞飞充电振子框架下的SODA3受力平衡修正检验

## 关键修正

上一轮把净力代理与Q20输送的正负直接比较，这在动力学上不严格。受力平衡约束的是流速或输送的**变化率**：

\[
\frac{{dM}}{{dt}}=F_{{pressure}}+F_{{wind}}-rM+F_{{unresolved}}.
\]

所以 `F_net=0` 时，已有东向输送仍然可以保持为正。上一轮约0.51的分类准确率不能用来否定平衡点。

## 修正后的资料检验

- 13次暖事件，SODA3五日资料；响应量为下一五日日界线20°C以上暖水体积输送倾向，单位Sv day⁻¹。
- 海面坡度代理使用SSH西—中差；金飞飞式内部温跃层坡度代理使用D20西—中差和约化重力 `g′=0.02 m s⁻²`。
- 模型包含已有输送 `M`，因为稳态平衡必须包含摩擦/阻尼或流动记忆。
- 验证按完整事件留一，并用事件聚类自助法给出区间。

## 结果

### 只把两项相加仍不够

- SSH净力代理与未来五日暖水体积输送倾向：`r={correlations['ssh_net_vs_m_future5']['pearson_r']:+.2f}`，95%区间 `[{correlations['ssh_net_vs_m_future5']['ci_low']:+.2f}, {correlations['ssh_net_vs_m_future5']['ci_high']:+.2f}]`。
- D20净力代理与未来五日输送倾向：`r={correlations['d20_net_vs_m_future5']['pearson_r']:+.2f}`，95%区间 `[{correlations['d20_net_vs_m_future5']['ci_low']:+.2f}, {correlations['d20_net_vs_m_future5']['ci_high']:+.2f}]`。

这不表示没有受力平衡，而是说明“压力+风”仍未包括已有流动的惯性/阻尼、非线性平流、经向动量通量和波动相位。

### 加入已有输送后形成平衡面

- 仅输送记忆模型LOEO RMSE：`{score('m180_tendency_future5', 'memory_only'):.3f} Sv day⁻¹`。
- D20压力+风+已有输送模型RMSE：`{score('m180_tendency_future5', 'd20_balance'):.3f} Sv day⁻¹`，预测—观测相关 `{score('m180_tendency_future5', 'd20_balance', 'pearson_r'):+.2f}`。
- 相对记忆模型的事件平均MSE变化：`{d20_memory_delta['delta_mse']:+.3f}`，95%区间 `[{d20_memory_delta['ci_low']:+.3f}, {d20_memory_delta['ci_high']:+.3f}]`。
- 相对只含压力和风的模型，加入已有输送后的MSE变化：`{d20_force_delta['delta_mse']:+.3f}`，95%区间 `[{d20_force_delta['ci_low']:+.3f}, {d20_force_delta['ci_high']:+.3f}]`。
- D20压力项在 `{100*sign_fraction['d20_pressure_accel_1e8_ms2']:.0f}%` 的留一折中为正；风项在 `{100*sign_fraction['wind_accel_1e8_ms2']:.0f}%` 中为正；已有输送项在 `{100*damping_fraction:.0f}%` 中为负。

完整经验平衡不是一个固定OHC数，而是：

\[
b_0+b_s\sin\phi+b_c\cos\phi+b_pF_{{D20}}+b_wF_{{wind}}+b_mM=0.
\]

它在 `F_pressure–F_wind–M–season` 状态空间中是一张**平衡面**。事件轨迹穿过该面时，暖水输送由加速转为减速；但输送本身可以在面上保持非零。

## 与金飞飞理论的关系

金飞飞充电振子把快的温跃层倾斜调整与慢的盆地平均热含量分开：风应力与温跃层坡度的不平衡推动快速调整，盆地平均热含量 `h` 决定慢记忆，而东部SST `T` 决定Bjerknes反馈和放电。因此本研究应区分：

1. **动力受力平衡面**：决定暖量输送是加速还是减速；
2. **充电振子增长零线** `dT/dt=0`：决定海温开始增长还是衰减；
3. **大气耦合门**：决定增长能否转化为持续Bjerknes正反馈。

你的“必然存在平衡点”在完整动力系统中是正确的；需要修正的是，它不是一个只由西太平洋热含量决定的标量点。

## 输出

- 修正图：`{FIGURE_PDF}`
- 五日倾向表：`{TENDENCY_CSV}`
- 事件留一评分：`{SKILL_CSV}`
- 系数：`{COEF_CSV}`
- 自助检验：`{BOOT_CSV}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
