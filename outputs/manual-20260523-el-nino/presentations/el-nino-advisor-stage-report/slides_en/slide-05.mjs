import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Reproduction 1",
  "title": "Peng et al. Fig. 1: strong sea-surface temperature but weak wind-pressure coupling in 2023/24",
  "layout": "imagePairText",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.png",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/coupling_ratios.png",
  "figNote": "Data note: Peng et al. 2025 source archive Fig. 1; local table fig1_event_coupling.csv. Niño-3 is the eastern equatorial Pacific SST region; u10 is 10-m zonal wind; SOI is the Southern Oscillation Index. For 2023, Niño-3=1.929, u10=0.640, SOI=-0.433; u10 and SOI response ratios are only 0.27 and 0.31. How to read: the left panel reproduces the paper's SST, MSLP/u10, and scatter relationships; the right panel compresses them into response ratios. The anomaly is not weak SST, but a weak atmospheric response relative to historical slopes.",
  "bullets": [
    "Reproduction confirms 2023/24 as a strong SST event.",
    "Wind and pressure responses are muted relative to 1982/83, 1997/98, and 2015/16."
  ],
  "source": "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig1.png."
};
export async function slide05(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
