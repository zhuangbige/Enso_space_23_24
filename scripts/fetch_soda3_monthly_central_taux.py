#!/usr/bin/env python3
"""Extract 1980-2024 monthly SODA3 central-Pacific zonal-stress anomalies.

Only the 5S-5N, 180E-140W ``taux`` subset is read from official annual
SODA3.15.2 files with HTTP byte ranges.  Calendar-month linear trends over
1980-2024 are removed, matching the anomaly convention used by the existing
SODA3 process diagnostics.  The compact January-September table supplies the
monthly anchor for five-day coupling-onset analysis.
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
    source_format,
)


URL_TEMPLATE = (
    "https://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)
YEARS = tuple(range(1980, 2025))
MONTHS = tuple(range(1, 10))
LAT_BOUNDS = (-5.0, 5.0)
LON_BOUNDS = (180.0, 220.0)
OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_monthly_central_taux_1980_2024_jan_sep.csv"
)
EXISTING_JAN_JUN = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_transition_process_indices_1980_2024.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--years", nargs="+", type=int, default=list(YEARS))
    return parser.parse_args()


def weighted_mean(field: np.ndarray, latitude: np.ndarray) -> float:
    weights = np.cos(np.deg2rad(latitude))[:, None]
    valid = np.isfinite(field)
    denominator = float(np.sum(valid * weights))
    if denominator <= 0:
        raise ValueError("No valid central-Pacific stress cells")
    return float(np.nansum(field * weights) / denominator)


def read_cdf2_year(
    url: str,
    session: requests.Session,
    template: ClassicNetCDFRemote | None,
) -> tuple[pd.DataFrame, ClassicNetCDFRemote]:
    dataset = ClassicNetCDFRemote(url, session=session, template=template)
    latitude_full = dataset.read_coordinate("yu_ocean")
    longitude_full = dataset.read_coordinate("xu_ocean") % 360.0
    y_slice = contiguous_slice(latitude_full, *LAT_BOUNDS)
    x_slice = contiguous_slice(longitude_full, *LON_BOUNDS)
    latitude = latitude_full[y_slice]
    rows = []
    for month in MONTHS:
        field = dataset.read_time_3d("taux", month - 1, y_slice, x_slice)
        rows.append({"month": month, "taux_central_nm2": weighted_mean(field, latitude)})
    return pd.DataFrame(rows), dataset


def read_hdf5_year(url: str) -> pd.DataFrame:
    fsspec = import_fsspec()
    remote = fsspec.open(
        url,
        "rb",
        block_size=4 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            latitude_full = np.asarray(dataset["yu_ocean"][:], dtype=float)
            longitude_full = np.asarray(dataset["xu_ocean"][:], dtype=float) % 360.0
            y_slice = contiguous_slice(latitude_full, *LAT_BOUNDS)
            x_slice = contiguous_slice(longitude_full, *LON_BOUNDS)
            latitude = latitude_full[y_slice]
            rows = []
            for month in MONTHS:
                field = clean(dataset["taux"][month - 1, y_slice, x_slice])
                rows.append(
                    {
                        "month": month,
                        "taux_central_nm2": weighted_mean(field, latitude),
                    }
                )
    finally:
        remote.close()
    return pd.DataFrame(rows)


def add_detrended_anomaly(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["taux_central_anom_nm2"] = np.nan
    for month, indices in output.groupby("month").groups.items():
        current = output.loc[indices]
        years = current["year"].to_numpy(dtype=float)
        values = current["taux_central_nm2"].to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(years)), years])
        intercept, slope = np.linalg.lstsq(design, values, rcond=None)[0]
        output.loc[indices, "taux_central_anom_nm2"] = values - (
            intercept + slope * years
        )
    return output.sort_values(["year", "month"]).reset_index(drop=True)


def validate(frame: pd.DataFrame, requested_years: list[int]) -> None:
    expected = len(requested_years) * len(MONTHS)
    if len(frame) != expected or frame.duplicated(["year", "month"]).any():
        raise ValueError("Monthly stress coverage is incomplete or duplicated")
    if not frame["taux_central_nm2"].between(-0.5, 0.5).all():
        raise ValueError("Monthly stress falls outside physical QA bounds")
    if set(requested_years) == set(YEARS):
        residual_mean = frame.groupby("month")["taux_central_anom_nm2"].mean().abs()
        if float(residual_mean.max()) > 1.0e-12:
            raise ValueError("Detrended calendar-month residuals do not average to zero")
        if EXISTING_JAN_JUN.exists():
            reference = pd.read_csv(EXISTING_JAN_JUN)[
                ["year", "month", "taux_central_nm2_anom"]
            ]
            check = frame.loc[frame["month"] <= 6].merge(
                reference,
                on=["year", "month"],
                validate="one_to_one",
            )
            difference = np.abs(
                check["taux_central_anom_nm2"] - check["taux_central_nm2_anom"]
            )
            print(
                "Cross-check against existing Jan-Jun process product: "
                f"median |difference|={difference.median():.5f}, "
                f"max={difference.max():.5f} N m-2",
                flush=True,
            )


def main() -> int:
    args = parse_args()
    years = sorted(set(args.years))
    if OUTPUT.exists() and not args.force and years == list(YEARS):
        print(f"Already exists: {OUTPUT}")
        return 0
    session = requests.Session()
    pieces = []
    for year in years:
        url = URL_TEMPLATE.format(year=year)
        kind = source_format(url, session)
        if kind == "cdf2":
            # Annual CDF-2 headers change at least once within the archive;
            # parse each small header instead of reusing stale byte offsets.
            current, _ = read_cdf2_year(url, session, None)
        else:
            current = read_hdf5_year(url)
        current["year"] = year
        current["time"] = [pd.Timestamp(year, month, 15) for month in current["month"]]
        current["source_url"] = url
        pieces.append(current)
        print(f"{year}: monthly central stress complete ({kind})", flush=True)
    output = add_detrended_anomaly(pd.concat(pieces, ignore_index=True))
    validate(output, years)
    destination = OUTPUT if years == list(YEARS) else OUTPUT.with_name(
        f"soda3_monthly_central_taux_{min(years)}_{max(years)}_jan_sep.csv"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination, index=False)
    print(f"Wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
