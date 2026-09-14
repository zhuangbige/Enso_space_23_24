#!/usr/bin/env python3
"""Track January--June warm-anomaly centroids for 1997, 2015, and 2023.

The input is the existing 5S--5N cosine-weighted SODA3.15.2 section of
volumetric heat-content anomaly q'=rho0*Cp0*T'.  For each event month, the
centroid uses positive anomaly as the amplitude and native cell thickness/width
as geometry weights.  No hand-defined longitude or depth bins are used.
"""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/soda3_warm_anomaly_centroid_trajectories"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache"))

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg")
import matplotlib.pyplot as plt


INPUT = (
    ROOT
    / "data/derived/research_2026"
    / "soda3_ohc_vertical_sections_continuous_1997_2015_2023_1980_2024_detrended.nc"
)
EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
COLORS = {1997: "#0072B2", 2015: "#D55E00", 2023: "#7A3DB8"}
EARTH_RADIUS_M = 6_371_000.0
BOTTOM_DEPTH_M = 300.0


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.5,
            "axes.titlesize": 11.0,
            "axes.labelsize": 10.0,
            "xtick.labelsize": 8.8,
            "ytick.labelsize": 8.8,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def cell_edges(centers: np.ndarray, *, first: float, last: float) -> np.ndarray:
    values = np.asarray(centers, dtype=float)
    if values.ndim != 1 or values.size < 2 or not np.all(np.diff(values) > 0):
        raise ValueError("Cell centers must be a strictly increasing 1-D array")
    edges = np.empty(values.size + 1, dtype=float)
    edges[0] = first
    edges[1:-1] = 0.5 * (values[:-1] + values[1:])
    edges[-1] = last
    if not np.all(np.diff(edges) > 0):
        raise ValueError("Derived cell edges are not strictly increasing")
    return edges


def inspect_input(ds: xr.Dataset) -> None:
    required = {"heat_content_density_anomaly", "time", "depth", "lon"}
    missing = required.difference(set(ds.data_vars) | set(ds.coords))
    if missing:
        raise ValueError(f"Input is missing {sorted(missing)}")
    field = ds.heat_content_density_anomaly
    if field.dims != ("time", "depth", "lon"):
        raise ValueError(f"Unexpected field dimensions: {field.dims}")
    if field.attrs.get("units") != "MJ m-3":
        raise ValueError(f"Unexpected field units: {field.attrs.get('units')}")
    years = ds.time.dt.year.values.astype(int)
    months = ds.time.dt.month.values.astype(int)
    for event in EVENTS:
        selected = months[years == event]
        if tuple(selected) != MONTHS:
            raise ValueError(f"{event} does not contain January--June exactly: {selected}")
    depth = ds.depth.values.astype(float)
    lon = ds.lon.values.astype(float)
    if depth[0] > 10.0 or depth[-1] < 280.0:
        raise ValueError(f"Depth does not span the upper 300 m: {depth[[0, -1]]}")
    if lon[0] > 121.0 or lon[-1] < 279.0:
        raise ValueError(f"Longitude does not span 120E--80W: {lon[[0, -1]]}")


def geometry_weights(field: xr.DataArray) -> xr.DataArray:
    depth = field.depth.values.astype(float)
    lon = field.lon.values.astype(float)
    depth_edges = cell_edges(depth, first=0.0, last=BOTTOM_DEPTH_M)
    lon_step = float(np.median(np.diff(lon)))
    lon_edges = cell_edges(
        lon,
        first=float(lon[0] - 0.5 * lon_step),
        last=float(lon[-1] + 0.5 * lon_step),
    )
    dz = np.diff(depth_edges)
    dx = EARTH_RADIUS_M * np.deg2rad(np.diff(lon_edges))
    if not np.isclose(dz.sum(), BOTTOM_DEPTH_M):
        raise AssertionError(f"Depth-cell thicknesses sum to {dz.sum()}, not 300 m")
    weights = xr.DataArray(
        dz[:, None] * dx[None, :],
        dims=("depth", "lon"),
        coords={"depth": field.depth, "lon": field.lon},
        name="section_cell_area",
        attrs={"units": "m2"},
    )
    return weights


