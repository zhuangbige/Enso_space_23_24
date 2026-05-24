# Research Direction

This file keeps the project-level direction. The narrower post-literature-search
version is in `docs/research_direction_v2.md`.

## Revised Core Question

2023/24 is treated as a strong oceanic El Nino with muted atmospheric coupling.
After the literature search, the project is narrowed to the early development
stage:

**Why did Pacific atmosphere-ocean coupling weaken already during AMJ/JJA 2023,
when Nino-3 SST was comparable to or stronger than past strong El Nino events,
and how much of that early coupling deficit is associated with extra-Pacific
warming and background-state modulation?**

## Working Hypothesis

The event was not simply a weak version of a canonical strong El Nino. Instead,
Pacific ocean heat content and thermocline adjustment produced strong SST warming,
while pan-tropical warmth, Indian Ocean/Maritime Continent forcing, Atlantic
warming, and possibly North Pacific/NPMM-related anomalies damped or displaced
the atmospheric response during the development stage.

## First-Stage Deliverables

- Reproduce the basic fact pattern: strong Nino-3/Nino-3.4 SST anomalies but weak
  SOI and equatorial wind response.
- Quantify coupling residuals using historical SST-to-atmosphere regressions.
- Compare 2023/24 with 1982/83, 1997/98, and 2015/16.
- Produce seasonal maps for AMJ, JJA, SON, and DJF.
- Build coupling-efficiency residuals for AMJ/JJA, not only whole-event means.
- Test whether external-basin SST indices explain wind, SOI/SLP, rainfall, and
  OLR residuals after controlling for local Pacific SST.
- Prepare an AGCM matrix that can be run once CAM/CESM resources are confirmed.

## Out of Scope for Stage One

- No bulk climate data download by default.
- No AGCM run by default.
- No full western Pacific heat-content pathway attribution unless stage-one
  diagnostics show it is essential for the decoupling story.

## Provenance Rule

Every report must cite article sources for interpretations and dataset URLs for
all plotted or tabulated data. The running source log is:

```text
docs/data_source_log.md
```
