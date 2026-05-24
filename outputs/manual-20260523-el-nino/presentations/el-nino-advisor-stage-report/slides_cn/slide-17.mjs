import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "附录 A",
  "title": "图表与数据表对应关系",
  "layout": "appendixTable",
  "table": [
    [
      "页码",
      "图/结论",
      "对应数据表"
    ],
    [
      "5",
      "Fig.1 事件强度与耦合响应比",
      "fig1_event_coupling.csv"
    ],
    [
      "6",
      "Fig.2 赤道剖面/传播诊断",
      "fig2_equatorial_summary.csv"
    ],
    [
      "7",
      "Fig.3-4 AGCM 与风应力实验",
      "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"
    ],
    [
      "9",
      "OISST/GPCP/NCEP 独立验证",
      "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"
    ],
    [
      "10",
      "AMJ/JJA 历史耦合效率",
      "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"
    ],
    [
      "11-12",
      "AMJ/JJA 空间 SST/降水/风压",
      "stage_a_spatial_summary.csv"
    ],
    [
      "13",
      "外海盆暖异常与季节效率",
      "external_basin_seasonal_summary.csv"
    ]
  ],
  "source": "All paths are under /Users/daiyue/Documents/Maryland/data/derived."
};
export async function slide17(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
