#!/usr/bin/env python3
"""Diagnose leverage and metric-definition sensitivity of the ENSO OHC model.

The primary model is

    C_JJA = beta_0 + beta_1 H_3band + beta_2 D + epsilon,
    D = (H_S + H_N) / 2 - H_E.

The script separates the south and north contributions to D, evaluates all
leave-two-events-out fits, reports classical OLS influence statistics, and
constructs a positive-only sensitivity metric by clipping gridded 0--300 m
OHC anomalies at zero before spatial averaging.
"""

from __future__ import annotations

from itertools import combinations
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/enso_ohc_influence_mpl")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = (
    ROOT
    / "data/derived/research_2026/enso_report_unified_1982_2024"
)
EVENT_CSV = DERIVED / "enso_3d_warm_heat_spreading_event_metrics_1982_2024.csv"
CENTROID_CSV = DERIVED / "soda3_13_warm_events_monthly_core_centroids_1982_2024.csv"
OHC_FILE = DERIVED / "soda3_ohc300_jan_jun_30s30n_1982_2024_detrended.nc"

OUT_DIR = (
    ROOT
    / "outputs/research_2026/enso_meridional_configuration_influence_1982_2024"
)
EVENT_DIAGNOSTICS_CSV = OUT_DIR / "enso_meridional_configuration_event_diagnostics.csv"
LEAVE_TWO_CSV = OUT_DIR / "enso_leave_two_events_out.csv"
INFLUENCE_CSV = OUT_DIR / "enso_primary_model_influence_statistics.csv"
POSITIVE_ONLY_CSV = OUT_DIR / "enso_positive_only_event_metrics_1deg.csv"
SENSITIVITY_CSV = OUT_DIR / "enso_metric_definition_sensitivity.csv"
SUMMARY_JSON = OUT_DIR / "enso_meridional_configuration_influence_summary.json"
REPORT_MD = OUT_DIR / "ENSO_MERIDIONAL_CONFIGURATION_INFLUENCE_CN.md"
FIGURE_PNG = OUT_DIR / "enso_meridional_configuration_influence_diagnostics.png"
FIGURE_PDF = OUT_DIR / "enso_meridional_configuration_influence_diagnostics.pdf"

EVENTS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHTS = {1997: "#2f77b4", 2015: "#e08b19", 2023: "#c43c39"}
WINDOW_HALF_WIDTH = 10.0
BAND_BOUNDS = {
    "eq": (-5.0, 5.0),
    "south": (-15.0, -5.0),
    "north": (5.0, 15.0),
}
AREA_WEIGHTS = {
    "eq": np.sin(np.deg2rad(5.0)) - np.sin(np.deg2rad(-5.0)),
    "south": np.sin(np.deg2rad(-5.0)) - np.sin(np.deg2rad(-15.0)),
    "north": np.sin(np.deg2rad(15.0)) - np.sin(np.deg2rad(5.0)),
}


