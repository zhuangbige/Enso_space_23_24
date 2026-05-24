from __future__ import annotations

import csv
import json
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


DEFAULT_RECORD_ID = "15074285"
DEFAULT_RAW_DIR = Path("data/raw/peng2025_zenodo")


@dataclass(frozen=True)
class ZenodoFile:
    name: str
    size: int
    checksum: str
    download_url: str


def build_download_url(filename: str, record_id: str = DEFAULT_RECORD_ID) -> str:
    return f"https://zenodo.org/records/{record_id}/files/{quote(filename)}?download=1"


def fetch_record_metadata(record_id: str = DEFAULT_RECORD_ID) -> dict:
    url = f"https://zenodo.org/api/records/{record_id}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def record_files_from_metadata(metadata: dict) -> list[ZenodoFile]:
    files = []
    for entry in metadata.get("files", []):
        name = entry.get("key") or entry.get("filename")
        if not name:
            continue
        links = entry.get("links", {})
        download_url = links.get("self") or links.get("download") or build_download_url(name)
        files.append(
            ZenodoFile(
                name=name,
                size=int(entry.get("size") or entry.get("filesize") or 0),
                checksum=str(entry.get("checksum") or ""),
                download_url=download_url,
            )
        )
    return files


def classify_files(files: list[ZenodoFile]) -> dict[str, list[str]]:
    groups = {"main": [], "extended": [], "supplementary": [], "helpers": []}
    for file in files:
        if file.name.startswith("Fig"):
            groups["main"].append(file.name)
        elif file.name.startswith("Extended_Data_Fig"):
            groups["extended"].append(file.name)
        elif file.name.startswith("Supplementary_Fig"):
            groups["supplementary"].append(file.name)
        else:
            groups["helpers"].append(file.name)
    return groups


def write_manifest(files: list[ZenodoFile], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "size", "checksum", "download_url"])
        for file in files:
            writer.writerow([file.name, file.size, file.checksum, file.download_url])


def download_file(file: ZenodoFile, output_dir: Path = DEFAULT_RAW_DIR, overwrite: bool = False) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / file.name
    if target.exists() and not overwrite:
        return target

    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(file.download_url, timeout=120) as response:
        with partial.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    partial.replace(target)
    return target


def select_files(files: list[ZenodoFile], names: list[str] | None = None, figures_only: bool = False) -> list[ZenodoFile]:
    if names:
        wanted = set(names)
        selected = [file for file in files if file.name in wanted]
        missing = sorted(wanted - {file.name for file in selected})
        if missing:
            raise ValueError(f"Files not found in Zenodo metadata: {', '.join(missing)}")
        return selected
    if figures_only:
        return [file for file in files if file.name.startswith(("Fig", "readme", "creat_map"))]
    return files
