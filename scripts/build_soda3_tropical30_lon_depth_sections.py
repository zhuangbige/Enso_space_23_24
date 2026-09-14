#!/usr/bin/env python3
"""Build 30S--30N mean SODA3 longitude-depth sections for ENSO events.

The original project sections use a 5S--5N cosine-latitude-weighted mean.
This companion product repeats the same January--June 1980--2024
same-calendar-month detrending workflow after expanding the latitude mean to
30S--30N.  Only the outer latitude bands are fetched remotely; the validated
local 5S--5N temperature archive supplies the equatorial band.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((ROOT / "scripts").resolve()))

import build_soda3_tropical_ohc300 as tropical  # noqa: E402
import build_soda3_warm_core_meridional_sections as meridional  # noqa: E402
import plot_soda3_monthly_ohc_vertical_sections as original  # noqa: E402


EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
YEARS = np.arange(1980, 2025, dtype=int)
LAT_BOUNDS = (-30.0, 30.0)
RHO0 = tropical.RHO0
CP0 = tropical.CP0

EQUATORIAL_TEMP_FILE = tropical.DEPTH_SOURCE
OUT_DIR = ROOT / "data/interim/research_2026/soda3_lon_depth_sections_30s30n"
CACHE_DIR = OUT_DIR / "yearly_outer_latitude_sums"
OUT_FILE = (
    ROOT
    / "data/derived/research_2026"
    / "soda3_ohc_lon_depth_sections_30s30n_1997_2015_2023_1980_2024_detrended.nc"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def weighted_latitude_sums(field: np.ndarray, latitude: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return cosine-latitude numerator and denominator along the latitude axis."""
    if field.shape[-2] != latitude.size:
        raise ValueError(f"Latitude length mismatch: {field.shape} and {latitude.shape}")
    weights = np.cos(np.deg2rad(latitude)).reshape(
        (1,) * (field.ndim - 2) + (latitude.size, 1)
    )
    finite = np.isfinite(field)
    numerator = np.nansum(field * weights, axis=-2)
    denominator = np.sum(finite * weights, axis=-2)
    return numerator.astype(np.float32), denominator.astype(np.float32)


def cache_path(year: int) -> Path:
    return CACHE_DIR / f"soda3_tropical30_outer_lat_sums_{year}_jan_jun.npz"


def valid_cache(year: int) -> bool:
    path = cache_path(year)
    if not path.exists():
        return False
    try:
        with np.load(path) as data:
            return (
                int(data["year"]) == year
                and data["temperature_weighted_sum"].shape == (6, 20, 320)
                and data["valid_weight_sum"].shape == (6, 20, 320)
            )
    except Exception:
        return False


def save_cache(
    year: int,
    numerator: np.ndarray,
    denominator: np.ndarray,
) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(year)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        temporary,
        year=np.int32(year),
        months=np.asarray(MONTHS, dtype=np.int16),
        temperature_weighted_sum=numerator.astype(np.float32),
        valid_weight_sum=denominator.astype(np.float32),
    )
    temporary.replace(path)
    return path


def empty_sums() -> tuple[np.ndarray, np.ndarray]:
    shape = (len(MONTHS), tropical.UPPER_300M_LEVELS, 320)
    return np.zeros(shape, dtype=np.float32), np.zeros(shape, dtype=np.float32)


def add_band(
    numerator: np.ndarray,
    denominator: np.ndarray,
    field: np.ndarray,
    latitude: np.ndarray,
    month_index: int,
    depth_index: int,
) -> None:
    band_num, band_den = weighted_latitude_sums(field, latitude)
    numerator[month_index, depth_index] += band_num
    denominator[month_index, depth_index] += band_den


