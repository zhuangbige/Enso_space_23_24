# NMME回报试验：哪一类厄尔尼诺的春季预报障碍更明显

## 结论

在NOAA NMME 1991–2020年季节SST回报中，以固定SON为预测目标、用成熟DJF的
Niño3−Niño4观测指标区分事件后：

- EP组（n=3）从3–4月起报到6–7月起报的平均类型绝对误差变化为
  **+0.30 °C**；
- CP组（n=3）对应变化为
  **+0.01 °C**；
- EP减CP为 **+0.29 °C**，事件自助法95%区间为
  [-0.04,
  +0.62] °C，
  EP障碍较大的重采样概率为
  95%。
- 在6个单模式中，有
  **5/6**个给出EP大于CP，
  单模式EP−CP差值范围为
  [-0.29, +0.67] °C。

因此，本数据给出的判断必须分成两层：**点估计可用于判断方向，但样本不足以给出
稳定的类型差异显著性结论。** 如果EP的误差在春季后明显下降而CP没有同等下降，
才支持“EP春季障碍更强”；若两组差值很小或区间跨零，则只能说NMME中尚未验证该
文献结论。

敏感性检验显示，不去趋势时EP−CP为
**+0.27 °C**；主定义逐一剔除任一事件后，
EP−CP范围为
[+0.14,
+0.43] °C。
这用于判断方向是否完全由1997/98单个极端事件控制。

## 资料与方法

- 预测：NOAA CPC NMME季节SST回报，1°网格，1991–2020；
- 验证：NOAA ERSSTv5；
- Niño3：5°S–5°N，150°W–90°W；
- Niño4：5°S–5°N，160°E–150°W；
- Niño3.4：5°S–5°N，170°W–120°W；
- 类型指标：Niño3−Niño4；
- 每个模型、起报月、目标季节和区域分别计算1991–2020回报气候态；
- 预测与观测异常分别去除1991–2020线性趋势；
- EP/CP事件标签继续沿用现有报告的观测分型；这里不把模型回报气候态替换成报告
  的观测气候态，因为季节模式必须用各自回报期、各起报月的模式气候态订正漂移；
- 主检验固定SON目标，比较3–4月和6–7月起报的类型误差；
- EP/CP按成熟DJF观测类型指标阈值±0.2 °C分组，临界事件不参加两组比较。

## 基础预报技巧

NMME多模式平均对SON类型指标的全样本相关从3月起报的
**r=0.72**变化到7月起报的**r=0.88**；
Niño3.4对应从**r=0.78**变化到
**r=0.92**。这两条曲线必须同时看：Niño3.4技巧高但
Niño3−Niño4技巧低，说明模型可能预测到了厄尔尼诺强度，却没有预测对暖中心位置。

## 与海洋预条件和海气耦合的连接

在现有暖事件中，NMME 3–4月起报的SON类型绝对误差与候选量相关性最大的变量是
`may_jun_pattern_coupling_residual_z`（Pearson r=+0.96,
p=0.000, n=10）；控制成熟期类型幅度和
Niño3.4强度后，偏相关为
r=+0.79
（p=0.020）。
由于候选量多而事件数少，这只是探索性筛选，不作为独立机制证据；它的用途是决定
下一步应重点检查模型是否已经预测到东传暖水，还是预测到了海洋状态却没有接上
风—降水反馈。

## 科学限制

1. 1991–2020只有少量非临界EP和CP暖事件，集合成员不能替代独立事件；
2. 这里是业务回报验证，不是完美模式误差增长实验；
3. 固定SON目标下，较晚起报天然具有较短提前期，因此EP−CP差值比任一组的绝对
   “春季惩罚”更可解释；
4. IRI Niño3.4 plume不能区分EP和CP，只适合做实际业务预报强度的补充验证；
5. 最终结论需要用另一套系统（例如SEAS5）或更长的CFSv2回报作独立复核。

## 资料与文献链接

- NOAA CPC NMME数据入口：
  https://www.cpc.ncep.noaa.gov/products/NMME/data.html
- NOAA CPC季节回报CPT目录：
  https://ftp.cpc.ncep.noaa.gov/International/nmme/seasonal_nmme_hindcast_in_cpt_format/
- IRI ENSO历史业务预报：
  https://iri.columbia.edu/our-expertise/climate/forecasts/enso/archive/
- Hou, Duan & Zhi：EP春季障碍、CP夏季障碍的完美模式研究：
  https://link.springer.com/article/10.1007/s00382-019-04888-w
- Zhao et al. (2022)：外热带太平洋对跨越ENSO春季障碍的作用：
  https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022GL099488

## 输出

- 主图：`outputs/research_2026/nmme_enso_type_barrier/nmme_enso_type_spring_barrier_main.pdf`
- 技巧矩阵：`outputs/research_2026/nmme_enso_type_barrier/nmme_enso_type_skill_heatmaps.pdf`
- 事件预测轨迹：`outputs/research_2026/nmme_enso_type_barrier/nmme_son_event_type_forecasts.pdf`
- 全部指数：`data/derived/research_2026/nmme_enso_type_hindcast_indices_1991_2020.csv`
- 事件误差：`data/derived/research_2026/nmme_son_warm_event_errors.csv`
- 障碍统计：`data/derived/research_2026/nmme_son_type_barrier_summary.csv`
- 候选联系：`data/derived/research_2026/nmme_son_error_predictor_correlations.csv`
- 敏感性检验：`data/derived/research_2026/nmme_son_barrier_sensitivity.csv`
