import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const BUILD = path.join(ROOT, "outputs/research_2026/ppt/question_one_two_review_revision_build_20260809");
const FINAL = path.join(ROOT, "outputs/research_2026/ppt/厄尔尼诺异常暖量到达与去向_审查修订版_20260809.pptx");
const FIG_CHAK = path.join(ROOT, "outputs/research_2026/three_questions_full_report_assets_20260805/chakravorty2021_figure8_excerpt.png");
const FIG_PATHWAY = path.join(ROOT, "outputs/research_2026/three_questions_figure_package_20260805/01_main_figures/Fig02_CT_CP_three_box_arrival_and_fate.png");
const FIG_H20 = path.join(ROOT, "outputs/research_2026/soda3_h20/soda3_h20_hovmoller_1997_2015_2023.png");

const W = 1280;
const H = 720;
const WHITE = "#FFFFFF";
const INK = "#0A2133";
const MUTED = "#35566B";
const RULE = "#B8BCC4";
const PANEL = "#EDF3F6";
const BLUE = "#2C7FB8";
const BLUE_LIGHT = "#DDEFF7";
const ORANGE = "#D97706";
const ORANGE_LIGHT = "#FFF0D8";
const RED = "#B73A3A";
const RED_LIGHT = "#F9E2E0";
const TEAL = "#16877A";
const TEAL_LIGHT = "#DDF2EE";
const PURPLE = "#7E5AA6";
const PURPLE_LIGHT = "#EEE7F6";
const FONT = "PingFang SC";
const MATH = "Arial Unicode MS";

async function writeBlob(file, blob) {
  await fs.writeFile(file, new Uint8Array(await blob.arrayBuffer()));
}

async function readBytes(file) {
  const buffer = await fs.readFile(file);
  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
}

function addText(slide, name, value, x, y, w, h, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    fontSize: options.fontSize ?? 26,
    bold: options.bold ?? false,
    color: options.color ?? INK,
    alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "top",
    autoFit: options.autoFit ?? "shrinkText",
    wrap: "square",
    typeface: options.typeface ?? FONT,
    insets: options.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
    lineSpacing: options.lineSpacing ?? 1.0,
  };
  return shape;
}

function addRect(slide, name, x, y, w, h, fill = PANEL, line = "none", width = 0, radius = 0) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: line, width },
    ...(radius ? { borderRadius: radius } : {}),
  });
}

function addRule(slide, x, y, w, color = RULE, width = 1.5) {
  return slide.shapes.add({
    geometry: "line",
    name: `rule-${x}-${y}`,
    position: { left: x, top: y, width: w, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width },
  });
}

function addTitle(slide, value, kicker = "问题一") {
  addText(slide, "kicker", kicker, 54, 30, 180, 32, {
    fontSize: 22,
    bold: true,
    color: BLUE,
    valign: "middle",
  });
  addText(slide, "slide-title", value, 54, 70, 1172, 58, {
    fontSize: 40,
    bold: true,
    color: INK,
    valign: "middle",
    autoFit: "none",
  });
  addRule(slide, 54, 142, 1172, RULE, 1.4);
}

function addTakeaway(slide, value, color = BLUE) {
  addRect(slide, "takeaway-band", 54, 635, 1172, 55, color, color, 0, 8);
  addText(slide, "takeaway-text", value, 78, 644, 1124, 38, {
    fontSize: 25,
    bold: true,
    color: WHITE,
    align: "center",
    valign: "middle",
    autoFit: "none",
  });
}

function addNotes(slide, sources) {
  slide.speakerNotes.textFrame.setText(`[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}\n[/Sources]`);
  slide.speakerNotes.setVisible(false);
}

function addImage(slide, bytes, alt, x, y, w, h, crop = undefined, fit = "contain") {
  return slide.images.add({
    blob: bytes,
    contentType: "image/png",
    alt,
    fit,
    position: { left: x, top: y, width: w, height: h },
    ...(crop ? { crop } : {}),
  });
}

function addGroupedBar(slide, position, categories, series, max, majorUnit) {
  return slide.charts.add("bar", {
    position,
    categories,
    series,
    hasLegend: true,
    legend: {
      position: "top",
      overlay: false,
      textStyle: { fontSize: "20px", color: INK, bold: true, typeface: FONT },
      fill: "none",
      line: { style: "solid", fill: "none", width: 0 },
    },
    barOptions: { direction: "column", grouping: "clustered", gapWidth: 70 },
    xAxis: {
      visible: true,
      textStyle: { fontSize: "20px", color: INK, bold: true, typeface: FONT },
      line: { style: "solid", fill: INK, width: 1.2 },
      majorGridlines: null,
    },
    yAxis: {
      visible: true,
      min: 0,
      max,
      majorUnit,
      textStyle: { fontSize: "18px", color: MUTED, typeface: FONT },
      line: { style: "solid", fill: "none", width: 0 },
      majorGridlines: { style: "solid", fill: "#DDE5E9", width: 1 },
    },
    dataLabels: {
      showValue: true,
      position: "outEnd",
      textStyle: { fontSize: "21px", color: INK, bold: true, typeface: FONT },
      fill: "none",
      line: { style: "solid", fill: "none", width: 0 },
    },
    chartFill: WHITE,
    chartLine: { style: "solid", fill: "none", width: 0 },
    plotAreaFill: WHITE,
    plotAreaLine: { style: "solid", fill: "none", width: 0 },
  });
}

function addLineChart(slide, position, categories, series) {
  return slide.charts.add("line", {
    position,
    categories,
    series,
    hasLegend: true,
    legend: {
      position: "top",
      overlay: false,
      textStyle: { fontSize: "18px", color: INK, bold: true, typeface: FONT },
      fill: "none",
      line: { style: "solid", fill: "none", width: 0 },
    },
    xAxis: {
      visible: true,
      textStyle: { fontSize: "17px", color: INK, typeface: FONT },
      line: { style: "solid", fill: INK, width: 1.2 },
      majorGridlines: null,
    },
    yAxis: {
      visible: true,
      min: -0.5,
      max: 0.7,
      majorUnit: 0.2,
      numberFormatCode: "0.0",
      textStyle: { fontSize: "17px", color: MUTED, typeface: FONT },
      line: { style: "solid", fill: "none", width: 0 },
      majorGridlines: { style: "solid", fill: "#DDE5E9", width: 1 },
    },
    chartFill: WHITE,
    chartLine: { style: "solid", fill: "none", width: 0 },
    plotAreaFill: WHITE,
    plotAreaLine: { style: "solid", fill: "none", width: 0 },
    lineOptions: { grouping: "standard" },
  });
}

function addArrow(slide, name, geometry, x, y, w, h, fill) {
  return slide.shapes.add({
    geometry,
    name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill, width: 0 },
  });
}

function addCircle(slide, name, cx, cy, diameter, fill, line = fill, lineWidth = 0) {
  return slide.shapes.add({
    geometry: "ellipse",
    name,
    position: { left: cx - diameter / 2, top: cy - diameter / 2, width: diameter, height: diameter },
    fill,
    line: { style: "solid", fill: line, width: lineWidth },
  });
}

