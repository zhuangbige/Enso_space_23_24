#!/usr/bin/env python3
"""Create a claim-first Chinese summary figure for the three FEP findings."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVENT_CSV = ROOT / "data/derived/research_2026/pre1980_fep_vs_1997_2023_event_diagnostics.csv"
OUTDIR = ROOT / "outputs/research_2026/pre1980_fep_universality"
PNG_OUT = OUTDIR / "three_findings_explained_cn.png"
SVG_OUT = OUTDIR / "three_findings_explained_cn.svg"

EARLY = ("1965/66", "1969/70", "1972/73", "1976/77")
COLORS = {
    "early": "#58A6A6",
    "early_dark": "#26747B",
    "y1997": "#D44F3A",
    "y2023": "#315F9E",
    "ink": "#17202A",
    "muted": "#596773",
    "grid": "#D9E1E7",
    "good": "#DDEFE8",
    "bad": "#F6DDD8",
}


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": ["Arial Unicode MS", "Songti SC", "DejaVu Sans"],
            "font.size": 10.5,
            "axes.titlesize": 12.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.5,
            "axes.edgecolor": "#687680",
            "axes.linewidth": 0.8,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.dpi": 300,
            "axes.unicode_minus": False,
        }
    )


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.08,
        1.09,
        label,
        transform=ax.transAxes,
        fontsize=13,
        fontweight="bold",
        ha="left",
        va="top",
        color=COLORS["ink"],
    )


def plot_ocean_structure(ax: plt.Axes, df: pd.DataFrame) -> None:
    early = df[df["event"].isin(EARLY)]
    values = np.array(
        [
            early["d20_east_minus_west_m"].mean(),
            df.loc[df["event"] == "2023/24", "d20_east_minus_west_m"].iloc[0],
            df.loc[df["event"] == "1997/98", "d20_east_minus_west_m"].iloc[0],
        ]
    )
    x = np.arange(3)
    bars = ax.bar(
        x,
        values,
        width=0.62,
        color=[COLORS["early"], COLORS["y2023"], COLORS["y1997"]],
        alpha=0.92,
        edgecolor="white",
        linewidth=1.0,
        zorder=2,
    )
    jitter = np.array([-0.16, -0.055, 0.055, 0.16])
    ax.scatter(
        jitter,
        early["d20_east_minus_west_m"],
        s=38,
        facecolor="white",
        edgecolor=COLORS["early_dark"],
        linewidth=1.2,
        zorder=4,
        label="四次早期事件",
    )
    for b, val in zip(bars, values):
        ax.text(
            b.get_x() + b.get_width() / 2,
            val + 2.3,
            f"{val:.1f} m",
            ha="center",
            va="bottom",
            fontweight="bold",
            color=COLORS["ink"],
        )
    ax.annotate(
        "仅相差 2.2 m",
        xy=(0.5, 34.0),
        xytext=(0.5, 49),
        ha="center",
        color=COLORS["early_dark"],
        fontsize=10,
        arrowprops={"arrowstyle": "-[,widthB=3.0,lengthB=0.5", "lw": 1.2, "color": COLORS["early_dark"]},
    )
    ax.text(
        2,
        57,
        "约为早期合成的 2.3 倍",
        ha="center",
        va="center",
        color=COLORS["y1997"],
        fontsize=9.8,
        fontweight="bold",
    )
    ax.set_xticks(x, ["早期四事件\n合成", "2023/24", "1997/98"])
    ax.set_ylabel("MJJ D20 东部减西部异常（m）")
    ax.set_ylim(0, 84)
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.set_title("海洋结构具有重复性", loc="left", pad=12)
    ax.text(
        0.0,
        -0.25,
        "早期合成与2023都表现为较局地的东部温跃层调整；\n1997则是更强的盆地尺度倾斜。",
        transform=ax.transAxes,
        color=COLORS["muted"],
        fontsize=9.5,
        va="top",
    )
    panel_label(ax, "a")


def plot_atmospheric_chain(ax: plt.Axes, df: pd.DataFrame) -> None:
    early = df.set_index("event").loc[list(EARLY)]
    values = np.column_stack(
        [
            early["d20_east_minus_west_m"].values,
            early["precip_meridional_dipole_mmday"].values,
            early["northeasterly_index_ms"].values,
            -early["u925_residual_from_nino34"].values,
        ]
    )
    signs = np.where(values > 0, 1, -1)
    cmap = ListedColormap([COLORS["bad"], COLORS["good"]])
    ax.imshow(signs, cmap=cmap, vmin=-1, vmax=1, aspect="auto")

    formats = ["{:+.1f}", "{:+.2f}", "{:+.2f}", "{:+.2f}"]
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(
                j,
                i,
                formats[j].format(values[i, j]),
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold" if signs[i, j] > 0 else "normal",
                color="#1D4C3F" if signs[i, j] > 0 else "#8A3026",
            )

    outcomes = ["大气端失败", "完整", "完整（较弱）", "部分"]
    outcome_colors = [COLORS["y1997"], "#21835B", "#21835B", "#B77716"]
    for i, (text, color) in enumerate(zip(outcomes, outcome_colors)):
        ax.text(4.05, i, text, ha="left", va="center", color=color, fontweight="bold", fontsize=9.5)

    ax.set_xticks(
        range(4),
        ["D20东-西\n(m)", "降水偶极\n(mm d⁻¹)", "东北风指数\n(m s⁻¹)", "弱风支持\n−风残差 (m s⁻¹)"],
    )
    ax.set_yticks(range(4), list(EARLY))
    ax.tick_params(length=0)
    ax.set_xlim(-0.5, 5.2)
    ax.set_title("大气响应不具有严格普适性", loc="left", pad=12)
    ax.text(
        0.0,
        -0.25,
        "绿色表示该环节方向支持2023式链条；只有1969和1972四项同时成立。\n1965并非没有东部海洋异常，而是东北风和弱风环节失败。",
        transform=ax.transAxes,
        color=COLORS["muted"],
        fontsize=9.5,
        va="top",
    )
    panel_label(ax, "b")


def plot_fep_not_sufficient(ax: plt.Axes, df: pd.DataFrame) -> None:
    early = df[df["event"].isin(EARLY)]
    ax.scatter(
        early["fep_residual_c"],
        early["u925_residual_from_nino34"],
        s=55,
        color=COLORS["early"],
        edgecolor="white",
        linewidth=0.8,
        zorder=3,
    )
    for _, row in early.iterrows():
        ax.annotate(row["event"][:4], (row["fep_residual_c"], row["u925_residual_from_nino34"]), xytext=(5, 5), textcoords="offset points", fontsize=8.8, color=COLORS["early_dark"])

    label_positions = {"1997/98": (1.58, 1.13), "2023/24": (1.58, -1.82)}
    for event, color in [("1997/98", COLORS["y1997"]), ("2023/24", COLORS["y2023"])]:
        row = df[df["event"] == event].iloc[0]
        ax.scatter(row["fep_residual_c"], row["u925_residual_from_nino34"], s=105, color=color, edgecolor="white", linewidth=1.2, zorder=5)
        ax.annotate(
            f"{event}\nFEP={row['fep_residual_c']:.2f}°C\n风残差={row['u925_residual_from_nino34']:+.2f}",
            (row["fep_residual_c"], row["u925_residual_from_nino34"]),
            xytext=label_positions[event],
            textcoords="data",
            ha="left",
            va="center",
            color=color,
            fontsize=9.4,
            fontweight="bold",
            arrowprops={"arrowstyle": "-", "lw": 0.9, "color": color},
        )

    r97 = df[df["event"] == "1997/98"].iloc[0]
    r23 = df[df["event"] == "2023/24"].iloc[0]
    xmid = (r97["fep_residual_c"] + r23["fep_residual_c"]) / 2
    ax.plot(
        [xmid, xmid],
        [r23["u925_residual_from_nino34"], r97["u925_residual_from_nino34"]],
        linestyle="--",
        color="#4A5560",
        linewidth=1.2,
        zorder=2,
    )
    ax.text(
        1.34,
        -0.30,
        "FEP几乎相同\n风响应相差 3.50 m s⁻¹",
        ha="center",
        va="center",
        color=COLORS["ink"],
        fontsize=9.8,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#AAB5BD", "alpha": 0.95},
    )
    ax.axhline(0, color="#596773", linewidth=1.0)
    ax.axhspan(0, 1.8, color="#FBEDE9", alpha=0.65, zorder=0)
    ax.axhspan(-2.5, 0, color="#EAF0F8", alpha=0.75, zorder=0)
    ax.text(0.02, 0.95, "西风强于期望：反馈接上", transform=ax.transAxes, ha="left", va="top", color=COLORS["y1997"], fontsize=9)
    ax.text(0.02, 0.05, "西风弱于期望：脱耦倾向", transform=ax.transAxes, ha="left", va="bottom", color=COLORS["y2023"], fontsize=9)
    ax.set_xlim(0.96, 1.73)
    ax.set_ylim(-2.5, 1.8)
    ax.set_xlabel("残余FEP SST异常（°C）")
    ax.set_ylabel("Niño4 u925风残差（m s⁻¹）")
    ax.grid(color=COLORS["grid"], linewidth=0.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("FEP异常本身不能决定是否脱耦", loc="left", pad=12)
    ax.text(
        0.0,
        -0.25,
        "同样约+1.50°C的残余FEP增暖，可以对应完全相反的中央风响应。\n因此FEP暖异常不是海气反馈接通的充分条件。",
        transform=ax.transAxes,
        color=COLORS["muted"],
        fontsize=9.5,
        va="top",
    )
    panel_label(ax, "c")


def main() -> int:
    apply_style()
    df = pd.read_csv(EVENT_CSV)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(16.2, 6.2), gridspec_kw={"width_ratios": [0.92, 1.28, 1.18]})
    fig.subplots_adjust(left=0.055, right=0.975, top=0.80, bottom=0.28, wspace=0.34)
    plot_ocean_structure(axes[0], df)
    plot_atmospheric_chain(axes[1], df)
    plot_fep_not_sufficient(axes[2], df)

    fig.suptitle("三个发现的证据链：相似海洋结构，不稳定大气响应，FEP不是充分条件", fontsize=18, fontweight="bold", y=0.955, color=COLORS["ink"])
    fig.text(0.5, 0.885, "MJJ去趋势异常；1960–2024逐月气候态；早期事件清单依照Jiang et al. (2026)", ha="center", fontsize=10.5, color=COLORS["muted"])

    ribbon = FancyBboxPatch(
        (0.23, 0.045),
        0.54,
        0.065,
        boxstyle="round,pad=0.012,rounding_size=0.015",
        transform=fig.transFigure,
        facecolor="#EEF3F5",
        edgecolor="#B9C6CC",
        linewidth=0.9,
    )
    fig.add_artist(ribbon)
    fig.text(0.5, 0.078, "可推广的不是单一FEP阈值，而是：海洋结构 × 大气响应的匹配关系", ha="center", va="center", fontsize=12.3, fontweight="bold", color=COLORS["ink"])
    fig.text(0.5, 0.018, "资料：ERSSTv5 SST、ERA5 925-hPa风与降水、ORAS5 D20。负风残差表示中央西风弱于同等Niño3.4条件下的历史期望。", ha="center", fontsize=8.6, color=COLORS["muted"])

    fig.savefig(PNG_OUT, dpi=300, bbox_inches="tight")
    fig.savefig(SVG_OUT, bbox_inches="tight")
    plt.close(fig)
    print(PNG_OUT)
    print(SVG_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
