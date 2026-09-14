#!/usr/bin/env python3
"""Complete the ENSO-type formation, decoupling, and predictability analysis.

This script closes three linked research questions.

1. Does the NMME operational hindcast archive show a stronger boreal-spring
   barrier for EP than CP El Nino?
2. Once an El Nino year is known, when does the developing event acquire
   useful information about its mature east-versus-central SST pattern?
3. Can observed spring air-sea coupling update an early NMME forecast of the
   SON SST pattern?

The analysis deliberately separates the usual Nino3-Nino4 box contrast from
an EOF-based flavor coordinate.  The latter follows the logic of the E/C
indices of Takahashi et al. (2011) and helps expose the strong confounding
between the box contrast and ENSO amplitude.

All event prediction tests are leave-one-event-out with fold-specific linear
detrending, predictor scaling, and ridge fitting.  The NMME update experiment
also includes a chronological expanding-window verification.  Coupling
residuals in that experiment are re-estimated inside every outer fold.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Iterable

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_complete_enso_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
RAW_NMME = ROOT / "data/raw/nmme_cpt/seasonal"
ERSST = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
OUT = ROOT / "outputs/research_2026/complete_enso_type_research"
REPORT = ROOT / "reports/ENSO类型形成_海气脱耦与春季预报障碍完整研究.md"

BASE_MONTHLY = DERIVED / "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
EVENT_BASE = DERIVED / "ep_cp_two_gate_event_summary_1982_2023.csv"
SODA_PROCESS = DERIVED / "soda3_transition_process_indices_1980_2024.csv"
ORAS_PROCESS = DERIVED / "oras5_transition_indices_1980_2024.csv"
COUPLING_MONTHLY = DERIVED / "enso_type_coupling_monthly_1982_2023.csv"
FULL_COUPLING_MONTHLY = (
    DERIVED / "enso_full_year_coupling_monthly_1982_2024.csv"
)
NMME_INDEX = DERIVED / "nmme_enso_type_hindcast_indices_1991_2020.csv"
NMME_BARRIER = DERIVED / "nmme_son_type_barrier_summary.csv"
NMME_ERROR_LINK = DERIVED / "nmme_son_error_predictor_correlations.csv"

EC_MONTHLY_CSV = DERIVED / "enso_ec_indices_1980_2024.csv"
EC_EVENT_CSV = DERIVED / "enso_ec_event_summary_1982_2023.csv"
EVENT_PRED_CSV = DERIVED / "enso_transition_checkpoint_loeo_predictions.csv"
EVENT_SKILL_CSV = DERIVED / "enso_transition_checkpoint_loeo_skill.csv"
EVENT_SENSITIVITY_CSV = (
    DERIVED / "enso_transition_checkpoint_sensitivity.csv"
)
NMME_EOF_CSV = DERIVED / "nmme_son_ec_flavor_hindcasts_1991_2020.csv"
NMME_EOF_SKILL_CSV = DERIVED / "nmme_son_ec_flavor_skill.csv"
NMME_EOF_BARRIER_CSV = DERIVED / "nmme_son_ec_flavor_barrier.csv"
NMME_UPDATE_PRED_CSV = DERIVED / "nmme_son_coupling_update_predictions.csv"
NMME_UPDATE_SKILL_CSV = DERIVED / "nmme_son_coupling_update_skill.csv"
DIAGNOSTICS_JSON = DERIVED / "complete_enso_type_research_diagnostics.json"

FIG1 = OUT / "fig1_type_definition_and_transition_checkpoint"
FIG2 = OUT / "fig2_nmme_barrier_and_coupling_update"
FIG3 = OUT / "fig3_event_pathway_comparison"

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
EXTREME_EP = (1982, 1997, 2015)
MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
RIDGE_ALPHA = 1.0
BOOTSTRAP_SAMPLES = 30_000
PERMUTATION_SAMPLES = 30_000

MODEL_LABELS = {
    "nmme": "NMME",
    "cfsv2": "CFSv2",
    "cmc1": "CanCM3",
    "cmc2": "CanCM4",
    "nasa": "GEOS-5",
    "ncar_ccsm4": "CCSM4",
    "ncar_cesm1": "CESM1",
}
INIT_LABELS = {3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul"}

EVENT_MODELS: dict[str, tuple[str, ...]] = {
    "SST persistence": ("init_type_raw_c",),
    "+ total WWV": ("init_type_raw_c", "wwv_1e14m3"),
    "+ FEP residual": ("init_type_raw_c", "fep_residual_c"),
    "+ SODA3 position": ("init_type_raw_c", "wwv_centroid_deg_e"),
    "+ ORAS5 position": ("init_type_raw_c", "oras_d20_centroid_deg_e"),
    "+ coupling": ("init_type_raw_c", "coupling_pattern_residual_z"),
    "SODA3 position + coupling": (
        "init_type_raw_c",
        "wwv_centroid_deg_e",
        "coupling_pattern_residual_z",
    ),
    "ORAS5 position + coupling": (
        "init_type_raw_c",
        "oras_d20_centroid_deg_e",
        "coupling_pattern_residual_z",
    ),
    "FEP + SODA3 position": (
        "init_type_raw_c",
        "fep_residual_c",
        "wwv_centroid_deg_e",
    ),
    "Bjerknes chain": (
        "init_type_raw_c",
        "sst_to_precip_residual_z",
        "precip_to_slp_residual_z",
        "slp_to_tau_residual_z",
    ),
}

UPDATE_MODELS: dict[str, tuple[str, ...]] = {
    "NMME": ("nmme_mar_apr_raw",),
    "NMME + Mar-Apr total WWV": ("nmme_mar_apr_raw", "wwv_mar_apr"),
    "NMME + Mar-Apr FEP": ("nmme_mar_apr_raw", "fep_fold"),
    "NMME + May-Jun ocean position": (
        "nmme_mar_apr_raw",
        "position_may_jun",
    ),
    "NMME + May-Jun coupling": ("nmme_mar_apr_raw", "coupling_fold"),
    "NMME + position + coupling": (
        "nmme_mar_apr_raw",
        "position_may_jun",
        "coupling_fold",
    ),
}

FILE_RE = re.compile(
    r"(?P<model>.+)_sst_hcst_(?P<init>[A-Z][a-z]{2})ic_"
    r"9-11_(?P<years>[0-9]{4}-[0-9]{4})\.txt$"
)
HEADER_RE = re.compile(
    r"cpt:T=(?P<target>[^,]+), cpt:S=(?P<start>[0-9]{4}-[0-9]{2}-[0-9]{2}), "
    r"cpt:nrow=(?P<nrow>[0-9]+), cpt:ncol=(?P<ncol>[0-9]+)"
)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.3,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "legend.fontsize": 7.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def ensure_inputs() -> None:
    paths = (
        ERSST,
        BASE_MONTHLY,
        EVENT_BASE,
        SODA_PROCESS,
        ORAS_PROCESS,
        COUPLING_MONTHLY,
        FULL_COUPLING_MONTHLY,
        NMME_INDEX,
        NMME_BARRIER,
        NMME_ERROR_LINK,
    )
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)


def linear_residual(
    train_years: np.ndarray,
    train_values: np.ndarray,
    test_year: float,
    test_value: float,
) -> tuple[np.ndarray, float]:
    design = np.column_stack([np.ones(len(train_years)), train_years])
    coefficients = np.linalg.lstsq(design, train_values, rcond=None)[0]
    train_residual = train_values - design @ coefficients
    test_residual = test_value - np.asarray([1.0, test_year]) @ coefficients
    return train_residual, float(test_residual)


def ridge_fold(
    train: pd.DataFrame,
    test: pd.Series,
    features: tuple[str, ...],
    target_column: str,
) -> tuple[float, float]:
    required = [target_column, *features]
    train = train.dropna(subset=required)
    if len(train) < 8 or test[required].isna().any():
        return math.nan, math.nan
    years = train["year"].to_numpy(dtype=float)
    test_year = float(test["year"])
    target, observed = linear_residual(
        years,
        train[target_column].to_numpy(dtype=float),
        test_year,
        float(test[target_column]),
    )
    columns: list[np.ndarray] = []
    test_values: list[float] = []
    for feature in features:
        residual, test_residual = linear_residual(
            years,
            train[feature].to_numpy(dtype=float),
            test_year,
            float(test[feature]),
        )
        scale = float(np.std(residual, ddof=1))
        if not np.isfinite(scale) or scale == 0:
            return math.nan, math.nan
        columns.append(residual / scale)
        test_values.append(test_residual / scale)
    x_train = np.column_stack(columns)
    coefficients = np.linalg.solve(
        x_train.T @ x_train + RIDGE_ALPHA * np.eye(x_train.shape[1]),
        x_train.T @ target,
    )
    return float(np.asarray(test_values) @ coefficients), observed


def paired_improvement_p(
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
    seed: int,
) -> float:
    improvement = (baseline - observed) ** 2 - (predicted - observed) ** 2
    observed_mean = float(np.mean(improvement))
    rng = np.random.default_rng(seed)
    signs = rng.choice(
        (-1.0, 1.0),
        size=(PERMUTATION_SAMPLES, len(improvement)),
    )
    null = np.mean(signs * improvement[None, :], axis=1)
    return float((np.sum(null >= observed_mean) + 1) / (len(null) + 1))


def bootstrap_skill(
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
    seed: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = rng.integers(
        0,
        len(observed),
        size=(BOOTSTRAP_SAMPLES, len(observed)),
    )
    rmse = np.sqrt(
        np.mean((predicted[samples] - observed[samples]) ** 2, axis=1)
    )
    baseline_rmse = np.sqrt(
        np.mean((baseline[samples] - observed[samples]) ** 2, axis=1)
    )
    skill = 1.0 - rmse / baseline_rmse
    return tuple(np.nanpercentile(skill, [2.5, 97.5]).astype(float))


def benjamini_hochberg(values: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna()
    if valid.empty:
        return output
    order = valid.sort_values().index
    ranked = valid.loc[order].to_numpy(dtype=float)
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output.loc[order] = np.minimum(adjusted, 1.0)
    return output


def compute_ec_indices() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Compute E/C-style indices and an orthogonal east-minus-central axis."""
    with xr.open_dataset(ERSST, engine="h5netcdf") as dataset:
        sst = (
            dataset["sst"]
            .sel(time=slice("1980-01-01", "2024-12-31"))
            .assign_coords(lon=dataset.lon % 360.0)
            .sortby("lon")
            .sortby("lat")
            .sel(lat=slice(-10.0, 10.0), lon=slice(120.0, 280.0))
            .load()
        )
    times = pd.DatetimeIndex(pd.to_datetime(sst.time.values))
    values = np.asarray(sst.to_numpy(), dtype=float)
    for month in range(1, 13):
        selected = np.flatnonzero(times.month == month)
        with np.errstate(invalid="ignore"):
            climatology = np.nanmean(values[selected], axis=0)
        values[selected] -= climatology
    decimal_year = (
        times.year.to_numpy(dtype=float)
        + (times.month.to_numpy(dtype=float) - 0.5) / 12.0
    )
    centered_year = decimal_year - decimal_year.mean()
    slope = np.nansum(
        values * centered_year[:, None, None], axis=0
    ) / np.sum(centered_year**2)
    values -= centered_year[:, None, None] * slope

    latitude_weights = np.sqrt(np.cos(np.deg2rad(sst.lat.values)))[:, None]
    weighted = (values * latitude_weights[None, :, :]).reshape(len(times), -1)
    valid = np.isfinite(weighted).all(axis=0)
    u, singular, vt = np.linalg.svd(weighted[:, valid], full_matrices=False)
    raw_pcs = u[:, :2] * singular[:2]
    pc_scale = raw_pcs.std(axis=0, ddof=1)
    pcs = raw_pcs / pc_scale

    anomaly = xr.DataArray(
        values,
        coords=sst.coords,
        dims=sst.dims,
    )

    def weighted_box(lon0: float, lon1: float) -> np.ndarray:
        region = anomaly.sel(
            lat=slice(-5.0, 5.0),
            lon=slice(lon0, lon1),
        )
        weights = np.cos(np.deg2rad(region.lat))
        return region.weighted(weights).mean(("lat", "lon")).to_numpy()

    nino3 = weighted_box(210.0, 270.0)
    nino4 = weighted_box(160.0, 210.0)
    nino34 = weighted_box(190.0, 240.0)
    if np.corrcoef(pcs[:, 0], nino34)[0, 1] < 0:
        pcs[:, 0] *= -1.0
        raw_pcs[:, 0] *= -1.0
        vt[0] *= -1.0
    type_box = nino3 - nino4
    sign2 = max(
        (-1.0, 1.0),
        key=lambda sign: np.corrcoef(-sign * pcs[:, 1], type_box)[0, 1],
    )
    oriented_pc2 = sign2 * pcs[:, 1]
    e_index = (pcs[:, 0] - oriented_pc2) / np.sqrt(2.0)
    c_index = (pcs[:, 0] + oriented_pc2) / np.sqrt(2.0)
    flavor = (e_index - c_index) / np.sqrt(2.0)
    monthly = pd.DataFrame(
        {
            "time": times,
            "year": times.year,
            "month": times.month,
            "pc1_amplitude": pcs[:, 0],
            "pc2_oriented": oriented_pc2,
            "e_index": e_index,
            "c_index": c_index,
            "ec_flavor_e_minus_c": flavor,
            "ersst_nino3_anom_c": nino3,
            "ersst_nino4_anom_c": nino4,
            "ersst_nino34_anom_c": nino34,
            "ersst_nino3_minus_nino4_c": type_box,
        }
    )

    rows = []
    for year in EVENT_YEARS:
        selected = monthly.loc[
            (
                monthly["year"].eq(year)
                & monthly["month"].eq(12)
            )
            | (
                monthly["year"].eq(year + 1)
                & monthly["month"].isin([1, 2])
            )
        ]
        if len(selected) != 3:
            raise ValueError(f"Incomplete DJF E/C target for {year}")
        row: dict[str, float | int | str] = {"year": year}
        for column in (
            "pc1_amplitude",
            "e_index",
            "c_index",
            "ec_flavor_e_minus_c",
            "ersst_nino34_anom_c",
            "ersst_nino3_minus_nino4_c",
        ):
            row[f"mature_djf_{column}"] = float(selected[column].mean())
        rows.append(row)
    event = pd.DataFrame(rows)

    eof2_full = np.full(weighted.shape[1], np.nan, dtype=float)
    eof2_full[valid] = -sign2 * vt[1] / pc_scale[1]
    metadata: dict[str, object] = {
        "lat": np.asarray(sst.lat.to_numpy(), dtype=float),
        "lon": np.asarray(sst.lon.to_numpy(), dtype=float),
        "valid_flat_mask": valid,
        "flavor_projection_weighted": eof2_full,
        "variance_fraction_pc1": float(
            singular[0] ** 2 / np.sum(singular**2)
        ),
        "variance_fraction_pc2": float(
            singular[1] ** 2 / np.sum(singular**2)
        ),
        "pc2_orientation_sign": float(sign2),
    }
    return monthly, event, metadata


