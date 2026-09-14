#!/usr/bin/env node

/**
 * Create high-resolution PDF versions of the four-panel coupling-sequence
 * diagnostic for the 2015/16 and 2023/24 reference events.
 *
 * The data extraction matches plot_enso_report_late_figures.py:
 *   - western D20: 130°E-180°
 *   - eastern D20: 140°W-85°W
 *   - Niño3: 5°S-5°N, 150°W-90°W
 *   - CWP u10 and CP precipitation: observed and Niño3-conditioned values
 *     from ordinary_el_nino_expected_response.csv
 */

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const sharp = require("sharp");
const { PDFDocument } = require("pdf-lib");

const ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(ROOT, "outputs", "research_2026", "report_visual_revision");
const PYTHON =
  "/Users/daiyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";

const COLORS = {
  ink: "#17212B",
  muted: "#5C6773",
  grid: "#D9E0E6",
  zero: "#707B85",
  deep: "#C96555",
  shoal: "#4F86B5",
  wind: "#246A92",
  rain: "#2A7F68",
  expect: "#C84C43",
  gap: "#DCE2E7",
  panel: "#FBFCFD",
};

const EVENT_META = {
  2015: {
    title: "2015 January-June: strongly coupled tropical Pacific development",
    stages: [
      ["JAN-FEB", "Strong westerlies; basin-scale thermocline tilt", "#EAF2F7"],
      ["MAR-APR", "Surface-atmosphere amplification", "#FBF0E4"],
      ["MAY-JUN", "Deep-convective strengthening", "#EAF4EA"],
    ],
  },
  2023: {
    title: "2023 January-June: ocean-led development with limited atmospheric coupling",
    stages: [
      ["JAN-FEB", "Eastern deepening; wind-convection mismatch", "#EAF2F7"],
      ["MAR-APR", "Surface warming; modest westerly response", "#FBF0E4"],
      ["MAY-JUN", "Partial convective recovery", "#EAF4EA"],
    ],
  },
};

const PYTHON_EXTRACT = String.raw`
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
year = int(sys.argv[2])
npz = root / "data/interim/research_2026/monthly_panel_inputs" / (
    f"monthly_{year}_detrended_fields_1980_2014.npz"
)
expected_csv = (
    root
    / "outputs/research_2026/revised_event_figures"
    / "ordinary_el_nino_expected_response.csv"
)

with np.load(npz) as fields:
    d20_lon = np.asarray(fields["d20_lon"], dtype=float)
    d20 = np.asarray(fields["d20"], dtype=float)
    west_d20 = np.nanmean(d20[:, (d20_lon >= 130) & (d20_lon <= 180)], axis=1)
    east_d20 = np.nanmean(d20[:, (d20_lon >= 220) & (d20_lon <= 275)], axis=1)

    sst = np.asarray(fields["sst"], dtype=float)
    lat = np.asarray(fields["sst_lat"], dtype=float)
    lon = np.asarray(fields["sst_lon"], dtype=float)
    lat_mask = (lat >= -5) & (lat <= 5)
    lon_mask = (lon >= 210) & (lon <= 270)
    subset = sst[:, lat_mask, :][:, :, lon_mask]
    weights = np.cos(np.deg2rad(lat[lat_mask]))
    numerator = np.nansum(subset * weights[None, :, None], axis=(1, 2))
    denominator = np.sum(np.isfinite(subset) * weights[None, :, None], axis=(1, 2))
    nino3 = numerator / denominator

expected = pd.read_csv(expected_csv)

def response(name):
    subset = expected.loc[
        expected["target_year"].eq(year) & expected["response"].eq(name)
    ].sort_values("month")
    return {
        "observed": subset["observed"].astype(float).tolist(),
        "expected": subset["expected"].astype(float).tolist(),
    }

print(json.dumps({
    "west_d20": west_d20.tolist(),
    "east_d20": east_d20.tolist(),
    "nino3": nino3.tolist(),
    "u10": response("cwp_u10"),
    "precipitation": response("cp_precip"),
}))
`;

