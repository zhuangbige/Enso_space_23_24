#!/usr/bin/env python3
"""Event comparison and exploratory ENSO prediction tests using SODA3 OHC.

Inputs
------
* SODA3.15.2 0-100 m and 0-300 m OHC fields produced by
  ``build_soda3_ohc_analysis.py``.
* NOAA ERSSTv5 monthly Niño-3.4 SST extracted by the existing same-source
  Jiang Fig. 4 workflow.

The prediction experiment is deliberately compact and leakage-aware.  For
each January-June initialization month, a walk-forward model is trained only
on earlier years.  Linear trends and predictor standardization are estimated
inside each training fold.  The target is the following November-January
(NDJ) Niño-3.4 SST residual from its training-fold trend.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
OHC_NETCDF = (
    ROOT
    / "data/interim/research_2026/soda3_ohc/"
    "soda3_ohc_0_100_0_300_1980_2024.nc"
)
OHC_CSV = ROOT / "data/derived/research_2026/soda3_ohc_indices_1980_2024.csv"
ERSST_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "grl_fig4_same_source_monthly_sst_residual_ersstv5.csv"
)
OUT_FIG = ROOT / "outputs/research_2026"
OUT_DATA = ROOT / "data/derived/research_2026"

EVENTS = {
    1997: "1997/98",
    2015: "2015/16",
    2023: "2023/24",
}

MODEL_FEATURES = {
    "Persistence (Niño-3.4)": ("nino34_init_c",),
    "OHC100 basin": ("ohc100_basin_jm2",),
    "OHC300 west": ("ohc300_west_jm2",),
    "OHC300 central": ("ohc300_central_jm2",),
    "OHC300 east": ("ohc300_east_jm2",),
    "OHC300 basin": ("ohc300_basin_jm2",),
    "OHC300 east-west": ("ohc300_east_jm2", "ohc300_west_jm2"),
    "OHC300 basin + east-west": (
        "ohc300_basin_jm2",
        "ohc300_east_jm2",
        "ohc300_west_jm2",
    ),
}

MODEL_COLORS = {
    "Persistence (Niño-3.4)": "#202020",
    "OHC100 basin": "#8c6bb1",
    "OHC300 west": "#377eb8",
    "OHC300 central": "#4daf4a",
    "OHC300 east": "#e41a1c",
    "OHC300 basin": "#ff7f00",
    "OHC300 east-west": "#a65628",
    "OHC300 basin + east-west": "#984ea3",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-start-year", type=int, default=2000)
    parser.add_argument("--test-end-year", type=int, default=2023)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    return parser.parse_args()


def set_plot_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 300,
        }
    )


def area_weighted_equatorial_mean(field: xr.DataArray) -> xr.DataArray:
    subset = field.sel(lat=slice(-5.0, 5.0), lon=slice(130.0, 280.0))
    weights = np.cos(np.deg2rad(subset["lat"]))
    return subset.weighted(weights).mean("lat", skipna=True)


def longitude_label(value: float) -> str:
    if value < 180:
        return f"{value:g}°E"
    if value == 180:
        return "180°"
    return f"{360-value:g}°W"


def event_window(year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{year - 1}-07-01", f"{year}-12-01", freq="MS") + pd.Timedelta(
        days=14
    )


def plot_event_hovmoller(dataset: xr.Dataset) -> tuple[Path, Path]:
    zonal = area_weighted_equatorial_mean(
        dataset["ohc_300m_anomaly_detrended"]
    ) / 1.0e9
    event_arrays: dict[int, xr.DataArray] = {}
    pooled: list[np.ndarray] = []
    for year in EVENTS:
        selected = zonal.sel(time=event_window(year), method="nearest")
        event_arrays[year] = selected
        pooled.append(selected.values)

    finite = np.concatenate([values[np.isfinite(values)] for values in pooled])
    vmax = float(np.ceil(np.nanpercentile(np.abs(finite), 98) * 2.0) / 2.0)
    vmax = min(max(vmax, 2.0), 5.0)
    levels = np.linspace(-vmax, vmax, 17)

    fig, axes = plt.subplots(
        1,
        3,
        figsize=(12.2, 7.0),
        sharex=True,
        sharey=True,
    )
    fig.subplots_adjust(
        left=0.075,
        right=0.985,
        top=0.86,
        bottom=0.24,
        wspace=0.12,
    )
    mesh = None
    for ax, (year, label) in zip(axes, EVENTS.items()):
        data = event_arrays[year]
        y = np.arange(data.sizes["time"])
        mesh = ax.contourf(
            data["lon"],
            y,
            data.values,
            levels=levels,
            cmap="RdBu_r",
            extend="both",
        )
        ax.contour(
            data["lon"],
            y,
            data.values,
            levels=[-2, -1, 0, 1, 2],
            colors="0.25",
            linewidths=[0.45, 0.45, 0.8, 0.45, 0.45],
            alpha=0.72,
        )
        ax.axvline(180, color="0.2", lw=0.7, ls=":")
        ax.axvline(220, color="0.2", lw=0.7, ls=":")
        ax.axvline(270, color="0.2", lw=0.7, ls=":")
        ax.axhline(5.5, color="0.15", lw=0.9, ls="--")
        ax.axhline(11.5, color="0.15", lw=0.9, ls="--")
        ax.set_title(label)
        ax.set_xlabel("Longitude")
        ax.set_xlim(130, 280)
        ax.text(
            132,
            5.65,
            "Jan 0",
            ha="left",
            va="bottom",
            fontsize=8,
        )
        ax.text(
            132,
            11.65,
            "Jul 0",
            ha="left",
            va="bottom",
            fontsize=8,
        )

    times = event_arrays[1997]["time"].to_index()
    tick_positions = np.arange(0, len(times), 2)
    tick_labels = [
        f"{time:%b} {'−1' if time.year == 1996 else '0'}"
        for time in times[tick_positions]
    ]
    axes[0].set_yticks(tick_positions, tick_labels)
    axes[0].set_ylabel("Month relative to development year")
    x_ticks = [130, 150, 180, 210, 240, 270, 280]
    for ax in axes:
        ax.set_xticks(x_ticks, [longitude_label(value) for value in x_ticks])
        ax.tick_params(axis="x", labelrotation=35)
    assert mesh is not None
    colorbar_axis = fig.add_axes([0.20, 0.115, 0.60, 0.028])
    colorbar = fig.colorbar(
        mesh,
        cax=colorbar_axis,
        orientation="horizontal",
    )
    colorbar.set_label("0–300 m OHC anomaly (GJ m$^{-2}$)")
    fig.suptitle(
        "Equatorial Pacific upper-ocean heat-content evolution",
        fontsize=14,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.032,
        "SODA3.15.2; 5°S–5°N mean; 1980–2024 calendar-month climatology and "
        "same-month linear trend removed. Vertical guides: 180°, 140°W, 90°W.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="0.35",
    )

    png = OUT_FIG / "soda3_ohc300_hovmoller_1997_2015_2023.png"
    pdf = OUT_FIG / "soda3_ohc300_hovmoller_1997_2015_2023.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf


def plot_event_indices(indices: pd.DataFrame) -> tuple[Path, Path, pd.DataFrame]:
    selected = indices.loc[
        indices["year"].isin(EVENTS),
        [
            "time",
            "year",
            "month",
            "ohc300_west_anom_jm2",
            "ohc300_central_anom_jm2",
            "ohc300_east_anom_jm2",
            "ohc300_east_minus_west_anom_jm2",
            "ohc300_positive_centroid_deg_e",
        ],
    ].copy()
    selected.to_csv(OUT_DATA / "soda3_ohc300_event_indices_1997_2015_2023.csv", index=False)

    region_specs = [
        ("ohc300_west_anom_jm2", "West (130°E–180°)", "#377eb8"),
        ("ohc300_central_anom_jm2", "Central (180°–140°W)", "#4daf4a"),
        ("ohc300_east_anom_jm2", "East (140°–80°W)", "#e41a1c"),
    ]
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(10.6, 8.2),
        sharex=True,
        sharey=True,
    )
    fig.subplots_adjust(
        left=0.09,
        right=0.985,
        top=0.90,
        bottom=0.13,
        hspace=0.20,
    )
    for ax, (year, label) in zip(axes, EVENTS.items()):
        subset = selected.loc[selected["year"].eq(year)].sort_values("month")
        for column, legend, color in region_specs:
            ax.plot(
                subset["month"],
                subset[column] / 1.0e9,
                marker="o",
                ms=3.8,
                lw=1.8,
                color=color,
                label=legend,
            )
        ax.axhline(0, color="0.25", lw=0.8)
        ax.axvspan(0.5, 6.5, color="#f4ead7", alpha=0.45, zorder=-2)
        ax.set_title(label, loc="left", fontweight="bold")
        ax.set_ylabel("OHC anomaly\n(GJ m$^{-2}$)")
        ax.grid(axis="y", color="0.88", lw=0.7)
    axes[0].legend(ncol=3, frameon=False, loc="upper left")
    axes[-1].set_xticks(np.arange(1, 13), [pd.Timestamp(2001, m, 1).strftime("%b") for m in range(1, 13)])
    axes[-1].set_xlabel("Development-year calendar month")
    fig.suptitle(
        "Where was the upper-ocean heat stored during each event?",
        fontsize=14,
        fontweight="bold",
        y=0.975,
    )
    fig.text(
        0.5,
        0.025,
        "SODA3.15.2, 0–300 m; area-weighted 5°S–5°N means. Shading marks the "
        "January–June period emphasized in the report.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="0.35",
    )
    png = OUT_FIG / "soda3_ohc300_event_regions_1997_2015_2023.png"
    pdf = OUT_FIG / "soda3_ohc300_event_regions_1997_2015_2023.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf, selected


def build_prediction_table(indices: pd.DataFrame, ersst: pd.DataFrame) -> pd.DataFrame:
    ohc = indices.copy()
    ohc["time"] = pd.to_datetime(ohc["time"])
    sst = ersst[["time", "nino34_sst"]].copy()
    sst["time"] = pd.to_datetime(sst["time"])
    sst["year"] = sst["time"].dt.year
    sst["month"] = sst["time"].dt.month

    ndj_rows: list[dict[str, float | int]] = []
    sst_lookup = sst.set_index(["year", "month"])["nino34_sst"]
    for year in range(1980, 2024):
        keys = [(year, 11), (year, 12), (year + 1, 1)]
        values = [sst_lookup.get(key, np.nan) for key in keys]
        ndj_rows.append({"year": year, "target_ndj_c": float(np.nanmean(values))})
    ndj = pd.DataFrame(ndj_rows)

    frames: list[pd.DataFrame] = []
    for month in range(1, 7):
        subset = ohc.loc[ohc["month"].eq(month)].copy()
        subset["init_month"] = month
        subset = subset.merge(
            sst.loc[sst["month"].eq(month), ["year", "nino34_sst"]],
            on="year",
            how="left",
        ).rename(columns={"nino34_sst": "nino34_init_c"})
        subset = subset.merge(ndj, on="year", how="left")
        frames.append(subset)
    result = pd.concat(frames, ignore_index=True)
    keep = [
        "year",
        "init_month",
        "target_ndj_c",
        "nino34_init_c",
        "ohc100_basin_jm2",
        "ohc300_west_jm2",
        "ohc300_central_jm2",
        "ohc300_east_jm2",
        "ohc300_basin_jm2",
    ]
    return result[keep].sort_values(["init_month", "year"]).reset_index(drop=True)


def fit_trend(years: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    design = np.column_stack([np.ones(years.size), years])
    intercept, slope = np.linalg.lstsq(design, values, rcond=None)[0]
    return float(intercept), float(slope)


def detrend_with_training(
    train_years: np.ndarray,
    train_values: np.ndarray,
    test_year: float,
    test_value: float,
) -> tuple[np.ndarray, float]:
    intercept, slope = fit_trend(train_years, train_values)
    train_residual = train_values - (intercept + slope * train_years)
    test_residual = test_value - (intercept + slope * test_year)
    return train_residual, float(test_residual)


def predict_fold(
    train: pd.DataFrame,
    test: pd.Series,
    features: tuple[str, ...],
) -> tuple[float, float]:
    columns = ["target_ndj_c", *features]
    train = train.dropna(subset=columns)
    if len(train) < 15 or test[list(columns)].isna().any():
        return np.nan, np.nan
    years = train["year"].to_numpy(dtype=float)
    test_year = float(test["year"])

    y_train, y_observed = detrend_with_training(
        years,
        train["target_ndj_c"].to_numpy(dtype=float),
        test_year,
        float(test["target_ndj_c"]),
    )
    x_columns: list[np.ndarray] = []
    x_test_values: list[float] = []
    for feature in features:
        train_resid, test_resid = detrend_with_training(
            years,
            train[feature].to_numpy(dtype=float),
            test_year,
            float(test[feature]),
        )
        scale = float(np.std(train_resid, ddof=1))
        if not np.isfinite(scale) or scale == 0:
            return np.nan, np.nan
        x_columns.append(train_resid / scale)
        x_test_values.append(test_resid / scale)
    x_train = np.column_stack(x_columns)
    design = np.column_stack([np.ones(len(train)), x_train])
    coefficients = np.linalg.lstsq(design, y_train, rcond=None)[0]
    prediction = float(
        np.dot(np.r_[1.0, np.asarray(x_test_values, dtype=float)], coefficients)
    )
    return prediction, y_observed


def walk_forward_predictions(
    table: pd.DataFrame,
    test_start: int,
    test_end: int,
) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in range(1, 7):
        monthly = table.loc[table["init_month"].eq(month)].sort_values("year")
        for year in range(test_start, test_end + 1):
            test_rows = monthly.loc[monthly["year"].eq(year)]
            if test_rows.empty:
                continue
            test = test_rows.iloc[0]
            train = monthly.loc[monthly["year"].lt(year)]
            for model, features in MODEL_FEATURES.items():
                prediction, observed = predict_fold(train, test, features)
                rows.append(
                    {
                        "year": year,
                        "init_month": month,
                        "model": model,
                        "prediction_ndj_residual_c": prediction,
                        "observed_ndj_residual_c": observed,
                        "n_training_years": int(
                            train.dropna(subset=["target_ndj_c", *features]).shape[0]
                        ),
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_skill_interval(
    observed: np.ndarray,
    prediction: np.ndarray,
    persistence: np.ndarray,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = observed.size
    if n < 5:
        return np.nan, np.nan
    skills = np.empty(samples, dtype=float)
    for index in range(samples):
        sample = rng.integers(0, n, size=n)
        model_rmse = np.sqrt(np.mean((prediction[sample] - observed[sample]) ** 2))
        persistence_rmse = np.sqrt(
            np.mean((persistence[sample] - observed[sample]) ** 2)
        )
        skills[index] = (
            1.0 - model_rmse / persistence_rmse
            if persistence_rmse > 0
            else np.nan
        )
    return (
        float(np.nanpercentile(skills, 2.5)),
        float(np.nanpercentile(skills, 97.5)),
    )


def summarize_skill(predictions: pd.DataFrame, bootstrap_samples: int) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in range(1, 7):
        subset = predictions.loc[predictions["init_month"].eq(month)]
        persistence = subset.loc[
            subset["model"].eq("Persistence (Niño-3.4)"),
            ["year", "prediction_ndj_residual_c"],
        ].rename(columns={"prediction_ndj_residual_c": "persistence_prediction"})
        for model in MODEL_FEATURES:
            current = subset.loc[
                subset["model"].eq(model),
                [
                    "year",
                    "prediction_ndj_residual_c",
                    "observed_ndj_residual_c",
                ],
            ].merge(persistence, on="year", how="inner")
            current = current.replace([np.inf, -np.inf], np.nan).dropna()
            observed = current["observed_ndj_residual_c"].to_numpy()
            predicted = current["prediction_ndj_residual_c"].to_numpy()
            persistence_predicted = current["persistence_prediction"].to_numpy()
            rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
            mae = float(np.mean(np.abs(predicted - observed)))
            correlation = (
                float(np.corrcoef(predicted, observed)[0, 1])
                if len(current) >= 3
                else np.nan
            )
            persistence_rmse = float(
                np.sqrt(np.mean((persistence_predicted - observed) ** 2))
            )
            skill = (
                float(1.0 - rmse / persistence_rmse)
                if persistence_rmse > 0
                else np.nan
            )
            ci_low, ci_high = bootstrap_skill_interval(
                observed,
                predicted,
                persistence_predicted,
                bootstrap_samples,
                seed=10_000 + 100 * month + list(MODEL_FEATURES).index(model),
            )
            rows.append(
                {
                    "init_month": month,
                    "model": model,
                    "n_test_years": len(current),
                    "rmse_c": rmse,
                    "mae_c": mae,
                    "correlation": correlation,
                    "skill_vs_persistence": skill,
                    "skill_ci_2p5": ci_low,
                    "skill_ci_97p5": ci_high,
                }
            )
    return pd.DataFrame(rows)


def event_hindcasts(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for event_year in EVENTS:
        for month in range(1, 7):
            monthly = table.loc[table["init_month"].eq(month)].sort_values("year")
            test_rows = monthly.loc[monthly["year"].eq(event_year)]
            if test_rows.empty:
                continue
            test = test_rows.iloc[0]
            train = monthly.loc[monthly["year"].lt(event_year)]
            for model, features in MODEL_FEATURES.items():
                prediction, observed = predict_fold(train, test, features)
                rows.append(
                    {
                        "event": EVENTS[event_year],
                        "year": event_year,
                        "init_month": month,
                        "model": model,
                        "prediction_ndj_residual_c": prediction,
                        "observed_ndj_residual_c": observed,
                    }
                )
    return pd.DataFrame(rows)


def plot_prediction_skill(skill: pd.DataFrame) -> tuple[Path, Path]:
    months = np.arange(1, 7)
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(10.8, 10.0),
        sharex=True,
    )
    fig.subplots_adjust(
        left=0.11,
        right=0.985,
        top=0.90,
        bottom=0.11,
        hspace=0.10,
    )
    for model in MODEL_FEATURES:
        current = skill.loc[skill["model"].eq(model)].sort_values("init_month")
        style = "--" if model == "Persistence (Niño-3.4)" else "-"
        width = 2.4 if model in {"Persistence (Niño-3.4)", "OHC300 basin"} else 1.4
        axes[0].plot(
            months,
            current["rmse_c"],
            marker="o",
            ms=3.5,
            lw=width,
            ls=style,
            color=MODEL_COLORS[model],
            label=model,
        )
        axes[1].plot(
            months,
            current["correlation"],
            marker="o",
            ms=3.5,
            lw=width,
            ls=style,
            color=MODEL_COLORS[model],
        )
        if model != "Persistence (Niño-3.4)":
            axes[2].plot(
                months,
                current["skill_vs_persistence"],
                marker="o",
                ms=3.5,
                lw=width,
                color=MODEL_COLORS[model],
                label=model,
            )
    axes[0].set_ylabel("NDJ RMSE (°C)\nlower is better")
    axes[1].set_ylabel("Correlation\nhigher is better")
    axes[2].set_ylabel("RMSE skill vs persistence\nhigher is better")
    axes[1].axhline(0, color="0.35", lw=0.8)
    axes[2].axhline(0, color="0.2", lw=0.9, ls="--")
    axes[2].set_xticks(months, month_labels)
    axes[2].set_xlabel("Initialization month")
    for ax in axes:
        ax.grid(axis="y", color="0.88", lw=0.7)
    axes[0].legend(
        ncol=2,
        fontsize=8.2,
        frameon=False,
        loc="upper right",
    )
    fig.suptitle(
        "Does upper-ocean heat content improve NDJ Niño-3.4 prediction?",
        fontsize=14,
        fontweight="bold",
        y=0.975,
    )
    fig.text(
        0.5,
        0.025,
        "Walk-forward validation: train only on earlier years, test 2000–2023. "
        "Training-fold linear trends and scaling are refit for every prediction.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="0.35",
    )
    png = OUT_FIG / "soda3_ohc_ndj_nino34_walkforward_skill.png"
    pdf = OUT_FIG / "soda3_ohc_ndj_nino34_walkforward_skill.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf


def write_summary(
    indices: pd.DataFrame,
    skill: pd.DataFrame,
    event_predictions: pd.DataFrame,
    args: argparse.Namespace,
) -> Path:
    event_2023 = indices.loc[
        indices["year"].eq(2023) & indices["month"].isin([1, 6, 12])
    ].set_index("month")
    ohc_only = skill.loc[~skill["model"].str.startswith("Persistence")].copy()
    average_skill = (
        ohc_only.groupby("model", as_index=False)["skill_vs_persistence"]
        .mean()
        .sort_values("skill_vs_persistence", ascending=False)
    )
    best_model = str(average_skill.iloc[0]["model"])
    best_average_skill = float(average_skill.iloc[0]["skill_vs_persistence"])
    best_month_row = ohc_only.loc[ohc_only["skill_vs_persistence"].idxmax()]
    june = skill.loc[skill["init_month"].eq(6)].sort_values("rmse_c")

    lines = [
        "# SODA3 upper-ocean heat-content analysis: first results",
        "",
        "## Data and definitions",
        "",
        "- SODA3.15.2 potential temperature, 1980–2024.",
        "- OHC is vertically integrated with constant ρ = 1025 kg m⁻³ and "
        "cp = 3990 J kg⁻¹ K⁻¹.",
        "- Event figures use 1980–2024 calendar-month anomalies with the "
        "same-calendar-month linear trend removed.",
        "- Prediction target: NDJ (November–January) Niño-3.4 SST.",
        f"- Validation: walk-forward tests for {args.test_start_year}–"
        f"{args.test_end_year}; only earlier years are used in each fold.",
        "",
        "## 2023 heat redistribution",
        "",
        f"- January: west = {event_2023.loc[1, 'ohc300_west_anom_jm2']/1e9:+.2f}, "
        f"central = {event_2023.loc[1, 'ohc300_central_anom_jm2']/1e9:+.2f}, "
        f"east = {event_2023.loc[1, 'ohc300_east_anom_jm2']/1e9:+.2f} GJ m⁻².",
        f"- June: west = {event_2023.loc[6, 'ohc300_west_anom_jm2']/1e9:+.2f}, "
        f"central = {event_2023.loc[6, 'ohc300_central_anom_jm2']/1e9:+.2f}, "
        f"east = {event_2023.loc[6, 'ohc300_east_anom_jm2']/1e9:+.2f} GJ m⁻².",
        f"- December: west = {event_2023.loc[12, 'ohc300_west_anom_jm2']/1e9:+.2f}, "
        f"central = {event_2023.loc[12, 'ohc300_central_anom_jm2']/1e9:+.2f}, "
        f"east = {event_2023.loc[12, 'ohc300_east_anom_jm2']/1e9:+.2f} GJ m⁻².",
        "- This is a west-to-east redistribution signal, not uniform basin-wide "
        "warming: the western reservoir is depleted while eastern OHC increases.",
        "",
        "## Exploratory prediction result",
        "",
        f"- Best OHC model averaged across January–June: **{best_model}**, "
        f"mean RMSE skill versus Niño-3.4 persistence = "
        f"{best_average_skill:+.3f}.",
        f"- Largest single-month OHC skill: **{best_month_row['model']}** in "
        f"month {int(best_month_row['init_month'])}, skill = "
        f"{best_month_row['skill_vs_persistence']:+.3f} "
        f"(95% bootstrap interval "
        f"{best_month_row['skill_ci_2p5']:+.3f} to "
        f"{best_month_row['skill_ci_97p5']:+.3f}).",
        "- June model ranking by RMSE:",
        "",
    ]
    for _, row in june.head(5).iterrows():
        lines.append(
            f"  - {row['model']}: RMSE {row['rmse_c']:.3f} °C, "
            f"r = {row['correlation']:.3f}, "
            f"skill vs persistence = {row['skill_vs_persistence']:+.3f}."
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "- These are retrospective exploratory tests with only 24 independent "
            "verification years per initialization month.",
            "- Positive skill is useful evidence only when it is stable across "
            "months and the bootstrap interval is not dominated by zero.",
            "- The next test should add D20, zonal wind and OLR one at a time, "
            "then ask whether OHC contributes incremental skill beyond each baseline.",
            "",
            "## Event hindcast table",
            "",
            "The machine-readable event predictions for 1997/98, 2015/16 and "
            "2023/24 are stored beside this note.",
        ]
    )
    path = OUT_DATA / "soda3_ohc_first_analysis_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    diagnostics = {
        "best_average_ohc_model": best_model,
        "best_average_skill_vs_persistence": best_average_skill,
        "best_single_month_ohc_model": str(best_month_row["model"]),
        "best_single_month": int(best_month_row["init_month"]),
        "best_single_month_skill": float(best_month_row["skill_vs_persistence"]),
        "n_event_hindcast_rows": int(len(event_predictions)),
    }
    (OUT_DATA / "soda3_ohc_first_analysis_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2),
        encoding="utf-8",
    )
    return path


def main() -> int:
    args = parse_args()
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    set_plot_style()

    dataset = xr.open_dataset(OHC_NETCDF, engine="netcdf4", chunks=None)
    indices = pd.read_csv(OHC_CSV, parse_dates=["time"])
    ersst = pd.read_csv(ERSST_CSV, parse_dates=["time"])

    hov_png, hov_pdf = plot_event_hovmoller(dataset)
    regions_png, regions_pdf, _ = plot_event_indices(indices)

    table = build_prediction_table(indices, ersst)
    table_path = OUT_DATA / "soda3_ohc_prediction_input_table_1980_2023.csv"
    table.to_csv(table_path, index=False)
    predictions = walk_forward_predictions(
        table,
        args.test_start_year,
        args.test_end_year,
    )
    prediction_path = OUT_DATA / "soda3_ohc_ndj_nino34_walkforward_predictions.csv"
    predictions.to_csv(prediction_path, index=False)
    skill = summarize_skill(predictions, args.bootstrap_samples)
    skill_path = OUT_DATA / "soda3_ohc_ndj_nino34_walkforward_skill.csv"
    skill.to_csv(skill_path, index=False)

    event_predictions = event_hindcasts(table)
    event_prediction_path = (
        OUT_DATA / "soda3_ohc_event_hindcasts_1997_2015_2023.csv"
    )
    event_predictions.to_csv(event_prediction_path, index=False)
    skill_png, skill_pdf = plot_prediction_skill(skill)
    summary = write_summary(indices, skill, event_predictions, args)

    for path in (
        hov_png,
        hov_pdf,
        regions_png,
        regions_pdf,
        skill_png,
        skill_pdf,
        table_path,
        prediction_path,
        skill_path,
        event_prediction_path,
        summary,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
