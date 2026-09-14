import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const ROOT = "/Users/daiyue/Documents/Maryland";
const TMP = path.join(ROOT, "outputs/research_2026/ppt/.tmp_per_figure_formulas_20260811");
const SOURCE = path.join(TMP, "template-starter.pptx");
const OUTPUT = path.join(
  ROOT,
  "outputs/research_2026/ppt/厄尔尼诺异常暖量到达分配与耦合命运_逐图公式版_20260811.pptx",
);
const PREVIEW = path.join(TMP, "final-preview");
const LAYOUT = path.join(TMP, "final-layout");

const NAMES = {
  eyebrow: "chakravorty-formula-data-text-22",
  title: "chakravorty-formula-data-text-23",
  subtitle: "chakravorty-formula-data-text-25",
  card1Title: "chakravorty-formula-data-text-27",
  formula1Base: "chakravorty-formula-data-text-28",
  formula1Sub: "chakravorty-formula-data-text-29",
  formula1Rest: "chakravorty-formula-data-text-30",
  formula2Base: "chakravorty-formula-data-text-31",
  formula2Sub: "chakravorty-formula-data-text-32",
  formula2Rest: "chakravorty-formula-data-text-33",
  card1Body: "chakravorty-formula-data-text-34",
  card2Title: "chakravorty-formula-data-text-36",
  card2Body: "chakravorty-formula-data-text-37",
  card3Title: "chakravorty-formula-data-text-39",
  card3Body: "chakravorty-formula-data-text-40",
  strip: "chakravorty-formula-data-text-42",
  takeaway: "chakravorty-formula-data-text-44",
};

const FORMULA_SLIDES = [3, 5, 7, 16, 18, 20, 24, 28, 30, 32, 34];

