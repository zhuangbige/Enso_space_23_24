#!/usr/bin/env python3
"""Build an ordinary-El-Nino benchmark and actual-versus-expected diagnostics.

The main reference is an equal-event January-June composite of non-extreme
NOAA ONI warm episodes whose developing years fall in 1982-2014.  Extreme
events and all three target cases (2015/16, 2023/24, and 2026) are excluded.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
import urllib.request
from pathlib import Path
from types import ModuleType

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from el_nino_decoupling.typical_composite import (  # noqa: E402
    bootstrap_mean_ci,
    composite_fields,
    difference_fields,
    fit_expected_response,
    identify_warm_episodes,
    ordinary_event_manifest,
    read_oni_ascii,
    weighted_taylor_statistics,
)


NOAA_ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
BASELINE_START = 1980
BASELINE_END = 2014
BASELINE_TAG = "1980_2014"
SST_BASELINE_START = 1982
FIT_START = 1982
FIT_END = 2014
TARGET_YEARS = (2015, 2023, 2026)
TARGET_LABELS = {2015: "2015/16", 2023: "2023/24", 2026: "2026 developing state"}
MONTHS = tuple(range(1, 7))
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
EXPECTED_RESPONSES = (
    ("cwp_u10", "Peng CWP u10", "m s$^{-1}$"),
    ("cp_precip", "CP precipitation", "mm day$^{-1}$"),
)

INPUT_DIR = ROOT / "data/interim/research_2026/monthly_panel_inputs"
OUT_DIR = ROOT / "outputs/research_2026/revised_event_figures"
MANIFEST_CSV = OUT_DIR / "ordinary_el_nino_event_manifest.csv"
BOOTSTRAP_CSV = OUT_DIR / "ordinary_el_nino_bootstrap_summary.csv"
EXPECTED_CSV = OUT_DIR / "ordinary_el_nino_expected_response.csv"
TARGET_COMPARISON_CSV = OUT_DIR / "ordinary_el_nino_target_comparison.csv"
EP_CP_CSV = OUT_DIR / "ordinary_el_nino_ep_cp_sensitivity.csv"
SIMILARITY_CSV = OUT_DIR / "event_2026_taylor_similarity_to_2015_2023.csv"
PENG_CWP_U10_CSV = OUT_DIR / "peng_cwp_u10_monthly_detrended_1982_2014.csv"
COMPOSITE_NPZ = INPUT_DIR / f"monthly_ordinary_el_nino_composite_detrended_fields_{BASELINE_TAG}.npz"
PENG_CWP_U10_DIR = ROOT / "data/raw/era5/peng_cwp_u10_monthly_1deg"
PENG_CWP_BOX = (-5.0, 5.0, 140.0, 200.0)
ERA5_U10_HISTORY = ROOT / "data/raw/era5/era5_monthly_10m_wind_pmm_1deg_1982_2025.nc"
ERA5_U10_2026_JAN_MAY = ROOT / "data/raw/era5/era5_monthly_10m_wind_pmm_1deg_2026_jan_may.nc"


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load script module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oni-path", type=Path, help="Local NOAA oni.ascii.txt snapshot; fetched from CPC when omitted")
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--dry-run-events", action="store_true", help="Print the deterministic event selection and stop")
    return parser.parse_args()


def load_oni(path: Path | None) -> tuple[pd.DataFrame, str]:
    if path is not None:
        return read_oni_ascii(path), str(path)
    with urllib.request.urlopen(NOAA_ONI_URL, timeout=30) as response:  # noqa: S310 - fixed NOAA URL
        payload = response.read()
    with tempfile.NamedTemporaryFile(suffix="_oni.ascii.txt") as handle:
        handle.write(payload)
        handle.flush()
        return read_oni_ascii(handle.name), NOAA_ONI_URL


def load_npz(path: Path) -> dict[str, object]:
    with np.load(path) as archive:
        return {key: archive[key] for key in archive.files}


def ensure_event_fields(years: list[int], monthly_builder: ModuleType) -> dict[int, dict[str, object]]:
    fields: dict[int, dict[str, object]] = {}
    for year in sorted(set(years).union(TARGET_YEARS)):
        path = INPUT_DIR / f"monthly_{year}_detrended_fields_{BASELINE_TAG}.npz"
        needs_build = not path.exists()
        if not needs_build:
            with np.load(path) as archive:
                needs_build = len(archive["month_numbers"]) != len(MONTHS)
        if needs_build:
            monthly_builder.configure_run(
                year,
                f"El Nino {year}/{str(year + 1)[-2:]} development year",
                "outputs/research_2026/revised_event_figures/intermediate",
                BASELINE_START,
                BASELINE_END,
            )
            monthly_builder.build_fields()
        fields[year] = load_npz(path)
    return fields


def area_mean(field: np.ndarray, lat: np.ndarray, lon: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray:
    lat0, lat1, lon0, lon1 = box
    lat_mask = (lat >= lat0) & (lat <= lat1)
    lon_mask = (lon >= lon0) & (lon <= lon1)
    if not lat_mask.any() or not lon_mask.any():
        raise ValueError(f"Empty regional selection for box={box}")
    subset = field[:, lat_mask, :][:, :, lon_mask]
    weights = np.cos(np.deg2rad(lat[lat_mask]))
    numerator = np.nansum(subset * weights[None, :, None], axis=(1, 2))
    denominator = np.sum(np.isfinite(subset) * weights[None, :, None], axis=(1, 2))
    return np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=denominator > 0)


def event_metrics(
    fields: dict[str, object],
    *,
    event_year: int,
    cwp_u10: pd.Series,
) -> dict[str, np.ndarray]:
    lat = np.asarray(fields["lat"], dtype=float)
    lon = np.asarray(fields["lon"], dtype=float)
    sst_lat = np.asarray(fields["sst_lat"], dtype=float)
    sst_lon = np.asarray(fields["sst_lon"], dtype=float)
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    east_mask = (d20_lon >= 220) & (d20_lon <= 275)
    cwp_periods = [pd.Period(f"{event_year}-{month:02d}", freq="M") for month in MONTHS]
    cwp_values = np.asarray([cwp_u10.get(period, np.nan) for period in cwp_periods], dtype=float)
    if not np.isfinite(cwp_values).all():
        raise ValueError(f"Incomplete Peng CWP u10 series for January-June {event_year}")
    return {
        "nino3_sst": area_mean(np.asarray(fields["sst"], dtype=float), sst_lat, sst_lon, (-5, 5, 210, 270)),
        "cwp_u10": cwp_values,
        "cp_precip": area_mean(np.asarray(fields["precip"], dtype=float), lat, lon, (-5, 5, 180, 220)),
        "east_d20": np.nanmean(np.asarray(fields["d20"], dtype=float)[:, east_mask], axis=1),
    }


METRIC_UNITS = {
    "nino3_sst": "deg C",
    "cwp_u10": "m/s",
    "cp_precip": "mm/day",
    "east_d20": "m",
}


def bootstrap_tables(
    fields_by_year: dict[int, dict[str, object]],
    manifest: pd.DataFrame,
    *,
    cwp_u10: pd.Series,
    n_bootstrap: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    groups = {"ALL": manifest["event_year"].astype(int).tolist()}
    for event_type in ("EP", "CP"):
        groups[event_type] = manifest.loc[manifest["ep_cp_type"].eq(event_type), "event_year"].astype(int).tolist()

    rows: list[dict[str, object]] = []
    target_rows: list[dict[str, object]] = []
    for group, years in groups.items():
        if not years:
            continue
        metrics_by_year = {
            year: event_metrics(fields_by_year[year], event_year=year, cwp_u10=cwp_u10) for year in years
        }
        for metric in METRIC_UNITS:
            values = np.stack([metrics_by_year[year][metric] for year in years], axis=0)
            for month_index, month_label in enumerate(MONTH_LABELS):
                center, lower, upper = bootstrap_mean_ci(
                    values[:, month_index], n_bootstrap=n_bootstrap, seed=seed + month_index
                )
                rows.append(
                    {
                        "group": group,
                        "metric": metric,
                        "period": month_label,
                        "n_events": len(years),
                        "mean": float(center),
                        "ci_2.5": float(lower),
                        "ci_97.5": float(upper),
                        "unit": METRIC_UNITS[metric],
                        "bootstrap_replicates": n_bootstrap,
                        "seed": seed + month_index,
                    }
                )
            event_means = np.nanmean(values, axis=1)
            center, lower, upper = bootstrap_mean_ci(event_means, n_bootstrap=n_bootstrap, seed=seed + 100)
            rows.append(
                {
                    "group": group,
                    "metric": metric,
                    "period": "Jan-Jun",
                    "n_events": len(years),
                    "mean": float(center),
                    "ci_2.5": float(lower),
                    "ci_97.5": float(upper),
                    "unit": METRIC_UNITS[metric],
                    "bootstrap_replicates": n_bootstrap,
                    "seed": seed + 100,
                }
            )

    all_summary = pd.DataFrame(rows)
    ordinary = all_summary.loc[all_summary["group"].eq("ALL") & all_summary["period"].eq("Jan-Jun")]
    ordinary_lookup = ordinary.set_index("metric")
    for target_year in TARGET_YEARS:
        metrics = event_metrics(fields_by_year[target_year], event_year=target_year, cwp_u10=cwp_u10)
        for metric, monthly in metrics.items():
            target_mean = float(np.nanmean(monthly))
            reference = ordinary_lookup.loc[metric]
            target_rows.append(
                {
                    "target_year": target_year,
                    "target_label": TARGET_LABELS[target_year],
                    "metric": metric,
                    "target_jan_jun_mean": target_mean,
                    "ordinary_mean": float(reference["mean"]),
                    "target_minus_ordinary": target_mean - float(reference["mean"]),
                    "ordinary_ci_2.5": float(reference["ci_2.5"]),
                    "ordinary_ci_97.5": float(reference["ci_97.5"]),
                    "outside_bootstrap_ci_of_ordinary_mean": bool(
                        target_mean < float(reference["ci_2.5"]) or target_mean > float(reference["ci_97.5"])
                    ),
                    "unit": METRIC_UNITS[metric],
                }
            )
    return all_summary, pd.DataFrame(target_rows)


def published_ep_cp_assignments(event_years: list[int]) -> pd.DataFrame:
    """Use the observed event categories in Beniche et al. (2024) Fig. S4.

    Yan et al. (2025) motivates testing EP/CP rainfall sensitivity but uses
    continuous EOF regressions rather than a discrete observed event list.
    Beniche et al. supplies the required published CT/WP event assignments.
    """

    published = {
        1986: "EP",
        1991: "EP",
        2006: "EP",
        1994: "CP",
        2002: "CP",
        2004: "CP",
        2009: "CP",
    }
    missing = sorted(set(event_years).difference(published))
    if missing:
        raise ValueError(f"No published Beniche et al. EP/CP assignment for ordinary events: {missing}")
    return pd.DataFrame(
        [
            {
                "event_year": year,
                "mature_djf_year": year + 1,
                "ep_cp_type": published[year],
                "classification_method": (
                    "Published Cold Tongue/Warm Pool event category from Beniche et al. (2024), Supplementary Fig. S4"
                ),
                "classification_source": "https://doi.org/10.1038/s41598-024-52580-9",
            }
            for year in event_years
        ]
    )


def weighted_area_mean_da(da: xr.DataArray, box: tuple[float, float, float, float]) -> pd.Series:
    lat0, lat1, lon0, lon1 = box
    subset = da.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    weights = np.cos(np.deg2rad(subset["lat"]))
    mean = subset.weighted(weights).mean(("lat", "lon"), skipna=True)
    index = pd.PeriodIndex(pd.to_datetime(mean["time"].values), freq="M")
    return pd.Series(mean.values.astype(float), index=index).sort_index()


def detrend_monthly_series(series: pd.Series, *, baseline_start: int, baseline_end: int) -> pd.Series:
    output = pd.Series(index=series.index, dtype=float)
    for month in MONTHS:
        subset = series.loc[series.index.month == month].dropna()
        years = subset.index.year.astype(float)
        fit = (years >= baseline_start) & (years <= baseline_end)
        if int(fit.sum()) < 10:
            raise ValueError(f"Too few baseline years for month {month}")
        anomaly = subset.to_numpy(dtype=float) - float(subset.iloc[np.where(fit)[0]].mean())
        time = years + (month - 0.5) / 12.0
        slope, intercept = np.polyfit(time[fit], anomaly[fit], 1)
        output.loc[subset.index] = anomaly - (slope * time + intercept)
    return output.sort_index()


def load_peng_cwp_u10_series() -> pd.Series:
    """Load and detrend ERA5 u10 over Peng et al.'s exact CWP definition."""

    def read_u10(path: Path) -> xr.DataArray:
        if not path.exists():
            raise FileNotFoundError(path)
        dataset = xr.open_dataset(path, engine="h5netcdf")
        rename = {}
        if "valid_time" in dataset.coords:
            rename["valid_time"] = "time"
        if "latitude" in dataset.coords:
            rename["latitude"] = "lat"
        if "longitude" in dataset.coords:
            rename["longitude"] = "lon"
        dataset = dataset.rename(rename)
        field = (
            dataset["u10"]
            .assign_coords(lon=(dataset["lon"] % 360))
            .sortby("lat")
            .sortby("lon")
            .reset_coords(drop=True)
            .load()
        )
        dataset.close()
        return field

    history = read_u10(ERA5_U10_HISTORY)
    history = history.isel(time=history["time"].dt.month.isin(MONTHS))
    current = read_u10(ERA5_U10_2026_JAN_MAY)

    june_pieces = [
        read_u10(PENG_CWP_U10_DIR / f"era5_peng_cwp_{area_label}_m06_2026_2026_1p0deg.nc")
        for area_label in ("part01", "part02")
    ]
    june = xr.concat(june_pieces, dim="lon").sortby("lon")
    longitude = np.asarray(june["lon"].values, dtype=float)
    _, unique_indices = np.unique(longitude, return_index=True)
    june = june.isel(lon=np.sort(unique_indices))

    regional_fields = []
    for field in (history, current, june):
        regional_fields.append(field.sel(lat=slice(PENG_CWP_BOX[0], PENG_CWP_BOX[1]), lon=slice(PENG_CWP_BOX[2], PENG_CWP_BOX[3])))
    cwp_field = xr.concat(regional_fields, dim="time").sortby("time")
    periods = pd.PeriodIndex(pd.to_datetime(cwp_field["time"].values), freq="M")
    if periods.duplicated().any():
        raise ValueError("Duplicate calendar months in Peng CWP ERA5 inputs")
    expected_periods = pd.PeriodIndex(
        [f"{year}-{month:02d}" for year in range(1982, 2027) for month in MONTHS], freq="M"
    )
    missing = expected_periods.difference(periods)
    if len(missing):
        raise ValueError(f"Missing Peng CWP ERA5 months: {missing.astype(str).tolist()}")

    raw = weighted_area_mean_da(cwp_field, PENG_CWP_BOX)
    return detrend_monthly_series(raw, baseline_start=FIT_START, baseline_end=BASELINE_END)


