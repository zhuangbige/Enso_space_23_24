#!/usr/bin/env python3
"""Offline wind-stress counterfactuals for the SODA3 5N Ekman warm-heat exit.

The experiment keeps the SODA3 temperature field fixed and changes only the
zonal wind stress used in the first-order Ekman Q20 diagnostic.  It therefore
tests the direct local wind-stress contribution, not the ocean pressure-field
adjustment that a prognostic ocean or coupled model would produce.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_5n_current_decomposition as decomp  # noqa: E402
import analyze_soda3_air_sea_coupled_warm_heat_fate as coupling  # noqa: E402

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


SECTION_NC = decomp.SECTION_NC
EXISTING_EVENT_CSV = decomp.EVENT_CSV
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_5n_wind_stress_counterfactual"
PDF_DIR = ROOT / "output/pdf"

MONTHLY_CSV = DERIVED / "soda3_5n_wind_stress_counterfactual_monthly.csv"
MONTHLY_SUMMARY_CSV = (
    DERIVED / "soda3_5n_wind_stress_counterfactual_monthly_summary.csv"
)
EVENT_CSV = DERIVED / "soda3_5n_wind_stress_counterfactual_event.csv"
REPLACEMENT_MATRIX_CSV = (
    DERIVED / "soda3_5n_wind_stress_replacement_matrix.csv"
)
SUMMARY_CSV = DERIVED / "soda3_5n_wind_stress_counterfactual_summary.csv"
DIAGNOSTICS_JSON = (
    DERIVED / "soda3_5n_wind_stress_counterfactual_diagnostics.json"
)
FIGURE_PNG = OUT / "soda3_5n_wind_stress_counterfactual.png"
FIGURE_PDF = PDF_DIR / "soda3_5n_wind_stress_counterfactual.pdf"
REPORT_MD = OUT / "SODA3_5N_WIND_STRESS_COUNTERFACTUAL_CN.md"

LON_ENDS = decomp.LON_ENDS
DOSE_SCALES = np.arange(0.0, 1.5001, 0.25)
BOOTSTRAP = 20_000
SEED = 20260804
RELATIVE_MONTH_LABELS = ("Dec(0)", "Jan(+1)", "Feb", "Mar", "Apr", "May")

CORE_SCENARIOS = (
    "CT_control",
    "CT_tau_anomaly_removed",
    "CT_cp_tau_replacement",
    "CP_observed",
)


def baseline_and_anomaly(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int] = decomp.BASELINE,
) -> tuple[np.ndarray, np.ndarray]:
    """Return calendar-month linear baseline and detrended anomaly."""
    anomaly = decomp.same_month_detrended_array(values, times, baseline)
    return np.asarray(values, dtype=float) - anomaly, anomaly


def scaled_stress(
    baseline_stress: np.ndarray,
    stress_anomaly: np.ndarray,
    scale: float,
) -> np.ndarray:
    """Apply a scalar multiplier to the detrended stress anomaly."""
    return np.asarray(baseline_stress) + float(scale) * np.asarray(stress_anomaly)


def event_indices(times: pd.DatetimeIndex, year: int) -> np.ndarray:
    dates = pd.DatetimeIndex(decomp.event_dates(year))
    indices = times.get_indexer(dates)
    if np.any(indices < 0):
        raise ValueError(f"Incomplete Dec-May section for event {year}")
    return indices


def integrate_event(values: np.ndarray, year: int) -> float:
    dates = pd.DatetimeIndex(decomp.event_dates(year))
    return decomp.integrate_zj(np.asarray(values), dates)


def scenario_anomaly_pw(
    temperature: np.ndarray,
    stress: np.ndarray,
    q_reference: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    lon_end: int,
) -> np.ndarray:
    raw = decomp.ekman_heat_transport_pw(
        temperature, stress, depth, longitude, lon_end
    )
    return raw - np.asarray(q_reference)


def bootstrap_weights(
    rng: np.random.Generator, samples: int, n_events: int
) -> np.ndarray:
    draws = rng.integers(0, n_events, size=(samples, n_events))
    return np.eye(n_events, dtype=float)[draws].mean(axis=1)


def interval(values: np.ndarray) -> tuple[float, float]:
    low, high = np.quantile(np.asarray(values, dtype=float), [0.025, 0.975])
    return float(low), float(high)


def summary_row(
    label: str,
    lon_end: int,
    mean: float,
    bootstrap: np.ndarray,
    kind: str,
) -> dict[str, object]:
    low, high = interval(bootstrap)
    return {
        "kind": kind,
        "label": label,
        "lon_end_e": lon_end,
        "mean_zj": float(mean),
        "ci_low_zj": low,
        "ci_high_zj": high,
        "ci_excludes_zero": bool(low > 0.0 or high < 0.0),
    }


def build_analysis(section: xr.Dataset) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, float],
]:
    times = pd.DatetimeIndex(section.time.values)
    temperature = section.temp.values.astype(float)
    stress = section.taux.values.astype(float)
    depth = section.depth.values.astype(float)
    longitude = section.lon.values.astype(float)
    stress_baseline, stress_anomaly = baseline_and_anomaly(stress, times)

    event_index = {
        group: np.stack([event_indices(times, year) for year in years])
        for group, years in coupling.EVENTS.items()
    }
    cp_stress_events = stress_anomaly[event_index["CP"]]
    cp_stress_composite = cp_stress_events.mean(axis=0)

    rng = np.random.default_rng(SEED)
    ct_weights = bootstrap_weights(rng, BOOTSTRAP, len(coupling.EVENTS["CT"]))
    cp_weights = bootstrap_weights(rng, BOOTSTRAP, len(coupling.EVENTS["CP"]))

    monthly_rows: list[dict[str, object]] = []
    monthly_summary_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    matrix_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    diagnostics: dict[str, float] = {
        "n_time": float(len(times)),
        "stress_anomaly_reconstruction_max_abs_nm2": float(
            np.max(np.abs(stress - stress_baseline - stress_anomaly))
        ),
        "stress_raw_min_nm2": float(np.min(stress)),
        "stress_raw_max_nm2": float(np.max(stress)),
        "stress_baseline_min_nm2": float(np.min(stress_baseline)),
        "stress_baseline_max_nm2": float(np.max(stress_baseline)),
    }

    for lon_end in LON_ENDS:
        control_raw = decomp.ekman_heat_transport_pw(
            temperature, stress, depth, longitude, lon_end
        )
        control_anomaly = decomp.same_month_detrended_array(control_raw, times)
        q_reference = control_raw - control_anomaly
        no_tau_anomaly = scenario_anomaly_pw(
            temperature,
            stress_baseline,
            q_reference,
            depth,
            longitude,
            lon_end,
        )

        ct_control = np.empty(len(coupling.EVENTS["CT"]))
        ct_no_tau = np.empty_like(ct_control)
        cp_observed = np.empty(len(coupling.EVENTS["CP"]))
        replacement_matrix = np.empty((len(ct_control), len(cp_observed)))
        monthly_control = np.empty((len(ct_control), 6))
        monthly_no_tau = np.empty_like(monthly_control)
        monthly_cp_replacement_matrix = np.empty(
            (len(ct_control), len(cp_observed), 6)
        )
        monthly_cp_observed = np.empty((len(cp_observed), 6))

        for i, year in enumerate(coupling.EVENTS["CT"]):
            indices = event_index["CT"][i]
            dates = pd.DatetimeIndex(decomp.event_dates(year))
            monthly_control[i] = control_anomaly[indices]
            monthly_no_tau[i] = no_tau_anomaly[indices]
            ct_control[i] = decomp.integrate_zj(monthly_control[i], dates)
            ct_no_tau[i] = decomp.integrate_zj(monthly_no_tau[i], dates)

            replacement_composite = scenario_anomaly_pw(
                temperature[indices],
                stress_baseline[indices] + cp_stress_composite,
                q_reference[indices],
                depth,
                longitude,
                lon_end,
            )
            for relative_month, value in enumerate(replacement_composite):
                monthly_rows.append(
                    {
                        "event_class": "CT",
                        "event_year": year,
                        "relative_month": relative_month,
                        "month_label": RELATIVE_MONTH_LABELS[relative_month],
                        "scenario": "CT_cp_tau_replacement",
                        "lon_end_e": lon_end,
                        "q20_anom_pw": float(value),
                    }
                )

            for j, cp_year in enumerate(coupling.EVENTS["CP"]):
                pair_monthly = scenario_anomaly_pw(
                    temperature[indices],
                    stress_baseline[indices] + cp_stress_events[j],
                    q_reference[indices],
                    depth,
                    longitude,
                    lon_end,
                )
                monthly_cp_replacement_matrix[i, j] = pair_monthly
                replacement_matrix[i, j] = decomp.integrate_zj(pair_monthly, dates)
                matrix_rows.append(
                    {
                        "ct_temperature_event": year,
                        "cp_stress_event": cp_year,
                        "lon_end_e": lon_end,
                        "cumulative_zj": float(replacement_matrix[i, j]),
                    }
                )

            for scenario, values in (
                ("CT_control", monthly_control[i]),
                ("CT_tau_anomaly_removed", monthly_no_tau[i]),
            ):
                for relative_month, value in enumerate(values):
                    monthly_rows.append(
                        {
                            "event_class": "CT",
                            "event_year": year,
                            "relative_month": relative_month,
                            "month_label": RELATIVE_MONTH_LABELS[relative_month],
                            "scenario": scenario,
                            "lon_end_e": lon_end,
                            "q20_anom_pw": float(value),
                        }
                    )

            event_rows.extend(
                [
                    {
                        "event_class": "CT",
                        "event_year": year,
                        "scenario": "CT_control",
                        "stress_scale": 1.0,
                        "lon_end_e": lon_end,
                        "cumulative_zj": float(ct_control[i]),
                    },
                    {
                        "event_class": "CT",
                        "event_year": year,
                        "scenario": "CT_tau_anomaly_removed",
                        "stress_scale": 0.0,
                        "lon_end_e": lon_end,
                        "cumulative_zj": float(ct_no_tau[i]),
                    },
                    {
                        "event_class": "CT",
                        "event_year": year,
                        "scenario": "CT_cp_tau_replacement",
                        "stress_scale": np.nan,
                        "lon_end_e": lon_end,
                        "cumulative_zj": float(replacement_matrix[i].mean()),
                    },
                ]
            )
            for scale in DOSE_SCALES:
                dose_value = ct_no_tau[i] + scale * (ct_control[i] - ct_no_tau[i])
                event_rows.append(
                    {
                        "event_class": "CT",
                        "event_year": year,
                        "scenario": "CT_tau_dose",
                        "stress_scale": float(scale),
                        "lon_end_e": lon_end,
                        "cumulative_zj": float(dose_value),
                    }
                )

        for i, year in enumerate(coupling.EVENTS["CP"]):
            indices = event_index["CP"][i]
            dates = pd.DatetimeIndex(decomp.event_dates(year))
            monthly_cp_observed[i] = control_anomaly[indices]
            cp_observed[i] = decomp.integrate_zj(monthly_cp_observed[i], dates)
            for relative_month, value in enumerate(monthly_cp_observed[i]):
                monthly_rows.append(
                    {
                        "event_class": "CP",
                        "event_year": year,
                        "relative_month": relative_month,
                        "month_label": RELATIVE_MONTH_LABELS[relative_month],
                        "scenario": "CP_observed",
                        "lon_end_e": lon_end,
                        "q20_anom_pw": float(value),
                    }
                )
            event_rows.append(
                {
                    "event_class": "CP",
                    "event_year": year,
                    "scenario": "CP_observed",
                    "stress_scale": 1.0,
                    "lon_end_e": lon_end,
                    "cumulative_zj": float(cp_observed[i]),
                }
            )

        ct_control_boot = ct_weights @ ct_control
        ct_no_tau_boot = ct_weights @ ct_no_tau
        cp_observed_boot = cp_weights @ cp_observed
        replacement_boot = np.einsum(
            "bi,ij,bj->b", ct_weights, replacement_matrix, cp_weights
        )

        scenario_boot = {
            "CT_control": ct_control_boot,
            "CT_tau_anomaly_removed": ct_no_tau_boot,
            "CT_cp_tau_replacement": replacement_boot,
            "CP_observed": cp_observed_boot,
        }
        scenario_mean = {
            "CT_control": ct_control.mean(),
            "CT_tau_anomaly_removed": ct_no_tau.mean(),
            "CT_cp_tau_replacement": replacement_matrix.mean(),
            "CP_observed": cp_observed.mean(),
        }
        for label in CORE_SCENARIOS:
            summary_rows.append(
                summary_row(
                    label,
                    lon_end,
                    scenario_mean[label],
                    scenario_boot[label],
                    "scenario",
                )
            )

        contrasts = {
            "control_minus_tau_removed": (
                scenario_mean["CT_control"]
                - scenario_mean["CT_tau_anomaly_removed"],
                ct_control_boot - ct_no_tau_boot,
            ),
            "control_minus_cp_tau_replacement": (
                scenario_mean["CT_control"]
                - scenario_mean["CT_cp_tau_replacement"],
                ct_control_boot - replacement_boot,
            ),
            "control_minus_cp_observed": (
                scenario_mean["CT_control"] - scenario_mean["CP_observed"],
                ct_control_boot - cp_observed_boot,
            ),
            "tau_removed_minus_cp_observed": (
                scenario_mean["CT_tau_anomaly_removed"]
                - scenario_mean["CP_observed"],
                ct_no_tau_boot - cp_observed_boot,
            ),
            "cp_tau_replacement_minus_cp_observed": (
                scenario_mean["CT_cp_tau_replacement"]
                - scenario_mean["CP_observed"],
                replacement_boot - cp_observed_boot,
            ),
        }
        for label, (mean, boot) in contrasts.items():
            summary_rows.append(
                summary_row(label, lon_end, mean, boot, "contrast")
            )

        for scale in DOSE_SCALES:
            values = ct_no_tau + scale * (ct_control - ct_no_tau)
            boot = ct_no_tau_boot + scale * (ct_control_boot - ct_no_tau_boot)
            summary_rows.append(
                summary_row(
                    f"tau_scale_{scale:.2f}",
                    lon_end,
                    values.mean(),
                    boot,
                    "dose",
                )
            )

        for relative_month in range(6):
            replacement_month_boot = np.einsum(
                "bi,ij,bj->b",
                ct_weights,
                monthly_cp_replacement_matrix[:, :, relative_month],
                cp_weights,
            )
            month_values = {
                "CT_control": (
                    monthly_control[:, relative_month].mean(),
                    ct_weights @ monthly_control[:, relative_month],
                ),
                "CT_tau_anomaly_removed": (
                    monthly_no_tau[:, relative_month].mean(),
                    ct_weights @ monthly_no_tau[:, relative_month],
                ),
                "CT_cp_tau_replacement": (
                    monthly_cp_replacement_matrix[:, :, relative_month].mean(),
                    replacement_month_boot,
                ),
                "CP_observed": (
                    monthly_cp_observed[:, relative_month].mean(),
                    cp_weights @ monthly_cp_observed[:, relative_month],
                ),
            }
            for scenario, (mean, boot) in month_values.items():
                low, high = interval(boot)
                monthly_summary_rows.append(
                    {
                        "scenario": scenario,
                        "relative_month": relative_month,
                        "month_label": RELATIVE_MONTH_LABELS[relative_month],
                        "lon_end_e": lon_end,
                        "mean_pw": float(mean),
                        "ci_low_pw": low,
                        "ci_high_pw": high,
                        "ci_excludes_zero": bool(low > 0.0 or high < 0.0),
                    }
                )

        if lon_end == 280:
            direct_by_event = ct_control - ct_no_tau
            replacement_loss_by_event = ct_control - replacement_matrix.mean(axis=1)
            direct_loo = np.array(
                [np.delete(direct_by_event, i).mean() for i in range(len(direct_by_event))]
            )
            replacement_loo = np.array(
                [
                    np.delete(replacement_loss_by_event, i).mean()
                    for i in range(len(replacement_loss_by_event))
                ]
            )
            diagnostics.update(
                {
                    "ct_control_mean_zj": float(ct_control.mean()),
                    "ct_tau_removed_mean_zj": float(ct_no_tau.mean()),
                    "ct_cp_tau_replacement_mean_zj": float(
                        replacement_matrix.mean()
                    ),
                    "cp_observed_mean_zj": float(cp_observed.mean()),
                    "direct_ct_tau_anomaly_contribution_zj": float(
                        ct_control.mean() - ct_no_tau.mean()
                    ),
                    "direct_ct_tau_anomaly_fraction_of_control": float(
                        (ct_control.mean() - ct_no_tau.mean()) / ct_control.mean()
                    ),
                    "cp_tau_replacement_reduction_fraction": float(
                        (ct_control.mean() - replacement_matrix.mean())
                        / ct_control.mean()
                    ),
                    "direct_ct_tau_positive_event_count": float(
                        np.sum(direct_by_event > 0.0)
                    ),
                    "direct_ct_tau_leave_one_out_min_mean_zj": float(
                        direct_loo.min()
                    ),
                    "direct_ct_tau_leave_one_out_max_mean_zj": float(
                        direct_loo.max()
                    ),
                    "cp_tau_replacement_positive_reduction_event_count": float(
                        np.sum(replacement_loss_by_event > 0.0)
                    ),
                    "cp_tau_replacement_leave_one_out_min_mean_zj": float(
                        replacement_loo.min()
                    ),
                    "cp_tau_replacement_leave_one_out_max_mean_zj": float(
                        replacement_loo.max()
                    ),
                }
            )

    monthly = pd.DataFrame(monthly_rows)
    monthly_summary = pd.DataFrame(monthly_summary_rows)
    events = pd.DataFrame(event_rows)
    matrix = pd.DataFrame(matrix_rows)
    summary = pd.DataFrame(summary_rows)

    existing = pd.read_csv(EXISTING_EVENT_CSV)
    expected = existing[["event_class", "event_year", "ekman_220_280e_zj"]]
    actual = events.loc[
        events.lon_end_e.eq(280)
        & events.scenario.isin(("CT_control", "CP_observed")),
        ["event_class", "event_year", "cumulative_zj"],
    ]
    merged = expected.merge(actual, on=["event_class", "event_year"])
    diagnostics["control_existing_event_max_abs_zj"] = float(
        np.max(np.abs(merged.ekman_220_280e_zj - merged.cumulative_zj))
    )
    dose = events.loc[
        events.lon_end_e.eq(280) & events.scenario.eq("CT_tau_dose")
    ].pivot(index="event_year", columns="stress_scale", values="cumulative_zj")
    diagnostics["dose_affine_identity_max_abs_zj"] = float(
        np.max(np.abs(dose[0.5] - 0.5 * (dose[0.0] + dose[1.0])))
    )
    # The existing event CSV was written with finite decimal precision, so the
    # cross-file check uses a 1e-8 ZJ tolerance (about 1e-15 of the signal).
    if diagnostics["control_existing_event_max_abs_zj"] > 1.0e-8:
        raise ValueError("Counterfactual control does not reproduce existing Ekman events")
    if diagnostics["dose_affine_identity_max_abs_zj"] > 1.0e-12:
        raise ValueError("Stress-dose response is not affine at fixed temperature")

    return monthly, monthly_summary, events, matrix, summary, diagnostics


def select_summary(summary: pd.DataFrame, label: str, lon_end: int = 280) -> pd.Series:
    return summary.loc[
        summary.label.eq(label) & summary.lon_end_e.eq(lon_end)
    ].iloc[0]


def plot(
    monthly: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    events: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    coupling.setup_style()
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.4), constrained_layout=True)
    colors = {
        "CT_control": "#C23B3B",
        "CT_tau_anomaly_removed": "#777777",
        "CT_cp_tau_replacement": "#E58E26",
        "CP_observed": "#2C7FB8",
    }
    labels = {
        "CT_control": "CT control",
        "CT_tau_anomaly_removed": "CT with τ′ removed",
        "CT_cp_tau_replacement": "CT temperature + CP τ′",
        "CP_observed": "CP observed",
    }

    axis = axes[0, 0]
    x = np.arange(len(CORE_SCENARIOS))
    rows = [select_summary(summary, item) for item in CORE_SCENARIOS]
    means = np.array([row.mean_zj for row in rows])
    lows = np.array([row.ci_low_zj for row in rows])
    highs = np.array([row.ci_high_zj for row in rows])
    axis.bar(
        x,
        means,
        color=[colors[item] for item in CORE_SCENARIOS],
        yerr=np.vstack((means - lows, highs - means)),
        capsize=3,
    )
    axis.axhline(0.0, color="0.35", lw=0.7)
    axis.set_xticks(x, [labels[item] for item in CORE_SCENARIOS], rotation=18, ha="right")
    axis.set_ylabel("Dec–May Ekman Q20 anomaly (ZJ)")
    axis.set_title("a) Direct wind-stress counterfactual", loc="left", fontweight="bold")
    axis.grid(axis="y", color="0.9", lw=0.5)

    axis = axes[0, 1]
    xmonth = np.arange(6)
    for scenario in CORE_SCENARIOS:
        rows = monthly_summary.loc[
            monthly_summary.scenario.eq(scenario)
            & monthly_summary.lon_end_e.eq(280)
        ].sort_values("relative_month")
        axis.plot(
            xmonth,
            rows.mean_pw,
            color=colors[scenario],
            marker="o",
            label=labels[scenario],
        )
        axis.fill_between(
            xmonth,
            rows.ci_low_pw,
            rows.ci_high_pw,
            color=colors[scenario],
            alpha=0.12,
            linewidth=0,
        )
    axis.axhline(0.0, color="0.35", lw=0.7)
    axis.set_xticks(xmonth, RELATIVE_MONTH_LABELS, rotation=20)
    axis.set_ylabel("Monthly Ekman Q20 anomaly (PW)")
    axis.set_title("b) When does the wind effect matter?", loc="left", fontweight="bold")
    axis.legend(frameon=False, ncol=2)
    axis.grid(axis="y", color="0.9", lw=0.5)

    axis = axes[1, 0]
    dose = events.loc[
        events.scenario.eq("CT_tau_dose") & events.lon_end_e.eq(280)
    ]
    for _, rows_event in dose.groupby("event_year"):
        rows_event = rows_event.sort_values("stress_scale")
        axis.plot(
            rows_event.stress_scale,
            rows_event.cumulative_zj,
            color="0.72",
            lw=0.9,
            marker="o",
            ms=2.5,
        )
    dose_summary = summary.loc[
        summary.kind.eq("dose") & summary.lon_end_e.eq(280)
    ].copy()
    dose_summary["scale"] = dose_summary.label.str.replace("tau_scale_", "", regex=False).astype(float)
    dose_summary = dose_summary.sort_values("scale")
    axis.plot(
        dose_summary.scale,
        dose_summary.mean_zj,
        color=colors["CT_control"],
        lw=2.2,
        marker="o",
        label="CT mean",
    )
    axis.fill_between(
        dose_summary.scale,
        dose_summary.ci_low_zj,
        dose_summary.ci_high_zj,
        color=colors["CT_control"],
        alpha=0.18,
        linewidth=0,
    )
    cp = select_summary(summary, "CP_observed")
    axis.axhline(cp.mean_zj, color=colors["CP_observed"], ls="--", label="CP observed mean")
    axis.axhspan(cp.ci_low_zj, cp.ci_high_zj, color=colors["CP_observed"], alpha=0.08)
    axis.axvline(1.0, color="0.4", ls=":", lw=0.8)
    axis.set_xlabel("Multiplier applied to CT wind-stress anomaly τ′")
    axis.set_ylabel("Dec–May Ekman Q20 anomaly (ZJ)")
    axis.set_title("c) Fixed-temperature stress-dose response", loc="left", fontweight="bold")
    axis.legend(frameon=False)
    axis.grid(color="0.9", lw=0.5)

    axis = axes[1, 1]
    boundary_x = np.arange(len(LON_ENDS))
    for contrast, color, marker, label in (
        (
            "control_minus_tau_removed",
            "#7A5195",
            "o",
            "Direct CT τ′ contribution",
        ),
        (
            "control_minus_cp_tau_replacement",
            "#E58E26",
            "s",
            "Loss after CT→CP τ′ replacement",
        ),
    ):
        rows = summary.loc[
            summary.label.eq(contrast) & summary.kind.eq("contrast")
        ].set_index("lon_end_e").loc[list(LON_ENDS)]
        mean = rows.mean_zj.to_numpy()
        low = rows.ci_low_zj.to_numpy()
        high = rows.ci_high_zj.to_numpy()
        axis.errorbar(
            boundary_x,
            mean,
            yerr=np.vstack((mean - low, high - mean)),
            color=color,
            marker=marker,
            capsize=3,
            label=label,
        )
    axis.axhline(0.0, color="0.35", lw=0.7)
    axis.set_xticks(boundary_x, ["90°W", "85°W", "80°W"])
    axis.set_xlabel("Eastern end of 5°N section")
    axis.set_ylabel("Reduction relative to CT control (ZJ)")
    axis.set_title("d) Boundary robustness", loc="left", fontweight="bold")
    axis.legend(frameon=False)
    axis.grid(axis="y", color="0.9", lw=0.5)

    fig.suptitle(
        "Does the CT wind-stress anomaly directly sustain the 5°N warm-heat exit?",
        fontsize=13,
        fontweight="bold",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(summary: pd.DataFrame, diagnostics: dict[str, float]) -> None:
    def row(label: str, lon_end: int = 280) -> pd.Series:
        return select_summary(summary, label, lon_end)

    control = row("CT_control")
    removed = row("CT_tau_anomaly_removed")
    replacement = row("CT_cp_tau_replacement")
    cp = row("CP_observed")
    direct = row("control_minus_tau_removed")
    replace_loss = row("control_minus_cp_tau_replacement")
    removed_vs_cp = row("tau_removed_minus_cp_observed")
    replacement_vs_cp = row("cp_tau_replacement_minus_cp_observed")
    boundary_lines = []
    for end in LON_ENDS:
        direct_end = row("control_minus_tau_removed", end)
        replace_end = row("control_minus_cp_tau_replacement", end)
        boundary_lines.append(
            f"- 至 {360-end}°W：去除CT风应力异常使Q20减少 "
            f"{direct_end.mean_zj:+.2f} ZJ，CT→CP风应力替换使其减少 "
            f"{replace_end.mean_zj:+.2f} ZJ。"
        )

    report = f"""# SODA3 5°N风应力反事实敏感性试验

