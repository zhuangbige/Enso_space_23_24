import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const W = 1280;
const H = 720;
const FONT = "PingFang SC";
const FONT_LATIN = "Arial";
const C = {
  ink: "#17202A",
  muted: "#52606D",
  blue: "#2F75B5",
  blueDark: "#1F4E79",
  bluePale: "#EAF3F8",
  blueLight: "#D8ECF8",
  orange: "#C8841D",
  orangePale: "#FBF1DF",
  red: "#B73B35",
  green: "#2D8C68",
  gray: "#EEF1F3",
  gray2: "#D8DEE3",
  white: "#FFFFFF",
  black: "#000000",
};

const ROOT = "/Users/daiyue/Documents/Maryland";
const BUILD = `${ROOT}/outputs/research_2026/ppt_build_20260807`;
const ASSET = `${BUILD}/assets`;
const FIG = `${ROOT}/outputs/research_2026/three_questions_figure_package_20260805/01_main_figures`;
const OUT = `${ROOT}/outputs/research_2026/presentations/ENSO暖量到达_去向_耦合命运_完整汇报_20260807.pptx`;
const REPORT = `${ROOT}/outputs/research_2026/reports/三个核心问题_发现提出回答_完整研究报告_公式严谨性修订版_20260807.docx`;

const DOI = {
  jin: "https://doi.org/10.1175/1520-0469(1997)054%3C0811:AEORPF%3E2.0.CO;2",
  wwV: "https://doi.org/10.1175/1520-0442(2000)013%3C3551:OOWWVC%3E2.0.CO;2",
  chak: "https://doi.org/10.1029/2020JC017075",
  soda3: "https://doi.org/10.1175/JCLI-D-17-0149.1",
  li2022: "https://doi.org/10.1007/s00382-021-06056-5",
  verdy: "https://doi.org/10.1029/2022JC019576",
  era5: "https://doi.org/10.1002/qj.3803",
  oisst: "https://doi.org/10.1175/JCLI-D-20-0166.1",
  gpcp: "https://doi.org/10.3390/atmos9020138",
};

