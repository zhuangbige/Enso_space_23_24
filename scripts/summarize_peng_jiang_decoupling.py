#!/usr/bin/env python3
"""Summarize decoupling evidence for 13 warm events.

The screen keeps two literature-derived diagnostics separate:

1. Peng-style June--January Niño-3-conditioned CWP u10 and SOI response.
2. Jiang-style May--July residual-FEP -> northeasterly intrusion -> weak
   central-Pacific zonal-wind response.

Neither paper defines a universal binary threshold for all El Niño events.
The thresholds below are therefore conservative project screening rules, not
claims that the authors proposed a new formal event classification.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVENT_YEARS = (1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, 2023)

PENG_TABLE = ROOT / "data/derived/peng2025_repro/tables/fig1_event_coupling.csv"
JIANG_TABLE = ROOT / "data/derived/research_2026/enso_ne_wind_bridge_event_indices.csv"
SEASONAL_TABLE = ROOT / "data/derived/research_2026/enso_full_year_coupling_event_seasonal.csv"
MONTHLY_TABLE = ROOT / "data/derived/research_2026/enso_type_coupling_monthly_1982_2023.csv"
OUTPUT = ROOT / "data/derived/research_2026/peng_jiang_decoupling_event_summary.csv"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    peng = pd.read_csv(PENG_TABLE).set_index("year").reindex(EVENT_YEARS)
    jiang = pd.read_csv(JIANG_TABLE).set_index("year").reindex(EVENT_YEARS)
    seasonal = pd.read_csv(SEASONAL_TABLE)
    djf = (
        seasonal.loc[seasonal["season"].eq("DJF")]
        .set_index("year")
        .reindex(EVENT_YEARS)
    )
    for label, frame in (("Peng", peng), ("Jiang", jiang), ("DJF", djf)):
        if frame.isna().all(axis=1).any():
            missing = frame.index[frame.isna().all(axis=1)].tolist()
            raise ValueError(f"{label} table is missing event years: {missing}")
    return peng, jiang, djf


def final_label(row: pd.Series) -> str:
    if row["peng_clear_two_branch"] and row["jiang_chain_screen"]:
        return "clear_peng_jiang_decoupling"
    if row["djf_cross_product_weak"]:
        return "mature_season_candidate"
    if row["peng_single_branch_weak"]:
        return "single_branch_candidate"
    if row["mjj_composite_low"]:
        return "development_season_mismatch_only"
    if not row["peng_amplitude_comparable"]:
        return "weak_predictor_not_robust"
    return "no_clear_decoupling"


def build_summary() -> pd.DataFrame:
    peng, jiang, djf = load_inputs()
    monthly = pd.read_csv(MONTHLY_TABLE)
    output = pd.DataFrame({"year": EVENT_YEARS}).set_index("year")

    output["peng_nino3_jun_jan_c"] = peng["nino3"]
    output["peng_cwp_u10_ratio"] = peng["uwind_coupling_ratio"]
    output["peng_soi_ratio"] = peng["soi_coupling_ratio"]
    output["peng_cwp_u10_residual_ms"] = peng["uwind_residual"]
    output["peng_soi_residual"] = peng["soi_residual"]

    output["jiang_fep_residual_mjj_z"] = jiang["fep_residual_mjj_z"]
    output["jiang_ne850_mjj_z"] = jiang["ne850_mjj_z"]
    output["jiang_tau_response_mjj_z"] = jiang["tau_response_mjj_z"]
    output["mjj_composite_coupling_z"] = jiang["coupling_mjj_z"]

    # Broad sequence diagnostic, deliberately kept separate from Jiang's
    # stricter FEP-dominant event definition.  Require at least two consecutive
    # FMA months with positive total and residual FEP anomalies while Niño-3.4
    # has not yet exceeded +0.2 C.
    first_months: dict[int, int | None] = {}
    sustained: dict[int, bool] = {}
    for year in EVENT_YEARS:
        event = monthly.loc[
            monthly["year"].eq(year) & monthly["month"].isin((2, 3, 4))
        ].sort_values("month")
        condition = (
            event["fep_anom_c"].gt(0.0)
            & event["fep_residual_c"].gt(0.0)
            & event["nino34_anom_c"].le(0.2)
        )
        months = event["month"].to_numpy(dtype=int)
        flags = condition.to_numpy(dtype=bool)
        starts = [
            int(months[index])
            for index in range(len(flags) - 1)
            if flags[index]
            and flags[index + 1]
            and months[index + 1] == months[index] + 1
        ]
        sustained[year] = bool(starts)
        first_months[year] = starts[0] if starts else None
    output["broad_sustained_fep_first_fma"] = pd.Series(sustained)
    output["broad_fep_first_onset_month"] = pd.Series(first_months, dtype="Int64")

    output["djf_era5_gpcp_pattern_residual_z"] = djf[
        "coupling_pattern_residual_z"
    ]
    output["djf_ncep_pattern_residual_z"] = djf[
        "ncep_coupling_pattern_residual_z"
    ]
    output["djf_gpcp_precip_pattern_residual_z"] = djf[
        "precip_pattern_residual_z"
    ]
    output["djf_ncep_u_pattern_residual_z"] = djf[
        "ncep_u_pattern_residual_z"
    ]

    # Peng-style ratios become unstable when the Niño-3-predicted response is
    # close to zero. Restrict the binary screen to a clearly positive Niño-3
    # development signal.
    output["peng_amplitude_comparable"] = output["peng_nino3_jun_jan_c"] >= 0.5
    u_weak = output["peng_cwp_u10_ratio"] <= 0.5
    soi_weak = output["peng_soi_ratio"] <= 0.5
    output["peng_clear_two_branch"] = (
        output["peng_amplitude_comparable"] & u_weak & soi_weak
    )
    output["peng_single_branch_weak"] = (
        output["peng_amplitude_comparable"] & (u_weak ^ soi_weak)
    )

    # Operational Jiang-style chain screen. The residual-FEP and NE850 signs
    # follow Jiang et al.; the +/-1 and -0.75 SD cutoffs are project screening
    # thresholds used only to keep the event summary conservative.
    output["jiang_chain_screen"] = (
        (output["jiang_fep_residual_mjj_z"] >= 1.0)
        & (output["jiang_ne850_mjj_z"] >= 1.0)
        & (output["jiang_tau_response_mjj_z"] <= -0.75)
    )

    # Independent mature-season support must appear in both the ERA5/GPCP and
    # NCEP wind-pressure products after conditioning on SST amplitude and
    # spatial pattern.
    output["djf_cross_product_weak"] = (
        (output["djf_era5_gpcp_pattern_residual_z"] <= -0.75)
        & (output["djf_ncep_pattern_residual_z"] <= -0.75)
    )
    output["mjj_composite_low"] = output["mjj_composite_coupling_z"] <= -0.75
    output["final_screen"] = output.apply(final_label, axis=1)
    return output.reset_index()


def main() -> int:
    output = build_summary()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False)
    print(OUTPUT)
    print(
        output[
            [
                "year",
                "peng_cwp_u10_ratio",
                "peng_soi_ratio",
                "jiang_fep_residual_mjj_z",
                "jiang_ne850_mjj_z",
                "jiang_tau_response_mjj_z",
                "broad_sustained_fep_first_fma",
                "broad_fep_first_onset_month",
                "djf_era5_gpcp_pattern_residual_z",
                "djf_ncep_pattern_residual_z",
                "final_screen",
            ]
        ].to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