def weighted_centroid(
    field: xr.DataArray,
    cell_area: xr.DataArray,
    *,
    minimum_fraction_of_peak: float = 0.0,
) -> dict[str, float]:
    if not 0.0 <= minimum_fraction_of_peak < 1.0:
        raise ValueError("minimum_fraction_of_peak must be in [0, 1)")
    peak = float(field.max(skipna=True))
    threshold = max(0.0, minimum_fraction_of_peak * peak)
    positive = field.where(field > threshold, 0.0)
    amplitude_weight = positive * cell_area
    denominator = float(amplitude_weight.sum(("depth", "lon"), skipna=True))
    if not np.isfinite(denominator) or denominator <= 0.0:
        raise ValueError("Positive heat-content-density anomaly has zero total weight")

    lon_grid, depth_grid = xr.broadcast(field.lon, field.depth)
    lon_grid = lon_grid.transpose("depth", "lon")
    depth_grid = depth_grid.transpose("depth", "lon")
    lon_centroid = float((amplitude_weight * lon_grid).sum() / denominator)
    depth_centroid = float((amplitude_weight * depth_grid).sum() / denominator)
    lon_spread = float(
        np.sqrt((amplitude_weight * (lon_grid - lon_centroid) ** 2).sum() / denominator)
    )
    depth_spread = float(
        np.sqrt((amplitude_weight * (depth_grid - depth_centroid) ** 2).sum() / denominator)
    )
    # q' [MJ m-3] * section cell area [m2] = MJ m-1.  Divide by 1e9
    # to report petajoules per metre of meridional width.
    positive_section_heat = denominator / 1.0e9
    return {
        "centroid_lon_e": lon_centroid,
        "centroid_depth_m": depth_centroid,
        "lon_spread_deg": lon_spread,
        "depth_spread_m": depth_spread,
        "positive_section_heat_pj_per_m": positive_section_heat,
    }


def build_table(
    ds: xr.Dataset,
    *,
    minimum_fraction_of_peak: float = 0.0,
) -> pd.DataFrame:
    field = ds.heat_content_density_anomaly
    area = geometry_weights(field)
    records: list[dict[str, object]] = []
    for event in EVENTS:
        for month in MONTHS:
            selected = field.where(
                (field.time.dt.year == event) & (field.time.dt.month == month),
                drop=True,
            )
            if selected.sizes.get("time", 0) != 1:
                raise ValueError(f"Expected one field for {event}-{month:02d}")
            metrics = weighted_centroid(
                selected.isel(time=0),
                area,
                minimum_fraction_of_peak=minimum_fraction_of_peak,
            )
            records.append(
                {
                    "event": event,
                    "month": month,
                    "month_label": MONTH_LABELS[month - 1],
                    **metrics,
                }
            )
    table = pd.DataFrame(records).sort_values(["event", "month"]).reset_index(drop=True)
    if len(table) != len(EVENTS) * len(MONTHS):
        raise AssertionError("Unexpected centroid-table length")
    if not table.centroid_lon_e.between(120.0, 280.0).all():
        raise AssertionError("Longitude centroid lies outside the analysis domain")
    if not table.centroid_depth_m.between(0.0, BOTTOM_DEPTH_M).all():
        raise AssertionError("Depth centroid lies outside the analysis domain")
    return table


def build_sensitivity_table(ds: xr.Dataset) -> pd.DataFrame:
    records: list[dict[str, float | int]] = []
    for fraction in (0.0, 0.15, 0.25):
        table = build_table(ds, minimum_fraction_of_peak=fraction)
        for event in EVENTS:
            selected = table.loc[table.event.eq(event)].sort_values("month")
            january = selected.iloc[0]
            june = selected.iloc[-1]
            records.append(
                {
                    "minimum_fraction_of_monthly_peak": fraction,
                    "event": event,
                    "jan_to_jun_eastward_displacement_deg": (
                        june.centroid_lon_e - january.centroid_lon_e
                    ),
                    "jan_to_jun_upward_displacement_m": (
                        january.centroid_depth_m - june.centroid_depth_m
                    ),
                }
            )
    return pd.DataFrame(records)


def format_lon(value: float) -> str:
    value = value % 360.0
    if np.isclose(value, 180.0):
        return "180°"
    return f"{value:g}°E" if value < 180.0 else f"{360.0 - value:g}°W"


def marker_sizes(values: pd.Series) -> np.ndarray:
    lower = float(values.min())
    upper = float(values.max())
    if np.isclose(lower, upper):
        return np.full(values.size, 100.0)
    scaled = (values.to_numpy(dtype=float) - lower) / (upper - lower)
    return 70.0 + 150.0 * scaled


