import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  PresentationFile,
} from "@oai/artifact-tool";

process.on("uncaughtException", (error) => {
  console.error(JSON.stringify({
    name: error?.name,
    message: error?.message,
    stack: String(error?.stack ?? "").split("\n").filter((entry) => entry.includes("build_formula_data_robust") || entry.startsWith(`${error?.name}:`)),
  }, null, 2));
  process.exit(1);
});

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_formula_data_20260811");
const SOURCE = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_三文献图解扩展版_20260811.pptx",
);
const OUT = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_公式数据扩展版_20260811.pptx",
);
const PREVIEW = path.join(TMP, "final-preview");
const LAYOUT = path.join(TMP, "final-layout");

const C = {
  navy: "#0A2234",
  blue: "#2F80B9",
  blueDark: "#22668F",
  bluePale: "#EDF5FA",
  teal: "#16877A",
  tealPale: "#EAF6F3",
  orange: "#D97706",
  orangePale: "#FCF3E8",
  red: "#B73A3A",
  redPale: "#FAECEC",
  grayText: "#526474",
  grayLine: "#C7D0D8",
  grayPale: "#F4F7F9",
  white: "#FFFFFF",
};

let objectCounter = 0;

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function name(prefix) {
  objectCounter += 1;
  return `${prefix}-${objectCounter}`;
}

function tx(content, left, top, width, height, options = {}) {
  return {
    kind: "text",
    name: name("text"),
    content,
    position: { left, top, width, height },
    style: {
      fontSize: options.fontSize ?? 18,
      typeface: options.typeface ?? "PingFang SC",
      color: options.color ?? C.navy,
      bold: options.bold ?? false,
      italic: options.italic ?? false,
      alignment: options.alignment ?? "left",
      verticalAlignment: options.verticalAlignment ?? "top",
      autoFit: options.autoFit ?? "shrinkText",
      wrap: "square",
      insets: options.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
    },
  };
}

function rect(left, top, width, height, options = {}) {
  return {
    kind: "shape",
    name: name("shape"),
    geometry: options.geometry ?? "roundRect",
    fill: options.fill ?? C.white,
    line: options.line ?? { style: "solid", width: 1.2, fill: C.grayLine },
    position: { left, top, width, height },
  };
}

function line(left, top, width, height = 1, color = C.grayLine, lineWidth = 1.3) {
  return {
    kind: "shape",
    name: name("line"),
    geometry: "line",
    fill: "none",
    line: { style: "solid", width: lineWidth, fill: color },
    position: { left, top, width, height },
  };
}

function setSources(slide, lines) {
  slide.speakerNotes.clear();
  slide.speakerNotes.text = `[Sources]\n${lines.map((entry) => `- ${entry}`).join("\n")}\n[/Sources]`;
}

function header(spec) {
  return [
    tx(spec.eyebrow, 54, 30, 280, 28, { fontSize: 19, color: C.blue, bold: true }),
    tx(spec.title, 54, 68, 1172, 60, { fontSize: 33, color: C.navy, bold: true }),
    line(54, 142, 1172),
    tx(spec.subtitle, 54, 150, 1172, 28, { fontSize: 17, color: C.grayText }),
  ];
}

function takeaway(content, fill = C.blue) {
  return [
    rect(54, 638, 1172, 52, {
      geometry: "rect",
      fill,
      line: { style: "solid", width: 1, fill },
    }),
    tx(content, 76, 649, 1128, 32, {
      fontSize: 15.5,
      color: C.white,
      bold: true,
      verticalAlignment: "middle",
    }),
  ];
}

