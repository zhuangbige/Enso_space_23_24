import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "开题方向",
  "title": "2023/24 强厄尔尼诺为何呈现海洋强、空气弱的脱耦响应？",
  "subtitle": "从 Peng et al. 2025 复现出发，转向外海盆背景态对太平洋大气响应的调制",
  "layout": "cover",
  "bullets": [
    "主问题：哪些海盆/背景态因素削弱了太平洋暖 SST 对风场、SOI、降水和 Walker 环流的典型响应？",
    "阶段定位：复现完成，独立验证完成一部分，已形成新研究切口。"
  ],
  "source": "Source: Peng et al. 2025 Nature Geoscience; NOAA OISST, GPCP, NCEP/NCAR reanalysis."
};
export async function slide01(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
