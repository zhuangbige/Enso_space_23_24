from __future__ import annotations

import math
from collections.abc import Iterable


_NINO_BOUNDS = {
    "nino3": (-5.0, 5.0, 210.0, 270.0),
    "nino3.4": (-5.0, 5.0, 190.0, 240.0),
    "nino4": (-5.0, 5.0, 160.0, 210.0),
}


def nino_region_bounds(region: str) -> tuple[float, float, float, float]:
    normalized = region.lower()
    try:
        return _NINO_BOUNDS[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(_NINO_BOUNDS))
        raise KeyError(f"Unknown Nino region '{region}'. Available regions: {available}") from exc


def standardized_anomaly(
    values: Iterable[float],
    reference_values: Iterable[float] | None = None,
) -> list[float]:
    series = [float(value) for value in values]
    reference = [float(value) for value in (reference_values if reference_values is not None else series)]
    if len(reference) < 2:
        raise ValueError("At least two reference values are required.")

    mean = sum(reference) / len(reference)
    variance = sum((value - mean) ** 2 for value in reference) / (len(reference) - 1)
    stddev = math.sqrt(variance)
    if stddev == 0.0:
        raise ValueError("Reference standard deviation is zero.")

    return [(value - mean) / stddev for value in series]


def coupling_ratio(observed: float, expected: float) -> float | None:
    if expected == 0:
        return None
    return observed / expected
