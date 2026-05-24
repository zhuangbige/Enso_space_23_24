import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "新研究发现 3",
  "t": "图中数据名称：AMJ/JJA 近地面风和海平面气压空间异常",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_ncep_wind_slp.png",
  "boxes": [
    [
      "这幅图是什么数据",
      "NCEP/NCAR R1 的近地面 sigma995 风和海平面气压 SLP，计算 2023 AMJ/JJA 相对历史强事件 composite 的差值。"
    ],
    [
      "它反映了什么",
      "中西太平洋低层风异常相对历史强事件偏弱，海平面气压梯度也没有建立出典型强厄尔尼诺结构。这支持“Walker 环流响应不典型”。"
    ],
    [
      "对应原文与我的创新",
      "对应原文中风场偏弱的发现。创新是把风和气压做成发展季空间对比，指出 AMJ/JJA 已经出现大气端不同步。"
    ]
  ],
  "src": "Data: NCEP/NCAR R1 fallback; final manuscript stage should verify with ERA5."
};
export async function slide15(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
