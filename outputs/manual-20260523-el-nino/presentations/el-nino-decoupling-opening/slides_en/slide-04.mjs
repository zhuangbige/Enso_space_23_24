import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Paper Attribution",
  "title": "The reproduced AGCM and wind-stress experiments point to strong ocean dynamics but a muted atmosphere",
  "layout": "twoImagesTable",
  "leftImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.png",
  "rightImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.png",
  "tableTitle": "Extracted paper metrics",
  "table": [
    [
      "Metric",
      "Value"
    ],
    [
      "Fig.3 aPac taux",
      "0.0333"
    ],
    [
      "Fig.3 aIndAtl taux",
      "-0.0099"
    ],
    [
      "Fig.4 Dec Niño-3 CTRL",
      "2.344"
    ],
    [
      "Fig.4 Dec Niño-3 Wind2023",
      "0.681"
    ]
  ],
  "source": "Paper reproduction tables: fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv."
};
export async function slide04(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
