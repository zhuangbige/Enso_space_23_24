#!/usr/bin/env python3
"""Relate three-box Pacific heat-loss pathways to wind anomalies.

All public heat-fate terms use a positive-outward convention.  The script
reads the audited, fixed-depth SODA3 OHC-anomaly budget and treats its
residual as an audit term rather than a physical heat-loss mechanism.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(ROOT / "outputs/research_2026/mplconfig"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle

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
OUTPUT_DIR = Path("outputs/research_2026/three_box_wind_heat_fate_relationships")
EVENT_HEAT_NAME = "three_box_wind_heat_fate_events.csv"
WIND_NAME = "three_box_wind_indices.csv"
RELATIONSHIP_NAME = "three_box_wind_heat_prespecified_relationships.csv"
DISCOVERY_NAME = "three_box_wind_heat_discovery_matrix.csv"
AUDIT_NAME = "three_box_wind_heat_fate_audit.json"
REPORT_NAME = "THREE_BOX_WIND_HEAT_FATE_CN.md"
FATE_STEM = "three_box_2015_2023_heat_fate"
MATRIX_STEM = "three_box_wind_heat_relationship_matrix"
SCATTER_STEM = "three_box_wind_heat_scatter"

EVENT_COLORS = {1997: "#2F6FA5", 2015: "#D97706", 2023: "#0F8F83"}
BOX_COLORS = {"west": "#6BAED6", "central": "#4292C6", "east": "#2171B5"}

HEAT_FATE_COLUMNS = (
    "west_face_loss_zj",
    "east_face_loss_zj",
    "southward_loss_zj",
    "northward_loss_zj",
    "surface_loss_zj",
    "storage_loss_zj",
)


@dataclass(frozen=True)
class PipelineOutputs:
    event_heat_csv: Path
    wind_csv: Path
    relationship_csv: Path
    discovery_csv: Path
    audit_json: Path
    fate_png: Path
    fate_pdf: Path
    matrix_png: Path
    matrix_pdf: Path
    scatter_png: Path
    scatter_pdf: Path
    report_md: Path


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
    with xr.open_dataset(input_root / ERA5_U10, engine="h5netcdf", chunks=None) as dataset:
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
            with xr.open_dataset(path, engine="h5netcdf", chunks=None) as dataset:
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


def _residualize(values: np.ndarray, control: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    control = np.asarray(control, dtype=float)
    if np.nanstd(control) < 1.0e-12:
        return values - np.nanmean(values)
    design = np.column_stack([np.ones(len(control)), control])
    coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    return values - design @ coefficients


def partial_correlation(
    x: np.ndarray | pd.Series,
    y: np.ndarray | pd.Series,
    control: np.ndarray | pd.Series,
) -> float:
    """Return Pearson correlation after linear removal of one control."""

    x_array = np.asarray(x, dtype=float)
    y_array = np.asarray(y, dtype=float)
    control_array = np.asarray(control, dtype=float)
    valid = np.isfinite(x_array) & np.isfinite(y_array) & np.isfinite(control_array)
    if valid.sum() < 4:
        return float("nan")
    x_residual = _residualize(x_array[valid], control_array[valid])
    y_residual = _residualize(y_array[valid], control_array[valid])
    if np.std(x_residual) < 1.0e-12 or np.std(y_residual) < 1.0e-12:
        return float("nan")
    return float(np.corrcoef(x_residual, y_residual)[0, 1])


def relationship_statistics(
    x: np.ndarray | pd.Series,
    y: np.ndarray | pd.Series,
    control: np.ndarray | pd.Series,
) -> dict[str, float | int | bool]:
    """Calculate raw, rank, controlled, slope, and leave-one-event statistics."""

    x_array = np.asarray(x, dtype=float)
    y_array = np.asarray(y, dtype=float)
    control_array = np.asarray(control, dtype=float)
    valid = np.isfinite(x_array) & np.isfinite(y_array) & np.isfinite(control_array)
    x_array = x_array[valid]
    y_array = y_array[valid]
    control_array = control_array[valid]
    if len(x_array) < 4 or np.std(x_array) < 1.0e-12 or np.std(y_array) < 1.0e-12:
        return {
            "n": int(len(x_array)),
            "pearson_r": float("nan"),
            "pearson_p": float("nan"),
            "spearman_r": float("nan"),
            "spearman_p": float("nan"),
            "partial_r": float("nan"),
            "partial_spearman_r": float("nan"),
            "slope_physical": float("nan"),
            "slope_standardized": float("nan"),
            "loeo_r_min": float("nan"),
            "loeo_r_max": float("nan"),
            "sign_agreement": False,
            "loeo_sign_stable": False,
        }
    pearson = stats.pearsonr(x_array, y_array)
    spearman = stats.spearmanr(x_array, y_array)
    partial = partial_correlation(x_array, y_array, control_array)
    partial_rank = partial_correlation(
        stats.rankdata(x_array), stats.rankdata(y_array), stats.rankdata(control_array)
    )
    slope = stats.linregress(x_array, y_array).slope
    loeo = []
    for index in range(len(x_array)):
        keep = np.arange(len(x_array)) != index
        value = partial_correlation(x_array[keep], y_array[keep], control_array[keep])
        if np.isfinite(value):
            loeo.append(value)
    loeo_min = float(min(loeo)) if loeo else float("nan")
    loeo_max = float(max(loeo)) if loeo else float("nan")
    sign_agreement = bool(
        np.sign(pearson.statistic) == np.sign(spearman.statistic)
        and np.sign(pearson.statistic) == np.sign(partial)
    )
    loeo_stable = bool(
        loeo
        and (
            (partial > 0 and loeo_min > 0)
            or (partial < 0 and loeo_max < 0)
        )
    )
    return {
        "n": int(len(x_array)),
        "pearson_r": float(pearson.statistic),
        "pearson_p": float(pearson.pvalue),
        "spearman_r": float(spearman.statistic),
        "spearman_p": float(spearman.pvalue),
        "partial_r": float(partial),
        "partial_spearman_r": float(partial_rank),
        "slope_physical": float(slope),
        "slope_standardized": float(pearson.statistic),
        "loeo_r_min": loeo_min,
        "loeo_r_max": loeo_max,
        "sign_agreement": sign_agreement,
        "loeo_sign_stable": loeo_stable,
    }


def _pairing_specs(box: str) -> list[tuple[str, str, str]]:
    return [
        ("west_face_loss_zj", f"{box}_tau_x_anom_nm2", "zonal_faces"),
        ("west_face_loss_zj", "cwp_u10_anom_ms", "zonal_faces"),
        ("east_face_loss_zj", f"{box}_tau_x_anom_nm2", "zonal_faces"),
        ("east_face_loss_zj", "cwp_u10_anom_ms", "zonal_faces"),
        ("northward_loss_zj", f"{box}_tau_x_5n_anom_nm2", "north_boundary"),
        (
            "northward_loss_zj",
            f"{box}_north_curl_tx_anom_1e8_nm3",
            "north_boundary",
        ),
        ("northward_loss_zj", "jiang_ne925_mjj_ms", "north_boundary"),
        ("southward_loss_zj", f"{box}_tau_x_10s_anom_nm2", "south_boundary"),
        (
            "southward_loss_zj",
            f"{box}_south_curl_tx_anom_1e8_nm3",
            "south_boundary",
        ),
        ("surface_loss_zj", f"{box}_wind_speed_anom_ms", "surface"),
        ("surface_loss_zj", f"{box}_tau_x_anom_nm2", "surface"),
        ("storage_loss_zj", f"{box}_tau_x_anom_nm2", "storage"),
        ("storage_loss_zj", "cwp_u10_anom_ms", "storage"),
        ("storage_loss_zj", f"{box}_wind_speed_anom_ms", "storage"),
    ]


def _relationship_frame(
    heat: pd.DataFrame,
    wind: pd.DataFrame,
    *,
    box: str,
    response_phase: str,
    predictor_window: str,
    response: str,
    predictor: str,
) -> pd.DataFrame:
    response_rows = heat.loc[
        heat.box.eq(box) & heat.phase.eq(response_phase),
        ["event_year", response],
    ]
    controls = heat.loc[
        heat.box.eq(box) & heat.phase.eq("arrival_Jan_Jun"),
        ["event_year", "storage_change_zj"],
    ].rename(columns={"storage_change_zj": "arrival_storage_change_zj"})
    predictors = wind.loc[
        wind.window.eq(predictor_window), ["event_year", predictor]
    ]
    joined = response_rows.merge(controls, on="event_year", validate="one_to_one")
    joined = joined.merge(predictors, on="event_year", validate="one_to_one")
    return joined.sort_values("event_year").reset_index(drop=True)


def _relationship_record(
    joined: pd.DataFrame,
    *,
    box: str,
    family: str,
    response_phase: str,
    predictor_window: str,
    response: str,
    predictor: str,
    prespecified: bool,
) -> dict[str, object]:
    result: dict[str, object] = {
        "box": box,
        "family": family,
        "response_phase": response_phase,
        "predictor_window": predictor_window,
        "response": response,
        "predictor": predictor,
        "control": "arrival_storage_change_zj",
        "prespecified": prespecified,
    }
    result.update(
        relationship_statistics(
            joined[predictor], joined[response], joined["arrival_storage_change_zj"]
        )
    )
    for year in (1997, 2015, 2023):
        row = joined.loc[joined.event_year.eq(year)].iloc[0]
        result[f"predictor_{year}"] = float(row[predictor])
        result[f"response_{year}"] = float(row[response])
        result[f"control_{year}"] = float(row["arrival_storage_change_zj"])
    return result


def build_prespecified_relationships(
    heat: pd.DataFrame,
    wind: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate only physically pre-registered wind–loss relationships."""

    rows = []
    for box in BOXES:
        for response_phase in ("redistribution_Jul_Dec", "decay_Jan_May_next"):
            for response, predictor, family in _pairing_specs(box):
                predictor_windows = ["MJJ"] if predictor == "jiang_ne925_mjj_ms" else [
                    "MJJ",
                    response_phase,
                ]
                for predictor_window in predictor_windows:
                    joined = _relationship_frame(
                        heat,
                        wind,
                        box=box,
                        response_phase=response_phase,
                        predictor_window=predictor_window,
                        response=response,
                        predictor=predictor,
                    )
                    rows.append(
                        _relationship_record(
                            joined,
                            box=box,
                            family=family,
                            response_phase=response_phase,
                            predictor_window=predictor_window,
                            response=response,
                            predictor=predictor,
                            prespecified=True,
                        )
                    )
    output = pd.DataFrame(rows)
    key = ["box", "predictor_window", "response_phase", "response", "predictor"]
    if output.duplicated(key).any():
        raise ValueError("Pre-specified relationship registry produced duplicate rows")
    return output


