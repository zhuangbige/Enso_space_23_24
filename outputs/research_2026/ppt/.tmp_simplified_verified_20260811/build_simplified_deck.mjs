import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_simplified_verified_20260811");
const ASSETS = path.join(TMP, "assets");
const SOURCE = path.join(TMP, "template-starter.pptx");
const OUTPUT = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_精简核对版_20260811.pptx",
);
const PREVIEW = path.join(TMP, "final-preview");
const LAYOUT = path.join(TMP, "final-layout");
const MONTAGE = path.join(TMP, "final-montage.webp");

const FONT_CN = "PingFang SC";
const AUDIT = JSON.parse(await fs.readFile(path.join(ASSETS, "data-audit.json"), "utf8"));

const FORMULA = {
  eyebrow: "chakravorty-formula-data-text-22",
  title: "chakravorty-formula-data-text-23",
  subtitle: "chakravorty-formula-data-text-25",
  card1Title: "chakravorty-formula-data-text-27",
  formula1Base: "chakravorty-formula-data-text-28",
  formula1Sub: "chakravorty-formula-data-text-29",
  formula1Rest: "chakravorty-formula-data-text-30",
  formula2Base: "chakravorty-formula-data-text-31",
  formula2Sub: "chakravorty-formula-data-text-32",
  formula2Rest: "chakravorty-formula-data-text-33",
  card1Body: "chakravorty-formula-data-text-34",
  card2Title: "chakravorty-formula-data-text-36",
  card2Body: "chakravorty-formula-data-text-37",
  card3Title: "chakravorty-formula-data-text-39",
  card3Body: "chakravorty-formula-data-text-40",
  strip: "chakravorty-formula-data-text-42",
  takeaway: "chakravorty-formula-data-text-44",
};

function shapeByName(slide, name, required = true) {
  const item = slide.shapes.items.find((shape) => shape.name === name);
  if (!item && required) throw new Error(`Slide ${slide.index + 1}: missing shape ${name}`);
  return item;
}

function setText(slide, name, text, style = null) {
  const shape = shapeByName(slide, name);
  shape.text = text;
  if (style) shape.text.style = { ...shape.text.style, ...style };
}

function deleteShape(slide, name) {
  const shape = shapeByName(slide, name, false);
  if (shape) shape.delete();
}

function setNotes(slide, sources) {
  slide.speakerNotes.clear();
  slide.speakerNotes.text = `[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}\n[/Sources]`;
}

function applyFormula(slide, spec) {
  for (const key of [
    "eyebrow",
    "title",
    "subtitle",
    "card1Title",
    "card1Body",
    "card2Title",
    "card2Body",
    "card3Title",
    "card3Body",
    "takeaway",
  ]) {
    setText(slide, FORMULA[key], spec[key] ?? "");
  }
  for (const [name, value] of [
    [FORMULA.formula1Base, spec.formula1?.base ?? ""],
    [FORMULA.formula1Sub, spec.formula1?.sub ?? ""],
    [FORMULA.formula1Rest, spec.formula1?.rest ?? ""],
    [FORMULA.formula2Base, spec.formula2?.base ?? ""],
    [FORMULA.formula2Sub, spec.formula2?.sub ?? ""],
    [FORMULA.formula2Rest, spec.formula2?.rest ?? ""],
  ]) setText(slide, name, value);
  const strip = shapeByName(slide, FORMULA.strip, false);
  if (strip) strip.text = spec.strip ?? "";
  setNotes(slide, spec.sources);
}

async function replaceImages(slide, filename, position, alt) {
  for (const image of [...slide.images.items]) image.delete();
  const bytes = await fs.readFile(path.join(ASSETS, filename));
  const image = slide.images.add({
    blob: bytes,
    contentType: "image/png",
    alt,
    position,
    fit: "contain",
  });
  image.name = filename.replace(/\.png$/, "");
}

function assertClose(actual, expected, tolerance, label) {
  if (Math.abs(actual - expected) > tolerance) {
    throw new Error(`${label}: expected ${expected}, got ${actual}`);
  }
}

