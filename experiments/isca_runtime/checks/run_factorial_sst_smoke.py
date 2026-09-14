"""Run one day using a converted 2023 IA×FEP prescribed-SST boundary."""

import os

import f90nml
import xarray as xr

from isca import DiagTable, Experiment, GFDL_BASE, IscaCodeBase


runtime_dir = os.path.dirname(GFDL_BASE)
case_dir = os.path.join(GFDL_BASE, "exp", "test_cases", "realistic_continents")
forcing_stem = "sst_ag_ia0_fep0_isca"
forcing_file = os.path.join(runtime_dir, "forcing_isca", f"{forcing_stem}.nc")

codebase = IscaCodeBase.from_directory(GFDL_BASE)
experiment = Experiment("isca_factorial_sst_smoke_t42", codebase=codebase)
experiment.inputfiles = [
    os.path.join(GFDL_BASE, "input", "land_masks", "era_land_t42.nc"),
    os.path.join(GFDL_BASE, "input", "rrtm_input_files", "ozone_1990.nc"),
    forcing_file,
    os.path.join(case_dir, "input", "siconc_clim_amip.nc"),
]

diagnostics = DiagTable()
diagnostics.add_file("atmos_daily", 1, "days", time_units="days")
diagnostics.add_field("dynamics", "ps", time_avg=True)
diagnostics.add_field("dynamics", "bk")
diagnostics.add_field("dynamics", "pk")
diagnostics.add_field("dynamics", "zsurf")
diagnostics.add_field("atmosphere", "precipitation", time_avg=True)
diagnostics.add_field("atmosphere", "flux_u", time_avg=True)
diagnostics.add_field("atmosphere", "flux_v", time_avg=True)
diagnostics.add_field("atmosphere", "u_10m", time_avg=True)
diagnostics.add_field("atmosphere", "v_10m", time_avg=True)
diagnostics.add_field("mixed_layer", "t_surf", time_avg=True)
diagnostics.add_field("rrtm_radiation", "olr", time_avg=True)
experiment.diag_table = diagnostics

experiment.namelist = f90nml.read(os.path.join(case_dir, "namelist_basefile.nml"))
experiment.update_namelist(
    {
        "main_nml": {"days": 1, "current_date": [2023, 3, 1, 0, 0, 0]},
        "mixed_layer_nml": {
            "do_qflux": False,
            "do_read_sst": True,
            "do_sc_sst": True,
            "sst_file": forcing_stem,
            "specify_sst_over_ocean_only": True,
        },
    }
)
experiment.run(1, num_cores=4, use_restart=False, overwrite_data=True)

output_file = os.path.join(experiment.get_outputdir(1), "atmos_daily.nc")
with xr.open_dataset(output_file) as output:
    required = {
        "ps",
        "precipitation",
        "flux_u",
        "flux_v",
        "u_10m",
        "v_10m",
        "t_surf",
        "olr",
    }
    missing = required.difference(output.data_vars)
    if missing:
        raise RuntimeError(f"Missing requested diagnostics: {sorted(missing)}")
    for variable in required:
        if bool(output[variable].isnull().any()):
            raise RuntimeError(f"NaNs in model output diagnostic {variable}")

print(f"ISCA_FACTORIAL_SST_RUN_OK {output_file}")
