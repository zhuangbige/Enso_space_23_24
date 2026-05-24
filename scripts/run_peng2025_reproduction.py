#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from el_nino_decoupling.reproduction import prepare_reproduction_tree  # noqa: E402
from el_nino_decoupling.zenodo import DEFAULT_RAW_DIR  # noqa: E402


MAIN_FIGURE_SCRIPTS = ["Fig1.py", "Fig2.py", "Fig3.py", "Fig4.py"]
HELPER_SCRIPTS = ["creat_map.py", "creat_mapnoproj.py"]


def selected_scripts(group: str, explicit: list[str] | None = None) -> list[str]:
    if group == "main":
        return MAIN_FIGURE_SCRIPTS
    if group == "selected":
        if not explicit:
            raise ValueError("--selected is required when --group selected is used.")
        return explicit
    raise ValueError(f"Unknown group: {group}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch and run Peng et al. 2025 reproduction scripts.")
    parser.add_argument("--group", choices=("main", "selected"), default="main")
    parser.add_argument("--selected", nargs="*", help="Scripts to run when --group selected is used.")
    parser.add_argument("--source-dir", type=Path, default=ROOT / DEFAULT_RAW_DIR)
    parser.add_argument("--script-dir", type=Path, default=ROOT / "data/interim/peng2025_repro/scripts")
    parser.add_argument("--figure-dir", type=Path, default=ROOT / "data/derived/peng2025_repro/figures")
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/bin/python")
    args = parser.parse_args()

    scripts = selected_scripts(args.group, args.selected)
    prepare_reproduction_tree(
        source_dir=args.source_dir,
        target_dir=args.script_dir,
        figure_dir=args.figure_dir,
        filenames=scripts + HELPER_SCRIPTS,
    )

    env = os.environ.copy()
    env.setdefault("MPLBACKEND", "Agg")
    env.setdefault("MPLCONFIGDIR", "/private/tmp/mplconfig")
    for script in scripts:
        print(f"Running {script}")
        subprocess.run([str(args.python), script], cwd=args.script_dir, env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
