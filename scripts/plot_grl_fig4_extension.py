"""Extend Jiang et al. (2026) GRL Figure 4 logic to current data.

Panel a follows the paper's residual-FEP lead-lag idea using ERSSTv5 SST.
Panel b uses NOAA GODAS potential temperature to derive the 20 deg C
isotherm depth through the latest available month. This is a current-data
substitute for the ORAS5 thermocline-depth panel in the paper.
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
from scipy.signal import detrend


ROOT = Path("/Users/daiyue/Documents/Maryland")
OUT_FIG = ROOT / "outputs/research_2026/figures"
OUT_DERIVED = ROOT / "data/derived/research_2026"
OUT_INTERIM = ROOT / "data/interim/research_2026"

GODAS_URL_TMPL = "https://psl.noaa.gov/thredds/dodsC/Datasets/godas/pottmp.{year}.nc"

LOCAL_SST_INDICES = OUT_INTERIM / "current_2026_monthly_indices.csv"
GODAS_START_YEAR = 1980
GODAS_END_YEAR = 2026


@dataclass(frozen=True)
class Region:
    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


NINO34 = Region("nino34", -5, 5, 190, 240)  # 170W-120W
FEP = Region("fep", -5, 5, 270, 280)  # 90W-80W


def _detrend_series(values: np.ndarray) -> np.ndarray:
    mask = np.isfinite(values)
    out = np.full(values.shape, np.nan, dtype=float)
    if mask.sum() > 5:
        out[mask] = detrend(values[mask], type="linear")
    return out


def build_sst_residual() -> pd.DataFrame:
    """Use local ERSSTv5 monthly indices already built for the 2026 work.

    The local table begins in 1982, so panel a is a current-data extension
    rather than a full 1960-onward reproduction of the paper panel.
    """
    source = pd.read_csv(LOCAL_SST_INDICES)
    sst = source.loc[source["metric"].eq("ersstv5_sst") & source["region"].isin(["nino34", "fep"])].copy()
    pivot = sst.pivot_table(index=["year", "month"], columns="region", values="anomaly").reset_index()
    pivot["time"] = pd.to_datetime(
        pivot["year"].astype(str) + "-" + pivot["month"].astype(str).str.zfill(2) + "-01"
    )
    df = pivot.rename(columns={"nino34": "nino34_anom", "fep": "fep_anom"})[
        ["time", "nino34_anom", "fep_anom"]
    ].sort_values("time")
    df["nino34_detrended"] = _detrend_series(df["nino34_anom"].to_numpy())
    df["fep_detrended"] = _detrend_series(df["fep_anom"].to_numpy())

    valid = np.isfinite(df["nino34_detrended"]) & np.isfinite(df["fep_detrended"])
    x = df.loc[valid, "nino34_detrended"].to_numpy()
    y = df.loc[valid, "fep_detrended"].to_numpy()
    slope = float(np.sum(x * y) / np.sum(x * x))
    df["fep_expected_from_nino34"] = slope * df["nino34_detrended"]
    df["residual_fep"] = df["fep_detrended"] - df["fep_expected_from_nino34"]
    df["year"] = df["time"].dt.year
    df["month"] = df["time"].dt.month
    df.attrs["slope"] = slope
    return df


def build_leadlag_corr(df: pd.DataFrame, lags: np.ndarray, mode: str = "trailing") -> pd.DataFrame:
    """Correlation between T_R(t) and T_N34(t + lag).

    Positive lag therefore means residual FEP SST leads Nino3.4.
    """
    monthly = df.set_index(pd.PeriodIndex(df["time"], freq="M"))
    first_year = int(df["year"].min())
    last_year = int(df["year"].max())
    rows: list[dict] = []

    if mode == "trailing":
        years = range(first_year + 14, last_year + 1)
        year_to_window = {
            year: (pd.Period(f"{year-14}-01", freq="M"), pd.Period(f"{year}-12", freq="M"))
            for year in years
        }
    elif mode == "centered":
        years = range(first_year + 7, last_year - 6)
        year_to_window = {
            year: (pd.Period(f"{year-7}-01", freq="M"), pd.Period(f"{year+7}-12", freq="M"))
            for year in years
        }
    else:
        raise ValueError(f"unknown mode: {mode}")

    for year, (start, end) in year_to_window.items():
        months = pd.period_range(start, end, freq="M")
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
            if len(tr_vals) >= 60 and np.nanstd(tr_vals) > 0 and np.nanstd(n34_vals) > 0:
                corr = float(np.corrcoef(tr_vals, n34_vals)[0, 1])
            rows.append({"window_year": year, "lag_month": int(lag), "corr": corr, "mode": mode})

    return pd.DataFrame(rows)


def _interp_20c_depth(temp_c: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """Return 20C isotherm depth for columns shaped (level, lon)."""
    nlon = temp_c.shape[1]
    out = np.full(nlon, np.nan, dtype=float)
    for j in range(nlon):
        profile = temp_c[:, j]
        ok = np.isfinite(profile)
        if ok.sum() < 4:
            continue
        z = depth[ok]
        t = profile[ok]
        # Need warm water above and colder water below.
        if np.nanmax(t) < 20 or np.nanmin(t) > 20:
            continue
        below = np.where(t <= 20)[0]
        if len(below) == 0 or below[0] == 0:
            continue
        k = below[0]
        t1, t2 = t[k - 1], t[k]
        z1, z2 = z[k - 1], z[k]
        if not np.isfinite(t1 + t2 + z1 + z2) or t2 == t1:
            continue
        out[j] = z1 + (20 - t1) * (z2 - z1) / (t2 - t1)
    return out


def build_godas_20c_depth() -> pd.DataFrame:
    cache = OUT_INTERIM / "godas_20c_depth_monthly_equatorial_1980_2026.csv"
    if cache.exists():
        print(f"Using cached GODAS 20C depth: {cache}", flush=True)
        cached = pd.read_csv(cache, parse_dates=["time"])
        return cached

    rows: list[pd.DataFrame] = []
    for year in range(GODAS_START_YEAR, GODAS_END_YEAR + 1):
        url = GODAS_URL_TMPL.format(year=year)
        print(f"Reading GODAS {year}: {url}", flush=True)
        ds = xr.open_dataset(url, decode_times=True)
        # 2026 currently has only Jan-May; older years generally have 12 months.
        temp = ds["pottmp"].sel(lat=slice(-2, 2), lon=slice(120, 280))
        temp = temp.mean("lat").load()
        vals = temp.values.astype(float)
        if np.nanmean(vals) > 100:
            vals = vals - 273.15
        depth = temp["level"].values.astype(float)
        lon = temp["lon"].values.astype(float)

        depth_rows = []
        for i, timestamp in enumerate(pd.to_datetime(temp["time"].values)):
            d20 = _interp_20c_depth(vals[i, :, :], depth)
            depth_rows.append(pd.DataFrame({"time": timestamp, "lon": lon, "depth20_m": d20}))
        rows.append(pd.concat(depth_rows, ignore_index=True))

    out = pd.concat(rows, ignore_index=True)
    out["year"] = out["time"].dt.year
    out["month"] = out["time"].dt.month
    return out


def build_depth_anomaly_annual(depth_df: pd.DataFrame) -> pd.DataFrame:
    monthly = depth_df.copy()
    climatology = monthly.groupby("lon")["depth20_m"].mean()
    monthly["depth20_mean_removed_m"] = monthly["depth20_m"] - monthly["lon"].map(climatology)
    annual = (
        monthly.groupby(["year", "lon"], as_index=False)["depth20_mean_removed_m"]
        .mean()
        .rename(columns={"depth20_mean_removed_m": "depth20_mean_removed_annual_m"})
    )
    annual = annual.sort_values(["lon", "year"])
    annual["depth20_10yr_trailing_m"] = (
        annual.groupby("lon")["depth20_mean_removed_annual_m"]
        .transform(lambda s: s.rolling(10, min_periods=8).mean())
    )
    return annual


def _lon_label(lon: float) -> str:
    if lon == 180:
        return "180°"
    if lon < 180:
        return f"{int(lon)}°E"
    return f"{int(360-lon)}°W"


def plot_fig4_extension(corr_df: pd.DataFrame, annual_depth: pd.DataFrame) -> None:
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    lags = np.sort(corr_df["lag_month"].unique())
    years = np.sort(corr_df["window_year"].unique())
    corr_grid = (
        corr_df.pivot(index="window_year", columns="lag_month", values="corr")
        .reindex(index=years, columns=lags)
        .to_numpy()
    )
    corr_valid = np.isfinite(corr_grid).any(axis=1)
    years_plot = years[corr_valid]
    corr_grid_plot = corr_grid[corr_valid, :]

    lon = np.sort(annual_depth["lon"].unique())
    depth_years = np.sort(annual_depth["year"].unique())
    depth_grid = (
        annual_depth.pivot(index="year", columns="lon", values="depth20_10yr_trailing_m")
        .reindex(index=depth_years, columns=lon)
        .to_numpy()
    )
    depth_valid = np.isfinite(depth_grid).any(axis=1)
    depth_years_plot = depth_years[depth_valid]
    depth_grid_plot = depth_grid[depth_valid, :]

    fig = plt.figure(figsize=(12.6, 8.2), dpi=160)
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1], wspace=0.30)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    corr_levels = np.linspace(-0.9, 0.9, 19)
    im1 = ax1.contourf(lags, years_plot, corr_grid_plot, levels=corr_levels, cmap="RdBu_r", extend="both")
    ax1.axvline(0, color="0.25", ls="--", lw=1.6)
    for y in [1976, 2005]:
        if years_plot.min() <= y <= years_plot.max():
            ax1.axhline(y, color="white", ls=(0, (4, 4)), lw=1.4)
    ax1.set_title("(a) Lead-lag correlation\nbetween T$_{N34}$ and residual T$_R$", weight="bold")
    ax1.set_xlabel("Lag time (month)")
    ax1.set_ylabel("Window end year")
    ax1.set_xlim(-12, 12)
    ax1.set_ylim(years_plot.min(), years_plot.max())
    ax1.set_xticks(np.arange(-12, 13, 2))
    ax1.text(-8.5, years_plot.min() + 1.5, "T$_{N34}$ lead", weight="bold", ha="center")
    ax1.text(7.0, years_plot.min() + 1.5, "T$_R$ lead", weight="bold", ha="center")
    cbar1 = fig.colorbar(im1, ax=ax1, orientation="horizontal", pad=0.085, fraction=0.055)
    cbar1.set_label("correlation")

    depth_levels = np.arange(-18, 19, 3)
    im2 = ax2.contourf(lon, depth_years_plot, depth_grid_plot, levels=depth_levels, cmap="RdBu_r", extend="both")
    ax2.contour(lon, depth_years_plot, depth_grid_plot, levels=depth_levels, colors="k", linewidths=0.45, alpha=0.8)
    for y in [1976, 2005]:
        if depth_years_plot.min() <= y <= depth_years_plot.max():
            ax2.axhline(y, color="white", ls=(0, (4, 4)), lw=1.4)
    ax2.set_title("(b) Mean-removed 20°C isotherm depth\nGODAS-derived, 10-yr trailing mean", weight="bold")
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Year")
    ax2.set_xlim(120, 280)
    ax2.set_ylim(depth_years_plot.min(), depth_years_plot.max())
    xticks = [150, 180, 210, 240, 270]
    ax2.set_xticks(xticks)
    ax2.set_xticklabels([_lon_label(x) for x in xticks])
    cbar2 = fig.colorbar(im2, ax=ax2, orientation="horizontal", pad=0.085, fraction=0.055)
    cbar2.set_label("m")

    fig.suptitle(
        "GRL Fig. 4-style current extension (available through 2026-05)",
        weight="bold",
        y=0.98,
    )
    fig.text(
        0.07,
        0.025,
        "Panel a: local ERSSTv5 monthly indices from the 2026 workflow, 1982-2026; FEP residual = FEP minus simultaneous Niño3.4-related component. "
        "Positive lag means residual FEP leads Niño3.4. Panel b: NOAA GODAS potential temperature converted to 20°C isotherm depth; "
        "used as a current-data substitute for the ORAS5 panel in Jiang et al. (2026).",
        fontsize=8,
        color="0.25",
    )

    out_png = OUT_FIG / "fig11_grl_fig4_extended_to_2026.png"
    out_pdf = OUT_FIG / "fig11_grl_fig4_extended_to_2026.pdf"
    fig.savefig(out_png, bbox_inches="tight", dpi=300)
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)


def write_report(sst_df: pd.DataFrame, corr_df: pd.DataFrame, annual_depth: pd.DataFrame) -> None:
    report = ROOT / "reports/GRL图4延伸到2026说明.md"
    latest_sst = sst_df["time"].max().strftime("%Y-%m")
    latest_godas = int(annual_depth["year"].max())
    report.write_text(
        f"""# GRL Figure 4-style extension to current data

