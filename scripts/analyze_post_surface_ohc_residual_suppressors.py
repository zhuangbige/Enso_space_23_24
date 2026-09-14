#!/usr/bin/env python3
"""Test candidate suppressors of the atmosphere residual after SST and OHC.

The parent analysis controls the May--June tropical-Pacific SST pattern and
March--April central-Pacific 0--300 m OHC for 13 warm events.  This extension
asks whether the remaining atmospheric response can be predicted by:

1. concurrent May--June tropical Indian Ocean and tropical North Atlantic
   warmth; and
2. the preceding January--April central-Pacific 850-hPa zonal-wind state.

Every prediction remains leave-one-event-out.  The external-basin predictor is
predefined as the equal mean of the two basin SST anomalies.  It is tested both
with the observed trend retained (primary) and after a same-month linear trend
is removed (sensitivity).  The analysis is an observational falsification and
routing test, not a causal substitute for a prescribed-SST AGCM experiment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


RUNTIME = Path("/private/tmp/codex_residual_suppressors")
RUNTIME.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, "/Users/daiyue/.codex/skills/climate-plotting/scripts")

import analyze_surface_sst_ohc_atmosphere_mediation as parent  # noqa: E402
from climate_plot_style import add_panel_labels, apply_climate_style  # noqa: E402


DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/post_surface_ohc_residual_suppressors"

EXTERNAL_CSV = ROOT / "data/interim/raw_validation/oisst_external_basin_monthly.csv"
MONTHLY_CSV = DERIVED / "enso_type_coupling_monthly_1982_2023.csv"
PARENT_PREDICTIONS = DERIVED / "surface_sst_ohc_atmosphere_mediation_loeo_predictions.csv"

EVENT_OUT = DERIVED / "post_surface_ohc_residual_suppressor_event_table.csv"
PRED_OUT = DERIVED / "post_surface_ohc_residual_suppressor_loeo_predictions.csv"
SKILL_OUT = DERIVED / "post_surface_ohc_residual_suppressor_skill.csv"
INCREMENT_OUT = DERIVED / "post_surface_ohc_residual_suppressor_increment_tests.csv"
ASSOCIATION_OUT = DERIVED / "post_surface_ohc_residual_suppressor_associations.csv"
SENSITIVITY_OUT = DERIVED / "post_surface_ohc_residual_suppressor_sensitivity.csv"
DIAGNOSTICS_OUT = DERIVED / "post_surface_ohc_residual_suppressor_diagnostics.json"

FIGURE_PNG = OUT / "fig_post_surface_ohc_residual_suppressors.png"
FIGURE_PDF = OUT / "fig_post_surface_ohc_residual_suppressors.pdf"
REPORT_MD = OUT / "POST_SURFACE_OHC_RESIDUAL_SUPPRESSORS_CN.md"

EVENT_YEARS = parent.EVENT_YEARS
PRIMARY_PCS = parent.PRIMARY_PCS
PRIMARY_ALPHA = parent.PRIMARY_ALPHA
PRIMARY_WIND_MONTHS = (1, 2, 3, 4)
EXTERNAL_MONTHS = (5, 6)
EXTERNAL_BASELINE = (1982, 2023)
TREND_RETAINED_CLIMATOLOGY = (1982, 2022)
RNG_SEED = 20260816

MODEL_ORDER = [
    "Pacific SST + OHC",
    "+ external warmth",
    "+ preceding wind",
    "+ external + wind",
]
MODEL_COLORS = {
    "Pacific SST + OHC": "#4C78A8",
    "+ external warmth": "#E45756",
    "+ preceding wind": "#2A9D8F",
    "+ external + wind": "#7A3DB8",
}
MODEL_SHORT = {
    "Pacific SST + OHC": "Base",
    "+ external warmth": "+ external",
    "+ preceding wind": "+ Jan-Apr wind",
    "+ external + wind": "+ both",
}


def build_external_features() -> pd.DataFrame:
    source = pd.read_csv(EXTERNAL_CSV)
    required = {
        "tropical_indian_ocean": "tio",
        "tropical_north_atlantic": "tna",
    }
    pieces: list[pd.DataFrame] = []
    for region, prefix in required.items():
        selected = source.loc[
            source.region.eq(region) & source.month.isin(EXTERNAL_MONTHS)
        ].copy()
        selected = selected.sort_values(["year", "month"]).reset_index(drop=True)
        times = pd.DatetimeIndex(
            pd.to_datetime(
                {"year": selected.year, "month": selected.month, "day": 1}
            )
        )
        selected["detrended_anomaly"] = parent.same_month_residual_1d(
            selected.sst.to_numpy(dtype=float), times, EXTERNAL_BASELINE
        )
        annual = (
            selected.groupby("year", as_index=False)
            .agg(
                **{
                    f"{prefix}_trend_retained_anomaly_c": ("anomaly", "mean"),
                    f"{prefix}_detrended_anomaly_c": (
                        "detrended_anomaly",
                        "mean",
                    ),
                    f"{prefix}_absolute_sst_c": ("sst", "mean"),
                }
            )
            .loc[lambda frame: frame.year.isin(EVENT_YEARS)]
        )
        if len(annual) != len(EVENT_YEARS):
            raise ValueError(f"Incomplete external SST events for {region}")
        pieces.append(annual)

    output = pieces[0].merge(pieces[1], on="year", validate="one_to_one")
    output["external_warmth_trend_retained_c"] = output[
        ["tio_trend_retained_anomaly_c", "tna_trend_retained_anomaly_c"]
    ].mean(axis=1)
    output["external_warmth_detrended_c"] = output[
        ["tio_detrended_anomaly_c", "tna_detrended_anomaly_c"]
    ].mean(axis=1)
    return output


def build_preceding_wind_features() -> pd.DataFrame:
    monthly = pd.read_csv(MONTHLY_CSV)
    if "u850_cwp_anom_ms" not in monthly:
        raise KeyError("u850_cwp_anom_ms missing from monthly coupling table")
    rows: list[dict[str, float | int]] = []
    windows = {
        "jan_feb": (1, 2),
        "jan_mar": (1, 3),
        "jan_apr": (1, 4),
        "mar_apr": (3, 4),
    }
    for year in EVENT_YEARS:
        event = monthly.loc[monthly.year.eq(year)].copy()
        row: dict[str, float | int] = {"year": int(year)}
        for name, (month0, month1) in windows.items():
            selected = event.loc[event.month.between(month0, month1)]
            expected = month1 - month0 + 1
            if len(selected) != expected:
                raise ValueError(f"Incomplete {name} wind window for {year}")
            row[f"u850_{name}_anom_ms"] = float(selected.u850_cwp_anom_ms.mean())
        primary = event.loc[
            event.month.between(PRIMARY_WIND_MONTHS[0], PRIMARY_WIND_MONTHS[-1])
        ]
        row["jan_apr_easterly_month_count"] = int(
            (primary.u850_cwp_anom_ms < 0.0).sum()
        )
        rows.append(row)
    return pd.DataFrame(rows)


def model_inputs(table: pd.DataFrame) -> dict[str, np.ndarray]:
    surface = table[
        [
            "cp_absolute_sst_c",
            "warm_area_fraction_27p5",
            "warm_excess_centroid_lon_e",
        ]
    ].to_numpy(dtype=float)
    ohc = table[["ohc300_central_ma_gj_m2"]].to_numpy(dtype=float)
    base = np.column_stack([surface, ohc])
    external = table[["external_warmth_trend_retained_c"]].to_numpy(dtype=float)
    wind = table[["u850_jan_apr_anom_ms"]].to_numpy(dtype=float)
    return {
        "Pacific SST + OHC": base,
        "+ external warmth": np.column_stack([base, external]),
        "+ preceding wind": np.column_stack([base, wind]),
        "+ external + wind": np.column_stack([base, external, wind]),
    }


def bootstrap_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    return parent.bootstrap_mean_ci(np.asarray(values, dtype=float), seed)


def run_primary_models(
    table: pd.DataFrame,
    anomaly_maps: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    specifications = model_inputs(table)
    prediction_rows: list[dict[str, float | int | str]] = []
    skill_rows: list[dict[str, float | int | str]] = []
    increment_rows: list[dict[str, float | int | str]] = []
    association_rows: list[dict[str, float | int | str]] = []

    factors = {
        "external_warmth_trend_retained_c": table.external_warmth_trend_retained_c.to_numpy(
            dtype=float
        ),
        "external_warmth_detrended_c": table.external_warmth_detrended_c.to_numpy(
            dtype=float
        ),
        "u850_jan_apr_anom_ms": table.u850_jan_apr_anom_ms.to_numpy(dtype=float),
    }
    target_index = int(np.flatnonzero(table.year.to_numpy() == 2023)[0])

    for response_offset, response in enumerate(parent.RESPONSE_META):
        y = table[response].to_numpy(dtype=float)
        results: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for model, extras in specifications.items():
            predicted, scale = parent.loeo_predictions(
                y,
                map_values=anomaly_maps,
                extra_values=extras,
                n_components=PRIMARY_PCS,
                alpha=PRIMARY_ALPHA,
            )
            error = (y - predicted) / scale
            results[model] = (predicted, scale, error)
            skill_rows.append(
                {
                    "response": response,
                    "response_label": parent.RESPONSE_META[response][0],
                    "model": model,
                    "n_events": len(table),
                    "loeo_rmse_sd": float(np.sqrt(np.mean(error**2))),
                    "loeo_correlation": float(np.corrcoef(y, predicted)[0, 1]),
                    "loeo_mean_error_sd": float(error.mean()),
                    "n_pcs": PRIMARY_PCS,
                    "ridge_alpha": PRIMARY_ALPHA,
                }
            )
            for event, observed, expected, residual, fold_scale in zip(
                table.itertuples(index=False),
                y,
                predicted,
                error,
                scale,
                strict=True,
            ):
                prediction_rows.append(
                    {
                        "year": int(event.year),
                        "group": str(event.group),
                        "response": response,
                        "response_label": parent.RESPONSE_META[response][0],
                        "model": model,
                        "observed": float(observed),
                        "predicted": float(expected),
                        "error_sd": float(residual),
                        "training_response_sd": float(fold_scale),
                    }
                )

        base_error = results["Pacific SST + OHC"][2]
        for model_offset, model in enumerate(MODEL_ORDER[1:]):
            error = results[model][2]
            delta = error**2 - base_error**2
            low, high = bootstrap_ci(
                delta, RNG_SEED + 100 * response_offset + model_offset
            )
            increment_rows.append(
                {
                    "response": response,
                    "response_label": parent.RESPONSE_META[response][0],
                    "model": model,
                    "base_rmse_sd": float(np.sqrt(np.mean(base_error**2))),
                    "extended_rmse_sd": float(np.sqrt(np.mean(error**2))),
                    "rmse_change_extended_minus_base_sd": float(
                        np.sqrt(np.mean(error**2))
                        - np.sqrt(np.mean(base_error**2))
                    ),
                    "mean_squared_error_change": float(delta.mean()),
                    "mse_change_bootstrap_ci_low": low,
                    "mse_change_bootstrap_ci_high": high,
                    "exact_sign_flip_p_extended_improves": parent.exact_sign_flip_p(
                        delta, alternative="less"
                    ),
                    "residual_2023_base_sd": float(base_error[target_index]),
                    "residual_2023_extended_sd": float(error[target_index]),
                    "residual_2023_extended_lower_rank": int(
                        stats.rankdata(error, method="min")[target_index]
                    ),
                }
            )

        for factor_offset, (factor, values) in enumerate(factors.items()):
            association_rows.append(
                {
                    "response": response,
                    "response_label": parent.RESPONSE_META[response][0],
                    "factor": factor,
                    "pearson_r_with_base_loeo_residual": float(
                        np.corrcoef(values, base_error)[0, 1]
                    ),
                    "permutation_p_two_sided": parent.permutation_correlation_p(
                        values,
                        base_error,
                        RNG_SEED + 500 + 10 * response_offset + factor_offset,
                    ),
                }
            )

    return (
        pd.DataFrame(prediction_rows),
        pd.DataFrame(skill_rows),
        pd.DataFrame(increment_rows),
        pd.DataFrame(association_rows),
    )


def run_sensitivity(
    table: pd.DataFrame,
    anomaly_maps: np.ndarray,
) -> pd.DataFrame:
    surface = table[
        [
            "cp_absolute_sst_c",
            "warm_area_fraction_27p5",
            "warm_excess_centroid_lon_e",
        ]
    ].to_numpy(dtype=float)
    ohc = table[["ohc300_central_ma_gj_m2"]].to_numpy(dtype=float)
    base = np.column_stack([surface, ohc])
    additions = {
        "external_trend_retained": table[
            ["external_warmth_trend_retained_c"]
        ].to_numpy(dtype=float),
        "external_detrended": table[["external_warmth_detrended_c"]].to_numpy(
            dtype=float
        ),
        "wind_jan_feb": table[["u850_jan_feb_anom_ms"]].to_numpy(dtype=float),
        "wind_jan_mar": table[["u850_jan_mar_anom_ms"]].to_numpy(dtype=float),
        "wind_jan_apr": table[["u850_jan_apr_anom_ms"]].to_numpy(dtype=float),
        "wind_mar_apr": table[["u850_mar_apr_anom_ms"]].to_numpy(dtype=float),
        "external_plus_wind": table[
            ["external_warmth_trend_retained_c", "u850_jan_apr_anom_ms"]
        ].to_numpy(dtype=float),
    }
    y = table.atmosphere_composite_z.to_numpy(dtype=float)
    rows: list[dict[str, float | int | str]] = []
    for components in (1, 2, 3):
        for alpha in (0.1, 1.0, 10.0):
            base_prediction, base_scale = parent.loeo_predictions(
                y,
                map_values=anomaly_maps,
                extra_values=base,
                n_components=components,
                alpha=alpha,
            )
            base_error = (y - base_prediction) / base_scale
            base_rmse = float(np.sqrt(np.mean(base_error**2)))
            for name, addition in additions.items():
                prediction, scale = parent.loeo_predictions(
                    y,
                    map_values=anomaly_maps,
                    extra_values=np.column_stack([base, addition]),
                    n_components=components,
                    alpha=alpha,
                )
                error = (y - prediction) / scale
                rows.append(
                    {
                        "addition": name,
                        "n_pcs": components,
                        "ridge_alpha": alpha,
                        "base_rmse_sd": base_rmse,
                        "extended_rmse_sd": float(np.sqrt(np.mean(error**2))),
                        "rmse_change_extended_minus_base_sd": float(
                            np.sqrt(np.mean(error**2)) - base_rmse
                        ),
                        "residual_2023_sd": float(error[-1]),
                    }
                )
    return pd.DataFrame(rows)


def validate_parent_reproduction(
    predictions: pd.DataFrame,
) -> float:
    saved = pd.read_csv(PARENT_PREDICTIONS)
    saved = saved.loc[
        saved.response.eq("atmosphere_composite_z")
        & saved.model.eq("Full SST pattern + OHC")
    ].set_index("year").loc[EVENT_YEARS]
    current = predictions.loc[
        predictions.response.eq("atmosphere_composite_z")
        & predictions.model.eq("Pacific SST + OHC")
    ].set_index("year").loc[EVENT_YEARS]
    difference = float(
        np.max(np.abs(saved.predicted.to_numpy() - current.predicted.to_numpy()))
    )
    if difference > 1.0e-6:
        raise ValueError(f"Parent prediction reproduction failed: {difference}")
    return difference


def annotate_years(
    axis: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    years: np.ndarray,
) -> None:
    for xv, yv, year in zip(x, y, years, strict=True):
        important = int(year) in (1997, 2015, 2023)
        axis.scatter(
            xv,
            yv,
            s=72 if important else 36,
            color="#7A3DB8" if int(year) == 2023 else "#4C78A8",
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )
        if important:
            axis.annotate(
                str(int(year)),
                (xv, yv),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=8,
                fontweight="bold",
            )


def plot_results(
    table: pd.DataFrame,
    predictions: pd.DataFrame,
    skill: pd.DataFrame,
    increment: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    apply_climate_style(base_font_size=9.5)
    plt.rcParams.update({"pdf.fonttype": 42, "axes.unicode_minus": False})
    fig, axes = plt.subplots(2, 3, figsize=(17.2, 9.8))
    ax_skill, ax_delta, ax_target, ax_wind, ax_external, ax_robust = axes.ravel()

    responses = list(parent.RESPONSE_META)
    x = np.arange(len(responses))
    width = 0.19
    for offset, model in enumerate(MODEL_ORDER):
        current = skill.loc[skill.model.eq(model)].set_index("response").loc[responses]
        ax_skill.bar(
            x + (offset - 1.5) * width,
            current.loeo_rmse_sd,
            width=width,
            color=MODEL_COLORS[model],
            label=MODEL_SHORT[model],
        )
    ax_skill.set_xticks(
        x,
        [parent.RESPONSE_META[item][0] for item in responses],
        rotation=24,
        ha="right",
    )
    ax_skill.set_ylabel("LOEO RMSE (SD)")
    ax_skill.set_title("Out-of-event prediction after adding candidates")
    ax_skill.grid(axis="y", color="#DDDDDD", linewidth=0.6)
    ax_skill.legend(frameon=False, ncol=2, fontsize=8)

    composite_increment = increment.loc[
        increment.response.eq("atmosphere_composite_z")
    ].set_index("model").loc[MODEL_ORDER[1:]]
    values = composite_increment.mean_squared_error_change.to_numpy(dtype=float)
    low = values - composite_increment.mse_change_bootstrap_ci_low.to_numpy(dtype=float)
    high = composite_increment.mse_change_bootstrap_ci_high.to_numpy(dtype=float) - values
    ypos = np.arange(len(values))
    ax_delta.errorbar(
        values,
        ypos,
        xerr=np.vstack([low, high]),
        fmt="none",
        ecolor="#555555",
        capsize=3,
        linewidth=1.2,
    )
    ax_delta.scatter(
        values,
        ypos,
        c=[MODEL_COLORS[name] for name in MODEL_ORDER[1:]],
        s=70,
        zorder=3,
    )
    ax_delta.axvline(0.0, color="black", linewidth=0.8)
    ax_delta.set_yticks(ypos, [MODEL_SHORT[name] for name in MODEL_ORDER[1:]])
    ax_delta.invert_yaxis()
    ax_delta.set_xlabel("Change in squared LOEO error\n(negative = improvement)")
    ax_delta.set_title("Composite-response increment test")
    ax_delta.grid(axis="x", color="#DDDDDD", linewidth=0.6)

    target = predictions.loc[predictions.year.eq(2023)].copy()
    target = target.pivot(index="response", columns="model", values="error_sd").loc[
        responses, MODEL_ORDER
    ]
    for offset, model in enumerate(MODEL_ORDER):
        ax_target.scatter(
            x + (offset - 1.5) * 0.12,
            target[model],
            s=52,
            color=MODEL_COLORS[model],
            label=MODEL_SHORT[model],
        )
    ax_target.axhline(0.0, color="black", linewidth=0.8)
    ax_target.set_xticks(
        x,
        [parent.RESPONSE_META[item][0] for item in responses],
        rotation=24,
        ha="right",
    )
    ax_target.set_ylabel("2023 observed minus predicted (SD)")
    ax_target.set_title("2023 remains weaker than every conditional expectation")
    ax_target.grid(axis="y", color="#DDDDDD", linewidth=0.6)

    base_composite = predictions.loc[
        predictions.response.eq("atmosphere_composite_z")
        & predictions.model.eq("Pacific SST + OHC")
    ].set_index("year").loc[EVENT_YEARS]
    wind = table.set_index("year").loc[EVENT_YEARS, "u850_jan_apr_anom_ms"].to_numpy()
    residual = base_composite.error_sd.to_numpy(dtype=float)
    annotate_years(ax_wind, wind, residual, EVENT_YEARS)
    slope, intercept = np.polyfit(wind, residual, 1)
    line = np.linspace(wind.min(), wind.max(), 100)
    ax_wind.plot(line, intercept + slope * line, color="#333333", linewidth=1.0)
    ax_wind.axhline(0.0, color="#777777", linewidth=0.7)
    ax_wind.axvline(0.0, color="#777777", linewidth=0.7)
    ax_wind.set_xlabel("Jan-Apr central-Pacific u850 anomaly (m s$^{-1}$)")
    ax_wind.set_ylabel("Base composite residual (SD)")
    ax_wind.set_title("Preceding wind state: useful, but 2023 still an outlier")
    ax_wind.grid(color="#E1E1E1", linewidth=0.6)

    base_u850 = predictions.loc[
        predictions.response.eq("u850_response_z")
        & predictions.model.eq("Pacific SST + OHC")
    ].set_index("year").loc[EVENT_YEARS]
    external = table.set_index("year").loc[
        EVENT_YEARS, "external_warmth_trend_retained_c"
    ].to_numpy()
    wind_residual = base_u850.error_sd.to_numpy(dtype=float)
    annotate_years(ax_external, external, wind_residual, EVENT_YEARS)
    slope, intercept = np.polyfit(external, wind_residual, 1)
    line = np.linspace(external.min(), external.max(), 100)
    ax_external.plot(line, intercept + slope * line, color="#333333", linewidth=1.0)
    ax_external.axhline(0.0, color="#777777", linewidth=0.7)
    ax_external.axvline(0.0, color="#777777", linewidth=0.7)
    ax_external.set_xlabel("May-Jun TIO/TNA warmth (°C; trend retained)")
    ax_external.set_ylabel("Base u850 residual (SD)")
    ax_external.set_title("External warmth is exceptional in 2023, not a stable predictor")
    ax_external.grid(color="#E1E1E1", linewidth=0.6)

    robust_names = [
        "external_trend_retained",
        "external_detrended",
        "wind_jan_apr",
        "external_plus_wind",
    ]
    robust_labels = [
        "External\ntrend retained",
        "External\ndetrended",
        "Jan-Apr\nwind",
        "External\n+ wind",
    ]
    robust_colors = ["#E45756", "#F28E8B", "#2A9D8F", "#7A3DB8"]
    rng = np.random.default_rng(RNG_SEED)
    for position, (name, color) in enumerate(zip(robust_names, robust_colors, strict=True)):
        values = sensitivity.loc[
            sensitivity.addition.eq(name), "rmse_change_extended_minus_base_sd"
        ].to_numpy(dtype=float)
        jitter = rng.uniform(-0.08, 0.08, size=len(values))
        ax_robust.scatter(
            position + jitter,
            values,
            s=33,
            color=color,
            alpha=0.82,
            edgecolor="white",
            linewidth=0.4,
        )
        ax_robust.plot(
            [position - 0.17, position + 0.17],
            [np.median(values), np.median(values)],
            color="black",
            linewidth=1.5,
        )
    ax_robust.axhline(0.0, color="black", linewidth=0.8)
    ax_robust.set_xticks(np.arange(len(robust_names)), robust_labels)
    ax_robust.set_ylabel("Composite RMSE change (SD)")
    ax_robust.set_title("Sensitivity across PC count and ridge penalty")
    ax_robust.grid(axis="y", color="#DDDDDD", linewidth=0.6)

    add_panel_labels(list(axes.ravel()))
    fig.suptitle(
        "What remains after controlling Pacific SST structure and subsurface OHC?",
        fontsize=17,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.06,
        0.018,
        "13 warm events. Base: May-Jun Pacific OISST pattern + absolute-SST metrics + Mar-Apr SODA3 0-300 m OHC. "
        "External: May-Jun OISST TIO/TNA mean anomaly. Preceding wind: Jan-Apr ERA5 central-Pacific u850 anomaly. "
        "All predictions are leave-one-event-out; negative residual means the atmosphere is weaker than expected.",
        fontsize=8.4,
        color="#555555",
    )
    fig.subplots_adjust(left=0.065, right=0.985, top=0.92, bottom=0.12, hspace=0.40, wspace=0.30)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, dpi=360, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(
    table: pd.DataFrame,
    skill: pd.DataFrame,
    increment: pd.DataFrame,
    associations: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    composite_skill = skill.loc[
        skill.response.eq("atmosphere_composite_z")
    ].set_index("model").loc[MODEL_ORDER]
    composite_inc = increment.loc[
        increment.response.eq("atmosphere_composite_z")
    ].set_index("model").loc[MODEL_ORDER[1:]]
    target = table.loc[table.year.eq(2023)].iloc[0]
    component_inc = increment.loc[
        increment.model.eq("+ external warmth")
    ].set_index("response")
    primary_association = associations.loc[
        associations.response.eq("atmosphere_composite_z")
    ].set_index("factor")
    lead_sensitivity = sensitivity.loc[sensitivity.addition.eq("wind_jan_apr")]
    ext_sensitivity = sensitivity.loc[
        sensitivity.addition.eq("external_trend_retained")
    ]

    lines = [
        "# 控制太平洋 SSTA 与 OHC 后的大气残差：外海盆与前期风场检验",
        "",
        "## 结论",
        "",
        "这一步没有把 2023 年的剩余弱响应归结为一个新的单一观测指标。"
        "前期风场对跨事件预测有小幅、方向一致的增益，但 2023 仍是最弱的条件残差之一；"
        "外海盆增暖作为普通线性预测项则不能改善综合大气响应。",
        "",
        f"基础模型（太平洋完整 SSTA 形态、绝对 SST 对流条件和 SODA3 0—300 m OHC）的综合响应 LOEO RMSE 为 "
        f"{composite_skill.loc['Pacific SST + OHC', 'loeo_rmse_sd']:.3f} SD。"
        f"加入 1—4 月前期 u850 后降至 {composite_skill.loc['+ preceding wind', 'loeo_rmse_sd']:.3f} SD；"
        f"均方误差变化为 {composite_inc.loc['+ preceding wind', 'mean_squared_error_change']:+.3f}，"
        f"精确符号翻转检验 p={composite_inc.loc['+ preceding wind', 'exact_sign_flip_p_extended_improves']:.3f}。"
        "这是边界性支持，不是 5% 水平的决定性证据。",
        "",
        f"加入趋势保留的印度洋—热带北大西洋增暖后，综合 RMSE 为 "
        f"{composite_skill.loc['+ external warmth', 'loeo_rmse_sd']:.3f} SD，"
        f"均方误差变化 {composite_inc.loc['+ external warmth', 'mean_squared_error_change']:+.3f}。"
        "因此外海盆增暖不是 13 次事件中稳定的线性残差预测器。",
        "",
        "## 2023 年的含义",
        "",
        f"2023 年 5—6 月的 TIO/TNA 平均暖异常为 {target.external_warmth_trend_retained_c:.3f} ℃，"
        f"其中 TNA 为 {target.tna_trend_retained_anomaly_c:.3f} ℃、TIO 为 {target.tio_trend_retained_anomaly_c:.3f} ℃；"
        f"1—4 月中太平洋 u850 平均为 {target.u850_jan_apr_anom_ms:+.3f} m s⁻¹。",
        "",
        f"基础模型下 2023 综合残差为 {composite_inc.loc['+ preceding wind', 'residual_2023_base_sd']:+.3f} SD；"
        f"加入前期风后为 {composite_inc.loc['+ preceding wind', 'residual_2023_extended_sd']:+.3f} SD；"
        f"加入外海盆后反而为 {composite_inc.loc['+ external warmth', 'residual_2023_extended_sd']:+.3f} SD。"
        "也就是说，外海盆在 2023 的确异常暖，但历史事件协方差训练出的线性关系并不能把这种暖背景识别成抑制项。",
        "",
        "这并不等于外海盆没有物理作用。印度洋增暖常同时是 ENSO 的响应，TNA 又在 2023 处于历史分布边缘；"
        "观测回归会混合共同驱动、滞后响应和真正的跨海盆强迫。恰恰因为 2023 是分布外组合，"
        "规定 SST 的 AGCM 因子试验比继续增加回归指标更合适。",
        "",
        "## 分路径结果",
        "",
        f"外海盆项对 u850 的 RMSE 变化为 {component_inc.loc['u850_response_z', 'rmse_change_extended_minus_base_sd']:+.3f} SD，"
        f"对风应力为 {component_inc.loc['tau_response_z', 'rmse_change_extended_minus_base_sd']:+.3f} SD，"
        f"但对对流和降水分别为 {component_inc.loc['convection_response_z', 'rmse_change_extended_minus_base_sd']:+.3f} 与 "
        f"{component_inc.loc['precip_response_z', 'rmse_change_extended_minus_base_sd']:+.3f} SD。"
        "它最多提示风压通道和降水通道可能不同步，不能支持统一的外海盆抑制系数。",
        "",
        f"基础综合残差与趋势保留外海盆暖度的相关为 "
        f"r={primary_association.loc['external_warmth_trend_retained_c', 'pearson_r_with_base_loeo_residual']:+.3f}，"
        f"置换 p={primary_association.loc['external_warmth_trend_retained_c', 'permutation_p_two_sided']:.3f}；"
        f"与 1—4 月前期风的相关为 "
        f"r={primary_association.loc['u850_jan_apr_anom_ms', 'pearson_r_with_base_loeo_residual']:+.3f}，"
        f"置换 p={primary_association.loc['u850_jan_apr_anom_ms', 'permutation_p_two_sided']:.3f}。",
        "",
        "## 稳健性与边界",
        "",
        f"在 PC=1/2/3、ridge α=0.1/1/10 的九组设定中，加入 1—4 月前期风的 RMSE 变化范围为 "
        f"[{lead_sensitivity.rmse_change_extended_minus_base_sd.min():+.3f}, "
        f"{lead_sensitivity.rmse_change_extended_minus_base_sd.max():+.3f}] SD；"
        f"加入趋势保留外海盆项的范围为 "
        f"[{ext_sensitivity.rmse_change_extended_minus_base_sd.min():+.3f}, "
        f"{ext_sensitivity.rmse_change_extended_minus_base_sd.max():+.3f}] SD。",
        "",
        "本检验只能回答候选变量是否提供跨事件条件预测信息，不能把相关系数解释为因果效应。"
        "尤其不能用“外海盆线性项不改善 LOEO”否定针对 2023 的非线性强迫作用。",
        "",
        "## 下一项因果试验",
        "",
        "采用 2023 年实际太平洋 SST 作为共同背景，做 TIO/TNA 外海盆异常开/关的规定 SST AGCM 集合；"
        "在每个外海盆状态下再保留/移除 FEP 异常，形成 2×2 因子矩阵。主要响应量应为中太平洋降水、SLP 梯度、"
        "u850 和东向风应力。只有该试验可以判断外海盆强迫在给定太平洋 SST 后是否因果性削弱大气接通。",
        "",
        "## 数据与口径",
        "",
        "- 太平洋表层：OISST，5—6 月，15°S—15°N、120°E—80°W；训练折内 PCA。",
        "- 次表层：SODA3.15.2 位温计算的 0—300 m OHC 距平，3—4 月，5°S—5°N、180°—140°W。",
        "- 外海盆：OISST，TIO 为 20°S—20°N、40°—110°E，TNA 为 0°—20°N、60°—20°W；5—6 月。",
        "  趋势保留距平以 1982—2022 同月气候态为基准；去趋势敏感性以 1982—2023 同月线性拟合为基准。",
        "- 前期风：ERA5 850 hPa 纬向风距平，1—4 月中太平洋平均；正号为西风。",
        "- 响应：ERA5 5—6 月 u850、负 OLR、降水和东向风应力的等权标准化综合。",
        "- 样本：固定 13 次暖事件；所有模型使用留一事件预测。",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    for path in (EXTERNAL_CSV, MONTHLY_CSV, PARENT_PREDICTIONS):
        if not path.exists():
            raise FileNotFoundError(path)

    raw_sst, anomaly_sst = parent.open_oisst_may_june()
    _, anomaly_maps, _, _ = parent.flattened_event_maps(raw_sst, anomaly_sst)
    table = (
        parent.build_event_table(raw_sst, anomaly_sst)
        .merge(build_external_features(), on="year", validate="one_to_one")
        .merge(build_preceding_wind_features(), on="year", validate="one_to_one")
        .sort_values("year")
        .reset_index(drop=True)
    )
    if table.isna().any().any():
        raise ValueError(f"Missing values in event table: {table.columns[table.isna().any()].tolist()}")

    predictions, skill, increment, associations = run_primary_models(
        table, anomaly_maps
    )
    sensitivity = run_sensitivity(table, anomaly_maps)
    reproduction_difference = validate_parent_reproduction(predictions)

    OUT.mkdir(parents=True, exist_ok=True)
    EVENT_OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(EVENT_OUT, index=False)
    predictions.to_csv(PRED_OUT, index=False)
    skill.to_csv(SKILL_OUT, index=False)
    increment.to_csv(INCREMENT_OUT, index=False)
    associations.to_csv(ASSOCIATION_OUT, index=False)
    sensitivity.to_csv(SENSITIVITY_OUT, index=False)

    plot_results(table, predictions, skill, increment, sensitivity)
    write_report(table, skill, increment, associations, sensitivity)

    diagnostics = {
        "event_years": EVENT_YEARS.tolist(),
        "n_events": len(table),
        "primary_pcs": PRIMARY_PCS,
        "primary_ridge_alpha": PRIMARY_ALPHA,
        "external_months": list(EXTERNAL_MONTHS),
        "external_baseline": list(EXTERNAL_BASELINE),
        "trend_retained_climatology": list(TREND_RETAINED_CLIMATOLOGY),
        "preceding_wind_months": list(PRIMARY_WIND_MONTHS),
        "parent_prediction_max_abs_difference": reproduction_difference,
        "finite": {
            "event_table": bool(np.isfinite(table.select_dtypes(include=[np.number])).all().all()),
            "predictions": bool(np.isfinite(predictions.select_dtypes(include=[np.number])).all().all()),
            "skill": bool(np.isfinite(skill.select_dtypes(include=[np.number])).all().all()),
            "increment": bool(np.isfinite(increment.select_dtypes(include=[np.number])).all().all()),
            "sensitivity": bool(np.isfinite(sensitivity.select_dtypes(include=[np.number])).all().all()),
        },
        "outputs": {
            "figure_png": str(FIGURE_PNG),
            "figure_pdf": str(FIGURE_PDF),
            "report": str(REPORT_MD),
        },
    }
    if not all(diagnostics["finite"].values()):
        raise ValueError(f"Non-finite diagnostics: {diagnostics['finite']}")
    DIAGNOSTICS_OUT.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Wrote {FIGURE_PNG}")
    print(f"Wrote {FIGURE_PDF}")
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {DIAGNOSTICS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
