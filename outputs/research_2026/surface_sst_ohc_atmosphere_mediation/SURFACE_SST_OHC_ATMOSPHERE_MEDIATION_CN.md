# 完整SST空间型态对OHC—大气关系的中介检验

## 问题与设计

本检验使用固定的13次暖事件。海下层前兆为3—4月中太平洋0—300 m OHC；表层中介为5—6月OISST完整热带太平洋型态（15°S—15°N、120°E—80°W），并显式加入中西太平洋绝对SST、27.5°C以上暖区面积和暖区经度中心；大气响应为5—6月ERA5 850 hPa西风、负OLR、降水和东向风应力的标准化综合。

所有预测均为留一事件检验。空间场只在每个训练折内计算主成分，主分析预先固定2个主成分和岭参数1，避免13事件小样本下调参追结果。

## 主结果

- 仅OHC的综合响应LOEO RMSE为 **0.759 SD**。
- SST箱区指标模型为 **1.051 SD**。
- 完整SST型态模型为 **1.078 SD**。
- 完整SST型态加入OHC后为 **0.837 SD**，RMSE变化为 **-0.241 SD**。
- 加入OHC后的逐事件平方误差平均变化为 **-0.462**，事件bootstrap 95%区间 **[-1.246, +0.039]**，改善方向的精确符号翻转p=0.088。
- 控制完整表层型态后的OHC条件系数为 **+0.469**，Freedman—Lane p=0.013。
- 2023的表层条件大气残差为 **-1.56 SD**，从弱到强排名 **1/13**。

## 当前判断

结果不支持“完整海表状态已经把OHC信息全部中介掉”。加入OHC后综合响应的留一误差明显下降，但逐事件误差差的95%区间略跨零、符号翻转p=0.088，因此跨事件增量属于**有方向一致性的支持证据，而不是5%水平的决定性证据**；全样本条件系数显著只作为辅助证据，不能替代留一事件结果。

2023尤其关键：完整SST型态单独会预期较强的大气响应，但实测综合响应明显更弱；加入较低的春季中太平洋OHC后，2023残差仍为 **-1.23 SD**，从弱到强仍排 **1/13**。因此2023的弱响应不能由海表型态或春季OHC中的任一项单独解释。

目前更准确的机制表述是：**海表空间型态提供大气热力强迫，次表层OHC仍提供额外的海洋预置和动力背景；二者共同约束大气响应，但2023在同时控制两者后仍存在异常弱的耦合效率。** OHC的统计增量不代表大气直接感受海下层，它也可能编码温跃层、未来海表持续性以及此前风场的共同状态。

## 稳健性与边界

- 1—3个主成分、岭参数0.1—10以及原始绝对SST场均已作为敏感性；加入OHC的综合响应RMSE范围为 **0.837—0.983 SD**。
- OISST型态距平使用1982—2024同月线性去趋势；绝对SST对流量保留真实背景态。
- ERA5降水单位从m day⁻¹转换为mm day⁻¹，所有箱平均采用cos纬度权重。
- 只有13次事件，因此留一事件技能、整事件bootstrap和置换检验优先于样本内R²。
- 这是观测中介检验，仍不能替代“固定海表、交换次表层初值”的OGCM试验和“固定次表层、交换SST型态”的AGCM试验。

## 文件

- 主图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/surface_sst_ohc_atmosphere_mediation/fig_surface_sst_ohc_atmosphere_mediation.png`
- SST型态图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/surface_sst_ohc_atmosphere_mediation/fig_may_june_sst_pattern_context_1997_2015_2023.png`
- 事件表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/surface_sst_ohc_atmosphere_mediation_event_table.csv`
- 留一预测：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/surface_sst_ohc_atmosphere_mediation_loeo_predictions.csv`
- 模型技能：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/surface_sst_ohc_atmosphere_mediation_model_skill.csv`
- OHC增量检验：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/surface_sst_ohc_atmosphere_mediation_increment_tests.csv`
