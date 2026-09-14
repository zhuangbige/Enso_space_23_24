import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_nonh20_rebuild_20260810");
const FIG = path.join(ROOT, "outputs/research_2026/nonh20_ppt_figures");
const OUT = path.join(ROOT, "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_非阈值重构版_20260810.pptx");
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
  addText(slide, eyebrow, { left: 54, top: 30, width: 250, height: 28 }, { fontSize: 19, bold: true, color: C.blue });
  addText(slide, title, { left: 54, top: 68, width: 1172, height: 60 }, { fontSize: titleSize, bold: true, color: C.navy });
  addLine(slide, 54, 142, 1172, C.lightGray, 1.3);
  if (subtitle) {
    addText(slide, subtitle, { left: 54, top: 150, width: 1172, height: 28 }, { fontSize: 20, color: C.midGray, alignment: "center" });
  }
}

function addTakeaway(slide, text, color = C.blue) {
  addBox(slide, { left: 54, top: 638, width: 1172, height: 52 }, { geometry: "roundRect", fill: color, lineColor: color });
  addText(slide, text, { left: 76, top: 649, width: 1128, height: 32 }, { fontSize: 22, bold: true, color: C.white, alignment: "center", verticalAlignment: "middle" });
}

function addCard(slide, x, y, w, h, fill, lineColor, title, body, titleColor = C.navy, bodyColor = C.navy) {
  addBox(slide, { left: x, top: y, width: w, height: h }, { fill, lineColor, lineWidth: 1.4 });
  addText(slide, title, { left: x + 20, top: y + 18, width: w - 40, height: 42 }, { fontSize: 24, bold: true, color: titleColor });
  addText(slide, body, { left: x + 20, top: y + 70, width: w - 40, height: h - 88 }, { fontSize: 21, color: bodyColor, lineSpacing: 1.1 });
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
    ["其他事件", "#8FA0AC"],
    ["1997", C.orange],
    ["2015", C.blue],
    ["2023", C.teal],
  ];
  let cx = x;
  for (const [label, color] of items) {
    addBox(slide, { left: cx, top: y + 4, width: 14, height: 14 }, { geometry: "ellipse", fill: color, lineColor: color, lineWidth: 0 });
    addText(slide, label, { left: cx + 20, top: y, width: 90, height: 24 }, { fontSize: 18, color: C.midGray });
    cx += label === "其他事件" ? 120 : 92;
  }
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(path.join(TMP, "template-starter.pptx")));
if (presentation.slides.items.length !== 15) throw new Error(`Expected 15 slides, got ${presentation.slides.items.length}`);

for (const slide of presentation.slides.items) {
  slide.shapes.deleteAll();
  slide.background.fill = C.white;
  slide.speakerNotes.clear();
}

// 1. Cover
{
  const slide = presentation.slides.items[0];
  addText(slide, "SODA3 · 0–300 m OHC′ · 13个暖事件", { left: 54, top: 44, width: 620, height: 32 }, { fontSize: 21, color: C.blue });
  addText(slide, "厄尔尼诺异常暖量的\n到达、分配与耦合命运", { left: 54, top: 205, width: 930, height: 160 }, { fontSize: 52, bold: true, color: C.navy, lineSpacing: 0.96 });
  addLine(slide, 54, 432, 650, C.blue, 4);
  addText(slide, "问题一：暖量如何到达？    问题二：到达后如何分配？\n问题三：相似到达为何产生不同命运？", { left: 54, top: 468, width: 1060, height: 82 }, { fontSize: 27, bold: true, color: C.midGray, lineSpacing: 1.08 });
  addText(slide, "到达量设定衰减规模；动力与热力耦合门控决定释放效率。", { left: 54, top: 590, width: 1120, height: 42 }, { fontSize: 25, bold: true, color: C.orange });
  setSources(slide, ["Local project synthesis from the SODA3-derived datasets and reports listed in subsequent slides."]);
}

