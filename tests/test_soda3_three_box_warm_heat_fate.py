import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise ImportError(relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load_script(
    "fetch_soda3_three_box_warm_heat_budget",
    "scripts/fetch_soda3_three_box_warm_heat_budget.py",
)
analysis = load_script(
    "analyze_soda3_three_box_warm_heat_fate",
    "scripts/analyze_soda3_three_box_warm_heat_fate.py",
)


class ThreeBoxWarmHeatFateTest(unittest.TestCase):
    def test_box_cell_selections_do_not_overlap(self):
        longitude = np.arange(159.75, 280.26, 0.5)
        masks = [
            fetch.cell_selection(longitude, west, east)
            for west, east in fetch.BOXES.values()
        ]

        combined = sum(mask.astype(int) for mask in masks)

        self.assertEqual(int(combined.max()), 1)
        self.assertEqual([int(mask.sum()) for mask in masks], [40, 80, 120])

    def test_h20_matches_direct_volume_integral(self):
        depth = np.array([5.0, 15.0])
        latitude = np.array([-0.25, 0.25])
        longitude = np.array([160.25, 160.75])
        temperature = np.full((1, 2, 2, 2), 21.0)

        result = fetch.warm_heat_content_zj(
            temperature,
            depth=depth,
            latitude=latitude,
            longitude=longitude,
        )
        dz = np.diff(fetch.base.depth_bounds(depth, fetch.DEPTH_MAX_M))
        area = fetch.base.grid_cell_areas(latitude, longitude)
        expected = (
            fetch.RHO0_KG_M3
            * fetch.CP0_J_KG_K
            * dz.sum()
            * area.sum()
            / 1.0e21
        )

        self.assertAlmostEqual(float(result[0]), float(expected))

    def test_surface_warm_gate_excludes_cold_cells(self):
        latitude = np.array([-0.25, 0.25])
        longitude = np.array([160.25, 160.75])
        flux = np.full((1, 2, 2), 100.0)
        temperature = np.array([[[21.0, 19.0], [21.0, 19.0]]])

        all_pw, warm_pw, fraction = fetch.surface_heat_terms(
            flux,
            temperature,
            latitude=latitude,
            longitude=longitude,
        )

        self.assertAlmostEqual(float(warm_pw[0] / all_pw[0]), 0.5)
        self.assertAlmostEqual(float(fraction[0]), 0.5)

    def test_centered_storage_tendency_uses_actual_elapsed_seconds(self):
        times = pd.DatetimeIndex(
            [pd.Timestamp(2000, 1, 15), pd.Timestamp(2000, 2, 15), pd.Timestamp(2000, 3, 15)]
        )
        storage = np.array([0.0, 1.0, 2.0])

        result = analysis.centered_storage_tendency_pw(storage, times)
        expected = 2.0e6 / (times[2] - times[0]).total_seconds()

        self.assertTrue(np.isnan(result[0]))
        self.assertAlmostEqual(float(result[1]), float(expected))
        self.assertTrue(np.isnan(result[2]))


if __name__ == "__main__":
    unittest.main()
