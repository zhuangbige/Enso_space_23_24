from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.build_simplified_enso_ppt_assets_20260811 import build_assets


EXPECTED_IMAGES = (
    "fig-q1-hovmoller-en.png",
    "fig-q1-trajectory-en.png",
    "fig-q1-arrival-en.png",
    "fig-q2-partition-en.png",
    "fig-q3-independent-constraints-en.png",
)


class SimplifiedEnsoPptAssetsTests(unittest.TestCase):
    def test_highlight_values_match_authoritative_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit = build_assets(Path(directory))

        self.assertEqual(
            audit["arrival"]["1997"],
            {"inflow_zj": 16.95640595, "ohc_gain_zj": 17.31754541},
        )
        self.assertEqual(
            audit["arrival"]["2015"],
            {"inflow_zj": 8.48760368, "ohc_gain_zj": 8.604799183},
        )
        self.assertEqual(
            audit["arrival"]["2023"],
            {"inflow_zj": 9.903187024, "ohc_gain_zj": 11.11554695},
        )

        self.assertAlmostEqual(audit["trajectory"]["1997"]["median_eastward_deg"], 29.983107932136818, places=12)
        self.assertAlmostEqual(audit["trajectory"]["2015"]["active_weight_fraction"], 0.6379708821012113, places=12)
        self.assertAlmostEqual(audit["trajectory"]["2023"]["median_eastward_deg"], 17.654947997177857, places=12)

        self.assertEqual(audit["partition"]["1997"]["surface_loss_zj"], 4.913400194)
        self.assertEqual(audit["partition"]["2015"]["surface_loss_zj"], 1.508469573)
        self.assertEqual(audit["partition"]["2023"]["surface_loss_zj"], 0.4654415672)
        self.assertEqual(audit["partition"]["2015"]["residual_zj"], -6.385269096)
        self.assertEqual(audit["partition"]["2023"]["southward_output_zj"], -0.722921236)

    def test_q3_correlations_and_units_are_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit = build_assets(Path(directory))

        self.assertEqual(round(audit["q3"]["early_north_to_ne925"]["partial_r"], 2), 0.68)
        self.assertEqual(audit["q3"]["early_north_to_ne925"]["y_unit"], "m s-1")
        self.assertEqual(round(audit["q3"]["stress_to_north"]["partial_r"], 2), 0.74)
        self.assertEqual(audit["q3"]["stress_to_north"]["x_unit"], "N m-2")
        self.assertEqual(round(audit["q3"]["sst_to_surface"]["partial_r"], 2), 0.65)
        self.assertEqual(audit["q3"]["sst_to_surface"]["x_unit"], "degC")

    def test_figures_are_created_at_presentation_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_assets(output)
            for filename in EXPECTED_IMAGES:
                image_path = output / filename
                self.assertTrue(image_path.exists(), filename)
                with Image.open(image_path) as image:
                    self.assertGreaterEqual(image.width, 1800, (filename, image.size))
                    self.assertGreaterEqual(image.height, 900, (filename, image.size))


if __name__ == "__main__":
    unittest.main()
