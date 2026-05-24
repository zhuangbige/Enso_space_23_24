import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Next Data",
  "t": "Data needed for the next research version",
  "layout": "tableText",
  "rows": [
    [
      "Dataset",
      "Use",
      "Why needed"
    ],
    [
      "ERA5 u850 / SLP / χ200",
      "Low-level wind, sea-level pressure, and Walker circulation.",
      "Manuscript-grade wind-pressure-circulation evidence."
    ],
    [
      "NOAA OLR",
      "Independent deep-convection diagnosis.",
      "Avoid relying only on rainfall to infer convection."
    ],
    [
      "ERSSTv5",
      "Long-record robustness since 1854.",
      "Check whether the post-1981 OISST sample affects historical comparison."
    ],
    [
      "MJO/RMM or daily data",
      "Key-month decomposition, especially January 2024.",
      "Separate ENSO background, MJO, and trend effects."
    ]
  ],
  "text": "The near-term priority is ERA5 plus OLR. These will strengthen wind, pressure, Walker-circulation, and convection evidence before AGCM experiments.",
  "src": "Data priorities from reports/当前数据分析阶段总结.md."
};
export async function slide20(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
