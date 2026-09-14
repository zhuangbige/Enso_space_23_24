#!/usr/bin/env python3
"""Test the third-question coupling chain with non-H20 heat-fate terms.

The 13 warm events are organized as a time-ordered chain:

    early three-dimensional OHC configuration
      -> May--June central-Pacific wind response
      -> following Jan--May local 5N wind stress
      -> mass-balanced 0--300 m northward anomalous-enthalpy output.

A separate thermodynamic branch links following-winter eastern SST to surface
heat loss.  Arrival heat across 140W is controlled where appropriate so the
analysis asks why comparable input can have different fates.  Event
permutations, event bootstraps, and leave-one-event-out diagnostics are all
reported; none is interpreted as coupled-model causal attribution.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_chakravorty2021_soda3_baseline as legacy  # noqa: E402


DATA = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/nonh20_third_question_chain"
BUDGET_EVENTS = DATA / "soda3_three_box_ohc_anomaly_budget_events.csv"
ARRIVAL_EVENTS = DATA / "arrival_configuration_coupling_routing_event_table.csv"
COUPLING_EVENTS = DATA / "third_question_coupled_attribution_event_table.csv"
PROCESS_MONTHLY = DATA / "soda3_ohc_only_monthly_1980_2024.csv"

EVENT_OUTPUT = DATA / "nonh20_third_question_event_table.csv"
RELATION_OUTPUT = DATA / "nonh20_third_question_relationships.csv"
MODEL_OUTPUT = DATA / "nonh20_third_question_loeo_models.csv"
PREDICTION_OUTPUT = DATA / "nonh20_third_question_loeo_predictions.csv"
MEDIATION_OUTPUT = DATA / "nonh20_third_question_mediation_summary.csv"
DIAGNOSTICS_OUTPUT = DATA / "nonh20_third_question_diagnostics.json"
REPORT_OUTPUT = OUT / "NONH20_THIRD_QUESTION_CHAIN_CN.md"

EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = (1997, 2015, 2023)
BASELINE = (1980, 2022)
N_BOOTSTRAP = 20_000
N_PERMUTATIONS = 20_000
RANDOM_SEED = 20260810


def zscore(values: np.ndarray | pd.Series) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    scale = float(np.std(data, ddof=1))
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("Cannot standardize a constant or invalid series")
    return (data - float(np.mean(data))) / scale


def residualize(values: np.ndarray, controls: np.ndarray | None) -> np.ndarray:
    y = np.asarray(values, dtype=float)
    if controls is None or np.asarray(controls).size == 0:
        return y - float(np.mean(y))
    c = np.asarray(controls, dtype=float)
    if c.ndim == 1:
        c = c[:, None]
    design = np.column_stack([np.ones(len(y)), c])
    return y - design @ np.linalg.lstsq(design, y, rcond=None)[0]


def correlation(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or np.std(x) <= 0.0 or np.std(y) <= 0.0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def partial_correlation(
    x: np.ndarray, y: np.ndarray, controls: np.ndarray | None = None
) -> float:
    return correlation(residualize(x, controls), residualize(y, controls))


def rank_correlation(x: np.ndarray, y: np.ndarray) -> float:
    xr = pd.Series(np.asarray(x, dtype=float)).rank().to_numpy()
    yr = pd.Series(np.asarray(y, dtype=float)).rank().to_numpy()
    return correlation(xr, yr)


def bh_fdr(pvalues: pd.Series) -> pd.Series:
    values = pvalues.to_numpy(dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.clip(adjusted, 0.0, 1.0)
    return pd.Series(output, index=pvalues.index)


def same_month_detrended(values: np.ndarray, times: pd.DatetimeIndex) -> np.ndarray:
    return legacy.same_month_detrended(values, times, BASELINE)


def decay_surface_state() -> pd.DataFrame:
    monthly = pd.read_csv(PROCESS_MONTHLY, parse_dates=["time"])
    times = pd.DatetimeIndex(monthly["time"])
    monthly["tau5n_decay_anom_nm2"] = same_month_detrended(
        monthly["tau5n_westward_raw_nm2"].to_numpy(), times
    )
    monthly["east_sst_decay_anom_c"] = same_month_detrended(
        monthly["east_sst_raw_c"].to_numpy(), times
    )
    rows = []
    for event in EVENTS:
        selected = monthly.loc[
            monthly.year.eq(event + 1) & monthly.month.between(1, 5)
        ]
        if len(selected) != 5:
            raise ValueError(f"Incomplete following Jan-May process window: {event}")
        rows.append(
            {
                "event_year": event,
                "decay_tau5n_westward_nm2": float(
                    selected["tau5n_decay_anom_nm2"].mean()
                ),
                "decay_east_sst_anom_c": float(
                    selected["east_sst_decay_anom_c"].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def load_event_table() -> pd.DataFrame:
    budget = pd.read_csv(BUDGET_EVENTS)
    decay = budget.loc[
        budget.box.eq("east") & budget.phase.eq("decay_Jan_May_next")
    ].copy()
    arrival = budget.loc[
        budget.box.eq("east") & budget.phase.eq("arrival_Jan_Jun"),
        [
            "event_year",
            "west_theta_heat_in_zj",
            "storage_change_zj",
            "transport_convergence_zj",
        ],
    ].rename(
        columns={
            "west_theta_heat_in_zj": "arrival_140w_heat_in_zj",
            "storage_change_zj": "arrival_east_ohc_change_zj",
            "transport_convergence_zj": "arrival_transport_convergence_zj",
        }
    )
    decay = decay.rename(
        columns={
            "storage_change_zj": "decay_storage_change_zj",
            "transport_convergence_zj": "decay_transport_convergence_zj",
            "west_theta_heat_in_zj": "decay_west_heat_in_zj",
            "east_theta_heat_in_zj": "decay_east_heat_in_zj",
            "north_theta_heat_in_zj": "decay_north_heat_in_zj",
            "south_theta_heat_in_zj": "decay_south_heat_in_zj",
            "northward_output_zj": "decay_northward_output_zj",
            "southward_output_zj": "decay_southward_output_zj",
            "surface_loss_zj": "decay_surface_loss_zj",
            "residual_zj": "decay_residual_zj",
        }
    )
    keep_decay = [
        "event_year",
        "decay_storage_change_zj",
        "decay_transport_convergence_zj",
        "decay_west_heat_in_zj",
        "decay_east_heat_in_zj",
        "decay_north_heat_in_zj",
        "decay_south_heat_in_zj",
        "decay_northward_output_zj",
        "decay_southward_output_zj",
        "decay_surface_loss_zj",
        "decay_residual_zj",
    ]
    decay = decay[keep_decay]

    arrival_state = pd.read_csv(ARRIVAL_EVENTS)
    arrival_keep = [
        "year",
        "group",
        "early_total_positive_ohc_pj_m",
        "early_east_positive_fraction",
        "early_positive_centroid_deg_e",
        "early_central_ohc_gj_m2",
        "early_east_ohc_gj_m2",
        "early_east_minus_central_ohc_gj_m2",
        "jiang_tau_response_mjj_z",
        "precip_response_mjj",
        "slp_response_mjj",
        "tau_response_mjj",
    ]
    arrival_state = arrival_state[arrival_keep].rename(columns={"year": "event_year"})
    coupling = pd.read_csv(COUPLING_EVENTS)[
        [
            "year",
            "fep_total_mar_apr_c",
            "mar_apr_fep_residual_c",
            "ohc300_central_ma_gj_m2",
            "u850_cwp_mj_ms",
            "mature_djf_type_index_c",
        ]
    ].rename(columns={"year": "event_year"})

    table = decay.merge(arrival, on="event_year", validate="one_to_one")
    table = table.merge(arrival_state, on="event_year", validate="one_to_one")
    table = table.merge(coupling, on="event_year", validate="one_to_one")
    table = table.merge(decay_surface_state(), on="event_year", validate="one_to_one")
    table = table.sort_values("event_year").reset_index(drop=True)
    if tuple(table.event_year) != EVENTS:
        raise ValueError("Merged event table does not match the fixed 13 events")

    table["decay_storage_loss_zj"] = -table["decay_storage_change_zj"]
    table["decay_westward_return_zj"] = -table["decay_west_heat_in_zj"]
    table["decay_eastward_export_zj"] = -table["decay_east_heat_in_zj"]
    table["decay_residual_sink_zj"] = -table["decay_residual_zj"]
    table["decay_coupled_release_zj"] = (
        table["decay_northward_output_zj"] + table["decay_surface_loss_zj"]
    )
    table["decay_identified_sink_zj"] = (
        table["decay_westward_return_zj"]
        + table["decay_eastward_export_zj"]
        + table["decay_northward_output_zj"]
        + table["decay_southward_output_zj"]
        + table["decay_surface_loss_zj"]
    )
    table["decay_routing_contrast_z"] = zscore(
        table["decay_coupled_release_zj"]
    ) - zscore(table["decay_westward_return_zj"])
    table["budget_closure_error_zj"] = table["decay_storage_loss_zj"] - (
        table["decay_identified_sink_zj"] + table["decay_residual_sink_zj"]
    )
    if table["budget_closure_error_zj"].abs().max() > 1.0e-7:
        raise ValueError("Event-scale non-H20 budget does not close")
    numeric = table.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        raise ValueError(
            f"Missing event values: {numeric.columns[numeric.isna().any()].tolist()}"
        )
    return table


def relationship(
    table: pd.DataFrame,
    *,
    test_id: str,
    label: str,
    family: str,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...] = (),
    seed: int,
) -> dict[str, object]:
    x = table[x_name].to_numpy(dtype=float)
    y = table[y_name].to_numpy(dtype=float)
    control_values = table[list(controls)].to_numpy(dtype=float) if controls else None
    xr = residualize(x, control_values)
    yr = residualize(y, control_values)
    observed = correlation(xr, yr)
    rng = np.random.default_rng(seed)
    permutation = np.empty(N_PERMUTATIONS, dtype=float)
    for index in range(N_PERMUTATIONS):
        permutation[index] = correlation(xr, rng.permutation(yr))
    permutation_p = float(
        (np.sum(np.abs(permutation) >= abs(observed)) + 1)
        / (N_PERMUTATIONS + 1)
    )

    bootstrap = np.full(N_BOOTSTRAP, np.nan, dtype=float)
    n = len(table)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, n, size=n)
        sampled_controls = control_values[sample] if control_values is not None else None
        bootstrap[index] = partial_correlation(
            x[sample], y[sample], sampled_controls
        )
    finite_bootstrap = bootstrap[np.isfinite(bootstrap)]
    if len(finite_bootstrap) < 0.95 * N_BOOTSTRAP:
        raise ValueError(f"Too many invalid bootstrap samples for {test_id}")
    ci_low, ci_high = np.percentile(finite_bootstrap, [2.5, 97.5])

    loeo_values = []
    loeo_by_event: dict[int, float] = {}
    for omitted in table.event_year:
        keep = table.event_year.ne(omitted).to_numpy()
        kept_controls = control_values[keep] if control_values is not None else None
        value = partial_correlation(x[keep], y[keep], kept_controls)
        loeo_values.append(value)
        loeo_by_event[int(omitted)] = value
    loeo = np.asarray(loeo_values, dtype=float)
    sign = np.sign(observed)
    same_sign_fraction = float(np.mean(np.sign(loeo) == sign))
    return {
        "test_id": test_id,
        "label": label,
        "family": family,
        "x": x_name,
        "y": y_name,
        "controls": "+".join(controls) if controls else "none",
        "n_events": n,
        "partial_r": observed,
        "partial_spearman_r": rank_correlation(xr, yr),
        "permutation_p": permutation_p,
        "bootstrap_ci_low": float(ci_low),
        "bootstrap_ci_high": float(ci_high),
        "loeo_min_r": float(np.nanmin(loeo)),
        "loeo_max_r": float(np.nanmax(loeo)),
        "loeo_same_sign_fraction": same_sign_fraction,
        "r_without_1997": loeo_by_event[1997],
        "r_without_2015": loeo_by_event[2015],
        "r_without_2023": loeo_by_event[2023],
    }


def build_relationships(table: pd.DataFrame) -> pd.DataFrame:
    specifications = [
        (
            "central_ohc_to_u850_given_fep",
            "Jan-Mar central OHC -> May-Jun u850 at fixed FEP",
            "ordered_chain",
            "early_central_ohc_gj_m2",
            "u850_cwp_mj_ms",
            ("fep_total_mar_apr_c",),
        ),
        (
            "u850_to_decay_tau",
            "May-Jun u850 -> following Jan-May local 5N stress",
            "ordered_chain",
            "u850_cwp_mj_ms",
            "decay_tau5n_westward_nm2",
            (),
        ),
        (
            "decay_tau_to_north_given_arrival",
            "Local 5N stress -> non-H20 north output at fixed arrival",
            "ordered_chain",
            "decay_tau5n_westward_nm2",
            "decay_northward_output_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "decay_sst_to_surface_given_arrival",
            "Following eastern SST -> surface loss at fixed arrival",
            "thermodynamic_branch",
            "decay_east_sst_anom_c",
            "decay_surface_loss_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "arrival_to_storage_loss",
            "Arrival heat -> following storage loss",
            "fate_scale",
            "arrival_140w_heat_in_zj",
            "decay_storage_loss_zj",
            (),
        ),
        (
            "u850_to_north_given_arrival",
            "May-Jun u850 -> non-H20 north output at fixed arrival",
            "routing_sensitivity",
            "u850_cwp_mj_ms",
            "decay_northward_output_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "u850_to_coupled_release_given_arrival",
            "May-Jun u850 -> north plus surface release at fixed arrival",
            "routing_sensitivity",
            "u850_cwp_mj_ms",
            "decay_coupled_release_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "decay_tau_to_coupled_release_given_arrival",
            "Local stress -> north plus surface release at fixed arrival",
            "routing_sensitivity",
            "decay_tau5n_westward_nm2",
            "decay_coupled_release_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "decay_tau_to_west_return_given_arrival",
            "Local stress -> westward return at fixed arrival",
            "routing_sensitivity",
            "decay_tau5n_westward_nm2",
            "decay_westward_return_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "jiang_tau_to_north_given_arrival",
            "Development Jiang stress response -> later north output",
            "window_sensitivity",
            "jiang_tau_response_mjj_z",
            "decay_northward_output_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "decay_tau_to_north_given_arrival_central",
            "Local stress -> north output at fixed arrival and central OHC",
            "control_sensitivity",
            "decay_tau5n_westward_nm2",
            "decay_northward_output_zj",
            ("arrival_140w_heat_in_zj", "early_central_ohc_gj_m2"),
        ),
        (
            "decay_sst_to_surface_given_arrival_central",
            "Eastern SST -> surface loss at fixed arrival and central OHC",
            "control_sensitivity",
            "decay_east_sst_anom_c",
            "decay_surface_loss_zj",
            ("arrival_140w_heat_in_zj", "early_central_ohc_gj_m2"),
        ),
    ]
    rows = [
        relationship(
            table,
            test_id=test_id,
            label=label,
            family=family,
            x_name=x_name,
            y_name=y_name,
            controls=controls,
            seed=RANDOM_SEED + index * 101,
        )
        for index, (test_id, label, family, x_name, y_name, controls) in enumerate(
            specifications
        )
    ]
    result = pd.DataFrame(rows)
    result["fdr_q_within_family"] = np.nan
    for family in result.family.unique():
        selected = result.family.eq(family)
        result.loc[selected, "fdr_q_within_family"] = bh_fdr(
            result.loc[selected, "permutation_p"]
        )
    return result


def linear_fit_predict(
    train: pd.DataFrame, test: pd.DataFrame, predictors: tuple[str, ...], target: str
) -> np.ndarray:
    design = np.column_stack(
        [np.ones(len(train)), train[list(predictors)].to_numpy(dtype=float)]
    )
    beta = np.linalg.lstsq(design, train[target].to_numpy(dtype=float), rcond=None)[0]
    test_design = np.column_stack(
        [np.ones(len(test)), test[list(predictors)].to_numpy(dtype=float)]
    )
    return test_design @ beta


def build_models(table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    models = [
        ("north_arrival", "decay_northward_output_zj", ("arrival_140w_heat_in_zj",)),
        (
            "north_arrival_u850",
            "decay_northward_output_zj",
            ("arrival_140w_heat_in_zj", "u850_cwp_mj_ms"),
        ),
        (
            "north_arrival_tau",
            "decay_northward_output_zj",
            ("arrival_140w_heat_in_zj", "decay_tau5n_westward_nm2"),
        ),
        (
            "north_arrival_u850_tau",
            "decay_northward_output_zj",
            (
                "arrival_140w_heat_in_zj",
                "u850_cwp_mj_ms",
                "decay_tau5n_westward_nm2",
            ),
        ),
        (
            "surface_arrival",
            "decay_surface_loss_zj",
            ("arrival_140w_heat_in_zj",),
        ),
        (
            "surface_arrival_sst",
            "decay_surface_loss_zj",
            ("arrival_140w_heat_in_zj", "decay_east_sst_anom_c"),
        ),
    ]
    model_rows = []
    prediction_rows = []
    for model_id, target, predictors in models:
        fitted = linear_fit_predict(table, table, predictors, target)
        observed = table[target].to_numpy(dtype=float)
        residual_ss = float(np.sum((observed - fitted) ** 2))
        total_ss = float(np.sum((observed - np.mean(observed)) ** 2))
        predictions = np.full(len(table), np.nan)
        for index, event in enumerate(table.event_year):
            train = table.loc[table.event_year.ne(event)]
            test = table.loc[table.event_year.eq(event)]
            predictions[index] = linear_fit_predict(
                train, test, predictors, target
            )[0]
            prediction_rows.append(
                {
                    "model_id": model_id,
                    "event_year": int(event),
                    "target": target,
                    "observed": observed[index],
                    "predicted": predictions[index],
                    "error": predictions[index] - observed[index],
                }
            )
        rmse = float(np.sqrt(np.mean((predictions - observed) ** 2)))
        model_rows.append(
            {
                "model_id": model_id,
                "target": target,
                "predictors": "+".join(predictors),
                "n_predictors": len(predictors),
                "in_sample_r2": 1.0 - residual_ss / total_ss,
                "loeo_rmse_z": rmse / float(np.std(observed, ddof=1)),
                "loeo_correlation": correlation(predictions, observed),
            }
        )
    return pd.DataFrame(model_rows), pd.DataFrame(prediction_rows)


def mediation_summary(table: pd.DataFrame) -> pd.DataFrame:
    """Exploratory u850 -> local stress -> north-output serial bridge."""
    x = table["u850_cwp_mj_ms"].to_numpy(dtype=float)
    mediator = table["decay_tau5n_westward_nm2"].to_numpy(dtype=float)
    y = table["decay_northward_output_zj"].to_numpy(dtype=float)
    control = table[["arrival_140w_heat_in_zj"]].to_numpy(dtype=float)

    def effects(indices: np.ndarray) -> tuple[float, float, float, float]:
        xr = zscore(residualize(x[indices], control[indices]))
        mr = zscore(residualize(mediator[indices], control[indices]))
        yr = zscore(residualize(y[indices], control[indices]))
        a = float(np.linalg.lstsq(np.column_stack([np.ones(len(xr)), xr]), mr, rcond=None)[0][1])
        beta = np.linalg.lstsq(
            np.column_stack([np.ones(len(xr)), xr, mr]), yr, rcond=None
        )[0]
        direct = float(beta[1])
        b = float(beta[2])
        total = float(
            np.linalg.lstsq(
                np.column_stack([np.ones(len(xr)), xr]), yr, rcond=None
            )[0][1]
        )
        return a, b, a * b, direct if np.isfinite(direct) else np.nan

    full = np.arange(len(table))
    a, b, indirect, direct = effects(full)
    rng = np.random.default_rng(RANDOM_SEED + 991)
    boot = np.full((N_BOOTSTRAP, 4), np.nan)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(table), size=len(table))
        try:
            boot[index] = effects(sample)
        except ValueError:
            continue
    valid = np.isfinite(boot).all(axis=1)
    if valid.sum() < 0.95 * N_BOOTSTRAP:
        raise ValueError("Too many invalid mediation bootstrap samples")
    low = np.percentile(boot[valid], 2.5, axis=0)
    high = np.percentile(boot[valid], 97.5, axis=0)
    names = ("a_u850_to_tau", "b_tau_to_north", "indirect_ab", "direct_u850")
    values = (a, b, indirect, direct)
    return pd.DataFrame(
        {
            "effect": names,
            "estimate": values,
            "bootstrap_ci_low": low,
            "bootstrap_ci_high": high,
            "controls": "arrival_140w_heat_in_zj",
            "interpretation": "exploratory statistical bridge, not causal mediation",
        }
    )


def write_report(
    table: pd.DataFrame,
    relationships: pd.DataFrame,
    models: pd.DataFrame,
    mediation: pd.DataFrame,
) -> None:
    rel = relationships.set_index("test_id")
    selected = table.set_index("event_year").loc[list(HIGHLIGHTS)]

    def relation_line(test_id: str) -> str:
        row = rel.loc[test_id]
        return (
            f"r={row.partial_r:+.2f}，置换p={row.permutation_p:.3f}，"
            f"family-FDR q={row.fdr_q_within_family:.3f}，"
            f"bootstrap 95%区间[{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]，"
            f"留一范围[{row.loeo_min_r:+.2f}, {row.loeo_max_r:+.2f}]"
        )

    north_models = models.set_index("model_id")
    indirect = mediation.set_index("effect").loc["indirect_ab"]
    westward_event_count = int((table["decay_westward_return_zj"] > 0.0).sum())
    lines = [
        "# 第三个问题：非H20海气耦合—暖量命运链的13事件检验",
        "",
        "## 问题",
        "",
        "为什么相似的FEP先暖和东部暖量输入，会通过不同海气耦合产生不同暖量命运？本分析不再以Q20/H20作为主量，而使用质量闭合的0—300 m异常焓分区。",
        "",
        "## 时间有序的两条支路",
        "",
        "### 动力支路：次表层支撑—风—5°N输出",
        "",
        f"1. 固定3—4月FEP后，Jan—Mar中太平洋OHC与May—Jun中西太平洋u850：{relation_line('central_ohc_to_u850_given_fep')}。",
        f"2. May—Jun u850与次年Jan—May局地5°N向西风应力：{relation_line('u850_to_decay_tau')}。",
        f"3. 固定发展期140°W到达量后，局地5°N向西风应力与非H20北向输出：{relation_line('decay_tau_to_north_given_arrival')}。",
        "",
        "### 热力支路：东部暖态—海表散热",
        "",
        f"固定发展期到达量后，次年Jan—May东部SST与海表热损失：{relation_line('decay_sst_to_surface_given_arrival')}。",
        "",
        "### 规模与再循环",
        "",
        f"发展期140°W输入与次年东箱OHC′损失：{relation_line('arrival_to_storage_loss')}。",
        f"局地5°N风应力并不能单独解释向西返回：{relation_line('decay_tau_to_west_return_given_arrival')}。这说明向西返回更接近盆地再调整/环流重组支路，不能全部并入风驱北向出口。",
        "",
        "## 1997、2015、2023自然对照",
        "",
        "| 事件 | Jan–Mar中部OHC | May–Jun u850 | 次年5°N应力 | 140°W到达 | 北向输出 | 海表损失 | 向西返回 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for event, row in selected.iterrows():
        lines.append(
            f"| {event} | {row.early_central_ohc_gj_m2:+.2f} GJ m⁻² | "
            f"{row.u850_cwp_mj_ms:+.2f} m s⁻¹ | {row.decay_tau5n_westward_nm2:+.4f} N m⁻² | "
            f"{row.arrival_140w_heat_in_zj:+.2f} ZJ | {row.decay_northward_output_zj:+.2f} ZJ | "
            f"{row.decay_surface_loss_zj:+.2f} ZJ | {row.decay_westward_return_zj:+.2f} ZJ |"
        )
    lines += [
        "",
        "2015与2023的140°W到达量接近，但2023的早期中部OHC、u850和次年局地5°N应力均更弱；其北向输出和海表损失也更小。1997则沿整条动力链处于强端。三例叙述因此与13事件的动力支路检验方向一致。",
        "",
        "## 留一预测与统计桥",
        "",
        f"- 北向输出的‘仅到达量’模型LOEO RMSE={north_models.loc['north_arrival', 'loeo_rmse_z']:.2f}σ；加入局地5°N应力后为{north_models.loc['north_arrival_tau', 'loeo_rmse_z']:.2f}σ，LOEO相关由{north_models.loc['north_arrival', 'loeo_correlation']:+.2f}变为{north_models.loc['north_arrival_tau', 'loeo_correlation']:+.2f}。",
        f"- 海表损失的‘仅到达量’模型LOEO RMSE={north_models.loc['surface_arrival', 'loeo_rmse_z']:.2f}σ；加入同期东部SST后为{north_models.loc['surface_arrival_sst', 'loeo_rmse_z']:.2f}σ。",
        f"- 探索性u850→局地应力→北向输出间接效应为{indirect.estimate:+.2f} SD，bootstrap 95%区间[{indirect.bootstrap_ci_low:+.2f}, {indirect.bootstrap_ci_high:+.2f}]。即便区间不跨零，也只能称时间有序的统计桥，不能称因果中介。",
        "",
        "## 第三个问题的当前答案",
        "",
        "1. 相似FEP先暖不等于相似三维海洋状态；中太平洋次表层OHC对随后中西太平洋风响应构成重要约束。该边置换和留一结果稳定，但bootstrap下界略跨零，不能写成单一决定关系。",
        "2. 暖量到达后存在两条可分辨的耦合支路：局地5°N应力控制动力北向输出，东部SST控制海表散热。两者不应压成一个‘耦合强度’指标。",
        f"3. 向西返回在三例及{westward_event_count}/13事件中是净损失项，但当前大气指标对它的解释较弱；它仍需SSH/密度压力场和盆地调整诊断。",
        "4. 因而1997是次表层支撑、风门和热力释放同时强；2015是中等到达但风门有效；2023是到达不弱、早期中部支撑和风响应偏弱，北向与散热支路受限，更多暖量通过向西返回和残差调整。",
        "",
        "## 证据边界",
        "",
        "- 只有13个事件；bootstrap、置换和留一检验用于暴露杠杆点，不能制造大样本确定性。",
        "- 局地5°N应力与北向输送处于同一衰减窗口，是动力一致性证据，不是严格领先因果。",
        "- 残差仍含垂向交换、混合、同化增量和离散误差；2015和2023残差较大。",
        "- 正式因果检验仍需要耦合模式或至少强迫海洋模式反事实；当前结果是时间有序、质量闭合的观测诊断。",
        "",
        "## 产物",
        "",
        f"- 13事件表：`{EVENT_OUTPUT}`",
        f"- 关系检验：`{RELATION_OUTPUT}`",
        f"- 留一模型：`{MODEL_OUTPUT}`",
        f"- 留一预测：`{PREDICTION_OUTPUT}`",
        f"- 统计桥：`{MEDIATION_OUTPUT}`",
        "",
    ]
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    table = load_event_table()
    relationships = build_relationships(table)
    models, predictions = build_models(table)
    mediation = mediation_summary(table)
    diagnostics = {
        "events": list(EVENTS),
        "n_events": len(table),
        "baseline": list(BASELINE),
        "arrival_window": "Jan15-Jun15 event year",
        "fate_window": "Jan15-May15 following year",
        "max_budget_closure_error_zj": float(
            table["budget_closure_error_zj"].abs().max()
        ),
        "bootstrap_samples": N_BOOTSTRAP,
        "permutation_samples": N_PERMUTATIONS,
        "primary_dynamic_outcome": "mass-balanced non-H20 northward anomalous enthalpy output",
        "causal_status": "time-ordered observational diagnostic; not causal attribution",
    }
    DATA.mkdir(parents=True, exist_ok=True)
    EVENT_OUTPUT.write_text(table.to_csv(index=False, float_format="%.10g"), encoding="utf-8")
    RELATION_OUTPUT.write_text(
        relationships.to_csv(index=False, float_format="%.10g"), encoding="utf-8"
    )
    MODEL_OUTPUT.write_text(models.to_csv(index=False, float_format="%.10g"), encoding="utf-8")
    PREDICTION_OUTPUT.write_text(
        predictions.to_csv(index=False, float_format="%.10g"), encoding="utf-8"
    )
    MEDIATION_OUTPUT.write_text(
        mediation.to_csv(index=False, float_format="%.10g"), encoding="utf-8"
    )
    DIAGNOSTICS_OUTPUT.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(table, relationships, models, mediation)
    print(f"Wrote {EVENT_OUTPUT} ({len(table)} events)")
    print(f"Wrote {RELATION_OUTPUT} ({len(relationships)} tests)")
    print(f"Wrote {MODEL_OUTPUT} ({len(models)} models)")
    print(f"Wrote {REPORT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
