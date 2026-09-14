const fs = require('fs');
const path = require('path');

const moduleRoot = '/Users/daiyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const sharp = require(path.join(moduleRoot, 'sharp'));
const { PDFDocument } = require(path.join(moduleRoot, 'pdf-lib'));

const OUT = '/Users/daiyue/Documents/Maryland/outputs/research_2026/figures';
fs.mkdirSync(OUT, { recursive: true });

const C = {
  ink: '#10283B',
  muted: '#426077',
  grid: '#D8E2E9',
  ct: '#D97706',
  cp: '#2F7FBA',
  red: '#BE3A3A',
  teal: '#168B80',
  cpBand: '#DCEEF7',
  ctBand: '#FFF0D2',
  white: '#FFFFFF',
};

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function text(x, y, value, size, opts = {}) {
  const anchor = opts.anchor || 'start';
  const weight = opts.weight || 400;
  const fill = opts.fill || C.ink;
  const italic = opts.italic ? 'italic' : 'normal';
  const family = opts.family || 'Arial, Helvetica, sans-serif';
  const baseline = opts.baseline || 'alphabetic';
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" dominant-baseline="${baseline}" font-family="${family}" font-size="${size}" font-weight="${weight}" font-style="${italic}" fill="${fill}">${esc(value)}</text>`;
}

function line(x1, y1, x2, y2, stroke, width = 1, dash = '') {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${width}"${dash ? ` stroke-dasharray="${dash}"` : ''}/>`;
}

function rect(x, y, w, h, fill, rx = 0, stroke = 'none', sw = 0) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
}

function circle(cx, cy, r, fill, stroke = 'none', sw = 0) {
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
}

async function exportFigure(svg, stem, width, height) {
  const svgPath = path.join(OUT, `${stem}.svg`);
  const pngPath = path.join(OUT, `${stem}.png`);
  const pdfPath = path.join(OUT, `${stem}.pdf`);
  fs.writeFileSync(svgPath, svg);

  const png = await sharp(Buffer.from(svg))
    .resize(width * 2, height * 2)
    .png({ compressionLevel: 9 })
    .toBuffer();
  fs.writeFileSync(pngPath, png);

  const pdfDoc = await PDFDocument.create();
  const page = pdfDoc.addPage([width, height]);
  const image = await pdfDoc.embedPng(png);
  page.drawImage(image, { x: 0, y: 0, width, height });
  fs.writeFileSync(pdfPath, await pdfDoc.save());
  return { svgPath, pngPath, pdfPath };
}

