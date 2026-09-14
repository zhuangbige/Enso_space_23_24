#!/usr/bin/env python3
"""Extend the non-H20 three-box budget through 2023 using annual SODA3 files.

The official SODA3.15.2 annual files are used because the APDRC aggregation
ends in 2022.  All months of 2023 and January 2024 are retained so a centered
December 2023 storage tendency can be evaluated.  Output contains the same
mass-balanced boundary terms as the historical extractor plus full (not
temperature-gated) surface net heating for each fixed box.
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
import fetch_soda3_three_box_enthalpy_boundary_terms as enthalpy  # noqa: E402
import fetch_soda3_three_box_warm_heat_budget as warm  # noqa: E402
from fetch_soda3_equatorial_process_fields import import_fsspec  # noqa: E402


URL_TEMPLATE = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)
OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_three_box_enthalpy_budget_terms_2023_2024.csv"
)
MONTHS = {2023: tuple(range(1, 13)), 2024: tuple(range(1, 7))}


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
            zslice = contiguous_slice(depth_all, 0.0, enthalpy.DEPTH_MAX_M)
            depth = depth_all[zslice]
            t_yslice = contiguous_slice(
                t_lat_all, enthalpy.SOUTH - 0.5, enthalpy.NORTH + 0.5
            )
            t_xslice = contiguous_slice(t_lon_all, 159.5, 280.5)
            t_lat = t_lat_all[t_yslice]
            t_lon = t_lon_all[t_xslice]
            time_slice = slice(months[0] - 1, months[-1])
            temperature = clean(
                dataset["temp"][time_slice, zslice, t_yslice, t_xslice]
            )
            net_heating = clean(
                dataset["net_heating"][time_slice, t_yslice, t_xslice]
            )
            expected = len(months)
            if temperature.shape[0] != expected or net_heating.shape[0] != expected:
                raise ValueError("Unexpected annual-file time dimension")

            h_lat_mask = warm.cell_selection(t_lat, enthalpy.SOUTH, enthalpy.NORTH)
            h_lat = t_lat[h_lat_mask]
            rows: dict[str, np.ndarray] = {}
            for box, (west, east) in enthalpy.BOXES.items():
                xmask = warm.cell_selection(t_lon, west, east)
                box_lon = t_lon[xmask]
                box_temp = temperature[:, :, h_lat_mask, :][:, :, :, xmask]
                box_flux = net_heating[:, h_lat_mask, :][:, :, xmask]
                surface_all, _, _ = warm.surface_heat_terms(
                    box_flux,
                    box_temp[:, 0, :, :],
                    latitude=h_lat,
                    longitude=box_lon,
                )
                rows[f"{box}_surface_all_pw"] = surface_all

            u_yslice = contiguous_slice(u_lat_all, enthalpy.SOUTH, enthalpy.NORTH)
            u_lat = u_lat_all[u_yslice]
            if u_lat.size != h_lat.size + 1:
                raise ValueError("Unexpected latitude staggering on zonal gates")
            zonal = {}
            for gate in enthalpy.ZONAL_GATES:
                left_global, right_global = base.adjacent_indices(t_lon_all, gate)
                left = int(
                    np.flatnonzero(np.isclose(t_lon, t_lon_all[left_global]))[0]
                )
                right = int(
                    np.flatnonzero(np.isclose(t_lon, t_lon_all[right_global]))[0]
                )
                gate_temperature = 0.5 * (
                    temperature[:, :, h_lat_mask, left]
                    + temperature[:, :, h_lat_mask, right]
                )
                xindex = base.exact_index(u_lon_all, gate)
                raw_u = clean(
                    dataset["u"][
                        time_slice,
                        zslice,
                        u_yslice,
                        slice(xindex, xindex + 1),
                    ]
                )[:, :, :, 0]
                gate_u = 0.5 * (raw_u[:, :, :-1] + raw_u[:, :, 1:])
                moments = enthalpy.section_moments(
                    gate_temperature,
                    gate_u,
                    depth,
                    base.zonal_section_width(h_lat),
                )
                zonal[gate] = moments
                label = f"{int(gate)}e"
                for metric, values in zip(
                    (
                        "volume_east_sv",
                        "heat0_east_pw",
                        "area_m2",
                        "temperature_area_cm2",
                    ),
                    moments,
                    strict=True,
                ):
                    rows[f"gate_{label}_{metric}"] = values

            v_xslice = contiguous_slice(u_lon_all, 160.0, 280.0)
            v_lon = u_lon_all[v_xslice]
            tracer_v_mask = warm.cell_selection(t_lon, 160.0, 280.0)
            tracer_v_lon = t_lon[tracer_v_mask]
            if v_lon.size != tracer_v_lon.size + 1:
                raise ValueError("Unexpected longitude staggering on meridional gates")
            boundary_data = {}
            for label, latitude in (
                ("south", enthalpy.SOUTH),
                ("north", enthalpy.NORTH),
            ):
                below_global, above_global = base.adjacent_indices(t_lat_all, latitude)
                below = int(
                    np.flatnonzero(np.isclose(t_lat, t_lat_all[below_global]))[0]
                )
                above = int(
                    np.flatnonzero(np.isclose(t_lat, t_lat_all[above_global]))[0]
                )
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
                boundary_data[label] = (boundary_temperature, boundary_v, latitude)

            for box, (west, east) in enthalpy.BOXES.items():
                faces = {
                    "west": enthalpy._face(*zonal[west], inward_sign=1.0),
                    "east": enthalpy._face(*zonal[east], inward_sign=-1.0),
                }
                xmask = warm.cell_selection(tracer_v_lon, west, east)
                box_lon = tracer_v_lon[xmask]
                for boundary_label, inward_sign in (
                    ("south", 1.0),
                    ("north", -1.0),
                ):
                    boundary_temp, boundary_v, latitude = boundary_data[boundary_label]
                    moments = enthalpy.section_moments(
                        boundary_temp[:, :, xmask],
                        boundary_v[:, :, xmask],
                        depth,
                        base.meridional_section_width(box_lon, latitude),
                    )
                    faces[boundary_label] = enthalpy._face(
                        *moments, inward_sign=inward_sign
                    )
                    for metric, values in zip(
                        (
                            "volume_north_sv",
                            "heat0_north_pw",
                            "area_m2",
                            "temperature_area_cm2",
                        ),
                        moments,
                        strict=True,
                    ):
                        rows[f"{box}_{boundary_label}_{metric}"] = values
                corrected = enthalpy.mass_balance_box_faces(faces)
                for metric, values in corrected.items():
                    rows[f"{box}_{metric}"] = values
    finally:
        remote.close()

    times = pd.DatetimeIndex([pd.Timestamp(year, month, 15) for month in months])
    print(f"Official {year}: three-box enthalpy subset complete", flush=True)
    return pd.DataFrame(
        {"time": times, "year": year, "month": months, **rows}
    )


def validate(frame: pd.DataFrame) -> None:
    expected = pd.DatetimeIndex(
        [
            pd.Timestamp(year, month, 15)
            for year, months in MONTHS.items()
            for month in months
        ]
    )
    times = pd.DatetimeIndex(frame["time"])
    if not times.equals(expected) or not times.is_unique:
        raise ValueError("Unexpected extension time axis")
    numeric = frame.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        raise ValueError(
            f"Missing values: {numeric.columns[numeric.isna().any()].tolist()}"
        )
    for box in enthalpy.BOXES:
        if numeric[f"{box}_volume_convergence_corr_sv"].abs().max() > 1.0e-9:
            raise ValueError(f"Corrected volume budget does not close for {box}")
        if numeric[f"{box}_surface_all_pw"].abs().max() > 2.0:
            raise ValueError(f"Surface flux outside broad range for {box}")


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
    pieces = [
        annual_rows(year, months) for year, months in missing_by_year.items()
    ]
    if existing is not None:
        pieces.insert(0, existing)
    output = pd.concat(pieces, ignore_index=True).sort_values("time").reset_index(
        drop=True
    )
    output = output.drop_duplicates("time", keep="last").reset_index(drop=True)
    validate(output)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False, float_format="%.10g")
    print(f"Wrote {OUTPUT} ({len(output)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
