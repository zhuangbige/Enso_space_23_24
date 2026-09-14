#!/usr/bin/env python3
"""Build five SODA3 latitude-band longitude-depth section diagnostics.

The five cosine-latitude-weighted bands are arranged north to south:
15N--30N, 5N--15N, 5S--5N, 5S--15S, and 15S--30S.  January--June
temperature anomalies use the same 1980--2024 same-calendar-month detrending
as the original equatorial longitude-depth sections.
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
import build_soda3_tropical30_lon_depth_sections as tropical30  # noqa: E402
import build_soda3_warm_core_meridional_sections as meridional  # noqa: E402
import plot_soda3_monthly_ohc_vertical_sections as original  # noqa: E402


EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
YEARS = np.arange(1980, 2025, dtype=int)
RHO0 = tropical.RHO0
CP0 = tropical.CP0
MIN_VALID_WEIGHT_FRACTION = 0.30

BAND_ORDER = (
    "north_15_30",
    "north_5_15",
    "equatorial_5s_5n",
    "south_5_15",
    "south_15_30",
)
OUTER_BANDS = (
    "north_15_30",
    "north_5_15",
    "south_5_15",
    "south_15_30",
)
BAND_LABELS = {
    "north_15_30": "15°–30°N",
    "north_5_15": "5°–15°N",
    "equatorial_5s_5n": "5°S–5°N",
    "south_5_15": "5°–15°S",
    "south_15_30": "15°–30°S",
}
BAND_BOUNDS = {
    "north_15_30": (15.0, 30.0),
    "north_5_15": (5.0, 15.0),
    "equatorial_5s_5n": (-5.0, 5.0),
    "south_5_15": (-15.0, -5.0),
    "south_15_30": (-30.0, -15.0),
}

EQUATORIAL_TEMP_FILE = tropical.DEPTH_SOURCE
OUT_DIR = ROOT / "data/interim/research_2026/soda3_latband_lon_depth_sections"
CACHE_DIR = OUT_DIR / "yearly_outer_band_latitude_sums"
OUT_FILE = (
    ROOT
    / "data/derived/research_2026"
    / "soda3_ohc_lon_depth_sections_five_latbands_1997_2015_2023_1980_2024_detrended.nc"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def cache_path(year: int) -> Path:
    return CACHE_DIR / f"soda3_four_outer_latband_sums_{year}_jan_jun.npz"


def valid_cache(year: int) -> bool:
    path = cache_path(year)
    if not path.exists():
        return False
    try:
        with np.load(path) as data:
            return (
                int(data["year"]) == year
                and tuple(str(value) for value in data["bands"]) == OUTER_BANDS
                and data["temperature_weighted_sum"].shape == (4, 6, 20, 320)
                and data["valid_weight_sum"].shape == (4, 6, 20, 320)
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
        bands=np.asarray(OUTER_BANDS, dtype="U16"),
        temperature_weighted_sum=numerator.astype(np.float32),
        valid_weight_sum=denominator.astype(np.float32),
    )
    temporary.replace(path)
    return path


def empty_sums() -> tuple[np.ndarray, np.ndarray]:
    shape = (len(OUTER_BANDS), len(MONTHS), tropical.UPPER_300M_LEVELS, 320)
    return np.zeros(shape, dtype=np.float32), np.zeros(shape, dtype=np.float32)


def split_outer_field(
    source_band: str,
    field: np.ndarray,
) -> tuple[tuple[str, np.ndarray, np.ndarray], ...]:
    if source_band == "south":
        return (
            (
                "south_15_30",
                field[:30],
                -74.75 + 0.5 * np.arange(90, 120),
            ),
            (
                "south_5_15",
                field[30:50],
                -74.75 + 0.5 * np.arange(120, 140),
            ),
        )
    if source_band == "north":
        return (
            (
                "north_5_15",
                field[:20],
                -74.75 + 0.5 * np.arange(160, 180),
            ),
            (
                "north_15_30",
                field[20:50],
                -74.75 + 0.5 * np.arange(180, 210),
            ),
        )
    raise ValueError(f"Unexpected source band: {source_band}")


def add_source_band(
    numerator: np.ndarray,
    denominator: np.ndarray,
    source_band: str,
    field: np.ndarray,
    month_index: int,
    depth_index: int,
) -> None:
    for band, selected, latitude in split_outer_field(source_band, field):
        band_index = OUTER_BANDS.index(band)
        band_num, band_den = tropical30.weighted_latitude_sums(selected, latitude)
        numerator[band_index, month_index, depth_index] = band_num
        denominator[band_index, month_index, depth_index] = band_den


def fetch_netcdf3_year(year: int) -> Path:
    url = tropical.URL_TEMPLATE.format(year=year)
    layout = tropical.fetch_layout(url)
    requests: dict[tuple[int, int], tuple[str, int, int, int]] = {}
    for month_index in range(len(MONTHS)):
        for depth_index in range(tropical.UPPER_300M_LEVELS):
            for source_band, (lat_start, lat_stop) in meridional.SECTION_LAT_BANDS.items():
                bounds = tropical.range_for_band(
                    layout,
                    month_index,
                    depth_index,
                    lat_start,
                    lat_stop,
                )
                requests[bounds] = (source_band, month_index, depth_index, lat_start)
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
        source_band, month_index, depth_index, lat_start = requests[bounds]
        lat_stop = meridional.SECTION_LAT_BANDS[source_band][1]
        field = meridional.decode_band_payload_full(payload, lat_start, lat_stop)
        add_source_band(
            numerator,
            denominator,
            source_band,
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
                    for source_band, (lat_start, lat_stop) in meridional.SECTION_LAT_BANDS.items():
                        field = plane[
                            lat_start : lat_stop + 1,
                            tropical.LON_START_INDEX : tropical.LON_STOP_INDEX + 1,
                        ]
                        field[field <= -1.0e10] = np.nan
                        add_source_band(
                            numerator,
                            denominator,
                            source_band,
                            field,
                            month_index,
                            depth_index,
                        )
    finally:
        remote.close()
    return save_cache(year, numerator, denominator)


def fetch_year(year: int, force: bool) -> Path:
    if not force and valid_cache(year):
        print(f"Five-band section cache reused: {year}", flush=True)
        return cache_path(year)
    url = tropical.URL_TEMPLATE.format(year=year)
    _, signature = tropical.http_read(url, range_header="0-3")
    if signature.startswith(b"CDF"):
        path = fetch_netcdf3_year(year)
    elif signature == b"\x89HDF":
        path = fetch_netcdf4_year(year)
    else:
        raise ValueError(f"Unrecognized SODA file signature for {year}: {signature!r}")
    print(f"Five-band longitude-depth latitude sums complete: {year}", flush=True)
    return path


def equatorial_absolute() -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex, np.ndarray, np.ndarray]:
    with xr.open_dataset(EQUATORIAL_TEMP_FILE, engine="netcdf4") as dataset:
        temperature = dataset["temp"].load()
    numerator, denominator = tropical30.weighted_latitude_sums(
        temperature.values.astype(np.float32),
        temperature.lat.values.astype(float),
    )
    absolute = np.divide(
        numerator,
        denominator,
        out=np.full(numerator.shape, np.nan, dtype=np.float32),
        where=denominator > 0,
    )
    return (
        absolute,
        denominator,
        pd.DatetimeIndex(temperature.time.values),
        temperature.depth.values.astype(float),
        temperature.lon.values.astype(float),
    )


def detrended_event_values(
    absolute: np.ndarray,
    times: pd.DatetimeIndex,
    depth: np.ndarray,
    longitude: np.ndarray,
) -> np.ndarray:
    da = xr.DataArray(
        absolute,
        dims=("time", "depth", "lon"),
        coords={"time": times, "depth": depth, "lon": longitude},
    )
    anomaly = original.detrended_same_month_anomaly(da)
    selected = anomaly.where(anomaly.time.dt.year.isin(EVENTS), drop=True)
    return selected.values.astype(np.float32)


def nominal_band_weight(band: str) -> float:
    """Return total native-grid cosine weight for an outer latitude band."""
    if band == "north_15_30":
        latitude = -74.75 + 0.5 * np.arange(180, 210)
    elif band == "north_5_15":
        latitude = -74.75 + 0.5 * np.arange(160, 180)
    elif band == "south_5_15":
        latitude = -74.75 + 0.5 * np.arange(120, 140)
    elif band == "south_15_30":
        latitude = -74.75 + 0.5 * np.arange(90, 120)
    else:
        raise ValueError(f"No outer-band nominal weight for {band}")
    return float(np.sum(np.cos(np.deg2rad(latitude))))


def assemble_output() -> Path:
    eq_absolute, eq_den, times, depth, longitude = equatorial_absolute()
    outer_num = []
    outer_den = []
    for year in YEARS:
        with np.load(cache_path(int(year))) as data:
            outer_num.append(np.asarray(data["temperature_weighted_sum"], dtype=np.float32))
            outer_den.append(np.asarray(data["valid_weight_sum"], dtype=np.float32))
    outer_num_values = np.stack(outer_num, axis=1).reshape(4, 270, 20, 320)
    outer_den_values = np.stack(outer_den, axis=1).reshape(4, 270, 20, 320)

    anomaly_by_band = []
    outer_absolute_by_band = []
    for band_index in range(len(OUTER_BANDS)):
        minimum_weight = (
            MIN_VALID_WEIGHT_FRACTION * nominal_band_weight(OUTER_BANDS[band_index])
        )
        absolute = np.divide(
            outer_num_values[band_index],
            outer_den_values[band_index],
            out=np.full((270, 20, 320), np.nan, dtype=np.float32),
            where=outer_den_values[band_index] >= minimum_weight,
        )
        outer_absolute_by_band.append(absolute)
        anomaly_by_band.append(
            detrended_event_values(absolute, times, depth, longitude)
        )
    equatorial_anomaly = detrended_event_values(eq_absolute, times, depth, longitude)
    anomaly_lookup = {
        band: anomaly_by_band[index] for index, band in enumerate(OUTER_BANDS)
    }
    anomaly_lookup["equatorial_5s_5n"] = equatorial_anomaly
    temperature_anomaly = np.stack(
        [anomaly_lookup[band] for band in BAND_ORDER],
        axis=0,
    )
    heat_density = temperature_anomaly * np.float32(RHO0 * CP0 / 1.0e6)

    event_times = pd.DatetimeIndex(
        [pd.Timestamp(event, month, 15) for event in EVENTS for month in MONTHS]
    )
    band_lat_min = np.asarray([BAND_BOUNDS[band][0] for band in BAND_ORDER], dtype=np.float32)
    band_lat_max = np.asarray([BAND_BOUNDS[band][1] for band in BAND_ORDER], dtype=np.float32)
    dataset = xr.Dataset(
        data_vars={
            "temperature_anomaly": (
                ("band", "time", "depth", "lon"),
                temperature_anomaly.astype(np.float32),
            ),
            "heat_content_density_anomaly": (
                ("band", "time", "depth", "lon"),
                heat_density.astype(np.float32),
            ),
            "band_lat_min": (("band",), band_lat_min),
            "band_lat_max": (("band",), band_lat_max),
            "band_label": (
                ("band",),
                np.asarray([BAND_LABELS[band] for band in BAND_ORDER], dtype="U12"),
            ),
        },
        coords={
            "band": np.asarray(BAND_ORDER, dtype="U20"),
            "time": event_times,
            "depth": depth,
            "lon": longitude,
        },
        attrs={
            "title": "SODA3.15.2 five-latitude-band upper-ocean longitude-depth diagnostics",
            "source": "SODA3.15.2 official UMD annual files and validated local equatorial archive",
            "events": ", ".join(str(event) for event in EVENTS),
            "months": "January-June",
            "latitude_weighting": "Cosine-latitude weighted over valid ocean cells in each band",
            "minimum_valid_latitude_weight_fraction": MIN_VALID_WEIGHT_FRACTION,
            "sampling_note": (
                "Outer-band longitude-depth cells are retained only when valid ocean cells "
                "supply at least 30 percent of the band's nominal cosine-latitude weight"
            ),
            "anomaly_definition": "1980-2024 same-calendar-month climatology and linear trend removed",
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
        },
    )
    dataset.temperature_anomaly.attrs.update(
        units="degC",
        long_name="Detrended latitude-band mean potential-temperature anomaly",
    )
    dataset.heat_content_density_anomaly.attrs.update(
        units="MJ m-3",
        long_name="Volumetric heat-content anomaly rho0*cp0*T_prime",
    )
    dataset.band_lat_min.attrs["units"] = "degrees_north"
    dataset.band_lat_max.attrs["units"] = "degrees_north"

    # Recombine the five absolute band means with their native valid-ocean
    # weights and verify that they reproduce the independently built 30S--30N
    # mean diagnostic.
    all_num = np.sum(outer_num_values, axis=0) + eq_absolute * eq_den
    all_den = np.sum(outer_den_values, axis=0) + eq_den
    all_absolute = np.divide(
        all_num,
        all_den,
        out=np.full(all_num.shape, np.nan, dtype=np.float32),
        where=all_den > 0,
    )
    recombined = detrended_event_values(all_absolute, times, depth, longitude)
    with xr.open_dataset(tropical30.OUT_FILE, engine="netcdf4") as reference:
        reference_values = reference.temperature_anomaly.values.astype(np.float32)
    reconstruction_error = float(np.nanmax(np.abs(recombined - reference_values)))
    dataset.attrs["max_abs_reconstruction_error_degC"] = reconstruction_error
    if reconstruction_error > 3.0e-2:
        raise ValueError(f"Five-band reconstruction error is too large: {reconstruction_error}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        "temperature_anomaly": {"zlib": True, "complevel": 4, "dtype": "float32"},
        "heat_content_density_anomaly": {"zlib": True, "complevel": 4, "dtype": "float32"},
    }
    dataset.to_netcdf(OUT_FILE, engine="netcdf4", encoding=encoding)
    print(f"Five-band reconstruction max error: {reconstruction_error:.6f} degC", flush=True)
    for band_index, band in enumerate(BAND_ORDER):
        values = heat_density[band_index].astype(float)
        print(
            f"  {BAND_LABELS[band]}: range=[{np.nanmin(values):.3f}, "
            f"{np.nanmax(values):.3f}], rms={np.sqrt(np.nanmean(values ** 2)):.3f} MJ m-3",
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
                raise RuntimeError(f"Five-band section extraction failed for {year}") from exc
    assemble_output()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
