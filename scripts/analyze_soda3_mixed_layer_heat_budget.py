#!/usr/bin/env python3
"""Diagnose the spring mixed-layer heat budget and dateline warm-water gate.

The analysis uses the compact SODA3.15.2 January-June equatorial Pacific
subsets already prepared for 1980-2024. It asks two process questions:

1. Is water warmer than 20 degC actually transported eastward across the
   dateline and retained between 180E and 140W?
2. Which monthly-mean mixed-layer heat-budget terms accompany eastern
   Pacific warming?

The budget is diagnostic rather than exactly closed. It is based on monthly
mean fields. The residual contains entrainment, unresolved covariance,
vertical/lateral mixing, numerical effects, and assimilation increments.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


TEMP_NC = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
PROCESS_NC = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
)
MONTHLY_BASE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_monthly_predictors_1982_2023.csv"
)
EVENT_BASE_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "ep_cp_two_gate_event_summary_1982_2023.csv"
)

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_mixed_layer_budget"
OUT_PDF = ROOT / "output/pdf"
INDEX_CSV = OUT_DATA / "soda3_mixed_layer_budget_indices_1980_2024.csv"
TRANSPORT_CSV = OUT_DATA / "soda3_warm_transport_longitude_1980_2024.csv"
EVENT_CSV = OUT_DATA / "soda3_mixed_layer_budget_event_summary_1982_2023.csv"
CORR_CSV = OUT_DATA / "soda3_mixed_layer_budget_event_correlations.csv"
MONTHLY_CORR_CSV = (
    OUT_DATA / "soda3_mixed_layer_budget_monthly_event_correlations.csv"
)
DIAGNOSTICS_JSON = OUT_DATA / "soda3_mixed_layer_budget_diagnostics.json"
FIGURE_PNG = OUT_DIR / "soda3_mixed_layer_budget_transition_evidence.png"
FIGURE_PDF = OUT_PDF / "soda3_mixed_layer_budget_transition_evidence.pdf"
HOV_PNG = OUT_DIR / "soda3_dateline_warm_transport_hovmoller.png"
HOV_PDF = OUT_PDF / "soda3_dateline_warm_transport_hovmoller.pdf"
SUMMARY_MD = OUT_DIR / "SODA3_MIXED_LAYER_BUDGET_RESULTS_CN.md"

MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
BASELINE = (1980, 2024)
TARGET_EVENTS = (1997, 2015, 2023)
CP_EVENTS = (1994, 2004, 2019)
GATE_LONGITUDES = np.arange(150.0, 241.0, 5.0)

RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
SECONDS_PER_MONTH = 30.4375 * 86400.0
PERMUTATION_SAMPLES = 20_000

REGIONS = {
    "west": (130.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 280.0),
}

EVENT_FEATURES = {
    "q20_dateline_pw": "Dateline warm-heat transport",
    "q20_200e_pw": "200°E warm-heat transport",
    "q20_220e_pw": "140°W warm-heat transport",
    "q20_zonal_convergence_180_220_wm2": "180°–140°W zonal convergence",
    "warm_excess_east_tendency_wm2": "Eastern warm-content tendency",
    "ml_temp_tendency_east_kmonth": "Eastern mixed-layer warming",
    "ml_hadv_interval_east_kmonth": "Mixed-layer horizontal advection",
    "ml_vadv_interval_east_kmonth": "Mixed-layer vertical advection",
    "ml_surface_interval_east_kmonth": "Mixed-layer surface heating",
    "ml_residual_east_kmonth": "Unresolved/entrainment residual",
    "barrier_east_m": "Eastern barrier-layer thickness",
    "mld_east_m": "Eastern density mixed-layer depth",
}

MONTHLY_FEATURES = {
    "q20_dateline_pw": "Dateline transport",
    "q20_220e_pw": "140°W transport",
    "q20_zonal_convergence_180_220_wm2": "Zonal convergence",
    "warm_excess_east_tendency_wm2": "Eastern warm-content tendency",
    "ml_vadv_interval_east_kmonth": "Vertical advection",
    "barrier_east_m": "Barrier layer",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.1,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.2,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.3,
            "ytick.labelsize": 8.3,
            "legend.fontsize": 7.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def cell_areas(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    dlat = float(np.median(np.diff(lat)))
    dlon = float(np.median(np.diff(lon)))
    south = np.deg2rad(lat - dlat / 2.0)
    north = np.deg2rad(lat + dlat / 2.0)
    area_lat = EARTH_RADIUS**2 * (np.sin(north) - np.sin(south))
    return area_lat[:, None] * np.deg2rad(dlon) * np.ones((1, len(lon)))


def depth_bounds(depth: np.ndarray, maximum: float = 300.0) -> np.ndarray:
    bounds = np.empty(len(depth) + 1, dtype=float)
    bounds[0] = 0.0
    bounds[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    bounds[-1] = min(
        maximum,
        depth[-1] + 0.5 * (depth[-1] - depth[-2]),
    )
    return bounds


def vertical_thickness(depth: np.ndarray, maximum: float = 300.0) -> np.ndarray:
    return np.diff(depth_bounds(depth, maximum))


def interpolate_velocity_to_tracer(
    velocity: np.ndarray,
    u_lat: np.ndarray,
    u_lon: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
) -> np.ndarray:
    if (
        velocity.shape[-2:] == (len(lat) + 1, len(lon) + 1)
        and np.allclose(0.5 * (u_lat[:-1] + u_lat[1:]), lat)
        and np.allclose(0.5 * (u_lon[:-1] + u_lon[1:]), lon)
    ):
        return 0.25 * (
            velocity[:, :-1, :-1]
            + velocity[:, 1:, :-1]
            + velocity[:, :-1, 1:]
            + velocity[:, 1:, 1:]
        )
    raise ValueError("Velocity and tracer grids are not the expected pair")


def mixed_layer_mean(
    field: np.ndarray,
    mld: np.ndarray,
    depth: np.ndarray,
) -> np.ndarray:
    """Vertically average a 3-D field from the surface to local MLD."""
    bounds = depth_bounds(depth)
    top = bounds[:-1, None, None]
    bottom = bounds[1:, None, None]
    effective_mld = np.clip(mld, 5.0, bounds[-1])
    overlap = np.maximum(
        0.0,
        np.minimum(bottom, effective_mld[None, :, :]) - top,
    )
    valid = np.isfinite(field)
    numerator = np.nansum(field * overlap, axis=0)
    denominator = np.sum(overlap * valid, axis=0)
    return np.divide(
        numerator,
        denominator,
        out=np.full(mld.shape, np.nan, dtype=float),
        where=denominator > 0.0,
    )


def area_mean(
    field: np.ndarray,
    areas: np.ndarray,
    lon: np.ndarray,
    bounds: tuple[float, float],
) -> float:
    selected = (lon >= bounds[0]) & (lon <= bounds[1])
    values = field[:, selected]
    weights = areas[:, selected]
    valid = np.isfinite(values)
    denominator = np.sum(weights * valid)
    if denominator == 0.0:
        return np.nan
    return float(np.nansum(values * weights) / denominator)


def warm_section_diagnostics(
    temperature: np.ndarray,
    u_velocity: np.ndarray,
    *,
    depth: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    u_lat: np.ndarray,
    u_lon: np.ndarray,
    longitude: float,
) -> tuple[float, float, float]:
    """Return warm-heat transport, warm-volume transport, and warm content.

    Heat transport is relative to 20 degC and therefore isolates transport
    of the thermocline warm-water reservoir rather than arbitrary enthalpy.
    Positive transport is eastward.
    """
    u_index = int(np.argmin(np.abs(u_lon - longitude)))
    if abs(float(u_lon[u_index]) - longitude) > 0.26:
        raise ValueError(f"No velocity longitude close to {longitude}")
    left = np.flatnonzero(lon < longitude)
    right = np.flatnonzero(lon > longitude)
    if left.size == 0 or right.size == 0:
        raise ValueError(f"Longitude {longitude} is outside tracer grid")
    left_index = int(left[-1])
    right_index = int(right[0])

    boundary_temp = 0.5 * (
        temperature[:, :, left_index] + temperature[:, :, right_index]
    )
    boundary_u = 0.5 * (
        u_velocity[:, :-1, u_index] + u_velocity[:, 1:, u_index]
    )
    if boundary_temp.shape != boundary_u.shape:
        raise ValueError("Boundary temperature and velocity shapes differ")
    if not np.allclose(0.5 * (u_lat[:-1] + u_lat[1:]), lat):
        raise ValueError("Velocity latitude is not staggered around tracer")

    dz = vertical_thickness(depth)[:, None]
    dlat = float(np.median(np.diff(lat)))
    south = np.deg2rad(lat - dlat / 2.0)
    north = np.deg2rad(lat + dlat / 2.0)
    dy = EARTH_RADIUS * (north - south)
    section_area = dz * dy[None, :]

    valid = np.isfinite(boundary_temp) & np.isfinite(boundary_u)
    warm_excess = np.where(
        valid,
        np.maximum(boundary_temp - 20.0, 0.0),
        np.nan,
    )
    warm_mask = np.where(valid, boundary_temp >= 20.0, False)
    heat_transport_w = RHO0 * CP0 * np.nansum(
        boundary_u * warm_excess * section_area
    )
    volume_transport_m3s = np.nansum(
        boundary_u * warm_mask * section_area
    )
    warm_heat_per_m_jm = RHO0 * CP0 * np.nansum(
        warm_excess * section_area
    )
    return (
        float(heat_transport_w / 1.0e15),
        float(volume_transport_m3s / 1.0e6),
        float(warm_heat_per_m_jm / 1.0e9),
    )


def same_month_residual(
    values: np.ndarray,
    times: pd.DatetimeIndex,
) -> np.ndarray:
    """Remove the 1980-2024 calendar-month climatology and linear trend."""
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in MONTHS:
        selected = (times.month == month) & np.isfinite(values)
        baseline = (
            selected
            & (times.year >= BASELINE[0])
            & (times.year <= BASELINE[1])
        )
        years = times.year[baseline].astype(float)
        fit_values = values[baseline]
        if len(fit_values) < 3:
            continue
        design = np.column_stack([np.ones(len(years)), years])
        intercept, slope = np.linalg.lstsq(
            design,
            fit_values,
            rcond=None,
        )[0]
        output[selected] = values[selected] - (
            intercept + slope * times.year[selected].astype(float)
        )
    return output


def derive_monthly_fields(
    temperature_dataset: xr.Dataset,
    process_dataset: xr.Dataset,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    times = pd.DatetimeIndex(temperature_dataset.time.values)
    process_times = pd.DatetimeIndex(process_dataset.time.values)
    if not times.equals(process_times):
        raise ValueError("Temperature and process times do not match")
    depth = temperature_dataset.depth.values.astype(float)
    lat = temperature_dataset.lat.values.astype(float)
    lon = temperature_dataset.lon.values.astype(float)
    u_lat = process_dataset.u_lat.values.astype(float)
    u_lon = process_dataset.u_lon.values.astype(float)
    areas = cell_areas(lat, lon)
    dz = vertical_thickness(depth)[:, None, None]
    lat_radians = np.deg2rad(lat)
    lon_radians = np.deg2rad(lon)

    rows: list[dict[str, float | int | pd.Timestamp]] = []
    transport_rows: list[dict[str, float | int | pd.Timestamp]] = []
    for time_index, timestamp in enumerate(times):
        temperature = (
            temperature_dataset.temp.isel(time=time_index).values.astype(float)
        )
        raw_u = process_dataset.u.isel(time=time_index).values.astype(float)
        raw_v = process_dataset.v.isel(time=time_index).values.astype(float)
        u = interpolate_velocity_to_tracer(
            raw_u,
            u_lat,
            u_lon,
            lat,
            lon,
        )
        v = interpolate_velocity_to_tracer(
            raw_v,
            u_lat,
            u_lon,
            lat,
            lon,
        )
        wt = process_dataset.wt.isel(time=time_index).values.astype(float)
        mld = process_dataset.mlp.isel(time=time_index).values.astype(float)
        ild = process_dataset.mlt.isel(time=time_index).values.astype(float)
        net_heating = (
            process_dataset.net_heating.isel(time=time_index).values.astype(float)
        )

        dtdlambda = np.gradient(temperature, lon_radians, axis=2)
        dtdx = dtdlambda / (
            EARTH_RADIUS * np.cos(lat_radians)[None, :, None]
        )
        dtdy = np.gradient(temperature, lat_radians, axis=1) / EARTH_RADIUS
        dtdz = np.gradient(temperature, depth, axis=0)
        horizontal = -(u * dtdx + v * dtdy) * SECONDS_PER_MONTH
        # SODA wt is positive upward while depth is positive downward.
        vertical = wt * dtdz * SECONDS_PER_MONTH
        surface = (
            net_heating
            / (RHO0 * CP0 * np.maximum(mld, 5.0))
            * SECONDS_PER_MONTH
        )

        ml_temperature = mixed_layer_mean(temperature, mld, depth)
        ml_horizontal = mixed_layer_mean(horizontal, mld, depth)
        ml_vertical = mixed_layer_mean(vertical, mld, depth)
        barrier = np.maximum(ild - mld, 0.0)

        warm_excess_column = RHO0 * CP0 * np.nansum(
            np.maximum(temperature - 20.0, 0.0) * dz,
            axis=0,
        )
        row: dict[str, float | int | pd.Timestamp] = {
            "time": timestamp,
            "year": timestamp.year,
            "month": timestamp.month,
            "ml_temp_east_c": area_mean(
                ml_temperature,
                areas,
                lon,
                REGIONS["east"],
            ),
            "ml_hadv_east_kmonth": area_mean(
                ml_horizontal,
                areas,
                lon,
                REGIONS["east"],
            ),
            "ml_vadv_east_kmonth": area_mean(
                ml_vertical,
                areas,
                lon,
                REGIONS["east"],
            ),
            "ml_surface_east_kmonth": area_mean(
                surface,
                areas,
                lon,
                REGIONS["east"],
            ),
            "net_heating_east_wm2": area_mean(
                net_heating,
                areas,
                lon,
                REGIONS["east"],
            ),
            "mld_east_m": area_mean(mld, areas, lon, REGIONS["east"]),
            "barrier_east_m": area_mean(
                barrier,
                areas,
                lon,
                REGIONS["east"],
            ),
            "warm_excess_east_jm2": area_mean(
                warm_excess_column,
                areas,
                lon,
                REGIONS["east"],
            ),
        }

        gate_values: dict[float, tuple[float, float, float]] = {}
        for gate_lon in GATE_LONGITUDES:
            diagnostics = warm_section_diagnostics(
                temperature,
                raw_u,
                depth=depth,
                lat=lat,
                lon=lon,
                u_lat=u_lat,
                u_lon=u_lon,
                longitude=float(gate_lon),
            )
            gate_values[float(gate_lon)] = diagnostics
            transport_rows.append(
                {
                    "time": timestamp,
                    "year": timestamp.year,
                    "month": timestamp.month,
                    "longitude_e": float(gate_lon),
                    "q20_pw": diagnostics[0],
                    "warm_volume_transport_sv": diagnostics[1],
                    "warm_heat_section_gj_per_m": diagnostics[2],
                }
            )
        row["q20_dateline_pw"] = gate_values[180.0][0]
        row["q20_200e_pw"] = gate_values[200.0][0]
        row["q20_220e_pw"] = gate_values[220.0][0]
        row["warm_volume_dateline_sv"] = gate_values[180.0][1]
        row["warm_volume_200e_sv"] = gate_values[200.0][1]

        central_area = float(
            np.sum(areas[:, (lon >= 180.0) & (lon <= 220.0)])
        )
        row["q20_zonal_convergence_180_220_wm2"] = (
            (gate_values[180.0][0] - gate_values[220.0][0])
            * 1.0e15
            / central_area
        )
        rows.append(row)
        if (time_index + 1) % 30 == 0 or time_index + 1 == len(times):
            print(
                f"Derived mixed-layer fields {time_index + 1}/{len(times)}",
                flush=True,
            )
    return pd.DataFrame(rows), pd.DataFrame(transport_rows)


def add_interval_budget(indices: pd.DataFrame) -> pd.DataFrame:
    indices = indices.sort_values(["year", "month"]).reset_index(drop=True)
    previous = indices.groupby("year", sort=False).shift(1)
    dt_seconds = (
        pd.to_datetime(indices["time"]) - pd.to_datetime(previous["time"])
    ).dt.total_seconds()
    same_sequence = indices["month"].eq(previous["month"] + 1)
    scale = np.where(
        same_sequence,
        SECONDS_PER_MONTH / dt_seconds,
        np.nan,
    )
    indices["ml_temp_tendency_east_kmonth"] = (
        indices["ml_temp_east_c"] - previous["ml_temp_east_c"]
    ) * scale
    indices["warm_excess_east_tendency_wm2"] = (
        indices["warm_excess_east_jm2"]
        - previous["warm_excess_east_jm2"]
    ) / dt_seconds.where(same_sequence)
    for source, destination in (
        ("ml_hadv_east_kmonth", "ml_hadv_interval_east_kmonth"),
        ("ml_vadv_east_kmonth", "ml_vadv_interval_east_kmonth"),
        ("ml_surface_east_kmonth", "ml_surface_interval_east_kmonth"),
    ):
        indices[destination] = 0.5 * (
            indices[source] + previous[source]
        )
        indices.loc[~same_sequence, destination] = np.nan
    resolved = (
        indices["ml_hadv_interval_east_kmonth"]
        + indices["ml_vadv_interval_east_kmonth"]
        + indices["ml_surface_interval_east_kmonth"]
    )
    indices["ml_residual_east_kmonth"] = (
        indices["ml_temp_tendency_east_kmonth"] - resolved
    )
    return indices


def add_anomalies(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    times = pd.DatetimeIndex(frame["time"])
    for column in columns:
        frame[f"{column}_anom"] = same_month_residual(
            frame[column].to_numpy(dtype=float),
            times,
        )
    return frame


def add_transport_anomalies(transport: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for _, current in transport.groupby("longitude_e", sort=True):
        current = current.sort_values("time").copy()
        times = pd.DatetimeIndex(current["time"])
        for column in (
            "q20_pw",
            "warm_volume_transport_sv",
            "warm_heat_section_gj_per_m",
        ):
            current[f"{column}_anom"] = same_month_residual(
                current[column].to_numpy(dtype=float),
                times,
            )
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True).sort_values(
        ["time", "longitude_e"]
    )


def permutation_correlation(
    x: np.ndarray,
    y: np.ndarray,
    seed: int,
) -> tuple[float, float, int]:
    valid = np.isfinite(x) & np.isfinite(y)
    x = np.asarray(x[valid], dtype=float)
    y = np.asarray(y[valid], dtype=float)
    if len(x) < 4:
        return np.nan, np.nan, len(x)
    observed = float(np.corrcoef(x, y)[0, 1])
    rng = np.random.default_rng(seed)
    null = np.empty(PERMUTATION_SAMPLES, dtype=float)
    for index in range(PERMUTATION_SAMPLES):
        null[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    p_value = float(
        (np.sum(np.abs(null) >= abs(observed)) + 1)
        / (PERMUTATION_SAMPLES + 1)
    )
    return observed, p_value, len(x)


def benjamini_hochberg(values: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna()
    if valid.empty:
        return output
    order = valid.sort_values().index
    ranked = valid.loc[order].to_numpy(dtype=float)
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output.loc[order] = np.minimum(adjusted, 1.0)
    return output


def build_event_tables(
    indices: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly_base = pd.read_csv(MONTHLY_BASE_CSV)
    event_base = pd.read_csv(EVENT_BASE_CSV)
    merged = monthly_base.merge(
        indices,
        on=["year", "month"],
        how="left",
        suffixes=("", "_soda"),
        validate="one_to_one",
    )
    event_rows = []
    for event_year in event_base["event_year"].astype(int):
        current = merged.loc[
            merged["year"].eq(event_year) & merged["month"].isin([5, 6])
        ]
        base_row = event_base.loc[
            event_base["event_year"].eq(event_year)
        ].iloc[0]
        row: dict[str, float | int | str] = {
            "event_year": event_year,
            "event_label": base_row["event_label"],
            "mature_djf_type_index_c": base_row[
                "mature_djf_type_index_c"
            ],
            "mature_djf_nino34_c": base_row["mature_djf_nino34_c"],
            "mature_flavor": base_row["mature_flavor"],
            "fep_residual_may_jun_c": current["fep_residual_c"].mean(),
        }
        for feature in EVENT_FEATURES:
            row[f"{feature}_may_jun_anom"] = current[
                f"{feature}_anom"
            ].mean()
        event_rows.append(row)
    events = pd.DataFrame(event_rows)

    correlation_rows = []
    target = events["mature_djf_type_index_c"].to_numpy(dtype=float)
    for seed, (feature, label) in enumerate(EVENT_FEATURES.items(), 300):
        x = events[f"{feature}_may_jun_anom"].to_numpy(dtype=float)
        correlation, p_value, n_events = permutation_correlation(
            x,
            target,
            seed,
        )
        correlation_rows.append(
            {
                "feature": feature,
                "label": label,
                "correlation_with_djf_nino3_minus_nino4": correlation,
                "two_sided_permutation_p": p_value,
                "n_events": n_events,
            }
        )
    correlations = pd.DataFrame(correlation_rows)
    correlations["bh_fdr_q_across_event_family"] = benjamini_hochberg(
        correlations["two_sided_permutation_p"]
    )

    event_monthly = merged.loc[
        merged["year"].isin(event_base["event_year"].astype(int))
    ].copy()
    monthly_rows = []
    seed = 700
    for month in range(2, 7):
        current = event_monthly.loc[event_monthly["month"].eq(month)]
        target = current["mature_djf_type_index_c"].to_numpy(dtype=float)
        for feature, label in MONTHLY_FEATURES.items():
            correlation, p_value, n_events = permutation_correlation(
                current[f"{feature}_anom"].to_numpy(dtype=float),
                target,
                seed,
            )
            seed += 1
            monthly_rows.append(
                {
                    "month": month,
                    "feature": feature,
                    "label": label,
                    "correlation_with_djf_nino3_minus_nino4": correlation,
                    "two_sided_permutation_p": p_value,
                    "n_events": n_events,
                }
            )
    monthly_correlations = pd.DataFrame(monthly_rows)
    monthly_correlations["bh_fdr_q_across_month_feature_family"] = (
        benjamini_hochberg(
            monthly_correlations["two_sided_permutation_p"]
        )
    )
    return events, correlations, monthly_correlations


def event_or_composite_series(
    frame: pd.DataFrame,
    column: str,
    event: int | tuple[int, ...],
) -> np.ndarray:
    if isinstance(event, tuple):
        selected = frame.loc[frame["year"].isin(event)]
        return (
            selected.groupby("month")[column]
            .mean()
            .reindex(MONTHS)
            .to_numpy(dtype=float)
        )
    return (
        frame.loc[frame["year"].eq(event)]
        .set_index("month")[column]
        .reindex(MONTHS)
        .to_numpy(dtype=float)
    )


def plot_transition_evidence(
    indices: pd.DataFrame,
    events: pd.DataFrame,
    correlations: pd.DataFrame,
    monthly_correlations: pd.DataFrame,
) -> None:
    setup_style()
    figure, axes = plt.subplots(2, 2, figsize=(11.2, 8.2))
    figure.subplots_adjust(
        left=0.08,
        right=0.98,
        bottom=0.10,
        top=0.90,
        wspace=0.32,
        hspace=0.42,
    )

    current = correlations.sort_values(
        "correlation_with_djf_nino3_minus_nino4"
    )
    colors = np.where(
        current["bh_fdr_q_across_event_family"] < 0.05,
        "#B54B4B",
        np.where(
            current["bh_fdr_q_across_event_family"] < 0.10,
            "#D9995B",
            "#9AA3AA",
        ),
    )
    axes[0, 0].barh(
        np.arange(len(current)),
        current["correlation_with_djf_nino3_minus_nino4"],
        color=colors,
        height=0.72,
    )
    axes[0, 0].set_yticks(np.arange(len(current)))
    axes[0, 0].set_yticklabels(current["label"])
    axes[0, 0].axvline(0.0, color="#555555", lw=0.8)
    axes[0, 0].set_xlim(-1.0, 1.0)
    axes[0, 0].set_xlabel("Correlation with mature Niño3 − Niño4")
    axes[0, 0].set_title(
        "(a) May–June process discrimination across 13 events",
        loc="left",
        fontweight="bold",
    )
    axes[0, 0].text(
        0.01,
        -0.20,
        "Red: BH-FDR q < 0.05; orange: q < 0.10",
        transform=axes[0, 0].transAxes,
        fontsize=7.7,
        color="#555555",
    )

    pivot_r = monthly_correlations.pivot(
        index="label",
        columns="month",
        values="correlation_with_djf_nino3_minus_nino4",
    ).reindex(list(MONTHLY_FEATURES.values()))
    pivot_q = monthly_correlations.pivot(
        index="label",
        columns="month",
        values="bh_fdr_q_across_month_feature_family",
    ).reindex(list(MONTHLY_FEATURES.values()))
    image = axes[0, 1].imshow(
        pivot_r.to_numpy(),
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0),
        aspect="auto",
    )
    axes[0, 1].set_xticks(np.arange(5))
    axes[0, 1].set_xticklabels(MONTH_LABELS[1:])
    axes[0, 1].set_yticks(np.arange(len(pivot_r)))
    axes[0, 1].set_yticklabels(pivot_r.index)
    for row in range(len(pivot_r)):
        for column in range(5):
            value = pivot_r.iloc[row, column]
            q_value = pivot_q.iloc[row, column]
            marker = "*" if np.isfinite(q_value) and q_value < 0.10 else ""
            axes[0, 1].text(
                column,
                row,
                f"{value:+.2f}{marker}",
                ha="center",
                va="center",
                fontsize=7.6,
                color="white" if abs(value) > 0.55 else "#222222",
            )
    axes[0, 1].set_title(
        "(b) When does the EP/CP separation emerge?",
        loc="left",
        fontweight="bold",
    )
    colorbar = figure.colorbar(
        image,
        ax=axes[0, 1],
        orientation="vertical",
        fraction=0.046,
        pad=0.03,
    )
    colorbar.set_label("Event correlation")
    axes[0, 1].text(
        0.0,
        -0.18,
        "* BH-FDR q < 0.10 across the month × process family",
        transform=axes[0, 1].transAxes,
        fontsize=7.7,
        color="#555555",
    )

    palette = {
        1997: "#B52D2D",
        2015: "#D17A22",
        2023: "#1F6A9B",
        "CP": "#535A60",
    }
    for event in TARGET_EVENTS:
        axes[1, 0].plot(
            np.arange(1, 7),
            event_or_composite_series(
                indices,
                "q20_dateline_pw_anom",
                event,
            ),
            marker="o",
            lw=1.8,
            ms=4.3,
            color=palette[event],
            label=str(event),
        )
    axes[1, 0].plot(
        np.arange(1, 7),
        event_or_composite_series(
            indices,
            "q20_dateline_pw_anom",
            CP_EVENTS,
        ),
        marker="s",
        lw=1.8,
        ms=4.0,
        color=palette["CP"],
        label="CP composite (1994/2004/2019)",
    )
    axes[1, 0].axhline(0.0, color="#666666", lw=0.8)
    axes[1, 0].set_xticks(np.arange(1, 7))
    axes[1, 0].set_xticklabels(MONTH_LABELS)
    axes[1, 0].set_ylabel("20°C-relative eastward heat transport (PW anomaly)")
    axes[1, 0].set_title(
        "(c) Dateline entry is not the type gate",
        loc="left",
        fontweight="bold",
    )
    axes[1, 0].legend(frameon=False, ncol=2, loc="best")
    axes[1, 0].grid(axis="y", color="#DDDDDD", lw=0.6)

    budget_columns = [
        "ml_hadv_interval_east_kmonth_anom",
        "ml_vadv_interval_east_kmonth_anom",
        "ml_surface_interval_east_kmonth_anom",
        "ml_residual_east_kmonth_anom",
    ]
    budget_labels = ["Horizontal", "Vertical", "Surface", "Residual"]
    budget_colors = ["#3A78A1", "#64A96B", "#D7A33D", "#8E8E8E"]
    event_specs: list[tuple[str, int | tuple[int, ...]]] = [
        ("1997", 1997),
        ("2015", 2015),
        ("2023", 2023),
        ("CP comp.", CP_EVENTS),
    ]
    values = np.empty((len(event_specs), len(budget_columns)))
    tendency = np.empty(len(event_specs))
    for row, (_, event) in enumerate(event_specs):
        for column, feature in enumerate(budget_columns):
            series = event_or_composite_series(indices, feature, event)
            values[row, column] = np.nanmean(series[4:6])
        tendency[row] = np.nanmean(
            event_or_composite_series(
                indices,
                "ml_temp_tendency_east_kmonth_anom",
                event,
            )[4:6]
        )
    x = np.arange(len(event_specs))
    positive_bottom = np.zeros(len(event_specs))
    negative_bottom = np.zeros(len(event_specs))
    for column, (label, color) in enumerate(
        zip(budget_labels, budget_colors, strict=True)
    ):
        current_values = values[:, column]
        bottom = np.where(
            current_values >= 0.0,
            positive_bottom,
            negative_bottom,
        )
        axes[1, 1].bar(
            x,
            current_values,
            bottom=bottom,
            width=0.64,
            color=color,
            label=label,
        )
        positive_bottom += np.where(current_values > 0.0, current_values, 0.0)
        negative_bottom += np.where(current_values < 0.0, current_values, 0.0)
    axes[1, 1].scatter(
        x,
        tendency,
        marker="D",
        s=30,
        facecolor="white",
        edgecolor="#111111",
        linewidth=1.0,
        zorder=5,
        label="Observed tendency",
    )
    axes[1, 1].axhline(0.0, color="#555555", lw=0.8)
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels([item[0] for item in event_specs])
    axes[1, 1].set_ylabel("May–June mixed-layer tendency anomaly (K month⁻¹)")
    axes[1, 1].set_title(
        "(d) Eastern-Pacific diagnostic heat budget",
        loc="left",
        fontweight="bold",
    )
    axes[1, 1].legend(frameon=False, ncol=2, loc="best")
    axes[1, 1].grid(axis="y", color="#DDDDDD", lw=0.6)

    figure.suptitle(
        "SODA3 spring transition: dateline warm-water transport and mixed-layer heat budget",
        fontsize=14.0,
        fontweight="bold",
        y=0.965,
    )
    figure.text(
        0.5,
        0.026,
        "SODA3.15.2, Jan–Jun 1980–2024; 5°S–5°N. "
        "Anomalies remove the 1980–2024 calendar-month trend. "
        "Monthly-mean residual includes entrainment, mixing, transients, and assimilation increments.",
        ha="center",
        fontsize=7.8,
        color="#4C4C4C",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def plot_transport_hovmoller(transport: pd.DataFrame) -> None:
    setup_style()
    event_specs: list[tuple[str, int | tuple[int, ...]]] = [
        ("1997", 1997),
        ("2015", 2015),
        ("2023", 2023),
        ("CP composite", CP_EVENTS),
    ]
    arrays = []
    warm_arrays = []
    for _, event in event_specs:
        selected = (
            transport.loc[transport["year"].isin(event)]
            if isinstance(event, tuple)
            else transport.loc[transport["year"].eq(event)]
        )
        current = selected.pivot_table(
            index="month",
            columns="longitude_e",
            values="q20_pw_anom",
            aggfunc="mean",
        ).reindex(index=MONTHS, columns=GATE_LONGITUDES)
        warm = selected.pivot_table(
            index="month",
            columns="longitude_e",
            values="warm_heat_section_gj_per_m_anom",
            aggfunc="mean",
        ).reindex(index=MONTHS, columns=GATE_LONGITUDES)
        arrays.append(current.to_numpy(dtype=float))
        warm_arrays.append(warm.to_numpy(dtype=float))
    transport_limit = float(
        np.nanpercentile(np.abs(np.concatenate([x.ravel() for x in arrays])), 97)
    )
    warm_limit = float(
        np.nanpercentile(
            np.abs(np.concatenate([x.ravel() for x in warm_arrays])),
            90,
        )
    )
    transport_limit = max(transport_limit, 0.02)
    warm_limit = max(warm_limit, 5.0)
    warm_levels = np.array(
        [-warm_limit, -0.5 * warm_limit, 0.5 * warm_limit, warm_limit]
    )

    figure, axes = plt.subplots(
        1,
        4,
        figsize=(12.2, 4.6),
        sharex=True,
        sharey=True,
    )
    figure.subplots_adjust(
        left=0.07,
        right=0.96,
        bottom=0.24,
        top=0.80,
        wspace=0.10,
    )
    longitude_edges = np.r_[
        GATE_LONGITUDES - 2.5,
        GATE_LONGITUDES[-1] + 2.5,
    ]
    month_edges = np.arange(0.5, 7.0, 1.0)
    image = None
    for index, (axis, (label, _), values, warm) in enumerate(
        zip(axes, event_specs, arrays, warm_arrays, strict=True)
    ):
        image = axis.pcolormesh(
            longitude_edges,
            month_edges,
            values,
            cmap="RdBu_r",
            norm=TwoSlopeNorm(
                vmin=-transport_limit,
                vcenter=0.0,
                vmax=transport_limit,
            ),
            shading="flat",
        )
        if np.nanmax(warm) > warm_levels[-1]:
            axis.contour(
                GATE_LONGITUDES,
                np.arange(1, 7),
                warm,
                levels=warm_levels,
                colors="#262626",
                linewidths=0.65,
            )
        axis.axvline(180.0, color="white", lw=1.2, ls="--")
        axis.set_title(
            f"({chr(97 + index)}) {label}",
            loc="left",
            fontweight="bold",
        )
        axis.set_xticks([150, 180, 210, 240])
        axis.set_xticklabels(["150°E", "180°", "150°W", "120°W"])
        axis.set_yticks(np.arange(1, 7))
        axis.set_yticklabels(MONTH_LABELS)
        axis.invert_yaxis()
    axes[0].set_ylabel("Calendar month")
    figure.suptitle(
        "SODA3 eastward transport of the >20°C reservoir, January–June",
        fontsize=13.5,
        fontweight="bold",
        y=0.95,
    )
    colorbar_axis = figure.add_axes([0.19, 0.12, 0.62, 0.035])
    colorbar = figure.colorbar(
        image,
        cax=colorbar_axis,
        orientation="horizontal",
        extend="both",
    )
    colorbar.set_label("20°C-relative zonal heat transport anomaly (PW)")
    figure.text(
        0.5,
        0.025,
        "Dashed line: dateline. Black contours: warm-section heat-content anomaly. "
        "CP composite = 1994, 2004, 2019. Same detrended 1980–2024 monthly baseline.",
        ha="center",
        fontsize=7.8,
        color="#4C4C4C",
    )
    figure.savefig(HOV_PNG, bbox_inches="tight")
    figure.savefig(HOV_PDF, bbox_inches="tight")
    plt.close(figure)


def strongest_month_text(monthly_correlations: pd.DataFrame) -> str:
    rows = []
    for feature, label in MONTHLY_FEATURES.items():
        current = monthly_correlations.loc[
            monthly_correlations["feature"].eq(feature)
        ].sort_values(
            "correlation_with_djf_nino3_minus_nino4",
            ascending=False,
        )
        best = current.iloc[0]
        rows.append(
            f"- {label}：{MONTH_LABELS[int(best['month']) - 1]}，"
            f"r={best['correlation_with_djf_nino3_minus_nino4']:+.2f}，"
            f"q={best['bh_fdr_q_across_month_feature_family']:.3f}。"
        )
    return "\n".join(rows)


def write_summary(
    events: pd.DataFrame,
    correlations: pd.DataFrame,
    monthly_correlations: pd.DataFrame,
) -> None:
    ranked = correlations.sort_values(
        "bh_fdr_q_across_event_family"
    ).reset_index(drop=True)
    significant = ranked.loc[
        ranked["bh_fdr_q_across_event_family"] < 0.10
    ]
    significant_lines = "\n".join(
        f"- {row.label}：r="
        f"{row.correlation_with_djf_nino3_minus_nino4:+.2f}，"
        f"p={row.two_sided_permutation_p:.4f}，"
        f"q={row.bh_fdr_q_across_event_family:.3f}。"
        for row in significant.itertuples()
    )
    if not significant_lines:
        significant_lines = "- 本组检验没有通过 q<0.10 的过程量。"
    correlation_lookup = correlations.set_index("feature")
    dateline = correlation_lookup.loc["q20_dateline_pw"]
    gate_200 = correlation_lookup.loc["q20_200e_pw"]
    gate_220 = correlation_lookup.loc["q20_220e_pw"]
    convergence = correlation_lookup.loc[
        "q20_zonal_convergence_180_220_wm2"
    ]

    selected_columns = [
        "event_year",
        "mature_djf_type_index_c",
        "q20_dateline_pw_may_jun_anom",
        "q20_zonal_convergence_180_220_wm2_may_jun_anom",
        "warm_excess_east_tendency_wm2_may_jun_anom",
        "ml_temp_tendency_east_kmonth_may_jun_anom",
    ]
    selected = events.loc[
        events["event_year"].isin([*TARGET_EVENTS, *CP_EVENTS]),
        selected_columns,
    ].sort_values("event_year")
    event_lines = "\n".join(
        f"- {int(row.event_year)}：类型指数"
        f"{row.mature_djf_type_index_c:+.2f} °C；"
        f"日界线热输送{row.q20_dateline_pw_may_jun_anom:+.3f} PW；"
        f"纬向辐合{row.q20_zonal_convergence_180_220_wm2_may_jun_anom:+.1f} W m⁻²；"
        f"东部暖含量倾向{row.warm_excess_east_tendency_wm2_may_jun_anom:+.1f} W m⁻²。"
        for row in selected.itertuples()
    )

    text = f"""# SODA3 春季混合层热收支与日界线暖水闸门

