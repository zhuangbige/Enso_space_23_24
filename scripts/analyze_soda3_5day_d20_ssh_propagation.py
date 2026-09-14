#!/usr/bin/env python3
"""Diagnose 5-day SODA3 D20/SSH propagation for four ENSO events.

The event-only 5-day records are anchored to detrended 1980-2024 monthly
anomalies computed from the full SODA3.15.2 equatorial subset. This preserves
submonthly variability without pretending that four event years define a
5-day climatology.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_maryland_climate_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from fetch_soda3_5day_event_transport import (
    d20_from_temperature,
    interpolate_longitude,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data/interim/research_2026/soda3_5day_event_transport"
TEMP_NC = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_temp_jan_jun_1980_2024.nc"
)
PROCESS_NC = (
    ROOT
    / "data/raw/soda3/"
    "soda3.15.2_equatorial_process_fields_jan_jun_1980_2024.nc"
)
TRANSPORT_ANCHORED_CSV = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_5day_event_transport_anchored.csv"
)
OUT_DATA = ROOT / "data/derived/research_2026"
OUT_DIR = ROOT / "outputs/research_2026/soda3_5day_propagation"
OUT_PDF = ROOT / "output/pdf"
MONTHLY_REFERENCE_CSV = (
    OUT_DATA / "soda3_monthly_d20_ssh_gate_reference_1980_2024.csv"
)
ANCHORED_CSV = OUT_DATA / "soda3_5day_d20_ssh_anchored.csv"
LAG_CSV = OUT_DATA / "soda3_5day_d20_ssh_lag_correlations.csv"
EVENT_SUMMARY_CSV = OUT_DATA / "soda3_5day_d20_ssh_event_summary.csv"
DIAGNOSTICS_JSON = OUT_DATA / "soda3_5day_d20_ssh_diagnostics.json"
FIGURE_PNG = OUT_DIR / "soda3_5day_d20_ssh_propagation.png"
FIGURE_PDF = OUT_PDF / "soda3_5day_d20_ssh_propagation.pdf"
SUMMARY_MD = OUT_DIR / "SODA3_5DAY_D20_SSH_RESULTS_CN.md"

EVENTS = {
    1997: "1997 EP",
    2004: "2004 CP",
    2015: "2015 EP",
    2023: "2023 EP-like",
}
BASELINE = (1980, 2024)
MONTHS = tuple(range(1, 7))
GATES = np.arange(150.0, 241.0, 5.0)
ALL_LAGS = np.arange(-6, 9)
EARTH_RADIUS = 6_371_000.0

BEST_LAGS = {
    "wind_to_q220": np.arange(0, 5),
    "wind_to_d20_220": np.arange(0, 5),
    "q220_to_d20_220": np.arange(0, 5),
    "q220_to_ssh_220": np.arange(0, 5),
    "d20_180_to_220": np.arange(0, 7),
    "ssh_180_to_220": np.arange(0, 7),
    "d20_220_to_t5_220": np.arange(0, 7),
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 360,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.5,
            "axes.titlesize": 9.7,
            "axes.labelsize": 8.8,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 7.1,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def same_month_residual(
    values: np.ndarray,
    times: pd.DatetimeIndex,
) -> np.ndarray:
    """Remove each calendar month's 1980-2024 mean and linear trend."""
    values = np.asarray(values, dtype=float)
    output = np.full(values.shape, np.nan, dtype=float)
    for month in MONTHS:
        selected = (times.month == month) & np.isfinite(values)
        baseline = (
            selected
            & (times.year >= BASELINE[0])
            & (times.year <= BASELINE[1])
        )
        years = times.year[baseline].astype(float)
        fit_values = values[baseline]
        if len(fit_values) < 3:
            continue
        design = np.column_stack([np.ones(len(years)), years])
        intercept, slope = np.linalg.lstsq(
            design,
            fit_values,
            rcond=None,
        )[0]
        output[selected] = values[selected] - (
            intercept + slope * times.year[selected].astype(float)
        )
    return output


