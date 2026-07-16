#!/usr/bin/env python3
"""Plot Jiang et al. (2026) Fig. 4-style extension using the same source data.

Same-source choices:
- ERSSTv5 for Niño3.4 and far eastern Pacific SST residuals.
- ORAS5 `depth_of_20_c_isotherm` for thermocline depth (D20).

The figure is an extension, not a pixel reproduction: the lead-lag window and
D20 smoothing are trailing windows so that the final plotted year can reach the
latest available month, currently 2026-05.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
OUT_FIG = ROOT / "outputs/research_2026/figures"
OUT_DERIVED = ROOT / "data/derived/research_2026"
OUT_INTERIM = ROOT / "data/interim/research_2026"

ERSST_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc"
ORAS5_TRANSECT = OUT_INTERIM / "oras5_d20_timeseries_equatorial_1960_202605.csv"

BASELINE_START = 1960
BASELINE_END = 2024
LATEST_LABEL = "2026-05"


@dataclass(frozen=True)
class Region:
    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


NINO34 = Region("nino34", -5, 5, 190, 240)  # 170W-120W
FEP = Region("fep", -5, 5, 270, 280)  # 90W-80W


def _area_mean_sst(sst: xr.DataArray, region: Region) -> pd.Series:
    lat_values = sst["lat"].values
    lat_slice = (
        slice(region.lat_min, region.lat_max)
        if lat_values[0] < lat_values[-1]
        else slice(region.lat_max, region.lat_min)
    )
    subset = sst.sel(lat=lat_slice, lon=slice(region.lon_min, region.lon_max))
    weights = np.cos(np.deg2rad(subset["lat"]))
    mean = subset.weighted(weights).mean(("lat", "lon"), skipna=True)
    series = mean.to_series()
    series.index = pd.to_datetime(series.index)
    return series


def _monthly_anomaly(series: pd.Series, start: int = BASELINE_START, end: int = BASELINE_END) -> pd.Series:
    df = pd.DataFrame({"value": series}).dropna()
    years = df.index.year
    months = df.index.month
    clim = df.loc[(years >= start) & (years <= end)].groupby(months[(years >= start) & (years <= end)])[
        "value"
    ].mean()
    return df["value"] - months.map(clim).to_numpy()


def _remove_linear_trend(series: pd.Series, start: int = BASELINE_START, end: int = BASELINE_END) -> pd.Series:
    out = series.copy()
    years = out.index.year + (out.index.month - 0.5) / 12.0
    fit_mask = (out.index.year >= start) & (out.index.year <= end) & np.isfinite(out.to_numpy())
    if fit_mask.sum() < 24:
        return out * np.nan
    coef = np.polyfit(years[fit_mask], out.to_numpy()[fit_mask], 1)
    trend = np.polyval(coef, years)
    return out - trend


def build_ersst_residual() -> pd.DataFrame:
    ds = xr.open_dataset(ERSST_URL)
    sst = ds["sst"].sel(time=slice("1960-01-01", "2026-05-31"))
    n34 = _area_mean_sst(sst, NINO34)
    fep = _area_mean_sst(sst, FEP)
    df = pd.DataFrame({"nino34_sst": n34, "fep_sst": fep}).dropna().sort_index()
    df["nino34_anom"] = _monthly_anomaly(df["nino34_sst"])
    df["fep_anom"] = _monthly_anomaly(df["fep_sst"])
    df["nino34_detrended"] = _remove_linear_trend(df["nino34_anom"])
    df["fep_detrended"] = _remove_linear_trend(df["fep_anom"])

    fit_mask = (
        (df.index.year >= BASELINE_START)
        & (df.index.year <= BASELINE_END)
        & np.isfinite(df["nino34_detrended"])
        & np.isfinite(df["fep_detrended"])
    )
    x = df.loc[fit_mask, "nino34_detrended"].to_numpy()
    y = df.loc[fit_mask, "fep_detrended"].to_numpy()
    slope = float(np.sum(x * y) / np.sum(x * x))
    df["fep_expected_from_nino34"] = slope * df["nino34_detrended"]
    df["residual_fep"] = df["fep_detrended"] - df["fep_expected_from_nino34"]
    df["time"] = df.index
    df["year"] = df.index.year
    df["month"] = df.index.month
    df.attrs["slope"] = slope
    return df.reset_index(drop=True)


def build_leadlag_corr(df: pd.DataFrame, lags: np.ndarray) -> pd.DataFrame:
    monthly = df.set_index(pd.PeriodIndex(df["time"], freq="M"))
    first_year = int(df["year"].min())
    last_year = int(df["year"].max())
    rows: list[dict] = []
    for year in range(first_year + 14, last_year + 1):
        months = pd.period_range(pd.Period(f"{year-14}-01", freq="M"), pd.Period(f"{year}-12", freq="M"), freq="M")
        for lag in lags:
            tr_vals = []
            n34_vals = []
            for t in months:
                n_time = t + int(lag)
                if t not in monthly.index or n_time not in monthly.index:
                    continue
                tr = monthly.loc[t, "residual_fep"]
                n34 = monthly.loc[n_time, "nino34_detrended"]
                if np.isfinite(tr) and np.isfinite(n34):
                    tr_vals.append(float(tr))
                    n34_vals.append(float(n34))
            corr = np.nan
            if len(tr_vals) >= 120 and np.nanstd(tr_vals) > 0 and np.nanstd(n34_vals) > 0:
                corr = float(np.corrcoef(tr_vals, n34_vals)[0, 1])
            rows.append({"window_year": year, "lag_month": int(lag), "corr": corr, "mode": "trailing15"})
    return pd.DataFrame(rows)


def build_oras5_d20_annual() -> pd.DataFrame:
    raw = pd.read_csv(ORAS5_TRANSECT, parse_dates=["time"])
    # Consolidated covers the historical reanalysis period; operational carries 2015-present.
    raw = raw.loc[((raw["product_type"] == "consolidated") & (raw["year"] <= 2014)) | (raw["product_type"] == "operational")].copy()
    raw = raw.loc[raw["d20_m"].notna()].copy()
    raw["lon"] = raw["requested_lon"].astype(float)
    climatology = raw.loc[(raw["year"] >= BASELINE_START) & (raw["year"] <= BASELINE_END)].groupby("lon")["d20_m"].mean()
    raw["d20_mean_removed_m"] = raw["d20_m"] - raw["lon"].map(climatology)
    annual = raw.groupby(["year", "lon"], as_index=False)["d20_mean_removed_m"].mean()
    annual = annual.sort_values(["lon", "year"])
    annual["d20_10yr_trailing_m"] = annual.groupby("lon")["d20_mean_removed_m"].transform(
        lambda s: s.rolling(10, min_periods=8).mean()
    )
    return annual


def _lon_label(lon: float) -> str:
    if lon == 180:
        return "180°"
    if lon < 180:
        return f"{int(lon)}°E"
    return f"{int(360-lon)}°W"


def plot(corr_df: pd.DataFrame, annual_d20: pd.DataFrame) -> None:
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    lags = np.sort(corr_df["lag_month"].unique())
    years = np.sort(corr_df["window_year"].unique())
    corr_grid = corr_df.pivot(index="window_year", columns="lag_month", values="corr").reindex(index=years, columns=lags).to_numpy()
    corr_valid = np.isfinite(corr_grid).any(axis=1)
    years_plot = years[corr_valid]
    corr_grid = corr_grid[corr_valid, :]

    lon = np.sort(annual_d20["lon"].unique())
    d20_years = np.sort(annual_d20["year"].unique())
    d20_grid = (
        annual_d20.pivot(index="year", columns="lon", values="d20_10yr_trailing_m")
        .reindex(index=d20_years, columns=lon)
        .to_numpy()
    )
    d20_valid = np.isfinite(d20_grid).any(axis=1)
    d20_years_plot = d20_years[d20_valid]
    d20_grid = d20_grid[d20_valid, :]

    fig = plt.figure(figsize=(12.8, 8.0), dpi=170)
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1], wspace=0.30)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    im1 = ax1.contourf(lags, years_plot, corr_grid, levels=np.linspace(-0.9, 0.9, 19), cmap="RdBu_r", extend="both")
    ax1.axvline(0, color="0.25", ls="--", lw=1.5)
    for y in [1976, 2005]:
        ax1.axhline(y, color="white", ls=(0, (4, 4)), lw=1.4)
    ax1.set_title("(a) Lead-lag correlation\nERSSTv5 T$_{N34}$ and residual FEP T$_R$", weight="bold")
    ax1.set_xlabel("Lag time (month)")
    ax1.set_ylabel("15-yr window end year")
    ax1.set_xlim(-12, 12)
    ax1.set_xticks(np.arange(-12, 13, 2))
    ax1.text(-8.4, years_plot.min() + 1.7, "T$_{N34}$ lead", weight="bold", ha="center")
    ax1.text(7.0, years_plot.min() + 1.7, "T$_R$ lead", weight="bold", ha="center")
    cbar1 = fig.colorbar(im1, ax=ax1, orientation="horizontal", pad=0.085, fraction=0.055)
    cbar1.set_label("correlation")

    im2 = ax2.contourf(lon, d20_years_plot, d20_grid, levels=np.arange(-18, 19, 3), cmap="RdBu_r", extend="both")
    ax2.contour(lon, d20_years_plot, d20_grid, levels=np.arange(-18, 19, 3), colors="k", linewidths=0.45, alpha=0.75)
    for y in [1976, 2005]:
        ax2.axhline(y, color="white", ls=(0, (4, 4)), lw=1.4)
    ax2.set_title("(b) Mean-removed ORAS5 D20\n10-yr trailing mean", weight="bold")
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Year")
    ax2.set_xlim(130, 280)
    xticks = [150, 180, 210, 240, 270]
    ax2.set_xticks(xticks)
    ax2.set_xticklabels([_lon_label(x) for x in xticks])
    cbar2 = fig.colorbar(im2, ax=ax2, orientation="horizontal", pad=0.085, fraction=0.055)
    cbar2.set_label("m")

    fig.suptitle("GRL Fig. 4 same-source extension (ERSSTv5 + ORAS5, through 2026-05)", weight="bold", y=0.98)
    fig.text(
        0.055,
        0.025,
        "SST: NOAA ERSSTv5, anomalies relative to 1960-2024 monthly climatology, linear trend removed using 1960-2024 fit. "
        "D20: CDS ORAS5 time-series product, nearest native-grid points along 0° from 130°E to 80°W every 5°. "
        "White dashed lines mark 1976 and 2005 as in Jiang et al. (2026).",
        fontsize=8,
        color="0.25",
    )
    fig.savefig(OUT_FIG / "fig12_grl_fig4_same_sources_extended_to_2026.png", bbox_inches="tight", dpi=300)
    fig.savefig(OUT_FIG / "fig12_grl_fig4_same_sources_extended_to_2026.pdf", bbox_inches="tight")
    plt.close(fig)


def write_report(sst_df: pd.DataFrame, corr_df: pd.DataFrame, annual_d20: pd.DataFrame) -> None:
    report = ROOT / "reports/GRL图4同源数据延伸到2026说明.md"
    latest_sst = pd.to_datetime(sst_df["time"]).max().strftime("%Y-%m")
    latest_d20 = int(annual_d20["year"].max())
    latest_corr = corr_df.loc[corr_df["window_year"].eq(corr_df["window_year"].max())].copy()
    pos = latest_corr.loc[latest_corr["lag_month"].between(1, 12)]
    neg = latest_corr.loc[latest_corr["lag_month"].between(-12, -1)]
    max_pos = pos.loc[pos["corr"].idxmax()]
    max_neg = neg.loc[neg["corr"].idxmax()]
    report.write_text(
        f"""# GRL Figure 4 same-source extension to 2026

