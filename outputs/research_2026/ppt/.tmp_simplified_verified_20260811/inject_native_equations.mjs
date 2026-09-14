import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";

const require = createRequire(import.meta.url);
const JSZip = require("/Users/daiyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/jszip");

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_simplified_verified_20260811");
const SOURCE = path.join(TMP, "native-equation-stage.pptx");
const OUTPUT = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_原生公式版_20260811.pptx",
);
const PANDOC = "/opt/homebrew/bin/pandoc";
const MATHML_TO_OMML = "/Applications/Microsoft Word.app/Contents/Resources/mathml2omml.xsl";

const equations = [
  {
    slide: 4,
    marker: "EQ04_01",
    latex: String.raw`H_{300}=\left\langle \rho_0 c_p \int_0^{300\,\mathrm{m}} T\,dz \right\rangle_{\phi}`,
    fallback: "H₃₀₀ = ⟨ρ₀cₚ∫₀³⁰⁰ᵐ T dz⟩ᵩ",
  },
  {
    slide: 4,
    marker: "EQ04_02",
    latex: String.raw`H'_{300}=H_{300}-\widehat{C}_m-b_m\left(y-\bar{y}_m\right)`,
    fallback: "H′₃₀₀ = H₃₀₀ − Ĉₘ − bₘ(y − ȳₘ)",
  },
  {
    slide: 4,
    marker: "EQ04_03",
    latex: String.raw`\langle H\rangle_{\phi}=\frac{\sum_i H_i\cos\phi_i}{\sum_i\cos\phi_i}`,
    fallback: "⟨H⟩ᵩ = ΣᵢHᵢcosφᵢ / Σᵢcosφᵢ",
  },
  {
    slide: 6,
    marker: "EQ06_01",
    latex: String.raw`T'_p=T_p-\widehat{T}_{m,-e}`,
    fallback: "T′ₚ = Tₚ − T̂ₘ,₋ₑ",
  },
  {
    slide: 6,
    marker: "EQ06_02",
    latex: String.raw`\omega_p=\max\!\left(T'_p,0\right)\cos\phi_p\,\Delta z_p`,
    fallback: "ωₚ = max(T′ₚ,0)cosφₚΔzₚ",
  },
  {
    slide: 6,
    marker: "EQ06_03",
    latex: String.raw`\begin{aligned}\frac{d\lambda}{dt}&=\frac{u}{R\cos\phi}\\[2pt]\frac{d\phi}{dt}&=\frac{v}{R}\\[2pt]\frac{dz}{dt}&=-w\end{aligned}`,
    fallback: "dλ/dt = u/(Rcosφ)\ndφ/dt = v/R\ndz/dt = −w",
  },
  {
    slide: 6,
    marker: "EQ06_04",
    latex: String.raw`\begin{aligned}\Delta\lambda_p&=\lambda_{\mathrm{release}}-\lambda_{\mathrm{source}}\\[2pt]\sum_{\Delta\lambda_p\leq\widetilde{\Delta\lambda}}\omega_p&=\frac{1}{2}\sum_p\omega_p\\[2pt]f_{\mathrm{active}}&=\frac{\sum_{p\in\mathrm{active}}\omega_p}{\sum_p\omega_p}\end{aligned}`,
    fallback: "Δλₚ = λrelease − λsource\nΣωₚ = ½Σωₚ\nfactive = Σωactive / Σωₚ",
  },
  {
    slide: 8,
    marker: "EQ08_01",
    latex: String.raw`Q_{140^{\circ}\mathrm{W}}=\rho_0c_p\iint u_n\left(T-\bar{T}_b\right)\,dA`,
    fallback: "Q₁₄₀°W = ρ₀cₚ∬uₙ(T − T̄ᵦ)dA",
  },
  {
    slide: 8,
    marker: "EQ08_02",
    latex: String.raw`A_{\mathrm{Jan-Jun}}=\int_{\mathrm{Jan}}^{\mathrm{Jun}}Q'_{140^{\circ}\mathrm{W}}(t)\,dt`,
    fallback: "AJan–Jun = ∫JanJun Q′₁₄₀°W(t)dt",
  },
  {
    slide: 8,
    marker: "EQ08_03",
    latex: String.raw`\begin{aligned}H'_e(t)&=\rho_0c_p\iiint_eT'\,dV\\[4pt]\Delta H'_e&=H'_e(\mathrm{Jun})-H'_e(\mathrm{Jan})\end{aligned}`,
    fallback: "H′ₑ(t) = ρ₀cₚ∭ₑT′dV\nΔH′ₑ = H′ₑ(Jun) − H′ₑ(Jan)",
  },
  {
    slide: 10,
    marker: "EQ10_01",
    latex: String.raw`\Delta H'_e=Q'_W+Q'_E+Q'_N+Q'_S+Q'_s+R'`,
    fallback: "ΔH′ₑ = Q′W + Q′E + Q′N + Q′S + Q′ₛ + R′",
  },
  {
    slide: 10,
    marker: "EQ10_02",
    latex: String.raw`R'=\Delta H'_e-\left(Q'_W+Q'_E+Q'_N+Q'_S\right)-Q'_s`,
    fallback: "R′ = ΔH′ₑ − (Q′W + Q′E + Q′N + Q′S) − Q′ₛ",
  },
  {
    slide: 10,
    marker: "EQ10_03",
    latex: String.raw`\begin{aligned}L_H&=-\Delta H'_e & E_W&=-Q'_W\\E_E&=-Q'_E & E_N&=-Q'_N\\E_S&=-Q'_S & L_s&=-Q'_s\end{aligned}`,
    fallback: "LH = −ΔH′ₑ   EW = −Q′W\nEE = −Q′E   EN = −Q′N\nES = −Q′S   Ls = −Q′ₛ",
  },
  {
    slide: 12,
    marker: "EQ12_01",
    latex: String.raw`\begin{aligned}X_r&=X-\left(a_x+b_xA\right)\\[3pt]Y_r&=Y-\left(a_y+b_yA\right)\\[3pt]r_{XY\cdot A}&=\operatorname{corr}\!\left(X_r,Y_r\right)\end{aligned}`,
    fallback: "Xᵣ = X − (aₓ + bₓA)\nYᵣ = Y − (aᵧ + bᵧA)\nrXY·A = corr(Xᵣ,Yᵣ)",
  },
];