## 结论

本阶段把“西太平洋有多少暖水”推进为“暖水是否真正跨过日界线，并在
中东太平洋被保留下来”。全部量采用 SODA3.15.2、1980–2024 年同月
气候态和同月线性趋势。

13 个暖事件的 5–6 月检验中，通过本组 BH-FDR q<0.10 的量为：

{significant_lines}

这组结果应与上一阶段的暖水质心、日界线以东暖水比例、D20、SSH 和
ORAS5 独立验证共同解释。日界线输送本身的相关只有
r={dateline['correlation_with_djf_nino3_minus_nino4']:+.2f}
（q={dateline['bh_fdr_q_across_event_family']:.3f}），而 200°E/160°W
输送提高到 r={gate_200['correlation_with_djf_nino3_minus_nino4']:+.2f}
（q={gate_200['bh_fdr_q_across_event_family']:.3f}），140°W输送进一步
达到 r={gate_220['correlation_with_djf_nino3_minus_nino4']:+.2f}
（q={gate_220['bh_fdr_q_across_event_family']:.3f}）。180°–140°W
“纬向辐合”的相关为
r={convergence['correlation_with_djf_nino3_minus_nino4']:+.2f}
（q={convergence['bh_fdr_q_across_event_family']:.3f}）；负号表示 EP
事件中 140°W 的向东输出常强于日界线入口，即暖水不是停留在中部，
而是继续穿过 140°W 进入东部。

