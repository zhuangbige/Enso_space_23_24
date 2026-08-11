#!/usr/bin/env python3
"""Build the five standalone ENSO geographic figures and their audit files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.enso_geographic_figures.config import OUTPUT_DIR
from scripts.enso_geographic_figures.data import open_geographic_fields
from scripts.enso_geographic_figures.figures import (
    build_arrival_box_map,
    build_fate_budget_map,
    build_propagation_atlas,
    build_q3_state_map,
    build_trajectory_connectivity,
)

DEFAULT_FIELDS = (
    ROOT
    / "data/derived/research_2026/"
    "soda3_geographic_figure_fields_1997_2015_2023.nc"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--fields", type=Path, default=DEFAULT_FIELDS)
    parser.add_argument("--skip-grid-fields", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def create_montage(png_paths: list[Path], output: Path) -> None:
    if not png_paths:
        raise ValueError("Montage requires at least one PNG")
    tiles = []
    target_width = 1100
    for path in png_paths:
        with Image.open(path) as source:
            image = source.convert("RGB")
        if image.width > target_width:
            height = round(image.height * target_width / image.width)
            image = image.resize((target_width, height), Image.Resampling.LANCZOS)
        tiles.append((path.stem, image))

    padding = 32
    label_height = 54
    columns = 2
    rows = (len(tiles) + columns - 1) // columns
    column_width = max(image.width for _, image in tiles)
    row_heights = []
    for row in range(rows):
        items = tiles[row * columns : (row + 1) * columns]
        row_heights.append(max(image.height for _, image in items) + label_height)
    canvas = Image.new(
        "RGB",
        (
            columns * column_width + (columns + 1) * padding,
            sum(row_heights) + (rows + 1) * padding,
        ),
        "white",
    )
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=28)
    y = padding
    for row in range(rows):
        items = tiles[row * columns : (row + 1) * columns]
        for column, (label, image) in enumerate(items):
            x = padding + column * (column_width + padding)
            canvas.paste(image, (x, y + label_height))
            draw.text((x, y + 6), label, fill="#132530", font=font)
        y += row_heights[row] + padding
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def build_atlas(output_dir: Path, fields_path: Path, *, skip_grid_fields: bool) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures: dict[str, dict] = {}
    fields = None
    if not skip_grid_fields:
        fields = open_geographic_fields(fields_path)
        figures["fig01_propagation_atlas"] = build_propagation_atlas(output_dir, fields)
    figures["fig02_trajectory_connectivity"] = build_trajectory_connectivity(output_dir)
    figures["fig03_arrival_box_map"] = build_arrival_box_map(output_dir, fields)
    figures["fig04_fate_budget_map"] = build_fate_budget_map(output_dir, fields)
    figures["fig05_q3_state_map"] = build_q3_state_map(output_dir)
    if fields is not None:
        field_attributes = dict(fields.attrs)
        fields.close()
    else:
        field_attributes = None

    audit = {
        "figures": figures,
        "grid_fields": {
            "path": str(fields_path),
            "attributes": field_attributes,
        }
        if not skip_grid_fields
        else None,
        "constraints": {
            "events": [1997, 2015, 2023],
            "depth": "0-300 m",
            "arrival_window": "event-year Jan-Jun",
            "fate_window": "following Jan-May",
            "warm_threshold_metric_used": False,
        },
    }
    audit_path = output_dir / "figure-audit.json"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
        + "\n",
        encoding="utf-8",
    )
    png_paths = [Path(metadata["artifacts"]["png"]) for metadata in figures.values()]
    montage_path = output_dir / "atlas-montage.png"
    create_montage(png_paths, montage_path)
    return {
        "figures": figures,
        "audit": str(audit_path),
        "montage": str(montage_path),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_atlas(
        args.output_dir,
        args.fields,
        skip_grid_fields=args.skip_grid_fields,
    )
    print(json.dumps(result, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
