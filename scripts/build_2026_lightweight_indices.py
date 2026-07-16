#!/usr/bin/env python3
"""Build lightweight 2026 ENSO/FEP coupling diagnostics from OPeNDAP indices.

This script is intentionally index-based. It avoids large field downloads and
keeps the 2023/24 research outputs untouched while extending the same
observed/expected-response logic to the currently available 2026 data.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import time


ERSSTV5_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc"
GPCP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc"
NCEP_UWND_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface/uwnd.sig995.mon.mean.nc"
NCEP_SLP_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/Monthlies/surface/slp.mon.mean.nc"
OLR_ANOM_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_blended_olr-2.5deg/olr.day.anom.nc"

REFERENCE_START = 1982
REFERENCE_END = 2022
REGRESSION_START = 1982
REGRESSION_END = 2022
MIN_REGRESSION_YEARS = 12


@dataclass(frozen=True)
class Region:
    id: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


SST_REGIONS = {
    "nino34": Region("nino34", -5, 5, 190, 240),
    "nino3": Region("nino3", -5, 5, 210, 270),
    "fep": Region("fep", -5, 5, 270, 280),
    "nino12": Region("nino12", -10, 0, 270, 280),
    "western_pacific_warm_pool": Region("western_pacific_warm_pool", -10, 10, 120, 160),
    "maritime_continent": Region("maritime_continent", -10, 10, 95, 150),
    "tropical_indian_ocean": Region("tropical_indian_ocean", -20, 20, 40, 110),
    "tropical_north_atlantic": Region("tropical_north_atlantic", 0, 20, 300, 340),
}
ATM_REGIONS = {
    "cwp_160e_140w": Region("cwp_160e_140w", -5, 5, 160, 220),
    "central_pacific_180_140w": Region("central_pacific_180_140w", -5, 5, 180, 220),
    "eastern_pacific_140w_100w": Region("eastern_pacific_140w_100w", -5, 5, 220, 260),
    "tahiti_proxy": Region("tahiti_proxy", -25, -10, 200, 220),
    "darwin_proxy": Region("darwin_proxy", -20, -5, 120, 140),
}
PERIODS_2026 = {
    "JAN": ((2026, 1),),
    "FEB": ((2026, 2),),
    "MAR": ((2026, 3),),
    "APR": ((2026, 4),),
    "MAY": ((2026, 5),),
    "JFM": ((2026, 1), (2026, 2), (2026, 3)),
    "FMA": ((2026, 2), (2026, 3), (2026, 4)),
    "MAM": ((2026, 3), (2026, 4), (2026, 5)),
    "AM_to_date": ((2026, 4), (2026, 5)),
}


def _ym_key(year: int, month: int) -> int:
    return int(year) * 100 + int(month)


def _target_ym(end_year: int, end_month: int) -> int:
    return _ym_key(end_year, end_month)


def _weighted_region_mean(values, lats) -> float:
    import numpy as np

    arr = np.ma.filled(values, np.nan).astype(float)
    weights = np.cos(np.deg2rad(lats)).astype(float)
    valid_row = np.isfinite(arr).any(axis=1)
    if not valid_row.any():
        return math.nan
    row_mean = np.nanmean(arr, axis=1)
    return float(np.nansum(row_mean * weights) / np.nansum(weights[valid_row]))


def _region_indices(lat, lon, region: Region):
    import numpy as np

    lat_idx = np.where((lat >= region.lat_min) & (lat <= region.lat_max))[0]
    lon_idx = np.where((lon >= region.lon_min) & (lon <= region.lon_max))[0]
    if len(lat_idx) == 0 or len(lon_idx) == 0:
        raise ValueError(f"Empty selection for region {region.id}")
    return lat_idx, lon_idx


def _time_bounds(dates, start_year: int, start_month: int, end_year: int, end_month: int):
    start_key = _ym_key(start_year, start_month)
    end_key = _target_ym(end_year, end_month)
    start = next(i for i, date in enumerate(dates) if _ym_key(date.year, date.month) >= start_key)
    eligible = [i for i, date in enumerate(dates) if _ym_key(date.year, date.month) <= end_key]
    if not eligible:
        raise ValueError("No available data before requested end date.")
    return start, eligible[-1]


def _monthly_climatology(records: list[dict], value_key: str, start: int, end: int) -> dict[tuple[str, int], float]:
    by_month: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in records:
        if start <= int(row["year"]) <= end:
            value = float(row[value_key])
            if not math.isnan(value):
                by_month[(str(row.get("region", "")), int(row["month"]))].append(value)
    return {key: sum(values) / len(values) for key, values in by_month.items() if values}


def _add_anomalies(records: list[dict], value_key: str, out_key: str, start: int, end: int) -> list[dict]:
    clim = _monthly_climatology(records, value_key, start, end)
    output = []
    for row in records:
        month = int(row["month"])
        key = (str(row.get("region", "")), month)
        out = dict(row)
        out[out_key] = float(row[value_key]) - clim[key] if key in clim else math.nan
        output.append(out)
    return output


def _read_monthly_regions(
    url: str,
    variable: str,
    regions: dict[str, Region],
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    *,
    chunk_months: int = 120,
):
    import netCDF4
    import numpy as np

    dataset = netCDF4.Dataset(url)
    try:
        time_var = dataset.variables["time"]
        dates = netCDF4.num2date(time_var[:], units=time_var.units, calendar=getattr(time_var, "calendar", "standard"))
        lat = dataset.variables["lat"][:]
        lon = dataset.variables["lon"][:]
        start, end = _time_bounds(dates, start_year, start_month, end_year, end_month)
        records = []
        for region_id, region in regions.items():
            lat_idx, lon_idx = _region_indices(lat, lon, region)
            for chunk_start in range(start, end + 1, chunk_months):
                chunk_end = min(chunk_start + chunk_months - 1, end)
                for attempt in range(4):
                    try:
                        cube = dataset.variables[variable][
                            chunk_start : chunk_end + 1,
                            lat_idx[0] : lat_idx[-1] + 1,
                            lon_idx[0] : lon_idx[-1] + 1,
                        ]
                        break
                    except RuntimeError:
                        if attempt == 3:
                            raise
                        time.sleep(2 * (attempt + 1))
                cube = np.ma.filled(cube, np.nan)
                for offset, time_index in enumerate(range(chunk_start, chunk_end + 1)):
                    date = dates[time_index]
                    records.append(
                        {
                            "region": region_id,
                            "year": int(date.year),
                            "month": int(date.month),
                            "value": _weighted_region_mean(cube[offset], lat[lat_idx]),
                        }
                    )
        return records
    finally:
        dataset.close()


def _read_olr_daily_monthly(url: str, regions: dict[str, Region], start_year: int, start_month: int, end_year: int, end_month: int):
    import netCDF4
    import numpy as np

    dataset = netCDF4.Dataset(url)
    try:
        time_var = dataset.variables["time"]
        dates = netCDF4.num2date(time_var[:], units=time_var.units, calendar=getattr(time_var, "calendar", "standard"))
        lat = dataset.variables["lat"][:]
        lon = dataset.variables["lon"][:]
        start, end = _time_bounds(dates, start_year, start_month, end_year, end_month)
        monthly: dict[tuple[str, int, int], list[float]] = defaultdict(list)
        for region_id, region in regions.items():
            lat_idx, lon_idx = _region_indices(lat, lon, region)
            current = start
            while current <= end:
                year = dates[current].year
                block_end = current
                while block_end + 1 <= end and dates[block_end + 1].year == year:
                    block_end += 1
                for attempt in range(4):
                    try:
                        cube = dataset.variables["olr"][
                            current : block_end + 1,
                            lat_idx[0] : lat_idx[-1] + 1,
                            lon_idx[0] : lon_idx[-1] + 1,
                        ]
                        break
                    except RuntimeError:
                        if attempt == 3:
                            raise
                        time.sleep(2 * (attempt + 1))
                cube = np.ma.filled(cube, np.nan)
                for offset, time_index in enumerate(range(current, block_end + 1)):
                    date = dates[time_index]
                    monthly[(region_id, int(date.year), int(date.month))].append(
                        _weighted_region_mean(cube[offset], lat[lat_idx])
                    )
                current = block_end + 1
        return [
            {
                "region": region,
                "year": year,
                "month": month,
                "value": sum(values) / len(values),
                "anomaly": sum(values) / len(values),
            }
            for (region, year, month), values in sorted(monthly.items())
        ]
    finally:
        dataset.close()


def _metric_rows_from_region_records(records: list[dict], metric: str, unit: str, anomaly_kind: str, source: str, anomaly_key: str = "anomaly"):
    return [
        {
            "metric": metric,
            "region": row["region"],
            "year": row["year"],
            "month": row["month"],
            "value": row["value"],
            "anomaly": row[anomaly_key],
            "unit": unit,
            "anomaly_kind": anomaly_kind,
            "source": source,
        }
        for row in records
    ]


def _combine_ncep(u_records: list[dict], slp_records: list[dict]) -> list[dict]:
    rows = []
    u_anom = _add_anomalies(u_records, "value", "anomaly", REFERENCE_START, REFERENCE_END)
    rows.extend(_metric_rows_from_region_records(u_anom, "ncep_sig995_u", "m/s", "1982-2022 monthly climatology", "NCEP/NCAR"))

    slp_anom = _add_anomalies(slp_records, "value", "anomaly", REFERENCE_START, REFERENCE_END)
    by_key = {(row["region"], int(row["year"]), int(row["month"])): row for row in slp_anom}
    for key in sorted({(int(row["year"]), int(row["month"])) for row in slp_anom}):
        year, month = key
        tahiti = by_key.get(("tahiti_proxy", year, month))
        darwin = by_key.get(("darwin_proxy", year, month))
        if not tahiti or not darwin:
            continue
        rows.append(
            {
                "metric": "ncep_soi_like_slp",
                "region": "tahiti_minus_darwin",
                "year": year,
                "month": month,
                "value": float(tahiti["value"]) - float(darwin["value"]),
                "anomaly": float(tahiti["anomaly"]) - float(darwin["anomaly"]),
                "unit": "hPa",
                "anomaly_kind": "1982-2022 monthly climatology",
                "source": "NCEP/NCAR",
            }
        )
    return rows


def _period_year_values(rows: list[dict], metric: str, region: str, months: tuple[int, ...], value_key: str = "anomaly") -> dict[int, float]:
    by_key = {(int(row["year"]), int(row["month"])): float(row[value_key]) for row in rows if row["metric"] == metric and row["region"] == region}
    years = sorted({year for year, _ in by_key})
    output = {}
    for year in years:
        values = []
        for month in months:
            if (year, month) not in by_key:
                values = []
                break
            value = by_key[(year, month)]
            if math.isnan(value):
                values = []
                break
            values.append(value)
        if values:
            output[year] = sum(values) / len(values)
    return output


def _period_value_2026(rows: list[dict], metric: str, region: str, period_months: tuple[tuple[int, int], ...]) -> float | None:
    by_key = {(int(row["year"]), int(row["month"])): float(row["anomaly"]) for row in rows if row["metric"] == metric and row["region"] == region}
    values = []
    for year, month in period_months:
        if (year, month) not in by_key:
            return None
        value = by_key[(year, month)]
        if math.isnan(value):
            return None
        values.append(value)
    return sum(values) / len(values)


def _linear_fit(x: list[float], y: list[float]) -> tuple[float, float, float, int]:
    import numpy as np

    arr_x = np.array(x, dtype=float)
    arr_y = np.array(y, dtype=float)
    slope, intercept = np.polyfit(arr_x, arr_y, 1)
    r = float(np.corrcoef(arr_x, arr_y)[0, 1]) if len(arr_x) > 1 else math.nan
    return float(slope), float(intercept), r, len(arr_x)


def _build_expected_rows(rows: list[dict]) -> list[dict]:
    outputs = []
    predictor_metric = "ersstv5_sst"
    predictor_region = "nino3"
    response_pairs = [
        ("ncep_sig995_u", "cwp_160e_140w"),
        ("ncep_soi_like_slp", "tahiti_minus_darwin"),
        ("gpcp_precip", "central_pacific_180_140w"),
        ("olr_anomaly", "central_pacific_180_140w"),
    ]
    for period, target_months in PERIODS_2026.items():
        months = tuple(month for _, month in target_months)
        pred_hist = _period_year_values(rows, predictor_metric, predictor_region, months)
        pred_2026 = _period_value_2026(rows, predictor_metric, predictor_region, target_months)
        if pred_2026 is None:
            continue
        for metric, region in response_pairs:
            resp_hist = _period_year_values(rows, metric, region, months)
            common_years = [year for year in sorted(pred_hist) if REGRESSION_START <= year <= REGRESSION_END and year in resp_hist]
            if len(common_years) < MIN_REGRESSION_YEARS:
                continue
            observed = _period_value_2026(rows, metric, region, target_months)
            if observed is None:
                continue
            slope, intercept, r, n = _linear_fit([pred_hist[year] for year in common_years], [resp_hist[year] for year in common_years])
            expected = slope * pred_2026 + intercept
            outputs.append(
                {
                    "period": period,
                    "predictor": f"{predictor_metric}:{predictor_region}",
                    "response_metric": metric,
                    "response_region": region,
                    "nino3_2026": pred_2026,
                    "observed_2026": observed,
                    "expected_from_regression": expected,
                    "residual_observed_minus_expected": observed - expected,
                    "observed_over_expected": observed / expected if expected else "",
                    "slope": slope,
                    "intercept": intercept,
                    "r": r,
                    "regression_n_years": n,
                    "regression_years": f"{min(common_years)}-{max(common_years)}",
                }
            )
    return outputs


def _build_fep_rows(rows: list[dict]) -> list[dict]:
    outputs = []
    for period, target_months in PERIODS_2026.items():
        months = tuple(month for _, month in target_months)
        nino_hist = _period_year_values(rows, "ersstv5_sst", "nino34", months)
        fep_hist = _period_year_values(rows, "ersstv5_sst", "fep", months)
        common_years = [year for year in sorted(nino_hist) if REGRESSION_START <= year <= REGRESSION_END and year in fep_hist]
        if len(common_years) < MIN_REGRESSION_YEARS:
            continue
        nino_2026 = _period_value_2026(rows, "ersstv5_sst", "nino34", target_months)
        fep_2026 = _period_value_2026(rows, "ersstv5_sst", "fep", target_months)
        if nino_2026 is None or fep_2026 is None:
            continue
        slope, intercept, r, n = _linear_fit([nino_hist[year] for year in common_years], [fep_hist[year] for year in common_years])
        expected = slope * nino_2026 + intercept
        outputs.append(
            {
                "period": period,
                "nino34_2026": nino_2026,
                "fep_observed_2026": fep_2026,
                "fep_expected_from_nino34": expected,
                "fep_residual": fep_2026 - expected,
                "slope": slope,
                "intercept": intercept,
                "r": r,
                "regression_n_years": n,
                "regression_years": f"{min(common_years)}-{max(common_years)}",
                "note": "FEP residual follows the GRL paper logic: FEP minus the part linearly associated with Nino-3.4.",
            }
        )
    return outputs


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build lightweight 2026 ENSO/FEP coupling diagnostics.")
    parser.add_argument("--start-year", type=int, default=1982)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--end-month", type=int, default=5)
    parser.add_argument("--monthly-output", type=Path, default=Path("data/interim/research_2026/current_2026_monthly_indices.csv"))
    parser.add_argument("--expected-output", type=Path, default=Path("data/derived/research_2026/current_2026_regression_expected_response.csv"))
    parser.add_argument("--fep-output", type=Path, default=Path("data/derived/research_2026/current_2026_fep_residual.csv"))
    parser.add_argument("--skip-olr", action="store_true")
    args = parser.parse_args()

    rows = []

    sst = _read_monthly_regions(ERSSTV5_URL, "sst", SST_REGIONS, args.start_year, 1, args.end_year, args.end_month)
    sst = _add_anomalies(sst, "value", "anomaly", REFERENCE_START, REFERENCE_END)
    rows.extend(_metric_rows_from_region_records(sst, "ersstv5_sst", "deg C", "1982-2022 monthly climatology", "NOAA ERSSTv5"))

    gpcp_regions = {
        key: ATM_REGIONS[key]
        for key in ("central_pacific_180_140w", "eastern_pacific_140w_100w", "cwp_160e_140w")
    }
    gpcp = _read_monthly_regions(GPCP_URL, "precip", gpcp_regions, args.start_year, 1, args.end_year, args.end_month)
    gpcp = _add_anomalies(gpcp, "value", "anomaly", REFERENCE_START, REFERENCE_END)
    rows.extend(_metric_rows_from_region_records(gpcp, "gpcp_precip", "mm/day", "1982-2022 monthly climatology", "GPCP"))

    u = _read_monthly_regions(NCEP_UWND_URL, "uwnd", {"cwp_160e_140w": ATM_REGIONS["cwp_160e_140w"]}, args.start_year, 1, args.end_year, args.end_month)
    slp_regions = {key: ATM_REGIONS[key] for key in ("tahiti_proxy", "darwin_proxy")}
    slp = _read_monthly_regions(NCEP_SLP_URL, "slp", slp_regions, args.start_year, 1, args.end_year, args.end_month)
    rows.extend(_combine_ncep(u, slp))

    if not args.skip_olr:
        olr_regions = {
            key: ATM_REGIONS[key]
            for key in ("central_pacific_180_140w", "eastern_pacific_140w_100w", "cwp_160e_140w")
        }
        olr = _read_olr_daily_monthly(OLR_ANOM_URL, olr_regions, 1997, 1, args.end_year, args.end_month)
        rows.extend(_metric_rows_from_region_records(olr, "olr_anomaly", "W/m2", "CPC daily anomaly averaged to month", "CPC blended OLR"))

    _write_csv(args.monthly_output, rows)
    _write_csv(args.expected_output, _build_expected_rows(rows))
    _write_csv(args.fep_output, _build_fep_rows(rows))
    print(args.monthly_output)
    print(args.expected_output)
    print(args.fep_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
