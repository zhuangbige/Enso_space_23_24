#!/usr/bin/env python3
"""Build unified-baseline ERA5 OLR and CPC SOI diagnostics.

For each calendar month, the script subtracts the 1980-2014 ERA5 climatology
and removes the grid-cell linear trend fitted over those same 35 years. This
matches the processing used for the report's ERA5 winds and precipitation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data/raw/era5/olr_monthly_1deg_1980_2026"
SOI_DIR = ROOT / "data/raw/noaa_cpc"
INTERIM_DIR = ROOT / "data/interim/research_2026"
DERIVED_DIR = ROOT / "data/derived/research_2026"

OUTPUT_NPZ = (
    INTERIM_DIR
    / "era5_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014.npz"
)
OUTPUT_CSV = (
    DERIVED_DIR
    / "era5_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014.csv"
)
OUTPUT_METADATA = (
    DERIVED_DIR
    / "era5_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014_metadata.json"
)

YEARS = (2015, 2023, 2026)
MONTHS = tuple(range(1, 7))
BASELINE_START = 1980
BASELINE_END = 2014
VARIABLE_CANDIDATES = (
    "avg_tnlwrf",
    "mtnlwrf",
    "mean_top_net_long_wave_radiation_flux",
    "var235040",
)
REGIONS = {
    "indonesia_120e_170e": (-5.0, 5.0, 120.0, 170.0),
    "central_pacific_170e_140w": (-5.0, 5.0, 170.0, 220.0),
    "central_pacific_precip_box_180_140w": (-5.0, 5.0, 180.0, 220.0),
    "east_central_pacific_140w_110w": (-5.0, 5.0, 220.0, 250.0),
}


def numeric_tokens(line: str) -> list[float]:
    return [
        float(token)
        for token in re.findall(r"(?<!\d)[+-]?(?:\d+(?:\.\d*)?|\.\d+)", line)
    ]


def parse_cpc_soi_standardized(text: str) -> dict[int, np.ndarray]:
    marker = "STANDARDIZED    DATA"
    if marker not in text:
        raise ValueError("CPC SOI standardized-data block was not found")
    rows: dict[int, np.ndarray] = {}
    for line in text.split(marker, 1)[1].splitlines():
        values = numeric_tokens(line)
        if len(values) >= 13 and 1900 <= int(values[0]) <= 2100:
            rows[int(values[0])] = np.asarray(values[1:13], dtype=float)
    return rows


def parse_equatorial_soi(text: str) -> dict[int, np.ndarray]:
    rows: dict[int, np.ndarray] = {}
    for line in text.splitlines():
        values = numeric_tokens(line)
        if len(values) >= 13 and 1900 <= int(values[0]) <= 2100:
            rows[int(values[0])] = np.asarray(values[1:13], dtype=float)
    return rows


def standardize_part(path: Path) -> xr.DataArray:
    ds = xr.open_dataset(path)
    rename = {}
    if "valid_time" in ds.coords:
        rename["valid_time"] = "time"
    if "latitude" in ds.coords:
        rename["latitude"] = "lat"
    if "longitude" in ds.coords:
        rename["longitude"] = "lon"
    ds = ds.rename(rename)
    variable = next(
        (candidate for candidate in VARIABLE_CANDIDATES if candidate in ds),
        None,
    )
    if variable is None:
        raise ValueError(f"ERA5 OLR flux variable not found in {path}")
    olr = (-ds[variable]).rename("olr")
    olr.attrs.update(
        {
            "long_name": "Outgoing longwave radiation at the top of the atmosphere",
            "units": "W m-2",
            "conversion": (
                "OLR = -1 × ERA5 mean top net long-wave radiation flux; "
                "ERA5 vertical fluxes are positive downward"
            ),
        }
    )
    olr = olr.assign_coords(lon=(olr.lon % 360)).sortby("lon").sortby("lat")
    return olr.load()


def open_month(month: int) -> xr.DataArray:
    west = standardize_part(
        INPUT_DIR / f"era5_olr_west_m{month:02d}_1980_2026_1deg.nc"
    )
    east = standardize_part(
        INPUT_DIR / f"era5_olr_east_m{month:02d}_1980_2026_1deg.nc"
    )
    combined = xr.concat([west, east], dim="lon").sortby("lon")
    unique_lon, unique_indices = np.unique(
        combined.lon.values,
        return_index=True,
    )
    combined = combined.isel(lon=np.sort(unique_indices)).assign_coords(lon=unique_lon)
    if combined.sizes["time"] != 47:
        raise ValueError(f"Unexpected time count for month {month}: {combined.sizes}")
    if not np.allclose(combined.lon.values, np.arange(100.0, 281.0, 1.0)):
        raise ValueError(f"Longitude grid is incomplete for month {month}")
    return combined


def linear_detrend_grid(
    values: np.ndarray,
    years: np.ndarray,
    fit_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    original_shape = values.shape
    flat = values.reshape(values.shape[0], -1).astype(float)
    x = years[fit_mask].astype(float)
    y = flat[fit_mask]
    valid = np.isfinite(y)
    count = valid.sum(axis=0).astype(float)
    x2 = x[:, None]
    sum_x = (x2 * valid).sum(axis=0)
    sum_y = np.where(valid, y, 0.0).sum(axis=0)
    mean_x = np.divide(
        sum_x,
        count,
        out=np.full_like(count, np.nan),
        where=count >= 30,
    )
    mean_y = np.divide(
        sum_y,
        count,
        out=np.full_like(count, np.nan),
        where=count >= 30,
    )
    dx = np.where(valid, x2 - mean_x, 0.0)
    dy = np.where(valid, y - mean_y, 0.0)
    denominator = (dx * dx).sum(axis=0)
    slope = np.divide(
        (dx * dy).sum(axis=0),
        denominator,
        out=np.full_like(denominator, np.nan),
        where=denominator > 0,
    )
    intercept = mean_y - slope * mean_x
    detrended = flat - (
        years[:, None].astype(float) * slope[None, :] + intercept[None, :]
    )
    detrended[:, count < 30] = np.nan
    return (
        detrended.reshape(original_shape).astype(np.float32),
        slope.reshape(original_shape[1:]).astype(np.float32),
    )


def build_event_fields() -> tuple[
    np.ndarray,
    np.ndarray,
    dict[int, np.ndarray],
    np.ndarray,
    np.ndarray,
]:
    event_fields = {year: [] for year in YEARS}
    climatologies: list[np.ndarray] = []
    slopes: list[np.ndarray] = []
    lat = None
    lon = None
    for month in MONTHS:
        monthly = open_month(month)
        years = monthly.time.dt.year.values.astype(int)
        if set(years) != set(range(1980, 2027)):
            raise ValueError(f"Year coverage is incomplete for month {month}")
        baseline = (years >= BASELINE_START) & (years <= BASELINE_END)
        if int(baseline.sum()) != 35:
            raise ValueError(f"Expected 35 baseline years for month {month}")
        climatology = monthly.isel(time=np.where(baseline)[0]).mean(
            "time",
            skipna=True,
        )
        anomalies = monthly - climatology
        detrended, slope = linear_detrend_grid(
            anomalies.transpose("time", "lat", "lon").values,
            years,
            baseline,
        )
        for year in YEARS:
            target = np.where(years == year)[0]
            if len(target) != 1:
                raise ValueError(f"Expected one record for {year}-{month:02d}")
            event_fields[year].append(detrended[target[0]])
        climatologies.append(climatology.values.astype(np.float32))
        slopes.append(slope)
        lat = monthly.lat.values.astype(np.float32)
        lon = monthly.lon.values.astype(np.float32)
    return (
        lat,
        lon,
        {
            year: np.stack(fields).astype(np.float32)
            for year, fields in event_fields.items()
        },
        np.stack(climatologies).astype(np.float32),
        np.stack(slopes).astype(np.float32),
    )


def cosine_weighted_region_mean(
    field: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    bounds: tuple[float, float, float, float],
) -> float:
    lat0, lat1, lon0, lon1 = bounds
    lat_mask = (lat >= lat0) & (lat <= lat1)
    lon_mask = (lon >= lon0) & (lon <= lon1)
    subset = field[np.ix_(lat_mask, lon_mask)]
    weights = np.cos(np.deg2rad(lat[lat_mask]))[:, None]
    valid = np.isfinite(subset)
    return float(
        np.nansum(subset * weights)
        / np.sum(valid * weights)
    )


def main() -> int:
    soi_path = SOI_DIR / "soi_monthly.txt"
    equatorial_path = SOI_DIR / "equatorial_soi_monthly.txt"
    for path in (soi_path, equatorial_path):
        if not path.exists():
            raise FileNotFoundError(path)
    soi = parse_cpc_soi_standardized(soi_path.read_text(encoding="utf-8"))
    equatorial_soi = parse_equatorial_soi(
        equatorial_path.read_text(encoding="utf-8")
    )

    lat, lon, monthly_olr, climatology, trend_slope = build_event_fields()
    if not np.all(np.isfinite(monthly_olr[2026])):
        raise ValueError("2026 ERA5 OLR contains missing values")

    rows = []
    for year in YEARS:
        for month_index, month in enumerate(MONTHS):
            field = monthly_olr[year][month_index]
            regional = {
                name: cosine_weighted_region_mean(field, lat, lon, bounds)
                for name, bounds in REGIONS.items()
            }
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "soi_standardized": float(soi[year][month - 1]),
                    "equatorial_soi_standardized": float(
                        equatorial_soi[year][month - 1]
                    ),
                    "olr_indonesia_120e_170e_wm2": regional[
                        "indonesia_120e_170e"
                    ],
                    "olr_central_pacific_170e_140w_wm2": regional[
                        "central_pacific_170e_140w"
                    ],
                    "olr_central_pacific_180_140w_wm2": regional[
                        "central_pacific_precip_box_180_140w"
                    ],
                    "olr_east_central_pacific_140w_110w_wm2": regional[
                        "east_central_pacific_140w_110w"
                    ],
                    "olr_cp_minus_indonesia_wm2": (
                        regional["central_pacific_170e_140w"]
                        - regional["indonesia_120e_170e"]
                    ),
                }
            )

    table = pd.DataFrame(rows)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT_CSV, index=False, float_format="%.5f")
    np.savez_compressed(
        OUTPUT_NPZ,
        lat=lat,
        lon=lon,
        months=np.asarray(MONTHS, dtype=np.int16),
        years=np.asarray(YEARS, dtype=np.int16),
        olr_2015=monthly_olr[2015],
        olr_2023=monthly_olr[2023],
        olr_2026=monthly_olr[2026],
        soi_2015=soi[2015][:6].astype(np.float32),
        soi_2023=soi[2023][:6].astype(np.float32),
        soi_2026=soi[2026][:6].astype(np.float32),
        equatorial_soi_2015=equatorial_soi[2015][:6].astype(np.float32),
        equatorial_soi_2023=equatorial_soi[2023][:6].astype(np.float32),
        equatorial_soi_2026=equatorial_soi[2026][:6].astype(np.float32),
        olr_climatology_1980_2014=climatology,
        olr_linear_trend_slope_wm2_per_year=trend_slope,
        olr_anomaly_baseline=np.asarray(
            "1980-2014 calendar-month climatology, "
            "same-calendar-month 1980-2014 linear trend removed"
        ),
        olr_units=np.asarray("W m-2"),
    )
    metadata = {
        "olr_source": (
            "Copernicus Climate Data Store, "
            "reanalysis-era5-single-levels-monthly-means"
        ),
        "olr_variable": "mean_top_net_long_wave_radiation_flux",
        "olr_conversion": (
            "OLR is the negative of ERA5 mean top net long-wave radiation flux "
            "because ERA5 vertical fluxes are positive downward."
        ),
        "olr_anomaly_method": (
            "For each calendar month and grid cell, subtract the 1980-2014 "
            "climatology and remove the linear trend fitted across the same "
            "1980-2014 years."
        ),
        "olr_grid": "1.0 degree",
        "olr_domain": "20S-20N, 100E-80W",
        "years": list(YEARS),
        "months": list(MONTHS),
        "soi_source": "https://www.cpc.ncep.noaa.gov/data/indices/soi",
        "equatorial_soi_source": (
            "https://www.cpc.ncep.noaa.gov/data/indices/reqsoi.for"
        ),
        "regions": {
            name: {
                "lat_min": bounds[0],
                "lat_max": bounds[1],
                "lon_min_east": bounds[2],
                "lon_max_east": bounds[3],
            }
            for name, bounds in REGIONS.items()
        },
        "sign_conventions": {
            "olr": "negative anomaly denotes enhanced deep convection",
            "soi": "negative denotes an El Nino-like pressure pattern",
        },
    }
    OUTPUT_METADATA.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(OUTPUT_NPZ)
    print(OUTPUT_CSV)
    print(OUTPUT_METADATA)
    print(table.loc[table["year"].eq(2026)].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
