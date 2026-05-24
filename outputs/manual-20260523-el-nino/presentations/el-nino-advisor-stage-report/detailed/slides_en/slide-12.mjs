import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Raw Validation",
  "t": "Data shown: OISST, GPCP, and NCEP/NCAR recalculations of paper-related metrics",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/validation_summary.png",
  "boxes": [
    [
      "Data name",
      "OISST is NOAA SST, GPCP is global precipitation, and NCEP/NCAR R1 is reanalysis wind and pressure. The chart summarizes agreement with reproduced indices."
    ],
    [
      "What it shows",
      "OISST Niño-3 correlates 0.9999 with the reproduced Fig. 1 index; NCEP wind and SOI-like pressure proxies are also highly consistent."
    ],
    [
      "Paper link and innovation",
      "This validates the paper-level signal with public data. The innovation is building a traceable raw-data pipeline for original seasonal diagnostics."
    ]
  ],
  "src": "Tables: oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv."
};
export async function slide12(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
