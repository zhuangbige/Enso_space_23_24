#!/usr/bin/env python3
"""Diagnose ENSO type formation and air-sea coupling efficiency.

The analysis intentionally separates two questions:

1. Where does the oceanic warm anomaly penetrate and become stored?
2. Is the atmospheric response weaker or stronger than expected from the
   contemporaneous SST amplitude and pattern?

It is a mechanism analysis, not an El Nino onset forecast.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_type_coupling_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
RAW = ROOT / "data/raw"
OUT = ROOT / "outputs/research_2026/type_coupling"
PDF = ROOT / "output/pdf/enso_type_formation_coupling_efficiency.pdf"
PNG = OUT / "enso_type_formation_coupling_efficiency.png"
REPORT = OUT / "ENSO_TYPE_COUPLING_RESULTS_CN.md"

BASE_CSV = DERIVED / "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
BUDGET_CSV = DERIVED / "soda3_mixed_layer_budget_indices_1980_2024.csv"
GATE_CSV = DERIVED / "soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
OISST_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
PRECIP_FILES = [
    RAW / "era5/era5_monthly_precip_tropics_1deg_1980_2026_jan_may.nc",
    RAW / "era5/era5_monthly_precip_tropics_1deg_1980_2026_jun.nc",
]
ERA5_SINGLE = RAW / "era5/era5_monthly_single_levels_tropics_1982_2024.nc"
ERA5_COUPLING = RAW / "era5/coupling_monthly_1deg"

MONTHLY_CSV = DERIVED / "enso_type_coupling_monthly_1982_2023.csv"
EVENT_CSV = DERIVED / "enso_type_coupling_event_summary.csv"
CORRELATION_CSV = DERIVED / "enso_type_coupling_event_correlations.csv"
GROUP_CSV = DERIVED / "enso_type_coupling_group_summary.csv"
DIAGNOSTICS_JSON = DERIVED / "enso_type_coupling_diagnostics.json"

MONTHS = tuple(range(1, 7))
BASELINE_END = 2014
EVENT_YEARS = [
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
]
CLASSIC_EP = [1982, 1997, 2015]
CP_EVENTS = [1994, 2004, 2019]


def normalize_field(field: xr.DataArray) -> xr.DataArray:
    rename = {}
    if "valid_time" in field.coords:
        rename["valid_time"] = "time"
    if "latitude" in field.coords:
        rename["latitude"] = "lat"
    if "longitude" in field.coords:
        rename["longitude"] = "lon"
    field = field.rename(rename)
    field = field.assign_coords(lon=field.lon % 360.0)
    return field.sortby("lon").sortby("lat")


def weighted_box(
    field: xr.DataArray,
    lon0: float,
    lon1: float,
    lat0: float = -5.0,
    lat1: float = 5.0,
) -> xr.DataArray:
    field = normalize_field(field)
    subset = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if subset.sizes["lat"] == 0 or subset.sizes["lon"] == 0:
        raise ValueError(f"Empty box {lon0}:{lon1}, {lat0}:{lat1}")
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def to_frame(data: xr.DataArray, name: str) -> pd.DataFrame:
    times = pd.DatetimeIndex(pd.to_datetime(data.time.values))
    return pd.DataFrame(
        {
            "year": times.year,
            "month": times.month,
            name: np.asarray(data.values, dtype=float),
        }
    )


def load_oisst_gradient() -> pd.DataFrame:
    rows = []
    tags = {
        1: "jan",
        2: "feb",
        3: "mar",
        4: "apr",
        5: "may",
        6: "jun",
    }
    for month, tag in tags.items():
        path = OISST_DIR / f"oisst_sst_tropics_1deg_{tag}_1982_2026.nc"
        with xr.open_dataset(path, engine="scipy") as dataset:
            sst = dataset["sst"].sel(
                time=slice(f"1982-{month:02d}-01", f"2023-{month:02d}-28")
            ).load()
        west = weighted_box(sst, 130.0, 160.0)
        east = weighted_box(sst, 220.0, 250.0)
        current = to_frame(west, "sst_west_raw_c")
        current["sst_east_raw_c"] = np.asarray(east.values, dtype=float)
        rows.append(current)
    output = pd.concat(rows, ignore_index=True)
    output["sst_gradient_e_minus_w_raw_c"] = (
        output["sst_east_raw_c"] - output["sst_west_raw_c"]
    )
    return output.sort_values(["year", "month"])


def load_precip_gradient() -> pd.DataFrame:
    frames = []
    for path in PRECIP_FILES:
        with xr.open_dataset(path, engine="netcdf4") as dataset:
            field = normalize_field(dataset["tp"])
            time = pd.DatetimeIndex(pd.to_datetime(field.time.values))
            selected = np.flatnonzero(
                (time.year >= 1982)
                & (time.year <= 2023)
                & time.month.isin(MONTHS)
            )
            field = field.isel(time=selected)
            west = weighted_box(field, 130.0, 160.0).load() * 1000.0
            east = weighted_box(field, 220.0, 250.0).load() * 1000.0
        current = to_frame(west, "precip_west_raw_mmday")
        current["precip_east_raw_mmday"] = np.asarray(
            east.values, dtype=float
        )
        frames.append(current)
    output = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(["year", "month"])
        .sort_values(["year", "month"])
    )
    output["precip_gradient_e_minus_w_raw_mmday"] = (
        output["precip_east_raw_mmday"]
        - output["precip_west_raw_mmday"]
    )
    return output


def load_slp_gradient() -> pd.DataFrame:
    with xr.open_dataset(ERA5_SINGLE, engine="netcdf4") as dataset:
        field = normalize_field(dataset["msl"]) / 100.0
        time = pd.DatetimeIndex(pd.to_datetime(field.time.values))
        selected = np.flatnonzero(
            (time.year >= 1982)
            & (time.year <= 2023)
            & time.month.isin(MONTHS)
        )
        field = field.isel(time=selected)
        west = weighted_box(field, 130.0, 160.0).load()
        east = weighted_box(field, 220.0, 250.0).load()
    output = to_frame(west, "slp_west_raw_hpa")
    output["slp_east_raw_hpa"] = np.asarray(east.values, dtype=float)
    output["slp_drive_w_minus_e_raw_hpa"] = (
        output["slp_west_raw_hpa"] - output["slp_east_raw_hpa"]
    )
    return output


def load_tau() -> pd.DataFrame:
    rows = []
    for month in MONTHS:
        pieces = []
        for part in ("part01", "part02"):
            path = (
                ERA5_COUPLING
                / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            )
            with xr.open_dataset(path, engine="netcdf4") as dataset:
                pieces.append(normalize_field(dataset["avg_iews"]).load())
        field = xr.concat(pieces, dim="lon").sortby("lon")
        _, unique = np.unique(field.lon.values, return_index=True)
        field = field.isel(lon=np.sort(unique))
        tau = weighted_box(field, 160.0, 220.0)
        current = to_frame(tau, "tau_cwp_raw_nm2")
        current = current.loc[current["year"].between(1982, 2023)]
        rows.append(current)
    return pd.concat(rows, ignore_index=True).sort_values(["year", "month"])


def month_standardize(
    frame: pd.DataFrame,
    value: str,
    baseline_start: int = 1980,
    baseline_end: int = 2024,
) -> pd.Series:
    output = pd.Series(np.nan, index=frame.index, dtype=float)
    for month, group in frame.groupby("month"):
        baseline = group.loc[group["year"].between(baseline_start, baseline_end)]
        scale = float(baseline[value].std(ddof=1))
        output.loc[group.index] = (
            group[value] - float(baseline[value].mean())
        ) / scale
    return output


def ocean_indices() -> pd.DataFrame:
    budget = pd.read_csv(BUDGET_CSV)
    budget = budget[
        [
            "year",
            "month",
            "q20_dateline_pw_anom",
            "q20_220e_pw_anom",
        ]
    ].copy()
    budget["q180_z"] = month_standardize(
        budget, "q20_dateline_pw_anom"
    )
    budget["q220_z"] = month_standardize(budget, "q20_220e_pw_anom")
    budget["q20_penetration_z"] = (
        budget["q220_z"] - budget["q180_z"]
    ) / np.sqrt(2.0)

    gate = pd.read_csv(GATE_CSV)
    central = gate.loc[np.isclose(gate["longitude_e"], 190.0)].copy()
    east = gate.loc[np.isclose(gate["longitude_e"], 220.0)].copy()
    central["d190_z"] = month_standardize(central, "d20_m_anom")
    east["d220_z"] = month_standardize(east, "d20_m_anom")
    d20 = central[["year", "month", "d190_z", "d20_m_anom"]].rename(
        columns={"d20_m_anom": "d20_190e_anom_m"}
    ).merge(
        east[["year", "month", "d220_z", "d20_m_anom"]].rename(
            columns={"d20_m_anom": "d20_220e_anom_m"}
        ),
        on=["year", "month"],
        validate="one_to_one",
    )
    d20["d20_penetration_z"] = (
        d20["d220_z"] - d20["d190_z"]
    ) / np.sqrt(2.0)
    output = budget.merge(
        d20, on=["year", "month"], validate="one_to_one"
    )
    output["ocean_penetration_z"] = (
        output["q20_penetration_z"] + output["d20_penetration_z"]
    ) / 2.0
    return output


def cross_validated_expected_residual(
    frame: pd.DataFrame,
    response: str,
    predictors: list[str],
) -> pd.Series:
    """Historical-expectation residual using 1982-2014 and leave-one-year-out."""
    output = pd.Series(np.nan, index=frame.index, dtype=float)
    for month, group in frame.groupby("month"):
        baseline = group.loc[group["year"].le(BASELINE_END)]
        for index, test in group.iterrows():
            train = baseline.loc[baseline["year"].ne(test["year"])]
            x_train = np.column_stack(
                [
                    np.ones(len(train)),
                    train["year"].to_numpy(dtype=float) - 1998.0,
                    *[
                        train[column].to_numpy(dtype=float)
                        for column in predictors
                    ],
                ]
            )
            x_test = np.asarray(
                [
                    1.0,
                    float(test["year"]) - 1998.0,
                    *[float(test[column]) for column in predictors],
                ]
            )
            target = train[response].to_numpy(dtype=float)
            coefficients = np.linalg.lstsq(x_train, target, rcond=None)[0]
            fitted = x_train @ coefficients
            scale = float(np.std(target - fitted, ddof=x_train.shape[1]))
            output.loc[index] = (
                float(test[response]) - float(x_test @ coefficients)
            ) / scale
    return output


def build_monthly_table() -> pd.DataFrame:
    base = pd.read_csv(BASE_CSV)
    base["minus_olr_cp_raw_wm2"] = -base["olr_cp_raw_wm2"]
    base["sst_type_raw_c"] = base["nino3_raw_c"] - base["nino4_raw_c"]
    table = base.merge(
        ocean_indices(),
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )
    for addition in (
        load_oisst_gradient(),
        load_precip_gradient(),
        load_slp_gradient(),
        load_tau(),
    ):
        table = table.merge(
            addition,
            on=["year", "month"],
            how="left",
            validate="one_to_one",
        )
    required = [
        "ocean_penetration_z",
        "sst_gradient_e_minus_w_raw_c",
        "precip_gradient_e_minus_w_raw_mmday",
        "slp_drive_w_minus_e_raw_hpa",
        "tau_cwp_raw_nm2",
    ]
    if table[required].isna().any().any():
        missing = table.loc[
            table[required].isna().any(axis=1),
            ["year", "month", *required],
        ]
        raise ValueError(f"Missing monthly inputs:\n{missing}")

    response_models = [
        (
            "conv_intensity_mismatch_z",
            "minus_olr_cp_raw_wm2",
            ["nino34_raw_c"],
        ),
        (
            "conv_pattern_mismatch_z",
            "minus_olr_cp_raw_wm2",
            ["nino34_raw_c", "sst_type_raw_c"],
        ),
        (
            "u850_intensity_mismatch_z",
            "u850_cwp_raw_ms",
            ["nino34_raw_c"],
        ),
        (
            "u850_pattern_mismatch_z",
            "u850_cwp_raw_ms",
            ["nino34_raw_c", "sst_type_raw_c"],
        ),
        (
            "tau_intensity_mismatch_z",
            "tau_cwp_raw_nm2",
            ["nino34_raw_c"],
        ),
        (
            "tau_pattern_mismatch_z",
            "tau_cwp_raw_nm2",
            ["nino34_raw_c", "sst_type_raw_c"],
        ),
        (
            "sst_to_precip_residual_z",
            "precip_gradient_e_minus_w_raw_mmday",
            ["sst_gradient_e_minus_w_raw_c"],
        ),
        (
            "precip_to_slp_residual_z",
            "slp_drive_w_minus_e_raw_hpa",
            ["precip_gradient_e_minus_w_raw_mmday"],
        ),
        (
            "slp_to_tau_residual_z",
            "tau_cwp_raw_nm2",
            ["slp_drive_w_minus_e_raw_hpa"],
        ),
    ]
    for name, response, predictors in response_models:
        table[name] = cross_validated_expected_residual(
            table, response, predictors
        )
    table["coupling_intensity_residual_z"] = table[
        [
            "conv_intensity_mismatch_z",
            "u850_intensity_mismatch_z",
            "tau_intensity_mismatch_z",
        ]
    ].mean(axis=1)
    table["coupling_pattern_residual_z"] = table[
        [
            "conv_pattern_mismatch_z",
            "u850_pattern_mismatch_z",
            "tau_pattern_mismatch_z",
        ]
    ].mean(axis=1)
    return table.sort_values(["year", "month"]).reset_index(drop=True)


def event_group(year: int) -> str:
    if year in CLASSIC_EP:
        return "classic EP"
    if year in CP_EVENTS:
        return "CP"
    if year == 2023:
        return "2023 weak-coupling EP"
    return "other warm"


def build_event_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    chain_columns = [
        "sst_to_precip_residual_z",
        "precip_to_slp_residual_z",
        "slp_to_tau_residual_z",
    ]
    link_names = {
        "sst_to_precip_residual_z": "SST→precipitation",
        "precip_to_slp_residual_z": "precipitation→SLP",
        "slp_to_tau_residual_z": "SLP→wind stress",
    }
    for year in EVENT_YEARS:
        current = monthly.loc[monthly["year"].eq(year)].copy()
        early = current.loc[current["month"].isin([3, 4])]
        late = current.loc[current["month"].isin([5, 6])]
        chain = current.loc[current["month"].between(3, 6), chain_columns].mean()
        weakest = str(chain.idxmin())
        first_persistent = None
        for month in range(1, 6):
            subset = current.loc[
                current["month"].isin([month, month + 1]),
                "coupling_intensity_residual_z",
            ]
            if len(subset) == 2 and subset.lt(-0.75).all():
                first_persistent = month
                break
        target = current.iloc[0]
        rows.append(
            {
                "year": year,
                "group": event_group(year),
                "mature_djf_type_index_c": float(
                    target["mature_djf_type_index_c"]
                ),
                "mature_djf_nino34_c": float(
                    target["mature_djf_nino34_c"]
                ),
                "mar_apr_q20_penetration_z": float(
                    early["q20_penetration_z"].mean()
                ),
                "mar_apr_d20_penetration_z": float(
                    early["d20_penetration_z"].mean()
                ),
                "mar_apr_ocean_penetration_z": float(
                    early["ocean_penetration_z"].mean()
                ),
                "mar_apr_fep_residual_c": float(
                    early["fep_residual_c"].mean()
                ),
                "may_jun_intensity_coupling_residual_z": float(
                    late["coupling_intensity_residual_z"].mean()
                ),
                "may_jun_pattern_coupling_residual_z": float(
                    late["coupling_pattern_residual_z"].mean()
                ),
                "mar_jun_sst_to_precip_residual_z": float(
                    chain["sst_to_precip_residual_z"]
                ),
                "mar_jun_precip_to_slp_residual_z": float(
                    chain["precip_to_slp_residual_z"]
                ),
                "mar_jun_slp_to_tau_residual_z": float(
                    chain["slp_to_tau_residual_z"]
                ),
                "weakest_chain_link": link_names[weakest],
                "weakest_chain_residual_z": float(chain[weakest]),
                "first_two_month_intensity_mismatch_below_minus0p75": (
                    first_persistent
                ),
            }
        )
    return pd.DataFrame(rows)


def permutation_p(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
    repetitions: int = 40_000,
) -> float:
    observed = abs(float(np.corrcoef(x, y)[0, 1]))
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(repetitions):
        exceed += (
            abs(float(np.corrcoef(x, rng.permutation(y))[0, 1]))
            >= observed
        )
    return (exceed + 1.0) / (repetitions + 1.0)


def bootstrap_correlation_ci(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
    repetitions: int = 20_000,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(repetitions):
        index = rng.integers(0, len(x), len(x))
        if np.std(x[index]) == 0 or np.std(y[index]) == 0:
            continue
        values.append(float(np.corrcoef(x[index], y[index])[0, 1]))
    return tuple(np.quantile(values, [0.025, 0.975]))


def benjamini_hochberg(p_values: pd.Series) -> np.ndarray:
    values = p_values.to_numpy(dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.minimum(adjusted, 1.0)
    return output


def correlation_table(event: pd.DataFrame) -> pd.DataFrame:
    variables = [
        "mar_apr_q20_penetration_z",
        "mar_apr_d20_penetration_z",
        "mar_apr_ocean_penetration_z",
        "mar_apr_fep_residual_c",
        "may_jun_intensity_coupling_residual_z",
        "may_jun_pattern_coupling_residual_z",
        "mar_jun_sst_to_precip_residual_z",
        "mar_jun_precip_to_slp_residual_z",
        "mar_jun_slp_to_tau_residual_z",
    ]
    target = event["mature_djf_type_index_c"].to_numpy(dtype=float)
    rows = []
    for index, variable in enumerate(variables):
        value = event[variable].to_numpy(dtype=float)
        ci_low, ci_high = bootstrap_correlation_ci(
            value, target, 71_000 + index
        )
        rows.append(
            {
                "variable": variable,
                "n_events": len(event),
                "pearson_r_with_mature_type": float(
                    np.corrcoef(value, target)[0, 1]
                ),
                "spearman_r_with_mature_type": float(
                    stats.spearmanr(value, target).statistic
                ),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "two_sided_permutation_p": permutation_p(
                    value, target, 72_000 + index
                ),
            }
        )
    output = pd.DataFrame(rows)
    output["bh_fdr_q"] = benjamini_hochberg(
        output["two_sided_permutation_p"]
    )
    return output


def group_summary(event: pd.DataFrame) -> pd.DataFrame:
    variables = [
        "mar_apr_ocean_penetration_z",
        "may_jun_intensity_coupling_residual_z",
        "may_jun_pattern_coupling_residual_z",
        "mar_jun_sst_to_precip_residual_z",
        "mar_jun_precip_to_slp_residual_z",
        "mar_jun_slp_to_tau_residual_z",
    ]
    rows = []
    for name, years in [
        ("classic EP composite", CLASSIC_EP),
        ("CP composite", CP_EVENTS),
        ("2023", [2023]),
    ]:
        subset = event.loc[event["year"].isin(years)]
        row: dict[str, float | int | str] = {
            "group": name,
            "n_events": len(subset),
        }
        for variable in variables:
            row[variable] = float(subset[variable].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def composite_trajectory(
    monthly: pd.DataFrame,
    years: list[int],
) -> pd.DataFrame:
    return (
        monthly.loc[monthly["year"].isin(years)]
        .groupby("month", as_index=False)
        .mean(numeric_only=True)
    )


def make_figure(
    monthly: pd.DataFrame,
    event: pd.DataFrame,
    correlations: pd.DataFrame,
    group: pd.DataFrame,
) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9,
            "pdf.fonttype": 42,
        }
    )
    colors = {
        "1997": "#9E0142",
        "2015": "#D95F0E",
        "2023": "#2C7FB8",
        "CP composite": "#4D4D4D",
    }
    trajectories = {
        "1997": composite_trajectory(monthly, [1997]),
        "2015": composite_trajectory(monthly, [2015]),
        "2023": composite_trajectory(monthly, [2023]),
        "CP composite": composite_trajectory(monthly, CP_EVENTS),
    }

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.2))
    for label, trajectory in trajectories.items():
        axes[0, 0].plot(
            trajectory["month"],
            trajectory["ocean_penetration_z"],
            marker="o",
            lw=1.8,
            color=colors[label],
            label=label,
        )
        axes[0, 1].plot(
            trajectory["month"],
            trajectory["coupling_intensity_residual_z"],
            marker="o",
            lw=1.8,
            color=colors[label],
            label=label,
        )
    axes[0, 0].axhline(0, color="0.55", lw=0.8)
    axes[0, 0].set(
        title="(a) Oceanic eastward penetration and storage",
        xlabel="Calendar month",
        ylabel="Ocean penetration score (z)",
        xticks=MONTHS,
    )
    axes[0, 0].legend(frameon=False, ncol=2, fontsize=8)
    axes[0, 1].axhline(0, color="0.55", lw=0.8)
    axes[0, 1].axhspan(-3, -0.75, color="#DDEBF7", alpha=0.55)
    axes[0, 1].set(
        title="(b) Atmospheric response relative to Niño3.4 amplitude",
        xlabel="Calendar month",
        ylabel="Coupling-response residual (z)",
        xticks=MONTHS,
    )
    axes[0, 1].text(
        1.05,
        -0.93,
        "weaker than historical SST-conditioned response",
        fontsize=7,
        color="#24557A",
    )

    phase = axes[1, 0]
    for label, trajectory in trajectories.items():
        x = trajectory["ocean_penetration_z"].to_numpy()
        y = trajectory["coupling_pattern_residual_z"].to_numpy()
        phase.plot(x, y, marker="o", lw=1.5, color=colors[label], label=label)
        for month, xx, yy in zip(trajectory["month"], x, y):
            phase.annotate(
                str(int(month)),
                (xx, yy),
                xytext=(3, 2),
                textcoords="offset points",
                fontsize=6.5,
                color=colors[label],
            )
        phase.annotate(
            "",
            xy=(x[-1], y[-1]),
            xytext=(x[-2], y[-2]),
            arrowprops=dict(arrowstyle="->", color=colors[label], lw=1.2),
        )
    phase.axhline(0, color="0.6", lw=0.8)
    phase.axvline(0, color="0.6", lw=0.8)
    phase.set(
        title="(c) Ocean pathway versus pattern-adjusted coupling",
        xlabel="Ocean penetration score (z)",
        ylabel="Pattern-adjusted response residual (z)",
    )
    phase.text(
        0.98,
        0.03,
        "Month labels: 1–6",
        transform=phase.transAxes,
        ha="right",
        fontsize=7,
        color="0.35",
    )

    heat_axis = axes[1, 1]
    heat_columns = [
        "mar_jun_sst_to_precip_residual_z",
        "mar_jun_precip_to_slp_residual_z",
        "mar_jun_slp_to_tau_residual_z",
        "may_jun_intensity_coupling_residual_z",
        "may_jun_pattern_coupling_residual_z",
    ]
    heat = group.set_index("group")[heat_columns].to_numpy(dtype=float)
    maximum = max(2.0, float(np.nanmax(np.abs(heat))))
    image = heat_axis.imshow(
        heat,
        cmap="RdBu_r",
        vmin=-maximum,
        vmax=maximum,
        aspect="auto",
    )
    heat_axis.set_xticks(np.arange(len(heat_columns)))
    heat_axis.set_xticklabels(
        [
            "SST→P",
            "P→SLP",
            "SLP→τx",
            "Niño3.4-\nconditioned",
            "pattern-\nconditioned",
        ],
        fontsize=8,
    )
    heat_axis.set_yticks(np.arange(len(group)))
    heat_axis.set_yticklabels(group["group"])
    for row in range(heat.shape[0]):
        for column in range(heat.shape[1]):
            heat_axis.text(
                column,
                row,
                f"{heat[row, column]:+.2f}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if abs(heat[row, column]) > 0.75 * maximum else "0.1",
            )
    heat_axis.set_title("(d) Where does the coupling chain first weaken?")
    colorbar = fig.colorbar(image, ax=heat_axis, shrink=0.83, pad=0.03)
    colorbar.set_label("Observed minus historical expectation (z)")

    for axis in axes.flat[:3]:
        axis.grid(color="0.9", lw=0.7)
    fig.suptitle(
        "ENSO type formation and air–sea coupling are distinct dimensions",
        fontsize=14,
        fontweight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.012,
        "Ocean score contrasts 140W with the dateline/170W; atmospheric "
        "residuals are leave-one-year-out relative to 1982–2014 calendar-month "
        "relationships. Negative values indicate weaker response than expected.",
        ha="center",
        fontsize=7.5,
        color="0.32",
    )
    fig.tight_layout(rect=[0.02, 0.04, 0.99, 0.96])

    fig2, axes2 = plt.subplots(1, 2, figsize=(11.4, 4.4))
    scatter = axes2[0]
    event_plot = event.copy()
    points = scatter.scatter(
        event_plot["mar_apr_ocean_penetration_z"],
        event_plot["mature_djf_type_index_c"],
        c=event_plot["may_jun_intensity_coupling_residual_z"],
        cmap="RdBu_r",
        vmin=-2.0,
        vmax=2.0,
        s=55,
        edgecolor="white",
        linewidth=0.7,
    )
    for _, point in event_plot.iterrows():
        scatter.annotate(
            str(int(point["year"])),
            (
                point["mar_apr_ocean_penetration_z"],
                point["mature_djf_type_index_c"],
            ),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7,
        )
    scatter.axhline(0, color="0.6", lw=0.8)
    scatter.axvline(0, color="0.6", lw=0.8)
    scatter.set(
        title="(e) Ocean penetration is linked to mature EP–CP type",
        xlabel="Mar–Apr ocean penetration score (z)",
        ylabel="Mature DJF Niño3−Niño4 (°C)",
    )
    selected = correlations.loc[
        correlations["variable"].eq("mar_apr_ocean_penetration_z")
    ].iloc[0]
    scatter.text(
        0.03,
        0.96,
        f"r={selected.pearson_r_with_mature_type:+.2f}, "
        f"q={selected.bh_fdr_q:.3f}",
        transform=scatter.transAxes,
        va="top",
        fontsize=8,
    )
    cb = fig2.colorbar(points, ax=scatter, pad=0.02)
    cb.set_label("May–Jun Niño3.4-conditioned response residual (z)")

    mismatch = axes2[1]
    mismatch.scatter(
        event_plot["may_jun_intensity_coupling_residual_z"],
        event_plot["may_jun_pattern_coupling_residual_z"],
        s=50,
        color="#6A51A3",
        edgecolor="white",
        linewidth=0.7,
    )
    for _, point in event_plot.iterrows():
        mismatch.annotate(
            str(int(point["year"])),
            (
                point["may_jun_intensity_coupling_residual_z"],
                point["may_jun_pattern_coupling_residual_z"],
            ),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7,
        )
    limits = [
        min(
            mismatch.get_xlim()[0],
            mismatch.get_ylim()[0],
        ),
        max(
            mismatch.get_xlim()[1],
            mismatch.get_ylim()[1],
        ),
    ]
    mismatch.plot(limits, limits, color="0.45", lw=0.9, ls="--")
    mismatch.axhline(0, color="0.75", lw=0.7)
    mismatch.axvline(0, color="0.75", lw=0.7)
    mismatch.set(
        title="(f) How much mismatch is explained by SST pattern?",
        xlabel="Residual conditioned on Niño3.4 amplitude (z)",
        ylabel="Residual after adding EP–CP SST pattern (z)",
    )
    mismatch.text(
        0.03,
        0.97,
        "Below/above diagonal: pattern makes response\nlook weaker/stronger",
        transform=mismatch.transAxes,
        va="top",
        fontsize=7.5,
        color="0.35",
    )
    for axis in axes2:
        axis.grid(color="0.9", lw=0.7)
    fig2.tight_layout()

    OUT.mkdir(parents=True, exist_ok=True)
    PDF.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(PDF) as pages:
        pages.savefig(fig, dpi=300, bbox_inches="tight")
        pages.savefig(fig2, dpi=300, bbox_inches="tight")
    fig.savefig(PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)
    plt.close(fig2)


def make_report(
    event: pd.DataFrame,
    correlations: pd.DataFrame,
    group: pd.DataFrame,
) -> None:
    lookup = correlations.set_index("variable")
    ocean = lookup.loc["mar_apr_ocean_penetration_z"]
    q20 = lookup.loc["mar_apr_q20_penetration_z"]
    d20 = lookup.loc["mar_apr_d20_penetration_z"]
    fep = lookup.loc["mar_apr_fep_residual_c"]
    e2023 = event.loc[event["year"].eq(2023)].iloc[0]
    g = group.set_index("group")
    classic = g.loc["classic EP composite"]
    cp = g.loc["CP composite"]
    y2023 = g.loc["2023"]
    persistent_value = (
        "未出现"
        if pd.isna(
            e2023.first_two_month_intensity_mismatch_below_minus0p75
        )
        else (
            f"{int(e2023.first_two_month_intensity_mismatch_below_minus0p75)}月"
        )
    )
    text = f"""# ENSO类型形成与海气耦合效率：阶段结果

