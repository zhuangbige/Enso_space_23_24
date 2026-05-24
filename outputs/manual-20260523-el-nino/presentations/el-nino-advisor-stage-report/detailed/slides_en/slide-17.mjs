import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Historical Summary",
  "t": "Key numbers: spring-summer 2023 was not SST-weak; it was atmosphere-response weak",
  "layout": "tableText",
  "rows": [
    [
      "Metric",
      "AMJ",
      "JJA"
    ],
    [
      "Niño-3 SST relative to strong-event composite",
      "1.41x",
      "1.22x"
    ],
    [
      "Central-west Pacific low-level wind ratio",
      "-0.43x",
      "-0.14x"
    ],
    [
      "SOI-like pressure-response efficiency",
      "0.22",
      "0.28"
    ],
    [
      "Central Pacific GPCP rainfall ratio",
      "0.43",
      "0.38"
    ]
  ],
  "text": "Together, these values show that the developing-season ocean state was already strong, but the atmospheric branch did not produce the usual westerly-wind, pressure-gradient, and rainfall-displacement responses.",
  "src": "Tables: asynchronous_coupling_efficiency.csv; gpcp_precip_seasonal_summary.csv."
};
export async function slide17(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
