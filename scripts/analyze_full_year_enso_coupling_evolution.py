#!/usr/bin/env python3
"""Full-year ENSO coupling evolution using OISST, GPCP and ERA5.

This extends the January-June mechanism analysis through the mature season
and distinguishes an SST-amplitude mismatch from a residual mismatch after
the EP-CP SST pattern is included.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_full_coupling_cache")
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
import sys

sys.path.insert(0, str(ROOT / "scripts"))
from analyze_enso_type_coupling_efficiency import (  # noqa: E402
    BASELINE_END,
    CLASSIC_EP,
    CP_EVENTS,
    EVENT_YEARS,
    GATE_CSV,
    BUDGET_CSV,
    ERA5_COUPLING,
    ERA5_SINGLE,
    cross_validated_expected_residual,
    permutation_p,
    bootstrap_correlation_ci,
    benjamini_hochberg,
    normalize_field,
    weighted_box,
    to_frame,
)


DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/type_coupling"
PDF = ROOT / "output/pdf/enso_full_year_coupling_evolution.pdf"
PNG = OUT / "enso_full_year_coupling_evolution.png"
REPORT = OUT / "ENSO_FULL_YEAR_COUPLING_EVOLUTION_CN.md"
MONTHLY_CSV = DERIVED / "enso_full_year_coupling_monthly_1982_2024.csv"
SEASONAL_CSV = DERIVED / "enso_full_year_coupling_event_seasonal.csv"
ALL_YEAR_SEASONAL_CSV = (
    DERIVED / "enso_full_year_coupling_all_year_seasonal_1982_2023.csv"
)
OCEAN_CSV = DERIVED / "enso_type_east_ocean_state_event_summary.csv"
OCEAN_STATS_CSV = (
    DERIVED / "enso_type_east_ocean_state_correlations.csv"
)
DIAGNOSTICS_JSON = DERIVED / "enso_full_year_coupling_diagnostics.json"

OISST_DIR = ROOT / "data/interim/research_2026/pmm_inputs"
GPCP_NC = (
    ROOT
    / "data/interim/research_2026/"
    "gpcp_event_spatial_tropics_1982_202605.nc"
)
NCEP_CSV = ROOT / "data/interim/raw_validation/ncep_atmosphere_monthly.csv"

MONTH_TAGS = {
    1: "jan",
    2: "feb",
    3: "mar",
    4: "apr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "aug",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dec",
}
SEASONS = {
    "AMJ": [(0, 4), (0, 5), (0, 6)],
    "JJA": [(0, 6), (0, 7), (0, 8)],
    "SON": [(0, 9), (0, 10), (0, 11)],
    "DJF": [(0, 12), (1, 1), (1, 2)],
}


def load_oisst_indices() -> pd.DataFrame:
    frames = []
    for month, tag in MONTH_TAGS.items():
        path = OISST_DIR / f"oisst_sst_pmm_1deg_{tag}_1982_2025.nc"
        if not path.exists():
            path = OISST_DIR / f"oisst_sst_pmm_1deg_{tag}_1982_2026.nc"
        with xr.open_dataset(path, engine="scipy") as dataset:
            field = dataset["sst"].sel(
                time=slice(f"1982-{month:02d}-01", f"2024-{month:02d}-28")
            ).load()
        boxes = {
            "nino3_raw_c": (210.0, 270.0),
            "nino4_raw_c": (160.0, 210.0),
            "nino34_raw_c": (190.0, 240.0),
            "fep_raw_c": (270.0, 280.0),
            "sst_west_raw_c": (130.0, 160.0),
            "sst_east_raw_c": (220.0, 250.0),
        }
        current = None
        for name, (lon0, lon1) in boxes.items():
            index = weighted_box(field, lon0, lon1)
            if current is None:
                current = to_frame(index, name)
            else:
                current[name] = np.asarray(index.values, dtype=float)
        frames.append(current)
    output = pd.concat(frames, ignore_index=True)
    output["sst_type_raw_c"] = (
        output["nino3_raw_c"] - output["nino4_raw_c"]
    )
    output["sst_gradient_e_minus_w_raw_c"] = (
        output["sst_east_raw_c"] - output["sst_west_raw_c"]
    )
    return output.sort_values(["year", "month"])


def load_gpcp_indices() -> pd.DataFrame:
    with xr.open_dataset(GPCP_NC, engine="netcdf4") as dataset:
        field = normalize_field(dataset["precip"]).sel(
            time=slice("1982-01-01", "2024-12-31")
        )
        west = weighted_box(field, 130.0, 160.0).load()
        central = weighted_box(field, 180.0, 220.0).load()
        east = weighted_box(field, 220.0, 250.0).load()
        tropical = weighted_box(field, 180.0, 250.0).load()
    output = to_frame(west, "precip_west_raw_mmday")
    output["precip_central_raw_mmday"] = np.asarray(
        central.values, dtype=float
    )
    output["precip_east_raw_mmday"] = np.asarray(east.values, dtype=float)
    output["precip_tropical_pacific_raw_mmday"] = np.asarray(
        tropical.values, dtype=float
    )
    output["precip_gradient_e_minus_w_raw_mmday"] = (
        output["precip_east_raw_mmday"]
        - output["precip_west_raw_mmday"]
    )
    return output


def load_slp_indices() -> pd.DataFrame:
    with xr.open_dataset(ERA5_SINGLE, engine="netcdf4") as dataset:
        field = normalize_field(dataset["msl"]).sel(
            time=slice("1982-01-01", "2024-12-31")
        ) / 100.0
        west = weighted_box(field, 130.0, 160.0).load()
        east = weighted_box(field, 220.0, 250.0).load()
    output = to_frame(west, "slp_west_raw_hpa")
    output["slp_east_raw_hpa"] = np.asarray(east.values, dtype=float)
    output["slp_drive_w_minus_e_raw_hpa"] = (
        output["slp_west_raw_hpa"] - output["slp_east_raw_hpa"]
    )
    return output


def load_tau_indices() -> pd.DataFrame:
    frames = []
    for month in range(1, 13):
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
        index = weighted_box(field, 160.0, 220.0)
        current = to_frame(index, "tau_cwp_raw_nm2")
        frames.append(current.loc[current["year"].between(1982, 2024)])
    return pd.concat(frames, ignore_index=True).sort_values(["year", "month"])


def load_ncep_indices() -> pd.DataFrame:
    output = pd.read_csv(NCEP_CSV)
    output = output.loc[output["year"].between(1982, 2024)].copy()
    output["minus_soi_like_ncep"] = (
        -output["soi_like_tahiti_minus_darwin"]
    )
    return output


def build_monthly() -> pd.DataFrame:
    table = load_oisst_indices()
    for addition in (
        load_gpcp_indices(),
        load_slp_indices(),
        load_tau_indices(),
        load_ncep_indices(),
    ):
        table = table.merge(
            addition,
            on=["year", "month"],
            how="inner",
            validate="one_to_one",
        )
    expected = (2024 - 1982 + 1) * 12
    if len(table) != expected:
        raise ValueError(f"Expected {expected} monthly rows, got {len(table)}")

    models = [
        (
            "precip_intensity_residual_z",
            "precip_tropical_pacific_raw_mmday",
            ["nino34_raw_c"],
        ),
        (
            "precip_pattern_residual_z",
            "precip_tropical_pacific_raw_mmday",
            ["nino34_raw_c", "sst_type_raw_c"],
        ),
        (
            "slp_intensity_residual_z",
            "slp_drive_w_minus_e_raw_hpa",
            ["nino34_raw_c"],
        ),
        (
            "slp_pattern_residual_z",
            "slp_drive_w_minus_e_raw_hpa",
            ["nino34_raw_c", "sst_type_raw_c"],
        ),
        (
            "tau_intensity_residual_z",
            "tau_cwp_raw_nm2",
            ["nino34_raw_c"],
        ),
        (
            "tau_pattern_residual_z",
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
        (
            "ncep_u_intensity_residual_z",
            "cwp_u_sig995",
            ["nino34_raw_c"],
        ),
        (
            "ncep_u_pattern_residual_z",
            "cwp_u_sig995",
            ["nino34_raw_c", "sst_type_raw_c"],
        ),
        (
            "ncep_soi_intensity_residual_z",
            "minus_soi_like_ncep",
            ["nino34_raw_c"],
        ),
        (
            "ncep_soi_pattern_residual_z",
            "minus_soi_like_ncep",
            ["nino34_raw_c", "sst_type_raw_c"],
        ),
    ]
    for name, response, predictors in models:
        table[name] = cross_validated_expected_residual(
            table, response, predictors
        )
    table["coupling_intensity_residual_z"] = table[
        [
            "precip_intensity_residual_z",
            "slp_intensity_residual_z",
            "tau_intensity_residual_z",
        ]
    ].mean(axis=1)
    table["coupling_pattern_residual_z"] = table[
        [
            "precip_pattern_residual_z",
            "slp_pattern_residual_z",
            "tau_pattern_residual_z",
        ]
    ].mean(axis=1)
    table["ncep_coupling_intensity_residual_z"] = table[
        [
            "ncep_u_intensity_residual_z",
            "ncep_soi_intensity_residual_z",
        ]
    ].mean(axis=1)
    table["ncep_coupling_pattern_residual_z"] = table[
        [
            "ncep_u_pattern_residual_z",
            "ncep_soi_pattern_residual_z",
        ]
    ].mean(axis=1)
    return table


def season_subset(
    monthly: pd.DataFrame,
    event_year: int,
    season: str,
) -> pd.DataFrame:
    parts = SEASONS[season]
    mask = np.zeros(len(monthly), dtype=bool)
    for offset, month in parts:
        mask |= monthly["year"].eq(event_year + offset) & monthly[
            "month"
        ].eq(month)
    return monthly.loc[mask]


def build_seasonal(monthly: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "nino34_raw_c",
        "sst_type_raw_c",
        "precip_tropical_pacific_raw_mmday",
        "slp_drive_w_minus_e_raw_hpa",
        "tau_cwp_raw_nm2",
        "precip_intensity_residual_z",
        "precip_pattern_residual_z",
        "slp_intensity_residual_z",
        "slp_pattern_residual_z",
        "tau_intensity_residual_z",
        "tau_pattern_residual_z",
        "coupling_intensity_residual_z",
        "coupling_pattern_residual_z",
        "sst_to_precip_residual_z",
        "precip_to_slp_residual_z",
        "slp_to_tau_residual_z",
        "ncep_u_intensity_residual_z",
        "ncep_u_pattern_residual_z",
        "ncep_soi_intensity_residual_z",
        "ncep_soi_pattern_residual_z",
        "ncep_coupling_intensity_residual_z",
        "ncep_coupling_pattern_residual_z",
    ]
    rows = []
    for year in EVENT_YEARS:
        for season in SEASONS:
            subset = season_subset(monthly, year, season)
            if len(subset) != 3:
                raise ValueError(f"Incomplete {season} for {year}")
            row: dict[str, float | int | str] = {
                "year": year,
                "season": season,
                "group": (
                    "classic EP"
                    if year in CLASSIC_EP
                    else "CP"
                    if year in CP_EVENTS
                    else "2023 weak-coupling EP"
                    if year == 2023
                    else "other warm"
                ),
            }
            for column in columns:
                row[column] = float(subset[column].mean())
            rows.append(row)
    return pd.DataFrame(rows)


def build_all_year_seasonal(monthly: pd.DataFrame) -> pd.DataFrame:
    """Seasonal coupling residuals for every 1982–2023 start year."""
    columns = [
        "coupling_intensity_residual_z",
        "coupling_pattern_residual_z",
        "precip_pattern_residual_z",
        "slp_pattern_residual_z",
        "tau_pattern_residual_z",
        "sst_to_precip_residual_z",
        "precip_to_slp_residual_z",
        "slp_to_tau_residual_z",
        "ncep_u_pattern_residual_z",
        "ncep_soi_pattern_residual_z",
        "ncep_coupling_pattern_residual_z",
    ]
    rows = []
    for year in range(1982, 2024):
        for season in SEASONS:
            subset = season_subset(monthly, year, season)
            if len(subset) != 3:
                raise ValueError(f"Incomplete all-year {season} for {year}")
            row: dict[str, float | int | str] = {
                "year": year,
                "season": season,
            }
            for column in columns:
                row[column] = float(subset[column].mean())
            rows.append(row)
    output = pd.DataFrame(rows)
    for column in columns:
        output[f"{column}_lower_rank"] = output.groupby("season")[
            column
        ].rank(method="min", ascending=True)
        output[f"{column}_lower_percentile"] = (
            output[f"{column}_lower_rank"]
            / output.groupby("season")[column].transform("count")
        )
    return output


def month_standardize(frame: pd.DataFrame, value: str) -> pd.Series:
    output = pd.Series(np.nan, index=frame.index, dtype=float)
    for month, group in frame.groupby("month"):
        mean = float(group[value].mean())
        scale = float(group[value].std(ddof=1))
        output.loc[group.index] = (group[value] - mean) / scale
    return output


def build_ocean_summary() -> pd.DataFrame:
    budget = pd.read_csv(BUDGET_CSV)
    budget["q140_z"] = month_standardize(
        budget, "q20_220e_pw_anom"
    )
    gate = pd.read_csv(GATE_CSV)
    east = gate.loc[np.isclose(gate["longitude_e"], 220.0)].copy()
    east["d140_z"] = month_standardize(east, "d20_m_anom")
    ocean = budget[
        ["year", "month", "q20_220e_pw_anom", "q140_z"]
    ].merge(
        east[["year", "month", "d20_m_anom", "d140_z"]],
        on=["year", "month"],
        validate="one_to_one",
    )
    rows = []
    target = pd.read_csv(
        DERIVED / "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
    )
    target = target.loc[
        target["month"].eq(4),
        ["year", "mature_djf_type_index_c", "mature_djf_nino34_c"],
    ]
    for year in EVENT_YEARS:
        current = ocean.loc[
            ocean["year"].eq(year) & ocean["month"].isin([3, 4])
        ]
        row = {
            "year": year,
            "q140_mar_apr_z": float(current["q140_z"].mean()),
            "d140_mar_apr_z": float(current["d140_z"].mean()),
            "east_ocean_state_z": float(
                (
                    current["q140_z"].mean()
                    + current["d140_z"].mean()
                )
                / 2.0
            ),
        }
        rows.append(row)
    output = pd.DataFrame(rows).merge(
        target, on="year", validate="one_to_one"
    )
    return output


def build_ocean_statistics(ocean: pd.DataFrame) -> pd.DataFrame:
    target = ocean["mature_djf_type_index_c"].to_numpy(dtype=float)
    variables = [
        "q140_mar_apr_z",
        "d140_mar_apr_z",
        "east_ocean_state_z",
    ]
    rows = []
    for index, variable in enumerate(variables):
        values = ocean[variable].to_numpy(dtype=float)
        ci_low, ci_high = bootstrap_correlation_ci(
            values, target, 88_100 + index
        )
        leave_one_out = []
        for left_out in ocean["year"]:
            keep = ocean["year"].ne(left_out)
            leave_one_out.append(
                (
                    int(left_out),
                    float(
                        np.corrcoef(
                            ocean.loc[keep, variable],
                            ocean.loc[keep, "mature_djf_type_index_c"],
                        )[0, 1]
                    ),
                )
            )
        non_extreme = ocean.loc[~ocean["year"].isin(CLASSIC_EP)]
        non_extreme_values = non_extreme[variable].to_numpy(dtype=float)
        non_extreme_target = non_extreme[
            "mature_djf_type_index_c"
        ].to_numpy(dtype=float)
        rows.append(
            {
                "variable": variable,
                "n_events": len(values),
                "pearson_r_with_mature_type": float(
                    np.corrcoef(values, target)[0, 1]
                ),
                "spearman_r_with_mature_type": float(
                    stats.spearmanr(values, target).statistic
                ),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "two_sided_permutation_p": permutation_p(
                    values, target, 88_200 + index
                ),
                "leave_one_out_min_r": min(
                    value for _, value in leave_one_out
                ),
                "leave_one_out_min_excluded_year": min(
                    leave_one_out, key=lambda item: item[1]
                )[0],
                "leave_one_out_max_r": max(
                    value for _, value in leave_one_out
                ),
                "non_classic_ep_n": len(non_extreme),
                "non_classic_ep_r": float(
                    np.corrcoef(
                        non_extreme_values, non_extreme_target
                    )[0, 1]
                ),
                "non_classic_ep_permutation_p": permutation_p(
                    non_extreme_values,
                    non_extreme_target,
                    88_300 + index,
                ),
            }
        )
    output = pd.DataFrame(rows)
    output["bh_fdr_q"] = benjamini_hochberg(
        output["two_sided_permutation_p"]
    )
    return output


def group_seasonal(seasonal: pd.DataFrame) -> pd.DataFrame:
    selected = seasonal.loc[
        seasonal["group"].isin(
            ["classic EP", "CP", "2023 weak-coupling EP"]
        )
    ].copy()
    selected["display_group"] = selected["group"].replace(
        {
            "classic EP": "classic EP composite",
            "CP": "CP composite",
            "2023 weak-coupling EP": "2023",
        }
    )
    return (
        selected.groupby(["display_group", "season"], as_index=False)
        .mean(numeric_only=True)
    )


def make_figure(
    seasonal: pd.DataFrame,
    ocean: pd.DataFrame,
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
    group = group_seasonal(seasonal)
    colors = {
        "classic EP composite": "#B2182B",
        "CP composite": "#4D4D4D",
        "2023": "#2166AC",
    }
    order = list(SEASONS)
    x = np.arange(len(order))
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.0))
    for name in colors:
        current = (
            group.loc[group["display_group"].eq(name)]
            .set_index("season")
            .reindex(order)
        )
        axes[0, 0].plot(
            x,
            current["coupling_intensity_residual_z"],
            marker="o",
            lw=1.9,
            color=colors[name],
            label=name,
        )
        axes[0, 1].plot(
            x,
            current["coupling_pattern_residual_z"],
            marker="o",
            lw=1.9,
            color=colors[name],
            label=name,
        )
    for axis in axes[0, :]:
        axis.axhline(0, color="0.55", lw=0.8)
        axis.axhspan(-3.5, -0.75, color="#DDEBF7", alpha=0.5)
        axis.set_xticks(x, order)
        axis.set_ylabel("Observed minus expected response (z)")
        axis.grid(color="0.9", lw=0.7)
    axes[0, 0].set_title(
        "(a) Response expected from Niño3.4 amplitude alone"
    )
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 1].set_title(
        "(b) Residual after adding the EP–CP SST pattern"
    )

    chain_axis = axes[1, 0]
    y2023 = (
        seasonal.loc[seasonal["year"].eq(2023)]
        .set_index("season")
        .reindex(order)
    )
    chain_columns = [
        "sst_to_precip_residual_z",
        "precip_to_slp_residual_z",
        "slp_to_tau_residual_z",
    ]
    chain = y2023[chain_columns].to_numpy(dtype=float).T
    maximum = max(2.0, float(np.nanmax(np.abs(chain))))
    image = chain_axis.imshow(
        chain,
        cmap="RdBu_r",
        vmin=-maximum,
        vmax=maximum,
        aspect="auto",
    )
    chain_axis.set_xticks(np.arange(len(order)), order)
    chain_axis.set_yticks(
        np.arange(3),
        ["SST→precipitation", "precipitation→SLP", "SLP→wind stress"],
    )
    for row in range(chain.shape[0]):
        for column in range(chain.shape[1]):
            chain_axis.text(
                column,
                row,
                f"{chain[row, column]:+.2f}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if abs(chain[row, column]) > 0.75 * maximum else "0.1",
            )
    chain_axis.set_title("(c) 2023: seasonal location of the chain mismatch")
    cb = fig.colorbar(image, ax=chain_axis, shrink=0.85, pad=0.03)
    cb.set_label("Link residual (z)")

    ocean_axis = axes[1, 1]
    scatter = ocean_axis.scatter(
        ocean["q140_mar_apr_z"],
        ocean["d140_mar_apr_z"],
        c=ocean["mature_djf_type_index_c"],
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=2.0,
        s=58,
        edgecolor="white",
        linewidth=0.7,
    )
    for _, point in ocean.iterrows():
        ocean_axis.annotate(
            str(int(point["year"])),
            (point["q140_mar_apr_z"], point["d140_mar_apr_z"]),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7,
        )
    ocean_axis.axhline(0, color="0.65", lw=0.8)
    ocean_axis.axvline(0, color="0.65", lw=0.8)
    ocean_axis.set(
        title="(d) Keep delivery and storage separate",
        xlabel="Mar–Apr Q20 at 140W (z)",
        ylabel="Mar–Apr D20 at 140W (z)",
    )
    ocean_axis.grid(color="0.9", lw=0.7)
    cb2 = fig.colorbar(scatter, ax=ocean_axis, shrink=0.85, pad=0.03)
    cb2.set_label("Mature DJF Niño3−Niño4 (°C)")

    fig.suptitle(
        "Full-year evolution separates ENSO type formation from coupling efficiency",
        fontsize=14,
        fontweight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.012,
        "Atmospheric responses combine GPCP tropical-Pacific precipitation, "
        "ERA5 west-minus-east SLP and ERA5 central-western Pacific zonal "
        "wind stress. Historical expectations use 1982–2014 calendar-month "
        "leave-one-year-out fits.",
        ha="center",
        fontsize=7.5,
        color="0.33",
    )
    fig.tight_layout(rect=[0.02, 0.04, 0.99, 0.96])

    fig2, axes2 = plt.subplots(1, 3, figsize=(11.2, 3.8), sharey=True)
    variables = [
        ("precip_pattern_residual_z", "Precipitation"),
        ("slp_pattern_residual_z", "SLP gradient"),
        ("tau_pattern_residual_z", "Wind stress"),
    ]
    for axis, (variable, title) in zip(axes2, variables):
        for name in colors:
            current = (
                group.loc[group["display_group"].eq(name)]
                .set_index("season")
                .reindex(order)
            )
            axis.plot(
                x,
                current[variable],
                marker="o",
                lw=1.7,
                color=colors[name],
                label=name,
            )
        axis.axhline(0, color="0.55", lw=0.8)
        axis.axhspan(-4, -0.75, color="#DDEBF7", alpha=0.5)
        axis.set_xticks(x, order)
        axis.set_title(title)
        axis.grid(color="0.9", lw=0.7)
    axes2[0].set_ylabel("Pattern-adjusted residual (z)")
    axes2[-1].legend(frameon=False, fontsize=7.5)
    fig2.suptitle(
        "Which atmospheric component remains anomalous after SST pattern adjustment?",
        fontsize=12,
        fontweight="bold",
    )
    fig2.tight_layout()

    fig3, axes3 = plt.subplots(1, 2, figsize=(9.2, 3.8), sharey=True)
    independent_variables = [
        ("ncep_u_pattern_residual_z", "NCEP central-Pacific zonal wind"),
        ("ncep_soi_pattern_residual_z", "NCEP Tahiti−Darwin pressure index"),
    ]
    for axis, (variable, title) in zip(axes3, independent_variables):
        for name in colors:
            current = (
                group.loc[group["display_group"].eq(name)]
                .set_index("season")
                .reindex(order)
            )
            axis.plot(
                x,
                current[variable],
                marker="o",
                lw=1.7,
                color=colors[name],
                label=name,
            )
        axis.axhline(0, color="0.55", lw=0.8)
        axis.axhspan(-4, -0.75, color="#DDEBF7", alpha=0.5)
        axis.set_xticks(x, order)
        axis.set_title(title)
        axis.grid(color="0.9", lw=0.7)
    axes3[0].set_ylabel("Pattern-adjusted residual (z)")
    axes3[1].legend(frameon=False, fontsize=7.5)
    fig3.suptitle(
        "Independent NCEP checkpoint of the coupling mismatch",
        fontsize=12,
        fontweight="bold",
    )
    fig3.tight_layout()

    OUT.mkdir(parents=True, exist_ok=True)
    PDF.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(PDF) as pages:
        pages.savefig(fig, dpi=300, bbox_inches="tight")
        pages.savefig(fig2, dpi=300, bbox_inches="tight")
        pages.savefig(fig3, dpi=300, bbox_inches="tight")
    fig.savefig(PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)
    plt.close(fig2)
    plt.close(fig3)


def make_report(
    seasonal: pd.DataFrame,
    ocean: pd.DataFrame,
    all_year_seasonal: pd.DataFrame,
    ocean_statistics: pd.DataFrame,
) -> None:
    group = group_seasonal(seasonal)

    def value(name: str, season: str, variable: str) -> float:
        return float(
            group.loc[
                group["display_group"].eq(name)
                & group["season"].eq(season),
                variable,
            ].iloc[0]
        )

    ocean_lookup = ocean_statistics.set_index("variable")
    q_stats = ocean_lookup.loc["q140_mar_apr_z"]
    d_stats = ocean_lookup.loc["d140_mar_apr_z"]
    joint_stats = ocean_lookup.loc["east_ocean_state_z"]
    lines = []
    for season in SEASONS:
        intensity = value(
            "2023", season, "coupling_intensity_residual_z"
        )
        pattern = value(
            "2023", season, "coupling_pattern_residual_z"
        )
        lines.append(
            f"- {season}：Niño3.4幅度条件残差{intensity:+.2f} z；"
            f"加入EP–CP空间型态后{pattern:+.2f} z。"
        )
    ncep_lines = []
    for season in SEASONS:
        ncep_lines.append(
            f"- {season}：NCEP风残差"
            f"{value('2023', season, 'ncep_u_pattern_residual_z'):+.2f} z，"
            f"NCEP压力响应残差"
            f"{value('2023', season, 'ncep_soi_pattern_residual_z'):+.2f} z。"
        )
    y2023 = seasonal.loc[seasonal["year"].eq(2023)].copy()
    link_columns = [
        "sst_to_precip_residual_z",
        "precip_to_slp_residual_z",
        "slp_to_tau_residual_z",
    ]
    link_names = {
        "sst_to_precip_residual_z": "SST→降水",
        "precip_to_slp_residual_z": "降水→SLP",
        "slp_to_tau_residual_z": "SLP→风应力",
    }
    weakest_rows = []
    for _, row in y2023.iterrows():
        weakest = min(link_columns, key=lambda column: float(row[column]))
        weakest_rows.append(
            f"- {row['season']}最弱环节：{link_names[weakest]}，"
            f"残差{float(row[weakest]):+.2f} z。"
        )
    rank_variables = {
        "coupling_pattern_residual_z": "ERA5/GPCP综合",
        "ncep_coupling_pattern_residual_z": "NCEP风压综合",
        "precip_pattern_residual_z": "GPCP降水",
        "ncep_u_pattern_residual_z": "NCEP中太平洋风",
    }
    rank_lines = []
    for season in SEASONS:
        current = all_year_seasonal.loc[
            all_year_seasonal["year"].eq(2023)
            & all_year_seasonal["season"].eq(season)
        ].iloc[0]
        pieces = []
        for variable, label in rank_variables.items():
            pieces.append(
                f"{label}{int(current[f'{variable}_lower_rank'])}/42"
            )
        rank_lines.append(f"- {season}：" + "；".join(pieces) + "。")
    text = f"""# ENSO全年海气耦合演变：类型与脱耦分离诊断

