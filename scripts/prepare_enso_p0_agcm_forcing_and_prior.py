#!/usr/bin/env python3
"""Prepare the P0 IA x residual-FEP AGCM forcing and observational prior.

The script has two deliberately separate products.

1. A model-agnostic CF-NetCDF file containing four prescribed-SST cells for
   March-August 2023:

       IA off/on x residual-FEP off/on.

   The primary IA component is the total observed 2023 tropical Indian Ocean
   plus tropical North Atlantic SST anomaly.  An additional sensitivity family
   uses only the IA residual after calendar-month regressions on trend,
   Nino-3.4, and the E-minus-C flavor coordinate.  The FEP component is the
   eastern-Pacific SST footprint linearly associated with the similarly
   orthogonal 5S-5N, 90W-80W residual-FEP index.

2. A 1982-2024 observational test of whether IA x residual-FEP improves the
   May-July precipitation, SLP, wind-stress, and composite atmospheric
   connection residuals.  This is an observational prior, not a causal model
   integration.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_enso_p0_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ImportError:
    ccrs = None
    cfeature = None


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
EXPERIMENT = ROOT / "experiments/enso_type_transition_matrix"
FORCING_DIR = EXPERIMENT / "forcing"
FIGURE_DIR = ROOT / "outputs/research_2026/p0_agcm_prior"
PDF_DIR = ROOT / "output/pdf"

ERSST = ROOT / "data/raw/ersstv5_sst_monthly_full.nc"
EC_MONTHLY = DERIVED / "enso_ec_indices_1980_2024.csv"
COUPLING = DERIVED / "enso_full_year_coupling_monthly_1982_2024.csv"
EXTERNAL = ROOT / "data/interim/raw_validation/oisst_external_basin_monthly.csv"
PMM = DERIVED / "pmm_like_index_oisst_era5_1982_2026.csv"
SODA = DERIVED / "soda3_transition_process_indices_1980_2024.csv"

FORCING_NC = (
    FORCING_DIR / "ersstv5_2023_agcm_ia_fep_factorial_mar_aug.nc"
)
FORCING_SUMMARY = DERIVED / "enso_p0_agcm_forcing_monthly_summary.csv"
RUN_MANIFEST = EXPERIMENT / "p0_agcm_run_manifest.csv"
EVENT_TABLE = DERIVED / "enso_p0_all_year_ia_fep_event_table.csv"
INTERACTION_TABLE = DERIVED / "enso_p0_all_year_ia_fep_interaction.csv"
SKILL_TABLE = DERIVED / "enso_p0_all_year_ia_fep_loyo_skill.csv"
BASIN_INTERACTION_TABLE = (
    DERIVED / "enso_p0_basin_specific_fep_interactions.csv"
)
BASIN_SKILL_TABLE = DERIVED / "enso_p0_basin_specific_fep_loyo_skill.csv"
DIAGNOSTICS = DERIVED / "enso_p0_agcm_forcing_and_prior_diagnostics.json"
REPORT = ROOT / "reports/ENSO_P0_IA_FEP强迫与全年份观测先验.md"
FIG_FORCING = FIGURE_DIR / "fig6_p0_agcm_forcing_components"
FIG_PRIOR = FIGURE_DIR / "fig7_p0_all_year_interaction_prior"

BASELINE_START = 1982
BASELINE_END = 2024
TARGET_YEAR = 2023
FORCING_MONTHS = (3, 4, 5, 6, 7, 8)
RESPONSE_MONTHS = (5, 6, 7)
BOOTSTRAP_SAMPLES = 10_000
PERMUTATION_SAMPLES = 20_000
RANDOM_SEED = 20260731

TARGETS = {
    "precip_response_mjj": "Precipitation",
    "slp_response_mjj": "SLP gradient",
    "tau_response_mjj": "Zonal stress",
    "coupling_mjj": "Composite connection",
}
CONTROLS = (
    "early_ec_apr",
    "npmm_fma",
    "ocean_gate_ma",
    "multi_year_la_nina_memory",
)


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.7,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.0,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "legend.fontsize": 7.4,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def ensure_inputs() -> None:
    required = (ERSST, EC_MONTHLY, COUPLING, EXTERNAL, PMM, SODA)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing inputs: {missing}")
    for directory in (DERIVED, FORCING_DIR, FIGURE_DIR, PDF_DIR, REPORT.parent):
        directory.mkdir(parents=True, exist_ok=True)


def open_dataset(path: Path) -> xr.Dataset:
    try:
        return xr.open_dataset(path, engine="h5netcdf")
    except (OSError, ValueError):
        return xr.open_dataset(path, engine="scipy")


def normalize_field(field: xr.DataArray) -> xr.DataArray:
    rename = {}
    for old, new in (
        ("valid_time", "time"),
        ("latitude", "lat"),
        ("longitude", "lon"),
    ):
        if old in field.coords:
            rename[old] = new
    field = field.rename(rename)
    field = field.assign_coords(lon=field.lon % 360).sortby("lon")
    return field.sortby("lat")


def area_mean(
    field: xr.DataArray,
    *,
    lat0: float,
    lat1: float,
    lon0: float,
    lon1: float,
) -> xr.DataArray:
    subset = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(f"Empty region: {lat0}:{lat1}, {lon0}:{lon1}")
    return subset.weighted(np.cos(np.deg2rad(subset.lat))).mean(
        ("lat", "lon"), skipna=True
    )


def taper_1d(
    coordinates: np.ndarray,
    lower: float,
    upper: float,
    width: float,
) -> np.ndarray:
    values = np.asarray(coordinates, dtype=float)
    weight = np.zeros_like(values)
    inside = (values >= lower) & (values <= upper)
    weight[inside] = 1.0
    if width > 0:
        left = inside & (values < lower + width)
        right = inside & (values > upper - width)
        weight[left] = 0.5 * (
            1.0 - np.cos(np.pi * (values[left] - lower) / width)
        )
        weight[right] = 0.5 * (
            1.0 - np.cos(np.pi * (upper - values[right]) / width)
        )
    return np.clip(weight, 0.0, 1.0)


def rectangle_mask(
    lat: np.ndarray,
    lon: np.ndarray,
    *,
    lat0: float,
    lat1: float,
    lon0: float,
    lon1: float,
    lat_taper: float,
    lon_taper: float,
) -> np.ndarray:
    lat_weight = taper_1d(lat, lat0, lat1, lat_taper)
    lon_weight = taper_1d(lon, lon0, lon1, lon_taper)
    return lat_weight[:, None] * lon_weight[None, :]


def field_regression_residuals(
    values: np.ndarray,
    design_train: np.ndarray,
    design_test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return training and test residuals for [year, lat, lon] SST."""
    n_year, n_lat, n_lon = values.shape
    flat = values.reshape(n_year, n_lat * n_lon)
    valid = np.isfinite(flat).all(axis=0)
    fitted_train = np.full_like(flat, np.nan, dtype=float)
    fitted_test = np.full((n_lat * n_lon,), np.nan, dtype=float)
    if valid.any():
        coefficients = np.linalg.lstsq(
            design_train, flat[:, valid], rcond=None
        )[0]
        fitted_train[:, valid] = design_train @ coefficients
        fitted_test[valid] = design_test @ coefficients
    train_residual = flat - fitted_train
    test_residual = flat[-1] - fitted_test
    return (
        train_residual.reshape(n_year, n_lat, n_lon),
        test_residual.reshape(n_lat, n_lon),
    )


