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


def test_same_month_detrending_removes_monthly_linear_signal() -> None:
    frame = analysis.synthetic_monthly_signal(1982, 2024)
    anomaly = analysis.same_month_linear_anomaly(frame, "value", (1982, 2014))
    assert np.allclose(anomaly, 0.0, atol=1e-10)


def test_cosine_box_mean_weights_latitude() -> None:
    field = xr.DataArray(
        [[0.0], [10.0]],
        dims=("lat", "lon"),
        coords={"lat": [0.0, 60.0], "lon": [220.0]},
    )
    assert float(analysis.cosine_box_mean(field, 0, 60, 220, 220)) == pytest.approx(
        10.0 / 3.0
    )


def test_event_wind_table_has_complete_primary_predictors() -> None:
    table = analysis.build_event_wind_table(analysis.discover_input_root())
    assert len(table) == 13 * 5
    assert set(table.event_year) == set(analysis.EVENTS)
    assert set(table.window) == set(analysis.WIND_WINDOWS)
    primary = [
        column
        for column in table
        if column.endswith(("_u10_anom_ms", "_wind_speed_anom_ms", "_tau_x_anom_nm2"))
    ]
    assert primary
    assert table[primary].notna().all().all()
    assert table["jiang_ne925_mjj_ms"].notna().all()


def test_partial_correlation_removes_shared_control() -> None:
    control = np.arange(13, dtype=float)
    noise = np.array([0, 1, -1, 1, -1, 0, 1, -1, 0, 1, -1, 0, 0], dtype=float)
    x = control + noise
    y = control - noise
    raw = np.corrcoef(x, y)[0, 1]
    adjusted = analysis.partial_correlation(x, y, control)
    assert raw > 0.8
    assert adjusted < -0.9


def test_relationship_statistics_reports_loeo_range() -> None:
    x = np.arange(13, dtype=float)
    result = analysis.relationship_statistics(x, 2.0 * x, np.zeros_like(x))
    assert result["pearson_r"] == pytest.approx(1.0)
    assert result["spearman_r"] == pytest.approx(1.0)
    assert result["partial_r"] == pytest.approx(1.0)
    assert result["loeo_r_min"] == pytest.approx(1.0)
    assert result["loeo_r_max"] == pytest.approx(1.0)


def test_prespecified_relationships_are_unique_and_complete() -> None:
    root = analysis.discover_input_root()
    heat = analysis.load_heat_fate_events(root)
    wind = analysis.build_event_wind_table(root)
    relationships = analysis.build_prespecified_relationships(heat, wind)
    key = ["box", "predictor_window", "response_phase", "response", "predictor"]
    assert not relationships.duplicated(key).any()
    assert set(relationships["n"]) == {13}
    assert relationships[["pearson_r", "spearman_r", "partial_r"]].notna().all().all()
    assert relationships["prespecified"].all()


def test_prespecified_rows_retain_highlight_values() -> None:
    root = analysis.discover_input_root()
    relationships = analysis.build_prespecified_relationships(
        analysis.load_heat_fate_events(root),
        analysis.build_event_wind_table(root),
    )
    row = relationships.loc[
        relationships.box.eq("central")
        & relationships.response_phase.eq("redistribution_Jul_Dec")
        & relationships.response.eq("storage_loss_zj")
        & relationships.predictor.eq("central_tau_x_anom_nm2")
        & relationships.predictor_window.eq("MJJ")
    ].iloc[0]
    assert row["response_2015"] == pytest.approx(4.041709, abs=0.005)
    assert row["response_2023"] == pytest.approx(-3.501413, abs=0.005)
    assert row["predictor_2015"] == pytest.approx(0.02004, abs=0.0002)
    assert row["predictor_2023"] == pytest.approx(0.00400, abs=0.0002)
