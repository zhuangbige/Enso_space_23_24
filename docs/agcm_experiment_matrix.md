# AGCM Experiment Matrix

Generate the current matrix with:

```bash
python3 scripts/make_agcm_matrix.py --include-optional --format markdown
```

## Required Experiments

- `global_observed_sst`: baseline observed global SST forcing.
- `pacific_only`: canonical Pacific SST response with other basins held near climatology.
- `atlantic_only`: Atlantic contribution to weak coupling and easterly anomalies.
- `indian_ocean_only`: Indian Ocean and monsoon/Maritime Continent pathway.
- `atlantic_plus_indian`: combined extra-Pacific damping.
- `detrended_global_sst`: event-pattern response without long-term SST trend.
- `trend_retained_global_sst`: pan-tropical warmth and trend-retained reference.

## Optional Experiments

- `tna_only`: focused tropical North Atlantic test for summer 2023.
- `ism_mc_heating`: idealized Indian summer monsoon/Maritime Continent heating test.

## Default Run Window

Use 2022-2024 event-window ensembles first. A longer 1982-2024 low-member run is
useful later for historical composites and regression-based response estimates.
