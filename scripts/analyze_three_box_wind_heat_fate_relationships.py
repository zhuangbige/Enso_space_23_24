#!/usr/bin/env python3
"""Relate three-box Pacific heat-loss pathways to wind anomalies.

All public heat-fate terms use a positive-outward convention.  The script
reads the audited, fixed-depth SODA3 OHC-anomaly budget and treats its
residual as an audit term rather than a physical heat-loss mechanism.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
EVENTS = (
    1982,
    1986,
    1991,
    1994,
    1997,
    2002,
    2004,
    2006,
    2009,
    2015,
    2018,
    2019,
    2023,
)
BOXES = {
    "west": (160.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 280.0),
}
PHASE_MONTHS = {
    "arrival_Jan_Jun": (0, 1, 6),
    "redistribution_Jul_Dec": (0, 7, 12),
    "decay_Jan_May_next": (1, 1, 5),
}

DERIVED = Path("data/derived/research_2026")
BUDGET_EVENTS = DERIVED / "soda3_three_box_ohc_anomaly_budget_events.csv"
ERA5_U10 = Path("data/raw/era5/era5_monthly_10m_wind_pmm_1deg_1982_2025.nc")
ERA5_TX_DIR = Path("data/raw/era5/coupling_monthly_1deg")
JIANG_EVENTS = DERIVED / "jiang_ne_wind_h20_exit_event_table.csv"
EARTH_RADIUS_M = 6_371_000.0
WIND_BASELINE = (1982, 2014)
WIND_WINDOWS = {
    "MAM": (0, 3, 5),
    "MJJ": (0, 5, 7),
    "arrival_Jan_Jun": (0, 1, 6),
    "redistribution_Jul_Dec": (0, 7, 12),
    "decay_Jan_May_next": (1, 1, 5),
}

HEAT_FATE_COLUMNS = (
    "west_face_loss_zj",
    "east_face_loss_zj",
    "southward_loss_zj",
    "northward_loss_zj",
    "surface_loss_zj",
    "storage_loss_zj",
)


def discover_input_root() -> Path:
    """Locate the data-bearing main project from a linked worktree."""

    candidates: list[Path] = []
    configured = os.environ.get("MARYLAND_INPUT_ROOT")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(ROOT)
    if ROOT.parent.name == ".worktrees":
        candidates.append(ROOT.parents[1])
    for candidate in candidates:
        if (
            (candidate / BUDGET_EVENTS).exists()
            and (candidate / ERA5_U10).exists()
            and (candidate / ERA5_TX_DIR).exists()
        ):
            return candidate.resolve()
    rendered = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Could not locate {BUDGET_EVENTS} under {rendered}")


def positive_outward_heat_fate(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert face, surface, and storage terms to positive loss from a box."""

    required = {
        "west_theta_heat_in_zj",
        "east_theta_heat_in_zj",
        "south_theta_heat_in_zj",
        "north_theta_heat_in_zj",
        "surface_zj",
        "storage_change_zj",
        "residual_zj",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing heat-fate inputs: {sorted(missing)}")
    output = frame.copy()
    output["west_face_loss_zj"] = -output["west_theta_heat_in_zj"]
    output["east_face_loss_zj"] = -output["east_theta_heat_in_zj"]
    output["southward_loss_zj"] = -output["south_theta_heat_in_zj"]
    output["northward_loss_zj"] = -output["north_theta_heat_in_zj"]
    output["surface_loss_zj"] = -output["surface_zj"]
    output["storage_loss_zj"] = -output["storage_change_zj"]
    output["residual_audit_zj"] = output["residual_zj"]
    return output


def validate_heat_fate(frame: pd.DataFrame) -> dict[str, object]:
    """Enforce exact event/phase/box coverage and finite physical terms."""

    key = ["event_year", "phase", "box"]
    if frame.duplicated(key).any():
        duplicates = frame.loc[frame.duplicated(key, keep=False), key]
        raise ValueError(f"Duplicate heat-fate rows:\n{duplicates}")
    expected_rows = len(EVENTS) * len(PHASE_MONTHS) * len(BOXES)
    if len(frame) != expected_rows:
        raise ValueError(f"Expected {expected_rows} heat-fate rows, found {len(frame)}")
    if set(frame.event_year) != set(EVENTS):
        raise ValueError("Heat-fate table does not contain the exact event sample")
    if set(frame.phase) != set(PHASE_MONTHS):
        raise ValueError("Heat-fate table does not contain the exact phases")
    if set(frame.box) != set(BOXES):
        raise ValueError("Heat-fate table does not contain the exact boxes")
    missing = int(frame[list(HEAT_FATE_COLUMNS)].isna().sum().sum())
    if missing:
        raise ValueError(f"Heat-fate table contains {missing} missing physical values")
    return {
        "rows": int(len(frame)),
        "events": sorted(int(value) for value in frame.event_year.unique()),
        "phases": list(PHASE_MONTHS),
        "boxes": list(BOXES),
        "missing_physical_values": missing,
    }


def load_heat_fate_events(input_root: Path | None = None) -> pd.DataFrame:
    """Load audited event budgets and expose positive-outward heat fates."""

    root = discover_input_root() if input_root is None else Path(input_root)
    source = pd.read_csv(root / BUDGET_EVENTS)
    source["phase"] = source["phase"].replace(
        {"post_Jul_Dec": "redistribution_Jul_Dec"}
    )
    selected = source.loc[
        source.event_year.isin(EVENTS)
        & source.box.isin(BOXES)
        & source.phase.isin(PHASE_MONTHS)
    ].copy()
    output = positive_outward_heat_fate(selected)
    output = output.sort_values(["event_year", "phase", "box"]).reset_index(drop=True)
    validate_heat_fate(output)
    return output


def synthetic_monthly_signal(start_year: int, end_year: int) -> pd.DataFrame:
    """Return a deterministic trend-plus-calendar-month signal for tests."""

    rows = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "value": 0.17 * year + 2.5 * month,
                }
            )
    return pd.DataFrame(rows)


