import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Reproduced Fig. 4",
  "t": "Data shown: wind-stress experiments and their effect on Niño-3 SST development",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.png",
  "boxes": [
    [
      "Data name",
      "Wind-stress experiments comparing Niño-3 SST evolution under different wind forcing settings. Key values include Dec Niño-3 CTRL=2.344 and Wind2023=0.681."
    ],
    [
      "What it shows",
      "The actual 2023 wind field did not force ocean warming as strongly as a canonical strong El Niño wind pattern would."
    ],
    [
      "Paper link and innovation",
      "This supports the paper's weak-wind point. The new contribution is to locate weak wind-pressure coupling during AMJ/JJA and compare it with rainfall."
    ]
  ],
  "src": "Data: Peng et al. source archive; table fig4_wind_experiment_summary.csv."
};
export async function slide10(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