function warmHeatBudgetFigure() {
  const W = 1600;
  const H = 720;
  const left = 375;
  const right = 80;
  const top = 145;
  const bottom = 118;
  const plotW = W - left - right;
  const plotH = H - top - bottom;
  const xmin = -3.4;
  const xmax = 5.0;
  const sx = x => left + ((x - xmin) / (xmax - xmin)) * plotW;

  const rows = [
    { label: '5°N input', ct: [2.74244682, 0.923864347, 4.56102929], cp: [-0.959627273, -1.50874583, -0.245312805] },
    { label: 'Zonal convergence, Cx,N', ct: [-1.65382937, -2.50346664, -0.176024822], cp: [0.738788462, 0.147177448, 1.61234262] },
    { label: '12°N input term', ct: [-0.0636903747, -0.483725183, 0.364526967], cp: [-0.174510768, -0.968643602, 0.296185695] },
    { label: 'Surface warm-layer term', ct: [-1.70222542, -2.42973366, -0.974717177], cp: [-0.676838919, -0.996856201, -0.230157979] },
    { label: 'Residual', ct: [1.27294475, 0.933680771, 1.61220874], cp: [0.811696631, 0.566869993, 1.05478738] },
    { label: 'Storage tendency', ct: [0.595646407, 0.184841595, 0.885662888], cp: [-0.260491867, -0.887588819, 0.716135612] },
  ];
  const rowGap = plotH / rows.length;
  const ticks = [-3, -2, -1, 0, 1, 2, 3, 4, 5];
  const parts = [];
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`);
  parts.push(rect(0, 0, W, H, C.white));

  parts.push(text(42, 48, 'Northern receiver-box warm-heat budget', 32, { weight: 700 }));
  parts.push(text(42, 82, 'Cumulative anomalies: Dec(0)–May(+1)', 22, { fill: C.muted, weight: 600 }));
  parts.push(text(W - 42, 48, 'Receiver box: 5°–12°N, 140°W–80°W, 0–300 m', 20, { fill: C.muted, anchor: 'end', weight: 600 }));

  const legendY = 104;
  parts.push(circle(W - 330, legendY, 8, C.ct));
  parts.push(text(W - 313, legendY + 1, 'CT (n = 4)', 19, { fill: C.ct, weight: 700, baseline: 'middle' }));
  parts.push(circle(W - 175, legendY, 8, C.cp));
  parts.push(text(W - 158, legendY + 1, 'CP (n = 4)', 19, { fill: C.cp, weight: 700, baseline: 'middle' }));

  ticks.forEach(t => {
    const x = sx(t);
    parts.push(line(x, top, x, H - bottom, t === 0 ? C.ink : C.grid, t === 0 ? 3 : 1));
    parts.push(text(x, H - bottom + 39, String(t).replace('-', '−'), 19, { anchor: 'middle', fill: C.muted }));
  });

  function errorMark(values, y, color, labelAbove) {
    const [mean, lo, hi] = values;
    const xlo = sx(lo);
    const xhi = sx(hi);
    const xm = sx(mean);
    parts.push(line(xlo, y, xhi, y, color, 4));
    parts.push(line(xlo, y - 10, xlo, y + 10, color, 3));
    parts.push(line(xhi, y - 10, xhi, y + 10, color, 3));
    parts.push(circle(xm, y, 10, color));
    const signed = `${mean >= 0 ? '+' : '−'}${Math.abs(mean).toFixed(2)}`;
    let tx = xm + 14;
    let anchor = 'start';
    if (mean > 4.1) { tx = xm - 14; anchor = 'end'; }
    if (mean < -2.6) { tx = xm + 14; anchor = 'start'; }
    parts.push(text(tx, y + (labelAbove ? -15 : 24), signed, 18, { fill: color, weight: 700, anchor }));
  }

  rows.forEach((row, i) => {
    const yc = top + (i + 0.5) * rowGap;
    if (i > 0) parts.push(line(24, top + i * rowGap, W - 40, top + i * rowGap, '#E5ECF1', 1));
    parts.push(text(28, yc, row.label, 23, { weight: 700, baseline: 'middle' }));
    errorMark(row.ct, yc - 13, C.ct, true);
    errorMark(row.cp, yc + 13, C.cp, false);
  });

  parts.push(text(left + plotW / 2, H - 53, 'Cumulative anomalous warm-heat contribution (ZJ)', 23, { anchor: 'middle', weight: 700, fill: C.muted }));
  parts.push(text(42, H - 19, 'Positive values add H₂₀ to the receiver box; negative values remove it. Dots show event means; whiskers show 95% event-bootstrap intervals.', 15, { fill: C.muted }));
  parts.push(text(W - 42, H - 19, 'Source: SODA3.15.2', 15, { fill: C.muted, anchor: 'end' }));
  parts.push('</svg>');
  return { svg: parts.join('\n'), W, H };
}

function ensoFlavorFigure() {
  const W = 1600;
  const H = 720;
  const left = 260;
  const right = 75;
  const top = 130;
  const bottom = 92;
  const plotW = W - left - right;
  const xmin = -1.0;
  const xmax = 2.5;
  const sx = x => left + ((x - xmin) / (xmax - xmin)) * plotW;
  const zero = sx(0);
  const rows = [
    { event: '1997/98', value: 2.18, color: C.ct, title: 'Canonical CT', note: 'Eastern warming overwhelmingly dominates.' },
    { event: '2015/16', value: 1.07, color: C.red, title: 'CT-like / E–C mixed', note: 'Eastern warming dominates, with concurrent central-Pacific warming.' },
    { event: '2023/24', value: 0.59, color: C.teal, title: 'CT-like / FEP-led', note: 'Eastern warming leads; development-stage coupling is weaker.' },
  ];
  const ys = [220, 380, 540];
  const ticks = [-1.0, -0.5, 0, 0.5, 1.0, 1.5, 2.0, 2.5];
  const parts = [];
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`);
  parts.push(rect(0, 0, W, H, C.white));
  parts.push(text(42, 48, 'Mature-phase ENSO flavor of the three events', 32, { weight: 700 }));
  parts.push(text(42, 82, 'Classified by the DJF Niño3 − Niño4 SST-anomaly contrast', 21, { fill: C.muted, weight: 600 }));

  const bandY = 99;
  const bandH = 46;
  parts.push(rect(left, bandY, zero - left, bandH, C.cpBand, 8));
  parts.push(rect(zero, bandY, W - right - zero, bandH, C.ctBand, 8));
  parts.push(text(left + (zero - left) / 2, bandY + bandH / 2 + 1, 'CP-like: central-Pacific warming maximum', 19, { anchor: 'middle', baseline: 'middle', weight: 700, fill: C.cp }));
  parts.push(text(zero + (W - right - zero) / 2, bandY + bandH / 2 + 1, 'CT-like: eastern cold-tongue warming maximum', 19, { anchor: 'middle', baseline: 'middle', weight: 700, fill: C.ct }));

  ticks.forEach(t => {
    const x = sx(t);
    parts.push(line(x, top + 24, x, H - bottom, t === 0 ? C.ink : C.grid, t === 0 ? 3 : 1));
    const label = (Math.abs(t) < 1e-9 ? '0.0' : t.toFixed(1)).replace('-', '−');
    parts.push(text(x, H - bottom + 34, label, 18, { anchor: 'middle', fill: C.muted }));
  });

  rows.forEach((row, i) => {
    const y = ys[i];
    const xv = sx(row.value);
    parts.push(text(26, y, row.event, 30, { weight: 700, baseline: 'middle' }));
    parts.push(line(zero, y, xv, y, row.color, 15));
    parts.push(circle(xv, y, 16, row.color));
    parts.push(text(xv, y - 38, `+${row.value.toFixed(2)}°C`, 22, { anchor: 'middle', fill: row.color, weight: 700 }));

    const tx = sx(0.94);
    parts.push(text(tx, y - 15, row.title, 25, { fill: row.color, weight: 700 }));
    parts.push(text(tx, y + 31, row.note, 19, { fill: C.muted, weight: 600 }));
  });

  parts.push(text(left + plotW / 2, H - 27, 'Mature DJF Niño3 − Niño4 SST anomaly (°C)', 23, { anchor: 'middle', weight: 700, fill: C.muted }));
  parts.push('</svg>');
  return { svg: parts.join('\n'), W, H };
}

