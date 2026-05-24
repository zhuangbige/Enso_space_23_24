# Data Acquisition Plan

## Immediate Download Targets

Use these first because they are closest to the source paper and have manageable
volume.

| Priority | Dataset | Variables | Period | Notes |
|---|---|---|---|---|
| 1 | Peng 2025 Zenodo archive | `Fig*.mat`, `Fig*.py`, `Extended_Data_Fig*.mat`, `Supplementary_Fig*.mat` | Figure-specific | Establish paper conventions before processing raw data. |
| 2 | OISSTv2 high-res | SST | 1982-2024 | Nino-3/Nino-3.4, SST anomaly maps, trend split. |
| 3 | GPCP | precipitation | 1982-2024 | Rainfall Hovmoller and weak precipitation response check. |
| 4 | GODAS | ocean temperature, currents if needed | 1982-2024 | Equatorial temperature, 20 C isotherm, mixed-layer budget follow-up. |
| 5 | ERA5 monthly | u10/u850, SLP, precipitation, velocity potential | 1982-2024 | Coupling residuals and Walker diagnostics. |

## Secondary Download Targets

| Dataset | Use | Trigger |
|---|---|---|
| ERA5 daily wind stress | Reproduce wind-stress-prescribed CGCM forcing logic | Only if moving beyond diagnosis into hindcast forcing reconstruction. |
| NOAA OLR | Independent convection proxy | Use when GPCP/ERA5 rainfall disagree. |
| ERSSTv5 | Long-record SST sensitivity | Use after OISST workflow is stable. |
| ORAS5 | Ocean reanalysis robustness | Use after GODAS replication is complete. |
| GLORYS12V1, Argo, DUACS | Ocean pathway extension | Use only if heat-content pathway becomes the main paper. |
| CESM-LENS2 | Future frequency / warming context | Defer until stage two. |

## File Organization

Recommended local layout:

```text
data/
  raw/
    peng2025_zenodo/
    oisst/
    gpcp/
    godas/
    era5/
  interim/
    monthly_indices/
    seasonal_anomalies/
  derived/
    coupling_residuals/
    figures_first_pass/
```

Do not commit downloaded climate data. Commit only scripts, small manifests, and
derived metadata needed to reproduce the acquisition.
