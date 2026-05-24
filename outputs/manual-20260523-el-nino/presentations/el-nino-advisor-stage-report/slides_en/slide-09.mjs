import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Raw Validation",
  "title": "Public datasets confirm that the paper-level signal is not a single-dataset artifact",
  "layout": "imageBrief",
  "image": "/Users/daiyue/Documents/Maryland/outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets/validation_summary.png",
  "figNote": "Data note: NOAA OISST, GPCP, and NCEP/NCAR R1; corresponding tables oisst_vs_fig1_nino3.csv, gpcp_vs_fig2_precip.csv, and ncep_vs_fig1_atmosphere.csv. How to read: OISST validates SST, GPCP validates rainfall, and NCEP serves as a wind/pressure fallback. Their consistent direction means the ocean-strong / atmosphere-weak signal is not an artifact of the paper source data.",
  "bullets": [
    "NOAA Optimum Interpolation SST, or OISST, Niño-3 correlates 0.9999 with reproduced Fig. 1.",
    "Global Precipitation Climatology Project, or GPCP, shows weaker central/eastern Pacific rainfall in 2023 than in the strong-event composite.",
    "NCEP/NCAR reanalysis wind and SOI-like pressure-gradient proxies align closely with the paper's atmospheric metrics."
  ],
  "source": "D2 NOAA OISST; D3 GPCP; D4 NCEP/NCAR R1 via NOAA PSL OPeNDAP."
};
export async function slide09(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
