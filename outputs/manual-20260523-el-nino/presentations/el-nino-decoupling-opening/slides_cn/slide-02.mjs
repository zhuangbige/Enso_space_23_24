import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "逻辑链",
  "title": "先复现核心事实，再把“全年脱耦”拆成春夏的机制问题",
  "layout": "flow",
  "steps": [
    "原文复现\nFig.1-4",
    "原始数据验证\nOISST / GPCP / NCEP",
    "季节分解\nAMJ-JJA 提前脱耦",
    "新研究问题\n外海盆暖背景是否抑制耦合？"
  ],
  "notes": [
    "复现不是终点，而是把论文的定性判断变成可检验指标。",
    "博士课题切口：春夏阶段，太平洋已变暖，但大气反馈没有跟上。"
  ],
  "source": "Derived workflow in /reports/阶段性中文报告.md."
};
export async function slide02(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
