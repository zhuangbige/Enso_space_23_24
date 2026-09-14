#!/usr/bin/env python3
"""Timing-only extension of the minimal SODA3 OHC coupling experiment.

No new physical candidate is introduced.  The script asks whether monthly
central-Pacific 0-300 m OHC anomalies lead central-western Pacific 850-hPa
zonal-wind anomalies by zero, one, or two months across 13 warm events.
It also documents the first two-month positive run for the three cases with
positive March-April FEP residual SST (1997, 2002, and 2023).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUNTIME_CACHE = Path("/private/tmp/codex_soda3_ohc_timing_cache")
RUNTIME_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(RUNTIME_CACHE / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(RUNTIME_CACHE))

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived/research_2026"
OUT = ROOT / "outputs/research_2026/soda3_ohc_minimal"

OHC_CSV = DERIVED / "soda3_ohc_indices_1980_2024.csv"
COUPLING_CSV = DERIVED / "enso_type_coupling_monthly_1982_2023.csv"
EVENT_CSV = DERIVED / "enso_type_coupling_event_summary.csv"

LAG_CSV = DERIVED / "soda3_ohc_coupling_monthly_lag_scan.csv"
ONSET_CSV = DERIVED / "soda3_ohc_coupling_positive_run_onsets.csv"
DIAGNOSTICS_JSON = DERIVED / "soda3_ohc_coupling_timing_diagnostics.json"
FIG_PNG = OUT / "soda3_ohc_coupling_timing.png"
FIG_PDF = OUT / "soda3_ohc_coupling_timing.pdf"
REPORT_MD = OUT / "SODA3_OHC_COUPLING_TIMING_CN.md"

HIGHLIGHT_YEARS = (1997, 2002, 2023)
MONTH_LABELS = {month: pd.Timestamp(2001, month, 1).strftime("%b") for month in range(1, 7)}


def set_plot_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.2,
            "axes.titlesize": 10.2,
            "axes.labelsize": 9.2,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 300,
        }
    )


def benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    values = p_values.to_numpy(dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty_like(adjusted)
    output[order] = np.clip(adjusted, 0.0, 1.0)
    return pd.Series(output, index=p_values.index)


def load_monthly_matrices() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ohc = pd.read_csv(OHC_CSV)
    coupling = pd.read_csv(COUPLING_CSV)
    events = pd.read_csv(EVENT_CSV)
    event_years = events["year"].astype(int).tolist()

    ocean = (
        ohc.loc[
            ohc["year"].isin(event_years) & ohc["month"].between(1, 6),
            ["year", "month", "ohc300_central_anom_jm2"],
        ]
        .pivot(index="year", columns="month", values="ohc300_central_anom_jm2")
        .reindex(event_years)
        / 1.0e9
    )
    wind = (
        coupling.loc[
            coupling["year"].isin(event_years) & coupling["month"].between(1, 6),
            ["year", "month", "u850_cwp_anom_ms"],
        ]
        .pivot(index="year", columns="month", values="u850_cwp_anom_ms")
        .reindex(event_years)
    )
    if ocean.shape != (13, 6) or wind.shape != (13, 6):
        raise ValueError(f"Unexpected timing matrices: OHC {ocean.shape}, wind {wind.shape}")
    if ocean.isna().any().any() or wind.isna().any().any():
        raise ValueError("Missing values in the timing matrices")
    return ocean, wind, events


def lag_scan(ocean: pd.DataFrame, wind: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int]] = []
    for ocean_month in range(1, 7):
        for lag_months in range(0, 3):
            wind_month = ocean_month + lag_months
            if wind_month > 6:
                continue
            x = ocean[ocean_month].to_numpy(dtype=float)
            y = wind[wind_month].to_numpy(dtype=float)
            pearson = stats.pearsonr(x, y)
            spearman = stats.spearmanr(x, y)
            leave_one_out = []
            for index in range(len(x)):
                keep = np.arange(len(x)) != index
                leave_one_out.append(float(np.corrcoef(x[keep], y[keep])[0, 1]))
            rows.append(
                {
                    "ohc_month": ocean_month,
                    "wind_month": wind_month,
                    "lag_months": lag_months,
                    "n_events": len(x),
                    "pearson_r": float(pearson.statistic),
                    "pearson_p": float(pearson.pvalue),
                    "spearman_r": float(spearman.statistic),
                    "spearman_p": float(spearman.pvalue),
                    "loeo_r_min": float(min(leave_one_out)),
                    "loeo_r_max": float(max(leave_one_out)),
                }
            )
    output = pd.DataFrame(rows)
    output["bh_fdr_q"] = benjamini_hochberg(output["pearson_p"])
    return output.sort_values(["ohc_month", "lag_months"]).reset_index(drop=True)


def first_two_month_positive_run(series: pd.Series) -> int | None:
    for month in range(1, 6):
        if float(series.loc[month]) > 0.0 and float(series.loc[month + 1]) > 0.0:
            return month
    return None


def onset_table(
    ocean: pd.DataFrame,
    wind: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    fep = events.set_index("year")["mar_apr_fep_residual_c"]
    group = events.set_index("year")["group"]
    for year in ocean.index:
        ohc_onset = first_two_month_positive_run(ocean.loc[year])
        wind_onset = first_two_month_positive_run(wind.loc[year])
        rows.append(
            {
                "year": int(year),
                "group": group.loc[year],
                "mar_apr_fep_residual_c": float(fep.loc[year]),
                "positive_spring_fep_residual": bool(fep.loc[year] > 0.0),
                "ohc_first_two_month_positive_start": ohc_onset,
                "wind_first_two_month_positive_start": wind_onset,
                "wind_minus_ohc_onset_months": (
                    None if ohc_onset is None or wind_onset is None else wind_onset - ohc_onset
                ),
                "ohc_jan_jun_mean_gj_m2": float(ocean.loc[year].mean()),
                "wind_jan_jun_mean_ms": float(wind.loc[year].mean()),
                "ohc_jan_jun_max_gj_m2": float(ocean.loc[year].max()),
                "wind_jan_jun_max_ms": float(wind.loc[year].max()),
            }
        )
    return pd.DataFrame(rows)


def build_diagnostics(lag: pd.DataFrame, onset: pd.DataFrame) -> dict[str, object]:
    best = lag.loc[lag["pearson_r"].idxmax()]
    highlighted = onset.loc[onset["year"].isin(HIGHLIGHT_YEARS)]
    top = lag.sort_values("pearson_r", ascending=False).head(5)
    return {
        "experiment": {
            "only_ocean_variable": "SODA3 March-June central-Pacific 0-300 m OHC anomaly",
            "only_atmospheric_variable": "ERA5 March-June central-western-Pacific U850 anomaly",
            "tested_lags_months": [0, 1, 2],
            "n_warm_events": 13,
        },
        "strongest_sampled_month_pair": best.to_dict(),
        "five_highest_correlations": top.to_dict(orient="records"),
        "positive_fep_case_onsets": highlighted.to_dict(orient="records"),
        "interpretation": (
            "The strongest sampled link is simultaneous in April, while one- and two-month "
            "lead relations are also strong. Monthly data therefore identify a March-April "
            "coupled checkpoint, not a uniquely ocean-leading causal transition. A two-month "
            "positive sign run is too weak a threshold to distinguish strong from weak coupling."
        ),
    }


def make_figure(
    ocean: pd.DataFrame,
    wind: pd.DataFrame,
    lag: pd.DataFrame,
    onset: pd.DataFrame,
) -> None:
    set_plot_style()
    colors = {1997: "#b2182b", 2002: "#d99a20", 2023: "#2166ac"}
    fig = plt.figure(figsize=(11.5, 7.3))
    grid = fig.add_gridspec(
        3,
        2,
        width_ratios=[1.05, 1.45],
        left=0.075,
        right=0.93,
        top=0.88,
        bottom=0.14,
        wspace=0.28,
        hspace=0.30,
    )

    axis = fig.add_subplot(grid[:, 0])
    matrix = np.full((6, 3), np.nan)
    q_matrix = np.full((6, 3), np.nan)
    wind_month_matrix = np.full((6, 3), np.nan)
    for _, row in lag.iterrows():
        i = int(row["ohc_month"]) - 1
        j = int(row["lag_months"])
        matrix[i, j] = row["pearson_r"]
        q_matrix[i, j] = row["bh_fdr_q"]
        wind_month_matrix[i, j] = row["wind_month"]
    image = axis.imshow(matrix, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    axis.set_xticks([0, 1, 2], ["same month", "+1 month", "+2 months"])
    axis.set_yticks(np.arange(6), [MONTH_LABELS[m] for m in range(1, 7)])
    axis.set_xlabel("Wind response lag after OHC month")
    axis.set_ylabel("Central-Pacific OHC month")
    axis.set_title("(a) Event-wise OHC-U850 correlation")
    axis.tick_params(axis="x", labelrotation=20)
    axis.set_facecolor("0.92")
    for i in range(6):
        for j in range(3):
            if not np.isfinite(matrix[i, j]):
                continue
            mark = "*" if q_matrix[i, j] < 0.05 else ""
            text_color = "white" if abs(matrix[i, j]) > 0.62 else "0.18"
            axis.text(
                j,
                i,
                f"r={matrix[i, j]:.2f}{mark}\nU: {MONTH_LABELS[int(wind_month_matrix[i, j])]}",
                ha="center",
                va="center",
                fontsize=8,
                color=text_color,
                fontweight="bold" if mark else "normal",
            )
    onset_indexed = onset.set_index("year")
    for row_index, year in enumerate(HIGHLIGHT_YEARS):
        axis = fig.add_subplot(grid[row_index, 1])
        wind_axis = axis.twinx()
        months = np.arange(1, 7)
        axis.axvspan(3.5, 4.5, color="#eee4ca", alpha=0.65, zorder=-3)
        axis.plot(
            months,
            ocean.loc[year].to_numpy(dtype=float),
            color="#b2182b",
            marker="o",
            ms=3.8,
            lw=1.8,
            label="OHC",
        )
        wind_axis.plot(
            months,
            wind.loc[year].to_numpy(dtype=float),
            color="#2166ac",
            marker="s",
            ms=3.4,
            lw=1.6,
            ls="--",
            label="U850",
        )
        axis.axhline(0.0, color="#b2182b", lw=0.65, alpha=0.55)
        wind_axis.axhline(0.0, color="#2166ac", lw=0.65, alpha=0.55)
        axis.set_xlim(0.8, 6.2)
        axis.set_ylim(-0.25, 2.10)
        wind_axis.set_ylim(-3.2, 7.8)
        axis.set_xticks(months, [MONTH_LABELS[m] for m in months])
        axis.grid(axis="x", color="0.91", lw=0.7)
        axis.set_title(f"({chr(98 + row_index)}) {year}: OHC and westerly evolution", loc="left")
        current = onset_indexed.loc[year]
        ohc_onset = current["ohc_first_two_month_positive_start"]
        wind_onset = current["wind_first_two_month_positive_start"]
        ohc_text = "none" if pd.isna(ohc_onset) else MONTH_LABELS[int(ohc_onset)]
        wind_text = "none" if pd.isna(wind_onset) else MONTH_LABELS[int(wind_onset)]
        axis.text(
            0.985,
            0.90,
            f"first 2-month positive run: OHC {ohc_text}, U850 {wind_text}",
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=7.8,
            color=colors[year],
        )
        if row_index == 1:
            axis.set_ylabel("0-300 m OHC anomaly (GJ m$^{-2}$)", color="#b2182b")
            wind_axis.set_ylabel("U850 anomaly (m s$^{-1}$)", color="#2166ac")
        if row_index < 2:
            axis.tick_params(axis="x", labelbottom=False)
        else:
            axis.set_xlabel("Development-year month")
        axis.tick_params(axis="y", colors="#b2182b")
        wind_axis.tick_params(axis="y", colors="#2166ac")

    fig.suptitle(
        "SODA3 OHC timing test: spring checkpoint, but no unique ocean lead",
        fontsize=13.5,
        fontweight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.025,
        (
            "Red: SODA3 central-Pacific OHC (180-140W). Blue: ERA5 U850 "
            "(160E-140W). April shading marks the strongest sampled same-month association; "
            "* denotes Benjamini-Hochberg q < 0.05."
        ),
        ha="center",
        va="bottom",
        fontsize=7.8,
        color="0.35",
    )
    fig.savefig(FIG_PNG, dpi=300)
    fig.savefig(FIG_PDF)
    plt.close(fig)


def write_report(lag: pd.DataFrame, onset: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    best = diagnostics["strongest_sampled_month_pair"]
    top = lag.sort_values("pearson_r", ascending=False).head(4)
    highlighted = onset.loc[onset["year"].isin(HIGHLIGHT_YEARS)].copy()
    lag_rows = []
    for _, row in top.iterrows():
        lag_rows.append(
            "| {om} | {um} | {lag:+d} | {r:.2f} | {q:.3f} |".format(
                om=MONTH_LABELS[int(row["ohc_month"])],
                um=MONTH_LABELS[int(row["wind_month"])],
                lag=int(row["lag_months"]),
                r=row["pearson_r"],
                q=row["bh_fdr_q"],
            )
        )
    onset_rows = []
    for _, row in highlighted.iterrows():
        ohc_onset = row["ohc_first_two_month_positive_start"]
        wind_onset = row["wind_first_two_month_positive_start"]
        onset_rows.append(
            "| {year} | {ohc} | {wind} | {lag} | {omax:+.2f} | {umax:+.2f} |".format(
                year=int(row["year"]),
                ohc="无" if pd.isna(ohc_onset) else MONTH_LABELS[int(ohc_onset)],
                wind="无" if pd.isna(wind_onset) else MONTH_LABELS[int(wind_onset)],
                lag="—" if pd.isna(row["wind_minus_ohc_onset_months"]) else f"{int(row['wind_minus_ohc_onset_months']):+d}",
                omax=row["ohc_jan_jun_max_gj_m2"],
                umax=row["wind_jan_jun_max_ms"],
            )
        )
    report = f"""# SODA3热含量—海气耦合时间检验

