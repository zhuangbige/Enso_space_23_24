#!/usr/bin/env python3
"""Diagnose the ENSO-type boreal-spring prediction barrier in NMME hindcasts.

Primary question
----------------
For a fixed SON verification season, is the reduction in forecast error from
pre-/mid-spring initializations (March-April) to post-spring initializations
(June-July) larger for eventual eastern-Pacific (EP) than central-Pacific
(CP) El Nino events?

The script deliberately separates:

1. proper forecast verification: predicted SON anomalies versus observed SON;
2. event conditioning: EP/CP labels based on the observed mature DJF pattern;
3. operational model bias correction: a model-, initialization-, target-, and
   region-specific 1991-2020 hindcast climatology; and
4. the project's detrended anomaly convention.

The NOAA CPT files contain ensemble-mean seasonal SST on a 1-degree global
grid.  Only Nino-region area means are retained in the derived output.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "nmme_cpt" / "seasonal"
DERIVED_DIR = ROOT / "data" / "derived" / "research_2026"
OUTPUT_DIR = ROOT / "outputs" / "research_2026" / "nmme_enso_type_barrier"
ERSST_FILE = ROOT / "data" / "raw" / "ersstv5_sst_monthly_full.nc"
EVENT_FILE = DERIVED_DIR / "ep_cp_two_gate_event_summary_1982_2023.csv"
OCEAN_FILE = DERIVED_DIR / "enso_type_east_ocean_state_event_summary.csv"
COUPLING_FILE = DERIVED_DIR / "enso_type_coupling_event_summary.csv"

INDEX_FILE = DERIVED_DIR / "nmme_enso_type_hindcast_indices_1991_2020.csv"
SKILL_FILE = DERIVED_DIR / "nmme_enso_type_barrier_skill.csv"
EVENT_ERROR_FILE = DERIVED_DIR / "nmme_son_warm_event_errors.csv"
BARRIER_FILE = DERIVED_DIR / "nmme_son_type_barrier_summary.csv"
LINK_FILE = DERIVED_DIR / "nmme_son_error_predictor_correlations.csv"
SENSITIVITY_FILE = DERIVED_DIR / "nmme_son_barrier_sensitivity.csv"
DIAGNOSTICS_FILE = DERIVED_DIR / "nmme_enso_type_barrier_diagnostics.json"

MODEL_ORDER = (
    "nmme",
    "cfsv2",
    "cmc1",
    "cmc2",
    "nasa",
    "ncar_ccsm4",
    "ncar_cesm1",
)
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
TARGET_LABELS = {"9-11": "SON", "10-12": "OND", "11-1": "NDJ", "12-2": "DJF"}
TARGET_MONTHS = {
    "SON": ((0, 9), (0, 10), (0, 11)),
    "OND": ((0, 10), (0, 11), (0, 12)),
    "NDJ": ((0, 11), (0, 12), (1, 1)),
    "DJF": ((0, 12), (1, 1), (1, 2)),
}
REGIONS = {
    "nino3": (210.0, 270.0),
    "nino4": (160.0, 210.0),
    "nino34": (190.0, 240.0),
}
FILE_RE = re.compile(
    r"(?P<model>.+)_sst_hcst_(?P<init>[A-Z][a-z]{2})ic_"
    r"(?P<target>[0-9]+-[0-9]+)_(?P<years>[0-9]{4}-[0-9]{4})\.txt$"
)
HEADER_RE = re.compile(
    r"cpt:T=(?P<target>[^,]+), cpt:S=(?P<start>[0-9]{4}-[0-9]{2}-[0-9]{2}), "
    r"cpt:nrow=(?P<nrow>[0-9]+), cpt:ncol=(?P<ncol>[0-9]+)"
)


@dataclass(frozen=True)
class FileMetadata:
    model: str
    init_month: int
    target_season: str


def pearson(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    valid = np.isfinite(x.to_numpy(float)) & np.isfinite(y.to_numpy(float))
    if valid.sum() < 3:
        return math.nan, math.nan
    result = stats.pearsonr(x.to_numpy(float)[valid], y.to_numpy(float)[valid])
    return float(result.statistic), float(result.pvalue)


def spearman(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    valid = np.isfinite(x.to_numpy(float)) & np.isfinite(y.to_numpy(float))
    if valid.sum() < 3:
        return math.nan, math.nan
    result = stats.spearmanr(x.to_numpy(float)[valid], y.to_numpy(float)[valid])
    return float(result.statistic), float(result.pvalue)


def partial_pearson(
    x: pd.Series, y: pd.Series, controls: pd.DataFrame
) -> tuple[float, float]:
    combined = pd.concat([x, y, controls], axis=1).dropna()
    n = len(combined)
    k = controls.shape[1]
    if n <= k + 2:
        return math.nan, math.nan
    x_values = combined.iloc[:, 0].to_numpy(float)
    y_values = combined.iloc[:, 1].to_numpy(float)
    control_values = combined.iloc[:, 2:].to_numpy(float)
    design = np.column_stack([np.ones(n), control_values])
    x_residual = x_values - design @ np.linalg.lstsq(
        design, x_values, rcond=None
    )[0]
    y_residual = y_values - design @ np.linalg.lstsq(
        design, y_values, rcond=None
    )[0]
    r = float(np.corrcoef(x_residual, y_residual)[0, 1])
    degrees_of_freedom = n - k - 2
    if abs(r) >= 1.0:
        return r, 0.0
    t_value = r * math.sqrt(degrees_of_freedom / (1.0 - r**2))
    p_value = float(2.0 * stats.t.sf(abs(t_value), degrees_of_freedom))
    return r, p_value


def weighted_region_means(
    lons: np.ndarray, latitudes: list[float], rows: list[np.ndarray]
) -> dict[str, float]:
    lat = np.asarray(latitudes, dtype=float)
    data = np.vstack(rows)
    weights_lat = np.cos(np.deg2rad(lat))
    output: dict[str, float] = {}
    for name, (lon0, lon1) in REGIONS.items():
        lon_mask = (lons >= lon0) & (lons <= lon1)
        subset = data[:, lon_mask]
        weights = np.broadcast_to(weights_lat[:, None], subset.shape)
        valid = np.isfinite(subset)
        output[name] = float(
            np.sum(np.where(valid, subset * weights, 0.0))
            / np.sum(np.where(valid, weights, 0.0))
        )
    return output


def parse_filename(path: Path) -> FileMetadata:
    match = FILE_RE.match(path.name)
    if match is None:
        raise ValueError(f"Unrecognized NMME filename: {path.name}")
    init_month = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }[match.group("init")]
    return FileMetadata(
        model=match.group("model"),
        init_month=init_month,
        target_season=TARGET_LABELS[match.group("target")],
    )


def parse_cpt_file(path: Path) -> pd.DataFrame:
    metadata = parse_filename(path)
    records: list[dict[str, float | int | str]] = []
    with path.open(encoding="utf-8") as handle:
        iterator = iter(handle)
        for line in iterator:
            if not line.startswith("cpt:field="):
                continue
            match = HEADER_RE.search(line)
            if match is None:
                raise ValueError(f"Cannot parse CPT header in {path}: {line[:200]}")
            start = pd.Timestamp(match.group("start"))
            nrow = int(match.group("nrow"))
            ncol = int(match.group("ncol"))
            lon_fields = next(iterator).strip().split()
            lons = np.asarray(lon_fields, dtype=float)
            if lons.size != ncol:
                raise ValueError(f"Expected {ncol} longitudes, got {lons.size}")
            selected_latitudes: list[float] = []
            selected_rows: list[np.ndarray] = []
            for _ in range(nrow):
                fields = next(iterator).strip().split()
                if len(fields) != ncol + 1:
                    raise ValueError(
                        f"Expected {ncol + 1} values in {path}, got {len(fields)}"
                    )
                latitude = float(fields[0])
                if -5.0 <= latitude <= 5.0:
                    values = np.asarray(fields[1:], dtype=float)
                    values[values <= -900.0] = np.nan
                    selected_latitudes.append(latitude)
                    selected_rows.append(values)
            means = weighted_region_means(lons, selected_latitudes, selected_rows)
            records.append(
                {
                    "model": metadata.model,
                    "init_month": metadata.init_month,
                    "target_season": metadata.target_season,
                    "event_year": start.year,
                    **{f"forecast_{name}_raw_c": value for name, value in means.items()},
                }
            )
    result = pd.DataFrame.from_records(records)
    if len(result) != 30 or result["event_year"].nunique() != 30:
        raise ValueError(f"Expected 30 hindcast years in {path}, got {len(result)}")
    return result


def parse_all_forecasts() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("*_sst_hcst_*.txt"))
    if not files:
        raise FileNotFoundError(f"No NMME CPT files found under {RAW_DIR}")
    frames = []
    for index, path in enumerate(files, start=1):
        print(f"Parsing [{index:02d}/{len(files):02d}] {path.name}", flush=True)
        frames.append(parse_cpt_file(path))
    forecasts = pd.concat(frames, ignore_index=True)
    duplicates = forecasts.duplicated(
        ["model", "init_month", "target_season", "event_year"]
    )
    if duplicates.any():
        raise ValueError("Duplicate forecast records detected")
    return forecasts


def ersst_region_means() -> pd.DataFrame:
    ds = xr.open_dataset(ERSST_FILE)
    sst = ds["sst"].sel(time=slice("1991-01-01", "2021-02-01"))
    lat_mask = (sst.lat >= -5.0) & (sst.lat <= 5.0)
    sst = sst.sel(lat=sst.lat[lat_mask])
    lat_weights = np.cos(np.deg2rad(sst.lat))
    records: list[dict[str, float | int | str]] = []
    for event_year in range(1991, 2021):
        for target_season, offsets_months in TARGET_MONTHS.items():
            times = [
                pd.Timestamp(event_year + year_offset, month, 1)
                for year_offset, month in offsets_months
            ]
            seasonal = sst.sel(time=times).mean("time")
            record: dict[str, float | int | str] = {
                "event_year": event_year,
                "target_season": target_season,
            }
            for name, (lon0, lon1) in REGIONS.items():
                region = seasonal.sel(lon=slice(lon0, lon1))
                value = region.weighted(lat_weights).mean(("lat", "lon"))
                record[f"observed_{name}_raw_c"] = float(value)
            records.append(record)
    ds.close()
    return pd.DataFrame.from_records(records)


def detrend_by_groups(
    data: pd.DataFrame,
    group_columns: list[str],
    column: str,
    output_column: str,
) -> None:
    output = pd.Series(np.nan, index=data.index, dtype=float)
    grouper: str | list[str] = (
        group_columns[0] if len(group_columns) == 1 else group_columns
    )
    for _, indices in data.groupby(grouper, sort=False).groups.items():
        group = data.loc[indices]
        x = group["event_year"].to_numpy(float)
        y = group[column].to_numpy(float)
        valid = np.isfinite(y)
        if valid.sum() < 3:
            continue
        slope, intercept = np.polyfit(x[valid], y[valid], deg=1)
        output.loc[indices] = y - (slope * x + intercept)
    data[output_column] = output


def add_anomalies(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    forecast_groups = ["model", "init_month", "target_season"]
    observed_groups = ["target_season"]
    for region in REGIONS:
        forecast_raw = f"forecast_{region}_raw_c"
        observed_raw = f"observed_{region}_raw_c"
        data[f"forecast_{region}_anom_c"] = data[forecast_raw] - data.groupby(
            forecast_groups
        )[forecast_raw].transform("mean")
        data[f"observed_{region}_anom_c"] = data[observed_raw] - data.groupby(
            observed_groups
        )[observed_raw].transform("mean")

        detrend_by_groups(
            data,
            forecast_groups,
            f"forecast_{region}_anom_c",
            f"forecast_{region}_anom_dt_c",
        )
        detrend_by_groups(
            data,
            observed_groups,
            f"observed_{region}_anom_c",
            f"observed_{region}_anom_dt_c",
        )

    for prefix in ("forecast", "observed"):
        data[f"{prefix}_type_dt_c"] = (
            data[f"{prefix}_nino3_anom_dt_c"]
            - data[f"{prefix}_nino4_anom_dt_c"]
        )
    data["type_error_dt_c"] = (
        data["forecast_type_dt_c"] - data["observed_type_dt_c"]
    )
    data["abs_type_error_dt_c"] = data["type_error_dt_c"].abs()
    data["nino34_error_dt_c"] = (
        data["forecast_nino34_anom_dt_c"] - data["observed_nino34_anom_dt_c"]
    )
    data["abs_nino34_error_dt_c"] = data["nino34_error_dt_c"].abs()
    return data


def attach_event_groups(data: pd.DataFrame) -> pd.DataFrame:
    events = pd.read_csv(EVENT_FILE).rename(columns={"event_year": "year"})
    keep = events[
        [
            "year",
            "event_label",
            "mature_djf_type_index_c",
            "mature_djf_nino34_c",
            "mature_flavor",
            "borderline_abs_type_lt_0p2",
        ]
    ].copy()
    keep["enso_type_group"] = np.select(
        [
            keep["mature_djf_type_index_c"] >= 0.2,
            keep["mature_djf_type_index_c"] <= -0.2,
        ],
        ["EP", "CP"],
        default="borderline",
    )
    result = data.merge(keep, left_on="event_year", right_on="year", how="left")
    result["is_warm_event"] = result["year"].notna()
    result = result.drop(columns="year")
    return result


def validate_scientific_inputs(data: pd.DataFrame) -> dict[str, float]:
    required = [
        "forecast_nino3_raw_c",
        "forecast_nino4_raw_c",
        "forecast_nino34_raw_c",
        "observed_nino3_raw_c",
        "observed_nino4_raw_c",
        "observed_nino34_raw_c",
    ]
    if data[required].isna().any().any():
        raise ValueError("Missing SST values in a Niño region")
    extrema = data[required].agg(["min", "max"])
    if extrema.loc["min"].min() < 15.0 or extrema.loc["max"].max() > 35.0:
        raise ValueError(f"Physically implausible tropical Pacific SST:\n{extrema}")

    son_sets = (
        data[data.target_season == "SON"]
        .groupby("model")["init_month"]
        .apply(lambda values: sorted(values.unique().tolist()))
    )
    for model, initialization_months in son_sets.items():
        if initialization_months != [3, 4, 5, 6, 7]:
            raise ValueError(
                f"Incomplete SON initialization set for {model}: "
                f"{initialization_months}"
            )

    comparison = data[
        (data.model == "nmme")
        & (data.target_season == "DJF")
        & (data.init_month == 7)
        & data.is_warm_event
    ]
    type_r, _ = pearson(
        comparison["observed_type_dt_c"],
        comparison["mature_djf_type_index_c"],
    )
    nino34_r, _ = pearson(
        comparison["observed_nino34_anom_dt_c"],
        comparison["mature_djf_nino34_c"],
    )
    if type_r < 0.98 or nino34_r < 0.98:
        raise ValueError(
            "ERSST verification does not reproduce the existing mature-event "
            f"indices (type r={type_r:.3f}, Niño3.4 r={nino34_r:.3f})"
        )
    return {
        "observed_type_index_crosscheck_r": type_r,
        "observed_nino34_crosscheck_r": nino34_r,
    }


def metric_row(group: pd.DataFrame) -> dict[str, float | int]:
    type_r, type_p = pearson(
        group["forecast_type_dt_c"], group["observed_type_dt_c"]
    )
    n34_r, n34_p = pearson(
        group["forecast_nino34_anom_dt_c"],
        group["observed_nino34_anom_dt_c"],
    )
    warm = group[group["is_warm_event"]]
    classified = warm[warm["enso_type_group"].isin(["EP", "CP"])].copy()
    if len(classified):
        expected_sign = np.where(classified["enso_type_group"] == "EP", 1.0, -1.0)
        type_sign_accuracy = float(
            np.mean(np.sign(classified["forecast_type_dt_c"]) == expected_sign)
        )
    else:
        type_sign_accuracy = math.nan
    return {
        "n_all_years": int(len(group)),
        "type_acc": type_r,
        "type_acc_p": type_p,
        "type_rmse_c": float(np.sqrt(np.mean(group["type_error_dt_c"] ** 2))),
        "nino34_acc": n34_r,
        "nino34_acc_p": n34_p,
        "nino34_rmse_c": float(np.sqrt(np.mean(group["nino34_error_dt_c"] ** 2))),
        "n_warm_events": int(len(warm)),
        "n_classified_warm_events": int(len(classified)),
        "warm_type_mae_c": float(warm["abs_type_error_dt_c"].mean()),
        "warm_type_sign_accuracy": type_sign_accuracy,
        "ep_n": int((warm["enso_type_group"] == "EP").sum()),
        "ep_type_mae_c": float(
            warm.loc[warm["enso_type_group"] == "EP", "abs_type_error_dt_c"].mean()
        ),
        "cp_n": int((warm["enso_type_group"] == "CP").sum()),
        "cp_type_mae_c": float(
            warm.loc[warm["enso_type_group"] == "CP", "abs_type_error_dt_c"].mean()
        ),
    }


def build_skill_table(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in data.groupby(["model", "init_month", "target_season"]):
        row = {
            "model": keys[0],
            "init_month": int(keys[1]),
            "target_season": keys[2],
        }
        row.update(metric_row(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["model", "target_season", "init_month"]
    )


def bootstrap_barrier_difference(
    event_errors: pd.DataFrame, n_bootstrap: int = 20_000
) -> dict[str, float]:
    rng = np.random.default_rng(20260731)
    penalties: dict[str, np.ndarray] = {}
    for group_name in ("EP", "CP"):
        subset = event_errors[event_errors["enso_type_group"] == group_name]
        values = subset["spring_penalty_c"].dropna().to_numpy(float)
        if len(values) == 0:
            penalties[group_name] = np.full(n_bootstrap, np.nan)
            continue
        draws = rng.choice(values, size=(n_bootstrap, len(values)), replace=True)
        penalties[group_name] = draws.mean(axis=1)
    difference = penalties["EP"] - penalties["CP"]
    return {
        "ep_minus_cp_mean_c": float(np.nanmean(difference)),
        "ep_minus_cp_ci_low_c": float(np.nanpercentile(difference, 2.5)),
        "ep_minus_cp_ci_high_c": float(np.nanpercentile(difference, 97.5)),
        "probability_ep_penalty_greater_than_cp": float(np.nanmean(difference > 0)),
    }


def build_barrier_tables(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    son = data[
        (data["target_season"] == "SON")
        & data["is_warm_event"]
        & data["enso_type_group"].isin(["EP", "CP"])
    ].copy()
    event_rows = []
    for keys, group in son.groupby(
        ["model", "event_year", "event_label", "enso_type_group"]
    ):
        init_error = group.set_index("init_month")["abs_type_error_dt_c"]
        pre = init_error.reindex([3, 4]).mean()
        post = init_error.reindex([6, 7]).mean()
        event_rows.append(
            {
                "model": keys[0],
                "event_year": int(keys[1]),
                "event_label": keys[2],
                "enso_type_group": keys[3],
                "pre_spring_mae_c": float(pre),
                "post_spring_mae_c": float(post),
                "spring_penalty_c": float(pre - post),
                **{
                    f"{INIT_LABELS[month].lower()}_abs_type_error_c": float(
                        init_error.get(month, np.nan)
                    )
                    for month in INIT_LABELS
                },
            }
        )
    event_errors = pd.DataFrame(event_rows)

    rows = []
    for (model, group_name), group in event_errors.groupby(
        ["model", "enso_type_group"]
    ):
        values = group["spring_penalty_c"]
        rows.append(
            {
                "model": model,
                "enso_type_group": group_name,
                "n_events": int(len(group)),
                "pre_spring_mae_c": float(group["pre_spring_mae_c"].mean()),
                "post_spring_mae_c": float(group["post_spring_mae_c"].mean()),
                "spring_penalty_mean_c": float(values.mean()),
                "spring_penalty_median_c": float(values.median()),
                "spring_penalty_min_c": float(values.min()),
                "spring_penalty_max_c": float(values.max()),
            }
        )
    barrier = pd.DataFrame(rows)
    return event_errors, barrier


def barrier_sensitivity(data: pd.DataFrame) -> pd.DataFrame:
    son = data[
        (data["model"] == "nmme")
        & (data["target_season"] == "SON")
        & data["is_warm_event"]
    ].copy()
    son["type_error_anom_c"] = (
        son["forecast_nino3_anom_c"]
        - son["forecast_nino4_anom_c"]
        - son["observed_nino3_anom_c"]
        + son["observed_nino4_anom_c"]
    )
    settings = (
        ("detrended_threshold_0p2", "type_error_dt_c", 0.2),
        ("not_detrended_threshold_0p2", "type_error_anom_c", 0.2),
        ("detrended_threshold_0p3", "type_error_dt_c", 0.3),
        ("detrended_sign_only", "type_error_dt_c", 0.0),
    )
    rows = []
    for label, error_column, threshold in settings:
        subset = son.copy()
        subset["sensitivity_group"] = np.select(
            [
                subset["mature_djf_type_index_c"] > threshold,
                subset["mature_djf_type_index_c"] < -threshold,
            ],
            ["EP", "CP"],
            default="excluded",
        )
        subset["metric_abs_error"] = subset[error_column].abs()
        event_penalties = (
            subset[
                subset["sensitivity_group"].isin(["EP", "CP"])
                & subset["init_month"].isin([3, 4, 6, 7])
            ]
            .groupby(["event_year", "sensitivity_group", "init_month"])[
                "metric_abs_error"
            ]
            .mean()
            .unstack("init_month")
        )
        event_penalties["spring_penalty_c"] = (
            event_penalties[[3, 4]].mean(axis=1)
            - event_penalties[[6, 7]].mean(axis=1)
        )
        grouped = event_penalties.groupby("sensitivity_group")["spring_penalty_c"]
        ep_values = grouped.get_group("EP").to_numpy(float)
        cp_values = grouped.get_group("CP").to_numpy(float)
        difference = float(ep_values.mean() - cp_values.mean())

        leave_one_out = []
        combined = event_penalties.reset_index()
        for event_year in combined["event_year"]:
            retained = combined[combined["event_year"] != event_year]
            means = retained.groupby("sensitivity_group")["spring_penalty_c"].mean()
            if {"EP", "CP"}.issubset(means.index):
                leave_one_out.append(float(means["EP"] - means["CP"]))
        rows.append(
            {
                "setting": label,
                "error_metric": error_column,
                "type_threshold_c": threshold,
                "ep_n": int(len(ep_values)),
                "cp_n": int(len(cp_values)),
                "ep_spring_penalty_c": float(ep_values.mean()),
                "cp_spring_penalty_c": float(cp_values.mean()),
                "ep_minus_cp_c": difference,
                "leave_one_event_out_min_c": float(np.min(leave_one_out)),
                "leave_one_event_out_max_c": float(np.max(leave_one_out)),
            }
        )
    return pd.DataFrame(rows)


def predictor_correlations(data: pd.DataFrame) -> pd.DataFrame:
    son = data[
        (data["model"] == "nmme")
        & (data["target_season"] == "SON")
        & data["is_warm_event"]
    ].copy()
    early = (
        son[son["init_month"].isin([3, 4])]
        .groupby("event_year", as_index=False)
        .agg(
            early_abs_type_error_c=("abs_type_error_dt_c", "mean"),
            early_signed_type_error_c=("type_error_dt_c", "mean"),
            mature_djf_type_index_c=("mature_djf_type_index_c", "first"),
            mature_djf_nino34_c=("mature_djf_nino34_c", "first"),
        )
        .rename(columns={"event_year": "year"})
    )
    early["abs_mature_djf_type_index_c"] = early[
        "mature_djf_type_index_c"
    ].abs()
    ocean = pd.read_csv(OCEAN_FILE)[
        ["year", "q140_mar_apr_z", "d140_mar_apr_z", "east_ocean_state_z"]
    ]
    coupling = pd.read_csv(COUPLING_FILE)[
        [
            "year",
            "mar_apr_ocean_penetration_z",
            "mar_apr_fep_residual_c",
            "may_jun_intensity_coupling_residual_z",
            "may_jun_pattern_coupling_residual_z",
            "mar_jun_sst_to_precip_residual_z",
            "mar_jun_precip_to_slp_residual_z",
            "mar_jun_slp_to_tau_residual_z",
        ]
    ]
    joined = early.merge(ocean, on="year", how="left").merge(
        coupling, on="year", how="left"
    )
    predictor_columns = [
        "q140_mar_apr_z",
        "d140_mar_apr_z",
        "east_ocean_state_z",
        "mar_apr_ocean_penetration_z",
        "mar_apr_fep_residual_c",
        "may_jun_intensity_coupling_residual_z",
        "may_jun_pattern_coupling_residual_z",
        "mar_jun_sst_to_precip_residual_z",
        "mar_jun_precip_to_slp_residual_z",
        "mar_jun_slp_to_tau_residual_z",
    ]
    rows = []
    for error_column in (
        "early_abs_type_error_c",
        "early_signed_type_error_c",
    ):
        for predictor in predictor_columns:
            r, p = pearson(joined[predictor], joined[error_column])
            rho, rho_p = spearman(joined[predictor], joined[error_column])
            partial_r, partial_p = partial_pearson(
                joined[predictor],
                joined[error_column],
                joined[
                    ["abs_mature_djf_type_index_c", "mature_djf_nino34_c"]
                ],
            )
            rows.append(
                {
                    "error_metric": error_column,
                    "predictor": predictor,
                    "n": int(joined[[predictor, error_column]].dropna().shape[0]),
                    "pearson_r": r,
                    "pearson_p": p,
                    "spearman_rho": rho,
                    "spearman_p": rho_p,
                    "partial_r_controlling_type_and_nino34": partial_r,
                    "partial_p_controlling_type_and_nino34": partial_p,
                }
            )
    return (
        pd.DataFrame(rows)
        .assign(abs_pearson_r=lambda frame: frame["pearson_r"].abs())
        .sort_values(["error_metric", "abs_pearson_r"], ascending=[True, False])
        .drop(columns="abs_pearson_r")
    )


def plot_main(
    data: pd.DataFrame,
    skill: pd.DataFrame,
    event_errors: pd.DataFrame,
    barrier: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 8.7), constrained_layout=True)
    ax = axes[0, 0]
    mm = skill[(skill.model == "nmme") & (skill.target_season == "SON")].sort_values(
        "init_month"
    )
    ax.plot(
        mm.init_month,
        mm.type_acc,
        marker="o",
        lw=2.2,
        color="#C84C3A",
        label="Type index: Niño3 − Niño4",
    )
    ax.plot(
        mm.init_month,
        mm.nino34_acc,
        marker="s",
        lw=2.0,
        color="#2670A8",
        label="Niño3.4 amplitude",
    )
    ax.axhline(0, color="#777777", lw=0.8)
    ax.axvspan(3, 5, color="#F3D9B1", alpha=0.35, zorder=0)
    ax.set(
        title="(a) Fixed SON target: all-year anomaly correlation",
        ylabel="Correlation",
        xticks=list(INIT_LABELS),
        xticklabels=[INIT_LABELS[m] for m in INIT_LABELS],
        ylim=(-0.2, 1.0),
    )
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", color="#DDDDDD", lw=0.6)

    ax = axes[0, 1]
    son_warm = data[
        (data.model == "nmme")
        & (data.target_season == "SON")
        & data.enso_type_group.isin(["EP", "CP"])
    ]
    palette = {"EP": "#C84C3A", "CP": "#2670A8"}
    for group_name in ("EP", "CP"):
        subset = son_warm[son_warm.enso_type_group == group_name]
        summary = subset.groupby("init_month")["abs_type_error_dt_c"].agg(
            ["mean", "std", "count"]
        )
        sem = summary["std"] / np.sqrt(summary["count"])
        ax.errorbar(
            summary.index,
            summary["mean"],
            yerr=sem,
            marker="o",
            capsize=3,
            lw=2.2,
            color=palette[group_name],
            label=f"{group_name} events (n={int(summary['count'].iloc[0])})",
        )
    ax.axvspan(3, 5, color="#F3D9B1", alpha=0.35, zorder=0)
    ax.set(
        title="(b) Event-conditioned SON type error",
        ylabel="Mean absolute type error (°C)",
        xticks=list(INIT_LABELS),
        xticklabels=[INIT_LABELS[m] for m in INIT_LABELS],
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#DDDDDD", lw=0.6)

    ax = axes[1, 0]
    plot_barrier = barrier[barrier.model.isin(MODEL_ORDER)].copy()
    wide = plot_barrier.pivot(
        index="model", columns="enso_type_group", values="spring_penalty_mean_c"
    ).reindex(MODEL_ORDER)
    x = np.arange(len(wide))
    width = 0.36
    ax.bar(
        x - width / 2,
        wide["EP"],
        width,
        color=palette["EP"],
        label="EP",
    )
    ax.bar(
        x + width / 2,
        wide["CP"],
        width,
        color=palette["CP"],
        label="CP",
    )
    ax.axhline(0, color="#333333", lw=0.9)
    ax.set(
        title="(c) Spring penalty: Mar–Apr error minus Jun–Jul error",
        ylabel="Error reduction after spring (°C)",
        xticks=x,
        xticklabels=[MODEL_LABELS.get(m, m) for m in wide.index],
    )
    ax.tick_params(axis="x", rotation=25)
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#DDDDDD", lw=0.6)

    ax = axes[1, 1]
    mm_events = event_errors[event_errors.model == "nmme"].sort_values(
        ["enso_type_group", "event_year"]
    )
    positions = np.arange(len(mm_events))
    colors = [palette[group] for group in mm_events.enso_type_group]
    ax.scatter(
        positions,
        mm_events.spring_penalty_c,
        c=colors,
        s=62,
        edgecolor="white",
        linewidth=0.7,
        zorder=3,
    )
    ax.axhline(0, color="#333333", lw=0.9)
    ax.set(
        title="(d) NMME event-level spring penalty",
        ylabel="Mar–Apr MAE − Jun–Jul MAE (°C)",
        xticks=positions,
        xticklabels=mm_events.event_label,
    )
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", color="#DDDDDD", lw=0.6)
    for position, row in zip(positions, mm_events.itertuples(), strict=True):
        ax.annotate(
            row.enso_type_group,
            (position, row.spring_penalty_c),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            color=palette[row.enso_type_group],
            fontsize=8,
            weight="bold",
        )

    fig.suptitle(
        "NMME hindcast test of the ENSO-type spring predictability barrier",
        fontsize=16,
        weight="bold",
    )
    fig.text(
        0.5,
        -0.018,
        "NOAA NMME seasonal SST hindcasts, 1991–2020; ERSSTv5 verification. "
        "Anomalies are model-specific and linearly detrended. EP/CP groups use "
        "the observed mature-DJF Niño3−Niño4 index (|index| ≥ 0.2 °C). "
        "Shading marks initializations before or within boreal spring.",
        ha="center",
        va="bottom",
        fontsize=8.5,
    )
    for extension in ("png", "pdf"):
        path = OUTPUT_DIR / f"nmme_enso_type_spring_barrier_main.{extension}"
        fig.savefig(path, dpi=400 if extension == "png" else None, bbox_inches="tight")
    plt.close(fig)


def plot_skill_heatmaps(skill: pd.DataFrame) -> None:
    mm = skill[skill.model == "nmme"].copy()
    seasons = ["SON", "OND", "NDJ", "DJF"]
    init_months = list(INIT_LABELS)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.7), constrained_layout=True)
    for ax, metric, title in (
        (axes[0], "type_acc", "(a) Niño3 − Niño4 pattern skill"),
        (axes[1], "nino34_acc", "(b) Niño3.4 amplitude skill"),
    ):
        matrix = (
            mm.pivot(index="target_season", columns="init_month", values=metric)
            .reindex(index=seasons, columns=init_months)
            .to_numpy(float)
        )
        image = ax.imshow(
            matrix,
            cmap="RdYlBu_r",
            vmin=-0.2,
            vmax=1.0,
            aspect="auto",
        )
        ax.set(
            title=title,
            xlabel="Initialization month",
            ylabel="Verification season",
            xticks=np.arange(len(init_months)),
            xticklabels=[INIT_LABELS[m] for m in init_months],
            yticks=np.arange(len(seasons)),
            yticklabels=seasons,
        )
        for row in range(matrix.shape[0]):
            for column in range(matrix.shape[1]):
                if np.isfinite(matrix[row, column]):
                    ax.text(
                        column,
                        row,
                        f"{matrix[row, column]:.2f}",
                        ha="center",
                        va="center",
                        fontsize=9,
                        color="black" if matrix[row, column] < 0.75 else "white",
                    )
    cbar = fig.colorbar(image, ax=axes, shrink=0.86, pad=0.03)
    cbar.set_label("Anomaly correlation")
    fig.suptitle(
        "NMME multi-model mean seasonal SST hindcast skill, 1991–2020",
        fontsize=14,
        weight="bold",
    )
    fig.text(
        0.5,
        0.005,
        "Blank cells are unavailable initialization–target combinations in the "
        "NOAA seasonal CPT archive.",
        ha="center",
        fontsize=8.5,
    )
    for extension in ("png", "pdf"):
        path = OUTPUT_DIR / f"nmme_enso_type_skill_heatmaps.{extension}"
        fig.savefig(path, dpi=400 if extension == "png" else None, bbox_inches="tight")
    plt.close(fig)


def plot_event_forecasts(data: pd.DataFrame) -> None:
    subset = data[
        (data["model"] == "nmme")
        & (data["target_season"] == "SON")
        & data["enso_type_group"].isin(["EP", "CP"])
    ].copy()
    event_metadata = (
        subset[
            [
                "event_year",
                "event_label",
                "enso_type_group",
                "observed_type_dt_c",
            ]
        ]
        .drop_duplicates()
        .sort_values("event_year")
    )
    all_values = np.concatenate(
        [
            subset["forecast_type_dt_c"].to_numpy(float),
            event_metadata["observed_type_dt_c"].to_numpy(float),
        ]
    )
    lower = math.floor((np.nanmin(all_values) - 0.2) * 2) / 2
    upper = math.ceil((np.nanmax(all_values) + 0.2) * 2) / 2
    palette = {"EP": "#C84C3A", "CP": "#2670A8"}
    fig, axes = plt.subplots(2, 3, figsize=(12.0, 6.8), sharex=True, sharey=True)
    for ax, event in zip(axes.ravel(), event_metadata.itertuples(), strict=True):
        event_data = subset[subset.event_year == event.event_year].sort_values(
            "init_month"
        )
        color = palette[event.enso_type_group]
        ax.plot(
            event_data.init_month,
            event_data.forecast_type_dt_c,
            color=color,
            marker="o",
            lw=2.1,
            label="NMME forecast",
        )
        ax.axhline(
            event.observed_type_dt_c,
            color="#303030",
            ls="--",
            lw=1.5,
            label="Observed SON",
        )
        ax.axhline(0, color="#999999", lw=0.7)
        ax.axvspan(3, 5, color="#F3D9B1", alpha=0.35, zorder=0)
        ax.set(
            title=f"{event.event_label}  ({event.enso_type_group})",
            xticks=list(INIT_LABELS),
            xticklabels=[INIT_LABELS[m] for m in INIT_LABELS],
            ylim=(lower, upper),
        )
        ax.grid(axis="y", color="#DDDDDD", lw=0.6)
    axes[0, 0].legend(frameon=False, fontsize=8, loc="upper left")
    for ax in axes[:, 0]:
        ax.set_ylabel("SON Niño3 − Niño4 anomaly (°C)")
    for ax in axes[-1, :]:
        ax.set_xlabel("Initialization month")
    fig.suptitle(
        "NMME forecasts of the developing-season ENSO SST pattern",
        fontsize=14,
        weight="bold",
    )
    fig.text(
        0.5,
        0.012,
        "Positive values indicate an eastward-tilted SST anomaly pattern; "
        "negative values indicate a central-Pacific-tilted pattern. "
        "All series use model-specific 1991–2020 climatologies and linear detrending.",
        ha="center",
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.045, 1, 0.95))
    for extension in ("png", "pdf"):
        path = OUTPUT_DIR / f"nmme_son_event_type_forecasts.{extension}"
        fig.savefig(path, dpi=400 if extension == "png" else None, bbox_inches="tight")
    plt.close(fig)


def write_report(
    skill: pd.DataFrame,
    event_errors: pd.DataFrame,
    barrier: pd.DataFrame,
    correlations: pd.DataFrame,
    sensitivity: pd.DataFrame,
    bootstrap: dict[str, float],
) -> None:
    mm_barrier = barrier[barrier.model == "nmme"].set_index("enso_type_group")
    ep = mm_barrier.loc["EP"]
    cp = mm_barrier.loc["CP"]
    mm_son = skill[(skill.model == "nmme") & (skill.target_season == "SON")]
    mar = mm_son.set_index("init_month").loc[3]
    jul = mm_son.set_index("init_month").loc[7]
    strongest = (
        correlations[correlations.error_metric == "early_abs_type_error_c"]
        .assign(abs_r=lambda frame: frame.pearson_r.abs())
        .sort_values("abs_r", ascending=False)
        .iloc[0]
    )
    cross_model = (
        barrier.pivot(
            index="model",
            columns="enso_type_group",
            values="spring_penalty_mean_c",
        )
        .dropna(subset=["EP", "CP"])
        .assign(ep_minus_cp_c=lambda frame: frame["EP"] - frame["CP"])
    )
    individual = cross_model.drop(index="nmme", errors="ignore")
    baseline_sensitivity = sensitivity[
        sensitivity.setting == "detrended_threshold_0p2"
    ].iloc[0]
    raw_sensitivity = sensitivity[
        sensitivity.setting == "not_detrended_threshold_0p2"
    ].iloc[0]
    report = f"""# NMME回报试验：哪一类厄尔尼诺的春季预报障碍更明显

