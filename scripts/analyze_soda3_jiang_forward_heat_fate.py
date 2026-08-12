#!/usr/bin/env python3
"""Track 140°W positive anomalous heat forward with SODA3 five-day flow.

This implements a Jiang-style Lagrangian destination diagnostic while
retaining the established fixed-box heat budget as an independent Eulerian
closure.  It does not use H20 or a fixed temperature threshold.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator


ROOT = Path(__file__).resolve().parents[1]
RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS_M = 6_371_000.0
SECONDS_PER_DAY = 86_400.0
GATE_LONGITUDE = 220.0
WEST_EXIT_LONGITUDE = 220.0
EAST_EXIT_LONGITUDE = 280.0
SOUTH_EXIT_LATITUDE = -10.0
NORTH_EXIT_LATITUDE = 5.0
MINIMUM_DEPTH_M = 5.0
MAXIMUM_DEPTH_M = 300.0
MINIMUM_ANOMALY_C = 0.05


class SnapshotLike(Protocol):
    timestamp: pd.Timestamp
    z_t: np.ndarray
    lat_t: np.ndarray

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


def _mark_exits(state: pd.DataFrame, indices: np.ndarray) -> None:
    if len(indices) == 0:
        return
    lon = state.loc[indices, "lon"].to_numpy(float)
    lat = state.loc[indices, "lat"].to_numpy(float)
    depth = state.loc[indices, "depth_m"].to_numpy(float)
    destinations = np.full(len(indices), "active", dtype=object)
    destinations[lon < WEST_EXIT_LONGITUDE] = "returned_west_140w"
    destinations[(destinations == "active") & (lat > NORTH_EXIT_LATITUDE)] = "north_of_5n"
    destinations[(destinations == "active") & (lat < SOUTH_EXIT_LATITUDE)] = "south_of_10s"
    destinations[(destinations == "active") & (depth > MAXIMUM_DEPTH_M)] = "below_300m"
    destinations[(destinations == "active") & (lon > EAST_EXIT_LONGITUDE)] = "east_of_80w"
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
            result.loc[failed, "destination"] = "invalid_velocity"
        indices = indices[valid_first]
        if len(indices) == 0:
            current_seconds += dt
            continue
        positions = positions[valid_first]
        midpoint = positions + 0.5 * dt * first[valid_first]
        midpoint[:, 2] = np.maximum(midpoint[:, 2], MINIMUM_DEPTH_M)
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
            result.loc[failed, "destination"] = "invalid_velocity"
        indices = indices[valid_second]
        if len(indices) == 0:
            current_seconds += dt
            continue
        candidate = positions[valid_second] + dt * second[valid_second]
        shallow = candidate[:, 2] < MINIMUM_DEPTH_M
        if np.any(shallow):
            shallow_indices = indices[shallow]
            candidate[shallow, 2] = MINIMUM_DEPTH_M
            result.loc[shallow_indices, "surface_clip_steps"] = (
                result.loc[shallow_indices, "surface_clip_steps"].to_numpy(int) + 1
            )
        result.loc[indices, ["lon", "lat", "depth_m"]] = candidate
        _mark_exits(result, indices)
        current_seconds += dt
    return result