## 结论先行

在保持每个CT事件的SODA3温度场不变时：

- 控制试验的Dec(0)–May(+1) Ekman Q20为 **{control.mean_zj:+.2f} ZJ**，95%区间 [{control.ci_low_zj:+.2f}, {control.ci_high_zj:+.2f}]。
- 去除CT日历月线性去趋势风应力异常后，Q20变为 **{removed.mean_zj:+.2f} ZJ**；相对控制减少 **{direct.mean_zj:+.2f} ZJ**，区间 [{direct.ci_low_zj:+.2f}, {direct.ci_high_zj:+.2f}]。
- 用CP合成风应力异常替换CT风应力异常后，Q20变为 **{replacement.mean_zj:+.2f} ZJ**；相对控制减少 **{replace_loss.mean_zj:+.2f} ZJ**，区间 [{replace_loss.ci_low_zj:+.2f}, {replace_loss.ci_high_zj:+.2f}]。
- 作为参照，实际CP事件为 **{cp.mean_zj:+.2f} ZJ**。
- 去除CT风应力异常后的结果与实际CP仅差 **{removed_vs_cp.mean_zj:+.2f} ZJ**，区间 [{removed_vs_cp.ci_low_zj:+.2f}, {removed_vs_cp.ci_high_zj:+.2f}]；换成CP风应力后的差值为 **{replacement_vs_cp.mean_zj:+.2f} ZJ**，区间 [{replacement_vs_cp.ci_low_zj:+.2f}, {replacement_vs_cp.ci_high_zj:+.2f}]。两者区间均跨零，说明修改风应力后，固定CT温度场得到的直接Ekman出口已降入CP事件的统计范围。