function addDotWhisker(slide, name, y, mean, low, high, color, xMap, valueDy) {
  const lowX = xMap(low);
  const highX = xMap(high);
  const meanX = xMap(mean);
  slide.shapes.add({
    geometry: "line",
    name: `${name}-whisker`,
    position: { left: lowX, top: y, width: highX - lowX, height: 0 },
    fill: "none",
    line: { style: "solid", fill: color, width: 3 },
  });
  for (const [suffix, x] of [["low", lowX], ["high", highX]]) {
    slide.shapes.add({
      geometry: "line",
      name: `${name}-${suffix}-cap`,
      position: { left: x, top: y - 7, width: 0, height: 14 },
      fill: "none",
      line: { style: "solid", fill: color, width: 2.4 },
    });
  }
  addCircle(slide, `${name}-mean`, meanX, y, 15, color);
  const label = `${mean >= 0 ? "+" : "−"}${Math.abs(mean).toFixed(2)}`;
  addText(slide, `${name}-value`, label, meanX + 10, y + valueDy, 76, 24, {
    fontSize: 17,
    bold: true,
    color,
    valign: "middle",
    autoFit: "none",
  });
}

function addMiniBudgetPanel(slide, x, eventLabel, values) {
  const panelW = 356;
  const plotTop = 242;
  const plotBottom = 556;
  const zeroY = 438;
  const posScale = (zeroY - plotTop) / 5.2;
  const negScale = (plotBottom - zeroY) / 3.1;
  const labels = ["5°N", "Cx", "海表", "残差", "储量"];
  const fills = [ORANGE, BLUE, RED, TEAL, INK];
  addText(slide, `event-${eventLabel}`, eventLabel, x, 178, panelW, 36, {
    fontSize: 29,
    bold: true,
    color: INK,
    align: "center",
    autoFit: "none",
  });
  addRule(slide, x + 12, zeroY, panelW - 24, RULE, 1.3);
  values.forEach((value, i) => {
    const barX = x + 22 + i * 67;
    const barW = 43;
    const barH = value >= 0 ? value * posScale : Math.abs(value) * negScale;
    const barY = value >= 0 ? zeroY - barH : zeroY;
    addRect(slide, `${eventLabel}-bar-${i}`, barX, barY, barW, Math.max(barH, 3), fills[i], fills[i], 0, 3);
    const valueText = `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`;
    const labelY = value >= 0 ? barY - 27 : barY + barH + 4;
    addText(slide, `${eventLabel}-value-${i}`, valueText, barX - 16, labelY, 76, 24, {
      fontSize: 17,
      bold: true,
      color: fills[i],
      align: "center",
      autoFit: "none",
    });
    addText(slide, `${eventLabel}-label-${i}`, labels[i], barX - 11, 578, 66, 26, {
      fontSize: 18,
      bold: true,
      color: INK,
      align: "center",
      autoFit: "none",
    });
  });
}

