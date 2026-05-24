#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(new URL("..", import.meta.url).pathname);
const WORKSPACE = path.join(ROOT, "outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening");
const ASSETS = path.join(WORKSPACE, "assets");
const FIGURES = path.join(ROOT, "data/derived/peng2025_repro/figures");

const common = {
  fig1: path.join(FIGURES, "Fig1.png"),
  fig2: path.join(FIGURES, "Fig2.png"),
  fig3: path.join(FIGURES, "Fig3.png"),
  fig4: path.join(FIGURES, "Fig4.png"),
  coupling: path.join(ASSETS, "coupling_ratios.png"),
  validation: path.join(ASSETS, "validation_summary.png"),
  seasonal: path.join(ASSETS, "seasonal_decoupling.png"),
  external: path.join(ASSETS, "external_basin_bars.png"),
};

const cn = [
  {
    kicker: "开题方向",
    title: "2023/24 强厄尔尼诺为何呈现海洋强、空气弱的脱耦响应？",
    subtitle: "从 Peng et al. 2025 复现出发，转向外海盆背景态对太平洋大气响应的调制",
    layout: "cover",
    bullets: ["主问题：哪些海盆/背景态因素削弱了太平洋暖 SST 对风场、SOI、降水和 Walker 环流的典型响应？", "阶段定位：复现完成，独立验证完成一部分，已形成新研究切口。"],
    source: "Source: Peng et al. 2025 Nature Geoscience; NOAA OISST, GPCP, NCEP/NCAR reanalysis.",
  },
  {
    kicker: "逻辑链",
    title: "先复现核心事实，再把“全年脱耦”拆成春夏的机制问题",
    layout: "flow",
    steps: ["原文复现\nFig.1-4", "原始数据验证\nOISST / GPCP / NCEP", "季节分解\nAMJ-JJA 提前脱耦", "新研究问题\n外海盆暖背景是否抑制耦合？"],
    notes: ["复现不是终点，而是把论文的定性判断变成可检验指标。", "博士课题切口：春夏阶段，太平洋已变暖，但大气反馈没有跟上。"],
    source: "Derived workflow in /reports/阶段性中文报告.md.",
  },
  {
    kicker: "复现结果",
    title: "原文 Fig.1 的核心事实可以复现：2023/24 SST 强，但风压响应偏弱",
    layout: "imageChart",
    image: common.fig1,
    chart: common.coupling,
    source: "Paper reproduction: data/raw/peng2025_zenodo; table: fig1_event_coupling.csv.",
  },
  {
    kicker: "原文归因",
    title: "原文的 AGCM 和风应力实验提示：海洋动力强，但大气端响应不足",
    layout: "twoImagesTable",
    leftImage: common.fig3,
    rightImage: common.fig4,
    tableTitle: "原文表格化摘录",
    table: [
      ["指标", "数值"],
      ["Fig.3 aPac taux", "0.0333"],
      ["Fig.3 aIndAtl taux", "-0.0099"],
      ["Fig.4 Dec Niño-3 CTRL", "2.344"],
      ["Fig.4 Dec Niño-3 Wind2023", "0.681"],
    ],
    source: "Paper reproduction tables: fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv.",
  },
  {
    kicker: "独立验证",
    title: "用公开原始资料重算后，论文级信号仍然成立",
    layout: "chartText",
    chart: common.validation,
    notes: ["OISST 重新计算 Niño-3，与原文 Fig.1 相关 0.9999。", "GPCP 显示 2023/24 中东太平洋降水低于强厄尔尼诺 composite。", "NCEP 风和 SOI-like proxy 与原文大气指标高度一致。"],
    source: "Raw validation: NOAA PSL OPeNDAP OISST/GPCP/NCEP outputs in data/derived/raw_validation.",
  },
  {
    kicker: "季节分解",
    title: "关键新切口：2023 年 AMJ/JJA Niño-3 不弱，但大气响应已经显著偏弱",
    layout: "chartTable",
    chart: common.seasonal,
    table: [
      ["指标", "AMJ 差值", "JJA 差值"],
      ["Niño-3 SST", "+0.282", "+0.309"],
      ["CWP u proxy", "-2.301", "-2.576"],
      ["SOI-like proxy", "+1.133", "+1.551"],
    ],
    source: "Seasonal table: data/derived/research/seasonal_decoupling_first_pass.csv.",
  },
  {
    kicker: "新研究内容",
    title: "外海盆 OISST 指数显示：2023 春夏热带背景态异常偏暖",
    layout: "chartTable",
    chart: common.external,
    table: [
      ["区域", "AMJ", "JJA"],
      ["Tropical N. Atlantic", "+1.110", "+1.350"],
      ["W. Pacific warm pool", "+0.726", "+0.881"],
      ["Maritime Continent", "+0.547", "+0.677"],
      ["Tropical Indian Ocean", "+0.438", "+0.401"],
    ],
    source: "New diagnostic: OISST external-basin indices, 2023 minus 1982/1997/2015 composite.",
  },
  {
    kicker: "拟定题目",
    title: "可开题为：外海盆暖异常对 2023/24 强厄尔尼诺海气脱耦的调制作用",
    layout: "hypothesis",
    hypothesis: ["H1：春夏外海盆暖异常改变 Walker 环流背景，削弱中太平洋西风响应。", "H2：海陆洲/印度洋暖异常维持局地对流，抑制典型 ENSO 降水中心东移。", "H3：Tropical North Atlantic 异常偏暖通过遥相关或热带平均增暖背景提高大气响应阈值。"],
    question: "主问题：在太平洋 SST 已足够暖的条件下，外海盆和背景增暖如何改变大气耦合效率？",
    source: "Interpretation based on reproduction + raw validation + external-basin diagnostics.",
  },
  {
    kicker: "数据来源",
    title: "数据链条已经覆盖复现、独立验证和新机制诊断",
    layout: "dataSources",
    table: [
      ["用途", "数据", "时间/变量"],
      ["原文复现", "Peng et al. Zenodo", "Fig.1-4 source data/code"],
      ["SST", "NOAA OISST v2.1", "1982-2024 monthly SST"],
      ["降水", "GPCP", "Equatorial Pacific precipitation"],
      ["风压", "NCEP/NCAR R1", "u wind, SLP proxy"],
      ["后续高阶验证", "ERA5 / OLR / ORAS5", "Walker circulation, convection, OHC"],
    ],
    source: "Catalog: docs/data_catalog.md; source inventory: docs/source_paper_data_inventory.md.",
  },
  {
    kicker: "下一步",
    title: "下一阶段从指数走向空间图和归因：先诊断，再设计 AGCM 实验",
    layout: "roadmap",
    steps: ["AMJ/JJA SST 异常图\n确认外海盆空间结构", "降水/风/SLP 图\n定位对流与 Walker 响应", "散点与回归残差\n量化耦合效率", "AGCM 预案\nPacific-only / external-basin / detrended"],
    source: "Planned workflow: docs/research_stage_workflow.md; docs/agcm_experiment_matrix.md.",
  },
];

