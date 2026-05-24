import tempfile
import unittest
from pathlib import Path

from el_nino_decoupling.validation import compare_yearly_series, write_series_comparison


class RawValidationTest(unittest.TestCase):
    def test_compare_yearly_series_computes_difference(self):
        rows = compare_yearly_series(
            source_rows=[{"year": "2000", "value": "1.5"}],
            raw_rows=[{"event_year": "2000", "raw": "1.0"}],
            source_year_key="year",
            source_value_key="value",
            raw_year_key="event_year",
            raw_value_key="raw",
        )

        self.assertEqual(rows[0]["difference_raw_minus_source"], -0.5)

    def test_write_series_comparison_outputs_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "comparison.csv"
            write_series_comparison(
                [{"year": 2000, "source": 1.5, "raw": 1.0, "difference_raw_minus_source": -0.5}],
                output,
            )

            text = output.read_text(encoding="utf-8")

        self.assertIn("difference_raw_minus_source", text)
        self.assertIn("2000,1.5,1.0,-0.5", text)


if __name__ == "__main__":
    unittest.main()
