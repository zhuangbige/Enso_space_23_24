#!/usr/bin/env python3
"""Connect SODA3 eastern-Pacific warm-heat fate to air-sea coupling.

The analysis asks whether the CT-minus-CP contrast in poleward warm-heat
export across 5N is accompanied by a physically consistent atmospheric
response.  It combines the previously closed SODA3 H20 box budget with
OISST/GPCP/ERA5 monthly indices and ERA5 surface stress/heat-flux fields.

All anomalies are calendar-month linear detrended over 1982-2022 and then
centered-three-month smoothed for time-series and scalar diagnostics.  Event
uncertainty resamples whole events, never individual months.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_chakravorty2021_soda3_baseline as legacy  # noqa: E402

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ImportError:  # pragma: no cover - the fallback is intentionally usable.
    ccrs = None
    cfeature = None


BASELINE = (1982, 2022)
EVENTS = legacy.EVENTS
RELATIVE_MONTHS = tuple(range(0, 17))
PHASES = {
    "development_Jun0_to_Nov0": (5, 10),
    "mature_decay_Dec0_to_May1": (11, 16),
}
BOOTSTRAP_SAMPLES = 20_000
RANDOM_SEED = 20260804

RHO_WATER = 1025.0
OMEGA = 7.2921159e-5
EARTH_RADIUS = 6_371_000.0

SODA_MONTHLY = (
    ROOT / "data/derived/research_2026/soda3_three_box_warm_heat_budget_monthly_1980_2022.csv"
)
ATM_MONTHLY = ROOT / "data/derived/research_2026/enso_full_year_coupling_monthly_1982_2024.csv"
ERA5_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"
GPCP_NC = ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_air_sea_coupled_fate"
PDF_DIR = ROOT / "output/pdf"

MONTHLY_CSV = DERIVED / "soda3_air_sea_coupled_warm_heat_monthly_1982_2022.csv"
EVENT_MONTHLY_CSV = DERIVED / "soda3_air_sea_coupled_warm_heat_event_monthly.csv"
EVENT_PHASE_CSV = DERIVED / "soda3_air_sea_coupled_warm_heat_event_phase.csv"
SUMMARY_CSV = DERIVED / "soda3_air_sea_coupled_warm_heat_summary.csv"
CORRELATION_CSV = DERIVED / "soda3_air_sea_coupled_warm_heat_correlations.csv"
MAP_NC = DERIVED / "soda3_air_sea_coupled_warm_heat_decay_maps.nc"
DIAGNOSTICS_JSON = DERIVED / "soda3_air_sea_coupled_warm_heat_diagnostics.json"

MECHANISM_PNG = OUT / "soda3_air_sea_coupled_warm_heat_mechanism.png"
MECHANISM_PDF = PDF_DIR / "soda3_air_sea_coupled_warm_heat_mechanism.pdf"
SEQUENCE_PNG = OUT / "soda3_air_sea_coupled_warm_heat_sequence.png"
SEQUENCE_PDF = PDF_DIR / "soda3_air_sea_coupled_warm_heat_sequence.pdf"
REPORT_MD = OUT / "SODA3_AIR_SEA_COUPLED_WARM_HEAT_FATE_CN.md"

ERA5_VARIABLES = {
    "avg_iews": "tau_x",
    "avg_snswrf": "shortwave",
    "avg_snlwrf": "longwave",
    "avg_slhtf": "latent",
    "avg_ishf": "sensible",
}
FLUX_COMPONENTS = ("shortwave", "longwave", "latent", "sensible")


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.7,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.0,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 7.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def normalize_time(values: np.ndarray) -> pd.DatetimeIndex:
    times = pd.to_datetime(values)
    return pd.DatetimeIndex(
        [pd.Timestamp(year=item.year, month=item.month, day=15) for item in times]
    )


def anomaly_and_smooth(values: np.ndarray, times: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    anomaly = legacy.same_month_detrended(np.asarray(values, dtype=float), times, BASELINE)
    smooth = pd.Series(anomaly).rolling(3, center=True, min_periods=3).mean().to_numpy()
    return anomaly, smooth


def normalize_era5(dataset: xr.Dataset) -> xr.Dataset:
    rename = {
        name: replacement
        for name, replacement in {
            "valid_time": "time",
            "latitude": "lat",
            "longitude": "lon",
        }.items()
        if name in dataset.dims or name in dataset.coords
    }
    output = dataset.rename(rename)
    output = output.rename({name: ERA5_VARIABLES[name] for name in ERA5_VARIABLES if name in output})
    output = output.assign_coords(lon=(output.lon % 360.0)).sortby("lon").sortby("lat")
    output = output.assign_coords(time=normalize_time(output.time.values))
    return output


def load_era5_fields() -> xr.Dataset:
    months: list[xr.Dataset] = []
    for month in range(1, 13):
        pieces = []
        for part in ("part01", "part02"):
            path = ERA5_DIR / f"era5_coupling_{part}_m{month:02d}_1982_2025_1p0deg.nc"
            with xr.open_dataset(path, engine="netcdf4", chunks=None) as dataset:
                selected = normalize_era5(dataset[list(ERA5_VARIABLES)]).sel(
                    time=slice("1982-01-15", "2022-12-15")
                )
                pieces.append(selected.load())
        combined = xr.concat(pieces, dim="lon").sortby("lon")
        _, unique = np.unique(combined.lon.values, return_index=True)
        months.append(combined.isel(lon=np.sort(unique)))
    output = xr.concat(months, dim="time").sortby("time")
    expected = pd.date_range("1982-01-01", "2022-12-01", freq="MS") + pd.Timedelta(days=14)
    if not pd.DatetimeIndex(output.time.values).equals(expected):
        raise ValueError("ERA5 fields do not form a complete 1982-2022 monthly axis")
    return output


def weighted_mean(field: xr.DataArray, lat0: float, lat1: float, lon0: float, lon1: float) -> xr.DataArray:
    selected = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    weights = xr.DataArray(
        np.cos(np.deg2rad(selected.lat.values)),
        dims=("lat",),
        coords={"lat": selected.lat},
    )
    return selected.weighted(weights).mean(("lat", "lon"))


def box_area_m2(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    dlat = float(np.median(np.diff(lat)))
    dlon = float(np.median(np.diff(lon)))
    south = np.deg2rad(lat - dlat / 2.0)
    north = np.deg2rad(lat + dlat / 2.0)
    strip = EARTH_RADIUS**2 * np.deg2rad(dlon) * (np.sin(north) - np.sin(south))
    return strip[:, None] * np.ones((1, len(lon)))


def integrated_power_pw(field: xr.DataArray, lat0: float, lat1: float, lon0: float, lon1: float) -> np.ndarray:
    selected = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    area = box_area_m2(selected.lat.values, selected.lon.values)
    return np.nansum(np.asarray(selected.values, dtype=float) * area[None, :, :], axis=(1, 2)) / 1.0e15


def ekman_north_sv(tau_x_nm2: np.ndarray, lon0: float, lon1: float, latitude: float = 5.0) -> np.ndarray:
    """Return northward Ekman volume transport; westward stress is positive northward."""
    width = EARTH_RADIUS * np.cos(np.deg2rad(latitude)) * np.deg2rad(lon1 - lon0)
    coriolis = 2.0 * OMEGA * np.sin(np.deg2rad(latitude))
    return -np.asarray(tau_x_nm2, dtype=float) * width / (RHO_WATER * coriolis) / 1.0e6


def build_era5_indices(fields: xr.Dataset) -> pd.DataFrame:
    times = pd.DatetimeIndex(fields.time.values)
    output = pd.DataFrame({"time": times, "year": times.year, "month": times.month})

    for lon1 in (270.0, 275.0, 280.0):
        tau_line = (
            fields.tau_x.sel(lat=slice(4.0, 6.0), lon=slice(220.0, lon1)).mean(("lat", "lon")).values
        )
        anomaly, smooth = anomaly_and_smooth(tau_line, times)
        tag = int(lon1)
        output[f"tau5n_220_{tag}e_anom_nm2"] = anomaly
        output[f"tau5n_220_{tag}e_sm3_nm2"] = smooth
        output[f"ekman5n_220_{tag}e_north_sm3_sv"] = ekman_north_sv(
            smooth, 220.0, lon1, 5.0
        )

    tau_values = np.asarray(fields.tau_x.values, dtype=float)
    y = EARTH_RADIUS * np.deg2rad(fields.lat.values)
    curl_x_component = -np.gradient(tau_values, y, axis=1)
    curl_da = xr.DataArray(curl_x_component, coords=fields.tau_x.coords, dims=fields.tau_x.dims)
    curl_index = weighted_mean(curl_da, 0.0, 10.0, 220.0, 280.0).values * 1.0e8
    anomaly, smooth = anomaly_and_smooth(curl_index, times)
    output["minus_dtaux_dy_east_nh_anom_1e8_nm3"] = anomaly
    output["minus_dtaux_dy_east_nh_sm3_1e8_nm3"] = smooth

    for component in FLUX_COMPONENTS:
        mean_values = weighted_mean(fields[component], -10.0, 5.0, 220.0, 280.0).values
        power_values = integrated_power_pw(fields[component], -10.0, 5.0, 220.0, 280.0)
        mean_anomaly, mean_smooth = anomaly_and_smooth(mean_values, times)
        power_anomaly, power_smooth = anomaly_and_smooth(power_values, times)
        output[f"era5_east_{component}_anom_wm2"] = mean_anomaly
        output[f"era5_east_{component}_sm3_wm2"] = mean_smooth
        output[f"era5_east_{component}_anom_pw"] = power_anomaly
        output[f"era5_east_{component}_sm3_pw"] = power_smooth

    output["era5_east_qnet_anom_wm2"] = output[
        [f"era5_east_{item}_anom_wm2" for item in FLUX_COMPONENTS]
    ].sum(axis=1)
    output["era5_east_qnet_sm3_wm2"] = output[
        [f"era5_east_{item}_sm3_wm2" for item in FLUX_COMPONENTS]
    ].sum(axis=1)
    output["era5_east_qnet_anom_pw"] = output[
        [f"era5_east_{item}_anom_pw" for item in FLUX_COMPONENTS]
    ].sum(axis=1)
    output["era5_east_qnet_sm3_pw"] = output[
        [f"era5_east_{item}_sm3_pw" for item in FLUX_COMPONENTS]
    ].sum(axis=1)
    return output


def build_atmospheric_indices() -> pd.DataFrame:
    raw = pd.read_csv(ATM_MONTHLY)
    raw = raw.loc[raw.year.between(BASELINE[0], BASELINE[1])].copy()
    raw["time"] = pd.to_datetime(dict(year=raw.year, month=raw.month, day=15))
    source = {
        "sst_east_raw_c": "oisst_east_sst",
        "precip_central_raw_mmday": "gpcp_central_precip",
        "precip_east_raw_mmday": "gpcp_east_precip",
        "slp_drive_w_minus_e_raw_hpa": "era5_slp_drive",
        "tau_cwp_raw_nm2": "era5_cwp_tau",
    }
    times = pd.DatetimeIndex(raw.time)
    output = raw[["time", "year", "month"]].copy()
    for column, name in source.items():
        anomaly, smooth = anomaly_and_smooth(raw[column].to_numpy(), times)
        output[f"{name}_anom"] = anomaly
        output[f"{name}_sm3"] = smooth
    return output


def build_monthly(fields: xr.Dataset) -> pd.DataFrame:
    soda = pd.read_csv(SODA_MONTHLY, parse_dates=["time"])
    soda = soda.loc[soda.time.dt.year.between(BASELINE[0], BASELINE[1])].copy()
    output = soda.merge(build_atmospheric_indices(), on=["time", "year", "month"], validate="one_to_one")
    output = output.merge(build_era5_indices(fields), on=["time", "year", "month"], validate="one_to_one")
    if len(output) != 41 * 12:
        raise ValueError(f"Expected 492 merged months, found {len(output)}")
    output["soda_east_north_export_sm3_pw"] = -output["east_north_q20_in_sm3"]
    output["soda_east_surface_loss_sm3_pw"] = -output["east_surface_warm_sm3"]
    output["era5_tau5n_westward_sm3_nm2"] = -output["tau5n_220_280e_sm3_nm2"]
    return output


def event_align(monthly: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for event_class, years in EVENTS.items():
        for event_year in years:
            rel = (monthly.year - event_year) * 12 + monthly.month - 1
            selected = monthly.loc[rel.between(min(RELATIVE_MONTHS), max(RELATIVE_MONTHS))].copy()
            selected["event_class"] = event_class
            selected["event_year"] = event_year
            selected["relative_month"] = rel.loc[selected.index].astype(int)
            pieces.append(selected)
    output = pd.concat(pieces, ignore_index=True)
    counts = output.groupby(["event_class", "event_year"])["relative_month"].nunique()
    if not counts.eq(len(RELATIVE_MONTHS)).all():
        raise ValueError("Incomplete event-aligned atmospheric sequence")
    return output


def integrate_zj(values_pw: pd.Series, times: pd.Series) -> float:
    days = pd.to_datetime(times).dt.days_in_month.to_numpy(dtype=float)
    return float(np.nansum(values_pw.to_numpy(dtype=float) * days * 86400.0 * 1.0e-6))


def event_phase_table(aligned: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (event_class, event_year), event in aligned.groupby(["event_class", "event_year"]):
        for phase, (lower, upper) in PHASES.items():
            selected = event.loc[event.relative_month.between(lower, upper)].sort_values("time")
            row = {
                "event_class": event_class,
                "event_year": int(event_year),
                "phase": phase,
                "east_h20_mean_zj": float(selected.east_h20_zj_sm3.mean()),
                "east_sst_mean_c": float(selected.oisst_east_sst_sm3.mean()),
                "east_precip_mean_mmday": float(selected.gpcp_east_precip_sm3.mean()),
                "central_precip_mean_mmday": float(selected.gpcp_central_precip_sm3.mean()),
                "slp_drive_mean_hpa": float(selected.era5_slp_drive_sm3.mean()),
                "tau5n_westward_mean_nm2": float(selected.era5_tau5n_westward_sm3_nm2.mean()),
                "ekman5n_north_mean_sv": float(selected.ekman5n_220_280e_north_sm3_sv.mean()),
                "curl_x_component_mean_1e8_nm3": float(
                    selected.minus_dtaux_dy_east_nh_sm3_1e8_nm3.mean()
                ),
                "soda_north_export_mean_pw": float(selected.soda_east_north_export_sm3_pw.mean()),
                "soda_north_export_zj": integrate_zj(selected.soda_east_north_export_sm3_pw, selected.time),
                "soda_surface_loss_zj": integrate_zj(selected.soda_east_surface_loss_sm3_pw, selected.time),
                "era5_qnet_loss_zj": integrate_zj(-selected.era5_east_qnet_sm3_pw, selected.time),
            }
            for component in FLUX_COMPONENTS:
                row[f"era5_{component}_loss_zj"] = integrate_zj(
                    -selected[f"era5_east_{component}_sm3_pw"], selected.time
                )
            for lon1 in (270, 275, 280):
                row[f"tau5n_220_{lon1}e_westward_mean_nm2"] = float(
                    -selected[f"tau5n_220_{lon1}e_sm3_nm2"].mean()
                )
            rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(events: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    metrics = [
        column
        for column in events.columns
        if column not in {"event_class", "event_year", "phase"}
    ]
    rows = []
    for phase in PHASES:
        phase_data = events.loc[events.phase.eq(phase)]
        groups = {key: phase_data.loc[phase_data.event_class.eq(key)] for key in ("CT", "CP")}
        for metric in metrics:
            samples: dict[str, np.ndarray] = {}
            for event_class, group in groups.items():
                values = group[metric].to_numpy(dtype=float)
                draw = rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))
                boot = values[draw].mean(axis=1)
                samples[event_class] = boot
                low, high = np.quantile(boot, [0.025, 0.975])
                rows.append(
                    {
                        "contrast": event_class,
                        "phase": phase,
                        "metric": metric,
                        "mean": float(values.mean()),
                        "ci_low": float(low),
                        "ci_high": float(high),
                        "ci_excludes_zero": bool(low > 0 or high < 0),
                    }
                )
            difference = samples["CT"] - samples["CP"]
            low, high = np.quantile(difference, [0.025, 0.975])
            rows.append(
                {
                    "contrast": "CT_minus_CP",
                    "phase": phase,
                    "metric": metric,
                    "mean": float(groups["CT"][metric].mean() - groups["CP"][metric].mean()),
                    "ci_low": float(low),
                    "ci_high": float(high),
                    "ci_excludes_zero": bool(low > 0 or high < 0),
                }
            )
    return pd.DataFrame(rows)


def block_bootstrap_correlation(frame: pd.DataFrame, x: str, y: str, block: str) -> tuple[float, float, float]:
    clean = frame[[block, x, y]].dropna()
    observed = float(stats.pearsonr(clean[x], clean[y]).statistic)
    groups = [group for _, group in clean.groupby(block)]
    rng = np.random.default_rng(RANDOM_SEED)
    values = []
    for _ in range(BOOTSTRAP_SAMPLES):
        draw = rng.integers(0, len(groups), len(groups))
        sample = pd.concat([groups[index] for index in draw], ignore_index=True)
        if sample[x].std() > 0 and sample[y].std() > 0:
            values.append(float(stats.pearsonr(sample[x], sample[y]).statistic))
    low, high = np.quantile(values, [0.025, 0.975])
    return observed, float(low), float(high)


def correlations(events: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    decay = events.loc[events.phase.eq("mature_decay_Dec0_to_May1")].copy()
    rows = []
    for lon1 in (270, 275, 280):
        x = f"tau5n_220_{lon1}e_westward_mean_nm2"
        r = float(stats.pearsonr(decay[x], decay.soda_north_export_zj).statistic)
        loo = []
        for index in decay.index:
            selected = decay.drop(index)
            loo.append(float(stats.pearsonr(selected[x], selected.soda_north_export_zj).statistic))
        rows.append(
            {
                "sample": "eight_events_decay",
                "x": x,
                "y": "soda_north_export_zj",
                "r": r,
                "ci_low": np.nan,
                "ci_high": np.nan,
                "leave_one_out_min": min(loo),
                "leave_one_out_max": max(loo),
                "n_blocks": len(decay),
            }
        )

    r = float(stats.pearsonr(decay.era5_qnet_loss_zj, decay.soda_surface_loss_zj).statistic)
    loo = []
    for index in decay.index:
        selected = decay.drop(index)
        loo.append(
            float(stats.pearsonr(selected.era5_qnet_loss_zj, selected.soda_surface_loss_zj).statistic)
        )
    rows.append(
        {
            "sample": "eight_events_decay",
            "x": "era5_qnet_loss_zj",
            "y": "soda_surface_loss_zj",
            "r": r,
            "ci_low": np.nan,
            "ci_high": np.nan,
            "leave_one_out_min": min(loo),
            "leave_one_out_max": max(loo),
            "n_blocks": len(decay),
        }
    )

    seasonal = monthly.loc[monthly.month.isin([12, 1, 2, 3, 4, 5])].copy()
    seasonal["season_year"] = np.where(seasonal.month.eq(12), seasonal.year, seasonal.year - 1)
    seasonal = seasonal.loc[seasonal.season_year.between(1982, 2021)]
    r, low, high = block_bootstrap_correlation(
        seasonal,
        "era5_tau5n_westward_sm3_nm2",
        "soda_east_north_export_sm3_pw",
        "season_year",
    )
    rows.append(
        {
            "sample": "all_years_Dec_to_May",
            "x": "era5_tau5n_westward_sm3_nm2",
            "y": "soda_east_north_export_sm3_pw",
            "r": r,
            "ci_low": low,
            "ci_high": high,
            "leave_one_out_min": np.nan,
            "leave_one_out_max": np.nan,
            "n_blocks": seasonal.season_year.nunique(),
        }
    )
    seasonal["era5_qnet_loss_sm3_pw"] = -seasonal.era5_east_qnet_sm3_pw
    r, low, high = block_bootstrap_correlation(
        seasonal,
        "era5_qnet_loss_sm3_pw",
        "soda_east_surface_loss_sm3_pw",
        "season_year",
    )
    rows.append(
        {
            "sample": "all_years_Dec_to_May",
            "x": "era5_qnet_loss_sm3_pw",
            "y": "soda_east_surface_loss_sm3_pw",
            "r": r,
            "ci_low": low,
            "ci_high": high,
            "leave_one_out_min": np.nan,
            "leave_one_out_max": np.nan,
            "n_blocks": seasonal.season_year.nunique(),
        }
    )
    return pd.DataFrame(rows)


def detrend_field(field: xr.DataArray) -> xr.DataArray:
    values = np.asarray(field.values, dtype=float)
    times = pd.DatetimeIndex(field.time.values)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in range(1, 13):
        indices = np.where(times.month == month)[0]
        years = np.asarray(times.year[indices], dtype=float)
        x = years - years.mean()
        selected = values[indices]
        mean = np.nanmean(selected, axis=0)
        slope = np.nansum(x[:, None, None] * (selected - mean), axis=0) / np.sum(x**2)
        output[indices] = selected - (mean[None, :, :] + x[:, None, None] * slope[None, :, :])
    return xr.DataArray(output, coords=field.coords, dims=field.dims, attrs=field.attrs)


def composite_decay_maps(fields: xr.Dataset) -> xr.Dataset:
    tau = detrend_field(fields.tau_x.sel(lat=slice(-10, 10), lon=slice(120, 280)))
    with xr.open_dataset(GPCP_NC, engine="netcdf4", chunks=None) as dataset:
        precip = dataset.precip.assign_coords(lon=(dataset.lon % 360.0)).sortby("lon").sortby("lat")
        precip = precip.sel(time=slice("1982-01-01", "2022-12-31"), lat=slice(-10, 10), lon=slice(120, 280)).load()
    precip = precip.assign_coords(time=normalize_time(precip.time.values))
    precip = detrend_field(precip)
    output = xr.Dataset()
    for event_class, years in EVENTS.items():
        dates = [
            pd.Timestamp(year=event_year + (1 if month <= 5 else 0), month=month, day=15)
            for event_year in years
            for month in (12, 1, 2, 3, 4, 5)
        ]
        output[f"precip_{event_class}"] = precip.sel(time=dates).mean("time")
        output[f"tau_x_{event_class}"] = tau.sel(time=dates).mean("time")
    output["precip_CT_minus_CP"] = output.precip_CT - output.precip_CP
    output["tau_x_CT_minus_CP"] = output.tau_x_CT - output.tau_x_CP
    output.attrs.update(
        {
            "period": "Dec(0)-May(+1)",
            "baseline": "calendar-month linear detrend 1982-2022",
            "precipitation_source": "GPCP v2.3 mm/day",
            "stress_source": "ERA5 mean eastward turbulent surface stress N m-2",
        }
    )
    return output


def monthly_composites(aligned: pd.DataFrame) -> pd.DataFrame:
    metrics = {
        "east_h20_zj_sm3": "east_h20",
        "gpcp_east_precip_sm3": "east_precip",
        "era5_tau5n_westward_sm3_nm2": "tau5n_westward",
        "soda_east_north_export_sm3_pw": "north_export",
    }
    rng = np.random.default_rng(RANDOM_SEED)
    rows = []
    for event_class in ("CT", "CP"):
        selected = aligned.loc[aligned.event_class.eq(event_class)]
        years = sorted(selected.event_year.unique())
        for relative_month in RELATIVE_MONTHS:
            month = selected.loc[selected.relative_month.eq(relative_month)].set_index("event_year")
            for column, metric in metrics.items():
                values = month.loc[years, column].to_numpy(dtype=float)
                draw = rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))
                boot = values[draw].mean(axis=1)
                low, high = np.quantile(boot, [0.025, 0.975])
                rows.append(
                    {
                        "event_class": event_class,
                        "relative_month": relative_month,
                        "metric": metric,
                        "mean": float(values.mean()),
                        "ci_low": float(low),
                        "ci_high": float(high),
                    }
                )
    return pd.DataFrame(rows)


def summary_row(summary: pd.DataFrame, contrast: str, phase: str, metric: str) -> pd.Series:
    return summary.loc[
        summary.contrast.eq(contrast) & summary.phase.eq(phase) & summary.metric.eq(metric)
    ].iloc[0]


def plot_sequence(composites: pd.DataFrame) -> None:
    setup_style()
    metrics = [
        ("east_h20", "Eastern H20 anomaly", "ZJ"),
        ("east_precip", "Eastern-Pacific rainfall anomaly", "mm day$^{-1}$"),
        ("tau5n_westward", "5°N westward stress anomaly", "N m$^{-2}$"),
        ("north_export", "SODA3 northward warm-heat export", "PW"),
    ]
    colors = {"CT": "#C23B3B", "CP": "#2C7FB8"}
    fig, axes = plt.subplots(4, 1, figsize=(8.2, 8.5), sharex=True, constrained_layout=True)
    for axis, (metric, title, unit) in zip(axes, metrics):
        for event_class in ("CT", "CP"):
            data = composites.loc[
                composites.event_class.eq(event_class) & composites.metric.eq(metric)
            ].sort_values("relative_month")
            axis.plot(data.relative_month, data["mean"], color=colors[event_class], lw=1.8, label=event_class)
            axis.fill_between(
                data.relative_month,
                data.ci_low,
                data.ci_high,
                color=colors[event_class],
                alpha=0.15,
                linewidth=0,
            )
        axis.axhline(0, color="0.35", lw=0.7)
        axis.axvspan(5, 10, color="#F1C75B", alpha=0.10)
        axis.axvspan(11, 16, color="#8AB6D6", alpha=0.10)
        axis.set_title(title, loc="left", fontweight="bold")
        axis.set_ylabel(unit)
        axis.grid(axis="y", color="0.9", lw=0.6)
    axes[0].legend(frameon=False, ncol=2, loc="upper left")
    axes[-1].set_xticks([0, 3, 6, 9, 12, 15])
    axes[-1].set_xticklabels(["Jan0", "Apr0", "Jul0", "Oct0", "Jan+1", "Apr+1"])
    axes[-1].set_xlabel("Event-relative month")
    fig.suptitle("CT and CP diverge after eastern-Pacific warm heat couples to the atmosphere", fontsize=13, fontweight="bold")
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(SEQUENCE_PNG, bbox_inches="tight")
    fig.savefig(SEQUENCE_PDF, bbox_inches="tight")
    plt.close(fig)


def plot_map_axis(axis, lon, lat, precip, tau, title: str, transform=None):
    kwargs = {} if transform is None else {"transform": transform}
    levels = np.arange(-6, 6.1, 1.0)
    filled = axis.contourf(lon, lat, precip, levels=levels, cmap="BrBG", extend="both", **kwargs)
    contour_levels = np.array([-0.012, -0.008, -0.004, 0.004, 0.008, 0.012])
    contours = axis.contour(lon, lat, tau, levels=contour_levels, colors="k", linewidths=0.7, **kwargs)
    axis.clabel(contours, fmt="%.3f", fontsize=6.2)
    axis.set_title(title, fontweight="bold")
    return filled


def plot_mechanism(maps: xr.Dataset, events: pd.DataFrame, summary: pd.DataFrame, correlations_frame: pd.DataFrame) -> None:
    setup_style()
    use_cartopy = ccrs is not None
    projection = ccrs.PlateCarree(central_longitude=180) if use_cartopy else None
    fig = plt.figure(figsize=(12.0, 7.0))
    layout = fig.add_gridspec(
        3,
        2,
        height_ratios=(0.72, 0.10, 2.15),
        left=0.07,
        right=0.98,
        bottom=0.09,
        top=0.91,
        hspace=0.72,
        wspace=0.11,
    )
    if use_cartopy:
        ax_ct = fig.add_subplot(layout[0, 0], projection=projection)
        ax_cp = fig.add_subplot(layout[0, 1], projection=projection)
        transform = ccrs.PlateCarree()
    else:
        ax_ct = fig.add_subplot(layout[0, 0])
        ax_cp = fig.add_subplot(layout[0, 1])
        transform = None
    ax_scatter = fig.add_subplot(layout[2, 0])
    ax_flux = fig.add_subplot(layout[2, 1])

    filled = None
    for axis, event_class in ((ax_ct, "CT"), (ax_cp, "CP")):
        filled = plot_map_axis(
            axis,
            maps[f"precip_{event_class}"].lon,
            maps[f"precip_{event_class}"].lat,
            maps[f"precip_{event_class}"],
            maps[f"tau_x_{event_class}"],
            f"{event_class}: rainfall shading + zonal stress contours",
            transform,
        )
        if use_cartopy:
            axis.set_extent([120, 280, -10, 10], crs=transform)
            axis.coastlines(linewidth=0.6)
            axis.add_feature(cfeature.LAND, facecolor="0.92", edgecolor="none")
            gridlines = axis.gridlines(draw_labels=True, linewidth=0.35, color="0.6", alpha=0.5)
            gridlines.top_labels = False
            gridlines.right_labels = False
        else:
            axis.set_xlim(120, 280)
            axis.set_ylim(-10, 10)
            axis.set_xlabel("Longitude (°E)")
            axis.set_ylabel("Latitude")
        axis.plot([220, 280, 280, 220, 220], [-10, -10, 5, 5, -10], color="#D62728", lw=1.1, **({} if transform is None else {"transform": transform}))
        axis.plot([220, 280], [5, 5], color="#D62728", lw=1.2, ls="--", **({} if transform is None else {"transform": transform}))
    color_axis = fig.add_subplot(layout[1, :])
    cbar = fig.colorbar(filled, cax=color_axis, orientation="horizontal")
    cbar.set_label("GPCP precipitation anomaly (mm day$^{-1}$); contours: ERA5 $\\tau_x$ (N m$^{-2}$)")

    decay = events.loc[events.phase.eq("mature_decay_Dec0_to_May1")]
    colors = {"CT": "#C23B3B", "CP": "#2C7FB8"}
    max_tau = float(decay.tau5n_westward_mean_nm2.max())
    for event_class in ("CT", "CP"):
        data = decay.loc[decay.event_class.eq(event_class)]
        ax_scatter.scatter(
            data.tau5n_westward_mean_nm2,
            data.soda_north_export_zj,
            s=42,
            color=colors[event_class],
            label=event_class,
            zorder=3,
        )
        for row in data.itertuples():
            if np.isclose(row.tau5n_westward_mean_nm2, max_tau):
                offset = (-22, 3)
            elif event_class == "CP":
                offset = (3, -10)
            else:
                offset = (3, 4)
            ax_scatter.annotate(
                str(row.event_year),
                (row.tau5n_westward_mean_nm2, row.soda_north_export_zj),
                xytext=offset,
                textcoords="offset points",
                fontsize=6.5,
            )
    x = decay.tau5n_westward_mean_nm2.to_numpy()
    y = decay.soda_north_export_zj.to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    xline = np.linspace(x.min(), x.max(), 100)
    ax_scatter.plot(xline, intercept + slope * xline, color="0.25", lw=1.1)
    r = correlations_frame.loc[
        correlations_frame["x"].eq("tau5n_220_280e_westward_mean_nm2"), "r"
    ].iloc[0]
    ax_scatter.text(0.03, 0.95, f"8-event r = {r:.2f}", transform=ax_scatter.transAxes, va="top", fontweight="bold")
    ax_scatter.axhline(0, color="0.5", lw=0.6)
    ax_scatter.axvline(0, color="0.5", lw=0.6)
    ax_scatter.set_xlabel("5°N east-box westward stress anomaly (N m$^{-2}$)")
    ax_scatter.set_ylabel("SODA3 northward warm-heat export (ZJ)")
    ax_scatter.set_title("Atmospheric stress and ocean heat export co-vary", fontweight="bold")
    ax_scatter.legend(frameon=False)
    ax_scatter.grid(color="0.9", lw=0.5)
    ax_scatter.margins(x=0.09, y=0.10)

    phase = "mature_decay_Dec0_to_May1"
    components = ["shortwave", "longwave", "latent", "sensible", "qnet"]
    labels = ["Shortwave", "Longwave", "Latent", "Sensible", "Net"]
    positions = np.arange(len(components))
    width = 0.36
    for offset, event_class in ((-width / 2, "CT"), (width / 2, "CP")):
        values = [summary_row(summary, event_class, phase, f"era5_{item}_loss_zj")["mean"] for item in components]
        lows = [summary_row(summary, event_class, phase, f"era5_{item}_loss_zj")["ci_low"] for item in components]
        highs = [summary_row(summary, event_class, phase, f"era5_{item}_loss_zj")["ci_high"] for item in components]
        errors = np.vstack([np.array(values) - np.array(lows), np.array(highs) - np.array(values)])
        ax_flux.bar(positions + offset, values, width, color=colors[event_class], alpha=0.85, label=event_class, yerr=errors, capsize=2)
    ax_flux.axhline(0, color="0.4", lw=0.7)
    ax_flux.set_xticks(positions)
    ax_flux.set_xticklabels(labels, rotation=20)
    ax_flux.set_ylabel("Cumulative ocean heat loss anomaly (ZJ)")
    ax_flux.set_title("Surface feedback: cloud shortwave and evaporation contribute", fontweight="bold")
    ax_flux.legend(frameon=False)
    ax_flux.grid(axis="y", color="0.9", lw=0.5)

    fig.suptitle("A coherent air-sea pathway for eastern-Pacific warm-heat fate", fontsize=14, fontweight="bold")
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(MECHANISM_PNG, bbox_inches="tight")
    fig.savefig(MECHANISM_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(summary: pd.DataFrame, correlations_frame: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    phase = "mature_decay_Dec0_to_May1"
    get = lambda contrast, metric: summary_row(summary, contrast, phase, metric)
    ct_precip = get("CT", "east_precip_mean_mmday")
    cp_precip = get("CP", "east_precip_mean_mmday")
    diff_precip = get("CT_minus_CP", "east_precip_mean_mmday")
    ct_tau = get("CT", "tau5n_westward_mean_nm2")
    cp_tau = get("CP", "tau5n_westward_mean_nm2")
    diff_tau = get("CT_minus_CP", "tau5n_westward_mean_nm2")
    ct_export = get("CT", "soda_north_export_zj")
    cp_export = get("CP", "soda_north_export_zj")
    diff_export = get("CT_minus_CP", "soda_north_export_zj")
    ct_qnet = get("CT", "era5_qnet_loss_zj")
    cp_qnet = get("CP", "era5_qnet_loss_zj")
    diff_qnet = get("CT_minus_CP", "era5_qnet_loss_zj")
    ct_soda_surface = get("CT", "soda_surface_loss_zj")
    cp_soda_surface = get("CP", "soda_surface_loss_zj")
    ct_sw = get("CT", "era5_shortwave_loss_zj")
    ct_lh = get("CT", "era5_latent_loss_zj")
    correlation = correlations_frame.loc[
        correlations_frame["x"].eq("tau5n_220_280e_westward_mean_nm2")
    ].iloc[0]
    background = correlations_frame.loc[
        correlations_frame["sample"].eq("all_years_Dec_to_May")
        & correlations_frame["x"].eq("era5_tau5n_westward_sm3_nm2")
    ].iloc[0]
    thermal_event = correlations_frame.loc[
        correlations_frame["sample"].eq("eight_events_decay")
        & correlations_frame["x"].eq("era5_qnet_loss_zj")
    ].iloc[0]
    thermal_background = correlations_frame.loc[
        correlations_frame["sample"].eq("all_years_Dec_to_May")
        & correlations_frame["x"].eq("era5_qnet_loss_sm3_pw")
    ].iloc[0]
    report = f"""# SODA3暖量去向的海气耦合闭环

