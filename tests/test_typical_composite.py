from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from el_nino_decoupling.typical_composite import (
    bootstrap_mean_ci,
    classify_ep_cp,
    composite_fields,
    difference_fields,
    fit_expected_response,
    identify_warm_episodes,
    ordinary_event_manifest,
    weighted_taylor_statistics,
)


class TestOrdinaryEventSelection(unittest.TestCase):
    def test_multiyear_episode_uses_strongest_djf_for_developing_year(self) -> None:
        rows = []
        seasons = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")
        for year in (1986, 1987, 1988):
            for season in seasons:
                rows.append({"year": year, "season": season, "oni": -0.2})
        frame = pd.DataFrame(rows)
        active = {
            (1986, "ASO"): 0.7,
            (1986, "SON"): 0.9,
            (1986, "OND"): 1.1,
            (1986, "NDJ"): 1.2,
            (1987, "DJF"): 1.3,
            (1987, "JFM"): 1.2,
            (1987, "FMA"): 1.0,
            (1987, "MAM"): 0.8,
            (1987, "AMJ"): 0.7,
            (1987, "MJJ"): 0.8,
            (1987, "JJA"): 1.0,
            (1987, "JAS"): 1.4,
            (1987, "ASO"): 1.3,
            (1987, "SON"): 1.2,
            (1987, "OND"): 1.0,
            (1987, "NDJ"): 0.9,
            (1988, "DJF"): 0.8,
            (1988, "JFM"): 0.5,
        }
        for (year, season), value in active.items():
            frame.loc[(frame["year"] == year) & (frame["season"] == season), "oni"] = value

        episodes = identify_warm_episodes(frame)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].event_year, 1986)
        self.assertEqual(episodes[0].mature_djf_year, 1987)

    def test_ordinary_manifest_excludes_extreme_and_targets(self) -> None:
        rows = []
        seasons = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")
        for year in range(1982, 1999):
            for season in seasons:
                rows.append({"year": year, "season": season, "oni": -0.2})
        frame = pd.DataFrame(rows)
        for event_year, amplitude in ((1982, 2.2), (1986, 1.2), (1991, 1.6), (1997, 2.4)):
            for year, season in (
                (event_year, "ASO"),
                (event_year, "SON"),
                (event_year, "OND"),
                (event_year, "NDJ"),
                (event_year + 1, "DJF"),
            ):
                frame.loc[(frame["year"] == year) & (frame["season"] == season), "oni"] = amplitude
        manifest = ordinary_event_manifest(identify_warm_episodes(frame))
        self.assertEqual(manifest["event_year"].tolist(), [1986, 1991])


class TestCompositeMath(unittest.TestCase):
    @staticmethod
    def _fields(value: float) -> dict[str, object]:
        return {
            "lat": np.array([-1.0, 1.0]),
            "lon": np.array([160.0, 200.0]),
            "sst_lat": np.array([-1.0, 1.0]),
            "sst_lon": np.array([160.0, 200.0]),
            "d20_lon": np.array([160.0, 200.0]),
            "month_numbers": np.arange(1, 7),
            "months": np.array(["Jan", "Feb", "Mar", "Apr", "May", "Jun"]),
            "sst": np.full((6, 2, 2), value),
            "u850": np.full((6, 2, 2), value),
            "v850": np.full((6, 2, 2), value),
            "precip": np.full((6, 2, 2), value),
            "d20": np.full((6, 2), value),
        }

    def test_composite_and_difference_direction(self) -> None:
        fields = {1986: self._fields(1.0), 1991: self._fields(3.0)}
        composite = composite_fields(fields, [1986, 1991], method="test")
        self.assertTrue(np.allclose(composite["sst"], 2.0))
        difference = difference_fields(self._fields(5.0), composite, method="target minus reference")
        self.assertTrue(np.allclose(difference["sst"], 3.0))

    def test_bootstrap_constant_mean(self) -> None:
        center, lower, upper = bootstrap_mean_ci(np.ones((4, 6)), n_bootstrap=250, seed=7)
        self.assertTrue(np.allclose(center, 1.0))
        self.assertTrue(np.allclose(lower, 1.0))
        self.assertTrue(np.allclose(upper, 1.0))

    def test_expected_response_recovers_linear_relationship(self) -> None:
        x = np.arange(20, dtype=float)
        y = 2.0 * x + 1.0
        result = fit_expected_response(x, y, 3.0, 8.0)
        self.assertAlmostEqual(result["expected"], 7.0)
        self.assertAlmostEqual(result["residual"], 1.0)

    def test_ep_cp_classification(self) -> None:
        self.assertEqual(classify_ep_cp(1.0, 0.2), "EP")
        self.assertEqual(classify_ep_cp(0.1, 0.9), "CP")

    def test_taylor_statistics_keep_pattern_and_amplitude_separate(self) -> None:
        reference = np.array([1.0, 2.0, 3.0])
        candidate = 2.0 * reference + 4.0
        result = weighted_taylor_statistics(reference, candidate, np.ones(3))
        self.assertAlmostEqual(result["pattern_correlation"], 1.0)
        self.assertAlmostEqual(result["standard_deviation_ratio"], 2.0)
        self.assertGreater(result["centered_rmsd"], 0.0)
        self.assertAlmostEqual(result["mean_bias"], 6.0)

    def test_taylor_statistics_reject_shape_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "same shape"):
            weighted_taylor_statistics(np.ones(3), np.ones(4), np.ones(3))


if __name__ == "__main__":
    unittest.main()
