import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Quantified Fig. 1",
  "t": "Data shown: u10 and SOI response ratios relative to historical strong El Niño behavior",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/coupling_ratios.png",
  "boxes": [
    [
      "Data name",
      "Event metrics extracted from fig1_event_coupling.csv. Niño-3 is SST strength, u10 is 10-m zonal wind, and SOI is the Southern Oscillation Index."
    ],
    [
      "What it shows",
      "The 2023 u10 response ratio is about 0.27 and the SOI response ratio is about 0.31, roughly one-third of the expected historical response."
    ],
    [
      "Paper link and innovation",
      "This corresponds to Peng et al. Fig. 1. The innovation is to generalize this response-ratio idea into a seasonal coupling matrix."
    ]
  ],
  "src": "Derived table: data/derived/peng2025_repro/tables/fig1_event_coupling.csv."
};
export async function slide07(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
