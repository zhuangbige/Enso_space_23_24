from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_soda3_5n_current_decomposition as analysis  # noqa: E402


class Soda35NCurrentDecompositionTest(unittest.TestCase):
    def test_eos80_standard_warm_seawater_density_is_physical(self) -> None:
        density = float(analysis.density_eos80(np.array(20.0), np.array(35.0)))
        self.assertGreater(density, 1024.0)
        self.assertLess(density, 1026.0)

    def test_finite_gradient_x_recovers_linear_gradient(self) -> None:
        longitude = np.arange(220.25, 223.0, 0.5)
        x = (
            analysis.EARTH_RADIUS
            * np.cos(np.deg2rad(analysis.LATITUDE))
            * np.deg2rad(longitude)
        )
        slope = 2.5e-7
        values = 4.0 + slope * x
        gradient = analysis.finite_gradient_x(
            values[None, :], longitude, analysis.LATITUDE
        )
        np.testing.assert_allclose(gradient, slope, rtol=1e-10, atol=1e-14)

    def test_vertical_integral_constant_field_uses_positive_down_depth(self) -> None:
        depth = np.array([5.0, 15.0, 30.0])
        field = np.full((2, 3, 4), 3.0)
        integrated = analysis.vertical_integral_from_surface(field, depth)
        expected = np.broadcast_to(3.0 * depth[None, :, None], integrated.shape)
        np.testing.assert_allclose(integrated, expected)

    def test_westward_stress_gives_northward_ekman_heat_at_5n(self) -> None:
        depth = np.array([5.0, 15.0, 30.0, 50.0])
        longitude = np.array([220.25, 220.75])
        temperature = np.full((1, depth.size, longitude.size), 25.0)
        westward_stress = np.full((1, longitude.size), -0.05)
        transport = analysis.ekman_heat_transport_pw(
            temperature,
            westward_stress,
            depth,
            longitude,
            280,
        )
        self.assertGreater(transport[0], 0.0)

    def test_same_month_detrending_removes_monthly_linear_signal(self) -> None:
        times = pd.DatetimeIndex(
            [
                pd.Timestamp(year=year, month=month, day=15)
                for year in range(1982, 1992)
                for month in (1, 2)
            ]
        )
        values = np.array(
            [
                (10.0 if time.month == 1 else -4.0) + 0.3 * time.year
                for time in times
            ]
        )
        anomaly = analysis.same_month_detrended_array(values, times, (1982, 1991))
        np.testing.assert_allclose(anomaly, 0.0, atol=1e-10)


if __name__ == "__main__":
    unittest.main()