const SPECS = [
  {
    eyebrow: "逐图计算｜文献一",
    title: "Original Figure 8：CT/CP事件与充放电量如何计算",
    subtitle: "作者原方法｜SODA2.x + HadISST + wind products｜8 CT + 8 CP",
    card1Title: "事件分类",
    formula1: { base: "N", sub: "CT", rest: "= N₃ − αN₄" },
    formula2: { base: "N", sub: "CP", rest: "= N₄ − αN₃" },
    card1Body: "α = 2/5，当 N₃·N₄ > 0；否则 α = 0\nN₃/N₄：区域SST′指数\nCHI：SST′的经向一阶矩\n指数与CHI > 0.8°C，连续≥5月",
    card2Title: "三行诊断量",
    card2Body: "WWV(t) = ∬ h′(x,y,t)dA\n\nZT₁₇₀E(t) = ∬u dzdy\nMTᵩ(t) = ∬v dzdλ\n\n异常均先去季节循环、去趋势并作3月滑动平均",
    card3Title: "下一页分面对应",
    card3Body: "上：WWV异常，表示充电/放电\n中：170°E纬向输送\n下：5°N与10°S经向输送\n\nCT/CP分别做事件合成；阴影/标记由双侧t检验给出",
    strip: "边界：170°E、5°N、10°S｜符号遵循论文的入流/出流约定",
    takeaway: "下一页的三组曲线不是同一指标：储热、纬向输入和经向释放需联合解释。",
    sources: [
      "https://doi.org/10.1029/2020JC017075 (Chakravorty et al., 2021; Equations 1-2, Sections 2.1-2.3 and Figure 8)",
      "Local PDF: /Users/daiyue/Documents/Maryland/tmp/pdfs/chakravorty_2021_recharge_discharge_enso_flavors.pdf, pages 3-4 and 12.",
    ],
  },
  {
    eyebrow: "逐图计算｜文献二",
    title: "Original Figure 3a：沿粒子轨迹累积各热收支项",
    subtitle: "作者原方法｜ECCO4三维速度与闭合温度预算｜同一水团的Lagrangian积分",
    card1Title: "轨迹与温度异常",
    formula1: { rest: "Θ′ₚ(t) = Θ′[xₚ(t),t]" },
    formula2: { rest: "ΔΘ′ₚ = ∫ₜ₀ᵗ₁ ΣRᵢ[xₚ(t),t]dt" },
    card1Body: "dxₚ/dt = U[xₚ(t),t]\n\np：粒子；Rᵢ：异常预算第i项\n沿同一轨迹取样后积分，终点温度变化应与各项之和闭合",
    card2Title: "异常温度方程",
    card2Body: "∂Θ′/∂t + A(U,Θ′)\n= Dₕ′ + Dᵥ′ + Q′ + δ′ₙₐ\n+ ⟨A(U′,Θ′)⟩ − A(U′,⟨Θ⟩)\n\n依次代表扩散、外部加热、未归属平流、整流和异常平流",
    card3Title: "下一页分面对应",
    card3Body: "每种颜色 = 一个Rᵢ的沿轨迹累计贡献\n实线/集合 = 粒子统计\n终点总和 = 预测的ΔΘ′ₚ\n\nFigure 3a展示建立期各过程如何共同造成异常升温",
    strip: "⟨·⟩为1992–2017季节气候态｜积分先逐粒子计算，再汇总粒子集合",
    takeaway: "下一页的关键不是相关，而是同一水团、同一时间段上的逐项温度收支闭合。",
    sources: [
      "https://doi.org/10.21203/rs.3.rs-7762242/v1 (Wenrui Jiang et al., 2025 preprint; Equations 1-3 and Sections 4.2-4.4)",
      "Local PDF: /Users/daiyue/Documents/Maryland/outputs/research_2026/ppt/.tmp_three_papers_english_figures_20260811/mhw_preprint.pdf, pages 7-9 and 15.",
    ],
  },
  {
    eyebrow: "逐图计算｜文献三",
    title: "Original Figure 1b,f：先分离FEP残差，再计算MJJ异常场",
    subtitle: "作者原方法｜ERSSTv5 + ERA5 + ORAS5｜1960–2024月资料，全部去趋势",
    card1Title: "FEP与ENSO分离",
    formula1: { rest: "T(t) = E·Tₙ₃₄(t) + Tᵣ(t)" },
    formula2: { rest: "X = αTₙ₃₄ + βTᵣ + ε" },
    card1Body: "T：FEP SSTA；Tₙ₃₄：Niño3.4\nTᵣ：不能由典型ENSO解释的FEP残差\nX：SST / 风 / 降水 / 次表层变量\nβTᵣ给出FEP独立响应",
    card2Title: "季节与区域平均",
    card2Body: "X′ₘ = Xₘ − climatologyₘ − bₘ(t−t̄)\n\nX̄ᴹᴶᴶ = (X′ᴹᵃʸ + X′ᴶᵘⁿ + X′ᴶᵘˡ)/3\n\nNE wind：3°–7°N，180°E–130°W\nFEP：5°S–5°N，90°W–80°W",
    card3Title: "下一页分面对应",
    card3Body: "Figure 1b：经度—时间SSTA演变\nFigure 1f：MJJ风—雨—SST异常\n\n2023与历史事件使用同一异常定义；异常风由区域平均/回归场给出",
    strip: "Figure 1用于观测描述；残差分解为后续归因提供坐标，不把相关直接当作因果",
    takeaway: "下一页先显示东部先行增暖，再显示MJJ东北风增强与中太平洋西风偏弱。",
    sources: [
      "https://doi.org/10.1029/2026GL123227 (Leishan Jiang et al., 2026; Equations 1-2, Section 2 and Figure 1)",
      "Local PDF: /Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf, pages 2-5.",
    ],
  },
  {
    eyebrow: "逐图计算｜问题一",
    title: "传播图：把SODA3的0–300 m OHC转换为经度—时间异常",
    subtitle: "当前计算｜SODA3.15.2｜10°S–5°N｜130°E–80°W｜1980–2014同月基线",
    card1Title: "固定层OHC",
    formula1: { rest: "H₃₀₀ = ⟨ρ₀cₚ∫₀³⁰⁰ T dz⟩ᵩ" },
    formula2: { rest: "H′₃₀₀ = H₃₀₀ − Ĉₘ − bₘ(y−ȳₘ)" },
    card1Body: "先在每个格点垂向积分到300 m\n再按cosφ对10°S–5°N作纬向加权平均\n\nĈₘ、bₘ：基线期同一日历月的均值与线性趋势",
    card2Title: "纬向加权与异常",
    card2Body: "⟨H⟩ᵩ = ΣᵢHᵢcosφᵢ / Σᵢcosφᵢ\n\n每个经度、每个日历月分别拟合：\nH(t) = Ĉₘ + bₘ(y−ȳₘ) + H′(t)\n\n输出单位：GJ m⁻²",
    card3Title: "下一页三幅图",
    card3Body: "事件窗：前一年Jul至发展年Nov\n相对月：−6…+10\n面板：1997 / 2015 / 2023\n\n虚线：140°W；等值线：H′₃₀₀ = 0\n三幅图使用同一色标",
    strip: "数据直接读取SODA3的0–300 m OHC场；这里没有温度阈值和暖水体积定义",
    takeaway: "下一页每个色块都是“同月气候态与趋势之外”的固定层OHC异常。",
    sources: [
      "Local script: /Users/daiyue/Documents/Maryland/scripts/analyze_soda3_post_arrival_three_box_ohc.py (make_anomaly_hovmoller).",
      "Local dataset: /Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc300_anomaly_hovmoller_1997_2015_2023.csv.",
    ],
  },
  {
    eyebrow: "逐图计算｜问题一",
    title: "轨迹图：用正温度异常权重统计SODA3三维反向路径",
    subtitle: "当前计算｜SODA3.15.2五日u/v/w与温度｜东太平洋释放｜Jan–Jun反向追踪",
    card1Title: "释放异常与权重",
    formula1: { rest: "T′ₚ = Tₚ − T̂ₘ,−e" },
    formula2: { rest: "ωₚ = max(T′ₚ,0)cosφₚΔzₚ" },
    card1Body: "T̂ₘ,−e：同月线性预期，排除事件年e\n保留T′ₚ > 0.05°C的粒子\n释放区：140°W–100°W，5°S–5°N，15–160 m\nωₚ仅用于比例加权，不是焦耳",
    card2Title: "反向轨迹积分",
    card2Body: "dλ/dt = u/(Rcosφ)\ndφ/dt = v/R\ndz/dt = −w\n\n五日场间线性插值；midpoint RK2\n从6月末反向积分到1月初\n并检验无w与反号w敏感性",
    card3Title: "下一页两个柱图",
    card3Body: "Δλₚ = λrelease − λsource\n\n加权中位数：累计ωₚ首次达到0.5Σωₚ\n活动轨迹权重占比：Σactiveωₚ / Σωₚ\n\n分别对1997、2015、2023统计",
    strip: "轨迹回答“路径是否存在”；它不是守恒热预算，因此不把释放权重解释为能量",
    takeaway: "下一页左图是加权东移距离，右图是仍可解析的轨迹权重占比。",
    sources: [
      "Local script: /Users/daiyue/Documents/Maryland/scripts/pilot_soda3_lagrangian_connectivity.py.",
      "Local dataset: /Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_temp_anomaly_lagrangian_pilot_summary.csv.",
    ],
  },
  {
    eyebrow: "逐图计算｜问题一",
    title: "到达图：140°W边界输入与东箱OHC′增量独立计算",
    subtitle: "当前计算｜SODA3.15.2｜东箱140°W–80°W，10°S–5°N，0–300 m｜Jan–Jun",
    card1Title: "质量闭合边界输送",
    formula1: { rest: "Q₁₄₀W = ρ₀cₚ ∬uₙ(T−T̄ᵦ)dA" },
    formula2: { rest: "Aᴶᵃⁿ–ᴶᵘⁿ = ∫Q′₁₄₀W(t)dt" },
    card1Body: "四边界先作统一法向速度校正：\nδu = ΣᵢVᵢ / ΣᵢAᵢ\nV*ᵢ = Vᵢ − δuAᵢ\n\n校正后的净体积输送为0；西边界正值表示进入东箱",
    card2Title: "东箱储热增量",
    card2Body: "H′ₑ(t) = ρ₀cₚ∭ₑT′dV\n\nΔH′ₑ = H′ₑ(Jun) − H′ₑ(Jan)\n\nT′与Q′均按1980–2022同月气候态和线性趋势去除；单位由PW积分为ZJ",
    card3Title: "下一页两组柱",
    card3Body: "橙色：Aᴶᵃⁿ–ᴶᵘⁿ，140°W累计输入\n蓝色：ΔH′ₑ，东箱固定层储热增加\n\n同一顺序：1997 / 2015 / 2023\n两者接近表示边界输入主要进入东箱储热",
    strip: "时间积分采用月样本梯形积分：E = ∫Qdt；1 PW·s = 10⁻⁶ ZJ",
    takeaway: "下一页用“跨边界输入 + 箱内储热”两套量同时确认到达，而不是只看SST。",
    sources: [
      "Local scripts: /Users/daiyue/Documents/Maryland/scripts/fetch_soda3_three_box_enthalpy_boundary_terms.py and analyze_soda3_three_box_ohc_anomaly_budget.py.",
      "Local dataset: /Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv.",
    ],
  },
  {
    eyebrow: "逐图计算｜问题二",
    title: "去向图：用固定层OHC′预算把following Jan–May逐项闭合",
    subtitle: "当前计算｜SODA3.15.2｜东箱140°W–80°W，10°S–5°N，0–300 m｜13事件",
    card1Title: "异常能量预算",
    formula1: { rest: "ΔH′ₑ = C′ₑ + Q′ₛ + R′" },
    formula2: { rest: "C′ₑ = Q′W + Q′E + Q′N + Q′S" },
    card1Body: "ΔH′ₑ：东箱OHC′变化\nC′ₑ：四边界质量闭合总焓收敛\nQ′ₛ：向海洋为正的净海表热通量\nR′ = ΔH′ₑ − C′ₑ − Q′ₛ\n所有项使用同一Jan–May积分窗",
    card2Title: "绘图符号转换",
    card2Body: "储热损失 = −ΔH′ₑ\n向西返回 = −Q′W\n向北输出 = −Q′N\n向南输出 = −Q′S\n海表散热 = −Q′ₛ\n\n正值统一表示离开东箱；R′保持预算原符号单列",
    card3Title: "下一页三个事件",
    card3Body: "每个面板：1997 / 2015 / 2023\n每根柱：following Jan–May累计ZJ\n\n四边界输送先做体积闭合；总焓收敛不依赖温标零点\n残差不命名为某个物理通道",
    strip: "逐月异常先积分为ZJ，再按统一输出符号绘图；收支恒等式在事件尺度重新核验",
    takeaway: "下一页所有去向都来自同一个东箱预算；正柱表示输出，残差保持独立。",
    sources: [
      "Local script: /Users/daiyue/Documents/Maryland/scripts/analyze_soda3_three_box_ohc_anomaly_budget.py.",
      "Local dataset: /Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_three_box_ohc_anomaly_budget_events.csv.",
    ],
  },
  {
    eyebrow: "逐图计算｜问题三",
    title: "先行线索图：检验JFM北向热量分流是否领先MJJ东北风",
    subtitle: "当前计算｜13个暖事件｜固定JFM 140°W到达量｜Jiang区域MJJ东北风",
    card1Title: "控制到达量的偏相关",
    formula1: { rest: "Xᵣ = X − (aₓ + bₓA)" },
    formula2: { rest: "rₓᵧ·A = corr(Xᵣ,Yᵣ)" },
    card1Body: "X：JFM北向输出；Y：MJJ NE925\nA：JFM 140°W到达量\nXᵣ、Yᵣ分别对A做OLS残差化\n\np：20,000次事件置换双侧检验\n95% CI：10,000次事件bootstrap",
    card2Title: "海洋与风指数",
    card2Body: "Nᴶᶠᴹ = −∫ᴶᶠᴹQ′N(t)dt\nAᴶᶠᴹ = ∫ᴶᶠᴹQ′₁₄₀W(t)dt\n\nNE925ᴹᴶᴶ：Jiang区域5–7月平均东北风指标\n\n二者时间窗严格分开：JFM在前，MJJ在后",
    card3Title: "下一页两个分面",
    card3Body: "(a) Xᵣ–Yᵣ散点 + OLS拟合线\n突出1997 / 2015 / 2023\n\n(b) 三事件标准化对照：\nz = (x−x̄)/s\nJFM北向输出、JFM NE850、MJJ NE850并列",
    strip: "事件集合：1982、1986、1991、1994、1997、2002、2004、2006、2009、2015、2018、2019、2023",
    takeaway: "下一页检验的是“先海洋、后大气”，并用到达量残差化排除输入规模差异。",
    sources: [
      "Local script: /Users/daiyue/Documents/Maryland/scripts/analyze_nonh20_early_north_to_jiang_ne.py.",
      "Local datasets: nonh20_early_north_to_jiang_event_table.csv and relationships.csv.",
      "https://doi.org/10.1029/2026GL123227 (Jiang et al., 2026; MJJ northeasterly region and timing).",
    ],
  },
  {
    eyebrow: "逐图计算｜问题三",
    title: "动力门控图：用三组残差关系连接东北风、应力与北向输出",
    subtitle: "当前计算｜13个暖事件｜发展年MJJ → following Jan–May｜Pearson r + permutation/FDR",
    card1Title: "残差、拟合与相关",
    formula1: { rest: "Xᵣ = X − C(CᵀC)⁻¹CᵀX" },
    formula2: { rest: "ŷ = a + bx； r = corr(Xᵣ,Yᵣ)" },
    card1Body: "C含截距与指定控制量\n若不控制到达量，仅减去事件均值\n散点拟合线由OLS给出\n\np：20,000次事件置换\nq：同一检验族内Benjamini–Hochberg FDR",
    card2Title: "下一页(a)–(c)",
    card2Body: "(a) NE850ᴹᴶᴶ → 中央纬向应力ᴹᴶᴶ\n两轴均固定JFM到达量\n\n(b) 中央U850ᴹᴶᴶ → 次年5°N西向应力\n仅去事件均值\n\n(c) 5°N应力 → 晚期北向输出\n两轴均固定Jan–Jun到达量",
    card3Title: "显著性与FDR",
    card3Body: "p = [1 + ΣI(|rπ|≥|r|)]/(B+1)\nB = 20,000\n\n排序后：q(i) = minⱼ≥ᵢ[m·p(j)/j]\n\nbootstrap 95% CI与leave-one-event-out符号稳定性另行核验",
    strip: "应力定义为向西为正；北向输出定义为离开东箱为正｜所有单位在残差化前保留",
    takeaway: "下一页三幅散点图分别计算，只有(a)和(c)固定到达量；不能把三组r直接相乘。",
    sources: [
      "Local scripts: /Users/daiyue/Documents/Maryland/scripts/analyze_nonh20_third_question_chain.py and plot_nonh20_ppt_figures.py.",
      "Local datasets: nonh20_third_question_event_table.csv, relationships.csv, and nonh20_early_north_to_jiang_event_table.csv.",
    ],
  },
  {
    eyebrow: "逐图计算｜问题三",
    title: "热力与调整图：在固定到达量后分别检验散热与向西返回",
    subtitle: "当前计算｜13个暖事件｜following Jan–May｜两组偏相关采用相同残差化程序",
    card1Title: "固定到达量",
    formula1: { rest: "Xᵣ = X − (aₓ + bₓA)" },
    formula2: { rest: "rₓᵧ·A = corr(Xᵣ,Yᵣ)" },
    card1Body: "A：Jan–Jun 140°W累计到达量\nX、Y分别对A做OLS后取残差\n\n置换p：20,000次\nfamily-FDR q：在同一检验族内校正\n95% CI：20,000次bootstrap",
    card2Title: "下一页(a)：热力分支",
    card2Body: "X = 东箱SST′的following Jan–May平均\nY = −∫Q′ₛdt，海表散热量\n\nSST′按1980–2022同月气候态与趋势去除\n正的Y表示海洋向大气失热\n拟合线：Yᵣ = a + bXᵣ",
    card3Title: "下一页(b)：调整分支",
    card3Body: "X = following Jan–May 5°N西向应力异常\nY = −∫Q′Wdt，向西返回量\n\n二者同样固定到达量\n若置换p未过检验，则只报告相关方向，不宣称门控成立",
    strip: "两幅图的控制量、样本和统计程序相同；差别只在X/Y的物理定义",
    takeaway: "下一页(a)通过统计检验，(b)未通过；因此散热分支有约束，向西返回机制仍开放。",
    sources: [
      "Local scripts: /Users/daiyue/Documents/Maryland/scripts/analyze_nonh20_third_question_chain.py and plot_nonh20_ppt_figures.py.",
      "Local datasets: nonh20_third_question_event_table.csv and nonh20_third_question_relationships.csv.",
    ],
  },
  {
    eyebrow: "逐图计算｜问题三",
    title: "稳健性图：逐次留出一个事件，比较加入门控变量前后的误差",
    subtitle: "当前计算｜n = 13｜普通最小二乘｜每个事件只用其余12个事件拟合",
    card1Title: "LOEO预测",
    formula1: { rest: "ŷ₋ᵢ = β̂₀,−i + Σⱼβ̂ⱼ,−i xᵢⱼ" },
    formula2: { rest: "RMSEz = √[n⁻¹Σ(ŷ₋ᵢ−yᵢ)²]/sᵧ" },
    card1Body: "β̂−i = argminβ Σk≠i(yk−Xkβ)²\n\n对i = 1…13重复：\n训练12个事件 → 预测被留出的1个事件\nRMSE除以目标量样本标准差sᵧ\n越小越好",
    card2Title: "北向输出模型",
    card2Body: "基线：N = β₀ + β₁A\n门控：N = β₀ + β₁A + β₂τ₅N\n\nA：Jan–Jun到达量\nτ₅N：following Jan–May 5°N应力\n\n下一页比较两模型的RMSEz，并报告LOEO预测相关",
    card3Title: "海表散热模型",
    card3Body: "基线：L = β₀ + β₁A\n门控：L = β₀ + β₁A + β₂SSTₑ\n\nL：following Jan–May海表散热\nSSTₑ：同期东箱SST′\n\n所有预测均来自未见过该事件的模型",
    strip: "LOEO相关 = corr(ŷ₋ᵢ,yᵢ)｜柱图只画标准化RMSE，右侧文字同时给出相关变化",
    takeaway: "下一页误差下降说明门控变量含有到达量之外的信息，但仍属于样本外统计约束。",
    sources: [
      "Local script: /Users/daiyue/Documents/Maryland/scripts/analyze_nonh20_third_question_chain.py (linear_fit_predict and build_models).",
      "Local datasets: nonh20_third_question_loeo_models.csv and nonh20_third_question_loeo_predictions.csv.",
    ],
  },
];

