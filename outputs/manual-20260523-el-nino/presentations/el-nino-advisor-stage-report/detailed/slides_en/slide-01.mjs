import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Advisor Reading Version",
  "t": "Atmosphere-ocean decoupling during the 2023/24 strong El Niño: reproduction, open question, and new diagnostics",
  "layout": "cover",
  "sub": "Goal: make every figure readable without oral explanation by stating the data name, physical meaning, link to the original paper, and new contribution.",
  "bullets": [
    "Explain variables and abbreviations before using them heavily.",
    "For each figure, state: data name, what it shows, how it maps to Peng et al. 2025, and what is new here.",
    "Use larger explanatory text, accepting a slightly longer deck."
  ],
  "src": "Peng et al. 2025; NOAA OISST; GPCP; NCEP/NCAR R1; local diagnostics. 2026-05-24."
};
export async function slide01(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
