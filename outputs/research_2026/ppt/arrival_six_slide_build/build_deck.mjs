import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const W = 1280;
const H = 720;
const ROOT = "/Users/daiyue/Documents/Maryland";
const BUILD = path.join(ROOT, "outputs/research_2026/ppt/arrival_six_slide_build");
const FINAL = path.join(ROOT, "outputs/research_2026/ppt/ENSO暖量到达东太平洋_加入OHC演变图_七页汇报_20260808.pptx");
const FIG8 = path.join(ROOT, "outputs/research_2026/three_questions_full_report_assets_20260805/chakravorty2021_figure8_excerpt.png");
const OHC_HOV = path.join(ROOT, "outputs/research_2026/soda3_ohc300_hovmoller_1997_2015_2023.png");

const NAVY = "#0B1F33";
const BLUE = "#087EAD";
const BLUE_DARK = "#075B82";
const BLUE_LIGHT = "#E7F5FA";
const TEAL = "#008A8A";
const TEAL_LIGHT = "#E6F6F4";
const ORANGE = "#D97706";
const ORANGE_LIGHT = "#FFF2DD";
const RED = "#B63A3A";
const WHITE = "#FFFFFF";
const GRID = "#CFE9F2";
const FONT = "PingFang SC";
const MATH_FONT = "Arial Unicode MS";

function box(slide, name, x, y, w, h, fill = WHITE, lineFill = BLUE, lineWidth = 2, radius = 18) {
  return slide.shapes.add({
    geometry: "roundRect",
    name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: lineFill, width: lineWidth },
    borderRadius: radius,
  });
}

function text(slide, name, value, x, y, w, h, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    fontSize: opts.fontSize ?? 24,
    bold: opts.bold ?? false,
    color: opts.color ?? NAVY,
    alignment: opts.align ?? "left",
    verticalAlignment: opts.valign ?? "top",
    autoFit: opts.autoFit ?? "shrinkText",
    wrap: opts.wrap ?? "square",
    insets: opts.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
    lineSpacing: opts.lineSpacing ?? 1.0,
    typeface: opts.typeface ?? FONT,
  };
  return shape;
}

function title(slide, value) {
  text(slide, "slide-title", value, 68, 42, 1144, 58, {
    fontSize: 38,
    bold: true,
    color: NAVY,
    valign: "middle",
  });
  slide.shapes.add({
    geometry: "line",
    name: "title-rule",
    position: { left: 68, top: 108, width: 1144, height: 0 },
    fill: "none",
    line: { style: "solid", fill: BLUE, width: 3 },
  });
}

function takeaway(slide, value, fill = BLUE, y = 630, h = 58, fontSize = 25) {
  const bar = slide.shapes.add({
    geometry: "roundRect",
    name: "takeaway",
    position: { left: 68, top: y, width: 1144, height: h },
    fill,
    line: { style: "solid", fill, width: 0 },
    borderRadius: 14,
  });
  text(slide, "takeaway-text", value, 88, y + 7, 1104, h - 14, {
    fontSize,
    bold: true,
    color: WHITE,
    align: "center",
    valign: "middle",
  });
  return bar;
}

function addNotes(slide, lines) {
  slide.speakerNotes.textFrame.setText(`[Sources]\n${lines.map((x) => `- ${x}`).join("\n")}\n[/Sources]`);
  slide.speakerNotes.setVisible(false);
}

function addNumberedPoint(slide, n, value, y) {
  const c = slide.shapes.add({
    geometry: "ellipse",
    name: `question-${n}-number`,
    position: { left: 116, top: y, width: 54, height: 54 },
    fill: n === 1 ? BLUE : n === 2 ? TEAL : ORANGE,
    line: { style: "solid", fill: "none", width: 0 },
  });
  text(slide, `question-${n}-number-text`, String(n), 116, y + 3, 54, 46, {
    fontSize: 26,
    bold: true,
    color: WHITE,
    align: "center",
    valign: "middle",
  });
  text(slide, `question-${n}-text`, value, 194, y - 1, 930, 58, {
    fontSize: 27,
    bold: true,
    valign: "middle",
  });
  return c;
}

