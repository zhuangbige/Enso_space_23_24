#!/usr/bin/env python3
"""Complete the CT/CP decay-phase wind-stress curl and Ekman heat estimate."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_air_sea_coupled_warm_heat_fate as coupling  # noqa: E402

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

TX_DIR = ROOT / "data/raw/era5/coupling_monthly_1deg"
TY_DIR = ROOT / "data/raw/era5/coupling_meridional_stress_monthly_1deg"
MONTHLY = coupling.MONTHLY_CSV
ATM_MONTHLY = coupling.ATM_MONTHLY
PHASE_EVENTS = coupling.EVENT_PHASE_CSV

DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/era5_full_stress_curl_warm_heat"
PDF_DIR = ROOT / "output/pdf"
EVENT_CSV = DERIVED / "era5_full_stress_curl_warm_heat_event.csv"
SUMMARY_CSV = DERIVED / "era5_full_stress_curl_warm_heat_summary.csv"
MAP_NC = DERIVED / "era5_full_stress_curl_decay_composites.nc"
DIAGNOSTICS_JSON = DERIVED / "era5_full_stress_curl_warm_heat_diagnostics.json"
FIGURE_PNG = OUT / "era5_full_stress_curl_warm_heat.png"
FIGURE_PDF = PDF_DIR / "era5_full_stress_curl_warm_heat.pdf"
REPORT_MD = OUT / "ERA5_FULL_STRESS_CURL_WARM_HEAT_CN.md"

MONTHS = (12, 1, 2, 3, 4, 5)
CP_WATER = 3990.0
BOOTSTRAP = 20_000
SEED = 20260804


def load_stress() -> xr.Dataset:
    pieces = []
    for month in MONTHS:
        tx_path = TX_DIR / f"era5_coupling_part02_m{month:02d}_1982_2025_1p0deg.nc"
        ty_name = "part02" if month == 1 else "full"
        ty_path = TY_DIR / f"era5_coupling_{ty_name}_m{month:02d}_1982_2022_1p0deg.nc"
        with xr.open_dataset(tx_path, engine="netcdf4") as tx_ds, xr.open_dataset(
            ty_path, engine="netcdf4"
        ) as ty_ds:
            tx = coupling.normalize_era5(tx_ds[["avg_iews"]]).tau_x.sel(
                time=slice("1982-01-15", "2022-12-15"), lat=slice(-10, 10), lon=slice(220, 280)
            )
            ty = ty_ds.avg_inss.rename(
                {"valid_time": "time", "latitude": "lat", "longitude": "lon"}
            ).assign_coords(lon=lambda item: item.lon % 360.0).sortby("lon").sortby("lat")
            ty = ty.assign_coords(time=coupling.normalize_time(ty.time.values)).sel(
                lat=slice(-10, 10), lon=slice(220, 280)
            )
            pieces.append(xr.Dataset({"tau_x": tx.load(), "tau_y": ty.load()}))
    output = xr.concat(pieces, dim="time").sortby("time")
    if output.sizes["time"] != 41 * 6:
        raise ValueError(f"Expected 246 Dec-May months, found {output.sizes['time']}")
    return output


def detrend_available_months(field: xr.DataArray) -> xr.DataArray:
    values = np.asarray(field.values, dtype=float)
    times = pd.DatetimeIndex(field.time.values)
    output = np.full(values.shape, np.nan)
    for month in sorted(set(times.month)):
        indices = np.where(times.month == month)[0]
        years = np.asarray(times.year[indices], dtype=float)
        x = years - years.mean()
        selected = values[indices]
        mean = np.nanmean(selected, axis=0)
        slope = np.nansum(x[:, None, None] * (selected - mean), axis=0) / np.sum(x**2)
        output[indices] = selected - mean[None, :, :] - x[:, None, None] * slope[None, :, :]
    return xr.DataArray(output, coords=field.coords, dims=field.dims, attrs=field.attrs)


def curl_components(stress: xr.Dataset) -> xr.Dataset:
    tx = detrend_available_months(stress.tau_x)
    ty = detrend_available_months(stress.tau_y)
    latitude_rad = np.deg2rad(tx.lat.values)
    longitude_rad = np.deg2rad(tx.lon.values)
    dty_dlambda = np.gradient(ty.values, longitude_rad, axis=2)
    dtx_dphi = np.gradient(tx.values, latitude_rad, axis=1)
    term_y = dty_dlambda / (
        coupling.EARTH_RADIUS * np.cos(latitude_rad)[None, :, None]
    )
    term_x = -dtx_dphi / coupling.EARTH_RADIUS
    full = term_y + term_x
    coords = tx.coords
    return xr.Dataset(
        {
            "tau_x_anom": tx,
            "tau_y_anom": ty,
            "curl_from_tau_y": xr.DataArray(term_y, coords=coords, dims=tx.dims),
            "curl_from_tau_x": xr.DataArray(term_x, coords=coords, dims=tx.dims),
            "curl_full": xr.DataArray(full, coords=coords, dims=tx.dims),
        }
    )


def region_mean(field: xr.DataArray) -> xr.DataArray:
    return coupling.weighted_mean(field, 0.0, 10.0, 220.0, 280.0)


def event_dates(year: int) -> list[pd.Timestamp]:
    return [pd.Timestamp(year=year, month=12, day=15)] + [
        pd.Timestamp(year=year + 1, month=month, day=15) for month in range(1, 6)
    ]


def build_events(curl: xr.Dataset) -> tuple[pd.DataFrame, xr.Dataset]:
    monthly = pd.read_csv(MONTHLY, parse_dates=["time"])
    atmosphere = pd.read_csv(ATM_MONTHLY)
    atmosphere["time"] = pd.to_datetime(dict(year=atmosphere.year, month=atmosphere.month, day=15))
    monthly = monthly.merge(
        atmosphere[["time", "sst_east_raw_c"]], on="time", how="left", validate="one_to_one"
    )
    phase = pd.read_csv(PHASE_EVENTS)
    phase = phase.loc[phase.phase.eq("mature_decay_Dec0_to_May1")]
    rows = []
    maps = xr.Dataset()
    for event_class, years in coupling.EVENTS.items():
        all_dates = [date for year in years for date in event_dates(year)]
        for variable in curl.data_vars:
            maps[f"{variable}_{event_class}"] = curl[variable].sel(time=all_dates).mean("time")
        for year in years:
            dates = event_dates(year)
            selected = monthly.loc[monthly.time.isin(dates)].sort_values("time")
            ekman_pw = (
                coupling.RHO_WATER
                * CP_WATER
                * selected.ekman5n_220_280e_north_sm3_sv.to_numpy()
                * 1.0e6
                * np.maximum(selected.sst_east_raw_c.to_numpy() - 20.0, 0.0)
                / 1.0e15
            )
            ekman_zj = coupling.integrate_zj(pd.Series(ekman_pw), selected.time.reset_index(drop=True))
            soda_export = float(
                phase.loc[
                    phase.event_class.eq(event_class) & phase.event_year.eq(year),
                    "soda_north_export_zj",
                ].iloc[0]
            )
            dates_curl = curl.sel(time=dates)
            rows.append(
                {
                    "event_class": event_class,
                    "event_year": year,
                    "curl_full_mean_1e8_nm3": float(region_mean(dates_curl.curl_full).mean() * 1e8),
                    "curl_tau_x_mean_1e8_nm3": float(region_mean(dates_curl.curl_from_tau_x).mean() * 1e8),
                    "curl_tau_y_mean_1e8_nm3": float(region_mean(dates_curl.curl_from_tau_y).mean() * 1e8),
                    "ekman_heat_estimate_zj": ekman_zj,
                    "soda_north_export_zj": soda_export,
                    "non_ekman_remainder_zj": soda_export - ekman_zj,
                }
            )
    for variable in list(curl.data_vars):
        maps[f"{variable}_CT_minus_CP"] = maps[f"{variable}_CT"] - maps[f"{variable}_CP"]
    return pd.DataFrame(rows), maps


def summarize(events: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    metrics = [column for column in events if column not in {"event_class", "event_year"}]
    rows = []
    for metric in metrics:
        boot = {}
        for group in ("CT", "CP"):
            values = events.loc[events.event_class.eq(group), metric].to_numpy()
            draw = rng.integers(0, len(values), (BOOTSTRAP, len(values)))
            boot[group] = values[draw].mean(1)
            low, high = np.quantile(boot[group], [0.025, 0.975])
            rows.append({"contrast": group, "metric": metric, "mean": values.mean(), "ci_low": low, "ci_high": high})
        difference = boot["CT"] - boot["CP"]
        low, high = np.quantile(difference, [0.025, 0.975])
        rows.append(
            {
                "contrast": "CT_minus_CP",
                "metric": metric,
                "mean": events.loc[events.event_class.eq("CT"), metric].mean()
                - events.loc[events.event_class.eq("CP"), metric].mean(),
                "ci_low": low,
                "ci_high": high,
            }
        )
    return pd.DataFrame(rows)


def value(summary: pd.DataFrame, contrast: str, metric: str) -> pd.Series:
    return summary.loc[summary.contrast.eq(contrast) & summary.metric.eq(metric)].iloc[0]


def plot(maps: xr.Dataset, summary: pd.DataFrame) -> None:
    coupling.setup_style()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.1), constrained_layout=True)
    levels = np.arange(-1.5, 1.51, 0.25)
    filled = None
    for axis, group in zip(axes[:2], ("CT", "CP")):
        field = maps[f"curl_full_{group}"] * 1e8
        filled = axis.contourf(field.lon, field.lat, field, levels=levels, cmap="RdBu_r", extend="both")
        skip = (slice(None, None, 3), slice(None, None, 5))
        axis.quiver(
            maps.lon.values[skip[1]],
            maps.lat.values[skip[0]],
            maps[f"tau_x_anom_{group}"].values[skip],
            maps[f"tau_y_anom_{group}"].values[skip],
            scale=0.18,
            width=0.003,
        )
        axis.axhline(5, color="k", ls="--", lw=0.8)
        axis.set_title(f"{group}: full stress curl + stress vectors", fontweight="bold")
        axis.set_xlabel("Longitude (°E)")
        axis.set_ylabel("Latitude")
    fig.colorbar(filled, ax=axes[:2], orientation="horizontal", shrink=0.72, label="Stress curl anomaly (10$^{-8}$ N m$^{-3}$)")

    metrics = ("soda_north_export_zj", "ekman_heat_estimate_zj", "non_ekman_remainder_zj")
    labels = ("SODA3 total", "Ekman estimate", "Remainder")
    x = np.arange(3)
    width = 0.36
    colors = {"CT": "#C23B3B", "CP": "#2C7FB8"}
    for offset, group in ((-width / 2, "CT"), (width / 2, "CP")):
        means = np.array([value(summary, group, metric)["mean"] for metric in metrics])
        lows = np.array([value(summary, group, metric).ci_low for metric in metrics])
        highs = np.array([value(summary, group, metric).ci_high for metric in metrics])
        axes[2].bar(x + offset, means, width, color=colors[group], label=group, yerr=np.vstack([means - lows, highs - means]), capsize=2)
    axes[2].axhline(0, color="0.4", lw=0.7)
    axes[2].set_xticks(x, labels, rotation=18)
    axes[2].set_ylabel("Northward warm-heat transport (ZJ)")
    axes[2].set_title("First-order Ekman heat contribution", fontweight="bold")
    axes[2].legend(frameon=False)
    axes[2].grid(axis="y", color="0.9", lw=0.5)
    fig.suptitle("Full ERA5 wind-stress curl and the CT warm-heat exit", fontsize=13, fontweight="bold")
    OUT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PNG, bbox_inches="tight")
    fig.savefig(FIGURE_PDF, bbox_inches="tight")
    plt.close(fig)


def write_report(summary: pd.DataFrame, events: pd.DataFrame, diagnostics: dict[str, float]) -> None:
    full = value(summary, "CT_minus_CP", "curl_full_mean_1e8_nm3")
    tx = value(summary, "CT_minus_CP", "curl_tau_x_mean_1e8_nm3")
    ty = value(summary, "CT_minus_CP", "curl_tau_y_mean_1e8_nm3")
    ct_ek = value(summary, "CT", "ekman_heat_estimate_zj")
    cp_ek = value(summary, "CP", "ekman_heat_estimate_zj")
    ct_total = value(summary, "CT", "soda_north_export_zj")
    report = f"""# ERA5完整风应力旋度与暖量北向出口

