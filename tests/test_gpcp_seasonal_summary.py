import tempfile
import unittest
from pathlib import Path

from scripts.build_gpcp_seasonal_summary import build_summary_rows


class GpcpSeasonalSummaryTest(unittest.TestCase):
    def test_build_summary_rows_compares_2023_with_comparable_years(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "gpcp_monthly.csv"
            lines = ["region,year,month,precip,anomaly"]
            for year, value in ((1982, 1.0), (1997, 2.0), (2015, 3.0), (2023, 5.0)):
                for month in (4, 5, 6):
                    lines.append(f"central,{year},{month},{value},{value}")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            rows = build_summary_rows(path)

        amj = next(row for row in rows if row["region"] == "central" and row["season"] == "AMJ")
        self.assertEqual(amj["value_2023"], 5.0)
        self.assertEqual(amj["value_comparable"], 2.0)
        self.assertEqual(amj["difference_2023_minus_comparable"], 3.0)

    def test_build_summary_rows_handles_cross_year_djf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "gpcp_monthly.csv"
            lines = ["region,year,month,precip,anomaly"]
            for event_year, value in ((1982, 1.0), (1997, 2.0), (2015, 3.0), (2023, 6.0)):
                lines.append(f"central,{event_year},12,{value},{value}")
                lines.append(f"central,{event_year + 1},1,{value},{value}")
                lines.append(f"central,{event_year + 1},2,{value},{value}")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            rows = build_summary_rows(path)

        djf = next(row for row in rows if row["region"] == "central" and row["season"] == "DJF")
        self.assertEqual(djf["value_2023"], 6.0)
        self.assertEqual(djf["value_comparable"], 2.0)
        self.assertEqual(djf["difference_2023_minus_comparable"], 4.0)


if __name__ == "__main__":
    unittest.main()
