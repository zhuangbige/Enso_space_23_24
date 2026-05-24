import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Research Distinction",
  "title": "Related studies emphasize individual mechanisms or months; this project targets multi-variable seasonal coupling efficiency",
  "layout": "comparison",
  "table": [
    [
      "Study",
      "Existing focus",
      "How this project differs"
    ],
    [
      "Peng et al. 2025",
      "Ocean-dynamical generation of the strong El Niño",
      "Explains why and when the atmospheric response was weak"
    ],
    [
      "Zhang et al. 2025",
      "Weak rainfall/teleconnection response and external-basin heating",
      "Builds a seasonal matrix across wind, pressure, rainfall, and SST"
    ],
    [
      "Kim et al. 2025",
      "Developing-season wind anomalies and west-central Pacific gradients",
      "Adds SOI-like pressure, GPCP rainfall, and external-basin historical comparison"
    ],
    [
      "Zhao et al. 2025",
      "July 2023 Tropical North Atlantic plus Indian summer monsoon / Maritime Continent heating",
      "Tracks a continuous AMJ/JJA to SON/DJF evolution"
    ],
    [
      "Yang & Li 2025",
      "January 2024 Madden-Julian Oscillation MJO / trend / ENSO decomposition",
      "Builds the developing-season background before adding MJO/OLR mechanism tests"
    ]
  ],
  "source": "Literature notes: docs/literature_method_notes.md; source IDs L2-L8 in docs/data_source_log.md.",
  "reader": "This slide answers the likely advisor question of whether the topic has already been done. Existing papers discuss weak rainfall, teleconnections, TNA, MJO, or individual key months. The distinction here is to systematize the problem as seasonal, multi-variable coupling efficiency against historical strong El Niño events."
};
export async function slide14(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
