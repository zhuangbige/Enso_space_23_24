import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const TMP = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_paper_summary_20260811";
const p = await PresentationFile.importPptx(await FileBlob.load(path.join(TMP, "template-starter.pptx")));
for (const slideIndex of [2, 3, 4]) {
  const slide = p.slides.items[slideIndex];
  console.log("SLIDE", slideIndex + 1, "shapes", slide.shapes.items.length, "images", slide.images.items.length);
  for (const shape of slide.shapes.items) {
    const t = shape.text ? String(shape.text) : "";
    console.log(JSON.stringify({ id: shape.id, name: shape.name, text: t.slice(0, 80), type: shape.type }));
  }
  for (const image of slide.images.items) {
    console.log(JSON.stringify({ imageId: image.id, name: image.name, frame: image.frame, fit: image.fit, crop: image.crop }));
  }
}
