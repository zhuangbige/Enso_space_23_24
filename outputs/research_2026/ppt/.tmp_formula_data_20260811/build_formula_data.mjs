import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_formula_data_20260811");
const OUT = path.join(ROOT, "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_公式数据扩展版_20260811.pptx");
const PREVIEW = path.join(TMP, "final-preview");
const LAYOUT = path.join(TMP, "final-layout");

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function shapeById(slide, id) {
  const shape = slide.shapes.items.find((item) => String(item.id) === String(id));
  if (!shape) throw new Error(`Shape ${id} not found`);
  return shape;
}

function rewrite(slide, id, text) {
  shapeById(slide, id).text = text;
}

function setSources(slide, lines) {
  slide.speakerNotes.clear();
  slide.speakerNotes.text = `[Sources]\n${lines.map((line) => `- ${line}`).join("\n")}\n[/Sources]`;
}

function editThreeCardSlide13(slide, spec) {
  rewrite(slide, "18", spec.eyebrow);
  rewrite(slide, "2", spec.title);
  rewrite(slide, "4", spec.subtitle);
  rewrite(slide, "6", spec.cards[0].title);
  rewrite(slide, "7", spec.cards[0].body);
  rewrite(slide, "9", spec.cards[1].title);
  rewrite(slide, "10", spec.cards[1].body);
  rewrite(slide, "12", spec.cards[2].title);
  rewrite(slide, "13", spec.cards[2].body);
  rewrite(slide, "15", spec.strip);
  rewrite(slide, "17", spec.takeaway);
  setSources(slide, spec.sources);
}

function editThreeCardSlide19(slide, spec) {
  rewrite(slide, "17", spec.eyebrow);
  rewrite(slide, "2", spec.title);
  rewrite(slide, "5", spec.cards[0].title);
  rewrite(slide, "6", spec.cards[0].body);
  rewrite(slide, "8", spec.cards[1].title);
  rewrite(slide, "9", spec.cards[1].body);
  rewrite(slide, "11", spec.cards[2].title);
  rewrite(slide, "12", spec.cards[2].body);
  rewrite(slide, "14", spec.strip);
  rewrite(slide, "16", spec.takeaway);
  const takeawayBar = shapeById(slide, "15");
  takeawayBar.fill = "#2F80B9";
  takeawayBar.line = { style: "solid", fill: "#2F80B9", width: 1.2 };
  setSources(slide, spec.sources);
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(path.join(TMP, "template-starter.pptx")));
if (presentation.slides.items.length !== 25) throw new Error(`Expected 25 slides, got ${presentation.slides.items.length}`);

