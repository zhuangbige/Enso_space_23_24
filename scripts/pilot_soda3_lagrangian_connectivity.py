#!/usr/bin/env python3
"""Pilot backward particle tracking with SODA3.15.2 five-day fields.

This is a deliberately small, falsifiable connectivity experiment.  Particles
representing positive temperature anomalies are released in the eastern
equatorial Pacific at the final January--June SODA3 record and integrated
backward with offline u/v/w fields.  It tests whether the Eulerian heat-anomaly
analysis has a plausible water-mass pathway; it is not a closed heat budget or
a passive-tracer model.

The default samples every sixth five-day record (roughly monthly) for a cheap
technical pilot.  Use ``--stride 1`` only after the pilot QA is satisfactory.
"""

from __future__ import annotations

import argparse
import math
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import h5py
import matplotlib
import numpy as np
import pandas as pd
import requests
import xarray as xr
from scipy.interpolate import RegularGridInterpolator

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from fetch_soda3_5day_event_transport import (
    ClassicNetCDFRemote,
    clean,
    contiguous_slice,
    import_fsspec,
    list_event_files,
    source_format,
)


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = (
    ROOT / "data/interim/research_2026/soda3_lagrangian_pilot/cache"
)
TEMPERATURE_BASELINE_NC = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
DATA_DIR = ROOT / "data/derived/research_2026"
OUTPUT_DIR = (
    ROOT / "outputs/research_2026/soda3_temp_anomaly_lagrangian_pilot"
)
ENDPOINT_CSV = DATA_DIR / "soda3_temp_anomaly_lagrangian_pilot_endpoints.csv"
TRAJECTORY_CSV = DATA_DIR / "soda3_temp_anomaly_lagrangian_pilot_trajectories.csv"
SUMMARY_CSV = DATA_DIR / "soda3_temp_anomaly_lagrangian_pilot_summary.csv"
SENSITIVITY_CSV = (
    DATA_DIR / "soda3_temp_anomaly_lagrangian_pilot_vertical_sensitivity.csv"
)
FIGURE_PNG = OUTPUT_DIR / "soda3_temp_anomaly_lagrangian_pilot.png"
FIGURE_PDF = OUTPUT_DIR / "soda3_temp_anomaly_lagrangian_pilot.pdf"
SENSITIVITY_PNG = (
    OUTPUT_DIR / "soda3_temp_anomaly_lagrangian_pilot_sensitivity.png"
)
SENSITIVITY_PDF = (
    OUTPUT_DIR / "soda3_temp_anomaly_lagrangian_pilot_sensitivity.pdf"
)
REPORT_MD = OUTPUT_DIR / "SODA3_TEMP_ANOMALY_LAGRANGIAN_PILOT_CN.md"

DEFAULT_YEARS = (1997, 2015, 2023)
EARTH_RADIUS_M = 6_371_000.0
SECONDS_PER_DAY = 86_400.0

DOMAIN_LON = (145.0, 270.0)
DOMAIN_LAT = (-8.0, 8.0)
DOMAIN_DEPTH = (5.0, 200.0)
RELEASE_LON = (220.0, 260.0)
RELEASE_LAT = (-5.0, 5.0)
RELEASE_DEPTHS = np.asarray([15.0, 35.0, 60.0, 90.0, 125.0, 160.0])
WEIGHT_COLUMN = "heat_anomaly_weight"
MINIMUM_RELEASE_ANOMALY_C = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument(
        "--stride",
        type=int,
        default=6,
        help="Use every Nth native five-day record; 6 is a coarse pilot.",
    )
    parser.add_argument("--step-hours", type=float, default=12.0)
    parser.add_argument("--force-cache", action="store_true")
    parser.add_argument(
        "--skip-sensitivity",
        action="store_true",
        help="Skip no-w and reversed-w sign checks.",
    )
    return parser.parse_args()


@dataclass
class Snapshot:
    timestamp: pd.Timestamp
    z_t: np.ndarray
    z_w: np.ndarray
    lat_t: np.ndarray
    lon_t: np.ndarray
    lat_uv: np.ndarray
    lon_uv: np.ndarray
    u: np.ndarray
    v: np.ndarray
    w: np.ndarray
    temp: np.ndarray | None = None
    _interpolators: dict[str, RegularGridInterpolator] = field(
        default_factory=dict,
        repr=False,
    )

    def interpolate(self, name: str, positions: np.ndarray) -> np.ndarray:
        if name not in self._interpolators:
            if name in {"u", "v"}:
                grid = (self.z_t, self.lat_uv, self.lon_uv)
            elif name == "w":
                grid = (self.z_w, self.lat_t, self.lon_t)
            elif name == "temp" and self.temp is not None:
                grid = (self.z_t, self.lat_t, self.lon_t)
            else:
                raise KeyError(f"Field {name!r} is unavailable")
            self._interpolators[name] = RegularGridInterpolator(
                grid,
                getattr(self, name),
                bounds_error=False,
                fill_value=np.nan,
            )
        query = np.column_stack(
            [positions[:, 2], positions[:, 1], positions[:, 0]]
        )
        return np.asarray(self._interpolators[name](query), dtype=float)


def velocity_to_position_rates(
    positions: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    w: np.ndarray,
    *,
    w_to_depth_sign: float = -1.0,
) -> np.ndarray:
    """Convert m/s velocities to degrees/s, degrees/s and depth-m/s.

    SODA depth coordinates are positive downward.  The main experiment uses
    conventional upward-positive ocean w, hence ``dz/dt = -w``.  A reversed
    sign and a no-w experiment are reported as explicit sensitivities.
    """
    latitude_radians = np.deg2rad(positions[:, 1])
    cos_latitude = np.cos(latitude_radians)
    result = np.empty_like(positions, dtype=float)
    result[:, 0] = (
        u / (EARTH_RADIUS_M * cos_latitude) * 180.0 / np.pi
    )
    result[:, 1] = v / EARTH_RADIUS_M * 180.0 / np.pi
    result[:, 2] = w_to_depth_sign * w
    return result


