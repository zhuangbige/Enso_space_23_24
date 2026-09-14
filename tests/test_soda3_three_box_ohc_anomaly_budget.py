from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_soda3_three_box_ohc_anomaly_budget as analysis  # noqa: E402


class ThreeBoxOHCAnomalyBudgetTests(unittest.TestCase):
    def test_reference_heat_shift_uses_volume_transport(self) -> None:
        heat0 = np.array([1.0])
        volume = np.array([10.0])
        result = analysis.reference_heat_pw(heat0, volume, 20.0)
        expected_shift = (
            analysis.fetch.RHO0_KG_M3
            * analysis.fetch.CP0_J_KG_K
            * 20.0
            * 10.0
            * 1.0e6
            / 1.0e15
        )
        self.assertAlmostEqual(float(result[0]), 1.0 - expected_shift)

    def test_centered_storage_tendency_uses_actual_calendar_spacing(self) -> None:
        times = pd.DatetimeIndex(
            ["2000-01-15", "2000-02-15", "2000-03-15"]
        )
        result = analysis.centered_storage_tendency_pw(
            np.array([0.0, 1.0, 2.0]), times
        )
        expected = 2.0e6 / (times[2] - times[0]).total_seconds()
        self.assertTrue(np.isnan(result[0]))
        self.assertAlmostEqual(float(result[1]), expected)
        self.assertTrue(np.isnan(result[2]))

    def test_month_integration_converts_pw_to_zj(self) -> None:
        times = pd.Series(pd.to_datetime(["2001-01-15", "2001-02-15"]))
        values = pd.Series([1.0, 1.0])
        result = analysis.integrate_zj(values, times)
        expected = 31.0 * 86_400.0 / 1.0e6
        self.assertAlmostEqual(result, expected)

    def test_same_month_expected_recovers_monthly_linear_signal(self) -> None:
        times = pd.date_range("1980-01-01", "2022-12-01", freq="MS") + pd.Timedelta(days=14)
        values = 5.0 + 0.2 * times.year.to_numpy() + times.month.to_numpy()
        expected = analysis.same_month_expected(values, times)
        self.assertTrue(np.allclose(expected, values))


if __name__ == "__main__":
    unittest.main()
