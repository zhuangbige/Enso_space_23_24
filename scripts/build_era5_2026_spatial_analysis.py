#!/usr/bin/env python3
"""Build ERA5 anomaly fields and regional diagnostics for 2026."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
SINGLE_DIR = ROOT / "data/raw/era5/era5_monthly_single_tropics_1deg_1982_2022_2026_jan_may"
SINGLE_AVGUA = SINGLE_DIR / "data_stream-moda_stepType-avgua.nc"
SINGLE_AVGAD = SINGLE_DIR / "data_stream-moda_stepType-avgad.nc"
PRESSURE = ROOT / "data/raw/era5/era5_monthly_pressure850_tropics_1deg_1982_2022_2026_jan_may.nc"
OUT_NPZ = ROOT / "data/interim/research_2026/current_2026_era5_spatial_anomalies.npz"
OUT_CSV = ROOT / "data/derived/research_2026/current_2026_era5_region_summary.csv"

REFERENCE_START = 1982
REFERENCE_END = 2022
PERIODS = {
    "JAN": (1,),
    "FEB": (2,),
    "MAR": (3,),
    "APR": (4,),
    "MAY": (5,),
    "JFM": (1, 2, 3),
    "FMA": (2, 3, 4),
    "MAM": (3, 4, 5),
    "AM_to_date": (4, 5),
}


@dataclass(frozen=True)
class Region:
    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


REGIONS = {
    "cwp_160e_140w": Region("cwp_160e_140w", -5, 5, 160, 220),
    "central_pacific_180_140w": Region("central_pacific_180_140w", -5, 5, 180, 220),
    "eastern_pacific_140w_100w": Region("eastern_pacific_140w_100w", -5, 5, 220, 260),
    "darwin_proxy": Region("darwin_proxy", -20, -5, 120, 140),
    "tahiti_proxy": Region("tahiti_proxy", -25, -10, 200, 220),
}


def _time_name(ds: xr.Dataset) -> str:
    if "valid_time" in ds.coords:
        return "valid_time"
    if "time" in ds.coords:
        return "time"
    raise ValueError("No time coordinate found")


def _standardize(ds: xr.Dataset) -> xr.Dataset:
    time_name = _time_name(ds)
    rename = {}
    if time_name != "time":
        rename[time_name] = "time"
    if "latitude" in ds.coords:
        rename["latitude"] = "lat"
    if "longitude" in ds.coords:
        rename["longitude"] = "lon"
    ds = ds.rename(rename)
    ds = ds.assign_coords(lon=(ds["lon"] % 360)).sortby("lon").sortby("lat")
    return ds


def _open_inputs() -> xr.Dataset:
    avgua = _standardize(xr.open_dataset(SINGLE_AVGUA))
    avgad = _standardize(xr.open_dataset(SINGLE_AVGAD))
    pressure = _standardize(xr.open_dataset(PRESSURE))
    if "pressure_level" in pressure.dims:
        pressure = pressure.sel(pressure_level=850).drop_vars("pressure_level")

    # Align precipitation time stamps (06 UTC) to the same monthly labels as analysis variables.
    avgad = avgad.assign_coords(time=avgua.time)

    ds = xr.merge(
        [
            avgua[["u10", "v10", "msl"]],
            avgad[["tp"]],
            pressure[["u", "v", "w"]].rename({"u": "u850", "v": "v850", "w": "omega850"}),
        ],
        compat="override",
    )
    ds["msl_hpa"] = ds["msl"] / 100.0
    ds["tp_mm_day"] = ds["tp"] * 1000.0
    return ds[["u10", "v10", "msl_hpa", "tp_mm_day", "u850", "v850", "omega850"]]


def _monthly_anomalies(ds: xr.Dataset) -> xr.Dataset:
    clim = ds.sel(time=slice(f"{REFERENCE_START}-01-01", f"{REFERENCE_END}-12-31")).groupby("time.month").mean("time")
    return ds.groupby("time.month") - clim


def _period_mean(anom: xr.Dataset, period: str) -> xr.Dataset:
    months = PERIODS[period]
    selected = anom.sel(time=(anom.time.dt.year == 2026) & (anom.time.dt.month.isin(months)))
    if selected.sizes.get("time", 0) != len(months):
        raise ValueError(f"Missing 2026 months for {period}: expected {months}, found {selected.time.values}")
    return selected.mean("time")


def _weighted_region_mean(da: xr.DataArray, region: Region) -> float:
    sub = da.sel(lat=slice(region.lat_min, region.lat_max), lon=slice(region.lon_min, region.lon_max))
    weights = np.cos(np.deg2rad(sub.lat))
    return float(sub.weighted(weights).mean(("lat", "lon"), skipna=True).values)


def _equatorial_hov(anom: xr.Dataset, var: str) -> np.ndarray:
    selected = anom[var].sel(time=(anom.time.dt.year == 2026), lat=slice(-5, 5))
    selected = selected.sortby("time")
    weights = np.cos(np.deg2rad(selected.lat))
    return selected.weighted(weights).mean("lat", skipna=True).values.astype(np.float32)


def main() -> int:
    ds = _open_inputs()
    anom = _monthly_anomalies(ds)
    lat = anom.lat.values.astype(np.float32)
    lon = anom.lon.values.astype(np.float32)
    periods = ["JAN", "FEB", "MAR", "APR", "MAY", "JFM", "FMA", "MAM", "AM_to_date"]
    variables = ["u10", "v10", "msl_hpa", "tp_mm_day", "u850", "v850", "omega850"]

    output: dict[str, object] = {
        "lat": lat,
        "lon": lon,
        "periods": np.asarray(periods),
        "variables": np.asarray(variables),
        "months": np.asarray(["JAN", "FEB", "MAR", "APR", "MAY"]),
        "reference_period": np.asarray(f"{REFERENCE_START}-{REFERENCE_END} monthly climatology"),
        "sources": np.asarray([str(SINGLE_AVGUA), str(SINGLE_AVGAD), str(PRESSURE)]),
        "u10_hov": _equatorial_hov(anom, "u10"),
        "u850_hov": _equatorial_hov(anom, "u850"),
        "tp_hov": _equatorial_hov(anom, "tp_mm_day"),
    }

    period_fields: dict[str, xr.Dataset] = {}
    for period in periods:
        period_fields[period] = _period_mean(anom, period)
        for var in variables:
            output[f"{var}_{period}"] = period_fields[period][var].values.astype(np.float32)

    rows = []
    for period in periods:
        fields = period_fields[period]
        for var in variables:
            for region_id, region in REGIONS.items():
                rows.append(
                    {
                        "period": period,
                        "metric": f"era5_{var}",
                        "region": region_id,
                        "anomaly": _weighted_region_mean(fields[var], region),
                        "unit": {
                            "u10": "m/s",
                            "v10": "m/s",
                            "msl_hpa": "hPa",
                            "tp_mm_day": "mm/day",
                            "u850": "m/s",
                            "v850": "m/s",
                            "omega850": "Pa/s",
                        }[var],
                        "anomaly_kind": "1982-2022 monthly climatology",
                        "source": "ERA5 monthly means via Copernicus CDS",
                    }
                )
        rows.append(
            {
                "period": period,
                "metric": "era5_soi_like_mslp",
                "region": "tahiti_minus_darwin",
                "anomaly": _weighted_region_mean(fields["msl_hpa"], REGIONS["tahiti_proxy"])
                - _weighted_region_mean(fields["msl_hpa"], REGIONS["darwin_proxy"]),
                "unit": "hPa",
                "anomaly_kind": "1982-2022 monthly climatology",
                "source": "ERA5 monthly means via Copernicus CDS",
            }
        )

    OUT_NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT_NPZ, **output)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(OUT_NPZ)
    print(OUT_CSV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
