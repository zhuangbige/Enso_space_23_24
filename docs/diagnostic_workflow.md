# Diagnostic Workflow

## Step 1: Baseline Indices

- Build monthly Nino-3 and Nino-3.4 indices from OISST.
- Rebuild the same indices from ERSSTv5 for robustness.
- Build equatorial Pacific u850 and SLP/SOI-like indices from ERA5.

## Step 2: Coupling Residuals

- Fit historical Nino-to-u850 and Nino-to-SOI regressions.
- Compute expected wind and pressure response for 2023/24 SST anomalies.
- Define coupling ratio as observed atmospheric response divided by expected
  response. Values near one imply canonical coupling; values well below one imply
  weak coupling.

## Step 3: Seasonal Maps

Prepare AMJ, JJA, SON, and DJF anomaly maps for:

- SST
- ERA5 u850
- ERA5 SLP
- ERA5 precipitation
- NOAA OLR
- 200 hPa velocity potential, if available in the ERA5 pressure-level pull

## Step 4: Event Comparison

Compare at least:

- 1982/83
- 1997/98
- 2015/16
- 2023/24

The first figure set should include time series, residual plots, seasonal maps, and
a coupling-strength scatter plot.