def expected_response_table(monthly_builder: ModuleType, *, cwp_u10: pd.Series) -> pd.DataFrame:
    sst = monthly_builder.open_oisst()
    era5 = monthly_builder.open_era5()
    nino3 = detrend_monthly_series(
        weighted_area_mean_da(sst, (-5, 5, 210, 270)), baseline_start=SST_BASELINE_START, baseline_end=BASELINE_END
    )
    responses = {
        "cwp_u10": cwp_u10,
        "cp_precip": detrend_monthly_series(
            weighted_area_mean_da(era5["precip_mm_day"], (-5, 5, 180, 220)),
            baseline_start=BASELINE_START,
            baseline_end=BASELINE_END,
        ),
    }
    rows: list[dict[str, object]] = []
    for response_key, response in responses.items():
        for month in MONTHS:
            train_periods = [pd.Period(f"{year}-{month:02d}", freq="M") for year in range(FIT_START, FIT_END + 1)]
            x_train = np.asarray([nino3.get(period, np.nan) for period in train_periods], dtype=float)
            y_train = np.asarray([response.get(period, np.nan) for period in train_periods], dtype=float)
            for target_year in TARGET_YEARS:
                target_period = pd.Period(f"{target_year}-{month:02d}", freq="M")
                result = fit_expected_response(
                    x_train,
                    y_train,
                    float(nino3.loc[target_period]),
                    float(response.loc[target_period]),
                )
                rows.append(
                    {
                        "target_year": target_year,
                        "target_label": TARGET_LABELS[target_year],
                        "month": month,
                        "month_label": MONTH_LABELS[month - 1],
                        "response": response_key,
                        "unit": METRIC_UNITS[response_key],
                        **result,
                        "fit_years": f"{FIT_START}-{FIT_END}",
                        "target_excluded_from_fit": True,
                    }
                )
    return pd.DataFrame(rows)


