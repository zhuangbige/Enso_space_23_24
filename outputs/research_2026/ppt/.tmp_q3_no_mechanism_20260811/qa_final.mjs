import fs from "node:fs/promises";
import path from "node:path";

const extracted = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_q3_no_mechanism_20260811/qa-unzip-final/ppt/slides";
const files = (await fs.readdir(extracted)).filter((name) => /^slide\d+\.xml$/.test(name)).sort();
const emptyPlaceholders = [];

for (const file of files) {
  const xml = await fs.readFile(path.join(extracted, file), "utf8");
  const shapes = xml.match(/<p:sp\b[\s\S]*?<\/p:sp>/g) ?? [];
  for (let index = 0; index < shapes.length; index += 1) {
    const shape = shapes[index];
    if (!shape.includes("<p:ph")) continue;
    const text = [...shape.matchAll(/<a:t>([\s\S]*?)<\/a:t>/g)]
      .map((match) => match[1]
        .replace(/&amp;/g, "&")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">"))
      .join("")
      .trim();
    if (!text) emptyPlaceholders.push({ file, shapeIndex: index + 1 });
  }
}

const report = {
  slideXmlFiles: files.length,
  expectedSlides: 38,
  emptyPlaceholders,
  status: files.length === 38 && emptyPlaceholders.length === 0 ? "pass" : "fail",
};
console.log(JSON.stringify(report, null, 2));
if (report.status !== "pass") process.exitCode = 1;
