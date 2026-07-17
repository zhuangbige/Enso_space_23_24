import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from el_nino_decoupling.coupling_chain import (
    _validate_era5_units,
    eta_from_diagnostics,
    event_diagnostics,
    fit_monthly_models,
    load_oras5_d20,
    preprocess_monthly_series,
    validate_monthly_table,
)
from scripts.fetch_era5_coupling_fields import _split_cds_areas, build_request


class CouplingChainTest(unittest.TestCase):
    def test_same_month_detrending_removes_linear_trend(self):
        index = pd.date_range("1982-01-01", "2024-12-01", freq="MS")
        decimal_year = index.year + (index.month - 0.5) / 12.0
        seasonal = np.sin(2 * np.pi * (index.month - 1) / 12)
        raw = pd.Series(seasonal + 0.05 * decimal_year, index=index)

        processed = preprocess_monthly_series(raw)
        baseline = processed.loc["1982":"2022", "anomaly"]

        for month in range(1, 13):
            values = baseline[baseline.index.month == month]
            slope = np.polyfit(values.index.year, values.to_numpy(), 1)[0]
            self.assertAlmostEqual(float(slope), 0.0, places=10)

    def test_eta_projection_distinguishes_full_absent_and_reversed_response(self):
        rows = []
        expected = np.array([1.0, 2.0, -1.0])
        for event, factor in (("full", 1.0), ("absent", 0.0), ("reversed", -1.0)):
            for value in expected:
                rows.append(
                    {
                        "event": event,
                        "product_combo": "synthetic",
                        "link": "atmospheric",
                        "link_label": "synthetic link",
                        "expected_feedback": value,
                        "observed_innovation": factor * value,
                        "time": pd.Timestamp("2023-04-01"),
                    }
                )

        scores = eta_from_diagnostics(pd.DataFrame(rows)).set_index("event")

        self.assertAlmostEqual(float(scores.loc["full", "eta"]), 1.0)
        self.assertAlmostEqual(float(scores.loc["absent", "eta"]), 0.0)
        self.assertAlmostEqual(float(scores.loc["reversed", "eta"]), -1.0)

    def test_monthly_models_recover_known_atmospheric_feedback(self):
        rng = np.random.default_rng(7)
        index = pd.date_range("1982-01-01", "2024-12-01", freq="MS")
        n = len(index)
        sst = rng.normal(size=n)
        table = pd.DataFrame(index=index)
        table["nino3_sst_anom"] = sst
        table["tau_x_era5_anom"] = 0.3 * sst + rng.normal(scale=0.01, size=n)
        table["d20_east_anom"] = rng.normal(scale=10, size=n)
        table["d20_slope_anom"] = rng.normal(scale=10, size=n)
        table["qnet_nino3_anom"] = -12 * sst + rng.normal(scale=0.1, size=n)

        coefficients = fit_monthly_models(table)
        atmospheric = coefficients[coefficients["link"] == "atmospheric"]
        damping = coefficients[coefficients["link"] == "thermal_damping"]

        self.assertTrue(np.allclose(atmospheric["feedback_beta"], 0.3, atol=0.01))
        self.assertTrue(np.allclose(damping["feedback_beta"], -12, atol=0.1))
        self.assertTrue((coefficients["baseline_end"] == 2022).all())

    def test_event_diagnostics_subtracts_persistence_before_eta(self):
        index = pd.date_range("2023-04-01", "2024-03-01", freq="MS")
        table = pd.DataFrame(index=index)
        table["nino3_sst_anom"] = np.linspace(1, 2, len(index))
        table["tau_x_era5_anom"] = 0.5 * table["nino3_sst_anom"]
        table["d20_east_anom"] = np.linspace(2, 3, len(index))
        table["d20_slope_anom"] = np.linspace(3, 4, len(index))
        table["qnet_nino3_anom"] = -10 * table["nino3_sst_anom"]
        coefficient_rows = []
        for link, beta, persistence in (
            ("atmospheric", 0.5, 0.0),
            ("ocean_adjustment", 0.0, 1.0),
            ("thermocline_feedback", 0.0, 1.0),
            ("thermal_damping", -10.0, 0.0),
        ):
            for month in range(1, 13):
                coefficient_rows.append(
                    {
                        "link": link,
                        "month": month,
                        "intercept": 0.0,
                        "persistence": persistence,
                        "feedback_beta": beta,
                    }
                )
        diagnostics = event_diagnostics(
            table,
            pd.DataFrame(coefficient_rows),
            event_label="synthetic",
            start=pd.Timestamp(2023, 4, 1),
            end=pd.Timestamp(2024, 2, 1),
        )
        scores = eta_from_diagnostics(diagnostics).set_index("link")

        self.assertAlmostEqual(float(scores.loc["atmospheric", "eta"]), 1.0)
        self.assertAlmostEqual(float(scores.loc["thermal_damping", "eta"]), 1.0)

    def test_validation_rejects_missing_required_event_month(self):
        index = pd.date_range("1982-01-01", "2026-05-01", freq="MS")
        table = pd.DataFrame(
            1.0,
            index=index,
            columns=[
                "nino3_sst_anom",
                "tau_x_era5_anom",
                "d20_east_anom",
                "d20_west_anom",
                "d20_slope_anom",
                "qnet_nino3_anom",
            ],
        )
        table.loc[pd.Timestamp("2023-09-01"), "d20_east_anom"] = np.nan

        with self.assertRaisesRegex(ValueError, "2023/24 event plus lag target"):
            validate_monthly_table(table)

    def test_western_d20_region_crosses_date_line_to_170w(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "d20.csv"
            pd.DataFrame(
                {
                    "year": [2000] * 6,
                    "month": [1] * 6,
                    "requested_lon": [140, 170, 180, 190, 210, 260],
                    "d20_m": [10, 20, 30, 40, 50, 70],
                }
            ).to_csv(path, index=False)

            result = load_oras5_d20(path)

        self.assertAlmostEqual(float(result.iloc[0]["d20_west"]), 25.0)
        self.assertAlmostEqual(float(result.iloc[0]["d20_east"]), 60.0)
        self.assertAlmostEqual(float(result.iloc[0]["d20_slope"]), 35.0)


class Era5CouplingDownloadTest(unittest.TestCase):
    def test_era5_unit_metadata_is_checked_by_field_role(self):
        _validate_era5_units(SimpleNamespace(attrs={"units": "N m**-2"}), "tau_x")
        _validate_era5_units(SimpleNamespace(attrs={"units": "W m**-2"}), "latent")
        with self.assertRaisesRegex(ValueError, "expected W m-2"):
            _validate_era5_units(SimpleNamespace(attrs={"units": "J m**-2"}), "latent")

    def test_default_pacific_area_splits_at_date_line(self):
        areas = _split_cds_areas([10, 120, -10, 280])

        self.assertEqual(len(areas), 2)
        self.assertEqual(areas[0][1], [10.0, 120.0, -10.0, 180.0])
        self.assertEqual(areas[1][1], [10.0, -180.0, -10.0, -80.0])

    def test_request_uses_monthly_mean_fields_and_explicit_format(self):
        request = build_request(
            years=["2023", "2024"], month="01", area=[10, 120, -10, 180], grid=1.0
        )

        self.assertEqual(request["product_type"], ["monthly_averaged_reanalysis"])
        self.assertIn("mean_eastward_turbulent_surface_stress", request["variable"])
        self.assertEqual(request["data_format"], "netcdf")
        self.assertEqual(request["grid"], [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
