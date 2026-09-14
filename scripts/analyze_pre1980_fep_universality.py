#!/usr/bin/env python3
"""Test whether Jiang pre-1980 FEP-dominant events resemble 2023 or 1997.

Inputs follow Jiang et al. (2026): ERSSTv5 SST, ERA5 925-hPa winds and
precipitation, and ORAS5 D20, all referenced to 1960--2024 with the linear
trend removed.  The analysis retains the four Jiang pre-1980 cases
(1965/66, 1969/70, 1972/73, 1976/77) individually, then compares their
composite with 1997/98 and 2023/24.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived" / "research_2026"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs" / "research_2026" / "pre1980_fep_universality"
PDF_OUT = ROOT / "output" / "pdf" / "pre1980_fep_vs_1997_2023_universality.pdf"

ERSST = RAW / "ersstv5_sst_monthly_full.nc"
ORAS5 = ROOT / "data" / "interim" / "research_2026" / "oras5_d20_timeseries_equatorial_1960_202606.csv"
ERA5 = RAW / "era5" / "pre1980_fep_mjj_1deg"

BASELINE_START = 1960
BASELINE_END = 2024
MONTHS = (5, 6, 7)
PRE1980 = (1965, 1969, 1972, 1976)
REFERENCES = (1997, 2023)
EVENTS = (*PRE1980, *REFERENCES)
LABELS = OrderedDict(
    [
        (1965, "1965/66"),
        (1969, "1969/70"),
        (1972, "1972/73"),
        (1976, "1976/77"),
        (1997, "1997/98"),
        (2023, "2023/24"),
    ]
)
COLORS = {
    1965: "#8CB9BD",
    1969: "#6FA6AD",
    1972: "#4F8B94",
    1976: "#2E6E78",
    1997: "#C23B2A",
    2023: "#355C9A",
}


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.0,
            "axes.titlesize": 10.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.2,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 8.0,
            "figure.dpi": 180,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def normalize_field(field: xr.DataArray) -> xr.DataArray:
    rename = {}
    if "valid_time" in field.coords:
        rename["valid_time"] = "time"
    if "latitude" in field.coords:
        rename["latitude"] = "lat"
    if "longitude" in field.coords:
        rename["longitude"] = "lon"
    field = field.rename(rename)
    if "pressure_level" in field.dims and field.sizes["pressure_level"] == 1:
        field = field.isel(pressure_level=0, drop=True)
    field = field.assign_coords(lon=field["lon"] % 360.0)
    return field.sortby("lat").sortby("lon")


def detrend_anomaly(field: xr.DataArray) -> xr.DataArray:
    """Remove calendar-month climatology and one linear trend over 1960-2024."""
    field = field.sel(time=slice(f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-31"))
    climatology = field.groupby("time.month").mean("time", skipna=True)
    anomaly = field.groupby("time.month") - climatology
    decimal_year = (
        anomaly["time"].dt.year.astype(float)
        + (anomaly["time"].dt.month.astype(float) - 1.0) / 12.0
    )
    centered = decimal_year - decimal_year.mean("time")
    slope = (anomaly * centered).sum("time", skipna=True) / (centered**2).sum("time")
    return anomaly - slope * centered


def weighted_box(
    field: xr.DataArray,
    lon0: float,
    lon1: float,
    lat0: float = -5.0,
    lat1: float = 5.0,
) -> xr.DataArray:
    subset = field.sel(lon=slice(lon0, lon1), lat=slice(lat0, lat1))
    if subset.sizes.get("lat", 0) == 0 or subset.sizes.get("lon", 0) == 0:
        raise ValueError(f"empty region lon={lon0}:{lon1}, lat={lat0}:{lat1}")
    weights = np.cos(np.deg2rad(subset["lat"]))
    return subset.weighted(weights).mean(("lat", "lon"), skipna=True)


def annual_mjj(series: xr.DataArray, name: str) -> pd.DataFrame:
    values = series.where(series["time"].dt.month.isin(MONTHS), drop=True)
    annual = values.groupby("time.year").mean("time", skipna=True).to_series()
    annual.index = annual.index.astype(int)
    return pd.DataFrame({"year": annual.index, name: annual.values})


def load_sst() -> tuple[xr.DataArray, pd.DataFrame]:
    with xr.open_dataset(ERSST, engine="netcdf4") as ds:
        raw = normalize_field(ds["sst"]).sel(
            time=slice(f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-01")
        ).load()
    dt = detrend_anomaly(raw)
    fep = weighted_box(dt, 270, 280)
    n34 = weighted_box(dt, 190, 240)
    n4 = weighted_box(dt, 160, 210)
    x = n34.values.astype(float)
    y = fep.values.astype(float)
    valid = np.isfinite(x) & np.isfinite(y)
    beta = float(np.sum(x[valid] * y[valid]) / np.sum(x[valid] ** 2))
    expected = beta * n34
    residual = fep - expected

    indices = annual_mjj(fep, "fep_total_c")
    for series, name in [
        (n34, "nino34_c"),
        (n4, "nino4_c"),
        (expected, "fep_nino34_component_c"),
        (residual, "fep_residual_c"),
    ]:
        indices = indices.merge(annual_mjj(series, name), on="year", validate="one_to_one")
    indices.attrs["fep_beta"] = beta
    return dt, indices


def load_era5() -> tuple[dict[str, xr.DataArray], pd.DataFrame]:
    pressure_parts = []
    surface_parts: dict[str, list[xr.DataArray]] = {"tp": [], "msl": [], "avg_iews": []}
    for month in MONTHS:
        pressure_path = ERA5 / f"era5_pressure925_m{month:02d}_1960_2024_1deg.nc"
        with xr.open_dataset(pressure_path, engine="netcdf4") as ds:
            pressure_parts.append(
                xr.Dataset(
                    {
                        "u925": normalize_field(ds["u"]).load(),
                        "v925": normalize_field(ds["v"]).load(),
                    }
                )
            )
        surface_dir = ERA5 / f"era5_surface_m{month:02d}_1960_2024_1deg"
        for path in sorted(surface_dir.glob("*.nc")):
            with xr.open_dataset(path, engine="netcdf4") as ds:
                for name in surface_parts:
                    if name in ds:
                        surface_parts[name].append(normalize_field(ds[name]).load())

    pressure = xr.concat(pressure_parts, dim="time").sortby("time")
    fields = {
        "u925": detrend_anomaly(pressure["u925"]),
        "v925": detrend_anomaly(pressure["v925"]),
    }
    for name, parts in surface_parts.items():
        if len(parts) != len(MONTHS):
            raise RuntimeError(f"missing ERA5 {name}: found {len(parts)} monthly parts")
        fields[name] = detrend_anomaly(xr.concat(parts, dim="time").sortby("time"))
    fields["tp"] = fields["tp"] * 1000.0
    fields["tp"].attrs["units"] = "mm day-1"
    fields["msl"] = fields["msl"] / 100.0
    fields["msl"].attrs["units"] = "hPa"

    u_n4 = weighted_box(fields["u925"], 160, 210)
    ne_u = weighted_box(fields["u925"], 180, 230, 3, 7)
    ne_v = weighted_box(fields["v925"], 180, 230, 3, 7)
    ne_index = -(ne_u + ne_v) / np.sqrt(2.0)
    rain_eq = weighted_box(fields["tp"], 180, 230, -5, 5)
    rain_north = weighted_box(fields["tp"], 180, 230, 6, 10)
    rain_dipole = rain_eq - rain_north
    slp_west = weighted_box(fields["msl"], 130, 160)
    slp_east = weighted_box(fields["msl"], 220, 250)
    slp_drive = slp_west - slp_east
    tau = weighted_box(fields["avg_iews"], 160, 220)

    indices = annual_mjj(u_n4, "u925_nino4_ms")
    for series, name in [
        (ne_u, "u925_ne_box_ms"),
        (ne_v, "v925_ne_box_ms"),
        (ne_index, "northeasterly_index_ms"),
        (rain_eq, "precip_equatorial_mmday"),
        (rain_north, "precip_north_mmday"),
        (rain_dipole, "precip_meridional_dipole_mmday"),
        (slp_drive, "slp_drive_w_minus_e_hpa"),
        (tau, "tau_central_nm2"),
    ]:
        indices = indices.merge(annual_mjj(series, name), on="year", validate="one_to_one")
    return fields, indices


def load_d20() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(ORAS5, parse_dates=["time"])
    raw = raw[
        raw["year"].between(BASELINE_START, BASELINE_END)
        & raw["requested_lon"].between(135, 275)
    ].copy()
    raw["lon"] = raw["requested_lon"].astype(float)
    pieces = []
    for lon, group in raw.groupby("lon"):
        group = group.sort_values("time").copy()
        climatology = group.groupby("month")["d20_m"].transform("mean")
        anomaly = group["d20_m"] - climatology
        decimal_year = group["year"] + (group["month"] - 1.0) / 12.0
        centered = decimal_year - decimal_year.mean()
        good = np.isfinite(anomaly.to_numpy())
        slope = np.polyfit(centered.to_numpy()[good], anomaly.to_numpy()[good], 1)[0]
        group["d20_anomaly_m"] = anomaly - slope * centered
        pieces.append(group)
    dt = pd.concat(pieces, ignore_index=True)
    mjj = dt[dt["month"].isin(MONTHS)].copy()
    profile = mjj.groupby(["year", "lon"], as_index=False)["d20_anomaly_m"].mean()

    def region_mean(frame: pd.DataFrame, lon0: float, lon1: float) -> float:
        subset = frame[frame["lon"].between(lon0, lon1)]
        return float(subset["d20_anomaly_m"].mean())

    rows = []
    for year, frame in profile.groupby("year"):
        west = region_mean(frame, 140, 190)
        central = region_mean(frame, 190, 240)
        east = region_mean(frame, 240, 275)
        fep = region_mean(frame, 270, 275)
        rows.append(
            {
                "year": int(year),
                "d20_west_m": west,
                "d20_central_m": central,
                "d20_east_m": east,
                "d20_fep_m": fep,
                "d20_east_minus_west_m": east - west,
                "d20_fep_minus_central_m": fep - central,
            }
        )
    return profile, pd.DataFrame(rows)


def add_regression_residuals(all_years: pd.DataFrame) -> pd.DataFrame:
    out = all_years.copy()
    for response, prefix in [
        ("u925_nino4_ms", "u925"),
        ("tau_central_nm2", "tau"),
    ]:
        valid = out[["nino34_c", response]].dropna()
        x = valid["nino34_c"].to_numpy()
        y = valid[response].to_numpy()
        slope = float(np.sum(x * y) / np.sum(x**2))
        out[f"{prefix}_expected_from_nino34"] = slope * out["nino34_c"]
        out[f"{prefix}_residual_from_nino34"] = (
            out[response] - out[f"{prefix}_expected_from_nino34"]
        )
        out.attrs[f"{prefix}_slope"] = slope
    return out


def build_event_table(
    sst_indices: pd.DataFrame,
    era_indices: pd.DataFrame,
    d20_indices: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_years = sst_indices.merge(era_indices, on="year", validate="one_to_one").merge(
        d20_indices, on="year", validate="one_to_one"
    )
    all_years = add_regression_residuals(all_years)
    # The selected-event list is taken directly from Jiang et al.  Their
    # threshold is not reclassified here because tiny differences in the
    # standard-deviation sample change the borderline status of 1997.
    events = all_years[all_years["year"].isin(EVENTS)].copy()
    events["event"] = events["year"].map(LABELS)
    events["jiang_fep_dominant"] = events["year"].isin((*PRE1980, 2023))
    events["east_thermocline_gate"] = events["d20_east_minus_west_m"] > 0
    events["weak_wind_for_sst"] = events["u925_residual_from_nino34"] < 0
    events["fep_atmospheric_signature"] = (
        (events["northeasterly_index_ms"] > 0)
        & (events["precip_meridional_dipole_mmday"] > 0)
    )
    events["complete_2023_like_chain"] = (
        events["east_thermocline_gate"]
        & events["weak_wind_for_sst"]
        & events["fep_atmospheric_signature"]
    )
    return all_years, events.sort_values("year")


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.10, 1.06, label, transform=ax.transAxes, fontweight="bold", fontsize=11)


def plot_page1(
    all_years: pd.DataFrame,
    events: pd.DataFrame,
    d20_profile: pd.DataFrame,
) -> plt.Figure:
    fig, axes = plt.subplots(3, 2, figsize=(13.2, 14.0))
    fig.subplots_adjust(left=0.075, right=0.955, top=0.91, bottom=0.075, hspace=0.40, wspace=0.27)
    ax = axes[0, 0]
    x = np.arange(len(events))
    width = 0.36
    ax.bar(x - width / 2, events["fep_nino34_component_c"], width, color="#D98F58", label="Niño3.4-related FEP")
    ax.bar(x + width / 2, events["fep_residual_c"], width, color="#2D7B87", label="Residual FEP")
    ax.axhline(0, color="#4d5966", linewidth=0.8)
    ax.set_xticks(x, events["event"], rotation=20)
    ax.set_ylabel("MJJ FEP contribution (°C)")
    ax.set_title("Jiang decomposition: local residual versus canonical ENSO contribution")
    ax.legend(frameon=False, ncol=2)
    ax.grid(axis="y", color="#d8dde3", linewidth=0.6)
    add_panel_label(ax, "a")

    ax = axes[0, 1]
    ax.scatter(all_years["nino34_c"], all_years["u925_nino4_ms"], s=18, color="#b8bec5", alpha=0.65, label="All years, 1960–2024")
    slope = all_years.attrs["u925_slope"]
    xx = np.linspace(all_years["nino34_c"].min(), all_years["nino34_c"].max(), 100)
    ax.plot(xx, slope * xx, color="#30363d", linewidth=1.4, label="All-year expectation")
    for _, row in events.iterrows():
        year = int(row["year"])
        ax.scatter(row["nino34_c"], row["u925_nino4_ms"], s=70, color=COLORS[year], edgecolor="white", linewidth=0.8, zorder=5)
        ax.annotate(str(year), (row["nino34_c"], row["u925_nino4_ms"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.axhline(0, color="#65717c", linewidth=0.7)
    ax.axvline(0, color="#65717c", linewidth=0.7)
    ax.set_xlabel("MJJ Niño3.4 SST anomaly (°C)")
    ax.set_ylabel("MJJ Niño4 u925 anomaly (m s$^{-1}$)")
    ax.set_title("Central-Pacific wind response relative to SST forcing")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(color="#d8dde3", linewidth=0.6)
    add_panel_label(ax, "b")

    ax = axes[1, 0]
    for year in EVENTS:
        sub = d20_profile[d20_profile["year"] == year].sort_values("lon")
        linewidth = 2.4 if year in REFERENCES else 1.2
        alpha = 1.0 if year in REFERENCES else 0.72
        ax.plot(sub["lon"], sub["d20_anomaly_m"], color=COLORS[year], linewidth=linewidth, alpha=alpha, label=LABELS[year])
    ax.axhline(0, color="#4d5966", linewidth=0.8)
    ax.axvline(220, color="#666", linestyle=":", linewidth=0.9)
    ax.axvspan(270, 275, color="#F1D36B", alpha=0.24)
    ax.set_xticks([140, 180, 220, 260, 275], ["140°E", "180°", "140°W", "100°W", "85°W"])
    ax.set_ylabel("MJJ ORAS5 D20 anomaly (m)")
    ax.set_title("Thermocline structure: local FEP route versus basin-scale tilt")
    ax.legend(frameon=False, ncol=3)
    ax.grid(color="#d8dde3", linewidth=0.6)
    add_panel_label(ax, "c")

    ax = axes[1, 1]
    metrics = [
        ("u925_residual_from_nino34", "Wind residual\n(m s$^{-1}$)", 1.0),
        ("tau_residual_from_nino34", "100× stress residual\n(N m$^{-2}$)", 100.0),
    ]
    for i, (column, label, scale) in enumerate(metrics):
        positions = x + (i - 0.5) * 0.32
        ax.bar(positions, events[column] * scale, 0.30, color=[COLORS[int(y)] for y in events["year"]], alpha=1.0 if i == 0 else 0.55, edgecolor="white", label=label)
    ax.axhline(0, color="#30363d", linewidth=0.9)
    ax.set_xticks(x, events["event"], rotation=20)
    ax.set_ylabel("Observed minus Niño3.4-conditioned expectation")
    ax.set_title("Negative residual = weaker central coupling than SST implies")
    ax.legend(frameon=False, ncol=2)
    ax.grid(axis="y", color="#d8dde3", linewidth=0.6)
    add_panel_label(ax, "d")

    ax = axes[2, 0]
    ax2 = ax.twinx()
    ax.bar(x - 0.18, events["precip_meridional_dipole_mmday"], 0.36, color=[COLORS[int(y)] for y in events["year"]], alpha=0.72, label="Rain: equator minus 6–10°N")
    ax2.bar(x + 0.18, events["northeasterly_index_ms"], 0.36, color=[COLORS[int(y)] for y in events["year"]], alpha=1.0, hatch="//", label="Northeasterly index")
    ax.axhline(0, color="#4d5966", linewidth=0.8)
    ax2.axhline(0, color="#4d5966", linewidth=0.8)
    ax.set_xticks(x, events["event"], rotation=20)
    ax.set_ylabel("Precipitation dipole (mm day$^{-1}$)")
    ax2.set_ylabel("Northeasterly index (m s$^{-1}$)")
    ax.set_title("Jiang atmospheric bridge: meridional rain dipole and NE winds")
    handles = [
        mpl.patches.Patch(facecolor="#8798A8", alpha=0.72, label="Rain dipole"),
        mpl.patches.Patch(facecolor="#8798A8", hatch="//", label="NE wind index"),
    ]
    ax.legend(handles=handles, frameon=False, ncol=2)
    ax.grid(axis="y", color="#d8dde3", linewidth=0.6)
    add_panel_label(ax, "e")

    ax = axes[2, 1]
    heat_cols = [
        "fep_residual_c",
        "d20_fep_minus_central_m",
        "u925_residual_from_nino34",
        "northeasterly_index_ms",
        "precip_meridional_dipole_mmday",
        "tau_residual_from_nino34",
    ]
    labels = ["Residual FEP", "FEP−central D20", "Wind residual", "NE wind", "Rain dipole", "Stress residual"]
    z = []
    for col in heat_cols:
        mu = all_years[col].mean()
        sd = all_years[col].std(ddof=1)
        z.append((events[col].to_numpy() - mu) / sd)
    matrix = np.column_stack(z)
    im = ax.imshow(matrix, cmap="RdBu_r", vmin=-2.5, vmax=2.5, aspect="auto")
    ax.set_xticks(range(len(labels)), labels, rotation=32, ha="right")
    ax.set_yticks(range(len(events)), events["event"])
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:+.1f}", ha="center", va="center", fontsize=7.5, color="white" if abs(matrix[i, j]) > 1.25 else "#20262d")
    ax.set_title("Cross-event standardized diagnostic matrix")
    cbar = fig.colorbar(im, ax=ax, fraction=0.047, pad=0.03)
    cbar.set_label("Standard deviation")
    add_panel_label(ax, "f")

    fig.suptitle(
        "Are pre-1980 FEP-dominant El Niño events a general analogue of 2023—or of 1997?",
        fontsize=15.0,
        fontweight="bold",
        y=0.972,
    )
    fig.text(
        0.075,
        0.025,
        "MJJ detrended anomalies; 1960–2024 calendar-month climatology. Positive NE index denotes anomalous northeasterlies. "
        "The four pre-1980 cases follow Jiang et al. (2026). Sources: ERSSTv5, ERA5, ORAS5.",
        fontsize=8.2,
        color="#4d5966",
    )
    return fig


def composite_field(field: xr.DataArray, years: tuple[int, ...]) -> xr.DataArray:
    selected = field.where(
        field["time"].dt.year.isin(years) & field["time"].dt.month.isin(MONTHS),
        drop=True,
    )
    return selected.mean("time", skipna=True)


def plot_page2(sst: xr.DataArray, fields: dict[str, xr.DataArray]) -> plt.Figure:
    cases = [
        ("Pre-1980 FEP composite", PRE1980),
        ("1997/98", (1997,)),
        ("2023/24", (2023,)),
    ]
    projection = ccrs.PlateCarree(central_longitude=180)
    fig, axes = plt.subplots(2, 3, figsize=(14.0, 5.8), subplot_kw={"projection": projection})
    fig.subplots_adjust(left=0.045, right=0.96, top=0.82, bottom=0.25, hspace=0.25, wspace=0.08)
    sst_levels = np.arange(-1.8, 1.81, 0.2)
    rain_levels = np.arange(-3.0, 3.01, 0.3)
    sst_map = None
    rain_map = None
    for j, (title, years) in enumerate(cases):
        sst_case = composite_field(sst, years)
        u_case = composite_field(fields["u925"], years)
        v_case = composite_field(fields["v925"], years)
        rain_case = composite_field(fields["tp"], years)
        for row, (shade, levels, cmap) in enumerate(
            [(sst_case, sst_levels, "RdBu_r"), (rain_case, rain_levels, "BrBG")]
        ):
            ax = axes[row, j]
            mappable = ax.contourf(
                shade["lon"], shade["lat"], shade, levels=levels, cmap=cmap,
                extend="both", transform=ccrs.PlateCarree()
            )
            if row == 0:
                sst_map = mappable
            else:
                rain_map = mappable
            ax.coastlines(resolution="110m", linewidth=0.55, color="#263238")
            ax.set_extent([120, 280, -15, 15], crs=ccrs.PlateCarree())
            ax.set_xticks([120, 160, 200, 240, 280], crs=ccrs.PlateCarree())
            ax.set_xticklabels(["120°E", "160°E", "160°W", "120°W", "80°W"])
            ax.set_yticks([-15, 0, 15], crs=ccrs.PlateCarree())
            ax.set_yticklabels(["15°S", "Eq", "15°N"] if j == 0 else [])
            ax.gridlines(
                crs=ccrs.PlateCarree(), xlocs=[120, 160, 200, 240, 280], ylocs=[-15, 0, 15],
                color="#66717c", linewidth=0.35, alpha=0.35, linestyle=":"
            )
            ix = np.arange(0, len(u_case["lon"]), 10)
            iy = np.arange(0, len(u_case["lat"]), 3)
            q = ax.quiver(
                u_case["lon"].values[ix][None, :].repeat(len(iy), axis=0),
                u_case["lat"].values[iy][:, None].repeat(len(ix), axis=1),
                u_case.values[np.ix_(iy, ix)],
                v_case.values[np.ix_(iy, ix)],
                color="#18232d", width=0.0024, headwidth=3.3, headlength=4.0,
                scale=42, transform=ccrs.PlateCarree(), zorder=5
            )
            if row == 0:
                ax.set_title(title)
                ax.quiverkey(q, 0.86, -0.16, 2, "2 m s$^{-1}$", coordinates="axes", labelpos="E")
            if j == 0:
                ax.text(-0.12, 0.5, "SST anomaly" if row == 0 else "Precipitation anomaly", transform=ax.transAxes, rotation=90, ha="center", va="center", fontweight="bold")

    cax1 = fig.add_axes([0.17, 0.105, 0.29, 0.022])
    cb1 = fig.colorbar(sst_map, cax=cax1, orientation="horizontal")
    cb1.ax.set_title("ERSSTv5 SST anomaly (°C)", fontsize=9.2, pad=5)
    cax2 = fig.add_axes([0.57, 0.105, 0.29, 0.022])
    cb2 = fig.colorbar(rain_map, cax=cax2, orientation="horizontal")
    cb2.ax.set_title("ERA5 precipitation anomaly (mm day$^{-1}$)", fontsize=9.2, pad=5)
    fig.suptitle(
        "MJJ spatial patterns: the pre-1980 composite shares the 2023 eastern-centered route, but coupling varies by event",
        fontsize=14.0,
        fontweight="bold",
        y=0.955,
    )
    fig.text(
        0.5,
        0.022,
        "Shading: detrended 1960–2024 anomalies. Vectors: ERA5 925-hPa wind anomalies. Identical scales are used across cases.",
        ha="center",
        fontsize=8.3,
        color="#4d5966",
    )
    return fig


def write_report(events: pd.DataFrame, all_years: pd.DataFrame) -> Path:
    early = events[events["year"].isin(PRE1980)]
    n_weak = int(early["weak_wind_for_sst"].sum())
    n_atm = int(early["fep_atmospheric_signature"].sum())
    n_chain = int(early["complete_2023_like_chain"].sum())
    comp = early.mean(numeric_only=True)
    r97 = events[events["year"] == 1997].iloc[0]
    r23 = events[events["year"] == 2023].iloc[0]
    lines = [
        "# 1980年前FEP主导事件与1997、2023的可推广性检验",
        "",
        "## 结论",
        "",
        "在空间演变和合成平均上，四次Jiang早期事件更接近2023的FEP局地发展路径，而不是1997的经典盆地尺度Bjerknes闭环。",
        "但逐事件只有一半完整复现‘FEP局地温跃层—降水偶极—东北风—弱中央西风’链，因此这是一条可重复出现的路径，不是严格普适定律。",
        "",
        "## 逐事件共同性",
        "",
        f"- {n_weak}/4次早期事件的Niño4 u925低于同等Niño3.4条件下的历史期望。",
        f"- {n_atm}/4次同时具有正的经向降水偶极和东北风指数。",
        f"- {n_chain}/4次同时满足东部D20结构、弱中央风响应和Jiang大气桥三项符号条件。",
        "- 其中1969/70和1972/73完整满足；1976/77具有降水偶极和东北风，但中央风只接近历史期望；1965/66的中央西风明显强于期望。",
        "- 由于样本只有4次，任何比例都只能称为一致性证据，不能单独给出显著的普适阈值。",
        "",
        "## 与1997和2023的区别",
        "",
        f"- 早期四事件合成的D20东减西为{comp['d20_east_minus_west_m']:+.1f} m，2023为{r23['d20_east_minus_west_m']:+.1f} m，1997为{r97['d20_east_minus_west_m']:+.1f} m。",
        f"- 早期合成的FEP减中太平洋D20为{comp['d20_fep_minus_central_m']:+.1f} m，2023为{r23['d20_fep_minus_central_m']:+.1f} m，1997为{r97['d20_fep_minus_central_m']:+.1f} m。该单一差值不能区分路径，必须结合整个D20剖面和风响应。",
        f"- 早期合成u925风残差为{comp['u925_residual_from_nino34']:+.2f} m s⁻¹；2023为{r23['u925_residual_from_nino34']:+.2f} m s⁻¹；1997为{r97['u925_residual_from_nino34']:+.2f} m s⁻¹。",
        f"- 早期合成东北风指数为{comp['northeasterly_index_ms']:+.2f} m s⁻¹，2023为{r23['northeasterly_index_ms']:+.2f} m s⁻¹，1997为{r97['northeasterly_index_ms']:+.2f} m s⁻¹。",
        "",
        "## 对原两门槛假说的修正",
        "",
        "1997代表经典路径：较盆地尺度的温跃层调整与中太平洋西风/对流反馈迅速接通。",
        "Jiang四事件合成和2023揭示另一条FEP路径：局地FEP温跃层敏感性和沿岸/远东升温更重要，相关经向降水偶极与东北风可抵消中央西风；但这项抵消在单个早期事件中的强度并不固定。",
        "因此，两门槛框架只能推广为‘海洋结构必须与相应的大气响应匹配’，不能把‘必须形成1997式强中央西风’当作所有FEP事件的必要条件。",
        "",
        "## 数据边界",
        "",
        "SODA3从1980年开始，无法覆盖四次早期事件。本检验用ORAS5 D20评估地下结构，不能直接比较SODA3总OHC库存或五日暖量释放。ERA5早期资料受观测稀疏影响，逐事件结论应以合成和符号一致性为主。",
    ]
    path = OUT / "PRE1980_FEP_UNIVERSALITY_RESULT_CN.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_OUT.parent.mkdir(parents=True, exist_ok=True)
    sst, sst_indices = load_sst()
    fields, era_indices = load_era5()
    d20_profile, d20_indices = load_d20()
    all_years, events = build_event_table(sst_indices, era_indices, d20_indices)

    all_years.to_csv(DERIVED / "pre1980_fep_all_year_mjj_diagnostics_1960_2024.csv", index=False)
    events.to_csv(DERIVED / "pre1980_fep_vs_1997_2023_event_diagnostics.csv", index=False)
    d20_profile[d20_profile["year"].isin(EVENTS)].to_csv(
        DERIVED / "pre1980_fep_vs_1997_2023_d20_profiles_mjj.csv", index=False
    )
    report = write_report(events, all_years)

    fig1 = plot_page1(all_years, events, d20_profile)
    fig2 = plot_page2(sst, fields)
    with PdfPages(PDF_OUT) as pdf:
        pdf.savefig(fig1, bbox_inches="tight", facecolor="white")
        pdf.savefig(fig2, bbox_inches="tight", facecolor="white")
    png1 = OUT / "pre1980_fep_event_metrics.png"
    png2 = OUT / "pre1980_fep_spatial_comparison.png"
    fig1.savefig(png1, bbox_inches="tight", facecolor="white")
    fig2.savefig(png2, bbox_inches="tight", facecolor="white")
    plt.close(fig1)
    plt.close(fig2)

    print(events.round(3).to_string(index=False))
    print(PDF_OUT)
    print(png1)
    print(png2)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
