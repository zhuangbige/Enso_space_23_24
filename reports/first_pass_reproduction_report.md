# First-Pass Reproduction Report

## What Has Been Reproduced From Article Data

- The Zenodo figure data and plotting scripts were downloaded and patched only in a local interim copy.
- Main Figures 1-4 were reproduced as PNG/PDF outputs.
- The source figure data were converted into four analysis tables for coupling, equatorial evolution, AGCM attribution, and wind-stress experiments.

## Fig. 1: Coupling Weakness

| Year | Nino-3 | u10 | SOI | u10 ratio | SOI ratio |
|---|---:|---:|---:|---:|---:|
| 1982 | 1.657 | 2.733 | -2.127 | 1.353 | 1.769 |
| 1997 | 2.490 | 2.774 | -1.510 | 0.906 | 0.829 |
| 2015 | 2.201 | 2.501 | -1.361 | 0.926 | 0.847 |
| 2023 | 1.929 | 0.640 | -0.433 | 0.271 | 0.308 |

For 2023/24, the u10 coupling ratio is 0.271 and the SOI coupling ratio is 0.308. This reproduces the paper's core claim that the atmospheric response was only about one third of the historical SST-expected response.

## Fig. 3: AGCM Attribution Signal

| Experiment | Central Pacific Jun-Dec taux |
|---|---:|
| aCTRL | 0.0211 |
| aPac | 0.0333 |
| aIndAtl | -0.0099 |
| aTrend | -0.0119 |

The Pacific-only response (`aPac`) gives a stronger positive central Pacific wind-stress anomaly, while `aIndAtl` and `aTrend` are negative in the same region.

## Fig. 4: Wind-Stress Experiment Signal

| 2023 Experiment | December Nino-3 |
|---|---:|
| CTRL | 2.344 |
| InitApr | 1.663 |
| Wind2023 | 0.681 |

The December `InitApr` value remains large relative to `CTRL`, which is consistent with the paper's interpretation that ocean preconditioning retains much of the warming after low-frequency post-April wind-stress anomalies are removed.

## Boundary Of This Step

These results reproduce and tabulate the article-provided figure data. They do not yet independently verify the results from raw OISST, ERA5, GPCP, or GODAS downloads.

## Next Independent-Data Step

1. Download monthly OISSTv2, GPCP, GODAS, and ERA5 fields for 1982-2024.
2. Rebuild Nino-3, CWP u10, SOI-like SLP, rainfall, and equatorial wind-stress indices from raw products.
3. Compare raw-product diagnostics against the article-data tables generated here.
