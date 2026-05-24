# Seasonal Decoupling First Pass

This is the first research-stage table after the reproduction/validation phase.
It uses raw OISST, raw GPCP, and the public NCEP/NCAR atmospheric proxy dataset.

## Output Table

```text
data/derived/research/seasonal_decoupling_first_pass.csv
```

Generated with:

```bash
python3 scripts/build_seasonal_research_table.py
```

## First Findings

| Metric | Season/window | 2023 | Comparable | 2023 minus comparable |
|---|---:|---:|---:|---:|
| Nino-3 SST | AMJ | 0.974 | 0.692 | 0.282 |
| Nino-3 SST | JJA | 1.733 | 1.424 | 0.309 |
| Nino-3 SST | SON | 2.148 | 2.481 | -0.333 |
| Nino-3 SST | DJF | 1.898 | 2.637 | -0.739 |
| NCEP CWP u proxy | Jun-Jan | 0.253 | 2.790 | -2.538 |
| NCEP SOI-like proxy | Jun-Jan | -0.640 | -2.710 | 2.070 |
| NCEP CWP u proxy | AMJ | -0.695 | 1.606 | -2.301 |
| NCEP CWP u proxy | JJA | -0.312 | 2.264 | -2.576 |
| NCEP CWP u proxy | SON | 0.768 | 3.486 | -2.718 |
| NCEP CWP u proxy | DJF | 0.171 | 2.228 | -2.057 |
| NCEP SOI-like proxy | AMJ | -0.506 | -1.639 | 1.133 |
| NCEP SOI-like proxy | JJA | -0.806 | -2.357 | 1.551 |
| NCEP SOI-like proxy | SON | -1.078 | -2.614 | 1.536 |
| NCEP SOI-like proxy | DJF | -0.645 | -3.559 | 2.914 |
| GPCP central Pacific precip | Jun-Dec | 1.761 | 4.857 | -3.096 |
| GPCP central Pacific precip | Jan-Apr next | 1.056 | 5.822 | -4.765 |

## Interpretation

The seasonal SST evolution already hints at a more specific research question.
2023/24 is not simply weaker than past strong El Ninos throughout development:
Nino-3 is slightly stronger than the 1982/83, 1997/98, and 2015/16 composite in
AMJ and JJA, then becomes weaker in SON and DJF.

The atmospheric and rainfall response is much more suppressed than the SST
difference alone would imply. The key new seasonal contrast is AMJ/JJA: Nino-3
is already stronger than the comparable-event composite, but the central-western
Pacific wind proxy is weaker by more than 2 m/s and the SOI-like pressure
gradient is also much weaker.

That supports shifting from "is the paper right?" to the research question:

> Why did a spring-summer oceanic warming comparable to past strong El Ninos fail
> to produce a comparable central Pacific wind, SOI, and precipitation response?

## Next Required Step

The next research task is to move beyond box indices into maps and forcing
diagnostics:

1. Produce AMJ/JJA/SON/DJF maps for SST, precipitation, NCEP/ERA5 wind, and SLP.
2. Add Indian Ocean, Maritime Continent, and tropical Atlantic SST/precipitation
   indices to test external-basin damping.
3. Replace the NCEP fallback with ERA5 once CDS credentials are configured, or
   keep NCEP as a robustness product.

## External-Basin Index Setup

The external-basin OISST extraction script has been added:

```bash
.venv/bin/python scripts/extract_oisst_external_basin_indices.py
```

It defines first-pass SST boxes for:

- Tropical Indian Ocean
- Maritime Continent
- Western Pacific warm pool
- Tropical North Atlantic

A small OPeNDAP smoke test succeeded, but the full 1982-2024 extraction still
needs to be run once network execution is available again.

Once the monthly file is complete, build the seasonal external-basin table with:

```bash
python3 scripts/build_external_basin_summary.py
```

Expected output:

```text
data/derived/research/external_basin_seasonal_summary.csv
```

That table will provide the first direct test of whether AMJ/JJA 2023 had
unusual tropical Indian Ocean, Maritime Continent, western Pacific warm-pool, or
tropical North Atlantic SST conditions relative to the comparable strong El Ninos.
