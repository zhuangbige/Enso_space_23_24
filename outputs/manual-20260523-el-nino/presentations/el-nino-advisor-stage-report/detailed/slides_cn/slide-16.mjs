import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "新研究发现 4",
  "t": "图中数据名称：外海盆暖异常指数与季节耦合效率",
  "layout": "twoFigureExplain",
  "left": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/external_basin_bars.png",
  "right": "/Users/daiyue/Documents/Maryland/data/derived/research/asynchronous_coupling_by_season.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "左图是 OISST 计算的热带北大西洋、西太暖池、海陆洲和热带印度洋海温差值；右图是季节耦合效率指标。"
    ],
    [
      "它反映了什么",
      "2023 春夏外海盆和西太暖池明显偏暖，同时太平洋大气耦合效率偏低。二者在时间上共同出现，是后续机制分析的重点线索。"
    ],
    [
      "对应原文与我的创新",
      "原文用 AGCM 提示外海盆可能抵消太平洋响应；我的创新是先用观测资料确认 2023 发展季外海盆暖异常的空间和季节存在。"
    ]
  ],
  "src": "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_efficiency.csv."
};
export async function slide16(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