生成日期：2026-06-23

## 这次相较上一版改了什么

上一版右图使用 GODAS 位温剖面推算 20°C 等温面深度，是“同类替代”。这次改为原文 Methods 中列出的同源资料：

- SST：NOAA ERSSTv5；
- D20 / thermocline depth：CDS ORAS5 `depth_of_20_c_isotherm`；
- 时间：当前可用到 **{latest_sst} / 2026-05**。

因此，这一版更适合放进“沿原文 Fig. 4 继续更新”的汇报。

## 方法

### Panel a

使用 ERSSTv5 计算 Niño3.4 和 FEP SST：

- Niño3.4：170°W-120°W, 5°S-5°N；
- FEP：90°W-80°W, 5°S-5°N；
- 月异常基准期：1960-2024；
- 线性趋势：用 1960-2024 拟合并从 1960-2026 序列扣除；
- 残差定义：`FEP(t) = E * Niño3.4(t) + residual_FEP(t)`；
- lead-lag 相关：15 年 trailing window；正 lag 表示 residual FEP 领先 Niño3.4。

### Panel b

使用 CDS ORAS5 time-series 产品下载赤道太平洋 D20：

- 变量：`depth_of_20_c_isotherm` / `so20chgt`；
- 点列：0° 纬线，130°E-80°W，每 5° 一个 nearest native-grid point；
- consolidated：1960-2014；
- operational：2015-2026；
- mean-removed：每个经度扣除 1960-2024 平均；
- 平滑：年度平均后做 10 年 trailing running mean。