function card(children, x, y, w, h, card, index, options = {}) {
  const fills = options.fills ?? [C.bluePale, C.orangePale, C.tealPale];
  const accents = options.accents ?? [C.blue, C.orange, C.teal];
  children.push(
    rect(x, y, w, h, {
      fill: fills[index % fills.length],
      line: { style: "solid", width: 1.3, fill: accents[index % accents.length] },
    }),
    tx(card.title, x + 20, y + 18, w - 40, 42, {
      fontSize: options.titleSize ?? 20,
      color: accents[index % accents.length],
      bold: true,
    }),
  );
  let bodyTop = y + 70;
  if (card.formulaLines) {
    const formulaSize = options.bodySize ?? 17;
    for (let i = 0; i < card.formulaLines.length; i += 1) {
      const formula = card.formulaLines[i];
      const formulaTop = y + 70 + i * 26;
      children.push(
        tx(formula.base, x + 20, formulaTop, 18, 24, {
          fontSize: formulaSize,
          color: C.navy,
          typeface: "Calibri",
        }),
        tx(formula.subscript, x + 35, formulaTop + 10, 22, 14, {
          fontSize: 10.5,
          color: C.navy,
          typeface: "Calibri",
        }),
        tx(formula.rest, x + 57, formulaTop, w - 77, 24, {
          fontSize: formulaSize,
          color: C.navy,
          typeface: "Calibri",
        }),
      );
    }
    bodyTop = y + 132;
  }
  children.push(
    tx(card.body, x + 20, bodyTop, w - 40, h - (bodyTop - y) - 18, {
      fontSize: options.bodySize ?? 17,
      color: C.navy,
      typeface: options.bodyTypeface ?? "PingFang SC",
    }),
  );
}

function compose(slide, children, layerName) {
  for (const child of children) {
    if (child.kind === "text") {
      const textbox = slide.shapes.add({
        geometry: "textbox",
        name: `${layerName}-${child.name}`,
        position: child.position,
        fill: "none",
      });
      textbox.text = child.content;
      textbox.text.style = child.style;
      textbox.text.fontSize = child.style.fontSize;
      textbox.text.typeface = child.style.typeface;
      textbox.text.color = child.style.color;
      textbox.text.bold = child.style.bold;
      textbox.text.alignment = child.style.alignment;
      textbox.text.verticalAlignment = child.style.verticalAlignment;
      continue;
    }
    slide.shapes.add({
      geometry: child.geometry,
      name: `${layerName}-${child.name}`,
      position: child.position,
      fill: child.fill,
      line: child.line,
    });
  }
}

function buildThreeCardSlide(slide, spec) {
  const children = [...header(spec)];
  const xs = [54, 452, 850];
  for (let i = 0; i < 3; i += 1) {
    card(children, xs[i], 205, 330, 330, spec.cards[i], i, {
      bodySize: spec.bodySize ?? 17,
      bodyTypeface: spec.bodyTypeface,
    });
  }
  children.push(
    rect(54, 555, 1172, 60, {
      geometry: "rect",
      fill: C.grayPale,
      line: { style: "solid", width: 1, fill: C.grayLine },
    }),
    tx(spec.strip, 76, 569, 1128, 34, {
      fontSize: spec.stripSize ?? 16.5,
      color: C.grayText,
      bold: true,
      alignment: "center",
      verticalAlignment: "middle",
    }),
    ...takeaway(spec.takeaway),
  );
  compose(slide, children, spec.layerName);
  setSources(slide, spec.sources);
}

function buildOverviewSlide(slide, spec) {
  const children = [...header(spec)];
  const xs = [54, 452, 850];
  for (let i = 0; i < 3; i += 1) {
    card(children, xs[i], 205, 330, 350, spec.cards[i], i, { bodySize: 18 });
  }
  children.push(...takeaway(spec.takeaway));
  compose(slide, children, spec.layerName);
  setSources(slide, spec.sources);
}

