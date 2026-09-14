# ENSO大气“接上”与类型转换：扰动实验结果

## 先给结论

这轮结果否定了“一个变量单独主导所有年份”，也没有发现把2023单个条件改掉就能稳健改型的证据。更符合资料与动力研究的解释是一个有顺序、带竞争路径的条件链：

`多年La Niña与外海盆背景 → NPMM/西中太平洋梯度 → 对流空间结构与WWB发生概率 → 东北风或西风支路 → 暖量东传 → 成熟型态`。

在13个事件的观测统计中，去掉同期SST幅度和东西型结构后的经向降水偶极，是唯一仍与综合大气响应显著相关的量；但它主要对应降水和气压支路，对西风应力不显著，因此是**接通状态/中介指标，不是已经确证的上游主因**。多年La Niña、Indo-Atlantic加热、NPMM与高频WWB的独立份额都无法在这个小样本中稳定分开。

## 1. 实验如何定义

- 事件：1982、1986、1991、1994、1997、2002、2004、2006、2009、2015、2018、2019、2023。
- 气候态：所有重新计算的月异常统一使用1982—2024；随后去线性趋势。
- 大气是否接上：MJJ降水、东西气压驱动和中太平洋风应力分别对同期Niño3.4、Niño3−Niño4和趋势做留一年回归，三者标准化残差平均。正值表示给定SST后大气响应比历史预期强。
- 多年La Niña：前三个冬季低于−0.5°C的个数与过去30个月冷异常积分组成连续记忆量。
- Indo-Atlantic加热：MJJ热带印度洋和热带北大西洋SST相对1982—2024气候态的联合量；去趋势并移除Niño3.4的相对加热定义另作稳健性检验。
- NPMM：OISST SST与ERA5 10米风联合EOF的FMA指数，已去趋势并移除Niño3.4。
- 经向降水偶极：MJJ、180°—90°W，赤道带降水减6°—10°N降水，并移除同期Niño3.4、Niño3−Niño4和趋势；正值对应Jiang所述“赤道增强、北侧抑制”的额外空间结构。
- 东北风桥梁：ERA5 MJJ 850 hPa、3°—7°N和180°—130°W，将负u与负v投影成正的东北风入侵，并同样移除同期SST幅度与型态。
- 随机西风爆发代理：SODA3五日135°E—180°风应力，先移除各事件逐月均值，再累计超过1个五日扰动标准差的正脉冲。它是高频WWB代理，不等同于逐日ERA5严格WWB目录。
- 海洋条件：3—4月140°W Q20与D20组合；成熟型态同时用正交E/C和Niño3−Niño4，避免单一分型定义支配结论。

## 2. 哪个因素最接近“接上”环节

| 因素 | 控制海洋/FEP/早期型态后的partial r | 95% bootstrap CI | FDR q |
|---|---:|---:|---:|
| FEP meridional rain dipole | +0.72 | [+0.47, +0.91] | 0.024 |
| Multi-year La Niña memory | -0.33 | [-0.69, +0.03] | 0.676 |
| Indo-Atlantic total heating | +0.22 | [-0.33, +0.68] | 0.770 |
| Warm NPMM | +0.10 | [-0.52, +0.51] | 0.875 |
| High-frequency westerly pulses | +0.05 | [-0.41, +0.40] | 0.875 |

五个候选量全加入后，留一事件回报的RMSE skill为 **+0.165**，相关为 **+0.58**。只加入降水偶极时的skill反而更高，为 **+0.359**；这说明全因子模型已出现小样本过拟合，不能把系数解释为因果份额。

分支检验显示，偶极与降水残差的partial r为+0.79（FDR q=0.009）、与气压梯度为+0.71（q=0.033），但与纬向风应力只有+0.46且区间跨零。因此它能识别“对流—气压已响应”，却不能单独证明中太平洋西风已经接上。

## 3. +1σ单因子扰动

| 因素 | Δ大气接通/SD | 95% CI | ΔE/C型态/SD | 95% CI |
|---|---:|---:|---:|---:|
| Multi-year La Niña memory | -0.01 | [-0.21, +0.09] | +0.00 | [-0.05, +0.08] |
| Indo-Atlantic total heating | +0.00 | [-0.42, +0.62] | -0.00 | [-0.24, +0.06] |
| Warm NPMM | +0.05 | [-0.37, +0.37] | -0.01 | [-0.15, +0.12] |
| FEP meridional rain dipole | +0.49 | [-0.02, +0.81] | -0.11 | [-0.42, +0.19] |
| High-frequency westerly pulses | +0.04 | [-0.66, +0.38] | -0.01 | [-0.15, +0.18] |

