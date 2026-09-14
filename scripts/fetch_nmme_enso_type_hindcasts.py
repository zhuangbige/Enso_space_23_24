#!/usr/bin/env python3
"""Download the NMME seasonal SST hindcasts used for ENSO-type verification.

The NOAA CPC CPT archive stores one global 1-degree SST file for every
model/initialization/target-season combination.  This script downloads:

* the NMME multi-model mean for SON, OND, NDJ, and DJF targets; and
* the individual contributing models for the fixed SON target.

The fixed SON target, initialized from March through July, is the main
diagnostic for the boreal-spring predictability barrier.  The later target
seasons check whether conclusions depend on the verification season.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "raw" / "nmme_cpt" / "seasonal"
BASE_URL = (
    "https://ftp.cpc.ncep.noaa.gov/International/nmme/"
    "seasonal_nmme_hindcast_in_cpt_format"
)

INDIVIDUAL_MODELS = (
    "cfsv2",
    "cmc1",
    "cmc2",
    "nasa",
    "ncar_ccsm4",
    "ncar_cesm1",
)

# All files below have 30 hindcast years.  Seasons crossing New Year use
# 1991-2021 in the NOAA filename even though the initialization years remain
# 1991-2020.
MULTIMODEL_COMBINATIONS = (
    ("Maric", "9-11", "1991-2020"),
    ("Apric", "9-11", "1991-2020"),
    ("Mayic", "9-11", "1991-2020"),
    ("Junic", "9-11", "1991-2020"),
    ("Julic", "9-11", "1991-2020"),
    ("Apric", "10-12", "1991-2020"),
    ("Mayic", "10-12", "1991-2020"),
    ("Junic", "10-12", "1991-2020"),
    ("Julic", "10-12", "1991-2020"),
    ("Mayic", "11-1", "1991-2021"),
    ("Junic", "11-1", "1991-2021"),
    ("Julic", "11-1", "1991-2021"),
    ("Junic", "12-2", "1991-2021"),
    ("Julic", "12-2", "1991-2021"),
)

SON_COMBINATIONS = tuple(
    (initialization, "9-11", "1991-2020")
    for initialization in ("Maric", "Apric", "Mayic", "Junic", "Julic")
)


@dataclass(frozen=True)
class Download:
    model: str
    initialization: str
    target_months: str
    year_span: str

    @property
    def filename(self) -> str:
        return (
            f"{self.model}_sst_hcst_{self.initialization}_"
            f"{self.target_months}_{self.year_span}.txt"
        )

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.filename}"


def build_downloads(include_individual: bool) -> list[Download]:
    downloads = [
        Download("nmme", initialization, target, years)
        for initialization, target, years in MULTIMODEL_COMBINATIONS
    ]
    if include_individual:
        downloads.extend(
            Download(model, initialization, target, years)
            for model in INDIVIDUAL_MODELS
            for initialization, target, years in SON_COMBINATIONS
        )
    return downloads


def download_file(item: Download, output_dir: Path, force: bool) -> str:
    destination = output_dir / item.filename
    if destination.exists() and destination.stat().st_size > 1_000_000 and not force:
        return "existing"
    subprocess.run(
        [
            "curl",
            "-fL",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            item.url,
            "-o",
            str(destination),
        ],
        check=True,
    )
    if destination.stat().st_size < 1_000_000:
        raise RuntimeError(f"Downloaded file is unexpectedly small: {destination}")
    return "downloaded"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--multimodel-only",
        action="store_true",
        help="Skip the individual-model SON files.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str | int]] = []
    for index, item in enumerate(
        build_downloads(include_individual=not args.multimodel_only), start=1
    ):
        print(f"[{index:02d}] {item.filename}", flush=True)
        status = download_file(item, args.output_dir, force=args.force)
        path = args.output_dir / item.filename
        manifest_rows.append(
            {
                "model": item.model,
                "initialization": item.initialization,
                "target_months": item.target_months,
                "year_span": item.year_span,
                "filename": item.filename,
                "url": item.url,
                "bytes": path.stat().st_size,
                "status": status,
            }
        )

    manifest = args.output_dir / "download_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=manifest_rows[0].keys())
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(manifest)


if __name__ == "__main__":
    main()
