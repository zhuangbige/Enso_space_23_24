import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Finding 4",
  "title": "External-basin warmth provides a background-state clue for developing-season asynchrony",
  "layout": "twoChartsTable",
  "leftImage": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/external_basin_bars.png",
  "rightImage": "/Users/daiyue/Documents/Maryland/data/derived/research/asynchronous_coupling_by_season.png",
  "figNote": "Data note: left chart uses OISST external-basin indices; right chart uses seasonal coupling efficiency. Both compare 2023 with the 1982/83, 1997/98, and 2015/16 strong-event composite. How to read: the left chart shows unusual spring-summer external-basin warmth, and the right chart shows low coupling efficiency. The next step is to test whether this is causal modulation or a shared background using ERA5/OLR/AGCM evidence.",
  "table": [
    [
      "Region / metric",
      "AMJ",
      "JJA"
    ],
    [
      "Tropical N. Atlantic TNA",
      "+1.11",
      "+1.35"
    ],
    [
      "W. Pacific warm pool WPWP",
      "+0.73",
      "+0.88"
    ],
    [
      "Maritime Continent MC",
      "+0.55",
      "+0.68"
    ],
    [
      "Tropical Indian Ocean TIO",
      "+0.44",
      "+0.40"
    ]
  ],
  "source": "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_by_season.png."
};
export async function slide13(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