bootstrap区间在大气接通目标上不跨零的因素：**无**。但这只是固定因果图和岭回归下的观测扰动，不是模式积分产生的强迫响应。

## 4. 2023换条件会不会改型

以下实验全部不使用2023来拟合；把2023的一个条件替换成中性值或1997/2015平均值，再沿结构链向下传播。

| 情景 | Δ接通/SD | ΔE/C/SD | E/C过零？ | ΔNiño3−Niño4/SD | box指标过零？ |
|---|---:|---:|---:|---:|---:|
| Neutralize multi-year La Nina | +0.02 | -0.00 | 否 | -0.00 | 否 |
| Neutralize Indo-Atlantic heating | -0.33 | +0.07 | 否 | +0.08 | 否 |
| Replace NPMM with 1997/2015 mean | +0.03 | -0.01 | 否 | -0.01 | 否 |
| Remove FEP rain dipole | -0.70 | +0.15 | 否 | +0.16 | 否 |
| Replace WWB pulses with 1997/2015 mean | -0.05 | +0.01 | 否 | +0.01 | 否 |
| NPMM + WWB to 1997/2015 | +0.01 | -0.00 | 否 | -0.00 | 否 |
| All atmospheric factors to 1997/2015 | -0.21 | +0.04 | 否 | +0.05 | 否 |

本组统计替换中出现的过零记录数为 **0**。只有当E/C与box两个定义、不同岭参数、不同偶极区域和删除极端事件后都保持同向，才能称为稳健类型转换；否则只能说成熟暖中心发生位移。

## 5. 2023为什么特别

- 多年La Niña记忆：+1.62 SD；
- Indo-Atlantic总加热：+2.27 SD；
- NPMM：-1.07 SD；
- FEP经向降水偶极：+1.22 SD；
- 高频西风脉冲：-0.66 SD；
- 3°—7°N东北风入侵：+1.39 SD；
- MJJ大气接通残差：-0.24 SD。

2023同时表现为强多年La Niña遗产、创纪录式外海盆增暖、冷NPMM、少WWB、高东北风入侵和弱纬向风应力；但FEP残余增暖与降水偶极又都很强。这说明“对流有响应”与“赤道西风反馈接上”不是同一件事。

## 6. 当前能下什么结论

1. **大气“接上”至少要拆成两条支路。** 降水—气压支路可在FEP/经向偶极下明显响应；真正能推动暖水东传的是赤道西风—风应力支路。2023是前者存在而后者偏弱，若继续把三者平均成一个量，会掩盖这一点。
2. **Jiang机制在2023个例上成立，但不是13事件中的普适单因子。** 2023东北风入侵为+1.39 SD、纬向应力响应为−0.95 SD；跨事件的“偶极→东北风”partial r=+0.51、“东北风→纬向应力”r=−0.28，符号符合机制但bootstrap区间均跨零。FEP残余本身与东北风只有r=+0.05，因此还需要北侧冷却/降水组织等条件。
3. **WWB有真实海洋作用，但不是独立随机冠军。** 五日脉冲保留了高频随机成分，其发生又受背景态调制；因此更准确的称呼是state-dependent stochastic forcing。
   SODA3独立的传播核验中，西太平洋五日风应力扰动与随后140°W暖水输送的最大相关出现在风领先约20天，r=+0.17，事件块bootstrap区间[+0.12, +0.26]。
4. **多年LaNiña、NPMM与外海盆加热是上游背景，不宜互相竞争“第一名”。** 多年LaNiña既充电又可留下西暖—中冷/冷NPMM背景；NPMM影响梯度、MJO与WWB概率；Indo-Atlantic加热可远程压制太平洋对流。它们高度共线，而且在不同事件可同向或抵消。
5. **观测替换没有产生类型转换。** 2023的7组单因子/组合替换在E/C和Niño3−Niño4两种指标上均未过零；所有区间都很宽。成熟型态的留一RMSE skill以4月海洋门控单独最高（E/C为+0.301），加入MJJ耦合后为+0.208。这说明当前样本中海洋暖量的位置比单个大气因子更稳定，但不表示大气不重要。
6. **所以现在的回答是“条件链+交互”，不是单因子。** 只有耦合模式中固定海洋初态、逐一替换NPMM、外海盆、FEP残余和WWB，并积分到DJF，才能判定人为改变一个条件是否真的改型。

## 7. 下一组动力扰动必须怎么做

