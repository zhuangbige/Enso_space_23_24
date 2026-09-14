import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_simplified_verified_20260811");
const SOURCE = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_精简核对版_20260811.pptx",
);
const OUTPUT = path.join(TMP, "native-equation-stage.pptx");

const FORMULA = {
  formula1Base: "chakravorty-formula-data-text-28",
  formula1Sub: "chakravorty-formula-data-text-29",
  formula1Rest: "chakravorty-formula-data-text-30",
  formula2Base: "chakravorty-formula-data-text-31",
  formula2Sub: "chakravorty-formula-data-text-32",
  formula2Rest: "chakravorty-formula-data-text-33",
  card1Body: "chakravorty-formula-data-text-34",
  card2Body: "chakravorty-formula-data-text-37",
  card3Body: "chakravorty-formula-data-text-40",
  strip: "chakravorty-formula-data-text-42",
};

function shapeByName(slide, name, required = true) {
  const shape = slide.shapes.items.find((item) => item.name === name);
  if (!shape && required) throw new Error(`Missing shape ${name}`);
  return shape;
}

function deleteShape(slide, name) {
  const shape = shapeByName(slide, name, false);
  if (shape) shape.delete();
}

function setBody(slide, name, text, position) {
  const shape = shapeByName(slide, name);
  shape.text = text;
  shape.position = position;
  shape.text.style = {
    ...shape.text.style,
    fontSize: 16.5,
    typeface: "PingFang SC",
    color: "#0A2234",
    autoFit: "shrinkText",
    alignment: "left",
    verticalAlignment: "top",
  };
}

function styleMarker(shape, fontSize = 17) {
  shape.text.style = {
    ...shape.text.style,
    fontSize,
    typeface: "Cambria Math",
    color: "#0A2234",
    autoFit: "shrinkText",
    alignment: "left",
    verticalAlignment: "middle",
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  };
}

function reuseMarker(slide, shapeName, marker, position, fontSize = 17) {
  const shape = shapeByName(slide, shapeName);
  shape.text = marker;
  shape.position = position;
  shape.name = `native-office-math-${marker.slice(2)}`;
  styleMarker(shape, fontSize);
  return shape;
}

function addMarker(slide, marker, position, fontSize = 17) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: `native-office-math-${marker.slice(2)}`,
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = marker;
  styleMarker(shape, fontSize);
  return shape;
}

