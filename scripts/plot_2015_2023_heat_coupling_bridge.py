#!/usr/bin/env python3
"""PPT-ready 2015/2023 heat-allocation and coupling comparison figures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LATITUDE_FORMATTER
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


EARTH_RADIUS_M = 6_371_000.0
BASELINE = (1982, 2014)
EVENT_YEARS = (1997, 2015, 2023)
MJJ_MONTHS = (5, 6, 7)
ROOT = Path(__file__).resolve().parents[1]
EVENT_COLORS = {1997: "#2F7FB8", 2015: "#D97706", 2023: "#0F8F83"}
BOX_BOUNDS = {
    "west": (160.0, 180.0, -10.0, 5.0),
    "central": (180.0, 220.0, -10.0, 5.0),
    "east": (220.0, 280.0, -10.0, 5.0),
}
# Fixed ocean-cell areas diagnosed from the SODA3.15.2 0-300 m OHC mask.
BOX_WET_AREA_M2 = {
    "west": 3.695189276063043e12,
    "central": 7.390378552126086e12,
    "east": 10.999217977165735e12,
}
BOX_LABELS = {"west": "WEST", "central": "CENTRAL", "east": "EAST"}


@dataclass(frozen=True)
class PlotOutputs:
    map_pngs: tuple[Path, ...]
    coupling_png: Path
    pdfs: tuple[Path, ...]
    arrival_audit_csv: Path
    mjj_sst_audit_csv: Path


def spherical_box_area_m2(
    lon0: float,
    lon1: float,
    lat0: float,
    lat1: float,
    radius_m: float = EARTH_RADIUS_M,
) -> float:
    """Return the exact spherical area of a latitude-longitude box."""

    longitude_width = np.deg2rad(lon1 - lon0)
    latitude_factor = np.sin(np.deg2rad(lat1)) - np.sin(np.deg2rad(lat0))
    return float(radius_m**2 * longitude_width * latitude_factor)


def heat_density_gj_m2(heat_zj: float, area_m2: float) -> float:
    """Convert a box-integrated heat amount in ZJ to GJ m-2."""

    if area_m2 <= 0:
        raise ValueError("Box area must be positive")
    return float(heat_zj * 1.0e21 / area_m2 / 1.0e9)


def symmetric_density_limit(values: pd.Series) -> float:
    """Return a shared rounded color limit that contains every event."""

    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("No finite heat-density values")
    return float(np.ceil(np.max(np.abs(finite)) * 10.0) / 10.0)


def same_month_linear_anomaly(
    frame: pd.DataFrame,
    value_column: str,
    baseline: tuple[int, int] = BASELINE,
) -> pd.Series:
    """Remove the calendar-month linear expectation over a fixed baseline."""

    required = {"year", "month", value_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    output = pd.Series(np.nan, index=frame.index, dtype=float)
    for month, group in frame.groupby("month", sort=False):
        reference = group.loc[
            group.year.between(*baseline), ["year", value_column]
        ].dropna()
        if len(reference) < 3:
            raise ValueError(f"Month {month} has fewer than three baseline values")
        slope, intercept = np.polyfit(
            reference.year.to_numpy(dtype=float),
            reference[value_column].to_numpy(dtype=float),
            1,
        )
        expected = intercept + slope * group.year.to_numpy(dtype=float)
        output.loc[group.index] = group[value_column].to_numpy(dtype=float) - expected
    return output


def build_mjj_sst_contrast(atmosphere_csv: Path | str) -> pd.DataFrame:
    """Return MJJ Niño-4 and far-eastern-Pacific SST anomalies by event."""

    source = pd.read_csv(atmosphere_csv)
    metrics = {"Nino4": "nino4_raw_c", "FEP": "fep_raw_c"}
    rows: list[dict[str, float | int | str]] = []
    for region, column in metrics.items():
        anomaly = same_month_linear_anomaly(source, column)
        working = source[["year", "month"]].copy()
        working["sst_anomaly_c"] = anomaly
        means = (
            working.loc[
                working.year.isin(EVENT_YEARS) & working.month.isin(MJJ_MONTHS)
            ]
            .groupby("year", as_index=False)["sst_anomaly_c"]
            .mean()
        )
        for row in means.itertuples(index=False):
            rows.append(
                {
                    "event_year": int(row.year),
                    "region": region,
                    "sst_anomaly_c": float(row.sst_anomaly_c),
                }
            )
    return pd.DataFrame(rows).sort_values(["region", "event_year"]).reset_index(drop=True)


def build_arrival_map_table(three_box_csv: Path | str) -> pd.DataFrame:
    """Prepare Jan-Jun storage changes for geographically faithful shading."""

    source = pd.read_csv(three_box_csv)
    required = {
        "event_year",
        "phase",
        "box",
        "storage_change_zj",
        "west_theta_heat_in_zj",
    }
    missing = required.difference(source.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    selected = source.loc[
        source.event_year.isin(EVENT_YEARS)
        & source.phase.eq("arrival_Jan_Jun")
        & source.box.isin(BOX_BOUNDS)
    ].copy()
    counts = selected.groupby("event_year")["box"].nunique().to_dict()
    expected_counts = {event_year: 3 for event_year in EVENT_YEARS}
    if counts != expected_counts:
        raise ValueError(f"Expected three arrival boxes per event, found {counts}")

    records: list[dict[str, float | int | str]] = []
    for row in selected.itertuples(index=False):
        lon0, lon1, lat0, lat1 = BOX_BOUNDS[row.box]
        area = BOX_WET_AREA_M2[row.box]
        records.append(
            {
                "event_year": int(row.event_year),
                "box": str(row.box),
                "lon0": lon0,
                "lon1": lon1,
                "lat0": lat0,
                "lat1": lat1,
                "area_m2": area,
                "area_kind": "SODA3 fixed wet-cell area",
                "storage_change_zj": float(row.storage_change_zj),
                "storage_density_gj_m2": heat_density_gj_m2(
                    float(row.storage_change_zj), area
                ),
                "input_140w_zj": (
                    float(row.west_theta_heat_in_zj) if row.box == "east" else np.nan
                ),
            }
        )
    return pd.DataFrame(records).sort_values(["event_year", "lon0"]).reset_index(drop=True)


def _set_plot_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 12,
            "axes.labelsize": 13,
            "axes.linewidth": 1.0,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 12,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _save_figure(fig: plt.Figure, png: Path, pdf: Path) -> None:
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_arrival_map(
    arrival_table: pd.DataFrame,
    event_year: int,
    png: Path,
    pdf: Path,
) -> None:
    """Draw one full-width Pacific map for one event."""

    event = arrival_table.loc[arrival_table.event_year.eq(event_year)].copy()
    if len(event) != 3:
        raise ValueError(f"Expected three boxes for {event_year}")

    projection = ccrs.PlateCarree(central_longitude=180.0)
    data_crs = ccrs.PlateCarree()
    fig = plt.figure(figsize=(13.8, 5.4))
    ax = fig.add_subplot(1, 1, 1, projection=projection)
    ax.set_extent([150.0, 282.0, -15.5, 9.0], crs=data_crs)
    ax.set_facecolor("#F7FBFF")
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#E7E5E4", zorder=3)
    ax.coastlines(resolution="50m", color="#263746", linewidth=0.8, zorder=4)

    density_limit = symmetric_density_limit(arrival_table["storage_density_gj_m2"])
    norm = Normalize(vmin=-density_limit, vmax=density_limit)
    cmap = plt.get_cmap("RdBu_r")
    for row in event.itertuples(index=False):
        rectangle = Rectangle(
            (row.lon0, row.lat0),
            row.lon1 - row.lon0,
            row.lat1 - row.lat0,
            transform=data_crs,
            facecolor=cmap(norm(row.storage_density_gj_m2)),
            edgecolor="#102A43",
            linewidth=2.0,
            zorder=2,
        )
        ax.add_patch(rectangle)
        center_lon = (row.lon0 + row.lon1) / 2.0
        center_lat = (row.lat0 + row.lat1) / 2.0
        ax.text(
            center_lon,
            center_lat + 1.5,
            BOX_LABELS[row.box],
            transform=data_crs,
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color="#102A43",
            zorder=5,
        )
        ax.text(
            center_lon,
            center_lat - 1.2,
            f"{row.storage_change_zj:+.2f} ZJ",
            transform=data_crs,
            ha="center",
            va="center",
            fontsize=16,
            fontweight="bold",
            color="#102A43",
            zorder=5,
        )

    east = event.loc[event.box.eq("east")].iloc[0]
    ax.annotate(
        "",
        xy=(226.0, -12.3),
        xytext=(214.0, -12.3),
        xycoords=data_crs._as_mpl_transform(ax),
        textcoords=data_crs._as_mpl_transform(ax),
        arrowprops={"arrowstyle": "-|>", "lw": 2.5, "color": "#102A43"},
        zorder=6,
    )
    ax.text(
        220.0,
        -14.2,
        f"140°W input  {east.input_140w_zj:.2f} ZJ",
        transform=data_crs,
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color="#102A43",
        zorder=6,
    )
    ax.text(
        152.0,
        7.0,
        str(event_year),
        transform=data_crs,
        ha="left",
        va="top",
        fontsize=22,
        fontweight="bold",
        color=EVENT_COLORS[event_year],
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": EVENT_COLORS[event_year], "linewidth": 1.5},
        zorder=7,
    )

    ax.set_xticks([-20, 0, 40, 80, 100])
    ax.set_xticklabels(["160°E", "180°", "140°W", "100°W", "80°W"])
    ax.set_yticks([-10, 0, 5], crs=data_crs)
    ax.yaxis.set_major_formatter(LATITUDE_FORMATTER)
    ax.tick_params(length=5, width=1.0, color="#475569")
    ax.gridlines(
        crs=data_crs,
        draw_labels=False,
        linewidth=0.55,
        color="#94A3B8",
        alpha=0.55,
        linestyle=":",
        zorder=1,
    )
    ax.set_xlabel("Longitude", labelpad=10)
    ax.set_ylabel("Latitude", labelpad=10)

    scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    scalar.set_array([])
    colorbar = fig.colorbar(
        scalar,
        ax=ax,
        orientation="horizontal",
        fraction=0.075,
        pad=0.12,
        aspect=38,
        extend="both",
    )
    colorbar.set_label("Jan–Jun OHC change per unit area (GJ m⁻²)", labelpad=8)
    colorbar.outline.set_linewidth(0.8)
    _save_figure(fig, png, pdf)


def _style_cartesian_axis(ax: plt.Axes, panel: str) -> None:
    ax.text(
        0.0,
        1.03,
        panel,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=14,
        fontweight="bold",
        color="#102A43",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#CBD5E1", linewidth=0.7, alpha=0.8)
    ax.set_axisbelow(True)


def plot_coupling_contrast(
    sst_table: pd.DataFrame,
    coupling_csv: Path | str,
    png: Path,
    pdf: Path,
) -> None:
    """Draw direct 2015/2023 SST-distribution and coupling contrasts."""

    coupling = pd.read_csv(coupling_csv)
    required = {
        "year",
        "month",
        "net_ocean_loss_anom_wm2",
        "minus_olr_cp_wm2",
        "tau_cwp_anom_nm2",
    }
    missing = required.difference(coupling.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    coupling = coupling.loc[
        coupling.year.isin(EVENT_YEARS) & coupling.month.between(3, 11)
    ].copy()
    counts = coupling.groupby("year")["month"].nunique().to_dict()
    expected_counts = {event_year: 9 for event_year in EVENT_YEARS}
    if counts != expected_counts:
        raise ValueError(f"Expected complete March-November series, found {counts}")

    fig, axes = plt.subplots(2, 2, figsize=(13.4, 10.0))
    ax = axes[0, 0]
    positions = np.arange(2, dtype=float)
    width = 0.24
    offsets = np.linspace(-width, width, len(EVENT_YEARS))
    for offset, event_year in zip(offsets, EVENT_YEARS, strict=True):
        values = []
        for region in ("Nino4", "FEP"):
            value = sst_table.loc[
                sst_table.event_year.eq(event_year) & sst_table.region.eq(region),
                "sst_anomaly_c",
            ].iloc[0]
            values.append(float(value))
        bars = ax.bar(
            positions + offset,
            values,
            width=width,
            color=EVENT_COLORS[event_year],
            label=str(event_year),
            zorder=3,
        )
        ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=11, fontweight="bold")
    ax.set_xticks(positions, ["Niño 4\ncentral Pacific", "FEP\nfar eastern Pacific"])
    ax.set_ylabel("MJJ SST anomaly (°C)")
    ax.axhline(0.0, color="#475569", linewidth=0.9)
    ax.legend(frameon=False, loc="upper left", ncols=2)
    _style_cartesian_axis(ax, "(a)")

    line_specs = (
        (
            axes[0, 1],
            "net_ocean_loss_anom_wm2",
            "Eastern Pacific ocean heat-loss anomaly\n(W m⁻²; positive upward)",
            "(b)",
        ),
        (
            axes[1, 0],
            "minus_olr_cp_wm2",
            "Central Pacific −OLR anomaly (W m⁻²)",
            "(c)",
        ),
        (
            axes[1, 1],
            "tau_cwp_anom_nm2",
            "Central-western Pacific eastward stress\nanomaly (N m⁻²)",
            "(d)",
        ),
    )
    for axis, metric, ylabel, panel in line_specs:
        axis.axvspan(4.5, 7.5, color="#E2E8F0", alpha=0.65, zorder=0)
        axis.axhline(0.0, color="#64748B", linewidth=0.9, zorder=1)
        for event_year in EVENT_YEARS:
            event = coupling.loc[coupling.year.eq(event_year)].sort_values("month")
            axis.plot(
                event.month,
                event[metric],
                color=EVENT_COLORS[event_year],
                linewidth=2.8,
                marker="o",
                markersize=6.5,
                markeredgecolor="white",
                markeredgewidth=0.8,
                label=str(event_year),
                zorder=3,
            )
        axis.text(
            6.0,
            0.96,
            "MJJ",
            transform=axis.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
            color="#475569",
        )
        axis.set_xlim(2.7, 11.3)
        axis.set_xticks(
            range(3, 12),
            ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"],
        )
        axis.set_xlabel("Month")
        axis.set_ylabel(ylabel)
        _style_cartesian_axis(axis, panel)

    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.08, top=0.96, wspace=0.28, hspace=0.35)
    _save_figure(fig, png, pdf)


def run_pipeline(
    three_box_csv: Path | str,
    atmosphere_csv: Path | str,
    coupling_csv: Path | str,
    output_dir: Path | str,
) -> PlotOutputs:
    """Build audit tables and all requested figures."""

    _set_plot_style()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    arrival = build_arrival_map_table(three_box_csv)
    sst = build_mjj_sst_contrast(atmosphere_csv)
    arrival_audit = output / "three_box_arrival_map_values.csv"
    sst_audit = output / "mjj_sst_contrast_values.csv"
    arrival.to_csv(arrival_audit, index=False)
    sst.to_csv(sst_audit, index=False)

    map_pngs: list[Path] = []
    map_pdfs: list[Path] = []
    for event_year in EVENT_YEARS:
        png = output / f"three_box_arrival_{event_year}.png"
        pdf = output / f"three_box_arrival_{event_year}.pdf"
        plot_arrival_map(arrival, event_year, png, pdf)
        map_pngs.append(png)
        map_pdfs.append(pdf)

    coupling_png = output / "coupling_contrast_1997_2015_2023.png"
    coupling_pdf = output / "coupling_contrast_1997_2015_2023.pdf"
    plot_coupling_contrast(sst, coupling_csv, coupling_png, coupling_pdf)

    return PlotOutputs(
        map_pngs=tuple(map_pngs),
        coupling_png=coupling_png,
        pdfs=(*map_pdfs, coupling_pdf),
        arrival_audit_csv=arrival_audit,
        mjj_sst_audit_csv=sst_audit,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--three-box-csv", type=Path, required=True)
    parser.add_argument("--atmosphere-csv", type=Path, required=True)
    parser.add_argument("--coupling-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    outputs = run_pipeline(
        three_box_csv=args.three_box_csv,
        atmosphere_csv=args.atmosphere_csv,
        coupling_csv=args.coupling_csv,
        output_dir=args.output_dir,
    )
    for path in (*outputs.map_pngs, outputs.coupling_png, *outputs.pdfs):
        print(path)


if __name__ == "__main__":
    main()
