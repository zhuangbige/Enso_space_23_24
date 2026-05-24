import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "原文复现 2",
  "title": "Peng et al. Fig. 2：原文将强事件归因到赤道太平洋海洋动力过程",
  "layout": "fullImage",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig2.png",
  "figNote": "数据说明：Peng et al. 2025 source archive Fig. 2 数据；本地表 fig2_equatorial_summary.csv。该图用于支撑原文的海洋动力解释，包括赤道传播、次表层热含量和风应力相关诊断。 读图要点：这页不是你的新机制，而是原文的基础归因。它告诉我们强海温可以由海洋动力解释，但并没有解释为什么春夏早期风压和降水没有同步放大。",
  "source": "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig2.png."
};
export async function slide06(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
