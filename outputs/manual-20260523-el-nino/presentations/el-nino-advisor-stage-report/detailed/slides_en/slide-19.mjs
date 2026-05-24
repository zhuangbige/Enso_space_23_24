import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Working Topic",
  "t": "Proposed topic: developing-season coupling failure during the 2023/24 strong El Niño and external-basin modulation",
  "layout": "text",
  "claim": "Working hypothesis: spring-summer external-basin warmth and tropical-mean warming altered the Walker circulation and convective threshold, delaying or weakening the canonical wind-pressure-rainfall response to warm Pacific SST.",
  "points": [
    "H1: Tropical North Atlantic, Indian Ocean, and Maritime Continent warmth suppressed the central-Pacific westerly response.",
    "H2: Maritime Continent / Indian Ocean convection maintained western-side convection and weakened the eastward rainfall shift.",
    "H3: Tropical-mean warming raised the convective threshold, so the same Pacific SST anomaly produced weaker atmospheric feedback."
  ],
  "src": "Current diagnostics establish association; mechanism attribution requires ERA5, OLR, MJO/RMM and AGCM tests."
};
export async function slide19(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
