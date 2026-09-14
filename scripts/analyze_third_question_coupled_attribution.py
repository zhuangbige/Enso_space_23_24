#!/usr/bin/env python3
"""Quantify the coupled attribution behind the third warm-heat-fate question.

The analysis joins four previously separate diagnostics for the same 13 warm
events (1982--2023):

1. far-eastern-Pacific (FEP) surface warming;
2. March--April central-Pacific 0--300 m OHC preconditioning;
3. May--June ERA5 850-hPa westerly response;
4. following-January--May 5N Q20 fate from SODA3.

It also performs a local, offline wind-stress swap among the 1997, 2015, and
2023 events.  Temperature, geostrophic transport, and the diagnosed residual
are held fixed while the 5N zonal-wind-stress anomaly is replaced.  The result
is a process attribution, not a coupled-model causal experiment.
"""

from __future__ import annotations

import json
import importlib.machinery
import os
from pathlib import Path
import sys
import types

RUNTIME_CACHE = Path("/private/tmp/codex_third_question_attribution")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, "/Users/daiyue/.codex/skills/climate-plotting/scripts")

# The Anaconda netCDF4 extension on this machine links to a missing libjpeg.8.
# These imported analysis modules only need numerical helper functions from the
# downloader module, not netCDF4.Dataset.  A stub keeps the import read-only;
# all local NetCDF files below are opened explicitly with h5netcdf.
if "netCDF4" not in sys.modules:
    netcdf4_stub = types.ModuleType("netCDF4")
    netcdf4_stub.__spec__ = importlib.machinery.ModuleSpec("netCDF4", loader=None)
    sys.modules["netCDF4"] = netcdf4_stub

import analyze_1997_2015_2023_5n_geostrophic_fate as fate  # noqa: E402
import analyze_soda3_5n_current_decomposition as dec  # noqa: E402
from analyze_jiang_soda3_transition import (  # noqa: E402
    MONTHS,
    SST_BASELINE,
    oisst_path,
    same_month_residual,
    weighted_box_mean,
)
from climate_plot_style import add_panel_labels, apply_climate_style  # noqa: E402


DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/third_question_coupled_attribution"
PDF_DIR = ROOT / "output/pdf"

MINIMAL_EVENT_CSV = DERIVED / "soda3_ohc_coupling_minimal_event_table.csv"
PERTURBATION_EVENT_CSV = DERIVED / "enso_perturbation_event_indices_1982_2023.csv"

EVENT_TABLE_CSV = DERIVED / "third_question_coupled_attribution_event_table.csv"
RELATIONSHIP_CSV = DERIVED / "third_question_coupled_attribution_relationships.csv"
MODEL_CSV = DERIVED / "third_question_coupled_attribution_models.csv"
COUNTERFACTUAL_CSV = DERIVED / "third_question_coupled_attribution_counterfactual.csv"
DIAGNOSTICS_JSON = DERIVED / "third_question_coupled_attribution_diagnostics.json"

FIGURE_PNG = OUT / "Fig08_third_question_coupled_attribution.png"
FIGURE_PDF = PDF_DIR / "third_question_coupled_attribution.pdf"
REPORT_MD = OUT / "THIRD_QUESTION_COUPLED_ATTRIBUTION_CN.md"

BASELINE = (1980, 2014)
BASELINE_TAG = "b1980_2014"
HIGHLIGHT_YEARS = (1997, 2015, 2023)
COLORS = {1997: "#B33E3E", 2015: "#D17A18", 2023: "#2166AC"}
BOOTSTRAP_SAMPLES = 20_000
PERMUTATION_SAMPLES = 50_000
RNG_SEED = 20260805


