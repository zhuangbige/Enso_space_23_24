"""Deterministic validation tests for the P0 publication-figure inputs."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from plot_p0_screening_results import CASES, CONTRASTS, METRICS, validate_monthly, validate_summary


def complete_monthly() -> pd.DataFrame:
    rows = []
    for case in CASES:
        for member in range(1, 11):
            for month in range(3, 9):
                rows.append(
                    {
                        "case": case,
                        "member": member,
                        "month": month,
                        **{metric: float(member + month) for metric in METRICS},
                    }
                )
    return pd.DataFrame(rows)


def complete_summary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "metric": metric,
                "contrast": contrast,
                "mean": 0.25,
                "ci95_low": -0.1,
                "ci95_high": 0.5,
                "n_members": 10,
            }
            for metric in METRICS
            for contrast in CONTRASTS
        ]
    )


class PlotInputValidationTest(unittest.TestCase):
    def test_complete_inputs_pass(self) -> None:
        validate_monthly(complete_monthly())
        validate_summary(complete_summary())

    def test_missing_month_is_rejected(self) -> None:
        monthly = complete_monthly()
        monthly = monthly.loc[~monthly["month"].eq(8)]
        with self.assertRaises(ValueError):
            validate_monthly(monthly)

    def test_duplicate_row_is_rejected(self) -> None:
        monthly = complete_monthly()
        monthly = pd.concat([monthly, monthly.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            validate_monthly(monthly)

    def test_nonfinite_metric_is_rejected(self) -> None:
        monthly = complete_monthly()
        monthly.loc[0, METRICS[0]] = np.nan
        with self.assertRaises(ValueError):
            validate_monthly(monthly)

    def test_bad_summary_member_count_is_rejected(self) -> None:
        summary = complete_summary()
        summary.loc[0, "n_members"] = 9
        with self.assertRaises(ValueError):
            validate_summary(summary)


if __name__ == "__main__":
    unittest.main()