def _time_interpolated_rates(
    earlier: Snapshot,
    later: Snapshot,
    positions: np.ndarray,
    alpha: float,
    *,
    w_to_depth_sign: float,
) -> np.ndarray:
    alpha = float(np.clip(alpha, 0.0, 1.0))
    u = (1.0 - alpha) * earlier.interpolate("u", positions) + alpha * later.interpolate(
        "u", positions
    )
    v = (1.0 - alpha) * earlier.interpolate("v", positions) + alpha * later.interpolate(
        "v", positions
    )
    if w_to_depth_sign == 0.0:
        w = np.zeros(len(positions), dtype=float)
    else:
        w = (1.0 - alpha) * earlier.interpolate("w", positions) + alpha * later.interpolate(
            "w", positions
        )
    return velocity_to_position_rates(
        positions,
        u,
        v,
        w,
        w_to_depth_sign=w_to_depth_sign,
    )


def integrate_interval(
    positions: np.ndarray,
    active: np.ndarray,
    status: np.ndarray,
    surface_hits: np.ndarray,
    earlier: Snapshot,
    later: Snapshot,
    *,
    step_hours: float,
    w_to_depth_sign: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Integrate from ``later`` backward to ``earlier`` with midpoint RK2."""
    total_seconds = float((later.timestamp - earlier.timestamp).total_seconds())
    if total_seconds <= 0.0:
        raise ValueError("Snapshots must be in strictly increasing time order")
    count = max(1, int(math.ceil(total_seconds / (step_hours * 3600.0))))
    dt = -total_seconds / count
    current_time = total_seconds
    result = positions.copy()
    active_result = active.copy()
    status_result = status.copy()
    surface_result = surface_hits.copy()

    minimum_depth = max(float(earlier.z_t.min()), float(earlier.z_w.min()))
    maximum_depth = min(float(earlier.z_t.max()), float(earlier.z_w.max()))
    minimum_depth = max(minimum_depth, DOMAIN_DEPTH[0])
    maximum_depth = min(maximum_depth, DOMAIN_DEPTH[1])

    for _ in range(count):
        indices = np.flatnonzero(active_result)
        if not len(indices):
            break
        points = result[indices]
        alpha = current_time / total_seconds
        first = _time_interpolated_rates(
            earlier,
            later,
            points,
            alpha,
            w_to_depth_sign=w_to_depth_sign,
        )
        first_valid = np.isfinite(first).all(axis=1)
        if not np.all(first_valid):
            failed = indices[~first_valid]
            active_result[failed] = False
            status_result[failed] = "invalid_velocity"
        indices = indices[first_valid]
        if not len(indices):
            current_time += dt
            continue
        first = first[first_valid]
        midpoint = result[indices] + 0.5 * dt * first
        midpoint[:, 2] = np.maximum(midpoint[:, 2], minimum_depth)
        second = _time_interpolated_rates(
            earlier,
            later,
            midpoint,
            (current_time + 0.5 * dt) / total_seconds,
            w_to_depth_sign=w_to_depth_sign,
        )
        second_valid = np.isfinite(second).all(axis=1)
        if not np.all(second_valid):
            failed = indices[~second_valid]
            active_result[failed] = False
            status_result[failed] = "invalid_velocity"
        indices = indices[second_valid]
        if not len(indices):
            current_time += dt
            continue
        candidate = result[indices] + dt * second[second_valid]
        shallow = candidate[:, 2] < minimum_depth
        candidate[shallow, 2] = minimum_depth
        surface_result[indices[shallow]] += 1

        horizontal_exit = (
            (candidate[:, 0] < DOMAIN_LON[0])
            | (candidate[:, 0] > DOMAIN_LON[1])
            | (candidate[:, 1] < DOMAIN_LAT[0])
            | (candidate[:, 1] > DOMAIN_LAT[1])
        )
        depth_exit = candidate[:, 2] > maximum_depth
        result[indices] = candidate
        if np.any(horizontal_exit):
            failed = indices[horizontal_exit]
            active_result[failed] = False
            status_result[failed] = "horizontal_exit"
        if np.any(depth_exit):
            failed = indices[depth_exit & ~horizontal_exit]
            active_result[failed] = False
            status_result[failed] = "depth_exit"
        current_time += dt
    return result, active_result, status_result, surface_result


def classify_endpoint(lon: float, lat: float, active: bool, status: str) -> str:
    if not active:
        return status
    if lat > 5.0:
        return "north_of_5N"
    if lat < -5.0:
        return "south_of_5S"
    if lon < 180.0:
        return "equatorial_west"
    if lon < 220.0:
        return "equatorial_central"
    return "equatorial_east"


def _selected_files(
    files: list[tuple[pd.Timestamp, str]],
    stride: int,
) -> list[tuple[pd.Timestamp, str]]:
    if stride < 1:
        raise ValueError("stride must be at least one")
    selected = files[::stride]
    if selected[-1][0] != files[-1][0]:
        selected.append(files[-1])
    return selected


def _grid_slices(
    z_t_full: np.ndarray,
    z_w_full: np.ndarray,
    lat_t_full: np.ndarray,
    lon_t_full: np.ndarray,
    lat_uv_full: np.ndarray,
    lon_uv_full: np.ndarray,
) -> tuple[tuple[np.ndarray, ...], tuple[slice, ...]]:
    z_t_slice = contiguous_slice(z_t_full, *DOMAIN_DEPTH)
    z_w_slice = contiguous_slice(z_w_full, *DOMAIN_DEPTH)
    lat_t_slice = contiguous_slice(lat_t_full, *DOMAIN_LAT)
    lon_t_slice = contiguous_slice(lon_t_full, *DOMAIN_LON)
    lat_uv_slice = contiguous_slice(lat_uv_full, *DOMAIN_LAT)
    lon_uv_slice = contiguous_slice(lon_uv_full, *DOMAIN_LON)
    grids = (
        z_t_full[z_t_slice],
        z_w_full[z_w_slice],
        lat_t_full[lat_t_slice],
        lon_t_full[lon_t_slice],
        lat_uv_full[lat_uv_slice],
        lon_uv_full[lon_uv_slice],
    )
    slices = (
        z_t_slice,
        z_w_slice,
        lat_t_slice,
        lon_t_slice,
        lat_uv_slice,
        lon_uv_slice,
    )
    return grids, slices


def _read_cdf2_snapshot(
    timestamp: pd.Timestamp,
    url: str,
    session: requests.Session,
    metadata: dict[str, object],
    *,
    need_temp: bool,
) -> Snapshot:
    template = metadata.get("template")
    dataset = ClassicNetCDFRemote(
        url,
        session=session,
        template=template if isinstance(template, ClassicNetCDFRemote) else None,
    )
    if template is None:
        metadata["template"] = dataset
    if "grid" not in metadata:
        grids, slices = _grid_slices(
            dataset.read_coordinate("st_ocean"),
            dataset.read_coordinate("sw_ocean"),
            dataset.read_coordinate("yt_ocean"),
            dataset.read_coordinate("xt_ocean") % 360.0,
            dataset.read_coordinate("yu_ocean"),
            dataset.read_coordinate("xu_ocean") % 360.0,
        )
        metadata["grid"] = grids
        metadata["slices"] = slices
    z_t, z_w, lat_t, lon_t, lat_uv, lon_uv = metadata["grid"]
    z_t_slice, z_w_slice, lat_t_slice, lon_t_slice, lat_uv_slice, lon_uv_slice = metadata[
        "slices"
    ]

    jobs = {
        "u": (z_t_slice, lat_uv_slice, lon_uv_slice),
        "v": (z_t_slice, lat_uv_slice, lon_uv_slice),
        "w": (z_w_slice, lat_t_slice, lon_t_slice),
    }
    if need_temp:
        jobs["temp"] = (z_t_slice, lat_t_slice, lon_t_slice)
    with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        futures = {
            name: executor.submit(dataset.read_record_4d, "wt" if name == "w" else name, *parts)
            for name, parts in jobs.items()
        }
        values = {name: future.result() for name, future in futures.items()}
    return Snapshot(
        timestamp,
        np.asarray(z_t),
        np.asarray(z_w),
        np.asarray(lat_t),
        np.asarray(lon_t),
        np.asarray(lat_uv),
        np.asarray(lon_uv),
        values["u"],
        values["v"],
        values["w"],
        values.get("temp"),
    )


def _read_hdf5_snapshot(
    timestamp: pd.Timestamp,
    url: str,
    *,
    need_temp: bool,
) -> Snapshot:
    fsspec = import_fsspec()
    remote = fsspec.open(
        url,
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            grids, slices = _grid_slices(
                np.asarray(dataset["st_ocean"][:], dtype=float),
                np.asarray(dataset["sw_ocean"][:], dtype=float),
                np.asarray(dataset["yt_ocean"][:], dtype=float),
                np.asarray(dataset["xt_ocean"][:], dtype=float) % 360.0,
                np.asarray(dataset["yu_ocean"][:], dtype=float),
                np.asarray(dataset["xu_ocean"][:], dtype=float) % 360.0,
            )
            z_t, z_w, lat_t, lon_t, lat_uv, lon_uv = grids
            z_t_slice, z_w_slice, lat_t_slice, lon_t_slice, lat_uv_slice, lon_uv_slice = slices
            u = clean(dataset["u"][0, z_t_slice, lat_uv_slice, lon_uv_slice])
            v = clean(dataset["v"][0, z_t_slice, lat_uv_slice, lon_uv_slice])
            w = clean(dataset["wt"][0, z_w_slice, lat_t_slice, lon_t_slice])
            temp = (
                clean(dataset["temp"][0, z_t_slice, lat_t_slice, lon_t_slice])
                if need_temp
                else None
            )
    finally:
        remote.close()
    return Snapshot(
        timestamp,
        z_t,
        z_w,
        lat_t,
        lon_t,
        lat_uv,
        lon_uv,
        u,
        v,
        w,
        temp,
    )


def _save_snapshot(path: Path, snapshot: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        timestamp_ns=np.asarray(snapshot.timestamp.value, dtype=np.int64),
        z_t=snapshot.z_t,
        z_w=snapshot.z_w,
        lat_t=snapshot.lat_t,
        lon_t=snapshot.lon_t,
        lat_uv=snapshot.lat_uv,
        lon_uv=snapshot.lon_uv,
        u=snapshot.u,
        v=snapshot.v,
        w=snapshot.w,
        temp=np.asarray([]) if snapshot.temp is None else snapshot.temp,
    )


def _load_snapshot(path: Path) -> Snapshot:
    with np.load(path) as data:
        temp = np.asarray(data["temp"])
        return Snapshot(
            pd.Timestamp(int(data["timestamp_ns"])),
            np.asarray(data["z_t"]),
            np.asarray(data["z_w"]),
            np.asarray(data["lat_t"]),
            np.asarray(data["lon_t"]),
            np.asarray(data["lat_uv"]),
            np.asarray(data["lon_uv"]),
            np.asarray(data["u"]),
            np.asarray(data["v"]),
            np.asarray(data["w"]),
            None if temp.size == 0 else temp,
        )


def get_snapshot(
    year: int,
    timestamp: pd.Timestamp,
    url: str,
    session: requests.Session,
    metadata: dict[str, object],
    *,
    need_temp: bool,
    force: bool,
) -> Snapshot:
    cache_path = CACHE_DIR / str(year) / f"{timestamp:%Y%m%d}.npz"
    if cache_path.exists() and not force:
        cached = _load_snapshot(cache_path)
        if not need_temp or cached.temp is not None:
            print(f"cache {year} {timestamp.date()}", flush=True)
            return cached
    snapshot: Snapshot | None = None
    for attempt in range(1, 6):
        try:
            kind = metadata.get("format")
            if kind is None:
                kind = source_format(url, session)
                metadata["format"] = kind
            print(
                f"fetch {year} {timestamp.date()} {kind} attempt={attempt}",
                flush=True,
            )
            if kind == "cdf2":
                snapshot = _read_cdf2_snapshot(
                    timestamp,
                    url,
                    session,
                    metadata,
                    need_temp=need_temp,
                )
            elif kind == "hdf5":
                snapshot = _read_hdf5_snapshot(timestamp, url, need_temp=need_temp)
            else:
                raise ValueError(f"Unsupported source format {kind!r}")
            break
        except Exception as error:
            if attempt == 5:
                raise
            metadata.pop("format", None)
            print(
                f"retry {year} {timestamp.date()} after "
                f"{type(error).__name__}: {error}",
                flush=True,
            )
            time.sleep(2.0 * attempt)
    if snapshot is None:
        raise RuntimeError(f"Snapshot read failed without an exception: {url}")
    _save_snapshot(cache_path, snapshot)
    return snapshot


@dataclass(frozen=True)
class TemperatureExpectedField:
    depth: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    temperature_c: np.ndarray
    month: int
    baseline_start_year: int
    baseline_end_year: int


def linear_expected_temperature(
    values: np.ndarray,
    years: np.ndarray,
    target_year: int,
) -> np.ndarray:
    """Return the cellwise linear expected value at ``target_year``.

    ``values`` has time on axis zero.  NaNs are handled cell by cell, and at
    least three finite years are required.  The event year must be removed by
    the caller so its anomaly cannot pull its own baseline toward zero.
    """
    data = np.asarray(values, dtype=float)
    x = np.asarray(years, dtype=float)
    if data.ndim < 2 or data.shape[0] != len(x):
        raise ValueError("Temperature time dimension does not match years")
    reshape = (len(x),) + (1,) * (data.ndim - 1)
    x_full = x.reshape(reshape)
    valid = np.isfinite(data)
    count = valid.sum(axis=0)
    x_sum = np.where(valid, x_full, 0.0).sum(axis=0)
    y_sum = np.where(valid, data, 0.0).sum(axis=0)
    x_mean = np.divide(
        x_sum,
        count,
        out=np.full_like(x_sum, np.nan, dtype=float),
        where=count > 0,
    )
    y_mean = np.divide(
        y_sum,
        count,
        out=np.full_like(y_sum, np.nan, dtype=float),
        where=count > 0,
    )
    x_centered = x_full - x_mean
    numerator = np.where(valid, x_centered * (data - y_mean), 0.0).sum(axis=0)
    denominator = np.where(valid, x_centered**2, 0.0).sum(axis=0)
    slope = np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, np.nan, dtype=float),
        where=(count >= 3) & (denominator > 0.0),
    )
    return y_mean + slope * (float(target_year) - x_mean)


def load_temperature_expected_field(
    event: int,
    month: int,
) -> TemperatureExpectedField:
    if not TEMPERATURE_BASELINE_NC.exists():
        raise FileNotFoundError(TEMPERATURE_BASELINE_NC)
    with xr.open_dataset(TEMPERATURE_BASELINE_NC) as dataset:
        if dataset["temp"].attrs.get("units") not in {"degC", "degrees C"}:
            raise ValueError("Unexpected SODA temperature units")
        subset = (
            dataset["temp"]
            .where(dataset.time.dt.month == month, drop=True)
            .sel(
                depth=slice(DOMAIN_DEPTH[0], DOMAIN_DEPTH[1]),
                lat=slice(RELEASE_LAT[0], RELEASE_LAT[1]),
                lon=slice(RELEASE_LON[0] - 2.0, RELEASE_LON[1] + 2.0),
            )
            .load()
        )
    years = np.asarray(subset.time.dt.year.to_numpy(), dtype=int)
    keep = years != event
    if not np.any(years == event):
        raise ValueError(f"Event year {event} is absent from temperature baseline")
    expected = linear_expected_temperature(
        subset.to_numpy()[keep],
        years[keep],
        event,
    )
    for coordinate in ("depth", "lat", "lon"):
        values = np.asarray(subset[coordinate].to_numpy(), dtype=float)
        if not np.all(np.diff(values) > 0.0):
            raise ValueError(f"Temperature baseline {coordinate} is not increasing")
    return TemperatureExpectedField(
        depth=np.asarray(subset.depth.to_numpy(), dtype=float),
        lat=np.asarray(subset.lat.to_numpy(), dtype=float),
        lon=np.asarray(subset.lon.to_numpy(), dtype=float),
        temperature_c=expected,
        month=month,
        baseline_start_year=int(years.min()),
        baseline_end_year=int(years.max()),
    )


def _sparse_release_coordinate(
    values: np.ndarray,
    lower: float,
    upper: float,
    *,
    stride: int = 5,
) -> np.ndarray:
    selected = np.asarray(values[(values >= lower) & (values <= upper)], dtype=float)
    if selected.size == 0:
        raise ValueError(f"No release coordinates inside {lower}..{upper}")
    output = selected[::stride]
    if not np.isclose(output[-1], selected[-1]):
        output = np.append(output, selected[-1])
    return output


def seed_particles(
    snapshot: Snapshot,
    event: int,
    expected_field: TemperatureExpectedField,
) -> pd.DataFrame:
    if snapshot.temp is None:
        raise ValueError("Release snapshot must include temperature")
    lon_values = _sparse_release_coordinate(
        expected_field.lon,
        *RELEASE_LON,
    )
    lat_values = _sparse_release_coordinate(
        expected_field.lat,
        *RELEASE_LAT,
    )
    lon, lat, depth = np.meshgrid(
        lon_values,
        lat_values,
        RELEASE_DEPTHS,
        indexing="xy",
    )
    positions = np.column_stack([lon.ravel(), lat.ravel(), depth.ravel()])
    temperature = snapshot.interpolate("temp", positions)
    baseline_interpolator = RegularGridInterpolator(
        (expected_field.depth, expected_field.lat, expected_field.lon),
        expected_field.temperature_c,
        bounds_error=False,
        fill_value=np.nan,
    )
    expected_temperature = baseline_interpolator(
        np.column_stack([positions[:, 2], positions[:, 1], positions[:, 0]])
    )
    temperature_anomaly = temperature - expected_temperature
    valid = (
        np.isfinite(temperature)
        & np.isfinite(expected_temperature)
        & (temperature_anomaly > MINIMUM_RELEASE_ANOMALY_C)
    )
    positions = positions[valid]
    temperature = temperature[valid]
    expected_temperature = expected_temperature[valid]
    temperature_anomaly = temperature_anomaly[valid]
    depth_edges = np.concatenate(
        [
            [max(DOMAIN_DEPTH[0], RELEASE_DEPTHS[0] - 10.0)],
            0.5 * (RELEASE_DEPTHS[:-1] + RELEASE_DEPTHS[1:]),
            [min(DOMAIN_DEPTH[1], RELEASE_DEPTHS[-1] + 20.0)],
        ]
    )
    layer_thickness = np.diff(depth_edges)
    depth_weight = np.interp(positions[:, 2], RELEASE_DEPTHS, layer_thickness)
    anomaly_weight = (
        temperature_anomaly
        * np.cos(np.deg2rad(positions[:, 1]))
        * depth_weight
    )
    return pd.DataFrame(
        {
            "event": event,
            "particle_id": np.arange(len(positions), dtype=int),
            "release_lon": positions[:, 0],
            "release_lat": positions[:, 1],
            "release_depth_m": positions[:, 2],
            "release_temp_c": temperature,
            "expected_temp_c": expected_temperature,
            "release_temp_anomaly_c": temperature_anomaly,
            WEIGHT_COLUMN: anomaly_weight,
        }
    )


def track_event(
    event: int,
    snapshots: list[Snapshot],
    seeds: pd.DataFrame,
    *,
    step_hours: float,
    w_to_depth_sign: float,
    retain_trajectory: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = seeds[["release_lon", "release_lat", "release_depth_m"]].to_numpy(float)
    active = np.ones(len(seeds), dtype=bool)
    status = np.full(len(seeds), "active", dtype=object)
    surface_hits = np.zeros(len(seeds), dtype=int)
    records: list[pd.DataFrame] = []

    def record(timestamp: pd.Timestamp) -> None:
        if not retain_trajectory:
            return
        frame = pd.DataFrame(
            {
                "event": event,
                "date": timestamp,
                "particle_id": seeds["particle_id"].to_numpy(),
                "lon": positions[:, 0],
                "lat": positions[:, 1],
                "depth_m": positions[:, 2],
                "active": active,
            }
        )
        records.append(frame)

    record(snapshots[-1].timestamp)
    for index in range(len(snapshots) - 2, -1, -1):
        earlier = snapshots[index]
        later = snapshots[index + 1]
        positions, active, status, surface_hits = integrate_interval(
            positions,
            active,
            status,
            surface_hits,
            earlier,
            later,
            step_hours=step_hours,
            w_to_depth_sign=w_to_depth_sign,
        )
        record(earlier.timestamp)

    endpoints = seeds.copy()
    endpoints["source_date"] = snapshots[0].timestamp
    endpoints["source_lon"] = positions[:, 0]
    endpoints["source_lat"] = positions[:, 1]
    endpoints["source_depth_m"] = positions[:, 2]
    endpoints["active"] = active
    endpoints["status"] = status
    endpoints["surface_clip_steps"] = surface_hits
    endpoints["zonal_displacement_deg"] = endpoints["release_lon"] - endpoints["source_lon"]
    endpoints["source_region"] = [
        classify_endpoint(lon, lat, ok, state)
        for lon, lat, ok, state in zip(
            positions[:, 0], positions[:, 1], active, status, strict=True
        )
    ]
    trajectory = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
    return endpoints, trajectory


def weighted_fraction(frame: pd.DataFrame, mask: pd.Series | np.ndarray) -> float:
    denominator = float(frame[WEIGHT_COLUMN].sum())
    if denominator <= 0.0:
        return float("nan")
    return float(frame.loc[np.asarray(mask), WEIGHT_COLUMN].sum() / denominator)


def summarize_endpoints(
    endpoints: pd.DataFrame,
    *,
    variant: str,
) -> dict[str, float | int | str]:
    active = endpoints["active"]
    total_weight = float(endpoints[WEIGHT_COLUMN].sum())
    active_frame = endpoints.loc[active]
    if active_frame.empty:
        weighted_median_displacement = float("nan")
    else:
        ordered = active_frame.sort_values("zonal_displacement_deg")
        cumulative = ordered[WEIGHT_COLUMN].cumsum()
        weighted_median_displacement = float(
            ordered.loc[cumulative >= 0.5 * cumulative.iloc[-1], "zonal_displacement_deg"].iloc[0]
        )
    row: dict[str, float | int | str] = {
        "event": int(endpoints["event"].iloc[0]),
        "variant": variant,
        "particle_count": int(len(endpoints)),
        "active_fraction_count": float(active.mean()),
        "active_fraction_weight": float(
            endpoints.loc[active, WEIGHT_COLUMN].sum() / total_weight
        ),
        "weighted_mean_release_temp_anomaly_c": float(
            np.average(
                endpoints["release_temp_anomaly_c"],
                weights=endpoints[WEIGHT_COLUMN],
            )
        ),
        "weighted_median_eastward_displacement_deg": weighted_median_displacement,
        "surface_clip_fraction": float((endpoints["surface_clip_steps"] > 0).mean()),
    }
    for region in (
        "equatorial_west",
        "equatorial_central",
        "equatorial_east",
        "north_of_5N",
        "south_of_5S",
        "invalid_velocity",
        "horizontal_exit",
        "depth_exit",
    ):
        row[f"weight_fraction_{region}"] = weighted_fraction(
            endpoints,
            endpoints["source_region"] == region,
        )
    return row


def plot_results(endpoints: pd.DataFrame, trajectory: pd.DataFrame, summary: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    events = sorted(endpoints["event"].unique())
    colors = {1997: "#b2182b", 2015: "#ef8a62", 2023: "#2166ac"}
    fig = plt.figure(figsize=(13.2, 8.4))
    grid = fig.add_gridspec(2, len(events), height_ratios=[2.1, 1.0], hspace=0.28, wspace=0.18)
    for column, event in enumerate(events):
        axis = fig.add_subplot(grid[0, column])
        event_tracks = trajectory.loc[trajectory["event"] == event]
        particle_ids = event_tracks["particle_id"].drop_duplicates().to_numpy()
        if len(particle_ids) > 70:
            particle_ids = particle_ids[np.linspace(0, len(particle_ids) - 1, 70).astype(int)]
        for particle_id in particle_ids:
            path = event_tracks.loc[event_tracks["particle_id"] == particle_id].sort_values("date")
            axis.plot(path["lon"], path["lat"], color=colors.get(event, "0.4"), alpha=0.17, lw=0.7)
        event_end = endpoints.loc[endpoints["event"] == event]
        relative_weight = event_end[WEIGHT_COLUMN] / event_end[WEIGHT_COLUMN].max()
        point_size = 3.0 + 18.0 * np.sqrt(relative_weight)
        axis.scatter(
            event_end["source_lon"],
            event_end["source_lat"],
            s=point_size,
            color="#2166ac",
            alpha=0.25,
            label="Jan source",
        )
        axis.scatter(
            event_end["release_lon"],
            event_end["release_lat"],
            s=point_size,
            color="#b2182b",
            alpha=0.25,
            label="Jun release",
        )
        axis.axvline(180.0, color="0.55", ls="--", lw=0.8)
        axis.axvline(220.0, color="0.55", ls="--", lw=0.8)
        axis.axhline(5.0, color="0.65", ls=":", lw=0.8)
        axis.axhline(-5.0, color="0.65", ls=":", lw=0.8)
        axis.add_patch(
            Rectangle(
                (RELEASE_LON[0], RELEASE_LAT[0]),
                RELEASE_LON[1] - RELEASE_LON[0],
                RELEASE_LAT[1] - RELEASE_LAT[0],
                fill=False,
                edgecolor="#b2182b",
                linewidth=0.9,
                linestyle="--",
            )
        )
        axis.set_xlim(*DOMAIN_LON)
        axis.set_ylim(*DOMAIN_LAT)
        axis.set_xticks(
            [160, 180, 200, 220, 240, 260],
            ["160°E", "180°", "160°W", "140°W", "120°W", "100°W"],
        )
        axis.set_title(str(event), fontweight="bold")
        axis.set_xlabel("Longitude (°E)")
        if column == 0:
            axis.set_ylabel("Latitude")
            axis.legend(frameon=False, fontsize=8, loc="lower left")

    bottom = fig.add_subplot(grid[1, :])
    main = summary.loc[summary["variant"] == "w_upward_positive"].set_index("event")
    regions = ["equatorial_west", "equatorial_central", "equatorial_east", "north_of_5N", "south_of_5S", "inactive"]
    labels = ["Eq. west", "Eq. central", "Eq. east", "North of 5°N", "South of 5°S", "Inactive / unresolved"]
    region_colors = ["#542788", "#998ec3", "#d8daeb", "#1b7837", "#d95f02", "#bdbdbd"]
    x = np.arange(len(events), dtype=float)
    bottom_values = np.zeros(len(events), dtype=float)
    for region, label, color in zip(regions, labels, region_colors, strict=True):
        if region == "inactive":
            values = np.asarray(
                [1.0 - main.loc[event, "active_fraction_weight"] for event in events]
            )
        else:
            values = np.asarray([main.loc[event, f"weight_fraction_{region}"] for event in events])
        bottom.bar(x, values, bottom=bottom_values, width=0.62, label=label, color=color)
        bottom_values += values
    bottom.set_xticks(x, [str(event) for event in events])
    bottom.set_ylim(0.0, 1.0)
    bottom.set_ylabel("Fraction of release T′ weight")
    bottom.set_title("January endpoint partition (main vertical convention)")
    bottom.legend(ncol=6, frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    fig.suptitle(
        "SODA3 positive-temperature-anomaly backward connectivity: January to late June",
        fontsize=14,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.955,
        "Release T′ relative to leave-event-out June linear baseline, 1980–2024; marker size ∝ T′ weight",
        ha="center",
        va="top",
        fontsize=9,
        color="0.3",
    )
    fig.savefig(FIGURE_PNG, dpi=220, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def plot_sensitivity(summary: pd.DataFrame) -> None:
    events = sorted(summary["event"].unique())
    variants = [
        ("w_upward_positive", "w upward (+)"),
        ("no_vertical_velocity", "w = 0"),
        ("w_downward_positive", "w downward (+)"),
    ]
    colors = {1997: "#b2182b", 2015: "#ef8a62", 2023: "#2166ac"}
    metrics = [
        ("weighted_median_eastward_displacement_deg", "Median eastward displacement (°)", 1.0),
        ("weight_fraction_equatorial_central", "Equatorial-central source weight (%)", 100.0),
        ("active_fraction_weight", "Resolved release weight (%)", 100.0),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 3.7), constrained_layout=True)
    x = np.arange(len(variants), dtype=float)
    for axis, (metric, label, scale) in zip(axes, metrics, strict=True):
        for event in events:
            event_rows = summary.loc[summary["event"] == event].set_index("variant")
            values = np.asarray([event_rows.loc[key, metric] * scale for key, _ in variants])
            axis.plot(
                x,
                values,
                marker="o",
                ms=5,
                color=colors.get(event, "0.4"),
                label=str(event),
            )
        axis.set_xticks(x, [label for _, label in variants], rotation=18, ha="right")
        axis.set_ylabel(label)
        axis.grid(axis="y", color="0.9", lw=0.8)
    axes[0].axhline(0.0, color="0.4", lw=0.8)
    axes[0].set_title("Path direction")
    axes[1].set_title("Source partition")
    axes[2].set_title("Numerical retention")
    axes[2].legend(frameon=False, title="Event")
    fig.suptitle(
        "Sensitivity to SODA3 wt sign convention\n"
        "Release T′: leave-event-out June linear baseline, 1980–2024",
        fontweight="bold",
    )
    fig.savefig(SENSITIVITY_PNG, dpi=220, bbox_inches="tight")
    fig.savefig(SENSITIVITY_PDF, bbox_inches="tight")
    plt.close(fig)


def fmt(value: float, digits: int = 1) -> str:
    return "NA" if not np.isfinite(value) else f"{value:.{digits}f}"


def write_report(
    summary: pd.DataFrame,
    args: argparse.Namespace,
    snapshots_per_event: dict[int, int],
    field_qa: dict[int, dict[str, float]],
) -> None:
    main = summary.loc[summary["variant"] == "w_upward_positive"].set_index("event")
    rows = []
    for event in args.years:
        row = main.loc[event]
        rows.append(
            "| {event} | {n} | {tprime} | {active} | {west} | {central} | {east} | {north} | {south} | {dx} |".format(
                event=event,
                n=int(row["particle_count"]),
                tprime=fmt(row["weighted_mean_release_temp_anomaly_c"], 2),
                active=fmt(100.0 * row["active_fraction_weight"]),
                west=fmt(100.0 * row["weight_fraction_equatorial_west"]),
                central=fmt(100.0 * row["weight_fraction_equatorial_central"]),
                east=fmt(100.0 * row["weight_fraction_equatorial_east"]),
                north=fmt(100.0 * row["weight_fraction_north_of_5N"]),
                south=fmt(100.0 * row["weight_fraction_south_of_5S"]),
                dx=fmt(row["weighted_median_eastward_displacement_deg"]),
            )
        )
    sensitivity_lines = []
    for event in args.years:
        event_rows = summary.loc[summary["event"] == event]
        west_values = 100.0 * event_rows["weight_fraction_equatorial_west"]
        central_values = 100.0 * event_rows["weight_fraction_equatorial_central"]
        sensitivity_lines.append(
            f"- {event}：西部端点 {fmt(west_values.min())}–{fmt(west_values.max())}%；"
            f"中部端点 {fmt(central_values.min())}–{fmt(central_values.max())}%（三种垂向处理范围）。"
        )
    source_counts = "、".join(f"{year}年{snapshots_per_event[year]}个" for year in args.years)
    qa_lines = [
        f"- {year}：各快照99百分位的最大值为 |u|={field_qa[year]['u_p99']:.2f} m/s、"
        f"|v|={field_qa[year]['v_p99']:.2f} m/s、|w|={field_qa[year]['w_p99'] * SECONDS_PER_DAY:.2f} m/day；"
        f"东部赤道50—150 m平均 w={field_qa[year]['east_eq_w_mean_m_day']:+.2f} m/day。"
        for year in args.years
    ]
    report = f"""# SODA3正温度异常三维离线粒子连通性：三问题最小试验

## 结论先行

三个科学问题保持不变，但本试验**不使用H20或20°C阈值**。它从每个事件6月末东太平洋（140°W—100°W、约5°S—5°N、15—160 m）的正温度异常格点释放粒子，以 `max(T′,0) × cos(lat) × Δz` 加权，使用SODA3.15.2五日三维 `u/v/wt` 场反向积分到1月初。这里 `T′` 是相对于1980—2024同月、排除事件年后线性趋势预期值的偏差。

这仍是一个**技术性、可证伪的连通性试验**，不是热量闭合。主方案把海洋 `w` 解释为向上为正，并显式给出无垂向速度和反号敏感性。

| 事件 | 粒子数 | 释放加权T′(°C) | 有效权重(%) | 赤道西部(%) | 赤道中部(%) | 赤道东部(%) | 5°N以北(%) | 5°S以南(%) | 中位东向位移(°) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

表中的“东向位移”定义为6月释放经度减去1月源经度，正值表示粒子在正向时间内总体向东。区域比例的分母是全部正温度异常权重，因此失活粒子不会被悄悄归一化掉。

## 三个固定问题与不使用H20后的主线

### 问题一：异常暖水是否、以及通过什么路径到达东太平洋？

本试验直接回答路径的最小部分：6月末东部正 `T′` 粒子的1月上游位置在哪里、群体是否表现为正向东移。它把欧拉热输送与同一批数值粒子的连通性分开检验。只有在完整五日场、基准和垂向处理下方向都稳定，才可把路径证据纳入主结论。

### 问题二：到达后的异常热量如何在北向、南向、散热和储存之间分配？

不再以H20为核心后，主体应改为固定深度层热含量异常：`OHC′ = ρcp∫_0^300m (T−T_expected) dz`。边界项使用相对于同月趋势基准的异常焓输送，并在闭合箱体内执行净体积输送校正；否则 `vT` 会受参考温度和质量不平衡影响。表面项用净向下热通量异常，剩余项明确保留垂向交换、混合、同化增量和离散误差。本次反向轨迹不回答该分配；下一步需从到达面和5°N/5°S边界正向释放。

### 问题三：为什么相似的东部增暖会产生不同命运？

继续检验“到达构型—大气响应—海洋出口”：用 `OHC′`重心、垂向 `T′`结构、D20/SSH和粒子端点构型描述海洋初态，再与风应力、降水/OLR及表面热通量配对。1997/2015/2023的轨迹差异只能作为候选前置条件，不能由粒子本身推出海气因果。

## 设计与物理QA

- 原始资料：官方SODA3.15.2五日再分析；1997和2015为CDF-2，2023为HDF5，二者通过同一坐标/插值流程。
- 温度异常基准：本地SODA3月平均三维温度，1980—2024同月逐格点线性预期；每个事件排除自身年份。释放时刻是6月末五日场，因此该试验仍包含“月基准—五日瞬时场”的时间尺度不匹配。
- 试验抽样：每隔 `{args.stride}` 个五日文件取场，{source_counts}；场间线性时间插值，RK2步长 `{args.step_hours:g}` 小时。
- 域：145°E—90°W、8°S—8°N、约5—200 m。越出水平域、深度域或遇到不可插值速度的粒子保留为失活，不删除。
- 速度单位：`u/v/wt` 均为m/s；SODA深度坐标明确为向下为正。`wt`缺少明确正方向属性，因此主方案采用海洋学常规“向上为正”，并把无`w`和反号作为必要敏感性。
- 释放条件：`T′>{MINIMUM_RELEASE_ANOMALY_C:.2f}°C`；权重为 `T′ × cos(lat) × Δz`。这是相对异常热含量的比例权重，没有乘完整格点面积，不能直接解释为焦耳。

区域场速度量级检查（每个快照先取99百分位，再报事件内最大值）：

{chr(10).join(qa_lines)}

三个事件的东部赤道层平均 `wt` 均为正，与该区典型上升流方向一致，因而经验上支持主方案的“正值向上”；但这不是缺失元数据的替代证明，反号敏感性仍必须保留。

## 垂向符号敏感性

{chr(10).join(sensitivity_lines) if sensitivity_lines else '- 本次跳过。'}

如果主结论在三种垂向处理间改变符号，说明当前试验尚不能升级为科学结论；应先确认SODA `wt`定义或改用被动示踪器。

## 不能越过的解释边界

1. 正 `T′` 仅在释放时刻赋权；沿途温度异常并未作为守恒示踪量积分，因此“初始异常热权重”不能被解释为沿轨迹保持不变的焦耳。
2. 六月月趋势基准与六月末五日场不完全同尺度。完整试验应构建同五日历日气候态，或至少比较月基准与五日气候态结果。
3. 默认 `--stride {args.stride}` 是低成本烟雾试验，时间采样约为月尺度。只有以 `--stride 1` 重跑并证明分区稳定后，才可称为完整五日离线轨迹。
4. 离线粒子没有显式扩散、夹卷、同化增量或表面浮力改变，不能复现被动示踪浓度，也不能闭合焦耳去向。
5. 反向轨迹对速度误差和混合不可逆性敏感。本文只把群体分配当作连通性证据，不把单条轨迹当成真实水团履历。
6. 仅三个个例不支持显著性推断。它的价值是决定是否值得扩展，而不是给出总体频率。

## 产物

- 主图（PNG/PDF）：`{FIGURE_PNG.relative_to(ROOT)}`；`{FIGURE_PDF.relative_to(ROOT)}`
- 垂向敏感性图（PNG/PDF）：`{SENSITIVITY_PNG.relative_to(ROOT)}`；`{SENSITIVITY_PDF.relative_to(ROOT)}`
- 端点：`{ENDPOINT_CSV.relative_to(ROOT)}`
- 轨迹：`{TRAJECTORY_CSV.relative_to(ROOT)}`
- 汇总：`{SUMMARY_CSV.relative_to(ROOT)}`
- 垂向敏感性：`{SENSITIVITY_CSV.relative_to(ROOT)}`
- 可复现脚本：`scripts/pilot_soda3_lagrangian_connectivity.py`
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.step_hours <= 0.0:
        raise ValueError("step-hours must be positive")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_files = list_event_files(args.years)
    session = requests.Session()
    main_endpoints: list[pd.DataFrame] = []
    main_trajectories: list[pd.DataFrame] = []
    summary_rows: list[dict[str, float | int | str]] = []
    snapshots_per_event: dict[int, int] = {}
    field_qa: dict[int, dict[str, float]] = {}

    variants = [("w_upward_positive", -1.0)]
    if not args.skip_sensitivity:
        variants.extend([("no_vertical_velocity", 0.0), ("w_downward_positive", 1.0)])

    for year in args.years:
        selected = _selected_files(all_files[year], args.stride)
        snapshots_per_event[year] = len(selected)
        metadata: dict[str, object] = {}
        snapshots = [
            get_snapshot(
                year,
                timestamp,
                url,
                session,
                metadata,
                need_temp=index == len(selected) - 1,
                force=args.force_cache,
            )
            for index, (timestamp, url) in enumerate(selected)
        ]
        field_qa[year] = {
            f"{name}_p99": max(
                float(np.nanpercentile(np.abs(getattr(snapshot, name)), 99.0))
                for snapshot in snapshots
            )
            for name in ("u", "v", "w")
        }
        east_w_values = []
        for snapshot in snapshots:
            z_mask = (snapshot.z_w >= 50.0) & (snapshot.z_w <= 150.0)
            lat_mask = (snapshot.lat_t >= -2.0) & (snapshot.lat_t <= 2.0)
            lon_mask = (snapshot.lon_t >= 220.0) & (snapshot.lon_t <= 260.0)
            east_w_values.append(
                float(
                    np.nanmean(snapshot.w[np.ix_(z_mask, lat_mask, lon_mask)])
                    * SECONDS_PER_DAY
                )
            )
        field_qa[year]["east_eq_w_mean_m_day"] = float(np.mean(east_w_values))
        expected_field = load_temperature_expected_field(
            year,
            snapshots[-1].timestamp.month,
        )
        seeds = seed_particles(snapshots[-1], year, expected_field)
        print(
            f"track {year}: {len(seeds)} positive-temperature-anomaly particles",
            flush=True,
        )
        for variant, vertical_sign in variants:
            endpoints, trajectory = track_event(
                year,
                snapshots,
                seeds,
                step_hours=args.step_hours,
                w_to_depth_sign=vertical_sign,
                retain_trajectory=variant == "w_upward_positive",
            )
            endpoints["variant"] = variant
            summary_rows.append(summarize_endpoints(endpoints, variant=variant))
            if variant == "w_upward_positive":
                main_endpoints.append(endpoints)
                main_trajectories.append(trajectory)

    endpoint_frame = pd.concat(main_endpoints, ignore_index=True)
    trajectory_frame = pd.concat(main_trajectories, ignore_index=True)
    summary_frame = pd.DataFrame(summary_rows).sort_values(["event", "variant"])
    sensitivity_frame = summary_frame.copy()
    endpoint_frame.to_csv(ENDPOINT_CSV, index=False)
    trajectory_frame.to_csv(TRAJECTORY_CSV, index=False)
    summary_frame.loc[summary_frame["variant"] == "w_upward_positive"].to_csv(
        SUMMARY_CSV,
        index=False,
    )
    sensitivity_frame.to_csv(SENSITIVITY_CSV, index=False)
    plot_results(endpoint_frame, trajectory_frame, summary_frame)
    plot_sensitivity(summary_frame)
    write_report(summary_frame, args, snapshots_per_event, field_qa)
    print(summary_frame.to_string(index=False), flush=True)
    print(f"Wrote {REPORT_MD}", flush=True)


if __name__ == "__main__":
    main()
