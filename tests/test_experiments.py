import unittest

from el_nino_decoupling.experiments import (
    REQUIRED_AGCM_EXPERIMENTS,
    build_agcm_matrix,
    seasonal_windows,
)


class ExperimentMatrixTest(unittest.TestCase):
    def test_required_agcm_experiments_are_defined(self):
        experiments = build_agcm_matrix()
        experiment_ids = {experiment.id for experiment in experiments}

        self.assertEqual(set(REQUIRED_AGCM_EXPERIMENTS), experiment_ids)
        self.assertIn("global_observed_sst", experiment_ids)
        self.assertIn("pacific_only", experiment_ids)
        self.assertIn("atlantic_only", experiment_ids)
        self.assertIn("indian_ocean_only", experiment_ids)
        self.assertIn("atlantic_plus_indian", experiment_ids)
        self.assertIn("detrended_global_sst", experiment_ids)
        self.assertIn("trend_retained_global_sst", experiment_ids)

    def test_experiment_matrix_identifies_optional_heating_tests(self):
        optional = build_agcm_matrix(include_optional=True)
        optional_ids = {experiment.id for experiment in optional if experiment.optional}

        self.assertIn("tna_only", optional_ids)
        self.assertIn("ism_mc_heating", optional_ids)

    def test_seasonal_windows_cover_event_development(self):
        windows = seasonal_windows()

        self.assertEqual(windows["AMJ"], (4, 5, 6))
        self.assertEqual(windows["JJA"], (6, 7, 8))
        self.assertEqual(windows["SON"], (9, 10, 11))
        self.assertEqual(windows["DJF"], (12, 1, 2))


if __name__ == "__main__":
    unittest.main()
