import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Terms First",
  "title": "Common abbreviations in this briefing: variables and datasets before results",
  "layout": "glossary",
  "table": [
    [
      "Abbrev.",
      "Full name",
      "Meaning in this project"
    ],
    [
      "SST",
      "Sea Surface Temperature",
      "The core ocean variable used to measure El Niño warming strength."
    ],
    [
      "Niño-3",
      "Eastern equatorial Pacific SST region",
      "Usually 5°S-5°N, 150°W-90°W; used here as the eastern-Pacific warming index."
    ],
    [
      "u10 / u850",
      "10-m / 850-hPa zonal wind",
      "East-west wind; positive anomalies usually indicate westerlies that support warm-water eastward propagation."
    ],
    [
      "SOI / SLP",
      "Southern Oscillation Index / Sea-Level Pressure",
      "SOI measures the east-west Pacific pressure seesaw; SLP is used to build SOI-like gradients."
    ],
    [
      "OLR / χ200",
      "Outgoing Longwave Radiation / 200-hPa velocity potential",
      "OLR diagnoses deep convection; χ200 diagnoses upper-level Walker-circulation divergence."
    ],
    [
      "AMJ/JJA/SON/DJF",
      "Apr-Jun / Jun-Aug / Sep-Nov / Dec-Feb",
      "Seasonal windows for the 2023/24 event; AMJ and JJA are the early developing seasons."
    ],
    [
      "OISST/GPCP/NCEP",
      "NOAA SST / global precipitation / NCEP reanalysis",
      "Public datasets already used for validation; ERA5 and OLR are next-stage additions."
    ],
    [
      "TNA/MC/WPWP/TIO",
      "Tropical North Atlantic / Maritime Continent / Western Pacific warm pool / Tropical Indian Ocean",
      "External-basin and tropical-background regions used in the mechanism diagnostics."
    ]
  ],
  "reader": "Reading guide: later slides spell out the full name before using abbreviations where possible. The one-line storyline is that SST was strong, but wind, pressure, rainfall, and convection did not respond in the historical strong-El Niño way.",
  "source": "Definitions follow standard climate diagnostics; variable usage follows docs/data_source_log.md and local analysis scripts."
};
export async function slide04(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
