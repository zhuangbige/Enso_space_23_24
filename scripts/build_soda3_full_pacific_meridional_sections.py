#!/usr/bin/env python3
"""Build fixed full-Pacific SODA3 latitude-depth sections for ENSO events.

Potential temperature is averaged at every native latitude and depth across
the fixed 120E--80W longitude domain.  January--June anomalies remove the
1980--2024 same-calendar-month climatology and linear trend.  The resulting
30S--30N, 0--300 m sections are directly comparable across months because the
longitude sampling never follows the migrating warm core.
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
BASELINE = (1980, 2024)
RHO0 = tropical.RHO0
CP0 = tropical.CP0
N_LONGITUDE = tropical.LON_STOP_INDEX - tropical.LON_START_INDEX + 1
MIN_VALID_LONGITUDE_FRACTION = 0.30

EQUATORIAL_TEMP_FILE = tropical.DEPTH_SOURCE
OUT_DIR = ROOT / "data/interim/research_2026/soda3_full_pacific_meridional_sections"
CACHE_DIR = OUT_DIR / "yearly_outer_longitude_sums"
OUT_FILE = (
    ROOT
    / "data/derived/research_2026"
    / "soda3_ohc_meridional_sections_full_pacific_120e80w_"
    "1997_2015_2023_1980_2024_detrended.nc"
)
OUTER_BANDS = ("south", "north")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def longitude_sums(field: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return temperature sum and valid-cell count along longitude."""
    if field.shape[-1] != N_LONGITUDE:
        raise ValueError(f"Unexpected longitude count: {field.shape[-1]}")
    finite = np.isfinite(field)
    numerator = np.nansum(field, axis=-1)
    denominator = finite.sum(axis=-1)
    return numerator.astype(np.float32), denominator.astype(np.int16)


def cache_path(year: int) -> Path:
    return CACHE_DIR / f"soda3_full_pacific_outer_lon_sums_{year}_jan_jun.npz"


def valid_cache(year: int) -> bool:
    path = cache_path(year)
    if not path.exists():
        return False
    try:
        with np.load(path) as data:
            return (
                int(data["year"]) == year
                and tuple(str(value) for value in data["bands"]) == OUTER_BANDS
                and data["temperature_longitude_sum"].shape == (2, 6, 20, 50)
                and data["valid_longitude_count"].shape == (2, 6, 20, 50)
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
        bands=np.asarray(OUTER_BANDS, dtype="U5"),
        temperature_longitude_sum=numerator.astype(np.float32),
        valid_longitude_count=denominator.astype(np.int16),
    )
    temporary.replace(path)
    return path


def empty_sums() -> tuple[np.ndarray, np.ndarray]:
    shape = (2, len(MONTHS), tropical.UPPER_300M_LEVELS, 50)
    return np.zeros(shape, dtype=np.float32), np.zeros(shape, dtype=np.int16)


def add_band(
    numerator: np.ndarray,
    denominator: np.ndarray,
    band: str,
    field: np.ndarray,
    month_index: int,
    depth_index: int,
) -> None:
    band_index = OUTER_BANDS.index(band)
    band_num, band_den = longitude_sums(field)
    numerator[band_index, month_index, depth_index] = band_num
    denominator[band_index, month_index, depth_index] = band_den


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
        add_band(
            numerator,
            denominator,
            band,
            field,
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
                    for band, (lat_start, lat_stop) in meridional.SECTION_LAT_BANDS.items():
                        field = plane[
                            lat_start : lat_stop + 1,
                            tropical.LON_START_INDEX : tropical.LON_STOP_INDEX + 1,
                        ]
                        field[field <= -1.0e10] = np.nan
                        add_band(
                            numerator,
                            denominator,
                            band,
                            field,
                            month_index,
                            depth_index,
                        )
    finally:
        remote.close()
    return save_cache(year, numerator, denominator)


def fetch_year(year: int, force: bool) -> Path:
    if not force and valid_cache(year):
        print(f"Full-Pacific meridional cache reused: {year}", flush=True)
        return cache_path(year)
    url = tropical.URL_TEMPLATE.format(year=year)
    _, signature = tropical.http_read(url, range_header="0-3")
    if signature.startswith(b"CDF"):
        path = fetch_netcdf3_year(year)
    elif signature == b"\x89HDF":
        path = fetch_netcdf4_year(year)
    else:
        raise ValueError(f"Unrecognized SODA file signature for {year}: {signature!r}")
    print(f"Full-Pacific outer longitude sums complete: {year}", flush=True)
    return path


def equatorial_absolute() -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex, np.ndarray, np.ndarray]:
    with xr.open_dataset(EQUATORIAL_TEMP_FILE, engine="netcdf4") as dataset:
        temperature = dataset["temp"].load()
    values = temperature.values.astype(np.float32)
    numerator, denominator = longitude_sums(values)
    minimum_count = int(np.ceil(MIN_VALID_LONGITUDE_FRACTION * N_LONGITUDE))
    absolute = np.divide(
        numerator,
        denominator,
        out=np.full(numerator.shape, np.nan, dtype=np.float32),
        where=denominator >= minimum_count,
    )
    return (
        absolute,
        denominator,
        pd.DatetimeIndex(temperature.time.values),
        temperature.depth.values.astype(float),
        temperature.lat.values.astype(float),
    )


