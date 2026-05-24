import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "New Finding 1",
  "t": "Data shown: seasonal coupling-efficiency matrix for AMJ/JJA/SON/DJF",
  "layout": "figureExplain",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/seasonal_asynchrony_figure.png",
  "boxes": [
    [
      "Data name",
      "OISST Niño-3, NCEP central-west Pacific low-level wind, SOI-like SLP gradient, and GPCP rainfall compared with the 1982/83, 1997/98, and 2015/16 strong-event composite."
    ],
    [
      "What it shows",
      "AMJ/JJA 2023 SST was already historically strong, but wind-pressure-rainfall response efficiency was low. AMJ CWP wind ratio is about -0.43, and JJA is about -0.14."
    ],
    [
      "Paper link and innovation",
      "Peng et al. identifies event-level weak coupling; the innovation here is locating it in the developing season and identifying which variables desynchronize first."
    ]
  ],
  "src": "Tables: asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv."
};
export async function slide13(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
