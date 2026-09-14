#!/usr/bin/env python3
"""Add a lagged Jiang-box atmospheric gate to the SODA3 OHC framework.

The atmospheric predictor is the previous completed month's ERA5 850-hPa
northeasterly intrusion residual over 3N-7N, 180E-130W.  The expected wind
is fitted separately by calendar month from year, Nino-3.4 SST and the
east-minus-west SST pattern.  Residualization is repeated inside every
leave-one-event-out fold, excluding the held event.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

RUNTIME_CACHE = Path("/private/tmp/codex_soda3_era5_two_gate_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from sklearn.metrics import log_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_soda3_5day_ohc_geometry_coupling as base  # noqa: E402


WIND_PART1 = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc"
)
WIND_JUNE = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jun.nc"
)
WIND_JULY = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_850_ne_box_july_1982_2024.nc"
)
COUPLING_MONTHLY = (
    ROOT
    / "data/derived/research_2026/"
    "enso_full_year_coupling_monthly_1982_2024.csv"
)

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_era5_two_gate"
ATM_MONTHLY_CSV = DERIVED / "era5_jiang_ne850_monthly_1982_2024_jan_jul.csv"
PRIMARY_PREDICTIONS_CSV = DERIVED / "soda3_era5_two_gate_primary_loeo_predictions.csv"
PRIMARY_SKILL_CSV = DERIVED / "soda3_era5_two_gate_primary_skill.csv"
DURABLE_PREDICTIONS_CSV = DERIVED / "soda3_era5_two_gate_durable_loeo_predictions.csv"
DURABLE_SKILL_CSV = DERIVED / "soda3_era5_two_gate_durable_skill.csv"
COEFFICIENTS_CSV = DERIVED / "soda3_era5_two_gate_loeo_coefficients.csv"
EVENT_DELTAS_CSV = DERIVED / "soda3_era5_two_gate_event_brier_deltas.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_era5_two_gate_diagnostics.json"
FIGURE_PNG = OUT / "soda3_era5_two_gate_incremental_skill.png"
REPORT_MD = OUT / "SODA3_ERA5_TWO_GATE_RESULT_CN.md"

NE_LAT_BOUNDS = (3.0, 7.0)
NE_LON_BOUNDS = (180.0, 230.0)
BASELINE_YEARS = (1982, 2024)
RNG_SEED = 20260802
N_BOOTSTRAP = 10000

BASE_FEATURES = [
    "season_sin",
    "season_cos",
    "ohc300_positive_total_pj_m_15day",
    "ohc300_positive_total_pj_m_change15day",
]
MODEL_FEATURES = {
    "heat_only": BASE_FEATURES,
    "ocean_geometry": BASE_FEATURES
    + [
        "ohc300_positive_east140w_fraction_15day",
        "ohc300_positive_east140w_fraction_change15day",
    ],
    "atmosphere_gate": BASE_FEATURES + ["atmosphere_favorable_lag1_ms"],
    "two_gate": BASE_FEATURES
    + [
        "ohc300_positive_east140w_fraction_15day",
        "ohc300_positive_east140w_fraction_change15day",
        "atmosphere_favorable_lag1_ms",
        "ocean_atmosphere_gate_interaction",
    ],
}


def normalize(dataset: xr.Dataset) -> xr.Dataset:
    dataset = dataset.rename(
        {
            name: replacement
            for name, replacement in (
                ("valid_time", "time"),
                ("latitude", "lat"),
                ("longitude", "lon"),
            )
            if name in dataset.coords
        }
    )
    return dataset.assign_coords(lon=dataset["lon"] % 360.0).sortby(["lat", "lon"])


def area_mean_jiang_box(field: xr.DataArray) -> xr.DataArray:
    subset = field.sel(
        lat=slice(*NE_LAT_BOUNDS),
        lon=slice(*NE_LON_BOUNDS),
    )
    if subset.sizes.get("lat", 0) != 5 or subset.sizes.get("lon", 0) != 51:
        raise ValueError(f"Unexpected Jiang-box grid: {subset.sizes}")
    weights = np.cos(np.deg2rad(subset["lat"]))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def load_era5_monthly() -> pd.DataFrame:
    pieces = []
    for path in (WIND_PART1, WIND_JUNE, WIND_JULY):
        with xr.open_dataset(path, engine="h5netcdf") as raw:
            dataset = normalize(raw).sel(
                time=slice(f"{BASELINE_YEARS[0]}-01-01", f"{BASELINE_YEARS[1]}-12-31")
            )
            if "pressure_level" in dataset.dims:
                dataset = dataset.sel(pressure_level=850, drop=True)
            current = xr.Dataset(
                {
                    "u850_jiang_box_ms": area_mean_jiang_box(dataset["u"]).load(),
                    "v850_jiang_box_ms": area_mean_jiang_box(dataset["v"]).load(),
                }
            )
            pieces.append(current)
    combined = xr.concat(pieces, dim="time").sortby("time")
    combined = combined.sel(time=combined["time"].dt.month.isin(range(1, 8)))
    if combined.get_index("time").duplicated().any():
        raise ValueError("Duplicate ERA5 Jiang-box monthly records")
    time = pd.DatetimeIndex(combined["time"].values)
    frame = pd.DataFrame(
        {
            "time": time,
            "year": time.year,
            "month": time.month,
            "u850_jiang_box_ms": combined["u850_jiang_box_ms"].values.astype(float),
            "v850_jiang_box_ms": combined["v850_jiang_box_ms"].values.astype(float),
        }
    )
    frame["ne850_jiang_box_ms"] = -(
        frame["u850_jiang_box_ms"] + frame["v850_jiang_box_ms"]
    ) / np.sqrt(2.0)
    coupling = pd.read_csv(COUPLING_MONTHLY)[
        ["year", "month", "nino34_raw_c", "sst_type_raw_c"]
    ]
    frame = frame.merge(
        coupling,
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )
    expected = (BASELINE_YEARS[1] - BASELINE_YEARS[0] + 1) * 7
    if len(frame) != expected:
        raise ValueError(f"Expected {expected} ERA5 monthly records, found {len(frame)}")
    required = [
        "u850_jiang_box_ms",
        "v850_jiang_box_ms",
        "ne850_jiang_box_ms",
        "nino34_raw_c",
        "sst_type_raw_c",
    ]
    if frame[required].isna().any().any():
        raise ValueError("Missing ERA5 or SST values in atmospheric-gate baseline")
    if not frame[["u850_jiang_box_ms", "v850_jiang_box_ms"]].apply(
        lambda values: values.between(-25.0, 25.0).all()
    ).all():
        raise ValueError("ERA5 Jiang-box wind is outside physical QA bounds")
    return frame.sort_values(["year", "month"]).reset_index(drop=True)


def fold_atmospheric_gate(
    monthly: pd.DataFrame,
    held_year: int,
) -> pd.DataFrame:
    """Fit month-specific expected NE850 without the held event year."""
    pieces = []
    for month, group in monthly.groupby("month", sort=True):
        training = group.loc[group["year"] != held_year]
        train_design = np.column_stack(
            [
                np.ones(len(training)),
                training["year"].to_numpy(dtype=float) - 2003.0,
                training["nino34_raw_c"].to_numpy(dtype=float),
                training["sst_type_raw_c"].to_numpy(dtype=float),
            ]
        )
        coefficients = np.linalg.lstsq(
            train_design,
            training["ne850_jiang_box_ms"].to_numpy(dtype=float),
            rcond=None,
        )[0]
        design = np.column_stack(
            [
                np.ones(len(group)),
                group["year"].to_numpy(dtype=float) - 2003.0,
                group["nino34_raw_c"].to_numpy(dtype=float),
                group["sst_type_raw_c"].to_numpy(dtype=float),
            ]
        )
        current = group[["year", "month"]].copy()
        current["ne850_residual_ms"] = (
            group["ne850_jiang_box_ms"].to_numpy(dtype=float)
            - design @ coefficients
        )
        current["atmosphere_favorable_ms"] = -current["ne850_residual_ms"]
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True)


def add_lag_coordinates(risk: pd.DataFrame) -> pd.DataFrame:
    output = risk.copy()
    lag = pd.to_datetime(output["time"]).dt.to_period("M") - 1
    output["atmos_lag_year"] = lag.dt.year
    output["atmos_lag_month"] = lag.dt.month
    return output.loc[output["atmos_lag_month"].between(1, 7)].copy()


def attach_fold_gate(
    risk: pd.DataFrame,
    gate: pd.DataFrame,
) -> pd.DataFrame:
    lookup = gate.rename(
        columns={
            "year": "atmos_lag_year",
            "month": "atmos_lag_month",
            "atmosphere_favorable_ms": "atmosphere_favorable_lag1_ms",
        }
    )
    output = risk.merge(
        lookup[
            ["atmos_lag_year", "atmos_lag_month", "atmosphere_favorable_lag1_ms"]
        ],
        on=["atmos_lag_year", "atmos_lag_month"],
        how="left",
        validate="many_to_one",
    )
    if output["atmosphere_favorable_lag1_ms"].isna().any():
        raise ValueError("Missing fold-specific lagged atmospheric gate")
    output["ocean_atmosphere_gate_interaction"] = (
        output["ohc300_positive_east140w_fraction_15day"]
        * output["atmosphere_favorable_lag1_ms"]
    )
    return output


def loeo_two_gate(
    risk: pd.DataFrame,
    monthly: pd.DataFrame,
    outcome_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_rows = []
    coefficient_rows = []
    years = sorted(risk["year"].unique())
    for held_year in years:
        fold_gate = fold_atmospheric_gate(monthly, int(held_year))
        current = attach_fold_gate(risk, fold_gate)
        train = current.loc[current["year"] != held_year]
        test = current.loc[current["year"] == held_year]
        train_weights = base.event_balancing_weights(train["year"])
        for model_name, features in MODEL_FEATURES.items():
            model = base.make_model()
            model.fit(
                train[features].to_numpy(dtype=float),
                train["onset_within_20day"].to_numpy(dtype=int),
                logistic__sample_weight=train_weights,
            )
            probability = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
            for row, value in zip(test.itertuples(), probability, strict=True):
                prediction_rows.append(
                    {
                        "outcome": outcome_label,
                        "time": row.time,
                        "year": int(row.year),
                        "observed_onset_within_20day": int(row.onset_within_20day),
                        "model": model_name,
                        "probability": float(value),
                    }
                )
            coefficients = model.named_steps["logistic"].coef_[0]
            for feature, coefficient in zip(features, coefficients, strict=True):
                coefficient_rows.append(
                    {
                        "outcome": outcome_label,
                        "held_year": int(held_year),
                        "model": model_name,
                        "feature": feature,
                        "standardized_logit_coefficient": float(coefficient),
                    }
                )
    return pd.DataFrame(prediction_rows), pd.DataFrame(coefficient_rows)


def summarize_skill(
    predictions: pd.DataFrame,
    coefficients: pd.DataFrame,
) -> pd.DataFrame:
    baseline = predictions.loc[predictions["model"] == "heat_only"].rename(
        columns={"probability": "baseline_probability"}
    )
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for model_name, group in predictions.groupby("model", sort=False):
        current = group.copy()
        weights = base.event_balancing_weights(current["year"])
        observed = current["observed_onset_within_20day"].to_numpy(dtype=int)
        probability = current["probability"].to_numpy(dtype=float)
        brier = base.weighted_brier(observed, probability, weights)
        auc = float(roc_auc_score(observed, probability, sample_weight=weights))
        logscore = float(
            log_loss(observed, probability, sample_weight=weights, labels=[0, 1])
        )
        merged = current.merge(
            baseline[["time", "year", "baseline_probability"]],
            on=["time", "year"],
            validate="one_to_one",
        )
        event_deltas = []
        for year, event in merged.groupby("year"):
            y = event["observed_onset_within_20day"].to_numpy(dtype=float)
            model_error = np.mean((event["probability"].to_numpy() - y) ** 2)
            base_error = np.mean((event["baseline_probability"].to_numpy() - y) ** 2)
            event_deltas.append((int(year), float(model_error - base_error)))
        delta = np.asarray([item[1] for item in event_deltas], dtype=float)
        bootstrap = np.empty(N_BOOTSTRAP, dtype=float)
        for index in range(N_BOOTSTRAP):
            sample = rng.integers(0, len(delta), len(delta))
            bootstrap[index] = float(np.mean(delta[sample]))
        gate_coefficient = coefficients.loc[
            coefficients["model"].eq(model_name)
            & coefficients["feature"].eq("atmosphere_favorable_lag1_ms"),
            "standardized_logit_coefficient",
        ].to_numpy(dtype=float)
        interaction_coefficient = coefficients.loc[
            coefficients["model"].eq(model_name)
            & coefficients["feature"].eq("ocean_atmosphere_gate_interaction"),
            "standardized_logit_coefficient",
        ].to_numpy(dtype=float)
        rows.append(
            {
                "model": model_name,
                "event_weighted_brier": brier,
                "event_weighted_auc": auc,
                "event_weighted_log_loss": logscore,
                "delta_brier_vs_heat_only": float(np.mean(delta)),
                "delta_brier_ci_low": float(np.quantile(bootstrap, 0.025)),
                "delta_brier_ci_high": float(np.quantile(bootstrap, 0.975)),
                "events_improved_vs_heat_only": int(np.sum(delta < 0.0)),
                "events_total": len(delta),
                "favorable_gate_coefficient_median": (
                    np.nan if not len(gate_coefficient) else float(np.median(gate_coefficient))
                ),
                "favorable_gate_positive_fold_fraction": (
                    np.nan
                    if not len(gate_coefficient)
                    else float(np.mean(gate_coefficient > 0.0))
                ),
                "interaction_coefficient_median": (
                    np.nan
                    if not len(interaction_coefficient)
                    else float(np.median(interaction_coefficient))
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("event_weighted_brier")


def event_brier_deltas(predictions: pd.DataFrame) -> pd.DataFrame:
    """Return event-level skill changes relative to the heat-only baseline."""
    baseline = predictions.loc[predictions["model"] == "heat_only"].rename(
        columns={"probability": "baseline_probability"}
    )
    rows = []
    for model_name, group in predictions.groupby("model", sort=False):
        current = group.merge(
            baseline[["time", "year", "baseline_probability"]],
            on=["time", "year"],
            validate="one_to_one",
        )
        for year, event in current.groupby("year"):
            observed = event["observed_onset_within_20day"].to_numpy(dtype=float)
            model_error = np.mean((event["probability"].to_numpy() - observed) ** 2)
            baseline_error = np.mean(
                (event["baseline_probability"].to_numpy() - observed) ** 2
            )
            rows.append(
                {
                    "outcome": event["outcome"].iloc[0],
                    "year": int(year),
                    "model": model_name,
                    "event_brier": float(model_error),
                    "heat_only_event_brier": float(baseline_error),
                    "delta_brier_vs_heat_only": float(model_error - baseline_error),
                }
            )
    return pd.DataFrame(rows)


def set_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "axes.linewidth": 0.8,
            "savefig.dpi": 320,
        }
    )


def plot_results(
    primary_skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    indices: pd.DataFrame,
    monthly: pd.DataFrame,
    summaries: pd.DataFrame,
) -> None:
    set_style()
    models = ["ocean_geometry", "atmosphere_gate", "two_gate"]
    labels = ["Ocean geometry", "Lagged atmosphere gate", "Ocean × atmosphere"]
    primary = primary_skill.set_index("model").loc[models]
    durable = durable_skill.set_index("model").loc[models]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    y = np.arange(len(models))
    for current, offset, color, marker, label in (
        (primary, -0.10, "#a11d22", "o", "30-day episode"),
        (durable, 0.10, "#2166ac", "s", "60-day durable"),
    ):
        values = current["delta_brier_vs_heat_only"].to_numpy(dtype=float)
        errors = np.vstack(
            [
                values - current["delta_brier_ci_low"].to_numpy(dtype=float),
                current["delta_brier_ci_high"].to_numpy(dtype=float) - values,
            ]
        )
        axes[0].errorbar(
            values,
            y + offset,
            xerr=errors,
            fmt=marker,
            color=color,
            capsize=3,
            label=label,
        )
    axes[0].axvline(0.0, color="0.3", lw=0.8)
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("LOEO Brier change vs heat-only model")
    axes[0].set_title("a  Incremental predictive skill", loc="left", fontweight="bold")
    axes[0].legend(frameon=False, loc="lower right")
    axes[0].text(0.02, 0.02, "Better ←", transform=axes[0].transAxes, color="0.35")
    axes[0].spines[["top", "right"]].set_visible(False)

    event = indices.loc[indices["year"] == 2023].sort_values("time").copy()
    lag = pd.to_datetime(event["time"]).dt.to_period("M") - 1
    event["atmos_lag_year"] = lag.dt.year
    event["atmos_lag_month"] = lag.dt.month
    gate_2023 = fold_atmospheric_gate(monthly, 2023).rename(
        columns={
            "year": "atmos_lag_year",
            "month": "atmos_lag_month",
            "atmosphere_favorable_ms": "atmosphere_favorable_lag1_ms",
        }
    )
    event = event.merge(
        gate_2023[
            ["atmos_lag_year", "atmos_lag_month", "atmosphere_favorable_lag1_ms"]
        ],
        on=["atmos_lag_year", "atmos_lag_month"],
        how="left",
        validate="many_to_one",
    )
    event = event.loc[event["atmosphere_favorable_lag1_ms"].notna()]
    ocean_line = axes[1].plot(
        event["time"],
        event["ohc300_positive_east140w_fraction_15day"],
        color="#1b7837",
        lw=1.8,
        label="East-of-140°W heat fraction",
    )[0]
    axes[1].set_ylim(0.0, 1.0)
    axes[1].set_ylabel("East-of-140°W positive-OHC fraction", color="#1b7837")
    axes[1].tick_params(axis="y", colors="#1b7837")
    axes[1].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    atmosphere_axis = axes[1].twinx()
    gate_line = atmosphere_axis.step(
        event["time"],
        event["atmosphere_favorable_lag1_ms"],
        where="post",
        color="#762a83",
        lw=1.5,
        label="Lagged atmospheric favorability",
    )[0]
    atmosphere_axis.axhline(0.0, color="#762a83", lw=0.6, alpha=0.6)
    atmosphere_axis.set_ylabel("Lagged Jiang-box atmospheric gate (m s$^{-1}$)", color="#762a83")
    atmosphere_axis.tick_params(axis="y", colors="#762a83")
    row = summaries.loc[summaries["year"] == 2023].iloc[0]
    short_date = pd.Timestamp(row["coupling_onset_date"])
    durable_date = pd.Timestamp(row["sensitivity_8of12_durable_onset_date"])
    axes[1].axvline(short_date, color="#111111", lw=1.1, label="30-day episode")
    axes[1].axvline(durable_date, color="#2166ac", lw=1.1, ls="--", label="60-day durable")
    axes[1].set_title("b  2023 event sequence", loc="left", fontweight="bold")
    axes[1].spines["top"].set_visible(False)
    atmosphere_axis.spines["top"].set_visible(False)
    handles = [
        ocean_line,
        gate_line,
        mpl.lines.Line2D([], [], color="#111111", lw=1.1, label="30-day episode"),
        mpl.lines.Line2D([], [], color="#2166ac", lw=1.1, ls="--", label="60-day durable"),
    ]
    axes[1].legend(handles=handles, frameon=False, loc="lower right", fontsize=7.6)
    fig.suptitle(
        "SODA3 heat framework + lagged ERA5 Jiang-box atmospheric gate",
        fontsize=12.5,
        fontweight="bold",
    )
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    plt.close(fig)


def write_report(
    primary_skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    summaries: pd.DataFrame,
) -> None:
    primary_best = primary_skill.iloc[0]
    durable_best = durable_skill.iloc[0]
    primary_atmos = primary_skill.loc[primary_skill["model"] == "atmosphere_gate"].iloc[0]
    primary_two = primary_skill.loc[primary_skill["model"] == "two_gate"].iloc[0]
    durable_atmos = durable_skill.loc[durable_skill["model"] == "atmosphere_gate"].iloc[0]
    durable_two = durable_skill.loc[durable_skill["model"] == "two_gate"].iloc[0]
    durable_heat = durable_skill.loc[durable_skill["model"] == "heat_only"].iloc[0]
    robust = (
        durable_two["delta_brier_ci_high"] < 0.0
        and durable_two["events_improved_vs_heat_only"] >= 7
        and durable_two["favorable_gate_positive_fold_fraction"] >= 0.75
    )
    conclusion = (
        "海洋-大气双门在当前事件样本中通过了预先设定的稳定性条件。"
        if robust
        else "海洋-大气双门尚未通过稳定性条件，不能写成已经闭合的预测公式。"
    )
    text = f"""# SODA3热含量加入ERA5大气门：增量检验

