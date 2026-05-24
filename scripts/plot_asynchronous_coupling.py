#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SEASONS = ["AMJ", "JJA", "SON", "DJF"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def seasonal_values(rows: list[dict[str, str]], metric: str, key: str) -> list[float]:
    values = []
    for season in SEASONS:
        row = next(row for row in rows if row["metric"] == metric and row["season"] == season)
        values.append(float(row[key]))
    return values


def main() -> int:
    seasonal = read_rows(ROOT / "data/derived/research/seasonal_decoupling_first_pass.csv")
    efficiency = read_rows(ROOT / "data/derived/research/asynchronous_coupling_efficiency.csv")

    nino_ratio = [
        float(next(row for row in seasonal if row["metric"] == "nino3_sst_oisst" and row["season"] == season)["value_2023"])
        / float(next(row for row in seasonal if row["metric"] == "nino3_sst_oisst" and row["season"] == season)["value_comparable"])
        for season in SEASONS
    ]
    u_ratio = seasonal_values(efficiency, "cwp_u_ncep_sig995", "atmospheric_response_ratio")
    soi_eff = seasonal_values(efficiency, "soi_like_ncep", "atmosphere_to_sst_efficiency")
    u_eff = seasonal_values(efficiency, "cwp_u_ncep_sig995", "atmosphere_to_sst_efficiency")

    output = ROOT / "data/derived/research/asynchronous_coupling_by_season.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.2), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.patch.set_facecolor("#f7f3ea")
    for ax in axes:
        ax.set_facecolor("#f7f3ea")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", color="#d8d1c4", linewidth=0.8, alpha=0.8)

    axes[0].plot(SEASONS, nino_ratio, marker="o", linewidth=2.6, label="Niño-3 SST strength ratio", color="#cc5a43")
    axes[0].plot(SEASONS, u_ratio, marker="o", linewidth=2.6, label="CWP u response ratio", color="#2f6f73")
    axes[0].axhline(1, color="#1d1b18", linewidth=1)
    axes[0].axhline(0, color="#1d1b18", linewidth=0.8, alpha=0.6)
    axes[0].set_title("Same-season response", loc="left", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("2023 / 1982-1997-2015 composite")
    axes[0].legend(frameon=False, fontsize=9, loc="lower right")

    axes[1].bar([x - 0.18 for x in range(len(SEASONS))], u_eff, width=0.35, label="CWP u efficiency", color="#2f6f73")
    axes[1].bar([x + 0.18 for x in range(len(SEASONS))], soi_eff, width=0.35, label="SOI-like efficiency", color="#4a5f99")
    axes[1].axhline(1, color="#1d1b18", linewidth=1)
    axes[1].axhline(0, color="#1d1b18", linewidth=0.8, alpha=0.6)
    axes[1].set_xticks(range(len(SEASONS)), SEASONS)
    axes[1].set_title("Atmospheric efficiency relative to SST forcing", loc="left", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("Atmospheric ratio / SST ratio")
    axes[1].legend(frameon=False, fontsize=9, loc="upper right")

    fig.suptitle("2023/24 El Niño asynchronous coupling diagnostics", x=0.02, y=0.98, ha="left", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.9), w_pad=3)
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
