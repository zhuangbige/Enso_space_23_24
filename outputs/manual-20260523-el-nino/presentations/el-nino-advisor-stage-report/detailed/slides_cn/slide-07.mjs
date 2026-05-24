import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "复现数值化 Fig. 1",
  "t": "图中数据名称：u10 和 SOI 相对历史强事件的响应比",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/coupling_ratios.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "从 fig1_event_coupling.csv 提取的事件指标。Niño-3 表示海温强度，u10 表示 10 米纬向风，SOI 表示南方涛动指数。"
    ],
    [
      "它反映了什么",
      "2023 年 u10 响应比约 0.27，SOI 响应比约 0.31，即大气响应只有历史强厄尔尼诺期望值的大约三分之一。"
    ],
    [
      "对应原文与我的创新",
      "对应原文 Fig. 1 的“强海温、弱大气”结论。我的创新是把这个比值思想扩展成季节耦合效率矩阵，而不是只做全年单点对比。"
    ]
  ],
  "src": "Derived table: data/derived/peng2025_repro/tables/fig1_event_coupling.csv."
};
export async function slide07(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
