import tempfile
import unittest
from pathlib import Path

from el_nino_decoupling.analysis import (
    EventRecord,
    average_lon_time,
    average_lon_level,
    compute_fig1_event_records,
    response_strength_ratio,
    write_event_records,
)


class AnalysisExtractionTest(unittest.TestCase):
    def test_compute_fig1_event_records_marks_highlight_years_and_residuals(self):
        records = compute_fig1_event_records(
            nino3=[0.0, 1.0, 2.0],
            uwind=[0.0, 1.0, 1.0],
            soi=[0.0, -1.0, -1.0],
            start_year=2000,
            highlight_years=(2001,),
        )

        self.assertEqual([record.year for record in records], [2000, 2001, 2002])
        self.assertTrue(records[1].highlight)
        self.assertFalse(records[0].highlight)
        self.assertIsNotNone(records[2].uwind_expected)
        self.assertAlmostEqual(records[2].uwind_residual, records[2].uwind - records[2].uwind_expected)

    def test_write_event_records_outputs_csv(self):
        records = [
            EventRecord(
                year=2023,
                nino3=2.1,
                uwind=0.4,
                soi=-0.5,
                uwind_expected=1.2,
                soi_expected=-1.5,
                uwind_residual=-0.8,
                soi_residual=1.0,
                uwind_coupling_ratio=1 / 3,
                soi_coupling_ratio=1 / 3,
                highlight=True,
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.csv"
            write_event_records(records, path)
            text = path.read_text(encoding="utf-8")

        self.assertIn("year,nino3,uwind,soi", text)
        self.assertIn("2023,2.1,0.4,-0.5", text)

    def test_average_lon_time_selects_requested_window(self):
        lon = [100, 120, 140]
        # shape: lon x time
        values = [
            [1, 2, 3],
            [10, 20, 30],
            [100, 200, 300],
        ]

        result = average_lon_time(values, lon=lon, lon_min=110, lon_max=150, month_indices=[0, 1])

        self.assertEqual(result, 82.5)

    def test_average_lon_level_selects_requested_pressure_layer(self):
        lon = [0, 90, 180]
        levels = [200, 500]
        # shape: lon x level
        values = [
            [1, 2],
            [10, 20],
            [100, 200],
        ]

        result = average_lon_level(values, lon=lon, levels=levels, lon_min=0, lon_max=100, level_min=100, level_max=600)

        self.assertEqual(result, 8.25)

    def test_response_strength_ratio_handles_signed_and_absolute_metrics(self):
        self.assertAlmostEqual(response_strength_ratio(2.0, 4.0), 0.5)
        self.assertAlmostEqual(response_strength_ratio(-1.0, -4.0, use_absolute=True), 0.25)
        self.assertIsNone(response_strength_ratio(1.0, 0.0))


if __name__ == "__main__":
    unittest.main()