## 研究问题

本阶段停止把TSI作为“厄尔尼诺预测器”优化，改为回答：

1. 暖水和热跃层异常在什么位置发生EP/CP分叉？
2. 同样的SST强度为什么会产生不同的对流、气压和风响应？
3. CP是否等于海气脱耦，2023又在哪一环偏离经典EP？

成熟类型仍用去趋势DJF `Niño3−Niño4` 连续指标；所有统计只解释暖
事件类型，不预测事件是否发生。

## 两个独立坐标

### 海洋向东穿透—储存

- `Q penetration = [z(Q20_140W) − z(Q20_dateline)] / sqrt(2)`
- `D20 penetration = [z(D20_140W) − z(D20_170W)] / sqrt(2)`
- `Ocean penetration = mean(Q penetration, D20 penetration)`

正值表示异常更偏向140°W，而不是停在日界线—170°W。3—4月事件
统计中：

- Q20穿透与成熟类型：r={q20.pearson_r_with_mature_type:+.3f}，
  95% CI [{q20.bootstrap_ci_low:+.3f}, {q20.bootstrap_ci_high:+.3f}]，
  q={q20.bh_fdr_q:.3f}。
- D20穿透与成熟类型：r={d20.pearson_r_with_mature_type:+.3f}，
  95% CI [{d20.bootstrap_ci_low:+.3f}, {d20.bootstrap_ci_high:+.3f}]，
  q={d20.bh_fdr_q:.3f}。
