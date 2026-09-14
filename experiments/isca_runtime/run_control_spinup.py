"""Create a common 2023-03-01 atmospheric restart for factorial branching."""

from __future__ import annotations

import argparse
from pathlib import Path

import f90nml

from isca import DiagTable, Experiment, GFDL_BASE, IscaCodeBase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--keep-all-restarts",
        action="store_true",
        help="Keep every monthly restart instead of retaining only the newest one.",
    )
    args = parser.parse_args()
    if args.months < 1:
        parser.error("--months must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    case_dir = Path(GFDL_BASE) / "exp" / "test_cases" / "realistic_continents"
    codebase = IscaCodeBase.from_directory(GFDL_BASE)
    experiment = Experiment("isca_control_spinup_t42", codebase=codebase)
    experiment.inputfiles = [
        str(Path(GFDL_BASE) / "input" / "land_masks" / "era_land_t42.nc"),
        str(Path(GFDL_BASE) / "input" / "rrtm_input_files" / "ozone_1990.nc"),
        str(case_dir / "input" / "sst_clim_amip.nc"),
        str(case_dir / "input" / "siconc_clim_amip.nc"),
    ]

    diagnostics = DiagTable()
    diagnostics.add_file("spinup_monthly", 30, "days", time_units="days")
    for module, field in (
        ("dynamics", "ps"),
        ("dynamics", "temp"),
        ("dynamics", "ucomp"),
        ("dynamics", "vcomp"),
        ("mixed_layer", "t_surf"),
        ("atmosphere", "precipitation"),
    ):
        diagnostics.add_field(module, field, time_avg=True)
    experiment.diag_table = diagnostics

    experiment.namelist = f90nml.read(case_dir / "namelist_basefile.nml")
    experiment.update_namelist(
        {
            "main_nml": {
                "days": 30,
                "current_date": [2021, 3, 1, 0, 0, 0],
            },
            "mixed_layer_nml": {
                "do_qflux": False,
                "do_read_sst": True,
                "do_sc_sst": True,
                "sst_file": "sst_clim_amip",
                "specify_sst_over_ocean_only": True,
            },
        }
    )

    for run_number in range(1, args.months + 1):
        experiment.run(
            run_number,
            use_restart=run_number > 1,
            num_cores=args.cores,
            overwrite_data=args.overwrite,
        )
        if run_number > 1 and not args.keep_all_restarts:
            experiment.delete_restart(run_number - 1)

    final_restart = experiment.get_restart_file(args.months)
    print(f"ISCA_CONTROL_SPINUP_COMPLETE {final_restart}")


if __name__ == "__main__":
    main()
