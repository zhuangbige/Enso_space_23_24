import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811");
const FIG = path.join(ROOT, "outputs/research_2026/three_paper_english_figures_20260811");
const OUT = path.join(ROOT, "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_三文献英文图版_20260811.pptx");
const PREVIEW = path.join(TMP, "final-preview");
const LAYOUT = path.join(TMP, "final-layout");

const C = {
  navy: "#0A2234",
  blue: "#2F80B9",
  orange: "#E17600",
  red: "#BE3D3D",
  teal: "#168C82",
  purple: "#7D57AF",
  paleBlue: "#E8F2F8",
  paleOrange: "#FFF1DA",
  paleTeal: "#E7F4F2",
  paleGray: "#F4F7F9",
  midGray: "#526B7C",
  lightGray: "#C7D0D8",
  white: "#FFFFFF",
};

const FONT = "PingFang SC";
const FIGURE_FILES = [
  "q1_ohc300_hovmoller.png",
  "q1_lagrangian_summary.png",
  "q1_arrival_storage.png",
  "q2_fate_partition.png",
  "q3_early_north_to_ne.png",
  "q3_dynamic_chain.png",
  "q3_thermo_return.png",
  "q3_loeo_rmse.png",
];
const FIGURE_BYTES = Object.fromEntries(
  await Promise.all(FIGURE_FILES.map(async (filename) => [filename, await fs.readFile(path.join(FIG, filename))])),
);

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function addText(slide, text, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: options.fontSize ?? 24,
    bold: options.bold ?? false,
    color: options.color ?? C.navy,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "top",
    autoFit: options.autoFit ?? "shrinkText",
    wrap: "square",
    insets: options.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
    lineSpacing: options.lineSpacing ?? 1.05,
    typeface: FONT,
  };
  if (options.name) shape.name = options.name;
  return shape;
}

function addBox(slide, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: options.geometry ?? "roundRect",
    position,
    fill: options.fill ?? C.paleGray,
    line: {
      style: "solid",
      fill: options.lineColor ?? options.fill ?? C.lightGray,
      width: options.lineWidth ?? 1.2,
    },
  });
  if (options.name) shape.name = options.name;
  return shape;
}

function addLine(slide, left, top, width, color = C.lightGray, lineWidth = 1.2) {
  return slide.shapes.add({
    geometry: "line",
    position: { left, top, width, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: lineWidth },
  });
}

function addHeader(slide, eyebrow, title, subtitle = "", titleSize = 34) {
  addText(slide, eyebrow, { left: 54, top: 30, width: 280, height: 28 }, { fontSize: 19, bold: true, color: C.blue });
  addText(slide, title, { left: 54, top: 68, width: 1172, height: 60 }, { fontSize: titleSize, bold: true, color: C.navy });
  addLine(slide, 54, 142, 1172, C.lightGray, 1.3);
  if (subtitle) {
    addText(slide, subtitle, { left: 54, top: 150, width: 1172, height: 28 }, { fontSize: 20, color: C.midGray, alignment: "center" });
  }
}

function addTakeaway(slide, text, color = C.blue) {
  addBox(slide, { left: 54, top: 638, width: 1172, height: 52 }, { fill: color, lineColor: color });
  addText(slide, text, { left: 76, top: 649, width: 1128, height: 32 }, { fontSize: 22, bold: true, color: C.white, alignment: "center", verticalAlignment: "middle" });
}

function addCard(slide, x, y, w, h, fill, lineColor, title, body, titleColor = C.navy, bodyColor = C.navy, bodySize = 21) {
  addBox(slide, { left: x, top: y, width: w, height: h }, { fill, lineColor, lineWidth: 1.4 });
  addText(slide, title, { left: x + 20, top: y + 18, width: w - 40, height: 42 }, { fontSize: 24, bold: true, color: titleColor });
  addText(slide, body, { left: x + 20, top: y + 70, width: w - 40, height: h - 88 }, { fontSize: bodySize, color: bodyColor, lineSpacing: 1.08 });
}

function addImage(slide, filename, position, alt) {
  const image = slide.images.add({
    blob: FIGURE_BYTES[filename],
    contentType: "image/png",
    alt,
    position,
    fit: "contain",
  });
  image.name = filename.replace(/\.png$/, "");
  return image;
}

function setSources(slide, lines) {
  slide.speakerNotes.clear();
  slide.speakerNotes.text = `[Sources]\n${lines.map((line) => `- ${line}`).join("\n")}\n[/Sources]`;
}

