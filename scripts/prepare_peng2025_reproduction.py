#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.reproduction import prepare_reproduction_tree  # noqa: E402
from el_nino_decoupling.zenodo import DEFAULT_RAW_DIR  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare patched local copies of Peng 2025 reproduction scripts.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--target-dir", type=Path, default=Path("data/interim/peng2025_repro/scripts"))
    parser.add_argument("--figure-dir", type=Path, default=Path("data/derived/peng2025_repro/figures"))
    parser.add_argument("--selected", nargs="*", help="Specific Python scripts to patch, such as Fig1.py.")
    args = parser.parse_args()

    prepared = prepare_reproduction_tree(
        source_dir=args.source_dir,
        target_dir=args.target_dir,
        figure_dir=args.figure_dir,
        filenames=args.selected,
    )
    for path in prepared:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