def build_forcing() -> tuple[xr.Dataset, pd.DataFrame, dict[str, float]]:
    ec = pd.read_csv(EC_MONTHLY)
    ec = ec.loc[
        ec["year"].between(BASELINE_START, BASELINE_END)
        & ec["month"].isin(FORCING_MONTHS)
    ].copy()
    with open_dataset(ERSST) as source:
        sst = normalize_field(source["sst"]).sel(
            time=slice(
                f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-31"
            )
        ).load()

    lat = sst.lat.values.astype(float)
    lon = sst.lon.values.astype(float)
    ia_mask = np.maximum(
        rectangle_mask(
            lat,
            lon,
            lat0=-20,
            lat1=20,
            lon0=40,
            lon1=110,
            lat_taper=4,
            lon_taper=6,
        ),
        rectangle_mask(
            lat,
            lon,
            lat0=0,
            lat1=20,
            lon0=300,
            lon1=340,
            lat_taper=4,
            lon_taper=6,
        ),
    )
    fep_footprint_mask = rectangle_mask(
        lat,
        lon,
        lat0=-15,
        lat1=15,
        lon0=240,
        lon1=286,
        lat_taper=4,
        lon_taper=6,
    )
    overlap = float(np.nanmax(ia_mask * fep_footprint_mask))
    if overlap != 0.0:
        raise ValueError(f"IA and FEP masks overlap: {overlap}")

    observed_list = []
    climatology_list = []
    ia_total_list = []
    ia_independent_list = []
    fep_list = []
    summary_rows = []
    for month in FORCING_MONTHS:
        years = np.arange(BASELINE_START, BASELINE_END + 1)
        field_month = (
            sst.where(sst.time.dt.month == month, drop=True)
            .assign_coords(year=("time", sst.where(
                sst.time.dt.month == month, drop=True
            ).time.dt.year.values))
            .swap_dims({"time": "year"})
            .drop_vars("time")
            .reindex(year=years)
        )
        predictors = (
            ec.loc[ec["month"].eq(month)]
            .set_index("year")
            .reindex(years)
        )
        if predictors[
            ["ersst_nino34_anom_c", "ec_flavor_e_minus_c"]
        ].isna().any().any():
            raise ValueError(f"Missing EC predictors for calendar month {month}")

        train_years = years[years != TARGET_YEAR]
        train_field = field_month.sel(year=train_years)
        test_field = field_month.sel(year=TARGET_YEAR)
        train_predictors = predictors.loc[train_years]
        test_predictors = predictors.loc[TARGET_YEAR]
        design_train = np.column_stack(
            [
                np.ones(len(train_years)),
                train_years.astype(float) - 2003.0,
                train_predictors["ersst_nino34_anom_c"].to_numpy(float),
                train_predictors["ec_flavor_e_minus_c"].to_numpy(float),
            ]
        )
        design_test = np.asarray(
            [
                1.0,
                TARGET_YEAR - 2003.0,
                float(test_predictors["ersst_nino34_anom_c"]),
                float(test_predictors["ec_flavor_e_minus_c"]),
            ]
        )
        values = np.concatenate(
            [
                train_field.values.astype(float),
                test_field.values[None, ...].astype(float),
            ],
            axis=0,
        )
        design_all_train = np.vstack([design_train, design_test])
        train_residual, test_residual = field_regression_residuals(
            values, design_all_train, design_test
        )
        # The regression above includes the target as the final row only to
        # preserve array ordering. Refit strictly without 2023 to avoid target
        # leakage in the component definition.
        train_values = train_field.values.astype(float)
        n_lat, n_lon = train_values.shape[1:]
        flat = train_values.reshape(len(train_years), n_lat * n_lon)
        valid = np.isfinite(flat).all(axis=0)
        beta = np.full((design_train.shape[1], n_lat * n_lon), np.nan)
        beta[:, valid] = np.linalg.lstsq(
            design_train, flat[:, valid], rcond=None
        )[0]
        fitted_train = (design_train @ beta).reshape(train_values.shape)
        fitted_test = (design_test @ beta).reshape(n_lat, n_lon)
        train_residual = train_values - fitted_train
        test_residual = test_field.values.astype(float) - fitted_test

        ocean = np.isfinite(test_field.values)
        climatology = train_field.mean("year", skipna=True).values.astype(float)
        observed = test_field.values.astype(float)
        ia_total_component = np.where(
            ocean, (observed - climatology) * ia_mask, np.nan
        )
        ia_independent_component = np.where(
            ocean, test_residual * ia_mask, np.nan
        )

        residual_da = xr.DataArray(
            train_residual,
            dims=("year", "lat", "lon"),
            coords={"year": train_years, "lat": lat, "lon": lon},
        )
        fep_seed_train = area_mean(
            residual_da,
            lat0=-5,
            lat1=5,
            lon0=270,
            lon1=280,
        ).values.astype(float)
        test_residual_da = xr.DataArray(
            test_residual,
            dims=("lat", "lon"),
            coords={"lat": lat, "lon": lon},
        )
        fep_seed_2023 = float(
            area_mean(
                test_residual_da,
                lat0=-5,
                lat1=5,
                lon0=270,
                lon1=280,
            )
        )
        denominator = float(np.nansum(fep_seed_train**2))
        if denominator == 0:
            raise ValueError(f"Degenerate residual FEP in month {month}")
        pattern = np.nansum(
            train_residual * fep_seed_train[:, None, None], axis=0
        ) / denominator
        fep_component = np.where(
            ocean,
            pattern * fep_seed_2023 * fep_footprint_mask,
            np.nan,
        )

        observed_list.append(observed)
        climatology_list.append(climatology)
        ia_total_list.append(ia_total_component)
        ia_independent_list.append(ia_independent_component)
        fep_list.append(fep_component)
        area = xr.DataArray(
            np.ones_like(observed),
            dims=("lat", "lon"),
            coords={"lat": lat, "lon": lon},
        )
        ia_total_da = xr.DataArray(
            ia_total_component,
            dims=("lat", "lon"),
            coords={"lat": lat, "lon": lon},
        )
        ia_independent_da = xr.DataArray(
            ia_independent_component,
            dims=("lat", "lon"),
            coords={"lat": lat, "lon": lon},
        )
        fep_da = xr.DataArray(
            fep_component,
            dims=("lat", "lon"),
            coords={"lat": lat, "lon": lon},
        )
        summary_rows.append(
            {
                "year": TARGET_YEAR,
                "month": month,
                "fep_seed_residual_c": fep_seed_2023,
                "ia_total_tio_component_c": float(
                    area_mean(
                        ia_total_da,
                        lat0=-20,
                        lat1=20,
                        lon0=40,
                        lon1=110,
                    )
                ),
                "ia_total_tna_component_c": float(
                    area_mean(
                        ia_total_da,
                        lat0=0,
                        lat1=20,
                        lon0=300,
                        lon1=340,
                    )
                ),
                "ia_independent_tio_component_c": float(
                    area_mean(
                        ia_independent_da,
                        lat0=-20,
                        lat1=20,
                        lon0=40,
                        lon1=110,
                    )
                ),
                "ia_independent_tna_component_c": float(
                    area_mean(
                        ia_independent_da,
                        lat0=0,
                        lat1=20,
                        lon0=300,
                        lon1=340,
                    )
                ),
                "fep_component_seed_box_c": float(
                    area_mean(
                        fep_da, lat0=-5, lat1=5, lon0=270, lon1=280
                    )
                ),
            }
        )

    observed = np.stack(observed_list)
    climatology = np.stack(climatology_list)
    ia_total_component = np.stack(ia_total_list)
    ia_independent_component = np.stack(ia_independent_list)
    fep_component = np.stack(fep_list)
    background = observed - ia_total_component - fep_component
    independent_background = (
        observed - ia_independent_component - fep_component
    )
    cells = {
        "sst_AG_IA0_FEP0": background,
        "sst_AG_IA0_FEP1": background + fep_component,
        "sst_AG_IA1_FEP0": background + ia_total_component,
        "sst_AG_IA1_FEP1": (
            background + ia_total_component + fep_component
        ),
        "sst_AG_IAR0_FEP0": independent_background,
        "sst_AG_IAR0_FEP1": independent_background + fep_component,
        "sst_AG_IAR1_FEP0": (
            independent_background + ia_independent_component
        ),
        "sst_AG_IAR1_FEP1": (
            independent_background
            + ia_independent_component
            + fep_component
        ),
    }
    time = pd.to_datetime(
        [f"{TARGET_YEAR}-{month:02d}-01" for month in FORCING_MONTHS]
    )
    dataset = xr.Dataset(
        {
            "sst_observed_2023": (("time", "lat", "lon"), observed),
            "sst_climatology_1982_2024_excluding_2023": (
                ("time", "lat", "lon"),
                climatology,
            ),
            "sst_ia_total_anomaly_component": (
                ("time", "lat", "lon"),
                ia_total_component,
            ),
            "sst_ia_independent_component": (
                ("time", "lat", "lon"),
                ia_independent_component,
            ),
            "sst_residual_fep_component": (
                ("time", "lat", "lon"),
                fep_component,
            ),
            "ia_mask": (("lat", "lon"), ia_mask),
            "fep_footprint_mask": (("lat", "lon"), fep_footprint_mask),
            **{
                name: (("time", "lat", "lon"), values)
                for name, values in cells.items()
            },
        },
        coords={"time": time, "lat": lat, "lon": lon},
        attrs={
            "title": "P0 AGCM prescribed-SST IA x residual-FEP factorial",
            "source": "NOAA ERSSTv5 local monthly file",
            "target_year": TARGET_YEAR,
            "forcing_months": "March-August",
            "regression_baseline": "1982-2024, target year excluded",
            "orthogonalization": (
                "calendar-month gridpoint OLS on intercept, linear trend, "
                "Nino-3.4 anomaly, and E-minus-C flavor"
            ),
            "fep_seed_box": "5S-5N, 90W-80W",
            "ia_domains": (
                "20S-20N, 40E-110E and 0-20N, 60W-20W; cosine tapered"
            ),
            "primary_factorial": (
                "AG_IA uses the total observed 2023 IA anomaly relative to "
                "the target-excluded 1982-2024 calendar-month climatology"
            ),
            "sensitivity_factorial": (
                "AG_IAR uses only the IA residual independent of trend, "
                "Nino-3.4, and E-minus-C flavor"
            ),
            "warning": (
                "Model-agnostic ocean SST boundary. Remap and add the target "
                "model's sea-ice/land treatment before integration."
            ),
        },
    )
    for name in dataset.data_vars:
        if name.startswith("sst"):
            dataset[name].attrs.update(
                {"units": "degC", "long_name": name.replace("_", " ")}
            )
    dataset["ia_mask"].attrs.update(
        {"units": "1", "long_name": "cosine-tapered IA mask"}
    )
    dataset["fep_footprint_mask"].attrs.update(
        {"units": "1", "long_name": "cosine-tapered FEP footprint mask"}
    )
    reconstruction_error = float(
        np.nanmax(np.abs(cells["sst_AG_IA1_FEP1"] - observed))
    )
    independent_reconstruction_error = float(
        np.nanmax(np.abs(cells["sst_AG_IAR1_FEP1"] - observed))
    )
    contrast_error = float(
        np.nanmax(
            np.abs(
                (
                    cells["sst_AG_IA1_FEP1"]
                    - cells["sst_AG_IA1_FEP0"]
                )
                - (
                    cells["sst_AG_IA0_FEP1"]
                    - cells["sst_AG_IA0_FEP0"]
                )
            )
        )
    )
    independent_contrast_error = float(
        np.nanmax(
            np.abs(
                (
                    cells["sst_AG_IAR1_FEP1"]
                    - cells["sst_AG_IAR1_FEP0"]
                )
                - (
                    cells["sst_AG_IAR0_FEP1"]
                    - cells["sst_AG_IAR0_FEP0"]
                )
            )
        )
    )
    ocean_values = np.concatenate(
        [
            values[np.isfinite(values)]
            for values in cells.values()
        ]
    )
    checks = {
        "reconstruction_max_abs_error_c": reconstruction_error,
        "independent_sensitivity_reconstruction_max_abs_error_c": (
            independent_reconstruction_error
        ),
        "factor_contrast_max_abs_error_c": contrast_error,
        "independent_sensitivity_factor_contrast_max_abs_error_c": (
            independent_contrast_error
        ),
        "ia_fep_mask_max_overlap": overlap,
        "minimum_cell_sst_c": float(ocean_values.min()),
        "maximum_cell_sst_c": float(ocean_values.max()),
    }
    if (
        reconstruction_error > 1e-10
        or independent_reconstruction_error > 1e-10
        or contrast_error > 1e-10
        or independent_contrast_error > 1e-10
    ):
        raise ValueError(f"Factorial identity failed: {checks}")
    if checks["minimum_cell_sst_c"] < -2.5 or checks["maximum_cell_sst_c"] > 40:
        raise ValueError(f"Unphysical prescribed SST: {checks}")

    encoding = {
        name: {
            "dtype": "float32",
            "zlib": True,
            "complevel": 4,
            "_FillValue": np.float32(1.0e20),
        }
        for name in dataset.data_vars
    }
    dataset.to_netcdf(FORCING_NC, engine="h5netcdf", encoding=encoding)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(FORCING_SUMMARY, index=False)
    return dataset, summary, checks


