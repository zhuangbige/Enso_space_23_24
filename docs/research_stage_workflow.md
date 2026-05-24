# Research-Stage Workflow

This starts after the paper reproduction and first raw-product checks.

## Current Research Question

Why did 2023 AMJ/JJA Nino-3 warming, which was comparable to or slightly stronger
than past strong El Ninos, fail to produce comparable central Pacific wind,
pressure-gradient, precipitation, and convection responses?

This is intentionally narrower than the whole-event question already addressed
by recent studies on the 2023/24 El Nino. The project's first novelty target is
the **early-season coupling-efficiency deficit**.

## Current Evidence

- Raw OISST: 2023 Nino-3 is stronger than the comparable-event composite in AMJ
  and JJA.
- Raw NCEP proxy: central-western Pacific wind and SOI-like pressure response are
  much weaker in the same seasons.
- Raw GPCP: central/eastern Pacific precipitation is weaker than comparable
  strong El Ninos.
- Raw OISST external-basin indices: 2023 AMJ/JJA tropical North Atlantic,
  western Pacific warm pool, Maritime Continent, and tropical Indian Ocean SSTs
  are all warmer than the 1982/1997/2015 comparable-event composite.
- Seasonal asynchronous coupling diagnostics: AMJ/JJA Nino-3 SST was stronger
  than the comparable-event composite, while CWP wind response was opposite-sign
  or near zero and SOI-like response efficiency was only about 22-28%.

## External-Basin Step

Run:

```bash
.venv/bin/python scripts/extract_oisst_external_basin_indices.py
python3 scripts/build_external_basin_summary.py
```

Then inspect:

```text
data/derived/research/external_basin_seasonal_summary.csv
```

The key first pass is AMJ/JJA differences for:

- tropical Indian Ocean
- Maritime Continent
- western Pacific warm pool
- tropical North Atlantic

Note: NOAA PSL OPeNDAP can silently return all-zero arrays for very large remote
OISST slices. The extraction script therefore reads 12 months per request.

## Next Diagnostics

1. Map AMJ/JJA SST anomalies to confirm the external-basin spatial pattern.
2. Map precipitation, near-surface wind, and SLP anomalies for the same seasons.
3. Build scatter/regression residual diagnostics linking external-basin warmth to
   weak Pacific atmospheric coupling.
4. Add OLR or alternative convection data if 2023/24 coverage is available.
5. Add North Pacific / NPMM-related indices to avoid falsely attributing all weak
   coupling to tropical Indian/Atlantic warming.

## Interpretation Rule

Treat these external-basin SST indices as candidate damping/background indicators,
not causal proof. A causal attribution step would still require either AGCM
experiments, existing pacemaker experiment output, or a regression/partial
regression design that separates Pacific SST from extra-Pacific SST covariability.

## Source Logging Rule

Before or immediately after any data extraction, append the data page and exact
access URL to:

```text
docs/data_source_log.md
```

Reports should cite both:

- article source for interpretation;
- dataset source URL for each plotted or tabulated result.
