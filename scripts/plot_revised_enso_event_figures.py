#!/usr/bin/env python3
"""Create revised ENSO event comparison figures with wider strip layouts."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


BASELINE_START = 1980
BASELINE_END = 2014
BASELINE_TAG = "1980_2014"
OUT_DIR = ROOT / "outputs/research_2026/revised_event_figures"
INPUT_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
NINO3_EVENT_CSV = ROOT / "data/derived/research_2026/oisst_nino3_jun_jan_to_2025.csv"

EVENTS = {
    "2015": {
        "label": "2015/16 development year",
        "panel_year": "2015",
        "npz": INPUT_DIR / "monthly_2015_detrended_fields_1980_2014.npz",
    },
    "2023": {
        "label": "2023/24 development year",
        "panel_year": "2023",
        "npz": INPUT_DIR / "monthly_2023_detrended_fields_1980_2014.npz",
    },
    "2026": {
        "label": "2026 January-June",
        "panel_year": "2026",
        "npz": INPUT_DIR / "monthly_2026_detrended_fields_1980_2014.npz",
    },
}

CLASSIC_REFERENCE_YEARS = [1982, 1997]
EXTENDED_SENSITIVITY_YEARS = [2002, 2009]
ALL_REFERENCE_YEARS = CLASSIC_REFERENCE_YEARS + EXTENDED_SENSITIVITY_YEARS
REFERENCE_EVENT_LABELS = {
    1982: "1982/83",
    1997: "1997/98",
    2002: "2002/03",
    2009: "2009/10",
}
MONTH_LABELS = ["January", "February", "March", "April", "May", "June"]
SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
D20_AXIS_LIMIT_M = 60.0
U850_AXIS_LIMIT_MS = 12.0


def load_monthly_module():
    path = ROOT / "scripts/plot_2026_monthly_sst_precip_d20_wind.py"
    spec = importlib.util.spec_from_file_location("monthly_panel_builder", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["monthly_panel_builder"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 320,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 12.6,
            "axes.titlesize": 13.0,
            "axes.labelsize": 11.6,
            "xtick.labelsize": 10.2,
            "ytick.labelsize": 10.2,
            "axes.linewidth": 0.95,
            "axes.unicode_minus": False,
        }
    )


def format_lon(value: float) -> str:
    lon = value % 360
    if np.isclose(lon, 0):
        return "0"
    if np.isclose(lon, 180):
        return "180"
    if lon < 180:
        return f"{lon:g}E"
    return f"{360 - lon:g}W"


def format_lat(value: float) -> str:
    if np.isclose(value, 0):
        return "Eq"
    return f"{abs(value):g}{'N' if value > 0 else 'S'}"


def format_map_axes(
    ax: plt.Axes,
    *,
    show_ylabel: bool,
    show_xlabel: bool = True,
) -> None:
    xticks = [120, 160, 200, 240, 280]
    yticks = [-30, 0, 30]
    ax.set_xlim(120, 280)
    ax.set_ylim(-30, 30)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(tick) for tick in xticks])
    ax.set_yticks(yticks)
    ax.set_yticklabels([format_lat(tick) for tick in yticks] if show_ylabel else [])
    ax.axhline(0, color="0.2", lw=0.65)
    ax.set_xlabel("Longitude" if show_xlabel else "")
    if show_ylabel:
        ax.set_ylabel("Latitude")


def format_precip_map_axes(ax: plt.Axes, *, show_ylabel: bool) -> None:
    """Use a compact, paper-style strip layout for rainfall-wind panels."""
    xticks = [120, 180, 240]
    yticks = [-30, 0, 30]
    ax.set_xlim(120, 280)
    ax.set_ylim(-30, 30)
    ax.set_xticks(xticks)
    ax.set_xticklabels([format_lon(tick) for tick in xticks], fontsize=13.0)
    ax.set_yticks(yticks)
    ax.set_yticklabels([format_lat(tick) for tick in yticks] if show_ylabel else [], fontsize=13.0)
    ax.axhline(0, color="0.28", lw=0.72, zorder=3)
    ax.tick_params(length=3.6, width=0.9, pad=2.2)
    for spine in ax.spines.values():
        spine.set_linewidth(0.9)
        spine.set_color("0.18")


def add_boxes(ax: plt.Axes, *, include_nino: bool = True) -> None:
    boxes = [
        ("CWP", -5, 5, 160, 220),
        ("CP", -5, 5, 180, 220),
        ("EP", -5, 5, 220, 260),
        ("FEP", -5, 5, 270, 280),
        ("Niño-3.4", -5, 5, 190, 240),
        ("Niño-3", -5, 5, 210, 270),
    ]
    for label, lat0, lat1, lon0, lon1 in boxes:
        if not include_nino and label.startswith("Niño"):
            continue
        ax.plot([lon0, lon1, lon1, lon0, lon0], [lat0, lat0, lat1, lat1, lat0], color="0.12", lw=0.85)
        dx, dy = {
            "FEP": (-10.0, 1.1),
            "Niño-3": (14.0, -5.6),
            "Niño-3.4": (1.1, 1.1),
        }.get(label, (1.1, 1.1))
        y_anchor = lat1 if dy >= 0 else lat0
        ax.text(lon0 + dx, y_anchor + dy, label, fontsize=8.1, color="0.10")


def add_precip_boxes(ax: plt.Axes) -> None:
    """Retain only the two non-overlapping rainfall-response boxes."""
    for label, lon0, lon1, color in [
        ("CP", 180, 220, "#111111"),
        ("EP", 220, 260, "#b0185b"),
    ]:
        ax.plot(
            [lon0, lon1, lon1, lon0, lon0],
            [-5, -5, 5, 5, -5],
            color=color,
            lw=1.25,
            zorder=6,
        )
        ax.text(
            (lon0 + lon1) / 2,
            7.0,
            label,
            ha="center",
            va="bottom",
            fontsize=10.8,
            weight="bold",
            color=color,
            bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.76},
            zorder=7,
        )


def add_vectors(
    ax: plt.Axes,
    lon: np.ndarray,
    lat: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    *,
    key: bool,
    emphasis: str,
):
    if emphasis == "precip":
        x = lon[::10]
        y = lat[::8]
        uu = u[::8, ::10]
        vv = v[::8, ::10]
        ax.quiver(
            x,
            y,
            uu,
            vv,
            color="white",
            pivot="middle",
            width=0.0058,
            headwidth=4.0,
            headlength=5.0,
            headaxislength=4.5,
            scale=48,
            alpha=0.74,
            zorder=4,
        )
        color = "#111111"
        width = 0.00335
    else:
        x = lon[::7]
        y = lat[::5]
        uu = u[::5, ::7]
        vv = v[::5, ::7]
        ax.quiver(
            x,
            y,
            uu,
            vv,
            color="white",
            pivot="middle",
            width=0.0052,
            headwidth=3.8,
            headlength=4.7,
            headaxislength=4.3,
            scale=47,
            alpha=0.72,
            zorder=4,
        )
        color = "#111111"
        width = 0.0031
    q = ax.quiver(
        x,
        y,
        uu,
        vv,
        color=color,
        pivot="middle",
        width=width,
        headwidth=3.6,
        headlength=4.7,
        headaxislength=4.3,
        scale=47 if emphasis != "precip" else 48,
        zorder=5,
    )
    if key and emphasis != "precip":
        add_panel_vector_key(ax, q)
    return q


def add_panel_vector_key(
    ax: plt.Axes,
    q,
    *,
    value: float = 4.0,
    x: float = 0.902,
    y: float = 0.17,
    fontsize: float = 9.5,
) -> None:
    """Place a paper-style wind-vector reference inside one panel.

    The lower-right reference area is first whitened, matching the supplied
    paper example, then the arrow, magnitude, and unit are drawn on top.
    """
    key_background = Rectangle(
        (0.81, 0.015),
        0.185,
        0.255,
        transform=ax.transAxes,
        facecolor="white",
        edgecolor="0.28",
        linewidth=0.65,
        zorder=8,
    )
    ax.add_patch(key_background)
    key_artist = ax.quiverkey(
        q,
        x,
        y,
        value,
        rf"{value:g} m s$^{{-1}}$",
        labelpos="S",
        coordinates="axes",
        labelsep=0.035,
        fontproperties={"size": fontsize},
    )
    key_artist.set_zorder(10)


def save(fig: plt.Figure, stem: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight", pad_inches=0.08)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.08)
    print(png)
    print(pdf)
    return png, pdf


def load_npz(path: Path) -> dict[str, object]:
    z = np.load(path)
    return {key: z[key] for key in z.files}


def selected_el_nino_years() -> list[int]:
    df = pd.read_csv(NINO3_EVENT_CSV)
    years = df.loc[
        (df["event_year"].between(1982, 2014))
        & (df["nino3_jun_jan_anomaly"] >= 0.5),
        "event_year",
    ].astype(int)
    return years.tolist()


def ensure_event_fields() -> None:
    module = load_monthly_module()
    for key, event in EVENTS.items():
        needs_build = not event["npz"].exists()
        if not needs_build:
            with np.load(event["npz"]) as current:
                needs_build = len(current["month_numbers"]) != len(MONTH_LABELS)
        if needs_build:
            module.configure_run(
                int(key),
                event["label"],
                None,
                BASELINE_START,
                BASELINE_END,
            )
            module.build_fields()
    for year in ALL_REFERENCE_YEARS:
        npz = INPUT_DIR / f"monthly_{year}_detrended_fields_{BASELINE_TAG}.npz"
        needs_build = not npz.exists()
        if not needs_build:
            with np.load(npz) as current:
                needs_build = len(current["month_numbers"]) != len(MONTH_LABELS)
        if needs_build:
            module.configure_run(
                year,
                f"El Niño {REFERENCE_EVENT_LABELS.get(year, str(year))} development year",
                "outputs/research_2026/revised_event_figures/intermediate",
                BASELINE_START,
                BASELINE_END,
            )
            module.build_fields()


def build_composite_fields(years: list[int]) -> dict[str, object]:
    module = load_monthly_module()
    fields = []
    for year in years:
        npz = INPUT_DIR / f"monthly_{year}_detrended_fields_{BASELINE_TAG}.npz"
        if not npz.exists():
            module.configure_run(
                year,
                f"El Niño {year}",
                "outputs/research_2026/revised_event_figures/intermediate",
                BASELINE_START,
                BASELINE_END,
            )
            module.build_fields()
        fields.append(load_npz(npz))
    template = fields[0]
    composite: dict[str, object] = {}
    for key, value in template.items():
        if key in {"sst", "u850", "v850", "precip", "d20"}:
            composite[key] = np.nanmean(np.stack([np.asarray(item[key], dtype=float) for item in fields], axis=0), axis=0).astype(
                np.float32
            )
        elif key == "months":
            composite[key] = np.asarray(MONTH_LABELS)
        elif key == "month_numbers":
            composite[key] = np.arange(1, 7)
        else:
            composite[key] = value
    composite["composite_years"] = np.asarray(years, dtype=np.int16)
    composite["method"] = np.asarray(
        "January-June development-year composite mean of the 1982/83 and 1997/98 main classic strong-event references after same-month "
        "climatology and linear trend removal. Target events, including 2015/16, are excluded."
    )
    out = INPUT_DIR / f"monthly_classic_strong_reference_composite_detrended_fields_{BASELINE_TAG}.npz"
    np.savez_compressed(out, **composite)
    print(out)
    return composite


def load_reference_event_fields(years: list[int]) -> list[tuple[int, str, dict[str, object]]]:
    events = []
    for year in years:
        events.append(
            (
                year,
                REFERENCE_EVENT_LABELS.get(year, str(year)),
                load_npz(INPUT_DIR / f"monthly_{year}_detrended_fields_{BASELINE_TAG}.npz"),
            )
        )
    return events


def plot_monthly_map_group(
    fields: dict[str, object],
    *,
    variable: str,
    title: str,
    panel_year: str,
    cmap: str,
    vmin: float,
    vmax: float,
    colorbar_label: str,
    stem: str,
    composite_years: list[int] | None = None,
) -> None:
    lon = np.asarray(fields["lon"], dtype=float)
    lat = np.asarray(fields["lat"], dtype=float)
    u = np.asarray(fields["u850"], dtype=float)
    v = np.asarray(fields["v850"], dtype=float)
    if variable == "sst":
        xlon = np.asarray(fields["sst_lon"], dtype=float)
        ylat = np.asarray(fields["sst_lat"], dtype=float)
    else:
        xlon = lon
        ylat = lat
    data = np.asarray(fields[variable], dtype=float)
    nmonths = len(SHORT_MONTHS)
    # Keep the figure at full manuscript width while using a moderately wide
    # 2 x 3 layout.  A 1 x 6 strip makes the individual maps too small when
    # the image is inserted into a portrait report at 6.35 inches wide.
    fig, axes = plt.subplots(2, 3, figsize=(13.6, 6.05), constrained_layout=True)
    axes_flat = np.asarray(axes).ravel()
    fig.suptitle(title, fontsize=17.0, weight="bold", y=1.015)
    mesh = None
    vector_ref = None
    for i, ax in enumerate(axes_flat):
        row, col = divmod(i, 3)
        if variable == "precip":
            levels = np.linspace(vmin, vmax, 25)
            mesh = ax.contourf(
                xlon,
                ylat,
                data[i],
                levels=levels,
                cmap=cmap,
                extend="both",
                antialiased=True,
            )
            vector_ref = add_vectors(ax, lon, lat, u[i], v[i], key=False, emphasis="precip")
            add_panel_vector_key(ax, vector_ref, fontsize=9.8)
            format_precip_map_axes(ax, show_ylabel=(col == 0))
            if row == 0:
                ax.tick_params(labelbottom=False)
            ax.set_box_aspect(0.375)
            add_precip_boxes(ax)
            ax.set_title(
                f"{SHORT_MONTHS[i]} {panel_year}" if composite_years is None else f"{SHORT_MONTHS[i]} composite",
                fontsize=14.0,
                weight="bold",
                pad=6,
            )
        else:
            mesh = ax.pcolormesh(xlon, ylat, data[i], cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
            vector_ref = add_vectors(ax, lon, lat, u[i], v[i], key=False, emphasis="sst")
            add_panel_vector_key(ax, vector_ref, fontsize=9.8)
            format_map_axes(ax, show_ylabel=(col == 0), show_xlabel=(row == 1))
            if row == 0:
                ax.tick_params(labelbottom=False)
            ax.set_box_aspect(0.375)
            add_boxes(ax, include_nino=True)
            if composite_years is None:
                ax.set_title(f"{SHORT_MONTHS[i]} {panel_year}", fontsize=14.0, weight="bold")
            else:
                ax.set_title(f"{SHORT_MONTHS[i]} composite", fontsize=14.0, weight="bold")
    assert mesh is not None
    if variable == "precip":
        assert vector_ref is not None
        cbar = fig.colorbar(
            mesh,
            ax=axes_flat.tolist(),
            orientation="horizontal",
            ticks=np.arange(vmin, vmax + 0.1, 3.0),
            shrink=0.64,
            pad=0.045,
            aspect=42,
        )
        cbar.ax.tick_params(labelsize=12.3, length=3.2, width=0.8, pad=2)
        cbar.set_label(colorbar_label, fontsize=13.2, labelpad=3)
        cbar.outline.set_linewidth(0.85)
    else:
        cbar = fig.colorbar(
            mesh,
            ax=axes_flat.tolist(),
            orientation="horizontal",
            label=colorbar_label,
            shrink=0.64,
            pad=0.045,
            aspect=42,
        )
        cbar.ax.tick_params(labelsize=11.4)
        cbar.set_label(colorbar_label, fontsize=12.4)
    if composite_years is None:
        if variable == "sst":
            note = (
                f"Monthly detrended anomalies. ERA5 wind baseline {fields['era5_baseline_used']}; "
                f"OISST baseline {fields['sst_baseline_used']}. "
                r"Each panel's wind-vector reference is 4 m s$^{-1}$."
            )
        else:
            note = (
                f"Monthly detrended anomalies. ERA5 precipitation/wind baseline {fields['era5_baseline_used']}. "
                r"Each panel's wind-vector reference is 4 m s$^{-1}$."
            )
    else:
        years = ", ".join(str(y) for y in composite_years)
        if variable == "sst":
            note = (
                f"Composite years: {years}. Same monthly anomaly and detrending method; "
                f"ERA5 wind baseline {BASELINE_START}-{BASELINE_END}; OISST baseline 1982-{BASELINE_END}. "
                r"Each panel's wind-vector reference is 4 m s$^{-1}$."
            )
        else:
            note = (
                f"Composite years: {years}. Same monthly anomaly and detrending method; "
                f"ERA5 precipitation/wind baseline {BASELINE_START}-{BASELINE_END}. "
                r"Each panel's wind-vector reference is 4 m s$^{-1}$."
            )
    fig.text(0.01, -0.025, note, fontsize=9.6, color="0.28")
    save(fig, stem)
    plt.close(fig)


def plot_selected_event_map_grid(
    reference_events: list[tuple[int, str, dict[str, object]]],
    *,
    variable: str,
    title: str,
    cmap: str,
    vmin: float,
    vmax: float,
    colorbar_label: str,
    stem: str,
    group_description: str,
) -> None:
    nrows = len(reference_events)
    nmonths = len(SHORT_MONTHS)
    fig, axes = plt.subplots(nrows, nmonths, figsize=(22.0, 2.85 * nrows + 0.35), constrained_layout=True, squeeze=False)
    fig.suptitle(title, weight="bold", y=1.03)
    mesh = None
    vector_ref = None
    for row_idx, (_year, event_label, fields) in enumerate(reference_events):
        lon = np.asarray(fields["lon"], dtype=float)
        lat = np.asarray(fields["lat"], dtype=float)
        u = np.asarray(fields["u850"], dtype=float)
        v = np.asarray(fields["v850"], dtype=float)
        if variable == "sst":
            xlon = np.asarray(fields["sst_lon"], dtype=float)
            ylat = np.asarray(fields["sst_lat"], dtype=float)
        else:
            xlon = lon
            ylat = lat
        data = np.asarray(fields[variable], dtype=float)
        for col_idx, ax in enumerate(axes[row_idx]):
            mesh = ax.pcolormesh(xlon, ylat, data[col_idx], cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
            vector_ref = add_vectors(
                ax,
                lon,
                lat,
                u[col_idx],
                v[col_idx],
                key=False,
                emphasis="precip" if variable == "precip" else "sst",
            )
            add_panel_vector_key(ax, vector_ref, fontsize=7.8)
            format_map_axes(ax, show_ylabel=(col_idx == 0))
            add_boxes(ax, include_nino=variable == "sst")
            if row_idx == 0:
                ax.set_title(SHORT_MONTHS[col_idx], fontsize=12.8, weight="bold")
            if row_idx < nrows - 1:
                ax.set_xlabel("")
                ax.tick_params(labelbottom=False)
            ax.text(
                0.02,
                0.93,
                event_label,
                transform=ax.transAxes,
                fontsize=10.1,
                weight="bold",
                color="0.08",
                va="top",
                bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": 0.78},
                zorder=8,
            )
    assert mesh is not None
    cbar = fig.colorbar(mesh, ax=axes.ravel().tolist(), label=colorbar_label, shrink=0.92, pad=0.006)
    cbar.ax.tick_params(labelsize=10.0)
    cbar.set_label(colorbar_label, fontsize=11.2)
    years = ", ".join(label for _year, label, _fields in reference_events)
    if variable == "sst":
        note = (
            f"{group_description}, plotted individually, not averaged: {years}. "
            f"Monthly detrended anomalies; ERA5 wind baseline {BASELINE_START}-{BASELINE_END}; "
            f"OISST baseline 1982-{BASELINE_END}. "
            r"Each panel's wind-vector reference is 4 m s$^{-1}$."
        )
    else:
        note = (
            f"{group_description}, plotted individually, not averaged: {years}. "
            f"Monthly detrended anomalies; ERA5 precipitation/wind baseline {BASELINE_START}-{BASELINE_END}. "
            r"Each panel's wind-vector reference is 4 m s$^{-1}$."
        )
    fig.text(0.01, -0.02, note, fontsize=10.0, color="0.28")
    save(fig, stem)
    plt.close(fig)


def weighted_equatorial_mean(field: np.ndarray, lat: np.ndarray) -> np.ndarray:
    idx = np.where((lat >= -5) & (lat <= 5))[0]
    weights = np.cos(np.deg2rad(lat[idx])).astype(float)
    return np.average(field[:, idx, :], axis=1, weights=weights)


def interp_monthly_to_lons(field: np.ndarray, src_lon: np.ndarray, dst_lon: np.ndarray) -> np.ndarray:
    return np.asarray([np.interp(dst_lon, src_lon, row) for row in field])


def plot_d20_wind(
    fields: dict[str, object],
    *,
    title: str,
    panel_year: str,
    stem: str,
    composite_years: list[int] | None = None,
) -> None:
    lon = np.asarray(fields["lon"], dtype=float)
    lat = np.asarray(fields["lat"], dtype=float)
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    d20 = np.asarray(fields["d20"], dtype=float)
    u_eq = weighted_equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
    u_eq_on_d20 = interp_monthly_to_lons(u_eq, lon, d20_lon)
    d20_lim = D20_AXIS_LIMIT_M
    wind_lim = U850_AXIS_LIMIT_MS

    fig, axes = plt.subplots(2, 3, figsize=(13.6, 6.05), sharex=True, sharey=True, constrained_layout=True)
    axes_flat = np.asarray(axes).ravel()
    fig.suptitle(title, fontsize=17.0, weight="bold", y=0.99)
    layout_engine = fig.get_layout_engine()
    if layout_engine is not None:
        layout_engine.set(rect=(0.0, 0.0, 1.0, 0.93))
    for i, (ax, label) in enumerate(zip(axes_flat, SHORT_MONTHS)):
        row, col = divmod(i, 3)
        colors = np.where(d20[i] >= 0, "#b84b40", "#2f6fab")
        ax.bar(d20_lon, d20[i], width=4.0, color=colors, alpha=0.78, edgecolor="none")
        ax.axhline(0, color="0.25", lw=0.8)
        ax.set_ylim(-d20_lim, d20_lim)
        ax.set_ylabel("D20 (m)" if col == 0 else "", fontsize=11.5)
        panel_label = f"{label} {panel_year}" if composite_years is None else f"{label} composite"
        ax.text(
            0.012,
            0.965,
            panel_label,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=12.6,
            weight="bold",
            bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.78},
            zorder=8,
        )
        ax2 = ax.twinx()
        ax2.plot(d20_lon, u_eq_on_d20[i], color="#111111", lw=1.7)
        ax2.fill_between(d20_lon, 0, u_eq_on_d20[i], color="#111111", alpha=0.12)
        ax2.axhline(0, color="0.45", lw=0.6, ls="--")
        ax2.set_ylim(-wind_lim, wind_lim)
        ax2.set_ylabel("u850 (m/s)" if col == 2 else "", fontsize=11.5)
        if col != 2:
            ax2.tick_params(labelright=False)
        ax.tick_params(labelsize=10.2)
        ax2.tick_params(labelsize=10.2)
        for x, text in [(160, "CWP"), (180, "Date line"), (220, "CP"), (260, "EP"), (275, "FEP")]:
            ax.axvline(x, color="0.35", lw=0.52, ls="--")
            if i == 0:
                ax.text(x + 1, d20_lim * 0.62, text, fontsize=8.8, color="0.25")
        if row == 0:
            ax.tick_params(labelbottom=False)
    axes_flat[-1].set_xlim(130, 275)
    # Keep the date line as the central reference tick.  The former 170E tick
    # was only 10 degrees away and overlapped with 180 in the 2 x 3 layout.
    ticks = [130, 150, 180, 200, 220, 240, 260, 275]
    for ax in axes[1]:
        ax.set_xticks(ticks)
        ax.set_xticklabels([format_lon(tick) for tick in ticks], fontsize=9.2)
        ax.set_xlabel("Longitude along equator", fontsize=10.6)
    if composite_years is None:
        note = (
            f"D20: ORAS5 equatorial 20 deg C isotherm depth, detrended against {BASELINE_START}-{BASELINE_END}. "
            "Wind: ERA5 u850 averaged over 5S-5N. Positive u850 is westerly."
        )
    else:
        years = ", ".join(str(y) for y in composite_years)
        note = (
            f"Composite years: {years}. D20 and ERA5 u850 use the same monthly anomaly and detrending method. "
            "Positive u850 is westerly; positive D20 is deeper thermocline."
        )
    fig.text(0.01, -0.025, note, fontsize=9.6, color="0.28")
    save(fig, stem)
    plt.close(fig)


def plot_selected_event_d20_grid(
    reference_events: list[tuple[int, str, dict[str, object]]],
    *,
    title: str,
    stem: str,
    group_description: str,
) -> None:
    prepared = []
    d20_abs = 0.0
    u_abs = 0.0
    for _year, event_label, fields in reference_events:
        lon = np.asarray(fields["lon"], dtype=float)
        lat = np.asarray(fields["lat"], dtype=float)
        d20_lon = np.asarray(fields["d20_lon"], dtype=float)
        d20 = np.asarray(fields["d20"], dtype=float)
        u_eq = weighted_equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
        u_eq_on_d20 = interp_monthly_to_lons(u_eq, lon, d20_lon)
        d20_abs = max(d20_abs, float(np.nanmax(np.abs(d20))))
        u_abs = max(u_abs, float(np.nanmax(np.abs(u_eq_on_d20))))
        prepared.append((event_label, d20_lon, d20, u_eq_on_d20))
    d20_lim = D20_AXIS_LIMIT_M
    wind_lim = U850_AXIS_LIMIT_MS

    nrows = len(prepared)
    nmonths = len(SHORT_MONTHS)
    fig, axes = plt.subplots(nrows, nmonths, figsize=(22.0, 2.25 * nrows + 0.35), sharex=True, sharey=True, constrained_layout=True)
    axes = np.asarray(axes).reshape(nrows, nmonths)
    fig.suptitle(title, weight="bold", y=1.045)
    for row_idx, (event_label, d20_lon, d20, u_eq_on_d20) in enumerate(prepared):
        for col_idx, ax in enumerate(axes[row_idx]):
            colors = np.where(d20[col_idx] >= 0, "#b84b40", "#2f6fab")
            ax.bar(d20_lon, d20[col_idx], width=4.0, color=colors, alpha=0.78, edgecolor="none")
            ax.axhline(0, color="0.25", lw=0.78)
            ax.set_ylim(-d20_lim, d20_lim)
            for x in (160, 180, 220, 260):
                ax.axvline(x, color="0.38", lw=0.45, ls="--")
            if row_idx == 0:
                ax.set_title(SHORT_MONTHS[col_idx], fontsize=12.8, weight="bold")
            if col_idx == 0:
                ax.set_ylabel(f"{event_label}\nD20 (m)", fontsize=10.2)
            else:
                ax.tick_params(labelleft=False)
            if row_idx < nrows - 1:
                ax.tick_params(labelbottom=False)
            ax2 = ax.twinx()
            ax2.plot(d20_lon, u_eq_on_d20[col_idx], color="#111111", lw=1.45)
            ax2.fill_between(d20_lon, 0, u_eq_on_d20[col_idx], color="#111111", alpha=0.12)
            ax2.axhline(0, color="0.45", lw=0.55, ls="--")
            ax2.set_ylim(-wind_lim, wind_lim)
            if col_idx == nmonths - 1:
                ax2.set_ylabel("u850 (m/s)", fontsize=10.2)
            else:
                ax2.tick_params(labelright=False)
            ax.tick_params(labelsize=9.0)
            ax2.tick_params(labelsize=9.0)
    for ax in axes[-1]:
        ax.set_xlim(130, 275)
        ticks = [130, 150, 180, 200, 220, 240, 260, 275]
        ax.set_xticks(ticks)
        ax.set_xticklabels([format_lon(tick) for tick in ticks])
        ax.set_xlabel("Longitude")
    years = ", ".join(label for label, _d20_lon, _d20, _u in prepared)
    note = (
        f"{group_description}, plotted individually, not averaged: {years}. "
        f"D20: ORAS5 equatorial 20 deg C isotherm depth, detrended against {BASELINE_START}-{BASELINE_END}. "
        "Wind: ERA5 u850 averaged over 5S-5N; positive u850 is westerly."
    )
    fig.text(0.01, -0.02, note, fontsize=10.0, color="0.28")
    save(fig, stem)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create target-event and group-separated ENSO development-phase figures.")
    parser.add_argument(
        "--target-precip-only",
        action="store_true",
        help="Regenerate only the three target-event precipitation-wind strip figures.",
    )
    parser.add_argument(
        "--targets-only",
        action="store_true",
        help="Regenerate the SST-wind, precipitation-wind, and D20-wind figures for the three target events only.",
    )
    parser.add_argument(
        "--groups-only",
        action="store_true",
        help="Regenerate only the historical reference/sensitivity groups and leave the target-event figures untouched.",
    )
    args = parser.parse_args()
    setup_style()
    ensure_event_fields()
    if args.target_precip_only:
        for key, event in EVENTS.items():
            fields = load_npz(event["npz"])
            plot_monthly_map_group(
                fields,
                variable="precip",
                title=f"{event['label']}: precipitation and 850-hPa wind anomalies",
                panel_year=event["panel_year"],
                cmap="BrBG",
                vmin=-12.0,
                vmax=12.0,
                colorbar_label=r"ERA5 precipitation anomaly (mm day$^{-1}$)",
                stem=f"fig_{key}_paperstyle_era5_precip_u850_strip_detrended_{BASELINE_TAG}",
            )
        return 0
    if not args.groups_only:
        for key, event in EVENTS.items():
            fields = load_npz(event["npz"])
            label = event["label"]
            panel_year = event["panel_year"]
            plot_monthly_map_group(
                fields,
                variable="sst",
                title=f"{label}: OISST SSTA with ERA5 850 hPa wind anomalies",
                panel_year=panel_year,
                cmap="RdBu_r",
                vmin=-2.5,
                vmax=2.5,
                colorbar_label="OISST SST anomaly (deg C)",
                stem=f"fig_{key}_revised_ssta_u850_detrended_{BASELINE_TAG}",
            )
            plot_monthly_map_group(
                fields,
                variable="precip",
                title=f"{label}: precipitation and 850-hPa wind anomalies",
                panel_year=panel_year,
                cmap="BrBG",
                vmin=-12.0,
                vmax=12.0,
                colorbar_label=r"ERA5 precipitation anomaly (mm day$^{-1}$)",
                stem=f"fig_{key}_paperstyle_era5_precip_u850_strip_detrended_{BASELINE_TAG}",
            )
            plot_d20_wind(
                fields,
                title=f"{label}: ORAS5 equatorial D20 anomaly with ERA5 850 hPa zonal wind",
                panel_year=panel_year,
                stem=f"fig_{key}_revised_d20_u850_detrended_{BASELINE_TAG}",
            )

    if args.targets_only:
        return 0

    classic_events = load_reference_event_fields(CLASSIC_REFERENCE_YEARS)
    sensitivity_events = load_reference_event_fields(EXTENDED_SENSITIVITY_YEARS)
    build_composite_fields(CLASSIC_REFERENCE_YEARS)

    group_specs = [
        (
            "classic_strong",
            classic_events,
            "Main classic strong reference events, development-year January-June (target-only 2015/16 excluded)",
            "Main classic strong reference group",
        ),
        (
            "extended_sensitivity",
            sensitivity_events,
            "Extended sensitivity events, development-year January-June (not included in the main classic reference)",
            "Extended sensitivity group",
        ),
    ]
    for slug, reference_events, title_prefix, group_description in group_specs:
        plot_selected_event_map_grid(
            reference_events,
            variable="sst",
            title=f"{title_prefix}: OISST SSTA with ERA5 850 hPa wind anomalies",
            cmap="RdBu_r",
            vmin=-2.5,
            vmax=2.5,
            colorbar_label="OISST SST anomaly (deg C)",
            stem=f"fig_{slug}_events_revised_ssta_u850_detrended_{BASELINE_TAG}",
            group_description=group_description,
        )
        plot_selected_event_map_grid(
            reference_events,
            variable="precip",
            title=f"{title_prefix}: ERA5 precipitation with ERA5 850 hPa wind anomalies",
            cmap="BrBG",
            vmin=-5.0,
            vmax=5.0,
            colorbar_label="ERA5 precipitation anomaly (mm/day)",
            stem=f"fig_{slug}_events_revised_era5_precip_u850_detrended_{BASELINE_TAG}",
            group_description=group_description,
        )
        plot_selected_event_d20_grid(
            reference_events,
            title=f"{title_prefix}: ORAS5 equatorial D20 anomaly with ERA5 850 hPa zonal wind",
            stem=f"fig_{slug}_events_revised_d20_u850_detrended_{BASELINE_TAG}",
            group_description=group_description,
        )

    assignments = pd.DataFrame(
        [
            {"event_year": 1982, "event_label": "1982/83", "comparison_window": "Jan-Jun 1982", "phase": "early_formation", "group": "main_classic_strong_reference", "role": "reference"},
            {"event_year": 1997, "event_label": "1997/98", "comparison_window": "Jan-Jun 1997", "phase": "early_formation", "group": "main_classic_strong_reference", "role": "reference"},
            {"event_year": 2002, "event_label": "2002/03", "comparison_window": "Jan-Jun 2002", "phase": "early_formation", "group": "extended_sensitivity", "role": "sensitivity_only"},
            {"event_year": 2009, "event_label": "2009/10", "comparison_window": "Jan-Jun 2009", "phase": "early_formation", "group": "extended_sensitivity", "role": "sensitivity_only"},
            {"event_year": 2015, "event_label": "2015/16", "comparison_window": "Jan-Jun 2015", "phase": "early_formation", "group": "target_events", "role": "target_only"},
            {"event_year": 2023, "event_label": "2023/24", "comparison_window": "Jan-Jun 2023", "phase": "early_formation", "group": "target_events", "role": "target_only"},
            {"event_year": 2026, "event_label": "2026", "comparison_window": "Jan-Jun 2026", "phase": "early_formation", "group": "target_events", "role": "target_only"},
        ]
    )
    assignments.to_csv(OUT_DIR / "enso_event_group_assignments.csv", index=False)
    assignments.loc[
        assignments["group"] == "main_classic_strong_reference",
        ["event_year", "event_label", "comparison_window", "phase"],
    ].to_csv(
        OUT_DIR / "classic_strong_reference_event_years.csv", index=False
    )
    assignments.loc[
        assignments["group"] == "extended_sensitivity",
        ["event_year", "event_label", "comparison_window", "phase"],
    ].to_csv(
        OUT_DIR / "extended_sensitivity_event_years.csv", index=False
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
