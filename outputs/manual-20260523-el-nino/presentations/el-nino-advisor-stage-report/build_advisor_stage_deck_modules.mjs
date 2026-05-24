#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(new URL("../../../..", import.meta.url).pathname);
const WORKSPACE = path.join(ROOT, "outputs/manual-20260523-el-nino/presentations/el-nino-advisor-stage-report");
const OLD_ASSETS = path.join(ROOT, "outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets");
const PENG_FIGURES = path.join(ROOT, "data/derived/peng2025_repro/figures");
const RESEARCH = path.join(ROOT, "data/derived/research");

const img = {
  fig1: path.join(PENG_FIGURES, "Fig1.png"),
  fig2: path.join(PENG_FIGURES, "Fig2.png"),
  fig3: path.join(PENG_FIGURES, "Fig3.png"),
  fig4: path.join(PENG_FIGURES, "Fig4.png"),
  coupling: path.join(OLD_ASSETS, "coupling_ratios.png"),
  validation: path.join(OLD_ASSETS, "validation_summary.png"),
  seasonal: path.join(RESEARCH, "seasonal_asynchrony_figure.png"),
  seasonalCompact: path.join(OLD_ASSETS, "seasonal_decoupling.png"),
  external: path.join(OLD_ASSETS, "external_basin_bars.png"),
  asyncBars: path.join(RESEARCH, "asynchronous_coupling_by_season.png"),
  spatialSstPrecip: path.join(RESEARCH, "stage_a_amj_jja_sst_precip.png"),
  spatialWindSlp: path.join(RESEARCH, "stage_a_amj_jja_ncep_wind_slp.png"),
};

