import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const p = await PresentationFile.importPptx(await FileBlob.load("./template-starter.pptx"));
const result = p.help("*", {
  search: "speaker notes|slide.notes|notes.setText|add notes|set notes",
  include: ["index", "examples", "notes"],
  maxChars: 20000,
});
console.log(result.ndjson);
