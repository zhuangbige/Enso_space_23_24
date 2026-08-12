#!/usr/bin/env python3
"""Track 140°W positive anomalous heat forward with SODA3 five-day flow.

This implements a Jiang-style Lagrangian destination diagnostic while
retaining the established fixed-box heat budget as an independent Eulerian
closure.  It does not use H20 or a fixed temperature threshold.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import RegularGridInterpolator


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib-cache"))
DERIVED_DIR = ROOT / "data/derived/research_2026"
INTERIM_DIR = ROOT / "data/interim/research_2026/soda3_jiang_forward_heat_fate"
OUTPUT_DIR = ROOT / "outputs/research_2026/soda3_jiang_forward_heat_fate"
ENDPOINT_CSV = DERIVED_DIR / "soda3_jiang_forward_heat_fate_endpoints.csv"
TRAJECTORY_CSV = DERIVED_DIR / "soda3_jiang_forward_heat_fate_trajectories.csv"
SUMMARY_CSV = DERIVED_DIR / "soda3_jiang_forward_heat_fate_summary.csv"
AUDIT_JSON = DERIVED_DIR / "soda3_jiang_forward_heat_fate_audit.json"
RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS_M = 6_371_000.0
SECONDS_PER_DAY = 86_400.0
GATE_LONGITUDE = 220.0
WEST_EXIT_LONGITUDE = 220.0
EAST_EXIT_LONGITUDE = 280.0
SOUTH_EXIT_LATITUDE = -5.0
NORTH_EXIT_LATITUDE = 5.0
MINIMUM_DEPTH_M = 5.0
MAXIMUM_DEPTH_M = 300.0
MINIMUM_ANOMALY_C = 0.05
DESTINATIONS = (
    "returned_west_140w",
    "north_of_5n",
    "south_of_5s",
    "below_300m",
    "east_of_80w",
    "retained_east",
    "unresolved_land_or_grid",
    "invalid_velocity",
)


@dataclass(frozen=True)
class TemperatureExpectedField:
    depth: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    temperature_c: np.ndarray
    month: int
    baseline_start_year: int
    baseline_end_year: int


def discover_source_root() -> Path:
    for candidate in (ROOT, *ROOT.parents):
        if (
            (candidate / "scripts/pilot_soda3_lagrangian_connectivity.py").exists()
            and (
                candidate
                / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
            ).exists()
        ):
            return candidate
    raise FileNotFoundError("Could not locate the SODA3 pilot and temperature baseline")


def _source_modules() -> tuple[object, object]:
    source_root = discover_source_root()
    script_path = str(source_root / "scripts")
    if script_path not in sys.path:
        sys.path.insert(0, script_path)
    pilot = importlib.import_module("pilot_soda3_lagrangian_connectivity")
    fetch = importlib.import_module("fetch_soda3_5day_event_transport")
    pilot.CACHE_DIR = INTERIM_DIR / "cache_218e_280e"
    pilot.TEMPERATURE_BASELINE_NC = (
        source_root
        / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
    )
    pilot.DOMAIN_LON = (218.0, 280.0)
    pilot.DOMAIN_LAT = (-5.0, 5.0)
    pilot.DOMAIN_DEPTH = (MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M)
    return pilot, fetch


def record_variable_offset(
    *,
    variable_begin: int,
    record_size: int,
    time_index: int,
    spatial_element_index: int,
    itemsize: int,
) -> int:
    return int(
        variable_begin
        + time_index * record_size
        + spatial_element_index * itemsize
    )


def is_release_time(timestamp: pd.Timestamp, event: int) -> bool:
    time = pd.Timestamp(timestamp)
    return time.year == int(event) and 1 <= time.month <= 6


def filter_tracking_calendar(
    files: list[tuple[pd.Timestamp, str]],
    event: int,
) -> list[tuple[pd.Timestamp, str]]:
    start = pd.Timestamp(int(event), 1, 1)
    end = pd.Timestamp(int(event) + 1, 6, 1)
    selected = [
        (pd.Timestamp(timestamp), url)
        for timestamp, url in files
        if start <= pd.Timestamp(timestamp) < end
    ]
    selected.sort(key=lambda item: item[0])
    if not selected:
        raise ValueError(f"No tracking files for event {event}")
    return selected


def subsample_tracking_files(
    files: list[tuple[pd.Timestamp, str]],
    *,
    event: int,
    stride: int,
) -> list[tuple[pd.Timestamp, str]]:
    if stride < 1:
        raise ValueError("stride must be at least one")
    eligible = filter_tracking_calendar(files, event)
    selected = eligible[::stride]
    release = [item for item in eligible if is_release_time(item[0], event)]
    if not release:
        raise ValueError(f"No January–June release files for event {event}")
    selected.extend([release[-1], eligible[-1]])
    return sorted(dict(selected).items(), key=lambda item: item[0])


class SnapshotLike(Protocol):
    timestamp: pd.Timestamp
    z_t: np.ndarray
    lat_t: np.ndarray
    lon_t: np.ndarray

    def interpolate(self, name: str, positions: np.ndarray) -> np.ndarray: ...


def _cell_bounds(values: np.ndarray, lower: float, upper: float) -> np.ndarray:
    coordinates = np.asarray(values, dtype=float)
    if coordinates.ndim != 1 or len(coordinates) < 2:
        raise ValueError("At least two increasing coordinates are required")
    if not np.all(np.diff(coordinates) > 0.0):
        raise ValueError("Coordinates must be strictly increasing")
    bounds = np.empty(len(coordinates) + 1, dtype=float)
    bounds[1:-1] = 0.5 * (coordinates[:-1] + coordinates[1:])
    bounds[0] = max(lower, coordinates[0] - 0.5 * (coordinates[1] - coordinates[0]))
    bounds[-1] = min(
        upper,
        coordinates[-1] + 0.5 * (coordinates[-1] - coordinates[-2]),
    )
    if not np.all(np.diff(bounds) > 0.0):
        raise ValueError("Coordinate bounds have nonpositive cells")
    return bounds


def centered_release_intervals_seconds(
    times: pd.DatetimeIndex,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> np.ndarray:
    """Return midpoint sampling intervals clipped to a half-open window."""

    index = pd.DatetimeIndex(times)
    if len(index) == 0 or not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError("Release times must be nonempty, increasing, and unique")
    start = pd.Timestamp(window_start)
    end = pd.Timestamp(window_end)
    if end <= start or index[0] < start or index[-1] >= end:
        raise ValueError("Release times must lie inside the requested window")
    boundaries = [start]
    boundaries.extend(index[:-1] + (index[1:] - index[:-1]) / 2)
    boundaries.append(end)
    return np.asarray(
        [
            float((boundaries[index_ + 1] - boundaries[index_]).total_seconds())
            for index_ in range(len(index))
        ],
        dtype=float,
    )


def seed_gate_particles(
    snapshot: SnapshotLike,
    expected_field: object,
    interval_seconds: float,
    event: int,
) -> pd.DataFrame:
    """Seed eastward positive-T′ cells at 140°W with heat-flux weights."""

    if interval_seconds <= 0.0:
        raise ValueError("interval_seconds must be positive")
    depth = np.asarray(snapshot.z_t, dtype=float)
    latitude = np.asarray(snapshot.lat_t, dtype=float)
    depth = depth[(depth >= MINIMUM_DEPTH_M) & (depth <= MAXIMUM_DEPTH_M)]
    latitude = latitude[
        (latitude >= SOUTH_EXIT_LATITUDE) & (latitude <= NORTH_EXIT_LATITUDE)
    ]
    lon, lat, z = np.meshgrid(
        np.asarray([GATE_LONGITUDE]),
        latitude,
        depth,
        indexing="xy",
    )
    positions = np.column_stack([lon.ravel(), lat.ravel(), z.ravel()])
    gate_u = np.asarray(snapshot.interpolate("u", positions), dtype=float)
    temperature = np.asarray(snapshot.interpolate("temp", positions), dtype=float)
    expected_interpolator = RegularGridInterpolator(
        (
            np.asarray(expected_field.depth, dtype=float),
            np.asarray(expected_field.lat, dtype=float),
            np.asarray(expected_field.lon, dtype=float),
        ),
        np.asarray(expected_field.temperature_c, dtype=float),
        bounds_error=False,
        fill_value=np.nan,
    )
    expected_temperature = expected_interpolator(
        np.column_stack([positions[:, 2], positions[:, 1], positions[:, 0]])
    )
    anomaly = temperature - expected_temperature

    depth_bounds = _cell_bounds(depth, 0.0, MAXIMUM_DEPTH_M)
    depth_thickness = np.diff(depth_bounds)
    latitude_bounds = _cell_bounds(latitude, -90.0, 90.0)
    latitude_width_m = EARTH_RADIUS_M * np.deg2rad(np.diff(latitude_bounds))
    area = np.outer(latitude_width_m, depth_thickness).ravel()
    valid = (
        np.isfinite(gate_u)
        & np.isfinite(temperature)
        & np.isfinite(expected_temperature)
        & (gate_u > 0.0)
        & (anomaly > MINIMUM_ANOMALY_C)
        & np.isfinite(area)
        & (area > 0.0)
    )
    positions = positions[valid]
    gate_u = gate_u[valid]
    temperature = temperature[valid]
    expected_temperature = expected_temperature[valid]
    anomaly = anomaly[valid]
    area = area[valid]
    weights = (
        RHO0
        * CP0
        * gate_u
        * anomaly
        * area
        * float(interval_seconds)
        / 1.0e21
    )
    return pd.DataFrame(
        {
            "event": int(event),
            "release_date": pd.Timestamp(snapshot.timestamp),
            "release_lon": positions[:, 0],
            "release_lat": positions[:, 1],
            "release_depth_m": positions[:, 2],
            "gate_u_ms": gate_u,
            "release_temp_c": temperature,
            "expected_temp_c": expected_temperature,
            "release_temp_anomaly_c": anomaly,
            "section_area_m2": area,
            "interval_seconds": float(interval_seconds),
            "heat_weight_zj": weights,
        }
    )


def _position_rates(
    snapshot_earlier: SnapshotLike,
    snapshot_later: SnapshotLike,
    positions: np.ndarray,
    alpha: float,
    *,
    w_to_depth_sign: float,
) -> np.ndarray:
    fraction = float(np.clip(alpha, 0.0, 1.0))
    values: dict[str, np.ndarray] = {}
    for name in ("u", "v", "w"):
        earlier = np.asarray(snapshot_earlier.interpolate(name, positions), dtype=float)
        later = np.asarray(snapshot_later.interpolate(name, positions), dtype=float)
        values[name] = (1.0 - fraction) * earlier + fraction * later
    latitude_radians = np.deg2rad(positions[:, 1])
    rates = np.empty_like(positions, dtype=float)
    rates[:, 0] = (
        values["u"]
        / (EARTH_RADIUS_M * np.cos(latitude_radians))
        * 180.0
        / np.pi
    )
    rates[:, 1] = values["v"] / EARTH_RADIUS_M * 180.0 / np.pi
    rates[:, 2] = w_to_depth_sign * values["w"]
    return rates


def _mark_exits(
    state: pd.DataFrame,
    indices: np.ndarray,
    *,
    positions: np.ndarray | None = None,
    maximum_depth_m: float = MAXIMUM_DEPTH_M,
    north_limit: float = NORTH_EXIT_LATITUDE,
    south_limit: float = SOUTH_EXIT_LATITUDE,
    east_limit: float = EAST_EXIT_LONGITUDE,
) -> None:
    if len(indices) == 0:
        return
    values = (
        state.loc[indices, ["lon", "lat", "depth_m"]].to_numpy(float)
        if positions is None
        else np.asarray(positions, dtype=float)
    )
    lon, lat, depth = values[:, 0], values[:, 1], values[:, 2]
    destinations = np.full(len(indices), "active", dtype=object)
    destinations[lon < WEST_EXIT_LONGITUDE] = "returned_west_140w"
    destinations[(destinations == "active") & (lat > north_limit)] = "north_of_5n"
    destinations[(destinations == "active") & (lat < south_limit)] = "south_of_5s"
    destinations[(destinations == "active") & (depth > maximum_depth_m)] = "below_300m"
    destinations[(destinations == "active") & (lon > east_limit)] = "east_of_80w"
    exited = destinations != "active"
    if np.any(exited):
        exited_indices = indices[exited]
        state.loc[exited_indices, "active"] = False
        state.loc[exited_indices, "destination"] = destinations[exited]


def integrate_interval_forward(
    state: pd.DataFrame,
    earlier: SnapshotLike,
    later: SnapshotLike,
    *,
    step_hours: float,
    w_to_depth_sign: float,
) -> pd.DataFrame:
    """Advance active particles with time-interpolated midpoint RK2."""

    total_seconds = float((later.timestamp - earlier.timestamp).total_seconds())
    if total_seconds <= 0.0 or step_hours <= 0.0:
        raise ValueError("Snapshots and integration step must move forward")
    result = state.copy()
    count = max(1, int(math.ceil(total_seconds / (step_hours * 3600.0))))
    dt = total_seconds / count
    current_seconds = 0.0
    maximum_depth_m = min(
        MAXIMUM_DEPTH_M,
        float(np.max(earlier.z_t)),
        float(np.max(later.z_t)),
    )
    minimum_depth_m = max(
        MINIMUM_DEPTH_M,
        float(np.min(earlier.z_t)),
        float(np.min(later.z_t)),
    )
    north_limit = min(
        NORTH_EXIT_LATITUDE,
        float(np.max(earlier.lat_t)),
        float(np.max(later.lat_t)),
    )
    south_limit = max(
        SOUTH_EXIT_LATITUDE,
        float(np.min(earlier.lat_t)),
        float(np.min(later.lat_t)),
    )
    east_limit = min(
        EAST_EXIT_LONGITUDE,
        float(np.max(earlier.lon_t)),
        float(np.max(later.lon_t)),
    )
    for _ in range(count):
        indices = result.index[result["active"].astype(bool)].to_numpy()
        if len(indices) == 0:
            break
        positions = result.loc[indices, ["lon", "lat", "depth_m"]].to_numpy(float)
        first = _position_rates(
            earlier,
            later,
            positions,
            current_seconds / total_seconds,
            w_to_depth_sign=w_to_depth_sign,
        )
        valid_first = np.isfinite(first).all(axis=1)
        if not np.all(valid_first):
            failed = indices[~valid_first]
            result.loc[failed, "active"] = False
            result.loc[failed, "destination"] = "unresolved_land_or_grid"
        indices = indices[valid_first]
        if len(indices) == 0:
            current_seconds += dt
            continue
        positions = positions[valid_first]
        midpoint = positions + 0.5 * dt * first[valid_first]
        midpoint_shallow = midpoint[:, 2] < minimum_depth_m
        if np.any(midpoint_shallow):
            shallow_indices = indices[midpoint_shallow]
            midpoint[midpoint_shallow, 2] = minimum_depth_m
            result.loc[shallow_indices, "surface_clip_steps"] = (
                result.loc[shallow_indices, "surface_clip_steps"].to_numpy(int) + 1
            )
        _mark_exits(
            result,
            indices,
            positions=midpoint,
            maximum_depth_m=maximum_depth_m,
            north_limit=north_limit,
            south_limit=south_limit,
            east_limit=east_limit,
        )
        midpoint_active = result.loc[indices, "active"].to_numpy(bool)
        indices = indices[midpoint_active]
        midpoint = midpoint[midpoint_active]
        positions = positions[midpoint_active]
        if len(indices) == 0:
            current_seconds += dt
            continue
        second = _position_rates(
            earlier,
            later,
            midpoint,
            (current_seconds + 0.5 * dt) / total_seconds,
            w_to_depth_sign=w_to_depth_sign,
        )
        valid_second = np.isfinite(second).all(axis=1)
        if not np.all(valid_second):
            failed = indices[~valid_second]
            result.loc[failed, "active"] = False
            result.loc[failed, "destination"] = "unresolved_land_or_grid"
        indices = indices[valid_second]
        if len(indices) == 0:
            current_seconds += dt
            continue
        candidate = positions[valid_second] + dt * second[valid_second]
        shallow = candidate[:, 2] < minimum_depth_m
        if np.any(shallow):
            shallow_indices = indices[shallow]
            candidate[shallow, 2] = minimum_depth_m
            result.loc[shallow_indices, "surface_clip_steps"] = (
                result.loc[shallow_indices, "surface_clip_steps"].to_numpy(int) + 1
            )
        result.loc[indices, ["lon", "lat", "depth_m"]] = candidate
        _mark_exits(
            result,
            indices,
            maximum_depth_m=maximum_depth_m,
            north_limit=north_limit,
            south_limit=south_limit,
            east_limit=east_limit,
        )
        current_seconds += dt
    return result


def summarize_endpoints(endpoints: pd.DataFrame) -> dict[str, float | int]:
    """Summarize destinations without dropping unresolved heat weight."""

    if endpoints.empty or endpoints["event"].nunique() != 1:
        raise ValueError("Endpoint summary requires one nonempty event")
    weights = endpoints["heat_weight_zj"].to_numpy(float)
    total = float(np.nansum(weights))
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError("Initial positive anomaly heat must be finite and positive")
    row: dict[str, float | int] = {
        "event": int(endpoints["event"].iloc[0]),
        "particle_count": int(len(endpoints)),
        "gate_positive_anomaly_heat_zj": total,
        "surface_exposure_heat_fraction": float(
            np.nansum(weights[endpoints["surface_clip_steps"].to_numpy(int) > 0]) / total
        ),
    }
    for destination in DESTINATIONS:
        selected = endpoints["destination"].eq(destination).to_numpy()
        row[f"heat_fraction_{destination}"] = float(np.nansum(weights[selected]) / total)
    unresolved = float(row["heat_fraction_unresolved_land_or_grid"])
    invalid = float(row["heat_fraction_invalid_velocity"])
    resolved = 1.0 - unresolved - invalid
    row["resolved_heat_fraction"] = resolved
    for destination in DESTINATIONS:
        if destination in {"unresolved_land_or_grid", "invalid_velocity"}:
            continue
        row[f"resolved_fraction_{destination}"] = (
            float(row[f"heat_fraction_{destination}"]) / resolved
            if resolved > 0.0
            else float("nan")
        )
    retained = endpoints["destination"].eq("retained_east").to_numpy()
    endpoint_anomaly = endpoints["endpoint_temp_anomaly_c"].to_numpy(float)
    release_anomaly = endpoints["release_temp_anomaly_c"].to_numpy(float)
    finite = (
        retained
        & np.isfinite(endpoint_anomaly)
        & np.isfinite(release_anomaly)
        & (release_anomaly > 0.0)
    )
    finite_weight = float(np.nansum(weights[finite]))
    row["retained_endpoint_anomaly_coverage_fraction"] = finite_weight / total
    if finite_weight > 0.0:
        row["retained_weighted_endpoint_temp_anomaly_c"] = float(
            np.average(endpoint_anomaly[finite], weights=weights[finite])
        )
        row["retained_weighted_anomaly_ratio"] = float(
            np.average(endpoint_anomaly[finite] / release_anomaly[finite], weights=weights[finite])
        )
    else:
        row["retained_weighted_endpoint_temp_anomaly_c"] = float("nan")
        row["retained_weighted_anomaly_ratio"] = float("nan")
    return row


def _expected_at_positions(expected_field: object, positions: np.ndarray) -> np.ndarray:
    interpolator = RegularGridInterpolator(
        (
            np.asarray(expected_field.depth, dtype=float),
            np.asarray(expected_field.lat, dtype=float),
            np.asarray(expected_field.lon, dtype=float),
        ),
        np.asarray(expected_field.temperature_c, dtype=float),
        bounds_error=False,
        fill_value=np.nan,
    )
    return np.asarray(
        interpolator(np.column_stack([positions[:, 2], positions[:, 1], positions[:, 0]])),
        dtype=float,
    )


def track_event_cohorts(
    *,
    event: int,
    snapshots: list[SnapshotLike],
    release_expected_fields: dict[int, object],
    final_expected_field: object,
    step_hours: float,
    w_to_depth_sign: float = -1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Release January–June gate cohorts and follow them to the final snapshot."""

    if len(snapshots) < 2:
        raise ValueError("At least two snapshots are required")
    times = pd.DatetimeIndex([snapshot.timestamp for snapshot in snapshots])
    if not times.is_monotonic_increasing or times.has_duplicates:
        raise ValueError("Snapshots must be increasing and unique")
    release_indices = [
        index for index, timestamp in enumerate(times) if is_release_time(timestamp, event)
    ]
    if not release_indices:
        raise ValueError(f"No release snapshots for event {event}")
    release_times = times[release_indices]
    release_intervals = centered_release_intervals_seconds(
        release_times,
        pd.Timestamp(event, 1, 1),
        pd.Timestamp(event, 7, 1),
    )
    endpoint_frames: list[pd.DataFrame] = []
    trajectory_frames: list[pd.DataFrame] = []
    next_particle_id = 0

    for release_index, interval_seconds in zip(
        release_indices,
        release_intervals,
        strict=True,
    ):
        release_snapshot = snapshots[release_index]
        expected_field = release_expected_fields.get(release_snapshot.timestamp.month)
        if expected_field is None:
            raise KeyError(f"Missing expected temperature for month {release_snapshot.timestamp.month}")
        seeds = seed_gate_particles(
            release_snapshot,
            expected_field,
            interval_seconds=float(interval_seconds),
            event=event,
        )
        if seeds.empty:
            continue
        seeds = seeds.copy()
        seeds["particle_id"] = np.arange(
            next_particle_id,
            next_particle_id + len(seeds),
            dtype=int,
        )
        next_particle_id += len(seeds)
        state = pd.DataFrame(
            {
                "lon": seeds["release_lon"].to_numpy(float) + 1.0e-6,
                "lat": seeds["release_lat"].to_numpy(float),
                "depth_m": seeds["release_depth_m"].to_numpy(float),
                "active": True,
                "destination": "active",
                "surface_clip_steps": 0,
                "terminal_date": pd.NaT,
            },
            index=seeds["particle_id"].to_numpy(int),
        )

        def record(timestamp: pd.Timestamp) -> None:
            trajectory_frames.append(
                pd.DataFrame(
                    {
                        "event": event,
                        "particle_id": state.index.to_numpy(int),
                        "release_date": release_snapshot.timestamp,
                        "date": pd.Timestamp(timestamp),
                        "lon": state["lon"].to_numpy(float),
                        "lat": state["lat"].to_numpy(float),
                        "depth_m": state["depth_m"].to_numpy(float),
                        "active": state["active"].to_numpy(bool),
                        "destination": state["destination"].to_numpy(object),
                    }
                )
            )

        record(release_snapshot.timestamp)
        for interval_index in range(release_index, len(snapshots) - 1):
            before_active = state["active"].to_numpy(bool)
            state = integrate_interval_forward(
                state,
                snapshots[interval_index],
                snapshots[interval_index + 1],
                step_hours=step_hours,
                w_to_depth_sign=w_to_depth_sign,
            )
            after_active = state["active"].to_numpy(bool)
            newly_terminal = before_active & ~after_active
            if np.any(newly_terminal):
                state.loc[state.index[newly_terminal], "terminal_date"] = snapshots[
                    interval_index + 1
                ].timestamp
            record(snapshots[interval_index + 1].timestamp)
            if not after_active.any():
                break

        retained = state["active"].to_numpy(bool)
        state.loc[state.index[retained], "destination"] = "retained_east"
        state.loc[state.index[retained], "terminal_date"] = snapshots[-1].timestamp
        endpoint_anomaly = np.full(len(state), np.nan, dtype=float)
        if np.any(retained):
            retained_positions = state.loc[
                state.index[retained], ["lon", "lat", "depth_m"]
            ].to_numpy(float)
            endpoint_temperature = snapshots[-1].interpolate("temp", retained_positions)
            endpoint_expected = _expected_at_positions(final_expected_field, retained_positions)
            endpoint_anomaly[retained] = endpoint_temperature - endpoint_expected
        endpoints = seeds.set_index("particle_id").join(state)
        endpoints["endpoint_temp_anomaly_c"] = endpoint_anomaly
        endpoint_frames.append(endpoints.reset_index())

    if not endpoint_frames:
        raise ValueError(f"No positive anomaly gate particles for event {event}")
    return (
        pd.concat(endpoint_frames, ignore_index=True),
        pd.concat(trajectory_frames, ignore_index=True),
    )


