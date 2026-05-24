# Data Catalog

Detailed source URLs, access endpoints, and literature citations are logged in:

```text
docs/data_source_log.md
```

Generate the current table with:

```bash
python3 scripts/list_data_sources.py --format markdown
```

## Core Datasets

| Dataset | Role |
|---|---|
| ERA5 | Atmospheric wind, SLP, rainfall, velocity potential, and Walker diagnostics. |
| NOAA OISST v2.1 | Primary SST product for Nino indices and seasonal anomalies. |
| ERSSTv5 | Long-record SST robustness and historical event comparison. |
| GPCP | Independent precipitation check. |
| NOAA OLR | Convection proxy for tropical Pacific and Maritime Continent response. |
| ORAS5 | Auxiliary ocean precondition check for OHC/D20. |
| TAO/TRITON | Equatorial Pacific station validation for winds and subsurface structure. |

## Source-Paper Datasets

These are the products explicitly listed by Peng et al. 2025 or required by its
reproduction archive:

| Dataset | Role |
|---|---|
| Peng 2025 Zenodo archive | Processed figure data and Python plotting scripts. |
| OISSTv2 | Source-paper SST product. |
| ERA5 | Source-paper atmospheric reanalysis and daily wind-stress forcing source. |
| GPCP | Source-paper precipitation product. |
| GODAS | Source-paper ocean reanalysis for temperature and heat-budget diagnostics. |
| CESM-LENS2 | Source-paper large-ensemble warming-context product. |

## Expansion Datasets

| Dataset | Role |
|---|---|
| GLORYS12V1 | High-resolution ocean diagnostics if propagation pathways become central. |
| Argo | Independent profile constraint on OHC and stratification. |
| DUACS | SLA/SSH diagnostics linking sea level to ocean memory. |

## Download Principle

Start with monthly fields and regional subsets. Retrieve daily or hourly products
only after the monthly diagnostics identify a mechanism that requires higher
frequency evidence.
