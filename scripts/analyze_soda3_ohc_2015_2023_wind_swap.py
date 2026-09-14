#!/usr/bin/env python3
"""Repeat the 1997/2015/2023 offline wind swap with standard OHC transport.

The target event keeps its 5N boundary temperature and its diagnosed
non-Ekman heat transport.  Only the calendar-month detrended 5N zonal-wind-
stress anomaly is replaced by that of the donor event.  Heat transports use
rho*Cp*integral[v*(T-Tref)]dA over 0--300 m; Tref=0 C is primary and 10/20 C
are reported as reference-temperature sensitivity tests.

This is an offline diagnostic reconstruction.  It does not allow temperature,
pressure, circulation, or the non-Ekman component to adjust to the donor wind.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
import xarray as xr

import analyze_soda3_ohc_only_three_questions as ohc


TEMP_NC = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
PROCESS_NC = ROOT / "data/raw/soda3/soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
MONTHLY_OHC_CSV = ROOT / "data/derived/research_2026/soda3_ohc_only_monthly_1980_2024.csv"
PHASE_OHC_CSV = ROOT / "data/derived/research_2026/soda3_ohc_only_phase_summary_13events.csv"
OLD_H20_SWAP_CSV = ROOT / "data/derived/research_2026/third_question_coupled_attribution_counterfactual.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/ohc_only_three_questions"
MONTHLY_CSV = DERIVED / "soda3_ohc_2015_2023_wind_swap_monthly.csv"
SUMMARY_CSV = DERIVED / "soda3_ohc_2015_2023_wind_swap_summary.csv"
MATRIX_CSV = DERIVED / "soda3_ohc_2015_2023_wind_swap_matrix.csv"
COMPARISON_CSV = DERIVED / "soda3_ohc_vs_h20_wind_swap_comparison.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_ohc_2015_2023_wind_swap_diagnostics.json"
FIGURE_PNG = OUT / "soda3_ohc_2015_2023_wind_swap.png"

BASELINE = (1980, 2014)
EVENTS = (1997, 2015, 2023)
REFERENCES = (0.0, 10.0, 20.0)
MONTHS = (1, 2, 3, 4, 5)


def same_month_detrended_array(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline: tuple[int, int] = BASELINE,
) -> np.ndarray:
    """Remove a calendar-month climatology and linear trend, time first."""
    array = np.asarray(values, dtype=float)
    flat = array.reshape((array.shape[0], -1))
    output = np.full_like(flat, np.nan, dtype=float)
    for month in sorted(set(times.month)):
        fit = np.where(
            (times.month == month)
            & (times.year >= baseline[0])
            & (times.year <= baseline[1])
        )[0]
        apply = np.where(times.month == month)[0]
        years = times.year.to_numpy(dtype=float)[fit]
        center = float(years.mean())
        x = years - center
        selected = flat[fit]
        valid = np.isfinite(selected)
        count = valid.sum(axis=0)
        mean = np.nansum(selected, axis=0) / np.where(count > 0, count, np.nan)
        denominator = np.nansum(valid * x[:, None] ** 2, axis=0)
        slope = np.nansum(x[:, None] * (selected - mean), axis=0) / np.where(
            denominator > 0, denominator, np.nan
        )
        apply_x = times.year.to_numpy(dtype=float)[apply] - center
        output[apply] = flat[apply] - (mean[None, :] + apply_x[:, None] * slope[None, :])
    return output.reshape(array.shape)


def integrate_zj(values_pw: np.ndarray, times: pd.DatetimeIndex) -> float:
    seconds = times.days_in_month.to_numpy(dtype=float) * 86400.0
    return float(np.nansum(np.asarray(values_pw, dtype=float) * seconds) / 1.0e6)


def event_indices(times: pd.DatetimeIndex, event_year: int) -> np.ndarray:
    indices = np.where(
        (times.year == event_year + 1) & np.isin(times.month, MONTHS)
    )[0]
    if len(indices) != len(MONTHS):
        raise ValueError(f"Incomplete Jan--May(+1) for {event_year}: {len(indices)} months")
    return indices


def load_boundary_fields() -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return time, depth, longitude, 4.75N temperature, and 5N tau_x."""
    with xr.open_dataset(TEMP_NC, engine="h5netcdf") as temp, xr.open_dataset(
        PROCESS_NC, engine="h5netcdf"
    ) as process:
        times = pd.DatetimeIndex(temp.time.values)
        if not np.array_equal(temp.time.values, process.time.values):
            raise ValueError("Temperature and process time axes differ")
        depth = temp.depth.values.astype(float)
        latitude = temp.lat.values.astype(float)
        longitude = temp.lon.values.astype(float)
        u_latitude = process.u_lat.values.astype(float)
        u_longitude = process.u_lon.values.astype(float)

        east_mask = (longitude >= ohc.EAST_LON[0]) & (longitude <= ohc.EAST_LON[1])
        east_longitude = longitude[east_mask]
        north_temp_index = int(np.argmax(latitude))
        north_face_index = int(np.argmin(np.abs(u_latitude - 5.0)))
        if not np.isclose(latitude[north_temp_index], 4.75):
            raise ValueError("Expected northern tracer row at 4.75N")
        if not np.isclose(u_latitude[north_face_index], 5.0):
            raise ValueError("Expected velocity/stress face at 5N")

        longitude_faces = np.flatnonzero(
            (u_longitude >= ohc.EAST_LON[0]) & (u_longitude <= ohc.EAST_LON[1])
        )
        first_face, last_face = int(longitude_faces[0]), int(longitude_faces[-1])
        if last_face - first_face != len(east_longitude):
            raise ValueError("Unexpected SODA3 longitude staggering")

        boundary_temperature = temp.temp.isel(lat=north_temp_index).values[:, :, east_mask]
        raw_tau = process.taux.isel(u_lat=north_face_index).values
        boundary_tau = 0.5 * (
            raw_tau[:, first_face:last_face] + raw_tau[:, first_face + 1 : last_face + 1]
        )
    return times, depth, east_longitude, boundary_temperature.astype(float), boundary_tau.astype(float)


