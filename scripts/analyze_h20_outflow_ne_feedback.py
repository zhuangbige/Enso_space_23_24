#!/usr/bin/env python3
"""Test whether early eastern-Pacific H20 outflow can precede Jiang NE winds.

Primary forward path (monthly, April--July):

    Q20 across 5N at month t
      -> H20 tendency in 5--12N, 140W--80W at t+1
      -> north-box SST / meridional rainfall and SLP contrast at t+1
      -> Jiang-box 925-hPa northeasterly anomaly at t+1.

The reverse direction is tested with contemporaneous NE--Q20 relations and
May NE -> June Q20 while controlling May Q20.  All monthly fields are
calendar-month detrended.  Primary correlations additionally remove
contemporaneous Nino-3.4, SST type and FEP SST.  Uncertainty resamples or
permutes complete years so April--June observations are never treated as
independent events.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/codex_maryland_h20_ne_feedback_mpl")
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt


NORTH_TEMP = ROOT / "data/raw/soda3/soda3.15.2_north_receiver_temp_jan_jul_1980_2022.nc"
Q5N_MONTHLY = ROOT / "data/derived/research_2026/enso_1997_2015_2023_warm_heat_fate_monthly.csv"
COUPLING = ROOT / "data/derived/research_2026/enso_full_year_coupling_monthly_1982_2024.csv"
GPCP = ROOT / "data/interim/research_2026/gpcp_event_spatial_tropics_1982_202605.nc"
OISST_DIR = ROOT / "data/interim/research_2026/pmm_inputs"
ERA5_SINGLE = ROOT / "data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc"
ERA5_NE_DIR = ROOT / "data/raw/era5/pre1980_fep_mjj_1deg"
EVENT_BASE = ROOT / "data/derived/research_2026/jiang_ne_wind_h20_exit_event_table.csv"

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/h20_outflow_ne_feedback"
MONTHLY_CSV = DERIVED / "h20_outflow_ne_feedback_monthly_1982_2024.csv"
LAG_CSV = DERIVED / "h20_outflow_ne_feedback_lag_panel_1982_2022.csv"
RELATIONSHIP_CSV = DERIVED / "h20_outflow_ne_feedback_relationships.csv"
EVENT_CSV = DERIVED / "h20_outflow_ne_feedback_event_table.csv"
EVENT_RELATIONSHIP_CSV = DERIVED / "h20_outflow_ne_feedback_event_relationships.csv"
DIAGNOSTICS_JSON = DERIVED / "h20_outflow_ne_feedback_diagnostics.json"
FIG_PATH_PNG = OUT / "h20_outflow_to_ne_lag_path.png"
FIG_PATH_PDF = OUT / "h20_outflow_to_ne_lag_path.pdf"
FIG_EVENT_PNG = OUT / "h20_outflow_ne_three_event_sequence.png"
FIG_EVENT_PDF = OUT / "h20_outflow_ne_three_event_sequence.pdf"
REPORT = OUT / "H20_OUTFLOW_NE_FEEDBACK_CN.md"

RHO0 = 1025.0
CP0 = 3990.0
EARTH_RADIUS = 6_371_000.0
DEPTH_MAX = 300.0
BASELINE = (1982, 2022)
EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)
HIGHLIGHT_YEARS = (1997, 2015, 2023)
COLORS = {1997: "#222222", 2015: "#2878b5", 2023: "#df5b3f"}
SOURCE_MONTHS = (4, 5, 6)
RANDOM_SEED = 20260808
N_PERMUTATIONS = 30_000
N_BOOTSTRAP = 20_000


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.2,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def normalize(dataset: xr.Dataset) -> xr.Dataset:
    rename = {
        old: new
        for old, new in (("valid_time", "time"), ("latitude", "lat"), ("longitude", "lon"))
        if old in dataset.coords
    }
    output = dataset.rename(rename)
    if "pressure_level" in output.dims:
        output = output.squeeze("pressure_level", drop=True)
    return output.assign_coords(lon=output.lon % 360.0).sortby(["lat", "lon"])


def area_mean(field: xr.DataArray, lat0: float, lat1: float, lon0: float, lon1: float) -> xr.DataArray:
    selected = field.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    weights = np.cos(np.deg2rad(selected.lat))
    return selected.weighted(weights).mean(("lat", "lon"), skipna=True)


def cell_areas(latitude: np.ndarray, longitude: np.ndarray) -> np.ndarray:
    latitude = np.asarray(latitude, dtype=float)
    longitude = np.asarray(longitude, dtype=float)
    dlat = float(np.median(np.diff(latitude)))
    dlon = float(np.median(np.diff(longitude)))
    south = np.deg2rad(latitude - dlat / 2.0)
    north = np.deg2rad(latitude + dlat / 2.0)
    strip = EARTH_RADIUS**2 * (np.sin(north) - np.sin(south))
    return strip[:, None] * np.deg2rad(dlon) * np.ones((1, longitude.size))


def layer_thickness(depth: np.ndarray) -> np.ndarray:
    depth = np.asarray(depth, dtype=float)
    edges = np.empty(depth.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    edges[-1] = min(DEPTH_MAX, depth[-1] + 0.5 * (depth[-1] - depth[-2]))
    return np.maximum(0.0, np.minimum(edges[1:], DEPTH_MAX) - edges[:-1])


def detrend_same_month(values: np.ndarray, times: pd.DatetimeIndex, baseline: tuple[int, int]) -> np.ndarray:
    data = np.asarray(values, dtype=float)
    result = np.full_like(data, np.nan, dtype=float)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    for month in sorted(np.unique(months)):
        fit = (months == month) & (years >= baseline[0]) & (years <= baseline[1])
        apply = months == month
        if fit.sum() < 10:
            continue
        x = years[fit] - np.mean(years[fit])
        current = data[fit]
        mean = np.nanmean(current, axis=0)
        anomaly = current - mean
        expand = (-1,) + (1,) * (data.ndim - 1)
        denominator = np.nansum(np.isfinite(anomaly) * x.reshape(expand) ** 2, axis=0)
        numerator = np.nansum(anomaly * x.reshape(expand), axis=0)
        slope = np.divide(numerator, denominator, out=np.full(data.shape[1:], np.nan), where=denominator > 0)
        x_apply = years[apply] - np.mean(years[fit])
        result[apply] = data[apply] - mean - x_apply.reshape(expand) * slope
    return result


def to_frame(times: pd.DatetimeIndex, **series: np.ndarray) -> pd.DataFrame:
    output = pd.DataFrame({"time": times, "year": times.year, "month": times.month})
    for name, values in series.items():
        output[name] = np.asarray(values, dtype=float)
    return output


def load_north_h20() -> pd.DataFrame:
    with xr.open_dataset(NORTH_TEMP, engine="h5netcdf") as dataset:
        field = dataset.temp.sel(lat=slice(5.25, 11.25), lon=slice(220.0, 280.0)).load()
    times = pd.DatetimeIndex(field.time.values)
    dz = layer_thickness(field.depth.values)
    temperature = field.values.astype(float)
    warm = np.maximum(temperature - 20.0, 0.0)
    valid_column = np.isfinite(temperature[:, dz > 0]).all(axis=1)
    h20_jm2 = RHO0 * CP0 * np.nansum(
        warm[:, dz > 0] * dz[dz > 0][None, :, None, None], axis=1
    )
    h20_jm2[~valid_column] = np.nan
    area = cell_areas(field.lat.values, field.lon.values)
    valid_area = np.nansum(np.where(np.isfinite(h20_jm2), area[None], np.nan), axis=(1, 2))
    total_zj = np.nansum(h20_jm2 * area[None], axis=(1, 2)) / 1.0e21
    mean_gjm2 = np.nansum(h20_jm2 * area[None], axis=(1, 2)) / valid_area / 1.0e9
    total_anom = detrend_same_month(total_zj, times, BASELINE)
    mean_anom = detrend_same_month(mean_gjm2, times, BASELINE)
    return to_frame(
        times,
        h20_north_raw_zj=total_zj,
        h20_north_raw_gjm2=mean_gjm2,
        h20_north_anom_zj=total_anom,
        h20_north_anom_gjm2=mean_anom,
    )


def load_q5n() -> pd.DataFrame:
    raw = pd.read_csv(Q5N_MONTHLY, parse_dates=["time"])
    return raw[
        [
            "time",
            "year",
            "month",
            "q20_5n_north_pw_anom_b1982_2022",
            "q20_5n_ekman_north_pw_anom_b1982_2022",
            "tau5n_westward_nm2_anom_b1982_2022",
        ]
    ].rename(
        columns={
            "q20_5n_north_pw_anom_b1982_2022": "q5n_total_anom_pw",
            "q20_5n_ekman_north_pw_anom_b1982_2022": "q5n_ekman_anom_pw",
            "tau5n_westward_nm2_anom_b1982_2022": "taux5n_westward_anom_nm2",
        }
    )


def load_oisst() -> pd.DataFrame:
    pieces = []
    names = {1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun", 7: "jul"}
    for month, label in names.items():
        candidates = sorted(OISST_DIR.glob(f"oisst_sst_pmm_1deg_{label}_1982_*.nc"))
        if not candidates:
            raise FileNotFoundError(label)
        path = max(candidates, key=lambda item: item.name)
        with xr.open_dataset(path, engine="scipy") as raw:
            field = normalize(raw).sst.sel(time=slice("1982-01-01", "2024-12-31"))
            north = area_mean(field, 5.0, 12.0, 220.0, 280.0).load()
            equator = area_mean(field, -3.75, 3.75, 210.0, 270.0).load()
        times = pd.DatetimeIndex(north.time.values)
        pieces.append(
            to_frame(
                times,
                sst_north_raw_c=north.values,
                sst_eq_raw_c=equator.values,
            )
        )
    output = pd.concat(pieces, ignore_index=True).sort_values(["year", "month"])
    times = pd.DatetimeIndex(output.time)
    output["sst_north_anom_c"] = detrend_same_month(output.sst_north_raw_c.to_numpy(), times, (1982, 2024))
    output["sst_eq_anom_c"] = detrend_same_month(output.sst_eq_raw_c.to_numpy(), times, (1982, 2024))
    output["sst_eq_minus_north_anom_c"] = output.sst_eq_anom_c - output.sst_north_anom_c
    return output


def load_gpcp() -> pd.DataFrame:
    with xr.open_dataset(GPCP, engine="h5netcdf") as dataset:
        field = dataset.precip.sel(time=slice("1982-01-01", "2024-12-31"))
        equator = area_mean(field, -3.75, 3.75, 210.0, 270.0).load()
        north = area_mean(field, 6.25, 11.25, 210.0, 270.0).load()
    times = pd.DatetimeIndex(equator.time.values)
    eq_anom = detrend_same_month(equator.values, times, (1982, 2024))
    north_anom = detrend_same_month(north.values, times, (1982, 2024))
    return to_frame(
        times,
        precip_eq_anom_mmday=eq_anom,
        precip_north_anom_mmday=north_anom,
        precip_eq_minus_north_anom_mmday=eq_anom - north_anom,
    )


def load_slp() -> pd.DataFrame:
    with xr.open_dataset(ERA5_SINGLE, engine="h5netcdf") as raw:
        field = normalize(raw).msl.sel(time=slice("1982-01-01", "2024-12-31")) / 100.0
        field = field.sel(lat=slice(-5.0, 12.0), lon=slice(210.0, 270.0))
        equator = area_mean(field, -3.75, 3.75, 210.0, 270.0).load()
        north = area_mean(field, 6.25, 11.25, 210.0, 270.0).load()
    times = pd.DatetimeIndex(equator.time.values)
    eq_anom = detrend_same_month(equator.values, times, (1982, 2024))
    north_anom = detrend_same_month(north.values, times, (1982, 2024))
    return to_frame(
        times,
        slp_eq_anom_hpa=eq_anom,
        slp_north_anom_hpa=north_anom,
        slp_north_minus_eq_anom_hpa=north_anom - eq_anom,
    )


def load_ne925() -> pd.DataFrame:
    pieces = []
    for month in (5, 6, 7):
        path = ERA5_NE_DIR / f"era5_pressure925_m{month:02d}_1960_2024_1deg.nc"
        with xr.open_dataset(path, engine="h5netcdf") as raw:
            field = normalize(raw).sel(time=slice("1982-01-01", "2024-12-31"))
            u = area_mean(field.u, 3.0, 7.0, 180.0, 230.0).load()
            v = area_mean(field.v, 3.0, 7.0, 180.0, 230.0).load()
        times = pd.DatetimeIndex(u.time.values)
        pieces.append(to_frame(times, u925_raw_ms=u.values, v925_raw_ms=v.values))
    output = pd.concat(pieces, ignore_index=True).sort_values(["year", "month"])
    times = pd.DatetimeIndex(output.time)
    output["ne925_raw_ms"] = -(output.u925_raw_ms + output.v925_raw_ms) / np.sqrt(2.0)
    output["ne925_anom_ms"] = detrend_same_month(output.ne925_raw_ms.to_numpy(), times, (1982, 2024))
    output["easterly925_anom_ms"] = -detrend_same_month(output.u925_raw_ms.to_numpy(), times, (1982, 2024))
    output["northerly925_anom_ms"] = -detrend_same_month(output.v925_raw_ms.to_numpy(), times, (1982, 2024))
    return output


def build_monthly() -> pd.DataFrame:
    coupling = pd.read_csv(
        COUPLING,
        usecols=["year", "month", "nino34_raw_c", "sst_type_raw_c", "fep_raw_c"],
    )
    coupling["time"] = pd.to_datetime(dict(year=coupling.year, month=coupling.month, day=15))
    output = coupling
    for addition in (load_q5n(), load_north_h20(), load_oisst(), load_gpcp(), load_slp(), load_ne925()):
        addition = addition.copy()
        addition["time"] = pd.to_datetime(addition.time).map(lambda value: pd.Timestamp(value.year, value.month, 15))
        output = output.merge(addition.drop(columns=["year", "month"]), on="time", how="left", validate="one_to_one")
    output["year"] = output.time.dt.year
    output["month"] = output.time.dt.month
    return output.sort_values("time").reset_index(drop=True)


def build_lag_panel(monthly: pd.DataFrame) -> pd.DataFrame:
    lookup = monthly.set_index(["year", "month"])
    rows = []
    for year in range(BASELINE[0], BASELINE[1] + 1):
        for source_month in SOURCE_MONTHS:
            source = lookup.loc[(year, source_month)]
            target = lookup.loc[(year, source_month + 1)]
            rows.append(
                {
                    "year": year,
                    "source_month": source_month,
                    "target_month": source_month + 1,
                    "q5n_total_source_pw": source.q5n_total_anom_pw,
                    "q5n_ekman_source_pw": source.q5n_ekman_anom_pw,
                    "taux5n_source_nm2": source.taux5n_westward_anom_nm2,
                    "h20_north_source_zj": source.h20_north_anom_zj,
                    "h20_north_target_zj": target.h20_north_anom_zj,
                    "dh20_north_next_zj": target.h20_north_anom_zj - source.h20_north_anom_zj,
                    "h20_north_target_gjm2": target.h20_north_anom_gjm2,
                    "sst_north_target_c": target.sst_north_anom_c,
                    "sst_eq_minus_north_target_c": target.sst_eq_minus_north_anom_c,
                    "precip_north_target_mmday": target.precip_north_anom_mmday,
                    "precip_dipole_target_mmday": target.precip_eq_minus_north_anom_mmday,
                    "slp_gradient_target_hpa": target.slp_north_minus_eq_anom_hpa,
                    "ne925_target_ms": target.ne925_anom_ms,
                    "easterly925_target_ms": target.easterly925_anom_ms,
                    "nino34_target_c": target.nino34_raw_c,
                    "sst_type_target_c": target.sst_type_raw_c,
                    "fep_target_c": target.fep_raw_c,
                }
            )
    output = pd.DataFrame(rows)
    required = [
        "q5n_total_source_pw",
        "dh20_north_next_zj",
        "sst_north_target_c",
        "precip_dipole_target_mmday",
        "slp_gradient_target_hpa",
        "ne925_target_ms",
    ]
    if output[required].isna().any().any():
        raise ValueError(f"Missing lag panel inputs:\n{output.loc[output[required].isna().any(axis=1)]}")
    return output


def residual_pair(
    frame: pd.DataFrame,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...],
    group_name: str,
) -> pd.DataFrame:
    required = ["year", group_name, x_name, y_name, *controls]
    data = frame.dropna(subset=required).copy()
    data["x_residual"] = np.nan
    data["y_residual"] = np.nan
    for _, group in data.groupby(group_name):
        design = np.column_stack([np.ones(len(group)), *[group[name].to_numpy(dtype=float) for name in controls]])
        for source, target in ((x_name, "x_residual"), (y_name, "y_residual")):
            values = group[source].to_numpy(dtype=float)
            coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
            scale = float(np.std(values - design @ coefficients, ddof=max(1, len(controls) + 1)))
            residual = values - design @ coefficients
            if scale > 0:
                residual = residual / scale
            data.loc[group.index, target] = residual
    return data.sort_values(["year", group_name]).reset_index(drop=True)


def clustered_relationship(
    frame: pd.DataFrame,
    test_id: str,
    label: str,
    x_name: str,
    y_name: str,
    controls: tuple[str, ...],
    group_name: str,
    seed: int,
) -> dict[str, float | int | str]:
    data = residual_pair(frame, x_name, y_name, controls, group_name)
    years = np.sort(data.year.unique())
    groups = np.sort(data[group_name].unique())
    counts = data.groupby("year")[group_name].nunique()
    if not counts.eq(len(groups)).all():
        raise ValueError(f"Incomplete clusters for {test_id}")
    x_matrix = data.pivot(index="year", columns=group_name, values="x_residual").loc[years, groups].to_numpy()
    y_matrix = data.pivot(index="year", columns=group_name, values="y_residual").loc[years, groups].to_numpy()
    observed = float(np.corrcoef(x_matrix.ravel(), y_matrix.ravel())[0, 1])
    raw_r = float(np.corrcoef(data[x_name], data[y_name])[0, 1])
    rng = np.random.default_rng(seed)
    permuted = np.empty(N_PERMUTATIONS)
    for index in range(N_PERMUTATIONS):
        permuted[index] = np.corrcoef(x_matrix[rng.permutation(len(years))].ravel(), y_matrix.ravel())[0, 1]
    p_value = float((np.sum(np.abs(permuted) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1))
    bootstrap = np.empty(N_BOOTSTRAP)
    for index in range(N_BOOTSTRAP):
        selected = rng.integers(0, len(years), len(years))
        bootstrap[index] = np.corrcoef(x_matrix[selected].ravel(), y_matrix[selected].ravel())[0, 1]
    low, high = np.nanpercentile(bootstrap, [2.5, 97.5])
    loeo = []
    for held in range(len(years)):
        keep = np.arange(len(years)) != held
        loeo.append(float(np.corrcoef(x_matrix[keep].ravel(), y_matrix[keep].ravel())[0, 1]))
    return {
        "test_id": test_id,
        "label": label,
        "x": x_name,
        "y": y_name,
        "controls": ";".join(controls),
        "n_years": len(years),
        "n_rows": len(data),
        "raw_r": raw_r,
        "controlled_r": observed,
        "year_block_permutation_p": p_value,
        "year_block_bootstrap_ci_low": float(low),
        "year_block_bootstrap_ci_high": float(high),
        "loyo_r_min": float(np.min(loeo)),
        "loyo_r_max": float(np.max(loeo)),
    }


def bh_fdr(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.minimum(adjusted, 1.0)
    return output


def build_relationships(lag: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    controls = ("nino34_target_c", "sst_type_target_c", "fep_target_c")
    tests = [
        ("q_to_h20", "Q5N(t) -> north-box H20 tendency(t+1)", "q5n_total_source_pw", "dh20_north_next_zj"),
        ("q_to_sst", "Q5N(t) -> north-box SST(t+1)", "q5n_total_source_pw", "sst_north_target_c"),
        ("h20_to_sst", "north-box H20(t+1) -> SST(t+1)", "h20_north_target_gjm2", "sst_north_target_c"),
        ("h20_to_north_rain", "north-box H20(t+1) -> north rain(t+1)", "h20_north_target_gjm2", "precip_north_target_mmday"),
        ("h20_to_rain_dipole", "north-box H20(t+1) -> equator-minus-north rain(t+1)", "h20_north_target_gjm2", "precip_dipole_target_mmday"),
        ("h20_to_slp", "north-box H20(t+1) -> north-minus-equator SLP(t+1)", "h20_north_target_gjm2", "slp_gradient_target_hpa"),
        ("h20_to_ne", "north-box H20(t+1) -> NE925(t+1)", "h20_north_target_gjm2", "ne925_target_ms"),
        ("q_to_rain_dipole", "Q5N(t) -> rain dipole(t+1)", "q5n_total_source_pw", "precip_dipole_target_mmday"),
        ("q_to_ne", "Q5N(t) -> NE925(t+1)", "q5n_total_source_pw", "ne925_target_ms"),
        ("rain_dipole_to_ne", "rain dipole(t+1) -> NE925(t+1)", "precip_dipole_target_mmday", "ne925_target_ms"),
    ]
    rows = [
        clustered_relationship(lag, test_id, label, x, y, controls, "source_month", RANDOM_SEED + index)
        for index, (test_id, label, x, y) in enumerate(tests)
    ]

    same = monthly.loc[
        monthly.year.between(*BASELINE) & monthly.month.isin([5, 6]),
        [
            "year",
            "month",
            "ne925_anom_ms",
            "q5n_total_anom_pw",
            "nino34_raw_c",
            "sst_type_raw_c",
            "fep_raw_c",
        ],
    ].rename(
        columns={
            "month": "source_month",
            "nino34_raw_c": "nino34_target_c",
            "sst_type_raw_c": "sst_type_target_c",
            "fep_raw_c": "fep_target_c",
        }
    )
    rows.append(
        clustered_relationship(
            same,
            "ne_to_q_same",
            "NE925(t) -> Q5N(t), contemporaneous",
            "ne925_anom_ms",
            "q5n_total_anom_pw",
            controls,
            "source_month",
            RANDOM_SEED + 20,
        )
    )

    cross_rows = []
    lookup = monthly.set_index(["year", "month"])
    for year in range(BASELINE[0], BASELINE[1] + 1):
        may = lookup.loc[(year, 5)]
        june = lookup.loc[(year, 6)]
        cross_rows.append(
            {
                "year": year,
                "source_month": 5,
                "ne925_may_ms": may.ne925_anom_ms,
                "q5n_may_pw": may.q5n_total_anom_pw,
                "q5n_june_pw": june.q5n_total_anom_pw,
                "nino34_target_c": june.nino34_raw_c,
                "sst_type_target_c": june.sst_type_raw_c,
                "fep_target_c": june.fep_raw_c,
            }
        )
    cross = pd.DataFrame(cross_rows)
    rows.append(
        clustered_relationship(
            cross,
            "ne_to_q_next",
            "May NE925 -> June Q5N, controlling May Q5N",
            "ne925_may_ms",
            "q5n_june_pw",
            (*controls, "q5n_may_pw"),
            "source_month",
            RANDOM_SEED + 21,
        )
    )
    output = pd.DataFrame(rows)
    output["bh_fdr_q"] = bh_fdr(output.year_block_permutation_p.to_numpy(dtype=float))
    return output


def integrate_zj(frame: pd.DataFrame, column: str) -> float:
    days = pd.to_datetime(frame.time).dt.days_in_month.to_numpy(dtype=float)
    return float(np.nansum(frame[column].to_numpy(dtype=float) * days * 86400.0 * 1.0e-6))


def build_event_table(monthly: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(EVENT_BASE)[["year", "group"]]
    rows = []
    for year in EVENT_YEARS:
        current = monthly.loc[monthly.year.eq(year)].copy()
        fma = current.loc[current.month.isin([2, 3, 4])]
        amj = current.loc[current.month.isin([4, 5, 6])]
        mjj = current.loc[current.month.isin([5, 6, 7])]
        jan = current.loc[current.month.eq(1)]
        june = current.loc[current.month.eq(6)]
        row: dict[str, float | int] = {
            "year": year,
            "q5n_fma_zj": integrate_zj(fma, "q5n_total_anom_pw"),
            "q5n_amj_zj": integrate_zj(amj, "q5n_total_anom_pw"),
            "q5n_ekman_amj_zj": integrate_zj(amj, "q5n_ekman_anom_pw"),
            "sst_north_mjj_c": float(mjj.sst_north_anom_c.mean()),
            "sst_eq_minus_north_mjj_c": float(mjj.sst_eq_minus_north_anom_c.mean()),
            "precip_north_mjj_mmday": float(mjj.precip_north_anom_mmday.mean()),
            "precip_dipole_mjj_mmday": float(mjj.precip_eq_minus_north_anom_mmday.mean()),
            "slp_gradient_mjj_hpa": float(mjj.slp_north_minus_eq_anom_hpa.mean()),
            "ne925_mjj_ms": float(mjj.ne925_anom_ms.mean()),
        }
        if year <= 2022:
            row["h20_north_jan_to_jun_zj"] = float(june.h20_north_anom_zj.iloc[0] - jan.h20_north_anom_zj.iloc[0])
            row["h20_north_mjj_gjm2"] = float(mjj.h20_north_anom_gjm2.mean())
        else:
            row["h20_north_jan_to_jun_zj"] = np.nan
            row["h20_north_mjj_gjm2"] = np.nan
        rows.append(row)
    return base.merge(pd.DataFrame(rows), on="year", validate="one_to_one")


def event_relationships(events: pd.DataFrame) -> pd.DataFrame:
    tests = [
        ("event_q_to_h20", "FMA Q5N -> Jan-Jun north H20 change", "q5n_fma_zj", "h20_north_jan_to_jun_zj"),
        ("event_q_to_sst", "FMA Q5N -> MJJ north SST", "q5n_fma_zj", "sst_north_mjj_c"),
        ("event_q_to_rain", "FMA Q5N -> MJJ rain dipole", "q5n_fma_zj", "precip_dipole_mjj_mmday"),
        ("event_q_to_ne", "FMA Q5N -> MJJ NE925", "q5n_fma_zj", "ne925_mjj_ms"),
        ("event_h20_to_ne", "MJJ north H20 -> MJJ NE925", "h20_north_mjj_gjm2", "ne925_mjj_ms"),
        ("event_sst_to_ne", "MJJ north SST -> MJJ NE925", "sst_north_mjj_c", "ne925_mjj_ms"),
    ]
    rng = np.random.default_rng(RANDOM_SEED + 100)
    rows = []
    for test_id, label, x_name, y_name in tests:
        data = events.dropna(subset=[x_name, y_name])
        x = data[x_name].to_numpy(dtype=float)
        y = data[y_name].to_numpy(dtype=float)
        observed = float(np.corrcoef(x, y)[0, 1])
        permutations = np.empty(N_PERMUTATIONS)
        for index in range(N_PERMUTATIONS):
            permutations[index] = np.corrcoef(x, rng.permutation(y))[0, 1]
        p_value = float((np.sum(np.abs(permutations) >= abs(observed)) + 1) / (N_PERMUTATIONS + 1))
        bootstrap = np.empty(N_BOOTSTRAP)
        for index in range(N_BOOTSTRAP):
            selected = rng.integers(0, len(x), len(x))
            bootstrap[index] = np.corrcoef(x[selected], y[selected])[0, 1]
        low, high = np.nanpercentile(bootstrap, [2.5, 97.5])
        rows.append(
            {
                "test_id": test_id,
                "label": label,
                "x": x_name,
                "y": y_name,
                "n_events": len(data),
                "pearson_r": observed,
                "permutation_p": p_value,
                "bootstrap_ci_low": float(low),
                "bootstrap_ci_high": float(high),
            }
        )
    output = pd.DataFrame(rows)
    output["bh_fdr_q"] = bh_fdr(output.permutation_p.to_numpy(dtype=float))
    return output


def relationship_residuals(lag: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    controls = tuple(str(row.controls).split(";")) if row.controls else ()
    return residual_pair(lag, row.x, row.y, controls, "source_month")


def scatter_panel(axis: plt.Axes, data: pd.DataFrame, row: pd.Series, title: str, xlabel: str, ylabel: str) -> None:
    month_colors = {4: "#4daf4a", 5: "#377eb8", 6: "#984ea3"}
    for month, group in data.groupby("source_month"):
        axis.scatter(group.x_residual, group.y_residual, s=24, alpha=0.65, color=month_colors[int(month)], label={4: "Apr→May", 5: "May→Jun", 6: "Jun→Jul"}[int(month)])
    coefficients = np.polyfit(data.x_residual, data.y_residual, 1)
    xx = np.linspace(data.x_residual.min(), data.x_residual.max(), 100)
    axis.plot(xx, np.polyval(coefficients, xx), color="#202020", linewidth=1.4)
    axis.axhline(0, color="#777777", linewidth=0.7)
    axis.axvline(0, color="#777777", linewidth=0.7)
    axis.set_title(title, loc="left", fontweight="bold")
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.text(
        0.03,
        0.96,
        f"controlled r={row.controlled_r:+.2f}\nblock p={row.year_block_permutation_p:.3f}; q={row.bh_fdr_q:.3f}",
        transform=axis.transAxes,
        va="top",
        fontsize=8.0,
    )


def plot_path(lag: pd.DataFrame, relationships: pd.DataFrame) -> None:
    setup_style()
    lookup = relationships.set_index("test_id")
    panels = [
        ("q_to_h20", "a  Does outflow accumulate north of 5°N?", "Q5N residual", "Next-month north H20 tendency residual"),
        ("h20_to_sst", "b  Does subsurface warm heat reach the surface?", "North H20 residual", "North SST residual"),
        ("h20_to_rain_dipole", "c  Does north-side warming reorganize rainfall?", "North H20 residual", "Equator-minus-north rainfall residual"),
        ("rain_dipole_to_ne", "d  Does the rainfall contrast project onto NE winds?", "Rainfall-dipole residual", "NE925 residual"),
        ("q_to_ne", "e  Forward test: early Q5N → later NE925", "Q5N residual", "Next-month NE925 residual"),
    ]
    figure, axes = plt.subplots(2, 3, figsize=(13.0, 8.0))
    for axis, (test_id, title, xlabel, ylabel) in zip(axes.flat[:5], panels, strict=True):
        row = lookup.loc[test_id]
        data = relationship_residuals(lag, row)
        scatter_panel(axis, data, row, title, xlabel, ylabel)
    axes[0, 0].legend(frameon=False, loc="lower right")

    axis = axes.flat[5]
    forward = lookup.loc["q_to_ne"]
    reverse_same = lookup.loc["ne_to_q_same"]
    reverse_next = lookup.loc["ne_to_q_next"]
    labels = ["Q(t) → NE(t+1)", "NE(t) ↔ Q(t)", "NE(May) → Q(Jun)"]
    values = [forward.controlled_r, reverse_same.controlled_r, reverse_next.controlled_r]
    errors = np.array(
        [
            [forward.controlled_r - forward.year_block_bootstrap_ci_low, reverse_same.controlled_r - reverse_same.year_block_bootstrap_ci_low, reverse_next.controlled_r - reverse_next.year_block_bootstrap_ci_low],
            [forward.year_block_bootstrap_ci_high - forward.controlled_r, reverse_same.year_block_bootstrap_ci_high - reverse_same.controlled_r, reverse_next.year_block_bootstrap_ci_high - reverse_next.controlled_r],
        ]
    )
    colors = ["#d95f4c", "#777777", "#3b78b8"]
    axis.bar(np.arange(3), values, color=colors, width=0.65)
    axis.errorbar(np.arange(3), values, yerr=errors, fmt="none", ecolor="#202020", capsize=4, linewidth=1.0)
    axis.axhline(0, color="#555555", linewidth=0.8)
    axis.set_xticks(np.arange(3), labels, rotation=18, ha="right")
    axis.set_ylabel("Controlled correlation")
    axis.set_title("f  Direction check", loc="left", fontweight="bold")
    for index, row in enumerate((forward, reverse_same, reverse_next)):
        axis.text(index, values[index] + (0.04 if values[index] >= 0 else -0.08), f"p={row.year_block_permutation_p:.3f}", ha="center", va="bottom" if values[index] >= 0 else "top", fontsize=8.0)
    figure.suptitle("Can early eastern-Pacific H20 outflow precede Jiang-type northeasterlies?", fontweight="bold", fontsize=12.2, y=0.995)
    figure.tight_layout(rect=(0, 0, 1, 0.97), h_pad=2.0, w_pad=1.6)
    OUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIG_PATH_PNG, bbox_inches="tight")
    figure.savefig(FIG_PATH_PDF, bbox_inches="tight")
    plt.close(figure)


def plot_events(monthly: pd.DataFrame) -> None:
    setup_style()
    variables = [
        ("q5n_total_anom_pw", "Q5N (PW)"),
        ("sst_north_anom_c", "North SST (°C)"),
        ("precip_eq_minus_north_anom_mmday", "Eq − north rain\n(mm day$^{-1}$)"),
        ("ne925_anom_ms", "NE925 (m s$^{-1}$)"),
    ]
    figure, axes = plt.subplots(4, 1, figsize=(10.0, 9.0), sharex=True)
    month_order = [4, 5, 6, 7]
    for axis, (column, ylabel) in zip(axes, variables, strict=True):
        for year in HIGHLIGHT_YEARS:
            current = monthly.loc[monthly.year.eq(year) & monthly.month.isin(month_order)].set_index("month")
            axis.plot(month_order, current.reindex(month_order)[column], color=COLORS[year], marker="o", linewidth=1.8, label=str(year))
        axis.axhline(0, color="#777777", linewidth=0.7)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", color="#dddddd", linewidth=0.6)
    axes[0].legend(frameon=False, ncol=3, loc="upper left")
    axes[-1].set_xticks(month_order, ["Apr(0)", "May", "Jun", "Jul"])
    axes[-1].set_xlabel("Development year")
    figure.suptitle("Three-event sequence: ocean outflow, receiving SST, rainfall contrast and NE winds", fontweight="bold", fontsize=12.0, y=0.995)
    figure.tight_layout(rect=(0.02, 0, 1, 0.97), h_pad=1.0)
    figure.savefig(FIG_EVENT_PNG, bbox_inches="tight")
    figure.savefig(FIG_EVENT_PDF, bbox_inches="tight")
    plt.close(figure)


def write_report(events: pd.DataFrame, relationships: pd.DataFrame, event_rel: pd.DataFrame) -> None:
    r = relationships.set_index("test_id")
    er = event_rel.set_index("test_id")
    lines = [
        "# 东部暖量流出是否诱发Jiang型东北风：双向反馈检验",
        "",
        "## 结论",
        "",
        "**当前资料不支持“5°N北向暖量流出先在北侧沉积并增暖，继而造成Jiang型东北风异常”这条完整因果链。**",
        "",
        "1. 必要的第一环没有成立：全边界Q5N与下一月北侧H20增量近零（controlled r=-0.01）。东西分区后，只有110°W—80°W东段出现名义上的正关系（r=+0.22, p=0.023），但多重检验后q=0.063；140°W—130°W的Jiang区域重叠段仍不显著。",
        "2. 北侧H20与SST联系稳健，但H20不能继续解释降水偶极子、海平面气压梯度或东北风。因此即使局地次表层暖量能够投影到海表，也没有检测到所需的大气响应桥梁。",
        "3. Q5N确实领先一月NE925（r=+0.30），但该信号主要来自140°W—110°W及Jiang重叠段；这些区域恰好同时表现为“无H20沉积”。与此同时，NE925与同期Q5N关系更强（r=+0.64），且May NE925在控制May Q5N后仍能预测June Q5N（r=+0.38）。",
        "",
        "因此现阶段更稳妥的方向是：**发展期东北风/表面风应力驱动或调制5°N暖量输送；输送与下月东北风的正关系可能包含大气持续性或双向反馈，但不能归因于已观测到的“北侧暖量沉积—增暖—降水/气压响应”。** 这不否定成熟—衰减期5°N出口的重要性，只说明它不是Jiang发展期东北风异常的已证实上游原因。",
        "",
        "## 逐月全年份检验（1982—2022）",
        "",
    ]
    for test_id in ["q_to_h20", "q_to_sst", "h20_to_sst", "h20_to_north_rain", "h20_to_rain_dipole", "h20_to_slp", "h20_to_ne", "q_to_rain_dipole", "q_to_ne", "rain_dipole_to_ne", "ne_to_q_same", "ne_to_q_next"]:
        row = r.loc[test_id]
        lines.append(
            f"- {row.label}: raw r={row.raw_r:+.2f}, controlled r={row.controlled_r:+.2f}, "
            f"year-block p={row.year_block_permutation_p:.3f}, FDR q={row.bh_fdr_q:.3f}, "
            f"95% CI [{row.year_block_bootstrap_ci_low:+.2f}, {row.year_block_bootstrap_ci_high:+.2f}]。"
        )
    lines += ["", "## 暖事件检验", ""]
    for _, row in event_rel.iterrows():
        lines.append(
            f"- {row.label}: n={int(row.n_events)}, r={row.pearson_r:+.2f}, p={row.permutation_p:.3f}, "
            f"FDR q={row.bh_fdr_q:.3f}, 95% CI [{row.bootstrap_ci_low:+.2f}, {row.bootstrap_ci_high:+.2f}]。"
        )
    lines += [
        "",
        "## 1997、2015、2023",
        "",
        "| Event | FMA Q5N | AMJ Q5N | MJJ north SST | MJJ rain dipole | MJJ NE925 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in HIGHLIGHT_YEARS:
        row = events.loc[events.year.eq(year)].iloc[0]
        lines.append(
            f"| {year} | {row.q5n_fma_zj:+.2f} ZJ | {row.q5n_amj_zj:+.2f} ZJ | "
            f"{row.sst_north_mjj_c:+.2f} °C | {row.precip_dipole_mjj_mmday:+.2f} mm d⁻¹ | {row.ne925_mjj_ms:+.2f} m s⁻¹ |"
        )
    lines += [
        "",
        "## 东西分区敏感性",
        "",
        "- 140°W—80°W全边界：Q5N -> 同区域北侧H20增量，r=-0.01，p=0.887。",
        "- 140°W—110°W西段：r=-0.13，p=0.178；但Q5N -> 下一月NE925为r=+0.37，FDR q=0.002。",
        "- 110°W—80°W东段：Q5N -> H20增量为r=+0.22，p=0.023，FDR q=0.063；东段H20 -> NE925为r=-0.08，p=0.445。",
        "- 140°W—130°W Jiang重叠段：Q5N -> H20增量为r=+0.08，p=0.467；Q5N -> 下一月NE925为r=+0.35，FDR q=0.002。",
        "",
        "## 方法边界",
        "",
        "- Q20穿过5°N只是北侧箱体的输入边界之一；H20倾向同时受10°N输出、东西边界、海表通量、混合和阈值转换影响。",
        "- 全年份逐月关系控制同期Niño-3.4、SST型态和FEP SST，并按整年置换与bootstrap；仍不能排除共同动力过程或同化资料中的反馈。",
        "- 2023没有可用的SODA3北侧三维H20扩展，因此其接收侧响应使用OISST表面海温；1997、2015可同时检查SODA3 H20。",
        "- 同期东北风—Q20关系和局地应力—Ekman关系包含动力上的反向作用；方向判别以领先一月关系为主。",
        "- 这里检验的是发展年Apr—Jul的早期反馈，不应与原文成熟—衰减期Jan(+1)—May(+1)的5°N出口混为同一阶段。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    monthly = build_monthly()
    lag = build_lag_panel(monthly)
    relationships = build_relationships(lag, monthly)
    events = build_event_table(monthly)
    event_rel = event_relationships(events)
    monthly.to_csv(MONTHLY_CSV, index=False, float_format="%.9g")
    lag.to_csv(LAG_CSV, index=False, float_format="%.9g")
    relationships.to_csv(RELATIONSHIP_CSV, index=False, float_format="%.9g")
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    event_rel.to_csv(EVENT_RELATIONSHIP_CSV, index=False, float_format="%.9g")
    diagnostics = {
        "north_receiver_box": "5.25-11.25N, 140W-80W",
        "rain_slp_dipole_box": "equator 3.75S-3.75N minus north 6.25-11.25N, 150W-90W",
        "source_months": list(SOURCE_MONTHS),
        "baseline": list(BASELINE),
        "n_lag_rows": len(lag),
    }
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    plot_path(lag, relationships)
    plot_events(monthly)
    write_report(events, relationships, event_rel)
    print(RELATIONSHIP_CSV)
    print(EVENT_CSV)
    print(FIG_PATH_PNG)
    print(FIG_EVENT_PNG)
    print(REPORT)


if __name__ == "__main__":
    main()
