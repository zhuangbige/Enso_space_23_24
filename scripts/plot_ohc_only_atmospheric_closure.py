#!/usr/bin/env python3
"""Plot the FEP–OHC–atmosphere sequence without D20 or threshold diagnostics."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from analyze_jiang_soda3_transition import (
    EVENTS,
    MONTH_LABELS,
    MONTHS,
    OHC_FILE,
    longitude_label,
    rounded_limit,
    setup_style,
    weighted_lat_mean,
)
from add_atmospheric_closure_to_soda3_transition import (
    ATMOS_COLOR,
    ATMOS_FILE,
    EXTENDED_CSV,
    event_field,
)


OUT = (
    ROOT
    / "outputs/research_2026/ohc_only_three_questions/"
    "Fig04_OHC_atmospheric_closure.png"
)


def format_hov_axis(axis: plt.Axes, *, row: int, show_months: bool) -> None:
    axis.set_xlim(130, 280)
    axis.set_ylim(5, 0)
    axis.set_yticks(np.arange(6))
    axis.set_yticklabels(MONTH_LABELS if show_months else [])
    ticks = [130, 160, 180, 220, 250, 270, 280]
    axis.set_xticks(
        ticks,
        [longitude_label(value) for value in ticks] if row == 2 else [],
    )
    axis.tick_params(axis="x", rotation=25)
    for boundary in (180, 220, 270):
        axis.axvline(boundary, color="0.25", lw=0.6, ls=":")


def add_atmospheric_line(axis: plt.Axes, month: int, *, vertical: bool) -> None:
    coordinate = month if vertical else month - 1
    if vertical:
        axis.axvline(
            coordinate,
            color=ATMOS_COLOR,
            lw=1.25,
            ls=(0, (1.5, 1.5)),
            zorder=8,
        )
    else:
        axis.axhline(
            coordinate,
            color=ATMOS_COLOR,
            lw=1.25,
            ls=(0, (1.5, 1.5)),
            zorder=8,
        )


def main() -> None:
    setup_style()
    fep = pd.read_csv(EXTENDED_CSV).rename(columns={"event_year": "year"})
    with xr.open_dataset(OHC_FILE, chunks=None, engine="h5netcdf") as ds:
        ohc = (
            ds["ohc_300m_anomaly_detrended"]
            .where(ds.time.dt.month.isin(MONTHS), drop=True)
            .sel(lat=slice(-5.0, 5.0))
            .load()
        )
    with xr.open_dataset(ATMOS_FILE, chunks=None, engine="h5netcdf") as ds:
        atmosphere = ds.load()

    zonal = {
        "ohc": weighted_lat_mean(ohc) / 1.0e9,
        "u850": weighted_lat_mean(atmosphere["u850_anomaly_detrended"]),
        "olr": weighted_lat_mean(atmosphere["olr_anomaly_detrended"]),
    }
    event_arrays = {
        name: {year: event_field(field, year) for year in EVENTS}
        for name, field in zonal.items()
    }
    step = {"ohc": 0.5, "u850": 1.0, "olr": 5.0}
    floor = {"ohc": 2.0, "u850": 3.0, "olr": 20.0}
    ceiling = {"ohc": 6.0, "u850": 10.0, "olr": 60.0}
    limits = {
        name: min(
            ceiling[name],
            rounded_limit(
                np.concatenate([item.values.ravel() for item in by_year.values()]),
                step[name],
                floor[name],
            ),
        )
        for name, by_year in event_arrays.items()
    }
    levels = {
        name: np.linspace(-limit, limit, 17)
        for name, limit in limits.items()
    }

    event_fep = fep.loc[fep["year"].isin(EVENTS) & fep["month"].isin(MONTHS)]
    sst_values = event_fep[
        ["fep_total_ssta_c", "fep_nino34_related_c", "fep_residual_c"]
    ].to_numpy()
    sst_limit = min(3.5, rounded_limit(sst_values, 0.5, 1.5))
    closure = (
        pd.read_csv(EXTENDED_CSV)
        .groupby("event_year")["atmospheric_closure_month"]
        .first()
        .astype(int)
        .to_dict()
    )

    fig, axes = plt.subplots(
        3,
        4,
        figsize=(15.7, 9.7),
        gridspec_kw={"width_ratios": [1.02, 1.22, 1.22, 1.22]},
    )
    fig.subplots_adjust(
        left=0.06,
        right=0.991,
        top=0.865,
        bottom=0.19,
        hspace=0.28,
        wspace=0.18,
    )

    meshes: dict[str, object] = {}
    field_order = ("ohc", "u850", "olr")
    for row, year in enumerate(EVENTS):
        line_axis = axes[row, 0]
        event = event_fep.loc[event_fep["year"].eq(year)].sort_values("month")
        x = event["month"].to_numpy()
        line_axis.plot(
            x,
            event["fep_total_ssta_c"],
            color="#222222",
            lw=2.0,
            marker="o",
            ms=4.0,
        )
        line_axis.plot(
            x,
            event["fep_nino34_related_c"],
            color="#D55E00",
            lw=1.55,
            marker="s",
            ms=3.4,
        )
        line_axis.plot(
            x,
            event["fep_residual_c"],
            color="#0072B2",
            lw=1.55,
            marker="^",
            ms=3.6,
        )
        line_axis.axhline(0, color="0.45", lw=0.75)
        line_axis.set_xlim(0.75, 6.25)
        line_axis.set_ylim(-sst_limit, sst_limit)
        line_axis.set_xticks(MONTHS, MONTH_LABELS if row == 2 else [])
        line_axis.set_ylabel("SST anomaly (°C)")
        line_axis.grid(axis="y", color="0.89", lw=0.65)
        line_axis.text(
            0.025,
            0.92,
            str(year),
            transform=line_axis.transAxes,
            ha="left",
            va="top",
            fontsize=10.5,
            weight="bold",
            color="#263746",
        )
        add_atmospheric_line(line_axis, closure[year], vertical=True)

        for column, name in enumerate(field_order, start=1):
            axis = axes[row, column]
            data = event_arrays[name][year]
            mesh = axis.contourf(
                data.lon,
                np.arange(6),
                data.values,
                levels=levels[name],
                cmap="RdBu_r",
                extend="both",
            )
            axis.contour(
                data.lon,
                np.arange(6),
                data.values,
                levels=[0],
                colors="0.20",
                linewidths=0.7,
            )
            meshes[name] = mesh
            format_hov_axis(axis, row=row, show_months=column == 1)
            add_atmospheric_line(axis, closure[year], vertical=False)

    titles = (
        "(a) FEP decomposition",
        "(b) 0–300 m OHC",
        "(c) ERA5 u850",
        "(d) ERA5 OLR",
    )
    for column, title in enumerate(titles):
        axes[0, column].set_title(title, weight="bold")
    axes[2, 0].set_xlabel("Development-year month")
    for column in range(1, 4):
        axes[2, column].set_xlabel("Longitude")
    for row in range(3):
        axes[row, 1].set_ylabel("Calendar month")

    handles = [
        Line2D([0], [0], color="#222222", marker="o", lw=2.0, ms=4, label="Total FEP"),
        Line2D([0], [0], color="#D55E00", marker="s", lw=1.55, ms=3.5, label="Niño-3.4-related"),
        Line2D([0], [0], color="#0072B2", marker="^", lw=1.55, ms=3.7, label="Residual FEP"),
        Line2D([0], [0], color=ATMOS_COLOR, ls=(0, (1.5, 1.5)), lw=1.4, label="Atmospheric closure"),
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.913),
        ncol=4,
        frameon=False,
        handlelength=2.4,
        columnspacing=1.55,
    )

    colorbar_labels = {
        "ohc": "OHC (GJ m$^{-2}$)",
        "u850": "u850 (m s$^{-1}$; + westerly)",
        "olr": "OLR (W m$^{-2}$; − convection)",
    }
    fig.canvas.draw()
    for column, name in enumerate(field_order, start=1):
        position = axes[2, column].get_position()
        color_axis = fig.add_axes([position.x0, 0.092, position.width, 0.017])
        colorbar = fig.colorbar(meshes[name], cax=color_axis, orientation="horizontal")
        colorbar.set_ticks(np.linspace(-limits[name], limits[name], 5))
        colorbar.set_label(colorbar_labels[name])

    fig.suptitle(
        "FEP warming, upper-ocean heat redistribution, and atmospheric closure",
        fontsize=14.3,
        weight="bold",
        y=0.973,
    )
    fig.text(
        0.5,
        0.013,
        "OISST FEP: 1982–2024; SODA3.15.2 OHC and ERA5 u850/OLR: 1980–2024 same-month detrended anomalies; "
        "all Hovmöller fields are 5°S–5°N means. Purple line: first of two months with CWP u850 > 0 and "
        "central-Pacific OLR < 0 (operational atmospheric-closure marker).",
        ha="center",
        va="bottom",
        fontsize=7.25,
        color="0.31",
        wrap=True,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()