function addNativeChart(slide, position, categories, series, max, major, axisTitle) {
  return slide.charts.add("bar", {
    position,
    categories,
    series,
    hasLegend: true,
    legend: {
      position: "top",
      overlay: false,
      fill: "none",
      line: { style: "solid", fill: "none", width: 0 },
      textStyle: { fontSize: 19, fill: NAVY, bold: true },
    },
    barOptions: { direction: "column", grouping: "clustered", gapWidth: 70 },
    xAxis: {
      visible: true,
      textStyle: { fontSize: 19, fill: NAVY, bold: true },
      line: { style: "solid", fill: BLUE_DARK, width: 1.5 },
      majorGridlines: null,
    },
    yAxis: {
      visible: true,
      min: 0,
      max,
      majorUnit: major,
      title: { text: axisTitle, textStyle: { fontSize: 18, fill: NAVY, bold: true } },
      textStyle: { fontSize: 17, fill: NAVY },
      line: { style: "solid", fill: BLUE_DARK, width: 1.5 },
      majorGridlines: { style: "solid", fill: GRID, width: 1 },
    },
    dataLabels: {
      showValue: true,
      position: "outEnd",
      textStyle: { fontSize: 18, fill: NAVY, bold: true },
      fill: "none",
      line: { style: "solid", fill: "none", width: 0 },
    },
    chartFill: WHITE,
    chartLine: { style: "solid", fill: "none", width: 0 },
    plotAreaFill: WHITE,
    plotAreaLine: { style: "solid", fill: "none", width: 0 },
  });
}

