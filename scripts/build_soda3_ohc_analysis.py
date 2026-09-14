#!/usr/bin/env python3
"""Build upper-ocean heat-content fields and indices from SODA3.15.2.

The workflow intentionally downloads only the equatorial Pacific temperature
subset.  APDRC OPeNDAP is used for 1980-2022, while the official University of
Maryland annual files are read through HTTP byte ranges for 2023 onward.

Outputs
-------
* Monthly 0-100 m and 0-300 m OHC on 10S-10N, 120E-80W.
* Calendar-month anomalies with the 1980-2014 same-month trend removed.
* Area-weighted basin, western, central, eastern, and far-eastern indices.
* East-minus-west OHC contrast and positive-anomaly longitude centroid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
OUT_INTERIM = ROOT / "data/interim/research_2026/soda3_ohc"
OUT_DERIVED = ROOT / "data/derived/research_2026"

APDRC_URL = (
    "https://apdrc.soest.hawaii.edu/dods/public_data/"
    "SODA/soda_3.15.2/monthly_t"
)
OFFICIAL_TEMPLATE = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)

LAT_MIN = -10.0
LAT_MAX = 10.0
LON_MIN = 120.0
LON_MAX = 280.0
DEPTH_LIMITS = (100.0, 300.0)
RHO0 = 1025.0
CP0 = 3990.0
FILL_THRESHOLD = -1.0e10

REGIONS = {
    # Start at 130E to avoid the Maritime Continent/coastal mask boundary and
    # to stay consistent with the report's western-Pacific D20 box.
    "basin": (-5.0, 5.0, 130.0, 280.0),
    "west": (-5.0, 5.0, 130.0, 180.0),
    "central": (-5.0, 5.0, 180.0, 220.0),
    "east": (-5.0, 5.0, 220.0, 280.0),
    "fep": (-5.0, 5.0, 270.0, 280.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=1980)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--baseline-start", type=int, default=1980)
    parser.add_argument("--baseline-end", type=int, default=2024)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def import_fsspec():
    """Import fsspec, using the local Anaconda copy when absent in .venv."""
    try:
        import fsspec  # type: ignore
    except ModuleNotFoundError:
        anaconda_site = Path("/opt/anaconda3/lib/python3.12/site-packages")
        if anaconda_site.exists():
            sys.path.append(str(anaconda_site))
        import fsspec  # type: ignore
    return fsspec


def layer_thicknesses(depth: np.ndarray, limit: float) -> np.ndarray:
    """Return nominal layer overlap with 0-limit from cell-center depths."""
    depth = np.asarray(depth, dtype=float)
    edges = np.empty(depth.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    edges[-1] = depth[-1] + 0.5 * (depth[-1] - depth[-2])
    top = edges[:-1]
    bottom = edges[1:]
    return np.maximum(0.0, np.minimum(bottom, limit) - top)


def compute_ohc(temperature: np.ndarray, depth: np.ndarray) -> dict[int, np.ndarray]:
    """Integrate potential temperature over fixed upper-ocean depth ranges."""
    values = np.asarray(temperature, dtype=np.float64)
    values[values <= FILL_THRESHOLD] = np.nan
    outputs: dict[int, np.ndarray] = {}
    for limit_float in DEPTH_LIMITS:
        weights = layer_thicknesses(depth, limit_float)
        used = weights > 0
        finite = np.all(np.isfinite(values[:, used, :, :]), axis=1)
        integral = np.nansum(
            values[:, used, :, :] * weights[used][None, :, None, None],
            axis=1,
        )
        integral[~finite] = np.nan
        outputs[int(limit_float)] = (RHO0 * CP0 * integral).astype(np.float32)
    return outputs


def select_indices(
    latitude: np.ndarray,
    longitude: np.ndarray,
    depth: np.ndarray,
) -> tuple[slice, slice, slice]:
    iy = np.flatnonzero((latitude >= LAT_MIN) & (latitude <= LAT_MAX))
    ix = np.flatnonzero((longitude >= LON_MIN) & (longitude <= LON_MAX))
    depth_weights = layer_thicknesses(depth, max(DEPTH_LIMITS))
    iz = np.flatnonzero(depth_weights > 0)
    if iy.size == 0 or ix.size == 0 or iz.size == 0:
        raise ValueError("Requested SODA3 subset is empty")
    return (
        slice(int(iz[0]), int(iz[-1]) + 1),
        slice(int(iy[0]), int(iy[-1]) + 1),
        slice(int(ix[0]), int(ix[-1]) + 1),
    )


def fetch_apdrc(
    start_year: int,
    end_year: int,
) -> tuple[list[pd.Timestamp], np.ndarray, np.ndarray, np.ndarray, dict[int, list[np.ndarray]]]:
    """Read monthly equatorial temperature from the APDRC OPeNDAP mirror."""
    dataset = netCDF4.Dataset(APDRC_URL)
    try:
        depth = np.asarray(dataset.variables["lev"][:], dtype=float)
        latitude = np.asarray(dataset.variables["lat"][:], dtype=float)
        longitude = np.asarray(dataset.variables["lon"][:], dtype=float)
        z_slice, y_slice, x_slice = select_indices(latitude, longitude, depth)
        sub_depth = depth[z_slice]
        sub_latitude = latitude[y_slice]
        sub_longitude = longitude[x_slice]
        years_available = np.arange(1980, 2023)
        start = max(start_year, int(years_available.min()))
        end = min(end_year, int(years_available.max()))
        times: list[pd.Timestamp] = []
        output: dict[int, list[np.ndarray]] = {100: [], 300: []}
        if start > end:
            return times, sub_depth, sub_latitude, sub_longitude, output
        for year in range(start, end + 1):
            first = (year - 1980) * 12
            last = first + 12
            temperature = np.ma.filled(
                dataset.variables["temp"][first:last, z_slice, y_slice, x_slice],
                np.nan,
            )
            ohc = compute_ohc(temperature, sub_depth)
            for limit in output:
                output[limit].append(ohc[limit])
            times.extend(
                pd.date_range(f"{year}-01-01", periods=12, freq="MS")
                + pd.Timedelta(days=14)
            )
            print(f"APDRC SODA3 OHC complete: {year}", flush=True)
        return times, sub_depth, sub_latitude, sub_longitude, output
    finally:
        dataset.close()


def fetch_official_year(
    year: int,
) -> tuple[list[pd.Timestamp], np.ndarray, np.ndarray, np.ndarray, dict[int, np.ndarray]]:
    """Read one annual official SODA3 file through HTTP byte ranges."""
    fsspec = import_fsspec()
    url = OFFICIAL_TEMPLATE.format(year=year)
    remote = fsspec.open(
        url,
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            depth = np.asarray(dataset["st_ocean"][:], dtype=float)
            latitude = np.asarray(dataset["yt_ocean"][:], dtype=float)
            longitude = np.asarray(dataset["xt_ocean"][:], dtype=float)
            z_slice, y_slice, x_slice = select_indices(latitude, longitude, depth)
            sub_depth = depth[z_slice]
            sub_latitude = latitude[y_slice]
            sub_longitude = longitude[x_slice]
            temperature = np.asarray(
                dataset["temp"][:, z_slice, y_slice, x_slice],
                dtype=np.float32,
            )
            ohc = compute_ohc(temperature, sub_depth)
    finally:
        remote.close()
    times = list(pd.date_range(f"{year}-01-01", periods=12, freq="MS") + pd.Timedelta(days=14))
    print(f"Official SODA3 OHC complete: {year}", flush=True)
    return times, sub_depth, sub_latitude, sub_longitude, ohc


def detrended_calendar_anomaly(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline_start: int,
    baseline_end: int,
) -> np.ndarray:
    """Remove calendar-month climatology and same-month baseline trend."""
    data = np.asarray(values, dtype=np.float64)
    result = np.full(data.shape, np.nan, dtype=np.float32)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    baseline_year = (years >= baseline_start) & (years <= baseline_end)
    for month in range(1, 13):
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


def weighted_region_mean(
    field: xr.DataArray,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> xr.DataArray:
    subset = field.sel(lat=slice(lat_min, lat_max), lon=slice(lon_min, lon_max))
    weights = np.cos(np.deg2rad(subset["lat"]))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def build_indices(dataset: xr.Dataset) -> pd.DataFrame:
    frame = pd.DataFrame({"time": pd.to_datetime(dataset["time"].values)})
    for limit in (100, 300):
        absolute = dataset[f"ohc_{limit}m"]
        anomaly = dataset[f"ohc_{limit}m_anomaly_detrended"]
        for region, bounds in REGIONS.items():
            lat0, lat1, lon0, lon1 = bounds
            frame[f"ohc{limit}_{region}_jm2"] = weighted_region_mean(
                absolute, lat0, lat1, lon0, lon1
            ).values
            frame[f"ohc{limit}_{region}_anom_jm2"] = weighted_region_mean(
                anomaly, lat0, lat1, lon0, lon1
            ).values
        frame[f"ohc{limit}_east_minus_west_anom_jm2"] = (
            frame[f"ohc{limit}_east_anom_jm2"]
            - frame[f"ohc{limit}_west_anom_jm2"]
        )
        equatorial = anomaly.sel(lat=slice(-5.0, 5.0))
        lat_weights = np.cos(np.deg2rad(equatorial["lat"]))
        zonal = equatorial.weighted(lat_weights).mean("lat", skipna=True)
        positive = zonal.clip(min=0)
        numerator = (positive * positive["lon"]).sum("lon", skipna=True)
        denominator = positive.sum("lon", skipna=True)
        frame[f"ohc{limit}_positive_centroid_deg_e"] = np.divide(
            numerator.values,
            denominator.values,
            out=np.full(numerator.shape, np.nan, dtype=float),
            where=denominator.values > 0,
        )
    frame["year"] = frame["time"].dt.year
    frame["month"] = frame["time"].dt.month
    return frame


def main() -> int:
    args = parse_args()
    if args.start_year > args.end_year:
        raise ValueError("start-year must be <= end-year")
    if args.baseline_start < args.start_year or args.baseline_end > args.end_year:
        raise ValueError("Baseline years must fall inside the requested time range")

    tag = f"{args.start_year}_{args.end_year}"
    netcdf_path = OUT_INTERIM / f"soda3_ohc_0_100_0_300_{tag}.nc"
    csv_path = OUT_DERIVED / f"soda3_ohc_indices_{tag}.csv"
    metadata_path = OUT_DERIVED / f"soda3_ohc_metadata_{tag}.json"
    if not args.force and netcdf_path.exists() and csv_path.exists() and metadata_path.exists():
        print(netcdf_path)
        print(csv_path)
        print(metadata_path)
        return 0

    OUT_INTERIM.mkdir(parents=True, exist_ok=True)
    OUT_DERIVED.mkdir(parents=True, exist_ok=True)

    times, depth, latitude, longitude, historical = fetch_apdrc(
        args.start_year,
        min(args.end_year, 2022),
    )
    collected: dict[int, list[np.ndarray]] = {100: list(historical[100]), 300: list(historical[300])}
    sources: dict[str, str] = {}
    if times:
        sources[
            f"{max(args.start_year, 1980)}-{min(args.end_year, 2022)}"
        ] = APDRC_URL

    for year in range(max(args.start_year, 2023), args.end_year + 1):
        year_times, year_depth, year_latitude, year_longitude, year_ohc = fetch_official_year(year)
        if times:
            if not (
                np.allclose(depth, year_depth)
                and np.allclose(latitude, year_latitude)
                and np.allclose(longitude, year_longitude)
            ):
                raise ValueError(f"Grid mismatch between APDRC and official data for {year}")
        else:
            depth, latitude, longitude = year_depth, year_latitude, year_longitude
        times.extend(year_times)
        for limit in collected:
            collected[limit].append(year_ohc[limit])
        sources[str(year)] = OFFICIAL_TEMPLATE.format(year=year)

    if not times:
        raise ValueError("No SODA3 records were collected")

    time_index = pd.DatetimeIndex(times)
    order = np.argsort(time_index.values)
    time_index = time_index[order]
    fields: dict[int, np.ndarray] = {}
    anomalies: dict[int, np.ndarray] = {}
    for limit in collected:
        values = np.concatenate(collected[limit], axis=0)[order]
        fields[limit] = values.astype(np.float32)
        anomalies[limit] = detrended_calendar_anomaly(
            values,
            time_index,
            args.baseline_start,
            args.baseline_end,
        )

    dataset = xr.Dataset(
        data_vars={
            "ohc_100m": (("time", "lat", "lon"), fields[100]),
            "ohc_300m": (("time", "lat", "lon"), fields[300]),
            "ohc_100m_anomaly_detrended": (("time", "lat", "lon"), anomalies[100]),
            "ohc_300m_anomaly_detrended": (("time", "lat", "lon"), anomalies[300]),
        },
        coords={
            "time": time_index,
            "lat": latitude,
            "lon": longitude,
        },
        attrs={
            "title": "SODA3.15.2 equatorial Pacific upper-ocean heat content",
            "source": "SODA3.15.2 potential temperature; APDRC OPeNDAP plus UMD official files",
            "rho0_kg_m3": RHO0,
            "cp0_j_kg_k": CP0,
            "anomaly_definition": (
                f"{args.baseline_start}-{args.baseline_end} calendar-month climatology "
                "and same-calendar-month linear trend removed"
            ),
            "spatial_domain": f"{LAT_MIN:g} to {LAT_MAX:g} N, {LON_MIN:g} to {LON_MAX:g} E",
        },
    )
    for name in ("ohc_100m", "ohc_300m"):
        dataset[name].attrs.update(
            units="J m-2",
            long_name=f"Ocean heat content integrated over 0-{name.split('_')[1]}",
        )
    for name in ("ohc_100m_anomaly_detrended", "ohc_300m_anomaly_detrended"):
        dataset[name].attrs.update(
            units="J m-2",
            long_name=f"Detrended calendar-month anomaly of {name.split('_anomaly')[0]}",
        )

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
    dataset.to_netcdf(netcdf_path, engine="netcdf4", encoding=encoding)

    indices = build_indices(dataset)
    indices.to_csv(csv_path, index=False)

    metadata = {
        "dataset": "SODA3.15.2",
        "created_by": Path(__file__).name,
        "time_start": str(time_index.min().date()),
        "time_end": str(time_index.max().date()),
        "n_months": int(time_index.size),
        "baseline": [args.baseline_start, args.baseline_end],
        "domain": {
            "lat": [float(latitude.min()), float(latitude.max())],
            "lon": [float(longitude.min()), float(longitude.max())],
        },
        "depth_center_levels_used_m": [float(value) for value in depth],
        "integration_limits_m": list(DEPTH_LIMITS),
        "constants": {"rho0_kg_m3": RHO0, "cp0_j_kg_k": CP0},
        "regions": REGIONS,
        "sources": sources,
        "notes": [
            "OHC uses potential temperature and constant reference density/specific heat.",
            "Cells without a complete water column to the requested integration depth are masked.",
            "The official annual files contain duplicated time coordinate values; calendar months are assigned by record order.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(netcdf_path)
    print(csv_path)
    print(metadata_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
