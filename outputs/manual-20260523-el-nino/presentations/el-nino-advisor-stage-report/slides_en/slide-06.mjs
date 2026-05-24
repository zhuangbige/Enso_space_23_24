import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Reproduction 2",
  "title": "Peng et al. Fig. 2: the paper attributes the strong event to equatorial Pacific ocean dynamics",
  "layout": "fullImage",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig2.png",
  "figNote": "Data note: Peng et al. 2025 source archive Fig. 2; local table fig2_equatorial_summary.csv. The figure supports the ocean-dynamics argument using equatorial propagation, subsurface heat content, and wind-stress diagnostics. How to read: this is the paper's baseline attribution, not the new mechanism. It explains how ocean dynamics produced strong warming, but it does not fully explain why early wind, pressure, and rainfall responses lagged.",
  "source": "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig2.png."
};
export async function slide06(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
