#!/usr/bin/env python3
"""Compare January-June ENSO recharge evolution by official NOAA/CPC RONI class.

The ocean diagnostic follows the physical framework of Li et al. (2022,
doi:10.1029/2022GL099242): D20 represents thermocline depth and its tropical
Pacific mean is used as a warm-water-volume (WWV) proxy.  The local data that
extend through June 2026 are an ORAS5 equatorial transect, so the primary
quantity here is explicitly called an *equatorial D20 recharge proxy*, not the
paper's exact 5S-5N WWV index.

Historical event strength follows the current NOAA/CPC operational convention:
RONI from ERSSTv6 and 0.5 degC intensity bins.  The requested primary contrast
combines strong and very strong events (peak RONI >= 1.5 degC) because the
strict strong bin contains only two post-1981 events.  Strict strong and very
strong groups are retained separately in output tables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/research_2026/enso_recharge_strength_2026"
OUT_DATA = ROOT / "data/derived/research_2026/enso_recharge_strength_2026"
MPL_DIR = ROOT / "outputs/research_2026/mplconfig"
os.environ.setdefault("MPLCONFIGDIR", str(MPL_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm


D20_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_d20_timeseries_equatorial_1960_202606.csv"
)
D20_3LAT_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_process_timeseries_3lat_5deg_1980_2024.csv"
)
TAUX_CSV = (
    ROOT
    / "data/interim/research_2026/"
    "oras5_windstress_timeseries_equatorial_1980_202605.csv"
)
LEGACY_D20_ANOM_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "oras5_equatorial_d20_monthly_anomaly_1980_202606_detrended_1980_2014.csv"
)

BASELINE_START = 1982
BASELINE_END = 2024
MONTHS = np.arange(1, 7)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
VALID_LONS = np.arange(135.0, 280.0, 5.0)
WEST = (135.0, 180.0)
CENTRAL = (180.0, 220.0)
EAST = (220.0, 275.0)

# Current NOAA/CPC RONI (ERSSTv6) peak values for post-1981 warm events.
# Source checked 2026-08-19:
# https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/
# 2015 denotes the calendar year of the main development into the 2015/16 peak.
EVENTS = (
    (1982, 2.4, "very strong"),
    (1986, 1.5, "strong"),
    (1991, 2.1, "very strong"),
    (1994, 1.3, "moderate"),
    (1997, 2.3, "very strong"),
    (2002, 1.3, "moderate"),
    (2004, 0.7, "weak"),
    (2006, 0.9, "weak"),
    (2009, 1.5, "strong"),
    (2015, 2.3, "very strong"),
    (2018, 0.8, "weak"),
    (2023, 1.4, "moderate"),
)

RONI_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"
STRENGTH_URL = (
    "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/"
    "enso/roni/strengths/"
)
PAPER_URL = "https://doi.org/10.1029/2022GL099242"


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 170,
            "savefig.dpi": 360,
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 9.2,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.4,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.4,
            "ytick.labelsize": 8.4,
            "legend.fontsize": 8.2,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def calendar_month_detrended_anomaly(
    frame: pd.DataFrame,
    value_col: str,
    location_cols: list[str],
) -> pd.DataFrame:
    """Remove 1982-2024 same-month mean and linear trend point by point."""

    result = frame.copy()
    result["time"] = pd.to_datetime(result["time"])
    result["year"] = result["time"].dt.year
    result["month"] = result["time"].dt.month
    result["anomaly"] = np.nan
    keys = location_cols + ["month"]
    mean_year = (BASELINE_START + BASELINE_END) / 2.0
    for _, idx in result.groupby(keys, sort=False).groups.items():
        current = result.loc[idx]
        train = current.loc[
            current["year"].between(BASELINE_START, BASELINE_END)
            & current[value_col].notna()
        ]
        if len(train) < 20:
            continue
        x = train["year"].to_numpy(dtype=float) - mean_year
        y = train[value_col].to_numpy(dtype=float)
        design = np.column_stack([np.ones_like(x), x])
        intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
        all_x = current["year"].to_numpy(dtype=float) - mean_year
        result.loc[idx, "anomaly"] = (
            current[value_col].to_numpy(dtype=float) - intercept - slope * all_x
        )
    return result


def build_event_table() -> pd.DataFrame:
    events = pd.DataFrame(EVENTS, columns=["event_year", "peak_roni_c", "roni_class"])
    events["primary_group"] = np.where(
        events["peak_roni_c"] >= 1.5,
        "strong_or_very_strong",
        np.where(events["peak_roni_c"] >= 1.0, "moderate", "weak"),
    )
    events["included_primary"] = events["primary_group"].isin(
        ["strong_or_very_strong", "moderate"]
    )
    return events


def prepare_d20() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(D20_CSV)
    raw["time"] = pd.to_datetime(raw["time"])
    raw = raw.loc[
        raw["requested_lon"].isin(VALID_LONS)
        & raw["year"].between(BASELINE_START, 2026)
    ].copy()
    anomaly = calendar_month_detrended_anomaly(raw, "d20_m", ["requested_lon"])
    main = anomaly.loc[
        anomaly["year"].isin([year for year, _, _ in EVENTS] + [2026])
        & anomaly["month"].isin(MONTHS)
    ].copy()
    return anomaly, main


def prepare_taux() -> pd.DataFrame:
    raw = pd.read_csv(TAUX_CSV)
    raw["time"] = pd.to_datetime(raw["time"])
    raw = raw.loc[
        raw["requested_lon"].between(CENTRAL[0], CENTRAL[1])
        & raw["year"].between(BASELINE_START, 2026)
    ].copy()
    anomaly = calendar_month_detrended_anomaly(raw, "tau_x_n_m2", ["requested_lon"])
    return anomaly.loc[
        anomaly["year"].isin([year for year, _, _ in EVENTS] + [2026])
        & anomaly["month"].between(1, 6)
    ].copy()


def region_mean(frame: pd.DataFrame, bounds: tuple[float, float]) -> float:
    values = frame.loc[frame["requested_lon"].between(*bounds), "anomaly"]
    return float(values.mean())


def build_monthly_metrics(
    d20: pd.DataFrame,
    taux: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    group_lookup = events.set_index("event_year")["primary_group"].to_dict()
    class_lookup = events.set_index("event_year")["roni_class"].to_dict()
    peak_lookup = events.set_index("event_year")["peak_roni_c"].to_dict()
    rows: list[dict[str, float | int | str]] = []
    for (year, month), current in d20.groupby(["year", "month"], sort=True):
        positive = current["anomaly"].clip(lower=0.0).to_numpy(dtype=float)
        longitude = current["requested_lon"].to_numpy(dtype=float)
        pos_sum = np.nansum(positive)
        centroid = (
            float(np.nansum(positive * longitude) / pos_sum)
            if pos_sum > 0.0
            else np.nan
        )
        east_positive_fraction = (
            float(np.nansum(positive[longitude >= EAST[0]]) / pos_sum)
            if pos_sum > 0.0
            else np.nan
        )
        tau_current = taux.loc[(taux["year"] == year) & (taux["month"] == month)]
        rows.append(
            {
                "year": int(year),
                "month": int(month),
                "month_label": MONTH_LABELS[int(month) - 1],
                "roni_class": class_lookup.get(year, "2026 target"),
                "primary_group": group_lookup.get(year, "2026 target"),
                "peak_roni_c": peak_lookup.get(year, np.nan),
                "basin_mean_d20_m": float(current["anomaly"].mean()),
                "west_d20_m": region_mean(current, WEST),
                "central_d20_m": region_mean(current, CENTRAL),
                "east_d20_m": region_mean(current, EAST),
                "east_minus_west_d20_m": (
                    region_mean(current, EAST) - region_mean(current, WEST)
                ),
                "positive_d20_centroid_deg_e": centroid,
                "east_positive_d20_fraction": east_positive_fraction,
                "central_taux_anom_n_m2": (
                    float(tau_current["anomaly"].mean())
                    if not tau_current.empty
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def build_event_metrics(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for year, current in monthly.groupby("year", sort=True):
        current = current.sort_values("month")
        jan = current.loc[current["month"] == 1].iloc[0]
        jun = current.loc[current["month"] == 6].iloc[0]
        jfm = current.loc[current["month"].between(1, 3)]
        amj = current.loc[current["month"].between(4, 6)]
        rows.append(
            {
                "year": int(year),
                "roni_class": current["roni_class"].iloc[0],
                "primary_group": current["primary_group"].iloc[0],
                "peak_roni_c": current["peak_roni_c"].iloc[0],
                "jfm_basin_mean_d20_m": float(jfm["basin_mean_d20_m"].mean()),
                "amj_basin_mean_d20_m": float(amj["basin_mean_d20_m"].mean()),
                "jan_to_jun_basin_change_m": float(
                    jun["basin_mean_d20_m"] - jan["basin_mean_d20_m"]
                ),
                "jfm_west_d20_m": float(jfm["west_d20_m"].mean()),
                "jfm_central_d20_m": float(jfm["central_d20_m"].mean()),
                "jfm_east_d20_m": float(jfm["east_d20_m"].mean()),
                "amj_west_d20_m": float(amj["west_d20_m"].mean()),
                "amj_central_d20_m": float(amj["central_d20_m"].mean()),
                "amj_east_d20_m": float(amj["east_d20_m"].mean()),
                "jfm_east_minus_west_m": float(jfm["east_minus_west_d20_m"].mean()),
                "amj_east_minus_west_m": float(amj["east_minus_west_d20_m"].mean()),
                "jan_to_jun_centroid_shift_deg": float(
                    jun["positive_d20_centroid_deg_e"]
                    - jan["positive_d20_centroid_deg_e"]
                ),
                "jfm_east_positive_fraction": float(
                    jfm["east_positive_d20_fraction"].mean()
                ),
                "amj_east_positive_fraction": float(
                    amj["east_positive_d20_fraction"].mean()
                ),
                "jan_may_central_taux_n_m2": float(
                    current.loc[current["month"].between(1, 5), "central_taux_anom_n_m2"].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def composite_matrix(
    d20: pd.DataFrame,
    years: list[int],
) -> np.ndarray:
    selected = d20.loc[d20["year"].isin(years)]
    matrix = (
        selected.groupby(["month", "requested_lon"])["anomaly"]
        .mean()
        .unstack("requested_lon")
        .reindex(index=MONTHS, columns=VALID_LONS)
    )
    return matrix.to_numpy(dtype=float)


def pattern_metrics(target: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    valid = np.isfinite(target) & np.isfinite(reference)
    target_v = target[valid]
    reference_v = reference[valid]
    correlation = float(pearsonr(target_v, reference_v).statistic)
    rmse = float(np.sqrt(np.mean((target_v - reference_v) ** 2)))
    centered_rmse = float(
        np.sqrt(
            np.mean(
                (
                    (target_v - target_v.mean())
                    - (reference_v - reference_v.mean())
                )
                ** 2
            )
        )
    )
    amplitude_ratio = float(np.std(target_v, ddof=1) / np.std(reference_v, ddof=1))
    return {
        "pattern_correlation": correlation,
        "rmse_m": rmse,
        "centered_rmse_m": centered_rmse,
        "amplitude_ratio": amplitude_ratio,
    }


def compare_patterns(d20: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    target = composite_matrix(d20, [2026])
    definitions = {
        "moderate": events.loc[events["roni_class"] == "moderate", "event_year"].tolist(),
        "strict_strong": events.loc[events["roni_class"] == "strong", "event_year"].tolist(),
        "very_strong": events.loc[events["roni_class"] == "very strong", "event_year"].tolist(),
        "strong_or_very_strong": events.loc[
            events["peak_roni_c"] >= 1.5, "event_year"
        ].tolist(),
    }
    rows = []
    for name, years in definitions.items():
        values = pattern_metrics(target, composite_matrix(d20, years))
        rows.append(
            {
                "reference_group": name,
                "event_years": ",".join(map(str, years)),
                "n_events": len(years),
                **values,
            }
        )
    return pd.DataFrame(rows)


def compare_individual_patterns(d20: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    target = composite_matrix(d20, [2026])
    event_info = events.set_index("event_year")
    rows = []
    for year in events["event_year"]:
        values = pattern_metrics(target, composite_matrix(d20, [int(year)]))
        rows.append(
            {
                "event_year": int(year),
                "roni_class": event_info.loc[year, "roni_class"],
                "peak_roni_c": float(event_info.loc[year, "peak_roni_c"]),
                **values,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["pattern_correlation", "rmse_m"], ascending=[False, True]
    )


def baseline_sensitivity(events: pd.DataFrame) -> pd.DataFrame:
    """Repeat pattern matching with the existing 1980-2014 anomaly product."""

    frame = pd.read_csv(LEGACY_D20_ANOM_CSV)
    frame = frame.loc[
        frame["lon"].isin(VALID_LONS)
        & frame["month"].isin(MONTHS)
        & frame["year"].isin(events["event_year"].tolist() + [2026])
    ].rename(
        columns={
            "lon": "requested_lon",
            "d20_detrended_anomaly_m": "anomaly",
        }
    )
    target = composite_matrix(frame, [2026])
    definitions = {
        "moderate": events.loc[events["roni_class"] == "moderate", "event_year"].tolist(),
        "strict_strong": events.loc[events["roni_class"] == "strong", "event_year"].tolist(),
        "very_strong": events.loc[events["roni_class"] == "very strong", "event_year"].tolist(),
        "strong_or_very_strong": events.loc[
            events["peak_roni_c"] >= 1.5, "event_year"
        ].tolist(),
    }
    rows = []
    for name, years in definitions.items():
        rows.append(
            {
                "baseline": "1980-2014 same-month climatology and trend",
                "reference_group": name,
                "event_years": ",".join(map(str, years)),
                "n_events": len(years),
                **pattern_metrics(target, composite_matrix(frame, years)),
            }
        )
    return pd.DataFrame(rows)


def validate_equatorial_proxy(d20_all: pd.DataFrame) -> dict[str, float]:
    three = pd.read_csv(D20_3LAT_CSV)
    three["time"] = pd.to_datetime(three["time"])
    three = three.loc[
        three["requested_lon"].isin(VALID_LONS)
        & three["year"].between(BASELINE_START, BASELINE_END)
    ].copy()
    three_anom = calendar_month_detrended_anomaly(
        three, "d20_m", ["requested_lat", "requested_lon"]
    )
    three_monthly = three_anom.groupby("time")["anomaly"].mean()
    equator_monthly = (
        d20_all.loc[d20_all["year"].between(BASELINE_START, BASELINE_END)]
        .groupby("time")["anomaly"]
        .mean()
    )
    joined = pd.concat(
        [equator_monthly.rename("equator"), three_monthly.rename("three_lat")],
        axis=1,
        join="inner",
    ).dropna()
    regression = np.polyfit(joined["three_lat"], joined["equator"], 1)
    return {
        "n_months": int(len(joined)),
        "correlation": float(joined.corr().iloc[0, 1]),
        "equator_on_three_lat_slope": float(regression[0]),
        "equator_on_three_lat_intercept_m": float(regression[1]),
        "equator_rmse_vs_three_lat_m": float(
            np.sqrt(np.mean((joined["equator"] - joined["three_lat"]) ** 2))
        ),
    }


def longitude_labels(values: np.ndarray) -> list[str]:
    labels = []
    for value in values:
        if value < 180:
            labels.append(f"{int(value)}°E")
        elif value == 180:
            labels.append("180°")
        else:
            labels.append(f"{int(360-value)}°W")
    return labels


def plot_hovmoller(d20: pd.DataFrame, events: pd.DataFrame) -> None:
    strong_years = events.loc[events["peak_roni_c"] >= 1.5, "event_year"].tolist()
    moderate_years = events.loc[events["roni_class"] == "moderate", "event_year"].tolist()
    strong = composite_matrix(d20, strong_years)
    moderate = composite_matrix(d20, moderate_years)
    target = composite_matrix(d20, [2026])
    difference = strong - moderate

    finite = np.concatenate([strong.ravel(), moderate.ravel(), target.ravel()])
    vmax = max(10.0, float(np.nanpercentile(np.abs(finite), 98)))
    vmax = np.ceil(vmax / 2.0) * 2.0
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    cmap = "RdBu_r"

    fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.8), constrained_layout=True)
    panels = (
        (strong, f"(a) Strong + very strong composite (n={len(strong_years)})"),
        (moderate, f"(b) Moderate composite (n={len(moderate_years)})"),
        (difference, "(c) Strong+ minus moderate"),
        (target, "(d) 2026"),
    )
    for ax, (matrix, title) in zip(axes.flat, panels):
        image = ax.pcolormesh(
            VALID_LONS,
            MONTHS,
            matrix,
            shading="nearest",
            cmap=cmap,
            norm=norm,
            rasterized=True,
        )
        ax.contour(
            VALID_LONS,
            MONTHS,
            matrix,
            levels=[0.0],
            colors="0.25",
            linewidths=0.55,
        )
        ax.axvline(180.0, color="0.25", lw=0.55, ls="--")
        ax.axvline(220.0, color="0.25", lw=0.55, ls="--")
        ax.set_title(title, loc="left")
        ax.set_yticks(MONTHS, MONTH_LABELS)
        ax.invert_yaxis()
        ticks = np.array([140, 180, 220, 260])
        ax.set_xticks(ticks, longitude_labels(ticks))
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Development month")

    cbar = fig.colorbar(image, ax=axes, orientation="horizontal", shrink=0.72, pad=0.07)
    cbar.set_label("Equatorial D20 anomaly (m)")
    fig.savefig(OUT_DIR / "enso_recharge_hovmoller_roni_2026.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "enso_recharge_hovmoller_roni_2026.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_official_class_hovmoller(d20: pd.DataFrame, events: pd.DataFrame) -> None:
    definitions = (
        ("moderate", "Moderate"),
        ("strong", "Strong"),
        ("very strong", "Very strong"),
    )
    matrices: list[tuple[np.ndarray, str]] = []
    for class_name, label in definitions:
        years = events.loc[events["roni_class"] == class_name, "event_year"].tolist()
        matrices.append(
            (
                composite_matrix(d20, years),
                f"{label} composite (n={len(years)}; {', '.join(map(str, years))})",
            )
        )
    matrices.append((composite_matrix(d20, [2026]), "2026"))

    finite = np.concatenate([matrix.ravel() for matrix, _ in matrices])
    vmax = max(10.0, float(np.nanpercentile(np.abs(finite), 98)))
    vmax = np.ceil(vmax / 2.0) * 2.0
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)

    fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.8), constrained_layout=True)
    for panel, (ax, (matrix, title)) in enumerate(zip(axes.flat, matrices)):
        image = ax.pcolormesh(
            VALID_LONS,
            MONTHS,
            matrix,
            shading="nearest",
            cmap="RdBu_r",
            norm=norm,
            rasterized=True,
        )
        ax.contour(
            VALID_LONS,
            MONTHS,
            matrix,
            levels=[0.0],
            colors="0.25",
            linewidths=0.55,
        )
        ax.axvline(180.0, color="0.25", lw=0.55, ls="--")
        ax.axvline(220.0, color="0.25", lw=0.55, ls="--")
        ax.set_title(f"({chr(97 + panel)}) {title}", loc="left")
        ax.set_yticks(MONTHS, MONTH_LABELS)
        ax.invert_yaxis()
        ticks = np.array([140, 180, 220, 260])
        ax.set_xticks(ticks, longitude_labels(ticks))
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Development month")
    cbar = fig.colorbar(image, ax=axes, orientation="horizontal", shrink=0.72, pad=0.07)
    cbar.set_label("Equatorial D20 anomaly (m)")
    fig.savefig(
        OUT_DIR / "enso_recharge_hovmoller_official_roni_classes_2026.png",
        bbox_inches="tight",
    )
    fig.savefig(
        OUT_DIR / "enso_recharge_hovmoller_official_roni_classes_2026.pdf",
        bbox_inches="tight",
    )
    plt.close(fig)


def group_monthly_stats(
    monthly: pd.DataFrame,
    years: list[int],
    column: str,
) -> tuple[np.ndarray, np.ndarray]:
    pivot = (
        monthly.loc[monthly["year"].isin(years)]
        .pivot(index="year", columns="month", values=column)
        .reindex(columns=MONTHS)
    )
    mean = pivot.mean(axis=0).to_numpy(dtype=float)
    sem = pivot.sem(axis=0, ddof=1).to_numpy(dtype=float)
    return mean, sem


def plot_indices(monthly: pd.DataFrame, events: pd.DataFrame) -> None:
    strong_years = events.loc[events["peak_roni_c"] >= 1.5, "event_year"].tolist()
    moderate_years = events.loc[events["roni_class"] == "moderate", "event_year"].tolist()
    target = monthly.loc[monthly["year"] == 2026].set_index("month")
    colors = {"strong": "#a51c30", "moderate": "#2166ac", "target": "#111111"}

    fields = (
        ("basin_mean_d20_m", "Basin-mean D20 anomaly (m)", "(a) Recharge amount"),
        ("east_minus_west_d20_m", "East-minus-west D20 anomaly (m)", "(b) Eastward redistribution"),
        ("central_taux_anom_n_m2", "Central-Pacific zonal stress anomaly (N m$^{-2}$)", "(c) Westerly forcing"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.5), constrained_layout=True)
    for ax, (field, ylabel, title) in zip(axes, fields):
        strong_mean, strong_sem = group_monthly_stats(monthly, strong_years, field)
        moderate_mean, moderate_sem = group_monthly_stats(monthly, moderate_years, field)
        ax.plot(MONTHS, strong_mean, color=colors["strong"], lw=1.8, label="Strong + very strong")
        ax.fill_between(
            MONTHS,
            strong_mean - strong_sem,
            strong_mean + strong_sem,
            color=colors["strong"],
            alpha=0.15,
            linewidth=0,
        )
        ax.plot(MONTHS, moderate_mean, color=colors["moderate"], lw=1.8, label="Moderate")
        ax.fill_between(
            MONTHS,
            moderate_mean - moderate_sem,
            moderate_mean + moderate_sem,
            color=colors["moderate"],
            alpha=0.15,
            linewidth=0,
        )
        target_values = target.reindex(MONTHS)[field].to_numpy(dtype=float)
        ax.plot(
            MONTHS,
            target_values,
            color=colors["target"],
            lw=2.0,
            marker="o",
            ms=3.7,
            label="2026",
            zorder=4,
        )
        ax.axhline(0.0, color="0.45", lw=0.7)
        ax.set_xticks(MONTHS, MONTH_LABELS)
        ax.set_title(title, loc="left")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", color="0.88", lw=0.55)
        if field == "central_taux_anom_n_m2":
            ax.text(
                0.98,
                0.03,
                "2026 available through May",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=7.7,
                color="0.35",
            )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.12))
    fig.savefig(OUT_DIR / "enso_recharge_indices_roni_2026.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "enso_recharge_indices_roni_2026.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_official_class_indices(monthly: pd.DataFrame, events: pd.DataFrame) -> None:
    definitions = (
        ("moderate", "Moderate", "#2166ac"),
        ("strong", "Strong", "#e08214"),
        ("very strong", "Very strong", "#b2182b"),
    )
    target = monthly.loc[monthly["year"] == 2026].set_index("month")
    fields = (
        ("basin_mean_d20_m", "Basin-mean D20 anomaly (m)", "(a) Recharge amount"),
        ("east_minus_west_d20_m", "East-minus-west D20 anomaly (m)", "(b) Eastward redistribution"),
        ("central_taux_anom_n_m2", "Central-Pacific zonal stress anomaly (N m$^{-2}$)", "(c) Westerly forcing"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.5), constrained_layout=True)
    for ax, (field, ylabel, title) in zip(axes, fields):
        for class_name, label, color in definitions:
            years = events.loc[events["roni_class"] == class_name, "event_year"].tolist()
            mean, sem = group_monthly_stats(monthly, years, field)
            ax.plot(MONTHS, mean, color=color, lw=1.65, label=f"{label} (n={len(years)})")
            ax.fill_between(
                MONTHS,
                mean - sem,
                mean + sem,
                color=color,
                alpha=0.10,
                linewidth=0,
            )
        target_values = target.reindex(MONTHS)[field].to_numpy(dtype=float)
        ax.plot(
            MONTHS,
            target_values,
            color="#111111",
            lw=2.0,
            marker="o",
            ms=3.7,
            label="2026",
            zorder=5,
        )
        ax.axhline(0.0, color="0.45", lw=0.7)
        ax.set_xticks(MONTHS, MONTH_LABELS)
        ax.set_title(title, loc="left")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", color="0.88", lw=0.55)
        if field == "central_taux_anom_n_m2":
            ax.text(
                0.98,
                0.03,
                "2026 available through May",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=7.7,
                color="0.35",
            )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.12))
    fig.savefig(
        OUT_DIR / "enso_recharge_indices_official_roni_classes_2026.png",
        bbox_inches="tight",
    )
    fig.savefig(
        OUT_DIR / "enso_recharge_indices_official_roni_classes_2026.pdf",
        bbox_inches="tight",
    )
    plt.close(fig)


def summarize_groups(event_metrics: pd.DataFrame) -> pd.DataFrame:
    historical = event_metrics.loc[event_metrics["year"] != 2026].copy()
    definitions = {
        "moderate": historical["roni_class"] == "moderate",
        "strict_strong": historical["roni_class"] == "strong",
        "very_strong": historical["roni_class"] == "very strong",
        "strong_or_very_strong": historical["peak_roni_c"] >= 1.5,
    }
    numeric = [
        column
        for column in event_metrics.columns
        if column not in {"year", "roni_class", "primary_group"}
    ]
    rows = []
    for group, mask in definitions.items():
        selected = historical.loc[mask]
        row: dict[str, float | int | str] = {
            "group": group,
            "n_events": int(len(selected)),
            "event_years": ",".join(map(str, selected["year"].tolist())),
        }
        for column in numeric:
            row[f"{column}_mean"] = float(selected[column].mean())
            row[f"{column}_sd"] = float(selected[column].std(ddof=1))
        rows.append(row)
    return pd.DataFrame(rows)


def write_summary(
    events: pd.DataFrame,
    event_metrics: pd.DataFrame,
    group_summary: pd.DataFrame,
    similarity: pd.DataFrame,
    individual_similarity: pd.DataFrame,
    sensitivity: pd.DataFrame,
    validation: dict[str, float],
) -> None:
    target = event_metrics.loc[event_metrics["year"] == 2026].iloc[0]
    strong = group_summary.loc[group_summary["group"] == "strong_or_very_strong"].iloc[0]
    moderate = group_summary.loc[group_summary["group"] == "moderate"].iloc[0]
    sim = similarity.set_index("reference_group")
    sens = sensitivity.set_index("reference_group")
    closest = individual_similarity.head(3)

    def fmt(value: float, digits: int = 2) -> str:
        return f"{value:.{digits}f}"

    lines = [
        "# 基于官方 RONI 强度分组的 ENSO 充电过程及 2026 年对比",
        "",
        "## 强度定义",
        "",
        "主分析采用 NOAA/CPC 当前官方 RONI（ERSSTv6）口径：弱 0.5–0.9°C，中等 1.0–1.4°C，强 1.5–1.9°C，极强 ≥2.0°C。为回答‘强事件与中等事件’的对比，同时避免严格强事件仅两个样本造成的不稳定，主强事件组透明地合并强与极强事件；严格强组和极强组仍单独输出作为敏感性结果。",
        "",
        f"- 中等：{', '.join(map(str, events.loc[events.roni_class == 'moderate', 'event_year']))}。",
        f"- 严格强：{', '.join(map(str, events.loc[events.roni_class == 'strong', 'event_year']))}。",
        f"- 极强：{', '.join(map(str, events.loc[events.roni_class == 'very strong', 'event_year']))}。",
        f"- 主分析强组（强+极强）：{', '.join(map(str, events.loc[events.peak_roni_c >= 1.5, 'event_year']))}。",
        "",
        "按这一当前官方口径，2023/24 的峰值 RONI 为 1.4°C，归入中等事件。它与旧版 ONI 对该事件的更高强度判断不同，因此本文不会把两套口径混用。",
        "",
        "## 量和计算",
        "",
        "参考 Li et al. (2022) 用 20°C 等温面深度（D20）表征温跃层、用热带太平洋平均 D20 异常近似 WWV 的思路。由于本地延伸到 2026 年 6 月的数据是 ORAS5 赤道剖面，本文使用 0°、135°E–85°W 的经向平均 D20 异常，称为‘赤道 D20 充电代理量’，不冒充论文严格的 5°S–5°N、120°E–80°W WWV。异常按每个经度和同历月，用 1982–2024 年均值及线性趋势去除后得到。",
        "",
        f"赤道代理量与本地三纬度（4°S、0°、4°N）D20 平均代理量在 1982–2024 年逐月相关为 r={fmt(validation['correlation'], 3)}（n={validation['n_months']}），说明赤道剖面能较好追踪盆地尺度充电变化，但不用于声称完整体积积分。",
        "",
        "## 当前计算结果",
        "",
        f"1. 2026 年 JFM 赤道盆地平均 D20 异常为 {fmt(target['jfm_basin_mean_d20_m'])} m，AMJ 为 {fmt(target['amj_basin_mean_d20_m'])} m。强+极强组对应均值分别为 {fmt(strong['jfm_basin_mean_d20_m_mean'])} 和 {fmt(strong['amj_basin_mean_d20_m_mean'])} m；中等组为 {fmt(moderate['jfm_basin_mean_d20_m_mean'])} 和 {fmt(moderate['amj_basin_mean_d20_m_mean'])} m。",
        f"2. 2026 年 JFM 到 AMJ 的暖层东移可由东部减西部 D20 差衡量：JFM 为 {fmt(target['jfm_east_minus_west_m'])} m，AMJ 为 {fmt(target['amj_east_minus_west_m'])} m；强+极强组 AMJ 均值为 {fmt(strong['amj_east_minus_west_m_mean'])} m，中等组为 {fmt(moderate['amj_east_minus_west_m_mean'])} m。",
        f"3. 把 1–6 月完整的经度—月份 D20 异常场直接做型态相关，2026 与强+极强合成的 r={fmt(sim.loc['strong_or_very_strong', 'pattern_correlation'], 3)}、RMSE={fmt(sim.loc['strong_or_very_strong', 'rmse_m'])} m；与中等合成的 r={fmt(sim.loc['moderate', 'pattern_correlation'], 3)}、RMSE={fmt(sim.loc['moderate', 'rmse_m'])} m。这里比较的是截至 6 月的充电结构相似性，不是对 2026 最终峰值强度的预报。",
        f"4. 逐事件比较时最接近 2026 的三个年份是 {int(closest.iloc[0]['event_year'])}（r={fmt(closest.iloc[0]['pattern_correlation'], 3)}）、{int(closest.iloc[1]['event_year'])}（r={fmt(closest.iloc[1]['pattern_correlation'], 3)}）和 {int(closest.iloc[2]['event_year'])}（r={fmt(closest.iloc[2]['pattern_correlation'], 3)}）。改用已有的 1980–2014 基准异常后，2026 与极强组合成的型态相关仍为 r={fmt(sens.loc['very_strong', 'pattern_correlation'], 3)}，说明‘更接近极强事件的充电—东移结构’不依赖本次 1982–2024 基准选择。",
        "",
        "## 解释边界",
        "",
        "事件样本很少，尤其严格强事件只有 1986 和 2009。因此当前结果应作为过程型态诊断，而不是把复合差异写成普遍因果律。2026 仍处在发展期，官方未来强度分类要等成熟季 RONI 才能确定。",
        "",
        "## 来源",
        "",
        f"- Li et al. (2022): {PAPER_URL}",
        f"- NOAA/CPC historical RONI table: {RONI_URL}",
        f"- NOAA/CPC official strength bins: {STRENGTH_URL}",
    ]
    (OUT_DIR / "ENSO_RECHARGE_STRENGTH_2026_CN.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    MPL_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()

    events = build_event_table()
    d20_all, d20_events = prepare_d20()
    taux = prepare_taux()
    monthly = build_monthly_metrics(d20_events, taux, events)
    event_metrics = build_event_metrics(monthly)
    group_summary = summarize_groups(event_metrics)
    similarity = compare_patterns(d20_events, events)
    individual_similarity = compare_individual_patterns(d20_events, events)
    sensitivity = baseline_sensitivity(events)
    validation = validate_equatorial_proxy(d20_all)

    events.to_csv(OUT_DATA / "official_roni_event_classes.csv", index=False)
    d20_events[
        ["time", "year", "month", "requested_lon", "d20_m", "anomaly", "product_type"]
    ].to_csv(OUT_DATA / "event_monthly_equatorial_d20_anomaly.csv", index=False)
    monthly.to_csv(OUT_DATA / "event_monthly_recharge_metrics.csv", index=False)
    event_metrics.to_csv(OUT_DATA / "event_recharge_summary.csv", index=False)
    group_summary.to_csv(OUT_DATA / "group_recharge_summary.csv", index=False)
    similarity.to_csv(OUT_DATA / "2026_pattern_similarity.csv", index=False)
    individual_similarity.to_csv(
        OUT_DATA / "2026_individual_event_pattern_similarity.csv", index=False
    )
    sensitivity.to_csv(
        OUT_DATA / "2026_pattern_similarity_baseline_sensitivity.csv", index=False
    )
    (OUT_DATA / "equatorial_proxy_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    plot_hovmoller(d20_events, events)
    plot_official_class_hovmoller(d20_events, events)
    plot_indices(monthly, events)
    plot_official_class_indices(monthly, events)
    write_summary(
        events,
        event_metrics,
        group_summary,
        similarity,
        individual_similarity,
        sensitivity,
        validation,
    )

    run = {
        "baseline": f"{BASELINE_START}-{BASELINE_END}",
        "longitude_range": "135E-85W at 0 latitude",
        "historical_strength_index": "NOAA/CPC RONI, ERSSTv6",
        "primary_strong_group": events.loc[
            events["peak_roni_c"] >= 1.5, "event_year"
        ].tolist(),
        "moderate_group": events.loc[
            events["roni_class"] == "moderate", "event_year"
        ].tolist(),
        "proxy_validation": validation,
    }
    (OUT_DIR / "run_summary.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
