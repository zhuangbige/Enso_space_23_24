from __future__ import annotations

import math


def seasonal_grid_mean(
    records: list[dict], event_year: int, months: tuple[int, ...]
) -> list[list[float]]:
    lookup = {(int(row["year"]), int(row["month"])): row["values"] for row in records}
    selected = []
    for month in months:
        year = event_year
        actual_month = month
        if month > 12:
            year += 1
            actual_month = month - 12
        selected.append(lookup[(year, actual_month)])
    return mean_grid(selected)


def difference_grid(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [float(left[row][col]) - float(right[row][col]) for col in range(len(left[0]))]
        for row in range(len(left))
    ]


def mean_grid(grids: list[list[list[float]]]) -> list[list[float]]:
    rows = len(grids[0])
    cols = len(grids[0][0])
    return [
        [
            sum(float(grid[row][col]) for grid in grids) / len(grids)
            for col in range(cols)
        ]
        for row in range(rows)
    ]


def grid_region_mean(
    values: list[list[float]],
    lat,
    lon,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> float:
    selected = []
    for lat_index, lat_value in enumerate(lat):
        if not (lat_min <= float(lat_value) <= lat_max):
            continue
        weight = math.cos(math.radians(float(lat_value)))
        for lon_index, lon_value in enumerate(lon):
            if lon_min <= float(lon_value) <= lon_max:
                value = float(values[lat_index][lon_index])
                if not math.isnan(value):
                    selected.append((value, weight))
    if not selected:
        return math.nan
    numerator = sum(value * weight for value, weight in selected)
    denominator = sum(weight for _, weight in selected)
    return numerator / denominator
