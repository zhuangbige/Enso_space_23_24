import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Logic Chain",
  "title": "The project moves from reproducing the paper to isolating a spring-summer coupling failure",
  "layout": "flow",
  "steps": [
    "Paper reproduction\nFig. 1-4",
    "Raw-product checks\nOISST / GPCP / NCEP",
    "Seasonal split\nAMJ-JJA decoupling",
    "New question\nCan extra-Pacific warmth damp coupling?"
  ],
  "notes": [
    "Reproduction turns the paper's qualitative claim into a measurable coupling residual.",
    "The PhD-level opening is seasonal: Pacific SST was already warm, but the atmosphere did not respond normally."
  ],
  "source": "Derived workflow in reports/阶段性中文报告.md."
};
export async function slide02(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
