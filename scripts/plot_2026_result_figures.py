#!/usr/bin/env python3
"""Create presentation-ready figures for the current 2026 ENSO/FEP diagnostics."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "outputs/research_2026/mplconfig"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import text as mtext
import pandas as pd

MONTHLY = ROOT / "data/interim/research_2026/current_2026_monthly_indices.csv"
OISST_NINO3 = ROOT / "data/interim/research_2026/oisst_nino3_monthly_1982_2026m05.csv"
FEP = ROOT / "data/derived/research_2026/current_2026_fep_residual.csv"
EXPECTED = ROOT / "data/derived/research_2026/current_2026_regression_expected_response.csv"
OUT_DIR = ROOT / "outputs/research_2026/figures"
ANOMALY_LABEL = "1982-2022 baseline"
ANOMALY_NOTE = ANOMALY_LABEL


MONTH_LABELS = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May"}
CN_MONTH_LABELS = {1: "1月", 2: "2月", 3: "3月", 4: "4月", 5: "5月"}

CN_FONT_PATHS = [
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
]


def setup_style() -> None:
    for font_path in CN_FONT_PATHS:
        if font_path.exists():
            fm.fontManager.addfont(str(font_path))

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "DejaVu Sans",
                "STHeiti",
                "PingFang SC",
                "Hiragino Sans GB",
                "Arial Unicode MS",
            ],
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "legend.fontsize": 9,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "axes.linewidth": 0.9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
        }
    )


def cn_font() -> fm.FontProperties | None:
    for font_path in CN_FONT_PATHS:
        if font_path.exists():
            return fm.FontProperties(fname=str(font_path))
    return None


def apply_cn_font(fig: plt.Figure) -> None:
    font = cn_font()
    if font is None:
        return
    for item in fig.findobj(match=mtext.Text):
        item.set_fontproperties(font)


def _series(df: pd.DataFrame, metric: str, region: str, year: int = 2026) -> pd.DataFrame:
    return df.loc[
        (df["metric"] == metric) & (df["region"] == region) & (df["year"] == year)
    ].sort_values("month")


def save(fig: plt.Figure, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.png", bbox_inches="tight", pad_inches=0.18)
    fig.savefig(OUT_DIR / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.18)
    print(OUT_DIR / f"{stem}.png")
    print(OUT_DIR / f"{stem}.pdf")


def plot_sst_fep(monthly: pd.DataFrame, fep: pd.DataFrame, oisst: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.1), constrained_layout=True)
    fig.suptitle("2026 Pacific SST development: eastern-Pacific warming and positive FEP residual", weight="bold")

    ax = axes[0]
    for region, label, color in [
        ("nino34", "Nino-3.4 (ERSSTv5)", "#222222"),
        ("nino3", "Nino-3 (ERSSTv5)", "#c44e52"),
        ("fep", "FEP 90W-80W (ERSSTv5)", "#2b7b9f"),
        ("nino12", "Nino-1+2 (ERSSTv5)", "#6a9f58"),
    ]:
        data = _series(monthly, "ersstv5_sst", region)
        ax.plot(data["month"], data["anomaly"], marker="o", lw=2.2, label=label, color=color)

    oisst_2026 = oisst.loc[oisst["year"] == 2026].sort_values("month")
    ax.plot(
        oisst_2026["month"],
        oisst_2026["anomaly"],
        ls="--",
        marker="x",
        lw=1.6,
        color="#c44e52",
        label="Nino-3 (OISST check)",
    )
    ax.axhline(0, color="0.25", lw=0.9)
    ax.fill_between([4, 5], -0.75, 2.1, color="#e8d7b2", alpha=0.35, zorder=0)
    ax.text(4.5, 1.95, "AM-to-date", ha="center", va="top", fontsize=9, color="0.35")
    ax.set_xlim(0.8, 5.2)
    ax.set_ylim(-0.75, 2.05)
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels([MONTH_LABELS[m] for m in range(1, 6)])
    ax.set_ylabel(f"SST anomaly (deg C; {ANOMALY_LABEL})")
    ax.set_title("SST indices through May 2026")
    ax.grid(True, color="0.88", lw=0.7)
    ax.legend(frameon=False, ncol=2, loc="upper left")

    ax = axes[1]
    fep_plot = fep.loc[fep["period"].isin(["JAN", "FEB", "MAR", "APR", "MAY"])].copy()
    x = list(range(len(fep_plot)))
    ax.bar([i - 0.18 for i in x], fep_plot["fep_observed_2026"], width=0.36, color="#4d7f9f", label="Observed FEP")
    ax.bar([i + 0.18 for i in x], fep_plot["fep_expected_from_nino34"], width=0.36, color="#d8a657", label="Expected from Nino-3.4")
    ax.plot(x, fep_plot["fep_residual"], marker="o", color="#1e6a63", lw=2.2, label="Residual FEP")
    for i, row in enumerate(fep_plot.itertuples()):
        ax.text(i, row.fep_residual + 0.07, f"{row.fep_residual:.2f}", ha="center", va="bottom", fontsize=8, color="#1e6a63")
    ax.axhline(0, color="0.25", lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May"])
    ax.set_ylabel("FEP SST anomaly (deg C)")
    ax.set_title("FEP is warmer than Nino-3.4 expectation from February onward")
    ax.grid(True, axis="y", color="0.88", lw=0.7)
    ax.legend(frameon=False, loc="upper left")

    fig.text(
        0.01,
        -0.035,
        "Data: ERSSTv5 SST; OISST v2.1 cross-check for Nino-3. "
        "FEP residual = observed FEP minus value expected from historical Nino-3.4 regression. "
        f"Anomalies: {ANOMALY_NOTE}.",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig1_2026_sst_fep_residual")
    plt.close(fig)


def plot_atmosphere(monthly: pd.DataFrame, expected: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.1), constrained_layout=True)
    fig.suptitle("2026 available atmospheric response: precipitation remains weaker than SST would suggest", weight="bold")

    ax = axes[0]
    cp = _series(monthly, "gpcp_precip", "central_pacific_180_140w")
    cwp = _series(monthly, "gpcp_precip", "cwp_160e_140w")
    soi = _series(monthly, "ncep_soi_like_slp", "tahiti_minus_darwin")
    x = cp["month"].tolist()
    ax.bar([m - 0.16 for m in x], cp["anomaly"], width=0.32, color="#2f8378", label="GPCP central Pacific")
    ax.bar([m + 0.16 for m in cwp["month"]], cwp["anomaly"], width=0.32, color="#a46e3c", label="GPCP central-west Pacific")
    ax.axhline(0, color="0.25", lw=0.9)
    ax.set_xlim(0.6, 3.4)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Jan", "Feb", "Mar"])
    ax.set_ylabel("Precipitation anomaly (mm/day)")
    ax.set_title("GPCP rainfall: suppressed through March")
    ax.grid(True, axis="y", color="0.88", lw=0.7)
    ax.legend(frameon=False, loc="upper left")

    ax2 = ax.twinx()
    ax2.plot(soi["month"], soi["anomaly"], marker="s", color="#4b4b9f", lw=2.0, label="SOI-like SLP")
    ax2.set_ylabel("Tahiti-Darwin SLP anomaly (hPa)")
    ax2.spines["right"].set_visible(True)
    ax2.legend(frameon=False, loc="upper right")

    ax = axes[1]
    plot_rows = expected.loc[
        (expected["response_metric"] == "gpcp_precip")
        & (expected["response_region"] == "central_pacific_180_140w")
        & expected["period"].isin(["JAN", "FEB", "MAR", "JFM"])
    ].copy()
    x = list(range(len(plot_rows)))
    ax.bar([i - 0.18 for i in x], plot_rows["observed_2026"], width=0.36, color="#2f8378", label="Observed")
    ax.bar([i + 0.18 for i in x], plot_rows["expected_from_regression"], width=0.36, color="#d8a657", label="Expected from Nino-3")
    for i, row in enumerate(plot_rows.itertuples()):
        resid = row.residual_observed_minus_expected
        y = row.observed_2026 + 0.14 if row.observed_2026 < 0 else row.observed_2026 - 0.14
        va = "bottom" if row.observed_2026 < 0 else "top"
        ax.text(i, y, f"resid {resid:.2f}", ha="center", va=va, fontsize=8, color="0.25")
    ax.axhline(0, color="0.25", lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(plot_rows["period"])
    ax.set_ylabel("Central Pacific precip anomaly (mm/day)")
    ax.set_title("Observed CP rainfall is below regression expectation")
    ax.grid(True, axis="y", color="0.88", lw=0.7)
    ax.legend(frameon=False)

    fig.text(
        0.01,
        -0.035,
        "Data availability: GPCP monthly precipitation through March 2026; NCEP/NCAR SLP through February 2026. "
        "NCEP sigma995 u is missing/NaN for current 2026 months. "
        f"Anomalies: {ANOMALY_NOTE}.",
        fontsize=8.5,
        color="0.28",
    )
    save(fig, "fig2_2026_atmospheric_response")
    plt.close(fig)


def plot_cn_summary(monthly: pd.DataFrame, fep: pd.DataFrame, expected: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.8), constrained_layout=True)
    fig.suptitle("2026年当前快速诊断：东太平洋增暖已出现，但降水/气压响应尚未同步", weight="bold")

    ax = axes[0, 0]
    for region, label, color in [
        ("nino34", "Niño-3.4", "#222222"),
        ("nino3", "Niño-3", "#c44e52"),
        ("fep", "FEP", "#2b7b9f"),
        ("nino12", "Niño1+2", "#6a9f58"),
    ]:
        data = _series(monthly, "ersstv5_sst", region)
        ax.plot(data["month"], data["anomaly"], marker="o", lw=2.0, label=label, color=color)
    ax.axhline(0, color="0.25", lw=0.8)
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels([CN_MONTH_LABELS[m] for m in range(1, 6)])
    ax.set_ylabel("SST异常 (°C)")
    ax.set_title("海温：2-5月东太平洋/FEP快速转暖")
    ax.grid(True, color="0.88", lw=0.7)
    ax.legend(frameon=False, ncol=2)

    ax = axes[0, 1]
    fep_plot = fep.loc[fep["period"].isin(["JAN", "FEB", "MAR", "APR", "MAY"])].copy()
    x = list(range(len(fep_plot)))
    ax.bar([i - 0.18 for i in x], fep_plot["fep_observed_2026"], width=0.36, color="#4d7f9f", label="FEP实际")
    ax.bar([i + 0.18 for i in x], fep_plot["fep_expected_from_nino34"], width=0.36, color="#d8a657", label="Niño-3.4预期")
    ax.plot(x, fep_plot["fep_residual"], marker="o", color="#1e6a63", lw=2.0, label="FEP残差")
    ax.axhline(0, color="0.25", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(["1月", "2月", "3月", "4月", "5月"])
    ax.set_ylabel("FEP SST异常 (°C)")
    ax.set_title("FEP residual：2月后持续为正")
    ax.grid(True, axis="y", color="0.88", lw=0.7)
    ax.legend(frameon=False)

    ax = axes[1, 0]
    cp = _series(monthly, "gpcp_precip", "central_pacific_180_140w")
    cwp = _series(monthly, "gpcp_precip", "cwp_160e_140w")
    soi = _series(monthly, "ncep_soi_like_slp", "tahiti_minus_darwin")
    ax.bar(cp["month"] - 0.16, cp["anomaly"], width=0.32, color="#2f8378", label="中太平洋降水")
    ax.bar(cwp["month"] + 0.16, cwp["anomaly"], width=0.32, color="#a46e3c", label="中西太降水")
    ax.axhline(0, color="0.25", lw=0.8)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["1月", "2月", "3月"])
    ax.set_ylabel("降水异常 (mm/day)")
    ax.set_title("降水：1-3月仍显著偏弱")
    ax.grid(True, axis="y", color="0.88", lw=0.7)
    ax.legend(frameon=False, loc="upper left")
    ax2 = ax.twinx()
    ax2.plot(soi["month"], soi["anomaly"], marker="s", color="#4b4b9f", lw=2.0, label="SOI-like SLP")
    ax2.set_ylabel("Tahiti-Darwin SLP异常 (hPa)")
    ax2.spines["right"].set_visible(True)
    ax2.legend(frameon=False, loc="upper right")

    ax = axes[1, 1]
    plot_rows = expected.loc[
        (expected["response_metric"] == "gpcp_precip")
        & (expected["response_region"] == "central_pacific_180_140w")
        & expected["period"].isin(["JAN", "FEB", "MAR", "JFM"])
    ].copy()
    x = list(range(len(plot_rows)))
    ax.bar([i - 0.18 for i in x], plot_rows["observed_2026"], width=0.36, color="#2f8378", label="实际")
    ax.bar([i + 0.18 for i in x], plot_rows["expected_from_regression"], width=0.36, color="#d8a657", label="Niño-3回归预期")
    ax.axhline(0, color="0.25", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(["1月", "2月", "3月", "JFM"])
    ax.set_ylabel("中太平洋降水异常 (mm/day)")
    ax.set_title("实际降水低于海温回归预期")
    ax.grid(True, axis="y", color="0.88", lw=0.7)
    ax.legend(frameon=False)

    fig.text(
        0.01,
        -0.03,
        f"资料：ERSSTv5/OISST SST至2026年5月；GPCP降水至2026年3月；NCEP SLP至2026年2月。异常处理：{ANOMALY_NOTE}。",
        fontsize=8.5,
        color="0.28",
    )
    apply_cn_font(fig)
    save(fig, "fig3_2026_cn_summary")
    plt.close(fig)


def main() -> int:
    setup_style()
    monthly = pd.read_csv(MONTHLY)
    oisst = pd.read_csv(OISST_NINO3)
    fep = pd.read_csv(FEP)
    expected = pd.read_csv(EXPECTED)
    plot_sst_fep(monthly, fep, oisst)
    plot_atmosphere(monthly, expected)
    plot_cn_summary(monthly, fep, expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
