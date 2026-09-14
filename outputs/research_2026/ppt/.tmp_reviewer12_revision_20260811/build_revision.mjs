import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_reviewer12_revision_20260811");
const SOURCE = path.join(TMP, "template-starter.pptx");
const OUTPUT = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_稳健性残差修订版_20260811.pptx",
);
const PREVIEW = path.join(TMP, "final-preview");
const LAYOUT = path.join(TMP, "final-layout");

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

const RESULT = {
  eyebrow: "矩形 15",
  title: "矩形 1",
  subtitle: "矩形 3",
  card1Title: "矩形 5",
  card1Body: "矩形 6",
  card2Title: "矩形 8",
  card2Body: "矩形 9",
  card3Title: "矩形 11",
  card3Body: "矩形 12",
  takeaway: "矩形 14",
};

function shapeByName(slide, name) {
  const shape = slide.shapes.items.find((item) => item.name === name);
  if (!shape) throw new Error(`Missing shape ${name}`);
  return shape;
}

function setText(slide, name, value) {
  shapeByName(slide, name).text = value;
}

function setUniformBodyStyle(slide, name, fontSize) {
  shapeByName(slide, name).text.style = {
    fontSize,
    typeface: "PingFang SC",
    color: "#0A2234",
    alignment: "left",
  };
}

function normalizeFormulaBodies(slide) {
  setUniformBodyStyle(slide, FORMULA.card1Body, 16.31);
  setUniformBodyStyle(slide, FORMULA.card2Body, 16.31);
  setUniformBodyStyle(slide, FORMULA.card3Body, 16.31);
}

function normalizeResultBodies(slide) {
  setUniformBodyStyle(slide, RESULT.card1Body, 19);
  setUniformBodyStyle(slide, RESULT.card2Body, 19);
  setUniformBodyStyle(slide, RESULT.card3Body, 19);
}

function setNotes(slide, sources) {
  slide.speakerNotes.clear();
  slide.speakerNotes.text = `[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}\n[/Sources]`;
}

function applyFormula(slide, spec) {
  for (const [key, name] of Object.entries(FORMULA)) {
    if (key.startsWith("formula")) continue;
    setText(slide, name, spec[key] ?? "");
  }
  setText(slide, FORMULA.formula1Base, spec.formula1?.base ?? "");
  setText(slide, FORMULA.formula1Sub, spec.formula1?.sub ?? "");
  setText(slide, FORMULA.formula1Rest, spec.formula1?.rest ?? "");
  setText(slide, FORMULA.formula2Base, spec.formula2?.base ?? "");
  setText(slide, FORMULA.formula2Sub, spec.formula2?.sub ?? "");
  setText(slide, FORMULA.formula2Rest, spec.formula2?.rest ?? "");
  setNotes(slide, spec.sources);
}

function applyResult(slide, spec) {
  for (const [key, name] of Object.entries(RESULT)) setText(slide, name, spec[key] ?? "");
  setNotes(slide, spec.sources);
}

