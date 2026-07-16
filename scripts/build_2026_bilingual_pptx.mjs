import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const OUT_DIR = path.join(ROOT, "outputs/research_2026/presentations");
const PREVIEW_ROOT = path.join("/private/tmp/codex-presentations/enso-2026-bilingual/tmp", "preview");
const LAYOUT_ROOT = path.join("/private/tmp/codex-presentations/enso-2026-bilingual/tmp", "layout");

const FIG = {
  fep: path.join(ROOT, "outputs/research_2026/figures/fig1_2026_sst_fep_residual.png"),
  sstPrecip: path.join(ROOT, "outputs/research_2026/spatial_meteorology/fig4_2026_sst_precip_spatial.png"),
  olr: path.join(ROOT, "outputs/research_2026/spatial_meteorology/fig6_2026_olr_convection_spatial.png"),
  era5Surface: path.join(ROOT, "outputs/research_2026/era5_spatial/fig8_2026_era5_surface_wind_pressure.png"),
  era5Precip: path.join(ROOT, "outputs/research_2026/era5_spatial/fig9_2026_era5_precip_u850_omega.png"),
  era5Hov: path.join(ROOT, "outputs/research_2026/era5_spatial/fig10_2026_era5_equatorial_hovmoller.png"),
};

const COLORS = {
  bg: "#F7F4EC",
  ink: "#1C1B18",
  muted: "#5B5A55",
  line: "#D8D1C2",
  teal: "#2C7773",
  tealDark: "#1C5E5A",
  rust: "#C85B45",
  rustDark: "#A84434",
  blue: "#2B5F8A",
  paleTeal: "#E7F1EF",
  paleRust: "#F5E4DE",
  paleBlue: "#E8EEF4",
  white: "#FFFDF8",
  black: "#161513",
};

const W = 1280;
const H = 720;
const PAGE = { left: 56, top: 50, width: 1168, height: 610 };

function pt(n) {
  return Math.round(n * 96 / 72);
}

function titleSize(text) {
  if (text.length > 58) return pt(29);
  if (text.length > 45) return pt(31);
  return pt(33);
}

async function readImageBytes(imagePath) {
  const bytes = await fs.readFile(imagePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

async function ensureInputs() {
  for (const p of Object.values(FIG)) await fs.access(p);
  await fs.mkdir(OUT_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_ROOT, { recursive: true });
  await fs.mkdir(LAYOUT_ROOT, { recursive: true });
}

function addText(slide, text, opts) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: opts.name,
    position: {
      left: opts.x,
      top: opts.y,
      width: opts.w,
      height: opts.h,
    },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: opts.size ?? pt(17),
    bold: opts.bold ?? false,
    color: opts.color ?? COLORS.ink,
    alignment: opts.align ?? "left",
    typeface: opts.font ?? "Aptos",
  };
  return shape;
}

function addRule(slide, y, color = COLORS.line, width = 1) {
  slide.shapes.add({
    geometry: "rect",
    name: `rule-${y}`,
    position: { left: PAGE.left, top: y, width: PAGE.width, height: width },
    fill: color,
    line: { style: "solid", fill: color, width: 0 },
  });
}

function addFooter(slide, lang, slideNo, source = "") {
  const text = lang === "cn"
    ? `第 ${slideNo} 页 | ${source}`
    : `Slide ${slideNo} | ${source}`;
  addText(slide, text, {
    x: PAGE.left,
    y: 684,
    w: 930,
    h: 22,
    size: pt(9),
    color: COLORS.muted,
    font: lang === "cn" ? "PingFang SC" : "Aptos",
    name: `footer-${slideNo}`,
  });
  addText(slide, "ENSO/FEP 2026 diagnostic", {
    x: 980,
    y: 684,
    w: 240,
    h: 22,
    size: pt(9),
    color: COLORS.muted,
    align: "right",
    font: lang === "cn" ? "PingFang SC" : "Aptos",
    name: `footer-tag-${slideNo}`,
  });
}

function addHeader(slide, title, lang, slideNo, source = "") {
  slide.background.fill = COLORS.bg;
  addText(slide, title, {
    x: PAGE.left,
    y: 40,
    w: 1110,
    h: 70,
    size: titleSize(title),
    bold: true,
    color: COLORS.ink,
    font: lang === "cn" ? "PingFang SC" : "Aptos",
    name: `title-${slideNo}`,
  });
  addRule(slide, 112);
  addFooter(slide, lang, slideNo, source);
}

