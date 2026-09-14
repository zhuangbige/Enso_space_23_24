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
    "fetch_soda3_chakravorty_transport_baseline",
    "scripts/fetch_soda3_chakravorty_transport_baseline.py",
)
analysis = load_script(
    "analyze_chakravorty2021_soda3_baseline",
    "scripts/analyze_chakravorty2021_soda3_baseline.py",
)


class ChakravortySoda3BaselineTest(unittest.TestCase):
    def test_d20_is_linearly_interpolated(self):
        depth = np.array([5.0, 15.0, 30.0])
        temperature = np.array([[[25.0], [21.0], [19.0]]])

        d20 = fetch.d20_from_temperature(temperature, depth)

        self.assertAlmostEqual(float(d20[0, 0]), 22.5)

    def test_layer_overlap_sums_to_d20(self):
        depth = np.array([5.0, 15.0, 30.0])
        d20 = np.array([[22.5, 0.0, 35.0]])

        overlap = fetch.layer_overlap(d20, depth)

        np.testing.assert_allclose(
            overlap.sum(axis=1),
            np.array([[22.5, 0.0, 35.0]]),
        )

    def test_section_transport_preserves_velocity_sign(self):
        depth = np.array([5.0, 15.0, 30.0])
        temperature = np.full((1, 3, 2), 22.0)
        velocity = np.full((1, 3, 2), 0.25)
        width = np.array([1000.0, 1000.0])

        positive_volume, positive_q20 = fetch.section_transports(
            temperature, velocity, depth, width
        )
        negative_volume, negative_q20 = fetch.section_transports(
            temperature, -velocity, depth, width
        )

        self.assertGreater(float(positive_volume[0]), 0.0)
        self.assertGreater(float(positive_q20[0]), 0.0)
        self.assertAlmostEqual(float(positive_volume[0]), -float(negative_volume[0]))
        self.assertAlmostEqual(float(positive_q20[0]), -float(negative_q20[0]))

    def test_same_month_detrending_removes_season_and_linear_trend(self):
        times = pd.date_range("1980-01-01", "1999-12-01", freq="MS") + pd.Timedelta(
            days=14
        )
        values = times.month.to_numpy() * 10.0 + (times.year.to_numpy() - 1980) * 0.5

        result = analysis.same_month_detrended(values, times, (1980, 1999))

        self.assertLess(float(np.nanmax(np.abs(result))), 1.0e-10)

    def test_year_chunks_cover_each_year_once(self):
        chunks = fetch.year_chunks(1980, 1992, 5)

        self.assertEqual(chunks, [(1980, 1984), (1985, 1989), (1990, 1992)])


if __name__ == "__main__":
    unittest.main()
