# Seasonal Asynchronous Coupling Design

Access date for literature and data-source checking: 2026-05-23.

## Research Pivot

The project should now move from reproducing Peng et al. (2025) to a new, narrower question:

**During the 2023/24 strong El Nino, did tropical Pacific SST, equatorial winds, pressure/SOI, rainfall/convection, and Walker-circulation indicators respond in the same season, or did the atmosphere lag, mute, or reverse the oceanic signal?**

The thesis-sized contribution is not simply "2023/24 had weak atmospheric coupling"; that is already established. The sharper contribution is a **seasonal asynchronous response matrix** that shows which coupling variables failed first, where the seasonal phase mismatch was largest, and which external-basin or background-state signals are consistent with that mismatch.

## What The Recent Papers Teach Us

### Peng et al. 2025

Source: https://www.nature.com/articles/s41561-025-01700-9

Useful methods to internalize:

- Reproduce event-level coupling by comparing 2023/24 against historical strong El Nino cases.
- Separate oceanic growth from atmospheric wind feedback by contrasting observed evolution and wind-forced model experiments.
- Use Pacific-only versus external-basin SST forcing logic to frame why warm Pacific SST did not generate a canonical atmospheric response.

How to adapt it:

- Keep Peng et al. as the reproduction backbone.
- Convert the annual / Jun-Jan result into AMJ, JJA, SON, and DJF seasonal diagnostics.
- Use the reproduced Fig. 1-4 values as the bridge between the original paper and our new seasonal question.

### Zhang et al. 2025

Source: https://www.nature.com/articles/s43247-025-02584-8

Useful methods to internalize:

- Compare tropical Pacific rainfall and extratropical teleconnections against strong-El-Nino expectations.
- Use observed/reanalysis data plus atmospheric-model logic to argue that tropical Indian and Atlantic warming suppressed canonical Pacific rainfall and teleconnection responses.

How to adapt it:

- Add rainfall/OLR as an atmospheric response layer, rather than diagnosing only SST and wind.
- Treat weak tropical rainfall response as the pathway between equatorial decoupling and remote teleconnection weakness.

### Kim et al. 2025

Source: https://www.nature.com/articles/s41612-024-00890-0

Useful methods to internalize:

- Focus on development-stage easterly anomalies after the triple-dip La Nina.
- Relate wind anomalies to west-central Pacific SST gradient and delayed El Nino growth.

How to adapt it:

- Use AMJ/JJA 2023 as the primary development-season test.
- Map west-central Pacific SST gradient and central-western Pacific wind anomalies, not only Nino-3 or Nino-3.4.

### Zhao, Li & Pan 2025

Source: https://link.springer.com/article/10.1007/s00382-025-07625-8

Useful methods to internalize:

- A month-specific decoupling diagnosis can be publishable when the mechanism is sharply identified.
- July 2023 is treated as a specific wind-SST decoupling case.
- Tropical North Atlantic warming and Indian summer monsoon / Maritime Continent heating are tested as competing or complementary sources of anomalous Pacific easterlies.

How to adapt it:

- Use July 2023 as a key zoom-in month inside the broader JJA asynchronous-coupling matrix.
- Avoid duplicating the paper by not making July alone the whole story.
- Compare July with AMJ/JJA seasonal means to show whether the July mechanism was an isolated month or part of a broader seasonal phase mismatch.

### Yang & Li 2025

Source: https://journals.ametsoc.org/view/journals/clim/38/23/JCLI-D-24-0689.1.xml

Useful methods to internalize:

- January 2024 easterly anomalies can be decomposed into El Nino-induced westerlies versus MJO and interdecadal/global-trend-related easterly components.
- The central question is not only response magnitude; it is sign competition among processes.

How to adapt it:

- Use January 2024 as a DJF zoom-in month, paired with July 2023 as the development-stage zoom.
- Add MJO/RMM and trend-separated SST/atmospheric anomalies only after the seasonal matrix is stable.

### Hong et al. 2024 and Lin et al. 2025

Sources:

- https://doi.org/10.1029/2024GL110639
- https://www.nature.com/articles/s41612-025-01013-z

Useful methods to internalize:

- North Atlantic Tripole, extratropical North Pacific SSTs, and NPMM-like states offer non-tropical explanations for weak wind burst and Kelvin-wave development.
- These mechanisms are especially relevant before and during the El Nino development stage.

How to adapt it:

- Include external-basin SST indices in AMJ/JJA.
- Treat NPMM/North Pacific as a robustness branch, not the first-pass core unless the maps show a clear signal.

## Proposed Analysis Architecture