## 结论

在NOAA NMME 1991–2020年季节SST回报中，以固定SON为预测目标、用成熟DJF的
Niño3−Niño4观测指标区分事件后：

- EP组（n={int(ep.n_events)}）从3–4月起报到6–7月起报的平均类型绝对误差变化为
  **{ep.spring_penalty_mean_c:+.2f} °C**；
- CP组（n={int(cp.n_events)}）对应变化为
  **{cp.spring_penalty_mean_c:+.2f} °C**；
- EP减CP为 **{bootstrap['ep_minus_cp_mean_c']:+.2f} °C**，事件自助法95%区间为
  [{bootstrap['ep_minus_cp_ci_low_c']:+.2f},
  {bootstrap['ep_minus_cp_ci_high_c']:+.2f}] °C，
  EP障碍较大的重采样概率为
  {bootstrap['probability_ep_penalty_greater_than_cp']:.0%}。
- 在{len(individual)}个单模式中，有
  **{int((individual.ep_minus_cp_c > 0).sum())}/{len(individual)}**个给出EP大于CP，
  单模式EP−CP差值范围为
  [{individual.ep_minus_cp_c.min():+.2f}, {individual.ep_minus_cp_c.max():+.2f}] °C。

因此，本数据给出的判断必须分成两层：**点估计可用于判断方向，但样本不足以给出
稳定的类型差异显著性结论。** 如果EP的误差在春季后明显下降而CP没有同等下降，
才支持“EP春季障碍更强”；若两组差值很小或区间跨零，则只能说NMME中尚未验证该
文献结论。

