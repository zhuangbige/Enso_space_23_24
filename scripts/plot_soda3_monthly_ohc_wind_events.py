#!/usr/bin/env python3
"""Plot January--June SODA3 OHC anomalies with ERA5 850-hPa wind anomalies.

The layout follows the existing OISST SSTA + ERA5 wind comparison panels.  OHC
is integrated over 0--300 m and shown as a same-calendar-month detrended
anomaly.  The longitude range exactly matches the OISST comparison panels;
analysis-box overlays are intentionally omitted.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib
import numpy as np
import xarray as xr


matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle


OHC_FILE = (
    ROOT
    / "data/interim/research_2026/soda3_ohc_tropical_30s30n"
    / "soda3_ohc300_jan_jun_30s30n_1980_2024_1deg.nc"
)
WIND_DIR = ROOT / "data/derived/research_2026"
DEFAULT_OUT_DIR = (
    ROOT
    / "outputs/research_2026"
    / "soda3_ohc300_monthly_wind_panels_30s30n_1980_2024_detrended"
)
EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
OHC_BASELINE = "1980-2024"
WIND_BASELINE = "1980-2024"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, nargs="+", default=list(EVENTS))
    parser.add_argument("--vlim", type=float, default=3.0, help="Symmetric OHC color limit in GJ m-2.")
    parser.add_argument("--ohc-file", type=Path, default=OHC_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.4,
            "axes.titlesize": 10.4,
            "axes.labelsize": 9.2,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "axes.linewidth": 0.82,
            "axes.unicode_minus": False,
        }
    )


def open_dataset(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    try:
        return xr.open_dataset(path, engine="netcdf4")
    except Exception:
        return xr.open_dataset(path, engine="scipy")


def format_lon(value: float) -> str:
    lon = value % 360.0
    if np.isclose(lon, 180.0):
        return "180°"
    if lon < 180.0:
        return f"{lon:g}°E"
    return f"{360.0 - lon:g}°W"


def format_lat(value: float) -> str:
    if np.isclose(value, 0.0):
        return "Eq"
    return f"{abs(value):g}°{'N' if value > 0 else 'S'}"


def validate_ohc(ds: xr.Dataset) -> xr.DataArray:
    required = {"time", "lat", "lon", "ohc_300m_anomaly_detrended"}
    missing = required.difference(set(ds.variables) | set(ds.coords))
    if missing:
        raise ValueError(f"OHC input is missing: {sorted(missing)}")
    da = ds["ohc_300m_anomaly_detrended"]
    if da.dims != ("time", "lat", "lon"):
        raise ValueError(f"Unexpected OHC dimensions: {da.dims}")
    if da.attrs.get("units") != "J m-2":
        raise ValueError(f"Unexpected OHC units: {da.attrs.get('units')}")
    definition = str(ds.attrs.get("anomaly_definition", ""))
    if OHC_BASELINE not in definition:
        raise ValueError(f"Unexpected OHC anomaly definition: {definition}")
    if float(da.lat.min()) > -29.0 or float(da.lat.max()) < 29.0:
        raise ValueError(
            f"OHC latitude coverage does not match the SSTA panels: "
            f"{float(da.lat.min()):.2f} to {float(da.lat.max()):.2f}"
        )
    if float(da.lon.min()) > 121.0 or float(da.lon.max()) < 279.0:
        raise ValueError(
            f"OHC longitude coverage does not match the SSTA panels: "
            f"{float(da.lon.min()):.2f} to {float(da.lon.max()):.2f}"
        )
    return da / 1.0e9


def select_event_ohc(ohc: xr.DataArray, event: int) -> xr.DataArray:
    selected = ohc.where(
        (ohc.time.dt.year == event) & ohc.time.dt.month.isin(MONTHS), drop=True
    )
    if selected.sizes.get("time") != len(MONTHS):
        raise ValueError(f"Expected six OHC months for {event}, got {selected.sizes.get('time', 0)}")
    actual_months = tuple(int(value) for value in selected.time.dt.month.values)
    if actual_months != MONTHS:
        raise ValueError(f"Unexpected OHC months for {event}: {actual_months}")
    return selected


def load_event_wind(event: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path = WIND_DIR / f"{event}_jan_jun_oisst_ssta_era5_850_wind_anomalies_1982_2024.nc"
    with open_dataset(path) as ds:
        for name in ("u850a", "v850a", "wind_lon", "wind_lat", "time"):
            if name not in ds.variables and name not in ds.coords:
                raise ValueError(f"{path.name} is missing {name}")
        if ds.sizes.get("time") != len(MONTHS):
            raise ValueError(f"Expected six wind months for {event}")
        if str(ds.attrs.get("era5_wind_baseline", "")) != WIND_BASELINE:
            raise ValueError(f"Unexpected ERA5 baseline in {path.name}")
        times = ds.time
        years = tuple(int(value) for value in times.dt.year.values)
        months = tuple(int(value) for value in times.dt.month.values)
        if years != (event,) * len(MONTHS) or months != MONTHS:
            raise ValueError(f"Unexpected wind time axis in {path.name}")
        lat_mask = (ds.wind_lat >= -30.0) & (ds.wind_lat <= 30.0)
        lon = np.mod(ds.wind_lon.values.astype(float), 360.0)
        order = np.argsort(lon)
        lat = ds.wind_lat.where(lat_mask, drop=True).values.astype(float)
        u = ds.u850a.where(lat_mask, drop=True).values.astype(float)[:, :, order]
        v = ds.v850a.where(lat_mask, drop=True).values.astype(float)[:, :, order]
    return lon[order], lat, u, v


def format_axes(ax: plt.Axes, row: int, col: int) -> None:
    xticks = (120, 160, 200, 240, 280)
    yticks = (-30, 0, 30)
    ax.set_xlim(120, 280)
    ax.set_ylim(-30, 30)
    ax.set_xticks(xticks)
    ax.set_yticks(yticks)
    ax.set_xticklabels([format_lon(value) for value in xticks])
    ax.set_yticklabels([format_lat(value) for value in yticks])
    ax.axhline(0.0, color="0.20", linewidth=0.55, zorder=4)
    if row == 1:
        ax.set_xlabel("Longitude")
    else:
        ax.tick_params(labelbottom=False)
    if col == 0:
        ax.set_ylabel("Latitude")
    else:
        ax.tick_params(labelleft=False)
    ax.tick_params(length=3.5, width=0.85, pad=2.2)
    ax.set_box_aspect(0.375)


def add_wind(
    ax: plt.Axes,
    lon: np.ndarray,
    lat: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
) -> None:
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
        alpha=0.70,
        zorder=4,
    )
    q = ax.quiver(
        x,
        y,
        uu,
        vv,
        color="#111111",
        pivot="middle",
        width=0.0031,
        headwidth=3.6,
        headlength=4.7,
        headaxislength=4.3,
        scale=47,
        zorder=5,
    )
    ax.add_patch(
        Rectangle(
            (0.81, 0.015),
            0.185,
            0.255,
            transform=ax.transAxes,
            facecolor="white",
            edgecolor="0.28",
            linewidth=0.65,
            zorder=8,
        )
    )
    key = ax.quiverkey(
        q,
        0.902,
        0.17,
        4.0,
        r"4 m s$^{-1}$",
        labelpos="S",
        coordinates="axes",
        labelsep=0.035,
        fontproperties={"size": 9.0},
    )
    key.set_zorder(10)


def plot_event(
    ohc: xr.DataArray,
    event: int,
    output_dir: Path,
    vlim: float,
) -> tuple[Path, Path]:
    event_ohc = select_event_ohc(ohc, event)
    wind_lon, wind_lat, u850, v850 = load_event_wind(event)
    lon = event_ohc.lon.values.astype(float)
    lat = event_ohc.lat.values.astype(float)

    fig, axes = plt.subplots(2, 3, figsize=(13.6, 6.05), constrained_layout=True)
    fig.suptitle(
        f"{event} January–June: SODA3 0–300 m OHC anomalies with ERA5 850 hPa wind anomalies",
        fontsize=16,
        fontweight="bold",
        y=1.015,
    )
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    mesh = None
    for index, (ax, month_name) in enumerate(zip(axes.ravel(), MONTH_NAMES)):
        row, col = divmod(index, 3)
        mesh = ax.pcolormesh(
            lon,
            lat,
            event_ohc.isel(time=index).values,
            cmap="RdBu_r",
            norm=norm,
            shading="auto",
            rasterized=True,
            zorder=1,
        )
        add_wind(ax, wind_lon, wind_lat, u850[index], v850[index])
        format_axes(ax, row, col)
        ax.set_title(f"{month_name} {event}", fontsize=12.2, fontweight="bold", pad=6)

    assert mesh is not None
    colorbar = fig.colorbar(
        mesh,
        ax=axes.ravel().tolist(),
        orientation="horizontal",
        shrink=0.64,
        pad=0.045,
        aspect=42,
        extend="both",
    )
    colorbar.set_label("SODA3 0–300 m OHC anomaly (GJ m$^{-2}$)", fontsize=10.2)
    colorbar.set_ticks(np.linspace(-vlim, vlim, 7))
    note = (
        "Monthly same-calendar-month detrended anomalies; SODA3 OHC and ERA5 wind baselines: "
        f"{OHC_BASELINE}. Domain matches the OISST panels: 30°S–30°N, 120°E–80°W."
    )
    fig.text(0.01, -0.025, note, fontsize=8.2, color="0.30")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"fig_{event}_jan_jun_soda3_ohc300_30s30n_era5_850_windA_"
        f"{OHC_BASELINE.replace('-', '_')}"
    )
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    return png, pdf


def main() -> None:
    args = parse_args()
    if args.vlim <= 0:
        raise ValueError("--vlim must be positive")
    setup_style()
    with open_dataset(args.ohc_file) as ds:
        ohc = validate_ohc(ds).load()
    all_values = []
    for event in args.events:
        all_values.append(select_event_ohc(ohc, event).values)
    combined = np.concatenate(all_values, axis=0)
    print(
        "Selected OHC anomaly diagnostics (GJ m-2): "
        f"finite={np.isfinite(combined).mean():.4f}, "
        f"min={np.nanmin(combined):.3f}, max={np.nanmax(combined):.3f}, "
        f"p02={np.nanquantile(combined, 0.02):.3f}, p98={np.nanquantile(combined, 0.98):.3f}"
    )
    for event in args.events:
        png, pdf = plot_event(ohc, event, args.output_dir, args.vlim)
        print(png)
        print(pdf)


if __name__ == "__main__":
    main()
