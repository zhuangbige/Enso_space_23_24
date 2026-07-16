#!/usr/bin/env python3
"""Plot seasonal regression-expected coupling ratios in the matrix style."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "data/derived/research/seasonal_regression_expected_response.csv"
EXTERNAL = ROOT / "data/derived/research/external_basin_seasonal_summary.csv"
OUT = ROOT / "data/derived/research/seasonal_regression_asynchrony_matrix.png"
OUT_PDF = ROOT / "data/derived/research/seasonal_regression_asynchrony_matrix.pdf"

SEASONS = ["AMJ", "JJA", "SON", "DJF"]
COUPLING_ORDER = [
    "era5_u10_cwp_160e_140w",
    "era5_soi_like_tahiti_minus_darwin",
    "gpcp_precip_central_pacific_180_140w",
    "olr_central_pacific_180_140w",
]
EXTERNAL_ORDER = [
    "maritime_continent",
    "tropical_indian_ocean",
    "tropical_north_atlantic",
    "western_pacific_warm_pool",
]
LABELS = {
    "era5_u10_cwp_160e_140w": "ERA5 CWP u10",
    "era5_soi_like_tahiti_minus_darwin": "ERA5 SOI-like SLP",
    "gpcp_precip_central_pacific_180_140w": "GPCP CP rainfall",
    "olr_central_pacific_180_140w": "CPC OLR CP",
    "maritime_continent": "Maritime Continent SST",
    "tropical_indian_ocean": "Tropical Indian Ocean SST",
    "tropical_north_atlantic": "Tropical North Atlantic SST",
    "western_pacific_warm_pool": "W. Pacific warm pool SST",
}


def _annotate(ax: plt.Axes, data: np.ndarray) -> None:
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7)


def _style_matrix_axis(ax: plt.Axes) -> None:
    ax.tick_params(length=0, labelsize=9)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.8)
        spine.set_color("#2b2b2b")


def main() -> int:
    regression = pd.read_csv(REGRESSION)
    external = pd.read_csv(EXTERNAL)

    coupling = (
        regression[regression["metric"].isin(COUPLING_ORDER)]
        .pivot_table(
            index="metric",
            columns="season",
            values="coupling_ratio_observed_over_expected",
            aggfunc="mean",
        )
        .reindex(index=COUPLING_ORDER, columns=SEASONS)
    )
    external_matrix = (
        external[external["region"].isin(EXTERNAL_ORDER)]
        .pivot_table(
            index="region",
            columns="season",
            values="difference_2023_minus_comparable",
            aggfunc="mean",
        )
        .reindex(index=EXTERNAL_ORDER, columns=SEASONS)
    )

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12.4, 4.7),
        constrained_layout=True,
        gridspec_kw={"width_ratios": [1.18, 1.35]},
    )

    coupling_data = coupling.to_numpy(dtype=float)
    im0 = axes[0].imshow(
        coupling_data,
        cmap="RdBu_r",
        vmin=-1.5,
        vmax=1.5,
        aspect="auto",
    )
    axes[0].set_title(
        "Seasonal atmospheric coupling ratios\nobserved / regression-expected",
        fontsize=10,
    )
    axes[0].set_xticks(np.arange(len(SEASONS)), SEASONS)
    axes[0].set_yticks(
        np.arange(len(coupling.index)),
        [LABELS.get(item, item) for item in coupling.index],
    )
    _annotate(axes[0], coupling_data)
    _style_matrix_axis(axes[0])
    fig.colorbar(im0, ax=axes[0], label="ratio", fraction=0.046, pad=0.04)

    external_data = external_matrix.to_numpy(dtype=float)
    im1 = axes[1].imshow(
        external_data,
        cmap="RdBu_r",
        vmin=-1.5,
        vmax=1.5,
        aspect="auto",
    )
    axes[1].set_title(
        "External-basin SST contrast\n2023 minus comparable (deg C)",
        fontsize=10,
    )
    axes[1].set_xticks(np.arange(len(SEASONS)), SEASONS)
    axes[1].set_yticks(
        np.arange(len(external_matrix.index)),
        [LABELS.get(item, item) for item in external_matrix.index],
    )
    _annotate(axes[1], external_data)
    _style_matrix_axis(axes[1])
    fig.colorbar(im1, ax=axes[1], label="deg C", fraction=0.046, pad=0.04)

    fig.suptitle(
        "Seasonal asynchronous coupling during the 2023/24 strong El Nino",
        fontsize=12,
        y=1.02,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight")
    fig.savefig(OUT_PDF, bbox_inches="tight")
    print(OUT)
    print(OUT_PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
