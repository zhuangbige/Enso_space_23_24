
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
