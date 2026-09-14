import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

process.on("uncaughtException", (error) => {
  console.error("BUILD_ERROR", error?.message ?? String(error));
  console.error(error?.stack ?? "");
  process.exit(1);
});
process.on("unhandledRejection", (error) => {
  console.error("BUILD_REJECTION", error?.message ?? String(error));
  console.error(error?.stack ?? "");
  process.exit(1);
});

const starter = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_third_question_20260809/template-starter.pptx";
const output = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与去向_第三问补全版_20260809.pptx";
const eventCsv = "/Users/daiyue/Documents/Maryland/data/derived/research_2026/d20_partition_direction_event_table.csv";

const presentation = await PresentationFile.importPptx(await FileBlob.load(starter));

function setText(id, value) {
  presentation.resolve(id).text = value;
}

function setNotes(slideIndex, lines) {
  const slide = presentation.slides.getItem(slideIndex);
  slide.speakerNotes.textFrame.setText(["[Sources]", ...lines.map((line) => `- ${line}`), "[/Sources]"].join("\n"));
  slide.speakerNotes.setVisible(true);
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    return Object.fromEntries(header.map((name, index) => [name, values[index]]));
  });
}

function solveLinear(matrix, vector) {
  const n = vector.length;
  const aug = matrix.map((row, i) => [...row, vector[i]]);
  for (let col = 0; col < n; col += 1) {
    let pivot = col;
    for (let row = col + 1; row < n; row += 1) {
      if (Math.abs(aug[row][col]) > Math.abs(aug[pivot][col])) pivot = row;
    }
    [aug[col], aug[pivot]] = [aug[pivot], aug[col]];
    const divisor = aug[col][col];
    if (Math.abs(divisor) < 1e-12) throw new Error("Singular regression design");
    for (let j = col; j <= n; j += 1) aug[col][j] /= divisor;
    for (let row = 0; row < n; row += 1) {
      if (row === col) continue;
      const factor = aug[row][col];
      for (let j = col; j <= n; j += 1) aug[row][j] -= factor * aug[col][j];
    }
  }
  return aug.map((row) => row[n]);
}

function residualize(values, controls) {
  const design = values.map((_, i) => [1, ...controls.map((column) => column[i])]);
  const p = design[0].length;
  const xtx = Array.from({ length: p }, () => Array(p).fill(0));
  const xty = Array(p).fill(0);
  for (let i = 0; i < design.length; i += 1) {
    for (let a = 0; a < p; a += 1) {
      xty[a] += design[i][a] * values[i];
      for (let b = 0; b < p; b += 1) xtx[a][b] += design[i][a] * design[i][b];
    }
  }
  const beta = solveLinear(xtx, xty);
  return values.map((value, i) => value - design[i].reduce((sum, current, j) => sum + current * beta[j], 0));
}

const navy = "#0B2438";
const blue = "#2E7FB8";
const orange = "#E47D00";
const red = "#C83C3C";
const gray = "#9B9B9B";
const grid = "#D8E0E6";
const font = "PingFang SC";

// Cover: include Q3 in the deck-level narrative.
setText("sh/7qp4be9c", "问题一：暖量到达？　问题二：暖量去向？　问题三：空间分配如何关联海气接通？");
setText("sh/65g3298r", "回答：到达不等于接通；2023不是缺热，而是暖量更宽、相对偏北，并关联较弱海气响应。");
setNotes(0, [
  "Local SODA3.15.2 warm-heat arrival and receiver-box analyses retained from the source deck.",
  "Added Q3 synthesis uses data/derived/research_2026/warm_heat_partition_coupling_event_table.csv and d20_partition_direction_relationships.csv.",
]);

// Slide 17: frame Q3 without adding a future-research agenda.
setText("sh/4by9or6l", "问题三");
setText("sh/1c7e50ni", "暖量已经到达，2023为何仍未形成\n1997/2015式海气接通？");
setText("sh/rm5czq50", "已排除：暖量没有进入东太平洋");
setText("sh/6lwvql4v", "已排除：赤道缺热——Jan–Apr赤道箱仍增加 +3.04 ZJ");
setText("sh/t8ne10n6", "关键对象：给定总暖量后的赤道—北侧空间分配");
setText("sh/snedsvml", "表述：比较海气接通效率，而不是二元化的“耦合/脱耦”。");
setText("sh/ihcvml4j", "到达  →  分配  →  海气接通  →  后期路由");
setNotes(16, [
  "data/derived/research_2026/warm_heat_partition_coupling_event_table.csv",
  "scripts/analyze_warm_heat_partition_coupling.py",
]);