### Layer 1: Seasonal Response Matrix

Build a table and figure with rows as seasons and columns as:

- Pacific ocean forcing: Nino-3, Nino-3.4, west-central Pacific gradient.
- Local atmosphere: central/western Pacific low-level zonal wind, 10 m wind stress proxy, SLP/SOI-like gradient.
- Convection: GPCP precipitation and OLR when available.
- Walker circulation: 200 hPa velocity potential or divergent wind proxy when ERA5 pressure-level data is available.
- External basins: tropical North Atlantic, tropical Indian Ocean, Maritime Continent, western Pacific warm pool, optional North Pacific/NPMM.

The core metric remains:

```text
response_efficiency = atmospheric_response_ratio / pacific_sst_strength_ratio
```

where the strength ratios compare 2023/24 against comparable strong El Nino events.

### Layer 2: Seasonal Maps

Create AMJ, JJA, SON, and DJF maps for:

- SST anomalies from OISST.
- Low-level wind and SLP from ERA5 when available; NCEP/NCAR only as fallback.
- Rainfall anomalies from GPCP.
- OLR anomalies from CPC Blended OLR if available.

The paper-quality figure should be a four-column seasonal panel, with consistent color scales and boxes marking Nino-3, central-western Pacific wind, TNA, tropical Indian Ocean, and Maritime Continent regions.

### Layer 3: Key-Month Mechanism Zooms

Use July 2023 and January 2024 as mechanism panels:

- July 2023: test whether JJA weak wind response is dominated by tropical Atlantic and ISM/MC heating signals.
- January 2024: test whether DJF apparent response weakness includes MJO/trend-related easterly competition.

These zooms should not replace the seasonal matrix. They should explain the two most visible breaks in synchrony.

## Data Need Decision

Existing local data is enough for the first analysis layer:

- Peng et al. source archive for reproduced baseline.
- OISST for SST indices and external-basin SSTs.
- GPCP for precipitation.
- NCEP/NCAR R1 fallback for low-level wind and SLP-like diagnostics.

Additional data is needed before a defensible paper-quality manuscript:

- ERA5 single-level monthly means for SLP, 10 m winds, total precipitation, and surface fluxes.
- ERA5 pressure-level monthly means for u850 and Walker-circulation diagnostics.
- CPC Blended OLR or another 2023/24-ready OLR product.
- RMM/MJO index or daily OLR/wind fields for January 2024 decomposition.
- ERSSTv5 for long-record SST robustness.
- Optional NPMM/PMM index or North Pacific SST pattern index if the early-season maps show a strong North Pacific pathway.

## Figure Set For The New Article

### Figure 1: Reproduction-to-New-Question Bridge

Content:

- Reproduced Peng et al. event-level SST, wind, and SOI facts.
- Added seasonal response-efficiency bars for AMJ/JJA/SON/DJF.

Message:

2023/24 is not only weakly coupled on annual/event mean. The weakest atmospheric synchronization begins in the development seasons.

### Figure 2: Seasonal Asynchronous Coupling Matrix

Content:

- Heatmap of 2023/comparable ratios by season and variable.
- Columns: Nino-3 SST, CWP wind, SOI-like SLP, central-Pacific precipitation, TNA SST, Indian Ocean SST, Maritime Continent SST.

Message:

Oceanic warming and external-basin warming peak early, while atmospheric Pacific response is muted or sign-opposed.

### Figure 3: AMJ/JJA Spatial Diagnosis

Content:

- OISST SST anomaly maps.
- Low-level wind / SLP maps from ERA5 or NCEP fallback.
- GPCP/OLR convection maps.

Message:

The early-season atmosphere did not organize into a canonical Bjerknes-feedback pattern despite strong Pacific warming.

### Figure 4: July 2023 and January 2024 Mechanism Zooms

Content:

- July 2023 TNA/Indian/MC heating and equatorial wind anomalies.
- January 2024 MJO/trend competition panel after new data is obtained.

Message:

Two different mechanisms can create similar apparent decoupling: external-basin heating during development and intraseasonal/background-state interference during mature winter.

## Working Title Options

1. Seasonal asynchrony in the atmospheric response to the 2023/24 strong El Nino
2. Why the 2023/24 strong El Nino warmed the ocean before the atmosphere followed
3. Seasonally dependent air-sea decoupling during the 2023/24 strong El Nino

Recommended title for now:

**Seasonal asynchrony in the atmospheric response to the 2023/24 strong El Nino**

It is broad enough for AMJ-DJF analysis, but narrow enough to avoid competing directly with single-month July or January papers.
