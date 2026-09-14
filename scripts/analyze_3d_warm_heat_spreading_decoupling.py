#!/usr/bin/env python3
"""Link early three-dimensional warm-heat geometry to later ENSO decoupling.

The analysis extends the existing equator--north box calculation by adding the
5--15S band and by separating 0--100 m from 100--300 m.  For each of 13 warm
events, January--March ocean geometry is sampled in a moving +/-10-degree
longitude window around the existing equatorial positive-OHC centroid.  The
primary meridional-broadening test asks whether mean off-equatorial OHC is high
after the three-band total OHC has been held fixed.  Surface exposure and the
north--south asymmetry are tested as separate components rather than folded
into an optimized index.

All ocean anomalies use a 1980--2024 same-calendar-month linear baseline.
Later atmospheric outcomes are the existing SST-pattern-adjusted coupling
residuals.  The script produces event/month tables, permutation/bootstrap
statistics, manuscript-style PNG/PDF figures, diagnostics, and a Chinese
report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Iterable

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/enso_3d_warm_heat_spreading_decoupling"
os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / "mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(OUT_DIR / "cache"))
os.environ.setdefault("OMP_NUM_THREADS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

sys.path.insert(0, str(ROOT / "scripts"))
from climate_plot_style import add_panel_labels, apply_climate_style, save_figure  # noqa: E402


EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = (1997, 2015, 2023)
MONTHS = (1, 2, 3, 4, 5, 6)
YEARS = np.arange(1980, 2025, dtype=int)
BASELINE = (1980, 2024)
WINDOW_HALF_WIDTH = 10.0
EAST_LON_BOUNDS = (220.0, 280.0)  # 140W--80W
RHO0 = 1025.0
CP0 = 3990.0
N_PERMUTATIONS = 10_000
N_BOOTSTRAP = 5_000
SEED = 20260818

BAND_ORDER = ("eq", "south", "north")
BAND_LABELS = {"eq": "5S-5N", "south": "5-15S", "north": "5-15N"}
LAYER_BOUNDS = {
    "surface_0_100": (0.0, 100.0),
    "deep_100_300": (100.0, 300.0),
    "full_0_300": (0.0, 300.0),
    "core_150_250": (150.0, 250.0),
}
AREA_WEIGHTS = {
    "eq": np.sin(np.deg2rad(5.0)) - np.sin(np.deg2rad(-5.0)),
    "south": np.sin(np.deg2rad(-5.0)) - np.sin(np.deg2rad(-15.0)),
    "north": np.sin(np.deg2rad(15.0)) - np.sin(np.deg2rad(5.0)),
}
COLORS = {1997: "#2f6da5", 2015: "#d98c27", 2023: "#b23a3a"}

TEMP_FILE = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
OUTER_CACHE = (
    ROOT
    / "data/interim/research_2026/soda3_latband_lon_depth_sections/"
    "yearly_outer_band_latitude_sums"
)
CENTROID_CSV = (
    ROOT
    / "outputs/research_2026/soda3_all_warm_event_core_trajectories/"
    "soda3_13_warm_events_monthly_core_centroids.csv"
)
COUPLING_CSV = DERIVED / "enso_ocean_conditioned_decoupling_event_summary.csv"
OLD_PARTITION_CSV = DERIVED / "warm_heat_partition_coupling_event_table.csv"

MONTHLY_CSV = DERIVED / "enso_3d_warm_heat_spreading_monthly.csv"
EVENT_CSV = DERIVED / "enso_3d_warm_heat_spreading_event_metrics.csv"
RELATIONSHIP_CSV = DERIVED / "enso_3d_warm_heat_spreading_relationships.csv"
SENSITIVITY_CSV = DERIVED / "enso_3d_warm_heat_spreading_sensitivity.csv"
DIAGNOSTICS_JSON = DERIVED / "enso_3d_warm_heat_spreading_diagnostics.json"
FIG_PNG = OUT_DIR / "enso_3d_warm_heat_spreading_decoupling.png"
FIG_PDF = OUT_DIR / "enso_3d_warm_heat_spreading_decoupling.pdf"
ROBUST_PNG = OUT_DIR / "enso_3d_warm_heat_spreading_robustness.png"
ROBUST_PDF = OUT_DIR / "enso_3d_warm_heat_spreading_robustness.pdf"
CROSS_EVENT_PNG = OUT_DIR / "enso_cross_event_broadening_jja_coupling_en.png"
CROSS_EVENT_PDF = OUT_DIR / "enso_cross_event_broadening_jja_coupling_en.pdf"
REPORT_MD = OUT_DIR / "ENSO_3D_WARM_HEAT_SPREADING_DECOUPLING_CN.md"


def require_files(paths: Iterable[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")


def layer_overlap_weights(depth: np.ndarray, lower: float, upper: float) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    if not np.all(np.diff(depth) > 0):
        raise ValueError("Depth coordinate must increase downward")
    edges = np.empty(depth.size + 1, dtype=float)
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    edges[0] = 0.0
    edges[-1] = 300.0
    return np.maximum(0.0, np.minimum(edges[1:], upper) - np.maximum(edges[:-1], lower))


def detrend_year_axis(values: np.ndarray) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    x = YEARS.astype(float)
    fit = (x >= BASELINE[0]) & (x <= BASELINE[1])
    selected = data[fit]
    xf = x[fit]
    xc = xf - xf.mean()
    expand = (-1,) + (1,) * (data.ndim - 1)
    finite = np.isfinite(selected)
    count = finite.sum(axis=0)
    mean = np.divide(
        np.nansum(selected, axis=0),
        count,
        out=np.full(data.shape[1:], np.nan),
        where=count > 0,
    )
    denominator = np.sum(finite * xc.reshape(expand) ** 2, axis=0)
    numerator = np.nansum((selected - mean) * xc.reshape(expand), axis=0)
    slope = np.divide(
        numerator,
        denominator,
        out=np.full(data.shape[1:], np.nan),
        where=denominator > 0,
    )
    return data - mean - (x - xf.mean()).reshape(expand) * slope


def load_anomaly_fields() -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    with xr.open_dataset(TEMP_FILE, engine="netcdf4") as source:
        if source.temp.attrs.get("units") != "degC":
            raise ValueError(f"Unexpected SODA3 temperature units: {source.temp.attrs.get('units')}")
        depth = source.depth.values.astype(float)
        latitude = source.lat.values.astype(float)
        longitude = source.lon.values.astype(float)
        times = pd.DatetimeIndex(source.time.values)
        raw = source.temp.load().values.astype(float)
    expected_times = pd.DatetimeIndex(
        [pd.Timestamp(year, month, 15) for year in YEARS for month in MONTHS]
    )
    if not np.array_equal(times.year, expected_times.year) or not np.array_equal(
        times.month, expected_times.month
    ):
        raise ValueError("Unexpected SODA3 Jan--Jun time axis")
    if not np.all(np.diff(longitude) > 0):
        raise ValueError("SODA3 longitude must increase")
    raw = raw.reshape(len(YEARS), len(MONTHS), len(depth), len(latitude), len(longitude))
    lat_weight = np.cos(np.deg2rad(latitude))[None, None, :, None]
    numerator = np.nansum(raw * lat_weight, axis=3)
    denominator = np.nansum(np.isfinite(raw) * lat_weight, axis=3)
    equatorial = np.divide(
        numerator,
        denominator,
        out=np.full(numerator.shape, np.nan),
        where=denominator > 0,
    )

    outer: list[np.ndarray] = []
    expected_bands = ("north_15_30", "north_5_15", "south_5_15", "south_15_30")
    for year in YEARS:
        path = OUTER_CACHE / f"soda3_four_outer_latband_sums_{year}_jan_jun.npz"
        with np.load(path) as cache:
            bands = tuple(str(value) for value in cache["bands"])
            if bands != expected_bands:
                raise ValueError(f"Unexpected outer-band order for {year}: {bands}")
            numerator = cache["temperature_weighted_sum"].astype(float)
            denominator = cache["valid_weight_sum"].astype(float)
            average = np.divide(
                numerator,
                denominator,
                out=np.full(numerator.shape, np.nan),
                where=denominator > 0,
            )
            outer.append(average)
    outer_values = np.stack(outer)
    fields = {
        "eq": equatorial,
        "north": outer_values[:, 1],
        "south": outer_values[:, 2],
    }
    for field in fields.values():
        for month_index in range(len(MONTHS)):
            field[:, month_index] = detrend_year_axis(field[:, month_index])
    return fields, depth, longitude


def layer_ohc_per_area(
    field: np.ndarray,
    depth_weights: np.ndarray,
    lon_mask: np.ndarray,
    column_validity_weights: np.ndarray,
) -> float:
    selected = np.asarray(field, dtype=float)[:, lon_mask]
    valid_fraction = np.nansum(
        np.isfinite(selected) * column_validity_weights[:, None], axis=0
    ) / np.sum(column_validity_weights)
    valid_columns = valid_fraction > 0.999
    if valid_columns.sum() < 3:
        raise ValueError("Too few full-depth longitude columns in analysis window")
    integrated = np.nansum(selected * depth_weights[:, None], axis=0)
    return float(np.nanmean(integrated[valid_columns]) * RHO0 * CP0 / 1.0e9)


def build_monthly_table(
    fields: dict[str, np.ndarray], depth: np.ndarray, longitude: np.ndarray
) -> pd.DataFrame:
    centroids = pd.read_csv(CENTROID_CSV)
    if set(centroids.event.unique()) != set(EVENTS):
        raise ValueError("Centroid event sample does not match the 13-event analysis")
    if centroids.duplicated(["event", "month"]).any():
        raise ValueError("Duplicate event-month centroid rows")
    weights = {
        name: layer_overlap_weights(depth, lower, upper)
        for name, (lower, upper) in LAYER_BOUNDS.items()
    }
    rows: list[dict[str, float | int | str]] = []
    for event in EVENTS:
        year_index = int(np.flatnonzero(YEARS == event)[0])
        group = str(centroids.loc[centroids.event.eq(event), "group"].iloc[0])
        for month in MONTHS:
            current = centroids.loc[
                centroids.event.eq(event) & centroids.month.eq(month)
            ].iloc[0]
            center = float(current.centroid_lon_e)
            moving_mask = (longitude >= center - WINDOW_HALF_WIDTH) & (
                longitude <= center + WINDOW_HALF_WIDTH
            )
            east_mask = (longitude >= EAST_LON_BOUNDS[0]) & (
                longitude <= EAST_LON_BOUNDS[1]
            )
            row: dict[str, float | int | str] = {
                "year": int(event),
                "group": group,
                "month": int(month),
                "warm_core_center_lon_e": center,
                "warm_core_center_depth_m": float(current.centroid_depth_m),
            }
            for band, field in fields.items():
                current_field = field[year_index, month - 1]
                for layer, depth_weights in weights.items():
                    moving = layer_ohc_per_area(
                        current_field,
                        depth_weights,
                        moving_mask,
                        weights["full_0_300"],
                    )
                    east = layer_ohc_per_area(
                        current_field,
                        depth_weights,
                        east_mask,
                        weights["full_0_300"],
                    )
                    row[f"moving_{band}_{layer}_gjm2"] = moving
                    row[f"east_{band}_{layer}_gjm2"] = east
                    if layer == "core_150_250":
                        thickness = LAYER_BOUNDS[layer][1] - LAYER_BOUNDS[layer][0]
                        row[f"moving_{band}_core_150_250_mjm3"] = moving * 1000.0 / thickness
            rows.append(row)
    table = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    expected_rows = len(EVENTS) * len(MONTHS)
    if len(table) != expected_rows:
        raise ValueError(f"Unexpected monthly row count: {len(table)} != {expected_rows}")
    numeric = table.select_dtypes(include=[np.number])
    if numeric.isna().any().any():
        raise ValueError(f"Missing monthly values: {numeric.columns[numeric.isna().any()].tolist()}")
    return table


def residualize(values: np.ndarray, controls: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    controls = np.asarray(controls, dtype=float)
    if controls.ndim == 1:
        controls = controls[:, None]
    if controls.shape[1] == 0:
        return values - values.mean()
    design = np.column_stack([np.ones(len(values)), controls])
    return values - design @ np.linalg.lstsq(design, values, rcond=None)[0]


def standardize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    scale = values.std(ddof=1)
    if not np.isfinite(scale) or scale < 1.0e-12:
        raise ValueError("Cannot standardize a constant series")
    return (values - values.mean()) / scale


def area_weighted_three_band(frame: pd.DataFrame, suffix: str) -> np.ndarray:
    numerator = sum(
        AREA_WEIGHTS[band] * frame[f"moving_{band}_{suffix}_gjm2"].to_numpy(dtype=float)
        for band in BAND_ORDER
    )
    return numerator / sum(AREA_WEIGHTS.values())


def add_window_metrics(event_table: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    output = event_table.copy()
    windows = {"jf": (1, 2), "jfm": (1, 2, 3), "fma": (2, 3, 4)}
    for label, months in windows.items():
        means = (
            monthly.loc[monthly.month.isin(months)]
            .groupby("year")
            .mean(numeric_only=True)
            .reindex(EVENTS)
        )
        for band in BAND_ORDER:
            for layer in LAYER_BOUNDS:
                column = f"moving_{band}_{layer}_gjm2"
                output[f"{column}_{label}"] = means[column].to_numpy(dtype=float)
            output[f"moving_{band}_core_150_250_mjm3_{label}"] = means[
                f"moving_{band}_core_150_250_mjm3"
            ].to_numpy(dtype=float)

        total_full = area_weighted_three_band(means, "full_0_300")
        off_full = 0.5 * (
            means["moving_south_full_0_300_gjm2"].to_numpy(dtype=float)
            + means["moving_north_full_0_300_gjm2"].to_numpy(dtype=float)
        )
        total_deep = area_weighted_three_band(means, "deep_100_300")
        off_deep = 0.5 * (
            means["moving_south_deep_100_300_gjm2"].to_numpy(dtype=float)
            + means["moving_north_deep_100_300_gjm2"].to_numpy(dtype=float)
        )
        output[f"total_full_0_300_gjm2_{label}"] = total_full
        output[f"offeq_full_0_300_gjm2_{label}"] = off_full
        output[f"total_deep_100_300_gjm2_{label}"] = total_deep
        output[f"offeq_deep_100_300_gjm2_{label}"] = off_deep
        output[f"broadening_residual_full_gjm2_{label}"] = residualize(
            off_full, total_full[:, None]
        )
        output[f"broadening_residual_deep_gjm2_{label}"] = residualize(
            off_deep, total_deep[:, None]
        )
        eq_surface = means["moving_eq_surface_0_100_gjm2"].to_numpy(dtype=float)
        eq_full = means["moving_eq_full_0_300_gjm2"].to_numpy(dtype=float)
        exposure = residualize(eq_surface, eq_full[:, None])
        output[f"surface_exposure_residual_eq_gjm2_{label}"] = exposure
        output[f"burial_residual_eq_gjm2_{label}"] = -exposure
        output[f"south_minus_north_full_gjm2_{label}"] = (
            means["moving_south_full_0_300_gjm2"].to_numpy(dtype=float)
            - means["moving_north_full_0_300_gjm2"].to_numpy(dtype=float)
        )
        output[f"broad_buried_score_{label}"] = 0.5 * (
            standardize(output[f"broadening_residual_full_gjm2_{label}"])
            + standardize(output[f"burial_residual_eq_gjm2_{label}"])
        )

    january = monthly.loc[monthly.month.eq(1)].set_index("year").reindex(EVENTS)
    april = monthly.loc[monthly.month.eq(4)].set_index("year").reindex(EVENTS)
    for band in BAND_ORDER:
        column = f"east_{band}_full_0_300_gjm2"
        output[f"east_{band}_delta_jan_apr_gjm2"] = (
            april[column] - january[column]
        ).to_numpy(dtype=float)
    east_total = sum(
        AREA_WEIGHTS[band] * output[f"east_{band}_delta_jan_apr_gjm2"].to_numpy(dtype=float)
        for band in BAND_ORDER
    ) / sum(AREA_WEIGHTS.values())
    east_off = 0.5 * (
        output["east_south_delta_jan_apr_gjm2"].to_numpy(dtype=float)
        + output["east_north_delta_jan_apr_gjm2"].to_numpy(dtype=float)
    )
    output["east_total_delta_jan_apr_gjm2"] = east_total
    output["east_offeq_delta_jan_apr_gjm2"] = east_off
    output["east_broadening_residual_jan_apr_gjm2"] = residualize(
        east_off, east_total[:, None]
    )
    return output


def build_event_table(monthly: pd.DataFrame) -> pd.DataFrame:
    coupling = pd.read_csv(COUPLING_CSV)
    required_seasons = {"AMJ", "JJA", "SON", "DJF"}
    if set(coupling.season.unique()) != required_seasons:
        raise ValueError(f"Unexpected coupling seasons: {set(coupling.season.unique())}")
    if coupling.duplicated(["year", "season"]).any():
        raise ValueError("Duplicate coupling event-season rows")
    manifest = coupling.loc[coupling.season.eq("DJF"), ["year", "group"]].copy()
    manifest = manifest.set_index("year").reindex(EVENTS).reset_index()
    event_table = manifest
    ocean_columns = ["q140_mar_apr_z", "d140_mar_apr_z", "east_ocean_state_z"]
    ocean = coupling.loc[coupling.season.eq("DJF"), ["year", *ocean_columns]]
    event_table = event_table.merge(ocean, on="year", validate="one_to_one")
    outcome_columns = [
        "coupling_pattern_residual_z",
        "tau_pattern_residual_z",
        "sst_to_precip_residual_z",
        "slp_to_tau_residual_z",
        "precip_pattern_residual_z",
    ]
    for season in ("AMJ", "JJA", "SON", "DJF"):
        selected = coupling.loc[coupling.season.eq(season), ["year", *outcome_columns]].copy()
        selected = selected.rename(
            columns={column: f"{column}_{season.lower()}" for column in outcome_columns}
        )
        event_table = event_table.merge(selected, on="year", validate="one_to_one")
    old_partition = pd.read_csv(OLD_PARTITION_CSV)[
        ["year", "partition_north_given_total_jan_apr_zj"]
    ]
    event_table = event_table.merge(old_partition, on="year", validate="one_to_one")
    event_table = add_window_metrics(event_table, monthly)
    numeric = event_table.select_dtypes(include=[np.number])
    if len(event_table) != len(EVENTS) or numeric.isna().any().any():
        raise ValueError("Event table is incomplete")
    return event_table


def fdr_bh(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * len(p) / np.arange(1, len(p) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def relationship(
    frame: pd.DataFrame,
    *,
    test_id: str,
    family: str,
    label: str,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...] = (),
    seed_offset: int = 0,
) -> dict[str, float | int | str]:
    data = frame[["year", x_name, y_name, *controls]].dropna().reset_index(drop=True)
    x = data[x_name].to_numpy(dtype=float)
    y = data[y_name].to_numpy(dtype=float)
    c = data[list(controls)].to_numpy(dtype=float) if controls else np.zeros((len(data), 0))
    xr = residualize(x, c)
    yr = residualize(y, c)
    observed = float(np.corrcoef(xr, yr)[0, 1])
    degrees = len(data) - len(controls) - 2
    t_value = observed * np.sqrt(degrees / max(1.0e-15, 1.0 - observed**2))
    analytic_p = float(2.0 * stats.t.sf(abs(t_value), degrees))
    spearman = float(stats.spearmanr(xr, yr).statistic)
    rng = np.random.default_rng(SEED + seed_offset)
    permutations = np.empty(N_PERMUTATIONS)
    for index in range(N_PERMUTATIONS):
        permutations[index] = np.corrcoef(xr, rng.permutation(yr))[0, 1]
    permutation_p = float(
        (np.sum(np.abs(permutations) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1)
    )
    bootstrap = np.full(N_BOOTSTRAP, np.nan)
    for index in range(N_BOOTSTRAP):
        sample = rng.integers(0, len(data), len(data))
        xbr = residualize(x[sample], c[sample])
        ybr = residualize(y[sample], c[sample])
        if np.std(xbr) > 0 and np.std(ybr) > 0:
            bootstrap[index] = np.corrcoef(xbr, ybr)[0, 1]
    ci_low, ci_high = np.nanpercentile(bootstrap, [2.5, 97.5])
    loeo: list[float] = []
    for omitted in range(len(data)):
        keep = np.arange(len(data)) != omitted
        xkr = residualize(x[keep], c[keep])
        ykr = residualize(y[keep], c[keep])
        loeo.append(float(np.corrcoef(xkr, ykr)[0, 1]))
    return {
        "test_id": test_id,
        "family": family,
        "label": label,
        "x": x_name,
        "y": y_name,
        "controls": ";".join(controls),
        "n_events": len(data),
        "partial_r": observed,
        "partial_spearman_r": spearman,
        "analytic_p": analytic_p,
        "permutation_p": permutation_p,
        "bootstrap_ci_low": float(ci_low),
        "bootstrap_ci_high": float(ci_high),
        "loeo_r_min": float(np.min(loeo)),
        "loeo_r_max": float(np.max(loeo)),
    }


def build_relationships(events: pd.DataFrame) -> pd.DataFrame:
    tests: list[tuple[str, str, str, str, str, tuple[str, ...]]] = [
        (
            "component_broadening", "component_primary", "JFM off-equatorial broadening -> JJA coupling",
            "offeq_full_0_300_gjm2_jfm", "coupling_pattern_residual_z_jja", ("total_full_0_300_gjm2_jfm",),
        ),
        (
            "component_exposure", "component_primary", "JFM equatorial surface exposure -> JJA coupling",
            "moving_eq_surface_0_100_gjm2_jfm", "coupling_pattern_residual_z_jja", ("moving_eq_full_0_300_gjm2_jfm",),
        ),
        (
            "component_asymmetry", "component_primary", "JFM south-minus-north asymmetry -> JJA coupling",
            "south_minus_north_full_gjm2_jfm", "coupling_pattern_residual_z_jja", ("offeq_full_0_300_gjm2_jfm",),
        ),
        (
            "component_composite", "component_exploratory", "JFM broad-and-buried score -> JJA coupling",
            "broad_buried_score_jfm", "coupling_pattern_residual_z_jja", (),
        ),
    ]
    for season in ("amj", "jja", "son", "djf"):
        tests.append(
            (
                f"broadening_coupling_{season}", "seasonal_broadening",
                f"JFM broadening -> {season.upper()} coupling residual",
                "offeq_full_0_300_gjm2_jfm", f"coupling_pattern_residual_z_{season}",
                ("total_full_0_300_gjm2_jfm",),
            )
        )
    mechanism_tests = [
        ("broadening_tau_amj", "JFM broadening -> AMJ wind-stress residual", "tau_pattern_residual_z_amj"),
        ("broadening_tau_jja", "JFM broadening -> JJA wind-stress residual", "tau_pattern_residual_z_jja"),
        ("broadening_precip_son", "JFM broadening -> SON SST-to-precip residual", "sst_to_precip_residual_z_son"),
        ("broadening_precip_djf", "JFM broadening -> DJF SST-to-precip residual", "sst_to_precip_residual_z_djf"),
    ]
    for test_id, label, y_name in mechanism_tests:
        tests.append(
            (
                test_id, "mechanism_links", label,
                "offeq_full_0_300_gjm2_jfm", y_name, ("total_full_0_300_gjm2_jfm",),
            )
        )
    rows = [
        relationship(
            events,
            test_id=test_id,
            family=family,
            label=label,
            x_name=x_name,
            y_name=y_name,
            controls=controls,
            seed_offset=index,
        )
        for index, (test_id, family, label, x_name, y_name, controls) in enumerate(tests)
    ]
    output = pd.DataFrame(rows)
    output["permutation_q_fdr"] = np.nan
    for family in output.family.unique():
        mask = output.family.eq(family)
        output.loc[mask, "permutation_q_fdr"] = fdr_bh(
            output.loc[mask, "permutation_p"].to_numpy(dtype=float)
        )
    return output


def build_sensitivity(events: pd.DataFrame) -> pd.DataFrame:
    tests = [
        (
            "window_jf_to_jja", "JF moving window -> JJA coupling",
            "offeq_full_0_300_gjm2_jf", "coupling_pattern_residual_z_jja",
            ("total_full_0_300_gjm2_jf",),
        ),
        (
            "window_jfm_to_jja", "JFM moving window -> JJA coupling",
            "offeq_full_0_300_gjm2_jfm", "coupling_pattern_residual_z_jja",
            ("total_full_0_300_gjm2_jfm",),
        ),
        (
            "window_fma_to_jja", "FMA moving window -> JJA coupling",
            "offeq_full_0_300_gjm2_fma", "coupling_pattern_residual_z_jja",
            ("total_full_0_300_gjm2_fma",),
        ),
        (
            "control_q140", "JFM broadening -> JJA coupling; +Q140 control",
            "offeq_full_0_300_gjm2_jfm", "coupling_pattern_residual_z_jja",
            ("total_full_0_300_gjm2_jfm", "q140_mar_apr_z"),
        ),
        (
            "control_d20", "JFM broadening -> JJA coupling; +D20 control",
            "offeq_full_0_300_gjm2_jfm", "coupling_pattern_residual_z_jja",
            ("total_full_0_300_gjm2_jfm", "d140_mar_apr_z"),
        ),
        (
            "control_q140_d20", "JFM broadening -> JJA coupling; +Q140+D20",
            "offeq_full_0_300_gjm2_jfm", "coupling_pattern_residual_z_jja",
            ("total_full_0_300_gjm2_jfm", "q140_mar_apr_z", "d140_mar_apr_z"),
        ),
        (
            "deep_only", "JFM deep broadening -> JJA coupling",
            "offeq_deep_100_300_gjm2_jfm", "coupling_pattern_residual_z_jja",
            ("total_deep_100_300_gjm2_jfm",),
        ),
        (
            "fixed_east_delta", "East-box Jan-Apr off-equatorial warming -> JJA coupling",
            "east_offeq_delta_jan_apr_gjm2", "coupling_pattern_residual_z_jja",
            ("east_total_delta_jan_apr_gjm2",),
        ),
    ]
    rows = [
        relationship(
            events,
            test_id=test_id,
            family="sensitivity",
            label=label,
            x_name=x_name,
            y_name=y_name,
            controls=controls,
            seed_offset=200 + index,
        )
        for index, (test_id, label, x_name, y_name, controls) in enumerate(tests)
    ]
    output = pd.DataFrame(rows)
    output["permutation_q_fdr"] = fdr_bh(output.permutation_p.to_numpy(dtype=float))
    return output


def plot_main(events: pd.DataFrame, relationships: pd.DataFrame) -> None:
    apply_climate_style(10)
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.8))
    ax_heat, ax_scatter, ax_components, ax_seasons = axes.flat

    heat_columns = [
        "moving_eq_surface_0_100_gjm2_jfm", "moving_eq_deep_100_300_gjm2_jfm",
        "moving_south_surface_0_100_gjm2_jfm", "moving_south_deep_100_300_gjm2_jfm",
        "moving_north_surface_0_100_gjm2_jfm", "moving_north_deep_100_300_gjm2_jfm",
    ]
    selected = events.set_index("year").loc[list(HIGHLIGHTS), heat_columns]
    values = selected.to_numpy(dtype=float)
    limit = float(np.nanmax(np.abs(values)))
    image = ax_heat.imshow(
        values,
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit),
        aspect="auto",
    )
    ax_heat.set_xticks(range(len(heat_columns)))
    ax_heat.set_xticklabels(
        ["Eq\n0-100", "Eq\n100-300", "5-15S\n0-100", "5-15S\n100-300", "5-15N\n0-100", "5-15N\n100-300"]
    )
    ax_heat.set_yticks(range(len(HIGHLIGHTS)))
    ax_heat.set_yticklabels([str(year) for year in HIGHLIGHTS])
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            color = "white" if abs(values[row, column]) > 0.58 * limit else "black"
            ax_heat.text(column, row, f"{values[row, column]:+.2f}", ha="center", va="center", color=color, fontsize=8.7)
    ax_heat.set_title("JFM warm-core geometry: 2023 is broad and subsurface-heavy")
    cbar = fig.colorbar(image, ax=ax_heat, orientation="horizontal", fraction=0.08, pad=0.15)
    cbar.set_label("OHC anomaly per area (GJ m$^{-2}$)")

    total = events["total_full_0_300_gjm2_jfm"].to_numpy(dtype=float)
    x = residualize(events["offeq_full_0_300_gjm2_jfm"].to_numpy(dtype=float), total[:, None])
    y = residualize(events["coupling_pattern_residual_z_jja"].to_numpy(dtype=float), total[:, None])
    ax_scatter.scatter(x, y, color="0.62", s=38, zorder=2)
    slope, intercept = np.polyfit(x, y, 1)
    xx = np.linspace(x.min(), x.max(), 100)
    ax_scatter.plot(xx, slope * xx + intercept, color="0.18", linewidth=1.5)
    for index, year in enumerate(events.year):
        if int(year) in HIGHLIGHTS:
            color = COLORS[int(year)]
            ax_scatter.scatter(x[index], y[index], s=75, color=color, edgecolor="white", linewidth=0.8, zorder=4)
            ax_scatter.annotate(str(int(year)), (x[index], y[index]), xytext=(5, 5), textcoords="offset points", color=color, fontweight="bold")
    primary = relationships.loc[relationships.test_id.eq("component_broadening")].iloc[0]
    ax_scatter.text(
        0.04, 0.96,
        f"partial r = {primary.partial_r:+.2f}\nperm p = {primary.permutation_p:.3f}\nFDR q = {primary.permutation_q_fdr:.3f}",
        transform=ax_scatter.transAxes, ha="left", va="top",
    )
    ax_scatter.axhline(0, color="0.78", linewidth=0.8)
    ax_scatter.axvline(0, color="0.78", linewidth=0.8)
    ax_scatter.set_xlabel("JFM off-equatorial broadening residual (GJ m$^{-2}$)")
    ax_scatter.set_ylabel("JJA coupling residual after total-OHC control (z)")
    ax_scatter.set_title("More meridional broadening precedes weaker JJA coupling")

    component_ids = ["component_broadening", "component_exposure", "component_asymmetry", "component_composite"]
    component_labels = ["Meridional broadening", "Equatorial surface exposure", "South-minus-north", "Broad + buried (exploratory)"]
    comp = relationships.set_index("test_id").loc[component_ids]
    ypos = np.arange(len(comp))[::-1]
    ax_components.errorbar(
        comp.partial_r,
        ypos,
        xerr=np.vstack([
            comp.partial_r - comp.bootstrap_ci_low,
            comp.bootstrap_ci_high - comp.partial_r,
        ]),
        fmt="o",
        color="#365f91",
        ecolor="#88a3c2",
        capsize=3,
    )
    ax_components.axvline(0, color="0.25", linewidth=0.8)
    ax_components.set_yticks(ypos)
    ax_components.set_yticklabels(component_labels)
    ax_components.set_xlim(-1.05, 1.05)
    ax_components.set_xlabel("Partial correlation with JJA coupling residual")
    ax_components.set_title("Broadening is the cross-event component with clear support")
    ax_components.grid(axis="x", color="0.9", linewidth=0.7)

    seasonal_ids = [f"broadening_coupling_{season}" for season in ("amj", "jja", "son", "djf")]
    seasonal = relationships.set_index("test_id").loc[seasonal_ids]
    xpos = np.arange(4)
    ax_seasons.errorbar(
        xpos,
        seasonal.partial_r,
        yerr=np.vstack([
            seasonal.partial_r - seasonal.bootstrap_ci_low,
            seasonal.bootstrap_ci_high - seasonal.partial_r,
        ]),
        color="#b23a3a",
        marker="o",
        capsize=3,
    )
    ax_seasons.axhline(0, color="0.25", linewidth=0.8)
    ax_seasons.set_xticks(xpos)
    ax_seasons.set_xticklabels(["AMJ", "JJA", "SON", "DJF"])
    ax_seasons.set_ylim(-1.05, 0.65)
    ax_seasons.set_ylabel("Partial correlation")
    ax_seasons.set_title("The broadening signal is strongest in early coupling seasons")
    ax_seasons.grid(axis="y", color="0.9", linewidth=0.7)

    add_panel_labels(axes.flat)
    fig.suptitle(
        "Early warm-heat spreading and later air-sea decoupling across 13 ENSO events",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.005,
        f"SODA3.15.2; JFM moving warm-core window (centroid +/-10 deg); ocean anomalies detrended by calendar month over {BASELINE[0]}-{BASELINE[1]}. Coupling residuals already adjust for SST amplitude and EP-CP pattern.",
        ha="center",
        va="bottom",
        fontsize=8.4,
        color="0.35",
    )
    fig.subplots_adjust(top=0.91, bottom=0.10, hspace=0.42, wspace=0.32)
    save_figure(fig, FIG_PNG)
    save_figure(fig, FIG_PDF)
    plt.close(fig)


def plot_robustness(sensitivity: pd.DataFrame) -> None:
    apply_climate_style(10)
    fig, ax = plt.subplots(figsize=(10.8, 5.6))
    table = sensitivity.copy()
    ypos = np.arange(len(table))[::-1]
    colors = ["#365f91" if not test.startswith("control") else "#b23a3a" for test in table.test_id]
    for index, row in enumerate(table.itertuples()):
        ax.errorbar(
            row.partial_r,
            ypos[index],
            xerr=[[row.partial_r - row.bootstrap_ci_low], [row.bootstrap_ci_high - row.partial_r]],
            fmt="o",
            color=colors[index],
            ecolor=colors[index],
            alpha=0.9,
            capsize=3,
        )
    ax.axvline(0, color="0.2", linewidth=0.9)
    ax.set_yticks(ypos)
    ax.set_yticklabels(table.label)
    ax.set_xlim(-1.05, 1.05)
    ax.set_xlabel("Partial correlation with JJA coupling residual")
    ax.set_title("Window, control, depth, and fixed-east sensitivity")
    ax.grid(axis="x", color="0.9", linewidth=0.7)
    fig.suptitle("Robustness of the warm-heat broadening signal", fontsize=15, fontweight="bold", y=0.98)
    fig.subplots_adjust(left=0.46, right=0.97, top=0.86, bottom=0.12)
    save_figure(fig, ROBUST_PNG)
    save_figure(fig, ROBUST_PDF)
    plt.close(fig)


def plot_cross_event_support(
    events: pd.DataFrame, relationships: pd.DataFrame
) -> None:
    """Create the single-claim scatter used in the Chinese stage report."""

    apply_climate_style(11)
    plt.rcParams.update(
        {
            "font.sans-serif": [
                "DejaVu Sans",
                "Arial",
                "Helvetica",
            ]
        }
    )
    fig, ax = plt.subplots(figsize=(9.4, 6.6))
    total = events["total_full_0_300_gjm2_jfm"].to_numpy(dtype=float)
    x = residualize(
        events["offeq_full_0_300_gjm2_jfm"].to_numpy(dtype=float),
        total[:, None],
    )
    y = residualize(
        events["coupling_pattern_residual_z_jja"].to_numpy(dtype=float),
        total[:, None],
    )

    grid = np.linspace(x.min() - 0.01, x.max() + 0.01, 200)
    slope, intercept = np.polyfit(x, y, 1)
    rng = np.random.default_rng(SEED + 500)
    bootstrap_lines = []
    for _ in range(2_000):
        sample = rng.integers(0, len(events), len(events))
        if np.unique(x[sample]).size < 2:
            continue
        boot_slope, boot_intercept = np.polyfit(x[sample], y[sample], 1)
        bootstrap_lines.append(boot_slope * grid + boot_intercept)
    line_low, line_high = np.percentile(np.asarray(bootstrap_lines), [2.5, 97.5], axis=0)
    ax.fill_between(
        grid,
        line_low,
        line_high,
        color="#9aa0a6",
        alpha=0.20,
        linewidth=0,
        label="Event-resampled 95% regression interval",
    )
    ax.plot(grid, slope * grid + intercept, color="#2f2f2f", linewidth=2.0)

    label_offsets = {
        1982: (-23, -2),
        1986: (-24, -2),
        1991: (6, -8),
        1994: (7, 5),
        1997: (7, 4),
        2002: (-24, -10),
        2004: (-32, 7),
        2006: (-25, 7),
        2009: (6, -9),
        2015: (7, -5),
        2018: (5, 9),
        2019: (6, 5),
        2023: (7, 5),
    }
    for index, year_value in enumerate(events.year.to_numpy(dtype=int)):
        color = COLORS.get(year_value, "#737373")
        size = 86 if year_value in HIGHLIGHTS else 55
        ax.scatter(
            x[index],
            y[index],
            s=size,
            color=color,
            edgecolor="white",
            linewidth=0.9,
            zorder=3,
        )
        ax.annotate(
            str(year_value),
            (x[index], y[index]),
            xytext=label_offsets[year_value],
            textcoords="offset points",
            color=color,
            fontsize=9.4 if year_value in HIGHLIGHTS else 8.3,
            fontweight="bold" if year_value in HIGHLIGHTS else "normal",
        )

    primary = relationships.loc[
        relationships.test_id.eq("component_broadening")
    ].iloc[0]
    stats_text = (
        f"N = {int(primary.n_events)}\n"
        f"Partial r = {primary.partial_r:+.2f}\n"
        f"Residual rank r = {primary.partial_spearman_r:+.2f}\n"
        f"Permutation p = {primary.permutation_p:.3f}\n"
        f"FDR q = {primary.permutation_q_fdr:.3f}\n"
        f"Leave-one-event-out r = {primary.loeo_r_min:+.2f} to {primary.loeo_r_max:+.2f}"
    )
    ax.text(
        0.97,
        0.96,
        stats_text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10.2,
        bbox={
            "boxstyle": "round,pad=0.45",
            "facecolor": "white",
            "edgecolor": "#bdbdbd",
            "alpha": 0.94,
        },
    )
    ax.axhline(0, color="#bdbdbd", linewidth=0.9, zorder=0)
    ax.axvline(0, color="#bdbdbd", linewidth=0.9, zorder=0)
    ax.grid(color="#ececec", linewidth=0.7, zorder=0)
    ax.set_xlabel(
        "JFM off-equatorial OHC residual\n"
        "(three-band area-weighted mean OHC controlled; GJ m$^{-2}$)",
        labelpad=8,
    )
    ax.set_ylabel(
        "JJA pattern-adjusted coupling residual\n"
        "(three-band area-weighted mean OHC additionally controlled; z)",
        labelpad=8,
    )
    fig.suptitle(
        "Early meridional ocean-heat spreading is linked to weaker-than-expected coupling",
        x=0.14,
        y=0.975,
        ha="left",
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.14,
        0.905,
        "13 ENSO warm events: JFM warm-core geometry → JJA development-stage air–sea response",
        ha="left",
        va="bottom",
        fontsize=10.5,
        color="#555555",
    )
    fig.text(
        0.5,
        0.015,
        f"Ocean: SODA3.15.2, warm-core centroid ±10° longitude, 5°S–15°N, 0–300 m; calendar-month linear detrending over {BASELINE[0]}–{BASELINE[1]}.\n"
        "Coupling residuals adjust for SST amplitude and EP–CP pattern; shading shows the event-resampled 95% regression interval.",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#555555",
    )
    fig.subplots_adjust(left=0.14, right=0.97, top=0.83, bottom=0.16)
    save_figure(fig, CROSS_EVENT_PNG)
    save_figure(fig, CROSS_EVENT_PDF)
    plt.close(fig)


def fmt_relation(row: pd.Series) -> str:
    return (
        f"r={row.partial_r:+.2f}, permutation p={row.permutation_p:.3f}, "
        f"FDR q={row.permutation_q_fdr:.3f}, 95% CI "
        f"[{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}], "
        f"LOEO [{row.loeo_r_min:+.2f}, {row.loeo_r_max:+.2f}]"
    )


def write_report(events: pd.DataFrame, relationships: pd.DataFrame, sensitivity: pd.DataFrame) -> None:
    rel = relationships.set_index("test_id")
    sen = sensitivity.set_index("test_id")
    highlights = events.set_index("year").loc[list(HIGHLIGHTS)]
    target = highlights.loc[2023]
    broad_rank = int(
        events["broadening_residual_full_gjm2_jfm"].rank(ascending=False, method="min").loc[
            events.year.eq(2023)
        ].iloc[0]
    )
    burial_rank = int(
        events["burial_residual_eq_gjm2_jfm"].rank(ascending=False, method="min").loc[
            events.year.eq(2023)
        ].iloc[0]
    )
    rows = []
    for year in HIGHLIGHTS:
        current = highlights.loc[year]
        rows.append(
            f"| {year} | {current.moving_eq_surface_0_100_gjm2_jfm:+.3f} | "
            f"{current.moving_eq_deep_100_300_gjm2_jfm:+.3f} | "
            f"{current.moving_south_full_0_300_gjm2_jfm:+.3f} | "
            f"{current.moving_north_full_0_300_gjm2_jfm:+.3f} | "
            f"{current.broadening_residual_full_gjm2_jfm:+.3f} | "
            f"{current.coupling_pattern_residual_z_jja:+.2f} |"
        )
    report = f"""# 暖量三维展宽与2023海气脱耦：13事件诊断

