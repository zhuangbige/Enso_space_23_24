#!/usr/bin/env python3
"""Fetch and derive January-June CPC OLR and SOI diagnostics.

The script reads NOAA/CPC Blended OLR daily means, the NOAA Interpolated OLR
monthly record, and the operational CPC SOI text products through NOAA/PSL.
The 1980-2014 Interpolated OLR record supplies the common climatology and
linear trend. An additive calendar-month bias correction fitted over the
1991-2014 overlap places the CPC Blended OLR event fields on that reference
scale before anomalies are calculated.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.request import urlopen

import netCDF4
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/noaa_cpc"
INTERIM_DIR = ROOT / "data/interim/research_2026"
DERIVED_DIR = ROOT / "data/derived/research_2026"

CPC_BLEND_OLR_URL = (
    "https://psl.noaa.gov/thredds/dodsC/"
    "Datasets/cpc_blended_olr-2.5deg/olr.day.mean.nc"
)
REFERENCE_OLR_URL = (
    "https://psl.noaa.gov/thredds/dodsC/"
    "Datasets/interp_OLR/olr.mon.mean.nc"
)
SOI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/soi"
EQUATORIAL_SOI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/reqsoi.for"

OUTPUT_NPZ = (
    INTERIM_DIR
    / "cpc_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014.npz"
)
OUTPUT_CSV = (
    DERIVED_DIR
    / "cpc_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014.csv"
)
OUTPUT_METADATA = (
    DERIVED_DIR
    / "cpc_olr_soi_jan_jun_2015_2023_2026_detrended_1980_2014_metadata.json"
)

YEARS = (2015, 2023, 2026)
MONTHS = tuple(range(1, 7))
BASELINE_START = 1980
BASELINE_END = 2014
MAP_LAT_BOUNDS = (-20.0, 20.0)
MAP_LON_BOUNDS = (100.0, 280.0)
REGIONS = {
    "indonesia_120e_170e": (-5.0, 5.0, 120.0, 170.0),
    "central_pacific_170e_140w": (-5.0, 5.0, 170.0, 220.0),
    "central_pacific_precip_box_180_140w": (-5.0, 5.0, 180.0, 220.0),
    "east_central_pacific_140w_110w": (-5.0, 5.0, 220.0, 250.0),
}


def download_text(url: str, destination: Path) -> str:
    with urlopen(url, timeout=60) as response:
        text = response.read().decode("utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return text


def numeric_tokens(line: str) -> list[float]:
    return [
        float(token)
        for token in re.findall(r"(?<!\d)[+-]?(?:\d+(?:\.\d*)?|\.\d+)", line)
    ]


def parse_cpc_soi_standardized(text: str) -> dict[int, np.ndarray]:
    marker = "STANDARDIZED    DATA"
    if marker not in text:
        raise ValueError("CPC SOI standardized-data block was not found")
    block = text.split(marker, 1)[1]
    rows: dict[int, np.ndarray] = {}
    for line in block.splitlines():
        values = numeric_tokens(line)
        if len(values) < 13:
            continue
        year = int(values[0])
        if 1900 <= year <= 2100:
            monthly = np.asarray(values[1:13], dtype=float)
            monthly[np.abs(monthly) >= 900] = np.nan
            rows[year] = monthly
    return rows


def parse_equatorial_soi(text: str) -> dict[int, np.ndarray]:
    rows: dict[int, np.ndarray] = {}
    for line in text.splitlines():
        values = numeric_tokens(line)
        if len(values) < 13:
            continue
        year = int(values[0])
        if 1900 <= year <= 2100:
            monthly = np.asarray(values[1:13], dtype=float)
            monthly[np.abs(monthly) >= 900] = np.nan
            rows[year] = monthly
    return rows


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
    numerator = np.nansum(subset * weights)
    denominator = np.sum(valid * weights)
    return float(numerator / denominator)


def decimal_year(year: np.ndarray, month: np.ndarray) -> np.ndarray:
    return year.astype(float) + (month.astype(float) - 0.5) / 12.0


def linear_detrend_grid(
    values: np.ndarray,
    time: np.ndarray,
    fit_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Remove the baseline-period least-squares trend at every grid cell."""
    original_shape = values.shape
    flat = values.reshape(values.shape[0], -1).astype(float)
    x = time[fit_mask].astype(float)
    y = flat[fit_mask, :]
    valid = np.isfinite(y)
    count = valid.sum(axis=0).astype(float)
    x2 = x[:, None]
    sum_x = (x2 * valid).sum(axis=0)
    sum_y = np.where(valid, y, 0.0).sum(axis=0)
    mean_x = np.divide(
        sum_x,
        count,
        out=np.full_like(count, np.nan, dtype=float),
        where=count > 24,
    )
    mean_y = np.divide(
        sum_y,
        count,
        out=np.full_like(count, np.nan, dtype=float),
        where=count > 24,
    )
    dx = np.where(valid, x2 - mean_x, 0.0)
    dy = np.where(valid, y - mean_y, 0.0)
    denominator = (dx * dx).sum(axis=0)
    numerator = (dx * dy).sum(axis=0)
    slope = np.divide(
        numerator,
        denominator,
        out=np.full_like(denominator, np.nan, dtype=float),
        where=denominator > 0,
    )
    intercept = mean_y - slope * mean_x
    trend = time[:, None] * slope[None, :] + intercept[None, :]
    detrended = flat - trend
    detrended[:, count <= 24] = np.nan
    return (
        detrended.reshape(original_shape).astype(np.float32),
        slope.reshape(original_shape[1:]).astype(np.float32),
    )