function addBadge(slide, label, x, y, color, lang, w = 168) {
  slide.shapes.add({
    geometry: "roundRect",
    name: `badge-${label}`,
    position: { left: x, top: y, width: w, height: 34 },
    fill: color,
    line: { style: "solid", fill: color, width: 0 },
    borderRadius: "rounded-lg",
  });
  addText(slide, label, {
    x: x + 10,
    y: y + 7,
    w: w - 20,
    h: 22,
    size: pt(11),
    bold: true,
    color: COLORS.white,
    align: "center",
    font: lang === "cn" ? "PingFang SC" : "Aptos",
  });
}

function addCallout(slide, title, body, x, y, w, h, fill, border, lang, name) {
  const compact = h < 120;
  const titleTop = y + (compact ? 10 : 16);
  const titleHeight = compact ? 24 : 30;
  const bodyTop = y + (compact ? 38 : 54);
  const bodyHeight = h - (compact ? 48 : 66);
  slide.shapes.add({
    geometry: "roundRect",
    name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: border, width: 1 },
    borderRadius: "rounded-lg",
  });
  addText(slide, title, {
    x: x + 18,
    y: titleTop,
    w: w - 36,
    h: titleHeight,
    size: compact ? pt(12) : pt(14),
    bold: true,
    color: border,
    font: lang === "cn" ? "PingFang SC" : "Aptos",
    name: `${name}-title`,
  });
  addText(slide, body, {
    x: x + 18,
    y: bodyTop,
    w: w - 36,
    h: bodyHeight,
    size: compact ? pt(12) : pt(14),
    color: COLORS.ink,
    font: lang === "cn" ? "PingFang SC" : "Aptos",
    name: `${name}-body`,
  });
}

function addBullets(slide, items, x, y, w, h, lang, size = pt(17), name = "bullets") {
  const text = items.map((d) => `• ${d}`).join("\n");
  return addText(slide, text, {
    x,
    y,
    w,
    h,
    size,
    color: COLORS.ink,
    font: lang === "cn" ? "PingFang SC" : "Aptos",
    name,
  });
}

async function addFigure(slide, imagePath, x, y, w, h, alt) {
  const blob = await readImageBytes(imagePath);
  slide.images.add({
    blob,
    contentType: "image/png",
    alt,
    fit: "contain",
    position: { left: x, top: y, width: w, height: h },
    geometry: "rect",
  });
}

function addNativeTable(slide, values, x, y, w, h, lang, name, tracks = null, fontSize = pt(13)) {
  const rows = values.length;
  const columns = values[0].length;
  const table = slide.tables.add({
    rows,
    columns,
    left: x,
    top: y,
    width: w,
    height: h,
    values,
    ...(tracks ? { columnTracks: tracks } : {}),
  });
  table.borders.assign({ style: "solid", fill: COLORS.line, width: 1 });
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: columns }).assign({
    fill: COLORS.black,
    textStyle: { color: COLORS.white, bold: true, fontSize, typeface: lang === "cn" ? "PingFang SC" : "Aptos" },
    margins: { left: 8, right: 8, top: 6, bottom: 6 },
  });
  if (rows > 1) {
    table.cells.block({ row: 1, column: 0, rowCount: rows - 1, columnCount: columns }).assign({
      fill: COLORS.white,
      textStyle: { color: COLORS.ink, fontSize, typeface: lang === "cn" ? "PingFang SC" : "Aptos" },
      margins: { left: 8, right: 8, top: 6, bottom: 6 },
    });
  }
  for (let r = 1; r < rows; r += 2) {
    table.cells.block({ row: r, column: 0, rowCount: 1, columnCount: columns }).assign({
      fill: "#EFEADF",
    });
  }
  table.name = name;
  return table;
}

function addTwoColumnTextSlide(pres, cfg) {
  const slide = pres.slides.add();
  addHeader(slide, cfg.title, cfg.lang, cfg.no, cfg.source);
  addCallout(slide, cfg.leftTitle, cfg.leftBody, 66, 150, 530, 410, cfg.leftFill, cfg.leftBorder, cfg.lang, "left-callout");
  addCallout(slide, cfg.rightTitle, cfg.rightBody, 650, 150, 530, 410, cfg.rightFill, cfg.rightBorder, cfg.lang, "right-callout");
  return slide;
}

async function addFigureSlide(pres, cfg) {
  const slide = pres.slides.add();
  addHeader(slide, cfg.title, cfg.lang, cfg.no, cfg.source);
  await addFigure(slide, cfg.image, cfg.figX ?? 62, cfg.figY ?? 132, cfg.figW ?? 720, cfg.figH ?? 500, cfg.alt);
  addCallout(slide, cfg.noteTitle, cfg.noteBody, cfg.noteX ?? 824, cfg.noteY ?? 150, cfg.noteW ?? 356, cfg.noteH ?? 380, cfg.fill ?? COLORS.paleTeal, cfg.border ?? COLORS.teal, cfg.lang, `note-${cfg.no}`);
  return slide;
}