function buildFiveStepSlide(slide, spec) {
  const children = [...header(spec)];
  const xs = [54, 290, 526, 762, 998];
  const fills = [C.bluePale, C.orangePale, C.tealPale, C.redPale, C.bluePale];
  const accents = [C.blue, C.orange, C.teal, C.red, C.blueDark];
  for (let i = 0; i < 5; i += 1) {
    children.push(
      rect(xs[i], 215, 190, 178, {
        fill: fills[i],
        line: { style: "solid", width: 1.3, fill: accents[i] },
      }),
      tx(spec.steps[i].title, xs[i] + 20, 233, 150, 42, {
        fontSize: 18,
        color: accents[i],
        bold: true,
      }),
      tx(spec.steps[i].body, xs[i] + 20, 285, 150, 90, {
        fontSize: 14.5,
        color: C.navy,
      }),
    );
    if (i < 4) {
      children.push(
        tx("→", xs[i] + 195, 273, 36, 44, {
          fontSize: 28,
          color: C.grayText,
          bold: true,
          alignment: "center",
          verticalAlignment: "middle",
        }),
      );
    }
  }
  children.push(
    rect(54, 435, 420, 132, { fill: C.grayPale }),
    tx(spec.leftCallout.title, 74, 453, 380, 34, { fontSize: 18, color: C.blue, bold: true }),
    tx(spec.leftCallout.body, 74, 497, 380, 52, { fontSize: 15.5, color: C.navy }),
    rect(505, 450, 270, 96, { fill: C.white, line: { style: "solid", width: 1.3, fill: C.grayLine } }),
    tx(spec.centerCallout, 525, 468, 230, 60, {
      fontSize: 16,
      color: C.navy,
      bold: true,
      alignment: "center",
      verticalAlignment: "middle",
    }),
    rect(806, 435, 382, 132, { fill: C.grayPale }),
    tx(spec.rightCallout.title, 826, 453, 342, 34, { fontSize: 18, color: C.teal, bold: true }),
    tx(spec.rightCallout.body, 826, 497, 342, 52, { fontSize: 15.5, color: C.navy }),
    ...takeaway(spec.takeaway),
  );
  compose(slide, children, spec.layerName);
  setSources(slide, spec.sources);
}

function buildJiangDataSlide(slide, spec) {
  const children = [...header(spec)];
  children.push(
    rect(54, 190, 340, 160, { fill: C.bluePale, line: { style: "solid", width: 1.3, fill: C.blue } }),
    tx("观测数据", 74, 208, 300, 42, { fontSize: 20, color: C.blue, bold: true }),
    tx("ERSSTv5：SST\nERA5：925 hPa风、降水\nORAS5：海洋温度与次表层结构", 74, 260, 300, 72, { fontSize: 16.5 }),
    rect(54, 380, 340, 174, { fill: C.orangePale, line: { style: "solid", width: 1.3, fill: C.orange } }),
    tx("事件与预处理", 74, 398, 300, 42, { fontSize: 20, color: C.orange, bold: true }),
    tx("月数据：1960–2024；全部去趋势\nNiño3.4 > +0.5°C，连续≥5个重叠三月季\nFEP-dominant：FEP>1 SD，Tᵣ>ENSO，ENSO<1 SD", 74, 448, 300, 88, { fontSize: 15.3 }),
    rect(488, 270, 360, 190, { fill: C.tealPale, line: { style: "solid", width: 1.3, fill: C.teal } }),
    tx("关键时空坐标", 528, 292, 280, 36, { fontSize: 20, color: C.teal, bold: true, alignment: "center" }),
    tx("Niño3.4：5°S–5°N，170°W–120°W\nFEP：5°S–5°N，90°W–80°W\nNE wind：3°–7°N，180°E–130°W\n发展季节：MJJ", 528, 340, 280, 100, { fontSize: 16.5, alignment: "center" }),
    tx("回归分解", 402, 344, 78, 28, { fontSize: 14.5, color: C.grayText, bold: true, alignment: "center" }),
    tx("强迫验证", 856, 344, 96, 28, { fontSize: 14.5, color: C.grayText, bold: true, alignment: "center" }),
    tx("→", 410, 292, 62, 48, { fontSize: 29, color: C.grayText, bold: true, alignment: "center" }),
    tx("→", 862, 292, 76, 48, { fontSize: 29, color: C.grayText, bold: true, alignment: "center" }),
    rect(966, 212, 238, 342, { fill: C.redPale, line: { style: "solid", width: 1.3, fill: C.red } }),
    tx("ECHAM4.6 AGCM", 986, 230, 198, 42, { fontSize: 19, color: C.red, bold: true }),
    tx("T42 ≈ 2.8°\n19层，顶层10 hPa\nCTRL：1991–2020 SST\n积分20年\n4–7月叠加SSTA\n20成员集合\n响应 = sensitivity − CTRL\n\n5个FEP-dominant事件：\n1965/66 · 1969/70 · 1972/73\n1976/77 · 2023/24\n2014/15排除", 986, 282, 198, 252, { fontSize: 14.2 }),
    ...takeaway(spec.takeaway),
  );
  compose(slide, children, spec.layerName);
  setSources(slide, spec.sources);
}