// 2. Literature starting points
{
  const slide = presentation.slides.items[1];
  addHeader(slide, "研究出发点", "两个文献起点，共同指向“路径—收支—反馈”", "", 35);
  addCard(slide, 54, 180, 560, 340, C.paleBlue, C.blue,
    "Chakravorty et al. (2021)",
    "• 给出CT/CP事件分类与边界框架\n• 强调暖异常的空间结构差异\n• 尚未闭合140°W输入与东部固定层收支",
    C.blue);
  addCard(slide, 666, 180, 560, 340, C.paleOrange, C.orange,
    "Jiang et al. (2025 preprint)",
    "• 将拉格朗日热追踪与闭合热收支连接\n• 区分建立期与维持/衰减期\n• 把海洋输送、海表通量与大气反馈组织成回路",
    C.orange);
  addBox(slide, { left: 148, top: 544, width: 984, height: 70 }, { fill: C.paleTeal, lineColor: C.teal });
  addText(slide, "本研究只借鉴方法结构，不把北太平洋机制直接移植到ENSO。", { left: 180, top: 565, width: 920, height: 32 }, { fontSize: 23, bold: true, color: C.teal, alignment: "center" });
  addTakeaway(slide, "因此采用：轨迹证据 + 固定层闭合预算 + 建立/衰减分期 + 双向耦合检验。", C.blue);
  setSources(slide, [
    "https://doi.org/10.1029/2020JC017075 (Chakravorty et al., 2021; accessed 2026-08-10)",
    "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Jiang et al., 2025 preprint; accessed 2026-08-10)",
  ]);
}

// 3. Three-question chain
{
  const slide = presentation.slides.items[2];
  addHeader(slide, "研究问题", "三个问题必须由同一条证据链回答", "发展期与衰减期分开诊断");
  const cards = [
    [54, C.paleOrange, C.orange, "1  到达", "OHC′传播\n拉格朗日东移\n140°W输入 + 东箱增量"],
    [452, C.paleBlue, C.blue, "2  分配", "向西返回\n向北/向南输出\n海表散热 + 收支残差"],
    [850, C.paleTeal, C.teal, "3  命运", "中央储热—风—应力\n东部SST—海表散热\n盆地调整路径"],
  ];
  for (const [x, fill, color, title, body] of cards) {
    addCard(slide, x, 225, 330, 280, fill, color, title, body, color);
  }
  for (const x of [390, 788]) {
    addBox(slide, { left: x, top: 330, width: 48, height: 54 }, { geometry: "rightArrow", fill: C.midGray, lineColor: C.midGray, lineWidth: 0 });
  }
  addBox(slide, { left: 184, top: 545, width: 912, height: 60 }, { fill: C.paleGray, lineColor: C.lightGray });
  addText(slide, "发展期 Jan–Jun：到达与建立   →   following Jan–May：衰减与去向", { left: 210, top: 562, width: 860, height: 30 }, { fontSize: 23, bold: true, color: C.midGray, alignment: "center" });
  addTakeaway(slide, "先确认“到了多少”，再讨论“去了哪里”，最后检验“为何不同”。", C.blue);
  setSources(slide, ["Local project analysis design; phase definitions follow the derived SODA3 workflows."]);
}

// 4. Hovmoller arrival evidence
{
  const slide = presentation.slides.items[3];
  addHeader(slide, "问题一｜传播证据", "0–300 m OHC′显示三次事件均向140°W以东扩展", "统一色标；虚线为140°W，点线为Jan(0)与Jun(0)", 33);
  addImage(slide, "q1_ohc300_hovmoller.png", { left: 54, top: 180, width: 1172, height: 430 }, "1997、2015和2023事件的赤道0至300米海洋热含量距平经度时间图");
  addTakeaway(slide, "1997建立最强；2015与2023也在发展期形成清晰的东部正OHC′。", C.blue);
  setSources(slide, ["Local dataset: data/derived/research_2026/soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv"]);
}

// 5. Lagrangian evidence
{
  const slide = presentation.slides.items[4];
  addHeader(slide, "问题一｜轨迹证据", "正温度异常轨迹均显著东移，但1997的位移最远", "释放权重仅用于轨迹统计");
  addImage(slide, "q1_lagrangian_summary.png", { left: 54, top: 190, width: 820, height: 390 }, "三次事件拉格朗日东移距离与持续参与轨迹权重柱状图");
  addCard(slide, 914, 194, 286, 150, C.paleOrange, C.orange, "加权中位东移", "1997   30.0°\n2015   21.0°\n2023   17.7°", C.orange);
  addCard(slide, 914, 370, 286, 176, C.paleBlue, C.blue, "解释边界", "这是路径诊断，\n不是守恒的拉格朗日热预算。", C.blue);
  addTakeaway(slide, "轨迹方向对垂向设置稳健：三次事件都存在向东传播路径。", C.blue);
  setSources(slide, [
    "Local dataset: data/derived/research_2026/soda3_temp_anomaly_lagrangian_pilot_summary.csv",
    "Local report: outputs/research_2026/soda3_temp_anomaly_lagrangian_pilot/SODA3_TEMP_ANOMALY_LAGRANGIAN_PILOT_CN.md",
  ]);
}

