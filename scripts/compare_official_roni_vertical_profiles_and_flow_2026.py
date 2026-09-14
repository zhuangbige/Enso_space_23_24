#!/usr/bin/env python3
"""Official-RONI vertical profiles, warm-water storage, and zonal transport.

Historical temperature and current are from SODA3.15.2.  The 2026 target uses
NOAA/NCEP GODAS potential temperature and zonal current.  Three quantities are
kept distinct:

1. V20 = integral(D20 dA), a warm-water volume/storage measure;
2. dV20/dt, an equivalent storage tendency in Sv, not a boundary current;
3. M20 and Q20, actual eastward volume and 20-degC-relative heat transports
   across fixed longitude sections.

Historical event intensity follows current NOAA/CPC RONI (ERSSTv6) bins.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import pearsonr


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/enso_vertical_flow_official_roni_2026"
OUT_DATA = ROOT / "data/derived/research_2026/enso_vertical_flow_official_roni_2026"
MPL_DIR = ROOT / "outputs/research_2026/mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(MPL_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


SODA_TEMP = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
SODA_TRANSPORT = ROOT / "data/derived/research_2026/soda3_warm_transport_longitude_1980_2024.csv"
GODAS_TEMP = ROOT / "data/raw/godas/godas_pottmp_equatorial_2026_jan_jun.nc"
GODAS_TEMP_CLIM = ROOT / "data/raw/godas/godas_pottmp_climatology_equatorial_1991_2020.nc"
GODAS_U = ROOT / "data/raw/godas/godas_ucur_equatorial_2026_jan_may.nc"
GODAS_U_CLIM_FILES = {
    month: ROOT
    / "data/raw/godas"
    / f"godas_ucur_climatology_equatorial_1991_2020_{label}.nc"
    for month, label in enumerate(("jan", "feb", "mar", "apr", "may", "jun"), 1)
}
VALIDATION_YEARS = (1997, 2002, 2015, 2023)

BASELINE = (1982, 2024)
MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SEASONS = {"JFM": (1, 2, 3), "AMJ": (4, 5, 6)}
LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (120.0, 280.0)
MAX_DEPTH = 300.0
SECTIONS = (180.0, 200.0, 220.0)
SECTION_LABELS = {180.0: "180°", 200.0: "160°W", 220.0: "140°W"}
REGIONS = {
    "basin": (120.0, 280.0),
    "west": (120.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 280.0),
}
RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0

EVENTS = pd.DataFrame(
    [
        (1982, 2.4, "very_strong"),
        (1986, 1.5, "strong"),
        (1991, 2.1, "very_strong"),
        (1994, 1.3, "moderate"),
        (1997, 2.3, "very_strong"),
        (2002, 1.3, "moderate"),
        (2009, 1.5, "strong"),
        (2015, 2.3, "very_strong"),
        (2023, 1.4, "moderate"),
    ],
    columns=["event_year", "peak_roni_c", "roni_class"],
)
GROUPS = {
    name: EVENTS.loc[EVENTS["roni_class"] == name, "event_year"].tolist()
    for name in ("moderate", "strong", "very_strong")
}
COLORS = {
    "moderate": "#2166ac",
    "strong": "#e08214",
    "very_strong": "#b2182b",
    "2026": "#111111",
}
LABELS = {
    "moderate": "Moderate",
    "strong": "Strong",
    "very_strong": "Very strong",
    "2026": "2026",
}


def open_dataset(path: Path, *, decode_times: bool = True) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(path)
    return xr.open_dataset(path, engine="h5netcdf", decode_times=decode_times)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 170,
            "savefig.dpi": 360,
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 9.2,
            "axes.titlesize": 10.3,
            "axes.labelsize": 9.4,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "axes.linewidth": 0.8,
            "legend.fontsize": 8.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def coordinate_widths(values: np.ndarray, lower: float, upper: float) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    edges = np.empty(values.size + 1, dtype=float)
    edges[1:-1] = 0.5 * (values[:-1] + values[1:])
    edges[0] = lower
    edges[-1] = upper
    if np.any(np.diff(edges) <= 0):
        raise ValueError("Non-positive coordinate cell width")
    return np.diff(edges)


def depth_thickness(depth: np.ndarray) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    edges = np.empty(depth.size + 1, dtype=float)
    edges[0] = 0.0
    edges[-1] = MAX_DEPTH
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    thickness = np.diff(edges)
    if np.any(thickness <= 0) or not np.isclose(thickness.sum(), MAX_DEPTH):
        raise ValueError("Invalid 0-300 m depth thickness")
    return thickness


def d20_from_temperature(temperature_c: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Deepest 20-degC crossing, linearly interpolated along the depth axis."""

    temperature_c = np.asarray(temperature_c, dtype=float)
    depth = np.asarray(depth, dtype=float)
    if temperature_c.shape[1] != depth.size:
        raise ValueError("Depth axis must be axis 1")
    valid = np.isfinite(temperature_c)
    warm = valid & (temperature_c >= 20.0)
    indices = np.arange(depth.size, dtype=int)[None, :, None, None]
    deepest = np.where(warm, indices, -1).max(axis=1)
    any_warm = deepest >= 0
    all_warm = deepest == depth.size - 1
    safe = np.clip(deepest, 0, depth.size - 2)
    lower_t = np.take_along_axis(
        temperature_c, safe[:, None, :, :], axis=1
    )[:, 0]
    upper_t = np.take_along_axis(
        temperature_c, (safe + 1)[:, None, :, :], axis=1
    )[:, 0]
    lower_z = depth[safe]
    upper_z = depth[safe + 1]
    denominator = upper_t - lower_t
    fraction = np.divide(
        20.0 - lower_t,
        denominator,
        out=np.zeros_like(lower_t),
        where=np.isfinite(denominator) & (np.abs(denominator) > 1.0e-10),
    )
    crossing = lower_z + np.clip(fraction, 0.0, 1.0) * (upper_z - lower_z)
    result = np.where(any_warm, crossing, 0.0)
    result = np.where(all_warm, MAX_DEPTH, result)
    result = np.where(valid.any(axis=1), result, np.nan)
    return np.clip(result, 0.0, MAX_DEPTH)