## 要回答的问题

为什么CT厄尔尼诺在东太平洋暖量到达后，于Dec(0)–May(+1)出现显著的跨5°N北向暖量输出，而CP没有？本分析把同一组4个CT和4个CP事件的SODA3三箱H20收支，与OISST、GPCP和ERA5大气响应对齐。所有量按日历月在1982–2022线性去趋势，标量诊断再做中心3个月平均；不把单个月份当独立样本，置信区间以整事件bootstrap得到。

## 直接结果

1. **东部暖海温首先表现出不同的对流响应位置。** 衰减期东太平洋GPCP降水异常在CT为 {ct_precip['mean']:+.2f} mm/day且区间为正，在CP仅 {cp_precip['mean']:+.2f} mm/day且区间跨零；CT−CP为 {diff_precip['mean']:+.2f}，95%区间 [{diff_precip['ci_low']:+.2f}, {diff_precip['ci_high']:+.2f}]。这个组间降水差异非常接近但尚未越过95%门槛，应该写成机制线索；空间图显示CP增强主要偏中太平洋，而CT把对流响应带入东部。

2. **东部大气响应在5°N产生了正确方向的动力出口。** 以向西风应力为正，CT/CP在140°W–80°W、4°–6°N的异常分别为 {ct_tau['mean']:+.4f}/{cp_tau['mean']:+.4f} N/m²；CT−CP为 {diff_tau['mean']:+.4f}，区间 [{diff_tau['ci_low']:+.4f}, {diff_tau['ci_high']:+.4f}]。北半球中，异常向西风应力对应向北Ekman输送，方向与SODA3跨5°N暖量输出一致。

