#!/usr/bin/env python3
"""Compare January--June FEP SSTA and 0--300 m OHC for all warm events.

The primary sample is read from the project's 13-event coupling summary.  The
consecutive 1987/88 warm event, omitted from that primary statistical sample,
is retained as a sensitivity case.  OISST and SODA are both expressed as
1982--2024 same-calendar-month detrended anomalies and averaged on the same
time-invariant, complete 0--300 m SODA ocean footprint.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / "outputs/research_2026/font_cache"))

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr


matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, TwoSlopeNorm
from matplotlib.patches import Patch, Rectangle

from plot_enso_year_jan_jun_ssta_winda import open_oisst
from verify_2023_ssta_ohc_vertical_mismatch import (
    detrended_same_month,
    integrate_temperature_anomaly,
)


TEMP_FILE = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
EVENT_FILE = ROOT / "data/derived/research_2026/enso_type_coupling_event_summary.csv"
MANIFEST_FILE = ROOT / "data/derived/research_2026/jiang2026_epcp_fep_event_manifest_1963_2023.csv"
OUT_DIR = ROOT / "outputs/research_2026/soda3_all_warm_event_ssta_ohc_mismatch"
DERIVED_DIR = ROOT / "data/derived/research_2026"

MONTHS = (1, 2, 3, 4, 5, 6)
MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun")
BASELINE = (1982, 2024)
SENSITIVITY_EVENT = 1987
REGIONS = {
    "fep_90W_80W": (-5.0, 5.0, 270.0, 280.0),
    "east_140W_80W": (-5.0, 5.0, 220.0, 280.0),
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "font.size": 9.2,
            "axes.titlesize": 11.0,
            "axes.labelsize": 9.6,
            "xtick.labelsize": 8.6,
            "ytick.labelsize": 8.2,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
        }
    )


def load_event_sample() -> pd.DataFrame:
    primary = pd.read_csv(EVENT_FILE)[["year", "group"]].copy()
    primary["year"] = primary.year.astype(int)
    primary["primary_sample"] = True
    if len(primary) != 13 or 2023 not in set(primary.year):
        raise ValueError("The primary coupling event table is not the expected 13-event sample")

    manifest = pd.read_csv(MANIFEST_FILE)
    sensitivity = manifest.loc[manifest.event_year.eq(SENSITIVITY_EVENT)].iloc[0]
    extra = pd.DataFrame(
        [
            {
                "year": SENSITIVITY_EVENT,
                "group": f"{sensitivity.mature_type_working} consecutive sensitivity",
                "primary_sample": False,
            }
        ]
    )
    return pd.concat([primary, extra], ignore_index=True).sort_values("year").reset_index(drop=True)


def build_common_fields() -> tuple[xr.DataArray, xr.DataArray, xr.DataArray, xr.DataArray]:
    with xr.open_dataset(TEMP_FILE) as ds:
        if ds.temp.dims != ("time", "depth", "lat", "lon"):
            raise ValueError(f"Unexpected SODA temperature dimensions: {ds.temp.dims}")
        if ds.temp.attrs.get("units") != "degC":
            raise ValueError(f"Unexpected SODA temperature units: {ds.temp.attrs.get('units')}")
        temperature = ds.temp.load()

    soda_times = pd.DatetimeIndex(temperature.time.values)
    temperature_anomaly = detrended_same_month(
        temperature.values,
        soda_times,
        BASELINE[0],
        BASELINE[1],
    )
    ohc = integrate_temperature_anomaly(
        temperature_anomaly,
        temperature.depth.values.astype(float),
        0.0,
        300.0,
    )
    ohc_da = xr.DataArray(
        ohc / 1.0e9,
        dims=("time", "lat", "lon"),
        coords={"time": temperature.time, "lat": temperature.lat, "lon": temperature.lon},
        name="ohc300_anomaly",
        attrs={"units": "GJ m-2", "baseline": "1982-2024"},
    )
    soda_surface_da = xr.DataArray(
        temperature_anomaly[:, 0],
        dims=("time", "lat", "lon"),
        coords={"time": temperature.time, "lat": temperature.lat, "lon": temperature.lon},
        name="soda_surface_temperature_anomaly",
        attrs={
            "units": "degC",
            "baseline": "1982-2024",
            "depth_m": float(temperature.depth.values[0]),
        },
    )
    stable_soda_ocean = xr.DataArray(
        np.isfinite(temperature.values).all(axis=(0, 1)),
        dims=("lat", "lon"),
        coords={"lat": temperature.lat, "lon": temperature.lon},
    )

    sst = open_oisst().load()
    if str(sst.attrs.get("units", "")).lower() not in {"degc", "degree_celsius", "degrees c"}:
        raise ValueError(f"Unexpected OISST units: {sst.attrs.get('units')}")
    sst_times = pd.DatetimeIndex(sst.time.values)
    ssta = detrended_same_month(sst.values, sst_times, BASELINE[0], BASELINE[1])
    ssta_da = xr.DataArray(
        ssta,
        dims=sst.dims,
        coords=sst.coords,
        name="ssta",
        attrs={"units": "degC", "baseline": "1982-2024"},
    )
    ssta_on_soda = ssta_da.interp(lat=ohc_da.lat, lon=ohc_da.lon, method="linear")
    stable_oisst_ocean = np.isfinite(ssta_on_soda).all("time")
    common_footprint = stable_soda_ocean & stable_oisst_ocean
    return ssta_on_soda, soda_surface_da, ohc_da, common_footprint


def regional_series(
    field: xr.DataArray,
    footprint: xr.DataArray,
    bounds: tuple[float, float, float, float],
) -> xr.DataArray:
    lat0, lat1, lon0, lon1 = bounds
    region = (
        (field.lat >= lat0)
        & (field.lat <= lat1)
        & (field.lon >= lon0)
        & (field.lon <= lon1)
        & footprint
    )
    weights = np.cos(np.deg2rad(field.lat)).broadcast_like(footprint).where(region, 0.0)
    denominator = weights.sum(("lat", "lon"))
    if float(denominator) <= 0:
        raise ValueError(f"Empty common footprint for bounds {bounds}")
    return (field.where(region) * weights).sum(("lat", "lon"), skipna=True) / denominator


def build_monthly_table(
    sample: pd.DataFrame,
    ssta: xr.DataArray,
    soda_surface: xr.DataArray,
    ohc: xr.DataArray,
    footprint: xr.DataArray,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for region_name, bounds in REGIONS.items():
        ssta_series = regional_series(ssta, footprint, bounds)
        soda_surface_series = regional_series(soda_surface, footprint, bounds)
        ohc_series = regional_series(ohc, footprint, bounds)
        ssta_frame = pd.DataFrame(
            {
                "year": ssta_series.time.dt.year.values.astype(int),
                "month": ssta_series.time.dt.month.values.astype(int),
                "ssta_c": ssta_series.values.astype(float),
            }
        )
        ohc_frame = pd.DataFrame(
            {
                "year": ohc_series.time.dt.year.values.astype(int),
                "month": ohc_series.time.dt.month.values.astype(int),
                "ohc300_gj_m2": ohc_series.values.astype(float),
            }
        )
        soda_surface_frame = pd.DataFrame(
            {
                "year": soda_surface_series.time.dt.year.values.astype(int),
                "month": soda_surface_series.time.dt.month.values.astype(int),
                "soda_surface_ta_c": soda_surface_series.values.astype(float),
            }
        )
        all_years = (
            ssta_frame.merge(ohc_frame, on=["year", "month"], validate="one_to_one")
            .merge(soda_surface_frame, on=["year", "month"], validate="one_to_one")
        )
        baseline = all_years.loc[all_years.year.between(*BASELINE)].copy()
        month_std = baseline.groupby("month").agg(
            ssta_sd_c=("ssta_c", "std"),
            soda_surface_sd_c=("soda_surface_ta_c", "std"),
            ohc300_sd_gj_m2=("ohc300_gj_m2", "std"),
        )
        selected = all_years.loc[all_years.year.isin(sample.year)].copy()
        selected = selected.merge(sample, on="year", how="left", validate="many_to_one")
        selected["region"] = region_name
        selected["ssta_z"] = selected.ssta_c / selected.month.map(month_std.ssta_sd_c)
        selected["soda_surface_z"] = selected.soda_surface_ta_c / selected.month.map(
            month_std.soda_surface_sd_c
        )
        selected["ohc300_z"] = selected.ohc300_gj_m2 / selected.month.map(
            month_std.ohc300_sd_gj_m2
        )
        selected["surface_positive_ohc_negative"] = (
            selected.ssta_c.gt(0.0) & selected.ohc300_gj_m2.lt(0.0)
        )
        selected["soda_surface_positive_ohc_negative"] = (
            selected.soda_surface_ta_c.gt(0.0) & selected.ohc300_gj_m2.lt(0.0)
        )
        selected["standardized_contrast"] = selected.ssta_z - selected.ohc300_z
        records.extend(selected.to_dict("records"))

    output = pd.DataFrame(records).sort_values(["region", "year", "month"]).reset_index(drop=True)
    expected = len(REGIONS) * len(sample) * len(MONTHS)
    if len(output) != expected:
        raise ValueError(f"Expected {expected} event-month rows, got {len(output)}")
    return output


def first_positive_month(series: pd.Series, months: pd.Series) -> int | None:
    positive = months.loc[series.gt(0.0)]
    return None if positive.empty else int(positive.iloc[0])


def summarize_events(monthly: pd.DataFrame) -> pd.DataFrame:
    reference: dict[str, pd.Series] = {}
    for region in REGIONS:
        row = monthly.loc[
            monthly.region.eq(region) & monthly.year.eq(2023) & monthly.month.eq(2)
        ]
        if len(row) != 1:
            raise ValueError(f"Missing unique February 2023 reference for {region}")
        reference[region] = row.iloc[0]

    rows: list[dict[str, object]] = []
    for (region, year), event in monthly.groupby(["region", "year"], sort=True):
        event = event.sort_values("month").reset_index(drop=True)
        ssta_first = first_positive_month(event.ssta_c, event.month)
        soda_surface_first = first_positive_month(event.soda_surface_ta_c, event.month)
        ohc_first = first_positive_month(event.ohc300_gj_m2, event.month)
        mismatch = event.loc[event.surface_positive_ohc_negative]
        soda_mismatch = event.loc[event.soda_surface_positive_ohc_negative]
        mismatch_months = ",".join(str(int(value)) for value in mismatch.month)
        january = event.loc[event.month.eq(1)].iloc[0]
        strict_sequence = bool(
            january.ssta_c <= 0.0
            and january.ohc300_gj_m2 <= 0.0
            and ssta_first is not None
            and ohc_first is not None
            and ssta_first < ohc_first
            and bool(event.loc[event.month.eq(ohc_first), "ssta_c"].iloc[0] > 0.0)
        )
        strict_same_product_sequence = bool(
            january.soda_surface_ta_c <= 0.0
            and january.ohc300_gj_m2 <= 0.0
            and soda_surface_first is not None
            and ohc_first is not None
            and soda_surface_first < ohc_first
            and bool(event.loc[event.month.eq(ohc_first), "soda_surface_ta_c"].iloc[0] > 0.0)
        )
        ref = reference[region]
        at_least_2023_raw = bool(
            (
                mismatch.ssta_c.ge(float(ref.ssta_c))
                & mismatch.ohc300_gj_m2.le(float(ref.ohc300_gj_m2))
            ).any()
        )
        at_least_2023_contrast = bool(
            mismatch.standardized_contrast.ge(float(ref.standardized_contrast)).any()
        )
        robust_2023_sequence = bool(strict_sequence and at_least_2023_raw)
        robust_same_product_sequence = bool(
            strict_same_product_sequence
            and (
                soda_mismatch.soda_surface_ta_c.ge(float(ref.soda_surface_ta_c))
                & soda_mismatch.ohc300_gj_m2.le(float(ref.ohc300_gj_m2))
            ).any()
        )
        rows.append(
            {
                "region": region,
                "year": int(year),
                "group": str(event.group.iloc[0]),
                "primary_sample": bool(event.primary_sample.iloc[0]),
                "first_positive_ssta_month": ssta_first,
                "first_positive_soda_surface_month": soda_surface_first,
                "first_positive_ohc_month": ohc_first,
                "ohc_minus_ssta_onset_lag_months": (
                    np.nan if ssta_first is None or ohc_first is None else ohc_first - ssta_first
                ),
                "any_surface_positive_ohc_negative": not mismatch.empty,
                "any_soda_surface_positive_ohc_negative": not soda_mismatch.empty,
                "mismatch_months": mismatch_months,
                "n_mismatch_months": int(len(mismatch)),
                "strict_2023_sequence": strict_sequence,
                "robust_2023_sequence": robust_2023_sequence,
                "strict_same_product_sequence": strict_same_product_sequence,
                "robust_same_product_sequence": robust_same_product_sequence,
                "at_least_feb2023_raw_strength": at_least_2023_raw,
                "at_least_feb2023_standardized_contrast": at_least_2023_contrast,
                "max_standardized_contrast_during_mismatch": (
                    np.nan if mismatch.empty else float(mismatch.standardized_contrast.max())
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["region", "year"]).reset_index(drop=True)


def draw_month_matrix(
    ax: plt.Axes,
    values: np.ndarray,
    mismatch: np.ndarray,
    years: list[int],
    *,
    title: str,
    cmap: str,
    vlim: float,
    colorbar_label: str,
) -> None:
    mesh = ax.pcolormesh(
        np.arange(0.5, 6.6, 1.0),
        np.arange(-0.5, len(years) + 0.5, 1.0),
        values,
        cmap=cmap,
        norm=TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim),
        shading="flat",
    )
    ax.set_xlim(0.5, 6.5)
    ax.set_ylim(len(years) - 0.5, -0.5)
    ax.set_xticks(range(1, 7), MONTH_LABELS)
    ax.set_yticks(range(len(years)), [str(year) for year in years])
    ax.set_title(title, fontweight="bold", pad=7)
    ax.set_xlabel("Development-year month")
    for row, col in zip(*np.where(mismatch)):
        ax.add_patch(
            Rectangle(
                (col + 0.5, row - 0.5),
                1.0,
                1.0,
                fill=False,
                edgecolor="black",
                linewidth=1.5,
            )
        )
    target_row = years.index(2023)
    ax.add_patch(
        Rectangle(
            (0.505, target_row - 0.48),
            5.99,
            0.96,
            fill=False,
            edgecolor="#8E44AD",
            linewidth=2.1,
        )
    )
    colorbar = plt.colorbar(mesh, ax=ax, pad=0.018, fraction=0.046, extend="both")
    colorbar.set_label(colorbar_label)


def plot_primary_fep(monthly: pd.DataFrame, summary: pd.DataFrame) -> tuple[Path, Path]:
    data = monthly.loc[monthly.region.eq("fep_90W_80W") & monthly.primary_sample].copy()
    years = sorted(data.year.unique().astype(int).tolist())
    ssta = data.pivot(index="year", columns="month", values="ssta_c").loc[years, MONTHS].values
    ohc = data.pivot(index="year", columns="month", values="ohc300_gj_m2").loc[years, MONTHS].values
    mismatch = data.pivot(
        index="year", columns="month", values="surface_positive_ohc_negative"
    ).loc[years, MONTHS].values.astype(bool)
    event_summary = summary.loc[
        summary.region.eq("fep_90W_80W") & summary.primary_sample
    ].set_index("year").loc[years]

    fig = plt.figure(figsize=(14.8, 9.6))
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=(1.0, 1.0, 0.72),
        left=0.075,
        right=0.98,
        top=0.88,
        bottom=0.13,
        wspace=0.28,
    )
    ax_sst = fig.add_subplot(grid[0, 0])
    ax_ohc = fig.add_subplot(grid[0, 1], sharey=ax_sst)
    ax_lag = fig.add_subplot(grid[0, 2], sharey=ax_sst)
    draw_month_matrix(
        ax_sst,
        ssta,
        mismatch,
        years,
        title="FEP OISST SSTA",
        cmap="RdBu_r",
        vlim=2.5,
        colorbar_label="SSTA (°C)",
    )
    draw_month_matrix(
        ax_ohc,
        ohc,
        mismatch,
        years,
        title="FEP SODA3 0–300 m OHC",
        cmap="RdBu_r",
        vlim=1.8,
        colorbar_label="OHC anomaly (GJ m$^{-2}$)",
    )
    ax_ohc.tick_params(labelleft=False)

    lag = event_summary.ohc_minus_ssta_onset_lag_months.values.astype(float)
    colors = [
        "#8E44AD"
        if year == 2023
        else "#E67E22"
        if bool(event_summary.loc[year, "strict_2023_sequence"])
        else "#6C7A89"
        for year in years
    ]
    y = np.arange(len(years))
    ax_lag.axvline(0.0, color="0.25", linewidth=0.9)
    ax_lag.barh(y, np.nan_to_num(lag, nan=0.0), color=colors, height=0.62)
    missing = ~np.isfinite(lag)
    ax_lag.scatter(np.zeros(missing.sum()), y[missing], marker="x", color="0.15", s=30, zorder=3)
    ax_lag.set_xlim(-4.2, 4.2)
    ax_lag.set_xticks(range(-4, 5, 2))
    ax_lag.set_xlabel("OHC onset minus SSTA onset (months)\npositive = surface leads")
    ax_lag.set_title("First-positive-month lag", fontweight="bold", pad=7)
    ax_lag.tick_params(labelleft=False)
    ax_lag.grid(axis="x", color="0.88", linewidth=0.7)

    fig.suptitle(
        "Surface–column timing across 13 SODA3 warm events",
        fontsize=16,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.075,
        0.925,
        "FEP = 5°S–5°N, 90°W–80°W; 1982–2024 same-month detrended anomalies; common complete 0–300 m footprint",
        fontsize=9.2,
        color="0.30",
    )
    fig.legend(
        handles=[
            Patch(facecolor="white", edgecolor="black", linewidth=1.5, label="SSTA > 0 and OHC < 0"),
            Patch(facecolor="#E67E22", label="Strict surface-first sequence"),
            Patch(facecolor="#8E44AD", label="2023"),
        ],
        loc="lower center",
        bbox_to_anchor=(0.54, 0.035),
        ncol=3,
        frameon=False,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = "fig_13_soda3_warm_events_fep_ssta_ohc_jan_jun_1982_2024"
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(pdf, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    return png, pdf


def event_list(frame: pd.DataFrame, column: str) -> str:
    selected = frame.loc[frame[column], "year"].astype(int).tolist()
    return ", ".join(str(value) for value in selected) if selected else "none"


def write_report(monthly: pd.DataFrame, summary: pd.DataFrame) -> Path:
    lines = [
        "# SODA3 warm-event SSTA--OHC onset comparison",
        "",
        "Primary sample: 13 warm events from `enso_type_coupling_event_summary.csv`. The consecutive 1987/88 event is reported only as a sensitivity case.",
        "",
    ]
    for region in ("fep_90W_80W", "east_140W_80W"):
        primary = summary.loc[summary.region.eq(region) & summary.primary_sample]
        sensitivity = summary.loc[summary.region.eq(region) & ~summary.primary_sample]
        lines.extend(
            [
                f"## {region}",
                "",
                f"- Any January--June region-mean SSTA-positive/OHC-negative month: {int(primary.any_surface_positive_ohc_negative.sum())}/13 events ({event_list(primary, 'any_surface_positive_ohc_negative')}).",
                f"- Strict 2023 sequence (January both non-positive, SSTA first turns positive, OHC turns positive later): {int(primary.strict_2023_sequence.sum())}/13 events ({event_list(primary, 'strict_2023_sequence')}).",
                f"- Robust strict sequence (strict timing plus at least February-2023 raw mismatch strength): {int(primary.robust_2023_sequence.sum())}/13 events ({event_list(primary, 'robust_2023_sequence')}).",
                f"- Same-product SODA ~5 m versus SODA OHC, any mismatch: {int(primary.any_soda_surface_positive_ohc_negative.sum())}/13 events ({event_list(primary, 'any_soda_surface_positive_ohc_negative')}).",
                f"- Same-product robust strict sequence: {int(primary.robust_same_product_sequence.sum())}/13 events ({event_list(primary, 'robust_same_product_sequence')}).",
                f"- At least February-2023 raw mismatch strength: {int(primary.at_least_feb2023_raw_strength.sum())}/13 events ({event_list(primary, 'at_least_feb2023_raw_strength')}).",
                f"- At least February-2023 standardized contrast: {int(primary.at_least_feb2023_standardized_contrast.sum())}/13 events ({event_list(primary, 'at_least_feb2023_standardized_contrast')}).",
                f"- 1987/88 sensitivity: any mismatch={bool(sensitivity.any_surface_positive_ohc_negative.iloc[0])}, strict sequence={bool(sensitivity.strict_2023_sequence.iloc[0])}.",
                "",
            ]
        )
    target = monthly.loc[
        monthly.region.eq("fep_90W_80W") & monthly.year.eq(2023) & monthly.month.eq(2)
    ].iloc[0]
    lines.extend(
        [
            "## February 2023 reference",
            "",
            f"FEP OISST SSTA={target.ssta_c:+.3f} °C, SODA ~5 m temperature anomaly={target.soda_surface_ta_c:+.3f} °C, OHC={target.ohc300_gj_m2:+.3f} GJ m-2, standardized contrast={target.standardized_contrast:+.3f}.",
            "",
            "Black cell outlines in the figure mark months with SSTA > 0 and OHC < 0. A positive lag means the surface first-positive month precedes the OHC first-positive month.",
        ]
    )
    path = OUT_DIR / "SODA3_ALL_WARM_EVENT_SSTA_OHC_MISMATCH_CN.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    setup_style()
    sample = load_event_sample()
    ssta, soda_surface, ohc, footprint = build_common_fields()
    monthly = build_monthly_table(sample, ssta, soda_surface, ohc, footprint)
    summary = summarize_events(monthly)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly_path = DERIVED_DIR / "soda3_all_warm_event_fep_ssta_ohc_monthly_1982_2024.csv"
    summary_path = DERIVED_DIR / "soda3_all_warm_event_fep_ssta_ohc_summary_1982_2024.csv"
    monthly.to_csv(monthly_path, index=False)
    summary.to_csv(summary_path, index=False)
    png, pdf = plot_primary_fep(monthly, summary)
    report = write_report(monthly, summary)

    print(summary.loc[summary.region.eq("fep_90W_80W")].to_string(index=False))
    print(monthly_path)
    print(summary_path)
    print(png)
    print(pdf)
    print(report)


if __name__ == "__main__":
    main()
