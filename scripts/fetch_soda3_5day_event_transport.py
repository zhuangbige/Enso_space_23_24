#!/usr/bin/env python3
"""Stream SODA3.15.2 5-day event subsets and derive propagation diagnostics.

The official regridded files are about 285 MB each. This script uses HTTP
byte ranges to read only 0-300 m, 5S-5N, 150E-120W temperature and zonal
velocity plus sea-surface height and surface zonal stress. It stores derived
compact CSV files, not the full global source files.

Default events are 1997, 2004, 2015, and 2023 for January-June.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = (
    "https://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean"
)
OUTPUT_DIR = (
    ROOT / "data/interim/research_2026/soda3_5day_event_transport"
)
COMBINED_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "soda3_5day_event_transport_1997_2004_2015_2023_jan_jun.csv"
)

DEFAULT_YEARS = (1997, 2004, 2015, 2023)
GATE_LONGITUDES = np.arange(150.0, 241.0, 5.0)
LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (145.0, 245.0)
DEPTH_MAX_M = 300.0
RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
FILL_THRESHOLD = -1.0e10
DEPTH_BLOCK_SIZE = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=list(DEFAULT_YEARS),
    )
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-files", type=int)
    return parser.parse_args()


NETCDF_DTYPES = {
    1: (np.dtype(">i1"), 1),
    2: (np.dtype("S1"), 1),
    3: (np.dtype(">i2"), 2),
    4: (np.dtype(">i4"), 4),
    5: (np.dtype(">f4"), 4),
    6: (np.dtype(">f8"), 8),
}


@dataclass(frozen=True)
class RemoteVariable:
    name: str
    dimensions: tuple[str, ...]
    shape: tuple[int, ...]
    nc_type: int
    dtype: np.dtype
    itemsize: int
    begin: int
    vsize: int
    attributes: dict[str, object]


class HeaderCursor:
    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def read(self, size: int) -> bytes:
        output = self.data[self.position : self.position + size]
        if len(output) != size:
            raise EOFError("NetCDF header buffer ended unexpectedly")
        self.position += size
        return output

    def int32(self) -> int:
        return int(struct.unpack(">i", self.read(4))[0])

    def uint32(self) -> int:
        return int(struct.unpack(">I", self.read(4))[0])

    def int64(self) -> int:
        return int(struct.unpack(">q", self.read(8))[0])

    def name(self) -> str:
        length = self.uint32()
        raw = self.read(length)
        padding = (-length) % 4
        if padding:
            self.read(padding)
        return raw.decode("latin1")

    def attributes(self) -> dict[str, object]:
        tag = self.int32()
        count = self.int32()
        if tag not in (0, 12):
            raise ValueError(f"Unexpected NetCDF attribute tag {tag}")
        output: dict[str, object] = {}
        for _ in range(count):
            name = self.name()
            nc_type = self.int32()
            length = self.uint32()
            if nc_type not in NETCDF_DTYPES:
                raise ValueError(f"Unsupported NetCDF attribute type {nc_type}")
            dtype, size = NETCDF_DTYPES[nc_type]
            raw = self.read(length * size)
            padding = (-(length * size)) % 4
            if padding:
                self.read(padding)
            if nc_type == 2:
                value: object = raw.decode("latin1").rstrip("\x00")
            else:
                array = np.frombuffer(raw, dtype=dtype)
                value = array[0].item() if len(array) == 1 else array.copy()
            output[name] = value
        return output


class ClassicNetCDFRemote:
    """Minimal read-only CDF-2 reader backed by HTTP Range requests."""

    def __init__(
        self,
        url: str,
        session: requests.Session | None = None,
        template: "ClassicNetCDFRemote | None" = None,
    ):
        self.url = url
        self.session = session or requests.Session()
        if template is None:
            self.num_records = 0
            self.record_dimension_name: str | None = None
            self.dimensions: dict[str, int] = {}
            self.dimension_order: list[str] = []
            self.global_attributes: dict[str, object] = {}
            self.variables: dict[str, RemoteVariable] = {}
            self._read_header()
        else:
            self.num_records = template.num_records
            self.record_dimension_name = template.record_dimension_name
            self.dimensions = template.dimensions
            self.dimension_order = template.dimension_order
            self.global_attributes = template.global_attributes
            self.variables = template.variables

    def range_bytes(self, start: int, end: int) -> bytes:
        expected = end - start + 1
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                response = self.session.get(
                    self.url,
                    headers={"Range": f"bytes={start}-{end}"},
                    timeout=120,
                )
                response.raise_for_status()
                if response.status_code != 206:
                    raise ValueError(
                        f"Server ignored Range for {self.url}: "
                        f"HTTP {response.status_code}"
                    )
                if len(response.content) != expected:
                    raise ValueError(
                        f"Range length mismatch "
                        f"{len(response.content)} != {expected}"
                    )
                return response.content
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt < 5:
                    time.sleep(1.5 * attempt)
        if last_error is None:
            raise RuntimeError("Range read failed without an exception")
        raise last_error

    def _read_header(self) -> None:
        data = self.range_bytes(0, 262_143)
        cursor = HeaderCursor(data)
        magic = cursor.read(4)
        if magic != b"CDF\x02":
            raise ValueError(f"Expected CDF-2, found {magic!r}")
        self.num_records = cursor.uint32()

        dimension_tag = cursor.int32()
        dimension_count = cursor.int32()
        if dimension_tag not in (0, 10):
            raise ValueError(f"Unexpected dimension tag {dimension_tag}")
        raw_dimensions: dict[str, int | None] = {}
        for _ in range(dimension_count):
            name = cursor.name()
            size = cursor.uint32()
            raw_dimensions[name] = None if size == 0 else size
            if size == 0:
                if self.record_dimension_name is not None:
                    raise ValueError("Multiple unlimited NetCDF dimensions")
                self.record_dimension_name = name
            self.dimension_order.append(name)
        self.dimensions = {
            name: self.num_records if size is None else int(size)
            for name, size in raw_dimensions.items()
        }
        self.global_attributes = cursor.attributes()

        variable_tag = cursor.int32()
        variable_count = cursor.int32()
        if variable_tag not in (0, 11):
            raise ValueError(f"Unexpected variable tag {variable_tag}")
        for _ in range(variable_count):
            name = cursor.name()
            dimension_count = cursor.int32()
            dimension_ids = [
                cursor.int32() for _ in range(dimension_count)
            ]
            dimension_names = tuple(
                self.dimension_order[index] for index in dimension_ids
            )
            attributes = cursor.attributes()
            nc_type = cursor.int32()
            vsize = cursor.uint32()
            begin = cursor.int64()
            if nc_type not in NETCDF_DTYPES:
                raise ValueError(f"Unsupported NetCDF variable type {nc_type}")
            dtype, itemsize = NETCDF_DTYPES[nc_type]
            shape = tuple(self.dimensions[item] for item in dimension_names)
            self.variables[name] = RemoteVariable(
                name=name,
                dimensions=dimension_names,
                shape=shape,
                nc_type=nc_type,
                dtype=dtype,
                itemsize=itemsize,
                begin=begin,
                vsize=vsize,
                attributes=attributes,
            )

    def read_coordinate(self, name: str) -> np.ndarray:
        variable = self.variables[name]
        if len(variable.shape) != 1:
            raise ValueError(f"{name} is not one-dimensional")
        size = variable.shape[0] * variable.itemsize
        raw = self.range_bytes(variable.begin, variable.begin + size - 1)
        return np.frombuffer(raw, dtype=variable.dtype).astype(float)

    def read_record_4d(
        self,
        name: str,
        z_slice: slice,
        y_slice: slice,
        x_slice: slice,
    ) -> np.ndarray:
        variable = self.variables[name]
        if len(variable.shape) != 4 or variable.shape[0] != 1:
            raise ValueError(f"Unexpected {name} shape {variable.shape}")
        _, nz, ny, nx = variable.shape
        z_indices = range(*z_slice.indices(nz))
        y_indices = range(*y_slice.indices(ny))
        x_indices = range(*x_slice.indices(nx))
        if z_slice.step not in (None, 1):
            raise ValueError("Only contiguous depth slices are supported")
        if y_slice.step not in (None, 1) or x_slice.step not in (None, 1):
            raise ValueError("Only contiguous horizontal slices are supported")
        y_start = y_indices.start
        y_stop = y_indices.stop
        x_start = x_indices.start
        x_stop = x_indices.stop
        z_values = list(z_indices)
        blocks = [
            z_values[index : index + DEPTH_BLOCK_SIZE]
            for index in range(0, len(z_values), DEPTH_BLOCK_SIZE)
        ]
        requests_to_make = []
        for block in blocks:
            first_z = block[0]
            last_z = block[-1]
            start_element = (first_z * ny + y_start) * nx
            stop_element = ((last_z * ny + y_stop) * nx)
            start = variable.begin + start_element * variable.itemsize
            end = variable.begin + stop_element * variable.itemsize - 1
            requests_to_make.append((start, end))
        with ThreadPoolExecutor(max_workers=4) as executor:
            raw_blocks = list(
                executor.map(
                    lambda item: self.range_bytes(*item),
                    requests_to_make,
                )
            )
        output = np.empty(
            (len(z_indices), len(y_indices), len(x_indices)),
            dtype=np.float32,
        )
        output_z = 0
        for block, raw in zip(blocks, raw_blocks, strict=True):
            values = np.frombuffer(raw, dtype=variable.dtype)
            first_element = (block[0] * ny + y_start) * nx
            for source_z in block:
                source_start = (
                    (source_z * ny + y_start) * nx - first_element
                )
                source_stop = source_start + (y_stop - y_start) * nx
                plane = values[source_start:source_stop].reshape(
                    (y_stop - y_start, nx)
                )
                output[output_z] = plane[:, x_start:x_stop]
                output_z += 1
        return clean(output)

    def read_record_3d(
        self,
        name: str,
        y_slice: slice,
        x_slice: slice,
    ) -> np.ndarray:
        variable = self.variables[name]
        if len(variable.shape) != 3 or variable.shape[0] != 1:
            raise ValueError(f"Unexpected {name} shape {variable.shape}")
        _, ny, nx = variable.shape
        y_indices = range(*y_slice.indices(ny))
        x_indices = range(*x_slice.indices(nx))
        y_start = y_indices.start
        y_stop = y_indices.stop
        x_start = x_indices.start
        x_stop = x_indices.stop
        start_element = y_start * nx
        element_count = (y_stop - y_start) * nx
        start = variable.begin + start_element * variable.itemsize
        end = start + element_count * variable.itemsize - 1
        raw = self.range_bytes(start, end)
        values = np.frombuffer(raw, dtype=variable.dtype).reshape(
            (y_stop - y_start, nx)
        )
        return clean(values[:, x_start:x_stop])

    def read_time_3d(
        self,
        name: str,
        time_index: int,
        y_slice: slice,
        x_slice: slice,
    ) -> np.ndarray:
        """Read one time record from a CDF-2 (time, y, x) variable."""
        variable = self.variables[name]
        if len(variable.shape) != 3:
            raise ValueError(f"Unexpected {name} shape {variable.shape}")
        if not variable.dimensions or variable.dimensions[0] != self.record_dimension_name:
            raise ValueError(f"{name} is not a record variable")
        if not 0 <= time_index < self.num_records:
            raise IndexError(f"time_index {time_index} outside 0..{self.num_records - 1}")
        _, ny, nx = variable.shape
        y_indices = range(*y_slice.indices(ny))
        x_indices = range(*x_slice.indices(nx))
        y_start = y_indices.start
        y_stop = y_indices.stop
        x_start = x_indices.start
        x_stop = x_indices.stop
        record_size = sum(
            item.vsize
            for item in self.variables.values()
            if item.dimensions
            and item.dimensions[0] == self.record_dimension_name
        )
        start_element = y_start * nx
        element_count = (y_stop - y_start) * nx
        start = (
            variable.begin
            + time_index * record_size
            + start_element * variable.itemsize
        )
        end = start + element_count * variable.itemsize - 1
        raw = self.range_bytes(start, end)
        values = np.frombuffer(raw, dtype=variable.dtype).reshape(
            (y_stop - y_start, nx)
        )
        return clean(values[:, x_start:x_stop])


def clean(values: np.ndarray) -> np.ndarray:
    output = np.asarray(values, dtype=np.float32)
    output[output <= FILL_THRESHOLD] = np.nan
    return output


def import_fsspec():
    try:
        import fsspec  # type: ignore
    except ModuleNotFoundError:
        anaconda_site = Path("/opt/anaconda3/lib/python3.12/site-packages")
        if not anaconda_site.exists():
            raise
        sys.path.append(str(anaconda_site))
        import fsspec  # type: ignore
    return fsspec


def contiguous_slice(
    values: np.ndarray,
    lower: float,
    upper: float,
) -> slice:
    indices = np.flatnonzero((values >= lower) & (values <= upper))
    if indices.size == 0 or not np.all(np.diff(indices) == 1):
        raise ValueError(f"Cannot make contiguous slice for {lower}..{upper}")
    return slice(int(indices[0]), int(indices[-1]) + 1)


def list_event_files(
    years: list[int],
    *,
    end_month: int = 6,
) -> dict[int, list[tuple[pd.Timestamp, str]]]:
    """List five-day files from January through ``end_month``.

    The default preserves the original January-June behavior used by the
    transport scripts.  Later coupling diagnostics can request a longer
    season without silently changing existing products.
    """
    if not 1 <= end_month <= 12:
        raise ValueError("end_month must be between 1 and 12")
    response = requests.get(f"{BASE_URL}/", timeout=60)
    response.raise_for_status()
    pattern = re.compile(
        r"soda3\.15\.2_5dy_ocean_reg_"
        r"(?P<year>\d{4})_(?P<month>\d{2})_(?P<day>\d{2})\.nc"
    )
    requested = set(years)
    found: dict[int, dict[str, tuple[pd.Timestamp, str]]] = {
        year: {} for year in years
    }
    for match in pattern.finditer(response.text):
        year = int(match.group("year"))
        month = int(match.group("month"))
        day = int(match.group("day"))
        if year not in requested or month > end_month:
            continue
        filename = match.group(0)
        found[year][filename] = (
            pd.Timestamp(year, month, day),
            f"{BASE_URL}/{filename}",
        )
    output = {
        year: sorted(values.values())
        for year, values in found.items()
    }
    minimum_files = max(1, int(np.floor(365.0 * end_month / 12.0 / 5.0)) - 2)
    for year, values in output.items():
        if len(values) < minimum_files:
            raise ValueError(
                f"Expected at least {minimum_files} Jan-{end_month:02d} "
                f"files for {year}, "
                f"found {len(values)}"
            )
    return output


def depth_bounds(depth: np.ndarray, maximum: float = 300.0) -> np.ndarray:
    bounds = np.empty(len(depth) + 1, dtype=float)
    bounds[0] = 0.0
    bounds[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    bounds[-1] = min(
        maximum,
        depth[-1] + 0.5 * (depth[-1] - depth[-2]),
    )
    return bounds


def section_diagnostics(
    temperature: np.ndarray,
    velocity: np.ndarray,
    *,
    depth: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    u_lat: np.ndarray,
    u_lon: np.ndarray,
    longitude: float,
) -> tuple[float, float, float]:
    u_index = int(np.argmin(np.abs(u_lon - longitude)))
    left_index = int(np.flatnonzero(lon < longitude)[-1])
    right_index = int(np.flatnonzero(lon > longitude)[0])
    boundary_temp = 0.5 * (
        temperature[:, :, left_index] + temperature[:, :, right_index]
    )
    boundary_u = 0.5 * (
        velocity[:, :-1, u_index] + velocity[:, 1:, u_index]
    )
    if boundary_temp.shape != boundary_u.shape:
        raise ValueError("Temperature and velocity section shapes differ")
    if not np.allclose(0.5 * (u_lat[:-1] + u_lat[1:]), lat):
        raise ValueError("Velocity latitude is not staggered around tracer")

    dz = np.diff(depth_bounds(depth))[:, None]
    dlat = float(np.median(np.diff(lat)))
    dy = EARTH_RADIUS * (
        np.deg2rad(lat + dlat / 2.0)
        - np.deg2rad(lat - dlat / 2.0)
    )
    section_area = dz * dy[None, :]
    valid = np.isfinite(boundary_temp) & np.isfinite(boundary_u)
    warm_excess = np.where(
        valid,
        np.maximum(boundary_temp - 20.0, 0.0),
        np.nan,
    )
    warm_mask = np.where(valid, boundary_temp >= 20.0, False)
    q20_pw = (
        RHO0
        * CP0
        * np.nansum(boundary_u * warm_excess * section_area)
        / 1.0e15
    )
    volume_sv = (
        np.nansum(boundary_u * warm_mask * section_area) / 1.0e6
    )
    warm_heat_gj_per_m = (
        RHO0
        * CP0
        * np.nansum(warm_excess * section_area)
        / 1.0e9
    )
    return float(q20_pw), float(volume_sv), float(warm_heat_gj_per_m)


def d20_from_temperature(
    temperature: np.ndarray,
    depth: np.ndarray,
) -> np.ndarray:
    """Linearly interpolate the first downward 20 degC crossing."""
    if temperature.ndim != 3:
        raise ValueError("Expected temperature with dimensions depth, lat, lon")
    if temperature.shape[0] != len(depth):
        raise ValueError("Temperature depth dimension does not match depth")
    upper = temperature[:-1]
    lower = temperature[1:]
    crossings = (
        np.isfinite(upper)
        & np.isfinite(lower)
        & (upper >= 20.0)
        & (lower < 20.0)
    )
    has_crossing = crossings.any(axis=0)
    first = np.argmax(crossings, axis=0)
    y_index, x_index = np.indices(has_crossing.shape)
    upper_temp = upper[first, y_index, x_index]
    lower_temp = lower[first, y_index, x_index]
    upper_depth = depth[first]
    lower_depth = depth[first + 1]
    denominator = lower_temp - upper_temp
    fraction = np.divide(
        20.0 - upper_temp,
        denominator,
        out=np.full_like(upper_temp, np.nan, dtype=float),
        where=np.abs(denominator) > 1.0e-8,
    )
    result = upper_depth + fraction * (lower_depth - upper_depth)
    return np.where(has_crossing, result, np.nan)


def interpolate_longitude(
    field: np.ndarray,
    lon: np.ndarray,
    longitude: float,
) -> np.ndarray:
    """Interpolate a latitude-longitude tracer field to one longitude."""
    if field.ndim != 2 or field.shape[1] != len(lon):
        raise ValueError("Expected field dimensions lat, lon")
    return np.asarray(
        [
            np.interp(longitude, lon, row)
            if np.isfinite(row).sum() >= 2
            else np.nan
            for row in field
        ],
        dtype=float,
    )


def tracer_gate_diagnostics(
    temperature: np.ndarray,
    ssh: np.ndarray,
    *,
    depth: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    longitude: float,
) -> tuple[float, float, float, int]:
    """Return 5S-5N D20, SSH and near-surface T at a longitude gate."""
    d20 = d20_from_temperature(temperature, depth)
    d20_section = interpolate_longitude(d20, lon, longitude)
    ssh_section = interpolate_longitude(ssh, lon, longitude)
    temp_5m_section = interpolate_longitude(
        temperature[0],
        lon,
        longitude,
    )
    weights = np.cos(np.deg2rad(lat))

    def weighted_mean(values: np.ndarray) -> float:
        valid = np.isfinite(values)
        if not np.any(valid):
            return float("nan")
        return float(np.average(values[valid], weights=weights[valid]))

    return (
        weighted_mean(d20_section),
        weighted_mean(ssh_section),
        weighted_mean(temp_5m_section),
        int(np.isfinite(d20_section).sum()),
    )


def inspect_source(url: str) -> None:
    response = requests.get(
        url,
        headers={"Range": "bytes=0-3"},
        timeout=60,
    )
    response.raise_for_status()
    if response.content == b"CDF\x02":
        dataset = ClassicNetCDFRemote(url)
        print(f"Source: {url}")
        print(f"Records: {dataset.num_records}")
        print(f"Dimensions: {dataset.dimensions}")
        for variable in dataset.variables.values():
            print(
                variable.name,
                variable.shape,
                variable.dtype,
                "begin=",
                variable.begin,
                "vsize=",
                variable.vsize,
            )
        return
    if response.content == b"\x89HDF":
        fsspec = import_fsspec()
        remote = fsspec.open(
            url,
            "rb",
            block_size=16 * 1024 * 1024,
            cache_type="readahead",
        ).open()
        try:
            with h5py.File(remote, "r") as dataset:
                print(f"Source: {url}")
                for name in dataset:
                    item = dataset[name]
                    if isinstance(item, h5py.Dataset):
                        print(
                            name,
                            item.shape,
                            item.dtype,
                            "chunks=",
                            item.chunks,
                        )
                        if name in {"temp", "v", "net_heating", "hflux_total", "swflx"}:
                            attributes = {
                                key: value.decode("utf-8", errors="replace")
                                if isinstance(value, bytes)
                                else value
                                for key, value in item.attrs.items()
                            }
                            print("  attrs=", attributes)
        finally:
            remote.close()
        return
    raise ValueError(f"Unrecognized source magic {response.content!r}")


def source_format(
    url: str,
    session: requests.Session,
) -> str:
    response = session.get(
        url,
        headers={"Range": "bytes=0-3"},
        timeout=60,
    )
    response.raise_for_status()
    if response.content == b"CDF\x02":
        return "cdf2"
    if response.content == b"\x89HDF":
        return "hdf5"
    raise ValueError(f"Unrecognized source magic {response.content!r}")


def process_file_hdf5(
    timestamp: pd.Timestamp,
    url: str,
    cache: dict[str, object],
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    tuple[np.ndarray, ...],
]:
    fsspec = import_fsspec()
    remote = fsspec.open(
        url,
        "rb",
        block_size=16 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            required = {
                "temp",
                "u",
                "ssh",
                "taux",
                "st_ocean",
                "yt_ocean",
                "xt_ocean",
                "yu_ocean",
                "xu_ocean",
            }
            missing = required - set(dataset)
            if missing:
                raise KeyError(
                    f"Missing variables in {url}: {sorted(missing)}"
                )
            if "hdf_grid" not in cache:
                depth_full = np.asarray(dataset["st_ocean"][:], dtype=float)
                lat_full = np.asarray(dataset["yt_ocean"][:], dtype=float)
                lon_full = (
                    np.asarray(dataset["xt_ocean"][:], dtype=float) % 360
                )
                u_lat_full = np.asarray(dataset["yu_ocean"][:], dtype=float)
                u_lon_full = (
                    np.asarray(dataset["xu_ocean"][:], dtype=float) % 360
                )
                z_slice = contiguous_slice(
                    depth_full,
                    0.0,
                    DEPTH_MAX_M,
                )
                y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
                x_slice = contiguous_slice(lon_full, *LON_BOUNDS)
                uy_slice = contiguous_slice(u_lat_full, *LAT_BOUNDS)
                ux_slice = contiguous_slice(u_lon_full, *LON_BOUNDS)
                cache["hdf_grid"] = (
                    depth_full[z_slice],
                    lat_full[y_slice],
                    lon_full[x_slice],
                    u_lat_full[uy_slice],
                    u_lon_full[ux_slice],
                    z_slice,
                    y_slice,
                    x_slice,
                    uy_slice,
                    ux_slice,
                )
            grid = cache["hdf_grid"]
            (
                _,
                _,
                _,
                _,
                _,
                z_slice,
                y_slice,
                x_slice,
                uy_slice,
                ux_slice,
            ) = grid
            temperature = clean(
                dataset["temp"][0, z_slice, y_slice, x_slice]
            )
            velocity = clean(
                dataset["u"][0, z_slice, uy_slice, ux_slice]
            )
            ssh = clean(dataset["ssh"][0, y_slice, x_slice])
            taux = clean(dataset["taux"][0, uy_slice, ux_slice])
    finally:
        remote.close()
    return temperature, velocity, ssh, taux, grid


def process_file(
    timestamp: pd.Timestamp,
    url: str,
    session: requests.Session,
    cache: dict[str, object],
) -> pd.DataFrame:
    source_kind = cache.get("source_format")
    if source_kind is None:
        source_kind = source_format(url, session)
        cache["source_format"] = source_kind
    if source_kind == "hdf5":
        temperature, velocity, ssh, taux, grid = process_file_hdf5(
            timestamp,
            url,
            cache,
        )
        depth, lat, lon, u_lat, u_lon = grid[:5]
    else:
        temperature = velocity = ssh = taux = None
    template = cache.get("template")
    if source_kind == "cdf2":
        dataset = ClassicNetCDFRemote(
            url,
            session=session,
            template=template
            if isinstance(template, ClassicNetCDFRemote)
            else None,
        )
        if template is None:
            cache["template"] = dataset
        required = {
            "temp",
            "u",
            "ssh",
            "taux",
            "st_ocean",
            "yt_ocean",
            "xt_ocean",
            "yu_ocean",
            "xu_ocean",
        }
        missing = required - set(dataset.variables)
        if missing:
            raise KeyError(f"Missing variables in {url}: {sorted(missing)}")
        if "grid" not in cache:
            depth_full = dataset.read_coordinate("st_ocean")
            lat_full = dataset.read_coordinate("yt_ocean")
            lon_full = dataset.read_coordinate("xt_ocean") % 360
            u_lat_full = dataset.read_coordinate("yu_ocean")
            u_lon_full = dataset.read_coordinate("xu_ocean") % 360
            z_slice = contiguous_slice(depth_full, 0.0, DEPTH_MAX_M)
            y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
            x_slice = contiguous_slice(lon_full, *LON_BOUNDS)
            uy_slice = contiguous_slice(u_lat_full, *LAT_BOUNDS)
            ux_slice = contiguous_slice(u_lon_full, *LON_BOUNDS)
            cache["grid"] = (
                depth_full[z_slice],
                lat_full[y_slice],
                lon_full[x_slice],
                u_lat_full[uy_slice],
                u_lon_full[ux_slice],
                z_slice,
                y_slice,
                x_slice,
                uy_slice,
                ux_slice,
            )
        (
            depth,
            lat,
            lon,
            u_lat,
            u_lon,
            z_slice,
            y_slice,
            x_slice,
            uy_slice,
            ux_slice,
        ) = cache["grid"]
        with ThreadPoolExecutor(max_workers=4) as executor:
            temperature_future = executor.submit(
                dataset.read_record_4d,
                "temp",
                z_slice,
                y_slice,
                x_slice,
            )
            velocity_future = executor.submit(
                dataset.read_record_4d,
                "u",
                z_slice,
                uy_slice,
                ux_slice,
            )
            ssh_future = executor.submit(
                dataset.read_record_3d,
                "ssh",
                y_slice,
                x_slice,
            )
            taux_future = executor.submit(
                dataset.read_record_3d,
                "taux",
                uy_slice,
                ux_slice,
            )
            temperature = temperature_future.result()
            velocity = velocity_future.result()
            ssh = ssh_future.result()
            taux = taux_future.result()

    rows = []
    central_lon = (u_lon >= 180.0) & (u_lon <= 220.0)
    central_taux = float(np.nanmean(taux[:, central_lon]))
    for longitude in GATE_LONGITUDES:
        q20_pw, volume_sv, warm_heat = section_diagnostics(
            temperature,
            velocity,
            depth=depth,
            lat=lat,
            lon=lon,
            u_lat=u_lat,
            u_lon=u_lon,
            longitude=float(longitude),
        )
        d20_m, ssh_m, sst_c, d20_valid_lat_count = (
            tracer_gate_diagnostics(
                temperature,
                ssh,
                depth=depth,
                lat=lat,
                lon=lon,
                longitude=float(longitude),
            )
        )
        rows.append(
            {
                "time": timestamp,
                "year": timestamp.year,
                "month": timestamp.month,
                "day": timestamp.day,
                "longitude_e": float(longitude),
                "q20_pw": q20_pw,
                "warm_volume_transport_sv": volume_sv,
                "warm_heat_section_gj_per_m": warm_heat,
                "d20_m": d20_m,
                "ssh_m": ssh_m,
                # SODA's shallowest tracer level is about 5 m.
                "sst_c": sst_c,
                "d20_valid_lat_count": d20_valid_lat_count,
                "taux_central_nm2": central_taux,
                "source_url": url,
            }
        )
    return pd.DataFrame(rows)


def process_year(
    year: int,
    files: list[tuple[pd.Timestamp, str]],
    *,
    force: bool,
    max_files: int | None,
) -> Path:
    suffix = f"_first{max_files}" if max_files else ""
    output = OUTPUT_DIR / (
        f"soda3_5day_transport_{year}_jan_jun{suffix}.csv"
    )
    if output.exists() and not force:
        existing = pd.read_csv(output, nrows=1)
        required_output_columns = {
            "d20_m",
            "ssh_m",
            "sst_c",
            "d20_valid_lat_count",
        }
        if required_output_columns.issubset(existing.columns):
            print(f"Already exists: {output}", flush=True)
            return output
        print(
            f"Existing output lacks propagation fields; rebuilding {output}",
            flush=True,
        )
    selected = files[:max_files] if max_files else files
    pieces = []
    session = requests.Session()
    cache: dict[str, object] = {}
    for index, (timestamp, url) in enumerate(selected, 1):
        cache_path = (
            OUTPUT_DIR
            / "cache"
            / str(year)
            / f"{timestamp:%Y_%m_%d}.csv"
        )
        if cache_path.exists() and not force:
            cached = pd.read_csv(cache_path, parse_dates=["time"])
            required_cache_columns = {
                "d20_m",
                "ssh_m",
                "sst_c",
                "d20_valid_lat_count",
            }
            if required_cache_columns.issubset(cached.columns):
                pieces.append(cached)
                print(
                    f"{year}: reused {index}/{len(selected)} "
                    f"({timestamp.date()})",
                    flush=True,
                )
                continue
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                current = process_file(timestamp, url, session, cache)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                current.to_csv(cache_path, index=False)
                pieces.append(current)
                last_error = None
                break
            except Exception as error:
                last_error = error
                if attempt < 3:
                    print(
                        f"{year} {timestamp.date()} attempt {attempt} "
                        f"failed: {error}; retrying",
                        flush=True,
                    )
                    time.sleep(2 * attempt)
        if last_error is not None:
            raise last_error
        print(
            f"{year}: processed {index}/{len(selected)} "
            f"({timestamp.date()})",
            flush=True,
        )
    frame = pd.concat(pieces, ignore_index=True)
    if frame.duplicated(["time", "longitude_e"]).any():
        raise ValueError(f"Duplicate time-longitude rows for {year}")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    print(f"Wrote {output}", flush=True)
    return output


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    files = list_event_files(years)
    if args.inspect_only:
        timestamp, url = files[years[0]][0]
        print(f"Inspecting {timestamp.date()}", flush=True)
        inspect_source(url)
        return 0
    outputs = [
        process_year(
            year,
            files[year],
            force=args.force,
            max_files=args.max_files,
        )
        for year in years
    ]
    if years == list(DEFAULT_YEARS) and args.max_files is None:
        combined = pd.concat(
            [pd.read_csv(path, parse_dates=["time"]) for path in outputs],
            ignore_index=True,
        ).sort_values(["time", "longitude_e"])
        combined.to_csv(COMBINED_CSV, index=False)
        print(f"Wrote {COMBINED_CSV}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