// 6. Arrival and storage
{
  const slide = presentation.slides.items[5];
  addHeader(slide, "问题一｜边界与储存", "140°W输入与东箱OHC′增量共同确认到达", "10°S–5°N，0–300 m，Jan–Jun");
  addImage(slide, "q1_arrival_storage.png", { left: 54, top: 190, width: 850, height: 390 }, "三次事件140度西经输入和东部箱体海洋热含量增量对比图");
  addCard(slide, 930, 194, 260, 144, C.paleOrange, C.orange, "140°W输入", "17.0 / 8.5 / 9.9 ZJ", C.orange);
  addCard(slide, 930, 366, 260, 144, C.paleBlue, C.blue, "东箱OHC′增量", "17.3 / 8.6 / 11.1 ZJ", C.blue);
  addText(slide, "顺序：1997 / 2015 / 2023", { left: 930, top: 532, width: 260, height: 30 }, { fontSize: 20, color: C.midGray, alignment: "center" });
  addTakeaway(slide, "2023不是暖量未达：其140°W输入与东箱增量均不低于2015。", C.red);
  setSources(slide, [
    "Local dataset: data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv",
    "Local report: outputs/research_2026/soda3_three_box_ohc_anomaly_budget/SODA3_THREE_BOX_OHC_ANOMALY_BUDGET_CN.md",
  ]);
}

// 7. Q1 answer
{
  const slide = presentation.slides.items[6];
  addText(slide, "问题一的回答", { left: 54, top: 42, width: 260, height: 30 }, { fontSize: 20, bold: true, color: C.blue });
  addText(slide, "暖量确实到达东太平洋，\n且由两类独立证据共同确认", { left: 54, top: 190, width: 1050, height: 150 }, { fontSize: 48, bold: true, color: C.navy, lineSpacing: 0.98 });
  addLine(slide, 54, 390, 1172, C.lightGray, 1.5);
  addText(slide, "路径证据", { left: 54, top: 430, width: 180, height: 34 }, { fontSize: 27, bold: true, color: C.orange });
  addText(slide, "OHC′向东扩展；释放加权轨迹中位东移17.7°–30.0°。", { left: 250, top: 430, width: 910, height: 40 }, { fontSize: 25, color: C.navy });
  addText(slide, "收支证据", { left: 54, top: 495, width: 180, height: 34 }, { fontSize: 27, bold: true, color: C.blue });
  addText(slide, "140°W净输入为正，并伴随东部0–300 m OHC′增加。", { left: 250, top: 495, width: 910, height: 40 }, { fontSize: 25, color: C.navy });
  addText(slide, "边界", { left: 54, top: 560, width: 180, height: 34 }, { fontSize: 27, bold: true, color: C.teal });
  addText(slide, "轨迹回答“从哪里来”；闭合预算回答“到了多少”。", { left: 250, top: 560, width: 910, height: 40 }, { fontSize: 25, color: C.navy });
  setSources(slide, ["Synthesis of the local datasets cited on slides 4–6."]);
}

