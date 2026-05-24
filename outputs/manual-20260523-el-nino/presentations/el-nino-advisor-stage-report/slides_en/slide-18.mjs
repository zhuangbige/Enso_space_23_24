import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Appendix B",
  "title": "Data and literature links",
  "layout": "links",
  "links": [
    [
      "Peng et al. 2025",
      "https://www.nature.com/articles/s41561-025-01700-9"
    ],
    [
      "NOAA OISST v2.1",
      "https://www.ncei.noaa.gov/products/optimum-interpolation-sst"
    ],
    [
      "GPCP",
      "https://psl.noaa.gov/data/gridded/data.gpcp.html"
    ],
    [
      "NCEP/NCAR R1",
      "https://www.psl.noaa.gov/data/reanalysis/"
    ],
    [
      "ERA5",
      "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels"
    ],
    [
      "NOAA OLR",
      "https://psl.noaa.gov/data/gridded/data.interp_OLR.html"
    ],
    [
      "ERSSTv5",
      "https://www.ncei.noaa.gov/products/extended-reconstructed-sst"
    ],
    [
      "ORAS5",
      "https://www.ecmwf.int/en/forecasts/dataset/ocean-reanalysis-system-5"
    ],
    [
      "TAO/TRITON",
      "https://www.pmel.noaa.gov/gtmba/building-tao"
    ]
  ],
  "source": "Full source log: docs/data_source_log.md."
};
export async function slide18(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