function addLegendDots(slide, x, y) {
  const items = [
    ["Other events", "#8FA0AC", 122],
    ["1997", C.orange, 92],
    ["2015", C.blue, 92],
    ["2023", C.teal, 92],
  ];
  let cx = x;
  for (const [label, color, advance] of items) {
    addBox(slide, { left: cx, top: y + 4, width: 14, height: 14 }, { geometry: "ellipse", fill: color, lineColor: color, lineWidth: 0 });
    addText(slide, label, { left: cx + 20, top: y, width: 102, height: 24 }, { fontSize: 18, color: C.midGray });
    cx += advance;
  }
}

function clearSlide(slide) {
  slide.shapes.deleteAll();
  slide.background.fill = C.white;
  slide.speakerNotes.clear();
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(path.join(TMP, "template-starter.pptx")));
if (presentation.slides.items.length !== 16) throw new Error(`Expected 16 slides, got ${presentation.slides.items.length}`);

// Overlay English Python redraws on inherited evidence frames.
addImage(presentation.slides.items[3], "q1_ohc300_hovmoller.png", { left: 54, top: 180, width: 1172, height: 430 }, "Longitude-time evolution of 0–300 m OHC anomalies for 1997, 2015, and 2023");
addImage(presentation.slides.items[4], "q1_lagrangian_summary.png", { left: 54, top: 190, width: 820, height: 390 }, "Lagrangian eastward displacement and active-trajectory release weight");
addImage(presentation.slides.items[5], "q1_arrival_storage.png", { left: 54, top: 190, width: 850, height: 390 }, "140 degree west inflow and eastern-box ocean heat content gain");
addImage(presentation.slides.items[8], "q2_fate_partition.png", { left: 54, top: 185, width: 1172, height: 430 }, "Following January to May partition of eastern-box ocean heat loss");
addImage(presentation.slides.items[13], "q3_thermo_return.png", { left: 54, top: 215, width: 820, height: 370 }, "Event relationships for surface heat loss and westward return");
addImage(presentation.slides.items[14], "q3_loeo_rmse.png", { left: 54, top: 195, width: 820, height: 390 }, "Leave-one-event-out RMSE for northward export and surface heat loss");

// 2. Three literature starting points.
{
  const slide = presentation.slides.items[1];
  clearSlide(slide);
  addHeader(slide, "研究出发点", "三篇文章共同给出“时空路径—闭合收支—耦合门控”", "借鉴图形组织与检验逻辑，不直接移植原论文机制", 33);
  addCard(slide, 54, 205, 330, 330, "none", C.blue,
    "Chakravorty et al. (2021)",
    "• CT/CP事件与阶段对照\n• 经度—时间传播图\n• 纬向与经向输送并列\n\n对应：问题一、问题二",
    C.blue, C.navy, 19);
  addCard(slide, 452, 205, 330, 330, "none", C.orange,
    "Jiang et al. (2025 preprint)",
    "• 三维拉格朗日热预算\n• 南北分量与闭合收支\n• 建立—维持/衰减分期\n\n对应：路径、分配、反馈",
    C.orange, C.navy, 19);
  addCard(slide, 850, 205, 330, 330, "none", C.teal,
    "Leishan Jiang et al. (2026)",
    "• 2023远东太平洋先行增暖\n• MJJ东北风异常\n• 中太平洋西风响应偏弱\n\n对应：问题三的时序门控",
    C.teal, C.navy, 19);
  addTakeaway(slide, "三篇文献把当前主线收束为：先追踪到达，再闭合去向，最后检验耦合时序。", C.blue);
  setSources(slide, [
    "https://doi.org/10.1029/2020JC017075 (Chakravorty et al., 2021; accessed 2026-08-11)",
    "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint; accessed 2026-08-11)",
    "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026; accessed 2026-08-11)",
  ]);
}

// 3. Updated three-question chain.
{
  const slide = presentation.slides.items[2];
  clearSlide(slide);
  addHeader(slide, "研究问题", "三个问题必须由同一条时间有序证据链回答", "发展年早期、发展年MJJ与次年衰减期分开诊断", 33);
  const cards = [
    [54, C.paleOrange, C.orange, "1  到达", "OHC′经度—时间传播\n拉格朗日东移\n140°W输入 + 东箱增量"],
    [452, C.paleBlue, C.blue, "2  分配", "向西返回\n向北/向南输出\n海表散热 + 收支残差"],
    [850, C.paleTeal, C.teal, "3  命运", "JFM早期北向分流\nMJJ东北风与中太平洋风响应\n次年5°N输出 + 海表散热"],
  ];
  for (const [x, fill, color, title, body] of cards) addCard(slide, x, 225, 330, 280, fill, color, title, body, color, C.navy, 21);
  for (const x of [390, 788]) addBox(slide, { left: x, top: 330, width: 48, height: 54 }, { geometry: "rightArrow", fill: C.midGray, lineColor: C.midGray, lineWidth: 0 });
  addBox(slide, { left: 164, top: 545, width: 952, height: 60 }, { fill: C.paleGray, lineColor: C.lightGray });
  addText(slide, "Jan–Jun到达与早期路由   →   MJJ耦合门控   →   following Jan–May去向", { left: 190, top: 562, width: 900, height: 30 }, { fontSize: 23, bold: true, color: C.midGray, alignment: "center" });
  addTakeaway(slide, "先确认“到了多少”，再量化“去了哪里”，最后解释“为什么事件不同”。", C.blue);
  setSources(slide, ["Local project analysis design; windows are defined by the SODA3-derived workflows and Jiang et al. (2026)."]);
}

