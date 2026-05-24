import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Appendix A",
  "t": "Slide-to-data table",
  "layout": "appendix",
  "rows": [
    [
      "Slides",
      "Figure / content",
      "Data table"
    ],
    [
      "6-7",
      "Reproduced Fig. 1 and coupling ratios",
      "fig1_event_coupling.csv"
    ],
    [
      "8",
      "Reproduced Fig. 2 ocean dynamics",
      "fig2_equatorial_summary.csv"
    ],
    [
      "9-10",
      "Reproduced Fig. 3-4 AGCM/wind-stress experiments",
      "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"
    ],
    [
      "12",
      "Raw-product validation",
      "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"
    ],
    [
      "13",
      "Seasonal coupling-efficiency matrix",
      "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"
    ],
    [
      "14-15",
      "AMJ/JJA spatial maps",
      "stage_a_spatial_summary.csv"
    ],
    [
      "16-17",
      "External basins and historical comparison",
      "external_basin_seasonal_summary.csv; gpcp_precip_seasonal_summary.csv"
    ]
  ],
  "src": "All local paths are under /Users/daiyue/Documents/Maryland/data/derived."
};
export async function slide21(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