def same_month_linear_anomaly(
    frame: pd.DataFrame,
    value_column: str,
    baseline: tuple[int, int] = WIND_BASELINE,
) -> pd.Series:
    """Remove a calendar-month linear expectation and preserve row order."""

    required = {"year", "month", value_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing anomaly columns: {sorted(missing)}")
    output = pd.Series(np.nan, index=frame.index, dtype=float)
    for month, group in frame.groupby("month", sort=False):
        base = group.loc[group.year.between(*baseline), ["year", value_column]].dropna()
        if len(base) < 3:
            raise ValueError(f"Month {month} has fewer than three baseline values")
        slope, intercept = np.polyfit(
            base.year.to_numpy(dtype=float),
            base[value_column].to_numpy(dtype=float),
            1,
        )
        expected = intercept + slope * group.year.to_numpy(dtype=float)
        output.loc[group.index] = group[value_column].to_numpy(dtype=float) - expected
    return output


def _normalize_field(field: xr.DataArray) -> xr.DataArray:
    rename = {}
    for source, target in (
        ("valid_time", "time"),
        ("latitude", "lat"),
        ("longitude", "lon"),
    ):
        if source in field.dims or source in field.coords:
            rename[source] = target
    output = field.rename(rename)
    if not {"lat", "lon"}.issubset(output.coords):
        raise ValueError("Meteorological field requires latitude and longitude")
    output = output.assign_coords(lon=output.lon % 360.0).sortby("lon").sortby("lat")
    return output


def cosine_box_mean(
    field: xr.DataArray,
    lat0: float,
    lat1: float,
    lon0: float,
    lon1: float,
) -> xr.DataArray:
    """Return a cosine-latitude weighted mean from a 0–360 field."""

    normalized = _normalize_field(field)
    selected = normalized.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if selected.sizes.get("lat", 0) == 0 or selected.sizes.get("lon", 0) == 0:
        raise ValueError(f"Empty box lat={lat0}:{lat1}, lon={lon0}:{lon1}")
    weights = np.cos(np.deg2rad(selected.lat))
    dimensions = tuple(dimension for dimension in ("lat", "lon") if dimension in selected.dims)
    return selected.weighted(weights).mean(dimensions, skipna=True)


def _time_frame(times: xr.DataArray | np.ndarray) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(np.asarray(times)))
    return pd.DataFrame({"year": index.year, "month": index.month})


def _load_u10_indices(input_root: Path) -> pd.DataFrame:
    with xr.open_dataset(input_root / ERA5_U10, engine="netcdf4", chunks=None) as dataset:
        u10 = _normalize_field(dataset.u10).load()
        v10 = _normalize_field(dataset.v10).load()
    frame = _time_frame(u10.time.values)
    speed = np.hypot(u10, v10)
    for box, (lon0, lon1) in BOXES.items():
        frame[f"{box}_u10_raw_ms"] = cosine_box_mean(u10, -10.0, 5.0, lon0, lon1).values
        frame[f"{box}_v10_raw_ms"] = cosine_box_mean(v10, -10.0, 5.0, lon0, lon1).values
        frame[f"{box}_wind_speed_raw_ms"] = cosine_box_mean(
            speed, -10.0, 5.0, lon0, lon1
        ).values
    frame["cwp_u10_raw_ms"] = cosine_box_mean(u10, -5.0, 5.0, 140.0, 200.0).values
    return frame


