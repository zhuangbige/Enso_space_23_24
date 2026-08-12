#!/usr/bin/env python3
"""Compare the development-year air-sea coupling of 2015 and 2023.

ERA5 surface fluxes are stored with downward-positive signs.  Every public
diagnostic from this module converts them to ocean-to-atmosphere heat loss,
positive upward.  OISST, ERA5, and GPCP anomalies use calendar-month linear
expectations fitted over 1982-2014.  CPC OLR retains its published anomaly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
BASELINE = (1982, 2014)
EVENT_YEARS = (2015, 2023)
SEASON_MONTHS = {
    "MAM": (3, 4, 5),
    "MJJ": (5, 6, 7),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
}
ARRIVAL_VALUES = {
    2015: {"transport_140w_zj": 8.49, "east_ohc_gain_zj": 8.60},
    2023: {"transport_140w_zj": 9.90, "east_ohc_gain_zj": 11.12},
}


def same_month_linear_anomaly(
    frame: pd.DataFrame,
    value_column: str,
    baseline: tuple[int, int] = BASELINE,
) -> pd.Series:
    """Remove a calendar-month linear expectation while preserving row order."""

    required = {"year", "month", value_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns for anomaly calculation: {sorted(missing)}")

    output = pd.Series(np.nan, index=frame.index, dtype=float, name=f"{value_column}_anom")
    for month, group in frame.groupby("month", sort=False):
        baseline_rows = group.loc[group.year.between(*baseline), ["year", value_column]].dropna()
        if len(baseline_rows) < 3:
            raise ValueError(f"Month {month} has fewer than three baseline values")
        slope, intercept = np.polyfit(
            baseline_rows.year.to_numpy(dtype=float),
            baseline_rows[value_column].to_numpy(dtype=float),
            1,
        )
        expected = intercept + slope * group.year.to_numpy(dtype=float)
        output.loc[group.index] = group[value_column].to_numpy(dtype=float) - expected
    return output


def weighted_box_mean(
    field: xr.DataArray,
    lat0: float,
    lat1: float,
    lon0: float,
    lon1: float,
) -> xr.DataArray:
    """Return a cosine-latitude-weighted mean from a 0-360 longitude field."""

    rename = {}
    if "latitude" in field.coords:
        rename["latitude"] = "lat"
    if "longitude" in field.coords:
        rename["longitude"] = "lon"
    normalized = field.rename(rename)
    if "lat" not in normalized.coords or "lon" not in normalized.coords:
        raise ValueError("Field requires latitude and longitude coordinates")
    normalized = normalized.assign_coords(lon=normalized.lon % 360.0).sortby("lon").sortby("lat")
    selected = normalized.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if selected.sizes.get("lat", 0) == 0 or selected.sizes.get("lon", 0) == 0:
        raise ValueError(f"Empty box lat={lat0}:{lat1}, lon={lon0}:{lon1}")
    weights = np.cos(np.deg2rad(selected.lat))
    return selected.weighted(weights).mean(("lat", "lon"), skipna=True)


def to_upward_loss(
    latent_down: np.ndarray,
    sensible_down: np.ndarray,
    shortwave_down: np.ndarray,
    longwave_down: np.ndarray,
) -> dict[str, np.ndarray]:
    """Convert ERA5 downward-positive fluxes to positive ocean heat loss."""

    latent = np.asarray(latent_down, dtype=float)
    sensible = np.asarray(sensible_down, dtype=float)
    shortwave = np.asarray(shortwave_down, dtype=float)
    longwave = np.asarray(longwave_down, dtype=float)
    latent_loss = -latent
    sensible_loss = -sensible
    return {
        "latent_loss": latent_loss,
        "sensible_loss": sensible_loss,
        "turbulent_loss": latent_loss + sensible_loss,
        "net_ocean_loss": -(shortwave + longwave + latent + sensible),
    }


def audited_arrival_table() -> pd.DataFrame:
    """Return current-PPT arrival values from the mass-closed OHC analysis."""

    return pd.DataFrame(
        [
            {"year": year, **ARRIVAL_VALUES[year]}
            for year in EVENT_YEARS
        ]
    )


if __name__ == "__main__":
    print(audited_arrival_table().to_string(index=False))
