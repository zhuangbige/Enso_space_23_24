#!/usr/bin/env python3
"""Reproduce the three-event equatorial Pacific Hovmoller using H20.

H20 is diagnosed from the native monthly SODA3.15.2 potential temperature:

    h20(x, y, t) = rho0 * cp * integral_0^300m max(T - 20 degC, 0) dz

The nonlinear threshold is applied before the calendar-month climatology and
same-month linear trend are removed.  The plotted field is the cosine-latitude
weighted 5S-5N mean, in GJ m-2.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fsspec
import h5py
import matplotlib as mpl
import netCDF4

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data/interim/research_2026/soda3_h20"
OUT_DIR = ROOT / "outputs/research_2026/soda3_h20"
CACHE_FILE = CACHE_DIR / "soda3_h20_0_300_equatorial_1980_2024.npz"

OFFICIAL_TEMPLATE = (
    "http://dsrs.atmos.umd.edu/DATA/soda3.15.2/REGRIDED/ocean/"
    "soda3.15.2_mn_ocean_reg_{year}.nc"
)
APDRC_URL = (
    "https://apdrc.soest.hawaii.edu/dods/public_data/"
    "SODA/soda_3.15.2/monthly_t"
)

START_YEAR = 1980
END_YEAR = 2024
BASELINE_START = 1980
BASELINE_END = 2024
RHO0 = 1025.0
CP0 = 3990.0
DEPTH_LIMIT = 300.0
FILL_THRESHOLD = -1.0e10
EVENTS = {1997: "1997/98", 2015: "2015/16", 2023: "2023/24"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild the cache")
    return parser.parse_args()


def layer_thicknesses(depth: np.ndarray, limit: float) -> np.ndarray:
    """Return each center-defined layer's overlap with 0-limit."""
    depth = np.asarray(depth, dtype=float)
    edges = np.empty(depth.size + 1, dtype=float)
    edges[0] = 0.0
    edges[1:-1] = 0.5 * (depth[:-1] + depth[1:])
    edges[-1] = depth[-1] + 0.5 * (depth[-1] - depth[-2])
    return np.maximum(0.0, np.minimum(edges[1:], limit) - edges[:-1])


def selection_slice(values: np.ndarray, lower: float, upper: float) -> slice:
    selected = np.flatnonzero((values >= lower) & (values <= upper))
    if not selected.size:
        raise ValueError(f"Empty selection: {lower} to {upper}")
    return slice(int(selected[0]), int(selected[-1]) + 1)


