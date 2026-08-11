"""Shared scientific and visual configuration for the geographic atlas."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/derived/research_2026"
OUTPUT_DIR = ROOT / "outputs/research_2026/enso_geographic_figure_atlas_20260812"

EVENTS = (1997, 2015, 2023)
BOXES = {
    "west": (160.0, 180.0, -10.0, 5.0),
    "central": (180.0, 220.0, -10.0, 5.0),
    "east": (220.0, 280.0, -10.0, 5.0),
}
PHASES = {
    "arrival": "arrival_Jan_Jun",
    "fate": "decay_Jan_May_next",
}

EVENT_COLORS = {
    1997: "#E97800",
    2015: "#2F86C1",
    2023: "#148F88",
}
OTHER_EVENT_COLOR = "#96A6B2"
LAND_COLOR = "#E8E5DE"
COAST_COLOR = "#49545C"
GRID_COLOR = "#C9D2D8"

TRAJECTORY_PATH = DATA_DIR / "soda3_temp_anomaly_lagrangian_pilot_trajectories.csv"
ENDPOINT_PATH = DATA_DIR / "soda3_temp_anomaly_lagrangian_pilot_endpoints.csv"
BUDGET_EVENT_PATH = DATA_DIR / "soda3_three_box_ohc_anomaly_budget_events.csv"
HOVMOLLER_PATH = DATA_DIR / "soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv"
EARLY_Q3_EVENT_PATH = DATA_DIR / "nonh20_early_north_to_jiang_event_table.csv"
EARLY_Q3_RELATION_PATH = DATA_DIR / "nonh20_early_north_to_jiang_relationships.csv"
Q3_EVENT_PATH = DATA_DIR / "nonh20_third_question_event_table.csv"
Q3_RELATION_PATH = DATA_DIR / "nonh20_third_question_relationships.csv"