def assemble_output() -> Path:
    eq_absolute, eq_count, times, depth, eq_lat = equatorial_absolute()
    outer_num = []
    outer_den = []
    for year in YEARS:
        with np.load(cache_path(int(year))) as data:
            outer_num.append(np.asarray(data["temperature_longitude_sum"], dtype=np.float32))
            outer_den.append(np.asarray(data["valid_longitude_count"], dtype=np.int16))
    outer_num_values = np.stack(outer_num, axis=1)
    outer_den_values = np.stack(outer_den, axis=1)
    minimum_count = int(np.ceil(MIN_VALID_LONGITUDE_FRACTION * N_LONGITUDE))
    outer_absolute = np.divide(
        outer_num_values,
        outer_den_values,
        out=np.full(outer_num_values.shape, np.nan, dtype=np.float32),
        where=outer_den_values >= minimum_count,
    )

    south = outer_absolute[0].reshape(270, 20, 50)
    north = outer_absolute[1].reshape(270, 20, 50)
    south_count = outer_den_values[0].reshape(270, 20, 50)
    north_count = outer_den_values[1].reshape(270, 20, 50)
    south_lat = -74.75 + 0.5 * np.arange(90, 140)
    north_lat = -74.75 + 0.5 * np.arange(160, 210)
    latitude = np.concatenate([south_lat, eq_lat, north_lat])
    absolute = np.concatenate([south, eq_absolute, north], axis=-1)
    valid_fraction = (
        np.concatenate([south_count, eq_count, north_count], axis=-1).astype(np.float32)
        / np.float32(N_LONGITUDE)
    )

    if absolute.shape != (270, 20, 120):
        raise ValueError(f"Unexpected assembled shape: {absolute.shape}")
    if not np.all(np.diff(latitude) > 0) or not np.allclose(np.diff(latitude), 0.5):
        raise ValueError("Latitude assembly is not a continuous 0.5-degree grid")
    expected_times = pd.DatetimeIndex(
        [pd.Timestamp(year, month, 15) for year in YEARS for month in MONTHS]
    )
    if not np.array_equal(times.values.astype("datetime64[D]"), expected_times.values.astype("datetime64[D]")):
        raise ValueError("Local equatorial time axis does not match 1980--2024 January--June")

    temperature = xr.DataArray(
        absolute,
        dims=("time", "depth", "lat"),
        coords={"time": times, "depth": depth, "lat": latitude},
    )
    original.BASELINE = BASELINE
    anomaly = original.detrended_same_month_anomaly(temperature)
    event_mask = anomaly.time.dt.year.isin(EVENTS)
    selected = anomaly.where(event_mask, drop=True)
    selected_fraction = xr.DataArray(
        valid_fraction,
        dims=("time", "depth", "lat"),
        coords=temperature.coords,
    ).where(event_mask, drop=True)
    temperature_anomaly = selected.values.reshape(3, 6, 20, 120)
    heat_density = temperature_anomaly * np.float32(RHO0 * CP0 / 1.0e6)
    event_fraction = selected_fraction.values.reshape(3, 6, 20, 120)

    if np.nanmax(np.abs(temperature_anomaly)) > 8.0:
        raise ValueError(
            f"Implausible temperature anomaly: {np.nanmax(np.abs(temperature_anomaly))}"
        )

    dataset = xr.Dataset(
        data_vars={
            "temperature_anomaly": (
                ("event", "month", "depth", "lat"),
                temperature_anomaly.astype(np.float32),
            ),
            "heat_content_density_anomaly": (
                ("event", "month", "depth", "lat"),
                heat_density.astype(np.float32),
            ),
            "valid_longitude_fraction": (
                ("event", "month", "depth", "lat"),
                event_fraction.astype(np.float32),
            ),
        },
        coords={
            "event": np.asarray(EVENTS, dtype=np.int16),
            "month": np.asarray(MONTHS, dtype=np.int16),
            "depth": depth,
            "lat": latitude,
        },
        attrs={
            "title": "SODA3 fixed full-Pacific meridional upper-ocean sections",
            "source": "SODA3.15.2 official UMD annual files and validated local equatorial archive",
            "anomaly_definition": (
                f"{BASELINE[0]}-{BASELINE[1]} same-calendar-month climatology "
                "and linear trend removed"
            ),
            "section_definition": (
                "30S-30N latitude-depth section; every event-month is averaged over "
                "the same 120E-80W longitude domain"
            ),
            "longitude_min_degrees_east": 120.0,
            "longitude_max_degrees_east": 280.0,
            "native_longitude_centers": "120.25E-279.75E at 0.5-degree spacing",
            "minimum_valid_longitude_fraction": MIN_VALID_LONGITUDE_FRACTION,
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
        },
    )
    dataset.temperature_anomaly.attrs.update(
        units="degC",
        long_name="Full-Pacific longitude-mean potential-temperature anomaly",
    )
    dataset.heat_content_density_anomaly.attrs.update(
        units="MJ m-3",
        long_name="Volumetric heat-content anomaly rho0*cp0*T_prime",
    )
    dataset.valid_longitude_fraction.attrs.update(
        units="1",
        long_name="Fraction of 120E-80W longitude cells with valid ocean temperature",
    )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        name: {"zlib": True, "complevel": 4, "dtype": "float32"}
        for name in dataset.data_vars
    }
    dataset.to_netcdf(OUT_FILE, engine="netcdf4", encoding=encoding)
    finite = np.isfinite(heat_density)
    print(
        "Full-Pacific meridional diagnostics: "
        f"shape={heat_density.shape}, finite={finite.mean():.4f}, "
        f"range=[{np.nanmin(heat_density):.3f}, {np.nanmax(heat_density):.3f}] MJ m-3, "
        f"valid-longitude fraction=[{np.nanmin(event_fraction):.3f}, "
        f"{np.nanmax(event_fraction):.3f}]",
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
                raise RuntimeError(f"Full-Pacific extraction failed for {year}") from exc
    assemble_output()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
