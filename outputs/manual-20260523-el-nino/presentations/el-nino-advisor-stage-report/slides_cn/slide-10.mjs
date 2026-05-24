import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "阶段性发现 1",
  "title": "历史对比显示：春季 AMJ / 夏季 JJA 的海温已强，但同步风压响应失效",
  "layout": "imageTable",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/seasonal_asynchrony_figure.png",
  "figNote": "数据说明：OISST Niño-3、NCEP CWP u proxy 与 SOI-like SLP gradient；相对 1982/83、1997/98、2015/16 strong-El Niño composite。 读图要点：如果只看 Niño-3，AMJ/JJA 2023 已经很像强 El Niño；但 CWP u 和 SOI-like 指标没有同步增强，甚至低层风响应反向。这就是目前最核心的新发现。",
  "table": [
    [
      "指标",
      "AMJ",
      "JJA"
    ],
    [
      "Niño-3 SST 比值",
      "1.41",
      "1.22"
    ],
    [
      "中西太平洋 CWP 风比值",
      "-0.43",
      "-0.14"
    ],
    [
      "SOI-like 效率",
      "0.22",
      "0.28"
    ],
    [
      "CP 降水比值",
      "0.43",
      "0.38"
    ]
  ],
  "source": "Tables: asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv."
};
export async function slide10(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
