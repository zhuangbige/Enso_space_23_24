import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "下一步",
  "title": "下一阶段优先补足 ERA5 与 OLR，把“现象”推进到“机制检验”",
  "layout": "roadmap",
  "steps": [
    "ERA5 u850/SLP/χ200\n替换 NCEP fallback",
    "NOAA OLR + GPCP\n独立验证对流中心",
    "ERSSTv5 长记录\n检查历史样本稳健性",
    "AGCM 大气模式预案\nPacific-only / IO-ATL / detrended"
  ],
  "notes": [
    "当前可以开始你的研究主线：先写作“发展季耦合效率丧失”的诊断论文框架，再用 ERA5/OLR 强化机制证据。",
    "短期优先级不是马上跑模式，而是把 ERA5 u850/SLP/χ200 与 OLR 接入，使风压、Walker 环流和对流证据达到论文级可靠性。"
  ],
  "source": "Data priorities from reports/当前数据分析阶段总结.md."
};
export async function slide16(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
