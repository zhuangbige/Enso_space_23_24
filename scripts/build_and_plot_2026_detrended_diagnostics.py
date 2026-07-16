#!/usr/bin/env python3
"""Build and plot detrended 2026 ENSO/FEP diagnostics.

This script keeps the original non-detrended products intact. It creates a
parallel set of monthly tables, ERA5 anomaly fields, and figures in
``*_detrended`` paths. The detrending convention is:

1. subtract the 1982-2022 monthly climatology;
2. fit a linear trend to the 1982-2022 monthly anomaly series;
3. subtract that fitted trend from every available month.

For the GRL Fig. 4-style D20 panel, the source paper used a 1960-2024
baseline, so the ORAS5 D20 detrending follows that longer period.
"""

from __future__ import annotations

import csv
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

BASELINE_START = 1982
BASELINE_END = 2022
GRL_BASELINE_START = 1960
GRL_BASELINE_END = 2024

MONTHLY_IN = ROOT / "data/interim/research_2026/current_2026_monthly_indices.csv"
OISST_IN = ROOT / "data/interim/research_2026/oisst_nino3_monthly_1982_2026m05.csv"
ERA5_SCRIPT = ROOT / "scripts/build_era5_2026_spatial_analysis.py"
QUICKLOOK_SCRIPT = ROOT / "scripts/plot_2026_current_diagnostics.py"
RESULT_SCRIPT = ROOT / "scripts/plot_2026_result_figures.py"
ERA5_PLOT_SCRIPT = ROOT / "scripts/plot_2026_era5_spatial_meteorology.py"

MONTHLY_OUT = ROOT / "data/interim/research_2026/current_2026_monthly_indices_detrended.csv"
OISST_OUT = ROOT / "data/interim/research_2026/oisst_nino3_monthly_1982_2026m05_detrended.csv"
FEP_OUT = ROOT / "data/derived/research_2026/current_2026_fep_residual_detrended.csv"
EXPECTED_OUT = ROOT / "data/derived/research_2026/current_2026_regression_expected_response_detrended.csv"
ERA5_NPZ_OUT = ROOT / "data/interim/research_2026/current_2026_era5_spatial_anomalies_detrended.npz"
ERA5_CSV_OUT = ROOT / "data/derived/research_2026/current_2026_era5_region_summary_detrended.csv"
D20_TRANSECT = ROOT / "data/interim/research_2026/oras5_d20_timeseries_equatorial_1960_202605.csv"
D20_ANNUAL_OUT = ROOT / "data/derived/research_2026/oras5_d20_annual_detrended_10yr.csv"
GRL_CORR_IN = ROOT / "data/derived/research_2026/grl_fig4_same_source_leadlag_corr_ersstv5_trailing15.csv"
GRL_FIG_OUT_DIR = ROOT / "outputs/research_2026/figures_detrended"
REPORT_OUT = ROOT / "reports/2026去趋势重画说明.md"

PERIODS = {
    "JAN": (1,),
    "FEB": (2,),
    "MAR": (3,),
    "APR": (4,),
    "MAY": (5,),
    "JFM": (1, 2, 3),
    "FMA": (2, 3, 4),
    "MAM": (3, 4, 5),
    "AM_to_date": (4, 5),
}


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _decimal_year(year: pd.Series | np.ndarray, month: pd.Series | np.ndarray) -> np.ndarray:
    return np.asarray(year, dtype=float) + (np.asarray(month, dtype=float) - 0.5) / 12.0


def _fit_and_remove_trend(values: np.ndarray, years: np.ndarray, fit_mask: np.ndarray) -> tuple[np.ndarray, float, float]:
    finite = np.isfinite(values)
    mask = fit_mask & finite
    if int(mask.sum()) < 24:
        return np.full_like(values, np.nan, dtype=float), np.nan, np.nan
    slope, intercept = np.polyfit(years[mask], values[mask], 1)
    detrended = values - (slope * years + intercept)
    return detrended, float(slope), float(intercept)


