import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "独立验证",
  "title": "用公开原始资料重算后，论文级信号仍然成立",
  "layout": "chartText",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/validation_summary.png",
  "notes": [
    "OISST 重新计算 Niño-3，与原文 Fig.1 相关 0.9999。",
    "GPCP 显示 2023/24 中东太平洋降水低于强厄尔尼诺 composite。",
    "NCEP 风和 SOI-like proxy 与原文大气指标高度一致。"
  ],
  "source": "Raw validation: NOAA PSL OPeNDAP OISST/GPCP/NCEP outputs in data/derived/raw_validation."
};
export async function slide05(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
