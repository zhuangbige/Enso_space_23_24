import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "总判断",
  "t": "目前主线已经从“复现原文”推进到“发展季耦合效率丧失”的新问题",
  "layout": "text",
  "claim": "原文证明 2023/24 强厄尔尼诺主要由海洋动力生成，但同时暴露出一个关键异常：海温很强，大气端的风、气压和降水响应却偏弱。",
  "points": [
    "本研究接着问：这种弱响应最早从哪个季节出现？是全年平均现象，还是发展季 AMJ/JJA 就已经发生？",
    "目前阶段性结果显示：2023 年春夏 Niño-3 海表温度已经强于历史强事件平均，但中西太平洋低层风、SOI-like 压力梯度和降水响应没有同步增强。",
    "因此，新研究的入口不是再证明 2023/24 是强厄尔尼诺，而是解释为什么强海温没有触发典型强厄尔尼诺式的大气耦合。"
  ],
  "src": "Synthesis from reproduced Peng et al. figures and data/derived/research seasonal diagnostics."
};
export async function slide02(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