## 结论先行

本次计算对“赤道仍有暖量，但暖异常更宽、更深，赤道表层可利用比例降低”给出**部分支持**：

1. 13事件中，最稳定的跨事件信号是**经向展宽**。在固定暖核三纬带总OHC后，1—3月离赤道暖量越多，JJA型态调整后的综合耦合响应越弱（{fmt_relation(rel.loc['component_broadening'])}）。
2. 2023同时表现为强次表层储热、赤道上100 m偏冷和明显南侧展宽；但“表层暴露不足”与“南北不对称”单独并未在13事件中形成同样稳定的耦合关系。
3. 因而当前最稳妥的新表述是：**三维结构中的经向展宽是有跨事件支持的早期候选脱耦条件；深埋和南偏在2023个例中很突出，但尚未证明是普适控制量。**

## 1. 指标定义

- 事件：13次暖事件，1982—2023；
- 原因窗：1—3月，严格早于JJA结果窗；
- 经度：每个事件已有赤道正OHC质心±10°；
- 纬带：5°S—5°N、5°—15°S、5°—15°N；
- 垂向：0—100 m、100—300 m、0—300 m；
- 异常：1980—2024同历月线性去趋势；
- 经向展宽：离赤道两纬带平均OHC在固定三纬带总OHC后的回归残差；
- 表层暴露：赤道0—100 m OHC在固定赤道0—300 m OHC后的残差，负值表示更埋藏；
- 南北不对称：南侧减北侧0—300 m OHC；
- 结果量：已控制SST幅度和EP—CP空间型态的耦合残差。

