# Stage A AMJ/JJA Spatial Diagnostics Design

Access date: 2026-05-23.

## Goal

Build a NOAA fast-pass spatial evidence layer for the developing-season asynchrony hypothesis:

**In AMJ/JJA 2023, tropical Pacific SST was already strong, but wind/pressure and convection did not organize like comparable strong El Nino events.**

This stage should strengthen the current index/matrix results with spatial fields. It does not replace the later ERA5/OLR manuscript-grade analysis.

## Scope

### Included

- AMJ and JJA only.
- Historical comparison against comparable strong El Nino events: 1982/83, 1997/98, 2015/16.
- NOAA quick datasets already in the project data plan:
  - OISST v2.1 for SST spatial anomalies.
  - GPCP for precipitation spatial anomalies.
  - NCEP/NCAR Reanalysis 1 fallback for low-level wind and SLP spatial proxies if grid extraction is feasible.
- Outputs should include both:
  - gridded seasonal anomaly/difference files for reproducibility;
  - compact spatial diagnostics/report text explaining what the fields show.

### Excluded

- ERA5 u850/SLP/velocity potential.
- CPC Blended OLR.
- MJO/RMM or daily decomposition.
- Final manuscript-grade figure styling.
- AGCM experiments.

## Analysis Design

### Spatial Products

For each variable, compute:

1. 2023 AMJ and JJA seasonal anomaly.
2. Comparable-event AMJ and JJA seasonal anomaly mean from 1982, 1997, and 2015 event years.
3. Difference: 2023 minus comparable.

Minimum required fields:

- `sst_oisst`: tropical Indo-Pacific/Atlantic view if remote request size allows; otherwise Pacific-first plus external-basin boxes.
- `precip_gpcp`: tropical Pacific precipitation field.

Fallback fields, if OPeNDAP extraction is feasible:

- `uwnd_ncep_sig995`: near-surface zonal wind proxy.
- `slp_ncep`: sea-level pressure proxy.

If NCEP grid extraction is too slow or unstable, keep wind/SLP as index evidence for this stage and explicitly defer spatial wind/SLP to ERA5.

### Region Boxes

All spatial diagnostics should mark the same boxes used in the matrix:

- Nino-3: 5S-5N, 150W-90W.
- Central Pacific precipitation: 5S-5N, 180-140W.
- Eastern Pacific precipitation: 5S-5N, 140W-100W.
- CWP wind: 5S-5N, 160E-140W.
- Tropical North Atlantic: 0-20N, 60W-20W.
- Tropical Indian Ocean: 20S-20N, 40E-110E.
- Maritime Continent: 10S-10N, 95E-150E.
- Western Pacific warm pool: 10S-10N, 120E-160E.

## File Outputs

Use new files so existing reproduction outputs remain untouched:

- `data/interim/raw_validation/oisst_spatial_amj_jja.nc` or `.npz`
- `data/interim/raw_validation/gpcp_spatial_amj_jja.nc` or `.npz`
- `data/interim/raw_validation/ncep_spatial_amj_jja.nc` or `.npz` if feasible
- `data/derived/research/stage_a_spatial_summary.csv`
- `reports/stage_a_amj_jja_spatial_diagnostics.md`

Figure outputs may be created after the data layer is stable:

- `data/derived/research/stage_a_amj_jja_sst_precip.png`
- optional `data/derived/research/stage_a_amj_jja_wind_slp.png`

## Interpretation Rules

- Always compare 2023 against the historical comparable-event mean.
- Use `2023 minus comparable` for spatial fields, not ratios.
- Use the existing matrix ratios only as side text or summary values.
- Treat NCEP as a fallback product and label it as such.
- Do not claim a Walker-circulation result until ERA5 pressure-level or velocity-potential diagnostics are available.

## Success Criteria

Stage A is successful if it can answer these questions:

1. Does the AMJ/JJA SST spatial pattern show strong Pacific warming relative to comparable strong events?
2. Does GPCP show weaker central/eastern Pacific precipitation response in the same seasons?
3. Are external-basin warm anomalies spatially visible in AMJ/JJA?
4. Can NCEP fallback wind/SLP spatial fields be extracted well enough to use as provisional context?
5. Does the report clearly separate quick-look evidence from later ERA5/OLR manuscript-grade work?

## Validation

- Reuse existing unit-tested seasonal logic where possible.
- Add tests for event-year seasonal compositing over gridded records, including DJF-capable cross-year behavior if the helper is generalized.
- Check that generated summary CSV reproduces known index-level values within tolerance:
  - AMJ/JJA Nino-3 SST ratios/differences from `seasonal_asynchrony_matrix.csv`.
  - AMJ/JJA central/eastern Pacific GPCP values from `gpcp_precip_seasonal_summary.csv`.
- Run `python -m unittest discover -s tests`.

## Risks And Fallbacks

- NOAA OPeNDAP may be slow. Use small region/time chunks and cache intermediate files.
- Local Anaconda `netCDF4` requires `DYLD_LIBRARY_PATH=/opt/anaconda3/pkgs/libjpeg-turbo-2.0.0-h1a28f6b_0/lib`; log this caveat.
- If NCEP grid extraction fails, Stage A still proceeds with SST + GPCP spatial evidence and NCEP index evidence.
