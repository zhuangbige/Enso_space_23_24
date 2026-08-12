# Three-Box Wind–Heat-Fate Diagnostic Design

Date: 2026-08-12

## 1. Scientific objective

The diagnostic will determine which component of tropical-Pacific warm-heat loss is most closely associated with wind anomalies, and whether that relationship differs among the western, central, and eastern equatorial Pacific boxes. The analysis is designed to distinguish total heat arrival from the spatial and temporal routing of that heat after arrival.

The primary comparison is between the 2015/16 and 2023/24 events, embedded in the same 13-event sample used by the current three-question analysis. The analysis will not treat a high bivariate correlation as proof of one-way causation.

## 2. Fixed control volumes

All boxes span 10°S–5°N and 0–300 m. The longitudinal boundaries are fixed before looking at correlations:

| Box | Longitude range | Role |
|---|---|---|
| West | 160°E–180° | western reservoir and inflow gateway |
| Central | 180°–140°W | central-Pacific coupling and convection corridor |
| East | 140°W–80°W | eastern arrival and terminal-storage region |

The boxes are non-overlapping and share internal faces, allowing a mass-balanced enthalpy budget. Standard Niño boxes may be overlaid as SST or atmospheric-response indices, but will not replace the closed control volumes because they overlap.

## 3. Heat-fate terms and sign convention

For every event, phase, and box, each corrected boundary enthalpy flux is retained separately. Raw face fluxes are positive into the box. The public heat-loss variables will be transformed so positive values always denote loss from the selected box:

\[
L_{W}=-F_{W,in},\quad
L_{E}=-F_{E,in},\quad
L_{S}=-F_{S,in},\quad
L_{N}=-F_{N,in},\quad
L_{surface}=-Q_{surface}.
\]

The storage loss is

\[
L_{storage}=-\Delta H'_{0-300m}.
\]

The reported terms are therefore:

1. westward-face loss;
2. eastward-face loss;
3. southward loss across 10°S;
4. northward loss across 5°N;
5. net surface heat loss;
6. storage loss.

The budget residual remains a separate audit term. It will not be labeled as a physical loss mechanism because it combines vertical exchange, mixing, diffusion, assimilation increments, and discretization error.

Uncorrected shared-face transports must cancel between adjacent boxes to numerical precision. The established budget applies a separate uniform mass correction to each box, so corrected internal-face partitions are not assumed to cancel exactly. Their mismatch will be reported, and cross-box transfer comparisons will additionally use the single common-gate transport diagnostic at 180° and 140°W.

## 4. Event phases

Three fixed phases will be calculated:

| Phase | Window | Interpretation |
|---|---|---|
| Arrival | January–June of year 0 | input and early storage establishment |
| Redistribution | July–December of year 0 | post-arrival zonal and meridional routing |
| Decay | January–May of year +1 | mature-to-decay heat release and export |

The primary wind predictors are calculated both contemporaneously and in the preceding MAM or MJJ development window. This permits a restricted lead–lag test without scanning every possible lag.

## 5. Wind predictors and pre-specified physical pairings

The primary atmospheric data are ERA5 10 m wind and eastward/northward turbulent surface stress. Existing Jiang-region northeasterly-wind indices and the central-western-Pacific westerly index are used as additional physically motivated predictors.

| Heat-fate response | Primary wind predictors |
|---|---|
| west/east face loss | equatorial box-mean zonal stress; central-western-Pacific westerly stress or u10 |
| 5°N northward loss | 5°N zonal stress; northern-flank stress curl; Jiang-region northeasterly anomaly |
| 10°S southward loss | 10°S zonal stress; southern-flank stress curl |
| surface heat loss | local wind-speed or stress-magnitude anomaly; local zonal stress |
| storage loss | the matched wind predictors plus arrival-phase box storage as a control |

The primary analysis uses these pre-specified pairs. A complete wind-by-loss matrix is retained as a discovery appendix, not as the basis for selecting a preferred mechanism.

## 6. Statistical analysis

The event sample contains the 13 established events: 1982, 1986, 1991, 1994, 1997, 2002, 2004, 2006, 2009, 2015, 2018, 2019, and 2023.

For each pre-specified pair the output will contain:

1. Pearson correlation and linear slope;
2. Spearman rank correlation;
3. partial relationship after controlling for arrival-phase box OHC or boundary input, using only one control variable;
4. leave-one-event sign stability, used internally to identify relationships driven entirely by one event;
5. the positions of 1997, 2015, and 2023 in the event distribution.

Because the sample is small, the interpretation will emphasize sign, magnitude, physical consistency, and event leverage rather than a binary significance label. A relationship will be promoted to the main result only when Pearson and Spearman signs agree, the sign is physically interpretable, and it is not created solely by deleting or retaining one highlighted event.

The audited SODA3 budget retains its established 1980–2022 same-calendar-month linear baseline. ERA5 wind indices retain their validated 1982–2014 baseline. A common-baseline recalculation may be used as an internal sign check, but will not replace the audited heat-budget values in the main tables.

## 7. Outputs

The calculation will produce:

1. an event-by-phase-by-box heat-fate table in ZJ;
2. an event-by-window wind-index table in physical units;
3. a pre-specified wind–loss relationship table;
4. a complete discovery matrix for audit;
5. a three-box geographic locator and 2015/2023 phase comparison figure;
6. a compact wind–loss relationship matrix;
7. scatter panels for the strongest physically defensible relationships;
8. a concise Chinese interpretation report.

No PowerPoint file will be modified in this stage.

## 8. Validation and interpretation boundaries

The implementation must verify:

- complete months in every phase;
- consistent longitude, latitude, units, and flux signs;
- numerical closure of each box budget;
- cancellation of uncorrected shared internal faces and explicit reporting of the corrected-face mismatch;
- reproduction of the audited 2015 and 2023 January–June storage changes: central +2.63/+0.87 ZJ and east +8.60/+11.12 ZJ, within checkpoint precision;
- no missing wind or heat-fate values for the 13 events;
- deterministic figures and tables.

The conclusions may state that a wind anomaly is associated with or dynamically consistent with a particular heat-loss pathway. They may not state that the wind anomaly uniquely caused that loss without an independent forcing or counterfactual experiment.