function reviseExisting(presentation) {
  const slide = (number) => presentation.slides.items[number - 1];

  setText(slide(1), "矩形 4", "到达量设定衰减规模；动力与热力变量提供释放效率的统计约束。");

  setText(slide(23), "矩形 1", "到达后，用可审计的三箱OHC′预算追踪去向");
  setText(slide(23), "矩形 24", "正值：离开东箱\n残差：单列，不命名通道\nQnet：已显式计入\n总收敛/残差：参考不敏感\n单边分配：依赖参考定义");
  setText(slide(23), "矩形 26", "单边输出用于分配诊断；总收敛与残差用于闭合诊断，两者证据层级不同。");

  setText(slide(24), FORMULA.card3Body, "每个面板：1997 / 2015 / 2023\n每根柱：following Jan–May累计ZJ\n\n单边项采用逐月动态边界温度参考\n总收敛与R′对常数参考温标不敏感\n单边西/北分配对参考定义敏感");
  setText(slide(24), FORMULA.card1Body, "ΔH′ₑ：东箱OHC′变化\nC′ₑ：四侧边界总焓收敛\nQnet已显式计入\nR′ = ΔH′ₑ − C′ₑ − Q′ₛ\n所有项使用同一Jan–May积分窗");
  setText(slide(24), FORMULA.card2Body, "储热损失 = −ΔH′ₑ\n向西返回 = −Q′W\n向北输出 = −Q′N\n向南输出 = −Q′S\n海表散热 = −Q′ₛ\n\n正值统一表示离开东箱；R′单列");
  setText(slide(24), FORMULA.strip, "逐月异常积分为ZJ；先核验总收支，再解释当前参考下的单边分配");
  setText(slide(24), FORMULA.takeaway, "下一页比较当前动态参考下的已识别项；残差随后单独审计。");
  normalizeFormulaBodies(slide(24));

  setText(slide(25), "矩形 1", "当前动态参考下，向西返回是最大的已识别水平项");
  setText(slide(25), "矩形 3", "following Jan–May；正值表示离开东箱；残差单列");
  setText(slide(25), "矩形 6", "单边分配依赖参考定义；总收敛与残差不依赖常数参考温标，下一页审计残差。");
  setNotes(slide(25), [
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_face_reference_sensitivity.csv`,
  ]);

  setText(slide(28), "矩形 1", "当前参考下共同水平项相近，但未闭合量限制精确归因");
  setText(slide(28), "矩形 3", "following Jan–May累计能量（ZJ）；残差按未闭合汇的绝对值列出");
  setText(slide(28), "矩形 6", "东箱损失 21.76\n向西返回 9.52\n向北输出 5.70\n海表散热 4.89\n未闭合汇 0.52（2.4%）");
  setText(slide(28), "矩形 9", "东箱损失 19.89\n向西返回 8.65\n向北输出 2.99\n海表散热 1.49\n未闭合汇 6.39（32.1%）");
  setText(slide(28), "矩形 12", "东箱损失 15.95\n向西返回 9.45\n向北输出 2.17\n海表散热 0.54\n未闭合汇 4.43（27.7%）");
  setText(slide(28), "矩形 14", "当前参考：向西返回相近   ｜   稳健差异：北向输出与散热   ｜   限制：残差");
  setText(slide(28), "矩形 16", "问题二可回答“已识别项如何分配”；尚不能把全部损失精确归入具体物理通道。");
  setNotes(slide(28), [
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_monthly.csv`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_face_reference_sensitivity.csv`,
  ]);

  setText(slide(29), "矩形 1", "早期北向分流能否衔接东北风，并约束次年释放方式？");
  setText(slide(29), "矩形 11", "东北风线索");
  setText(slide(29), "矩形 14", "候选风—应力桥");
  setText(slide(29), "矩形 32", "到达量给出总尺度；早期路由、热力与动力变量提供后续分配的统计约束。");

  setText(slide(31), "矩形 27", "早期北向分流领先东北风，是后续链条的稳健先行线索");
  setText(slide(31), "矩形 46", "13事件支持“先海洋、后大气”的时序关系；具体中间机制仍需过程诊断。");

  setText(slide(32), FORMULA.title, "动力链图：分段检验东北风、应力与北向输出，不拼接因果系数");
  setText(slide(32), FORMULA.card2Title, "三段关系：中间段为候选");
  setText(slide(32), FORMULA.card2Body, "(a) NE850ᴹᴶᴶ → 中央应力ᴹᴶᴶ\n固定JFM到达量；候选桥梁\n\n(b) 中央U850ᴹᴶᴶ → 次年5°N应力\n仅去事件均值；对1997敏感\n\n(c) 5°N应力 → 晚期北向输出\n固定Jan–Jun到达量；稳健端点");
  setText(slide(32), FORMULA.card3Title, "显著性之外的稳健性");
  setText(slide(32), FORMULA.card3Body, "置换p与family-FDR\nSpearman秩相关\nbootstrap 95% CI\n去掉1997 / 2015 / 2023\n逐一留一事件系数范围\n\n下一组页面给出证据等级");
  setText(slide(32), FORMULA.takeaway, "下一页只展示分段相关；随后用秩相关、bootstrap和留一事件检验决定证据等级。");
  normalizeFormulaBodies(slide(32));

  setText(slide(33), "矩形 27", "东北风—中央应力仅是候选桥梁；5°N应力—北向输出更稳健");
  setText(slide(33), "矩形 29", "MJJ → following Jan–May；13事件残差化关系，证据分段解释");
  setText(slide(33), "矩形 40", "NE850 → 中央应力（脆弱）");
  setText(slide(33), "矩形 41", "r = −0.56；ρₛ = −0.35");
  setText(slide(33), "矩形 49", "早期分流与晚期输出两端较稳健；东北风—中央应力的中间桥梁仍需因果试验。");
  setNotes(slide(33), [
    `${ROOT}/data/derived/research_2026/nonh20_third_question_relationships.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_early_north_to_jiang_relationships.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_third_question_mediation_summary.csv`,
    "https://doi.org/10.1029/2026GL123227",
  ]);

  setText(slide(39), "矩形 1", "加入耦合变量后，留一事件预测误差下降");
  setText(slide(39), "矩形 12", "误差下降表明含有额外预测信息；不等同于串联中介或因果闭环。");

  setText(slide(40), "矩形 1", "到达、早期路由与统计约束构成一条可检验主线");
  setText(slide(40), "矩形 8", "当前参考：向西返回最大\n稳健差异：北向输出与散热\n限制：残差尚未闭合");
  setText(slide(40), "矩形 11", "JFM北向分流领先MJJ东北风。\n5°N应力与晚期北向输出稳健。\n中间风—应力桥仍是候选。");
  setText(slide(40), "矩形 13", "到达 → 早期路由 → 候选动力桥 → 次年分配\n热力散热受统计约束；向西返回机制与残差仍开放");
  setText(slide(40), "矩形 15", "2023不是“没到”：现有证据支持先北向分流、后东北风增强，并伴随次年释放偏弱。");
}

const residualFormula = {
  eyebrow: "逐图计算｜问题二",
  title: "残差审计：区分已计入项、缺失过程与参考敏感性",
  subtitle: "SODA3.15.2｜东箱following Jan–May｜0–300 m固定层｜13事件",
  card1Title: "残差与相对量级",
  formula1: { rest: "R′ = ΔH′ₑ − ∫(C′ₑ + Q′ₛ)dt" },
  formula2: { rest: "fᴿ = |R′| / |ΔH′ₑ|" },
  card1Body: "ΔH′ₑ = H′ₑ(t₂) − H′ₑ(t₁)\nC′ₑ：四个侧边界的总焓收敛\nQ′ₛ：向海洋为正的净海表热通量\nR′：端点变化减去逐月积分\nfᴿ：未闭合量占东箱损失比例",
  card2Title: "已经显式计入",
  card2Body: "• 四个侧边界总焓收敛\n• 净海表热通量Qnet\n• Jan–May端点OHC′变化\n\n因此Qnet不是残差来源。\n总收敛与R′对常数参考温标不敏感。",
  card3Title: "尚未显式计入",
  card3Body: "• 300 m底边界垂向平流\n• 垂向混合与扩散\n• SODA同化/分析增量\n• 月平均积分与端点离散误差\n\n这些项目前只能作为候选来源。",
  strip: "单边面分配对参考定义敏感；残差审计优先看总收敛，不把参考敏感性误判为残差来源",
  takeaway: "下一页先量化未闭合比例，再决定哪些问题二结论可以保留。",
  sources: [
    `${ROOT}/scripts/analyze_soda3_three_box_ohc_anomaly_budget.py`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_monthly.csv`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_face_reference_sensitivity.csv`,
  ],
};

const residualResult = {
  eyebrow: "问题二｜残差审计",
  title: "2015和2023的残差分别占东箱损失32%和28%",
  subtitle: "13事件中位数：|R′|/损失 = 26.4%；|R′| = 2.84 ZJ；11/13为未闭合汇",
  card1Title: "1997｜近似闭合",
  card1Body: "东箱损失  21.76 ZJ\n未闭合汇  0.52 ZJ\n占损失  2.4%\n逐月积分残差  0.44\n端点差  0.08",
  card2Title: "2015｜残差较大",
  card2Body: "东箱损失  19.89 ZJ\n未闭合汇  6.39 ZJ\n占损失  32.1%\n逐月积分残差  5.76\n端点差  0.63",
  card3Title: "2023｜残差较大",
  card3Body: "东箱损失  15.95 ZJ\n未闭合汇  4.43 ZJ\n占损失  27.7%\n逐月积分残差  3.11\n端点差  1.31",
  takeaway: "Qnet已计入；优先补300 m底通量、混合/扩散和SODA同化增量。",
  sources: [
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv`,
    `${ROOT}/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_monthly.csv`,
    `${ROOT}/scripts/analyze_soda3_three_box_ohc_anomaly_budget.py`,
  ],
};

const robustnessFormula = {
  eyebrow: "逐图计算｜问题三",
  title: "稳健性矩阵：不让13个事件被三次强事件支配",
  subtitle: "Pearson + Spearman + bootstrap CI + 去高亮事件 + 逐一留一事件",
  card1Title: "偏相关与bootstrap",
  formula1: { rest: "rₓᵧ·C = corr(M꜀X, M꜀Y)" },
  formula2: { rest: "M꜀ = I − C(CᵀC)⁻¹Cᵀ" },
  card1Body: "C含截距；按原关系选择是否加入到达量\n对事件有放回抽样20,000次\nCI₉₅取r*的2.5%与97.5%分位\n\n区间跨0：不判为稳健桥梁\n置换p仍用于原始显著性检验",
  card2Title: "秩相关与删点",
  card2Body: "ρₛ = corr(rank Xᵣ, rank Yᵣ)\n\nr₋ₑ：去掉事件e后重算\ne = 1997、2015、2023\n\n再逐一留出13个事件，报告r与斜率范围。",
  card3Title: "证据分级规则",
  card3Body: "稳健：CI不跨0，秩相关同号，删点后稳定\n\n中等：方向稳定，但对一个强事件敏感\n\n脆弱：CI跨0或删点后相关显著减弱",
  strip: "串联中介另行bootstrap：间接效应95% CI跨0时，不把分段相关写成完整因果链",
  takeaway: "下一页按同一规则给五段关系分级，而不是只报告一个Pearson r。",
  sources: [
    `${ROOT}/outputs/research_2026/ppt/.tmp_per_figure_formulas_20260811/audit_q3_robustness.py`,
    `${ROOT}/data/derived/research_2026/nonh20_third_question_relationships.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_early_north_to_jiang_relationships.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_third_question_mediation_summary.csv`,
  ],
};

const robustnessResult = {
  eyebrow: "问题三｜稳健性矩阵",
  title: "两端关系稳健，中间的NE850—中央应力桥梁最脆弱",
  subtitle: "n = 13；沿用各关系原控制量；Pearson、Spearman、bootstrap与留一事件联合判断",
  card1Title: "稳健｜链条两端",
  card1Body: "JFM north → MJJ NE925\nr .68｜ρₛ .56｜CI .24–.95\n5°N stress → late north export\nr .74｜ρₛ .68｜CI .28–.92\n去1997/2015/2023：.73/.74/.74",
  card2Title: "脆弱｜候选桥梁",
  card2Body: "NE850 → central stress\nr −.56｜ρₛ −.35\nCI −.90–.11，跨0\n去2015：r = −.26\n间接效应CI：−.11–.75",
  card3Title: "中等｜对1997敏感",
  card3Body: "U850 → next-year 5°N stress\nr .69｜ρₛ .48\nCI .10–.89\n去1997：r = .42\n方向保持为正，幅度明显减弱",
  takeaway: "可保留“统计链条”假说；不能把三段相关叙述为完整串联因果。",
  sources: [
    `${ROOT}/outputs/research_2026/ppt/.tmp_per_figure_formulas_20260811/audit_q3_robustness.py`,
    `${ROOT}/data/derived/research_2026/nonh20_third_question_mediation_summary.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_third_question_relationships.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_early_north_to_jiang_relationships.csv`,
  ],
};

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(PREVIEW, { recursive: true });
  await fs.mkdir(LAYOUT, { recursive: true });
  const presentation = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
  if (presentation.slides.items.length !== 40) throw new Error(`Expected 40 slides, found ${presentation.slides.items.length}`);

  reviseExisting(presentation);
  applyFormula(presentation.slides.items[25], residualFormula);
  applyResult(presentation.slides.items[26], residualResult);
  applyFormula(presentation.slides.items[33], robustnessFormula);
  applyResult(presentation.slides.items[34], robustnessResult);
  normalizeFormulaBodies(presentation.slides.items[25]);
  normalizeResultBodies(presentation.slides.items[26]);
  normalizeFormulaBodies(presentation.slides.items[33]);
  normalizeResultBodies(presentation.slides.items[34]);

  for (let index = 0; index < presentation.slides.items.length; index += 1) {
    const slide = presentation.slides.items[index];
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(PREVIEW, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(LAYOUT, `${stem}.layout.json`), await layout.text(), "utf8");
  }

  await writeBlob(path.join(TMP, "final-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));
  const inspect = await presentation.inspect({
    kind: "slide,textbox,shape,image,notes,layout",
    include: "id,slide,name,title,text,textPreview,bbox,isPlaceholder",
    maxChars: 1000000,
  });
  await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(OUTPUT);
  console.log(JSON.stringify({ output: OUTPUT, slides: presentation.slides.items.length }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