def ekman_series(
    temperature: np.ndarray,
    tau: np.ndarray,
    depth: np.ndarray,
    longitude: np.ndarray,
    reference: float,
) -> np.ndarray:
    result = np.full(temperature.shape[0], np.nan, dtype=float)
    for index in range(temperature.shape[0]):
        result[index] = ohc.ekman_heat_transport(
            temperature[index], tau[index], depth, longitude, reference, 5.0
        )[0]
    return result


def build_counterfactuals() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    times, depth, longitude, temperature, tau = load_boundary_fields()
    monthly_ohc = pd.read_csv(MONTHLY_OHC_CSV, parse_dates=["time"])
    if not np.array_equal(pd.DatetimeIndex(monthly_ohc.time).values, times.values):
        raise ValueError("OHC checkpoint time axis does not match raw SODA3 fields")
    phases = pd.read_csv(PHASE_OHC_CSV)
    phases = phases.loc[
        phases.baseline.eq("1980-2014")
        & phases.phase.eq("decay_Jan1_May1")
        & phases.event_year.isin(EVENTS)
    ].set_index("event_year")

    tau_anomaly = same_month_detrended_array(tau, times, BASELINE)
    tau_baseline = tau - tau_anomaly
    raw_actual: dict[float, np.ndarray] = {}
    anomaly_actual: dict[float, np.ndarray] = {}
    q_baseline: dict[float, np.ndarray] = {}
    for reference in REFERENCES:
        tag = f"tref{int(reference):02d}"
        raw_actual[reference] = ekman_series(
            temperature, tau, depth, longitude, reference
        )
        anomaly_actual[reference] = monthly_ohc[
            f"qekman_5n_north_{tag}_pw_anom_b1980_2014"
        ].to_numpy(dtype=float)
        checkpoint_raw = monthly_ohc[f"qekman_5n_north_{tag}_raw_pw"].to_numpy(dtype=float)
        if not np.allclose(raw_actual[reference], checkpoint_raw, rtol=0.0, atol=5.0e-8):
            raise ValueError(f"Raw Ekman checkpoint mismatch for Tref={reference:g} C")
        q_baseline[reference] = raw_actual[reference] - anomaly_actual[reference]

    monthly_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for target in EVENTS:
        target_index = event_indices(times, target)
        target_times = times[target_index]
        for reference in REFERENCES:
            tag = f"tref{int(reference):02d}"
            observed_total = float(phases.loc[target, f"qvt_5n_north_{tag}_zj"])
            observed_ekman = float(phases.loc[target, f"qekman_5n_north_{tag}_zj"])
            held_nonekman = observed_total - observed_ekman
            scenarios: list[tuple[str, int | None]] = [("removed", None)] + [
                (str(donor), donor) for donor in EVENTS
            ]
            for donor_label, donor in scenarios:
                if donor is None:
                    scenario_tau = tau_baseline[target_index]
                else:
                    donor_index = event_indices(times, donor)
                    scenario_tau = tau_baseline[target_index] + tau_anomaly[donor_index]
                scenario_raw = ekman_series(
                    temperature[target_index],
                    scenario_tau,
                    depth,
                    longitude,
                    reference,
                )
                scenario_anomaly = scenario_raw - q_baseline[reference][target_index]
                scenario_ekman = integrate_zj(scenario_anomaly, target_times)
                reconstructed_total = held_nonekman + scenario_ekman
                summary_rows.append(
                    {
                        "target_ocean_event": target,
                        "donor_wind_anomaly": donor_label,
                        "reference_temperature_c": reference,
                        "observed_total_zj": observed_total,
                        "observed_ekman_zj": observed_ekman,
                        "held_nonekman_zj": held_nonekman,
                        "scenario_ekman_zj": scenario_ekman,
                        "reconstructed_total_zj": reconstructed_total,
                        "change_from_control_zj": reconstructed_total - observed_total,
                        "offline_diagnostic": True,
                    }
                )
                for local, time_index in enumerate(target_index):
                    monthly_rows.append(
                        {
                            "time": times[time_index],
                            "target_ocean_event": target,
                            "donor_wind_anomaly": donor_label,
                            "reference_temperature_c": reference,
                            "target_temperature_fixed": True,
                            "target_nonekman_fixed": True,
                            "scenario_ekman_raw_pw": scenario_raw[local],
                            "target_ekman_baseline_pw": q_baseline[reference][time_index],
                            "scenario_ekman_anomaly_pw": scenario_anomaly[local],
                        }
                    )

    summary = pd.DataFrame(summary_rows)
    monthly = pd.DataFrame(monthly_rows)
    matrix = (
        summary.loc[summary.donor_wind_anomaly.isin([str(year) for year in EVENTS])]
        .pivot(
            index=["reference_temperature_c", "target_ocean_event"],
            columns="donor_wind_anomaly",
            values="reconstructed_total_zj",
        )
        .reset_index()
    )

    control_errors: dict[str, float] = {}
    for reference in REFERENCES:
        for event in EVENTS:
            row = summary.loc[
                summary.reference_temperature_c.eq(reference)
                & summary.target_ocean_event.eq(event)
                & summary.donor_wind_anomaly.eq(str(event))
            ].iloc[0]
            control_errors[f"tref{int(reference):02d}_{event}"] = float(
                row.reconstructed_total_zj - row.observed_total_zj
            )
    max_control_error = max(abs(value) for value in control_errors.values())
    if max_control_error > 1.0e-7:
        raise ValueError(f"Wind-swap control does not close: {max_control_error:g} ZJ")

    direction_checks = {}
    for reference in REFERENCES:
        current = summary.loc[summary.reference_temperature_c.eq(reference)].set_index(
            ["target_ocean_event", "donor_wind_anomaly"]
        )
        direction_checks[f"tref{int(reference):02d}_2015_weakened_by_2023_wind"] = bool(
            current.loc[(2015, "2023"), "reconstructed_total_zj"]
            < current.loc[(2015, "2015"), "reconstructed_total_zj"]
        )
        direction_checks[f"tref{int(reference):02d}_2023_strengthened_by_2015_wind"] = bool(
            current.loc[(2023, "2015"), "reconstructed_total_zj"]
            > current.loc[(2023, "2023"), "reconstructed_total_zj"]
        )
    diagnostics: dict[str, object] = {
        "definition": "rho Cp integral[v(T-Tref)]dA; fixed target temperature and non-Ekman transport; donor 5N tau_x anomaly only",
        "phase": "Jan(+1)-May(+1)",
        "baseline": "calendar-month climatology and linear trend, 1980-2014",
        "actual_seconds_weighting": True,
        "max_abs_control_closure_error_zj": max_control_error,
        "control_errors_zj": control_errors,
        "direction_checks": direction_checks,
        "all_direction_checks_pass": bool(all(direction_checks.values())),
    }
    return monthly, summary, matrix, diagnostics