def analog_similarity_table(fields_by_year: dict[int, dict[str, object]]) -> pd.DataFrame:
    """Compare 2026 with 2015 and 2023 using standard Taylor statistics.

    Each physical layer is evaluated independently over January-June.  No
    cross-variable score or hand-tuned layer weighting is constructed.
    """

    target = fields_by_year[2026]
    specifications = (
        ("sst", "Tropical-Pacific SST", "deg C", "10S-10N, 120E-80W"),
        ("u850", "850 hPa zonal wind", "m/s", "10S-10N, 120E-80W"),
        ("precip", "Precipitation", "mm/day", "10S-10N, 120E-80W"),
        ("d20", "Equatorial D20", "m", "equator, 130E-85W"),
    )
    rows: list[dict[str, object]] = []
    for variable, layer, unit, domain in specifications:
        if variable == "sst":
            lat = np.asarray(target["sst_lat"], dtype=float)
            lon = np.asarray(target["sst_lon"], dtype=float)
            lat_mask = (lat >= -10) & (lat <= 10)
            lon_mask = (lon >= 120) & (lon <= 280)
            reference = np.asarray(target[variable], dtype=float)[:, lat_mask, :][:, :, lon_mask]
            weights = np.broadcast_to(np.cos(np.deg2rad(lat[lat_mask]))[None, :, None], reference.shape)
        elif variable in {"u850", "precip"}:
            lat = np.asarray(target["lat"], dtype=float)
            lon = np.asarray(target["lon"], dtype=float)
            lat_mask = (lat >= -10) & (lat <= 10)
            lon_mask = (lon >= 120) & (lon <= 280)
            reference = np.asarray(target[variable], dtype=float)[:, lat_mask, :][:, :, lon_mask]
            weights = np.broadcast_to(np.cos(np.deg2rad(lat[lat_mask]))[None, :, None], reference.shape)
        else:
            lon = np.asarray(target["d20_lon"], dtype=float)
            lon_mask = (lon >= 130) & (lon <= 275)
            reference = np.asarray(target[variable], dtype=float)[:, lon_mask]
            weights = np.ones_like(reference)

        for candidate_year in (2015, 2023):
            candidate_fields = fields_by_year[candidate_year]
            if variable == "sst":
                candidate = np.asarray(candidate_fields[variable], dtype=float)[:, lat_mask, :][:, :, lon_mask]
            elif variable in {"u850", "precip"}:
                candidate = np.asarray(candidate_fields[variable], dtype=float)[:, lat_mask, :][:, :, lon_mask]
            else:
                candidate = np.asarray(candidate_fields[variable], dtype=float)[:, lon_mask]
            statistics = weighted_taylor_statistics(reference, candidate, weights)
            rows.append(
                {
                    "reference_year": 2026,
                    "candidate_year": candidate_year,
                    "candidate_label": TARGET_LABELS[candidate_year],
                    "period": "January-June",
                    "layer": layer,
                    "variable": variable,
                    "domain": domain,
                    "unit": unit,
                    **statistics,
                    "method": (
                        "Taylor (2001) area-weighted pattern comparison pooled over six calendar months; "
                        "correlation, centered RMSD, and standard-deviation ratio reported separately"
                    ),
                }
            )
    return pd.DataFrame(rows)


