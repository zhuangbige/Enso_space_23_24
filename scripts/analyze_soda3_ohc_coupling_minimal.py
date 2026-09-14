#!/usr/bin/env python3
"""Minimal SODA3 OHC test for the ocean-to-atmosphere ENSO transition.

The experiment intentionally keeps one ocean predictor and one atmospheric
response:

* predictor: March-April 0-300 m OHC anomaly in 5S-5N, 180-140W;
* response: May-June ERA5 850-hPa zonal-wind anomaly in 5S-5N,
  160E-140W.

Warm-event years are inherited from the existing event catalogue.  The
positive spring-FEP-residual cases (1997, 2002, and 2023) are highlighted,
but the association is estimated across all 13 warm events to avoid drawing
a correlation from only three cases.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_soda3_ohc_minimal_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
OHC_NETCDF = (
    ROOT
    / "data/interim/research_2026/soda3_ohc/"
    "soda3_ohc_0_100_0_300_1980_2024.nc"
)
OHC_INDEX_CSV = ROOT / "data/derived/research_2026/soda3_ohc_indices_1980_2024.csv"
COUPLING_MONTHLY_CSV = (
    ROOT / "data/derived/research_2026/enso_type_coupling_monthly_1982_2023.csv"
)
EVENT_CSV = ROOT / "data/derived/research_2026/enso_type_coupling_event_summary.csv"

OUT_DATA = ROOT / "data/derived/research_2026"
OUT_FIG = ROOT / "outputs/research_2026/soda3_ohc_minimal"
TABLE_CSV = OUT_DATA / "soda3_ohc_coupling_minimal_event_table.csv"
DIAGNOSTICS_JSON = OUT_DATA / "soda3_ohc_coupling_minimal_diagnostics.json"
FIG_PNG = OUT_FIG / "soda3_ohc_coupling_minimal.png"
FIG_PDF = OUT_FIG / "soda3_ohc_coupling_minimal.pdf"
REPORT_MD = OUT_FIG / "SODA3_OHC_MINIMAL_RESULT_CN.md"

PREDICTOR_COLUMN = "ohc300_central_ma_gj_m2"
RESPONSE_COLUMN = "u850_cwp_mj_ms"
HIGHLIGHT_YEARS = (1997, 2002, 2023)


def set_plot_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 300,
        }
    )


def build_event_table() -> pd.DataFrame:
    ohc = pd.read_csv(OHC_INDEX_CSV)
    monthly = pd.read_csv(COUPLING_MONTHLY_CSV)
    events = pd.read_csv(EVENT_CSV)
    event_years = events["year"].astype(int).tolist()

    predictor = (
        ohc.loc[
            ohc["year"].isin(event_years) & ohc["month"].isin([3, 4]),
            ["year", "ohc300_central_anom_jm2"],
        ]
        .groupby("year", as_index=False)["ohc300_central_anom_jm2"]
        .mean()
        .rename(columns={"ohc300_central_anom_jm2": PREDICTOR_COLUMN})
    )
    predictor[PREDICTOR_COLUMN] /= 1.0e9

    response = (
        monthly.loc[
            monthly["year"].isin(event_years) & monthly["month"].isin([5, 6]),
            ["year", "u850_cwp_anom_ms"],
        ]
        .groupby("year", as_index=False)["u850_cwp_anom_ms"]
        .mean()
        .rename(columns={"u850_cwp_anom_ms": RESPONSE_COLUMN})
    )

    table = (
        events[
            [
                "year",
                "group",
                "mar_apr_fep_residual_c",
                "mature_djf_type_index_c",
            ]
        ]
        .merge(predictor, on="year", validate="one_to_one")
        .merge(response, on="year", validate="one_to_one")
        .sort_values("year")
        .reset_index(drop=True)
    )
    table["positive_spring_fep_residual"] = table["mar_apr_fep_residual_c"] > 0.0
    table["highlight_case"] = table["year"].isin(HIGHLIGHT_YEARS)
    if len(table) != len(event_years):
        raise ValueError("The minimal table does not contain every warm-event year")
    if table[[PREDICTOR_COLUMN, RESPONSE_COLUMN]].isna().any().any():
        raise ValueError("Missing predictor or response in the minimal event table")
    return table


def bootstrap_correlation(
    x: np.ndarray,
    y: np.ndarray,
    samples: int = 20_000,
) -> tuple[float, float]:
    rng = np.random.default_rng(20260802)
    values = []
    for _ in range(samples):
        index = rng.integers(0, len(x), len(x))
        if np.std(x[index]) == 0 or np.std(y[index]) == 0:
            continue
        values.append(float(np.corrcoef(x[index], y[index])[0, 1]))
    return tuple(np.percentile(values, [2.5, 97.5]).tolist())


def calculate_diagnostics(table: pd.DataFrame) -> dict[str, object]:
    x = table[PREDICTOR_COLUMN].to_numpy(dtype=float)
    y = table[RESPONSE_COLUMN].to_numpy(dtype=float)
    pearson = stats.pearsonr(x, y)
    spearman = stats.spearmanr(x, y)
    regression = stats.linregress(x, y)
    ci_low, ci_high = bootstrap_correlation(x, y)
    leave_one_out = []
    for year in table["year"]:
        keep = table["year"].ne(year)
        leave_one_out.append(
            {
                "excluded_year": int(year),
                "pearson_r": float(
                    np.corrcoef(
                        table.loc[keep, PREDICTOR_COLUMN],
                        table.loc[keep, RESPONSE_COLUMN],
                    )[0, 1]
                ),
            }
        )
    highlighted = table.loc[table["highlight_case"]].copy()
    return {
        "experiment": {
            "ocean_predictor": (
                "SODA3.15.2 March-April 0-300 m OHC anomaly, "
                "5S-5N 180-140W"
            ),
            "atmospheric_response": (
                "ERA5 May-June 850-hPa zonal-wind anomaly, "
                "5S-5N 160E-140W"
            ),
            "ohc_baseline": "1980-2024 calendar-month climatology with same-month trend removed",
            "n_warm_events": int(len(table)),
        },
        "all_warm_events": {
            "pearson_r": float(pearson.statistic),
            "pearson_p": float(pearson.pvalue),
            "bootstrap_95_ci": [float(ci_low), float(ci_high)],
            "spearman_r": float(spearman.statistic),
            "spearman_p": float(spearman.pvalue),
            "linear_slope_ms_per_gjm2": float(regression.slope),
            "linear_intercept_ms": float(regression.intercept),
            "leave_one_event_out_r_range": [
                float(min(item["pearson_r"] for item in leave_one_out)),
                float(max(item["pearson_r"] for item in leave_one_out)),
            ],
            "leave_one_event_out": leave_one_out,
        },
        "positive_fep_highlight_cases": highlighted[
            [
                "year",
                "mar_apr_fep_residual_c",
                PREDICTOR_COLUMN,
                RESPONSE_COLUMN,
                "mature_djf_type_index_c",
            ]
        ].to_dict(orient="records"),
        "interpretation_limit": (
            "This is an event-level observational association and does not by itself "
            "establish a causal or universal OHC threshold."
        ),
    }


def load_highlight_profiles() -> tuple[np.ndarray, dict[int, np.ndarray]]:
    # h5netcdf avoids relying on a system NetCDF shared-library stack and is
    # sufficient for this self-contained NetCDF4/HDF5 product.
    with xr.open_dataset(OHC_NETCDF, engine="h5netcdf") as dataset:
        field = dataset["ohc_300m_anomaly_detrended"].sel(
            lat=slice(-5.0, 5.0),
            lon=slice(130.0, 280.0),
        )
        weights = np.cos(np.deg2rad(field["lat"]))
        zonal = field.weighted(weights).mean("lat", skipna=True) / 1.0e9
        longitude = np.asarray(zonal["lon"].to_numpy(), dtype=float)
        profiles: dict[int, np.ndarray] = {}
        for year in HIGHLIGHT_YEARS:
            profile = zonal.sel(time=slice(f"{year}-03-01", f"{year}-04-30")).mean("time")
            smoothed = profile.rolling(lon=11, center=True, min_periods=1).mean()
            profiles[year] = np.asarray(smoothed.to_numpy(), dtype=float)
    return longitude, profiles


def longitude_label(value: float) -> str:
    if value < 180.0:
        return f"{value:g}E"
    if np.isclose(value, 180.0):
        return "180"
    return f"{360.0 - value:g}W"


def make_figure(table: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    set_plot_style()
    longitude, profiles = load_highlight_profiles()
    colors = {1997: "#b2182b", 2002: "#d99a20", 2023: "#2166ac"}

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    fig.subplots_adjust(left=0.075, right=0.985, top=0.83, bottom=0.23, wspace=0.24)

    axis = axes[0]
    axis.axvspan(180.0, 220.0, color="#efe3c2", alpha=0.75, zorder=-2)
    for year in HIGHLIGHT_YEARS:
        axis.plot(
            longitude,
            profiles[year],
            color=colors[year],
            lw=2.0,
            label=str(year),
        )
    axis.axhline(0.0, color="0.35", lw=0.8)
    axis.axvline(180.0, color="0.45", lw=0.7, ls=":")
    axis.axvline(220.0, color="0.45", lw=0.7, ls=":")
    axis.set_xlim(130.0, 280.0)
    axis.set_xticks(
        [130, 150, 180, 200, 220, 240, 260, 280],
        [longitude_label(value) for value in [130, 150, 180, 200, 220, 240, 260, 280]],
    )
    axis.set_xlabel("Longitude")
    axis.set_ylabel("0-300 m OHC anomaly (GJ m$^{-2}$)")
    axis.set_title("(a) March-April ocean heat distribution")
    axis.legend(frameon=False, ncol=3, loc="upper left")
    y_min, y_max = axis.get_ylim()
    axis.text(
        200.0,
        y_min + 0.08 * (y_max - y_min),
        "candidate bridge: 180-140W",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#6f581c",
    )
    axis.grid(axis="y", color="0.90", lw=0.7)

    axis = axes[1]
    ordinary = table.loc[~table["positive_spring_fep_residual"]]
    highlighted = table.loc[table["positive_spring_fep_residual"]]
    axis.scatter(
        ordinary[PREDICTOR_COLUMN],
        ordinary[RESPONSE_COLUMN],
        color="0.62",
        edgecolor="white",
        linewidth=0.6,
        s=46,
        zorder=3,
        label="Other warm events",
    )
    for _, row in highlighted.iterrows():
        year = int(row["year"])
        axis.scatter(
            row[PREDICTOR_COLUMN],
            row[RESPONSE_COLUMN],
            color=colors.get(year, "#762a83"),
            edgecolor="white",
            linewidth=0.8,
            s=82,
            zorder=5,
        )
    for _, row in table.iterrows():
        axis.annotate(
            str(int(row["year"])),
            (row[PREDICTOR_COLUMN], row[RESPONSE_COLUMN]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7.2,
            color="0.25" if not row["positive_spring_fep_residual"] else colors.get(int(row["year"]), "#762a83"),
        )
    regression = diagnostics["all_warm_events"]
    x_line = np.linspace(
        float(table[PREDICTOR_COLUMN].min()) - 0.08,
        float(table[PREDICTOR_COLUMN].max()) + 0.08,
        100,
    )
    y_line = (
        float(regression["linear_intercept_ms"])
        + float(regression["linear_slope_ms_per_gjm2"]) * x_line
    )
    axis.plot(x_line, y_line, color="0.20", lw=1.2, zorder=2)
    axis.axhline(0.0, color="0.55", lw=0.8)
    axis.axvline(0.0, color="0.55", lw=0.8)
    axis.set_xlabel("Mar-Apr central-Pacific OHC anomaly (GJ m$^{-2}$)")
    axis.set_ylabel("May-Jun 850-hPa zonal-wind anomaly (m s$^{-1}$)")
    axis.set_title("(b) Does stored heat precede westerly coupling?")
    axis.grid(color="0.90", lw=0.7)
    axis.text(
        0.04,
        0.95,
        (
            f"r = {regression['pearson_r']:.2f}, p = {regression['pearson_p']:.1e}\n"
            f"LOEO r = {regression['leave_one_event_out_r_range'][0]:.2f} to "
            f"{regression['leave_one_event_out_r_range'][1]:.2f}"
        ),
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "0.8", "alpha": 0.9},
    )

    fig.suptitle(
        "Minimal SODA3 test: central-Pacific subsurface heat and atmospheric coupling",
        fontsize=13.5,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.055,
        (
            "SODA3.15.2 OHC anomalies use a 1980-2024 calendar-month baseline with "
            "same-month trend removed. Colored cases have positive Mar-Apr FEP residual SST. "
            "Association across 13 warm events; it is not yet a causal threshold."
        ),
        ha="center",
        va="bottom",
        fontsize=7.8,
        color="0.35",
        wrap=True,
    )
    fig.savefig(FIG_PNG, dpi=300)
    fig.savefig(FIG_PDF)
    plt.close(fig)


def write_report(table: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    stats_all = diagnostics["all_warm_events"]
    highlighted = table.loc[table["highlight_case"]].copy()
    rows = []
    for _, row in highlighted.iterrows():
        rows.append(
            "| {year} | {fep:+.2f} | {ohc:+.2f} | {u:+.2f} |".format(
                year=int(row["year"]),
                fep=row["mar_apr_fep_residual_c"],
                ohc=row[PREDICTOR_COLUMN],
                u=row[RESPONSE_COLUMN],
            )
        )
    text = f"""# SODA3热含量—海气耦合最小实验

