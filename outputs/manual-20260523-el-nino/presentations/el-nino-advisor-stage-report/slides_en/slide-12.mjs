import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Finding 3",
  "title": "Spatial maps: low-level wind and sea-level pressure also show an atypical developing-season Walker response",
  "layout": "fullImage",
  "image": "/Users/daiyue/Documents/Maryland/data/derived/research/stage_a_amj_jja_ncep_wind_slp.png",
  "figNote": "Data note: NCEP/NCAR R1 near-surface sigma995 wind and sea-level pressure SLP; maps show 2023 AMJ/JJA minus the 1982/1997/2015 composite. CWP means central-western Pacific. CWP low-level wind differences are -2.301 m/s in AMJ and -2.576 m/s in JJA; SOI-like SLP-gradient differences are positive. How to read: NCEP is still a fallback, but it already provides a clear clue: AMJ/JJA central-western Pacific low-level wind is weaker than in historical strong events, and the SLP gradient is not established in a canonical El Niño way.",
  "source": "D4 NCEP/NCAR R1 fallback diagnostic. Final manuscript stage should replace/check with ERA5."
};
export async function slide12(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
