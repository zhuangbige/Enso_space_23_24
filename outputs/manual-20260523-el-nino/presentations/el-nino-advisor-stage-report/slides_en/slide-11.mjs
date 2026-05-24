import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Finding 2",
  "title": "Spatial maps: the 2023 AMJ/JJA tropical background was warmer, but Pacific rainfall did not strengthen synchronously",
  "layout": "fullImage",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_sst_precip.png",
  "figNote": "Data note: OISST sea-surface temperature and GPCP precipitation; maps show 2023 AMJ/JJA minus the 1982/1997/2015 strong-event composite. TNA is Tropical North Atlantic, MC is Maritime Continent, and WPWP is western Pacific warm pool. These regions are warmer, while central/eastern Pacific rainfall is weaker. How to read: SST maps show that 2023 spring-summer warming extended beyond the eastern Pacific into external basins and the warm pool; rainfall maps show that central/eastern Pacific convection did not intensify accordingly, motivating a threshold/background-state interpretation.",
  "source": "D2 NOAA OISST; D3 GPCP. Summary table: stage_a_spatial_summary.csv."
};
export async function slide11(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