已生成可直接交给CAM6/ECHAM与CESM类模式的实验矩阵。AGCM先回答“给定SST后为何不出西风”：CTRL-2023、PAC-only、去Indo-Atlantic、NPMM-neutral、去FEP残余/去北侧冷却。耦合模式再回答“是否改型”：固定同一2023海洋初态，分别加入/移除WWB并做 `NPMM × WWB` 与 `Indo-Atlantic × residual-FEP` 因子试验，至少20成员、多个WWB起始日期，积分到DJF并同时诊断E/C与Niño3−Niño4。只有第二层能检验事件类型转换。

## 8. 稳健性边界

- 13个暖事件远小于动力模式大样本，极端事件会强烈影响斜率。
- 2023替换实验虽排除了2023训练，但1997/2015同时是极端事件，替换值不是随机处理。
- GPCP为月资料；经向偶极是中介过程，不能与上游外海盆/NPMM当成完全独立处理。
- 东北风桥梁用月平均850 hPa风；它能检验Jiang空间机制，但不能代替逐日天气尺度动量收支。
- SODA3五日风应力比逐日ERA5平滑，适合脉冲敏感性，不适合宣布标准WWB日数。
- FDR、事件bootstrap、总/相对外海盆加热、不同偶极经度、不同岭惩罚以及删除极端事件均保存在表中；若结论只在单一设定成立，不作主结论。

## 9. 文件

- 事件指标：`data/derived/research_2026/enso_perturbation_event_indices_1982_2023.csv`
- 偏相关/FDR：`data/derived/research_2026/enso_perturbation_partial_correlations.csv`
- 留一事件技巧：`data/derived/research_2026/enso_perturbation_model_skill.csv`
- 单因子扰动：`data/derived/research_2026/enso_perturbation_counterfactual_effects.csv`
- 2023替换：`data/derived/research_2026/enso_perturbation_2023_replacements.csv`
- 稳健性：`data/derived/research_2026/enso_perturbation_robustness.csv`
- WWB—140°W输送滞后核验：`data/derived/research_2026/enso_wwb_to_140w_transport_lag_validation.csv`
- FEP—东北风桥梁事件表：`data/derived/research_2026/enso_ne_wind_bridge_event_indices.csv`
- FEP—东北风关系表：`data/derived/research_2026/enso_ne_wind_bridge_relationships.csv`
- 动力模式矩阵：`data/derived/research_2026/enso_dynamical_perturbation_experiment_matrix.csv`
- 图：`outputs/research_2026/perturbation_attribution/fig1_event_factor_and_response_matrix.pdf`、`outputs/research_2026/perturbation_attribution/fig2_single_factor_perturbation_effects.pdf`、`outputs/research_2026/perturbation_attribution/fig3_2023_counterfactual_replacements.pdf`、`outputs/research_2026/perturbation_attribution/fig4_fep_ne_wind_bridge.pdf`

## 10. 与权威研究的对应

| 机制 | 已有最强证据 | 本研究能否独立复现 | 判断 |
|---|---|---|---|
| 多年LaNiña→西部暖量/西伸增暖→弱西风 | Fan et al. (2026)：观测热收支、CAM5/6、CESM1/2 | 方向上支持；事件partial r=-0.33但不显著 | 重要背景，非充分条件 |
| 冷NPMM→不利梯度/MJO/WWB | Lin et al. (2025)：观测+2200年CESM1 | 2023冷NPMM且WWB偏少；跨事件独立效应不稳 | 对2023很有解释力，非普适冠军 |
| FEP残余→降水偶极→东北风 | Jiang et al. (2026)：ECHAM4.6集合 | 2023个例符号完整；13事件路径区间跨零 | 事件特异机制，需要条件交互 |
| Indo-Atlantic加热→抑制太平洋响应 | 2025 CEE：AGCM去/加外海盆强迫 | 2023为+2.27 SD；跨事件观测效应定义敏感 | 2023抵消项，不宜外推为所有事件主因 |
| WWB→Kelvin波/暖量东传 | Chen et al. (2015)耦合模式；Lin et al. (2025) | SODA3显示约20天后140°W输送增强 | 有因果能力，但发生概率依赖背景态 |

- Jiang et al. (2026), GRL: https://doi.org/10.1029/2026GL123227
- Fan et al. (2026), The Innovation Geoscience: https://doi.org/10.59717/j.xinn-geo.2026.100224
- Lin et al. (2025), npj Climate and Atmospheric Science: https://doi.org/10.1038/s41612-025-01013-z
- 2023/24 Indo-Atlantic warming AGCM study, Communications Earth & Environment: https://doi.org/10.1038/s43247-025-02584-8
- Chen et al. (2015), Nature Geoscience: https://doi.org/10.1038/ngeo2399
