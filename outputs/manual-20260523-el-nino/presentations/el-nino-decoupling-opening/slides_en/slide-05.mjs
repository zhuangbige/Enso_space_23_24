import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Raw Validation",
  "title": "Independent public datasets reproduce the paper-level signal",
  "layout": "chartText",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/validation_summary.png",
  "notes": [
    "Raw OISST Niño-3 correlates 0.9999 with the reproduced Fig. 1 index.",
    "GPCP shows weaker 2023/24 central/eastern Pacific precipitation than the strong-El Niño composite.",
    "NCEP wind and SOI-like proxies align closely with the paper's atmospheric indices."
  ],
  "source": "Raw validation: NOAA PSL OPeNDAP OISST/GPCP/NCEP outputs in data/derived/raw_validation."
};
export async function slide05(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
