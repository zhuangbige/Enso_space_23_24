#!/usr/bin/env python3
"""Test whether Jiang-type northeasterlies directly open the 5N H20 exit.

The analysis distinguishes three physically different quantities:

1. ERA5 925-hPa northeasterly residual in the Jiang box (3-7N,
   180E-130W) during May-July of the El Nino development year.
2. ERA5 eastward turbulent surface stress over the same season, with
   westward stress defined as positive.
3. SODA3 westward surface stress and Q20 across 5N, 140W-80W during
   January-May of the following year.

All MJJ atmosphere variables are detrended and residualized month by month
against Nino3.4 and the east-minus-central SST type index, matching the
existing Jiang-box diagnosis.  SODA3 decay stress uses the same-month
1980-2014 anomaly definition used by the 1997/2015/2023 H20 fate analysis.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_5n_current_decomposition as soda_decomp  # noqa: E402

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_maryland_ne_h20_mpl")
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt


RAW_ERA5 = ROOT / "data/raw/era5/pre1980_fep_mjj_1deg"
PRESSURE_TEMPLATE = RAW_ERA5 / "era5_pressure925_m{month:02d}_1960_2024_1deg.nc"
STRESS_TEMPLATE = (
    RAW_ERA5
    / "era5_surface_m{month:02d}_1960_2024_1deg"
    / "data_stream-moda_stepType-avgad.nc"
)
COUPLING_MONTHLY = (
    ROOT / "data/derived/research_2026/enso_full_year_coupling_monthly_1982_2024.csv"
)
NE850_EVENTS = ROOT / "data/derived/research_2026/enso_ne_wind_bridge_event_indices.csv"
Q5N_EVENTS = (
    ROOT / "data/derived/research_2026/third_question_coupled_attribution_event_table.csv"
)
SODA_SECTION = (
    ROOT / "data/interim/research_2026/soda3_5n_geostrophic_sections_1980_2022.nc"
)
SODA_2024 = ROOT / "data/interim/research_2026/soda3_5n_geostrophic_section_2024_jan_may.nc"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/jiang_ne_wind_h20_exit"
EVENT_CSV = DERIVED / "jiang_ne_wind_h20_exit_event_table.csv"
RELATION_CSV = DERIVED / "jiang_ne_wind_h20_exit_relationships.csv"
PROFILE_CSV = DERIVED / "jiang_ne_surface_stress_longitude_profile.csv"
DIAGNOSTICS_JSON = DERIVED / "jiang_ne_wind_h20_exit_diagnostics.json"
FIGURE_PNG = OUT / "jiang_ne_wind_to_5n_h20_exit.png"
FIGURE_PDF = OUT / "jiang_ne_wind_to_5n_h20_exit.pdf"
REPORT_MD = OUT / "JIANG_NE_WIND_TO_5N_H20_EXIT_CN.md"

EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
MJJ = (5, 6, 7)
RANDOM_SEED = 20260808
N_PERMUTATIONS = 50_000
N_BOOTSTRAP = 20_000

STRESS_BOXES = {
    "jiang": (3.0, 7.0, 180.0, 230.0),
    "overlap": (3.0, 7.0, 220.0, 230.0),
    "exit": (4.0, 6.0, 220.0, 280.0),
    "exit_west": (4.0, 6.0, 220.0, 250.0),
    "exit_east": (4.0, 6.0, 250.0, 280.0),
}


def normalize(dataset: xr.Dataset) -> xr.Dataset:
    rename = {
        old: new
        for old, new in (
            ("valid_time", "time"),
            ("latitude", "lat"),
            ("longitude", "lon"),
        )
        if old in dataset.coords
    }
    output = dataset.rename(rename)
    if "pressure_level" in output.dims:
        output = output.squeeze("pressure_level", drop=True)
    return output.assign_coords(lon=output.lon % 360).sortby(["lat", "lon"])


def area_mean(field: xr.DataArray, bounds: tuple[float, float, float, float]) -> xr.DataArray:
    lat0, lat1, lon0, lon1 = bounds
    subset = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def latitude_mean(field: xr.DataArray, lat0: float, lat1: float) -> xr.DataArray:
    subset = field.sel(lat=slice(lat0, lat1), lon=slice(180.0, 280.0))
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean("lat", skipna=True)


def load_mjj_atmosphere() -> tuple[pd.DataFrame, xr.DataArray]:
    """Read 925-hPa wind and surface stress for 1982-2024 MJJ."""
    wind_rows: list[dict[str, float | int]] = []
    stress_rows: list[dict[str, float | int]] = []
    profile_parts: list[xr.DataArray] = []
    for month in MJJ:
        with xr.open_dataset(PRESSURE_TEMPLATE.with_name(PRESSURE_TEMPLATE.name.format(month=month))) as raw:
            wind = normalize(raw).sel(time=slice("1982", "2024"))
            box_u = area_mean(wind["u"], (3.0, 7.0, 180.0, 230.0)).load()
            box_v = area_mean(wind["v"], (3.0, 7.0, 180.0, 230.0)).load()
            for time, u, v in zip(pd.to_datetime(box_u.time.values), box_u.values, box_v.values):
                wind_rows.append(
                    {
                        "year": int(time.year),
                        "month": int(time.month),
                        "u925_jiang_ms": float(u),
                        "v925_jiang_ms": float(v),
                        "ne925_jiang_ms": float(-(u + v) / np.sqrt(2.0)),
                    }
                )

        stress_path = Path(str(STRESS_TEMPLATE).format(month=month))
        with xr.open_dataset(stress_path) as raw:
            stress = normalize(raw).sel(time=slice("1982", "2024"))
            for name, bounds in STRESS_BOXES.items():
                series = area_mean(stress["avg_iews"], bounds).load()
                for time, value in zip(pd.to_datetime(series.time.values), series.values):
                    stress_rows.append(
                        {
                            "year": int(time.year),
                            "month": int(time.month),
                            "box": name,
                            "taux_nm2": float(value),
                        }
                    )
            profile_parts.append(latitude_mean(stress["avg_iews"], 3.0, 7.0).load())

    wind_frame = pd.DataFrame(wind_rows)
    stress_frame = (
        pd.DataFrame(stress_rows)
        .pivot(index=["year", "month"], columns="box", values="taux_nm2")
        .reset_index()
    )
    profile = xr.concat(profile_parts, dim="time").sortby("time")
    return wind_frame.merge(stress_frame, on=["year", "month"], validate="one_to_one"), profile


def anomaly_detrend(frame: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    output = frame.copy()
    decimal_year = output.year + (output.month - 0.5) / 12.0
    for variable in variables:
        climatology = output.groupby("month")[variable].transform("mean")
        anomaly = output[variable] - climatology
        slope, intercept = np.polyfit(decimal_year, anomaly, 1)
        output[f"{variable}_ad"] = anomaly - (slope * decimal_year + intercept)
    return output


def residualize_monthly(
    frame: pd.DataFrame, variables: list[str], suffix: str = "_residual"
) -> pd.DataFrame:
    coupling = pd.read_csv(
        COUPLING_MONTHLY,
        usecols=["year", "month", "nino34_raw_c", "sst_type_raw_c"],
    )
    merged = frame.merge(coupling, on=["year", "month"], validate="one_to_one")
    pieces: list[pd.DataFrame] = []
    for month, group in merged.groupby("month"):
        design = np.column_stack(
            [
                np.ones(len(group)),
                group.year.to_numpy(dtype=float) - 2003.0,
                group.nino34_raw_c.to_numpy(dtype=float),
                group.sst_type_raw_c.to_numpy(dtype=float),
            ]
        )
        current = group[["year", "month"]].copy()
        for variable in variables:
            values = group[f"{variable}_ad"].to_numpy(dtype=float)
            coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
            current[f"{variable}{suffix}"] = values - design @ coefficients
        pieces.append(current)
    return merged.merge(pd.concat(pieces, ignore_index=True), on=["year", "month"])


def residualize_profile(profile: xr.DataArray) -> xr.DataArray:
    """Apply the scalar atmospheric residual definition at every longitude."""
    times = pd.to_datetime(profile.time.values)
    values = profile.values.astype(float)
    years = times.year.to_numpy()
    months = times.month.to_numpy()
    decimal_year = years + (months - 0.5) / 12.0
    coupling = pd.read_csv(
        COUPLING_MONTHLY,
        usecols=["year", "month", "nino34_raw_c", "sst_type_raw_c"],
    ).set_index(["year", "month"])
    nino = np.array([coupling.loc[(y, m), "nino34_raw_c"] for y, m in zip(years, months)])
    sst_type = np.array([coupling.loc[(y, m), "sst_type_raw_c"] for y, m in zip(years, months)])

    adjusted = np.full_like(values, np.nan, dtype=float)
    for month in MJJ:
        indices = np.where(months == month)[0]
        current = values[indices]
        anomaly = current - np.nanmean(current, axis=0, keepdims=True)
        x = decimal_year[indices] - np.mean(decimal_year[indices])
        denominator = np.sum(x**2)
        slope = np.nansum(x[:, None] * anomaly, axis=0) / denominator
        adjusted[indices] = anomaly - x[:, None] * slope[None, :]

    residual = np.full_like(adjusted, np.nan)
    for month in MJJ:
        indices = np.where(months == month)[0]
        design = np.column_stack(
            [
                np.ones(len(indices)),
                years[indices] - 2003.0,
                nino[indices],
                sst_type[indices],
            ]
        )
        coefficients = np.linalg.lstsq(design, adjusted[indices], rcond=None)[0]
        residual[indices] = adjusted[indices] - design @ coefficients
    return xr.DataArray(
        residual,
        dims=("time", "lon"),
        coords={"time": profile.time, "lon": profile.lon},
        name="taux_residual_nm2",
    )


def build_development_indices() -> tuple[pd.DataFrame, pd.DataFrame]:
    atmosphere, profile = load_mjj_atmosphere()
    variables = ["u925_jiang_ms", "v925_jiang_ms", "ne925_jiang_ms", *STRESS_BOXES]
    processed = residualize_monthly(anomaly_detrend(atmosphere, variables), variables)
    aggregation: dict[str, tuple[str, str | object]] = {
        "ne925_mjj_ms": ("ne925_jiang_ms_residual", "mean"),
        "easterly925_mjj_ms": (
            "u925_jiang_ms_residual",
            lambda values: -float(np.mean(values)),
        ),
        "northerly925_mjj_ms": (
            "v925_jiang_ms_residual",
            lambda values: -float(np.mean(values)),
        ),
    }
    for name in STRESS_BOXES:
        aggregation[f"westward_taux_{name}_mjj_nm2"] = (
            f"{name}_residual",
            lambda values: -float(np.mean(values)),
        )
    seasonal = processed.groupby("year").agg(**aggregation).reset_index()

    profile_residual = residualize_profile(profile)
    event_profile = []
    for year in EVENT_YEARS:
        selected = profile_residual.sel(time=profile_residual.time.dt.year == year)
        event_profile.append((-selected.mean("time")).assign_coords(event=year))
    stress_events = xr.concat(event_profile, dim="event")
    ne = seasonal.set_index("year").loc[list(EVENT_YEARS), "ne925_mjj_ms"].to_numpy()
    correlations = np.array(
        [
            np.corrcoef(ne, stress_events[:, index].values)[0, 1]
            for index in range(stress_events.sizes["lon"])
        ]
    )
    profile_frame = pd.DataFrame(
        {
            "lon_e": stress_events.lon.values,
            "pearson_r_ne925_vs_westward_taux": correlations,
        }
    )
    return seasonal, profile_frame


def build_decay_stress() -> pd.DataFrame:
    """Calculate Jan-May(+1) SODA3 westward-stress anomalies."""
    with xr.open_dataset(SODA_SECTION) as base, xr.open_dataset(SODA_2024) as recent:
        times = pd.DatetimeIndex(base.time.values).append(pd.DatetimeIndex(recent.time.values))
        values = np.concatenate(
            [base.taux.values.astype(float), recent.taux.values.astype(float)], axis=0
        )
        lon = base.lon.values.astype(float)
    anomaly = soda_decomp.same_month_detrended_array(values, times, baseline=(1980, 2014))
    rows = []
    for year in EVENT_YEARS:
        indices = np.where(
            (times.year == year + 1) & np.isin(times.month, [1, 2, 3, 4, 5])
        )[0]
        if len(indices) != 5:
            raise ValueError(f"Missing following Jan-May SODA3 section for {year}")
        row: dict[str, float | int] = {"year": year}
        for name, (lon0, lon1) in {
            "all": (220.0, 280.0),
            "west": (220.0, 250.0),
            "east": (250.0, 280.0),
        }.items():
            mask = (lon >= lon0) & (lon <= lon1)
            row[f"westward_taux_decay_{name}_nm2"] = float(
                -np.nanmean(anomaly[indices][:, mask])
            )
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_ci(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    samples = np.full(N_BOOTSTRAP, np.nan)
    for index in range(N_BOOTSTRAP):
        selected = rng.integers(0, len(x), len(x))
        if np.std(x[selected]) > 0 and np.std(y[selected]) > 0:
            samples[index] = np.corrcoef(x[selected], y[selected])[0, 1]
    return tuple(np.nanpercentile(samples, [2.5, 97.5]).astype(float))


def relationship(
    frame: pd.DataFrame, label: str, x_name: str, y_name: str, seed_offset: int
) -> dict[str, float | int | str]:
    x = frame[x_name].to_numpy(dtype=float)
    y = frame[y_name].to_numpy(dtype=float)
    observed = float(np.corrcoef(x, y)[0, 1])
    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    permuted = np.empty(N_PERMUTATIONS)
    for index in range(N_PERMUTATIONS):
        permuted[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
    permutation_p = float((np.sum(np.abs(permuted) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1))
    low, high = bootstrap_ci(x, y, rng)
    leave_one_out = [
        np.corrcoef(np.delete(x, index), np.delete(y, index))[0, 1]
        for index in range(len(x))
    ]
    return {
        "relationship": label,
        "x": x_name,
        "y": y_name,
        "n_events": len(frame),
        "pearson_r": observed,
        "permutation_p": permutation_p,
        "bootstrap_ci_low": low,
        "bootstrap_ci_high": high,
        "loeo_r_min": float(np.min(leave_one_out)),
        "loeo_r_max": float(np.max(leave_one_out)),
    }


def build_event_table() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    development, profile = build_development_indices()
    decay = build_decay_stress()
    ne850 = pd.read_csv(NE850_EVENTS)[
        ["year", "ne850_mjj", "easterly850_mjj", "northerly850_mjj"]
    ]
    q5n = pd.read_csv(Q5N_EVENTS)
    events = (
        q5n.merge(ne850, on="year", validate="one_to_one")
        .merge(development, on="year", validate="one_to_one")
        .merge(decay, on="year", validate="one_to_one")
        .sort_values("year")
        .reset_index(drop=True)
    )

    tests = [
        (
            "Immediate vertical projection: NE925 -> Jiang-box westward surface stress",
            "ne925_mjj_ms",
            "westward_taux_jiang_mjj_nm2",
        ),
        (
            "Immediate western exit projection: NE925 -> 140W-110W stress",
            "ne925_mjj_ms",
            "westward_taux_exit_west_mjj_nm2",
        ),
        (
            "Immediate eastern exit projection: NE925 -> 110W-80W stress",
            "ne925_mjj_ms",
            "westward_taux_exit_east_mjj_nm2",
        ),
        (
            "Cross-season link: NE925 -> following 5N Ekman Q20",
            "ne925_mjj_ms",
            "q5n_ekman_jan_may1_zj",
        ),
        (
            "Cross-season link: NE925 -> following total 5N Q20",
            "ne925_mjj_ms",
            "q5n_total_jan_may1_zj",
        ),
        (
            "Persistence test: NE925 -> following local westward stress",
            "ne925_mjj_ms",
            "westward_taux_decay_all_nm2",
        ),
        (
            "Late wind control: following westward stress -> Ekman Q20",
            "westward_taux_decay_all_nm2",
            "q5n_ekman_jan_may1_zj",
        ),
        (
            "Late wind control: following westward stress -> total Q20",
            "westward_taux_decay_all_nm2",
            "q5n_total_jan_may1_zj",
        ),
        (
            "Pressure competition: geostrophic Q20 -> total Q20",
            "q5n_geo_eos80_jan_may1_zj",
            "q5n_total_jan_may1_zj",
        ),
    ]
    relationships = pd.DataFrame(
        [relationship(events, label, x, y, index) for index, (label, x, y) in enumerate(tests)]
    )
    return events, relationships, profile


def longitude_label(value: float) -> str:
    if value == 180:
        return "180°"
    return f"{360 - value:g}°W"


def format_p(value: float, digits: int = 3) -> str:
    threshold = 10.0 ** (-digits)
    return f"<{threshold:.{digits}f}" if value < threshold else f"={value:.{digits}f}"


def scatter_panel(
    axis: plt.Axes,
    frame: pd.DataFrame,
    x_name: str,
    y_name: str,
    x_label: str,
    y_label: str,
    relation: pd.Series,
    panel_title: str,
) -> None:
    x = frame[x_name].to_numpy(dtype=float)
    y = frame[y_name].to_numpy(dtype=float)
    ordinary = ~frame.year.isin([1997, 2015, 2023])
    axis.scatter(x[ordinary], y[ordinary], s=34, color="#8C8C8C", edgecolor="white", linewidth=0.5, zorder=3)
    colors = {1997: "#B2182B", 2015: "#2166AC", 2023: "#6A3D9A"}
    for year, color in colors.items():
        row = frame.loc[frame.year.eq(year)].iloc[0]
        axis.scatter(row[x_name], row[y_name], s=65, color=color, edgecolor="white", linewidth=0.7, zorder=4)
        axis.annotate(
            str(year),
            (row[x_name], row[y_name]),
            xytext=(4, 5),
            textcoords="offset points",
            fontsize=8.5,
            color=color,
        )
    slope, intercept = np.polyfit(x, y, 1)
    xx = np.linspace(np.min(x), np.max(x), 100)
    axis.plot(xx, slope * xx + intercept, color="#222222", lw=1.2)
    axis.axhline(0, color="0.65", lw=0.7)
    axis.axvline(0, color="0.65", lw=0.7)
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.set_title(panel_title, loc="left", fontweight="bold")
    axis.text(
        0.04,
        0.94,
        f"r = {relation.pearson_r:+.2f}; permutation p {format_p(float(relation.permutation_p))}",
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=9,
    )


def plot_results(events: pd.DataFrame, relationships: pd.DataFrame, profile: pd.DataFrame) -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 300,
        }
    )
    OUT.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.1))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.88, bottom=0.10, hspace=0.36, wspace=0.28)

    ax = axes[0, 0]
    ax.axvspan(180, 230, color="#F3D7B5", alpha=0.55, label="Jiang NE box")
    ax.axvspan(220, 280, color="#BFDCEB", alpha=0.40, label="5°N H20 exit")
    ax.plot(profile.lon_e, profile.pearson_r_ne925_vs_westward_taux, color="#1F4E79", lw=2)
    ax.axhline(0, color="0.3", lw=0.8)
    ax.axhline(0.553, color="0.45", lw=0.8, ls="--")
    ax.axhline(-0.553, color="0.45", lw=0.8, ls="--")
    for boundary in (220, 230, 250):
        ax.axvline(boundary, color="0.4", lw=0.7, ls=":")
    ticks = [180, 200, 220, 230, 250, 270, 280]
    ax.set_xticks(ticks, [longitude_label(value) for value in ticks], rotation=25)
    ax.set_ylim(-1.0, 1.0)
    ax.set_ylabel("Event correlation with MJJ westward stress")
    ax.set_title("a  Jiang northeasterlies project mainly west of 110°W", loc="left", fontweight="bold")
    ax.text(
        0.98,
        0.96,
        "dashed: two-sided p=0.05",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
    )
    ax.legend(frameon=False, fontsize=8, loc="lower left")

    lookup = relationships.set_index("relationship")
    scatter_panel(
        axes[0, 1],
        events,
        "ne925_mjj_ms",
        "westward_taux_jiang_mjj_nm2",
        "MJJ Jiang-box NE925 residual (m s$^{-1}$)",
        "MJJ westward surface-stress residual (N m$^{-2}$)",
        lookup.loc["Immediate vertical projection: NE925 -> Jiang-box westward surface stress"],
        "b  The low-level anomaly reaches the surface locally",
    )
    scatter_panel(
        axes[1, 0],
        events,
        "ne925_mjj_ms",
        "q5n_ekman_jan_may1_zj",
        "MJJ Jiang-box NE925 residual (m s$^{-1}$)",
        "Following Jan-May 5°N Ekman $Q_{20}$ (ZJ)",
        lookup.loc["Cross-season link: NE925 -> following 5N Ekman Q20"],
        "c  Early northeasterlies do not directly open the later exit",
    )
    scatter_panel(
        axes[1, 1],
        events,
        "westward_taux_decay_all_nm2",
        "q5n_ekman_jan_may1_zj",
        "Following Jan-May local westward stress (N m$^{-2}$)",
        "Following Jan-May 5°N Ekman $Q_{20}$ (ZJ)",
        lookup.loc["Late wind control: following westward stress -> Ekman Q20"],
        "d  The outlet is controlled by the later local stress",
    )
    fig.suptitle(
        r"From Jiang-type northeasterlies to the 5°N $H_{20}$ exit: a two-stage wind control",
        fontsize=14,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.020,
        "13 warm events; ERA5 MJJ residuals remove trend, Niño-3.4 and SST type. "
        "SODA3 uses following Jan-May anomalies; westward stress and northward transport are positive.",
        ha="center",
        va="bottom",
        fontsize=7.8,
        color="0.25",
    )
    fig.savefig(FIGURE_PNG)
    fig.savefig(FIGURE_PDF)
    plt.close(fig)


def write_report(events: pd.DataFrame, relationships: pd.DataFrame, diagnostics: dict[str, float]) -> None:
    relation = relationships.set_index("relationship")
    immediate = relation.loc[
        "Immediate vertical projection: NE925 -> Jiang-box westward surface stress"
    ]
    western = relation.loc[
        "Immediate western exit projection: NE925 -> 140W-110W stress"
    ]
    eastern = relation.loc[
        "Immediate eastern exit projection: NE925 -> 110W-80W stress"
    ]
    delayed = relation.loc["Cross-season link: NE925 -> following 5N Ekman Q20"]
    persistence = relation.loc[
        "Persistence test: NE925 -> following local westward stress"
    ]
    late = relation.loc["Late wind control: following westward stress -> Ekman Q20"]
    total = relation.loc["Late wind control: following westward stress -> total Q20"]

    selected = events.loc[events.year.isin([1997, 2015, 2023])]
    selected_rows = []
    for row in selected.itertuples():
        selected_rows.append(
            f"| {row.year} | {row.ne925_mjj_ms:+.2f} | "
            f"{row.westward_taux_jiang_mjj_nm2:+.4f} | "
            f"{row.westward_taux_decay_all_nm2:+.4f} | "
            f"{row.q5n_ekman_jan_may1_zj:+.2f} | {row.q5n_geo_eos80_jan_may1_zj:+.2f} | "
            f"{row.q5n_total_jan_may1_zj:+.2f} |"
        )

    report = f"""# 从Jiang东北风到5°N H20出口：第一轮直接检验

