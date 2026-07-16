import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "核心数值",
  "t": "2023 春夏不是海温驱动弱，而是大气响应低于历史回归预期",
  "layout": "tableText",
  "rows": [
    [
      "指标",
      "AMJ",
      "JJA"
    ],
    [
      "Niño-3 海温异常，作为回归预测因子",
      "0.97°C",
      "1.73°C"
    ],
    [
      "ERA5 中西太平洋 u10 实际/预期",
      "-0.38",
      "0.06"
    ],
    [
      "ERA5 SOI-like 海平面气压实际/预期",
      "0.56",
      "0.41"
    ],
    [
      "GPCP 中太平洋降水实际/预期",
      "0.35",
      "0.46"
    ],
    [
      "CPC 中太平洋 OLR 实际/预期",
      "0.17",
      "0.26"
    ]
  ],
  "text": "每个季节分别用历史 Niño-3 海温异常和大气变量异常建立回归关系，由此得到 2023 年在该海温强度下应有的大气响应。数值低于 1 表示弱于历史回归预期；小于 0 表示响应方向相反。",
  "src": "Table: seasonal_regression_expected_response.csv. Data: OISST Niño-3, ERA5 u10/SLP, GPCP precipitation, CPC blended OLR."
};
export async function slide17(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
