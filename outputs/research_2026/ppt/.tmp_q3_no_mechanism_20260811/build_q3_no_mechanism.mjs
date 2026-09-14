import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_q3_no_mechanism_20260811");
const SOURCE = path.join(TMP, "template-starter.pptx");
const OUTPUT = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_第三问精简版_20260811.pptx",
);
const PREVIEW = path.join(TMP, "final-preview");
const LAYOUT = path.join(TMP, "final-layout");
const SOURCE_INSPECT = path.join(
  ROOT,
  "outputs/research_2026/ppt/.tmp_reviewer12_revision_20260811/final-inspect.ndjson",
);

let sourceElementIndex = new Map();

function resolve(presentation, id) {
  const source = sourceElementIndex.get(id);
  if (source) {
    const outputSlide = source.slide < 32 ? source.slide : source.slide - 2;
    const slide = presentation.slides.items[outputSlide - 1];
    const item = slide.shapes.items.find((shape) => shape.name === source.name);
    if (!item) throw new Error(`Missing starter element for ${id} (${source.name}) on output slide ${outputSlide}`);
    return item;
  }
  const item = presentation.resolve(id);
  if (!item) throw new Error(`Missing presentation element: ${id}`);
  return item;
}

function setText(presentation, id, value) {
  resolve(presentation, id).text = value;
}

function setBodyStyle(presentation, id, fontSize) {
  resolve(presentation, id).text.style = {
    fontSize,
    typeface: "PingFang SC",
    color: "#0A2234",
    alignment: "left",
  };
}