## 结论

Jiang型东北风确实能够向下投影为同期海面向西风应力，但这种投影主要局限在Jiang区及5°N出口的西段，并没有均匀延伸到整个140°W—80°W出口。更重要的是，发展期东北风并不直接延续为次年成熟—衰减期的北向Ekman暖量出口。

因此，当前结果不支持“同一股东北风直接打开后期5°N出口”的单阶段解释，而支持两个相互衔接但动力上不同的风门：

1. MJJ发展期东北风是耦合抑制门，主要抵消中太平洋西风；
2. 次年1—5月局地5°N向西风应力是暖量放电门，直接控制Ekman暖量输出。

## 直接证据

- MJJ 925 hPa东北风与同季Jiang区海面向西风应力：r={immediate.pearson_r:+.2f}，置换p{format_p(float(immediate.permutation_p), 4)}；925与现有850 hPa东北风指数相关为r={diagnostics['ne925_vs_ne850_r']:+.2f}。
- 东北风与出口西段140°W—110°W风应力：r={western.pearson_r:+.2f}；与出口东段110°W—80°W风应力：r={eastern.pearson_r:+.2f}。说明信号向东快速衰减并发生结构变化。
- MJJ东北风与次年1—5月5°N Ekman Q20：r={delayed.pearson_r:+.2f}，置换p{format_p(float(delayed.permutation_p), 4)}；不是预期的正向直接驱动。
- MJJ东北风与次年局地向西风应力：r={persistence.pearson_r:+.2f}。这表明早期东北风不是后期出口风应力的简单持续。
- 次年局地向西风应力与Ekman Q20：r={late.pearson_r:+.2f}，置换p{format_p(float(late.permutation_p), 4)}；与总Q20为r={total.pearson_r:+.2f}。后者较低是因为总出口还受到地转项和残差影响。

