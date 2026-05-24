
const C = {
  bg: "#f7f3ea",
  ink: "#1d1b18",
  muted: "#6e675d",
  rule: "#d8d1c4",
  red: "#cc5a43",
  teal: "#2f6f73",
  blue: "#4a5f99",
  pale: "#efe8dc",
  cream: "#fbf8f1",
  greenPale: "#edf3ef",
  rosePale: "#f5e5df",
};

function bg(slide, ctx) {
  ctx.addShape(slide, { x: 0, y: 0, w: 1280, h: 720, fill: C.bg });
}

function text(slide, ctx, value, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text: value || "", x, y, w, h,
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
  text(slide, ctx, d.kicker, 64, 34, 300, 24, { size: 13, bold: true, color: C.red });
  text(slide, ctx, d.title, 64, 65, 1090, 82, { size: 31, bold: true, title: true });
  ctx.addShape(slide, { x: 64, y: 151, w: 1120, h: 1.5, fill: C.rule });
}

function source(slide, ctx, value) {
  text(slide, ctx, value || "", 64, 684, 1100, 22, { size: 8.6, color: C.muted });
}

function bulletList(slide, ctx, items, x, y, w, row = 55, size = 17) {
  let yy = y;
  for (const item of items || []) {
    ctx.addShape(slide, { x, y: yy + 8, w: 7, h: 7, fill: C.red, geometry: "ellipse" });
    text(slide, ctx, item, x + 20, yy, w - 20, row - 5, { size });
    yy += row;
  }
}

async function addImage(slide, ctx, imagePath, x, y, w, h, fit = "contain") {
  await ctx.addImage(slide, { path: imagePath, x, y, w, h, fit });
}

function note(slide, ctx, value, x, y, w, h = 42) {
  ctx.addShape(slide, { x, y, w, h, fill: "#fffaf1", line: { style: "solid", fill: C.rule, width: 0.8 } });
  text(slide, ctx, value, x + 12, y + 8, w - 24, h - 12, { size: 10.4, color: C.muted });
}

function smallTable(slide, ctx, rows, x, y, w, rowH = 38, opts = {}) {
  const cols = rows[0].length;
  const colW = opts.colWidths || Array(cols).fill(w / cols);
  rows.forEach((row, r) => {
    let xx = x;
    row.forEach((cell, c) => {
      const cw = colW[c];
      ctx.addShape(slide, {
        x: xx, y: y + r * rowH, w: cw, h: rowH,
        fill: r === 0 ? C.ink : (r % 2 === 0 ? "#f3ede2" : C.cream),
        line: { style: "solid", fill: C.rule, width: 0.7 },
      });
      text(slide, ctx, cell, xx + 8, y + r * rowH + 7, cw - 16, rowH - 10, {
        size: r === 0 ? (opts.headerSize || 11) : (opts.size || 12.2),
        bold: r === 0,
        color: r === 0 ? "#ffffff" : C.ink,
      });
      xx += cw;
    });
  });
}