因此真正的“转变点”不是暖水第一次越过 180°，而是春季输送能否向
160°W–140°W 继续推进，并伴随东部暖含量增长、垂向平流和障碍层建立。
残差虽然与事件类型相关，但其幅度很大，只能说明月平均收支遗漏的夹卷、
混合、高频协方差和同化增量重要，不能把“残差”当作一种已识别机制。

## 月份定位

{strongest_month_text(monthly_correlations)}

星号检验在 5 个过程量 × 5 个月共 25 个检验上统一控制 FDR，因此比逐图
挑选显著月份更严格。

## 代表事件

{event_lines}

## 计算定义

- 日界线暖水热输送：
  `rho*Cp*integral[u*max(T-20°C,0) dz dy]`，5°S–5°N、0–300 m，
  正值表示向东；这里报告去趋势的同月异常。
- 180°–140°W 纬向辐合：180°入口输送减去 140°W 出口输送，再除以
  区域水平面积。它只表示纬向分量，不包含 5°S/5°N 边界的经向输送。
- 混合层热收支：月际混合层温度倾向减去月平均水平平流、垂直平流和
  表面净热通量贡献，剩余记为残差。
- 残差不是单一物理过程；它包含夹卷、垂向/侧向混合、月平均遗漏的
  高频协方差、数值效应以及资料同化增量。