function escapeXml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function latexToMathMl(latex) {
  const result = spawnSync(PANDOC, ["-f", "markdown", "-t", "html5", "--mathml"], {
    input: `$${latex}$`,
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
  });
  if (result.status !== 0) throw new Error(`Pandoc failed for ${latex}: ${result.stderr}`);
  const match = result.stdout.match(/<math[\s\S]*?<\/math>/);
  if (!match) throw new Error(`No MathML generated for ${latex}: ${result.stdout}`);
  return match[0];
}

function mathMlToOmml(mathml) {
  const result = spawnSync("xsltproc", [MATHML_TO_OMML, "-"], {
    input: mathml,
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
  });
  if (result.status !== 0) throw new Error(`MathML to OMML conversion failed: ${result.stderr}`);
  return result.stdout.replace(/^<\?xml[^>]*>\s*/u, "").trim();
}

function replaceMarkerShape(xml, equation, omml) {
  const markerTag = `<a:t>${equation.marker}</a:t>`;
  const markerIndex = xml.indexOf(markerTag);
  if (markerIndex < 0) throw new Error(`Marker ${equation.marker} not found on slide ${equation.slide}`);
  if (xml.indexOf(markerTag, markerIndex + markerTag.length) >= 0) {
    throw new Error(`Marker ${equation.marker} occurs more than once on slide ${equation.slide}`);
  }

  const shapeStart = xml.lastIndexOf("<p:sp>", markerIndex);
  const shapeEndClose = xml.indexOf("</p:sp>", markerIndex);
  if (shapeStart < 0 || shapeEndClose < 0) throw new Error(`Could not locate shape for ${equation.marker}`);
  const shapeEnd = shapeEndClose + "</p:sp>".length;
  const shapeXml = xml.slice(shapeStart, shapeEnd);
  const relativeMarker = shapeXml.indexOf(markerTag);
  const runStart = shapeXml.lastIndexOf("<a:r>", relativeMarker);
  const runEndClose = shapeXml.indexOf("</a:r>", relativeMarker);
  if (runStart < 0 || runEndClose < 0) throw new Error(`Could not locate text run for ${equation.marker}`);
  const runEnd = runEndClose + "</a:r>".length;

  const choiceShape =
    shapeXml.slice(0, runStart) +
    `<a14:m xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">${omml}</a14:m>` +
    shapeXml.slice(runEnd);
  const fallbackShape = shapeXml.replace(markerTag, `<a:t>${escapeXml(equation.fallback)}</a:t>`);
  const alternate =
    `<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">` +
    `<mc:Choice Requires="a14" xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">${choiceShape}</mc:Choice>` +
    `<mc:Fallback>${fallbackShape}</mc:Fallback>` +
    `</mc:AlternateContent>`;
  return xml.slice(0, shapeStart) + alternate + xml.slice(shapeEnd);
}

const input = await fs.readFile(SOURCE);
const zip = await JSZip.loadAsync(input);
const manifest = [];

for (const equation of equations) {
  const slidePath = `ppt/slides/slide${equation.slide}.xml`;
  const slideFile = zip.file(slidePath);
  if (!slideFile) throw new Error(`Missing ${slidePath}`);
  let xml = await slideFile.async("string");
  const mathml = latexToMathMl(equation.latex);
  const omml = mathMlToOmml(mathml);
  xml = replaceMarkerShape(xml, equation, omml);
  zip.file(slidePath, xml);
  manifest.push({ slide: equation.slide, marker: equation.marker, latex: equation.latex, ommlChars: omml.length });
}

for (const slideNumber of [4, 6, 8, 10, 12]) {
  const xml = await zip.file(`ppt/slides/slide${slideNumber}.xml`).async("string");
  const textMarkers = xml.match(/<a:t>EQ\d{2}_\d{2}<\/a:t>/g) ?? [];
  if (textMarkers.length) throw new Error(`Unconverted markers remain on slide ${slideNumber}: ${textMarkers.join(", ")}`);
}

const output = await zip.generateAsync({
  type: "nodebuffer",
  compression: "DEFLATE",
  compressionOptions: { level: 6 },
  mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
});
await fs.writeFile(OUTPUT, output);
await fs.writeFile(path.join(TMP, "native-equation-manifest.json"), JSON.stringify(manifest, null, 2), "utf8");
console.log(JSON.stringify({ output: OUTPUT, equations: equations.length, bytes: output.length }, null, 2));