def fetch_netcdf3_year(year: int) -> Path:
    url = tropical.URL_TEMPLATE.format(year=year)
    layout = tropical.fetch_layout(url)
    requests: dict[tuple[int, int], tuple[str, int, int, int]] = {}
    for month_index in range(len(MONTHS)):
        for depth_index in range(tropical.UPPER_300M_LEVELS):
            for band, (lat_start, lat_stop) in meridional.SECTION_LAT_BANDS.items():
                bounds = tropical.range_for_band(
                    layout,
                    month_index,
                    depth_index,
                    lat_start,
                    lat_stop,
                )
                requests[bounds] = (band, month_index, depth_index, lat_start)
    parts: dict[tuple[int, int], bytes] = {}
    bounds_list = list(requests)
    for first in range(0, len(bounds_list), 100):
        batch = bounds_list[first : first + 100]
        range_header = ",".join(f"{start}-{end}" for start, end in batch)
        content_type, body = tropical.http_read(url, range_header=range_header)
        parts.update(tropical.parse_multipart(content_type, body))
    if set(parts) != set(requests):
        raise ValueError(f"Incomplete multipart response for {year}")

    numerator, denominator = empty_sums()
    for bounds, payload in parts.items():
        band, month_index, depth_index, lat_start = requests[bounds]
        lat_stop = meridional.SECTION_LAT_BANDS[band][1]
        field = meridional.decode_band_payload_full(payload, lat_start, lat_stop)
        latitude = -74.75 + 0.5 * np.arange(lat_start, lat_stop + 1)
        add_band(
            numerator,
            denominator,
            field,
            latitude,
            month_index,
            depth_index,
        )
    return save_cache(year, numerator, denominator)


def fetch_netcdf4_year(year: int) -> Path:
    fsspec = tropical.import_fsspec()
    url = tropical.URL_TEMPLATE.format(year=year)
    remote = fsspec.open(
        url,
        "rb",
        block_size=8 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    numerator, denominator = empty_sums()
    try:
        with tropical.h5py.File(remote, "r") as dataset:
            expected_shape = (
                12,
                tropical.NDEPTH,
                tropical.GLOBAL_NLAT,
                tropical.GLOBAL_NLON,
            )
            if dataset["temp"].shape != expected_shape:
                raise ValueError(f"Unexpected NetCDF4 SODA temp shape for {year}")
            for month_index in range(len(MONTHS)):
                for depth_index in range(tropical.UPPER_300M_LEVELS):
                    plane = np.asarray(
                        dataset["temp"][month_index, depth_index, :, :],
                        dtype=np.float32,
                    )
                    for lat_start, lat_stop in meridional.SECTION_LAT_BANDS.values():
                        field = plane[
                            lat_start : lat_stop + 1,
                            tropical.LON_START_INDEX : tropical.LON_STOP_INDEX + 1,
                        ]
                        field[field <= -1.0e10] = np.nan
                        latitude = -74.75 + 0.5 * np.arange(lat_start, lat_stop + 1)
                        add_band(
                            numerator,
                            denominator,
                            field,
                            latitude,
                            month_index,
                            depth_index,
                        )
    finally:
        remote.close()
    return save_cache(year, numerator, denominator)


def fetch_year(year: int, force: bool) -> Path:
    if not force and valid_cache(year):
        print(f"Tropical-30 section cache reused: {year}", flush=True)
        return cache_path(year)
    url = tropical.URL_TEMPLATE.format(year=year)
    _, signature = tropical.http_read(url, range_header="0-3")
    if signature.startswith(b"CDF"):
        path = fetch_netcdf3_year(year)
    elif signature == b"\x89HDF":
        path = fetch_netcdf4_year(year)
    else:
        raise ValueError(f"Unrecognized SODA file signature for {year}: {signature!r}")
    print(f"Tropical-30 longitude-depth latitude sums complete: {year}", flush=True)
    return path


def equatorial_sums() -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex, np.ndarray, np.ndarray]:
    with xr.open_dataset(EQUATORIAL_TEMP_FILE, engine="netcdf4") as dataset:
        temperature = dataset["temp"].load()
    if temperature.shape != (270, 20, 20, 320):
        raise ValueError(f"Unexpected equatorial temperature shape: {temperature.shape}")
    numerator, denominator = weighted_latitude_sums(
        temperature.values.astype(np.float32),
        temperature.lat.values.astype(float),
    )
    return (
        numerator,
        denominator,
        pd.DatetimeIndex(temperature.time.values),
        temperature.depth.values.astype(float),
        temperature.lon.values.astype(float),
    )


