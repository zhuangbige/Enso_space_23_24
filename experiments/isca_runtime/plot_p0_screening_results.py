"""Create manuscript-ready figures from the verified Isca P0 screening tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CASES = ("ia0_fep0", "ia0_fep1", "ia1_fep0", "ia1_fep1")
CASE_LABELS = {
    "ia0_fep0": "IA0 FEP0",
    "ia0_fep1": "IA0 FEP1",
    "ia1_fep0": "IA1 FEP0",
    "ia1_fep1": "IA1 FEP1",
}
CASE_COLORS = {
    "ia0_fep0": "#4b5563",
    "ia0_fep1": "#2b6cb0",
    "ia1_fep0": "#d97706",
    "ia1_fep1": "#7c3aed",
}
CONTRASTS = (
    "FEP_at_IA0",
    "FEP_at_IA1",
    "IA_at_FEP0",
    "IA_at_FEP1",
    "IA_x_FEP",
)
CONTRAST_LABELS = {
    "FEP_at_IA0": "FEP | IA0",
    "FEP_at_IA1": "FEP | IA1",
    "IA_at_FEP0": "IA | FEP0",
    "IA_at_FEP1": "IA | FEP1",
    "IA_x_FEP": "IA × FEP",
}
CONTRAST_COLORS = {
    "FEP_at_IA0": "#63a7d8",
    "FEP_at_IA1": "#2367a2",
    "IA_at_FEP0": "#efb05a",
    "IA_at_FEP1": "#c96b1f",
    "IA_x_FEP": "#7c3aed",
}
METRICS = (
    "precip_tp_mm_day",
    "precip_cp_mm_day",
    "olr_cp_w_m2",
    "peng_cwp_u10_m_s",
    "tau_cwp_ocean_n_m2",
    "slp_drive_w_minus_e_hpa",
)
METRIC_LABELS = {
    "precip_tp_mm_day": "Tropical Pacific precipitation\n(mm day$^{-1}$)",
    "precip_cp_mm_day": "Central Pacific precipitation\n(mm day$^{-1}$)",
    "olr_cp_w_m2": "−Central Pacific OLR\n(W m$^{-2}$)",
    "peng_cwp_u10_m_s": "Peng CWP $u_{10}$\n(m s$^{-1}$)",
    "tau_cwp_ocean_n_m2": "CWP eastward ocean stress\n(N m$^{-2}$)",
    "slp_drive_w_minus_e_hpa": "West-minus-east SLP drive\n(hPa)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 180,
            "savefig.dpi": 400,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "font.size": 8.7,
            "axes.titlesize": 9.4,
            "axes.labelsize": 8.7,
            "legend.fontsize": 8.0,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def transformed(metric: str, values: pd.Series | np.ndarray) -> pd.Series | np.ndarray:
    return -values if metric == "olr_cp_w_m2" else values


def validate_monthly(monthly: pd.DataFrame) -> None:
    missing_columns = sorted(
        set(("case", "member", "month", *METRICS)) - set(monthly.columns)
    )
    if missing_columns:
        raise ValueError(f"monthly table is missing columns: {missing_columns}")
    cases = set(monthly["case"].unique())
    if cases != set(CASES):
        raise ValueError(f"expected cases {CASES}, found {sorted(cases)}")
    if len(monthly) != len(CASES) * 10 * 6:
        raise ValueError(f"expected 240 monthly rows, found {len(monthly)}")
    if set(monthly["month"].unique()) != set(range(3, 9)):
        raise ValueError(
            f"expected March-August months 3-8, found {sorted(monthly['month'].unique())}"
        )
    if set(monthly["member"].unique()) != set(range(1, 11)):
        raise ValueError(
            f"expected members 1-10, found {sorted(monthly['member'].unique())}"
        )
    duplicate = monthly.duplicated(["case", "member", "month"], keep=False)
    if bool(duplicate.any()):
        keys = monthly.loc[duplicate, ["case", "member", "month"]].to_dict("records")
        raise ValueError(f"duplicate case-member-month rows: {keys[:10]}")
    values = monthly.loc[:, METRICS].to_numpy(float)
    if not bool(np.isfinite(values).all()):
        raise ValueError("monthly metrics contain NaN or infinity")
    counts = monthly.groupby(["case", "month"])["member"].nunique()
    if counts.empty or counts.nunique() != 1 or int(counts.iloc[0]) != 10:
        raise ValueError(f"expected 10 members per case-month, found {counts.to_dict()}")


def validate_summary(summary: pd.DataFrame) -> None:
    required = {
        "metric",
        "contrast",
        "mean",
        "ci95_low",
        "ci95_high",
        "n_members",
    }
    missing = sorted(required - set(summary.columns))
    if missing:
        raise ValueError(f"factorial summary is missing columns: {missing}")
    expected = {(metric, contrast) for metric in METRICS for contrast in CONTRASTS}
    found = set(zip(summary["metric"], summary["contrast"]))
    if found != expected or len(summary) != len(expected):
        raise ValueError(
            f"expected one row for each of {len(expected)} metric-contrast pairs"
        )
    if not bool((summary["n_members"] == 10).all()):
        raise ValueError(
            f"expected n_members=10 throughout, found {sorted(summary['n_members'].unique())}"
        )
    values = summary[["mean", "ci95_low", "ci95_high"]].to_numpy(float)
    if not bool(np.isfinite(values).all()):
        raise ValueError("factorial summary contains NaN or infinity")
    if bool((summary["ci95_low"] > summary["mean"]).any()) or bool(
        (summary["mean"] > summary["ci95_high"]).any()
    ):
        raise ValueError("factorial summary has a mean outside its 95% interval")


def save_both(fig: plt.Figure, output: Path, stem: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / f"{stem}.png", dpi=400, bbox_inches="tight")
    fig.savefig(output / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def monthly_response_figure(monthly: pd.DataFrame, output: Path) -> None:
    index = ["member", "month"]
    wide = monthly.pivot(index=index, columns="case", values=list(METRICS))
    months = np.arange(3, 9)
    fig, axes = plt.subplots(2, 3, figsize=(10.8, 6.7), sharex=True)
    fig.suptitle(
        "P0 prescribed-SST response relative to IA0 FEP0",
        fontsize=13,
        fontweight="bold",
        y=0.985,
    )

    for panel, (ax, metric) in enumerate(zip(axes.ravel(), METRICS)):
        for case in CASES:
            if case == "ia0_fep0":
                mean = np.zeros(len(months))
                low = mean
                high = mean
            else:
                differences = wide[metric][case] - wide[metric]["ia0_fep0"]
                differences = transformed(metric, differences).rename("value").reset_index()
                grouped = differences.groupby("month")["value"]
                mean = grouped.mean().reindex(months).to_numpy(float)
                sd = grouped.std(ddof=1).reindex(months).to_numpy(float)
                n = grouped.count().reindex(months).to_numpy(float)
                half_width = 1.96 * sd / np.sqrt(n)
                low, high = mean - half_width, mean + half_width
            ax.plot(
                months,
                mean,
                marker="o",
                markersize=3.5,
                color=CASE_COLORS[case],
                label=CASE_LABELS[case],
                zorder=3,
            )
            if case != "ia0_fep0":
                ax.fill_between(months, low, high, color=CASE_COLORS[case], alpha=0.13)

        ax.axhline(0.0, color="#374151", linewidth=0.8, zorder=1)
        ax.axvspan(4.5, 7.5, color="#dcefe5", alpha=0.48, zorder=0)
        ax.set_title(f"{chr(97 + panel)}  {METRIC_LABELS[metric]}", loc="left", fontweight="bold")
        ax.grid(axis="y", color="#d1d5db", linewidth=0.55, alpha=0.75)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xticks(months, ("Mar", "Apr", "May", "Jun", "Jul", "Aug"))

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 0.925), frameon=False)
    fig.text(0.5, 0.025, "Model calendar month; green shading marks MJJ", ha="center")
    fig.text(
        0.01,
        0.01,
        "Lines are paired ensemble means; shading is mean ± 1.96 SE (n=10). Positive −OLR denotes stronger convection.",
        fontsize=7.2,
        color="#4b5563",
    )
    fig.subplots_adjust(left=0.08, right=0.985, bottom=0.11, top=0.80, hspace=0.36, wspace=0.28)
    save_both(fig, output, "fig_p0_monthly_paired_response")


def factorial_effect_figure(summary: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(10.8, 6.5))
    fig.suptitle(
        "MJJ paired factorial effects in the P0 prescribed-SST ensemble",
        fontsize=13,
        fontweight="bold",
        y=0.985,
    )
    y = np.arange(len(CONTRASTS))

    for panel, (ax, metric) in enumerate(zip(axes.ravel(), METRICS)):
        current = summary.loc[summary["metric"].eq(metric)].set_index("contrast").reindex(CONTRASTS)
        if current[["mean", "ci95_low", "ci95_high"]].isna().any().any():
            raise ValueError(f"incomplete contrasts for {metric}")
        mean = transformed(metric, current["mean"]).to_numpy(float)
        if metric == "olr_cp_w_m2":
            low = (-current["ci95_high"]).to_numpy(float)
            high = (-current["ci95_low"]).to_numpy(float)
        else:
            low = current["ci95_low"].to_numpy(float)
            high = current["ci95_high"].to_numpy(float)
        xerr = np.vstack((mean - low, high - mean))
        for position, contrast in enumerate(CONTRASTS):
            ax.errorbar(
                mean[position],
                position,
                xerr=xerr[:, position : position + 1],
                fmt="o",
                markersize=5.5 if contrast == "IA_x_FEP" else 4.5,
                color=CONTRAST_COLORS[contrast],
                ecolor=CONTRAST_COLORS[contrast],
                elinewidth=1.3,
                capsize=2.5,
                zorder=3,
            )
        ax.axvline(0.0, color="#374151", linewidth=0.85)
        ax.set_yticks(y, [CONTRAST_LABELS[name] for name in CONTRASTS])
        ax.invert_yaxis()
        ax.set_title(f"{chr(97 + panel)}  {METRIC_LABELS[metric]}", loc="left", fontweight="bold")
        ax.grid(axis="x", color="#d1d5db", linewidth=0.55, alpha=0.75)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)

    fig.text(
        0.5,
        0.02,
        "Points are paired-member MJJ means; bars are member-bootstrap 95% intervals (n=10). Positive −OLR denotes stronger convection.",
        ha="center",
        fontsize=7.5,
        color="#4b5563",
    )
    fig.subplots_adjust(left=0.15, right=0.985, bottom=0.10, top=0.82, hspace=0.40, wspace=0.38)
    save_both(fig, output, "fig_p0_mjj_factorial_effects")


def main() -> None:
    args = parse_args()
    setup_style()
    monthly = pd.read_csv(args.input / "p0_monthly_metrics.csv")
    summary = pd.read_csv(args.input / "p0_mjj_factorial_summary.csv")
    validate_monthly(monthly)
    validate_summary(summary)
    monthly_response_figure(monthly, args.output)
    factorial_effect_figure(summary, args.output)
    print(f"P0_FIGURES_COMPLETE output={args.output}")


if __name__ == "__main__":
    main()
