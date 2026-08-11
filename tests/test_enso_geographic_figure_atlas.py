from __future__ import annotations

import unittest

import numpy as np

from scripts.enso_geographic_figures.config import BOXES, EVENTS
from scripts.enso_geographic_figures.data import (
    extract_event_budget,
    load_hovmoller,
    load_trajectory_data,
    to_display_longitude,
)


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


if __name__ == "__main__":
    unittest.main()