function shapeByName(slide, shapeName) {
  const found = slide.shapes.items.find((shape) => shape.name === shapeName);
  if (!found) throw new Error(`Missing shape ${shapeName}`);
  return found;
}

function setText(slide, key, value) {
  const shape = shapeByName(slide, NAMES[key]);
  shape.text = value ?? "";
}

function applyFormula(slide, spec) {
  setText(slide, "eyebrow", spec.eyebrow);
  setText(slide, "title", spec.title);
  setText(slide, "subtitle", spec.subtitle);
  setText(slide, "card1Title", spec.card1Title);
  setText(slide, "formula1Base", spec.formula1?.base ?? "");
  setText(slide, "formula1Sub", spec.formula1?.sub ?? "");
  setText(slide, "formula1Rest", spec.formula1?.rest ?? "");
  setText(slide, "formula2Base", spec.formula2?.base ?? "");
  setText(slide, "formula2Sub", spec.formula2?.sub ?? "");
  setText(slide, "formula2Rest", spec.formula2?.rest ?? "");
  setText(slide, "card1Body", spec.card1Body);
  setText(slide, "card2Title", spec.card2Title);
  setText(slide, "card2Body", spec.card2Body);
  setText(slide, "card3Title", spec.card3Title);
  setText(slide, "card3Body", spec.card3Body);
  setText(slide, "strip", spec.strip);
  setText(slide, "takeaway", spec.takeaway);
  slide.speakerNotes.clear();
  slide.speakerNotes.text = `[Sources]\n${spec.sources.map((source) => `- ${source}`).join("\n")}\n[/Sources]`;
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(PREVIEW, { recursive: true });
  await fs.mkdir(LAYOUT, { recursive: true });
  const presentation = await PresentationFile.importPptx(await FileBlob.load(SOURCE));
  if (presentation.slides.items.length !== 36) {
    throw new Error(`Expected 36 starter slides, found ${presentation.slides.items.length}`);
  }
  FORMULA_SLIDES.forEach((number, index) => {
    applyFormula(presentation.slides.items[number - 1], SPECS[index]);
  });

  for (let index = 0; index < presentation.slides.items.length; index += 1) {
    const slide = presentation.slides.items[index];
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(PREVIEW, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(LAYOUT, `${stem}.layout.json`), await layout.text(), "utf8");
  }
  await writeBlob(path.join(TMP, "final-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));
  const inspect = await presentation.inspect({
    kind: "slide,textbox,shape,image,notes,layout",
    include: "id,slide,name,title,text,textPreview,bbox,isPlaceholder",
    maxChars: 800000,
  });
  await fs.writeFile(path.join(TMP, "final-inspect.ndjson"), inspect.ndjson, "utf8");
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(OUTPUT);
  console.log(JSON.stringify({ output: OUTPUT, slides: presentation.slides.items.length, formulaSlides: FORMULA_SLIDES }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