function assertAudit() {
  const checks = [
    [AUDIT.arrival["1997"].inflow_zj, 16.95640595, "1997 arrival"],
    [AUDIT.arrival["2015"].inflow_zj, 8.48760368, "2015 arrival"],
    [AUDIT.arrival["2023"].inflow_zj, 9.903187024, "2023 arrival"],
    [AUDIT.partition["1997"].surface_loss_zj, 4.913400194, "1997 surface loss"],
    [AUDIT.partition["2015"].surface_loss_zj, 1.508469573, "2015 surface loss"],
    [AUDIT.partition["2023"].surface_loss_zj, 0.4654415672, "2023 surface loss"],
    [AUDIT.q3.early_north_to_ne925.partial_r, 0.6796797189, "Q3 relation a"],
    [AUDIT.q3.stress_to_north.partial_r, 0.7415531028, "Q3 relation b"],
    [AUDIT.q3.sst_to_surface.partial_r, 0.6465693631, "Q3 relation c"],
  ];
  for (const [actual, expected, label] of checks) assertClose(actual, expected, 1e-8, label);
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

assertAudit();
const presentation = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
if (presentation.slides.items.length !== 15) {
  throw new Error(`Expected 15 slides, got ${presentation.slides.items.length}`);
}
const slide = (number) => presentation.slides.items[number - 1];

// 1. Opening thesis.
setText(slide(1), "矩形 5", "SODA3.15.2 · 0–300 m OHC′ · 13个暖事件");
setText(slide(1), "矩形 1", "厄尔尼诺异常暖量的\n到达、分配与不同命运");
setText(slide(1), "矩形 3", "问题一：暖量是否到达？    问题二：到达后去哪里？\n问题三：相似到达为何对应不同释放？");
setText(slide(1), "矩形 4", "到达量决定可释放规模；路由、动力与热力状态分别约束释放去向。");
setNotes(slide(1), ["Local synthesis of the audited SODA3.15.2 and ERA5 diagnostics used in this deck."]);

// 2. Three papers, one compact page.
setText(slide(2), "矩形 15", "研究出发点");
setText(slide(2), "矩形 1", "三篇文章分别提供传播、闭合和状态约束的思路");
setText(slide(2), "矩形 5", "Chakravorty et al. (2021)");
setText(slide(2), "矩形 6", "事件类型与阶段对照\n经度—时间传播\n纬向和经向输送并列\n\n启发：问题一、问题二");
setText(slide(2), "矩形 8", "Wenrui Jiang et al. (2025)");
setText(slide(2), "矩形 9", "三维拉格朗日路径\n沿轨迹热收支\n建立和衰减分期\n\n启发：路径、分配、反馈");
setText(slide(2), "矩形 11", "Leishan Jiang et al. (2026)");
setText(slide(2), "矩形 12", "2023远东太平洋先行增暖\nMJJ东北风异常\n中太平洋西风响应偏弱\n\n启发：问题三的时序坐标");
setText(slide(2), "矩形 14", "借鉴顺序：先追踪到达，再闭合去向，最后检验到达量之外的状态关系。");
setNotes(slide(2), [
  "https://doi.org/10.1029/2020JC017075 (Chakravorty et al., 2021)",
  "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint)",
  "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026)",
]);

// 3. Questions and non-overlapping windows.
setText(slide(3), "矩形 19", "研究问题");
setText(slide(3), "矩形 1", "三个问题由同一条时间有序证据链回答");
setText(slide(3), "矩形 3", "到达与早期路由、发展年大气状态、次年衰减期分开诊断");
setText(slide(3), "矩形 5", "1  到达");
setText(slide(3), "矩形 6", "OHC′向东传播\n反向轨迹东移\n140°W输入与东箱增量");
setText(slide(3), "矩形 8", "2  分配");
setText(slide(3), "矩形 9", "向西返回\n南北和东向输出\n海表散热与残差");
setText(slide(3), "矩形 11", "3  不同命运");
setText(slide(3), "矩形 12", "JFM北向分流\nMJJ东北风状态\n次年动力与热力释放");
setText(slide(3), "矩形 16", "Jan–Jun到达  →  JFM早期路由  →  MJJ大气状态  →  following Jan–May去向");
setText(slide(3), "矩形 18", "问题三只报告三组独立统计约束，不补写尚未验证的中间机制。");
setNotes(slide(3), ["Local analysis design and time windows used consistently throughout this deck."]);

// 4. Formula for the longitude–time OHC figure.
applyFormula(slide(4), {
  eyebrow: "逐图计算｜问题一",
  title: "传播图：把0–300 m OHC转换为经度—时间异常",
  subtitle: "SODA3.15.2｜10°S–5°N｜130°E–80°W｜1980–2014同月基线",
  card1Title: "固定层OHC",
  formula1: { rest: "H₃₀₀ = ⟨ρ₀cₚ∫₀³⁰⁰ T dz⟩ᵩ" },
  formula2: { rest: "H′₃₀₀ = H₃₀₀ − Ĉₘ − bₘ(y−ȳₘ)" },
  card1Body: "先在每个格点积分到300 m\n再按cosφ作纬向加权平均\n\nĈₘ与bₘ为同一日历月的均值和线性趋势",
  card2Title: "纬向平均与异常",
  card2Body: "⟨H⟩ᵩ = ΣᵢHᵢcosφᵢ / Σᵢcosφᵢ\n\n每个经度、每个日历月分别去除气候态和线性趋势\n\n输出单位：GJ m⁻²",
  card3Title: "下一页读图方式",
  card3Body: "事件窗：前一年Jul至发展年Nov\n面板：1997 / 2015 / 2023\n\n虚线：140°W\n黑线：H′₃₀₀ = 0\n三幅图使用同一色标",
  strip: "使用固定层OHC异常，不采用温度阈值暖水体积。",
  takeaway: "若暖异常跨过140°W并进入东箱，说明暖量确实向东到达。",
  sources: [
    `${ROOT}/scripts/analyze_soda3_post_arrival_three_box_ohc.py`,
    `${ROOT}/data/derived/research_2026/soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv`,
  ],
});

// 5. Longitude–time OHC result.
setText(slide(5), "矩形 7", "问题一｜传播证据");
setText(slide(5), "矩形 1", "三次事件的暖异常都跨过140°W并进入东太平洋");
setText(slide(5), "矩形 6", "2023并非“没到”；它与1997、2015一样存在清楚的向东传播信号。");
await replaceImages(
  slide(5),
  "fig-q1-hovmoller-en.png",
  { left: 54, top: 185, width: 1172, height: 430 },
  "Longitude-time evolution of 0–300 m ocean heat content anomalies in 1997, 2015, and 2023",
);
setNotes(slide(5), [
  `${ROOT}/data/derived/research_2026/soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv`,
  `${ROOT}/scripts/build_simplified_enso_ppt_assets_20260811.py`,
]);

// 6. Formula for the trajectory summary.
applyFormula(slide(6), {
  eyebrow: "逐图计算｜问题一",
  title: "轨迹图：用正温度异常权重统计三维反向路径",
  subtitle: "SODA3.15.2五日u/v/w与温度｜东太平洋释放区｜Jan–Jun反向追踪",
  card1Title: "释放异常与权重",
  formula1: { rest: "T′ₚ = Tₚ − T̂ₘ,₋ₑ" },
  formula2: { rest: "ωₚ = max(T′ₚ,0)cosφₚΔzₚ" },
  card1Body: "T̂ₘ,₋ₑ：排除事件年的同月线性预期\n保留T′ₚ > 0.05°C的粒子\n\nωₚ用于比例加权，不表示焦耳",
  card2Title: "反向轨迹积分",
  card2Body: "dλ/dt = u/(Rcosφ)\ndφ/dt = v/R\ndz/dt = −w\n\n五日场线性插值；midpoint RK2\n从6月末反向积分到1月初",
  card3Title: "下一页两个统计量",
  card3Body: "Δλₚ = λᵣₑₗₑₐₛₑ − λₛₒᵤᵣcₑ\n\n加权中位数：累计ωₚ达到0.5Σωₚ\n活动轨迹权重占比：Σωₚ,active / Σωₚ",
  takeaway: "轨迹只用于识别路径连通性，不替代能量守恒预算。",
  sources: [
    `${ROOT}/scripts/pilot_soda3_lagrangian_connectivity.py`,
    `${ROOT}/data/derived/research_2026/soda3_temp_anomaly_lagrangian_pilot_summary.csv`,
  ],
});

// 7. Trajectory result.
setText(slide(7), "矩形 13", "问题一｜轨迹证据");
setText(slide(7), "矩形 1", "三次事件都有东向连通路径，2023的活动轨迹权重最高");
setText(slide(7), "矩形 3", "Jan–Jun反向追踪；正温度异常权重；路径诊断不等同能量预算");
setText(slide(7), "矩形 6", "加权东移中位数");
setText(
  slide(7),
  "矩形 7",
  `1997  ${AUDIT.trajectory["1997"].median_eastward_deg.toFixed(1)}°\n2015  ${AUDIT.trajectory["2015"].median_eastward_deg.toFixed(1)}°\n2023  ${AUDIT.trajectory["2023"].median_eastward_deg.toFixed(1)}°`,
);
setText(slide(7), "矩形 9", "活动轨迹权重");
setText(
  slide(7),
  "矩形 10",
  `1997  ${(100 * AUDIT.trajectory["1997"].active_weight_fraction).toFixed(0)}%\n2015  ${(100 * AUDIT.trajectory["2015"].active_weight_fraction).toFixed(0)}%\n2023  ${(100 * AUDIT.trajectory["2023"].active_weight_fraction).toFixed(0)}%`,
);
setText(slide(7), "矩形 12", "路径证据说明三次事件均与东太平洋释放区相连；到达量由下一页边界预算确认。");
await replaceImages(
  slide(7),
  "fig-q1-trajectory-en.png",
  { left: 54, top: 192, width: 810, height: 344 },
  "Weighted eastward displacement and active trajectory weight fraction",
);
setNotes(slide(7), [
  `${ROOT}/data/derived/research_2026/soda3_temp_anomaly_lagrangian_pilot_summary.csv`,
  `${ROOT}/outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/data-audit.json`,
]);

// 8. Formula for independent arrival estimates.
applyFormula(slide(8), {
  eyebrow: "逐图计算｜问题一",
  title: "到达图：140°W输入与东箱OHC′增量独立计算",
  subtitle: "SODA3.15.2｜东箱140°W–80°W，10°S–5°N，0–300 m｜Jan–Jun",
  card1Title: "质量闭合边界输送",
  formula1: { rest: "Q₁₄₀W = ρ₀cₚ ∬uₙ(T−T̄ᵦ)dA" },
  formula2: { rest: "Aᴶᵃⁿ–ᴶᵘⁿ = ∫Q′₁₄₀W(t)dt" },
  card1Body: "四侧边界先作统一法向速度校正\n校正后净体积输送为0\n\n西边界正值表示进入东箱",
  card2Title: "东箱储热增量",
  card2Body: "H′ₑ(t) = ρ₀cₚ∭ₑT′dV\n\nΔH′ₑ = H′ₑ(Jun) − H′ₑ(Jan)\n\nT′与Q′均去除同月气候态和线性趋势",
  card3Title: "下一页两组柱",
  card3Body: "140°W累计输入Aᴶᵃⁿ–ᴶᵘⁿ\n东箱固定层储热增加ΔH′ₑ\n\n两者独立计算\n单位统一为ZJ",
  strip: "月样本采用梯形积分；1 PW·s = 10⁻⁶ ZJ。",
  takeaway: "边界输入和箱内储热同时为正，才能把“到达”从图像判断变为数量判断。",
  sources: [
    `${ROOT}/scripts/fetch_soda3_three_box_enthalpy_boundary_terms.py`,
    `${ROOT}/scripts/analyze_soda3_three_box_ohc_anomaly_budget.py`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
  ],
});

// 9. Arrival result.
setText(slide(9), "矩形 14", "问题一｜到达量");
setText(slide(9), "矩形 1", "140°W输入与东箱储热增量共同确认三次事件均已到达");
setText(slide(9), "矩形 3", "Jan–Jun累计能量；两套量由边界积分和箱内OHC′分别计算");
setText(slide(9), "矩形 6", "140°W输入");
setText(
  slide(9),
  "矩形 7",
  `1997  ${AUDIT.arrival["1997"].inflow_zj.toFixed(2)} ZJ\n2015  ${AUDIT.arrival["2015"].inflow_zj.toFixed(2)} ZJ\n2023  ${AUDIT.arrival["2023"].inflow_zj.toFixed(2)} ZJ`,
);
setText(slide(9), "矩形 9", "东箱OHC′增量");
setText(
  slide(9),
  "矩形 10",
  `1997  ${AUDIT.arrival["1997"].ohc_gain_zj.toFixed(2)} ZJ\n2015  ${AUDIT.arrival["2015"].ohc_gain_zj.toFixed(2)} ZJ\n2023  ${AUDIT.arrival["2023"].ohc_gain_zj.toFixed(2)} ZJ`,
);
setText(slide(9), "矩形 11", "排序一致：1997最大，2023次之，2015最小。");
setText(slide(9), "矩形 13", "问题一答案：2023不是“没到”；它的到达量高于2015，但明显低于1997。");
await replaceImages(
  slide(9),
  "fig-q1-arrival-en.png",
  { left: 54, top: 192, width: 810, height: 405 },
  "Independent estimates of 140 degree west inflow and eastern-box heat-content gain",
);
setNotes(slide(9), [
  `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
  `${ROOT}/outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/data-audit.json`,
]);

// 10. Formula for fate partition.
applyFormula(slide(10), {
  eyebrow: "逐图计算｜问题二",
  title: "去向图：用固定层OHC′预算分解following Jan–May能量变化",
  subtitle: "SODA3.15.2｜东箱140°W–80°W，10°S–5°N，0–300 m｜13事件",
  card1Title: "异常能量预算",
  formula1: { rest: "ΔH′ₑ = Q′W + Q′E + Q′N + Q′S + Q′ₛ + R′" },
  formula2: { rest: "R′ = ΔH′ₑ − ΣQ′ − Q′ₛ" },
  card1Body: "ΔH′ₑ：东箱OHC′变化\nQ′W、Q′E、Q′N、Q′S：四侧焓输送\nQ′ₛ：净海表热通量\nR′：未闭合项",
  card2Title: "绘图符号",
  card2Body: "储热损失 = −ΔH′ₑ\n向西返回 = −Q′W\n向东输出 = −Q′E\n向北输出 = −Q′N\n向南输出 = −Q′S\n海表散热 = −Q′ₛ",
  card3Title: "下一页三个事件",
  card3Body: "following Jan–May累计ZJ\n正值表示离开东箱\nR′保留预算符号\n\n边界项采用逐月动态边界温度参考",
  takeaway: "只解释已识别分量；较大的未闭合项作为问题二的明确限制保留一行。",
  sources: [
    `${ROOT}/scripts/analyze_soda3_three_box_ohc_anomaly_budget.py`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
  ],
});

// 11. Fate partition result with compact residual caveat.
setText(slide(11), "矩形 7", "问题二｜去向");
setText(slide(11), "矩形 1", "向西返回在三次事件中都最大；北向输出和散热差异明显");
setText(slide(11), "矩形 3", "following Jan–May；正值表示离开东箱；R′保留预算符号");
setText(
  slide(11),
  "矩形 6",
  `未闭合量占东箱损失约${(100 * AUDIT.residual_summary.fraction_of_loss["1997"]).toFixed(0)}% / ${(100 * AUDIT.residual_summary.fraction_of_loss["2015"]).toFixed(0)}% / ${(100 * AUDIT.residual_summary.fraction_of_loss["2023"]).toFixed(0)}%（1997 / 2015 / 2023），因此只解释已识别分量。`,
);
await replaceImages(
  slide(11),
  "fig-q2-partition-en.png",
  { left: 124, top: 184, width: 1032, height: 430 },
  "Partition of eastern-box ocean heat loss for 1997, 2015, and 2023",
);
setNotes(slide(11), [
  `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
  `${ROOT}/outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/data-audit.json`,
]);

// 12. Formula for Q3: three independent partial correlations.
applyFormula(slide(12), {
  eyebrow: "逐图计算｜问题三",
  title: "三联图：固定到达量后检验三组独立统计关系",
  subtitle: "13个暖事件｜偏相关｜事件置换双侧p值",
  card1Title: "统一残差化",
  formula1: { rest: "Xᵣ = X − (aₓ + bₓA)" },
  formula2: { rest: "Yᵣ = Y − (aᵧ + bᵧA)" },
  card1Body: "rₓᵧ·A = corr(Xᵣ,Yᵣ)\n\n图(a)：A为JFM 140°W到达量\n图(b)、(c)：A为Jan–Jun 140°W到达量",
  card2Title: "三组独立关系",
  card2Body: "(a) JFM北向输出 → MJJ NE925\n\n(b) 次年5°N向西应力 → 北向输出\n\n(c) 次年东箱SST → 海表散热",
  card3Title: "图中统计量",
  card3Body: "n = 13\n黑线：OLS拟合\nr：偏相关系数\np：20,000次事件置换\n\n1997橙，2015蓝，2023绿",
  takeaway: "三组关系并列报告，不补写MJJ东北风到次年应力的中间机制。",
  sources: [
    `${ROOT}/scripts/build_simplified_enso_ppt_assets_20260811.py`,
    `${ROOT}/outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/data-audit.json`,
    "https://doi.org/10.1029/2026GL123227",
  ],
});

// 13. Q3 result.
setText(slide(13), "矩形 7", "问题三｜独立统计约束");
setText(slide(13), "矩形 1", "控制到达量后，三组状态关系分别区分后续命运");
setText(slide(13), "矩形 3", "(a) JFM路由→MJJ NE925；(b) 5°N应力→北向输出；(c) SST→海表散热");
setText(slide(13), "矩形 6", "三组关系是并列统计约束，不构成已经闭合的中间因果链。");
await replaceImages(
  slide(13),
  "fig-q3-independent-constraints-en.png",
  { left: 54, top: 184, width: 1116, height: 430 },
  "Three independent partial relationships controlling for arrival amount across thirteen warm events",
);
setNotes(slide(13), [
  `${ROOT}/outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/data-audit.json`,
  `${ROOT}/scripts/build_simplified_enso_ppt_assets_20260811.py`,
  "https://doi.org/10.1029/2026GL123227",
]);

// 14. Unified answer.
setText(slide(14), "矩形 16", "三个问题的统一回答");
setText(slide(14), "矩形 1", "暖量确实到达；到达后的路由和释放状态决定事件差异");
setText(slide(14), "矩形 4", "1  暖量是否到达？");
setText(slide(14), "矩形 5", "到达。\nOHC′向东扩展，轨迹东移，140°W输入与东箱增量相互印证。");
setText(slide(14), "矩形 7", "2  到达后去哪里？");
setText(slide(14), "矩形 8", "共同项：向西返回最大。\n差异项：北向输出和海表散热。\n限制：2015与2023残差较大。");
setText(slide(14), "矩形 10", "3  为何命运不同？");
setText(slide(14), "矩形 11", "JFM北向分流领先MJJ NE925。\n次年动力状态对应北向输出。\n东箱SST对应海表散热。");
setText(slide(14), "矩形 13", "到达量决定可释放规模；路由、动力与热力状态分别约束释放去向。");
setText(slide(14), "矩形 15", "2023不是“没到”，而是到达后次年向北和向大气的释放都偏弱。");
setNotes(slide(14), [
  "Synthesis of the audited local results shown on slides 5, 7, 9, 11, and 13.",
  "https://doi.org/10.1029/2026GL123227",
]);

// 15. Compact backup: data, regions and windows.
setText(slide(15), "formula-data-overview-text-1", "备份｜数据与窗口");
setText(slide(15), "formula-data-overview-text-2", "全部结果使用固定区域、固定层和三个不重叠时间段");
setText(slide(15), "formula-data-overview-text-4", "SODA3.15.2 + ERA5｜13个暖事件｜不采用温度阈值暖水体积");
for (const name of [
  "formula-data-overview-text-7",
  "formula-data-overview-text-8",
  "formula-data-overview-text-9",
  "formula-data-overview-text-10",
  "formula-data-overview-text-11",
  "formula-data-overview-text-12",
]) deleteShape(slide(15), name);
setText(slide(15), "formula-data-overview-text-6", "数据与事件");
setText(slide(15), "formula-data-overview-text-13", "SODA3月平均T/u/v/w/Qnet\nSODA3五日T/u/v/w\nERA5风与应力\n\n13事件\n1982、1986、1991、1994\n1997、2002、2004、2006\n2009、2015、2018、2019、2023");
shapeByName(slide(15), "formula-data-overview-text-13").text.style = {
  ...shapeByName(slide(15), "formula-data-overview-text-13").text.style,
  fontSize: 17.5,
  autoFit: "shrinkText",
};
setText(slide(15), "formula-data-overview-text-15", "区域与层次");
setText(slide(15), "formula-data-overview-text-16", "传播：10°S–5°N，130°E–80°W\n东箱：10°S–5°N，140°W–80°W\n固定层：0–300 m\nJiang区域：3°–7°N，180°–130°W");
setText(slide(15), "formula-data-overview-text-18", "时间窗口");
setText(slide(15), "formula-data-overview-text-19", "到达：发展年Jan–Jun\n早期路由：发展年JFM\n大气状态：发展年MJJ\n去向：次年Jan–May\n\n基线：1980–2014或1980–2022");
setText(slide(15), "formula-data-overview-text-21", "公式页与结果页一一对应；所有可见数值均由CSV直接读取并通过审计脚本复核。");
setNotes(slide(15), [
  `${ROOT}/outputs/research_2026/ppt/.tmp_simplified_verified_20260811/assets/data-audit.json`,
  `${ROOT}/scripts/build_simplified_enso_ppt_assets_20260811.py`,
  `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
]);

// Normalize inherited formula-body typography after rewriting.
for (const number of [4, 6, 8, 10, 12]) {
  for (const name of [FORMULA.card1Body, FORMULA.card2Body, FORMULA.card3Body]) {
    const item = shapeByName(slide(number), name);
    item.text.style = {
      ...item.text.style,
      typeface: FONT_CN,
      fontSize: 16.5,
      color: "#0A2234",
      alignment: "left",
      autoFit: "shrinkText",
    };
  }
}

await fs.mkdir(PREVIEW, { recursive: true });
await fs.mkdir(LAYOUT, { recursive: true });
for (const [index, currentSlide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(PREVIEW, `${stem}.png`), await presentation.export({ slide: currentSlide, format: "png", scale: 1 }));
  const layout = await currentSlide.export({ format: "layout" });
  await fs.writeFile(path.join(LAYOUT, `${stem}.layout.json`), await layout.text());
}
await writeBlob(MONTAGE, await presentation.export({ format: "webp", montage: true, scale: 1 }));

const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,notes,layout", maxChars: 1200000 });
await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");
await fs.writeFile(
  path.join(TMP, "visible-number-audit.json"),
  JSON.stringify(
    {
      arrival: AUDIT.arrival,
      trajectory: AUDIT.trajectory,
      partition: AUDIT.partition,
      q3: AUDIT.q3,
      residual_summary: AUDIT.residual_summary,
    },
    null,
    2,
  ),
  "utf8",
);
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUTPUT);
console.log(JSON.stringify({ output: OUTPUT, slides: presentation.slides.items.length, montage: MONTAGE }, null, 2));
