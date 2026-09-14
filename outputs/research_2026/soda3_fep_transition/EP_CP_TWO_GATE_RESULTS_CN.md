# EP/CP 类型“两道门”全事件检验

## 结论先行

- 1982–2023 年共识别出 **13 次** NOAA ONI 暖事件。成熟型态以随后 DJF 的 OISST `Niño3−Niño4` 为连续指标；`>0` 表示更偏东，`<0` 表示更偏中部。
- 全年份逐年回报检验中，最佳非持续性模型是 **May 的 + FEP residual**，相对类型持续性的 RMSE skill 为 **+0.072**，95% bootstrap 区间 [+0.001, +0.170]。
- 暖事件留一法中，最佳结果是 **Jan 的 Atmosphere gate**，RMSE skill **+0.286**，符号命中率 **69%**。
- 严格不确定性检查：对所有“月份 × 模型”检验进行 BH-FDR 校正后，没有任何改进达到 q<0.05。因此，May FEP 的正技巧只能表述为“候选预测信号”，不能表述为已经建立稳定预测能力。
- “两道门越早完整打开，成熟期越偏东”的事件相关为 **r=+0.13**，置换检验 p=0.688。未通过门的事件按 7（月）编码，仅用于排序检验。
- 相比“过零时间”，异常**强度**更有信息。五个事件强度指标经 BH-FDR 校正后 q<0.05 的有：**D20 E-W May-Jun、u850 May-Jun**。
- `Niño3−Niño4` 的正负号与可核验的文献分类 **7/7 一致**；但接近 0 的事件仍保留为 mixed/borderline。

## 这是否形成研究闭环

- 机制链条可以形成一个**待检验的闭环假说**：FEP 异常是触发背景，而不是充分条件；热量向东重分配的强度（OHC/D20）和大气持续响应的强度（西风/对流）共同影响暖异常能否发展成偏东型。
- 但统计证据仍是探索性的：只有 13 个暖事件，且 OHC 与 D20、风与 OLR 均存在共线性。真正可投稿的下一步应增加不同资料集敏感性、模式试验或更长重建，并预先固定阈值。

## 解释边界

- `Niño3−Niño4` 是连续的“偏东/偏中部”度量，不等同于唯一公认的 EP/CP 离散定义。
- `|Niño3−Niño4|<0.2°C` 标为 mixed/borderline，避免把接近 0 的事件过度分类。
- 门槛 `>0` 且连续两个月是操作性诊断，必须在其他阈值和资料集上做敏感性检验。
- 全年份逐年检验严格使用过去年份拟合趋势和尺度；事件留一法仍受小样本限制。

## 关键输出

- 机制审计图：`/Users/daiyue/Documents/Maryland/output/pdf/ep_cp_two_gate_full_event_test.pdf`
- 预测技巧图：`/Users/daiyue/Documents/Maryland/output/pdf/ep_cp_type_prediction_skill.pdf`
- 事件表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/ep_cp_two_gate_event_summary_1982_2023.csv`
- 逐年预测技巧：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/ep_cp_type_walkforward_skill_2000_2023.csv`
- 暖事件留一法技巧：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/ep_cp_type_event_loeo_skill.csv`
