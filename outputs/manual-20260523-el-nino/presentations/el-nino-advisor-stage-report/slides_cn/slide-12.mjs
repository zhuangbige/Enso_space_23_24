import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "阶段性发现 3",
  "title": "空间图：低层风和海平面气压也显示发展季 Walker 环流响应不典型",
  "layout": "fullImage",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_ncep_wind_slp.png",
  "figNote": "数据说明：NCEP/NCAR R1 近地面 sigma995 风与海平面气压 SLP；图为 2023 AMJ/JJA 减去 1982/1997/2015 composite。CWP 指中西太平洋，CWP 低层风差值 AMJ=-2.301 m/s, JJA=-2.576 m/s；类 SOI 的 SLP 梯度差值为正。 读图要点：NCEP 结果目前是 fallback，但已经给出清楚线索：AMJ/JJA 中西太平洋低层风异常相对历史强事件偏弱，SLP 梯度也不像典型强 El Niño 那样充分建立。",
  "source": "D4 NCEP/NCAR R1 fallback diagnostic. Final paper stage should replace/check with ERA5."
};
export async function slide12(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