def format_lon(value: float) -> str:
    longitude = value % 360
    if np.isclose(longitude, 180):
        return "180"
    if longitude < 180:
        return f"{longitude:g}E"
    return f"{360 - longitude:g}W"


def equatorial_mean(field: np.ndarray, lat: np.ndarray) -> np.ndarray:
    mask = (lat >= -5) & (lat <= 5)
    weights = np.cos(np.deg2rad(lat[mask]))
    values = np.asarray(field, dtype=float)[:, mask, :]
    numerator = np.nansum(values * weights[None, :, None], axis=1)
    denominator = np.sum(np.isfinite(values) * weights[None, :, None], axis=1)
    return np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=denominator > 0)


def add_wind_contours(ax, lon: np.ndarray, months: np.ndarray, wind: np.ndarray) -> None:
    levels = [-4, -2, -1, 1, 2, 4]
    contour = ax.contour(lon, months, wind, levels=levels, colors="black", linewidths=0.85)
    ax.clabel(contour, fmt="%g", fontsize=7.8, inline=True)


def plot_difference_hovmoller(
    difference: dict[str, object],
    plot_module: ModuleType,
    *,
    target_year: int,
) -> None:
    plot_module.setup_style()
    import matplotlib.pyplot as plt

    lon = np.asarray(difference["lon"], dtype=float)
    lat = np.asarray(difference["lat"], dtype=float)
    sst_lon = np.asarray(difference["sst_lon"], dtype=float)
    sst_lat = np.asarray(difference["sst_lat"], dtype=float)
    d20_lon = np.asarray(difference["d20_lon"], dtype=float)
    months = np.arange(1, 7, dtype=float)
    u_eq = equatorial_mean(np.asarray(difference["u850"], dtype=float), lat)
    sst_eq = equatorial_mean(np.asarray(difference["sst"], dtype=float), sst_lat)
    precip_eq = equatorial_mean(np.asarray(difference["precip"], dtype=float), lat)
    d20 = np.asarray(difference["d20"], dtype=float)
    u_sst = np.asarray([np.interp(sst_lon, lon, row) for row in u_eq])
    u_d20 = np.asarray([np.interp(d20_lon, lon, row) for row in u_eq])

    fig, axes = plt.subplots(3, 1, figsize=(13.6, 7.9), constrained_layout=True)
    target_label = "2026" if target_year == 2026 else TARGET_LABELS[target_year]
    fig.suptitle(f"{target_label} minus ordinary El Niño: January-June departures", fontsize=17, weight="bold")
    panels = [
        (axes[0], sst_lon, sst_eq, u_sst, "Niño-belt SST difference", "RdBu_r", -2.0, 2.0, "deg C"),
        (axes[1], lon, precip_eq, u_eq, "Equatorial precipitation difference", "BrBG", -5.0, 5.0, "mm day$^{-1}$"),
        (axes[2], d20_lon, d20, u_d20, "Equatorial D20 difference", "RdBu_r", -35.0, 35.0, "m"),
    ]
    for panel_index, (ax, xlon, field, wind, title, cmap, vmin, vmax, unit) in enumerate(panels):
        mesh = ax.pcolormesh(xlon, months, field, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
        add_wind_contours(ax, xlon, months, wind)
        ax.set_yticks(months)
        ax.set_yticklabels(MONTH_LABELS)
        ax.invert_yaxis()
        ax.set_xlim(float(xlon.min()), float(xlon.max()))
        ax.set_title(f"{chr(97 + panel_index)}. {title}", loc="left", fontsize=13.2, weight="bold")
        ax.set_ylabel("Development month")
        ax.grid(False)
        cbar = fig.colorbar(mesh, ax=ax, orientation="vertical", pad=0.012, shrink=0.93)
        cbar.set_label(unit)
    ticks = [130, 160, 180, 220, 260, 275]
    for ax in axes:
        ax.set_xticks(ticks)
        ax.set_xticklabels([format_lon(tick) for tick in ticks])
        ax.set_xlabel("Longitude")
        ax.text(
            0.995,
            0.04,
            "Black contours: u850 difference (m s$^{-1}$)",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=8.7,
            bbox={"facecolor": "white", "edgecolor": "0.75", "alpha": 0.88, "pad": 2.0},
        )
    fig.text(
        0.01,
        -0.012,
        f"Differences are January-June {target_year} minus the seven-event ordinary composite. Negative u850 contours denote a weaker westerly or stronger easterly response.",
        fontsize=9.4,
        color="0.28",
    )
    plot_module.save(fig, f"fig_{target_year}_minus_ordinary_el_nino_hovmoller_detrended_1980_2014")
    plt.close(fig)


def plot_2026_staged_coupling(
    fields: dict[str, object],
    expected: pd.DataFrame,
    cwp_u10_series: pd.Series,
    plot_module: ModuleType,
) -> None:
    """Plot the observed 2026 ocean-to-atmosphere sequence in physical units."""

    plot_module.setup_style()
    import matplotlib.pyplot as plt

    metrics = event_metrics(fields, event_year=2026, cwp_u10=cwp_u10_series)
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    d20 = np.asarray(fields["d20"], dtype=float)
    west_d20 = np.nanmean(d20[:, (d20_lon >= 130) & (d20_lon <= 180)], axis=1)
    east_d20 = np.nanmean(d20[:, (d20_lon >= 220) & (d20_lon <= 275)], axis=1)
    u10 = expected.loc[
        expected["target_year"].eq(2026) & expected["response"].eq("cwp_u10")
    ].sort_values("month")
    precipitation = expected.loc[
        expected["target_year"].eq(2026) & expected["response"].eq("cp_precip")
    ].sort_values("month")

    fig, axes = plt.subplots(4, 1, figsize=(13.6, 7.8), sharex=True, constrained_layout=True)
    fig.suptitle("2026 January-June: observed sequence of tropical Pacific coupling", fontsize=17, weight="bold")
    stage_bands = (
        (0.5, 2.5, "#eaf3f8", "Jan-Feb: SST-wind mismatch"),
        (2.5, 4.5, "#fbf0e3", "Mar-Apr: westerly strengthening"),
        (4.5, 6.5, "#eaf5ea", "May-Jun: convective recovery"),
    )
    for axis in axes:
        axis.axhline(0, color="0.55", lw=0.8)
        for left, right, color, _label in stage_bands:
            axis.axvspan(left, right, color=color, zorder=0)
        axis.grid(True, axis="y", color="0.88", lw=0.6)
        axis.set_xlim(0.7, 6.3)

    axes[0].plot(MONTHS, west_d20, color="#3976a8", marker="o", lw=2.0, label="Western D20")
    axes[0].plot(MONTHS, east_d20, color="#c55448", marker="o", lw=2.0, label="Eastern D20")
    axes[0].set_ylabel("D20 (m)")
    axes[0].set_title("a. Thermocline adjustment", loc="left", fontsize=12.8, weight="bold")
    axes[0].legend(loc="lower left", ncol=2, frameon=False, fontsize=9)

    axes[1].plot(MONTHS, metrics["nino3_sst"], color="#c85f3d", marker="o", lw=2.1)
    axes[1].set_ylabel("Niño3 SST (°C)")
    axes[1].set_title("b. Eastern-Pacific surface warming", loc="left", fontsize=12.8, weight="bold")

    axes[2].fill_between(
        MONTHS,
        u10["observed"].to_numpy(float),
        u10["expected"].to_numpy(float),
        color="#d95f59",
        alpha=0.15,
    )
    axes[2].plot(MONTHS, u10["observed"], color="#27668f", marker="o", lw=2.1, label="Observed")
    axes[2].plot(MONTHS, u10["expected"], color="#c23b33", marker="s", lw=1.7, ls="--", label="SST-conditioned expectation")
    axes[2].set_ylabel("Peng CWP u10 (m s$^{-1}$)")
    axes[2].set_title("c. Near-surface zonal-wind response", loc="left", fontsize=12.8, weight="bold")
    axes[2].legend(loc="upper left", ncol=2, frameon=False, fontsize=9)

    axes[3].fill_between(
        MONTHS,
        precipitation["observed"].to_numpy(float),
        precipitation["expected"].to_numpy(float),
        color="#d95f59",
        alpha=0.15,
    )
    axes[3].plot(MONTHS, precipitation["observed"], color="#2f7f62", marker="o", lw=2.1, label="Observed")
    axes[3].plot(MONTHS, precipitation["expected"], color="#c23b33", marker="s", lw=1.7, ls="--", label="SST-conditioned expectation")
    axes[3].set_ylabel("CP precip. (mm day$^{-1}$)")
    axes[3].set_title("d. Deep-convective response", loc="left", fontsize=12.8, weight="bold")
    axes[3].set_xticks(MONTHS)
    axes[3].set_xticklabels(MONTH_LABELS)
    axes[3].set_xlabel("2026 calendar month")

    for left, right, _color, label in stage_bands:
        axes[0].text(
            (left + right) / 2,
            0.93,
            label,
            transform=axes[0].get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=8.8,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.4},
        )
    fig.text(
        0.01,
        -0.012,
        "All curves retain physical units. Historical expectations are calendar-month Niño3 regressions fitted over 1982-2014; 2026 is excluded. Shaded month groups are descriptive aids, not formal indices or statistically identified regime shifts, and do not constitute an event-strength forecast.",
        fontsize=9.3,
        color="0.28",
    )
    plot_module.save(fig, "fig_2026_staged_air_sea_coupling_jan_jun_1980_2014")
    plt.close(fig)


