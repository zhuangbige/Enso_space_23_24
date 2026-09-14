#!/usr/bin/env python3
"""Reproduce the JFM OHC-broadening versus JJA coupling figure.

This is the compact entry point for the cross-event result used in the stage
report.  It starts from the local SODA3 temperature data, the existing moving
warm-core centroids, and the existing pattern-adjusted coupling table.  It
does not read a previously generated plot or event-metric CSV.

The detailed implementation lives in
``analyze_3d_warm_heat_spreading_decoupling.py`` so that the standalone result
and the full analysis cannot silently diverge.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import analyze_3d_warm_heat_spreading_decoupling as core


POINTS_CSV = (
    core.DERIVED / "enso_cross_event_broadening_jja_coupling_points.csv"
)
STATS_CSV = (
    core.DERIVED / "enso_cross_event_broadening_jja_coupling_statistics.csv"
)


def required_inputs() -> list[Path]:
    """Return every local input needed to rebuild the section from source."""

    return [
        core.TEMP_FILE,
        core.CENTROID_CSV,
        core.COUPLING_CSV,
        core.OLD_PARTITION_CSV,
        *[
            core.OUTER_CACHE
            / f"soda3_four_outer_latband_sums_{year}_jan_jun.npz"
            for year in core.YEARS
        ],
    ]


def build_points(events: pd.DataFrame) -> pd.DataFrame:
    """Construct the exact x and y residuals shown in the scatter plot."""

    total = events["total_full_0_300_gjm2_jfm"].to_numpy(dtype=float)
    off_equatorial = events[
        "offeq_full_0_300_gjm2_jfm"
    ].to_numpy(dtype=float)
    coupling = events[
        "coupling_pattern_residual_z_jja"
    ].to_numpy(dtype=float)
    x_residual = core.residualize(off_equatorial, total[:, None])
    y_residual = core.residualize(coupling, total[:, None])

    return pd.DataFrame(
        {
            "year": events["year"].to_numpy(dtype=int),
            "group": events["group"].astype(str),
            "jfm_total_three_band_ohc_gjm2": total,
            "jfm_offequatorial_ohc_gjm2": off_equatorial,
            "jfm_offequatorial_ohc_residual_gjm2": x_residual,
            "jja_pattern_adjusted_coupling_residual_z_raw": coupling,
            "jja_coupling_residual_after_total_ohc_control_z": y_residual,
        }
    )


def main() -> int:
    core.require_files(required_inputs())

    fields, depth, longitude = core.load_anomaly_fields()
    monthly = core.build_monthly_table(fields, depth, longitude)
    events = core.build_event_table(monthly)
    relationships = core.build_relationships(events)
    points = build_points(events)

    primary = relationships.loc[
        relationships["test_id"].eq("component_broadening")
    ].iloc[0]
    primary.to_frame().T.to_csv(STATS_CSV, index=False)
    points.to_csv(POINTS_CSV, index=False)
    core.plot_cross_event_support(events, relationships)

    point_2023 = points.loc[points["year"].eq(2023)].iloc[0]
    diagnostics = {
        "n_events": int(primary["n_events"]),
        "partial_r": float(primary["partial_r"]),
        "residual_rank_r": float(primary["partial_spearman_r"]),
        "permutation_p": float(primary["permutation_p"]),
        "fdr_q": float(primary["permutation_q_fdr"]),
        "bootstrap_95pct": [
            float(primary["bootstrap_ci_low"]),
            float(primary["bootstrap_ci_high"]),
        ],
        "leave_one_event_out_r": [
            float(primary["loeo_r_min"]),
            float(primary["loeo_r_max"]),
        ],
        "year_2023_x_gjm2": float(
            point_2023["jfm_offequatorial_ohc_residual_gjm2"]
        ),
        "year_2023_y_z": float(
            point_2023[
                "jja_coupling_residual_after_total_ohc_control_z"
            ]
        ),
        "points_csv": str(POINTS_CSV),
        "statistics_csv": str(STATS_CSV),
        "figure_png": str(core.CROSS_EVENT_PNG),
        "figure_pdf": str(core.CROSS_EVENT_PDF),
    }
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
