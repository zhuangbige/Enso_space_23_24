"""Run one member of the 2023 IA×FEP prescribed-SST experiment.

The production design branches every case from the same equilibrated
atmospheric restart. Each model run is one 30-day month; the prescribed SST
boundary contains the March-August 2023 fields and AMIP climatology otherwise.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import f90nml

from isca import DiagTable, Experiment, GFDL_BASE, IscaCodeBase


CASES = (
    "ia0_fep0",
    "ia0_fep1",
    "ia1_fep0",
    "ia1_fep1",
    "iar0_fep0",
    "iar0_fep1",
    "iar1_fep0",
    "iar1_fep1",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--member", type=int, default=1)
    parser.add_argument("--months", type=int, default=6, choices=range(1, 7))
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument(
        "--mpirun-opts",
        default="",
        help="Options passed directly to mpirun (for example '--bind-to none').",
    )
    parser.add_argument(
        "--restart",
        type=Path,
        help="Common atmospheric restart valid at 2023-03-01. Omit only for a technical test.",
    )
    parser.add_argument(
        "--daily-surface",
        action="store_true",
        help="Also retain daily 2-D coupling diagnostics; increases storage.",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.member < 1:
        parser.error("--member must be at least 1")
    if args.restart and not args.restart.is_file():
        parser.error(f"restart file does not exist: {args.restart}")
    return args


def build_diag_table(include_daily: bool) -> DiagTable:
    diagnostics = DiagTable()
    diagnostics.add_file("atmos_monthly", 30, "days", time_units="days")
    if include_daily:
        diagnostics.add_file("surface_daily", 1, "days", time_units="days")

    three_dimensional = ("sphum", "ucomp", "vcomp", "temp")
    for field in ("ps", "slp", "bk", "pk", "zsurf", *three_dimensional):
        diagnostics.add_field(
            "dynamics",
            field,
            time_avg=field not in {"bk", "pk", "zsurf"},
            files=["atmos_monthly"],
        )

    surface_fields = (
        ("atmosphere", "precipitation"),
        ("atmosphere", "flux_u"),
        ("atmosphere", "flux_v"),
        ("atmosphere", "u_10m"),
        ("atmosphere", "v_10m"),
        ("mixed_layer", "t_surf"),
        ("rrtm_radiation", "olr"),
        ("rrtm_radiation", "flux_sw"),
        ("rrtm_radiation", "flux_lw"),
    )
    for module, field in surface_fields:
        diagnostics.add_field(
            module, field, time_avg=True, files=["atmos_monthly"]
        )
        if include_daily:
            diagnostics.add_field(
                module, field, time_avg=True, files=["surface_daily"]
            )
    return diagnostics


def main() -> None:
    args = parse_args()
    runtime = Path(GFDL_BASE).parent
    case_dir = Path(GFDL_BASE) / "exp" / "test_cases" / "realistic_continents"
    forcing_stem = f"sst_ag_{args.case}_isca"
    forcing_file = runtime / "forcing_isca" / f"{forcing_stem}.nc"
    if not forcing_file.is_file():
        raise FileNotFoundError(
            f"{forcing_file} is missing; run prepare_isca_sst_boundaries.py first"
        )

    name = f"isca_2023_{args.case}_m{args.member:02d}_t42"
    codebase = IscaCodeBase.from_directory(GFDL_BASE)
    experiment = Experiment(name, codebase=codebase)
    experiment.inputfiles = [
        str(Path(GFDL_BASE) / "input" / "land_masks" / "era_land_t42.nc"),
        str(Path(GFDL_BASE) / "input" / "rrtm_input_files" / "ozone_1990.nc"),
        str(forcing_file),
        str(case_dir / "input" / "siconc_clim_amip.nc"),
    ]
    experiment.diag_table = build_diag_table(args.daily_surface)
    experiment.namelist = f90nml.read(case_dir / "namelist_basefile.nml")
    experiment.update_namelist(
        {
            "main_nml": {
                "days": 30,
                "current_date": [2023, 3, 1, 0, 0, 0],
            },
            "mixed_layer_nml": {
                "do_qflux": False,
                "do_read_sst": True,
                "do_sc_sst": True,
                "sst_file": forcing_stem,
                "specify_sst_over_ocean_only": True,
            },
        }
    )

    for run_number in range(1, args.months + 1):
        external_restart = (
            str(args.restart) if run_number == 1 and args.restart else None
        )
        experiment.run(
            run_number,
            restart_file=external_restart,
            use_restart=run_number > 1 or external_restart is not None,
            num_cores=args.cores,
            overwrite_data=args.overwrite,
            mpirun_opts=args.mpirun_opts,
        )
    print(f"ISCA_FACTORIAL_COMPLETE {name} months={args.months}")


if __name__ == "__main__":
    main()