## 为什么要延伸到全年

1—6月初检显示，2023年5—6月综合大气残差只有约−0.3 z，不能仅凭
春季资料称为“强脱耦”。Peng等研究讨论的是事件后续发展期的持续
弱风和弱SO响应，因此本阶段使用OISST、GPCP和ERA5把诊断延伸到
AMJ、JJA、SON和成熟DJF。

## 修正海洋分型指标

原先尝试的“140°W减去日界线/170°W”相对穿透分数与13事件类型关系
很弱。强EP发展时中太平洋D20也会加深，做差会删掉共同的盆地调整。
因此不再使用这个相对分数作为主结论，而是分别保留：

- 3—4月140°W Q20：东部通过量；
- 3—4月140°W D20：东部储存状态。

在13暖事件中，Q20与成熟`Niño3−Niño4`相关为
{q_stats.pearson_r_with_mature_type:+.3f}
（95% bootstrap CI {q_stats.bootstrap_ci_low:+.3f}—
{q_stats.bootstrap_ci_high:+.3f}，FDR q={q_stats.bh_fdr_q:.4f}）；
D20为{d_stats.pearson_r_with_mature_type:+.3f}
（CI {d_stats.bootstrap_ci_low:+.3f}—
{d_stats.bootstrap_ci_high:+.3f}，q={d_stats.bh_fdr_q:.4f}）；
二者等权状态为{joint_stats.pearson_r_with_mature_type:+.3f}
（CI {joint_stats.bootstrap_ci_low:+.3f}—
{joint_stats.bootstrap_ci_high:+.3f}，q={joint_stats.bh_fdr_q:.4f}）。
这里的等权量只作机制摘要，不作发生预测。

