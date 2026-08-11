"""Standalone geographic figures for ENSO arrival, routing, and fate."""

from __future__ import annotations

from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LogNorm, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

from .config import BOXES, EVENT_COLORS, EVENTS
from .data import extract_event_budget, load_trajectory_data
from .plotting import (
    DATA_CRS,
    add_panel_label,
    arrow_width_zj,
    draw_box_boundaries,
    format_pacific_axis,
    save_figure_pair,
)


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    finite = np.isfinite(values) & np.isfinite(weights) & (weights >= 0)
    values = values[finite]
    weights = weights[finite]
    if values.size == 0 or weights.sum() <= 0:
        return float("nan")
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    return float(values[np.searchsorted(np.cumsum(weights), 0.5 * weights.sum())])


def _data_transform(ax):
    return DATA_CRS._as_mpl_transform(ax)


def _draw_arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str,
    linewidth: float,
    alpha: float = 0.95,
    zorder: int = 16,
) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        xycoords=_data_transform(ax),
        textcoords=_data_transform(ax),
        arrowprops={
            "arrowstyle": "-|>",
            "color": color,
            "linewidth": linewidth,
            "mutation_scale": 11 + 1.6 * linewidth,
            "alpha": alpha,
            "shrinkA": 0,
            "shrinkB": 0,
        },
        zorder=zorder,
    )


def _fill_box(ax, box: str, value: float, *, cmap, norm, alpha: float = 0.84) -> None:
    west, east, south, north = BOXES[box]
    color = cmap(norm(value))
    ax.add_patch(
        Rectangle(
            (west, south),
            east - west,
            north - south,
            facecolor=color,
            edgecolor="none",
            alpha=alpha,
            transform=DATA_CRS,
            zorder=3,
        )
    )


def _artifact_metadata(png: Path, pdf: Path) -> dict[str, str]:
    return {"png": str(png), "pdf": str(pdf)}