function addSourceSlide(pres, lang, no) {
  const slide = pres.slides.add();
  addHeader(slide, lang === "cn" ? "数据链接与本地文件位置" : "Data Links and Local Files", lang, no, lang === "cn" ? "数据来源页" : "source slide");
  const rows = lang === "cn"
    ? [
        ["类别", "数据/文件", "链接或路径"],
        ["ERA5", "月平均 single levels", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means"],
        ["ERA5", "月平均 pressure levels", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels-monthly-means"],
        ["SST", "NOAA OISST v2.1", "https://www.ncei.noaa.gov/products/optimum-interpolation-sst"],
        ["降水", "GPCP monthly precipitation", "https://psl.noaa.gov/data/gridded/data.gpcp.html"],
        ["对流", "CPC Blended OLR", "https://psl.noaa.gov/data/gridded/data.cpc_blended_olr-1deg.html"],
        ["本地报告", "ERA5 图说明", "reports/2026_ERA5再分析气象图说明.md"],
        ["本地表格", "ERA5 区域统计", "data/derived/research_2026/current_2026_era5_region_summary.csv"],
      ]
    : [
        ["Category", "Dataset / file", "Link or local path"],
        ["ERA5", "Monthly single levels", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means"],
        ["ERA5", "Monthly pressure levels", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels-monthly-means"],
        ["SST", "NOAA OISST v2.1", "https://www.ncei.noaa.gov/products/optimum-interpolation-sst"],
        ["Rainfall", "GPCP monthly precipitation", "https://psl.noaa.gov/data/gridded/data.gpcp.html"],
        ["Convection", "CPC Blended OLR", "https://psl.noaa.gov/data/gridded/data.cpc_blended_olr-1deg.html"],
        ["Local report", "ERA5 figure notes", "reports/2026_ERA5再分析气象图说明.md"],
        ["Local table", "ERA5 regional summary", "data/derived/research_2026/current_2026_era5_region_summary.csv"],
      ];
  addNativeTable(slide, rows, 62, 138, 1158, 480, lang, "source-table", [{ mode: "fixed", value: 120 }, { mode: "fixed", value: 230 }, { mode: "fr", value: 1 }], pt(11));
  addText(slide, lang === "cn"
    ? "注：所有异常均相对于 1982-2022 同月气候态；2026 的完整 AMJ 仍需等待 6 月月平均数据。"
    : "Note: all anomalies are relative to the 1982-2022 same-month climatology; full 2026 AMJ still requires the June monthly mean.",
    { x: 66, y: 632, w: 1120, h: 44, size: pt(14), color: COLORS.muted, font: lang === "cn" ? "PingFang SC" : "Aptos" });
  return slide;
}

async function createDeck(lang) {
  const cn = lang === "cn";
  const pres = Presentation.create({ slideSize: { width: W, height: H } });
  const font = cn ? "PingFang SC" : "Aptos";

  // 1. Title
  {
    const slide = pres.slides.add();
    slide.background.fill = COLORS.bg;
    addText(slide, cn ? "2026 年当前 ENSO/FEP 事件的实时气象诊断" : "Real-Time Meteorological Diagnosis of the 2026 ENSO/FEP Event", {
      x: 72,
      y: 116,
      w: 900,
      h: 132,
      size: pt(36),
      bold: true,
      color: COLORS.ink,
      font,
      name: "deck-title",
    });
    addText(slide, cn
      ? "从 2023/24 海气脱耦问题出发：海温先行，风压滞后恢复，降水/对流仍不稳定"
      : "From the 2023/24 decoupling problem: SST leads, wind and pressure recover with lag, rainfall and convection remain uneven",
      {
        x: 76,
        y: 276,
        w: 850,
        h: 92,
        size: pt(19),
        color: COLORS.muted,
        font,
        name: "deck-subtitle",
      });
    addBadge(slide, cn ? "当前数据版" : "Current-data update", 76, 402, COLORS.teal, lang, cn ? 150 : 190);
    addBadge(slide, "ERA5 + OISST + GPCP + OLR", 250, 402, COLORS.rust, lang, 290);
    slide.shapes.add({
      geometry: "rect",
      position: { left: 992, top: 0, width: 288, height: 720 },
      fill: COLORS.teal,
      line: { style: "solid", fill: COLORS.teal, width: 0 },
    });
    addText(slide, cn ? "汇报目标" : "Purpose", {
      x: 1028,
      y: 126,
      w: 190,
      h: 40,
      size: pt(20),
      bold: true,
      color: COLORS.white,
      font,
      name: "purpose-title",
    });
    addText(slide, cn
      ? "把 2023/24 的“海洋强、大气弱”问题迁移到 2026 当前事件，用同一条数据链检查大气响应是否同步。"
      : "Apply the 2023/24 ocean-strong / atmosphere-weak logic to the ongoing 2026 event, and test whether the atmospheric branch is catching up.",
      {
        x: 1028,
        y: 180,
        w: 190,
        h: 248,
        size: pt(16),
        color: COLORS.white,
        font,
        name: "purpose-body",
      });
    addText(slide, cn ? "Yue Dai | 2026-06-22" : "Yue Dai | 22 June 2026", {
      x: 76,
      y: 650,
      w: 480,
      h: 24,
      size: pt(13),
      color: COLORS.muted,
      font,
      name: "date",
    });
  }

  // 2. Logic
  addTwoColumnTextSlide(pres, {
    lang,
    no: 2,
    title: cn ? "从 2023/24 问题到 2026 实时检验" : "From the 2023/24 Question to a 2026 Real-Time Test",
    source: cn ? "研究逻辑" : "research logic",
    leftTitle: cn ? "原始问题" : "Starting point",
    leftBody: cn
      ? "Peng et al. (2025) 强调 2023/24 强厄尔尼诺主要由海洋动力过程生成，但它同时暴露出一个更适合继续做的问题：为什么强海温异常没有引发同等强度的风场、气压、降水和遥相关响应？"
      : "Peng et al. (2025) argues that the 2023/24 strong El Nino was generated primarily by ocean dynamics. The follow-up question for this project is why strong SST anomalies did not produce equally strong wind, pressure, rainfall, and teleconnection responses.",
    rightTitle: cn ? "2026 的作用" : "Why 2026 matters",
    rightBody: cn
      ? "2026 年初到春季提供了一个实时对照案例：东太平洋/FEP 海温率先增暖后，低层风、海平面气压、降水和对流是否同步跟上？目前 ERA5 结果显示：风压在春季开始恢复，但降水/对流仍最滞后。"
      : "The ongoing 2026 case provides a real-time comparison: after far-eastern/eastern Pacific SST warming begins, do low-level winds, sea-level pressure, rainfall, and convection respond at the same time? ERA5 indicates that wind and pressure begin to recover in spring, while rainfall and convection remain the slowest branch.",
    leftFill: COLORS.paleRust,
    leftBorder: COLORS.rust,
    rightFill: COLORS.paleTeal,
    rightBorder: COLORS.teal,
  });

  // 3. Data / abbreviations
  {
    const slide = pres.slides.add();
    addHeader(slide, cn ? "数据链和缩写说明" : "Data Chain and Abbreviations", lang, 3, cn ? "数据说明" : "data note");
    const rows = cn
      ? [
          ["缩写", "含义", "本报告中的用途"],
          ["ENSO", "厄尔尼诺-南方涛动", "热带太平洋海气耦合背景"],
          ["FEP", "远东太平洋", "靠近南美沿岸的早期暖异常区"],
          ["SST", "海表温度", "OISST 判断海温异常"],
          ["u10 / u850", "10 米 / 850 hPa 纬向风", "正值为偏西风，负值为偏东风"],
          ["MSLP", "平均海平面气压", "构造 SOI-like Tahiti-Darwin 压差"],
          ["OLR", "向外长波辐射", "负值代表深对流增强，正值代表对流偏弱"],
          ["omega850", "850 hPa 垂直速度", "正值偏下沉，负值偏上升"],
        ]
      : [
          ["Abbrev.", "Meaning", "Use in this deck"],
          ["ENSO", "El Nino-Southern Oscillation", "Air-sea coupling background in the tropical Pacific"],
          ["FEP", "Far Eastern Pacific", "Coastal eastern-Pacific early-warming region"],
          ["SST", "Sea surface temperature", "OISST-based ocean-warming anomaly"],
          ["u10 / u850", "Zonal wind at 10 m / 850 hPa", "Positive: westerly anomaly; negative: easterly anomaly"],
          ["MSLP", "Mean sea-level pressure", "Used for SOI-like Tahiti-Darwin pressure contrast"],
          ["OLR", "Outgoing longwave radiation", "Negative: stronger deep convection; positive: suppressed convection"],
          ["omega850", "Vertical pressure velocity at 850 hPa", "Positive: downward motion; negative: upward motion"],
        ];
    addNativeTable(slide, rows, 70, 138, 1140, 420, lang, "glossary-table", [{ mode: "fixed", value: 132 }, { mode: "fixed", value: 300 }, { mode: "fr", value: 1 }], pt(13));
    addCallout(slide,
      cn ? "异常定义" : "Anomaly definition",
      cn
        ? "2026 异常 = 2026 某月或某时段平均值 − 1982-2022 同月气候态。MAM 表示 3-5 月，Apr-May 表示 4-5 月。完整 AMJ 仍需等待 2026 年 6 月月平均数据。"
        : "2026 anomaly = 2026 monthly or period mean minus the 1982-2022 same-month climatology. MAM means March-May; Apr-May means April-May. Full AMJ requires the June 2026 monthly mean.",
      72, 585, 1128, 76, COLORS.paleBlue, COLORS.blue, lang, "anom-callout");
  }

  // 4. Figure: SST/FEP
  await addFigureSlide(pres, {
    lang,
    no: 4,
    title: cn ? "海温端：FEP 和东太平洋在春季率先增暖" : "Ocean Branch: FEP and Eastern Pacific Warm First",
    source: cn ? "图：OISST 指数和 FEP residual" : "Figure: OISST indices and FEP residual",
    image: FIG.fep,
    alt: "FEP SST residual time series",
    noteTitle: cn ? "这幅图表示什么" : "What the figure shows",
    noteBody: cn
      ? "数据名称：NOAA OISST v2.1 月平均海表温度异常。\n\n读图重点：2026 年 2 月以后，FEP 与 Niño1+2 附近暖异常快速增强。FEP residual 为正，说明沿岸东太平洋暖异常相对热带太平洋整体更突出。\n\n与研究主线的关系：先确认“海温端确实先动了”，再检查大气是否同步响应。"
      : "Dataset: NOAA OISST v2.1 monthly SST anomaly.\n\nKey reading: after February 2026, FEP and Niño1+2 warming intensifies rapidly. A positive FEP residual means coastal eastern-Pacific warming is stronger than the broader tropical-Pacific background.\n\nRole in the story: first establish that the ocean branch moved, then test whether the atmosphere responded synchronously.",
    fill: COLORS.paleRust,
    border: COLORS.rust,
  });

  // 5. Figure: SST + GPCP
  await addFigureSlide(pres, {
    lang,
    no: 5,
    title: cn ? "海温与降水：暖异常清楚，但赤道降水没有整齐跟上" : "SST and Rainfall: Warming Is Clear, Equatorial Rainfall Is Not",
    source: cn ? "图：OISST SST + GPCP 降水" : "Figure: OISST SST + GPCP rainfall",
    image: FIG.sstPrecip,
    alt: "OISST and GPCP spatial anomaly maps",
    noteTitle: cn ? "这幅图表示什么" : "What the figure shows",
    noteBody: cn
      ? "数据名称：OISST 海表温度异常和 GPCP 月降水异常。\n\n读图重点：MAM 与 Apr-May 的东太平洋/FEP 偏暖明显，但 GPCP 降水增强中心偏向西太平洋和赤道以北；赤道中东太平洋没有形成连续强正降水带。\n\n创新点：把 2023/24 的“海温-降水不同步”问题迁移到 2026 实时个例。"
      : "Datasets: OISST SST anomaly and GPCP monthly precipitation anomaly.\n\nKey reading: MAM and Apr-May show clear eastern-Pacific/FEP warming, but the rainfall enhancement is displaced toward the western Pacific and north of the equator. A continuous positive equatorial central-eastern Pacific rainfall band is absent.\n\nNew contribution: transfer the 2023/24 SST-rainfall asynchrony question to a real-time 2026 case.",
    fill: COLORS.paleTeal,
    border: COLORS.teal,
  });

  // 6. Figure: OLR
  await addFigureSlide(pres, {
    lang,
    no: 6,
    title: cn ? "对流独立检验：OLR 支持降水中心空间错位" : "Independent Convection Check: OLR Supports Spatial Displacement",
    source: cn ? "图：CPC Blended OLR anomaly" : "Figure: CPC Blended OLR anomaly",
    image: FIG.olr,
    alt: "CPC OLR anomaly maps",
    noteTitle: cn ? "这幅图表示什么" : "What the figure shows",
    noteBody: cn
      ? "数据名称：CPC Blended OLR 日异常时段平均。\n\n读图重点：OLR 负异常代表深对流增强，正异常代表对流偏弱。2026 春季对流增强更偏西太平洋/中太平洋北侧，赤道中东太平洋没有典型强厄尔尼诺式的大范围增强对流。\n\n作用：避免只依赖 GPCP，给“降水/对流仍滞后或错位”增加独立约束。"
      : "Dataset: CPC Blended OLR daily anomaly averaged over selected periods.\n\nKey reading: negative OLR means stronger deep convection; positive OLR means suppressed convection. In spring 2026, enhanced convection is displaced toward the western/northern central Pacific rather than forming a broad equatorial central-eastern Pacific signal.\n\nRole: this gives an independent check on the rainfall conclusion.",
    fill: COLORS.paleBlue,
    border: COLORS.blue,
  });

  // 7. Figure: ERA5 surface
  await addFigureSlide(pres, {
    lang,
    no: 7,
    title: cn ? "ERA5 风压新证据：春季风场和气压开始恢复" : "ERA5 Wind-Pressure Evidence: Spring Recovery Begins",
    source: cn ? "图：ERA5 10 m 风和 MSLP" : "Figure: ERA5 10 m wind and MSLP",
    image: FIG.era5Surface,
    alt: "ERA5 surface wind and MSLP maps",
    noteTitle: cn ? "这幅图表示什么" : "What the figure shows",
    noteBody: cn
      ? "数据名称：ERA5 10 m 风异常和平均海平面气压异常。\n\n读图重点：MAM 和 Apr-May 赤道中西太平洋出现偏西风异常，热带中东太平洋气压偏低，Tahiti-Darwin 压差开始转为更厄尔尼诺型。\n\n相较旧判断：NCEP 只到 2 月时只能说明年初不同步；ERA5 1-5 月显示春季风压并非持续无响应，而是滞后恢复。"
      : "Datasets: ERA5 10 m wind anomaly and mean sea-level pressure anomaly.\n\nKey reading: in MAM and Apr-May, westerly anomalies emerge over the central-western equatorial Pacific, and pressure lowers over the central-eastern tropical Pacific. The Tahiti-Darwin contrast becomes more El Nino-like.\n\nUpdate from the older view: NCEP only covered Jan-Feb, so it showed early asynchrony. ERA5 Jan-May indicates lagged recovery rather than persistent non-response.",
    fill: COLORS.paleRust,
    border: COLORS.rust,
  });

  // 8. Figure: ERA5 precip/u850/omega
  await addFigureSlide(pres, {
    lang,
    no: 8,
    title: cn ? "ERA5 低层风、降水与垂直运动：响应恢复并不同步" : "ERA5 u850, Rainfall, and Vertical Motion: Recovery Is Not Synchronous",
    source: cn ? "图：ERA5 降水、u850、omega850" : "Figure: ERA5 rainfall, u850, omega850",
    image: FIG.era5Precip,
    alt: "ERA5 precipitation u850 omega maps",
    noteTitle: cn ? "这幅图表示什么" : "What the figure shows",
    noteBody: cn
      ? "数据名称：ERA5 总降水、850 hPa 纬向风、850 hPa 垂直速度。\n\n读图重点：u850 在 MAM/Apr-May 已转为偏西风，说明低层风分支开始跟上；但降水增强中心仍偏西/偏北，中太平洋降水和 omega850 没有表现为稳定强上升响应。\n\n关键结论：风压分支恢复早于降水/对流分支。"
      : "Datasets: ERA5 total precipitation, 850 hPa zonal wind, and 850 hPa pressure velocity.\n\nKey reading: u850 turns westerly in MAM/Apr-May, indicating that the low-level wind branch is catching up. However, rainfall remains displaced westward/northward, and central-Pacific omega850 does not show a stable strong upward-motion response.\n\nMain conclusion: the wind-pressure branch recovers before the rainfall-convection branch.",
    fill: COLORS.paleTeal,
    border: COLORS.teal,
  });

  // 9. Hovmoller
  await addFigureSlide(pres, {
    lang,
    no: 9,
    title: cn ? "经度-时间图：年初偏东风，春季风压恢复，降水滞后" : "Longitude-Time View: Early Easterlies, Spring Wind Recovery, Rainfall Lag",
    source: cn ? "图：ERA5 赤道 Hovmoller" : "Figure: ERA5 equatorial Hovmoller",
    image: FIG.era5Hov,
    alt: "ERA5 equatorial Hovmoller",
    noteTitle: cn ? "这幅图表示什么" : "What the figure shows",
    noteBody: cn
      ? "数据名称：ERA5 赤道平均 u10、u850、降水和 omega850 异常。\n\n读图重点：1-2 月中太平洋风场为明显偏东风；3-5 月中西太平洋风场逐渐转偏西。降水在 1-4 月仍大范围偏弱，5 月才出现更多局地恢复。\n\n这张图最直接支持“阶段性恢复”而不是“全程脱耦”。"
      : "Datasets: ERA5 equatorial-mean u10, u850, precipitation, and omega850 anomalies.\n\nKey reading: January-February shows clear central-Pacific easterly anomalies. From March to May, central-western Pacific winds gradually turn westerly. Rainfall remains broadly weak from January to April and becomes more locally positive only in May.\n\nThis is the most direct evidence for staged recovery rather than all-season decoupling.",
    fill: COLORS.paleBlue,
    border: COLORS.blue,
  });

  // 10. Key numbers
  {
    const slide = pres.slides.add();
    addHeader(slide, cn ? "关键数值：2026 当前事件呈现阶段性耦合恢复" : "Key Numbers: 2026 Shows Staged Coupling Recovery", lang, 10, cn ? "表：ERA5 区域统计" : "Table: ERA5 regional summary");
    const rows = cn
      ? [
          ["时段", "指标", "异常值", "含义"],
          ["Jan", "中太平洋 u10", "-1.15 m/s", "年初仍是偏东风，不是典型厄尔尼诺偏西风响应"],
          ["Feb", "中太平洋 u850", "-2.95 m/s", "850 hPa 偏东风很强，低层大气尚未跟上海温"],
          ["Feb", "SOI-like MSLP", "+2.63 hPa", "气压梯度偏 La Niña-like"],
          ["MAM", "CWP u850", "+0.98 m/s", "春季中西太平洋低层风开始偏西"],
          ["MAM", "中太平洋降水", "-0.87 mm/day", "降水仍弱于气候态"],
          ["Apr-May", "CWP u850", "+1.47 m/s", "风场恢复更明显"],
          ["Apr-May", "SOI-like MSLP", "-1.16 hPa", "气压分支也转向厄尔尼诺型"],
          ["Apr-May", "中太平洋降水", "-0.26 mm/day", "降水接近恢复，但仍不是强正异常"],
        ]
      : [
          ["Period", "Metric", "Anomaly", "Interpretation"],
          ["Jan", "Central-Pacific u10", "-1.15 m/s", "Early easterlies; not the canonical El Nino westerly response"],
          ["Feb", "Central-Pacific u850", "-2.95 m/s", "Strong lower-tropospheric easterly anomaly"],
          ["Feb", "SOI-like MSLP", "+2.63 hPa", "Pressure gradient remains La Nina-like"],
          ["MAM", "CWP u850", "+0.98 m/s", "Spring low-level wind begins to recover westerly"],
          ["MAM", "Central-Pacific rainfall", "-0.87 mm/day", "Rainfall remains below climatology"],
          ["Apr-May", "CWP u850", "+1.47 m/s", "Wind recovery becomes clearer"],
          ["Apr-May", "SOI-like MSLP", "-1.16 hPa", "Pressure branch shifts toward El Nino-like"],
          ["Apr-May", "Central-Pacific rainfall", "-0.26 mm/day", "Rainfall approaches recovery but is not strongly positive"],
        ];
    addNativeTable(slide, rows, 62, 138, 1156, 438, lang, "key-numbers-table", [{ mode: "fixed", value: 108 }, { mode: "fixed", value: 250 }, { mode: "fixed", value: 150 }, { mode: "fr", value: 1 }], pt(12));
    addCallout(slide,
      cn ? "一句话判断" : "One-sentence takeaway",
      cn
        ? "判断：海温/FEP 先行；1-2 月风压和降水不同步；3-5 月风压恢复；降水/对流仍最滞后。"
        : "Takeaway: SST/FEP leads; Jan-Feb wind-pressure and rainfall are asynchronous; Mar-May wind-pressure recovers; rainfall-convection lags.",
      74, 600, 1120, 78, COLORS.paleTeal, COLORS.teal, lang, "takeaway-table");
  }

  // 11. What changed / next
  addTwoColumnTextSlide(pres, {
    lang,
    no: 11,
    title: cn ? "相较前一版，ERA5 改变了我们能说的话" : "What ERA5 Changes Compared with the Earlier Version",
    source: cn ? "阶段判断" : "stage assessment",
    leftTitle: cn ? "前一版能说什么" : "Earlier version",
    leftBody: cn
      ? "基于 OISST、GPCP、OLR 和 NCEP 1-2 月资料，前一版主要能说明：2026 年初海温已经转暖，但低层风、气压和降水还没有同步响应。由于 NCEP 风压资料只到 2 月，不能判断春季以后是否继续弱响应。"
      : "Using OISST, GPCP, OLR, and NCEP data only through January-February, the earlier version could say that SST had begun warming while low-level wind, pressure, and rainfall had not responded synchronously. It could not determine whether the weak response persisted into spring.",
    rightTitle: cn ? "现在能说什么" : "Current interpretation",
    rightBody: cn
      ? "ERA5 1-5 月补齐后，结论更精细：年初不同步是真实存在的；但 3-5 月风场和气压开始恢复到更厄尔尼诺型。仍然最值得追踪的是降水、OLR 和垂直运动，它们表现出滞后、偏北或空间破碎。"
      : "With ERA5 through May, the conclusion becomes more nuanced: early asynchrony is real, but wind and pressure begin to recover toward an El Nino-like state in March-May. The most important branch to track next is rainfall, OLR, and vertical motion, which still show lagged, northward, or fragmented responses.",
    leftFill: COLORS.paleRust,
    leftBorder: COLORS.rust,
    rightFill: COLORS.paleTeal,
    rightBorder: COLORS.teal,
  });

  // 12. Next steps
  {
    const slide = pres.slides.add();
    addHeader(slide, cn ? "下一步：把 2026 做成与 2023/24 同口径的对照" : "Next Steps: Turn 2026 into a Same-Metric Comparison with 2023/24", lang, 12, cn ? "下一步计划" : "next steps");
    const items = cn
      ? [
          "等待 2026 年 6 月 ERA5 月平均，正式生成 AMJ 2026，而不是只用 MAM 或 Apr-May 近似。",
          "把 ERA5 风压结果接入前面 2023/24 的 response-ratio / observed-vs-expected 框架，用同一公式比较 2023 与 2026。",
          "用同一套 ERA5 变量回算 2023/24 AMJ/JJA，避免不同资料集造成的结论差异。",
          "加入 200 hPa divergence 或 velocity potential，补 Walker circulation 上层分支。",
          "继续保留 OLR 和 GPCP 双约束，判断降水/对流中心是否从偏北/偏西转向赤道中东太平洋。",
        ]
      : [
          "Wait for the June 2026 ERA5 monthly mean to construct formal AMJ 2026, rather than using MAM or Apr-May as proxies.",
          "Insert ERA5 wind-pressure diagnostics into the existing response-ratio / observed-vs-expected framework for direct 2023-versus-2026 comparison.",
          "Recalculate 2023/24 AMJ/JJA using the same ERA5 variables to avoid dataset-dependent interpretation.",
          "Add 200 hPa divergence or velocity potential to diagnose the upper branch of the Walker circulation.",
          "Keep both OLR and GPCP constraints to test whether convection/rainfall shifts from west/north displacement toward the equatorial central-eastern Pacific.",
        ];
    addBullets(slide, items, 78, 148, 1080, 298, lang, pt(17), "next-step-bullets");
    addCallout(slide,
      cn ? "可作为开题后的明确工作线" : "A concrete post-presentation work line",
      cn
        ? "题目可以从“2023/24 强厄尔尼诺海气脱耦”扩展为“发展季海温、风压、降水和 Walker 环流的不等时响应：2023/24 复现与 2026 实时对照”。"
        : "A working title could expand from “2023/24 strong El Nino air-sea decoupling” to “Asynchronous developing-season responses of SST, wind-pressure, rainfall, and the Walker circulation: a 2023/24 reproduction and 2026 real-time comparison.”",
      78, 490, 1080, 104, COLORS.paleBlue, COLORS.blue, lang, "workline");
  }

  addSourceSlide(pres, lang, 13);

  return pres;
}

async function exportDeck(pres, lang, outPath) {
  const previewDir = path.join(PREVIEW_ROOT, lang);
  const layoutDir = path.join(LAYOUT_ROOT, lang);
  await fs.mkdir(previewDir, { recursive: true });
  await fs.mkdir(layoutDir, { recursive: true });

  for (const [idx, slide] of pres.slides.items.entries()) {
    const stem = `slide-${String(idx + 1).padStart(2, "0")}`;
    const png = await pres.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(previewDir, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(layoutDir, `${stem}.layout.json`), await layout.text());
  }

  const montage = await pres.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(path.join(previewDir, "deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));

  const inspect = await pres.inspect({ kind: "slide,textbox,shape,image,table", maxChars: 60000 });
  await fs.writeFile(path.join(layoutDir, "inspect.ndjson"), inspect.ndjson);

  const pptx = await PresentationFile.exportPptx(pres);
  await pptx.save(outPath);
}

async function main() {
  await ensureInputs();
  const cnDeck = await createDeck("cn");
  const enDeck = await createDeck("en");
  const cnPath = path.join(OUT_DIR, "2026_ENSO_FEP_ERA5_Current_Diagnosis_CN.pptx");
  const enPath = path.join(OUT_DIR, "2026_ENSO_FEP_ERA5_Current_Diagnosis_EN.pptx");
  await exportDeck(cnDeck, "cn", cnPath);
  await exportDeck(enDeck, "en", enPath);
  console.log(JSON.stringify({
    cnPath,
    enPath,
    cnPreview: path.join(PREVIEW_ROOT, "cn/deck-montage.webp"),
    enPreview: path.join(PREVIEW_ROOT, "en/deck-montage.webp"),
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
