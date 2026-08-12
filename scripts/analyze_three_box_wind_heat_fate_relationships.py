#!/usr/bin/env python3
"""Relate three-box Pacific heat-loss pathways to wind anomalies.

All public heat-fate terms use a positive-outward convention.  The script
reads the audited, fixed-depth SODA3 OHC-anomaly budget and treats its
residual as an audit term rather than a physical heat-loss mechanism.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVENTS = (
    1982,
    1986,
    1991,
    1994,
    1997,
    2002,
    2004,
    2006,
    2009,
    2015,
    2018,
    2019,
    2023,
)
BOXES = {
    "west": (160.0, 180.0),
    "central": (180.0, 220.0),
    "east": (220.0, 280.0),
}
PHASE_MONTHS = {
    "arrival_Jan_Jun": (0, 1, 6),
    "redistribution_Jul_Dec": (0, 7, 12),
    "decay_Jan_May_next": (1, 1, 5),
}

DERIVED = Path("data/derived/research_2026")
BUDGET_EVENTS = DERIVED / "soda3_three_box_ohc_anomaly_budget_events.csv"

HEAT_FATE_COLUMNS = (
    "west_face_loss_zj",
    "east_face_loss_zj",
    "southward_loss_zj",
    "northward_loss_zj",
    "surface_loss_zj",
    "storage_loss_zj",
)


def discover_input_root() -> Path:
    """Locate the data-bearing main project from a linked worktree."""

    candidates: list[Path] = []
    configured = os.environ.get("MARYLAND_INPUT_ROOT")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(ROOT)
    if ROOT.parent.name == ".worktrees":
        candidates.append(ROOT.parents[1])
    for candidate in candidates:
        if (candidate / BUDGET_EVENTS).exists():
            return candidate.resolve()
    rendered = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Could not locate {BUDGET_EVENTS} under {rendered}")


def positive_outward_heat_fate(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert face, surface, and storage terms to positive loss from a box."""

    required = {
        "west_theta_heat_in_zj",
        "east_theta_heat_in_zj",
        "south_theta_heat_in_zj",
        "north_theta_heat_in_zj",
        "surface_zj",
        "storage_change_zj",
        "residual_zj",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing heat-fate inputs: {sorted(missing)}")
    output = frame.copy()
    output["west_face_loss_zj"] = -output["west_theta_heat_in_zj"]
    output["east_face_loss_zj"] = -output["east_theta_heat_in_zj"]
    output["southward_loss_zj"] = -output["south_theta_heat_in_zj"]
    output["northward_loss_zj"] = -output["north_theta_heat_in_zj"]
    output["surface_loss_zj"] = -output["surface_zj"]
    output["storage_loss_zj"] = -output["storage_change_zj"]
    output["residual_audit_zj"] = output["residual_zj"]
    return output


def validate_heat_fate(frame: pd.DataFrame) -> dict[str, object]:
    """Enforce exact event/phase/box coverage and finite physical terms."""

    key = ["event_year", "phase", "box"]
    if frame.duplicated(key).any():
        duplicates = frame.loc[frame.duplicated(key, keep=False), key]
        raise ValueError(f"Duplicate heat-fate rows:\n{duplicates}")
    expected_rows = len(EVENTS) * len(PHASE_MONTHS) * len(BOXES)
    if len(frame) != expected_rows:
        raise ValueError(f"Expected {expected_rows} heat-fate rows, found {len(frame)}")
    if set(frame.event_year) != set(EVENTS):
        raise ValueError("Heat-fate table does not contain the exact event sample")
    if set(frame.phase) != set(PHASE_MONTHS):
        raise ValueError("Heat-fate table does not contain the exact phases")
    if set(frame.box) != set(BOXES):
        raise ValueError("Heat-fate table does not contain the exact boxes")
    missing = int(frame[list(HEAT_FATE_COLUMNS)].isna().sum().sum())
    if missing:
        raise ValueError(f"Heat-fate table contains {missing} missing physical values")
    return {
        "rows": int(len(frame)),
        "events": sorted(int(value) for value in frame.event_year.unique()),
        "phases": list(PHASE_MONTHS),
        "boxes": list(BOXES),
        "missing_physical_values": missing,
    }


def load_heat_fate_events(input_root: Path | None = None) -> pd.DataFrame:
    """Load audited event budgets and expose positive-outward heat fates."""

    root = discover_input_root() if input_root is None else Path(input_root)
    source = pd.read_csv(root / BUDGET_EVENTS)
    source["phase"] = source["phase"].replace(
        {"post_Jul_Dec": "redistribution_Jul_Dec"}
    )
    selected = source.loc[
        source.event_year.isin(EVENTS)
        & source.box.isin(BOXES)
        & source.phase.isin(PHASE_MONTHS)
    ].copy()
    output = positive_outward_heat_fate(selected)
    output = output.sort_values(["event_year", "phase", "box"]).reset_index(drop=True)
    validate_heat_fate(output)
    return output

