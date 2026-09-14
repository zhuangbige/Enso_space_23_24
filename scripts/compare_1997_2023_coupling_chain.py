#!/usr/bin/env python3
"""Compare the January--June ocean--atmosphere coupling chains of 1997 and 2023.

The script combines existing, locally derived SODA3 five-day diagnostics with
monthly OISST/ORAS5/ERA5/CPC/GPCP diagnostics.  It produces a manuscript-style
figure, a machine-readable comparison table, and a concise Chinese interpretation.
"""

from __future__ import annotations

from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived" / "research_2026"
OUT = ROOT / "outputs" / "research_2026" / "compare_1997_2023_coupling"
PDF_OUT = ROOT / "output" / "pdf"

FEATURES = DERIVED / "soda3_reservoir_release_coupling_features.csv"
MONTHLY = DERIVED / "enso_type_coupling_monthly_1982_2023.csv"
TIMELINE = DERIVED / "soda3_reservoir_release_coupling_event_timeline.csv"
MAP_FILES = {
    1997: DERIVED / "1997_jan_jun_oisst_ssta_era5_850_wind_anomalies_1982_2024.nc",
    2023: DERIVED / "2023_jan_jun_oisst_ssta_era5_850_wind_anomalies_1982_2024.nc",
}

EVENTS = (1997, 2023)
COLORS = {1997: "#B83A2E", 2023: "#176B87"}
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.2,
            "axes.titlesize": 10.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.2,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.0,
            "figure.dpi": 180,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def style_axis(ax: plt.Axes) -> None:
    ax.grid(True, color="#d8dde3", linewidth=0.6, alpha=0.72)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.axhline(0, color="#4d5966", linewidth=0.7, alpha=0.75, zorder=0)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.085,
        1.075,
        label,
        transform=ax.transAxes,
        fontsize=11,
        fontweight="bold",
        va="top",
        ha="left",
    )


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    f = pd.read_csv(FEATURES, parse_dates=["time"])
    f = f[(f["year"].isin(EVENTS)) & (f["month"].between(1, 6))].copy()
    m = pd.read_csv(MONTHLY, parse_dates=["time"])
    m = m[(m["year"].isin(EVENTS)) & (m["month"].between(1, 6))].copy()
    t = pd.read_csv(
        TIMELINE,
        parse_dates=[
            "release_onset_date",
            "soda3_westerly_onset_date",
            "monthly_convection_onset_midpoint",
            "monthly_joint_onset_midpoint",
        ],
    )
    t = t[t["year"].isin(EVENTS)].copy()
    return f, m, t


def monthly_feature_means(f: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "reservoir_release_15day_pw",
        "taux_central_180_220e_anom_nm2",
        "ohc300_positive_total_pj_m",
        "ohc300_positive_east140w_fraction",
    ]
    return f.groupby(["year", "month"], as_index=False)[cols].mean()


def make_comparison_table(m: pd.DataFrame, fm: pd.DataFrame) -> pd.DataFrame:
    monthly_cols = [
        "fep_anom_c",
        "ohc300_central_anom_jm2",
        "d20_ew_anom_m",
        "u850_cwp_anom_ms",
        "olr_cp_anom_wm2",
        "precip_gradient_e_minus_w_raw_mmday",
        "slp_drive_w_minus_e_raw_hpa",
        "tau_cwp_raw_nm2",
        "coupling_intensity_residual_z",
    ]
    base = m[["year", "month", *monthly_cols]].merge(
        fm, on=["year", "month"], how="left", validate="one_to_one"
    )
    wide = base.pivot(index="month", columns="year")
    out = pd.DataFrame({"month": range(1, 7), "month_label": MONTH_LABELS})
    for var in [*monthly_cols, *[c for c in fm.columns if c not in {"year", "month"}]]:
        for year in EVENTS:
            out[f"{var}_{year}"] = [wide.loc[month, (var, year)] for month in range(1, 7)]
        out[f"{var}_2023_minus_1997"] = out[f"{var}_2023"] - out[f"{var}_1997"]
    return out