def write_run_manifest() -> pd.DataFrame:
    families = {
        "primary_total_ia": (
            "AG_IA0_FEP0",
            "AG_IA0_FEP1",
            "AG_IA1_FEP0",
            "AG_IA1_FEP1",
        ),
        "sensitivity_independent_ia": (
            "AG_IAR0_FEP0",
            "AG_IAR0_FEP1",
            "AG_IAR1_FEP0",
            "AG_IAR1_FEP1",
        ),
    }
    rows = []
    cell_number = 0
    for family, cells in families.items():
        for cell in cells:
            cell_number += 1
            for member in range(1, 31):
                rows.append(
                    {
                        "family": family,
                        "experiment_id": cell,
                        "member": member,
                        "sst_variable": f"sst_{cell}",
                        "sst_file": str(FORCING_NC.relative_to(ROOT)),
                        "integration_start": "2023-03-01",
                        "integration_end": "2023-08-31",
                        "atmosphere_initial_condition": (
                            "common March climatological state plus "
                            "member perturbation"
                        ),
                        "member_seed": 20230000
                        + cell_number * 100
                        + member,
                        "required_monthly_outputs": (
                            "PRECT, OLR/FLUT, PSL, U850, TAUX"
                        ),
                        "required_daily_outputs": (
                            "PRECT, U850, V850, TAUX"
                        ),
                        "status": "awaiting_target_model_and_compute",
                    }
                )
    manifest = pd.DataFrame(rows)
    manifest.to_csv(RUN_MANIFEST, index=False)
    return manifest


def monthly_anomaly_detrend(
    frame: pd.DataFrame,
    column: str,
    *,
    output: str,
) -> pd.DataFrame:
    data = frame.copy()
    climatology = (
        data.loc[data["year"].between(BASELINE_START, BASELINE_END)]
        .groupby("month")[column]
        .mean()
    )
    anomaly = data[column] - data["month"].map(climatology)
    decimal_year = data["year"] + (data["month"] - 0.5) / 12.0
    valid = anomaly.notna() & data["year"].between(
        BASELINE_START, BASELINE_END
    )
    design = np.column_stack(
        [
            np.ones(valid.sum()),
            decimal_year.loc[valid].to_numpy(float) - 2003.0,
        ]
    )
    coefficient = np.linalg.lstsq(
        design, anomaly.loc[valid].to_numpy(float), rcond=None
    )[0]
    data[output] = anomaly - (
        coefficient[0]
        + coefficient[1] * (decimal_year.to_numpy(float) - 2003.0)
    )
    return data


def zscore(values: pd.Series) -> pd.Series:
    scale = float(values.std(ddof=1))
    if not np.isfinite(scale) or scale == 0:
        return pd.Series(np.nan, index=values.index)
    return (values - values.mean()) / scale


def seasonal_mean(
    frame: pd.DataFrame,
    column: str,
    months: tuple[int, ...],
) -> pd.Series:
    return (
        frame.loc[frame["month"].isin(months)]
        .groupby("year")[column]
        .mean()
    )


def leave_one_year_residual(
    monthly: pd.DataFrame,
    response: str,
    *,
    controls: tuple[str, ...],
) -> pd.DataFrame:
    rows = []
    for month, group in monthly.groupby("month"):
        valid = group.dropna(subset=[response, *controls]).copy()
        for row in valid.itertuples(index=False):
            year = int(row.year)
            train = valid.loc[valid["year"].ne(year)]
            design = np.column_stack(
                [
                    np.ones(len(train)),
                    train["year"].to_numpy(float) - 2003.0,
                    *[
                        train[column].to_numpy(float)
                        for column in controls
                    ],
                ]
            )
            coefficient = np.linalg.lstsq(
                design, train[response].to_numpy(float), rcond=None
            )[0]
            fitted = design @ coefficient
            degrees = max(1, len(train) - design.shape[1])
            scale = math.sqrt(
                float(np.sum((train[response].to_numpy(float) - fitted) ** 2))
                / degrees
            )
            test = np.asarray(
                [
                    1.0,
                    year - 2003.0,
                    *[float(getattr(row, column)) for column in controls],
                ]
            )
            residual = (float(getattr(row, response)) - test @ coefficient)
            if scale > 0:
                residual /= scale
            else:
                residual = np.nan
            rows.append({"year": year, "month": month, "residual": residual})
    return pd.DataFrame(rows)


def build_nino_long_record() -> pd.DataFrame:
    with open_dataset(ERSST) as source:
        field = normalize_field(source["sst"]).sel(
            time=slice("1978-01-01", f"{BASELINE_END}-12-31")
        )
        nino = area_mean(
            field, lat0=-5, lat1=5, lon0=190, lon1=240
        ).load()
    time = pd.to_datetime(nino.time.values)
    frame = pd.DataFrame(
        {
            "time": time,
            "year": time.year,
            "month": time.month,
            "nino34": nino.values.astype(float),
        }
    )
    return monthly_anomaly_detrend(
        frame, "nino34", output="nino34_ad"
    )


def residualize(
    values: pd.Series,
    controls: pd.DataFrame,
) -> pd.Series:
    table = pd.concat([values.rename("target"), controls], axis=1)
    valid = table.notna().all(axis=1)
    x = np.column_stack(
        [
            np.ones(valid.sum()),
            table.index.to_numpy(float)[valid] - 2003.0,
            *[
                table.loc[valid, column].to_numpy(float)
                for column in controls.columns
            ],
        ]
    )
    coefficient = np.linalg.lstsq(
        x, table.loc[valid, "target"].to_numpy(float), rcond=None
    )[0]
    x_full = np.column_stack(
        [
            np.ones(len(table)),
            table.index.to_numpy(float) - 2003.0,
            *[
                table[column].to_numpy(float)
                for column in controls.columns
            ],
        ]
    )
    output = table["target"] - x_full @ coefficient
    output.loc[~valid] = np.nan
    return output


