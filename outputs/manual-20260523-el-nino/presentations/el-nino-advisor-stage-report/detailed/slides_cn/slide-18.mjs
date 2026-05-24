import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "与现有研究区别",
  "t": "已有研究解释单个机制或月份，本研究系统化为季节耦合效率问题",
  "layout": "tableText",
  "rows": [
    [
      "文献",
      "已有重点",
      "本研究新增"
    ],
    [
      "Peng et al. 2025",
      "海洋动力生成强事件",
      "解释大气响应为何弱、何时弱。"
    ],
    [
      "Zhang et al. 2025",
      "弱降水/遥相关与外海盆加热",
      "将风、气压、降水、SST 做季节矩阵。"
    ],
    [
      "Kim et al. 2025",
      "发展季风场与西中太梯度",
      "加入 SOI-like、GPCP 和外海盆历史对比。"
    ],
    [
      "Zhao et al. 2025",
      "2023 年 7 月 TNA 和季风/海陆洲加热",
      "从 AMJ/JJA 到 SON/DJF 连续追踪。"
    ],
    [
      "Yang & Li 2025",
      "2024 年 1 月 MJO/trend/ENSO 分解",
      "先建立发展季背景，再接入 MJO/OLR。"
    ]
  ],
  "text": "因此，本研究的差异不是只提出一个新的资料集，而是把“弱响应”拆成时间维度和变量维度：哪一季开始弱、哪个变量最先弱、外海盆背景是否同步异常。",
  "src": "Literature notes: docs/literature_method_notes.md; source IDs L2-L8."
};
export async function slide18(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