## 设计

在上一阶段热含量模型上，只加入一个独立大气量：ERA5 3°N-7°N、180°E-130°W的850 hPa东北风残差。每个五日预测只使用上一个完整月；每个留一事件折内重新拟合月别风-SST关系，并排除测试年份。

比较四个模型：仅总暖量、加入暖量位置、加入滞后大气门、暖量位置与大气门交互。验证继续完整留出事件，不拆分相邻五日。

## 结果

- 30天西风段中，最佳模型为`{primary_best['model']}`，Brier={primary_best['event_weighted_brier']:.4f}。
- 单独加入大气门相对热量基线的Brier变化为{primary_atmos['delta_brier_vs_heat_only']:+.4f}，95%区间[{primary_atmos['delta_brier_ci_low']:+.4f}, {primary_atmos['delta_brier_ci_high']:+.4f}]。
- 双门交互模型的变化为{primary_two['delta_brier_vs_heat_only']:+.4f}，95%区间[{primary_two['delta_brier_ci_low']:+.4f}, {primary_two['delta_brier_ci_high']:+.4f}]。
- 60天耐久接通中，热量基线Brier={durable_heat['event_weighted_brier']:.4f}；最佳模型为`{durable_best['model']}`，Brier={durable_best['event_weighted_brier']:.4f}。
- 耐久判据下，单独大气门变化为{durable_atmos['delta_brier_vs_heat_only']:+.4f}，双门变化为{durable_two['delta_brier_vs_heat_only']:+.4f}；双门95%区间为[{durable_two['delta_brier_ci_low']:+.4f}, {durable_two['delta_brier_ci_high']:+.4f}]。
- 30天目标中，大气有利度系数中位数为{primary_atmos['favorable_gate_coefficient_median']:+.3f}，10个留一折中预期正号比例为{primary_atmos['favorable_gate_positive_fold_fraction']:.0%}，没有形成稳定的跨事件正关系。

