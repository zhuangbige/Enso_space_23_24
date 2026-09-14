#!/usr/bin/env python3
"""Extract compact five-day SODA3 central-Pacific 0-300 m OHC indices.

Only the temperature subset needed for 5S-5N, 180-140W and 0-300 m is
streamed from the official SODA3.15.2 files.  The full ~285 MB source files
are not downloaded.  Five-day OHC is aligned to the existing 1980-2024
monthly detrended OHC baseline, and paired with the already extracted SODA3
five-day central-Pacific zonal wind stress.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import h5py
import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_soda3_5day_event_transport import (  # noqa: E402
    ClassicNetCDFRemote,
    clean,
    contiguous_slice,
    import_fsspec,
    list_event_files,
    source_format,
)


DEFAULT_YEARS = (1997, 2002, 2023)
LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (180.0, 220.0)
DEPTH_MAX_M = 300.0
RHO0 = 1025.0
CP0 = 3990.0

OUTPUT_DIR = ROOT / "data/interim/research_2026/soda3_5day_ohc"
LEGACY_COMBINED_CSV = OUTPUT_DIR / "soda3_5day_ohc_1997_2002_2023_jan_jun.csv"
MONTHLY_OHC_CSV = ROOT / "data/derived/research_2026/soda3_ohc_indices_1980_2024.csv"
STRESS_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "soda3_5day_wwb_stress_1982_2023_event_years.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-files", type=int)
    return parser.parse_args()


def combined_output_path(years: list[int]) -> Path:
    """Return a deterministic combined filename without overwriting other runs."""
    if tuple(years) == tuple(DEFAULT_YEARS):
        return LEGACY_COMBINED_CSV
    return OUTPUT_DIR / (
        f"soda3_5day_ohc_{len(years)}events_{min(years)}_{max(years)}_jan_jun.csv"
    )


def layer_thicknesses(depth: np.ndarray, limit: float = DEPTH_MAX_M) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    edges = np.empty(depth.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    edges[-1] = depth[-1] + 0.5 * (depth[-1] - depth[-2])
    return np.maximum(0.0, np.minimum(edges[1:], limit) - edges[:-1])


def area_weighted_ohc(
    temperature: np.ndarray,
    depth: np.ndarray,
    latitude: np.ndarray,
) -> tuple[float, float, float]:
    """Return area-mean 0-300 m OHC, depth-mean T, and valid fraction."""
    if temperature.shape != (len(depth), len(latitude), temperature.shape[2]):
        raise ValueError("Temperature coordinate dimensions are inconsistent")
    dz = layer_thicknesses(depth)
    used = dz > 0
    if not np.isclose(dz.sum(), DEPTH_MAX_M, atol=1.0e-5):
        raise ValueError(f"Integrated layer thickness is {dz.sum()}, expected 300 m")
    valid_column = np.all(np.isfinite(temperature[used]), axis=0)
    integral = np.nansum(
        temperature[used] * dz[used, None, None],
        axis=0,
    )
    integral[~valid_column] = np.nan
    weights = np.cos(np.deg2rad(latitude))[:, None]
    valid = np.isfinite(integral)
    denominator = float(np.sum(valid * weights))
    if denominator <= 0:
        raise ValueError("No valid central-Pacific OHC cells")
    mean_t_dz = float(np.nansum(integral * weights) / denominator)
    valid_fraction = float(valid.mean())
    return (
        RHO0 * CP0 * mean_t_dz,
        mean_t_dz / DEPTH_MAX_M,
        valid_fraction,
    )


def read_hdf5_temperature(
    url: str,
    cache: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    fsspec = import_fsspec()
    remote = fsspec.open(
        url,
        "rb",
        block_size=8 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            if "hdf_grid" not in cache:
                depth_full = np.asarray(dataset["st_ocean"][:], dtype=float)
                lat_full = np.asarray(dataset["yt_ocean"][:], dtype=float)
                lon_full = np.asarray(dataset["xt_ocean"][:], dtype=float) % 360.0
                z_slice = contiguous_slice(depth_full, 0.0, DEPTH_MAX_M)
                y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
                x_slice = contiguous_slice(lon_full, *LON_BOUNDS)
                cache["hdf_grid"] = (
                    depth_full[z_slice],
                    lat_full[y_slice],
                    lon_full[x_slice],
                    z_slice,
                    y_slice,
                    x_slice,
                )
            depth, lat, lon, z_slice, y_slice, x_slice = cache["hdf_grid"]
            temperature = clean(dataset["temp"][0, z_slice, y_slice, x_slice])
    finally:
        remote.close()
    return temperature, np.asarray(depth), np.asarray(lat), np.asarray(lon)


def read_cdf2_temperature(
    url: str,
    session: requests.Session,
    cache: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    template = cache.get("template")
    dataset = ClassicNetCDFRemote(
        url,
        session=session,
        template=template if isinstance(template, ClassicNetCDFRemote) else None,
    )
    if template is None:
        cache["template"] = dataset
    if "cdf_grid" not in cache:
        depth_full = dataset.read_coordinate("st_ocean")
        lat_full = dataset.read_coordinate("yt_ocean")
        lon_full = dataset.read_coordinate("xt_ocean") % 360.0
        z_slice = contiguous_slice(depth_full, 0.0, DEPTH_MAX_M)
        y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
        x_slice = contiguous_slice(lon_full, *LON_BOUNDS)
        cache["cdf_grid"] = (
            depth_full[z_slice],
            lat_full[y_slice],
            lon_full[x_slice],
            z_slice,
            y_slice,
            x_slice,
        )
    depth, lat, lon, z_slice, y_slice, x_slice = cache["cdf_grid"]
    temperature = dataset.read_record_4d("temp", z_slice, y_slice, x_slice)
    return temperature, np.asarray(depth), np.asarray(lat), np.asarray(lon)


def process_year(
    year: int,
    files: list[tuple[pd.Timestamp, str]],
    *,
    force: bool,
    max_files: int | None,
) -> Path:
    suffix = f"_first{max_files}" if max_files else ""
    output = OUTPUT_DIR / f"soda3_5day_ohc_{year}_jan_jun{suffix}.csv"
    if output.exists() and not force:
        print(f"Already exists: {output}", flush=True)
        return output
    selected = files[:max_files] if max_files else files
    session = requests.Session()
    cache: dict[str, object] = {}
    rows = []
    for index, (timestamp, url) in enumerate(selected, 1):
        kind = cache.get("source_format")
        if kind is None:
            kind = source_format(url, session)
            cache["source_format"] = kind
        if kind == "hdf5":
            temperature, depth, lat, lon = read_hdf5_temperature(url, cache)
        else:
            temperature, depth, lat, lon = read_cdf2_temperature(url, session, cache)
        ohc, mean_temperature, valid_fraction = area_weighted_ohc(
            temperature,
            depth,
            lat,
        )
        rows.append(
            {
                "time": timestamp,
                "year": year,
                "month": timestamp.month,
                "day": timestamp.day,
                "ohc300_central_jm2": ohc,
                "temp300_central_mean_c": mean_temperature,
                "valid_column_fraction": valid_fraction,
                "source_url": url,
            }
        )
        print(
            f"{year}: OHC {index}/{len(selected)} ({timestamp.date()})",
            flush=True,
        )
    frame = pd.DataFrame(rows).sort_values("time")
    if frame["time"].duplicated().any():
        raise ValueError(f"Duplicate SODA3 timestamps for {year}")
    frame.to_csv(output, index=False)
    print(f"Wrote {output}", flush=True)
    return output


def align_to_monthly_baseline(frame: pd.DataFrame) -> pd.DataFrame:
    monthly = pd.read_csv(MONTHLY_OHC_CSV, parse_dates=["time"])
    output = frame.copy()
    output["time"] = pd.to_datetime(output["time"])
    output["ohc300_central_anom_gj_m2"] = np.nan
    output["monthly_alignment_offset_gj_m2"] = np.nan
    for year, indices in output.groupby("year").groups.items():
        current = output.loc[indices].sort_values("time")
        reference = monthly.loc[
            monthly["year"].eq(year) & monthly["month"].between(1, 6),
            [
                "time",
                "month",
                "ohc300_central_jm2",
                "ohc300_central_anom_jm2",
            ],
        ].sort_values("time")
        if len(reference) != 6:
            raise ValueError(f"Expected six monthly OHC references for {year}")
        correction = (
            reference["ohc300_central_jm2"]
            - reference["ohc300_central_anom_jm2"]
        ).to_numpy(dtype=float)
        interpolated = np.interp(
            current["time"].astype("int64").to_numpy(dtype=float),
            reference["time"].astype("int64").to_numpy(dtype=float),
            correction,
        )
        raw_anomaly = (
            current["ohc300_central_jm2"].to_numpy(dtype=float) - interpolated
        ) / 1.0e9
        current_indices = current.index.to_numpy()
        output.loc[current_indices, "ohc300_central_anom_gj_m2"] = raw_anomaly
        for month, month_indices in current.groupby("month").groups.items():
            target = float(
                reference.loc[
                    reference["month"].eq(month),
                    "ohc300_central_anom_jm2",
                ].iloc[0]
                / 1.0e9
            )
            raw_mean = float(output.loc[month_indices, "ohc300_central_anom_gj_m2"].mean())
            offset = target - raw_mean
            output.loc[month_indices, "ohc300_central_anom_gj_m2"] += offset
            output.loc[month_indices, "monthly_alignment_offset_gj_m2"] = offset
    return output.sort_values("time").reset_index(drop=True)


def add_stress_and_smoothing(frame: pd.DataFrame) -> pd.DataFrame:
    stress = pd.read_csv(STRESS_CSV, parse_dates=["time"])
    stress = stress[
        ["time", "year", "taux_central_180_220e_nm2"]
    ].drop_duplicates("time")
    output = frame.merge(stress, on=["time", "year"], how="left", validate="one_to_one")
    if output["taux_central_180_220e_nm2"].isna().any():
        missing = output.loc[output["taux_central_180_220e_nm2"].isna(), "time"]
        raise ValueError(f"Missing matching SODA3 five-day stress: {missing.tolist()}")
    pieces = []
    for _, group in output.groupby("year", sort=True):
        current = group.sort_values("time").copy()
        current["ohc300_central_anom_15day_gj_m2"] = current[
            "ohc300_central_anom_gj_m2"
        ].rolling(3, center=True, min_periods=2).mean()
        current["taux_central_15day_nm2"] = current[
            "taux_central_180_220e_nm2"
        ].rolling(3, center=True, min_periods=2).mean()
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True).sort_values("time")


def validate_monthly_alignment(frame: pd.DataFrame) -> None:
    monthly = pd.read_csv(MONTHLY_OHC_CSV)
    target = monthly.loc[
        monthly["year"].isin(frame["year"].unique())
        & monthly["month"].between(1, 6),
        ["year", "month", "ohc300_central_anom_jm2"],
    ].copy()
    target["target_gj_m2"] = target["ohc300_central_anom_jm2"] / 1.0e9
    aggregated = (
        frame.groupby(["year", "month"], as_index=False)["ohc300_central_anom_gj_m2"]
        .mean()
        .rename(columns={"ohc300_central_anom_gj_m2": "five_day_mean_gj_m2"})
    )
    check = aggregated.merge(target, on=["year", "month"], validate="one_to_one")
    error = np.abs(check["five_day_mean_gj_m2"] - check["target_gj_m2"])
    if float(error.max()) > 1.0e-8:
        raise ValueError(f"Monthly OHC alignment failed; maximum error {error.max()}")
    if not frame["valid_column_fraction"].between(0.99, 1.0).all():
        raise ValueError("Unexpected missing central-Pacific water columns")


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = list_event_files(years)
    paths = [
        process_year(
            year,
            files[year],
            force=args.force,
            max_files=args.max_files,
        )
        for year in years
    ]
    if args.max_files:
        print("Subset extraction complete; combined aligned product not built.")
        return 0
    pieces = [pd.read_csv(path, parse_dates=["time"]) for path in paths]
    combined = pd.concat(pieces, ignore_index=True).sort_values("time")
    combined = align_to_monthly_baseline(combined)
    combined = add_stress_and_smoothing(combined)
    validate_monthly_alignment(combined)
    combined_csv = combined_output_path(years)
    combined.to_csv(combined_csv, index=False)
    print(f"Wrote {combined_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