// Slide 18: event partition evidence.
setText("sh/7mpknmp0", "问题三");
setText("sh/wrelszu9", "2023赤道不缺热，异常在于暖量分布更宽、更偏北");
setText("sh/itw3upcf", "Jan→Apr · 140°W—80°W · 赤道5°S—5°N / 北侧5°—12°N");
setText("sh/5gnmp4bq", "分配残差 P_H");
setText("sh/6hw3y9sb", "1997 / 2015 / 2023\n−0.76 / −0.57 / +0.47 ZJ");
setText("sh/fapkr6pw", "2023 Jan→Apr");
setText("sh/upg3i18r", "赤道  +3.04 ZJ\n北侧  +0.86 ZJ");
setText("sh/gbylkbqh", "2023不是赤道缺热，而是同样总暖量下北侧份额显著偏高。");
presentation.slides.getItem(17).charts.deleteById(presentation.resolve("ch/q9cnmpcj").id);
presentation.slides.getItem(17).charts.add("bar", {
  position: { left: 54, top: 178, width: 820, height: 426 },
  categories: ["1997", "2015", "2023"],
  series: [
    { name: "赤道箱 ΔH₂₀", values: [4.75, 2.89, 3.04], fill: blue, line: { style: "solid", fill: blue, width: 1 } },
    { name: "北侧箱 ΔH₂₀", values: [-0.34, -0.26, 0.86], fill: orange, line: { style: "solid", fill: orange, width: 1 } },
  ],
  barOptions: { direction: "column", grouping: "clustered", gapWidth: 72 },
  hasLegend: true,
  legend: { position: "bottom", overlay: false, textStyle: { fontFamily: font, fontSize: 14, fill: navy } },
  xAxis: { textStyle: { fontFamily: font, fontSize: 15, bold: true, fill: navy }, line: { style: "solid", fill: navy, width: 1 } },
  yAxis: { title: { text: "Jan→Apr ΔH₂₀（ZJ）", textStyle: { fontFamily: font, fontSize: 14, fill: navy } }, min: -1, max: 5.5, majorUnit: 1, textStyle: { fontFamily: font, fontSize: 13, fill: navy }, majorGridlines: { style: "solid", fill: grid, width: 1 } },
  dataLabels: { showValue: true, position: "outEnd", textStyle: { fontFamily: font, fontSize: 13, bold: true, fill: navy } },
  chartFill: "#FFFFFF",
  chartLine: { style: "solid", fill: "#FFFFFF", width: 0 },
  plotAreaFill: "#FFFFFF",
  plotAreaLine: { style: "solid", fill: "#FFFFFF", width: 0 },
});
setNotes(17, [
  "data/derived/research_2026/warm_heat_partition_coupling_event_table.csv",
  "outputs/research_2026/warm_heat_partition_coupling/WARM_HEAT_PARTITION_COUPLING_CN.md",
  "P_H is the north-box H20 residual after holding equatorial+northern total H20 change fixed.",
]);

// Slide 19: fully controlled partition–wind relationship.
const rows = parseCsv(await fs.readFile(eventCsv, "utf8"));
const years = rows.map((row) => Number(row.year));
const xRaw = rows.map((row) => Number(row.partition_jan_to_m4_z));
const yRaw = rows.map((row) => Number(row.tau_response_mjj));
const controls = [
  rows.map((row) => Number(row.d20_jf_z)),
  rows.map((row) => Number(row.partition_jan_to_m2_z)),
  rows.map((row) => Number(row.q140_mar_apr_z)),
];
const xResidual = residualize(xRaw, controls);
const yResidual = residualize(yRaw, controls);

