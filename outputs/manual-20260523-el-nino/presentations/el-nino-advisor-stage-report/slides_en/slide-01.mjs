import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Advisor Update",
  "title": "Atmosphere-ocean decoupling during the 2023/24 strong El Niño: from paper reproduction to developing-season asynchrony",
  "subtitle": "Main question: why did a strong oceanic event fail to trigger equally strong wind, pressure, rainfall, and convection responses?",
  "layout": "cover",
  "bullets": [
    "Reproduce the core figures and metrics from Peng et al. 2025.",
    "Validate the ocean-strong / atmosphere-weak signal with public datasets.",
    "Extend the analysis to AMJ/JJA historical comparisons."
  ],
  "source": "Peng et al. 2025; NOAA OISST v2.1; GPCP; NCEP/NCAR R1. Briefing date: 2026-05-23."
};
export async function slide01(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