// 8. Budget method
{
  const slide = presentation.slides.items[7];
  addHeader(slide, "问题二｜方法", "到达后，用质量闭合的三箱OHC′预算追踪去向", "固定层：10°S–5°N，0–300 m");
  addCard(slide, 54, 190, 340, 160, C.paleGray, C.lightGray, "固定层储热", "OHC′ = ρ₀cₚ ∭ T′ dV\n不依赖暖阈值", C.navy);
  addCard(slide, 54, 380, 340, 174, C.paleTeal, C.teal, "闭合约束", "四边界体积输送校正\n体积闭合误差 < 4×10⁻¹⁴ Sv", C.teal);
  addBox(slide, { left: 488, top: 290, width: 360, height: 150 }, { fill: C.paleOrange, lineColor: C.orange, lineWidth: 2 });
  addText(slide, "东箱\n140°W–80°W", { left: 528, top: 326, width: 280, height: 78 }, { fontSize: 30, bold: true, color: C.navy, alignment: "center", verticalAlignment: "middle" });
  addBox(slide, { left: 405, top: 338, width: 76, height: 56 }, { geometry: "leftArrow", fill: C.blue, lineColor: C.blue, lineWidth: 0 });
  addText(slide, "向西返回", { left: 405, top: 407, width: 100, height: 30 }, { fontSize: 20, bold: true, color: C.blue, alignment: "center" });
  addBox(slide, { left: 635, top: 210, width: 66, height: 72 }, { geometry: "upArrow", fill: C.red, lineColor: C.red, lineWidth: 0 });
  addText(slide, "海表散热", { left: 600, top: 180, width: 136, height: 28 }, { fontSize: 20, bold: true, color: C.red, alignment: "center" });
  addBox(slide, { left: 758, top: 220, width: 62, height: 64 }, { geometry: "upArrow", fill: C.orange, lineColor: C.orange, lineWidth: 0 });
  addText(slide, "向北输出", { left: 736, top: 188, width: 110, height: 28 }, { fontSize: 20, bold: true, color: C.orange, alignment: "center" });
  addBox(slide, { left: 758, top: 448, width: 62, height: 64 }, { geometry: "downArrow", fill: C.purple, lineColor: C.purple, lineWidth: 0 });
  addText(slide, "向南输出", { left: 736, top: 520, width: 110, height: 28 }, { fontSize: 20, bold: true, color: C.purple, alignment: "center" });
  addBox(slide, { left: 866, top: 338, width: 76, height: 56 }, { geometry: "leftArrow", fill: C.teal, lineColor: C.teal, lineWidth: 0 });
  addText(slide, "残差", { left: 870, top: 407, width: 70, height: 28 }, { fontSize: 20, bold: true, color: C.teal, alignment: "center" });
  addCard(slide, 966, 212, 238, 330, C.paleBlue, C.blue, "解释规则", "正值：离开东箱\n\n残差：单列，不命名通道\n\n总焓收敛：对温标零点不敏感", C.blue);
  addTakeaway(slide, "预算回答的是固定层OHC′去向，而不是某一温度阈值以上的暖水体积。", C.blue);
  setSources(slide, [
    "Local dataset: data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv",
    "Local reference sensitivity: data/derived/research_2026/soda3_three_box_ohc_anomaly_face_reference_sensitivity.csv",
  ]);
}

// 9. Fate partition
{
  const slide = presentation.slides.items[8];
  addHeader(slide, "问题二｜结果", "向西返回是三次事件共同的最大已识别水平去向", "following Jan–May；正值为输出，负值为输入或收支残差", 32);
  addImage(slide, "q2_fate_partition.png", { left: 54, top: 185, width: 1172, height: 430 }, "三次事件东部箱体热含量损失及向西、向北、向南、海表和残差分解");
  addTakeaway(slide, "2023北向输出与海表散热较弱但非零；收支残差仍需单独解释。", C.blue);
  setSources(slide, ["Local derived dataset: 13-event fixed-layer third-question event table (generated 2026-08-10)."]);
}

// 10. Q2 answer
{
  const slide = presentation.slides.items[9];
  addHeader(slide, "问题二的回答", "共同主路由稳定，释放支路强度却显著不同", "following Jan–May累计能量（ZJ）");
  addCard(slide, 54, 205, 350, 330, C.paleOrange, C.orange, "1997", "东箱损失 21.8\n向西返回 9.5\n向北输出 5.7\n海表散热 4.9\n收支残差 −0.5", C.orange);
  addCard(slide, 465, 205, 350, 330, C.paleBlue, C.blue, "2015", "东箱损失 19.9\n向西返回 8.6\n向北输出 3.0\n海表散热 1.5\n收支残差 −6.4", C.blue);
  addCard(slide, 876, 205, 350, 330, C.paleTeal, C.teal, "2023", "东箱损失 16.0\n向西返回 9.5\n向北输出 2.2\n海表散热 0.5\n向南输出 −0.7", C.teal);
  addBox(slide, { left: 154, top: 565, width: 972, height: 50 }, { fill: C.paleGray, lineColor: C.lightGray });
  addText(slide, "共同项：向西返回   ｜   差异项：向北输出与海表散热   ｜   未闭合项：残差", { left: 178, top: 578, width: 924, height: 28 }, { fontSize: 22, bold: true, color: C.navy, alignment: "center" });
  addTakeaway(slide, "到达后的暖量命运发生“强度变化 + 方向重组”，不能只看一个边界。", C.blue);
  setSources(slide, ["Local derived dataset: 13-event fixed-layer third-question event table (generated 2026-08-10)."]);
}

