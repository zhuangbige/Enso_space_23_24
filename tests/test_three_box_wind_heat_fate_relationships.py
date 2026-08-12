from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from scripts import analyze_three_box_wind_heat_fate_relationships as analysis


def test_positive_outward_conversion() -> None:
    source = pd.DataFrame(
        {
            "west_theta_heat_in_zj": [2.0],
            "east_theta_heat_in_zj": [-3.0],
            "south_theta_heat_in_zj": [-4.0],
            "north_theta_heat_in_zj": [5.0],
            "surface_zj": [-6.0],
            "storage_change_zj": [-7.0],
            "residual_zj": [0.5],
        }
    )
    result = analysis.positive_outward_heat_fate(source)
    assert result.loc[0, "west_face_loss_zj"] == -2.0
    assert result.loc[0, "east_face_loss_zj"] == 3.0
    assert result.loc[0, "southward_loss_zj"] == 4.0
    assert result.loc[0, "northward_loss_zj"] == -5.0
    assert result.loc[0, "surface_loss_zj"] == 6.0
    assert result.loc[0, "storage_loss_zj"] == 7.0
    assert result.loc[0, "residual_audit_zj"] == 0.5


def test_phase_months_are_fixed() -> None:
    assert analysis.PHASE_MONTHS == {
        "arrival_Jan_Jun": (0, 1, 6),
        "redistribution_Jul_Dec": (0, 7, 12),
        "decay_Jan_May_next": (1, 1, 5),
    }


def test_audited_arrival_storage_changes() -> None:
    table = analysis.load_heat_fate_events(analysis.discover_input_root())
    arrival = table.loc[table.phase.eq("arrival_Jan_Jun")].set_index(
        ["event_year", "box"]
    )
    assert arrival.loc[(2015, "central"), "storage_change_zj"] == pytest.approx(
        2.6285, abs=0.005
    )
    assert arrival.loc[(2023, "central"), "storage_change_zj"] == pytest.approx(
        0.8720, abs=0.005
    )
    assert arrival.loc[(2015, "east"), "storage_change_zj"] == pytest.approx(
        8.6048, abs=0.005
    )
    assert arrival.loc[(2023, "east"), "storage_change_zj"] == pytest.approx(
        11.1155, abs=0.005
    )


def test_heat_fate_table_has_thirteen_events_three_phases_three_boxes() -> None:
    table = analysis.load_heat_fate_events(analysis.discover_input_root())
    assert len(table) == 13 * 3 * 3
    assert set(table.event_year) == set(analysis.EVENTS)
    assert set(table.box) == set(analysis.BOXES)
    assert set(table.phase) == set(analysis.PHASE_MONTHS)

