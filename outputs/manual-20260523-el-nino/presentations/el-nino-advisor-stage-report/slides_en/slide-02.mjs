import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Bottom Line",
  "title": "The work has moved from reproduction into first-layer original diagnostics",
  "layout": "thesis",
  "claim": "During AMJ/JJA 2023, Niño-3 SST had already reached a historically strong El Niño level, but central-western Pacific low-level wind, SOI-like pressure gradient, and rainfall responses did not intensify synchronously.",
  "notes": [
    "Paper contribution: Peng et al. show that ocean dynamics sustained the 2023/24 strong El Niño and that atmospheric feedbacks were weak.",
    "Our question: when did the weak atmospheric response first emerge, and which external basins or background states may have modulated coupling efficiency?",
    "Current finding: AMJ/JJA is the key window, with simultaneous warming over the TNA, Indian Ocean, Maritime Continent, and western Pacific warm pool.",
    "Thus the project is not merely repeating the paper; it uses the paper's ocean-dynamics result to ask why the atmospheric branch did not respond as expected."
  ],
  "source": "Current synthesis from reproduced paper figures and data/derived/research seasonal diagnostics."
};
export async function slide02(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
