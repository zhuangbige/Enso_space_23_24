from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_5n_wind_stress_counterfactual as analysis  # noqa: E402


class Soda35NWindStressCounterfactualTest(unittest.TestCase):
    def test_baseline_plus_anomaly_reconstructs_input(self) -> None:
        times = pd.DatetimeIndex(
            [
                pd.Timestamp(year=year, month=month, day=15)
                for year in range(1982, 1992)
                for month in (1, 2)
            ]
        )
        values = np.array(
            [
                (4.0 if time.month == 1 else -2.0) + 0.2 * time.year
                for time in times
            ]
        )
        baseline, anomaly = analysis.baseline_and_anomaly(
            values, times, (1982, 1991)
        )
        np.testing.assert_allclose(baseline + anomaly, values)
        np.testing.assert_allclose(anomaly, 0.0, atol=1e-10)

    def test_scaled_stress_endpoints(self) -> None:
        baseline = np.array([[1.0, 2.0]])
        anomaly = np.array([[-0.2, 0.4]])
        np.testing.assert_allclose(
            analysis.scaled_stress(baseline, anomaly, 0.0), baseline
        )
        np.testing.assert_allclose(
            analysis.scaled_stress(baseline, anomaly, 1.0), baseline + anomaly
        )

    def test_fixed_temperature_ekman_response_is_affine_in_stress(self) -> None:
        depth = np.array([5.0, 15.0, 30.0, 50.0])
        longitude = np.array([220.25, 220.75])
        temperature = np.full((1, depth.size, longitude.size), 25.0)
        baseline = np.full((1, longitude.size), -0.03)
        anomaly = np.full((1, longitude.size), -0.02)
        reference = np.zeros(1)
        q0 = analysis.scenario_anomaly_pw(
            temperature, baseline, reference, depth, longitude, 280
        )
        q1 = analysis.scenario_anomaly_pw(
            temperature, baseline + anomaly, reference, depth, longitude, 280
        )
        qhalf = analysis.scenario_anomaly_pw(
            temperature, baseline + 0.5 * anomaly, reference, depth, longitude, 280
        )
        np.testing.assert_allclose(qhalf, 0.5 * (q0 + q1))
        self.assertGreater(q1[0], q0[0])


if __name__ == "__main__":
    unittest.main()
