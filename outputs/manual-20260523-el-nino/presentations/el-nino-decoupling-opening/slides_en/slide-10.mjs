import { renderDeckSlide } from "../deck_shared_en.mjs";
const data = {
  "kicker": "Next Step",
  "title": "Move from indices to spatial diagnostics and attribution design",
  "layout": "roadmap",
  "steps": [
    "AMJ/JJA SST maps\nconfirm basin-scale structure",
    "Rainfall / wind / SLP maps\nlocate convection and Walker response",
    "Scatter and residual tests\nquantify coupling efficiency",
    "AGCM design\nPacific-only / external-basin / detrended"
  ],
  "source": "Planned workflow: docs/research_stage_workflow.md; docs/agcm_experiment_matrix.md."
};
export async function slide10(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
