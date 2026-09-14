#!/usr/bin/env python3
"""Independently validate the SODA3 coupling gate with daily ERA5 u10."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

RUNTIME_CACHE = Path("/private/tmp/codex_era5_daily_wind_gate_cache")
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
import analyze_soda3_high_frequency_wind_gate as soda_gate  # noqa: E402


EVENT_YEARS = (1982, 1986, 1991, 1997, 2002, 2004, 2015, 2018, 2019, 2023)
RAW_DIR = ROOT / "data/raw/era5/daily_u10_central_pacific_event_years_1deg"
MONTHLY_BASELINE = ROOT / "data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc"
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/era5_daily_wind_gate_independent"
DAILY_INDEX_CSV = DERIVED / "era5_daily_u10_central_pacific_event_years.csv"
RISK_SET_CSV = DERIVED / "era5_daily_wind_gate_independent_risk_set.csv"
PRIMARY_PREDICTIONS_CSV = DERIVED / "era5_daily_wind_gate_primary_loeo_predictions.csv"
DURABLE_PREDICTIONS_CSV = DERIVED / "era5_daily_wind_gate_durable_loeo_predictions.csv"
PRIMARY_SKILL_CSV = DERIVED / "era5_daily_wind_gate_primary_skill.csv"
DURABLE_SKILL_CSV = DERIVED / "era5_daily_wind_gate_durable_skill.csv"
COEFFICIENTS_CSV = DERIVED / "era5_daily_wind_gate_loeo_coefficients.csv"
EVENT_DELTAS_CSV = DERIVED / "era5_daily_wind_gate_event_brier_deltas.csv"
GATE_COMPARISON_CSV = DERIVED / "era5_soda3_high_frequency_gate_comparison.csv"
DIAGNOSTICS_JSON = DERIVED / "era5_daily_wind_gate_diagnostics.json"
FIGURE_PNG = OUT / "era5_daily_wind_gate_independent_validation.png"
REPORT_MD = OUT / "ERA5_DAILY_WIND_GATE_INDEPENDENT_RESULT_CN.md"

ERA_GATE = "era5_lagged_positive_u10_impulse15_ms"
RNG_SEED = 20260802
N_BOOTSTRAP = 10000
BASE_FEATURES = [
    "season_sin",
    "season_cos",
    "ohc300_positive_total_pj_m_15day",
    "ohc300_positive_total_pj_m_change15day",
]
GEOMETRY_FEATURES = [
    "ohc300_positive_east140w_fraction_15day",
    "ohc300_positive_east140w_fraction_change15day",
]
MODEL_FEATURES = {
    "heat_only": BASE_FEATURES,
    "ocean_geometry": BASE_FEATURES + GEOMETRY_FEATURES,
    "era5_wind_memory": BASE_FEATURES + [ERA_GATE],
    "ocean_plus_era5_wind": BASE_FEATURES + GEOMETRY_FEATURES + [ERA_GATE],
}


def normalize(dataset: xr.Dataset) -> xr.Dataset:
    renames = {}
    for source, target in (
        ("valid_time", "time"),
        ("latitude", "lat"),
        ("longitude", "lon"),
    ):
        if source in dataset.coords:
            renames[source] = target
    dataset = dataset.rename(renames)
    return dataset.sortby(["lat", "lon"])


def area_mean_u10(dataset: xr.Dataset) -> xr.DataArray:
    current = normalize(dataset)
    subset = current["u10"].sel(lat=slice(-5.0, 5.0), lon=slice(-180.0, -140.0))
    if subset.sizes.get("lat", 0) < 11 or subset.sizes.get("lon", 0) < 41:
        raise ValueError(f"Unexpected ERA5 central-Pacific grid: {subset.sizes}")
    weights = np.cos(np.deg2rad(subset["lat"]))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def load_monthly_expected() -> pd.DataFrame:
    with xr.open_dataset(MONTHLY_BASELINE, engine="h5netcdf") as dataset:
        regional = area_mean_u10(dataset).load()
    times = pd.DatetimeIndex(regional["time"].values)
    frame = pd.DataFrame(
        {
            "year": times.year,
            "month": times.month,
            "monthly_u10_ms": regional.values.astype(float),
        }
    )
    if len(frame) != 43 * 12 or frame.duplicated(["year", "month"]).any():
        raise ValueError("Incomplete ERA5 monthly baseline")
    rows = []
    for month, group in frame.groupby("month", sort=True):
        years = group["year"].to_numpy(dtype=float)
        values = group["monthly_u10_ms"].to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(years)), years - 2003.0])
        coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
        for year in EVENT_YEARS:
            expected = coefficients[0] + coefficients[1] * (year - 2003.0)
            rows.append(
                {
                    "year": year,
                    "month": int(month),
                    "expected_monthly_u10_ms": float(expected),
                }
            )
    return pd.DataFrame(rows)


def load_daily_u10() -> pd.DataFrame:
    paths = sorted(RAW_DIR.glob("era5_daily_gate_hourly_u10_m*.nc"))
    if len(paths) != 9:
        raise FileNotFoundError(f"Expected 9 monthly ERA5 files in {RAW_DIR}, found {len(paths)}")
    hourly_pieces = []
    for path in paths:
        with xr.open_dataset(path, engine="h5netcdf") as dataset:
            regional = area_mean_u10(dataset).load()
        time = pd.DatetimeIndex(regional["time"].values)
        hourly_pieces.append(
            pd.DataFrame({"time": time, "u10_raw_ms": regional.values.astype(float)})
        )
    hourly = pd.concat(hourly_pieces, ignore_index=True).sort_values("time")
    if hourly.duplicated("time").any():
        raise ValueError("Duplicate ERA5 hourly timestamps")
    hourly["date"] = hourly["time"].dt.floor("D")
    counts = hourly.groupby("date")["time"].size()
    if not counts.eq(24).all():
        raise ValueError(f"Incomplete UTC days: {counts.loc[~counts.eq(24)].to_dict()}")
    daily = hourly.groupby("date", as_index=False).agg(
        u10_raw_ms=("u10_raw_ms", "mean"),
        hourly_count=("time", "size"),
    )
    daily["year"] = daily["date"].dt.year
    daily["month"] = daily["date"].dt.month
    if set(daily["year"].unique()) != set(EVENT_YEARS):
        raise ValueError(f"Unexpected ERA5 event years: {sorted(daily['year'].unique())}")
    expected_days = sum(
        pd.Period(f"{year}-{month:02d}").days_in_month
        for year in EVENT_YEARS
        for month in range(1, 10)
    )
    if len(daily) != expected_days:
        raise ValueError(f"Expected {expected_days} ERA5 days, found {len(daily)}")
    if not daily["u10_raw_ms"].between(-20.0, 20.0).all():
        raise ValueError("ERA5 daily regional u10 outside physical QA bounds")
    expected = load_monthly_expected()
    daily = daily.merge(expected, on=["year", "month"], validate="many_to_one")
    daily["u10_anom_ms"] = daily["u10_raw_ms"] - daily["expected_monthly_u10_ms"]
    return daily.sort_values("date").reset_index(drop=True)


def gate_for_times(times: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    daily_by_year = {year: group.set_index("date") for year, group in daily.groupby("year")}
    for row in times[["year", "time"]].drop_duplicates().itertuples(index=False):
        forecast = pd.Timestamp(row.time).floor("D")
        window = daily_by_year[int(row.year)].loc[
            (daily_by_year[int(row.year)].index >= forecast - pd.Timedelta(days=15))
            & (daily_by_year[int(row.year)].index < forecast)
        ]
        if len(window) != 15:
            value = np.nan
            positive_days = np.nan
            mean_anomaly = np.nan
            latest = pd.NaT
        else:
            anomaly = window["u10_anom_ms"].to_numpy(dtype=float)
            value = float(np.maximum(anomaly, 0.0).mean())
            positive_days = int(np.sum(anomaly > 0.0))
            mean_anomaly = float(np.mean(anomaly))
            latest = pd.Timestamp(window.index.max())
        rows.append(
            {
                "year": int(row.year),
                "time": pd.Timestamp(row.time),
                ERA_GATE: value,
                "era5_positive_u10_days15": positive_days,
                "era5_mean_u10_anom15_ms": mean_anomaly,
                "era5_gate_latest_source_date": latest,
            }
        )
    return pd.DataFrame(rows)


def build_gated_risk(
    indices: pd.DataFrame,
    daily: pd.DataFrame,
    *,
    positive_count: int = base.ONSET_POSITIVE_COUNT,
    window_pentads: int = base.ONSET_WINDOW_PENTADS,
) -> pd.DataFrame:
    risk = base.build_risk_set(
        indices,
        positive_count=positive_count,
        window_pentads=window_pentads,
    )
    gate = gate_for_times(risk, daily)
    output = risk.merge(gate, on=["year", "time"], validate="one_to_one")
    required = [ERA_GATE, "era5_positive_u10_days15", "era5_mean_u10_anom15_ms"]
    if output[required].isna().any().any():
        raise ValueError("Missing ERA5 gate values in risk set")
    latest = pd.to_datetime(output["era5_gate_latest_source_date"])
    forecast = pd.to_datetime(output["time"]).dt.floor("D")
    if not (forecast - latest).dt.days.eq(1).all():
        raise ValueError("ERA5 gate does not stop on the day before forecast time")
    return output.sort_values(["year", "time"]).reset_index(drop=True)


def loeo(risk: pd.DataFrame, outcome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions = []
    coefficients = []
    for held_year in sorted(risk["year"].unique()):
        train = risk.loc[risk["year"] != held_year]
        test = risk.loc[risk["year"] == held_year]
        weights = base.event_balancing_weights(train["year"])
        for model_name, features in MODEL_FEATURES.items():
            model = base.make_model()
            model.fit(
                train[features].to_numpy(dtype=float),
                train["onset_within_20day"].to_numpy(dtype=int),
                logistic__sample_weight=weights,
            )
            probability = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
            for row, value in zip(test.itertuples(), probability, strict=True):
                predictions.append(
                    {
                        "outcome": outcome,
                        "time": row.time,
                        "year": int(row.year),
                        "observed_onset_within_20day": int(row.onset_within_20day),
                        "model": model_name,
                        "probability": float(value),
                    }
                )
            for feature, value in zip(
                features, model.named_steps["logistic"].coef_[0], strict=True
            ):
                coefficients.append(
                    {
                        "outcome": outcome,
                        "held_year": int(held_year),
                        "model": model_name,
                        "feature": feature,
                        "standardized_logit_coefficient": float(value),
                    }
                )
    return pd.DataFrame(predictions), pd.DataFrame(coefficients)


def event_brier_table(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, year), event in predictions.groupby(["model", "year"]):
        observed = event["observed_onset_within_20day"].to_numpy(dtype=float)
        probability = event["probability"].to_numpy(dtype=float)
        rows.append(
            {
                "outcome": event["outcome"].iloc[0],
                "model": model,
                "year": int(year),
                "event_brier": float(np.mean((probability - observed) ** 2)),
            }
        )
    table = pd.DataFrame(rows)
    heat = table.loc[table["model"] == "heat_only", ["year", "event_brier"]].rename(
        columns={"event_brier": "heat_only_event_brier"}
    )
    ocean = table.loc[
        table["model"] == "ocean_geometry", ["year", "event_brier"]
    ].rename(columns={"event_brier": "ocean_geometry_event_brier"})
    table = table.merge(heat, on="year", validate="many_to_one").merge(
        ocean, on="year", validate="many_to_one"
    )
    table["delta_brier_vs_heat_only"] = table["event_brier"] - table["heat_only_event_brier"]
    table["delta_brier_vs_ocean_geometry"] = (
        table["event_brier"] - table["ocean_geometry_event_brier"]
    )
    return table


def bootstrap_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(values), size=(N_BOOTSTRAP, len(values)))
    means = values[samples].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def summarize_skill(
    predictions: pd.DataFrame,
    coefficients: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_table = event_brier_table(predictions)
    rows = []
    for index, (model, group) in enumerate(predictions.groupby("model", sort=False)):
        weights = base.event_balancing_weights(group["year"])
        observed = group["observed_onset_within_20day"].to_numpy(dtype=int)
        probability = group["probability"].to_numpy(dtype=float)
        events = event_table.loc[event_table["model"] == model]
        delta_heat = events["delta_brier_vs_heat_only"].to_numpy(dtype=float)
        delta_ocean = events["delta_brier_vs_ocean_geometry"].to_numpy(dtype=float)
        heat_ci = bootstrap_ci(delta_heat, RNG_SEED + index * 2)
        ocean_ci = bootstrap_ci(delta_ocean, RNG_SEED + index * 2 + 1)
        gate_coefficients = coefficients.loc[
            coefficients["model"].eq(model) & coefficients["feature"].eq(ERA_GATE),
            "standardized_logit_coefficient",
        ].to_numpy(dtype=float)
        rows.append(
            {
                "model": model,
                "event_weighted_brier": base.weighted_brier(observed, probability, weights),
                "event_weighted_auc": float(
                    roc_auc_score(observed, probability, sample_weight=weights)
                ),
                "event_weighted_log_loss": float(
                    log_loss(observed, probability, sample_weight=weights, labels=[0, 1])
                ),
                "delta_brier_vs_heat_only": float(delta_heat.mean()),
                "delta_brier_vs_heat_ci_low": heat_ci[0],
                "delta_brier_vs_heat_ci_high": heat_ci[1],
                "delta_brier_vs_ocean_geometry": float(delta_ocean.mean()),
                "delta_brier_vs_ocean_ci_low": ocean_ci[0],
                "delta_brier_vs_ocean_ci_high": ocean_ci[1],
                "events_improved_vs_heat_only": int(np.sum(delta_heat < 0.0)),
                "events_improved_vs_ocean_geometry": int(np.sum(delta_ocean < 0.0)),
                "events_total": len(delta_heat),
                "era5_gate_coefficient_median": (
                    np.nan if not len(gate_coefficients) else float(np.median(gate_coefficients))
                ),
                "era5_gate_positive_fold_fraction": (
                    np.nan
                    if not len(gate_coefficients)
                    else float(np.mean(gate_coefficients > 0.0))
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("event_weighted_brier"), event_table


def set_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 8.5,
            "axes.linewidth": 0.8,
            "savefig.dpi": 320,
        }
    )


def plot_results(
    primary_skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    events: pd.DataFrame,
    gate_comparison: pd.DataFrame,
    summaries: pd.DataFrame,
) -> None:
    set_style()
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.5), constrained_layout=True)
    comparisons = (
        (primary_skill, "era5_wind_memory", "delta_brier_vs_heat_only", "delta_brier_vs_heat_ci_low", "delta_brier_vs_heat_ci_high", "#b2182b", "o", "30d: ERA5 wind vs heat"),
        (primary_skill, "ocean_plus_era5_wind", "delta_brier_vs_ocean_geometry", "delta_brier_vs_ocean_ci_low", "delta_brier_vs_ocean_ci_high", "#b2182b", "s", "30d: ocean+ERA5 vs ocean"),
        (durable_skill, "era5_wind_memory", "delta_brier_vs_heat_only", "delta_brier_vs_heat_ci_low", "delta_brier_vs_heat_ci_high", "#2166ac", "o", "60d: ERA5 wind vs heat"),
        (durable_skill, "ocean_plus_era5_wind", "delta_brier_vs_ocean_geometry", "delta_brier_vs_ocean_ci_low", "delta_brier_vs_ocean_ci_high", "#2166ac", "s", "60d: ocean+ERA5 vs ocean"),
    )
    labels = []
    for y, (skill, model, value_column, low_column, high_column, color, marker, label) in enumerate(comparisons):
        row = skill.loc[skill["model"] == model].iloc[0]
        value = float(row[value_column])
        error = np.asarray(
            [[value - float(row[low_column])], [float(row[high_column]) - value]]
        )
        axes[0].errorbar(value, y, xerr=error, fmt=marker, color=color, capsize=4, ms=6)
        labels.append(label)
    axes[0].axvline(0.0, color="0.25", lw=0.8)
    axes[0].set_yticks(np.arange(len(labels)), labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Paired LOEO Brier change")
    axes[0].set_title("a  Independent incremental skill", loc="left", fontweight="bold")
    axes[0].text(0.02, 0.03, "Better ←", transform=axes[0].transAxes, color="0.35")
    axes[0].spines[["top", "right"]].set_visible(False)

    both = events.loc[events["model"] == "ocean_plus_era5_wind"]
    for outcome, color, marker, offset, label in (
        ("30day_episode", "#b2182b", "o", -0.11, "30-day"),
        ("60day_durable", "#2166ac", "s", 0.11, "60-day"),
    ):
        current = both.loc[both["outcome"] == outcome].sort_values("year")
        axes[1].scatter(
            current["delta_brier_vs_ocean_geometry"],
            np.arange(len(current)) + offset,
            color=color,
            marker=marker,
            s=24,
            label=label,
            zorder=3,
        )
    years = sorted(both["year"].unique())
    axes[1].axvline(0.0, color="0.25", lw=0.8)
    axes[1].set_yticks(np.arange(len(years)), years)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Event Brier change vs ocean geometry")
    axes[1].set_title("b  Event-to-event replication", loc="left", fontweight="bold")
    axes[1].legend(frameon=False, fontsize=7.4, loc="lower right")
    axes[1].spines[["top", "right"]].set_visible(False)

    event = gate_comparison.loc[gate_comparison["year"] == 2023].sort_values("time")
    ocean_line = axes[2].plot(
        event["time"],
        event["ohc300_positive_east140w_fraction_15day"],
        color="#1b7837",
        lw=1.8,
        label="East-of-140°W heat fraction",
    )[0]
    axes[2].set_ylim(0.0, 1.0)
    axes[2].set_ylabel("East-of-140°W positive-OHC fraction", color="#1b7837")
    axes[2].tick_params(axis="y", colors="#1b7837")
    axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    wind_axis = axes[2].twinx()
    wind_line = wind_axis.plot(
        event["time"], event[ERA_GATE], color="#e08214", lw=1.5, label="ERA5 lagged wind gate"
    )[0]
    wind_axis.set_ylabel("ERA5 positive-u10 impulse (m s$^{-1}$)", color="#e08214")
    wind_axis.tick_params(axis="y", colors="#e08214")
    row = summaries.loc[summaries["year"] == 2023].iloc[0]
    axes[2].axvline(pd.Timestamp(row["coupling_onset_date"]), color="#111111", lw=1.1)
    axes[2].axvline(
        pd.Timestamp(row["sensitivity_8of12_durable_onset_date"]),
        color="#2166ac",
        lw=1.1,
        ls="--",
    )
    handles = [
        ocean_line,
        wind_line,
        mpl.lines.Line2D([], [], color="#111111", lw=1.1, label="30-day onset"),
        mpl.lines.Line2D([], [], color="#2166ac", lw=1.1, ls="--", label="60-day onset"),
    ]
    axes[2].legend(handles=handles, frameon=False, fontsize=7.0, loc="upper left")
    axes[2].set_title("c  Independent 2023 sequence", loc="left", fontweight="bold")
    axes[2].spines["top"].set_visible(False)
    wind_axis.spines["top"].set_visible(False)

    fig.suptitle(
        "Does ERA5 daily westerly memory independently predict SODA3-defined onset?",
        fontsize=12.5,
        fontweight="bold",
    )
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    plt.close(fig)


def write_report(
    primary_skill: pd.DataFrame,
    durable_skill: pd.DataFrame,
    events: pd.DataFrame,
    diagnostics: dict[str, object],
) -> None:
    p_wind = primary_skill.loc[primary_skill["model"] == "era5_wind_memory"].iloc[0]
    p_both = primary_skill.loc[primary_skill["model"] == "ocean_plus_era5_wind"].iloc[0]
    d_wind = durable_skill.loc[durable_skill["model"] == "era5_wind_memory"].iloc[0]
    d_both = durable_skill.loc[durable_skill["model"] == "ocean_plus_era5_wind"].iloc[0]
    wind_pass = bool(
        d_wind["delta_brier_vs_heat_ci_high"] < 0.0
        and d_wind["events_improved_vs_heat_only"] >= 7
        and d_wind["era5_gate_positive_fold_fraction"] >= 0.75
    )
    both_pass = bool(
        d_both["delta_brier_vs_ocean_ci_high"] < 0.0
        and d_both["events_improved_vs_ocean_geometry"] >= 7
        and d_both["era5_gate_positive_fold_fraction"] >= 0.75
    )
    if wind_pass and both_pass:
        judgment = "ERA5逐日西风门在两个预设比较中均通过，SODA3高频门得到独立资料支持。"
    elif wind_pass or both_pass:
        judgment = "ERA5逐日西风门只在一个预设比较中通过，得到部分独立支持，但尚未形成唯一闭合模型。"
    else:
        judgment = "ERA5逐日西风门未通过预设独立复核，SODA3高频结果不能视为跨资料稳定转折点。"
    event_2023 = events.loc[
        (events["year"] == 2023) & (events["model"] == "ocean_plus_era5_wind")
    ].set_index("outcome")
    text = f"""# ERA5逐日西风门对SODA3接通的独立复核

