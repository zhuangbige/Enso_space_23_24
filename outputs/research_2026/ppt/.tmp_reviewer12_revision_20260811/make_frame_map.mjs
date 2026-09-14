import fs from "node:fs/promises";

const out = "/Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_reviewer12_revision_20260811/template-frame-map.json";

const edits = {
  1: ["sh/65g3298r"],
  23: ["sh/90vqdczq", "sh/k3y9g3u9", "sh/y1gretc3"],
  24: ["sh/nu50zm10", "sh/axgza10b", "sh/d43itcjy", "sh/s72p8z6p", "sh/6lk76poz"],
  25: ["sh/xg7axgf2", "sh/napsr6x0", "sh/obyt0bel"],
  26: ["sh/uhk36lk7", "sh/8fil4b21", "sh/7e9kv6lg", "sh/lsja143i", "sh/y5sr69kr", "sh/c3a94z21", "sh/a18r2pkv"],
  27: ["sh/kn694nmx", "sh/lw7yxcra", "sh/apwfix8n", "sh/aho3y9cj"],
  29: ["sh/lw3ato3a", "sh/cjmxwv6p"],
  30: ["sh/po72d8nm", "sh/3mhwzu1c", "sh/dcje54ze", "sh/q9sfap03", "sh/sf6d0fip", "sh/tgfetkja", "sh/mxw36xob"],
  31: ["sh/5sn2to3u", "sh/ilory1wf", "sh/m947qlor", "sh/9cvqlgni", "sh/gni5c7mh"],
  35: ["sh/idonexon", "sh/ilonmxsr"],
  36: ["sh/5s3atkbq", "sh/exwb69s7", "sh/ydgn2xkf", "sh/83i5872h", "sh/m10n6xkr"],
};

const formula24 = [
  "sh/1cv6l47m", "sh/1sfqxsv6", "sh/nux8zidc", "sh/9wzq1svi",
  "sh/ov6p8nux", "sh/3ydonyd8", "sh/ix47utcn", "sh/8veh8ril",
  "sh/9wni1wjq", "sh/mtwz6h0f", "sh/nu50zm10", "sh/x07i5wj2",
  "sh/axgza10b", "sh/c3uh07id", "sh/d43itcjy", "sh/s72p8z6p", "sh/6lk76poz",
];

const formula30 = [
  "sh/h47mlc7y", "sh/po72d8nm", "sh/bqpkfy5s", "sh/xsr2h8ni",
  "sh/cril836d", "sh/ru5k3ep8", "sh/6twju9o3", "sh/onqx8zix",
  "sh/p8ze14zi", "sh/2l8f6p0r", "sh/3mhwzu1c", "sh/dcje54ze",
  "sh/q9sfap03", "sh/sf6d0fip", "sh/tgfetkja", "sh/8zel8761", "sh/mxw36xob",
];

const result2 = [
  "sh/ahwrqhgj", "sh/9072xkry", "sh/b29kza94", "sh/x4r21kru", "sh/w3i1sfa9",
  "sh/q5wjelsz", "sh/ove9o7yd", "sh/mtwrmxg7", "sh/nu58f2hs", "sh/xk7qlczu",
];

const sequence = [
  ...Array.from({ length: 25 }, (_, i) => i + 1),
  24, 2, 26, 27, 28, 29, 30, 31, 30, 2, 32, 33, 34, 35, 36,
];

const outputSlides = sequence.map((sourceSlide, index) => {
  const outputSlide = index + 1;
  let ids = edits[sourceSlide] ?? [];
  let narrativeRole = "preserve source slide";
  if (outputSlide === 26) {
    ids = formula24;
    narrativeRole = "residual audit calculation";
  } else if (outputSlide === 27) {
    ids = result2;
    narrativeRole = "residual audit result";
  } else if (outputSlide === 34) {
    ids = formula30;
    narrativeRole = "Q3 robustness calculation";
  } else if (outputSlide === 35) {
    ids = result2;
    narrativeRole = "Q3 robustness result";
  } else if (ids.length) {
    narrativeRole = "revised scientific interpretation";
  }
  return {
    outputSlide,
    sourceSlide,
    narrativeRole,
    reuseMode: "duplicate-slide",
    editTargets: ids.length ? [{ action: "rewrite", sourceElementIds: ids }] : [],
  };
});

await fs.writeFile(out, JSON.stringify({ outputSlides, omittedSourceSlides: [] }, null, 2));