## 仍需的高频验证

SODA 官方提供 5 日资料。下一步只需针对代表事件下载区域子集，验证
月平均结果是否由少数西风爆发/Kelvin 波过程主导；不宜直接下载每个
约 285 MB 的完整全球文件。

## 文件

- 过程指标：`{INDEX_CSV}`
- 经度输送：`{TRANSPORT_CSV}`
- 事件表：`{EVENT_CSV}`
- 相关检验：`{CORR_CSV}`
- 月份检验：`{MONTHLY_CORR_CSV}`
- 主图：`{FIGURE_PDF}`
- 经度—月份图：`{HOV_PDF}`
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text(text, encoding="utf-8")


def validate_outputs(
    indices: pd.DataFrame,
    transport: pd.DataFrame,
    events: pd.DataFrame,
) -> None:
    if len(indices) != 45 * 6:
        raise ValueError(f"Expected 270 index rows, found {len(indices)}")
    if indices.duplicated(["year", "month"]).any():
        raise ValueError("Duplicate index year-month")
    expected_transport = len(indices) * len(GATE_LONGITUDES)
    if len(transport) != expected_transport:
        raise ValueError(
            f"Expected {expected_transport} transport rows, "
            f"found {len(transport)}"
        )
    if transport.duplicated(["year", "month", "longitude_e"]).any():
        raise ValueError("Duplicate transport coordinates")
    if len(events) != 13:
        raise ValueError(f"Expected 13 warm events, found {len(events)}")
    if not np.isfinite(indices["q20_dateline_pw"]).all():
        raise ValueError("Non-finite dateline heat transport")
    closure = (
        indices["ml_hadv_interval_east_kmonth"]
        + indices["ml_vadv_interval_east_kmonth"]
        + indices["ml_surface_interval_east_kmonth"]
        + indices["ml_residual_east_kmonth"]
        - indices["ml_temp_tendency_east_kmonth"]
    )
    if float(np.nanmax(np.abs(closure))) > 1.0e-10:
        raise ValueError("Diagnostic budget arithmetic does not close")


