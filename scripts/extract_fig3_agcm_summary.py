#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.analysis import average_lon_level, average_lon_time  # noqa: E402


REGIONS = {
    "indian_ocean_40e_100e": (40, 100),
    "maritime_continent_100e_150e": (100, 150),
    "western_central_pacific_140e_180": (140, 180),
    "central_pacific_180_140w": (180, 220),
    "eastern_pacific_140w_100w": (220, 260),
}

WINDOWS = {
    "feb_may": [1, 2, 3, 4],
    "jun_dec": [5, 6, 7, 8, 9, 10, 11],
}

TAUX_EXPERIMENTS = {
    "aCTRL": "TAUXen2023anomEQ",
    "aPac": "TAUXenPACanomEQ",
    "aIndAtl": "TAUXenINDATLanomEQ",
    "aTrend": "TAUXentrendanomEQ",
}

OMEGA_EXPERIMENTS = {
    "aCTRL": "omegaen2023anomEQ",
    "aPac": "omegaenPACdetrend2023anomEQ",
    "aIndAtl": "omegaenINDATLdetrend2023anomEQ",
    "aTrend": "omegaentrend2023anomEQ",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Fig. 3 AGCM attribution summary metrics.")
    parser.add_argument("--mat", type=Path, default=Path("data/raw/peng2025_zenodo/Fig3.mat"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/peng2025_repro/tables/fig3_agcm_summary.csv"))
    args = parser.parse_args()

    import numpy as np
    import scipy.io as scio

    data = scio.loadmat(args.mat)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "experiment", "region", "window_or_layer", "value"])
        for experiment, variable in TAUX_EXPERIMENTS.items():
            for region_name, (lon_min, lon_max) in REGIONS.items():
                for window_name, month_indices in WINDOWS.items():
                    writer.writerow(
                        [
                            "taux",
                            experiment,
                            region_name,
                            window_name,
                            average_lon_time(
                                data[variable],
                                lon=data["loninterp"].squeeze(),
                                lon_min=lon_min,
                                lon_max=lon_max,
                                month_indices=month_indices,
                            ),
                        ]
                    )

        for experiment, variable in OMEGA_EXPERIMENTS.items():
            june_dec_mean = np.nanmean(data[variable][:, :, 5:12], axis=2)
            for region_name, (lon_min, lon_max) in REGIONS.items():
                writer.writerow(
                    [
                        "minus_omega_jun_dec_200_850hpa",
                        experiment,
                        region_name,
                        "jun_dec_200_850hpa",
                        -average_lon_level(
                            june_dec_mean,
                            lon=data["lon"].squeeze(),
                            levels=data["lev"].squeeze(),
                            lon_min=lon_min,
                            lon_max=lon_max,
                            level_min=200,
                            level_max=850,
                        ),
                    ]
                )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
