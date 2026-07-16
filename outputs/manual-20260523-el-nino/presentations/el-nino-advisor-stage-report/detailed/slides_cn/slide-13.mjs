import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "新研究发现 1",
  "t": "图中数据名称：AMJ/JJA/SON/DJF 分季节回归预期响应矩阵",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/seasonal_regression_asynchrony_matrix.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "左图为 2023 年实际大气响应除以历史 Niño-3 回归关系给出的预期响应，分别计算 AMJ、JJA、SON、DJF。右图为外海盆 SST 相对历史强事件 composite 的差值。"
    ],
    [
      "它反映了什么",
      "AMJ/JJA 已经出现明显弱响应：ERA5 中西太平洋 u10 在 AMJ 为 -0.38、JJA 为 0.06；SOI-like、GPCP 降水和 CPC OLR 也均低于 1。"
    ],
    [
      "对应原文与我的创新",
      "原文在事件尺度比较 observed 与 expected response；本研究把同一逻辑季节化，并扩展到风压、降水和对流链条。"
    ]
  ],
  "src": "Tables: seasonal_regression_expected_response.csv; external_basin_seasonal_summary.csv."
};
export async function slide13(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
