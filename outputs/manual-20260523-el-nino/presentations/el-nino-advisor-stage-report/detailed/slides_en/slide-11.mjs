import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "From Paper To Question",
  "t": "Open gap: when did weak coupling appear, and was it linked to the external-basin background?",
  "layout": "text",
  "claim": "Saying that the 2023/24 atmospheric response was weak is not enough for a new paper. We need to know whether weak coupling emerged during development, maturity, or throughout the event.",
  "points": [
    "Peng et al. focuses mainly on event generation and ocean dynamics; seasonal wind-pressure-rainfall-convection asynchrony remains less systematically developed.",
    "This project separates SST, low-level wind, sea-level pressure, rainfall, OLR, and Walker circulation across AMJ/JJA/SON/DJF.",
    "That turns a broad weak-response statement into a testable seasonal coupling-efficiency problem."
  ],
  "src": "Research transition based on L1 and local seasonal diagnostics."
};
export async function slide11(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
