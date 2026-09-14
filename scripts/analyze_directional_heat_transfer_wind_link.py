#!/usr/bin/env python3
"""Relate direct directional upper-ocean heat transfers to wind response.

This script uses the existing mass-balanced SODA3 0--300 m two-box anomaly
budget and the existing Jiang-event physical-variable means.  It does not
define a coupling/decoupling index or a new heat-routing metric.  Positive
directional terms in the output table follow their literal labels:

* west_input: heat entering through the western face;
* eastward_output: heat leaving through the eastern face;
* northward_output / southward_output: heat leaving the named meridional face;
* surface_loss: heat leaving the ocean through the surface.

Negative values therefore indicate transport or surface exchange in the
opposite direction.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/jiang_epcp_two_box_heat_fate"

BUDGET_FILE = DERIVED / "soda3_three_box_ohc_anomaly_budget_monthly.csv"
MJJ_PHYSICAL_FILE = DERIVED / "jiang_epcp_mjj_direct_physical_variable_means.csv"
EVENT_BUDGET_FILE = DERIVED / "jiang_epcp_two_box_event_budgets.csv"

PHASE_FILE = DERIVED / "jiang_directional_heat_transfer_wind_direct_phases.csv"
RELATION_FILE = DERIVED / "jiang_early_direction_mjj_wind_direct_relations.csv"
METADATA_FILE = DERIVED / "jiang_directional_heat_transfer_wind_diagnostics.json"

PATHWAY_FIGURE = OUT / "jiang_1997_2015_2023_directional_heat_pathways.png"
RELATION_FIGURE = OUT / "jiang_all_events_early_direction_vs_mjj_stress.png"

EVENTS = (1997, 2015, 2023)
PHASES = {"JFM": (1, 3), "MJJ": (5, 7)}
COLORS = {1997: "#C44E52", 2015: "#DD8452", 2023: "#6F4E9C"}
GROUP_COLORS = {"EP": "#D95F02", "CP": "#2A9D8F", "2023": "#7B2CBF"}


def integrate_zj(values_pw: pd.Series, times: pd.Series) -> float:
    """Use the same month-centre trapezoidal integration as the box audit."""
    values = values_pw.to_numpy(dtype=float)
    timestamps = pd.DatetimeIndex(times)
    seconds = (timestamps - timestamps[0]).total_seconds().to_numpy(dtype=float)
    return float(np.trapezoid(values, x=seconds) / 1.0e6)


def build_phase_table() -> pd.DataFrame:
    budget = pd.read_csv(BUDGET_FILE, parse_dates=["time"])
    physical = pd.read_csv(MJJ_PHYSICAL_FILE).set_index("event_year")
    rows: list[dict[str, object]] = []
    for event_year, physical_row in physical.iterrows():
        for phase, (month_start, month_end) in PHASES.items():
            selected = budget.loc[
                budget.year.eq(event_year)
                & budget.month.between(month_start, month_end)
            ].copy()
            expected = month_end - month_start + 1
            if len(selected) != expected:
                raise ValueError(
                    f"Expected {expected} months for {event_year} {phase}, found {len(selected)}"
                )
            for box in ("central", "east"):
                west_input = integrate_zj(
                    selected[f"{box}_west_theta_heat_in_corr_anom_pw"],
                    selected.time,
                )
                eastward_output = -integrate_zj(
                    selected[f"{box}_east_theta_heat_in_corr_anom_pw"],
                    selected.time,
                )
                southward_output = -integrate_zj(
                    selected[f"{box}_south_theta_heat_in_corr_anom_pw"],
                    selected.time,
                )
                northward_output = -integrate_zj(
                    selected[f"{box}_north_theta_heat_in_corr_anom_pw"],
                    selected.time,
                )
                surface_loss = -integrate_zj(
                    selected[f"{box}_surface_anom_pw"], selected.time
                )
                transport_convergence = integrate_zj(
                    selected[f"{box}_transport_convergence_anom_pw"],
                    selected.time,
                )
                surface_input = -surface_loss
                storage_change = float(
                    selected[f"{box}_ohc300_anom_zj"].iloc[-1]
                    - selected[f"{box}_ohc300_anom_zj"].iloc[0]
                )
                rows.append(
                    {
                        "event_year": int(event_year),
                        "event_label": physical_row.event_label,
                        "group": physical_row.group,
                        "phase": phase,
                        "month_start": month_start,
                        "month_end": month_end,
                        "box": box,
                        "storage_change_zj": storage_change,
                        "west_input_zj": west_input,
                        "eastward_output_zj": eastward_output,
                        "southward_output_zj": southward_output,
                        "northward_output_zj": northward_output,
                        "surface_loss_zj": surface_loss,
                        "transport_convergence_zj": transport_convergence,
                        "unresolved_storage_contribution_zj": (
                            storage_change - transport_convergence - surface_input
                        ),
                        "mjj_central_taux_anom_nm2": physical_row.central_taux_anom_nm2,
                        "mjj_central_precip_anom_mm_day": physical_row.central_precip_anom_mm_day,
                        "mjj_central_sst_anom_c": physical_row.central_sst_anom_c,
                        "mjj_east_sst_anom_c": physical_row.east_sst_anom_c,
                    }
                )
    return pd.DataFrame(rows)


def validate_against_event_budget(phases: pd.DataFrame) -> dict[str, float]:
    existing = pd.read_csv(EVENT_BUDGET_FILE)
    existing = existing.loc[existing.phase.eq("development_MJJ")]
    computed = phases.loc[phases.phase.eq("MJJ")]
    pairs = {
        "storage_change_zj": "storage_change_zj",
        "west_input_zj": "west_heat_in_zj",
        "eastward_output_zj": "east_heat_in_zj",
        "southward_output_zj": "south_heat_in_zj",
        "northward_output_zj": "north_heat_in_zj",
        "surface_loss_zj": "surface_heat_in_zj",
    }
    computed_columns = ["event_year", "box", *pairs]
    existing_columns = ["event_year", "box", *dict.fromkeys(pairs.values())]
    computed_check = computed[computed_columns].rename(
        columns={name: f"{name}_computed" for name in pairs}
    )
    existing_check = existing[existing_columns].rename(
        columns={name: f"{name}_existing" for name in set(pairs.values())}
    )
    merged = computed_check.merge(
        existing_check,
        on=["event_year", "box"],
        validate="one_to_one",
    )
    errors: dict[str, float] = {}
    for computed_name, existing_name in pairs.items():
        sign = -1.0 if computed_name in {
            "eastward_output_zj",
            "southward_output_zj",
            "northward_output_zj",
            "surface_loss_zj",
        } else 1.0
        difference = (
            merged[f"{computed_name}_computed"]
            - sign * merged[f"{existing_name}_existing"]
        )
        errors[computed_name] = float(np.nanmax(np.abs(difference)))
    if max(errors.values()) > 1.0e-7:
        raise ValueError(f"MJJ integration did not reproduce event budget: {errors}")
    return errors


def phase_wide(phases: pd.DataFrame, phase: str) -> pd.DataFrame:
    selected = phases.loc[phases.phase.eq(phase)].copy()
    identity = (
        selected[["event_year", "event_label", "group", "mjj_central_taux_anom_nm2"]]
        .drop_duplicates("event_year")
        .set_index("event_year")
    )
    directional = selected.pivot(
        index="event_year",
        columns="box",
        values=[
            "storage_change_zj",
            "west_input_zj",
            "eastward_output_zj",
            "southward_output_zj",
            "northward_output_zj",
            "surface_loss_zj",
            "unresolved_storage_contribution_zj",
        ],
    )
    directional.columns = [f"{box}_{metric}" for metric, box in directional.columns]
    return identity.join(directional)


def build_relations(phases: pd.DataFrame) -> pd.DataFrame:
    early = phase_wide(phases, "JFM")
    rows: list[dict[str, object]] = []
    for variable in [
        "central_west_input_zj",
        "central_eastward_output_zj",
        "central_southward_output_zj",
        "central_northward_output_zj",
        "central_surface_loss_zj",
        "central_storage_change_zj",
        "east_west_input_zj",
        "east_eastward_output_zj",
        "east_southward_output_zj",
        "east_northward_output_zj",
        "east_surface_loss_zj",
        "east_storage_change_zj",
    ]:
        for sample, selected in (
            ("all_events", early),
            ("historical_only", early.loc[early.index != 2023]),
        ):
            values = selected[[variable, "mjj_central_taux_anom_nm2"]].dropna()
            pearson = pearsonr(
                values[variable], values.mjj_central_taux_anom_nm2
            )
            spearman = spearmanr(
                values[variable], values.mjj_central_taux_anom_nm2
            )
            rows.append(
                {
                    "sample": sample,
                    "early_JFM_variable": variable,
                    "later_variable": "mjj_central_taux_anom_nm2",
                    "n_events": len(values),
                    "pearson_r": float(pearson.statistic),
                    "pearson_p_unadjusted": float(pearson.pvalue),
                    "spearman_rho": float(spearman.statistic),
                    "spearman_p_unadjusted": float(spearman.pvalue),
                }
            )
    return pd.DataFrame(rows)


def make_pathway_figure(phases: pd.DataFrame) -> None:
    terms = [
        ("central_storage_change_zj", "C storage"),
        ("central_west_input_zj", "C west\ninput"),
        ("central_eastward_output_zj", "C east\noutput"),
        ("central_southward_output_zj", "C south\noutput"),
        ("central_northward_output_zj", "C north\noutput"),
        ("central_surface_loss_zj", "C surface\nloss"),
        ("east_storage_change_zj", "E storage"),
        ("east_west_input_zj", "E west\ninput"),
        ("east_eastward_output_zj", "E east\noutput"),
        ("east_southward_output_zj", "E south\noutput"),
        ("east_northward_output_zj", "E north\noutput"),
        ("east_surface_loss_zj", "E surface\nloss"),
    ]
    labels = [label for _, label in terms]
    x = np.arange(len(terms), dtype=float)
    width = 0.25
    fig, axes = plt.subplots(2, 1, figsize=(14.2, 8.0), constrained_layout=True)
    for axis, phase in zip(axes, ("JFM", "MJJ"), strict=True):
        wide = phase_wide(phases, phase)
        for offset, event_year in zip((-width, 0.0, width), EVENTS, strict=True):
            values = [wide.loc[event_year, variable] for variable, _ in terms]
            stress = wide.loc[event_year, "mjj_central_taux_anom_nm2"]
            axis.bar(
                x + offset,
                values,
                width=width,
                color=COLORS[event_year],
                edgecolor="white",
                linewidth=0.5,
                label=f"{event_year}; MJJ stress {stress:+.3f} N m⁻²",
            )
        axis.axhline(0.0, color="#333333", linewidth=0.8)
        axis.axvline(5.5, color="#777777", linestyle=":", linewidth=1.0)
        axis.axvspan(-0.5, 5.5, color="#4C78A8", alpha=0.035)
        axis.axvspan(5.5, 11.5, color="#F58518", alpha=0.035)
        axis.set_xticks(x, labels)
        axis.tick_params(axis="x", labelsize=8)
        axis.set_ylabel("Integrated anomaly (ZJ)")
        axis.set_title(
            f"{phase}: direct directional heat transfers and storage",
            loc="left",
            fontweight="bold",
        )
        axis.grid(axis="y", color="#DDDDDD", linewidth=0.6)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, ncol=3, loc="upper right", fontsize=8.5)
    fig.suptitle(
        "1997, 2015 and 2023 upper-ocean heat pathways",
        fontsize=16,
        fontweight="bold",
        y=1.070,
    )
    fig.text(
        0.5,
        1.025,
        "C: central box; E: eastern box. Positive terms follow their labels; negative values mean the opposite direction.",
        ha="center",
        fontsize=9.5,
        color="#444444",
    )
    fig.savefig(PATHWAY_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_relation_figure(phases: pd.DataFrame, relations: pd.DataFrame) -> None:
    early = phase_wide(phases, "JFM")
    specs = [
        ("central_west_input_zj", "Central west input"),
        ("central_eastward_output_zj", "Central eastward output"),
        ("central_southward_output_zj", "Central southward output"),
        ("east_northward_output_zj", "Eastern northward output"),
        ("central_surface_loss_zj", "Central surface heat loss"),
        ("east_surface_loss_zj", "Eastern surface heat loss"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12.7, 7.8), constrained_layout=True)
    for panel, (axis, (variable, label)) in enumerate(
        zip(axes.flat, specs, strict=True)
    ):
        for group, marker, size in (("CP", "o", 46), ("EP", "s", 54), ("2023", "*", 180)):
            selected = early.loc[early.group.eq(group)]
            axis.scatter(
                selected[variable],
                selected.mjj_central_taux_anom_nm2,
                color=GROUP_COLORS[group],
                marker=marker,
                s=size,
                edgecolor="white",
                linewidth=0.65,
                zorder=3,
                label=("2023/24" if group == "2023" else group),
            )
        for event_year in EVENTS:
            row = early.loc[event_year]
            axis.annotate(
                str(event_year),
                (row[variable], row.mjj_central_taux_anom_nm2),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7.5,
            )
        relation = relations.loc[
            relations["sample"].eq("all_events")
            & relations.early_JFM_variable.eq(variable)
        ].iloc[0]
        axis.axhline(0.0, color="#777777", linewidth=0.7)
        axis.axvline(0.0, color="#AAAAAA", linewidth=0.6, linestyle=":")
        axis.set_title(
            f"{chr(97 + panel)}) {label}\nraw Pearson r={relation.pearson_r:+.2f}",
            loc="left",
            fontsize=10,
            fontweight="bold",
        )
        axis.set_xlabel("JFM integrated anomaly (ZJ)")
        axis.set_ylabel("MJJ central eastward stress (N m⁻²)")
        axis.grid(color="#E5E5E5", linewidth=0.5)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle(
        "Direct early heat-direction terms versus later central-Pacific wind stress",
        fontsize=15,
        fontweight="bold",
        y=1.070,
    )
    fig.text(
        0.5,
        1.025,
        "Four Jiang-consistent EP events, nine CP events, and 2023; correlations are descriptive and unadjusted.",
        ha="center",
        fontsize=9.2,
        color="#444444",
    )
    fig.savefig(RELATION_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    phases = build_phase_table()
    validation = validate_against_event_budget(phases)
    relations = build_relations(phases)
    phases.to_csv(PHASE_FILE, index=False)
    relations.to_csv(RELATION_FILE, index=False)
    make_pathway_figure(phases)
    make_relation_figure(phases, relations)
    diagnostics = {
        "scope": "Direct physical terms only; no new coupling or routing index.",
        "budget_definition": "dOHC'/dt = corrected lateral enthalpy convergence' + surface heat flux' + unresolved contribution",
        "sign_convention": "Positive directional values follow the output column labels; negative values indicate the opposite direction.",
        "integration": "Month-centre trapezoidal integration, matching the existing Jiang event-budget audit.",
        "n_events": int(phases.event_year.nunique()),
        "events": [int(value) for value in sorted(phases.event_year.unique())],
        "mjj_reproduction_max_abs_error_zj": validation,
        "phase_table": str(PHASE_FILE),
        "relation_table": str(RELATION_FILE),
    }
    METADATA_FILE.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    print(f"Wrote {PHASE_FILE}")
    print(f"Wrote {RELATION_FILE}")
    print(f"Wrote {METADATA_FILE}")
    print(f"Wrote {PATHWAY_FIGURE}")
    print(f"Wrote {RELATION_FIGURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
