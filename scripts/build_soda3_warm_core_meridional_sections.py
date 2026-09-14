#!/usr/bin/env python3
"""Build warm-core-following SODA3 latitude-depth sections for three ENSO events.

For each January--June event month, the longitude center is diagnosed from the
positive 0--300 m OHC anomaly map.  Potential temperature is then averaged in
a 20-degree longitude window centered on that warm OHC centroid.  The output
contains 30S--30N, 0--300 m same-calendar-month detrended anomalies for 1997,
2015, and 2023, using the 1980--2024 baseline.

Only the two outer latitude bands are fetched from the official UMD annual
files.  The already validated local equatorial temperature archive supplies
5S--5N.  Yearly outer-band caches make the remote extraction resumable.
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


EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
YEARS = np.arange(1980, 2025, dtype=int)
WINDOW_HALF_WIDTH_DEG = 10.0
WARM_THRESHOLD_GJ_M2 = 0.5
RHO0 = tropical.RHO0
CP0 = tropical.CP0

OHC_FILE = tropical.OUT_FILE
EQUATORIAL_TEMP_FILE = tropical.DEPTH_SOURCE
OUT_DIR = ROOT / "data/interim/research_2026/soda3_meridional_sections_30s30n"
CACHE_DIR = OUT_DIR / "yearly_outer_band_cache"
OUT_FILE = (
    OUT_DIR
    / "soda3_warm_core_meridional_sections_1997_2015_2023_jan_jun_1980_2024.nc"
)

# The local temperature archive covers 4.75S--4.75N.  Fetch adjacent outer
# bands so the assembled section is continuous on the native 0.5-degree grid.
SECTION_LAT_BANDS = {
    "south": (90, 139),  # 29.75S--5.25S
    "north": (160, 209),  # 5.25N--29.75N
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def positive_warm_core_centers() -> np.ndarray:
    """Return event/month OHC-positive centroid longitudes in degrees east."""
    with xr.open_dataset(OHC_FILE, engine="netcdf4") as dataset:
        ohc = (dataset["ohc_300m_anomaly_detrended"] / 1.0e9).load()
    latitude = ohc.lat.values.astype(float)
    longitude = ohc.lon.values.astype(float)
    lat2d, lon2d = np.meshgrid(latitude, longitude, indexing="ij")
    geometry = np.cos(np.deg2rad(lat2d))
    region = (np.abs(lat2d) <= 20.0) & (lon2d >= 140.0) & (lon2d <= 280.0)
    centers = np.full((len(EVENTS), len(MONTHS)), np.nan, dtype=float)
    for event_index, event in enumerate(EVENTS):
        selected = ohc.where(ohc.time.dt.year == event, drop=True)
        if selected.sizes.get("time") != len(MONTHS):
            raise ValueError(f"Expected six OHC months for {event}")
        for month_index in range(len(MONTHS)):
            field = selected.isel(time=month_index).values.astype(float)
            weights = np.where(
                np.isfinite(field) & (field >= WARM_THRESHOLD_GJ_M2) & region,
                field * geometry,
                0.0,
            )
            if weights.sum() <= 0:
                raise ValueError(f"No warm OHC core found for {event}-{month_index + 1:02d}")
            centers[event_index, month_index] = float(
                np.sum(weights * lon2d) / np.sum(weights)
            )
    return centers


def longitude_average(values: np.ndarray, longitude: np.ndarray, center: float) -> np.ndarray:
    mask = (longitude >= center - WINDOW_HALF_WIDTH_DEG) & (
        longitude <= center + WINDOW_HALF_WIDTH_DEG
    )
    if mask.sum() < 20:
        raise ValueError(f"Too few longitude cells around {center:.2f}E")
    selected = values[..., mask]
    finite = np.isfinite(selected)
    count = finite.sum(axis=-1)
    total = np.nansum(selected, axis=-1)
    return np.divide(
        total,
        count,
        out=np.full(total.shape, np.nan, dtype=float),
        where=count > 0,
    ).astype(np.float32)


def decode_band_payload_full(payload: bytes, lat_start: int, lat_stop: int) -> np.ndarray:
    n_rows = lat_stop - lat_start + 1
    n_selected_lon = tropical.LON_STOP_INDEX - tropical.LON_START_INDEX + 1
    values = np.frombuffer(payload, dtype=">f4")
    expected = (
        (tropical.GLOBAL_NLON - tropical.LON_START_INDEX)
        + max(0, n_rows - 2) * tropical.GLOBAL_NLON
        + (tropical.LON_STOP_INDEX + 1)
    )
    if values.size != expected:
        raise ValueError(f"Unexpected byte-range float count: {values.size} != {expected}")
    selected = np.empty((n_rows, n_selected_lon), dtype=np.float32)
    first_row_length = tropical.GLOBAL_NLON - tropical.LON_START_INDEX
    for row in range(n_rows):
        offset = 0 if row == 0 else first_row_length + (row - 1) * tropical.GLOBAL_NLON + tropical.LON_START_INDEX
        selected[row] = values[offset : offset + n_selected_lon]
    selected[selected <= -1.0e10] = np.nan
    return selected


def cache_path(year: int) -> Path:
    return CACHE_DIR / f"soda3_warm_core_outer_sections_{year}_jan_jun.npz"


def valid_cache(year: int, centers: np.ndarray) -> bool:
    path = cache_path(year)
    if not path.exists():
        return False
    try:
        with np.load(path) as data:
            return (
                int(data["year"]) == year
                and data["south_temp"].shape == (3, 6, 20, 50)
                and data["north_temp"].shape == (3, 6, 20, 50)
                and np.allclose(data["window_center_lon"], centers)
            )
    except Exception:
        return False


def save_cache(
    year: int,
    centers: np.ndarray,
    south: np.ndarray,
    north: np.ndarray,
) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(year)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        temporary,
        year=np.int32(year),
        events=np.asarray(EVENTS, dtype=np.int16),
        months=np.asarray(MONTHS, dtype=np.int16),
        window_center_lon=centers.astype(np.float32),
        south_temp=south.astype(np.float32),
        north_temp=north.astype(np.float32),
    )
    temporary.replace(path)
    return path


def empty_outer() -> dict[str, np.ndarray]:
    shape = (len(EVENTS), len(MONTHS), tropical.UPPER_300M_LEVELS, 50)
    return {
        "south": np.full(shape, np.nan, dtype=np.float32),
        "north": np.full(shape, np.nan, dtype=np.float32),
    }


def fetch_netcdf3_year(year: int, centers: np.ndarray) -> Path:
    url = tropical.URL_TEMPLATE.format(year=year)
    layout = tropical.fetch_layout(url)
    requests: dict[tuple[int, int], tuple[str, int, int, int]] = {}
    for month_index in range(len(MONTHS)):
        for depth_index in range(tropical.UPPER_300M_LEVELS):
            for band, (lat_start, lat_stop) in SECTION_LAT_BANDS.items():
                bounds = tropical.range_for_band(
                    layout, month_index, depth_index, lat_start, lat_stop
                )
                requests[bounds] = (band, month_index, depth_index, lat_start)
    bounds_list = list(requests)
    parts: dict[tuple[int, int], bytes] = {}
    for first in range(0, len(bounds_list), 100):
        batch = bounds_list[first : first + 100]
        range_header = ",".join(f"{start}-{end}" for start, end in batch)
        content_type, body = tropical.http_read(url, range_header=range_header)
        parts.update(tropical.parse_multipart(content_type, body))
    if set(parts) != set(requests):
        raise ValueError(f"Incomplete multipart response for {year}")

    output = empty_outer()
    longitude = 120.25 + 0.5 * np.arange(320)
    for bounds, payload in parts.items():
        band, month_index, depth_index, lat_start = requests[bounds]
        full = decode_band_payload_full(
            payload,
            lat_start,
            SECTION_LAT_BANDS[band][1],
        )
        for event_index in range(len(EVENTS)):
            output[band][event_index, month_index, depth_index] = longitude_average(
                full,
                longitude,
                centers[event_index, month_index],
            )
    return save_cache(year, centers, output["south"], output["north"])


def fetch_netcdf4_year(year: int, centers: np.ndarray) -> Path:
    fsspec = tropical.import_fsspec()
    url = tropical.URL_TEMPLATE.format(year=year)
    remote = fsspec.open(
        url,
        "rb",
        block_size=8 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    output = empty_outer()
    longitude = 120.25 + 0.5 * np.arange(320)
    try:
        with tropical.h5py.File(remote, "r") as dataset:
            if dataset["temp"].shape != (
                12,
                tropical.NDEPTH,
                tropical.GLOBAL_NLAT,
                tropical.GLOBAL_NLON,
            ):
                raise ValueError(f"Unexpected NetCDF4 SODA temp shape for {year}")
            for month_index in range(len(MONTHS)):
                for depth_index in range(tropical.UPPER_300M_LEVELS):
                    plane = np.asarray(
                        dataset["temp"][month_index, depth_index, :, :],
                        dtype=np.float32,
                    )
                    for band, (lat_start, lat_stop) in SECTION_LAT_BANDS.items():
                        selected = plane[
                            lat_start : lat_stop + 1,
                            tropical.LON_START_INDEX : tropical.LON_STOP_INDEX + 1,
                        ]
                        selected[selected <= -1.0e10] = np.nan
                        for event_index in range(len(EVENTS)):
                            output[band][event_index, month_index, depth_index] = (
                                longitude_average(
                                    selected,
                                    longitude,
                                    centers[event_index, month_index],
                                )
                            )
    finally:
        remote.close()
    return save_cache(year, centers, output["south"], output["north"])


def fetch_year(year: int, centers: np.ndarray, force: bool) -> Path:
    if not force and valid_cache(year, centers):
        print(f"Meridional-section cache reused: {year}", flush=True)
        return cache_path(year)
    url = tropical.URL_TEMPLATE.format(year=year)
    _, signature = tropical.http_read(url, range_header="0-3")
    if signature.startswith(b"CDF"):
        path = fetch_netcdf3_year(year, centers)
    elif signature == b"\x89HDF":
        path = fetch_netcdf4_year(year, centers)
    else:
        raise ValueError(f"Unrecognized SODA file signature for {year}: {signature!r}")
    print(f"Meridional-section outer bands complete: {year}", flush=True)
    return path


def load_equatorial_sections(centers: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with xr.open_dataset(EQUATORIAL_TEMP_FILE, engine="netcdf4") as dataset:
        temperature = dataset["temp"].load()
    if temperature.dims != ("time", "depth", "lat", "lon"):
        raise ValueError(f"Unexpected equatorial temperature dimensions: {temperature.dims}")
    times = pd.DatetimeIndex(temperature.time.values)
    latitude = temperature.lat.values.astype(float)
    longitude = temperature.lon.values.astype(float)
    depth = temperature.depth.values.astype(float)
    expected = (len(YEARS) * len(MONTHS), 20, 20, 320)
    if temperature.shape != expected:
        raise ValueError(f"Unexpected equatorial temperature shape: {temperature.shape}")
    output = np.full((len(YEARS), 3, 6, 20, 20), np.nan, dtype=np.float32)
    for year_index, year in enumerate(YEARS):
        for month_index, month in enumerate(MONTHS):
            time_index = np.flatnonzero((times.year == year) & (times.month == month))
            if time_index.size != 1:
                raise ValueError(f"Expected one equatorial record for {year}-{month:02d}")
            values = temperature.isel(time=int(time_index[0])).values.astype(np.float32)
            for event_index in range(len(EVENTS)):
                output[year_index, event_index, month_index] = longitude_average(
                    values,
                    longitude,
                    centers[event_index, month_index],
                )
    return output, latitude, depth


def detrend_and_select(values: np.ndarray) -> np.ndarray:
    """Detrend across 1980--2024 and select each event's target year."""
    x = YEARS.astype(float)
    center = float(x.mean())
    xc = x - center
    residual = np.full(values.shape, np.nan, dtype=np.float32)
    for event_index in range(len(EVENTS)):
        for month_index in range(len(MONTHS)):
            selected = values[:, event_index, month_index].astype(np.float64)
            finite = np.isfinite(selected)
            count = finite.sum(axis=0)
            mean = np.divide(
                np.nansum(selected, axis=0),
                count,
                out=np.full(selected.shape[1:], np.nan),
                where=count > 0,
            )
            denominator = np.sum(finite * xc[:, None, None] ** 2, axis=0)
            slope = np.divide(
                np.nansum((selected - mean) * xc[:, None, None], axis=0),
                denominator,
                out=np.full(selected.shape[1:], np.nan),
                where=denominator > 0,
            )
            residual[:, event_index, month_index] = (
                selected
                - mean[None, :, :]
                - slope[None, :, :] * xc[:, None, None]
            ).astype(np.float32)
    output = np.full(values.shape[1:], np.nan, dtype=np.float32)
    for event_index, event in enumerate(EVENTS):
        year_index = int(np.flatnonzero(YEARS == event)[0])
        output[event_index] = residual[year_index, event_index]
    return output


