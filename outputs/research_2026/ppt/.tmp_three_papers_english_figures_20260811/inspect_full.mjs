import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const source = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_非阈值重构版_20260810.pptx";
const target = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811/template-inspect/template-inspect-full.ndjson";

const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
const result = await presentation.inspect({
  kind: "slide,textbox,shape,image,table,chart",
  maxChars: 1000000,
});
await fs.writeFile(target, result.ndjson, "utf8");
console.log(JSON.stringify({ target, truncated: result.truncated, chars: result.ndjson.length }));
