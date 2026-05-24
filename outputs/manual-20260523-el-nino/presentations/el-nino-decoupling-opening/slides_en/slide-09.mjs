import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Data Sources",
  "title": "The data chain now spans reproduction, independent validation, and new mechanism diagnostics",
  "layout": "dataSources",
  "table": [
    [
      "Purpose",
      "Dataset",
      "Time / variables"
    ],
    [
      "Paper reproduction",
      "Peng et al. Zenodo",
      "Fig. 1-4 source data/code"
    ],
    [
      "SST",
      "NOAA OISST v2.1",
      "1982-2024 monthly SST"
    ],
    [
      "Rainfall",
      "GPCP",
      "Equatorial Pacific precipitation"
    ],
    [
      "Wind/pressure",
      "NCEP/NCAR R1",
      "u wind, SLP proxy"
    ],
    [
      "Next-stage checks",
      "ERA5 / OLR / ORAS5",
      "Walker circulation, convection, OHC"
    ]
  ],
  "source": "Catalog: docs/data_catalog.md; source inventory: docs/source_paper_data_inventory.md."
};
export async function slide09(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