def make_figure(summary: pd.DataFrame) -> None:
    primary = summary.loc[
        summary.reference_temperature_c.eq(0.0)
        & summary.donor_wind_anomaly.isin([str(year) for year in EVENTS])
    ]
    matrix = (
        primary.pivot(
            index="target_ocean_event",
            columns="donor_wind_anomaly",
            values="reconstructed_total_zj",
        )
        .reindex(index=EVENTS, columns=[str(year) for year in EVENTS])
    )
    values = matrix.to_numpy(dtype=float)
    limit = max(1.0, float(np.nanmax(np.abs(values))))

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.4), constrained_layout=True)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    image = axes[0].imshow(values, cmap="RdBu_r", norm=norm, aspect="auto")
    axes[0].set_xticks(range(len(EVENTS)), [f"{year} wind" for year in EVENTS])
    axes[0].set_yticks(range(len(EVENTS)), [f"{year} ocean" for year in EVENTS])
    axes[0].set_title("Reconstructed total 5°N heat transport")
    for i in range(len(EVENTS)):
        for j in range(len(EVENTS)):
            color = "white" if abs(values[i, j]) > 0.55 * limit else "black"
            axes[0].text(j, i, f"{values[i, j]:+.2f}", ha="center", va="center", color=color, fontweight="bold")
    fig.colorbar(image, ax=axes[0], label="Jan–May(+1) heat transport anomaly (ZJ)")

    scenario_order = [(2015, "2015"), (2015, "2023"), (2023, "2023"), (2023, "2015")]
    labels = ["2015\nself wind", "2015\n2023 wind", "2023\nself wind", "2023\n2015 wind"]
    x = np.arange(len(labels))
    colors = ["#D47A1F", "#86A6C2", "#2B6F9F", "#E6A85C"]
    for reference, marker, line in [(0.0, "o", "-"), (10.0, "s", "--"), (20.0, "^", ":")]:
        current = summary.loc[summary.reference_temperature_c.eq(reference)].set_index(
            ["target_ocean_event", "donor_wind_anomaly"]
        )
        y = [current.loc[item, "reconstructed_total_zj"] for item in scenario_order]
        axes[1].plot(x, y, marker=marker, linestyle=line, linewidth=1.7, markersize=6, label=f"Tref={reference:g}°C")
    axes[1].axhline(0.0, color="0.35", linewidth=0.8)
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Reconstructed total 5°N heat transport (ZJ)")
    axes[1].set_title("Reference-temperature sensitivity")
    axes[1].legend(frameon=False)
    axes[1].grid(axis="y", color="0.88", linewidth=0.7)
    fig.suptitle("OHC-only offline wind swap: fixed ocean state, replaced 5°N wind anomaly", fontweight="bold")
    fig.savefig(FIGURE_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_h20_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    old = pd.read_csv(OLD_H20_SWAP_CSV)
    old["donor_wind"] = old.donor_wind.astype(str)
    old = old.loc[
        old.target_ocean_event.isin(EVENTS)
        & old.donor_wind.isin([str(year) for year in EVENTS])
    ].set_index(["target_ocean_event", "donor_wind"])
    current = summary.loc[
        summary.donor_wind_anomaly.isin([str(year) for year in EVENTS])
    ].set_index(["target_ocean_event", "donor_wind_anomaly", "reference_temperature_c"])
    rows: list[dict[str, float | int]] = []
    for target in EVENTS:
        old_self = float(old.loc[(target, str(target)), "reconstructed_total_zj"])
        for donor in EVENTS:
            row: dict[str, float | int] = {
                "target_ocean_event": target,
                "donor_wind": donor,
                "h20_reconstructed_total_zj": float(
                    old.loc[(target, str(donor)), "reconstructed_total_zj"]
                ),
                "h20_change_from_self_zj": float(
                    old.loc[(target, str(donor)), "reconstructed_total_zj"] - old_self
                ),
            }
            values = []
            for reference in REFERENCES:
                value = float(current.loc[(target, str(donor), reference), "reconstructed_total_zj"])
                self_value = float(current.loc[(target, str(target), reference), "reconstructed_total_zj"])
                row[f"ohc_tref{int(reference):02d}_reconstructed_total_zj"] = value
                row[f"ohc_tref{int(reference):02d}_change_from_self_zj"] = value - self_value
                values.append(value)
            row["ohc_reconstructed_min_zj"] = min(values)
            row["ohc_reconstructed_max_zj"] = max(values)
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    monthly, summary, matrix, diagnostics = build_counterfactuals()
    comparison = build_h20_comparison(summary)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.9g")
    matrix.to_csv(MATRIX_CSV, index=False, float_format="%.9g")
    comparison.to_csv(COMPARISON_CSV, index=False, float_format="%.9g")
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    make_figure(summary)
    print(summary.to_string(index=False))
    print(f"\nWrote {SUMMARY_CSV}")
    print(f"Wrote {FIGURE_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