def plot_march_map(ax: plt.Axes, year: int, label: str):
    ds = xr.open_dataset(MAP_FILES[year], engine="h5netcdf")
    try:
        march = ds.sel(time=f"{year}-03-01", method="nearest")
        lon = march["sst_lon"].values
        lat = march["sst_lat"].values
        ssta = march["ssta"].values
        levels = np.arange(-2.5, 2.51, 0.25)
        cf = ax.contourf(
            lon,
            lat,
            ssta,
            levels=levels,
            cmap="RdBu_r",
            extend="both",
            transform=ccrs.PlateCarree(),
        )
        ax.coastlines(resolution="110m", color="#263238", linewidth=0.55)
        ax.set_extent([120, 280, -30, 30], crs=ccrs.PlateCarree())
        xticks = [120, 160, 200, 240, 280]
        ax.set_xticks(xticks, crs=ccrs.PlateCarree())
        ax.set_xticklabels(["120°E", "160°E", "160°W", "120°W", "80°W"])
        ax.set_yticks([-30, -15, 0, 15, 30], crs=ccrs.PlateCarree())
        ax.set_yticklabels(["30°S", "15°S", "Eq", "15°N", "30°N"])
        ax.gridlines(
            crs=ccrs.PlateCarree(),
            xlocs=xticks,
            ylocs=[-30, -15, 0, 15, 30],
            color="#5c6770",
            linewidth=0.35,
            alpha=0.35,
            linestyle=":",
        )

        wlon = march["wind_lon"].values
        wlat = march["wind_lat"].values
        u = march["u850a"].values
        v = march["v850a"].values
        ix = np.arange(0, len(wlon), 8)
        iy = np.arange(0, len(wlat), 6)
        q = ax.quiver(
            wlon[ix][None, :].repeat(len(iy), axis=0),
            wlat[iy][:, None].repeat(len(ix), axis=1),
            u[np.ix_(iy, ix)],
            v[np.ix_(iy, ix)],
            color="#17212b",
            width=0.0022,
            headwidth=3.3,
            headlength=4.0,
            scale=65,
            transform=ccrs.PlateCarree(),
            zorder=4,
        )
        ax.quiverkey(q, 0.90, -0.13, 4, "4 m s$^{-1}$", labelpos="E", coordinates="axes")
        ax.set_title(f"March {year}: OISST SSTA and ERA5 850-hPa wind anomaly")
        panel_label(ax, label)
        return cf
    finally:
        ds.close()


def add_month_ticks(ax: plt.Axes) -> None:
    ax.set_xlim(0.8, 6.2)
    ax.set_xticks(range(1, 7), MONTH_LABELS)


