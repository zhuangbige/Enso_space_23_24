import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "历史对比总结",
  "t": "核心数值：2023 春夏不是海温不够强，而是大气响应没有跟上",
  "layout": "tableText",
  "rows": [
    [
      "指标",
      "AMJ",
      "JJA"
    ],
    [
      "Niño-3 海温相对历史强事件",
      "1.41 倍",
      "1.22 倍"
    ],
    [
      "中西太平洋低层风响应比",
      "-0.43 倍",
      "-0.14 倍"
    ],
    [
      "SOI-like 压力响应效率",
      "0.22",
      "0.28"
    ],
    [
      "中太平洋 GPCP 降水响应比",
      "0.43",
      "0.38"
    ]
  ],
  "text": "这些数值共同说明：2023 年发展季的海洋端已经足够强，但大气端没有产生历史强厄尔尼诺中常见的西风增强、气压梯度变化和降水东移。这就是本研究的核心诊断结果。",
  "src": "Tables: asynchronous_coupling_efficiency.csv; gpcp_precip_seasonal_summary.csv."
};
export async function slide17(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
