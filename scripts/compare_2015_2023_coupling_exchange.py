#!/usr/bin/env python3
"""Compare the development-year air-sea coupling of 2015 and 2023.

ERA5 surface fluxes are stored with downward-positive signs.  Every public
diagnostic from this module converts them to ocean-to-atmosphere heat loss,
positive upward.  OISST, ERA5, and GPCP anomalies use calendar-month linear
expectations fitted over 1982-2014.  CPC OLR retains its published anomaly.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
BASELINE = (1982, 2014)
EVENT_YEARS = (2015, 2023)
SEASON_MONTHS = {
    "MAM": (3, 4, 5),
    "MJJ": (5, 6, 7),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
}
ARRIVAL_VALUES = {
    2015: {"transport_140w_zj": 8.49, "east_ohc_gain_zj": 8.60},
    2023: {"transport_140w_zj": 9.90, "east_ohc_gain_zj": 11.12},
}
ERA5_DIR = Path("data/raw/era5/coupling_monthly_1deg")
ATMOSPHERE_TABLE = Path(
    "data/derived/research_2026/enso_full_year_coupling_monthly_1982_2024.csv"
)
OLR_TABLE = Path("data/interim/raw_validation/olr_monthly.csv")
DERIVED_DIR = Path("data/derived/research_2026")
MONTHLY_CSV_NAME = "enso_2015_2023_coupling_exchange_monthly.csv"
SEASONAL_CSV_NAME = "enso_2015_2023_coupling_exchange_seasonal.csv"
AUDIT_JSON_NAME = "enso_2015_2023_coupling_exchange_audit.json"

MONTHLY_OUTPUT_COLUMNS = (
    "date",
    "year",
    "month",
    "sst_east_raw_c",
    "sst_east_anom_c",
    "latent_loss_anom_wm2",
    "sensible_loss_anom_wm2",
    "turbulent_loss_anom_wm2",
    "shortwave_loss_anom_wm2",
    "longwave_loss_anom_wm2",
    "net_ocean_loss_anom_wm2",
    "minus_olr_ep_wm2",
    "minus_olr_cp_wm2",
    "precip_east_anom_mmday",
    "precip_central_anom_mmday",
    "tau_cwp_anom_nm2",
)
SEASONAL_METRICS = tuple(column for column in MONTHLY_OUTPUT_COLUMNS if column not in {"date", "year", "month"})


def same_month_linear_anomaly(
    frame: pd.DataFrame,
    value_column: str,
    baseline: tuple[int, int] = BASELINE,
) -> pd.Series:
    """Remove a calendar-month linear expectation while preserving row order."""

    required = {"year", "month", value_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns for anomaly calculation: {sorted(missing)}")

    output = pd.Series(np.nan, index=frame.index, dtype=float, name=f"{value_column}_anom")
    for month, group in frame.groupby("month", sort=False):
        baseline_rows = group.loc[group.year.between(*baseline), ["year", value_column]].dropna()
        if len(baseline_rows) < 3:
            raise ValueError(f"Month {month} has fewer than three baseline values")
        slope, intercept = np.polyfit(
            baseline_rows.year.to_numpy(dtype=float),
            baseline_rows[value_column].to_numpy(dtype=float),
            1,
        )
        expected = intercept + slope * group.year.to_numpy(dtype=float)
        output.loc[group.index] = group[value_column].to_numpy(dtype=float) - expected
    return output


def weighted_box_mean(
    field: xr.DataArray,
    lat0: float,
    lat1: float,
    lon0: float,
    lon1: float,
) -> xr.DataArray:
    """Return a cosine-latitude-weighted mean from a 0-360 longitude field."""

    rename = {}
    if "latitude" in field.coords:
        rename["latitude"] = "lat"
    if "longitude" in field.coords:
        rename["longitude"] = "lon"
    normalized = field.rename(rename)
    if "lat" not in normalized.coords or "lon" not in normalized.coords:
        raise ValueError("Field requires latitude and longitude coordinates")
    normalized = normalized.assign_coords(lon=normalized.lon % 360.0).sortby("lon").sortby("lat")
    selected = normalized.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if selected.sizes.get("lat", 0) == 0 or selected.sizes.get("lon", 0) == 0:
        raise ValueError(f"Empty box lat={lat0}:{lat1}, lon={lon0}:{lon1}")
    weights = np.cos(np.deg2rad(selected.lat))
    return selected.weighted(weights).mean(("lat", "lon"), skipna=True)


def to_upward_loss(
    latent_down: np.ndarray,
    sensible_down: np.ndarray,
    shortwave_down: np.ndarray,
    longwave_down: np.ndarray,
) -> dict[str, np.ndarray]:
    """Convert ERA5 downward-positive fluxes to positive ocean heat loss."""

    latent = np.asarray(latent_down, dtype=float)
    sensible = np.asarray(sensible_down, dtype=float)
    shortwave = np.asarray(shortwave_down, dtype=float)
    longwave = np.asarray(longwave_down, dtype=float)
    latent_loss = -latent
    sensible_loss = -sensible
    return {
        "latent_loss": latent_loss,
        "sensible_loss": sensible_loss,
        "turbulent_loss": latent_loss + sensible_loss,
        "shortwave_loss": -shortwave,
        "longwave_loss": -longwave,
        "net_ocean_loss": -(shortwave + longwave + latent + sensible),
    }


def audited_arrival_table() -> pd.DataFrame:
    """Return current-PPT arrival values from the mass-closed OHC analysis."""

    return pd.DataFrame(
        [
            {"year": year, **ARRIVAL_VALUES[year]}
            for year in EVENT_YEARS
        ]
    )


def discover_input_root() -> Path:
    """Find the data-bearing project root when execution occurs in a worktree."""

    candidates = []
    if os.environ.get("MARYLAND_INPUT_ROOT"):
        candidates.append(Path(os.environ["MARYLAND_INPUT_ROOT"]).expanduser())
    candidates.append(ROOT)
    if ROOT.parent.name == ".worktrees":
        candidates.append(ROOT.parents[1])
    for candidate in candidates:
        if (candidate / ERA5_DIR).exists() and (candidate / ATMOSPHERE_TABLE).exists():
            return candidate.resolve()
    rendered = ", ".join(str(item) for item in candidates)
    raise FileNotFoundError(f"Could not locate required local inputs under: {rendered}")


def _load_era5_indices(input_root: Path) -> pd.DataFrame:
    rows = []
    variable_names = [
        "avg_iews",
        "avg_snswrf",
        "avg_snlwrf",
        "avg_slhtf",
        "avg_ishf",
    ]
    for month in range(1, 13):
        pieces = []
        for part in ("part01", "part02"):
            path = (
                input_root
                / ERA5_DIR
                / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            )
            with xr.open_dataset(path, engine="netcdf4", chunks=None) as dataset:
                selected = dataset[variable_names].rename(
                    {"valid_time": "time", "latitude": "lat", "longitude": "lon"}
                )
                selected = selected.assign_coords(lon=selected.lon % 360.0).sortby("lon").sortby("lat")
                pieces.append(selected.load())
        fields = xr.concat(pieces, dim="lon").sortby("lon")
        _, unique = np.unique(fields.lon.values, return_index=True)
        fields = fields.isel(lon=np.sort(unique))
        times = pd.DatetimeIndex(pd.to_datetime(fields.time.values))

        latent = weighted_box_mean(fields.avg_slhtf, -10.0, 5.0, 220.0, 280.0).values
        sensible = weighted_box_mean(fields.avg_ishf, -10.0, 5.0, 220.0, 280.0).values
        shortwave = weighted_box_mean(fields.avg_snswrf, -10.0, 5.0, 220.0, 280.0).values
        longwave = weighted_box_mean(fields.avg_snlwrf, -10.0, 5.0, 220.0, 280.0).values
        losses = to_upward_loss(latent, sensible, shortwave, longwave)
        tau = weighted_box_mean(fields.avg_iews, -5.0, 5.0, 160.0, 220.0).values
        current = pd.DataFrame(
            {
                "year": times.year,
                "month": times.month,
                "latent_loss_raw_wm2": losses["latent_loss"],
                "sensible_loss_raw_wm2": losses["sensible_loss"],
                "turbulent_loss_raw_wm2": losses["turbulent_loss"],
                "shortwave_loss_raw_wm2": losses["shortwave_loss"],
                "longwave_loss_raw_wm2": losses["longwave_loss"],
                "net_ocean_loss_raw_wm2": losses["net_ocean_loss"],
                "tau_cwp_raw_nm2": tau,
            }
        )
        rows.append(current)
    output = pd.concat(rows, ignore_index=True).sort_values(["year", "month"]).reset_index(drop=True)
    if output.duplicated(["year", "month"]).any():
        raise ValueError("ERA5 index table contains duplicate months")
    return output


def _load_sst_precip_indices(input_root: Path) -> pd.DataFrame:
    path = input_root / ATMOSPHERE_TABLE
    source = pd.read_csv(path)
    columns = [
        "year",
        "month",
        "sst_east_raw_c",
        "precip_east_raw_mmday",
        "precip_central_raw_mmday",
    ]
    output = source[columns].copy()
    if output.duplicated(["year", "month"]).any():
        raise ValueError("OISST/GPCP source table contains duplicate months")
    return output


def _load_olr_indices(input_root: Path) -> pd.DataFrame:
    source = pd.read_csv(input_root / OLR_TABLE)
    regions = {
        "eastern_pacific_140w_100w": "olr_ep_native_anom_wm2",
        "central_pacific_180_140w": "olr_cp_native_anom_wm2",
    }
    pieces = []
    for region, name in regions.items():
        selected = source.loc[source.region.eq(region), ["year", "month", "olr_anomaly"]].copy()
        selected = selected.rename(columns={"olr_anomaly": name})
        pieces.append(selected)
    return pieces[0].merge(pieces[1], on=["year", "month"], validate="one_to_one")


def build_monthly_table(input_root: Path | None = None) -> pd.DataFrame:
    """Build monthly 2015/2023 diagnostics from complete historical inputs."""

    data_root = discover_input_root() if input_root is None else Path(input_root)
    full = _load_era5_indices(data_root)
    full = full.merge(_load_sst_precip_indices(data_root), on=["year", "month"], validate="one_to_one")
    full = full.merge(_load_olr_indices(data_root), on=["year", "month"], how="left", validate="one_to_one")

    anomaly_columns = {
        "sst_east_raw_c": "sst_east_anom_c",
        "precip_east_raw_mmday": "precip_east_anom_mmday",
        "precip_central_raw_mmday": "precip_central_anom_mmday",
        "latent_loss_raw_wm2": "latent_loss_anom_wm2",
        "sensible_loss_raw_wm2": "sensible_loss_anom_wm2",
        "turbulent_loss_raw_wm2": "turbulent_loss_anom_wm2",
        "shortwave_loss_raw_wm2": "shortwave_loss_anom_wm2",
        "longwave_loss_raw_wm2": "longwave_loss_anom_wm2",
        "net_ocean_loss_raw_wm2": "net_ocean_loss_anom_wm2",
        "tau_cwp_raw_nm2": "tau_cwp_anom_nm2",
    }
    for raw_name, anomaly_name in anomaly_columns.items():
        full[anomaly_name] = same_month_linear_anomaly(full, raw_name)
    full["minus_olr_ep_wm2"] = -full.olr_ep_native_anom_wm2
    full["minus_olr_cp_wm2"] = -full.olr_cp_native_anom_wm2
    full["date"] = pd.to_datetime(dict(year=full.year, month=full.month, day=1))

    events = full.loc[full.year.isin(EVENT_YEARS), MONTHLY_OUTPUT_COLUMNS].copy()
    events = events.sort_values(["year", "month"]).reset_index(drop=True)
    counts = events.groupby("year")["month"].nunique().to_dict()
    if counts != {2015: 12, 2023: 12}:
        raise ValueError(f"Incomplete event-month table: {counts}")
    return events


def build_seasonal_table(monthly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate overlapping development-season windows in physical units."""

    rows = []
    for season, months in SEASON_MONTHS.items():
        event_rows = []
        for year in EVENT_YEARS:
            selected = monthly.loc[monthly.year.eq(year) & monthly.month.isin(months)]
            if tuple(selected.month) != months:
                raise ValueError(f"{year} {season} has months {tuple(selected.month)}, expected {months}")
            row = {"season": season, "event": str(year), "year": year}
            row.update({metric: float(selected[metric].mean()) for metric in SEASONAL_METRICS})
            event_rows.append(row)
            rows.append(row)
        difference = {"season": season, "event": "2015_minus_2023", "year": np.nan}
        difference.update(
            {
                metric: event_rows[0][metric] - event_rows[1][metric]
                for metric in SEASONAL_METRICS
            }
        )
        rows.append(difference)
    return pd.DataFrame(rows)


