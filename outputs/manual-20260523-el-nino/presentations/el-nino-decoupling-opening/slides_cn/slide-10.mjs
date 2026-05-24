import { renderDeckSlide } from "../deck_shared_cn.mjs";
const data = {
  "kicker": "下一步",
  "title": "下一阶段从指数走向空间图和归因：先诊断，再设计 AGCM 实验",
  "layout": "roadmap",
  "steps": [
    "AMJ/JJA SST 异常图\n确认外海盆空间结构",
    "降水/风/SLP 图\n定位对流与 Walker 响应",
    "散点与回归残差\n量化耦合效率",
    "AGCM 预案\nPacific-only / external-basin / detrended"
  ],
  "source": "Planned workflow: docs/research_stage_workflow.md; docs/agcm_experiment_matrix.md."
};
export async function slide10(presentation, ctx) {
  return renderDeckSlide(presentation, ctx, data);
}
