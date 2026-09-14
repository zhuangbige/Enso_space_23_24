"""Run one model day of Isca's dry core at T21 on two MPI ranks."""

from isca import DiagTable, DryCodeBase, Experiment, GFDL_BASE, Namelist


codebase = DryCodeBase.from_directory(GFDL_BASE)
experiment = Experiment("isca_macos_smoke_t21", codebase=codebase)

diagnostics = DiagTable()
diagnostics.add_file("atmos_daily", 1, "days", time_units="days")
diagnostics.add_field("dynamics", "ps", time_avg=True)
diagnostics.add_field("dynamics", "ucomp", time_avg=True)
diagnostics.add_field("dynamics", "vcomp", time_avg=True)
diagnostics.add_field("dynamics", "temp", time_avg=True)
experiment.diag_table = diagnostics

experiment.namelist = Namelist(
    {
        "main_nml": {
            "dt_atmos": 600,
            "days": 1,
            "calendar": "thirty_day",
            "current_date": [2000, 1, 1, 0, 0, 0],
        },
        "atmosphere_nml": {"idealized_moist_model": False},
        "spectral_dynamics_nml": {
            "damping_order": 4,
            "water_correction_limit": 200.0e2,
            "reference_sea_level_press": 1.0e5,
            "valid_range_t": [100.0, 800.0],
            "initial_sphum": 0.0,
            "vert_coord_option": "uneven_sigma",
            "scale_heights": 6.0,
            "exponent": 7.5,
            "surf_res": 0.5,
        },
        "hs_forcing_nml": {
            "t_zero": 315.0,
            "t_strat": 200.0,
            "delh": 60.0,
            "delv": 10.0,
            "eps": 0.0,
            "sigma_b": 0.7,
            "ka": -40.0,
            "ks": -4.0,
            "kf": -1.0,
            "do_conserve_energy": True,
        },
        "diag_manager_nml": {"mix_snapshot_average_fields": False},
        "fms_nml": {"domains_stack_size": 600000},
        "fms_io_nml": {
            "threading_write": "single",
            "fileset_write": "single",
        },
    }
)
experiment.set_resolution("T21", 10)
experiment.run(1, num_cores=2, use_restart=False, overwrite_data=True)
print(f"ISCA_RUN_OK {experiment.get_outputdir(1)}")