## 三个关键事件

| 事件 | MJJ NE925 | MJJ Jiang区向西应力 | 次年出口局地向西应力 | Ekman Q20 | 地转Q20 | 总Q20 |
|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(selected_rows)}

2023在MJJ具有最强的正东北风异常之一，但其后期局地向西风应力和总暖量出口都不强；2015在MJJ表现为东北风反向异常，却在后期形成更强的局地向西风应力和Ekman出口。1997则在后期同时获得强Ekman和正地转贡献。这三个事件直接否定了“早期东北风越强，后期北向放电越强”的简单解释。

## 对第三个问题的修正答案

海气耦合控制暖量命运的关键不在于一个东北风指标从春季一直持续到衰减期，而在于风场发生了阶段转换：早期Jiang型东北风决定中太平洋西风反馈能否接通；只有成功建立的盆地尺度耦合，才可能在成熟—衰减期形成东部5°N局地应力和压力场配置，从而打开暖量出口。

新的核心链条应写为：

```text
FEP增暖与降水偶极
        ↓
MJJ赤道以北东北风（发展期耦合抑制门）
        ↓
中太平洋西风/Bjerknes反馈是否接通
        ↓
成熟期对流、风应力和SSH结构
        ↓
次年5°N局地向西应力 + 地转压力项
        ↓
东太平洋H20北向释放或滞留
```

## 证据边界

- 13个事件仍是小样本，置换检验和整事件bootstrap只用于约束统计不确定性。
- 发展期与衰减期相关不能证明中间每一步的因果；需要逐月空间演变或模式扰动补充。
- ERA5风应力和SODA3 Ekman Q20来自不同产品，二者在这里分别承担独立大气投影和海洋响应诊断，不强制逐月完全相等。
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    events, relationships, profile = build_event_table()
    diagnostics = {
        "ne925_vs_ne850_r": float(np.corrcoef(events.ne925_mjj_ms, events.ne850_mjj)[0, 1]),
        "event_count": int(len(events)),
        "profile_lon_min": float(profile.lon_e.min()),
        "profile_lon_max": float(profile.lon_e.max()),
    }
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    relationships.to_csv(RELATION_CSV, index=False, float_format="%.9g")
    profile.to_csv(PROFILE_CSV, index=False, float_format="%.9g")
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_results(events, relationships, profile)
    write_report(events, relationships, diagnostics)
    for path in (EVENT_CSV, RELATION_CSV, PROFILE_CSV, FIGURE_PNG, FIGURE_PDF, REPORT_MD):
        print(path)


if __name__ == "__main__":
    main()
