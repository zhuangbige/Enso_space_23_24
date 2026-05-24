import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "k": "附录 B",
  "t": "数据和文献链接",
  "layout": "appendix",
  "rows": [
    [
      "来源",
      "链接",
      "用途"
    ],
    [
      "Peng et al. 2025",
      "nature.com/articles/s41561-025-01700-9",
      "原文复现与问题来源"
    ],
    [
      "NOAA OISST",
      "ncei.noaa.gov/products/optimum-interpolation-sst",
      "海表温度"
    ],
    [
      "GPCP",
      "psl.noaa.gov/data/gridded/data.gpcp.html",
      "降水"
    ],
    [
      "NCEP/NCAR R1",
      "psl.noaa.gov/data/reanalysis/",
      "风压 fallback"
    ],
    [
      "ERA5",
      "cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels",
      "下一步风压/Walker"
    ],
    [
      "NOAA OLR",
      "psl.noaa.gov/data/gridded/data.interp_OLR.html",
      "下一步对流验证"
    ],
    [
      "ERSSTv5",
      "ncei.noaa.gov/products/extended-reconstructed-sst",
      "长记录稳健性"
    ]
  ],
  "src": "Full source log: docs/data_source_log.md."
};
export async function slide22(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
