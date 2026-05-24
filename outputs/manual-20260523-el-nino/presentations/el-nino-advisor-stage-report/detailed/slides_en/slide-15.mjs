import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "New Finding 3",
  "t": "Data shown: AMJ/JJA near-surface wind and sea-level-pressure spatial anomalies",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_ncep_wind_slp.png",
  "boxes": [
    [
      "Data name",
      "NCEP/NCAR R1 near-surface sigma995 wind and sea-level pressure, calculated as 2023 AMJ/JJA minus the historical strong-event composite."
    ],
    [
      "What it shows",
      "Central-west Pacific low-level wind is weaker than in historical strong events, and the pressure-gradient pattern is not a canonical strong-El Niño Walker response."
    ],
    [
      "Paper link and innovation",
      "This corresponds to the paper's weak-wind finding. The innovation is making it seasonal and spatial, showing that AMJ/JJA already contains atmospheric asynchrony."
    ]
  ],
  "src": "Data: NCEP/NCAR R1 fallback; final manuscript stage should verify with ERA5."
};
export async function slide15(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
