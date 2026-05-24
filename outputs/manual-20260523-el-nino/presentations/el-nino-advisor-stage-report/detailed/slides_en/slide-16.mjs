import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "New Finding 4",
  "t": "Data shown: external-basin warm anomalies and seasonal coupling efficiency",
  "layout": "twoFigureExplain",
  "left": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/external_basin_bars.png",
  "right": "/Users/daiyue/Documents/Maryland/data/derived/research/asynchronous_coupling_by_season.png",
  "boxes": [
    [
      "Data name",
      "Left: OISST indices for TNA, western Pacific warm pool, Maritime Continent, and Tropical Indian Ocean. Right: seasonal coupling-efficiency diagnostics."
    ],
    [
      "What it shows",
      "Unusual external-basin warmth and low Pacific atmospheric coupling efficiency occur together in spring-summer 2023."
    ],
    [
      "Paper link and innovation",
      "Peng et al. suggests external basins may damp Pacific response. The new step is observationally confirming that these warm anomalies were present during the coupling-loss season."
    ]
  ],
  "src": "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_efficiency.csv."
};
export async function slide16(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
