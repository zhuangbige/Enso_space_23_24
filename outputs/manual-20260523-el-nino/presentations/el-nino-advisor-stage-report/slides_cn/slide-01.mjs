import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "导师阶段汇报",
  "title": "2023/24 强厄尔尼诺海气脱耦：从原文复现到发展季不同步响应",
  "subtitle": "主线：强海温事件为何没有激发同等强度的风压、降水和对流响应？",
  "layout": "cover",
  "bullets": [
    "复现 Peng et al. 2025 的核心图和关键数值。",
    "在公开资料中验证“海温强、大气弱”。",
    "把全年结论推进到 AMJ/JJA 发展前期的历史对比。"
  ],
  "source": "Peng et al. 2025; NOAA OISST v2.1; GPCP; NCEP/NCAR R1. 汇报日期：2026-05-23。"
};
export async function slide01(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