// 11. Q3 framing
{
  const slide = presentation.slides.items[10];
  addHeader(slide, "问题三｜框架", "相近到达量，为何走向不同？关键在两个耦合门控", "2015与2023的140°W输入分别为8.5与9.9 ZJ", 33);
  addBox(slide, { left: 70, top: 220, width: 178, height: 88 }, { fill: C.paleOrange, lineColor: C.orange });
  addText(slide, "到达量\n控制总规模", { left: 88, top: 240, width: 142, height: 52 }, { fontSize: 24, bold: true, color: C.orange, alignment: "center" });
  addBox(slide, { left: 270, top: 238, width: 64, height: 50 }, { geometry: "rightArrow", fill: C.midGray, lineColor: C.midGray, lineWidth: 0 });
  addCard(slide, 354, 188, 370, 180, C.paleBlue, C.blue, "动力门控", "中央OHC′ → u850 → 5°N应力\n→ 北向输出", C.blue);
  addCard(slide, 354, 400, 370, 160, C.paleOrange, C.red, "热力门控", "东部SST → 海表散热", C.red);
  addBox(slide, { left: 748, top: 238, width: 64, height: 50 }, { geometry: "rightArrow", fill: C.midGray, lineColor: C.midGray, lineWidth: 0 });
  addCard(slide, 832, 188, 378, 372, C.paleTeal, C.teal, "三事件关键量", "中央OHC′：1.22 / 1.02 / 0.19\nu850：5.25 / 3.37 / 0.29 m s⁻¹\n5°N应力：0.0111 / 0.0058 / 0.0018 N m⁻²\n\n顺序：1997 / 2015 / 2023", C.teal);
  addText(slide, "向西返回：作为独立的盆地调整支路检验", { left: 70, top: 430, width: 250, height: 100 }, { fontSize: 22, bold: true, color: C.teal, alignment: "center", verticalAlignment: "middle" });
  addTakeaway(slide, "到达量控制可衰减规模；耦合门控决定暖量以何种方式释放。", C.blue);
  setSources(slide, ["Local derived dataset: 13-event fixed-layer third-question event table (generated 2026-08-10)."]);
}

// 12. Dynamic branch
{
  const slide = presentation.slides.items[11];
  addHeader(slide, "问题三｜动力分支", "13事件支持：中央储热 → 风 → 5°N应力 → 北向输出", "残差化散点；第三步固定140°W到达量", 32);
  addLegendDots(slide, 610, 180);
  addImage(slide, "q3_dynamic_chain.png", { left: 54, top: 215, width: 880, height: 370 }, "十三个事件的中央海洋热含量、低层风、五度北应力与北向输出残差关系");
  addBox(slide, { left: 960, top: 205, width: 240, height: 106 }, { fill: C.paleBlue, lineColor: C.blue });
  addText(slide, "中央OHC′ → u850", { left: 980, top: 220, width: 200, height: 38 }, { fontSize: 21, bold: true, color: C.blue });
  addText(slide, "r = 0.65   q = 0.018", { left: 980, top: 270, width: 200, height: 24 }, { fontSize: 18, color: C.navy });
  addBox(slide, { left: 960, top: 333, width: 240, height: 106 }, { fill: C.paleOrange, lineColor: C.orange });
  addText(slide, "u850 → 5°N应力", { left: 980, top: 350, width: 200, height: 34 }, { fontSize: 21, bold: true, color: C.orange });
  addText(slide, "r = 0.69   q = 0.014", { left: 980, top: 400, width: 200, height: 24 }, { fontSize: 18, color: C.navy });
  addBox(slide, { left: 960, top: 461, width: 240, height: 126 }, { fill: C.paleTeal, lineColor: C.teal });
  addText(slide, "应力 → 北向输出", { left: 980, top: 478, width: 200, height: 34 }, { fontSize: 21, bold: true, color: C.teal });
  addText(slide, "r = 0.74   q = 0.014\n固定到达量", { left: 980, top: 526, width: 200, height: 46 }, { fontSize: 18, color: C.navy });
  addTakeaway(slide, "第一步bootstrap区间跨零：中央储热是重要约束，但不是单一决定因子。", C.blue);
  setSources(slide, [
    "Local derived dataset: 13-event fixed-layer third-question event table (generated 2026-08-10).",
    "Local derived statistics: third-question relationship tests (generated 2026-08-10).",
  ]);
}

