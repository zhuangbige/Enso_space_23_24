#!/usr/bin/env python3
"""Fetch ORAS5 equatorial wind-stress time series for 2026 diagnostics.

The gridded ORAS5 product is large on the native curvilinear ocean grid. For a
lightweight current-state diagnostic matching the previous D20 transect, use
the official CDS ORAS5 time-series product at nearest native-grid points along
the equatorial Pacific.
"""

from __future__ import annotations

import argparse
import io
import time
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_RAW = ROOT / "data/raw/oras5_timeseries"
OUT_INTERIM = ROOT / "data/interim/research_2026"

DATASET = "reanalysis-oras5-timeseries"
VARIABLES = ["zonal_wind_stress", "meridional_wind_stress"]
DATE_RANGE = "1980-01-01/2026-05-01"


def _lon_label(lon: int) -> str:
    if lon == 180:
        return "180"
    if lon < 180:
        return f"{lon}E"
    return f"{360 - lon}W"


def _query_lon(lon: int) -> int:
    """CDS time-series location lookup expects western longitudes as negatives."""
    return lon if lon <= 180 else lon - 360


def _download_one(lon: int, latitude: float, *, force: bool, dry_run: bool, retries: int = 3) -> Path:
    OUT_RAW.mkdir(parents=True, exist_ok=True)
    target = OUT_RAW / f"oras5_windstress_eq_{_lon_label(lon)}_1980_202605.zip"
    if target.exists() and target.stat().st_size > 0 and not force:
        print(f"exists: {target}")
        return target

    request = {
        "product_type": ["consolidated", "operational"],
        "variable": VARIABLES,
        "date": DATE_RANGE,
        "location": {"latitude": latitude, "longitude": _query_lon(lon)},
        "data_format": "csv",
    }
    if dry_run:
        print(DATASET)
        print(target)
        print(request)
        return target

    import cdsapi

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            print(
                f"request lon={lon} query_lon={_query_lon(lon)} lat={latitude} attempt={attempt}: {target}",
                flush=True,
            )
            cdsapi.Client().retrieve(DATASET, request, str(target))
            return target
        except Exception as exc:  # noqa: BLE001 - keep long CDS batches resumable.
            last_error = exc
            if attempt == retries:
                break
            sleep_seconds = 20 * attempt
            print(f"retry after CDS error for lon={lon}: {exc}; sleeping {sleep_seconds}s", flush=True)
            time.sleep(sleep_seconds)
    raise RuntimeError(f"failed to download ORAS5 wind stress at lon={lon}") from last_error


def _read_zip_csv(path: Path, requested_lon: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with ZipFile(path) as zf:
        for name in zf.namelist():
            product = "operational" if "operational" in name else "consolidated"
            payload = zf.read(name)
            df = pd.read_csv(io.BytesIO(payload), parse_dates=["valid_time"])
            df["product_type"] = product
            df["requested_lon"] = requested_lon
            frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(
        columns={
            "valid_time": "time",
            "sozotaux": "tau_x_n_m2",
            "sometauy": "tau_y_n_m2",
            "latitude": "native_lat",
            "longitude": "native_lon",
        }
    )
    out["year"] = out["time"].dt.year
    out["month"] = out["time"].dt.month
    return out


def build_transect(longitudes: list[int], latitude: float, *, force: bool, dry_run: bool) -> pd.DataFrame:
    frames = []
    for lon in longitudes:
        path = _download_one(lon, latitude, force=force, dry_run=dry_run)
        if not dry_run:
            frames.append(_read_zip_csv(path, lon))

    if dry_run:
        return pd.DataFrame()

    all_data = pd.concat(frames, ignore_index=True)
    all_data = all_data.sort_values(["requested_lon", "time", "product_type"])
    valid_counts = all_data.groupby("requested_lon")[["tau_x_n_m2", "tau_y_n_m2"]].apply(lambda s: s.notna().sum())
    print("valid monthly counts by requested lon:")
    print(valid_counts.to_string())
    return all_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch ORAS5 wind-stress time series along the equatorial Pacific.")
    parser.add_argument("--latitude", type=float, default=0.0)
    parser.add_argument("--lon-start", type=int, default=120)
    parser.add_argument("--lon-end", type=int, default=280)
    parser.add_argument("--lon-step", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    longitudes = list(range(args.lon_start, args.lon_end + 1, args.lon_step))
    transect = build_transect(longitudes, args.latitude, force=args.force, dry_run=args.dry_run)
    if args.dry_run:
        return 0

    OUT_INTERIM.mkdir(parents=True, exist_ok=True)
    out_path = OUT_INTERIM / "oras5_windstress_timeseries_equatorial_1980_202605.csv"
    transect.to_csv(out_path, index=False)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