const overviewSpec = {
  layerName: "formula-data-overview",
  eyebrow: "文献方法总览",
  title: "三篇论文的公式和数据，分别支撑路径、闭合与耦合门控",
  subtitle: "原式、数据设置与当前三个问题逐项对应",
  cards: [
    {
      title: "Chakravorty et al. (2021)",
      formulaLines: [
        { base: "N", subscript: "CT", rest: "= N₃ − αN₄" },
        { base: "N", subscript: "CP", rest: "= N₄ − αN₃" },
      ],
      body: "SODA + HadISST\nERA-40 + QuikSCAT + 20CRv2c\n\n对应：Q1传播路径 / Q2边界分配",
    },
    { title: "Wenrui Jiang et al. (2025)", body: "∂Θ′/∂t + A(U,Θ′) = ΣRᵢ\n\nECCO4 + OISST + ERA5\n被动示踪 + 粒子轨迹\n\n对应：Q1轨迹 / Q2闭合 / Q3反馈" },
    { title: "Leishan Jiang et al. (2026)", body: "T = E·Tₙ₃₄ + Tᵣ\nX = αTₙ₃₄ + βTᵣ + ε\n\nERSSTv5 + ERA5 + ORAS5\nECHAM4.6\n\n对应：Q3东北风门控与强迫验证" },
  ],
  takeaway: "借鉴顺序：事件分类 → 路径追踪 → 收支闭合 → 残差分解 → 模式验证。",
  sources: [
    "https://doi.org/10.1029/2020JC017075 (Equations 1-2 and Sections 2-3)",
    "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Equations 1-3 and Section 4)",
    "https://doi.org/10.1029/2026GL123227 (Equations 1-2 and Section 2)",
  ],
};

const chakSpec = {
  layerName: "chakravorty-formula-data",
  eyebrow: "文献一｜公式与数据",
  title: "事件分类与充放电诊断，建立在两组指数和边界输送上",
  subtitle: "Chakravorty et al. (2021)｜Equations 1–2 + described diagnostics",
  bodySize: 16.3,
  cards: [
    {
      title: "CT / CP事件指数",
      formulaLines: [
        { base: "N", subscript: "CT", rest: "= N₃ − αN₄" },
        { base: "N", subscript: "CP", rest: "= N₄ − αN₃" },
      ],
      body: "α = 2/5，若 N₃·N₄ > 0\n否则 α = 0\n\n事件：指数 + CHI > 0.8°C\n连续 ≥ 5个月",
    },
    { title: "空间与输送诊断", body: "N₃：5°N–5°S，150°W–90°W\nN₄：5°N–5°S，160°E–150°W\nCHI：SST′空间一阶矩\n\nWWV = ∬hₜ dA\nZT₍170E₎ = ∬u dzdy\nMTᵩ = ∬v dzdλ" },
    { title: "全部数据与统计设置", body: "SODA2.1.6：1958–2008\nSODA2.2.4：1901–2008\nHadISST：独立核验\nERA-40：再分析风场\nQuikSCAT：卫星风场\n20CRv2c：长期风应力\n\n8 CT + 8 CP；双侧t检验95%" },
  ],
  strip: "去季节循环 + 去线性趋势 + 3个月滑动平均｜边界：170°E、5°N、10°S",
  takeaway: "对应Q1–Q2：借鉴事件分类与跨边界输送；原文阈值温跃层指标不纳入当前固定层方案。",
  sources: [
    "https://doi.org/10.1029/2020JC017075 (Chakravorty et al., 2021; Equations 1-2; Sections 2.1-2.3 and 3.5)",
    "Local PDF: /Users/daiyue/Documents/Maryland/tmp/pdfs/chakravorty_2021_recharge_discharge_enso_flavors.pdf, PDF pages 3-4 and 12.",
    "SODA 2.1.6/2.2.4, HadISST, ERA-40, QuikSCAT and 20CRv2c data descriptions are from Section 2.1.",
  ],
};