def plot_expected_response(expected: pd.DataFrame, plot_module: ModuleType) -> None:
    plot_module.setup_style()
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(13.6, 6.15), sharex=True, sharey="row", constrained_layout=True)
    fig.suptitle("Observed versus SST-conditioned historical atmospheric response", fontsize=17, weight="bold")
    response_specs = {
        "cwp_u10": ("Peng CWP u10 (m s$^{-1}$)", "#27668f"),
        "cp_precip": ("CP precipitation (mm day$^{-1}$)", "#2f7f62"),
    }
    for row, (response, (ylabel, color)) in enumerate(response_specs.items()):
        for column, target_year in enumerate(TARGET_YEARS):
            ax = axes[row, column]
            subset = expected.loc[
                expected["response"].eq(response) & expected["target_year"].eq(target_year)
            ].sort_values("month")
            x = subset["month"].to_numpy(dtype=float)
            observed = subset["observed"].to_numpy(dtype=float)
            anticipated = subset["expected"].to_numpy(dtype=float)
            ax.axhline(0, color="0.55", lw=0.75)
            ax.fill_between(x, observed, anticipated, color="#d95f59", alpha=0.16, label="Residual gap")
            ax.plot(x, observed, color=color, marker="o", lw=2.0, label="Observed")
            ax.plot(x, anticipated, color="#c23b33", marker="s", lw=1.7, ls="--", label="Historical expectation")
            mean_residual = float(subset["residual"].mean())
            ax.text(
                0.04,
                0.06,
                f"Jan-Jun residual = {mean_residual:+.2f}",
                transform=ax.transAxes,
                fontsize=9.3,
                bbox={"facecolor": "white", "edgecolor": "0.82", "alpha": 0.9, "pad": 2.2},
            )
            if row == 0:
                ax.set_title(TARGET_LABELS[target_year], fontsize=13.4, weight="bold")
            if column == 0:
                ax.set_ylabel(ylabel)
            ax.set_xticks(MONTHS)
            ax.set_xticklabels(MONTH_LABELS)
            ax.grid(True, color="0.89", lw=0.6)
    axes[1, 0].legend(loc="upper left", frameon=False, fontsize=8.8)
    for ax in axes[1]:
        ax.set_xlabel("Development month")
    fig.text(
        0.01,
        -0.015,
        "Expected responses are calendar-month regressions on detrended Niño-3 SST fitted over 1982-2014. The 2015, 2023, and 2026 targets are excluded from fitting.",
        fontsize=9.4,
        color="0.28",
    )
    plot_module.save(fig, "fig_targets_observed_expected_atmospheric_response_1982_2014")
    plt.close(fig)


