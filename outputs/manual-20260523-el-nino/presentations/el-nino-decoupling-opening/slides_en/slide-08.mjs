import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Proposed Topic",
  "title": "Working title: Extra-Pacific warming as a modulator of atmosphere-ocean decoupling during the 2023/24 El Niño",
  "layout": "hypothesis",
  "hypothesis": [
    "H1: Spring-summer external-basin warmth altered the Walker background state and weakened central-Pacific westerly response.",
    "H2: Maritime Continent / Indian Ocean warmth maintained local convection and limited the canonical eastward rainfall shift.",
    "H3: Tropical North Atlantic warmth or tropical-mean warming raised the threshold for a Pacific-driven atmospheric response."
  ],
  "question": "Core question: when Pacific SST is already sufficiently warm, how do external basins and background warming change coupling efficiency?",
  "source": "Interpretation based on reproduction + raw validation + external-basin diagnostics."
};
export async function slide08(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
