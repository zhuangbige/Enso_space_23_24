# SODA3 5°N 暖量北向出口的海洋动力分解

## 结论先行

在与 Chakravorty et al. (2021) 重叠的 4 个 CT 与 4 个 CP 事件中，Dec(0)–May(+1) 的 5°N、140°W–80°W 原生 SODA3 北向 Q20 异常，CT/CP 分别为 **+2.77/-1.00 ZJ**；CT−CP 为 **+3.77 ZJ**，95% 事件 bootstrap 区间 [+1.39, +6.04]。

动力分解给出的核心判断是：

- 地转项（SSH 表面地转流 + 温盐密度热成风）CT/CP 为 **+0.87/-1.23 ZJ**，CT−CP 为 **+2.10 ZJ**，区间 [+0.95, +2.96]。
- SODA3 自身风应力估算的 Ekman 项为 **+2.18/+0.41 ZJ**，CT−CP 为 **+1.77 ZJ**，区间 [+0.45, +3.23]。
- 残差为 **-0.27/-0.17 ZJ**。它按定义包含非地转流、Ekman 近似误差、垂向/沿岸结构和诊断误差，不能直接命名为某一种流。

最重要的细分是：**CT 组自身显著的北向项是 Ekman（+2.18 ZJ），CT 地转北向项的区间跨零；CP 组则出现显著的地转南向异常（−1.23 ZJ），Ekman 项不显著。** 因而：

- 若回答“CT 暖水怎样向北离开”，第一主角是风驱 Ekman，事件均值约占 CT 总北向输出的 79%。
- 若回答“为什么 CT 与 CP 不同”，则地转差异和 Ekman 差异都重要，按均值分别约为总差异的 56% 与 47%；前者主要表现为 CP 的南向地转异常，后者表现为 CT 更强的北向 Ekman 输出。

因此论文不应写成“纯 Ekman 北逃”，也不应把地转项说成独立外强迫。它是一个运动学分解：SSH/密度压力场本身也会响应风和热力过程。只有置信区间不跨零并通过边界/EOS敏感性的项，才称为可辨识动力贡献。

## 为什么这一步能收束到海气耦合

这套分解把先前的大气证据接回了海洋内部：CT 在东太平洋形成更强的暖异常和对流，随后 5°N 附近西向风应力与正风应力旋度增强；现在用同一 SODA3 产品检验，其中有多少跨 5°N 暖量输出可由局地风应力 Ekman 输送解释，又有多少对应海面高度和密度梯度控制的地转调整。这样“暖量去了哪里”不再只是箱体收支，而成为可检验的 **SST/对流 → 风应力 → Ekman 与海洋压力场调整 → 暖量北出口** 链条。

后续逐月检验也给出相同次序：Dec(0)先出现东部H20和降水差异，Jan(+1)东部SST与总Q20差异变得可辨识，Feb西向风应力以及Ekman/地转Q20均显著为正，Mar Ekman与总出口仍为正。完整时序见 `outputs/research_2026/soda3_5n_coupled_timing/SODA3_5N_COUPLED_TIMING_CN.md`。月资料支持先后顺序，但不替代耦合模式扰动试验。

## 稳健性

- 终点 90°W：总量 +3.51 ZJ，地转 +1.95 ZJ，Ekman +1.60 ZJ。
- 终点 85°W：总量 +3.55 ZJ，地转 +1.98 ZJ，Ekman +1.68 ZJ。
- 终点 80°W：总量 +3.77 ZJ，地转 +2.10 ZJ，Ekman +1.77 ZJ。

- EOS-80 改成线性状态方程后，80°W 终点的 CT−CP 地转项为 +2.19 ZJ（EOS-80 为 +2.10 ZJ）。
- 原生总 Q20 与既有三箱 5°N 边界逐月复算的最大绝对误差为 2.75e-09 PW，相关系数 1.000000。
- 全部月—深度—经度格点的总流速异常与重建地转流速异常相关为 r=0.76。该相关只用于检查结构一致性，不等同于因果归因。
- 8 个事件中，总 Q20 与“地转+Ekman”的相关为 r=0.995；逐一删除任一事件后仍为 0.991–0.997。
- 不平滑分解得到的 CT/CP 总量 +2.77/-1.00 ZJ，与此前完整月轴三个月平滑结果 +2.74/-0.96 ZJ 几乎一致，说明结论不是平滑选择造成的。
- SODA3 自身风应力的 CT−CP Ekman 差异为 +1.77 ZJ；独立 ERA5 风应力的一阶估算为 +1.67 ZJ，95% 区间 [+0.44, +3.19]。两套资料对风驱差异给出近乎相同的量级。

## 方法与限定

1. 断面：5°N，140°W–80°W，0–300 m；北向为正；东端另取 90°W、85°W 做边界敏感性。
2. Q20：`rho0 cp ∫ v max(T−20,0) dz dx`，与原三箱暖量预算完全同定义。
3. 地转流：`v_g(0)=g/f ∂SSH/∂x`；深度向下为正时，`v_g(d)=v_g(0)+g/(rho0 f)∫0^d ∂rho/∂x dd`。主结果用 UNESCO EOS-80 的 0 dbar 位密度，线性 EOS 作敏感性。
4. Ekman：`M_y=−tau_x/(rho0 f)`，用 0–50 m 平均的 `(T−20)+` 折算 Q20。这是第一阶深度积分估算，不假设它等于 SODA3 原生 Ekman 层流量。
5. 所有分量先按日历月在 1982–2022 年线性去趋势，再以整事件为样本累计 Dec(0)–May(+1)；本分解不做三个月平滑，以避免只有 Dec–May 断面时跨缺月伪平滑。
6. 残差严格定义为总量−地转−Ekman，不作动力学过度命名。5°N 接近赤道，地转近似对小尺度噪声敏感，这也是必须报告边界和 EOS 敏感性的原因。

## 产物

- 主图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/soda3_5n_current_decomposition/soda3_5n_current_decomposition.png`
- 月度分量：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_current_decomposition_monthly.csv`
- 事件累计：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_current_decomposition_event.csv`
- bootstrap 汇总：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_current_decomposition_summary.csv`
- 断面合成：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_current_decomposition_composites.nc`
- 诊断：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_5n_current_decomposition_diagnostics.json`