const en = [
  {
    kicker: "Research Topic",
    title: "Why did the 2023/24 strong El Niño show ocean-strong but atmosphere-weak coupling?",
    subtitle: "From reproducing Peng et al. 2025 to testing whether extra-Pacific warming damped the Pacific atmospheric response",
    layout: "cover",
    bullets: ["Core question: which basins or background-state factors weakened the canonical wind, SOI, rainfall, and Walker-circulation response to warm Pacific SST?", "Current stage: paper reproduction is complete; raw-product validation and first mechanism diagnostics are underway."],
    source: "Source: Peng et al. 2025 Nature Geoscience; NOAA OISST, GPCP, NCEP/NCAR reanalysis.",
  },
  {
    kicker: "Logic Chain",
    title: "The project moves from reproducing the paper to isolating a spring-summer coupling failure",
    layout: "flow",
    steps: ["Paper reproduction\nFig. 1-4", "Raw-product checks\nOISST / GPCP / NCEP", "Seasonal split\nAMJ-JJA decoupling", "New question\nCan extra-Pacific warmth damp coupling?"],
    notes: ["Reproduction turns the paper's qualitative claim into a measurable coupling residual.", "The PhD-level opening is seasonal: Pacific SST was already warm, but the atmosphere did not respond normally."],
    source: "Derived workflow in reports/阶段性中文报告.md.",
  },
  {
    kicker: "Reproduction",
    title: "Reproduced Fig. 1 confirms the core fact: 2023/24 SST was strong while wind and pressure responses were weak",
    layout: "imageChart",
    image: common.fig1,
    chart: common.coupling,
    source: "Paper reproduction: data/raw/peng2025_zenodo; table: fig1_event_coupling.csv.",
  },
  {
    kicker: "Paper Attribution",
    title: "The reproduced AGCM and wind-stress experiments point to strong ocean dynamics but a muted atmosphere",
    layout: "twoImagesTable",
    leftImage: common.fig3,
    rightImage: common.fig4,
    tableTitle: "Extracted paper metrics",
    table: [
      ["Metric", "Value"],
      ["Fig.3 aPac taux", "0.0333"],
      ["Fig.3 aIndAtl taux", "-0.0099"],
      ["Fig.4 Dec Niño-3 CTRL", "2.344"],
      ["Fig.4 Dec Niño-3 Wind2023", "0.681"],
    ],
    source: "Paper reproduction tables: fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv.",
  },
  {
    kicker: "Raw Validation",
    title: "Independent public datasets reproduce the paper-level signal",
    layout: "chartText",
    chart: common.validation,
    notes: ["Raw OISST Niño-3 correlates 0.9999 with the reproduced Fig. 1 index.", "GPCP shows weaker 2023/24 central/eastern Pacific precipitation than the strong-El Niño composite.", "NCEP wind and SOI-like proxies align closely with the paper's atmospheric indices."],
    source: "Raw validation: NOAA PSL OPeNDAP OISST/GPCP/NCEP outputs in data/derived/raw_validation.",
  },
  {
    kicker: "Seasonal Split",
    title: "The key opening: 2023 AMJ/JJA Niño-3 was not weak, yet atmospheric coupling was already suppressed",
    layout: "chartTable",
    chart: common.seasonal,
    table: [
      ["Metric", "AMJ diff.", "JJA diff."],
      ["Niño-3 SST", "+0.282", "+0.309"],
      ["CWP u proxy", "-2.301", "-2.576"],
      ["SOI-like proxy", "+1.133", "+1.551"],
    ],
    source: "Seasonal table: data/derived/research/seasonal_decoupling_first_pass.csv.",
  },
  {
    kicker: "New Diagnostic",
    title: "External-basin OISST indices show unusually warm tropical background conditions in spring-summer 2023",
    layout: "chartTable",
    chart: common.external,
    table: [
      ["Region", "AMJ", "JJA"],
      ["Tropical N. Atlantic", "+1.110", "+1.350"],
      ["W. Pacific warm pool", "+0.726", "+0.881"],
      ["Maritime Continent", "+0.547", "+0.677"],
      ["Tropical Indian Ocean", "+0.438", "+0.401"],
    ],
    source: "New diagnostic: OISST external-basin indices, 2023 minus 1982/1997/2015 composite.",
  },
  {
    kicker: "Proposed Topic",
    title: "Working title: Extra-Pacific warming as a modulator of atmosphere-ocean decoupling during the 2023/24 El Niño",
    layout: "hypothesis",
    hypothesis: ["H1: Spring-summer external-basin warmth altered the Walker background state and weakened central-Pacific westerly response.", "H2: Maritime Continent / Indian Ocean warmth maintained local convection and limited the canonical eastward rainfall shift.", "H3: Tropical North Atlantic warmth or tropical-mean warming raised the threshold for a Pacific-driven atmospheric response."],
    question: "Core question: when Pacific SST is already sufficiently warm, how do external basins and background warming change coupling efficiency?",
    source: "Interpretation based on reproduction + raw validation + external-basin diagnostics.",
  },
  {
    kicker: "Data Sources",
    title: "The data chain now spans reproduction, independent validation, and new mechanism diagnostics",
    layout: "dataSources",
    table: [
      ["Purpose", "Dataset", "Time / variables"],
      ["Paper reproduction", "Peng et al. Zenodo", "Fig. 1-4 source data/code"],
      ["SST", "NOAA OISST v2.1", "1982-2024 monthly SST"],
      ["Rainfall", "GPCP", "Equatorial Pacific precipitation"],
      ["Wind/pressure", "NCEP/NCAR R1", "u wind, SLP proxy"],
      ["Next-stage checks", "ERA5 / OLR / ORAS5", "Walker circulation, convection, OHC"],
    ],
    source: "Catalog: docs/data_catalog.md; source inventory: docs/source_paper_data_inventory.md.",
  },
  {
    kicker: "Next Step",
    title: "Move from indices to spatial diagnostics and attribution design",
    layout: "roadmap",
    steps: ["AMJ/JJA SST maps\nconfirm basin-scale structure", "Rainfall / wind / SLP maps\nlocate convection and Walker response", "Scatter and residual tests\nquantify coupling efficiency", "AGCM design\nPacific-only / external-basin / detrended"],
    source: "Planned workflow: docs/research_stage_workflow.md; docs/agcm_experiment_matrix.md.",
  },
];

