import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Seasonal Split",
  "title": "The key opening: 2023 AMJ/JJA Niño-3 was not weak, yet atmospheric coupling was already suppressed",
  "layout": "chartTable",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/seasonal_decoupling.png",
  "table": [
    [
      "Metric",
      "AMJ diff.",
      "JJA diff."
    ],
    [
      "Niño-3 SST",
      "+0.282",
      "+0.309"
    ],
    [
      "CWP u proxy",
      "-2.301",
      "-2.576"
    ],
    [
      "SOI-like proxy",
      "+1.133",
      "+1.551"
    ]
  ],
  "source": "Seasonal table: data/derived/research/seasonal_decoupling_first_pass.csv."
};
export async function slide06(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