async function imageBytes(file) {
  const b = await fs.readFile(file);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

async function main() {
  await fs.mkdir(BUILD, { recursive: true });
  await fs.mkdir(path.dirname(FINAL), { recursive: true });

  const p = Presentation.create({ slideSize: { width: W, height: H } });
  p.theme.colorScheme = {
    name: "Ocean Arrival",
    themeColors: {
      accent1: BLUE,
      accent2: ORANGE,
      accent3: TEAL,
      accent4: RED,
      accent5: BLUE_DARK,
      accent6: "#6A4C93",
      bg1: WHITE,
      bg2: BLUE_LIGHT,
      tx1: NAVY,
      tx2: NAVY,
      dk1: NAVY,
      dk2: BLUE_DARK,
      lt1: WHITE,
      lt2: BLUE_LIGHT,
      hlink: BLUE,
      folHlink: TEAL,
    },
  };

  // Slide 1
  {
    const s = p.slides.add();
    s.background.fill = WHITE;
    text(s, "deck-title", "厄尔尼诺暖量是否真正到达东太平洋？", 68, 38, 1144, 62, {
      fontSize: 44,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });
    text(s, "deck-subtitle", "从 Chakravorty et al.（2021）的 CT/CP 充放电差异开始", 68, 105, 1144, 42, {
      fontSize: 25,
      bold: true,
      color: BLUE_DARK,
      align: "center",
      valign: "middle",
    });
    box(s, "paper-summary", 72, 178, 380, 376, BLUE_LIGHT, BLUE, 2, 18);
    text(s, "paper-question", "原文问题", 104, 204, 316, 38, {
      fontSize: 25,
      bold: true,
      color: BLUE_DARK,
      align: "center",
    });
    text(s, "ct-line", "CT：西太平洋蓄热\n→ 赤道东传\n→ 成熟期极向放电", 106, 265, 312, 122, {
      fontSize: 25,
      bold: true,
      lineSpacing: 1.12,
    });
    text(s, "cp-line", "CP：盆地尺度充放电循环弱", 106, 423, 312, 70, {
      fontSize: 23,
      bold: true,
      color: TEAL,
      valign: "middle",
    });
    const fig = await imageBytes(FIG8);
    s.images.add({
      blob: fig,
      contentType: "image/png",
      alt: "Chakravorty et al. (2021) Figure 8 excerpt comparing CT and CP transport and WWV evolution",
      fit: "contain",
      position: { left: 486, top: 172, width: 722, height: 382 },
    });
    text(s, "source", "Source: Chakravorty et al. (2021), their Figure 8.", 488, 566, 718, 30, {
      fontSize: 18,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });
    takeaway(s, "他们回答了“CT/CP充放电是否不同”，但没有直接量化暖量是否越过140°W。", BLUE, 628, 58, 23);
    addNotes(s, [
      "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020JC017075",
      FIG8,
    ]);
  }

  // Slide 2
  {
    const s = p.slides.add();
    s.background.fill = WHITE;
    title(s, "已有研究尚未直接回答：暖量是否进入东部箱体？");
    box(s, "prior-scope", 82, 142, 466, 146, BLUE_LIGHT, BLUE, 2, 18);
    text(s, "prior-label", "已有框架", 108, 160, 130, 34, { fontSize: 23, bold: true, color: BLUE_DARK });
    text(s, "prior-content", "WWV + 170°E暖水输送\n5°N / 10°S经向输送\n以标准化体积异常为主", 108, 202, 402, 78, {
      fontSize: 23,
      bold: true,
      lineSpacing: 1.08,
    });
    s.shapes.add({
      geometry: "rightArrow",
      name: "scope-arrow",
      position: { left: 576, top: 184, width: 112, height: 54 },
      fill: ORANGE,
      line: { style: "solid", fill: ORANGE, width: 0 },
    });
    text(s, "scope-arrow-label", "尺度推进", 562, 242, 140, 30, {
      fontSize: 20,
      bold: true,
      color: ORANGE,
      align: "center",
    });
    box(s, "new-scope", 716, 142, 482, 146, ORANGE_LIGHT, ORANGE, 2, 18);
    text(s, "new-label", "本文推进", 744, 160, 140, 34, { fontSize: 23, bold: true, color: ORANGE });
    text(s, "new-content", "140°W固定断面暖量输入\n东部固定箱体 H₂₀ 储量\n用PW和ZJ保留能量量纲", 744, 202, 418, 78, {
      fontSize: 23,
      bold: true,
      lineSpacing: 1.08,
    });
    addNumberedPoint(s, 1, "暖量是否继续越过140°W进入东太平洋？", 336);
    addNumberedPoint(s, 2, "到达量有多少，能否用ZJ直接比较？", 412);
    addNumberedPoint(s, 3, "跨边界输入与东部箱体储存是否一致？", 488);
    takeaway(s, "不是重新证明暖水会东传，而是把体积输送推进为固定区域的能量到达问题。", BLUE_DARK, 626, 60, 24);
    addNotes(s, [
      "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020JC017075",
      "Local SODA3.15.2 fixed-gate and fixed-box analysis in /Users/daiyue/Documents/Maryland/scripts/",
    ]);
  }

  // Slide 3
  {
    const s = p.slides.add();
    s.background.fill = WHITE;
    title(s, "用固定断面输送与固定箱体储量判断“到达”");
    box(s, "h20-box", 72, 136, 548, 154, BLUE_LIGHT, BLUE, 2, 18);
    text(s, "h20-label", "东部箱体储存", 96, 152, 500, 34, { fontSize: 23, bold: true, color: BLUE_DARK, align: "center" });
    text(s, "h20-formula", "H₂₀ = ρ₀ cₚ ∭ max(T − 20 °C, 0) dV", 92, 198, 508, 48, {
      fontSize: 29,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
      typeface: MATH_FONT,
    });
    text(s, "h20-use", "固定箱体内的20°C阈值相对热含量｜ZJ", 96, 254, 500, 28, {
      fontSize: 20,
      bold: true,
      align: "center",
    });
    box(s, "q20-box", 660, 136, 548, 154, ORANGE_LIGHT, ORANGE, 2, 18);
    text(s, "q20-label", "固定断面输送", 684, 152, 500, 34, { fontSize: 23, bold: true, color: ORANGE, align: "center" });
    text(s, "q20-formula", "Qwarm,20 = ρ₀ cₚ ∬ vₙ max(T − 20 °C, 0) dA", 674, 198, 520, 48, {
      fontSize: 23,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
      typeface: MATH_FONT,
    });
    text(s, "q20-use", "断面瞬时暖量输送为PW｜按每月实际秒数积分为ZJ", 684, 254, 500, 28, {
      fontSize: 20,
      bold: true,
      align: "center",
    });
    text(s, "symbols", "ρ₀：参考海水密度　cₚ：定压比热　T：位温　vₙ：断面法向流速　dV / dA：体积元 / 面积元", 84, 308, 1112, 34, {
      fontSize: 19,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });

    // Arrows are created before nodes so they remain behind the box labels.
    s.shapes.add({ geometry: "rightArrow", name: "arrow-180", position: { left: 360, top: 405, width: 126, height: 50 }, fill: BLUE, line: { style: "solid", fill: BLUE, width: 0 } });
    s.shapes.add({ geometry: "rightArrow", name: "arrow-140", position: { left: 792, top: 405, width: 126, height: 50 }, fill: ORANGE, line: { style: "solid", fill: ORANGE, width: 0 } });
    const west = box(s, "west-box", 110, 378, 250, 104, BLUE_LIGHT, BLUE, 2, 18);
    const central = box(s, "central-box", 486, 378, 304, 104, TEAL_LIGHT, TEAL, 2, 18);
    const east = box(s, "east-box", 918, 378, 250, 104, ORANGE_LIGHT, ORANGE, 2, 18);
    text(s, "west-text", "西箱\n160°E—180°", 130, 396, 210, 70, { fontSize: 25, bold: true, align: "center", valign: "middle" });
    text(s, "central-text", "中箱\n180°—140°W", 510, 396, 256, 70, { fontSize: 25, bold: true, align: "center", valign: "middle" });
    text(s, "east-text", "东箱\n140°W—80°W", 938, 396, 210, 70, { fontSize: 25, bold: true, align: "center", valign: "middle" });
    text(s, "gate180", "180°", 386, 366, 74, 28, { fontSize: 20, bold: true, color: BLUE, align: "center" });
    text(s, "gate140", "140°W", 816, 366, 84, 28, { fontSize: 20, bold: true, color: ORANGE, align: "center" });
    box(s, "criterion-box", 164, 520, 952, 80, WHITE, BLUE_DARK, 3, 16);
    text(s, "criterion", "到达一致性：140°W东向输入 > 0　＋　东部 H₂₀ 增加", 190, 536, 900, 42, {
      fontSize: 27,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });
    text(s, "euler-note", "解释边界：这是欧拉控制体意义上的到达，不是同一水团的拉格朗日追踪。", 168, 606, 944, 30, {
      fontSize: 20,
      bold: true,
      color: BLUE_DARK,
      align: "center",
    });
    addNotes(s, [
      path.join(ROOT, "scripts/fetch_soda3_three_box_warm_heat_budget.py"),
      path.join(ROOT, "scripts/fetch_soda3_chakravorty_transport_baseline.py"),
      path.join(ROOT, "scripts/analyze_soda3_three_box_warm_heat_fate.py"),
    ]);
  }

  // Slide 4
  {
    const s = p.slides.add();
    s.background.fill = WHITE;
    title(s, "CT和CP的暖量都越过140°W，但CT明显更强");
    text(s, "phase", "本文定义的发展期：Jun(0)—Nov(0)｜SODA3.15.2｜累计异常暖量", 74, 118, 900, 32, {
      fontSize: 21,
      bold: true,
      color: BLUE_DARK,
    });
    addNativeChart(
      s,
      { left: 72, top: 152, width: 770, height: 442 },
      ["140°W东向输入", "东部H₂₀增长"],
      [
        { name: "CT", values: [6.25, 7.81], fill: ORANGE, valuesFormatCode: "0.00" },
        { name: "CP", values: [2.97, 3.71], fill: BLUE, valuesFormatCode: "0.00" },
      ],
      10,
      2,
      "累计暖量（ZJ）",
    );
    text(s, "result-1", "两类事件的两项指标均为正", 884, 178, 292, 72, {
      fontSize: 27,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });
    text(s, "result-1-sub", "95%区间均高于0", 892, 250, 276, 34, {
      fontSize: 21,
      bold: true,
      color: TEAL,
      align: "center",
    });
    box(s, "ct-strong", 874, 316, 310, 134, ORANGE_LIGHT, ORANGE, 2, 18);
    text(s, "ct-strong-text", "CT相对CP\n输入约2.1倍\n储热约2.1倍", 900, 334, 258, 96, {
      fontSize: 25,
      bold: true,
      color: ORANGE,
      align: "center",
      valign: "middle",
      lineSpacing: 1.08,
    });
    text(s, "not-equal", "输入量不要求等于储量增长：东箱还受到南北边界、海表通量和未解析过程影响。", 870, 486, 320, 102, {
      fontSize: 21,
      bold: true,
      color: NAVY,
      align: "left",
      valign: "middle",
      lineSpacing: 1.08,
    });
    takeaway(s, "第一部分答案：暖量确实进入东太平洋；CP不是“完全没有暖量东传”。", BLUE_DARK, 628, 58, 24);
    addNotes(s, [
      path.join(ROOT, "data/derived/research_2026/soda3_three_box_warm_heat_fate_cumulative_summary.csv"),
      path.join(ROOT, "scripts/analyze_soda3_three_box_warm_heat_fate.py"),
    ]);
  }

  // Slide 5
  {
    const s = p.slides.add();
    s.background.fill = WHITE;
    title(s, "1997暖量东传最强；2015与2023都进入东部");
    const ohc = await imageBytes(OHC_HOV);
    s.images.add({
      blob: ohc,
      contentType: "image/png",
      alt: "1997/98、2015/16和2023/24赤道太平洋0—300米上层海洋热含量异常的经度—时间演变",
      fit: "cover",
      crop: { left: 0, top: 0.085, right: 0, bottom: 0.055 },
      position: { left: 104, top: 120, width: 1072, height: 519 },
    });
    text(s, "ohc-meta", "色标：0—300 m OHC异常（GJ m⁻²）｜SODA3.15.2｜5°S—5°N平均｜1980—2024逐月去气候态并去同月线性趋势", 68, 652, 1144, 40, {
      fontSize: 20,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });
    addNotes(s, [
      OHC_HOV,
      path.join(ROOT, "scripts/analyze_soda3_ohc_predictability.py"),
      "SODA3.15.2; 5°S–5°N mean; 0–300 m OHC anomaly; 1980–2024 calendar-month climatology and same-month linear trend removed.",
    ]);
  }

  // Slide 6
  {
    const s = p.slides.add();
    s.background.fill = WHITE;
    title(s, "2015与2023的到达量近似，后续差异不能归因于“没到”");
    text(s, "phase", "事件比较：Jan(0)—Jun(0)｜基准1980—2014｜SODA3.15.2", 74, 118, 900, 32, {
      fontSize: 21,
      bold: true,
      color: BLUE_DARK,
    });
    addNativeChart(
      s,
      { left: 72, top: 152, width: 820, height: 432 },
      ["1997", "2015", "2023"],
      [
        { name: "140°W东向输入", values: [12.13, 3.30, 3.91], fill: ORANGE, valuesFormatCode: "0.00" },
        { name: "东部H₂₀增长", values: [9.29, 3.53, 3.88], fill: BLUE, valuesFormatCode: "0.00" },
      ],
      14,
      2,
      "累计暖量（ZJ）",
    );
    box(s, "similar-box", 920, 174, 286, 156, BLUE_LIGHT, BLUE, 3, 18);
    text(s, "similar-title", "2015 ≈ 2023", 940, 198, 246, 44, {
      fontSize: 32,
      bold: true,
      color: BLUE_DARK,
      align: "center",
      valign: "middle",
    });
    text(s, "similar-values", "输入：3.30 / 3.91 ZJ\n储热：3.53 / 3.88 ZJ", 938, 254, 250, 58, {
      fontSize: 21,
      bold: true,
      align: "center",
      valign: "middle",
    });
    box(s, "q500-box", 920, 354, 286, 148, ORANGE_LIGHT, ORANGE, 2, 18);
    text(s, "q500-title", "0—500 m OHC敏感性", 938, 372, 250, 34, {
      fontSize: 22,
      bold: true,
      color: ORANGE,
      align: "center",
    });
    text(s, "q500-values", "2015：6.43 ZJ\n2023：6.46 ZJ", 948, 420, 230, 62, {
      fontSize: 25,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });
    text(s, "q500-meaning", "结论不依赖H₂₀定义", 928, 520, 270, 34, {
      fontSize: 21,
      bold: true,
      color: TEAL,
      align: "center",
    });
    takeaway(s, "相近到达量没有产生相同演变：到达量本身不足以决定后续事件命运。", BLUE_DARK, 628, 58, 24);
    addNotes(s, [
      path.join(ROOT, "data/derived/research_2026/enso_1997_2015_2023_warm_heat_fate_phase_summary.csv"),
      path.join(ROOT, "data/derived/research_2026/soda3_h20_q500_three_event_phase_sensitivity.csv"),
      path.join(ROOT, "data/derived/research_2026/soda3_h20_q500_sensitivity_summary.json"),
    ]);
  }

  // Slide 7
  {
    const s = p.slides.add();
    s.background.fill = WHITE;
    title(s, "到达以后呢？下一步解释2015与2023为何走向不同");
    text(s, "next-question", "如果2015和2023都有相近的暖量输入和东部储热，为什么后续出口与海气演变明显不同？", 92, 126, 1096, 58, {
      fontSize: 26,
      bold: true,
      color: NAVY,
      align: "center",
      valign: "middle",
    });

    const ys = [220, 340, 460];
    const fills = [BLUE_LIGHT, ORANGE_LIGHT, TEAL_LIGHT];
    const lines = [BLUE, ORANGE, TEAL];
    const labels = ["暖量去了哪里？", "5°N出口由什么动力组成？", "相似FEP先暖为何没有形成相同耦合？"];
    const equations = [
      "dH₂₀/dt = Cₓ + F₁₀S + F₅N + Qsurface,warm + R₂₀",
      "Qtotal = Qgeo + QEkman + Qres",
      "FEP先暖 → OHC / D20预置 → 深对流与西风 → Ekman出口",
    ];
    const aims = [
      "区分边界输出、海表热损失与储量变化",
      "检验地转、Ekman和剩余项的相对贡献",
      "判断海洋预置能否转化为持续大气响应",
    ];
    for (let i = 0; i < 3; i += 1) {
      const number = s.shapes.add({
        geometry: "ellipse",
        name: `next-${i + 1}-number`,
        position: { left: 84, top: ys[i] + 14, width: 64, height: 64 },
        fill: lines[i],
        line: { style: "solid", fill: "none", width: 0 },
      });
      text(s, `next-${i + 1}-numtext`, String(i + 1), 84, ys[i] + 18, 64, 52, {
        fontSize: 29,
        bold: true,
        color: WHITE,
        align: "center",
        valign: "middle",
      });
      box(s, `next-${i + 1}-band`, 168, ys[i], 1038, 94, fills[i], lines[i], 2, 16);
      text(s, `next-${i + 1}-label`, labels[i], 192, ys[i] + 12, 430, 32, {
        fontSize: 23,
        bold: true,
        color: lines[i],
      });
      text(s, `next-${i + 1}-equation`, equations[i], 192, ys[i] + 50, 620, 30, {
        fontSize: i === 0 ? 19 : i === 1 ? 22 : 20,
        bold: true,
        color: NAVY,
        typeface: i < 2 ? MATH_FONT : FONT,
      });
      text(s, `next-${i + 1}-aim`, aims[i], 830, ys[i] + 24, 346, 48, {
        fontSize: 20,
        bold: true,
        color: NAVY,
        align: "center",
        valign: "middle",
      });
    }
    takeaway(s, "阶段性结论：暖量到达东部，但相近到达量不足以决定后续事件命运。", BLUE_DARK, 628, 58, 25);
    addNotes(s, [
      path.join(ROOT, "scripts/analyze_soda3_three_box_warm_heat_fate.py"),
      path.join(ROOT, "scripts/analyze_soda3_5n_current_decomposition.py"),
      path.join(ROOT, "scripts/analyze_soda3_5n_wind_stress_counterfactual.py"),
      "Causal boundary: current results motivate diagnostic attribution; they do not prove that arrival is a necessary condition or that wind alone determines event fate.",
    ]);
  }

  for (const [idx, slide] of p.slides.items.entries()) {
    const stem = `slide-${String(idx + 1).padStart(2, "0")}`;
    const png = await p.export({ slide, format: "png", scale: 1.5 });
    await fs.writeFile(path.join(BUILD, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(BUILD, `${stem}.layout.json`), await layout.text());
  }
  const montage = await p.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(path.join(BUILD, "montage.webp"), new Uint8Array(await montage.arrayBuffer()));

  const pptx = await PresentationFile.exportPptx(p);
  await pptx.save(FINAL);
  console.log(FINAL);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
