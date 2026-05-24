import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "原文复现 3",
  "title": "Peng et al. Fig. 3-4：外海盆海表温度和 2023 年风场均削弱典型响应",
  "layout": "twoImagesTable",
  "leftImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.png",
  "rightImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.png",
  "figNote": "数据说明：Peng et al. 2025 source archive Fig. 3-4 数据；本地表 fig3_agcm_summary.csv 与 fig4_wind_experiment_summary.csv。 读图要点：aPac 代表太平洋 SST 对大气风应力的典型驱动，aIndAtl 为印度洋和大西洋背景的外海盆影响。外海盆项为负，说明它可能抵消太平洋暖 SST 的大气响应。",
  "tableTitle": "关键摘录",
  "table": [
    [
      "指标",
      "值"
    ],
    [
      "aPac 风应力",
      "0.0333"
    ],
    [
      "aIndAtl 风应力",
      "-0.0099"
    ],
    [
      "Dec Niño-3 CTRL",
      "2.344"
    ],
    [
      "Dec Niño-3 Wind2023",
      "0.681"
    ]
  ],
  "source": "L1 Peng et al. 2025; reproduction tables in data/derived/peng2025_repro/tables."
};
export async function slide07(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
