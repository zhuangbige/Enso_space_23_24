#!/usr/bin/env python3
"""Build data-verified scientific figures for the simplified ENSO PPT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "research_2026"
HIGHLIGHT_EVENTS = (1997, 2015, 2023)

HOVMOLLER_CSV = DATA / "soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv"
TRAJECTORY_CSV = DATA / "soda3_temp_anomaly_lagrangian_pilot_summary.csv"
BUDGET_CSV = DATA / "soda3_three_box_ohc_anomaly_budget_events.csv"
EARLY_EVENT_CSV = DATA / "nonh20_early_north_to_jiang_event_table.csv"
EARLY_RELATION_CSV = DATA / "nonh20_early_north_to_jiang_relationships.csv"
Q3_EVENT_CSV = DATA / "nonh20_third_question_event_table.csv"
Q3_RELATION_CSV = DATA / "nonh20_third_question_relationships.csv"

COLORS = {
    1997: "#E87500",
    2015: "#2E86C1",
    2023: "#148F88",
    "other": "#93A4AF",
    "ink": "#0A2234",
    "grid": "#D9E2E8",
    "red": "#C53D3D",
    "purple": "#7C58A5",
}


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def _clean_axis(axis: plt.Axes) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(True, color=COLORS["grid"], linewidth=0.7, alpha=0.9)
    axis.set_axisbelow(True)


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _float(value: object) -> float:
    return float(np.asarray(value).item())


def residualize(values: np.ndarray, control: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    control = np.asarray(control, dtype=float)
    design = np.column_stack([np.ones(control.size), control])
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    return values - design @ coefficients


def _event_color(year: int) -> str:
    return COLORS.get(year, COLORS["other"])


def _load_audit() -> tuple[dict, dict[str, pd.DataFrame]]:
    trajectory = pd.read_csv(TRAJECTORY_CSV)
    trajectory = trajectory.loc[trajectory["variant"].eq("w_upward_positive")].copy()

    budget = pd.read_csv(BUDGET_CSV)
    arrival = budget.loc[
        budget["phase"].eq("arrival_Jan_Jun")
        & budget["box"].eq("east")
        & budget["event_year"].isin(HIGHLIGHT_EVENTS)
    ].set_index("event_year")
    decay = budget.loc[
        budget["phase"].eq("decay_Jan_May_next")
        & budget["box"].eq("east")
        & budget["event_year"].isin(HIGHLIGHT_EVENTS)
    ].set_index("event_year")

    early_events = pd.read_csv(EARLY_EVENT_CSV).sort_values("year")
    early_relations = pd.read_csv(EARLY_RELATION_CSV).set_index("test_id")
    q3_events = pd.read_csv(Q3_EVENT_CSV).sort_values("event_year")
    q3_relations = pd.read_csv(Q3_RELATION_CSV).set_index("test_id")

    trajectory_audit: dict[str, dict[str, float]] = {}
    for year in HIGHLIGHT_EVENTS:
        row = trajectory.loc[trajectory["event"].eq(year)].iloc[0]
        trajectory_audit[str(year)] = {
            "median_eastward_deg": _float(row["weighted_median_eastward_displacement_deg"]),
            "active_weight_fraction": _float(row["active_fraction_weight"]),
        }

    arrival_audit: dict[str, dict[str, float]] = {}
    partition_audit: dict[str, dict[str, float]] = {}
    for year in HIGHLIGHT_EVENTS:
        arrival_row = arrival.loc[year]
        decay_row = decay.loc[year]
        arrival_audit[str(year)] = {
            "inflow_zj": _float(arrival_row["west_theta_heat_in_zj"]),
            "ohc_gain_zj": _float(arrival_row["storage_change_zj"]),
        }
        partition_audit[str(year)] = {
            "storage_loss_zj": -_float(decay_row["storage_change_zj"]),
            "westward_return_zj": -_float(decay_row["west_theta_heat_in_zj"]),
            "northward_output_zj": _float(decay_row["northward_output_zj"]),
            "southward_output_zj": _float(decay_row["southward_output_zj"]),
            "eastward_export_zj": -_float(decay_row["east_theta_heat_in_zj"]),
            "surface_loss_zj": _float(decay_row["surface_loss_zj"]),
            "residual_zj": _float(decay_row["residual_zj"]),
        }

    q3_specs = {
        "early_north_to_ne925": {
            "events": early_events,
            "x": "north_output_jfm_zj",
            "y": "ne925_mjj_ms",
            "control": "arrival_140w_jfm_zj",
            "relation": early_relations.loc["jfm_north_to_ne925"],
            "x_unit": "ZJ",
            "y_unit": "m s-1",
        },
        "stress_to_north": {
            "events": q3_events,
            "x": "decay_tau5n_westward_nm2",
            "y": "decay_northward_output_zj",
            "control": "arrival_140w_heat_in_zj",
            "relation": q3_relations.loc["decay_tau_to_north_given_arrival"],
            "x_unit": "N m-2",
            "y_unit": "ZJ",
        },
        "sst_to_surface": {
            "events": q3_events,
            "x": "decay_east_sst_anom_c",
            "y": "decay_surface_loss_zj",
            "control": "arrival_140w_heat_in_zj",
            "relation": q3_relations.loc["decay_sst_to_surface_given_arrival"],
            "x_unit": "degC",
            "y_unit": "ZJ",
        },
    }

    q3_audit: dict[str, dict[str, object]] = {}
    q3_plot_data: dict[str, pd.DataFrame] = {}
    for key, spec in q3_specs.items():
        events = spec["events"].copy()
        x_residual = residualize(events[spec["x"]].to_numpy(), events[spec["control"]].to_numpy())
        y_residual = residualize(events[spec["y"]].to_numpy(), events[spec["control"]].to_numpy())
        correlation = _float(np.corrcoef(x_residual, y_residual)[0, 1])
        reported = _float(spec["relation"]["partial_r"])
        if not np.isclose(correlation, reported, atol=1e-9):
            raise AssertionError(f"{key}: recalculated r={correlation}, reported r={reported}")
        plot_frame = pd.DataFrame(
            {
                "event_year": events["year"] if "year" in events.columns else events["event_year"],
                "x_residual": x_residual,
                "y_residual": y_residual,
            }
        )
        q3_plot_data[key] = plot_frame
        q3_audit[key] = {
            "partial_r": reported,
            "permutation_p": _float(spec["relation"]["permutation_p"]),
            "x_unit": spec["x_unit"],
            "y_unit": spec["y_unit"],
        }

    residual_fractions = {
        str(year): abs(partition_audit[str(year)]["residual_zj"])
        / partition_audit[str(year)]["storage_loss_zj"]
        for year in HIGHLIGHT_EVENTS
    }

    audit = {
        "arrival": arrival_audit,
        "trajectory": trajectory_audit,
        "partition": partition_audit,
        "q3": q3_audit,
        "residual_summary": {"fraction_of_loss": residual_fractions},
        "source_files": [
            str(HOVMOLLER_CSV),
            str(TRAJECTORY_CSV),
            str(BUDGET_CSV),
            str(EARLY_EVENT_CSV),
            str(EARLY_RELATION_CSV),
            str(Q3_EVENT_CSV),
            str(Q3_RELATION_CSV),
        ],
    }
    frames = {
        "trajectory": trajectory,
        "arrival": arrival.reset_index(),
        "decay": decay.reset_index(),
        **{f"q3_{key}": frame for key, frame in q3_plot_data.items()},
    }
    return audit, frames


def _plot_hovmoller(output: Path) -> None:
    frame = pd.read_csv(HOVMOLLER_CSV)
    maximum = np.nanpercentile(np.abs(frame["ohc300_anom_gjm2"].to_numpy()), 98.5)
    limit = max(1.0, float(np.ceil(maximum * 2.0) / 2.0))
    levels = np.linspace(-limit, limit, 21)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.4), sharex=True, sharey=True)
    image = None
    for index, (axis, year) in enumerate(zip(axes, HIGHLIGHT_EVENTS)):
        event = frame.loc[frame["event_year"].eq(year)]
        grid = event.pivot(index="relative_month", columns="lon_deg_e", values="ohc300_anom_gjm2").sort_index()
        image = axis.contourf(
            grid.columns.to_numpy(),
            grid.index.to_numpy(),
            grid.to_numpy(),
            levels=levels,
            cmap="RdBu_r",
            norm=norm,
            extend="both",
        )
        axis.contour(
            grid.columns.to_numpy(),
            grid.index.to_numpy(),
            grid.to_numpy(),
            levels=[0.0],
            colors=COLORS["ink"],
            linewidths=0.7,
        )
        axis.axvline(220.0, color=COLORS["ink"], linestyle="--", linewidth=1.0)
        axis.set_xlim(130, 280)
        axis.set_ylim(-6, 10)
        axis.set_xticks([140, 180, 220, 260, 280])
        axis.set_xticklabels(["140°E", "180°", "140°W", "100°W", "80°W"])
        axis.set_yticks([-6, -3, 0, 3, 6, 9])
        axis.set_yticklabels(["Jul−1", "Oct−1", "Jan", "Apr", "Jul", "Oct"])
        axis.text(0.03, 0.96, f"({chr(97 + index)})  {year}", transform=axis.transAxes, va="top", ha="left", fontweight="bold")
        axis.set_xlabel("Longitude")
        axis.grid(False)
    axes[0].set_ylabel("Relative month")
    assert image is not None
    colorbar = fig.colorbar(image, ax=axes, orientation="horizontal", fraction=0.08, pad=0.19, aspect=42)
    colorbar.set_label("0–300 m OHC anomaly (GJ m$^{-2}$)")
    fig.subplots_adjust(left=0.075, right=0.99, top=0.96, bottom=0.27, wspace=0.09)
    _save(fig, output)


def _plot_trajectory(frame: pd.DataFrame, output: Path) -> None:
    selected = frame.loc[frame["event"].isin(HIGHLIGHT_EVENTS)].set_index("event").loc[list(HIGHLIGHT_EVENTS)]
    colors = [_event_color(year) for year in HIGHLIGHT_EVENTS]
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.5))

    values = selected["weighted_median_eastward_displacement_deg"].to_numpy()
    axes[0].bar([str(year) for year in HIGHLIGHT_EVENTS], values, color=colors, width=0.62)
    axes[0].set_ylabel("Weighted median eastward displacement (°)")
    axes[0].set_ylim(0, 34)
    for position, value in enumerate(values):
        axes[0].text(position, value + 0.8, f"{value:.1f}°", ha="center", va="bottom", fontweight="bold")
    axes[0].text(0.02, 0.97, "(a)", transform=axes[0].transAxes, va="top", fontweight="bold")
    _clean_axis(axes[0])

    fractions = 100.0 * selected["active_fraction_weight"].to_numpy()
    axes[1].bar([str(year) for year in HIGHLIGHT_EVENTS], fractions, color=colors, width=0.62)
    axes[1].set_ylabel("Active trajectory weight (%)")
    axes[1].set_ylim(0, 84)
    for position, value in enumerate(fractions):
        axes[1].text(position, value + 1.6, f"{value:.0f}%", ha="center", va="bottom", fontweight="bold")
    axes[1].text(0.02, 0.97, "(b)", transform=axes[1].transAxes, va="top", fontweight="bold")
    _clean_axis(axes[1])
    fig.subplots_adjust(left=0.10, right=0.99, top=0.96, bottom=0.14, wspace=0.30)
    _save(fig, output)


def _plot_arrival(frame: pd.DataFrame, output: Path) -> None:
    selected = frame.set_index("event_year").loc[list(HIGHLIGHT_EVENTS)]
    positions = np.arange(len(HIGHLIGHT_EVENTS), dtype=float)
    width = 0.34
    inflow = selected["west_theta_heat_in_zj"].to_numpy()
    storage = selected["storage_change_zj"].to_numpy()
    fig, axis = plt.subplots(figsize=(9.6, 4.8))
    axis.bar(positions - width / 2, inflow, width, color=COLORS[1997], label="140°W inflow")
    axis.bar(positions + width / 2, storage, width, color=COLORS[2015], label="Eastern-box OHC gain")
    for x, value in zip(positions - width / 2, inflow):
        axis.text(x, value + 0.45, f"{value:.2f}", ha="center", va="bottom", fontweight="bold")
    for x, value in zip(positions + width / 2, storage):
        axis.text(x, value + 0.45, f"{value:.2f}", ha="center", va="bottom", fontweight="bold")
    axis.set_xticks(positions, [str(year) for year in HIGHLIGHT_EVENTS])
    axis.set_ylabel("Jan–Jun cumulative energy (ZJ)")
    axis.set_ylim(0, 20)
    axis.legend(frameon=False, ncol=2, loc="upper right")
    _clean_axis(axis)
    fig.subplots_adjust(left=0.11, right=0.99, top=0.96, bottom=0.14)
    _save(fig, output)


def _plot_partition(frame: pd.DataFrame, output: Path) -> None:
    selected = frame.set_index("event_year").loc[list(HIGHLIGHT_EVENTS)]
    categories = [
        ("Eastern-box OHC loss", lambda row: -row["storage_change_zj"], COLORS["ink"]),
        ("Westward return", lambda row: -row["west_theta_heat_in_zj"], COLORS[2015]),
        ("Northward export", lambda row: row["northward_output_zj"], COLORS[1997]),
        ("Southward export", lambda row: row["southward_output_zj"], COLORS["purple"]),
        ("Eastward export", lambda row: -row["east_theta_heat_in_zj"], "#D8A13B"),
        ("Surface heat loss", lambda row: row["surface_loss_zj"], COLORS["red"]),
        ("Budget residual", lambda row: row["residual_zj"], COLORS[2023]),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 5.0), sharex=True, sharey=True)
    y = np.arange(len(categories))
    for axis, year in zip(axes, HIGHLIGHT_EVENTS):
        row = selected.loc[year]
        values = np.asarray([function(row) for _, function, _ in categories], dtype=float)
        axis.barh(y, values, color=[color for _, _, color in categories], height=0.66)
        axis.axvline(0.0, color=COLORS["ink"], linewidth=0.9)
        axis.set_title(str(year), fontweight="bold", pad=8)
        axis.set_xlim(-7.5, 23.5)
        for position, value in zip(y, values):
            horizontal = "left" if value >= 0 else "right"
            offset = 0.35 if value >= 0 else -0.35
            axis.text(value + offset, position, f"{value:+.2f}", ha=horizontal, va="center", fontsize=9.5, fontweight="bold")
        _clean_axis(axis)
    axes[0].set_yticks(y, [item[0] for item in categories])
    axes[0].invert_yaxis()
    fig.supxlabel("Following Jan–May cumulative energy (ZJ)", y=0.035)
    fig.subplots_adjust(left=0.20, right=0.995, top=0.93, bottom=0.14, wspace=0.08)
    _save(fig, output)


def _plot_q3(frames: dict[str, pd.DataFrame], audit: dict, output: Path) -> None:
    specs = [
        (
            "early_north_to_ne925",
            "JFM northward export residual (ZJ)",
            "MJJ NE925 residual (m s$^{-1}$)",
        ),
        (
            "stress_to_north",
            "Following 5°N westward-stress residual (N m$^{-2}$)",
            "Following northward-export residual (ZJ)",
        ),
        (
            "sst_to_surface",
            "Eastern SST residual (°C)",
            "Surface heat-loss residual (ZJ)",
        ),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.7))
    for index, (axis, (key, xlabel, ylabel)) in enumerate(zip(axes, specs)):
        frame = frames[f"q3_{key}"]
        for row in frame.itertuples(index=False):
            year = int(row.event_year)
            axis.scatter(
                row.x_residual,
                row.y_residual,
                s=72 if year in HIGHLIGHT_EVENTS else 42,
                color=_event_color(year),
                edgecolor="white",
                linewidth=0.8,
                zorder=3,
            )
        x = frame["x_residual"].to_numpy()
        y = frame["y_residual"].to_numpy()
        slope, intercept = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 100)
        axis.plot(x_line, intercept + slope * x_line, color=COLORS["ink"], linewidth=1.6)
        relation = audit["q3"][key]
        axis.text(
            0.04,
            0.95,
            f"({chr(97 + index)})  r = {relation['partial_r']:.2f}\np = {relation['permutation_p']:.3f}",
            transform=axis.transAxes,
            va="top",
            ha="left",
            fontweight="bold",
        )
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        _clean_axis(axis)

    handles = [
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["other"], markeredgecolor="white", markersize=7, label="Other events"),
        *[
            plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=_event_color(year), markeredgecolor="white", markersize=8, label=str(year))
            for year in HIGHLIGHT_EVENTS
        ],
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False, handletextpad=0.4, columnspacing=1.2)
    fig.subplots_adjust(left=0.075, right=0.995, top=0.86, bottom=0.22, wspace=0.30)
    _save(fig, output)


def build_assets(output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _apply_style()
    audit, frames = _load_audit()
    _plot_hovmoller(output_dir / "fig-q1-hovmoller-en.png")
    _plot_trajectory(frames["trajectory"], output_dir / "fig-q1-trajectory-en.png")
    _plot_arrival(frames["arrival"], output_dir / "fig-q1-arrival-en.png")
    _plot_partition(frames["decay"], output_dir / "fig-q2-partition-en.png")
    _plot_q3(frames, audit, output_dir / "fig-q3-independent-constraints-en.png")
    (output_dir / "data-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    build_assets(arguments.output_dir)


if __name__ == "__main__":
    main()
