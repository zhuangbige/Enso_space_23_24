from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    id: str
    label: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    rationale: str


REGION_BOUNDS = {
    "nino3": Region("nino3", "Nino-3", -5.0, 5.0, 210.0, 270.0, "Eastern Pacific ENSO SST core."),
    "tropical_indian_ocean": Region(
        "tropical_indian_ocean",
        "Tropical Indian Ocean",
        -20.0,
        20.0,
        40.0,
        110.0,
        "Basin-scale Indian Ocean warmth that may damp Pacific convection.",
    ),
    "maritime_continent": Region(
        "maritime_continent",
        "Maritime Continent",
        -10.0,
        10.0,
        95.0,
        150.0,
        "Regional convection bridge between Indian and Pacific basins.",
    ),
    "western_pacific_warm_pool": Region(
        "western_pacific_warm_pool",
        "Western Pacific warm pool",
        -10.0,
        10.0,
        120.0,
        160.0,
        "Warm-pool SST and convection region west of the central Pacific.",
    ),
    "tropical_north_atlantic": Region(
        "tropical_north_atlantic",
        "Tropical North Atlantic",
        0.0,
        20.0,
        300.0,
        340.0,
        "Atlantic warm anomaly region implicated in summer Pacific easterly response.",
    ),
}


def get_region(region_id: str) -> Region:
    try:
        return REGION_BOUNDS[region_id]
    except KeyError as exc:
        available = ", ".join(sorted(REGION_BOUNDS))
        raise KeyError(f"Unknown region '{region_id}'. Available regions: {available}") from exc