这里使用条件残差，不使用可能在零附近失稳的“表层/总量”比值。

## 2. 1997、2015和2023的1—3月暖核结构

| 事件 | 赤道0—100 m | 赤道100—300 m | 南侧0—300 m | 北侧0—300 m | 经向展宽残差 | JJA耦合残差 |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

单位：海洋量为GJ m⁻²，耦合残差为z。

2023赤道0—100 m为 **{target.moving_eq_surface_0_100_gjm2_jfm:+.3f} GJ m⁻²**，但100—300 m为 **{target.moving_eq_deep_100_300_gjm2_jfm:+.3f} GJ m⁻²**；南侧和北侧0—300 m分别为 **{target.moving_south_full_0_300_gjm2_jfm:+.3f}** 和 **{target.moving_north_full_0_300_gjm2_jfm:+.3f} GJ m⁻²**。2023经向展宽残差在13事件中排名 **{broad_rank}/13**，埋藏残差排名 **{burial_rank}/13**。

## 3. 三个候选分量的检验

- 经向展宽 → JJA耦合：{fmt_relation(rel.loc['component_broadening'])}；残差秩相关为 {rel.loc['component_broadening'].partial_spearman_r:+.2f}。
- 赤道表层暴露 → JJA耦合：{fmt_relation(rel.loc['component_exposure'])}。
- 南减北不对称 → JJA耦合：{fmt_relation(rel.loc['component_asymmetry'])}。
- “展宽+埋藏”等权辅助量：{fmt_relation(rel.loc['component_composite'])}。该量没有调权，只作摘要，不作为新阈值。

