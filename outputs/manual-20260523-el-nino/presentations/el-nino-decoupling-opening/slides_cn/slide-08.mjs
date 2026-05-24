import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "拟定题目",
  "title": "可开题为：外海盆暖异常对 2023/24 强厄尔尼诺海气脱耦的调制作用",
  "layout": "hypothesis",
  "hypothesis": [
    "H1：春夏外海盆暖异常改变 Walker 环流背景，削弱中太平洋西风响应。",
    "H2：海陆洲/印度洋暖异常维持局地对流，抑制典型 ENSO 降水中心东移。",
    "H3：Tropical North Atlantic 异常偏暖通过遥相关或热带平均增暖背景提高大气响应阈值。"
  ],
  "question": "主问题：在太平洋 SST 已足够暖的条件下，外海盆和背景增暖如何改变大气耦合效率？",
  "source": "Interpretation based on reproduction + raw validation + external-basin diagnostics."
};
export async function slide08(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