- 联合海洋穿透与成熟类型：r={ocean.pearson_r_with_mature_type:+.3f}，
  95% CI [{ocean.bootstrap_ci_low:+.3f}, {ocean.bootstrap_ci_high:+.3f}]，
  q={ocean.bh_fdr_q:.3f}。
- FEP残差与类型：r={fep.pearson_r_with_mature_type:+.3f}，
  q={fep.bh_fdr_q:.3f}。

这部分不再把140°W当作固定硬阈值，而是用相对于日界线/170°W的
穿透程度描述“停在中部”还是“继续进入东部”。

### 海气响应残差

对每个日历月，以1982—2014为历史基准，并对基准期内年份做留一年：

`atmospheric mismatch = observed response − historical SST-conditioned response`

分别建立两种期望：

1. 只给Niño3.4幅度，回答“相同总体暖度通常产生多大响应”；
2. 再加入Niño3−Niño4空间型态，回答“考虑EP/CP位置后是否仍异常”。

响应同时使用CP对流（−OLR）、中西太平洋U850和表面纬向风应力。
负残差表示大气响应弱于历史预期。它是连续耦合效率，不是二元
“耦合/脱耦”标签。

## 经典EP、CP和2023

- 经典EP复合3—4月海洋穿透为
  {classic.mar_apr_ocean_penetration_z:+.2f} z；CP复合为
  {cp.mar_apr_ocean_penetration_z:+.2f} z；2023为
  {y2023.mar_apr_ocean_penetration_z:+.2f} z。
