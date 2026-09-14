#!/usr/bin/env python3
"""Independently verify the compact P0 archive after cloud download."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath


REQUIRED = {
    "MANIFEST.sha256",
    "results/p0_screening/p0_verification.json",
    "results/p0_screening/p0_monthly_metrics.csv",
    "results/p0_screening/p0_paired_monthly_effects.csv",
    "results/p0_screening/p0_mjj_factorial_summary.csv",
    "results/p0_screening/p0_mjj_factorial_summary_oriented.csv",
    "results/p0_screening/p0_scientific_interpretation.json",
    "results/p0_screening/p0_scientific_interpretation.md",
    "results/p0_screening/pipeline_summary.txt",
    "results/p0_screening/march_aligned_pool_validation.json",
    "results/p0_screening/figures/fig_p0_monthly_paired_response.png",
    "results/p0_screening/figures/fig_p0_monthly_paired_response.pdf",
    "results/p0_screening/figures/fig_p0_mjj_factorial_effects.png",
    "results/p0_screening/figures/fig_p0_mjj_factorial_effects.pdf",
    "scripts/summarize_isca_p0_results.py",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(name: str) -> str:
    parts = [part for part in PurePosixPath(name).parts if part not in (".", "")]
    return "/".join(parts)


def main() -> None:
    args = parse_args()
    archive_bytes = args.archive.read_bytes()
    archive_hash = digest(archive_bytes)
    sha_path = args.sha256 or Path(str(args.archive) + ".sha256")
    if sha_path.is_file():
        expected = sha_path.read_text(encoding="utf-8").split()[0]
        if archive_hash != expected:
            raise SystemExit(
                f"Archive SHA-256 mismatch: expected={expected} found={archive_hash}"
            )

    with tarfile.open(args.archive, "r:gz") as bundle:
        members = {
            normalized(member.name): member
            for member in bundle.getmembers()
            if member.isfile()
        }
        missing = sorted(REQUIRED - set(members))
        if missing:
            raise SystemExit(f"Missing required archive entries: {missing}")

        manifest_bytes = bundle.extractfile(members["MANIFEST.sha256"]).read()
        manifest = {}
        for line in manifest_bytes.decode("utf-8").splitlines():
            expected_hash, name = line.split(maxsplit=1)
            manifest[normalized(name)] = expected_hash
        manifest_missing = sorted((set(members) - {"MANIFEST.sha256"}) - set(manifest))
        if manifest_missing:
            raise SystemExit(f"Files absent from MANIFEST.sha256: {manifest_missing}")

        bad_hashes = []
        for name, expected_hash in manifest.items():
            if name not in members:
                bad_hashes.append({"file": name, "error": "manifest entry missing"})
                continue
            data = bundle.extractfile(members[name]).read()
            found_hash = digest(data)
            if found_hash != expected_hash:
                bad_hashes.append(
                    {"file": name, "expected": expected_hash, "found": found_hash}
                )
        if bad_hashes:
            raise SystemExit(f"Archive payload hash failures: {bad_hashes}")

        verification = json.loads(
            bundle.extractfile(
                members["results/p0_screening/p0_verification.json"]
            ).read()
        )
        if not (
            verification.get("complete") is True
            and verification.get("expected_files") == 240
            and verification.get("valid_files") == 240
            and verification.get("invalid_files") == 0
            and verification.get("errors") == []
        ):
            raise SystemExit("Embedded P0 verification does not prove 240/240 completion")

        march = json.loads(
            bundle.extractfile(
                members["results/p0_screening/march_aligned_pool_validation.json"]
            ).read()
        )
        if not (
            march.get("complete") is True
            and march.get("valid_state_hashes") == 10
            and march.get("unique_state_hashes") == 10
        ):
            raise SystemExit("Embedded March pool verification is incomplete")

        pipeline = bundle.extractfile(
            members["results/p0_screening/pipeline_summary.txt"]
        ).read().decode("utf-8")
        if "P0_PIPELINE_COMPLETE" not in pipeline:
            raise SystemExit("Embedded pipeline summary lacks completion marker")

    report = {
        "complete": True,
        "archive": str(args.archive.resolve()),
        "archive_sha256": archive_hash,
        "payload_files_verified": len(manifest),
        "p0_files": "240/240",
        "march_initial_states": "10/10 unique",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        "P0_ARCHIVE_VALIDATION_COMPLETE "
        f"payload_files={len(manifest)} sha256={archive_hash}"
    )


if __name__ == "__main__":
    main()
