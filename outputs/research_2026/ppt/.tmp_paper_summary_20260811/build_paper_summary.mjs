import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_paper_summary_20260811");
const FIG = path.join(TMP, "paper-figures");
const OUT = path.join(ROOT, "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_三文献图解扩展版_20260811.pptx");
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

async function replaceImages(slide, filename, alt) {
  const bytes = await fs.readFile(path.join(FIG, filename));
  if (slide.images.items.length !== 2) throw new Error(`Expected two inherited image slots, got ${slide.images.items.length}`);
  const frame = slide.images.items[0].frame;
  for (const image of [...slide.images.items]) image.delete();
  const inserted = slide.images.add({
    blob: bytes,
    contentType: "image/png",
    alt,
    position: frame,
    fit: "contain",
  });
  inserted.name = filename.replace(/\.png$/, "");
}

async function editLiteratureSlide(slide, spec) {
  rewrite(slide, "22", spec.eyebrow);
  rewrite(slide, "2", spec.title);
  rewrite(slide, "4", spec.sourceLine);
  for (const id of ["6", "8", "10", "12"]) rewrite(slide, id, "");
  for (const id of ["5", "7", "9", "11"]) shapeById(slide, id).delete();
  rewrite(slide, "15", spec.card1Title);
  rewrite(slide, "16", spec.card1Body);
  rewrite(slide, "18", spec.card2Title);
  rewrite(slide, "19", spec.card2Body);
  rewrite(slide, "21", spec.takeaway);
  await replaceImages(slide, spec.figure, spec.alt);
  setSources(slide, spec.sources);
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(path.join(TMP, "template-starter.pptx")));
if (presentation.slides.items.length !== 19) throw new Error(`Expected 19 slides, got ${presentation.slides.items.length}`);

const specs = [
  {
    eyebrow: "文献一｜ENSO充放电",
    title: "CT与CP的差异，不只是暖中心位置，而是充放电路径",
    sourceLine: "Original Figure 8 | Chakravorty et al. (2021)",
    card1Title: "做了什么",
    card1Body: "CT/CP事件合成\nWWV + 纬向/经向输送\n事件前后两年演变",
    card2Title: "核心结论",
    card2Body: "CT：蓄积后极向放电\nCP：输送弱、调整同步",
    takeaway: "对应Q1–Q2：提供事件类型与边界输送框架；但仍未回答单次暖量是否真正到达、最终分到哪里。",
    figure: "chakravorty_fig8.png",
    alt: "Original Figure 8 comparing zonal transport, meridional transport and warm-water volume for CT and CP El Nino",
    sources: [
      "https://doi.org/10.1029/2020JC017075 (Chakravorty et al., 2021; accessed 2026-08-11)",
      "Local source: tmp/pdfs/chakravorty_2021_recharge_discharge_enso_flavors.pdf, PDF page 12, original Figure 8.",
    ],
  },
  {
    eyebrow: "文献二｜拉格朗日热预算",
    title: "追踪同一团异常暖水，才能把建立、维持与衰减过程闭合",
    sourceLine: "Original Figure 3a | Wenrui Jiang et al. (2025 preprint)",
    card1Title: "方法创新",
    card1Body: "3D粒子轨迹 + 沿轨迹热预算\n平流、扩散、外部加热分解",
    card2Title: "核心结论",
    card2Body: "建立、维持由不同过程控制\n输送与海表通量共同参与",
    takeaway: "对应Q1–Q3：借鉴“轨迹—预算—分期—反馈”结构，不直接移植北太平洋机制。",
    figure: "mhw_fig3a_wide.png",
    alt: "Original Figure 3a cumulative Lagrangian heat-budget contributions for the North Pacific marine heatwave",
    sources: [
      "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint; accessed 2026-08-11)",
      "Local source: outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811/mhw_preprint.pdf, PDF page 15, original Figure 3a.",
    ],
  },
  {
    eyebrow: "文献三｜2023耦合异常",
    title: "2023先建立远东太平洋暖异常，随后出现更强东北风和更弱西风",
    sourceLine: "Original Figure 1b,f | Leishan Jiang et al. (2026)",
    card1Title: "对比框架",
    card1Body: "2023 / post-1980 / pre-1980\nHovmöller + MJJ风—雨—SST",
    card2Title: "关键异常",
    card2Body: "3–7°N东北风增强\n中太平洋西风响应偏弱",
    takeaway: "对应Q3：论文给出大气门控坐标；当前结果进一步把JFM北向热量分流放到它之前。",
    figure: "leishan_jiang_fig1bf.png",
    alt: "Original Figure 1b and 1f showing 2023 eastern Pacific warming evolution and MJJ air-sea anomalies",
    sources: [
      "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026; accessed 2026-08-11)",
      "Local source: /Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf, PDF page 4, original Figure 1b and 1f.",
    ],
  },
];

for (let i = 0; i < specs.length; i += 1) {
  await editLiteratureSlide(presentation.slides.items[i + 2], specs[i]);
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

const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,notes,layout", maxChars: 1200000 });
await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(OUT);
console.log(JSON.stringify({ output: OUT, slides: presentation.slides.items.length, revision: inspect.revision }, null, 2));
