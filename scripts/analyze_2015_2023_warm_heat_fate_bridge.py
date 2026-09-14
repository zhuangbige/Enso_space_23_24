#!/usr/bin/env python3
"""Bridge the 1997/2015/2023/2026 coupling work to warm-heat fate diagnostics.

This first-pass experiment uses the common January-June SODA3.15.2 subset
available through 2024 to compare the rapidly coupled 1997/98 event, the
strongly coupled 2015/16 event, and the atmosphere-limited 2023/24 event.  It
diagnoses, in physical units:

* eastward Q20 through 140W during January-June of the development year;
* H20 storage in the eastern equatorial Pacific (5S-5N, 140W-80W);
* total and first-order Ekman Q20 export across 5N;
* surface warm-layer heat loss over the eastern box; and
* the same outlet terms during January-May of the following year.

The extended SODA3 subset does not contain salinity.  Therefore total minus
Ekman transport is reported as a non-Ekman remainder, not mislabeled as a
geostrophic term.  The primary anomaly baseline is 1980-2014 to match the
three-event coupling report; 1982-2022 is retained as a sensitivity test.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
matplotlib.use("Agg")

TEMP_NC = (
    ROOT
    / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
PROCESS_NC = (
    ROOT
    / "data/raw/soda3/soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
)
EXISTING_Q20_CSV = (
    ROOT / "data/derived/research_2026/soda3_warm_transport_longitude_1980_2024.csv"
)
EXISTING_THREE_BOX_CSV = (
    ROOT
    / "data/derived/research_2026/soda3_three_box_warm_heat_budget_terms_1980_2022.csv"
)
DERIVED = ROOT / "data/derived/research_2026"
PDF_DIR = ROOT / "output/pdf"

OUT = ROOT / "outputs/research_2026/enso_1997_2015_2023_warm_heat_fate_bridge"
MONTHLY_CSV = DERIVED / "enso_1997_2015_2023_warm_heat_fate_monthly.csv"
PHASE_CSV = DERIVED / "enso_1997_2015_2023_warm_heat_fate_phase_summary.csv"
DIAGNOSTICS_JSON = DERIVED / "enso_1997_2015_2023_warm_heat_fate_diagnostics.json"
FIGURE_PNG = OUT / "enso_1997_2015_2023_warm_heat_fate_bridge.png"
FIGURE_PDF = PDF_DIR / "enso_1997_2015_2023_warm_heat_fate_bridge.pdf"
REPORT_MD = OUT / "ENSO_1997_2015_2023_WARM_HEAT_FATE_BRIDGE_CN.md"

RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
OMEGA = 7.2921159e-5
DEPTH_MAX = 300.0
EVENTS = (1997, 2015, 2023)
EVENT_PAIRS = ((1997, 2015), (1997, 2023), (2015, 2023))
BASELINES = ((1980, 2014), (1982, 2022))
PRIMARY_BASELINE = (1980, 2014)
EAST_LON = (220.0, 280.0)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.4,
            "axes.labelsize": 9.2,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def depth_bounds(depth: np.ndarray, maximum: float = DEPTH_MAX) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    bounds = np.empty(depth.size + 1, dtype=float)
    bounds[0] = 0.0
    bounds[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    bounds[-1] = min(maximum, depth[-1] + 0.5 * (depth[-1] - depth[-2]))
    if np.any(np.diff(bounds) <= 0.0):
        raise ValueError("Non-increasing depth bounds")
    return bounds


def cell_areas(latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    latitude = np.asarray(latitude, dtype=float)
    longitude = np.asarray(longitude, dtype=float)
    dlat = float(np.median(np.diff(latitude)))
    dlon = float(np.median(np.diff(longitude)))
    south = np.deg2rad(latitude - dlat / 2.0)
    north = np.deg2rad(latitude + dlat / 2.0)
    strip = EARTH_RADIUS**2 * (np.sin(north) - np.sin(south))
    return strip[:, None] * np.deg2rad(dlon) * np.ones((1, longitude.size))


def zonal_width(latitude: np.ndarray) -> np.ndarray:
    dlat = float(np.median(np.diff(latitude)))
    return np.full(len(latitude), EARTH_RADIUS * np.deg2rad(dlat))


def meridional_width(longitude: np.ndarray, latitude: float) -> np.ndarray:
    dlon = float(np.median(np.diff(longitude)))
    return np.full(
        len(longitude),
        EARTH_RADIUS * np.cos(np.deg2rad(latitude)) * np.deg2rad(dlon),
    )


def q20_transport_pw(
    temperature: np.ndarray,
    velocity: np.ndarray,
    depth: np.ndarray,
    horizontal_width: np.ndarray,
) -> float:
    """Q20 = rho Cp integral[v(T-20)+] dA, positive with velocity sign."""
    if temperature.shape != velocity.shape:
        raise ValueError(
            f"Temperature/velocity section mismatch: {temperature.shape} vs {velocity.shape}"
        )
    dz = np.diff(depth_bounds(depth))[:, None]
    width = np.asarray(horizontal_width, dtype=float)[None, :]
    valid = np.isfinite(temperature) & np.isfinite(velocity)
    warm = np.where(valid, np.maximum(temperature - 20.0, 0.0), np.nan)
    return float(RHO0 * CP0 * np.nansum(velocity * warm * dz * width) / 1.0e15)


def d20_field(temperature: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Linearly interpolated 20 C isotherm depth for (depth, lat, lon)."""
    values = np.asarray(temperature, dtype=float)
    crossing = (values[:-1] >= 20.0) & (values[1:] < 20.0)
    has_crossing = crossing.any(axis=0)
    index = np.argmax(crossing, axis=0)
    t0 = np.take_along_axis(values, index[None, ...], axis=0)[0]
    t1 = np.take_along_axis(values, (index + 1)[None, ...], axis=0)[0]
    z0 = np.asarray(depth)[index]
    z1 = np.asarray(depth)[index + 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        output = z0 + (20.0 - t0) * (z1 - z0) / (t1 - t0)
    output = np.where(has_crossing, output, np.nan)
    surface_valid = np.isfinite(values[0])
    output = np.where(
        (~has_crossing) & surface_valid & (values[-1] >= 20.0), DEPTH_MAX, output
    )
    output = np.where(
        (~has_crossing) & surface_valid & (values[0] < 20.0), 0.0, output
    )
    return np.clip(output, 0.0, DEPTH_MAX)


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    valid = np.isfinite(values)
    denominator = float(np.sum(np.where(valid, weights, 0.0)))
    if denominator <= 0.0:
        return np.nan
    return float(np.nansum(values * weights) / denominator)


def same_month_detrended(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int],
) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in range(1, 7):
        fit = (
            (times.month == month)
            & (times.year >= baseline[0])
            & (times.year <= baseline[1])
            & np.isfinite(values)
        )
        apply = (times.month == month) & np.isfinite(values)
        if fit.sum() < 10:
            raise ValueError(f"Insufficient baseline values for calendar month {month}")
        x = times.year[fit].astype(float)
        design = np.column_stack([np.ones(fit.sum()), x])
        intercept, slope = np.linalg.lstsq(design, values[fit], rcond=None)[0]
        output[apply] = values[apply] - (
            intercept + slope * times.year[apply].astype(float)
        )
    return output


