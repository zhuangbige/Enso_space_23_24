import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "逻辑链条",
  "title": "汇报结构：复现文章结论，再提出发展季耦合失效问题",
  "layout": "flow",
  "steps": [
    "原文复现\nFig. 1-4",
    "原始资料验证\nOISST/GPCP/NCEP",
    "发展季历史对比\nAMJ/JJA",
    "研究差异\n从成因到响应时序"
  ],
  "notes": [
    "每个有图页面都在图下标注数据来源；附录给出数据表格与链接。",
    "给导师阅读时，可以把这页看作全文路线图：前半部分证明基础事实可靠，后半部分说明你的新问题从哪里来。"
  ],
  "source": "Workflow recorded in reports/当前数据分析阶段总结.md and docs/data_source_log.md."
};
export async function slide03(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
