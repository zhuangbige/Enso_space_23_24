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

const starter = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_insert_ctcp_formula_sHy1ie/template-starter.pptx";
const output = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与去向_加入CTCP定义公式_20260809.pptx";

const presentation = await PresentationFile.importPptx(await FileBlob.load(starter));
const slide = presentation.slides.getItem(1);
const target = slide.shapes.items.find((shape) => shape.name === "prior-body");
if (!target) throw new Error("Could not locate slide 2 shape named prior-body");

target.position = { left: 54, top: 242, width: 440, height: 356 };
target.text.style = {
  fontSize: 26,
  typeface: "PingFang SC",
  color: "#0A2133",
  bold: true,
  lineSpacing: 1.02,
  alignment: "left",
  verticalAlignment: "top",
  autoFit: "shrinkText",
  wrap: "square",
  insets: { top: 0, right: 0, bottom: 0, left: 0 },
};
target.text.set([
  {
    runs: [{ run: "分类公式", textStyle: { bold: true, color: "#2C7FB8", fontSize: "28px", typeface: "PingFang SC" } }],
    spaceAfter: 4,
  },
  {
    runs: ["N_CT = N₃ − αN₄"],
  },
  {
    runs: ["N_CP = N₄ − αN₃"],
  },
  {
    runs: ["α = 0.4（N₃N₄ > 0），否则 α = 0"],
    spaceAfter: 10,
  },
  {
    runs: [{ run: "事件判据", textStyle: { bold: true, color: "#2C7FB8", fontSize: "28px", typeface: "PingFang SC" } }],
    spaceAfter: 4,
  },
  {
    runs: [{ run: "CT：", textStyle: { bold: true } }, "HF–N_CT 与 CHI > 0.8°C，持续 ≥ 5个月"],
  },
  {
    runs: [{ run: "CP：", textStyle: { bold: true } }, "HF–N_CP 与 CHI > 0.8°C，持续 ≥ 5个月且非CT"],
  },
]);

slide.speakerNotes.append(
  "\n[Sources]\n" +
  "- Chakravorty et al. (2021), Journal of Geophysical Research: Oceans, https://doi.org/10.1029/2020JC017075\n" +
  "- CT/CP transformation follows Ren and Jin (2011), as adopted by Chakravorty et al. (2021).\n" +
  "[/Sources]"
);
slide.speakerNotes.setVisible(true);

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(output);
