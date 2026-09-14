#!/usr/bin/env python3
"""Spatial sensitivity of the necessary Q5N -> north-receiver H20 link.

The full 140W--80W boundary can conceal zonally localized deposition.  This
script therefore pairs Q20 across 5N with the next-month H20 tendency in the
same longitude range for four boxes: 140W--80W, 140W--110W, 110W--80W, and
140W--130W (the overlap with the eastern edge of the Jiang wind box).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

from analyze_h20_outflow_ne_feedback import (
    BASELINE,
    CP0,
    RANDOM_SEED,
    RHO0,
    bh_fdr,
    cell_areas,
    clustered_relationship,
    detrend_same_month,
    layer_thickness,
    setup_style,
)


ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / "data/raw/soda3/soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
PROCESS = ROOT / "data/raw/soda3/soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
NORTH = ROOT / "data/raw/soda3/soda3.15.2_north_receiver_temp_jan_jul_1980_2022.nc"
MONTHLY = ROOT / "data/derived/research_2026/h20_outflow_ne_feedback_monthly_1982_2024.csv"
OUT = ROOT / "data/derived/research_2026/h20_outflow_ne_feedback_spatial_sensitivity.csv"
FIG_DIR = ROOT / "outputs/research_2026/h20_outflow_ne_feedback"
FIG_PNG = FIG_DIR / "h20_outflow_ne_spatial_sensitivity.png"
FIG_PDF = FIG_DIR / "h20_outflow_ne_spatial_sensitivity.pdf"

SEGMENTS = {
    "full_140w_80w": (220.0, 280.0),
    "west_140w_110w": (220.0, 250.0),
    "east_110w_80w": (250.0, 280.0),
    "jiang_overlap_140w_130w": (220.0, 230.0),
}


def correlation_bars(
    axis: plt.Axes,
    result: pd.DataFrame,
    ids: list[str],
    labels: list[str],
    colors: list[str],
    title: str,
) -> None:
    table = result.set_index("test_id").loc[ids]
    values = table.controlled_r.to_numpy(dtype=float)
    error = np.vstack(
        [
            values - table.year_block_bootstrap_ci_low.to_numpy(dtype=float),
            table.year_block_bootstrap_ci_high.to_numpy(dtype=float) - values,
        ]
    )
    x = np.arange(len(ids))
    axis.bar(x, values, color=colors, width=0.66)
    axis.errorbar(x, values, yerr=error, fmt="none", ecolor="#222222", capsize=4, linewidth=1.0)
    axis.axhline(0, color="#666666", linewidth=0.8)
    axis.set_xticks(x, labels)
    axis.set_ylim(-0.55, 0.75)
    axis.set_ylabel("Controlled correlation")
    axis.set_title(title, loc="left", fontweight="bold")
    for index, row in enumerate(table.itertuples()):
        y = values[index] + (0.08 if values[index] >= 0 else -0.11)
        axis.text(index, y, f"q={row.bh_fdr_q:.3f}", ha="center", fontsize=8.0)


def plot_result(result: pd.DataFrame) -> None:
    setup_style()
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.4))
    correlation_bars(
        axes[0],
        result,
        ["full_140w_80w", "west_140w_110w", "east_110w_80w", "jiang_overlap_140w_130w"],
        ["Full", "West", "East", "Jiang\noverlap"],
        ["#777777", "#4c78a8", "#f28e2b", "#59a14f"],
        "a  Q5N → matching north-side H20 tendency",
    )
    correlation_bars(
        axes[1],
        result,
        ["west_q_to_ne", "east_q_to_ne", "overlap_q_to_ne"],
        ["West", "East", "Jiang\noverlap"],
        ["#4c78a8", "#f28e2b", "#59a14f"],
        "b  Regional Q5N(t) → NE925(t+1)",
    )
    correlation_bars(
        axes[2],
        result,
        ["east_h20_to_sst", "east_h20_to_rain", "east_h20_to_slp", "east_h20_to_ne"],
        ["SST", "Rain", "SLP", "NE925"],
        ["#e15759", "#76b7b2", "#b07aa1", "#59a14f"],
        "c  East-side H20 → surface/atmosphere",
    )
    figure.suptitle(
        "Spatial test of the proposed outflow → warming → northeasterly pathway",
        fontsize=12.2,
        fontweight="bold",
        y=0.995,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.96), w_pad=1.7)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIG_PNG, bbox_inches="tight")
    figure.savefig(FIG_PDF, bbox_inches="tight")
    plt.close(figure)


def frame(time: pd.DatetimeIndex, name: str, values: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": time,
            "year": time.year,
            "month": time.month,
            name: np.asarray(values, dtype=float),
        }
    )


def derive_segment_q() -> pd.DataFrame:
    with xr.open_dataset(TEMP, engine="h5netcdf") as temp_ds, xr.open_dataset(
        PROCESS, engine="h5netcdf"
    ) as process_ds:
        temp = temp_ds.temp.load()
        v = process_ds.v.sel(u_lat=5.0).load()
    times = pd.DatetimeIndex(temp.time.values)
    lon = temp.lon.values.astype(float)
    depth = temp.depth.values.astype(float)
    latitude_index = int(np.argmin(np.abs(temp.lat.values - 4.75)))
    boundary_temp = temp.values[:, :, latitude_index, :].astype(float)
    boundary_v = 0.5 * (v.values[:, :, :-1] + v.values[:, :, 1:])
    dz = layer_thickness(depth)[None, :, None]
    dlon = float(np.median(np.diff(lon)))
    width = 6_371_000.0 * np.cos(np.deg2rad(5.0)) * np.deg2rad(dlon)
    output = None
    for name, (lon0, lon1) in SEGMENTS.items():
        mask = (lon >= lon0) & (lon <= lon1)
        current_temp = boundary_temp[:, :, mask]
        current_v = boundary_v[:, :, mask]
        valid = np.isfinite(current_temp) & np.isfinite(current_v)
        warm = np.where(valid, np.maximum(current_temp - 20.0, 0.0), np.nan)
        raw = RHO0 * CP0 * np.nansum(current_v * warm * dz * width, axis=(1, 2)) / 1.0e15
        anomaly = detrend_same_month(raw, times, BASELINE)
        addition = frame(times, f"q_{name}_pw", anomaly)
        output = addition if output is None else output.merge(addition, on=["time", "year", "month"])
    assert output is not None
    return output


def derive_segment_h20() -> pd.DataFrame:
    with xr.open_dataset(NORTH, engine="h5netcdf") as dataset:
        temp = dataset.temp.sel(lat=slice(5.25, 11.25)).load()
    times = pd.DatetimeIndex(temp.time.values)
    depth = temp.depth.values.astype(float)
    dz = layer_thickness(depth)[None, :, None, None]
    output = None
    for name, (lon0, lon1) in SEGMENTS.items():
        field = temp.sel(lon=slice(lon0, lon1))
        temperature = field.values.astype(float)
        warm = np.maximum(temperature - 20.0, 0.0)
        valid_column = np.isfinite(temperature[:, dz[0, :, 0, 0] > 0]).all(axis=1)
        h20_jm2 = RHO0 * CP0 * np.nansum(warm * dz, axis=1)
        h20_jm2[~valid_column] = np.nan
        area = cell_areas(field.lat.values, field.lon.values)
        total_zj = np.nansum(h20_jm2 * area[None], axis=(1, 2)) / 1.0e21
        anomaly = detrend_same_month(total_zj, times, BASELINE)
        addition = frame(times, f"h20_{name}_zj", anomaly)
        output = addition if output is None else output.merge(addition, on=["time", "year", "month"])
    assert output is not None
    return output


def build_lag(q: pd.DataFrame, h20: pd.DataFrame) -> pd.DataFrame:
    controls = pd.read_csv(
        MONTHLY,
        parse_dates=["time"],
        usecols=[
            "time",
            "year",
            "month",
            "nino34_raw_c",
            "sst_type_raw_c",
            "fep_raw_c",
            "sst_north_anom_c",
            "precip_eq_minus_north_anom_mmday",
            "slp_north_minus_eq_anom_hpa",
            "ne925_anom_ms",
        ],
    )
    monthly = controls.merge(q, on=["time", "year", "month"], how="left").merge(
        h20, on=["time", "year", "month"], how="left"
    )
    lookup = monthly.set_index(["year", "month"])
    rows = []
    for year in range(BASELINE[0], BASELINE[1] + 1):
        for source_month in (4, 5, 6):
            source = lookup.loc[(year, source_month)]
            target = lookup.loc[(year, source_month + 1)]
            row = {
                "year": year,
                "source_month": source_month,
                "nino34_target_c": target.nino34_raw_c,
                "sst_type_target_c": target.sst_type_raw_c,
                "fep_target_c": target.fep_raw_c,
                "sst_north_target_c": target.sst_north_anom_c,
                "precip_dipole_target_mmday": target.precip_eq_minus_north_anom_mmday,
                "slp_gradient_target_hpa": target.slp_north_minus_eq_anom_hpa,
                "ne925_target_ms": target.ne925_anom_ms,
            }
            for name in SEGMENTS:
                row[f"q_{name}_source_pw"] = source[f"q_{name}_pw"]
                row[f"dh20_{name}_next_zj"] = target[f"h20_{name}_zj"] - source[f"h20_{name}_zj"]
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    q = derive_segment_q()
    h20 = derive_segment_h20()
    lag = build_lag(q, h20)
    controls = ("nino34_target_c", "sst_type_target_c", "fep_target_c")
    rows = []
    for index, (name, bounds) in enumerate(SEGMENTS.items()):
        rows.append(
            clustered_relationship(
                lag,
                name,
                f"Q5N {bounds[0]:.0f}-{bounds[1]:.0f}E -> matching north H20 tendency",
                f"q_{name}_source_pw",
                f"dh20_{name}_next_zj",
                controls,
                "source_month",
                RANDOM_SEED + 300 + index,
            )
        )
    # The eastern half is the only segment with even a nominally positive
    # Q->H20 tendency relation.  Test the remainder of the proposed mediator
    # chain explicitly rather than treating that first link as sufficient.
    east_h20 = "h20_east_110w_80w_target_zj"
    lag[east_h20] = [
        h20.set_index(["year", "month"]).loc[(int(year), int(month + 1)), "h20_east_110w_80w_zj"]
        for year, month in zip(lag.year, lag.source_month, strict=True)
    ]
    east_tests = [
        ("east_h20_to_sst", "East receiver H20 -> north-box SST", east_h20, "sst_north_target_c"),
        ("east_h20_to_rain", "East receiver H20 -> rainfall dipole", east_h20, "precip_dipole_target_mmday"),
        ("east_h20_to_slp", "East receiver H20 -> SLP gradient", east_h20, "slp_gradient_target_hpa"),
        ("east_h20_to_ne", "East receiver H20 -> Jiang NE925", east_h20, "ne925_target_ms"),
        ("east_q_to_ne", "East-segment Q5N(t) -> Jiang NE925(t+1)", "q_east_110w_80w_source_pw", "ne925_target_ms"),
        ("west_q_to_ne", "West-segment Q5N(t) -> Jiang NE925(t+1)", "q_west_140w_110w_source_pw", "ne925_target_ms"),
        ("overlap_q_to_ne", "Jiang-overlap Q5N(t) -> Jiang NE925(t+1)", "q_jiang_overlap_140w_130w_source_pw", "ne925_target_ms"),
    ]
    for offset, (test_id, label, x_name, y_name) in enumerate(east_tests):
        rows.append(
            clustered_relationship(
                lag,
                test_id,
                label,
                x_name,
                y_name,
                controls,
                "source_month",
                RANDOM_SEED + 320 + offset,
            )
        )
    result = pd.DataFrame(rows)
    result["bh_fdr_q"] = bh_fdr(result.year_block_permutation_p.to_numpy(dtype=float))

    reference = pd.read_csv(
        ROOT / "data/derived/research_2026/enso_1997_2015_2023_warm_heat_fate_monthly.csv",
        parse_dates=["time"],
        usecols=["time", "q20_5n_north_pw_anom_b1982_2022"],
    )
    validation = q.merge(reference, on="time").dropna()
    result["full_q_validation_r"] = np.corrcoef(
        validation.q_full_140w_80w_pw,
        validation.q20_5n_north_pw_anom_b1982_2022,
    )[0, 1]
    result["full_q_validation_max_abs_pw"] = np.max(
        np.abs(
            validation.q_full_140w_80w_pw
            - validation.q20_5n_north_pw_anom_b1982_2022
        )
    )
    result.to_csv(OUT, index=False, float_format="%.9g")
    plot_result(result)
    print(result.to_string(index=False))
    print(OUT)
    print(FIG_PNG)


if __name__ == "__main__":
    main()
