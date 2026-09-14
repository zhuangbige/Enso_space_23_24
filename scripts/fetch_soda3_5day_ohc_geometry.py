#!/usr/bin/env python3
"""Build five-day SODA3 OHC-geometry and central-wind indices.

This product is designed for the ENSO coupling question "given comparable
total upper-ocean heat, does its eastward position determine when the
atmospheric westerly response becomes sustained?"  For 13 El Nino onset
years, it streams only the 0-300 m, 5S-5N, 180E-80W temperature subset and
the 5S-5N, 180E-140W zonal wind stress from SODA3.15.2 five-day files.

The within-month five-day OHC variability is anchored to the existing
1980-2024 detrended monthly SODA3 OHC anomaly field.  This keeps the same
climatology as the project's monthly products while retaining five-day
timing.  Raw per-year profiles are cached after every source file so a long
remote extraction can be resumed safely.
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


EVENT_YEARS = (
    1982,
    1986,
    1991,
    1994,
    1997,
    2002,
    2004,
    2006,
    2009,
    2015,
    2018,
    2019,
    2023,
)
LAT_BOUNDS = (-5.0, 5.0)
OHC_LON_BOUNDS = (180.0, 280.0)
EAST_GATE_LON = 220.0  # 140W
STRESS_LON_BOUNDS = (180.0, 220.0)
DEPTH_MAX_M = 300.0
END_MONTH = 9
RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0

MONTHLY_OHC_NC = (
    ROOT
    / "data/interim/research_2026/soda3_ohc/"
    "soda3_ohc_0_100_0_300_1980_2024.nc"
)
MONTHLY_TAUX_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_monthly_central_taux_1980_2024_jan_sep.csv"
)
OUTPUT_DIR = (
    ROOT / "data/interim/research_2026/soda3_5day_ohc_geometry"
)
PROFILE_OUTPUT = (
    OUTPUT_DIR
    / "soda3_5day_ohc_profiles_13events_1982_2023_jan_sep.csv.gz"
)
INDEX_OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_5day_ohc_geometry_coupling_13events_jan_sep.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=list(EVENT_YEARS))
    parser.add_argument("--end-month", type=int, default=END_MONTH)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-files", type=int)
    parser.add_argument(
        "--finalize-only",
        action="store_true",
        help="Build aligned products from complete per-year caches without network access",
    )
    return parser.parse_args()


def layer_thicknesses(depth: np.ndarray) -> np.ndarray:
    """Return layer portions between the surface and 300 m."""
    depth = np.asarray(depth, dtype=float)
    edges = np.empty(depth.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    edges[-1] = depth[-1] + 0.5 * (depth[-1] - depth[-2])
    thickness = np.maximum(
        0.0,
        np.minimum(edges[1:], DEPTH_MAX_M) - edges[:-1],
    )
    if not np.isclose(thickness.sum(), DEPTH_MAX_M, atol=1.0e-6):
        raise ValueError(
            f"Integrated layer thickness is {thickness.sum():.6f} m, not 300 m"
        )
    return thickness


def latitude_mean_ohc_profile(
    temperature: np.ndarray,
    depth: np.ndarray,
    latitude: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return 5S-5N mean absolute OHC and valid-column fraction by longitude."""
    if temperature.shape[:2] != (len(depth), len(latitude)):
        raise ValueError("Temperature dimensions do not match depth/latitude")
    thickness = layer_thicknesses(depth)
    used = thickness > 0
    valid_column = np.all(np.isfinite(temperature[used]), axis=0)
    heat = RHO0 * CP0 * np.nansum(
        temperature[used] * thickness[used, None, None],
        axis=0,
    )
    heat[~valid_column] = np.nan
    weights = np.cos(np.deg2rad(latitude))[:, None]
    valid = np.isfinite(heat)
    denominator = np.sum(valid * weights, axis=0)
    numerator = np.nansum(heat * weights, axis=0)
    profile = np.divide(
        numerator,
        denominator,
        out=np.full(heat.shape[1], np.nan, dtype=float),
        where=denominator > 0,
    )
    return profile, valid.mean(axis=0)


