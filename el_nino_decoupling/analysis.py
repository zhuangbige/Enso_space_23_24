from __future__ import annotations

import csv
from dataclasses import dataclass, fields
from pathlib import Path
import math


@dataclass(frozen=True)
class EventRecord:
    year: int
    nino3: float
    uwind: float
    soi: float
    uwind_expected: float
    soi_expected: float
    uwind_residual: float
    soi_residual: float
    uwind_coupling_ratio: float | None
    soi_coupling_ratio: float | None
    highlight: bool


def _as_float_list(values) -> list[float]:
    return [float(value) for value in values]


def _linear_fit(x: list[float], y: list[float]) -> tuple[float, float]:
    if len(x) != len(y):
        raise ValueError("x and y must have the same length.")
    if len(x) < 2:
        raise ValueError("At least two points are required.")
    xmean = sum(x) / len(x)
    ymean = sum(y) / len(y)
    denominator = sum((value - xmean) ** 2 for value in x)
    if denominator == 0:
        raise ValueError("Cannot fit a line when all x values are equal.")
    slope = sum((xvalue - xmean) * (yvalue - ymean) for xvalue, yvalue in zip(x, y)) / denominator
    intercept = ymean - slope * xmean
    return slope, intercept


def _ratio(observed: float, expected: float) -> float | None:
    if expected == 0:
        return None
    return observed / expected


def response_strength_ratio(value_2023: float, value_comparable: float, use_absolute: bool = False) -> float | None:
    numerator = abs(value_2023) if use_absolute else value_2023
    denominator = abs(value_comparable) if use_absolute else value_comparable
    if denominator == 0:
        return None
    return numerator / denominator


def compute_fig1_event_records(
    nino3,
    uwind,
    soi,
    start_year: int = 1982,
    highlight_years: tuple[int, ...] = (1982, 1997, 2015, 2023),
) -> list[EventRecord]:
    nino3_values = _as_float_list(nino3)
    uwind_values = _as_float_list(uwind)
    soi_values = _as_float_list(soi)
    uwind_slope, uwind_intercept = _linear_fit(nino3_values, uwind_values)
    soi_slope, soi_intercept = _linear_fit(nino3_values, soi_values)

    records = []
    for offset, (nino_value, uwind_value, soi_value) in enumerate(zip(nino3_values, uwind_values, soi_values)):
        year = start_year + offset
        uwind_expected = uwind_slope * nino_value + uwind_intercept
        soi_expected = soi_slope * nino_value + soi_intercept
        records.append(
            EventRecord(
                year=year,
                nino3=nino_value,
                uwind=uwind_value,
                soi=soi_value,
                uwind_expected=uwind_expected,
                soi_expected=soi_expected,
                uwind_residual=uwind_value - uwind_expected,
                soi_residual=soi_value - soi_expected,
                uwind_coupling_ratio=_ratio(uwind_value, uwind_expected),
                soi_coupling_ratio=_ratio(soi_value, soi_expected),
                highlight=year in highlight_years,
            )
        )
    return records


def write_event_records(records: list[EventRecord], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    field_names = [field.name for field in fields(EventRecord)]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names)
        writer.writeheader()
        for record in records:
            writer.writerow({name: getattr(record, name) for name in field_names})


def average_lon_time(values, lon, lon_min: float, lon_max: float, month_indices: list[int]) -> float:
    lon_values = _as_float_list(lon)
    selected = []
    for lon_index, lon_value in enumerate(lon_values):
        if lon_min <= lon_value <= lon_max:
            row = values[lon_index]
            for month_index in month_indices:
                value = float(row[month_index])
                if not math.isnan(value):
                    selected.append(value)
    if not selected:
        return math.nan
    return sum(selected) / len(selected)


def average_lon_level(values, lon, levels, lon_min: float, lon_max: float, level_min: float, level_max: float) -> float:
    lon_values = _as_float_list(lon)
    level_values = _as_float_list(levels)
    selected = []
    for lon_index, lon_value in enumerate(lon_values):
        if lon_min <= lon_value <= lon_max:
            row = values[lon_index]
            for level_index, level_value in enumerate(level_values):
                if level_min <= level_value <= level_max:
                    value = float(row[level_index])
                    if not math.isnan(value):
                        selected.append(value)
    if not selected:
        return math.nan
    return sum(selected) / len(selected)
