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
from scipy import stats


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
