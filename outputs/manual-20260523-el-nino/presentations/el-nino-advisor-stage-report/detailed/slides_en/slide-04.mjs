import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Terms First 2",
  "t": "Dataset, model-experiment, and region abbreviations",
  "layout": "glossary",
  "rows": [
    [
      "Abbrev.",
      "Full name",
      "Meaning in this project"
    ],
    [
      "NOAA",
      "National Oceanic and Atmospheric Administration",
      "Main provider for OISST and OLR products."
    ],
    [
      "NCEP/NCAR R1",
      "NCEP/NCAR Reanalysis 1",
      "Current fallback dataset for low-level wind and sea-level pressure."
    ],
    [
      "ERA5",
      "ECMWF Reanalysis version 5",
      "Next manuscript-grade dataset for u850, SLP, and Walker circulation."
    ],
    [
      "ERSSTv5",
      "Extended Reconstructed Sea Surface Temperature version 5",
      "Long-record SST check for historical robustness."
    ],
    [
      "AGCM",
      "Atmospheric General Circulation Model",
      "Atmospheric model forced by prescribed SST boundary conditions."
    ],
    [
      "ENSO",
      "El Niño-Southern Oscillation",
      "The coupled tropical Pacific system containing El Niño and La Niña."
    ],
    [
      "CWP",
      "Central-western Pacific",
      "Key region for low-level wind response in this study."
    ],
    [
      "MJO/RMM",
      "Madden-Julian Oscillation / Real-time Multivariate MJO index",
      "Used later to separate intraseasonal variability from ENSO background."
    ],
    [
      "CTRL",
      "Control experiment",
      "Baseline model experiment for comparison with sensitivity experiments."
    ]
  ],
  "src": "Acronyms checked against all detailed slide text."
};
export async function slide04(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