def assemble_output(centers: np.ndarray) -> Path:
    equatorial, eq_lat, depth = load_equatorial_sections(centers)
    south = []
    north = []
    for year in YEARS:
        with np.load(cache_path(int(year))) as data:
            south.append(np.asarray(data["south_temp"], dtype=np.float32))
            north.append(np.asarray(data["north_temp"], dtype=np.float32))
    south_values = np.stack(south, axis=0)
    north_values = np.stack(north, axis=0)
    south_lat = -74.75 + 0.5 * np.arange(90, 140)
    north_lat = -74.75 + 0.5 * np.arange(160, 210)
    latitude = np.concatenate([south_lat, eq_lat, north_lat])
    absolute = np.concatenate([south_values, equatorial, north_values], axis=-1)
    anomaly = detrend_and_select(absolute)
    heat_density = anomaly * np.float32(RHO0 * CP0 / 1.0e6)

    if not np.all(np.diff(latitude) > 0) or not np.allclose(np.diff(latitude), 0.5):
        raise ValueError("Latitude assembly is not a continuous 0.5-degree grid")
    if np.nanmax(np.abs(anomaly)) > 8.0:
        raise ValueError(f"Implausible temperature anomaly: {np.nanmax(np.abs(anomaly))}")

    dataset = xr.Dataset(
        data_vars={
            "temperature_anomaly": (
                ("event", "month", "depth", "lat"),
                anomaly.astype(np.float32),
            ),
            "heat_content_density_anomaly": (
                ("event", "month", "depth", "lat"),
                heat_density.astype(np.float32),
            ),
            "window_center_lon": (("event", "month"), centers.astype(np.float32)),
            "window_lon_min": (
                ("event", "month"),
                (centers - WINDOW_HALF_WIDTH_DEG).astype(np.float32),
            ),
            "window_lon_max": (
                ("event", "month"),
                (centers + WINDOW_HALF_WIDTH_DEG).astype(np.float32),
            ),
        },
        coords={
            "event": np.asarray(EVENTS, dtype=np.int16),
            "month": np.asarray(MONTHS, dtype=np.int16),
            "depth": depth,
            "lat": latitude,
        },
        attrs={
            "title": "SODA3 warm-core-following tropical Pacific meridional sections",
            "source": "SODA3.15.2 official UMD annual files and validated local equatorial archive",
            "anomaly_definition": "1980-2024 same-calendar-month climatology and linear trend removed",
            "section_definition": (
                "30S-30N latitude-depth section; each event-month is zonally averaged "
                "within 10 degrees longitude of its positive OHC anomaly centroid"
            ),
            "ohc_centroid_threshold_gj_m2": WARM_THRESHOLD_GJ_M2,
            "ohc_centroid_domain": "20S-20N, 140E-80W",
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
        },
    )
    dataset.temperature_anomaly.attrs.update(
        units="degC",
        long_name="Potential-temperature anomaly in warm-core-following longitude window",
    )
    dataset.heat_content_density_anomaly.attrs.update(
        units="MJ m-3",
        long_name="Volumetric heat-content anomaly rho0*cp0*T_prime",
    )
    for name in ("window_center_lon", "window_lon_min", "window_lon_max"):
        dataset[name].attrs["units"] = "degrees_east"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    encoding = {
        "temperature_anomaly": {"zlib": True, "complevel": 4, "dtype": "float32"},
        "heat_content_density_anomaly": {"zlib": True, "complevel": 4, "dtype": "float32"},
    }
    dataset.to_netcdf(OUT_FILE, engine="netcdf4", encoding=encoding)
    finite = np.isfinite(heat_density)
    print(
        "Meridional-section diagnostics: "
        f"shape={heat_density.shape}, finite={finite.mean():.4f}, "
        f"range=[{np.nanmin(heat_density):.3f}, {np.nanmax(heat_density):.3f}] MJ m-3",
        flush=True,
    )
    print(OUT_FILE, flush=True)
    return OUT_FILE


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 4:
        raise ValueError("--workers must be between 1 and 4")
    centers = positive_warm_core_centers()
    print("Warm-core longitude centers (degrees east):", flush=True)
    for event, values in zip(EVENTS, centers):
        print(f"  {event}: " + ", ".join(f"{value:.1f}" for value in values), flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_year, int(year), centers, args.force): int(year)
            for year in YEARS
        }
        for future in as_completed(futures):
            year = futures[future]
            try:
                future.result()
            except Exception as exc:
                raise RuntimeError(f"Meridional-section extraction failed for {year}") from exc
    assemble_output(centers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