def compute_h20(temperature: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Apply the 20 C threshold before vertically integrating to 300 m."""
    values = np.asarray(temperature, dtype=np.float64)
    values[values <= FILL_THRESHOLD] = np.nan
    dz = layer_thicknesses(depth, DEPTH_LIMIT)
    valid = np.all(np.isfinite(values[:, dz > 0, :, :]), axis=1)
    h20 = RHO0 * CP0 * np.nansum(
        np.maximum(values[:, dz > 0, :, :] - 20.0, 0.0)
        * dz[dz > 0][None, :, None, None],
        axis=1,
    )
    h20[~valid] = np.nan
    return h20.astype(np.float32)


def read_official_year(year: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read one recent NetCDF4 annual file and calculate h20(lat, lon)."""
    url = OFFICIAL_TEMPLATE.format(year=year)
    remote = fsspec.open(
        url,
        "rb",
        block_size=8 * 1024 * 1024,
        cache_type="readahead",
    ).open()
    try:
        with h5py.File(remote, "r") as dataset:
            depth = np.asarray(dataset["st_ocean"][:], dtype=float)
            latitude = np.asarray(dataset["yt_ocean"][:], dtype=float)
            longitude = np.asarray(dataset["xt_ocean"][:], dtype=float)

            iz = np.flatnonzero(layer_thicknesses(depth, DEPTH_LIMIT) > 0)
            z_slice = slice(int(iz[0]), int(iz[-1]) + 1)
            y_slice = selection_slice(latitude, -5.0, 5.0)
            x_slice = selection_slice(longitude, 130.0, 280.0)

            temperature = np.asarray(
                dataset["temp"][:, z_slice, y_slice, x_slice],
                dtype=np.float64,
            )
            h20 = compute_h20(temperature, depth[z_slice])
            return (
                h20.astype(np.float32),
                latitude[y_slice].astype(np.float32),
                longitude[x_slice].astype(np.float32),
            )
    finally:
        remote.close()


def read_apdrc_years(
    start_year: int, end_year: int
) -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
    """Read 1980-2022 through APDRC OPeNDAP in annual blocks."""
    annual: list[np.ndarray] = []
    dataset = netCDF4.Dataset(APDRC_URL)
    try:
        depth = np.asarray(dataset.variables["lev"][:], dtype=float)
        latitude = np.asarray(dataset.variables["lat"][:], dtype=float)
        longitude = np.asarray(dataset.variables["lon"][:], dtype=float)
        iz = np.flatnonzero(layer_thicknesses(depth, DEPTH_LIMIT) > 0)
        z_slice = slice(int(iz[0]), int(iz[-1]) + 1)
        y_slice = selection_slice(latitude, -5.0, 5.0)
        x_slice = selection_slice(longitude, 130.0, 280.0)
        for year in range(start_year, end_year + 1):
            first = (year - 1980) * 12
            temperature = np.ma.filled(
                dataset.variables["temp"][
                    first : first + 12, z_slice, y_slice, x_slice
                ],
                np.nan,
            )
            annual.append(compute_h20(temperature, depth[z_slice]))
            print(f"SODA3 H20 complete: {year}", flush=True)
        return annual, latitude[y_slice].astype(np.float32), longitude[x_slice].astype(np.float32)
    finally:
        dataset.close()


def build_cache() -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    apdrc_end = min(END_YEAR, 2022)
    annual, reference_lat, reference_lon = read_apdrc_years(START_YEAR, apdrc_end)
    for year in range(max(2023, START_YEAR), END_YEAR + 1):
        h20, latitude, longitude = read_official_year(year)
        if not np.allclose(latitude, reference_lat):
            raise ValueError(f"Latitude grid changed in {year}")
        if not np.allclose(longitude, reference_lon):
            raise ValueError(f"Longitude grid changed in {year}")
        annual.append(h20)
        print(f"SODA3 H20 complete: {year}", flush=True)

    values = np.concatenate(annual, axis=0)
    times = pd.date_range(
        f"{START_YEAR}-01-01", f"{END_YEAR}-12-01", freq="MS"
    ) + pd.Timedelta(days=14)
    np.savez_compressed(
        CACHE_FILE,
        time=times.values.astype("datetime64[ns]"),
        lat=reference_lat,
        lon=reference_lon,
        h20_jm2=values,
    )
    return times, reference_lat, reference_lon, values


def load_or_build(force: bool) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray]:
    if force or not CACHE_FILE.exists():
        return build_cache()
    with np.load(CACHE_FILE) as cached:
        times = pd.DatetimeIndex(cached["time"])
        latitude = cached["lat"]
        longitude = cached["lon"]
        values = cached["h20_jm2"]
    return times, latitude, longitude, values


def detrended_calendar_anomaly(
    values: np.ndarray, times: pd.DatetimeIndex
) -> np.ndarray:
    """Remove 1980-2024 monthly climatology and same-month linear trend."""
    data = np.asarray(values, dtype=np.float64)
    result = np.full(data.shape, np.nan, dtype=np.float32)
    years = times.year.to_numpy(dtype=float)
    months = times.month.to_numpy(dtype=int)
    baseline_year = (years >= BASELINE_START) & (years <= BASELINE_END)
    for month in range(1, 13):
        target = months == month
        baseline = target & baseline_year
        baseline_values = data[baseline]
        baseline_years = years[baseline]
        center_year = float(np.mean(baseline_years))
        x = baseline_years - center_year
        finite = np.isfinite(baseline_values)
        count = finite.sum(axis=0)
        climatology = np.divide(
            np.nansum(baseline_values, axis=0),
            count,
            out=np.full(data.shape[1:], np.nan),
            where=count > 0,
        )
        centered = baseline_values - climatology[None, :, :]
        numerator = np.nansum(centered * x[:, None, None], axis=0)
        denominator = np.sum(finite * x[:, None, None] ** 2, axis=0)
        slope = np.divide(
            numerator,
            denominator,
            out=np.full(data.shape[1:], np.nan),
            where=denominator > 0,
        )
        result[target] = (
            data[target]
            - climatology[None, :, :]
            - slope[None, :, :]
            * (years[target, None, None] - center_year)
        ).astype(np.float32)
    return result


def latitude_weighted_mean(values: np.ndarray, latitude: np.ndarray) -> np.ndarray:
    weights = np.cos(np.deg2rad(latitude)).astype(float)
    finite = np.isfinite(values)
    numerator = np.nansum(values * weights[None, :, None], axis=1)
    denominator = np.sum(finite * weights[None, :, None], axis=1)
    return np.divide(
        numerator,
        denominator,
        out=np.full(numerator.shape, np.nan),
        where=denominator > 0,
    )


