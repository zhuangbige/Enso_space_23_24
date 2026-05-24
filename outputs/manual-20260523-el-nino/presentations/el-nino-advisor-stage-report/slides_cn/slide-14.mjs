import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "与现有研究的区别",
  "title": "相关研究多解释某一机制或月份，本课题聚焦“多变量季节耦合效率”",
  "layout": "comparison",
  "table": [
    [
      "文献",
      "已有重点",
      "与本课题区别"
    ],
    [
      "Peng et al. 2025",
      "海洋动力生成强 El Niño",
      "本课题解释大气响应为何弱、何时开始弱"
    ],
    [
      "Zhang et al. 2025",
      "弱降水/遥相关与外海盆加热",
      "本课题把风压、降水、SST 做季节同步性矩阵"
    ],
    [
      "Kim et al. 2025",
      "发展季风场异常与西中太梯度",
      "本课题加入 SOI-like、GPCP 和外海盆历史对比"
    ],
    [
      "Zhao et al. 2025",
      "2023 年 7 月热带北大西洋 + 印度夏季风/海陆洲 heating",
      "本课题从 AMJ/JJA 到 SON/DJF 连续追踪"
    ],
    [
      "Yang & Li 2025",
      "2024 年 1 月季节内振荡 MJO / 趋势 / ENSO 分解",
      "本课题先建立发展季背景，再接入 MJO/OLR 机制拆解"
    ]
  ],
  "source": "Literature notes: docs/literature_method_notes.md; source IDs L2-L8 in docs/data_source_log.md.",
  "reader": "这页用于回答导师可能会问的“已有文章是否已经做过”。现有研究确实讨论了弱降水、遥相关、TNA、MJO 或某个关键月份；你的差异是把问题系统化为 AMJ/JJA/SON/DJF 的多变量耦合效率，并且明确与历史强事件对比。"
};
export async function slide14(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