// 11. Integrated Q3 framework.
{
  const slide = presentation.slides.items[10];
  clearSlide(slide);
  addHeader(slide, "问题三｜整体框架", "早期北向分流能否接上东北风，并最终改变次年释放方式？", "发展年早期输出与次年晚期输出是两个不同窗口", 32);
  const boxes = [
    [54, "none", C.orange, "到达规模", "Jan–Jun\n140°W输入"],
    [290, "none", C.orange, "早期路由", "发展年JFM\n5°N北向分流"],
    [526, "none", C.teal, "东北风门控", "发展年MJJ\nJiang区域NE"],
    [762, "none", C.blue, "风—应力链", "中太平洋风响应\n→ 次年5°N应力"],
    [998, "none", C.teal, "晚期去向", "following Jan–May\n北向输出"],
  ];
  for (const [x, fill, color, title, body] of boxes) addCard(slide, x, 215, 190, 178, fill, color, title, body, color, C.navy, 19);
  for (const x of [247, 483, 719, 955]) addBox(slide, { left: x, top: 278, width: 38, height: 46 }, { geometry: "rightArrow", fill: C.midGray, lineColor: C.midGray, lineWidth: 0 });
  addCard(slide, 54, 435, 420, 132, "none", C.lightGray, "独立调整支路", "向西返回保留为盆地尺度调整结果", C.midGray, C.navy, 20);
  addCard(slide, 806, 435, 382, 132, "none", C.red, "热力支路", "东部SST → 海表散热", C.red, C.navy, 20);
  addBox(slide, { left: 505, top: 450, width: 270, height: 96 }, { fill: "none", lineColor: C.blue });
  addText(slide, "严格按时间连接\n不把两次北向输出混为同一量", { left: 525, top: 470, width: 230, height: 58 }, { fontSize: 21, bold: true, color: C.blue, alignment: "center", verticalAlignment: "middle" });
  addTakeaway(slide, "到达量给出总尺度；早期路由与耦合门控决定后续释放强度和方向。", C.blue);
  setSources(slide, [
    "Local derived datasets: early-routing/Jiang event table and fixed-layer third-question event table (generated 2026-08-10).",
    "https://doi.org/10.1029/2026GL123227 (Jiang et al., 2026; atmospheric coupling context)",
  ]);
}

// 12. New early-routing result.
{
  const slide = presentation.slides.items[11];
  clearSlide(slide);
  addHeader(slide, "问题三｜海洋先行线索", "早期北向分流先于东北风异常，并非既有风场的简单延续", "JFM海洋路由 → MJJ Jiang区域东北风；固定JFM 140°W到达量", 31);
  addLegendDots(slide, 615, 180);
  addImage(slide, "q3_early_north_to_ne.png", { left: 54, top: 210, width: 875, height: 382 }, "JFM northward heat export preceding MJJ Jiang-region northeasterly anomalies across 13 events");
  addCard(slide, 958, 210, 250, 170, "none", C.teal, "跨事件关系", "r = +0.68\np = 0.007\n95% CI  0.23–0.95", C.teal, C.navy, 19);
  addCard(slide, 958, 408, 250, 176, "none", C.orange, "2023时序", "JFM北向输出 +0.95 ZJ\nJFM NE850 −0.74 m s⁻¹\nMJJ NE850 +1.39 SD", C.orange, C.navy, 18);
  addTakeaway(slide, "2023先出现北向热量分流，东北风随后增强；这是严格滞后的观测桥梁。", C.blue);
  setSources(slide, [
    "Local derived statistics: early northward routing to Jiang-region northeasterly relationship tests (generated 2026-08-10).",
    "Local derived event table: 13-event early-routing and atmospheric-window diagnostics.",
    "https://doi.org/10.1029/2026GL123227 (Jiang et al., 2026; MJJ northeasterly definition and coupling context)",
  ]);
}