def ekman_q20_pw(
    boundary_temperature: np.ndarray,
    tau_x: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    latitude: float = 5.0,
) -> float:
    """First-order northward Ekman Q20 using 0-50 m mean warm excess."""
    bounds = depth_bounds(depth)
    overlap = np.maximum(
        0.0, np.minimum(bounds[1:], 50.0) - np.maximum(bounds[:-1], 0.0)
    )
    warm = np.maximum(boundary_temperature - 20.0, 0.0)
    valid = np.isfinite(warm)
    numerator = np.nansum(warm * overlap[:, None], axis=0)
    denominator = np.sum(valid * overlap[:, None], axis=0)
    warm_mean = np.divide(
        numerator,
        denominator,
        out=np.full(numerator.shape, np.nan),
        where=denominator > 0.0,
    )
    f = 2.0 * OMEGA * np.sin(np.deg2rad(latitude))
    northward_m2s = -np.asarray(tau_x, dtype=float) / (RHO0 * f)
    width = meridional_width(longitude, latitude)
    return float(
        RHO0 * CP0 * np.nansum(northward_m2s * warm_mean * width) / 1.0e15
    )


def validate_inputs(temp: xr.Dataset, process: xr.Dataset) -> None:
    temp_times = pd.DatetimeIndex(temp.time.values)
    process_times = pd.DatetimeIndex(process.time.values)
    expected = pd.DatetimeIndex(
        [pd.Timestamp(year, month, 15) for year in range(1980, 2025) for month in range(1, 7)]
    )
    if not temp_times.equals(process_times) or not temp_times.equals(expected):
        raise ValueError("Temperature/process time axes are not the expected Jan-Jun 1980-2024 axis")
    if not np.allclose(temp.depth, process.depth):
        raise ValueError("Temperature/process depth coordinates differ")
    if not np.allclose(0.5 * (process.u_lat.values[:-1] + process.u_lat.values[1:]), temp.lat):
        raise ValueError("Velocity and tracer latitude staggering is inconsistent")
    if not np.allclose(0.5 * (process.u_lon.values[:-1] + process.u_lon.values[1:]), temp.lon):
        raise ValueError("Velocity and tracer longitude staggering is inconsistent")
    if float(temp.temp.min()) < -3.0 or float(temp.temp.max()) > 40.0:
        raise ValueError("Temperature outside broad physical limits")
    if float(abs(process.v).max()) > 5.0 or float(abs(process.taux).max()) > 5.0:
        raise ValueError("Velocity or wind stress outside broad physical limits")


