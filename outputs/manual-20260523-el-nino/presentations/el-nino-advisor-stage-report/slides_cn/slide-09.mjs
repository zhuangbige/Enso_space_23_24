import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "独立资料验证",
  "title": "公开资料重算表明：原文的核心事实不是单一数据集产物",
  "layout": "imageBrief",
  "image": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/validation_summary.png",
  "figNote": "数据说明：OISST、GPCP、NCEP/NCAR R1 公开资料；对应表 oisst_vs_fig1_nino3.csv, gpcp_vs_fig2_precip.csv, ncep_vs_fig1_atmosphere.csv。 读图要点：OISST 验证海温，GPCP 验证降水，NCEP 作为风压 fallback。三类独立资料方向一致，说明“海温强、大气弱”不是原文源数据的偶然结果。",
  "bullets": [
    "NOAA 最优插值海表温度 OISST 的 Niño-3 与复现 Fig. 1 相关 0.9999。",
    "全球降水气候计划 GPCP 显示 2023 中东太平洋降水弱于强事件 composite。",
    "NCEP/NCAR 再分析风和类 SOI 压力梯度与原文大气指标高度一致。"
  ],
  "source": "D2 NOAA OISST; D3 GPCP; D4 NCEP/NCAR R1 via NOAA PSL OPeNDAP."
};
export async function slide09(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