## 设计

ERA5 5°S—5°N、180°—140°W逐日10 m纬向风减去1982—2024同月线性预期。每个五日预测只使用此前15个完整UTC日的正西风异常；目标仍为SODA3定义的30天西风段与60天耐久接通。

## 30天目标

- ERA5风记忆相对仅热量：Brier变化{p_wind['delta_brier_vs_heat_only']:+.4f}，95%区间[{p_wind['delta_brier_vs_heat_ci_low']:+.4f}, {p_wind['delta_brier_vs_heat_ci_high']:+.4f}]，{int(p_wind['events_improved_vs_heat_only'])}/10事件改善。
- 海洋位置加ERA5风相对海洋位置：Brier变化{p_both['delta_brier_vs_ocean_geometry']:+.4f}，95%区间[{p_both['delta_brier_vs_ocean_ci_low']:+.4f}, {p_both['delta_brier_vs_ocean_ci_high']:+.4f}]，{int(p_both['events_improved_vs_ocean_geometry'])}/10事件改善。

## 60天耐久目标

- ERA5风记忆相对仅热量：Brier变化{d_wind['delta_brier_vs_heat_only']:+.4f}，95%区间[{d_wind['delta_brier_vs_heat_ci_low']:+.4f}, {d_wind['delta_brier_vs_heat_ci_high']:+.4f}]，{int(d_wind['events_improved_vs_heat_only'])}/10事件改善，风门系数正号比例{d_wind['era5_gate_positive_fold_fraction']:.0%}。
- 海洋位置加ERA5风相对海洋位置：Brier变化{d_both['delta_brier_vs_ocean_geometry']:+.4f}，95%区间[{d_both['delta_brier_vs_ocean_ci_low']:+.4f}, {d_both['delta_brier_vs_ocean_ci_high']:+.4f}]，{int(d_both['events_improved_vs_ocean_geometry'])}/10事件改善，风门系数正号比例{d_both['era5_gate_positive_fold_fraction']:.0%}。