async function main() {
  await fs.mkdir(BUILD, { recursive: true });
  await fs.mkdir(path.dirname(FINAL), { recursive: true });

  const [chak, pathway, h20] = await Promise.all([
    readBytes(FIG_CHAK),
    readBytes(FIG_PATHWAY),
    readBytes(FIG_H20),
  ]);

  const deck = Presentation.create({ slideSize: { width: W, height: H } });
  deck.theme.colorScheme = {
    name: "Pacific Heat Arrival",
    themeColors: {
      accent1: BLUE,
      accent2: ORANGE,
      accent3: TEAL,
      accent4: RED,
      accent5: MUTED,
      accent6: "#7E5AA6",
      bg1: WHITE,
      bg2: PANEL,
      tx1: INK,
      tx2: MUTED,
      dk1: INK,
      dk2: MUTED,
      lt1: WHITE,
      lt2: PANEL,
      hlink: BLUE,
      folHlink: TEAL,
    },
  };

  // 1. Cover — based on Codex Grid slide-01 stacked-text hierarchy.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addText(slide, "cover-kicker", "SODA3 · CT/CP · 1997/2015/2023", 54, 42, 760, 36, {
      fontSize: 24,
      bold: true,
      color: BLUE,
      valign: "middle",
    });
    addText(slide, "cover-title", "厄尔尼诺异常暖量的\n到达与去向", 54, 168, 1050, 220, {
      fontSize: 70,
      bold: true,
      color: INK,
      valign: "bottom",
      autoFit: "none",
      lineSpacing: 0.92,
    });
    addRule(slide, 54, 435, 620, BLUE, 5);
    addText(slide, "cover-subtitle", "问题一：是否越过140°W？　问题二：跨过5°N后去了哪里？", 54, 475, 1120, 58, {
      fontSize: 32,
      bold: true,
      color: MUTED,
      valign: "middle",
      autoFit: "none",
    });
    addText(slide, "cover-answer", "回答：异常暖量越界并形成东部储存；北侧显式损失以西向输出和海表失热为主。", 54, 565, 1140, 58, {
      fontSize: 28,
      bold: true,
      color: ORANGE,
      valign: "middle",
      autoFit: "none",
    });
    addNotes(slide, [
      "Local SODA3.15.2 analysis: scripts/analyze_soda3_three_box_warm_heat_fate.py",
      "Local event comparison: outputs/research_2026/enso_1997_2015_2023_warm_heat_fate_bridge/",
    ]);
  }

  // 2. Literature bridge — Codex Grid slide-08 half-text/half-image silhouette.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "Chakravorty等刻画170°E与南北边界，但未量化140°W东部输入");
    addText(slide, "prior-claim", "Chakravorty et al. (2021)", 54, 186, 400, 42, {
      fontSize: 28,
      bold: true,
      color: BLUE,
    });
    addText(slide, "prior-body", "CT\n西太平洋蓄热 → 赤道东传 → 成熟期极向放电\n\nCP\n盆地尺度充放电循环较弱", 54, 248, 420, 280, {
      fontSize: 28,
      bold: true,
      color: INK,
      lineSpacing: 1.08,
    });
    addRect(slide, "figure-frame", 500, 174, 726, 394, "#F7FAFB", RULE, 1.2, 8);
    addImage(slide, chak, "Chakravorty et al. 2021 Figure 8 showing normalized zonal and meridional warm-water transports and WWV for CT and CP El Nino", 520, 194, 686, 354);
    addTakeaway(slide, "本文把固定门框架向东推进到140°W控制体输入与东部异常暖量储存。");
    addNotes(slide, [
      "Chakravorty et al. (2021), Revisiting the Recharge and Discharge Processes for Different Flavors of El Niño, JGR Oceans, https://doi.org/10.1029/2020JC017075",
      FIG_CHAK,
    ]);
  }

  // 3. Method — Codex Grid slide-17 process/timeline silhouette.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "跨140°W判断越界，东部H₂₀增长判断储存");

    addText(slide, "formula-q-label", "断面异常暖量输送", 54, 168, 300, 34, { fontSize: 24, bold: true, color: ORANGE });
    addText(slide, "formula-q", "Qwarm,20 = ρ₀cₚ ∬ vₙ χ₂₀ dA", 54, 208, 560, 52, {
      fontSize: 28,
      bold: true,
      color: INK,
      typeface: MATH,
      valign: "middle",
      autoFit: "none",
    });
    addText(slide, "formula-h20-label", "固定箱体异常暖量储存", 674, 168, 330, 34, { fontSize: 24, bold: true, color: BLUE });
    addText(slide, "formula-h20", "χ₂₀ = max(T−20°C, 0)\nH₂₀ = ρ₀cₚ ∭ χ₂₀ dV", 674, 200, 552, 70, {
      fontSize: 27,
      bold: true,
      color: INK,
      typeface: MATH,
      valign: "middle",
      autoFit: "none",
    });

    addRect(slide, "boundary-evidence", 54, 290, 560, 82, ORANGE_LIGHT, ORANGE, 1.5, 8);
    addText(slide, "boundary-evidence-text", "Q′₁₄₀W > 0　→　异常暖量越过140°W", 78, 311, 512, 40, {
      fontSize: 25, bold: true, color: ORANGE, align: "center", valign: "middle", autoFit: "none", typeface: MATH,
    });
    addRect(slide, "storage-evidence", 674, 290, 552, 82, BLUE_LIGHT, BLUE, 1.5, 8);
    addText(slide, "storage-evidence-text", "ΔH′₂₀,E > 0　→　东部形成异常暖量储存", 698, 311, 504, 40, {
      fontSize: 25, bold: true, color: BLUE, align: "center", valign: "middle", autoFit: "none", typeface: MATH,
    });

    // Connectors first so they remain behind the boxes.
    slide.shapes.add({
      geometry: "rightArrow",
      name: "arrow-west-central",
      position: { left: 360, top: 458, width: 118, height: 38 },
      fill: BLUE,
      line: { style: "solid", fill: BLUE, width: 0 },
    });
    slide.shapes.add({
      geometry: "rightArrow",
      name: "arrow-central-east",
      position: { left: 804, top: 458, width: 118, height: 38 },
      fill: ORANGE,
      line: { style: "solid", fill: ORANGE, width: 0 },
    });
    addRect(slide, "west-box", 62, 414, 298, 116, BLUE_LIGHT, BLUE, 2, 8);
    addRect(slide, "central-box", 478, 414, 326, 116, PANEL, MUTED, 2, 8);
    addRect(slide, "east-box", 922, 414, 298, 116, ORANGE_LIGHT, ORANGE, 2, 8);
    addText(slide, "west-box-text", "西箱\n160°E—180°", 82, 432, 258, 76, { fontSize: 27, bold: true, align: "center", valign: "middle" });
    addText(slide, "central-box-text", "中箱\n180°—140°W", 498, 432, 286, 76, { fontSize: 27, bold: true, align: "center", valign: "middle" });
    addText(slide, "east-box-text", "东箱\n140°W—80°W", 942, 432, 258, 76, { fontSize: 27, bold: true, align: "center", valign: "middle" });
    addText(slide, "gate-label-180", "180°", 374, 420, 92, 30, { fontSize: 20, bold: true, color: BLUE, align: "center" });
    addText(slide, "gate-label-140", "140°W", 808, 420, 110, 30, { fontSize: 20, bold: true, color: ORANGE, align: "center" });

    addText(slide, "method-note-1", "ρ₀为Boussinesq参考密度；Qwarm,20为PW，按每月实际秒数积分为ZJ。", 54, 552, 1172, 28, {
      fontSize: 18, bold: true, color: MUTED, align: "center", autoFit: "none",
    });
    addText(slide, "method-note-2", "先计算完整非线性H₂₀与Qwarm,20，再逐日历月去气候态与趋势；区域10°S—5°N、0—300 m。", 54, 584, 1172, 28, {
      fontSize: 18, bold: true, color: MUTED, align: "center", autoFit: "none",
    });
    addTakeaway(slide, "两项共同支持：异常暖量到达并在东部建立暖量库；发展期为Jun(0)—Nov(0)。", MUTED);
    addNotes(slide, [
      "Chakravorty et al. (2021) provides the 20°C warm-water framework and 5°N/10°S transport boundaries: https://doi.org/10.1029/2020JC017075",
      "The fixed 0–300 m three-box control volume and 140°W gate are project diagnostics: scripts/analyze_soda3_three_box_warm_heat_fate.py",
    ]);
  }

  // 4. Pathway evidence — two clean native charts, avoiding the unrelated fate panels.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "CT和CP的发展期均出现140°W东向异常暖量输送增强");
    addText(slide, "ct-panel-title", "CT 合成", 54, 170, 560, 38, { fontSize: 27, bold: true, color: ORANGE, align: "center" });
    addText(slide, "cp-panel-title", "CP 合成", 666, 170, 560, 38, { fontSize: 27, bold: true, color: BLUE, align: "center" });
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"];
    addLineChart(
      slide,
      { left: 54, top: 216, width: 560, height: 386 },
      months,
      [
        {
          name: "180°",
          categories: months,
          values: [-0.101, 0.115, 0.244, 0.338, 0.235, 0.148, 0.232, 0.377, 0.479, 0.443, 0.361],
          line: { style: "solid", width: 3, fill: INK },
          marker: { symbol: "circle", size: 5 },
        },
        {
          name: "140°W",
          categories: months,
          values: [0.041, 0.190, 0.375, 0.495, 0.590, 0.495, 0.405, 0.329, 0.340, 0.413, 0.393],
          line: { style: "solid", width: 4, fill: BLUE },
          marker: { symbol: "circle", size: 5 },
        },
      ],
    );
    addLineChart(
      slide,
      { left: 666, top: 216, width: 560, height: 386 },
      months,
      [
        {
          name: "180°",
          categories: months,
          values: [-0.183, -0.362, -0.404, -0.243, -0.103, 0.028, 0.139, 0.226, 0.161, 0.067, 0.020],
          line: { style: "solid", width: 3, fill: INK },
          marker: { symbol: "circle", size: 5 },
        },
        {
          name: "140°W",
          categories: months,
          values: [-0.076, -0.155, -0.151, -0.085, -0.006, 0.085, 0.146, 0.226, 0.233, 0.230, 0.205],
          line: { style: "solid", width: 4, fill: BLUE },
          marker: { symbol: "circle", size: 5 },
        },
      ],
    );
    const phaseFill = { type: "solid", color: { type: "rgb", value: "#F5C783", transform: { opacity: 0.18 } } };
    addRect(slide, "ct-jun-nov-band", 352, 272, 244, 286, phaseFill, "none", 0, 0);
    addRect(slide, "cp-jun-nov-band", 964, 272, 244, 286, phaseFill, "none", 0, 0);
    addText(slide, "ct-phase-label", "Jun(0)—Nov(0)", 374, 276, 198, 24, { fontSize: 17, bold: true, color: ORANGE, align: "center", autoFit: "none" });
    addText(slide, "cp-phase-label", "Jun(0)—Nov(0)", 986, 276, 198, 24, { fontSize: 17, bold: true, color: ORANGE, align: "center", autoFit: "none" });
    addText(slide, "unit-label", "异常暖量输送（PW）", 54, 593, 1172, 28, { fontSize: 20, bold: true, color: MUTED, align: "center" });
    addTakeaway(slide, "CT更早、更强；CP在夏秋也转为正。", BLUE);
    addNotes(slide, [
      "Monthly composite values from data/derived/research_2026/soda3_three_box_warm_heat_budget_composites.csv",
      "Generated by scripts/analyze_soda3_three_box_warm_heat_fate.py from SODA3.15.2; three-month-smoothed calendar-month detrended anomalies.",
    ]);
  }

  // 5. CT/CP quantitative arrival — Codex Grid chart-and-callout silhouette.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "CT到达更强，但CP也不是“没有暖量东传”");
    addText(slide, "arrival-phase", "累计窗口：Jun(0)—Nov(0)　·　CT/CP各4个事件", 54, 150, 760, 28, {
      fontSize: 20, bold: true, color: MUTED, align: "center", autoFit: "none",
    });
    addGroupedBar(
      slide,
      { left: 54, top: 178, width: 760, height: 426 },
      ["140°W输入", "东部H₂₀增长"],
      [
        { name: "CT", categories: ["140°W输入", "东部H₂₀增长"], values: [6.25, 7.81], fill: ORANGE },
        { name: "CP", categories: ["140°W输入", "东部H₂₀增长"], values: [2.97, 3.71], fill: BLUE },
      ],
      10,
      2,
    );
    addRect(slide, "ct-stat", 850, 184, 346, 126, ORANGE_LIGHT, ORANGE, 1.5, 8);
    addText(slide, "ct-stat-number", "≈ 2.1倍", 880, 202, 286, 50, { fontSize: 38, bold: true, color: ORANGE, align: "center", valign: "middle", autoFit: "none" });
    addText(slide, "ct-stat-label", "CT / CP 的140°W输入比", 878, 258, 290, 34, { fontSize: 22, bold: true, color: INK, align: "center", valign: "middle" });
    addRect(slide, "ci-stat", 850, 336, 346, 236, BLUE_LIGHT, BLUE, 1.5, 8);
    addText(slide, "ci-title", "整事件bootstrap 95%区间", 872, 354, 302, 34, { fontSize: 23, bold: true, color: BLUE, align: "center" });
    addText(slide, "ci-body", "140°W输入\nCT：2.91—9.60\nCP：1.91—4.03\n\n东部H₂₀增长\nCT：5.16—10.46\nCP：2.63—4.80", 872, 392, 302, 166, {
      fontSize: 19, bold: true, color: INK, align: "center", valign: "middle", autoFit: "none", lineSpacing: 1.06,
    });
    addTakeaway(slide, "输入与储量不必相等；东部箱体还受南北边界、海表通量和残差影响。", MUTED);
    addNotes(slide, [
      "CT/CP values from outputs/research_2026/soda3_three_box_warm_heat_fate/SODA3_THREE_BOX_WARM_HEAT_FATE_CN.md",
      "Underlying event data: data/derived/research_2026/soda3_three_box_warm_heat_fate_cumulative_summary.csv",
    ]);
  }

  // 6. Three-event H20 evolution — full scientific visual.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "三次事件都在140°W以东形成正H₂₀异常");
    addText(slide, "event-1997", "1997/98", 132, 156, 338, 30, { fontSize: 23, bold: true, color: INK, align: "center" });
    addText(slide, "event-2015", "2015/16", 500, 156, 338, 30, { fontSize: 23, bold: true, color: INK, align: "center" });
    addText(slide, "event-2023", "2023/24", 868, 156, 338, 30, { fontSize: 23, bold: true, color: INK, align: "center" });
    addImage(
      slide,
      h20,
      "Longitude-time evolution of 0-300 m H20 anomalies for 1997/98, 2015/16 and 2023/24",
      54,
      188,
      1172,
      426,
      { left: 0.0, top: 0.13, right: 0.0, bottom: 0.10 },
      "cover",
    );
    addTakeaway(slide, "1997最强；2015和2023在东部的建立幅度接近。", BLUE);
    addNotes(slide, [
      FIG_H20,
      "Generated from SODA3.15.2 by scripts/plot_soda3_h20_hovmoller.py",
    ]);
  }

  // 7. Three-event quantitative comparison + fixed-depth sensitivity.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "按暖中心位置三次事件均偏CT，但动力性质并不相同", "事件定性");

    const axisLeft = 250;
    const axisRight = 1170;
    const axisMin = -1.0;
    const axisMax = 2.5;
    const xMap = (v) => axisLeft + ((v - axisMin) / (axisMax - axisMin)) * (axisRight - axisLeft);
    const zeroX = xMap(0);

    addRect(slide, "cp-zone", axisLeft, 166, zeroX - axisLeft, 44, BLUE_LIGHT, BLUE_LIGHT, 0, 5);
    addRect(slide, "ct-zone", zeroX, 166, axisRight - zeroX, 44, ORANGE_LIGHT, ORANGE_LIGHT, 0, 5);
    addText(slide, "cp-zone-label", "CP-like：中太平洋暖中心", axisLeft + 12, 174, zeroX - axisLeft - 24, 28, { fontSize: 20, bold: true, color: BLUE, align: "center" });
    addText(slide, "ct-zone-label", "CT-like：东部冷舌区暖中心", zeroX + 12, 174, axisRight - zeroX - 24, 28, { fontSize: 20, bold: true, color: ORANGE, align: "center" });

    for (let tick = -1.0; tick <= 2.5 + 1e-9; tick += 0.5) {
      const x = xMap(tick);
      slide.shapes.add({
        geometry: "line",
        name: `type-grid-${tick}`,
        position: { left: x, top: 220, width: 0, height: 352 },
        fill: "none",
        line: { style: "solid", fill: Math.abs(tick) < 1e-9 ? INK : "#E1E8EC", width: Math.abs(tick) < 1e-9 ? 2 : 1 },
      });
      addText(slide, `type-tick-${tick}`, tick.toFixed(1), x - 26, 580, 52, 25, { fontSize: 17, bold: Math.abs(tick) < 1e-9, color: Math.abs(tick) < 1e-9 ? INK : MUTED, align: "center", autoFit: "none" });
    }

    const eventRows = [
      { event: "1997/98", value: 2.18, y: 275, color: ORANGE, tag: "典型CT", note: "原文CT事件；E指数占绝对优势" },
      { event: "2015/16", value: 1.07, y: 395, color: RED, tag: "CT-like / E–C混合", note: "东部更暖，但中太平洋共同增暖" },
      { event: "2023/24", value: 0.59, y: 515, color: TEAL, tag: "CT-like / FEP主导", note: "东部先暖，但发展期海气耦合偏弱" },
    ];
    eventRows.forEach((row, i) => {
      const x = xMap(row.value);
      addText(slide, `type-event-${i}`, row.event, 54, row.y - 24, 164, 40, { fontSize: 28, bold: true, color: INK, valign: "middle", autoFit: "none" });
      slide.shapes.add({
        geometry: "line",
        name: `type-bar-${i}`,
        position: { left: zeroX, top: row.y, width: x - zeroX, height: 0 },
        fill: "none",
        line: { style: "solid", fill: row.color, width: 12 },
      });
      addCircle(slide, `type-marker-${i}`, x, row.y, 24, row.color);
      addText(slide, `type-value-${i}`, `+${row.value.toFixed(2)}°C`, x - 54, row.y - 48, 108, 28, { fontSize: 20, bold: true, color: row.color, align: "center", autoFit: "none" });
      addText(slide, `type-tag-${i}`, row.tag, 760, row.y - 34, 380, 34, { fontSize: 24, bold: true, color: row.color, autoFit: "none" });
      addText(slide, `type-note-${i}`, row.note, 760, row.y + 4, 420, 30, { fontSize: 20, bold: true, color: MUTED, autoFit: "none" });
    });
    addText(slide, "type-axis-label", "成熟期DJF Niño3 − Niño4（°C）", axisLeft, 606, axisRight - axisLeft, 26, { fontSize: 20, bold: true, color: MUTED, align: "center" });
    addTakeaway(slide, "三者都不是CP对照；关键是同为CT-like，2015与2023却出现不同耦合和暖量命运。", BLUE);
    addNotes(slide, [
      "CT/CP conceptual and event-selection framework: Chakravorty et al. (2021), https://doi.org/10.1029/2020JC017075",
      "Mature DJF OISST Niño3−Niño4 values and EP-like labels: data/derived/research_2026/ep_cp_two_gate_event_summary_1982_2023.csv",
      "Orthogonal E/C sensitivity: data/derived/research_2026/enso_perturbation_event_indices_1982_2023.csv. 2015 and 2023 are mixed under E/C even though Niño3−Niño4 is positive.",
      "2015 and 2023 are extensions of the CT/CP spatial logic; they are outside the original Chakravorty et al. SODA2 event list ending in 2008.",
    ]);
  }

  // 8. Three-event quantitative comparison + fixed-depth sensitivity.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "2015与2023的输入和储量同量级且接近");
    addText(slide, "event-arrival-window", "1997 / 2015 / 2023累计窗口：Jan(0)—Jun(0)", 54, 150, 820, 28, {
      fontSize: 20, bold: true, color: MUTED, align: "center", autoFit: "none",
    });
    addGroupedBar(
      slide,
      { left: 54, top: 178, width: 820, height: 426 },
      ["1997", "2015", "2023"],
      [
        { name: "140°W输入", categories: ["1997", "2015", "2023"], values: [12.13, 3.30, 3.91], fill: ORANGE },
        { name: "东部H₂₀增长", categories: ["1997", "2015", "2023"], values: [9.29, 3.53, 3.88], fill: BLUE },
      ],
      14,
      2,
    );
    addRect(slide, "pair-stat", 918, 186, 268, 166, ORANGE_LIGHT, ORANGE, 1.5, 8);
    addText(slide, "pair-title", "2015 vs 2023", 942, 208, 220, 34, { fontSize: 25, bold: true, color: ORANGE, align: "center" });
    addText(slide, "pair-body", "输入  3.30 / 3.91 ZJ\n储量  3.53 / 3.88 ZJ", 930, 260, 244, 72, { fontSize: 22, bold: true, color: INK, align: "center", valign: "middle", autoFit: "none" });
    addRect(slide, "q500-stat", 918, 390, 268, 156, BLUE_LIGHT, BLUE, 1.5, 8);
    addText(slide, "q500-title", "0—500 m OHC敏感性", 936, 412, 232, 34, { fontSize: 24, bold: true, color: BLUE, align: "center" });
    addText(slide, "q500-body", "2015：6.43 ZJ\n2023：6.46 ZJ", 938, 466, 228, 60, { fontSize: 26, bold: true, color: INK, align: "center", valign: "middle" });
    addTakeaway(slide, "H₂₀与0—500 m OHC均显示2015和2023接近；2023较弱不能归因于“暖量未到”。", RED);
    addNotes(slide, [
      "Event arrival values: outputs/research_2026/enso_1997_2015_2023_warm_heat_fate_bridge/ENSO_1997_2015_2023_WARM_HEAT_FATE_BRIDGE_CN.md",
      "Q500 sensitivity: data/derived/research_2026/soda3_h20_q500_sensitivity_summary.json and soda3_h20_q500_three_event_phase_sensitivity.csv",
    ]);
  }

  // 9. Conservation and source-closure guardrail.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "预算代数闭合，但热量来源尚未完全物理闭合", "守恒检查");

    addText(slide, "closure-equation", "R₂₀ = dH₂₀/dt − (Cₓ + F₁₀S + F₅N + Qsurface,warm)", 54, 166, 1172, 52, {
      fontSize: 29,
      bold: true,
      color: INK,
      typeface: MATH,
      align: "center",
      valign: "middle",
      autoFit: "none",
    });

    addText(slide, "ct-close-title", "CT东箱发展期：ΔH₂₀ = +7.81 ZJ", 54, 248, 548, 36, { fontSize: 26, bold: true, color: ORANGE, align: "center" });
    addText(slide, "cp-close-title", "CP东箱发展期：ΔH₂₀ = +3.71 ZJ", 678, 248, 548, 36, { fontSize: 26, bold: true, color: BLUE, align: "center" });

    const barX1 = 96;
    const barX2 = 720;
    const barY = 312;
    const barW = 464;
    const barH = 78;
    const ctExplicit = 3.4339379;
    const ctResidual = 4.37520117;
    const cpExplicit = 3.0716406;
    const cpResidual = 0.64199709;
    const ctExplicitW = barW * ctExplicit / (ctExplicit + ctResidual);
    const cpExplicitW = barW * cpExplicit / (cpExplicit + cpResidual);

    addRect(slide, "ct-explicit", barX1, barY, ctExplicitW, barH, ORANGE, ORANGE, 0, 5);
    addRect(slide, "ct-residual", barX1 + ctExplicitW, barY, barW - ctExplicitW, barH, PURPLE, PURPLE, 0, 5);
    addText(slide, "ct-explicit-text", "显式净来源\n+3.43 ZJ（44%）", barX1 + 6, barY + 12, ctExplicitW - 12, 56, { fontSize: 21, bold: true, color: WHITE, align: "center", valign: "middle" });
    addText(slide, "ct-residual-text", "残差\n+4.38 ZJ（56%）", barX1 + ctExplicitW + 6, barY + 12, barW - ctExplicitW - 12, 56, { fontSize: 21, bold: true, color: WHITE, align: "center", valign: "middle" });

    addRect(slide, "cp-explicit", barX2, barY, cpExplicitW, barH, BLUE, BLUE, 0, 5);
    addRect(slide, "cp-residual", barX2 + cpExplicitW, barY, barW - cpExplicitW, barH, PURPLE, PURPLE, 0, 5);
    addText(slide, "cp-explicit-text", "显式净来源\n+3.07 ZJ（83%）", barX2 + 6, barY + 12, cpExplicitW - 12, 56, { fontSize: 21, bold: true, color: WHITE, align: "center", valign: "middle" });
    addText(slide, "cp-residual-text", "残差\n+0.64 ZJ", barX2 + cpExplicitW + 4, barY + 12, barW - cpExplicitW - 8, 56, { fontSize: 18, bold: true, color: WHITE, align: "center", valign: "middle" });

    addRect(slide, "algebra-box", 54, 434, 548, 154, BLUE_LIGHT, BLUE, 1.5, 8);
    addText(slide, "algebra-title", "代数守恒：是", 82, 454, 492, 38, { fontSize: 28, bold: true, color: BLUE, align: "center" });
    addText(slide, "algebra-body", "加入R₂₀后，最大闭合误差\n< 1.1 × 10⁻¹⁶ PW", 82, 504, 492, 62, { fontSize: 24, bold: true, color: INK, align: "center", valign: "middle" });

    addRect(slide, "physical-box", 678, 434, 548, 154, PURPLE_LIGHT, PURPLE, 1.5, 8);
    addText(slide, "physical-title", "物理来源闭合：尚未", 706, 454, 492, 38, { fontSize: 28, bold: true, color: PURPLE, align: "center" });
    addText(slide, "physical-body", "R₂₀仍混合垂向交换、混合、阈值转换、\n同化增量和月平均离散", 706, 504, 492, 62, { fontSize: 22, bold: true, color: INK, align: "center", valign: "middle" });

    addTakeaway(slide, "可以证明异常暖量“越界与储存”；不能声称东部全部增热都来自140°W水平输入。", RED);
    addNotes(slide, [
      "East-box development budget values: data/derived/research_2026/soda3_three_box_warm_heat_fate_cumulative_summary.csv",
      "Algebraic closure QA: data/derived/research_2026/soda3_three_box_warm_heat_fate_diagnostics.json",
      "The residual is defined diagnostically; algebraic closure is not an independent physical validation.",
    ]);
  }

  // 10. Direct answer — Codex Grid slide-26 large-message hierarchy.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addText(slide, "answer-kicker", "问题一的回答", 54, 42, 300, 36, { fontSize: 24, bold: true, color: BLUE });
    addText(slide, "answer-title", "异常暖量越过140°W，\n并在东太平洋建立暖量库", 54, 142, 1120, 230, {
      fontSize: 62,
      bold: true,
      color: INK,
      valign: "bottom",
      autoFit: "none",
      lineSpacing: 0.92,
    });
    addRule(slide, 54, 410, 1172, RULE, 1.6);
    addText(slide, "answer-1", "越界证据：140°W东向异常输入为正", 54, 452, 1172, 44, { fontSize: 28, bold: true, color: BLUE, autoFit: "none" });
    addText(slide, "answer-2", "储存证据：东部H₂₀增加；强度为CT > CP，1997 ≫ 2015 ≈ 2023", 54, 516, 1172, 44, { fontSize: 28, bold: true, color: ORANGE, autoFit: "none" });
    addText(slide, "answer-3", "边界：这是欧拉控制体意义上的到达，不是同一水团的拉格朗日追踪。", 54, 580, 1172, 44, { fontSize: 25, bold: true, color: MUTED, autoFit: "none" });
    addNotes(slide, [
      "Synthesis of the SODA3.15.2 fixed-gate transport, fixed-box H20 storage, event H20 Hovmoller, and Q500 sensitivity results used on slides 3–7.",
    ]);
  }

  // 9. Question 2 setup — close the fate after the 5°N transfer gate.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "用北侧接收箱补上5°N之后的暖量去向", "问题二");
    addText(slide, "receiver-formula", "dH₂₀,N/dt = Cₓ,N + F₅N + F₁₂N + Qsurface,N + Rₙ", 54, 168, 1172, 54, {
      fontSize: 31,
      bold: true,
      color: INK,
      typeface: MATH,
      align: "center",
      valign: "middle",
      autoFit: "none",
    });
    addText(slide, "cx-definition", "Cₓ,N = Q₁₄₀W,east − Q₈₀W,east", 54, 220, 1172, 34, {
      fontSize: 24, bold: true, color: BLUE, typeface: MATH, align: "center", autoFit: "none",
    });
    addText(slide, "sign-rule", "所有项以进入北侧箱体为正　·　累计窗口：Dec(0)—May(+1)", 54, 248, 1172, 30, {
      fontSize: 21, bold: true, color: MUTED, align: "center",
    });

    // Draw arrows before boxes so the boxes stay on top.
    addArrow(slide, "q5n-arrow", "upArrow", 592, 500, 96, 74, ORANGE);
    addArrow(slide, "surface-arrow", "upArrow", 594, 292, 92, 62, RED);
    addArrow(slide, "west-arrow", "leftArrow", 274, 380, 178, 72, BLUE);
    addArrow(slide, "east-arrow", "rightArrow", 828, 380, 178, 72, MUTED);
    addArrow(slide, "north-arrow", "upArrow", 744, 300, 66, 82, PURPLE);
    addArrow(slide, "residual-arrow", "leftArrow", 896, 472, 116, 48, TEAL);

    addRect(slide, "atmosphere-box", 515, 268, 250, 56, RED_LIGHT, RED, 1.5, 8);
    addText(slide, "atmosphere-text", "海表热交换", 535, 281, 210, 30, { fontSize: 24, bold: true, color: RED, align: "center", valign: "middle" });
    addRect(slide, "receiver-box", 430, 352, 420, 150, ORANGE_LIGHT, ORANGE, 2, 8);
    addText(slide, "receiver-box-text", "北侧接收箱\n5°N—12°N · 140°W—80°W · 0—300 m", 452, 385, 376, 84, {
      fontSize: 26,
      bold: true,
      color: INK,
      align: "center",
      valign: "middle",
    });
    addRect(slide, "equatorial-box", 480, 552, 320, 58, BLUE_LIGHT, BLUE, 1.5, 8);
    addText(slide, "equatorial-box-text", "赤道东箱（10°S—5°N）", 500, 566, 280, 30, { fontSize: 23, bold: true, color: BLUE, align: "center", valign: "middle" });
    addText(slide, "q5n-label", "F₅N", 694, 514, 90, 28, { fontSize: 23, bold: true, color: ORANGE });
    addText(slide, "west-label", "140°W边界", 96, 396, 170, 32, { fontSize: 22, bold: true, color: BLUE, align: "right" });
    addText(slide, "east-label", "80°W边界", 1018, 398, 150, 32, { fontSize: 22, bold: true, color: MUTED, align: "left" });
    addText(slide, "north-label", "F₁₂N", 800, 296, 110, 30, { fontSize: 22, bold: true, color: PURPLE });
    addText(slide, "residual-label", "Rₙ", 1018, 480, 80, 28, { fontSize: 22, bold: true, color: TEAL });
    addTakeaway(slide, "5°N只是转移门；Cₓ,N同时包含140°W与80°W，残差不是已识别的物理去向。", MUTED);
    addNotes(slide, [
      "Northern receiver-box diagnostic: outputs/research_2026/soda3_north_receiver_budget/SODA3_NORTH_RECEIVER_WARM_HEAT_BUDGET_CN.md",
      "Control volume: 5°N–12°N, 140°W–80°W, 0–300 m; all terms use the into-box-positive convention.",
    ]);
  }

  // 10. CT/CP composite dot-whisker chart with event-bootstrap intervals.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "成熟—衰减期，CT在5°N获得暖量，CP却向南返回", "问题二");
    addText(slide, "receiver-phase", "累计窗口：Dec(0)—May(+1)", 54, 151, 300, 28, {
      fontSize: 20, bold: true, color: MUTED, autoFit: "none",
    });

    const chartLeft = 350;
    const chartRight = 1160;
    const min = -3;
    const max = 5;
    const xMap = (v) => chartLeft + ((v - min) / (max - min)) * (chartRight - chartLeft);
    const rows = [
      { label: "5°N输入", ct: [2.74244682, 0.923864347, 4.56102929], cp: [-0.959627273, -1.50874583, -0.245312805] },
      { label: "纬向汇聚 Cₓ,N", ct: [-1.65382859, -2.50346712, -0.17602483], cp: [0.73878810, 0.14717723, 1.61234288] },
      { label: "12°N输入项", ct: [-0.0636903747, -0.483725183, 0.364526967], cp: [-0.174510768, -0.968643602, 0.296185695] },
      { label: "海表暖层项", ct: [-1.70222542, -2.42973366, -0.974717177], cp: [-0.676838919, -0.996856201, -0.230157979] },
      { label: "剩余项", ct: [1.27294475, 0.933680771, 1.61220874], cp: [0.811696631, 0.566869993, 1.05478738] },
      { label: "储量倾向", ct: [0.595646407, 0.184841595, 0.885662888], cp: [-0.260491867, -0.887588819, 0.716135612] },
    ];
    const y0 = 220;
    const dy = 64;
    for (let tick = min; tick <= max; tick += 1) {
      const x = xMap(tick);
      slide.shapes.add({
        geometry: "line",
        name: `grid-${tick}`,
        position: { left: x, top: 190, width: 0, height: 380 },
        fill: "none",
        line: { style: "solid", fill: tick === 0 ? INK : "#DDE5E9", width: tick === 0 ? 2 : 1 },
      });
      addText(slide, `tick-${tick}`, `${tick}`, x - 22, 578, 44, 26, { fontSize: 18, bold: tick === 0, color: tick === 0 ? INK : MUTED, align: "center", autoFit: "none" });
    }
    rows.forEach((row, i) => {
      const y = y0 + i * dy;
      addText(slide, `row-label-${i}`, row.label, 54, y - 18, 260, 36, { fontSize: 23, bold: true, color: INK, valign: "middle", autoFit: "none" });
      if (i < rows.length - 1) addRule(slide, 54, y + 31, 1106, "#E7ECEF", 1);
      addDotWhisker(slide, `ct-${i}`, y - 9, row.ct[0], row.ct[1], row.ct[2], ORANGE, xMap, -26);
      addDotWhisker(slide, `cp-${i}`, y + 11, row.cp[0], row.cp[1], row.cp[2], BLUE, xMap, 6);
    });
    addCircle(slide, "legend-ct", 936, 164, 14, ORANGE);
    addText(slide, "legend-ct-text", "CT（均值与95%区间）", 950, 151, 210, 28, { fontSize: 19, bold: true, color: ORANGE, valign: "middle" });
    addCircle(slide, "legend-cp", 1138, 164, 14, BLUE);
    addText(slide, "legend-cp-text", "CP", 1152, 151, 70, 28, { fontSize: 19, bold: true, color: BLUE, valign: "middle" });
    addText(slide, "axis-label", "累计异常暖量（ZJ）", 350, 604, 810, 26, { fontSize: 20, bold: true, color: MUTED, align: "center" });
    addTakeaway(slide, "CT与CP在5°N和Cₓ,N上方向相反；Rₙ与显式项同量级，不能解释为已识别去向。", BLUE);
    addNotes(slide, [
      "CT/CP Dec(0)–May(+1) mean and 95% event-bootstrap intervals: data/derived/research_2026/soda3_north_receiver_budget_summary.csv",
      "SODA3.15.2, 1980–2022 calendar-month detrended anomalies, three-month smoothing; CT and CP each n=4.",
    ]);
  }

  // 13. Northern-boundary sensitivity: 12N zero is not the core claim.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "改变北边界后，持续北向仍不是CT的主要去向", "边界敏感性");
    addText(slide, "sensitivity-phase", "Dec(0)—May(+1)　·　正值表示向北异常输出　·　CT/CP各4个事件", 54, 150, 1172, 28, {
      fontSize: 20, bold: true, color: MUTED, align: "center", autoFit: "none",
    });

    const chartLeft = 320;
    const chartRight = 1160;
    const min = -1.2;
    const max = 1.4;
    const xMap = (v) => chartLeft + ((v - min) / (max - min)) * (chartRight - chartLeft);
    for (let tick = -1.0; tick <= 1.25 + 1e-9; tick += 0.25) {
      const x = xMap(tick);
      slide.shapes.add({
        geometry: "line",
        name: `sens-grid-${tick}`,
        position: { left: x, top: 210, width: 0, height: 300 },
        fill: "none",
        line: { style: "solid", fill: Math.abs(tick) < 1e-9 ? INK : "#DDE5E9", width: Math.abs(tick) < 1e-9 ? 2 : 1 },
      });
      if (Math.abs(tick * 4 - Math.round(tick * 4)) < 1e-9) {
        addText(slide, `sens-tick-${tick}`, tick.toFixed(2).replace(/0$/, ""), x - 28, 522, 56, 26, {
          fontSize: 17, bold: Math.abs(tick) < 1e-9, color: Math.abs(tick) < 1e-9 ? INK : MUTED, align: "center", autoFit: "none",
        });
      }
    }
    const rows = [
      { label: "10°N", y: 270, ct: [0.427444, 0.067612, 0.881054], cp: [0.545887, 0.108235, 0.983539] },
      { label: "12°N", y: 360, ct: [0.063690, -0.364527, 0.483725], cp: [0.174511, -0.296186, 0.968644] },
      { label: "15°N", y: 450, ct: [0.449439, 0.051109, 0.847769], cp: [-0.077869, -0.413120, 0.202323] },
    ];
    rows.forEach((row, i) => {
      addText(slide, `sens-row-${i}`, row.label, 88, row.y - 22, 170, 44, { fontSize: 29, bold: true, color: INK, align: "center", valign: "middle", autoFit: "none" });
      addDotWhisker(slide, `sens-ct-${i}`, row.y - 12, row.ct[0], row.ct[1], row.ct[2], ORANGE, xMap, -26);
      addDotWhisker(slide, `sens-cp-${i}`, row.y + 14, row.cp[0], row.cp[1], row.cp[2], BLUE, xMap, 6);
    });
    addCircle(slide, "sens-legend-ct", 898, 190, 14, ORANGE);
    addText(slide, "sens-legend-ct-text", "CT（均值与95%区间）", 912, 177, 210, 28, { fontSize: 19, bold: true, color: ORANGE, valign: "middle" });
    addCircle(slide, "sens-legend-cp", 1100, 190, 14, BLUE);
    addText(slide, "sens-legend-cp-text", "CP", 1114, 177, 70, 28, { fontSize: 19, bold: true, color: BLUE, valign: "middle" });
    addText(slide, "sens-axis", "向北累计异常暖量输送（ZJ）", chartLeft, 552, chartRight - chartLeft, 28, { fontSize: 20, bold: true, color: MUTED, align: "center" });
    addText(slide, "sens-ratio", "CT：10°N / 12°N / 15°N北向输出 = 0.43 / 0.06 / 0.45 ZJ；仅为5°N输入2.74 ZJ的16% / 2% / 16%", 54, 590, 1172, 30, {
      fontSize: 20, bold: true, color: INK, align: "center", autoFit: "none",
    });
    addTakeaway(slide, "“12°N≈0”不具边界稳健性；“持续北向不是CT的主要去向”在10°N—15°N范围内稳健。", BLUE);
    addNotes(slide, [
      "SODA3.15.2 north-boundary sensitivity: data/derived/research_2026/soda3_north_boundary_q20_10_12_15_summary.csv",
      "Generated by scripts/analyze_soda3_north_boundary_sensitivity.py; 1980–2022 calendar-month detrending, centered three-month smoothing, actual calendar-month seconds, whole-event bootstrap.",
    ]);
  }

  // 14. Side-by-side fate pathways for CT and CP.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "暖量命运发生方向重组，而不只是强弱变化", "问题二");
    addText(slide, "flow-phase", "累计窗口：Dec(0)—May(+1)　·　异常暖量的欧拉控制体收支", 54, 148, 1172, 26, {
      fontSize: 19, bold: true, color: MUTED, align: "center", autoFit: "none",
    });
    addRule(slide, 640, 170, 0, RULE, 1.3);
    addText(slide, "ct-flow-title", "CT：西向再分配与海表失热", 54, 178, 560, 40, { fontSize: 28, bold: true, color: ORANGE, align: "center" });
    addText(slide, "cp-flow-title", "CP：5°N净输送方向反转", 666, 178, 560, 40, { fontSize: 28, bold: true, color: BLUE, align: "center" });

    // CT arrows first.
    addArrow(slide, "ct-surface", "upArrow", 288, 222, 72, 92, RED);
    addArrow(slide, "ct-west", "leftArrow", 52, 354, 172, 66, BLUE);
    addArrow(slide, "ct-north", "upArrow", 500, 278, 56, 86, PURPLE);
    addArrow(slide, "ct-south", "upArrow", 292, 470, 74, 92, ORANGE);
    addArrow(slide, "ct-residual", "leftArrow", 498, 448, 112, 50, TEAL);
    addRect(slide, "ct-receiver", 216, 318, 292, 150, ORANGE_LIGHT, ORANGE, 2, 8);
    addText(slide, "ct-receiver-text", "北侧接收箱\n储量 +0.60 ZJ\n80°W东向 +0.01 ≈ 0", 238, 336, 248, 112, { fontSize: 24, bold: true, color: INK, align: "center", valign: "middle" });
    addRect(slide, "ct-equatorial", 244, 560, 236, 48, BLUE_LIGHT, BLUE, 1.4, 8);
    addText(slide, "ct-equatorial-text", "赤道东箱", 266, 571, 192, 26, { fontSize: 22, bold: true, color: BLUE, align: "center" });
    addText(slide, "ct-surface-label", "海表失热 1.70", 208, 216, 230, 30, { fontSize: 21, bold: true, color: RED, align: "center" });
    addText(slide, "ct-west-label", "向西越140°W\n1.64", 54, 424, 155, 58, { fontSize: 21, bold: true, color: BLUE, align: "center" });
    addText(slide, "ct-north-label", "跨12°N\n0.06 ≈ 0", 494, 215, 120, 58, { fontSize: 20, bold: true, color: PURPLE, align: "center" });
    addText(slide, "ct-f5n-label", "跨5°N +2.74", 372, 514, 168, 30, { fontSize: 22, bold: true, color: ORANGE, align: "left" });
    addText(slide, "ct-res-label", "残差 +1.27", 440, 498, 160, 28, { fontSize: 20, bold: true, color: TEAL, align: "center" });

    // CP arrows first.
    addArrow(slide, "cp-surface", "upArrow", 926, 222, 72, 92, RED);
    addArrow(slide, "cp-west", "rightArrow", 674, 354, 172, 66, BLUE);
    addArrow(slide, "cp-north", "upArrow", 1138, 278, 56, 86, PURPLE);
    addArrow(slide, "cp-south", "downArrow", 930, 452, 74, 106, BLUE);
    addArrow(slide, "cp-residual", "leftArrow", 1136, 448, 90, 50, TEAL);
    addRect(slide, "cp-receiver", 854, 318, 292, 150, BLUE_LIGHT, BLUE, 2, 8);
    addText(slide, "cp-receiver-text", "北侧接收箱\n储量 −0.26 ZJ\n80°W东向 +0.02 ≈ 0", 876, 336, 248, 112, { fontSize: 24, bold: true, color: INK, align: "center", valign: "middle" });
    addRect(slide, "cp-equatorial", 882, 560, 236, 48, ORANGE_LIGHT, ORANGE, 1.4, 8);
    addText(slide, "cp-equatorial-text", "赤道东箱", 904, 571, 192, 26, { fontSize: 22, bold: true, color: ORANGE, align: "center" });
    addText(slide, "cp-surface-label", "海表失热 0.68", 846, 216, 230, 30, { fontSize: 21, bold: true, color: RED, align: "center" });
    addText(slide, "cp-west-label", "140°W东向输入\n+0.76", 674, 424, 164, 58, { fontSize: 21, bold: true, color: BLUE, align: "center" });
    addText(slide, "cp-north-label", "跨12°N\n0.17 ≈ 0", 1128, 215, 120, 58, { fontSize: 20, bold: true, color: PURPLE, align: "center" });
    addText(slide, "cp-f5n-label", "经5°N向南 0.96", 698, 514, 220, 30, { fontSize: 22, bold: true, color: BLUE, align: "right" });
    addText(slide, "cp-res-label", "残差 +0.81", 1070, 498, 150, 28, { fontSize: 20, bold: true, color: TEAL, align: "center" });

    addTakeaway(slide, "在已解析显式项中，CT以西向输出和海表失热为主；CP的5°N净输送方向反转。", MUTED);
    addNotes(slide, [
      "Pathway values from data/derived/research_2026/soda3_north_receiver_budget_summary.csv, Dec(0)–May(+1).",
      "The residual is a closure term and is not interpreted as an identified physical destination.",
    ]);
  }

  // 12. Three-event small multiples with a shared zero line.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addTitle(slide, "三个事件的北侧预算：1997最强，2023整体最弱", "问题二");
    addText(slide, "north-near-zero", "Dec(0)—May(+1)　·　12°N输入项：1997 −0.15　│　2015 +0.01　│　2023 +0.09 ZJ", 54, 148, 1172, 34, {
      fontSize: 21,
      bold: true,
      color: PURPLE,
      align: "center",
      autoFit: "none",
    });
    addMiniBudgetPanel(slide, 54, "1997/98", [4.98305081, -2.55113636, -2.85350535, 1.51576448, 0.945917338]);
    addMiniBudgetPanel(slide, 462, "2015/16", [1.49826429, -2.44177214, -1.62054077, 2.12008497, -0.43777631]);
    addMiniBudgetPanel(slide, 870, "2023/24", [0.52152919, -0.27092135, -0.578487114, 0.124440393, -0.108632878]);
    addText(slide, "residual-warning", "2015残差 +2.12 ZJ > 5°N输入 +1.50 ZJ：未解析过程不可忽略", 54, 606, 1172, 26, {
      fontSize: 20, bold: true, color: TEAL, align: "center", autoFit: "none",
    });
    addTakeaway(slide, "5°N输入为1997 ≫ 2015 > 2023；显式通道不能替代对残差的物理拆解。", BLUE);
    addNotes(slide, [
      "Event Dec(0)–May(+1) receiver-box budgets: data/derived/research_2026/soda3_north_receiver_budget_event_cumulative.csv",
      "1997 and 2015 use historical SODA3.15.2; 2023/24 is extended with official University of Maryland annual SODA3 files.",
    ]);
  }

  // 13. Direct answer and bridge to Question 3.
  {
    const slide = deck.slides.add();
    slide.background.fill = WHITE;
    addText(slide, "answer2-kicker", "问题二的回答", 54, 42, 300, 36, { fontSize: 24, bold: true, color: BLUE });
    addText(slide, "answer2-title", "异常暖量没有持续向北输出；\n进入北侧箱体后发生方向重组", 54, 124, 1160, 220, {
      fontSize: 58,
      bold: true,
      color: INK,
      valign: "bottom",
      autoFit: "none",
      lineSpacing: 0.92,
    });
    addRule(slide, 54, 378, 1172, RULE, 1.6);
    addText(slide, "answer2-ct", "CT：在已解析项中，5°N输入对应140°W西向输出与海表失热", 54, 410, 1172, 40, { fontSize: 26, bold: true, color: ORANGE, autoFit: "none" });
    addText(slide, "answer2-cp", "CP：5°N净输送方向反转，北侧箱体向赤道东箱异常输出", 54, 466, 1172, 40, { fontSize: 26, bold: true, color: BLUE, autoFit: "none" });
    addText(slide, "answer2-common", "共同点：10°N—15°N范围内持续北向不是CT的主要去向；80°W项也接近0", 54, 522, 1172, 40, { fontSize: 25, bold: true, color: PURPLE, autoFit: "none" });
    addText(slide, "answer2-residual", "边界：Rₙ仍包含阈值转换、垂向交换、混合、同化增量与月平均离散。", 54, 570, 1172, 30, { fontSize: 20, bold: true, color: TEAL, align: "center", autoFit: "none" });
    addRect(slide, "q3-bridge", 54, 618, 1172, 62, ORANGE_LIGHT, ORANGE, 1.5, 8);
    addText(slide, "q3-bridge-text", "进入问题三：什么海气耦合过程选择了不同的风场与暖量去向？", 78, 630, 1124, 36, {
      fontSize: 26,
      bold: true,
      color: INK,
      align: "center",
      valign: "middle",
      autoFit: "none",
    });
    addNotes(slide, [
      "Synthesis of the northern receiver-box composite and event budgets shown on slides 9–12.",
    ]);
  }

  for (const [index, slide] of deck.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(BUILD, `${stem}.png`), await deck.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(BUILD, `${stem}.layout.json`), await layout.text());
  }

  await writeBlob(path.join(BUILD, "montage.webp"), await deck.export({ format: "webp", montage: true, scale: 1 }));
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(FINAL);
  console.log(FINAL);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
