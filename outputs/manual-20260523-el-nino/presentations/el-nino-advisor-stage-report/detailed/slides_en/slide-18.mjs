import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Difference From Literature",
  "t": "Existing studies emphasize mechanisms or individual months; this project systematizes seasonal coupling efficiency",
  "layout": "tableText",
  "rows": [
    [
      "Study",
      "Existing focus",
      "New contribution here"
    ],
    [
      "Peng et al. 2025",
      "Ocean-dynamical event generation",
      "Why and when the atmospheric response weakened."
    ],
    [
      "Zhang et al. 2025",
      "Weak rainfall/teleconnections and external-basin heating",
      "Seasonal matrix across wind, pressure, rainfall, and SST."
    ],
    [
      "Kim et al. 2025",
      "Developing-season wind anomalies and west-central Pacific gradients",
      "Adds SOI-like pressure, GPCP rainfall, and external-basin historical comparison."
    ],
    [
      "Zhao et al. 2025",
      "July 2023 TNA and monsoon/Maritime Continent heating",
      "Tracks AMJ/JJA through SON/DJF continuously."
    ],
    [
      "Yang & Li 2025",
      "January 2024 MJO/trend/ENSO decomposition",
      "Builds developing-season background before adding MJO/OLR tests."
    ]
  ],
  "text": "The difference is not simply adding a dataset. It is turning weak response into a time-by-variable question: which season, which variable, and which external-basin background changed first?",
  "src": "Literature notes: docs/literature_method_notes.md; source IDs L2-L8."
};
export async function slide18(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
