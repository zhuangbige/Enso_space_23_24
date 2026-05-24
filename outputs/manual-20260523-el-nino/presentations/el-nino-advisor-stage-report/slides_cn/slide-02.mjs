import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "一句话结论",
  "title": "目前已经从复现进入新研究第一层诊断",
  "layout": "thesis",
  "claim": "2023 年 AMJ/JJA 的 Niño-3 海温已达到历史强厄尔尼诺量级，但中西太平洋低层风、SOI-like 压力梯度和降水响应没有同步增强。",
  "notes": [
    "原文贡献：证明 2023/24 强厄尔尼诺主要由海洋动力维持，并指出大气反馈偏弱。",
    "本课题问题：偏弱大气响应最早在哪个季节出现？哪些外海盆或背景态可能调制了耦合效率？",
    "阶段发现：AMJ/JJA 是关键窗口，TNA、印度洋、海陆洲和西太暖池同步偏暖。",
    "因此，当前不是简单重复原文，而是在原文“海洋动力生成强事件”的基础上追问：大气为什么没有按历史经验给出同等响应。"
  ],
  "source": "Current synthesis from reproduced paper figures and data/derived/research seasonal diagnostics."
};
export async function slide02(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
