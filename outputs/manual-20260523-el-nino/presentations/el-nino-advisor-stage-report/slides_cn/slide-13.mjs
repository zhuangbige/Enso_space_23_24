import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "阶段性发现 4",
  "title": "外海盆暖异常为“发展季不同步响应”提供背景态线索",
  "layout": "twoChartsTable",
  "leftImage": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/external_basin_bars.png",
  "rightImage": "/Users/daiyue/Documents/Maryland/data/derived/research/asynchronous_coupling_by_season.png",
  "figNote": "数据说明：左图为 OISST 外海盆指数，右图为季节耦合效率。均以 1982/83、1997/98、2015/16 为历史强事件参照。 读图要点：左图说明外海盆暖异常是 2023 春夏的显著背景，右图说明这种背景对应着大气耦合效率低。下一步需要用 ERA5/OLR/AGCM 判断它是因果调制还是共同背景。",
  "table": [
    [
      "区域/指标",
      "AMJ",
      "JJA"
    ],
    [
      "热带北大西洋 TNA",
      "+1.11",
      "+1.35"
    ],
    [
      "西太暖池 WPWP",
      "+0.73",
      "+0.88"
    ],
    [
      "海陆洲 MC",
      "+0.55",
      "+0.68"
    ],
    [
      "热带印度洋 TIO",
      "+0.44",
      "+0.40"
    ]
  ],
  "source": "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_by_season.png."
};
export async function slide13(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