## 当前初步读法

- 最新 2026 结束窗口中，正 lag 一侧最大相关为 **r={max_pos['corr']:.2f} at lag +{int(max_pos['lag_month'])} months**；负 lag 一侧最大相关为 **r={max_neg['corr']:.2f} at lag {int(max_neg['lag_month'])} months**。
- 这说明在当前同源 ERSSTv5 延伸下，近年 residual FEP 领先 Niño3.4 的信号仍然存在，但相关强度不是特别高，应作为机制线索，而不是单独结论。
- ORAS5 D20 右图现在是真正同源数据，不再是 GODAS 替代。2026 年仍然只有 Jan-May，因此 2026 行代表早期状态，不能当作全年背景。

## 输出

- 图：`outputs/research_2026/figures/fig12_grl_fig4_same_sources_extended_to_2026.png`
- PDF：`outputs/research_2026/figures/fig12_grl_fig4_same_sources_extended_to_2026.pdf`
- ERSSTv5 residual 表：`data/derived/research_2026/grl_fig4_same_source_monthly_sst_residual_ersstv5.csv`
- lead-lag 表：`data/derived/research_2026/grl_fig4_same_source_leadlag_corr_ersstv5_trailing15.csv`
- ORAS5 D20 点列：`data/interim/research_2026/oras5_d20_timeseries_equatorial_1960_202605.csv`
- ORAS5 D20 年度平滑表：`data/derived/research_2026/oras5_d20_annual_mean_removed_10yr.csv`

