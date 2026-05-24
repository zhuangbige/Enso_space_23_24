import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Reproduction 3",
  "title": "Peng et al. Fig. 3-4: external-basin sea-surface temperature and 2023 wind forcing both damp the canonical response",
  "layout": "twoImagesTable",
  "leftImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.png",
  "rightImage": "/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.png",
  "figNote": "Data note: Peng et al. 2025 source archive Fig. 3-4; local tables fig3_agcm_summary.csv and fig4_wind_experiment_summary.csv. How to read: aPac is the canonical Pacific SST-driven atmospheric wind-stress response, while aIndAtl captures Indian-Atlantic external-basin influence. The negative external-basin term suggests possible damping of the Pacific response.",
  "tableTitle": "Extracted metrics",
  "table": [
    [
      "Metric",
      "Value"
    ],
    [
      "aPac wind stress",
      "0.0333"
    ],
    [
      "aIndAtl wind stress",
      "-0.0099"
    ],
    [
      "Dec Niño-3 CTRL",
      "2.344"
    ],
    [
      "Dec Niño-3 Wind2023",
      "0.681"
    ]
  ],
  "source": "L1 Peng et al. 2025; reproduction tables in data/derived/peng2025_repro/tables."
};
export async function slide07(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