def assemble_output() -> Path:
    eq_num, eq_den, times, depth, longitude = equatorial_sums()
    outer_num = []
    outer_den = []
    for year in YEARS:
        with np.load(cache_path(int(year))) as data:
            outer_num.append(np.asarray(data["temperature_weighted_sum"], dtype=np.float32))
            outer_den.append(np.asarray(data["valid_weight_sum"], dtype=np.float32))
    outer_num_values = np.stack(outer_num, axis=0).reshape(270, 20, 320)
    outer_den_values = np.stack(outer_den, axis=0).reshape(270, 20, 320)
    total_num = outer_num_values + eq_num
    total_den = outer_den_values + eq_den
    mean_temperature = np.divide(
        total_num,
        total_den,
        out=np.full(total_num.shape, np.nan, dtype=np.float32),
        where=total_den > 0,
    )
    mean_da = xr.DataArray(
        mean_temperature,
        dims=("time", "depth", "lon"),
        coords={"time": times, "depth": depth, "lon": longitude},
        name="temperature",
        attrs={
            "units": "degC",
            "long_name": "30S-30N cosine-latitude-weighted potential temperature",
        },
    )
    anomaly = original.detrended_same_month_anomaly(mean_da)
    event_mask = anomaly.time.dt.year.isin(EVENTS) & anomaly.time.dt.month.isin(MONTHS)
    selected = anomaly.where(event_mask, drop=True)
    if selected.sizes.get("time") != len(EVENTS) * len(MONTHS):
        raise ValueError(f"Unexpected event time count: {selected.sizes.get('time')}")
    heat_density = selected * np.float32(RHO0 * CP0 / 1.0e6)
    dataset = xr.Dataset(
        data_vars={
            "temperature_anomaly": selected.astype(np.float32),
            "heat_content_density_anomaly": heat_density.astype(np.float32),
        },
        attrs={
            "title": "SODA3.15.2 30S-30N mean upper-ocean heat-content vertical diagnostics",
            "source": "SODA3.15.2 official UMD annual files and validated local equatorial archive",
            "events": ", ".join(str(event) for event in EVENTS),
            "months": "January-June",
            "latitude_average": "30S to 30N, cosine-latitude weighted over valid ocean cells",
            "anomaly_definition": "1980-2024 same-calendar-month climatology and linear trend removed",
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
        },
    )
    dataset.temperature_anomaly.attrs.update(
        units="degC",
        long_name="Detrended 30S-30N mean potential-temperature anomaly",
    )
    dataset.heat_content_density_anomaly.attrs.update(
        units="MJ m-3",
        long_name="Volumetric heat-content anomaly rho0*cp0*T_prime",
    )
    if np.nanmax(np.abs(dataset.temperature_anomaly.values)) > 8.0:
        raise ValueError("Implausible event temperature anomaly")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        name: {"zlib": True, "complevel": 4, "dtype": "float32"}
        for name in dataset.data_vars
    }
    dataset.to_netcdf(OUT_FILE, engine="netcdf4", encoding=encoding)
    values = dataset.heat_content_density_anomaly.values.astype(float)
    print(
        "Tropical-30 longitude-depth diagnostics: "
        f"shape={values.shape}, finite={np.isfinite(values).mean():.4f}, "
        f"range=[{np.nanmin(values):.3f}, {np.nanmax(values):.3f}] MJ m-3",
        flush=True,
    )
    print(OUT_FILE, flush=True)
    return OUT_FILE


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 4:
        raise ValueError("--workers must be between 1 and 4")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_year, int(year), args.force): int(year)
            for year in YEARS
        }
        for future in as_completed(futures):
            year = futures[future]
            try:
                future.result()
            except Exception as exc:
                raise RuntimeError(f"Tropical-30 section extraction failed for {year}") from exc
    assemble_output()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
