#!/usr/bin/env python3
"""Test the observational Arrival -> Configuration -> Coupling -> Routing chain.

The event chronology is fixed before calculation:

* January--March(0): SODA3 0--300 m ocean preconditioning;
* April--July(0): atmosphere response conditional on concurrent SST;
* January--May(+1): SODA3 5N warm-heat routing.

The analysis distinguishes the amount of early subsurface heat from its
spatial distribution.  It is an event-level observational diagnostic, not a
causal coupled-model experiment.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_arrival_configuration_coupling")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/arrival_configuration_coupling_routing"
PDF_DIR = ROOT / "output/pdf"

GEOMETRY_CSV = DERIVED / "soda3_5day_ohc_geometry_coupling_13events_jan_sep.csv"
COUPLING_MONTHLY_CSV = DERIVED / "enso_full_year_coupling_monthly_1982_2024.csv"
ROUTING_CSV = DERIVED / "third_question_coupled_attribution_event_table.csv"
H20_MONTHLY_CSV = DERIVED / "soda3_three_box_warm_heat_budget_monthly_1980_2022.csv"
PENG_JIANG_CSV = DERIVED / "peng_jiang_decoupling_event_summary.csv"

EVENT_TABLE_CSV = DERIVED / "arrival_configuration_coupling_routing_event_table.csv"
RELATIONSHIP_CSV = DERIVED / "arrival_configuration_coupling_routing_relationships.csv"
MODEL_CSV = DERIVED / "arrival_configuration_coupling_routing_models.csv"
DIAGNOSTICS_JSON = DERIVED / "arrival_configuration_coupling_routing_diagnostics.json"
FIGURE_PNG = OUT / "arrival_configuration_coupling_routing.png"
FIGURE_PDF = PDF_DIR / "arrival_configuration_coupling_routing.pdf"
REPORT_MD = OUT / "ARRIVAL_CONFIGURATION_COUPLING_ROUTING_CN.md"

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
HIGHLIGHT_YEARS = (1997, 2015, 2023)
COLORS = {1997: "#B33E3E", 2015: "#D97706", 2023: "#2166AC"}
RESPONSES = (
    "precip_tropical_pacific_raw_mmday",
    "slp_drive_w_minus_e_raw_hpa",
    "tau_cwp_raw_nm2",
)
BOOTSTRAP_SAMPLES = 30_000
PERMUTATION_SAMPLES = 50_000
RNG_SEED = 20260809


def zscore(values: pd.Series | np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return (array - np.nanmean(array)) / np.nanstd(array, ddof=1)


def residualize(
    target: pd.Series | np.ndarray,
    predictors: list[pd.Series | np.ndarray],
) -> np.ndarray:
    y = np.asarray(target, dtype=float)
    x = np.column_stack([np.ones(len(y)), *[np.asarray(v, dtype=float) for v in predictors]])
    return y - x @ np.linalg.lstsq(x, y, rcond=None)[0]


def loeo_residual_z(
    frame: pd.DataFrame,
    target: str,
    predictors: list[str],
) -> np.ndarray:
    output = np.full(len(frame), np.nan, dtype=float)
    for index in range(len(frame)):
        train = frame.index != index
        x_train = np.column_stack(
            [np.ones(train.sum()), *[frame.loc[train, p].to_numpy(float) for p in predictors]]
        )
        y_train = frame.loc[train, target].to_numpy(float)
        beta = np.linalg.lstsq(x_train, y_train, rcond=None)[0]
        scale = float(np.std(y_train - x_train @ beta, ddof=x_train.shape[1]))
        x_test = np.asarray([1.0, *[float(frame.loc[index, p]) for p in predictors]])
        output[index] = (float(frame.loc[index, target]) - x_test @ beta) / scale
    return output


def build_early_ocean_table() -> pd.DataFrame:
    frame = pd.read_csv(GEOMETRY_CSV, parse_dates=["time"])
    if set(frame["year"].unique()) != set(EVENT_YEARS):
        raise ValueError("Unexpected event years in five-day OHC geometry table")
    selected = frame.loc[frame["month"].isin((1, 2, 3))]
    source_columns = {
        "ohc300_positive_total_pj_m": "early_total_positive_ohc_pj_m",
        "ohc300_positive_east140w_fraction": "early_east_positive_fraction",
        "ohc300_positive_centroid_deg_e": "early_positive_centroid_deg_e",
        "ohc300_west_180e_140w_gj_m2": "early_central_ohc_gj_m2",
        "ohc300_east_140w_80w_gj_m2": "early_east_ohc_gj_m2",
        "ohc300_east_minus_west_gj_m2": "early_east_minus_central_ohc_gj_m2",
    }
    output = (
        selected.groupby("year", as_index=False)[list(source_columns)]
        .mean()
        .rename(columns=source_columns)
        .sort_values("year")
        .reset_index(drop=True)
    )
    counts = selected.groupby("year")["time"].nunique().reindex(EVENT_YEARS)
    if not counts.between(17, 19).all():
        raise ValueError(f"Incomplete January--March pentads: {counts.to_dict()}")
    output["central_bridge_given_east_gj_m2"] = residualize(
        output["early_central_ohc_gj_m2"], [output["early_east_ohc_gj_m2"]]
    )
    output["central_bridge_given_east_total_gj_m2"] = residualize(
        output["early_central_ohc_gj_m2"],
        [output["early_east_ohc_gj_m2"], output["early_total_positive_ohc_pj_m"]],
    )
    output["central_bridge_given_east_loeo_z"] = loeo_residual_z(
        output, "early_central_ohc_gj_m2", ["early_east_ohc_gj_m2"]
    )
    return output


def expected_response_residual(
    monthly: pd.DataFrame,
    *,
    response: str,
    event_year: int,
    month: int,
) -> float:
    same_month = monthly.loc[monthly["month"].eq(month)].dropna(
        subset=[response, "nino34_raw_c", "sst_type_raw_c"]
    )
    train = same_month.loc[same_month["year"].ne(event_year)]
    test = same_month.loc[same_month["year"].eq(event_year)]
    if len(test) != 1 or len(train) < 35:
        raise ValueError(f"Cannot form conditional response for {event_year}-{month:02d}")
    x_train = np.column_stack(
        [
            np.ones(len(train)),
            train["year"].to_numpy(float) - 2003.0,
            train["nino34_raw_c"].to_numpy(float),
            train["sst_type_raw_c"].to_numpy(float),
        ]
    )
    y_train = train[response].to_numpy(float)
    beta = np.linalg.lstsq(x_train, y_train, rcond=None)[0]
    residual = y_train - x_train @ beta
    scale = float(np.std(residual, ddof=x_train.shape[1]))
    row = test.iloc[0]
    x_test = np.asarray(
        [
            1.0,
            float(event_year) - 2003.0,
            float(row["nino34_raw_c"]),
            float(row["sst_type_raw_c"]),
        ]
    )
    return float((float(row[response]) - x_test @ beta) / scale)


def coupling_for_window(monthly: pd.DataFrame, months: tuple[int, ...], tag: str) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    short_names = ("precip", "slp", "tau")
    for year in EVENT_YEARS:
        branch = {}
        for short, response in zip(short_names, RESPONSES):
            branch[short] = float(
                np.mean(
                    [
                        expected_response_residual(
                            monthly, response=response, event_year=year, month=month
                        )
                        for month in months
                    ]
                )
            )
        rows.append(
            {
                "year": year,
                f"precip_response_{tag}": branch["precip"],
                f"slp_response_{tag}": branch["slp"],
                f"tau_response_{tag}": branch["tau"],
                f"coupling_strength_{tag}": float(np.mean(list(branch.values()))),
            }
        )
    output = pd.DataFrame(rows)
    output[f"coupling_strength_{tag}_z"] = zscore(output[f"coupling_strength_{tag}"])
    output[f"decoupling_{tag}_z"] = -output[f"coupling_strength_{tag}_z"]
    return output


def build_coupling_table() -> pd.DataFrame:
    monthly = pd.read_csv(COUPLING_MONTHLY_CSV)
    if monthly.duplicated(["year", "month"]).any():
        raise ValueError("Duplicate monthly coupling rows")
    primary = coupling_for_window(monthly, (4, 5, 6, 7), "apr_jul")
    sensitivity = coupling_for_window(monthly, (5, 6, 7), "mjj")
    return primary.merge(sensitivity, on="year", validate="one_to_one")


def build_h20_sensitivity(coupling: pd.DataFrame) -> pd.DataFrame:
    frame = pd.read_csv(H20_MONTHLY_CSV)
    years = [year for year in EVENT_YEARS if year <= int(frame["year"].max())]
    selected = frame.loc[frame["year"].isin(years) & frame["month"].isin((1, 2, 3))]
    output = (
        selected.groupby("year", as_index=False)[
            ["central_h20_zj_anom", "east_h20_zj_anom"]
        ]
        .mean()
        .rename(
            columns={
                "central_h20_zj_anom": "early_central_h20_zj_anom",
                "east_h20_zj_anom": "early_east_h20_zj_anom",
            }
        )
    )
    if set(output["year"]) != set(years):
        raise ValueError("Incomplete H20 sensitivity event set")
    output["h20_bridge_given_east_zj"] = residualize(
        output["early_central_h20_zj_anom"], [output["early_east_h20_zj_anom"]]
    )
    return output.merge(coupling, on="year", validate="one_to_one")


def build_event_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    ocean = build_early_ocean_table()
    coupling = build_coupling_table()
    routing = pd.read_csv(ROUTING_CSV)
    published_aligned = pd.read_csv(PENG_JIANG_CSV)
    routing_columns = [
        "year",
        "group",
        "q5n_total_jan_may1_zj",
        "q5n_ekman_jan_may1_zj",
        "q5n_geo_eos80_jan_may1_zj",
        "q5n_residual_eos80_jan_may1_zj",
    ]
    table = (
        ocean.merge(coupling, on="year", validate="one_to_one")
        .merge(routing[routing_columns], on="year", validate="one_to_one")
        .merge(
            published_aligned[
                [
                    "year",
                    "peng_cwp_u10_ratio",
                    "peng_cwp_u10_residual_ms",
                    "jiang_fep_residual_mjj_z",
                    "jiang_ne850_mjj_z",
                    "jiang_tau_response_mjj_z",
                    "djf_era5_gpcp_pattern_residual_z",
                    "djf_gpcp_precip_pattern_residual_z",
                    "djf_ncep_u_pattern_residual_z",
                ]
            ],
            on="year",
            validate="one_to_one",
        )
        .sort_values("year")
        .reset_index(drop=True)
    )
    if tuple(table["year"]) != EVENT_YEARS:
        raise ValueError("Joined event chronology is incomplete")
    required = table.select_dtypes(include=[np.number]).columns
    if table[required].isna().any().any():
        raise ValueError("Missing numeric value in joined event table")
    for column in (
        "early_total_positive_ohc_pj_m",
        "early_central_ohc_gj_m2",
        "early_east_ohc_gj_m2",
        "central_bridge_given_east_gj_m2",
        "central_bridge_given_east_total_gj_m2",
        "q5n_ekman_jan_may1_zj",
        "q5n_total_jan_may1_zj",
    ):
        table[f"{column}_z"] = zscore(table[column])
    for column in (
        "peng_cwp_u10_ratio",
        "peng_cwp_u10_residual_ms",
        "jiang_fep_residual_mjj_z",
        "jiang_ne850_mjj_z",
        "jiang_tau_response_mjj_z",
        "djf_era5_gpcp_pattern_residual_z",
        "djf_gpcp_precip_pattern_residual_z",
        "djf_ncep_u_pattern_residual_z",
    ):
        table[f"{column}_lower_rank"] = table[column].rank(
            method="min", ascending=True
        ).astype(int)
    return table, build_h20_sensitivity(coupling)


def rowwise_corr(x: np.ndarray, y_matrix: np.ndarray) -> np.ndarray:
    x0 = x - x.mean()
    y0 = y_matrix - y_matrix.mean(axis=1, keepdims=True)
    numerator = np.sum(y0 * x0[None, :], axis=1)
    denominator = np.sqrt(np.sum(x0**2) * np.sum(y0**2, axis=1))
    return numerator / denominator


def correlation_stats(
    frame: pd.DataFrame,
    *,
    link_id: str,
    label: str,
    x_name: str,
    y_name: str,
    family: str,
    seed: int,
) -> dict[str, float | int | str]:
    valid = frame[[x_name, y_name]].dropna()
    x = valid[x_name].to_numpy(float)
    y = valid[y_name].to_numpy(float)
    pearson = stats.pearsonr(x, y)
    spearman = stats.spearmanr(x, y)
    rng = np.random.default_rng(seed)
    boot_index = rng.integers(0, len(x), size=(BOOTSTRAP_SAMPLES, len(x)))
    boot_x = x[boot_index]
    boot_y = y[boot_index]
    boot_x0 = boot_x - boot_x.mean(axis=1, keepdims=True)
    boot_y0 = boot_y - boot_y.mean(axis=1, keepdims=True)
    denominator = np.sqrt(np.sum(boot_x0**2, axis=1) * np.sum(boot_y0**2, axis=1))
    boot_r = np.divide(
        np.sum(boot_x0 * boot_y0, axis=1),
        denominator,
        out=np.full(BOOTSTRAP_SAMPLES, np.nan),
        where=denominator > 0,
    )
    perm_index = np.argsort(rng.random((PERMUTATION_SAMPLES, len(y))), axis=1)
    perm_r = rowwise_corr(x, y[perm_index])
    permutation_p = float((np.sum(np.abs(perm_r) >= abs(float(pearson.statistic))) + 1) / (PERMUTATION_SAMPLES + 1))
    loeo = []
    for index in range(len(x)):
        keep = np.arange(len(x)) != index
        loeo.append(float(np.corrcoef(x[keep], y[keep])[0, 1]))
    return {
        "link_id": link_id,
        "label": label,
        "family": family,
        "x": x_name,
        "y": y_name,
        "n_events": len(x),
        "pearson_r": float(pearson.statistic),
        "pearson_p_parametric": float(pearson.pvalue),
        "permutation_p": permutation_p,
        "bootstrap_ci_low": float(np.nanpercentile(boot_r, 2.5)),
        "bootstrap_ci_high": float(np.nanpercentile(boot_r, 97.5)),
        "spearman_r": float(spearman.statistic),
        "spearman_p": float(spearman.pvalue),
        "loeo_r_min": float(np.min(loeo)),
        "loeo_r_max": float(np.max(loeo)),
    }


def bh_fdr(values: pd.Series) -> np.ndarray:
    p = values.to_numpy(float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * len(p) / np.arange(1, len(p) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.clip(adjusted, 0.0, 1.0)
    return output


def build_relationships(table: pd.DataFrame, h20: pd.DataFrame) -> pd.DataFrame:
    h20_jiang = h20.merge(
        table[["year", "jiang_tau_response_mjj_z"]],
        on="year",
        validate="one_to_one",
    )
    definitions = [
        ("central_to_jiang_tau", "Jan-Mar central OHC -> Jiang-window central wind-stress response", "early_central_ohc_gj_m2", "jiang_tau_response_mjj_z", "primary_ocean", table),
        ("total_to_jiang_tau", "Jan-Mar total positive OHC -> Jiang-window wind-stress response", "early_total_positive_ohc_pj_m", "jiang_tau_response_mjj_z", "primary_ocean", table),
        ("east_to_jiang_tau", "Jan-Mar eastern OHC -> Jiang-window wind-stress response", "early_east_ohc_gj_m2", "jiang_tau_response_mjj_z", "ocean_geometry", table),
        ("bridge_east_to_jiang_tau", "Central bridge given eastern OHC -> Jiang-window wind response", "central_bridge_given_east_gj_m2", "jiang_tau_response_mjj_z", "ocean_geometry", table),
        ("bridge_total_east_to_jiang_tau", "Central bridge given eastern and total OHC -> Jiang-window wind response", "central_bridge_given_east_total_gj_m2", "jiang_tau_response_mjj_z", "ocean_geometry", table),
        ("east_fraction_to_jiang_tau", "East-of-140W positive-heat fraction -> Jiang-window wind response", "early_east_positive_fraction", "jiang_tau_response_mjj_z", "ocean_geometry", table),
        ("centroid_to_jiang_tau", "Positive-heat centroid -> Jiang-window wind response", "early_positive_centroid_deg_e", "jiang_tau_response_mjj_z", "ocean_geometry", table),
        ("gradient_to_jiang_tau", "East-minus-central OHC -> Jiang-window wind response", "early_east_minus_central_ohc_gj_m2", "jiang_tau_response_mjj_z", "ocean_geometry", table),
        ("jiang_tau_to_ekman", "Jiang-window central wind response -> following Jan-May 5N Ekman Q20", "jiang_tau_response_mjj_z", "q5n_ekman_jan_may1_zj", "routing", table),
        ("jiang_tau_to_total", "Jiang-window central wind response -> following Jan-May total 5N Q20", "jiang_tau_response_mjj_z", "q5n_total_jan_may1_zj", "routing", table),
        ("central_to_ekman", "Jan-Mar central OHC -> following 5N Ekman Q20", "early_central_ohc_gj_m2", "q5n_ekman_jan_may1_zj", "routing", table),
        ("broad_composite_sensitivity", "Jan-Mar central OHC -> broad Apr-Jul three-branch mean", "early_central_ohc_gj_m2", "coupling_strength_apr_jul", "window_sensitivity", table),
        ("h20_central_to_jiang_tau", "Jan-Mar central H20 -> Jiang-window wind response", "early_central_h20_zj_anom", "jiang_tau_response_mjj_z", "h20_sensitivity", h20_jiang),
        ("h20_bridge_to_jiang_tau", "Central H20 given eastern H20 -> Jiang-window wind response", "h20_bridge_given_east_zj", "jiang_tau_response_mjj_z", "h20_sensitivity", h20_jiang),
    ]
    rows = []
    for offset, (link_id, label, x_name, y_name, family, frame) in enumerate(definitions):
        rows.append(
            correlation_stats(
                frame,
                link_id=link_id,
                label=label,
                x_name=x_name,
                y_name=y_name,
                family=family,
                seed=RNG_SEED + offset,
            )
        )
    result = pd.DataFrame(rows)
    result["fdr_q_within_family"] = np.nan
    for family, index in result.groupby("family").groups.items():
        result.loc[index, "fdr_q_within_family"] = bh_fdr(result.loc[index, "permutation_p"])
    return result


def standardized_models(table: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    rows = []

    def fit(model: str, response: str, predictors: list[str]) -> tuple[np.ndarray, float, float]:
        y = zscore(table[response])
        x = np.column_stack([np.ones(len(table)), *[zscore(table[p]) for p in predictors]])
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        fitted = x @ beta
        rmse = float(np.sqrt(np.mean((y - fitted) ** 2)))
        r2 = float(1.0 - np.sum((y - fitted) ** 2) / np.sum((y - y.mean()) ** 2))
        for name, value in zip(["intercept", *predictors], beta):
            rows.append(
                {
                    "model": model,
                    "response": response,
                    "term": name,
                    "standardized_coefficient": float(value),
                    "in_sample_rmse": rmse,
                    "in_sample_r2": r2,
                }
            )
        return beta, rmse, r2

    fit(
        "jiang_wind_response_from_central",
        "jiang_tau_response_mjj_z",
        ["early_central_ohc_gj_m2"],
    )
    fit(
        "jiang_wind_amount_plus_geometry",
        "jiang_tau_response_mjj_z",
        ["early_total_positive_ohc_pj_m", "central_bridge_given_east_total_gj_m2"],
    )
    beta_route, _, _ = fit(
        "ekman_from_central_and_coupling",
        "q5n_ekman_jan_may1_zj",
        ["early_central_ohc_gj_m2", "jiang_tau_response_mjj_z"],
    )

    x = zscore(table["early_central_ohc_gj_m2"])
    m = zscore(table["jiang_tau_response_mjj_z"])
    y = zscore(table["q5n_ekman_jan_may1_zj"])
    a = float(np.linalg.lstsq(np.column_stack([np.ones(len(x)), x]), m, rcond=None)[0][1])
    b = float(beta_route[2])
    indirect = a * b
    rng = np.random.default_rng(RNG_SEED + 100)
    boot = []
    for _ in range(BOOTSTRAP_SAMPLES):
        index = rng.integers(0, len(table), len(table))
        xb, mb, yb = x[index], m[index], y[index]
        if np.std(xb) == 0 or np.std(mb) == 0 or np.std(yb) == 0:
            continue
        ab = float(np.linalg.lstsq(np.column_stack([np.ones(len(xb)), xb]), mb, rcond=None)[0][1])
        route = np.linalg.lstsq(np.column_stack([np.ones(len(xb)), xb, mb]), yb, rcond=None)[0]
        boot.append(ab * float(route[2]))
    mediation = {
        "a_central_to_coupling": a,
        "b_coupling_to_ekman_given_central": b,
        "indirect_effect": indirect,
        "bootstrap_ci_low": float(np.percentile(boot, 2.5)),
        "bootstrap_ci_high": float(np.percentile(boot, 97.5)),
    }
    return pd.DataFrame(rows), mediation


def relation(result: pd.DataFrame, link_id: str) -> pd.Series:
    return result.loc[result["link_id"].eq(link_id)].iloc[0]


def add_fit(axis: plt.Axes, x: pd.Series, y: pd.Series) -> None:
    beta = np.polyfit(x.to_numpy(float), y.to_numpy(float), 1)
    line_x = np.linspace(float(x.min()), float(x.max()), 100)
    axis.plot(line_x, np.polyval(beta, line_x), color="#34495E", lw=1.6, zorder=2)


def scatter_events(axis: plt.Axes, table: pd.DataFrame, x: str, y: str) -> None:
    normal = table.loc[~table["year"].isin(HIGHLIGHT_YEARS)]
    axis.scatter(normal[x], normal[y], s=35, color="#9AA4AE", edgecolor="white", lw=0.5, zorder=3)
    routing_offsets = {
        1991: (5, -11),
        2002: (5, 7),
        2006: (5, -10),
        2019: (5, 8),
        2004: (-30, 4),
    }
    for _, row in table.iterrows():
        year = int(row["year"])
        if year in HIGHLIGHT_YEARS:
            axis.scatter(
                [row[x]], [row[y]], s=78, color=COLORS[year], edgecolor="white", lw=0.8, zorder=4
            )
        offset = routing_offsets.get(year, (4, 3)) if y == "q5n_ekman_jan_may1_zj" else (4, 3)
        axis.annotate(
            str(year),
            (row[x], row[y]),
            xytext=offset,
            textcoords="offset points",
            fontsize=7,
        )


def make_figure(table: pd.DataFrame, relationships: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": ["Hiragino Sans GB", "Arial Unicode MS", "sans-serif"],
            "font.size": 9.5,
            "axes.titlesize": 11,
            "axes.labelsize": 9.5,
            "axes.edgecolor": "#263746",
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "figure.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.2))
    fig.suptitle("相似的东部到达量，不等于相同的早期次表层预置", fontsize=17, fontweight="bold", y=0.985)

    axis = axes[0, 0]
    x_name = "early_east_ohc_gj_m2"
    y_name = "early_central_ohc_gj_m2"
    add_fit(axis, table[x_name], table[y_name])
    scatter_events(axis, table, x_name, y_name)
    axis.set(
        title="a  1—3月：东部储量与中太平洋桥接并不等价",
        xlabel="东部 OHC异常（140°W—80°W；GJ m⁻²）",
        ylabel="中部 OHC异常（180°—140°W；GJ m⁻²）",
    )

    axis = axes[0, 1]
    x_name = "early_central_ohc_gj_m2"
    y_name = "jiang_tau_response_mjj_z"
    add_fit(axis, table[x_name], table[y_name])
    scatter_events(axis, table, x_name, y_name)
    result = relation(relationships, "central_to_jiang_tau")
    axis.text(
        0.03,
        0.96,
        f"r = {result.pearson_r:+.2f}  [95%: {result.bootstrap_ci_low:+.2f}, {result.bootstrap_ci_high:+.2f}]",
        transform=axis.transAxes,
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#B8C2CC"},
    )
    axis.set(
        title="b  早期中太平洋暖层与Jiang型西风响应一致变化",
        xlabel="1—3月中部 OHC异常（GJ m⁻²）",
        ylabel="5—7月中太平洋风应力响应（标准化残差）",
    )

    axis = axes[1, 0]
    x_name = "jiang_tau_response_mjj_z"
    y_name = "q5n_ekman_jan_may1_zj"
    add_fit(axis, table[x_name], table[y_name])
    scatter_events(axis, table, x_name, y_name)
    result = relation(relationships, "jiang_tau_to_ekman")
    axis.text(
        0.03,
        0.96,
        f"r = {result.pearson_r:+.2f}  [95%: {result.bootstrap_ci_low:+.2f}, {result.bootstrap_ci_high:+.2f}]",
        transform=axis.transAxes,
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#B8C2CC"},
    )
    axis.set(
        title="c  Jiang型西风响应越强，次年风驱暖量输送越大",
        xlabel="5—7月中太平洋风应力响应（标准化残差）",
        ylabel="次年1—5月 5°N Ekman暖量输送（ZJ）",
    )

    axis = axes[1, 1]
    metrics = [
        ("early_east_ohc_gj_m2_z", "东部\nOHC"),
        ("early_central_ohc_gj_m2_z", "中部\nOHC"),
        ("jiang_tau_response_mjj_z", "Jiang型\n风响应"),
        ("q5n_ekman_jan_may1_zj_z", "次年\nEkman"),
    ]
    positions = np.arange(len(metrics))
    width = 0.23
    for offset, year in enumerate(HIGHLIGHT_YEARS):
        row = table.loc[table["year"].eq(year)].iloc[0]
        values = [float(row[column]) for column, _ in metrics]
        axis.bar(
            positions + (offset - 1) * width,
            values,
            width=width,
            color=COLORS[year],
            label=str(year),
        )
    axis.axhline(0, color="#263746", lw=0.8)
    axis.set_xticks(positions, [label for _, label in metrics])
    axis.set_ylabel("相对13事件平均的标准差")
    axis.set_title("d  2023的中太平洋风响应显著弱于1997和2015")
    axis.legend(frameon=False, ncol=3, loc="upper left")

    for axis in axes.ravel():
        axis.grid(color="#DFE5EA", lw=0.7, alpha=0.9)
        axis.set_axisbelow(True)
    fig.text(
        0.5,
        0.012,
        "时间顺序：Jan—Mar(0) 海洋预置 → May—Jul(0) Jiang型中太平洋风响应 → Jan—May(+1) 5°N暖量路由",
        ha="center",
        fontsize=9.2,
        color="#263746",
    )
    fig.tight_layout(rect=(0.02, 0.045, 0.99, 0.955), h_pad=2.0, w_pad=2.0)
    fig.savefig(FIGURE_PNG, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fmt(value: float) -> str:
    return f"{value:+.2f}"


def make_report(
    table: pd.DataFrame,
    h20: pd.DataFrame,
    relationships: pd.DataFrame,
    mediation: dict[str, float],
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    selected = table.set_index("year").loc[list(HIGHLIGHT_YEARS)]
    central = relation(relationships, "central_to_jiang_tau")
    bridge = relation(relationships, "bridge_east_to_jiang_tau")
    independent_geometry = relation(relationships, "bridge_total_east_to_jiang_tau")
    routing = relation(relationships, "jiang_tau_to_ekman")
    h20_central = relation(relationships, "h20_central_to_jiang_tau")
    h20_bridge = relation(relationships, "h20_bridge_to_jiang_tau")
    lines = [
        "# 到达—配置—接通—路由：第一轮观测检验",
        "",
        "## 固定时间顺序",
        "",
        "- 海洋预置：Jan—Mar(0)，SODA3 5°S—5°N、0—300 m OHC。",
        "- 大气接通主指标：May—Jul(0)中太平洋纬向风应力响应，与Jiang等研究所强调的西风受抑过程对应。",
        "- 原Apr—Jul降水—SLP—风应力三分支平均量仅作宽泛敏感性，不能用于判定2023脱耦强度。",
        "- 后期路由：Jan—May(+1)，5°N阈值暖量总输送与Ekman分量。",
        "- 事件样本：13个暖事件。所有相关均以事件为独立样本；不是逐月伪样本。",
        "",
        "## 三个典型事件",
        "",
        "| 事件 | Jan—Mar总正OHC (PJ m⁻¹) | Jan—Mar中部OHC (GJ m⁻²) | Jan—Mar东部OHC (GJ m⁻²) | Jiang型风响应 (z) | 次年Ekman (ZJ) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year, row in selected.iterrows():
        lines.append(
            f"| {year} | {row.early_total_positive_ohc_pj_m:.2f} | {row.early_central_ohc_gj_m2:.2f} | {row.early_east_ohc_gj_m2:.2f} | {fmt(row.jiang_tau_response_mjj_z)} | {row.q5n_ekman_jan_may1_zj:.2f} |"
        )
    lines += [
        "",
        "## 结果",
        "",
        f"1. 早期中太平洋OHC与随后Jiang型中太平洋风应力响应的相关为 r={central.pearson_r:+.2f}，事件bootstrap 95%区间[{central.bootstrap_ci_low:+.2f}, {central.bootstrap_ci_high:+.2f}]，置换p={central.permutation_p:.3f}。",
        f"2. 只控制东部OHC后，中部桥接剩余量与风响应的相关为 r={bridge.pearson_r:+.2f}；但再同时控制总正OHC后降为 r={independent_geometry.pearson_r:+.2f}。这说明当前样本更支持‘早期盆地/中部次表层支撑量’，尚不支持‘独立于总量的空间分布开关’。",
        f"3. Jiang型中太平洋风应力响应与次年5°N Ekman暖量输送的相关为 r={routing.pearson_r:+.2f}，95%区间[{routing.bootstrap_ci_low:+.2f}, {routing.bootstrap_ci_high:+.2f}]，置换p={routing.permutation_p:.3f}。",
        f"4. 12事件H20敏感性中，中部H20与Jiang型风响应相关为 r={h20_central.pearson_r:+.2f}，控制东部H20后的桥接相关为 r={h20_bridge.pearson_r:+.2f}。2023因三箱H20月资料只到2022年，不参与该项；主分析因此使用覆盖全部13事件的OHC空间资料。",
        f"5. 探索性中介效应（中部OHC→耦合→Ekman）为{mediation['indirect_effect']:+.2f} SD，bootstrap 95%区间[{mediation['bootstrap_ci_low']:+.2f}, {mediation['bootstrap_ci_high']:+.2f}]。只有区间不跨0时才可称为统计一致的间接路径；即便如此也不是因果证明。",
        "",
        "## 对2015与2023的直接解释",
        "",
        f"2023属于严重脱耦事件：其Peng型中太平洋风—SST响应比仅为{selected.loc[2023, 'peng_cwp_u10_ratio']:.2f}，为13事件最低；风响应残差为{selected.loc[2023, 'peng_cwp_u10_residual_ms']:.2f} m s⁻¹，同样最低。Jiang链条中，2023的FEP独立暖异常为{selected.loc[2023, 'jiang_fep_residual_mjj_z']:+.2f} SD、东北风为{selected.loc[2023, 'jiang_ne850_mjj_z']:+.2f} SD，均为13事件最高，而中太平洋风应力响应为{selected.loc[2023, 'jiang_tau_response_mjj_z']:+.2f} SD，为最低。",
        "原来得到的−0.18 SD是降水、SLP和风应力的宽泛平均，分支相消后低估了风—SST通道的破裂，不能据此把2023说成仅略弱。",
        "",
        f"虽然前面按Jan—Jun累计得到的140°W输入和东部H20增长接近，但在大气响应之前，2015的Jan—Mar总正OHC为{selected.loc[2015, 'early_total_positive_ohc_pj_m']:.2f} PJ m⁻¹，中部OHC异常为{selected.loc[2015, 'early_central_ohc_gj_m2']:.2f} GJ m⁻²；2023分别只有{selected.loc[2023, 'early_total_positive_ohc_pj_m']:.2f}和{selected.loc[2023, 'early_central_ohc_gj_m2']:.2f}。因此，‘累计到达量接近’没有推出‘耦合前的次表层支撑相同’。",
        "",
        "当前最稳妥的物理表述是：**东部暖量到达之后，能否形成强耦合，还取决于大气响应之前中太平洋是否存在足够的次表层暖层支撑；形成的耦合状态随后与风驱5°N暖量路由一致变化。**",
        "",
        "## 尚未闭合之处",
        "",
        "- 相关与事件bootstrap只能检验时间有序的一致性，不能排除共同外因。",
        "- 13个事件的样本量较小，控制总量后的空间分布效应不稳健。",
        "- 下一步应做AGCM或耦合敏感性试验：保持东部SST强迫近似一致，只改变中太平洋次表层/表面桥接结构，检验降水—SLP—风应力响应是否改变；随后再检验风应力改变是否重排5°N暖量输送。",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    table, h20 = build_event_table()
    relationships = build_relationships(table, h20)
    models, mediation = standardized_models(table)
    table.to_csv(EVENT_TABLE_CSV, index=False)
    relationships.to_csv(RELATIONSHIP_CSV, index=False)
    models.to_csv(MODEL_CSV, index=False)
    diagnostics = {
        "event_years": list(EVENT_YEARS),
        "early_ocean_window": "Jan-Mar(0)",
        "coupling_window": "May-Jul(0) Jiang-aligned central Pacific zonal-stress response",
        "routing_window": "Jan-May(+1)",
        "ocean_domain": "5S-5N, 0-300 m; central 180-140W; east 140W-80W",
        "coupling_definition": "Primary: Jiang-aligned May-Jul central Pacific zonal-stress response; broad precipitation-SLP-stress mean retained as sensitivity only",
        "mediation": mediation,
        "h20_sensitivity_n": int(len(h20)),
        "limitations": [
            "event-level observational association",
            "small n=13",
            "H20 three-box sensitivity excludes 2023 because the historical monthly extraction ends in 2022",
        ],
    }
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    make_figure(table, relationships)
    make_report(table, h20, relationships, mediation)
    print(f"Wrote {EVENT_TABLE_CSV}")
    print(f"Wrote {RELATIONSHIP_CSV}")
    print(f"Wrote {MODEL_CSV}")
    print(f"Wrote {DIAGNOSTICS_JSON}")
    print(f"Wrote {FIGURE_PNG}")
    print(f"Wrote {FIGURE_PDF}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
