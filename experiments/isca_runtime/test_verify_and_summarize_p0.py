"""Small deterministic tests for the P0 paired-factorial calculations."""

from __future__ import annotations

import unittest

import pandas as pd

from verify_and_summarize_p0 import CASES, METRICS, bootstrap_summary, paired_effects


class FactorialEffectsTest(unittest.TestCase):
    def setUp(self) -> None:
        rows = []
        case_effect = {
            "ia0_fep0": 0.0,
            "ia0_fep1": 1.0,
            "ia1_fep0": 2.0,
            # 1 (FEP) + 2 (IA) + 3 (interaction)
            "ia1_fep1": 6.0,
        }
        for member in range(1, 11):
            for run in range(1, 7):
                baseline = 0.1 * member + 0.01 * run
                for case in CASES:
                    rows.append(
                        {
                            "case": case,
                            "member": member,
                            "run": run,
                            "month": run + 2,
                            "month_name": str(run),
                            **{
                                metric: baseline + case_effect[case]
                                for metric in METRICS
                            },
                        }
                    )
        self.monthly = pd.DataFrame(rows)

    def test_paired_contrast_values(self) -> None:
        effects = paired_effects(self.monthly)
        expected = {
            "FEP_at_IA0": 1.0,
            "FEP_at_IA1": 4.0,
            "IA_at_FEP0": 2.0,
            "IA_at_FEP1": 5.0,
            "IA_x_FEP": 3.0,
        }
        for contrast, value in expected.items():
            subset = effects.loc[effects["contrast"].eq(contrast), "value"]
            self.assertTrue((subset.round(12) == value).all(), contrast)

    def test_bootstrap_preserves_constant_interaction(self) -> None:
        effects = paired_effects(self.monthly)
        summary = bootstrap_summary(effects, samples=1_000, seed=42)
        interaction = summary.loc[summary["contrast"].eq("IA_x_FEP")]
        self.assertTrue((interaction["mean"].round(12) == 3.0).all())
        self.assertTrue((interaction["ci95_low"].round(12) == 3.0).all())
        self.assertTrue((interaction["ci95_high"].round(12) == 3.0).all())
        self.assertTrue((interaction["same_sign_fraction"] == 1.0).all())


if __name__ == "__main__":
    unittest.main()