生成日期：2026-06-23

## 图 4 原文图型

Jiang et al. (2026) 图 4 包含两个诊断：

1. **Lead-lag correlation**：Niño3.4 指数与 residual FEP SST anomaly 的 15 年滑动窗口 lead-lag 相关。正 lag 表示 residual FEP 领先 Niño3.4，负 lag 表示 Niño3.4 领先 residual FEP。
2. **Mean-removed thermocline depth**：赤道太平洋 20°C 等温面深度的经度-时间变化，原文使用 ORAS5，做 10 年滑动平均。

## 本次延伸方式

- Panel a 使用本项目已经生成的 ERSSTv5 月指数表，当前可用到 **{latest_sst}**。该表从 1982 年开始，因此是“当前延伸版”，不是原文 1960 年起始版本的严格复现。
- Panel b 使用 NOAA GODAS `pottmp` 位温剖面计算 20°C 等温面深度，当前 2026 文件含 1-5 月，因此可追踪到 **2026-05**。年度图中 2026 是 1-5 月平均，后续需要在 6 月、全年数据更新后重算。
- 由于公开 ICDC THREDDS 的 ORAS5 `so20chgt` 年文件只列到 2018，本次右图不是原文 ORAS5 的严格复现，而是 **GODAS current-data substitute**。