这组结果把“2023很深、很偏南”和“跨事件可重复关系”区分开：2023个例同时具有三种特征，但样本内真正稳定对应较弱JJA耦合的是离赤道总展宽，而不是南偏方向或表层暴露单项。

## 4. 时间演变

- AMJ综合耦合：{fmt_relation(rel.loc['broadening_coupling_amj'])}；
- JJA综合耦合：{fmt_relation(rel.loc['broadening_coupling_jja'])}；
- SON综合耦合：{fmt_relation(rel.loc['broadening_coupling_son'])}；
- DJF综合耦合：{fmt_relation(rel.loc['broadening_coupling_djf'])}。

展宽关系在AMJ—JJA最强，之后减弱。这符合“早期海洋几何影响接通阶段，但成熟期还受到外海盆、背景SST、对流和大气内部变率控制”的解释。

## 5. 稳健性边界

- JF原因窗：{fmt_relation(sen.loc['window_jf_to_jja'])}；
- JFM原因窗：{fmt_relation(sen.loc['window_jfm_to_jja'])}；
- FMA原因窗：{fmt_relation(sen.loc['window_fma_to_jja'])}；
- 加Q140控制：{fmt_relation(sen.loc['control_q140'])}；
- 加D20控制：{fmt_relation(sen.loc['control_d20'])}；
- 同时控制Q140和D20：{fmt_relation(sen.loc['control_q140_d20'])}；
- 只用100—300 m展宽：{fmt_relation(sen.loc['deep_only'])}；
- 固定140°W—80°W东部箱Jan→Apr展宽：{fmt_relation(sen.loc['fixed_east_delta'])}。

