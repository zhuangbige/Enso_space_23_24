import tempfile
import unittest
from pathlib import Path

from scripts.build_data_chain_inventory import build_inventory, write_csv, write_report


class DataChainInventoryTest(unittest.TestCase):
    def test_build_inventory_marks_existing_and_pending_nodes(self):
        rows = build_inventory()

        self.assertGreaterEqual(len(rows), 20)
        by_step = {row["step"]: row for row in rows}
        self.assertIn("01", by_step)
        self.assertIn("19", by_step)
        self.assertIn("22", by_step)
        self.assertEqual(by_step["19"]["source_ids"], "D5")
        self.assertEqual(by_step["22"]["source_ids"], "D6")
        self.assertTrue(by_step["22"]["next_action_if_missing"])

    def test_writers_emit_csv_and_report(self):
        rows = [
            {
                "step": "01",
                "layer": "test",
                "product": "present product",
                "status": "present",
                "local_path": "present.csv",
                "count_or_size": "1",
                "fields_or_keys": "a,b",
                "source_ids": "D1",
                "upstream_scripts": "script.py",
                "role": "role",
                "next_action_if_missing": "",
            },
            {
                "step": "02",
                "layer": "test",
                "product": "missing product",
                "status": "missing",
                "local_path": "missing.csv",
                "count_or_size": "",
                "fields_or_keys": "",
                "source_ids": "D2",
                "upstream_scripts": "script.py",
                "role": "role",
                "next_action_if_missing": "rerun",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = tmp / "inventory.csv"
            report_path = tmp / "report.md"

            write_csv(csv_path, rows)
            write_report(report_path, rows, csv_path)

            self.assertIn("missing product", csv_path.read_text(encoding="utf-8"))
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("已完成 1/2 个节点", report)
            self.assertIn("rerun", report)


if __name__ == "__main__":
    unittest.main()
