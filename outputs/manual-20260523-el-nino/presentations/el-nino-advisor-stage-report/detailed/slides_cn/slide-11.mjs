import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "从原文到新问题",
  "t": "原文留下的缺口：弱耦合是何时出现的？是否与外海盆背景态有关？",
  "layout": "text",
  "claim": "如果只说“2023/24 大气响应弱”，还不够形成新论文。必须进一步回答：弱响应发生在发展季、成熟期，还是全程？哪些变量最先低于历史 Niño-3 关系的预期？",
  "points": [
    "原文主要围绕事件生成和海洋动力过程展开，季节性的风压/降水/对流不同步还没有被系统展开。",
    "我的研究把响应变量拆成海表温度、低层风、海平面气压、降水、OLR 和 Walker 环流，再按 AMJ/JJA/SON/DJF 比较。",
    "目前主方法沿用原文 observed / expected response 思路：每个季节分别用历史 Niño-3 与大气变量的回归关系估计预期响应，再看 2023 实际响应偏离多少。"
  ],
  "src": "Research transition based on L1 and local seasonal diagnostics."
};
export async function slide11(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