const mhwEquationSpec = {
  layerName: "mhw-equations",
  eyebrow: "文献二｜闭合方程",
  title: "ECCO4把温度变化闭合到平流、扩散与外部加热",
  subtitle: "⟨·⟩表示1992–2017季节气候态；δₙₐ为在线与离线平流之差",
  bodySize: 16.2,
  stripSize: 16,
  bodyTypeface: "Calibri",
  cards: [
    { title: "Eq. 1｜网格闭合", body: "∂Θ/∂t + A(U,Θ)\n= Dₕ(K,Θ) + Dᵥ(K,Θ)\n+ Q(Θ) + δₙₐ\n\nU：速度；K：扩散率\nQ：海表/外部加热\nδₙₐ：未归属平流项" },
    { title: "Eq. 2｜季节气候态", body: "∂⟨Θ⟩/∂t + A(U,⟨Θ⟩)\n= ⟨Dₕ(K,Θ)⟩ + ⟨Dᵥ(K,Θ)⟩\n+ ⟨Q(Θ)⟩ + ⟨δₙₐ⟩\n− ⟨A(U′,Θ′)⟩\n+ A(U′,⟨Θ⟩)" },
    { title: "Eq. 3｜异常预算", body: "∂Θ′/∂t + A(U,Θ′)\n= Dₕ(K,Θ)′ + Dᵥ(K,Θ)′\n+ Q(Θ)′ + δ′ₙₐ\n+ ⟨A(U′,Θ′)⟩\n− A(U′,⟨Θ⟩)\n\n扩散｜加热｜NA｜整流｜异常平流" },
  ],
  strip: "(t₁−t₀) ∂Θ/∂t = [ΔH/(ρcₚ) − ΘΔV] / V₀",
  takeaway: "对应Q2：沿同一固定体积、同一边界和同一积分时段，逐项检查闭合与残差。",
  sources: [
    "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint; Equations 1-3, Section 4.2)",
    "Local PDF: /Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811/mhw_preprint.pdf, PDF page 7 (manuscript page 6).",
    "Angle brackets compactly denote the paper's overbar seasonal-climatology notation; the mathematical decomposition is unchanged.",
  ],
};

const mhwDataSpec = {
  layerName: "mhw-data-experiments",
  eyebrow: "文献二｜数据与实验",
  title: "水团识别、轨迹回溯与逐粒子预算构成一条闭合证据链",
  subtitle: "ECCO4 daily budget fields + OISST daily SST + ERA5 atmosphere",
  steps: [
    { title: "ECCO4 v4r4", body: "流场、温度\n闭合热/体积预算\n日更新" },
    { title: "MHW体积", body: "20°N–60°N\n180°W–90°W\nT′ > 1.5°C\n名义深度≤200 m" },
    { title: "前向示踪", body: "2014–2015\n每月初始化\n24次试验\n合成保留≥0.1 mol m⁻³" },
    { title: "伴随与粒子", body: "伴随至2014-09-01\n粒子：2016-03-01\n回溯至2013-09-01" },
    { title: "沿轨迹积分", body: "ΔΘ′ₚ = ∫ΣᵢRᵢ[xₚ(t),t]dt\n逐粒子预算后求和" },
  ],
  leftCallout: { title: "独立观测与大气强迫", body: "OISST：日SST，0.25°｜ERA5：潜热、感热、长短波与整层水汽/热输送" },
  centerCallout: "季节气候态\n1992–2017",
  rightCallout: { title: "环流代理量", body: "Ψ₍GOA₎ = ∫v dz｜Ψ₍CC₎ = ∫w dx₍onshore₎｜检验海洋输送与海气反馈" },
  takeaway: "对应Q1–Q3：示踪/粒子给路径，沿轨迹预算给去向，ERA5与环流代理量检验反馈。",
  sources: [
    "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint; Sections 4.1 and 4.3-4.5)",
    "Local PDF: /Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811/mhw_preprint.pdf, PDF pages 7-9.",
    "The compact trajectory integral and proxy streamfunction notation transcribe the method definitions in Sections 4.4-4.5; they are not separately numbered equations.",
  ],
};