def build_trajectory_connectivity(output_dir: Path) -> dict:
    trajectories, endpoints = load_trajectory_data()
    lon_edges = np.linspace(145.0, 275.0, 131)
    lat_edges = np.linspace(-10.0, 10.0, 61)
    histograms: dict[int, np.ndarray] = {}
    metrics: dict[int, dict[str, float]] = {}
    particle_counts: dict[int, int] = {}

    for event in EVENTS:
        event_endpoints = endpoints.loc[endpoints["event"] == event].copy()
        event_tracks = trajectories.loc[trajectories["event"] == event].merge(
            event_endpoints[["particle_id", "heat_anomaly_weight", "active"]],
            on="particle_id",
            how="left",
            validate="many_to_one",
            suffixes=("", "_endpoint"),
        )
        active_column = "active_endpoint" if "active_endpoint" in event_tracks else "active"
        event_tracks = event_tracks.loc[event_tracks[active_column].astype(bool)]
        weights = event_tracks["heat_anomaly_weight"].to_numpy(dtype=float)
        counts = event_tracks.groupby("particle_id")["particle_id"].transform("size").to_numpy()
        weights = np.divide(weights, counts, out=np.zeros_like(weights), where=counts > 0)
        histogram, _, _ = np.histogram2d(
            event_tracks["lon"],
            event_tracks["lat"],
            bins=(lon_edges, lat_edges),
            weights=weights,
        )
        histogram[histogram <= 0] = np.nan
        histograms[event] = histogram.T
        total_weight = event_endpoints["heat_anomaly_weight"].sum()
        active_weight = event_endpoints.loc[
            event_endpoints["active"].astype(bool), "heat_anomaly_weight"
        ].sum()
        metrics[event] = {
            "median_eastward_deg": _weighted_median(
                event_endpoints["zonal_displacement_deg"].to_numpy(),
                event_endpoints["heat_anomaly_weight"].to_numpy(),
            ),
            "active_weight_fraction": float(active_weight / total_weight),
        }
        particle_counts[event] = int(event_endpoints["particle_id"].nunique())

    positive = np.concatenate(
        [array[np.isfinite(array) & (array > 0)] for array in histograms.values()]
    )
    vmin = max(float(np.nanpercentile(positive, 8)), float(positive.min()))
    vmax = float(np.nanpercentile(positive, 99.5))
    norm = LogNorm(vmin=vmin, vmax=vmax)

    fig = plt.figure(figsize=(12.4, 4.25), constrained_layout=True)
    axes = fig.subplots(
        1,
        3,
        subplot_kw={"projection": ccrs.PlateCarree(central_longitude=180.0)},
    )
    mesh = None
    for index, (axis, event) in enumerate(zip(axes, EVENTS, strict=True)):
        format_pacific_axis(
            axis,
            extent=(145.0, 280.0, -12.0, 12.0),
            label_left=index == 0,
            label_bottom=True,
        )
        mesh = axis.pcolormesh(
            lon_edges,
            lat_edges,
            histograms[event],
            cmap="magma_r",
            norm=norm,
            shading="auto",
            transform=DATA_CRS,
            zorder=2,
        )
        axis.add_patch(
            Rectangle(
                (220.0, -5.0),
                50.0,
                10.0,
                fill=False,
                edgecolor="#132530",
                linewidth=1.25,
                transform=DATA_CRS,
                zorder=12,
            )
        )
        axis.plot(
            [220.0, 220.0],
            [-10.0, 5.0],
            color="#132530",
            linewidth=1.8,
            transform=DATA_CRS,
            zorder=12,
        )
        source = endpoints.loc[(endpoints["event"] == event) & endpoints["active"].astype(bool)]
        axis.scatter(
            source["source_lon"],
            source["source_lat"],
            s=3.5,
            c=EVENT_COLORS[event],
            alpha=0.22,
            linewidths=0,
            transform=DATA_CRS,
            zorder=11,
        )
        add_panel_label(axis, f"({chr(97 + index)}) {event}")
        axis.text(
            0.98,
            0.05,
            f"median Δλ = {metrics[event]['median_eastward_deg']:.1f}°\n"
            f"active weight = {100 * metrics[event]['active_weight_fraction']:.0f}%",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=9.4,
            color="#0F2431",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 2.4},
            zorder=20,
        )
    colorbar = fig.colorbar(mesh, ax=axes, orientation="horizontal", fraction=0.065, pad=0.08)
    colorbar.set_label("Positive-anomaly-weighted trajectory occupancy (a.u.)")
    png, pdf = save_figure_pair(fig, "fig02_trajectory_connectivity", output_dir)
    return {
        "particles": particle_counts,
        "metrics": metrics,
        "density_limits": [vmin, vmax],
        "artifacts": _artifact_metadata(png, pdf),
    }


