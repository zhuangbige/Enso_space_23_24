#!/usr/bin/env python3
"""Create the Chinese two-gate ENSO type-formation framework figure."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/research_2026/paper_cn"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": ["Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)

INK = "#17324D"
BLUE = "#2C7FB8"
TEAL = "#239A8B"
ORANGE = "#D9782D"
RED = "#B83A3A"
PALE_BLUE = "#EAF3F8"
PALE_TEAL = "#E9F5F2"
PALE_ORANGE = "#FCF0E5"
GRAY = "#66737F"


def rounded_box(ax, x, y, w, h, face, title, body):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.016,rounding_size=0.025",
        linewidth=1.2,
        edgecolor="#B7C4CF",
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(x + 0.04 * w, y + 0.70 * h, title, fontsize=15, weight="bold", color=INK)
    ax.text(x + 0.04 * w, y + 0.38 * h, body, fontsize=10.3, color=GRAY,
            linespacing=1.45, va="center")


def arrow(ax, start, end, color=INK, lw=2.0, style="-"):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=lw,
            linestyle=style,
            color=color,
            shrinkA=2,
            shrinkB=2,
        )
    )


def main():
    fig, ax = plt.subplots(figsize=(13.2, 7.1), constrained_layout=True)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.95,
        "ENSO类型形成的三阶段与两个动力关口",
        ha="center",
        va="center",
        fontsize=22,
        weight="bold",
        color=INK,
    )
    ax.text(
        0.5,
        0.905,
        "总暖量决定事件潜力；暖量位置与大气反馈决定成熟暖中心",
        ha="center",
        va="center",
        fontsize=11.5,
        color=GRAY,
    )

    rounded_box(
        ax, 0.035, 0.56, 0.25, 0.25, PALE_BLUE,
        "阶段Ⅰ  蓄能（1—3月）",
        "总暖水体积、OHC、暖池D20\n回答“有没有足够的能量”\n不能单独决定EP或CP",
    )
    rounded_box(
        ax, 0.375, 0.56, 0.25, 0.25, PALE_TEAL,
        "阶段Ⅱ  东传—储存（3—5月）",
        "暖量重心、140°W Q20/D20、SSH\n回答“暖量是否真正向东到位”\n四月是候选检查点",
    )
    rounded_box(
        ax, 0.715, 0.56, 0.25, 0.25, PALE_ORANGE,
        "阶段Ⅲ  大气兑现（5—6月后）",
        "SST → 降水/OLR → SLP → 纬向风应力\n回答“Bjerknes反馈是否接上”\n须分开对流与西风两条支路",
    )

    arrow(ax, (0.29, 0.685), (0.365, 0.685), color=TEAL, lw=2.6)
    arrow(ax, (0.63, 0.685), (0.705, 0.685), color=ORANGE, lw=2.6)

    ax.text(0.327, 0.755, "关口1", ha="center", fontsize=12, weight="bold", color=TEAL)
    ax.text(0.327, 0.505, "暖量跨越日界线并在140°W附近储存",
            ha="center", fontsize=9.8, color=TEAL)
    ax.plot([0.327, 0.327], [0.55, 0.65], color=TEAL, lw=1.2, ls="--")

    ax.text(0.667, 0.755, "关口2", ha="center", fontsize=12, weight="bold", color=ORANGE)
    ax.text(0.667, 0.505, "对流—气压响应转化为持续赤道西风应力",
            ha="center", fontsize=9.8, color=ORANGE)
    ax.plot([0.667, 0.667], [0.55, 0.65], color=ORANGE, lw=1.2, ls="--")

    # Event pathways
    ax.text(0.05, 0.39, "事件路径对照", fontsize=12.5, weight="bold", color=INK)
    y97, y23 = 0.305, 0.205
    ax.text(0.05, y97, "1997", fontsize=12, weight="bold", color=RED, va="center")
    arrow(ax, (0.12, y97), (0.94, y97), color=RED, lw=3.2)
    for x in (0.23, 0.50, 0.81):
        ax.scatter(x, y97, s=55, color=RED, zorder=5, edgecolor="white", linewidth=0.8)
    ax.text(0.70, y97 + 0.045, "两道关口均通过：强EP分支", fontsize=10.5,
            color=RED, va="bottom", ha="center")

    ax.text(0.05, y23, "2023", fontsize=12, weight="bold", color=BLUE, va="center")
    arrow(ax, (0.12, y23), (0.61, y23), color=BLUE, lw=3.0)
    arrow(ax, (0.61, y23), (0.91, y23), color=BLUE, lw=2.3, style="--")
    for x in (0.23, 0.50):
        ax.scatter(x, y23, s=55, color=BLUE, zorder=5, edgecolor="white", linewidth=0.8)
    ax.scatter(0.81, y23, s=70, facecolor="white", edgecolor=BLUE, linewidth=2.0, zorder=5)
    ax.text(0.74, y23 - 0.045, "表层FEP强，但西风兑现不足：混合路径", fontsize=10.5,
            color=BLUE, va="top", ha="center")

    ax.text(
        0.5,
        0.075,
        "可证伪预期：只有固定海洋初态并逐一改变外海盆、FEP、NPMM或WWB，\n"
        "再检验E/C与Niño3−Niño4是否同时过零，才能判定类型发生因果转换。",
        ha="center",
        va="center",
        fontsize=10.2,
        color=INK,
        linespacing=1.45,
    )

    png = OUT / "fig01_enso_two_gate_framework_cn.png"
    pdf = OUT / "fig01_enso_two_gate_framework_cn.pdf"
    fig.savefig(png, dpi=320, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