敏感性检查给出边界：逐一删除任一事件后，Q20相关最低仍为
{q_stats.leave_one_out_min_r:+.3f}，D20为
{d_stats.leave_one_out_min_r:+.3f}，联合状态为
{joint_stats.leave_one_out_min_r:+.3f}；但同时删除1982、1997、2015
三个经典强EP后，三者分别降为{q_stats.non_classic_ep_r:+.3f}、
{d_stats.non_classic_ep_r:+.3f}和{joint_stats.non_classic_ep_r:+.3f}。
所以信号并非由某一个事件单独制造，但强度明显依赖经典EP端点；
它适合解释“东部海洋状态”，不足以证明固定分型阈值。

## 全年耦合残差

大气响应由三个观测/再分析量共同表示：

1. GPCP 180°—110°W热带太平洋降水；
2. ERA5西部减东部SLP梯度；
3. ERA5 160°E—140°W表面纬向风应力。

每个日历月用1982—2014建立历史关系，基准期内采用留一年拟合。先仅
以Niño3.4幅度估计预期响应，再加入`Niño3−Niño4`型态。2023结果为：

{chr(10).join(lines)}

若加入空间型态后残差明显回到零，说明弱响应主要可由增暖位置解释；
若仍显著为负，才是更严格的“型态调整后脱耦”，需要外部海盆、背景
SST或大气内部变率解释。

