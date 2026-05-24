#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.analysis import compute_fig1_event_records, write_event_records  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Fig. 1 event/coupling table from Peng 2025 figure data.")
    parser.add_argument("--mat", type=Path, default=Path("data/raw/peng2025_zenodo/Fig1.mat"))
    parser.add_argument("--output", type=Path, default=Path("data/derived/peng2025_repro/tables/fig1_event_coupling.csv"))
    parser.add_argument("--python-note", action="store_true", help="Only print dependency note.")
    args = parser.parse_args()

    if args.python_note:
        print("Requires scipy in the active Python environment.")
        return 0

    import scipy.io as scio

    data = scio.loadmat(args.mat)
    records = compute_fig1_event_records(
        nino3=data["sstanomnino3JuntoJan"].squeeze(),
        uwind=data["uwindCWPJuntoJan"].squeeze(),
        soi=data["SOIJuntoJan"].squeeze(),
    )
    write_event_records(records, args.output)
    print(args.output)
    for record in records:
        if record.highlight:
            print(
                f"{record.year}: Nino3={record.nino3:.3f}, "
                f"u10={record.uwind:.3f}, SOI={record.soi:.3f}, "
                f"u10_ratio={record.uwind_coupling_ratio:.3f}, "
                f"SOI_ratio={record.soi_coupling_ratio:.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
