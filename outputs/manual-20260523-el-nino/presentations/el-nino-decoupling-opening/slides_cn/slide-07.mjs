import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "新研究内容",
  "title": "外海盆 OISST 指数显示：2023 春夏热带背景态异常偏暖",
  "layout": "chartTable",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/external_basin_bars.png",
  "table": [
    [
      "区域",
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
