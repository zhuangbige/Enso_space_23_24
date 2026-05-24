import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "新研究发现 1",
  "t": "图中数据名称：AMJ/JJA/SON/DJF 季节耦合效率矩阵",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/seasonal_asynchrony_figure.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "OISST Niño-3、NCEP 中西太平洋低层风、SOI-like 海平面气压梯度、GPCP 降水等指标，按季节与 1982/83、1997/98、2015/16 强事件平均比较。"
    ],
    [
      "它反映了什么",
      "AMJ/JJA 的 Niño-3 海温比历史强事件还强或相当强，但风压和降水响应效率很低。AMJ CWP 风响应比约 -0.43，JJA 约 -0.14。"
    ],
    [
      "对应原文与我的创新",
      "原文指出 2023/24 总体弱耦合；我的创新是定位到发展前期，并用历史强事件作基准定量说明哪些变量最先不同步。"
    ]
  ],
  "src": "Tables: asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv."
};
export async function slide13(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