敏感性检验显示，不去趋势时EP−CP为
**{raw_sensitivity.ep_minus_cp_c:+.2f} °C**；主定义逐一剔除任一事件后，
EP−CP范围为
[{baseline_sensitivity.leave_one_event_out_min_c:+.2f},
{baseline_sensitivity.leave_one_event_out_max_c:+.2f}] °C。
这用于判断方向是否完全由1997/98单个极端事件控制。

## 资料与方法

- 预测：NOAA CPC NMME季节SST回报，1°网格，1991–2020；
- 验证：NOAA ERSSTv5；
- Niño3：5°S–5°N，150°W–90°W；
- Niño4：5°S–5°N，160°E–150°W；
- Niño3.4：5°S–5°N，170°W–120°W；
- 类型指标：Niño3−Niño4；
- 每个模型、起报月、目标季节和区域分别计算1991–2020回报气候态；
- 预测与观测异常分别去除1991–2020线性趋势；
- EP/CP事件标签继续沿用现有报告的观测分型；这里不把模型回报气候态替换成报告
  的观测气候态，因为季节模式必须用各自回报期、各起报月的模式气候态订正漂移；
- 主检验固定SON目标，比较3–4月和6–7月起报的类型误差；
- EP/CP按成熟DJF观测类型指标阈值±0.2 °C分组，临界事件不参加两组比较。

