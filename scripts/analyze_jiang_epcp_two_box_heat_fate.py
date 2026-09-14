#!/usr/bin/env python3
"""Jiang-aligned EP/CP two-box upper-ocean heat-fate analysis.

The analysis keeps mature ENSO flavor and developing pathway as two separate
labels.  It uses the fixed-depth, mass-balanced SODA3 0--300 m OHC anomaly
budget for a central box (180E--140W) and an eastern box (140W--80W), both
10S--5N.  Historical EP and CP events form event-level reference samples;
2023 is retained as an out-of-sample FEP-dominant case.

Important provenance note
-------------------------
The local Jiang et al. (2026) main-text PDF explicitly gives the five
FEP-dominant events, the mature type of those five, and the aggregate result
that 12 of 16 non-FEP events are CP.  The individual non-FEP labels are in
Supporting Figure S6, which is not present in the local 11-page PDF.  The
non-FEP event labels used here are therefore exported as a transparent
"Jiang-consistent working reconstruction", never as verbatim paper labels.
"""

from __future__ import annotations

from itertools import combinations
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/jiang_epcp_two_box_heat_fate"

BUDGET_FILE = DERIVED / "soda3_three_box_ohc_anomaly_budget_monthly.csv"
PREDICTOR_FILE = DERIVED / "ep_cp_two_gate_monthly_predictors_1982_2023.csv"

MANIFEST_FILE = DERIVED / "jiang2026_epcp_fep_event_manifest_1963_2023.csv"
EVENT_FILE = DERIVED / "jiang_epcp_two_box_event_budgets.csv"
SUMMARY_FILE = DERIVED / "jiang_epcp_two_box_group_summary.csv"
DIFFERENCE_FILE = DERIVED / "jiang_epcp_two_box_ep_minus_cp_differences.csv"
STATE_FILE = DERIVED / "jiang_epcp_may_jun_surface_subsurface_state.csv"
SENSITIVITY_FILE = DERIVED / "jiang_epcp_two_box_sensitivity.csv"
DIAGNOSTICS_FILE = DERIVED / "jiang_epcp_two_box_diagnostics.json"

FIGURE_PNG = OUT / "jiang_epcp_two_box_heat_fate_summary.png"
FIGURE_PDF = OUT / "jiang_epcp_two_box_heat_fate_summary.pdf"
AUDIT_FILE = DERIVED / "jiang_epcp_mjj_event_heat_routing_audit.csv"
AUDIT_FIGURE_PNG = OUT / "jiang_epcp_mjj_event_heat_routing_audit.png"
AUDIT_FIGURE_PDF = OUT / "jiang_epcp_mjj_event_heat_routing_audit.pdf"
REPORT_FILE = OUT / "JIANG_EPCP_TWO_BOX_HEAT_FATE_CN.md"

BOX_LABELS = {"central": "Central box", "east": "Eastern box"}
COLORS = {"CP": "#2A9D8F", "EP": "#D95F02", "2023": "#7B2CBF"}

