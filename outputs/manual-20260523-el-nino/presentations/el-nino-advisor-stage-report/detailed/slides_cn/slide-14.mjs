import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "新研究发现 2",
  "t": "图中数据名称：AMJ/JJA 海表温度和 GPCP 降水空间异常",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_sst_precip.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "上排是 OISST 海表温度，下面是 GPCP 降水。每个格点都是 2023 AMJ/JJA 减去历史强厄尔尼诺 composite。"
    ],
    [
      "它反映了什么",
      "2023 春夏不只是东太平洋暖，热带北大西洋、海陆洲和西太暖池也显著偏暖；但中东太平洋降水没有同步增强，甚至相对历史强事件偏弱。"
    ],
    [
      "对应原文与我的创新",
      "对应原文关于外海盆 SST 可能调制响应的提示。我的创新是给出发展季空间证据，说明外海盆暖背景和弱降水响应同时出现。"
    ]
  ],
  "src": "Data: NOAA OISST v2.1 and GPCP; summary table stage_a_spatial_summary.csv."
};
export async function slide14(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