function prepareFormulaSlide(slide) {
  for (const name of [
    FORMULA.formula1Base,
    FORMULA.formula1Sub,
    FORMULA.formula2Base,
    FORMULA.formula2Sub,
  ]) deleteShape(slide, name);
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
if (presentation.slides.items.length !== 15) throw new Error("Expected 15 slides");
const slide = (number) => presentation.slides.items[number - 1];

// Slide 4: fixed-depth OHC and anomaly construction.
prepareFormulaSlide(slide(4));
reuseMarker(slide(4), FORMULA.formula1Rest, "EQ04_01", { left: 74, top: 270, width: 290, height: 31 }, 16);
reuseMarker(slide(4), FORMULA.formula2Rest, "EQ04_02", { left: 74, top: 305, width: 290, height: 31 }, 15.5);
addMarker(slide(4), "EQ04_03", { left: 472, top: 270, width: 290, height: 48 }, 16.5);
setBody(
  slide(4),
  FORMULA.card1Body,
  "先在每个格点积分到300 m\n再按cosφ作纬向加权平均\n\nĈₘ与bₘ为同一日历月的均值和线性趋势",
  { left: 74, top: 350, width: 290, height: 167 },
);
setBody(
  slide(4),
  FORMULA.card2Body,
  "每个经度、每个日历月分别去除气候态和线性趋势\n\n输出单位：GJ m⁻²",
  { left: 472, top: 335, width: 290, height: 182 },
);
setBody(
  slide(4),
  FORMULA.card3Body,
  "事件窗：前一年Jul至发展年Nov\n面板：1997 / 2015 / 2023\n\n虚线：140°W\n黑线：零异常线\n三幅图使用同一色标",
  { left: 870, top: 275, width: 290, height: 242 },
);

// Slide 6: Lagrangian weights, trajectory equations and summary statistics.
prepareFormulaSlide(slide(6));
reuseMarker(slide(6), FORMULA.formula1Rest, "EQ06_01", { left: 74, top: 270, width: 290, height: 31 }, 17);
reuseMarker(slide(6), FORMULA.formula2Rest, "EQ06_02", { left: 74, top: 305, width: 290, height: 31 }, 16.5);
addMarker(slide(6), "EQ06_03", { left: 472, top: 268, width: 290, height: 93 }, 16.5);
addMarker(slide(6), "EQ06_04", { left: 870, top: 268, width: 290, height: 128 }, 14.5);
setBody(
  slide(6),
  FORMULA.card1Body,
  "T̂ₘ,₋ₑ：排除事件年的同月线性预期\n保留正温度异常粒子\n\nωₚ用于比例加权，不表示焦耳",
  { left: 74, top: 350, width: 290, height: 167 },
);
setBody(
  slide(6),
  FORMULA.card2Body,
  "五日场线性插值\n采用midpoint RK2\n从6月末反向积分到1月初",
  { left: 472, top: 375, width: 290, height: 142 },
);
setBody(
  slide(6),
  FORMULA.card3Body,
  "第一式：东移距离\n第二式：加权中位数\n第三式：活动轨迹权重占比",
  { left: 870, top: 410, width: 290, height: 107 },
);

// Slide 8: independent arrival estimates.
prepareFormulaSlide(slide(8));
reuseMarker(slide(8), FORMULA.formula1Rest, "EQ08_01", { left: 74, top: 270, width: 290, height: 38 }, 15);
reuseMarker(slide(8), FORMULA.formula2Rest, "EQ08_02", { left: 74, top: 312, width: 290, height: 38 }, 14.5);
addMarker(slide(8), "EQ08_03", { left: 472, top: 270, width: 290, height: 82 }, 16);
setBody(
  slide(8),
  FORMULA.card1Body,
  "四侧边界先作统一法向速度校正\n校正后净体积输送为0\n\n西边界正值表示进入东箱",
  { left: 74, top: 365, width: 290, height: 152 },
);
setBody(
  slide(8),
  FORMULA.card2Body,
  "T′与Q′均去除同月气候态和线性趋势\n\n单位统一为ZJ",
  { left: 472, top: 370, width: 290, height: 147 },
);
setBody(
  slide(8),
  FORMULA.card3Body,
  "140°W累计输入\n东箱固定层储热增加\n\n两者独立计算\n单位统一为ZJ",
  { left: 870, top: 275, width: 290, height: 242 },
);
const strip8 = shapeByName(slide(8), FORMULA.strip, false);
if (strip8) strip8.text = "月样本采用梯形积分；能量统一换算为ZJ。";

// Slide 10: fixed-layer energy budget and plotted-sign definitions.
prepareFormulaSlide(slide(10));
reuseMarker(slide(10), FORMULA.formula1Rest, "EQ10_01", { left: 74, top: 270, width: 290, height: 36 }, 14.5);
reuseMarker(slide(10), FORMULA.formula2Rest, "EQ10_02", { left: 74, top: 310, width: 290, height: 36 }, 14.5);
addMarker(slide(10), "EQ10_03", { left: 472, top: 268, width: 290, height: 148 }, 14.5);
setBody(
  slide(10),
  FORMULA.card1Body,
  "ΔH′ₑ：东箱OHC′变化\nQ′W、Q′E、Q′N、Q′S：四侧焓输送\nQ′ₛ：净海表热通量\nR′：未闭合项",
  { left: 74, top: 365, width: 290, height: 152 },
);
setBody(
  slide(10),
  FORMULA.card2Body,
  "Lᴴ：储热损失\nEᵂ、Eᴱ、Eᴺ、Eˢ：四向输出\nLˢ：海表散热\n\n正值统一表示离开东箱",
  { left: 472, top: 425, width: 290, height: 92 },
);

// Slide 12: one native equation array for partial-correlation residualization.
prepareFormulaSlide(slide(12));
deleteShape(slide(12), FORMULA.formula1Rest);
deleteShape(slide(12), FORMULA.formula2Rest);
addMarker(slide(12), "EQ12_01", { left: 74, top: 268, width: 290, height: 108 }, 16.5);
setBody(
  slide(12),
  FORMULA.card1Body,
  "图(a)：A为JFM 140°W到达量\n图(b)、(c)：A为Jan–Jun 140°W到达量",
  { left: 74, top: 398, width: 290, height: 119 },
);

const exported = await PresentationFile.exportPptx(presentation);
await exported.save(OUTPUT);
const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,notes,layout", maxChars: 1200000 });
await fs.writeFile(path.join(TMP, "native-equation-stage.inspect.ndjson"), inspect.ndjson, "utf8");
console.log(JSON.stringify({ output: OUTPUT, slides: presentation.slides.items.length }, null, 2));
