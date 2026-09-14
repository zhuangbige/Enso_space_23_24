import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const source = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_第三问精简版_20260811.pptx";
const output = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_simplified_verified_20260811/source-full-inspect.ndjson";
const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
const result = await presentation.inspect({
  kind: "slide,textbox,shape,image,notes,layout",
  include: "id,slide,name,title,text,textPreview,bbox,isPlaceholder",
  maxChars: 2000000,
});
await fs.writeFile(output, result.ndjson, "utf8");
console.log(JSON.stringify({ slideCount: presentation.slides.items.length, truncated: result.truncated ?? false, output }));
