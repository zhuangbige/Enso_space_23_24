import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Reproduction",
  "title": "Reproduced Fig. 1 confirms the core fact: 2023/24 SST was strong while wind and pressure responses were weak",
  "layout": "imageChart",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.png",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/coupling_ratios.png",
  "source": "Paper reproduction: data/raw/peng2025_zenodo; table: fig1_event_coupling.csv."
};
export async function slide03(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
