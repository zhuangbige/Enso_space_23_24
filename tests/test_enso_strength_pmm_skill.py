"""Scientific contract tests for the frozen event-stratified forecast comparison."""
from pathlib import Path
import json
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import analyze_enso_strength_pmm_skill as analysis
import three_event_segmented_slim as slim


class EventSkillTests(unittest.TestCase):
    def test_published_decimal_boundaries(self):
        for text, expected in [("0.45", .5), ("0.95", 1.), ("1.45", 1.5), ("-0.45", -.5)]:
            self.assertEqual(analysis.rounded_oni(text), expected)
        self.assertEqual(analysis.classify(.9), "weak")
        self.assertEqual(analysis.classify(1.), "moderate")
        self.assertEqual(analysis.classify(1.5), "strong")
        self.assertEqual(analysis.classify(2.8), "strong")

    def test_four_overlapping_seasons_are_not_an_event(self):
        times = pd.date_range("2000-01-01", "2002-12-01", freq="MS")
        values = np.zeros(len(times))
        values[5:9] = .7
        oni = pd.DataFrame({"oni": values}, index=times)
        self.assertTrue(analysis.detect_events(oni).empty)
        oni.iloc[9, 0] = .7
        self.assertEqual(len(analysis.detect_events(oni)), 1)

    def test_frozen_catalog_covers_all_thirteen_events(self):
        events = analysis.detect_events(analysis.read_oni()).set_index("event")
        self.assertEqual(events.strength.to_dict(), analysis.EXPECTED)
        self.assertEqual(events.strength.value_counts().to_dict(), {"strong": 7, "moderate": 3, "weak": 3})
        self.assertEqual(events.loc["1986-1988", "development_years"], "1986,1987")
        self.assertEqual(events.loc["2014-2016", "development_years"], "2014,2015")
        self.assertEqual(events.loc["2019-2020", "n_seasons"], 5)
        self.assertEqual(events.loc["2014-2016", "holdout_start"], pd.Timestamp("2013-09-01"))
        self.assertEqual(events.loc["2014-2016", "holdout_end"], pd.Timestamp("2017-06-01"))

    def test_2002_2024_catalog_retains_eight_complete_events(self):
        events = analysis.detect_events(analysis.read_oni(), start_year=2002, end_year=2024).set_index("event")
        self.assertEqual(events.strength.to_dict(), {
            "2002-2003": "moderate", "2004-2005": "weak", "2006-2007": "weak",
            "2009-2010": "strong", "2014-2016": "strong", "2018-2019": "moderate",
            "2019-2020": "weak", "2023-2024": "strong"})
        self.assertEqual(events.n_development_years.sum(), 9)
        self.assertEqual(events.loc["2014-2016", "development_years"], "2014,2015")

    def test_2002_fit_preserves_full_reference_and_frozen_preprocessing(self):
        import analyze_enso_strength_fullperiod_d20 as continuous
        root = Path(__file__).resolve().parents[1]
        archive = json.loads((root / "outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014/frozen_models_and_preprocessing.json").read_text())
        raw, states, meta, display = continuous.load_and_prepare("2025-04-01", start="2002-01-01")
        self.assertEqual(len(raw), 276)
        self.assertEqual(len(states), 276)
        old = archive["preprocessing"]
        for key in ("clim", "beta", "center"):
            np.testing.assert_allclose(meta[key], old[key], atol=1e-10, rtol=0)
        np.testing.assert_allclose(display[["sst", "d20"]], old["clim"], atol=1e-10, rtol=0)
        self.assertAlmostEqual(meta["pmm_sst_mean"], old["pmm_mean"][0])

    def test_event_weighting_is_not_pair_weighting(self):
        frame = pd.DataFrame({"event": ["A"]+["B"]*10, "strength": ["strong"]*11,
            "target": range(11), "init": range(11), "observed": np.zeros(11),
            "RO": [1.]+[3.]*10, "RO_PMM": [2.]+[6.]*10})
        events = analysis.event_metrics(frame)
        group = analysis.aggregate(events, "strong")
        self.assertAlmostEqual(group["RMSE_RO"], np.sqrt(5))
        self.assertNotAlmostEqual(group["RMSE_RO"], np.sqrt(91/11))
        self.assertAlmostEqual(group["improvement_percent"], -100.)
        self.assertAlmostEqual(group["ci_low"], -100.)
        self.assertAlmostEqual(group["ci_high"], -100.)
        self.assertEqual(group["improved_events"], 0)
        self.assertEqual(group["worsened_events"], 2)

    def test_zero_baseline_is_explicitly_undefined(self):
        self.assertTrue(np.isnan(analysis.improvement(0., 1.)))
        self.assertEqual(analysis.improvement(1., 0.), 100.)

    def test_first_season_contains_lead_zero_once(self):
        dates = pd.date_range("2000-02-01", periods=10, freq="MS")
        frame = pd.DataFrame({"event": "A", "strength": "weak", "development_year": 2000,
            "init": dates[0], "init_month": 2, "lead": range(10), "target": dates,
            "observed": np.arange(10.)**2, "RO": np.arange(10.), "RO_PMM": 2*np.arange(10.)})
        result = analysis.seasonal_forecasts(frame).set_index("lead")
        self.assertEqual(result.index.tolist(), list(range(1, 6)))
        self.assertAlmostEqual(result.loc[1, "observed"], 5/3)
        self.assertEqual(result.loc[1, "RO"], 1.)
        self.assertEqual(result.loc[5, "target"], dates[5])

    def test_forecast_matches_known_constant_operator(self):
        columns = ["sst", "wwv26"]
        coef = np.zeros((5, 2, 2))
        coef[0] = np.diag([-1., -.5])
        model = dict(coef=coef, scale=np.ones(2), order=2, columns=columns)
        dates = pd.date_range("2000-02-01", periods=10, freq="MS")
        meta = dict(clim=np.zeros((12, 2)), trend=np.zeros((2, 2)), center=2000.)
        display = pd.DataFrame(0., index=range(1, 13), columns=columns)
        pred, _ = analysis.predict_from_initial(model, meta, [2., 3.], dates, display)
        truth = np.column_stack([2*np.exp(-np.arange(10)/12), 3*np.exp(-.5*np.arange(10)/12)])
        np.testing.assert_allclose(pred, truth, atol=1e-10, rtol=0)

    def test_gap_exclusion_does_not_leak_into_preprocessing_or_moments(self):
        index = pd.date_range("1982-01-01", periods=180, freq="MS")
        rng = np.random.default_rng(109)
        raw = pd.DataFrame(rng.normal(size=(180, 3)), index=index, columns=["sst", "wwv26", "pmm"])
        mask = np.ones(180, dtype=bool)
        mask[60:100] = False
        changed = raw.copy()
        changed.loc[~mask] += 1000
        a, meta = analysis.prepare(raw, mask)
        b, altered_meta = analysis.prepare(changed, mask)
        for key in ("clim", "trend"):
            np.testing.assert_allclose(meta[key], altered_meta[key], atol=1e-12)
        ma, scale_a, diag_a = slim.pool_moments(a, mask)
        mb, scale_b, _ = slim.pool_moments(b, mask)
        np.testing.assert_allclose(scale_a, scale_b, atol=1e-12)
        self.assertEqual([s["months"] for s in diag_a["segments"]], [60, 80])
        for lag in (1, 6):
            for expected, actual in zip(ma[lag], mb[lag]):
                np.testing.assert_allclose(expected, actual, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