3. **海洋出口与大气风应力不是仅仅“看起来同时”。** SODA3累计北向暖量输出在CT/CP中分别为 {ct_export['mean']:+.2f}/{cp_export['mean']:+.2f} ZJ；CT−CP为 {diff_export['mean']:+.2f} ZJ，区间 [{diff_export['ci_low']:+.2f}, {diff_export['ci_high']:+.2f}]。8个事件的5°N向西风应力与北向暖量输出相关为 r={correlation['r']:.2f}，逐一删除任一事件后范围仍为 {correlation['leave_one_out_min']:.2f}–{correlation['leave_one_out_max']:.2f}。在全部1982–2022年Dec–May月份中，按季节年block bootstrap的相关为 r={background['r']:.2f}，95%区间 [{background['ci_low']:.2f}, {background['ci_high']:.2f}]。

4. **热力反馈与动力出口同时存在，而且得到独立产品复核。** ERA5东部箱体净向下表面热通量异常换算成海洋热损失，CT/CP分别为 {ct_qnet['mean']:+.2f}/{cp_qnet['mean']:+.2f} ZJ，CT−CP为 {diff_qnet['mean']:+.2f} ZJ，区间 [{diff_qnet['ci_low']:+.2f}, {diff_qnet['ci_high']:+.2f}]；SODA3对应值为 {ct_soda_surface['mean']:+.2f}/{cp_soda_surface['mean']:+.2f} ZJ。8事件ERA5与SODA3热损失相关为 r={thermal_event['r']:.2f}；全部Dec–May月份的季节年block-bootstrap相关为 r={thermal_background['r']:.2f}，区间 [{thermal_background['ci_low']:.2f}, {thermal_background['ci_high']:.2f}]。CT中主要来自短波减少 {ct_sw['mean']:+.2f} ZJ和潜热散失 {ct_lh['mean']:+.2f} ZJ：前者与增强云对流一致，后者与风速/蒸发反馈一致；其中CT−CP的短波差异显著，潜热差异本身未越过95%门槛。

