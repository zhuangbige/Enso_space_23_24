import fs from "node:fs/promises";

const ROOT = "/Users/daiyue/Documents/Maryland";
const DATA = `${ROOT}/data/derived/research_2026`;
const OUT = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_reviewer_revision_CHOJ3S";

function parseCsvLine(line) {
  const fields = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (quoted && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      fields.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  fields.push(current);
  return fields;
}

async function readCsv(path) {
  const lines = (await fs.readFile(path, "utf8")).trim().split(/\r?\n/);
  const header = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return Object.fromEntries(header.map((name, index) => [name, values[index]]));
  });
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function quantile(sorted, probability) {
  const index = (sorted.length - 1) * probability;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] * (upper - index) + sorted[upper] * (index - lower);
}

function combinations(values, choose) {
  const result = [];
  function visit(start, current) {
    if (current.length === choose) {
      result.push([...current]);
      return;
    }
    for (let index = start; index <= values.length - (choose - current.length); index += 1) {
      current.push(values[index]);
      visit(index + 1, current);
      current.pop();
    }
  }
  visit(0, []);
  return result;
}

function mulberry32(seed) {
  return () => {
    let value = (seed += 0x6d2b79f5);
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function bootstrapDifference(ct, cp, samples = 200000) {
  const random = mulberry32(20260810);
  const differences = new Array(samples);
  for (let sample = 0; sample < samples; sample += 1) {
    let ctSum = 0;
    let cpSum = 0;
    for (let i = 0; i < ct.length; i += 1) ctSum += ct[Math.floor(random() * ct.length)];
    for (let i = 0; i < cp.length; i += 1) cpSum += cp[Math.floor(random() * cp.length)];
    differences[sample] = ctSum / ct.length - cpSum / cp.length;
  }
  differences.sort((a, b) => a - b);
  return [quantile(differences, 0.025), quantile(differences, 0.975)];
}

function exactPermutationP(ct, cp) {
  const pooled = [...ct, ...cp];
  const observed = Math.abs(mean(ct) - mean(cp));
  const indices = [...pooled.keys()];
  const assignments = combinations(indices, ct.length);
  let extreme = 0;
  for (const assignment of assignments) {
    const selected = new Set(assignment);
    const groupA = pooled.filter((_, index) => selected.has(index));
    const groupB = pooled.filter((_, index) => !selected.has(index));
    if (Math.abs(mean(groupA) - mean(groupB)) >= observed - 1e-12) extreme += 1;
  }
  return extreme / assignments.length;
}

function transpose(matrix) {
  return matrix[0].map((_, column) => matrix.map((row) => row[column]));
}

function multiplyMatrices(a, b) {
  return a.map((row) => b[0].map((_, column) => row.reduce((sum, value, index) => sum + value * b[index][column], 0)));
}

function invert(matrix) {
  const n = matrix.length;
  const augmented = matrix.map((row, index) => [
    ...row,
    ...Array.from({ length: n }, (_, column) => (column === index ? 1 : 0)),
  ]);
  for (let column = 0; column < n; column += 1) {
    let pivot = column;
    for (let row = column + 1; row < n; row += 1) {
      if (Math.abs(augmented[row][column]) > Math.abs(augmented[pivot][column])) pivot = row;
    }
    [augmented[column], augmented[pivot]] = [augmented[pivot], augmented[column]];
    const divisor = augmented[column][column];
    if (Math.abs(divisor) < 1e-12) throw new Error("Singular matrix");
    for (let j = 0; j < 2 * n; j += 1) augmented[column][j] /= divisor;
    for (let row = 0; row < n; row += 1) {
      if (row === column) continue;
      const factor = augmented[row][column];
      for (let j = 0; j < 2 * n; j += 1) augmented[row][j] -= factor * augmented[column][j];
    }
  }
  return augmented.map((row) => row.slice(n));
}

function ols(y, x) {
  const xt = transpose(x);
  const xtxInv = invert(multiplyMatrices(xt, x));
  const xty = multiplyMatrices(xt, y.map((value) => [value]));
  const beta = multiplyMatrices(xtxInv, xty).map((row) => row[0]);
  const fitted = x.map((row) => row.reduce((sum, value, index) => sum + value * beta[index], 0));
  const residuals = y.map((value, index) => value - fitted[index]);
  const hat = x.map((row) => {
    const left = multiplyMatrices([row], xtxInv)[0];
    return left.reduce((sum, value, index) => sum + value * row[index], 0);
  });
  return { beta, fitted, residuals, hat, xtxInv };
}

function residualize(values, controls) {
  const x = values.map((_, index) => [1, ...controls.map((column) => column[index])]);
  return ols(values, x).residuals;
}

function correlation(a, b) {
  const meanA = mean(a);
  const meanB = mean(b);
  let numerator = 0;
  let sumA = 0;
  let sumB = 0;
  for (let i = 0; i < a.length; i += 1) {
    const da = a[i] - meanA;
    const db = b[i] - meanB;
    numerator += da * db;
    sumA += da * da;
    sumB += db * db;
  }
  return numerator / Math.sqrt(sumA * sumB);
}

function ranks(values) {
  const order = values.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
  const output = new Array(values.length);
  let start = 0;
  while (start < order.length) {
    let end = start;
    while (end + 1 < order.length && order[end + 1].value === order[start].value) end += 1;
    const rank = (start + end) / 2 + 1;
    for (let i = start; i <= end; i += 1) output[order[i].index] = rank;
    start = end + 1;
  }
  return output;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return quantile(sorted, 0.5);
}

function theilSenSlope(x, y) {
  const slopes = [];
  for (let i = 0; i < x.length; i += 1) {
    for (let j = i + 1; j < x.length; j += 1) {
      if (x[j] !== x[i]) slopes.push((y[j] - y[i]) / (x[j] - x[i]));
    }
  }
  return median(slopes);
}

function bhAdjusted(pValues) {
  const indexed = pValues.map((p, index) => ({ p, index })).sort((a, b) => a.p - b.p);
  const adjustedSorted = new Array(indexed.length);
  let running = 1;
  for (let rank = indexed.length; rank >= 1; rank -= 1) {
    running = Math.min(running, (indexed[rank - 1].p * indexed.length) / rank);
    adjustedSorted[rank - 1] = running;
  }
  const output = new Array(indexed.length);
  indexed.forEach((entry, rank) => { output[entry.index] = adjustedSorted[rank]; });
  return output;
}

function csvEscape(value) {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

async function writeCsv(path, rows) {
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const body = [columns.join(","), ...rows.map((row) => columns.map((column) => csvEscape(row[column])).join(","))].join("\n");
  await fs.writeFile(path, `${body}\n`);
}

const cumulative = await readCsv(`${DATA}/soda3_three_box_warm_heat_fate_cumulative_events.csv`);
const phaseRows = cumulative.filter((row) => row.phase === "development_Jun0_to_Nov0");
const eventClasses = ["CT", "CP"];
const eventYears = {
  CT: [1982, 1986, 1997, 2006],
  CP: [1991, 1994, 2002, 2004],
};
const arrivalByEvent = [];
for (const eventClass of eventClasses) {
  for (const eventYear of eventYears[eventClass]) {
    const arrival = phaseRows.find((row) => row.event_class === eventClass && Number(row.event_year) === eventYear && row.box === "gate" && row.component === "q20_220e_10s5n");
    const storage = phaseRows.find((row) => row.event_class === eventClass && Number(row.event_year) === eventYear && row.box === "east" && row.component === "storage_tendency");
    if (!arrival || !storage) throw new Error(`Missing event budget row for ${eventClass} ${eventYear}`);
    arrivalByEvent.push({
      event_class: eventClass,
      event_year: eventYear,
      q140_east_zj: Number(arrival.cumulative_zj),
      east_h20_growth_zj: Number(storage.cumulative_zj),
    });
  }
}

const ctArrival = arrivalByEvent.filter((row) => row.event_class === "CT").map((row) => row.q140_east_zj);
const cpArrival = arrivalByEvent.filter((row) => row.event_class === "CP").map((row) => row.q140_east_zj);
const ctStorage = arrivalByEvent.filter((row) => row.event_class === "CT").map((row) => row.east_h20_growth_zj);
const cpStorage = arrivalByEvent.filter((row) => row.event_class === "CP").map((row) => row.east_h20_growth_zj);

function summarizeMetric(metric, ct, cp) {
  const [ciLow, ciHigh] = bootstrapDifference(ct, cp);
  const observed = mean(ct) - mean(cp);
  const differences = [];
  for (let index = 0; index < ct.length; index += 1) differences.push(mean(ct.filter((_, i) => i !== index)) - mean(cp));
  for (let index = 0; index < cp.length; index += 1) differences.push(mean(ct) - mean(cp.filter((_, i) => i !== index)));
  return {
    metric,
    ct_mean: mean(ct),
    cp_mean: mean(cp),
    ct_minus_cp: observed,
    bootstrap_ci_low: ciLow,
    bootstrap_ci_high: ciHigh,
    exact_permutation_p: exactPermutationP(ct, cp),
    leave_one_event_difference_min: Math.min(...differences),
    leave_one_event_difference_max: Math.max(...differences),
  };
}

const arrivalSummary = summarizeMetric("q140_east_zj", ctArrival, cpArrival);
const storageSummary = summarizeMetric("east_h20_growth_zj", ctStorage, cpStorage);
const ctNo1997 = arrivalByEvent.filter((row) => row.event_class === "CT" && row.event_year !== 1997);
const robustnessRows = [
  ...arrivalByEvent.map((row) => ({ row_type: "event", metric: "q140_east_zj", ...row })),
  ...arrivalByEvent.map((row) => ({ row_type: "event", metric: "east_h20_growth_zj", ...row })),
  { row_type: "summary", ...arrivalSummary },
  { row_type: "summary", ...storageSummary },
  {
    row_type: "sensitivity",
    metric: "q140_east_zj_without_1997",
    ct_mean: mean(ctNo1997.map((row) => row.q140_east_zj)),
    cp_mean: mean(cpArrival),
    ct_minus_cp: mean(ctNo1997.map((row) => row.q140_east_zj)) - mean(cpArrival),
    ratio: mean(ctNo1997.map((row) => row.q140_east_zj)) / mean(cpArrival),
  },
  {
    row_type: "sensitivity",
    metric: "east_h20_growth_zj_without_1997",
    ct_mean: mean(ctNo1997.map((row) => row.east_h20_growth_zj)),
    cp_mean: mean(cpStorage),
    ct_minus_cp: mean(ctNo1997.map((row) => row.east_h20_growth_zj)) - mean(cpStorage),
    ratio: mean(ctNo1997.map((row) => row.east_h20_growth_zj)) / mean(cpStorage),
  },
];
await writeCsv(`${OUT}/review_ct_cp_arrival_robustness.csv`, robustnessRows);

const partition = await readCsv(`${DATA}/d20_partition_direction_event_table.csv`);
const years = partition.map((row) => Number(row.year));
const x = partition.map((row) => Number(row.partition_jan_to_m4_z));
const y = partition.map((row) => Number(row.tau_response_mjj));
const controls = [
  partition.map((row) => Number(row.d20_jf_z)),
  partition.map((row) => Number(row.partition_jan_to_m2_z)),
  partition.map((row) => Number(row.q140_mar_apr_z)),
];
const xResidual = residualize(x, controls);
const yResidual = residualize(y, controls);
const partialR = correlation(xResidual, yResidual);
const partialSpearman = correlation(ranks(xResidual), ranks(yResidual));
const fullDesign = years.map((_, index) => [1, x[index], ...controls.map((column) => column[index])]);
const fit = ols(y, fullDesign);
const p = fullDesign[0].length;
const mse = fit.residuals.reduce((sum, value) => sum + value * value, 0) / (years.length - p);
const cooks = fit.residuals.map((residual, index) => ((residual * residual) / (p * mse)) * (fit.hat[index] / ((1 - fit.hat[index]) ** 2)));
const influence = years.map((year, index) => ({ year, cooks_d: cooks[index], leverage: fit.hat[index], residual: fit.residuals[index] })).sort((a, b) => b.cooks_d - a.cooks_d);

const d20Relationships = await readCsv(`${DATA}/d20_partition_direction_relationships.csv`);
const pValues = d20Relationships.map((row) => Number(row.permutation_p));
const qValues = bhAdjusted(pValues);
const primaryIndex = d20Relationships.findIndex((row) => row.test_id === "partition_apr_to_tau_after_early_d20_arrival");
const primary = d20Relationships[primaryIndex];
const q3Rows = [
  {
    row_type: "primary",
    test_id: primary.test_id,
    n_events: years.length,
    partial_r_recomputed: partialR,
    partial_spearman_recomputed: partialSpearman,
    permutation_p: Number(primary.permutation_p),
    bootstrap_ci_low: Number(primary.bootstrap_ci_low),
    bootstrap_ci_high: Number(primary.bootstrap_ci_high),
    loeo_r_min: Number(primary.loeo_r_min),
    loeo_r_max: Number(primary.loeo_r_max),
    bh_fdr_q_across_d20_family: qValues[primaryIndex],
    theil_sen_slope_partial_residuals: theilSenSlope(xResidual, yResidual),
    cooks_threshold_4_over_n: 4 / years.length,
    max_cooks_year: influence[0].year,
    max_cooks_d: influence[0].cooks_d,
    n_cooks_above_4_over_n: influence.filter((row) => row.cooks_d > 4 / years.length).length,
  },
  ...influence.map((row) => {
    const index = years.indexOf(row.year);
    return {
      row_type: "influence",
      ...row,
      partition_residual_x: xResidual[index],
      wind_residual_y: yResidual[index],
      highlight: [1997, 2015, 2023].includes(row.year),
    };
  }),
];
await writeCsv(`${OUT}/review_partition_robustness.csv`, q3Rows);

const report = [
  "CT/CP arrival robustness",
  JSON.stringify(arrivalSummary, null, 2),
  JSON.stringify(storageSummary, null, 2),
  `Without 1997: Q140 CT=${mean(ctNo1997.map((row) => row.q140_east_zj)).toFixed(3)} CP=${mean(cpArrival).toFixed(3)} ratio=${(mean(ctNo1997.map((row) => row.q140_east_zj)) / mean(cpArrival)).toFixed(3)}`,
  `Without 1997: storage CT=${mean(ctNo1997.map((row) => row.east_h20_growth_zj)).toFixed(3)} CP=${mean(cpStorage).toFixed(3)} ratio=${(mean(ctNo1997.map((row) => row.east_h20_growth_zj)) / mean(cpStorage)).toFixed(3)}`,
  "",
  "Q3 robustness",
  JSON.stringify(q3Rows[0], null, 2),
  "Top Cook's D events",
  JSON.stringify(influence.slice(0, 5), null, 2),
].join("\n");
await fs.writeFile(`${OUT}/reviewer_reanalysis.txt`, `${report}\n`);
console.log(report);
