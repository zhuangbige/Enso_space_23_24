import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "New Finding 2",
  "t": "Data shown: AMJ/JJA SST and GPCP rainfall spatial anomalies",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_sst_precip.png",
  "boxes": [
    [
      "Data name",
      "Top panels: OISST sea-surface temperature. Bottom panels: GPCP precipitation. Each map is 2023 AMJ/JJA minus the historical strong-El Niño composite."
    ],
    [
      "What it shows",
      "Spring-summer 2023 warming extended beyond the eastern Pacific into TNA, the Maritime Continent, and the western Pacific warm pool, while central/eastern Pacific rainfall did not strengthen."
    ],
    [
      "Paper link and innovation",
      "This corresponds to the paper's external-basin modulation hint. The innovation is developing-season spatial evidence tying warm background conditions to weak rainfall response."
    ]
  ],
  "src": "Data: NOAA OISST v2.1 and GPCP; summary table stage_a_spatial_summary.csv."
};
export async function slide14(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
