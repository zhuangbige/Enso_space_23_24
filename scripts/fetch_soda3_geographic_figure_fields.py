#!/usr/bin/env python3
"""Prepare the compact SODA3 OHC anomaly fields needed by the figure atlas.

The default source is the locally cached SODA3.15.2 0--300 m OHC file.  The
script recomputes the anomaly from absolute OHC using a 1980--2022
same-calendar-month linear expectation, then retains only the three events,
two analysis phases, and the 130E--80W, 10S--5N plotting region.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "data/interim/research_2026/soda3_ohc/"
    "soda3_ohc_0_100_0_300_1980_2024.nc"
)
DEFAULT_OUTPUT = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_geographic_figure_fields_1997_2015_2023.nc"
)
EVENTS = (1997, 2015, 2023)
PHASES = ("arrival_Jan_Jun", "fate_Jan_May_next")
BASELINE_START = 1980
BASELINE_END = 2022


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _linear_expectation(
    values: np.ndarray,
    years: np.ndarray,
    target_year: int,
) -> np.ndarray:
    """Return cellwise linear expectation with NaN-safe closed-form OLS."""
    values = np.asarray(values, dtype=np.float64)
    years = np.asarray(years, dtype=np.float64)
    x = years - years.mean()
    valid = np.isfinite(values)
    count = valid.sum(axis=0)
    safe = np.where(valid, values, 0.0)
    mean = np.divide(
        safe.sum(axis=0),
        count,
        out=np.full(values.shape[1:], np.nan, dtype=np.float64),
        where=count > 1,
    )
    numerator = np.sum(np.where(valid, x[:, None, None] * (values - mean), 0.0), axis=0)
    denominator = np.sum(np.where(valid, x[:, None, None] ** 2, 0.0), axis=0)
    slope = np.divide(
        numerator,
        denominator,
        out=np.zeros_like(mean),
        where=denominator > 0,
    )
    return mean + slope * (target_year - years.mean())


def prepare_fields(source: Path) -> xr.Dataset:
    with xr.open_dataset(source) as raw:
        if "ohc_300m" not in raw:
            raise KeyError(f"ohc_300m not found in {source}")
        ohc = raw["ohc_300m"].sel(lat=slice(-10.0, 5.0), lon=slice(130.0, 280.0)).load()
        source_attrs = dict(raw.attrs)

    time_index = pd.DatetimeIndex(ohc["time"].values)
    baseline_mask = (time_index.year >= BASELINE_START) & (time_index.year <= BASELINE_END)
    output = np.full(
        (len(EVENTS), len(PHASES), ohc.sizes["lat"], ohc.sizes["lon"]),
        np.nan,
        dtype=np.float32,
    )

    for event_index, event in enumerate(EVENTS):
        for phase_index, phase in enumerate(PHASES):
            target_year = event if phase == "arrival_Jan_Jun" else event + 1
            months = range(1, 7) if phase == "arrival_Jan_Jun" else range(1, 6)
            anomalies = []
            for month in months:
                baseline_month_mask = baseline_mask & (time_index.month == month)
                baseline_values = ohc.isel(time=np.flatnonzero(baseline_month_mask)).values
                baseline_years = time_index.year[baseline_month_mask]
                expectation = _linear_expectation(
                    baseline_values,
                    baseline_years,
                    target_year,
                )
                target_mask = (time_index.year == target_year) & (time_index.month == month)
                target_indices = np.flatnonzero(target_mask)
                if target_indices.size != 1:
                    raise ValueError(
                        f"Expected one SODA3 record for {target_year}-{month:02d}, "
                        f"found {target_indices.size}"
                    )
                anomalies.append(ohc.isel(time=int(target_indices[0])).values - expectation)
            stacked = np.stack(anomalies)
            valid_count = np.isfinite(stacked).sum(axis=0)
            phase_mean = np.divide(
                np.nansum(stacked, axis=0),
                valid_count,
                out=np.full(stacked.shape[1:], np.nan, dtype=np.float64),
                where=valid_count > 0,
            )
            output[event_index, phase_index] = (phase_mean / 1.0e9).astype(np.float32)

    dataset = xr.Dataset(
        {
            "ohc300_anom_gjm2": (
                ("event", "phase", "lat", "lon"),
                output,
                {
                    "long_name": "0-300 m ocean heat content anomaly",
                    "units": "GJ m-2",
                },
            )
        },
        coords={
            "event": np.asarray(EVENTS, dtype=np.int16),
            "phase": np.asarray(PHASES, dtype=str),
            "lat": ohc["lat"].values.astype(np.float32),
            "lon": ohc["lon"].values.astype(np.float32),
        },
        attrs={
            "title": "Compact SODA3 fields for the ENSO geographic figure atlas",
            "source": source_attrs.get("source", "SODA3.15.2"),
            "source_file": str(source),
            "baseline": "1980-2022 same-calendar-month linear expectation",
            "depth_range": "0-300 m",
            "phase_definition": (
                "arrival_Jan_Jun = event-year January-June mean; "
                "fate_Jan_May_next = following-year January-May mean"
            ),
        },
    )
    return dataset


def write_fields(dataset: xr.Dataset, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    encoding = {"ohc300_anom_gjm2": {"zlib": True, "complevel": 4, "dtype": "float32"}}
    dataset.to_netcdf(output, engine="netcdf4", encoding=encoding)


def main() -> int:
    args = parse_args()
    if args.output.exists() and not args.force:
        print(f"Using existing {args.output}")
        return 0
    if not args.source.exists():
        raise FileNotFoundError(args.source)
    dataset = prepare_fields(args.source)
    write_fields(dataset, args.output)
    print(f"Wrote {args.output} ({args.output.stat().st_size / 2**20:.2f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
