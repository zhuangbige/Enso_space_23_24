#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.report import write_first_pass_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a first-pass report from reproduced Peng 2025 tables.")
    parser.add_argument("--fig1", type=Path, default=Path("data/derived/peng2025_repro/tables/fig1_event_coupling.csv"))
    parser.add_argument("--fig3", type=Path, default=Path("data/derived/peng2025_repro/tables/fig3_agcm_summary.csv"))
    parser.add_argument("--fig4", type=Path, default=Path("data/derived/peng2025_repro/tables/fig4_wind_experiment_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports/first_pass_reproduction_report.md"))
    args = parser.parse_args()

    write_first_pass_report(args.fig1, args.fig3, args.fig4, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
