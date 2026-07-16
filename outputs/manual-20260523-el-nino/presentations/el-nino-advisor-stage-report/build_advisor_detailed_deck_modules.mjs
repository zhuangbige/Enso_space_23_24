#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(new URL("../../../..", import.meta.url).pathname);
const WORKSPACE = path.join(ROOT, "outputs/manual-20260523-el-nino/presentations/el-nino-advisor-stage-report");
const DETAIL = path.join(WORKSPACE, "detailed");
const OLD_ASSETS = path.join(ROOT, "outputs/manual-20260523-el-nino/presentations/el-nino-decoupling-opening/assets");
const PENG = path.join(ROOT, "data/derived/peng2025_repro/figures");
const RESEARCH = path.join(ROOT, "data/derived/research");

const img = {
  fig1: path.join(PENG, "Fig1.png"),
  fig2: path.join(PENG, "Fig2.png"),
  fig3: path.join(PENG, "Fig3.png"),
  fig4: path.join(PENG, "Fig4.png"),
  coupling: path.join(OLD_ASSETS, "coupling_ratios.png"),
  validation: path.join(OLD_ASSETS, "validation_summary.png"),
  seasonal: path.join(RESEARCH, "seasonal_asynchrony_figure.png"),
  seasonalRegression: path.join(RESEARCH, "seasonal_regression_asynchrony_matrix.png"),
  asyncBars: path.join(RESEARCH, "asynchronous_coupling_by_season.png"),
  external: path.join(OLD_ASSETS, "external_basin_bars.png"),
  sstPrecip: path.join(RESEARCH, "stage_a_amj_jja_sst_precip.png"),
  windSlp: path.join(RESEARCH, "stage_a_amj_jja_ncep_wind_slp.png"),
};

