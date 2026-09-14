# SODA3 热含量—再分配—东部放大分析

## 这一步回答什么

单看 FEP 海温异常，只能看到东端已经暖了多少；SODA3 可以把问题拆成：

1. **蓄积**：整个热带太平洋 20°C 以上暖水体积（WWV）有多少；
2. **再分配**：暖水体积重心和日界线以东的占比是否向东移动；
3. **东部放大/抑制**：水平输送、上升流相关垂直平流、表面净加热分别是否有利于东部增暖；
4. **记忆与屏障**：SSH 东西差、次表层东向流、混合层/障碍层是否帮助暖水保持并传播；
5. **预测检验**：这些量能否在只使用此前年份训练的条件下，优于当月 Niño-3−Niño-4 类型持续性。

## 统一计算口径

- 数据：SODA3.15.2，1980–2024 年 1–6 月，5°S–5°N、120°E–80°W、上层 300 m。
- 气候态：全部量统一使用 **1980–2024 同月气候态并去除同月线性趋势**。
- 成熟类型目标：下一成熟 DJF 的 OISST Niño-3−Niño-4；正值为相对 EP-like，负值为相对 CP-like。
- 事件证据：NOAA ONI 定义的 13 个暖事件，使用 5–6 月平均过程异常。
- 预测证据：2000–2023 逐年向前检验；每一折只用目标年以前资料估计趋势、标准差和回归。
- 条件预测：对 13 个暖事件逐一留出，使用另外 12 个暖事件训练固定
  α=1 的岭回归；趋势和标准差也只在每一折训练集内估计。
- 水平平流代理：`−(u∂T/∂x + v∂T/∂y)`；垂直平流代理：
  `w∂T/∂z`（SODA `wt` 向上为正、深度向下为正）；表面受热代理：
  `Qnet/(ρCp·max(MLD,5 m))`。

## 目前结果

- 13 事件中绝对相关最高的候选量是 **Warm-volume centroid**：
  r=+0.77，
  双侧置换 p=0.006，
  BH-FDR q=0.024。
- 通过 BH-FDR 0.05 的事件关系为：Warm-volume centroid (r=+0.77, q=0.024)、East WWV fraction (r=+0.75, q=0.027)、Vertical advection (r=+0.73, q=0.024)、Barrier-layer thickness (r=+0.75, q=0.024)、SSH east minus west (r=+0.66, q=0.036)。
- 逐年预测的表面最佳组合是 **Jun 的 + SSH gradient**：
  相对类型持续性的 RMSE skill=
  +0.03，95% bootstrap 区间
  [-0.25, +0.26]，
  q=0.993。
- 所有新增模型在 72 个模型×月份检验的 BH-FDR 校正后均未达到 q<0.05；当前不能声称它们稳定提高了类型预测。
- 暖事件条件下的最佳候选是 **May 的 + east WWV fraction**（skill=+0.48，单项 p=0.010），但在 72 个模型×月份检验校正后 q=0.160，因此是值得扩大样本验证的候选信号，而不是已确认技巧。

## 怎样理解“转变点”

最合理的工作定义不是一个固定 FEP 阈值，而是一个**连续门槛**：
西部已有暖水储备之后，暖水体积重心、日界线以东 WWV 占比和 SSH 东西差首先显示
**热量是否真的完成向东再分配**；随后，东部垂直平流异常和障碍层显示
**上升流冷却是否减弱、表层暖异常能否被保留**。这两组信号同时成立时，
FEP 暖异常才更可能发展成 EP 型。

本次结果并不支持把表面净热通量或月平均水平平流当成主要“开关”：
表面受热与 EP 程度为负相关（r=-0.53，
q=0.090），
更像对海洋增暖的阻尼；水平平流的事件相关很弱
（r=+0.15）。
因此当前数据支持的“转变点”更接近**暖水东移 + 垂直冷却减弱/屏障增强**，
而不是“FEP 到达某个固定温度”。

三次代表事件也符合这一分层：1997 年 5–6 月暖水重心东移
+6.63°、东侧 WWV 占比异常
+0.065、SSH 东西差异常
+0.149 m；2023 年对应值只有
+2.97°、
+0.022 和
+0.051 m。2023 虽然最终仍为 EP-like，
但早夏的海洋再分配明显弱于 1997，解释了它不是同等级的强东部发展。

## 必须保留的限制

- `-u·∇T`、`w∂T/∂z` 和 `Qnet/(ρCp h)` 用的是月平均场，是**过程代理量**；
  月平均乘积不等于瞬变协方差，且没有显式闭合混合、卷入、扩散和资料同化增量。
- SODA3.15.2 由 ERA5 强迫，所以海洋量与 ERA5 风/通量不是独立资料验证。
- 事件只有 13 个，多重检验校正后的结果优先于单个最好看的相关系数。
- 预测增益必须看逐年外推，而不能用全时段回归拟合优度代替。

## 数据与方法出处

- SODA 官方说明：<https://www.soda.umd.edu/>（SODA3.15.2、ERA5 强迫、
  1980–2024；并给出 Carton, Chepurin & Chen 2018 的正式引用）。
- APDRC 变量说明：<https://apdrc.soest.hawaii.edu/datadoc/soda_3.15.2.php>
  （`temp/wt/ssh/mlt/mlp/net_heating/u/v/taux` 的定义与单位）。
- 建议引用：Carton, J. A., G. A. Chepurin, and L. Chen (2018),
  *SODA3: A New Ocean Climate Reanalysis*, Journal of Climate, 31,
  6967–6983, doi:10.1175/JCLI-D-18-0149.1。

## 输出

- 过程指标：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_transition_process_indices_1980_2024.csv`
- 事件表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_process_event_summary_1982_2023.csv`
- 事件相关：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_process_event_correlations.csv`
- 逐年预测：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_process_walkforward_predictions_2000_2023.csv`
- 预测技巧：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_process_walkforward_skill_2000_2023.csv`
- 暖事件留一预测：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_process_event_loeo_predictions.csv`
- 暖事件留一技巧：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_process_event_loeo_skill.csv`
- 三事件过程图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_process_diagnostics_1997_2015_2023.pdf`
- 全事件与预测检验图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_process_full_event_evidence.pdf`
