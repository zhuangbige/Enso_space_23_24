from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import numpy as np

from scripts.enso_geographic_figures.config import BOXES, EVENTS
from scripts.enso_geographic_figures.data import (
    extract_event_budget,
    load_hovmoller,
    load_trajectory_data,
    open_geographic_fields,
    to_display_longitude,
)
from scripts.enso_geographic_figures.figures import (
    build_arrival_box_map,
    build_fate_budget_map,
    build_trajectory_connectivity,
)
from scripts.enso_geographic_figures.plotting import arrow_width_zj, save_figure_pair


class GeographicFigureDataTests(unittest.TestCase):
    def test_fixed_domains_and_events(self) -> None:
        self.assertEqual(EVENTS, (1997, 2015, 2023))
        self.assertEqual(BOXES["west"], (160.0, 180.0, -10.0, 5.0))
        self.assertEqual(BOXES["central"], (180.0, 220.0, -10.0, 5.0))
        self.assertEqual(BOXES["east"], (220.0, 280.0, -10.0, 5.0))

    def test_east_box_arrival_values_match_audited_csv(self) -> None:
        expected = {
            1997: (16.96, 17.32),
            2015: (8.49, 8.60),
            2023: (9.90, 11.12),
        }
        for event, (inflow, gain) in expected.items():
            row = extract_event_budget(event, "arrival_Jan_Jun", "east")
            self.assertEqual(round(row["west_theta_heat_in_zj"], 2), inflow)
            self.assertEqual(round(row["storage_change_zj"], 2), gain)

    def test_east_box_fate_values_match_audited_csv(self) -> None:
        expected_loss = {1997: 21.76, 2015: 19.89, 2023: 15.95}
        for event, loss in expected_loss.items():
            row = extract_event_budget(event, "decay_Jan_May_next", "east")
            self.assertEqual(round(-row["storage_change_zj"], 2), loss)

    def test_trajectory_ranges_and_particle_counts(self) -> None:
        trajectories, endpoints = load_trajectory_data()
        self.assertTrue(trajectories["lon"].between(0.0, 360.0).all())
        self.assertTrue(trajectories["lat"].between(-90.0, 90.0).all())
        self.assertEqual(
            endpoints.groupby("event")["particle_id"].nunique().to_dict(),
            {1997: 467, 2015: 483, 2023: 410},
        )

    def test_hovmoller_contains_all_events_and_finite_ocean_values(self) -> None:
        frame = load_hovmoller()
        self.assertEqual(tuple(sorted(frame["event_year"].unique())), EVENTS)
        self.assertTrue(np.isfinite(frame["ohc300_anom_gjm2"]).all())

    def test_display_longitude_conversion(self) -> None:
        actual = to_display_longitude(np.array([130.0, 180.0, 220.0, 280.0]))
        np.testing.assert_allclose(actual, np.array([130.0, 180.0, -140.0, -80.0]))


class GeographicPlottingTests(unittest.TestCase):
    def test_arrow_scale_is_monotonic_and_sign_independent(self) -> None:
        self.assertEqual(arrow_width_zj(0.0, 20.0), 0.0)
        self.assertLess(arrow_width_zj(10.0, 20.0), arrow_width_zj(20.0, 20.0))
        self.assertEqual(arrow_width_zj(-10.0, 20.0), arrow_width_zj(10.0, 20.0))

    def test_arrow_scale_rejects_nonpositive_reference(self) -> None:
        with self.assertRaises(ValueError):
            arrow_width_zj(1.0, 0.0)

    def test_export_creates_png_and_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            fig = plt.figure(figsize=(4, 2))
            axis = fig.add_subplot(111)
            axis.plot([0, 1], [0, 1], color="black")
            png, pdf = save_figure_pair(fig, "probe", Path(directory))
            self.assertEqual(png.name, "probe.png")
            self.assertEqual(pdf.name, "probe.pdf")
            self.assertGreater(png.stat().st_size, 5_000)
            self.assertGreater(pdf.stat().st_size, 1_000)


class GeographicFieldTests(unittest.TestCase):
    def test_geographic_field_schema(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "data/derived/research_2026/"
            "soda3_geographic_figure_fields_1997_2015_2023.nc"
        )
        with open_geographic_fields(path) as dataset:
            self.assertEqual(dataset.event.values.tolist(), [1997, 2015, 2023])
            self.assertEqual(
                dataset.ohc300_anom_gjm2.dims,
                ("event", "phase", "lat", "lon"),
            )
            self.assertEqual(
                dataset.attrs["baseline"],
                "1980-2022 same-calendar-month linear expectation",
            )
            self.assertGreaterEqual(float(dataset.lon.min()), 130.0)
            self.assertLessEqual(float(dataset.lon.max()), 280.0)
            self.assertGreaterEqual(float(dataset.lat.min()), -10.0)
            self.assertLessEqual(float(dataset.lat.max()), 5.0)
            self.assertTrue(np.isfinite(dataset.ohc300_anom_gjm2.values).any())


class ImmediateGeographicFigureTests(unittest.TestCase):
    def test_map_builders_return_audited_metadata_and_artifacts(self) -> None:
        with TemporaryDirectory() as directory:
            output_dir = Path(directory)
            trajectory = build_trajectory_connectivity(output_dir)
            arrival = build_arrival_box_map(output_dir)
            fate = build_fate_budget_map(output_dir)
            self.assertEqual(trajectory["particles"], {1997: 467, 2015: 483, 2023: 410})
            self.assertEqual(
                arrival["east_inflow_zj"], {1997: 16.96, 2015: 8.49, 2023: 9.90}
            )
            self.assertEqual(
                fate["storage_loss_zj"], {1997: 21.76, 2015: 19.89, 2023: 15.95}
            )
            self.assertGreater(fate["westward_return_zj"][1997], 0.0)
            for stem in (
                "fig02_trajectory_connectivity",
                "fig03_arrival_box_map",
                "fig04_fate_budget_map",
            ):
                self.assertGreater((output_dir / f"{stem}.png").stat().st_size, 50_000)
                self.assertGreater((output_dir / f"{stem}.pdf").stat().st_size, 5_000)


if __name__ == "__main__":
    unittest.main()