def plot_figure(f: pd.DataFrame, m: pd.DataFrame, fm: pd.DataFrame, t: pd.DataFrame) -> tuple[Path, Path]:
    setup_style()
    fig = plt.figure(figsize=(14.4, 17.0), constrained_layout=False)
    gs = fig.add_gridspec(
        4,
        2,
        height_ratios=[1.02, 1.0, 1.0, 1.0],
        hspace=0.46,
        wspace=0.23,
        left=0.065,
        right=0.94,
        top=0.94,
        bottom=0.075,
    )
    map_axes = [
        fig.add_subplot(gs[0, 0], projection=ccrs.PlateCarree(central_longitude=180)),
        fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree(central_longitude=180)),
    ]
    cf = plot_march_map(map_axes[0], 1997, "a")
    plot_march_map(map_axes[1], 2023, "b")
    # Keep the shared map colorbar inside the inter-row whitespace so its tick
    # labels never collide with the five-day panel titles below.
    cax = fig.add_axes([0.31, 0.743, 0.38, 0.009])
    cb = fig.colorbar(cf, cax=cax, orientation="horizontal")
    cb.set_label("SST anomaly (°C)")

    ax_release_1997 = fig.add_subplot(gs[1, 0])
    ax_release_2023 = fig.add_subplot(gs[1, 1])
    for ax, year, label in zip(
        (ax_release_1997, ax_release_2023), EVENTS, ("c", "d"), strict=True
    ):
        sub = f[f["year"] == year].sort_values("time")
        ax2 = ax.twinx()
        ax.plot(
            sub["time"],
            sub["reservoir_release_15day_pw"],
            color="#D65F4A",
            linewidth=2.0,
            label="15-day reservoir release",
        )
        ax2.plot(
            sub["time"],
            sub["taux_central_180_220e_anom_nm2"],
            color="#2A6F9E",
            linewidth=1.8,
            label="Central-Pacific zonal stress",
        )
        row = t[t["year"] == year].iloc[0]
        ax.axvline(
            row["release_onset_date"], color="#D65F4A", linestyle=":", linewidth=1.3
        )
        ax.axvline(
            row["monthly_joint_onset_midpoint"], color="#6A3D9A", linestyle="--", linewidth=1.4
        )
        ax.set_ylim(-0.9, 1.05)
        ax2.set_ylim(-0.085, 0.065)
        ax.set_ylabel("Reservoir release (PW)", color="#A33A2A")
        ax2.set_ylabel("Zonal stress anomaly (N m$^{-2}$)", color="#20577A")
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.set_xlim(pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-06-30"))
        style_axis(ax)
        ax2.spines["top"].set_visible(False)
        ax.set_title(f"{year}: five-day heat release and wind stress")
        panel_label(ax, label)
        handles = [
            plt.Line2D([0], [0], color="#D65F4A", linewidth=2, label="15-day heat release"),
            plt.Line2D([0], [0], color="#2A6F9E", linewidth=2, label="zonal stress"),
            plt.Line2D([0], [0], color="#D65F4A", linestyle=":", label="release onset"),
            plt.Line2D([0], [0], color="#6A3D9A", linestyle="--", label="joint coupling onset"),
        ]
        ax.legend(handles=handles, loc="upper left", ncol=2, frameon=False)

    ax_ohc = fig.add_subplot(gs[2, 0])
    ax_d20 = fig.add_subplot(gs[2, 1])
    ax_ohc2 = ax_ohc.twinx()
    ax_d202 = ax_d20.twinx()
    for year in EVENTS:
        subf = fm[fm["year"] == year].sort_values("month")
        subm = m[m["year"] == year].sort_values("month")
        color = COLORS[year]
        ax_ohc.plot(
            subf["month"], subf["ohc300_positive_total_pj_m"], "o-", color=color,
            linewidth=2.1, markersize=4.5, label=f"{year} total OHC+"
        )
        ax_ohc2.plot(
            subf["month"], subf["ohc300_positive_east140w_fraction"], "s--", color=color,
            linewidth=1.65, markersize=3.8, alpha=0.85, label=f"{year} east fraction"
        )
        ax_d20.plot(
            subm["month"], subm["fep_anom_c"], "o-", color=color,
            linewidth=2.1, markersize=4.5, label=f"{year} FEP SSTA"
        )
        ax_d202.plot(
            subm["month"], subm["d20_ew_anom_m"], "s--", color=color,
            linewidth=1.65, markersize=3.8, alpha=0.85, label=f"{year} D20 east−west"
        )
    ax_ohc.set_ylabel("Total positive OHC (PJ m$^{-1}$)")
    ax_ohc2.set_ylabel("Fraction of positive OHC east of 140°W")
    ax_ohc.set_ylim(0, 19)
    ax_ohc2.set_ylim(0, 0.82)
    ax_ohc.set_title("Ocean heat inventory versus eastward placement")
    style_axis(ax_ohc)
    ax_ohc2.spines["top"].set_visible(False)
    add_month_ticks(ax_ohc)
    panel_label(ax_ohc, "e")
    h1, l1 = ax_ohc.get_legend_handles_labels()
    h2, l2 = ax_ohc2.get_legend_handles_labels()
    ax_ohc.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2, frameon=False)

    ax_d20.set_ylabel("FEP SST anomaly (°C)")
    ax_d202.set_ylabel("D20 east−west anomaly (m)")
    ax_d20.set_ylim(-1.5, 2.7)
    ax_d202.set_ylim(-25, 42)
    ax_d20.set_title("Surface eastern warming versus subsurface tilt")
    style_axis(ax_d20)
    ax_d202.spines["top"].set_visible(False)
    add_month_ticks(ax_d20)
    panel_label(ax_d20, "f")
    h1, l1 = ax_d20.get_legend_handles_labels()
    h2, l2 = ax_d202.get_legend_handles_labels()
    ax_d20.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2, frameon=False)

    ax_conv = fig.add_subplot(gs[3, 0])
    ax_press = fig.add_subplot(gs[3, 1])
    ax_conv2 = ax_conv.twinx()
    ax_press2 = ax_press.twinx()
    for year in EVENTS:
        sub = m[m["year"] == year].sort_values("month")
        color = COLORS[year]
        ax_conv.plot(
            sub["month"], sub["u850_cwp_anom_ms"], "o-", color=color,
            linewidth=2.1, markersize=4.5, label=f"{year} u850"
        )
        ax_conv2.plot(
            sub["month"], -sub["olr_cp_anom_wm2"], "s--", color=color,
            linewidth=1.65, markersize=3.8, alpha=0.85, label=f"{year} −OLR"
        )
        ax_press.plot(
            sub["month"], sub["precip_gradient_e_minus_w_raw_mmday"], "o-", color=color,
            linewidth=2.1, markersize=4.5, label=f"{year} rain E−W"
        )
        ax_press2.plot(
            sub["month"], sub["slp_drive_w_minus_e_raw_hpa"], "s--", color=color,
            linewidth=1.65, markersize=3.8, alpha=0.85, label=f"{year} SLP W−E"
        )
    ax_conv.set_ylabel("Central-Pacific u850 anomaly (m s$^{-1}$)")
    ax_conv2.set_ylabel("−OLR anomaly (W m$^{-2}$; convection positive)")
    ax_conv.set_ylim(-3.5, 8.5)
    ax_conv2.set_ylim(-20, 38)
    ax_conv.set_title("Wind response versus deep convection")
    style_axis(ax_conv)
    ax_conv2.spines["top"].set_visible(False)
    add_month_ticks(ax_conv)
    panel_label(ax_conv, "g")
    h1, l1 = ax_conv.get_legend_handles_labels()
    h2, l2 = ax_conv2.get_legend_handles_labels()
    ax_conv.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2, frameon=False)

    ax_press.set_ylabel("Rainfall gradient, east−west (mm day$^{-1}$)")
    ax_press2.set_ylabel("SLP drive, west−east (hPa)")
    ax_press.set_ylim(-13, 2)
    ax_press2.set_ylim(-4.2, 1.5)
    ax_press.set_title("Convection relocation and pressure-gradient closure")
    style_axis(ax_press)
    ax_press2.spines["top"].set_visible(False)
    add_month_ticks(ax_press)
    panel_label(ax_press, "h")
    h1, l1 = ax_press.get_legend_handles_labels()
    h2, l2 = ax_press2.get_legend_handles_labels()
    ax_press.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2, frameon=False)

    fig.suptitle(
        "1997 versus 2023: why eastern-Pacific surface warming did—or did not—close the air–sea feedback",
        fontsize=15.5,
        fontweight="bold",
        y=0.982,
    )
    fig.text(
        0.065,
        0.028,
        "Definitions: positive reservoir release = heat loss from 5°S–5°N, 180°–80°W; positive u850/stress = westerly; "
        "negative OLR = enhanced deep convection; positive SLP W−E favors westerly pressure-gradient forcing. "
        "Baselines follow each locally derived source product. Sources: SODA3.15.2, OISST, ORAS5, ERA5, CPC OLR and GPCP.",
        fontsize=8.1,
        color="#4d5966",
        ha="left",
        va="bottom",
        wrap=True,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "1997_2023_coupling_chain_comparison.png"
    pdf = PDF_OUT / "1997_2023_coupling_chain_comparison.pdf"
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png, pdf


def write_report(m: pd.DataFrame, fm: pd.DataFrame, t: pd.DataFrame, png: Path, pdf: Path) -> Path:
    def mv(year: int, month: int, col: str) -> float:
        return float(m[(m["year"] == year) & (m["month"] == month)][col].iloc[0])

    def fv(year: int, month: int, col: str) -> float:
        return float(fm[(fm["year"] == year) & (fm["month"] == month)][col].iloc[0])

    march_total_ratio = fv(1997, 3, "ohc300_positive_total_pj_m") / fv(
        2023, 3, "ohc300_positive_total_pj_m"
    )
    march_central_ratio = mv(1997, 3, "ohc300_central_anom_jm2") / mv(
        2023, 3, "ohc300_central_anom_jm2"
    )
    mj_u = {
        year: m[(m["year"] == year) & (m["month"].isin([5, 6]))]["u850_cwp_anom_ms"].mean()
        for year in EVENTS
    }
    mj_conv = {
        year: -m[(m["year"] == year) & (m["month"].isin([5, 6]))]["olr_cp_anom_wm2"].mean()
        for year in EVENTS
    }
    mj_rain = {
        year: m[(m["year"] == year) & (m["month"].isin([5, 6]))][
            "precip_gradient_e_minus_w_raw_mmday"
        ].mean()
        for year in EVENTS
    }
    mj_slp = {
        year: m[(m["year"] == year) & (m["month"].isin([5, 6]))][
            "slp_drive_w_minus_e_raw_hpa"
        ].mean()
        for year in EVENTS
    }
    t97 = t[t["year"] == 1997].iloc[0]
    t23 = t[t["year"] == 2023].iloc[0]

    report = f"""# 1997与2023年1—6月海气耦合比较

## 核心判断

1997和2023的根本差别，不是东部海表是否升温，而是升温之后整条Bjerknes反馈链是否闭合。2023年3月FEP海温异常已经达到{mv(2023, 3, 'fep_anom_c'):+.2f} °C，高于1997年3月的{mv(1997, 3, 'fep_anom_c'):+.2f} °C；但是2023同期中太平洋OLR仍为{mv(2023, 3, 'olr_cp_anom_wm2'):+.2f} W m⁻²，代表深对流受抑。1997同期OLR为{mv(1997, 3, 'olr_cp_anom_wm2'):+.2f} W m⁻²，同时u850达到{mv(1997, 3, 'u850_cwp_anom_ms'):+.2f} m s⁻¹，因此海温—对流—西风链已经接通。

## 一、海洋预条件

- 1997年3月赤道太平洋总正OHC为{fv(1997, 3, 'ohc300_positive_total_pj_m'):.2f} PJ m⁻¹，2023年只有{fv(2023, 3, 'ohc300_positive_total_pj_m'):.2f} PJ m⁻¹，前者约为后者的{march_total_ratio:.1f}倍。
- 中太平洋OHC异常的差距更大：1997年3月为{mv(1997, 3, 'ohc300_central_anom_jm2') / 1e9:.2f} GJ m⁻²，2023年为{mv(2023, 3, 'ohc300_central_anom_jm2') / 1e9:.2f} GJ m⁻²，约相差{march_central_ratio:.1f}倍。
- D20东西差异在1997年3月已为{mv(1997, 3, 'd20_ew_anom_m'):+.1f} m、4月迅速增至{mv(1997, 4, 'd20_ew_anom_m'):+.1f} m；2023年3月仍为{mv(2023, 3, 'd20_ew_anom_m'):+.1f} m，4月仍接近零（{mv(2023, 4, 'd20_ew_anom_m'):+.1f} m），到5月才转正。
- 2023年4—6月“140°W以东暖量占比”并不低，甚至高于1997，但总暖量库存明显更小。这说明暖量的位置偏东和暖量总量是两个不同条件；只有位置偏东，并不等于已经具备1997式的强海洋反馈能力。

## 二、大气是否接上

- 1997年3月：FEP为{mv(1997, 3, 'fep_anom_c'):+.2f} °C，u850为{mv(1997, 3, 'u850_cwp_anom_ms'):+.2f} m s⁻¹，OLR为{mv(1997, 3, 'olr_cp_anom_wm2'):+.2f} W m⁻²。风和深对流同时响应。
- 2023年3月：FEP更高（{mv(2023, 3, 'fep_anom_c'):+.2f} °C），但u850只有{mv(2023, 3, 'u850_cwp_anom_ms'):+.2f} m s⁻¹，OLR却为正（{mv(2023, 3, 'olr_cp_anom_wm2'):+.2f} W m⁻²）。这正是“表层已暖、大气未接”的脱耦信号。
- 5—6月平均，1997年u850为{mj_u[1997]:+.2f} m s⁻¹、−OLR为{mj_conv[1997]:+.2f} W m⁻²；2023年分别只有{mj_u[2023]:+.2f} m s⁻¹和{mj_conv[2023]:+.2f} W m⁻²。
- 2023年5—6月降水东西梯度仍为{mj_rain[2023]:+.2f} mm day⁻¹，远比1997年的{mj_rain[1997]:+.2f} mm day⁻¹更偏向西部；SLP西高东低驱动力（W−E）在1997年为{mj_slp[1997]:+.2f} hPa，而2023年仍为{mj_slp[2023]:+.2f} hPa。也就是说，2023的对流中心没有充分东移，气压梯度也没有反转成可维持西风的状态。

## 三、五日尺度暖量释放不能单独当作“转折点”

- 1997年联合耦合落在3月（图中用月中{t97['monthly_joint_onset_midpoint'].date()}表示），持续暖量释放起点为{t97['release_onset_date'].date()}；大气接通反而早约14天。
- 2023年持续释放判据最早在{t23['release_onset_date'].date()}触发，但联合耦合落在5月（图中用月中{t23['monthly_joint_onset_midpoint'].date()}表示），两者相差约103天。早期释放幅度弱且3月发生反转，不能自动触发大气反馈。

因此，“暖量释放先行”不是普适因果顺序。1997中强西风和对流反馈很可能反过来加强暖量东输与释放；2023则证明单独出现弱释热，仍不足以让大气接上。

## 四、两道门槛的解释

1. **海洋门槛**：需要足够大的次表层暖量库存，并形成向东的D20/压力梯度结构，而不仅仅是FEP表层SSTA为正。
2. **大气门槛**：深对流必须从西太平洋向中东太平洋迁移，随后形成有利的东西气压梯度和持续西风应力。

1997在春季基本同时跨过两道门槛；2023先出现东部表层升温，但海洋深层结构偏弱、对流仍滞留西部，因此第二道门槛只迟缓、有限地通过。这个比较支持“FEP高并非充分条件”，并把脱耦位置具体锁定在**表层升温之后、深对流东移之前**。

## 证据边界

这里只是两个关键事件的过程诊断，不能单独证明因果，也不能把某个OHC或D20数值宣布为普适临界值。下一步若要验证转折点，应在更多事件中检验“总暖量×D20结构”是否能预测对流接通，并用扰动实验分别改变暖量库存和对流背景。

## 输出

- 主图：`{pdf}`
- PNG预览：`{png}`
- 月度比较表：`{OUT / '1997_2023_monthly_comparison.csv'}`
"""
    path = OUT / "1997_2023_COUPLING_COMPARISON_CN.md"
    path.write_text(report, encoding="utf-8")
    return path


def main() -> None:
    f, m, t = read_inputs()
    fm = monthly_feature_means(f)
    comparison = make_comparison_table(m, fm)
    OUT.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(OUT / "1997_2023_monthly_comparison.csv", index=False)
    png, pdf = plot_figure(f, m, fm, t)
    report = write_report(m, fm, t, png, pdf)
    print(f"Wrote {png}")
    print(f"Wrote {pdf}")
    print(f"Wrote {OUT / '1997_2023_monthly_comparison.csv'}")
    print(f"Wrote {report}")


if __name__ == "__main__":
    main()