def zscore(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return (values - np.nanmean(values)) / np.nanstd(values, ddof=1)


def integrate_zj(values_pw: np.ndarray, times: pd.DatetimeIndex) -> float:
    seconds = times.days_in_month.to_numpy(dtype=float) * 86400.0
    return float(np.nansum(np.asarray(values_pw, dtype=float) * seconds) / 1.0e6)


def bh_fdr(p_values: np.ndarray) -> np.ndarray:
    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    ranked = p_values[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0.0, 1.0)
    return result


def bootstrap_correlation(
    x: np.ndarray,
    y: np.ndarray,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = RNG_SEED,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    values: list[float] = []
    for _ in range(samples):
        index = rng.integers(0, len(x), len(x))
        if np.std(x[index]) == 0.0 or np.std(y[index]) == 0.0:
            continue
        values.append(float(np.corrcoef(x[index], y[index])[0, 1]))
    return tuple(np.percentile(values, [2.5, 97.5]).tolist())


def permutation_p(
    x: np.ndarray,
    y: np.ndarray,
    samples: int = PERMUTATION_SAMPLES,
    seed: int = RNG_SEED,
) -> float:
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    observed = abs(float(np.corrcoef(x, y)[0, 1]))
    exceed = 0
    for _ in range(samples):
        trial = abs(float(np.corrcoef(x, rng.permutation(y))[0, 1]))
        exceed += int(trial >= observed)
    return float((exceed + 1) / (samples + 1))


def build_all_event_fate(monthly: pd.DataFrame, event_years: list[int]) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for event_year in event_years:
        decay_year = event_year + 1
        selected = monthly.loc[
            monthly.year.eq(decay_year) & monthly.month.between(1, 5)
        ].sort_values("time")
        if len(selected) != 5:
            raise ValueError(f"Incomplete following Jan-May for event {event_year}")
        times = pd.DatetimeIndex(selected.time)
        row: dict[str, float | int] = {
            "year": event_year,
            "decay_year": decay_year,
        }
        for metric in (
            "total",
            "ekman",
            "geo_eos80",
            "geo_ssh_eos80",
            "geo_density_eos80",
            "residual_eos80",
        ):
            column = f"{metric}_anom_pw_{BASELINE_TAG}"
            row[f"q5n_{metric}_jan_may1_zj"] = integrate_zj(
                selected[column].to_numpy(dtype=float), times
            )
        rows.append(row)
    result = pd.DataFrame(rows)
    closure = result.q5n_total_jan_may1_zj - (
        result.q5n_ekman_jan_may1_zj
        + result.q5n_geo_eos80_jan_may1_zj
        + result.q5n_residual_eos80_jan_may1_zj
    )
    if float(np.max(np.abs(closure))) > 1.0e-8:
        raise ValueError("Event Q20 decomposition does not close")
    return result


def load_section_h5netcdf() -> xr.Dataset:
    """Load the two section files without requiring the broken netCDF4 dylib."""
    with xr.open_dataset(fate.HISTORICAL_NC, engine="h5netcdf") as source:
        historical = source.sel(time=source.time.dt.month.isin([1, 2, 3, 4, 5])).load()
    with xr.open_dataset(fate.EXTENSION_NC, engine="h5netcdf") as source:
        extension = source.load()
    for coordinate in ("depth", "lon"):
        if not np.allclose(historical[coordinate], extension[coordinate]):
            raise ValueError(f"Historical and 2024 {coordinate} coordinates differ")
    extension = extension.assign_coords(
        depth=historical.depth.values,
        lon=historical.lon.values,
    )
    output = xr.concat([historical, extension], dim="time", join="exact").sortby("time")
    times = pd.DatetimeIndex(output.time.values)
    if not times.is_unique or not times.is_monotonic_increasing:
        raise ValueError("Combined section time axis is not unique/increasing")
    return output


def build_fep_decomposition_h5netcdf() -> pd.DataFrame:
    pieces: list[xr.DataArray] = []
    for month in MONTHS:
        path = oisst_path(month)
        with xr.open_dataset(path, engine="scipy") as source:
            da = source["sst"].load()
        rename = {}
        if "latitude" in da.coords:
            rename["latitude"] = "lat"
        if "longitude" in da.coords:
            rename["longitude"] = "lon"
        if "valid_time" in da.coords:
            rename["valid_time"] = "time"
        da = da.rename(rename)
        da = da.assign_coords(lon=da.lon % 360).sortby("lon").sortby("lat")
        da = da.assign_coords(
            time=pd.to_datetime(da.time.values).to_period("M").to_timestamp()
        )
        pieces.append(da)
    sst = xr.concat(pieces, dim="time").sortby("time")
    n34_raw = weighted_box_mean(sst, 190.0, 240.0).to_series()
    fep_raw = weighted_box_mean(sst, 270.0, 280.0).to_series()
    times = pd.DatetimeIndex(n34_raw.index)
    n34_anom = same_month_residual(n34_raw.to_numpy(), times, SST_BASELINE)
    fep_anom = same_month_residual(fep_raw.to_numpy(), times, SST_BASELINE)
    frame = pd.DataFrame(
        {
            "time": times,
            "year": times.year,
            "month": times.month,
            "nino34_ssta_c": n34_anom,
            "fep_total_ssta_c": fep_anom,
        }
    )
    residual = np.full(len(frame), np.nan, dtype=float)
    for month in MONTHS:
        mask = (
            frame.month.eq(month)
            & frame.year.between(*SST_BASELINE)
            & frame.nino34_ssta_c.notna()
            & frame.fep_total_ssta_c.notna()
        )
        x = frame.loc[mask, "nino34_ssta_c"].to_numpy(dtype=float)
        y = frame.loc[mask, "fep_total_ssta_c"].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        target = frame.month.eq(month)
        residual[target] = frame.loc[target, "fep_total_ssta_c"].to_numpy(dtype=float) - (
            intercept + slope * frame.loc[target, "nino34_ssta_c"].to_numpy(dtype=float)
        )
    frame["fep_residual_c"] = residual
    return frame


def build_surface_trigger(event_years: list[int]) -> pd.DataFrame:
    fep = build_fep_decomposition_h5netcdf()
    selected = fep.loc[
        fep.year.isin(event_years) & fep.month.isin([3, 4]),
        ["year", "fep_total_ssta_c", "fep_residual_c"],
    ]
    result = (
        selected.groupby("year", as_index=False)
        .mean(numeric_only=True)
        .rename(
            columns={
                "fep_total_ssta_c": "fep_total_mar_apr_c",
                "fep_residual_c": "fep_residual_mar_apr_c_recomputed",
            }
        )
    )
    if len(result) != len(event_years):
        raise ValueError("FEP surface-trigger table is incomplete")
    return result


def build_event_table(monthly: pd.DataFrame) -> pd.DataFrame:
    minimal = pd.read_csv(MINIMAL_EVENT_CSV)
    minimal["year"] = minimal.year.astype(int)
    event_years = minimal.year.tolist()
    perturbation = pd.read_csv(PERTURBATION_EVENT_CSV)
    keep = [
        "year",
        "fep_residual_mjj",
        "coupling_mjj",
        "precip_response_mjj",
        "slp_response_mjj",
        "tau_response_mjj",
        "q140_mar_apr_z",
        "d140_mar_apr_z",
        "east_ocean_state_z",
    ]
    table = (
        minimal.merge(build_surface_trigger(event_years), on="year", validate="one_to_one")
        .merge(perturbation[keep], on="year", validate="one_to_one")
        .merge(build_all_event_fate(monthly, event_years), on="year", validate="one_to_one")
        .sort_values("year")
        .reset_index(drop=True)
    )
    required = [
        "fep_total_mar_apr_c",
        "ohc300_central_ma_gj_m2",
        "u850_cwp_mj_ms",
        "q5n_total_jan_may1_zj",
        "q5n_ekman_jan_may1_zj",
        "q5n_geo_eos80_jan_may1_zj",
    ]
    if table[required].isna().any().any():
        raise ValueError("Missing required value in joined event table")
    slope, intercept = np.polyfit(
        table.fep_total_mar_apr_c.to_numpy(dtype=float),
        table.ohc300_central_ma_gj_m2.to_numpy(dtype=float),
        1,
    )
    table["ohc_expected_from_fep_gj_m2"] = (
        intercept + slope * table.fep_total_mar_apr_c
    )
    table["ohc_given_fep_residual_gj_m2"] = (
        table.ohc300_central_ma_gj_m2 - table.ohc_expected_from_fep_gj_m2
    )
    table["ohc_given_fep_residual_lower_rank"] = (
        table.ohc_given_fep_residual_gj_m2.rank(method="min", ascending=True).astype(int)
    )
    return table


def relationship_table(table: pd.DataFrame) -> pd.DataFrame:
    links = [
        (
            "surface_to_ocean",
            "FEP surface warming -> central OHC",
            "fep_total_mar_apr_c",
            "ohc300_central_ma_gj_m2",
        ),
        (
            "surface_to_wind",
            "FEP surface warming -> May-Jun u850",
            "fep_total_mar_apr_c",
            "u850_cwp_mj_ms",
        ),
        (
            "ocean_to_wind",
            "central OHC -> May-Jun u850",
            "ohc300_central_ma_gj_m2",
            "u850_cwp_mj_ms",
        ),
        (
            "wind_to_ekman",
            "May-Jun u850 -> following Jan-May 5N Ekman Q20",
            "u850_cwp_mj_ms",
            "q5n_ekman_jan_may1_zj",
        ),
        (
            "coupling_to_ekman",
            "MJJ atmosphere closure -> following 5N Ekman Q20",
            "coupling_mjj",
            "q5n_ekman_jan_may1_zj",
        ),
        (
            "ekman_to_total",
            "5N Ekman Q20 -> total Q20",
            "q5n_ekman_jan_may1_zj",
            "q5n_total_jan_may1_zj",
        ),
        (
            "geo_to_total",
            "5N geostrophic Q20 -> total Q20",
            "q5n_geo_eos80_jan_may1_zj",
            "q5n_total_jan_may1_zj",
        ),
    ]
    rows: list[dict[str, float | int | str]] = []
    for offset, (link_id, label, x_name, y_name) in enumerate(links):
        x = table[x_name].to_numpy(dtype=float)
        y = table[y_name].to_numpy(dtype=float)
        pearson = stats.pearsonr(x, y)
        spearman = stats.spearmanr(x, y)
        ci_low, ci_high = bootstrap_correlation(x, y, seed=RNG_SEED + offset)
        loeo = []
        for year in table.year:
            keep = table.year.ne(year)
            loeo.append(float(np.corrcoef(table.loc[keep, x_name], table.loc[keep, y_name])[0, 1]))
        rows.append(
            {
                "link_id": link_id,
                "label": label,
                "x": x_name,
                "y": y_name,
                "n_events": len(table),
                "pearson_r": float(pearson.statistic),
                "pearson_p_parametric": float(pearson.pvalue),
                "permutation_p": permutation_p(x, y, seed=RNG_SEED + offset),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "spearman_r": float(spearman.statistic),
                "spearman_p": float(spearman.pvalue),
                "loeo_r_min": float(np.min(loeo)),
                "loeo_r_max": float(np.max(loeo)),
            }
        )
    result = pd.DataFrame(rows)
    result["fdr_q"] = bh_fdr(result.permutation_p.to_numpy(dtype=float))
    return result


def fit_standardized_model(
    table: pd.DataFrame,
    predictors: list[str],
    response: str,
) -> tuple[np.ndarray, float, float]:
    x = np.column_stack([zscore(table[name].to_numpy(dtype=float)) for name in predictors])
    x = np.column_stack([np.ones(len(x)), x])
    y = zscore(table[response].to_numpy(dtype=float))
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    fitted = x @ beta
    rmse = float(np.sqrt(np.mean((y - fitted) ** 2)))
    r2 = float(1.0 - np.sum((y - fitted) ** 2) / np.sum((y - y.mean()) ** 2))
    return beta, rmse, r2


def loeo_rmse(table: pd.DataFrame, predictors: list[str], response: str) -> float:
    observed: list[float] = []
    predicted: list[float] = []
    for held in table.year:
        train = table.loc[table.year.ne(held)].copy()
        test = table.loc[table.year.eq(held)].copy()
        means = {name: float(train[name].mean()) for name in predictors + [response]}
        scales = {name: float(train[name].std(ddof=1)) for name in predictors + [response]}
        x_train = np.column_stack(
            [
                (train[name].to_numpy(dtype=float) - means[name]) / scales[name]
                for name in predictors
            ]
        )
        x_train = np.column_stack([np.ones(len(x_train)), x_train])
        y_train = (train[response].to_numpy(dtype=float) - means[response]) / scales[response]
        beta = np.linalg.lstsq(x_train, y_train, rcond=None)[0]
        x_test = np.array(
            [1.0]
            + [
                (float(test.iloc[0][name]) - means[name]) / scales[name]
                for name in predictors
            ]
        )
        predicted.append(float(x_test @ beta))
        observed.append((float(test.iloc[0][response]) - means[response]) / scales[response])
    return float(np.sqrt(np.mean((np.asarray(observed) - np.asarray(predicted)) ** 2)))


def interaction_feature_table(table: pd.DataFrame) -> pd.DataFrame:
    working = table.copy()
    working["fep_x_ohc"] = zscore(working.fep_total_mar_apr_c) * zscore(
        working.ohc300_central_ma_gj_m2
    )
    specifications = [
        ("fep_only", ["fep_total_mar_apr_c"]),
        ("ohc_only", ["ohc300_central_ma_gj_m2"]),
        ("fep_plus_ohc", ["fep_total_mar_apr_c", "ohc300_central_ma_gj_m2"]),
        (
            "fep_ohc_interaction",
            ["fep_total_mar_apr_c", "ohc300_central_ma_gj_m2", "fep_x_ohc"],
        ),
    ]
    rows: list[dict[str, float | int | str]] = []
    for model_id, predictors in specifications:
        beta, in_sample_rmse, r2 = fit_standardized_model(
            working, predictors, "u850_cwp_mj_ms"
        )
        row: dict[str, float | int | str] = {
            "model_id": model_id,
            "n_events": len(working),
            "predictors": "+".join(predictors),
            "in_sample_rmse_sd": in_sample_rmse,
            "in_sample_r2": r2,
            "loeo_rmse_sd": loeo_rmse(working, predictors, "u850_cwp_mj_ms"),
        }
        for name, value in zip(["intercept"] + predictors, beta):
            row[f"beta_{name}"] = float(value)
        rows.append(row)
    result = pd.DataFrame(rows)

    # Event bootstrap and Freedman-Lane residual permutation for the interaction.
    rng = np.random.default_rng(RNG_SEED + 100)
    bootstrap_beta: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        index = rng.integers(0, len(working), len(working))
        sample = working.iloc[index].copy()
        if sample.fep_total_mar_apr_c.std(ddof=1) == 0.0 or sample.ohc300_central_ma_gj_m2.std(ddof=1) == 0.0:
            continue
        sample["fep_x_ohc"] = zscore(sample.fep_total_mar_apr_c) * zscore(
            sample.ohc300_central_ma_gj_m2
        )
        beta, _, _ = fit_standardized_model(
            sample,
            ["fep_total_mar_apr_c", "ohc300_central_ma_gj_m2", "fep_x_ohc"],
            "u850_cwp_mj_ms",
        )
        bootstrap_beta.append(float(beta[-1]))
    ci_low, ci_high = np.percentile(bootstrap_beta, [2.5, 97.5])

    fep_z = zscore(working.fep_total_mar_apr_c.to_numpy(dtype=float))
    ohc_z = zscore(working.ohc300_central_ma_gj_m2.to_numpy(dtype=float))
    interaction = fep_z * ohc_z
    y = zscore(working.u850_cwp_mj_ms.to_numpy(dtype=float))
    reduced_x = np.column_stack([np.ones(len(working)), fep_z, ohc_z])
    reduced_beta = np.linalg.lstsq(reduced_x, y, rcond=None)[0]
    fitted = reduced_x @ reduced_beta
    residual = y - fitted
    full_x = np.column_stack([reduced_x, interaction])
    observed_beta = float(np.linalg.lstsq(full_x, y, rcond=None)[0][-1])
    exceed = 0
    for _ in range(PERMUTATION_SAMPLES):
        y_trial = fitted + rng.permutation(residual)
        trial_beta = float(np.linalg.lstsq(full_x, y_trial, rcond=None)[0][-1])
        exceed += int(abs(trial_beta) >= abs(observed_beta))
    permutation = float((exceed + 1) / (PERMUTATION_SAMPLES + 1))
    mask = result.model_id.eq("fep_ohc_interaction")
    result.loc[mask, "interaction_beta_bootstrap_ci_low"] = float(ci_low)
    result.loc[mask, "interaction_beta_bootstrap_ci_high"] = float(ci_high)
    result.loc[mask, "interaction_freedman_lane_p"] = permutation
    return result


def wind_swap_counterfactual(
    section,
    monthly: pd.DataFrame,
    event_table: pd.DataFrame,
) -> pd.DataFrame:
    times = pd.DatetimeIndex(section.time.values)
    temperature = section.temp.values.astype(float)
    taux = section.taux.values.astype(float)
    depth = section.depth.values.astype(float)
    longitude = section.lon.values.astype(float)
    taux_anomaly = dec.same_month_detrended_array(taux, times, BASELINE)
    baseline_taux = taux - taux_anomaly

    q_raw_actual = dec.ekman_heat_transport_pw(
        temperature, taux, depth, longitude, fate.LON_END
    )
    q_anom_actual = dec.same_month_detrended_array(q_raw_actual, times, BASELINE)
    q_baseline = q_raw_actual - q_anom_actual

    lookup = event_table.set_index("year")
    rows: list[dict[str, float | int | str]] = []
    donor_sets: list[tuple[str, list[int]]] = [
        (str(year), [year]) for year in HIGHLIGHT_YEARS
    ] + [("1997_2015_mean", [1997, 2015])]
    for target_event in HIGHLIGHT_YEARS:
        target_year = target_event + 1
        target_index = np.where((times.year == target_year) & np.isin(times.month, [1, 2, 3, 4, 5]))[0]
        if len(target_index) != 5:
            raise ValueError(f"Missing target months for {target_event}")
        target_times = times[target_index]
        for donor_label, donor_events in donor_sets:
            donor_anomalies = []
            for donor_event in donor_events:
                donor_year = donor_event + 1
                donor_index = np.where(
                    (times.year == donor_year) & np.isin(times.month, [1, 2, 3, 4, 5])
                )[0]
                if len(donor_index) != 5:
                    raise ValueError(f"Missing donor months for {donor_event}")
                donor_anomalies.append(taux_anomaly[donor_index])
            donor_anomaly = np.nanmean(np.stack(donor_anomalies, axis=0), axis=0)
            counterfactual_taux = baseline_taux[target_index] + donor_anomaly
            q_counterfactual_raw = dec.ekman_heat_transport_pw(
                temperature[target_index],
                counterfactual_taux,
                depth,
                longitude,
                fate.LON_END,
            )
            q_counterfactual_anom = q_counterfactual_raw - q_baseline[target_index]
            ekman_zj = integrate_zj(q_counterfactual_anom, target_times)
            geo_zj = float(lookup.loc[target_event, "q5n_geo_eos80_jan_may1_zj"])
            residual_zj = float(lookup.loc[target_event, "q5n_residual_eos80_jan_may1_zj"])
            rows.append(
                {
                    "target_ocean_event": target_event,
                    "donor_wind": donor_label,
                    "ekman_zj": ekman_zj,
                    "held_geo_zj": geo_zj,
                    "held_residual_zj": residual_zj,
                    "reconstructed_total_zj": ekman_zj + geo_zj + residual_zj,
                    "offline_diagnostic": True,
                }
            )
    result = pd.DataFrame(rows)
    for year in HIGHLIGHT_YEARS:
        actual = float(lookup.loc[year, "q5n_ekman_jan_may1_zj"])
        reproduced = float(
            result.loc[
                result.target_ocean_event.eq(year) & result.donor_wind.eq(str(year)),
                "ekman_zj",
            ].iloc[0]
        )
        if abs(actual - reproduced) > 1.0e-8:
            raise ValueError(f"Wind-swap control failed for {year}: {reproduced} vs {actual}")
    return result


def regression_band(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    grid = np.linspace(x.min(), x.max(), 100)
    rng = np.random.default_rng(RNG_SEED)
    predictions = []
    for _ in range(5000):
        index = rng.integers(0, len(x), len(x))
        if np.std(x[index]) == 0:
            continue
        slope, intercept = np.polyfit(x[index], y[index], 1)
        predictions.append(intercept + slope * grid)
    prediction_array = np.asarray(predictions)
    low, high = np.percentile(prediction_array, [2.5, 97.5], axis=0)
    return grid, low, high


def scatter_events(ax, table: pd.DataFrame, x_name: str, y_name: str) -> None:
    ordinary = table.loc[~table.year.isin(HIGHLIGHT_YEARS)]
    ax.scatter(
        ordinary[x_name],
        ordinary[y_name],
        s=30,
        color="0.72",
        edgecolor="white",
        linewidth=0.5,
        zorder=2,
    )
    for _, row in table.loc[table.year.isin(HIGHLIGHT_YEARS)].iterrows():
        year = int(row.year)
        ax.scatter(
            row[x_name],
            row[y_name],
            s=58,
            color=COLORS[year],
            edgecolor="white",
            linewidth=0.8,
            zorder=4,
        )
        ax.annotate(
            str(year),
            (row[x_name], row[y_name]),
            xytext=(5, 5),
            textcoords="offset points",
            color=COLORS[year],
            fontsize=8.5,
            fontweight="bold",
        )


def relationship_row(relationships: pd.DataFrame, link_id: str) -> pd.Series:
    return relationships.loc[relationships.link_id.eq(link_id)].iloc[0]


def plot_figure(
    table: pd.DataFrame,
    relationships: pd.DataFrame,
    counterfactual: pd.DataFrame,
) -> None:
    apply_climate_style(base_font_size=9)
    mpl.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})
    fig, axes = plt.subplots(2, 2, figsize=(10.6, 8.1), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    scatter_events(ax_a, table, "fep_total_mar_apr_c", "ohc300_central_ma_gj_m2")
    ax_a.axvline(0.0, color="0.65", linewidth=0.8, linestyle="--")
    ax_a.axhline(0.0, color="0.65", linewidth=0.8, linestyle="--")
    row = relationship_row(relationships, "surface_to_ocean")
    ax_a.text(
        0.03,
        0.96,
        f"r={row.pearson_r:+.2f}, permutation p={row.permutation_p:.3f}",
        transform=ax_a.transAxes,
        va="top",
        fontsize=8.3,
    )
    ax_a.set_title("Surface FEP warming is not the subsurface state")
    ax_a.set_xlabel("March-April total FEP SST anomaly (°C)")
    ax_a.set_ylabel("March-April central-Pacific 0-300 m OHC (GJ m$^{-2}$)")

    scatter_events(ax_b, table, "ohc300_central_ma_gj_m2", "u850_cwp_mj_ms")
    x = table.ohc300_central_ma_gj_m2.to_numpy(dtype=float)
    y = table.u850_cwp_mj_ms.to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    grid, low, high = regression_band(x, y)
    ax_b.plot(grid, intercept + slope * grid, color="#2C7FB8", linewidth=1.8)
    ax_b.fill_between(grid, low, high, color="#2C7FB8", alpha=0.16, linewidth=0)
    row = relationship_row(relationships, "ocean_to_wind")
    ax_b.text(
        0.03,
        0.96,
        (
            f"r={row.pearson_r:+.2f}, p={row.permutation_p:.4f}\n"
            f"event-bootstrap 95% CI [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]"
        ),
        transform=ax_b.transAxes,
        va="top",
        fontsize=8.3,
    )
    ax_b.set_title("Subsurface preconditioning strongly constrains wind response")
    ax_b.set_xlabel("March-April central-Pacific 0-300 m OHC (GJ m$^{-2}$)")
    ax_b.set_ylabel("May-June central-western Pacific u850 (m s$^{-1}$)")

    scatter_events(ax_c, table, "u850_cwp_mj_ms", "q5n_ekman_jan_may1_zj")
    x = table.u850_cwp_mj_ms.to_numpy(dtype=float)
    y = table.q5n_ekman_jan_may1_zj.to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    grid, low, high = regression_band(x, y)
    ax_c.plot(grid, intercept + slope * grid, color="#238B45", linewidth=1.8)
    ax_c.fill_between(grid, low, high, color="#238B45", alpha=0.16, linewidth=0)
    row = relationship_row(relationships, "wind_to_ekman")
    ax_c.text(
        0.03,
        0.96,
        (
            f"r={row.pearson_r:+.2f}, p={row.permutation_p:.3f}\n"
            f"95% CI [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]"
        ),
        transform=ax_c.transAxes,
        va="top",
        fontsize=8.3,
    )
    ax_c.set_title("Early wind closure and following 5°N Ekman export")
    ax_c.set_xlabel("May-June central-western Pacific u850 (m s$^{-1}$)")
    ax_c.set_ylabel("Following Jan-May 5°N Ekman Qwarm,20 (ZJ)")

    matrix = (
        counterfactual.loc[counterfactual.donor_wind.isin([str(y) for y in HIGHLIGHT_YEARS])]
        .pivot(index="target_ocean_event", columns="donor_wind", values="reconstructed_total_zj")
        .reindex(index=HIGHLIGHT_YEARS, columns=[str(y) for y in HIGHLIGHT_YEARS])
    )
    limit = float(np.nanmax(np.abs(matrix.to_numpy(dtype=float))))
    image = ax_d.imshow(
        matrix,
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit),
        aspect="auto",
    )
    ax_d.set_xticks(range(len(HIGHLIGHT_YEARS)), [str(year) for year in HIGHLIGHT_YEARS])
    ax_d.set_yticks(range(len(HIGHLIGHT_YEARS)), [str(year) for year in HIGHLIGHT_YEARS])
    ax_d.set_xlabel("Donor 5°N wind-stress anomaly")
    ax_d.set_ylabel("Fixed ocean temperature/pressure state")
    ax_d.set_title("Offline wind swap: reconstructed total 5°N Qwarm,20")
    for i, target in enumerate(HIGHLIGHT_YEARS):
        for j, donor in enumerate(HIGHLIGHT_YEARS):
            value = float(matrix.loc[target, str(donor)])
            color = "white" if abs(value) > 0.58 * limit else "black"
            weight = "bold" if target == donor else "normal"
            ax_d.text(j, i, f"{value:+.2f}", ha="center", va="center", color=color, fontweight=weight)
    colorbar = fig.colorbar(image, ax=ax_d, fraction=0.046, pad=0.03)
    colorbar.set_label("Reconstructed total Qwarm,20 (ZJ)")
    ax_d.text(
        0.5,
        -0.22,
        "Temperature, geostrophic transport and residual held fixed; only local wind stress is replaced.",
        transform=ax_d.transAxes,
        ha="center",
        va="top",
        fontsize=7.4,
        color="0.35",
    )

    for ax in (ax_a, ax_b, ax_c):
        ax.grid(True, color="0.9", linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    add_panel_labels([ax_a, ax_b, ax_c, ax_d])
    fig.suptitle(
        "Why similar far-eastern-Pacific surface warming led to different warm-heat fates",
        fontsize=13,
        fontweight="bold",
    )
    fig.text(
        0.5,
        -0.015,
        (
            "SODA3.15.2 and ERA5; 13 warm events. Ocean/atmosphere indices are same-calendar-month "
            "detrended anomalies. Correlation uncertainty resamples whole events."
        ),
        ha="center",
        fontsize=7.5,
        color="0.35",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, dpi=360, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(
    table: pd.DataFrame,
    relationships: pd.DataFrame,
    models: pd.DataFrame,
    counterfactual: pd.DataFrame,
) -> None:
    rel = relationships.set_index("link_id")
    cf = counterfactual.set_index(["target_ocean_event", "donor_wind"])
    highlights = table.loc[table.year.isin(HIGHLIGHT_YEARS)].set_index("year")
    model = models.set_index("model_id")
    lines = [
        "# 第三个问题：海气耦合与暖量命运的定量归因",
        "",
        "## 核心结果",
        "",
        (
            "13个暖事件中，3—4月中太平洋0—300 m OHC与5—6月中西太平洋u850的事件级相关为 "
            f"**r={rel.loc['ocean_to_wind', 'pearson_r']:+.2f}**，事件置换 "
            f"p={rel.loc['ocean_to_wind', 'permutation_p']:.4f}，事件bootstrap 95%区间 "
            f"[{rel.loc['ocean_to_wind', 'bootstrap_ci_low']:+.2f}, "
            f"{rel.loc['ocean_to_wind', 'bootstrap_ci_high']:+.2f}]。"
        ),
        "",
        (
            "FEP总表面增暖与中太平洋OHC的相关为 "
            f"r={rel.loc['surface_to_ocean', 'pearson_r']:+.2f}（置换 "
            f"p={rel.loc['surface_to_ocean', 'permutation_p']:.3f}）。这检验了“表面先暖”是否等价于"
            "“次表层已经准备好”。"
        ),
        "",
        (
            "2023给定FEP暖度后的OHC残差为 "
            f"**{highlights.loc[2023, 'ohc_given_fep_residual_gj_m2']:+.2f} GJ m⁻²**，"
            f"从低到高排名{int(highlights.loc[2023, 'ohc_given_fep_residual_lower_rank'])}/13；"
            f"2015和1997分别为{highlights.loc[2015, 'ohc_given_fep_residual_gj_m2']:+.2f}和"
            f"{highlights.loc[1997, 'ohc_given_fep_residual_gj_m2']:+.2f} GJ m⁻²。"
        ),
        "",
        (
            "5—6月u850与次年1—5月5°N Ekman Q20的跨事件相关为 "
            f"r={rel.loc['wind_to_ekman', 'pearson_r']:+.2f}（置换 "
            f"p={rel.loc['wind_to_ekman', 'permutation_p']:.3f}）。它是跨季节过程联系，不作为单独因果证明。"
        ),
        "",
        "## 1997、2015与2023",
        "",
        "| 事件 | 3—4月FEP | 3—4月中太平洋OHC | 5—6月u850 | 次年Ekman Q20 | 次年总Q20 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in HIGHLIGHT_YEARS:
        row = highlights.loc[year]
        lines.append(
            "| {year} | {fep:+.2f} °C | {ohc:+.2f} GJ m⁻² | {u:+.2f} m s⁻¹ | {ek:+.2f} ZJ | {total:+.2f} ZJ |".format(
                year=year,
                fep=row.fep_total_mar_apr_c,
                ohc=row.ohc300_central_ma_gj_m2,
                u=row.u850_cwp_mj_ms,
                ek=row.q5n_ekman_jan_may1_zj,
                total=row.q5n_total_jan_may1_zj,
            )
        )
    lines.extend(
        [
            "",
            "## 2023风应力替换",
            "",
            (
                "保持2023海洋温度、地转项和残差不变，使用2023自身5°N风应力异常时，重构总Q20为 "
                f"**{cf.loc[(2023, '2023'), 'reconstructed_total_zj']:+.2f} ZJ**；换成2015风应力异常后为 "
                f"**{cf.loc[(2023, '2015'), 'reconstructed_total_zj']:+.2f} ZJ**；换成1997风应力异常后为 "
                f"**{cf.loc[(2023, '1997'), 'reconstructed_total_zj']:+.2f} ZJ**。"
            ),
            "",
            (
                "反向地，保持2015海洋状态但换成2023风应力，重构总Q20由 "
                f"{cf.loc[(2015, '2015'), 'reconstructed_total_zj']:+.2f} ZJ变为 "
                f"{cf.loc[(2015, '2023'), 'reconstructed_total_zj']:+.2f} ZJ。"
            ),
            "",
            "该试验直接修改Ekman公式中的局地风应力，因此比事件相关更接近过程归因；但SSH、密度、海流和大气没有重新演化，仍不能替代强迫海洋模式或耦合模式试验。",
            "",
            "## 模型比较",
            "",
            "| 模型 | 样本内R² | 留一RMSE（标准差） |",
            "|---|---:|---:|",
            f"| 仅FEP | {model.loc['fep_only', 'in_sample_r2']:.2f} | {model.loc['fep_only', 'loeo_rmse_sd']:.2f} |",
            f"| 仅OHC | {model.loc['ohc_only', 'in_sample_r2']:.2f} | {model.loc['ohc_only', 'loeo_rmse_sd']:.2f} |",
            f"| FEP+OHC | {model.loc['fep_plus_ohc', 'in_sample_r2']:.2f} | {model.loc['fep_plus_ohc', 'loeo_rmse_sd']:.2f} |",
            f"| FEP×OHC交互 | {model.loc['fep_ohc_interaction', 'in_sample_r2']:.2f} | {model.loc['fep_ohc_interaction', 'loeo_rmse_sd']:.2f} |",
            "",
            (
                "交互项标准化系数为 "
                f"{model.loc['fep_ohc_interaction', 'beta_fep_x_ohc']:+.2f}，事件bootstrap 95%区间 "
                f"[{model.loc['fep_ohc_interaction', 'interaction_beta_bootstrap_ci_low']:+.2f}, "
                f"{model.loc['fep_ohc_interaction', 'interaction_beta_bootstrap_ci_high']:+.2f}]，"
                f"Freedman—Lane置换p={model.loc['fep_ohc_interaction', 'interaction_freedman_lane_p']:.3f}。"
            ),
            "",
            "留一误差用于防止13事件小样本下把更复杂模型的样本内拟合误认为稳定机制；若交互项区间跨零，则只保留为支持性而非决定性证据。",
            "",
            "## 可以写入论文的结论",
            "",
            "FEP表面增暖只提供东部表面触发，并不等价于盆地次表层暖量已经向中东太平洋配置。事件级证据表明，中太平洋OHC是随后西风响应的稳定约束；风应力替换进一步表明，在保持海洋压力场不变时，局地风驱Ekman强度足以改变5°N出口的开闭程度。因此，不同暖量命运可归结为“次表层预置调制大气接通效率，而大气风应力决定Ekman能否克服地转阻力”。",
            "",
            "## 证据边界",
            "",
            "1. 13事件统计支持跨事件普适性，但样本仍小；所有不确定性均以事件为重采样单位。",
            "2. 5—6月u850到次年1—5月出口是跨季节联系，不应解释为单一步骤的直接作用。",
            "3. 风应力替换是离线诊断，不能包含SSH、温跃层和大气对流的反馈调整。",
            "4. 因而当前可称为“定量过程归因”，尚不是完整耦合模式因果归因。",
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    section = load_section_h5netcdf()
    monthly, physical = fate.build_monthly(section)
    table = build_event_table(monthly)
    relationships = relationship_table(table)
    models = interaction_feature_table(table)
    counterfactual = wind_swap_counterfactual(section, monthly, table)

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    EVENT_TABLE_CSV.write_text(table.to_csv(index=False), encoding="utf-8")
    RELATIONSHIP_CSV.write_text(relationships.to_csv(index=False), encoding="utf-8")
    MODEL_CSV.write_text(models.to_csv(index=False), encoding="utf-8")
    COUNTERFACTUAL_CSV.write_text(counterfactual.to_csv(index=False), encoding="utf-8")

    diagnostics = {
        "event_years": table.year.astype(int).tolist(),
        "n_events": int(len(table)),
        "baseline": f"{BASELINE[0]}-{BASELINE[1]} same-calendar-month linear detrend",
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "permutation_samples": PERMUTATION_SAMPLES,
        "physical_qc": physical,
        "event_decomposition_max_abs_closure_zj": float(
            np.max(
                np.abs(
                    table.q5n_total_jan_may1_zj
                    - table.q5n_ekman_jan_may1_zj
                    - table.q5n_geo_eos80_jan_may1_zj
                    - table.q5n_residual_eos80_jan_may1_zj
                )
            )
        ),
        "wind_swap_control_max_abs_error_zj": float(
            max(
                abs(
                    float(
                        counterfactual.loc[
                            counterfactual.target_ocean_event.eq(year)
                            & counterfactual.donor_wind.eq(str(year)),
                            "ekman_zj",
                        ].iloc[0]
                    )
                    - float(
                        table.loc[table.year.eq(year), "q5n_ekman_jan_may1_zj"].iloc[0]
                    )
                )
                for year in HIGHLIGHT_YEARS
            )
        ),
        "interpretation_limit": (
            "Event-level observational association plus offline local-wind-stress replacement; "
            "not a dynamically adjusted coupled-model causal experiment."
        ),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot_figure(table, relationships, counterfactual)
    write_report(table, relationships, models, counterfactual)
    print(FIGURE_PNG)
    print(REPORT_MD)


if __name__ == "__main__":
    main()
