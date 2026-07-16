import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "与现有研究区别",
  "t": "已有研究解释单个机制或月份，本研究把原文预期响应逻辑系统化到季节尺度",
  "layout": "tableText",
  "rows": [
    [
      "文献",
      "已有重点",
      "本研究新增"
    ],
    [
      "Peng et al. 2025",
      "海洋动力生成强事件；事件尺度风场/SOI 弱响应",
      "将 observed/expected response 从事件尺度扩展到 AMJ/JJA/SON/DJF。"
    ],
    [
      "Zhang et al. 2025",
      "弱降水/遥相关与外海盆加热",
      "把降水弱响应放入风压-降水-对流的同一季节矩阵。"
    ],
    [
      "Kim et al. 2025",
      "发展季风场与西中太梯度",
      "加入 SOI-like 气压、GPCP 降水、CPC OLR 和回归预期比较。"
    ],
    [
      "Zhao et al. 2025",
      "2023 年 7 月 TNA 和季风/海陆洲加热",
      "将单月机制扩展为 AMJ-JJA 发展季建立窗口。"
    ],
    [
      "Yang & Li 2025",
      "2024 年 1 月 MJO/trend/ENSO 分解",
      "在日尺度 MJO/OLR 机制前，先建立发展季背景诊断。"
    ]
  ],
  "text": "因此，本研究的差异不是只多加一个资料集，而是把“弱响应”拆成时间维度和变量链条：哪一季开始低于预期、哪个变量最先不同步、外海盆暖背景是否同步异常。",
  "src": "Literature notes: docs/literature_method_notes.md; source IDs L1-L8; main diagnostic table: seasonal_regression_expected_response.csv."
};
export async function slide18(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
