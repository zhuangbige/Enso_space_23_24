#!/usr/bin/env python3
"""Plot external-basin SST and equatorial D20 for pre-1980 FEP events.

The event list follows Jiang et al. (2026): 1965/66, 1969/70,
1972/73, and 1976/77.  ERSSTv5 and ORAS5 are put on a common
1960--2024 calendar-month climatology, and a linear trend is removed from
the monthly-anomaly series before the event diagnostics are calculated.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import cartopy.crs as ccrs
from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
ERSST = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
ORAS5 = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_d20_timeseries_equatorial_1960_202606.csv"
)
OUT = ROOT / "outputs/research_2026/pre1980_fep_external_d20"
DERIVED = ROOT / "data/derived/research_2026"

BASELINE_START = 1960
BASELINE_END = 2024
EVENTS = OrderedDict(
    [
        (1965, "1965/66 (EP)"),
        (1969, "1969/70 (CP)"),
        (1972, "1972/73 (EP)"),
        (1976, "1976/77 (EP)"),
    ]
)
REFERENCE_YEAR = 2023

REGIONS = OrderedDict(
    [
        ("tropical_indian_ocean", ("Tropical Indian Ocean", -20, 20, 40, 110, "#6a51a3")),
        ("maritime_continent", ("Maritime Continent", -10, 10, 95, 150, "#e08214")),
        ("western_pacific_warm_pool", ("W. Pacific warm pool", -10, 10, 120, 160, "#2b8cbe")),
        ("tropical_north_atlantic", ("Tropical North Atlantic", 0, 20, 300, 340, "#1b9e77")),
    ]
)

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
LON_TICKS = [140, 180, 220, 260, 275]
LON_LABELS = ["140°E", "180°", "140°W", "100°W", "85°W"]


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
        }
    )


def detrend_monthly_series(series: pd.Series) -> pd.Series:
    """Remove 1960--2024 monthly climatology and centered linear trend."""
    series = series.sort_index().loc[
        f"{BASELINE_START}-01-01":f"{BASELINE_END}-12-31"
    ]
    climatology = series.groupby(series.index.month).mean()
    anomaly = series - series.index.month.map(climatology).to_numpy()
    decimal_year = (
        series.index.year.to_numpy(dtype=float)
        + (series.index.month.to_numpy(dtype=float) - 1.0) / 12.0
    )
    centered_year = decimal_year - decimal_year.mean()
    good = np.isfinite(anomaly.to_numpy())
    slope = np.polyfit(centered_year[good], anomaly.to_numpy()[good], 1)[0]
    return anomaly - slope * centered_year


def load_external_basin_indices() -> pd.DataFrame:
    ds = xr.open_dataset(ERSST)
    sst = ds["sst"].sel(
        time=slice(f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-01")
    )
    rows: list[dict[str, float | int | str]] = []
    years = list(EVENTS) + [REFERENCE_YEAR]
    for region_id, (_, lat0, lat1, lon0, lon1, _) in REGIONS.items():
        subset = sst.where(
            (sst["lat"] >= lat0)
            & (sst["lat"] <= lat1)
            & (sst["lon"] >= lon0)
            & (sst["lon"] <= lon1),
            drop=True,
        )
        weights = np.cos(np.deg2rad(subset["lat"]))
        series = subset.weighted(weights).mean(("lat", "lon")).to_series()
        anomaly = detrend_monthly_series(series)
        for year in years:
            for month in range(1, 8):
                time = pd.Timestamp(year=year, month=month, day=1)
                rows.append(
                    {
                        "year": year,
                        "month": month,
                        "region": region_id,
                        "sst_anomaly_c": float(anomaly.loc[time]),
                        "baseline_years": f"{BASELINE_START}-{BASELINE_END}",
                        "detrended": True,
                        "source": "NOAA ERSSTv5",
                    }
                )
    ds.close()
    return pd.DataFrame(rows)


def load_detrended_sst_maps() -> xr.DataArray:
    ds = xr.open_dataset(ERSST)
    sst = ds["sst"].sel(
        time=slice(f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-01")
    ).load()
    climatology = sst.groupby("time.month").mean("time")
    anomaly = sst.groupby("time.month") - climatology
    decimal_year = (
        anomaly["time"].dt.year.astype(float)
        + (anomaly["time"].dt.month.astype(float) - 1.0) / 12.0
    )
    centered_year = decimal_year - decimal_year.mean("time")
    slope = (anomaly * centered_year).sum("time", skipna=True) / (
        centered_year**2
    ).sum("time")
    detrended = anomaly - slope * centered_year
    event_maps = []
    for year in EVENTS:
        event = detrended.where(
            (detrended["time"].dt.year == year)
            & detrended["time"].dt.month.isin([5, 6, 7]),
            drop=True,
        ).mean("time")
        event_maps.append(event.expand_dims(event_year=[year]))
    ds.close()
    return xr.concat(event_maps, dim="event_year")


def load_d20_anomalies() -> pd.DataFrame:
    raw = pd.read_csv(ORAS5, parse_dates=["time"])
    raw = raw.loc[
        raw["year"].between(BASELINE_START, BASELINE_END)
        & raw["requested_lon"].between(135, 275)
    ].copy()
    raw["lon"] = raw["requested_lon"].astype(float)
    pieces = []
    for lon, group in raw.groupby("lon"):
        group = group.sort_values("time").copy()
        climatology = group.groupby("month")["d20_m"].transform("mean")
        raw_anomaly = group["d20_m"] - climatology
        decimal_year = (
            group["time"].dt.year.to_numpy(dtype=float)
            + (group["time"].dt.month.to_numpy(dtype=float) - 1.0) / 12.0
        )
        centered_year = decimal_year - decimal_year.mean()
        good = np.isfinite(raw_anomaly.to_numpy())
        slope = np.polyfit(
            centered_year[good], raw_anomaly.to_numpy()[good], 1
        )[0]
        group["d20_anomaly_m"] = raw_anomaly - slope * centered_year
        group["baseline_years"] = f"{BASELINE_START}-{BASELINE_END}"
        group["linear_trend_slope_m_per_year"] = slope
        pieces.append(group)
    data = pd.concat(pieces, ignore_index=True)
    years = list(EVENTS) + [REFERENCE_YEAR]
    return data.loc[data["year"].isin(years) & data["month"].between(1, 7)].copy()


def add_panel_label(ax: plt.Axes, index: int) -> None:
    ax.text(
        0.015,
        0.98,
        f"({chr(97 + index)})",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontweight="bold",
        fontsize=11,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.5},
        zorder=20,
    )


def plot_external_maps(event_maps: xr.DataArray) -> tuple[Path, Path]:
    projection = ccrs.PlateCarree(central_longitude=180)
    data_crs = ccrs.PlateCarree()
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(13.2, 5.8),
        subplot_kw={"projection": projection},
    )
    levels = np.arange(-2.0, 2.01, 0.2)
    mappable = None
    for index, (ax, (year, label)) in enumerate(zip(axes.ravel(), EVENTS.items())):
        field = event_maps.sel(event_year=year)
        mappable = ax.contourf(
            field["lon"],
            field["lat"],
            field,
            levels=levels,
            cmap="RdBu_r",
            extend="both",
            transform=data_crs,
        )
        ax.set_extent([20, 340, -35, 35], crs=data_crs)
        ax.coastlines(linewidth=0.65, color="#303030")
        ax.gridlines(
            crs=data_crs,
            draw_labels=False,
            xlocs=[40, 100, 160, 220, 280, 340],
            ylocs=[-30, -15, 0, 15, 30],
            linewidth=0.35,
            color="#666666",
            alpha=0.45,
            linestyle=":",
        )
        ax.set_xticks([40, 100, 160, 220, 280, 340], crs=data_crs)
        ax.xaxis.set_major_formatter(LongitudeFormatter())
        ax.set_yticks([-30, -15, 0, 15, 30], crs=data_crs)
        ax.yaxis.set_major_formatter(LatitudeFormatter())
        if index % 2:
            ax.set_yticklabels([])
        ax.set_title(label, fontweight="bold")
        add_panel_label(ax, index)

        # External-basin boxes use the same definitions as the previous report.
        for region_id, (_, lat0, lat1, lon0, lon1, color) in REGIONS.items():
            linestyle = "--" if region_id in {"maritime_continent", "western_pacific_warm_pool"} else "-"
            rect = Rectangle(
                (lon0, lat0),
                lon1 - lon0,
                lat1 - lat0,
                fill=False,
                edgecolor=color,
                linewidth=1.15,
                linestyle=linestyle,
                transform=data_crs,
                zorder=10,
            )
            ax.add_patch(rect)
        fep = Rectangle(
            (270, -5),
            10,
            10,
            fill=False,
            edgecolor="#111111",
            linewidth=1.4,
            transform=data_crs,
            zorder=11,
        )
        ax.add_patch(fep)
        ax.text(
            276,
            7,
            "FEP",
            transform=data_crs,
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )

    fig.subplots_adjust(left=0.045, right=0.99, top=0.84, bottom=0.23, hspace=0.36, wspace=0.035)
    colorbar_axis = fig.add_axes([0.13, 0.105, 0.74, 0.042])
    colorbar = fig.colorbar(mappable, cax=colorbar_axis, orientation="horizontal", extend="both")
    colorbar.set_label("Detrended ERSSTv5 SST anomaly (°C)")
    fig.suptitle(
        "Pre-1980 FEP-dominant El Niño events: tropical SST background (MJJ)",
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.022,
        "Calendar-month climatology and linear trend: 1960–2024. "
        "Boxes: TIO (purple), Maritime Continent (orange dashed), "
        "western Pacific warm pool (blue dashed), TNA (green), and FEP (black).",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#4d4d4d",
    )
    png = OUT / "pre1980_fep_external_basin_ersstv5_mjj.png"
    pdf = OUT / "pre1980_fep_external_basin_ersstv5_mjj.pdf"
    fig.savefig(png, dpi=600)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf


def plot_external_indices(indices: pd.DataFrame) -> tuple[Path, Path]:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2), sharex=True, sharey=True)
    for index, (ax, (year, label)) in enumerate(zip(axes.ravel(), EVENTS.items())):
        event = indices.loc[(indices["year"] == year) & indices["month"].between(1, 6)]
        for region_id, (region_label, _, _, _, _, color) in REGIONS.items():
            subset = event.loc[event["region"] == region_id].sort_values("month")
            ax.plot(
                subset["month"],
                subset["sst_anomaly_c"],
                marker="o",
                markersize=3.8,
                linewidth=1.8,
                color=color,
                label=region_label,
            )
        ax.axhline(0, color="#555555", linewidth=0.8)
        ax.axvspan(4.5, 6.5, color="#f5d7a1", alpha=0.22, zorder=0)
        ax.set_title(label, fontweight="bold")
        ax.set_xlim(0.8, 6.2)
        ax.set_ylim(-1.25, 1.25)
        ax.set_xticks(range(1, 7), MONTH_LABELS)
        ax.grid(True, linestyle=":", linewidth=0.55, alpha=0.55)
        add_panel_label(ax, index)
    for ax in axes[:, 0]:
        ax.set_ylabel("SST anomaly (°C)")
    for ax in axes[-1, :]:
        ax.set_xlabel("Development-year month")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.955),
        ncol=4,
        frameon=False,
    )
    fig.suptitle(
        "External-basin SST evolution before pre-1980 FEP-dominant events",
        fontsize=15,
        fontweight="bold",
        y=1.02,
    )
    fig.subplots_adjust(top=0.86, bottom=0.12, hspace=0.28, wspace=0.12)
    fig.text(
        0.5,
        0.025,
        "NOAA ERSSTv5; 1960–2024 calendar-month climatology and linear trend removed. "
        "Pale shading marks the May–June portion of the Jiang et al. MJJ development window.",
        ha="center",
        fontsize=8.5,
        color="#4d4d4d",
    )
    png = OUT / "pre1980_fep_external_basin_indices_jan_jun.png"
    pdf = OUT / "pre1980_fep_external_basin_indices_jan_jun.pdf"
    fig.savefig(png, dpi=600)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf


def plot_d20(d20: pd.DataFrame) -> tuple[Path, Path]:
    fig, axes = plt.subplots(2, 2, figsize=(11.8, 7.3), sharex=True, sharey=True)
    levels = np.arange(-60, 61, 10)
    mappable = None
    for index, (ax, (year, label)) in enumerate(zip(axes.ravel(), EVENTS.items())):
        event = d20.loc[(d20["year"] == year) & d20["month"].between(1, 6)]
        pivot = event.pivot(index="month", columns="lon", values="d20_anomaly_m")
        pivot = pivot.sort_index().sort_index(axis=1)
        x = pivot.columns.to_numpy(dtype=float)
        y = pivot.index.to_numpy(dtype=float)
        z = pivot.to_numpy(dtype=float)
        mappable = ax.contourf(
            x,
            y,
            z,
            levels=levels,
            cmap="RdBu_r",
            extend="both",
        )
        contours = ax.contour(
            x,
            y,
            z,
            levels=levels,
            colors="#3f3f3f",
            linewidths=0.45,
            alpha=0.75,
        )
        ax.clabel(contours, levels=[-40, -20, 20, 40], fmt="%d", fontsize=7)
        ax.contour(x, y, z, levels=[0], colors="#1a1a1a", linewidths=1.0)
        ax.axvline(180, color="#333333", linestyle="--", linewidth=0.9)
        ax.axvline(220, color="#333333", linestyle=":", linewidth=0.9)
        ax.axvspan(270, 275, color="#f5d76e", alpha=0.22, zorder=8)
        ax.set_title(label, fontweight="bold")
        ax.set_xlim(140, 275)
        ax.set_ylim(1, 6)
        ax.set_yticks(range(1, 7), MONTH_LABELS)
        ax.set_xticks(LON_TICKS, LON_LABELS)
        add_panel_label(ax, index)
        ax.text(
            272.5,
            5.82,
            "FEP",
            ha="center",
            va="top",
            fontsize=8,
            fontweight="bold",
            zorder=15,
        )
    for ax in axes[:, 0]:
        ax.set_ylabel("Development-year month")
    for ax in axes[-1, :]:
        ax.set_xlabel("Longitude along the equator")
    colorbar = fig.colorbar(
        mappable,
        ax=axes.ravel().tolist(),
        orientation="horizontal",
        fraction=0.055,
        pad=0.105,
        aspect=45,
    )
    colorbar.set_label("ORAS5 equatorial D20 anomaly (m; positive = deeper thermocline)")
    fig.suptitle(
        "Equatorial thermocline evolution in pre-1980 FEP-dominant El Niño events",
        fontsize=15,
        fontweight="bold",
        y=1.01,
    )
    fig.text(
        0.5,
        0.015,
        "ORAS5 depth of the 20°C isotherm at 0°; 1960–2024 calendar-month climatology "
        "and linear trend removed. Dashed: date line; dotted: 140°W; yellow: available FEP points (90°–85°W).",
        ha="center",
        fontsize=8.5,
        color="#4d4d4d",
    )
    png = OUT / "pre1980_fep_oras5_d20_jan_jun.png"
    pdf = OUT / "pre1980_fep_oras5_d20_jan_jun.pdf"
    fig.savefig(png, dpi=600)
    fig.savefig(pdf)
    plt.close(fig)
    return png, pdf


def regional_mean(
    data: pd.DataFrame,
    lon_min: float,
    lon_max: float,
    *,
    include_upper: bool = False,
) -> float:
    if include_upper:
        subset = data.loc[data["lon"].between(lon_min, lon_max)]
    else:
        subset = data.loc[(data["lon"] >= lon_min) & (data["lon"] < lon_max)]
    return float(subset["d20_anomaly_m"].mean())


def build_summary(indices: pd.DataFrame, d20: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in list(EVENTS) + [REFERENCE_YEAR]:
        external = indices.loc[
            (indices["year"] == year) & indices["month"].isin([5, 6, 7])
        ]
        d20_mjj = d20.loc[
            (d20["year"] == year) & d20["month"].isin([5, 6, 7])
        ]
        west = regional_mean(d20_mjj, 140, 190)
        central = regional_mean(d20_mjj, 190, 240)
        east = regional_mean(d20_mjj, 240, 275, include_upper=True)
        fep = regional_mean(d20_mjj, 270, 275, include_upper=True)
        row: dict[str, float | int | str | bool] = {
            "year": year,
            "event": EVENTS.get(year, "2023/24 reference"),
            "pre1980_fep_event": year in EVENTS,
            "d20_west_140e_170w_m": west,
            "d20_central_170w_120w_m": central,
            "d20_east_120w_85w_m": east,
            "d20_fep_90w_85w_m": fep,
            "d20_east_minus_west_m": east - west,
        }
        for region_id in REGIONS:
            row[f"{region_id}_sst_mjj_c"] = float(
                external.loc[external["region"] == region_id, "sst_anomaly_c"].mean()
            )
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)

    indices = load_external_basin_indices()
    d20 = load_d20_anomalies()
    event_maps = load_detrended_sst_maps()
    summary = build_summary(indices, d20)

    monthly_sst_path = DERIVED / "pre1980_fep_external_basin_monthly_1960_2024_detrended.csv"
    monthly_d20_path = DERIVED / "pre1980_fep_oras5_d20_monthly_1960_2024_detrended.csv"
    summary_path = DERIVED / "pre1980_fep_external_d20_mjj_summary.csv"
    indices.to_csv(monthly_sst_path, index=False)
    d20.to_csv(monthly_d20_path, index=False)
    summary.to_csv(summary_path, index=False)

    map_paths = plot_external_maps(event_maps)
    index_paths = plot_external_indices(indices)
    d20_paths = plot_d20(d20)

    print(summary.round(3).to_string(index=False))
    for path in [monthly_sst_path, monthly_d20_path, summary_path, *map_paths, *index_paths, *d20_paths]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