def build_event_monthly(ec_event: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(BASE_MONTHLY)
    soda = pd.read_csv(SODA_PROCESS)
    oras = pd.read_csv(ORAS_PROCESS)
    coupling = pd.read_csv(COUPLING_MONTHLY)
    table = (
        base.merge(
            soda[
                [
                    "year",
                    "month",
                    "wwv_1e14m3",
                    "wwv_centroid_deg_e",
                    "wwv_east_fraction",
                ]
            ],
            on=["year", "month"],
            validate="one_to_one",
        )
        .merge(
            oras[
                [
                    "year",
                    "month",
                    "oras_d20_volume_proxy",
                    "oras_d20_centroid_deg_e",
                    "oras_d20_east_fraction",
                ]
            ],
            on=["year", "month"],
            validate="one_to_one",
        )
        .merge(
            coupling[
                [
                    "year",
                    "month",
                    "coupling_pattern_residual_z",
                    "coupling_intensity_residual_z",
                    "sst_to_precip_residual_z",
                    "precip_to_slp_residual_z",
                    "slp_to_tau_residual_z",
                ]
            ],
            on=["year", "month"],
            validate="one_to_one",
        )
        .merge(ec_event, on="year", validate="many_to_one")
    )
    return table.loc[table["year"].isin(EVENT_YEARS)].sort_values(
        ["year", "month"]
    )


def event_loeo_predictions(table: pd.DataFrame) -> pd.DataFrame:
    target_columns = {
        "Nino3-Nino4 box contrast": "mature_djf_type_raw_c",
        "orthogonal E-C flavor": "mature_djf_ec_flavor_e_minus_c",
    }
    rows = []
    for target_label, target_column in target_columns.items():
        for month in MONTHS:
            current = table.loc[table["month"].eq(month)]
            for year in EVENT_YEARS:
                test = current.loc[current["year"].eq(year)].iloc[0]
                train = current.loc[current["year"].ne(year)]
                for model, features in EVENT_MODELS.items():
                    prediction, observed = ridge_fold(
                        train,
                        test,
                        features,
                        target_column,
                    )
                    rows.append(
                        {
                            "target": target_label,
                            "year": year,
                            "month": month,
                            "model": model,
                            "prediction": prediction,
                            "observed": observed,
                            "n_training_events": len(train),
                            "ridge_alpha": RIDGE_ALPHA,
                        }
                    )
    return pd.DataFrame(rows)


def summarize_event_skill(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    seed = 810_000
    for (target, month), subset in predictions.groupby(["target", "month"]):
        baseline = (
            subset.loc[
                subset["model"].eq("SST persistence"),
                ["year", "prediction"],
            ]
            .set_index("year")["prediction"]
        )
        for model in EVENT_MODELS:
            current = (
                subset.loc[
                    subset["model"].eq(model),
                    ["year", "prediction", "observed"],
                ]
                .set_index("year")
                .join(baseline.rename("baseline"))
                .dropna()
            )
            observed = current["observed"].to_numpy(dtype=float)
            predicted = current["prediction"].to_numpy(dtype=float)
            reference = current["baseline"].to_numpy(dtype=float)
            rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
            baseline_rmse = float(
                np.sqrt(np.mean((reference - observed) ** 2))
            )
            skill = 1.0 - rmse / baseline_rmse
            if model == "SST persistence":
                p_value = ci_low = ci_high = math.nan
            else:
                p_value = paired_improvement_p(
                    observed,
                    predicted,
                    reference,
                    seed,
                )
                ci_low, ci_high = bootstrap_skill(
                    observed,
                    predicted,
                    reference,
                    seed + 10_000,
                )
            rows.append(
                {
                    "target": target,
                    "month": int(month),
                    "model": model,
                    "n_events": len(current),
                    "rmse": rmse,
                    "persistence_rmse": baseline_rmse,
                    "rmse_skill_vs_persistence": skill,
                    "bootstrap_skill_ci_low": ci_low,
                    "bootstrap_skill_ci_high": ci_high,
                    "prediction_observation_r": float(
                        np.corrcoef(predicted, observed)[0, 1]
                    ),
                    "sign_accuracy": float(
                        np.mean(np.sign(predicted) == np.sign(observed))
                    ),
                    "one_sided_paired_improvement_p": p_value,
                }
            )
            seed += 1
    output = pd.DataFrame(rows)
    for target, indices in output.groupby("target").groups.items():
        selected = output.loc[indices, "one_sided_paired_improvement_p"]
        output.loc[indices, "bh_fdr_q_within_target"] = benjamini_hochberg(
            selected
        )
    return output


def sensitivity_table(
    table: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    settings = (
        (
            "all 13 events",
            set(EVENT_YEARS),
            "Nino3-Nino4 box contrast",
            "SODA3 position + coupling",
            4,
        ),
        (
            "all 13 events, independent ocean",
            set(EVENT_YEARS),
            "Nino3-Nino4 box contrast",
            "ORAS5 position + coupling",
            4,
        ),
        (
            "orthogonal E-C target",
            set(EVENT_YEARS),
            "orthogonal E-C flavor",
            "SODA3 position + coupling",
            4,
        ),
        (
            "orthogonal E-C target, independent ocean",
            set(EVENT_YEARS),
            "orthogonal E-C flavor",
            "ORAS5 position + coupling",
            4,
        ),
    )
    rng_seed = 830_000
    for label, years, target, model, month in settings:
        current = predictions.loc[
            predictions["target"].eq(target)
            & predictions["month"].eq(month)
            & predictions["year"].isin(years)
        ]
        model_data = current.loc[
            current["model"].eq(model),
            ["year", "prediction", "observed"],
        ].set_index("year")
        baseline = current.loc[
            current["model"].eq("SST persistence"),
            ["year", "prediction"],
        ].set_index("year")
        joined = model_data.join(baseline, rsuffix="_baseline")
        observed = joined["observed"].to_numpy(dtype=float)
        predicted = joined["prediction"].to_numpy(dtype=float)
        reference = joined["prediction_baseline"].to_numpy(dtype=float)
        ci_low, ci_high = bootstrap_skill(
            observed,
            predicted,
            reference,
            rng_seed,
        )
        rows.append(
            {
                "setting": label,
                "target": target,
                "model": model,
                "month": month,
                "n_events": len(joined),
                "rmse_skill_vs_persistence": 1.0
                - np.sqrt(np.mean((predicted - observed) ** 2))
                / np.sqrt(np.mean((reference - observed) ** 2)),
                "bootstrap_skill_ci_low": ci_low,
                "bootstrap_skill_ci_high": ci_high,
                "prediction_observation_r": float(
                    np.corrcoef(predicted, observed)[0, 1]
                ),
                "sign_accuracy": float(
                    np.mean(np.sign(predicted) == np.sign(observed))
                ),
            }
        )
        rng_seed += 1

    # Refit the April checkpoint after removing the three extreme EP events.
    retained = tuple(year for year in EVENT_YEARS if year not in EXTREME_EP)
    for source, feature in (
        ("SODA3", "wwv_centroid_deg_e"),
        ("ORAS5", "oras_d20_centroid_deg_e"),
    ):
        current = table.loc[
            table["year"].isin(retained) & table["month"].eq(4)
        ]
        prediction_rows = []
        for year in retained:
            train = current.loc[current["year"].ne(year)]
            test = current.loc[current["year"].eq(year)].iloc[0]
            baseline, observed = ridge_fold(
                train,
                test,
                ("init_type_raw_c",),
                "mature_djf_type_raw_c",
            )
            prediction, _ = ridge_fold(
                train,
                test,
                (
                    "init_type_raw_c",
                    feature,
                    "coupling_pattern_residual_z",
                ),
                "mature_djf_type_raw_c",
            )
            prediction_rows.append((observed, baseline, prediction))
        values = np.asarray(prediction_rows, dtype=float)
        observed = values[:, 0]
        reference = values[:, 1]
        predicted = values[:, 2]
        ci_low, ci_high = bootstrap_skill(
            observed,
            predicted,
            reference,
            rng_seed,
        )
        rows.append(
            {
                "setting": f"exclude 1982, 1997, 2015 ({source})",
                "target": "Nino3-Nino4 box contrast",
                "model": f"{source} position + coupling",
                "month": 4,
                "n_events": len(values),
                "rmse_skill_vs_persistence": 1.0
                - np.sqrt(np.mean((predicted - observed) ** 2))
                / np.sqrt(np.mean((reference - observed) ** 2)),
                "bootstrap_skill_ci_low": ci_low,
                "bootstrap_skill_ci_high": ci_high,
                "prediction_observation_r": float(
                    np.corrcoef(predicted, observed)[0, 1]
                ),
                "sign_accuracy": float(
                    np.mean(np.sign(predicted) == np.sign(observed))
                ),
            }
        )
        rng_seed += 1
    return pd.DataFrame(rows)


def parse_nmme_regional_file(
    path: Path,
    target_lat: np.ndarray,
    target_lon: np.ndarray,
) -> tuple[str, int, np.ndarray, np.ndarray]:
    match_file = FILE_RE.match(path.name)
    if match_file is None:
        raise ValueError(f"Unrecognized SON forecast file: {path.name}")
    model = match_file.group("model")
    init_month = {
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
    }[match_file.group("init")]
    fields = []
    years = []
    latitude_lookup = {round(float(value), 6): i for i, value in enumerate(target_lat)}
    with path.open(encoding="utf-8") as handle:
        iterator = iter(handle)
        for line in iterator:
            if not line.startswith("cpt:field="):
                continue
            match = HEADER_RE.search(line)
            if match is None:
                raise ValueError(f"Cannot parse CPT header in {path}")
            start = pd.Timestamp(match.group("start"))
            nrow = int(match.group("nrow"))
            ncol = int(match.group("ncol"))
            all_lon = np.asarray(next(iterator).strip().split(), dtype=float)
            if len(all_lon) != ncol:
                raise ValueError(f"Bad longitude header in {path}")
            lon_indices = [
                int(np.flatnonzero(np.isclose(all_lon, value))[0])
                for value in target_lon
            ]
            field = np.full((len(target_lat), len(target_lon)), np.nan)
            for _ in range(nrow):
                parts = next(iterator).strip().split()
                latitude = round(float(parts[0]), 6)
                if latitude in latitude_lookup:
                    values = np.asarray(parts[1:], dtype=float)
                    selected = values[lon_indices]
                    selected[selected <= -900.0] = np.nan
                    field[latitude_lookup[latitude], :] = selected
            fields.append(field)
            years.append(start.year)
    result = np.asarray(fields, dtype=float)
    if result.shape != (30, len(target_lat), len(target_lon)):
        raise ValueError(f"Unexpected regional shape for {path}: {result.shape}")
    if np.isnan(result).all(axis=0).any():
        # Land points are handled by the ERSST ocean mask later; all-ocean
        # missing points would be caught during projection.
        pass
    return model, init_month, np.asarray(years, dtype=int), result


def detrend_grid(years: np.ndarray, values: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        output = values - np.nanmean(values, axis=0)
    centered = years.astype(float) - years.mean()
    denominator = np.sum(centered**2)
    slope = np.nansum(output * centered[:, None, None], axis=0) / denominator
    return output - centered[:, None, None] * slope


def son_observed_flavor(ec_monthly: pd.DataFrame) -> pd.DataFrame:
    son = (
        ec_monthly.loc[
            ec_monthly["year"].between(1991, 2020)
            & ec_monthly["month"].isin([9, 10, 11])
        ]
        .groupby("year", as_index=False)["ec_flavor_e_minus_c"]
        .mean()
        .rename(columns={"ec_flavor_e_minus_c": "observed_ec_flavor"})
    )
    years = son["year"].to_numpy(dtype=float)
    values = son["observed_ec_flavor"].to_numpy(dtype=float)
    residual, _ = linear_residual(
        years,
        values,
        float(years[-1]),
        float(values[-1]),
    )
    son["observed_ec_flavor_dt"] = residual
    return son


def project_nmme_ec_flavor(
    ec_monthly: pd.DataFrame,
    metadata: dict[str, object],
) -> pd.DataFrame:
    target_lat = np.asarray(metadata["lat"], dtype=float)
    target_lon = np.asarray(metadata["lon"], dtype=float)
    projection = np.asarray(
        metadata["flavor_projection_weighted"], dtype=float
    )
    latitude_weights = np.sqrt(np.cos(np.deg2rad(target_lat)))[:, None]
    observed = son_observed_flavor(ec_monthly)
    event_labels = pd.read_csv(EVENT_BASE)[
        [
            "event_year",
            "event_label",
            "mature_djf_type_index_c",
            "mature_djf_nino34_c",
        ]
    ].rename(columns={"event_year": "year"})
    event_labels["box_group"] = np.select(
        [
            event_labels["mature_djf_type_index_c"] >= 0.2,
            event_labels["mature_djf_type_index_c"] <= -0.2,
        ],
        ["EP", "CP"],
        default="borderline",
    )
    files = sorted(RAW_NMME.glob("*_sst_hcst_*ic_9-11_1991-2020.txt"))
    expected_files = 35
    if len(files) != expected_files:
        raise ValueError(
            f"Expected {expected_files} SON files, found {len(files)}"
        )
    rows = []
    for index, path in enumerate(files, start=1):
        print(
            f"Projecting NMME E/C flavor [{index:02d}/{len(files):02d}] "
            f"{path.name}",
            flush=True,
        )
        model, init_month, years, raw = parse_nmme_regional_file(
            path,
            target_lat,
            target_lon,
        )
        anomaly = detrend_grid(years, raw)
        weighted = (anomaly * latitude_weights[None, :, :]).reshape(
            len(years), -1
        )
        valid_projection = np.isfinite(projection)
        valid_forecast = np.isfinite(weighted).all(axis=0)
        valid = valid_projection & valid_forecast
        retained_norm = float(np.sum(projection[valid] ** 2))
        full_norm = float(np.sum(projection[valid_projection] ** 2))
        if retained_norm / full_norm < 0.90:
            raise ValueError(
                f"More than 10% of the E/C projection is unavailable in {path}"
            )
        # Coastal masks differ slightly between ERSST and the forecast models.
        # Renormalize the retained projection so these few points do not
        # artificially reduce forecast amplitude.
        normalization = math.sqrt(full_norm / retained_norm)
        forecast = weighted[:, valid] @ projection[valid] * normalization
        for year, value in zip(years, forecast, strict=True):
            rows.append(
                {
                    "model": model,
                    "init_month": init_month,
                    "year": int(year),
                    "forecast_ec_flavor_dt": float(value),
                }
            )
    output = (
        pd.DataFrame(rows)
        .merge(observed, on="year", validate="many_to_one")
        .merge(event_labels, on="year", how="left", validate="many_to_one")
    )
    output["is_warm_event"] = output["event_label"].notna()
    output["ec_flavor_error"] = (
        output["forecast_ec_flavor_dt"]
        - output["observed_ec_flavor_dt"]
    )
    output["abs_ec_flavor_error"] = output["ec_flavor_error"].abs()
    return output


def summarize_nmme_ec(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for (model, init_month), group in data.groupby(["model", "init_month"]):
        result = stats.pearsonr(
            group["forecast_ec_flavor_dt"],
            group["observed_ec_flavor_dt"],
        )
        rows.append(
            {
                "model": model,
                "init_month": int(init_month),
                "n_years": len(group),
                "ec_flavor_acc": float(result.statistic),
                "ec_flavor_acc_p": float(result.pvalue),
                "ec_flavor_rmse": float(
                    np.sqrt(np.mean(group["ec_flavor_error"] ** 2))
                ),
            }
        )
    skill = pd.DataFrame(rows)

    event_rows = []
    warm = data.loc[
        data["is_warm_event"] & data["box_group"].isin(["EP", "CP"])
    ]
    for keys, group in warm.groupby(
        ["model", "year", "event_label", "box_group"]
    ):
        errors = group.set_index("init_month")["abs_ec_flavor_error"]
        event_rows.append(
            {
                "model": keys[0],
                "year": int(keys[1]),
                "event_label": keys[2],
                "box_group": keys[3],
                "early_error": float(errors.reindex([3, 4]).mean()),
                "late_error": float(errors.reindex([6, 7]).mean()),
                "spring_penalty": float(
                    errors.reindex([3, 4]).mean()
                    - errors.reindex([6, 7]).mean()
                ),
            }
        )
    event = pd.DataFrame(event_rows)
    barrier = (
        event.groupby(["model", "box_group"], as_index=False)
        .agg(
            n_events=("year", "count"),
            early_error=("early_error", "mean"),
            late_error=("late_error", "mean"),
            spring_penalty=("spring_penalty", "mean"),
        )
    )
    return skill, barrier


def build_nmme_update_base() -> tuple[pd.DataFrame, pd.DataFrame]:
    nmme = pd.read_csv(NMME_INDEX)
    selected = nmme.loc[
        nmme["model"].eq("nmme")
        & nmme["target_season"].eq("SON")
        & nmme["init_month"].isin([3, 4])
    ].copy()
    selected["forecast_type_raw"] = (
        selected["forecast_nino3_raw_c"]
        - selected["forecast_nino4_raw_c"]
    )
    selected["observed_type_raw"] = (
        selected["observed_nino3_raw_c"]
        - selected["observed_nino4_raw_c"]
    )
    annual = (
        selected.groupby("event_year", as_index=False)
        .agg(
            nmme_mar_apr_raw=("forecast_type_raw", "mean"),
            target_son_type_raw=("observed_type_raw", "mean"),
            warm_event=("is_warm_event", "max"),
            box_group=("enso_type_group", "first"),
        )
        .rename(columns={"event_year": "year"})
    )
    base = pd.read_csv(BASE_MONTHLY)
    soda = pd.read_csv(SODA_PROCESS)
    coupling = pd.read_csv(FULL_COUPLING_MONTHLY)
    monthly = (
        base.merge(
            soda[
                [
                    "year",
                    "month",
                    "wwv_1e14m3",
                    "wwv_centroid_deg_e",
                ]
            ],
            on=["year", "month"],
            validate="one_to_one",
        )
        .merge(
            coupling,
            on=["year", "month"],
            suffixes=("", "_coupling"),
            validate="one_to_one",
        )
    )
    aggregates = []
    for year in annual["year"]:
        current = monthly.loc[monthly["year"].eq(year)]
        mar_apr = current.loc[current["month"].isin([3, 4])]
        may_jun = current.loc[current["month"].isin([5, 6])]
        aggregates.append(
            {
                "year": int(year),
                "wwv_mar_apr": float(mar_apr["wwv_1e14m3"].mean()),
                "position_may_jun": float(
                    may_jun["wwv_centroid_deg_e"].mean()
                ),
            }
        )
    annual = annual.merge(
        pd.DataFrame(aggregates),
        on="year",
        validate="one_to_one",
    )
    return annual, monthly


def fold_residual_feature(
    monthly: pd.DataFrame,
    train_years: list[int],
    test_year: int,
    months: Iterable[int],
    response: str,
    predictors: tuple[str, ...],
) -> tuple[pd.Series, float]:
    training_output: dict[int, list[float]] = {
        int(year): [] for year in train_years
    }
    test_output = []
    centered_year = float(np.mean(train_years))
    for month in months:
        train = monthly.loc[
            monthly["year"].isin(train_years)
            & monthly["month"].eq(month)
        ].sort_values("year")
        test = monthly.loc[
            monthly["year"].eq(test_year)
            & monthly["month"].eq(month)
        ].iloc[0]
        design = np.column_stack(
            [
                np.ones(len(train)),
                train["year"].to_numpy(dtype=float) - centered_year,
                *[
                    train[column].to_numpy(dtype=float)
                    for column in predictors
                ],
            ]
        )
        test_design = np.asarray(
            [
                1.0,
                float(test_year) - centered_year,
                *[float(test[column]) for column in predictors],
            ]
        )
        target = train[response].to_numpy(dtype=float)
        coefficients = np.linalg.lstsq(design, target, rcond=None)[0]
        residual = target - design @ coefficients
        degrees = max(1, design.shape[1])
        scale = float(np.std(residual, ddof=degrees))
        if not np.isfinite(scale) or scale == 0:
            raise ValueError(f"Degenerate fold residual for {response}, {month}")
        train_z = residual / scale
        test_z = (
            float(test[response]) - float(test_design @ coefficients)
        ) / scale
        for year, value in zip(train["year"], train_z, strict=True):
            training_output[int(year)].append(float(value))
        test_output.append(float(test_z))
    return (
        pd.Series(
            {
                year: float(np.mean(values))
                for year, values in training_output.items()
            }
        ),
        float(np.mean(test_output)),
    )


def prepare_update_fold(
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    test_year: int,
    mode: str,
) -> tuple[pd.DataFrame, pd.Series] | None:
    if mode == "leave-one-year-out":
        train = annual.loc[annual["year"].ne(test_year)].copy()
    elif mode == "expanding-window":
        train = annual.loc[annual["year"].lt(test_year)].copy()
    else:
        raise ValueError(mode)
    if len(train) < 12:
        return None
    test = annual.loc[annual["year"].eq(test_year)].iloc[0].copy()
    train_years = train["year"].astype(int).tolist()

    fep_train, fep_test = fold_residual_feature(
        monthly,
        train_years,
        test_year,
        (3, 4),
        "fep_raw_c",
        ("nino34_raw_c",),
    )
    coupling_parts = []
    coupling_tests = []
    for response in (
        "precip_tropical_pacific_raw_mmday",
        "slp_drive_w_minus_e_raw_hpa",
        "tau_cwp_raw_nm2",
    ):
        current_train, current_test = fold_residual_feature(
            monthly,
            train_years,
            test_year,
            (5, 6),
            response,
            ("nino34_raw_c", "sst_type_raw_c"),
        )
        coupling_parts.append(current_train.rename(response))
        coupling_tests.append(current_test)
    train = train.set_index("year")
    train["fep_fold"] = fep_train
    train["coupling_fold"] = pd.concat(coupling_parts, axis=1).mean(axis=1)
    train = train.reset_index()
    test["fep_fold"] = fep_test
    test["coupling_fold"] = float(np.mean(coupling_tests))
    return train, test


def nmme_update_predictions(
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for mode in ("leave-one-year-out", "expanding-window"):
        for test_year in annual["year"].astype(int):
            prepared = prepare_update_fold(
                annual,
                monthly,
                test_year,
                mode,
            )
            if prepared is None:
                continue
            train, test = prepared
            for model, features in UPDATE_MODELS.items():
                prediction, observed = ridge_fold(
                    train,
                    test,
                    features,
                    "target_son_type_raw",
                )
                rows.append(
                    {
                        "validation": mode,
                        "year": test_year,
                        "warm_event": bool(test["warm_event"]),
                        "box_group": test["box_group"],
                        "model": model,
                        "prediction": prediction,
                        "observed": observed,
                        "n_training_years": len(train),
                    }
                )
    return pd.DataFrame(rows)


def summarize_update_skill(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    seed = 860_000
    for validation in predictions["validation"].unique():
        validation_data = predictions.loc[
            predictions["validation"].eq(validation)
        ]
        for sample, sample_data in (
            ("all years", validation_data),
            (
                "warm events",
                validation_data.loc[validation_data["warm_event"]],
            ),
        ):
            baseline = (
                sample_data.loc[
                    sample_data["model"].eq("NMME"),
                    ["year", "prediction"],
                ]
                .set_index("year")["prediction"]
            )
            for model in UPDATE_MODELS:
                current = (
                    sample_data.loc[
                        sample_data["model"].eq(model),
                        ["year", "prediction", "observed"],
                    ]
                    .set_index("year")
                    .join(baseline.rename("baseline"))
                    .dropna()
                )
                observed = current["observed"].to_numpy(dtype=float)
                predicted = current["prediction"].to_numpy(dtype=float)
                reference = current["baseline"].to_numpy(dtype=float)
                rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
                base_rmse = float(
                    np.sqrt(np.mean((reference - observed) ** 2))
                )
                if model == "NMME":
                    ci_low = ci_high = p_value = math.nan
                else:
                    ci_low, ci_high = bootstrap_skill(
                        observed,
                        predicted,
                        reference,
                        seed,
                    )
                    p_value = paired_improvement_p(
                        observed,
                        predicted,
                        reference,
                        seed + 10_000,
                    )
                rows.append(
                    {
                        "validation": validation,
                        "sample": sample,
                        "model": model,
                        "n_test": len(current),
                        "rmse": rmse,
                        "nmme_rmse": base_rmse,
                        "rmse_skill_vs_nmme": 1.0 - rmse / base_rmse,
                        "bootstrap_skill_ci_low": ci_low,
                        "bootstrap_skill_ci_high": ci_high,
                        "prediction_observation_r": float(
                            np.corrcoef(predicted, observed)[0, 1]
                        ),
                        "sign_accuracy": float(
                            np.mean(np.sign(predicted) == np.sign(observed))
                        ),
                        "one_sided_paired_improvement_p": p_value,
                    }
                )
                seed += 1
    output = pd.DataFrame(rows)
    for keys, indices in output.groupby(["validation", "sample"]).groups.items():
        output.loc[indices, "bh_fdr_q_within_family"] = benjamini_hochberg(
            output.loc[indices, "one_sided_paired_improvement_p"]
        )
    return output


def plot_figure1(
    ec_event: pd.DataFrame,
    event_base: pd.DataFrame,
    skill: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    event = event_base.rename(columns={"event_year": "year"}).merge(
        ec_event,
        on="year",
        validate="one_to_one",
    )
    colors = np.where(
        event["mature_djf_type_index_c"] >= 0.2,
        "#C84C3A",
        np.where(
            event["mature_djf_type_index_c"] <= -0.2,
            "#2670A8",
            "#8A8A8A",
        ),
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.3, 8.8), constrained_layout=True)

    ax = axes[0, 0]
    ax.scatter(
        event["mature_djf_nino34_c"],
        event["mature_djf_type_index_c"],
        c=colors,
        s=58,
        edgecolor="white",
        linewidth=0.6,
    )
    for row in event.itertuples():
        ax.annotate(
            str(row.year),
            (row.mature_djf_nino34_c, row.mature_djf_type_index_c),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7.2,
        )
    correlation = float(
        np.corrcoef(
            event["mature_djf_nino34_c"],
            event["mature_djf_type_index_c"],
        )[0, 1]
    )
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set(
        title="(a) The box-type index is strongly amplitude-confounded",
        xlabel="Mature DJF Niño3.4 anomaly (°C)",
        ylabel="Mature DJF Niño3 − Niño4 (°C)",
    )
    ax.text(
        0.03,
        0.95,
        f"r = {correlation:.2f}",
        transform=ax.transAxes,
        va="top",
        weight="bold",
    )
    ax.grid(color="#E5E5E5", lw=0.6)

    ax = axes[0, 1]
    ax.scatter(
        event["mature_djf_c_index"],
        event["mature_djf_e_index"],
        c=colors,
        s=58,
        edgecolor="white",
        linewidth=0.6,
    )
    for row in event.itertuples():
        ax.annotate(
            str(row.year),
            (row.mature_djf_c_index, row.mature_djf_e_index),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7.2,
        )
    limits = [
        min(
            event["mature_djf_c_index"].min(),
            event["mature_djf_e_index"].min(),
        )
        - 0.2,
        max(
            event["mature_djf_c_index"].max(),
            event["mature_djf_e_index"].max(),
        )
        + 0.2,
    ]
    ax.plot(limits, limits, color="#777777", ls="--", lw=1.0)
    ax.set(
        title="(b) E/C view exposes hybrid and definition-sensitive events",
        xlabel="Mature DJF C index",
        ylabel="Mature DJF E index",
        xlim=limits,
        ylim=limits,
    )
    ax.grid(color="#E5E5E5", lw=0.6)

    ax = axes[1, 0]
    specifications = (
        (
            "Nino3-Nino4 box contrast",
            "SODA3 position + coupling",
            "#009E73",
            "SODA3, box target",
        ),
        (
            "Nino3-Nino4 box contrast",
            "ORAS5 position + coupling",
            "#0072B2",
            "ORAS5, box target",
        ),
        (
            "orthogonal E-C flavor",
            "SODA3 position + coupling",
            "#E69F00",
            "SODA3, E−C target",
        ),
        (
            "orthogonal E-C flavor",
            "ORAS5 position + coupling",
            "#CC79A7",
            "ORAS5, E−C target",
        ),
    )
    for target, model, color, label in specifications:
        current = skill.loc[
            skill["target"].eq(target) & skill["model"].eq(model)
        ].sort_values("month")
        ax.plot(
            current["month"],
            current["rmse_skill_vs_persistence"],
            marker="o",
            lw=2.0,
            color=color,
            label=label,
        )
    ax.axhline(0, color="#333333", lw=0.9)
    ax.axvline(4, color="#777777", lw=1.0, ls="--")
    ax.axvspan(3, 5, color="#F2D7A7", alpha=0.25)
    ax.set(
        title="(c) Fixed ocean-position + coupling checkpoint",
        xlabel="Information available through month",
        ylabel="LOEO RMSE skill vs SST persistence",
        xticks=MONTHS,
        xticklabels=MONTH_LABELS,
    )
    ax.legend(frameon=False, ncol=2)
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    ax = axes[1, 1]
    plot = sensitivity.copy()
    y = np.arange(len(plot))
    values = plot["rmse_skill_vs_persistence"].to_numpy(dtype=float)
    lower = values - plot["bootstrap_skill_ci_low"].to_numpy(dtype=float)
    upper = plot["bootstrap_skill_ci_high"].to_numpy(dtype=float) - values
    bar_colors = [
        "#2670A8" if "ORAS5" in label else "#009E73"
        for label in plot["setting"]
    ]
    ax.errorbar(
        values,
        y,
        xerr=np.vstack([lower, upper]),
        fmt="none",
        ecolor="#444444",
        capsize=3,
        lw=1.2,
    )
    ax.scatter(values, y, c=bar_colors, s=55, zorder=3)
    ax.axvline(0, color="#333333", lw=0.9)
    ax.set(
        title="(d) April checkpoint emerges, but is regime-dependent",
        xlabel="LOEO RMSE skill vs SST persistence",
        yticks=y,
        yticklabels=plot["setting"],
    )
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    fig.suptitle(
        "ENSO type formation: definition, transition timing, and robustness",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.5,
        -0.015,
        "Warm-event sample: 13 NOAA El Niño episodes, 1982–2023. "
        "Ocean position is the warm-volume/D20 centroid; coupling is the "
        "observed response residual after SST amplitude and pattern are included. "
        "All prediction statistics are leave-one-event-out.",
        ha="center",
        fontsize=8.2,
    )
    for extension in ("png", "pdf"):
        fig.savefig(
            f"{FIG1}.{extension}",
            dpi=400 if extension == "png" else None,
            bbox_inches="tight",
        )
    plt.close(fig)


def plot_figure2(
    nmme_eof_skill: pd.DataFrame,
    update_skill: pd.DataFrame,
) -> None:
    box_skill = pd.read_csv(DERIVED / "nmme_enso_type_barrier_skill.csv")
    box_nmme = box_skill.loc[
        box_skill["model"].eq("nmme")
        & box_skill["target_season"].eq("SON")
    ].sort_values("init_month")
    eof_nmme = nmme_eof_skill.loc[
        nmme_eof_skill["model"].eq("nmme")
    ].sort_values("init_month")
    barrier = pd.read_csv(NMME_BARRIER)
    barrier = barrier.loc[barrier["model"].eq("nmme")]
    eof_barrier = pd.read_csv(NMME_EOF_BARRIER_CSV)
    eof_barrier = eof_barrier.loc[eof_barrier["model"].eq("nmme")]
    links = pd.read_csv(NMME_ERROR_LINK)
    links = links.loc[links["error_metric"].eq("early_abs_type_error_c")]
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.5), constrained_layout=True)

    ax = axes[0, 0]
    ax.plot(
        box_nmme["init_month"],
        box_nmme["nino34_acc"],
        marker="s",
        color="#2670A8",
        lw=2.0,
        label="Niño3.4 amplitude",
    )
    ax.plot(
        box_nmme["init_month"],
        box_nmme["type_acc"],
        marker="o",
        color="#C84C3A",
        lw=2.0,
        label="Niño3 − Niño4",
    )
    ax.plot(
        eof_nmme["init_month"],
        eof_nmme["ec_flavor_acc"],
        marker="^",
        color="#7B3294",
        lw=2.0,
        label="Orthogonal E−C flavor",
    )
    ax.axvspan(3, 5, color="#F2D7A7", alpha=0.25)
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set(
        title="(a) Fixed SON target: pattern skill lags amplitude skill",
        ylabel="Anomaly correlation",
        xticks=list(INIT_LABELS),
        xticklabels=[INIT_LABELS[m] for m in INIT_LABELS],
        ylim=(-0.3, 1.0),
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    ax = axes[0, 1]
    groups = ["EP", "CP"]
    x = np.arange(2)
    width = 0.34
    box_values = [
        float(
            barrier.loc[
                barrier["enso_type_group"].eq(group),
                "spring_penalty_mean_c",
            ].iloc[0]
        )
        for group in groups
    ]
    eof_values = [
        float(
            eof_barrier.loc[
                eof_barrier["box_group"].eq(group),
                "spring_penalty",
            ].iloc[0]
        )
        for group in groups
    ]
    ax.bar(
        x - width / 2,
        box_values,
        width,
        color="#C84C3A",
        label="Niño3 − Niño4 error",
    )
    ax.bar(
        x + width / 2,
        eof_values,
        width,
        color="#7B3294",
        label="E−C flavor error",
    )
    ax.axhline(0, color="#333333", lw=0.9)
    ax.set(
        title="(b) EP−CP barrier comparison depends on type definition",
        ylabel="Mar–Apr error minus Jun–Jul error",
        xticks=x,
        xticklabels=groups,
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#E5E5E5", lw=0.6)

    ax = axes[1, 0]
    current = update_skill.loc[
        update_skill["validation"].eq("expanding-window")
        & update_skill["sample"].eq("all years")
    ].copy()
    order = list(UPDATE_MODELS)
    current["model"] = pd.Categorical(current["model"], order, ordered=True)
    current = current.sort_values("model")
    colors = [
        "#777777",
        "#56B4E9",
        "#E69F00",
        "#009E73",
        "#7B3294",
        "#CC79A7",
    ]
    values = current["rmse_skill_vs_nmme"].to_numpy(dtype=float)
    ax.barh(np.arange(len(current)), values, color=colors)
    ci_low = current["bootstrap_skill_ci_low"].to_numpy(dtype=float)
    ci_high = current["bootstrap_skill_ci_high"].to_numpy(dtype=float)
    ci_low = np.where(np.isfinite(ci_low), ci_low, values)
    ci_high = np.where(np.isfinite(ci_high), ci_high, values)
    ax.errorbar(
        values,
        np.arange(len(current)),
        xerr=np.vstack([values - ci_low, ci_high - values]),
        fmt="none",
        ecolor="#333333",
        capsize=3,
        lw=1.0,
    )
    ax.axvline(0, color="#333333", lw=0.9)
    ax.set(
        title="(c) Observed coupling is the leading candidate update",
        xlabel="Expanding-window RMSE skill vs calibrated NMME",
        yticks=np.arange(len(current)),
        yticklabels=current["model"],
    )
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    ax = axes[1, 1]
    selected_names = [
        "may_jun_pattern_coupling_residual_z",
        "east_ocean_state_z",
        "mar_apr_fep_residual_c",
        "d140_mar_apr_z",
        "q140_mar_apr_z",
    ]
    current = (
        links.loc[links["predictor"].isin(selected_names)]
        .set_index("predictor")
        .reindex(selected_names)
        .reset_index()
    )
    label_map = {
        "may_jun_pattern_coupling_residual_z": "May–Jun coupling residual",
        "east_ocean_state_z": "East-ocean state",
        "mar_apr_fep_residual_c": "Mar–Apr FEP residual",
        "d140_mar_apr_z": "Mar–Apr D20 at 140°W",
        "q140_mar_apr_z": "Mar–Apr Q20 at 140°W",
    }
    y = np.arange(len(current))
    ax.barh(
        y,
        current["partial_r_controlling_type_and_nino34"],
        color=["#7B3294", "#009E73", "#E69F00", "#56B4E9", "#2670A8"],
    )
    ax.axvline(0, color="#333333", lw=0.9)
    ax.set(
        title="(d) What early NMME type errors are tied to",
        xlabel="Partial correlation with absolute type error",
        yticks=y,
        yticklabels=[label_map[value] for value in current["predictor"]],
        xlim=(0, 0.9),
    )
    ax.invert_yaxis()
    ax.grid(axis="x", color="#E5E5E5", lw=0.6)

    fig.suptitle(
        "Operational evidence: spring barrier and a coupling-based update",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.5,
        -0.015,
        "NOAA NMME SST hindcasts, 1991–2020; ERSSTv5 verification. "
        "The update experiment predicts SON Niño3−Niño4 and rebuilds the "
        "May–June coupling expectation inside every validation fold. "
        "Panel (c) bars show 95% event-block bootstrap intervals.",
        ha="center",
        fontsize=8.2,
    )
    for extension in ("png", "pdf"):
        fig.savefig(
            f"{FIG2}.{extension}",
            dpi=400 if extension == "png" else None,
            bbox_inches="tight",
        )
    plt.close(fig)


def plot_figure3(
    event_monthly: pd.DataFrame,
    ec_event: pd.DataFrame,
) -> None:
    years = (1997, 2015, 2023)
    colors = {1997: "#9E0142", 2015: "#D95F0E", 2023: "#2C7FB8"}
    variables = (
        ("wwv_1e14m3", "Total warm-water volume (10¹⁴ m³)"),
        ("wwv_centroid_deg_e", "Warm-volume centroid (°E)"),
        ("fep_residual_c", "FEP SST residual (°C)"),
        ("coupling_pattern_residual_z", "Air–sea coupling residual (z)"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(11.7, 7.8), constrained_layout=True)
    for ax, (column, ylabel) in zip(axes.ravel(), variables, strict=True):
        for year in years:
            current = event_monthly.loc[event_monthly["year"].eq(year)]
            ax.plot(
                current["month"],
                current[column],
                marker="o",
                lw=2.0,
                color=colors[year],
                label=str(year),
            )
        ax.axhline(0, color="#555555", lw=0.8)
        ax.axvspan(3, 5, color="#F2D7A7", alpha=0.25)
        ax.set(
            xlabel="Developing-year month",
            ylabel=ylabel,
            xticks=MONTHS,
            xticklabels=MONTH_LABELS,
        )
        ax.grid(color="#E5E5E5", lw=0.6)
    axes[0, 0].set_title("(a) Reservoir")
    axes[0, 1].set_title("(b) Eastward redistribution")
    axes[1, 0].set_title("(c) Surface FEP route")
    axes[1, 1].set_title("(d) Atmospheric realization")
    axes[0, 0].legend(frameon=False, ncol=3)
    event_targets = ec_event.set_index("year")
    subtitle = "; ".join(
        [
            (
                f"{year}: E−C={event_targets.loc[year, 'mature_djf_ec_flavor_e_minus_c']:+.2f}"
            )
            for year in years
        ]
    )
    fig.suptitle(
        "Three pathways to a warm event are not dynamically identical",
        fontsize=15,
        weight="bold",
    )
    fig.text(
        0.5,
        -0.015,
        f"{subtitle}. Positive E−C is more east-focused. "
        "The 2023 event combines a strong surface-FEP route with weaker "
        "atmospheric realization and a hybrid E/C mature pattern.",
        ha="center",
        fontsize=8.2,
    )
    for extension in ("png", "pdf"):
        fig.savefig(
            f"{FIG3}.{extension}",
            dpi=400 if extension == "png" else None,
            bbox_inches="tight",
        )
    plt.close(fig)


def build_report(
    ec_event: pd.DataFrame,
    event_skill: pd.DataFrame,
    sensitivity: pd.DataFrame,
    nmme_ec_skill: pd.DataFrame,
    nmme_ec_barrier: pd.DataFrame,
    update_skill: pd.DataFrame,
    diagnostics: dict[str, object],
) -> str:
    box_corr = diagnostics["type_definition"]["box_type_vs_nino34_r"]
    ec_corr = diagnostics["type_definition"]["ec_flavor_vs_nino34_r"]
    transition = diagnostics["transition_checkpoint"]
    barrier = diagnostics["nmme_barrier"]
    update = diagnostics["nmme_update"]
    ec_nmme = nmme_ec_barrier.loc[nmme_ec_barrier["model"].eq("nmme")]
    ec_ep_penalty = float(
        ec_nmme.loc[
            ec_nmme["box_group"].eq("EP"),
            "spring_penalty",
        ].iloc[0]
    )
    ec_cp_penalty = float(
        ec_nmme.loc[
            ec_nmme["box_group"].eq("CP"),
            "spring_penalty",
        ].iloc[0]
    )
    lines = [
        "# ENSO类型形成、海气脱耦与春季预报障碍：完整研究",
        "",
        "## 摘要",
        "",
        "本研究把此前的SODA3/ORAS5海洋过程诊断、ERA5/GPCP海气耦合诊断和",
        "NOAA NMME业务回报试验放入同一条验证链。核心结论不是存在一个能够普遍",
        "决定EP/CP类型的单一阈值，而是存在两个连续关口：海洋暖量是否向东重分配，",
        "以及大气风—降水—气压反馈是否在春季以后接上。",
        "",
        f"传统Niño3−Niño4成熟期类型指标与Niño3.4强度的相关达到"
        f" **r={box_corr:.2f}**；正交E−C型指标把相关降低至"
        f" **r={ec_corr:.2f}**。因此，总热含量与传统类型指标的高相关不能全部解释为",
        "暖中心位置的可预报性，其中包含强事件更容易成为东部型的幅度效应。",
        "",
        "## 1. 研究问题与假设",
        "",
        "1. NMME中EP事件跨越春季时，类型误差是否比CP下降得更明显？",
        "2. 在已知当年将发展为El Niño的条件下，何时才能稳定判断暖中心位置？",
        "3. FEP先增暖而大气未跟随时，哪一环节最能解释模式类型误差？",
        "4. 把观测到的春季海气耦合状态加入早期NMME预报，是否具有增量技巧？",
        "",
        "## 2. 数据",
        "",
        "- NOAA ERSSTv5：1980–2024气候态、EOF型指数和NMME验证；",
        "- SODA3.15.2：1980–2024，暖水体积、暖量重心、热收支和输运；",
        "- ORAS5：独立验证D20暖水重心及东传通道；",
        "- OISST、ERA5和GPCP：FEP、低层风、风应力、降水与气压响应；",
        "- NOAA NMME：1991–2020季节SST回报，固定SON目标。",
        "",
        "## 3. 类型定义与防止强度混淆",
        "",
        "主报告沿用Niño3−Niño4，便于与既有图件和事件标签保持一致。敏感性检验",
        "使用Takahashi等提出的E/C逻辑：对1980–2024年、10°S–10°N、",
        "120°E–80°W的月SST距平做面积加权EOF，将前两个标准化PC旋转为E和C；",
        "进一步使用(E−C)/√2作为东部相对中部的正交型坐标。",
        "",
        "1982和1997在E方向非常突出；2015接近E/C混合；2023的Niño3−Niño4为正，",
        "但E−C为负，说明2023对“EP”的判断对分类方法敏感。它更准确的描述是",
        "东部偏暖但成熟型态混合、同时大气耦合偏弱。",
        "",
        "## 4. 春季预报障碍",
        "",
        f"按既有Niño3−Niño4分型，NMME的EP春季惩罚为"
        f" **{barrier['ep_penalty_c']:+.2f} °C**，CP为"
        f" **{barrier['cp_penalty_c']:+.2f} °C**，EP−CP为"
        f" **{barrier['difference_c']:+.2f} °C**。事件Bootstrap 95%区间为"
        f" [{barrier['ci_low_c']:+.2f}, {barrier['ci_high_c']:+.2f}] °C。",
        "点估计支持EP春季障碍更强，但每组只有3个事件，不能当成稳定显著结论。",
        "",
        "EOF型投影进一步表明，NMME对暖中心位置的技巧低于Niño3.4幅度技巧；",
        f"把验证量换成正交E−C暖中心位置后，按同一批箱式标签分组得到的春季惩罚",
        f"反而是CP **{ec_cp_penalty:+.2f}**、EP **{ec_ep_penalty:+.2f}**。",
        "也就是说，EP/CP谁更受春季障碍影响会随类型定义改变。这说明当前结果应写成",
        "“NMME存在明显的春季类型定位困难”，而不应写成已经普遍证明",
        "“所有EP事件都比CP更难预测”。",
        "",
        "## 5. 转变点：四月是候选检查点，不是普适阈值",
        "",
        f"使用同一个“当前SST型 + 暖量重心 + 海气耦合残差”模型逐月做13事件",
        f"留一法后，SODA3在四月首次得到正且Bootstrap区间不跨零的技巧："
        f" **skill={transition['soda_box_skill']:+.2f}**，符号正确率"
        f" **{transition['soda_box_sign']:.0%}**。ORAS5替代海洋重心后为"
        f" **skill={transition['oras_box_skill']:+.2f}**，符号正确率"
        f" **{transition['oras_box_sign']:.0%}**。",
        "",
        f"换成正交E−C目标后，四月技巧仍为SODA3"
        f" **{transition['soda_ec_skill']:+.2f}**、ORAS5"
        f" **{transition['oras_ec_skill']:+.2f}**，说明四月信号不是完全由",
        "Niño3−Niño4定义造成的。但剔除1982、1997和2015后，该“重心+耦合”",
        "模型不再稳定。这意味着四月更像强EP非线性分支的检查点，而不是适用于",
        "所有中等或混合事件的硬阈值。",
        "",
        "阶段分解显示：二月至三月，总暖水体积主要提供事件强度和蓄能信息；",
        "四月至五月，暖量重心和140°W附近D20开始描述热量是否真正进入中东太平洋；",
        "六月以后，SST→降水→气压→风应力链条决定海洋潜力是否被大气兑现。",
        "",
        "## 6. 海气脱耦与业务预报更新",
        "",
        "在NMME暖事件中，早春SON类型绝对误差与5–6月耦合残差的偏相关为",
        f" **r={diagnostics['coupling_error_link']['partial_r']:.2f}**",
        f"（p={diagnostics['coupling_error_link']['partial_p']:.3f}），强于控制事件",
        "强度后的单独Q20/D20联系。",
        "",
        f"严格的逐年扩展窗口试验中，在3–4月NMME预报之后加入5–6月观测耦合状态，",
        f"SON类型RMSE相对NMME降低 **{update['walk_skill']:.0%}**，预测—观测相关",
        f"由 **{update['walk_nmme_r']:.2f}** 提高到"
        f" **{update['walk_coupling_r']:.2f}**。留一年法的改进为"
        f" **{update['loyo_skill']:.0%}**。耦合期望关系在每个外层验证折内重算，",
        "因此不是把全时段回归关系泄漏进测试年。",
        "",
        f"不确定性检验显示，留一年法95%区间为"
        f" [{update['loyo_skill_ci'][0]:+.0%}, {update['loyo_skill_ci'][1]:+.0%}]，",
        f"而年代顺序扩展窗口区间为"
        f" [{update['walk_skill_ci'][0]:+.0%}, {update['walk_skill_ci'][1]:+.0%}]，仍跨零。",
        "因此耦合量是当前最有希望的春末动力预报更新量，并得到严格时间外推的同向",
        "支持，但还不是已经确立的业务增益。它不取代海洋热含量，也不能单独充当",
        "提前数月的类型触发器。",
        "",
        "## 7. 1997、2015与2023的解释",
        "",
        "- 1997：总暖量大、暖量重心迅速东移，随后耦合链完整，是典型强EP非线性分支；",
        "- 2015：海洋和大气均较强，但E/C指标显示成熟形态比Niño3−Niño4标签更混合；",
        "- 2023：FEP表层路径很强，深层输运—储存指标却未给出同等强的EP信号，",
        "  而大气耦合偏弱；因此海洋仍可形成强暖事件，但成熟空间型态和典型",
        "  Bjerknes反馈不同步。",
        "",
        "## 8. 与权威研究的对应关系和本研究增量",
        "",
        "- Takahashi et al. (2011)证明ENSO的东部和中部变化应在正交E/C坐标中",
        "  分开。本研究的关键修正是把这一分型直接用于NMME空间场验证，并发现",
        "  “EP障碍更强”的判断并不对类型指标稳健。",
        "- Fang & Mu (2018)的完美模式试验指出海洋温跃层状态和西太平洋风异常",
        "  都是ENSO可预报性的必要组成。本研究的“向东重分配—大气兑现”双关口",
        "  与其一致，但本研究是观测/回报诊断，不能替代因果扰动试验。",
        "- Li et al. (2024)把大气Bjerknes反馈拆为SST—降水加热—气压—风应力。",
        "  本研究沿同一过程链构造型态调整后的耦合残差，并首次在本项目中检验它",
        "  对NMME类型预报是否提供折外增量。",
        "- Kim et al. (2025)、Jiang et al. (2026)和Fan et al. (2026)分别从",
        "  西部暖水/风演变、FEP残余增暖与多年La Niña背景解释2023的非经典路径。",
        "  本研究把这些机制放在1997、2015、2023同一诊断坐标中，结果支持2023",
        "  是“强表面FEP路线+弱大气兑现+混合成熟型”，而非典型EP的弱版本。",
        "- 既有研究提出EP更受春季障碍、CP更受夏季障碍；本研究确认NMME的",
        "  暖中心位置技巧确实落后于振幅技巧，但也表明EP—CP差异会被分型指标、",
        "  极端事件和小样本显著改变。",
        "",
        "本研究真正新增的是一套可否证的统一检验：同一成熟目标、两种类型定义、",
        "SODA3/ORAS5海洋替代量、事件留一法、NMME空间场投影和年代顺序更新试验。",
        "它把机制解释推进到预报验证，但没有宣称找到了普适触发阈值或完成因果证明。",
        "",
        "## 9. 可以作结的内容",
        "",
        "可以作结：",
        "",
        "1. 只看FEP或总热含量不足以判定EP；",
        "2. 类型形成需要区分蓄能、向东重分配和大气兑现三个阶段；",
        "3. 四月是强EP分支中可重复出现的候选转折检查点；",
        "4. 海气耦合状态是修正早春动力模式暖中心位置的首要候选更新量；",
        "5. 2023代表表层东部先暖但耦合偏弱的混合路径，而不是1997的弱化复制。",
        "",
        "尚不能作结：",
        "",
        "1. 尚未发现适用于所有EP/CP事件的单一数值阈值；",
        "2. 13个事件不足以稳定估计非线性分类边界；",
        "3. 当前观测回归不能证明大气耦合残差的因果来源；",
        "4. 年代顺序检验的增量技巧区间仍跨零，需要独立年份或更长回报确认；",
        "5. CP夏季预报障碍仍需更长回报或专门完美模式试验。",
        "",
        "## 10. 输出文件",
        "",
        f"- 图1：`{FIG1.relative_to(ROOT)}.pdf`",
        f"- 图2：`{FIG2.relative_to(ROOT)}.pdf`",
        f"- 图3：`{FIG3.relative_to(ROOT)}.pdf`",
        f"- E/C月指数：`{EC_MONTHLY_CSV.relative_to(ROOT)}`",
        f"- 事件逐月留一预测：`{EVENT_PRED_CSV.relative_to(ROOT)}`",
        f"- NMME耦合更新预测：`{NMME_UPDATE_PRED_CSV.relative_to(ROOT)}`",
        f"- 完整诊断：`{DIAGNOSTICS_JSON.relative_to(ROOT)}`",
        "",
        "## 11. 主要资料与文献",
        "",
        "- SODA3.15.2: https://www.soda.umd.edu/",
        "- NOAA NMME: https://www.cpc.ncep.noaa.gov/products/NMME/data.html",
        "- Takahashi et al. (2011): https://doi.org/10.1029/2011GL047364",
        "- Fang & Mu (2018): https://www.nature.com/articles/s41598-018-28964-z",
        "- Li et al. (2024): https://doi.org/10.1029/2024GL109874",
        "- Kim et al. (2025): https://doi.org/10.1038/s41612-024-00890-0",
        "- Jiang et al. (2026): https://doi.org/10.1029/2026GL123227",
        "- Fan et al. (2026): https://doi.org/10.59717/j.xinn-geo.2026.100224",
        "- Zhao et al. (2022): https://doi.org/10.1029/2022GL099488",
        "- Pang et al. (2023): https://doi.org/10.1029/2023GL106673",
        "- Hou et al.: EP春季与CP夏季预报障碍研究，"
        "https://link.springer.com/article/10.1007/s00382-019-04888-w",
    ]
    return "\n".join(lines) + "\n"


def validate_outputs(
    event_skill: pd.DataFrame,
    nmme_ec: pd.DataFrame,
    update_predictions: pd.DataFrame,
) -> None:
    if event_skill.isna().all(axis=1).any():
        raise ValueError("Empty event-skill row")
    if len(nmme_ec) != 35 * 30:
        raise ValueError(f"Unexpected NMME E/C rows: {len(nmme_ec)}")
    if update_predictions["validation"].nunique() != 2:
        raise ValueError("Both update validation designs are required")
    for stem in (FIG1, FIG2, FIG3):
        for extension in ("png", "pdf"):
            path = Path(f"{stem}.{extension}")
            if not path.exists() or path.stat().st_size < 10_000:
                raise ValueError(f"Missing or small figure: {path}")


def main() -> None:
    ensure_inputs()
    setup_style()

    print("Computing ERSSTv5 E/C indices", flush=True)
    ec_monthly, ec_event, ec_metadata = compute_ec_indices()
    ec_monthly.to_csv(EC_MONTHLY_CSV, index=False)
    ec_event.to_csv(EC_EVENT_CSV, index=False)

    print("Running event-level sequential prediction tests", flush=True)
    event_monthly = build_event_monthly(ec_event)
    event_predictions = event_loeo_predictions(event_monthly)
    event_skill = summarize_event_skill(event_predictions)
    sensitivity = sensitivity_table(event_monthly, event_predictions)
    event_predictions.to_csv(EVENT_PRED_CSV, index=False)
    event_skill.to_csv(EVENT_SKILL_CSV, index=False)
    sensitivity.to_csv(EVENT_SENSITIVITY_CSV, index=False)

    print("Projecting NMME SST maps onto the orthogonal E-C coordinate", flush=True)
    nmme_ec = project_nmme_ec_flavor(ec_monthly, ec_metadata)
    nmme_ec_skill, nmme_ec_barrier = summarize_nmme_ec(nmme_ec)
    nmme_ec.to_csv(NMME_EOF_CSV, index=False)
    nmme_ec_skill.to_csv(NMME_EOF_SKILL_CSV, index=False)
    nmme_ec_barrier.to_csv(NMME_EOF_BARRIER_CSV, index=False)

    print("Running fold-specific NMME coupling-update experiments", flush=True)
    update_annual, update_monthly = build_nmme_update_base()
    update_predictions = nmme_update_predictions(
        update_annual,
        update_monthly,
    )
    update_skill = summarize_update_skill(update_predictions)
    update_predictions.to_csv(NMME_UPDATE_PRED_CSV, index=False)
    update_skill.to_csv(NMME_UPDATE_SKILL_CSV, index=False)

    event_base = pd.read_csv(EVENT_BASE)
    type_join = event_base.merge(
        ec_event,
        left_on="event_year",
        right_on="year",
        validate="one_to_one",
    )
    box_nino34_r = float(
        np.corrcoef(
            type_join["mature_djf_type_index_c"],
            type_join["mature_djf_nino34_c"],
        )[0, 1]
    )
    ec_nino34_r = float(
        np.corrcoef(
            type_join["mature_djf_ec_flavor_e_minus_c"],
            type_join["mature_djf_ersst_nino34_anom_c"],
        )[0, 1]
    )

    def event_metric(
        target: str,
        model: str,
        month: int,
        column: str,
    ) -> float:
        return float(
            event_skill.loc[
                event_skill["target"].eq(target)
                & event_skill["model"].eq(model)
                & event_skill["month"].eq(month),
                column,
            ].iloc[0]
        )

    box_barrier = pd.read_csv(NMME_BARRIER)
    box_barrier = box_barrier.loc[box_barrier["model"].eq("nmme")]
    bootstrap = json.loads(
        (DERIVED / "nmme_enso_type_barrier_diagnostics.json").read_text()
    )["bootstrap"]
    error_link = pd.read_csv(NMME_ERROR_LINK)
    error_link = error_link.loc[
        error_link["error_metric"].eq("early_abs_type_error_c")
        & error_link["predictor"].eq(
            "may_jun_pattern_coupling_residual_z"
        )
    ].iloc[0]
    walk_update = update_skill.loc[
        update_skill["validation"].eq("expanding-window")
        & update_skill["sample"].eq("all years")
    ]
    loyo_update = update_skill.loc[
        update_skill["validation"].eq("leave-one-year-out")
        & update_skill["sample"].eq("all years")
    ]
    walk_nmme = walk_update.loc[walk_update["model"].eq("NMME")].iloc[0]
    walk_coupling = walk_update.loc[
        walk_update["model"].eq("NMME + May-Jun coupling")
    ].iloc[0]
    loyo_coupling = loyo_update.loc[
        loyo_update["model"].eq("NMME + May-Jun coupling")
    ].iloc[0]
    diagnostics = {
        "method": {
            "climatology": "1980-2024 for observational E/C indices",
            "event_validation": "leave one El Nino episode out",
            "nmme_validation": [
                "leave one year out",
                "chronological expanding window",
            ],
            "target_primary": "mature DJF Nino3 minus Nino4",
            "target_sensitivity": "orthogonal ERSSTv5 E minus C flavor",
            "ridge_alpha": RIDGE_ALPHA,
        },
        "type_definition": {
            "box_type_vs_nino34_r": box_nino34_r,
            "ec_flavor_vs_nino34_r": ec_nino34_r,
            "pc1_variance_fraction": ec_metadata["variance_fraction_pc1"],
            "pc2_variance_fraction": ec_metadata["variance_fraction_pc2"],
        },
        "transition_checkpoint": {
            "earliest_robust_month": 4,
            "soda_box_skill": event_metric(
                "Nino3-Nino4 box contrast",
                "SODA3 position + coupling",
                4,
                "rmse_skill_vs_persistence",
            ),
            "soda_box_sign": event_metric(
                "Nino3-Nino4 box contrast",
                "SODA3 position + coupling",
                4,
                "sign_accuracy",
            ),
            "oras_box_skill": event_metric(
                "Nino3-Nino4 box contrast",
                "ORAS5 position + coupling",
                4,
                "rmse_skill_vs_persistence",
            ),
            "oras_box_sign": event_metric(
                "Nino3-Nino4 box contrast",
                "ORAS5 position + coupling",
                4,
                "sign_accuracy",
            ),
            "soda_ec_skill": event_metric(
                "orthogonal E-C flavor",
                "SODA3 position + coupling",
                4,
                "rmse_skill_vs_persistence",
            ),
            "oras_ec_skill": event_metric(
                "orthogonal E-C flavor",
                "ORAS5 position + coupling",
                4,
                "rmse_skill_vs_persistence",
            ),
            "regime_dependence": "checkpoint loses skill when 1982, 1997, and 2015 are removed",
        },
        "nmme_barrier": {
            "ep_penalty_c": float(
                box_barrier.loc[
                    box_barrier["enso_type_group"].eq("EP"),
                    "spring_penalty_mean_c",
                ].iloc[0]
            ),
            "cp_penalty_c": float(
                box_barrier.loc[
                    box_barrier["enso_type_group"].eq("CP"),
                    "spring_penalty_mean_c",
                ].iloc[0]
            ),
            "difference_c": float(bootstrap["ep_minus_cp_mean_c"]),
            "ci_low_c": float(bootstrap["ep_minus_cp_ci_low_c"]),
            "ci_high_c": float(bootstrap["ep_minus_cp_ci_high_c"]),
            "probability_ep_greater": float(
                bootstrap["probability_ep_penalty_greater_than_cp"]
            ),
        },
        "nmme_ec_flavor_barrier": {
            "ep_penalty": float(
                nmme_ec_barrier.loc[
                    nmme_ec_barrier["model"].eq("nmme")
                    & nmme_ec_barrier["box_group"].eq("EP"),
                    "spring_penalty",
                ].iloc[0]
            ),
            "cp_penalty": float(
                nmme_ec_barrier.loc[
                    nmme_ec_barrier["model"].eq("nmme")
                    & nmme_ec_barrier["box_group"].eq("CP"),
                    "spring_penalty",
                ].iloc[0]
            ),
            "grouping_note": "groups retain the original Nino3-minus-Nino4 event labels",
        },
        "coupling_error_link": {
            "partial_r": float(
                error_link[
                    "partial_r_controlling_type_and_nino34"
                ]
            ),
            "partial_p": float(
                error_link[
                    "partial_p_controlling_type_and_nino34"
                ]
            ),
            "n_events": int(error_link["n"]),
        },
        "nmme_update": {
            "walk_skill": float(walk_coupling["rmse_skill_vs_nmme"]),
            "walk_skill_ci": [
                float(walk_coupling["bootstrap_skill_ci_low"]),
                float(walk_coupling["bootstrap_skill_ci_high"]),
            ],
            "walk_nmme_r": float(walk_nmme["prediction_observation_r"]),
            "walk_coupling_r": float(
                walk_coupling["prediction_observation_r"]
            ),
            "loyo_skill": float(loyo_coupling["rmse_skill_vs_nmme"]),
            "loyo_skill_ci": [
                float(loyo_coupling["bootstrap_skill_ci_low"]),
                float(loyo_coupling["bootstrap_skill_ci_high"]),
            ],
        },
        "sample_sizes": {
            "warm_events": len(EVENT_YEARS),
            "nmme_years": 30,
            "nmme_son_files_projected": 35,
        },
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Rendering final figures and report", flush=True)
    plot_figure1(ec_event, event_base, event_skill, sensitivity)
    plot_figure2(nmme_ec_skill, update_skill)
    plot_figure3(event_monthly, ec_event)
    REPORT.write_text(
        build_report(
            ec_event,
            event_skill,
            sensitivity,
            nmme_ec_skill,
            nmme_ec_barrier,
            update_skill,
            diagnostics,
        ),
        encoding="utf-8",
    )
    validate_outputs(event_skill, nmme_ec, update_predictions)
    print(f"Wrote report: {REPORT}", flush=True)
    print(f"Wrote diagnostics: {DIAGNOSTICS_JSON}", flush=True)


if __name__ == "__main__":
    main()
