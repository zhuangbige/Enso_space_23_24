#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.analysis import average_lon_time  # noqa: E402


REGIONS = {
    "western_central_pacific_140e_180": (140, 180),
    "central_pacific_180_140w": (180, 220),
    "eastern_pacific_140w_100w": (220, 260),
    "full_tropical_pacific_120e_80w": (120, 280),
}

WINDOWS = {
    "feb_may": [1, 2, 3, 4],
    "jun_dec": [5, 6, 7, 8, 9, 10, 11],
    "jan_apr_next": [12, 13, 14, 15],
}

PAIRS = (
    ("taux", "tauxanomEQ2023", "tauxanomEQextreme"),
    ("precip", "precipanomEQ2023", "precipanomEQextreme"),
    ("oisst", "oisstanomeq2023", "oisstanomeqcompextreme"),
    ("sla", "slaanomeq2023", "slaanomeqcompextreme"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Fig. 2 longitude-time summary metrics.")
    parser.add_argument("--mat", type=Path, default=Path("data/raw/peng2025_zenodo/Fig2.mat"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/peng2025_repro/tables/fig2_equatorial_summary.csv"))
    args = parser.parse_args()

    import scipy.io as scio

    data = scio.loadmat(args.mat)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "region", "window", "value_2023", "value_comparable", "difference_2023_minus_comparable"])
        for metric, var_2023, var_comparable in PAIRS:
            lon_name = "loninterp" if metric == "sla" else "lon"
            lon = data[lon_name].squeeze()
            for region_name, (lon_min, lon_max) in REGIONS.items():
                for window_name, month_indices in WINDOWS.items():
                    value_2023 = average_lon_time(
                        data[var_2023],
                        lon=lon,
                        lon_min=lon_min,
                        lon_max=lon_max,
                        month_indices=month_indices,
                    )
                    value_comparable = average_lon_time(
                        data[var_comparable],
                        lon=lon,
                        lon_min=lon_min,
                        lon_max=lon_max,
                        month_indices=month_indices,
                    )
                    writer.writerow(
                        [
                            metric,
                            region_name,
                            window_name,
                            value_2023,
                            value_comparable,
                            value_2023 - value_comparable,
                        ]
                    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