def derive_raw_monthly(temp: xr.Dataset, process: xr.Dataset) -> pd.DataFrame:
    times = pd.DatetimeIndex(temp.time.values)
    depth = temp.depth.values.astype(float)
    lat = temp.lat.values.astype(float)
    lon = temp.lon.values.astype(float)
    u_lat = process.u_lat.values.astype(float)
    u_lon = process.u_lon.values.astype(float)

    east_lon_mask = (lon >= EAST_LON[0]) & (lon <= EAST_LON[1])
    east_lon = lon[east_lon_mask]
    east_area = cell_areas(lat, east_lon)
    dz = np.diff(depth_bounds(depth))[:, None, None]

    gate_u_index = int(np.argmin(np.abs(u_lon - 220.0)))
    if not np.isclose(u_lon[gate_u_index], 220.0):
        raise ValueError("No 140W velocity face")
    gate_left = int(np.flatnonzero(lon < 220.0)[-1])
    gate_right = int(np.flatnonzero(lon > 220.0)[0])

    north_v_index = int(np.argmin(np.abs(u_lat - 5.0)))
    if not np.isclose(u_lat[north_v_index], 5.0):
        raise ValueError("No 5N velocity face")
    north_lon_faces = np.flatnonzero((u_lon >= EAST_LON[0]) & (u_lon <= EAST_LON[1]))
    first_face, last_face = int(north_lon_faces[0]), int(north_lon_faces[-1])
    north_lon = lon[east_lon_mask]
    if last_face - first_face != len(north_lon):
        raise ValueError("Unexpected longitude staggering along 5N")

    primary_temp_lat = int(np.argmax(lat))  # 4.75N, nearest tracer row inside box.
    sensitivity_temp_lat = primary_temp_lat - 1  # 4.25N.
    if not np.isclose(lat[primary_temp_lat], 4.75) or not np.isclose(
        lat[sensitivity_temp_lat], 4.25
    ):
        raise ValueError("Expected 4.25N/4.75N tracer rows are unavailable")

    rows: list[dict[str, float | int | pd.Timestamp]] = []
    for index, timestamp in enumerate(times):
        temperature = temp.temp.isel(time=index).values.astype(float)
        raw_u = process.u.isel(time=index).values.astype(float)
        raw_v = process.v.isel(time=index).values.astype(float)
        raw_tau = process.taux.isel(time=index).values.astype(float)
        net_heating = process.net_heating.isel(time=index).values.astype(float)

        east_temp = temperature[:, :, east_lon_mask]
        warm = np.maximum(east_temp - 20.0, 0.0)
        east_h20 = RHO0 * CP0 * np.nansum(warm * dz * east_area[None, :, :]) / 1.0e21
        east_sst = weighted_mean(east_temp[0], east_area)
        east_d20 = weighted_mean(d20_field(east_temp, depth), east_area)
        warm_surface = np.isfinite(east_temp[0]) & (east_temp[0] > 20.0)
        east_surface_pw = float(
            np.nansum(np.where(warm_surface, net_heating[:, east_lon_mask] * east_area, np.nan))
            / 1.0e15
        )

        gate_temp = 0.5 * (
            temperature[:, :, gate_left] + temperature[:, :, gate_right]
        )
        gate_u = 0.5 * (
            raw_u[:, :-1, gate_u_index] + raw_u[:, 1:, gate_u_index]
        )
        q140 = q20_transport_pw(gate_temp, gate_u, depth, zonal_width(lat))

        north_v = 0.5 * (
            raw_v[:, north_v_index, first_face:last_face]
            + raw_v[:, north_v_index, first_face + 1 : last_face + 1]
        )
        north_tau = 0.5 * (
            raw_tau[north_v_index, first_face:last_face]
            + raw_tau[north_v_index, first_face + 1 : last_face + 1]
        )
        boundary_temp = temperature[:, primary_temp_lat, east_lon_mask]
        boundary_temp_sensitivity = temperature[:, sensitivity_temp_lat, east_lon_mask]
        north_total = q20_transport_pw(
            boundary_temp, north_v, depth, meridional_width(north_lon, 5.0)
        )
        north_total_sensitivity = q20_transport_pw(
            boundary_temp_sensitivity,
            north_v,
            depth,
            meridional_width(north_lon, 5.0),
        )
        north_ekman = ekman_q20_pw(
            boundary_temp, north_tau, depth, north_lon, 5.0
        )
        north_ekman_sensitivity = ekman_q20_pw(
            boundary_temp_sensitivity, north_tau, depth, north_lon, 5.0
        )

        rows.append(
            {
                "time": timestamp,
                "year": timestamp.year,
                "month": timestamp.month,
                "east_h20_raw_zj": east_h20,
                "east_sst_raw_c": east_sst,
                "east_d20_raw_m": east_d20,
                "q20_140w_east_raw_pw": q140,
                "q20_5n_north_raw_pw": north_total,
                "q20_5n_ekman_north_raw_pw": north_ekman,
                "q20_5n_nonekman_north_raw_pw": north_total - north_ekman,
                "q20_5n_north_4p25_raw_pw": north_total_sensitivity,
                "q20_5n_ekman_north_4p25_raw_pw": north_ekman_sensitivity,
                "tau5n_westward_raw_nm2": -float(np.nanmean(north_tau)),
                "east_surface_loss_raw_pw": -east_surface_pw,
            }
        )
    return pd.DataFrame(rows)


