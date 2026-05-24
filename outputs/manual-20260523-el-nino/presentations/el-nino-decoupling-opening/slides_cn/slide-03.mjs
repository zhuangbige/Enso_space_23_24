import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "复现结果",
  "title": "原文 Fig.1 的核心事实可以复现：2023/24 SST 强，但风压响应偏弱",
  "layout": "imageChart",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.png",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/coupling_ratios.png",
  "source": "Paper reproduction: data/raw/peng2025_zenodo; table: fig1_event_coupling.csv."
};
export async function slide03(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