def plot_ep_cp_sensitivity(
    ep_composite: dict[str, object],
    cp_composite: dict[str, object],
    manifest: pd.DataFrame,
    plot_module: ModuleType,
) -> None:
    plot_module.setup_style()
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(13.6, 5.8), constrained_layout=True)
    fig.suptitle("Ordinary El Niño sensitivity: EP versus CP precipitation-wind evolution", fontsize=17, weight="bold")
    months = np.arange(1, 7, dtype=float)
    mesh = None
    for ax, event_type, fields in zip(axes, ("EP", "CP"), (ep_composite, cp_composite)):
        lon = np.asarray(fields["lon"], dtype=float)
        lat = np.asarray(fields["lat"], dtype=float)
        precip = equatorial_mean(np.asarray(fields["precip"], dtype=float), lat)
        wind = equatorial_mean(np.asarray(fields["u850"], dtype=float), lat)
        mesh = ax.pcolormesh(lon, months, precip, cmap="BrBG", vmin=-5, vmax=5, shading="nearest")
        add_wind_contours(ax, lon, months, wind)
        years = manifest.loc[manifest["ep_cp_type"].eq(event_type), "event_year"].astype(int).tolist()
        ax.set_title(f"{event_type} subset (n={len(years)}): {', '.join(str(year) for year in years)}", loc="left", fontsize=13, weight="bold")
        ax.set_yticks(months)
        ax.set_yticklabels(MONTH_LABELS)
        ax.invert_yaxis()
        ax.set_ylabel("Development month")
        ax.text(
            0.995,
            0.05,
            "Black contours: u850 (m s$^{-1}$)",
            transform=ax.transAxes,
            ha="right",
            fontsize=8.8,
            bbox={"facecolor": "white", "edgecolor": "0.75", "alpha": 0.88, "pad": 2.0},
        )
    ticks = [130, 160, 180, 220, 260, 275]
    for ax in axes:
        ax.set_xticks(ticks)
        ax.set_xticklabels([format_lon(tick) for tick in ticks])
        ax.set_xlabel("Longitude")
    assert mesh is not None
    colorbar = fig.colorbar(mesh, ax=axes, orientation="vertical", pad=0.012, shrink=0.9)
    colorbar.set_label("ERA5 precipitation anomaly (mm day$^{-1}$)")
    fig.text(
        0.01,
        -0.015,
        "EP/CP event types follow the published CT/WP categories in Beniche et al. (2024) Supplementary Fig. S4; Yan et al. (2025) motivates the rainfall-pattern sensitivity. Subsets are qualitative when n<3.",
        fontsize=9.4,
        color="0.28",
    )
    plot_module.save(fig, "fig_ordinary_el_nino_ep_cp_sensitivity_precip_u850")
    plt.close(fig)


