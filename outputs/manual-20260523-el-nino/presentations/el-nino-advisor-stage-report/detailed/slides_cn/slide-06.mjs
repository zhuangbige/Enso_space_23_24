import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "原文复现 Fig. 1",
  "t": "图中数据名称：SST、海平面气压/10米风、Niño-3 与大气响应散点",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "Peng et al. Fig. 1 的源数据。上半部分是 2023/24 与历史强事件的海表温度、海平面气压和 10 米风异常；下半部分是 Niño-3 海温与 u10、SOI 的历史关系。"
    ],
    [
      "它反映了什么",
      "2023/24 的 Niño-3 海温很强，但对应的近地面风和气压响应偏弱，说明海洋强度和大气响应强度没有按历史经验同步增长。"
    ],
    [
      "对应原文与我的创新",
      "对应原文的核心事实复现。创新不是这页本身，而是后续把这个全年/成熟期事实拆到 AMJ/JJA 发展前期，追问弱响应何时开始。"
    ]
  ],
  "src": "Data: Peng et al. source archive; local file Fig1.png; table fig1_event_coupling.csv."
};
export async function slide06(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
