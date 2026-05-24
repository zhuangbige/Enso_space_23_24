import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Terms First",
  "t": "Common variables and abbreviations in this deck",
  "layout": "glossary",
  "rows": [
    [
      "Abbrev.",
      "Full name",
      "Meaning in this project"
    ],
    [
      "SST",
      "Sea Surface Temperature",
      "Core ocean variable for El Niño warming strength."
    ],
    [
      "Niño-3",
      "Eastern equatorial Pacific SST region",
      "Index region representing eastern-Pacific warming."
    ],
    [
      "u10 / u850",
      "10-m / 850-hPa zonal wind",
      "East-west wind; westerly anomalies support coupling."
    ],
    [
      "SOI / SLP",
      "Southern Oscillation Index / Sea-Level Pressure",
      "Pressure seesaw and Walker-circulation response."
    ],
    [
      "OLR / χ200",
      "Outgoing Longwave Radiation / 200-hPa velocity potential",
      "Deep convection and upper-level circulation diagnostics."
    ],
    [
      "AMJ/JJA",
      "Apr-Jun / Jun-Aug",
      "Early developing seasons emphasized here."
    ],
    [
      "TNA/MC/WPWP/TIO",
      "Tropical North Atlantic / Maritime Continent / Western Pacific warm pool / Tropical Indian Ocean",
      "External-basin and tropical-background regions."
    ]
  ],
  "src": "Standard climate diagnostics and docs/data_source_log.md."
};
export async function slide03(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
