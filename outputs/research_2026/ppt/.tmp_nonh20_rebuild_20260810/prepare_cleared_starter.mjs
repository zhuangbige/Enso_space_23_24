import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspace = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_nonh20_rebuild_20260810";
const source = path.join(workspace, "template-starter.pptx");
const output = path.join(workspace, "template-starter-cleared.pptx");
const layoutDir = path.join(workspace, "template-starter-cleared-layout");

const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
await fs.mkdir(layoutDir, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  slide.shapes.deleteAll();
  slide.speakerNotes.clear();
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(layoutDir, `starter-cleared-slide-${String(index + 1).padStart(2, "0")}.layout.json`), await layout.text());
}
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(output);
console.log(JSON.stringify({ output, slides: presentation.slides.items.length }, null, 2));
