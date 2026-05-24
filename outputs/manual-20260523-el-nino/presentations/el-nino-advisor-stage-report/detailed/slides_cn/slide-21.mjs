import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "附录 A",
  "t": "每页图对应的数据表",
  "layout": "appendix",
  "rows": [
    [
      "页码",
      "图/内容",
      "数据表"
    ],
    [
      "6-7",
      "原文 Fig. 1 与耦合响应比",
      "fig1_event_coupling.csv"
    ],
    [
      "8",
      "原文 Fig. 2 海洋动力诊断",
      "fig2_equatorial_summary.csv"
    ],
    [
      "9-10",
      "原文 Fig. 3-4 AGCM/风应力实验",
      "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"
    ],
    [
      "12",
      "公开资料验证",
      "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"
    ],
    [
      "13",
      "季节耦合效率矩阵",
      "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"
    ],
    [
      "14-15",
      "AMJ/JJA 空间图",
      "stage_a_spatial_summary.csv"
    ],
    [
      "16-17",
      "外海盆和历史对比",
      "external_basin_seasonal_summary.csv; gpcp_precip_seasonal_summary.csv"
    ]
  ],
  "src": "All local paths are under /Users/daiyue/Documents/Maryland/data/derived."
};
export async function slide21(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
