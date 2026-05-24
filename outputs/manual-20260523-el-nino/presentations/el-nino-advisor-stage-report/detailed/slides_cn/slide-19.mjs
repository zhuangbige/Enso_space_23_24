import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "拟定研究题目",
  "t": "建议题目：2023/24 强厄尔尼诺发展季海气耦合失效及其外海盆背景态调制",
  "layout": "text",
  "claim": "工作假设：2023 春夏热带外海盆暖异常和热带平均增暖背景改变了 Walker 环流和对流阈值，使太平洋暖 SST 对低层风、海平面气压和降水的典型响应滞后或减弱。",
  "points": [
    "假设 1：热带北大西洋、印度洋和海陆洲暖异常改变大尺度热力背景，抑制中太平洋西风响应。",
    "假设 2：海陆洲/印度洋对流维持在西侧，使典型 El Niño 降水中心东移不充分。",
    "假设 3：热带平均增暖提高对流触发阈值，使同样的太平洋 SST 异常对应更弱大气反馈。"
  ],
  "src": "Current diagnostics establish association; mechanism attribution requires ERA5, OLR, MJO/RMM and AGCM tests."
};
export async function slide19(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
