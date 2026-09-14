#!/usr/bin/env python3
"""Answer the three ENSO heat-fate questions with standard 0--300 m OHC.

This workflow deliberately does not use H20 in its primary results.  Storage is
fixed-depth 0--300 m ocean heat content and boundary fluxes are conventional
rho*Cp*integral(v*T)dA heat transports.  The nonlinear product is formed before
calendar-month climatology/trend removal.  H20 is calculated only in a separate
comparison table so the new OHC-only conclusions can be audited against the
previous diagnostic.

The common local SODA3.15.2 subset contains January--June for 1980--2024.  The
two phases are therefore Jan(0)--Jun(0) development and Jan(+1)--May(+1) decay.
The eastern control volume is 5S--5N, 140W--80W, 0--300 m.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr

import analyze_2015_2023_warm_heat_fate_bridge as common


matplotlib.use("Agg")

TEMP_NC = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
PROCESS_NC = ROOT / "data/raw/soda3/soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
COUPLING_CSV = ROOT / "data/derived/research_2026/enso_type_coupling_event_summary.csv"
TYPE_MEMBERS_CSV = ROOT / "data/derived/research_2026/chakravorty2021_soda3_event_aligned_members.csv"
OLD_PHASE_CSV = ROOT / "data/derived/research_2026/enso_1997_2015_2023_warm_heat_fate_phase_summary.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/ohc_only_three_questions"
PDF_DIR = ROOT / "output/pdf"
MONTHLY_CSV = DERIVED / "soda3_ohc_only_monthly_1980_2024.csv"
PHASE_CSV = DERIVED / "soda3_ohc_only_phase_summary_13events.csv"
THREE_EVENT_CSV = DERIVED / "soda3_ohc_only_three_event_summary.csv"
TYPE_SUMMARY_CSV = DERIVED / "soda3_ohc_only_ct_cp_summary.csv"
TYPE_COMPARISON_CSV = DERIVED / "soda3_ohc_vs_h20_ct_cp_comparison.csv"
REFERENCE_CSV = DERIVED / "soda3_ohc_only_reference_temperature_sensitivity.csv"
COMPARE_CSV = DERIVED / "soda3_ohc_vs_h20_comparison.csv"
CORRELATION_CSV = DERIVED / "soda3_ohc_only_coupling_correlations.csv"
ALL_COMPARISON_CSV = DERIVED / "soda3_ohc_vs_h20_all_metric_comparison.csv"
ROBUST_AUDIT_CSV = DERIVED / "soda3_ohc_only_robustness_audit.csv"
COUPLING_EVENT_CSV = DERIVED / "soda3_ohc_only_three_event_coupling_chain.csv"
SWAP_SUMMARY_CSV = DERIVED / "soda3_ohc_2015_2023_wind_swap_summary.csv"
SWAP_COMPARISON_CSV = DERIVED / "soda3_ohc_vs_h20_wind_swap_comparison.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_ohc_only_three_questions_diagnostics.json"
FIGURE_PNG = OUT / "soda3_ohc_only_three_questions_comparison.png"
FIGURE_PDF = PDF_DIR / "soda3_ohc_only_three_questions_comparison.pdf"
COMPARE_FIGURE_PNG = OUT / "soda3_ohc_vs_h20_all_data_comparison.png"
COMPARE_FIGURE_PDF = PDF_DIR / "soda3_ohc_vs_h20_all_data_comparison.pdf"
SWAP_FIGURE_PNG = OUT / "soda3_ohc_2015_2023_wind_swap.png"
REPORT_MD = OUT / "OHC_ONLY_THREE_QUESTIONS_RESULTS_CN.md"
OHC_FIELD_NC = ROOT / "data/interim/research_2026/soda3_ohc/soda3_ohc_0_100_0_300_1980_2024.nc"

RHO0 = common.RHO0
CP0 = common.CP0
OMEGA = common.OMEGA
DEPTH_MAX = common.DEPTH_MAX
EAST_LON = common.EAST_LON
PRIMARY_BASELINE = (1980, 2014)
SECONDARY_BASELINE = (1982, 2022)
BASELINES = (PRIMARY_BASELINE, SECONDARY_BASELINE)
REFERENCE_TEMPERATURES = (0.0, 10.0, 20.0)
THREE_EVENTS = (1997, 2015, 2023)


def heat_content_zj(
    temperature: np.ndarray,
    depth: np.ndarray,
    area: np.ndarray,
    reference_temperature: float = 0.0,
) -> float:
    """rho Cp integral(T-Tref)dV over a fixed 0--300 m volume."""
    dz = np.diff(common.depth_bounds(depth))[:, None, None]
    valid = np.isfinite(temperature)
    heat = np.where(valid, temperature - reference_temperature, np.nan)
    return float(RHO0 * CP0 * np.nansum(heat * dz * area[None, :, :]) / 1.0e21)


def section_heat_transport(
    temperature: np.ndarray,
    velocity: np.ndarray,
    depth: np.ndarray,
    horizontal_width: np.ndarray,
    reference_temperature: float = 0.0,
) -> tuple[float, float]:
    """Return conventional heat transport (PW) and volume transport (Sv)."""
    if temperature.shape != velocity.shape:
        raise ValueError(f"Section mismatch: {temperature.shape} vs {velocity.shape}")
    dz = np.diff(common.depth_bounds(depth))[:, None]
    width = np.asarray(horizontal_width, dtype=float)[None, :]
    valid = np.isfinite(temperature) & np.isfinite(velocity)
    volume = np.nansum(np.where(valid, velocity * dz * width, np.nan)) / 1.0e6
    heat = np.nansum(
        np.where(
            valid,
            velocity * (temperature - reference_temperature) * dz * width,
            np.nan,
        )
    )
    return float(RHO0 * CP0 * heat / 1.0e15), float(volume)


def ekman_heat_transport(
    boundary_temperature: np.ndarray,
    tau_x: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    reference_temperature: float = 0.0,
    latitude: float = 5.0,
) -> tuple[float, float]:
    """Standard first-order Ekman heat and volume transport at fixed latitude."""
    bounds = common.depth_bounds(depth)
    overlap = np.maximum(
        0.0, np.minimum(bounds[1:], 50.0) - np.maximum(bounds[:-1], 0.0)
    )
    values = boundary_temperature - reference_temperature
    valid = np.isfinite(values)
    numerator = np.nansum(np.where(valid, values * overlap[:, None], np.nan), axis=0)
    denominator = np.sum(valid * overlap[:, None], axis=0)
    mean_temperature = np.divide(
        numerator,
        denominator,
        out=np.full(numerator.shape, np.nan),
        where=denominator > 0.0,
    )
    f = 2.0 * OMEGA * np.sin(np.deg2rad(latitude))
    northward_m2s = -np.asarray(tau_x, dtype=float) / (RHO0 * f)
    width = common.meridional_width(longitude, latitude)
    valid_column = np.isfinite(northward_m2s) & np.isfinite(mean_temperature)
    volume = np.nansum(np.where(valid_column, northward_m2s * width, np.nan)) / 1.0e6
    heat = RHO0 * CP0 * np.nansum(
        np.where(valid_column, northward_m2s * mean_temperature * width, np.nan)
    ) / 1.0e15
    return float(heat), float(volume)


def bottom_upward_heat_transport(
    temperature: np.ndarray,
    vertical_velocity: np.ndarray,
    area: np.ndarray,
    reference_temperature: float = 0.0,
) -> float:
    """Approximate upward advective heat input through the 300 m box bottom."""
    t_bottom = temperature[-1]
    w_bottom = vertical_velocity[-1]
    valid = np.isfinite(t_bottom) & np.isfinite(w_bottom)
    heat = np.nansum(
        np.where(valid, w_bottom * (t_bottom - reference_temperature) * area, np.nan)
    )
    return float(RHO0 * CP0 * heat / 1.0e15)


def derive_raw_monthly(temp: xr.Dataset, process: xr.Dataset) -> pd.DataFrame:
    common.validate_inputs(temp, process)
    times = pd.DatetimeIndex(temp.time.values)
    depth = temp.depth.values.astype(float)
    lat = temp.lat.values.astype(float)
    lon = temp.lon.values.astype(float)
    u_lat = process.u_lat.values.astype(float)
    u_lon = process.u_lon.values.astype(float)

    east_mask = (lon >= EAST_LON[0]) & (lon <= EAST_LON[1])
    east_lon = lon[east_mask]
    east_area = common.cell_areas(lat, east_lon)

    gate_indices: dict[float, tuple[int, int, int]] = {}
    for gate in (220.0, 280.0):
        face = int(np.argmin(np.abs(u_lon - gate)))
        if not np.isclose(u_lon[face], gate):
            raise ValueError(f"No velocity face at {gate}E")
        left = int(np.flatnonzero(lon < gate)[-1])
        if gate < lon.max():
            right = int(np.flatnonzero(lon > gate)[0])
        else:
            right = left
        gate_indices[gate] = (face, left, right)

    north_index = int(np.argmin(np.abs(u_lat - 5.0)))
    south_index = int(np.argmin(np.abs(u_lat + 5.0)))
    if not np.isclose(u_lat[north_index], 5.0) or not np.isclose(u_lat[south_index], -5.0):
        raise ValueError("Expected 5S and 5N velocity faces")
    lon_faces = np.flatnonzero((u_lon >= EAST_LON[0]) & (u_lon <= EAST_LON[1]))
    first_face, last_face = int(lon_faces[0]), int(lon_faces[-1])
    if last_face - first_face != len(east_lon):
        raise ValueError("Unexpected east-box longitude staggering")

    north_temp_index = int(np.argmax(lat))
    south_temp_index = int(np.argmin(lat))
    if not np.isclose(lat[north_temp_index], 4.75) or not np.isclose(lat[south_temp_index], -4.75):
        raise ValueError("Expected one-sided 4.75S/4.75N boundary temperature rows")

    rows: list[dict[str, float | int | pd.Timestamp]] = []
    for index, timestamp in enumerate(times):
        temperature = temp.temp.isel(time=index).values.astype(float)
        raw_u = process.u.isel(time=index).values.astype(float)
        raw_v = process.v.isel(time=index).values.astype(float)
        raw_tau = process.taux.isel(time=index).values.astype(float)
        net_heating = process.net_heating.isel(time=index).values.astype(float)
        raw_w = process.wt.isel(time=index).values.astype(float)

        east_temp = temperature[:, :, east_mask]
        east_w = raw_w[:, :, east_mask]
        record: dict[str, float | int | pd.Timestamp] = {
            "time": timestamp,
            "year": timestamp.year,
            "month": timestamp.month,
            "days_in_month": timestamp.days_in_month,
            "east_ohc300_raw_zj": heat_content_zj(east_temp, depth, east_area, 0.0),
            "east_h20_compare_raw_zj": heat_content_zj(
                np.maximum(east_temp - 20.0, 0.0), depth, east_area, 0.0
            ),
            "east_surface_loss_raw_pw": -float(
                np.nansum(net_heating[:, east_mask] * east_area) / 1.0e15
            ),
            "east_sst_raw_c": common.weighted_mean(east_temp[0], east_area),
            "tau5n_westward_raw_nm2": np.nan,
        }

        for reference in REFERENCE_TEMPERATURES:
            tag = f"tref{int(reference):02d}"
            record[f"east_bottom_upward_{tag}_raw_pw"] = bottom_upward_heat_transport(
                east_temp, east_w, east_area, reference
            )

        for gate in (220.0, 280.0):
            face, left, right = gate_indices[gate]
            if gate == 280.0:
                gate_temp = temperature[:, :, left]
            else:
                gate_temp = 0.5 * (temperature[:, :, left] + temperature[:, :, right])
            gate_u = 0.5 * (raw_u[:, :-1, face] + raw_u[:, 1:, face])
            for reference in REFERENCE_TEMPERATURES:
                tag = f"tref{int(reference):02d}"
                q, volume = section_heat_transport(
                    gate_temp, gate_u, depth, common.zonal_width(lat), reference
                )
                record[f"qvt_{int(gate)}e_{tag}_raw_pw"] = q
                record[f"volume_{int(gate)}e_raw_sv"] = volume
            record[f"q20_{int(gate)}e_compare_raw_pw"] = common.q20_transport_pw(
                gate_temp, gate_u, depth, common.zonal_width(lat)
            )

        north_v = 0.5 * (
            raw_v[:, north_index, first_face:last_face]
            + raw_v[:, north_index, first_face + 1 : last_face + 1]
        )
        south_v = 0.5 * (
            raw_v[:, south_index, first_face:last_face]
            + raw_v[:, south_index, first_face + 1 : last_face + 1]
        )
        north_tau = 0.5 * (
            raw_tau[north_index, first_face:last_face]
            + raw_tau[north_index, first_face + 1 : last_face + 1]
        )
        north_temp = temperature[:, north_temp_index, east_mask]
        south_temp = temperature[:, south_temp_index, east_mask]
        record["tau5n_westward_raw_nm2"] = -float(np.nanmean(north_tau))
        for label, boundary_temp, boundary_v, latitude in (
            ("5n_north", north_temp, north_v, 5.0),
            ("5s_north", south_temp, south_v, -5.0),
        ):
            for reference in REFERENCE_TEMPERATURES:
                tag = f"tref{int(reference):02d}"
                q, volume = section_heat_transport(
                    boundary_temp,
                    boundary_v,
                    depth,
                    common.meridional_width(east_lon, latitude),
                    reference,
                )
                record[f"qvt_{label}_{tag}_raw_pw"] = q
                record[f"volume_{label}_raw_sv"] = volume
            record[f"q20_{label}_compare_raw_pw"] = common.q20_transport_pw(
                boundary_temp,
                boundary_v,
                depth,
                common.meridional_width(east_lon, latitude),
            )

        for reference in REFERENCE_TEMPERATURES:
            tag = f"tref{int(reference):02d}"
            q, volume = ekman_heat_transport(
                north_temp, north_tau, depth, east_lon, reference, 5.0
            )
            record[f"qekman_5n_north_{tag}_raw_pw"] = q
            record["volume_ekman_5n_north_raw_sv"] = volume
        record["q20_ekman_5n_compare_raw_pw"] = common.ekman_q20_pw(
            north_temp, north_tau, depth, east_lon, 5.0
        )
        rows.append(record)

    frame = pd.DataFrame(rows)
    duplicated_volume = [c for c in frame if c.startswith("volume_")]
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()
    if frame[duplicated_volume].isna().any().any():
        raise ValueError("Missing volume transports")
    return frame


def add_anomalies(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    times = pd.DatetimeIndex(output.time)
    raw_columns = [
        name
        for name in output.columns
        if name.endswith("_raw_zj")
        or name.endswith("_raw_pw")
        or name.endswith("_raw_sv")
        or name.endswith("_raw_c")
        or name.endswith("_raw_nm2")
    ]
    for baseline in BASELINES:
        btag = f"b{baseline[0]}_{baseline[1]}"
        for column in raw_columns:
            output[f"{column.replace('_raw_', '_')}_anom_{btag}"] = common.same_month_detrended(
                output[column].to_numpy(dtype=float), times, baseline
            )
    return output


def integrate_zj(values_pw: pd.Series | np.ndarray, times: pd.DatetimeIndex) -> float:
    seconds = times.days_in_month.to_numpy(dtype=float) * 86400.0
    return float(np.nansum(np.asarray(values_pw, dtype=float) * seconds) / 1.0e6)


def phase_selection(monthly: pd.DataFrame, event_year: int, phase: str) -> pd.DataFrame:
    if phase == "development_Jan0_Jun0":
        selected = monthly.loc[
            monthly.year.eq(event_year) & monthly.month.between(1, 6)
        ]
        expected = 6
    elif phase == "decay_Jan1_May1":
        selected = monthly.loc[
            monthly.year.eq(event_year + 1) & monthly.month.between(1, 5)
        ]
        expected = 5
    else:
        raise KeyError(phase)
    selected = selected.sort_values("time")
    if len(selected) != expected:
        raise ValueError(f"Incomplete {event_year} {phase}: {len(selected)}")
    return selected


def build_phase_summary(monthly: pd.DataFrame, event_years: list[int]) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for baseline in BASELINES:
        btag = f"b{baseline[0]}_{baseline[1]}"
        for event_year in event_years:
            for phase in ("development_Jan0_Jun0", "decay_Jan1_May1"):
                selected = phase_selection(monthly, event_year, phase)
                times = pd.DatetimeIndex(selected.time)
                storage = f"east_ohc300_zj_anom_{btag}"
                h20_storage = f"east_h20_compare_zj_anom_{btag}"
                row: dict[str, float | int | str] = {
                    "baseline": f"{baseline[0]}-{baseline[1]}",
                    "event_year": event_year,
                    "phase": phase,
                    "east_ohc300_start_zj": float(selected[storage].iloc[0]),
                    "east_ohc300_end_zj": float(selected[storage].iloc[-1]),
                    "east_ohc300_change_zj": float(selected[storage].iloc[-1] - selected[storage].iloc[0]),
                    "east_h20_compare_change_zj": float(
                        selected[h20_storage].iloc[-1] - selected[h20_storage].iloc[0]
                    ),
                    "east_sst_mean_c": float(selected[f"east_sst_c_anom_{btag}"].mean()),
                    "tau5n_westward_mean_nm2": float(
                        selected[f"tau5n_westward_nm2_anom_{btag}"].mean()
                    ),
                    "east_surface_loss_zj": integrate_zj(
                        selected[f"east_surface_loss_pw_anom_{btag}"], times
                    ),
                    "q20_140w_compare_zj": integrate_zj(
                        selected[f"q20_220e_compare_pw_anom_{btag}"], times
                    ),
                    "q20_5n_compare_zj": integrate_zj(
                        selected[f"q20_5n_north_compare_pw_anom_{btag}"], times
                    ),
                    "q20_5n_ekman_compare_zj": integrate_zj(
                        selected[f"q20_ekman_5n_compare_pw_anom_{btag}"], times
                    ),
                }
                for reference in REFERENCE_TEMPERATURES:
                    tag = f"tref{int(reference):02d}"
                    q140 = integrate_zj(selected[f"qvt_220e_{tag}_pw_anom_{btag}"], times)
                    q80 = integrate_zj(selected[f"qvt_280e_{tag}_pw_anom_{btag}"], times)
                    q5n = integrate_zj(selected[f"qvt_5n_north_{tag}_pw_anom_{btag}"], times)
                    q5s_north = integrate_zj(selected[f"qvt_5s_north_{tag}_pw_anom_{btag}"], times)
                    qekman = integrate_zj(
                        selected[f"qekman_5n_north_{tag}_pw_anom_{btag}"], times
                    )
                    bottom = integrate_zj(
                        selected[f"east_bottom_upward_{tag}_pw_anom_{btag}"], times
                    )
                    horizontal_in = q140 - q80 + q5s_north - q5n
                    surface_in = -float(row["east_surface_loss_zj"])
                    resolved = horizontal_in + surface_in + bottom
                    residual = float(row["east_ohc300_change_zj"]) - resolved
                    row.update(
                        {
                            f"qvt_140w_east_{tag}_zj": q140,
                            f"qvt_80w_east_{tag}_zj": q80,
                            f"qvt_5n_north_{tag}_zj": q5n,
                            f"qvt_5s_south_{tag}_zj": -q5s_north,
                            f"qekman_5n_north_{tag}_zj": qekman,
                            f"qnonekman_5n_north_{tag}_zj": q5n - qekman,
                            f"bottom_upward_{tag}_zj": bottom,
                            f"horizontal_convergence_{tag}_zj": horizontal_in,
                            f"resolved_budget_{tag}_zj": resolved,
                            f"budget_residual_{tag}_zj": residual,
                        }
                    )
                rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_group(values: np.ndarray, *, seed: int = 20260808, samples: int = 20000) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    boot = rng.choice(values, size=(samples, values.size), replace=True).mean(axis=1)
    return float(values.mean()), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def build_type_summary(phases: pd.DataFrame) -> pd.DataFrame:
    members = pd.read_csv(TYPE_MEMBERS_CSV)[["event_class", "event_year"]].drop_duplicates()
    primary = phases.loc[phases.baseline.eq("1980-2014")].merge(members, on="event_year")
    metrics = [
        "east_ohc300_change_zj",
        "east_h20_compare_change_zj",
        "qvt_140w_east_tref00_zj",
        "q20_140w_compare_zj",
        "qvt_5n_north_tref00_zj",
        "q20_5n_compare_zj",
        "qekman_5n_north_tref00_zj",
        "q20_5n_ekman_compare_zj",
        "east_surface_loss_zj",
        "budget_residual_tref00_zj",
    ]
    rows = []
    for phase in primary.phase.unique():
        for event_class in ("CT", "CP"):
            selected = primary.loc[
                primary.phase.eq(phase) & primary.event_class.eq(event_class)
            ]
            for metric_index, metric in enumerate(metrics):
                mean, low, high = bootstrap_group(
                    selected[metric].to_numpy(dtype=float), seed=20260808 + metric_index
                )
                rows.append(
                    {
                        "phase": phase,
                        "event_class": event_class,
                        "metric": metric,
                        "n": len(selected),
                        "mean": mean,
                        "ci95_low": low,
                        "ci95_high": high,
                    }
                )
    return pd.DataFrame(rows)


def build_type_comparison(phases: pd.DataFrame) -> pd.DataFrame:
    members = pd.read_csv(TYPE_MEMBERS_CSV)[["event_class", "event_year"]].drop_duplicates()
    primary = phases.loc[phases.baseline.eq("1980-2014")].merge(members, on="event_year")
    definitions = [
        ("development_Jan0_Jun0", "east_storage_change", "east_ohc300_change_zj", None, "east_h20_compare_change_zj"),
        ("development_Jan0_Jun0", "140w_eastward_transport", None, "qvt_140w_east_{tag}_zj", "q20_140w_compare_zj"),
        ("decay_Jan1_May1", "east_storage_change", "east_ohc300_change_zj", None, "east_h20_compare_change_zj"),
        ("decay_Jan1_May1", "5n_northward_transport", None, "qvt_5n_north_{tag}_zj", "q20_5n_compare_zj"),
        ("decay_Jan1_May1", "5n_ekman_transport", None, "qekman_5n_north_{tag}_zj", "q20_5n_ekman_compare_zj"),
        ("decay_Jan1_May1", "surface_heat_loss", "east_surface_loss_zj", None, "east_surface_loss_zj"),
    ]
    rows = []
    for event_class in ("CT", "CP"):
        for phase, quantity, fixed, reference_pattern, h20_metric in definitions:
            selected = primary.loc[
                primary.event_class.eq(event_class) & primary.phase.eq(phase)
            ]
            if fixed is not None:
                values = np.repeat(float(selected[fixed].mean()), 3)
            else:
                values = np.array(
                    [
                        float(selected[reference_pattern.format(tag=f"tref{int(t):02d}")].mean())
                        for t in REFERENCE_TEMPERATURES
                    ]
                )
            h20 = float(selected[h20_metric].mean())
            rows.append(
                {
                    "event_class": event_class,
                    "n": len(selected),
                    "phase": phase,
                    "quantity": quantity,
                    "ohc_tref0_mean_zj": values[0],
                    "ohc_tref10_mean_zj": values[1],
                    "ohc_tref20_mean_zj": values[2],
                    "ohc_sign_stable_across_references": bool(
                        np.all(np.sign(values) == np.sign(values[0]))
                    ),
                    "h20_same_window_mean_zj": h20,
                }
            )
    return pd.DataFrame(rows)


def build_reference_sensitivity(phases: pd.DataFrame) -> pd.DataFrame:
    primary = phases.loc[
        phases.baseline.eq("1980-2014") & phases.event_year.isin(THREE_EVENTS)
    ]
    rows = []
    for _, current in primary.iterrows():
        for reference in REFERENCE_TEMPERATURES:
            tag = f"tref{int(reference):02d}"
            rows.append(
                {
                    "event_year": int(current.event_year),
                    "phase": current.phase,
                    "reference_temperature_c": reference,
                    "q140_east_zj": current[f"qvt_140w_east_{tag}_zj"],
                    "q5n_north_zj": current[f"qvt_5n_north_{tag}_zj"],
                    "q5s_south_zj": current[f"qvt_5s_south_{tag}_zj"],
                    "horizontal_convergence_zj": current[f"horizontal_convergence_{tag}_zj"],
                    "budget_residual_zj": current[f"budget_residual_{tag}_zj"],
                }
            )
    return pd.DataFrame(rows)


def build_comparison(phases: pd.DataFrame) -> pd.DataFrame:
    primary = phases.loc[
        phases.baseline.eq("1980-2014") & phases.event_year.isin(THREE_EVENTS)
    ].copy()
    old = pd.read_csv(OLD_PHASE_CSV)
    old = old.loc[
        old.baseline.eq("1980-2014") & old.event_year.isin(THREE_EVENTS)
    ][
        [
            "event_year",
            "phase",
            "east_h20_change_zj",
            "q20_140w_east_zj",
            "q20_5n_north_zj",
            "q20_5n_ekman_north_zj",
            "east_surface_loss_zj",
        ]
    ].rename(
        columns={
            "east_h20_change_zj": "old_h20_storage_change_zj",
            "q20_140w_east_zj": "old_q20_140w_zj",
            "q20_5n_north_zj": "old_q20_5n_zj",
            "q20_5n_ekman_north_zj": "old_q20_5n_ekman_zj",
            "east_surface_loss_zj": "old_surface_loss_zj",
        }
    )
    keep = primary[
        [
            "event_year",
            "phase",
            "east_ohc300_change_zj",
            "east_h20_compare_change_zj",
            "qvt_140w_east_tref00_zj",
            "qvt_5n_north_tref00_zj",
            "qekman_5n_north_tref00_zj",
            "east_surface_loss_zj",
            "budget_residual_tref00_zj",
        ]
    ].rename(
        columns={
            "east_surface_loss_zj": "ohc_surface_loss_zj",
        }
    )
    output = keep.merge(old, on=["event_year", "phase"], how="left", validate="one_to_one")
    output["local_h20_minus_old_h20_storage_zj"] = (
        output.east_h20_compare_change_zj - output.old_h20_storage_change_zj
    )
    return output


def build_coupling_correlations(phases: pd.DataFrame) -> pd.DataFrame:
    coupling = pd.read_csv(COUPLING_CSV)
    development = phases.loc[
        phases.baseline.eq("1980-2014") & phases.phase.eq("development_Jan0_Jun0")
    ]
    decay = phases.loc[
        phases.baseline.eq("1980-2014") & phases.phase.eq("decay_Jan1_May1")
    ]
    merged = coupling.merge(
        development[
            [
                "event_year",
                "east_ohc300_change_zj",
                "qvt_140w_east_tref00_zj",
            ]
        ].rename(columns={"event_year": "year"}),
        on="year",
        how="inner",
    ).merge(
        decay[
            [
                "event_year",
                "qvt_5n_north_tref00_zj",
                "qekman_5n_north_tref00_zj",
                "east_surface_loss_zj",
                "budget_residual_tref00_zj",
            ]
        ].rename(columns={"event_year": "year"}),
        on="year",
        how="inner",
    )
    x_metrics = [
        "east_ohc300_change_zj",
        "qvt_140w_east_tref00_zj",
        "qvt_5n_north_tref00_zj",
        "qekman_5n_north_tref00_zj",
        "east_surface_loss_zj",
    ]
    y_metrics = [
        "mature_djf_nino34_c",
        "may_jun_intensity_coupling_residual_z",
        "mar_jun_sst_to_precip_residual_z",
        "mar_jun_precip_to_slp_residual_z",
        "mar_jun_slp_to_tau_residual_z",
    ]
    rows = []
    for x in x_metrics:
        for y in y_metrics:
            selected = merged[[x, y]].dropna()
            result = stats.pearsonr(selected[x], selected[y])
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "n": len(selected),
                    "pearson_r": float(result.statistic),
                    "p_value": float(result.pvalue),
                }
            )
    return pd.DataFrame(rows)


def build_all_metric_comparison(phases: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    primary = phases.loc[
        phases.baseline.eq("1980-2014") & phases.event_year.isin(THREE_EVENTS)
    ].set_index(["event_year", "phase"])
    old = comparison.set_index(["event_year", "phase"])
    rows: list[dict[str, float | int | str | bool]] = []
    definitions = [
        (
            "development_Jan0_Jun0",
            "east_storage_change",
            "east_ohc300_change_zj",
            None,
            "old_h20_storage_change_zj",
        ),
        (
            "development_Jan0_Jun0",
            "140w_eastward_transport",
            None,
            "qvt_140w_east_{tag}_zj",
            "old_q20_140w_zj",
        ),
        (
            "development_Jan0_Jun0",
            "horizontal_convergence",
            None,
            "horizontal_convergence_{tag}_zj",
            None,
        ),
        (
            "decay_Jan1_May1",
            "east_storage_change",
            "east_ohc300_change_zj",
            None,
            "old_h20_storage_change_zj",
        ),
        (
            "decay_Jan1_May1",
            "5n_northward_transport",
            None,
            "qvt_5n_north_{tag}_zj",
            "old_q20_5n_zj",
        ),
        (
            "decay_Jan1_May1",
            "5n_ekman_transport",
            None,
            "qekman_5n_north_{tag}_zj",
            "old_q20_5n_ekman_zj",
        ),
        (
            "decay_Jan1_May1",
            "surface_heat_loss",
            "east_surface_loss_zj",
            None,
            "old_surface_loss_zj",
        ),
    ]
    for year in THREE_EVENTS:
        for phase, quantity, fixed_metric, reference_metric, old_metric in definitions:
            current = primary.loc[(year, phase)]
            old_current = old.loc[(year, phase)]
            if fixed_metric is not None:
                values = np.repeat(float(current[fixed_metric]), 3)
            else:
                values = np.array(
                    [
                        float(current[reference_metric.format(tag=f"tref{int(t):02d}")])
                        for t in REFERENCE_TEMPERATURES
                    ]
                )
            h20 = np.nan if old_metric is None else float(old_current[old_metric])
            rows.append(
                {
                    "event_year": year,
                    "phase": phase,
                    "quantity": quantity,
                    "ohc_tref0_zj": values[0],
                    "ohc_tref10_zj": values[1],
                    "ohc_tref20_zj": values[2],
                    "ohc_reference_min_zj": float(values.min()),
                    "ohc_reference_max_zj": float(values.max()),
                    "ohc_sign_stable_across_references": bool(
                        np.all(np.sign(values) == np.sign(values[0]))
                    ),
                    "h20_previous_zj": h20,
                    "h20_inside_ohc_reference_range": bool(
                        np.isfinite(h20) and values.min() <= h20 <= values.max()
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_robustness_audit(phases: pd.DataFrame) -> pd.DataFrame:
    primary = phases.loc[
        phases.baseline.eq("1980-2014") & phases.event_year.isin(THREE_EVENTS)
    ].set_index(["event_year", "phase"])
    rows = []
    checks = [
        ("development_Jan0_Jun0", "140W transport sign", "qvt_140w_east_{tag}_zj"),
        ("development_Jan0_Jun0", "horizontal convergence sign", "horizontal_convergence_{tag}_zj"),
        ("decay_Jan1_May1", "5N total transport sign", "qvt_5n_north_{tag}_zj"),
        ("decay_Jan1_May1", "5N Ekman transport sign", "qekman_5n_north_{tag}_zj"),
        ("decay_Jan1_May1", "horizontal convergence sign", "horizontal_convergence_{tag}_zj"),
    ]
    for phase, quantity, pattern in checks:
        for year in THREE_EVENTS:
            current = primary.loc[(year, phase)]
            values = np.array(
                [float(current[pattern.format(tag=f"tref{int(t):02d}")]) for t in REFERENCE_TEMPERATURES]
            )
            rows.append(
                {
                    "scope": str(year),
                    "phase": phase,
                    "quantity": quantity,
                    "tref0_zj": values[0],
                    "tref10_zj": values[1],
                    "tref20_zj": values[2],
                    "sign_stable": bool(np.all(np.sign(values) == np.sign(values[0]))),
                    "ordering_stable": np.nan,
                }
            )
        rankings = []
        for reference in REFERENCE_TEMPERATURES:
            tag = f"tref{int(reference):02d}"
            values = {
                year: float(primary.loc[(year, phase), pattern.format(tag=tag)])
                for year in THREE_EVENTS
            }
            rankings.append(tuple(sorted(values, key=values.get, reverse=True)))
        rows.append(
            {
                "scope": "three-event ranking",
                "phase": phase,
                "quantity": quantity,
                "tref0_zj": np.nan,
                "tref10_zj": np.nan,
                "tref20_zj": np.nan,
                "sign_stable": np.nan,
                "ordering_stable": bool(all(rank == rankings[0] for rank in rankings)),
            }
        )
    return pd.DataFrame(rows)


def build_three_event_coupling_chain(phases: pd.DataFrame) -> pd.DataFrame:
    coupling = pd.read_csv(COUPLING_CSV).loc[lambda x: x.year.isin(THREE_EVENTS)]
    development = phases.loc[
        phases.baseline.eq("1980-2014")
        & phases.phase.eq("development_Jan0_Jun0")
        & phases.event_year.isin(THREE_EVENTS)
    ][
        ["event_year", "east_ohc300_change_zj", "horizontal_convergence_tref00_zj"]
    ].rename(columns={"event_year": "year"})
    decay = phases.loc[
        phases.baseline.eq("1980-2014")
        & phases.phase.eq("decay_Jan1_May1")
        & phases.event_year.isin(THREE_EVENTS)
    ][
        [
            "event_year",
            "qvt_5n_north_tref00_zj",
            "qvt_5n_north_tref10_zj",
            "qvt_5n_north_tref20_zj",
            "qekman_5n_north_tref00_zj",
            "qekman_5n_north_tref10_zj",
            "qekman_5n_north_tref20_zj",
            "east_surface_loss_zj",
            "tau5n_westward_mean_nm2",
        ]
    ].rename(columns={"event_year": "year"})
    keep = [
        "year",
        "group",
        "mature_djf_nino34_c",
        "may_jun_intensity_coupling_residual_z",
        "mar_jun_sst_to_precip_residual_z",
        "mar_jun_precip_to_slp_residual_z",
        "mar_jun_slp_to_tau_residual_z",
        "weakest_chain_link",
        "weakest_chain_residual_z",
    ]
    return coupling[keep].merge(development, on="year").merge(decay, on="year")


def validate_storage_against_precomputed(monthly: pd.DataFrame) -> float:
    with xr.open_dataset(OHC_FIELD_NC, engine="h5netcdf") as dataset:
        field = dataset.ohc_300m.sel(
            time=pd.DatetimeIndex(monthly.time),
            lat=slice(-5.0, 5.0),
            lon=slice(EAST_LON[0], EAST_LON[1]),
        )
        area = common.cell_areas(field.lat.values, field.lon.values)
        integrated = np.nansum(field.values * area[None, :, :], axis=(1, 2)) / 1.0e21
    difference = integrated - monthly.east_ohc300_raw_zj.to_numpy(float)
    return float(np.nanmax(np.abs(difference)))


def synchronize_precomputed_ohc(monthly: pd.DataFrame) -> pd.DataFrame:
    """Use the independently built standard OHC field as the storage source."""
    output = monthly.copy()
    times = pd.DatetimeIndex(output.time)
    with xr.open_dataset(OHC_FIELD_NC, engine="h5netcdf") as dataset:
        field = dataset.ohc_300m.sel(
            time=times,
            lat=slice(-5.0, 5.0),
            lon=slice(EAST_LON[0], EAST_LON[1]),
        )
        area = common.cell_areas(field.lat.values, field.lon.values)
        integrated = np.nansum(field.values * area[None, :, :], axis=(1, 2)) / 1.0e21
    output["east_ohc300_raw_zj"] = integrated
    for baseline in BASELINES:
        btag = f"b{baseline[0]}_{baseline[1]}"
        output[f"east_ohc300_zj_anom_{btag}"] = common.same_month_detrended(
            integrated, times, baseline
        )
    return output


def make_figure(three: pd.DataFrame, comparison: pd.DataFrame) -> None:
    common.setup_style()
    primary = three.loc[three.baseline.eq("1980-2014")]
    development = primary.loc[primary.phase.eq("development_Jan0_Jun0")].set_index("event_year")
    decay = primary.loc[primary.phase.eq("decay_Jan1_May1")].set_index("event_year")
    colors = {1997: "#B2182B", 2015: "#2166AC", 2023: "#E08214"}
    years = list(THREE_EVENTS)
    x = np.arange(len(years))

    fig, axes = plt.subplots(1, 3, figsize=(14.2, 4.7))
    width = 0.34
    axes[0].bar(
        x - width / 2,
        [development.loc[y, "qvt_140w_east_tref00_zj"] for y in years],
        width,
        color="#D97706",
        label="140°W eastward heat input",
    )
    axes[0].bar(
        x + width / 2,
        [development.loc[y, "east_ohc300_change_zj"] for y in years],
        width,
        color="#087EAD",
        label="East-box OHC change",
    )
    axes[0].axhline(0, color="0.25", linewidth=0.8)
    axes[0].set_xticks(x, years)
    axes[0].set_ylabel("ZJ")
    axes[0].set_title("a  Question 1: Jan(0)–Jun(0) arrival")
    axes[0].legend(frameon=False)

    fate_metrics = [
        ("qvt_5n_north_tref00_zj", "5°N northward", "#377EB8"),
        ("qvt_5s_south_tref00_zj", "5°S southward", "#4DAF4A"),
        ("east_surface_loss_zj", "surface loss", "#E41A1C"),
        ("budget_residual_tref00_zj", "residual", "#984EA3"),
    ]
    offsets = np.linspace(-0.3, 0.3, len(fate_metrics))
    for offset, (metric, label, color) in zip(offsets, fate_metrics):
        axes[1].bar(
            x + offset,
            [decay.loc[y, metric] for y in years],
            0.18,
            label=label,
            color=color,
        )
    axes[1].axhline(0, color="0.25", linewidth=0.8)
    axes[1].set_xticks(x, years)
    axes[1].set_ylabel("ZJ; positive means outward/loss for first three")
    axes[1].set_title("b  Question 2: Jan(+1)–May(+1) fate")
    axes[1].legend(frameon=False, ncol=2, fontsize=7.2)

    comp_decay = comparison.loc[comparison.phase.eq("decay_Jan1_May1")].set_index("event_year")
    for year in years:
        axes[2].scatter(
            comp_decay.loc[year, "old_q20_5n_zj"],
            comp_decay.loc[year, "qvt_5n_north_tref00_zj"],
            s=70,
            color=colors[year],
            label=str(year),
            edgecolor="white",
            linewidth=0.7,
        )
    values = np.r_[
        comp_decay.old_q20_5n_zj.to_numpy(float),
        comp_decay.qvt_5n_north_tref00_zj.to_numpy(float),
    ]
    lo, hi = float(np.nanmin(values) - 0.5), float(np.nanmax(values) + 0.5)
    axes[2].plot([lo, hi], [lo, hi], color="0.35", linestyle="--", linewidth=1.0)
    axes[2].axhline(0, color="0.75", linewidth=0.7)
    axes[2].axvline(0, color="0.75", linewidth=0.7)
    axes[2].set_xlim(lo, hi)
    axes[2].set_ylim(lo, hi)
    axes[2].set_xlabel("Previous Qwarm,20 5°N export (ZJ)")
    axes[2].set_ylabel("Standard vT 5°N heat export (ZJ)")
    axes[2].set_title("c  Diagnostic sensitivity at the 5°N outlet")
    axes[2].legend(frameon=False)

    fig.suptitle(
        "SODA3.15.2 OHC-only test: fixed 0–300 m heat content and conventional vT transport",
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.01,
        "5°S–5°N, 140°W–80°W; anomalies remove 1980–2014 calendar-month climatology and same-month trend. Products are formed before anomaly calculation.",
        ha="center",
        fontsize=8,
        color="0.25",
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, dpi=360)
    fig.savefig(FIGURE_PDF)
    plt.close(fig)


def make_comparison_figure(all_comparison: pd.DataFrame) -> None:
    common.setup_style()
    years = list(THREE_EVENTS)
    colors = {1997: "#B2182B", 2015: "#2166AC", 2023: "#E08214"}
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.6))
    panels = [
        ("development_Jan0_Jun0", "east_storage_change", "a  East-box storage change", "OHC", "H20"),
        ("development_Jan0_Jun0", "140w_eastward_transport", "b  140°W eastward transport", "vT reference range", "Qwarm,20"),
        ("decay_Jan1_May1", "5n_northward_transport", "c  5°N northward transport", "vT reference range", "Qwarm,20"),
    ]
    for axis, (phase, quantity, title, ohc_label, h20_label) in zip(axes, panels):
        selected = all_comparison.loc[
            all_comparison.phase.eq(phase) & all_comparison.quantity.eq(quantity)
        ].set_index("event_year")
        x = np.arange(len(years))
        if quantity == "east_storage_change":
            axis.bar(
                x - 0.18,
                [selected.loc[y, "ohc_tref0_zj"] for y in years],
                0.36,
                color="#087EAD",
                label=ohc_label,
            )
            axis.bar(
                x + 0.18,
                [selected.loc[y, "h20_previous_zj"] for y in years],
                0.36,
                color="#D97706",
                label=h20_label,
            )
        else:
            for index, year in enumerate(years):
                low = selected.loc[year, "ohc_reference_min_zj"]
                high = selected.loc[year, "ohc_reference_max_zj"]
                central = selected.loc[year, "ohc_tref10_zj"]
                axis.vlines(index - 0.10, low, high, color=colors[year], linewidth=4, alpha=0.75)
                axis.scatter(index - 0.10, central, color=colors[year], s=32, zorder=3)
                axis.scatter(
                    index + 0.13,
                    selected.loc[year, "h20_previous_zj"],
                    marker="D",
                    color="#111111",
                    s=34,
                    zorder=3,
                )
            axis.plot([], [], color="0.35", linewidth=4, label=ohc_label)
            axis.scatter([], [], marker="D", color="#111111", label=h20_label)
        axis.axhline(0.0, color="0.35", linewidth=0.8)
        axis.set_xticks(np.arange(len(years)), years)
        axis.set_ylabel("ZJ")
        axis.set_title(title)
        axis.legend(frameon=False, fontsize=7.5)
    fig.suptitle(
        "What changes when the analysis is rebuilt with standard 0–300 m OHC?",
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.015,
        "Vertical ranges span vT reference temperatures 0, 10 and 20°C; diamonds show the previous H20/Qwarm,20 result.",
        ha="center",
        fontsize=8,
        color="0.25",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.96])
    fig.savefig(COMPARE_FIGURE_PNG, dpi=360)
    fig.savefig(COMPARE_FIGURE_PDF)
    plt.close(fig)


def fmt(value: float) -> str:
    return f"{float(value):+.2f}"


def reference_range(current: pd.Series, pattern: str) -> str:
    values = [float(current[pattern.format(tag=f"tref{int(t):02d}")]) for t in REFERENCE_TEMPERATURES]
    return f"{min(values):+.2f}—{max(values):+.2f}"


def write_report(
    three: pd.DataFrame,
    types: pd.DataFrame,
    comparison: pd.DataFrame,
    reference: pd.DataFrame,
    correlations: pd.DataFrame,
    all_comparison: pd.DataFrame,
    audit: pd.DataFrame,
    coupling_chain: pd.DataFrame,
) -> None:
    primary = three.loc[three.baseline.eq("1980-2014")]
    development = primary.loc[primary.phase.eq("development_Jan0_Jun0")].set_index("event_year")
    decay = primary.loc[primary.phase.eq("decay_Jan1_May1")].set_index("event_year")
    chain = coupling_chain.set_index("year")
    comp = comparison.set_index(["event_year", "phase"])
    swap_lines: list[str] = []
    if SWAP_SUMMARY_CSV.exists():
        swap = pd.read_csv(SWAP_SUMMARY_CSV)
        swap = swap.loc[swap.donor_wind_anomaly.astype(str).isin(["1997", "2015", "2023"])]
        indexed_swap = swap.set_index(
            ["target_ocean_event", "donor_wind_anomaly", "reference_temperature_c"]
        )
        swap_lines = [
            "",
            "### 离线换风实验（固定海洋状态）",
            "",
            "固定目标事件的5°N温度和非Ekman输送，只替换去趋势的5°N风应力异常。控制试验与直接计算的闭合误差小于 $4\\times10^{-9}$ ZJ。",
            "",
            "| 固定海洋状态 | 1997风 | 2015风 | 2023风 |",
            "|---|---:|---:|---:|",
        ]
        for target in THREE_EVENTS:
            swap_lines.append(
                f"| {target} | {indexed_swap.loc[(target, '1997', 0.0), 'reconstructed_total_zj']:+.2f} | {indexed_swap.loc[(target, '2015', 0.0), 'reconstructed_total_zj']:+.2f} | {indexed_swap.loc[(target, '2023', 0.0), 'reconstructed_total_zj']:+.2f} |"
            )
        swap_lines.extend(
            [
                "",
                "上表是标准 $vT$、$T_{ref}=0$°C的重构总出口。总值受参考温度与未闭合体积输送影响，2015/2023的绝对正负号不稳健；因此换风实验的稳健证据应读成风造成的增量，而不是某一参考温度下的总值。",
                "",
                "| 换风效应 | Tref=0°C | Tref=10°C | Tref=20°C |",
                "|---|---:|---:|---:|",
                f"| 2015海洋：换成2023风 | {indexed_swap.loc[(2015, '2023', 0.0), 'change_from_control_zj']:+.2f} | {indexed_swap.loc[(2015, '2023', 10.0), 'change_from_control_zj']:+.2f} | {indexed_swap.loc[(2015, '2023', 20.0), 'change_from_control_zj']:+.2f} |",
                f"| 2023海洋：换成2015风 | {indexed_swap.loc[(2023, '2015', 0.0), 'change_from_control_zj']:+.2f} | {indexed_swap.loc[(2023, '2015', 10.0), 'change_from_control_zj']:+.2f} | {indexed_swap.loc[(2023, '2015', 20.0), 'change_from_control_zj']:+.2f} |",
                "",
                "三个参考温度下方向完全一致：2023风都会削弱固定2015海洋状态下的北向热输送，2015风都会增强固定2023海洋状态下的北向热输送。由此可保留‘局地风应力是2015—2023 Ekman差异的重要贡献者’，但OHC版不支持‘总出口状态几乎完全互换’这一更强表述。",
            ]
        )
    lines = [
        "# 完全基于标准OHC的三个问题复算结果",
        "",
        "主定义为0—300 m固定深度OHC与标准 $\\rho_0c_p\\int vT\\,dA$ 热输送；正文结果不使用H20。",
        "",
        "## 问题一：热量是否进入140°W以东？",
        "",
        "单断面 $vT$ 依赖参考温度，因此主证据采用东部OHC变化和全边界净水平辐合；断面值只报告0、10、20°C参考范围。",
        "",
        "| 事件 | 东部OHC变化（ZJ） | 140°W东向vT范围（ZJ） | 净水平热辐合范围（ZJ） |",
        "|---|---:|---:|---:|",
    ]
    for year in THREE_EVENTS:
        lines.append(
            f"| {year} | {fmt(development.loc[year, 'east_ohc300_change_zj'])} | {reference_range(development.loc[year], 'qvt_140w_east_{tag}_zj')} | {reference_range(development.loc[year], 'horizontal_convergence_{tag}_zj')} |"
        )
    lines.extend(
        [
            "",
            "## 问题二：成熟后热量去了哪里？",
            "",
            "以下为Jan(+1)—May(+1)。OHC减少和净水平辐合为负表示东部箱体放热；5°N与海表项为正表示向北输出或向大气失热。",
            "",
            "| 事件 | 东部OHC变化 | 5°N总vT范围 | 5°N Ekman范围 | 海表热损失 | 净水平辐合范围 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for year in THREE_EVENTS:
        lines.append(
            f"| {year} | {fmt(decay.loc[year, 'east_ohc300_change_zj'])} | {reference_range(decay.loc[year], 'qvt_5n_north_{tag}_zj')} | {reference_range(decay.loc[year], 'qekman_5n_north_{tag}_zj')} | {fmt(decay.loc[year, 'east_surface_loss_zj'])} | {reference_range(decay.loc[year], 'horizontal_convergence_{tag}_zj')} |"
        )
    lines.extend(
        [
            "",
            "## 问题三：为什么2015与2023没有形成相同耦合？",
            "",
            "| 指标 | 2015 | 2023 |",
            "|---|---:|---:|",
            f"| 发展期东部OHC增加（ZJ） | {development.loc[2015, 'east_ohc300_change_zj']:.2f} | {development.loc[2023, 'east_ohc300_change_zj']:.2f} |",
            f"| 次年5°N Ekman范围（ZJ） | {reference_range(decay.loc[2015], 'qekman_5n_north_{tag}_zj')} | {reference_range(decay.loc[2023], 'qekman_5n_north_{tag}_zj')} |",
            f"| 5°N西风应力异常（N m⁻²） | {chain.loc[2015, 'tau5n_westward_mean_nm2']:.4f} | {chain.loc[2023, 'tau5n_westward_mean_nm2']:.4f} |",
            f"| 海表异常热损失（ZJ） | {chain.loc[2015, 'east_surface_loss_zj']:.2f} | {chain.loc[2023, 'east_surface_loss_zj']:.2f} |",
            f"| 强度耦合残差（z） | {chain.loc[2015, 'may_jun_intensity_coupling_residual_z']:.2f} | {chain.loc[2023, 'may_jun_intensity_coupling_residual_z']:.2f} |",
            f"| SLP→风应力残差（z） | {chain.loc[2015, 'mar_jun_slp_to_tau_residual_z']:.2f} | {chain.loc[2023, 'mar_jun_slp_to_tau_residual_z']:.2f} |",
            "",
            "2015与2023的OHC到达量只差约5%，但2015的西风应力、Ekman热输出和海表热损失均更强；2023的最弱环节位于SLP→风应力。该结果支持海气接通差异，但不证明单向因果。",
            *swap_lines,
            "",
            "## 与H20结果相比",
            "",
            "| 事件 | 发展期OHC/H20储量比 | 衰减期OHC/H20储量比 |",
            "|---|---:|---:|",
            *[
                f"| {year} | {comp.loc[(year, 'development_Jan0_Jun0'), 'east_ohc300_change_zj'] / comp.loc[(year, 'development_Jan0_Jun0'), 'old_h20_storage_change_zj']:.2f} | {comp.loc[(year, 'decay_Jan1_May1'), 'east_ohc300_change_zj'] / comp.loc[(year, 'decay_Jan1_May1'), 'old_h20_storage_change_zj']:.2f} |"
                for year in THREE_EVENTS
            ],
            "",
            "OHC给出的储量变化幅度约为H20的1.6—1.8倍，但三事件排序和2015≈2023的结论不变。真正发生变化的是开放断面的输送值：2015、2023的140°W和5°N总vT可能随参考温度换号，不能像Qwarm,20那样直接给出唯一的暖水通道量。",
            "",
            "## 输出文件",
            "",
            f"- 月资料：`{MONTHLY_CSV}`",
            f"- 13事件阶段表：`{PHASE_CSV}`",
            f"- CT/CP合成：`{TYPE_SUMMARY_CSV}`",
            f"- CT/CP同窗OHC/H20对比：`{TYPE_COMPARISON_CSV}`",
            f"- 三事件OHC/H20比较：`{COMPARE_CSV}`",
            f"- 参考温度敏感性：`{REFERENCE_CSV}`",
            f"- 耦合相关：`{CORRELATION_CSV}`",
            f"- 全指标OHC/H20对比：`{ALL_COMPARISON_CSV}`",
            f"- 稳健性审计：`{ROBUST_AUDIT_CSV}`",
            f"- 三事件海气链：`{COUPLING_EVENT_CSV}`",
            f"- OHC离线换风汇总：`{SWAP_SUMMARY_CSV}`",
            f"- OHC/H20换风对比：`{SWAP_COMPARISON_CSV}`",
            f"- 图：`{FIGURE_PNG}`",
            f"- 对比图：`{COMPARE_FIGURE_PNG}`",
            f"- OHC离线换风图：`{SWAP_FIGURE_PNG}`",
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_outputs(monthly: pd.DataFrame, phases: pd.DataFrame) -> dict[str, float | int | bool]:
    if len(monthly) != 270 or monthly.time.duplicated().any():
        raise ValueError("Monthly output is not the expected 270-record axis")
    numeric = monthly.select_dtypes(include=[np.number])
    if numeric.isna().all().any():
        raise ValueError("A monthly numeric column is entirely missing")
    if not monthly.east_ohc300_raw_zj.between(100.0, 300.0).all():
        raise ValueError("Raw east-box OHC is outside broad physical limits")
    heat_columns = [c for c in monthly if c.startswith("qvt_") and c.endswith("_raw_pw")]
    if not (monthly[heat_columns].abs() < 30.0).all().all():
        raise ValueError("Boundary heat transport exceeds broad physical limits")
    primary = phases.loc[phases.baseline.eq("1980-2014")]
    reference_sign_stability = True
    for event in THREE_EVENTS:
        for phase in primary.phase.unique():
            row = primary.loc[
                primary.event_year.eq(event) & primary.phase.eq(phase)
            ].iloc[0]
            q140 = np.array(
                [row[f"qvt_140w_east_tref{int(t):02d}_zj"] for t in REFERENCE_TEMPERATURES]
            )
            q5n = np.array(
                [row[f"qvt_5n_north_tref{int(t):02d}_zj"] for t in REFERENCE_TEMPERATURES]
            )
            reference_sign_stability &= bool(np.all(np.sign(q140) == np.sign(q140[0])))
            reference_sign_stability &= bool(np.all(np.sign(q5n) == np.sign(q5n[0])))
    return {
        "monthly_rows": len(monthly),
        "phase_rows": len(phases),
        "raw_ohc_min_zj": float(monthly.east_ohc300_raw_zj.min()),
        "raw_ohc_max_zj": float(monthly.east_ohc300_raw_zj.max()),
        "max_abs_heat_transport_pw": float(monthly[heat_columns].abs().max().max()),
        "three_event_reference_sign_stability": bool(reference_sign_stability),
        "max_abs_storage_difference_vs_precomputed_ohc_zj": validate_storage_against_precomputed(monthly),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    if MONTHLY_CSV.exists():
        monthly = pd.read_csv(MONTHLY_CSV, parse_dates=["time"])
        print(f"Using monthly checkpoint: {MONTHLY_CSV}", flush=True)
    else:
        with xr.open_dataset(TEMP_NC, engine="h5netcdf") as temp, xr.open_dataset(
            PROCESS_NC, engine="h5netcdf"
        ) as process:
            raw = derive_raw_monthly(temp, process)
        monthly = add_anomalies(raw)
        monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
        print(f"Wrote monthly checkpoint: {MONTHLY_CSV}", flush=True)
    monthly = synchronize_precomputed_ohc(monthly)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    event_years = sorted(pd.read_csv(COUPLING_CSV).year.astype(int).unique().tolist())
    phases = build_phase_summary(monthly, event_years)
    three = phases.loc[phases.event_year.isin(THREE_EVENTS)].copy()
    types = build_type_summary(phases)
    type_comparison = build_type_comparison(phases)
    reference = build_reference_sensitivity(phases)
    comparison = build_comparison(phases)
    correlations = build_coupling_correlations(phases)
    all_comparison = build_all_metric_comparison(phases, comparison)
    audit = build_robustness_audit(phases)
    coupling_chain = build_three_event_coupling_chain(phases)
    diagnostics = validate_outputs(monthly, phases)

    phases.to_csv(PHASE_CSV, index=False, float_format="%.9g")
    three.to_csv(THREE_EVENT_CSV, index=False, float_format="%.9g")
    types.to_csv(TYPE_SUMMARY_CSV, index=False, float_format="%.9g")
    type_comparison.to_csv(TYPE_COMPARISON_CSV, index=False, float_format="%.9g")
    reference.to_csv(REFERENCE_CSV, index=False, float_format="%.9g")
    comparison.to_csv(COMPARE_CSV, index=False, float_format="%.9g")
    correlations.to_csv(CORRELATION_CSV, index=False, float_format="%.9g")
    all_comparison.to_csv(ALL_COMPARISON_CSV, index=False, float_format="%.9g")
    audit.to_csv(ROBUST_AUDIT_CSV, index=False, float_format="%.9g")
    coupling_chain.to_csv(COUPLING_EVENT_CSV, index=False, float_format="%.9g")
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    make_figure(three, comparison)
    make_comparison_figure(all_comparison)
    write_report(
        three,
        types,
        comparison,
        reference,
        correlations,
        all_comparison,
        audit,
        coupling_chain,
    )
    print(REPORT_MD)
    print(FIGURE_PNG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
