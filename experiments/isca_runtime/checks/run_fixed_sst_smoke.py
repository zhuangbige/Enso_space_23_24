"""Run one day of the realistic-continent, fixed-SST Isca configuration."""

import os

import f90nml

from isca import DiagTable, Experiment, GFDL_BASE, IscaCodeBase


case_dir = os.path.join(GFDL_BASE, "exp", "test_cases", "realistic_continents")
codebase = IscaCodeBase.from_directory(GFDL_BASE)
experiment = Experiment("isca_fixed_sst_smoke_t42", codebase=codebase)
experiment.inputfiles = [
    os.path.join(GFDL_BASE, "input", "land_masks", "era_land_t42.nc"),
    os.path.join(GFDL_BASE, "input", "rrtm_input_files", "ozone_1990.nc"),
    os.path.join(case_dir, "input", "sst_clim_amip.nc"),
    os.path.join(case_dir, "input", "siconc_clim_amip.nc"),
]

diagnostics = DiagTable()
diagnostics.add_file("atmos_daily", 1, "days", time_units="days")
diagnostics.add_field("dynamics", "ps", time_avg=True)
diagnostics.add_field("dynamics", "bk")
diagnostics.add_field("dynamics", "pk")
diagnostics.add_field("dynamics", "zsurf")
diagnostics.add_field("atmosphere", "precipitation", time_avg=True)
diagnostics.add_field("mixed_layer", "t_surf", time_avg=True)
diagnostics.add_field("dynamics", "sphum", time_avg=True)
diagnostics.add_field("dynamics", "ucomp", time_avg=True)
diagnostics.add_field("dynamics", "vcomp", time_avg=True)
diagnostics.add_field("dynamics", "temp", time_avg=True)
experiment.diag_table = diagnostics

experiment.namelist = f90nml.read(os.path.join(case_dir, "namelist_basefile.nml"))
experiment.update_namelist(
    {
        "main_nml": {"days": 1},
        "mixed_layer_nml": {
            "do_qflux": False,
            "do_read_sst": True,
            "do_sc_sst": True,
            "sst_file": "sst_clim_amip",
            "specify_sst_over_ocean_only": True,
        },
    }
)
experiment.run(1, num_cores=4, use_restart=False, overwrite_data=True)
print(f"ISCA_FIXED_SST_RUN_OK {experiment.get_outputdir(1)}")
