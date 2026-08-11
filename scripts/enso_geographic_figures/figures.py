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
import pandas as pd

from .config import (
    BOXES,
    EARLY_Q3_EVENT_PATH,
    EARLY_Q3_RELATION_PATH,
    EVENT_COLORS,
    EVENTS,
    OTHER_EVENT_COLOR,
    Q3_EVENT_PATH,
    Q3_RELATION_PATH,
)
from .data import extract_event_budget, load_hovmoller, load_trajectory_data
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


def _symmetric_percentile_limit(values: np.ndarray, percentile: float = 98.0) -> float:
    finite = np.abs(np.asarray(values, dtype=float))
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("Cannot scale a field without finite values")
    return float(max(0.25, np.nanpercentile(finite, percentile)))


def _residualize_standardized(values, controls) -> np.ndarray:
    y = np.asarray(values, dtype=float)
    x = np.asarray(controls, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    design = np.column_stack([np.ones(len(y)), x])
    residual = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
    scale = float(np.std(residual, ddof=1))
    if not np.isfinite(scale) or scale == 0:
        raise ValueError("Residual series has no variance")
    return residual / scale


def _scatter_residual_relation(
    axis,
    frame: pd.DataFrame,
    *,
    year_column: str,
    x_column: str,
    y_column: str,
    control_column: str,
    xlabel: str,
    ylabel: str,
    relation: pd.Series,
) -> None:
    years = frame[year_column].to_numpy(dtype=int)
    controls = frame[control_column].to_numpy(dtype=float)
    x = _residualize_standardized(frame[x_column], controls)
    y = _residualize_standardized(frame[y_column], controls)
    other = ~np.isin(years, EVENTS)
    axis.scatter(
        x[other],
        y[other],
        s=31,
        color=OTHER_EVENT_COLOR,
        alpha=0.84,
        edgecolor="white",
        linewidth=0.55,
        zorder=3,
    )
    for event in EVENTS:
        selected = years == event
        axis.scatter(
            x[selected],
            y[selected],
            s=68,
            color=EVENT_COLORS[event],
            edgecolor="white",
            linewidth=0.8,
            zorder=5,
        )
    slope, intercept = np.polyfit(x, y, 1)
    grid = np.linspace(x.min(), x.max(), 100)
    axis.plot(grid, slope * grid + intercept, color="#102A43", linewidth=1.7, zorder=2)
    axis.axhline(0.0, color="#C7D1D8", linewidth=0.7, zorder=1)
    axis.axvline(0.0, color="#C7D1D8", linewidth=0.7, zorder=1)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(False)
    axis.set_xlabel(xlabel, fontsize=9.2)
    axis.set_ylabel(ylabel, fontsize=9.2)
    axis.text(
        0.97,
        0.96,
        f"r = {relation['partial_r']:+.2f}\np = {relation['permutation_p']:.3f}",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=8.8,
        color="#102A43",
    )


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

    fig = plt.figure(figsize=(10.8, 11.4), constrained_layout=True)
    axes = fig.subplots(
        3,
        1,
        subplot_kw={"projection": ccrs.PlateCarree(central_longitude=180.0)},
    )
    mesh = None
    for index, (axis, event) in enumerate(zip(axes, EVENTS, strict=True)):
        format_pacific_axis(
            axis,
            extent=(145.0, 280.0, -24.0, 20.0),
            label_left=True,
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

    background_norm = None
    background_cmap = plt.get_cmap("RdBu_r")
    if ohc_field is not None:
        background = ohc_field["ohc300_anom_gjm2"].sel(phase="arrival_Jan_Jun")
        background_limit = _symmetric_percentile_limit(background.values)
        background_norm = TwoSlopeNorm(
            vmin=-background_limit,
            vcenter=0.0,
            vmax=background_limit,
        )

    fig = plt.figure(figsize=(10.8, 11.6), constrained_layout=True)
    axes = fig.subplots(
        3,
        1,
        subplot_kw={"projection": ccrs.PlateCarree(central_longitude=180.0)},
    )
    for index, (axis, event) in enumerate(zip(axes, EVENTS, strict=True)):
        format_pacific_axis(
            axis,
            extent=(145.0, 285.0, -24.0, 22.0),
            label_left=True,
            label_bottom=True,
        )
        if ohc_field is not None:
            event_field = background.sel(event=event)
            axis.pcolormesh(
                event_field["lon"],
                event_field["lat"],
                event_field,
                cmap=background_cmap,
                norm=background_norm,
                shading="auto",
                transform=DATA_CRS,
                zorder=2,
            )
            axis.contour(
                event_field["lon"],
                event_field["lat"],
                event_field,
                levels=[0.0],
                colors="#3F4D56",
                linewidths=0.45,
                transform=DATA_CRS,
                zorder=3,
            )
        else:
            for box in BOXES:
                _fill_box(axis, box, values[event][box], cmap=cmap, norm=norm)
        draw_box_boundaries(axis, emphasize_gate=220.0)
        for box, (west, east, south, north) in BOXES.items():
            if ohc_field is not None:
                value = values[event][box]
                axis.scatter(
                    [(west + east) / 2],
                    [(south + north) / 2],
                    s=90.0 + 390.0 * abs(value) / limit,
                    color="#B6243B" if value >= 0 else "#25669A",
                    edgecolor="white",
                    linewidth=1.1,
                    alpha=0.88,
                    transform=DATA_CRS,
                    zorder=16,
                )
            axis.text(
                (west + east) / 2,
                (south + north) / 2,
                f"{values[event][box]:+.1f}",
                transform=DATA_CRS,
                ha="center",
                va="center",
                fontsize=10.5,
                fontweight="bold" if box == "east" else "normal",
                color="white" if ohc_field is not None else "#10232F",
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
    scalar = ScalarMappable(
        norm=background_norm if background_norm is not None else norm,
        cmap=background_cmap if background_norm is not None else cmap,
    )
    colorbar = fig.colorbar(scalar, ax=axes, orientation="horizontal", fraction=0.065, pad=0.085)
    colorbar.set_label(
        "Jan–Jun 0–300 m OHC′ (GJ m$^{-2}$)"
        if background_norm is not None
        else "Jan–Jun box OHC′ change (ZJ)"
    )
    if background_norm is not None:
        fig.text(
            0.5,
            0.995,
            "Circle area represents |box OHC′ change|; red = gain, blue = loss",
            ha="center",
            va="top",
            fontsize=9.0,
            color="#344854",
        )
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

    background_norm = None
    background_cmap = plt.get_cmap("RdBu_r")
    if surface_field is not None:
        background = surface_field["ohc300_anom_gjm2"].sel(phase="fate_Jan_May_next")
        background_limit = _symmetric_percentile_limit(background.values)
        background_norm = TwoSlopeNorm(
            vmin=-background_limit,
            vcenter=0.0,
            vmax=background_limit,
        )

    fig = plt.figure(figsize=(8.4, 15.8), constrained_layout=True)
    axes = fig.subplots(
        3,
        1,
        subplot_kw={"projection": ccrs.PlateCarree(central_longitude=180.0)},
    )
    for index, (axis, event) in enumerate(zip(axes, EVENTS, strict=True)):
        format_pacific_axis(
            axis,
            extent=(205.0, 286.0, -25.0, 25.0),
            label_left=True,
            label_bottom=True,
        )
        if surface_field is not None:
            event_field = background.sel(event=event)
            axis.pcolormesh(
                event_field["lon"],
                event_field["lat"],
                event_field,
                cmap=background_cmap,
                norm=background_norm,
                shading="auto",
                transform=DATA_CRS,
                zorder=2,
            )
            axis.contour(
                event_field["lon"],
                event_field["lat"],
                event_field,
                levels=[0.0],
                colors="#3F4D56",
                linewidths=0.45,
                transform=DATA_CRS,
                zorder=3,
            )
        else:
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

    scalar = ScalarMappable(
        norm=background_norm if background_norm is not None else storage_norm,
        cmap=background_cmap if background_norm is not None else storage_cmap,
    )
    colorbar = fig.colorbar(scalar, ax=axes, orientation="horizontal", fraction=0.055, pad=0.085)
    colorbar.set_label(
        "Following Jan–May 0–300 m OHC′ (GJ m$^{-2}$)"
        if background_norm is not None
        else "Following Jan–May east-box OHC′ change (ZJ)"
    )
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


def build_propagation_atlas(output_dir: Path, fields) -> dict:
    """Combine longitude-time propagation and event OHC maps."""
    hovmoller = load_hovmoller()
    field = fields["ohc300_anom_gjm2"].sel(phase="arrival_Jan_Jun")
    hov_limit = _symmetric_percentile_limit(hovmoller["ohc300_anom_gjm2"].to_numpy())
    map_limit = _symmetric_percentile_limit(field.values)
    hov_norm = TwoSlopeNorm(vmin=-hov_limit, vcenter=0.0, vmax=hov_limit)
    map_norm = TwoSlopeNorm(vmin=-map_limit, vcenter=0.0, vmax=map_limit)
    cmap = plt.get_cmap("RdBu_r")

    fig = plt.figure(figsize=(11.2, 18.0), constrained_layout=True)
    grid = fig.add_gridspec(
        8,
        1,
        height_ratios=(0.78, 1.12, 0.78, 1.12, 0.78, 1.12, 0.10, 0.10),
    )
    hov_axes = [fig.add_subplot(grid[2 * index, 0]) for index in range(3)]
    map_axes = [
        fig.add_subplot(
            grid[2 * index + 1, 0],
            projection=ccrs.PlateCarree(central_longitude=180.0),
        )
        for index in range(3)
    ]
    hov_mesh = None
    map_mesh = None
    for index, event in enumerate(EVENTS):
        event_hov = hovmoller.loc[hovmoller["event_year"] == event]
        matrix = event_hov.pivot(
            index="relative_month",
            columns="lon_deg_e",
            values="ohc300_anom_gjm2",
        ).sort_index().sort_index(axis=1)
        axis = hov_axes[index]
        hov_mesh = axis.pcolormesh(
            matrix.columns.to_numpy(),
            matrix.index.to_numpy(),
            matrix.to_numpy(),
            cmap=cmap,
            norm=hov_norm,
            shading="nearest",
        )
        axis.contour(
            matrix.columns.to_numpy(),
            matrix.index.to_numpy(),
            matrix.to_numpy(),
            levels=[0.0],
            colors="#31424D",
            linewidths=0.55,
        )
        axis.axvline(220.0, color="#111820", linewidth=1.7)
        axis.set_xlim(130.0, 280.0)
        axis.set_ylim(-6.0, 10.0)
        axis.set_xticks([140.0, 180.0, 220.0, 260.0, 280.0])
        axis.set_xticklabels(["140°E", "180°", "140°W", "100°W", "80°W"])
        axis.set_yticks([-6, 0, 5, 10])
        axis.set_yticklabels(["Jul −1", "Jan", "Jun", "Nov"])
        axis.tick_params(length=3, width=0.7)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(color="#D2D9DE", linestyle=":", linewidth=0.5)
        add_panel_label(axis, f"({chr(97 + 2 * index)}) {event}")

        map_axis = map_axes[index]
        format_pacific_axis(
            map_axis,
            extent=(130.0, 280.0, -22.0, 22.0),
            label_left=True,
            label_bottom=True,
        )
        event_field = field.sel(event=event)
        map_mesh = map_axis.pcolormesh(
            event_field["lon"],
            event_field["lat"],
            event_field,
            cmap=cmap,
            norm=map_norm,
            shading="auto",
            transform=DATA_CRS,
            zorder=2,
        )
        map_axis.contour(
            event_field["lon"],
            event_field["lat"],
            event_field,
            levels=[0.0],
            colors="#35454F",
            linewidths=0.5,
            transform=DATA_CRS,
            zorder=3,
        )
        draw_box_boundaries(map_axis, emphasize_gate=220.0)
        add_panel_label(map_axis, f"({chr(98 + 2 * index)}) {event}")

    hov_color_axis = fig.add_subplot(grid[6, 0])
    map_color_axis = fig.add_subplot(grid[7, 0])
    hov_colorbar = fig.colorbar(
        hov_mesh,
        cax=hov_color_axis,
        orientation="horizontal",
    )
    hov_colorbar.set_label("Equatorial 0–300 m OHC′ (GJ m$^{-2}$)")
    map_colorbar = fig.colorbar(
        map_mesh,
        cax=map_color_axis,
        orientation="horizontal",
    )
    map_colorbar.set_label("Jan–Jun 0–300 m OHC′ (GJ m$^{-2}$)")
    png, pdf = save_figure_pair(fig, "fig01_propagation_atlas", output_dir)
    return {
        "events": list(EVENTS),
        "gate_longitude_deg_e": 220.0,
        "color_limits": [-map_limit, map_limit],
        "hovmoller_color_limits": [-hov_limit, hov_limit],
        "artifacts": _artifact_metadata(png, pdf),
    }


def build_q3_state_map(output_dir: Path, fields=None) -> dict:
    """Map the geographic diagnostics and retain only compact residual evidence."""
    early = pd.read_csv(EARLY_Q3_EVENT_PATH)
    early_relations = pd.read_csv(EARLY_Q3_RELATION_PATH).set_index("test_id")
    fate = pd.read_csv(Q3_EVENT_PATH)
    fate_relations = pd.read_csv(Q3_RELATION_PATH).set_index("test_id")
    route_relation = early_relations.loc["jfm_north_to_ne925"]
    stress_relation = fate_relations.loc["decay_tau_to_north_given_arrival"]
    surface_relation = fate_relations.loc["decay_sst_to_surface_given_arrival"]

    fig = plt.figure(figsize=(12.4, 7.6), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=(1.18, 0.92))
    map_axis = fig.add_subplot(
        grid[0, :], projection=ccrs.PlateCarree(central_longitude=180.0)
    )
    format_pacific_axis(
        map_axis,
        extent=(165.0, 285.0, -14.0, 15.0),
        label_left=True,
        label_bottom=True,
    )

    # Thermodynamic eastern box: geographic state, not a causal connector.
    east = BOXES["east"]
    map_axis.add_patch(
        Rectangle(
            (east[0], east[2]),
            east[1] - east[0],
            east[3] - east[2],
            facecolor="#E98C76",
            edgecolor="#A84335",
            linewidth=1.2,
            alpha=0.18,
            hatch="....",
            transform=DATA_CRS,
            zorder=3,
        )
    )
    map_axis.text(
        266.0,
        -7.6,
        "Following eastern SST\nand surface heat loss",
        transform=DATA_CRS,
        ha="right",
        va="bottom",
        color="#8B342C",
        fontsize=9.5,
        fontweight="bold",
        zorder=12,
    )

    # Jiang MJJ northeasterly diagnostic box: 3–7N, 180E–130W.
    map_axis.add_patch(
        Rectangle(
            (180.0, 3.0),
            50.0,
            4.0,
            facecolor="#7B6CAF",
            edgecolor="#594A89",
            linewidth=1.3,
            alpha=0.22,
            transform=DATA_CRS,
            zorder=4,
        )
    )
    _draw_arrow(
        map_axis,
        (224.0, 10.5),
        (211.0, 1.0),
        color="#594A89",
        linewidth=2.8,
        zorder=13,
    )
    map_axis.text(
        181.5,
        8.3,
        "MJJ NE925 region",
        transform=DATA_CRS,
        ha="left",
        va="bottom",
        color="#594A89",
        fontsize=9.5,
        fontweight="bold",
        zorder=12,
    )

    # JFM northward routing across 5N and following local 5N stress gate.
    for longitude in (238.0, 252.0, 266.0):
        _draw_arrow(
            map_axis,
            (longitude, 2.5),
            (longitude, 9.7),
            color="#E97800",
            linewidth=2.2,
            zorder=13,
        )
    map_axis.text(
        270.0,
        10.6,
        "JFM northward export",
        transform=DATA_CRS,
        ha="right",
        va="bottom",
        color="#C65F00",
        fontsize=9.5,
        fontweight="bold",
        zorder=12,
    )
    map_axis.plot(
        [220.0, 280.0],
        [5.0, 5.0],
        color="#2F86C1",
        linewidth=3.0,
        transform=DATA_CRS,
        zorder=14,
    )
    map_axis.text(
        278.0,
        3.8,
        "Following 5°N stress",
        transform=DATA_CRS,
        ha="right",
        va="top",
        color="#236A9D",
        fontsize=9.5,
        fontweight="bold",
        zorder=12,
    )
    draw_box_boundaries(map_axis, emphasize_gate=220.0)
    add_panel_label(map_axis, "(a) Geographic diagnostics")

    scatter_axes = [fig.add_subplot(grid[1, index]) for index in range(3)]
    _scatter_residual_relation(
        scatter_axes[0],
        early,
        year_column="year",
        x_column="north_output_jfm_zj",
        y_column="ne925_mjj_ms",
        control_column="arrival_140w_jfm_zj",
        xlabel="JFM northward export residual (SD)",
        ylabel="MJJ NE925 residual (SD)",
        relation=route_relation,
    )
    _scatter_residual_relation(
        scatter_axes[1],
        fate,
        year_column="event_year",
        x_column="decay_tau5n_westward_nm2",
        y_column="decay_northward_output_zj",
        control_column="arrival_140w_heat_in_zj",
        xlabel="Following 5°N stress residual (SD)",
        ylabel="Northward export residual (SD)",
        relation=stress_relation,
    )
    _scatter_residual_relation(
        scatter_axes[2],
        fate,
        year_column="event_year",
        x_column="decay_east_sst_anom_c",
        y_column="decay_surface_loss_zj",
        control_column="arrival_140w_heat_in_zj",
        xlabel="Eastern SST residual (SD)",
        ylabel="Surface heat-loss residual (SD)",
        relation=surface_relation,
    )
    for index, axis in enumerate(scatter_axes, start=1):
        add_panel_label(axis, f"({chr(97 + index)})")

    handles = [
        Line2D([0], [0], marker="o", linestyle="none", color=EVENT_COLORS[event], label=str(event))
        for event in EVENTS
    ]
    handles.insert(
        0,
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="none",
            color=OTHER_EVENT_COLOR,
            label="Other events",
        ),
    )
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.015))
    png, pdf = save_figure_pair(fig, "fig05_q3_state_map", output_dir)
    return {
        "n_events": int(len(fate)),
        "relations": {
            "route_to_ne925": {
                "r": float(route_relation["partial_r"]),
                "p": float(route_relation["permutation_p"]),
            },
            "stress_to_export": {
                "r": float(stress_relation["partial_r"]),
                "p": float(stress_relation["permutation_p"]),
            },
            "sst_to_surface_loss": {
                "r": float(surface_relation["partial_r"]),
                "p": float(surface_relation["permutation_p"]),
            },
        },
        "artifacts": _artifact_metadata(png, pdf),
    }
