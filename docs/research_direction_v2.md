# Research Direction V2

Access date for source search: 2026-05-23.

## Position After Literature Search

The broad question, "Why was the 2023/24 El Nino atmosphere weak despite strong
Pacific SST warming?", is already an active literature topic. The project should
therefore avoid claiming novelty at the whole-event level.

The revised thesis direction is narrower:

**Why did Pacific atmosphere-ocean coupling weaken already during AMJ/JJA 2023,
when Nino-3 SST was comparable to or stronger than past strong El Nino events,
and how much of that early coupling deficit is associated with extra-Pacific
warming and background-state modulation?**

## Working Title

Chinese:

**2023/24 强厄尔尼诺发展早期太平洋海气耦合效率减弱及其外海盆调制**

English:

**Early-Season Weakening of Pacific Atmosphere-Ocean Coupling During the
2023/24 El Nino: Roles of Extra-Pacific Warming and Background-State Modulation**

## Why This Is Distinct From Existing Studies

Existing studies already show that:

- The event had strong Pacific ocean warming but muted wind/SOI response.
- Tropical Indian and Atlantic warming weakened tropical Pacific rainfall and
  extratropical teleconnections.
- Persistent easterlies, North Atlantic tripole forcing, NPMM state, and North
  Pacific SST anomalies contributed to the event not becoming a super El Nino.

This project should focus on:

- **Seasonal timing**: AMJ/JJA development stage rather than only DJF or annual
  event summaries.
- **Coupling efficiency**: residuals from SST-to-wind, SST-to-SOI, and
  SST-to-rainfall relationships.
- **Mechanism pathway**: whether extra-Pacific warmth is associated with
  Maritime Continent/Indian Ocean convection, strengthened Pacific Walker-cell
  background, or altered western-central Pacific wind response.
- **Reproducibility chain**: paper reproduction -> raw-product validation ->
  seasonal residuals -> mechanism diagnostics.

## Primary Research Questions

1. During AMJ/JJA 2023, how large was the deficit in Pacific atmospheric response
   relative to the historical Nino-3 SST relationship?
2. Which external basin indices best co-vary with this early coupling deficit:
   tropical North Atlantic, tropical Indian Ocean, Maritime Continent, western
   Pacific warm pool, or North Pacific/NPMM-related SST patterns?
3. Does the weak coupling appear first in winds/SLP, rainfall/OLR, or upper-level
   Walker circulation diagnostics?
4. Can regression or partial-regression diagnostics separate local Pacific SST
   forcing from extra-Pacific SST covariability before any AGCM experiment?

## First Research Package

Use monthly data first:

- OISST: Nino-3 and external-basin SST indices.
- GPCP and/or OLR: tropical Pacific and Maritime Continent convection response.
- NCEP/NCAR R1 first, ERA5 later: u850/u10, SLP/SOI-like gradients, velocity
  potential/Walker diagnostics.

Event comparison:

- Main strong-event composite: 1982/83, 1997/98, 2015/16.
- Target event: 2023/24.
- Extension if useful: 2009/10 and moderate events for regression context.

Season windows:

- AMJ and JJA are the core novelty windows.
- SON and DJF are retained for continuity with the paper and literature.

## Citation And Data Provenance Rule

Every claim in reports must identify whether it comes from:

- a cited paper, with article URL/DOI;
- a source-paper reproduction table/figure;
- a raw public dataset, with dataset page and access URL;
- a newly derived diagnostic, with input data and local output path.

Every new data access must be appended to `docs/data_source_log.md` before or
immediately after the extraction is run.
