import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "原文复现 Fig. 2",
  "t": "图中数据名称：赤道太平洋传播、次表层热结构和海洋动力诊断",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig2.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "Peng et al. Fig. 2 的赤道剖面和时间-经度诊断，展示海温、次表层热异常、传播特征和风应力相关信号。"
    ],
    [
      "它反映了什么",
      "原文用这组图证明 2023/24 强海温不是偶然表层变暖，而是受到赤道太平洋海洋动力过程支持。"
    ],
    [
      "对应原文与我的创新",
      "对应原文的海洋动力归因部分。本研究接受这个结论，并把研究焦点转向：既然海洋端足够强，为什么大气端没有同步跟上？"
    ]
  ],
  "src": "Data: Peng et al. source archive; local Fig2.png; table fig2_equatorial_summary.csv."
};
export async function slide08(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