def residualize(values: np.ndarray, control: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    control = np.asarray(control, dtype=float)
    design = np.column_stack([np.ones(len(values)), control])
    return values - design @ np.linalg.lstsq(design, values, rcond=None)[0]


def fit_model(
    response: np.ndarray,
    total: np.ndarray,
    contrast: np.ndarray,
) -> tuple[dict[str, np.ndarray | float | int], float]:
    design = np.column_stack([np.ones(len(response)), total, contrast])
    coefficients = np.linalg.lstsq(design, response, rcond=None)[0]
    fitted = design @ coefficients
    residuals = response - fitted
    degrees_of_freedom = len(response) - design.shape[1]
    residual_variance = float(residuals @ residuals / degrees_of_freedom)
    inverse_xtx = np.linalg.inv(design.T @ design)
    covariance = residual_variance * inverse_xtx
    standard_errors = np.sqrt(np.diag(covariance))
    t_values = coefficients / standard_errors
    p_values = 2.0 * stats.t.sf(np.abs(t_values), degrees_of_freedom)
    t_critical = stats.t.ppf(0.975, degrees_of_freedom)
    confidence_intervals = np.column_stack(
        [
            coefficients - t_critical * standard_errors,
            coefficients + t_critical * standard_errors,
        ]
    )
    total_sum_squares = float(np.sum((response - np.mean(response)) ** 2))
    model = {
        "design": design,
        "coefficients": coefficients,
        "fitted": fitted,
        "residuals": residuals,
        "degrees_of_freedom": degrees_of_freedom,
        "residual_variance": residual_variance,
        "inverse_xtx": inverse_xtx,
        "standard_errors": standard_errors,
        "t_values": t_values,
        "p_values": p_values,
        "confidence_intervals": confidence_intervals,
        "r_squared": 1.0 - float(residuals @ residuals) / total_sum_squares,
    }
    partial_r = float(
        np.corrcoef(
            residualize(contrast, total),
            residualize(response, total),
        )[0, 1]
    )
    return model, partial_r


def model_row(
    model_id: str,
    response: np.ndarray,
    total: np.ndarray,
    contrast: np.ndarray,
    *,
    n: int | None = None,
) -> dict[str, float | int | str]:
    model, partial_r = fit_model(response, total, contrast)
    ci = model["confidence_intervals"][2]
    return {
        "model_id": model_id,
        "n": int(len(response) if n is None else n),
        "partial_r": partial_r,
        "beta_contrast": float(model["coefficients"][2]),
        "se_beta_contrast": float(model["standard_errors"][2]),
        "t_beta_contrast": float(model["t_values"][2]),
        "p_analytic_two_sided": float(model["p_values"][2]),
        "beta_contrast_ci_low": float(ci[0]),
        "beta_contrast_ci_high": float(ci[1]),
        "r_squared": float(model["r_squared"]),
    }


def signed_event_diagnostics(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    output = pd.DataFrame(
        {
            "year": events.year.astype(int),
            "H_E_gjm2": events.moving_eq_full_0_300_gjm2_jfm,
            "H_S_gjm2": events.moving_south_full_0_300_gjm2_jfm,
            "H_N_gjm2": events.moving_north_full_0_300_gjm2_jfm,
            "H_3band_gjm2": events.total_full_0_300_gjm2_jfm,
            "C_JJA_raw_z": events.coupling_pattern_residual_z_jja,
        }
    )
    output["H_off_gjm2"] = 0.5 * (output.H_S_gjm2 + output.H_N_gjm2)
    output["D_raw_gjm2"] = output.H_off_gjm2 - output.H_E_gjm2
    output["D_S_gjm2"] = output.H_S_gjm2 - output.H_E_gjm2
    output["D_N_gjm2"] = output.H_N_gjm2 - output.H_E_gjm2
    output["south_contribution_to_D_gjm2"] = 0.5 * output.D_S_gjm2
    output["north_contribution_to_D_gjm2"] = 0.5 * output.D_N_gjm2

    total = output.H_3band_gjm2.to_numpy(dtype=float)
    contrast = output.D_raw_gjm2.to_numpy(dtype=float)
    response = output.C_JJA_raw_z.to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(output)), total])
    d_coeff = np.linalg.lstsq(design, contrast, rcond=None)[0]
    c_coeff = np.linalg.lstsq(design, response, rcond=None)[0]
    output["D_hat_from_H3band_gjm2"] = design @ d_coeff
    output["D_residual_gjm2"] = contrast - output.D_hat_from_H3band_gjm2
    output["C_hat_from_H3band_z"] = design @ c_coeff
    output["C_residual_after_H3band_z"] = response - output.C_hat_from_H3band_z

    model, partial_r = fit_model(response, total, contrast)
    design_full = model["design"]
    inverse_xtx = model["inverse_xtx"]
    residuals = model["residuals"]
    residual_variance = float(model["residual_variance"])
    degrees_of_freedom = int(model["degrees_of_freedom"])
    leverage = np.einsum("ij,jk,ik->i", design_full, inverse_xtx, design_full)
    output["leverage_hii"] = leverage
    output["cooks_distance"] = (
        residuals**2
        / (design_full.shape[1] * residual_variance)
        * leverage
        / (1.0 - leverage) ** 2
    )
    deleted_residual_variance = (
        degrees_of_freedom * residual_variance
        - residuals**2 / (1.0 - leverage)
    ) / (degrees_of_freedom - 1)
    output["studentized_residual_external"] = residuals / np.sqrt(
        deleted_residual_variance * (1.0 - leverage)
    )
    coefficient_change = (
        (inverse_xtx @ design_full.T).T
        * (residuals / (1.0 - leverage))[:, None]
    )
    output["dfbeta_D"] = coefficient_change[:, 2] / np.sqrt(
        deleted_residual_variance * inverse_xtx[2, 2]
    )

    diagnostics = {
        "partial_r": partial_r,
        "beta_D": float(model["coefficients"][2]),
        "p_D": float(model["p_values"][2]),
        "mean_leverage": float(design_full.shape[1]) / len(output),
        "common_leverage_flag_2p_over_n": float(2.0 * design_full.shape[1] / len(output)),
        "common_cooks_flag_4_over_n": float(4.0 / len(output)),
        "common_abs_dfbeta_flag_2_over_sqrt_n": float(2.0 / np.sqrt(len(output))),
    }
    return output, diagnostics


