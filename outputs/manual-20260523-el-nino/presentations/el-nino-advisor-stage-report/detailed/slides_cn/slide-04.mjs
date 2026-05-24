import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "术语先说明 2",
  "t": "数据集、模式实验和区域缩写",
  "layout": "glossary",
  "rows": [
    [
      "缩写",
      "全称",
      "本研究中的意思"
    ],
    [
      "NOAA",
      "美国国家海洋和大气管理局",
      "OISST、OLR 等资料的重要发布机构。"
    ],
    [
      "NCEP/NCAR R1",
      "NCEP/NCAR 第一代再分析",
      "当前低层风和海平面气压的 fallback 验证资料。"
    ],
    [
      "ERA5",
      "ECMWF 第五代再分析",
      "下一步用于论文级 u850、SLP 和 Walker 环流诊断。"
    ],
    [
      "ERSSTv5",
      "扩展重建海表温度第 5 版",
      "用于长记录历史强厄尔尼诺稳健性检查。"
    ],
    [
      "AGCM",
      "大气环流模式",
      "用规定海表温度作为边界条件，检验大气响应来源。"
    ],
    [
      "ENSO",
      "厄尔尼诺-南方涛动",
      "El Niño 和 La Niña 所属的热带太平洋海气耦合系统。"
    ],
    [
      "CWP",
      "中西太平洋",
      "本研究中低层风响应的关键区域。"
    ],
    [
      "MJO/RMM",
      "Madden-Julian Oscillation / Real-time Multivariate MJO index",
      "用于后续区分季节内振荡对关键月份的影响。"
    ],
    [
      "CTRL",
      "Control experiment，控制实验",
      "模式实验中的基准组，用于和敏感性实验比较。"
    ]
  ],
  "src": "Acronyms checked against all detailed slide text."
};
export async function slide04(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