const jiangEquationSpec = {
  layerName: "jiang-equations",
  eyebrow: "文献三｜残差分解",
  title: "先剥离典型ENSO成分，再识别远东太平洋的独立贡献",
  subtitle: "Leishan Jiang et al. (2026)｜Equations 1–2",
  bodySize: 17.2,
  bodyTypeface: "Calibri",
  cards: [
    { title: "Eq. 1｜FEP分解", body: "T(t) = E·Tₙ₃₄(t) + Tᵣ(t)\n\nT：FEP SSTA\nE·Tₙ₃₄：典型ENSO成分\nTᵣ：FEP残差成分" },
    { title: "Eq. 2｜多元回归", body: "X(t,x,y) = α(x,y)Tₙ₃₄(t)\n+ β(x,y)Tᵣ(t) + ε(t,x,y)\n\nX：SST / 风 / 降水 / 次表层\nα：ENSO；β：FEP" },
    { title: "重建与时序检验", body: "Xₙ₃₄ = αTₙ₃₄\nXᵣ = βTᵣ\n\nlead–lag correlation\n15年滑动窗口\nAGCM检验Tᵣ强迫响应" },
  ],
  strip: "Niño3.4：5°S–5°N，170°W–120°W｜FEP：5°S–5°N，90°W–80°W",
  takeaway: "对应Q3：Tᵣ隔离东部先行增暖；β场给出东北风与弱西风的门控坐标。",
  sources: [
    "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026; Equations 1-2, Section 2.2)",
    "Local PDF: /Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf, PDF pages 2 and 5.",
  ],
};

const jiangDataSpec = {
  layerName: "jiang-data-agcm",
  eyebrow: "文献三｜观测与模式",
  title: "观测分解、事件筛选与AGCM试验共同支撑因果判断",
  subtitle: "Monthly 1960–2024｜MJJ｜NE wind: 3°–7°N, 180°E–130°W",
  takeaway: "对应Q3：观测提供统计时序，AGCM检验FEP异常能否主动激发东北风并削弱西风。",
  sources: [
    "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026; Sections 2.1 and 2.3)",
    "Local PDF: /Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf, PDF pages 2-3.",
    "Analyzed El Nino events: 1963/64, 1965/66, 1968/69, 1969/70, 1972/73, 1976/77, 1977/78, 1979/80, 1982/83, 1986/87, 1987/88, 1991/92, 1994/95, 1997/98, 2002/03, 2004/05, 2006/07, 2009/10, 2015/16, 2018/19, 2019/20, 2023/24; 2014/15 excluded.",
  ],
};

const presentation = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
if (presentation.slides.items.length !== 19) {
  throw new Error(`Expected 19 source slides, got ${presentation.slides.items.length}`);
}

let cursor = presentation.slides.items[4];
const builders = [
  [buildOverviewSlide, overviewSpec],
  [buildThreeCardSlide, chakSpec],
  [buildThreeCardSlide, mhwEquationSpec],
  [buildFiveStepSlide, mhwDataSpec],
  [buildThreeCardSlide, jiangEquationSpec],
  [buildJiangDataSlide, jiangDataSpec],
];

for (const [builder, spec] of builders) {
  const inserted = presentation.slides.insert({ after: cursor });
  const slide = inserted.slide;
  if (!slide?.shapes) {
    throw new TypeError(`Inserted slide is not an editable slide facade: ${JSON.stringify({ type: typeof slide, keys: slide ? Object.keys(slide) : [] })}`);
  }
  builder(slide, spec);
  cursor = slide;
}

if (presentation.slides.items.length !== 25) {
  throw new Error(`Expected 25 final slides, got ${presentation.slides.items.length}`);
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
  maxChars: 1500000,
});
await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUT);
console.log(JSON.stringify({ output: OUT, slides: presentation.slides.items.length, revision: inspect.revision }, null, 2));