def build_arrival_box_map(output_dir: Path, ohc_field=None) -> dict:
    values: dict[int, dict[str, float]] = {}
    storage_values: list[float] = []
    for event in EVENTS:
        values[event] = {}
        for box in BOXES:
            row = extract_event_budget(event, "arrival_Jan_Jun", box)
            values[event][box] = float(row["storage_change_zj"])
            storage_values.append(values[event][box])
        values[event]["east_inflow"] = float(
            extract_event_budget(event, "arrival_Jan_Jun", "east")[
                "west_theta_heat_in_zj"
            ]
        )
    limit = max(5.0, float(np.ceil(max(abs(np.asarray(storage_values))) / 5.0) * 5.0))
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    cmap = plt.get_cmap("RdBu_r")
    max_inflow = max(values[event]["east_inflow"] for event in EVENTS)

    fig = plt.figure(figsize=(12.4, 4.2), constrained_layout=True)
    axes = fig.subplots(
        1,
        3,
        subplot_kw={"projection": ccrs.PlateCarree(central_longitude=180.0)},
    )
    for index, (axis, event) in enumerate(zip(axes, EVENTS, strict=True)):
        format_pacific_axis(
            axis,
            extent=(155.0, 285.0, -17.0, 13.0),
            label_left=index == 0,
            label_bottom=True,
        )
        for box in BOXES:
            _fill_box(axis, box, values[event][box], cmap=cmap, norm=norm)
        draw_box_boundaries(axis, emphasize_gate=220.0)
        for box, (west, east, south, north) in BOXES.items():
            axis.text(
                (west + east) / 2,
                (south + north) / 2,
                f"{values[event][box]:+.1f}",
                transform=DATA_CRS,
                ha="center",
                va="center",
                fontsize=10.5,
                fontweight="bold" if box == "east" else "normal",
                color="#10232F",
                zorder=18,
            )
        inflow = values[event]["east_inflow"]
        _draw_arrow(
            axis,
            (213.5, -7.2),
            (231.0, -7.2),
            color=EVENT_COLORS[event],
            linewidth=arrow_width_zj(inflow, max_inflow),
        )
        axis.text(
            222.0,
            -10.7,
            f"140°W inflow  {inflow:.2f} ZJ",
            transform=DATA_CRS,
            ha="center",
            va="top",
            fontsize=9.2,
            color=EVENT_COLORS[event],
            fontweight="bold",
            zorder=20,
        )
        add_panel_label(axis, f"({chr(97 + index)}) {event}")
    scalar = ScalarMappable(norm=norm, cmap=cmap)
    colorbar = fig.colorbar(scalar, ax=axes, orientation="horizontal", fraction=0.065, pad=0.085)
    colorbar.set_label("Jan–Jun box OHC′ change (ZJ)")
    png, pdf = save_figure_pair(fig, "fig03_arrival_box_map", output_dir)
    return {
        "east_inflow_zj": {event: round(values[event]["east_inflow"], 2) for event in EVENTS},
        "east_storage_gain_zj": {event: round(values[event]["east"], 2) for event in EVENTS},
        "storage_color_limits_zj": [-limit, limit],
        "artifacts": _artifact_metadata(png, pdf),
    }