## 机制收束

当前证据支持的闭环是：

**CT更深、更靠东的暖量储存 → 东太平洋SST与对流增强 → 东部5°N异常东风/向西风应力与压力场调整 → Ekman和地转共同形成北向暖量出口 → 同时由云短波和潜热通量加强海洋散热。**

CP并非不耦合，而是对流和风应力响应中心偏在中太平洋，没有在东部5°N形成同强度、同方向的动力出口；因此到达东部后的暖量分配不同。

## 后续动力分解（已完成）

SODA3温盐、SSH、总v和自身风应力的5°N逐月分解表明：不平滑的CT/CP总北向Q20为 +2.77/−1.00 ZJ，与这里的三个月平滑结果一致；CT−CP总差异 +3.77 ZJ可分为地转 +2.10 ZJ、Ekman +1.77 ZJ和不显著残差 −0.10 ZJ。CT组自身显著的北向项是Ekman（+2.18 ZJ），而地转组间差异主要来自CP显著的南向地转异常（−1.23 ZJ）。SODA3自身应力给出的CT−CP Ekman差异 +1.77 ZJ也与独立ERA5估算 +1.67 ZJ一致。完整方法和边界/EOS敏感性见 `outputs/research_2026/soda3_5n_current_decomposition/SODA3_5N_CURRENT_DECOMPOSITION_CN.md`。