## 输出文件

- 图：`outputs/research_2026/figures/fig11_grl_fig4_extended_to_2026.png`
- PDF：`outputs/research_2026/figures/fig11_grl_fig4_extended_to_2026.pdf`
- lead-lag 相关表：`data/derived/research_2026/grl_fig4_leadlag_corr_ersstv5_trailing15.csv`
- residual FEP 月指数：`data/derived/research_2026/grl_fig4_monthly_sst_residual_ersstv5.csv`
- GODAS 20°C 等温面月数据：`data/interim/research_2026/godas_20c_depth_monthly_equatorial_1980_2026.csv`
- GODAS 10 年平滑年度数据：`data/derived/research_2026/godas_20c_depth_annual_mean_removed_10yr.csv`

## 方法说明

SST 处理：

```text
FEP(t) = E * Niño3.4(t) + residual_FEP(t)
```

其中 Niño3.4 和 FEP 均为月异常并去线性趋势；E 用 1982-2026 当前可用 ERSSTv5 月序列最小二乘估计。15 年窗口采用 **trailing window**，即图中年份表示窗口结束年，这样可以把图延伸到当前可用时间。

20°C 等温面处理：

1. 读取 GODAS `pottmp.YYYY.nc`。
2. 选取 2°S-2°N 平均、120°E-80°W。
3. 将 K 转为 °C。
4. 对每个经度和月份沿垂直方向线性插值求 `T=20°C` 的深度。
5. 去除每个经度的时间平均，得到 mean-removed depth。
6. 做年度平均和 10 年 trailing running mean。

