#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from el_nino_decoupling.zenodo import (  # noqa: E402
    DEFAULT_RAW_DIR,
    classify_files,
    download_file,
    fetch_record_metadata,
    record_files_from_metadata,
    select_files,
    write_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Peng et al. 2025 Zenodo figure data and plotting code.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RAW_DIR, help="Directory for downloaded files.")
    parser.add_argument("--selected", nargs="*", help="Download only these Zenodo filenames.")
    parser.add_argument("--figures-only", action="store_true", help="Download main Figure files plus helper scripts/readme.")
    parser.add_argument("--manifest-only", action="store_true", help="Only write the metadata manifest; do not download files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite files that already exist.")
    args = parser.parse_args()

    metadata = fetch_record_metadata()
    files = record_files_from_metadata(metadata)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(files, args.output_dir / "manifest.csv")

    groups = classify_files(files)
    print(f"Found {len(files)} files in Zenodo record.")
    print(
        "Groups: "
        + ", ".join(f"{name}={len(values)}" for name, values in groups.items())
    )
    print(f"Wrote manifest: {args.output_dir / 'manifest.csv'}")

    if args.manifest_only:
        return 0

    selected = select_files(files, names=args.selected, figures_only=args.figures_only)
    for file in selected:
        target = download_file(file, output_dir=args.output_dir, overwrite=args.overwrite)
        print(f"Downloaded {file.name} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
