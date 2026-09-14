#!/usr/bin/env python3
"""Direct May--July spatial context for 1997, 2015, and 2023.

The purpose is to inspect why the 2023 precipitation and wind response did not
expand into the central Pacific as strongly as in 1997/2015.  The script uses
only existing physical fields and does not create a new index, regression,
threshold, or attribution equation.

Outputs pair:

* tropical ERSSTv5 SST anomalies with ERA5 mean-sea-level-pressure anomalies;
* tropical-Pacific GPCP precipitation anomalies with ERA5 eastward turbulent
  surface-stress anomalies.
"""

from __future__ import annotations

import json
from pathlib import Path

import cartopy.crs as ccrs
from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/jiang_epcp_two_box_heat_fate"

SST_FILE = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
GPCP_FILE = ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc"
MSL_FILE = ROOT / "data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc"
STRESS_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"

FIELD_FILE = DERIVED / "jiang_1997_2015_2023_may_july_sst_slp_precip_stress.nc"
REGION_MEANS_FILE = DERIVED / "jiang_1997_2015_2023_may_july_direct_region_means.csv"
METADATA_FILE = DERIVED / "jiang_2023_may_july_convection_slp_context_metadata.json"
SST_SLP_FIGURE = OUT / "jiang_1997_2015_2023_may_july_tropical_sst_slp.png"
PRECIP_STRESS_FIGURE = OUT / "jiang_1997_2015_2023_may_july_pacific_precip_stress.png"

EVENTS = (1997, 2015, 2023)
MONTHS = (5, 6, 7)
MONTH_LABELS = {5: "May", 6: "June", 7: "July"}
REFERENCE_START = 1982
REFERENCE_END = 2022

REGIONS = {
    "western_pacific": (120.0, 170.0, -10.0, 5.0),
    "central_box": (180.0, 220.0, -10.0, 5.0),
    "eastern_box": (220.0, 280.0, -10.0, 5.0),
}

REGION_VARIABLES = {
    "sst_anomaly_c": ("lat", "lon"),
    "msl_anomaly_hpa": ("msl_lat", "msl_lon"),
    "precip_anomaly_mm_day": ("precip_lat", "precip_lon"),
    "eastward_stress_anomaly_nm2": ("stress_lat", "stress_lon"),
}


def normalize_longitude(data: xr.DataArray, longitude: str) -> xr.DataArray:
    normalized = data.assign_coords({longitude: np.mod(data[longitude], 360.0)})
    normalized = normalized.sortby(longitude)
    _, indices = np.unique(normalized[longitude].values, return_index=True)
    return normalized.isel({longitude: np.sort(indices)})