## 跨资料一致性与2023

所有可比五日中，ERA5逐日门与SODA3五日门的相关系数为{diagnostics['era5_soda_gate_correlation']:+.2f}；逐事件相关中位数为{diagnostics['median_event_gate_correlation']:+.2f}。在实际30天和60天风险集中，相关分别为{diagnostics['primary_risk_gate_correlation']:+.2f}和{diagnostics['durable_risk_gate_correlation']:+.2f}。2023年海洋位置加ERA5风相对海洋位置的事件Brier变化：30天{float(event_2023.loc['30day_episode', 'delta_brier_vs_ocean_geometry']):+.4f}，60天{float(event_2023.loc['60day_durable', 'delta_brier_vs_ocean_geometry']):+.4f}。

## 判断

{judgment}

两套门的高相关说明ERA5与SODA3一致识别了大尺度西风脉冲；但接通目标由SODA3风应力正负与持续天数定义，阈值附近的小幅产品差异足以改变事件起始判断。因此，高相关没有转化为可移植预测技巧。独立复现回答的是“过去15天的近地面西风状态能否跨资料预测SODA3接通”；只有跨资料技巧和事件稳定性同时成立，才可把高频西风持续性保留为转折门。
"""
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    daily = load_daily_u10()
    daily.to_csv(DAILY_INDEX_CSV, index=False)
    indices = base.load_indices(base.INPUT_INDEX)
    summaries = base.event_summary(indices)
    eligible_indices = indices.loc[indices["year"].isin(EVENT_YEARS)].copy()
    all_gate = gate_for_times(eligible_indices[["year", "time"]], daily)
    soda = soda_gate.add_strictly_lagged_wind_gate(eligible_indices)[
        ["year", "time", soda_gate.GATE_COLUMN]
    ]
    gate_comparison = eligible_indices[
        ["year", "time", "ohc300_positive_east140w_fraction_15day"]
    ].merge(all_gate, on=["year", "time"], validate="one_to_one").merge(
        soda, on=["year", "time"], validate="one_to_one"
    )
    gate_comparison.to_csv(GATE_COMPARISON_CSV, index=False)
    comparable = gate_comparison.dropna(subset=[ERA_GATE, soda_gate.GATE_COLUMN])
    event_correlations = comparable.groupby("year").apply(
        lambda frame: frame[ERA_GATE].corr(frame[soda_gate.GATE_COLUMN]),
        include_groups=False,
    )
    primary_risk = build_gated_risk(indices, daily)
    durable_risk = build_gated_risk(
        indices,
        daily,
        positive_count=base.DURABLE_POSITIVE_COUNT,
        window_pentads=base.DURABLE_WINDOW_PENTADS,
    )
    primary_gate_check = primary_risk[["year", "time"]].merge(
        comparable[["year", "time", ERA_GATE, soda_gate.GATE_COLUMN]],
        on=["year", "time"],
        validate="one_to_one",
    )
    durable_gate_check = durable_risk[["year", "time"]].merge(
        comparable[["year", "time", ERA_GATE, soda_gate.GATE_COLUMN]],
        on=["year", "time"],
        validate="one_to_one",
    )
    primary_predictions, primary_coefficients = loeo(primary_risk, "30day_episode")
    durable_predictions, durable_coefficients = loeo(durable_risk, "60day_durable")
    primary_skill, primary_events = summarize_skill(primary_predictions, primary_coefficients)
    durable_skill, durable_events = summarize_skill(durable_predictions, durable_coefficients)
    coefficients = pd.concat([primary_coefficients, durable_coefficients], ignore_index=True)
    events = pd.concat([primary_events, durable_events], ignore_index=True)
    primary_predictions.to_csv(PRIMARY_PREDICTIONS_CSV, index=False)
    durable_predictions.to_csv(DURABLE_PREDICTIONS_CSV, index=False)
    primary_skill.to_csv(PRIMARY_SKILL_CSV, index=False)
    durable_skill.to_csv(DURABLE_SKILL_CSV, index=False)
    coefficients.to_csv(COEFFICIENTS_CSV, index=False)
    events.to_csv(EVENT_DELTAS_CSV, index=False)
    pd.concat(
        [
            primary_risk.assign(outcome="30day_episode"),
            durable_risk.assign(outcome="60day_durable"),
        ],
        ignore_index=True,
    ).to_csv(RISK_SET_CSV, index=False)
    diagnostics = {
        "daily_records": len(daily),
        "hourly_count_per_day": 24,
        "monthly_baseline": "1982-2024 calendar-month linear expectation",
        "gate_window": "15 complete UTC days ending t-1",
        "primary_risk_rows": len(primary_risk),
        "durable_risk_rows": len(durable_risk),
        "era5_soda_gate_correlation": float(
            comparable[ERA_GATE].corr(comparable[soda_gate.GATE_COLUMN])
        ),
        "median_event_gate_correlation": float(event_correlations.median()),
        "primary_risk_gate_correlation": float(
            primary_gate_check[ERA_GATE].corr(primary_gate_check[soda_gate.GATE_COLUMN])
        ),
        "durable_risk_gate_correlation": float(
            durable_gate_check[ERA_GATE].corr(durable_gate_check[soda_gate.GATE_COLUMN])
        ),
        "event_gate_correlations": {
            str(int(year)): float(value) for year, value in event_correlations.items()
        },
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    plot_results(primary_skill, durable_skill, events, gate_comparison, summaries)
    write_report(primary_skill, durable_skill, events, diagnostics)
    print("Primary 30-day episode")
    print(primary_skill.to_string(index=False))
    print("\nDurable 60-day onset")
    print(durable_skill.to_string(index=False))
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
