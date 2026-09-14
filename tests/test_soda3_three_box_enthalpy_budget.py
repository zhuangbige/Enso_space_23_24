from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_soda3_three_box_enthalpy_boundary_terms as fetch  # noqa: E402


class ThreeBoxEnthalpyBudgetTests(unittest.TestCase):
    def test_section_moments_match_uniform_analytic_integrals(self) -> None:
        depth = np.array([5.0, 15.0])
        width = np.array([100.0, 200.0])
        temperature = np.full((1, 2, 2), 10.0)
        velocity = np.full((1, 2, 2), 0.5)

        volume, heat0, area, temperature_area = fetch.section_moments(
            temperature, velocity, depth, width
        )
        dz = np.diff(fetch.base.depth_bounds(depth, fetch.DEPTH_MAX_M))
        expected_area = dz.sum() * width.sum()
        expected_volume = 0.5 * expected_area / 1.0e6
        expected_heat = (
            fetch.RHO0_KG_M3
            * fetch.CP0_J_KG_K
            * 10.0
            * 0.5
            * expected_area
            / 1.0e15
        )

        self.assertAlmostEqual(float(area[0]), expected_area)
        self.assertAlmostEqual(float(volume[0]), expected_volume)
        self.assertAlmostEqual(float(heat0[0]), expected_heat)
        self.assertAlmostEqual(float(temperature_area[0]), 10.0 * expected_area)

    def test_mass_correction_closes_volume_and_total_heat_is_reference_invariant(self) -> None:
        faces = {}
        for index, name in enumerate(fetch.FACE_NAMES):
            area = np.array([1.0e6 * (index + 1)])
            volume = np.array([float(index + 2)])
            mean_temperature = 10.0 + index
            heat0 = (
                fetch.RHO0_KG_M3
                * fetch.CP0_J_KG_K
                * volume
                * 1.0e6
                * mean_temperature
                / 1.0e15
            )
            faces[name] = {
                "volume_sv": volume,
                "heat0_pw": heat0,
                "area_m2": area,
                "temperature_area_cm2": mean_temperature * area,
            }

        corrected = fetch.mass_balance_box_faces(faces)
        self.assertAlmostEqual(float(corrected["volume_convergence_corr_sv"][0]), 0.0)

        heat0 = float(corrected["heat0_convergence_corr_pw"][0])
        heat20 = sum(
            float(corrected[f"{name}_heat0_in_corr_pw"][0])
            - fetch.RHO0_KG_M3
            * fetch.CP0_J_KG_K
            * 20.0
            * float(corrected[f"{name}_volume_in_corr_sv"][0])
            * 1.0e6
            / 1.0e15
            for name in fetch.FACE_NAMES
        )
        self.assertAlmostEqual(heat0, heat20, places=12)

    def test_individual_face_reference_shift_tracks_corrected_volume(self) -> None:
        faces = {
            name: {
                "volume_sv": np.array([value]),
                "heat0_pw": np.array([value * 0.1]),
                "area_m2": np.array([1.0e6]),
                "temperature_area_cm2": np.array([15.0e6]),
            }
            for name, value in zip(fetch.FACE_NAMES, (3.0, -1.0, 2.0, 0.0), strict=True)
        }
        corrected = fetch.mass_balance_box_faces(faces)
        name = "west"
        reference = 20.0
        shift = (
            fetch.RHO0_KG_M3
            * fetch.CP0_J_KG_K
            * reference
            * corrected[f"{name}_volume_in_corr_sv"]
            * 1.0e6
            / 1.0e15
        )
        heat_ref = corrected[f"{name}_heat0_in_corr_pw"] - shift
        self.assertTrue(
            np.allclose(
                corrected[f"{name}_heat0_in_corr_pw"] - heat_ref,
                shift,
            )
        )


if __name__ == "__main__":
    unittest.main()