def build_all_year_table() -> pd.DataFrame:
    years = np.arange(BASELINE_START, BASELINE_END + 1)
    ec = pd.read_csv(EC_MONTHLY)
    coupling = pd.read_csv(COUPLING)
    nino = build_nino_long_record()

    table = pd.DataFrame({"year": years}).set_index("year")
    nino_mjj = seasonal_mean(nino, "nino34_ad", RESPONSE_MONTHS).reindex(years)
    ec_mjj = seasonal_mean(
        ec, "ec_flavor_e_minus_c", RESPONSE_MONTHS
    ).reindex(years)
    table["nino34_mjj_ad"] = nino_mjj
    table["early_ec_apr"] = (
        ec.loc[ec["month"].eq(4)]
        .set_index("year")["ec_flavor_e_minus_c"]
        .reindex(years)
    )

    fep_monthly = leave_one_year_residual(
        coupling,
        "fep_raw_c",
        controls=("nino34_raw_c", "sst_type_raw_c"),
    )
    table["fep_residual_mjj"] = seasonal_mean(
        fep_monthly, "residual", RESPONSE_MONTHS
    ).reindex(years)

    # Recompute the external-basin indices from the complete ERSSTv5 source.
    # The legacy OISST intermediate table ends in February 2024 and therefore
    # cannot support a 1982-2024 MJJ analysis.
    with open_dataset(ERSST) as source:
        external_field = normalize_field(source["sst"]).sel(
            time=slice(
                f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-31"
            )
        )
        external_series = {
            "tropical_indian_ocean": area_mean(
                external_field,
                lat0=-20,
                lat1=20,
                lon0=40,
                lon1=110,
            ).load(),
            "tropical_north_atlantic": area_mean(
                external_field,
                lat0=0,
                lat1=20,
                lon0=300,
                lon1=340,
            ).load(),
        }
    pieces = {}
    for region, series in external_series.items():
        time = pd.to_datetime(series.time.values)
        current = pd.DataFrame(
            {
                "year": time.year,
                "month": time.month,
                "sst": series.values.astype(float),
            }
        )
        current = monthly_anomaly_detrend(
            current, "sst", output="sst_ad"
        )
        pieces[region] = seasonal_mean(
            current, "sst_ad", RESPONSE_MONTHS
        ).reindex(years)
    control_frame = pd.DataFrame(
        {"nino34": nino_mjj, "ec_flavor": ec_mjj}, index=years
    )
    table["tio_total_ad"] = pieces["tropical_indian_ocean"]
    table["tna_total_ad"] = pieces["tropical_north_atlantic"]
    table["indo_atlantic_total_ad"] = zscore(
        (
            zscore(pieces["tropical_indian_ocean"])
            + zscore(pieces["tropical_north_atlantic"])
        )
        / math.sqrt(2.0)
    )
    tio = residualize(pieces["tropical_indian_ocean"], control_frame)
    tna = residualize(pieces["tropical_north_atlantic"], control_frame)
    table["tio_independent"] = tio
    table["tna_independent"] = tna
    table["indo_atlantic_independent"] = zscore(
        (zscore(tio) + zscore(tna)) / math.sqrt(2.0)
    )

    pmm = pd.read_csv(PMM)
    table["npmm_fma"] = (
        pmm.loc[
            pmm["year"].between(BASELINE_START, BASELINE_END)
            & pmm["month"].isin((2, 3, 4))
        ]
        .groupby("year")["pmm_joint_sst_wind"]
        .mean()
        .reindex(years)
    )

    soda = pd.read_csv(SODA)
    ocean = (
        soda.loc[soda["month"].isin((3, 4))]
        .groupby("year")
        .agg(
            d20_east_ma=("d20_east_m_anom", "mean"),
            east_fraction_ma=("wwv_east_fraction_anom", "mean"),
        )
        .reindex(years)
    )
    table["ocean_gate_ma"] = zscore(
        (
            zscore(ocean["d20_east_ma"])
            + zscore(ocean["east_fraction_ma"])
        )
        / math.sqrt(2.0)
    )

    indexed_nino = nino.set_index("time")["nino34_ad"].sort_index()
    memories = {}
    for year in years:
        winter_means = []
        for ending_year in (year - 2, year - 1, year):
            dates = [
                pd.Timestamp(ending_year - 1, 12, 1),
                pd.Timestamp(ending_year, 1, 1),
                pd.Timestamp(ending_year, 2, 1),
            ]
            winter_means.append(float(indexed_nino.reindex(dates).mean()))
        period = indexed_nino.loc[
            pd.Timestamp(year - 3, 9, 1):pd.Timestamp(year, 2, 1)
        ]
        cold_integral = float(
            np.nansum(np.maximum(-period.to_numpy(float) - 0.5, 0.0))
        )
        memories[year] = {
            "count": float(np.sum(np.asarray(winter_means) <= -0.5)),
            "integral": cold_integral,
        }
    memory = pd.DataFrame.from_dict(memories, orient="index")
    table["multi_year_la_nina_memory"] = zscore(
        (zscore(memory["count"]) + zscore(memory["integral"]))
        / math.sqrt(2.0)
    )

    response_columns = {
        "precip_response_mjj": "precip_tropical_pacific_raw_mmday",
        "slp_response_mjj": "slp_drive_w_minus_e_raw_hpa",
        "tau_response_mjj": "tau_cwp_raw_nm2",
    }
    for output, raw in response_columns.items():
        residual = leave_one_year_residual(
            coupling,
            raw,
            controls=("nino34_raw_c", "sst_type_raw_c"),
        )
        table[output] = seasonal_mean(
            residual, "residual", RESPONSE_MONTHS
        ).reindex(years)
    table["coupling_mjj"] = table[list(response_columns)].mean(axis=1)
    table = table.reset_index()

    required = [
        "fep_residual_mjj",
        "indo_atlantic_total_ad",
        "indo_atlantic_independent",
        "tio_total_ad",
        "tna_total_ad",
        "tio_independent",
        "tna_independent",
        *CONTROLS,
        *TARGETS,
    ]
    if table[required].isna().any().any():
        missing = table.loc[
            table[required].isna().any(axis=1), ["year", *required]
        ]
        raise ValueError(f"Missing all-year indices:\n{missing}")
    for column in required:
        table[f"{column}_z"] = zscore(table[column])
    table["warm_development"] = table["nino34_mjj_ad"] > 0.0
    table.to_csv(EVENT_TABLE, index=False)
    return table


def design_matrix(
    frame: pd.DataFrame,
    *,
    include_interaction: bool,
) -> tuple[np.ndarray, tuple[str, ...]]:
    columns = (
        *CONTROLS,
        "indo_atlantic_independent",
        "fep_residual_mjj",
    )
    standardized = frame.loc[:, columns].copy()
    for column in columns:
        standardized[column] = zscore(standardized[column])
    features = [np.ones(len(frame))]
    names = ["intercept"]
    for column in columns:
        features.append(standardized[column].to_numpy(float))
        names.append(column)
    if include_interaction:
        features.append(
            standardized["indo_atlantic_independent"].to_numpy(float)
            * standardized["fep_residual_mjj"].to_numpy(float)
        )
        names.append("ia_x_fep")
    return np.column_stack(features), tuple(names)


def fit_coefficient(
    frame: pd.DataFrame,
    target: str,
) -> tuple[float, np.ndarray]:
    x, names = design_matrix(frame, include_interaction=True)
    y = zscore(frame[target]).to_numpy(float)
    coefficient = np.linalg.lstsq(x, y, rcond=None)[0]
    return float(coefficient[names.index("ia_x_fep")]), coefficient


def interaction_coefficient_numpy(
    predictor_values: np.ndarray,
    response_values: np.ndarray,
) -> float:
    """Fast standardized OLS interaction coefficient for resampling loops."""
    predictor_mean = predictor_values.mean(axis=0)
    predictor_scale = predictor_values.std(axis=0, ddof=1)
    response_scale = float(response_values.std(ddof=1))
    if (
        np.any(~np.isfinite(predictor_scale))
        or np.any(predictor_scale == 0)
        or not np.isfinite(response_scale)
        or response_scale == 0
    ):
        return float("nan")
    z = (predictor_values - predictor_mean) / predictor_scale
    y = (response_values - response_values.mean()) / response_scale
    interaction = z[:, -2] * z[:, -1]
    design = np.column_stack([np.ones(len(z)), z, interaction])
    coefficient = np.linalg.lstsq(design, y, rcond=None)[0]
    return float(coefficient[-1])