const cn = [
  {
    kicker: "导师阶段汇报",
    title: "2023/24 强厄尔尼诺海气脱耦：从原文复现到发展季不同步响应",
    subtitle: "主线：强海温事件为何没有激发同等强度的风压、降水和对流响应？",
    layout: "cover",
    bullets: ["复现 Peng et al. 2025 的核心图和关键数值。", "在公开资料中验证“海温强、大气弱”。", "把全年结论推进到 AMJ/JJA 发展前期的历史对比。"],
    source: "Peng et al. 2025; NOAA OISST v2.1; GPCP; NCEP/NCAR R1. 汇报日期：2026-05-23。",
  },
  {
    kicker: "一句话结论",
    title: "目前已经从复现进入新研究第一层诊断",
    layout: "thesis",
    claim: "2023 年 AMJ/JJA 的 Niño-3 海温已达到历史强厄尔尼诺量级，但中西太平洋低层风、SOI-like 压力梯度和降水响应没有同步增强。",
    notes: [
      "原文贡献：证明 2023/24 强厄尔尼诺主要由海洋动力维持，并指出大气反馈偏弱。",
      "本课题问题：偏弱大气响应最早在哪个季节出现？哪些外海盆或背景态可能调制了耦合效率？",
      "阶段发现：AMJ/JJA 是关键窗口，TNA、印度洋、海陆洲和西太暖池同步偏暖。"
    ],
    source: "Current synthesis from reproduced paper figures and data/derived/research seasonal diagnostics.",
  },
  {
    kicker: "逻辑链条",
    title: "汇报结构：复现文章结论，再提出发展季耦合失效问题",
    layout: "flow",
    steps: ["原文复现\nFig. 1-4", "原始资料验证\nOISST/GPCP/NCEP", "发展季历史对比\nAMJ/JJA", "研究差异\n从成因到响应时序"],
    notes: ["每个有图页面都在图下标注数据来源；附录给出数据表格与链接。"],
    source: "Workflow recorded in reports/当前数据分析阶段总结.md and docs/data_source_log.md.",
  },
  {
    kicker: "原文复现 1",
    title: "Peng et al. Fig. 1：2023/24 海表温度强，但风压耦合响应偏弱",
    layout: "imagePairText",
    image: img.fig1,
    chart: img.coupling,
    figNote: "数据说明：Peng et al. 2025 source archive Fig. 1 数据；本地表 fig1_event_coupling.csv。Niño-3 指东赤道太平洋海温区；u10 是 10 米纬向风；SOI 是南方涛动指数。2023 Niño-3=1.929, u10=0.640, SOI=-0.433；u10 与 SOI 响应比仅为 0.27 和 0.31。",
    bullets: ["复现结果确认：2023/24 是强海温事件。", "相对于 1982/83、1997/98、2015/16，风压响应明显偏弱。"],
    source: "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig1.png.",
  },
  {
    kicker: "原文复现 2",
    title: "Peng et al. Fig. 2：原文将强事件归因到赤道太平洋海洋动力过程",
    layout: "fullImage",
    image: img.fig2,
    figNote: "数据说明：Peng et al. 2025 source archive Fig. 2 数据；本地表 fig2_equatorial_summary.csv。该图用于支撑原文的海洋动力解释，包括赤道传播、次表层热含量和风应力相关诊断。",
    source: "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig2.png.",
  },
  {
    kicker: "原文复现 3",
    title: "Peng et al. Fig. 3-4：外海盆海表温度和 2023 年风场均削弱典型响应",
    layout: "twoImagesTable",
    leftImage: img.fig3,
    rightImage: img.fig4,
    figNote: "数据说明：Peng et al. 2025 source archive Fig. 3-4 数据；本地表 fig3_agcm_summary.csv 与 fig4_wind_experiment_summary.csv。",
    tableTitle: "关键摘录",
    table: [
      ["指标", "值"],
      ["aPac 风应力", "0.0333"],
      ["aIndAtl 风应力", "-0.0099"],
      ["Dec Niño-3 CTRL", "2.344"],
      ["Dec Niño-3 Wind2023", "0.681"],
    ],
    source: "L1 Peng et al. 2025; reproduction tables in data/derived/peng2025_repro/tables.",
  },
  {
    kicker: "原文贡献与缺口",
    title: "原文回答了“强 El Niño 如何生成”，但留下“何时、为何脱耦”的问题",
    layout: "comparison",
    table: [
      ["维度", "Peng et al. 2025 的贡献", "本课题延伸"],
      ["主问题", "强 2023/24 El Niño 的海洋动力生成", "发展季大气响应为何未同步"],
      ["主要证据", "海洋热含量、赤道传播、风应力实验", "海表温度-风压-降水-对流的季节耦合效率"],
      ["时间尺度", "事件生成与成熟期", "AMJ/JJA/SON/DJF 不等时响应"],
      ["机制候选", "太平洋海洋动力与外海盆 SST 影响", "TNA、印度洋、海陆洲、西太暖池背景态调制"],
    ],
    source: "Synthesis of L1 and current diagnostics; citations listed in final appendix.",
  },
  {
    kicker: "独立资料验证",
    title: "公开资料重算表明：原文的核心事实不是单一数据集产物",
    layout: "imageBrief",
    image: img.validation,
    figNote: "数据说明：OISST、GPCP、NCEP/NCAR R1 公开资料；对应表 oisst_vs_fig1_nino3.csv, gpcp_vs_fig2_precip.csv, ncep_vs_fig1_atmosphere.csv。",
    bullets: ["NOAA 最优插值海表温度 OISST 的 Niño-3 与复现 Fig. 1 相关 0.9999。", "全球降水气候计划 GPCP 显示 2023 中东太平洋降水弱于强事件 composite。", "NCEP/NCAR 再分析风和类 SOI 压力梯度与原文大气指标高度一致。"],
    source: "D2 NOAA OISST; D3 GPCP; D4 NCEP/NCAR R1 via NOAA PSL OPeNDAP.",
  },
  {
    kicker: "阶段性发现 1",
    title: "历史对比显示：春季 AMJ / 夏季 JJA 的海温已强，但同步风压响应失效",
    layout: "imageTable",
    image: img.seasonal,
    figNote: "数据说明：OISST Niño-3、NCEP CWP u proxy 与 SOI-like SLP gradient；相对 1982/83、1997/98、2015/16 strong-El Niño composite。",
    table: [
      ["指标", "AMJ", "JJA"],
      ["Niño-3 SST 比值", "1.41", "1.22"],
      ["中西太平洋 CWP 风比值", "-0.43", "-0.14"],
      ["SOI-like 效率", "0.22", "0.28"],
      ["CP 降水比值", "0.43", "0.38"],
    ],
    source: "Tables: asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv.",
  },
  {
    kicker: "阶段性发现 2",
    title: "空间图：2023 春夏热带背景更暖，但太平洋降水中心未同步增强",
    layout: "fullImage",
    image: img.spatialSstPrecip,
    figNote: "数据说明：OISST 海表温度与 GPCP 降水；图为 2023 AMJ/JJA 减去 1982/1997/2015 强事件 composite。TNA 指热带北大西洋，MC 指海陆洲，WPWP 指西太平洋暖池。TNA、海陆洲、西太暖池偏暖；中东太平洋降水偏弱。",
    source: "D2 NOAA OISST; D3 GPCP. Summary table: stage_a_spatial_summary.csv.",
  },
  {
    kicker: "阶段性发现 3",
    title: "空间图：低层风和海平面气压也显示发展季 Walker 环流响应不典型",
    layout: "fullImage",
    image: img.spatialWindSlp,
    figNote: "数据说明：NCEP/NCAR R1 近地面 sigma995 风与海平面气压 SLP；图为 2023 AMJ/JJA 减去 1982/1997/2015 composite。CWP 指中西太平洋，CWP 低层风差值 AMJ=-2.301 m/s, JJA=-2.576 m/s；类 SOI 的 SLP 梯度差值为正。",
    source: "D4 NCEP/NCAR R1 fallback diagnostic. Final paper stage should replace/check with ERA5.",
  },
  {
    kicker: "阶段性发现 4",
    title: "外海盆暖异常为“发展季不同步响应”提供背景态线索",
    layout: "twoChartsTable",
    leftImage: img.external,
    rightImage: img.asyncBars,
    figNote: "数据说明：左图为 OISST 外海盆指数，右图为季节耦合效率。均以 1982/83、1997/98、2015/16 为历史强事件参照。",
    table: [
      ["区域/指标", "AMJ", "JJA"],
      ["热带北大西洋 TNA", "+1.11", "+1.35"],
      ["西太暖池 WPWP", "+0.73", "+0.88"],
      ["海陆洲 MC", "+0.55", "+0.68"],
      ["热带印度洋 TIO", "+0.44", "+0.40"],
    ],
    source: "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_by_season.png.",
  },
  {
    kicker: "与现有研究的区别",
    title: "相关研究多解释某一机制或月份，本课题聚焦“多变量季节耦合效率”",
    layout: "comparison",
    table: [
      ["文献", "已有重点", "与本课题区别"],
      ["Peng et al. 2025", "海洋动力生成强 El Niño", "本课题解释大气响应为何弱、何时开始弱"],
      ["Zhang et al. 2025", "弱降水/遥相关与外海盆加热", "本课题把风压、降水、SST 做季节同步性矩阵"],
      ["Kim et al. 2025", "发展季风场异常与西中太梯度", "本课题加入 SOI-like、GPCP 和外海盆历史对比"],
      ["Zhao et al. 2025", "2023 年 7 月热带北大西洋 + 印度夏季风/海陆洲 heating", "本课题从 AMJ/JJA 到 SON/DJF 连续追踪"],
      ["Yang & Li 2025", "2024 年 1 月季节内振荡 MJO / 趋势 / ENSO 分解", "本课题先建立发展季背景，再接入 MJO/OLR 机制拆解"],
    ],
    source: "Literature notes: docs/literature_method_notes.md; source IDs L2-L8 in docs/data_source_log.md.",
  },
  {
    kicker: "拟定研究题目",
    title: "建议题目：2023/24 强厄尔尼诺发展季海气耦合失效及其外海盆背景态调制",
    layout: "thesis",
    claim: "工作假设：2023 春夏的热带外海盆暖异常和热带平均增暖背景，改变了 Walker 环流和对流阈值，使太平洋暖 SST 对低层风压与降水的典型响应滞后或减弱。",
    notes: [
      "可检验 H1：AMJ/JJA 外海盆暖异常抑制中太平洋西风响应。",
      "可检验 H2：海陆洲/印度洋局地加热维持西侧对流，削弱降水中心东移。",
      "可检验 H3：TNA 偏暖或热带平均增暖提高 ENSO 大气响应阈值。"
    ],
    source: "Current diagnostics only establish association; ERA5/OLR/MJO and AGCM experiments are needed for mechanism attribution.",
  },
  {
    kicker: "下一步",
    title: "下一阶段优先补足 ERA5 与 OLR，把“现象”推进到“机制检验”",
    layout: "roadmap",
    steps: ["ERA5 u850/SLP/χ200\n替换 NCEP fallback", "NOAA OLR + GPCP\n独立验证对流中心", "ERSSTv5 长记录\n检查历史样本稳健性", "AGCM 大气模式预案\nPacific-only / IO-ATL / detrended"],
    notes: ["当前可以开始你的研究主线：先写作“发展季耦合效率丧失”的诊断论文框架，再用 ERA5/OLR 强化机制证据。"],
    source: "Data priorities from reports/当前数据分析阶段总结.md.",
  },
  {
    kicker: "附录 A",
    title: "图表与数据表对应关系",
    layout: "appendixTable",
    table: [
      ["页码", "图/结论", "对应数据表"],
      ["4", "Fig.1 事件强度与耦合响应比", "fig1_event_coupling.csv"],
      ["5", "Fig.2 赤道剖面/传播诊断", "fig2_equatorial_summary.csv"],
      ["6", "Fig.3-4 AGCM 与风应力实验", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["8", "OISST/GPCP/NCEP 独立验证", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["9", "AMJ/JJA 历史耦合效率", "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"],
      ["10-11", "AMJ/JJA 空间 SST/降水/风压", "stage_a_spatial_summary.csv"],
      ["12", "外海盆暖异常与季节效率", "external_basin_seasonal_summary.csv"],
    ],
    source: "All paths are under /Users/daiyue/Documents/Maryland/data/derived.",
  },
  {
    kicker: "附录 B",
    title: "数据与文献链接",
    layout: "links",
    links: [
      ["Peng et al. 2025", "https://www.nature.com/articles/s41561-025-01700-9"],
      ["NOAA OISST v2.1", "https://www.ncei.noaa.gov/products/optimum-interpolation-sst"],
      ["GPCP", "https://psl.noaa.gov/data/gridded/data.gpcp.html"],
      ["NCEP/NCAR R1", "https://www.psl.noaa.gov/data/reanalysis/"],
      ["ERA5", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels"],
      ["NOAA OLR", "https://psl.noaa.gov/data/gridded/data.interp_OLR.html"],
      ["ERSSTv5", "https://www.ncei.noaa.gov/products/extended-reconstructed-sst"],
      ["ORAS5", "https://www.ecmwf.int/en/forecasts/dataset/ocean-reanalysis-system-5"],
      ["TAO/TRITON", "https://www.pmel.noaa.gov/gtmba/building-tao"],
    ],
    source: "Full source log: docs/data_source_log.md.",
  },
];

const en = [
  {
    kicker: "Advisor Update",
    title: "Atmosphere-ocean decoupling during the 2023/24 strong El Niño: from paper reproduction to developing-season asynchrony",
    subtitle: "Main question: why did a strong oceanic event fail to trigger equally strong wind, pressure, rainfall, and convection responses?",
    layout: "cover",
    bullets: ["Reproduce the core figures and metrics from Peng et al. 2025.", "Validate the ocean-strong / atmosphere-weak signal with public datasets.", "Extend the analysis to AMJ/JJA historical comparisons."],
    source: "Peng et al. 2025; NOAA OISST v2.1; GPCP; NCEP/NCAR R1. Briefing date: 2026-05-23.",
  },
  {
    kicker: "Bottom Line",
    title: "The work has moved from reproduction into first-layer original diagnostics",
    layout: "thesis",
    claim: "During AMJ/JJA 2023, Niño-3 SST had already reached a historically strong El Niño level, but central-western Pacific low-level wind, SOI-like pressure gradient, and rainfall responses did not intensify synchronously.",
    notes: [
      "Paper contribution: Peng et al. show that ocean dynamics sustained the 2023/24 strong El Niño and that atmospheric feedbacks were weak.",
      "Our question: when did the weak atmospheric response first emerge, and which external basins or background states may have modulated coupling efficiency?",
      "Current finding: AMJ/JJA is the key window, with simultaneous warming over the TNA, Indian Ocean, Maritime Continent, and western Pacific warm pool."
    ],
    source: "Current synthesis from reproduced paper figures and data/derived/research seasonal diagnostics.",
  },
  {
    kicker: "Storyline",
    title: "Deck structure: reproduce the paper, then isolate the developing-season coupling failure",
    layout: "flow",
    steps: ["Paper reproduction\nFig. 1-4", "Raw validation\nOISST/GPCP/NCEP", "Developing-season comparison\nAMJ/JJA", "Research distinction\nFrom genesis to response timing"],
    notes: ["Every figure slide includes a data note; appendices map slides to tables and source links."],
    source: "Workflow recorded in reports/当前数据分析阶段总结.md and docs/data_source_log.md.",
  },
  {
    kicker: "Reproduction 1",
    title: "Peng et al. Fig. 1: strong sea-surface temperature but weak wind-pressure coupling in 2023/24",
    layout: "imagePairText",
    image: img.fig1,
    chart: img.coupling,
    figNote: "Data note: Peng et al. 2025 source archive Fig. 1; local table fig1_event_coupling.csv. Niño-3 is the eastern equatorial Pacific SST region; u10 is 10-m zonal wind; SOI is the Southern Oscillation Index. For 2023, Niño-3=1.929, u10=0.640, SOI=-0.433; u10 and SOI response ratios are only 0.27 and 0.31.",
    bullets: ["Reproduction confirms 2023/24 as a strong SST event.", "Wind and pressure responses are muted relative to 1982/83, 1997/98, and 2015/16."],
    source: "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig1.png.",
  },
  {
    kicker: "Reproduction 2",
    title: "Peng et al. Fig. 2: the paper attributes the strong event to equatorial Pacific ocean dynamics",
    layout: "fullImage",
    image: img.fig2,
    figNote: "Data note: Peng et al. 2025 source archive Fig. 2; local table fig2_equatorial_summary.csv. The figure supports the ocean-dynamics argument using equatorial propagation, subsurface heat content, and wind-stress diagnostics.",
    source: "L1 Peng et al. 2025; local reproduction: data/derived/peng2025_repro/figures/Fig2.png.",
  },
  {
    kicker: "Reproduction 3",
    title: "Peng et al. Fig. 3-4: external-basin sea-surface temperature and 2023 wind forcing both damp the canonical response",
    layout: "twoImagesTable",
    leftImage: img.fig3,
    rightImage: img.fig4,
    figNote: "Data note: Peng et al. 2025 source archive Fig. 3-4; local tables fig3_agcm_summary.csv and fig4_wind_experiment_summary.csv.",
    tableTitle: "Extracted metrics",
    table: [
      ["Metric", "Value"],
      ["aPac wind stress", "0.0333"],
      ["aIndAtl wind stress", "-0.0099"],
      ["Dec Niño-3 CTRL", "2.344"],
      ["Dec Niño-3 Wind2023", "0.681"],
    ],
    source: "L1 Peng et al. 2025; reproduction tables in data/derived/peng2025_repro/tables.",
  },
  {
    kicker: "Paper Contribution",
    title: "The paper explains how the strong El Niño formed, but leaves open when and why coupling failed",
    layout: "comparison",
    table: [
      ["Dimension", "Peng et al. 2025 contribution", "This project extends to"],
      ["Main question", "Ocean-dynamical generation of the strong 2023/24 El Niño", "Why the atmosphere did not respond synchronously"],
      ["Evidence base", "Heat content, equatorial propagation, wind-stress experiments", "Seasonal sea-surface-temperature, wind, pressure, rainfall, and convection coupling efficiency"],
      ["Timescale", "Event development and mature phase", "AMJ/JJA/SON/DJF asynchronous response"],
      ["Candidate mechanisms", "Pacific ocean dynamics and external-basin SST influence", "TNA, Indian Ocean, Maritime Continent, and warm-pool background-state modulation"],
    ],
    source: "Synthesis of L1 and current diagnostics; citations listed in final appendix.",
  },
  {
    kicker: "Raw Validation",
    title: "Public datasets confirm that the paper-level signal is not a single-dataset artifact",
    layout: "imageBrief",
    image: img.validation,
    figNote: "Data note: NOAA OISST, GPCP, and NCEP/NCAR R1; corresponding tables oisst_vs_fig1_nino3.csv, gpcp_vs_fig2_precip.csv, and ncep_vs_fig1_atmosphere.csv.",
    bullets: ["NOAA Optimum Interpolation SST, or OISST, Niño-3 correlates 0.9999 with reproduced Fig. 1.", "Global Precipitation Climatology Project, or GPCP, shows weaker central/eastern Pacific rainfall in 2023 than in the strong-event composite.", "NCEP/NCAR reanalysis wind and SOI-like pressure-gradient proxies align closely with the paper's atmospheric metrics."],
    source: "D2 NOAA OISST; D3 GPCP; D4 NCEP/NCAR R1 via NOAA PSL OPeNDAP.",
  },
  {
    kicker: "Finding 1",
    title: "Historical comparison: spring AMJ / summer JJA SST was strong, but synchronous wind-pressure coupling failed",
    layout: "imageTable",
    image: img.seasonal,
    figNote: "Data note: OISST Niño-3, NCEP CWP u proxy, and SOI-like SLP gradient; all relative to the 1982/83, 1997/98, and 2015/16 strong-El Niño composite.",
    table: [
      ["Metric", "AMJ", "JJA"],
      ["Niño-3 SST ratio", "1.41", "1.22"],
      ["Central-west Pacific CWP wind ratio", "-0.43", "-0.14"],
      ["SOI-like efficiency", "0.22", "0.28"],
      ["CP rainfall ratio", "0.43", "0.38"],
    ],
    source: "Tables: asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv.",
  },
  {
    kicker: "Finding 2",
    title: "Spatial maps: the 2023 AMJ/JJA tropical background was warmer, but Pacific rainfall did not strengthen synchronously",
    layout: "fullImage",
    image: img.spatialSstPrecip,
    figNote: "Data note: OISST sea-surface temperature and GPCP precipitation; maps show 2023 AMJ/JJA minus the 1982/1997/2015 strong-event composite. TNA is Tropical North Atlantic, MC is Maritime Continent, and WPWP is western Pacific warm pool. These regions are warmer, while central/eastern Pacific rainfall is weaker.",
    source: "D2 NOAA OISST; D3 GPCP. Summary table: stage_a_spatial_summary.csv.",
  },
  {
    kicker: "Finding 3",
    title: "Spatial maps: low-level wind and sea-level pressure also show an atypical developing-season Walker response",
    layout: "fullImage",
    image: img.spatialWindSlp,
    figNote: "Data note: NCEP/NCAR R1 near-surface sigma995 wind and sea-level pressure SLP; maps show 2023 AMJ/JJA minus the 1982/1997/2015 composite. CWP means central-western Pacific. CWP low-level wind differences are -2.301 m/s in AMJ and -2.576 m/s in JJA; SOI-like SLP-gradient differences are positive.",
    source: "D4 NCEP/NCAR R1 fallback diagnostic. Final manuscript stage should replace/check with ERA5.",
  },
  {
    kicker: "Finding 4",
    title: "External-basin warmth provides a background-state clue for developing-season asynchrony",
    layout: "twoChartsTable",
    leftImage: img.external,
    rightImage: img.asyncBars,
    figNote: "Data note: left chart uses OISST external-basin indices; right chart uses seasonal coupling efficiency. Both compare 2023 with the 1982/83, 1997/98, and 2015/16 strong-event composite.",
    table: [
      ["Region / metric", "AMJ", "JJA"],
      ["Tropical N. Atlantic TNA", "+1.11", "+1.35"],
      ["W. Pacific warm pool WPWP", "+0.73", "+0.88"],
      ["Maritime Continent MC", "+0.55", "+0.68"],
      ["Tropical Indian Ocean TIO", "+0.44", "+0.40"],
    ],
    source: "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_by_season.png.",
  },
  {
    kicker: "Research Distinction",
    title: "Related studies emphasize individual mechanisms or months; this project targets multi-variable seasonal coupling efficiency",
    layout: "comparison",
    table: [
      ["Study", "Existing focus", "How this project differs"],
      ["Peng et al. 2025", "Ocean-dynamical generation of the strong El Niño", "Explains why and when the atmospheric response was weak"],
      ["Zhang et al. 2025", "Weak rainfall/teleconnection response and external-basin heating", "Builds a seasonal matrix across wind, pressure, rainfall, and SST"],
      ["Kim et al. 2025", "Developing-season wind anomalies and west-central Pacific gradients", "Adds SOI-like pressure, GPCP rainfall, and external-basin historical comparison"],
      ["Zhao et al. 2025", "July 2023 Tropical North Atlantic plus Indian summer monsoon / Maritime Continent heating", "Tracks a continuous AMJ/JJA to SON/DJF evolution"],
      ["Yang & Li 2025", "January 2024 Madden-Julian Oscillation MJO / trend / ENSO decomposition", "Builds the developing-season background before adding MJO/OLR mechanism tests"],
    ],
    source: "Literature notes: docs/literature_method_notes.md; source IDs L2-L8 in docs/data_source_log.md.",
  },
  {
    kicker: "Working Topic",
    title: "Proposed topic: developing-season atmosphere-ocean coupling failure during the 2023/24 strong El Niño and its external-basin modulation",
    layout: "thesis",
    claim: "Working hypothesis: spring-summer external-basin warmth and the tropical-mean warming background altered the Walker circulation and convective threshold, delaying or weakening the canonical wind-pressure-rainfall response to warm Pacific SST.",
    notes: [
      "Testable H1: AMJ/JJA external-basin warmth suppressed central-Pacific westerly response.",
      "Testable H2: Maritime Continent / Indian Ocean heating maintained western-side convection and weakened eastward rainfall displacement.",
      "Testable H3: TNA warmth or tropical-mean warming raised the threshold for ENSO atmospheric response."
    ],
    source: "Current diagnostics establish association; ERA5/OLR/MJO and AGCM experiments are needed for mechanism attribution.",
  },
  {
    kicker: "Next Step",
    title: "Next stage: add ERA5 and OLR to move from phenomenon diagnosis to mechanism tests",
    layout: "roadmap",
    steps: ["ERA5 u850/SLP/χ200\nreplace NCEP fallback", "NOAA OLR + GPCP\nvalidate convection centers", "ERSSTv5 long record\ncheck historical robustness", "AGCM model plan\nPacific-only / IO-ATL / detrended"],
    notes: ["The research line can now start formally: diagnose developing-season coupling-efficiency loss, then strengthen mechanism evidence with ERA5/OLR."],
    source: "Data priorities from reports/当前数据分析阶段总结.md.",
  },
  {
    kicker: "Appendix A",
    title: "Slide-to-data table",
    layout: "appendixTable",
    table: [
      ["Slide", "Figure / claim", "Corresponding table"],
      ["4", "Fig. 1 event strength and coupling ratios", "fig1_event_coupling.csv"],
      ["5", "Fig. 2 equatorial propagation diagnostics", "fig2_equatorial_summary.csv"],
      ["6", "Fig. 3-4 AGCM and wind-stress experiments", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["8", "OISST/GPCP/NCEP independent validation", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["9", "AMJ/JJA historical coupling efficiency", "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"],
      ["10-11", "AMJ/JJA spatial SST/rainfall/wind/pressure", "stage_a_spatial_summary.csv"],
      ["12", "External-basin warmth and seasonal efficiency", "external_basin_seasonal_summary.csv"],
    ],
    source: "All paths are under /Users/daiyue/Documents/Maryland/data/derived.",
  },
  {
    kicker: "Appendix B",
    title: "Data and literature links",
    layout: "links",
    links: [
      ["Peng et al. 2025", "https://www.nature.com/articles/s41561-025-01700-9"],
      ["NOAA OISST v2.1", "https://www.ncei.noaa.gov/products/optimum-interpolation-sst"],
      ["GPCP", "https://psl.noaa.gov/data/gridded/data.gpcp.html"],
      ["NCEP/NCAR R1", "https://www.psl.noaa.gov/data/reanalysis/"],
      ["ERA5", "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels"],
      ["NOAA OLR", "https://psl.noaa.gov/data/gridded/data.interp_OLR.html"],
      ["ERSSTv5", "https://www.ncei.noaa.gov/products/extended-reconstructed-sst"],
      ["ORAS5", "https://www.ecmwf.int/en/forecasts/dataset/ocean-reanalysis-system-5"],
      ["TAO/TRITON", "https://www.pmel.noaa.gov/gtmba/building-tao"],
    ],
    source: "Full source log: docs/data_source_log.md.",
  },
];

const shared = `
const C = {
  bg: "#f7f3ea",
  ink: "#1d1b18",
  muted: "#6e675d",
  rule: "#d8d1c4",
  red: "#cc5a43",
  teal: "#2f6f73",
  blue: "#4a5f99",
  pale: "#efe8dc",
  cream: "#fbf8f1",
  greenPale: "#edf3ef",
  rosePale: "#f5e5df",
};

function bg(slide, ctx) {
  ctx.addShape(slide, { x: 0, y: 0, w: 1280, h: 720, fill: C.bg });
}

function text(slide, ctx, value, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text: value || "", x, y, w, h,
    fontSize: opts.size || 22,
    bold: opts.bold || false,
    color: opts.color || C.ink,
    typeface: opts.face || (opts.title ? ctx.fonts.title : ctx.fonts.body),
    valign: opts.valign || "top",
    align: opts.align || "left",
    insets: opts.insets || { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

function header(slide, ctx, d) {
  text(slide, ctx, d.kicker, 64, 34, 300, 24, { size: 13, bold: true, color: C.red });
  text(slide, ctx, d.title, 64, 65, 1090, 82, { size: 31, bold: true, title: true });
  ctx.addShape(slide, { x: 64, y: 151, w: 1120, h: 1.5, fill: C.rule });
}

function source(slide, ctx, value) {
  text(slide, ctx, value || "", 64, 684, 1100, 22, { size: 8.6, color: C.muted });
}

function bulletList(slide, ctx, items, x, y, w, row = 55, size = 17) {
  let yy = y;
  for (const item of items || []) {
    ctx.addShape(slide, { x, y: yy + 8, w: 7, h: 7, fill: C.red, geometry: "ellipse" });
    text(slide, ctx, item, x + 20, yy, w - 20, row - 5, { size });
    yy += row;
  }
}

async function addImage(slide, ctx, imagePath, x, y, w, h, fit = "contain") {
  await ctx.addImage(slide, { path: imagePath, x, y, w, h, fit });
}

function note(slide, ctx, value, x, y, w, h = 42) {
  ctx.addShape(slide, { x, y, w, h, fill: "#fffaf1", line: { style: "solid", fill: C.rule, width: 0.8 } });
  text(slide, ctx, value, x + 12, y + 8, w - 24, h - 12, { size: 10.4, color: C.muted });
}

function smallTable(slide, ctx, rows, x, y, w, rowH = 38, opts = {}) {
  const cols = rows[0].length;
  const colW = opts.colWidths || Array(cols).fill(w / cols);
  rows.forEach((row, r) => {
    let xx = x;
    row.forEach((cell, c) => {
      const cw = colW[c];
      ctx.addShape(slide, {
        x: xx, y: y + r * rowH, w: cw, h: rowH,
        fill: r === 0 ? C.ink : (r % 2 === 0 ? "#f3ede2" : C.cream),
        line: { style: "solid", fill: C.rule, width: 0.7 },
      });
      text(slide, ctx, cell, xx + 8, y + r * rowH + 7, cw - 16, rowH - 10, {
        size: r === 0 ? (opts.headerSize || 11) : (opts.size || 12.2),
        bold: r === 0,
        color: r === 0 ? "#ffffff" : C.ink,
      });
      xx += cw;
    });
  });
}

async function renderDeckSlide(presentation, ctx, d) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  if (d.layout === "cover") {
    text(slide, ctx, d.kicker, 64, 52, 260, 26, { size: 14, bold: true, color: C.red });
    text(slide, ctx, d.title, 64, 102, 890, 188, { size: 40, bold: true, title: true });
    text(slide, ctx, d.subtitle, 66, 316, 940, 62, { size: 21, color: C.muted });
    bulletList(slide, ctx, d.bullets, 72, 440, 860, 56, 18);
    ctx.addShape(slide, { x: 1012, y: 118, w: 148, h: 148, fill: C.red, geometry: "ellipse" });
    ctx.addShape(slide, { x: 1074, y: 308, w: 92, h: 92, fill: C.teal, geometry: "ellipse" });
    ctx.addShape(slide, { x: 996, y: 455, w: 176, h: 22, fill: C.blue });
    source(slide, ctx, d.source);
    return slide;
  }

  header(slide, ctx, d);

  if (d.layout === "thesis") {
    ctx.addShape(slide, { x: 84, y: 190, w: 1010, h: 136, fill: C.rosePale, line: { style: "solid", fill: C.rule, width: 1 } });
    text(slide, ctx, d.claim, 112, 214, 954, 92, { size: 23, bold: true, color: C.ink });
    bulletList(slide, ctx, d.notes, 104, 370, 960, 70, 18);
  } else if (d.layout === "flow" || d.layout === "roadmap") {
    const y = d.layout === "flow" ? 236 : 228;
    d.steps.forEach((step, i) => {
      const x = 74 + i * 288;
      const h = d.layout === "flow" ? 132 : 160;
      ctx.addShape(slide, { x, y, w: 236, h, fill: i % 2 ? C.greenPale : C.rosePale, line: { style: "solid", fill: C.rule, width: 1 } });
      text(slide, ctx, String(i + 1).padStart(2, "0"), x + 17, y + 16, 48, 28, { size: 17, bold: true, color: i % 2 ? C.teal : C.red });
      text(slide, ctx, step, x + 18, y + 54, 198, h - 70, { size: 16.2, bold: true });
      if (i < d.steps.length - 1) text(slide, ctx, ">", x + 248, y + 48, 28, 40, { size: 25, color: C.muted });
    });
    bulletList(slide, ctx, d.notes || [], 94, 466, 960, 52, 18);
  } else if (d.layout === "imagePairText") {
    await addImage(slide, ctx, d.image, 66, 178, 528, 386);
    await addImage(slide, ctx, d.chart, 620, 186, 430, 250);
    bulletList(slide, ctx, d.bullets, 632, 462, 480, 42, 14.5);
    note(slide, ctx, d.figNote, 68, 574, 1088, 82);
  } else if (d.layout === "fullImage") {
    await addImage(slide, ctx, d.image, 70, 172, 1080, 380);
    note(slide, ctx, d.figNote, 70, 568, 1080, 88);
  } else if (d.layout === "twoImagesTable") {
    await addImage(slide, ctx, d.leftImage, 64, 178, 376, 296);
    await addImage(slide, ctx, d.rightImage, 458, 178, 376, 296);
    text(slide, ctx, d.tableTitle, 870, 184, 260, 26, { size: 18, bold: true });
    smallTable(slide, ctx, d.table, 860, 224, 310, 42);
    note(slide, ctx, d.figNote, 66, 568, 1088, 88);
  } else if (d.layout === "imageBrief") {
    await addImage(slide, ctx, d.image, 78, 184, 548, 358);
    bulletList(slide, ctx, d.bullets, 680, 214, 430, 78, 18);
    note(slide, ctx, d.figNote, 78, 568, 1080, 88);
  } else if (d.layout === "imageTable") {
    await addImage(slide, ctx, d.image, 72, 174, 650, 376);
    smallTable(slide, ctx, d.table, 760, 218, 380, 44);
    note(slide, ctx, d.figNote, 72, 568, 1080, 88);
  } else if (d.layout === "twoChartsTable") {
    await addImage(slide, ctx, d.leftImage, 70, 180, 392, 302);
    await addImage(slide, ctx, d.rightImage, 480, 180, 392, 302);
    smallTable(slide, ctx, d.table, 880, 204, 304, 42, { colWidths: [164, 70, 70], size: 11.2, headerSize: 10.5 });
    note(slide, ctx, d.figNote, 72, 568, 1080, 88);
  } else if (d.layout === "comparison") {
    smallTable(slide, ctx, d.table, 72, 190, 1088, d.reader ? 54 : 64, { colWidths: [190, 405, 493], size: d.reader ? 10.6 : 11.4, headerSize: 11 });
    if (d.reader) note(slide, ctx, d.reader, 72, 540, 1088, 78);
  } else if (d.layout === "glossary") {
    smallTable(slide, ctx, d.table, 72, 178, 1088, 45, { colWidths: [140, 300, 648], size: 10.8, headerSize: 11 });
    note(slide, ctx, d.reader, 72, 596, 1088, 54);
  } else if (d.layout === "appendixTable") {
    smallTable(slide, ctx, d.table, 72, 178, 1088, 56, { colWidths: [96, 392, 600], size: 11.5, headerSize: 11 });
  } else if (d.layout === "links") {
    const rows = [["Source", "URL"], ...d.links];
    smallTable(slide, ctx, rows, 76, 176, 1078, 44, { colWidths: [255, 823], size: 10.4, headerSize: 11 });
  }

  source(slide, ctx, d.source);
  return slide;
}

export { renderDeckSlide };
`;

async function writeDeck(language, slides) {
  const slidesDir = path.join(WORKSPACE, language === "cn" ? "slides_cn" : "slides_en");
  await fs.mkdir(slidesDir, { recursive: true });
  await fs.writeFile(path.join(WORKSPACE, `deck_shared_${language}.mjs`), shared, "utf8");
  for (let i = 0; i < slides.length; i += 1) {
    const n = String(i + 1).padStart(2, "0");
    const content = [
      `import { renderDeckSlide } from "../deck_shared_${language}.mjs";`,
      `const data = ${JSON.stringify(slides[i], null, 2)};`,
      `export async function slide${n}(presentation, ctx) {`,
      `  return renderDeckSlide(presentation, ctx, data);`,
      `}`,
      "",
    ].join("\n");
    await fs.writeFile(path.join(slidesDir, `slide-${n}.mjs`), content, "utf8");
  }
}

async function writeNotes() {
  await fs.writeFile(path.join(WORKSPACE, "package.json"), `${JSON.stringify({ private: true, type: "module" }, null, 2)}\n`, "utf8");
  await fs.writeFile(path.join(WORKSPACE, "profile-plan.txt"), [
    "task mode: create",
    "primary deck-profile: strategy-leadership",
    "secondary gates: appendix-heavy scientific provenance",
    "proof objects: reproduced Peng et al. figures; raw validation chart; seasonal coupling chart; Stage A spatial maps; literature comparison table",
    "known missing inputs: ERA5, OLR, MJO/RMM, and ERSSTv5 long-record checks remain next-stage work",
    "",
  ].join("\n"), "utf8");
  await fs.writeFile(path.join(WORKSPACE, "claim-spine.txt"), [
    "Thesis: The project can now be framed around developing-season atmosphere-ocean coupling failure during the 2023/24 strong El Niño.",
    "Arc: reproduce original conclusions -> identify the open response-timing question -> validate with independent public data -> show AMJ/JJA historical asynchrony -> differentiate from existing studies.",
    "",
  ].join("\n"), "utf8");
  await fs.writeFile(path.join(WORKSPACE, "source-notes.txt"), [
    "Reproduction figures use local outputs from Peng et al. 2025 source data/code.",
    "Raw validation uses NOAA OISST, GPCP, and NCEP/NCAR R1 products logged in docs/data_source_log.md.",
    "Stage A spatial maps are first-pass diagnostics and use NCEP as a fallback for wind/SLP; ERA5 remains the planned paper-grade replacement.",
    "No logos or identity assets are used.",
    "",
  ].join("\n"), "utf8");
}

function enrichForReading(slides, language) {
  if (language === "cn") {
    slides[1].notes.push("因此，当前不是简单重复原文，而是在原文“海洋动力生成强事件”的基础上追问：大气为什么没有按历史经验给出同等响应。");
    slides[2].notes.push("给导师阅读时，可以把这页看作全文路线图：前半部分证明基础事实可靠，后半部分说明你的新问题从哪里来。");
    slides[3].figNote += " 读图要点：左侧复现原文中 SST、MSLP/u10 和散点关系，右侧把数值压缩成响应比。它说明 2023/24 的海温并不弱，真正异常的是大气端没有按历史强事件斜率响应。";
    slides[4].figNote += " 读图要点：这页不是你的新机制，而是原文的基础归因。它告诉我们强海温可以由海洋动力解释，但并没有解释为什么春夏早期风压和降水没有同步放大。";
    slides[5].figNote += " 读图要点：aPac 代表太平洋 SST 对大气风应力的典型驱动，aIndAtl 为印度洋和大西洋背景的外海盆影响。外海盆项为负，说明它可能抵消太平洋暖 SST 的大气响应。";
    slides[6].reader = "这页的作用是把原文贡献和你的研究空间分开：原文主要回答“强事件如何被海洋过程生成”，你的题目转向“强海温出现后，大气响应为什么不按历史同步发生”。因此后续分析必须分季节、分变量，而不能只看全年平均。";
    slides[7].figNote += " 读图要点：OISST 验证海温，GPCP 验证降水，NCEP 作为风压 fallback。三类独立资料方向一致，说明“海温强、大气弱”不是原文源数据的偶然结果。";
    slides[8].figNote += " 读图要点：如果只看 Niño-3，AMJ/JJA 2023 已经很像强 El Niño；但 CWP u 和 SOI-like 指标没有同步增强，甚至低层风响应反向。这就是目前最核心的新发现。";
    slides[9].figNote += " 读图要点：SST 图显示 2023 春夏不只是东太平洋暖，外海盆和西太暖池也更暖；降水图显示中东太平洋对流并没有跟随海温充分增强，支持“热背景改变对流阈值或 Walker 响应”的解释方向。";
    slides[10].figNote += " 读图要点：NCEP 结果目前是 fallback，但已经给出清楚线索：AMJ/JJA 中西太平洋低层风异常相对历史强事件偏弱，SLP 梯度也不像典型强 El Niño 那样充分建立。";
    slides[11].figNote += " 读图要点：左图说明外海盆暖异常是 2023 春夏的显著背景，右图说明这种背景对应着大气耦合效率低。下一步需要用 ERA5/OLR/AGCM 判断它是因果调制还是共同背景。";
    slides[12].reader = "这页用于回答导师可能会问的“已有文章是否已经做过”。现有研究确实讨论了弱降水、遥相关、TNA、MJO 或某个关键月份；你的差异是把问题系统化为 AMJ/JJA/SON/DJF 的多变量耦合效率，并且明确与历史强事件对比。";
    slides[13].notes.push("这三个假设都可以被数据逐步验证：先用 ERA5/OLR 建立大气结构，再用回归残差和 AGCM 实验区分太平洋自身与外海盆贡献。");
    slides[14].notes.push("短期优先级不是马上跑模式，而是把 ERA5 u850/SLP/χ200 与 OLR 接入，使风压、Walker 环流和对流证据达到论文级可靠性。");
  } else {
    slides[1].notes.push("Thus the project is not merely repeating the paper; it uses the paper's ocean-dynamics result to ask why the atmospheric branch did not respond as expected.");
    slides[2].notes.push("For an advisor reading the deck offline, this slide is the roadmap: the first half establishes reliability, and the second half defines the new research space.");
    slides[3].figNote += " How to read: the left panel reproduces the paper's SST, MSLP/u10, and scatter relationships; the right panel compresses them into response ratios. The anomaly is not weak SST, but a weak atmospheric response relative to historical slopes.";
    slides[4].figNote += " How to read: this is the paper's baseline attribution, not the new mechanism. It explains how ocean dynamics produced strong warming, but it does not fully explain why early wind, pressure, and rainfall responses lagged.";
    slides[5].figNote += " How to read: aPac is the canonical Pacific SST-driven atmospheric wind-stress response, while aIndAtl captures Indian-Atlantic external-basin influence. The negative external-basin term suggests possible damping of the Pacific response.";
    slides[6].reader = "This slide separates the paper's contribution from the proposed research space. Peng et al. mainly explain how the strong event was generated by ocean processes; this project asks why the atmosphere failed to respond synchronously once strong SST had already developed. That requires seasonal, multi-variable diagnostics rather than an event-mean view.";
    slides[7].figNote += " How to read: OISST validates SST, GPCP validates rainfall, and NCEP serves as a wind/pressure fallback. Their consistent direction means the ocean-strong / atmosphere-weak signal is not an artifact of the paper source data.";
    slides[8].figNote += " How to read: by Niño-3 alone, AMJ/JJA 2023 already resembles a strong El Niño; however, CWP u and SOI-like metrics do not strengthen synchronously, and the low-level wind response even reverses sign. This is the central new finding so far.";
    slides[9].figNote += " How to read: SST maps show that 2023 spring-summer warming extended beyond the eastern Pacific into external basins and the warm pool; rainfall maps show that central/eastern Pacific convection did not intensify accordingly, motivating a threshold/background-state interpretation.";
    slides[10].figNote += " How to read: NCEP is still a fallback, but it already provides a clear clue: AMJ/JJA central-western Pacific low-level wind is weaker than in historical strong events, and the SLP gradient is not established in a canonical El Niño way.";
    slides[11].figNote += " How to read: the left chart shows unusual spring-summer external-basin warmth, and the right chart shows low coupling efficiency. The next step is to test whether this is causal modulation or a shared background using ERA5/OLR/AGCM evidence.";
    slides[12].reader = "This slide answers the likely advisor question of whether the topic has already been done. Existing papers discuss weak rainfall, teleconnections, TNA, MJO, or individual key months. The distinction here is to systematize the problem as seasonal, multi-variable coupling efficiency against historical strong El Niño events.";
    slides[13].notes.push("Each hypothesis is testable: ERA5/OLR first establish the atmospheric structure, then regression residuals and AGCM experiments separate Pacific-internal and external-basin contributions.");
    slides[14].notes.push("The short-term priority is not to run AGCM immediately, but to add ERA5 u850/SLP/χ200 and OLR so the wind-pressure-Walker-convection evidence becomes manuscript-grade.");
  }
}

function insertGlossaryAndUpdateAppendix() {
  cn.splice(3, 0, {
    kicker: "术语先说明",
    title: "本汇报常用缩写：先把气象量和数据集讲清楚",
    layout: "glossary",
    table: [
      ["缩写", "全称/中文", "在本研究中的含义"],
      ["SST", "Sea Surface Temperature，海表温度", "判断厄尔尼诺海洋增暖强度的核心变量。"],
      ["Niño-3", "东赤道太平洋海温区", "通常取 5°S-5°N、150°W-90°W；本研究用它代表东太平洋增暖。"],
      ["u10 / u850", "10 米 / 850 hPa 纬向风", "东西向风；正值常代表西风异常，能推动暖水东传和海气耦合。"],
      ["SOI / SLP", "南方涛动指数 / 海平面气压", "SOI 反映东西太平洋气压跷跷板；SLP 用于构造类 SOI 压力梯度。"],
      ["OLR / χ200", "向外长波辐射 / 200 hPa 速度势", "OLR 用于判断深对流强弱；χ200 用于诊断 Walker 环流上层辐散。"],
      ["AMJ/JJA/SON/DJF", "4-6月 / 6-8月 / 9-11月 / 12-2月", "按季节拆解 2023/24 事件，重点看发展前期 AMJ 和 JJA。"],
      ["OISST/GPCP/NCEP", "NOAA 海温 / 全球降水 / NCEP 再分析", "当前已使用的公开验证资料；ERA5 和 OLR 是下一步补充。"],
      ["TNA/MC/WPWP/TIO", "热带北大西洋 / 海陆洲 / 西太暖池 / 热带印度洋", "用于描述外海盆和热带背景态异常。"],
    ],
    reader: "阅读建议：后面每页会尽量先写中文全称，再写缩写。若只记一条主线，就是：海表温度很强，但风、气压、降水和对流没有同步给出历史强厄尔尼诺式响应。",
    source: "Definitions follow standard climate diagnostics; variable usage follows docs/data_source_log.md and local analysis scripts.",
  });

  en.splice(3, 0, {
    kicker: "Terms First",
    title: "Common abbreviations in this briefing: variables and datasets before results",
    layout: "glossary",
    table: [
      ["Abbrev.", "Full name", "Meaning in this project"],
      ["SST", "Sea Surface Temperature", "The core ocean variable used to measure El Niño warming strength."],
      ["Niño-3", "Eastern equatorial Pacific SST region", "Usually 5°S-5°N, 150°W-90°W; used here as the eastern-Pacific warming index."],
      ["u10 / u850", "10-m / 850-hPa zonal wind", "East-west wind; positive anomalies usually indicate westerlies that support warm-water eastward propagation."],
      ["SOI / SLP", "Southern Oscillation Index / Sea-Level Pressure", "SOI measures the east-west Pacific pressure seesaw; SLP is used to build SOI-like gradients."],
      ["OLR / χ200", "Outgoing Longwave Radiation / 200-hPa velocity potential", "OLR diagnoses deep convection; χ200 diagnoses upper-level Walker-circulation divergence."],
      ["AMJ/JJA/SON/DJF", "Apr-Jun / Jun-Aug / Sep-Nov / Dec-Feb", "Seasonal windows for the 2023/24 event; AMJ and JJA are the early developing seasons."],
      ["OISST/GPCP/NCEP", "NOAA SST / global precipitation / NCEP reanalysis", "Public datasets already used for validation; ERA5 and OLR are next-stage additions."],
      ["TNA/MC/WPWP/TIO", "Tropical North Atlantic / Maritime Continent / Western Pacific warm pool / Tropical Indian Ocean", "External-basin and tropical-background regions used in the mechanism diagnostics."],
    ],
    reader: "Reading guide: later slides spell out the full name before using abbreviations where possible. The one-line storyline is that SST was strong, but wind, pressure, rainfall, and convection did not respond in the historical strong-El Niño way.",
    source: "Definitions follow standard climate diagnostics; variable usage follows docs/data_source_log.md and local analysis scripts.",
  });

  const cnAppendix = cn.find((slide) => slide.kicker === "附录 A");
  if (cnAppendix) {
    cnAppendix.table = [
      ["页码", "图/结论", "对应数据表"],
      ["5", "Fig.1 事件强度与耦合响应比", "fig1_event_coupling.csv"],
      ["6", "Fig.2 赤道剖面/传播诊断", "fig2_equatorial_summary.csv"],
      ["7", "Fig.3-4 AGCM 与风应力实验", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["9", "OISST/GPCP/NCEP 独立验证", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["10", "AMJ/JJA 历史耦合效率", "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"],
      ["11-12", "AMJ/JJA 空间 SST/降水/风压", "stage_a_spatial_summary.csv"],
      ["13", "外海盆暖异常与季节效率", "external_basin_seasonal_summary.csv"],
    ];
  }

  const enAppendix = en.find((slide) => slide.kicker === "Appendix A");
  if (enAppendix) {
    enAppendix.table = [
      ["Slide", "Figure / claim", "Corresponding table"],
      ["5", "Fig. 1 event strength and coupling ratios", "fig1_event_coupling.csv"],
      ["6", "Fig. 2 equatorial propagation diagnostics", "fig2_equatorial_summary.csv"],
      ["7", "Fig. 3-4 AGCM and wind-stress experiments", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["9", "OISST/GPCP/NCEP independent validation", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["10", "AMJ/JJA historical coupling efficiency", "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"],
      ["11-12", "AMJ/JJA spatial SST/rainfall/wind/pressure", "stage_a_spatial_summary.csv"],
      ["13", "External-basin warmth and seasonal efficiency", "external_basin_seasonal_summary.csv"],
    ];
  }
}

enrichForReading(cn, "cn");
enrichForReading(en, "en");
insertGlossaryAndUpdateAppendix();

await writeNotes();
await writeDeck("cn", cn);
await writeDeck("en", en);
console.log(JSON.stringify({ workspace: WORKSPACE, slides: { cn: cn.length, en: en.length } }, null, 2));