def subset_domain(
    data: xr.DataArray,
    *,
    latitude: str,
    longitude: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> xr.DataArray:
    normalized = normalize_longitude(data, longitude)
    return normalized.where(
        (normalized[latitude] >= lat_min)
        & (normalized[latitude] <= lat_max)
        & (normalized[longitude] >= lon_min)
        & (normalized[longitude] <= lon_max),
        drop=True,
    )


def event_field_anomalies(
    data: xr.DataArray,
    *,
    time: str,
    output_name: str,
) -> xr.DataArray:
    """Return event/month fields after removing the reference linear expectation."""
    time_index = pd.DatetimeIndex(data[time].values)
    results: list[xr.DataArray] = []
    for month in MONTHS:
        reference_indices = np.flatnonzero(
            (time_index.month == month)
            & (time_index.year >= REFERENCE_START)
            & (time_index.year <= REFERENCE_END)
        )
        reference = data.isel({time: reference_indices}).load()
        reference_years = np.asarray(
            pd.DatetimeIndex(reference[time].values).year,
            dtype=float,
        )
        reference_values = np.asarray(reference.to_numpy(), dtype=float)
        shape = reference_values.shape[1:]
        flattened = reference_values.reshape(reference_values.shape[0], -1)
        slopes = np.full(flattened.shape[1], np.nan)
        intercepts = np.full(flattened.shape[1], np.nan)
        for point in range(flattened.shape[1]):
            series = flattened[:, point]
            finite = np.isfinite(series)
            if finite.sum() >= 20:
                slopes[point], intercepts[point] = np.polyfit(
                    reference_years[finite], series[finite], 1
                )

        event_pieces: list[xr.DataArray] = []
        for event_year in EVENTS:
            target_indices = np.flatnonzero(
                (time_index.month == month) & (time_index.year == event_year)
            )
            if len(target_indices) != 1:
                raise ValueError(
                    f"Expected one {event_year}-{month:02d} field, found {len(target_indices)}"
                )
            target = data.isel({time: int(target_indices[0])}).load()
            expected = slopes * float(event_year) + intercepts
            anomaly_values = (
                np.asarray(target.to_numpy(), dtype=float).reshape(-1) - expected
            ).reshape(shape)
            anomaly = target.copy(data=anomaly_values).drop_vars(time, errors="ignore")
            event_pieces.append(anomaly.expand_dims(event_year=[event_year]))
        month_array = xr.concat(event_pieces, dim="event_year")
        results.append(month_array.expand_dims(month=[month]))
    return xr.concat(results, dim="month").transpose(
        "event_year", "month", ...
    ).rename(output_name)


def load_sst() -> xr.DataArray:
    with xr.open_dataset(SST_FILE, decode_times=True) as dataset:
        data = subset_domain(
            dataset["sst"],
            latitude="lat",
            longitude="lon",
            lat_min=-25.0,
            lat_max=25.0,
            lon_min=0.0,
            lon_max=358.0,
        )
        return event_field_anomalies(
            data, time="time", output_name="sst_anomaly_c"
        )


def load_msl() -> xr.DataArray:
    with xr.open_dataset(MSL_FILE, decode_times=True) as dataset:
        # The source is 0.25 degree.  One-degree sampling is sufficient for
        # the tropical pressure contours and keeps the computation compact.
        data = dataset["msl"].isel(latitude=slice(None, None, 4), longitude=slice(None, None, 4))
        data = subset_domain(
            data,
            latitude="latitude",
            longitude="longitude",
            lat_min=-25.0,
            lat_max=25.0,
            lon_min=0.0,
            lon_max=359.0,
        ).rename({"latitude": "msl_lat", "longitude": "msl_lon"})
        anomaly = event_field_anomalies(
            data, time="valid_time", output_name="msl_anomaly_hpa"
        )
    anomaly = anomaly / 100.0
    anomaly.attrs["units"] = "hPa"
    return anomaly


def load_precip() -> xr.DataArray:
    with xr.open_dataset(GPCP_FILE, decode_times=True) as dataset:
        data = subset_domain(
            dataset["precip"],
            latitude="lat",
            longitude="lon",
            lat_min=-15.0,
            lat_max=15.0,
            lon_min=120.0,
            lon_max=280.0,
        ).rename({"lat": "precip_lat", "lon": "precip_lon"})
        return event_field_anomalies(
            data, time="time", output_name="precip_anomaly_mm_day"
        )


def load_stress() -> xr.DataArray:
    monthly: list[xr.DataArray] = []
    for month in MONTHS:
        pieces = []
        for part in ("part01", "part02"):
            path = STRESS_DIR / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            with xr.open_dataset(path, decode_times=True) as dataset:
                pieces.append(dataset["avg_iews"].load())
        monthly.append(normalize_longitude(xr.concat(pieces, dim="longitude"), "longitude"))
    data = xr.concat(monthly, dim="valid_time").sortby("valid_time")
    data = subset_domain(
        data,
        latitude="latitude",
        longitude="longitude",
        lat_min=-10.0,
        lat_max=10.0,
        lon_min=120.0,
        lon_max=280.0,
    ).rename({"latitude": "stress_lat", "longitude": "stress_lon"})
    return event_field_anomalies(
        data,
        time="valid_time",
        output_name="eastward_stress_anomaly_nm2",
    )


def build_dataset() -> xr.Dataset:
    dataset = xr.Dataset(
        {
            "sst_anomaly_c": load_sst(),
            "msl_anomaly_hpa": load_msl(),
            "precip_anomaly_mm_day": load_precip(),
            "eastward_stress_anomaly_nm2": load_stress(),
        }
    )
    dataset.attrs.update(
        {
            "analysis": "Direct May-July spatial comparison; no new index/equation/threshold",
            "events": "1997, 2015, 2023",
            "reference": "1982-2022 same-calendar-month linear expectation",
        }
    )
    return dataset


def direct_region_means(dataset: xr.Dataset) -> pd.DataFrame:
    """Tabulate direct physical-variable means for the plotted regions."""
    rows: list[dict[str, object]] = []
    for event_year in EVENTS:
        for month in MONTHS:
            for region, (lon_min, lon_max, lat_min, lat_max) in REGIONS.items():
                row: dict[str, object] = {
                    "event_year": event_year,
                    "month": month,
                    "region": region,
                }
                for variable, (latitude, longitude) in REGION_VARIABLES.items():
                    field = dataset[variable].sel(event_year=event_year, month=month)
                    field = field.where(
                        (field[latitude] >= lat_min)
                        & (field[latitude] <= lat_max)
                        & (field[longitude] >= lon_min)
                        & (field[longitude] <= lon_max),
                        drop=True,
                    )
                    weights = np.cos(np.deg2rad(field[latitude]))
                    row[variable] = float(field.weighted(weights).mean())
                rows.append(row)
    return pd.DataFrame(rows)


def add_geo_style(
    axis: plt.Axes,
    *,
    extent: tuple[float, float, float, float],
    left_labels: bool,
    bottom_labels: bool,
) -> None:
    axis.set_extent(extent, crs=ccrs.PlateCarree())
    axis.coastlines(resolution="50m", linewidth=0.6, color="#333333")
    grid = axis.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=True,
        linewidth=0.4,
        color="#999999",
        alpha=0.45,
        linestyle=":",
    )
    grid.top_labels = False
    grid.right_labels = False
    grid.left_labels = left_labels
    grid.bottom_labels = bottom_labels
    grid.xformatter = LONGITUDE_FORMATTER
    grid.yformatter = LATITUDE_FORMATTER
    grid.xlabel_style = {"size": 8}
    grid.ylabel_style = {"size": 8}


