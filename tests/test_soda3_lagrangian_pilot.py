from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pilot_soda3_lagrangian_connectivity import (  # noqa: E402
    Snapshot,
    TemperatureExpectedField,
    WEIGHT_COLUMN,
    classify_endpoint,
    integrate_interval,
    linear_expected_temperature,
    seed_particles,
    velocity_to_position_rates,
)


class SODA3LagrangianPilotTests(unittest.TestCase):
    def test_velocity_conversion_at_equator(self) -> None:
        positions = np.asarray([[220.0, 0.0, 50.0]])
        rates = velocity_to_position_rates(
            positions,
            np.asarray([1.0]),
            np.asarray([1.0]),
            np.asarray([1.0e-5]),
            w_to_depth_sign=-1.0,
        )
        expected_horizontal = 180.0 / (np.pi * 6_371_000.0)
        self.assertAlmostEqual(rates[0, 0], expected_horizontal)
        self.assertAlmostEqual(rates[0, 1], expected_horizontal)
        self.assertAlmostEqual(rates[0, 2], -1.0e-5)

    def test_backward_midpoint_uses_time_mean_velocity(self) -> None:
        z = np.asarray([5.0, 100.0, 200.0])
        lat = np.asarray([-8.0, 0.0, 8.0])
        lon = np.asarray([145.0, 220.0, 270.0])
        shape = (3, 3, 3)

        def snapshot(day: int, u_value: float) -> Snapshot:
            return Snapshot(
                pd.Timestamp("2000-01-01") + pd.Timedelta(days=day),
                z,
                z,
                lat,
                lon,
                lat,
                lon,
                np.full(shape, u_value),
                np.zeros(shape),
                np.full(shape, 1.0e-5),
            )

        earlier = snapshot(0, 0.0)
        later = snapshot(5, 2.0)
        positions, active, status, surface_hits = integrate_interval(
            np.asarray([[220.0, 0.0, 50.0]]),
            np.asarray([True]),
            np.asarray(["active"], dtype=object),
            np.asarray([0]),
            earlier,
            later,
            step_hours=6.0,
            w_to_depth_sign=-1.0,
        )
        expected_westward = (
            5.0 * 86_400.0 / 6_371_000.0 * 180.0 / np.pi
        )
        self.assertTrue(active[0])
        self.assertEqual(status[0], "active")
        self.assertAlmostEqual(220.0 - positions[0, 0], expected_westward, places=5)
        self.assertAlmostEqual(positions[0, 2], 50.0 + 4.32, places=4)
        self.assertEqual(surface_hits[0], 0)

    def test_endpoint_classification_preserves_failures(self) -> None:
        self.assertEqual(classify_endpoint(175.0, 0.0, True, "active"), "equatorial_west")
        self.assertEqual(classify_endpoint(200.0, 0.0, True, "active"), "equatorial_central")
        self.assertEqual(classify_endpoint(230.0, 0.0, True, "active"), "equatorial_east")
        self.assertEqual(classify_endpoint(210.0, 6.0, True, "active"), "north_of_5N")
        self.assertEqual(classify_endpoint(210.0, -6.0, True, "active"), "south_of_5S")
        self.assertEqual(classify_endpoint(210.0, 0.0, False, "depth_exit"), "depth_exit")

    def test_linear_expected_temperature_handles_trend_and_nan(self) -> None:
        years = np.asarray([2000, 2001, 2002, 2003])
        values = np.asarray(
            [
                [[10.0, np.nan]],
                [[12.0, 5.0]],
                [[14.0, 6.0]],
                [[16.0, 7.0]],
            ]
        )
        expected = linear_expected_temperature(values, years, 2004)
        self.assertAlmostEqual(expected[0, 0], 18.0)
        self.assertAlmostEqual(expected[0, 1], 8.0)

    def test_seed_particles_uses_positive_anomaly_not_20c_threshold(self) -> None:
        z = np.asarray([5.0, 100.0, 200.0])
        lat = np.asarray([-8.0, 0.0, 8.0])
        lon = np.asarray([145.0, 220.0, 270.0])
        shape = (3, 3, 3)
        snapshot = Snapshot(
            pd.Timestamp("2000-06-28"),
            z,
            z,
            lat,
            lon,
            lat,
            lon,
            np.zeros(shape),
            np.zeros(shape),
            np.zeros(shape),
            np.full(shape, 18.0),
        )
        baseline = TemperatureExpectedField(
            depth=z,
            lat=np.asarray([-5.0, 0.0, 5.0]),
            lon=np.asarray([220.0, 240.0, 260.0]),
            temperature_c=np.full((3, 3, 3), 17.0),
            month=6,
            baseline_start_year=1980,
            baseline_end_year=2024,
        )
        seeds = seed_particles(snapshot, 2000, baseline)
        self.assertGreater(len(seeds), 0)
        self.assertLess(seeds["release_temp_c"].max(), 20.0)
        self.assertTrue(np.allclose(seeds["release_temp_anomaly_c"], 1.0))
        self.assertTrue((seeds[WEIGHT_COLUMN] > 0.0).all())


if __name__ == "__main__":
    unittest.main()
