#!/usr/bin/env python3
"""Fetch compact SODA3 terms for a 160E-180E warm-heat box budget.

Only three terms are retained for each five-day record: north/south Q20 heat
transport, their convergence into 5S-5N, and the surface net heat input over
5S-5N, 160E-180E.  Full remote NetCDF files are never stored locally.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys
import time

import h5py
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_5day_event_transport as source  # noqa: E402


DEFAULT_YEARS = (1997, 2015, 2023)
WEST, EAST = 160.0, 180.0
SOUTH, NORTH = -5.0, 5.0
DEPTH_MAX_M = 300.0
RHO0, CP0 = 1025.0, 3990.0
EARTH_RADIUS = 6_371_000.0
OUT_DIR = ROOT / "data/interim/research_2026/soda3_5day_box_budget_terms"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def coordinate(dataset: h5py.File, name: str) -> np.ndarray:
    return np.asarray(dataset[name][:], dtype=float)


def interp_tracer_to_velocity_longitude(
    temperature: np.ndarray,
    tracer_lon: np.ndarray,
    velocity_lon: np.ndarray,
) -> np.ndarray:
    """Interpolate depth-longitude temperature to the velocity longitude."""
    output = np.empty((temperature.shape[0], len(velocity_lon)), dtype=float)
    for depth_index, row in enumerate(temperature):
        valid = np.isfinite(row)
        output[depth_index] = (
            np.interp(velocity_lon, tracer_lon[valid], row[valid])
            if valid.sum() >= 2
            else np.nan
        )
    return output


def meridional_gate_q20(
    temperature: np.ndarray,
    velocity: np.ndarray,
    *,
    depth: np.ndarray,
    tracer_lat: np.ndarray,
    tracer_lon: np.ndarray,
    velocity_lat: np.ndarray,
    velocity_lon: np.ndarray,
    latitude: float,
) -> float:
    """Northward Q20 heat transport across one latitude gate, in PW."""
    velocity_y = int(np.argmin(np.abs(velocity_lat - latitude)))
    if not np.isclose(velocity_lat[velocity_y], latitude, atol=1.0e-6):
        raise ValueError(f"No velocity latitude at {latitude}")
    below = int(np.flatnonzero(tracer_lat < latitude)[-1])
    above = int(np.flatnonzero(tracer_lat > latitude)[0])
    boundary_temperature = 0.5 * (
        temperature[:, below, :] + temperature[:, above, :]
    )
    boundary_temperature = interp_tracer_to_velocity_longitude(
        boundary_temperature, tracer_lon, velocity_lon
    )
    boundary_velocity = velocity[:, velocity_y, :]
    if boundary_temperature.shape != boundary_velocity.shape:
        raise ValueError("Temperature and meridional velocity gates differ")
    valid = np.isfinite(boundary_temperature) & np.isfinite(boundary_velocity)
    warm_excess = np.where(
        valid, np.maximum(boundary_temperature - 20.0, 0.0), np.nan
    )
    x_m = EARTH_RADIUS * np.cos(np.deg2rad(latitude)) * np.deg2rad(velocity_lon)
    transport_by_depth = np.trapz(
        boundary_velocity * warm_excess, x=x_m, axis=1
    )
    dz = np.diff(source.depth_bounds(depth, DEPTH_MAX_M))
    return float(RHO0 * CP0 * np.nansum(transport_by_depth * dz) / 1.0e15)


def surface_heat_input(
    heat_flux: np.ndarray,
    *,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> tuple[float, float, float]:
    """Return integrated surface heating (PW), area mean and valid fraction."""
    if len(latitude) < 2 or len(longitude) < 2:
        raise ValueError("Surface box needs at least two points per direction")
    dlat = float(np.median(np.diff(latitude)))
    dlon = float(np.median(np.diff(longitude)))
    lat_south = np.deg2rad(latitude - dlat / 2.0)
    lat_north = np.deg2rad(latitude + dlat / 2.0)
    cell_area_lat = (
        EARTH_RADIUS**2
        * np.deg2rad(dlon)
        * (np.sin(lat_north) - np.sin(lat_south))
    )
    area = np.broadcast_to(cell_area_lat[:, None], heat_flux.shape)
    valid = np.isfinite(heat_flux)
    total_area = float(np.nansum(np.where(valid, area, np.nan)))
    total_watts = float(np.nansum(np.where(valid, heat_flux * area, np.nan)))
    expected_area = float(np.sum(area))
    return (
        total_watts / 1.0e15,
        total_watts / total_area,
        total_area / expected_area,
    )


def derive_terms(
    timestamp: pd.Timestamp,
    url: str,
    *,
    temperature: np.ndarray,
    velocity: np.ndarray,
    net_heating: np.ndarray,
    depth: np.ndarray,
    tracer_lat: np.ndarray,
    tracer_lon: np.ndarray,
    velocity_lat: np.ndarray,
    velocity_lon: np.ndarray,
    surface_lat: np.ndarray,
    surface_lon: np.ndarray,
) -> dict[str, object]:
    q20_south = meridional_gate_q20(
        temperature,
        velocity,
        depth=depth,
        tracer_lat=tracer_lat,
        tracer_lon=tracer_lon,
        velocity_lat=velocity_lat,
        velocity_lon=velocity_lon,
        latitude=SOUTH,
    )
    q20_north = meridional_gate_q20(
        temperature,
        velocity,
        depth=depth,
        tracer_lat=tracer_lat,
        tracer_lon=tracer_lon,
        velocity_lat=velocity_lat,
        velocity_lon=velocity_lon,
        latitude=NORTH,
    )
    surface_pw, surface_mean, valid_fraction = surface_heat_input(
        net_heating, latitude=surface_lat, longitude=surface_lon
    )
    return {
        "time": timestamp,
        "year": timestamp.year,
        "q20_south_northward_pw": q20_south,
        "q20_north_northward_pw": q20_north,
        "q20_meridional_convergence_pw": q20_south - q20_north,
        "surface_net_heating_pw": surface_pw,
        "surface_net_heating_wm2": surface_mean,
        "surface_valid_area_fraction": valid_fraction,
        "source_url": url,
    }


def process_hdf5(timestamp: pd.Timestamp, url: str) -> dict[str, object]:
    fsspec = source.import_fsspec()
    remote = fsspec.open(
        url, "rb", block_size=16 * 1024 * 1024, cache_type="readahead"
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            required = {
                "temp", "v", "net_heating", "st_ocean", "yt_ocean",
                "xt_ocean", "yu_ocean", "xu_ocean",
            }
            missing = required - set(dataset)
            if missing:
                raise KeyError(f"Missing variables: {sorted(missing)}")
            depth_full = coordinate(dataset, "st_ocean")
            tracer_lat_full = coordinate(dataset, "yt_ocean")
            tracer_lon_full = coordinate(dataset, "xt_ocean") % 360.0
            velocity_lat_full = coordinate(dataset, "yu_ocean")
            velocity_lon_full = coordinate(dataset, "xu_ocean") % 360.0

            z_slice = source.contiguous_slice(depth_full, 0.0, DEPTH_MAX_M)
            tracer_y_slice = source.contiguous_slice(
                tracer_lat_full, SOUTH - 0.6, NORTH + 0.6
            )
            tracer_x_slice = source.contiguous_slice(
                tracer_lon_full, WEST - 0.6, EAST + 0.6
            )
            velocity_y_slice = source.contiguous_slice(
                velocity_lat_full, SOUTH, NORTH
            )
            velocity_x_slice = source.contiguous_slice(
                velocity_lon_full, WEST, EAST
            )
            surface_y_slice = source.contiguous_slice(
                tracer_lat_full, SOUTH, NORTH
            )
            surface_x_slice = source.contiguous_slice(
                tracer_lon_full, WEST, EAST
            )

            temperature = source.clean(
                dataset["temp"][0, z_slice, tracer_y_slice, tracer_x_slice]
            )
            velocity = source.clean(
                dataset["v"][0, z_slice, velocity_y_slice, velocity_x_slice]
            )
            net_heating = source.clean(
                dataset["net_heating"][0, surface_y_slice, surface_x_slice]
            )

            depth = depth_full[z_slice]
            tracer_lat = tracer_lat_full[tracer_y_slice]
            tracer_lon = tracer_lon_full[tracer_x_slice]
            velocity_lat = velocity_lat_full[velocity_y_slice]
            velocity_lon = velocity_lon_full[velocity_x_slice]
            surface_lat = tracer_lat_full[surface_y_slice]
            surface_lon = tracer_lon_full[surface_x_slice]

            return derive_terms(
                timestamp,
                url,
                temperature=temperature,
                velocity=velocity,
                net_heating=net_heating,
                depth=depth,
                tracer_lat=tracer_lat,
                tracer_lon=tracer_lon,
                velocity_lat=velocity_lat,
                velocity_lon=velocity_lon,
                surface_lat=surface_lat,
                surface_lon=surface_lon,
            )
    finally:
        remote.close()


def process_cdf2(timestamp: pd.Timestamp, url: str) -> dict[str, object]:
    session = requests.Session()
    dataset = source.ClassicNetCDFRemote(url, session=session)
    required = {
        "temp", "v", "net_heating", "st_ocean", "yt_ocean",
        "xt_ocean", "yu_ocean", "xu_ocean",
    }
    missing = required - set(dataset.variables)
    if missing:
        raise KeyError(f"Missing variables: {sorted(missing)}")
    depth_full = dataset.read_coordinate("st_ocean")
    tracer_lat_full = dataset.read_coordinate("yt_ocean")
    tracer_lon_full = dataset.read_coordinate("xt_ocean") % 360.0
    velocity_lat_full = dataset.read_coordinate("yu_ocean")
    velocity_lon_full = dataset.read_coordinate("xu_ocean") % 360.0

    z_slice = source.contiguous_slice(depth_full, 0.0, DEPTH_MAX_M)
    tracer_y_slice = source.contiguous_slice(
        tracer_lat_full, SOUTH - 0.6, NORTH + 0.6
    )
    tracer_x_slice = source.contiguous_slice(
        tracer_lon_full, WEST - 0.6, EAST + 0.6
    )
    velocity_y_slice = source.contiguous_slice(velocity_lat_full, SOUTH, NORTH)
    velocity_x_slice = source.contiguous_slice(velocity_lon_full, WEST, EAST)
    surface_y_slice = source.contiguous_slice(tracer_lat_full, SOUTH, NORTH)
    surface_x_slice = source.contiguous_slice(tracer_lon_full, WEST, EAST)

    temperature = dataset.read_record_4d(
        "temp", z_slice, tracer_y_slice, tracer_x_slice
    )
    velocity = dataset.read_record_4d(
        "v", z_slice, velocity_y_slice, velocity_x_slice
    )
    net_heating = dataset.read_record_3d(
        "net_heating", surface_y_slice, surface_x_slice
    )
    return derive_terms(
        timestamp,
        url,
        temperature=temperature,
        velocity=velocity,
        net_heating=net_heating,
        depth=depth_full[z_slice],
        tracer_lat=tracer_lat_full[tracer_y_slice],
        tracer_lon=tracer_lon_full[tracer_x_slice],
        velocity_lat=velocity_lat_full[velocity_y_slice],
        velocity_lon=velocity_lon_full[velocity_x_slice],
        surface_lat=tracer_lat_full[surface_y_slice],
        surface_lon=tracer_lon_full[surface_x_slice],
    )


def process_year(
    year: int,
    files: list[tuple[pd.Timestamp, str]],
    *,
    force: bool,
    max_files: int | None,
    workers: int,
) -> Path:
    suffix = f"_first{max_files}" if max_files else ""
    output = OUT_DIR / f"soda3_5day_box_terms_{year}_jan_jun{suffix}.csv"
    selected = files[:max_files] if max_files else files
    cache_dir = OUT_DIR / "cache" / str(year)
    rows: list[dict[str, object]] = []
    pending: list[tuple[int, pd.Timestamp, str, Path]] = []
    for index, (timestamp, url) in enumerate(selected, 1):
        cache_path = cache_dir / f"{timestamp:%Y_%m_%d}.csv"
        if cache_path.exists() and not force:
            rows.append(pd.read_csv(cache_path, parse_dates=["time"]).iloc[0].to_dict())
            print(f"{year}: reused {index}/{len(selected)} ({timestamp.date()})", flush=True)
            continue
        pending.append((index, timestamp, url, cache_path))

    def fetch_one(item: tuple[int, pd.Timestamp, str, Path]) -> tuple[int, dict[str, object]]:
        index, timestamp, url, cache_path = item
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                kind = source.source_format(url, requests.Session())
                if kind == "hdf5":
                    row = process_hdf5(timestamp, url)
                elif kind == "cdf2":
                    row = process_cdf2(timestamp, url)
                else:
                    raise ValueError(f"Unsupported SODA source format {kind}")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame([row]).to_csv(cache_path, index=False)
                return index, row
            except Exception as error:
                last_error = error
                if attempt < 3:
                    time.sleep(2.0 * attempt)
        if last_error is None:
            raise RuntimeError("Fetch failed without an exception")
        raise last_error

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch_one, item): item for item in pending}
        for future in as_completed(futures):
            index, timestamp, _, _ = futures[future]
            _, row = future.result()
            rows.append(row)
            print(
                f"{year}: processed {index}/{len(selected)} ({timestamp.date()})",
                flush=True,
            )
    frame = pd.DataFrame(rows).sort_values("time")
    if frame["time"].duplicated().any():
        raise ValueError(f"Duplicate time records for {year}")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    print(f"Wrote {output}", flush=True)
    return output


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    files = source.list_event_files(years)
    for year in years:
        process_year(
            year,
            files[year],
            force=args.force,
            max_files=args.max_files,
            workers=args.workers,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