def main() -> int:
    for path in (TEMP_NC, PROCESS_NC, MONTHLY_BASE_CSV, EVENT_BASE_CSV):
        if not path.exists():
            raise FileNotFoundError(path)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)

    with xr.open_dataset(TEMP_NC, decode_times=True) as temperature_dataset:
        with xr.open_dataset(PROCESS_NC, decode_times=True) as process_dataset:
            indices, transport = derive_monthly_fields(
                temperature_dataset,
                process_dataset,
            )
    indices = add_interval_budget(indices)
    anomaly_columns = [
        column
        for column in indices.columns
        if column not in {"time", "year", "month"}
    ]
    indices = add_anomalies(indices, anomaly_columns)
    transport = add_transport_anomalies(transport)
    events, correlations, monthly_correlations = build_event_tables(indices)
    validate_outputs(indices, transport, events)

    indices.to_csv(INDEX_CSV, index=False)
    transport.to_csv(TRANSPORT_CSV, index=False)
    events.to_csv(EVENT_CSV, index=False)
    correlations.to_csv(CORR_CSV, index=False)
    monthly_correlations.to_csv(MONTHLY_CORR_CSV, index=False)

    plot_transition_evidence(
        indices,
        events,
        correlations,
        monthly_correlations,
    )
    plot_transport_hovmoller(transport)
    write_summary(events, correlations, monthly_correlations)

    diagnostics = {
        "dataset": "SODA3.15.2",
        "time_range": [1980, 2024],
        "months": list(MONTHS),
        "domain": "5S-5N, 120E-80W, 0-300 m",
        "gate_longitudes_e": GATE_LONGITUDES.tolist(),
        "n_months": len(indices),
        "n_events": len(events),
        "permutation_samples": PERMUTATION_SAMPLES,
        "baseline": list(BASELINE),
        "budget_warning": (
            "Monthly-mean diagnostic budget; residual includes entrainment, "
            "mixing, transients, numerical terms, and assimilation increments."
        ),
        "outputs": {
            "indices_csv": str(INDEX_CSV),
            "transport_csv": str(TRANSPORT_CSV),
            "event_csv": str(EVENT_CSV),
            "correlations_csv": str(CORR_CSV),
            "monthly_correlations_csv": str(MONTHLY_CORR_CSV),
            "figure_pdf": str(FIGURE_PDF),
            "hovmoller_pdf": str(HOV_PDF),
            "summary_md": str(SUMMARY_MD),
        },
    }
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {INDEX_CSV}", flush=True)
    print(f"Wrote {TRANSPORT_CSV}", flush=True)
    print(f"Wrote {FIGURE_PDF}", flush=True)
    print(f"Wrote {HOV_PDF}", flush=True)
    print(f"Wrote {SUMMARY_MD}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
