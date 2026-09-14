import fs from "node:fs/promises";

const root = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_simplified_verified_20260811";
const inspectPath = `${root}/source-full-inspect.ndjson`;
const outputPath = `${root}/template-frame-map.json`;
const sequence = [1, 2, 10, 11, 12, 13, 14, 15, 16, 19, 20, 19, 20, 32, 9];
const roles = [
  "opening thesis",
  "three-paper inspiration",
  "three research questions and windows",
  "Q1 Hovmoller formula",
  "Q1 Hovmoller result",
  "Q1 trajectory formula",
  "Q1 trajectory result",
  "Q1 arrival formula",
  "Q1 arrival result",
  "Q2 budget formula",
  "Q2 partition result",
  "Q3 partial-correlation formula",
  "Q3 independent-constraints result",
  "three-question synthesis",
  "backup data and windows",
];

const records = (await fs.readFile(inspectPath, "utf8"))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((line) => JSON.parse(line));

const outputSlides = sequence.map((sourceSlide, index) => {
  const textIds = records
    .filter((record) => record.slide === sourceSlide && record.kind === "textbox" && record.id)
    .map((record) => record.id);
  const imageIds = records
    .filter((record) => record.slide === sourceSlide && record.kind === "image" && record.id)
    .map((record) => record.id);
  const editTargets = [];
  if (textIds.length) editTargets.push({ action: "rewrite", sourceElementIds: textIds });
  if (imageIds.length) editTargets.push({ action: "replace", sourceElementIds: imageIds });
  return {
    outputSlide: index + 1,
    sourceSlide,
    narrativeRole: roles[index],
    reuseMode: "duplicate-slide",
    editTargets,
  };
});

const used = new Set(sequence);
const omittedSourceSlides = Array.from({ length: 32 }, (_, index) => index + 1)
  .filter((slide) => !used.has(slide))
  .map((sourceSlide) => ({
    sourceSlide,
    reason: "redundant literature detail, robustness detail, repeated summary, or superseded figure",
  }));

await fs.writeFile(outputPath, JSON.stringify({ outputSlides, omittedSourceSlides }, null, 2), "utf8");
console.log(outputPath);
