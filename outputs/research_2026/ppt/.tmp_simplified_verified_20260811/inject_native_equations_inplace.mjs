import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";

const require = createRequire(import.meta.url);
const JSZip = require("/Users/daiyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/jszip");

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_simplified_verified_20260811");
const SOURCE = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_精简核对版_20260811.pptx",
);
const OUTPUT = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_原生公式版_20260811.pptx",
);
const PANDOC = "/opt/homebrew/bin/pandoc";
const MATHML_TO_OMML = "/Applications/Microsoft Word.app/Contents/Resources/mathml2omml.xsl";

const groups = [
  {
    slide: 4,
    shape: "chakravorty-formula-data-text-30",
    equations: [
      ["H₃₀₀ = ⟨ρ₀cₚ∫₀³⁰⁰ T dz⟩ᵩ", String.raw`H_{300}=\left\langle\rho_0c_p\int_0^{300\,\mathrm{m}}T\,dz\right\rangle_{\phi}`],
    ],
  },
  {
    slide: 4,
    shape: "chakravorty-formula-data-text-33",
    equations: [
      ["H′₃₀₀ = H₃₀₀ − Ĉₘ − bₘ(y−ȳₘ)", String.raw`H'_{300}=H_{300}-\widehat C_m-b_m\left(y-\bar y_m\right)`],
    ],
  },
  {
    slide: 4,
    shape: "chakravorty-formula-data-text-37",
    equations: [
      ["⟨H⟩ᵩ = ΣᵢHᵢcosφᵢ / Σᵢcosφᵢ", String.raw`\langle H\rangle_{\phi}=\frac{\sum_iH_i\cos\phi_i}{\sum_i\cos\phi_i}`],
    ],
  },
  {
    slide: 6,
    shape: "chakravorty-formula-data-text-30",
    equations: [["T′ₚ = Tₚ − T̂ₘ,₋ₑ", String.raw`T'_p=T_p-\widehat T_{m,-e}`]],
  },
  {
    slide: 6,
    shape: "chakravorty-formula-data-text-33",
    equations: [["ωₚ = max(T′ₚ,0)cosφₚΔzₚ", String.raw`\omega_p=\max\!\left(T'_p,0\right)\cos\phi_p\,\Delta z_p`]],
  },
  {
    slide: 6,
    shape: "chakravorty-formula-data-text-37",
    equations: [
      ["dλ/dt = u/(Rcosφ)", String.raw`\frac{d\lambda}{dt}=\frac{u}{R\cos\phi}`],
      ["dφ/dt = v/R", String.raw`\frac{d\phi}{dt}=\frac{v}{R}`],
      ["dz/dt = −w", String.raw`\frac{dz}{dt}=-w`],
    ],
  },
  {
    slide: 6,
    shape: "chakravorty-formula-data-text-40",
    equations: [
      ["Δλₚ = λᵣₑₗₑₐₛₑ − λₛₒᵤᵣcₑ", String.raw`\Delta\lambda_p=\lambda_{\mathrm{release}}-\lambda_{\mathrm{source}}`],
      ["加权中位数：累计ωₚ达到0.5Σωₚ", String.raw`\sum_{\Delta\lambda_p\leq\widetilde{\Delta\lambda}}\omega_p=\frac{1}{2}\sum_p\omega_p`],
      ["活动轨迹权重占比：Σωₚ,active / Σωₚ", String.raw`f_{\mathrm{active}}=\frac{\sum_{p\in\mathrm{active}}\omega_p}{\sum_p\omega_p}`],
    ],
  },
  {
    slide: 8,
    shape: "chakravorty-formula-data-text-30",
    equations: [["Q₁₄₀W = ρ₀cₚ ∬uₙ(T−T̄ᵦ)dA", String.raw`Q_{140^{\circ}\mathrm{W}}=\rho_0c_p\iint u_n\left(T-\bar T_b\right)\,dA`]],
  },
  {
    slide: 8,
    shape: "chakravorty-formula-data-text-33",
    equations: [["Aᴶᵃⁿ–ᴶᵘⁿ = ∫Q′₁₄₀W(t)dt", String.raw`A_{\mathrm{Jan-Jun}}=\int_{\mathrm{Jan}}^{\mathrm{Jun}}Q'_{140^{\circ}\mathrm{W}}(t)\,dt`]],
  },
  {
    slide: 8,
    shape: "chakravorty-formula-data-text-37",
    equations: [
      ["H′ₑ(t) = ρ₀cₚ∭ₑT′dV", String.raw`H'_e(t)=\rho_0c_p\iiint_eT'\,dV`],
      ["ΔH′ₑ = H′ₑ(Jun) − H′ₑ(Jan)", String.raw`\Delta H'_e=H'_e(\mathrm{Jun})-H'_e(\mathrm{Jan})`],
    ],
  },
  {
    slide: 10,
    shape: "chakravorty-formula-data-text-30",
    equations: [["ΔH′ₑ = Q′W + Q′E + Q′N + Q′S + Q′ₛ + R′", String.raw`\Delta H'_e=Q'_W+Q'_E+Q'_N+Q'_S+Q'_s+R'`]],
  },
  {
    slide: 10,
    shape: "chakravorty-formula-data-text-33",
    equations: [["R′ = ΔH′ₑ − ΣQ′ − Q′ₛ", String.raw`R'=\Delta H'_e-\left(Q'_W+Q'_E+Q'_N+Q'_S\right)-Q'_s`]],
  },
  {
    slide: 10,
    shape: "chakravorty-formula-data-text-37",
    equations: [
      ["储热损失 = −ΔH′ₑ", String.raw`\text{储热损失}=-\Delta H'_e`],
      ["向西返回 = −Q′W", String.raw`\text{向西返回}=-Q'_W`],
      ["向东输出 = −Q′E", String.raw`\text{向东输出}=-Q'_E`],
      ["向北输出 = −Q′N", String.raw`\text{向北输出}=-Q'_N`],
      ["向南输出 = −Q′S", String.raw`\text{向南输出}=-Q'_S`],
      ["海表散热 = −Q′ₛ", String.raw`\text{海表散热}=-Q'_s`],
    ],
  },
  {
    slide: 12,
    shape: "chakravorty-formula-data-text-30",
    equations: [["Xᵣ = X − (aₓ + bₓA)", String.raw`X_r=X-\left(a_x+b_xA\right)`]],
  },
  {
    slide: 12,
    shape: "chakravorty-formula-data-text-33",
    equations: [["Yᵣ = Y − (aᵧ + bᵧA)", String.raw`Y_r=Y-\left(a_y+b_yA\right)`]],
  },
  {
    slide: 12,
    shape: "chakravorty-formula-data-text-34",
    equations: [["rₓᵧ·A = corr(Xᵣ,Yᵣ)", String.raw`r_{XY\cdot A}=\operatorname{corr}\!\left(X_r,Y_r\right)`]],
  },
];