const shared = `
const C = {
  bg: "#f7f3ea",
  ink: "#1d1b18",
  muted: "#6e675d",
  rule: "#d8d1c4",
  red: "#cc5a43",
  teal: "#2f6f73",
  blue: "#4a5f99",
  pale: "#efe8dc",
};

function bg(slide, ctx) {
  ctx.addShape(slide, { x: 0, y: 0, w: 1280, h: 720, fill: C.bg });
}

function text(slide, ctx, value, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text: value, x, y, w, h,
    fontSize: opts.size || 22,
    bold: opts.bold || false,
    color: opts.color || C.ink,
    typeface: opts.face || (opts.title ? ctx.fonts.title : ctx.fonts.body),
    valign: opts.valign || "top",
    align: opts.align || "left",
    insets: opts.insets || { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

function header(slide, ctx, d) {
  text(slide, ctx, d.kicker, 64, 34, 260, 24, { size: 13, bold: true, color: C.red });
  text(slide, ctx, d.title, 64, 65, 1020, 88, { size: 34, bold: true, title: true });
  ctx.addShape(slide, { x: 64, y: 151, w: 1120, h: 1.5, fill: C.rule });
}

function source(slide, ctx, value) {
  text(slide, ctx, value || "", 64, 684, 1070, 18, { size: 9, color: C.muted });
}

function bulletList(slide, ctx, items, x, y, w, color = C.ink) {
  let yy = y;
  for (const item of items || []) {
    ctx.addShape(slide, { x, y: yy + 8, w: 7, h: 7, fill: C.red, geometry: "ellipse" });
    text(slide, ctx, item, x + 20, yy, w - 20, 50, { size: 18, color });
    yy += 58;
  }
}

async function addImage(slide, ctx, imagePath, x, y, w, h, fit = "contain") {
  await ctx.addImage(slide, { path: imagePath, x, y, w, h, fit });
}

function smallTable(slide, ctx, rows, x, y, w, rowH = 38) {
  const cols = rows[0].length;
  const colW = w / cols;
  rows.forEach((row, r) => {
    row.forEach((cell, c) => {
      ctx.addShape(slide, {
        x: x + c * colW, y: y + r * rowH, w: colW, h: rowH,
        fill: r === 0 ? C.ink : (r % 2 === 0 ? "#f3ede2" : "#fbf8f1"),
        line: { style: "solid", fill: C.rule, width: 0.7 },
      });
      text(slide, ctx, cell, x + c * colW + 9, y + r * rowH + 8, colW - 18, rowH - 10, {
        size: r === 0 ? 12 : 13,
        bold: r === 0,
        color: r === 0 ? "#ffffff" : C.ink,
      });
    });
  });
}

async function renderDeckSlide(presentation, ctx, d) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  if (d.layout === "cover") {
    text(slide, ctx, d.kicker, 64, 54, 240, 24, { size: 14, bold: true, color: C.red });
    text(slide, ctx, d.title, 64, 104, 850, 190, { size: 45, bold: true, title: true });
    text(slide, ctx, d.subtitle, 66, 322, 920, 62, { size: 22, color: C.muted });
    bulletList(slide, ctx, d.bullets, 72, 440, 830);
    ctx.addShape(slide, { x: 1010, y: 118, w: 150, h: 150, fill: C.red, geometry: "ellipse" });
    ctx.addShape(slide, { x: 1075, y: 310, w: 88, h: 88, fill: C.teal, geometry: "ellipse" });
    source(slide, ctx, d.source);
    return slide;
  }
  header(slide, ctx, d);
  if (d.layout === "flow" || d.layout === "roadmap") {
    const y = d.layout === "flow" ? 244 : 236;
    const stepW = 242;
    d.steps.forEach((step, i) => {
      const x = 72 + i * 292;
      const stepH = d.layout === "roadmap" ? 172 : 132;
      ctx.addShape(slide, { x, y, w: stepW, h: stepH, fill: i % 2 ? "#edf3ef" : "#f5e5df", line: { style: "solid", fill: C.rule, width: 1 } });
      text(slide, ctx, String(i + 1).padStart(2, "0"), x + 18, y + 16, 52, 28, { size: 18, bold: true, color: i % 2 ? C.teal : C.red });
      text(slide, ctx, step, x + 18, y + 52, stepW - 36, stepH - 62, { size: d.layout === "roadmap" ? 18 : 20, bold: true });
      if (i < d.steps.length - 1) text(slide, ctx, "→", x + stepW + 20, y + 45, 36, 40, { size: 30, color: C.muted });
    });
    bulletList(slide, ctx, d.notes || [], 92, 466, 920);
  } else if (d.layout === "imageChart") {
    await addImage(slide, ctx, d.image, 70, 178, 560, 428);
    await addImage(slide, ctx, d.chart, 656, 184, 500, 374);
    text(slide, ctx, "2023 ratios: u10 = 0.27; SOI = 0.31", 676, 576, 450, 34, { size: 20, bold: true, color: C.red });
  } else if (d.layout === "twoImagesTable") {
    await addImage(slide, ctx, d.leftImage, 64, 178, 380, 320);
    await addImage(slide, ctx, d.rightImage, 462, 178, 380, 320);
    text(slide, ctx, d.tableTitle, 880, 184, 280, 26, { size: 18, bold: true });
    smallTable(slide, ctx, d.table, 870, 224, 312, 42);
  } else if (d.layout === "chartText") {
    await addImage(slide, ctx, d.chart, 80, 194, 520, 352);
    bulletList(slide, ctx, d.notes, 658, 214, 460);
  } else if (d.layout === "chartTable") {
    await addImage(slide, ctx, d.chart, 70, 188, 650, 386);
    smallTable(slide, ctx, d.table, 760, 210, 392, 42);
  } else if (d.layout === "hypothesis") {
    text(slide, ctx, d.question, 86, 190, 1000, 42, { size: 22, bold: true, color: C.teal });
    d.hypothesis.forEach((item, i) => {
      const y = 280 + i * 104;
      ctx.addShape(slide, { x: 88, y, w: 970, h: 76, fill: i === 0 ? "#f5e5df" : i === 1 ? "#edf3ef" : "#ececf6", line: { style: "solid", fill: C.rule, width: 1 } });
      text(slide, ctx, item, 112, y + 18, 916, 40, { size: 19, bold: i === 0 });
    });
  } else if (d.layout === "dataSources") {
    smallTable(slide, ctx, d.table, 76, 190, 1058, 54);
  }
  source(slide, ctx, d.source);
  return slide;
}

export { renderDeckSlide };
`;

