import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "数据来源",
  "title": "数据链条已经覆盖复现、独立验证和新机制诊断",
  "layout": "dataSources",
  "table": [
    [
      "用途",
      "数据",
      "时间/变量"
    ],
    [
      "原文复现",
      "Peng et al. Zenodo",
      "Fig.1-4 source data/code"
    ],
    [
      "SST",
      "NOAA OISST v2.1",
      "1982-2024 monthly SST"
    ],
    [
      "降水",
      "GPCP",
      "Equatorial Pacific precipitation"
    ],
    [
      "风压",
      "NCEP/NCAR R1",
      "u wind, SLP proxy"
    ],
    [
      "后续高阶验证",
      "ERA5 / OLR / ORAS5",
      "Walker circulation, convection, OHC"
    ]
  ],
  "source": "Catalog: docs/data_catalog.md; source inventory: docs/source_paper_data_inventory.md."
};
export async function slide09(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
