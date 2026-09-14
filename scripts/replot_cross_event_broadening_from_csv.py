#!/usr/bin/env python3
"""Rebuild the report scatter from the saved event points and statistics."""

from __future__ import annotations

import pandas as pd

import analyze_3d_warm_heat_spreading_decoupling as core
from run_cross_event_broadening_jja_coupling import POINTS_CSV, STATS_CSV


def main() -> int:
    points = pd.read_csv(POINTS_CSV)
    events = pd.DataFrame(
        {
            "year": points["year"],
            "total_full_0_300_gjm2_jfm": points[
                "jfm_total_three_band_ohc_gjm2"
            ],
            "offeq_full_0_300_gjm2_jfm": points[
                "jfm_offequatorial_ohc_gjm2"
            ],
            "coupling_pattern_residual_z_jja": points[
                "jja_pattern_adjusted_coupling_residual_z_raw"
            ],
        }
    )
    relationships = pd.read_csv(STATS_CSV)
    core.plot_cross_event_support(events, relationships)
    print(core.CROSS_EVENT_PNG)
    print(core.CROSS_EVENT_PDF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