async function writeDeck(language, slides) {
  const slidesDir = path.join(WORKSPACE, language === "cn" ? "slides_cn" : "slides_en");
  await fs.mkdir(slidesDir, { recursive: true });
  await fs.writeFile(path.join(WORKSPACE, `deck_shared_${language}.mjs`), shared, "utf8");
  for (let i = 0; i < slides.length; i += 1) {
    const n = String(i + 1).padStart(2, "0");
    const content = [
      `import { renderDeckSlide } from "../deck_shared_${language}.mjs";`,
      `const data = ${JSON.stringify(slides[i], null, 2)};`,
      `export async function slide${n}(presentation, ctx) {`,
      `  return renderDeckSlide(presentation, ctx, data);`,
      `}`,
      "",
    ].join("\n");
    await fs.writeFile(path.join(slidesDir, `slide-${n}.mjs`), content, "utf8");
  }
}

async function writeNotes() {
  await fs.writeFile(path.join(WORKSPACE, "profile-plan.txt"), [
    "task mode: create",
    "primary deck-profile: strategy-leadership",
    "secondary gates: appendix-heavy data provenance; scientific reproducibility",
    "required proof objects: reproduced figures, raw-validation metrics, seasonal table, external-basin diagnostic chart, data-source table",
    "known missing inputs: ERA5/OLR spatial fields are planned but not yet downloaded",
    "",
  ].join("\n"), "utf8");
  await fs.writeFile(path.join(WORKSPACE, "claim-spine.txt"), [
    "Thesis: The project can open as an attribution study of why 2023/24 El Niño produced strong ocean warming but weak atmospheric coupling.",
    "Audience: PhD adviser/group meeting.",
    "Arc: reproduce the paper -> validate with raw data -> isolate spring-summer decoupling -> propose external-basin warmth as the first mechanism to test.",
    "",
  ].join("\n"), "utf8");
  await fs.writeFile(path.join(WORKSPACE, "design-system.txt"), [
    "Slide size: 1280x720.",
    "Visual style: warm paper background, deep ink text, red/teal/blue accents.",
    "Proof grammar: one dominant chart or reproduced figure per slide with compact data table or notes.",
    "Footer: quiet source note on every slide.",
    "Banned motifs: decorative gradients, generic card grids, unverified logos.",
    "",
  ].join("\n"), "utf8");
  await fs.writeFile(path.join(WORKSPACE, "source-notes.txt"), [
    "Identity assets: none used.",
    "Reproduced paper figures: local outputs from Peng et al. 2025 Zenodo source data/code.",
    "Raw validation and new diagnostics: NOAA OISST v2.1, GPCP, NCEP/NCAR via NOAA PSL OPeNDAP.",
    "ERA5/OLR/ORAS5 listed as planned data sources, not used for the plotted results in these decks.",
    "",
  ].join("\n"), "utf8");
}

await writeNotes();
await writeDeck("cn", cn);
await writeDeck("en", en);