// 13. Thermodynamic branch and westward return
{
  const slide = presentation.slides.items[12];
  addHeader(slide, "问题三｜热力与调整", "热力分支可解释散热；向西返回仍缺少直接门控机制", "两组关系均固定140°W到达量", 31);
  addLegendDots(slide, 610, 180);
  addImage(slide, "q3_thermo_return.png", { left: 54, top: 215, width: 820, height: 370 }, "十三个事件的东部海表温度与散热以及五度北应力与向西返回残差关系");
  addCard(slide, 906, 215, 294, 150, C.paleOrange, C.red, "东部SST → 海表散热", "r = 0.65   q = 0.016\n95% CI：0.24–0.91", C.red);
  addCard(slide, 906, 400, 294, 166, C.paleTeal, C.teal, "5°N应力 → 向西返回", "r = −0.31   p = 0.306\n未通过显著性检验", C.teal);
  addTakeaway(slide, "向西返回需进一步诊断SSH、密度结构与盆地调整，不能归因于局地应力。", C.blue);
  setSources(slide, [
    "Local derived dataset: 13-event fixed-layer third-question event table (generated 2026-08-10).",
    "Local derived statistics: third-question relationship tests (generated 2026-08-10).",
  ]);
}

// 14. LOEO robustness
{
  const slide = presentation.slides.items[13];
  addHeader(slide, "问题三｜稳健性", "加入耦合门控后，留一事件预测显著改善", "n = 13；RMSE越低越好", 33);
  addImage(slide, "q3_loeo_rmse.png", { left: 54, top: 195, width: 820, height: 390 }, "北向输出和散热模型在留一事件检验中的标准化均方根误差");
  addCard(slide, 914, 205, 286, 150, C.paleOrange, C.orange, "北向输出", "RMSE  0.75 → 0.55\n相关  0.63 → 0.82", C.orange);
  addCard(slide, 914, 386, 286, 150, C.paleBlue, C.red, "海表散热", "RMSE  0.93 → 0.77\n相关  0.35 → 0.62", C.red);
  addTakeaway(slide, "耦合变量提供独立信息，但证据层级仍是统计约束，而非因果实验。", C.blue);
  setSources(slide, ["Local derived statistics: leave-one-event-out third-question models (generated 2026-08-10)."]);
}

// 15. Synthesis
{
  const slide = presentation.slides.items[14];
  addHeader(slide, "三个问题的统一回答", "到达、分配与耦合命运可以被同一框架连接", "", 35);
  addCard(slide, 54, 190, 350, 300, C.paleOrange, C.orange, "1  暖量是否到达？", "到达。\n路径：OHC′传播与轨迹。\n数量：140°W输入与东箱增量。", C.orange);
  addCard(slide, 465, 190, 350, 300, C.paleBlue, C.blue, "2  到达后去哪里？", "主路由：向西返回。\n事件差异：北向输出与散热。\n残差必须单列。", C.blue);
  addCard(slide, 876, 190, 350, 300, C.paleTeal, C.teal, "3  为何命运不同？", "到达量控制总规模。\n动力门控北向释放。\n东部SST门控海表散热。", C.teal);
  addBox(slide, { left: 118, top: 530, width: 1044, height: 76 }, { fill: C.paleGray, lineColor: C.lightGray });
  addText(slide, "路径 → 闭合收支 → 建立/衰减分期 → 动力与热力反馈\n向西返回保留为待解释的盆地调整支路", { left: 150, top: 545, width: 980, height: 50 }, { fontSize: 23, bold: true, color: C.navy, alignment: "center", lineSpacing: 1.05 });
  addTakeaway(slide, "2023的关键不是“没到”，而是释放门控较弱、暖量命运不同。", C.red);
  setSources(slide, [
    "Synthesis of local analyses cited on slides 4–14.",
    "https://doi.org/10.21203/rs.3.rs-7762242/v1 (methodological framing only; accessed 2026-08-10)",
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

const inspect = await presentation.inspect({
  kind: "slide,textbox,shape,image,notes,layout",
  maxChars: 200000,
});
await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUT);
console.log(JSON.stringify({ output: OUT, slides: presentation.slides.items.length, revision: inspect.revision }, null, 2));
