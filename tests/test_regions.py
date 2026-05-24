import unittest

from el_nino_decoupling.regions import REGION_BOUNDS, get_region


class RegionDefinitionTest(unittest.TestCase):
    def test_core_external_basin_regions_are_defined(self):
        self.assertIn("tropical_indian_ocean", REGION_BOUNDS)
        self.assertIn("maritime_continent", REGION_BOUNDS)
        self.assertIn("tropical_north_atlantic", REGION_BOUNDS)

    def test_get_region_returns_lon_360_bounds(self):
        region = get_region("tropical_north_atlantic")

        self.assertEqual(region.lon_min, 300.0)
        self.assertEqual(region.lon_max, 340.0)


if __name__ == "__main__":
    unittest.main()