- 经典EP 5—6月Niño3.4幅度条件下的大气响应残差为
  {classic.may_jun_intensity_coupling_residual_z:+.2f} z；CP为
  {cp.may_jun_intensity_coupling_residual_z:+.2f} z；2023为
  {y2023.may_jun_intensity_coupling_residual_z:+.2f} z。
- 加入SST空间型态后，2023残差为
  {y2023.may_jun_pattern_coupling_residual_z:+.2f} z。

因此CP不应自动称为脱耦：如果中部SST型态本来就只预期中部响应，
较弱的东部风并非异常。真正的脱耦是控制SST幅度和空间型态以后，
对流/风仍显著弱于历史关系。

## 反馈链在哪里先失配

使用逐月、留一年历史关系分别计算：

- SST梯度→降水梯度残差；
- 降水梯度→SLP梯度残差；
- SLP梯度→纬向风应力残差。

2023年3—6月最弱环节是
**{e2023.weakest_chain_link}**，
平均残差{e2023.weakest_chain_residual_z:+.2f} z。
第一次连续两个月低于−0.75 z的总体响应起始月为
**{persistent_value}**。

链式残差用于定位“失配最先出现在哪一环”，不等于因果实验。尤其
降水、SLP和风同时受印度洋、大西洋、背景SST趋势及天气尺度噪声影响。