## 基础预报技巧

NMME多模式平均对SON类型指标的全样本相关从3月起报的
**r={mar.type_acc:.2f}**变化到7月起报的**r={jul.type_acc:.2f}**；
Niño3.4对应从**r={mar.nino34_acc:.2f}**变化到
**r={jul.nino34_acc:.2f}**。这两条曲线必须同时看：Niño3.4技巧高但
Niño3−Niño4技巧低，说明模型可能预测到了厄尔尼诺强度，却没有预测对暖中心位置。

## 与海洋预条件和海气耦合的连接

在现有暖事件中，NMME 3–4月起报的SON类型绝对误差与候选量相关性最大的变量是
`{strongest.predictor}`（Pearson r={strongest.pearson_r:+.2f},
p={strongest.pearson_p:.3f}, n={int(strongest.n)}）；控制成熟期类型幅度和
Niño3.4强度后，偏相关为
r={strongest.partial_r_controlling_type_and_nino34:+.2f}
（p={strongest.partial_p_controlling_type_and_nino34:.3f}）。
由于候选量多而事件数少，这只是探索性筛选，不作为独立机制证据；它的用途是决定
下一步应重点检查模型是否已经预测到东传暖水，还是预测到了海洋状态却没有接上
风—降水反馈。

## 科学限制

