import unittest

from el_nino_decoupling.spatial import (
    difference_grid,
    grid_region_mean,
    seasonal_grid_mean,
)


class SpatialHelpersTest(unittest.TestCase):
    def test_seasonal_grid_mean_uses_event_year_months(self):
        records = [
            {"year": 2023, "month": 4, "values": [[1.0, 2.0], [3.0, 4.0]]},
            {"year": 2023, "month": 5, "values": [[2.0, 3.0], [4.0, 5.0]]},
            {"year": 2023, "month": 6, "values": [[3.0, 4.0], [5.0, 6.0]]},
        ]
        self.assertEqual(
            seasonal_grid_mean(records, 2023, (4, 5, 6)),
            [[2.0, 3.0], [4.0, 5.0]],
        )

    def test_seasonal_grid_mean_handles_cross_year_djf(self):
        records = [
            {"year": 2023, "month": 12, "values": [[1.0]]},
            {"year": 2024, "month": 1, "values": [[2.0]]},
            {"year": 2024, "month": 2, "values": [[3.0]]},
        ]
        self.assertEqual(seasonal_grid_mean(records, 2023, (12, 13, 14)), [[2.0]])

    def test_difference_grid_subtracts_cellwise(self):
        self.assertEqual(
            difference_grid([[3.0, 4.0]], [[1.0, 6.0]]),
            [[2.0, -2.0]],
        )

    def test_grid_region_mean_uses_lat_lon_bounds(self):
        values = [[1.0, 2.0], [3.0, 4.0]]
        lat = [-5.0, 5.0]
        lon = [180.0, 220.0]
        self.assertAlmostEqual(
            grid_region_mean(values, lat, lon, -6.0, 6.0, 170.0, 230.0),
            2.5,
        )


if __name__ == "__main__":
    unittest.main()
