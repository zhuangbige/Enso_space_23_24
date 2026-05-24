import tempfile
import unittest
from pathlib import Path

from scripts.build_asynchronous_coupling_table import build_efficiency_rows, build_phase_rows


class AsynchronousCouplingTest(unittest.TestCase):
    def test_build_efficiency_rows_compares_atmosphere_to_sst_strength(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "seasonal.csv"
            path.write_text(
                "metric,season,value_2023,value_comparable,difference_2023_minus_comparable,notes\n"
                "nino3_sst_oisst,AMJ,2,1,1,x\n"
                "cwp_u_ncep_sig995,AMJ,1,4,-3,x\n"
                "soi_like_ncep,AMJ,-1,-4,3,x\n",
                encoding="utf-8",
            )

            rows = build_efficiency_rows(path)

        u_row = next(row for row in rows if row["metric"] == "cwp_u_ncep_sig995")
        soi_row = next(row for row in rows if row["metric"] == "soi_like_ncep")
        self.assertEqual(u_row["atmosphere_to_sst_efficiency"], 0.125)
        self.assertEqual(soi_row["atmosphere_to_sst_efficiency"], 0.125)

    def test_build_phase_rows_identifies_first_and_largest_deficit(self):
        rows = [
            {"metric": "cwp_u_ncep_sig995", "season": "AMJ", "coupling_deficit": -1.0},
            {"metric": "cwp_u_ncep_sig995", "season": "JJA", "coupling_deficit": -3.0},
            {"metric": "cwp_u_ncep_sig995", "season": "SON", "coupling_deficit": 0.5},
        ]

        phase = build_phase_rows(rows)

        self.assertEqual(phase[0]["first_deficit_window"], "AMJ")
        self.assertEqual(phase[0]["largest_deficit_window"], "JJA")


if __name__ == "__main__":
    unittest.main()
