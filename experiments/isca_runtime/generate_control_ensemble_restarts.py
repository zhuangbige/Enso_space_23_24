"""Generate decorrelated atmospheric seed states for the P0 ensemble.

The pool is a continuous control integration with climatological SST.  Its
monthly states are independent seeds, not yet common-date production initial
conditions.  ``run_control_member_to_march.py`` subsequently sends every seed
through the same December--February climatological integration and retains the
resulting genuine 2023-03-01 restarts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import f90nml

from isca import DiagTable, Experiment, GFDL_BASE, IscaCodeBase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--members", type=int, default=10)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--restart", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.members < 1:
        parser.error("--members must be at least 1")
    if not args.restart.is_file():
        parser.error(f"restart file does not exist: {args.restart}")
    return args


def main() -> None:
    args = parse_args()
    case_dir = Path(GFDL_BASE) / "exp" / "test_cases" / "realistic_continents"
    codebase = IscaCodeBase.from_directory(GFDL_BASE)
    experiment = Experiment("isca_control_ensemble_pool_t42", codebase=codebase)
    experiment.inputfiles = [
        str(Path(GFDL_BASE) / "input" / "land_masks" / "era_land_t42.nc"),
        str(Path(GFDL_BASE) / "input" / "rrtm_input_files" / "ozone_1990.nc"),
        str(case_dir / "input" / "sst_clim_amip.nc"),
        str(case_dir / "input" / "siconc_clim_amip.nc"),
    ]

    diagnostics = DiagTable()
    diagnostics.add_file("pool_monthly", 30, "days", time_units="days")
    for module, field in (
        ("dynamics", "ps"),
        ("dynamics", "temp"),
        ("dynamics", "ucomp"),
        ("dynamics", "vcomp"),
        ("atmosphere", "precipitation"),
    ):
        diagnostics.add_field(module, field, time_avg=True)
    experiment.diag_table = diagnostics

    experiment.namelist = f90nml.read(case_dir / "namelist_basefile.nml")
    experiment.update_namelist(
        {
            "main_nml": {"days": 30, "current_date": [2023, 3, 1, 0, 0, 0]},
            "mixed_layer_nml": {
                "do_qflux": False,
                "do_read_sst": True,
                "do_sc_sst": True,
                "sst_file": "sst_clim_amip",
                "specify_sst_over_ocean_only": True,
            },
        }
    )

    for run_number in range(1, args.members + 1):
        external_restart = str(args.restart) if run_number == 1 else None
        experiment.run(
            run_number,
            restart_file=external_restart,
            use_restart=True,
            num_cores=args.cores,
            overwrite_data=args.overwrite,
        )
        print(f"ENSEMBLE_RESTART_READY member={run_number} "
              f"file={experiment.get_restart_file(run_number)}")

    print(f"CONTROL_ENSEMBLE_POOL_COMPLETE members={args.members}")


if __name__ == "__main__":
    main()
