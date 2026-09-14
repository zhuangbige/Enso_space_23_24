from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_nonh20_third_question_chain as analysis  # noqa: E402


class NonH20ThirdQuestionChainTests(unittest.TestCase):
    def test_residualize_removes_linear_control(self) -> None:
        control = np.arange(10.0)
        values = 2.0 + 3.0 * control
        residual = analysis.residualize(values, control)
        self.assertTrue(np.allclose(residual, 0.0, atol=1.0e-12))

    def test_partial_correlation_recovers_shared_residual(self) -> None:
        control = np.arange(12.0)
        signal = np.array([1, -1] * 6, dtype=float)
        x = 2.0 * control + signal
        y = -3.0 * control + 4.0 * signal
        result = analysis.partial_correlation(x, y, control)
        self.assertAlmostEqual(result, 1.0)

    def test_bh_fdr_is_monotonic_in_rank(self) -> None:
        p = pd.Series([0.04, 0.001, 0.02, 0.8])
        q = analysis.bh_fdr(p)
        order = np.argsort(p.to_numpy())
        self.assertTrue(np.all(np.diff(q.to_numpy()[order]) >= -1.0e-12))
        self.assertTrue(((q >= p) & (q <= 1.0)).all())

    def test_zscore_has_zero_mean_and_unit_sample_variance(self) -> None:
        values = analysis.zscore(np.array([1.0, 2.0, 3.0, 4.0]))
        self.assertAlmostEqual(float(values.mean()), 0.0)
        self.assertAlmostEqual(float(values.std(ddof=1)), 1.0)


if __name__ == "__main__":
    unittest.main()