const cn = [
  {
    k: "导师阅读版",
    t: "2023/24 强厄尔尼诺海气脱耦：复现、问题提出与阶段性创新",
    layout: "cover",
    sub: "目标：让不熟悉该方向的读者也能看懂每张图的数据来源、物理含义、与原文关系和本研究新增内容。",
    bullets: ["先解释缩写和变量，避免直接进入专业简称。", "每张图都写明：数据名称、反映了什么、对应原文什么、我的创新在哪里。", "字体和图注加大，牺牲一点页数，换取可独立阅读性。"],
    src: "Peng et al. 2025; NOAA OISST; GPCP; NCEP/NCAR R1; local diagnostics. 2026-05-24.",
  },
  {
    k: "总判断",
    t: "目前主线已经从“复现原文”推进到“分季节预期响应偏弱”的新问题",
    layout: "text",
    claim: "原文证明 2023/24 强厄尔尼诺主要由海洋动力生成，但同时暴露出一个关键异常：海温很强，大气端的风、气压和降水响应却偏弱。",
    points: [
      "本研究接着问：这种弱响应最早从哪个季节出现？是全年平均现象，还是发展季 AMJ/JJA 就已经发生？",
      "目前阶段性结果显示：2023 年春夏 Niño-3 海表温度驱动已经建立，但 ERA5 风压、GPCP 降水和 CPC OLR 对流响应都低于历史 Niño-3 回归关系预期。",
      "因此，新研究的入口不是再证明 2023/24 是强厄尔尼诺，而是解释为什么强海温没有触发典型强厄尔尼诺式的大气耦合。"
    ],
    src: "Synthesis from reproduced Peng et al. figures and data/derived/research seasonal diagnostics.",
  },
  {
    k: "术语先说明",
    t: "本报告常见缩写和变量",
    layout: "glossary",
    rows: [
      ["缩写", "全称", "本研究中的意思"],
      ["SST", "海表温度", "判断厄尔尼诺海洋增暖强度。"],
      ["Niño-3", "东赤道太平洋海温区", "代表东太平洋暖异常，常用于描述厄尔尼诺强度。"],
      ["u10 / u850", "10 米 / 850 hPa 纬向风", "东西向风；西风异常可加强海气耦合。"],
      ["SOI / SLP", "南方涛动指数 / 海平面气压", "衡量东西太平洋气压跷跷板和 Walker 环流响应。"],
      ["OLR / χ200", "向外长波辐射 / 200 hPa 速度势", "分别反映深对流和上层大尺度环流。"],
      ["AMJ/JJA", "4-6月 / 6-8月", "本研究重点的发展前期季节。"],
      ["TNA/MC/WPWP/TIO", "热带北大西洋/海陆洲/西太暖池/热带印度洋", "外海盆和热带背景态重点区域。"],
    ],
    src: "Standard climate diagnostics and docs/data_source_log.md.",
  },
  {
    k: "原文贡献",
    t: "Peng et al. 2025 主要回答了：强 2023/24 El Niño 是怎样生成的",
    layout: "tableText",
    rows: [
      ["层面", "原文结论", "对本研究的作用"],
      ["海洋端", "赤道太平洋海洋动力和热含量过程使 2023/24 事件变强。", "提供了“海温为什么强”的基础。"],
      ["大气端", "相对于历史强厄尔尼诺，大气风压反馈偏弱。", "引出“强海温为何没有强响应”的问题。"],
      ["外海盆", "印度洋和大西洋 SST 可能抵消部分太平洋强迫。", "提示外海盆背景态可能是机制切口。"],
      ["模式实验", "AGCM 和风应力实验区分了海温边界和风场强迫。", "为后续设计 Pacific-only / external-basin 实验提供模板。"],
    ],
    text: "所以，我不是推翻原文，而是在原文基础上把问题往大气耦合端推进：原文解释了强海温的生成，本研究解释强海温为什么没有带来同步的大气响应。",
    src: "L1: Peng et al. 2025 Nature Geoscience.",
  },
  {
    k: "原文复现 Fig. 1",
    t: "图中数据名称：SST、海平面气压/10米风、Niño-3 与大气响应散点",
    layout: "figureExplain",
    image: img.fig1,
    boxes: [
      ["这幅图是什么数据", "Peng et al. Fig. 1 的源数据。上半部分是 2023/24 与历史强事件的海表温度、海平面气压和 10 米风异常；下半部分是 Niño-3 海温与 u10、SOI 的历史关系。"],
      ["它反映了什么", "2023/24 的 Niño-3 海温很强，但对应的近地面风和气压响应偏弱，说明海洋强度和大气响应强度没有按历史经验同步增长。"],
      ["对应原文与我的创新", "对应原文的核心事实复现。创新不是这页本身，而是后续把这个全年/成熟期事实拆到 AMJ/JJA 发展前期，追问弱响应何时开始。"],
    ],
    src: "Data: Peng et al. source archive; local file Fig1.png; table fig1_event_coupling.csv.",
  },
  {
    k: "复现数值化 Fig. 1",
    t: "图中数据名称：u10 和 SOI 相对历史强事件的响应比",
    layout: "figureExplain",
    image: img.coupling,
    boxes: [
      ["这幅图是什么数据", "从 fig1_event_coupling.csv 提取的事件指标。Niño-3 表示海温强度，u10 表示 10 米纬向风，SOI 表示南方涛动指数。"],
      ["它反映了什么", "2023 年 u10 响应比约 0.27，SOI 响应比约 0.31，即大气响应只有历史强厄尔尼诺期望值的大约三分之一。"],
      ["对应原文与我的创新", "对应原文 Fig. 1 的“强海温、弱大气”结论。我的创新是把 observed / expected response 思路扩展到 AMJ/JJA/SON/DJF 的季节尺度，而不是只做全年单点对比。"],
    ],
    src: "Derived table: data/derived/peng2025_repro/tables/fig1_event_coupling.csv.",
  },
  {
    k: "原文复现 Fig. 2",
    t: "图中数据名称：赤道太平洋传播、次表层热结构和海洋动力诊断",
    layout: "figureExplain",
    image: img.fig2,
    boxes: [
      ["这幅图是什么数据", "Peng et al. Fig. 2 的赤道剖面和时间-经度诊断，展示海温、次表层热异常、传播特征和风应力相关信号。"],
      ["它反映了什么", "原文用这组图证明 2023/24 强海温不是偶然表层变暖，而是受到赤道太平洋海洋动力过程支持。"],
      ["对应原文与我的创新", "对应原文的海洋动力归因部分。本研究接受这个结论，并把研究焦点转向：既然海洋端足够强，为什么大气端没有同步跟上？"],
    ],
    src: "Data: Peng et al. source archive; local Fig2.png; table fig2_equatorial_summary.csv.",
  },
  {
    k: "原文复现 Fig. 3",
    t: "图中数据名称：AGCM 海温强迫实验中的风应力响应",
    layout: "figureExplain",
    image: img.fig3,
    boxes: [
      ["这幅图是什么数据", "AGCM 即大气环流模式实验。原文把全球 SST、太平洋 SST、印度洋/大西洋 SST 等边界条件分开，比较大气风应力响应。"],
      ["它反映了什么", "太平洋暖 SST 本应激发较强大气响应，但印度洋和大西洋背景可能提供相反或抵消作用。表格中 aPac 风应力为正，aIndAtl 风应力为负。"],
      ["对应原文与我的创新", "对应原文外海盆调制思路。我的创新是先不用马上跑模式，而是用观测资料分季节诊断外海盆暖异常是否与弱大气响应同步出现。"],
    ],
    src: "Data: Peng et al. source archive; table fig3_agcm_summary.csv.",
  },
  {
    k: "原文复现 Fig. 4",
    t: "图中数据名称：风应力实验对 Niño-3 海温发展的影响",
    layout: "figureExplain",
    image: img.fig4,
    boxes: [
      ["这幅图是什么数据", "原文风应力实验，比较不同风场设定下 Niño-3 海温的发展。关键数值包括 Dec Niño-3 CTRL=2.344，Wind2023=0.681。"],
      ["它反映了什么", "2023 年实际风场并没有像典型强厄尔尼诺那样强力推动海温增长，说明大气风强迫本身偏弱。"],
      ["对应原文与我的创新", "对应原文“2023 风场偏弱”的实验佐证。我的创新是把这个偏弱风场进一步定位到 AMJ/JJA 发展季，并与降水、气压一起比较。"],
    ],
    src: "Data: Peng et al. source archive; table fig4_wind_experiment_summary.csv.",
  },
  {
    k: "从原文到新问题",
    t: "原文留下的缺口：弱耦合是何时出现的？是否与外海盆背景态有关？",
    layout: "text",
    claim: "如果只说“2023/24 大气响应弱”，还不够形成新论文。必须进一步回答：弱响应发生在发展季、成熟期，还是全程？哪些变量最先低于历史 Niño-3 关系的预期？",
    points: [
      "原文主要围绕事件生成和海洋动力过程展开，季节性的风压/降水/对流不同步还没有被系统展开。",
      "我的研究把响应变量拆成海表温度、低层风、海平面气压、降水、OLR 和 Walker 环流，再按 AMJ/JJA/SON/DJF 比较。",
      "目前主方法沿用原文 observed / expected response 思路：每个季节分别用历史 Niño-3 与大气变量的回归关系估计预期响应，再看 2023 实际响应偏离多少。"
    ],
    src: "Research transition based on L1 and local seasonal diagnostics.",
  },
  {
    k: "独立资料验证",
    t: "图中数据名称：OISST、GPCP、NCEP/NCAR 对原文指标的再计算",
    layout: "figureExplain",
    image: img.validation,
    boxes: [
      ["这幅图是什么数据", "OISST 是 NOAA 海表温度资料，GPCP 是全球降水资料，NCEP/NCAR R1 是再分析风压资料。图中显示它们与复现指标的相关或一致性。"],
      ["它反映了什么", "OISST Niño-3 与原文复现相关 0.9999；NCEP 风和类 SOI 压力梯度也高度一致。这说明核心事实不是单一论文数据集造成的。"],
      ["对应原文与我的创新", "对应原文 Fig. 1-2 的外部资料验证。创新是把复现结果转为公开数据链条，为后续自己的季节诊断建立可追溯基础。"],
    ],
    src: "Tables: oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv.",
  },
  {
    k: "新研究发现 1",
    t: "图中数据名称：AMJ/JJA/SON/DJF 分季节回归预期响应矩阵",
    layout: "figureExplain",
    image: img.seasonalRegression,
    boxes: [
      ["这幅图是什么数据", "左图为 2023 年实际大气响应除以历史 Niño-3 回归关系给出的预期响应，分别计算 AMJ、JJA、SON、DJF。右图为外海盆 SST 相对历史强事件 composite 的差值。"],
      ["它反映了什么", "AMJ/JJA 已经出现明显弱响应：ERA5 中西太平洋 u10 在 AMJ 为 -0.38、JJA 为 0.06；SOI-like、GPCP 降水和 CPC OLR 也均低于 1。"],
      ["对应原文与我的创新", "原文在事件尺度比较 observed 与 expected response；本研究把同一逻辑季节化，并扩展到风压、降水和对流链条。"],
    ],
    src: "Tables: seasonal_regression_expected_response.csv; external_basin_seasonal_summary.csv.",
  },
  {
    k: "新研究发现 2",
    t: "图中数据名称：AMJ/JJA 海表温度和 GPCP 降水空间异常",
    layout: "figureExplain",
    image: img.sstPrecip,
    boxes: [
      ["这幅图是什么数据", "上排是 OISST 海表温度，下面是 GPCP 降水。每个格点都是 2023 AMJ/JJA 减去历史强厄尔尼诺 composite。"],
      ["它反映了什么", "2023 春夏不只是东太平洋暖，热带北大西洋、海陆洲和西太暖池也显著偏暖；但中东太平洋降水没有同步增强，甚至相对历史强事件偏弱。"],
      ["对应原文与我的创新", "对应原文关于外海盆 SST 可能调制响应的提示。我的创新是给出发展季空间证据，说明外海盆暖背景和弱降水响应同时出现。"],
    ],
    src: "Data: NOAA OISST v2.1 and GPCP; summary table stage_a_spatial_summary.csv.",
  },
  {
    k: "新研究发现 3",
    t: "图中数据名称：AMJ/JJA 近地面风和海平面气压空间异常",
    layout: "figureExplain",
    image: img.windSlp,
    boxes: [
      ["这幅图是什么数据", "NCEP/NCAR R1 的近地面 sigma995 风和海平面气压 SLP，计算 2023 AMJ/JJA 相对历史强事件 composite 的差值。"],
      ["它反映了什么", "中西太平洋低层风异常相对历史强事件偏弱，海平面气压梯度也没有建立出典型强厄尔尼诺结构。这支持“Walker 环流响应不典型”。"],
      ["对应原文与我的创新", "对应原文中风场偏弱的发现。创新是把风和气压做成发展季空间对比，指出 AMJ/JJA 已经出现大气端不同步。"],
    ],
    src: "Data: NCEP/NCAR R1 fallback; final manuscript stage should verify with ERA5.",
  },
  {
    k: "新研究发现 4",
    t: "图中数据名称：外海盆暖异常指数与早期耦合探索图",
    layout: "twoFigureExplain",
    left: img.external,
    right: img.asyncBars,
    boxes: [
      ["这幅图是什么数据", "左图是 OISST 计算的热带北大西洋、西太暖池、海陆洲和热带印度洋海温差值；右图是早期 composite-based 耦合探索图。"],
      ["它反映了什么", "2023 春夏外海盆和西太暖池明显偏暖，同时旧版探索图也提示太平洋大气响应偏弱。现在主结论以回归预期矩阵为准，这页作为背景和稳健性线索。"],
      ["对应原文与我的创新", "原文用 AGCM 提示外海盆可能抵消太平洋响应；本页说明 2023 发展季确实存在异常暖的外海盆背景。"],
    ],
    src: "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_efficiency.csv.",
  },
  {
    k: "核心数值",
    t: "2023 春夏不是海温驱动弱，而是大气响应低于历史回归预期",
    layout: "tableText",
    rows: [
      ["指标", "AMJ", "JJA"],
      ["Niño-3 海温异常，作为回归预测因子", "0.97°C", "1.73°C"],
      ["ERA5 中西太平洋 u10 实际/预期", "-0.38", "0.06"],
      ["ERA5 SOI-like 海平面气压实际/预期", "0.56", "0.41"],
      ["GPCP 中太平洋降水实际/预期", "0.35", "0.46"],
      ["CPC 中太平洋 OLR 实际/预期", "0.17", "0.26"],
    ],
    text: "每个季节分别用历史 Niño-3 海温异常和大气变量异常建立回归关系，由此得到 2023 年在该海温强度下应有的大气响应。数值低于 1 表示弱于历史回归预期；小于 0 表示响应方向相反。",
    src: "Table: seasonal_regression_expected_response.csv. Data: OISST Niño-3, ERA5 u10/SLP, GPCP precipitation, CPC blended OLR.",
  },
  {
    k: "与现有研究区别",
    t: "已有研究解释单个机制或月份，本研究把原文预期响应逻辑系统化到季节尺度",
    layout: "tableText",
    rows: [
      ["文献", "已有重点", "本研究新增"],
      ["Peng et al. 2025", "海洋动力生成强事件；事件尺度风场/SOI 弱响应", "将 observed/expected response 从事件尺度扩展到 AMJ/JJA/SON/DJF。"],
      ["Zhang et al. 2025", "弱降水/遥相关与外海盆加热", "把降水弱响应放入风压-降水-对流的同一季节矩阵。"],
      ["Kim et al. 2025", "发展季风场与西中太梯度", "加入 SOI-like 气压、GPCP 降水、CPC OLR 和回归预期比较。"],
      ["Zhao et al. 2025", "2023 年 7 月 TNA 和季风/海陆洲加热", "将单月机制扩展为 AMJ-JJA 发展季建立窗口。"],
      ["Yang & Li 2025", "2024 年 1 月 MJO/trend/ENSO 分解", "在日尺度 MJO/OLR 机制前，先建立发展季背景诊断。"],
    ],
    text: "因此，本研究的差异不是只多加一个资料集，而是把“弱响应”拆成时间维度和变量链条：哪一季开始低于预期、哪个变量最先不同步、外海盆暖背景是否同步异常。",
    src: "Literature notes: docs/literature_method_notes.md; source IDs L1-L8; main diagnostic table: seasonal_regression_expected_response.csv.",
  },
  {
    k: "拟定研究题目",
    t: "建议题目：2023/24 强厄尔尼诺发展季海气耦合失效及其外海盆背景态调制",
    layout: "text",
    claim: "工作假设：2023 春夏热带外海盆暖异常和热带平均增暖背景改变了 Walker 环流和对流阈值，使太平洋暖 SST 对低层风、海平面气压和降水的典型响应滞后或减弱。",
    points: [
      "假设 1：热带北大西洋、印度洋和海陆洲暖异常改变大尺度热力背景，抑制中太平洋西风响应。",
      "假设 2：海陆洲/印度洋对流维持在西侧，使典型 El Niño 降水中心东移不充分。",
      "假设 3：热带平均增暖提高对流触发阈值，使同样的太平洋 SST 异常对应更弱大气反馈。"
    ],
    src: "Current diagnostics establish association; mechanism attribution requires ERA5, OLR, MJO/RMM and AGCM tests.",
  },
  {
    k: "下一步数据",
    t: "下一版研究图需要补什么数据",
    layout: "tableText",
    rows: [
      ["数据", "用途", "为什么需要"],
      ["ERA5 pressure-level u850 / χ200", "补充低层风垂直层和 Walker 环流。", "single-level u10/SLP 已接入，pressure-level 环流仍是下一步。"],
      ["ERA5 AMJ/JJA 空间图", "替换 NCEP fallback 风压空间图。", "让发展季风压证据进入论文级资料链。"],
      ["ERSSTv5 / detrended SST", "长记录与去趋势稳健性。", "检查外海盆偏暖是否主要来自背景增暖趋势。"],
      ["MJO/RMM 或日资料", "拆解 2024 年 1 月等关键月份。", "区分 ENSO 背景、MJO 和趋势影响。"],
    ],
    text: "短期优先级是把 ERA5 AMJ/JJA 风压空间图和 pressure-level Walker 环流补齐。AGCM 仍作为后续机制归因预案，而不是当前汇报的必要前提。",
    src: "Data priorities from reports/当前数据分析阶段总结.md.",
  },
  {
    k: "附录 A",
    t: "每页图对应的数据表",
    layout: "appendix",
    rows: [
      ["页码", "图/内容", "数据表"],
      ["5-6", "原文 Fig. 1 与耦合响应比", "fig1_event_coupling.csv"],
      ["7", "原文 Fig. 2 海洋动力诊断", "fig2_equatorial_summary.csv"],
      ["8-9", "原文 Fig. 3-4 AGCM/风应力实验", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["11", "公开资料验证", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["12", "分季节回归预期响应矩阵", "seasonal_regression_expected_response.csv; external_basin_seasonal_summary.csv"],
      ["13-14", "AMJ/JJA 空间图", "stage_a_spatial_summary.csv"],
      ["15-16", "外海盆和历史对比", "external_basin_seasonal_summary.csv; gpcp_precip_seasonal_summary.csv"],
    ],
    src: "All local paths are under /Users/daiyue/Documents/Maryland/data/derived.",
  },
  {
    k: "附录 B",
    t: "数据和文献链接",
    layout: "appendix",
    rows: [
      ["来源", "链接", "用途"],
      ["Peng et al. 2025", "nature.com/articles/s41561-025-01700-9", "原文复现与问题来源"],
      ["NOAA OISST", "ncei.noaa.gov/products/optimum-interpolation-sst", "海表温度"],
      ["GPCP", "psl.noaa.gov/data/gridded/data.gpcp.html", "降水"],
      ["NCEP/NCAR R1", "psl.noaa.gov/data/reanalysis/", "风压 fallback"],
      ["ERA5", "cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels", "single-level u10/SLP 已用；下一步 pressure-level Walker"],
      ["NOAA OLR", "psl.noaa.gov/data/gridded/data.interp_OLR.html", "下一步对流验证"],
      ["ERSSTv5", "ncei.noaa.gov/products/extended-reconstructed-sst", "长记录稳健性"],
    ],
    src: "Full source log: docs/data_source_log.md.",
  },
];

const en = [
  {
    k: "Advisor Reading Version",
    t: "Atmosphere-ocean decoupling during the 2023/24 strong El Niño: reproduction, open question, and new diagnostics",
    layout: "cover",
    sub: "Goal: make every figure readable without oral explanation by stating the data name, physical meaning, link to the original paper, and new contribution.",
    bullets: ["Explain variables and abbreviations before using them heavily.", "For each figure, state: data name, what it shows, how it maps to Peng et al. 2025, and what is new here.", "Use larger explanatory text, accepting a slightly longer deck."],
    src: "Peng et al. 2025; NOAA OISST; GPCP; NCEP/NCAR R1; local diagnostics. 2026-05-24.",
  },
  {
    k: "Bottom Line",
    t: "The project has moved from reproducing the paper to diagnosing developing-season coupling loss",
    layout: "text",
    claim: "Peng et al. show that ocean dynamics generated the strong 2023/24 El Niño, but the event also exposes a key anomaly: SST was strong while wind, pressure, and rainfall responses were weak.",
    points: [
      "This project asks when the weak atmospheric response first emerged: only in the mature season, or already during AMJ/JJA development?",
      "Current diagnostics show that spring-summer 2023 Niño-3 SST was already historically strong, while central-west Pacific wind, SOI-like pressure gradient, and rainfall did not strengthen synchronously.",
      "The new question is therefore not whether 2023/24 was a strong El Niño, but why strong Pacific SST failed to trigger the historical strong-El Niño atmospheric response."
    ],
    src: "Synthesis from reproduced Peng et al. figures and data/derived/research seasonal diagnostics.",
  },
  {
    k: "Terms First",
    t: "Common variables and abbreviations in this deck",
    layout: "glossary",
    rows: [
      ["Abbrev.", "Full name", "Meaning in this project"],
      ["SST", "Sea Surface Temperature", "Core ocean variable for El Niño warming strength."],
      ["Niño-3", "Eastern equatorial Pacific SST region", "Index region representing eastern-Pacific warming."],
      ["u10 / u850", "10-m / 850-hPa zonal wind", "East-west wind; westerly anomalies support coupling."],
      ["SOI / SLP", "Southern Oscillation Index / Sea-Level Pressure", "Pressure seesaw and Walker-circulation response."],
      ["OLR / χ200", "Outgoing Longwave Radiation / 200-hPa velocity potential", "Deep convection and upper-level circulation diagnostics."],
      ["AMJ/JJA", "Apr-Jun / Jun-Aug", "Early developing seasons emphasized here."],
      ["TNA/MC/WPWP/TIO", "Tropical North Atlantic / Maritime Continent / Western Pacific warm pool / Tropical Indian Ocean", "External-basin and tropical-background regions."],
    ],
    src: "Standard climate diagnostics and docs/data_source_log.md.",
  },
  {
    k: "Paper Contribution",
    t: "Peng et al. 2025 mainly answers how the strong 2023/24 El Niño was generated",
    layout: "tableText",
    rows: [
      ["Layer", "Paper conclusion", "Role for this project"],
      ["Ocean", "Equatorial Pacific ocean dynamics and heat content made the event strong.", "Provides the baseline explanation for strong SST."],
      ["Atmosphere", "Wind-pressure feedback was weak relative to historical strong El Niño events.", "Raises the weak-response question."],
      ["External basins", "Indian and Atlantic SST may offset part of the Pacific forcing.", "Suggests a mechanism pathway."],
      ["Experiments", "AGCM and wind-stress experiments separate SST-boundary and wind-forcing effects.", "Guides future Pacific-only and external-basin experiments."],
    ],
    text: "This project does not overturn the paper. It extends the logic from oceanic event generation to atmospheric coupling: why did strong SST not produce a synchronous atmospheric response?",
    src: "L1: Peng et al. 2025 Nature Geoscience.",
  },
  {
    k: "Reproduced Fig. 1",
    t: "Data shown: SST, sea-level pressure / 10-m wind, and Niño-3 versus atmospheric-response scatterplots",
    layout: "figureExplain",
    image: img.fig1,
    boxes: [
      ["Data name", "Peng et al. Fig. 1 source data. The top panels show SST, sea-level pressure, and 10-m wind anomalies; the bottom panels relate Niño-3 SST to u10 and SOI."],
      ["What it shows", "The 2023/24 Niño-3 SST was strong, but near-surface wind and pressure responses were weak relative to historical relationships."],
      ["Paper link and innovation", "This reproduces the paper's core fact. The new contribution comes later: turning the event-level fact into seasonal AMJ/JJA coupling-efficiency diagnostics."],
    ],
    src: "Data: Peng et al. source archive; local file Fig1.png; table fig1_event_coupling.csv.",
  },
  {
    k: "Quantified Fig. 1",
    t: "Data shown: u10 and SOI response ratios relative to historical strong El Niño behavior",
    layout: "figureExplain",
    image: img.coupling,
    boxes: [
      ["Data name", "Event metrics extracted from fig1_event_coupling.csv. Niño-3 is SST strength, u10 is 10-m zonal wind, and SOI is the Southern Oscillation Index."],
      ["What it shows", "The 2023 u10 response ratio is about 0.27 and the SOI response ratio is about 0.31, roughly one-third of the expected historical response."],
      ["Paper link and innovation", "This corresponds to Peng et al. Fig. 1. The innovation is to generalize this response-ratio idea into a seasonal coupling matrix."],
    ],
    src: "Derived table: data/derived/peng2025_repro/tables/fig1_event_coupling.csv.",
  },
  {
    k: "Reproduced Fig. 2",
    t: "Data shown: equatorial Pacific propagation, subsurface heat structure, and ocean-dynamical diagnostics",
    layout: "figureExplain",
    image: img.fig2,
    boxes: [
      ["Data name", "Peng et al. Fig. 2 equatorial sections and longitude-time diagnostics showing SST, subsurface heat anomalies, propagation, and wind-stress-related signals."],
      ["What it shows", "The strong 2023/24 warming was supported by ocean dynamics, not merely by a surface-temperature fluctuation."],
      ["Paper link and innovation", "This reproduces the paper's ocean-dynamics attribution. The new project accepts this and asks why the atmosphere did not respond proportionally."],
    ],
    src: "Data: Peng et al. source archive; local Fig2.png; table fig2_equatorial_summary.csv.",
  },
  {
    k: "Reproduced Fig. 3",
    t: "Data shown: wind-stress response in Atmospheric General Circulation Model experiments",
    layout: "figureExplain",
    image: img.fig3,
    boxes: [
      ["Data name", "AGCM experiments separating global SST, Pacific SST, and Indian/Atlantic SST boundary conditions and comparing atmospheric wind-stress responses."],
      ["What it shows", "Pacific warm SST should drive a canonical atmospheric response, but Indian and Atlantic background SST can offset or damp that response."],
      ["Paper link and innovation", "This follows the paper's external-basin modulation idea. The new step is to test the same idea first with observed seasonal diagnostics."],
    ],
    src: "Data: Peng et al. source archive; table fig3_agcm_summary.csv.",
  },
  {
    k: "Reproduced Fig. 4",
    t: "Data shown: wind-stress experiments and their effect on Niño-3 SST development",
    layout: "figureExplain",
    image: img.fig4,
    boxes: [
      ["Data name", "Wind-stress experiments comparing Niño-3 SST evolution under different wind forcing settings. Key values include Dec Niño-3 CTRL=2.344 and Wind2023=0.681."],
      ["What it shows", "The actual 2023 wind field did not force ocean warming as strongly as a canonical strong El Niño wind pattern would."],
      ["Paper link and innovation", "This supports the paper's weak-wind point. The new contribution is to locate weak wind-pressure coupling during AMJ/JJA and compare it with rainfall."],
    ],
    src: "Data: Peng et al. source archive; table fig4_wind_experiment_summary.csv.",
  },
  {
    k: "From Paper To Question",
    t: "Open gap: when did weak coupling appear, and was it linked to the external-basin background?",
    layout: "text",
    claim: "Saying that the 2023/24 atmospheric response was weak is not enough for a new paper. We need to know whether weak coupling emerged during development, maturity, or throughout the event.",
    points: [
      "Peng et al. focuses mainly on event generation and ocean dynamics; seasonal wind-pressure-rainfall-convection asynchrony remains less systematically developed.",
      "This project separates SST, low-level wind, sea-level pressure, rainfall, OLR, and Walker circulation across AMJ/JJA/SON/DJF.",
      "That turns a broad weak-response statement into a testable seasonal coupling-efficiency problem."
    ],
    src: "Research transition based on L1 and local seasonal diagnostics.",
  },
  {
    k: "Raw Validation",
    t: "Data shown: OISST, GPCP, and NCEP/NCAR recalculations of paper-related metrics",
    layout: "figureExplain",
    image: img.validation,
    boxes: [
      ["Data name", "OISST is NOAA SST, GPCP is global precipitation, and NCEP/NCAR R1 is reanalysis wind and pressure. The chart summarizes agreement with reproduced indices."],
      ["What it shows", "OISST Niño-3 correlates 0.9999 with the reproduced Fig. 1 index; NCEP wind and SOI-like pressure proxies are also highly consistent."],
      ["Paper link and innovation", "This validates the paper-level signal with public data. The innovation is building a traceable raw-data pipeline for original seasonal diagnostics."],
    ],
    src: "Tables: oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv.",
  },
  {
    k: "New Finding 1",
    t: "Data shown: seasonal coupling-efficiency matrix for AMJ/JJA/SON/DJF",
    layout: "figureExplain",
    image: img.seasonal,
    boxes: [
      ["Data name", "OISST Niño-3, NCEP central-west Pacific low-level wind, SOI-like SLP gradient, and GPCP rainfall compared with the 1982/83, 1997/98, and 2015/16 strong-event composite."],
      ["What it shows", "AMJ/JJA 2023 SST was already historically strong, but wind-pressure-rainfall response efficiency was low. AMJ CWP wind ratio is about -0.43, and JJA is about -0.14."],
      ["Paper link and innovation", "Peng et al. identifies event-level weak coupling; the innovation here is locating it in the developing season and identifying which variables desynchronize first."],
    ],
    src: "Tables: asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv.",
  },
  {
    k: "New Finding 2",
    t: "Data shown: AMJ/JJA SST and GPCP rainfall spatial anomalies",
    layout: "figureExplain",
    image: img.sstPrecip,
    boxes: [
      ["Data name", "Top panels: OISST sea-surface temperature. Bottom panels: GPCP precipitation. Each map is 2023 AMJ/JJA minus the historical strong-El Niño composite."],
      ["What it shows", "Spring-summer 2023 warming extended beyond the eastern Pacific into TNA, the Maritime Continent, and the western Pacific warm pool, while central/eastern Pacific rainfall did not strengthen."],
      ["Paper link and innovation", "This corresponds to the paper's external-basin modulation hint. The innovation is developing-season spatial evidence tying warm background conditions to weak rainfall response."],
    ],
    src: "Data: NOAA OISST v2.1 and GPCP; summary table stage_a_spatial_summary.csv.",
  },
  {
    k: "New Finding 3",
    t: "Data shown: AMJ/JJA near-surface wind and sea-level-pressure spatial anomalies",
    layout: "figureExplain",
    image: img.windSlp,
    boxes: [
      ["Data name", "NCEP/NCAR R1 near-surface sigma995 wind and sea-level pressure, calculated as 2023 AMJ/JJA minus the historical strong-event composite."],
      ["What it shows", "Central-west Pacific low-level wind is weaker than in historical strong events, and the pressure-gradient pattern is not a canonical strong-El Niño Walker response."],
      ["Paper link and innovation", "This corresponds to the paper's weak-wind finding. The innovation is making it seasonal and spatial, showing that AMJ/JJA already contains atmospheric asynchrony."],
    ],
    src: "Data: NCEP/NCAR R1 fallback; final manuscript stage should verify with ERA5.",
  },
  {
    k: "New Finding 4",
    t: "Data shown: external-basin warm anomalies and seasonal coupling efficiency",
    layout: "twoFigureExplain",
    left: img.external,
    right: img.asyncBars,
    boxes: [
      ["Data name", "Left: OISST indices for TNA, western Pacific warm pool, Maritime Continent, and Tropical Indian Ocean. Right: seasonal coupling-efficiency diagnostics."],
      ["What it shows", "Unusual external-basin warmth and low Pacific atmospheric coupling efficiency occur together in spring-summer 2023."],
      ["Paper link and innovation", "Peng et al. suggests external basins may damp Pacific response. The new step is observationally confirming that these warm anomalies were present during the coupling-loss season."],
    ],
    src: "Tables: external_basin_seasonal_summary.csv; asynchronous_coupling_efficiency.csv.",
  },
  {
    k: "Historical Summary",
    t: "Key numbers: spring-summer 2023 was not SST-weak; it was atmosphere-response weak",
    layout: "tableText",
    rows: [
      ["Metric", "AMJ", "JJA"],
      ["Niño-3 SST relative to strong-event composite", "1.41x", "1.22x"],
      ["Central-west Pacific low-level wind ratio", "-0.43x", "-0.14x"],
      ["SOI-like pressure-response efficiency", "0.22", "0.28"],
      ["Central Pacific GPCP rainfall ratio", "0.43", "0.38"],
    ],
    text: "Together, these values show that the developing-season ocean state was already strong, but the atmospheric branch did not produce the usual westerly-wind, pressure-gradient, and rainfall-displacement responses.",
    src: "Tables: asynchronous_coupling_efficiency.csv; gpcp_precip_seasonal_summary.csv.",
  },
  {
    k: "Difference From Literature",
    t: "Existing studies emphasize mechanisms or individual months; this project systematizes seasonal coupling efficiency",
    layout: "tableText",
    rows: [
      ["Study", "Existing focus", "New contribution here"],
      ["Peng et al. 2025", "Ocean-dynamical event generation", "Why and when the atmospheric response weakened."],
      ["Zhang et al. 2025", "Weak rainfall/teleconnections and external-basin heating", "Seasonal matrix across wind, pressure, rainfall, and SST."],
      ["Kim et al. 2025", "Developing-season wind anomalies and west-central Pacific gradients", "Adds SOI-like pressure, GPCP rainfall, and external-basin historical comparison."],
      ["Zhao et al. 2025", "July 2023 TNA and monsoon/Maritime Continent heating", "Tracks AMJ/JJA through SON/DJF continuously."],
      ["Yang & Li 2025", "January 2024 MJO/trend/ENSO decomposition", "Builds developing-season background before adding MJO/OLR tests."],
    ],
    text: "The difference is not simply adding a dataset. It is turning weak response into a time-by-variable question: which season, which variable, and which external-basin background changed first?",
    src: "Literature notes: docs/literature_method_notes.md; source IDs L2-L8.",
  },
  {
    k: "Working Topic",
    t: "Proposed topic: developing-season coupling failure during the 2023/24 strong El Niño and external-basin modulation",
    layout: "text",
    claim: "Working hypothesis: spring-summer external-basin warmth and tropical-mean warming altered the Walker circulation and convective threshold, delaying or weakening the canonical wind-pressure-rainfall response to warm Pacific SST.",
    points: [
      "H1: Tropical North Atlantic, Indian Ocean, and Maritime Continent warmth suppressed the central-Pacific westerly response.",
      "H2: Maritime Continent / Indian Ocean convection maintained western-side convection and weakened the eastward rainfall shift.",
      "H3: Tropical-mean warming raised the convective threshold, so the same Pacific SST anomaly produced weaker atmospheric feedback."
    ],
    src: "Current diagnostics establish association; mechanism attribution requires ERA5, OLR, MJO/RMM and AGCM tests.",
  },
  {
    k: "Next Data",
    t: "Data needed for the next research version",
    layout: "tableText",
    rows: [
      ["Dataset", "Use", "Why needed"],
      ["ERA5 u850 / SLP / χ200", "Low-level wind, sea-level pressure, and Walker circulation.", "Manuscript-grade wind-pressure-circulation evidence."],
      ["NOAA OLR", "Independent deep-convection diagnosis.", "Avoid relying only on rainfall to infer convection."],
      ["ERSSTv5", "Long-record robustness since 1854.", "Check whether the post-1981 OISST sample affects historical comparison."],
      ["MJO/RMM or daily data", "Key-month decomposition, especially January 2024.", "Separate ENSO background, MJO, and trend effects."],
    ],
    text: "The near-term priority is ERA5 plus OLR. These will strengthen wind, pressure, Walker-circulation, and convection evidence before AGCM experiments.",
    src: "Data priorities from reports/当前数据分析阶段总结.md.",
  },
  {
    k: "Appendix A",
    t: "Slide-to-data table",
    layout: "appendix",
    rows: [
      ["Slides", "Figure / content", "Data table"],
      ["5-6", "Reproduced Fig. 1 and coupling ratios", "fig1_event_coupling.csv"],
      ["7", "Reproduced Fig. 2 ocean dynamics", "fig2_equatorial_summary.csv"],
      ["8-9", "Reproduced Fig. 3-4 AGCM/wind-stress experiments", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["11", "Raw-product validation", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["12", "Seasonal coupling-efficiency matrix", "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"],
      ["13-14", "AMJ/JJA spatial maps", "stage_a_spatial_summary.csv"],
      ["15-16", "External basins and historical comparison", "external_basin_seasonal_summary.csv; gpcp_precip_seasonal_summary.csv"],
    ],
    src: "All local paths are under /Users/daiyue/Documents/Maryland/data/derived.",
  },
  {
    k: "Appendix B",
    t: "Data and literature links",
    layout: "appendix",
    rows: [
      ["Source", "Link", "Use"],
      ["Peng et al. 2025", "nature.com/articles/s41561-025-01700-9", "Paper reproduction and question source"],
      ["NOAA OISST", "ncei.noaa.gov/products/optimum-interpolation-sst", "Sea-surface temperature"],
      ["GPCP", "psl.noaa.gov/data/gridded/data.gpcp.html", "Precipitation"],
      ["NCEP/NCAR R1", "psl.noaa.gov/data/reanalysis/", "Wind-pressure fallback"],
      ["ERA5", "cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels", "Next wind/Walker diagnostics"],
      ["NOAA OLR", "psl.noaa.gov/data/gridded/data.interp_OLR.html", "Next convection check"],
      ["ERSSTv5", "ncei.noaa.gov/products/extended-reconstructed-sst", "Long-record robustness"],
    ],
    src: "Full source log: docs/data_source_log.md.",
  },
];

const shared = `
const C = { bg:"#f7f3ea", ink:"#1d1b18", muted:"#5d574f", rule:"#d8d1c4", red:"#cc5a43", teal:"#2f6f73", blue:"#4a5f99", pale:"#fffaf1", rose:"#f5e5df", green:"#edf3ef" };
function bg(slide, ctx){ ctx.addShape(slide,{x:0,y:0,w:1280,h:720,fill:C.bg}); }
function text(slide, ctx, value, x,y,w,h,o={}){ return ctx.addText(slide,{text:value||"",x,y,w,h,fontSize:o.size||20,bold:o.bold||false,color:o.color||C.ink,typeface:o.title?ctx.fonts.title:ctx.fonts.body,valign:o.valign||"top",align:o.align||"left",insets:o.insets||{left:0,right:0,top:0,bottom:0}}); }
function header(slide,ctx,d){ text(slide,ctx,d.k,58,30,360,25,{size:14,bold:true,color:C.red}); text(slide,ctx,d.t,58,64,1100,82,{size:29,bold:true,title:true}); ctx.addShape(slide,{x:58,y:148,w:1130,h:1.5,fill:C.rule}); }
function src(slide,ctx,v){ text(slide,ctx,v||"",58,680,1120,26,{size:10.5,color:C.muted}); }
async function image(slide,ctx,p,x,y,w,h,fit="contain"){ await ctx.addImage(slide,{path:p,x,y,w,h,fit}); }
function bullets(slide,ctx,arr,x,y,w,row=58,size=17){ let yy=y; for(const b of arr||[]){ ctx.addShape(slide,{x,y:yy+9,w:7,h:7,fill:C.red,geometry:"ellipse"}); text(slide,ctx,b,x+20,yy,w-20,row-4,{size}); yy+=row; } }
function box(slide,ctx,title,body,x,y,w,h,fill){ ctx.addShape(slide,{x,y,w,h,fill,line:{style:"solid",fill:C.rule,width:0.8}}); text(slide,ctx,title,x+14,y+12,w-28,22,{size:14,bold:true,color:C.teal}); text(slide,ctx,body,x+14,y+42,w-28,h-50,{size:14.5,color:C.ink}); }
function table(slide,ctx,rows,x,y,w,rowH,opt={}){ const cols=rows[0].length; const widths=opt.widths||Array(cols).fill(w/cols); rows.forEach((r,i)=>{ let xx=x; r.forEach((cell,j)=>{ const cw=widths[j]; ctx.addShape(slide,{x:xx,y:y+i*rowH,w:cw,h:rowH,fill:i===0?C.ink:(i%2?C.pale:"#f2ecdf"),line:{style:"solid",fill:C.rule,width:0.7}}); text(slide,ctx,cell,xx+9,y+i*rowH+7,cw-18,rowH-10,{size:i===0?(opt.head||12):(opt.size||13.5),bold:i===0,color:i===0?"#fff":C.ink}); xx+=cw; }); }); }
async function renderDeckSlide(presentation,ctx,d){
 const slide=presentation.slides.add(); bg(slide,ctx);
 if(d.layout==="cover"){ text(slide,ctx,d.k,58,48,300,24,{size:14,bold:true,color:C.red}); text(slide,ctx,d.t,58,96,900,180,{size:38,bold:true,title:true}); text(slide,ctx,d.sub,60,304,960,58,{size:20,color:C.muted}); bullets(slide,ctx,d.bullets,68,410,900,56,17.5); ctx.addShape(slide,{x:1032,y:126,w:128,h:128,fill:C.red,geometry:"ellipse"}); ctx.addShape(slide,{x:1078,y:300,w:82,h:82,fill:C.teal,geometry:"ellipse"}); src(slide,ctx,d.src); return slide; }
 header(slide,ctx,d);
 if(d.layout==="text"){ ctx.addShape(slide,{x:76,y:178,w:1040,h:132,fill:C.rose,line:{style:"solid",fill:C.rule,width:1}}); text(slide,ctx,d.claim,98,202,996,92,{size:21,bold:true}); bullets(slide,ctx,d.points,92,350,980,70,18); }
 else if(d.layout==="glossary"){ table(slide,ctx,d.rows,70,174,1088,45,{widths:[145,315,628],size:12.4,head:12}); }
 else if(d.layout==="tableText"){ table(slide,ctx,d.rows,70,180,1088,d.rows.length>5?48:58,{widths:d.rows[0].length===3?[190,430,468]:[300,260,260],size:12.6,head:12}); box(slide,ctx,"Reading note",d.text,76,542,1040,106,C.green); }
 else if(d.layout==="figureExplain"){ await image(slide,ctx,d.image,60,182,600,366); const y=[168,302,436]; d.boxes.forEach((b,i)=>box(slide,ctx,b[0],b[1],694,y[i],452,118,i%2?C.green:C.rose)); }
 else if(d.layout==="twoFigureExplain"){ await image(slide,ctx,d.left,60,184,350,280); await image(slide,ctx,d.right,430,184,350,280); const y=[170,312,454]; d.boxes.forEach((b,i)=>box(slide,ctx,b[0],b[1],814,y[i],382,126,i%2?C.green:C.rose)); }
 else if(d.layout==="appendix"){ table(slide,ctx,d.rows,70,176,1088,48,{widths:d.rows[0].length===3?[170,390,528]:[255,570,263],size:12,head:12}); }
 src(slide,ctx,d.src); return slide;
}
export { renderDeckSlide };
`;

async function writeDeck(lang, slides) {
  const dir = path.join(DETAIL, lang === "cn" ? "slides_cn" : "slides_en");
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(path.join(DETAIL, `deck_shared_${lang}.mjs`), shared, "utf8");
  for (let i = 0; i < slides.length; i++) {
    const n = String(i + 1).padStart(2, "0");
    const body = `import { renderDeckSlide } from "../deck_shared_${lang}.mjs";\nconst data = ${JSON.stringify(slides[i], null, 2)};\nexport async function slide${n}(presentation, ctx) { return renderDeckSlide(presentation, ctx, data); }\n`;
    await fs.writeFile(path.join(dir, `slide-${n}.mjs`), body, "utf8");
  }
}

await fs.mkdir(DETAIL, { recursive: true });
await fs.writeFile(path.join(DETAIL, "package.json"), `${JSON.stringify({ private: true, type: "module" }, null, 2)}\n`, "utf8");
await fs.writeFile(path.join(DETAIL, "source-notes.txt"), "Detailed reading version. Every figure slide states data name, interpretation, link to original paper, and innovation.\n", "utf8");

function addExtraGlossary() {
  cn.splice(3, 0, {
    k: "术语先说明 2",
    t: "数据集、模式实验和区域缩写",
    layout: "glossary",
    rows: [
      ["缩写", "全称", "本研究中的意思"],
      ["NOAA", "美国国家海洋和大气管理局", "OISST、OLR 等资料的重要发布机构。"],
      ["NCEP/NCAR R1", "NCEP/NCAR 第一代再分析", "当前低层风和海平面气压的 fallback 验证资料。"],
      ["ERA5", "ECMWF 第五代再分析", "single-level u10 和 SLP 已进入主诊断；pressure-level Walker 环流仍待补。"],
      ["ERSSTv5", "扩展重建海表温度第 5 版", "用于长记录历史强厄尔尼诺稳健性检查。"],
      ["AGCM", "大气环流模式", "用规定海表温度作为边界条件，检验大气响应来源。"],
      ["ENSO", "厄尔尼诺-南方涛动", "El Niño 和 La Niña 所属的热带太平洋海气耦合系统。"],
      ["CWP", "中西太平洋", "本研究中低层风响应的关键区域。"],
      ["MJO/RMM", "Madden-Julian Oscillation / Real-time Multivariate MJO index", "用于后续区分季节内振荡对关键月份的影响。"],
      ["CTRL", "Control experiment，控制实验", "模式实验中的基准组，用于和敏感性实验比较。"],
    ],
    src: "Acronyms checked against all detailed slide text.",
  });
  en.splice(3, 0, {
    k: "Terms First 2",
    t: "Dataset, model-experiment, and region abbreviations",
    layout: "glossary",
    rows: [
      ["Abbrev.", "Full name", "Meaning in this project"],
      ["NOAA", "National Oceanic and Atmospheric Administration", "Main provider for OISST and OLR products."],
      ["NCEP/NCAR R1", "NCEP/NCAR Reanalysis 1", "Current fallback dataset for low-level wind and sea-level pressure."],
      ["ERA5", "ECMWF Reanalysis version 5", "Next manuscript-grade dataset for u850, SLP, and Walker circulation."],
      ["ERSSTv5", "Extended Reconstructed Sea Surface Temperature version 5", "Long-record SST check for historical robustness."],
      ["AGCM", "Atmospheric General Circulation Model", "Atmospheric model forced by prescribed SST boundary conditions."],
      ["ENSO", "El Niño-Southern Oscillation", "The coupled tropical Pacific system containing El Niño and La Niña."],
      ["CWP", "Central-western Pacific", "Key region for low-level wind response in this study."],
      ["MJO/RMM", "Madden-Julian Oscillation / Real-time Multivariate MJO index", "Used later to separate intraseasonal variability from ENSO background."],
      ["CTRL", "Control experiment", "Baseline model experiment for comparison with sensitivity experiments."],
    ],
    src: "Acronyms checked against all detailed slide text.",
  });

  const cnApp = cn.find((s) => s.k === "附录 A");
  if (cnApp) {
    cnApp.rows = [
      ["页码", "图/内容", "数据表"],
      ["6-7", "原文 Fig. 1 与耦合响应比", "fig1_event_coupling.csv"],
      ["8", "原文 Fig. 2 海洋动力诊断", "fig2_equatorial_summary.csv"],
      ["9-10", "原文 Fig. 3-4 AGCM/风应力实验", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["12", "公开资料验证", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["13", "分季节回归预期响应矩阵", "seasonal_regression_expected_response.csv; external_basin_seasonal_summary.csv"],
      ["14-15", "AMJ/JJA 空间图", "stage_a_spatial_summary.csv"],
      ["16-17", "外海盆和历史对比", "external_basin_seasonal_summary.csv; gpcp_precip_seasonal_summary.csv"],
    ];
  }
  const enApp = en.find((s) => s.k === "Appendix A");
  if (enApp) {
    enApp.rows = [
      ["Slides", "Figure / content", "Data table"],
      ["6-7", "Reproduced Fig. 1 and coupling ratios", "fig1_event_coupling.csv"],
      ["8", "Reproduced Fig. 2 ocean dynamics", "fig2_equatorial_summary.csv"],
      ["9-10", "Reproduced Fig. 3-4 AGCM/wind-stress experiments", "fig3_agcm_summary.csv; fig4_wind_experiment_summary.csv"],
      ["12", "Raw-product validation", "oisst_vs_fig1_nino3.csv; gpcp_vs_fig2_precip.csv; ncep_vs_fig1_atmosphere.csv"],
      ["13", "Seasonal coupling-efficiency matrix", "asynchronous_coupling_efficiency.csv; seasonal_asynchrony_matrix.csv"],
      ["14-15", "AMJ/JJA spatial maps", "stage_a_spatial_summary.csv"],
      ["16-17", "External basins and historical comparison", "external_basin_seasonal_summary.csv; gpcp_precip_seasonal_summary.csv"],
    ];
  }
}

addExtraGlossary();
await writeDeck("cn", cn);
await writeDeck("en", en);
console.log(JSON.stringify({ workspace: DETAIL, slides: { cn: cn.length, en: en.length } }, null, 2));
