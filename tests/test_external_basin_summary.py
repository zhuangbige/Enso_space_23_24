import tempfile
import unittest
from pathlib import Path

from scripts.build_external_basin_summary import build_summary_rows
from scripts.extract_oisst_external_basin_indices import chunk_ranges


class ExternalBasinSummaryTest(unittest.TestCase):
    def test_chunk_ranges_cover_inclusive_bounds(self):
        self.assertEqual(chunk_ranges(4, 10, 3), [(4, 6), (7, 9), (10, 10)])

    def test_build_summary_rows_compares_2023_with_comparable_years(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "external.csv"
            path.write_text(
                "region,year,month,sst,anomaly\n"
                "tna,1982,4,1,1\n"
                "tna,1982,5,1,1\n"
                "tna,1982,6,1,1\n"
                "tna,1997,4,2,2\n"
                "tna,1997,5,2,2\n"
                "tna,1997,6,2,2\n"
                "tna,2015,4,3,3\n"
                "tna,2015,5,3,3\n"
                "tna,2015,6,3,3\n"
                "tna,2023,4,5,5\n"
                "tna,2023,5,5,5\n"
                "tna,2023,6,5,5\n",
                encoding="utf-8",
            )

            rows = build_summary_rows(path)

        amj = next(row for row in rows if row["region"] == "tna" and row["season"] == "AMJ")
        self.assertEqual(amj["value_2023"], 5.0)
        self.assertEqual(amj["value_comparable"], 2.0)
        self.assertEqual(amj["difference_2023_minus_comparable"], 3.0)


if __name__ == "__main__":
    unittest.main()