setText("sh/0vi1k7qx", "问题三");
setText("sh/9gb6xgbi", "偏北分配越强，后续中太平洋风应力响应越弱");
setText("sh/vitozqt8", "13个暖事件 · Jan–Apr海洋配置领先MJJ大气响应");
setText("sh/wj2psvat", "控制变量");
setText("sh/jmd83atk", "早期D20与partition\n+ 140°W到达量");
setText("sh/cri1gnql", "完全控制后");
setText("sh/dsri9sr6", "r = −0.68\np_perm = 0.011");
setText("sh/rqp07290", "关系不是“总量更多”的替代信号；暖量配置保留了后续接通信息。");
presentation.slides.getItem(18).charts.deleteById(presentation.resolve("ch/pojm18ra").id);

const series = [{
  name: "其他事件",
  xValues: xResidual,
  values: yResidual,
  fill: gray,
  line: { style: "solid", fill: gray, width: 0 },
  marker: { symbol: "circle", size: 7 },
  trendlines: [{ type: "linear", name: "线性关系" }],
}];
const highlightColors = { 1997: "#202020", 2015: blue, 2023: red };
for (const year of [1997, 2015, 2023]) {
  const index = years.indexOf(year);
  series.push({
    name: String(year),
    xValues: [xResidual[index]],
    values: [yResidual[index]],
    fill: highlightColors[year],
    line: { style: "solid", fill: highlightColors[year], width: 0 },
    marker: { symbol: "circle", size: 10 },
    dataLabelOverrides: [{ idx: 0, text: String(year), position: "right", textStyle: { fontFamily: font, fontSize: 13, bold: true, fill: highlightColors[year] } }],
  });
}
presentation.slides.getItem(18).charts.add("scatter", {
  position: { left: 54, top: 178, width: 820, height: 426 },
  series,
  scatterOptions: { style: "marker", varyColors: false },
  hasLegend: false,
  xAxis: { title: { text: "偏北分配残差（控制后）", textStyle: { fontFamily: font, fontSize: 14, fill: navy } }, min: -1.6, max: 1.2, majorUnit: 0.5, textStyle: { fontFamily: font, fontSize: 12, fill: navy }, line: { style: "solid", fill: navy, width: 1 }, majorGridlines: { style: "solid", fill: grid, width: 1 } },
  yAxis: { title: { text: "MJJ风应力响应残差", textStyle: { fontFamily: font, fontSize: 14, fill: navy } }, min: -1.4, max: 1.7, majorUnit: 0.5, textStyle: { fontFamily: font, fontSize: 12, fill: navy }, line: { style: "solid", fill: navy, width: 1 }, majorGridlines: { style: "solid", fill: grid, width: 1 } },
  chartFill: "#FFFFFF",
  chartLine: { style: "solid", fill: "#FFFFFF", width: 0 },
  plotAreaFill: "#FFFFFF",
  plotAreaLine: { style: "solid", fill: "#FFFFFF", width: 0 },
});
setNotes(18, [
  "data/derived/research_2026/d20_partition_direction_event_table.csv",
  "data/derived/research_2026/d20_partition_direction_relationships.csv (partition_apr_to_tau_after_early_d20_arrival)",
  "scripts/analyze_d20_partition_direction.py",
]);