未平滑的逐月时序进一步显示：Dec(0)先出现东部H20和降水差异，Jan(+1)东部SST与总Q20差异可辨识，Feb西向风应力及Ekman/地转Q20均显著为正，Mar风驱出口仍持续。详见 `outputs/research_2026/soda3_5n_coupled_timing/SODA3_5N_COUPLED_TIMING_CN.md`。

## 不能越过的证据边界

- 后续ERA5经向应力已补齐；完整风应力旋度确认CT−CP为正，且纬向应力梯度仍是主贡献。
- 事件样本只有4+4。事件级关系很稳健，但类型差异仍可能混入事件强度；地图和相关支持机制，不替代耦合模式敏感性试验。
- 后续SODA3运动学分解已经闭合总量；但地转压力场本身也响应风和热力过程，因此地转与Ekman项不能被解释为彼此独立的因果强迫。
- ERA5表面通量为正向下；本文“热损失”已统一取负号。SODA3与ERA5通量产品不同，只用于独立物理核验，不强制逐月完全相等。

## QA

- 合并月份：{diagnostics['n_months']}；事件：{diagnostics['n_events']}；
- 5°N边界西端固定140°W，东端分别用90°W、85°W、80°W；8事件相关范围 {diagnostics['tau_boundary_correlation_min']:.3f}–{diagnostics['tau_boundary_correlation_max']:.3f}；
- ERA5净通量恒等于短波、长波、潜热和感热之和，最大误差 {diagnostics['qnet_component_identity_max_pw']:.2e} PW；
- GPCP与ERA5地图均使用相同1982–2022按月去趋势基准。
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> int:
    fields = load_era5_fields()
    monthly = build_monthly(fields)
    aligned = event_align(monthly)
    events = event_phase_table(aligned)
    summary = bootstrap_summary(events)
    correlations_frame = correlations(events, monthly)
    maps = composite_decay_maps(fields)
    composites = monthly_composites(aligned)

    qnet_identity = (
        monthly.era5_east_qnet_sm3_pw
        - monthly[[f"era5_east_{item}_sm3_pw" for item in FLUX_COMPONENTS]].sum(axis=1)
    ).abs().max()
    event_correlations = correlations_frame.loc[
        correlations_frame["sample"].eq("eight_events_decay")
        & correlations_frame["x"].str.startswith("tau5n_220_"),
        "r",
    ]
    diagnostics = {
        "baseline": list(BASELINE),
        "events": EVENTS,
        "n_months": int(len(monthly)),
        "n_events": int(events[["event_class", "event_year"]].drop_duplicates().shape[0]),
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "qnet_component_identity_max_pw": float(qnet_identity),
        "tau_boundary_correlation_min": float(event_correlations.min()),
        "tau_boundary_correlation_max": float(event_correlations.max()),
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    aligned.to_csv(EVENT_MONTHLY_CSV, index=False, float_format="%.9g")
    events.to_csv(EVENT_PHASE_CSV, index=False, float_format="%.9g")
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.9g")
    correlations_frame.to_csv(CORRELATION_CSV, index=False, float_format="%.9g")
    maps.to_netcdf(MAP_NC, engine="netcdf4")
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    plot_sequence(composites)
    plot_mechanism(maps, events, summary, correlations_frame)
    write_report(summary, correlations_frame, diagnostics)
    for path in (
        MONTHLY_CSV,
        EVENT_PHASE_CSV,
        SUMMARY_CSV,
        CORRELATION_CSV,
        MAP_NC,
        MECHANISM_PNG,
        SEQUENCE_PNG,
        REPORT_MD,
    ):
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
