#!/usr/bin/env python3
"""Observational perturbation attribution for ENSO atmospheric coupling.

The analysis is deliberately organized as a small causal emulator rather than
as a generic multi-predictor regression.  It asks whether five candidate
conditions help explain why the atmospheric branch connects in some El Nino
years but not others:

1. multi-year La Nina memory;
2. Indo-Atlantic relative heating;
3. the North Pacific Meridional Mode (NPMM);
4. the FEP-related meridional precipitation dipole;
5. high-frequency westerly wind-stress pulses.

The response is the May-July atmosphere-coupling residual after the
contemporaneous SST amplitude, SST pattern, and trend are removed in
leave-one-year-out regressions.  Mature ENSO type is evaluated with both the
orthogonal E/C flavor coordinate and the traditional Nino3-Nino4 contrast.

The counterfactual perturbations are an observational, regularized structural
emulator.  They do not replace an AGCM or coupled-model intervention.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_enso_perturbation_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
INTERIM = ROOT / "data/interim/research_2026"
OUT = ROOT / "outputs/research_2026/perturbation_attribution"
PDF_DIR = ROOT / "output/pdf"
REPORT = ROOT / "reports/ENSO大气接通与类型转换扰动实验.md"

ERSST = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
GPCP = INTERIM / "gpcp_event_spatial_tropics_1982_202605.nc"
FULL_COUPLING = DERIVED / "enso_full_year_coupling_monthly_1982_2024.csv"
EXTERNAL = (
    ROOT / "data/interim/raw_validation/oisst_external_basin_monthly.csv"
)
PMM = DERIVED / "pmm_like_index_oisst_era5_1982_2026.csv"
SODA_PROCESS = DERIVED / "soda3_transition_process_indices_1980_2024.csv"
SODA_BUDGET = DERIVED / "soda3_mixed_layer_budget_indices_1980_2024.csv"
OCEAN_GATE = DERIVED / "enso_type_east_ocean_state_event_summary.csv"
EC_MONTHLY = DERIVED / "enso_ec_indices_1980_2024.csv"
EC_EVENTS = DERIVED / "enso_ec_event_summary_1982_2023.csv"
WWB_STRESS = (
    INTERIM / "soda3_5day_wwb_stress_1982_2023_event_years.csv"
)

EVENT_INDEX_CSV = DERIVED / "enso_perturbation_event_indices_1982_2023.csv"
PARTIAL_CSV = DERIVED / "enso_perturbation_partial_correlations.csv"
SKILL_CSV = DERIVED / "enso_perturbation_model_skill.csv"
EFFECT_CSV = DERIVED / "enso_perturbation_counterfactual_effects.csv"
REPLACE_2023_CSV = DERIVED / "enso_perturbation_2023_replacements.csv"
ROBUSTNESS_CSV = DERIVED / "enso_perturbation_robustness.csv"
DIAGNOSTICS_JSON = DERIVED / "enso_perturbation_diagnostics.json"
AGCM_MATRIX_CSV = DERIVED / "enso_dynamical_perturbation_experiment_matrix.csv"
WWB_TRANSPORT_LAG_CSV = (
    DERIVED / "enso_wwb_to_140w_transport_lag_validation.csv"
)

FIG1 = OUT / "fig1_event_factor_and_response_matrix"
FIG2 = OUT / "fig2_single_factor_perturbation_effects"
FIG3 = OUT / "fig3_2023_counterfactual_replacements"

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
EXTREME_EVENTS = (1982, 1997, 2015)
BASELINE_START = 1982
BASELINE_END = 2024
RIDGE_ALPHA = 1.0
BOOTSTRAP_SAMPLES = 10_000
PERMUTATION_SAMPLES = 30_000
RANDOM_SEED = 20260731

FACTOR_COLUMNS = {
    "multi_year_la_nina": "multi_year_la_nina_memory",
    "indo_atlantic_heating": "indo_atlantic_total_heating",
    "npmm": "npmm_fma",
    "fep_precip_dipole": "precip_dipole_mjj",
    "wwb_pulses": "wwb_stochastic_impulse",
}
FACTOR_LABELS = {
    "multi_year_la_nina": "Multi-year La Niña memory",
    "indo_atlantic_heating": "Indo-Atlantic total heating",
    "npmm": "Warm NPMM",
    "fep_precip_dipole": "FEP meridional rain dipole",
    "wwb_pulses": "High-frequency westerly pulses",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.8,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.0,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "legend.fontsize": 7.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def ensure_inputs() -> None:
    required = (
        ERSST,
        GPCP,
        FULL_COUPLING,
        EXTERNAL,
        PMM,
        SODA_PROCESS,
        SODA_BUDGET,
        OCEAN_GATE,
        EC_MONTHLY,
        EC_EVENTS,
        WWB_STRESS,
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing inputs: {missing}")
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)


def open_dataset(path: Path) -> xr.Dataset:
    try:
        return xr.open_dataset(path, engine="h5netcdf")
    except (OSError, ValueError):
        return xr.open_dataset(path, engine="scipy")


def normalize_field(field: xr.DataArray) -> xr.DataArray:
    rename = {}
    for old, new in (
        ("valid_time", "time"),
        ("latitude", "lat"),
        ("longitude", "lon"),
    ):
        if old in field.coords:
            rename[old] = new
    field = field.rename(rename)
    if "lon" in field.coords:
        field = field.assign_coords(lon=field.lon % 360).sortby("lon")
    if "lat" in field.coords:
        field = field.sortby("lat")
    return field


def area_mean(
    field: xr.DataArray,
    *,
    lat0: float,
    lat1: float,
    lon0: float,
    lon1: float,
) -> xr.DataArray:
    subset = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(
            f"Empty region lat={lat0}..{lat1}, lon={lon0}..{lon1}"
        )
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def monthly_anomaly_detrend(
    frame: pd.DataFrame,
    column: str,
    *,
    output: str | None = None,
) -> pd.DataFrame:
    data = frame.copy()
    climatology = (
        data.loc[data["year"].between(BASELINE_START, BASELINE_END)]
        .groupby("month")[column]
        .mean()
    )
    anomaly = data[column] - data["month"].map(climatology)
    decimal_year = (
        data["year"].to_numpy(dtype=float)
        + (data["month"].to_numpy(dtype=float) - 0.5) / 12.0
    )
    fit = (
        data["year"].between(BASELINE_START, BASELINE_END)
        & anomaly.notna()
    )
    design = np.column_stack(
        [np.ones(fit.sum()), decimal_year[fit.to_numpy()] - 2003.0]
    )
    coefficients = np.linalg.lstsq(
        design,
        anomaly.loc[fit].to_numpy(dtype=float),
        rcond=None,
    )[0]
    trend = (
        coefficients[0]
        + coefficients[1] * (decimal_year - 2003.0)
    )
    name = output or f"{column}_anom_detrended"
    data[name] = anomaly - trend
    return data


def seasonal_mean(
    frame: pd.DataFrame,
    column: str,
    months: Iterable[int],
    *,
    years: Iterable[int] | None = None,
) -> pd.Series:
    subset = frame.loc[frame["month"].isin(tuple(months))]
    result = subset.groupby("year")[column].mean()
    if years is not None:
        result = result.reindex(tuple(years))
    return result


def zscore(values: pd.Series) -> pd.Series:
    scale = float(values.std(ddof=1))
    if not np.isfinite(scale) or scale == 0:
        return pd.Series(np.nan, index=values.index)
    return (values - values.mean()) / scale


def load_nino34_long_record() -> pd.DataFrame:
    with open_dataset(ERSST) as dataset:
        field = normalize_field(dataset["sst"]).sel(
            time=slice("1978-01-01", "2024-12-31")
        )
        index = area_mean(
            field,
            lat0=-5,
            lat1=5,
            lon0=190,
            lon1=240,
        ).load()
    time = pd.to_datetime(index.time.values)
    frame = pd.DataFrame(
        {
            "time": time,
            "year": time.year,
            "month": time.month,
            "nino34": index.values.astype(float),
        }
    )
    return monthly_anomaly_detrend(
        frame,
        "nino34",
        output="nino34_anom_detrended",
    )


def build_la_nina_memory(nino: pd.DataFrame) -> pd.DataFrame:
    indexed = nino.set_index("time")["nino34_anom_detrended"].sort_index()
    rows = []
    for year in EVENT_YEARS:
        winter_means = []
        for ending_year in (year - 2, year - 1, year):
            dates = [
                pd.Timestamp(ending_year - 1, 12, 1),
                pd.Timestamp(ending_year, 1, 1),
                pd.Timestamp(ending_year, 2, 1),
            ]
            winter_means.append(float(indexed.reindex(dates).mean()))
        start = pd.Timestamp(year - 3, 9, 1)
        end = pd.Timestamp(year, 2, 1)
        period = indexed.loc[start:end]
        cold_excess = np.maximum(-period.to_numpy(dtype=float) - 0.5, 0.0)
        rows.append(
            {
                "year": year,
                "la_nina_winter_count": int(
                    np.sum(np.asarray(winter_means) <= -0.5)
                ),
                "la_nina_cold_integral_c_month": float(
                    np.nansum(cold_excess)
                ),
                "prior_three_winter_nino34_mean_c": float(
                    np.nanmean(winter_means)
                ),
            }
        )
    output = pd.DataFrame(rows)
    count_z = zscore(output["la_nina_winter_count"])
    integral_z = zscore(output["la_nina_cold_integral_c_month"])
    output["multi_year_la_nina_memory"] = zscore(
        (count_z + integral_z) / math.sqrt(2.0)
    )
    return output


def residualize_on_nino(
    values: pd.Series,
    nino: pd.Series,
) -> pd.Series:
    table = pd.concat([values.rename("y"), nino.rename("nino")], axis=1)
    valid = table.notna().all(axis=1)
    design = np.column_stack(
        [
            np.ones(valid.sum()),
            table.index.to_numpy(dtype=float)[valid] - 2003.0,
            table.loc[valid, "nino"].to_numpy(dtype=float),
        ]
    )
    coefficients = np.linalg.lstsq(
        design,
        table.loc[valid, "y"].to_numpy(dtype=float),
        rcond=None,
    )[0]
    full_design = np.column_stack(
        [
            np.ones(len(table)),
            table.index.to_numpy(dtype=float) - 2003.0,
            table["nino"].to_numpy(dtype=float),
        ]
    )
    result = table["y"] - full_design @ coefficients
    result.loc[~valid] = np.nan
    return result


def build_external_indices(nino: pd.DataFrame) -> pd.DataFrame:
    external = pd.read_csv(EXTERNAL)
    total_pieces: dict[str, pd.Series] = {}
    independent_pieces: dict[str, pd.Series] = {}
    for region, group in external.groupby("region"):
        group = group.sort_values(["year", "month"]).copy()
        climatology = (
            group.loc[group["year"].between(BASELINE_START, BASELINE_END)]
            .groupby("month")["sst"]
            .mean()
        )
        group["sst_anom_total"] = (
            group["sst"] - group["month"].map(climatology)
        )
        detrended = monthly_anomaly_detrend(
            group,
            "sst",
            output="sst_anom_detrended",
        )
        total_pieces[region] = seasonal_mean(
            group,
            "sst_anom_total",
            (5, 6, 7),
        )
        independent_pieces[region] = seasonal_mean(
            detrended,
            "sst_anom_detrended",
            (5, 6, 7),
        )
    nino_mjj = seasonal_mean(
        nino,
        "nino34_anom_detrended",
        (5, 6, 7),
    )
    all_years = np.arange(BASELINE_START, BASELINE_END + 1)
    output = pd.DataFrame({"year": all_years}).set_index("year")
    for region in total_pieces:
        output[region] = total_pieces[region].reindex(all_years)
        output[f"{region}_independent"] = residualize_on_nino(
            independent_pieces[region].reindex(all_years),
            nino_mjj.reindex(all_years),
        )
    tio_total = zscore(output["tropical_indian_ocean"])
    tna_total = zscore(output["tropical_north_atlantic"])
    output["indo_atlantic_total_heating"] = zscore(
        (tio_total + tna_total) / math.sqrt(2.0)
    )
    tio = zscore(output["tropical_indian_ocean_independent"])
    tna = zscore(output["tropical_north_atlantic_independent"])
    output["indo_atlantic_relative_heating"] = zscore(
        (tio + tna) / math.sqrt(2.0)
    )
    return output.reset_index()


def build_pmm_indices() -> pd.DataFrame:
    pmm = pd.read_csv(PMM)
    pmm = pmm.loc[pmm["year"].le(BASELINE_END)].copy()
    for column in ("pmm_joint_sst_wind", "pmm_sst_only"):
        pmm = monthly_anomaly_detrend(
            pmm,
            column,
            output=f"{column}_harmonized",
        )
    output = (
        pmm.loc[pmm["month"].isin((2, 3, 4))]
        .groupby("year")
        .agg(
            npmm_fma=("pmm_joint_sst_wind_harmonized", "mean"),
            npmm_sst_only_fma=("pmm_sst_only_harmonized", "mean"),
        )
        .reset_index()
    )
    return output


def build_fep_and_gradient_indices(
    nino: pd.DataFrame,
) -> pd.DataFrame:
    monthly = pd.read_csv(FULL_COUPLING)
    for column in (
        "fep_raw_c",
        "nino34_raw_c",
        "sst_gradient_e_minus_w_raw_c",
    ):
        monthly = monthly_anomaly_detrend(
            monthly,
            column,
            output=f"{column}_ad",
        )
    residual_pieces = []
    for month, group in monthly.groupby("month"):
        x = group["nino34_raw_c_ad"].to_numpy(dtype=float)
        y = group["fep_raw_c_ad"].to_numpy(dtype=float)
        valid = np.isfinite(x) & np.isfinite(y)
        design = np.column_stack([np.ones(valid.sum()), x[valid]])
        coefficients = np.linalg.lstsq(design, y[valid], rcond=None)[0]
        current = group[["year", "month"]].copy()
        current["fep_residual"] = y - (
            coefficients[0] + coefficients[1] * x
        )
        residual_pieces.append(current)
    residuals = pd.concat(residual_pieces, ignore_index=True)
    monthly = monthly.merge(
        residuals,
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )
    output = pd.DataFrame({"year": EVENT_YEARS})
    output["fep_residual_mjj"] = output["year"].map(
        seasonal_mean(monthly, "fep_residual", (5, 6, 7))
    )
    output["fep_residual_fma"] = output["year"].map(
        seasonal_mean(monthly, "fep_residual", (2, 3, 4))
    )
    output["zonal_sst_gradient_fma"] = output["year"].map(
        seasonal_mean(
            monthly,
            "sst_gradient_e_minus_w_raw_c_ad",
            (2, 3, 4),
        )
    )
    return output


def gpcp_dipole_for_box(
    field: xr.DataArray,
    *,
    lon0: float,
    lon1: float,
) -> pd.DataFrame:
    equatorial = area_mean(
        field,
        lat0=-3.75,
        lat1=3.75,
        lon0=lon0,
        lon1=lon1,
    ).load()
    north = area_mean(
        field,
        lat0=6.25,
        lat1=11.25,
        lon0=lon0,
        lon1=lon1,
    ).load()
    time = pd.to_datetime(equatorial.time.values)
    frame = pd.DataFrame(
        {
            "time": time,
            "year": time.year,
            "month": time.month,
            "dipole": (
                equatorial.values.astype(float)
                - north.values.astype(float)
            ),
        }
    )
    return monthly_anomaly_detrend(
        frame,
        "dipole",
        output="dipole_ad",
    )


def build_precip_dipole_indices() -> pd.DataFrame:
    with open_dataset(GPCP) as dataset:
        field = normalize_field(dataset["precip"]).sel(
            time=slice("1982-01-01", "2024-12-31")
        )
        basin = gpcp_dipole_for_box(field, lon0=180, lon1=270)
        central = gpcp_dipole_for_box(field, lon0=180, lon1=230)
        eastern = gpcp_dipole_for_box(field, lon0=210, lon1=270)
    output = pd.DataFrame({"year": EVENT_YEARS})
    for name, frame in (
        ("precip_dipole_mjj", basin),
        ("precip_dipole_cp_mjj", central),
        ("precip_dipole_ep_mjj", eastern),
    ):
        coupling = pd.read_csv(
            FULL_COUPLING,
            usecols=[
                "year",
                "month",
                "nino34_raw_c",
                "sst_type_raw_c",
            ],
        )
        frame = frame.merge(
            coupling,
            on=["year", "month"],
            how="left",
            validate="one_to_one",
        )
        residual_pieces = []
        for month, group in frame.groupby("month"):
            valid = group.dropna(
                subset=[
                    "dipole_ad",
                    "nino34_raw_c",
                    "sst_type_raw_c",
                ]
            )
            design = np.column_stack(
                [
                    np.ones(len(valid)),
                    valid["year"].to_numpy(dtype=float) - 2003.0,
                    valid["nino34_raw_c"].to_numpy(dtype=float),
                    valid["sst_type_raw_c"].to_numpy(dtype=float),
                ]
            )
            coefficients = np.linalg.lstsq(
                design,
                valid["dipole_ad"].to_numpy(dtype=float),
                rcond=None,
            )[0]
            current = valid[["year", "month"]].copy()
            current["dipole_residual"] = (
                valid["dipole_ad"].to_numpy(dtype=float)
                - design @ coefficients
            )
            residual_pieces.append(current)
        residuals = pd.concat(residual_pieces, ignore_index=True)
        frame = frame.merge(
            residuals,
            on=["year", "month"],
            how="left",
            validate="one_to_one",
        )
        output[f"{name}_raw"] = output["year"].map(
            seasonal_mean(frame, "dipole_ad", (5, 6, 7))
        )
        output[name] = output["year"].map(
            seasonal_mean(frame, "dipole_residual", (5, 6, 7))
        )
    return output


def expected_residual(
    monthly: pd.DataFrame,
    *,
    response: str,
    event_year: int,
    month: int,
) -> float:
    group = monthly.loc[monthly["month"].eq(month)].dropna(
        subset=[response, "nino34_raw_c", "sst_type_raw_c"]
    )
    train = group.loc[group["year"].ne(event_year)]
    test = group.loc[group["year"].eq(event_year)]
    if len(test) != 1 or len(train) < 30:
        return float("nan")
    design = np.column_stack(
        [
            np.ones(len(train)),
            train["year"].to_numpy(dtype=float) - 2003.0,
            train["nino34_raw_c"].to_numpy(dtype=float),
            train["sst_type_raw_c"].to_numpy(dtype=float),
        ]
    )
    coefficients = np.linalg.lstsq(
        design,
        train[response].to_numpy(dtype=float),
        rcond=None,
    )[0]
    fitted = design @ coefficients
    scale = float(np.std(train[response] - fitted, ddof=4))
    row = test.iloc[0]
    test_design = np.asarray(
        [
            1.0,
            float(event_year) - 2003.0,
            float(row["nino34_raw_c"]),
            float(row["sst_type_raw_c"]),
        ]
    )
    return float((float(row[response]) - test_design @ coefficients) / scale)


def build_coupling_indices() -> pd.DataFrame:
    monthly = pd.read_csv(FULL_COUPLING)
    responses = (
        "precip_tropical_pacific_raw_mmday",
        "slp_drive_w_minus_e_raw_hpa",
        "tau_cwp_raw_nm2",
    )
    rows = []
    for year in EVENT_YEARS:
        branch_values: dict[str, list[float]] = {
            response: [] for response in responses
        }
        for month in (5, 6, 7):
            for response in responses:
                branch_values[response].append(
                    expected_residual(
                        monthly,
                        response=response,
                        event_year=year,
                        month=month,
                    )
                )
        branch_mean = {
            response: float(np.nanmean(values))
            for response, values in branch_values.items()
        }
        rows.append(
            {
                "year": year,
                "coupling_mjj": float(
                    np.mean(tuple(branch_mean.values()))
                ),
                "precip_response_mjj": branch_mean[responses[0]],
                "slp_response_mjj": branch_mean[responses[1]],
                "tau_response_mjj": branch_mean[responses[2]],
            }
        )
    return pd.DataFrame(rows)


def build_wwb_indices() -> pd.DataFrame:
    stress = pd.read_csv(WWB_STRESS, parse_dates=["time"])
    stress = stress.loc[
        stress["year"].isin(EVENT_YEARS)
        & stress["month"].isin((3, 4, 5))
    ].copy()
    definitions = (
        ("west", "taux_wwb_135e_180_nm2"),
        ("central", "taux_central_180_220e_nm2"),
    )
    grouped_outputs = []
    for label, column in definitions:
        departure = f"{label}_within_month_departure"
        excess = f"{label}_pulse_excess"
        flag = f"{label}_pulse_flag"
        stress[departure] = (
            stress[column]
            - stress.groupby(["year", "month"])[column].transform("mean")
        )
        threshold = float(stress[departure].std(ddof=1))
        stress[excess] = np.maximum(stress[departure] - threshold, 0.0)
        stress[flag] = (stress[departure] > threshold).astype(float)
        prefix = "" if label == "west" else "_central"
        current = (
            stress.groupby("year")
            .agg(
                **{
                    f"wwb_stochastic_impulse{prefix}": (excess, "sum"),
                    f"wwb_stochastic_frequency{prefix}": (flag, "mean"),
                    f"wwb_peak_stress_departure{prefix}_nm2": (
                        departure,
                        "max",
                    ),
                    f"wwb_mean_stress{prefix}_nm2": (column, "mean"),
                    f"wwb_n_pentads{prefix}": ("time", "count"),
                }
            )
            .reindex(EVENT_YEARS)
        )
        current[f"wwb_threshold{prefix}_nm2"] = threshold
        grouped_outputs.append(current)
    output = pd.concat(grouped_outputs, axis=1).reset_index()
    return output


def build_wwb_transport_validation() -> pd.DataFrame:
    """Test whether western stress pulses precede 140W warm transport."""
    stress = pd.read_csv(WWB_STRESS, parse_dates=["time"])
    stress = stress.loc[
        stress["year"].isin(EVENT_YEARS)
        & stress["month"].isin((3, 4, 5, 6))
    ].copy()
    stress_column = "taux_wwb_135e_180_nm2"
    stress["stress_departure"] = (
        stress[stress_column]
        - stress.groupby(["year", "month"])[stress_column].transform("mean")
    )
    monthly = pd.read_csv(SODA_BUDGET)
    monthly_reference = monthly[
        ["year", "month", "q20_220e_pw_anom"]
    ]
    pieces = []
    for year in EVENT_YEARS:
        path = (
            INTERIM
            / "soda3_5day_event_transport"
            / f"soda3_5day_transport_{year}_jan_jun.csv"
        )
        if not path.exists():
            raise FileNotFoundError(path)
        transport = pd.read_csv(path, parse_dates=["time"])
        transport = transport.loc[
            transport["longitude_e"].eq(220.0),
            ["time", "year", "month", "q20_pw"],
        ]
        transport["q20_departure"] = (
            transport["q20_pw"]
            - transport.groupby(["year", "month"])["q20_pw"].transform("mean")
        )
        transport = transport.merge(
            monthly_reference,
            on=["year", "month"],
            how="left",
            validate="many_to_one",
        )
        transport["q20_140w_anchored"] = (
            transport["q20_departure"]
            + transport["q20_220e_pw_anom"]
        )
        current = stress.loc[
            stress["year"].eq(year),
            ["time", "year", "stress_departure"],
        ].merge(
            transport[["time", "q20_140w_anchored"]],
            on="time",
            how="inner",
            validate="one_to_one",
        )
        pieces.append(current.sort_values("time"))
    frame = pd.concat(pieces, ignore_index=True)
    rng = np.random.default_rng(RANDOM_SEED + 23)
    rows = []
    for lag in range(0, 7):
        paired = []
        for year, group in frame.groupby("year"):
            current = group.sort_values("time").copy()
            current["transport_lead"] = current[
                "q20_140w_anchored"
            ].shift(-lag)
            paired.append(current.dropna())
        pairs = pd.concat(paired, ignore_index=True)
        correlation = float(
            pairs["stress_departure"].corr(pairs["transport_lead"])
        )
        samples = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
        years = np.asarray(EVENT_YEARS)
        by_year = {
            year: pairs.loc[pairs["year"].eq(year)] for year in EVENT_YEARS
        }
        for index in range(BOOTSTRAP_SAMPLES):
            selected = rng.choice(years, size=len(years), replace=True)
            bootstrap = pd.concat(
                [by_year[int(year)] for year in selected],
                ignore_index=True,
            )
            samples[index] = bootstrap["stress_departure"].corr(
                bootstrap["transport_lead"]
            )
        low, high = np.nanpercentile(samples, [2.5, 97.5])
        rows.append(
            {
                "lag_pentads_wind_leads": lag,
                "lag_days_wind_leads": lag * 5,
                "correlation": correlation,
                "event_block_bootstrap_ci_low": float(low),
                "event_block_bootstrap_ci_high": float(high),
                "n_paired_pentads": len(pairs),
            }
        )
    output = pd.DataFrame(rows)
    output.to_csv(WWB_TRANSPORT_LAG_CSV, index=False)
    return output


def build_ocean_and_type_indices() -> pd.DataFrame:
    ocean = pd.read_csv(OCEAN_GATE)
    ec_monthly = pd.read_csv(EC_MONTHLY)
    ec_events = pd.read_csv(EC_EVENTS)
    april = (
        ec_monthly.loc[
            ec_monthly["year"].isin(EVENT_YEARS)
            & ec_monthly["month"].eq(4)
        ]
        .set_index("year")
    )
    output = ocean.loc[ocean["year"].isin(EVENT_YEARS)].copy()
    output["early_ec_apr"] = output["year"].map(
        april["ec_flavor_e_minus_c"]
    )
    output["early_box_apr"] = output["year"].map(
        april["ersst_nino3_minus_nino4_c"]
    )
    event = ec_events.set_index("year")
    output["mature_ec_flavor"] = output["year"].map(
        event["mature_djf_ec_flavor_e_minus_c"]
    )
    output["mature_box_type"] = output["year"].map(
        event["mature_djf_ersst_nino3_minus_nino4_c"]
    )
    output["mature_nino34"] = output["year"].map(
        event["mature_djf_ersst_nino34_anom_c"]
    )
    return output


def build_event_table() -> pd.DataFrame:
    nino = load_nino34_long_record()
    table = pd.DataFrame({"year": EVENT_YEARS})
    for addition in (
        build_la_nina_memory(nino),
        build_external_indices(nino),
        build_pmm_indices(),
        build_fep_and_gradient_indices(nino),
        build_precip_dipole_indices(),
        build_coupling_indices(),
        build_wwb_indices(),
        build_ocean_and_type_indices(),
    ):
        table = table.merge(
            addition,
            on="year",
            how="left",
            validate="one_to_one",
        )
    required = [
        *FACTOR_COLUMNS.values(),
        "fep_residual_mjj",
        "zonal_sst_gradient_fma",
        "east_ocean_state_z",
        "early_ec_apr",
        "coupling_mjj",
        "precip_response_mjj",
        "slp_response_mjj",
        "tau_response_mjj",
        "mature_ec_flavor",
        "mature_box_type",
    ]
    if table[required].isna().any().any():
        missing = table.loc[
            table[required].isna().any(axis=1),
            ["year", *required],
        ]
        raise ValueError(f"Missing event indices:\n{missing}")
    for column in required:
        table[f"{column}_z"] = zscore(table[column])
    table["event_group"] = np.select(
        [
            table["year"].isin(EXTREME_EVENTS),
            table["year"].eq(2023),
            table["mature_ec_flavor"].lt(0),
        ],
        ["classic extreme EP", "2023 mixed/weak coupling", "CP-leaning"],
        default="other warm",
    )
    table.to_csv(EVENT_INDEX_CSV, index=False)
    return table


def partial_correlation(
    frame: pd.DataFrame,
    predictor: str,
    response: str,
    controls: tuple[str, ...],
) -> tuple[float, float, float, float]:
    required = [predictor, response, *controls]
    data = frame.dropna(subset=required)
    design = np.column_stack(
        [
            np.ones(len(data)),
            *[data[column].to_numpy(dtype=float) for column in controls],
        ]
    )
    x = data[predictor].to_numpy(dtype=float)
    y = data[response].to_numpy(dtype=float)
    x_resid = x - design @ np.linalg.lstsq(design, x, rcond=None)[0]
    y_resid = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
    correlation = float(np.corrcoef(x_resid, y_resid)[0, 1])
    rng = np.random.default_rng(RANDOM_SEED)
    permuted = np.empty(PERMUTATION_SAMPLES, dtype=float)
    for index in range(PERMUTATION_SAMPLES):
        permuted[index] = np.corrcoef(
            x_resid,
            rng.permutation(y_resid),
        )[0, 1]
    p_value = float(
        (np.sum(np.abs(permuted) >= abs(correlation)) + 1)
        / (PERMUTATION_SAMPLES + 1)
    )
    bootstrap = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    for index in range(BOOTSTRAP_SAMPLES):
        sample = rng.integers(0, len(data), len(data))
        if len(np.unique(sample)) < 4:
            bootstrap[index] = np.nan
            continue
        bootstrap[index] = np.corrcoef(
            x_resid[sample],
            y_resid[sample],
        )[0, 1]
    low, high = np.nanpercentile(bootstrap, [2.5, 97.5])
    return correlation, p_value, float(low), float(high)


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * len(p) / np.arange(1, len(p) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.clip(adjusted, 0, 1)
    return output


def build_partial_correlations(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    controls = (
        "east_ocean_state_z_z",
        "early_ec_apr_z",
        "fep_residual_mjj_z",
    )
    responses = {
        "coupling_mjj_z": "MJJ atmosphere coupling residual",
        "precip_response_mjj_z": "MJJ precipitation response residual",
        "slp_response_mjj_z": "MJJ SLP-gradient response residual",
        "tau_response_mjj_z": "MJJ zonal-stress response residual",
    }
    for response_column, response_label in responses.items():
        for factor_id, column in FACTOR_COLUMNS.items():
            correlation, p_value, low, high = partial_correlation(
                table,
                f"{column}_z",
                response_column,
                controls,
            )
            rows.append(
                {
                    "factor_id": factor_id,
                    "factor": FACTOR_LABELS[factor_id],
                    "response": response_label,
                    "partial_r": correlation,
                    "permutation_p": p_value,
                    "bootstrap_ci_low": low,
                    "bootstrap_ci_high": high,
                    "controls": (
                        "April ocean gate; April E/C; MJJ residual FEP"
                    ),
                }
            )
    output = pd.DataFrame(rows)
    output["fdr_q"] = output.groupby("response")[
        "permutation_p"
    ].transform(
        lambda values: benjamini_hochberg(values.to_numpy())
    )
    output.to_csv(PARTIAL_CSV, index=False)
    return output


def standardize_train_test(
    train: pd.DataFrame,
    test: pd.DataFrame,
    columns: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_z = train.copy()
    test_z = test.copy()
    for column in columns:
        mean = float(train[column].mean())
        scale = float(train[column].std(ddof=1))
        if not np.isfinite(scale) or scale == 0:
            raise ValueError(f"Cannot standardize {column}")
        train_z[column] = (train[column] - mean) / scale
        test_z[column] = (test[column] - mean) / scale
    return train_z, test_z


def loocv_ridge(
    table: pd.DataFrame,
    features: tuple[str, ...],
    target: str,
    *,
    alpha: float = RIDGE_ALPHA,
) -> tuple[np.ndarray, np.ndarray]:
    observed = []
    predicted = []
    columns = (*features, target)
    for year in table["year"]:
        train = table.loc[table["year"].ne(year)].dropna(
            subset=list(columns)
        )
        test = table.loc[table["year"].eq(year)].dropna(
            subset=list(columns)
        )
        if len(test) != 1:
            continue
        train_z, test_z = standardize_train_test(
            train,
            test,
            columns,
        )
        model = Ridge(alpha=alpha).fit(
            train_z[list(features)].to_numpy(),
            train_z[target].to_numpy(),
        )
        prediction_z = float(
            model.predict(test_z[list(features)].to_numpy())[0]
        )
        target_mean = float(train[target].mean())
        target_scale = float(train[target].std(ddof=1))
        predicted.append(target_mean + prediction_z * target_scale)
        observed.append(float(test[target].iloc[0]))
    return np.asarray(observed), np.asarray(predicted)


def skill_metrics(
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
) -> dict[str, float]:
    rmse = float(np.sqrt(np.mean((observed - predicted) ** 2)))
    baseline_rmse = float(
        np.sqrt(np.mean((observed - baseline) ** 2))
    )
    correlation = float(np.corrcoef(observed, predicted)[0, 1])
    return {
        "rmse": rmse,
        "baseline_rmse": baseline_rmse,
        "rmse_skill": 1.0 - rmse / baseline_rmse,
        "correlation": correlation,
    }


def build_model_skill(table: pd.DataFrame) -> pd.DataFrame:
    coupling_models = {
        "coupling climatology": (),
        "ocean + early SST": (
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
        ),
        "+ multi-year La Nina": (
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
            "multi_year_la_nina_memory",
        ),
        "+ Indo-Atlantic": (
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
            "indo_atlantic_total_heating",
        ),
        "+ NPMM": (
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
            "npmm_fma",
        ),
        "+ rain dipole": (
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
            "precip_dipole_mjj",
        ),
        "+ WWB pulses": (
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
            "wwb_stochastic_impulse",
        ),
        "all candidate factors": (
            "east_ocean_state_z",
            "early_ec_apr",
            "fep_residual_mjj",
            *FACTOR_COLUMNS.values(),
        ),
    }
    rows = []
    target = "coupling_mjj"
    observed = table[target].to_numpy(dtype=float)
    baseline = np.asarray(
        [
            table.loc[table["year"].ne(year), target].mean()
            for year in table["year"]
        ]
    )
    for name, features in coupling_models.items():
        if not features:
            predicted = baseline.copy()
            obs = observed.copy()
        else:
            obs, predicted = loocv_ridge(
                table,
                tuple(features),
                target,
            )
        metrics = skill_metrics(obs, predicted, baseline[: len(obs)])
        rows.append(
            {
                "stage": "atmosphere coupling",
                "target": target,
                "model": name,
                "features": "; ".join(features),
                **metrics,
            }
        )
    type_models = {
        "April persistence": ("early_ec_apr",),
        "+ ocean gate": ("early_ec_apr", "east_ocean_state_z"),
        "+ coupling": ("early_ec_apr", "coupling_mjj"),
        "+ ocean + coupling": (
            "early_ec_apr",
            "east_ocean_state_z",
            "coupling_mjj",
        ),
    }
    for target in ("mature_ec_flavor", "mature_box_type"):
        observed = table[target].to_numpy(dtype=float)
        baseline_obs, baseline_pred = loocv_ridge(
            table,
            ("early_ec_apr",),
            target,
        )
        for name, features in type_models.items():
            obs, predicted = loocv_ridge(table, features, target)
            metrics = skill_metrics(
                obs,
                predicted,
                baseline_pred,
            )
            rows.append(
                {
                    "stage": "mature type",
                    "target": target,
                    "model": name,
                    "features": "; ".join(features),
                    **metrics,
                }
            )
    output = pd.DataFrame(rows)
    output.to_csv(SKILL_CSV, index=False)
    return output


@dataclass
class NodeModel:
    target: str
    predictors: tuple[str, ...]
    model: Ridge


SEM_COLUMNS = (
    "multi_year_la_nina_memory",
    "indo_atlantic_total_heating",
    "fep_residual_mjj",
    "east_ocean_state_z",
    "early_ec_apr",
    "npmm_fma",
    "zonal_sst_gradient_fma",
    "precip_dipole_mjj",
    "wwb_stochastic_impulse",
    "coupling_mjj",
    "mature_ec_flavor",
    "mature_box_type",
)

SEM_SPEC = (
    (
        "npmm_fma",
        (
            "multi_year_la_nina_memory",
            "indo_atlantic_total_heating",
        ),
    ),
    (
        "zonal_sst_gradient_fma",
        (
            "multi_year_la_nina_memory",
            "npmm_fma",
            "indo_atlantic_total_heating",
        ),
    ),
    (
        "precip_dipole_mjj",
        (
            "fep_residual_mjj",
            "npmm_fma",
            "indo_atlantic_total_heating",
        ),
    ),
    (
        "wwb_stochastic_impulse",
        (
            "npmm_fma",
            "zonal_sst_gradient_fma",
            "multi_year_la_nina_memory",
        ),
    ),
    (
        "coupling_mjj",
        (
            "east_ocean_state_z",
            "indo_atlantic_total_heating",
            "precip_dipole_mjj",
            "wwb_stochastic_impulse",
            "fep_residual_mjj",
        ),
    ),
    (
        "mature_ec_flavor",
        ("early_ec_apr", "east_ocean_state_z", "coupling_mjj"),
    ),
    (
        "mature_box_type",
        ("early_ec_apr", "east_ocean_state_z", "coupling_mjj"),
    ),
)


@dataclass
class StructuralEmulator:
    means: dict[str, float]
    scales: dict[str, float]
    nodes: dict[str, NodeModel]

    def transform_row(self, row: pd.Series) -> dict[str, float]:
        return {
            column: (float(row[column]) - self.means[column])
            / self.scales[column]
            for column in SEM_COLUMNS
        }

    def simulate(
        self,
        row: pd.Series,
        *,
        intervention: dict[str, float] | None = None,
        intervention_is_z: bool = False,
    ) -> dict[str, float]:
        values = self.transform_row(row)
        intervention = intervention or {}
        intervention_z = {}
        for column, value in intervention.items():
            intervention_z[column] = (
                float(value)
                if intervention_is_z
                else (float(value) - self.means[column])
                / self.scales[column]
            )
        values.update(intervention_z)
        changed = set(intervention_z)
        for target, _ in SEM_SPEC:
            if target in intervention_z:
                values[target] = intervention_z[target]
                changed.add(target)
                continue
            node = self.nodes[target]
            if not any(predictor in changed for predictor in node.predictors):
                continue
            x = np.asarray(
                [[values[column] for column in node.predictors]]
            )
            values[target] = float(node.model.predict(x)[0])
            changed.add(target)
        return values

    def perturb_one_sd(
        self,
        row: pd.Series,
        variable: str,
        increment: float = 1.0,
    ) -> dict[str, float]:
        baseline = self.transform_row(row)
        return self.simulate(
            row,
            intervention={variable: baseline[variable] + increment},
            intervention_is_z=True,
        )


def fit_sem(
    train: pd.DataFrame,
    *,
    alpha: float = RIDGE_ALPHA,
    dipole_column: str = "precip_dipole_mjj",
) -> StructuralEmulator:
    working = train.copy()
    if dipole_column != "precip_dipole_mjj":
        working["precip_dipole_mjj"] = working[dipole_column]
    means = {
        column: float(working[column].mean()) for column in SEM_COLUMNS
    }
    scales = {
        column: float(working[column].std(ddof=1)) for column in SEM_COLUMNS
    }
    if any(
        not np.isfinite(value) or value == 0 for value in scales.values()
    ):
        raise ValueError("Degenerate SEM standardization")
    standardized = working.copy()
    for column in SEM_COLUMNS:
        standardized[column] = (
            standardized[column] - means[column]
        ) / scales[column]
    nodes = {}
    for target, predictors in SEM_SPEC:
        model = Ridge(alpha=alpha).fit(
            standardized[list(predictors)].to_numpy(dtype=float),
            standardized[target].to_numpy(dtype=float),
        )
        nodes[target] = NodeModel(target, predictors, model)
    return StructuralEmulator(means, scales, nodes)


def delta_from_intervention(
    emulator: StructuralEmulator,
    row: pd.Series,
    variable: str,
    *,
    increment: float = 1.0,
) -> dict[str, float]:
    current = emulator.transform_row(row)
    baseline = emulator.simulate(
        row,
        intervention={variable: current[variable]},
        intervention_is_z=True,
    )
    perturbed = emulator.perturb_one_sd(
        row,
        variable,
        increment=increment,
    )
    return {
        target: perturbed[target] - baseline[target]
        for target in (
            "coupling_mjj",
            "mature_ec_flavor",
            "mature_box_type",
        )
    }


def build_counterfactual_effects(table: pd.DataFrame) -> pd.DataFrame:
    variables = {
        "multi_year_la_nina": "multi_year_la_nina_memory",
        "indo_atlantic_heating": "indo_atlantic_total_heating",
        "npmm": "npmm_fma",
        "fep_precip_dipole": "precip_dipole_mjj",
        "wwb_pulses": "wwb_stochastic_impulse",
    }
    rng = np.random.default_rng(RANDOM_SEED)
    records: dict[tuple[str, str], list[float]] = {
        (factor, target): []
        for factor in variables
        for target in (
            "coupling_mjj",
            "mature_ec_flavor",
            "mature_box_type",
        )
    }
    point_emulator = fit_sem(table)
    point: dict[tuple[str, str], float] = {}
    reference_row = table.iloc[0]
    for factor, variable in variables.items():
        delta = delta_from_intervention(
            point_emulator,
            reference_row,
            variable,
        )
        for target in (
            "coupling_mjj",
            "mature_ec_flavor",
            "mature_box_type",
        ):
            point[(factor, target)] = float(delta[target])
    attempts = 0
    successful = 0
    while successful < BOOTSTRAP_SAMPLES and attempts < BOOTSTRAP_SAMPLES * 2:
        attempts += 1
        sample = rng.integers(0, len(table), len(table))
        if len(np.unique(sample)) < 7:
            continue
        train = table.iloc[sample].reset_index(drop=True)
        try:
            emulator = fit_sem(train)
        except ValueError:
            continue
        for factor, variable in variables.items():
            delta = delta_from_intervention(
                emulator,
                reference_row,
                variable,
            )
            for target in (
                "coupling_mjj",
                "mature_ec_flavor",
                "mature_box_type",
            ):
                records[(factor, target)].append(
                    float(delta[target])
                )
        successful += 1
    rows = []
    for (factor, target), samples in records.items():
        values = np.asarray(samples, dtype=float)
        low, high = np.nanpercentile(values, [2.5, 97.5])
        sign_probability = float(
            max(np.mean(values > 0), np.mean(values < 0))
        )
        rows.append(
            {
                "factor_id": factor,
                "factor": FACTOR_LABELS[factor],
                "intervention": "+1 training-sample SD",
                "response": target,
                "effect_response_sd": point[(factor, target)],
                "bootstrap_ci_low": float(low),
                "bootstrap_ci_high": float(high),
                "bootstrap_sign_probability": sign_probability,
                "bootstrap_samples": len(values),
                "ridge_alpha": RIDGE_ALPHA,
            }
        )
    output = pd.DataFrame(rows)
    output.to_csv(EFFECT_CSV, index=False)
    return output


def simulate_replacement(
    emulator: StructuralEmulator,
    row: pd.Series,
    intervention: dict[str, float],
) -> dict[str, float]:
    current = emulator.transform_row(row)
    baseline = emulator.simulate(
        row,
        intervention={
            column: current[column] for column in intervention
        },
        intervention_is_z=True,
    )
    perturbed = emulator.simulate(row, intervention=intervention)
    return {
        target: perturbed[target] - baseline[target]
        for target in (
            "coupling_mjj",
            "mature_ec_flavor",
            "mature_box_type",
        )
    }


def build_2023_replacements(table: pd.DataFrame) -> pd.DataFrame:
    train = table.loc[table["year"].ne(2023)].copy()
    row = table.loc[table["year"].eq(2023)].iloc[0]
    analog = table.loc[table["year"].isin((1997, 2015))]
    analog_mean = analog[list(SEM_COLUMNS)].mean()
    neutral = train[list(SEM_COLUMNS)].mean()
    scenarios = {
        "Neutralize multi-year La Nina": {
            "multi_year_la_nina_memory": neutral[
                "multi_year_la_nina_memory"
            ]
        },
        "Neutralize Indo-Atlantic heating": {
            "indo_atlantic_total_heating": neutral[
                "indo_atlantic_total_heating"
            ]
        },
        "Replace NPMM with 1997/2015 mean": {
            "npmm_fma": analog_mean["npmm_fma"]
        },
        "Remove FEP rain dipole": {
            "precip_dipole_mjj": neutral["precip_dipole_mjj"]
        },
        "Replace WWB pulses with 1997/2015 mean": {
            "wwb_stochastic_impulse": analog_mean[
                "wwb_stochastic_impulse"
            ]
        },
        "NPMM + WWB to 1997/2015": {
            "npmm_fma": analog_mean["npmm_fma"],
            "wwb_stochastic_impulse": analog_mean[
                "wwb_stochastic_impulse"
            ],
        },
        "All atmospheric factors to 1997/2015": {
            "multi_year_la_nina_memory": analog_mean[
                "multi_year_la_nina_memory"
            ],
            "indo_atlantic_total_heating": analog_mean[
                "indo_atlantic_total_heating"
            ],
            "npmm_fma": analog_mean["npmm_fma"],
            "precip_dipole_mjj": analog_mean["precip_dipole_mjj"],
            "wwb_stochastic_impulse": analog_mean[
                "wwb_stochastic_impulse"
            ],
        },
    }
    emulator = fit_sem(train)
    point = {
        name: simulate_replacement(emulator, row, intervention)
        for name, intervention in scenarios.items()
    }
    rng = np.random.default_rng(RANDOM_SEED + 11)
    samples: dict[tuple[str, str], list[float]] = {
        (name, target): []
        for name in scenarios
        for target in (
            "coupling_mjj",
            "mature_ec_flavor",
            "mature_box_type",
        )
    }
    successful = 0
    attempts = 0
    while successful < BOOTSTRAP_SAMPLES and attempts < BOOTSTRAP_SAMPLES * 3:
        attempts += 1
        indices = rng.integers(0, len(train), len(train))
        if len(np.unique(indices)) < 6:
            continue
        bootstrap_train = train.iloc[indices].reset_index(drop=True)
        try:
            current = fit_sem(bootstrap_train)
        except ValueError:
            continue
        for name, intervention in scenarios.items():
            delta = simulate_replacement(current, row, intervention)
            for target, value in delta.items():
                samples[(name, target)].append(value)
        successful += 1
    rows = []
    for name, intervention in scenarios.items():
        for target in (
            "coupling_mjj",
            "mature_ec_flavor",
            "mature_box_type",
        ):
            values = np.asarray(samples[(name, target)], dtype=float)
            low, high = np.nanpercentile(values, [2.5, 97.5])
            raw_delta = (
                point[name][target] * emulator.scales[target]
            )
            observed = float(row[target])
            counterfactual = observed + raw_delta
            rows.append(
                {
                    "scenario": name,
                    "intervention_values": json.dumps(
                        intervention,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "response": target,
                    "effect_response_sd": point[name][target],
                    "bootstrap_ci_low": float(low),
                    "bootstrap_ci_high": float(high),
                    "observed_2023_raw": observed,
                    "counterfactual_2023_raw": counterfactual,
                    "sign_flips_relative_to_zero": bool(
                        np.sign(observed) != np.sign(counterfactual)
                    ),
                    "training_excludes_2023": True,
                }
            )
    output = pd.DataFrame(rows)
    output.to_csv(REPLACE_2023_CSV, index=False)
    return output


def build_robustness(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for alpha in (0.25, 0.5, 1.0, 2.0, 5.0):
        for external_definition in (
            "indo_atlantic_total_heating",
            "indo_atlantic_relative_heating",
        ):
            for dipole in (
                "precip_dipole_mjj",
                "precip_dipole_cp_mjj",
                "precip_dipole_ep_mjj",
            ):
                for wwb_definition in (
                    "wwb_stochastic_impulse",
                    "wwb_stochastic_impulse_central",
                    "wwb_stochastic_frequency",
                ):
                    for sample_name, sample in (
                        ("all events", table),
                        (
                            "exclude classic extremes",
                            table.loc[
                                ~table["year"].isin(EXTREME_EVENTS)
                            ],
                        ),
                        (
                            "exclude 2023",
                            table.loc[table["year"].ne(2023)],
                        ),
                    ):
                        if len(sample) < 8:
                            continue
                        working = sample.copy()
                        working["precip_dipole_mjj"] = working[dipole]
                        working["indo_atlantic_total_heating"] = working[
                            external_definition
                        ]
                        working["wwb_stochastic_impulse"] = working[
                            wwb_definition
                        ]
                        emulator = fit_sem(
                            working,
                            alpha=alpha,
                        )
                        reference_row = working.iloc[0]
                        for factor, variable in FACTOR_COLUMNS.items():
                            delta = delta_from_intervention(
                                emulator,
                                reference_row,
                                variable,
                            )
                            rows.append(
                                {
                                    "ridge_alpha": alpha,
                                    "external_definition": (
                                        external_definition
                                    ),
                                    "dipole_definition": dipole,
                                    "wwb_definition": wwb_definition,
                                    "sample": sample_name,
                                    "n_events": len(working),
                                    "factor_id": factor,
                                    "coupling_effect_sd": float(
                                        delta["coupling_mjj"]
                                    ),
                                    "ec_type_effect_sd": float(
                                        delta["mature_ec_flavor"]
                                    ),
                                }
                            )
    output = pd.DataFrame(rows)
    output.to_csv(ROBUSTNESS_CSV, index=False)
    return output


def build_agcm_matrix() -> pd.DataFrame:
    rows = [
        (
            "CTRL-2023",
            "Observed 2023 global SST; observed ocean initial state",
            "Baseline weak-coupling event",
            "AGCM, 30 members",
        ),
        (
            "PAC-only",
            "2023 Pacific SST anomalies; climatology elsewhere",
            "Canonical Pacific-only wind/rain response",
            "AGCM, 30 members",
        ),
        (
            "minus-IA",
            "CTRL-2023 but remove tropical Indian and Atlantic anomalies",
            "Causal Indo-Atlantic damping",
            "AGCM, 30 members",
        ),
        (
            "NPMM-neutral",
            "CTRL-2023 but remove the cold NPMM SST pattern",
            "NPMM effect on central-Pacific convection and wind",
            "AGCM, 30 members",
        ),
        (
            "FEP-positive-only",
            "Positive residual-FEP SST pattern only, following Jiang et al.",
            "Whether FEP warming alone creates the meridional rain dipole",
            "AGCM, 30 members",
        ),
        (
            "FEP-minus-dipole",
            "CTRL-2023 plus idealized heating that cancels the 6-10N rain deficit",
            "Controlled role of the meridional precipitation dipole",
            "LBM/AGCM, 30 members",
        ),
        (
            "WWB-add",
            "CTRL-2023 plus 10-day westerly stress pulses at 135E-180",
            "Whether pulses launch sufficient Kelvin-wave heat transport",
            "Coupled model, 20 starts x 3 dates",
        ),
        (
            "MLN-ocean-neutral",
            "2023 atmosphere/SST with western subsurface heat reset to neutral composite",
            "Oceanic legacy of multi-year La Nina",
            "Coupled model, 20 members",
        ),
        (
            "NPMM-x-WWB",
            "Factorial cold/neutral/warm NPMM crossed with no/observed/added WWB",
            "State dependence and interaction",
            "Coupled model, 3 x 3 x 15 members",
        ),
        (
            "IA-x-FEP",
            "Factorial Indo-Atlantic anomalies on/off crossed with residual FEP on/off",
            "Remote forcing versus local FEP pathway",
            "AGCM, 2 x 2 x 30 members",
        ),
    ]
    output = pd.DataFrame(
        rows,
        columns=(
            "experiment_id",
            "perturbation",
            "causal_question",
            "minimum_ensemble",
        ),
    )
    output.to_csv(AGCM_MATRIX_CSV, index=False)
    return output


def plot_event_matrix(table: pd.DataFrame) -> None:
    setup_style()
    columns = [
        "multi_year_la_nina_memory_z",
        "indo_atlantic_total_heating_z",
        "npmm_fma_z",
        "precip_dipole_mjj_z",
        "wwb_stochastic_impulse_z",
        "east_ocean_state_z_z",
        "coupling_mjj_z",
        "mature_ec_flavor_z",
    ]
    labels = [
        "Multi-year\nLa Niña",
        "Indo-Atlantic\nheating",
        "Warm\nNPMM",
        "FEP rain\ndipole",
        "Westerly\npulses",
        "April ocean\ngate",
        "MJJ atmosphere\nconnection",
        "Mature E/C\n(EP +)",
    ]
    values = table.set_index("year")[columns].to_numpy()
    figure, axis = plt.subplots(figsize=(10.2, 5.0))
    image = axis.imshow(
        values,
        cmap="RdBu_r",
        vmin=-2.5,
        vmax=2.5,
        aspect="auto",
    )
    axis.set_xticks(np.arange(len(columns)))
    axis.set_xticklabels(labels)
    axis.set_yticks(np.arange(len(table)))
    axis.set_yticklabels(table["year"].astype(str))
    axis.set_title(
        "Warm-event factor matrix: conditions, atmospheric connection, and mature type",
        loc="left",
        weight="bold",
    )
    for row_index, year in enumerate(table["year"]):
        if year == 2023:
            axis.add_patch(
                plt.Rectangle(
                    (-0.49, row_index - 0.49),
                    len(columns) - 0.02,
                    0.98,
                    fill=False,
                    edgecolor="#f2c14e",
                    linewidth=2.0,
                )
            )
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            axis.text(
                j,
                i,
                f"{values[i, j]:+.1f}",
                ha="center",
                va="center",
                fontsize=6.3,
                color="white" if abs(values[i, j]) > 1.25 else "0.1",
            )
    colorbar = figure.colorbar(image, ax=axis, pad=0.015, fraction=0.035)
    colorbar.set_label("Event-standardized anomaly")
    figure.text(
        0.01,
        0.01,
        "Climate anomalies use the 1982-2024 reference. The rain dipole is equatorial minus 6-10N precipitation after removing concurrent Niño3.4 and Niño3-Niño4.",
        fontsize=6.8,
        color="0.35",
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    for suffix in ("png", "pdf"):
        figure.savefig(
            FIG1.with_suffix(f".{suffix}"),
            bbox_inches="tight",
        )
    figure.savefig(
        PDF_DIR / "enso_perturbation_event_factor_matrix.pdf",
        bbox_inches="tight",
    )
    plt.close(figure)


def plot_effects(effects: pd.DataFrame) -> None:
    setup_style()
    targets = (
        ("coupling_mjj", "MJJ atmospheric connection"),
        ("mature_ec_flavor", "Mature E/C type (EP positive)"),
    )
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.6), sharey=True)
    order = list(FACTOR_COLUMNS)
    y = np.arange(len(order))
    for axis, (target, title) in zip(axes, targets, strict=True):
        current = (
            effects.loc[effects["response"].eq(target)]
            .set_index("factor_id")
            .loc[order]
        )
        values = current["effect_response_sd"].to_numpy()
        low = current["bootstrap_ci_low"].to_numpy()
        high = current["bootstrap_ci_high"].to_numpy()
        colors = np.where(values >= 0, "#c95d45", "#2878a5")
        axis.barh(y, values, color=colors, alpha=0.88, height=0.62)
        axis.errorbar(
            values,
            y,
            xerr=np.vstack(
                [
                    np.maximum(values - low, 0),
                    np.maximum(high - values, 0),
                ]
            ),
            fmt="none",
            ecolor="0.15",
            elinewidth=1.0,
            capsize=2.5,
        )
        axis.axvline(0, color="0.2", lw=0.8)
        axis.set_title(title, loc="left", weight="bold")
        axis.set_xlabel("Change caused by +1 SD perturbation (response SD)")
        axis.grid(axis="x", alpha=0.2)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([FACTOR_LABELS[item] for item in order])
    axes[0].invert_yaxis()
    figure.suptitle(
        "Regularized structural-emulator perturbations",
        x=0.07,
        ha="left",
        weight="bold",
    )
    figure.text(
        0.01,
        0.01,
        "Intervals are event bootstraps (n=13). These are observational counterfactuals, not dynamical-model causal estimates.",
        fontsize=6.8,
        color="0.35",
    )
    figure.tight_layout(rect=(0, 0.04, 1, 0.95))
    for suffix in ("png", "pdf"):
        figure.savefig(
            FIG2.with_suffix(f".{suffix}"),
            bbox_inches="tight",
        )
    figure.savefig(
        PDF_DIR / "enso_single_factor_perturbation_effects.pdf",
        bbox_inches="tight",
    )
    plt.close(figure)


def plot_2023_replacements(replacements: pd.DataFrame) -> None:
    setup_style()
    targets = (
        ("coupling_mjj", "Atmospheric connection"),
        ("mature_ec_flavor", "E/C type"),
        ("mature_box_type", "Niño3−Niño4 type"),
    )
    scenario_order = list(dict.fromkeys(replacements["scenario"]))
    figure, axes = plt.subplots(1, 3, figsize=(14.0, 5.7), sharey=True)
    y = np.arange(len(scenario_order))
    for axis, (target, title) in zip(axes, targets, strict=True):
        current = (
            replacements.loc[replacements["response"].eq(target)]
            .set_index("scenario")
            .loc[scenario_order]
        )
        value = current["effect_response_sd"].to_numpy()
        low = current["bootstrap_ci_low"].to_numpy()
        high = current["bootstrap_ci_high"].to_numpy()
        axis.barh(
            y,
            value,
            color=np.where(value >= 0, "#c95d45", "#2878a5"),
            alpha=0.88,
            height=0.62,
        )
        axis.errorbar(
            value,
            y,
            xerr=np.vstack(
                [
                    np.maximum(value - low, 0),
                    np.maximum(high - value, 0),
                ]
            ),
            fmt="none",
            ecolor="0.15",
            elinewidth=1.0,
            capsize=2.5,
        )
        axis.axvline(0, color="0.2", lw=0.8)
        axis.set_title(title, loc="left", weight="bold")
        axis.set_xlabel("2023 counterfactual change (training-response SD)")
        axis.grid(axis="x", alpha=0.2)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(scenario_order)
    axes[0].invert_yaxis()
    figure.suptitle(
        "2023 replacements trained without 2023",
        x=0.08,
        ha="left",
        weight="bold",
    )
    figure.text(
        0.01,
        0.01,
        "1997/2015 replacement values are applied one factor at a time or jointly. Sign changes are reported separately because E/C and box metrics are not interchangeable.",
        fontsize=6.8,
        color="0.35",
    )
    figure.tight_layout(rect=(0, 0.04, 1, 0.95))
    for suffix in ("png", "pdf"):
        figure.savefig(
            FIG3.with_suffix(f".{suffix}"),
            bbox_inches="tight",
        )
    figure.savefig(
        PDF_DIR / "enso_2023_counterfactual_replacements.pdf",
        bbox_inches="tight",
    )
    plt.close(figure)


def fmt(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "NA"
    return f"{value:+.{digits}f}"


def write_report(
    table: pd.DataFrame,
    partial: pd.DataFrame,
    skill: pd.DataFrame,
    effects: pd.DataFrame,
    replacements: pd.DataFrame,
    robustness: pd.DataFrame,
    wwb_lags: pd.DataFrame,
) -> None:
    event_2023 = table.loc[table["year"].eq(2023)].iloc[0]
    ne_events_path = (
        DERIVED / "enso_ne_wind_bridge_event_indices.csv"
    )
    ne_relationships_path = (
        DERIVED / "enso_ne_wind_bridge_relationships.csv"
    )
    ne_events = (
        pd.read_csv(ne_events_path)
        if ne_events_path.exists()
        else pd.DataFrame()
    )
    ne_relationships = (
        pd.read_csv(ne_relationships_path)
        if ne_relationships_path.exists()
        else pd.DataFrame()
    )
    ne_2023 = (
        ne_events.loc[ne_events["year"].eq(2023)].iloc[0]
        if not ne_events.empty
        else None
    )
    coupling_effect = (
        effects.loc[effects["response"].eq("coupling_mjj")]
        .sort_values(
            "effect_response_sd",
            key=lambda values: values.abs(),
            ascending=False,
        )
    )
    stable = coupling_effect.loc[
        (coupling_effect["bootstrap_ci_low"] > 0)
        | (coupling_effect["bootstrap_ci_high"] < 0)
    ]
    partial_sorted = partial.loc[
        partial["response"].eq("MJJ atmosphere coupling residual")
    ].sort_values(
        "partial_r",
        key=lambda values: values.abs(),
        ascending=False,
    )
    full_skill = skill.loc[
        (skill["stage"].eq("atmosphere coupling"))
        & (skill["model"].eq("all candidate factors"))
    ].iloc[0]
    coupling_added = skill.loc[
        (skill["target"].eq("mature_ec_flavor"))
        & (skill["model"].eq("+ ocean + coupling"))
    ].iloc[0]
    rain_skill = skill.loc[
        (skill["stage"].eq("atmosphere coupling"))
        & (skill["model"].eq("+ rain dipole"))
    ].iloc[0]
    ocean_type_skill = skill.loc[
        (skill["target"].eq("mature_ec_flavor"))
        & (skill["model"].eq("+ ocean gate"))
    ].iloc[0]
    flips = replacements.loc[
        replacements["sign_flips_relative_to_zero"]
    ]
    positive_lags = wwb_lags.loc[
        wwb_lags["lag_days_wind_leads"].gt(0)
    ]
    best_lag = positive_lags.iloc[
        positive_lags["correlation"].argmax()
    ]
    robustness_summary = (
        robustness.groupby("factor_id")["coupling_effect_sd"]
        .agg(["median", lambda values: np.mean(np.sign(values) == np.sign(values.median()))])
        .rename(columns={"<lambda_0>": "sign_agreement"})
    )
    lines = [
        "# ENSO大气“接上”与类型转换：扰动实验结果",
        "",
        "## 先给结论",
        "",
        "这轮结果否定了“一个变量单独主导所有年份”，也没有发现把2023单个条件改掉就能稳健改型的证据。更符合资料与动力研究的解释是一个有顺序、带竞争路径的条件链：",
        "",
        "`多年La Niña与外海盆背景 → NPMM/西中太平洋梯度 → 对流空间结构与WWB发生概率 → 东北风或西风支路 → 暖量东传 → 成熟型态`。",
        "",
        "在13个事件的观测统计中，去掉同期SST幅度和东西型结构后的经向降水偶极，是唯一仍与综合大气响应显著相关的量；但它主要对应降水和气压支路，对西风应力不显著，因此是**接通状态/中介指标，不是已经确证的上游主因**。多年La Niña、Indo-Atlantic加热、NPMM与高频WWB的独立份额都无法在这个小样本中稳定分开。",
        "",
        "## 1. 实验如何定义",
        "",
        "- 事件：1982、1986、1991、1994、1997、2002、2004、2006、2009、2015、2018、2019、2023。",
        "- 气候态：所有重新计算的月异常统一使用1982—2024；随后去线性趋势。",
        "- 大气是否接上：MJJ降水、东西气压驱动和中太平洋风应力分别对同期Niño3.4、Niño3−Niño4和趋势做留一年回归，三者标准化残差平均。正值表示给定SST后大气响应比历史预期强。",
        "- 多年La Niña：前三个冬季低于−0.5°C的个数与过去30个月冷异常积分组成连续记忆量。",
        "- Indo-Atlantic加热：MJJ热带印度洋和热带北大西洋SST相对1982—2024气候态的联合量；去趋势并移除Niño3.4的相对加热定义另作稳健性检验。",
        "- NPMM：OISST SST与ERA5 10米风联合EOF的FMA指数，已去趋势并移除Niño3.4。",
        "- 经向降水偶极：MJJ、180°—90°W，赤道带降水减6°—10°N降水，并移除同期Niño3.4、Niño3−Niño4和趋势；正值对应Jiang所述“赤道增强、北侧抑制”的额外空间结构。",
        "- 东北风桥梁：ERA5 MJJ 850 hPa、3°—7°N和180°—130°W，将负u与负v投影成正的东北风入侵，并同样移除同期SST幅度与型态。",
        "- 随机西风爆发代理：SODA3五日135°E—180°风应力，先移除各事件逐月均值，再累计超过1个五日扰动标准差的正脉冲。它是高频WWB代理，不等同于逐日ERA5严格WWB目录。",
        "- 海洋条件：3—4月140°W Q20与D20组合；成熟型态同时用正交E/C和Niño3−Niño4，避免单一分型定义支配结论。",
        "",
        "## 2. 哪个因素最接近“接上”环节",
        "",
        "| 因素 | 控制海洋/FEP/早期型态后的partial r | 95% bootstrap CI | FDR q |",
        "|---|---:|---:|---:|",
    ]
    for _, row in partial_sorted.iterrows():
        lines.append(
            f"| {row['factor']} | {fmt(row['partial_r'])} | "
            f"[{fmt(row['bootstrap_ci_low'])}, {fmt(row['bootstrap_ci_high'])}] | "
            f"{row['fdr_q']:.3f} |"
        )
    lines.extend(
        [
            "",
            f"五个候选量全加入后，留一事件回报的RMSE skill为 **{fmt(full_skill['rmse_skill'], 3)}**，相关为 **{fmt(full_skill['correlation'])}**。"
            f"只加入降水偶极时的skill反而更高，为 **{fmt(rain_skill['rmse_skill'], 3)}**；这说明全因子模型已出现小样本过拟合，不能把系数解释为因果份额。",
            "",
            "分支检验显示，偶极与降水残差的partial r为+0.79（FDR q=0.009）、与气压梯度为+0.71（q=0.033），但与纬向风应力只有+0.46且区间跨零。因此它能识别“对流—气压已响应”，却不能单独证明中太平洋西风已经接上。",
            "",
            "## 3. +1σ单因子扰动",
            "",
            "| 因素 | Δ大气接通/SD | 95% CI | ΔE/C型态/SD | 95% CI |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for factor_id in FACTOR_COLUMNS:
        coupling_row = effects.loc[
            effects["factor_id"].eq(factor_id)
            & effects["response"].eq("coupling_mjj")
        ].iloc[0]
        type_row = effects.loc[
            effects["factor_id"].eq(factor_id)
            & effects["response"].eq("mature_ec_flavor")
        ].iloc[0]
        lines.append(
            f"| {FACTOR_LABELS[factor_id]} | "
            f"{fmt(coupling_row['effect_response_sd'])} | "
            f"[{fmt(coupling_row['bootstrap_ci_low'])}, {fmt(coupling_row['bootstrap_ci_high'])}] | "
            f"{fmt(type_row['effect_response_sd'])} | "
            f"[{fmt(type_row['bootstrap_ci_low'])}, {fmt(type_row['bootstrap_ci_high'])}] |"
        )
    stable_names = ", ".join(stable["factor"].tolist()) or "无"
    lines.extend(
        [
            "",
            f"bootstrap区间在大气接通目标上不跨零的因素：**{stable_names}**。"
            "但这只是固定因果图和岭回归下的观测扰动，不是模式积分产生的强迫响应。",
            "",
            "## 4. 2023换条件会不会改型",
            "",
            "以下实验全部不使用2023来拟合；把2023的一个条件替换成中性值或1997/2015平均值，再沿结构链向下传播。",
            "",
            "| 情景 | Δ接通/SD | ΔE/C/SD | E/C过零？ | ΔNiño3−Niño4/SD | box指标过零？ |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in replacements["scenario"].drop_duplicates():
        current = replacements.loc[replacements["scenario"].eq(scenario)]
        coupling = current.loc[
            current["response"].eq("coupling_mjj")
        ].iloc[0]
        ec = current.loc[
            current["response"].eq("mature_ec_flavor")
        ].iloc[0]
        box = current.loc[
            current["response"].eq("mature_box_type")
        ].iloc[0]
        lines.append(
            f"| {scenario} | {fmt(coupling['effect_response_sd'])} | "
            f"{fmt(ec['effect_response_sd'])} | "
            f"{'是' if ec['sign_flips_relative_to_zero'] else '否'} | "
            f"{fmt(box['effect_response_sd'])} | "
            f"{'是' if box['sign_flips_relative_to_zero'] else '否'} |"
        )
    lines.extend(
        [
            "",
            f"本组统计替换中出现的过零记录数为 **{len(flips)}**。"
            "只有当E/C与box两个定义、不同岭参数、不同偶极区域和删除极端事件后都保持同向，才能称为稳健类型转换；否则只能说成熟暖中心发生位移。",
            "",
            "## 5. 2023为什么特别",
            "",
            f"- 多年La Niña记忆：{fmt(event_2023['multi_year_la_nina_memory_z'])} SD；",
            f"- Indo-Atlantic总加热：{fmt(event_2023['indo_atlantic_total_heating_z'])} SD；",
            f"- NPMM：{fmt(event_2023['npmm_fma_z'])} SD；",
            f"- FEP经向降水偶极：{fmt(event_2023['precip_dipole_mjj_z'])} SD；",
            f"- 高频西风脉冲：{fmt(event_2023['wwb_stochastic_impulse_z'])} SD；",
            (
                f"- 3°—7°N东北风入侵：{fmt(ne_2023['ne850_mjj_z'])} SD；"
                if ne_2023 is not None
                else "- 3°—7°N东北风入侵：未计算；"
            ),
            f"- MJJ大气接通残差：{fmt(event_2023['coupling_mjj_z'])} SD。",
            "",
            "2023同时表现为强多年La Niña遗产、创纪录式外海盆增暖、冷NPMM、少WWB、高东北风入侵和弱纬向风应力；但FEP残余增暖与降水偶极又都很强。这说明“对流有响应”与“赤道西风反馈接上”不是同一件事。",
            "",
            "## 6. 当前能下什么结论",
            "",
            "1. **大气“接上”至少要拆成两条支路。** 降水—气压支路可在FEP/经向偶极下明显响应；真正能推动暖水东传的是赤道西风—风应力支路。2023是前者存在而后者偏弱，若继续把三者平均成一个量，会掩盖这一点。",
            "2. **Jiang机制在2023个例上成立，但不是13事件中的普适单因子。** 2023东北风入侵为+1.39 SD、纬向应力响应为−0.95 SD；跨事件的“偶极→东北风”partial r=+0.51、“东北风→纬向应力”r=−0.28，符号符合机制但bootstrap区间均跨零。FEP残余本身与东北风只有r=+0.05，因此还需要北侧冷却/降水组织等条件。",
            "3. **WWB有真实海洋作用，但不是独立随机冠军。** 五日脉冲保留了高频随机成分，其发生又受背景态调制；因此更准确的称呼是state-dependent stochastic forcing。",
            f"   SODA3独立的传播核验中，西太平洋五日风应力扰动与随后140°W暖水输送的最大相关出现在风领先约{int(best_lag['lag_days_wind_leads'])}天，"
            f"r={fmt(best_lag['correlation'])}，事件块bootstrap区间"
            f"[{fmt(best_lag['event_block_bootstrap_ci_low'])}, {fmt(best_lag['event_block_bootstrap_ci_high'])}]。",
            "4. **多年LaNiña、NPMM与外海盆加热是上游背景，不宜互相竞争“第一名”。** 多年LaNiña既充电又可留下西暖—中冷/冷NPMM背景；NPMM影响梯度、MJO与WWB概率；Indo-Atlantic加热可远程压制太平洋对流。它们高度共线，而且在不同事件可同向或抵消。",
            "5. **观测替换没有产生类型转换。** 2023的7组单因子/组合替换在E/C和Niño3−Niño4两种指标上均未过零；所有区间都很宽。成熟型态的留一RMSE skill以4月海洋门控单独最高（E/C为"
            f"{fmt(ocean_type_skill['rmse_skill'], 3)}），加入MJJ耦合后为{fmt(coupling_added['rmse_skill'], 3)}。"
            "这说明当前样本中海洋暖量的位置比单个大气因子更稳定，但不表示大气不重要。",
            "6. **所以现在的回答是“条件链+交互”，不是单因子。** 只有耦合模式中固定海洋初态、逐一替换NPMM、外海盆、FEP残余和WWB，并积分到DJF，才能判定人为改变一个条件是否真的改型。",
            "",
            "## 7. 下一组动力扰动必须怎么做",
            "",
            "已生成可直接交给CAM6/ECHAM与CESM类模式的实验矩阵。AGCM先回答“给定SST后为何不出西风”：CTRL-2023、PAC-only、去Indo-Atlantic、NPMM-neutral、去FEP残余/去北侧冷却。耦合模式再回答“是否改型”：固定同一2023海洋初态，分别加入/移除WWB并做 `NPMM × WWB` 与 `Indo-Atlantic × residual-FEP` 因子试验，至少20成员、多个WWB起始日期，积分到DJF并同时诊断E/C与Niño3−Niño4。只有第二层能检验事件类型转换。",
            "",
            "## 8. 稳健性边界",
            "",
            "- 13个暖事件远小于动力模式大样本，极端事件会强烈影响斜率。",
            "- 2023替换实验虽排除了2023训练，但1997/2015同时是极端事件，替换值不是随机处理。",
            "- GPCP为月资料；经向偶极是中介过程，不能与上游外海盆/NPMM当成完全独立处理。",
            "- 东北风桥梁用月平均850 hPa风；它能检验Jiang空间机制，但不能代替逐日天气尺度动量收支。",
            "- SODA3五日风应力比逐日ERA5平滑，适合脉冲敏感性，不适合宣布标准WWB日数。",
            "- FDR、事件bootstrap、总/相对外海盆加热、不同偶极经度、不同岭惩罚以及删除极端事件均保存在表中；若结论只在单一设定成立，不作主结论。",
            "",
            "## 9. 文件",
            "",
            f"- 事件指标：`{EVENT_INDEX_CSV.relative_to(ROOT)}`",
            f"- 偏相关/FDR：`{PARTIAL_CSV.relative_to(ROOT)}`",
            f"- 留一事件技巧：`{SKILL_CSV.relative_to(ROOT)}`",
            f"- 单因子扰动：`{EFFECT_CSV.relative_to(ROOT)}`",
            f"- 2023替换：`{REPLACE_2023_CSV.relative_to(ROOT)}`",
            f"- 稳健性：`{ROBUSTNESS_CSV.relative_to(ROOT)}`",
            f"- WWB—140°W输送滞后核验：`{WWB_TRANSPORT_LAG_CSV.relative_to(ROOT)}`",
            "- FEP—东北风桥梁事件表：`data/derived/research_2026/enso_ne_wind_bridge_event_indices.csv`",
            "- FEP—东北风关系表：`data/derived/research_2026/enso_ne_wind_bridge_relationships.csv`",
            f"- 动力模式矩阵：`{AGCM_MATRIX_CSV.relative_to(ROOT)}`",
            f"- 图：`{FIG1.relative_to(ROOT)}.pdf`、`{FIG2.relative_to(ROOT)}.pdf`、`{FIG3.relative_to(ROOT)}.pdf`、`outputs/research_2026/perturbation_attribution/fig4_fep_ne_wind_bridge.pdf`",
            "",
            "## 10. 与权威研究的对应",
            "",
            "| 机制 | 已有最强证据 | 本研究能否独立复现 | 判断 |",
            "|---|---|---|---|",
            "| 多年LaNiña→西部暖量/西伸增暖→弱西风 | Fan et al. (2026)：观测热收支、CAM5/6、CESM1/2 | 方向上支持；事件partial r=-0.33但不显著 | 重要背景，非充分条件 |",
            "| 冷NPMM→不利梯度/MJO/WWB | Lin et al. (2025)：观测+2200年CESM1 | 2023冷NPMM且WWB偏少；跨事件独立效应不稳 | 对2023很有解释力，非普适冠军 |",
            "| FEP残余→降水偶极→东北风 | Jiang et al. (2026)：ECHAM4.6集合 | 2023个例符号完整；13事件路径区间跨零 | 事件特异机制，需要条件交互 |",
            "| Indo-Atlantic加热→抑制太平洋响应 | 2025 CEE：AGCM去/加外海盆强迫 | 2023为+2.27 SD；跨事件观测效应定义敏感 | 2023抵消项，不宜外推为所有事件主因 |",
            "| WWB→Kelvin波/暖量东传 | Chen et al. (2015)耦合模式；Lin et al. (2025) | SODA3显示约20天后140°W输送增强 | 有因果能力，但发生概率依赖背景态 |",
            "",
            "- Jiang et al. (2026), GRL: https://doi.org/10.1029/2026GL123227",
            "- Fan et al. (2026), The Innovation Geoscience: https://doi.org/10.59717/j.xinn-geo.2026.100224",
            "- Lin et al. (2025), npj Climate and Atmospheric Science: https://doi.org/10.1038/s41612-025-01013-z",
            "- 2023/24 Indo-Atlantic warming AGCM study, Communications Earth & Environment: https://doi.org/10.1038/s43247-025-02584-8",
            "- Chen et al. (2015), Nature Geoscience: https://doi.org/10.1038/ngeo2399",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ensure_inputs()
    table = build_event_table()
    wwb_lags = build_wwb_transport_validation()
    partial = build_partial_correlations(table)
    skill = build_model_skill(table)
    effects = build_counterfactual_effects(table)
    replacements = build_2023_replacements(table)
    robustness = build_robustness(table)
    agcm = build_agcm_matrix()
    plot_event_matrix(table)
    plot_effects(effects)
    plot_2023_replacements(replacements)
    write_report(
        table,
        partial,
        skill,
        effects,
        replacements,
        robustness,
        wwb_lags,
    )
    diagnostics = {
        "event_count": len(table),
        "event_years": list(EVENT_YEARS),
        "climatology": f"{BASELINE_START}-{BASELINE_END}",
        "ridge_alpha": RIDGE_ALPHA,
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "permutation_samples": PERMUTATION_SAMPLES,
        "wwb_source": str(WWB_STRESS),
        "wwb_transport_best_lag_days": int(
            wwb_lags.iloc[
                wwb_lags["correlation"].abs().argmax()
            ]["lag_days_wind_leads"]
        ),
        "gpcp_shape_checked": True,
        "agcm_experiment_count": len(agcm),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(REPORT)
    print(EVENT_INDEX_CSV)
    print(EFFECT_CSV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