function partitionCouplingFigure() {
  const W = 1600;
  const H = 900;
  const left = 190;
  const right = 90;
  const top = 165;
  const bottom = 135;
  const plotW = W - left - right;
  const plotH = H - top - bottom;
  const xmin = -1.55;
  const xmax = 1.05;
  const ymin = -1.45;
  const ymax = 1.70;
  const sx = x => left + ((x - xmin) / (xmax - xmin)) * plotW;
  const sy = y => top + ((ymax - y) / (ymax - ymin)) * plotH;
  const points = [
    [1982, 0.502933360, -1.175330009],
    [1986, 0.514752563, -0.679639339],
    [1991, -0.979835506, 0.206244658],
    [1994, -1.256827975, 0.415802355],
    [1997, -0.287140498, 0.287916878],
    [2002, 0.845509376, -0.419109438],
    [2004, 0.838318823, -0.316562618],
    [2006, -0.145215961, 0.632199926],
    [2009, 0.648202805, -0.192650352],
    [2015, -1.240716338, 1.410089984],
    [2018, -0.481695285, 0.227891111],
    [2019, 0.678629820, 0.450762081],
    [2023, 0.363084816, -0.847615237],
  ];
  const slope = -0.603834584;
  const intercept = 0;
  const n = points.length;
  const controls = 3;
  const df = n - controls - 2;
  const tCritical = 2.306;
  const xbar = points.reduce((a, p) => a + p[1], 0) / n;
  const sxx = points.reduce((a, p) => a + (p[1] - xbar) ** 2, 0);
  const sse = points.reduce((a, p) => a + (p[2] - (intercept + slope * p[1])) ** 2, 0);
  const mse = sse / df;

  const xs = Array.from({ length: 101 }, (_, i) => xmin + ((xmax - xmin) * i) / 100);
  const upper = xs.map(x => {
    const yhat = intercept + slope * x;
    const se = Math.sqrt(mse * (1 / n + ((x - xbar) ** 2) / sxx));
    return [sx(x), sy(yhat + tCritical * se)];
  });
  const lower = xs.slice().reverse().map(x => {
    const yhat = intercept + slope * x;
    const se = Math.sqrt(mse * (1 / n + ((x - xbar) ** 2) / sxx));
    return [sx(x), sy(yhat - tCritical * se)];
  });
  const bandPath = [...upper, ...lower]
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(2)} ${p[1].toFixed(2)}`)
    .join(' ') + ' Z';

  const eventColors = { 1997: C.ct, 2015: C.red, 2023: C.teal };
  const labelOffsets = {
    1997: [16, -16],
    2015: [16, -15],
    2023: [16, 25],
  };
  const xticks = [-1.5, -1.0, -0.5, 0, 0.5, 1.0];
  const yticks = [-1.2, -0.8, -0.4, 0, 0.4, 0.8, 1.2, 1.6];
  const parts = [];
  parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`);
  parts.push(rect(0, 0, W, H, C.white));
  parts.push(text(48, 54, 'Spring warm-heat configuration precedes the MJJ atmospheric response', 32, { weight: 700 }));
  parts.push(text(48, 92, '13 warm events · Jan–Apr ocean partition versus MJJ wind-stress response', 21, { fill: C.muted, weight: 600 }));
  parts.push(text(48, 126, 'Both axes are residualized against Jan–Feb D20, early partition, and Mar–Apr warm-heat arrival across 140°W.', 17, { fill: C.muted }));

  xticks.forEach(t => {
    const x = sx(t);
    parts.push(line(x, top, x, H - bottom, t === 0 ? '#708797' : C.grid, t === 0 ? 1.7 : 1));
    const label = (t === 0 ? '0.0' : t.toFixed(1)).replace('-', '−');
    parts.push(text(x, H - bottom + 40, label, 18, { anchor: 'middle', fill: C.muted }));
  });
  yticks.forEach(t => {
    const y = sy(t);
    parts.push(line(left, y, W - right, y, t === 0 ? '#708797' : C.grid, t === 0 ? 1.7 : 1));
    const label = (t === 0 ? '0.0' : t.toFixed(1)).replace('-', '−');
    parts.push(text(left - 18, y, label, 18, { anchor: 'end', baseline: 'middle', fill: C.muted }));
  });

  parts.push(`<path d="${bandPath}" fill="#B9CAD6" fill-opacity="0.48" stroke="none"/>`);
  parts.push(line(sx(xmin), sy(intercept + slope * xmin), sx(xmax), sy(intercept + slope * xmax), C.ink, 4));

  points.forEach(([year, x, y]) => {
    if (eventColors[year]) return;
    parts.push(circle(sx(x), sy(y), 10, '#7E97A8', C.white, 2));
  });
  points.forEach(([year, x, y]) => {
    if (!eventColors[year]) return;
    const color = eventColors[year];
    const [dx, dy] = labelOffsets[year];
    parts.push(circle(sx(x), sy(y), 15, color, C.white, 3));
    parts.push(text(sx(x) + dx, sy(y) + dy, String(year), 20, { fill: color, weight: 700 }));
  });

  const statsX = sx(0.66);
  const statsY = sy(1.48);
  parts.push(rect(statsX - 10, statsY - 32, 315, 104, '#F4F7F9', 10, '#D3DEE5', 1));
  parts.push(text(statsX + 12, statsY, 'partial r = −0.68', 20, { weight: 700 }));
  parts.push(text(statsX + 12, statsY + 30, 'permutation p = 0.011', 18, { fill: C.muted, weight: 600 }));
  parts.push(text(statsX + 12, statsY + 57, 'R² = 0.46 · n = 13', 18, { fill: C.muted, weight: 600 }));

  const legendY = H - 45;
  parts.push(`<rect x="${left}" y="${legendY - 10}" width="38" height="18" rx="3" fill="#B9CAD6" fill-opacity="0.48"/>`);
  parts.push(line(left, legendY - 1, left + 38, legendY - 1, C.ink, 3));
  parts.push(text(left + 50, legendY, 'Linear fit with 95% confidence band', 16, { fill: C.muted, baseline: 'middle' }));
  parts.push(text(W - right, legendY, 'SODA3.15.2 · 1982–2022 detrended baseline', 16, { fill: C.muted, anchor: 'end', baseline: 'middle' }));

  parts.push(text(left + plotW / 2, H - bottom + 88, 'Jan–Apr northward warm-heat partition residual', 23, { anchor: 'middle', weight: 700, fill: C.muted }));
  parts.push(`<text x="54" y="${top + plotH / 2}" text-anchor="middle" dominant-baseline="middle" transform="rotate(-90 54 ${top + plotH / 2})" font-family="Arial, Helvetica, sans-serif" font-size="23" font-weight="700" fill="${C.muted}">MJJ wind-stress response residual</text>`);
  parts.push('</svg>');
  return { svg: parts.join('\n'), W, H };
}

(async () => {
  const f1 = warmHeatBudgetFigure();
  const f2 = ensoFlavorFigure();
  const f3 = partitionCouplingFigure();
  const out1 = await exportFigure(f1.svg, 'northern_receiver_warm_heat_budget_CT_CP_english', f1.W, f1.H);
  const out2 = await exportFigure(f2.svg, 'enso_flavor_1997_2015_2023_english', f2.W, f2.H);
  const out3 = await exportFigure(f3.svg, 'spring_partition_MJJ_wind_response_13events_english', f3.W, f3.H);
  console.log(JSON.stringify({ out1, out2, out3 }, null, 2));
})().catch(err => {
  console.error(err);
  process.exit(1);
});