控制项较多时自由度很低，三控制结果只能视为方向检查。固定东部箱与暖核随动窗若强度不同，说明“暖核附近早期几何”和“东部后续到达”不是同一个指标。

## 6. 与此前分箱结果的关系

此前赤道—北侧H20分箱已经显示2023 Jan→Apr赤道增加约+3.04 ZJ、北侧增加+0.86 ZJ；1997和2015北侧同期为负。本次增加南侧并使用暖核随动窗后，检验对象从“偏北份额”扩展为“离赤道总展宽”。二者不是互相替代：北侧H20描述东部接收箱命运，三纬带OHC描述早期暖核的经向几何。

## 7. 可以说与不能说

可以说：在总暖量相近时，早期暖核附近更多OHC配置到赤道两侧，与随后较弱的型态调整后海气耦合响应稳定相关；2023同时表现出强烈的次表层埋藏和南侧展宽。

不能说：欧拉分箱已经证明同一水团发生湍流“扩散”，或已经证明经向展宽单向造成脱耦。当前结果仍可能包含水平平流、温跃层下沉、波动调整和共同风强迫；13事件也限制了多变量因果识别。

推荐机制表述：

> 2023年初赤道暖量并未耗尽，但暖核表现出更强的离赤道展宽和次表层储存。跨13事件，在固定总暖量后，类似的经向展宽稳定对应随后较弱的早期海气耦合响应，提示暖量空间集中度可能影响海洋热储备向赤道表层—对流—风反馈的转化效率。

