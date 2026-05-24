import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "原文复现 1",
  "title": "Peng et al. Fig. 1：2023/24 海表温度强，但风压耦合响应偏弱",
  "layout": "imagePairText",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.png",
  "chart": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/coupling_ratios.png",
  "figNote": "数据说明：Peng et al. 2025 source archive Fig. 1 数据；本地表 fig1_event_coupling.csv。Niño-3 指东赤道太平洋海温区；u10 是 10 米纬向风；SOI 是南方涛动指数。2023 Niño-3=1.929, u10=0.640, SOI=-0.433；u10 与 SOI 响应比仅为 0.27 和 0.31。 读图要点：左侧复现原文中 SST、MSLP/u10 和散点关系，右侧把数值压缩成响应比。它说明 2023/24 的海温并不弱，真正异常的是大气端没有按历史强事件斜率响应。",
  "bullets": [
    "复现结果确认：2023/24 是强海温事件。",
    "相对于 1982/83、1997/98、2015/16，风压响应明显偏弱。"
  ],
  "source": "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig1.png."
};
export async function slide05(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