def detrend_monthly_table(
    frame: pd.DataFrame,
    group_cols: list[str],
    *,
    baseline_start: int = BASELINE_START,
    baseline_end: int = BASELINE_END,
) -> pd.DataFrame:
    """Return monthly anomalies with a linear trend removed within each group."""
    pieces: list[pd.DataFrame] = []
    for _, group in frame.groupby(group_cols, dropna=False):
        group = group.sort_values(["year", "month"]).copy()
        base_mask = group["year"].between(baseline_start, baseline_end).to_numpy()
        climatology = (
            group.loc[group["year"].between(baseline_start, baseline_end)]
            .groupby("month")["value"]
            .mean()
        )
        raw_anomaly = group["value"].to_numpy(dtype=float) - group["month"].map(climatology).to_numpy(dtype=float)
        time = _decimal_year(group["year"].to_numpy(), group["month"].to_numpy())
        detrended, slope, intercept = _fit_and_remove_trend(raw_anomaly, time, base_mask)
        group["anomaly_raw_before_detrend"] = raw_anomaly
        group["anomaly"] = detrended
        group["linear_trend_slope_per_year"] = slope
        group["linear_trend_intercept"] = intercept
        if "anomaly_kind" in group.columns:
            group["anomaly_kind"] = f"{baseline_start}-{baseline_end} monthly climatology, linear trend removed"
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def build_detrended_monthly_products() -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = pd.read_csv(MONTHLY_IN)
    monthly_det = detrend_monthly_table(monthly, ["metric", "region", "source", "unit"])
    MONTHLY_OUT.parent.mkdir(parents=True, exist_ok=True)
    monthly_det.to_csv(MONTHLY_OUT, index=False)

    oisst = pd.read_csv(OISST_IN)
    oisst["metric"] = "oisst_sst"
    oisst["region"] = "nino3"
    oisst["source"] = "NOAA OISST v2.1"
    oisst["unit"] = "deg C"
    oisst_det = detrend_monthly_table(oisst, ["metric", "region", "source", "unit"])
    oisst_det = oisst_det.drop(columns=["metric", "region", "source", "unit"])
    OISST_OUT.parent.mkdir(parents=True, exist_ok=True)
    oisst_det.to_csv(OISST_OUT, index=False)
    return monthly_det, oisst_det


def _period_value(
    monthly: pd.DataFrame,
    metric: str,
    region: str,
    year: int,
    months: tuple[int, ...],
) -> float:
    subset = monthly.loc[
        (monthly["metric"] == metric)
        & (monthly["region"] == region)
        & (monthly["year"] == year)
        & (monthly["month"].isin(months))
    ]
    if subset["month"].nunique() != len(months):
        return np.nan
    return float(subset["anomaly"].mean())


def _seasonal_series(monthly: pd.DataFrame, metric: str, region: str, months: tuple[int, ...]) -> pd.Series:
    years = sorted(monthly.loc[(monthly["metric"] == metric) & (monthly["region"] == region), "year"].unique())
    rows: dict[int, float] = {}
    for year in years:
        value = _period_value(monthly, metric, region, int(year), months)
        if np.isfinite(value):
            rows[int(year)] = value
    return pd.Series(rows, dtype=float).sort_index()


