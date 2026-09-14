#!/usr/bin/env node

/**
 * Plot a vertical Niño3.4 SST-anomaly time series aligned to the time axis of
 * the Jiang et al. (2026) Figure 4-style extension.
 *
 * Input is the already-derived same-source ERSSTv5 monthly table. The plotted
 * anomaly is the monthly Niño3.4 anomaly after removal of the 1960-2024
 * calendar-month climatology and the linear trend fitted over the same period.
 */

const fs = require("node:fs");
const path = require("node:path");
const sharp = require("sharp");
const { PDFDocument } = require("pdf-lib");

const ROOT = path.resolve(__dirname, "..");
const INPUT = path.join(
  ROOT,
  "data",
  "derived",
  "research_2026",
  "grl_fig4_same_source_monthly_sst_residual_ersstv5.csv",
);
const OUT_DIR = path.join(ROOT, "outputs", "research_2026", "figures");
const PNG_PATH = path.join(
  OUT_DIR,
  "fig12c_ersstv5_nino34_vertical_timeseries_1960_202606_600dpi.png",
);
const PDF_PATH = path.join(
  OUT_DIR,
  "fig12c_ersstv5_nino34_vertical_timeseries_1960_202606.pdf",
);

const COLORS = {
  ink: "#17212B",
  muted: "#5C6773",
  grid: "#D9E0E6",
  axis: "#6D7882",
  raw: "#8B96A0",
  positive: "#D6604D",
  negative: "#4393C3",
  positiveFill: "#F3A183",
  negativeFill: "#92C5DE",
  endpoint: "#8E1B17",
  multiYearFill: "#D9CCE9",
  multiYearEdge: "#73558F",
};

// Major multi-year La Niña episodes within the plotted period. Bounds are
// expressed as approximate calendar-year spans because exact onset/termination
// varies slightly with the ENSO index and seasonal averaging convention.
const MULTIYEAR_LA_NINA = [
  [1970.5, 1972.25, "1970-72"],
  [1973.5, 1976.25, "1973-76"],
  [1983.5, 1985.25, "1983-85"],
  [1998.5, 2001.25, "1998-01"],
  [2007.5, 2009.25, "2007-09"],
  [2010.5, 2012.25, "2010-12"],
  [2016.5, 2018.25, "2016-18"],
  [2020.5, 2023.25, "2020-23"],
];

function readData() {
  const lines = fs.readFileSync(INPUT, "utf8").trim().split(/\r?\n/);
  const header = lines[0].split(",");
  const column = Object.fromEntries(header.map((name, index) => [name, index]));
  return lines
    .slice(1)
    .map((line) => {
      const values = line.split(",");
      const year = Number(values[column.year]);
      const month = Number(values[column.month]);
      return {
        year,
        month,
        time: year + (month - 0.5) / 12,
        value: Number(values[column.nino34_detrended]),
      };
    })
    .filter(
      (row) =>
        row.year >= 1960 &&
        (row.year < 2026 || row.month <= 6) &&
        Number.isFinite(row.value),
    )
    .sort((a, b) => a.time - b.time);
}

function trailingMean(values, window) {
  return values.map((_, index) => {
    if (index < window - 1) return null;
    const subset = values.slice(index - window + 1, index + 1);
    return subset.reduce((sum, value) => sum + value, 0) / subset.length;
  });
}

function pathFromSeries(data, values, xScale, yScale) {
  let pathData = "";
  let open = false;
  values.forEach((value, index) => {
    if (!Number.isFinite(value)) {
      open = false;
      return;
    }
    pathData += `${open ? "L" : "M"} ${xScale(value).toFixed(2)} ${yScale(data[index].time).toFixed(2)} `;
    open = true;
  });
  return pathData.trim();
}

function fillSegments(data, values, xScale, yScale) {
  const zeroX = xScale(0);
  const polygons = [];

  function polygon(points, positive) {
    const fill = positive ? COLORS.positiveFill : COLORS.negativeFill;
    polygons.push(
      `<polygon points="${points
        .map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`)
        .join(" ")}" fill="${fill}" fill-opacity="0.76"/>`,
    );
  }

  for (let index = 0; index < values.length - 1; index += 1) {
    const value0 = values[index];
    const value1 = values[index + 1];
    if (!Number.isFinite(value0) || !Number.isFinite(value1)) continue;

    const y0 = yScale(data[index].time);
    const y1 = yScale(data[index + 1].time);
    const x0 = xScale(value0);
    const x1 = xScale(value1);

    if (value0 === 0 || value1 === 0 || Math.sign(value0) === Math.sign(value1)) {
      const signValue = value0 === 0 ? value1 : value0;
      polygon(
        [
          [zeroX, y0],
          [x0, y0],
          [x1, y1],
          [zeroX, y1],
        ],
        signValue >= 0,
      );
      continue;
    }

    const fraction = Math.abs(value0) / (Math.abs(value0) + Math.abs(value1));
    const crossingY = y0 + fraction * (y1 - y0);
    polygon(
      [
        [zeroX, y0],
        [x0, y0],
        [zeroX, crossingY],
      ],
      value0 > 0,
    );
    polygon(
      [
        [zeroX, crossingY],
        [x1, y1],
        [zeroX, y1],
      ],
      value1 > 0,
    );
  }
  return polygons.join("\n");
}

