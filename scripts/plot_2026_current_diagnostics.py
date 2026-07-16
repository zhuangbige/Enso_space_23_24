#!/usr/bin/env python3
"""Plot current 2026 lightweight ENSO/FEP coupling diagnostics."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MONTHLY = ROOT / "data/interim/research_2026/current_2026_monthly_indices.csv"
EXPECTED = ROOT / "data/derived/research_2026/current_2026_regression_expected_response.csv"
FEP = ROOT / "data/derived/research_2026/current_2026_fep_residual.csv"
OUT_DIR = ROOT / "outputs/research_2026"
ANOMALY_LABEL = "anomaly vs 1982-2022"
ANOMALY_NOTE = ANOMALY_LABEL


def _series(df: pd.DataFrame, metric: str, region: str) -> pd.DataFrame:
    return df.loc[
        (df["metric"] == metric) & (df["region"] == region) & (df["year"] == 2026)
    ].sort_values("month")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_csv(MONTHLY)
    expected = pd.read_csv(EXPECTED) if EXPECTED.exists() else pd.DataFrame()
    fep = pd.read_csv(FEP)

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "legend.fontsize": 8,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "axes.linewidth": 0.8,
        }
    )

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    fig.suptitle("2026 quick-look: ENSO/FEP development and available atmospheric response", weight="bold")

    ax = axes[0, 0]
    for region, label, color in [
        ("nino34", "Nino-3.4", "#202020"),
        ("nino3", "Nino-3", "#b94a48"),
        ("fep", "FEP", "#2d6f8f"),
        ("nino12", "Nino-1+2", "#6a9f58"),
    ]:
        data = _series(monthly, "ersstv5_sst", region)
        ax.plot(data["month"], data["anomaly"], marker="o", label=label, color=color, lw=1.8)
    ax.axhline(0, color="0.25", lw=0.8)
    ax.set_title(f"Pacific SST indices (ERSSTv5; {ANOMALY_LABEL})")
    ax.set_ylabel("deg C")
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May"])
    ax.grid(True, color="0.88", lw=0.6)
    ax.legend(ncol=2, frameon=False)

    ax = axes[0, 1]
    fep_plot = fep.loc[fep["period"].isin(["JAN", "FEB", "MAR", "APR", "MAY"])].copy()
    x = range(len(fep_plot))
    ax.bar([i - 0.18 for i in x], fep_plot["fep_observed_2026"], width=0.36, label="Observed FEP", color="#4c7899")
    ax.bar([i + 0.18 for i in x], fep_plot["fep_expected_from_nino34"], width=0.36, label="Expected from Nino-3.4", color="#d7a45b")
    ax.plot(x, fep_plot["fep_residual"], marker="o", color="#1f5f5b", label="Residual FEP")
    ax.axhline(0, color="0.25", lw=0.8)
    ax.set_title("FEP residual following Jiang et al. GRL logic")
    ax.set_ylabel("deg C")
    ax.set_xticks(list(x))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May"])
    ax.grid(True, axis="y", color="0.88", lw=0.6)
    ax.legend(frameon=False)

    ax = axes[1, 0]
    cp = _series(monthly, "gpcp_precip", "central_pacific_180_140w")
    cwp = _series(monthly, "gpcp_precip", "cwp_160e_140w")
    soi = _series(monthly, "ncep_soi_like_slp", "tahiti_minus_darwin")
    ax.bar(cp["month"] - 0.15, cp["anomaly"], width=0.3, label="GPCP CP precip", color="#2f7f78")
    ax.bar(cwp["month"] + 0.15, cwp["anomaly"], width=0.3, label="GPCP CWP precip", color="#9b6b3d")
    ax2 = ax.twinx()
    ax2.plot(soi["month"], soi["anomaly"], marker="s", color="#4b4b9f", label="NCEP SOI-like SLP")
    ax.axhline(0, color="0.25", lw=0.8)
    ax2.axhline(0, color="0.5", lw=0.6, ls="--")
    ax.set_title("Available atmospheric indices: precip through Mar; SLP through Feb")
    ax.set_ylabel("precip anomaly (mm/day)")
    ax2.set_ylabel("Tahiti-Darwin SLP anomaly (hPa)")
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May"])
    ax.grid(True, axis="y", color="0.88", lw=0.6)
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, frameon=False, loc="lower right")

    ax = axes[1, 1]
    if not expected.empty:
        plot_rows = expected.loc[
            (expected["response_metric"] == "gpcp_precip")
            & (expected["response_region"] == "central_pacific_180_140w")
            & expected["period"].isin(["JAN", "FEB", "MAR", "JFM"])
        ].copy()
        x = range(len(plot_rows))
        ax.bar([i - 0.18 for i in x], plot_rows["observed_2026"], width=0.36, color="#2f7f78", label="Observed")
        ax.bar([i + 0.18 for i in x], plot_rows["expected_from_regression"], width=0.36, color="#d7a45b", label="Expected")
        ax.axhline(0, color="0.5", lw=0.6)
        ax.set_xticks(list(x))
        ax.set_xticklabels(plot_rows["period"])
        ax.set_ylabel("CP precipitation anomaly (mm/day)")
        ax.set_title("GPCP CP precipitation: observed vs Nino-3 expected")
        ax.grid(True, axis="y", color="0.88", lw=0.6)
        ax.legend(frameon=False)
    else:
        ax.text(0.5, 0.5, "No expected-response table", ha="center", va="center")
        ax.axis("off")

    note = (
        "Data: ERSSTv5 SST through May 2026; GPCP precip through Mar 2026; "
        "NCEP SLP through Feb 2026. "
        f"Anomalies: {ANOMALY_NOTE}."
    )
    fig.text(0.01, 0.005, note, fontsize=8, color="0.25")
    png = OUT_DIR / "current_2026_quicklook_diagnostics.png"
    pdf = OUT_DIR / "current_2026_quicklook_diagnostics.pdf"
    fig.savefig(png, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    print(png)
    print(pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