// Slide 20: adjacent-window consistency.
setText("sh/pwvmlkzm", "问题三");
setText("sh/qpwjmh8n", "相邻领先窗口连续同号，春季配置影响随后逐步衰减");
setText("sh/4nu1krqh", "分配窗口与大气窗口依次向后平移；均为13个暖事件");
setText("sh/3ml0rmpw", "领先窗口");
setText("sh/gjuhg7ql", "Jan–Mar / Jan–Apr / Jan–May\n→ AMJ / MJJ / JJA");
setText("sh/dkfmp4zy", "偏相关 r");
setText("sh/cj65wzyd", "−0.68 / −0.57\n/ −0.52");
setText("sh/qh4nupg7", "三个相邻窗口连续同号，不是依赖单一窗口选择的结果。");
presentation.slides.getItem(19).charts.deleteById(presentation.resolve("ch/ozuxkze9").id);
presentation.slides.getItem(19).charts.add("bar", {
  position: { left: 54, top: 178, width: 820, height: 426 },
  categories: ["Jan–Mar → AMJ", "Jan–Apr → MJJ", "Jan–May → JJA"],
  series: [{ name: "偏相关 r", values: [-0.681, -0.565, -0.524], fill: blue, line: { style: "solid", fill: blue, width: 1 } }],
  barOptions: { direction: "bar", grouping: "clustered", gapWidth: 72 },
  hasLegend: false,
  xAxis: { title: { text: "暖量偏北分配与后续风响应的偏相关", textStyle: { fontFamily: font, fontSize: 14, fill: navy } }, min: -1, max: 0, majorUnit: 0.2, numberFormatCode: "0.0", textStyle: { fontFamily: font, fontSize: 12, fill: navy }, majorGridlines: { style: "solid", fill: grid, width: 1 }, line: { style: "solid", fill: navy, width: 1 } },
  yAxis: { textStyle: { fontFamily: font, fontSize: 14, bold: true, fill: navy }, line: { style: "solid", fill: navy, width: 1 } },
  dataLabels: { showValue: true, position: "outEnd", textStyle: { fontFamily: font, fontSize: 14, bold: true, fill: navy } },
  chartFill: "#FFFFFF",
  chartLine: { style: "solid", fill: "#FFFFFF", width: 0 },
  plotAreaFill: "#FFFFFF",
  plotAreaLine: { style: "solid", fill: "#FFFFFF", width: 0 },
});
setNotes(19, [
  "data/derived/research_2026/warm_heat_partition_coupling_lag_sensitivity.csv",
  "scripts/analyze_warm_heat_partition_coupling.py",
  "Permutation p-values: 0.009, 0.046, and 0.069 for the three adjacent windows.",
]);

// Slide 21: mechanism bridge and causal boundary.
setText("sh/2l0vypkn", "问题三");
setText("sh/1gbmxs7a", "对流—气压桥梁符合物理路径，但中介和因果尚未闭合");
setText("sh/ra9kryp8", "P_H（Jan–Apr）  →  降水–SLP（May–Jun）  →  τₓ（Jul–Aug）");
setText("sh/qp03yt8n", "路径方向一致");
setText("sh/dcb2t87y", "统计边界");
setText("sh/al43uxor", "路径 a\n−0.47");
setText("sh/4jax4nqd", "路径 b\n+0.78");
setText("sh/jy1gbi9s", "间接效应 ab = −0.37\n95% CI [−1.41, +0.29]");
setText("sh/wvax03q1", "跨零");
setText("sh/utsfyt8v", "加入桥梁后");
setText("sh/vu1w7y9g", "直接效应 −0.45 → −0.08\n与大气中介路径一致");
setText("sh/9sze58rq", "D20约束");
setText("sh/porutkje", "同期D20控制：r = −0.37，p = 0.213\nD20↔partition无稳定领先方向");
setText("sh/nm9cru18", "现有结果支持机制约束；不能写成“偏北分配直接导致2023弱接通”。");
setNotes(20, [
  "data/derived/research_2026/warm_heat_partition_coupling_mediation.csv",
  "data/derived/research_2026/d20_partition_direction_relationships.csv",
  "data/derived/research_2026/d20_partition_direction_mediation.csv",
  "scripts/analyze_warm_heat_partition_coupling.py and scripts/analyze_d20_partition_direction.py",
]);

// Slide 22: concise answer, no future-work section.
setText("sh/jmh8nyd0", "问题三的回答");
setText("sh/6987itcr", "2023不是缺热，\n而是暖量组织方式不同");
setText("sh/k7qpgjul", "排除：暖量没到、赤道缺热");
setText("sh/58zqpov6", "识别：总量强且赤道也强，但分布更宽、相对偏北");
setText("sh/il87etcv", "过程链：到达 → 分配 → 海气接通效率 → 后期路由｜证据层级：机制约束");
setNotes(21, [
  "Synthesis of slides 17–21 using the local SODA3 H20 partition and ERA5 coupling-response diagnostics.",
  "Primary tables: warm_heat_partition_coupling_event_table.csv, warm_heat_partition_coupling_lag_sensitivity.csv, d20_partition_direction_relationships.csv.",
]);

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(output);
