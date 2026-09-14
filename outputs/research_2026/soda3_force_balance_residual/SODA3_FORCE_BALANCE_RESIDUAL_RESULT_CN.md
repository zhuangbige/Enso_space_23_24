# SODA3简化受力平衡残差的过程归因

## 设计

基准模型仍为季节项、已有日界线暖水输送、D20压力坡度和当前风应力。新增变量被预先分为四组，并且只使用当前或过去五日资料：

1. **西风脉冲记忆**：五日风应力变化、过去15日正西风均值、过去15日风应力波动；
2. **Kelvin波/温跃层相位代理**：200°E D20倾向、220°E—200°E D20坡度倾向、对应SSH坡度倾向；
3. **输送结构与非线性代理**：160°E—180°E及180°E—220°E暖水输送差、输送×D20坡度交互；
4. **热含量几何**：140°W以东暖量比例、暖量质心变化、东西热含量梯度变化。

所有模型使用完全相同的五日样本。外层按完整事件留一，内层再按事件选择岭回归强度，避免用被检验事件调参。

## 五日输送倾向结果

- 基准模型事件等权RMSE为 `1.368 Sv day⁻¹`，相关为 `+0.41`。
- 四个单独过程组中表现最好的是 **+ transport structure**：RMSE `1.339 Sv day⁻¹`，相关 `+0.45`。
- 相对基准的事件平均MSE变化为 `-0.078`，95%事件自助区间 `[-0.180, +0.051]`；`10/13` 个事件改善。
- 该增量在事件层面没有通过零差异检验，因此只能把它视为候选排序，不能宣称已经完成残差闭合。

## 组内探索性细化

由于输送结构组和西风记忆组排名靠前，进一步只保留最直接的单项，且锁定为与主试验相同的408个五日样本：

- 仅加入**过去五日风应力变化**，MSE变化 `-0.058`，95%区间 `[-0.122, -0.002]`，`9/13` 次改善；系数在 `100%` 的事件留一折中为正。
- 仅加入**160°E输入减180°E输出的上游输送盈余**，MSE变化 `-0.077`，区间 `[-0.177, +0.039]`，`10/13` 次改善；系数在 `100%` 的折中为正。
- 两项合并后MSE变化 `-0.129`，区间 `[-0.240, +0.010]`。

风应力变化单项的区间刚好低于零，但这是看过过程组排序后的二阶段细化，必须标为**探索性发现**，不能当成预注册的独立显著性结果。物理上它说明重要的不是“西风现在有多强”，而是西风是否正在快速增强。

## 晚期事件时间外检验

只用1982—2009事件训练，再整体预测2015、2018、2019和2023：

- 基准模型事件等权RMSE `1.435`；
- 仅风应力变化 `1.417`；
- 仅上游输送盈余 `1.364`；
- 两项合并 `1.349 Sv day⁻¹`，并在 `4/4` 个晚期事件中优于基准。

这个结果支持一个更具体的工作假说：缺失项主要是**正在增强的西风所触发的上游暖水输送脉冲**，而不是静态D20坡度、单独的东部热含量位置，或目前使用的Kelvin相位代理。

## 十日倾向稳健性

- 十日目标的最佳单独过程组是 **+ transport structure**；基准RMSE `1.042`，最佳模型 `1.023 Sv day⁻¹`。
- MSE变化 `-0.039`，95%区间 `[-0.125, +0.077]`，未通过事件检验。

## 关键个例

- 1997年最佳过程组的MSE变化：`-0.179`；
- 2015年：`-0.287`；
- 2023年：`-0.117`。

负值表示新增过程减少了基准残差。三次事件不必同号；如果2023改善而1997恶化，说明该项可能专门描述弱耦合背景，而不是通用ENSO动力。

## 科学判断

这个试验回答的是“哪一类当前/滞后状态最能补充简化平衡面”，不是人为扰动后的因果归因。即使某组通过，也仍需要把对应项写入完整的热量或动量收支，或者用模式扰动实验确认。

## 输出

- 图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_force_balance_residual_attribution.pdf`
- 公共样本与候选量：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_residual_features.csv`
- 留一预测：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_residual_loeo_predictions.csv`
- 模型评分：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_residual_skill.csv`
- 事件MSE差：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_residual_event_deltas.csv`
- 探索性单项细化：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_residual_refinement_bootstrap.csv`
- 早期训练—晚期事件检验：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_residual_late_block.csv`