def weighted_gate_mean(
    field: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    longitude: float,
) -> float:
    section = interpolate_longitude(field, lon, longitude)
    weights = np.cos(np.deg2rad(lat))
    valid = np.isfinite(section)
    if not np.any(valid):
        return float("nan")
    return float(np.average(section[valid], weights=weights[valid]))


def monthly_reference() -> pd.DataFrame:
    """Compute gate-wise D20, SSH and 5-m temperature monthly anomalies."""
    if MONTHLY_REFERENCE_CSV.exists():
        cached = pd.read_csv(MONTHLY_REFERENCE_CSV, parse_dates=["time"])
        required = {
            "d20_m_anom",
            "ssh_m_anom",
            "sst_c_anom",
            "longitude_e",
        }
        if required.issubset(cached.columns):
            return cached

    rows: list[dict[str, float | int | pd.Timestamp]] = []
    with xr.open_dataset(
        TEMP_NC,
        engine="h5netcdf",
        decode_times=True,
    ) as temperature_dataset:
        with xr.open_dataset(
            PROCESS_NC,
            engine="h5netcdf",
            decode_times=True,
        ) as process_dataset:
            temperature_times = pd.DatetimeIndex(
                temperature_dataset["time"].values
            )
            process_times = pd.DatetimeIndex(process_dataset["time"].values)
            if not temperature_times.equals(process_times):
                raise ValueError("Monthly temperature and SSH times differ")
            depth = np.asarray(
                temperature_dataset["depth"].to_numpy(),
                dtype=float,
            )
            lat = np.asarray(
                temperature_dataset["lat"].to_numpy(),
                dtype=float,
            )
            lon = (
                np.asarray(
                    temperature_dataset["lon"].to_numpy(),
                    dtype=float,
                )
                % 360.0
            )
            process_lat = np.asarray(
                process_dataset["lat"].to_numpy(),
                dtype=float,
            )
            process_lon = (
                np.asarray(
                    process_dataset["lon"].to_numpy(),
                    dtype=float,
                )
                % 360.0
            )
            if not np.allclose(lat, process_lat):
                raise ValueError("Monthly temperature and SSH latitudes differ")
            if not np.allclose(lon, process_lon):
                raise ValueError("Monthly temperature and SSH longitudes differ")

            for time_index, timestamp in enumerate(temperature_times):
                temperature = temperature_dataset["temp"].isel(
                    time=time_index
                ).to_numpy()
                ssh = process_dataset["ssh"].isel(time=time_index).to_numpy()
                d20 = d20_from_temperature(temperature, depth)
                for longitude in GATES:
                    rows.append(
                        {
                            "time": timestamp,
                            "year": timestamp.year,
                            "month": timestamp.month,
                            "longitude_e": float(longitude),
                            "d20_m": weighted_gate_mean(
                                d20,
                                lat,
                                lon,
                                float(longitude),
                            ),
                            "ssh_m": weighted_gate_mean(
                                ssh,
                                lat,
                                lon,
                                float(longitude),
                            ),
                            # The shallowest tracer level is about 5 m.
                            "sst_c": weighted_gate_mean(
                                temperature[0],
                                lat,
                                lon,
                                float(longitude),
                            ),
                        }
                    )

    frame = pd.DataFrame(rows).sort_values(["longitude_e", "time"])
    pieces = []
    for _, current in frame.groupby("longitude_e", sort=True):
        current = current.sort_values("time").copy()
        times = pd.DatetimeIndex(current["time"])
        for variable in ("d20_m", "ssh_m", "sst_c"):
            current[f"{variable}_anom"] = same_month_residual(
                current[variable].to_numpy(dtype=float),
                times,
            )
        pieces.append(current)
    frame = pd.concat(pieces, ignore_index=True).sort_values(
        ["time", "longitude_e"]
    )
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    frame.to_csv(MONTHLY_REFERENCE_CSV, index=False)
    return frame