def area_matrix(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    dlat = coordinate_widths(lat, LAT_BOUNDS[0], LAT_BOUNDS[1])
    dlon = coordinate_widths(lon, LON_BOUNDS[0], LON_BOUNDS[1])
    lat_edges = np.empty(len(lat) + 1)
    lat_edges[0] = LAT_BOUNDS[0]
    lat_edges[-1] = LAT_BOUNDS[1]
    lat_edges[1:-1] = 0.5 * (lat[:-1] + lat[1:])
    lat_factor = np.sin(np.deg2rad(lat_edges[1:])) - np.sin(
        np.deg2rad(lat_edges[:-1])
    )
    return EARTH_RADIUS**2 * lat_factor[:, None] * np.deg2rad(dlon)[None, :]


def same_month_detrend(
    frame: pd.DataFrame,
    value_columns: list[str],
    group_columns: list[str],
) -> pd.DataFrame:
    result = frame.copy()
    mean_year = 0.5 * (BASELINE[0] + BASELINE[1])
    for column in value_columns:
        result[f"{column}_anom"] = np.nan
    for _, index in result.groupby(group_columns + ["month"], sort=False).groups.items():
        current = result.loc[index]
        train = current.loc[current["year"].between(*BASELINE)]
        x = train["year"].to_numpy(dtype=float) - mean_year
        design = np.column_stack([np.ones(len(x)), x])
        for column in value_columns:
            y = train[column].to_numpy(dtype=float)
            valid = np.isfinite(y)
            if valid.sum() < 20:
                continue
            intercept, slope = np.linalg.lstsq(design[valid], y[valid], rcond=None)[0]
            all_x = current["year"].to_numpy(dtype=float) - mean_year
            result.loc[index, f"{column}_anom"] = (
                current[column].to_numpy(dtype=float) - intercept - slope * all_x
            )
    return result


def fixed_latitude_mean(temperature: xr.DataArray, vertical: str) -> xr.DataArray:
    selected = temperature.sel(lat=slice(*LAT_BOUNDS), lon=slice(*LON_BOUNDS))
    selected = selected.sel({vertical: slice(0.0, MAX_DEPTH)})
    valid = selected.notnull().all(("time", vertical))
    weights = np.cos(np.deg2rad(selected.lat)).broadcast_like(valid).where(valid, 0.0)
    return selected.weighted(weights).mean("lat", skipna=True).load()


def detrended_temperature_anomaly(temperature: xr.DataArray) -> xr.DataArray:
    values = temperature.values.astype(np.float64)
    time = pd.DatetimeIndex(temperature.time.values)
    output = np.full(values.shape, np.nan, dtype=np.float32)
    mean_year = 0.5 * (BASELINE[0] + BASELINE[1])
    for month in MONTHS:
        index = np.where(time.month == month)[0]
        train_index = index[
            (time.year[index] >= BASELINE[0]) & (time.year[index] <= BASELINE[1])
        ]
        x = time.year[train_index].to_numpy(dtype=float) - mean_year
        field = values[train_index]
        finite = np.isfinite(field)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(field, axis=0),
            count,
            out=np.full(field.shape[1:], np.nan),
            where=count > 0,
        )
        denominator = np.nansum(finite * x[:, None, None] ** 2, axis=0)
        slope = np.divide(
            np.nansum(x[:, None, None] * (field - mean), axis=0),
            denominator,
            out=np.full(field.shape[1:], np.nan),
            where=denominator > 0,
        )
        all_x = time.year[index].to_numpy(dtype=float) - mean_year
        output[index] = (
            values[index] - mean[None] - slope[None] * all_x[:, None, None]
        ).astype(np.float32)
    return xr.DataArray(
        output,
        dims=temperature.dims,
        coords=temperature.coords,
        name="temperature_anomaly",
        attrs={"units": "degC", "baseline": "1982-2024 same-month detrended"},
    )


