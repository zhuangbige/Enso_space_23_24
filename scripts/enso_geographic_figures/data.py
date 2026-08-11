"""Load and validate the authoritative inputs used by the figure atlas."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    BUDGET_EVENT_PATH,
    ENDPOINT_PATH,
    EVENTS,
    HOVMOLLER_PATH,
    TRAJECTORY_PATH,
)


def _read_csv(path: Path, required: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} missing columns: {sorted(missing)}")
    return frame


@lru_cache(maxsize=1)
def load_budget_events() -> pd.DataFrame:
    required = {
        "event_year",
        "phase",
        "box",
        "storage_change_zj",
        "west_theta_heat_in_zj",
        "east_theta_heat_in_zj",
        "northward_output_zj",
        "southward_output_zj",
        "surface_loss_zj",
        "residual_zj",
    }
    frame = _read_csv(BUDGET_EVENT_PATH, required)
    keys = ["event_year", "phase", "box"]
    if frame.duplicated(keys).any():
        raise ValueError("Budget table contains duplicate event/phase/box keys")
    numeric = sorted(required - {"event_year", "phase", "box"})
    if not np.isfinite(frame[numeric].to_numpy(dtype=float)).all():
        raise ValueError("Budget table contains non-finite headline values")
    return frame


def extract_event_budget(event: int, phase: str, box: str) -> dict[str, float]:
    frame = load_budget_events()
    selected = frame.loc[
        (frame["event_year"] == event)
        & (frame["phase"] == phase)
        & (frame["box"] == box)
    ]
    if len(selected) != 1:
        raise ValueError(
            f"Expected one budget row for {event}/{phase}/{box}, found {len(selected)}"
        )
    record = selected.iloc[0].to_dict()
    return {
        key: float(value) if isinstance(value, (int, float, np.number)) else value
        for key, value in record.items()
    }


@lru_cache(maxsize=1)
def load_trajectory_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    trajectories = _read_csv(
        TRAJECTORY_PATH,
        {"event", "date", "particle_id", "lon", "lat", "depth_m", "active"},
    )
    endpoints = _read_csv(
        ENDPOINT_PATH,
        {
            "event",
            "particle_id",
            "release_lon",
            "release_lat",
            "source_lon",
            "source_lat",
            "heat_anomaly_weight",
            "zonal_displacement_deg",
            "active",
        },
    )
    if not trajectories["lon"].between(0.0, 360.0).all():
        raise ValueError("Trajectory longitude lies outside 0-360 degrees")
    if not trajectories["lat"].between(-90.0, 90.0).all():
        raise ValueError("Trajectory latitude lies outside -90 to 90 degrees")
    if tuple(sorted(trajectories["event"].unique())) != EVENTS:
        raise ValueError("Trajectory file does not contain the three highlighted events")
    if tuple(sorted(endpoints["event"].unique())) != EVENTS:
        raise ValueError("Endpoint file does not contain the three highlighted events")
    if (endpoints["heat_anomaly_weight"] < 0).any():
        raise ValueError("Heat-anomaly weights must be non-negative")
    trajectories = trajectories.copy()
    endpoints = endpoints.copy()
    trajectories["date"] = pd.to_datetime(trajectories["date"])
    return trajectories, endpoints


@lru_cache(maxsize=1)
def load_hovmoller() -> pd.DataFrame:
    frame = _read_csv(
        HOVMOLLER_PATH,
        {"event_year", "relative_month", "time", "lon_deg_e", "ohc300_anom_gjm2"},
    )
    if tuple(sorted(frame["event_year"].unique())) != EVENTS:
        raise ValueError("Hovmoller table does not contain the three highlighted events")
    if not np.isfinite(frame["ohc300_anom_gjm2"]).all():
        raise ValueError("Hovmoller table contains non-finite OHC anomalies")
    frame = frame.copy()
    frame["time"] = pd.to_datetime(frame["time"])
    return frame


def to_display_longitude(lon_deg_e: np.ndarray) -> np.ndarray:
    values = np.asarray(lon_deg_e, dtype=float)
    return np.where(values > 180.0, values - 360.0, values)
