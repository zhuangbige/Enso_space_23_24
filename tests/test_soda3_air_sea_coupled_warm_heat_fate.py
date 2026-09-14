from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
import xarray as xr

from scripts import analyze_soda3_air_sea_coupled_warm_heat_fate as coupling


class Soda3AirSeaCoupledWarmHeatFateTest(unittest.TestCase):
    def test_box_area_matches_spherical_rectangle(self) -> None:
        lat = np.arange(-9.5, 5.0, 1.0)
        lon = np.arange(220.5, 280.0, 1.0)
        calculated = coupling.box_area_m2(lat, lon).sum()
        expected = (
            coupling.EARTH_RADIUS**2
            * np.deg2rad(60.0)
            * (np.sin(np.deg2rad(5.0)) - np.sin(np.deg2rad(-10.0)))
        )
        self.assertAlmostEqual(calculated / expected, 1.0, places=12)

    def test_integrate_zj_uses_calendar_month_length(self) -> None:
        values = pd.Series([1.0, 1.0])
        times = pd.Series(pd.to_datetime(["2000-01-15", "2000-02-15"]))
        expected = (31 + 29) * 86400.0 * 1.0e-6
        self.assertAlmostEqual(coupling.integrate_zj(values, times), expected, places=12)

    def test_westward_stress_gives_northward_ekman_transport(self) -> None:
        transport = coupling.ekman_north_sv(np.array([-0.01, 0.01]), 220.0, 280.0)
        self.assertGreater(transport[0], 0.0)
        self.assertLess(transport[1], 0.0)
        self.assertAlmostEqual(transport[0], -transport[1], places=12)

    def test_integrated_power_is_linear_in_flux(self) -> None:
        field = xr.DataArray(
            np.ones((2, 2, 3)),
            dims=("time", "lat", "lon"),
            coords={"time": pd.date_range("2000-01-01", periods=2, freq="MS"), "lat": [-0.5, 0.5], "lon": [220.5, 221.5, 222.5]},
        )
        first = coupling.integrated_power_pw(field, -0.5, 0.5, 220.5, 222.5)
        second = coupling.integrated_power_pw(2.0 * field, -0.5, 0.5, 220.5, 222.5)
        np.testing.assert_allclose(second, 2.0 * first, rtol=0.0, atol=0.0)


if __name__ == "__main__":
    unittest.main()
