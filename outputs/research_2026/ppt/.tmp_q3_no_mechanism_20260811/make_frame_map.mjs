import fs from "node:fs/promises";

const out = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_q3_no_mechanism_20260811/template-frame-map.json";

const edits = new Map([
  [2, ["sh/9072xkry", "sh/nu58f2hs", "sh/xk7qlczu"]],
  [8, ["sh/7u5w765k", "sh/svydgb65"]],
  [9, ["sh/1cfmhgne", "sh/lsn2h4fa"]],
  [13, ["sh/6l4fu547"]],
  [15, ["sh/547mhg3m", "sh/vqdsrqx4", "sh/judsvqxg"]],
  [29, ["sh/tk36hwby", "sh/vmlojmto", "sh/h8n6lwbu", "sh/g7upcra9", "sh/idkbuxsv", "sh/t4butcri", "sh/6hkbyhs7", "sh/c7a9wj2t", "sh/b61snel8", "sh/lw3ato3a", "sh/58vy9wfm", "sh/p4jal432", "sh/n21sjelc"]],
  [31, ["sh/5sn2to3u", "sh/wf69wv6t"]],
  [34, ["sh/pwzm1kbm", "sh/za9wbutk", "sh/90beh4bm", "sh/mxkvmpcb", "sh/w32xszud", "sh/x4vel4by", "sh/k7y5gfi5", "sh/y5wne50z"]],
  [35, ["sh/idonexon", "sh/gb6lcn6x", "sh/u943ador", "sh/vad43ipc", "sh/t8vm1876", "sh/5of6xcbi", "sh/3mxov2tc", "sh/ilonmxsr", "sh/gjm5knal"]],
  [36, ["sh/94r61c32", "sh/w72pc72t", "sh/h8b65cje", "sh/i1wnuxcr"]],
  [37, ["sh/61c7md0r"]],
  [38, ["sh/kvy1kbep", "sh/hgrihsny", "sh/e94jyh4b", "sh/x8z2l07a"]],
  [39, ["sh/50769kvu", "sh/rid8vi1c"]],
  [40, ["sh/y9gzu50n", "sh/fu54vudk", "sh/tsnmt4vu", "sh/r6l4rudo"]],
]);

const outputSlides = [];
for (let sourceSlide = 1; sourceSlide <= 40; sourceSlide += 1) {
  if (sourceSlide === 32 || sourceSlide === 33) continue;
  const outputSlide = sourceSlide < 32 ? sourceSlide : sourceSlide - 2;
  const ids = edits.get(sourceSlide) ?? [];
  const rewriteIds = ids.filter((id) => !["sh/p4jal432", "sh/n21sjelc"].includes(id));
  const deleteIds = ids.filter((id) => ["sh/p4jal432", "sh/n21sjelc"].includes(id));
  const editTargets = [];
  if (rewriteIds.length) editTargets.push({ action: "rewrite", sourceElementIds: rewriteIds });
  if (deleteIds.length) editTargets.push({ action: "delete", sourceElementIds: deleteIds });
  outputSlides.push({
    outputSlide,
    sourceSlide,
    narrativeRole: ids.length ? "remove intermediate-mechanism language while preserving evidence" : "preserve source slide",
    reuseMode: "duplicate-slide",
    editTargets,
  });
}

const frameMap = {
  outputSlides,
  omittedSourceSlides: [
    { sourceSlide: 32, reason: "full dynamic-chain calculation page removed because Q3 no longer discusses the intermediate mechanism" },
    { sourceSlide: 33, reason: "full dynamic-chain result page removed because Q3 no longer discusses the intermediate mechanism" },
  ],
};

await fs.writeFile(out, `${JSON.stringify(frameMap, null, 2)}\n`, "utf8");
console.log(out);
