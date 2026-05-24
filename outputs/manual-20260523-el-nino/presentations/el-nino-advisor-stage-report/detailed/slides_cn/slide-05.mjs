import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "原文贡献",
  "t": "Peng et al. 2025 主要回答了：强 2023/24 El Niño 是怎样生成的",
  "layout": "tableText",
  "rows": [
    [
      "层面",
      "原文结论",
      "对本研究的作用"
    ],
    [
      "海洋端",
      "赤道太平洋海洋动力和热含量过程使 2023/24 事件变强。",
      "提供了“海温为什么强”的基础。"
    ],
    [
      "大气端",
      "相对于历史强厄尔尼诺，大气风压反馈偏弱。",
      "引出“强海温为何没有强响应”的问题。"
    ],
    [
      "外海盆",
      "印度洋和大西洋 SST 可能抵消部分太平洋强迫。",
      "提示外海盆背景态可能是机制切口。"
    ],
    [
      "模式实验",
      "AGCM 和风应力实验区分了海温边界和风场强迫。",
      "为后续设计 Pacific-only / external-basin 实验提供模板。"
    ]
  ],
  "text": "所以，我不是推翻原文，而是在原文基础上把问题往大气耦合端推进：原文解释了强海温的生成，本研究解释强海温为什么没有带来同步的大气响应。",
  "src": "L1: Peng et al. 2025 Nature Geoscience."
};
export async function slide05(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
