import unittest

from el_nino_decoupling.raw_indices import (
    monthly_anomalies,
    seasonal_mean_by_months,
    seasonal_event_mean,
    subtract_monthly_climatology_cube,
    weighted_region_mean,
    weighted_region_mean_timeseries,
)


class RawIndexHelpersTest(unittest.TestCase):
    def test_weighted_region_mean_uses_cos_lat_weights(self):
        values = [
            [1.0, 1.0],
            [3.0, 3.0],
        ]
        lats = [0.0, 60.0]

        result = weighted_region_mean(values, lats)

        self.assertAlmostEqual(result, (1.0 * 1.0 + 3.0 * 0.5) / 1.5)

    def test_weighted_region_mean_timeseries_uses_same_weights_for_each_time(self):
        values = [
            [
                [1.0, 1.0],
                [3.0, 3.0],
            ],
            [
                [2.0, 2.0],
                [6.0, 6.0],
            ],
        ]
        lats = [0.0, 60.0]

        result = weighted_region_mean_timeseries(values, lats)

        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0], (1.0 * 1.0 + 3.0 * 0.5) / 1.5)
        self.assertAlmostEqual(result[1], (2.0 * 1.0 + 6.0 * 0.5) / 1.5)

    def test_monthly_anomalies_remove_reference_climatology(self):
        records = [
            {"year": 2000, "month": 1, "value": 10.0},
            {"year": 2001, "month": 1, "value": 12.0},
            {"year": 2002, "month": 1, "value": 15.0},
        ]

        anomalies = monthly_anomalies(records, reference_start=2000, reference_end=2001)

        self.assertEqual([row["anomaly"] for row in anomalies], [-1.0, 1.0, 4.0])

    def test_seasonal_event_mean_handles_jun_to_next_jan(self):
        records = [{"year": 2023, "month": month, "anomaly": 1.0} for month in range(6, 13)]
        records.append({"year": 2024, "month": 1, "anomaly": 3.0})

        result = seasonal_event_mean(records, event_year=2023, months=(6, 7, 8, 9, 10, 11, 12, 13))

        self.assertEqual(result, 1.25)

    def test_seasonal_mean_by_months_handles_djf(self):
        records = [
            {"year": 2023, "month": 12, "anomaly": 1.0},
            {"year": 2024, "month": 1, "anomaly": 2.0},
            {"year": 2024, "month": 2, "anomaly": 3.0},
        ]

        self.assertEqual(seasonal_mean_by_months(records, event_year=2023, months=(12, 13, 14)), 2.0)

    def test_subtract_monthly_climatology_cube_uses_reference_years(self):
        records = [
            {"year": 2000, "month": 1, "values": [[1.0, 2.0]]},
            {"year": 2001, "month": 1, "values": [[3.0, 4.0]]},
            {"year": 2002, "month": 1, "values": [[6.0, 8.0]]},
        ]

        anomalies = subtract_monthly_climatology_cube(records, reference_start=2000, reference_end=2001)

        self.assertEqual(anomalies[2]["values"], [[4.0, 5.0]])


if __name__ == "__main__":
    unittest.main()
