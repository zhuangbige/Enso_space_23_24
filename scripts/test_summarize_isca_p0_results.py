import unittest

import pandas as pd

from scripts.summarize_isca_p0_results import interaction_audit, orient


class ScientificSummaryTests(unittest.TestCase):
    def test_olr_is_reversed_and_interval_reordered(self):
        frame = pd.DataFrame(
            [
                {
                    "season": "MJJ",
                    "metric": "olr_cp_w_m2",
                    "contrast": "IA_x_FEP",
                    "n_members": 10,
                    "mean": 2.0,
                    "sd": 1.0,
                    "ci95_low": 1.0,
                    "ci95_high": 3.0,
                    "same_sign_fraction": 0.9,
                }
            ]
        )
        result = orient(frame).iloc[0]
        self.assertEqual(result["oriented_mean"], -2.0)
        self.assertEqual(result["oriented_ci95_low"], -3.0)
        self.assertEqual(result["oriented_ci95_high"], -1.0)

    def test_strong_suppressive_requires_ci_and_member_agreement(self):
        frame = pd.DataFrame(
            [
                {
                    "season": "MJJ",
                    "metric": "precip_cp_mm_day",
                    "contrast": "IA_x_FEP",
                    "n_members": 10,
                    "mean": -0.5,
                    "sd": 0.2,
                    "ci95_low": -0.8,
                    "ci95_high": -0.1,
                    "same_sign_fraction": 0.9,
                }
            ]
        )
        result = interaction_audit(orient(frame))
        self.assertEqual(result["metrics"][0]["grade"], "strong_suppressive")
        self.assertEqual(result["strong_suppressive_count"], 1)


if __name__ == "__main__":
    unittest.main()