def standardized_interaction_design(
    predictor_values: np.ndarray,
    response_values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    predictor_scale = predictor_values.std(axis=0, ddof=1)
    response_scale = float(response_values.std(ddof=1))
    z = (
        predictor_values - predictor_values.mean(axis=0)
    ) / predictor_scale
    y = (response_values - response_values.mean()) / response_scale
    reduced = np.column_stack([np.ones(len(z)), z])
    full = np.column_stack(
        [reduced, z[:, -2] * z[:, -1]]
    )
    return reduced, full, y


def bh_fdr(p_values: pd.Series) -> pd.Series:
    values = p_values.to_numpy(float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.minimum(adjusted, 1.0)
    return pd.Series(output, index=p_values.index)


def loyo_predictions(
    frame: pd.DataFrame,
    target: str,
    *,
    include_interaction: bool,
) -> np.ndarray:
    predictions = np.full(len(frame), np.nan)
    for index in range(len(frame)):
        train = frame.drop(frame.index[index]).copy()
        test = frame.iloc[[index]].copy()
        columns = (
            *CONTROLS,
            "indo_atlantic_independent",
            "fep_residual_mjj",
        )
        means = train.loc[:, columns].mean()
        scales = train.loc[:, columns].std(ddof=1)
        y_mean = float(train[target].mean())
        y_scale = float(train[target].std(ddof=1))
        train_z = train.copy()
        test_z = test.copy()
        for column in columns:
            train_z[column] = (train[column] - means[column]) / scales[column]
            test_z[column] = (test[column] - means[column]) / scales[column]
        x_train, _ = design_matrix(
            train_z, include_interaction=include_interaction
        )
        # design_matrix standardizes again; train_z already has mean 0 and
        # sd 1, and the repeated transform is numerically identical.
        x_test_features = [1.0]
        x_test_features.extend(
            float(test_z.iloc[0][column]) for column in columns
        )
        if include_interaction:
            x_test_features.append(
                float(test_z.iloc[0]["indo_atlantic_independent"])
                * float(test_z.iloc[0]["fep_residual_mjj"])
            )
        y_train = (train[target] - y_mean) / y_scale
        coefficient = np.linalg.lstsq(
            x_train, y_train.to_numpy(float), rcond=None
        )[0]
        predictions[index] = (
            np.asarray(x_test_features) @ coefficient
        ) * y_scale + y_mean
    return predictions


def run_interaction_prior(
    table: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_SEED)
    interaction_rows = []
    skill_rows = []
    samples = {
        "all_years": table.copy(),
        "positive_nino34_mjj": table.loc[table["warm_development"]].copy(),
    }
    for sample_name, sample in samples.items():
        sample = sample.reset_index(drop=True)
        for ia_definition, ia_column in (
            ("independent", "indo_atlantic_independent"),
            ("total_anomaly", "indo_atlantic_total_ad"),
        ):
            working = sample.copy()
            working["indo_atlantic_independent"] = working[ia_column]
            predictor_columns = (
                *CONTROLS,
                "indo_atlantic_independent",
                "fep_residual_mjj",
            )
            predictor_values = working.loc[
                :, predictor_columns
            ].to_numpy(float)
            for target in TARGETS:
                response_values = working[target].to_numpy(float)
                point = interaction_coefficient_numpy(
                    predictor_values, response_values
                )
                boot = np.full(BOOTSTRAP_SAMPLES, np.nan)
                for iteration in range(BOOTSTRAP_SAMPLES):
                    indices = rng.integers(
                        0, len(working), len(working)
                    )
                    boot[iteration] = interaction_coefficient_numpy(
                        predictor_values[indices],
                        response_values[indices],
                    )
                low, high = np.nanpercentile(boot, [2.5, 97.5])
                reduced, full, standardized_response = (
                    standardized_interaction_design(
                        predictor_values, response_values
                    )
                )
                reduced_coefficient = np.linalg.lstsq(
                    reduced, standardized_response, rcond=None
                )[0]
                fitted_reduced = reduced @ reduced_coefficient
                reduced_residual = standardized_response - fitted_reduced
                permuted = np.full(PERMUTATION_SAMPLES, np.nan)
                for iteration in range(PERMUTATION_SAMPLES):
                    permuted_response = (
                        fitted_reduced
                        + rng.permutation(reduced_residual)
                    )
                    permuted[iteration] = np.linalg.lstsq(
                        full, permuted_response, rcond=None
                    )[0][-1]
                p_value = (
                    1.0
                    + float(np.sum(np.abs(permuted) >= abs(point)))
                ) / (PERMUTATION_SAMPLES + 1.0)
                interaction_rows.append(
                    {
                        "sample": sample_name,
                        "ia_definition": ia_definition,
                        "target": target,
                        "target_label": TARGETS[target],
                        "n_years": len(working),
                        "interaction_beta_sd": point,
                        "bootstrap_ci_low": float(low),
                        "bootstrap_ci_high": float(high),
                        "permutation_p": p_value,
                        "bootstrap_positive_fraction": float(
                            np.nanmean(boot > 0)
                        ),
                    }
                )

                observed = working[target].to_numpy(float)
                pred_main = loyo_predictions(
                    working, target, include_interaction=False
                )
                pred_interaction = loyo_predictions(
                    working, target, include_interaction=True
                )
                skill_rows.append(
                    {
                        "sample": sample_name,
                        "ia_definition": ia_definition,
                        "target": target,
                        "n_years": len(working),
                        "main_effects_loyo_r": float(
                            stats.pearsonr(
                                observed, pred_main
                            ).statistic
                        ),
                        "interaction_loyo_r": float(
                            stats.pearsonr(
                                observed, pred_interaction
                            ).statistic
                        ),
                        "delta_loyo_r": float(
                            stats.pearsonr(
                                observed, pred_interaction
                            ).statistic
                            - stats.pearsonr(
                                observed, pred_main
                            ).statistic
                        ),
                        "main_effects_rmse": float(
                            np.sqrt(
                                np.mean((observed - pred_main) ** 2)
                            )
                        ),
                        "interaction_rmse": float(
                            np.sqrt(
                                np.mean(
                                    (observed - pred_interaction) ** 2
                                )
                            )
                        ),
                        "delta_rmse_skill": float(
                            np.sqrt(
                                np.mean((observed - pred_main) ** 2)
                            )
                            - np.sqrt(
                                np.mean(
                                    (observed - pred_interaction) ** 2
                                )
                            )
                        ),
                    }
                )
    interactions = pd.DataFrame(interaction_rows)
    interactions["fdr_q_within_sample"] = (
        interactions.groupby(
            ["sample", "ia_definition"]
        )["permutation_p"]
        .transform(bh_fdr)
    )
    skill = pd.DataFrame(skill_rows)
    interactions.to_csv(INTERACTION_TABLE, index=False)
    skill.to_csv(SKILL_TABLE, index=False)
    return interactions, skill


def basin_interaction_design(
    predictor_values: np.ndarray,
    response_values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    predictor_scale = predictor_values.std(axis=0, ddof=1)
    response_scale = float(response_values.std(ddof=1))
    if (
        np.any(~np.isfinite(predictor_scale))
        or np.any(predictor_scale == 0)
        or not np.isfinite(response_scale)
        or response_scale == 0
    ):
        raise ValueError("Degenerate basin-interaction standardization")
    z = (
        predictor_values - predictor_values.mean(axis=0)
    ) / predictor_scale
    y = (response_values - response_values.mean()) / response_scale
    reduced = np.column_stack([np.ones(len(z)), z])
    full = np.column_stack(
        [
            reduced,
            z[:, -3] * z[:, -1],
            z[:, -2] * z[:, -1],
        ]
    )
    return reduced, full, y


def basin_interaction_coefficients(
    predictor_values: np.ndarray,
    response_values: np.ndarray,
) -> np.ndarray:
    try:
        _, full, y = basin_interaction_design(
            predictor_values, response_values
        )
    except ValueError:
        return np.asarray([np.nan, np.nan])
    return np.linalg.lstsq(full, y, rcond=None)[0][-2:]


def loyo_basin_predictions(
    frame: pd.DataFrame,
    target: str,
    *,
    include_interactions: bool,
) -> np.ndarray:
    columns = (
        *CONTROLS,
        "tio_independent",
        "tna_independent",
        "fep_residual_mjj",
    )
    predictions = np.full(len(frame), np.nan)
    for index in range(len(frame)):
        train = frame.drop(frame.index[index])
        test = frame.iloc[index]
        means = train.loc[:, columns].mean()
        scales = train.loc[:, columns].std(ddof=1)
        train_z = (train.loc[:, columns] - means) / scales
        test_z = (test.loc[list(columns)].astype(float) - means) / scales
        reduced = np.column_stack(
            [np.ones(len(train_z)), train_z.to_numpy(float)]
        )
        test_features = [1.0, *test_z.to_numpy(float)]
        if include_interactions:
            train_design = np.column_stack(
                [
                    reduced,
                    train_z["tio_independent"].to_numpy(float)
                    * train_z["fep_residual_mjj"].to_numpy(float),
                    train_z["tna_independent"].to_numpy(float)
                    * train_z["fep_residual_mjj"].to_numpy(float),
                ]
            )
            test_features.extend(
                [
                    float(test_z["tio_independent"])
                    * float(test_z["fep_residual_mjj"]),
                    float(test_z["tna_independent"])
                    * float(test_z["fep_residual_mjj"]),
                ]
            )
        else:
            train_design = reduced
        coefficient = np.linalg.lstsq(
            train_design, train[target].to_numpy(float), rcond=None
        )[0]
        predictions[index] = np.asarray(test_features) @ coefficient
    return predictions


def run_basin_specific_prior(
    table: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_SEED + 17)
    predictor_columns = (
        *CONTROLS,
        "tio_independent",
        "tna_independent",
        "fep_residual_mjj",
    )
    interaction_names = (
        ("tio_x_fep", "Tropical Indian Ocean × residual FEP", 0),
        ("tna_x_fep", "Tropical North Atlantic × residual FEP", 1),
    )
    rows = []
    skill_rows = []
    samples = {
        "all_years": table.copy(),
        "positive_nino34_mjj": table.loc[table["warm_development"]].copy(),
    }
    for sample_name, sample in samples.items():
        sample = sample.reset_index(drop=True)
        predictors = sample.loc[:, predictor_columns].to_numpy(float)
        for target in TARGETS:
            response = sample[target].to_numpy(float)
            point = basin_interaction_coefficients(predictors, response)
            boot = np.full((BOOTSTRAP_SAMPLES, 2), np.nan)
            for iteration in range(BOOTSTRAP_SAMPLES):
                indices = rng.integers(0, len(sample), len(sample))
                boot[iteration] = basin_interaction_coefficients(
                    predictors[indices], response[indices]
                )
            reduced, full, standardized_response = basin_interaction_design(
                predictors, response
            )
            reduced_coefficient = np.linalg.lstsq(
                reduced, standardized_response, rcond=None
            )[0]
            fitted_reduced = reduced @ reduced_coefficient
            residual_reduced = standardized_response - fitted_reduced
            permutation = np.full((PERMUTATION_SAMPLES, 2), np.nan)
            for iteration in range(PERMUTATION_SAMPLES):
                permuted_response = (
                    fitted_reduced + rng.permutation(residual_reduced)
                )
                permutation[iteration] = np.linalg.lstsq(
                    full, permuted_response, rcond=None
                )[0][-2:]
            for interaction_id, label, position in interaction_names:
                low, high = np.nanpercentile(
                    boot[:, position], [2.5, 97.5]
                )
                p_value = (
                    1.0
                    + float(
                        np.sum(
                            np.abs(permutation[:, position])
                            >= abs(point[position])
                        )
                    )
                ) / (PERMUTATION_SAMPLES + 1.0)
                rows.append(
                    {
                        "sample": sample_name,
                        "target": target,
                        "target_label": TARGETS[target],
                        "interaction": interaction_id,
                        "interaction_label": label,
                        "n_years": len(sample),
                        "interaction_beta_sd": float(point[position]),
                        "bootstrap_ci_low": float(low),
                        "bootstrap_ci_high": float(high),
                        "freedman_lane_p": p_value,
                        "bootstrap_positive_fraction": float(
                            np.nanmean(boot[:, position] > 0)
                        ),
                    }
                )
            observed = response
            prediction_main = loyo_basin_predictions(
                sample, target, include_interactions=False
            )
            prediction_full = loyo_basin_predictions(
                sample, target, include_interactions=True
            )
            skill_rows.append(
                {
                    "sample": sample_name,
                    "target": target,
                    "n_years": len(sample),
                    "main_effects_loyo_r": float(
                        stats.pearsonr(
                            observed, prediction_main
                        ).statistic
                    ),
                    "basin_interactions_loyo_r": float(
                        stats.pearsonr(
                            observed, prediction_full
                        ).statistic
                    ),
                    "delta_loyo_r": float(
                        stats.pearsonr(
                            observed, prediction_full
                        ).statistic
                        - stats.pearsonr(
                            observed, prediction_main
                        ).statistic
                    ),
                    "main_effects_rmse": float(
                        np.sqrt(
                            np.mean((observed - prediction_main) ** 2)
                        )
                    ),
                    "basin_interactions_rmse": float(
                        np.sqrt(
                            np.mean((observed - prediction_full) ** 2)
                        )
                    ),
                    "delta_rmse_skill": float(
                        np.sqrt(
                            np.mean((observed - prediction_main) ** 2)
                        )
                        - np.sqrt(
                            np.mean((observed - prediction_full) ** 2)
                        )
                    ),
                }
            )
    interactions = pd.DataFrame(rows)
    interactions["fdr_q_within_sample"] = (
        interactions.groupby("sample")["freedman_lane_p"]
        .transform(bh_fdr)
    )
    basin_skill = pd.DataFrame(skill_rows)
    interactions.to_csv(BASIN_INTERACTION_TABLE, index=False)
    basin_skill.to_csv(BASIN_SKILL_TABLE, index=False)
    return interactions, basin_skill


def save_figure(fig: plt.Figure, stem: Path) -> None:
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    if stem == FIG_FORCING:
        fig.savefig(
            PDF_DIR / "enso_p0_agcm_forcing_components.pdf",
            bbox_inches="tight",
        )
    if stem == FIG_PRIOR:
        fig.savefig(
            PDF_DIR / "enso_p0_all_year_interaction_prior.pdf",
            bbox_inches="tight",
        )
    plt.close(fig)


def plot_forcing(dataset: xr.Dataset) -> None:
    setup_style()
    means = {
        "IA total anomaly component": dataset[
            "sst_ia_total_anomaly_component"
        ].mean("time"),
        "IA independent component": dataset[
            "sst_ia_independent_component"
        ].mean("time"),
        "Residual-FEP component": dataset[
            "sst_residual_fep_component"
        ].mean("time"),
        "Primary both off: anomaly": (
            dataset["sst_AG_IA0_FEP0"]
            - dataset["sst_climatology_1982_2024_excluding_2023"]
        ).mean("time"),
        "Independent-IA both off: anomaly": (
            dataset["sst_AG_IAR0_FEP0"]
            - dataset["sst_climatology_1982_2024_excluding_2023"]
        ).mean("time"),
        "Observed 2023 anomaly": (
            dataset["sst_AG_IA1_FEP1"]
            - dataset["sst_climatology_1982_2024_excluding_2023"]
        ).mean("time"),
    }
    def tropical_values(field: xr.DataArray) -> np.ndarray:
        return field.sel(
            lat=slice(-32, 32), lon=slice(20, 340)
        ).values.ravel()

    component_max = float(
        np.nanmax(
            np.abs(
                np.concatenate(
                    [
                        tropical_values(
                            means["IA total anomaly component"]
                        ),
                        tropical_values(
                            means["IA independent component"]
                        ),
                        tropical_values(
                            means["Residual-FEP component"]
                        ),
                    ]
                )
            )
        )
    )
    anomaly_max = float(
        np.nanmax(
            np.abs(
                np.concatenate(
                    [
                        tropical_values(
                            means["Primary both off: anomaly"]
                        ),
                        tropical_values(
                            means["Independent-IA both off: anomaly"]
                        ),
                        tropical_values(
                            means["Observed 2023 anomaly"]
                        ),
                    ]
                )
            )
        )
    )
    component_limit = max(0.5, math.ceil(component_max * 2) / 2)
    anomaly_limit = max(2.0, math.ceil(anomaly_max * 2) / 2)
    projection = (
        ccrs.PlateCarree(central_longitude=180) if ccrs else None
    )
    subplot_kw = {"projection": projection} if projection else {}
    fig, axes = plt.subplots(
        2,
        3,
        figsize=(13.2, 5.8),
        subplot_kw=subplot_kw,
        constrained_layout=True,
    )
    panel_letters = ("a", "b", "c", "d", "e", "f")
    for index, (title, field) in enumerate(means.items()):
        ax = axes.flat[index]
        limit = component_limit if index < 3 else anomaly_limit
        kwargs = (
            {"transform": ccrs.PlateCarree()} if ccrs else {}
        )
        mesh = ax.pcolormesh(
            field.lon,
            field.lat,
            field,
            cmap="RdBu_r",
            vmin=-limit,
            vmax=limit,
            shading="auto",
            rasterized=True,
            **kwargs,
        )
        if ccrs:
            ax.set_global()
            ax.set_extent([20, 340, -32, 32], crs=ccrs.PlateCarree())
            ax.add_feature(cfeature.LAND, facecolor="#e5e2dc", zorder=3)
            ax.coastlines(linewidth=0.45, color="#444444")
            grid = ax.gridlines(
                draw_labels=True,
                linewidth=0.3,
                color="#777777",
                alpha=0.45,
                linestyle=":",
            )
            grid.top_labels = False
            grid.right_labels = False
        else:
            ax.set_xlim(20, 340)
            ax.set_ylim(-32, 32)
        ax.set_title(
            f"({panel_letters[index]}) {title}",
            loc="left",
            fontweight="bold",
        )
        colorbar = fig.colorbar(
            mesh, ax=ax, orientation="horizontal", pad=0.08, shrink=0.82
        )
        colorbar.set_label("SST anomaly/component (°C)")
    fig.suptitle(
        "P0 AGCM prescribed-SST forcing, March-August 2023 mean",
        fontsize=13,
        fontweight="bold",
    )
    save_figure(fig, FIG_FORCING)


def plot_prior(
    table: pd.DataFrame,
    interactions: pd.DataFrame,
    skill: pd.DataFrame,
) -> None:
    setup_style()
    fig = plt.figure(figsize=(11.2, 4.2), constrained_layout=True)
    grid = fig.add_gridspec(1, 3, width_ratios=(1.05, 1.25, 1.0))
    ax0 = fig.add_subplot(grid[0, 0])
    x = table["indo_atlantic_independent_z"]
    y = table["fep_residual_mjj_z"]
    color = table["coupling_mjj_z"]
    scatter = ax0.scatter(
        x,
        y,
        c=color,
        cmap="RdBu_r",
        vmin=-2,
        vmax=2,
        s=32,
        edgecolor="white",
        linewidth=0.45,
    )
    event_2023 = table.loc[table["year"].eq(2023)].iloc[0]
    ax0.scatter(
        event_2023["indo_atlantic_independent_z"],
        event_2023["fep_residual_mjj_z"],
        marker="*",
        s=145,
        color="#f4c542",
        edgecolor="#222222",
        linewidth=0.7,
        zorder=5,
    )
    ax0.annotate(
        "2023",
        (
            event_2023["indo_atlantic_independent_z"],
            event_2023["fep_residual_mjj_z"],
        ),
        xytext=(5, 5),
        textcoords="offset points",
        fontsize=8,
        fontweight="bold",
    )
    ax0.axhline(0, color="#777777", lw=0.6)
    ax0.axvline(0, color="#777777", lw=0.6)
    ax0.set_xlabel("Independent Indo-Atlantic heating (SD)")
    ax0.set_ylabel("Residual FEP (SD)")
    ax0.set_title("(a) 1982–2024 years", loc="left", fontweight="bold")
    cbar = fig.colorbar(scatter, ax=ax0, orientation="horizontal", pad=0.15)
    cbar.set_label("MJJ atmospheric connection residual (SD)")

    ax1 = fig.add_subplot(grid[0, 1])
    primary = interactions.loc[
        interactions["sample"].eq("all_years")
        & interactions["ia_definition"].eq("independent")
    ].copy()
    positions = np.arange(len(primary))
    values = primary["interaction_beta_sd"].to_numpy(float)
    lower = values - primary["bootstrap_ci_low"].to_numpy(float)
    upper = primary["bootstrap_ci_high"].to_numpy(float) - values
    ax1.errorbar(
        values,
        positions,
        xerr=np.vstack([lower, upper]),
        fmt="o",
        color="#186a78",
        ecolor="#6d8790",
        capsize=3,
        lw=1.3,
    )
    ax1.axvline(0, color="#555555", lw=0.8)
    ax1.set_yticks(positions)
    ax1.set_yticklabels(primary["target_label"])
    ax1.invert_yaxis()
    ax1.set_xlabel("IA × residual-FEP coefficient (SD)")
    ax1.set_title(
        "(b) Interaction, all years\n95% year-bootstrap interval",
        loc="left",
        fontweight="bold",
    )
    for pos, row in zip(positions, primary.itertuples(), strict=True):
        ax1.text(
            max(row.bootstrap_ci_high, row.interaction_beta_sd) + 0.03,
            pos,
            f"q={row.fdr_q_within_sample:.2f}",
            va="center",
            fontsize=7.3,
        )

    ax2 = fig.add_subplot(grid[0, 2])
    targets = list(TARGETS)
    width = 0.34
    for offset, sample_name, label, color_value in (
        (-width / 2, "all_years", "All years", "#2b7185"),
        (width / 2, "positive_nino34_mjj", "Positive Niño-3.4 MJJ", "#d26a4b"),
    ):
        current = (
            skill.loc[
                skill["sample"].eq(sample_name)
                & skill["ia_definition"].eq("independent")
            ]
            .set_index("target")
            .reindex(targets)
        )
        ax2.bar(
            np.arange(len(targets)) + offset,
            current["delta_loyo_r"],
            width=width,
            label=label,
            color=color_value,
        )
    ax2.axhline(0, color="#555555", lw=0.8)
    ax2.set_xticks(np.arange(len(targets)))
    ax2.set_xticklabels(
        [TARGETS[target].replace(" ", "\n") for target in targets],
        rotation=0,
    )
    ax2.set_ylabel("Δ leave-one-year-out correlation")
    ax2.set_title(
        "(c) Increment from adding interaction",
        loc="left",
        fontweight="bold",
    )
    ax2.legend(frameon=False, loc="best")
    fig.suptitle(
        "Observational prior for the P0 IA × residual-FEP experiment",
        fontsize=13,
        fontweight="bold",
    )
    save_figure(fig, FIG_PRIOR)


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}"


def write_report(
    forcing_summary: pd.DataFrame,
    checks: dict[str, float],
    table: pd.DataFrame,
    interactions: pd.DataFrame,
    skill: pd.DataFrame,
    basin_interactions: pd.DataFrame,
    basin_skill: pd.DataFrame,
) -> None:
    primary = interactions.loc[
        interactions["sample"].eq("all_years")
        & interactions["ia_definition"].eq("independent")
    ]
    primary_total = interactions.loc[
        interactions["sample"].eq("all_years")
        & interactions["ia_definition"].eq("total_anomaly")
    ]
    warm = interactions.loc[
        interactions["sample"].eq("positive_nino34_mjj")
        & interactions["ia_definition"].eq("independent")
    ]
    warm_total = interactions.loc[
        interactions["sample"].eq("positive_nino34_mjj")
        & interactions["ia_definition"].eq("total_anomaly")
    ]
    primary_skill = skill.loc[
        skill["sample"].eq("all_years")
        & skill["ia_definition"].eq("independent")
    ]
    warm_basin = basin_interactions.loc[
        basin_interactions["sample"].eq("positive_nino34_mjj")
    ]
    warm_basin_skill = basin_skill.loc[
        basin_skill["sample"].eq("positive_nino34_mjj")
    ]
    event_2023 = table.loc[table["year"].eq(2023)].iloc[0]
    lines = [
        "# ENSO P0：IA×residual-FEP强迫文件与全年份观测先验",
        "",
        "## 结论先行",
        "",
        (
            "已经把2023年3—8月的Indo–Atlantic总海温异常与"
            "residual-FEP空间分量拆成四组可移植的CF-NetCDF海温边界场；"
            "同时附加只保留IA独立残差的四格敏感性试验。两套四格都严格"
            "闭合到同一个观测场。"
        ),
        "",
        (
            "但1982—2024全年份观测先验并没有自动把IA×FEP确认为稳定"
            "因果交互。正Niño3.4发展年份中出现了“IA越暖，FEP对大气接通"
            "越不利”的负交互候选，但年份bootstrap区间仍跨零；最终仍以"
            "动力模式四格交互对比为准。"
        ),
        "",
        "## 1. 强迫如何构造",
        "",
        "- SST源：NOAA ERSSTv5月平均，2°网格。",
        "- 时段：2023年3—8月；回归背景为1982—2024，逐月且排除2023。",
        (
            "- 主试验IA分量是2023相对逐月气候态的总异常，直接对应"
            "“保留/移除观测外海盆异常”；敏感性试验IAR只保留移除"
            "趋势、Niño3.4和E/C型态后的独立残差。"
        ),
        (
            "- FEP仍定义为5°S–5°N、90°W–80°W；用其独立残差回归得到"
            "热带东太平洋空间足迹，而不是改变FEP定义。"
        ),
        "- 两个空间分量使用余弦边缘渐变，避免强迫边界产生数值跳变。",
        "",
        "| 格点 | SST边界 |",
        "|---|---|",
        "| AG_IA0_FEP0 | 观测2023 − IA分量 − FEP分量 |",
        "| AG_IA0_FEP1 | 上式 + FEP分量 |",
        "| AG_IA1_FEP0 | 上式 + IA分量 |",
        "| AG_IA1_FEP1 | 完整观测2023 |",
        "| AG_IAR0/1_FEP0/1 | 同样四格，但IA改为独立残差分量 |",
        "",
        "四格交互量：",
        "",
        "`(IA1_FEP1 − IA1_FEP0) − (IA0_FEP1 − IA0_FEP0)`",
        "",
        "## 2. NetCDF一致性检查",
        "",
        f"- 完整观测场重构最大误差：{checks['reconstruction_max_abs_error_c']:.3e} °C。",
        f"- 因子对比恒等式最大误差：{checks['factor_contrast_max_abs_error_c']:.3e} °C。",
        (
            "- 独立IA敏感性试验重构/因子恒等式误差："
            f"{checks['independent_sensitivity_reconstruction_max_abs_error_c']:.3e} / "
            f"{checks['independent_sensitivity_factor_contrast_max_abs_error_c']:.3e} °C。"
        ),
        f"- IA与FEP掩膜最大重叠：{checks['ia_fep_mask_max_overlap']:.3e}。",
        (
            f"- 四组边界场海洋格点范围：{checks['minimum_cell_sst_c']:.2f}"
            f" 至 {checks['maximum_cell_sst_c']:.2f} °C。"
        ),
        "",
        "月度分量：",
        "",
        (
            "| 月 | residual-FEP种子 | 印度洋IA总异常 | 北大西洋IA总异常 | "
            "印度洋IA独立残差 | 北大西洋IA独立残差 |"
        ),
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in forcing_summary.itertuples():
        lines.append(
            f"| {row.month} | {row.fep_seed_residual_c:+.2f} | "
            f"{row.ia_total_tio_component_c:+.2f} | "
            f"{row.ia_total_tna_component_c:+.2f} | "
            f"{row.ia_independent_tio_component_c:+.2f} | "
            f"{row.ia_independent_tna_component_c:+.2f} |"
        )
    lines.extend(
        [
            "",
            "## 3. 1982—2024全年份观测交互",
            "",
            (
                "响应量为MJJ降水、SLP梯度和中西太平洋纬向风应力；每个"
                "年份都用排除该年的逐月回归移除同期Niño3.4、E/C型态和"
                "趋势，再将三条支路平均为综合接通量。交互模型同时控制"
                "4月早期型态、FMA NPMM、3—4月SODA3东部海洋门控和多年"
                "La Niña记忆。"
            ),
            "",
            "| 响应 | n | IA×FEP系数(SD) | 95% bootstrap | Freedman–Lane p | FDR q |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in primary.itertuples():
        lines.append(
            f"| {row.target_label} | {row.n_years} | "
            f"{fmt(row.interaction_beta_sd)} | "
            f"[{fmt(row.bootstrap_ci_low)}, {fmt(row.bootstrap_ci_high)}] | "
            f"{row.permutation_p:.3f} | {row.fdr_q_within_sample:.3f} |"
        )
    lines.extend(
        [
            "",
            "正Niño3.4发展年份敏感性：",
            "",
            "| 响应 | n | IA×FEP系数(SD) | 95% bootstrap | FDR q |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in warm.itertuples():
        lines.append(
            f"| {row.target_label} | {row.n_years} | "
            f"{fmt(row.interaction_beta_sd)} | "
            f"[{fmt(row.bootstrap_ci_low)}, {fmt(row.bootstrap_ci_high)}] | "
            f"{row.fdr_q_within_sample:.3f} |"
        )
    lines.extend(
        [
            "",
            "IA总异常定义的稳健性对照：",
            "",
            "| 样本 | 响应 | IA×FEP系数(SD) | 95% bootstrap | FDR q |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for sample_label, current in (
        ("全部年份", primary_total),
        ("正Niño3.4发展年份", warm_total),
    ):
        for row in current.itertuples():
            lines.append(
                f"| {sample_label} | {row.target_label} | "
                f"{fmt(row.interaction_beta_sd)} | "
                f"[{fmt(row.bootstrap_ci_low)}, "
                f"{fmt(row.bootstrap_ci_high)}] | "
                f"{row.fdr_q_within_sample:.3f} |"
            )
    lines.extend(
        [
            "",
            (
                "解释：独立IA定义下，全43年样本的负交互未通过FDR。"
                "只保留MJJ Niño3.4为正的23年时，Freedman–Lane检验和"
                "留一年技巧给出较一致的负交互线索；然而年份bootstrap"
                "区间仍跨零。总异常定义给出相同的负号和相近的留一年"
                "改进，风应力交互通过FDR、综合接通量接近FDR阈值，但"
                "bootstrap同样跨零。因此符号并非只由IA定义造成，强度"
                "不确定性却仍很大。"
            ),
            "",
            "## 4. 印度洋还是热带北大西洋",
            "",
            (
                "为避免联合IA指数掩盖两个海盆的相反作用，又在同一个模型中"
                "同时加入TIO×FEP与TNA×FEP。下表为23个正Niño3.4发展"
                "年份；模型仍控制相同四个背景量和两个海盆的主效应。"
            ),
            "",
            "| 响应 | 海盆交互 | 系数(SD) | 95% bootstrap | FDR q |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in warm_basin.itertuples():
        lines.append(
            f"| {row.target_label} | {row.interaction_label} | "
            f"{fmt(row.interaction_beta_sd)} | "
            f"[{fmt(row.bootstrap_ci_low)}, {fmt(row.bootstrap_ci_high)}] | "
            f"{row.fdr_q_within_sample:.3f} |"
        )
    coupling_basin_skill = warm_basin_skill.loc[
        warm_basin_skill["target"].eq("coupling_mjj")
    ].iloc[0]
    lines.extend(
        [
            "",
            (
                "两个海盆拆开后，只有在系数符号、bootstrap区间与FDR三者"
                "同时一致时才允许指定主导海盆。若仍不一致，AGCM主四格"
                "应保持联合IA；只有主四格出现效应后，才进入TIO-only与"
                "TNA-only拆分。"
            ),
            (
                "正Niño3.4年份中加入两个海盆交互后，综合接通量的"
                f"留一年相关增量为{coupling_basin_skill['delta_loyo_r']:+.2f}，"
                f"RMSE改进为{coupling_basin_skill['delta_rmse_skill']:+.3f}。"
            ),
            "",
            "## 5. 留一年增量技巧",
            "",
            "| 响应 | 主效应r | 加交互r | Δr | RMSE改进 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in primary_skill.itertuples():
        lines.append(
            f"| {TARGETS[row.target]} | {row.main_effects_loyo_r:+.2f} | "
            f"{row.interaction_loyo_r:+.2f} | {row.delta_loyo_r:+.2f} | "
            f"{row.delta_rmse_skill:+.3f} |"
        )
    lines.extend(
        [
            "",
            "## 6. 2023在新坐标中的位置",
            "",
            (
                f"- Indo–Atlantic独立加热："
                f"{event_2023['indo_atlantic_independent_z']:+.2f} SD。"
            ),
            (
                f"- Indo–Atlantic总异常："
                f"{event_2023['indo_atlantic_total_ad_z']:+.2f} SD。"
            ),
            (
                f"- 印度洋/热带北大西洋独立残差："
                f"{event_2023['tio_independent_z']:+.2f} / "
                f"{event_2023['tna_independent_z']:+.2f} SD。"
            ),
            (
                f"- residual FEP：{event_2023['fep_residual_mjj_z']:+.2f} SD。"
            ),
            (
                f"- 综合大气接通残差：{event_2023['coupling_mjj_z']:+.2f} SD。"
            ),
            "",
            "## 7. 科学解释边界",
            "",
            (
                "这一步只回答“IA与FEP的联合状态在历史逐年样本中是否与"
                "额外大气响应同现”。它不能回答把IA海温人为移除后风是否"
                "一定改变；后者必须由30成员四格AGCM集合的因子主效应与"
                "交互量回答。"
            ),
            "",
            (
                "即使AGCM中交互显著，它也只能解释给定SST后大气为何接上；"
                "EP/CP是否真正翻型仍需下一阶段耦合模式的海洋门控×风场矩阵。"
            ),
            "",
            "## 8. 与权威研究的关系",
            "",
            (
                "- Peng et al. (2025, Nature Geoscience)用AGCM表明2023年"
                "印度洋、大西洋增暖和慢变SST背景削弱了热带太平洋表面风"
                "响应；本阶段两种IA定义都得到负交互候选，方向一致，但"
                "观测不确定性更大："
                "https://www.nature.com/articles/s41561-025-01700-9"
            ),
            (
                "- 2025年Communications Earth & Environment的三海盆"
                "AGCM实验显示，印度洋主要驱动跨太平洋东风，而大西洋"
                "产生东西不同号的风型；这解释了为什么本阶段把TIO与TNA"
                "拆开后不能简单期待同一个回归系数："
                "https://www.nature.com/articles/s43247-025-02584-8"
            ),
            (
                "- Kim, Tian & Yu (2025)把2023年的减速联系到多年La Niña"
                "后持续的西中太平洋东风、东西SST梯度和NPMM/D20背景；"
                "这说明IA×FEP不是唯一上游控制："
                "https://www.nature.com/articles/s41612-024-00890-0"
            ),
            (
                "- Jiang et al. (2026)提供residual-FEP及其大气响应机制；"
                "本阶段检验的是该局地FEP强迫是否会被外海盆背景调制，"
                "不是重复证明FEP自身存在："
                "https://doi.org/10.1029/2026GL123227"
            ),
            "",
            (
                "因此，本阶段没有声称发现一个全新的单因子规律。新增贡献"
                "是把已有“FEP局地响应”和“外海盆抑制”两条文献链预注册"
                "成同一个四格交互试验，并给出全年份观测先验和可直接重映射"
                "的边界场。"
            ),
            "",
            "## 9. 文件",
            "",
            f"- 强迫NetCDF：`{FORCING_NC.relative_to(ROOT)}`",
            f"- 240成员运行清单：`{RUN_MANIFEST.relative_to(ROOT)}`",
            f"- 强迫月表：`{FORCING_SUMMARY.relative_to(ROOT)}`",
            f"- 全年份表：`{EVENT_TABLE.relative_to(ROOT)}`",
            f"- 交互结果：`{INTERACTION_TABLE.relative_to(ROOT)}`",
            f"- 留一年技巧：`{SKILL_TABLE.relative_to(ROOT)}`",
            f"- 分海盆交互：`{BASIN_INTERACTION_TABLE.relative_to(ROOT)}`",
            f"- 分海盆留一年技巧：`{BASIN_SKILL_TABLE.relative_to(ROOT)}`",
            f"- 强迫图：`{FIG_FORCING.with_suffix('.pdf').relative_to(ROOT)}`",
            f"- 观测先验图：`{FIG_PRIOR.with_suffix('.pdf').relative_to(ROOT)}`",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ensure_inputs()
    forcing, forcing_summary, checks = build_forcing()
    run_manifest = write_run_manifest()
    all_year = build_all_year_table()
    interactions, skill = run_interaction_prior(all_year)
    basin_interactions, basin_skill = run_basin_specific_prior(all_year)
    plot_forcing(forcing)
    plot_prior(all_year, interactions, skill)
    write_report(
        forcing_summary,
        checks,
        all_year,
        interactions,
        skill,
        basin_interactions,
        basin_skill,
    )
    diagnostic = {
        "created_utc": pd.Timestamp.utcnow().isoformat(),
        "forcing_file": str(FORCING_NC),
        "forcing_dimensions": {
            name: int(size) for name, size in forcing.sizes.items()
        },
        "baseline": f"{BASELINE_START}-{BASELINE_END}",
        "target_year": TARGET_YEAR,
        "forcing_months": list(FORCING_MONTHS),
        "response_months": list(RESPONSE_MONTHS),
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "permutation_samples": PERMUTATION_SAMPLES,
        "checks": checks,
        "all_year_count": len(all_year),
        "warm_development_count": int(all_year["warm_development"].sum()),
        "basin_specific_interactions_tested": True,
        "run_manifest_members": len(run_manifest),
        "run_manifest_cells": int(
            run_manifest["experiment_id"].nunique()
        ),
        "model_integrations_completed": False,
        "observational_prior_only": True,
    }
    DIAGNOSTICS.write_text(
        json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(FORCING_NC)
    print(INTERACTION_TABLE)
    print(SKILL_TABLE)
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