## 数据来源

- ERSSTv5: https://psl.noaa.gov/data/gridded/data.noaa.ersst.v5.html
- ERSSTv5 OPeNDAP: https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc
- ORAS5: https://cds.climate.copernicus.eu/datasets/reanalysis-oras5
- ORAS5 time-series: https://cds.climate.copernicus.eu/datasets/reanalysis-oras5-timeseries
""",
        encoding="utf-8",
    )


def main() -> int:
    OUT_DERIVED.mkdir(parents=True, exist_ok=True)
    sst_df = build_ersst_residual()
    corr_df = build_leadlag_corr(sst_df, np.arange(-12, 13))
    annual_d20 = build_oras5_d20_annual()

    sst_path = OUT_DERIVED / "grl_fig4_same_source_monthly_sst_residual_ersstv5.csv"
    corr_path = OUT_DERIVED / "grl_fig4_same_source_leadlag_corr_ersstv5_trailing15.csv"
    annual_path = OUT_DERIVED / "oras5_d20_annual_mean_removed_10yr.csv"
    sst_df.to_csv(sst_path, index=False)
    corr_df.to_csv(corr_path, index=False)
    annual_d20.to_csv(annual_path, index=False)
    plot(corr_df, annual_d20)
    write_report(sst_df, corr_df, annual_d20)

    print(sst_path)
    print(corr_path)
    print(annual_path)
    print(OUT_FIG / "fig12_grl_fig4_same_sources_extended_to_2026.png")
    print(ROOT / "reports/GRL图4同源数据延伸到2026说明.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
