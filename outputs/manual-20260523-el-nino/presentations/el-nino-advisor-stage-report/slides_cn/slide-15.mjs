import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "拟定研究题目",
  "title": "建议题目：2023/24 强厄尔尼诺发展季海气耦合失效及其外海盆背景态调制",
  "layout": "thesis",
  "claim": "工作假设：2023 春夏的热带外海盆暖异常和热带平均增暖背景，改变了 Walker 环流和对流阈值，使太平洋暖 SST 对低层风压与降水的典型响应滞后或减弱。",
  "notes": [
    "可检验 H1：AMJ/JJA 外海盆暖异常抑制中太平洋西风响应。",
    "可检验 H2：海陆洲/印度洋局地加热维持西侧对流，削弱降水中心东移。",
    "可检验 H3：TNA 偏暖或热带平均增暖提高 ENSO 大气响应阈值。",
    "这三个假设都可以被数据逐步验证：先用 ERA5/OLR 建立大气结构，再用回归残差和 AGCM 实验区分太平洋自身与外海盆贡献。"
  ],
  "source": "Current diagnostics only establish association; ERA5/OLR/MJO and AGCM experiments are needed for mechanism attribution."
};
export async function slide15(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