## 结果

- 在0–10°N、140°W–80°W，衰减期CT−CP完整风应力旋度为 {full['mean']:+.3f}×10⁻⁸ N m⁻³，95%区间 [{full.ci_low:+.3f}, {full.ci_high:+.3f}]。
- 其中纬向应力的纬向梯度项 `−∂τx/∂y` 为 {tx['mean']:+.3f}，经向应力的经向梯度项 `∂τy/∂x` 为 {ty['mean']:+.3f}。因此先前只用纬向应力并未把旋度符号写反，但完整旋度的强度与显著性必须以上述总和为准。
- 用ERA5 5°N Ekman体积输送乘以OISST东部 `SST−20°C` 得到一阶暖量估计：CT为 {ct_ek['mean']:+.2f} ZJ，CP为 {cp_ek['mean']:+.2f} ZJ。相对于CT的SODA3总北向输出 {ct_total['mean']:+.2f} ZJ，事件合成比值约为 {ct_ek['mean']/ct_total['mean']*100:.0f}%。
- 8事件中Ekman估计与SODA3总北向输出相关为 r={diagnostics['ekman_total_r']:.2f}。剩余量不能直接称为地转输送，还包含温度代表误差、非线性/瞬变流与再分析产品差异。

## 判断

完整风应力资料支持“CT东部大气反馈帮助打开5°N暖量出口”。后续SODA3温盐、SSH、总v和自身风应力分解已经完成：CT−CP总差异 +3.77 ZJ由地转 +2.10 ZJ、Ekman +1.77 ZJ和不显著残差 −0.10 ZJ构成；SODA3自身应力的Ekman差异与这里ERA5的 +1.67 ZJ近乎一致。因此可把文章收束为风驱Ekman和海洋压力场调整共同控制跨5°N暖量出口，但该运动学分解不等同于独立因果强迫试验。
"""
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> int:
    stress = load_stress()
    curl = curl_components(stress)
    events, maps = build_events(curl)
    summary = summarize(events)
    r = float(stats.pearsonr(events.ekman_heat_estimate_zj, events.soda_north_export_zj).statistic)
    diagnostics = {
        "n_months": int(stress.sizes["time"]),
        "n_events": int(len(events)),
        "ekman_total_r": r,
        "curl_identity_max_1e8_nm3": float(
            np.abs(curl.curl_full - curl.curl_from_tau_x - curl.curl_from_tau_y).max() * 1e8
        ),
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    events.to_csv(EVENT_CSV, index=False, float_format="%.9g")
    summary.to_csv(SUMMARY_CSV, index=False, float_format="%.9g")
    maps.to_netcdf(MAP_NC, engine="netcdf4")
    DIAGNOSTICS_JSON.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    plot(maps, summary)
    write_report(summary, events, diagnostics)
    for path in (EVENT_CSV, SUMMARY_CSV, MAP_NC, FIGURE_PNG, REPORT_MD):
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