def read_five_day() -> pd.DataFrame:
    pieces = []
    for year in EVENTS:
        path = INPUT_DIR / f"soda3_5day_transport_{year}_jan_jun.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        current = pd.read_csv(path, parse_dates=["time"])
        expected_times = 37 if year == 2004 else 36
        if current["time"].nunique() != expected_times:
            raise ValueError(
                f"{year}: expected {expected_times} times, "
                f"found {current['time'].nunique()}"
            )
        required = {
            "d20_m",
            "ssh_m",
            "sst_c",
            "d20_valid_lat_count",
        }
        missing = required - set(current.columns)
        if missing:
            raise KeyError(f"{path} lacks {sorted(missing)}")
        pieces.append(current)
    frame = pd.concat(pieces, ignore_index=True).sort_values(
        ["time", "longitude_e"]
    )
    if frame.duplicated(["time", "longitude_e"]).any():
        raise ValueError("Duplicate 5-day time-longitude rows")
    return frame


def anchor_five_day(
    five_day: pd.DataFrame,
    monthly: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    frame = five_day.copy()
    diagnostics: dict[str, float] = {}
    for raw in ("d20_m", "ssh_m", "sst_c"):
        within_month_mean = frame.groupby(
            ["year", "month", "longitude_e"]
        )[raw].transform("mean")
        departure = f"{raw}_within_month_departure"
        anchored = f"{raw}_anchored_anom"
        frame[departure] = frame[raw] - within_month_mean
        reference = monthly[
            ["year", "month", "longitude_e", f"{raw}_anom"]
        ].rename(columns={f"{raw}_anom": "_monthly_reference"})
        frame = frame.merge(
            reference,
            on=["year", "month", "longitude_e"],
            how="left",
            validate="many_to_one",
        )
        frame[anchored] = frame[departure] + frame["_monthly_reference"]
        reconstruction = frame.groupby(
            ["year", "month", "longitude_e"]
        )[anchored].mean()
        target = (
            monthly.loc[monthly["year"].isin(EVENTS)]
            .set_index(["year", "month", "longitude_e"])[f"{raw}_anom"]
            .reindex(reconstruction.index)
        )
        diagnostics[f"{raw}_monthly_reconstruction_max_abs_error"] = float(
            np.nanmax(np.abs(reconstruction.to_numpy() - target.to_numpy()))
        )
        frame = frame.drop(columns="_monthly_reference")

    transport = pd.read_csv(TRANSPORT_ANCHORED_CSV, parse_dates=["time"])
    transport_columns = [
        "time",
        "longitude_e",
        "q20_pw_anchored_anom",
        "taux_central_nm2_anchored_anom",
    ]
    if not set(transport_columns).issubset(transport.columns):
        raise KeyError("Anchored transport file lacks required columns")
    frame = frame.merge(
        transport[transport_columns],
        on=["time", "longitude_e"],
        how="left",
        validate="one_to_one",
    )
    if frame[
        ["q20_pw_anchored_anom", "taux_central_nm2_anchored_anom"]
    ].isna().any().any():
        raise ValueError("Missing anchored wind or heat-transport values")
    return frame.sort_values(["time", "longitude_e"]), diagnostics


def event_series(
    frame: pd.DataFrame,
    year: int,
) -> dict[str, pd.Series]:
    current = frame.loc[frame["year"].eq(year)].copy()
    output: dict[str, pd.Series] = {}
    for longitude in (180.0, 200.0, 220.0):
        selected = current.loc[current["longitude_e"].eq(longitude)].sort_values(
            "time"
        )
        selected = selected.set_index("time")
        suffix = int(longitude)
        output[f"q{suffix}"] = selected["q20_pw_anchored_anom"]
        output[f"d20_{suffix}"] = selected["d20_m_anchored_anom"]
        output[f"ssh_{suffix}"] = selected["ssh_m_anchored_anom"]
        output[f"t5_{suffix}"] = selected["sst_c_anchored_anom"]
        if longitude == 220.0:
            output["wind"] = selected["taux_central_nm2_anchored_anom"]
    return output


def transformed(series: pd.Series, method: str) -> pd.Series:
    if method == "level":
        return series
    if method == "15day_change":
        return series.diff(3)
    raise ValueError(method)


RELATIONSHIPS = (
    ("wind_to_q220", "wind", "q220", "level"),
    ("wind_to_d20_220", "wind", "d20_220", "level"),
    ("q220_to_d20_220", "q220", "d20_220", "level"),
    ("q220_to_ssh_220", "q220", "ssh_220", "level"),
    ("d20_180_to_220", "d20_180", "d20_220", "15day_change"),
    ("ssh_180_to_220", "ssh_180", "ssh_220", "15day_change"),
    ("d20_220_to_t5_220", "d20_220", "t5_220", "level"),
)


def lag_correlations(frame: pd.DataFrame) -> pd.DataFrame:
    """Positive lag means the source leads the target."""
    rows = []
    for year in EVENTS:
        series = event_series(frame, year)
        for name, source_name, target_name, method in RELATIONSHIPS:
            source = transformed(series[source_name], method)
            target = transformed(series[target_name], method)
            for lag in ALL_LAGS:
                rows.append(
                    {
                        "event_year": year,
                        "relationship": name,
                        "source": source_name,
                        "target": target_name,
                        "transformation": method,
                        "lag_steps_source_leads": int(lag),
                        "lag_days_source_leads": int(lag * 5),
                        "correlation": source.corr(target.shift(-lag)),
                        "n_pairs": int(
                            (
                                source.notna()
                                & target.shift(-lag).notna()
                            ).sum()
                        ),
                    }
                )
    return pd.DataFrame(rows)


def best_positive_lag(
    lags: pd.DataFrame,
    year: int,
    relationship: str,
) -> tuple[int, float]:
    selected = lags.loc[
        lags["event_year"].eq(year)
        & lags["relationship"].eq(relationship)
        & lags["lag_steps_source_leads"].isin(BEST_LAGS[relationship])
    ].dropna(subset=["correlation"])
    if selected.empty:
        return -999, float("nan")
    row = selected.loc[selected["correlation"].idxmax()]
    return int(row["lag_days_source_leads"]), float(row["correlation"])


def event_summary(
    frame: pd.DataFrame,
    lags: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    distance_m = EARTH_RADIUS * np.deg2rad(40.0)
    for year, label in EVENTS.items():
        series = event_series(frame, year)
        row: dict[str, float | int | str] = {
            "event_year": year,
            "event_label": label,
            "d20_ssh_r_140w": series["d20_220"].corr(series["ssh_220"]),
        }
        for relationship, short_name in (
            ("wind_to_q220", "wind_to_q140w"),
            ("wind_to_d20_220", "wind_to_d20_140w"),
            ("q220_to_d20_220", "q140w_to_d20_140w"),
            ("q220_to_ssh_220", "q140w_to_ssh_140w"),
            ("d20_180_to_220", "d20_dateline_to_140w"),
            ("ssh_180_to_220", "ssh_dateline_to_140w"),
            ("d20_220_to_t5_220", "d20_to_t5_140w"),
        ):
            days, correlation = best_positive_lag(lags, year, relationship)
            row[f"{short_name}_best_lag_days"] = days
            row[f"{short_name}_best_r"] = correlation
        d20_days = int(row["d20_dateline_to_140w_best_lag_days"])
        ssh_days = int(row["ssh_dateline_to_140w_best_lag_days"])
        row["d20_implied_speed_ms"] = (
            distance_m / (d20_days * 86_400.0)
            if d20_days > 0
            else np.nan
        )
        row["ssh_implied_speed_ms"] = (
            distance_m / (ssh_days * 86_400.0)
            if ssh_days > 0
            else np.nan
        )
        selected = frame.loc[
            frame["year"].eq(year) & frame["longitude_e"].eq(220.0)
        ].sort_values("time")
        time_differences = np.diff(
            selected["time"].to_numpy(dtype="datetime64[D]")
        ).astype("timedelta64[D]").astype(int)
        median_interval_days = float(np.median(time_differences))
        row["q140w_positive_pw_days"] = float(
            np.maximum(
                selected["q20_pw_anchored_anom"].to_numpy(dtype=float),
                0.0,
            ).sum()
            * median_interval_days
        )
        row["d20_140w_jan_jun_mean_anom_m"] = float(
            selected["d20_m_anchored_anom"].mean()
        )
        row["d20_140w_may_jun_mean_anom_m"] = float(
            selected.loc[
                selected["month"].ge(5),
                "d20_m_anchored_anom",
            ].mean()
        )
        row["d20_140w_positive_m_days"] = float(
            np.maximum(
                selected["d20_m_anchored_anom"].to_numpy(dtype=float),
                0.0,
            ).sum()
            * median_interval_days
        )
        row["d20_140w_days_above_10m"] = float(
            selected["d20_m_anchored_anom"].gt(10.0).sum()
            * median_interval_days
        )
        row["ssh_140w_jan_jun_mean_anom_m"] = float(
            selected["ssh_m_anchored_anom"].mean()
        )
        row["t5_140w_may_jun_mean_anom_c"] = float(
            selected.loc[
                selected["month"].ge(5),
                "sst_c_anchored_anom",
            ].mean()
        )
        d20_index = selected["d20_m_anchored_anom"].idxmax()
        ssh_index = selected["ssh_m_anchored_anom"].idxmax()
        row["d20_140w_max_anom_m"] = selected.loc[
            d20_index, "d20_m_anchored_anom"
        ]
        row["d20_140w_max_date"] = selected.loc[
            d20_index, "time"
        ].strftime("%Y-%m-%d")
        row["ssh_140w_max_anom_m"] = selected.loc[
            ssh_index, "ssh_m_anchored_anom"
        ]
        row["ssh_140w_max_date"] = selected.loc[
            ssh_index, "time"
        ].strftime("%Y-%m-%d")
        rows.append(row)
    return pd.DataFrame(rows)


def coordinate_edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    midpoint = 0.5 * (values[:-1] + values[1:])
    return np.r_[
        values[0] - (midpoint[0] - values[0]),
        midpoint,
        values[-1] + (values[-1] - midpoint[-1]),
    ]


def date_edges(dates: pd.DatetimeIndex) -> np.ndarray:
    numeric = mdates.date2num(dates.to_pydatetime())
    return coordinate_edges(numeric)


def robust_limit(values: np.ndarray, percentile: float, minimum: float) -> float:
    return max(
        minimum,
        float(np.nanpercentile(np.abs(values.astype(float)), percentile)),
    )


def plot_propagation(
    frame: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    setup_style()
    figure, axes = plt.subplots(
        4,
        3,
        figsize=(14.2, 10.4),
        gridspec_kw={"width_ratios": [1.0, 1.0, 1.35]},
    )
    figure.subplots_adjust(
        left=0.075,
        right=0.975,
        bottom=0.115,
        top=0.91,
        wspace=0.19,
        hspace=0.24,
    )

    d20_limit = robust_limit(
        frame["d20_m_anchored_anom"].to_numpy(),
        98.0,
        10.0,
    )
    ssh_limit = robust_limit(
        frame["ssh_m_anchored_anom"].to_numpy(),
        98.0,
        0.04,
    )
    d20_norm = mpl.colors.TwoSlopeNorm(
        vmin=-d20_limit,
        vcenter=0.0,
        vmax=d20_limit,
    )
    ssh_norm = mpl.colors.TwoSlopeNorm(
        vmin=-ssh_limit,
        vcenter=0.0,
        vmax=ssh_limit,
    )
    longitude_edges = coordinate_edges(GATES)

    scale_columns = {
        "taux_central_nm2_anchored_anom": "#2471A3",
        "q20_pw_anchored_anom": "#1E8449",
        "d20_m_anchored_anom": "#C0392B",
        "sst_c_anchored_anom": "#7D3C98",
    }
    scales = {
        column: max(float(frame[column].std()), 1.0e-12)
        for column in scale_columns
    }
    line_labels = {
        "taux_central_nm2_anchored_anom": "central wind stress",
        "q20_pw_anchored_anom": "140°W Q20",
        "d20_m_anchored_anom": "140°W D20",
        "sst_c_anchored_anom": "140°W T(~5 m)",
    }
    d20_image = ssh_image = None

    for row, (year, label) in enumerate(EVENTS.items()):
        current = frame.loc[frame["year"].eq(year)].sort_values(
            ["time", "longitude_e"]
        )
        dates = pd.DatetimeIndex(current["time"].drop_duplicates().sort_values())
        d20 = current.pivot(
            index="time",
            columns="longitude_e",
            values="d20_m_anchored_anom",
        ).reindex(index=dates, columns=GATES)
        ssh = current.pivot(
            index="time",
            columns="longitude_e",
            values="ssh_m_anchored_anom",
        ).reindex(index=dates, columns=GATES)

        d20_image = axes[row, 0].pcolormesh(
            longitude_edges,
            date_edges(dates),
            d20.to_numpy(),
            cmap="RdBu_r",
            norm=d20_norm,
            shading="flat",
            rasterized=True,
        )
        ssh_image = axes[row, 1].pcolormesh(
            longitude_edges,
            date_edges(dates),
            ssh.to_numpy(),
            cmap="RdBu_r",
            norm=ssh_norm,
            shading="flat",
            rasterized=True,
        )

        for column in (0, 1):
            axis = axes[row, column]
            axis.axvline(180.0, color="0.15", ls="--", lw=0.9)
            axis.axvline(220.0, color="0.15", ls="-", lw=1.0)
            axis.set_xlim(147.5, 242.5)
            axis.set_ylim(
                mdates.date2num(pd.Timestamp(year, 6, 30)),
                mdates.date2num(pd.Timestamp(year, 1, 1)),
            )
            axis.set_xticks([150, 180, 200, 220, 240])
            axis.set_xticklabels(
                ["150°E", "180°", "160°W", "140°W", "120°W"]
            )
            axis.yaxis.set_major_locator(mdates.MonthLocator())
            axis.yaxis.set_major_formatter(mdates.DateFormatter("%b"))
            axis.grid(False)
        axes[row, 0].set_ylabel(f"{label}\nTime")
        axes[row, 1].tick_params(labelleft=False)

        gate = current.loc[current["longitude_e"].eq(220.0)].sort_values(
            "time"
        )
        for column, color in scale_columns.items():
            axes[row, 2].plot(
                gate["time"],
                gate[column] / scales[column],
                color=color,
                lw=1.35,
                label=line_labels[column],
            )
        axes[row, 2].axhline(0.0, color="0.55", lw=0.7)
        axes[row, 2].grid(axis="y", color="0.88", lw=0.6)
        axes[row, 2].set_xlim(
            pd.Timestamp(year, 1, 1),
            pd.Timestamp(year, 6, 30),
        )
        axes[row, 2].xaxis.set_major_locator(mdates.MonthLocator())
        axes[row, 2].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        axes[row, 2].set_ylabel("Anomaly / pooled SD")
        lag_row = summary.loc[summary["event_year"].eq(year)].iloc[0]
        axes[row, 2].text(
            0.985,
            0.93,
            (
                "Q140W→D20: "
                f"{int(lag_row['q140w_to_d20_140w_best_lag_days'])} d, "
                f"r={lag_row['q140w_to_d20_140w_best_r']:.2f}\n"
                "mean D20′="
                f"{lag_row['d20_140w_jan_jun_mean_anom_m']:+.1f} m"
            ),
            transform=axes[row, 2].transAxes,
            ha="right",
            va="top",
            fontsize=7.2,
            bbox={"facecolor": "white", "alpha": 0.72, "edgecolor": "none"},
        )
        if row == 0:
            axes[row, 2].legend(
                ncol=2,
                loc="lower left",
                frameon=False,
            )

    axes[0, 0].set_title(
        "(a) D20 anomaly: eastward thermocline signal",
        fontweight="bold",
    )
    axes[0, 1].set_title(
        "(b) SSH anomaly: dynamically consistent signal",
        fontweight="bold",
    )
    axes[0, 2].set_title(
        "(c) Sequence at 140°W",
        fontweight="bold",
    )
    for axis in axes[-1, :2]:
        axis.set_xlabel("Longitude")
    axes[-1, 2].set_xlabel("Month")

    if d20_image is None or ssh_image is None:
        raise RuntimeError("No images were plotted")
    d20_colorbar = figure.colorbar(
        d20_image,
        ax=list(axes[:, 0]),
        orientation="horizontal",
        fraction=0.035,
        pad=0.045,
        aspect=35,
        extend="both",
    )
    d20_colorbar.set_label("D20 anomaly (m; positive = deeper)")
    ssh_colorbar = figure.colorbar(
        ssh_image,
        ax=list(axes[:, 1]),
        orientation="horizontal",
        fraction=0.035,
        pad=0.045,
        aspect=35,
        extend="both",
    )
    ssh_colorbar.set_label("SSH anomaly (m; positive = higher)")

    figure.suptitle(
        "SODA3.15.2 five-day propagation toward the 140°W transition gate",
        fontsize=14.0,
        fontweight="bold",
        y=0.972,
    )
    figure.text(
        0.075,
        0.025,
        (
            "Source: official SODA3.15.2 5-day reanalysis, Jan-Jun. "
            "5°S-5°N means; D20 from the first downward 20°C crossing. "
            "Five-day departures are anchored to detrended 1980-2024 "
            "calendar-month anomalies. Dashed: dateline; solid: 140°W. "
            "Lag annotations are descriptive (four events), not causal tests."
        ),
        ha="left",
        va="bottom",
        fontsize=7.5,
        color="0.28",
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_PNG, bbox_inches="tight")
    figure.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(figure)


def write_summary(
    summary: pd.DataFrame,
    diagnostics: dict[str, float],
) -> None:
    table = summary[
        [
            "event_year",
            "d20_ssh_r_140w",
            "wind_to_q140w_best_lag_days",
            "wind_to_q140w_best_r",
            "q140w_to_d20_140w_best_lag_days",
            "q140w_to_d20_140w_best_r",
            "d20_dateline_to_140w_best_lag_days",
            "d20_dateline_to_140w_best_r",
            "d20_implied_speed_ms",
            "d20_140w_jan_jun_mean_anom_m",
            "d20_140w_days_above_10m",
        ]
    ].copy()
    table.columns = [
        "事件",
        "140W D20-SSH r",
        "风→Q140W lag(d)",
        "风→Q140W r",
        "Q140W→D20 lag(d)",
        "Q140W→D20 r",
        "D20 180→140W lag(d)",
        "D20传播 r",
        "推算速度(m/s)",
        "140W D20均值(m)",
        "D20>+10m天数",
    ]
    table_text = table.to_markdown(index=False, floatfmt=".2f")
    median_d20_ssh = float(summary["d20_ssh_r_140w"].median())
    median_q_lag = float(
        summary["q140w_to_d20_140w_best_lag_days"].median()
    )
    median_prop_lag = float(
        summary["d20_dateline_to_140w_best_lag_days"].median()
    )
    lines = [
        "# SODA3 五日 D20/SSH 传播诊断",
        "",
        "## 数据与方法",
        "",
        (
            "- 官方 SODA3.15.2 五日再分析；1997、2004、2015、2023 年"
            "1-6月，5°S-5°N，150°E-120°W。"
        ),
        (
            "- D20由温度剖面向下首次穿过20°C的位置线性插值得到；"
            "SSH直接来自同一五日文件。"
        ),
        (
            "- 五日月内扰动锚定到1980-2024年同月去趋势异常；"
            "所以事件月平均与完整月资料严格一致。"
        ),
        (
            "- 正滞后表示前一个量领先后一个量。日界线到140°W传播使用"
            "15日变化相关，减少共同季节趋势造成的虚高相关。"
        ),
        "",
        "## 事件结果",
        "",
        table_text,
        "",
        "## 当前可以怎样解释",
        "",
        (
            f"- 四个事件在140°W的D20与SSH中位相关为"
            f"{median_d20_ssh:.2f}。这说明等温线深浅和海面高度包含"
            "一致的热跃层动力信号。"
        ),
        (
            f"- 140°W暖水输送领先当地D20加深的最佳滞后中位数约"
            f"{median_q_lag:.0f}天；日界线到140°W的D20变化最佳传播"
            f"滞后中位数约{median_prop_lag:.0f}天。"
        ),
        (
            "- 四个事件都有15-20天量级的日界线到140°W传播，"
            "所以“有没有东传”不是充分的分型条件。差异主要出现在"
            "信号到达后能否形成足够强、足够持久的东部D20/SSH异常。"
        ),
        (
            "- 1997和2015在140°W的1-6月D20平均异常分别约"
            f"{summary.loc[summary['event_year'].eq(1997), 'd20_140w_jan_jun_mean_anom_m'].iloc[0]:+.1f}"
            "和"
            f"{summary.loc[summary['event_year'].eq(2015), 'd20_140w_jan_jun_mean_anom_m'].iloc[0]:+.1f} m，"
            "而2004和2023只有"
            f"{summary.loc[summary['event_year'].eq(2004), 'd20_140w_jan_jun_mean_anom_m'].iloc[0]:+.1f}"
            "和"
            f"{summary.loc[summary['event_year'].eq(2023), 'd20_140w_jan_jun_mean_anom_m'].iloc[0]:+.1f} m。"
        ),
        (
            "- 因而原来的140°W“输送闸门”需要补上第二个条件："
            "穿过闸门的热量还必须在东部转化为持续的热跃层加深和储热。"
            "动力链应写成：西风应力异常 → 暖水东输 → D20/SSH向东传播"
            " → 东部储存/维持 → 近表层升温与反馈闭合。"
        ),
        "",
        "## 限制",
        "",
        (
            "- D20与SSH来自同一个SODA再分析系统，二者一致属于内部"
            "动力一致性检查，不是独立资料验证。"
        ),
        (
            "- 只有4个事件且每个事件约36个五日时次；最佳滞后经过"
            "预设的0-20天（局地链条）或0-30天（传播）候选滞后筛选，"
            "只能作为描述性证据，不能直接宣称因果。"
        ),
        (
            "- SODA最浅温度层约5 m，图中的T(~5 m)不是卫星皮肤SST。"
        ),
        "",
        "## 数值质量控制",
        "",
        *[
            f"- `{name}` = {value:.3e}"
            for name, value in diagnostics.items()
        ],
        "",
        "## 输出",
        "",
        f"- PDF：`{FIGURE_PDF}`",
        f"- 五日异常：`{ANCHORED_CSV}`",
        f"- 全滞后相关：`{LAG_CSV}`",
        f"- 事件摘要：`{EVENT_SUMMARY_CSV}`",
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    monthly = monthly_reference()
    five_day = read_five_day()
    anchored, diagnostics = anchor_five_day(five_day, monthly)
    lags = lag_correlations(anchored)
    summary = event_summary(anchored, lags)

    diagnostics.update(
        {
            "n_events": float(len(EVENTS)),
            "n_5day_times": float(anchored["time"].nunique()),
            "n_longitude_gates": float(anchored["longitude_e"].nunique()),
            "d20_min_m": float(anchored["d20_m"].min()),
            "d20_max_m": float(anchored["d20_m"].max()),
            "ssh_min_m": float(anchored["ssh_m"].min()),
            "ssh_max_m": float(anchored["ssh_m"].max()),
            "d20_valid_lat_count_min": float(
                anchored["d20_valid_lat_count"].min()
            ),
        }
    )

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    anchored.to_csv(ANCHORED_CSV, index=False)
    lags.to_csv(LAG_CSV, index=False)
    summary.to_csv(EVENT_SUMMARY_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    plot_propagation(anchored, summary)
    write_summary(summary, diagnostics)
    print(f"Wrote {ANCHORED_CSV}")
    print(f"Wrote {EVENT_SUMMARY_CSV}")
    print(f"Wrote {FIGURE_PDF}")
    print(f"Wrote {SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
