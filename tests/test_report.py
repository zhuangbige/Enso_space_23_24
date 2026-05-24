import tempfile
import unittest
from pathlib import Path

from el_nino_decoupling.report import format_ratio, read_csv_rows, write_first_pass_report


class FirstPassReportTest(unittest.TestCase):
    def test_format_ratio_handles_missing_and_values(self):
        self.assertEqual(format_ratio(""), "NA")
        self.assertEqual(format_ratio("0.2712"), "0.271")

    def test_read_csv_rows_reads_dicts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")

            rows = read_csv_rows(path)

        self.assertEqual(rows, [{"a": "1", "b": "2"}])

    def test_write_first_pass_report_includes_core_claims(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fig1 = root / "fig1.csv"
            fig3 = root / "fig3.csv"
            fig4 = root / "fig4.csv"
            output = root / "report.md"
            fig1.write_text(
                "year,nino3,uwind,soi,uwind_coupling_ratio,soi_coupling_ratio,highlight\n"
                "2023,1.9,0.6,-0.4,0.27,0.31,True\n",
                encoding="utf-8",
            )
            fig3.write_text(
                "metric,experiment,region,window_or_layer,value\n"
                "taux,aCTRL,central_pacific_180_140w,jun_dec,0.020\n"
                "taux,aPac,central_pacific_180_140w,jun_dec,0.033\n"
                "taux,aIndAtl,central_pacific_180_140w,jun_dec,-0.010\n"
                "taux,aTrend,central_pacific_180_140w,jun_dec,-0.012\n",
                encoding="utf-8",
            )
            fig4.write_text(
                "case,experiment,month_index,month,nino3\n"
                "2023,CTRL,12,Dec,2.3\n"
                "2023,InitApr,12,Dec,1.7\n"
                "2023,Wind2023,12,Dec,0.7\n",
                encoding="utf-8",
            )

            write_first_pass_report(fig1, fig3, fig4, output)
            text = output.read_text(encoding="utf-8")

        self.assertIn("2023/24", text)
        self.assertIn("0.270", text)
        self.assertIn("aPac", text)
        self.assertIn("CTRL", text)


if __name__ == "__main__":
    unittest.main()