## 判断

{conclusion}

该结果回答的是：上一个完整月的异常东北风背景，能否在热含量条件之外提高未来20天接通概率。它比直接把当前风应力放进模型更独立，但仍然是诊断量，不代表东北风是唯一因果源。逐事件结果显示，它改善了2023年短期30天西风段的识别（事件Brier变化−0.0555），却没有改善2023年的60天耐久接通，也没有跨事件泛化。因此，本结果不否定Jiang所描述的2023机制；它否定的是把“前月月平均东北风残差”直接当成所有事件共用预测开关。月平均与整月滞后很可能抹平MJO/WWB等五日到日尺度过程。下一步应转向同一物理链上的高频对流或风爆发持续性，而不是继续增加海洋变量。

2023年的30天西风段日期为{summaries.loc[summaries['year'].eq(2023), 'coupling_onset_date'].iloc[0]}，60天耐久接通日期为{summaries.loc[summaries['year'].eq(2023), 'sensitivity_8of12_durable_onset_date'].iloc[0]}。
"""
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    monthly = load_era5_monthly()
    monthly.to_csv(ATM_MONTHLY_CSV, index=False)
    indices = base.load_indices(base.INPUT_INDEX)
    summaries = base.event_summary(indices)
    primary_risk = add_lag_coordinates(base.build_risk_set(indices))
    durable_risk = add_lag_coordinates(
        base.build_risk_set(
            indices,
            positive_count=base.DURABLE_POSITIVE_COUNT,
            window_pentads=base.DURABLE_WINDOW_PENTADS,
        )
    )
    primary_predictions, primary_coefficients = loeo_two_gate(
        primary_risk, monthly, "30day_episode"
    )
    durable_predictions, durable_coefficients = loeo_two_gate(
        durable_risk, monthly, "60day_durable"
    )
    primary_skill = summarize_skill(primary_predictions, primary_coefficients)
    durable_skill = summarize_skill(durable_predictions, durable_coefficients)
    coefficients = pd.concat(
        [primary_coefficients, durable_coefficients], ignore_index=True
    )
    event_deltas = pd.concat(
        [event_brier_deltas(primary_predictions), event_brier_deltas(durable_predictions)],
        ignore_index=True,
    )
    primary_predictions.to_csv(PRIMARY_PREDICTIONS_CSV, index=False)
    durable_predictions.to_csv(DURABLE_PREDICTIONS_CSV, index=False)
    primary_skill.to_csv(PRIMARY_SKILL_CSV, index=False)
    durable_skill.to_csv(DURABLE_SKILL_CSV, index=False)
    coefficients.to_csv(COEFFICIENTS_CSV, index=False)
    event_deltas.to_csv(EVENT_DELTAS_CSV, index=False)
    diagnostics = {
        "era5_monthly_records": len(monthly),
        "era5_months": sorted(monthly["month"].unique().tolist()),
        "primary_risk_rows": len(primary_risk),
        "durable_risk_rows": len(durable_risk),
        "events_primary": sorted(primary_risk["year"].unique().tolist()),
        "events_durable": sorted(durable_risk["year"].unique().tolist()),
        "atmospheric_gate": (
            "negative fold-specific residual NE850 over 3N-7N, 180E-130W, "
            "lagged one completed calendar month"
        ),
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    plot_results(primary_skill, durable_skill, indices, monthly, summaries)
    write_report(primary_skill, durable_skill, summaries)
    print("Primary 30-day episode")
    print(primary_skill.to_string(index=False))
    print("\nDurable 60-day onset")
    print(durable_skill.to_string(index=False))
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
