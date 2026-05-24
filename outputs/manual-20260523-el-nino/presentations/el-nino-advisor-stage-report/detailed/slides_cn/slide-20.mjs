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
      "ERA5 u850 / SLP / χ200",
      "替换 NCEP fallback，诊断低层风、海平面气压和 Walker 环流。",
      "论文级风压和环流证据需要更高质量再分析。"
    ],
    [
      "NOAA OLR",
      "独立验证深对流位置和强度。",
      "避免只依赖降水资料判断对流。"
    ],
    [
      "ERSSTv5",
      "做 1854 至今长记录稳健性。",
      "检查 OISST 1981 以后样本是否限制历史比较。"
    ],
    [
      "MJO/RMM 或日资料",
      "拆解 2024 年 1 月等关键月份。",
      "区分 ENSO 背景、MJO 和趋势影响。"
    ]
  ],
  "text": "短期优先级是 ERA5 和 OLR：先把风压、Walker 环流和对流证据补齐，再考虑 AGCM 模式实验。",
  "src": "Data priorities from reports/当前数据分析阶段总结.md."
};
export async function slide20(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
