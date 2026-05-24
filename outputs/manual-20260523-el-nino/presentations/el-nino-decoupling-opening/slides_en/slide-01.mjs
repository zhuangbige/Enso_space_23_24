import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Research Topic",
  "title": "Why did the 2023/24 strong El Niño show ocean-strong but atmosphere-weak coupling?",
  "subtitle": "From reproducing Peng et al. 2025 to testing whether extra-Pacific warming damped the Pacific atmospheric response",
  "layout": "cover",
  "bullets": [
    "Core question: which basins or background-state factors weakened the canonical wind, SOI, rainfall, and Walker-circulation response to warm Pacific SST?",
    "Current stage: paper reproduction is complete; raw-product validation and first mechanism diagnostics are underway."
  ],
  "source": "Source: Peng et al. 2025 Nature Geoscience; NOAA OISST, GPCP, NCEP/NCAR reanalysis."
};
export async function slide01(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
