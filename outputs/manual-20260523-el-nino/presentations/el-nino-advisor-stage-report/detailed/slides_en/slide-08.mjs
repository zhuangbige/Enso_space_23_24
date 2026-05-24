import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Reproduced Fig. 2",
  "t": "Data shown: equatorial Pacific propagation, subsurface heat structure, and ocean-dynamical diagnostics",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig2.png",
  "boxes": [
    [
      "Data name",
      "Peng et al. Fig. 2 equatorial sections and longitude-time diagnostics showing SST, subsurface heat anomalies, propagation, and wind-stress-related signals."
    ],
    [
      "What it shows",
      "The strong 2023/24 warming was supported by ocean dynamics, not merely by a surface-temperature fluctuation."
    ],
    [
      "Paper link and innovation",
      "This reproduces the paper's ocean-dynamics attribution. The new project accepts this and asks why the atmosphere did not respond proportionally."
    ]
  ],
  "src": "Data: Peng et al. source archive; local Fig2.png; table fig2_equatorial_summary.csv."
};
export async function slide08(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
