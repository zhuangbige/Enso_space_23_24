from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import plot_2015_2023_heat_coupling_bridge as module


def test_event_order_includes_1997_as_the_historical_anchor() -> None:
    assert module.EVENT_YEARS == (1997, 2015, 2023)


def test_spherical_box_area_recovers_earth_surface_area() -> None:
    expected = 4.0 * np.pi * module.EARTH_RADIUS_M**2
    assert module.spherical_box_area_m2(0.0, 360.0, -90.0, 90.0) == pytest.approx(expected)


def test_heat_density_converts_zj_to_gj_per_square_metre() -> None:
    assert module.heat_density_gj_m2(1.0, 1.0e12) == pytest.approx(1.0)


def test_shared_density_limit_contains_all_three_events() -> None:
    values = pd.Series([-1.318, -0.114, 1.562, -0.616, 1.003])
    assert module.symmetric_density_limit(values) == pytest.approx(1.6)


def test_same_month_linear_anomaly_removes_monthwise_trend() -> None:
    rows = []
    for year in range(1982, 2016):
        for month in range(1, 13):
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "value": 0.15 * (year - 1982) + 2.0 * month,
                }
            )
    frame = pd.DataFrame(rows)
    anomaly = module.same_month_linear_anomaly(frame, "value")
    assert np.allclose(anomaly, 0.0, atol=1.0e-10)


def test_mjj_sst_contrast_uses_calendar_month_linear_anomalies(tmp_path: Path) -> None:
    rows = []
    for year in range(1982, 2016):
        for month in range(1, 13):
            event_offset = 0.0
            if year == 2015 and month in (5, 6, 7):
                event_offset = 1.5
            rows.append(
                {
                    "year": year,
                    "month": month,
                    "nino4_raw_c": 25.0 + 0.01 * (year - 1982) + month / 10 + event_offset,
                    "fep_raw_c": 24.0 + 0.02 * (year - 1982) + month / 10 + 2 * event_offset,
                }
            )
    source = tmp_path / "atmosphere.csv"
    pd.DataFrame(rows).to_csv(source, index=False)

    result = module.build_mjj_sst_contrast(source)

    event = result.loc[result.event_year.eq(2015)].set_index("region")
    assert event.loc["Nino4", "sst_anomaly_c"] == pytest.approx(1.5)
    assert event.loc["FEP", "sst_anomaly_c"] == pytest.approx(3.0)


def test_arrival_map_table_keeps_totals_and_computes_areal_density(tmp_path: Path) -> None:
    rows = []
    for event_year, scale in ((1997, 0.8), (2015, 1.0), (2023, 2.0)):
        for box, heat in (("west", -1.0), ("central", 2.0), ("east", 3.0)):
            rows.append(
                {
                    "event_year": event_year,
                    "phase": "arrival_Jan_Jun",
                    "box": box,
                    "storage_change_zj": scale * heat,
                    "west_theta_heat_in_zj": 8.0 * scale if box == "east" else 0.0,
                }
            )
    source = tmp_path / "three_box.csv"
    pd.DataFrame(rows).to_csv(source, index=False)

    result = module.build_arrival_map_table(source)

    east = result.loc[(result.event_year.eq(2015)) & result.box.eq("east")].iloc[0]
    expected_area = module.BOX_WET_AREA_M2["east"]
    full_rectangle = module.spherical_box_area_m2(220.0, 280.0, -10.0, 5.0)
    assert expected_area < full_rectangle
    assert east["storage_density_gj_m2"] == pytest.approx(
        module.heat_density_gj_m2(3.0, expected_area)
    )
    assert east["input_140w_zj"] == pytest.approx(8.0)


def test_pipeline_writes_separate_event_maps_and_coupling_figure(tmp_path: Path) -> None:
    three_box_rows = []
    for event_year, values, input_140w in (
        (1997, (-0.80, 3.10, 9.20), 9.10),
        (2015, (-1.39, 2.63, 8.60), 8.49),
        (2023, (-2.28, 0.87, 11.12), 9.90),
    ):
        for box, value in zip(("west", "central", "east"), values, strict=True):
            three_box_rows.append(
                {
                    "event_year": event_year,
                    "phase": "arrival_Jan_Jun",
                    "box": box,
                    "storage_change_zj": value,
                    "west_theta_heat_in_zj": input_140w if box == "east" else 0.0,
                }
            )
    three_box_csv = tmp_path / "three_box.csv"
    pd.DataFrame(three_box_rows).to_csv(three_box_csv, index=False)

    atmosphere_rows = []
    for year in (*range(1982, 2015), 2015, 2023):
        for month in range(1, 13):
            nino4_offset = (
                1.2 if year == 1997 else 1.0 if year == 2015 else 0.6 if year == 2023 else 0.0
            )
            fep_offset = (
                2.1 if year == 1997 else 1.9 if year == 2015 else 2.4 if year == 2023 else 0.0
            )
            atmosphere_rows.append(
                {
                    "year": year,
                    "month": month,
                    "nino4_raw_c": 25.0 + 0.01 * year + month / 10 + nino4_offset,
                    "fep_raw_c": 24.0 + 0.02 * year + month / 10 + fep_offset,
                }
            )
    atmosphere_csv = tmp_path / "atmosphere.csv"
    pd.DataFrame(atmosphere_rows).to_csv(atmosphere_csv, index=False)

    coupling_rows = []
    for year, scale in ((1997, 1.2), (2015, 1.0), (2023, 0.35)):
        for month in range(1, 13):
            coupling_rows.append(
                {
                    "year": year,
                    "month": month,
                    "net_ocean_loss_anom_wm2": scale * month,
                    "minus_olr_cp_wm2": scale * (month + 5),
                    "tau_cwp_anom_nm2": scale * month / 1000,
                }
            )
    coupling_csv = tmp_path / "coupling.csv"
    pd.DataFrame(coupling_rows).to_csv(coupling_csv, index=False)

    outputs = module.run_pipeline(
        three_box_csv=three_box_csv,
        atmosphere_csv=atmosphere_csv,
        coupling_csv=coupling_csv,
        output_dir=tmp_path / "figures",
    )

    assert len(outputs.map_pngs) == 3
    assert len(outputs.pdfs) == 4
    for path in (*outputs.map_pngs, outputs.coupling_png, *outputs.pdfs):
        assert path.exists()
        assert path.stat().st_size > 10_000
    assert outputs.arrival_audit_csv.exists()
    assert outputs.mjj_sst_audit_csv.exists()