def build_fate_budget_map(output_dir: Path, surface_field=None) -> dict:
    budget: dict[int, dict[str, float]] = {}
    flow_terms: list[float] = []
    for event in EVENTS:
        row = extract_event_budget(event, "decay_Jan_May_next", "east")
        budget[event] = {
            "storage_change": float(row["storage_change_zj"]),
            "westward_return": -float(row["west_theta_heat_in_zj"]),
            "eastward_export": -float(row["east_theta_heat_in_zj"]),
            "northward_output": float(row["northward_output_zj"]),
            "southward_output": float(row["southward_output_zj"]),
            "surface_loss": float(row["surface_loss_zj"]),
            "residual": float(row["residual_zj"]),
        }
        flow_terms.extend(
            budget[event][key]
            for key in (
                "westward_return",
                "eastward_export",
                "northward_output",
                "southward_output",
                "surface_loss",
            )
        )
    max_flow = max(abs(np.asarray(flow_terms, dtype=float)))
    storage_limit = 25.0
    storage_norm = TwoSlopeNorm(vmin=-storage_limit, vcenter=0.0, vmax=storage_limit)
    storage_cmap = plt.get_cmap("RdBu_r")
    colors = {
        "westward_return": "#2F86C1",
        "eastward_export": "#C98B19",
        "northward_output": "#E97800",
        "southward_output": "#6D55A3",
        "surface_loss": "#C63C3C",
    }

    fig = plt.figure(figsize=(12.4, 4.45), constrained_layout=True)
    axes = fig.subplots(
        1,
        3,
        subplot_kw={"projection": ccrs.PlateCarree(central_longitude=180.0)},
    )
    for index, (axis, event) in enumerate(zip(axes, EVENTS, strict=True)):
        format_pacific_axis(
            axis,
            extent=(205.0, 286.0, -18.0, 14.0),
            label_left=index == 0,
            label_bottom=True,
        )
        _fill_box(
            axis,
            "east",
            budget[event]["storage_change"],
            cmap=storage_cmap,
            norm=storage_norm,
            alpha=0.78,
        )
        draw_box_boundaries(axis, emphasize_gate=220.0)
        width = lambda key: arrow_width_zj(budget[event][key], max_flow)
        _draw_arrow(
            axis,
            (224.0, -1.2),
            (211.0, -1.2),
            color=colors["westward_return"],
            linewidth=width("westward_return"),
        )
        _draw_arrow(
            axis,
            (276.0, -1.2),
            (284.0, -1.2),
            color=colors["eastward_export"],
            linewidth=width("eastward_export"),
        )
        north = budget[event]["northward_output"]
        _draw_arrow(
            axis,
            (248.0, 3.0) if north >= 0 else (248.0, 11.0),
            (248.0, 11.0) if north >= 0 else (248.0, 3.0),
            color=colors["northward_output"],
            linewidth=width("northward_output"),
        )
        south = budget[event]["southward_output"]
        _draw_arrow(
            axis,
            (258.0, -8.0) if south >= 0 else (258.0, -15.5),
            (258.0, -15.5) if south >= 0 else (258.0, -8.0),
            color=colors["southward_output"],
            linewidth=width("southward_output"),
        )
        for longitude in np.linspace(231.0, 269.0, 5):
            loss_width = arrow_width_zj(budget[event]["surface_loss"], max_flow)
            _draw_arrow(
                axis,
                (longitude, -5.8),
                (longitude, -2.8),
                color=colors["surface_loss"],
                linewidth=max(0.6, 0.48 * loss_width),
                alpha=0.76,
                zorder=14,
            )
        axis.text(
            251.5,
            0.0,
            f"ΔH′ = {budget[event]['storage_change']:+.2f} ZJ",
            transform=DATA_CRS,
            ha="center",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color="#10232F",
            zorder=20,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.76, "pad": 2.0},
        )
        axis.text(
            0.98,
            0.94,
            f"R′ = {budget[event]['residual']:+.2f} ZJ",
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=9.3,
            color="#148F88",
            fontweight="bold",
            zorder=20,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 1.8},
        )
        axis.text(
            0.02,
            0.06,
            f"W {budget[event]['westward_return']:+.2f}   "
            f"N {budget[event]['northward_output']:+.2f}   "
            f"S {budget[event]['southward_output']:+.2f}\n"
            f"E {budget[event]['eastward_export']:+.2f}   "
            f"surface {budget[event]['surface_loss']:+.2f} ZJ",
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=8.4,
            color="#10232F",
            zorder=20,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 2.0},
        )
        add_panel_label(axis, f"({chr(97 + index)}) {event}")

    scalar = ScalarMappable(norm=storage_norm, cmap=storage_cmap)
    colorbar = fig.colorbar(scalar, ax=axes, orientation="horizontal", fraction=0.055, pad=0.085)
    colorbar.set_label("Following Jan–May east-box OHC′ change (ZJ)")
    handles = [
        Line2D([0], [0], color=colors["westward_return"], lw=3, label="Westward return"),
        Line2D([0], [0], color=colors["northward_output"], lw=3, label="Northward export"),
        Line2D([0], [0], color=colors["southward_output"], lw=3, label="Southward export"),
        Line2D([0], [0], color=colors["surface_loss"], lw=3, label="Surface heat loss"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.04))
    png, pdf = save_figure_pair(fig, "fig04_fate_budget_map", output_dir)
    return {
        "storage_loss_zj": {
            event: round(-budget[event]["storage_change"], 2) for event in EVENTS
        },
        "westward_return_zj": {
            event: round(budget[event]["westward_return"], 2) for event in EVENTS
        },
        "northward_output_zj": {
            event: round(budget[event]["northward_output"], 2) for event in EVENTS
        },
        "southward_output_zj": {
            event: round(budget[event]["southward_output"], 2) for event in EVENTS
        },
        "surface_loss_zj": {
            event: round(budget[event]["surface_loss"], 2) for event in EVENTS
        },
        "residual_zj": {event: round(budget[event]["residual"], 2) for event in EVENTS},
        "max_arrow_reference_zj": max_flow,
        "artifacts": _artifact_metadata(png, pdf),
    }
