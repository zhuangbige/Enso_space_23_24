# First-Pass Numerical Reproduction

This stage turns the reproduced figures into tabular diagnostics that can be used
for the decoupling attribution work.

## Fig. 1 Event Coupling Table

Generated with:

```bash
.venv/bin/python scripts/extract_fig1_event_table.py
```

Output:

```text
data/derived/peng2025_repro/tables/fig1_event_coupling.csv
```

The table contains 1982-2023 June-January values from the source paper's
`Fig1.mat`: Nino-3 SST anomaly, central-western Pacific u10, SOI, historical
linear-regression expected responses, residuals, and coupling ratios.

Key first-pass result:

| Year | Nino-3 | u10 ratio | SOI ratio |
|---|---:|---:|---:|
| 1982 | 1.657 | 1.353 | 1.769 |
| 1997 | 2.490 | 0.906 | 0.829 |
| 2015 | 2.201 | 0.926 | 0.847 |
| 2023 | 1.929 | 0.271 | 0.308 |

This reproduces the central paper claim that the 2023/24 atmospheric response was
only about one third of the response expected from the historical SST relationship.

## Fig. 2 Equatorial Summary

Generated with:

```bash
.venv/bin/python scripts/extract_fig2_equatorial_summary.py
```

Output:

```text
data/derived/peng2025_repro/tables/fig2_equatorial_summary.csv
```

The table compares 2023/24 against comparable strong El Ninos for:

- zonal wind stress (`taux`)
- precipitation
- OISST SST anomaly
- SLA

It aggregates the source figure's longitude-time panels over four longitude bands
and three event windows. This is a compact bridge from visual reproduction to the
next diagnosis: where SST/SLA were strong while wind stress and precipitation
responses were weak or displaced.

## Fig. 3 AGCM Attribution Summary

Generated with:

```bash
.venv/bin/python scripts/extract_fig3_agcm_summary.py
```

Output:

```text
data/derived/peng2025_repro/tables/fig3_agcm_summary.csv
```

The table summarizes the source paper's CAM6-style AGCM attribution panels:

- `aCTRL`: global observed SST response
- `aPac`: Pacific SST anomaly response
- `aIndAtl`: Indian + Atlantic response
- `aTrend`: background-trend response

It extracts equatorial wind-stress averages and June-December 200-850 hPa
`-omega` averages. A useful first check is the central Pacific Jun-Dec wind
stress: `aPac` is strongly positive, while `aIndAtl` and `aTrend` are negative in
the same region. This tabulates the visual result that Pacific warming alone
would favor stronger westerly response, whereas extra-Pacific/baseline warming
terms damp it.

## Fig. 4 Wind-Stress Experiment Summary

Generated with:

```bash
.venv/bin/python scripts/extract_fig4_wind_experiment_summary.py
```

Output:

```text
data/derived/peng2025_repro/tables/fig4_wind_experiment_summary.csv
```

The table extracts the source paper's GFDL CM2.1 Niño-3 time series for 2023 and
other comparable El Niños:

- `CTRL`
- `InitApr`
- `Wind2023` / `WindOther`

Treat `Wind2023` and `WindOther` as experiment-specific contribution curves from
the authors' setup, not as observed Niño-3 values. The December 2023 `InitApr`
value remains large relative to `CTRL`, consistent with substantial post-April
warming being retained even when low-frequency post-April wind-stress anomalies
are removed.

## First Independent OISST Check

Generated with:

```bash
.venv/bin/python scripts/extract_oisst_nino3_opendap.py
python3 scripts/compare_oisst_to_fig1.py
```

Outputs:

```text
data/derived/raw_validation/oisst_nino3_jun_jan.csv
data/derived/raw_validation/oisst_vs_fig1_nino3.csv
```

The OISSTv2.1 check reads only the Niño-3 OPeNDAP subset from NOAA PSL, avoiding
download of the full 2.1 GB global monthly file. It computes monthly anomalies
relative to 1982-2022 and then Jun-Jan event means.

First result:

| Year | Fig. 1 Nino-3 | Raw OISST Nino-3 | Difference |
|---|---:|---:|---:|
| 1982 | 1.657 | 1.716 | 0.059 |
| 1997 | 2.490 | 2.578 | 0.088 |
| 2015 | 2.201 | 2.262 | 0.061 |
| 2023 | 1.929 | 1.974 | 0.045 |

The full 1982-2023 correlation is 0.9999, so the SST side of Fig. 1 is now
independently reproduced from raw OISST rather than only from the article's
Zenodo figure data.

## First Independent GPCP Check

Generated with:

```bash
.venv/bin/python scripts/extract_gpcp_equatorial_opendap.py
python3 scripts/compare_gpcp_to_fig2.py
```

Outputs:

```text
data/derived/raw_validation/gpcp_equatorial_summary.csv
data/derived/raw_validation/gpcp_vs_fig2_precip.csv
```

The GPCP check reads only the equatorial Pacific OPeNDAP subset from NOAA PSL,
computes monthly anomalies relative to 1982-2022, and compares 2023 with the
1982/83, 1997/98, and 2015/16 composite.

Central Pacific Jun-Dec precipitation:

| Source | 2023 minus comparable |
|---|---:|
| Fig. 2 table | -2.699 |
| Raw GPCP | -3.096 |

This independently supports the Fig. 2 result that the central/eastern Pacific
precipitation response in 2023/24 was weaker than in comparable strong El Ninos.

## First Independent Atmospheric Check

Generated with:

```bash
.venv/bin/python scripts/extract_ncep_atmosphere_opendap.py
python3 scripts/compare_ncep_to_fig1.py
```

Outputs:

```text
data/derived/raw_validation/ncep_atmosphere_jun_jan.csv
data/derived/raw_validation/ncep_vs_fig1_atmosphere.csv
```

ERA5 requires Copernicus/CDS authentication, which is not configured locally in
this workspace. As an interim independent check, this step uses publicly
accessible NOAA PSL NCEP/NCAR Reanalysis 1 OPeNDAP fields:

- near-surface sigma-995 zonal wind over a central-western Pacific box
- SLP difference between Tahiti-like and Darwin-like boxes as an SOI proxy

Comparison with Fig. 1:

| Metric | 1982-2023 correlation |
|---|---:|
| CWP wind proxy vs Fig. 1 u10 | 0.9583 |
| SOI-like SLP proxy vs Fig. 1 SOI | 0.9914 |

Highlighted events:

| Year | Fig. 1 u | NCEP u proxy | Fig. 1 SOI | NCEP SOI-like |
|---|---:|---:|---:|---:|
| 1982 | 2.733 | 2.494 | -2.127 | -3.474 |
| 1997 | 2.774 | 3.137 | -1.510 | -2.629 |
| 2015 | 2.501 | 2.740 | -1.361 | -2.026 |
| 2023 | 0.640 | 0.253 | -0.433 | -0.640 |

This is not an exact ERA5 replication, but it supports the robustness of the weak
2023/24 atmospheric response in an independent public reanalysis product.

## Research-Stage Seasonal Table

Generated with:

```bash
python3 scripts/build_seasonal_research_table.py
```

Output:

```text
data/derived/research/seasonal_decoupling_first_pass.csv
```

The table now includes AMJ/JJA/SON/DJF OISST Nino-3 and NCEP atmospheric proxy
indices. The most important early research signal is that 2023/24 Nino-3 is
slightly stronger than the comparable-event composite in AMJ and JJA, while the
central-western Pacific wind proxy and SOI-like pressure gradient are already
much weaker. This points to summer-season atmospheric non-response as the first
mechanism target.