def plot_trajectories(table: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    fig, axes = plt.subplots(1, 3, figsize=(15.8, 5.6))
    fig.subplots_adjust(left=0.065, right=0.985, top=0.83, bottom=0.21, wspace=0.27)
    fig.suptitle(
        "January–June warm-anomaly centroid trajectories in the equatorial upper Pacific",
        fontsize=15.0,
        fontweight="bold",
        y=0.965,
    )

    phase_ax, lon_ax, depth_ax = axes
    sizes = marker_sizes(table.positive_section_heat_pj_per_m)
    table = table.assign(marker_size=sizes)
    for event in EVENTS:
        selected = table.loc[table.event.eq(event)].sort_values("month")
        color = COLORS[event]
        phase_ax.plot(
            selected.centroid_lon_e,
            selected.centroid_depth_m,
            color=color,
            linewidth=2.0,
            alpha=0.88,
            zorder=2,
        )
        for first, second in zip(selected.iloc[:-1].itertuples(), selected.iloc[1:].itertuples()):
            phase_ax.annotate(
                "",
                xy=(second.centroid_lon_e, second.centroid_depth_m),
                xytext=(first.centroid_lon_e, first.centroid_depth_m),
                arrowprops={
                    "arrowstyle": "-|>",
                    "color": color,
                    "lw": 1.7,
                    "mutation_scale": 11,
                    "shrinkA": 8,
                    "shrinkB": 8,
                },
                zorder=3,
            )
        phase_ax.scatter(
            selected.centroid_lon_e,
            selected.centroid_depth_m,
            s=selected.marker_size,
            color=color,
            edgecolor="white",
            linewidth=1.0,
            label=str(event),
            zorder=4,
        )
        for row in selected.itertuples():
            phase_ax.text(
                row.centroid_lon_e,
                row.centroid_depth_m,
                str(row.month),
                ha="center",
                va="center",
                fontsize=7.3,
                fontweight="bold",
                color="white",
                zorder=5,
            )

        lon_ax.plot(
            selected.month,
            selected.centroid_lon_e,
            color=color,
            marker="o",
            markersize=5.8,
            linewidth=2.0,
            label=str(event),
        )
        depth_ax.plot(
            selected.month,
            selected.centroid_depth_m,
            color=color,
            marker="o",
            markersize=5.8,
            linewidth=2.0,
            label=str(event),
        )

    longitude_ticks = (120, 150, 180, 210, 240, 280)
    phase_ax.set_xlim(120, 280)
    phase_ax.set_ylim(240, 40)
    phase_ax.set_xticks(longitude_ticks)
    phase_ax.set_xticklabels([format_lon(value) for value in longitude_ticks])
    phase_ax.set_xlabel("Warm-centroid longitude")
    phase_ax.set_ylabel("Warm-centroid depth (m)")
    phase_ax.set_title("a  Longitude–depth trajectory")
    phase_ax.grid(True, color="0.88", linewidth=0.7)
    phase_ax.legend(title="Event", loc="lower left", frameon=True, framealpha=0.92)
    phase_ax.text(
        0.98,
        0.98,
        "Numbers denote months 1–6\nMarker size ∝ positive section heat",
        transform=phase_ax.transAxes,
        ha="right",
        va="top",
        fontsize=7.7,
        color="0.30",
    )

    for ax in (lon_ax, depth_ax):
        ax.set_xlim(0.75, 6.25)
        ax.set_xticks(MONTHS)
        ax.set_xticklabels(MONTH_LABELS)
        ax.grid(True, color="0.88", linewidth=0.7)
        ax.set_xlabel("Month")
    lon_ax.set_ylim(120, 280)
    lon_ax.set_yticks(longitude_ticks)
    lon_ax.set_yticklabels([format_lon(value) for value in longitude_ticks])
    lon_ax.set_ylabel("Warm-centroid longitude")
    lon_ax.set_title("b  Eastward displacement")

    depth_ax.set_ylim(240, 40)
    depth_ax.set_ylabel("Warm-centroid depth (m)")
    depth_ax.set_title("c  Upward displacement")

    note = (
        "Centroid weights: max(q′,0)×native layer thickness×zonal cell width; "
        "q′=ρ₀CₚT′ from 5°S–5°N cosine-weighted SODA3.15.2. "
        "Anomalies are 1980–2024 same-calendar-month detrended; domain 120°E–80°W, 0–300 m; no bins."
    )
    fig.text(0.012, 0.035, note, fontsize=7.8, color="0.30")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "fig_soda3_1997_2015_2023_jan_jun_warm_anomaly_centroid_trajectories"
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    return png, pdf


def print_summary(table: pd.DataFrame) -> None:
    print(table.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nJanuary-to-June displacement:")
    for event in EVENTS:
        selected = table.loc[table.event.eq(event)].sort_values("month")
        first = selected.iloc[0]
        last = selected.iloc[-1]
        print(
            f"{event}: eastward={last.centroid_lon_e - first.centroid_lon_e:+.2f} degrees; "
            f"upward={first.centroid_depth_m - last.centroid_depth_m:+.2f} m; "
            f"positive-section-heat change="
            f"{last.positive_section_heat_pj_per_m - first.positive_section_heat_pj_per_m:+.3f} PJ m-1"
        )


def main() -> None:
    setup_style()
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)
    with xr.open_dataset(INPUT, engine="h5netcdf") as source:
        inspect_input(source)
        dataset = source.load()
    table = build_table(dataset)
    sensitivity = build_sensitivity_table(dataset)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "soda3_1997_2015_2023_warm_anomaly_centroids_jan_jun.csv"
    sensitivity_path = (
        OUT_DIR
        / "soda3_1997_2015_2023_warm_anomaly_centroid_threshold_sensitivity.csv"
    )
    table.to_csv(csv_path, index=False, float_format="%.6f")
    sensitivity.to_csv(sensitivity_path, index=False, float_format="%.6f")
    png, pdf = plot_trajectories(table, OUT_DIR)
    print_summary(table)
    print("\nThreshold sensitivity:")
    print(sensitivity.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(csv_path)
    print(sensitivity_path)
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
