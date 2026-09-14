#!/usr/bin/env python3
"""Verify the early-2023 surface/upper-ocean anomaly sign mismatch.

The check is deliberately independent of the plotting code.  It recomputes
temperature anomalies before vertical integration, compares the resulting
0--300 m OHC anomalies with the archived OHC product, harmonizes the SODA
baseline with OISST (1982--2024), and diagnoses 0--80 m versus 80--300 m
contributions on the same valid 0--300 m ocean footprint.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
TEMP_FILE = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
OHC_FILE = (
    ROOT
    / "data/interim/research_2026/soda3_ohc"
    / "soda3_ohc_0_100_0_300_1980_2024.nc"
)
SSTA_TEMPLATE = (
    ROOT
    / "data/derived/research_2026"
    / "{event}_jan_jun_oisst_ssta_era5_850_wind_anomalies_1982_2024.nc"
)
OUT_DIR = ROOT / "outputs/research_2026/soda3_2023_ssta_ohc_verification"

EVENTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
RHO0 = 1025.0
CP0 = 3990.0
REGIONS = {
    "nino3_150W_90W": (-5.0, 5.0, 210.0, 270.0),
    "east_140W_80W": (-5.0, 5.0, 220.0, 280.0),
    "fep_90W_80W": (-5.0, 5.0, 270.0, 280.0),
}


def layer_overlap(depth: np.ndarray, top_limit: float, bottom_limit: float) -> np.ndarray:
    """Layer thickness overlapping ``top_limit``--``bottom_limit``."""
    centers = np.asarray(depth, dtype=float)
    if centers.ndim != 1 or centers.size < 2 or not np.all(np.diff(centers) > 0):
        raise ValueError("Depth centers must be a strictly increasing 1-D coordinate")
    edges = np.empty(centers.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (centers[:-1] + centers[1:])
    edges[-1] = centers[-1] + 0.5 * (centers[-1] - centers[-2])
    return np.maximum(
        0.0,
        np.minimum(edges[1:], bottom_limit) - np.maximum(edges[:-1], top_limit),
    )


def detrended_same_month(
    values: np.ndarray,
    times: pd.DatetimeIndex,
    baseline_start: int,
    baseline_end: int,
) -> np.ndarray:
    """Return same-month residuals from a baseline mean and linear trend."""
    data = np.asarray(values, dtype=np.float64)
    result = np.full(data.shape, np.nan, dtype=np.float32)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    reshape = (-1,) + (1,) * (data.ndim - 1)
    for month in MONTHS:
        target = months == month
        baseline = target & (years >= baseline_start) & (years <= baseline_end)
        if int(baseline.sum()) != baseline_end - baseline_start + 1:
            raise ValueError(
                f"Unexpected {month=} sample count for {baseline_start}-{baseline_end}: "
                f"{int(baseline.sum())}"
            )
        base = data[baseline]
        x = years[baseline]
        center_year = float(x.mean())
        xc = (x - center_year).reshape(reshape)
        finite = np.isfinite(base)
        count = finite.sum(axis=0)
        mean = np.divide(
            np.nansum(base, axis=0),
            count,
            out=np.full(data.shape[1:], np.nan, dtype=float),
            where=count > 0,
        )
        numerator = np.nansum(xc * (base - mean), axis=0)
        denominator = np.nansum(finite * xc**2, axis=0)
        slope = np.divide(
            numerator,
            denominator,
            out=np.full(data.shape[1:], np.nan, dtype=float),
            where=denominator > 0,
        )
        target_year = (years[target] - center_year).reshape((-1,) + (1,) * (data.ndim - 1))
        result[target] = (data[target] - mean - slope * target_year).astype(np.float32)
    return result


def integrate_temperature_anomaly(
    anomaly: np.ndarray,
    depth: np.ndarray,
    top_limit: float,
    bottom_limit: float,
) -> np.ndarray:
    weights = layer_overlap(depth, top_limit, bottom_limit)
    used = weights > 0
    finite = np.all(np.isfinite(anomaly[:, used]), axis=1)
    integral = np.nansum(
        anomaly[:, used] * weights[used][None, :, None, None],
        axis=1,
    )
    integral[~finite] = np.nan
    return (RHO0 * CP0 * integral).astype(np.float32)


def region_mask(da: xr.DataArray, bounds: tuple[float, float, float, float]) -> xr.DataArray:
    lat0, lat1, lon0, lon1 = bounds
    return (da.lat >= lat0) & (da.lat <= lat1) & (da.lon >= lon0) & (da.lon <= lon1)


def weighted_mean(
    da: xr.DataArray,
    bounds: tuple[float, float, float, float],
    valid_mask: xr.DataArray | None = None,
) -> xr.DataArray:
    mask = region_mask(da, bounds)
    if valid_mask is not None:
        mask = mask & valid_mask
    selected = da.where(mask)
    weights = np.cos(np.deg2rad(da.lat)).broadcast_like(da)
    return selected.weighted(weights.where(mask, 0.0)).mean(("lat", "lon"), skipna=True)


def load_ssta(event: int) -> xr.DataArray:
    path = Path(str(SSTA_TEMPLATE).format(event=event))
    with xr.open_dataset(path) as ds:
        if ds.attrs.get("oisst_baseline") != "1982-2024":
            raise ValueError(f"Unexpected OISST baseline in {path.name}")
        da = ds.ssta.rename({"sst_lat": "lat", "sst_lon": "lon"}).load()
    da = da.assign_coords(lon=np.mod(da.lon, 360.0)).sortby("lon")
    return da


def event_month_indices(times: pd.DatetimeIndex, event: int) -> np.ndarray:
    index = np.flatnonzero((times.year == event) & np.isin(times.month, MONTHS))
    if index.size != len(MONTHS):
        raise ValueError(f"Expected six records for {event}, got {index.size}")
    return index


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    """Render a compact Markdown table without an optional tabulate dependency."""
    formatted = frame.copy()
    for column in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[column]):
            formatted[column] = formatted[column].map(lambda value: f"{value:.3f}")
        else:
            formatted[column] = formatted[column].astype(str)
    headers = [str(column) for column in formatted.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in formatted.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with xr.open_dataset(TEMP_FILE) as temp_ds:
        if temp_ds.temp.dims != ("time", "depth", "lat", "lon"):
            raise ValueError(f"Unexpected temperature dimensions: {temp_ds.temp.dims}")
        temperature = temp_ds.temp.load()
    times = pd.DatetimeIndex(temperature.time.values)
    depth = temperature.depth.values.astype(float)

    # Independent check: anomaly temperature first, then integrate to 300 m.
    temp_anom_1980 = detrended_same_month(temperature.values, times, 1980, 2024)
    independent_ohc300_1980 = integrate_temperature_anomaly(temp_anom_1980, depth, 0.0, 300.0)
    independent_da = xr.DataArray(
        independent_ohc300_1980,
        dims=("time", "lat", "lon"),
        coords={"time": temperature.time, "lat": temperature.lat, "lon": temperature.lon},
    )

    with xr.open_dataset(OHC_FILE) as ohc_ds:
        archived = ohc_ds.ohc_300m_anomaly_detrended.sel(
            time=temperature.time,
            lat=temperature.lat,
            lon=temperature.lon,
        ).load()
        archived_ohc100 = ohc_ds.ohc_100m_anomaly_detrended.sel(
            time=temperature.time,
            lat=temperature.lat,
            lon=temperature.lon,
        ).load()
        archived_definition = str(ohc_ds.attrs.get("anomaly_definition", ""))

    common = np.isfinite(independent_da.values) & np.isfinite(archived.values)
    stable_ocean = np.isfinite(temperature.values).all(axis=(0, 1))
    stable_common = common & stable_ocean[None, :, :]
    comparison_rows = []
    for footprint, check_mask in (
        ("all contemporaneously valid cells", common),
        ("time-invariant complete 0-300 m columns", stable_common),
    ):
        independent_values = independent_da.values[check_mask]
        archived_values = archived.values[check_mask]
        difference = independent_values - archived_values
        comparison_rows.append(
            {
                "comparison": "temperature-anomaly-first versus archived OHC-anomaly-after-integration",
                "footprint": footprint,
                "n_common": int(check_mask.sum()),
                "rmse_gj_m2": float(np.sqrt(np.mean(difference**2)) / 1.0e9),
                "mean_bias_gj_m2": float(np.mean(difference) / 1.0e9),
                "max_abs_gj_m2": float(np.max(np.abs(difference)) / 1.0e9),
                "correlation": float(np.corrcoef(independent_values, archived_values)[0, 1]),
                "archived_definition": archived_definition,
            }
        )
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(OUT_DIR / "independent_ohc_recomputation_check.csv", index=False)

    # Harmonize SODA with the OISST 1982--2024 baseline and split the column.
    temp_anom_common = detrended_same_month(temperature.values, times, 1982, 2024)
    ohc_0_80 = integrate_temperature_anomaly(temp_anom_common, depth, 0.0, 80.0)
    ohc_80_300 = integrate_temperature_anomaly(temp_anom_common, depth, 80.0, 300.0)
    ohc_0_300 = integrate_temperature_anomaly(temp_anom_common, depth, 0.0, 300.0)
    closure = np.nanmax(np.abs((ohc_0_80 + ohc_80_300) - ohc_0_300)) / 1.0e9

    arrays = {
        "soda_5m_ta_c": xr.DataArray(
            temp_anom_common[:, 0],
            dims=("time", "lat", "lon"),
            coords={"time": temperature.time, "lat": temperature.lat, "lon": temperature.lon},
        ),
        "ohc_0_80_gj_m2": xr.DataArray(
            ohc_0_80 / 1.0e9,
            dims=("time", "lat", "lon"),
            coords={"time": temperature.time, "lat": temperature.lat, "lon": temperature.lon},
        ),
        "ohc_80_300_gj_m2": xr.DataArray(
            ohc_80_300 / 1.0e9,
            dims=("time", "lat", "lon"),
            coords={"time": temperature.time, "lat": temperature.lat, "lon": temperature.lon},
        ),
        "ohc_0_300_common_gj_m2": xr.DataArray(
            ohc_0_300 / 1.0e9,
            dims=("time", "lat", "lon"),
            coords={"time": temperature.time, "lat": temperature.lat, "lon": temperature.lon},
        ),
        "ohc_0_100_original_gj_m2": archived_ohc100 / 1.0e9,
        "ohc_0_300_original_gj_m2": archived / 1.0e9,
    }
    stable_ocean_da = xr.DataArray(
        stable_ocean,
        dims=("lat", "lon"),
        coords={"lat": temperature.lat, "lon": temperature.lon},
    )

    rows: list[dict[str, object]] = []
    mismatch_rows: list[dict[str, object]] = []
    for event in EVENTS:
        time_index = event_month_indices(times, event)
        ssta = load_ssta(event)
        for region_name, bounds in REGIONS.items():
            for month_offset, source_index in enumerate(time_index):
                month = MONTHS[month_offset]
                ohc300 = arrays["ohc_0_300_common_gj_m2"].isel(time=source_index)
                valid_ohc = np.isfinite(ohc300) & stable_ocean_da
                ssta_month = ssta.isel(time=month_offset)
                ssta_on_soda = ssta_month.interp(
                    lat=ohc300.lat,
                    lon=ohc300.lon,
                    method="linear",
                )
                native_ssta = weighted_mean(ssta_month, bounds)
                matched_ssta = weighted_mean(ssta_on_soda, bounds, valid_mask=valid_ohc)
                record: dict[str, object] = {
                    "event": event,
                    "month": month,
                    "region": region_name,
                    "oisst_ssta_native_c": float(native_ssta),
                    "oisst_ssta_matched_ohc_footprint_c": float(matched_ssta),
                }
                for name, da in arrays.items():
                    record[name] = float(
                        weighted_mean(da.isel(time=source_index), bounds, valid_mask=valid_ohc)
                    )
                record["surface_positive_common_ohc_negative"] = bool(
                    record["oisst_ssta_matched_ohc_footprint_c"] > 0
                    and record["ohc_0_300_common_gj_m2"] < 0
                )
                rows.append(record)

                mask = region_mask(ohc300, bounds) & valid_ohc & np.isfinite(ssta_on_soda)
                weights = np.cos(np.deg2rad(ohc300.lat)).broadcast_like(ohc300).where(mask, 0.0)
                denominator = float(weights.sum())
                mismatch = mask & (ssta_on_soda > 0.0) & (ohc300 < 0.0)
                ssta_positive = mask & (ssta_on_soda > 0.0)
                ohc_negative = mask & (ohc300 < 0.0)
                mismatch_rows.append(
                    {
                        "event": event,
                        "month": month,
                        "region": region_name,
                        "valid_weight_sum": denominator,
                        "area_fraction_ssta_positive_ohc_negative": (
                            float(weights.where(mismatch, 0.0).sum()) / denominator
                            if denominator > 0
                            else np.nan
                        ),
                        "area_fraction_ssta_positive": (
                            float(weights.where(ssta_positive, 0.0).sum()) / denominator
                            if denominator > 0
                            else np.nan
                        ),
                        "area_fraction_ohc_negative": (
                            float(weights.where(ohc_negative, 0.0).sum()) / denominator
                            if denominator > 0
                            else np.nan
                        ),
                    }
                )

    monthly = pd.DataFrame(rows)
    mismatch = pd.DataFrame(mismatch_rows)
    monthly.to_csv(OUT_DIR / "event_month_region_surface_ohc_check.csv", index=False)
    mismatch.to_csv(OUT_DIR / "event_month_region_spatial_mismatch_fraction.csv", index=False)

    focus = monthly.loc[
        (monthly.event == 2023) & (monthly.region.isin(["east_140W_80W", "fep_90W_80W"]))
    ].copy()
    focus_columns = [
        "month",
        "region",
        "oisst_ssta_matched_ohc_footprint_c",
        "soda_5m_ta_c",
        "ohc_0_80_gj_m2",
        "ohc_80_300_gj_m2",
        "ohc_0_300_common_gj_m2",
        "ohc_0_300_original_gj_m2",
        "surface_positive_common_ohc_negative",
    ]
    focus = focus[focus_columns]
    focus.to_csv(OUT_DIR / "focus_2023_east_fep_vertical_compensation.csv", index=False)

    stable_check = comparison.loc[
        comparison.footprint == "time-invariant complete 0-300 m columns"
    ].iloc[0]
    report_lines = [
        "# 2023 SSTA--OHC vertical mismatch verification",
        "",
        f"- Independent 0--300 m recomputation RMSE on stable full columns: {stable_check.rmse_gj_m2:.6g} GJ m-2.",
        f"- Independent recomputation maximum absolute difference on stable full columns: {stable_check.max_abs_gj_m2:.6g} GJ m-2.",
        f"- Independent recomputation correlation on stable full columns: {stable_check.correlation:.12f}.",
        f"- 0--80 m plus 80--300 m closure maximum error: {closure:.6g} GJ m-2.",
        "- OISST and harmonized SODA anomalies use the same 1982--2024 calendar-month linear baseline.",
        "- Matched-footprint SSTA is interpolated to the SODA grid and restricted to cells with a complete 0--300 m column.",
        "",
        "## 2023 eastern-region monthly values",
        "",
        dataframe_to_markdown(focus),
        "",
        "## Interpretation rule",
        "",
        "A row is a region-mean sign mismatch only when matched-footprint OISST SSTA is positive and common-baseline 0--300 m OHC is negative. The 0--80 m and 80--300 m columns show whether vertical compensation causes that sign difference.",
    ]
    (OUT_DIR / "VERIFICATION_SUMMARY.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(comparison.to_string(index=False))
    print(f"Vertical partition closure max: {closure:.6g} GJ m-2")
    print(focus.to_string(index=False))
    print(OUT_DIR / "VERIFICATION_SUMMARY.md")


if __name__ == "__main__":
    main()