def audit_summary(summary: pd.DataFrame) -> dict[str, object]:
    if summary.empty:
        raise ValueError("Summary is empty")
    fraction_columns = [f"heat_fraction_{destination}" for destination in DESTINATIONS]
    missing = [column for column in fraction_columns if column not in summary]
    if missing:
        raise ValueError(f"Summary misses destination columns: {missing}")
    fraction_sum = summary[fraction_columns].sum(axis=1)
    maximum_error = float(np.max(np.abs(fraction_sum.to_numpy(float) - 1.0)))
    if maximum_error > 1.0e-8:
        raise ValueError(f"Destination heat fractions do not close: {maximum_error}")
    heat = summary["gate_positive_anomaly_heat_zj"].to_numpy(float)
    if not np.isfinite(heat).all() or not (heat > 0.0).all():
        raise ValueError("Integrated gate heat must be finite and positive")
    return {
        "events": [int(value) for value in summary["event"].to_list()],
        "maximum_destination_fraction_sum_error": maximum_error,
        "minimum_gate_positive_anomaly_heat_zj": float(np.min(heat)),
        "missing_summary_values": int(summary.isna().sum().sum()),
    }


def load_temperature_expected_field(
    event: int,
    month: int,
    *,
    longitude_bounds: tuple[float, float],
) -> TemperatureExpectedField:
    """Load a leave-event-out same-month linear SODA temperature expectation."""

    pilot, _ = _source_modules()
    source_root = discover_source_root()
    path = (
        source_root
        / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
    )
    with xr.open_dataset(path, engine="h5netcdf") as dataset:
        subset = (
            dataset["temp"]
            .where(dataset.time.dt.month == int(month), drop=True)
            .sel(
                depth=slice(MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
                lat=slice(-5.0, 5.0),
                lon=slice(longitude_bounds[0], longitude_bounds[1]),
            )
            .load()
        )
    years = np.asarray(subset.time.dt.year.to_numpy(), dtype=int)
    if not np.any(years == event):
        raise ValueError(f"Temperature baseline lacks {event}-{month:02d}")
    keep = years != event
    expected = pilot.linear_expected_temperature(
        subset.to_numpy()[keep],
        years[keep],
        event,
    )
    return TemperatureExpectedField(
        depth=np.asarray(subset.depth.to_numpy(), dtype=float),
        lat=np.asarray(subset.lat.to_numpy(), dtype=float),
        lon=np.asarray(subset.lon.to_numpy(), dtype=float),
        temperature_c=np.asarray(expected, dtype=float),
        month=int(month),
        baseline_start_year=int(years.min()),
        baseline_end_year=int(years.max()),
    )


def list_forward_event_files(event: int, stride: int) -> list[tuple[pd.Timestamp, str]]:
    _, fetch = _source_modules()
    by_year = fetch.list_event_files([int(event), int(event) + 1], end_month=12)
    combined = [*by_year[int(event)], *by_year[int(event) + 1]]
    return subsample_tracking_files(combined, event=int(event), stride=int(stride))


def load_event_snapshots(
    event: int,
    files: list[tuple[pd.Timestamp, str]],
    *,
    force_cache: bool,
) -> list[SnapshotLike]:
    pilot, _ = _source_modules()
    import requests

    session = requests.Session()
    metadata_by_year: dict[int, dict[str, object]] = {}
    snapshots: list[SnapshotLike] = []
    for index, (timestamp, url) in enumerate(files):
        need_temperature = is_release_time(timestamp, event) or index == len(files) - 1
        snapshots.append(
            pilot.get_snapshot(
                int(timestamp.year),
                pd.Timestamp(timestamp),
                url,
                session,
                metadata_by_year.setdefault(int(timestamp.year), {}),
                need_temp=need_temperature,
                force=force_cache,
            )
        )
    return snapshots


def _slice_coordinates(
    values: np.ndarray,
    lower: float,
    upper: float,
) -> slice:
    selected = np.flatnonzero((values >= lower) & (values <= upper))
    if selected.size == 0 or not np.all(np.diff(selected) == 1):
        raise ValueError(f"Cannot select contiguous coordinates {lower}..{upper}")
    return slice(int(selected[0]), int(selected[-1]) + 1)


def _local_monthly_snapshot(year: int, month: int) -> SnapshotLike:
    pilot, _ = _source_modules()
    source_root = discover_source_root()
    process_path = (
        source_root
        / "data/raw/soda3/soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
    )
    temperature_path = (
        source_root
        / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
    )
    timestamp = pd.Timestamp(year, month, 15)
    with xr.open_dataset(process_path, engine="h5netcdf") as process:
        selected = process.sel(time=timestamp)
        tracer = selected.sel(
            depth=slice(MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
            lat=slice(SOUTH_EXIT_LATITUDE, NORTH_EXIT_LATITUDE),
            lon=slice(218.0, EAST_EXIT_LONGITUDE),
        ).load()
        velocity = selected.sel(
            depth=slice(MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
            u_lat=slice(SOUTH_EXIT_LATITUDE, NORTH_EXIT_LATITUDE),
            u_lon=slice(218.0, EAST_EXIT_LONGITUDE),
        ).load()
    with xr.open_dataset(temperature_path, engine="h5netcdf") as dataset:
        temperature = (
            dataset.temp.sel(time=timestamp)
            .sel(
                depth=slice(MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
                lat=slice(SOUTH_EXIT_LATITUDE, NORTH_EXIT_LATITUDE),
                lon=slice(218.0, EAST_EXIT_LONGITUDE),
            )
            .load()
        )
    return pilot.Snapshot(
        timestamp=timestamp,
        z_t=np.asarray(tracer.depth.to_numpy(), dtype=float),
        z_w=np.asarray(tracer.depth.to_numpy(), dtype=float),
        lat_t=np.asarray(tracer.lat.to_numpy(), dtype=float),
        lon_t=np.asarray(tracer.lon.to_numpy(), dtype=float),
        lat_uv=np.asarray(velocity.u_lat.to_numpy(), dtype=float),
        lon_uv=np.asarray(velocity.u_lon.to_numpy(), dtype=float),
        u=np.asarray(velocity.u.to_numpy(), dtype=float),
        v=np.asarray(velocity.v.to_numpy(), dtype=float),
        w=np.asarray(tracer.wt.to_numpy(), dtype=float),
        temp=np.asarray(temperature.to_numpy(), dtype=float),
    )


def _classic_read_time_4d(
    dataset: object,
    name: str,
    time_index: int,
    z_slice: slice,
    y_slice: slice,
    x_slice: slice,
) -> np.ndarray:
    variable = dataset.variables[name]
    _, nz, ny, nx = variable.shape
    z_values = list(range(*z_slice.indices(nz)))
    y_range = range(*y_slice.indices(ny))
    x_range = range(*x_slice.indices(nx))
    record_size = sum(
        item.vsize
        for item in dataset.variables.values()
        if item.dimensions and item.dimensions[0] == dataset.record_dimension_name
    )
    # The scientific subset is only about 1.3 MB per variable.  One
    # contiguous range avoids amplifying server latency with many small reads.
    blocks = [z_values]

    def read_block(block: list[int]) -> tuple[list[int], bytes]:
        first_element = (block[0] * ny + y_range.start) * nx
        stop_element = ((block[-1] * ny + y_range.stop) * nx)
        start = record_variable_offset(
            variable_begin=variable.begin,
            record_size=record_size,
            time_index=time_index,
            spatial_element_index=first_element,
            itemsize=variable.itemsize,
        )
        end = record_variable_offset(
            variable_begin=variable.begin,
            record_size=record_size,
            time_index=time_index,
            spatial_element_index=stop_element,
            itemsize=variable.itemsize,
        ) - 1
        return block, dataset.range_bytes(start, end)

    with ThreadPoolExecutor(max_workers=min(5, len(blocks))) as executor:
        raw_blocks = list(executor.map(read_block, blocks))
    output = np.empty((len(z_values), len(y_range), len(x_range)), dtype=np.float32)
    output_z = 0
    for block, raw in raw_blocks:
        values = np.frombuffer(raw, dtype=variable.dtype)
        first_element = (block[0] * ny + y_range.start) * nx
        for source_z in block:
            source_start = (source_z * ny + y_range.start) * nx - first_element
            source_stop = source_start + len(y_range) * nx
            plane = values[source_start:source_stop].reshape((len(y_range), nx))
            output[output_z] = plane[:, x_range.start : x_range.stop]
            output_z += 1
    return np.where(output <= -1.0e10, np.nan, output)


def _fetch_official_monthly_snapshots(year: int) -> list[SnapshotLike]:
    pilot, fetch = _source_modules()
    import h5py
    import requests

    cache_dir = INTERIM_DIR / "monthly_cache" / str(year)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = [cache_dir / f"{year}{month:02d}.npz" for month in range(7, 13)]
    if all(path.exists() for path in cached):
        return [pilot._load_snapshot(path) for path in cached]
    url = (
        "https://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
        f"soda3.15.2_mn_ocean_reg_{year}.nc"
    )
    session = requests.Session()
    kind = fetch.source_format(url, session)
    snapshots: list[SnapshotLike] = []
    if kind == "cdf2":
        dataset = fetch.ClassicNetCDFRemote(url, session=session)
        z_t_full = dataset.read_coordinate("st_ocean")
        z_w_full = dataset.read_coordinate("sw_ocean")
        lat_t_full = dataset.read_coordinate("yt_ocean")
        lon_t_full = dataset.read_coordinate("xt_ocean") % 360.0
        lat_uv_full = dataset.read_coordinate("yu_ocean")
        lon_uv_full = dataset.read_coordinate("xu_ocean") % 360.0
        slices = (
            _slice_coordinates(z_t_full, MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
            _slice_coordinates(z_w_full, MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
            _slice_coordinates(lat_t_full, SOUTH_EXIT_LATITUDE, NORTH_EXIT_LATITUDE),
            _slice_coordinates(lon_t_full, 218.0, EAST_EXIT_LONGITUDE),
            _slice_coordinates(lat_uv_full, SOUTH_EXIT_LATITUDE, NORTH_EXIT_LATITUDE),
            _slice_coordinates(lon_uv_full, 218.0, EAST_EXIT_LONGITUDE),
        )
        z_t_slice, z_w_slice, lat_t_slice, lon_t_slice, lat_uv_slice, lon_uv_slice = slices
        for month in range(7, 13):
            print(f"fetch monthly {year}-{month:02d} cdf2", flush=True)
            jobs = {
                "temp": ("temp", z_t_slice, lat_t_slice, lon_t_slice),
                "u": ("u", z_t_slice, lat_uv_slice, lon_uv_slice),
                "v": ("v", z_t_slice, lat_uv_slice, lon_uv_slice),
                "w": ("wt", z_w_slice, lat_t_slice, lon_t_slice),
            }
            with ThreadPoolExecutor(max_workers=4) as executor:
                future = {
                    name: executor.submit(
                        _classic_read_time_4d,
                        dataset,
                        parts[0],
                        month - 1,
                        parts[1],
                        parts[2],
                        parts[3],
                    )
                    for name, parts in jobs.items()
                }
                values = {name: item.result() for name, item in future.items()}
            snapshot = pilot.Snapshot(
                pd.Timestamp(year, month, 15),
                z_t_full[z_t_slice],
                z_w_full[z_w_slice],
                lat_t_full[lat_t_slice],
                lon_t_full[lon_t_slice],
                lat_uv_full[lat_uv_slice],
                lon_uv_full[lon_uv_slice],
                values["u"],
                values["v"],
                values["w"],
                values["temp"],
            )
            pilot._save_snapshot(cache_dir / f"{year}{month:02d}.npz", snapshot)
            snapshots.append(snapshot)
    elif kind == "hdf5":
        fsspec = fetch.import_fsspec()
        remote = fsspec.open(url, "rb", block_size=4 * 1024 * 1024, cache_type="readahead").open()
        try:
            with h5py.File(remote, "r") as dataset:
                z_t_full = np.asarray(dataset["st_ocean"][:], dtype=float)
                z_w_full = np.asarray(dataset["sw_ocean"][:], dtype=float)
                lat_t_full = np.asarray(dataset["yt_ocean"][:], dtype=float)
                lon_t_full = np.asarray(dataset["xt_ocean"][:], dtype=float) % 360.0
                lat_uv_full = np.asarray(dataset["yu_ocean"][:], dtype=float)
                lon_uv_full = np.asarray(dataset["xu_ocean"][:], dtype=float) % 360.0
                slices = (
                    _slice_coordinates(z_t_full, MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
                    _slice_coordinates(z_w_full, MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M),
                    _slice_coordinates(lat_t_full, SOUTH_EXIT_LATITUDE, NORTH_EXIT_LATITUDE),
                    _slice_coordinates(lon_t_full, 218.0, EAST_EXIT_LONGITUDE),
                    _slice_coordinates(lat_uv_full, SOUTH_EXIT_LATITUDE, NORTH_EXIT_LATITUDE),
                    _slice_coordinates(lon_uv_full, 218.0, EAST_EXIT_LONGITUDE),
                )
                z_t_slice, z_w_slice, lat_t_slice, lon_t_slice, lat_uv_slice, lon_uv_slice = slices
                for month in range(7, 13):
                    print(f"fetch monthly {year}-{month:02d} hdf5", flush=True)
                    snapshot = pilot.Snapshot(
                        pd.Timestamp(year, month, 15),
                        z_t_full[z_t_slice],
                        z_w_full[z_w_slice],
                        lat_t_full[lat_t_slice],
                        lon_t_full[lon_t_slice],
                        lat_uv_full[lat_uv_slice],
                        lon_uv_full[lon_uv_slice],
                        fetch.clean(dataset["u"][month - 1, z_t_slice, lat_uv_slice, lon_uv_slice]),
                        fetch.clean(dataset["v"][month - 1, z_t_slice, lat_uv_slice, lon_uv_slice]),
                        fetch.clean(dataset["wt"][month - 1, z_w_slice, lat_t_slice, lon_t_slice]),
                        fetch.clean(dataset["temp"][month - 1, z_t_slice, lat_t_slice, lon_t_slice]),
                    )
                    pilot._save_snapshot(cache_dir / f"{year}{month:02d}.npz", snapshot)
                    snapshots.append(snapshot)
        finally:
            remote.close()
    else:
        raise ValueError(f"Unsupported monthly source format {kind}")
    return snapshots


def load_monthly_tracking_snapshots(event: int) -> list[SnapshotLike]:
    snapshots = [_local_monthly_snapshot(event, month) for month in range(1, 7)]
    snapshots.extend(_fetch_official_monthly_snapshots(event))
    snapshots.extend(_local_monthly_snapshot(event + 1, month) for month in range(1, 6))
    return snapshots


def run_calculation(
    years: list[int],
    *,
    stride: int,
    step_hours: float,
    force_cache: bool,
    temporal_resolution: str = "monthly",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    endpoint_frames: list[pd.DataFrame] = []
    trajectory_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, float | int]] = []
    snapshot_counts: dict[str, int] = {}
    for event in years:
        if temporal_resolution == "monthly":
            snapshots = load_monthly_tracking_snapshots(event)
        elif temporal_resolution == "five_day":
            files = list_forward_event_files(event, stride)
            snapshots = load_event_snapshots(event, files, force_cache=force_cache)
        else:
            raise ValueError(f"Unknown temporal resolution {temporal_resolution}")
        release_months = sorted(
            {snapshot.timestamp.month for snapshot in snapshots if is_release_time(snapshot.timestamp, event)}
        )
        expected_fields = {
            month: load_temperature_expected_field(
                event,
                month,
                longitude_bounds=(218.0, 222.0),
            )
            for month in release_months
        }
        final_expected = load_temperature_expected_field(
            event + 1,
            snapshots[-1].timestamp.month,
            longitude_bounds=(218.0, 280.0),
        )
        endpoints, trajectories = track_event_cohorts(
            event=event,
            snapshots=snapshots,
            release_expected_fields=expected_fields,
            final_expected_field=final_expected,
            step_hours=step_hours,
        )
        endpoint_frames.append(endpoints)
        trajectory_frames.append(trajectories)
        summary_rows.append(summarize_endpoints(endpoints))
        snapshot_counts[str(event)] = len(snapshots)
    endpoints = pd.concat(endpoint_frames, ignore_index=True)
    trajectories = pd.concat(trajectory_frames, ignore_index=True)
    summary = pd.DataFrame(summary_rows).sort_values("event").reset_index(drop=True)
    audit = audit_summary(summary)
    audit.update(
        {
            "stride": int(stride),
            "step_hours": float(step_hours),
            "temporal_resolution": temporal_resolution,
            "snapshot_counts": snapshot_counts,
            "release_latitude_range": [-5.0, 5.0],
            "tracking_domain": {
                "longitude": [218.0, 280.0],
                "latitude": [-5.0, 5.0],
                "depth_m": [MINIMUM_DEPTH_M, MAXIMUM_DEPTH_M],
            },
            "method_scope": (
                "Heat-flux-weighted Lagrangian connectivity and following-May endpoint "
                "temperature anomaly; not a full native diffusion/external-heating budget."
            ),
        }
    )
    return endpoints, trajectories, summary, audit


def write_calculation_tables(
    endpoints: pd.DataFrame,
    trajectories: pd.DataFrame,
    summary: pd.DataFrame,
    audit: dict[str, object],
) -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    endpoints.to_csv(ENDPOINT_CSV, index=False, float_format="%.8g")
    trajectories.to_csv(TRAJECTORY_CSV, index=False, float_format="%.8g")
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.8g")
    AUDIT_JSON.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2015, 2023])
    parser.add_argument("--stride", type=int, default=6)
    parser.add_argument("--step-hours", type=float, default=12.0)
    parser.add_argument("--force-cache", action="store_true")
    parser.add_argument(
        "--temporal-resolution",
        choices=["monthly", "five_day"],
        default="monthly",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoints, trajectories, summary, audit = run_calculation(
        args.years,
        stride=args.stride,
        step_hours=args.step_hours,
        force_cache=args.force_cache,
        temporal_resolution=args.temporal_resolution,
    )
    write_calculation_tables(endpoints, trajectories, summary, audit)
    print(summary.to_string(index=False), flush=True)
    for path in (ENDPOINT_CSV, TRAJECTORY_CSV, SUMMARY_CSV, AUDIT_JSON):
        print(path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
