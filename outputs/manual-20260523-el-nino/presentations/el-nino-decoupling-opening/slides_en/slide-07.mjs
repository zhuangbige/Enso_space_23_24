import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "New Diagnostic",
  "title": "External-basin OISST indices show unusually warm tropical background conditions in spring-summer 2023",
  "layout": "chartTable",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/external_basin_bars.png",
  "table": [
    [
      "Region",
      "AMJ",
      "JJA"
    ],
    [
      "Tropical N. Atlantic",
      "+1.110",
      "+1.350"
    ],
    [
      "W. Pacific warm pool",
      "+0.726",
      "+0.881"
    ],
    [
      "Maritime Continent",
      "+0.547",
      "+0.677"
    ],
    [
      "Tropical Indian Ocean",
      "+0.438",
      "+0.401"
    ]
  ],
  "source": "New diagnostic: OISST external-basin indices, 2023 minus 1982/1997/2015 composite."
};
export async function slide07(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
