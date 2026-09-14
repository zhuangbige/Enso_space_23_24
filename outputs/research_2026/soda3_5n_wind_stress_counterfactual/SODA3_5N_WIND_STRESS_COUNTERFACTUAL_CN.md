# SODA3 5°N风应力反事实敏感性试验

## 结论先行

在保持每个CT事件的SODA3温度场不变时：

- 控制试验的Dec(0)–May(+1) Ekman Q20为 **+2.18 ZJ**，95%区间 [+0.92, +3.43]。
- 去除CT日历月线性去趋势风应力异常后，Q20变为 **+0.65 ZJ**；相对控制减少 **+1.52 ZJ**，区间 [+0.52, +2.70]。
- 用CP合成风应力异常替换CT风应力异常后，Q20变为 **+0.60 ZJ**；相对控制减少 **+1.57 ZJ**，区间 [+0.43, +2.88]。
- 作为参照，实际CP事件为 **+0.41 ZJ**。
- 去除CT风应力异常后的结果与实际CP仅差 **+0.25 ZJ**，区间 [-0.24, +0.77]；换成CP风应力后的差值为 **+0.20 ZJ**，区间 [-0.12, +0.50]。两者区间均跨零，说明修改风应力后，固定CT温度场得到的直接Ekman出口已降入CP事件的统计范围。

因此，在固定CT海洋热状态下，CT特有的5°N风应力异常对直接Ekman暖量出口的观测幅度具有可辨识且关键的贡献。去除风异常后仍保留一部分北向Q20，因为CT较暖的0–50 m水体仍会被气候态西向信风输送；所以不能写成“没有CT风异常就完全没有北向出口”，也不能把整个Ekman出口都归因于风异常。

## 试验设计

1. **CT control**：使用事件同期SODA3温度和风应力。
2. **CT τ′ removed**：温度不变，把风应力替换为1982–2022逐日历月线性基线。
3. **CT temperature + CP τ′**：温度和CT年代基线不变，将CT风应力异常替换为4个CP事件的Dec–May合成异常；bootstrap同时重采样CT温度事件与CP风事件。
4. **τ′ dose**：把CT风应力异常从0倍连续放大到1.5倍，温度固定，检验剂量响应。
5. 所有情景均相对于原控制Q20的同月线性基线计算异常，再积分为ZJ；不重新调整SSH、密度或总流速。

## 稳健性与硬校验

- 至 90°W：去除CT风应力异常使Q20减少 +1.35 ZJ，CT→CP风应力替换使其减少 +1.37 ZJ。
- 至 85°W：去除CT风应力异常使Q20减少 +1.42 ZJ，CT→CP风应力替换使其减少 +1.46 ZJ。
- 至 80°W：去除CT风应力异常使Q20减少 +1.52 ZJ，CT→CP风应力替换使其减少 +1.57 ZJ。

- 反事实控制与现有5°N Ekman事件结果的最大误差为 3.89e-09 ZJ。
- 0.5倍应力情景与0倍、1倍情景线性中点的最大误差为 1.11e-16 ZJ。
- 控制结果中可由CT风应力异常直接移除的均值比例为 70%；该比例是固定温度条件下的诊断量，不代表整个耦合系统的总因果贡献。
- 4个CT事件的控制−去风异常差值全部为正；逐一删除任一CT事件后，平均减少量仍为 0.93–1.96 ZJ。

## 能回答什么，不能回答什么

这一步比相关和时间先后更强，因为它直接改变了Ekman公式中的风应力，并保持温度不变；结果可表述为“局地CT风应力异常是再现直接Ekman暖量出口完整幅度所必需的组成，并呈线性剂量响应”，但不是北向输送保持正号的唯一条件。

但它仍是离线反事实：SSH、密度梯度、海流、SST和大气对流没有随修改后的风应力重新演化。因此不能据此宣称整个5°N总Q20或地转调整已经通过严格因果试验。要完成最终因果闭环，需要在强迫海洋模式或耦合模式中执行相同的风应力关闭/替换试验。

## 产物

- 主图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/soda3_5n_wind_stress_counterfactual/soda3_5n_wind_stress_counterfactual.png`
- 月度情景：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_wind_stress_counterfactual_monthly.csv`
- 事件累计：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_wind_stress_counterfactual_event.csv`
- CT温度×CP风应力替换矩阵：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_wind_stress_replacement_matrix.csv`
- bootstrap汇总：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_wind_stress_counterfactual_summary.csv`
- 诊断：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_wind_stress_counterfactual_diagnostics.json`