## 当前图的主要读法

- 左图若正 lag 一侧相关更强，表示 residual FEP 变化倾向于领先 Niño3.4，说明 ENSO 发展可能更偏 FEP/东太平洋先行。
- 右图红色表示 20°C 等温面比该经度平均状态更深，蓝色表示更浅。东太平洋较浅的热跃层背景意味着 SST 对上升流/风应力扰动更敏感。
- 由于 2026 年尚未完整，2026 右图只代表 Jan-May 资料的初步状态，不能作为全年年代际背景的最终判断。

## 数据来源

- ERSSTv5 OPeNDAP: https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc
- GODAS OPeNDAP pattern: https://psl.noaa.gov/thredds/dodsC/Datasets/godas/pottmp.YYYY.nc
- ORAS5 ICDC information and THREDDS: https://www.cen.uni-hamburg.de/icdc/data/ocean/easy-init-ocean/ecmwf-oras5.html
- Jiang et al. (2026) GRL local PDF: `/Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf`
""",
        encoding="utf-8",
    )


def main() -> None:
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    OUT_DERIVED.mkdir(parents=True, exist_ok=True)
    OUT_INTERIM.mkdir(parents=True, exist_ok=True)

    sst_df = build_sst_residual()
    lags = np.arange(-12, 13)
    corr_df = build_leadlag_corr(sst_df, lags, mode="trailing")
    depth_df = build_godas_20c_depth()
    annual_depth = build_depth_anomaly_annual(depth_df)

    sst_path = OUT_DERIVED / "grl_fig4_monthly_sst_residual_ersstv5.csv"
    corr_path = OUT_DERIVED / "grl_fig4_leadlag_corr_ersstv5_trailing15.csv"
    depth_path = OUT_INTERIM / "godas_20c_depth_monthly_equatorial_1980_2026.csv"
    annual_path = OUT_DERIVED / "godas_20c_depth_annual_mean_removed_10yr.csv"
    sst_df.to_csv(sst_path, index=False)
    corr_df.to_csv(corr_path, index=False)
    depth_df.to_csv(depth_path, index=False)
    annual_depth.to_csv(annual_path, index=False)

    plot_fig4_extension(corr_df, annual_depth)
    write_report(sst_df, corr_df, annual_depth)

    print(sst_path)
    print(corr_path)
    print(depth_path)
    print(annual_path)
    print(OUT_FIG / "fig11_grl_fig4_extended_to_2026.png")
    print(ROOT / "reports/GRL图4延伸到2026说明.md")


if __name__ == "__main__":
    main()
