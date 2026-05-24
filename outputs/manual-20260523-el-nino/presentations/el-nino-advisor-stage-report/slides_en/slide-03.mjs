import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Storyline",
  "title": "Deck structure: reproduce the paper, then isolate the developing-season coupling failure",
  "layout": "flow",
  "steps": [
    "Paper reproduction\nFig. 1-4",
    "Raw validation\nOISST/GPCP/NCEP",
    "Developing-season comparison\nAMJ/JJA",
    "Research distinction\nFrom genesis to response timing"
  ],
  "notes": [
    "Every figure slide includes a data note; appendices map slides to tables and source links.",
    "For an advisor reading the deck offline, this slide is the roadmap: the first half establishes reliability, and the second half defines the new research space."
  ],
  "source": "Workflow recorded in reports/当前数据分析阶段总结.md and docs/data_source_log.md."
};
export async function slide03(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
