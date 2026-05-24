import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "导师阅读版",
  "t": "2023/24 强厄尔尼诺海气脱耦：复现、问题提出与阶段性创新",
  "layout": "cover",
  "sub": "目标：让不熟悉该方向的读者也能看懂每张图的数据来源、物理含义、与原文关系和本研究新增内容。",
  "bullets": [
    "先解释缩写和变量，避免直接进入专业简称。",
    "每张图都写明：数据名称、反映了什么、对应原文什么、我的创新在哪里。",
    "字体和图注加大，牺牲一点页数，换取可独立阅读性。"
  ],
  "src": "Peng et al. 2025; NOAA OISST; GPCP; NCEP/NCAR R1; local diagnostics. 2026-05-24."
};
export async function slide01(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