def update_assignment_manifest(ordinary_manifest: pd.DataFrame) -> None:
    path = OUT_DIR / "enso_event_group_assignments.csv"
    if path.exists():
        assignments = pd.read_csv(path)
        assignments = assignments.loc[~assignments["group"].eq("ordinary_non_extreme_composite")]
    else:
        assignments = pd.DataFrame(columns=["event_year", "event_label", "comparison_window", "phase", "group", "role"])
    extra = ordinary_manifest[["event_year", "event_label", "comparison_window", "phase", "group", "role"]]
    pd.concat([assignments, extra], ignore_index=True).sort_values(["group", "event_year"]).to_csv(path, index=False)


def main() -> int:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    oni, _oni_source = load_oni(args.oni_path)
    episodes = identify_warm_episodes(oni)
    manifest = ordinary_event_manifest(episodes)
    # Keep the final manifest portable even when a local NOAA snapshot is used.
    manifest["oni_source"] = NOAA_ONI_URL
    manifest["selection_rule"] = "ONI >= 0.5 for >=5 consecutive overlapping seasons; peak ONI <2.0; targets/extremes excluded"
    if args.dry_run_events:
        print(manifest.to_string(index=False))
        return 0

    event_years = manifest["event_year"].astype(int).tolist()
    ep_cp = published_ep_cp_assignments(event_years)
    manifest = manifest.merge(ep_cp, on=["event_year", "mature_djf_year"], how="left", validate="one_to_one")
    if manifest["ep_cp_type"].isna().any():
        raise ValueError("At least one ordinary event could not be assigned an EP/CP sensitivity type")

    monthly_builder = load_script(ROOT / "scripts/plot_2026_monthly_sst_precip_d20_wind.py", "monthly_panel_builder_typical")
    plot_module = load_script(ROOT / "scripts/plot_revised_enso_event_figures.py", "revised_event_plotter_typical")
    fields_by_year = ensure_event_fields(event_years, monthly_builder)
    cwp_u10 = load_peng_cwp_u10_series()
    cwp_table = pd.DataFrame(
        {
            "period": cwp_u10.index.astype(str),
            "year": cwp_u10.index.year.astype(int),
            "month": cwp_u10.index.month.astype(int),
            "cwp_u10_anomaly_m_s": cwp_u10.to_numpy(float),
            "region": "5S-5N, 140E-160W",
            "source": [
                (
                    "ARCO-ERA5T hourly 10m_u_component_of_wind aggregated to monthly mean"
                    if period.year == 2026 and period.month == 6
                    else "ERA5 monthly averaged 10m_u_component_of_wind"
                )
                for period in cwp_u10.index
            ],
            "anomaly_method": "calendar-month climatology and linear trend removed over 1982-2014",
        }
    )
    method = (
        "Equal-event January-June composite of ordinary non-extreme NOAA ONI warm episodes with developing years "
        "1982-2014. Monthly fields use same-calendar-month climatology and linear detrending; targets and extreme events are excluded."
    )
    ordinary = composite_fields(fields_by_year, event_years, method=method)
    np.savez_compressed(COMPOSITE_NPZ, **ordinary)
    difference = difference_fields(
        fields_by_year[2026], ordinary, method="January-June 2026 fields minus the ordinary non-extreme El Nino composite"
    )

    group_composites: dict[str, dict[str, object]] = {}
    for event_type in ("EP", "CP"):
        years = manifest.loc[manifest["ep_cp_type"].eq(event_type), "event_year"].astype(int).tolist()
        group_composites[event_type] = composite_fields(
            fields_by_year,
            years,
            method=(
                f"{event_type} subset of the ordinary non-extreme El Nino composite using the published "
                "Cold Tongue/Warm Pool event categories in Beniche et al. (2024), Supplementary Fig. S4"
            ),
        )

    bootstrap, target_comparison = bootstrap_tables(
        fields_by_year,
        manifest,
        cwp_u10=cwp_u10,
        n_bootstrap=args.bootstrap_replicates,
        seed=args.seed,
    )
    expected = expected_response_table(monthly_builder, cwp_u10=cwp_u10)
    similarity = analog_similarity_table(fields_by_year)

    manifest.to_csv(MANIFEST_CSV, index=False)
    bootstrap.to_csv(BOOTSTRAP_CSV, index=False)
    target_comparison.to_csv(TARGET_COMPARISON_CSV, index=False)
    expected.to_csv(EXPECTED_CSV, index=False)
    similarity.to_csv(SIMILARITY_CSV, index=False)
    cwp_table.to_csv(PENG_CWP_U10_CSV, index=False)
    ep_cp_summary = bootstrap.loc[bootstrap["group"].isin(["EP", "CP"]) & bootstrap["period"].eq("Jan-Jun")].copy()
    ep_cp_summary.to_csv(EP_CP_CSV, index=False)
    update_assignment_manifest(manifest)

    plot_module.plot_monthly_map_group(
        ordinary,
        variable="sst",
        title="Ordinary non-extreme El Niño composite: OISST SSTA and ERA5 850 hPa wind",
        panel_year="composite",
        cmap="RdBu_r",
        vmin=-2.5,
        vmax=2.5,
        colorbar_label="OISST SST anomaly (deg C)",
        stem="fig_ordinary_el_nino_composite_ssta_u850_detrended_1980_2014",
        composite_years=event_years,
    )
    plot_module.plot_monthly_map_group(
        ordinary,
        variable="precip",
        title="Ordinary non-extreme El Niño composite: ERA5 precipitation and 850 hPa wind",
        panel_year="composite",
        cmap="BrBG",
        vmin=-12.0,
        vmax=12.0,
        colorbar_label=r"ERA5 precipitation anomaly (mm day$^{-1}$)",
        stem="fig_ordinary_el_nino_composite_precip_u850_detrended_1980_2014",
        composite_years=event_years,
    )
    plot_module.plot_d20_wind(
        ordinary,
        title="Ordinary non-extreme El Niño composite: ORAS5 equatorial D20 and ERA5 u850",
        panel_year="composite",
        stem="fig_ordinary_el_nino_composite_d20_u850_detrended_1980_2014",
        composite_years=event_years,
    )
    plot_difference_hovmoller(difference, plot_module, target_year=2026)
    plot_expected_response(expected, plot_module)
    plot_2026_staged_coupling(fields_by_year[2026], expected, cwp_u10, plot_module)
    plot_ep_cp_sensitivity(group_composites["EP"], group_composites["CP"], manifest, plot_module)

    print(MANIFEST_CSV)
    print(BOOTSTRAP_CSV)
    print(EXPECTED_CSV)
    print(SIMILARITY_CSV)
    print(PENG_CWP_U10_CSV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
