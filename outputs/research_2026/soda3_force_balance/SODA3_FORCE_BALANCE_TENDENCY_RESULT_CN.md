# 金飞飞充电振子框架下的SODA3受力平衡修正检验

## 关键修正

上一轮把净力代理与Q20输送的正负直接比较，这在动力学上不严格。受力平衡约束的是流速或输送的**变化率**：

\[
\frac{dM}{dt}=F_{pressure}+F_{wind}-rM+F_{unresolved}.
\]

所以 `F_net=0` 时，已有东向输送仍然可以保持为正。上一轮约0.51的分类准确率不能用来否定平衡点。

## 修正后的资料检验

- 13次暖事件，SODA3五日资料；响应量为下一五日日界线20°C以上暖水体积输送倾向，单位Sv day⁻¹。
- 海面坡度代理使用SSH西—中差；金飞飞式内部温跃层坡度代理使用D20西—中差和约化重力 `g′=0.02 m s⁻²`。
- 模型包含已有输送 `M`，因为稳态平衡必须包含摩擦/阻尼或流动记忆。
- 验证按完整事件留一，并用事件聚类自助法给出区间。

## 结果

### 只把两项相加仍不够

- SSH净力代理与未来五日暖水体积输送倾向：`r=+0.35`，95%区间 `[+0.29, +0.43]`。
- D20净力代理与未来五日输送倾向：`r=+0.32`，95%区间 `[+0.25, +0.38]`。

这不表示没有受力平衡，而是说明“压力+风”仍未包括已有流动的惯性/阻尼、非线性平流、经向动量通量和波动相位。

### 加入已有输送后形成平衡面

- 仅输送记忆模型LOEO RMSE：`1.500 Sv day⁻¹`。
- D20压力+风+已有输送模型RMSE：`1.379 Sv day⁻¹`，预测—观测相关 `+0.44`。
- 相对记忆模型的事件平均MSE变化：`-0.347`，95%区间 `[-0.530, -0.166]`。
- 相对只含压力和风的模型，加入已有输送后的MSE变化：`-0.179`，95%区间 `[-0.324, +0.008]`。
- D20压力项在 `100%` 的留一折中为正；风项在 `100%` 中为正；已有输送项在 `100%` 中为负。

完整经验平衡不是一个固定OHC数，而是：

\[
b_0+b_s\sin\phi+b_c\cos\phi+b_pF_{D20}+b_wF_{wind}+b_mM=0.
\]

它在 `F_pressure–F_wind–M–season` 状态空间中是一张**平衡面**。事件轨迹穿过该面时，暖水输送由加速转为减速；但输送本身可以在面上保持非零。

## 与金飞飞理论的关系

金飞飞充电振子把快的温跃层倾斜调整与慢的盆地平均热含量分开：风应力与温跃层坡度的不平衡推动快速调整，盆地平均热含量 `h` 决定慢记忆，而东部SST `T` 决定Bjerknes反馈和放电。因此本研究应区分：

1. **动力受力平衡面**：决定暖量输送是加速还是减速；
2. **充电振子增长零线** `dT/dt=0`：决定海温开始增长还是衰减；
3. **大气耦合门**：决定增长能否转化为持续Bjerknes正反馈。

你的“必然存在平衡点”在完整动力系统中是正确的；需要修正的是，它不是一个只由西太平洋热含量决定的标量点。

## 输出

- 修正图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_force_balance_tendency_verification.pdf`
- 五日倾向表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_tendency_pentads.csv`
- 事件留一评分：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_tendency_loeo_skill.csv`
- 系数：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_tendency_loeo_coefficients.csv`
- 自助检验：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_force_balance_tendency_bootstrap.csv`