const plainTextReplacements = [
  [4, "黑线：H′₃₀₀ = 0", "黑线：零异常线"],
  [6, "保留T′ₚ &gt; 0.05°C的粒子", "仅保留正温度异常粒子"],
  [8, "月样本采用梯形积分；1 PW·s = 10⁻⁶ ZJ。", "月样本采用梯形积分；能量统一换算为ZJ。"],
];

// PowerPoint's native equation renderer is slightly taller than a normal text run.
// Reserve explicit vertical space for the two budget equations before creating the
// AlternateContent wrappers, so the editable equations do not collide with body text.
const positionOverrides = [
  [10, "chakravorty-formula-data-text-30", 74, 265, 290, 35],
  [10, "chakravorty-formula-data-text-33", 74, 305, 290, 45],
  [10, "chakravorty-formula-data-text-34", 74, 380, 290, 137],
];

const EMU_PER_CANVAS_UNIT = 9525;

function escapeXml(text) {
  return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function latexToOmml(latex) {
  const pandoc = spawnSync(PANDOC, ["-f", "markdown", "-t", "html5", "--mathml"], {
    input: `$${latex}$`,
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
  });
  if (pandoc.status !== 0) throw new Error(`Pandoc failed for ${latex}: ${pandoc.stderr}`);
  const math = pandoc.stdout.match(/<math[\s\S]*?<\/math>/)?.[0];
  if (!math) throw new Error(`No MathML for ${latex}`);
  const xslt = spawnSync("xsltproc", [MATHML_TO_OMML, "-"], {
    input: math,
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
  });
  if (xslt.status !== 0) throw new Error(`OMML conversion failed for ${latex}: ${xslt.stderr}`);
  return xslt.stdout.replace(/^<\?xml[^>]*>\s*/u, "").trim();
}

function locateShape(xml, shapeName) {
  const nameToken = `name="${shapeName}"`;
  const nameIndex = xml.indexOf(nameToken);
  if (nameIndex < 0) throw new Error(`Shape ${shapeName} not found`);
  const start = xml.lastIndexOf("<p:sp>", nameIndex);
  const endClose = xml.indexOf("</p:sp>", nameIndex);
  if (start < 0 || endClose < 0) throw new Error(`Shape bounds missing for ${shapeName}`);
  return { start, end: endClose + "</p:sp>".length, xml: xml.slice(start, endClose + "</p:sp>".length) };
}

function setShapePosition(xml, shapeName, left, top, width, height) {
  const bounds = locateShape(xml, shapeName);
  const x = Math.round(left * EMU_PER_CANVAS_UNIT);
  const y = Math.round(top * EMU_PER_CANVAS_UNIT);
  const cx = Math.round(width * EMU_PER_CANVAS_UNIT);
  const cy = Math.round(height * EMU_PER_CANVAS_UNIT);
  const updatedShape = bounds.xml.replace(
    /(<a:xfrm[^>]*>[\s\S]*?<a:off\s+)(?:x="[^"]*"\s+y="[^"]*"|y="[^"]*"\s+x="[^"]*")(\s*\/>[\s\S]*?<a:ext\s+)(?:cx="[^"]*"\s+cy="[^"]*"|cy="[^"]*"\s+cx="[^"]*")(\s*\/>)/u,
    `$1x="${x}" y="${y}"$2cx="${cx}" cy="${cy}"$3`,
  );
  if (updatedShape === bounds.xml) throw new Error(`Position transform missing for ${shapeName}`);
  return xml.slice(0, bounds.start) + updatedShape + xml.slice(bounds.end);
}

function replaceRun(shapeXml, target, omml, shapeName) {
  const token = `<a:t>${escapeXml(target)}</a:t>`;
  const targetIndex = shapeXml.indexOf(token);
  if (targetIndex < 0) throw new Error(`Text target not found in ${shapeName}: ${target}`);
  if (shapeXml.indexOf(token, targetIndex + token.length) >= 0) {
    throw new Error(`Text target occurs twice in ${shapeName}: ${target}`);
  }
  const runStart = shapeXml.lastIndexOf("<a:r>", targetIndex);
  const runEndClose = shapeXml.indexOf("</a:r>", targetIndex);
  if (runStart < 0 || runEndClose < 0) throw new Error(`Run bounds missing in ${shapeName}: ${target}`);
  const runEnd = runEndClose + "</a:r>".length;
  return shapeXml.slice(0, runStart) + `<a14:m>${omml}</a14:m>` + shapeXml.slice(runEnd);
}

function wrapNativeMathShape(xml, group, ommlByTarget) {
  const bounds = locateShape(xml, group.shape);
  let choiceShape = bounds.xml;
  for (const [target] of group.equations) {
    choiceShape = replaceRun(choiceShape, target, ommlByTarget.get(target), group.shape);
  }
  const alternate =
    `<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">` +
    `<mc:Choice Requires="a14" xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main">${choiceShape}</mc:Choice>` +
    `<mc:Fallback>${bounds.xml}</mc:Fallback>` +
    `</mc:AlternateContent>`;
  return xml.slice(0, bounds.start) + alternate + xml.slice(bounds.end);
}

const input = await fs.readFile(SOURCE);
const zip = await JSZip.loadAsync(input);
const groupedBySlide = new Map();
for (const group of groups) {
  if (!groupedBySlide.has(group.slide)) groupedBySlide.set(group.slide, []);
  groupedBySlide.get(group.slide).push(group);
}

const manifest = [];
for (const [slideNumber, slideGroups] of groupedBySlide.entries()) {
  const slidePath = `ppt/slides/slide${slideNumber}.xml`;
  let xml = await zip.file(slidePath).async("string");
  for (const [overrideSlide, shapeName, left, top, width, height] of positionOverrides) {
    if (overrideSlide !== slideNumber) continue;
    xml = setShapePosition(xml, shapeName, left, top, width, height);
  }
  for (const [replacementSlide, from, to] of plainTextReplacements) {
    if (replacementSlide !== slideNumber) continue;
    const fromToken = `<a:t>${from}</a:t>`;
    if (!xml.includes(fromToken)) throw new Error(`Plain-text target missing on slide ${slideNumber}: ${from}`);
    xml = xml.replace(fromToken, `<a:t>${escapeXml(to)}</a:t>`);
  }
  for (const group of slideGroups) {
    const ommlByTarget = new Map();
    for (const [target, latex] of group.equations) {
      const omml = latexToOmml(latex);
      ommlByTarget.set(target, omml);
      manifest.push({ slide: slideNumber, shape: group.shape, target, latex, ommlChars: omml.length });
    }
    xml = wrapNativeMathShape(xml, group, ommlByTarget);
  }
  zip.file(slidePath, xml);
}

for (const slideNumber of [4, 6, 8, 10, 12]) {
  const xml = await zip.file(`ppt/slides/slide${slideNumber}.xml`).async("string");
  if (!xml.includes("<a14:m>")) throw new Error(`No native equations found on slide ${slideNumber}`);
}

const output = await zip.generateAsync({
  type: "nodebuffer",
  compression: "DEFLATE",
  compressionOptions: { level: 6 },
  mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
});
await fs.writeFile(OUTPUT, output);
await fs.writeFile(path.join(TMP, "native-equation-inplace-manifest.json"), JSON.stringify(manifest, null, 2), "utf8");
console.log(JSON.stringify({ output: OUTPUT, equations: manifest.length, groups: groups.length, bytes: output.length }, null, 2));