async function bytes(path) {
  const b = await fs.readFile(path);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

function rect(slide, x, y, w, h, fill, opts = {}) {
  return slide.shapes.add({
    geometry: opts.geometry || "rect",
    name: opts.name,
    position: { left: x, top: y, width: w, height: h },
    fill: fill || "none",
    line: opts.line || { style: "solid", fill: "none", width: 0 },
    ...(opts.borderRadius ? { borderRadius: opts.borderRadius } : {}),
  });
}

function line(slide, x, y, w, color = C.gray2, width = 2) {
  return slide.shapes.add({
    geometry: "straightConnector1",
    position: { left: x, top: y, width: w, height: 0.1 },
    fill: "none",
    line: { style: "solid", fill: color, width },
  });
}

function text(slide, value, x, y, w, h, opts = {}) {
  const s = slide.shapes.add({
    geometry: "textbox",
    name: opts.name,
    position: { left: x, top: y, width: w, height: h },
    fill: opts.fill || "none",
    line: opts.line || { style: "solid", fill: "none", width: 0 },
  });
  s.text = value;
  s.text.style = {
    fontSize: opts.size || 24,
    typeface: opts.typeface || FONT,
    color: opts.color || C.ink,
    bold: opts.bold || false,
    alignment: opts.align || "left",
    verticalAlignment: opts.valign || "top",
    autoFit: opts.autoFit || "shrinkText",
    ...(opts.italic ? { italic: true } : {}),
  };
  return s;
}

function title(slide, value, opts = {}) {
  text(slide, value, 60, 34, 1160, 64, {
    size: opts.size || 40,
    bold: true,
    color: opts.color || C.ink,
    autoFit: "shrinkText",
  });
  line(slide, 60, 106, 1160, opts.rule || C.blue, 3);
}

function formula(slide, value, x, y, w, h, opts = {}) {
  rect(slide, x, y, w, h, opts.fill || C.gray, {
    geometry: "roundRect",
    borderRadius: "rounded-xl",
    line: { style: "solid", fill: opts.line || C.gray2, width: 1 },
  });
  text(slide, value, x + 18, y + 12, w - 36, h - 24, {
    size: opts.size || 28,
    bold: opts.bold || false,
    typeface: opts.typeface || FONT_LATIN,
    color: opts.color || C.ink,
    align: opts.align || "center",
    valign: "middle",
  });
}

function callout(slide, heading, body, x, y, w, h, color = C.blue) {
  const compact = h < 180;
  const headTop = compact ? 12 : 20;
  const headH = compact ? 36 : 48;
  const bodyTop = compact ? 52 : 72;
  const bodyBottom = compact ? 10 : 16;
  rect(slide, x, y, w, h, C.bluePale, {
    geometry: "roundRect",
    borderRadius: "rounded-xl",
    line: { style: "solid", fill: C.blueLight, width: 1 },
  });
  rect(slide, x, y, 9, h, color);
  text(slide, heading, x + 28, y + headTop, w - 52, headH, { size: compact ? 24 : 27, bold: true, color });
  text(slide, body, x + 28, y + bodyTop, w - 52, h - bodyTop - bodyBottom, { size: compact ? 20 : 22, color: C.ink, valign: "middle" });
}

function bullets(slide, items, x, y, w, h, opts = {}) {
  const value = items.map((item) => `• ${item}`).join("\n");
  return text(slide, value, x, y, w, h, {
    size: opts.size || 24,
    color: opts.color || C.ink,
    bold: opts.bold || false,
  });
}

function stat(slide, value, label, x, y, w, h, color = C.blue) {
  const compact = h < 190;
  const valueH = compact ? 64 : 86;
  const bodyTop = compact ? 86 : 112;
  const bodyBottom = compact ? 10 : 18;
  rect(slide, x, y, w, h, C.gray, {
    geometry: "roundRect",
    borderRadius: "rounded-xl",
    line: { style: "solid", fill: C.gray2, width: 1 },
  });
  text(slide, value, x + 20, y + 14, w - 40, valueH, { size: compact ? 39 : 42, bold: true, color, valign: "middle" });
  text(slide, label, x + 20, y + bodyTop, w - 40, h - bodyTop - bodyBottom, { size: compact ? 19 : 21, color: C.muted, valign: "middle" });
}

function table(slide, headers, rows, x, y, widths, rowH = 58, opts = {}) {
  const totalW = widths.reduce((a, b) => a + b, 0);
  let yy = y;
  rect(slide, x, yy, totalW, rowH, opts.headerFill || C.blueDark);
  let xx = x;
  headers.forEach((h, i) => {
    text(slide, h, xx + 8, yy + 7, widths[i] - 16, rowH - 14, {
      size: opts.headerSize || 21,
      bold: true,
      color: C.white,
      align: opts.alignments?.[i] || "center",
      valign: "middle",
    });
    xx += widths[i];
  });
  yy += rowH;
  rows.forEach((row, r) => {
    const fill = opts.highlightRows?.includes(r) ? C.orangePale : (r % 2 === 0 ? C.white : C.gray);
    rect(slide, x, yy, totalW, rowH, fill, { line: { style: "solid", fill: C.gray2, width: 1 } });
    let x2 = x;
    row.forEach((v, i) => {
      text(slide, String(v), x2 + 8, yy + 7, widths[i] - 16, rowH - 14, {
        size: opts.bodySize || 21,
        bold: opts.boldCols?.includes(i) || false,
        color: opts.colorCols?.[i] || C.ink,
        align: opts.alignments?.[i] || (i === 0 ? "left" : "center"),
        valign: "middle",
      });
      x2 += widths[i];
    });
    yy += rowH;
  });
  return yy;
}

async function image(slide, path, x, y, w, h, opts = {}) {
  const blob = await bytes(path);
  return slide.images.add({
    blob,
    contentType: path.toLowerCase().endsWith(".jpg") ? "image/jpeg" : "image/png",
    alt: opts.alt || "Scientific figure",
    fit: opts.fit || "contain",
    position: { left: x, top: y, width: w, height: h },
    ...(opts.crop ? { crop: opts.crop } : {}),
  });
}

function notes(slide, sources, extra = "") {
  const body = ["[Sources]", ...sources.map((s) => `- ${s}`), extra].filter(Boolean).join("\n");
  slide.speakerNotes.textFrame.setText(body);
  slide.speakerNotes.setVisible(false);
}

function newSlide(presentation, bg = C.white) {
  const slide = presentation.slides.add();
  slide.background.fill = bg;
  return slide;
}

function questionBox(slide, n, q, x, y, w, h, color) {
  rect(slide, x, y, w, h, C.gray, { geometry: "roundRect", borderRadius: "rounded-xl" });
  text(slide, String(n), x + 20, y + 14, 70, 70, { size: 46, bold: true, color, valign: "middle" });
  text(slide, q, x + 95, y + 14, w - 115, h - 28, { size: 27, bold: true, valign: "middle" });
}

async function main() {
  const p = Presentation.create({ slideSize: { width: W, height: H } });

  // 1. Cover
  {
    const s = newSlide(p);
    rect(s, 0, 0, 18, H, C.blueDark);
    text(s, "ENSO暖量到达—去向—耦合命运", 76, 178, 1100, 150, { size: 62, bold: true, color: C.ink, valign: "middle" });
    text(s, "从 Chakravorty et al. (2021) 到 SODA3 三问题诊断闭环", 80, 360, 1040, 70, { size: 30, color: C.blueDark });
    notes(s, [REPORT, DOI.chak]);
  }

  // 2. Starting point
  {
    const s = newSlide(p);
    title(s, "研究起点：Chakravorty等（2021）回答了“充放电是否不同”");
    callout(s, "原文核心结论", "CT事件具有更清晰的赤道暖水充—放电演变；CP事件的充放电信号相对较弱。", 60, 150, 520, 220, C.blue);
    callout(s, "主要方法", "SODA2.1.6事件合成、CHI、D20 EOF与归一化暖水输送，比较不同厄尔尼诺类型。", 60, 395, 520, 220, C.green);
    text(s, "尚未直接回答", 680, 155, 430, 54, { size: 31, bold: true, color: C.red });
    bullets(s, ["输送的暖水究竟带走多少能量？", "暖量是否真的进入东太平洋？", "到达之后从哪里离开、由什么动力控制？"], 680, 230, 470, 280, { size: 27 });
    formula(s, "标准化输送  →  ZJ级暖量命运", 680, 520, 470, 100, { size: 31, color: C.blueDark, fill: C.bluePale });
    notes(s, [DOI.chak, REPORT]);
  }

  // 3. Timeline
  {
    const s = newSlide(p);
    title(s, "研究如何从“充放电”走到“暖量去哪了”");
    line(s, 100, 340, 1080, C.blueDark, 3);
    const xs = [110, 320, 535, 750, 965, 1165];
    const labels = [
      ["复现", "CT/CP充放电"],
      ["量纲化", "WWV→H20"],
      ["追踪", "Qwarm,20三箱"],
      ["归宿", "5°N/10°S/散热"],
      ["个例", "三事件对比"],
      ["归因", "海洋预置×风驱"],
    ];
    xs.forEach((x, i) => {
      rect(s, x - 9, 331, 18, 18, i < 3 ? C.blue : C.orange, { geometry: "ellipse" });
      text(s, labels[i][0], x - 80, 235, 160, 48, { size: 25, bold: true, align: "center", color: i < 3 ? C.blueDark : C.orange });
      text(s, labels[i][1], x - 90, 380, 180, 92, { size: 22, align: "center", valign: "middle" });
    });
    text(s, "每一步都把前一步的“有无/强弱”问题推进为可闭合的能量与动力问题。", 120, 545, 1040, 72, { size: 29, bold: true, color: C.blueDark, align: "center" });
    notes(s, [REPORT, DOI.chak]);
  }

  // 4. Literature gap
  {
    const s = newSlide(p);
    title(s, "已有研究提供了三块拼图，但尚未把它们闭合");
    const cols = [70, 445, 820];
    const heads = ["充放电与WWV", "海洋热量收支", "ENSO多样性与2023事件"];
    const bodies = [
      "解释赤道暖水体积如何随ENSO充放电，但多用体积或标准化输送。",
      "能闭合温盐、表面通量与经向输送，却少有CT/CP及三事件统一比较。",
      "揭示2023/24风场与背景异常特殊，但未回答同样FEP先暖为何导向不同暖量命运。",
    ];
    cols.forEach((x, i) => {
      text(s, heads[i], x, 160, 330, 70, { size: 28, bold: true, color: i === 2 ? C.orange : C.blueDark });
      line(s, x, 242, 330, C.gray2, 2);
      text(s, bodies[i], x, 270, 330, 200, { size: 23 });
    });
    callout(s, "本文补上的闭环", "在同一SODA3框架中同时量化：暖量到达、到达后的分配、地转—Ekman竞争，以及表面增暖向海气耦合响应的转化效率。", 110, 525, 1060, 120, C.blue);
    notes(s, [DOI.jin, DOI.wwV, DOI.li2022, DOI.verdy, DOI.chak, REPORT]);
  }

  // 5. Core questions
  {
    const s = newSlide(p);
    title(s, "整项工作收束为三个彼此递进的问题");
    questionBox(s, 1, "暖量是否真正到达东太平洋？", 70, 150, 1140, 120, C.blue);
    questionBox(s, 2, "到达后的暖量去了哪里？", 70, 300, 1140, 120, C.orange);
    questionBox(s, 3, "相似FEP先暖为何产生不同暖量命运？", 70, 450, 1140, 120, C.green);
    text(s, "到达  →  分配  →  海气耦合控制", 160, 610, 960, 56, { size: 32, bold: true, color: C.blueDark, align: "center" });
    notes(s, [REPORT]);
  }

  // 6. Data architecture
  {
    const s = newSlide(p);
    title(s, "数据体系：海洋主产品负责闭合，独立资料约束海气响应");
    table(s,
      ["数据", "变量", "在本文中的作用"],
      [
        ["SODA3.15.2", "T、S、u/v、SSH、τ、Qnet", "H20、Qwarm,20、三箱预算、地转/Ekman"],
        ["OISST", "SST", "FEP表面增暖与个例空间结构"],
        ["ERA5", "u850、SLP、应力、热通量", "大气闭合、风驱与独立通量检验"],
        ["GPCP / CPC OLR", "降水、OLR", "深对流和东西向迁移"],
        ["ORAS5（图件补充）", "OHC", "1997/2023盆地热库存对照"],
      ],
      75, 150, [235, 330, 565], 76, { bodySize: 21, headerSize: 23, alignments: ["left", "left", "left"] });
    notes(s, [DOI.soda3, DOI.era5, DOI.oisst, DOI.gpcp, REPORT]);
  }

  // 7. Samples and windows
  {
    const s = newSlide(p);
    title(s, "样本与时段：合成、个例和事件统计各回答不同层次");
    stat(s, "4 + 4", "与Chakravorty重叠的CT/CP事件，用于类型合成。", 70, 165, 350, 210, C.blue);
    stat(s, "3", "1997、2015、2023过程个例，用于机制对照。", 465, 165, 350, 210, C.orange);
    stat(s, "13", "1982—2023暖事件，用于事件级相关和置换统计。", 860, 165, 350, 210, C.green);
    table(s,
      ["阶段", "时间窗口", "诊断目标"],
      [
        ["发展期", "Jan—Jun(0) / Jun—Nov(0)", "跨140°W输入与东部储热"],
        ["成熟—衰减", "Dec(0)—May(+1)", "5°N/10°S输出、海表散热与储量下降"],
        ["海气接通", "Mar—Jun(0)", "FEP—OHC—u850—对流闭合"],
      ],
      150, 440, [250, 330, 550], 62, { bodySize: 21, headerSize: 22, alignments: ["left", "center", "left"] });
    notes(s, [REPORT, DOI.chak]);
  }

  // 8. H20
  {
    const s = newSlide(p);
    title(s, "H20把暖水体积转化为可比较的阈值相对热含量");
    formula(s, "χ₂₀(T) = max(T − Tᵣ, 0),      I₂₀ = 1(T > Tᵣ),      Tᵣ = 20°C", 90, 145, 1100, 90, { size: 31 });
    formula(s, "WWV = ∭ I₂₀ dV", 90, 270, 320, 110, { size: 33, color: C.blueDark, fill: C.bluePale });
    text(s, "×", 435, 288, 50, 60, { size: 44, bold: true, align: "center" });
    formula(s, "ΔT̄₂₀ =  ∭χ₂₀dV / ∭I₂₀dV", 510, 270, 370, 110, { size: 30 });
    text(s, "→", 900, 288, 80, 60, { size: 44, bold: true, align: "center", color: C.orange });
    formula(s, "H₂₀ = ρ₀cₚ ∭χ₂₀ dV", 970, 270, 250, 110, { size: 29, color: C.orange, fill: C.orangePale });
    bullets(s, ["20°C由温跃层位移和WWV动力意义决定，不是绝对热力参考态。", "H20表示20°C阈值以上的相对热含量，单位J或ZJ。"], 130, 450, 1020, 140, { size: 26 });
    notes(s, [DOI.wwV, DOI.jin, REPORT]);
  }

  // 9. Qwarm
  {
    const s = newSlide(p);
    title(s, "Qwarm,20量化穿过固定断面的暖水体阈值能量输送");
    formula(s, "Qwarm,20 = ρ₀cₚ ∬Γ vₙ χ₂₀(T) dA", 125, 165, 1030, 130, { size: 39, color: C.blueDark, fill: C.bluePale });
    table(s,
      ["量纲因子", "单位", "物理意义"],
      [
        ["ρ₀", "kg m⁻³", "海水密度"],
        ["cₚ", "J kg⁻¹ K⁻¹", "定压比热"],
        ["vₙ χ₂₀ dA", "m³ K s⁻¹", "暖水体跨断面输送"],
        ["Qwarm,20", "J s⁻¹ = W", "通常以PW表示"],
      ],
      170, 350, [280, 280, 390], 58, { bodySize: 22, headerSize: 23 });
    text(s, "它不是传统 ρcₚ∫vT dA 的总海洋热输送。", 210, 625, 860, 45, { size: 27, bold: true, color: C.red, align: "center" });
    notes(s, [REPORT, DOI.chak]);
  }

  // 10. Threshold budget
  {
    const s = newSlide(p);
    title(s, "阈值暖量预算是诊断恒等式，不应写成普通温度守恒方程");
    formula(s, "dH₂₀/dt = ΣΓ FΓ + Qsurface,warm + R₂₀", 120, 160, 1040, 120, { size: 39, color: C.blueDark, fill: C.bluePale });
    formula(s, "FΓ = −ρ₀cₚ ∬Γ (v·nout) χ₂₀ dA     （FΓ > 0 表示进入箱体）", 120, 320, 1040, 100, { size: 29 });
    bullets(s, ["χ₂₀(T)是非线性阈值算子。", "绝热不可压平流在几乎处处满足链式法则。", "混合、扩散、卷挟、强迫导致的跨20°C转换进入R₂₀。"], 150, 475, 980, 155, { size: 25 });
    notes(s, [REPORT]);
  }

  // 11. Three boxes
  {
    const s = newSlide(p);
    title(s, "三箱设计把“向东输送”转化为可闭合的空间收支");
    // connectors first
    line(s, 320, 335, 110, C.blueDark, 6);
    line(s, 720, 335, 110, C.blueDark, 6);
    text(s, "→", 405, 300, 70, 70, { size: 50, bold: true, color: C.blueDark, align: "center" });
    text(s, "→", 805, 300, 70, 70, { size: 50, bold: true, color: C.blueDark, align: "center" });
    const boxes = [
      [80, "西部蓄水库", "160°E—180°E"],
      [480, "中太平洋通道", "180°—140°W"],
      [880, "东太平洋受热区", "140°W—80°W"],
    ];
    boxes.forEach((b, i) => {
      rect(s, b[0], 215, 320, 250, i === 2 ? C.orangePale : C.bluePale, { geometry: "roundRect", borderRadius: "rounded-xl", line: { style: "solid", fill: i === 2 ? C.orange : C.blue, width: 2 } });
      text(s, b[1], b[0] + 25, 255, 270, 64, { size: 29, bold: true, align: "center", color: i === 2 ? C.orange : C.blueDark });
      text(s, b[2], b[0] + 25, 340, 270, 48, { size: 24, align: "center" });
    });
    text(s, "每个箱同时计算：储量倾向、东西边界、5°N/10°S、海表通量和剩余项。", 100, 540, 1080, 70, { size: 28, bold: true, color: C.blueDark, align: "center" });
    notes(s, [REPORT]);
  }

  // 12. Surface flux and residual
  {
    const s = newSlide(p);
    title(s, "表面加热和剩余项必须明确各自的物理边界");
    formula(s, "Qsurface,warm = ∬ I₂₀(Ts) Qnet dA", 90, 160, 520, 115, { size: 33, color: C.orange, fill: C.orangePale });
    bullets(s, ["只保留表层温度高于20°C格点的净热通量。", "月平均有限表层温度是阈值热源的一阶近似。", "D20>0仅作暖层足迹敏感性，不作主定义。"], 90, 315, 520, 245, { size: 24 });
    formula(s, "R₂₀ = dH₂₀/dt − ΣFΓ − Qsurface,warm", 670, 160, 520, 115, { size: 30, color: C.blueDark, fill: C.bluePale });
    bullets(s, ["包含垂向/斜压交换、混合、卷挟。", "包含跨20°C等温面转换和离散误差。", "不能把R₂₀预先命名为某一种洋流。"], 670, 315, 520, 245, { size: 24 });
    notes(s, [REPORT]);
  }

  // 13. Geostrophic derivation
  {
    const s = newSlide(p);
    title(s, "5°N地转输送由海表高度梯度与密度梯度共同决定");
    formula(s, "f v_g = (1/ρ₀) ∂p/∂x", 100, 145, 420, 80, { size: 33 });
    formula(s, "p(d) = ρ₀gη + g∫₀ᵈ ρ′(d′) dd′", 570, 145, 610, 80, { size: 31 });
    formula(s, "v_g(d) = (g/f)∂η/∂x + [g/(ρ₀f)]∫₀ᵈ ∂ρ′/∂x dd′", 100, 270, 1080, 115, { size: 31, color: C.blueDark, fill: C.bluePale });
    table(s,
      ["分量", "压力来源", "解释"],
      [
        ["SSH地转", "∂η/∂x", "海面坡度控制的深度一致流"],
        ["密度地转", "∫∂ρ′/∂x dd′", "斜压密度结构控制的热成风贡献"],
      ],
      170, 445, [260, 330, 430], 68, { bodySize: 22, headerSize: 23 });
    text(s, "ρ′ = ρ − ρref(d)；若参考密度仅随深度变化，∂ρ′/∂x = ∂ρ/∂x。", 150, 640, 980, 42, { size: 23, color: C.muted, align: "center" });
    notes(s, [REPORT]);
  }

  // 14. Ekman and identity
  {
    const s = newSlide(p);
    title(s, "Ekman风驱项与地转压力项构成出口动力竞争");
    formula(s, "Mᵧ = −τₓ/(ρ₀ f)", 90, 160, 430, 100, { size: 38, color: C.orange, fill: C.orangePale });
    formula(s, "QEkman = ρ₀cₚ ∫ Mᵧ · χ̄₂₀,E dx", 570, 160, 620, 100, { size: 32, color: C.orange, fill: C.orangePale });
    bullets(s, ["τx向东为正，Mᵧ向北为正；北半球西风异常对应向南Ekman输送。", "热权重使用Ekman层暖温差平均，是一阶深度积分估算。"], 120, 310, 1040, 120, { size: 25 });
    formula(s, "Qtotal = Qgeo + QEkman + Qres", 140, 470, 1000, 100, { size: 39, color: C.blueDark, fill: C.bluePale });
    text(s, "这是诊断恒等式；Qres包含年龄转、瞬变涡旋、惯性与近似误差。", 180, 610, 920, 48, { size: 25, bold: true, align: "center" });
    notes(s, [REPORT]);
  }

  // 15. FEP residual
  {
    const s = newSlide(p);
    title(s, "FEP residual分离“最东部增暖”与传统Niño-3.4共同变化");
    formula(s, "FEP′ₘ = aₘ + bₘ Niño3.4′ₘ + εₘ", 115, 160, 1050, 100, { size: 37, color: C.blueDark, fill: C.bluePale });
    formula(s, "FEPres,ₘ = FEP′ₘ − (aₘ + bₘ Niño3.4′ₘ)", 115, 300, 1050, 100, { size: 35 });
    stat(s, "43", "1982—2024，每个日历月独立回归。", 110, 465, 330, 160, C.blue);
    stat(s, "41", "OLS回归自由度 n−2。", 475, 465, 330, 160, C.orange);
    stat(s, "13", "暖事件样本用于机制关系。", 840, 465, 330, 160, C.green);
    notes(s, [REPORT]);
  }

  // 16. Stats and wind swap
  {
    const s = newSlide(p);
    title(s, "事件统计与换风实验把第三问推进到定量过程归因");
    callout(s, "13事件统计", "报告Pearson r、事件bootstrap 95%区间、事件置换p和逐一删除事件后的r范围；p值只作辅助证据。", 70, 150, 500, 230, C.green);
    formula(s, "Qrec(i←j) = Qgeo(i) + Qres(i) + QEkman[T(i), τx(j)]", 625, 155, 585, 135, { size: 28, color: C.blueDark, fill: C.bluePale });
    text(s, "固定海洋温度、地转项和残差，只替换局地5°N风应力。", 650, 315, 535, 74, { size: 24, bold: true, align: "center" });
    callout(s, "因果边界", "该试验不重新积分海洋或大气，也不允许压力场和残差响应新风场；因此是离线反事实敏感性试验，不是完整因果检验。", 170, 455, 940, 150, C.red);
    notes(s, [REPORT]);
  }

  // 17. Fig01
  {
    const s = newSlide(p);
    title(s, "问题一证据：暖异常沿赤道向东传播，但次表层支撑强度不同");
    await image(s, `${FIG}/Fig01_eastward_OHC_arrival_hovmoller.png`, 60, 125, 1160, 550, { alt: "1997、2015和2023赤道太平洋OHC向东传播Hovmöller图" });
    notes(s, [`${FIG}/Fig01_eastward_OHC_arrival_hovmoller.png`, DOI.soda3, REPORT]);
  }

  // 18. Fig02
  {
    const s = newSlide(p);
    title(s, "CT与CP都能把暖量送入东部，差别在强度与后续分配");
    await image(s, `${FIG}/Fig02_CT_CP_three_box_arrival_and_fate.png`, 50, 130, 860, 540, { alt: "CT和CP三箱暖量到达与去向" });
    callout(s, "关键判断", "两组发展期跨140°W输入均为正；因此不能把类型差异写成“CT到达、CP不到达”。\n\n真正差别是东部增热幅度，以及成熟—衰减期5°N与表面散热的分配。", 930, 165, 300, 420, C.blue);
    notes(s, [`${FIG}/Fig02_CT_CP_three_box_arrival_and_fate.png`, DOI.chak, DOI.soda3, REPORT]);
  }

  // 19. Arrival table + answer
  {
    const s = newSlide(p);
    title(s, "1997输入最强；2015与2023的发展期到达量十分接近");
    table(s,
      ["事件", "140°W Qwarm,20", "东部H20变化", "东部SST", "东部D20"],
      [
        ["1997", "+12.13 ZJ", "+9.29 ZJ", "+0.35°C", "+17.27 m"],
        ["2015", "+3.30 ZJ", "+3.53 ZJ", "+0.98°C", "+15.09 m"],
        ["2023", "+3.91 ZJ", "+3.88 ZJ", "+0.93°C", "+12.03 m"],
      ],
      70, 155, [150, 260, 250, 220, 220], 72, { bodySize: 22, headerSize: 21, highlightRows: [1, 2] });
    callout(s, "问题一的答案", "暖量确实通过赤道上层海洋和140°W通道进入东太平洋；1997最强，2015与2023的输入近似。事件分岔不能归因于2023“暖量没来”。", 110, 505, 1060, 130, C.blue);
    notes(s, [REPORT, `${FIG}/Fig03_event_arrival_export_surface_loss.png`]);
  }

  // 20. Fig03
  {
    const s = newSlide(p);
    title(s, "问题二证据：相似到达后，三事件走向强排放—部分排放—近闭合", { size: 36 });
    await image(s, `${FIG}/Fig03_event_arrival_export_surface_loss.png`, 50, 130, 860, 540, { alt: "1997、2015和2023到达、输出和海表散热对比" });
    callout(s, "三种命运", "1997：北向输出与海表散热都强。\n\n2015：出口与散热减弱，但仍有净排放。\n\n2023：5°N出口近闭合，海表热损失也最弱。", 930, 165, 300, 420, C.orange);
    notes(s, [`${FIG}/Fig03_event_arrival_export_surface_loss.png`, DOI.soda3, DOI.era5, REPORT]);
  }

  // 21. Composite budget
  {
    const s = newSlide(p);
    title(s, "CT/CP合成表明：关键分叉位于东部箱5°N北界");
    table(s,
      ["类型", "H20变化", "5°N北向输出", "10°S南向输出", "海表热损失", "预算剩余"],
      [
        ["CT", "−7.86", "+2.74", "+0.68", "+3.69", "+2.09"],
        ["CP", "−3.03", "−0.96", "−0.48", "+1.76", "+0.82"],
      ],
      60, 160, [140, 190, 220, 220, 200, 190], 82, { bodySize: 23, headerSize: 20, boldCols: [0], colorCols: { 2: C.orange } });
    stat(s, "+3.70 ZJ", "CT−CP的5°N北向输出差；95%区间[+1.65,+5.65]。", 100, 430, 330, 180, C.orange);
    stat(s, "+3.05 ZJ", "ERA5海表净热损失CT−CP差，95%区间为正。", 475, 430, 330, 180, C.blue);
    stat(s, "≈ 0", "10°S项组内区间跨零，不是稳健主出口。", 850, 430, 330, 180, C.green);
    notes(s, [REPORT, DOI.soda3, DOI.era5]);
  }

  // 22. Fig04
  {
    const s = newSlide(p);
    title(s, "5°N出口由Ekman风驱与地转压力场的竞争决定");
    await image(s, `${FIG}/Fig04_event_5N_dynamical_decomposition.png`, 50, 130, 860, 540, { alt: "三事件5°N总暖量输送的地转、Ekman和残差分解" });
    callout(s, "动力分解", "1997：Ekman与地转同向排放。\n\n2015：Ekman足以克服南向地转阻力。\n\n2023：地转阻力与2015相近，但Ekman较弱，总出口接近零。", 930, 165, 300, 420, C.orange);
    notes(s, [`${FIG}/Fig04_event_5N_dynamical_decomposition.png`, DOI.soda3, REPORT]);
  }

  // 23. Event fate table + answer
  {
    const s = newSlide(p);
    title(s, "问题二的答案：暖量主要经5°N、海表散热和储量变化重新分配");
    table(s,
      ["事件", "5°N总输出", "海表热损失", "东部H20变化", "4.75°N单边估计"],
      [
        ["1997", "+3.81 ZJ", "+4.37 ZJ", "−9.73 ZJ", "+3.85 ZJ"],
        ["2015", "+0.88 ZJ", "+1.16 ZJ", "−11.10 ZJ", "+0.92 ZJ"],
        ["2023", "+0.10 ZJ", "+0.40 ZJ", "−9.14 ZJ", "−1.24 ZJ"],
      ],
      70, 150, [150, 240, 240, 240, 250], 70, { bodySize: 22, headerSize: 21, highlightRows: [2] });
    callout(s, "结论边界", "10°S不是稳健主出口；2023对5°N通量面温度插值敏感，因此最稳健表述是“出口显著受抑或近闭合”，而不是断言其必然净向南。", 120, 505, 1040, 130, C.red);
    notes(s, [REPORT]);
  }

  // 24. Fig05
  {
    const s = newSlide(p);
    title(s, "问题三起点：相似FEP先暖不代表相同次表层海洋状态");
    await image(s, `${FIG}/Fig05_FEP_subsurface_preconditioning.png`, 50, 125, 900, 550, { alt: "FEP、OHC与D20的1997、2015和2023过程对比" });
    callout(s, "2023的关键异常", "3—4月FEP最暖，但中太平洋OHC只有+0.50 GJ m⁻²；给定FEP后的OHC残差为−0.61 GJ m⁻²，在13事件中最低。", 970, 170, 270, 390, C.green);
    notes(s, [`${FIG}/Fig05_FEP_subsurface_preconditioning.png`, DOI.soda3, DOI.oisst, REPORT]);
  }

  // 25. Fig06
  {
    const s = newSlide(p);
    title(s, "决定性分叉发生在表面增暖之后、深对流东移之前");
    await image(s, `${FIG}/Fig06_FEP_atmospheric_closure.png`, 60, 125, 1160, 550, { alt: "FEP到OHC、D20、u850和OLR闭合的三事件时间线" });
    notes(s, [`${FIG}/Fig06_FEP_atmospheric_closure.png`, DOI.era5, DOI.oisst, REPORT]);
  }

  // 26. Fig07 heat release and wind stress
  {
    const s = newSlide(p);
    title(s, "1997在3月形成暖量释放—西风应力接通，2023明显延迟");
    await image(s, `${ASSET}/Fig07_release_clean.png`, 60, 130, 1160, 390, { alt: "1997与2023五日暖量释放和纬向风应力对比" });
    rect(s, 60, 130, 1160, 12, C.white);
    rect(s, 535, 171, 210, 14, C.white);
    rect(s, 85, 555, 520, 90, C.orangePale, { geometry: "roundRect", borderRadius: "rounded-xl", line: { style: "solid", fill: C.orange, width: 1 } });
    rect(s, 675, 555, 520, 90, C.bluePale, { geometry: "roundRect", borderRadius: "rounded-xl", line: { style: "solid", fill: C.blue, width: 1 } });
    text(s, "1997：3月中旬释放与西风同步转强", 110, 574, 470, 54, { size: 24, bold: true, color: C.orange, align: "center", valign: "middle" });
    text(s, "2023：释放先起，5月中旬后才共同接通", 700, 574, 470, 54, { size: 24, bold: true, color: C.blueDark, align: "center", valign: "middle" });
    notes(s, [`${FIG}/Fig07_1997_2023_coupled_mechanism_synthesis.png`, DOI.era5, DOI.oisst, REPORT]);
  }

  // 27. Fig07 ocean preconditioning
  {
    const s = newSlide(p);
    title(s, "相似FEP暖度下，1997与2023的海洋热库存和次表层倾斜完全不同", { size: 34 });
    await image(s, `${ASSET}/Fig07_ocean_clean.png`, 60, 130, 1160, 470, { alt: "1997与2023海洋热库存、东移比例、FEP暖度和D20东西倾斜对比" });
    text(s, "1997具有更大的可用热库存与更强的东移次表层结构；2023主要表现为表面暖、深层支撑弱。", 105, 610, 1070, 54, { size: 25, bold: true, color: C.green, align: "center", valign: "middle" });
    notes(s, [`${FIG}/Fig07_1997_2023_coupled_mechanism_synthesis.png`, DOI.era5, DOI.oisst, DOI.gpcp, REPORT]);
  }

  // 28. Fig07 atmospheric closure
  {
    const s = newSlide(p);
    title(s, "次表层预置决定风场能否持续组织深对流和气压梯度");
    await image(s, `${ASSET}/Fig07_atmos_clean.png`, 60, 135, 1160, 455, { alt: "1997与2023中太平洋西风、深对流、降水迁移和海平面气压梯度对比" });
    rect(s, 60, 495, 1160, 20, C.white);
    text(s, "1997在3月同步建立西风、深对流东移和有利气压梯度；2023的响应弱且不连续。", 115, 610, 1050, 54, { size: 25, bold: true, color: C.blueDark, align: "center", valign: "middle" });
    notes(s, [`${FIG}/Fig07_1997_2023_coupled_mechanism_synthesis.png`, DOI.era5, DOI.oisst, DOI.gpcp, REPORT]);
  }

  // 29. Fig08
  {
    const s = newSlide(p);
    title(s, "13事件统计和局地换风共同锁定“海洋预置—西风—Ekman出口”链条");
    await image(s, `${FIG}/Fig08_third_question_coupled_attribution.png`, 50, 130, 860, 540, { alt: "13暖事件相关与离线风应力互换试验" });
    callout(s, "两条事件联系", "OHC → u850：r=+0.89，95%区间[+0.39,+0.97]。\n\nu850 → 次年Ekman：r=+0.75，95%区间[+0.18,+0.92]。", 930, 150, 300, 240, C.green);
    callout(s, "换风结果", "固定2023海洋状态：使用2023风为+0.10 ZJ；换2015风为+0.88 ZJ；换1997风为+2.10 ZJ。", 930, 420, 300, 200, C.orange);
    notes(s, [`${FIG}/Fig08_third_question_coupled_attribution.png`, DOI.soda3, DOI.era5, REPORT]);
  }

  // 29. Q3 answer
  {
    const s = newSlide(p);
    title(s, "问题三的答案：FEP先暖只是表面起点，耦合效率决定暖量命运");
    const xs = [80, 390, 700, 1010];
    const heads = ["表面触发", "次表层预置", "大气接通", "出口结果"];
    const bodies = ["FEP首先变暖", "OHC与D20/SSH结构决定可用热库存", "深对流东移并建立西风和SLP梯度", "Ekman能否克服地转阻力"];
    // arrows first
    for (let i = 0; i < 3; i++) text(s, "→", xs[i] + 240, 330, 70, 70, { size: 48, bold: true, color: C.blueDark, align: "center" });
    xs.forEach((x, i) => {
      rect(s, x, 220, 230, 260, i === 0 ? C.orangePale : C.bluePale, { geometry: "roundRect", borderRadius: "rounded-xl", line: { style: "solid", fill: i === 0 ? C.orange : C.blue, width: 2 } });
      text(s, heads[i], x + 20, 255, 190, 52, { size: 27, bold: true, align: "center", color: i === 0 ? C.orange : C.blueDark });
      text(s, bodies[i], x + 24, 330, 182, 110, { size: 22, align: "center", valign: "middle" });
    });
    text(s, "2023的异常不是“表面不暖”，而是FEP暖度与次表层预置严重不匹配，随后西风和出口均弱。", 110, 555, 1060, 70, { size: 28, bold: true, color: C.red, align: "center" });
    notes(s, [REPORT]);
  }

  // 30. Robustness
  {
    const s = newSlide(p);
    title(s, "稳健性检验保留了符号、排序和动力竞争结论");
    table(s,
      ["事件", "总量 1980—2014", "总量 1982—2022", "地转 1980—2014", "地转 1982—2022", "线性EOS地转"],
      [
        ["1997", "+3.81", "+3.85", "+0.59", "+0.73", "+0.58"],
        ["2015", "+0.88", "+1.52", "−1.28", "−0.45", "−1.35"],
        ["2023", "+0.10", "+0.99", "−1.27", "−0.13", "−1.32"],
      ],
      50, 145, [130, 215, 215, 215, 215, 190], 64, { bodySize: 21, headerSize: 18 });
    bullets(s, ["两种距平基准下总出口均保持1997 > 2015 > 2023。", "Ekman符号与地转符号不变；线性状态方程不改变地转方向。", "事件相关逐一删除后仍保持正相关，极端事件并非唯一支撑。"], 130, 470, 1020, 155, { size: 25 });
    notes(s, [REPORT]);
  }

  // 31. Completion and limits
  {
    const s = newSlide(p);
    title(s, "三个问题已经形成论文逻辑链，但边界必须写清楚");
    table(s,
      ["问题", "已解决", "仍保留的边界", "判断"],
      [
        ["暖量是否到达", "140°W、H20、OHC/D20/SSH共同约束", "不是同一水团拉格朗日追踪", "主体解决"],
        ["暖量去了哪里", "5°N、10°S、散热、储量与剩余项", "剩余项尚未完全物理拆分", "主要通道解决"],
        ["为什么命运不同", "三事件过程、13事件统计、局地换风", "上游唯一根因需模式集合", "过程归因解决"],
      ],
      55, 145, [205, 370, 360, 230], 92, { bodySize: 20, headerSize: 22, alignments: ["left", "left", "left", "center"] });
    callout(s, "不能过度声称", "欧拉预算不是同一水团追踪；R₂₀不是单一过程；换风不是完整因果试验；13事件不代表普适定律。", 140, 535, 1000, 125, C.red);
    notes(s, [REPORT]);
  }

  // 32. Main conclusion
  {
    const s = newSlide(p);
    title(s, "主结论：事件命运取决于暖量到达后的耦合分配");
    stat(s, "到达", "CT与CP均可把暖量送入东部；2015与2023输入近似。", 65, 175, 360, 300, C.blue);
    stat(s, "去向", "暖量在5°N、海表散热、储量变化和剩余过程中重新分配。", 460, 175, 360, 300, C.orange);
    stat(s, "控制", "次表层预置调制大气接通；局地风驱Ekman决定能否克服地转阻力。", 855, 175, 360, 300, C.green);
    text(s, "2015与2023的直接分水岭：海洋压力场相近，但2015风驱足以打开北向出口，2023不足。", 100, 545, 1080, 90, { size: 30, bold: true, color: C.blueDark, align: "center" });
    notes(s, [REPORT]);
  }

  // 33. Next steps
  {
    const s = newSlide(p);
    title(s, "下一步不是再堆相关图，而是完成两项决定性边界工作");
    callout(s, "1  拆分预算剩余项", "用五日三维热收支继续分离混合、垂向/斜压交换、跨20°C转换和离散误差，判断每一焦耳的最终归宿。", 80, 155, 520, 230, C.blue);
    callout(s, "2  受控模式因果检验", "在海洋模式或耦合模式中关闭/替换5°N异常风应力，并做海盆上游因子集合，检验第三问的因果充分性。", 680, 155, 520, 230, C.orange);
    bullets(s, ["离线粒子或水团标签：连接“到达”与“去向”的拉格朗日轨迹。", "多产品与高频断面：降低SODA3同化依赖和2024年通量面插值敏感性。", "模式过程指标：把5°N Qwarm,20、压力场—Ekman竞争和海表热损失用于模式评估。"], 120, 455, 1040, 165, { size: 24 });
    notes(s, [REPORT]);
  }

  await fs.mkdir(`${BUILD}/render`, { recursive: true });
  for (const [i, slide] of p.slides.items.entries()) {
    const png = await p.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(`${BUILD}/render/slide-${String(i + 1).padStart(2, "0")}.png`, new Uint8Array(await png.arrayBuffer()));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(`${BUILD}/render/slide-${String(i + 1).padStart(2, "0")}.layout.json`, await layout.text());
  }
  const montage = await p.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(`${BUILD}/render/montage.webp`, new Uint8Array(await montage.arrayBuffer()));
  const pptx = await PresentationFile.exportPptx(p);
  await pptx.save(OUT);
  console.log(OUT);
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