def build_vertical_profiles() -> tuple[xr.DataArray, xr.DataArray, pd.DataFrame]:
    with open_dataset(SODA_TEMP) as soda:
        soda_mean = fixed_latitude_mean(soda.temp, "depth")
    soda_anom = detrended_temperature_anomaly(soda_mean)
    target_lon = np.arange(121.0, 280.0, 1.0)
    target_depth = soda_anom.depth.where(soda_anom.depth < MAX_DEPTH, drop=True)
    soda_anom = soda_anom.sel(depth=target_depth).interp(lon=target_lon)

    group_fields = []
    for group, years in GROUPS.items():
        events = []
        for year in years:
            selected = soda_anom.where(soda_anom.time.dt.year == year, drop=True)
            selected = selected.assign_coords(time=list(MONTHS)).rename(time="month")
            events.append(selected)
        group_fields.append(xr.concat(events, dim="event").mean("event"))

    with open_dataset(GODAS_TEMP) as obs, open_dataset(GODAS_TEMP_CLIM) as clim:
        obs_c = obs.pottmp.sel(level=slice(0.0, MAX_DEPTH)) - 273.15
        clim_c = clim.pottmp.sel(level=slice(0.0, MAX_DEPTH)) - 273.15
        obs_mean = fixed_latitude_mean(obs_c, "level")
        clim_mean = fixed_latitude_mean(clim_c, "level")
        target_months = []
        for month in MONTHS:
            target_months.append(
                (obs_mean.isel(time=month - 1) - clim_mean.isel(time=month - 1))
                .interp(level=target_depth.values, lon=target_lon)
                .rename(level="depth")
            )
    target = xr.concat(target_months, dim=pd.Index(MONTHS, name="month"))
    monthly = xr.concat(
        group_fields + [target],
        dim=pd.Index(("moderate", "strong", "very_strong", "2026"), name="category"),
    )
    seasonal = xr.concat(
        [
            monthly.sel(month=list(months)).mean("month").expand_dims(season=[season])
            for season, months in SEASONS.items()
        ],
        dim="season",
    )

    rows = []
    target_values = monthly.sel(category="2026").values.ravel()
    for category in ("moderate", "strong", "very_strong"):
        reference = monthly.sel(category=category).values.ravel()
        valid = np.isfinite(target_values) & np.isfinite(reference)
        rows.append(
            {
                "reference_class": category,
                "n_events": len(GROUPS[category]),
                "event_years": ",".join(map(str, GROUPS[category])),
                "jan_jun_pattern_correlation": float(
                    pearsonr(target_values[valid], reference[valid]).statistic
                ),
                "jan_jun_rmse_degC": float(
                    np.sqrt(np.mean((target_values[valid] - reference[valid]) ** 2))
                ),
            }
        )
    return monthly, seasonal, pd.DataFrame(rows)


def build_soda_warm_volume() -> pd.DataFrame:
    with open_dataset(SODA_TEMP) as ds:
        temp = ds.temp.sel(depth=slice(0.0, MAX_DEPTH), lat=slice(*LAT_BOUNDS), lon=slice(*LON_BOUNDS))
        values = temp.values.astype(float)
        depth = temp.depth.values.astype(float)
        lat = temp.lat.values.astype(float)
        lon = temp.lon.values.astype(float)
        time = pd.DatetimeIndex(temp.time.values)
    d20 = d20_from_temperature(values, depth)
    area = area_matrix(lat, lon)
    rows = []
    for time_index, timestamp in enumerate(time):
        row: dict[str, float | int | pd.Timestamp] = {
            "time": timestamp,
            "year": timestamp.year,
            "month": timestamp.month,
            "source": "SODA3",
        }
        for name, bounds in REGIONS.items():
            if name == "basin":
                selected = np.ones(lon.size, dtype=bool)
            elif name == "west":
                selected = lon < bounds[1]
            elif name == "central":
                selected = (lon >= bounds[0]) & (lon < bounds[1])
            else:
                selected = lon >= bounds[0]
            row[f"v20_{name}_m3"] = float(
                np.nansum(d20[time_index][:, selected] * area[:, selected])
            )
        rows.append(row)
    frame = pd.DataFrame(rows)
    value_columns = [f"v20_{name}_m3" for name in REGIONS]
    return same_month_detrend(frame, value_columns, [])


def godas_d20_volume(temperature: xr.DataArray) -> dict[str, float]:
    selected = temperature.sel(level=slice(0.0, MAX_DEPTH), lat=slice(*LAT_BOUNDS))
    selected = selected.sel(lon=slice(120.5, 279.5))
    values = selected.values.astype(float)
    if values.ndim == 3:
        values = values[None]
    depth = selected.level.values.astype(float)
    lat = selected.lat.values.astype(float)
    lon = selected.lon.values.astype(float)
    d20 = d20_from_temperature(values, depth)[0]
    area = area_matrix(lat, lon)
    result = {}
    for name, bounds in REGIONS.items():
        if name == "basin":
            mask = np.ones(lon.size, dtype=bool)
        elif name == "west":
            mask = lon < bounds[1]
        elif name == "central":
            mask = (lon >= bounds[0]) & (lon < bounds[1])
        else:
            mask = lon >= bounds[0]
        result[f"v20_{name}_m3"] = float(np.nansum(d20[:, mask] * area[:, mask]))
    return result


def build_godas_warm_volume() -> pd.DataFrame:
    rows = []
    with open_dataset(GODAS_TEMP) as obs, open_dataset(GODAS_TEMP_CLIM) as clim:
        for month in MONTHS:
            observed = obs.pottmp.isel(time=month - 1) - 273.15
            baseline = clim.pottmp.isel(time=month - 1) - 273.15
            observed_volume = godas_d20_volume(observed)
            baseline_volume = godas_d20_volume(baseline)
            row: dict[str, float | int | str] = {
                "time": pd.Timestamp(2026, month, 1),
                "year": 2026,
                "month": month,
                "source": "GODAS",
            }
            for name in REGIONS:
                raw_name = f"v20_{name}_m3"
                row[raw_name] = observed_volume[raw_name]
                row[f"{raw_name}_climatology"] = baseline_volume[raw_name]
                row[f"{raw_name}_anom"] = observed_volume[raw_name] - baseline_volume[raw_name]
            rows.append(row)
    return pd.DataFrame(rows)


