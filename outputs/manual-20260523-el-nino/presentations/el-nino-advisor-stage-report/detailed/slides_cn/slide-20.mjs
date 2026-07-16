import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "下一步数据",
  "t": "下一版研究图需要补什么数据",
  "layout": "tableText",
  "rows": [
    [
      "数据",
      "用途",
      "为什么需要"
    ],
    [
      "ERA5 pressure-level u850 / χ200",
      "补充低层风垂直层和 Walker 环流。",
      "single-level u10/SLP 已接入，pressure-level 环流仍是下一步。"
    ],
    [
      "ERA5 AMJ/JJA 空间图",
      "替换 NCEP fallback 风压空间图。",
      "让发展季风压证据进入论文级资料链。"
    ],
    [
      "ERSSTv5 / detrended SST",
      "长记录与去趋势稳健性。",
      "检查外海盆偏暖是否主要来自背景增暖趋势。"
    ],
    [
      "MJO/RMM 或日资料",
      "拆解 2024 年 1 月等关键月份。",
      "区分 ENSO 背景、MJO 和趋势影响。"
    ]
  ],
  "text": "短期优先级是把 ERA5 AMJ/JJA 风压空间图和 pressure-level Walker 环流补齐。AGCM 仍作为后续机制归因预案，而不是当前汇报的必要前提。",
  "src": "Data priorities from reports/当前数据分析阶段总结.md."
};
export async function slide20(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