def leave_two_event_out(event_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    years = event_table.year.to_numpy(dtype=int)
    response = event_table.C_JJA_raw_z.to_numpy(dtype=float)
    total = event_table.H_3band_gjm2.to_numpy(dtype=float)
    contrast = event_table.D_raw_gjm2.to_numpy(dtype=float)
    for year_a, year_b in combinations(years, 2):
        keep = ~np.isin(years, [year_a, year_b])
        row = model_row(
            f"drop_{year_a}_{year_b}",
            response[keep],
            total[keep],
            contrast[keep],
        )
        row.update(dropped_year_1=int(year_a), dropped_year_2=int(year_b))
        rows.append(row)
    return pd.DataFrame(rows)


def weighted_spatial_mean(
    field: np.ndarray,
    latitude: np.ndarray,
    lat_mask: np.ndarray,
    lon_mask: np.ndarray,
) -> float:
    selected = np.asarray(field, dtype=float)[np.ix_(lat_mask, lon_mask)]
    weights = np.cos(np.deg2rad(latitude[lat_mask]))[:, None]
    finite = np.isfinite(selected)
    numerator = np.nansum(selected * weights)
    denominator = np.sum(finite * weights)
    if denominator <= 0:
        raise ValueError("No valid ocean cells in selected warm-core window")
    return float(numerator / denominator)


def build_gridded_positive_only(events: pd.DataFrame) -> pd.DataFrame:
    centroids = pd.read_csv(CENTROID_CSV)
    if set(centroids.event.astype(int)) != set(EVENTS):
        raise ValueError("Warm-core centroid sample does not match the 13 events")

    with xr.open_dataset(OHC_FILE, engine="h5netcdf") as source:
        variable = source["ohc_300m_anomaly_detrended"]
        if variable.attrs.get("units") != "J m-2":
            raise ValueError(f"Unexpected OHC units: {variable.attrs.get('units')}")
        latitude = source.lat.values.astype(float)
        longitude = source.lon.values.astype(float)
        if not np.all(np.diff(latitude) > 0) or not np.all(np.diff(longitude) > 0):
            raise ValueError("Latitude and longitude coordinates must increase")
        selected = variable.sel(
            time=variable.time.dt.year.isin(EVENTS)
            & variable.time.dt.month.isin([1, 2, 3])
        ).load()

    rows: list[dict[str, float | int]] = []
    for year in EVENTS:
        for month in (1, 2, 3):
            current_centroid = centroids.loc[
                centroids.event.eq(year) & centroids.month.eq(month)
            ]
            if len(current_centroid) != 1:
                raise ValueError(f"Expected one centroid for {year}-{month:02d}")
            center = float(current_centroid.centroid_lon_e.iloc[0])
            lon_mask = (longitude >= center - WINDOW_HALF_WIDTH) & (
                longitude <= center + WINDOW_HALF_WIDTH
            )
            current = selected.sel(
                time=(selected.time.dt.year == year)
                & (selected.time.dt.month == month)
            )
            if current.sizes.get("time") != 1:
                raise ValueError(f"Expected one OHC field for {year}-{month:02d}")
            field = current.isel(time=0).values.astype(float) / 1.0e9
            positive = np.maximum(field, 0.0)
            row: dict[str, float | int] = {
                "year": year,
                "month": month,
                "warm_core_center_lon_e": center,
                "valid_window_longitudes": int(lon_mask.sum()),
            }
            for band, (lower, upper) in BAND_BOUNDS.items():
                lat_mask = (latitude >= lower) & (latitude < upper)
                row[f"H_{band}_signed_1deg_gjm2"] = weighted_spatial_mean(
                    field, latitude, lat_mask, lon_mask
                )
                row[f"H_{band}_positive_1deg_gjm2"] = weighted_spatial_mean(
                    positive, latitude, lat_mask, lon_mask
                )
            rows.append(row)

    monthly = pd.DataFrame(rows)
    jfm = monthly.groupby("year", as_index=False).mean(numeric_only=True)
    jfm = jfm.set_index("year").reindex(EVENTS).reset_index()
    for suffix in ("signed_1deg", "positive_1deg"):
        he = jfm[f"H_eq_{suffix}_gjm2"].to_numpy(dtype=float)
        hs = jfm[f"H_south_{suffix}_gjm2"].to_numpy(dtype=float)
        hn = jfm[f"H_north_{suffix}_gjm2"].to_numpy(dtype=float)
        jfm[f"H_off_{suffix}_gjm2"] = 0.5 * (hs + hn)
        jfm[f"D_{suffix}_gjm2"] = jfm[f"H_off_{suffix}_gjm2"] - he
        jfm[f"H_3band_{suffix}_gjm2"] = (
            AREA_WEIGHTS["eq"] * he
            + AREA_WEIGHTS["south"] * hs
            + AREA_WEIGHTS["north"] * hn
        ) / sum(AREA_WEIGHTS.values())
    jfm = jfm.merge(
        events[["year", "C_JJA_raw_z", "H_E_gjm2", "H_S_gjm2", "H_N_gjm2", "H_3band_gjm2", "D_raw_gjm2"]],
        on="year",
        how="left",
        validate="one_to_one",
    )
    return jfm


def build_sensitivity(
    event_table: pd.DataFrame,
    positive_table: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    response = event_table.C_JJA_raw_z.to_numpy(dtype=float)
    signed_total = event_table.H_3band_gjm2.to_numpy(dtype=float)
    signed_d = event_table.D_raw_gjm2.to_numpy(dtype=float)
    signed_1deg_total = positive_table.H_3band_signed_1deg_gjm2.to_numpy(dtype=float)
    signed_1deg_d = positive_table.D_signed_1deg_gjm2.to_numpy(dtype=float)
    positive_total = positive_table.H_3band_positive_1deg_gjm2.to_numpy(dtype=float)
    positive_d = positive_table.D_positive_1deg_gjm2.to_numpy(dtype=float)
    keep_without_1997_2015 = ~positive_table.year.isin([1997, 2015]).to_numpy()

    rows = [
        model_row("primary_signed_0p5deg", response, signed_total, signed_d),
        model_row(
            "validation_signed_1deg",
            response,
            signed_1deg_total,
            signed_1deg_d,
        ),
        model_row(
            "positive_only_with_positive_total",
            response,
            positive_total,
            positive_d,
        ),
        model_row(
            "positive_only_with_original_signed_total",
            response,
            signed_total,
            positive_d,
        ),
        model_row(
            "positive_only_drop_1997_2015",
            response[keep_without_1997_2015],
            positive_total[keep_without_1997_2015],
            positive_d[keep_without_1997_2015],
        ),
    ]
    validation = {
        "corr_HE_1deg_vs_primary": float(np.corrcoef(positive_table.H_eq_signed_1deg_gjm2, positive_table.H_E_gjm2)[0, 1]),
        "corr_HS_1deg_vs_primary": float(np.corrcoef(positive_table.H_south_signed_1deg_gjm2, positive_table.H_S_gjm2)[0, 1]),
        "corr_HN_1deg_vs_primary": float(np.corrcoef(positive_table.H_north_signed_1deg_gjm2, positive_table.H_N_gjm2)[0, 1]),
        "corr_D_1deg_vs_primary": float(np.corrcoef(positive_table.D_signed_1deg_gjm2, positive_table.D_raw_gjm2)[0, 1]),
        "rmse_D_1deg_vs_primary_gjm2": float(np.sqrt(np.mean((positive_table.D_signed_1deg_gjm2 - positive_table.D_raw_gjm2) ** 2))),
    }
    return pd.DataFrame(rows), validation


def plot_diagnostics(
    event_table: pd.DataFrame,
    leave_two: pd.DataFrame,
    positive: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "axes.edgecolor": "#333333",
            "axes.linewidth": 0.9,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.0))
    ax_a, ax_b, ax_c, ax_d = axes.flat

    years = event_table.year.to_numpy(dtype=int)
    positions = np.arange(len(years))
    width = 0.25
    ax_a.bar(positions - width, event_table.H_E_gjm2, width, label="$H_E$", color="#b23a3a")
    ax_a.bar(positions, event_table.H_S_gjm2, width, label="$H_S$", color="#3d8b6d")
    ax_a.bar(positions + width, event_table.H_N_gjm2, width, label="$H_N$", color="#3d6ca8")
    ax_a.axhline(0, color="0.55", linewidth=0.7)
    ax_a.set_xticks(positions)
    ax_a.set_xticklabels(years, rotation=45, ha="right")
    ax_a.set_ylabel("JFM OHC anomaly (GJ m$^{-2}$)")
    ax_a.legend(frameon=False, ncol=3, loc="upper left")
    ax_a.set_title("(a) Signed OHC in the three latitude bands", loc="left", fontsize=11)

    x = event_table.D_residual_gjm2.to_numpy(dtype=float)
    y = event_table.C_residual_after_H3band_z.to_numpy(dtype=float)
    grid = np.linspace(x.min() - 0.03, x.max() + 0.03, 100)
    slope, intercept = np.polyfit(x, y, 1)
    ax_b.plot(grid, slope * grid + intercept, color="0.2", linewidth=1.4)
    for index, year in enumerate(years):
        color = HIGHLIGHTS.get(year, "#777777")
        ax_b.scatter(x[index], y[index], color=color, s=48 if year in HIGHLIGHTS else 30, edgecolor="white", linewidth=0.6, zorder=3)
        ax_b.annotate(str(year), (x[index], y[index]), xytext=(4, 4), textcoords="offset points", fontsize=7.8, color=color)
    primary = sensitivity.loc[sensitivity.model_id.eq("primary_signed_0p5deg")].iloc[0]
    ax_b.text(0.04, 0.96, f"partial r = {primary.partial_r:+.2f}\np = {primary.p_analytic_two_sided:.3f}", transform=ax_b.transAxes, va="top")
    ax_b.axhline(0, color="0.75", linewidth=0.7)
    ax_b.axvline(0, color="0.75", linewidth=0.7)
    ax_b.set_xlabel("Residual signed meridional OHC contrast (GJ m$^{-2}$)")
    ax_b.set_ylabel("Residual JJA coupling response (z)")
    ax_b.set_title("(b) Primary signed-contrast relation", loc="left", fontsize=11)

    values = np.sort(leave_two.partial_r.to_numpy(dtype=float))
    ax_c.plot(np.arange(1, len(values) + 1), values, color="#486a8c", linewidth=1.3)
    pair = leave_two.loc[
        (leave_two.dropped_year_1.eq(1997) & leave_two.dropped_year_2.eq(2015))
        | (leave_two.dropped_year_1.eq(2015) & leave_two.dropped_year_2.eq(1997))
    ].iloc[0]
    rank = int(np.searchsorted(values, pair.partial_r, side="left") + 1)
    ax_c.scatter(rank, pair.partial_r, color="#c43c39", s=55, zorder=3)
    ax_c.annotate("remove 1997 + 2015", (rank, pair.partial_r), xytext=(6, 5), textcoords="offset points", fontsize=8.2, color="#c43c39")
    ax_c.axhline(0, color="0.6", linewidth=0.7)
    ax_c.set_xlabel("Sorted leave-two-events-out fits (78 pairs)")
    ax_c.set_ylabel("Partial correlation")
    ax_c.set_title("(c) Paired-event sensitivity", loc="left", fontsize=11)

    positive_total = positive.H_3band_positive_1deg_gjm2.to_numpy(dtype=float)
    positive_d = positive.D_positive_1deg_gjm2.to_numpy(dtype=float)
    response = positive.C_JJA_raw_z.to_numpy(dtype=float)
    xp = residualize(positive_d, positive_total)
    yp = residualize(response, positive_total)
    gridp = np.linspace(xp.min() - 0.01, xp.max() + 0.01, 100)
    slopep, interceptp = np.polyfit(xp, yp, 1)
    ax_d.plot(gridp, slopep * gridp + interceptp, color="0.2", linewidth=1.4)
    for index, year in enumerate(years):
        color = HIGHLIGHTS.get(year, "#777777")
        ax_d.scatter(xp[index], yp[index], color=color, s=48 if year in HIGHLIGHTS else 30, edgecolor="white", linewidth=0.6, zorder=3)
        ax_d.annotate(str(year), (xp[index], yp[index]), xytext=(4, 4), textcoords="offset points", fontsize=7.8, color=color)
    warm = sensitivity.loc[
        sensitivity.model_id.eq("positive_only_with_positive_total")
    ].iloc[0]
    ax_d.text(0.04, 0.96, f"partial r = {warm.partial_r:+.2f}\np = {warm.p_analytic_two_sided:.3f}", transform=ax_d.transAxes, va="top")
    ax_d.axhline(0, color="0.75", linewidth=0.7)
    ax_d.axvline(0, color="0.75", linewidth=0.7)
    ax_d.set_xlabel("Residual positive-only OHC contrast (GJ m$^{-2}$)")
    ax_d.set_ylabel("Residual JJA coupling response (z)")
    ax_d.set_title("(d) Positive-only warm-allocation sensitivity", loc="left", fontsize=11)

    fig.tight_layout(pad=1.2, h_pad=2.0, w_pad=1.6)
    fig.savefig(FIGURE_PNG, dpi=360, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURE_PDF, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_report(
    event_table: pd.DataFrame,
    leave_two: pd.DataFrame,
    sensitivity: pd.DataFrame,
    diagnostics: dict[str, float],
    validation: dict[str, float],
) -> dict[str, object]:
    pair = leave_two.loc[
        leave_two.dropped_year_1.eq(1997) & leave_two.dropped_year_2.eq(2015)
    ].iloc[0]
    leave_summary = {
        "partial_r_min": float(leave_two.partial_r.min()),
        "partial_r_median": float(leave_two.partial_r.median()),
        "partial_r_max": float(leave_two.partial_r.max()),
        "fraction_negative": float((leave_two.partial_r < 0).mean()),
        "fraction_p_below_0p05": float((leave_two.p_analytic_two_sided < 0.05).mean()),
        "remove_1997_2015_partial_r": float(pair.partial_r),
        "remove_1997_2015_beta_D": float(pair.beta_contrast),
        "remove_1997_2015_p": float(pair.p_analytic_two_sided),
        "remove_1997_2015_ci_low": float(pair.beta_contrast_ci_low),
        "remove_1997_2015_ci_high": float(pair.beta_contrast_ci_high),
    }
    summary: dict[str, object] = {
        "primary_model": sensitivity.loc[
            sensitivity.model_id.eq("primary_signed_0p5deg")
        ].iloc[0].to_dict(),
        "remove_1997_and_2015": pair.to_dict(),
        "leave_two_events_out": leave_summary,
        "influence_thresholds": diagnostics,
        "positive_only_model": sensitivity.loc[
            sensitivity.model_id.eq("positive_only_with_positive_total")
        ].iloc[0].to_dict(),
        "positive_only_same_original_total_control": sensitivity.loc[
            sensitivity.model_id.eq("positive_only_with_original_signed_total")
        ].iloc[0].to_dict(),
        "positive_only_remove_1997_and_2015": sensitivity.loc[
            sensitivity.model_id.eq("positive_only_drop_1997_2015")
        ].iloc[0].to_dict(),
        "one_degree_validation": validation,
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    selected = event_table.loc[event_table.year.isin([1997, 2015, 2023])]
    lines = [
        "# ENSO经向OHC配置：成对高杠杆与正暖异常敏感性诊断",
        "",
        "## 主要结果",
        "",
        f"- 原始有符号指标模型：partial r = {summary['primary_model']['partial_r']:+.3f}，beta_D = {summary['primary_model']['beta_contrast']:+.3f}，p = {summary['primary_model']['p_analytic_two_sided']:.4f}。",
        f"- 同时删除1997和2015：partial r = {pair.partial_r:+.3f}，beta_D = {pair.beta_contrast:+.3f}，p = {pair.p_analytic_two_sided:.4f}。",
        f"- 78种leave-two-events-out：partial r范围 {leave_summary['partial_r_min']:+.3f} 至 {leave_summary['partial_r_max']:+.3f}，中位数 {leave_summary['partial_r_median']:+.3f}；{leave_summary['fraction_negative']:.1%} 为负。",
        f"- positive-only指标并控制positive-only三纬带平均：partial r = {summary['positive_only_model']['partial_r']:+.3f}，beta_D+ = {summary['positive_only_model']['beta_contrast']:+.3f}，p = {summary['positive_only_model']['p_analytic_two_sided']:.4f}。",
        f"- positive-only指标同时删除1997和2015：partial r = {summary['positive_only_remove_1997_and_2015']['partial_r']:+.3f}，beta_D+ = {summary['positive_only_remove_1997_and_2015']['beta_contrast']:+.3f}，p = {summary['positive_only_remove_1997_and_2015']['p_analytic_two_sided']:.4f}。",
        "",
        "## 1997、2015和2023的纬带拆分",
        "",
        "| year | H_E | H_S | H_N | D_S/2 | D_N/2 | D |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in selected.itertuples():
        lines.append(
            f"| {row.year} | {row.H_E_gjm2:+.3f} | {row.H_S_gjm2:+.3f} | {row.H_N_gjm2:+.3f} | {row.south_contribution_to_D_gjm2:+.3f} | {row.north_contribution_to_D_gjm2:+.3f} | {row.D_raw_gjm2:+.3f} |"
        )
    lines.extend(
        [
            "",
            "这里的D是有符号的赤道—离赤道OHC对比，不能单独解释为正暖量的空间分配。positive-only版本先在每个1° OHC异常格点计算max(H', 0)，再在同一暖核质心±10°窗口和三个纬带内作余弦纬度加权平均。",
            "",
            "1°有符号重算仅用于验证positive-only计算链。它与主分析D的相关为 "
            f"{validation['corr_D_1deg_vs_primary']:.3f}，RMSE为 {validation['rmse_D_1deg_vs_primary_gjm2']:.3f} GJ m⁻²。",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    for path in (EVENT_CSV, CENTROID_CSV, OHC_FILE):
        if not path.exists():
            raise FileNotFoundError(path)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(EVENT_CSV)
    if tuple(events.year.astype(int)) != EVENTS:
        raise ValueError("Unexpected event ordering or sample")

    event_table, diagnostics = signed_event_diagnostics(events)
    leave_two = leave_two_event_out(event_table)
    positive = build_gridded_positive_only(event_table)
    sensitivity, validation = build_sensitivity(event_table, positive)

    event_table.to_csv(EVENT_DIAGNOSTICS_CSV, index=False, float_format="%.8f")
    leave_two.to_csv(LEAVE_TWO_CSV, index=False, float_format="%.8f")
    event_table[
        [
            "year",
            "leverage_hii",
            "cooks_distance",
            "dfbeta_D",
            "studentized_residual_external",
        ]
    ].to_csv(INFLUENCE_CSV, index=False, float_format="%.8f")
    positive.to_csv(POSITIVE_ONLY_CSV, index=False, float_format="%.8f")
    sensitivity.to_csv(SENSITIVITY_CSV, index=False, float_format="%.8f")
    summary = write_report(
        event_table,
        leave_two,
        sensitivity,
        diagnostics,
        validation,
    )
    plot_diagnostics(event_table, leave_two, positive, sensitivity)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