def validate_monthly_table(monthly: pd.DataFrame, seasonal: pd.DataFrame) -> dict[str, object]:
    target = [column for column in MONTHLY_OUTPUT_COLUMNS if column not in {"date", "year", "month"}]
    mjj = seasonal.loc[
        seasonal.season.eq("MJJ") & seasonal.event.isin(["2015", "2023"])
    ].set_index("event")
    return {
        "baseline": "1982-2014 calendar-month linear expectation; CPC OLR native anomaly",
        "flux_sign": "positive means ocean-to-atmosphere heat loss",
        "month_counts": {
            str(year): int(count)
            for year, count in monthly.groupby("year")["month"].nunique().items()
        },
        "missing_target_values": int(monthly[target].isna().sum().sum()),
        "arrival_values": audited_arrival_table().to_dict(orient="records"),
        "mjj_key_values": {
            event: {
                metric: float(mjj.loc[event, metric])
                for metric in (
                    "sst_east_raw_c",
                    "sst_east_anom_c",
                    "latent_loss_anom_wm2",
                    "net_ocean_loss_anom_wm2",
                    "minus_olr_cp_wm2",
                    "precip_central_anom_mmday",
                    "tau_cwp_anom_nm2",
                )
            }
            for event in ("2015", "2023")
        },
    }


def write_tables(output_root: Path | None = None, input_root: Path | None = None) -> tuple[Path, Path, Path]:
    root = ROOT if output_root is None else Path(output_root)
    monthly = build_monthly_table(input_root=input_root)
    seasonal = build_seasonal_table(monthly)
    audit = validate_monthly_table(monthly, seasonal)
    target_dir = root / DERIVED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    monthly_path = target_dir / MONTHLY_CSV_NAME
    seasonal_path = target_dir / SEASONAL_CSV_NAME
    audit_path = target_dir / AUDIT_JSON_NAME
    monthly.to_csv(monthly_path, index=False, float_format="%.8g")
    seasonal.to_csv(seasonal_path, index=False, float_format="%.8g")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return monthly_path, seasonal_path, audit_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables-only", action="store_true")
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = write_tables(output_root=args.output_root, input_root=args.input_root)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