1. 1991–2020只有少量非临界EP和CP暖事件，集合成员不能替代独立事件；
2. 这里是业务回报验证，不是完美模式误差增长实验；
3. 固定SON目标下，较晚起报天然具有较短提前期，因此EP−CP差值比任一组的绝对
   “春季惩罚”更可解释；
4. IRI Niño3.4 plume不能区分EP和CP，只适合做实际业务预报强度的补充验证；
5. 最终结论需要用另一套系统（例如SEAS5）或更长的CFSv2回报作独立复核。

## 资料与文献链接

- NOAA CPC NMME数据入口：
  https://www.cpc.ncep.noaa.gov/products/NMME/data.html
- NOAA CPC季节回报CPT目录：
  https://ftp.cpc.ncep.noaa.gov/International/nmme/seasonal_nmme_hindcast_in_cpt_format/
- IRI ENSO历史业务预报：
  https://iri.columbia.edu/our-expertise/climate/forecasts/enso/archive/
- Hou, Duan & Zhi：EP春季障碍、CP夏季障碍的完美模式研究：
  https://link.springer.com/article/10.1007/s00382-019-04888-w
- Zhao et al. (2022)：外热带太平洋对跨越ENSO春季障碍的作用：
  https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022GL099488

## 输出

- 主图：`outputs/research_2026/nmme_enso_type_barrier/nmme_enso_type_spring_barrier_main.pdf`
- 技巧矩阵：`outputs/research_2026/nmme_enso_type_barrier/nmme_enso_type_skill_heatmaps.pdf`
- 事件预测轨迹：`outputs/research_2026/nmme_enso_type_barrier/nmme_son_event_type_forecasts.pdf`
- 全部指数：`data/derived/research_2026/nmme_enso_type_hindcast_indices_1991_2020.csv`
- 事件误差：`data/derived/research_2026/nmme_son_warm_event_errors.csv`
- 障碍统计：`data/derived/research_2026/nmme_son_type_barrier_summary.csv`
- 候选联系：`data/derived/research_2026/nmme_son_error_predictor_correlations.csv`
- 敏感性检验：`data/derived/research_2026/nmme_son_barrier_sensitivity.csv`
"""
    report_path = ROOT / "reports" / "NMME_EP_CP春季预报障碍分析.md"
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    forecasts = parse_all_forecasts()
    observed = ersst_region_means()
    data = forecasts.merge(
        observed, on=["event_year", "target_season"], how="left", validate="many_to_one"
    )
    if data.filter(regex=r"^observed_").isna().any().any():
        raise ValueError("Missing ERSST verification values")
    data = add_anomalies(data)
    data = attach_event_groups(data)
    data = data.sort_values(
        ["model", "target_season", "init_month", "event_year"]
    ).reset_index(drop=True)
    validation = validate_scientific_inputs(data)
    data.to_csv(INDEX_FILE, index=False)

    skill = build_skill_table(data)
    skill.to_csv(SKILL_FILE, index=False)
    event_errors, barrier = build_barrier_tables(data)
    event_errors.to_csv(EVENT_ERROR_FILE, index=False)
    barrier.to_csv(BARRIER_FILE, index=False)
    sensitivity = barrier_sensitivity(data)
    sensitivity.to_csv(SENSITIVITY_FILE, index=False)
    correlations = predictor_correlations(data)
    correlations.to_csv(LINK_FILE, index=False)

    mm_events = event_errors[event_errors.model == "nmme"]
    bootstrap = bootstrap_barrier_difference(mm_events)
    diagnostics = {
        "data_source": "NOAA CPC NMME seasonal SST hindcasts in CPT format",
        "verification": str(ERSST_FILE),
        "hindcast_years": [1991, 2020],
        "forecast_files": int(
            data[["model", "init_month", "target_season"]].drop_duplicates().shape[0]
        ),
        "models": sorted(data.model.unique().tolist()),
        "warm_event_group_counts": (
            data[
                (data.model == "nmme")
                & (data.target_season == "SON")
                & (data.init_month == 3)
                & data.is_warm_event
            ]["enso_type_group"]
            .value_counts()
            .to_dict()
        ),
        "individual_models_with_ep_penalty_greater_than_cp": int(
            (
                barrier.pivot(
                    index="model",
                    columns="enso_type_group",
                    values="spring_penalty_mean_c",
                )
                .drop(index="nmme", errors="ignore")
                .dropna(subset=["EP", "CP"])
                .eval("EP > CP")
            ).sum()
        ),
        "validation": validation,
        "bootstrap": bootstrap,
    }
    DIAGNOSTICS_FILE.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    plot_main(data, skill, event_errors, barrier)
    plot_skill_heatmaps(skill)
    plot_event_forecasts(data)
    write_report(skill, event_errors, barrier, correlations, sensitivity, bootstrap)

    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    print(ROOT / "reports" / "NMME_EP_CP春季预报障碍分析.md")


if __name__ == "__main__":
    main()