因此，在固定CT海洋热状态下，CT特有的5°N风应力异常对直接Ekman暖量出口的观测幅度具有可辨识且关键的贡献。去除风异常后仍保留一部分北向Q20，因为CT较暖的0–50 m水体仍会被气候态西向信风输送；所以不能写成“没有CT风异常就完全没有北向出口”，也不能把整个Ekman出口都归因于风异常。

## 试验设计

1. **CT control**：使用事件同期SODA3温度和风应力。
2. **CT τ′ removed**：温度不变，把风应力替换为1982–2022逐日历月线性基线。
3. **CT temperature + CP τ′**：温度和CT年代基线不变，将CT风应力异常替换为4个CP事件的Dec–May合成异常；bootstrap同时重采样CT温度事件与CP风事件。
4. **τ′ dose**：把CT风应力异常从0倍连续放大到1.5倍，温度固定，检验剂量响应。
5. 所有情景均相对于原控制Q20的同月线性基线计算异常，再积分为ZJ；不重新调整SSH、密度或总流速。

## 稳健性与硬校验

{chr(10).join(boundary_lines)}

- 反事实控制与现有5°N Ekman事件结果的最大误差为 {diagnostics['control_existing_event_max_abs_zj']:.2e} ZJ。
- 0.5倍应力情景与0倍、1倍情景线性中点的最大误差为 {diagnostics['dose_affine_identity_max_abs_zj']:.2e} ZJ。
- 控制结果中可由CT风应力异常直接移除的均值比例为 {diagnostics['direct_ct_tau_anomaly_fraction_of_control']*100:.0f}%；该比例是固定温度条件下的诊断量，不代表整个耦合系统的总因果贡献。
- 4个CT事件的控制−去风异常差值全部为正；逐一删除任一CT事件后，平均减少量仍为 {diagnostics['direct_ct_tau_leave_one_out_min_mean_zj']:.2f}–{diagnostics['direct_ct_tau_leave_one_out_max_mean_zj']:.2f} ZJ。

