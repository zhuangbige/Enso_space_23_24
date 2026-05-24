import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "原文贡献与缺口",
  "title": "原文回答了“强 El Niño 如何生成”，但留下“何时、为何脱耦”的问题",
  "layout": "comparison",
  "table": [
    [
      "维度",
      "Peng et al. 2025 的贡献",
      "本课题延伸"
    ],
    [
      "主问题",
      "强 2023/24 El Niño 的海洋动力生成",
      "发展季大气响应为何未同步"
    ],
    [
      "主要证据",
      "海洋热含量、赤道传播、风应力实验",
      "海表温度-风压-降水-对流的季节耦合效率"
    ],
    [
      "时间尺度",
      "事件生成与成熟期",
      "AMJ/JJA/SON/DJF 不等时响应"
    ],
    [
      "机制候选",
      "太平洋海洋动力与外海盆 SST 影响",
      "TNA、印度洋、海陆洲、西太暖池背景态调制"
    ]
  ],
  "source": "Synthesis of L1 and current diagnostics; citations listed in final appendix.",
  "reader": "这页的作用是把原文贡献和你的研究空间分开：原文主要回答“强事件如何被海洋过程生成”，你的题目转向“强海温出现后，大气响应为什么不按历史同步发生”。因此后续分析必须分季节、分变量，而不能只看全年平均。"
};
export async function slide08(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
