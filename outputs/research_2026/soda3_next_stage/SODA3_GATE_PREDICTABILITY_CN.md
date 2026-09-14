# 140°W暖水闸门的留一事件预测检验

## 设计

13个暖事件逐一留出；每一折只用其余12个事件去趋势、标准化和训练。
基线为当月已经存在的Niño3−Niño4型态，新增量分别为日界线、160°W、
140°W暖水输送或东部暖含量倾向。预测目标为成熟DJF Niño3−Niño4。

## 140°W结果

- 2月：RMSE skill=+0.123，p=0.127，q=0.253，95% bootstrap区间[-0.105, +0.243]。
- 3月：RMSE skill=+0.289，p=0.037，q=0.173，95% bootstrap区间[+0.072, +0.484]。
- 4月：RMSE skill=+0.472，p=0.006，q=0.122，95% bootstrap区间[+0.261, +0.640]。
- 5月：RMSE skill=+0.182，p=0.107，q=0.239，95% bootstrap区间[-0.049, +0.353]。
- 6月：RMSE skill=+0.035，p=0.279，q=0.430，95% bootstrap区间[-0.123, +0.132]。

最佳结果出现在4月，skill=
+0.472，但没有通过配对改进检验。
所有新增模型×月份统一FDR后均不显著。

## 解释

140°W输送是目前最强的机制分型指标，但尚未证明它在小样本留一预测中
提供独立于当月SST型态的稳定增量。报告中应写“有潜力的过程预测因子”
或“动力检查点”，不能写成“已显著提高预测技巧”。

这项阴性结果不否定机制：13个事件、强EP事件较少，且140°W输送与当月
SST型态共享信息。要证明预测价值，需要扩大事件/集合样本，或把它用于
实时概率更新而不是单一线性点预测。

## 文件

- 留一预测：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_gate_loeo_predictions.csv`
- 技巧表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_gate_loeo_skill.csv`