## 问题

在暖事件中，3—4月中太平洋（5°S–5°N，180°–140°W）的0—300米热含量，是否与随后5—6月西风异常建立有关？

## 仅保留的两个量

1. 海洋：SODA3.15.2 3—4月中太平洋0—300米OHC距平。
2. 大气：ERA5 5—6月中西太平洋850 hPa纬向风距平。

FEP残差只用于标出“表面远东太平洋已经先暖”的案例，不进入回归。

## 初步结果

13个暖事件中，春季中太平洋OHC与初夏西风异常的Pearson相关为 **r={stats_all['pearson_r']:.2f}**（p={stats_all['pearson_p']:.2e}），Spearman相关为 **{stats_all['spearman_r']:.2f}**。逐一删除任一事件后，相关仍为 **{stats_all['leave_one_event_out_r_range'][0]:.2f}—{stats_all['leave_one_event_out_r_range'][1]:.2f}**。

| 事件年 | 3—4月FEP残差（°C） | 3—4月中太平洋OHC（GJ m⁻²） | 5—6月U850距平（m s⁻¹） |
|---:|---:|---:|---:|
{chr(10).join(rows)}

1997年中太平洋次表层蓄热最强，随后西风响应也最强；2002和2023年虽然FEP残差为正，但中太平洋蓄热较弱，随后西风响应也弱。2023年尤其表现为暖量更多留在西部，尚未在春季形成1997式的中太平洋热量桥。

## 当前能说到哪里

这一步支持把 **180°–140°W的中太平洋上层热含量** 作为候选转变区：FEP表面先暖之后，若暖量没有在这里形成足够的次表层储存，大气西风反馈可能难以接上。

这还是相关关系，不能把某个数值直接称为普适阈值。下一步只需做一个更窄的检验：逐月确定中太平洋OHC首次持续转正的月份，并检查西风异常是否在其后1—2个月出现；不增加新的候选变量。
"""
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> None:
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    table = build_event_table()
    diagnostics = calculate_diagnostics(table)
    table.to_csv(TABLE_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_figure(table, diagnostics)
    write_report(table, diagnostics)
    print(f"Wrote {TABLE_CSV}")
    print(f"Wrote {DIAGNOSTICS_JSON}")
    print(f"Wrote {FIG_PNG}")
    print(f"Wrote {FIG_PDF}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
