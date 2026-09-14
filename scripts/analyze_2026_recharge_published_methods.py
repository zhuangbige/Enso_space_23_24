#!/usr/bin/env python3
"""Analyze 2026 ENSO recharge using published diagnostics only.

No event-similarity score, fitted event weights, tuned longitude window, or
new composite index is used.  The script applies three established choices:

1. Meinen and McPhaden (2000): WWV above the 20 degC isotherm in
   5S-5N, 120E-80W.  NOAA/PMEL's published WWV anomaly is the primary series.
2. Li et al. (2022): D20 represents thermocline structure; longitude-dependent
   D20 anomalies and the basin WWV evolution diagnose recharge/discharge.
3. Chakravorty et al. (2021): warm-water volume transport from the surface to
   the time-varying D20 at 170E (10S-5N), 5N and 10S (140E-80W).  Eastward and
   equatorward transports are positive.

Historical intensity classes are the NOAA/CPC RONI bins and are not pooled:
moderate, strong, and very strong are displayed separately.  The 2026 event is
left unclassified because its mature-phase peak has not yet occurred.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/godas/authoritative_recharge_sections"
OUT = ROOT / "outputs/research_2026/enso_recharge_published_methods_2026"
DATA_OUT = ROOT / "data/derived/research_2026/enso_recharge_published_methods_2026"
os.environ.setdefault("MPLCONFIGDIR", str(OUT / "mplconfig"))
os.environ.setdefault("KMP_USE_SHM", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


EARTH_RADIUS = 6_371_000.0
MONTHS = np.arange(1, 7)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
SEASONS = {"JFM": (1, 2, 3), "AMJ": (4, 5, 6)}

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
    columns=("event_year", "peak_roni_c", "roni_class"),
)
GROUPS = {
    name: EVENTS.loc[EVENTS.roni_class == name, "event_year"].tolist()
    for name in ("moderate", "strong", "very_strong")
}
COLORS = {
    "moderate": "#2166AC",
    "strong": "#E08214",
    "very_strong": "#B2182B",
    "2026": "#111111",
}
LABELS = {
    "moderate": "Moderate (n=3)",
    "strong": "Strong (n=2)",
    "very_strong": "Very strong (n=4)",
    "2026": "2026",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 170,
            "savefig.dpi": 360,
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 9.2,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.4,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "legend.fontsize": 8.0,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def open_nc(path: Path) -> xr.Dataset:
    if not path.exists():
        raise FileNotFoundError(path)
    return xr.open_dataset(path, engine="h5netcdf", decode_times=False)


def midpoint_edges(values: np.ndarray, lower: float, upper: float) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size == 0 or np.any(np.diff(values) <= 0):
        raise ValueError("coordinates must be a nonempty increasing vector")
    edges = np.empty(values.size + 1, dtype=float)
    edges[0], edges[-1] = lower, upper
    if values.size > 1:
        edges[1:-1] = 0.5 * (values[:-1] + values[1:])
    if np.any(np.diff(edges) <= 0):
        raise ValueError(f"invalid clipped edges for {lower}..{upper}")
    return edges


def depth_edges(level: np.ndarray) -> np.ndarray:
    level = np.asarray(level, dtype=float)
    edges = np.empty(level.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (level[:-1] + level[1:])
    edges[-1] = level[-1] + 0.5 * (level[-1] - level[-2])
    return edges


def d20_from_temperature(temperature_c: np.ndarray, level: np.ndarray) -> np.ndarray:
    """First downward warm-to-cold 20 degC crossing, linearly interpolated."""
    temperature_c = np.asarray(temperature_c, dtype=float)
    level = np.asarray(level, dtype=float)
    if temperature_c.shape[0] != level.size:
        raise ValueError("level must be the first temperature dimension")
    crossing = (temperature_c[:-1] >= 20.0) & (temperature_c[1:] < 20.0)
    any_crossing = crossing.any(axis=0)
    index = crossing.argmax(axis=0)
    t0 = np.take_along_axis(temperature_c, index[None], axis=0)[0]
    t1 = np.take_along_axis(temperature_c, (index + 1)[None], axis=0)[0]
    z0, z1 = level[index], level[index + 1]
    fraction = np.divide(
        20.0 - t0,
        t1 - t0,
        out=np.zeros_like(t0),
        where=np.isfinite(t0) & np.isfinite(t1) & (np.abs(t1 - t0) > 1.0e-12),
    )
    result = z0 + np.clip(fraction, 0.0, 1.0) * (z1 - z0)
    surface_valid = np.isfinite(temperature_c[0])
    result = np.where(any_crossing, result, np.nan)
    result = np.where(
        (~any_crossing) & surface_valid & (temperature_c[-1] >= 20.0),
        depth_edges(level)[-1],
        result,
    )
    result = np.where(
        (~any_crossing) & surface_valid & (temperature_c[0] < 20.0),
        0.0,
        result,
    )
    return result


def layer_overlap(d20: np.ndarray, level: np.ndarray) -> np.ndarray:
    edges = depth_edges(level)
    shape = (level.size,) + (1,) * d20.ndim
    top = edges[:-1].reshape(shape)
    bottom = edges[1:].reshape(shape)
    return np.maximum(0.0, np.minimum(bottom, d20[None]) - top)


def wwv_and_profile(temperature: xr.DataArray) -> tuple[float, np.ndarray, np.ndarray]:
    selected = temperature.sel(lat=slice(-5.0, 5.0), lon=slice(120.0, 279.999))
    temp_c = selected.transpose("level", "lat", "lon").values.astype(float) - 273.15
    d20 = d20_from_temperature(temp_c, selected.level.values)
    lat = selected.lat.values.astype(float)
    lon = selected.lon.values.astype(float)
    lat_edges = np.deg2rad(midpoint_edges(lat, -5.0, 5.0))
    lon_edges = np.deg2rad(midpoint_edges(lon, 120.0, 280.0))
    area = EARTH_RADIUS**2 * (
        np.sin(lat_edges[1:]) - np.sin(lat_edges[:-1])
    )[:, None] * np.diff(lon_edges)[None, :]
    wwv = float(np.nansum(d20 * area))
    weights = np.cos(np.deg2rad(lat))[:, None] * np.isfinite(d20)
    profile = np.divide(
        np.nansum(d20 * weights, axis=0),
        np.nansum(weights, axis=0),
        out=np.full(lon.size, np.nan),
        where=np.nansum(weights, axis=0) > 0,
    )
    return wwv, lon, profile


def zonal_transport_170e(temperature: xr.DataArray, velocity: xr.DataArray) -> float:
    u = velocity.sel(lon=170.0, method="nearest").sel(lat=slice(-10.0, 5.0))
    temp = temperature.interp(lon=170.0, lat=u.lat)
    temp_c = temp.transpose("level", "lat").values.astype(float) - 273.15
    u_values = u.transpose("level", "lat").values.astype(float)
    d20 = d20_from_temperature(temp_c, temp.level.values)
    overlap = layer_overlap(d20, temp.level.values)
    lat = u.lat.values.astype(float)
    dy = EARTH_RADIUS * np.diff(np.deg2rad(midpoint_edges(lat, -10.0, 5.0)))
    valid = np.isfinite(u_values) & np.isfinite(temp_c)
    return float(np.nansum(np.where(valid, u_values * overlap * dy[None], np.nan)) / 1.0e6)


def meridional_transport(
    temperature: xr.DataArray,
    velocity: xr.DataArray,
    latitude: float,
) -> float:
    v = velocity.sel(lat=latitude, method="nearest").sel(lon=slice(140.0, 280.0))
    temp = temperature.interp(lat=latitude, lon=v.lon)
    temp_c = temp.transpose("level", "lon").values.astype(float) - 273.15
    v_values = v.transpose("level", "lon").values.astype(float)
    d20 = d20_from_temperature(temp_c, temp.level.values)
    overlap = layer_overlap(d20, temp.level.values)
    lon = v.lon.values.astype(float)
    dx = (
        EARTH_RADIUS
        * np.cos(np.deg2rad(latitude))
        * np.diff(np.deg2rad(midpoint_edges(lon, 140.0, 280.0)))
    )
    sign = -1.0 if latitude > 0.0 else 1.0
    valid = np.isfinite(v_values) & np.isfinite(temp_c)
    return float(
        np.nansum(np.where(valid, sign * v_values * overlap * dx[None], np.nan))
        / 1.0e6
    )


def parse_pmel_wwv() -> pd.DataFrame:
    path = RAW / "pmel_tao_wwv.dat"
    rows: list[tuple[int, int, float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        pieces = line.split()
        if len(pieces) != 3 or not pieces[0].isdigit() or len(pieces[0]) != 6:
            continue
        date = int(pieces[0])
        rows.append((date // 100, date % 100, float(pieces[1]), float(pieces[2])))
    frame = pd.DataFrame(rows, columns=("year", "month", "pmel_wwv_m3", "pmel_wwv_anom_m3"))
    frame["pmel_wwv_1e14m3"] = frame.pmel_wwv_m3 / 1.0e14
    frame["pmel_wwv_anom_1e14m3"] = frame.pmel_wwv_anom_m3 / 1.0e14
    return frame


def build_godas_diagnostics() -> tuple[pd.DataFrame, dict[int, np.ndarray], dict[int, np.ndarray]]:
    clim_temp_ds = open_nc(RAW / "godas_pottmp_climatology_1991_2020.nc")
    clim_u_ds = open_nc(RAW / "godas_ucur_170e_climatology_1991_2020.nc")
    clim_v5_ds = open_nc(RAW / "godas_vcur_5n_climatology_1991_2020.nc")
    clim_v10_ds = open_nc(RAW / "godas_vcur_10s_climatology_1991_2020.nc")
    if any(ds.sizes.get("time") != 12 for ds in (clim_temp_ds, clim_u_ds, clim_v5_ds, clim_v10_ds)):
        raise ValueError("GODAS climatology must contain all 12 calendar months")

    rows: list[dict[str, float | int | str]] = []
    profiles: dict[int, np.ndarray] = {}
    vertical_sections: dict[int, np.ndarray] = {}
    profile_lon: np.ndarray | None = None
    section_depth: np.ndarray | None = None
    section_lon: np.ndarray | None = None

    years = [*EVENTS.event_year.tolist(), 2026]
    for year in years:
        temp_ds = open_nc(RAW / f"godas_pottmp_{year}_jan_jun.nc")
        u_ds = open_nc(RAW / f"godas_ucur_170e_{year}_jan_jun.nc")
        v5_ds = open_nc(RAW / f"godas_vcur_5n_{year}_jan_jun.nc")
        v10_ds = open_nc(RAW / f"godas_vcur_10s_{year}_jan_jun.nc")
        if any(ds.sizes.get("time") != 6 for ds in (temp_ds, u_ds, v5_ds, v10_ds)):
            raise ValueError(f"{year} does not contain January-June")
        year_profiles = []
        year_sections = []
        for index, month in enumerate(MONTHS):
            temp = temp_ds.pottmp.isel(time=index)
            u = u_ds.ucur.isel(time=index)
            v5 = v5_ds.vcur.isel(time=index)
            v10 = v10_ds.vcur.isel(time=index)
            clim_temp = clim_temp_ds.pottmp.isel(time=month - 1)
            clim_u = clim_u_ds.ucur.isel(time=month - 1)
            clim_v5 = clim_v5_ds.vcur.isel(time=month - 1)
            clim_v10 = clim_v10_ds.vcur.isel(time=month - 1)

            wwv, lon, d20_profile = wwv_and_profile(temp)
            clim_wwv, clim_lon, clim_profile = wwv_and_profile(clim_temp)
            if not np.allclose(lon, clim_lon):
                raise ValueError("event and climatology longitude grids differ")
            profile_lon = lon
            year_profiles.append(d20_profile - clim_profile)

            z170 = zonal_transport_170e(temp, u)
            z170_clim = zonal_transport_170e(clim_temp, clim_u)
            m5 = meridional_transport(temp, v5, 5.0)
            m5_clim = meridional_transport(clim_temp, clim_v5, 5.0)
            m10 = meridional_transport(temp, v10, -10.0)
            m10_clim = meridional_transport(clim_temp, clim_v10, -10.0)

            selected = temp.sel(level=slice(0.0, 300.0), lat=slice(-5.0, 5.0), lon=slice(120.0, 279.999))
            clim_selected = clim_temp.sel(level=selected.level, lat=slice(-5.0, 5.0), lon=selected.lon)
            weights = np.cos(np.deg2rad(selected.lat))
            event_section = selected.weighted(weights).mean("lat")
            clim_section = clim_selected.weighted(weights).mean("lat")
            anomaly_section = (event_section - clim_section).transpose("level", "lon").values.astype(float)
            section_depth = selected.level.values.astype(float)
            section_lon = selected.lon.values.astype(float)
            year_sections.append(anomaly_section)

            rows.append(
                {
                    "year": year,
                    "month": int(month),
                    "roni_class": EVENTS.set_index("event_year").roni_class.to_dict().get(year, "target"),
                    "godas_wwv_anom_1e14m3": (wwv - clim_wwv) / 1.0e14,
                    "zonal_170e_eastward_anom_sv": z170 - z170_clim,
                    "meridional_5n_equatorward_anom_sv": m5 - m5_clim,
                    "meridional_10s_equatorward_anom_sv": m10 - m10_clim,
                    "d20_profile_min_m": float(np.nanmin(d20_profile - clim_profile)),
                    "d20_profile_max_m": float(np.nanmax(d20_profile - clim_profile)),
                }
            )
        profiles[year] = np.stack(year_profiles)
        vertical_sections[year] = np.stack(year_sections)
        for ds in (temp_ds, u_ds, v5_ds, v10_ds):
            ds.close()

    for ds in (clim_temp_ds, clim_u_ds, clim_v5_ds, clim_v10_ds):
        ds.close()
    if profile_lon is None or section_depth is None or section_lon is None:
        raise RuntimeError("no diagnostics built")
    profiles[-1] = profile_lon
    # Coordinates are attached separately in the caller via module globals in
    # the returned dictionaries to keep CSV output simple.
    profiles[-2] = section_lon
    profiles[-3] = section_depth
    return pd.DataFrame(rows), profiles, vertical_sections


def attach_pmel(godas: pd.DataFrame, pmel: pd.DataFrame) -> pd.DataFrame:
    selected = pmel.loc[
        pmel.year.isin([*EVENTS.event_year.tolist(), 2026]) & pmel.month.isin(MONTHS),
        ["year", "month", "pmel_wwv_1e14m3", "pmel_wwv_anom_1e14m3"],
    ]
    output = godas.merge(selected, on=("year", "month"), how="left", validate="one_to_one")
    if output.pmel_wwv_anom_1e14m3.isna().any():
        raise ValueError("PMEL WWV is missing one or more event months")
    return output


def group_composites(monthly: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for group, years in GROUPS.items():
        current = monthly.loc[monthly.year.isin(years)].copy()
        for month, values in current.groupby("month"):
            for metric in (
                "pmel_wwv_anom_1e14m3",
                "godas_wwv_anom_1e14m3",
                "zonal_170e_eastward_anom_sv",
                "meridional_5n_equatorward_anom_sv",
                "meridional_10s_equatorward_anom_sv",
            ):
                array = values[metric].to_numpy(dtype=float)
                frames.append(
                    {
                        "roni_class": group,
                        "event_years": ",".join(map(str, years)),
                        "n_events": len(years),
                        "month": int(month),
                        "metric": metric,
                        "mean": float(np.mean(array)),
                        "min": float(np.min(array)),
                        "max": float(np.max(array)),
                    }
                )
    return pd.DataFrame(frames)


def seasonal_table(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = (
        "pmel_wwv_anom_1e14m3",
        "godas_wwv_anom_1e14m3",
        "zonal_170e_eastward_anom_sv",
        "meridional_5n_equatorward_anom_sv",
        "meridional_10s_equatorward_anom_sv",
    )
    for year, current in monthly.groupby("year"):
        for season, months in SEASONS.items():
            selected = current.loc[current.month.isin(months)]
            row: dict[str, float | int | str] = {
                "year": int(year),
                "season": season,
                "roni_class": selected.roni_class.iloc[0],
            }
            for metric in metrics:
                row[metric] = float(selected[metric].mean())
            rows.append(row)
    event_rows = pd.DataFrame(rows)
    group_rows = []
    for group, years in GROUPS.items():
        for season in SEASONS:
            values = event_rows.loc[(event_rows.year.isin(years)) & (event_rows.season == season)]
            row = {"year": group, "season": season, "roni_class": group}
            for metric in metrics:
                row[metric] = float(values[metric].mean())
            group_rows.append(row)
    return pd.concat([event_rows, pd.DataFrame(group_rows)], ignore_index=True)


def plot_line_panel(axis: plt.Axes, monthly: pd.DataFrame, metric: str, title: str, ylabel: str) -> None:
    for group, years in GROUPS.items():
        matrix = np.vstack(
            [monthly.loc[monthly.year == year].sort_values("month")[metric].to_numpy() for year in years]
        )
        axis.fill_between(MONTHS, matrix.min(axis=0), matrix.max(axis=0), color=COLORS[group], alpha=0.10, lw=0)
        axis.plot(MONTHS, matrix.mean(axis=0), color=COLORS[group], lw=1.8, label=LABELS[group])
    target = monthly.loc[monthly.year == 2026].sort_values("month")
    axis.plot(MONTHS, target[metric], color=COLORS["2026"], lw=2.5, marker="o", ms=4.2, label=LABELS["2026"])
    axis.axhline(0.0, color="0.45", lw=0.75)
    axis.set_xticks(MONTHS, MONTH_LABELS)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", color="0.90", lw=0.6)


def plot_transport(monthly: pd.DataFrame) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 6.7), sharex=True, constrained_layout=True)
    plot_line_panel(axes[0, 0], monthly, "pmel_wwv_anom_1e14m3", "(a) Equatorial Pacific warm-water volume", r"WWV anomaly ($10^{14}$ m$^3$)")
    plot_line_panel(axes[0, 1], monthly, "zonal_170e_eastward_anom_sv", "(b) Eastward warm-water transport at 170°E", "Transport anomaly (Sv)")
    plot_line_panel(axes[1, 0], monthly, "meridional_5n_equatorward_anom_sv", "(c) Equatorward warm-water transport at 5°N", "Transport anomaly (Sv)")
    plot_line_panel(axes[1, 1], monthly, "meridional_10s_equatorward_anom_sv", "(d) Equatorward warm-water transport at 10°S", "Transport anomaly (Sv)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="outside upper center", ncol=4, frameon=False)
    figure.savefig(OUT / "fig01_published_wwv_and_transport_jan_jun_2026.png", bbox_inches="tight")
    figure.savefig(OUT / "fig01_published_wwv_and_transport_jan_jun_2026.pdf", bbox_inches="tight")
    plt.close(figure)


def plot_d20_profiles(profiles: dict[int, np.ndarray]) -> None:
    setup_style()
    lon = profiles[-1]
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), sharey=True, constrained_layout=True)
    for axis, (season, months) in zip(axes, SEASONS.items()):
        indices = np.array(months) - 1
        for group, years in GROUPS.items():
            matrix = np.vstack([profiles[year][indices].mean(axis=0) for year in years])
            axis.fill_between(lon, matrix.min(axis=0), matrix.max(axis=0), color=COLORS[group], alpha=0.10, lw=0)
            axis.plot(lon, matrix.mean(axis=0), color=COLORS[group], lw=1.8, label=LABELS[group])
        axis.plot(lon, profiles[2026][indices].mean(axis=0), color=COLORS["2026"], lw=2.5, label="2026")
        axis.axhline(0.0, color="0.45", lw=0.75)
        axis.set_xlim(120, 280)
        axis.set_xticks([120, 150, 180, 210, 240, 270], ["120°E", "150°E", "180°", "150°W", "120°W", "90°W"])
        axis.set_title(f"({chr(97 + list(SEASONS).index(season))}) {season} D20 anomaly")
        axis.set_xlabel("Longitude")
        axis.grid(axis="y", color="0.90", lw=0.6)
    axes[0].set_ylabel("D20 anomaly (m)")
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="outside upper center", ncol=4, frameon=False)
    figure.savefig(OUT / "fig02_published_d20_profiles_jfm_amj_2026.png", bbox_inches="tight")
    figure.savefig(OUT / "fig02_published_d20_profiles_jfm_amj_2026.pdf", bbox_inches="tight")
    plt.close(figure)


def plot_d20_hovmoller(profiles: dict[int, np.ndarray]) -> None:
    """Monthly longitude evolution of D20 using the published thermocline metric."""
    setup_style()
    lon = profiles[-1]
    fields: dict[str, np.ndarray] = {
        group: np.mean([profiles[year] for year in years], axis=0)
        for group, years in GROUPS.items()
    }
    fields["2026"] = profiles[2026]
    vmax = max(float(np.nanpercentile(np.abs(field), 99.0)) for field in fields.values())
    vmax = max(10.0, min(60.0, np.ceil(vmax / 5.0) * 5.0))
    levels = np.linspace(-vmax, vmax, 25)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    figure, axes = plt.subplots(2, 2, figsize=(10.2, 6.4), sharex=True, sharey=True, constrained_layout=True)
    image = None
    for axis, category in zip(axes.flat, ("moderate", "strong", "very_strong", "2026")):
        image = axis.contourf(lon, MONTHS, fields[category], levels=levels, cmap="RdBu_r", norm=norm, extend="both")
        axis.contour(lon, MONTHS, fields[category], levels=[0.0], colors="0.35", linewidths=0.7)
        axis.set_title(LABELS[category])
        axis.set_xlim(120.0, 280.0)
        axis.set_xticks([120, 150, 180, 210, 240, 270], ["120°E", "150°E", "180°", "150°W", "120°W", "90°W"])
        axis.set_yticks(MONTHS, MONTH_LABELS)
        axis.invert_yaxis()
    for axis in axes[:, 0]:
        axis.set_ylabel("Month")
    for axis in axes[1, :]:
        axis.set_xlabel("Longitude")
    if image is None:
        raise RuntimeError("D20 Hovmöller was not built")
    colorbar = figure.colorbar(image, ax=axes, orientation="horizontal", fraction=0.065, pad=0.08, aspect=45)
    colorbar.set_label("D20 anomaly (m)")
    figure.savefig(OUT / "fig04_published_d20_hovmoller_jan_jun_2026.png", bbox_inches="tight")
    figure.savefig(OUT / "fig04_published_d20_hovmoller_jan_jun_2026.pdf", bbox_inches="tight")
    plt.close(figure)


def plot_vertical_sections(profiles: dict[int, np.ndarray], sections: dict[int, np.ndarray]) -> None:
    setup_style()
    lon = profiles[-2]
    depth = profiles[-3]
    fields: dict[tuple[str, str], np.ndarray] = {}
    categories = ("moderate", "strong", "very_strong", "2026")
    for season, months in SEASONS.items():
        indices = np.array(months) - 1
        for category in categories:
            if category == "2026":
                field = sections[2026][indices].mean(axis=0)
            else:
                field = np.mean([sections[year][indices].mean(axis=0) for year in GROUPS[category]], axis=0)
            fields[(season, category)] = field
    vmax = max(float(np.nanpercentile(np.abs(field), 98.5)) for field in fields.values())
    vmax = max(1.0, min(6.0, np.ceil(vmax * 2.0) / 2.0))
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    figure, axes = plt.subplots(2, 4, figsize=(12.2, 5.6), sharex=True, sharey=True, constrained_layout=True)
    image = None
    for row, season in enumerate(SEASONS):
        for col, category in enumerate(categories):
            axis = axes[row, col]
            image = axis.pcolormesh(lon, depth, fields[(season, category)], shading="auto", cmap="RdBu_r", norm=norm)
            axis.invert_yaxis()
            axis.set_title(f"{season} — {LABELS[category]}")
            axis.set_xticks([120, 180, 240, 280], ["120°E", "180°", "120°W", "80°W"])
            if row == 1:
                axis.set_xlabel("Longitude")
            if col == 0:
                axis.set_ylabel("Depth (m)")
    if image is None:
        raise RuntimeError("vertical-section plot was not built")
    colorbar = figure.colorbar(image, ax=axes, orientation="horizontal", fraction=0.06, pad=0.08, aspect=45)
    colorbar.set_label("Potential-temperature anomaly (°C)")
    figure.savefig(OUT / "fig03_published_vertical_temperature_sections_2026.png", bbox_inches="tight")
    figure.savefig(OUT / "fig03_published_vertical_temperature_sections_2026.pdf", bbox_inches="tight")
    plt.close(figure)


def validation(monthly: pd.DataFrame) -> dict[str, float]:
    x = monthly.godas_wwv_anom_1e14m3.to_numpy(dtype=float)
    y = monthly.pmel_wwv_anom_1e14m3.to_numpy(dtype=float)
    correlation = float(np.corrcoef(x, y)[0, 1])
    target = monthly.loc[monthly.year == 2026]
    return {
        "n_event_months": int(len(monthly)),
        "godas_vs_pmel_wwv_anomaly_r": correlation,
        "godas_vs_pmel_wwv_anomaly_rmse_1e14m3": float(np.sqrt(np.mean((x - y) ** 2))),
        "2026_d20_min_m": float(monthly.loc[monthly.year == 2026, "d20_profile_min_m"].min()),
        "2026_d20_max_m": float(monthly.loc[monthly.year == 2026, "d20_profile_max_m"].max()),
        "2026_transport_abs_max_sv": float(
            target[
                [
                    "zonal_170e_eastward_anom_sv",
                    "meridional_5n_equatorward_anom_sv",
                    "meridional_10s_equatorward_anom_sv",
                ]
            ].abs().to_numpy().max()
        ),
    }


def write_summary(monthly: pd.DataFrame, seasonal: pd.DataFrame, qa: dict[str, float]) -> None:
    target = seasonal.loc[seasonal.year == 2026].set_index("season")
    group = seasonal.loc[seasonal.year.isin(GROUPS)].set_index(["year", "season"])
    lines = [
        "# 2026 ENSO充电过程：仅采用已发表方法的诊断",
        "",
        "## 方法边界",
        "",
        "- NOAA/PMEL WWV：20°C等温面以上、5°S–5°N和120°E–80°W的暖水体积；异常由PMEL官方序列直接提供。",
        "- D20：按Li et al. (2022)将20°C等温面深度作为热带太平洋温跃层结构，比较JFM和AMJ的经向平均经度剖面。",
        "- 暖水输送：按Chakravorty et al. (2021)的固定边界，计算170°E（10°S–5°N）东向输送，以及5°N、10°S（140°E–80°W）向赤道输送；均从海表积分到逐格、逐月D20。",
        "- 输送异常以GODAS 1991–2020同历月气候态为基准。断面位置、积分上下限和正方向沿用文献；为保留截至2026年6月的实时月演变，本图未施加文献中的3个月平滑。",
        "- 强度分组：NOAA/CPC RONI，moderate=1.0–<1.5°C，strong=1.5–<2.0°C，very strong≥2.0°C；不合并strong与very strong。2026尚未成熟，因此不预先归类。",
        "- 没有使用相似度评分、经验权重、最佳经度搜索或自定义净输送指数。",
        "",
        "## 2026直接结果",
        "",
    ]
    for season in SEASONS:
        row = target.loc[season]
        lines.extend(
            [
                f"### {season}",
                "",
                f"- PMEL标准WWV异常：{row.pmel_wwv_anom_1e14m3:+.2f} × 10^14 m³。",
                f"- 170°E东向暖水输送异常：{row.zonal_170e_eastward_anom_sv:+.1f} Sv。",
                f"- 5°N向赤道暖水输送异常：{row.meridional_5n_equatorward_anom_sv:+.1f} Sv。",
                f"- 10°S向赤道暖水输送异常：{row.meridional_10s_equatorward_anom_sv:+.1f} Sv。",
                "",
            ]
        )
    lines.extend(["## 与官方强度组的直接比较", ""])
    for season in SEASONS:
        lines.append(f"### {season}")
        lines.append("")
        for category in ("moderate", "strong", "very_strong"):
            row = group.loc[(category, season)]
            lines.append(
                f"- {LABELS[category]}：WWV {row.pmel_wwv_anom_1e14m3:+.2f} × 10^14 m³；"
                f"170°E {row.zonal_170e_eastward_anom_sv:+.1f} Sv；"
                f"5°N {row.meridional_5n_equatorward_anom_sv:+.1f} Sv；"
                f"10°S {row.meridional_10s_equatorward_anom_sv:+.1f} Sv。"
            )
        lines.append("")
    jfm = target.loc["JFM"]
    amj = target.loc["AMJ"]
    very_strong_jfm = group.loc[("very_strong", "JFM")]
    very_strong_amj = group.loc[("very_strong", "AMJ")]
    lines.extend(
        [
            "## 核心判断",
            "",
            f"1. 2026年1–6月处于显著正充电状态：JFM和AMJ的PMEL WWV异常分别为{jfm.pmel_wwv_anom_1e14m3:+.2f}和{amj.pmel_wwv_anom_1e14m3:+.2f} × 10^14 m³，分别高于very-strong事件同期合成均值{jfm.pmel_wwv_anom_1e14m3 - very_strong_jfm.pmel_wwv_anom_1e14m3:+.2f}和{amj.pmel_wwv_anom_1e14m3 - very_strong_amj.pmel_wwv_anom_1e14m3:+.2f} × 10^14 m³。",
            f"2. JFM充电具有明显路径不对称性：170°E东向输送为{jfm.zonal_170e_eastward_anom_sv:+.1f} Sv、5°N向赤道输送为{jfm.meridional_5n_equatorward_anom_sv:+.1f} Sv，而10°S向赤道输送为{jfm.meridional_10s_equatorward_anom_sv:+.1f} Sv；即主要由西边界方向的东向输入和北侧向赤道输入共同支持，南侧没有同步贡献。",
            f"3. AMJ的WWV继续维持高值，但170°E和5°N输送分别降至{amj.zonal_170e_eastward_anom_sv:+.1f}和{amj.meridional_5n_equatorward_anom_sv:+.1f} Sv，10°S仍为{amj.meridional_10s_equatorward_anom_sv:+.1f} Sv。因此更稳妥的表述是‘JFM至4月快速充电，随后以高WWV储存和维持为主’，而不是‘强流量持续到6月’。",
            "4. D20和垂向温度剖面显示，2026由JFM西—中太平洋的次表层增暖，发展为AMJ中—东太平洋温跃层加深和暖异常东伸；形态上落在very-strong事件的历史结构范围附近，但本文没有构造相似度分数，也不据此预判2026最终事件强度。",
            "",
        ]
    )
    lines.extend(
        [
            "## QA与限制",
            "",
            f"- GODAS自算WWV异常与NOAA/PMEL官方WWV在所选10个年份1–6月共{qa['n_event_months']}个月上的相关为r={qa['godas_vs_pmel_wwv_anomaly_r']:.3f}。主结论优先采用PMEL官方WWV。",
            "- GODAS流速为资料同化产品；流量是跨固定断面的实际体积输送异常，不是由温度剖面反推的伪流量。",
            "- 三条输送曲线不能简单相加成闭合收支，因为本文没有计算东边界、跨20°C等温面的水团转化以及表面淡水项。",
            "- strong组只有1986和2009两次事件，组均值只能作为描述性参照，不能据此声称强度组间差异显著。",
            "",
            "## 参考文献",
            "",
            "- Meinen, C. S., & McPhaden, M. J. (2000). Observations of warm water volume changes in the equatorial Pacific and their relationship to El Niño and La Niña. Journal of Climate, 13, 3551–3559.",
            "- Chakravorty, S., Perez, R. C., Gnanaseelan, C., & Anderson, B. T. (2021). Revisiting the recharge and discharge processes for different flavors of El Niño. JGR: Oceans, 126, e2020JC017075.",
            "- Li et al. (2022). On the asymmetry of the tropical Pacific thermocline fluctuation associated with ENSO recharge and discharge. Geophysical Research Letters, 49, e2022GL099242.",
            "- NOAA/CPC Relative Oceanic Niño Index and strength thresholds; NOAA/PMEL TAO warm-water-volume archive.",
        ]
    )
    (OUT / "PUBLISHED_METHODS_RECHARGE_RESULT_CN.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    godas, profiles, sections = build_godas_diagnostics()
    monthly = attach_pmel(godas, parse_pmel_wwv()).sort_values(["year", "month"])
    composites = group_composites(monthly)
    seasonal = seasonal_table(monthly)
    qa = validation(monthly)

    monthly.to_csv(DATA_OUT / "published_method_event_monthly_diagnostics.csv", index=False)
    composites.to_csv(DATA_OUT / "published_method_group_monthly_composites.csv", index=False)
    seasonal.to_csv(DATA_OUT / "published_method_event_and_group_seasonal_summary.csv", index=False)
    (DATA_OUT / "published_method_qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    np.savez_compressed(
        DATA_OUT / "published_method_d20_and_vertical_sections.npz",
        d20_lon=profiles[-1],
        section_lon=profiles[-2],
        section_depth=profiles[-3],
        **{f"d20_{year}": profiles[year] for year in [*EVENTS.event_year.tolist(), 2026]},
        **{f"temp_section_{year}": sections[year] for year in [*EVENTS.event_year.tolist(), 2026]},
    )
    plot_transport(monthly)
    plot_d20_profiles(profiles)
    plot_d20_hovmoller(profiles)
    plot_vertical_sections(profiles, sections)
    write_summary(monthly, seasonal, qa)
    print(json.dumps(qa, indent=2))
    print(seasonal.loc[seasonal.year.isin([2026, "moderate", "strong", "very_strong"])].to_string(index=False))


if __name__ == "__main__":
    main()