function setNotes(slide, sources) {
  slide.speakerNotes.clear();
  slide.speakerNotes.text = `[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}\n[/Sources]`;
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(PREVIEW, { recursive: true });
  await fs.mkdir(LAYOUT, { recursive: true });

  const presentation = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
  if (presentation.slides.items.length !== 38) {
    throw new Error(`Expected 38 starter slides, found ${presentation.slides.items.length}`);
  }
  const inspectText = await fs.readFile(SOURCE_INSPECT, "utf8");
  sourceElementIndex = new Map(
    inspectText
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => JSON.parse(line))
      .filter((record) => record.id && record.slide && record.name)
      .map((record) => [record.id, record]),
  );

  // Literature framing: retain the papers, remove the claim that they establish a gate.
  setText(presentation, "sh/9072xkry", "三篇文章共同给出“时空路径—闭合收支—状态约束”");
  setText(
    presentation,
    "sh/nu58f2hs",
    "• 2023远东太平洋先行增暖\n• MJJ东北风异常\n• 中太平洋西风响应偏弱\n\n对应：问题三的时序关系",
  );
  setText(presentation, "sh/xk7qlczu", "三篇文献把当前主线收束为：先追踪到达，再闭合去向，最后检验独立状态关系。");

  setText(presentation, "sh/7u5w765k", "文献三｜2023大气异常");
  setText(
    presentation,
    "sh/svydgb65",
    "对应Q3：论文给出东北风异常的区域与时段；当前结果在更早的JFM检验北向热量分流。",
  );

  setText(presentation, "sh/1cfmhgne", "三篇论文的公式和数据，分别支撑路径、闭合与状态约束");
  setText(
    presentation,
    "sh/lsn2h4fa",
    "T = E·Tₙ₃₄ + Tᵣ\nX = αTₙ₃₄ + βTᵣ + ε\n\nERSSTv5 + ERA5 + ORAS5\nECHAM4.6\n\n对应：Q3东北风时序与强迫验证",
  );
  setText(
    presentation,
    "sh/6l4fu547",
    "对应Q3：Tᵣ隔离东部先行增暖；β场给出东北风与弱西风异常的空间特征。",
  );

  // Research questions: Q3 reports parallel statistical constraints, not an intermediate mechanism.
  setText(presentation, "sh/547mhg3m", "三个问题由同一时间框架回答；第三问只报告独立统计约束");
  setText(
    presentation,
    "sh/vqdsrqx4",
    "JFM北向分流—MJJ东北风\n次年5°N应力—北向输出\n东箱SST—海表散热",
  );
  setText(
    presentation,
    "sh/judsvqxg",
    "Jan–Jun到达   ｜   JFM–MJJ先后   ｜   following Jan–May去向",
  );

  // Q3 overview: keep only the two supported pairwise arrows.
  setText(presentation, "sh/tk36hwby", "在相似到达量下，哪些先行状态能够区分后续命运？");
  setText(presentation, "sh/vmlojmto", "三组关系分别检验，统一控制到达量");
  setText(presentation, "sh/h8n6lwbu", "控制量");
  setText(presentation, "sh/g7upcra9", "Jan–Jun\n140°W输入");
  setText(presentation, "sh/idkbuxsv", "大气标记");
  setText(presentation, "sh/t4butcri", "动力状态");
  setText(presentation, "sh/6hkbyhs7", "following Jan–May\n5°N应力");
  setText(presentation, "sh/c7a9wj2t", "开放项");
  setText(presentation, "sh/b61snel8", "向西返回仍待盆地尺度调整诊断");
  setText(presentation, "sh/lw3ato3a", "热力状态");
  setText(
    presentation,
    "sh/58vy9wfm",
    "到达量给出总尺度；早期路由、动力状态与热力状态分别提供独立统计约束。",
  );
  resolve(presentation, "sh/p4jal432").delete();
  resolve(presentation, "sh/n21sjelc").delete();

  // Early routing result: state timing and correlation only.
  setText(presentation, "sh/5sn2to3u", "早期北向分流领先东北风，是独立的时序约束");
  setText(
    presentation,
    "sh/wf69wv6t",
    "13事件支持“先海洋、后大气”的时序关系；这里报告先后与相关。",
  );

  // Robustness formula page, rewritten around three independent relationships.
  setText(presentation, "sh/pwzm1kbm", "稳健性矩阵：检验三组独立统计约束是否受强事件支配");
  setText(
    presentation,
    "sh/za9wbutk",
    "C含截距；按原关系选择是否加入到达量\n对事件有放回抽样20,000次\nCI₉₅取r*的2.5%与97.5%分位\n\n区间跨0：不报告为稳定约束\n置换p仍用于原始显著性检验",
  );
  setText(presentation, "sh/90beh4bm", "三组独立关系");
  setText(
    presentation,
    "sh/mxkvmpcb",
    "(a) JFM北向输出 → MJJ NE925\n固定JFM到达量\n\n(b) 5°N应力 → 晚期北向输出\n固定Jan–Jun到达量\n\n(c) 东箱SST → 海表散热\n固定Jan–Jun到达量",
  );
  setText(presentation, "sh/w32xszud", "证据保留规则");
  setText(
    presentation,
    "sh/x4vel4by",
    "95% CI不跨0\nSpearman同号\n去1997 / 2015 / 2023后稳定\n逐一留一事件不改变方向\n\n每组关系单独判断",
  );
  setText(presentation, "sh/k7y5gfi5", "三组关系分别计算、分别解释，证据等级互不替代");
  setText(presentation, "sh/y5wne50z", "下一页按同一规则判断哪些状态指标可稳定区分后续命运。");
  setBodyStyle(presentation, "sh/za9wbutk", 16.31);
  setBodyStyle(presentation, "sh/mxkvmpcb", 16.31);
  setBodyStyle(presentation, "sh/x4vel4by", 16.31);
  setNotes(presentation.slides.items[31], [
    `${ROOT}/outputs/research_2026/ppt/.tmp_per_figure_formulas_20260811/audit_q3_robustness.py`,
    `${ROOT}/data/derived/research_2026/nonh20_third_question_relationships.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_early_north_to_jiang_relationships.csv`,
  ]);

  // Robustness result page: three relationships, three evidence summaries.
  setText(presentation, "sh/idonexon", "三组独立关系保持同号，动力与热力状态可区分晚期命运");
  setText(
    presentation,
    "sh/gb6lcn6x",
    "n = 13；沿用各关系原控制量；Pearson、Spearman、bootstrap与删点联合判断",
  );
  setText(presentation, "sh/u943ador", "先行状态｜北向路由→东北风");
  setText(
    presentation,
    "sh/vad43ipc",
    "r .68｜ρₛ .56｜CI .24–.95\n去1997/2015/2023：.74/.60/.57\n时间窗：JFM → MJJ\n只报告先后与相关",
  );
  setText(presentation, "sh/t8vm1876", "动力状态｜5°N应力→北向输出");
  setText(
    presentation,
    "sh/5of6xcbi",
    "r .74｜ρₛ .68｜CI .28–.92\n去1997/2015/2023：.73/.74/.74\n删点后高度稳定\n固定到达量",
  );
  setText(presentation, "sh/3mxov2tc", "热力状态｜东箱SST→海表散热");
  setText(
    presentation,
    "sh/ilonmxsr",
    "r .65｜ρₛ .64｜CI .24–.92\n去1997/2015/2023：.66/.67/.63\n删点后方向与幅度稳定\n固定到达量",
  );
  setText(presentation, "sh/gjm5knal", "三组关系独立报告，用于区分事件命运。");
  setBodyStyle(presentation, "sh/vad43ipc", 19);
  setBodyStyle(presentation, "sh/5of6xcbi", 19);
  setBodyStyle(presentation, "sh/ilonmxsr", 19);
  setNotes(presentation.slides.items[32], [
    `${ROOT}/outputs/research_2026/ppt/.tmp_per_figure_formulas_20260811/audit_q3_robustness.py`,
    `${ROOT}/data/derived/research_2026/nonh20_third_question_relationships.csv`,
    `${ROOT}/data/derived/research_2026/nonh20_early_north_to_jiang_relationships.csv`,
  ]);

  // Thermal/adjustment pages: remove gate language but retain the null result.
  setText(presentation, "sh/94r61c32", "下一页(a)：热力关系");
  setText(presentation, "sh/w72pc72t", "下一页(b)：调整关系");
  setText(
    presentation,
    "sh/h8b65cje",
    "X = following Jan–May 5°N西向应力异常\nY = −∫Q′Wdt，向西返回量\n\n二者同样固定到达量\n若置换p未通过检验，则只报告相关方向，不作为稳定统计约束",
  );
  setText(
    presentation,
    "sh/i1wnuxcr",
    "下一页(a)通过统计检验，(b)未通过；因此保留SST—散热关系，向西返回仍是开放问题。",
  );
  setText(presentation, "sh/61c7md0r", "东箱SST稳定约束海表散热；向西返回的统计关系仍不显著");

  // LOEO pages: use state-variable language.
  setText(presentation, "sh/kvy1kbep", "稳健性图：逐次留出一个事件，比较加入状态变量前后的误差");
  setText(
    presentation,
    "sh/hgrihsny",
    "基线：N = β₀ + β₁A\n状态：N = β₀ + β₁A + β₂τ₅N\n\nA：Jan–Jun到达量\nτ₅N：following Jan–May 5°N应力\n\n下一页比较两模型的RMSEz，并报告LOEO预测相关",
  );
  setText(
    presentation,
    "sh/e94jyh4b",
    "基线：L = β₀ + β₁A\n状态：L = β₀ + β₁A + β₂SSTₑ\n\nL：following Jan–May海表散热\nSSTₑ：同期东箱SST′\n\n所有预测均来自未见过该事件的模型",
  );
  setText(
    presentation,
    "sh/x8z2l07a",
    "下一页误差下降说明状态变量含有到达量之外的信息，但仍属于样本外统计约束。",
  );
  setText(presentation, "sh/50769kvu", "加入状态变量后，留一事件预测误差下降");
  setText(presentation, "sh/rid8vi1c", "误差下降表明含有额外预测信息；仍是样本外统计证据。");

  // Final synthesis: parallel evidence, no bridge or mediation claim.
  setText(presentation, "sh/y9gzu50n", "到达、早期路由与独立状态约束构成可检验主线");
  setText(
    presentation,
    "sh/fu54vudk",
    "JFM北向分流领先MJJ东北风。\n5°N应力约束晚期北向输出。\n东箱SST约束海表散热。",
  );
  setText(
    presentation,
    "sh/tsnmt4vu",
    "到达尺度 + 早期路由 + 动力状态 + 热力状态 → 次年分配\n三组统计约束并列报告",
  );
  setText(
    presentation,
    "sh/r6l4rudo",
    "2023不是“没到”：它表现出更强早期北向分流，并伴随东北风增强和次年释放偏弱。",
  );

  // The starter map already omits source slides 32–33.
  if (presentation.slides.items.length !== 38) {
    throw new Error(`Expected 38 final slides, found ${presentation.slides.items.length}`);
  }

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
