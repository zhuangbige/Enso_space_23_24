"""Plot the seasonal asynchronous-coupling matrix."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data/derived/research/seasonal_asynchrony_matrix.csv"
OUT = ROOT / "data/derived/research/seasonal_asynchrony_figure.png"
SEASONS = ["AMJ", "JJA", "SON", "DJF"]
COUPLING_ORDER = ["nino3_sst", "cwp_u", "soi_like"]
LABELS = {
    "nino3_sst": "Nino-3 SST",
    "cwp_u": "CWP low-level u",
    "soi_like": "SOI-like SLP",
    "sst_maritime_continent": "Maritime Continent SST",
    "sst_tropical_indian_ocean": "Tropical Indian Ocean SST",
    "sst_tropical_north_atlantic": "Tropical North Atlantic SST",
    "sst_western_pacific_warm_pool": "W. Pacific warm pool SST",
}


def _annotate(ax: plt.Axes, data: np.ndarray) -> None:
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7)


def main() -> None:
    df = pd.read_csv(MATRIX)
    coupling = (
        df[df["metric"].isin(COUPLING_ORDER)]
        .pivot_table(index="metric", columns="season", values="ratio_to_comparable", aggfunc="mean")
        .reindex(index=COUPLING_ORDER, columns=SEASONS)
    )
    external = (
        df[df["metric"].str.startswith("sst_") & (df["metric"] != "nino3_sst")]
        .pivot_table(
            index="metric",
            columns="season",
            values="difference_2023_minus_comparable",
            aggfunc="mean",
        )
        .reindex(columns=SEASONS)
    )

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12, max(4.5, 0.42 * len(external.index))),
        constrained_layout=True,
        gridspec_kw={"width_ratios": [1.0, 1.45]},
    )

    coupling_data = coupling.to_numpy(dtype=float)
    im0 = axes[0].imshow(coupling_data, cmap="RdBu_r", vmin=-1.5, vmax=1.5, aspect="auto")
    axes[0].set_title("Pacific coupling ratios\n2023/comparable")
    axes[0].set_xticks(np.arange(len(SEASONS)), SEASONS)
    axes[0].set_yticks(
        np.arange(len(coupling.index)), [LABELS.get(item, item) for item in coupling.index]
    )
    _annotate(axes[0], coupling_data)
    fig.colorbar(im0, ax=axes[0], label="ratio")

    external_data = external.to_numpy(dtype=float)
    im1 = axes[1].imshow(external_data, cmap="RdBu_r", vmin=-1.5, vmax=1.5, aspect="auto")
    axes[1].set_title("External-basin SST contrast\n2023 minus comparable (deg C)")
    axes[1].set_xticks(np.arange(len(SEASONS)), SEASONS)
    axes[1].set_yticks(
        np.arange(len(external.index)), [LABELS.get(item, item) for item in external.index]
    )
    _annotate(axes[1], external_data)
    fig.colorbar(im1, ax=axes[1], label="deg C")

    fig.suptitle("Seasonal asynchronous coupling during the 2023/24 strong El Nino")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=220)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
