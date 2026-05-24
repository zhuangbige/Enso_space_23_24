import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Working Topic",
  "title": "Proposed topic: developing-season atmosphere-ocean coupling failure during the 2023/24 strong El Niño and its external-basin modulation",
  "layout": "thesis",
  "claim": "Working hypothesis: spring-summer external-basin warmth and the tropical-mean warming background altered the Walker circulation and convective threshold, delaying or weakening the canonical wind-pressure-rainfall response to warm Pacific SST.",
  "notes": [
    "Testable H1: AMJ/JJA external-basin warmth suppressed central-Pacific westerly response.",
    "Testable H2: Maritime Continent / Indian Ocean heating maintained western-side convection and weakened eastward rainfall displacement.",
    "Testable H3: TNA warmth or tropical-mean warming raised the threshold for ENSO atmospheric response.",
    "Each hypothesis is testable: ERA5/OLR first establish the atmospheric structure, then regression residuals and AGCM experiments separate Pacific-internal and external-basin contributions."
  ],
  "source": "Current diagnostics establish association; ERA5/OLR/MJO and AGCM experiments are needed for mechanism attribution."
};
export async function slide15(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