## 设定

仍然只使用两个量：中太平洋0—300米OHC距平与中西太平洋U850距平。对13个暖事件逐月检验同期、领先1个月和领先2个月的关系。

## 滞后扫描

| OHC月份 | U850月份 | 滞后（月） | Pearson r | FDR q |
|---|---|---:|---:|---:|
{chr(10).join(lag_rows)}

最高的单月相关出现在 **{MONTH_LABELS[int(best['ohc_month'])]} OHC与{MONTH_LABELS[int(best['wind_month'])]} U850同期**，r={best['pearson_r']:.2f}。但3月OHC→4月U850和4月OHC→6月U850也很强。因此月资料没有给出唯一的“OHC先、大气后”的顺序，而是把关键时间压缩到了 **3—4月耦合检查点**。

## “持续转正”检验

| 事件 | OHC首次连续两月为正 | U850首次连续两月为正 | 月差 | OHC最大值 | U850最大值 |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(onset_rows)}

简单的“连续两个月大于零”不能作为转变阈值：2002和2023也很早出现正OHC或正U850，但幅度小且不稳定；只有1997形成强而持续的中太平洋蓄热和西风响应。

## 阶段判断

目前能够定位的是 **3—4月、180°–140°W的中太平洋春季检查点**，而不是一个已经证实的精确数值阈值。OHC是重要的海洋准备条件，但月资料显示它与西风在春季几乎同步增强，不能仅凭相关关系判定OHC单向触发大气。

下一步仍不增加变量：用逐事件留一法寻找“能够稳定区分强西风和弱西风”的OHC幅度区间，并明确这个区间的不确定性；若区间不能稳定复现，就停止追求单一阈值，改称春季OHC检查点。
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ocean, wind, events = load_monthly_matrices()
    lag = lag_scan(ocean, wind)
    onset = onset_table(ocean, wind, events)
    diagnostics = build_diagnostics(lag, onset)
    lag.to_csv(LAG_CSV, index=False)
    onset.to_csv(ONSET_CSV, index=False)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    make_figure(ocean, wind, lag, onset)
    write_report(lag, onset, diagnostics)
    print(f"Wrote {LAG_CSV}")
    print(f"Wrote {ONSET_CSV}")
    print(f"Wrote {DIAGNOSTICS_JSON}")
    print(f"Wrote {FIG_PNG}")
    print(f"Wrote {FIG_PDF}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
