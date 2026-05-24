from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable


def weighted_region_mean(values: Iterable[Iterable[float]], lats: Iterable[float]) -> float:
    numerator = 0.0
    denominator = 0.0
    for row, lat in zip(values, lats):
        weight = math.cos(math.radians(float(lat)))
        row_values = [float(value) for value in row if not math.isnan(float(value))]
        if not row_values:
            continue
        row_mean = sum(row_values) / len(row_values)
        numerator += row_mean * weight
        denominator += weight
    if denominator == 0:
        return math.nan
    return numerator / denominator


def weighted_region_mean_timeseries(values: Iterable[Iterable[Iterable[float]]], lats: Iterable[float]) -> list[float]:
    return [weighted_region_mean(time_slice, lats) for time_slice in values]


def monthly_anomalies(records: list[dict], reference_start: int, reference_end: int) -> list[dict]:
    by_month = defaultdict(list)
    for record in records:
        if reference_start <= int(record["year"]) <= reference_end:
            by_month[int(record["month"])].append(float(record["value"]))

    climatology = {
        month: sum(values) / len(values)
        for month, values in by_month.items()
        if values
    }
    output = []
    for record in records:
        month = int(record["month"])
        row = dict(record)
        row["anomaly"] = float(record["value"]) - climatology[month]
        output.append(row)
    return output


def seasonal_event_mean(records: list[dict], event_year: int, months: tuple[int, ...]) -> float:
    values = []
    lookup = {(int(row["year"]), int(row["month"])): float(row["anomaly"]) for row in records}
    for month in months:
        year = event_year
        actual_month = month
        if month > 12:
            year += 1
            actual_month = month - 12
        values.append(lookup[(year, actual_month)])
    return sum(values) / len(values)


def seasonal_mean_by_months(records: list[dict], event_year: int, months: tuple[int, ...], value_key: str = "anomaly") -> float:
    lookup = {(int(row["year"]), int(row["month"])): float(row[value_key]) for row in records}
    values = []
    for month in months:
        year = event_year
        actual_month = month
        if month > 12:
            year += 1
            actual_month = month - 12
        values.append(lookup[(year, actual_month)])
    return sum(values) / len(values)


def subtract_monthly_climatology_cube(records: list[dict], reference_start: int, reference_end: int) -> list[dict]:
    by_month = defaultdict(list)
    for record in records:
        if reference_start <= int(record["year"]) <= reference_end:
            by_month[int(record["month"])].append(record["values"])

    climatology = {}
    for month, cubes in by_month.items():
        rows = len(cubes[0])
        cols = len(cubes[0][0])
        climatology[month] = [
            [
                sum(float(cube[row][col]) for cube in cubes) / len(cubes)
                for col in range(cols)
            ]
            for row in range(rows)
        ]

    output = []
    for record in records:
        month = int(record["month"])
        baseline = climatology[month]
        values = record["values"]
        row = dict(record)
        row["values"] = [
            [
                float(values[row_index][col_index]) - float(baseline[row_index][col_index])
                for col_index in range(len(values[0]))
            ]
            for row_index in range(len(values))
        ]
        output.append(row)
    return output