def make_sst_slp_figure(dataset: xr.Dataset) -> None:
    projection = ccrs.PlateCarree(central_longitude=180.0)
    transform = ccrs.PlateCarree()
    fig, axes = plt.subplots(
        3,
        3,
        figsize=(17, 5.8),
        subplot_kw={"projection": projection},
    )
    sst_norm = TwoSlopeNorm(vmin=-3.0, vcenter=0.0, vmax=3.0)
    pressure_levels = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]
    image = None
    for row, event_year in enumerate(EVENTS):
        for column, month in enumerate(MONTHS):
            axis = axes[row, column]
            sst = dataset.sst_anomaly_c.sel(event_year=event_year, month=month)
            slp = dataset.msl_anomaly_hpa.sel(event_year=event_year, month=month)
            image = axis.pcolormesh(
                dataset.lon,
                dataset.lat,
                sst,
                cmap="RdBu_r",
                norm=sst_norm,
                shading="auto",
                transform=transform,
            )
            contours = axis.contour(
                dataset.msl_lon,
                dataset.msl_lat,
                slp,
                levels=pressure_levels,
                colors="#202020",
                linewidths=0.65,
                transform=transform,
            )
            axis.clabel(contours, fmt="%g", fontsize=6, inline_spacing=2)
            add_geo_style(
                axis,
                extent=(0.0, 359.0, -25.0, 25.0),
                left_labels=column == 0,
                bottom_labels=row == len(EVENTS) - 1,
            )
            if row == 0:
                axis.set_title(MONTH_LABELS[month], fontsize=12, weight="bold")
            if column == 0:
                axis.text(
                    -0.10,
                    0.5,
                    str(event_year),
                    transform=axis.transAxes,
                    rotation=90,
                    va="center",
                    ha="center",
                    fontsize=13,
                    weight="bold",
                )
    if image is None:
        raise RuntimeError("No SST-SLP map created")
    colorbar = fig.colorbar(image, ax=axes, orientation="horizontal", fraction=0.035, pad=0.065)
    colorbar.set_label("ERSSTv5 SST anomaly (°C); contours: ERA5 SLP anomaly (hPa)")
    fig.suptitle(
        "Tropical thermal and pressure background",
        fontsize=18,
        weight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.925,
        "May–July direct fields; common scales; 1982–2022 same-calendar-month linear expectation",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.subplots_adjust(left=0.045, right=0.985, top=0.84, bottom=0.19, hspace=0.18, wspace=0.05)
    fig.savefig(SST_SLP_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def add_box_outlines(axis: plt.Axes) -> None:
    transform = ccrs.PlateCarree()
    for lon0, width, color in ((180.0, 40.0, "#5E3C99"), (220.0, 60.0, "#E66101")):
        axis.add_patch(
            Rectangle(
                (lon0, -10.0),
                width,
                15.0,
                fill=False,
                edgecolor=color,
                linewidth=1.2,
                transform=transform,
                zorder=5,
            )
        )


def make_precip_stress_figure(dataset: xr.Dataset) -> None:
    projection = ccrs.PlateCarree(central_longitude=180.0)
    transform = ccrs.PlateCarree()
    fig, axes = plt.subplots(
        3,
        3,
        figsize=(17, 6.2),
        subplot_kw={"projection": projection},
    )
    precip_norm = TwoSlopeNorm(vmin=-6.0, vcenter=0.0, vmax=6.0)
    stress_levels = [-0.05, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03, 0.05]
    image = None
    for row, event_year in enumerate(EVENTS):
        for column, month in enumerate(MONTHS):
            axis = axes[row, column]
            precip = dataset.precip_anomaly_mm_day.sel(
                event_year=event_year, month=month
            )
            stress = dataset.eastward_stress_anomaly_nm2.sel(
                event_year=event_year, month=month
            )
            image = axis.pcolormesh(
                dataset.precip_lon,
                dataset.precip_lat,
                precip,
                cmap="BrBG",
                norm=precip_norm,
                shading="auto",
                transform=transform,
            )
            contours = axis.contour(
                dataset.stress_lon,
                dataset.stress_lat,
                stress,
                levels=stress_levels,
                colors="#202020",
                linewidths=0.7,
                transform=transform,
            )
            axis.clabel(contours, fmt="%.2f", fontsize=5.5, inline_spacing=2)
            add_box_outlines(axis)
            add_geo_style(
                axis,
                extent=(120.0, 280.0, -15.0, 15.0),
                left_labels=column == 0,
                bottom_labels=row == len(EVENTS) - 1,
            )
            if row == 0:
                axis.set_title(MONTH_LABELS[month], fontsize=12, weight="bold")
            if column == 0:
                axis.text(
                    -0.10,
                    0.5,
                    str(event_year),
                    transform=axis.transAxes,
                    rotation=90,
                    va="center",
                    ha="center",
                    fontsize=13,
                    weight="bold",
                )
    if image is None:
        raise RuntimeError("No precipitation-stress map created")
    colorbar = fig.colorbar(image, ax=axes, orientation="horizontal", fraction=0.035, pad=0.065)
    colorbar.set_label(
        "GPCP precipitation anomaly (mm day⁻¹); contours: ERA5 eastward stress anomaly (N m⁻²)"
    )
    fig.suptitle(
        "Pacific convection and eastward surface-stress response",
        fontsize=18,
        weight="bold",
        y=0.985,
    )
    fig.text(
        0.5,
        0.925,
        "Purple box: central; orange box: eastern; positive stress contours are eastward/westerly",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.subplots_adjust(left=0.045, right=0.985, top=0.84, bottom=0.18, hspace=0.18, wspace=0.05)
    fig.savefig(PRECIP_STRESS_FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def validate(dataset: xr.Dataset) -> dict[str, object]:
    diagnostics: dict[str, object] = {"dimensions": dict(dataset.sizes), "variables": {}}
    for variable in dataset.data_vars:
        values = np.asarray(dataset[variable].to_numpy(), dtype=float)
        finite = np.isfinite(values)
        finite_fraction = float(finite.mean())
        if finite_fraction < 0.5:
            raise ValueError(f"Too few finite values in {variable}: {finite_fraction:.3f}")
        diagnostics["variables"][variable] = {
            "finite_fraction": finite_fraction,
            "minimum": float(np.nanmin(values)),
            "maximum": float(np.nanmax(values)),
        }
    return diagnostics


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset()
    diagnostics = validate(dataset)
    dataset.to_netcdf(FIELD_FILE)
    direct_region_means(dataset).to_csv(REGION_MEANS_FILE, index=False)
    make_sst_slp_figure(dataset)
    make_precip_stress_figure(dataset)
    metadata = {
        "scope": "Direct spatial comparison only; no new index, threshold, regression, or attribution equation.",
        "events": list(EVENTS),
        "months": list(MONTHS),
        "reference_years": [REFERENCE_START, REFERENCE_END],
        "sources": {
            "sst": str(SST_FILE),
            "precipitation": str(GPCP_FILE),
            "mean_sea_level_pressure": str(MSL_FILE),
            "eastward_surface_stress": str(STRESS_DIR),
        },
        "direct_region_means": str(REGION_MEANS_FILE),
        "diagnostics": diagnostics,
    }
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {FIELD_FILE}")
    print(f"Wrote {REGION_MEANS_FILE}")
    print(f"Wrote {METADATA_FILE}")
    print(f"Wrote {SST_SLP_FIGURE}")
    print(f"Wrote {PRECIP_STRESS_FIGURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