### NCEP独立检查

使用NCEP近地层中太平洋纬向风及Tahiti−Darwin型压力差，按完全相同
的1982—2014历史关系重新计算：

{chr(10).join(ncep_lines)}

NCEP检查用于判断ERA5风应力/SLP的结论是否具有产品依赖；它不与ERA5
平均成一个“更高技巧”的指数。

### 2023在42年参考分布中的位置

以下是从弱到强的下尾排名（1/42表示42个起始年中最弱）：

{chr(10).join(rank_lines)}

这一区分了“残差为负”和“历史上确实罕见”。2023春季并不罕见；
夏季先出现风响应不足，成熟DJF时综合耦合残差进入42年最弱的前三，
其中GPCP降水残差为42年最低。

## 2023反馈链的季节变化

{chr(10).join(weakest_rows)}

最弱环节可以随季节变化，因此不能用一个全年平均残差代替过程诊断。
尤其“降水已经弱”与“SLP有响应但风没有接上”是两种不同机制。

## CP为什么不等于脱耦

CP复合的风和降水中心位于中太平洋，东部响应弱本身符合其SST空间
型态。只有在加入`Niño3−Niño4`以后，大气响应仍显著低于历史预期，
才能称为脱耦。图中同时报告仅按Niño3.4幅度和加入型态后的两套残差，
避免把“响应位置不同”误判为“耦合效率低”。

