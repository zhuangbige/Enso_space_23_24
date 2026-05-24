import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Reproduced Fig. 3",
  "t": "Data shown: wind-stress response in Atmospheric General Circulation Model experiments",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.png",
  "boxes": [
    [
      "Data name",
      "AGCM experiments separating global SST, Pacific SST, and Indian/Atlantic SST boundary conditions and comparing atmospheric wind-stress responses."
    ],
    [
      "What it shows",
      "Pacific warm SST should drive a canonical atmospheric response, but Indian and Atlantic background SST can offset or damp that response."
    ],
    [
      "Paper link and innovation",
      "This follows the paper's external-basin modulation idea. The new step is to test the same idea first with observed seasonal diagnostics."
    ]
  ],
  "src": "Data: Peng et al. source archive; table fig3_agcm_summary.csv."
};
export async function slide09(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
