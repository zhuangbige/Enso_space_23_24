import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "k": "Appendix B",
  "t": "Data and literature links",
  "layout": "appendix",
  "rows": [
    [
      "Source",
      "Link",
      "Use"
    ],
    [
      "Peng et al. 2025",
      "nature.com/articles/s41561-025-01700-9",
      "Paper reproduction and question source"
    ],
    [
      "NOAA OISST",
      "ncei.noaa.gov/products/optimum-interpolation-sst",
      "Sea-surface temperature"
    ],
    [
      "GPCP",
      "psl.noaa.gov/data/gridded/data.gpcp.html",
      "Precipitation"
    ],
    [
      "NCEP/NCAR R1",
      "psl.noaa.gov/data/reanalysis/",
      "Wind-pressure fallback"
    ],
    [
      "ERA5",
      "cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels",
      "Next wind/Walker diagnostics"
    ],
    [
      "NOAA OLR",
      "psl.noaa.gov/data/gridded/data.interp_OLR.html",
      "Next convection check"
    ],
    [
      "ERSSTv5",
      "ncei.noaa.gov/products/extended-reconstructed-sst",
      "Long-record robustness"
    ]
  ],
  "src": "Full source log: docs/data_source_log.md."
};
export async function slide22(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }
