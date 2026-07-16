import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "原文复现 Fig. 3",
  "t": "图中数据名称：AGCM 海温强迫实验中的风应力响应",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "AGCM 即大气环流模式实验。原文把全球 SST、太平洋 SST、印度洋/大西洋 SST 等边界条件分开，比较大气风应力响应。"
    ],
    [
      "它反映了什么",
      "太平洋暖 SST 本应激发较强大气响应，但印度洋和大西洋背景可能提供相反或抵消作用。表格中 aPac 风应力为正，aIndAtl 风应力为负。"
    ],
    [
      "对应原文与我的创新",
      "对应原文外海盆调制思路。我的创新是先不用马上跑模式，而是用观测资料分季节诊断外海盆暖异常是否与弱大气响应同步出现。"
    ]
  ],
  "src": "Data: Peng et al. source archive; table fig3_agcm_summary.csv."
};
export async function slide09(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
