#!/usr/bin/env python3
"""Validate the completed 24-month Isca control spin-up."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/isca_control_spinup_t42"
REQUIRED = ("ps", "temp", "ucomp", "vcomp", "t_surf", "precipitation")


def weighted_mean_2d(data: xr.DataArray, weights: xr.DataArray) -> float:
    return float(data.weighted(weights).mean(("lat", "lon")).item())


def main() -> None:
    files = sorted(DATA.glob("run[0-9][0-9][0-9][0-9]/spinup_monthly.nc"))
    if len(files) != 24:
        raise RuntimeError(f"Expected 24 monthly files, found {len(files)}")

    extrema = {name: [np.inf, -np.inf] for name in REQUIRED}
    time_values: list[float] = []
    global_series = {"t_surf": [], "ps": [], "precipitation": []}
    reference_coords: dict[str, np.ndarray] | None = None

    for month, path in enumerate(files, start=1):
        with xr.open_dataset(path, engine="netcdf4", decode_times=False) as ds:
            if ds.sizes.get("time") != 1:
                raise RuntimeError(f"{path}: expected one monthly time record")
            missing = [name for name in REQUIRED if name not in ds]
            if missing:
                raise RuntimeError(f"{path}: missing variables {missing}")

            coords = {name: ds[name].values.copy() for name in ("lat", "lon", "pfull")}
            if reference_coords is None:
                reference_coords = coords
                if not np.all(np.diff(coords["lat"]) > 0):
                    raise RuntimeError("Latitude is not strictly south-to-north")
                if not np.all(np.diff(coords["lon"]) > 0):
                    raise RuntimeError("Longitude is not strictly increasing")
            else:
                for name in coords:
                    if not np.array_equal(coords[name], reference_coords[name]):
                        raise RuntimeError(f"{path}: inconsistent {name} coordinate")

            time_values.append(float(ds["time"].item()))
            weights = np.cos(np.deg2rad(ds["lat"]))

            for name in REQUIRED:
                values = ds[name].values
                if not np.isfinite(values).all():
                    bad = int(values.size - np.isfinite(values).sum())
                    raise RuntimeError(f"{path}: {name} contains {bad} non-finite values")
                extrema[name][0] = min(extrema[name][0], float(values.min()))
                extrema[name][1] = max(extrema[name][1], float(values.max()))

            global_series["t_surf"].append(weighted_mean_2d(ds["t_surf"].isel(time=0), weights))
            global_series["ps"].append(weighted_mean_2d(ds["ps"].isel(time=0), weights))
            global_series["precipitation"].append(
                weighted_mean_2d(ds["precipitation"].isel(time=0), weights) * 86400.0
            )

    time_values_array = np.asarray(time_values)
    if not np.all(np.diff(time_values_array) > 0):
        raise RuntimeError(f"Monthly time coordinate is not monotonic: {time_values}")

    restart = DATA / "restarts/res0024.tar.gz"
    if not restart.exists() or restart.stat().st_size == 0:
        raise RuntimeError("Final restart res0024.tar.gz is missing or empty")

    print("status=PASS")
    print(f"months={len(files)}")
    print(f"time_first={time_values_array[0]:.1f} days")
    print(f"time_last={time_values_array[-1]:.1f} days")
    print(f"time_step_unique={np.unique(np.diff(time_values_array)).tolist()} days")
    print(
        "grid="
        f"lat:{reference_coords['lat'].size},lon:{reference_coords['lon'].size},"
        f"pfull:{reference_coords['pfull'].size}"
    )
    print(f"restart={restart} ({restart.stat().st_size / 1024**2:.1f} MiB)")

    for name in REQUIRED:
        print(f"range_{name}={extrema[name][0]:.6g},{extrema[name][1]:.6g}")

    labels = {
        "t_surf": "K",
        "ps": "Pa",
        "precipitation": "mm/day",
    }
    for name, values in global_series.items():
        array = np.asarray(values)
        slope = float(np.polyfit(np.arange(array.size), array, 1)[0])
        half_difference = float(array[12:].mean() - array[:12].mean())
        print(
            f"global_{name}="
            f"mean:{array.mean():.6g} {labels[name]},"
            f"min:{array.min():.6g},max:{array.max():.6g},"
            f"slope:{slope:.6g} {labels[name]}/month,"
            f"last12_minus_first12:{half_difference:.6g} {labels[name]}"
        )


if __name__ == "__main__":
    main()