def monthly_mean_cube(
    daily_cube: np.ndarray,
    daily_dates: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    years = np.asarray([date.year for date in daily_dates], dtype=int)
    months = np.asarray([date.month for date in daily_dates], dtype=int)
    fields: list[np.ndarray] = []
    output_years: list[int] = []
    output_months: list[int] = []
    valid_days: list[int] = []
    for year in sorted(np.unique(years)):
        for month in range(1, 13):
            mask = (years == year) & (months == month)
            if not np.any(mask):
                continue
            cube = daily_cube[mask]
            fields.append(np.nanmean(cube, axis=0))
            output_years.append(int(year))
            output_months.append(month)
            valid_days.append(int(np.sum(np.any(np.isfinite(cube), axis=(1, 2)))))
    return (
        np.stack(fields).astype(np.float32),
        np.asarray(output_years, dtype=int),
        np.asarray(output_months, dtype=int),
        np.asarray(valid_days, dtype=int),
    )


def read_monthly_olr() -> tuple[
    np.ndarray,
    np.ndarray,
    dict[int, np.ndarray],
    dict[int, list[int]],
    str,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    reference = netCDF4.Dataset(REFERENCE_OLR_URL)
    try:
        reference_time = reference.variables["time"]
        reference_dates = np.asarray(
            netCDF4.num2date(
                reference_time[:],
                units=reference_time.units,
                calendar=getattr(reference_time, "calendar", "standard"),
            )
        )
        reference_lat_all = np.asarray(reference.variables["lat"][:], dtype=float)
        reference_lon_all = np.asarray(reference.variables["lon"][:], dtype=float)
        reference_lat_indices = np.where(
            (reference_lat_all >= MAP_LAT_BOUNDS[0])
            & (reference_lat_all <= MAP_LAT_BOUNDS[1])
        )[0]
        reference_lon_indices = np.where(
            (reference_lon_all >= MAP_LON_BOUNDS[0])
            & (reference_lon_all <= MAP_LON_BOUNDS[1])
        )[0]
        reference_lat_slice = slice(
            reference_lat_indices.min(),
            reference_lat_indices.max() + 1,
        )
        reference_lon_slice = slice(
            reference_lon_indices.min(),
            reference_lon_indices.max() + 1,
        )
        reference_lat = reference_lat_all[reference_lat_slice]
        reference_lon = reference_lon_all[reference_lon_slice]
        reference_indices = np.asarray(
            [
                index
                for index, date in enumerate(reference_dates)
                if BASELINE_START <= date.year <= BASELINE_END
            ],
            dtype=int,
        )
        baseline_monthly = reference.variables["olr"][
            reference_indices.min() : reference_indices.max() + 1,
            reference_lat_slice,
            reference_lon_slice,
        ]
        baseline_monthly = np.ma.filled(
            baseline_monthly,
            np.nan,
        ).astype(np.float32)
        baseline_dates = reference_dates[
            reference_indices.min() : reference_indices.max() + 1
        ]
        baseline_years = np.asarray([date.year for date in baseline_dates], dtype=int)
        baseline_months = np.asarray([date.month for date in baseline_dates], dtype=int)
        if len(baseline_monthly) != (BASELINE_END - BASELINE_START + 1) * 12:
            raise ValueError("The 1980-2014 OLR monthly baseline is incomplete")
        if reference_lat[0] > reference_lat[-1]:
            reference_lat = reference_lat[::-1]
            baseline_monthly = baseline_monthly[:, ::-1, :]
    finally:
        reference.close()

    dataset = netCDF4.Dataset(CPC_BLEND_OLR_URL)
    try:
        time_var = dataset.variables["time"]
        dates = np.asarray(
            netCDF4.num2date(
                time_var[:],
                units=time_var.units,
                calendar=getattr(time_var, "calendar", "standard"),
            )
        )
        latest_date = dates[-1].strftime("%Y-%m-%d")
        lat_all = np.asarray(dataset.variables["lat"][:], dtype=float)
        lon_all = np.asarray(dataset.variables["lon"][:], dtype=float)
        lat_indices = np.where(
            (lat_all >= MAP_LAT_BOUNDS[0]) & (lat_all <= MAP_LAT_BOUNDS[1])
        )[0]
        lon_indices = np.where(
            (lon_all >= MAP_LON_BOUNDS[0]) & (lon_all <= MAP_LON_BOUNDS[1])
        )[0]
        lat_slice = slice(lat_indices.min(), lat_indices.max() + 1)
        lon_slice = slice(lon_indices.min(), lon_indices.max() + 1)
        lat = lat_all[lat_slice]
        lon = lon_all[lon_slice]
        source_monthly_fields: dict[int, np.ndarray] = {}
        valid_days: dict[int, list[int]] = {}

        overlap_indices = np.asarray(
            [
                index
                for index, date in enumerate(dates)
                if 1991 <= date.year <= BASELINE_END
            ],
            dtype=int,
        )
        print(
            f"read CPC Blended OLR overlap 1991-{BASELINE_END}: "
            f"{len(overlap_indices)} daily fields",
            flush=True,
        )
        overlap_daily = dataset.variables["olr"][
            overlap_indices.min() : overlap_indices.max() + 1,
            lat_slice,
            lon_slice,
        ]
        overlap_daily = np.ma.filled(overlap_daily, np.nan).astype(np.float32)
        overlap_dates = dates[overlap_indices.min() : overlap_indices.max() + 1]
        (
            overlap_monthly,
            overlap_years,
            overlap_months,
            _overlap_valid_days,
        ) = monthly_mean_cube(overlap_daily, overlap_dates)
        del overlap_daily
        if len(overlap_monthly) != (BASELINE_END - 1991 + 1) * 12:
            raise ValueError("The 1991-2014 CPC Blended OLR overlap is incomplete")

        for year in YEARS:
            fields = []
            counts = []
            for month in MONTHS:
                time_indices = np.asarray(
                    [
                        index
                        for index, date in enumerate(dates)
                        if date.year == year and date.month == month
                    ],
                    dtype=int,
                )
                if len(time_indices) == 0:
                    raise ValueError(f"No CPC OLR data found for {year}-{month:02d}")
                cube = dataset.variables["olr"][
                    time_indices.min() : time_indices.max() + 1,
                    lat_slice,
                    lon_slice,
                ]
                cube = np.ma.filled(cube, np.nan).astype(np.float32)
                fields.append(np.nanmean(cube, axis=0))
                counts.append(int(np.sum(np.any(np.isfinite(cube), axis=(1, 2)))))
            source_monthly_fields[year] = np.stack(fields).astype(np.float32)
            valid_days[year] = counts

        if lat[0] > lat[-1]:
            lat = lat[::-1]
            overlap_monthly = overlap_monthly[:, ::-1, :]
            source_monthly_fields = {
                year: fields[:, ::-1, :]
                for year, fields in source_monthly_fields.items()
            }
        if not np.allclose(lat, reference_lat) or not np.allclose(lon, reference_lon):
            raise ValueError("Reference and CPC Blended OLR grids do not match")

        reference_lookup = {
            (int(year), int(month)): baseline_monthly[index]
            for index, (year, month) in enumerate(
                zip(baseline_years, baseline_months, strict=True)
            )
        }
        overlap_reference = np.stack(
            [
                reference_lookup[(int(year), int(month))]
                for year, month in zip(
                    overlap_years,
                    overlap_months,
                    strict=True,
                )
            ]
        ).astype(np.float32)
        harmonization_bias = np.stack(
            [
                np.nanmean(
                    (
                        overlap_monthly
                        - overlap_reference
                    )[overlap_months == month],
                    axis=0,
                )
                for month in range(1, 13)
            ]
        ).astype(np.float32)

        climatology = np.stack(
            [
                np.nanmean(
                    baseline_monthly[baseline_months == month],
                    axis=0,
                )
                for month in range(1, 13)
            ]
        ).astype(np.float32)
        baseline_anomalies = (
            baseline_monthly - climatology[baseline_months - 1]
        ).astype(np.float32)
        target_fields = np.concatenate(
            [source_monthly_fields[year] for year in YEARS],
            axis=0,
        )
        target_years = np.repeat(np.asarray(YEARS, dtype=int), len(MONTHS))
        target_months = np.tile(np.asarray(MONTHS, dtype=int), len(YEARS))
        target_fields = (
            target_fields - harmonization_bias[target_months - 1]
        ).astype(np.float32)
        target_anomalies = (
            target_fields - climatology[target_months - 1]
        ).astype(np.float32)
        combined = np.concatenate([baseline_anomalies, target_anomalies], axis=0)
        combined_years = np.concatenate([baseline_years, target_years])
        combined_months = np.concatenate([baseline_months, target_months])
        time = decimal_year(combined_years, combined_months)
        fit_mask = combined_years <= BASELINE_END
        detrended, trend_slope = linear_detrend_grid(combined, time, fit_mask)
        target_detrended = detrended[len(baseline_anomalies) :]
        monthly_fields = {
            year: target_detrended[index * len(MONTHS) : (index + 1) * len(MONTHS)]
            for index, year in enumerate(YEARS)
        }

        return (
            lat,
            lon,
            monthly_fields,
            valid_days,
            latest_date,
            climatology,
            trend_slope,
            harmonization_bias,
        )
    finally:
        dataset.close()


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    soi_text = download_text(SOI_URL, RAW_DIR / "soi_monthly.txt")
    equatorial_soi_text = download_text(
        EQUATORIAL_SOI_URL,
        RAW_DIR / "equatorial_soi_monthly.txt",
    )
    soi = parse_cpc_soi_standardized(soi_text)
    equatorial_soi = parse_equatorial_soi(equatorial_soi_text)

    for year in YEARS:
        if year not in soi or year not in equatorial_soi:
            raise ValueError(f"CPC SOI data are incomplete for {year}")
        if not np.all(np.isfinite(soi[year][:6])):
            raise ValueError(f"Traditional SOI is incomplete for January-June {year}")
        if not np.all(np.isfinite(equatorial_soi[year][:6])):
            raise ValueError(f"Equatorial SOI is incomplete for January-June {year}")

    (
        lat,
        lon,
        monthly_olr,
        valid_days,
        latest_date,
        olr_climatology,
        olr_trend_slope,
        olr_harmonization_bias,
    ) = read_monthly_olr()

    rows = []
    for year in YEARS:
        for month_index, month in enumerate(MONTHS):
            field = monthly_olr[year][month_index]
            regional = {
                region: cosine_weighted_region_mean(field, lat, lon, bounds)
                for region, bounds in REGIONS.items()
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
                    "valid_olr_days": valid_days[year][month_index],
                }
            )

    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT_CSV, index=False, float_format="%.5f")
    np.savez_compressed(
        OUTPUT_NPZ,
        lat=lat.astype(np.float32),
        lon=lon.astype(np.float32),
        olr_2015=monthly_olr[2015],
        olr_2023=monthly_olr[2023],
        olr_2026=monthly_olr[2026],
        months=np.asarray(MONTHS, dtype=np.int16),
        years=np.asarray(YEARS, dtype=np.int16),
        soi_2015=soi[2015][:6].astype(np.float32),
        soi_2023=soi[2023][:6].astype(np.float32),
        soi_2026=soi[2026][:6].astype(np.float32),
        equatorial_soi_2015=equatorial_soi[2015][:6].astype(np.float32),
        equatorial_soi_2023=equatorial_soi[2023][:6].astype(np.float32),
        equatorial_soi_2026=equatorial_soi[2026][:6].astype(np.float32),
        olr_latest_date=np.asarray(latest_date),
        olr_anomaly_baseline=np.asarray(
            "1980-2014 calendar-month climatology, 1980-2014 linear trend removed"
        ),
        olr_reference_climatology_1980_2014=olr_climatology,
        olr_linear_trend_slope_wm2_per_year=olr_trend_slope,
        olr_harmonization_bias_cbo_minus_interp_wm2=olr_harmonization_bias,
        olr_units=np.asarray("W m-2"),
    )
    metadata = {
        "olr_current_source": CPC_BLEND_OLR_URL,
        "olr_reference_source": REFERENCE_OLR_URL,
        "soi_source": SOI_URL,
        "equatorial_soi_source": EQUATORIAL_SOI_URL,
        "olr_latest_date": latest_date,
        "olr_anomaly_baseline": (
            "1980-2014 calendar-month climatology, "
            "1980-2014 linear trend removed"
        ),
        "olr_harmonization_method": (
            "The NOAA Interpolated OLR monthly record supplies the 1980-2014 "
            "calendar-month climatology and linear trend. CPC Blended OLR daily "
            "means are converted to monthly means, then adjusted by the "
            "calendar-month mean CPC-Blended-minus-Interpolated-OLR difference "
            "over their 1991-2014 overlap. The adjusted event fields are finally "
            "expressed as 1980-2014 anomalies with the 1980-2014 grid-cell linear "
            "trend removed."
        ),
        "olr_reference_period": f"{BASELINE_START}-{BASELINE_END}",
        "olr_harmonization_overlap": "1991-2014",
        "years": list(YEARS),
        "months": list(MONTHS),
        "valid_olr_days": {str(year): valid_days[year] for year in YEARS},
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
            "olr": "negative denotes enhanced high-cloud/deep-convection signal",
            "soi": "negative denotes an El Nino-like Tahiti-Darwin pressure pattern",
            "equatorial_soi": "negative denotes an El Nino-like equatorial pressure pattern",
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
