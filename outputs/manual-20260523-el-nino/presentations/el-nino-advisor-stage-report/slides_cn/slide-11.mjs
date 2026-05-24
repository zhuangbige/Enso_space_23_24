import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "阶段性发现 2",
  "title": "空间图：2023 春夏热带背景更暖，但太平洋降水中心未同步增强",
  "layout": "fullImage",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_sst_precip.png",
  "figNote": "数据说明：OISST 海表温度与 GPCP 降水；图为 2023 AMJ/JJA 减去 1982/1997/2015 强事件 composite。TNA 指热带北大西洋，MC 指海陆洲，WPWP 指西太平洋暖池。TNA、海陆洲、西太暖池偏暖；中东太平洋降水偏弱。 读图要点：SST 图显示 2023 春夏不只是东太平洋暖，外海盆和西太暖池也更暖；降水图显示中东太平洋对流并没有跟随海温充分增强，支持“热背景改变对流阈值或 Walker 响应”的解释方向。",
  "source": "D2 NOAA OISST; D3 GPCP. Summary table: stage_a_spatial_summary.csv."
};
export async function slide11(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
