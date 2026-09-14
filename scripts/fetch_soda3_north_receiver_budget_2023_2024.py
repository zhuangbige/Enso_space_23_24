#!/usr/bin/env python3
"""Fetch the 2023/24 SODA3 north-receiver H20 budget from annual files.

Reads the official University of Maryland annual SODA3.15.2 NetCDF files by
HTTP byte range.  The output covers all months of 2023 and January--June 2024
for the fixed 5N--12N, 140W--80W, 0--300 m receiver box.  June 2024 is kept
so the centered May 2024 storage tendency and three-month mean are defined.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import h5py
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_soda3_chakravorty_transport_baseline as base  # noqa: E402
import fetch_soda3_three_box_warm_heat_budget as three_box  # noqa: E402
from fetch_soda3_equatorial_process_fields import import_fsspec  # noqa: E402


URL_TEMPLATE = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)
OUTPUT = ROOT / "data/derived/research_2026/soda3_north_receiver_budget_terms_2023_2024.csv"
MONTHS = {2023: tuple(range(1, 13)), 2024: tuple(range(1, 8))}
SOUTH = 5.0
NORTH = 12.0
WEST = 220.0
EAST = 280.0
DEPTH_MAX_M = 300.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def contiguous_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    indices = np.flatnonzero((values >= lower) & (values <= upper))
    if indices.size == 0 or not np.all(np.diff(indices) == 1):
        raise ValueError(f"Cannot form contiguous slice for {lower}..{upper}")
    return slice(int(indices[0]), int(indices[-1]) + 1)


def clean(values: np.ndarray) -> np.ndarray:
    output = np.asarray(values, dtype=np.float32)
    output[output <= -1.0e10] = np.nan
    return output


def annual_rows(year: int, months: tuple[int, ...]) -> pd.DataFrame:
    url = URL_TEMPLATE.format(year=year)
    fsspec = import_fsspec()
    print(f"Opening official annual file: {year}", flush=True)
    remote = fsspec.open(
        url,
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            required = (
                "st_ocean",
                "yt_ocean",
                "xt_ocean",
                "yu_ocean",
                "xu_ocean",
                "temp",
                "net_heating",
                "u",
                "v",
            )
            missing = [name for name in required if name not in dataset]
            if missing:
                raise KeyError(f"Missing official SODA3 variables: {missing}")

            depth_all = np.asarray(dataset["st_ocean"][:], dtype=float)
            t_lat_all = np.asarray(dataset["yt_ocean"][:], dtype=float)
            t_lon_all = np.asarray(dataset["xt_ocean"][:], dtype=float) % 360.0
            u_lat_all = np.asarray(dataset["yu_ocean"][:], dtype=float)
            u_lon_all = np.asarray(dataset["xu_ocean"][:], dtype=float) % 360.0
            zslice = contiguous_slice(depth_all, 0.0, DEPTH_MAX_M)
            depth = depth_all[zslice]
            t_yslice = contiguous_slice(t_lat_all, SOUTH - 0.5, NORTH + 0.5)
            t_xslice = contiguous_slice(t_lon_all, WEST - 0.5, EAST + 0.5)
            t_lat = t_lat_all[t_yslice]
            t_lon = t_lon_all[t_xslice]
            time_slice = slice(months[0] - 1, months[-1])
            temperature = clean(dataset["temp"][time_slice, zslice, t_yslice, t_xslice])
            net_heating = clean(dataset["net_heating"][time_slice, t_yslice, t_xslice])

            h_lat_mask = three_box.cell_selection(t_lat, SOUTH, NORTH)
            h_lon_mask = three_box.cell_selection(t_lon, WEST, EAST)
            h_lat = t_lat[h_lat_mask]
            h_lon = t_lon[h_lon_mask]
            box_temp = temperature[:, :, h_lat_mask, :][:, :, :, h_lon_mask]
            box_flux = net_heating[:, h_lat_mask, :][:, :, h_lon_mask]
            rows: dict[str, np.ndarray] = {}
            rows["receiver_h20_zj"] = three_box.warm_heat_content_zj(
                box_temp, depth=depth, latitude=h_lat, longitude=h_lon
            )
            all_pw, warm_pw, warm_fraction = three_box.surface_heat_terms(
                box_flux,
                box_temp[:, 0, :, :],
                latitude=h_lat,
                longitude=h_lon,
            )
            rows["receiver_surface_all_pw"] = all_pw
            rows["receiver_surface_warm_pw"] = warm_pw
            rows["receiver_surface_warm_area_fraction"] = warm_fraction

            u_yslice = contiguous_slice(u_lat_all, SOUTH, NORTH)
            u_lat = u_lat_all[u_yslice]
            if u_lat.size != h_lat.size + 1:
                raise ValueError("Unexpected latitude staggering on zonal gates")
            for label, gate in (("west", WEST), ("east", EAST)):
                left_global, right_global = base.adjacent_indices(t_lon_all, gate)
                left = int(np.flatnonzero(np.isclose(t_lon, t_lon_all[left_global]))[0])
                right = int(np.flatnonzero(np.isclose(t_lon, t_lon_all[right_global]))[0])
                gate_temperature = 0.5 * (
                    temperature[:, :, h_lat_mask, left]
                    + temperature[:, :, h_lat_mask, right]
                )
                u_xindex = base.exact_index(u_lon_all, gate)
                raw_u = clean(
                    dataset["u"][
                        time_slice,
                        zslice,
                        u_yslice,
                        slice(u_xindex, u_xindex + 1),
                    ]
                )[:, :, :, 0]
                gate_u = 0.5 * (raw_u[:, :, :-1] + raw_u[:, :, 1:])
                _, q20 = base.section_transports(
                    gate_temperature,
                    gate_u,
                    depth,
                    base.zonal_section_width(h_lat),
                )
                rows[f"receiver_{label}_q20_east_pw"] = q20

            v_xslice = contiguous_slice(u_lon_all, WEST, EAST)
            v_lon = u_lon_all[v_xslice]
            tracer_v_mask = three_box.cell_selection(t_lon, WEST, EAST)
            tracer_v_lon = t_lon[tracer_v_mask]
            if v_lon.size != tracer_v_lon.size + 1:
                raise ValueError("Unexpected longitude staggering on meridional gates")
            for label, latitude, inflow_sign in (
                ("south", SOUTH, 1.0),
                ("north", NORTH, -1.0),
            ):
                below_global, above_global = base.adjacent_indices(t_lat_all, latitude)
                below = int(np.flatnonzero(np.isclose(t_lat, t_lat_all[below_global]))[0])
                above = int(np.flatnonzero(np.isclose(t_lat, t_lat_all[above_global]))[0])
                boundary_temperature = 0.5 * (
                    temperature[:, :, below, :][:, :, tracer_v_mask]
                    + temperature[:, :, above, :][:, :, tracer_v_mask]
                )
                yindex = base.exact_index(u_lat_all, latitude)
                raw_v = clean(
                    dataset["v"][
                        time_slice,
                        zslice,
                        slice(yindex, yindex + 1),
                        v_xslice,
                    ]
                )[:, :, 0, :]
                boundary_v = 0.5 * (raw_v[:, :, :-1] + raw_v[:, :, 1:])
                _, q20 = base.section_transports(
                    boundary_temperature,
                    inflow_sign * boundary_v,
                    depth,
                    base.meridional_section_width(tracer_v_lon, latitude),
                )
                rows[f"receiver_{label}_q20_in_pw"] = q20
    finally:
        remote.close()

    rows["receiver_zonal_convergence_pw"] = (
        rows["receiver_west_q20_east_pw"] - rows["receiver_east_q20_east_pw"]
    )
    rows["receiver_meridional_convergence_pw"] = (
        rows["receiver_south_q20_in_pw"] + rows["receiver_north_q20_in_pw"]
    )
    rows["receiver_resolved_warm_flux_pw"] = (
        rows["receiver_zonal_convergence_pw"]
        + rows["receiver_meridional_convergence_pw"]
        + rows["receiver_surface_warm_pw"]
    )
    times = pd.DatetimeIndex([pd.Timestamp(year, month, 15) for month in months])
    print(f"Official {year}: receiver budget subset complete", flush=True)
    return pd.DataFrame(
        {"time": times, "year": year, "month": months, **rows}
    )


def validate(frame: pd.DataFrame) -> None:
    expected = pd.DatetimeIndex(
        [pd.Timestamp(year, month, 15) for year, months in MONTHS.items() for month in months]
    )
    times = pd.DatetimeIndex(frame["time"])
    if not times.equals(expected) or not times.is_unique:
        raise ValueError("Unexpected extension time axis")
    numeric = frame.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        raise ValueError(f"Missing values: {numeric.columns[numeric.isna().any()].tolist()}")
    if not numeric["receiver_h20_zj"].between(0.0, 200.0).all():
        raise ValueError("H20 outside broad physical range")
    q_columns = [name for name in frame if "q20" in name and name.endswith("_pw")]
    if not (numeric[q_columns].abs() < 10.0).all().all():
        raise ValueError("Q20 outside broad physical range")
    surface_columns = [name for name in frame if "surface" in name and name.endswith("_pw")]
    if not (numeric[surface_columns].abs() < 2.0).all().all():
        raise ValueError("Surface flux outside broad physical range")


def main() -> int:
    args = parse_args()
    existing = None
    if OUTPUT.exists() and not args.force:
        existing = pd.read_csv(OUTPUT, parse_dates=["time"])
        existing_keys = set(zip(existing["year"], existing["month"]))
        missing_by_year = {
            year: tuple(month for month in months if (year, month) not in existing_keys)
            for year, months in MONTHS.items()
        }
        missing_by_year = {
            year: months for year, months in missing_by_year.items() if months
        }
        if not missing_by_year:
            print(f"Already complete: {OUTPUT}")
            return 0
        print(f"Extending existing output with {missing_by_year}", flush=True)
    else:
        missing_by_year = MONTHS
    pieces = [annual_rows(year, months) for year, months in missing_by_year.items()]
    if existing is not None:
        pieces.insert(0, existing)
    output = pd.concat(pieces, ignore_index=True).sort_values("time").reset_index(drop=True)
    output = output.drop_duplicates(subset=["time"], keep="last").reset_index(drop=True)
    validate(output)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False, float_format="%.9g")
    print(f"Wrote {OUTPUT} ({len(output)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
