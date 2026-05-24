import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Reproduced Fig. 1",
  "t": "Data shown: SST, sea-level pressure / 10-m wind, and Niño-3 versus atmospheric-response scatterplots",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.png",
  "boxes": [
    [
      "Data name",
      "Peng et al. Fig. 1 source data. The top panels show SST, sea-level pressure, and 10-m wind anomalies; the bottom panels relate Niño-3 SST to u10 and SOI."
    ],
    [
      "What it shows",
      "The 2023/24 Niño-3 SST was strong, but near-surface wind and pressure responses were weak relative to historical relationships."
    ],
    [
      "Paper link and innovation",
      "This reproduces the paper's core fact. The new contribution comes later: turning the event-level fact into seasonal AMJ/JJA coupling-efficiency diagnostics."
    ]
  ],
  "src": "Data: Peng et al. source archive; local file Fig1.png; table fig1_event_coupling.csv."
};
export async function slide06(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