## 当前能否作结

可以作结的主线是：

> EP/CP首先是海洋异常向东穿透和储存位置的差异；海气耦合效率是
> 另一维度。经典EP同时具有较强东部穿透和正常/增强反馈，CP的耦合
> 中心偏中部而不必脱耦；2023则需要检查在控制其SST空间型态后，
> 对流—气压—风链是否仍显著偏弱。

不能把相关当作固定140°W阈值，也不能把所有CP归为弱耦合。2023的
残差诊断还需要用GPCP/CPC OLR或另一套风产品复核。

## 文件

- 月度诊断：`{MONTHLY_CSV.relative_to(ROOT)}`
- 事件汇总：`{EVENT_CSV.relative_to(ROOT)}`
- 相关与FDR：`{CORRELATION_CSV.relative_to(ROOT)}`
- 组别复合：`{GROUP_CSV.relative_to(ROOT)}`
- 图：`{PDF.relative_to(ROOT)}`
"""
    REPORT.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    monthly = build_monthly_table()
    event = build_event_summary(monthly)
    correlations = correlation_table(event)
    group = group_summary(event)
    monthly.to_csv(MONTHLY_CSV, index=False)
    event.to_csv(EVENT_CSV, index=False)
    correlations.to_csv(CORRELATION_CSV, index=False)
    group.to_csv(GROUP_CSV, index=False)
    diagnostics = {
        "purpose": "ENSO type formation and coupling efficiency, not onset prediction",
        "historical_expectation_period": "1982-2014",
        "atmospheric_residual_validation": (
            "calendar-month leave-one-year-out within baseline; "
            "fixed baseline for post-2014"
        ),
        "event_years": EVENT_YEARS,
        "classic_ep": CLASSIC_EP,
        "cp_events": CP_EVENTS,
        "year_2023": event.loc[event["year"].eq(2023)].iloc[0].to_dict(),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    make_figure(monthly, event, correlations, group)
    make_report(event, correlations, group)
    print(correlations.to_string(index=False))
    print()
    print(group.to_string(index=False))
    print()
    print(event.loc[event["year"].isin([1997, 2015, 2023])].to_string(index=False))
    print(f"\n{REPORT}\n{PDF}")


if __name__ == "__main__":
    main()