const specs = [
  {
    eyebrow: "文献方法总览",
    title: "三篇论文的公式和数据，分别支撑路径、闭合与耦合门控",
    subtitle: "原式与数据设置逐项对应当前三个问题",
    cards: [
      { title: "Chakravorty et al. (2021)", body: "N_CT = N3 − αN4\nN_CP = N4 − αN3\nSODA + HadISST\n→ Q1路径 / Q2分配" },
      { title: "Wenrui Jiang et al. (2025)", body: "∂Θ′/∂t + A(U,Θ′) = ΣR_i\nECCO4 + OISST + ERA5\n→ Q1轨迹 / Q2闭合\n→ Q3海气反馈" },
      { title: "Leishan Jiang et al. (2026)", body: "T = E·T_N34 + T_R\nX = αT_N34 + βT_R + ε\nERSSTv5 + ERA5 + ORAS5\nECHAM4.6 → Q3门控" },
    ],
    strip: "Q1：传播与轨迹   ｜   Q2：边界与闭合收支   ｜   Q3：残差分解与强迫验证",
    takeaway: "借鉴顺序：事件分类 → 路径追踪 → 收支闭合 → 残差分解 → 模式验证。",
    sources: [
      "https://doi.org/10.1029/2020JC017075 (Equations 1-2 and Sections 2-3)",
      "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Equations 1-3 and Section 4)",
      "https://doi.org/10.1029/2026GL123227 (Equations 1-2 and Section 2)",
    ],
  },
  {
    eyebrow: "文献一｜公式与数据",
    title: "事件分类与充放电诊断，建立在两组指数和边界输送上",
    subtitle: "Chakravorty et al. (2021) | Equations 1–2 + described diagnostics",
    cards: [
      { title: "CT / CP指数", body: "N_CT = N3 − αN4\nN_CP = N4 − αN3\nα = 2/5，若 N3·N4 > 0\n否则 α = 0" },
      { title: "事件与空间定义", body: "N3：5°N–5°S\n150°W–90°W\nN4：5°N–5°S\n160°E–150°W\nCHI：SST′空间一阶矩\n阈值0.8°C，连续≥5个月" },
      { title: "WWV / 边界输送 / 数据", body: "WWV = ∬h_T dA\nZT_170E = ∬u dzdy\nMT_φ = ∬v dzdλ\nSODA2.1.6：1958–2008\nSODA2.2.4：1901–2008\nHadISST独立核验" },
    ],
    strip: "去季节循环 + 去趋势 + 3个月滑动平均 ｜ 8个CT + 8个CP ｜ 双侧t检验95%",
    takeaway: "对应Q1–Q2：借鉴分类与跨边界输送；当前固定层方案不采用阈值温跃层指标。",
    sources: [
      "https://doi.org/10.1029/2020JC017075 (Chakravorty et al., 2021; Equations 1-2; Sections 2.1-2.3 and 3.5)",
      "Local PDF: /Users/daiyue/Documents/Maryland/tmp/pdfs/chakravorty_2021_recharge_discharge_enso_flavors.pdf, PDF pages 3-4 and 12.",
      "SODA 2.1.6/2.2.4, HadISST, ERA-40, QuikSCAT and 20CRv2c data descriptions are from Section 2.1.",
    ],
  },
  {
    eyebrow: "文献二｜闭合方程",
    title: "ECCO4把温度变化闭合到平流、扩散与外部加热",
    subtitle: "⟨·⟩：1992–2017季节气候态；δ_NA = A_online − A_offline",
    cards: [
      { title: "Eq. 1｜网格闭合", body: "∂Θ/∂t + A(U,Θ)\n= D_h(K,Θ) + D_v(K,Θ)\n+ Q(Θ) + δ_NA\n\nU：速度；K：扩散率\nQ：外部/海表加热" },
      { title: "Eq. 2｜季节气候态", body: "∂⟨Θ⟩/∂t + A(⟨U⟩,⟨Θ⟩)\n= ⟨D_h⟩ + ⟨D_v⟩ + ⟨Q⟩ + ⟨δ_NA⟩\n− ⟨A(U′,Θ′)⟩\n+ A(⟨U′⟩,⟨Θ⟩)" },
      { title: "Eq. 3｜异常预算", body: "∂Θ′/∂t + A(U,Θ′)\n= D′_h + D′_v + Q′ + δ′_NA\n+ ⟨A(U′,Θ′)⟩\n− A(U′,⟨Θ⟩)\n\n扩散｜加热｜NA｜整流｜异常" },
    ],
    strip: "(t₁−t₀)∂Θ/∂t = [ΔH/(ρc_p) − ΘΔV] / V₀",
    takeaway: "对应Q2：沿同一固定体积、同一边界和同一时间积分，逐项检验闭合与残差。",
    sources: [
      "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint; Equations 1-3, Section 4.2)",
      "Local PDF: /Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811/mhw_preprint.pdf, PDF page 7.",
      "Angle brackets on this slide compactly denote the paper's overbar seasonal climatology notation; the mathematical decomposition is unchanged.",
    ],
  },
  {
    eyebrow: "文献二｜轨迹与实验",
    title: "被动示踪确定水团，粒子沿轨迹积分异常温度方程",
    subtitle: "ECCO4 daily budget fields + OISST daily SST + ERA5 atmosphere",
    cards: [
      { title: "数据", body: "ECCO4 v4r4\n流场、温度、闭合热预算\nOISST：日SST，0.25°\nERA5：潜热/感热、长短波\n大气水汽与热输送\n气候态：1992–2017" },
      { title: "被动示踪", body: "2014–2015每月初始化\n共24次前向试验\n1 mol m⁻³ → 2016-03-01\n合成取最大值\n保留 ≥0.1 mol m⁻³\n伴随回溯至2014-09-01" },
      { title: "粒子与积分", body: "粒子回溯：2016-03-01\n→ 2013-09-01\nΔΘ′_p = ∫Σ_i R_i[x_p(t),t]dt\nΨ_GOA = ∫v dz\nΨ_CC = ∫w dx_onshore\n逐粒子预算后求和" },
    ],
    strip: "MHW体积：20°N–60°N，180°W–90°W ｜ T′ > 1.5°C ｜ 名义深度 ≤ 200 m",
    takeaway: "对应Q1–Q3：粒子给路径，沿轨迹预算给去向，ERA5通量与环流用于反馈判断。",
    sources: [
      "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint; Sections 4.1 and 4.3-4.5)",
      "Local PDF: /Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811/mhw_preprint.pdf, PDF pages 7-8.",
      "The compact trajectory integral and proxy streamfunction notation transcribe the method definitions in Sections 4.4-4.5; they are not separately numbered equations in the paper.",
    ],
  },
  {
    eyebrow: "文献三｜残差分解",
    title: "先剥离典型ENSO成分，再识别远东太平洋的独立贡献",
    subtitle: "Leishan Jiang et al. (2026) | Equations 1–2",
    cards: [
      { title: "Eq. 1｜FEP分解", body: "T(t) = E·T_N34(t) + T_R(t)\n\nT：FEP SSTA\nE·T_N34：典型ENSO成分\nT_R：FEP残差成分" },
      { title: "Eq. 2｜多元回归", body: "X(t,x,y) = α(x,y)T_N34(t)\n+ β(x,y)T_R(t) + ε(t,x,y)\n\nX：SST / 风 / 降水 / 次表层\nα：ENSO；β：FEP" },
      { title: "重建与检验", body: "X_N34 = αT_N34\nX_R = βT_R\nlead–lag correlation\n15年滑动窗口\nAGCM强迫验证β相关响应" },
    ],
    strip: "N34：5°S–5°N，170°W–120°W   ｜   FEP：5°S–5°N，90°W–80°W",
    takeaway: "对应Q3：T_R隔离东部先行增暖；β场给出东北风与弱西风的门控坐标。",
    sources: [
      "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026; Equations 1-2, Section 2.2)",
      "Local PDF: /Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf, PDF pages 2 and 5.",
    ],
  },
  {
    eyebrow: "文献三｜观测与模式",
    title: "观测分解、事件筛选与AGCM试验共同支撑因果判断",
    subtitle: "Monthly 1960–2024 | MJJ | NE wind: 3°–7°N, 180°E–130°W",
    cards: [
      { title: "观测数据", body: "ERSSTv5：SST\nERA5：925 hPa风、降水\nORAS5：海洋温度/次表层结构\n异常：1960–2024气候态\n全部去线性趋势" },
      { title: "事件筛选", body: "El Niño：N34 > +0.5°C\n连续 ≥5个重叠三月季\nFEP > 1 SD\nT_R > ENSO成分\nENSO成分 < 1 SD" },
      { title: "ECHAM4.6试验", body: "T42 ≈ 2.8°；19层至10 hPa\nCTRL：1991–2020 SST\n积分20年\n4–7月叠加SSTA\n20成员集合\n响应 = 敏感试验 − CTRL" },
    ],
    strip: "FEP-dominant：1965/66 · 1969/70 · 1972/73 · 1976/77 · 2023/24 ｜ 2014/15排除",
    takeaway: "对应Q3：观测提供统计时序，AGCM检验FEP异常能否主动激发东北风并削弱西风。",
    sources: [
      "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026; Sections 2.1 and 2.3)",
      "Local PDF: /Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf, PDF pages 2-3.",
      "Analyzed El Nino events: 1963/64, 1965/66, 1968/69, 1969/70, 1972/73, 1976/77, 1977/78, 1979/80, 1982/83, 1986/87, 1987/88, 1991/92, 1994/95, 1997/98, 2002/03, 2004/05, 2006/07, 2009/10, 2015/16, 2018/19, 2019/20, 2023/24; 2014/15 excluded.",
    ],
  },
];

for (let i = 0; i < specs.length; i += 1) {
  const slide = presentation.slides.items[i + 5];
  if (i % 2 === 0) editThreeCardSlide13(slide, specs[i]);
  else editThreeCardSlide19(slide, specs[i]);
}

await fs.mkdir(PREVIEW, { recursive: true });
await fs.mkdir(LAYOUT, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(PREVIEW, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(LAYOUT, `${stem}.layout.json`), await layout.text());
}
await writeBlob(path.join(TMP, "final-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));

const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,notes,layout", maxChars: 1500000 });
await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUT);
console.log(JSON.stringify({ output: OUT, slides: presentation.slides.items.length, revision: inspect.revision }, null, 2));