// 13. Dynamic coupling gate.
{
  const slide = presentation.slides.items[12];
  clearSlide(slide);
  addHeader(slide, "问题三｜动力门控", "东北风接到后续释放链：抑制中太平洋风响应，改变次年北向输出", "发展年MJJ → following Jan–May；13事件残差化关系", 30);
  addLegendDots(slide, 615, 180);
  addImage(slide, "q3_dynamic_chain.png", { left: 54, top: 215, width: 880, height: 370 }, "MJJ northeasterly, central wind response, following 5 degree north stress, and late northward export");
  addBox(slide, { left: 960, top: 205, width: 240, height: 106 }, { fill: C.paleTeal, lineColor: C.teal });
  addText(slide, "NE850 → 中央纬向应力", { left: 980, top: 220, width: 200, height: 38 }, { fontSize: 20, bold: true, color: C.teal });
  addText(slide, "r = −0.56   p = 0.047", { left: 980, top: 270, width: 200, height: 24 }, { fontSize: 18, color: C.navy });
  addBox(slide, { left: 960, top: 333, width: 240, height: 106 }, { fill: C.paleBlue, lineColor: C.blue });
  addText(slide, "U850 → 次年5°N应力", { left: 980, top: 350, width: 200, height: 34 }, { fontSize: 20, bold: true, color: C.blue });
  addText(slide, "r = +0.69   q = 0.014", { left: 980, top: 400, width: 200, height: 24 }, { fontSize: 18, color: C.navy });
  addBox(slide, { left: 960, top: 461, width: 240, height: 126 }, { fill: C.paleOrange, lineColor: C.orange });
  addText(slide, "应力 → 晚期北向输出", { left: 980, top: 478, width: 200, height: 34 }, { fontSize: 20, bold: true, color: C.orange });
  addText(slide, "r = +0.74   q = 0.014\n固定到达量", { left: 980, top: 526, width: 200, height: 46 }, { fontSize: 18, color: C.navy });
  addTakeaway(slide, "发展年早期分流与次年晚期输出不是同一量；中间由东北风与风—应力门控连接。", C.blue);
  setSources(slide, [
    "Local derived datasets: early-routing/Jiang event table and fixed-layer third-question event table.",
    "Local derived statistics: third-question relationship tests and Jiang-aligned event relationships (generated 2026-08-10).",
    "https://doi.org/10.1029/2026GL123227 (Jiang et al., 2026; interpretation of strengthened northeasterlies and weakened central-Pacific westerlies)",
  ]);
}

// 16. Updated synthesis.
{
  const slide = presentation.slides.items[15];
  clearSlide(slide);
  addHeader(slide, "三个问题的统一回答", "到达、早期路由、耦合门控与最终分配可以串成一条主线", "", 34);
  addCard(slide, 54, 190, 350, 300, C.paleOrange, C.orange, "1  暖量是否到达？", "到达。\n路径：OHC′传播与轨迹。\n数量：140°W输入与东箱增量。", C.orange, C.navy, 21);
  addCard(slide, 465, 190, 350, 300, C.paleBlue, C.blue, "2  到达后去哪里？", "共同主路由：向西返回。\n事件差异：北向输出与散热。\n残差必须单列。", C.blue, C.navy, 21);
  addCard(slide, 876, 190, 350, 300, C.paleTeal, C.teal, "3  为何命运不同？", "发展年JFM北向分流领先MJJ东北风。\n风—应力门控影响次年北向输出。\n东部SST门控海表散热。", C.teal, C.navy, 20);
  addBox(slide, { left: 118, top: 530, width: 1044, height: 76 }, { fill: C.paleGray, lineColor: C.lightGray });
  addText(slide, "到达 → 早期路由 → 东北风/中太平洋风响应 → 次年分配\n热力散热与向西返回作为并行支路保留", { left: 150, top: 545, width: 980, height: 50 }, { fontSize: 23, bold: true, color: C.navy, alignment: "center", lineSpacing: 1.05 });
  addTakeaway(slide, "2023不是“没到”：它先表现为更强北向分流，随后伴随东北风增强和次年释放偏弱。", C.red);
  setSources(slide, [
    "Synthesis of local analyses cited on slides 4–15.",
    "https://doi.org/10.1029/2020JC017075",
    "https://doi.org/10.21203/rs.3.rs-7762242/v1",
    "https://doi.org/10.1029/2026GL123227",
  ]);
}

await fs.mkdir(PREVIEW, { recursive: true });
await fs.mkdir(LAYOUT, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(PREVIEW, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(LAYOUT, `${stem}.layout.json`), await layout.text());
}
await writeBlob(path.join(TMP, "final-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));

const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,notes,layout", maxChars: 1000000 });
await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUT);
console.log(JSON.stringify({ output: OUT, slides: presentation.slides.items.length, revision: inspect.revision }, null, 2));
