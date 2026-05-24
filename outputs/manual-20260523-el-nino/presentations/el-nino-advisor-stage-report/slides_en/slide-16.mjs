import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Next Step",
  "title": "Next stage: add ERA5 and OLR to move from phenomenon diagnosis to mechanism tests",
  "layout": "roadmap",
  "steps": [
    "ERA5 u850/SLP/χ200\nreplace NCEP fallback",
    "NOAA OLR + GPCP\nvalidate convection centers",
    "ERSSTv5 long record\ncheck historical robustness",
    "AGCM model plan\nPacific-only / IO-ATL / detrended"
  ],
  "notes": [
    "The research line can now start formally: diagnose developing-season coupling-efficiency loss, then strengthen mechanism evidence with ERA5/OLR.",
    "The short-term priority is not to run AGCM immediately, but to add ERA5 u850/SLP/χ200 and OLR so the wind-pressure-Walker-convection evidence becomes manuscript-grade."
  ],
  "source": "Data priorities from reports/当前数据分析阶段总结.md."
};
export async function slide16(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
