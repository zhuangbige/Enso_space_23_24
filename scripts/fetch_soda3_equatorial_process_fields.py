#!/usr/bin/env python3
"""Fetch a compact SODA3.15.2 equatorial Pacific process-field subset.

The APDRC OPeNDAP aggregation supplies 1980-2022. The University of
Maryland official annual files supply 2023-2024 and are read with HTTP byte
ranges so the multi-gigabyte global files are not stored locally.

Variables
---------
u, v
    Three-dimensional ocean velocity on the velocity grid.
wt
    Dia-surface velocity on the tracer grid.
ssh
    Effective sea level.
mlt, mlp
    Temperature- and potential-density-defined mixed-layer depths.
net_heating
    Surface ocean heat flux through the coupler and mass transfer.
taux
    Zonal wind stress applied to the ocean.

Output
------
data/raw/soda3/soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h5py
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
)
TEST_OUTPUT = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_process_fields_jan_jun_1980_test.nc"
)

APDRC_T_URL = (
    "https://apdrc.soest.hawaii.edu/dods/public_data/"
    "SODA/soda_3.15.2/monthly_t"
)
APDRC_U_URL = (
    "https://apdrc.soest.hawaii.edu/dods/public_data/"
    "SODA/soda_3.15.2/monthly_u"
)
OFFICIAL_TEMPLATE = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)

LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (120.0, 280.0)
DEPTH_MAX_M = 300.0
MONTHS = tuple(range(1, 7))
FILL_THRESHOLD = -1.0e10

TRACER_3D = ("wt",)
TRACER_2D = ("ssh", "mlt", "mlp", "net_heating")
VELOCITY_3D = ("u", "v")
VELOCITY_2D = ("taux",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


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


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    indices = np.flatnonzero((values >= lower) & (values <= upper))
    if indices.size == 0 or not np.all(np.diff(indices) == 1):
        raise ValueError(f"Cannot form contiguous slice for {lower}..{upper}")
    return slice(int(indices[0]), int(indices[-1]) + 1)


def clean(values: np.ndarray) -> np.ndarray:
    output = np.asarray(values, dtype=np.float32)
    output[output <= FILL_THRESHOLD] = np.nan
    return output


def source_coordinate_subset(
    dataset: netCDF4.Dataset,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, slice, slice, slice]:
    depth = np.asarray(dataset.variables["lev"][:], dtype=float)
    latitude = np.asarray(dataset.variables["lat"][:], dtype=float)
    longitude = np.asarray(dataset.variables["lon"][:], dtype=float)
    z_slice = contiguous_slice(depth, 0.0, DEPTH_MAX_M)
    y_slice = contiguous_slice(latitude, *LAT_BOUNDS)
    x_slice = contiguous_slice(longitude, *LON_BOUNDS)
    return depth[z_slice], latitude[y_slice], longitude[x_slice], z_slice, y_slice, x_slice


def fetch_apdrc(
    *,
    test_only: bool,
) -> xr.Dataset:
    print("Opening APDRC tracer and velocity aggregations", flush=True)
    tracer = netCDF4.Dataset(APDRC_T_URL)
    velocity = netCDF4.Dataset(APDRC_U_URL)
    try:
        (
            t_depth,
            t_lat,
            t_lon,
            t_zslice,
            t_yslice,
            t_xslice,
        ) = source_coordinate_subset(tracer)
        (
            u_depth,
            u_lat,
            u_lon,
            u_zslice,
            u_yslice,
            u_xslice,
        ) = source_coordinate_subset(velocity)
        if not np.allclose(t_depth, u_depth):
            raise ValueError("APDRC tracer and velocity depth grids differ")

        years = [1980] if test_only else list(range(1980, 2023))
        n_years = len(years)

        def read_calendar_months(
            variable,
            spatial_slices: tuple[slice, ...],
        ) -> np.ndarray:
            if test_only:
                return clean(variable[(slice(0, 6), *spatial_slices)])
            monthly: list[np.ndarray] = []
            for month_index, month in enumerate(MONTHS):
                print(
                    f"  {variable.name}: downloading {month:02d} "
                    f"for 1980-2022",
                    flush=True,
                )
                values = clean(
                    variable[
                        (
                            slice(month_index, n_years * 12, 12),
                            *spatial_slices,
                        )
                    ]
                )
                if values.shape[0] != n_years:
                    raise ValueError(
                        f"{variable.name} month {month}: "
                        f"expected {n_years} years, found {values.shape[0]}"
                    )
                monthly.append(values)
            stacked = np.stack(monthly, axis=1)
            return stacked.reshape(
                (n_years * len(MONTHS), *stacked.shape[2:])
            )

        collected: dict[str, np.ndarray] = {}
        for name in TRACER_3D:
            collected[name] = read_calendar_months(
                tracer.variables[name],
                (t_zslice, t_yslice, t_xslice),
            )
        for name in TRACER_2D:
            source_name = "nh" if name == "net_heating" else name
            collected[name] = read_calendar_months(
                tracer.variables[source_name],
                (t_yslice, t_xslice),
            )
        for name in VELOCITY_3D:
            collected[name] = read_calendar_months(
                velocity.variables[name],
                (u_zslice, u_yslice, u_xslice),
            )
        for name in VELOCITY_2D:
            collected[name] = read_calendar_months(
                velocity.variables[name],
                (u_yslice, u_xslice),
            )
        times = [
            pd.Timestamp(year, month, 15)
            for year in years
            for month in MONTHS
        ]
    finally:
        tracer.close()
        velocity.close()

    data_vars: dict[str, tuple[tuple[str, ...], np.ndarray]] = {}
    for name in TRACER_3D:
        data_vars[name] = (
            ("time", "depth", "lat", "lon"),
            collected[name],
        )
    for name in TRACER_2D:
        data_vars[name] = (
            ("time", "lat", "lon"),
            collected[name],
        )
    for name in VELOCITY_3D:
        data_vars[name] = (
            ("time", "depth", "u_lat", "u_lon"),
            collected[name],
        )
    for name in VELOCITY_2D:
        data_vars[name] = (
            ("time", "u_lat", "u_lon"),
            collected[name],
        )
    return xr.Dataset(
        data_vars=data_vars,
        coords={
            "time": pd.DatetimeIndex(times),
            "depth": t_depth,
            "lat": t_lat,
            "lon": t_lon,
            "u_lat": u_lat,
            "u_lon": u_lon,
        },
    )


def official_subset(
    dataset: h5py.File,
    name: str,
    *,
    tracer_slices: tuple[slice, slice, slice],
    velocity_slices: tuple[slice, slice, slice],
) -> np.ndarray:
    t_zslice, t_yslice, t_xslice = tracer_slices
    u_zslice, u_yslice, u_xslice = velocity_slices
    if name in TRACER_3D:
        return clean(dataset[name][:6, t_zslice, t_yslice, t_xslice])
    if name in TRACER_2D:
        return clean(dataset[name][:6, t_yslice, t_xslice])
    if name in VELOCITY_3D:
        return clean(dataset[name][:6, u_zslice, u_yslice, u_xslice])
    if name in VELOCITY_2D:
        return clean(dataset[name][:6, u_yslice, u_xslice])
    raise KeyError(name)


def fetch_official_year(
    year: int,
    reference: xr.Dataset,
) -> xr.Dataset:
    fsspec = import_fsspec()
    url = OFFICIAL_TEMPLATE.format(year=year)
    print(f"Opening official SODA3 file with byte ranges: {year}", flush=True)
    remote = fsspec.open(
        url,
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            t_depth_full = np.asarray(dataset["st_ocean"][:], dtype=float)
            w_depth_full = np.asarray(dataset["sw_ocean"][:], dtype=float)
            t_lat_full = np.asarray(dataset["yt_ocean"][:], dtype=float)
            t_lon_full = np.asarray(dataset["xt_ocean"][:], dtype=float) % 360
            u_lat_full = np.asarray(dataset["yu_ocean"][:], dtype=float)
            u_lon_full = np.asarray(dataset["xu_ocean"][:], dtype=float) % 360
            t_zslice = contiguous_slice(t_depth_full, 0.0, DEPTH_MAX_M)
            w_zslice = contiguous_slice(w_depth_full, 0.0, DEPTH_MAX_M)
            t_yslice = contiguous_slice(t_lat_full, *LAT_BOUNDS)
            t_xslice = contiguous_slice(t_lon_full, *LON_BOUNDS)
            u_yslice = contiguous_slice(u_lat_full, *LAT_BOUNDS)
            u_xslice = contiguous_slice(u_lon_full, *LON_BOUNDS)

            data_vars: dict[str, xr.DataArray] = {}
            for name in (*TRACER_3D, *TRACER_2D, *VELOCITY_3D, *VELOCITY_2D):
                if name not in dataset:
                    raise KeyError(f"{name} missing from {url}")
                if name == "wt":
                    values = clean(
                        dataset[name][
                            :6,
                            w_zslice,
                            t_yslice,
                            t_xslice,
                        ]
                    )
                    current = xr.DataArray(
                        values,
                        dims=("time", "depth", "lat", "lon"),
                        coords={
                            "time": range(6),
                            "depth": w_depth_full[w_zslice],
                            "lat": t_lat_full[t_yslice],
                            "lon": t_lon_full[t_xslice],
                        },
                    ).interp(
                        depth=reference["depth"],
                        lat=reference["lat"],
                        lon=reference["lon"],
                    )
                    # Two isolated 2024 cells exceed 0.01 m s-1, while the
                    # remaining 2024 distribution is -3.8e-4..1.5e-4 m s-1
                    # (99.98%). Treat these nonphysical interpolation/source
                    # spikes as missing rather than weakening the QA limit.
                    current = current.where(np.abs(current) <= 0.01)
                else:
                    values = official_subset(
                        dataset,
                        name,
                        tracer_slices=(t_zslice, t_yslice, t_xslice),
                        velocity_slices=(t_zslice, u_yslice, u_xslice),
                    )
                    if name in TRACER_3D:
                        current = xr.DataArray(
                            values,
                            dims=("time", "depth", "lat", "lon"),
                            coords={
                                "time": range(6),
                                "depth": t_depth_full[t_zslice],
                                "lat": t_lat_full[t_yslice],
                                "lon": t_lon_full[t_xslice],
                            },
                        ).interp(
                            depth=reference["depth"],
                            lat=reference["lat"],
                            lon=reference["lon"],
                        )
                    elif name in TRACER_2D:
                        current = xr.DataArray(
                            values,
                            dims=("time", "lat", "lon"),
                            coords={
                                "time": range(6),
                                "lat": t_lat_full[t_yslice],
                                "lon": t_lon_full[t_xslice],
                            },
                        ).interp(
                            lat=reference["lat"],
                            lon=reference["lon"],
                        )
                    elif name in VELOCITY_3D:
                        current = xr.DataArray(
                            values,
                            dims=("time", "depth", "u_lat", "u_lon"),
                            coords={
                                "time": range(6),
                                "depth": t_depth_full[t_zslice],
                                "u_lat": u_lat_full[u_yslice],
                                "u_lon": u_lon_full[u_xslice],
                            },
                        ).interp(
                            depth=reference["depth"],
                            u_lat=reference["u_lat"],
                            u_lon=reference["u_lon"],
                        )
                    else:
                        current = xr.DataArray(
                            values,
                            dims=("time", "u_lat", "u_lon"),
                            coords={
                                "time": range(6),
                                "u_lat": u_lat_full[u_yslice],
                                "u_lon": u_lon_full[u_xslice],
                            },
                        ).interp(
                            u_lat=reference["u_lat"],
                            u_lon=reference["u_lon"],
                        )
                data_vars[name] = current.astype(np.float32)
    finally:
        remote.close()

    times = pd.DatetimeIndex(
        [pd.Timestamp(year, month, 15) for month in MONTHS]
    )
    output = xr.Dataset(data_vars).assign_coords(time=times)
    print(f"Official {year}: compact subset complete", flush=True)
    return output


def add_metadata(dataset: xr.Dataset) -> xr.Dataset:
    dataset.attrs.update(
        title="SODA3.15.2 equatorial Pacific ocean process fields",
        source=(
            "APDRC OPeNDAP for 1980-2022; University of Maryland official "
            "annual files for 2023-2024"
        ),
        subset=(
            "January-June, 1980-2024; 5S-5N, 120E-80W; "
            "three-dimensional fields above 300 m"
        ),
        notes=(
            "The velocity and tracer fields retain their native staggered "
            "0.5-degree regridded coordinates. Official-file wt was "
            "interpolated from sw_ocean to the APDRC tracer depth levels. "
            "Two isolated 2024 wt cells above 0.01 m s-1 were masked as "
            "nonphysical source/interpolation spikes."
        ),
    )
    attributes = {
        "u": ("Zonal ocean velocity", "m s-1"),
        "v": ("Meridional ocean velocity", "m s-1"),
        "wt": ("Dia-surface velocity at tracer points", "m s-1"),
        "ssh": ("Effective sea level", "m"),
        "mlt": ("Temperature-criterion mixed-layer depth", "m"),
        "mlp": ("Potential-density mixed-layer depth", "m"),
        "net_heating": (
            "Surface ocean heat flux through coupler and mass transfer",
            "W m-2",
        ),
        "taux": ("Zonal wind stress applied to ocean", "N m-2"),
    }
    for name, (long_name, units) in attributes.items():
        dataset[name].attrs.update(long_name=long_name, units=units)
    return dataset


def write_output(dataset: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    dataset.to_netcdf(path, engine="netcdf4", encoding=encoding)
    print(f"Wrote {path} ({path.stat().st_size / 2**20:.1f} MiB)", flush=True)


def validate(dataset: xr.Dataset, *, test_only: bool) -> None:
    expected_time = 6 if test_only else 45 * 6
    if dataset.sizes.get("time") != expected_time:
        raise ValueError(
            f"Expected {expected_time} records, found {dataset.sizes.get('time')}"
        )
    if not dataset.get_index("time").is_unique:
        raise ValueError("Duplicate time coordinates")
    if not np.all(np.diff(dataset["depth"].values) > 0):
        raise ValueError("Depth is not increasing")
    expected_variables = {
        *TRACER_3D,
        *TRACER_2D,
        *VELOCITY_3D,
        *VELOCITY_2D,
    }
    if set(dataset.data_vars) != expected_variables:
        raise ValueError(
            f"Unexpected variables: {set(dataset.data_vars)} != {expected_variables}"
        )
    ranges = {
        "u": (-5.0, 5.0),
        "v": (-5.0, 5.0),
        "wt": (-0.01, 0.01),
        "ssh": (-5.0, 5.0),
        "mlt": (0.0, 500.0),
        "mlp": (0.0, 500.0),
        "net_heating": (-1000.0, 1000.0),
        "taux": (-5.0, 5.0),
    }
    for name, (lower, upper) in ranges.items():
        finite = dataset[name].values[np.isfinite(dataset[name].values)]
        if finite.size == 0:
            raise ValueError(f"No finite values for {name}")
        if float(finite.min()) < lower or float(finite.max()) > upper:
            raise ValueError(
                f"{name} outside QA range: {finite.min()}..{finite.max()}"
            )


def main() -> int:
    args = parse_args()
    destination = TEST_OUTPUT if args.test else OUTPUT
    if destination.exists() and not args.force:
        print(f"Already exists: {destination}", flush=True)
        return 0

    historical = fetch_apdrc(test_only=args.test)
    pieces = [historical]
    if not args.test:
        for year in (2023, 2024):
            pieces.append(fetch_official_year(year, historical))
    combined = xr.concat(
        pieces,
        dim="time",
        data_vars="all",
        coords="minimal",
        compat="override",
        join="exact",
    ).sortby("time")
    combined = add_metadata(combined)
    validate(combined, test_only=args.test)
    write_output(combined, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