function buildSvg(data) {
  const width = 700;
  const height = 1050;
  const left = 105;
  const right = 660;
  const top = 150;
  const bottom = 900;
  const plotWidth = right - left;
  const plotHeight = bottom - top;
  const xMin = -3;
  const xMax = 3;
  const yMin = 1960;
  const yMax = 2026.5;
  const smooth = trailingMean(
    data.map((row) => row.value),
    3,
  );

  const xScale = (value) => left + ((value - xMin) / (xMax - xMin)) * plotWidth;
  const yScale = (value) => bottom - ((value - yMin) / (yMax - yMin)) * plotHeight;
  const elements = [];

  elements.push(`<rect width="${width}" height="${height}" fill="white"/>`);
  elements.push(
    `<text x="${width / 2}" y="43" text-anchor="middle" class="main-title">ERSSTv5 Niño3.4 SST anomaly</text>`,
    `<text x="${width / 2}" y="72" text-anchor="middle" class="subtitle">January 1960-June 2026</text>`,
  );

  MULTIYEAR_LA_NINA.forEach(([start, end, label]) => {
    const bandTop = yScale(end);
    const bandBottom = yScale(start);
    const labelY = (bandTop + bandBottom) / 2 + 3.5;
    elements.push(
      `<rect x="${left}" y="${bandTop}" width="${plotWidth}" height="${bandBottom - bandTop}" fill="${COLORS.multiYearFill}" fill-opacity="0.34" stroke="${COLORS.multiYearEdge}" stroke-opacity="0.55" stroke-width="0.8" stroke-dasharray="4 4"/>`,
      `<text x="${right - 7}" y="${labelY}" text-anchor="end" class="episode">MY-LN ${label}</text>`,
    );
  });

  for (let xTick = -3; xTick <= 3; xTick += 1) {
    const x = xScale(xTick);
    elements.push(
      `<line x1="${x}" y1="${top}" x2="${x}" y2="${bottom}" stroke="${COLORS.grid}" stroke-width="0.9"/>`,
      `<line x1="${x}" y1="${bottom}" x2="${x}" y2="${bottom + 6}" stroke="${COLORS.axis}" stroke-width="1"/>`,
      `<text x="${x}" y="${bottom + 27}" text-anchor="middle" class="tick">${xTick}</text>`,
    );
  }

  for (let year = 1960; year <= 2025; year += 5) {
    const y = yScale(year);
    elements.push(
      `<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" stroke="${COLORS.grid}" stroke-width="0.9"/>`,
      `<line x1="${left - 6}" y1="${y}" x2="${left}" y2="${y}" stroke="${COLORS.axis}" stroke-width="1"/>`,
      `<text x="${left - 13}" y="${y + 4}" text-anchor="end" class="tick">${year}</text>`,
    );
  }

  elements.push(fillSegments(data, smooth, xScale, yScale));

  for (const markerYear of [1976, 2005]) {
    const y = yScale(markerYear);
    elements.push(
      `<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" stroke="#FFFFFF" stroke-width="2.0" stroke-dasharray="7 6"/>`,
      `<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" stroke="#65717B" stroke-opacity="0.55" stroke-width="0.8" stroke-dasharray="7 6"/>`,
    );
  }

  const zeroX = xScale(0);
  elements.push(
    `<line x1="${zeroX}" y1="${top}" x2="${zeroX}" y2="${bottom}" stroke="${COLORS.ink}" stroke-width="1.5"/>`,
    `<path d="${pathFromSeries(
      data,
      data.map((row) => row.value),
      xScale,
      yScale,
    )}" fill="none" stroke="${COLORS.raw}" stroke-width="0.85" stroke-opacity="0.85" stroke-linejoin="round"/>`,
    `<path d="${pathFromSeries(data, smooth, xScale, yScale)}" fill="none" stroke="${COLORS.ink}" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>`,
    `<line x1="${left}" y1="${top}" x2="${left}" y2="${bottom}" stroke="${COLORS.axis}" stroke-width="1.2"/>`,
    `<line x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}" stroke="${COLORS.axis}" stroke-width="1.2"/>`,
  );

  elements.push(
    `<text x="${(left + right) / 2}" y="${bottom + 58}" text-anchor="middle" class="axis-label">Niño3.4 SST anomaly (°C)</text>`,
    `<text x="30" y="${(top + bottom) / 2}" text-anchor="middle" class="axis-label" transform="rotate(-90 30 ${(top + bottom) / 2})">Time (year)</text>`,
  );

  const legendY = 104;
  elements.push(
    `<rect x="${left}" y="${legendY - 10}" width="18" height="12" fill="${COLORS.negativeFill}" fill-opacity="0.76"/>`,
    `<text x="${left + 25}" y="${legendY}" class="legend">Negative anomaly</text>`,
    `<rect x="${left + 150}" y="${legendY - 10}" width="18" height="12" fill="${COLORS.positiveFill}" fill-opacity="0.76"/>`,
    `<text x="${left + 175}" y="${legendY}" class="legend">Positive anomaly</text>`,
    `<line x1="${left + 308}" y1="${legendY - 4}" x2="${left + 340}" y2="${legendY - 4}" stroke="${COLORS.raw}" stroke-width="1.2"/>`,
    `<text x="${left + 348}" y="${legendY}" class="legend">Monthly</text>`,
    `<line x1="${left + 420}" y1="${legendY - 4}" x2="${left + 452}" y2="${legendY - 4}" stroke="${COLORS.ink}" stroke-width="2.2"/>`,
    `<text x="${left + 460}" y="${legendY}" class="legend">3-month mean</text>`,
    `<rect x="${left}" y="121" width="18" height="12" fill="${COLORS.multiYearFill}" fill-opacity="0.55" stroke="${COLORS.multiYearEdge}" stroke-width="0.8" stroke-dasharray="4 3"/>`,
    `<text x="${left + 25}" y="131" class="legend">Major multi-year La Niña interval (MY-LN)</text>`,
  );

  const last = data[data.length - 1];
  const lastX = xScale(last.value);
  const lastY = yScale(last.time);
  const labelToLeft = last.value > 1.8;
  elements.push(
    `<circle cx="${lastX}" cy="${lastY}" r="4.8" fill="${COLORS.endpoint}" stroke="white" stroke-width="1.2"/>`,
    `<line x1="${lastX}" y1="${lastY + 2}" x2="${lastX + (labelToLeft ? -34 : 34)}" y2="${lastY + 31}" stroke="${COLORS.endpoint}" stroke-width="1"/>`,
    `<text x="${lastX + (labelToLeft ? -40 : 40)}" y="${lastY + 31}" text-anchor="${labelToLeft ? "end" : "start"}" class="endpoint">Jun 2026: ${last.value >= 0 ? "+" : ""}${last.value.toFixed(2)}°C</text>`,
  );

  elements.push(
    `<text x="${left}" y="982" class="footnote">NOAA ERSSTv5; Niño3.4 = 5°S-5°N, 170°W-120°W.</text>`,
    `<text x="${left}" y="1000" class="footnote">The 1960-2024 calendar-month climatology and linear trend are removed.</text>`,
    `<text x="${left}" y="1018" class="footnote">Shading and the dark curve show the 3-month trailing mean; the thin gray curve is monthly.</text>`,
    `<text x="${left}" y="1036" class="footnote">MY-LN episode bounds are approximate; exact endpoints can vary slightly with the ENSO index.</text>`,
  );

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <style>
    text { font-family: Arial, Helvetica, sans-serif; fill: ${COLORS.ink}; }
    .main-title { font-size: 22px; font-weight: 700; }
    .subtitle { font-size: 16px; font-weight: 700; }
    .tick { font-size: 12px; }
    .axis-label { font-size: 14px; }
    .legend { font-size: 10.5px; fill: ${COLORS.muted}; }
    .episode { font-size: 8.8px; font-weight: 700; fill: ${COLORS.multiYearEdge}; paint-order: stroke; stroke: white; stroke-width: 2.5px; }
    .endpoint { font-size: 11px; font-weight: 700; fill: ${COLORS.endpoint}; }
    .footnote { font-size: 10.5px; fill: ${COLORS.muted}; }
  </style>
  ${elements.join("\n  ")}
</svg>`;
}

async function main() {
  const data = readData();
  const svg = buildSvg(data);
  const png = await sharp(Buffer.from(svg))
    .resize({ width: 3360, height: 5040, fit: "fill" })
    .png({ compressionLevel: 9 })
    .toBuffer();

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(PNG_PATH, png);

  const pdf = await PDFDocument.create();
  const image = await pdf.embedPng(png);
  const page = pdf.addPage([420, 630]);
  page.drawImage(image, { x: 0, y: 0, width: 420, height: 630 });
  pdf.setTitle("ERSSTv5 Niño3.4 SST anomaly, January 1960-June 2026");
  pdf.setSubject("Vertical Niño3.4 time series aligned with the Jiang et al. Figure 4 extension");
  pdf.setCreator("Codex climate plotting workflow");
  fs.writeFileSync(PDF_PATH, await pdf.save());

  process.stdout.write(`${PNG_PATH}\n${PDF_PATH}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
