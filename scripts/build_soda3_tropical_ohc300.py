#!/usr/bin/env python3
"""Build January--June SODA3 0--300 m OHC on 30S--30N, 120E--80W.

The existing project OHC archive covers 10S--10N.  This script preserves that
validated equatorial archive and adds the two outer latitude bands from the
official UMD SODA3.15.2 annual files.  Older UMD files are NetCDF-3 files of
roughly 3 GB per year, so only the required byte ranges are requested.  Newer
NetCDF-4 files are read with remote HDF5 range access.  File signatures are
detected automatically because the archive switches format within the record.

The final field is sampled at 1 degree for figure production and uses the same
1980--2024 calendar-month linear detrending convention as the equatorial OHC
archive.  Per-year outer-band caches make the download resumable.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import h5py
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str((ROOT / "scripts").resolve()))

from build_soda3_ohc_analysis import (  # noqa: E402
    CP0,
    RHO0,
    compute_ohc,
    import_fsspec,
)


URL_TEMPLATE = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)
EQUATORIAL_OHC = (
    ROOT
    / "data/interim/research_2026/soda3_ohc"
    / "soda3_ohc_0_100_0_300_1980_2024.nc"
)
DEPTH_SOURCE = (
    ROOT
    / "data/raw/soda3"
    / "soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
OUT_DIR = ROOT / "data/interim/research_2026/soda3_ohc_tropical_30s30n"
CACHE_DIR = OUT_DIR / "yearly_outer_band_cache"
OUT_FILE = OUT_DIR / "soda3_ohc300_jan_jun_30s30n_1980_2024_1deg.nc"

START_YEAR = 1980
END_YEAR = 2024
MONTHS = (1, 2, 3, 4, 5, 6)

# SODA3 regridded coordinates are 0.25E + 0.5*i and -74.75N + 0.5*j.
LON_START_INDEX = 240  # 120.25E
LON_STOP_INDEX = 559  # 279.75E, inclusive
GLOBAL_NLON = 720
GLOBAL_NLAT = 330
NDEPTH = 50
UPPER_300M_LEVELS = 20

# The two downloaded bands exclude the already validated 10S--10N archive.
LAT_BANDS = {
    "south": (90, 129),  # 29.75S--10.25S
    "north": (170, 209),  # 10.25N--29.75N
}

NC_DIMENSION = 10
NC_VARIABLE = 11
NC_ATTRIBUTE = 12
NC_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 4, 6: 8}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    return parser.parse_args()


@dataclass(frozen=True)
class Netcdf3Layout:
    temp_begin: int
    record_size: int
    n_records: int


class HeaderCursor:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        end = self.pos + size
        if end > len(self.data):
            raise EOFError("NetCDF header buffer is incomplete")
        result = self.data[self.pos:end]
        self.pos = end
        return result

    def u32(self) -> int:
        return struct.unpack(">I", self.take(4))[0]

    def i64(self) -> int:
        return struct.unpack(">q", self.take(8))[0]

    def name(self) -> str:
        size = self.u32()
        value = self.take(size).decode("latin1")
        self.take((-size) % 4)
        return value


def skip_attribute_list(cursor: HeaderCursor) -> None:
    tag = cursor.u32()
    count = cursor.u32()
    if tag == 0 and count == 0:
        return
    if tag != NC_ATTRIBUTE:
        raise ValueError(f"Unexpected NetCDF attribute tag: {tag}")
    for _ in range(count):
        cursor.name()
        nc_type = cursor.u32()
        n_values = cursor.u32()
        if nc_type not in NC_TYPE_SIZES:
            raise ValueError(f"Unsupported NetCDF attribute type: {nc_type}")
        n_bytes = NC_TYPE_SIZES[nc_type] * n_values
        cursor.take(n_bytes)
        cursor.take((-n_bytes) % 4)


def parse_netcdf3_layout(header: bytes) -> Netcdf3Layout:
    cursor = HeaderCursor(header)
    magic = cursor.take(4)
    if magic != b"CDF\x02":
        raise ValueError(f"Expected NetCDF-3 64-bit-offset file, got {magic!r}")
    n_records = cursor.u32()

    dim_tag = cursor.u32()
    dim_count = cursor.u32()
    if dim_tag != NC_DIMENSION:
        raise ValueError(f"Unexpected NetCDF dimension tag: {dim_tag}")
    dimensions: list[tuple[str, int]] = []
    unlimited_ids: set[int] = set()
    for dim_id in range(dim_count):
        name = cursor.name()
        length = cursor.u32()
        if length == 0:
            unlimited_ids.add(dim_id)
        dimensions.append((name, length))

    skip_attribute_list(cursor)

    var_tag = cursor.u32()
    var_count = cursor.u32()
    if var_tag != NC_VARIABLE:
        raise ValueError(f"Unexpected NetCDF variable tag: {var_tag}")
    temp_begin = None
    temp_dimensions: tuple[str, ...] | None = None
    record_size = 0
    for _ in range(var_count):
        name = cursor.name()
        n_dims = cursor.u32()
        dim_ids = tuple(cursor.u32() for _ in range(n_dims))
        skip_attribute_list(cursor)
        nc_type = cursor.u32()
        vsize = cursor.u32()
        begin = cursor.i64()
        if dim_ids and dim_ids[0] in unlimited_ids:
            record_size += vsize
        if name == "temp":
            if nc_type != 5:
                raise ValueError("SODA temp is not NetCDF float32")
            temp_begin = begin
            temp_dimensions = tuple(dimensions[index][0] for index in dim_ids)

    expected_dims = ("time", "st_ocean", "yt_ocean", "xt_ocean")
    if temp_begin is None or temp_dimensions != expected_dims:
        raise ValueError(f"Unexpected SODA temp dimensions: {temp_dimensions}")
    if record_size <= 0:
        raise ValueError("NetCDF record size was not resolved")
    return Netcdf3Layout(temp_begin=temp_begin, record_size=record_size, n_records=n_records)


def http_read(
    url: str,
    *,
    range_header: str,
    timeout: int = 240,
    attempts: int = 4,
) -> tuple[str, bytes]:
    request = Request(
        url,
        headers={
            "Range": f"bytes={range_header}",
            "User-Agent": "Maryland-ENSO-SODA3-subsetter/1.0",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                if response.status != 206:
                    raise RuntimeError(f"Expected HTTP 206, got {response.status}")
                content_type = response.headers.get("Content-Type", "")
                return content_type, response.read()
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(2.0 * attempt)
    raise RuntimeError(f"HTTP range request failed for {url}: {last_error}")


def fetch_layout(url: str) -> Netcdf3Layout:
    _, header = http_read(url, range_header="0-65535")
    return parse_netcdf3_layout(header)


def parse_multipart(content_type: str, body: bytes) -> dict[tuple[int, int], bytes]:
    if "multipart/byteranges" not in content_type.lower():
        raise ValueError(f"Expected multipart byte ranges, got {content_type!r}")
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
        + body
    )
    if not message.is_multipart():
        raise ValueError("HTTP byte-range body was not parsed as multipart")
    output: dict[tuple[int, int], bytes] = {}
    for part in message.iter_parts():
        content_range = str(part.get("Content-Range", ""))
        match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", content_range)
        if match is None:
            raise ValueError(f"Malformed Content-Range: {content_range!r}")
        start, end = int(match.group(1)), int(match.group(2))
        payload = part.get_payload(decode=True)
        if payload is None or len(payload) != end - start + 1:
            raise ValueError(f"Payload length mismatch for {start}-{end}")
        output[(start, end)] = payload
    return output


def range_for_band(
    layout: Netcdf3Layout,
    month_index: int,
    depth_index: int,
    lat_start: int,
    lat_stop: int,
) -> tuple[int, int]:
    temp_record_offset = layout.temp_begin + month_index * layout.record_size
    depth_stride = GLOBAL_NLAT * GLOBAL_NLON * 4
    lat_stride = GLOBAL_NLON * 4
    start = (
        temp_record_offset
        + depth_index * depth_stride
        + lat_start * lat_stride
        + LON_START_INDEX * 4
    )
    end = (
        temp_record_offset
        + depth_index * depth_stride
        + lat_stop * lat_stride
        + (LON_STOP_INDEX + 1) * 4
        - 1
    )
    return start, end


def decode_band_payload(payload: bytes, lat_start: int, lat_stop: int) -> np.ndarray:
    n_rows = lat_stop - lat_start + 1
    n_selected_lon = LON_STOP_INDEX - LON_START_INDEX + 1
    values = np.frombuffer(payload, dtype=">f4")
    expected = (
        (GLOBAL_NLON - LON_START_INDEX)
        + max(0, n_rows - 2) * GLOBAL_NLON
        + (LON_STOP_INDEX + 1)
    )
    if values.size != expected:
        raise ValueError(f"Unexpected byte-range float count: {values.size} != {expected}")
    selected = np.empty((n_rows, n_selected_lon), dtype=np.float32)
    first_row_length = GLOBAL_NLON - LON_START_INDEX
    for row in range(n_rows):
        if row == 0:
            offset = 0
        else:
            offset = first_row_length + (row - 1) * GLOBAL_NLON + LON_START_INDEX
        selected[row] = values[offset : offset + n_selected_lon]
    selected[selected <= -1.0e10] = np.nan
    return selected[::2, ::2]


def cache_path(year: int) -> Path:
    return CACHE_DIR / f"soda3_ohc300_outer_bands_{year}_jan_jun_1deg.npz"


def save_cache(year: int, south: np.ndarray, north: np.ndarray) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(year)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(
        temporary,
        year=np.int32(year),
        months=np.asarray(MONTHS, dtype=np.int16),
        south_ohc300_jm2=south.astype(np.float32),
        north_ohc300_jm2=north.astype(np.float32),
    )
    temporary.replace(path)
    return path


def valid_cache(year: int) -> bool:
    path = cache_path(year)
    if not path.exists():
        return False
    try:
        with np.load(path) as data:
            return (
                int(data["year"]) == year
                and data["south_ohc300_jm2"].shape == (6, 20, 160)
                and data["north_ohc300_jm2"].shape == (6, 20, 160)
            )
    except Exception:
        return False


def fetch_netcdf3_year(year: int) -> Path:
    url = URL_TEMPLATE.format(year=year)
    layout = fetch_layout(url)
    if layout.n_records != 12:
        raise ValueError(f"Expected 12 SODA records for {year}, got {layout.n_records}")
    requests: dict[tuple[int, int], tuple[str, int, int, int]] = {}
    for month_index in range(6):
        for depth_index in range(UPPER_300M_LEVELS):
            for band, (lat_start, lat_stop) in LAT_BANDS.items():
                bounds = range_for_band(
                    layout,
                    month_index,
                    depth_index,
                    lat_start,
                    lat_stop,
                )
                requests[bounds] = (band, month_index, depth_index, lat_start)
    # The UMD server accepts multipart byte ranges but falls back to a full-file
    # HTTP 200 response when one request contains too many ranges.  Keep each
    # header comfortably below that server-side limit.
    request_bounds = list(requests)
    parts: dict[tuple[int, int], bytes] = {}
    batch_size = 100
    for first in range(0, len(request_bounds), batch_size):
        batch = request_bounds[first : first + batch_size]
        range_header = ",".join(f"{start}-{end}" for start, end in batch)
        content_type, body = http_read(url, range_header=range_header)
        parts.update(parse_multipart(content_type, body))
    if set(parts) != set(requests):
        missing = sorted(set(requests).difference(parts))[:3]
        raise ValueError(f"Incomplete multipart response for {year}; missing {missing}")

    temperature = {
        "south": np.full((6, UPPER_300M_LEVELS, 20, 160), np.nan, dtype=np.float32),
        "north": np.full((6, UPPER_300M_LEVELS, 20, 160), np.nan, dtype=np.float32),
    }
    for bounds, payload in parts.items():
        band, month_index, depth_index, lat_start = requests[bounds]
        lat_stop = LAT_BANDS[band][1]
        temperature[band][month_index, depth_index] = decode_band_payload(
            payload, lat_start, lat_stop
        )

    depth = load_upper_depths()
    south = compute_ohc(temperature["south"], depth)[300]
    north = compute_ohc(temperature["north"], depth)[300]
    return save_cache(year, south, north)


def fetch_netcdf4_year(year: int) -> Path:
    fsspec = import_fsspec()
    url = URL_TEMPLATE.format(year=year)
    remote = fsspec.open(
        url,
        "rb",
        block_size=8 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            if dataset["temp"].shape != (12, NDEPTH, GLOBAL_NLAT, GLOBAL_NLON):
                raise ValueError(f"Unexpected NetCDF4 SODA temp shape for {year}")
            depth = np.asarray(dataset["st_ocean"][:UPPER_300M_LEVELS], dtype=float)
            fields = {
                band: np.full(
                    (6, UPPER_300M_LEVELS, 20, 160),
                    np.nan,
                    dtype=np.float32,
                )
                for band in LAT_BANDS
            }
            # These files are chunked as one complete horizontal plane for
            # each time/depth pair.  Reading that plane and subsetting in
            # memory avoids h5py point-selection requests over HTTP.
            for month_index in range(6):
                for depth_index in range(UPPER_300M_LEVELS):
                    plane = np.asarray(
                        dataset["temp"][month_index, depth_index, :, :],
                        dtype=np.float32,
                    )
                    for band, (lat_start, lat_stop) in LAT_BANDS.items():
                        fields[band][month_index, depth_index] = plane[
                            lat_start : lat_stop + 1 : 2,
                            LON_START_INDEX : LON_STOP_INDEX + 1 : 2,
                        ]
    finally:
        remote.close()
    south = compute_ohc(fields["south"], depth)[300]
    north = compute_ohc(fields["north"], depth)[300]
    return save_cache(year, south, north)


def load_upper_depths() -> np.ndarray:
    with xr.open_dataset(DEPTH_SOURCE, engine="netcdf4") as dataset:
        depth = np.asarray(dataset["depth"].values, dtype=float)
    if depth.size != UPPER_300M_LEVELS or not np.isclose(depth[-1], 287.55084228516):
        raise ValueError(f"Unexpected SODA upper-ocean depths: {depth}")
    return depth


def fetch_year(year: int, force: bool) -> Path:
    if not force and valid_cache(year):
        print(f"SODA outer-band cache reused: {year}", flush=True)
        return cache_path(year)
    url = URL_TEMPLATE.format(year=year)
    _, signature = http_read(url, range_header="0-3")
    if signature.startswith(b"CDF"):
        path = fetch_netcdf3_year(year)
    elif signature == b"\x89HDF":
        path = fetch_netcdf4_year(year)
    else:
        raise ValueError(f"Unrecognized SODA file signature for {year}: {signature!r}")
    print(f"SODA outer-band OHC complete: {year}", flush=True)
    return path


def load_equatorial_ohc() -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex]:
    if not EQUATORIAL_OHC.exists():
        raise FileNotFoundError(EQUATORIAL_OHC)
    with xr.open_dataset(EQUATORIAL_OHC, engine="netcdf4") as dataset:
        selected = dataset["ohc_300m"].where(
            dataset.time.dt.month.isin(MONTHS), drop=True
        )
        selected = selected.sel(lat=slice(-9.75, 9.75), lon=slice(120.25, 279.75))
        selected = selected.isel(lat=slice(None, None, 2), lon=slice(None, None, 2))
        values = np.asarray(selected.values, dtype=np.float32)
        latitude = np.asarray(selected.lat.values, dtype=float)
        longitude = np.asarray(selected.lon.values, dtype=float)
        times = pd.DatetimeIndex(selected.time.values)
    expected = ((END_YEAR - START_YEAR + 1) * len(MONTHS), 20, 160)
    if values.shape != expected:
        raise ValueError(f"Unexpected equatorial OHC shape: {values.shape} != {expected}")
    return values, latitude, longitude, times


def detrended_selected_month_anomaly(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline_start: int,
    baseline_end: int,
) -> np.ndarray:
    """Remove climatology and trend for the calendar months present in *times*."""
    data = np.asarray(values, dtype=np.float64)
    result = np.full(data.shape, np.nan, dtype=np.float32)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    baseline_year = (years >= baseline_start) & (years <= baseline_end)
    present_months = tuple(int(month) for month in np.unique(months))
    if present_months != MONTHS:
        raise ValueError(f"Expected January--June input, got months {present_months}")
    for month in present_months:
        target = months == month
        baseline = target & baseline_year
        if baseline.sum() < 10:
            raise ValueError(f"Insufficient baseline samples for calendar month {month}")
        baseline_values = data[baseline]
        baseline_years = years[baseline]
        center_year = float(np.mean(baseline_years))
        x = baseline_years - center_year
        finite = np.isfinite(baseline_values)
        count = finite.sum(axis=0)
        total = np.nansum(baseline_values, axis=0)
        climatology = np.divide(
            total,
            count,
            out=np.full(total.shape, np.nan, dtype=float),
            where=count > 0,
        )
        centered = baseline_values - climatology[None, :, :]
        numerator = np.nansum(centered * x[:, None, None], axis=0)
        denominator = np.sum(finite * (x[:, None, None] ** 2), axis=0)
        slope = np.divide(
            numerator,
            denominator,
            out=np.full(numerator.shape, np.nan, dtype=float),
            where=denominator > 0,
        )
        target_values = data[target]
        target_years = years[target]
        anomaly = (
            target_values
            - climatology[None, :, :]
            - slope[None, :, :] * (target_years[:, None, None] - center_year)
        )
        result[target] = anomaly.astype(np.float32)
    return result


def assemble_output(start_year: int, end_year: int) -> Path:
    if start_year != START_YEAR or end_year != END_YEAR:
        raise ValueError("The final 1980--2024 baseline requires the full configured year range")
    equatorial, eq_lat, longitude, times = load_equatorial_ohc()
    south_pieces = []
    north_pieces = []
    for year in range(start_year, end_year + 1):
        with np.load(cache_path(year)) as data:
            south_pieces.append(np.asarray(data["south_ohc300_jm2"], dtype=np.float32))
            north_pieces.append(np.asarray(data["north_ohc300_jm2"], dtype=np.float32))
    south = np.concatenate(south_pieces, axis=0)
    north = np.concatenate(north_pieces, axis=0)

    south_lat = -74.75 + 0.5 * np.arange(90, 130, 2)
    north_lat = -74.75 + 0.5 * np.arange(170, 210, 2)
    latitude = np.concatenate([south_lat, eq_lat, north_lat])
    values = np.concatenate([south, equatorial, north], axis=1)
    anomalies = detrended_selected_month_anomaly(
        values,
        times,
        baseline_start=START_YEAR,
        baseline_end=END_YEAR,
    )

    # Recomputing the shared equatorial band from the absolute archive must
    # reproduce its archived anomaly values to numerical precision.
    with xr.open_dataset(EQUATORIAL_OHC, engine="netcdf4") as dataset:
        reference = dataset["ohc_300m_anomaly_detrended"].where(
            dataset.time.dt.month.isin(MONTHS), drop=True
        )
        reference = reference.sel(lat=slice(-9.75, 9.75), lon=slice(120.25, 279.75))
        reference = reference.isel(lat=slice(None, None, 2), lon=slice(None, None, 2))
        reference_values = np.asarray(reference.values, dtype=np.float32)
    overlap_error = float(
        np.nanmax(np.abs(anomalies[:, 20:40, :] - reference_values))
    )
    if overlap_error > 2.0e4:
        raise ValueError(f"Equatorial anomaly overlap error is too large: {overlap_error}")

    dataset = xr.Dataset(
        data_vars={
            "ohc_300m": (("time", "lat", "lon"), values.astype(np.float32)),
            "ohc_300m_anomaly_detrended": (
                ("time", "lat", "lon"),
                anomalies.astype(np.float32),
            ),
        },
        coords={"time": times, "lat": latitude, "lon": longitude},
        attrs={
            "title": "SODA3.15.2 tropical Pacific 0-300 m ocean heat content",
            "source": (
                "SODA3.15.2 official UMD annual files outside 10S-10N; "
                "validated project OHC archive inside 10S-10N"
            ),
            "anomaly_definition": (
                "1980-2024 calendar-month climatology and same-calendar-month "
                "linear trend removed"
            ),
            "spatial_domain": "29.75S to 29.25N, 120.25E to 80.75W",
            "horizontal_sampling": "1 degree sampled from the 0.5-degree regridded product",
            "months": "January-June",
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
            "equatorial_overlap_max_abs_error_j_m2": overlap_error,
        },
    )
    for name in dataset.data_vars:
        dataset[name].attrs.update(units="J m-2")
    dataset["ohc_300m"].attrs["long_name"] = "Ocean heat content integrated over 0-300 m"
    dataset["ohc_300m_anomaly_detrended"].attrs["long_name"] = (
        "Detrended calendar-month anomaly of 0-300 m ocean heat content"
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    encoding = {
        name: {
            "zlib": True,
            "complevel": 4,
            "shuffle": True,
            "dtype": "float32",
            "_FillValue": np.float32(-1.0e20),
        }
        for name in dataset.data_vars
    }
    dataset.to_netcdf(OUT_FILE, engine="netcdf4", encoding=encoding)
    print(
        "Tropical OHC diagnostics: "
        f"shape={values.shape}, finite={np.isfinite(anomalies).mean():.4f}, "
        f"anomaly_min={np.nanmin(anomalies) / 1e9:.3f}, "
        f"anomaly_max={np.nanmax(anomalies) / 1e9:.3f} GJ m-2, "
        f"equatorial_overlap_max={overlap_error:.3f} J m-2",
        flush=True,
    )
    print(OUT_FILE, flush=True)
    return OUT_FILE


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 4:
        raise ValueError("--workers must be between 1 and 4")
    if args.start_year < START_YEAR or args.end_year > END_YEAR:
        raise ValueError(f"Years must stay within {START_YEAR}--{END_YEAR}")
    if args.start_year > args.end_year:
        raise ValueError("--start-year must not exceed --end-year")
    load_upper_depths()
    years = list(range(args.start_year, args.end_year + 1))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_year, year, args.force): year for year in years}
        for future in as_completed(futures):
            year = futures[future]
            try:
                future.result()
            except Exception as exc:
                raise RuntimeError(f"SODA outer-band processing failed for {year}") from exc
    assemble_output(args.start_year, args.end_year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
