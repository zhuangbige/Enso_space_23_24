"""Align one independent atmospheric seed to a common 2023-03-01 date.

The source seed may come from any calendar month.  Its internal model date is
first relabelled to 2022-12-01, then the atmosphere is integrated for three
months under the same climatological SST and sea ice used by every member.
The final restart is therefore a genuine 2023-03-01 state, not a seasonal
state whose filename alone was changed.
"""

from __future__ import annotations

import argparse
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

import f90nml

from isca import DiagTable, Experiment, GFDL_BASE, IscaCodeBase


TARGET_START = (2022, 12, 1, 0, 0, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--member", type=int, required=True)
    parser.add_argument("--source-restart", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--mpirun-opts", default="--bind-to none")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.member < 1:
        parser.error("--member must be positive")
    if args.months != 3:
        parser.error("the common December-to-March alignment requires 3 months")
    if not args.source_restart.is_file():
        parser.error(f"source restart does not exist: {args.source_restart}")
    return args


def relabel_restart(source: Path, destination: Path) -> tuple[int, ...]:
    """Write a safe copy whose atmos_model.res date is 2022-12-01."""
    with tempfile.TemporaryDirectory(prefix="isca_relabel_") as temporary:
        root = Path(temporary)
        with tarfile.open(source, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                clean = Path(member.name)
                if clean.is_absolute() or ".." in clean.parts:
                    raise ValueError(f"unsafe restart member: {member.name}")
            archive.extractall(root)

        model_file = root / "atmos_model.res"
        if not model_file.is_file():
            raise ValueError(f"{source} has no atmos_model.res")
        lines = model_file.read_text(encoding="ascii").splitlines(keepends=True)
        if not lines:
            raise ValueError(f"{source} has an empty atmos_model.res")
        numbers = tuple(int(value) for value in re.findall(r"\d+", lines[0])[:6])
        if len(numbers) != 6:
            raise ValueError(f"cannot parse model date from: {lines[0]!r}")
        suffix_match = re.search(r"\s+Current model time:.*$", lines[0])
        suffix = suffix_match.group(0) if suffix_match else "\n"
        lines[0] = "".join(f"{value:12d}" for value in TARGET_START) + suffix
        if not lines[0].endswith("\n"):
            lines[0] += "\n"
        model_file.write_text("".join(lines), encoding="ascii")

        destination.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(destination, "w:gz", compresslevel=6) as archive:
            for path in sorted(root.iterdir()):
                archive.add(path, arcname=f"./{path.name}", recursive=False)
    return numbers


def build_diagnostics() -> DiagTable:
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
    return diagnostics


def main() -> None:
    args = parse_args()
    case_dir = Path(GFDL_BASE) / "exp" / "test_cases" / "realistic_continents"
    runtime = Path(GFDL_BASE).parent
    relabelled = runtime / "work" / "aligned_seed_restarts" / f"seed{args.member:04d}.tar.gz"
    old_date = relabel_restart(args.source_restart, relabelled)

    name = f"isca_control_march_pool_m{args.member:02d}_t42"
    codebase = IscaCodeBase.from_directory(GFDL_BASE)
    experiment = Experiment(name, codebase=codebase)
    experiment.inputfiles = [
        str(Path(GFDL_BASE) / "input" / "land_masks" / "era_land_t42.nc"),
        str(Path(GFDL_BASE) / "input" / "rrtm_input_files" / "ozone_1990.nc"),
        str(case_dir / "input" / "sst_clim_amip.nc"),
        str(case_dir / "input" / "siconc_clim_amip.nc"),
    ]
    experiment.diag_table = build_diagnostics()
    experiment.namelist = f90nml.read(case_dir / "namelist_basefile.nml")
    experiment.update_namelist(
        {
            "main_nml": {"days": 30, "current_date": list(TARGET_START)},
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
            restart_file=str(relabelled) if run_number == 1 else None,
            use_restart=True,
            num_cores=args.cores,
            overwrite_data=args.overwrite,
            mpirun_opts=args.mpirun_opts,
        )
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(experiment.get_restart_file(args.months), args.destination)
    print(
        f"MARCH_ALIGNED_RESTART_COMPLETE member={args.member} "
        f"source_date={old_date} target_date=(2023, 3, 1, 0, 0, 0) "
        f"destination={args.destination}"
    )


if __name__ == "__main__":
    main()
