#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


SERIES = {
    "2023_CTRL": "sstanomnino3CTRL2023mean",
    "2023_InitApr": "sstanominitAprnino32023mean",
    "2023_Wind2023": "sstanomnino3wind2023mean",
    "Other_CTRL": "sstanomnino3CTRLextrememean",
    "Other_InitApr": "sstanominitAprnino3extrememean",
    "Other_WindOther": "sstanomnino3windextrememean",
}

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Fig. 4 wind-stress experiment Nino-3 summaries.")
    parser.add_argument("--mat", type=Path, default=Path("data/raw/peng2025_zenodo/Fig4.mat"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/peng2025_repro/tables/fig4_wind_experiment_summary.csv"))
    args = parser.parse_args()

    import numpy as np
    import scipy.io as scio

    data = scio.loadmat(args.mat)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case", "experiment", "month_index", "month", "nino3"])
        for label, variable in SERIES.items():
            case, experiment = label.split("_", 1)
            values = np.squeeze(data[variable])
            for index, value in enumerate(values, start=1):
                writer.writerow([case, experiment, index, MONTH_LABELS[index - 1], float(value)])
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