def build_godas_volume_validation(
    historical_volume: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    with open_dataset(GODAS_TEMP_CLIM) as clim:
        for year in VALIDATION_YEARS:
            path = (
                ROOT
                / "data/raw/godas/validation"
                / f"godas_pottmp_equatorial_{year}_jan_jun.nc"
            )
            with open_dataset(path) as obs:
                for month in MONTHS:
                    observed = godas_d20_volume(obs.pottmp.isel(time=month - 1) - 273.15)
                    baseline = godas_d20_volume(clim.pottmp.isel(time=month - 1) - 273.15)
                    row: dict[str, float | int] = {"year": year, "month": month}
                    for region in REGIONS:
                        name = f"v20_{region}_m3"
                        row[f"godas_{name}_anom"] = observed[name] - baseline[name]
                    rows.append(row)
    points = pd.DataFrame(rows).merge(historical_volume, on=["year", "month"])
    summary = []
    for region in REGIONS:
        godas = points[f"godas_v20_{region}_m3_anom"].to_numpy(dtype=float)
        soda = points[f"v20_{region}_m3_anom"].to_numpy(dtype=float)
        # Scale the O(1e14 m3) volumes before solving the regression.  This
        # avoids the ill-conditioning that would otherwise make the intercept
        # effectively vanish in the least-squares fit.
        volume_scale = 1.0e13
        godas_scaled = godas / volume_scale
        soda_scaled = soda / volume_scale
        design = np.column_stack([np.ones(len(godas_scaled)), godas_scaled])
        intercept_scaled, slope = np.linalg.lstsq(
            design, soda_scaled, rcond=None
        )[0]
        intercept = intercept_scaled * volume_scale
        summary.append(
            {
                "region": region,
                "n_points": len(godas),
                "correlation": float(pearsonr(godas, soda).statistic),
                "soda_on_godas_intercept_m3": float(intercept),
                "soda_on_godas_slope": float(slope),
                "godas_to_soda_std_ratio": float(
                    np.std(godas, ddof=1) / np.std(soda, ddof=1)
                ),
                "godas_to_soda_mean_abs_ratio": float(
                    np.mean(np.abs(godas)) / np.mean(np.abs(soda))
                ),
            }
        )
    return points, pd.DataFrame(summary)


def section_transport(
    temperature: xr.DataArray,
    velocity: xr.DataArray,
    longitude: float,
) -> tuple[float, float]:
    """Return eastward M20 (Sv) and Q20 (PW) across one longitude."""

    temp = (
        temperature.sel(level=slice(0.0, MAX_DEPTH), lat=slice(*LAT_BOUNDS))
        .interp(lon=longitude)
        .transpose("level", "lat")
    )
    current = (
        velocity.sel(level=slice(0.0, MAX_DEPTH))
        .interp(lon=longitude, lat=temp.lat)
        .transpose("level", "lat")
    )
    depth = temp.level.values.astype(float)
    lat = temp.lat.values.astype(float)
    dz = depth_thickness(depth)[:, None]
    lat_edges = np.empty(lat.size + 1)
    lat_edges[0] = LAT_BOUNDS[0]
    lat_edges[-1] = LAT_BOUNDS[1]
    lat_edges[1:-1] = 0.5 * (lat[:-1] + lat[1:])
    dy = EARTH_RADIUS * np.deg2rad(np.diff(lat_edges))[None, :]
    area = dz * dy
    t = temp.values.astype(float)
    u = current.values.astype(float)
    valid = np.isfinite(t) & np.isfinite(u)
    warm_mask = valid & (t >= 20.0)
    warm_excess = np.where(valid, np.maximum(t - 20.0, 0.0), np.nan)
    volume_sv = np.nansum(np.where(warm_mask, u * area, np.nan)) / 1.0e6
    heat_pw = RHO0 * CP0 * np.nansum(u * warm_excess * area) / 1.0e15
    return float(volume_sv), float(heat_pw)


def build_godas_transport() -> pd.DataFrame:
    rows = []
    with open_dataset(GODAS_TEMP) as temp_obs, open_dataset(GODAS_U) as u_obs, open_dataset(
        GODAS_TEMP_CLIM
    ) as temp_clim:
        for month in MONTHS:
            current_temp = temp_obs.pottmp.isel(time=month - 1) - 273.15
            baseline_temp = temp_clim.pottmp.isel(time=month - 1) - 273.15
            with open_dataset(GODAS_U_CLIM_FILES[month], decode_times=False) as u_clim:
                baseline_u = u_clim.ucur.isel(time=0)
                for longitude in SECTIONS:
                    current_volume, current_heat = section_transport(
                        current_temp, u_obs.ucur.isel(time=month - 1), longitude
                    )
                    baseline_volume, baseline_heat = section_transport(
                        baseline_temp, baseline_u, longitude
                    )
                    rows.append(
                        {
                            "year": 2026,
                            "month": month,
                            "longitude_e": longitude,
                            "source": "GODAS",
                            "warm_volume_transport_sv": current_volume,
                            "q20_pw": current_heat,
                            "warm_volume_transport_sv_climatology": baseline_volume,
                            "q20_pw_climatology": baseline_heat,
                            "warm_volume_transport_sv_anom": current_volume - baseline_volume,
                            "q20_pw_anom": current_heat - baseline_heat,
                        }
                    )
    return pd.DataFrame(rows)


def build_godas_transport_validation() -> pd.DataFrame:
    rows = []
    with open_dataset(GODAS_TEMP_CLIM) as temp_clim:
        for year in VALIDATION_YEARS:
            temp_path = (
                ROOT
                / "data/raw/godas/validation"
                / f"godas_pottmp_equatorial_{year}_jan_jun.nc"
            )
            u_path = (
                ROOT
                / "data/raw/godas/validation"
                / f"godas_ucur_equatorial_{year}_jan_jun.nc"
            )
            with open_dataset(temp_path) as temp_obs, open_dataset(u_path) as u_obs:
                for month in MONTHS:
                    current_temp = temp_obs.pottmp.isel(time=month - 1) - 273.15
                    baseline_temp = temp_clim.pottmp.isel(time=month - 1) - 273.15
                    with open_dataset(GODAS_U_CLIM_FILES[month], decode_times=False) as u_clim:
                        for longitude in SECTIONS:
                            volume, heat = section_transport(
                                current_temp, u_obs.ucur.isel(time=month - 1), longitude
                            )
                            climatology_volume, climatology_heat = section_transport(
                                baseline_temp, u_clim.ucur.isel(time=0), longitude
                            )
                            rows.append(
                                {
                                    "year": year,
                                    "month": month,
                                    "longitude_e": longitude,
                                    "godas_warm_volume_transport_sv_anom": volume - climatology_volume,
                                    "godas_q20_pw_anom": heat - climatology_heat,
                                }
                            )
    return pd.DataFrame(rows)


def transport_validation(
    godas: pd.DataFrame,
    soda: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    points = godas.merge(
        soda,
        on=["year", "month", "longitude_e"],
        suffixes=("_godas", "_soda"),
    )
    rows = []
    pairs = (
        (
            "warm_volume_transport_sv_anom",
            "godas_warm_volume_transport_sv_anom",
            "warm_volume_transport_sv_anom",
        ),
        ("q20_pw_anom", "godas_q20_pw_anom", "q20_pw_anom"),
    )
    for name, godas_column, soda_column in pairs:
        x = points[godas_column].to_numpy(dtype=float)
        y = points[soda_column].to_numpy(dtype=float)
        intercept, slope = np.linalg.lstsq(
            np.column_stack([np.ones(len(x)), x]), y, rcond=None
        )[0]
        rows.append(
            {
                "metric": name,
                "n_points": len(x),
                "correlation": float(pearsonr(x, y).statistic),
                "soda_on_godas_intercept": float(intercept),
                "soda_on_godas_slope": float(slope),
                "godas_to_soda_std_ratio": float(np.std(x, ddof=1) / np.std(y, ddof=1)),
                "godas_to_soda_mean_abs_ratio": float(
                    np.mean(np.abs(x)) / np.mean(np.abs(y))
                ),
                "rmse": float(np.sqrt(np.mean((x - y) ** 2))),
            }
        )
    return points, pd.DataFrame(rows)


def add_soda_equivalent_transport(
    current: pd.DataFrame,
    validation: pd.DataFrame,
) -> pd.DataFrame:
    result = current.copy()
    for metric in ("warm_volume_transport_sv_anom", "q20_pw_anom"):
        row = validation.loc[validation["metric"] == metric].iloc[0]
        result[f"{metric}_soda_equivalent"] = (
            row["soda_on_godas_intercept"]
            + row["soda_on_godas_slope"] * result[metric]
        )
    return result


def build_historical_transport() -> pd.DataFrame:
    frame = pd.read_csv(SODA_TRANSPORT)
    frame = frame.loc[frame["longitude_e"].isin(SECTIONS)].copy()
    frame = frame.drop(
        columns=["warm_volume_transport_sv_anom", "q20_pw_anom"],
        errors="ignore",
    )
    residual = same_month_detrend(
        frame,
        ["warm_volume_transport_sv", "q20_pw"],
        ["longitude_e"],
    )
    needed = [
        "time",
        "year",
        "month",
        "longitude_e",
        "q20_pw",
        "warm_volume_transport_sv",
        "q20_pw_anom",
        "warm_volume_transport_sv_anom",
    ]
    result = residual[needed].copy()
    result["source"] = "SODA3"
    return result


def add_class(frame: pd.DataFrame) -> pd.DataFrame:
    lookup = EVENTS.set_index("event_year")["roni_class"].to_dict()
    result = frame.copy()
    result["roni_class"] = result["year"].map(lookup).fillna("2026")
    return result


def class_monthly_summary(frame: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    historical = frame.loc[frame["year"].isin(EVENTS["event_year"])].copy()
    rows = []
    grouping = [column for column in ("roni_class", "month", "longitude_e") if column in frame]
    for keys, current in historical.groupby(grouping, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(grouping, keys))
        row["n_events"] = int(current["year"].nunique())
        for metric in metrics:
            row[f"{metric}_mean"] = float(current[metric].mean())
            row[f"{metric}_sem"] = float(current[metric].sem(ddof=1))
        rows.append(row)
    return pd.DataFrame(rows)


def storage_tendency(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, current in frame.groupby("year", sort=True):
        current = current.sort_values("month")
        times = pd.to_datetime(current["time"])
        for index in range(1, len(current)):
            seconds = (times.iloc[index] - times.iloc[index - 1]).total_seconds()
            row: dict[str, float | int | str] = {
                "year": int(year),
                "month": int(current.iloc[index]["month"]),
                "interval": f"{MONTH_LABELS[index-1]}–{MONTH_LABELS[index]}",
                "source": current.iloc[index]["source"],
            }
            for region in REGIONS:
                column = f"v20_{region}_m3_anom"
                row[f"dv20dt_{region}_sv"] = float(
                    (current.iloc[index][column] - current.iloc[index - 1][column])
                    / seconds
                    / 1.0e6
                )
            rows.append(row)
    return pd.DataFrame(rows)


def plot_vertical_profiles(seasonal: xr.DataArray) -> None:
    values = np.abs(seasonal.values[np.isfinite(seasonal.values)])
    vlim = max(2.0, math.ceil(float(np.quantile(values, 0.985)) * 2.0) / 2.0)
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)
    fig, axes = plt.subplots(2, 4, figsize=(13.6, 6.3), sharex=True, sharey=True, constrained_layout=True)
    categories = ("moderate", "strong", "very_strong", "2026")
    mesh = None
    for row, season in enumerate(SEASONS):
        for col, category in enumerate(categories):
            ax = axes[row, col]
            field = seasonal.sel(season=season, category=category)
            mesh = ax.pcolormesh(field.lon, field.depth, field, cmap="RdBu_r", norm=norm, shading="auto")
            ax.contour(field.lon, field.depth, field, levels=[-1.0, 0.0, 1.0], colors=["#2166ac", "0.35", "#b2182b"], linewidths=[0.55, 0.45, 0.55])
            ax.set_ylim(MAX_DEPTH, 0)
            ax.axvline(180.0, color="0.3", ls="--", lw=0.55)
            ax.axvline(220.0, color="0.3", ls="--", lw=0.55)
            ticks = np.array([140, 180, 220, 260])
            labels = ["140°E", "180°", "140°W", "100°W"]
            ax.set_xticks(ticks, labels)
            ax.set_title(
                f"({chr(97 + row * 4 + col)}) {season} — {LABELS[category]}"
                + (f" (n={len(GROUPS[category])})" if category != "2026" else ""),
                loc="left",
            )
            ax.set_xlabel("Longitude")
            if col == 0:
                ax.set_ylabel("Depth (m)")
    assert mesh is not None
    colorbar = fig.colorbar(mesh, ax=axes, orientation="horizontal", shrink=0.68, pad=0.08)
    colorbar.set_label("Potential-temperature anomaly (°C)")
    fig.savefig(OUT_DIR / "official_roni_vertical_profiles_2026.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "official_roni_vertical_profiles_2026.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_transport(historical: pd.DataFrame, current: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12.2, 6.2), sharex=True, constrained_layout=True)
    metrics = (
        ("warm_volume_transport_sv_anom", "Warm-volume transport anomaly (Sv)"),
        ("q20_pw_anom", "$Q_{20}$ heat-transport anomaly (PW)"),
    )
    for row, (metric, ylabel) in enumerate(metrics):
        for col, longitude in enumerate(SECTIONS):
            ax = axes[row, col]
            for category in ("moderate", "strong", "very_strong"):
                selected = summary.loc[
                    (summary["roni_class"] == category)
                    & (summary["longitude_e"] == longitude)
                ].sort_values("month")
                mean = selected[f"{metric}_mean"].to_numpy(dtype=float)
                sem = selected[f"{metric}_sem"].to_numpy(dtype=float)
                ax.plot(MONTHS, mean, color=COLORS[category], lw=1.65, label=f"{LABELS[category]} (n={len(GROUPS[category])})")
                ax.fill_between(MONTHS, mean - sem, mean + sem, color=COLORS[category], alpha=0.10, linewidth=0)
            target = current.loc[current["longitude_e"] == longitude].sort_values("month")
            ax.plot(
                MONTHS,
                target[metric],
                color="0.55",
                lw=1.15,
                ls="--",
                marker="o",
                ms=3.0,
                label="2026 GODAS raw",
            )
            ax.plot(
                MONTHS,
                target[f"{metric}_soda_equivalent"],
                color=COLORS["2026"],
                lw=2.0,
                marker="o",
                ms=3.7,
                label="2026 SODA-equivalent",
            )
            ax.axhline(0.0, color="0.45", lw=0.65)
            ax.set_xticks(MONTHS, MONTH_LABELS)
            ax.grid(axis="y", color="0.88", lw=0.5)
            ax.set_title(f"({chr(97 + row * 3 + col)}) {SECTION_LABELS[longitude]}", loc="left")
            if col == 0:
                ax.set_ylabel(ylabel)
            if row == 1:
                ax.set_xlabel("Development month")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.08))
    fig.savefig(OUT_DIR / "official_roni_zonal_warm_transport_2026.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "official_roni_zonal_warm_transport_2026.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_storage(
    monthly: pd.DataFrame,
    current: pd.DataFrame,
    tendency: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 3.5), constrained_layout=True)
    monthly_summary = class_monthly_summary(monthly, ["v20_basin_m3_anom"])
    tendency_summary = class_monthly_summary(
        tendency, ["dv20dt_west_sv", "dv20dt_east_sv"]
    )
    for category in ("moderate", "strong", "very_strong"):
        selected = monthly_summary.loc[monthly_summary["roni_class"] == category].sort_values("month")
        mean = selected["v20_basin_m3_anom_mean"].to_numpy(dtype=float) / 1.0e13
        sem = selected["v20_basin_m3_anom_sem"].to_numpy(dtype=float) / 1.0e13
        axes[0].plot(MONTHS, mean, color=COLORS[category], lw=1.65, label=f"{LABELS[category]} (n={len(GROUPS[category])})")
        axes[0].fill_between(MONTHS, mean - sem, mean + sem, color=COLORS[category], alpha=0.10, linewidth=0)
    axes[0].plot(MONTHS, current["v20_basin_m3_anom"] / 1.0e13, color=COLORS["2026"], lw=2.0, marker="o", ms=3.7, label="2026")
    for ax, region, title in ((axes[1], "west", "(b) Western storage tendency"), (axes[2], "east", "(c) Eastern storage tendency")):
        for category in ("moderate", "strong", "very_strong"):
            selected = tendency_summary.loc[tendency_summary["roni_class"] == category].sort_values("month")
            mean = selected[f"dv20dt_{region}_sv_mean"].to_numpy(dtype=float)
            sem = selected[f"dv20dt_{region}_sv_sem"].to_numpy(dtype=float)
            ax.plot(range(2, 7), mean, color=COLORS[category], lw=1.65)
            ax.fill_between(range(2, 7), mean - sem, mean + sem, color=COLORS[category], alpha=0.10, linewidth=0)
        target = tendency.loc[tendency["year"] == 2026].sort_values("month")
        ax.plot(range(2, 7), target[f"dv20dt_{region}_sv"], color=COLORS["2026"], lw=2.0, marker="o", ms=3.7)
        ax.set_title(title, loc="left")
        ax.set_ylabel("$dV_{20}/dt$ (Sv)")
        ax.set_xticks(range(2, 7), ("Jan–Feb", "Feb–Mar", "Mar–Apr", "Apr–May", "May–Jun"), rotation=25)
        ax.axhline(0.0, color="0.45", lw=0.65)
        ax.grid(axis="y", color="0.88", lw=0.5)
    axes[0].set_title("(a) Basin warm-water-volume anomaly", loc="left")
    axes[0].set_ylabel("$V_{20}$ anomaly ($10^{13}$ m$^3$)")
    axes[0].set_xticks(MONTHS, MONTH_LABELS)
    axes[0].axhline(0.0, color="0.45", lw=0.65)
    axes[0].grid(axis="y", color="0.88", lw=0.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.10))
    fig.savefig(OUT_DIR / "official_roni_warm_volume_storage_rate_2026.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "official_roni_warm_volume_storage_rate_2026.pdf", bbox_inches="tight")
    plt.close(fig)


def write_summary(
    profile_similarity: pd.DataFrame,
    godas_transport: pd.DataFrame,
    transport_summary: pd.DataFrame,
    current_volume: pd.DataFrame,
    tendency: pd.DataFrame,
    transport_validation_summary: pd.DataFrame,
    volume_validation_summary: pd.DataFrame,
) -> None:
    sim = profile_similarity.set_index("reference_class")
    transport_group = transport_summary.set_index(["roni_class", "longitude_e", "month"])
    target_220 = godas_transport.loc[godas_transport["longitude_e"] == 220.0].set_index("month")
    target_tendency = tendency.loc[tendency["year"] == 2026].set_index("month")
    trans_val = transport_validation_summary.set_index("metric")
    volume_val = volume_validation_summary.set_index("region")
    lines = [
        "# 官方 RONI 分组的垂向结构与暖水输送",
        "",
        "## 量的区别",
        "",
        "- 暖水体积 V20 = ∫D20 dA，是区域内20°C以上暖水储量。",
        "- dV20/dt 是储量变化率，单位可写为Sv，但它不是某一边界上的真实海流。",
        "- M20 = ∫u I(T≥20°C)dA，是穿过固定经度断面的真实东向暖水体积输送，单位Sv。",
        "- Q20 = ρcp∫u max(T−20°C,0)dA，是相对20°C的东向暖水热输送，单位PW。正值均表示向东。",
        "",
        "## 垂向结构",
        "",
        f"2026年1–6月温度异常垂向型态与极强组相关最高（r={sim.loc['very_strong', 'jan_jun_pattern_correlation']:.3f}），严格强组r={sim.loc['strong', 'jan_jun_pattern_correlation']:.3f}，中等组r={sim.loc['moderate', 'jan_jun_pattern_correlation']:.3f}。",
        "",
        "## 2026实际流量",
        "",
        f"140°W断面2026年GODAS原始M20异常由1月{target_220.loc[1, 'warm_volume_transport_sv_anom']:+.1f} Sv演变到6月{target_220.loc[6, 'warm_volume_transport_sv_anom']:+.1f} Sv；按重叠事件回归换算为SODA等效幅度后为{target_220.loc[1, 'warm_volume_transport_sv_anom_soda_equivalent']:+.1f}和{target_220.loc[6, 'warm_volume_transport_sv_anom_soda_equivalent']:+.1f} Sv。",
        f"对应Q20原始异常由{target_220.loc[1, 'q20_pw_anom']:+.2f}变为{target_220.loc[6, 'q20_pw_anom']:+.2f} PW，SODA等效值为{target_220.loc[1, 'q20_pw_anom_soda_equivalent']:+.2f}和{target_220.loc[6, 'q20_pw_anom_soda_equivalent']:+.2f} PW。",
        f"极强组140°W六月平均M20异常为{transport_group.loc[('very_strong', 220.0, 6), 'warm_volume_transport_sv_anom_mean']:+.1f} Sv，严格强组为{transport_group.loc[('strong', 220.0, 6), 'warm_volume_transport_sv_anom_mean']:+.1f} Sv，中等组为{transport_group.loc[('moderate', 220.0, 6), 'warm_volume_transport_sv_anom_mean']:+.1f} Sv。",
        f"2026东部暖水储量变化率在4–5月为{target_tendency.loc[5, 'dv20dt_east_sv']:+.1f} Sv、5–6月为{target_tendency.loc[6, 'dv20dt_east_sv']:+.1f} Sv。该量表示东部箱储量增长，不等同于140°W单边流量，因为还包含东边界、南北边界及局地垂向/表面过程。",
        f"四个重叠事件共72个经度—月份样本中，GODAS与SODA的M20异常相关r={trans_val.loc['warm_volume_transport_sv_anom', 'correlation']:.3f}，GODAS标准差约为SODA的{trans_val.loc['warm_volume_transport_sv_anom', 'godas_to_soda_std_ratio']:.2f}倍；Q20相关r={trans_val.loc['q20_pw_anom', 'correlation']:.3f}，标准差比为{trans_val.loc['q20_pw_anom', 'godas_to_soda_std_ratio']:.2f}。盆地V20异常的跨产品相关为r={volume_val.loc['basin', 'correlation']:.3f}，标准差比为{volume_val.loc['basin', 'godas_to_soda_std_ratio']:.2f}，因此储量比较比单边输送绝对幅度更稳健。",
        "",
        "## 产品边界",
        "",
        "历史输送为SODA3并按1982–2024同历月去均值和趋势；2026为GODAS当前场减GODAS 1991–2020月气候态输送。跨产品的符号、时间演变和相对型态比绝对幅度更稳健。GODAS气候态输送由月平均温度场与月平均流速场的乘积计算，并非逐月uT多年平均，因此小的气候态涡动协方差没有包含。",
    ]
    (OUT_DIR / "VERTICAL_PROFILE_AND_FLOW_2026_CN.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    MPL_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()

    monthly_profiles, seasonal_profiles, profile_similarity = build_vertical_profiles()
    plot_vertical_profiles(seasonal_profiles)

    historical_volume = add_class(build_soda_warm_volume())
    current_volume = add_class(build_godas_warm_volume())
    volume_validation_points, volume_validation_summary = build_godas_volume_validation(
        historical_volume
    )
    all_volume = pd.concat([historical_volume, current_volume], ignore_index=True, sort=False)
    event_volume = all_volume.loc[
        all_volume["year"].isin(EVENTS["event_year"].tolist() + [2026])
    ].copy()
    tendency = add_class(storage_tendency(event_volume))

    historical_transport = add_class(build_historical_transport())
    godas_transport_validation = build_godas_transport_validation()
    transport_validation_points, transport_validation_summary = transport_validation(
        godas_transport_validation,
        historical_transport,
    )
    current_transport = add_class(
        add_soda_equivalent_transport(build_godas_transport(), transport_validation_summary)
    )
    event_transport = historical_transport.loc[
        historical_transport["year"].isin(EVENTS["event_year"])
    ].copy()
    transport_summary = class_monthly_summary(
        event_transport,
        ["warm_volume_transport_sv_anom", "q20_pw_anom"],
    )

    plot_transport(event_transport, current_transport, transport_summary)
    plot_storage(event_volume, current_volume, tendency)

    monthly_profiles.astype(np.float32).to_dataset(name="temperature_anomaly").to_netcdf(
        OUT_DATA / "official_roni_monthly_vertical_profiles.nc", engine="h5netcdf"
    )
    seasonal_profiles.astype(np.float32).to_dataset(name="temperature_anomaly").to_netcdf(
        OUT_DATA / "official_roni_seasonal_vertical_profiles.nc", engine="h5netcdf"
    )
    profile_similarity.to_csv(OUT_DATA / "2026_vertical_profile_similarity.csv", index=False)
    event_volume.to_csv(OUT_DATA / "event_warm_water_volume.csv", index=False)
    tendency.to_csv(OUT_DATA / "event_warm_water_storage_tendency_sv.csv", index=False)
    event_transport.to_csv(OUT_DATA / "historical_event_zonal_transport.csv", index=False)
    current_transport.to_csv(OUT_DATA / "2026_godas_zonal_transport.csv", index=False)
    transport_summary.to_csv(OUT_DATA / "official_roni_transport_composites.csv", index=False)
    transport_validation_points.to_csv(
        OUT_DATA / "soda3_godas_transport_validation_points.csv", index=False
    )
    transport_validation_summary.to_csv(
        OUT_DATA / "soda3_godas_transport_validation_summary.csv", index=False
    )
    volume_validation_points.to_csv(
        OUT_DATA / "soda3_godas_warm_volume_validation_points.csv", index=False
    )
    volume_validation_summary.to_csv(
        OUT_DATA / "soda3_godas_warm_volume_validation_summary.csv", index=False
    )
    EVENTS.to_csv(OUT_DATA / "official_roni_event_classes.csv", index=False)

    write_summary(
        profile_similarity,
        current_transport,
        transport_summary,
        current_volume,
        tendency,
        transport_validation_summary,
        volume_validation_summary,
    )
    run = {
        "historical_temperature": str(SODA_TEMP),
        "historical_transport": str(SODA_TRANSPORT),
        "target_temperature": str(GODAS_TEMP),
        "target_zonal_current": str(GODAS_U),
        "baseline_historical": "1982-2024 same calendar month mean/trend removed",
        "baseline_target": "GODAS 1991-2020 monthly climatology",
        "groups": GROUPS,
        "sections_deg_e": list(SECTIONS),
    }
    (OUT_DIR / "run_summary.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
