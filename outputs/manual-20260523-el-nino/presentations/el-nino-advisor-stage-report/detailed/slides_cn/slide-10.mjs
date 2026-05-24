import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "原文复现 Fig. 4",
  "t": "图中数据名称：风应力实验对 Niño-3 海温发展的影响",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "原文风应力实验，比较不同风场设定下 Niño-3 海温的发展。关键数值包括 Dec Niño-3 CTRL=2.344，Wind2023=0.681。"
    ],
    [
      "它反映了什么",
      "2023 年实际风场并没有像典型强厄尔尼诺那样强力推动海温增长，说明大气风强迫本身偏弱。"
    ],
    [
      "对应原文与我的创新",
      "对应原文“2023 风场偏弱”的实验佐证。我的创新是把这个偏弱风场进一步定位到 AMJ/JJA 发展季，并与降水、气压一起比较。"
    ]
  ],
  "src": "Data: Peng et al. source archive; table fig4_wind_experiment_summary.csv."
};
export async function slide10(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