JIANG_EVENTS = (
    1963,
    1965,
    1968,
    1969,
    1972,
    1976,
    1977,
    1979,
    1982,
    1986,
    1987,
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
FEP_DOMINANT = {1965, 1969, 1972, 1976, 2023}
FEP_EP_EXPLICIT = {1965, 1972, 1976, 2023}
FEP_CP_EXPLICIT = {1969}

# Working reconstruction consistent with the Jiang main-text aggregate:
# 12 of 16 non-FEP events are CP and four are EP.  The 1963 event is retained
# as unresolved because 5 FEP + 16 non-FEP = 21 whereas the methods list 22.
WORKING_NONFEP_EP = {1982, 1986, 1997, 2015}
WORKING_NONFEP_CP = {
    1968,
    1977,
    1979,
    1987,
    1991,
    1994,
    2002,
    2004,
    2006,
    2009,
    2018,
    2019,
}

HISTORICAL_EP = (1982, 1986, 1997, 2015)
HISTORICAL_CP = (1987, 1991, 1994, 2002, 2004, 2006, 2009, 2018, 2019)
TARGET_EVENT = 2023

PHASES = {
    "arrival_Jan_Jun": (0, 1, 6),
    "development_MJJ": (0, 5, 7),
    "growth_Jul_Dec": (0, 7, 12),
    "decay_Jan_May_next": (1, 1, 5),
}
PRIMARY_PHASE = "development_MJJ"
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260813

BASE_METRICS = (
    "storage_change_zj",
    "transport_convergence_zj",
    "west_heat_in_zj",
    "east_heat_in_zj",
    "south_heat_in_zj",
    "north_heat_in_zj",
    "surface_heat_in_zj",
    "unresolved_storage_contribution_zj",
    "central_eastward_output_zj",
    "east_westward_return_zj",
    "northward_output_zj",
    "southward_output_zj",
    "surface_loss_zj",
)


def event_label(year: int) -> str:
    return f"{year}/{str(year + 1)[-2:]}"


def build_manifest() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year in JIANG_EVENTS:
        if year in FEP_EP_EXPLICIT:
            mature_type = "EP"
            evidence = "Explicit in Jiang et al. (2026) main-text discussion"
        elif year in FEP_CP_EXPLICIT:
            mature_type = "CP"
            evidence = "Explicit in Jiang et al. (2026) main-text discussion"
        elif year in WORKING_NONFEP_EP:
            mature_type = "EP"
            evidence = (
                "Jiang-consistent working reconstruction; individual S6 label "
                "not present in local main-text PDF"
            )
        elif year in WORKING_NONFEP_CP:
            mature_type = "CP"
            evidence = (
                "Jiang-consistent working reconstruction; individual S6 label "
                "not present in local main-text PDF"
            )
        else:
            mature_type = "unresolved"
            evidence = (
                "Retained as unresolved: Jiang lists 22 events but the mature-type "
                "discussion accounts for 5 FEP plus 16 non-FEP events"
            )
        rows.append(
            {
                "event_year": year,
                "event_label": event_label(year),
                "fep_dominant": year in FEP_DOMINANT,
                "mature_type_working": mature_type,
                "classification_evidence": evidence,
                "soda3_primary_role": (
                    "historical_EP"
                    if year in HISTORICAL_EP
                    else "historical_CP"
                    if year in HISTORICAL_CP
                    else "target_2023"
                    if year == TARGET_EVENT
                    else "outside_SODA3_primary_sample"
                ),
                "independence_note": (
                    "1986/87 and 1987/88 are consecutive Jiang events; "
                    "a drop-1987 sensitivity test is reported"
                    if year in {1986, 1987}
                    else ""
                ),
            }
        )
    return pd.DataFrame(rows)


def load_budget() -> pd.DataFrame:
    required = ["time", "year", "month"]
    for box in BOX_LABELS:
        required.extend(
            [
                f"{box}_ohc300_anom_zj",
                f"{box}_transport_convergence_anom_pw",
                f"{box}_surface_anom_pw",
                *[
                    f"{box}_{face}_theta_heat_in_corr_anom_pw"
                    for face in ("west", "east", "south", "north")
                ],
            ]
        )
    budget = pd.read_csv(BUDGET_FILE, usecols=required, parse_dates=["time"])
    budget = budget.sort_values("time").reset_index(drop=True)
    return budget


def integrate_zj(values_pw: pd.Series, times: pd.Series) -> float:
    values = values_pw.to_numpy(dtype=float)
    timestamps = pd.DatetimeIndex(times)
    if len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("Phase integration needs at least two finite months")
    seconds = (timestamps - timestamps[0]).total_seconds().to_numpy(dtype=float)
    return float(np.trapezoid(values, x=seconds) / 1.0e6)


def event_group(year: int) -> str:
    if year in HISTORICAL_EP:
        return "EP"
    if year in HISTORICAL_CP:
        return "CP"
    if year == TARGET_EVENT:
        return "2023"
    raise KeyError(year)


def build_event_budgets(budget: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year in (*HISTORICAL_EP, *HISTORICAL_CP, TARGET_EVENT):
        for phase, (offset, month0, month1) in PHASES.items():
            selected = budget.loc[
                budget.year.eq(year + offset)
                & budget.month.between(month0, month1)
            ].copy()
            expected_n = month1 - month0 + 1
            if len(selected) != expected_n:
                raise ValueError(f"Incomplete {phase} for {year}: {len(selected)} months")
            for box in BOX_LABELS:
                storage = float(
                    selected[f"{box}_ohc300_anom_zj"].iloc[-1]
                    - selected[f"{box}_ohc300_anom_zj"].iloc[0]
                )
                transport = integrate_zj(
                    selected[f"{box}_transport_convergence_anom_pw"],
                    selected["time"],
                )
                surface = integrate_zj(
                    selected[f"{box}_surface_anom_pw"], selected["time"]
                )
                face_values = {
                    face: integrate_zj(
                        selected[f"{box}_{face}_theta_heat_in_corr_anom_pw"],
                        selected["time"],
                    )
                    for face in ("west", "east", "south", "north")
                }
                unresolved = storage - transport - surface
                rows.append(
                    {
                        "event_year": year,
                        "event_label": event_label(year),
                        "group": event_group(year),
                        "phase": phase,
                        "target_year": year + offset,
                        "month_start": month0,
                        "month_end": month1,
                        "box": box,
                        "storage_change_zj": storage,
                        "transport_convergence_zj": transport,
                        "west_heat_in_zj": face_values["west"],
                        "east_heat_in_zj": face_values["east"],
                        "south_heat_in_zj": face_values["south"],
                        "north_heat_in_zj": face_values["north"],
                        "surface_heat_in_zj": surface,
                        "unresolved_storage_contribution_zj": unresolved,
                        "central_eastward_output_zj": (
                            -face_values["east"] if box == "central" else np.nan
                        ),
                        "east_westward_return_zj": (
                            -face_values["west"] if box == "east" else np.nan
                        ),
                        "northward_output_zj": -face_values["north"],
                        "southward_output_zj": -face_values["south"],
                        "surface_loss_zj": -surface,
                    }
                )
    return pd.DataFrame(rows)


def bootstrap_mean_ci(
    values: np.ndarray, rng: np.random.Generator
) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    samples = rng.choice(values, size=(BOOTSTRAP_SAMPLES, len(values)), replace=True)
    means = samples.mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def exact_permutation_difference(
    ep_values: np.ndarray, cp_values: np.ndarray
) -> tuple[float, float, int]:
    ep_values = np.asarray(ep_values, dtype=float)
    cp_values = np.asarray(cp_values, dtype=float)
    ep_values = ep_values[np.isfinite(ep_values)]
    cp_values = cp_values[np.isfinite(cp_values)]
    pooled = np.concatenate([ep_values, cp_values])
    observed = float(ep_values.mean() - cp_values.mean())
    permutations: list[float] = []
    for chosen in combinations(range(len(pooled)), len(ep_values)):
        mask = np.zeros(len(pooled), dtype=bool)
        mask[list(chosen)] = True
        permutations.append(float(pooled[mask].mean() - pooled[~mask].mean()))
    permutation_array = np.asarray(permutations)
    p_value = float(
        np.mean(np.abs(permutation_array) >= abs(observed) - 1.0e-12)
    )
    return observed, p_value, len(permutations)


def build_group_statistics(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_SEED)
    summary_rows: list[dict[str, object]] = []
    difference_rows: list[dict[str, object]] = []
    for phase in PHASES:
        for box in BOX_LABELS:
            selected = events.loc[events.phase.eq(phase) & events.box.eq(box)]
            for metric in BASE_METRICS:
                available = selected.loc[selected[metric].notna()]
                if available.empty:
                    continue
                for group in ("EP", "CP"):
                    values = available.loc[available.group.eq(group), metric].to_numpy(
                        dtype=float
                    )
                    if len(values) == 0:
                        continue
                    low, high = bootstrap_mean_ci(values, rng)
                    summary_rows.append(
                        {
                            "phase": phase,
                            "box": box,
                            "metric": metric,
                            "group": group,
                            "n_events": len(values),
                            "events": ",".join(
                                str(v)
                                for v in available.loc[
                                    available.group.eq(group), "event_year"
                                ]
                            ),
                            "mean": float(values.mean()),
                            "median": float(np.median(values)),
                            "ci95_low": low,
                            "ci95_high": high,
                        }
                    )
                ep = available.loc[available.group.eq("EP"), metric].to_numpy(float)
                cp = available.loc[available.group.eq("CP"), metric].to_numpy(float)
                if len(ep) and len(cp):
                    difference, p_value, n_perm = exact_permutation_difference(ep, cp)
                    difference_rows.append(
                        {
                            "phase": phase,
                            "box": box,
                            "metric": metric,
                            "ep_mean": float(ep.mean()),
                            "cp_mean": float(cp.mean()),
                            "ep_minus_cp": difference,
                            "exact_two_sided_p": p_value,
                            "n_exact_partitions": n_perm,
                            "ep_n": len(ep),
                            "cp_n": len(cp),
                        }
                    )
    return pd.DataFrame(summary_rows), pd.DataFrame(difference_rows)


def build_sensitivity(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    primary = events.loc[events.phase.eq(PRIMARY_PHASE)]
    for box, metric in (
        ("central", "storage_change_zj"),
        ("central", "central_eastward_output_zj"),
        ("east", "storage_change_zj"),
        ("east", "west_heat_in_zj"),
    ):
        selected = primary.loc[primary.box.eq(box) & primary[metric].notna()]
        ep = selected.loc[selected.group.eq("EP"), metric].to_numpy(float)
        for name, cp_years in (
            ("primary_Jiang_event_list", HISTORICAL_CP),
            ("drop_consecutive_1987", tuple(y for y in HISTORICAL_CP if y != 1987)),
        ):
            cp = selected.loc[
                selected.group.eq("CP") & selected.event_year.isin(cp_years), metric
            ].to_numpy(float)
            difference, p_value, n_perm = exact_permutation_difference(ep, cp)
            rows.append(
                {
                    "sensitivity": name,
                    "phase": PRIMARY_PHASE,
                    "box": box,
                    "metric": metric,
                    "ep_n": len(ep),
                    "cp_n": len(cp),
                    "ep_mean": float(ep.mean()),
                    "cp_mean": float(cp.mean()),
                    "ep_minus_cp": difference,
                    "exact_two_sided_p": p_value,
                    "n_exact_partitions": n_perm,
                }
            )
    return pd.DataFrame(rows)


def build_may_jun_state() -> pd.DataFrame:
    predictors = pd.read_csv(PREDICTOR_FILE)
    rows: list[dict[str, object]] = []
    for year in (*HISTORICAL_EP, *HISTORICAL_CP, TARGET_EVENT):
        selected = predictors.loc[
            predictors.year.eq(year) & predictors.month.between(5, 7)
        ]
        if len(selected) != 2:
            raise ValueError(f"Missing May-Jun state predictors for {year}")
        rows.append(
            {
                "event_year": year,
                "event_label": event_label(year),
                "group": event_group(year),
                "nino3_ssta_c": float(selected.nino3_anom_c.mean()),
                "nino4_ssta_c": float(selected.nino4_anom_c.mean()),
                "nino34_ssta_c": float(selected.nino34_anom_c.mean()),
                "fep_ssta_c": float(selected.fep_anom_c.mean()),
                "fep_residual_c": float(selected.fep_residual_c.mean()),
                "nino3_minus_nino4_c": float(selected.init_type_anom_c.mean()),
                "central_ohc300_anom_gjm2": float(
                    selected.ohc300_central_anom_jm2.mean() / 1.0e9
                ),
                "east_minus_west_ohc300_anom_gjm2": float(
                    selected.ohc300_east_minus_west_anom_jm2.mean() / 1.0e9
                ),
            }
        )
    return pd.DataFrame(rows)


def build_event_audit(events: pd.DataFrame) -> pd.DataFrame:
    """Build one MJJ heat-routing record per event and rank 2023 analogues."""
    selected = events.loc[events.phase.eq(PRIMARY_PHASE)]
    central = selected.loc[selected.box.eq("central")].set_index("event_year")
    east = selected.loc[selected.box.eq("east")].set_index("event_year")
    rows: list[dict[str, object]] = []
    years = (*HISTORICAL_EP, *HISTORICAL_CP, TARGET_EVENT)
    for year in years:
        rows.append(
            {
                "event_year": year,
                "event_label": event_label(year),
                "group": event_group(year),
                "central_storage_change_zj": float(
                    central.loc[year, "storage_change_zj"]
                ),
                "central_eastward_output_zj": float(
                    central.loc[year, "central_eastward_output_zj"]
                ),
                "east_storage_change_zj": float(
                    east.loc[year, "storage_change_zj"]
                ),
                "east_west_boundary_input_zj": float(
                    east.loc[year, "west_heat_in_zj"]
                ),
                "central_northward_output_zj": float(
                    central.loc[year, "northward_output_zj"]
                ),
                "central_surface_loss_zj": float(
                    central.loc[year, "surface_loss_zj"]
                ),
                "east_northward_output_zj": float(
                    east.loc[year, "northward_output_zj"]
                ),
                "east_surface_loss_zj": float(east.loc[year, "surface_loss_zj"]),
            }
        )
    audit = pd.DataFrame(rows)
    features = [
        "central_storage_change_zj",
        "central_eastward_output_zj",
        "east_storage_change_zj",
        "east_west_boundary_input_zj",
    ]
    historical = audit.loc[audit.event_year.ne(TARGET_EVENT), features]
    scale = historical.std(ddof=1).replace(0.0, np.nan)
    target = audit.loc[audit.event_year.eq(TARGET_EVENT), features].iloc[0]
    audit["routing_distance_to_2023"] = np.sqrt(
        (((audit[features] - target) / scale) ** 2).mean(axis=1)
    )
    audit["central_discharge_east_gain"] = (
        audit.central_storage_change_zj.lt(0)
        & audit.east_storage_change_zj.gt(0)
    )
    audit["eastward_boundary_transfer_consistent"] = (
        audit.central_eastward_output_zj.gt(0)
        & audit.east_west_boundary_input_zj.gt(0)
    )
    return audit.sort_values("event_year").reset_index(drop=True)


def make_event_audit_figure(audit: pd.DataFrame) -> None:
    """Plot all development events instead of hiding them in composites."""
    ordered = audit.sort_values("event_year").reset_index(drop=True)
    y = np.arange(len(ordered), dtype=float)
    specs = (
        ("central_storage_change_zj", "Central-box\nstorage change"),
        ("central_eastward_output_zj", "Central east-face\noutput"),
        ("east_storage_change_zj", "Eastern-box\nstorage change"),
        ("east_west_boundary_input_zj", "Eastern west-face\ninput"),
    )
    fig, axes = plt.subplots(
        1,
        4,
        figsize=(12.4, 7.2),
        sharey=True,
        constrained_layout=True,
    )
    for ax, (metric, title) in zip(axes, specs, strict=True):
        ax.axvline(0, color="0.55", lw=0.8, zorder=0)
        for group, marker, size in (
            ("CP", "o", 42),
            ("EP", "s", 48),
            ("2023", "*", 165),
        ):
            mask = ordered.group.eq(group)
            ax.scatter(
                ordered.loc[mask, metric],
                y[mask],
                color=COLORS[group],
                marker=marker,
                s=size,
                edgecolor="white",
                linewidth=0.7,
                zorder=3,
                label=("2023/24" if group == "2023" else group),
            )
        ax.set_title(title)
        ax.set_xlabel("MJJ (ZJ)")
        ax.grid(axis="y", color="0.92", lw=0.6)
        ax.tick_params(axis="y", length=0)
    labels = [
        f"{row.event_year}  {row.group if row.group != '2023' else 'FEP-EP'}"
        for row in ordered.itertuples(index=False)
    ]
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    axes[0].invert_yaxis()
    axes[0].legend(frameon=False, loc="lower left")
    fig.suptitle(
        "Event-by-event MJJ two-box upper-ocean heat routing",
        fontsize=13.5,
        fontweight="bold",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(AUDIT_FIGURE_PNG, dpi=300, bbox_inches="tight")
    fig.savefig(AUDIT_FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def jittered_positions(n: int, center: float, width: float = 0.12) -> np.ndarray:
    if n == 1:
        return np.asarray([center])
    return center + np.linspace(-width, width, n)


def summary_lookup(
    summary: pd.DataFrame, phase: str, box: str, metric: str, group: str
) -> pd.Series:
    return summary.loc[
        summary.phase.eq(phase)
        & summary.box.eq(box)
        & summary.metric.eq(metric)
        & summary.group.eq(group)
    ].iloc[0]


def make_figure(
    events: pd.DataFrame, summary: pd.DataFrame, state: pd.DataFrame
) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.2,
            "axes.titlesize": 11,
            "axes.labelsize": 9.5,
            "legend.fontsize": 8.5,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.8), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.flat

    # (a) Event-level two-box storage routing during MJJ.
    mjj = events.loc[events.phase.eq(PRIMARY_PHASE)]
    central = mjj.loc[mjj.box.eq("central")].set_index("event_year")
    east = mjj.loc[mjj.box.eq("east")].set_index("event_year")
    for group, marker, size in (("CP", "o", 42), ("EP", "s", 50), ("2023", "*", 180)):
        years = central.loc[central.group.eq(group)].index
        ax_a.scatter(
            central.loc[years, "storage_change_zj"],
            east.loc[years, "storage_change_zj"],
            s=size,
            marker=marker,
            color=COLORS[group],
            edgecolor="white",
            linewidth=0.8,
            zorder=4,
            label=("2023/24" if group == "2023" else f"Historical {group}"),
        )
        for year in years:
            if year in {1982, 1997, 2015, 2019, 2023}:
                offset = (4, -12) if year == 1997 else (4, 4)
                ax_a.annotate(
                    str(year),
                    (
                        central.loc[year, "storage_change_zj"],
                        east.loc[year, "storage_change_zj"],
                    ),
                    xytext=offset,
                    textcoords="offset points",
                    fontsize=7.5,
                )
    ax_a.axhline(0, color="0.55", lw=0.8)
    ax_a.axvline(0, color="0.55", lw=0.8)
    ax_a.set_xlabel("Central-box OHC' change (ZJ)")
    ax_a.set_ylabel("Eastern-box OHC' change (ZJ)")
    ax_a.set_title("(a) MJJ routing: central discharge vs eastern gain", loc="left")
    ax_a.legend(frameon=False, loc="upper right")

    # (b) Event dots and group means for the four central routing diagnostics.
    metric_specs = (
        ("central", "storage_change_zj", "Central\nstorage"),
        ("east", "storage_change_zj", "Eastern\nstorage"),
        ("central", "central_eastward_output_zj", "Central east-face\noutput"),
        ("east", "west_heat_in_zj", "Eastern west-face\ninput"),
    )
    offsets = {"CP": -0.18, "EP": 0.0, "2023": 0.18}
    for i, (box, metric, _) in enumerate(metric_specs):
        selected = mjj.loc[mjj.box.eq(box) & mjj[metric].notna()]
        for group in ("CP", "EP"):
            values = selected.loc[selected.group.eq(group), metric].to_numpy(float)
            xs = jittered_positions(len(values), i + offsets[group], width=0.055)
            ax_b.scatter(
                xs,
                values,
                s=24,
                color=COLORS[group],
                alpha=0.6,
                edgecolor="none",
                zorder=2,
            )
            stats = summary_lookup(summary, PRIMARY_PHASE, box, metric, group)
            ax_b.errorbar(
                i + offsets[group],
                stats["mean"],
                yerr=np.asarray(
                    [
                        [stats["mean"] - stats["ci95_low"]],
                        [stats["ci95_high"] - stats["mean"]],
                    ]
                ),
                fmt="o",
                ms=5.5,
                color=COLORS[group],
                capsize=2.5,
                lw=1.2,
                zorder=3,
            )
        target_value = float(
            selected.loc[selected.group.eq("2023"), metric].iloc[0]
        )
        ax_b.scatter(
            i + offsets["2023"],
            target_value,
            s=115,
            marker="*",
            color=COLORS["2023"],
            edgecolor="white",
            linewidth=0.7,
            zorder=5,
        )
    ax_b.axhline(0, color="0.55", lw=0.8)
    ax_b.set_xticks(range(len(metric_specs)))
    ax_b.set_xticklabels([spec[2] for spec in metric_specs])
    ax_b.set_ylabel("MJJ integrated heat / storage change (ZJ)")
    ax_b.set_title("(b) EP sends more heat across 140°W than CP", loc="left")
    ax_b.text(
        0.02,
        0.98,
        "Dots: events; large circles: mean ± event bootstrap 95% CI",
        transform=ax_b.transAxes,
        ha="left",
        va="top",
        color="0.35",
        fontsize=7.8,
    )

    # (c) Surface and subsurface development state for comparable strong cases.
    cases = state.loc[state.event_year.isin([1997, 2015, 2023])].copy()
    cases = cases.set_index("event_year").loc[[1997, 2015, 2023]].reset_index()
    x = np.arange(len(cases), dtype=float)
    width = 0.26
    ax_c.bar(
        x - width / 2,
        cases.fep_ssta_c,
        width,
        color="#C44E52",
        label="FEP SSTA",
    )
    ax_c.bar(
        x + width / 2,
        cases.nino4_ssta_c,
        width,
        color="#4C72B0",
        label="Niño-4 SSTA",
    )
    ax_c.set_ylabel("May–Jun SSTA (°C)")
    ax_c.set_xticks(x)
    ax_c.set_xticklabels(["1997/98", "2015/16", "2023/24"])
    ax_c.set_title("(c) 2023: FEP-hot but central-Pacific-cool", loc="left")
    ax_c2 = ax_c.twinx()
    ax_c2.spines["top"].set_visible(False)
    ax_c2.plot(
        x,
        cases.central_ohc300_anom_gjm2,
        color="0.15",
        marker="D",
        ms=5.5,
        lw=1.5,
        label="Central 0–300 m OHC'",
    )
    ax_c2.set_ylabel("Central-box OHC' (GJ m$^{-2}$)")
    handles1, labels1 = ax_c.get_legend_handles_labels()
    handles2, labels2 = ax_c2.get_legend_handles_labels()
    ax_c.legend(handles1 + handles2, labels1 + labels2, frameon=False, loc="upper center")

    # (d) Eastern-box loss pathways during the following Jan--May.
    decay = events.loc[
        events.phase.eq("decay_Jan_May_next") & events.box.eq("east")
    ]
    loss_specs = (
        ("east_westward_return_zj", "Westward\nreturn"),
        ("northward_output_zj", "Northward\nexport"),
        ("southward_output_zj", "Southward\nexport"),
        ("surface_loss_zj", "Surface\nloss"),
        ("storage_change_zj", "OHC loss\n(-ΔOHC')"),
    )
    for i, (metric, _) in enumerate(loss_specs):
        for group in ("CP", "EP"):
            values = decay.loc[decay.group.eq(group), metric].to_numpy(float)
            if metric == "storage_change_zj":
                values = -values
            stats_values = values
            low, high = bootstrap_mean_ci(
                stats_values, np.random.default_rng(RANDOM_SEED + i + (group == "EP"))
            )
            mean = float(stats_values.mean())
            ax_d.errorbar(
                i + offsets[group],
                mean,
                yerr=np.asarray([[mean - low], [high - mean]]),
                fmt="o",
                ms=5.5,
                color=COLORS[group],
                capsize=2.5,
                lw=1.2,
                zorder=3,
            )
        target = float(decay.loc[decay.group.eq("2023"), metric].iloc[0])
        if metric == "storage_change_zj":
            target = -target
        ax_d.scatter(
            i + offsets["2023"],
            target,
            s=115,
            marker="*",
            color=COLORS["2023"],
            edgecolor="white",
            linewidth=0.7,
            zorder=5,
        )
    ax_d.axhline(0, color="0.55", lw=0.8)
    ax_d.set_xticks(range(len(loss_specs)))
    ax_d.set_xticklabels([spec[1] for spec in loss_specs])
    ax_d.set_ylabel("Jan–May(+1) heat loss (ZJ)")
    ax_d.set_title("(d) 2023 eastern-box decay is dominated by westward return", loc="left")
    ax_d.text(
        0.02,
        0.98,
        "Residual is not assigned to a physical pathway",
        transform=ax_d.transAxes,
        ha="left",
        va="top",
        color="0.35",
        fontsize=7.8,
    )

    fig.suptitle(
        "Mature EP/CP type × two-box upper-ocean heat routing and fate",
        fontsize=13.5,
        fontweight="bold",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, dpi=300, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def get_event_row(
    events: pd.DataFrame, year: int, phase: str, box: str
) -> pd.Series:
    return events.loc[
        events.event_year.eq(year)
        & events.phase.eq(phase)
        & events.box.eq(box)
    ].iloc[0]


def get_group_mean(
    summary: pd.DataFrame, phase: str, box: str, metric: str, group: str
) -> float:
    return float(summary_lookup(summary, phase, box, metric, group)["mean"])


def write_report(
    manifest: pd.DataFrame,
    events: pd.DataFrame,
    summary: pd.DataFrame,
    differences: pd.DataFrame,
    state: pd.DataFrame,
    sensitivity: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    c23 = get_event_row(events, 2023, PRIMARY_PHASE, "central")
    e23 = get_event_row(events, 2023, PRIMARY_PHASE, "east")
    g23c = get_event_row(events, 2023, "growth_Jul_Dec", "central")
    g23e = get_event_row(events, 2023, "growth_Jul_Dec", "east")
    d23e = get_event_row(events, 2023, "decay_Jan_May_next", "east")

    def diff_p(box: str, metric: str) -> float:
        return float(
            differences.loc[
                differences.phase.eq(PRIMARY_PHASE)
                & differences.box.eq(box)
                & differences.metric.eq(metric),
                "exact_two_sided_p",
            ].iloc[0]
        )

    state_idx = state.set_index("event_year")
    analogues = (
        audit.loc[audit.event_year.ne(TARGET_EVENT)]
        .nsmallest(6, "routing_distance_to_2023")
        .set_index("event_year")
    )
    lines = [
        "# Jiang 框架下 EP/CP 两箱热量命运：当前结果",
        "",
        "## 一句话结论",
        "",
        "2023 年 MJJ 的中太平洋偏冷并不表示暖量消失，而主要对应 **中箱减储、跨 140°W 向东输出、东箱增储**；这一发展期路由与历史 EP 共性一致、与 CP 明显不同。2023 的特殊性更多出现在后续分配和衰减：夏秋东箱继续增储弱于历史 EP，次年东箱损失又主要通过向西返回，而不是海表散热或向北输出。",
        "",
        "## 分类层次",
        "",
        "- 成熟期类型：EP / CP。",
        "- 发展期路径：Jiang 的 FEP 主导 / 非 FEP 主导。两者不能互换；2023 是 EP 成熟型，同时是后 1980 年唯一的严格 FEP 主导事件。",
        "- 本地 Jiang 正文明确给出 5 个 FEP 主导事件及其成熟类型，并说明非 FEP 中 12/16 为 CP；逐事件非 FEP 标签位于缺失的 Supporting Figure S6。事件表因此把正文明确标签与工作重建标签分栏记录。",
        "- 2023 不进入历史 EP 复合；历史参照为 EP n=4、CP n=9。1986/87 与 1987/88 连续，另做删除 1987 的敏感性检验。",
        "",
        "## 两箱与预算",
        "",
        "- 中箱：10°S–5°N，180°–140°W，0–300 m。",
        "- 东箱：10°S–5°N，140°W–80°W，0–300 m。",
        "- 状态量为完整固定层 OHC′；输送为各箱体积闭合后的四边异常焓输送；海表量为完整净海表热通量。",
        "- 残差包含垂向、混合、扩散、同化增量及离散误差，不能命名为某一种热量损失过程。",
        "",
        "## 发展期 MJJ：EP/CP 的统一与分歧",
        "",
        f"- 历史 EP：中箱 OHC′ 平均变化 {get_group_mean(summary, PRIMARY_PHASE, 'central', 'storage_change_zj', 'EP'):+.2f} ZJ，东箱 {get_group_mean(summary, PRIMARY_PHASE, 'east', 'storage_change_zj', 'EP'):+.2f} ZJ；中箱东边界输出 {get_group_mean(summary, PRIMARY_PHASE, 'central', 'central_eastward_output_zj', 'EP'):+.2f} ZJ，东箱西边界输入 {get_group_mean(summary, PRIMARY_PHASE, 'east', 'west_heat_in_zj', 'EP'):+.2f} ZJ。",
        f"- CP：中箱 OHC′ 平均变化 {get_group_mean(summary, PRIMARY_PHASE, 'central', 'storage_change_zj', 'CP'):+.2f} ZJ，东箱 {get_group_mean(summary, PRIMARY_PHASE, 'east', 'storage_change_zj', 'CP'):+.2f} ZJ；中箱东边界输出 {get_group_mean(summary, PRIMARY_PHASE, 'central', 'central_eastward_output_zj', 'CP'):+.2f} ZJ，东箱西边界输入 {get_group_mean(summary, PRIMARY_PHASE, 'east', 'west_heat_in_zj', 'CP'):+.2f} ZJ。",
        f"- EP−CP 的事件级精确置换检验：中箱储存变化 p={diff_p('central', 'storage_change_zj'):.3f}，中箱东向输出 p={diff_p('central', 'central_eastward_output_zj'):.3f}，东箱西边界输入 p={diff_p('east', 'west_heat_in_zj'):.3f}；东箱储存变化本身 p={diff_p('east', 'storage_change_zj'):.3f}，说明路由差异比最终储存差异更稳定。",
        "- 共性：两类事件都可能把热量送入东箱，且个例离散度很大。分歧：EP 的典型结构是中箱减储并加强跨 140°W 东传；CP 更倾向于中箱本地保留，向东输送较弱。",
        "",
        "## 其他年份的发展期逐事件检查",
        "",
        "- 按中箱储存、中箱东向输出、东箱储存、东箱西边界输入四项标准化距离，最接近 2023 路由的历史事件依次为 "
        + "、".join(
            f"{year}（{analogues.loc[year, 'group']}，距离 {analogues.loc[year, 'routing_distance_to_2023']:.2f}）"
            for year in analogues.index[:4]
        )
        + "。这个距离只描述热量路由相似度，不代表完整动力机制相同。",
        f"- 2015 最接近：中箱变化 {analogues.loc[2015, 'central_storage_change_zj']:+.2f} ZJ、东向输出 {analogues.loc[2015, 'central_eastward_output_zj']:+.2f} ZJ、东箱增储 {analogues.loc[2015, 'east_storage_change_zj']:+.2f} ZJ。它与 2023 方向一致，但中箱减储和东箱增储都更弱。",
        f"- 1997 同样是“中箱减储—东箱增储”，但幅度远强：{analogues.loc[1997, 'central_storage_change_zj']:+.2f}/{analogues.loc[1997, 'east_storage_change_zj']:+.2f} ZJ，因此不是数值上最近的事件。",
        f"- 2009 虽是 CP，仍出现较强东向路由：中箱东向输出 {analogues.loc[2009, 'central_eastward_output_zj']:+.2f} ZJ、东箱增储 {analogues.loc[2009, 'east_storage_change_zj']:+.2f} ZJ。这说明 EP/CP 是概率性分组，不是每个预算项的硬阈值。",
        "- 2019 是最明显的反例：东箱减储且西边界为净输出；1987 则有中箱减储—东箱增储，但跨 140°W 输送远弱于 2023。逐事件图因此必须和复合图同时保留。",
        "",
        "## 2023：中部偏冷对应什么热量命运？",
        "",
        f"- MJJ 中箱 OHC′ 变化 {c23.storage_change_zj:+.2f} ZJ，东边界向东输出 {c23.central_eastward_output_zj:+.2f} ZJ；东箱 OHC′ 增加 {e23.storage_change_zj:+.2f} ZJ，并从西边界获得 {e23.west_heat_in_zj:+.2f} ZJ。",
        f"- May–Jun 平均 FEP SSTA 为 {state_idx.loc[2023, 'fep_ssta_c']:+.2f}°C，但 Niño-4 只有 {state_idx.loc[2023, 'nino4_ssta_c']:+.2f}°C，中箱 0–300 m OHC′ 平均为 {state_idx.loc[2023, 'central_ohc300_anom_gjm2']:+.2f} GJ m⁻²。1997/2015 的对应 Niño-4 为 {state_idx.loc[1997, 'nino4_ssta_c']:+.2f}/{state_idx.loc[2015, 'nino4_ssta_c']:+.2f}°C，中箱 OHC′ 为 {state_idx.loc[1997, 'central_ohc300_anom_gjm2']:+.2f}/{state_idx.loc[2015, 'central_ohc300_anom_gjm2']:+.2f} GJ m⁻²。",
        "- 因而“中部海温偏低”可以改写成更物理的结论：东部表面增暖已经很强，但中部上层海洋没有形成与 1997/2015 同等的热储存支撑；MJJ 的中箱热量还在净向东重分配。",
        "",
        "## 后续去向：2023 哪里不同？",
        "",
        f"- Jul–Dec 2023：中箱 OHC′ 增加 {g23c.storage_change_zj:+.2f} ZJ，东箱增加 {g23e.storage_change_zj:+.2f} ZJ；两箱合计 {g23c.storage_change_zj + g23e.storage_change_zj:+.2f} ZJ。历史 EP 两箱合计为 {get_group_mean(summary, 'growth_Jul_Dec', 'central', 'storage_change_zj', 'EP') + get_group_mean(summary, 'growth_Jul_Dec', 'east', 'storage_change_zj', 'EP'):+.2f} ZJ。总量相近，但 2023 更偏中箱回补、东箱增储较弱。",
        f"- 次年 Jan–May，2023 东箱 OHC′ 减少 {-d23e.storage_change_zj:.2f} ZJ；向西返回 {d23e.east_westward_return_zj:.2f} ZJ、向北输出 {d23e.northward_output_zj:.2f} ZJ、海表损失 {d23e.surface_loss_zj:.2f} ZJ，未解析储存贡献 {d23e.unresolved_storage_contribution_zj:+.2f} ZJ。",
        "- 这说明 2023 的衰减不能写成“主要向北丢失”或“主要向大气散热”；在已解析项中，向西返回最大。",
        "",
        "## 对 PPT 篇幅的建议",
        "",
        "主线压缩成 3 张结果图即可：",
        "",
        "1. 分类图：成熟 EP/CP × 发展期 FEP 主导/非主导，突出 2023。",
        "2. 本图：MJJ 中—东两箱路由，回答 EP/CP 共性与分歧。",
        "3. 2023 过程图：MJJ 中箱减储→东箱增储，随后 Jul–Dec 重分配与次年向西返回。",
        "",
        "原 OHC Hovmöller 留作背景证据，不再承担逐项热量命运解释；拉格朗日轨迹可降为补充验证路径连续性，而不是当前主结果。",
        "",
        "## 解释边界",
        "",
        "- 中箱东边界输出与东箱西边界输入分别来自两个独立体积闭合箱，数值不要求逐项相等；它们一致指示方向，但不能相减当作新物理源汇。",
        "- EP/CP 样本较小，置信区间使用事件 bootstrap，显著性使用事件标签精确置换；月份没有被当作独立样本。",
        "- 结果是欧拉箱体收支，回答热量在哪个箱、经哪条边界进出；不能直接证明同一水团身份。",
        "- 非 FEP 逐事件标签仍需 Jiang Supporting Figure S6 最终核对；当前 CSV 已保留这一来源状态。",
        "",
        "## 产出",
        "",
        f"- 主图：`{FIGURE_PNG.relative_to(ROOT)}` / `{FIGURE_PDF.relative_to(ROOT)}`",
        f"- 逐事件发展期图：`{AUDIT_FIGURE_PNG.relative_to(ROOT)}` / `{AUDIT_FIGURE_PDF.relative_to(ROOT)}`",
        f"- 逐事件发展期表：`{AUDIT_FILE.relative_to(ROOT)}`",
        f"- 事件分类：`{MANIFEST_FILE.relative_to(ROOT)}`",
        f"- 事件预算：`{EVENT_FILE.relative_to(ROOT)}`",
        f"- 组别统计：`{SUMMARY_FILE.relative_to(ROOT)}`",
        f"- EP−CP 差异：`{DIFFERENCE_FILE.relative_to(ROOT)}`",
        f"- 1987 敏感性：`{SENSITIVITY_FILE.relative_to(ROOT)}`",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def build_diagnostics(
    budget: pd.DataFrame,
    manifest: pd.DataFrame,
    events: pd.DataFrame,
    differences: pd.DataFrame,
    sensitivity: pd.DataFrame,
    audit: pd.DataFrame,
) -> dict[str, object]:
    primary = events.loc[events.phase.eq(PRIMARY_PHASE)]
    central = primary.loc[primary.box.eq("central")].set_index("event_year")
    east = primary.loc[primary.box.eq("east")].set_index("event_year")
    shared_direction_agreement = np.sign(
        central.loc[[*HISTORICAL_EP, *HISTORICAL_CP, TARGET_EVENT], "central_eastward_output_zj"]
    ) == np.sign(
        east.loc[[*HISTORICAL_EP, *HISTORICAL_CP, TARGET_EVENT], "west_heat_in_zj"]
    )
    return {
        "budget_time_start": str(budget.time.min().date()),
        "budget_time_end": str(budget.time.max().date()),
        "budget_anomaly_baseline": "1980-2022 same-calendar-month linear expectation (upstream product)",
        "central_box": "10S-5N, 180E-220E, 0-300 m",
        "east_box": "10S-5N, 220E-280E, 0-300 m",
        "historical_ep_events": list(HISTORICAL_EP),
        "historical_cp_events": list(HISTORICAL_CP),
        "target_event": TARGET_EVENT,
        "primary_phase": PRIMARY_PHASE,
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "random_seed": RANDOM_SEED,
        "manifest_counts": manifest.groupby(
            ["fep_dominant", "mature_type_working"], dropna=False
        ).size().rename("n").reset_index().to_dict("records"),
        "shared_face_direction_agreement_fraction": float(
            shared_direction_agreement.mean()
        ),
        "classification_limit": (
            "Non-FEP individual labels are a Jiang-consistent working reconstruction; "
            "local Supporting Figure S6 is unavailable"
        ),
        "statistics": (
            "Event bootstrap confidence intervals and exact event-label permutation tests"
        ),
        "primary_difference_records": differences.loc[
            differences.phase.eq(PRIMARY_PHASE)
            & differences.metric.isin(
                [
                    "storage_change_zj",
                    "central_eastward_output_zj",
                    "west_heat_in_zj",
                ]
            )
        ].to_dict("records"),
        "sensitivity_records": sensitivity.to_dict("records"),
        "nearest_historical_mjj_routing_analogues": audit.loc[
            audit.event_year.ne(TARGET_EVENT)
        ].nsmallest(6, "routing_distance_to_2023")[
            ["event_year", "group", "routing_distance_to_2023"]
        ].to_dict("records"),
    }


def main() -> int:
    manifest = build_manifest()
    budget = load_budget()
    events = build_event_budgets(budget)
    summary, differences = build_group_statistics(events)
    sensitivity = build_sensitivity(events)
    state = build_may_jun_state()
    audit = build_event_audit(events)

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(MANIFEST_FILE, index=False)
    events.to_csv(EVENT_FILE, index=False, float_format="%.10g")
    summary.to_csv(SUMMARY_FILE, index=False, float_format="%.10g")
    differences.to_csv(DIFFERENCE_FILE, index=False, float_format="%.10g")
    state.to_csv(STATE_FILE, index=False, float_format="%.10g")
    sensitivity.to_csv(SENSITIVITY_FILE, index=False, float_format="%.10g")
    audit.to_csv(AUDIT_FILE, index=False, float_format="%.10g")

    make_figure(events, summary, state)
    make_event_audit_figure(audit)
    write_report(
        manifest, events, summary, differences, state, sensitivity, audit
    )
    diagnostics = build_diagnostics(
        budget, manifest, events, differences, sensitivity, audit
    )
    DIAGNOSTICS_FILE.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Wrote {MANIFEST_FILE}")
    print(f"Wrote {EVENT_FILE}")
    print(f"Wrote {FIGURE_PNG}")
    print(f"Wrote {AUDIT_FIGURE_PNG}")
    print(f"Wrote {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