def _benjamini_hochberg(values: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    valid = values.dropna().sort_values()
    if valid.empty:
        return output
    count = len(valid)
    adjusted = valid.to_numpy(dtype=float) * count / np.arange(1, count + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output.loc[valid.index] = np.minimum(adjusted, 1.0)
    return output


def build_discovery_matrix(heat: pd.DataFrame, wind: pd.DataFrame) -> pd.DataFrame:
    """Retain a complete audit matrix without redefining the primary tests."""

    predictor_columns = [
        column
        for column in wind
        if "_anom_" in column or column == "jiang_ne925_mjj_ms"
    ]
    rows = []
    for box in BOXES:
        for response_phase in ("redistribution_Jul_Dec", "decay_Jan_May_next"):
            for predictor_window in ("MJJ", response_phase):
                for response in HEAT_FATE_COLUMNS:
                    for predictor in predictor_columns:
                        joined = _relationship_frame(
                            heat,
                            wind,
                            box=box,
                            response_phase=response_phase,
                            predictor_window=predictor_window,
                            response=response,
                            predictor=predictor,
                        )
                        rows.append(
                            _relationship_record(
                                joined,
                                box=box,
                                family="discovery",
                                response_phase=response_phase,
                                predictor_window=predictor_window,
                                response=response,
                                predictor=predictor,
                                prespecified=False,
                            )
                        )
    output = pd.DataFrame(rows)
    output["pearson_q"] = _benjamini_hochberg(output["pearson_p"])
    output["spearman_q"] = _benjamini_hochberg(output["spearman_p"])
    return output


def _setup_plot_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 340,
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.labelsize": 10.0,
            "axes.titlesize": 10.5,
            "axes.edgecolor": "#263746",
            "axes.labelcolor": "#102A3A",
            "xtick.color": "#263746",
            "ytick.color": "#263746",
            "text.color": "#102A3A",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(
        0.01,
        0.98,
        f"({label})",
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=10.5,
        fontweight="bold",
    )


def _save_figure(figure: plt.Figure, output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / f"{stem}.png"
    pdf = output_dir / f"{stem}.pdf"
    figure.savefig(png, dpi=340, bbox_inches="tight", facecolor="white")
    figure.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return png, pdf


def make_fate_figure(heat: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    """Plot the fixed boxes and paired 2015/2023 heat fates by phase."""

    _setup_plot_style()
    figure = plt.figure(figsize=(15.2, 12.8), constrained_layout=True)
    grid = figure.add_gridspec(4, 3, height_ratios=(0.52, 1.0, 1.0, 1.0))
    locator = figure.add_subplot(grid[0, :])
    locator.set_xlim(120, 290)
    locator.set_ylim(-20, 15)
    locator.axhline(0, color="#6C7A86", linewidth=0.7)
    locator.grid(color="#D9E1E6", linewidth=0.6, alpha=0.8)
    for box, (lon0, lon1) in BOXES.items():
        locator.add_patch(
            Rectangle(
                (lon0, -10),
                lon1 - lon0,
                15,
                facecolor=BOX_COLORS[box],
                edgecolor="#102A3A",
                linewidth=1.0,
                alpha=0.75,
            )
        )
        locator.text(
            (lon0 + lon1) / 2,
            -2.5,
            box.capitalize(),
            ha="center",
            va="center",
            color="white",
            fontweight="bold",
            fontsize=10.5,
        )
    locator.set_xticks(
        [120, 160, 180, 220, 260, 280],
        ["120°E", "160°E", "180°", "140°W", "100°W", "80°W"],
    )
    locator.set_yticks([-10, 0, 5], ["10°S", "Eq", "5°N"])
    locator.set_ylabel("Latitude")
    locator.spines[["top", "right"]].set_visible(False)
    _panel_label(locator, "a")

    component_labels = [
        "West\nface",
        "East\nface",
        "South",
        "North",
        "Surface",
        "Storage",
    ]
    phase_labels = {
        "arrival_Jan_Jun": "Arrival: Jan–Jun",
        "redistribution_Jul_Dec": "Redistribution: Jul–Dec",
        "decay_Jan_May_next": "Decay: following Jan–May",
    }
    highlighted = heat.loc[heat.event_year.isin([2015, 2023])]
    maximum = float(np.nanmax(np.abs(highlighted[list(HEAT_FATE_COLUMNS)].to_numpy())))
    limit = np.ceil(maximum / 2.0) * 2.0 * 1.08
    panel_index = 1
    for row_index, phase in enumerate(PHASE_MONTHS, start=1):
        for column_index, box in enumerate(BOXES):
            axis = figure.add_subplot(grid[row_index, column_index])
            x = np.arange(len(HEAT_FATE_COLUMNS))
            width = 0.36
            for event_index, year in enumerate((2015, 2023)):
                selected = heat.loc[
                    heat.event_year.eq(year) & heat.phase.eq(phase) & heat.box.eq(box)
                ].iloc[0]
                axis.bar(
                    x + (event_index - 0.5) * width,
                    [float(selected[column]) for column in HEAT_FATE_COLUMNS],
                    width=width,
                    color=EVENT_COLORS[year],
                    edgecolor="white",
                    linewidth=0.6,
                    label=str(year),
                    zorder=3,
                )
            axis.axhline(0, color="#52616B", linewidth=0.8)
            axis.grid(axis="y", color="#D8E0E6", linewidth=0.7, alpha=0.8)
            axis.set_ylim(-limit, limit)
            axis.set_xticks(x, component_labels)
            axis.tick_params(axis="x", labelsize=8.2)
            axis.spines[["top", "right"]].set_visible(False)
            if column_index == 0:
                axis.set_ylabel(f"{phase_labels[phase]}\nHeat loss from box (ZJ)")
            axis.set_title(box.capitalize(), fontweight="bold")
            if row_index == 1 and column_index == 0:
                axis.legend(frameon=False, ncol=2, loc="upper left", bbox_to_anchor=(0.10, 1.0))
            _panel_label(axis, chr(ord("a") + panel_index))
            panel_index += 1
    return _save_figure(figure, output_dir, FATE_STEM)


def _predictor_short(name: str) -> str:
    if name == "cwp_u10_anom_ms":
        return "CWP u10"
    if name == "jiang_ne925_mjj_ms":
        return "NE925"
    if "north_curl_tx" in name:
        return "−∂τx/∂y (N)"
    if "south_curl_tx" in name:
        return "−∂τx/∂y (S)"
    if "tau_x_5n" in name:
        return "τx at 5°N"
    if "tau_x_10s" in name:
        return "τx at 10°S"
    if "wind_speed" in name:
        return "Wind speed"
    if "tau_x" in name:
        return "Local τx"
    return name


def _best_relationship(
    relationships: pd.DataFrame,
    *,
    box: str,
    phase: str,
    response: str,
) -> pd.Series:
    candidates = relationships.loc[
        relationships.box.eq(box)
        & relationships.response_phase.eq(phase)
        & relationships.response.eq(response)
    ].copy()
    stable = candidates.loc[candidates.sign_agreement & candidates.loeo_sign_stable]
    if not stable.empty:
        candidates = stable
    return candidates.loc[candidates.partial_r.abs().idxmax()]


def make_relationship_matrix(
    relationships: pd.DataFrame,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Summarize the best pre-specified relationship for each loss pathway."""

    _setup_plot_style()
    response_labels = {
        "west_face_loss_zj": "West-face loss",
        "east_face_loss_zj": "East-face loss",
        "southward_loss_zj": "Southward loss",
        "northward_loss_zj": "Northward loss",
        "surface_loss_zj": "Surface loss",
        "storage_loss_zj": "Storage loss",
    }
    phases = ("redistribution_Jul_Dec", "decay_Jan_May_next")
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 7.2), constrained_layout=True)
    image = None
    for panel_index, (axis, phase) in enumerate(zip(axes, phases)):
        values = np.full((len(response_labels), len(BOXES)), np.nan)
        annotations: list[list[str]] = [["" for _ in BOXES] for _ in response_labels]
        for row_index, response in enumerate(response_labels):
            for column_index, box in enumerate(BOXES):
                row = _best_relationship(
                    relationships, box=box, phase=phase, response=response
                )
                values[row_index, column_index] = float(row.partial_r)
                window = "MJJ" if row.predictor_window == "MJJ" else "same phase"
                annotations[row_index][column_index] = (
                    f"{row.partial_r:+.2f}\n{_predictor_short(row.predictor)}\n{window}"
                )
        image = axis.imshow(
            values,
            cmap="RdBu_r",
            norm=TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0),
            aspect="auto",
        )
        axis.set_xticks(range(len(BOXES)), [box.capitalize() for box in BOXES])
        axis.set_yticks(range(len(response_labels)), list(response_labels.values()))
        axis.set_xlabel(
            "Jul–Dec response" if phase == "redistribution_Jul_Dec" else "Following Jan–May response"
        )
        for row_index in range(len(response_labels)):
            for column_index in range(len(BOXES)):
                color = "white" if abs(values[row_index, column_index]) >= 0.58 else "#102A3A"
                axis.text(
                    column_index,
                    row_index,
                    annotations[row_index][column_index],
                    ha="center",
                    va="center",
                    fontsize=8.2,
                    color=color,
                )
        _panel_label(axis, chr(ord("a") + panel_index))
    figure.colorbar(image, ax=axes, orientation="horizontal", shrink=0.72, label="Partial correlation")
    return _save_figure(figure, output_dir, MATRIX_STEM)


def make_scatter_figure(
    heat: pd.DataFrame,
    wind: pd.DataFrame,
    relationships: pd.DataFrame,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Plot four physically interpretable wind–loss relationships."""

    _setup_plot_style()
    selections = [
        (
            "east",
            "decay_Jan_May_next",
            "decay_Jan_May_next",
            "northward_loss_zj",
            "east_north_curl_tx_anom_1e8_nm3",
            "East-box northward loss (ZJ)",
            "East northern −∂τx/∂y (10⁻⁸ N m⁻³)",
        ),
        (
            "central",
            "redistribution_Jul_Dec",
            "redistribution_Jul_Dec",
            "east_face_loss_zj",
            "central_tau_x_anom_nm2",
            "Central east-face loss (ZJ)",
            "Central τx anomaly (N m⁻²)",
        ),
        (
            "central",
            "decay_Jan_May_next",
            "decay_Jan_May_next",
            "surface_loss_zj",
            "central_tau_x_anom_nm2",
            "Central surface loss (ZJ)",
            "Central τx anomaly (N m⁻²)",
        ),
        (
            "central",
            "redistribution_Jul_Dec",
            "MJJ",
            "storage_loss_zj",
            "cwp_u10_anom_ms",
            "Central storage loss (ZJ)",
            "MJJ CWP u10 anomaly (m s⁻¹)",
        ),
    ]
    figure, axes = plt.subplots(2, 2, figsize=(11.6, 9.0), constrained_layout=True)
    for panel_index, (axis, selection) in enumerate(zip(axes.ravel(), selections)):
        box, phase, window, response, predictor, ylabel, xlabel = selection
        joined = _relationship_frame(
            heat,
            wind,
            box=box,
            response_phase=phase,
            predictor_window=window,
            response=response,
            predictor=predictor,
        )
        row = relationships.loc[
            relationships.box.eq(box)
            & relationships.response_phase.eq(phase)
            & relationships.predictor_window.eq(window)
            & relationships.response.eq(response)
            & relationships.predictor.eq(predictor)
        ].iloc[0]
        ordinary = ~joined.event_year.isin(EVENT_COLORS)
        axis.scatter(
            joined.loc[ordinary, predictor],
            joined.loc[ordinary, response],
            s=38,
            color="#97A6B2",
            edgecolor="white",
            linewidth=0.7,
            zorder=3,
            label="Other events",
        )
        for year in EVENT_COLORS:
            selected = joined.loc[joined.event_year.eq(year)]
            axis.scatter(
                selected[predictor],
                selected[response],
                s=70,
                color=EVENT_COLORS[year],
                edgecolor="white",
                linewidth=0.9,
                zorder=4,
                label=str(year),
            )
        fit = stats.linregress(joined[predictor], joined[response])
        x_values = np.linspace(joined[predictor].min(), joined[predictor].max(), 100)
        axis.plot(x_values, fit.intercept + fit.slope * x_values, color="#102A3A", linewidth=1.5)
        axis.axhline(0, color="#7C8A94", linewidth=0.7)
        axis.axvline(0, color="#7C8A94", linewidth=0.7)
        axis.grid(color="#D8E0E6", linewidth=0.7, alpha=0.8)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        axis.text(
            0.98,
            0.04,
            f"n = {int(row.n)}\nr = {row.pearson_r:+.2f}\nρ = {row.spearman_r:+.2f}\npartial r = {row.partial_r:+.2f}",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=9.0,
        )
        _panel_label(axis, chr(ord("a") + panel_index))
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        frameon=False,
        ncol=4,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.015),
    )
    return _save_figure(figure, output_dir, SCATTER_STEM)


def _heat_value(
    heat: pd.DataFrame,
    event_year: int,
    phase: str,
    box: str,
    column: str,
) -> float:
    return float(
        heat.loc[
            heat.event_year.eq(event_year) & heat.phase.eq(phase) & heat.box.eq(box),
            column,
        ].iloc[0]
    )


def _relation_value(
    relationships: pd.DataFrame,
    *,
    box: str,
    phase: str,
    window: str,
    response: str,
    predictor: str,
) -> pd.Series:
    return relationships.loc[
        relationships.box.eq(box)
        & relationships.response_phase.eq(phase)
        & relationships.predictor_window.eq(window)
        & relationships.response.eq(response)
        & relationships.predictor.eq(predictor)
    ].iloc[0]


def write_report(
    heat: pd.DataFrame,
    relationships: pd.DataFrame,
    output_dir: Path,
) -> Path:
    """Write a compact Chinese scientific interpretation."""

    east_north = _relation_value(
        relationships,
        box="east",
        phase="decay_Jan_May_next",
        window="decay_Jan_May_next",
        response="northward_loss_zj",
        predictor="east_north_curl_tx_anom_1e8_nm3",
    )
    central_east = _relation_value(
        relationships,
        box="central",
        phase="redistribution_Jul_Dec",
        window="redistribution_Jul_Dec",
        response="east_face_loss_zj",
        predictor="central_tau_x_anom_nm2",
    )
    central_surface = _relation_value(
        relationships,
        box="central",
        phase="decay_Jan_May_next",
        window="decay_Jan_May_next",
        response="surface_loss_zj",
        predictor="central_tau_x_anom_nm2",
    )
    central_storage = _relation_value(
        relationships,
        box="central",
        phase="redistribution_Jul_Dec",
        window="MJJ",
        response="storage_loss_zj",
        predictor="cwp_u10_anom_ms",
    )
    east_storage = _relation_value(
        relationships,
        box="east",
        phase="decay_Jan_May_next",
        window="MJJ",
        response="storage_loss_zj",
        predictor="cwp_u10_anom_ms",
    )
    report = f"""# 三箱暖量命运与风异常关系

## 核心发现

暖量到达总量不能代表耦合所需的空间配置。1—6月中箱OHC异常增量在2015年为{_heat_value(heat, 2015, 'arrival_Jan_Jun', 'central', 'storage_change_zj'):.2f} ZJ，2023年仅为{_heat_value(heat, 2023, 'arrival_Jan_Jun', 'central', 'storage_change_zj'):.2f} ZJ；东箱则分别增加{_heat_value(heat, 2015, 'arrival_Jan_Jun', 'east', 'storage_change_zj'):.2f}和{_heat_value(heat, 2023, 'arrival_Jan_Jun', 'east', 'storage_change_zj'):.2f} ZJ。2023表现为更多暖量直接堆积在东部，而2015有更大的发展期中太平洋储热。

两次事件在7—12月进一步分化。2015中箱储存损失为{_heat_value(heat, 2015, 'redistribution_Jul_Dec', 'central', 'storage_loss_zj'):+.2f} ZJ，即中箱OHC开始下降；2023为{_heat_value(heat, 2023, 'redistribution_Jul_Dec', 'central', 'storage_loss_zj'):+.2f} ZJ，表示中箱仍在继续增热。同期中箱向东边界损失在2015和2023分别为{_heat_value(heat, 2015, 'redistribution_Jul_Dec', 'central', 'east_face_loss_zj'):.2f}和{_heat_value(heat, 2023, 'redistribution_Jul_Dec', 'central', 'east_face_loss_zj'):.2f} ZJ。因此2015的中部暖量更早建立并进入重新分配阶段，2023的中部增暖则明显推迟。

## 不同箱体中与风最一致的损失通道

东箱最清楚的风—热量关系出现在次年1—5月的北向输出。东箱北侧 `−∂τx/∂y` 与北向热量损失的Pearson相关为{east_north.pearson_r:+.2f}，Spearman相关为{east_north.spearman_r:+.2f}，控制1—6月东箱储热后的偏相关为{east_north.partial_r:+.2f}；逐一删除事件后的偏相关范围为{east_north.loeo_r_min:+.2f}至{east_north.loeo_r_max:+.2f}。2015和2023的东箱北向输出分别为{_heat_value(heat, 2015, 'decay_Jan_May_next', 'east', 'northward_loss_zj'):.2f}和{_heat_value(heat, 2023, 'decay_Jan_May_next', 'east', 'northward_loss_zj'):.2f} ZJ。这表明东箱衰减期最有风场信息的出口是5°N北侧边界，而不是笼统的总散热。

中箱的主要风响应集中在纬向重新分配和海表释放。7—12月中箱纬向风应力与向东边界损失的相关为r={central_east.pearson_r:+.2f}，偏相关为{central_east.partial_r:+.2f}；次年1—5月纬向风应力与中箱海表损失的相关为r={central_surface.pearson_r:+.2f}，偏相关为{central_surface.partial_r:+.2f}。2015/2023同期中箱海表损失分别为{_heat_value(heat, 2015, 'decay_Jan_May_next', 'central', 'surface_loss_zj'):.2f}/{_heat_value(heat, 2023, 'decay_Jan_May_next', 'central', 'surface_loss_zj'):.2f} ZJ。

发展期风异常还与后续储热衰减有关。MJJ中西太平洋u10与7—12月中箱储存损失的偏相关为{central_storage.partial_r:+.2f}，与次年1—5月东箱储存损失的偏相关为{east_storage.partial_r:+.2f}。这与2015更强、更早的西风异常以及更早的中部释放相一致，而2023的中箱储热建立较晚。

## 对2015和2023差异的更新

当前结果支持把两次事件的差异写成“空间配置和释放通道不同”，而不是“东部有没有暖量”。2015的发展期暖量较多进入中箱，并伴随较强的中太平洋纬向风应力；随后中箱通过向东输送和海表交换释放暖量，东箱在衰减期还出现较强北向输出。2023的暖量更集中于东箱，中箱在7—12月仍继续增热，说明中太平洋储热与风异常没有在同一发展窗口充分衔接。

这些统计关系不能证明单向因果。同期风、洋流、海表通量和对流属于相互反馈的耦合系统；即使MJJ风领先后期储热变化，也可能同时反映更早的海洋状态或对流组织。最稳妥的表述是：不同风异常分别与不同热量出口相匹配，中箱的纬向输送和表面释放、东箱的北向输出是2015与2023暖量命运分化中最值得保留的通道。

## 边界输送的使用范围

三个箱体分别采用质量闭合后的法向速度计算箱内边界输送，因此本文把它们解释为“该箱体的边界损失”，不把相邻两箱的修正值强制视为完全相等的共享通量。关键的140°W边界在2015和2023年7—12月的两侧差值分别为{abs(_heat_value(heat, 2015, 'redistribution_Jul_Dec', 'central', 'east_theta_heat_in_zj') + _heat_value(heat, 2015, 'redistribution_Jul_Dec', 'east', 'west_theta_heat_in_zj')):.2f}和{abs(_heat_value(heat, 2023, 'redistribution_Jul_Dec', 'central', 'east_theta_heat_in_zj') + _heat_value(heat, 2023, 'redistribution_Jul_Dec', 'east', 'west_theta_heat_in_zj')):.2f} ZJ。因而当前结果适合回答各箱热量从哪些出口流失；若要严格讨论箱间守恒转移，应另用同一个未分箱修正的共享断面通量。
"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / REPORT_NAME
    path.write_text(report, encoding="utf-8")
    return path


def _audit_payload(
    heat: pd.DataFrame,
    wind: pd.DataFrame,
    relationships: pd.DataFrame,
    discovery: pd.DataFrame,
) -> dict[str, object]:
    promoted = relationships.loc[
        relationships.sign_agreement
        & relationships.loeo_sign_stable
        & relationships.partial_r.abs().ge(0.5)
    ].copy()
    promoted = promoted.reindex(promoted.partial_r.abs().sort_values(ascending=False).index)
    internal_180 = heat["east_theta_heat_in_zj"].where(heat.box.eq("west"))
    # Corrected-face mismatches are evaluated after a self-join on event/phase.
    indexed = heat.set_index(["event_year", "phase", "box"])
    mismatch_180 = []
    mismatch_220 = []
    for event in EVENTS:
        for phase in PHASE_MONTHS:
            west = indexed.loc[(event, phase, "west")]
            central = indexed.loc[(event, phase, "central")]
            east = indexed.loc[(event, phase, "east")]
            mismatch_180.append(
                abs(float(west.east_theta_heat_in_zj + central.west_theta_heat_in_zj))
            )
            mismatch_220.append(
                abs(float(central.east_theta_heat_in_zj + east.west_theta_heat_in_zj))
            )
    del internal_180
    return {
        "heat_rows": int(len(heat)),
        "wind_rows": int(len(wind)),
        "prespecified_relationship_rows": int(len(relationships)),
        "discovery_rows": int(len(discovery)),
        "missing_primary_relationship_values": int(
            relationships[["pearson_r", "spearman_r", "partial_r"]].isna().sum().sum()
        ),
        "corrected_internal_face_mismatch_max_zj": {
            "180E": float(max(mismatch_180)),
            "140W": float(max(mismatch_220)),
        },
        "key_140W_mismatch_zj": {
            "2015_redistribution_Jul_Dec": abs(
                _heat_value(
                    heat,
                    2015,
                    "redistribution_Jul_Dec",
                    "central",
                    "east_theta_heat_in_zj",
                )
                + _heat_value(
                    heat,
                    2015,
                    "redistribution_Jul_Dec",
                    "east",
                    "west_theta_heat_in_zj",
                )
            ),
            "2023_redistribution_Jul_Dec": abs(
                _heat_value(
                    heat,
                    2023,
                    "redistribution_Jul_Dec",
                    "central",
                    "east_theta_heat_in_zj",
                )
                + _heat_value(
                    heat,
                    2023,
                    "redistribution_Jul_Dec",
                    "east",
                    "west_theta_heat_in_zj",
                )
            ),
        },
        "audited_arrival_storage_change_zj": {
            "2015_central": _heat_value(heat, 2015, "arrival_Jan_Jun", "central", "storage_change_zj"),
            "2023_central": _heat_value(heat, 2023, "arrival_Jan_Jun", "central", "storage_change_zj"),
            "2015_east": _heat_value(heat, 2015, "arrival_Jan_Jun", "east", "storage_change_zj"),
            "2023_east": _heat_value(heat, 2023, "arrival_Jan_Jun", "east", "storage_change_zj"),
        },
        "promoted_relationship_count": int(len(promoted)),
        "strongest_promoted_relationships": json.loads(
            promoted.head(12).to_json(orient="records")
        ),
    }


def run_pipeline(
    output_dir: Path | None = None,
    input_root: Path | None = None,
    output_root: Path | None = None,
) -> PipelineOutputs:
    """Run the complete calculation and write deterministic checkpoints."""

    data_root = discover_input_root() if input_root is None else Path(input_root)
    root = ROOT if output_root is None else Path(output_root)
    target = root / OUTPUT_DIR if output_dir is None else Path(output_dir)
    derived = root / DERIVED
    target.mkdir(parents=True, exist_ok=True)
    derived.mkdir(parents=True, exist_ok=True)

    heat = load_heat_fate_events(data_root)
    wind = build_event_wind_table(data_root)
    relationships = build_prespecified_relationships(heat, wind)
    discovery = build_discovery_matrix(heat, wind)

    event_heat_csv = derived / EVENT_HEAT_NAME
    wind_csv = derived / WIND_NAME
    relationship_csv = derived / RELATIONSHIP_NAME
    discovery_csv = derived / DISCOVERY_NAME
    audit_json = derived / AUDIT_NAME
    heat.to_csv(event_heat_csv, index=False, float_format="%.8g")
    wind.to_csv(wind_csv, index=False, float_format="%.8g")
    relationships.to_csv(relationship_csv, index=False, float_format="%.8g")
    discovery.to_csv(discovery_csv, index=False, float_format="%.8g")
    audit_json.write_text(
        json.dumps(
            _audit_payload(heat, wind, relationships, discovery),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fate_png, fate_pdf = make_fate_figure(heat, target)
    matrix_png, matrix_pdf = make_relationship_matrix(relationships, target)
    scatter_png, scatter_pdf = make_scatter_figure(heat, wind, relationships, target)
    report_md = write_report(heat, relationships, target)
    return PipelineOutputs(
        event_heat_csv=event_heat_csv,
        wind_csv=wind_csv,
        relationship_csv=relationship_csv,
        discovery_csv=discovery_csv,
        audit_json=audit_json,
        fate_png=fate_png,
        fate_pdf=fate_pdf,
        matrix_png=matrix_png,
        matrix_pdf=matrix_pdf,
        scatter_png=scatter_png,
        scatter_pdf=scatter_pdf,
        report_md=report_md,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    outputs = run_pipeline(
        output_dir=arguments.output_dir,
        input_root=arguments.input_root,
        output_root=arguments.output_root,
    )
    for path in outputs.__dict__.values():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
