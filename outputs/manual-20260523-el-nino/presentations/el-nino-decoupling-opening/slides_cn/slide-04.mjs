import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "原文归因",
  "title": "原文的 AGCM 和风应力实验提示：海洋动力强，但大气端响应不足",
  "layout": "twoImagesTable",
  "leftImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.png",
  "rightImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.png",
  "tableTitle": "原文表格化摘录",
  "table": [
    [
      "指标",
      "数值"
    ],
    [
      "Fig.3 aPac taux",
      "0.0333"
    ],
    [
      "Fig.3 aIndAtl taux",
      "-0.0099"
    ],
    [
      "Fig.4 Dec Niño-3 CTRL",
      "2.344"
    ],
    [
      "Fig.4 Dec Niño-3 Wind2023",
      "0.681"
    ]
  ],
  "source": "Paper reproduction tables: fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv."
};
export async function slide04(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
