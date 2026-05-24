import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "季节分解",
  "title": "关键新切口：2023 年 AMJ/JJA Niño-3 不弱，但大气响应已经显著偏弱",
  "layout": "chartTable",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/seasonal_decoupling.png",
  "table": [
    [
      "指标",
      "AMJ 差值",
      "JJA 差值"
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
