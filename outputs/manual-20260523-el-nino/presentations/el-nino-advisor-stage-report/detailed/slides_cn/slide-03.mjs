import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "术语先说明",
  "t": "本报告常见缩写和变量",
  "layout": "glossary",
  "rows": [
    [
      "缩写",
      "全称",
      "本研究中的意思"
    ],
    [
      "SST",
      "海表温度",
      "判断厄尔尼诺海洋增暖强度。"
    ],
    [
      "Niño-3",
      "东赤道太平洋海温区",
      "代表东太平洋暖异常，常用于描述厄尔尼诺强度。"
    ],
    [
      "u10 / u850",
      "10 米 / 850 hPa 纬向风",
      "东西向风；西风异常可加强海气耦合。"
    ],
    [
      "SOI / SLP",
      "南方涛动指数 / 海平面气压",
      "衡量东西太平洋气压跷跷板和 Walker 环流响应。"
    ],
    [
      "OLR / χ200",
      "向外长波辐射 / 200 hPa 速度势",
      "分别反映深对流和上层大尺度环流。"
    ],
    [
      "AMJ/JJA",
      "4-6月 / 6-8月",
      "本研究重点的发展前期季节。"
    ],
    [
      "TNA/MC/WPWP/TIO",
      "热带北大西洋/海陆洲/西太暖池/热带印度洋",
      "外海盆和热带背景态重点区域。"
    ]
  ],
  "src": "Standard climate diagnostics and docs/data_source_log.md."
};
export async function slide03(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
