import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Appendix A",
  "title": "Slide-to-data table",
  "layout": "appendixTable",
  "table": [
    [
      "Slide",
      "Figure / claim",
      "Corresponding table"
    ],
    [
      "5",
      "Fig. 1 event strength and coupling ratios",
      "fig1_event_coupling.csv"
    ],
    [
      "6",
      "Fig. 2 equatorial propagation diagnostics",
      "fig2_equatorial_summary.csv"
    ],
    [
      "7",
      "Fig. 3-4 AGCM and wind-stress experiments",
      "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"
    ],
    [
      "9",
      "OISST/GPCP/NCEP independent validation",
      "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"
    ],
    [
      "10",
      "AMJ/JJA historical coupling efficiency",
      "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"
    ],
    [
      "11-12",
      "AMJ/JJA spatial SST/rainfall/wind/pressure",
      "stage_a_spatial_summary.csv"
    ],
    [
      "13",
      "External-basin warmth and seasonal efficiency",
      "external_basin_seasonal_summary.csv"
    ]
  ],
  "source": "All paths are under /Users/daiyue/Documents/Maryland/data/derived."
};
export async function slide17(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