def _load_eastward_stress(input_root: Path) -> xr.DataArray:
    month_fields = []
    for month in range(1, 13):
        paths = sorted(
            (input_root / ERA5_TX_DIR).glob(
                f"era5_coupling_part*_m{month:02d}_1982_2025_1p0deg.nc"
            )
        )
        if len(paths) != 2:
            raise FileNotFoundError(
                f"Expected two eastward-stress files for month {month:02d}, found {paths}"
            )
        pieces = []
        for path in paths:
            with xr.open_dataset(path, engine="netcdf4", chunks=None) as dataset:
                pieces.append(_normalize_field(dataset.avg_iews).load())
        field = xr.concat(pieces, dim="lon").sortby("lon")
        _, unique = np.unique(field.lon.values, return_index=True)
        month_fields.append(field.isel(lon=np.sort(unique)))
    return xr.concat(month_fields, dim="time").sortby("time")


def _load_stress_indices(input_root: Path) -> pd.DataFrame:
    tau_x = _load_eastward_stress(input_root)
    frame = _time_frame(tau_x.time.values)
    curl_tx = -tau_x.differentiate("lat") / (EARTH_RADIUS_M * np.pi / 180.0)
    for box, (lon0, lon1) in BOXES.items():
        frame[f"{box}_tau_x_raw_nm2"] = cosine_box_mean(
            tau_x, -10.0, 5.0, lon0, lon1
        ).values
        frame[f"{box}_tau_x_5n_raw_nm2"] = cosine_box_mean(
            tau_x, 4.0, 6.0, lon0, lon1
        ).values
        frame[f"{box}_tau_x_10s_raw_nm2"] = cosine_box_mean(
            tau_x, -10.0, -8.0, lon0, lon1
        ).values
        frame[f"{box}_north_curl_tx_raw_1e8_nm3"] = (
            cosine_box_mean(curl_tx, 0.0, 5.0, lon0, lon1).values * 1.0e8
        )
        frame[f"{box}_south_curl_tx_raw_1e8_nm3"] = (
            cosine_box_mean(curl_tx, -10.0, -5.0, lon0, lon1).values * 1.0e8
        )
    frame["cwp_tau_x_raw_nm2"] = cosine_box_mean(
        tau_x, -5.0, 5.0, 140.0, 200.0
    ).values
    return frame


@lru_cache(maxsize=2)
def _cached_monthly_wind_indices(input_root_text: str) -> pd.DataFrame:
    input_root = Path(input_root_text)
    frame = _load_u10_indices(input_root).merge(
        _load_stress_indices(input_root),
        on=["year", "month"],
        validate="one_to_one",
    )
    for raw_column in [column for column in frame if "_raw_" in column]:
        anomaly_column = raw_column.replace("_raw_", "_anom_")
        frame[anomaly_column] = same_month_linear_anomaly(frame, raw_column)
    return frame.sort_values(["year", "month"]).reset_index(drop=True)


def load_monthly_wind_indices(input_root: Path | None = None) -> pd.DataFrame:
    root = discover_input_root() if input_root is None else Path(input_root)
    return _cached_monthly_wind_indices(str(root.resolve())).copy()


def build_event_wind_table(input_root: Path | None = None) -> pd.DataFrame:
    """Aggregate five fixed wind windows for the 13 event years."""

    root = discover_input_root() if input_root is None else Path(input_root)
    monthly = load_monthly_wind_indices(root)
    metric_columns = [column for column in monthly if column not in {"year", "month"} and "_anom_" in column]
    jiang = pd.read_csv(root / JIANG_EVENTS).set_index("year")
    rows = []
    for event_year in EVENTS:
        if event_year not in jiang.index:
            raise ValueError(f"Missing Jiang wind index for {event_year}")
        for window, (year_offset, month0, month1) in WIND_WINDOWS.items():
            selected = monthly.loc[
                monthly.year.eq(event_year + year_offset)
                & monthly.month.between(month0, month1)
            ]
            expected = month1 - month0 + 1
            if len(selected) != expected:
                raise ValueError(
                    f"{event_year} {window} contains {len(selected)} months, expected {expected}"
                )
            row: dict[str, float | int | str] = {
                "event_year": event_year,
                "window": window,
                "target_year": event_year + year_offset,
                "month_start": month0,
                "month_end": month1,
                "jiang_ne925_mjj_ms": float(jiang.loc[event_year, "ne925_mjj_ms"]),
            }
            row.update({column: float(selected[column].mean()) for column in metric_columns})
            rows.append(row)
    output = pd.DataFrame(rows)
    if len(output) != len(EVENTS) * len(WIND_WINDOWS):
        raise ValueError("Incomplete event wind table")
    return output
