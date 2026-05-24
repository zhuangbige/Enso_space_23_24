import unittest

from el_nino_decoupling.indices import (
    coupling_ratio,
    nino_region_bounds,
    standardized_anomaly,
)


class IndexHelperTest(unittest.TestCase):
    def test_nino_regions_use_standard_bounds(self):
        self.assertEqual(nino_region_bounds("nino3"), (-5.0, 5.0, 210.0, 270.0))
        self.assertEqual(nino_region_bounds("nino3.4"), (-5.0, 5.0, 190.0, 240.0))

    def test_standardized_anomaly_uses_reference_period(self):
        values = [1.0, 2.0, 3.0, 4.0]
        standardized = standardized_anomaly(values, reference_values=[1.0, 2.0, 3.0])

        self.assertAlmostEqual(standardized[-1], (4.0 - 2.0) / 1.0)

    def test_coupling_ratio_handles_expected_response(self):
        self.assertAlmostEqual(coupling_ratio(observed=-0.4, expected=-1.2), 1.0 / 3.0)
        self.assertIsNone(coupling_ratio(observed=0.2, expected=0.0))


if __name__ == "__main__":
    unittest.main()