def add_anomalies(monthly: pd.DataFrame) -> pd.DataFrame:
    output = monthly.copy()
    times = pd.DatetimeIndex(output.time)
    raw_columns = [name for name in output if name.endswith("_raw_zj") or name.endswith("_raw_c") or name.endswith("_raw_m") or name.endswith("_raw_pw") or name.endswith("_raw_nm2")]
    for baseline in BASELINES:
        tag = f"b{baseline[0]}_{baseline[1]}"
        for column in raw_columns:
            short = column.replace("_raw_", "_")
            output[f"{short}_anom_{tag}"] = same_month_detrended(
                output[column].to_numpy(dtype=float), times, baseline
            )
    return output


def integrate_zj(values_pw: np.ndarray, timestamps: pd.DatetimeIndex) -> float:
    seconds = timestamps.days_in_month.to_numpy(dtype=float) * 86400.0
    return float(np.nansum(np.asarray(values_pw, dtype=float) * seconds) / 1.0e6)


def build_phase_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for baseline in BASELINES:
        tag = f"b{baseline[0]}_{baseline[1]}"
        for event_year in EVENTS:
            phases = {
                "development_Jan0_Jun0": monthly.loc[
                    monthly.year.eq(event_year) & monthly.month.between(1, 6)
                ],
                "decay_Jan1_May1": monthly.loc[
                    monthly.year.eq(event_year + 1) & monthly.month.between(1, 5)
                ],
            }
            for phase, selected in phases.items():
                selected = selected.sort_values("time")
                expected = 6 if phase.startswith("development") else 5
                if len(selected) != expected:
                    raise ValueError(f"Incomplete {event_year} {phase}: {len(selected)} months")
                times = pd.DatetimeIndex(selected.time)
                metric = lambda name, unit: f"{name}_{unit}_anom_{tag}"
                rows.append(
                    {
                        "baseline": f"{baseline[0]}-{baseline[1]}",
                        "event_year": event_year,
                        "phase": phase,
                        "east_h20_start_zj": float(selected[metric("east_h20", "zj")].iloc[0]),
                        "east_h20_end_zj": float(selected[metric("east_h20", "zj")].iloc[-1]),
                        "east_h20_change_zj": float(
                            selected[metric("east_h20", "zj")].iloc[-1]
                            - selected[metric("east_h20", "zj")].iloc[0]
                        ),
                        "east_sst_mean_c": float(selected[metric("east_sst", "c")].mean()),
                        "east_d20_mean_m": float(selected[metric("east_d20", "m")].mean()),
                        "q20_140w_east_zj": integrate_zj(
                            selected[metric("q20_140w_east", "pw")], times
                        ),
                        "q20_5n_north_zj": integrate_zj(
                            selected[metric("q20_5n_north", "pw")], times
                        ),
                        "q20_5n_ekman_north_zj": integrate_zj(
                            selected[metric("q20_5n_ekman_north", "pw")], times
                        ),
                        "q20_5n_nonekman_north_zj": integrate_zj(
                            selected[metric("q20_5n_nonekman_north", "pw")], times
                        ),
                        "q20_5n_north_4p25_zj": integrate_zj(
                            selected[metric("q20_5n_north_4p25", "pw")], times
                        ),
                        "q20_5n_ekman_north_4p25_zj": integrate_zj(
                            selected[metric("q20_5n_ekman_north_4p25", "pw")], times
                        ),
                        "tau5n_westward_mean_nm2": float(
                            selected[metric("tau5n_westward", "nm2")].mean()
                        ),
                        "east_surface_loss_zj": integrate_zj(
                            selected[metric("east_surface_loss", "pw")], times
                        ),
                    }
                )
    return pd.DataFrame(rows)


def event_period(
    monthly: pd.DataFrame,
    event_year: int,
    stage: str,
    tag: str,
) -> pd.DataFrame:
    if stage == "development":
        selected = monthly.loc[monthly.year.eq(event_year) & monthly.month.between(1, 6)].copy()
    elif stage == "decay":
        selected = monthly.loc[monthly.year.eq(event_year + 1) & monthly.month.between(1, 5)].copy()
    else:
        raise KeyError(stage)
    selected = selected.sort_values("time")
    selected["plot_month"] = np.arange(1, len(selected) + 1)
    for source, destination in (
        (f"q20_140w_east_pw_anom_{tag}", "cum_q140_zj"),
        (f"q20_5n_north_pw_anom_{tag}", "cum_north_zj"),
        (f"q20_5n_ekman_north_pw_anom_{tag}", "cum_ekman_zj"),
        (f"east_surface_loss_pw_anom_{tag}", "cum_surface_loss_zj"),
    ):
        seconds = pd.DatetimeIndex(selected.time).days_in_month.to_numpy(dtype=float) * 86400.0
        selected[destination] = np.cumsum(selected[source].to_numpy(dtype=float) * seconds / 1.0e6)
    return selected


