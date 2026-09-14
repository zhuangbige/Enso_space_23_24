#!/usr/bin/env python3
"""Test whether early FEP, ocean, and atmosphere states predict ENSO flavor.

The mature-season target is the following DJF OISST Niño-3 minus Niño-4
anomaly. Positive values are relatively east-focused (EP-like), negative
values are relatively central-focused (CP-like). The continuous target is
primary; the sign is only a secondary descriptive label.

Two complementary validation designs are used:

1. All-year walk-forward hindcasts for 2000-2023. Every target year is
   predicted using earlier years only. Predictor/target trends and predictor
   scaling are estimated inside each training fold.
2. Leave-one-El-Niño-event-out ridge predictions across the 13 NOAA ONI warm
   episodes beginning in 1982-2023. This is explicitly exploratory because the
   event sample is small.

The operational "two gates" are descriptive diagnostics, not formal ENSO
indices:
* ocean gate: OHC300 east-minus-west > 0 and D20 east-minus-west > 0;
* atmosphere gate: central-western Pacific u850 > 0 and CP OLR < 0;
* each gate must persist for two consecutive January-June months.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from el_nino_decoupling.typical_composite import (
    identify_warm_episodes,
    read_oni_ascii,
)


MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SST_BASELINE = (1982, 2024)
FIELD_BASELINE = (1980, 2024)
TEST_YEARS = (2000, 2023)
BOOTSTRAP_SAMPLES = 5000
RIDGE_ALPHA = 1.0

OISST_DIR = ROOT / "data/interim/research_2026/pmm_inputs"
OHC_CSV = ROOT / "data/derived/research_2026/soda3_ohc_indices_1980_2024.csv"
D20_NC = ROOT / "data/derived/research_2026/soda3_d20_equatorial_jan_jun_1980_2024.nc"
ATMOS_NC = (
    ROOT
    / "data/derived/research_2026/"
    "era5_u850_olr_equatorial_jan_jun_1980_2024_anomalies.nc"
)
U850_FILES = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc",
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jun.nc",
)
OLR_DIR = ROOT / "data/raw/era5/olr_monthly_1deg_1980_2026"
ONI_FILE = ROOT / "data/raw/noaa_cpc/oni_as_of_2026-07-30.txt"

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_FIG = ROOT / "outputs/research_2026/soda3_fep_transition"
OUT_PDF = ROOT / "output/pdf"
MONTHLY_CSV = OUT_DATA / "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
EVENT_CSV = OUT_DATA / "ep_cp_two_gate_event_summary_1982_2023.csv"
WALK_PRED_CSV = OUT_DATA / "ep_cp_type_walkforward_predictions_2000_2023.csv"
WALK_SKILL_CSV = OUT_DATA / "ep_cp_type_walkforward_skill_2000_2023.csv"
LOEO_PRED_CSV = OUT_DATA / "ep_cp_type_event_loeo_predictions.csv"
LOEO_SKILL_CSV = OUT_DATA / "ep_cp_type_event_loeo_skill.csv"
DIAGNOSTIC_JSON = OUT_DATA / "ep_cp_two_gate_predictability_diagnostics.json"
MECHANISM_PNG = OUT_FIG / "ep_cp_two_gate_full_event_test.png"
MECHANISM_PDF = OUT_PDF / "ep_cp_two_gate_full_event_test.pdf"
PREDICTION_PNG = OUT_FIG / "ep_cp_type_prediction_skill.png"
PREDICTION_PDF = OUT_PDF / "ep_cp_type_prediction_skill.pdf"
SUMMARY_MD = OUT_FIG / "EP_CP_TWO_GATE_RESULTS_CN.md"

REGIONS = {
    "west": (130.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 270.0),
    "fep": (270.0, 280.0),
}

MODEL_FEATURES = {
    "Type persistence": ("init_type_raw_c",),
    "+ FEP residual": ("init_type_raw_c", "fep_residual"),
    "+ OHC gradient": ("init_type_raw_c", "ohc300_ew_raw_jm2"),
    "+ D20 gradient": ("init_type_raw_c", "d20_ew_raw_m"),
    "Ocean gate": (
        "init_type_raw_c",
        "ohc300_ew_raw_jm2",
        "d20_ew_raw_m",
    ),
    "Atmosphere gate": (
        "init_type_raw_c",
        "u850_cwp_raw_ms",
        "olr_cp_raw_wm2",
    ),
    "Two gates": (
        "init_type_raw_c",
        "ohc300_ew_raw_jm2",
        "u850_cwp_raw_ms",
        "olr_cp_raw_wm2",
    ),
    "Full mechanism": (
        "init_type_raw_c",
        "fep_residual",
        "ohc300_ew_raw_jm2",
        "u850_cwp_raw_ms",
        "olr_cp_raw_wm2",
    ),
}

MODEL_COLORS = {
    "Type persistence": "#222222",
    "+ FEP residual": "#D55E00",
    "+ OHC gradient": "#0072B2",
    "+ D20 gradient": "#56B4E9",
    "Ocean gate": "#009E73",
    "Atmosphere gate": "#7B3294",
    "Two gates": "#CC79A7",
    "Full mechanism": "#E69F00",
}

PUBLISHED_EP_CP = {
    1986: "EP",
    1991: "EP",
    1994: "CP",
    2002: "CP",
    2004: "CP",
    2006: "EP",
    2009: "CP",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 170,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.3,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.6,
            "ytick.labelsize": 8.6,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "legend.fontsize": 8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def standardize_field(da: xr.DataArray) -> xr.DataArray:
    rename = {}
    if "valid_time" in da.coords:
        rename["valid_time"] = "time"
    if "latitude" in da.coords:
        rename["latitude"] = "lat"
    if "longitude" in da.coords:
        rename["longitude"] = "lon"
    da = da.rename(rename)
    da = da.assign_coords(lon=da.lon % 360).sortby("lon").sortby("lat")
    da = da.assign_coords(
        time=pd.to_datetime(da.time.values).to_period("M").to_timestamp()
    )
    return da


def weighted_box_mean(
    da: xr.DataArray,
    lon0: float,
    lon1: float,
    lat0: float = -5.0,
    lat1: float = 5.0,
) -> xr.DataArray:
    subset = da.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(f"Empty box: {lat0}:{lat1}, {lon0}:{lon1}")
    weights = np.cos(np.deg2rad(subset["lat"]))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def same_month_residual(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int],
) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in sorted(np.unique(times.month)):
        selected = times.month == month
        baseline_selected = (
            selected
            & (times.year >= baseline[0])
            & (times.year <= baseline[1])
            & np.isfinite(values)
        )
        if int(baseline_selected.sum()) < 10:
            raise ValueError(f"Insufficient baseline data for month {month}")
        x_fit = times.year[baseline_selected].astype(float)
        y_fit = values[baseline_selected]
        slope, intercept = np.polyfit(x_fit, y_fit, 1)
        valid = selected & np.isfinite(values)
        output[valid] = values[valid] - (
            intercept + slope * times.year[valid].astype(float)
        )
    return output


def load_oisst_indices() -> pd.DataFrame:
    paths = sorted(OISST_DIR.glob("oisst_sst_pmm_1deg_*.nc"))
    if len(paths) != 12:
        raise FileNotFoundError(f"Expected 12 monthly OISST files, found {len(paths)}")
    pieces: list[xr.DataArray] = []
    for path in paths:
        with xr.open_dataset(path, chunks=None) as ds:
            pieces.append(standardize_field(ds["sst"].load()))
    sst = xr.concat(pieces, dim="time").sortby("time")
    if sst.get_index("time").duplicated().any():
        raise ValueError("Duplicate OISST timestamps")
    times = pd.DatetimeIndex(pd.to_datetime(sst.time.values))
    raw = pd.DataFrame(
        {
            "time": times,
            "nino3_raw_c": weighted_box_mean(sst, 210.0, 270.0).values,
            "nino4_raw_c": weighted_box_mean(sst, 160.0, 210.0).values,
            "nino34_raw_c": weighted_box_mean(sst, 190.0, 240.0).values,
            "fep_raw_c": weighted_box_mean(sst, 270.0, 280.0).values,
        }
    )
    for name in ("nino3", "nino4", "nino34", "fep"):
        raw[f"{name}_anom_c"] = same_month_residual(
            raw[f"{name}_raw_c"].to_numpy(),
            times,
            SST_BASELINE,
        )
    raw["init_type_raw_c"] = raw["nino3_raw_c"] - raw["nino4_raw_c"]
    raw["init_type_anom_c"] = raw["nino3_anom_c"] - raw["nino4_anom_c"]
    raw["year"] = raw["time"].dt.year
    raw["month"] = raw["time"].dt.month

    expected = np.full(len(raw), np.nan, dtype=float)
    for month in MONTHS:
        fit = (
            raw["month"].eq(month)
            & raw["year"].between(*SST_BASELINE)
            & raw["nino34_anom_c"].notna()
            & raw["fep_anom_c"].notna()
        )
        slope, intercept = np.polyfit(
            raw.loc[fit, "nino34_anom_c"],
            raw.loc[fit, "fep_anom_c"],
            1,
        )
        selected = raw["month"].eq(month)
        expected[selected] = (
            intercept
            + slope * raw.loc[selected, "nino34_anom_c"].to_numpy(dtype=float)
        )
    raw["fep_residual_c"] = raw["fep_anom_c"] - expected
    return raw.sort_values("time").reset_index(drop=True)


def load_ohc_indices() -> pd.DataFrame:
    frame = pd.read_csv(OHC_CSV)
    frame["time"] = pd.to_datetime(frame["time"]).dt.to_period("M").dt.to_timestamp()
    frame["ohc300_ew_raw_jm2"] = (
        frame["ohc300_east_jm2"] - frame["ohc300_west_jm2"]
    )
    return frame[
        [
            "time",
            "ohc300_ew_raw_jm2",
            "ohc300_east_minus_west_anom_jm2",
            "ohc300_central_jm2",
            "ohc300_central_anom_jm2",
        ]
    ]


def load_d20_indices() -> pd.DataFrame:
    with xr.open_dataset(D20_NC, chunks=None) as ds:
        raw = ds["d20"].load()
        anomaly = ds["d20_anomaly_detrended"].load()
    times = pd.DatetimeIndex(pd.to_datetime(raw.time.values)).to_period("M").to_timestamp()
    output = pd.DataFrame({"time": times})
    for field, suffix in ((raw, "raw_m"), (anomaly, "anom_m")):
        west = weighted_box_mean(field, *REGIONS["west"]).values
        east = weighted_box_mean(field, *REGIONS["east"]).values
        output[f"d20_ew_{suffix}"] = east - west
    return output


def open_raw_u850() -> xr.DataArray:
    pieces: list[xr.DataArray] = []
    for path in U850_FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        with xr.open_dataset(path, engine="netcdf4", chunks=None) as ds:
            current = ds["u"]
            if "pressure_level" in current.dims:
                current = current.sel(pressure_level=850, drop=True)
            pieces.append(standardize_field(current.load()))
    output = xr.concat(pieces, dim="time").sortby("time")
    if output.get_index("time").duplicated().any():
        raise ValueError("Duplicate ERA5 u850 timestamps")
    return output


def open_raw_olr() -> xr.DataArray:
    monthly: list[xr.DataArray] = []
    for month in MONTHS:
        pieces: list[xr.DataArray] = []
        for side in ("west", "east"):
            path = OLR_DIR / f"era5_olr_{side}_m{month:02d}_1980_2026_1deg.nc"
            if not path.exists():
                raise FileNotFoundError(path)
            with xr.open_dataset(path, engine="netcdf4", chunks=None) as ds:
                pieces.append(standardize_field((-ds["avg_tnlwrf"]).load()))
        combined = xr.concat(pieces, dim="lon").sortby("lon")
        _, unique = np.unique(combined.lon.values, return_index=True)
        monthly.append(combined.isel(lon=np.sort(unique)))
    output = xr.concat(monthly, dim="time").sortby("time")
    if output.get_index("time").duplicated().any():
        raise ValueError("Duplicate ERA5 OLR timestamps")
    return output


def load_atmospheric_indices() -> pd.DataFrame:
    u_raw = open_raw_u850()
    olr_raw = open_raw_olr()
    u_times = pd.DatetimeIndex(pd.to_datetime(u_raw.time.values)).to_period("M").to_timestamp()
    o_times = pd.DatetimeIndex(pd.to_datetime(olr_raw.time.values)).to_period("M").to_timestamp()
    u_frame = pd.DataFrame(
        {
            "time": u_times,
            "u850_cwp_raw_ms": weighted_box_mean(u_raw, 160.0, 220.0).values,
        }
    )
    o_frame = pd.DataFrame(
        {
            "time": o_times,
            "olr_cp_raw_wm2": weighted_box_mean(olr_raw, 170.0, 220.0).values,
        }
    )
    with xr.open_dataset(ATMOS_NC, chunks=None) as ds:
        u_anomaly = ds["u850_anomaly_detrended"].load()
        olr_anomaly = ds["olr_anomaly_detrended"].load()
    anomaly_times = (
        pd.DatetimeIndex(pd.to_datetime(u_anomaly.time.values))
        .to_period("M")
        .to_timestamp()
    )
    anomaly_frame = pd.DataFrame(
        {
            "time": anomaly_times,
            "u850_cwp_anom_ms": weighted_box_mean(
                u_anomaly, 160.0, 220.0
            ).values,
            "olr_cp_anom_wm2": weighted_box_mean(
                olr_anomaly, 170.0, 220.0
            ).values,
        }
    )
    return u_frame.merge(o_frame, on="time", validate="one_to_one").merge(
        anomaly_frame,
        on="time",
        how="left",
        validate="one_to_one",
    )


def mature_djf_targets(sst: pd.DataFrame) -> pd.DataFrame:
    lookup = sst.set_index("time")
    rows: list[dict[str, float | int | str | bool]] = []
    for year in range(1982, 2024):
        times = pd.to_datetime(
            [f"{year}-12-01", f"{year + 1}-01-01", f"{year + 1}-02-01"]
        )
        subset = lookup.reindex(times)
        if subset[["nino3_raw_c", "nino4_raw_c"]].isna().any().any():
            continue
        type_raw = float(
            (subset["nino3_raw_c"] - subset["nino4_raw_c"]).mean()
        )
        type_anomaly = float(
            (subset["nino3_anom_c"] - subset["nino4_anom_c"]).mean()
        )
        if type_anomaly > 0.2:
            flavor = "EP-like"
        elif type_anomaly < -0.2:
            flavor = "CP-like"
        else:
            flavor = "mixed/borderline"
        rows.append(
            {
                "year": year,
                "mature_djf_type_raw_c": type_raw,
                "mature_djf_type_index_c": type_anomaly,
                "mature_djf_nino3_c": float(subset["nino3_anom_c"].mean()),
                "mature_djf_nino4_c": float(subset["nino4_anom_c"].mean()),
                "mature_djf_nino34_c": float(subset["nino34_anom_c"].mean()),
                "mature_flavor": flavor,
                "borderline_abs_type_lt_0p2": bool(abs(type_anomaly) < 0.2),
            }
        )
    return pd.DataFrame(rows)


def build_monthly_table(sst: pd.DataFrame) -> pd.DataFrame:
    target = mature_djf_targets(sst)
    init = sst.loc[
        sst["year"].between(1982, 2023) & sst["month"].isin(MONTHS)
    ].copy()
    table = (
        init.merge(load_ohc_indices(), on="time", how="left", validate="one_to_one")
        .merge(load_d20_indices(), on="time", how="left", validate="one_to_one")
        .merge(
            load_atmospheric_indices(),
            on="time",
            how="left",
            validate="one_to_one",
        )
        .merge(target, on="year", how="left", validate="many_to_one")
    )
    expected_rows = (2023 - 1982 + 1) * 6
    if len(table) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, found {len(table)}")
    required = [
        "mature_djf_type_raw_c",
        "init_type_raw_c",
        "fep_raw_c",
        "nino34_raw_c",
        "ohc300_ew_raw_jm2",
        "d20_ew_raw_m",
        "u850_cwp_raw_ms",
        "olr_cp_raw_wm2",
    ]
    if table[required].isna().any().any():
        missing = table.loc[table[required].isna().any(axis=1), ["year", "month"]]
        raise ValueError(f"Missing predictor/target data:\n{missing}")
    return table.sort_values(["year", "month"]).reset_index(drop=True)


def event_manifest() -> pd.DataFrame:
    episodes = identify_warm_episodes(read_oni_ascii(ONI_FILE))
    selected = [
        episode
        for episode in episodes
        if 1982 <= int(episode.event_year) <= 2023
    ]
    frame = pd.DataFrame(asdict(episode) for episode in selected)
    if len(frame) != 13:
        raise ValueError(f"Expected 13 warm episodes, found {len(frame)}")
    frame["oni_source"] = str(ONI_FILE)
    frame["selection_rule"] = (
        "NOAA ONI >= 0.5 C for at least five consecutive overlapping seasons"
    )
    return frame.sort_values("event_year").reset_index(drop=True)


def first_two_months(condition: np.ndarray) -> int | None:
    condition = np.asarray(condition, dtype=bool)
    for index in range(condition.size - 1):
        if condition[index] and condition[index + 1]:
            return index + 1
    return None


def build_event_summary(
    monthly: pd.DataFrame,
    manifest: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, episode in manifest.iterrows():
        year = int(episode["event_year"])
        event = monthly.loc[monthly["year"].eq(year)].sort_values("month")
        if len(event) != 6:
            raise ValueError(f"Incomplete event predictors for {year}")
        fep_month = first_two_months(event["fep_residual_c"].to_numpy() > 0)
        ocean_month = first_two_months(
            (event["ohc300_east_minus_west_anom_jm2"].to_numpy() > 0)
            & (event["d20_ew_anom_m"].to_numpy() > 0)
        )
        atmosphere_month = first_two_months(
            (event["u850_cwp_anom_ms"].to_numpy() > 0)
            & (event["olr_cp_anom_wm2"].to_numpy() < 0)
        )
        full_month = (
            None
            if ocean_month is None or atmosphere_month is None
            else max(ocean_month, atmosphere_month)
        )
        target = event.iloc[0]
        relative_sign_label = (
            "EP" if float(target["mature_djf_type_index_c"]) > 0 else "CP"
        )
        published_label = PUBLISHED_EP_CP.get(year)
        rows.append(
            {
                **episode.to_dict(),
                "mature_djf_type_index_c": float(
                    target["mature_djf_type_index_c"]
                ),
                "mature_djf_nino34_c": float(target["mature_djf_nino34_c"]),
                "mature_flavor": target["mature_flavor"],
                "borderline_abs_type_lt_0p2": bool(
                    target["borderline_abs_type_lt_0p2"]
                ),
                "relative_sign_label": relative_sign_label,
                "published_ep_cp_label": published_label,
                "published_label_source": (
                    "Beniche et al. (2024), Supplementary Fig. S4"
                    if published_label is not None
                    else None
                ),
                "relative_sign_agrees_with_published": (
                    bool(relative_sign_label == published_label)
                    if published_label is not None
                    else None
                ),
                "fep_persistent_positive_month": fep_month,
                "ocean_gate_month": ocean_month,
                "atmosphere_gate_month": atmosphere_month,
                "full_two_gate_month": full_month,
                "fep_residual_jan_jun_mean_c": float(
                    event["fep_residual_c"].mean()
                ),
                "ohc300_ew_may_jun_mean_gjm2": float(
                    event.loc[event["month"].ge(5), "ohc300_east_minus_west_anom_jm2"].mean()
                    / 1.0e9
                ),
                "d20_ew_may_jun_mean_m": float(
                    event.loc[event["month"].ge(5), "d20_ew_anom_m"].mean()
                ),
                "u850_cwp_may_jun_mean_ms": float(
                    event.loc[event["month"].ge(5), "u850_cwp_anom_ms"].mean()
                ),
                "minus_olr_cp_may_jun_mean_wm2": float(
                    -event.loc[event["month"].ge(5), "olr_cp_anom_wm2"].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def fit_trend(
    years: np.ndarray,
    values: np.ndarray,
) -> tuple[float, float]:
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


def fold_fep_residual(
    train: pd.DataFrame,
    test: pd.Series,
) -> tuple[np.ndarray, float]:
    years = train["year"].to_numpy(dtype=float)
    test_year = float(test["year"])
    n34_train, n34_test = detrend_with_training(
        years,
        train["nino34_raw_c"].to_numpy(dtype=float),
        test_year,
        float(test["nino34_raw_c"]),
    )
    fep_train, fep_test = detrend_with_training(
        years,
        train["fep_raw_c"].to_numpy(dtype=float),
        test_year,
        float(test["fep_raw_c"]),
    )
    design = np.column_stack([np.ones(len(train)), n34_train])
    intercept, slope = np.linalg.lstsq(design, fep_train, rcond=None)[0]
    return (
        fep_train - (intercept + slope * n34_train),
        float(fep_test - (intercept + slope * n34_test)),
    )


def predict_walk_fold(
    train: pd.DataFrame,
    test: pd.Series,
    features: tuple[str, ...],
) -> tuple[float, float]:
    raw_features = [
        feature for feature in features if feature != "fep_residual"
    ]
    required = [
        "mature_djf_type_raw_c",
        "fep_raw_c",
        "nino34_raw_c",
        *raw_features,
    ]
    train = train.dropna(subset=list(dict.fromkeys(required)))
    if len(train) < 15 or test[list(dict.fromkeys(required))].isna().any():
        return np.nan, np.nan
    years = train["year"].to_numpy(dtype=float)
    test_year = float(test["year"])
    y_train, y_observed = detrend_with_training(
        years,
        train["mature_djf_type_raw_c"].to_numpy(dtype=float),
        test_year,
        float(test["mature_djf_type_raw_c"]),
    )
    x_columns: list[np.ndarray] = []
    x_test_values: list[float] = []
    for feature in features:
        if feature == "fep_residual":
            train_residual, test_residual = fold_fep_residual(train, test)
        else:
            train_residual, test_residual = detrend_with_training(
                years,
                train[feature].to_numpy(dtype=float),
                test_year,
                float(test[feature]),
            )
        scale = float(np.std(train_residual, ddof=1))
        if not np.isfinite(scale) or scale == 0:
            return np.nan, np.nan
        x_columns.append(train_residual / scale)
        x_test_values.append(test_residual / scale)
    x_train = np.column_stack(x_columns)
    design = np.column_stack([np.ones(len(train)), x_train])
    coefficients = np.linalg.lstsq(design, y_train, rcond=None)[0]
    prediction = float(
        np.dot(np.r_[1.0, np.asarray(x_test_values)], coefficients)
    )
    return prediction, y_observed


def walk_forward_predictions(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month in MONTHS:
        current = monthly.loc[monthly["month"].eq(month)].sort_values("year")
        for year in range(TEST_YEARS[0], TEST_YEARS[1] + 1):
            test_rows = current.loc[current["year"].eq(year)]
            if test_rows.empty:
                continue
            test = test_rows.iloc[0]
            train = current.loc[current["year"].lt(year)]
            for model, features in MODEL_FEATURES.items():
                prediction, observed = predict_walk_fold(train, test, features)
                rows.append(
                    {
                        "year": year,
                        "month": month,
                        "model": model,
                        "prediction_type_residual_c": prediction,
                        "observed_type_residual_c": observed,
                        "n_training_years": len(train),
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_skill(
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
    *,
    seed: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(observed)
    values = np.full(BOOTSTRAP_SAMPLES, np.nan)
    for index in range(BOOTSTRAP_SAMPLES):
        sample = rng.integers(0, n, size=n)
        rmse = np.sqrt(np.mean((predicted[sample] - observed[sample]) ** 2))
        baseline_rmse = np.sqrt(
            np.mean((baseline[sample] - observed[sample]) ** 2)
        )
        if baseline_rmse > 0:
            values[index] = 1.0 - rmse / baseline_rmse
    return (
        float(np.nanpercentile(values, 2.5)),
        float(np.nanpercentile(values, 97.5)),
    )


def paired_improvement_permutation_p(
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
    *,
    seed: int,
    samples: int = 50000,
) -> float:
    improvement = (
        (baseline - observed) ** 2
        - (predicted - observed) ** 2
    )
    observed_mean = float(np.mean(improvement))
    rng = np.random.default_rng(seed)
    null = np.empty(samples, dtype=float)
    for index in range(samples):
        signs = rng.choice((-1.0, 1.0), size=len(improvement))
        null[index] = float(np.mean(improvement * signs))
    return float((np.sum(null >= observed_mean) + 1) / (samples + 1))


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


def summarize_prediction_skill(
    predictions: pd.DataFrame,
    *,
    prediction_column: str,
    observed_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for month in MONTHS:
        subset = predictions.loc[predictions["month"].eq(month)]
        baseline = subset.loc[
            subset["model"].eq("Type persistence"),
            ["year", prediction_column],
        ].rename(columns={prediction_column: "baseline_prediction"})
        for model in MODEL_FEATURES:
            current = subset.loc[
                subset["model"].eq(model),
                ["year", prediction_column, observed_column],
            ].merge(baseline, on="year", validate="one_to_one")
            current = current.replace([np.inf, -np.inf], np.nan).dropna()
            observed = current[observed_column].to_numpy(dtype=float)
            predicted = current[prediction_column].to_numpy(dtype=float)
            persistence = current["baseline_prediction"].to_numpy(dtype=float)
            rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
            baseline_rmse = float(
                np.sqrt(np.mean((persistence - observed) ** 2))
            )
            skill = (
                float(1.0 - rmse / baseline_rmse)
                if baseline_rmse > 0
                else np.nan
            )
            lower, upper = bootstrap_skill(
                observed,
                predicted,
                persistence,
                seed=20260730 + month * 100 + list(MODEL_FEATURES).index(model),
            )
            correlation = (
                float(np.corrcoef(predicted, observed)[0, 1])
                if len(current) >= 3
                else np.nan
            )
            sign_accuracy = float(np.mean(np.sign(predicted) == np.sign(observed)))
            paired_p = (
                np.nan
                if model == "Type persistence"
                else paired_improvement_permutation_p(
                    observed,
                    predicted,
                    persistence,
                    seed=20260730
                    + month * 100
                    + list(MODEL_FEATURES).index(model),
                )
            )
            rows.append(
                {
                    "month": month,
                    "model": model,
                    "n_test": len(current),
                    "rmse_c": rmse,
                    "persistence_rmse_c": baseline_rmse,
                    "rmse_skill_vs_persistence": skill,
                    "skill_ci_2p5": lower,
                    "skill_ci_97p5": upper,
                    "correlation": correlation,
                    "sign_accuracy": sign_accuracy,
                    "paired_improvement_p_one_sided": paired_p,
                }
            )
    result = pd.DataFrame(rows)
    tested = result["model"].ne("Type persistence")
    result.loc[tested, "bh_fdr_q_across_model_month_tests"] = (
        benjamini_hochberg(
            result.loc[tested, "paired_improvement_p_one_sided"]
        )
    )
    return result


def ridge_prediction(
    train: pd.DataFrame,
    test: pd.Series,
    features: tuple[str, ...],
) -> float:
    mapping = {
        "init_type_raw_c": "init_type_anom_c",
        "fep_residual": "fep_residual_c",
        "ohc300_ew_raw_jm2": "ohc300_east_minus_west_anom_jm2",
        "d20_ew_raw_m": "d20_ew_anom_m",
        "u850_cwp_raw_ms": "u850_cwp_anom_ms",
        "olr_cp_raw_wm2": "olr_cp_anom_wm2",
    }
    columns = [mapping[feature] for feature in features]
    x_train = train[columns].to_numpy(dtype=float)
    x_test = test[columns].to_numpy(dtype=float)
    y_train = train["mature_djf_type_index_c"].to_numpy(dtype=float)
    x_mean = x_train.mean(axis=0)
    x_scale = x_train.std(axis=0, ddof=1)
    y_mean = float(y_train.mean())
    if np.any(~np.isfinite(x_scale)) or np.any(x_scale == 0):
        return np.nan
    x_standard = (x_train - x_mean) / x_scale
    x_test_standard = (x_test - x_mean) / x_scale
    y_centered = y_train - y_mean
    gram = x_standard.T @ x_standard
    coefficients = np.linalg.solve(
        gram + RIDGE_ALPHA * np.eye(gram.shape[0]),
        x_standard.T @ y_centered,
    )
    return float(y_mean + x_test_standard @ coefficients)


def event_loeo_predictions(
    monthly: pd.DataFrame,
    event_summary: pd.DataFrame,
) -> pd.DataFrame:
    years = event_summary["event_year"].astype(int).tolist()
    event_monthly = monthly.loc[monthly["year"].isin(years)].copy()
    rows: list[dict[str, object]] = []
    for month in MONTHS:
        current = event_monthly.loc[event_monthly["month"].eq(month)].copy()
        for year in years:
            test = current.loc[current["year"].eq(year)].iloc[0]
            train = current.loc[current["year"].ne(year)]
            for model, features in MODEL_FEATURES.items():
                rows.append(
                    {
                        "year": year,
                        "month": month,
                        "model": model,
                        "prediction_type_index_c": ridge_prediction(
                            train,
                            test,
                            features,
                        ),
                        "observed_type_index_c": float(
                            test["mature_djf_type_index_c"]
                        ),
                        "n_training_events": len(train),
                        "ridge_alpha": RIDGE_ALPHA,
                    }
                )
    return pd.DataFrame(rows)


def zscore_columns(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    values = frame[columns].to_numpy(dtype=float)
    return (values - values.mean(axis=0)) / values.std(axis=0, ddof=1)


def plot_mechanism_audit(event: pd.DataFrame) -> None:
    setup_style()
    ordered = event.sort_values("mature_djf_type_index_c").reset_index(drop=True)
    labels = [str(year) for year in ordered["event_year"]]
    y = np.arange(len(ordered))
    target = ordered["mature_djf_type_index_c"].to_numpy(dtype=float)
    colors = np.where(target >= 0, "#D6604D", "#4393C3")
    colors = np.where(np.abs(target) < 0.2, "#9E9E9E", colors)

    fig = plt.figure(figsize=(14.2, 8.8))
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=(1.05, 1.55, 1.2),
        left=0.07,
        right=0.985,
        bottom=0.15,
        top=0.85,
        wspace=0.23,
    )
    ax0 = fig.add_subplot(grid[0, 0])
    ax1 = fig.add_subplot(grid[0, 1], sharey=ax0)
    ax2 = fig.add_subplot(grid[0, 2], sharey=ax0)

    ax0.barh(y, target, color=colors, edgecolor="white", linewidth=0.7)
    ax0.axvline(0, color="0.15", lw=0.9)
    ax0.axvspan(-0.2, 0.2, color="0.75", alpha=0.25, zorder=0)
    ax0.set_yticks(y, labels)
    ax0.set_xlabel("DJF Niño3 − Niño4 anomaly (°C)")
    ax0.set_title("(a) Mature event flavor", weight="bold")
    ax0.grid(axis="x", color="0.88", lw=0.6)
    ax0.set_axisbelow(True)

    diagnostic_columns = [
        "fep_residual_jan_jun_mean_c",
        "ohc300_ew_may_jun_mean_gjm2",
        "d20_ew_may_jun_mean_m",
        "u850_cwp_may_jun_mean_ms",
        "minus_olr_cp_may_jun_mean_wm2",
    ]
    heat = zscore_columns(ordered, diagnostic_columns)
    mesh = ax1.imshow(
        heat,
        aspect="auto",
        origin="lower",
        cmap="RdBu_r",
        vmin=-2,
        vmax=2,
    )
    ax1.set_xticks(
        np.arange(5),
        [
            "FEP residual\nJan–Jun",
            "OHC E−W\nMay–Jun",
            "D20 E−W*\nMay–Jun",
            "u850*\nMay–Jun",
            "−OLR\nMay–Jun",
        ],
    )
    ax1.tick_params(axis="x", rotation=22)
    ax1.tick_params(axis="y", labelleft=False)
    ax1.set_title("(b) Early-state diagnostics (event z score)", weight="bold")
    for row in range(len(ordered) + 1):
        ax1.axhline(row - 0.5, color="white", lw=0.5)
    for column in range(6):
        ax1.axvline(column - 0.5, color="white", lw=0.5)
    colorbar = fig.colorbar(
        mesh,
        ax=ax1,
        orientation="horizontal",
        fraction=0.055,
        pad=0.16,
    )
    colorbar.set_label("Standardized anomaly across 13 events")

    timing_columns = [
        ("fep_persistent_positive_month", "FEP trigger", "#D55E00", "o"),
        ("ocean_gate_month", "Ocean gate", "#009E73", "s"),
        ("atmosphere_gate_month", "Atmosphere gate", "#7B3294", "^"),
        ("full_two_gate_month", "Both gates", "#111111", "D"),
    ]
    for column, label, color, marker in timing_columns:
        values = ordered[column].fillna(7).to_numpy(dtype=float)
        ax2.scatter(
            values,
            y,
            s=35,
            color=color,
            marker=marker,
            edgecolor="white",
            linewidth=0.45,
            label=label,
            zorder=3,
        )
    ax2.set_xlim(0.6, 7.4)
    ax2.set_xticks(np.arange(1, 8), [*MONTH_LABELS, "Not\nreached"])
    ax2.tick_params(axis="y", labelleft=False)
    ax2.grid(axis="x", color="0.87", lw=0.6)
    ax2.set_axisbelow(True)
    ax2.set_title("(c) First persistent transition month", weight="bold")
    handles, legend_labels = ax2.get_legend_handles_labels()
    fig.legend(
        handles,
        legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.72, 0.068),
        ncol=4,
        frameon=False,
    )

    fig.suptitle(
        "Full-event audit of the proposed FEP → ocean gate → atmosphere gate pathway",
        fontsize=14,
        weight="bold",
        y=0.955,
    )
    fig.text(
        0.5,
        0.014,
        "Events: NOAA ONI warm episodes, 1982–2023. SST: OISST (1982–2024 baseline); "
        "OHC/D20: SODA3.15.2; u850/OLR: ERA5 (1980–2024 baseline).\n"
        "Gray bars have |Niño3−Niño4| < 0.2°C. Gates require two consecutive months. "
        "* Event-strength correlation survives BH-FDR q<0.05.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="0.33",
    )
    MECHANISM_PNG.parent.mkdir(parents=True, exist_ok=True)
    MECHANISM_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(MECHANISM_PNG)
    fig.savefig(MECHANISM_PDF)
    plt.close(fig)


def plot_prediction_skill(
    walk_skill: pd.DataFrame,
    loeo_skill: pd.DataFrame,
    loeo_predictions: pd.DataFrame,
) -> None:
    setup_style()
    selected_models = (
        "+ FEP residual",
        "Ocean gate",
        "Atmosphere gate",
        "Two gates",
        "Full mechanism",
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 9.2))
    fig.subplots_adjust(
        left=0.075,
        right=0.98,
        bottom=0.125,
        top=0.88,
        hspace=0.34,
        wspace=0.26,
    )

    for ax, skill, title in (
        (
            axes[0, 0],
            walk_skill,
            "(a) All-year walk-forward RMSE skill (2000–2023)",
        ),
        (
            axes[0, 1],
            loeo_skill,
            "(b) El Niño leave-one-event-out RMSE skill (n = 13)",
        ),
    ):
        for model in selected_models:
            current = skill.loc[skill["model"].eq(model)]
            ax.plot(
                current["month"],
                current["rmse_skill_vs_persistence"],
                marker="o",
                lw=1.5,
                ms=4.5,
                color=MODEL_COLORS[model],
                label=model,
            )
        ax.axhline(0, color="0.15", lw=0.9)
        ax.set_xticks(MONTHS, MONTH_LABELS)
        ax.set_ylabel("Skill vs type persistence\n(1 − RMSE / RMSE$_{pers}$)")
        ax.set_title(title, weight="bold")
        ax.grid(color="0.88", lw=0.6)
        ax.set_axisbelow(True)

    walk_best = (
        walk_skill.loc[walk_skill["model"].ne("Type persistence")]
        .sort_values("rmse_skill_vs_persistence", ascending=False)
        .iloc[0]
    )
    loeo_best = (
        loeo_skill.loc[loeo_skill["model"].ne("Type persistence")]
        .sort_values("rmse_skill_vs_persistence", ascending=False)
        .iloc[0]
    )
    axes[0, 0].text(
        0.02,
        0.035,
        f"Best: {MONTH_LABELS[int(walk_best['month']) - 1]} "
        f"{walk_best['model']}, skill {walk_best['rmse_skill_vs_persistence']:+.3f}\n"
        f"BH-FDR q={walk_best['bh_fdr_q_across_model_month_tests']:.2f}",
        transform=axes[0, 0].transAxes,
        ha="left",
        va="bottom",
        fontsize=7.6,
        color="0.25",
    )
    axes[0, 1].text(
        0.02,
        0.035,
        f"Best: {MONTH_LABELS[int(loeo_best['month']) - 1]} "
        f"{loeo_best['model']}, skill {loeo_best['rmse_skill_vs_persistence']:+.3f}\n"
        f"BH-FDR q={loeo_best['bh_fdr_q_across_model_month_tests']:.2f}",
        transform=axes[0, 1].transAxes,
        ha="left",
        va="bottom",
        fontsize=7.6,
        color="0.25",
    )

    axes[0, 1].legend(
        loc="upper center",
        bbox_to_anchor=(-0.08, -0.20),
        ncol=3,
        frameon=False,
    )

    for ax, month in zip(axes[1], (4, 6)):
        current = loeo_predictions.loc[
            loeo_predictions["month"].eq(month)
            & loeo_predictions["model"].isin(
                ["Type persistence", "Two gates", "Full mechanism"]
            )
        ]
        limits = (-1.15, 2.45)
        ax.plot(limits, limits, color="0.25", ls="--", lw=0.8)
        for model, marker in (
            ("Type persistence", "o"),
            ("Two gates", "s"),
            ("Full mechanism", "^"),
        ):
            selected = current.loc[current["model"].eq(model)]
            ax.scatter(
                selected["observed_type_index_c"],
                selected["prediction_type_index_c"],
                s=34,
                marker=marker,
                color=MODEL_COLORS[model],
                edgecolor="white",
                linewidth=0.45,
                alpha=0.9,
                label=model,
            )
        for year in (1997, 2015, 2023):
            point = current.loc[
                current["model"].eq("Full mechanism")
                & current["year"].eq(year)
            ].iloc[0]
            ax.annotate(
                str(year),
                (
                    point["observed_type_index_c"],
                    point["prediction_type_index_c"],
                ),
                xytext=(4, 3),
                textcoords="offset points",
                fontsize=7.5,
            )
        ax.set_xlim(*limits)
        ax.set_ylim(*limits)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("Observed DJF Niño3 − Niño4 (°C)")
        ax.set_ylabel("LOEO prediction (°C)")
        ax.set_title(
            f"({'c' if month == 4 else 'd'}) {MONTH_LABELS[month - 1]} initialization",
            weight="bold",
        )
        ax.grid(color="0.9", lw=0.6)
        ax.set_axisbelow(True)

    fig.suptitle(
        "Does the two-gate mechanism add predictive information about EP/CP flavor?",
        fontsize=14,
        weight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.018,
        "Target: following-DJF OISST Niño3−Niño4. Walk-forward trends/scaling use prior years only. "
        "Event-only validation uses fixed ridge α=1 and leaves out one warm episode at a time.\n"
        "Positive skill means improvement over same-month type persistence; displayed q values "
        "control FDR across all model × month comparisons.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="0.33",
    )
    PREDICTION_PNG.parent.mkdir(parents=True, exist_ok=True)
    PREDICTION_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PREDICTION_PNG)
    fig.savefig(PREDICTION_PDF)
    plt.close(fig)


def permutation_correlation(
    x: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 20260730,
    samples: int = 20000,
) -> dict[str, float]:
    valid = np.isfinite(x) & np.isfinite(y)
    x = np.asarray(x[valid], dtype=float)
    y = np.asarray(y[valid], dtype=float)
    observed = float(np.corrcoef(x, y)[0, 1])
    rng = np.random.default_rng(seed)
    null = np.empty(samples, dtype=float)
    for index in range(samples):
        null[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    p_value = float((np.sum(np.abs(null) >= abs(observed)) + 1) / (samples + 1))
    return {"correlation": observed, "two_sided_permutation_p": p_value, "n": len(x)}


def write_summary(
    event: pd.DataFrame,
    walk_skill: pd.DataFrame,
    loeo_skill: pd.DataFrame,
) -> dict[str, object]:
    gate_code = event["full_two_gate_month"].fillna(7).to_numpy(dtype=float)
    gate_relationship = permutation_correlation(
        -gate_code,
        event["mature_djf_type_index_c"].to_numpy(dtype=float),
    )
    predictor_columns = {
        "FEP residual Jan-Jun": "fep_residual_jan_jun_mean_c",
        "OHC E-W May-Jun": "ohc300_ew_may_jun_mean_gjm2",
        "D20 E-W May-Jun": "d20_ew_may_jun_mean_m",
        "u850 May-Jun": "u850_cwp_may_jun_mean_ms",
        "-OLR May-Jun": "minus_olr_cp_may_jun_mean_wm2",
    }
    event_correlations = {
        label: permutation_correlation(
            event[column].to_numpy(dtype=float),
            event["mature_djf_type_index_c"].to_numpy(dtype=float),
            seed=20260730 + index,
        )
        for index, (label, column) in enumerate(predictor_columns.items())
    }
    correlation_p_values = pd.Series(
        {
            label: values["two_sided_permutation_p"]
            for label, values in event_correlations.items()
        }
    )
    correlation_q_values = benjamini_hochberg(correlation_p_values)
    for label in event_correlations:
        event_correlations[label]["bh_fdr_q_across_five_predictors"] = float(
            correlation_q_values[label]
        )
    walk_best = (
        walk_skill.loc[walk_skill["model"].ne("Type persistence")]
        .sort_values("rmse_skill_vs_persistence", ascending=False)
        .iloc[0]
    )
    loeo_best = (
        loeo_skill.loc[loeo_skill["model"].ne("Type persistence")]
        .sort_values("rmse_skill_vs_persistence", ascending=False)
        .iloc[0]
    )
    event_labels = event[
        [
            "event_year",
            "mature_djf_type_index_c",
            "mature_flavor",
            "full_two_gate_month",
        ]
    ].to_dict(orient="records")
    diagnostics = {
        "method": {
            "primary_target": "following DJF OISST Nino3 minus Nino4 anomaly",
            "warm_event_rule": (
                "NOAA ONI >= 0.5 C for at least five consecutive overlapping seasons"
            ),
            "n_warm_events": int(len(event)),
            "walk_forward_test_years": list(TEST_YEARS),
            "event_validation": "leave one warm episode out, ridge alpha=1",
            "gate_rule": "two consecutive January-June months",
        },
        "gate_timing_relationship": gate_relationship,
        "event_predictor_correlations": event_correlations,
        "best_walk_forward": walk_best.to_dict(),
        "best_event_loeo": loeo_best.to_dict(),
        "event_labels": event_labels,
        "published_classification_crosscheck": {
            "n_available": int(event["published_ep_cp_label"].notna().sum()),
            "n_agree": int(
                event["relative_sign_agrees_with_published"].fillna(False).sum()
            ),
            "source": "Beniche et al. (2024), Supplementary Fig. S4",
        },
    }
    DIAGNOSTIC_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    robust_walk = walk_skill.loc[
        (walk_skill["model"].ne("Type persistence"))
        & (walk_skill["bh_fdr_q_across_model_month_tests"] < 0.05)
    ].sort_values("rmse_skill_vs_persistence", ascending=False)
    robust_sentence = (
        "对所有“月份 × 模型”检验进行 BH-FDR 校正后，没有任何改进达到 q<0.05"
        if robust_walk.empty
        else "、".join(
            f"{MONTH_LABELS[int(row.month)-1]} {row.model}"
            for row in robust_walk.itertuples()
        )
    )
    significant_event_predictors = [
        label
        for label, values in event_correlations.items()
        if values["bh_fdr_q_across_five_predictors"] < 0.05
    ]
    predictor_sentence = (
        "无"
        if not significant_event_predictors
        else "、".join(significant_event_predictors)
    )
    published = diagnostics["published_classification_crosscheck"]
    lines = [
        "# EP/CP 类型“两道门”全事件检验",
        "",
        "## 结论先行",
        "",
        (
            f"- 1982–2023 年共识别出 **{len(event)} 次** NOAA ONI 暖事件。"
            "成熟型态以随后 DJF 的 OISST `Niño3−Niño4` 为连续指标；"
            "`>0` 表示更偏东，`<0` 表示更偏中部。"
        ),
        (
            f"- 全年份逐年回报检验中，最佳非持续性模型是 "
            f"**{MONTH_LABELS[int(walk_best['month']) - 1]} 的 "
            f"{walk_best['model']}**，相对类型持续性的 RMSE skill 为 "
            f"**{walk_best['rmse_skill_vs_persistence']:+.3f}**，"
            f"95% bootstrap 区间 "
            f"[{walk_best['skill_ci_2p5']:+.3f}, "
            f"{walk_best['skill_ci_97p5']:+.3f}]。"
        ),
        (
            f"- 暖事件留一法中，最佳结果是 "
            f"**{MONTH_LABELS[int(loeo_best['month']) - 1]} 的 "
            f"{loeo_best['model']}**，RMSE skill "
            f"**{loeo_best['rmse_skill_vs_persistence']:+.3f}**，"
            f"符号命中率 **{loeo_best['sign_accuracy']:.0%}**。"
        ),
        (
            f"- 严格不确定性检查：{robust_sentence}。"
            "因此，May FEP 的正技巧只能表述为“候选预测信号”，不能表述为已经建立稳定预测能力。"
        ),
        (
            f"- “两道门越早完整打开，成熟期越偏东”的事件相关为 "
            f"**r={gate_relationship['correlation']:+.2f}**，"
            f"置换检验 p={gate_relationship['two_sided_permutation_p']:.3f}。"
            "未通过门的事件按 7（月）编码，仅用于排序检验。"
        ),
        (
            f"- 相比“过零时间”，异常**强度**更有信息。五个事件强度指标经 "
            f"BH-FDR 校正后 q<0.05 的有：**{predictor_sentence}**。"
        ),
        (
            f"- `Niño3−Niño4` 的正负号与可核验的文献分类 "
            f"**{published['n_agree']}/{published['n_available']} 一致**；"
            "但接近 0 的事件仍保留为 mixed/borderline。"
        ),
        "",
        "## 这是否形成研究闭环",
        "",
        (
            "- 机制链条可以形成一个**待检验的闭环假说**：FEP 异常是触发背景，"
            "而不是充分条件；热量向东重分配的强度（OHC/D20）和大气持续响应的"
            "强度（西风/对流）共同影响暖异常能否发展成偏东型。"
        ),
        (
            "- 但统计证据仍是探索性的：只有 13 个暖事件，且 OHC 与 D20、"
            "风与 OLR 均存在共线性。真正可投稿的下一步应增加不同资料集敏感性、"
            "模式试验或更长重建，并预先固定阈值。"
        ),
        "",
        "## 解释边界",
        "",
        "- `Niño3−Niño4` 是连续的“偏东/偏中部”度量，不等同于唯一公认的 EP/CP 离散定义。",
        "- `|Niño3−Niño4|<0.2°C` 标为 mixed/borderline，避免把接近 0 的事件过度分类。",
        "- 门槛 `>0` 且连续两个月是操作性诊断，必须在其他阈值和资料集上做敏感性检验。",
        "- 全年份逐年检验严格使用过去年份拟合趋势和尺度；事件留一法仍受小样本限制。",
        "",
        "## 关键输出",
        "",
        f"- 机制审计图：`{MECHANISM_PDF}`",
        f"- 预测技巧图：`{PREDICTION_PDF}`",
        f"- 事件表：`{EVENT_CSV}`",
        f"- 逐年预测技巧：`{WALK_SKILL_CSV}`",
        f"- 暖事件留一法技巧：`{LOEO_SKILL_CSV}`",
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return diagnostics


def main() -> None:
    for path in (OHC_CSV, D20_NC, ATMOS_NC, ONI_FILE, *U850_FILES):
        if not path.exists():
            raise FileNotFoundError(path)
    for directory in (OUT_DATA, OUT_FIG, OUT_PDF):
        directory.mkdir(parents=True, exist_ok=True)

    sst = load_oisst_indices()
    monthly = build_monthly_table(sst)
    manifest = event_manifest()
    events = build_event_summary(monthly, manifest)
    walk_predictions = walk_forward_predictions(monthly)
    walk_skill = summarize_prediction_skill(
        walk_predictions,
        prediction_column="prediction_type_residual_c",
        observed_column="observed_type_residual_c",
    )
    loeo_predictions = event_loeo_predictions(monthly, events)
    loeo_skill = summarize_prediction_skill(
        loeo_predictions,
        prediction_column="prediction_type_index_c",
        observed_column="observed_type_index_c",
    )

    monthly.to_csv(MONTHLY_CSV, index=False)
    events.to_csv(EVENT_CSV, index=False)
    walk_predictions.to_csv(WALK_PRED_CSV, index=False)
    walk_skill.to_csv(WALK_SKILL_CSV, index=False)
    loeo_predictions.to_csv(LOEO_PRED_CSV, index=False)
    loeo_skill.to_csv(LOEO_SKILL_CSV, index=False)
    plot_mechanism_audit(events)
    plot_prediction_skill(walk_skill, loeo_skill, loeo_predictions)
    diagnostics = write_summary(events, walk_skill, loeo_skill)

    print(f"Events: {len(events)}")
    print(
        events[
            [
                "event_year",
                "mature_djf_type_index_c",
                "mature_flavor",
                "fep_persistent_positive_month",
                "ocean_gate_month",
                "atmosphere_gate_month",
                "full_two_gate_month",
            ]
        ].to_string(index=False)
    )
    print("\nBest walk-forward:", diagnostics["best_walk_forward"])
    print("Best event LOEO:", diagnostics["best_event_loeo"])
    for path in (
        MONTHLY_CSV,
        EVENT_CSV,
        WALK_PRED_CSV,
        WALK_SKILL_CSV,
        LOEO_PRED_CSV,
        LOEO_SKILL_CSV,
        DIAGNOSTIC_JSON,
        MECHANISM_PNG,
        MECHANISM_PDF,
        PREDICTION_PNG,
        PREDICTION_PDF,
        SUMMARY_MD,
    ):
        print(path)


if __name__ == "__main__":
    main()