def latitude_mean_stress(
    field: np.ndarray,
    latitude: np.ndarray,
) -> float:
    weights = np.cos(np.deg2rad(latitude))[:, None]
    valid = np.isfinite(field)
    denominator = float(np.sum(valid * weights))
    if denominator <= 0:
        raise ValueError("No valid central-Pacific wind-stress cells")
    return float(np.nansum(field * weights) / denominator)


def read_hdf5_fields(
    url: str,
    cache: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, ...]]:
    fsspec = import_fsspec()
    remote = fsspec.open(
        url,
        "rb",
        block_size=8 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            if "hdf_geometry_grid" not in cache:
                depth_full = np.asarray(dataset["st_ocean"][:], dtype=float)
                lat_full = np.asarray(dataset["yt_ocean"][:], dtype=float)
                lon_full = np.asarray(dataset["xt_ocean"][:], dtype=float) % 360.0
                u_lat_full = np.asarray(dataset["yu_ocean"][:], dtype=float)
                u_lon_full = np.asarray(dataset["xu_ocean"][:], dtype=float) % 360.0
                z_slice = contiguous_slice(depth_full, 0.0, DEPTH_MAX_M)
                y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
                x_slice = contiguous_slice(lon_full, *OHC_LON_BOUNDS)
                uy_slice = contiguous_slice(u_lat_full, *LAT_BOUNDS)
                ux_slice = contiguous_slice(u_lon_full, *STRESS_LON_BOUNDS)
                cache["hdf_geometry_grid"] = (
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
            grid = cache["hdf_geometry_grid"]
            z_slice, y_slice, x_slice, uy_slice, ux_slice = grid[5:]
            temperature = clean(dataset["temp"][0, z_slice, y_slice, x_slice])
            stress = clean(dataset["taux"][0, uy_slice, ux_slice])
    finally:
        remote.close()
    return temperature, stress, grid


def read_cdf2_fields(
    url: str,
    session: requests.Session,
    cache: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, ...]]:
    template = cache.get("template")
    dataset = ClassicNetCDFRemote(
        url,
        session=session,
        template=template if isinstance(template, ClassicNetCDFRemote) else None,
    )
    if template is None:
        cache["template"] = dataset
    if "cdf_geometry_grid" not in cache:
        depth_full = dataset.read_coordinate("st_ocean")
        lat_full = dataset.read_coordinate("yt_ocean")
        lon_full = dataset.read_coordinate("xt_ocean") % 360.0
        u_lat_full = dataset.read_coordinate("yu_ocean")
        u_lon_full = dataset.read_coordinate("xu_ocean") % 360.0
        z_slice = contiguous_slice(depth_full, 0.0, DEPTH_MAX_M)
        y_slice = contiguous_slice(lat_full, *LAT_BOUNDS)
        x_slice = contiguous_slice(lon_full, *OHC_LON_BOUNDS)
        uy_slice = contiguous_slice(u_lat_full, *LAT_BOUNDS)
        ux_slice = contiguous_slice(u_lon_full, *STRESS_LON_BOUNDS)
        cache["cdf_geometry_grid"] = (
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
    grid = cache["cdf_geometry_grid"]
    z_slice, y_slice, x_slice, uy_slice, ux_slice = grid[5:]
    temperature = dataset.read_record_4d("temp", z_slice, y_slice, x_slice)
    stress = dataset.read_record_3d("taux", uy_slice, ux_slice)
    return temperature, stress, grid


def raw_cache_path(year: int, end_month: int) -> Path:
    return OUTPUT_DIR / f"raw_profile_{year}_jan_{end_month:02d}.csv"


def process_year(
    year: int,
    files: list[tuple[pd.Timestamp, str]],
    *,
    end_month: int,
    force: bool,
    max_files: int | None,
) -> Path:
    """Stream one event year and append each completed pentad to its cache."""
    path = raw_cache_path(year, end_month)
    if force or not path.exists():
        existing = pd.DataFrame()
    else:
        existing = pd.read_csv(path, parse_dates=["time"])
    completed = set(pd.to_datetime(existing.get("time", pd.Series(dtype="datetime64[ns]"))))
    selected = files[:max_files] if max_files else files
    missing = [(time, url) for time, url in selected if time not in completed]
    if not missing:
        print(f"Already complete: {path}", flush=True)
        return path

    session = requests.Session()
    cache: dict[str, object] = {}
    first_write = existing.empty
    for index, (timestamp, url) in enumerate(missing, 1):
        kind = cache.get("source_format")
        if kind is None:
            kind = source_format(url, session)
            cache["source_format"] = kind
        if kind == "hdf5":
            temperature, stress, grid = read_hdf5_fields(url, cache)
        else:
            temperature, stress, grid = read_cdf2_fields(url, session, cache)
        depth, lat, lon, stress_lat, _ = grid[:5]
        ohc, valid_fraction = latitude_mean_ohc_profile(
            temperature,
            np.asarray(depth),
            np.asarray(lat),
        )
        stress_mean = latitude_mean_stress(stress, np.asarray(stress_lat))
        rows = pd.DataFrame(
            {
                "time": timestamp,
                "year": year,
                "month": timestamp.month,
                "day": timestamp.day,
                "longitude_e": np.round(np.asarray(lon, dtype=float), 2),
                "ohc300_raw_jm2": ohc,
                "valid_column_fraction": valid_fraction,
                "taux_central_180_220e_nm2": stress_mean,
                "source_url": url,
            }
        )
        rows.to_csv(
            path,
            mode="w" if first_write else "a",
            header=first_write,
            index=False,
        )
        first_write = False
        print(
            f"{year}: geometry {index}/{len(missing)} "
            f"({timestamp.date()}, {kind})",
            flush=True,
        )
    return path


def decode_monthly_times(dataset: h5py.File) -> pd.DatetimeIndex:
    units = dataset["time"].attrs["units"]
    if isinstance(units, bytes):
        units = units.decode("ascii")
    prefix = "days since "
    if not str(units).startswith(prefix):
        raise ValueError(f"Unsupported monthly time units: {units}")
    origin = pd.Timestamp(str(units)[len(prefix) :])
    return pd.DatetimeIndex(origin + pd.to_timedelta(dataset["time"][:], unit="D"))


def monthly_reference_profiles(
    years: list[int],
    end_month: int,
    target_lon: np.ndarray,
) -> dict[tuple[int, int], tuple[np.ndarray, np.ndarray]]:
    """Load monthly raw and detrended OHC profiles with h5py."""
    output: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
    with h5py.File(MONTHLY_OHC_NC, "r") as dataset:
        times = decode_monthly_times(dataset)
        latitude = np.asarray(dataset["lat"][:], dtype=float)
        longitude = np.asarray(dataset["lon"][:], dtype=float) % 360.0
        y_index = np.flatnonzero(
            (latitude >= LAT_BOUNDS[0]) & (latitude <= LAT_BOUNDS[1])
        )
        x_index = np.flatnonzero(
            (longitude >= OHC_LON_BOUNDS[0])
            & (longitude <= OHC_LON_BOUNDS[1])
        )
        if not len(y_index) or not len(x_index):
            raise ValueError("Monthly OHC file does not cover the target box")
        weights = np.cos(np.deg2rad(latitude[y_index]))[:, None]
        for year in years:
            # One following month permits causal interpolation through the
            # end of the requested season.  December is the natural cap.
            for month in range(1, min(12, end_month + 1) + 1):
                matches = np.flatnonzero((times.year == year) & (times.month == month))
                if len(matches) != 1:
                    raise ValueError(
                        f"Expected one monthly OHC field for {year}-{month:02d}"
                    )
                raw_field = np.asarray(
                    dataset["ohc_300m"][
                        int(matches[0]), y_index.min() : y_index.max() + 1,
                        x_index.min() : x_index.max() + 1,
                    ],
                    dtype=float,
                )
                anomaly_field = np.asarray(
                    dataset["ohc_300m_anomaly_detrended"][
                        int(matches[0]), y_index.min() : y_index.max() + 1,
                        x_index.min() : x_index.max() + 1,
                    ],
                    dtype=float,
                )
                profiles = []
                for field in (raw_field, anomaly_field):
                    field[field <= -1.0e19] = np.nan
                    valid = np.isfinite(field)
                    numerator = np.nansum(field * weights, axis=0)
                    denominator = np.sum(valid * weights, axis=0)
                    profile = np.divide(
                        numerator,
                        denominator,
                        out=np.full(len(x_index), np.nan, dtype=float),
                        where=denominator > 0,
                    )
                    profiles.append(
                        np.interp(target_lon, longitude[x_index], profile)
                    )
                output[(year, month)] = (profiles[0], profiles[1])
    return output


def anchor_profiles_to_monthly(
    frame: pd.DataFrame,
    years: list[int],
    end_month: int,
) -> pd.DataFrame:
    """Subtract the monthly climatology-plus-trend without future leakage."""
    output = frame.copy()
    output["time"] = pd.to_datetime(output["time"])
    longitudes = np.sort(output["longitude_e"].unique())
    references = monthly_reference_profiles(years, end_month, longitudes)
    anomaly_series = []
    for year, indices in output.groupby("year").groups.items():
        current = output.loc[indices].sort_values(["time", "longitude_e"])
        pivot = current.pivot(index="time", columns="longitude_e", values="ohc300_raw_jm2")
        pivot = pivot.reindex(columns=longitudes)
        reference_months = range(1, min(12, end_month + 1) + 1)
        reference_times = pd.DatetimeIndex(
            [pd.Timestamp(int(year), month, 15) for month in reference_months]
        )
        baseline = np.vstack(
            [
                references[(int(year), month)][0]
                - references[(int(year), month)][1]
                for month in reference_months
            ]
        )
        interpolated = np.empty_like(pivot.to_numpy(dtype=float))
        target_numeric = pivot.index.astype("int64").to_numpy(dtype=float)
        source_numeric = reference_times.astype("int64").to_numpy(dtype=float)
        for longitude_index in range(len(longitudes)):
            interpolated[:, longitude_index] = np.interp(
                target_numeric,
                source_numeric,
                baseline[:, longitude_index],
            )
        anomaly = pivot.to_numpy(dtype=float) - interpolated
        mapped = pd.DataFrame(
            anomaly,
            index=pivot.index,
            columns=pivot.columns,
        ).stack(future_stack=True)
        mapped.index.names = ["time", "longitude_e"]
        anomaly_series.append(mapped.rename("ohc300_anom_jm2"))
    aligned = pd.concat(anomaly_series)
    keys = pd.MultiIndex.from_arrays(
        [output["time"], output["longitude_e"]],
        names=["time", "longitude_e"],
    )
    output["ohc300_anom_jm2"] = aligned.reindex(keys).to_numpy(dtype=float)
    if output["ohc300_anom_jm2"].isna().any():
        raise ValueError("Monthly anchoring produced missing OHC anomalies")
    return output


def integrate_longitude(values: np.ndarray, longitude: np.ndarray) -> float:
    x_metres = EARTH_RADIUS * np.deg2rad(longitude)
    return float(np.trapz(values, x=x_metres))


def geometry_indices(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for timestamp, group in frame.groupby("time", sort=True):
        current = group.sort_values("longitude_e")
        longitude = current["longitude_e"].to_numpy(dtype=float)
        anomaly = current["ohc300_anom_jm2"].to_numpy(dtype=float)
        positive = np.maximum(anomaly, 0.0)
        total = integrate_longitude(positive, longitude)
        east = longitude >= EAST_GATE_LON
        east_heat = integrate_longitude(positive[east], longitude[east])
        centroid = (
            integrate_longitude(positive * longitude, longitude) / total
            if total > 0
            else np.nan
        )
        west = longitude <= EAST_GATE_LON
        rows.append(
            {
                "time": pd.Timestamp(timestamp),
                "year": int(current["year"].iloc[0]),
                "month": int(current["month"].iloc[0]),
                "day": int(current["day"].iloc[0]),
                "ohc300_mean_180e_80w_gj_m2": float(np.nanmean(anomaly) / 1.0e9),
                "ohc300_positive_total_pj_m": total / 1.0e15,
                "ohc300_positive_east140w_pj_m": east_heat / 1.0e15,
                "ohc300_positive_east140w_fraction": east_heat / total if total > 0 else np.nan,
                "ohc300_positive_centroid_deg_e": centroid,
                "ohc300_west_180e_140w_gj_m2": float(np.nanmean(anomaly[west]) / 1.0e9),
                "ohc300_east_140w_80w_gj_m2": float(np.nanmean(anomaly[east]) / 1.0e9),
                "ohc300_east_minus_west_gj_m2": float(
                    (np.nanmean(anomaly[east]) - np.nanmean(anomaly[west])) / 1.0e9
                ),
                "taux_central_180_220e_raw_nm2": float(
                    current["taux_central_180_220e_nm2"].iloc[0]
                ),
                "minimum_valid_column_fraction": float(
                    current["valid_column_fraction"].min()
                ),
                "fraction_longitudes_at_least_90pct_valid": float(
                    (current["valid_column_fraction"] >= 0.90).mean()
                ),
            }
        )
    output = pd.DataFrame(rows).sort_values("time")
    monthly_stress = pd.read_csv(MONTHLY_TAUX_CSV)
    output["taux_central_180_220e_anom_nm2"] = np.nan
    for year, indices in output.groupby("year").groups.items():
        reference = monthly_stress.loc[
            monthly_stress["year"].eq(year)
            & monthly_stress["month"].between(1, 9)
        ].sort_values("month")
        if len(reference) != 9:
            raise ValueError(f"Missing monthly stress anchors for {year}")
        reference_times = pd.DatetimeIndex(
            [pd.Timestamp(int(year), int(month), 15) for month in reference["month"]]
        )
        baseline = (
            reference["taux_central_nm2"]
            - reference["taux_central_anom_nm2"]
        ).to_numpy(dtype=float)
        target_times = pd.to_datetime(output.loc[indices, "time"])
        interpolated = np.interp(
            target_times.astype("int64").to_numpy(dtype=float),
            reference_times.astype("int64").to_numpy(dtype=float),
            baseline,
        )
        output.loc[indices, "taux_central_180_220e_anom_nm2"] = (
            output.loc[indices, "taux_central_180_220e_raw_nm2"].to_numpy(dtype=float)
            - interpolated
        )
    pieces = []
    rolling_columns = [
        "ohc300_positive_total_pj_m",
        "ohc300_positive_east140w_fraction",
        "ohc300_positive_centroid_deg_e",
        "ohc300_east_minus_west_gj_m2",
        "taux_central_180_220e_anom_nm2",
    ]
    for _, group in output.groupby("year", sort=True):
        current = group.sort_values("time").copy()
        for column in rolling_columns:
            # Trailing rather than centered: predictors at time t must never
            # contain information from the following pentad.
            current[f"{column}_15day"] = current[column].rolling(
                3, min_periods=2
            ).mean()
            current[f"{column}_change15day"] = current[column].diff(3)
        pieces.append(current)
    return pd.concat(pieces, ignore_index=True).sort_values("time")


def validate_products(
    profiles: pd.DataFrame,
    indices: pd.DataFrame,
    years: list[int],
    end_month: int,
) -> None:
    if profiles.duplicated(["time", "longitude_e"]).any():
        raise ValueError("Duplicate five-day profile cells")
    if indices.duplicated("time").any():
        raise ValueError("Duplicate five-day index timestamps")
    if set(indices["year"].unique()) != set(years):
        raise ValueError("Output event-year coverage is incomplete")
    if int(indices["month"].max()) != end_month:
        raise ValueError("Output does not reach the requested end month")
    if not indices["fraction_longitudes_at_least_90pct_valid"].between(0.98, 1.0).all():
        raise ValueError("Too many longitudes have low valid-column coverage")
    check = profiles.groupby(["year", "month", "longitude_e"], as_index=False)[
        "ohc300_anom_jm2"
    ].mean()
    longitude = np.sort(profiles["longitude_e"].unique())
    targets = monthly_reference_profiles(years, end_month, longitude)
    maximum_error = 0.0
    for (year, month), group in check.groupby(["year", "month"]):
        current = group.sort_values("longitude_e")["ohc300_anom_jm2"].to_numpy()
        maximum_error = max(
            maximum_error,
            float(
                np.nanmax(
                    np.abs(current - targets[(int(year), int(month))][1])
                )
            ),
        )
    if maximum_error > 7.5e8:
        raise ValueError(f"Monthly profile alignment error is {maximum_error:.3g} J m-2")
    monthly_stress = pd.read_csv(MONTHLY_TAUX_CSV)
    stress_check = indices.groupby(["year", "month"], as_index=False)[
        "taux_central_180_220e_anom_nm2"
    ].mean().merge(
        monthly_stress[["year", "month", "taux_central_anom_nm2"]],
        on=["year", "month"],
        validate="one_to_one",
    )
    stress_error = float(
        np.abs(
            stress_check["taux_central_180_220e_anom_nm2"]
            - stress_check["taux_central_anom_nm2"]
        ).max()
    )
    if stress_error > 0.005:
        raise ValueError(f"Monthly stress alignment error is {stress_error:.3g} N m-2")
    print(
        "Validation: maximum causal monthly OHC mismatch "
        f"{maximum_error / 1.0e9:.3f} GJ m-2"
    )
    print(f"Validation: maximum causal monthly stress mismatch {stress_error:.4f} N m-2")


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    if not 1 <= args.end_month <= 12:
        raise ValueError("--end-month must be between 1 and 12")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if args.finalize_only:
        paths = [raw_cache_path(year, args.end_month) for year in years]
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Missing raw profile caches: {missing}")
    else:
        files = list_event_files(years, end_month=args.end_month)
        paths = [
            process_year(
                year,
                files[year],
                end_month=args.end_month,
                force=args.force,
                max_files=args.max_files,
            )
            for year in years
        ]
    if args.max_files:
        print("Subset extraction complete; aligned combined product not built.")
        return 0
    profiles = pd.concat(
        [pd.read_csv(path, parse_dates=["time"]) for path in paths],
        ignore_index=True,
    ).sort_values(["time", "longitude_e"])
    # CDF-2 coordinates are float32 while HDF5 coordinates are float64.
    # They represent the same 0.5-degree grid but can differ in the last
    # decimal; normalize before combining historical and 2023 profiles.
    profiles["longitude_e"] = profiles["longitude_e"].round(2)
    if profiles.duplicated(["time", "longitude_e"]).any():
        raise ValueError("Longitude normalization created duplicate profile cells")
    profiles = anchor_profiles_to_monthly(profiles, years, args.end_month)
    indices = geometry_indices(profiles)
    validate_products(profiles, indices, years, args.end_month)
    profiles.to_csv(PROFILE_OUTPUT, index=False, compression="gzip")
    indices.to_csv(INDEX_OUTPUT, index=False)
    print(f"Wrote {PROFILE_OUTPUT}")
    print(f"Wrote {INDEX_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
