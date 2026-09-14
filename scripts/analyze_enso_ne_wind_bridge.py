#!/usr/bin/env python3
"""Close the FEP rain-dipole to northeasterly-wind suppression bridge."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/private/tmp/codex_maryland_ne_wind_cache")
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt


WIND_PART1 = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jan_may.nc"
)
WIND_JUNE = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_pressure850_wind_tropics_1deg_1980_2026_jun.nc"
)
WIND_JULY = (
    ROOT
    / "data/raw/era5/"
    "era5_monthly_850_ne_box_july_1982_2024.nc"
)
COUPLING = (
    ROOT
    / "data/derived/research_2026/"
    "enso_full_year_coupling_monthly_1982_2024.csv"
)
EVENTS = (
    ROOT
    / "data/derived/research_2026/"
    "enso_perturbation_event_indices_1982_2023.csv"
)
OUTPUT_EVENTS = (
    ROOT
    / "data/derived/research_2026/"
    "enso_ne_wind_bridge_event_indices.csv"
)
OUTPUT_RELATIONSHIPS = (
    ROOT
    / "data/derived/research_2026/"
    "enso_ne_wind_bridge_relationships.csv"
)
FIGURE = (
    ROOT
    / "outputs/research_2026/perturbation_attribution/"
    "fig4_fep_ne_wind_bridge"
)

EVENT_YEARS = (
    1982,
    1986,
    1991,
    1994,
    1997,
    2002,
    2004,
    2006,
    2009,
    2015,
    2018,
    2019,
    2023,
)
RANDOM_SEED = 20260731


def normalize(dataset: xr.Dataset) -> xr.Dataset:
    dataset = dataset.rename(
        {
            name: replacement
            for name, replacement in (
                ("valid_time", "time"),
                ("latitude", "lat"),
                ("longitude", "lon"),
            )
            if name in dataset.coords
        }
    )
    return dataset.assign_coords(lon=dataset.lon % 360).sortby(
        ["lat", "lon"]
    )


def area_mean(field: xr.DataArray) -> xr.DataArray:
    subset = field.sel(lat=slice(3, 7), lon=slice(180, 230))
    weights = np.cos(np.deg2rad(subset.lat))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def load_monthly_ne_wind() -> pd.DataFrame:
    datasets = []
    for path in (WIND_PART1, WIND_JUNE, WIND_JULY):
        with xr.open_dataset(path, engine="h5netcdf") as raw:
            dataset = normalize(raw).sel(
                time=slice("1982-01-01", "2024-12-31")
            )
            dataset = dataset.sel(pressure_level=850, drop=True)
            current = xr.Dataset(
                {
                    "u": area_mean(dataset["u"]).load(),
                    "v": area_mean(dataset["v"]).load(),
                }
            )
            datasets.append(current)
    combined = xr.concat(datasets, dim="time").sortby("time")
    combined = combined.sel(
        time=combined.time.dt.month.isin([5, 6, 7])
    )
    if combined.time.to_index().duplicated().any():
        raise ValueError("Duplicate ERA5 monthly wind records")
    time = pd.to_datetime(combined.time.values)
    frame = pd.DataFrame(
        {
            "year": time.year,
            "month": time.month,
            "u850_jiang_box": combined["u"].values.astype(float),
            "v850_jiang_box": combined["v"].values.astype(float),
        }
    )
    frame["ne850_jiang_box"] = -(
        frame["u850_jiang_box"] + frame["v850_jiang_box"]
    ) / np.sqrt(2.0)
    for variable in (
        "u850_jiang_box",
        "v850_jiang_box",
        "ne850_jiang_box",
    ):
        climatology = frame.groupby("month")[variable].transform("mean")
        anomaly = frame[variable] - climatology
        decimal_year = frame["year"] + (frame["month"] - 0.5) / 12.0
        coefficients = np.polyfit(decimal_year, anomaly, 1)
        frame[f"{variable}_ad"] = (
            anomaly - np.polyval(coefficients, decimal_year)
        )
    return frame


def residualize_on_sst(frame: pd.DataFrame) -> pd.DataFrame:
    coupling = pd.read_csv(
        COUPLING,
        usecols=[
            "year",
            "month",
            "nino34_raw_c",
            "sst_type_raw_c",
        ],
    )
    frame = frame.merge(
        coupling,
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )
    pieces = []
    for month, group in frame.groupby("month"):
        design = np.column_stack(
            [
                np.ones(len(group)),
                group["year"].to_numpy(dtype=float) - 2003.0,
                group["nino34_raw_c"].to_numpy(dtype=float),
                group["sst_type_raw_c"].to_numpy(dtype=float),
            ]
        )
        current = group[["year", "month"]].copy()
        for variable in (
            "u850_jiang_box_ad",
            "v850_jiang_box_ad",
            "ne850_jiang_box_ad",
        ):
            coefficients = np.linalg.lstsq(
                design,
                group[variable].to_numpy(dtype=float),
                rcond=None,
            )[0]
            current[f"{variable}_residual"] = (
                group[variable].to_numpy(dtype=float)
                - design @ coefficients
            )
        pieces.append(current)
    return frame.merge(
        pd.concat(pieces, ignore_index=True),
        on=["year", "month"],
        how="left",
        validate="one_to_one",
    )


def build_event_indices() -> pd.DataFrame:
    monthly = residualize_on_sst(load_monthly_ne_wind())
    seasonal = (
        monthly.groupby("year")
        .agg(
            ne850_mjj=(
                "ne850_jiang_box_ad_residual",
                "mean",
            ),
            easterly850_mjj=(
                "u850_jiang_box_ad_residual",
                lambda values: -float(np.mean(values)),
            ),
            northerly850_mjj=(
                "v850_jiang_box_ad_residual",
                lambda values: -float(np.mean(values)),
            ),
        )
        .reindex(EVENT_YEARS)
        .reset_index()
    )
    event = pd.read_csv(EVENTS)
    output = event.merge(
        seasonal,
        on="year",
        how="left",
        validate="one_to_one",
    )
    if output[
        ["ne850_mjj", "easterly850_mjj", "northerly850_mjj"]
    ].isna().any().any():
        raise ValueError("Missing MJJ northeasterly event indices")
    for column in (
        "ne850_mjj",
        "easterly850_mjj",
        "northerly850_mjj",
    ):
        output[f"{column}_z"] = (
            output[column] - output[column].mean()
        ) / output[column].std(ddof=1)
    output.to_csv(OUTPUT_EVENTS, index=False)
    return output


def partial_r(
    frame: pd.DataFrame,
    x: str,
    y: str,
    controls: tuple[str, ...],
) -> tuple[float, float, float]:
    design = np.column_stack(
        [
            np.ones(len(frame)),
            *[
                frame[column].to_numpy(dtype=float)
                for column in controls
            ],
        ]
    )
    x_values = frame[x].to_numpy(dtype=float)
    y_values = frame[y].to_numpy(dtype=float)
    x_residual = x_values - design @ np.linalg.lstsq(
        design,
        x_values,
        rcond=None,
    )[0]
    y_residual = y_values - design @ np.linalg.lstsq(
        design,
        y_values,
        rcond=None,
    )[0]
    observed = float(np.corrcoef(x_residual, y_residual)[0, 1])
    rng = np.random.default_rng(RANDOM_SEED)
    samples = np.empty(10_000)
    for index in range(len(samples)):
        selected = rng.integers(0, len(frame), len(frame))
        samples[index] = np.corrcoef(
            x_residual[selected],
            y_residual[selected],
        )[0, 1]
    low, high = np.nanpercentile(samples, [2.5, 97.5])
    return observed, float(low), float(high)


def build_relationships(frame: pd.DataFrame) -> pd.DataFrame:
    tests = (
        (
            "FEP residual -> northeasterly intrusion",
            "fep_residual_mjj_z",
            "ne850_mjj_z",
            ("east_ocean_state_z_z", "early_ec_apr_z"),
        ),
        (
            "Rain dipole -> northeasterly intrusion",
            "precip_dipole_mjj_z",
            "ne850_mjj_z",
            (
                "east_ocean_state_z_z",
                "early_ec_apr_z",
                "fep_residual_mjj_z",
            ),
        ),
        (
            "Northeasterly intrusion -> zonal stress",
            "ne850_mjj_z",
            "tau_response_mjj_z",
            (
                "east_ocean_state_z_z",
                "early_ec_apr_z",
                "fep_residual_mjj_z",
            ),
        ),
        (
            "Northeasterly intrusion -> coupling",
            "ne850_mjj_z",
            "coupling_mjj_z",
            (
                "east_ocean_state_z_z",
                "early_ec_apr_z",
                "fep_residual_mjj_z",
            ),
        ),
    )
    rows = []
    for name, x, y, controls in tests:
        correlation, low, high = partial_r(frame, x, y, controls)
        rows.append(
            {
                "relationship": name,
                "predictor": x,
                "response": y,
                "partial_r": correlation,
                "bootstrap_ci_low": low,
                "bootstrap_ci_high": high,
                "controls": "; ".join(controls),
                "n_events": len(frame),
            }
        )
    output = pd.DataFrame(rows)
    output.to_csv(OUTPUT_RELATIONSHIPS, index=False)
    return output


def plot_bridge(frame: pd.DataFrame, relationships: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )
    pairs = (
        (
            "precip_dipole_mjj_z",
            "ne850_mjj_z",
            "Residual rain dipole",
            "Residual 850-hPa northeasterly intrusion",
            "Rain structure does not uniquely imply wind suppression",
            relationships.iloc[1],
        ),
        (
            "ne850_mjj_z",
            "tau_response_mjj_z",
            "Residual 850-hPa northeasterly intrusion",
            "Zonal-stress response residual",
            "The Jiang wind bridge is the decisive sign test",
            relationships.iloc[2],
        ),
    )
    figure, axes = plt.subplots(1, 2, figsize=(10.4, 4.5))
    for panel_index, (
        axis,
        (x, y, xlabel, ylabel, title, result),
    ) in enumerate(zip(
        axes,
        pairs,
        strict=True,
    )):
        axis.scatter(
            frame[x],
            frame[y],
            s=34,
            color="#247ba0",
            edgecolor="white",
            linewidth=0.6,
            zorder=3,
        )
        for _, row in frame.iterrows():
            axis.annotate(
                str(int(row["year"])),
                (row[x], row[y]),
                xytext=(3, 3),
                textcoords="offset points",
                fontsize=6.5,
            )
        coefficients = np.polyfit(frame[x], frame[y], 1)
        xx = np.linspace(frame[x].min(), frame[x].max(), 100)
        axis.plot(xx, np.polyval(coefficients, xx), color="#d95f4c")
        axis.axhline(0, color="0.65", lw=0.7)
        axis.axvline(0, color="0.65", lw=0.7)
        axis.set_xlabel(xlabel + " (event SD)")
        axis.set_ylabel(ylabel + " (event SD)")
        axis.set_title(title, loc="left", weight="bold", fontsize=9.5)
        annotation_position = (
            (0.03, 0.97) if panel_index == 0 else (0.54, 0.64)
        )
        axis.text(
            *annotation_position,
            (
                f"partial r={result['partial_r']:+.2f}\n"
                f"95% CI [{result['bootstrap_ci_low']:+.2f}, "
                f"{result['bootstrap_ci_high']:+.2f}]"
            ),
            transform=axis.transAxes,
            va="top",
            fontsize=7.5,
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.82,
                "pad": 1.5,
            },
            zorder=6,
        )
        axis.grid(alpha=0.18)
    figure.suptitle(
        "FEP precipitation structure and the missing northeasterly-wind bridge",
        x=0.07,
        ha="left",
        weight="bold",
    )
    figure.text(
        0.01,
        0.01,
        "ERA5 MJJ 850-hPa winds in 3-7°N, 180-130°W; same-month 1982-2024 anomalies, detrended and residualized on Niño3.4 and Niño3-Niño4.",
        fontsize=6.7,
        color="0.35",
    )
    figure.tight_layout(rect=(0, 0.05, 1, 0.94))
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        figure.savefig(FIGURE.with_suffix(f".{suffix}"), bbox_inches="tight")
    delivery_pdf = ROOT / "output/pdf/enso_fep_ne_wind_bridge.pdf"
    delivery_pdf.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(delivery_pdf, bbox_inches="tight")
    plt.close(figure)


def main() -> int:
    for path in (WIND_PART1, WIND_JUNE, WIND_JULY, COUPLING, EVENTS):
        if not path.exists():
            raise FileNotFoundError(path)
    frame = build_event_indices()
    relationships = build_relationships(frame)
    plot_bridge(frame, relationships)
    print(OUTPUT_EVENTS)
    print(OUTPUT_RELATIONSHIPS)
    print(FIGURE.with_suffix(".pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