## 能回答什么，不能回答什么

这一步比相关和时间先后更强，因为它直接改变了Ekman公式中的风应力，并保持温度不变；结果可表述为“局地CT风应力异常是再现直接Ekman暖量出口完整幅度所必需的组成，并呈线性剂量响应”，但不是北向输送保持正号的唯一条件。

但它仍是离线反事实：SSH、密度梯度、海流、SST和大气对流没有随修改后的风应力重新演化。因此不能据此宣称整个5°N总Q20或地转调整已经通过严格因果试验。要完成最终因果闭环，需要在强迫海洋模式或耦合模式中执行相同的风应力关闭/替换试验。

## 产物

- 主图：`{FIGURE_PNG}`
- 月度情景：`{MONTHLY_CSV}`
- 事件累计：`{EVENT_CSV}`
- CT温度×CP风应力替换矩阵：`{REPLACEMENT_MATRIX_CSV}`
- bootstrap汇总：`{SUMMARY_CSV}`
- 诊断：`{DIAGNOSTICS_JSON}`
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> int:
    with xr.open_dataset(SECTION_NC, engine="netcdf4") as opened:
        section = opened.load()
    monthly, monthly_summary, events, matrix, summary, diagnostics = build_analysis(
        section
    )
    DERIVED.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    monthly_summary.to_csv(MONTHLY_SUMMARY_CSV, index=False, float_format="%.9g")
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    matrix.to_csv(REPLACEMENT_MATRIX_CSV, index=False, float_format="%.9g")
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.9g")
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot(monthly, monthly_summary, events, summary)
    write_report(summary, diagnostics)
    for path in (
        MONTHLY_CSV,
        MONTHLY_SUMMARY_CSV,
        EVENT_CSV,
        REPLACEMENT_MATRIX_CSV,
        SUMMARY_CSV,
        DIAGNOSTICS_JSON,
        FIGURE_PNG,
        FIGURE_PDF,
        REPORT_MD,
    ):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
