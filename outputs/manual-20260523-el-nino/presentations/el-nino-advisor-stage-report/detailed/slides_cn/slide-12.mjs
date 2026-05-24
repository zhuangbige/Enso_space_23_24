import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "独立资料验证",
  "t": "图中数据名称：OISST、GPCP、NCEP/NCAR 对原文指标的再计算",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/validation_summary.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "OISST 是 NOAA 海表温度资料，GPCP 是全球降水资料，NCEP/NCAR R1 是再分析风压资料。图中显示它们与复现指标的相关或一致性。"
    ],
    [
      "它反映了什么",
      "OISST Niño-3 与原文复现相关 0.9999；NCEP 风和类 SOI 压力梯度也高度一致。这说明核心事实不是单一论文数据集造成的。"
    ],
    [
      "对应原文与我的创新",
      "对应原文 Fig. 1-2 的外部资料验证。创新是把复现结果转为公开数据链条，为后续自己的季节诊断建立可追溯基础。"
    ]
  ],
  "src": "Tables: oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv."
};
export async function slide12(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