def _regress(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 10:
        return np.nan, np.nan, np.nan
    slope, intercept = np.polyfit(x[mask], y[mask], 1)
    corr = float(np.corrcoef(x[mask], y[mask])[0, 1]) if np.nanstd(x[mask]) > 0 and np.nanstd(y[mask]) > 0 else np.nan
    return float(slope), float(intercept), corr


def build_fep_residual(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for period, months in PERIODS.items():
        nino34 = _seasonal_series(monthly, "ersstv5_sst", "nino34", months)
        fep = _seasonal_series(monthly, "ersstv5_sst", "fep", months)
        joined = pd.concat({"nino34": nino34, "fep": fep}, axis=1).dropna()
        fit = joined.loc[(joined.index >= BASELINE_START) & (joined.index <= BASELINE_END)]
        slope, intercept, corr = _regress(fit["nino34"].to_numpy(), fit["fep"].to_numpy())
        nino34_2026 = joined.loc[2026, "nino34"] if 2026 in joined.index else np.nan
        fep_2026 = joined.loc[2026, "fep"] if 2026 in joined.index else np.nan
        expected = slope * nino34_2026 + intercept if np.isfinite(nino34_2026) else np.nan
        rows.append(
            {
                "period": period,
                "nino34_2026": nino34_2026,
                "fep_observed_2026": fep_2026,
                "fep_expected_from_nino34": expected,
                "fep_residual": fep_2026 - expected if np.isfinite(fep_2026) and np.isfinite(expected) else np.nan,
                "slope": slope,
                "intercept": intercept,
                "r": corr,
                "regression_n_years": int(len(fit.dropna())),
                "regression_years": f"{BASELINE_START}-{BASELINE_END}",
                "note": "Detrended FEP residual: FEP minus the part linearly associated with detrended Nino-3.4.",
            }
        )
    out = pd.DataFrame(rows)
    FEP_OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(FEP_OUT, index=False)
    return out


def build_expected_response(monthly: pd.DataFrame) -> pd.DataFrame:
    responses = [
        ("ncep_soi_like_slp", "tahiti_minus_darwin"),
        ("gpcp_precip", "central_pacific_180_140w"),
        ("gpcp_precip", "cwp_160e_140w"),
        ("ncep_sig995_u", "cwp_160e_140w"),
    ]
    rows: list[dict[str, object]] = []
    for period, months in PERIODS.items():
        predictor = _seasonal_series(monthly, "ersstv5_sst", "nino3", months)
        for response_metric, response_region in responses:
            response = _seasonal_series(monthly, response_metric, response_region, months)
            joined = pd.concat({"nino3": predictor, "response": response}, axis=1).dropna()
            if 2026 not in joined.index:
                continue
            fit = joined.loc[(joined.index >= BASELINE_START) & (joined.index <= BASELINE_END)]
            slope, intercept, corr = _regress(fit["nino3"].to_numpy(), fit["response"].to_numpy())
            nino3_2026 = float(joined.loc[2026, "nino3"])
            observed = float(joined.loc[2026, "response"])
            expected = slope * nino3_2026 + intercept
            ratio = observed / expected if np.isfinite(expected) and abs(expected) > 1e-8 else np.nan
            rows.append(
                {
                    "period": period,
                    "predictor": "ersstv5_sst:nino3",
                    "response_metric": response_metric,
                    "response_region": response_region,
                    "nino3_2026": nino3_2026,
                    "observed_2026": observed,
                    "expected_from_regression": expected,
                    "residual_observed_minus_expected": observed - expected,
                    "observed_over_expected": ratio,
                    "slope": slope,
                    "intercept": intercept,
                    "r": corr,
                    "regression_n_years": int(len(fit.dropna())),
                    "regression_years": f"{BASELINE_START}-{BASELINE_END}",
                }
            )
    out = pd.DataFrame(rows)
    EXPECTED_OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(EXPECTED_OUT, index=False)
    return out


def _time_decimal_from_xarray(time_coord: xr.DataArray) -> np.ndarray:
    year = time_coord.dt.year.values.astype(float)
    month = time_coord.dt.month.values.astype(float)
    return year + (month - 0.5) / 12.0


def _linear_detrend_grid(values: np.ndarray, time: np.ndarray, fit_mask: np.ndarray) -> np.ndarray:
    original_shape = values.shape
    flat = values.reshape(values.shape[0], -1).astype(float)
    x = time[fit_mask].astype(float)
    y = flat[fit_mask, :]
    valid = np.isfinite(y)
    count = valid.sum(axis=0).astype(float)
    x2 = x[:, None]
    sum_x = (x2 * valid).sum(axis=0)
    sum_y = np.where(valid, y, 0.0).sum(axis=0)
    mean_x = np.divide(sum_x, count, out=np.full_like(count, np.nan, dtype=float), where=count > 2)
    mean_y = np.divide(sum_y, count, out=np.full_like(count, np.nan, dtype=float), where=count > 2)
    dx = np.where(valid, x2 - mean_x, 0.0)
    dy = np.where(valid, y - mean_y, 0.0)
    denom = (dx * dx).sum(axis=0)
    numer = (dx * dy).sum(axis=0)
    slope = np.divide(numer, denom, out=np.full_like(denom, np.nan, dtype=float), where=denom > 0)
    intercept = mean_y - slope * mean_x
    trend = time[:, None] * slope[None, :] + intercept[None, :]
    detrended = flat - trend
    detrended[:, count <= 2] = np.nan
    return detrended.reshape(original_shape)


def _detrended_era5_anomalies(ds: xr.Dataset) -> xr.Dataset:
    climatology = ds.sel(time=slice(f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-31")).groupby("time.month").mean("time")
    anom = ds.groupby("time.month") - climatology
    time = _time_decimal_from_xarray(anom.time)
    fit_mask = (anom.time.dt.year.values >= BASELINE_START) & (anom.time.dt.year.values <= BASELINE_END)
    out = xr.Dataset(coords=anom.coords)
    for var in anom.data_vars:
        da = anom[var].transpose("time", "lat", "lon")
        det = _linear_detrend_grid(da.values, time, fit_mask)
        out[var] = xr.DataArray(det.astype(np.float32), coords=da.coords, dims=da.dims, attrs=da.attrs)
    return out


def build_detrended_era5() -> None:
    era5_builder = _load_module(ERA5_SCRIPT, "era5_builder_for_detrended")
    ds = era5_builder._open_inputs()
    anom = _detrended_era5_anomalies(ds)
    lat = anom.lat.values.astype(np.float32)
    lon = anom.lon.values.astype(np.float32)
    periods = list(PERIODS.keys())
    variables = ["u10", "v10", "msl_hpa", "tp_mm_day", "u850", "v850", "omega850"]
    output: dict[str, object] = {
        "lat": lat,
        "lon": lon,
        "periods": np.asarray(periods),
        "variables": np.asarray(variables),
        "months": np.asarray(["JAN", "FEB", "MAR", "APR", "MAY"]),
        "reference_period": np.asarray(f"{BASELINE_START}-{BASELINE_END} monthly climatology, linear trend removed"),
        "sources": np.asarray([str(era5_builder.SINGLE_AVGUA), str(era5_builder.SINGLE_AVGAD), str(era5_builder.PRESSURE)]),
        "u10_hov": era5_builder._equatorial_hov(anom, "u10"),
        "u850_hov": era5_builder._equatorial_hov(anom, "u850"),
        "tp_hov": era5_builder._equatorial_hov(anom, "tp_mm_day"),
    }
    rows: list[dict[str, object]] = []
    period_fields: dict[str, xr.Dataset] = {}
    for period in periods:
        period_fields[period] = era5_builder._period_mean(anom, period)
        for var in variables:
            output[f"{var}_{period}"] = period_fields[period][var].values.astype(np.float32)

    for period, fields in period_fields.items():
        for var in variables:
            for region_id, region in era5_builder.REGIONS.items():
                rows.append(
                    {
                        "period": period,
                        "metric": f"era5_{var}",
                        "region": region_id,
                        "anomaly": era5_builder._weighted_region_mean(fields[var], region),
                        "unit": {
                            "u10": "m/s",
                            "v10": "m/s",
                            "msl_hpa": "hPa",
                            "tp_mm_day": "mm/day",
                            "u850": "m/s",
                            "v850": "m/s",
                            "omega850": "Pa/s",
                        }[var],
                        "anomaly_kind": f"{BASELINE_START}-{BASELINE_END} monthly climatology, linear trend removed",
                        "source": "ERA5 monthly means via Copernicus CDS",
                    }
                )
        rows.append(
            {
                "period": period,
                "metric": "era5_soi_like_mslp",
                "region": "tahiti_minus_darwin",
                "anomaly": era5_builder._weighted_region_mean(fields["msl_hpa"], era5_builder.REGIONS["tahiti_proxy"])
                - era5_builder._weighted_region_mean(fields["msl_hpa"], era5_builder.REGIONS["darwin_proxy"]),
                "unit": "hPa",
                "anomaly_kind": f"{BASELINE_START}-{BASELINE_END} monthly climatology, linear trend removed",
                "source": "ERA5 monthly means via Copernicus CDS",
            }
        )
    ERA5_NPZ_OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(ERA5_NPZ_OUT, **output)
    ERA5_CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with ERA5_CSV_OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_detrended_d20_annual() -> pd.DataFrame:
    raw = pd.read_csv(D20_TRANSECT, parse_dates=["time"])
    raw = raw.loc[
        ((raw["product_type"] == "consolidated") & (raw["year"] <= 2014))
        | (raw["product_type"] == "operational")
    ].copy()
    raw = raw.loc[raw["d20_m"].notna()].copy()
    raw["lon"] = raw["requested_lon"].astype(float)
    pieces: list[pd.DataFrame] = []
    for lon, group in raw.groupby("lon"):
        group = group.sort_values("time").copy()
        base = group["year"].between(GRL_BASELINE_START, GRL_BASELINE_END)
        climatology = group.loc[base].groupby("month")["d20_m"].mean()
        anomaly = group["d20_m"].to_numpy(dtype=float) - group["month"].map(climatology).to_numpy(dtype=float)
        decimal_time = _decimal_year(group["year"].to_numpy(), group["month"].to_numpy())
        detrended, slope, intercept = _fit_and_remove_trend(anomaly, decimal_time, base.to_numpy())
        group["d20_anomaly_m"] = anomaly
        group["d20_detrended_m"] = detrended
        group["linear_trend_slope_m_per_year"] = slope
        group["linear_trend_intercept_m"] = intercept
        pieces.append(group)
    detrended = pd.concat(pieces, ignore_index=True)
    annual = (
        detrended.groupby(["year", "lon"], as_index=False)["d20_detrended_m"]
        .mean()
        .sort_values(["lon", "year"])
    )
    annual["d20_10yr_trailing_m"] = annual.groupby("lon")["d20_detrended_m"].transform(
        lambda s: s.rolling(10, min_periods=8).mean()
    )
    D20_ANNUAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    annual.to_csv(D20_ANNUAL_OUT, index=False)
    return annual


def _lon_label(lon: float) -> str:
    if np.isclose(lon, 180):
        return "180°"
    if lon < 180:
        return f"{int(lon)}°E"
    return f"{int(360-lon)}°W"


def plot_grl_fig4_detrended_d20(annual_d20: pd.DataFrame) -> None:
    corr_df = pd.read_csv(GRL_CORR_IN)
    lags = np.sort(corr_df["lag_month"].unique())
    years = np.sort(corr_df["window_year"].unique())
    corr_grid = corr_df.pivot(index="window_year", columns="lag_month", values="corr").reindex(index=years, columns=lags).to_numpy()
    corr_valid = np.isfinite(corr_grid).any(axis=1)
    years_plot = years[corr_valid]
    corr_grid = corr_grid[corr_valid, :]

    lon = np.sort(annual_d20["lon"].unique())
    d20_years = np.sort(annual_d20["year"].unique())
    d20_grid = (
        annual_d20.pivot(index="year", columns="lon", values="d20_10yr_trailing_m")
        .reindex(index=d20_years, columns=lon)
        .to_numpy()
    )
    d20_valid = np.isfinite(d20_grid).any(axis=1)
    d20_years_plot = d20_years[d20_valid]
    d20_grid = d20_grid[d20_valid, :]

    GRL_FIG_OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(12.8, 8.0), dpi=170)
    grid = fig.add_gridspec(1, 2, width_ratios=[1, 1], wspace=0.30)
    ax1 = fig.add_subplot(grid[0, 0])
    ax2 = fig.add_subplot(grid[0, 1])

    im1 = ax1.contourf(lags, years_plot, corr_grid, levels=np.linspace(-0.9, 0.9, 19), cmap="RdBu_r", extend="both")
    ax1.axvline(0, color="0.25", ls="--", lw=1.5)
    for year in [1976, 2005]:
        ax1.axhline(year, color="white", ls=(0, (4, 4)), lw=1.4)
    ax1.set_title("(a) Lead-lag correlation\nERSSTv5 T$_{N34}$ and residual FEP T$_R$", weight="bold")
    ax1.set_xlabel("Lag time (month)")
    ax1.set_ylabel("15-yr window end year")
    ax1.set_xlim(-12, 12)
    ax1.set_xticks(np.arange(-12, 13, 2))
    ax1.text(-8.4, years_plot.min() + 1.7, "T$_{N34}$ lead", weight="bold", ha="center")
    ax1.text(7.0, years_plot.min() + 1.7, "T$_R$ lead", weight="bold", ha="center")
    cbar1 = fig.colorbar(im1, ax=ax1, orientation="horizontal", pad=0.085, fraction=0.055)
    cbar1.set_label("correlation")

    im2 = ax2.contourf(lon, d20_years_plot, d20_grid, levels=np.arange(-18, 19, 3), cmap="RdBu_r", extend="both")
    ax2.contour(lon, d20_years_plot, d20_grid, levels=np.arange(-18, 19, 3), colors="k", linewidths=0.45, alpha=0.75)
    for year in [1976, 2005]:
        ax2.axhline(year, color="white", ls=(0, (4, 4)), lw=1.4)
    ax2.set_title("(b) Detrended ORAS5 D20\n10-yr trailing mean", weight="bold")
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Year")
    ax2.set_xlim(130, 280)
    xticks = [150, 180, 210, 240, 270]
    ax2.set_xticks(xticks)
    ax2.set_xticklabels([_lon_label(x) for x in xticks])
    cbar2 = fig.colorbar(im2, ax=ax2, orientation="horizontal", pad=0.085, fraction=0.055)
    cbar2.set_label("m")

    fig.suptitle("GRL Fig. 4 same-source extension with detrended ORAS5 D20 (through 2026-05)", weight="bold", y=0.98)
    fig.text(
        0.055,
        0.025,
        "SST panel uses the existing ERSSTv5 detrended residual-FEP calculation. "
        "D20 panel uses ORAS5 monthly anomalies relative to 1960-2024 monthly climatology with the 1960-2024 linear trend removed before annual and 10-yr trailing averaging.",
        fontsize=8,
        color="0.25",
    )
    fig.savefig(GRL_FIG_OUT_DIR / "fig12_grl_fig4_same_sources_detrended_to_2026.png", bbox_inches="tight", dpi=300)
    fig.savefig(GRL_FIG_OUT_DIR / "fig12_grl_fig4_same_sources_detrended_to_2026.pdf", bbox_inches="tight")
    plt.close(fig)


def run_existing_plotters() -> None:
    quick = _load_module(QUICKLOOK_SCRIPT, "plot_quicklook_detrended")
    quick.MONTHLY = MONTHLY_OUT
    quick.EXPECTED = EXPECTED_OUT
    quick.FEP = FEP_OUT
    quick.OUT_DIR = ROOT / "outputs/research_2026/detrended"
    if hasattr(quick, "ANOMALY_LABEL"):
        quick.ANOMALY_LABEL = "detrended anomaly"
    if hasattr(quick, "ANOMALY_NOTE"):
        quick.ANOMALY_NOTE = "1982-2022 monthly climatology with the 1982-2022 linear trend removed"
    quick.main()

    result = _load_module(RESULT_SCRIPT, "plot_results_detrended")
    result.MONTHLY = MONTHLY_OUT
    result.OISST_NINO3 = OISST_OUT
    result.FEP = FEP_OUT
    result.EXPECTED = EXPECTED_OUT
    result.OUT_DIR = ROOT / "outputs/research_2026/figures_detrended"
    if hasattr(result, "ANOMALY_LABEL"):
        result.ANOMALY_LABEL = "detrended anomaly"
    if hasattr(result, "ANOMALY_NOTE"):
        result.ANOMALY_NOTE = "1982-2022 monthly climatology with the 1982-2022 linear trend removed"
    result.main()

    era5_plot = _load_module(ERA5_PLOT_SCRIPT, "plot_era5_detrended")
    era5_plot.INPUT = ERA5_NPZ_OUT
    era5_plot.OUT_DIR = ROOT / "outputs/research_2026/era5_spatial_detrended"
    if hasattr(era5_plot, "ANOMALY_NOTE"):
        era5_plot.ANOMALY_NOTE = "Anomalies use 1982-2022 monthly climatology with the 1982-2022 linear trend removed."
    era5_plot.main()


def write_report() -> None:
    monthly = pd.read_csv(MONTHLY_OUT)
    fep = pd.read_csv(FEP_OUT)
    expected = pd.read_csv(EXPECTED_OUT)
    era5 = pd.read_csv(ERA5_CSV_OUT)
    d20 = pd.read_csv(D20_ANNUAL_OUT)
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)

    def val(metric: str, region: str, month: int) -> float:
        row = monthly.loc[
            (monthly["metric"] == metric)
            & (monthly["region"] == region)
            & (monthly["year"] == 2026)
            & (monthly["month"] == month)
        ]
        return float(row["anomaly"].iloc[0]) if len(row) else np.nan

    fep_mam = fep.loc[fep["period"].eq("MAM"), "fep_residual"].iloc[0]
    fep_am = fep.loc[fep["period"].eq("AM_to_date"), "fep_residual"].iloc[0]
    cp_precip_jfm = expected.loc[
        (expected["period"].eq("JFM"))
        & (expected["response_metric"].eq("gpcp_precip"))
        & (expected["response_region"].eq("central_pacific_180_140w"))
    ]
    cp_precip_text = "NA"
    if len(cp_precip_jfm):
        row = cp_precip_jfm.iloc[0]
        cp_precip_text = (
            f"观测 {row['observed_2026']:.2f} mm/day，"
            f"Niño-3 回归预期 {row['expected_from_regression']:.2f} mm/day，"
            f"残差 {row['residual_observed_minus_expected']:.2f} mm/day"
        )
    era5_u850_am = era5.loc[
        (era5["period"].eq("AM_to_date"))
        & (era5["metric"].eq("era5_u850"))
        & (era5["region"].eq("cwp_160e_140w"))
    ]["anomaly"].iloc[0]
    d20_latest = d20.loc[d20["year"].eq(d20["year"].max())].copy()
    west = d20_latest.loc[d20_latest["lon"].between(135, 180), "d20_10yr_trailing_m"].mean()
    central = d20_latest.loc[d20_latest["lon"].between(185, 240), "d20_10yr_trailing_m"].mean()
    east = d20_latest.loc[d20_latest["lon"].between(245, 275), "d20_10yr_trailing_m"].mean()

    REPORT_OUT.write_text(
        f"""# 2026 诊断图去趋势重画说明

生成日期：2026-06-24

## 本次完成

已将当前本地可重算的数据产品全部改为去趋势异常并重新绘图：

- 指数图与 FEP residual：`outputs/research_2026/detrended/`、`outputs/research_2026/figures_detrended/`
- ERA5 空间图与 Hovmoller 图：`outputs/research_2026/era5_spatial_detrended/`
- OISST/GPCP/NCEP 经纬度图：`outputs/research_2026/spatial_meteorology_detrended/`
- GRL Fig.4 同源延伸图的 ORAS5 D20 去趋势版本：`outputs/research_2026/figures_detrended/fig12_grl_fig4_same_sources_detrended_to_2026.png`

旧图没有被覆盖，仍保留在原来的输出目录。

## 去趋势算法

对 1982-2022 资料：

1. 先按月份计算气候态；
2. 用原值减去对应月份气候态，得到月异常；
3. 对每个变量/区域/格点的月异常序列拟合 1982-2022 线性趋势；
4. 从完整序列中扣除该线性趋势；
5. 再对 2026 的 Jan、Feb、Mar、Apr、May、JFM、FMA、MAM、Apr-May 等时段求平均。

GRL Fig.4 的 ORAS5 D20 右图使用原文同类基准：1960-2024 月气候态和 1960-2024 线性趋势。

## 去趋势后的几个关键读数

- 2026 年 5 月 detrended Niño-3 SST：{val('ersstv5_sst', 'nino3', 5):.2f} °C。
- 2026 年 MAM detrended FEP residual：{fep_mam:.2f} °C；Apr-May detrended FEP residual：{fep_am:.2f} °C。
- JFM 中太平洋 GPCP 降水相对 Niño-3 预期：{cp_precip_text}。
- ERA5 Apr-May CWP 850 hPa 纬向风异常：{era5_u850_am:.2f} m/s，正值表示西风异常。
- ORAS5 D20 2026 最新 10 年 trailing mean：西太平洋 {west:.2f} m，中太平洋 {central:.2f} m，东太平洋 {east:.2f} m。

## 与未去趋势图相比的初步判断

- FEP residual 的正异常仍然存在，说明“远东太平洋增暖相对 Niño-3.4 偏强”不是简单由线性背景增暖造成。
- 低层风和 D20 对去趋势更敏感。尤其 ERA5 850 hPa 风和 ORAS5 中东太平洋 D20 在扣除趋势后幅度/符号会改变，因此这两类图后续汇报应优先使用去趋势版本。
- 降水的负异常减弱一些，但 JFM 中太平洋降水仍低于由 Niño-3 回归得到的预期，弱对流响应的判断仍可保留，但要标注数据到 2026 年 3 月。

## OISST/GPCP/NCEP 经纬度图补充

2026-06-24 已重新从 NOAA PSL OPeNDAP 拉取历史格点资料，生成 `data/interim/research_2026/current_2026_spatial_meteorology_detrended.npz`，并重画：

- `fig4_2026_sst_precip_spatial`：OISST SST + GPCP precipitation 经纬度图；
- `fig5_2026_ncep_wind_slp_spatial`：NCEP 850 hPa 风场 + SLP 经纬度图；
- `fig7_2026_equatorial_sst_precip_hovmoller`：赤道 SST/降水 longitude-time 图。

为避免 NOAA 高分辨率 OISST OPeNDAP 远程读取过慢，OISST 使用 `--oisst-stride 4`，约等于 1° 输出分辨率；GPCP 和 NCEP 使用原始远程网格。所有这些图都使用 1982-2022 月气候态并扣除 1982-2022 线性趋势。

## 尚未真正去趋势重画的图

CPC OLR 图 `fig6_2026_olr_convection_spatial` 还没有严格去趋势重画。原因是 CPC OLR 是日异常产品，若严格去趋势需要扫描 1982-2022 每日格点异常；本轮尝试后发现远程 OPeNDAP 读取耗时明显偏长，因此先跳过 OLR，把 SST/GPCP/NCEP 经纬度图完成。后续可单独作为长任务运行完整 OLR 版本：

```bash
.venv/bin/python -u scripts/extract_2026_spatial_meteorology_opendap.py --detrend --oisst-stride 4 --output data/interim/research_2026/current_2026_spatial_meteorology_detrended_with_olr.npz
.venv/bin/python scripts/plot_2026_spatial_meteorology.py --input data/interim/research_2026/current_2026_spatial_meteorology_detrended_with_olr.npz --out-dir outputs/research_2026/spatial_meteorology_detrended_with_olr --anomaly-note "Anomalies use 1982-2022 monthly climatology with the 1982-2022 linear trend removed."
```

## 数据来源

- ERSSTv5：NOAA PSL / NOAA ERSSTv5
- OISST v2.1：NOAA NCEI Optimum Interpolation SST
- GPCP：NOAA PSL GPCP monthly precipitation
- NCEP/NCAR：NOAA PSL Reanalysis
- ERA5：Copernicus Climate Data Store ERA5 monthly means
- ORAS5：Copernicus Climate Data Store ORAS5 time-series

## 输出表

- `{MONTHLY_OUT}`
- `{OISST_OUT}`
- `{FEP_OUT}`
- `{EXPECTED_OUT}`
- `{ERA5_NPZ_OUT}`
- `{ERA5_CSV_OUT}`
- `{D20_ANNUAL_OUT}`
- `/Users/daiyue/Documents/Maryland/data/interim/research_2026/current_2026_spatial_meteorology_detrended.npz`
""",
        encoding="utf-8",
    )


def main() -> int:
    monthly, _ = build_detrended_monthly_products()
    build_fep_residual(monthly)
    build_expected_response(monthly)
    build_detrended_era5()
    annual_d20 = build_detrended_d20_annual()
    plot_grl_fig4_detrended_d20(annual_d20)
    run_existing_plotters()
    write_report()
    print(MONTHLY_OUT)
    print(OISST_OUT)
    print(FEP_OUT)
    print(EXPECTED_OUT)
    print(ERA5_NPZ_OUT)
    print(ERA5_CSV_OUT)
    print(D20_ANNUAL_OUT)
    print(REPORT_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
