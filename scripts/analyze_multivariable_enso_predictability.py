#!/usr/bin/env python3
"""Add D20, zonal wind, and OLR to the OHC ENSO prediction experiment.

All predictors are monthly physical values.  For every walk-forward test
year, trends and predictor scales are estimated only from earlier training
years.  This avoids using a fixed full-period climatology in the prediction
experiment while retaining the report's 1980-2024 climatology for event
anomaly figures.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
import xarray as xr

from analyze_soda3_ohc_predictability import (
    bootstrap_skill_interval,
    predict_fold,
    set_plot_style,
)


ROOT = Path(__file__).resolve().parents[1]
OHC_CSV = ROOT / "data/derived/research_2026/soda3_ohc_indices_1980_2024.csv"
D20_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_d20_timeseries_equatorial_1960_202606.csv"
)
TAUX_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_windstress_timeseries_equatorial_1980_202605.csv"
)
ERSST_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "grl_fig4_same_source_monthly_sst_residual_ersstv5.csv"
)
ERA5_U850_FILES = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc",
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jun.nc",
)
ERA5_OLR_DIR = ROOT / "data/raw/era5/olr_monthly_1deg_1980_2026"
OUT_DATA = ROOT / "data/derived/research_2026"
OUT_FIG = ROOT / "outputs/research_2026"

MODEL_FEATURES = {
    "Persistence (Niño-3.4)": ("nino34_init_c",),
    "OHC300 central": ("ohc300_central_jm2",),
    "D20 central": ("d20_central_m",),
    "D20 east-west": ("d20_gradient_m",),
    "ERA5 u850 CWP": ("era5_u850_cwp_ms",),
    "ORAS5 zonal stress CWP": ("oras5_taux_cwp_nm2",),
    "ERA5 OLR central": ("era5_olr_central_wm2",),
    "Atmosphere (u850 + OLR)": (
        "era5_u850_cwp_ms",
        "era5_olr_central_wm2",
    ),
    "OHC + D20": (
        "ohc300_central_jm2",
        "d20_central_m",
    ),
    "OHC + u850": (
        "ohc300_central_jm2",
        "era5_u850_cwp_ms",
    ),
    "OHC + OLR": (
        "ohc300_central_jm2",
        "era5_olr_central_wm2",
    ),
    "OHC + atmosphere": (
        "ohc300_central_jm2",
        "era5_u850_cwp_ms",
        "era5_olr_central_wm2",
    ),
    "OHC + D20 + atmosphere": (
        "ohc300_central_jm2",
        "d20_central_m",
        "era5_u850_cwp_ms",
        "era5_olr_central_wm2",
    ),
}

SINGLE_MODELS = [
    "Persistence (Niño-3.4)",
    "OHC300 central",
    "D20 central",
    "D20 east-west",
    "ERA5 u850 CWP",
    "ORAS5 zonal stress CWP",
    "ERA5 OLR central",
    "Atmosphere (u850 + OLR)",
]

INCREMENT_MODELS = [
    "OHC + D20",
    "OHC + u850",
    "OHC + OLR",
    "OHC + atmosphere",
    "OHC + D20 + atmosphere",
]

EVENTS = {1997: "1997/98", 2015: "2015/16", 2023: "2023/24"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-start-year", type=int, default=2000)
    parser.add_argument("--test-end-year", type=int, default=2023)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    return parser.parse_args()


def area_weighted_mean(
    field: xr.DataArray,
    lat_name: str,
    lon_name: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> xr.DataArray:
    sorted_field = field.sortby(lat_name).sortby(lon_name)
    subset = sorted_field.sel(
        {
            lat_name: slice(lat_min, lat_max),
            lon_name: slice(lon_min, lon_max),
        }
    )
    if subset.sizes[lat_name] == 0 or subset.sizes[lon_name] == 0:
        raise ValueError(
            f"Empty subset for {lat_name}={lat_min}:{lat_max}, "
            f"{lon_name}={lon_min}:{lon_max}"
        )
    weights = np.cos(np.deg2rad(subset[lat_name]))
    return subset.weighted(weights).mean((lat_name, lon_name), skipna=True)


def build_d20_indices() -> pd.DataFrame:
    data = pd.read_csv(D20_CSV)
    data = data.loc[
        data["year"].between(1980, 2023)
        & data["month"].between(1, 6)
        & data["d20_m"].notna()
    ].copy()
    # 130E is a constant shallow coastal value in this equatorial transect;
    # 280E is missing.  Restrict the analysis to valid 135E-270E points.
    regions = {
        "basin": (135, 270),
        "west": (135, 175),
        "central": (180, 215),
        "east": (220, 270),
    }
    base = data[["year", "month"]].drop_duplicates().sort_values(["year", "month"])
    for name, (lon0, lon1) in regions.items():
        region = (
            data.loc[data["requested_lon"].between(lon0, lon1)]
            .groupby(["year", "month"], as_index=False)["d20_m"]
            .mean()
            .rename(columns={"d20_m": f"d20_{name}_m"})
        )
        base = base.merge(region, on=["year", "month"], how="left")
    base["d20_gradient_m"] = base["d20_east_m"] - base["d20_west_m"]
    return base


def build_oras5_taux_index() -> pd.DataFrame:
    data = pd.read_csv(TAUX_CSV)
    subset = data.loc[
        data["year"].between(1980, 2023)
        & data["month"].between(1, 6)
        & data["requested_lon"].between(160, 220)
        & data["tau_x_n_m2"].notna()
    ]
    return (
        subset.groupby(["year", "month"], as_index=False)["tau_x_n_m2"]
        .mean()
        .rename(columns={"tau_x_n_m2": "oras5_taux_cwp_nm2"})
    )


def build_era5_u850_index() -> pd.DataFrame:
    opened: list[xr.Dataset] = []
    try:
        for path in ERA5_U850_FILES:
            opened.append(xr.open_dataset(path, engine="netcdf4", chunks=None))
        combined = xr.concat(opened, dim="valid_time").sortby("valid_time")
        u = combined["u"].squeeze("pressure_level", drop=True)
        u = u.assign_coords(longitude=(u["longitude"] % 360)).sortby("longitude")
        index = area_weighted_mean(
            u,
            "latitude",
            "longitude",
            -5.0,
            5.0,
            160.0,
            220.0,
        ).load()
    finally:
        for dataset in opened:
            dataset.close()
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(index["valid_time"].values),
            "era5_u850_cwp_ms": index.values,
        }
    )
    frame["year"] = frame["time"].dt.year
    frame["month"] = frame["time"].dt.month
    return frame.loc[
        frame["year"].between(1980, 2023) & frame["month"].between(1, 6),
        ["year", "month", "era5_u850_cwp_ms"],
    ]


def build_era5_olr_index() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month in range(1, 7):
        path = ERA5_OLR_DIR / f"era5_olr_east_m{month:02d}_1980_2026_1deg.nc"
        with xr.open_dataset(path, engine="netcdf4", chunks=None) as dataset:
            variable = "avg_tnlwrf"
            # ERA5 vertical radiative flux is positive downward.  OLR is the
            # opposite sign: positive values indicate more outgoing radiation.
            olr = -dataset[variable]
            olr = olr.assign_coords(longitude=(olr["longitude"] % 360)).sortby(
                "longitude"
            )
            index = area_weighted_mean(
                olr,
                "latitude",
                "longitude",
                -5.0,
                5.0,
                180.0,
                220.0,
            ).load()
        current = pd.DataFrame(
            {
                "time": pd.to_datetime(index["valid_time"].values),
                "era5_olr_central_wm2": index.values,
            }
        )
        current["year"] = current["time"].dt.year
        current["month"] = current["time"].dt.month
        frames.append(current)
    result = pd.concat(frames, ignore_index=True)
    return result.loc[
        result["year"].between(1980, 2023) & result["month"].between(1, 6),
        ["year", "month", "era5_olr_central_wm2"],
    ]


def build_target_and_persistence() -> pd.DataFrame:
    sst = pd.read_csv(ERSST_CSV, parse_dates=["time"])
    sst["year"] = sst["time"].dt.year
    sst["month"] = sst["time"].dt.month
    lookup = sst.set_index(["year", "month"])["nino34_sst"]
    rows: list[dict[str, float | int]] = []
    for year in range(1980, 2024):
        target = np.mean(
            [
                lookup.loc[(year, 11)],
                lookup.loc[(year, 12)],
                lookup.loc[(year + 1, 1)],
            ]
        )
        for month in range(1, 7):
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "nino34_init_c": float(lookup.loc[(year, month)]),
                    "target_ndj_c": float(target),
                }
            )
    return pd.DataFrame(rows)


def build_input_table() -> pd.DataFrame:
    ohc = pd.read_csv(OHC_CSV, parse_dates=["time"])
    ohc = ohc.loc[
        ohc["year"].between(1980, 2023) & ohc["month"].between(1, 6),
        [
            "year",
            "month",
            "ohc300_central_jm2",
            "ohc300_west_jm2",
            "ohc300_east_jm2",
        ],
    ].copy()
    ohc["ohc300_gradient_jm2"] = (
        ohc["ohc300_east_jm2"] - ohc["ohc300_west_jm2"]
    )

    table = build_target_and_persistence()
    for source in (
        ohc,
        build_d20_indices(),
        build_era5_u850_index(),
        build_oras5_taux_index(),
        build_era5_olr_index(),
    ):
        table = table.merge(source, on=["year", "month"], how="left")
    return table.sort_values(["month", "year"]).reset_index(drop=True)


def validate_input_table(table: pd.DataFrame) -> None:
    expected_rows = 44 * 6
    if len(table) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, found {len(table)}")
    if table.duplicated(["year", "month"]).any():
        raise ValueError("Duplicate year-month rows in predictor table")
    required = sorted({name for features in MODEL_FEATURES.values() for name in features})
    required.append("target_ndj_c")
    missing = table[required].isna().sum()
    if int(missing.sum()) > 0:
        raise ValueError(f"Missing predictor values:\n{missing[missing.gt(0)]}")

    bounds = {
        "nino34_init_c": (20.0, 32.0),
        "target_ndj_c": (20.0, 32.0),
        "ohc300_central_jm2": (1.0e10, 5.0e10),
        "d20_central_m": (20.0, 250.0),
        "d20_gradient_m": (-250.0, 100.0),
        "era5_u850_cwp_ms": (-15.0, 15.0),
        "oras5_taux_cwp_nm2": (-0.2, 0.2),
        "era5_olr_central_wm2": (100.0, 400.0),
    }
    for column, (lower, upper) in bounds.items():
        values = table[column]
        if values.min() < lower or values.max() > upper:
            raise ValueError(
                f"{column} outside physical QA range: "
                f"{values.min():.4g} to {values.max():.4g}"
            )
        print(
            f"{column}: min={values.min():.5g}, "
            f"median={values.median():.5g}, max={values.max():.5g}"
        )


def walk_forward_predictions(
    table: pd.DataFrame,
    test_start: int,
    test_end: int,
) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in range(1, 7):
        monthly = table.loc[table["month"].eq(month)].sort_values("year")
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


def skill_against_reference(
    observed: np.ndarray,
    predicted: np.ndarray,
    reference: np.ndarray,
) -> float:
    model_rmse = np.sqrt(np.mean((predicted - observed) ** 2))
    reference_rmse = np.sqrt(np.mean((reference - observed) ** 2))
    return float(1.0 - model_rmse / reference_rmse) if reference_rmse > 0 else np.nan


def summarize_skill(predictions: pd.DataFrame, bootstrap_samples: int) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in range(1, 7):
        subset = predictions.loc[predictions["init_month"].eq(month)]
        references = {}
        for label, model in (
            ("persistence_prediction", "Persistence (Niño-3.4)"),
            ("ohc_prediction", "OHC300 central"),
        ):
            references[label] = subset.loc[
                subset["model"].eq(model),
                ["year", "prediction_ndj_residual_c"],
            ].rename(columns={"prediction_ndj_residual_c": label})

        for model in MODEL_FEATURES:
            current = subset.loc[
                subset["model"].eq(model),
                [
                    "year",
                    "prediction_ndj_residual_c",
                    "observed_ndj_residual_c",
                ],
            ]
            for reference in references.values():
                current = current.merge(reference, on="year", how="inner")
            current = current.replace([np.inf, -np.inf], np.nan).dropna()
            observed = current["observed_ndj_residual_c"].to_numpy()
            predicted = current["prediction_ndj_residual_c"].to_numpy()
            persistence = current["persistence_prediction"].to_numpy()
            ohc = current["ohc_prediction"].to_numpy()
            rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
            mae = float(np.mean(np.abs(predicted - observed)))
            correlation = float(np.corrcoef(predicted, observed)[0, 1])
            persistence_skill = skill_against_reference(
                observed, predicted, persistence
            )
            persistence_low, persistence_high = bootstrap_skill_interval(
                observed,
                predicted,
                persistence,
                bootstrap_samples,
                seed=20_000 + 100 * month + list(MODEL_FEATURES).index(model),
            )
            incremental_skill = skill_against_reference(observed, predicted, ohc)
            incremental_low, incremental_high = bootstrap_skill_interval(
                observed,
                predicted,
                ohc,
                bootstrap_samples,
                seed=30_000 + 100 * month + list(MODEL_FEATURES).index(model),
            )
            rows.append(
                {
                    "init_month": month,
                    "model": model,
                    "n_test_years": len(current),
                    "rmse_c": rmse,
                    "mae_c": mae,
                    "correlation": correlation,
                    "skill_vs_persistence": persistence_skill,
                    "skill_vs_persistence_ci_2p5": persistence_low,
                    "skill_vs_persistence_ci_97p5": persistence_high,
                    "incremental_skill_vs_ohc": incremental_skill,
                    "incremental_skill_vs_ohc_ci_2p5": incremental_low,
                    "incremental_skill_vs_ohc_ci_97p5": incremental_high,
                }
            )
    return pd.DataFrame(rows)


def event_hindcasts(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for year, event in EVENTS.items():
        for month in range(1, 7):
            monthly = table.loc[table["month"].eq(month)].sort_values("year")
            test = monthly.loc[monthly["year"].eq(year)].iloc[0]
            train = monthly.loc[monthly["year"].lt(year)]
            for model, features in MODEL_FEATURES.items():
                prediction, observed = predict_fold(train, test, features)
                rows.append(
                    {
                        "event": event,
                        "year": year,
                        "init_month": month,
                        "model": model,
                        "prediction_ndj_residual_c": prediction,
                        "observed_ndj_residual_c": observed,
                    }
                )
    return pd.DataFrame(rows)


def matrix_from_skill(
    skill: pd.DataFrame,
    models: list[str],
    column: str,
) -> np.ndarray:
    matrix = np.full((len(models), 6), np.nan)
    for row_index, model in enumerate(models):
        current = skill.loc[skill["model"].eq(model)].set_index("init_month")
        for month in range(1, 7):
            matrix[row_index, month - 1] = current.loc[month, column]
    return matrix


def annotate_matrix(
    axis: plt.Axes,
    matrix: np.ndarray,
    skill: pd.DataFrame,
    models: list[str],
    value_column: str,
    low_column: str,
) -> None:
    for row_index, model in enumerate(models):
        current = skill.loc[skill["model"].eq(model)].set_index("init_month")
        for month in range(1, 7):
            value = matrix[row_index, month - 1]
            significant = current.loc[month, low_column] > 0
            label = f"{value:+.2f}{'*' if significant else ''}"
            color = "white" if abs(value) >= 0.32 else "0.1"
            axis.text(
                month - 1,
                row_index,
                label,
                ha="center",
                va="center",
                fontsize=8.2,
                color=color,
            )


def plot_skill_matrix(skill: pd.DataFrame) -> tuple[Path, Path]:
    single_matrix = matrix_from_skill(
        skill,
        SINGLE_MODELS,
        "skill_vs_persistence",
    )
    increment_matrix = matrix_from_skill(
        skill,
        INCREMENT_MODELS,
        "incremental_skill_vs_ohc",
    )
    norm = TwoSlopeNorm(vmin=-0.65, vcenter=0.0, vmax=0.65)
    cmap = mpl.colormaps["RdBu_r"]
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10.8, 8.7),
        gridspec_kw={"height_ratios": [1.45, 1.0]},
    )
    fig.subplots_adjust(
        left=0.31,
        right=0.90,
        top=0.88,
        bottom=0.12,
        hspace=0.34,
    )
    first = axes[0].imshow(single_matrix, cmap=cmap, norm=norm, aspect="auto")
    axes[0].set_title(
        "(a) Individual-variable skill relative to Niño-3.4 persistence",
        loc="left",
        fontweight="bold",
    )
    annotate_matrix(
        axes[0],
        single_matrix,
        skill,
        SINGLE_MODELS,
        "skill_vs_persistence",
        "skill_vs_persistence_ci_2p5",
    )

    axes[1].imshow(increment_matrix, cmap=cmap, norm=norm, aspect="auto")
    axes[1].set_title(
        "(b) Incremental skill after starting from central-Pacific OHC",
        loc="left",
        fontweight="bold",
    )
    annotate_matrix(
        axes[1],
        increment_matrix,
        skill,
        INCREMENT_MODELS,
        "incremental_skill_vs_ohc",
        "incremental_skill_vs_ohc_ci_2p5",
    )

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    for axis, models in zip(axes, (SINGLE_MODELS, INCREMENT_MODELS)):
        axis.set_xticks(np.arange(6), month_labels)
        axis.set_yticks(np.arange(len(models)), models)
        axis.tick_params(length=0)
        for spine in axis.spines.values():
            spine.set_linewidth(0.8)
            spine.set_color("0.3")
    axes[1].set_xlabel("Initialization month")
    colorbar_axis = fig.add_axes([0.925, 0.22, 0.018, 0.54])
    colorbar = fig.colorbar(first, cax=colorbar_axis)
    colorbar.set_label("RMSE skill (positive is better)")
    fig.suptitle(
        "Which variable adds useful information for NDJ Niño-3.4 prediction?",
        fontsize=14,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.035,
        "Walk-forward validation, 2000–2023. * marks a positive 95% bootstrap "
        "interval. All trends and scales are fitted using earlier training years only.",
        ha="center",
        va="bottom",
        fontsize=8.2,
        color="0.35",
    )
    png = OUT_FIG / "enso_ohc_d20_wind_olr_skill_matrix.png"
    pdf = OUT_FIG / "enso_ohc_d20_wind_olr_skill_matrix.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf


def write_summary(skill: pd.DataFrame, args: argparse.Namespace) -> Path:
    singles = skill.loc[
        skill["model"].isin(SINGLE_MODELS)
        & ~skill["model"].eq("Persistence (Niño-3.4)")
    ]
    single_average = (
        singles.groupby("model", as_index=False)["skill_vs_persistence"]
        .mean()
        .sort_values("skill_vs_persistence", ascending=False)
    )
    increments = skill.loc[skill["model"].isin(INCREMENT_MODELS)]
    increment_average = (
        increments.groupby("model", as_index=False)["incremental_skill_vs_ohc"]
        .mean()
        .sort_values("incremental_skill_vs_ohc", ascending=False)
    )
    best_single = single_average.iloc[0]
    best_increment = increment_average.iloc[0]
    best_single_month = singles.loc[singles["skill_vs_persistence"].idxmax()]
    best_increment_month = increments.loc[
        increments["incremental_skill_vs_ohc"].idxmax()
    ]
    may_ohc_wind = skill.loc[
        skill["model"].eq("OHC + u850") & skill["init_month"].eq(5)
    ].iloc[0]
    june_ohc_olr = skill.loc[
        skill["model"].eq("OHC + OLR") & skill["init_month"].eq(6)
    ].iloc[0]
    ohc_d20_average = float(
        increment_average.loc[
            increment_average["model"].eq("OHC + D20"),
            "incremental_skill_vs_ohc",
        ].iloc[0]
    )

    lines = [
        "# OHC + D20 + wind + OLR prediction analysis",
        "",
        "## Experiment",
        "",
        f"- Walk-forward verification: {args.test_start_year}–"
        f"{args.test_end_year}.",
        "- Target: November–January Niño-3.4 SST residual.",
        "- OHC: SODA3.15.2 0–300 m, central Pacific 5°S–5°N, "
        "180°–140°W.",
        "- D20: ORAS5 equatorial central-Pacific mean and east-minus-west "
        "thermocline slope.",
        "- Wind: ERA5 850-hPa zonal wind and ORAS5 zonal surface stress, "
        "160°E–140°W.",
        "- OLR: ERA5 outgoing longwave radiation, 5°S–5°N, 180°–140°W; "
        "positive OLR means weaker deep convection.",
        "- Prediction preprocessing uses training-fold trends and scaling, not "
        "the fixed event-figure climatology.",
        "",
        "## Main results",
        "",
        f"- Best individual predictor family on the January–June mean: "
        f"**{best_single['model']}**, mean skill versus persistence = "
        f"{best_single['skill_vs_persistence']:+.3f}.",
        f"- Strongest individual month: **{best_single_month['model']}**, "
        f"month {int(best_single_month['init_month'])}, skill = "
        f"{best_single_month['skill_vs_persistence']:+.3f}, 95% interval "
        f"{best_single_month['skill_vs_persistence_ci_2p5']:+.3f} to "
        f"{best_single_month['skill_vs_persistence_ci_97p5']:+.3f}.",
        f"- Best average addition after OHC: **{best_increment['model']}**, "
        f"mean incremental skill = "
        f"{best_increment['incremental_skill_vs_ohc']:+.3f}.",
        f"- Strongest single-month addition after OHC: "
        f"**{best_increment_month['model']}**, month "
        f"{int(best_increment_month['init_month'])}, incremental skill = "
        f"{best_increment_month['incremental_skill_vs_ohc']:+.3f}, "
        f"95% interval "
        f"{best_increment_month['incremental_skill_vs_ohc_ci_2p5']:+.3f} to "
        f"{best_increment_month['incremental_skill_vs_ohc_ci_97p5']:+.3f}.",
        f"- May OHC + u850: skill versus persistence = "
        f"{may_ohc_wind['skill_vs_persistence']:+.3f}; incremental skill "
        f"versus OHC = {may_ohc_wind['incremental_skill_vs_ohc']:+.3f} "
        f"(95% interval "
        f"{may_ohc_wind['incremental_skill_vs_ohc_ci_2p5']:+.3f} to "
        f"{may_ohc_wind['incremental_skill_vs_ohc_ci_97p5']:+.3f}).",
        f"- June OHC + OLR: skill versus persistence = "
        f"{june_ohc_olr['skill_vs_persistence']:+.3f}; incremental skill "
        f"versus OHC = {june_ohc_olr['incremental_skill_vs_ohc']:+.3f} "
        f"(95% interval "
        f"{june_ohc_olr['incremental_skill_vs_ohc_ci_2p5']:+.3f} to "
        f"{june_ohc_olr['incremental_skill_vs_ohc_ci_97p5']:+.3f}).",
        f"- OHC + D20 mean incremental skill is only "
        f"{ohc_d20_average:+.3f}, indicating substantial overlap between "
        "the two subsurface-ocean measures.",
        "",
        "## Interpretation rule",
        "",
        "- A variable is considered a promising addition only when its skill "
        "is positive across neighboring initialization months and its "
        "bootstrap interval is not dominated by zero.",
        "- These tests diagnose prediction information, not causal direction. "
        "D20, OHC, wind, and OLR are dynamically coupled and therefore not "
        "statistically independent.",
        "- For 2023, positive OHC/D20 signals coexisted with weak or easterly "
        "central-western Pacific wind anomalies and a much weaker convective "
        "response than in 1997 or 2015.  This supports an ocean-ready but "
        "atmospherically under-coupled interpretation.",
    ]
    path = OUT_DATA / "enso_ohc_d20_wind_olr_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    diagnostics = {
        "best_single_average_model": str(best_single["model"]),
        "best_single_average_skill": float(best_single["skill_vs_persistence"]),
        "best_increment_average_model": str(best_increment["model"]),
        "best_increment_average_skill": float(
            best_increment["incremental_skill_vs_ohc"]
        ),
    }
    (OUT_DATA / "enso_ohc_d20_wind_olr_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2),
        encoding="utf-8",
    )
    return path


def main() -> int:
    args = parse_args()
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    set_plot_style()

    table = build_input_table()
    validate_input_table(table)
    table_path = OUT_DATA / "enso_ohc_d20_wind_olr_prediction_inputs_1980_2023.csv"
    table.to_csv(table_path, index=False)

    predictions = walk_forward_predictions(
        table,
        args.test_start_year,
        args.test_end_year,
    )
    prediction_path = (
        OUT_DATA / "enso_ohc_d20_wind_olr_walkforward_predictions.csv"
    )
    predictions.to_csv(prediction_path, index=False)
    skill = summarize_skill(predictions, args.bootstrap_samples)
    skill_path = OUT_DATA / "enso_ohc_d20_wind_olr_walkforward_skill.csv"
    skill.to_csv(skill_path, index=False)

    events = event_hindcasts(table)
    event_path = OUT_DATA / "enso_ohc_d20_wind_olr_event_hindcasts.csv"
    events.to_csv(event_path, index=False)
    png, pdf = plot_skill_matrix(skill)
    summary = write_summary(skill, args)

    for path in (
        table_path,
        prediction_path,
        skill_path,
        event_path,
        png,
        pdf,
        summary,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