function extractData(year) {
  const output = execFileSync(
    PYTHON,
    ["-c", PYTHON_EXTRACT, ROOT, String(year)],
    { encoding: "utf8" },
  );
  return JSON.parse(output);
}

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function linePath(values, xScale, yScale) {
  return values
    .map((value, index) => `${index === 0 ? "M" : "L"} ${xScale(index + 1)} ${yScale(value)}`)
    .join(" ");
}

function areaPath(first, second, xScale, yScale) {
  const forward = first.map((value, index) => [xScale(index + 1), yScale(value)]);
  const backward = second
    .map((value, index) => [xScale(index + 1), yScale(value)])
    .reverse();
  return [...forward, ...backward]
    .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`)
    .join(" ") + " Z";
}

function markerSet(values, xScale, yScale, color, shape = "circle") {
  return values
    .map((value, index) => {
      const x = xScale(index + 1);
      const y = yScale(value);
      if (shape === "square") {
        return `<rect x="${x - 3.2}" y="${y - 3.2}" width="6.4" height="6.4" fill="${color}"/>`;
      }
      return `<circle cx="${x}" cy="${y}" r="3.7" fill="${color}"/>`;
    })
    .join("");
}

function buildSvg(year, data) {
  const width = 1340;
  const height = 725;
  const plotLeft = 116;
  const plotRight = 1318;
  const plotWidth = plotRight - plotLeft;
  const panelHeight = 104;
  const panelTops = [132, 260, 388, 516];
  const xMin = 0.8;
  const xMax = 6.2;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const meta = EVENT_META[year];

  const xScale = (month) =>
    plotLeft + ((month - xMin) / (xMax - xMin)) * plotWidth;

  const panelSpecs = [
    {
      title: "a  Thermocline adjustment",
      ylabel: "D20 anomaly (m)",
      domain: [-30, 55],
      ticks: [-20, 0, 20, 40],
      series: [
        { values: data.west_d20, color: COLORS.shoal, label: "Western D20" },
        { values: data.east_d20, color: COLORS.deep, label: "Eastern D20" },
      ],
    },
    {
      title: "b  Eastern-Pacific surface warming",
      ylabel: "Niño3 SSTA (°C)",
      domain: [-0.1, 1.85],
      ticks: [0, 0.5, 1.0, 1.5],
      series: [{ values: data.nino3, color: COLORS.deep }],
    },
    {
      title: "c  Near-surface zonal-wind response",
      ylabel: "CWP u10 (m s⁻¹)",
      domain: [-2.1, 4.1],
      ticks: [-2, 0, 2, 4],
      gap: [data.u10.observed, data.u10.expected],
      series: [
        { values: data.u10.observed, color: COLORS.wind, label: "Observed" },
        {
          values: data.u10.expected,
          color: COLORS.expect,
          label: "SST-conditioned expectation",
          dashed: true,
          shape: "square",
        },
      ],
    },
    {
      title: "d  Deep-convective response",
      ylabel: "CP precip. (mm day⁻¹)",
      domain: [-2.6, 4.8],
      ticks: [-2, 0, 2, 4],
      gap: [data.precipitation.observed, data.precipitation.expected],
      series: [
        { values: data.precipitation.observed, color: COLORS.rain },
        {
          values: data.precipitation.expected,
          color: COLORS.expect,
          dashed: true,
          shape: "square",
        },
      ],
    },
  ];

  const stageBounds = [
    [0.8, 2.5],
    [2.5, 4.5],
    [4.5, 6.2],
  ];

  const elements = [];
  elements.push(`<rect width="${width}" height="${height}" fill="white"/>`);
  elements.push(
    `<text x="${width / 2}" y="45" text-anchor="middle" class="main-title">${esc(meta.title)}</text>`,
  );

  meta.stages.forEach(([period, label, fill], index) => {
    const [left, right] = stageBounds[index];
    const center = (xScale(left) + xScale(right)) / 2;
    const labelWidth = Math.min(365, Math.max(180, label.length * 6.7));
    elements.push(
      `<text x="${center}" y="82" text-anchor="middle" class="stage-period">${esc(period)}</text>`,
      `<rect x="${center - labelWidth / 2}" y="94" width="${labelWidth}" height="22" rx="3" fill="${fill}"/>`,
      `<text x="${center}" y="109" text-anchor="middle" class="stage-label">${esc(label)}</text>`,
    );
  });

  panelSpecs.forEach((panel, panelIndex) => {
    const top = panelTops[panelIndex];
    const bottom = top + panelHeight;
    const [yMin, yMax] = panel.domain;
    const yScale = (value) =>
      bottom - ((value - yMin) / (yMax - yMin)) * panelHeight;

    elements.push(`<rect x="${plotLeft}" y="${top}" width="${plotWidth}" height="${panelHeight}" fill="${COLORS.panel}"/>`);

    meta.stages.forEach((stage, stageIndex) => {
      const [left, right] = stageBounds[stageIndex];
      elements.push(
        `<rect x="${xScale(left)}" y="${top}" width="${xScale(right) - xScale(left)}" height="${panelHeight}" fill="${stage[2]}"/>`,
      );
    });

    for (let month = 1; month <= 6; month += 1) {
      const x = xScale(month);
      elements.push(
        `<line x1="${x}" y1="${top}" x2="${x}" y2="${bottom}" stroke="${COLORS.grid}" stroke-width="0.7"/>`,
      );
    }

    panel.ticks.forEach((tick) => {
      const y = yScale(tick);
      elements.push(
        `<line x1="${plotLeft}" y1="${y}" x2="${plotRight}" y2="${y}" stroke="${COLORS.grid}" stroke-width="0.75"/>`,
        `<text x="${plotLeft - 12}" y="${y + 4}" text-anchor="end" class="tick">${esc(tick)}</text>`,
      );
    });

    [2.5, 4.5].forEach((boundary) => {
      const x = xScale(boundary);
      elements.push(
        `<line x1="${x}" y1="${top}" x2="${x}" y2="${bottom}" stroke="#9AA4AD" stroke-width="1" stroke-dasharray="4 4"/>`,
      );
    });

    if (yMin <= 0 && yMax >= 0) {
      const zeroY = yScale(0);
      elements.push(
        `<line x1="${plotLeft}" y1="${zeroY}" x2="${plotRight}" y2="${zeroY}" stroke="${COLORS.zero}" stroke-width="1.05"/>`,
      );
    }

    elements.push(
      `<line x1="${plotLeft}" y1="${top}" x2="${plotLeft}" y2="${bottom}" stroke="#7A858F" stroke-width="1"/>`,
      `<line x1="${plotLeft}" y1="${bottom}" x2="${plotRight}" y2="${bottom}" stroke="#7A858F" stroke-width="1"/>`,
      `<text x="${plotLeft}" y="${top - 10}" class="panel-title">${esc(panel.title)}</text>`,
      `<text x="32" y="${top + panelHeight / 2}" text-anchor="middle" class="axis-label" transform="rotate(-90 32 ${top + panelHeight / 2})">${esc(panel.ylabel)}</text>`,
    );

    if (panel.gap) {
      elements.push(
        `<path d="${areaPath(panel.gap[0], panel.gap[1], xScale, yScale)}" fill="${COLORS.gap}" fill-opacity="0.9"/>`,
      );
    }

    panel.series.forEach((series) => {
      elements.push(
        `<path d="${linePath(series.values, xScale, yScale)}" fill="none" stroke="${series.color}" stroke-width="${series.dashed ? 2.2 : 2.8}" ${series.dashed ? 'stroke-dasharray="8 5"' : ""} stroke-linejoin="round" stroke-linecap="round"/>`,
        markerSet(series.values, xScale, yScale, series.color, series.shape),
      );
    });

    if (panelIndex === 0) {
      elements.push(
        `<line x1="${plotLeft + 18}" y1="${bottom - 15}" x2="${plotLeft + 48}" y2="${bottom - 15}" stroke="${COLORS.shoal}" stroke-width="2.8"/>`,
        `<circle cx="${plotLeft + 33}" cy="${bottom - 15}" r="3.7" fill="${COLORS.shoal}"/>`,
        `<text x="${plotLeft + 56}" y="${bottom - 11}" class="legend">Western D20</text>`,
        `<line x1="${plotLeft + 170}" y1="${bottom - 15}" x2="${plotLeft + 200}" y2="${bottom - 15}" stroke="${COLORS.deep}" stroke-width="2.8"/>`,
        `<circle cx="${plotLeft + 185}" cy="${bottom - 15}" r="3.7" fill="${COLORS.deep}"/>`,
        `<text x="${plotLeft + 208}" y="${bottom - 11}" class="legend">Eastern D20</text>`,
      );
    }

    if (panelIndex === 2) {
      elements.push(
        `<line x1="${plotLeft + 18}" y1="${top + 18}" x2="${plotLeft + 48}" y2="${top + 18}" stroke="${COLORS.wind}" stroke-width="2.8"/>`,
        `<circle cx="${plotLeft + 33}" cy="${top + 18}" r="3.7" fill="${COLORS.wind}"/>`,
        `<text x="${plotLeft + 56}" y="${top + 22}" class="legend">Observed</text>`,
        `<line x1="${plotLeft + 142}" y1="${top + 18}" x2="${plotLeft + 176}" y2="${top + 18}" stroke="${COLORS.expect}" stroke-width="2.2" stroke-dasharray="8 5"/>`,
        `<rect x="${plotLeft + 155.8}" y="${top + 14.8}" width="6.4" height="6.4" fill="${COLORS.expect}"/>`,
        `<text x="${plotLeft + 185}" y="${top + 22}" class="legend">SST-conditioned expectation</text>`,
      );
    }

    if (panelIndex === panelSpecs.length - 1) {
      months.forEach((label, index) => {
        const x = xScale(index + 1);
        elements.push(
          `<line x1="${x}" y1="${bottom}" x2="${x}" y2="${bottom + 5}" stroke="#7A858F" stroke-width="1"/>`,
          `<text x="${x}" y="${bottom + 22}" text-anchor="middle" class="tick">${label}</text>`,
        );
      });
      elements.push(
        `<text x="${(plotLeft + plotRight) / 2}" y="${bottom + 43}" text-anchor="middle" class="axis-label">${year} calendar month</text>`,
      );
    }
  });

  elements.push(
    `<text x="${plotLeft}" y="704" class="footnote">All variables retain physical units. Stage bands summarize the observed sequence and are not formal regime indices. SST-conditioned expectations use the 1982-2014 calendar-month regressions.</text>`,
  );

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <style>
    text { font-family: Arial, Helvetica, sans-serif; fill: ${COLORS.ink}; }
    .main-title { font-size: 20px; font-weight: 700; }
    .stage-period { font-size: 11px; font-weight: 700; fill: ${COLORS.muted}; }
    .stage-label { font-size: 11.5px; }
    .panel-title { font-size: 15px; font-weight: 700; }
    .axis-label { font-size: 12.5px; }
    .tick { font-size: 11px; fill: ${COLORS.ink}; }
    .legend { font-size: 10.5px; }
    .footnote { font-size: 10.5px; fill: ${COLORS.muted}; }
  </style>
  ${elements.join("\n  ")}
</svg>`;
}

async function writePdf(year) {
  const data = extractData(year);
  const svg = buildSvg(year, data);
  const png = await sharp(Buffer.from(svg))
    .resize({ width: 4800, height: 2600, fit: "fill" })
    .png({ compressionLevel: 9 })
    .toBuffer();

  const pdf = await PDFDocument.create();
  const image = await pdf.embedPng(png);
  const page = pdf.addPage([960, 520]);
  page.drawImage(image, { x: 0, y: 0, width: 960, height: 520 });
  pdf.setTitle(EVENT_META[year].title);
  pdf.setSubject("January-June ENSO air-sea coupling sequence");
  pdf.setCreator("Codex climate plotting workflow");

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const output = path.join(OUT_DIR, `fig11_${year}_coupling_sequence_polished.pdf`);
  fs.writeFileSync(output, await pdf.save());
  return output;
}

async function main() {
  for (const year of [2015, 2023]) {
    const output = await writePdf(year);
    process.stdout.write(`${output}\n`);
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
