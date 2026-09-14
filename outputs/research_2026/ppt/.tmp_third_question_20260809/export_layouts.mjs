import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const input = process.argv[2];
const outDir = process.argv[3];
if (!input || !outDir) throw new Error("Usage: node export_layouts.mjs <pptx> <out-dir>");
await fs.mkdir(outDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(input));
for (let index = 0; index < presentation.slides.count; index += 1) {
  const slide = presentation.slides.getItem(index);
  const layout = await presentation.export({ slide, format: "layout" });
  const bytes = new Uint8Array(await layout.arrayBuffer());
  await fs.writeFile(`${outDir}/final-slide-${String(index + 1).padStart(2, "0")}.layout.json`, bytes);
}
console.log(`${presentation.slides.count} layouts written to ${outDir}`);