def event_window(year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{year - 1}-07-01", f"{year}-12-01", freq="MS") + pd.Timedelta(
        days=14
    )


def longitude_label(value: float) -> str:
    if value < 180:
        return f"{value:g}°E"
    if value == 180:
        return "180°"
    return f"{360 - value:g}°W"


def set_plot_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 300,
        }
    )


def plot(
    times: pd.DatetimeIndex,
    longitude: np.ndarray,
    zonal_anomaly: np.ndarray,
) -> tuple[Path, Path]:
    event_arrays: dict[int, np.ndarray] = {}
    pooled: list[np.ndarray] = []
    for year in EVENTS:
        indices = times.get_indexer(event_window(year))
        if np.any(indices < 0):
            raise ValueError(f"Event window unavailable: {year}")
        event_arrays[year] = zonal_anomaly[indices] / 1.0e9
        pooled.append(event_arrays[year])

    finite = np.concatenate([item[np.isfinite(item)] for item in pooled])
    raw_vmax = float(np.nanpercentile(np.abs(finite), 98))
    vmax = max(0.25, np.ceil(raw_vmax * 4.0) / 4.0)
    levels = np.linspace(-vmax, vmax, 17)
    contour_step = vmax / 3.5
    contour_levels = np.array([-2, -1, 0, 1, 2], dtype=float) * contour_step

    set_plot_style()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 7.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.86, bottom=0.24, wspace=0.12)
    mesh = None
    for ax, (year, label) in zip(axes, EVENTS.items()):
        data = event_arrays[year]
        y = np.arange(data.shape[0])
        mesh = ax.contourf(
            longitude, y, data, levels=levels, cmap="RdBu_r", extend="both"
        )
        ax.contour(
            longitude,
            y,
            data,
            levels=contour_levels,
            colors="0.25",
            linewidths=[0.45, 0.45, 0.8, 0.45, 0.45],
            alpha=0.72,
        )
        for boundary in (180, 220, 270):
            ax.axvline(boundary, color="0.2", lw=0.7, ls=":")
        ax.axhline(5.5, color="0.15", lw=0.9, ls="--")
        ax.axhline(11.5, color="0.15", lw=0.9, ls="--")
        ax.set_title(label)
        ax.set_xlabel("Longitude")
        ax.set_xlim(130, 280)
        ax.text(132, 5.65, "Jan 0", ha="left", va="bottom", fontsize=8)
        ax.text(132, 11.65, "Jul 0", ha="left", va="bottom", fontsize=8)

    reference_times = event_window(1997)
    tick_positions = np.arange(0, len(reference_times), 2)
    tick_labels = [
        f"{time:%b} {'−1' if time.year == 1996 else '0'}"
        for time in reference_times[tick_positions]
    ]
    axes[0].set_yticks(tick_positions, tick_labels)
    axes[0].set_ylabel("Month relative to development year")
    x_ticks = [130, 150, 180, 210, 240, 270, 280]
    for ax in axes:
        ax.set_xticks(x_ticks, [longitude_label(value) for value in x_ticks])
        ax.tick_params(axis="x", labelrotation=35)

    assert mesh is not None
    cax = fig.add_axes([0.20, 0.115, 0.60, 0.028])
    colorbar = fig.colorbar(mesh, cax=cax, orientation="horizontal")
    colorbar.set_label(
        r"0–300 m $H_{20}$ anomaly (GJ m$^{-2}$)"
    )
    fig.suptitle(
        r"Equatorial Pacific 20°C-threshold relative heat-content evolution",
        fontsize=14,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.032,
        "SODA3.15.2; 5°S–5°N mean; 1980–2024 calendar-month climatology and "
        "same-month linear trend removed. Vertical guides: 180°, 140°W, 90°W.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="0.25",
    )

    png = OUT_DIR / "soda3_h20_hovmoller_1997_2015_2023.png"
    pdf = OUT_DIR / "soda3_h20_hovmoller_1997_2015_2023.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    print(f"Color range: {-vmax:.3f} to {vmax:.3f} GJ m-2")
    return png, pdf


def main() -> None:
    args = parse_args()
    times, latitude, longitude, h20 = load_or_build(args.force)
    anomaly = detrended_calendar_anomaly(h20, times)
    zonal_anomaly = latitude_weighted_mean(anomaly, latitude)
    png, pdf = plot(times, longitude, zonal_anomaly)
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
