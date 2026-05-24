import unittest

from el_nino_decoupling.seasonal_matrix import (
    build_matrix_records,
    response_efficiency,
    ratio_to_comparable,
)


class SeasonalMatrixTests(unittest.TestCase):
    def test_ratio_to_comparable_handles_signed_response(self):
        self.assertAlmostEqual(ratio_to_comparable(2.0, 1.0), 2.0)
        self.assertAlmostEqual(ratio_to_comparable(-0.5, 1.0), -0.5)

    def test_response_efficiency_uses_sst_ratio_denominator(self):
        self.assertAlmostEqual(response_efficiency(-0.25, 1.25), -0.2)

    def test_response_efficiency_returns_none_for_zero_sst_ratio(self):
        self.assertIsNone(response_efficiency(1.0, 0.0))

    def test_build_matrix_records_preserves_sources(self):
        rows = [
            {
                "season": "AMJ",
                "metric": "nino3_sst",
                "value_2023": 1.4,
                "value_comparable": 1.0,
                "source_ids": "D2",
            },
            {
                "season": "AMJ",
                "metric": "cwp_u",
                "value_2023": -0.2,
                "value_comparable": 1.0,
                "source_ids": "D4",
            },
        ]
        records = build_matrix_records(rows, sst_metric="nino3_sst")
        by_metric = {row["metric"]: row for row in records}
        self.assertAlmostEqual(by_metric["nino3_sst"]["ratio_to_comparable"], 1.4)
        self.assertAlmostEqual(
            by_metric["cwp_u"]["difference_2023_minus_comparable"], -1.2
        )
        self.assertAlmostEqual(
            by_metric["cwp_u"]["response_efficiency"], -0.14285714285714288
        )
        self.assertEqual(by_metric["cwp_u"]["source_ids"], "D4")


if __name__ == "__main__":
    unittest.main()
