# SODA3 upper-ocean heat-content analysis: first results

## Data and definitions

- SODA3.15.2 potential temperature, 1980–2024.
- OHC is vertically integrated with constant ρ = 1025 kg m⁻³ and cp = 3990 J kg⁻¹ K⁻¹.
- Event figures use 1980–2024 calendar-month anomalies with the same-calendar-month linear trend removed.
- Prediction target: NDJ (November–January) Niño-3.4 SST.
- Validation: walk-forward tests for 2000–2023; only earlier years are used in each fold.

## 2023 heat redistribution

- January: west = +1.44, central = +0.15, east = -0.25 GJ m⁻².
- June: west = +0.31, central = +0.48, east = +0.98 GJ m⁻².
- December: west = -1.70, central = +0.60, east = +1.59 GJ m⁻².
- This is a west-to-east redistribution signal, not uniform basin-wide warming: the western reservoir is depleted while eastern OHC increases.

## Exploratory prediction result

- Best OHC model averaged across January–June: **OHC300 basin + east-west**, mean RMSE skill versus Niño-3.4 persistence = +0.150.
- Largest single-month OHC skill: **OHC300 central** in month 4, skill = +0.287 (95% bootstrap interval +0.133 to +0.421).
- June model ranking by RMSE:

  - OHC300 basin + east-west: RMSE 0.623 °C, r = 0.868, skill vs persistence = +0.171.
  - OHC100 basin: RMSE 0.672 °C, r = 0.842, skill vs persistence = +0.107.
  - Persistence (Niño-3.4): RMSE 0.752 °C, r = 0.805, skill vs persistence = +0.000.
  - OHC300 central: RMSE 0.769 °C, r = 0.778, skill vs persistence = -0.023.
  - OHC300 east: RMSE 0.807 °C, r = 0.778, skill vs persistence = -0.074.

## Interpretation boundary

- These are retrospective exploratory tests with only 24 independent verification years per initialization month.
- Positive skill is useful evidence only when it is stable across months and the bootstrap interval is not dominated by zero.
- The next test should add D20, zonal wind and OLR one at a time, then ask whether OHC contributes incremental skill beyond each baseline.

## Event hindcast table

The machine-readable event predictions for 1997/98, 2015/16 and 2023/24 are stored beside this note.
