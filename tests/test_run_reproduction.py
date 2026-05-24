import unittest

from scripts.run_peng2025_reproduction import selected_scripts


class RunReproductionScriptTest(unittest.TestCase):
    def test_main_figures_selection(self):
        self.assertEqual(selected_scripts("main"), ["Fig1.py", "Fig2.py", "Fig3.py", "Fig4.py"])

    def test_selected_selection_accepts_explicit_scripts(self):
        self.assertEqual(selected_scripts("selected", ["Fig1.py", "Extended_Data_Fig1.py"]), ["Fig1.py", "Extended_Data_Fig1.py"])


if __name__ == "__main__":
    unittest.main()
