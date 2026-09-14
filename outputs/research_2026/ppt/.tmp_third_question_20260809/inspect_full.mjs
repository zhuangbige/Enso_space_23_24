import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const source = process.argv[2] ?? "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/厄尔尼诺异常暖量到达与去向_审查修订版_20260809.pptx";
const out = process.argv[3] ?? "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_third_question_20260809/template-inspect-full.ndjson";

const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
const snapshot = await presentation.inspect({
  kind: "slide,textbox,shape,image,table,chart,notes,thread,layout",
  include: "id,slide,name,title,text,textPreview,textChars,textLines,bbox,bboxUnit,chartType,isPlaceholder,placeholders",
  maxChars: 1000000,
});
await fs.writeFile(out, `${snapshot.ndjson}\n`, "utf8");
console.log(out);
