import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Finding 1",
  "title": "Historical comparison: spring AMJ / summer JJA SST was strong, but synchronous wind-pressure coupling failed",
  "layout": "imageTable",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/seasonal_asynchrony_figure.png",
  "figNote": "Data note: OISST Niño-3, NCEP CWP u proxy, and SOI-like SLP gradient; all relative to the 1982/83, 1997/98, and 2015/16 strong-El Niño composite. How to read: by Niño-3 alone, AMJ/JJA 2023 already resembles a strong El Niño; however, CWP u and SOI-like metrics do not strengthen synchronously, and the low-level wind response even reverses sign. This is the central new finding so far.",
  "table": [
    [
      "Metric",
      "AMJ",
      "JJA"
    ],
    [
      "Niño-3 SST ratio",
      "1.41",
      "1.22"
    ],
    [
      "Central-west Pacific CWP wind ratio",
      "-0.43",
      "-0.14"
    ],
    [
      "SOI-like efficiency",
      "0.22",
      "0.28"
    ],
    [
      "CP rainfall ratio",
      "0.43",
      "0.38"
    ]
  ],
  "source": "Tables: asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv."
};
export async function slide10(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
