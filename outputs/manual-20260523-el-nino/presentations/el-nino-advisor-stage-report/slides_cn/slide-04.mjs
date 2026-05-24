import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "术语先说明",
  "title": "本汇报常用缩写：先把气象量和数据集讲清楚",
  "layout": "glossary",
  "table": [
    [
      "缩写",
      "全称/中文",
      "在本研究中的含义"
    ],
    [
      "SST",
      "Sea Surface Temperature，海表温度",
      "判断厄尔尼诺海洋增暖强度的核心变量。"
    ],
    [
      "Niño-3",
      "东赤道太平洋海温区",
      "通常取 5°S-5°N、150°W-90°W；本研究用它代表东太平洋增暖。"
    ],
    [
      "u10 / u850",
      "10 米 / 850 hPa 纬向风",
      "东西向风；正值常代表西风异常，能推动暖水东传和海气耦合。"
    ],
    [
      "SOI / SLP",
      "南方涛动指数 / 海平面气压",
      "SOI 反映东西太平洋气压跷跷板；SLP 用于构造类 SOI 压力梯度。"
    ],
    [
      "OLR / χ200",
      "向外长波辐射 / 200 hPa 速度势",
      "OLR 用于判断深对流强弱；χ200 用于诊断 Walker 环流上层辐散。"
    ],
    [
      "AMJ/JJA/SON/DJF",
      "4-6月 / 6-8月 / 9-11月 / 12-2月",
      "按季节拆解 2023/24 事件，重点看发展前期 AMJ 和 JJA。"
    ],
    [
      "OISST/GPCP/NCEP",
      "NOAA 海温 / 全球降水 / NCEP 再分析",
      "当前已使用的公开验证资料；ERA5 和 OLR 是下一步补充。"
    ],
    [
      "TNA/MC/WPWP/TIO",
      "热带北大西洋 / 海陆洲 / 西太暖池 / 热带印度洋",
      "用于描述外海盆和热带背景态异常。"
    ]
  ],
  "reader": "阅读建议：后面每页会尽量先写中文全称，再写缩写。若只记一条主线，就是：海表温度很强，但风、气压、降水和对流没有同步给出历史强厄尔尼诺式响应。",
  "source": "Definitions follow standard climate diagnostics; variable usage follows docs/data_source_log.md and local analysis scripts."
};
export async function slide04(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