## 输出

- 主图：`{FIG_PNG}`
- 跨事件支撑单图：`{CROSS_EVENT_PNG}`
- 稳健性图：`{ROBUST_PNG}`
- 事件表：`{EVENT_CSV}`
- 月表：`{MONTHLY_CSV}`
- 关系统计：`{RELATIONSHIP_CSV}`
- 敏感性：`{SENSITIVITY_CSV}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def validate_outputs(
    monthly: pd.DataFrame,
    events: pd.DataFrame,
    relationships: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> dict[str, object]:
    for name, frame in (
        ("monthly", monthly),
        ("events", events),
        ("relationships", relationships),
        ("sensitivity", sensitivity),
    ):
        numeric = frame.select_dtypes(include=[np.number])
        if numeric.isna().any().any():
            raise ValueError(f"{name} output contains missing numeric values")
    closure_errors = []
    for sampling in ("moving", "east"):
        for band in BAND_ORDER:
            closure_errors.append(
                np.abs(
                    monthly[f"{sampling}_{band}_full_0_300_gjm2"]
                    - monthly[f"{sampling}_{band}_surface_0_100_gjm2"]
                    - monthly[f"{sampling}_{band}_deep_100_300_gjm2"]
                ).to_numpy(dtype=float)
            )
    closure = float(np.max(np.concatenate(closure_errors)))
    if closure > 1.0e-10:
        raise ValueError(f"Vertical OHC layers do not close: {closure}")
    primary = relationships.loc[relationships.test_id.eq("component_broadening")].iloc[0]
    return {
        "analysis_version": "20260818_v2",
        "event_count": len(events),
        "monthly_rows": len(monthly),
        "relationship_rows": len(relationships),
        "sensitivity_rows": len(sensitivity),
        "ocean_baseline": list(BASELINE),
        "moving_window_half_width_deg": WINDOW_HALF_WIDTH,
        "common_full_depth_column_mask": True,
        "max_vertical_layer_closure_gjm2": float(closure),
        "primary_partial_r": float(primary.partial_r),
        "primary_partial_spearman_r": float(primary.partial_spearman_r),
        "primary_permutation_p": float(primary.permutation_p),
        "primary_fdr_q": float(primary.permutation_q_fdr),
        "primary_bootstrap_ci": [
            float(primary.bootstrap_ci_low),
            float(primary.bootstrap_ci_high),
        ],
        "primary_loeo_range": [float(primary.loeo_r_min), float(primary.loeo_r_max)],
        "sign_convention": "positive broadening residual means more off-equatorial OHC at fixed three-band total",
        "causal_limit": "diagnostic association; not a diffusion or coupled-model attribution",
    }


def main() -> int:
    require_files(
        [
            TEMP_FILE,
            CENTROID_CSV,
            COUPLING_CSV,
            OLD_PARTITION_CSV,
            *[
                OUTER_CACHE / f"soda3_four_outer_latband_sums_{year}_jan_jun.npz"
                for year in YEARS
            ],
        ]
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    fields, depth, longitude = load_anomaly_fields()
    monthly = build_monthly_table(fields, depth, longitude)
    events = build_event_table(monthly)
    relationships = build_relationships(events)
    sensitivity = build_sensitivity(events)
    diagnostics = validate_outputs(monthly, events, relationships, sensitivity)

    monthly.to_csv(MONTHLY_CSV, index=False)
    events.to_csv(EVENT_CSV, index=False)
    relationships.to_csv(RELATIONSHIP_CSV, index=False)
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    plot_main(events, relationships)
    plot_robustness(sensitivity)
    plot_cross_event_support(events, relationships)
    write_report(events, relationships, sensitivity)
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
