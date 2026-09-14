# OHC + D20 + wind + OLR prediction analysis

## Experiment

- Walk-forward verification: 2000–2023.
- Target: November–January Niño-3.4 SST residual.
- OHC: SODA3.15.2 0–300 m, central Pacific 5°S–5°N, 180°–140°W.
- D20: ORAS5 equatorial central-Pacific mean and east-minus-west thermocline slope.
- Wind: ERA5 850-hPa zonal wind and ORAS5 zonal surface stress, 160°E–140°W.
- OLR: ERA5 outgoing longwave radiation, 5°S–5°N, 180°–140°W; positive OLR means weaker deep convection.
- Prediction preprocessing uses training-fold trends and scaling, not the fixed event-figure climatology.

## Main results

- Best individual predictor family on the January–June mean: **OHC300 central**, mean skill versus persistence = +0.093.
- Strongest individual month: **OHC300 central**, month 4, skill = +0.287, 95% interval +0.120 to +0.425.
- Best average addition after OHC: **OHC + OLR**, mean incremental skill = +0.058.
- Strongest single-month addition after OHC: **OHC + OLR**, month 6, incremental skill = +0.198, 95% interval +0.081 to +0.352.
- May OHC + u850: skill versus persistence = +0.289; incremental skill versus OHC = +0.095 (95% interval +0.022 to +0.192).
- June OHC + OLR: skill versus persistence = +0.180; incremental skill versus OHC = +0.198 (95% interval +0.081 to +0.352).
- OHC + D20 mean incremental skill is only +0.004, indicating substantial overlap between the two subsurface-ocean measures.

## Interpretation rule

- A variable is considered a promising addition only when its skill is positive across neighboring initialization months and its bootstrap interval is not dominated by zero.
- These tests diagnose prediction information, not causal direction. D20, OHC, wind, and OLR are dynamically coupled and therefore not statistically independent.
- For 2023, positive OHC/D20 signals coexisted with weak or easterly central-western Pacific wind anomalies and a much weaker convective response than in 1997 or 2015.  This supports an ocean-ready but atmospherically under-coupled interpretation.