def plot_bridge(monthly: pd.DataFrame) -> None:
    setup_style()
    tag = f"b{PRIMARY_BASELINE[0]}_{PRIMARY_BASELINE[1]}"
    colors = {1997: "#B33A3A", 2015: "#D17A22", 2023: "#2878B5"}
    labels = {
        1997: "1997/98: rapid, strong coupling",
        2015: "2015/16: early, strong coupling",
        2023: "2023/24: delayed, weak coupling",
    }
    figure, axes = plt.subplots(2, 2, figsize=(10.2, 7.2), constrained_layout=True)

    for event_year in EVENTS:
        development = event_period(monthly, event_year, "development", tag)
        decay = event_period(monthly, event_year, "decay", tag)
        color = colors[event_year]
        axes[0, 0].plot(
            development.plot_month,
            development[f"east_h20_zj_anom_{tag}"],
            marker="o",
            color=color,
            label=labels[event_year],
        )
        axes[0, 1].plot(
            development.plot_month,
            development.cum_q140_zj,
            marker="o",
            color=color,
            label=labels[event_year],
        )
        axes[1, 0].plot(
            decay.plot_month,
            decay.cum_north_zj,
            marker="o",
            color=color,
            label=f"{event_year} total",
        )
        axes[1, 0].plot(
            decay.plot_month,
            decay.cum_ekman_zj,
            marker="s",
            linestyle="--",
            color=color,
            alpha=0.85,
            label=f"{event_year} Ekman",
        )
        axes[1, 1].plot(
            decay.plot_month,
            decay.cum_surface_loss_zj,
            marker="o",
            color=color,
            label=labels[event_year],
        )

    titles = (
        "a  Eastern H20 storage during development",
        "b  Eastward warm-heat input through 140°W",
        "c  Following-year warm-heat export across 5°N",
        "d  Following-year eastern surface heat loss",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title, loc="left", fontweight="bold")
        axis.axhline(0.0, color="#777777", linewidth=0.8)
        axis.grid(axis="y", color="#D8D8D8", linewidth=0.6, alpha=0.8)
        axis.spines[["top", "right"]].set_visible(False)

    axes[0, 0].set_ylabel("H20 anomaly (ZJ)")
    axes[0, 0].set_xticks(range(1, 7), ["Jan", "Feb", "Mar", "Apr", "May", "Jun"])
    axes[0, 1].set_ylabel("Cumulative eastward Qwarm,20 (ZJ)")
    axes[0, 1].set_xticks(range(1, 7), ["Jan", "Feb", "Mar", "Apr", "May", "Jun"])
    axes[1, 0].set_ylabel("Cumulative northward Qwarm,20 (ZJ)")
    axes[1, 0].set_xticks(range(1, 6), ["Jan+1", "Feb+1", "Mar+1", "Apr+1", "May+1"])
    axes[1, 1].set_ylabel("Cumulative ocean heat loss (ZJ)")
    axes[1, 1].set_xticks(range(1, 6), ["Jan+1", "Feb+1", "Mar+1", "Apr+1", "May+1"])
    axes[0, 0].legend(frameon=False, loc="best")
    axes[1, 0].legend(frameon=False, ncol=2, loc="best")
    figure.suptitle(
        "Does air–sea coupling state alter where eastern-Pacific warm heat goes?\n"
        "SODA3.15.2; 5°S–5°N, 140°W–80°W; calendar-month detrended over 1980–2014",
        fontsize=12.0,
        fontweight="bold",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def build_diagnostics(monthly: pd.DataFrame, phases: pd.DataFrame) -> dict[str, object]:
    primary = phases.loc[phases.baseline.eq("1980-2014")]
    sensitivity = phases.loc[phases.baseline.eq("1982-2022")]
    metrics = (
        "q20_140w_east_zj",
        "q20_5n_north_zj",
        "q20_5n_ekman_north_zj",
        "east_surface_loss_zj",
        "east_h20_change_zj",
    )
    sign_stability: dict[str, bool] = {}
    for phase in primary.phase.unique():
        for event_year in EVENTS:
            p = primary.loc[
                primary.phase.eq(phase) & primary.event_year.eq(event_year)
            ].iloc[0]
            s = sensitivity.loc[
                sensitivity.phase.eq(phase) & sensitivity.event_year.eq(event_year)
            ].iloc[0]
            for metric in metrics:
                sign_stability[f"{event_year}_{phase}_{metric}"] = bool(
                    np.sign(p[metric]) == np.sign(s[metric])
                )

    primary_decay = primary.loc[primary.phase.eq("decay_Jan1_May1")].set_index("event_year")
    boundary_sensitivity = {
        str(year): float(
            primary_decay.loc[year, "q20_5n_north_4p25_zj"]
            - primary_decay.loc[year, "q20_5n_north_zj"]
        )
        for year in EVENTS
    }
    core_decay_metrics = (
        "q20_5n_north_zj",
        "q20_5n_ekman_north_zj",
        "east_surface_loss_zj",
        "east_h20_change_zj",
    )
    core_decay_sign_stable = all(
        sign_stability[f"{year}_decay_Jan1_May1_{metric}"]
        for year in EVENTS
        for metric in core_decay_metrics
    )
    contrast_metrics = (
        ("development_Jan0_Jun0", "q20_140w_east_zj"),
        ("development_Jan0_Jun0", "east_h20_change_zj"),
        ("decay_Jan1_May1", "q20_5n_north_zj"),
        ("decay_Jan1_May1", "q20_5n_ekman_north_zj"),
        ("decay_Jan1_May1", "q20_5n_nonekman_north_zj"),
        ("decay_Jan1_May1", "east_surface_loss_zj"),
        ("decay_Jan1_May1", "east_h20_change_zj"),
    )
    contrast_direction_stability: dict[str, bool] = {}
    for phase, metric in contrast_metrics:
        p = primary.loc[primary.phase.eq(phase)].set_index("event_year")
        s = sensitivity.loc[sensitivity.phase.eq(phase)].set_index("event_year")
        for first, second in EVENT_PAIRS:
            primary_contrast = float(p.loc[first, metric] - p.loc[second, metric])
            sensitivity_contrast = float(s.loc[first, metric] - s.loc[second, metric])
            contrast_direction_stability[
                f"{first}_minus_{second}_{phase}_{metric}"
            ] = bool(np.sign(primary_contrast) == np.sign(sensitivity_contrast))
    primary_decay_contrasts = {
        metric: float(
            primary_decay.loc[2015, metric] - primary_decay.loc[2023, metric]
        )
        for metric in (
            "q20_5n_north_zj",
            "q20_5n_ekman_north_zj",
            "q20_5n_nonekman_north_zj",
            "east_surface_loss_zj",
            "east_h20_change_zj",
        )
    }
    total_contrast = primary_decay_contrasts["q20_5n_north_zj"]
    ekman_fraction = (
        primary_decay_contrasts["q20_5n_ekman_north_zj"] / total_contrast
        if total_contrast != 0.0
        else np.nan
    )
    pairwise_metrics = (
        "q20_5n_north_zj",
        "q20_5n_ekman_north_zj",
        "q20_5n_nonekman_north_zj",
        "east_surface_loss_zj",
        "east_h20_change_zj",
    )
    pairwise_decay: dict[str, dict[str, float]] = {}
    pairwise_ekman_fraction: dict[str, float] = {}
    for first, second in EVENT_PAIRS:
        key = f"{first}_minus_{second}"
        pairwise_decay[key] = {
            metric: float(
                primary_decay.loc[first, metric] - primary_decay.loc[second, metric]
            )
            for metric in pairwise_metrics
        }
        pair_total = pairwise_decay[key]["q20_5n_north_zj"]
        pairwise_ekman_fraction[key] = float(
            pairwise_decay[key]["q20_5n_ekman_north_zj"] / pair_total
            if pair_total != 0.0
            else np.nan
        )
    existing_q20 = pd.read_csv(EXISTING_Q20_CSV, parse_dates=["time"])
    existing_q20 = existing_q20.loc[
        existing_q20.longitude_e.eq(220.0), ["time", "q20_pw"]
    ]
    q140_compare = monthly[["time", "q20_140w_east_raw_pw"]].merge(
        existing_q20, on="time", validate="one_to_one"
    )
    q140_difference = (
        q140_compare.q20_140w_east_raw_pw - q140_compare.q20_pw
    )
    existing_box = pd.read_csv(EXISTING_THREE_BOX_CSV, parse_dates=["time"])
    north_compare = monthly[["time", "q20_5n_north_raw_pw"]].merge(
        existing_box[["time", "east_north_q20_in_pw"]],
        on="time",
        validate="one_to_one",
    )
    north_reference = -north_compare.east_north_q20_in_pw
    north_difference = north_compare.q20_5n_north_raw_pw - north_reference
    independent_reproduction = {
        "q140_n_months": int(len(q140_compare)),
        "q140_correlation": float(
            np.corrcoef(q140_compare.q20_140w_east_raw_pw, q140_compare.q20_pw)[0, 1]
        ),
        "q140_max_abs_difference_pw": float(np.max(np.abs(q140_difference))),
        "q5n_n_months": int(len(north_compare)),
        "q5n_correlation": float(
            np.corrcoef(north_compare.q20_5n_north_raw_pw, north_reference)[0, 1]
        ),
        "q5n_max_abs_difference_pw": float(np.max(np.abs(north_difference))),
        "q5n_mean_abs_difference_pw": float(np.mean(np.abs(north_difference))),
    }
    return {
        "source_months": int(len(monthly)),
        "source_start": str(pd.Timestamp(monthly.time.min()).date()),
        "source_end": str(pd.Timestamp(monthly.time.max()).date()),
        "primary_baseline": "1980-2014",
        "sensitivity_baseline": "1982-2022",
        "event_years": list(EVENTS),
        "primary_5n_temperature_latitude": 4.75,
        "sensitivity_5n_temperature_latitude": 4.25,
        "decay_total_export_boundary_sensitivity_zj": boundary_sensitivity,
        "baseline_sign_stability": sign_stability,
        "all_key_signs_stable": bool(all(sign_stability.values())),
        "core_decay_signs_stable": bool(core_decay_sign_stable),
        "contrast_direction_stability": contrast_direction_stability,
        "all_core_contrast_directions_stable": bool(
            all(contrast_direction_stability.values())
        ),
        "primary_decay_2015_minus_2023_zj": primary_decay_contrasts,
        "ekman_fraction_of_total_export_contrast": float(ekman_fraction),
        "primary_pairwise_decay_contrasts_zj": pairwise_decay,
        "pairwise_ekman_fraction_of_total_export_contrast": pairwise_ekman_fraction,
        "primary_decay_north_export_order_1997_gt_2015_gt_2023": bool(
            primary_decay.loc[1997, "q20_5n_north_zj"]
            > primary_decay.loc[2015, "q20_5n_north_zj"]
            > primary_decay.loc[2023, "q20_5n_north_zj"]
        ),
        "independent_reproduction_checks": independent_reproduction,
        "limitations": [
            "January-June source months only; the mature December is unavailable in this extension subset.",
            "The eastern storage box is 5S-5N rather than the 10S-5N composite box.",
            "Salinity is unavailable, so total-minus-Ekman is a non-Ekman remainder, not a geostrophic estimate.",
            "The 2026 decay season has not occurred and is not inferred from these data.",
        ],
    }


def fmt(row: pd.Series, name: str) -> str:
    return f"{float(row[name]):+.2f}"


def write_report(phases: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    primary = phases.loc[phases.baseline.eq("1980-2014")]
    development = primary.loc[primary.phase.eq("development_Jan0_Jun0")].set_index("event_year")
    decay = primary.loc[primary.phase.eq("decay_Jan1_May1")].set_index("event_year")
    d97, d15, d23 = development.loc[1997], development.loc[2015], development.loc[2023]
    x97, x15, x23 = decay.loc[1997], decay.loc[2015], decay.loc[2023]

    diff = lambda first, second, name: float(decay.loc[first, name] - decay.loc[second, name])
    text = f"""# 1997/98—2015/16—2023/24暖量去向对比：三事件桥接试验

## 问题

此前报告判定：2015是较早且完整的海气接通，2023是海洋先行但大气响应受限，2026则在2026年5—6月晚接通。现在加入快速、强耦合的1997/98，检验2015—2023的出口差异是否只是两个个例，还是能形成“1997强排放—2015部分排放—2023出口未打开”的过程阶梯。2026尚未经历成熟—衰减期，只保留为后续独立检验。

## 统一口径

- SODA3.15.2月资料，每年1—6月，1980—2024；
- 东部储热区：5°S—5°N、140°W—80°W、0—300 m；
- 发展期：事件年1—6月；衰减诊断期：次年1—5月；
- 主距平：1980—2014逐日历月线性去趋势；1982—2022作为敏感性；
- 暖量采用相对20°C的H20/Q20；正的5°N Q20表示暖量向北离开赤道东太平洋；
- Ekman项由SODA3风应力和0—50 m暖含量一阶估算。延伸资料没有盐度，因此总量减Ekman只能称为“非Ekman剩余”，不能直接称为地转。

## 主要结果（ZJ）

| 阶段 | 指标 | 1997/98 | 2015/16 | 2023/24 |
|---|---|---:|---:|---:|
| 发展年Jan—Jun | 140°W东向Q20累计 | {fmt(d97, 'q20_140w_east_zj')} | {fmt(d15, 'q20_140w_east_zj')} | {fmt(d23, 'q20_140w_east_zj')} |
| 发展年Jan—Jun | 东部H20 Jan→Jun变化 | {fmt(d97, 'east_h20_change_zj')} | {fmt(d15, 'east_h20_change_zj')} | {fmt(d23, 'east_h20_change_zj')} |
| 次年Jan—May | 5°N总北向Q20累计 | {fmt(x97, 'q20_5n_north_zj')} | {fmt(x15, 'q20_5n_north_zj')} | {fmt(x23, 'q20_5n_north_zj')} |
| 次年Jan—May | 其中Ekman累计 | {fmt(x97, 'q20_5n_ekman_north_zj')} | {fmt(x15, 'q20_5n_ekman_north_zj')} | {fmt(x23, 'q20_5n_ekman_north_zj')} |
| 次年Jan—May | 非Ekman剩余累计 | {fmt(x97, 'q20_5n_nonekman_north_zj')} | {fmt(x15, 'q20_5n_nonekman_north_zj')} | {fmt(x23, 'q20_5n_nonekman_north_zj')} |
| 次年Jan—May | 东部海表异常热损失 | {fmt(x97, 'east_surface_loss_zj')} | {fmt(x15, 'east_surface_loss_zj')} | {fmt(x23, 'east_surface_loss_zj')} |
| 次年Jan—May | 东部H20 Jan→May变化 | {fmt(x97, 'east_h20_change_zj')} | {fmt(x15, 'east_h20_change_zj')} | {fmt(x23, 'east_h20_change_zj')} |

## 第一轮判断

### 1. 1997是完整的“强输入—强储热—强排放”事件

1997发展期跨140°W的东向Q20达到{fmt(d97, 'q20_140w_east_zj')} ZJ，东部H20增加{fmt(d97, 'east_h20_change_zj')} ZJ，均远大于2015和2023。次年1—5月，它又通过5°N净向北排出{fmt(x97, 'q20_5n_north_zj')} ZJ，并产生{fmt(x97, 'east_surface_loss_zj')} ZJ的异常海表热损失。Ekman为{fmt(x97, 'q20_5n_ekman_north_zj')} ZJ，非Ekman剩余也为正（{fmt(x97, 'q20_5n_nonekman_north_zj')} ZJ），说明两个动力分量同向帮助排放。

### 2. 2015是“Ekman打开、但非Ekman仍部分抵消”的中间态

2015的发展期输入和储热仅为1997的约三分之一，但与2023非常接近。其次年Ekman北向输出达到{fmt(x15, 'q20_5n_ekman_north_zj')} ZJ，足以克服{abs(float(x15.q20_5n_nonekman_north_zj)):.2f} ZJ的南向非Ekman抵消，最终保留{fmt(x15, 'q20_5n_north_zj')} ZJ的净北向输出。因此2015确实支持“大气接通帮助打开出口”，但其完整排放程度弱于1997。

### 3. 2023是“暖量到达、但总出口没有打开”

2023与2015的发展期跨140°W输入和H20增长近似，甚至略大；因此它不是“暖量未到东部”。其Ekman项仍提供{fmt(x23, 'q20_5n_ekman_north_zj')} ZJ的北向输出，但被{abs(float(x23.q20_5n_nonekman_north_zj)):.2f} ZJ的南向非Ekman项完全压过，最终总量为{fmt(x23, 'q20_5n_north_zj')} ZJ。海表异常热损失也只有{fmt(x23, 'east_surface_loss_zj')} ZJ。

三事件的净北向输出形成{fmt(x97, 'q20_5n_north_zj')} → {fmt(x15, 'q20_5n_north_zj')} → {fmt(x23, 'q20_5n_north_zj')} ZJ的阶梯；对应的西向风应力和海表散热也按1997—2015—2023依次减弱。这个结果把原报告中的“耦合完整性”转化成了实际暖量后果。

但总H20下降并不严格按同样顺序排列，2015的Jan—May下降反而略大于1997。这说明“事件衰减”不能只看H20减少多少，而必须问减少的暖量分配到哪里：北向出口、海表散热、南侧/纬向过程和未解析交换可能相互补偿。

## 稳健性

主基准与1982—2022敏感性中，三事件衰减期核心量的符号稳定：**{'是' if diagnostics['core_decay_signs_stable'] else '否'}**；全部三组事件对比方向稳定：**{'是' if diagnostics['all_core_contrast_directions_stable'] else '否'}**。5°N边界温度从4.75°N改用4.25°N后，1997/2015/2023总输出累计变化分别为{diagnostics['decay_total_export_boundary_sensitivity_zj']['1997']:+.2f}/{diagnostics['decay_total_export_boundary_sensitivity_zj']['2015']:+.2f}/{diagnostics['decay_total_export_boundary_sensitivity_zj']['2023']:+.2f} ZJ。

独立复算核验：140°W Q20与既有序列的相关为{diagnostics['independent_reproduction_checks']['q140_correlation']:.8f}，最大绝对差{diagnostics['independent_reproduction_checks']['q140_max_abs_difference_pw']:.2e} PW；5°N Q20与既有三箱收支边界项的相关为{diagnostics['independent_reproduction_checks']['q5n_correlation']:.6f}，平均绝对差{diagnostics['independent_reproduction_checks']['q5n_mean_abs_difference_pw']:.4f} PW。

## 与2026的承接

2026年5—6月出现了比2023更完整的对流、SOI和西风接通，但它的暖量“出口结果”尚未发生。后续应只做前瞻检验：若接通持续，则观察2026年后续5°N西向风应力和Ekman北向输出是否在一至两个月后增强；若接通回落，则不能预设其会走向2015式排放。

## 证据边界

- 只有三个目标事件，结果是过程对照，不是样本统计；
- 延伸SODA3只有1—6月，因此衰减阶段使用次年1—5月，缺少成熟期12月；
- 东部箱体为5°S—5°N，以匹配现有延伸资料，不与10°S—5°N的CT/CP绝对量直接混用；
- 非Ekman剩余包含地转、瞬变、非线性和温度取样误差；
- 2026现在只能检验接通阶段，不能声称暖量最终去向已经确定。

## 输出

- 图：`{FIGURE_PNG}`
- 月表：`{MONTHLY_CSV}`
- 阶段汇总：`{PHASE_CSV}`
- 数值核验：`{DIAGNOSTICS_JSON}`
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with xr.open_dataset(TEMP_NC, engine="netcdf4") as temp, xr.open_dataset(
        PROCESS_NC, engine="netcdf4"
    ) as process:
        validate_inputs(temp, process)
        monthly = add_anomalies(derive_raw_monthly(temp, process))
    phases = build_phase_summary(monthly)
    diagnostics = build_diagnostics(monthly, phases)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    phases.to_csv(PHASE_CSV, index=False, float_format="%.9g")
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot_bridge(monthly)
    write_report(phases, diagnostics)
    print(phases.loc[phases.baseline.eq("1980-2014")].to_string(index=False))
    print(f"Wrote {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
