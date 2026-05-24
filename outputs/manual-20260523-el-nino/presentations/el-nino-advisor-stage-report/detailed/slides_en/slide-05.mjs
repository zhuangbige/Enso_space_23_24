import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Paper Contribution",
  "t": "Peng et al. 2025 mainly answers how the strong 2023/24 El Niño was generated",
  "layout": "tableText",
  "rows": [
    [
      "Layer",
      "Paper conclusion",
      "Role for this project"
    ],
    [
      "Ocean",
      "Equatorial Pacific ocean dynamics and heat content made the event strong.",
      "Provides the baseline explanation for strong SST."
    ],
    [
      "Atmosphere",
      "Wind-pressure feedback was weak relative to historical strong El Niño events.",
      "Raises the weak-response question."
    ],
    [
      "External basins",
      "Indian and Atlantic SST may offset part of the Pacific forcing.",
      "Suggests a mechanism pathway."
    ],
    [
      "Experiments",
      "AGCM and wind-stress experiments separate SST-boundary and wind-forcing effects.",
      "Guides future Pacific-only and external-basin experiments."
    ]
  ],
  "text": "This project does not overturn the paper. It extends the logic from oceanic event generation to atmospheric coupling: why did strong SST not produce a synchronous atmospheric response?",
  "src": "L1: Peng et al. 2025 Nature Geoscience."
};
export async function slide05(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
