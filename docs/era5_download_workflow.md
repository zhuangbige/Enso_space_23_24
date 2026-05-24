# ERA5 Download Workflow

This project uses ERA5 as the paper-grade replacement for the current NCEP/NCAR
fallback atmospheric diagnostics.

## Why ERA5

ERA5 monthly means from Copernicus CDS provide the final wind and pressure fields
needed for the 2023/24 El Nino decoupling chain:

- `10m_u_component_of_wind`: near-surface zonal wind, replacing the NCEP sig995
  fallback for u10-like diagnostics.
- `mean_sea_level_pressure`: sea-level pressure, replacing the NCEP SOI-like
  pressure proxy.
- `u_component_of_wind` at 850 hPa: low-level tropical wind response.
- `divergence` at 200 hPa and `vertical_velocity` at 500 hPa: first Walker
  circulation proxies. If a full velocity-potential diagnostic is needed later,
  it should be derived from divergent wind/divergence or obtained from a product
  that already provides velocity potential.

Official CDS pages:

- ERA5 monthly averaged data on single levels:
  https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means
- ERA5 monthly averaged data on pressure levels:
  https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels-monthly-means

## One-Time Setup

1. Create or log into a Copernicus CDS account.
2. Accept the licence terms on both ERA5 dataset pages above.
3. Create `~/.cdsapirc` from the CDS API key shown in your account page.
4. Confirm `cdsapi` is installed:

```bash
python3 - <<'PY'
import cdsapi
print("cdsapi ready")
PY
```

## Download

The current request is intentionally tropical and monthly to keep volume
manageable:

```bash
python3 scripts/fetch_era5_monthly_cds.py --request single_levels
python3 scripts/fetch_era5_monthly_cds.py --request pressure_levels
```

Outputs:

```text
data/raw/era5/era5_monthly_single_levels_tropics_1982_2024.nc
data/raw/era5/era5_monthly_pressure_levels_tropics_1982_2024.nc
```

## Build Diagnostics

After both files exist:

```bash
python3 scripts/build_era5_seasonal_summary.py
python3 scripts/build_data_chain_inventory.py
```

Primary output:

```text
data/derived/research/era5_seasonal_summary.csv
```

This table is designed to be compared directly with:

```text
data/derived/research/seasonal_decoupling_first_pass.csv
data/derived/research/seasonal_asynchrony_matrix.csv
data/derived/research/stage_a_spatial_summary.csv
```

## Interpretation Rule

ERA5 should replace NCEP/NCAR fallback in final figures, but the historical
comparison logic remains unchanged: compare 2023/24 with 1982/83, 1997/98, and
2015/16 by season. Keep NCEP results as a robustness/fallback appendix if ERA5
and NCEP agree on the sign and seasonality of the weak response.