## 阶段结论

1. CP/EP类型与140°W的实际东部通过量和D20储存联系更强；相对
   日界线的简单做差不稳健。
2. 海洋分型与大气耦合效率是两个维度：经典EP通常两者都强，CP主要
   是响应位置偏中部，2023则需根据全年型态调整后残差判断弱耦合。
3. “海气脱耦”应写成相对于历史SST幅度与空间型态的连续残差，而不是
   依据某个月西风较弱作二元分类。
4. 这些是观测诊断，不是因果实验；外部海盆影响仍需AGCM或控制试验。

## 文件

- 全年月度诊断：`{MONTHLY_CSV.relative_to(ROOT)}`
- 事件季节汇总：`{SEASONAL_CSV.relative_to(ROOT)}`
- 42年季节参考分布：`{ALL_YEAR_SEASONAL_CSV.relative_to(ROOT)}`
- 东部海洋状态：`{OCEAN_CSV.relative_to(ROOT)}`
- 东部海洋状态统计：`{OCEAN_STATS_CSV.relative_to(ROOT)}`
- 图：`{PDF.relative_to(ROOT)}`
"""
    REPORT.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    monthly = build_monthly()
    seasonal = build_seasonal(monthly)
    all_year_seasonal = build_all_year_seasonal(monthly)
    ocean = build_ocean_summary()
    ocean_statistics = build_ocean_statistics(ocean)
    monthly.to_csv(MONTHLY_CSV, index=False)
    seasonal.to_csv(SEASONAL_CSV, index=False)
    all_year_seasonal.to_csv(ALL_YEAR_SEASONAL_CSV, index=False)
    ocean.to_csv(OCEAN_CSV, index=False)
    ocean_statistics.to_csv(OCEAN_STATS_CSV, index=False)
    diagnostics = {
        "purpose": "full-year coupling evolution, not onset prediction",
        "sources": {
            "sst": "OISST",
            "precipitation": "GPCP v2.3",
            "slp_and_wind_stress": "ERA5",
            "independent_wind_and_pressure": "NCEP reanalysis",
        },
        "historical_expectation_period": f"1982-{BASELINE_END}",
        "seasons": SEASONS,
        "event_years": EVENT_YEARS,
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_figure(seasonal, ocean)
    make_report(
        seasonal,
        ocean,
        all_year_seasonal,
        ocean_statistics,
    )
    print(
        seasonal.loc[
            seasonal["year"].isin([1997, 2015, 2023])
        ].to_string(index=False)
    )
    print()
    print(ocean.to_string(index=False))
    print(f"\n{REPORT}\n{PDF}")


if __name__ == "__main__":
    main()