async function renderDeckSlide(presentation, ctx, d) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  if (d.layout === "cover") {
    text(slide, ctx, d.kicker, 64, 52, 260, 26, { size: 14, bold: true, color: C.red });
    text(slide, ctx, d.title, 64, 102, 890, 188, { size: 40, bold: true, title: true });
    text(slide, ctx, d.subtitle, 66, 316, 940, 62, { size: 21, color: C.muted });
    bulletList(slide, ctx, d.bullets, 72, 440, 860, 56, 18);
    ctx.addShape(slide, { x: 1012, y: 118, w: 148, h: 148, fill: C.red, geometry: "ellipse" });
    ctx.addShape(slide, { x: 1074, y: 308, w: 92, h: 92, fill: C.teal, geometry: "ellipse" });
    ctx.addShape(slide, { x: 996, y: 455, w: 176, h: 22, fill: C.blue });
    source(slide, ctx, d.source);
    return slide;
  }

  header(slide, ctx, d);

  if (d.layout === "thesis") {
    ctx.addShape(slide, { x: 84, y: 190, w: 1010, h: 136, fill: C.rosePale, line: { style: "solid", fill: C.rule, width: 1 } });
    text(slide, ctx, d.claim, 112, 214, 954, 92, { size: 23, bold: true, color: C.ink });
    bulletList(slide, ctx, d.notes, 104, 370, 960, 70, 18);
  } else if (d.layout === "flow" || d.layout === "roadmap") {
    const y = d.layout === "flow" ? 236 : 228;
    d.steps.forEach((step, i) => {
      const x = 74 + i * 288;
      const h = d.layout === "flow" ? 132 : 160;
      ctx.addShape(slide, { x, y, w: 236, h, fill: i % 2 ? C.greenPale : C.rosePale, line: { style: "solid", fill: C.rule, width: 1 } });
      text(slide, ctx, String(i + 1).padStart(2, "0"), x + 17, y + 16, 48, 28, { size: 17, bold: true, color: i % 2 ? C.teal : C.red });
      text(slide, ctx, step, x + 18, y + 54, 198, h - 70, { size: 16.2, bold: true });
      if (i < d.steps.length - 1) text(slide, ctx, ">", x + 248, y + 48, 28, 40, { size: 25, color: C.muted });
    });
    bulletList(slide, ctx, d.notes || [], 94, 466, 960, 52, 18);
  } else if (d.layout === "imagePairText") {
    await addImage(slide, ctx, d.image, 66, 178, 528, 386);
    await addImage(slide, ctx, d.chart, 620, 186, 430, 250);
    bulletList(slide, ctx, d.bullets, 632, 462, 480, 42, 14.5);
    note(slide, ctx, d.figNote, 68, 574, 1088, 82);
  } else if (d.layout === "fullImage") {
    await addImage(slide, ctx, d.image, 70, 172, 1080, 380);
    note(slide, ctx, d.figNote, 70, 568, 1080, 88);
  } else if (d.layout === "twoImagesTable") {
    await addImage(slide, ctx, d.leftImage, 64, 178, 376, 296);
    await addImage(slide, ctx, d.rightImage, 458, 178, 376, 296);
    text(slide, ctx, d.tableTitle, 870, 184, 260, 26, { size: 18, bold: true });
    smallTable(slide, ctx, d.table, 860, 224, 310, 42);
    note(slide, ctx, d.figNote, 66, 568, 1088, 88);
  } else if (d.layout === "imageBrief") {
    await addImage(slide, ctx, d.image, 78, 184, 548, 358);
    bulletList(slide, ctx, d.bullets, 680, 214, 430, 78, 18);
    note(slide, ctx, d.figNote, 78, 568, 1080, 88);
  } else if (d.layout === "imageTable") {
    await addImage(slide, ctx, d.image, 72, 174, 650, 376);
    smallTable(slide, ctx, d.table, 760, 218, 380, 44);
    note(slide, ctx, d.figNote, 72, 568, 1080, 88);
  } else if (d.layout === "twoChartsTable") {
    await addImage(slide, ctx, d.leftImage, 70, 180, 392, 302);
    await addImage(slide, ctx, d.rightImage, 480, 180, 392, 302);
    smallTable(slide, ctx, d.table, 880, 204, 304, 42, { colWidths: [164, 70, 70], size: 11.2, headerSize: 10.5 });
    note(slide, ctx, d.figNote, 72, 568, 1080, 88);
  } else if (d.layout === "comparison") {
    smallTable(slide, ctx, d.table, 72, 190, 1088, d.reader ? 54 : 64, { colWidths: [190, 405, 493], size: d.reader ? 10.6 : 11.4, headerSize: 11 });
    if (d.reader) note(slide, ctx, d.reader, 72, 540, 1088, 78);
  } else if (d.layout === "glossary") {
    smallTable(slide, ctx, d.table, 72, 178, 1088, 45, { colWidths: [140, 300, 648], size: 10.8, headerSize: 11 });
    note(slide, ctx, d.reader, 72, 596, 1088, 54);
  } else if (d.layout === "appendixTable") {
    smallTable(slide, ctx, d.table, 72, 178, 1088, 56, { colWidths: [96, 392, 600], size: 11.5, headerSize: 11 });
  } else if (d.layout === "links") {
    const rows = [["Source", "URL"], ...d.links];
    smallTable(slide, ctx, rows, 76, 176, 1078, 44, { colWidths: [255, 823], size: 10.4, headerSize: 11 });
  }

  source(slide, ctx, d.source);
  return slide;
}

export { renderDeckSlide };
