# SODA3可解释预测量筛选结果

## 目前最有潜力的量

当前最强、同时具有明确物理含义的候选是**4月输送-储存指数**
（transport-storage index, TSI）：

`TSI_Apr = 0.5 × [Q20′(140°W, Mar-Apr) / 0.404 PW + D20′(140°W, Mar-Apr) / 12.75 m]`

Q20′为140°W暖水东向热输送异常，D20′为140°W热跃层深度异常；
两者都先取3–4月平均，再用1980–2024年全部年份4月样本的标准差归一化。
这个定义不使用成熟期信息。

- 与成熟DJF Niño3-Niño4的样本相关：
  r=+0.860，
  permutation p=0.0010，
  探索指标族FDR q=0.0083。
- 留一事件预测相对当月SST型态基线的RMSE skill：
  +0.632，
  p=0.0007，
  探索模型×月份FDR q=
  0.0537，
  bootstrap区间
  [+0.467,
  +0.808]。
- LOEO预测与观测相关为
  +0.922。

## 为什么它比单独一个量更合理

140°W Q20回答“热量有没有穿过动力闸门”，D20回答“热量是否已经转化为
当地热跃层加深和储存”。指数要求输送和储存同时偏强，因此对应：

西风/海流调整 → 暖水穿过140°W → 热跃层加深 → 东部持续增暖。

单独4月Q20的LOEO skill约为+0.47；加入储存分量后提高到约
+0.63。

## 跨资料发现：D20可预测走廊向东扩展

SODA3与ORAS5都显示D20和最终类型的高相关区在春季向东扩展，但
“最大相关所在经度”并非每个月都严格单调东移：

- 2–3月：主要位于175°W–165°W附近；
- 4月：155°W–140°W过渡带在两套资料中都已出现强相关；
- 5月：SODA3的最大值移到东部，而ORAS5的最大值仍偏中东太平洋，
  但130°W–120°W带平均值依然与最终类型强相关。

预先指定的ORAS5 4月155°W–140°W D20指标与最终类型相关
r=+0.797，
其LOEO RMSE skill=+0.540，
p=0.0014，
四个预设检查点FDR q=
0.0056。
这独立确认了D20传播/储存通道，但没有独立确认SODA3的Q20分量。

## 实际预测建议

1. 2–3月先看175°W–165°W D20是否显著偏深；
2. 4月底计算TSI，同时检查ORAS5的155°W–140°W D20；
3. 若TSI和过渡带D20都偏强，提高EP型概率；
4. 若信号停留在中部或Q20强但D20不维持，保留CP或FEP表层先行、
   海气耦合不足的可能。

目前不建议设置“超过某个数就一定转型”的硬阈值，而应把TSI作为连续
概率更新量。

## 稳健性与限制

- TSI样本相关的逐事件jackknife范围为
  [+0.761,
  +0.898]。
- 去掉1982、1997和2015三个极端事件后，样本相关降至
  +0.494；非极端事件LOEO
  技巧为+0.231，
  预测-观测相关为
  +0.617，仍为正但明显变弱。
- 2023的LOEO观测型态残差为
  +0.91°C，
  TSI预测只有
  +0.02°C。
  因此TSI更擅长识别“海洋动力驱动的经典EP路径”，对2023式FEP表层
  先行事件会低估。
- 只有13个暖事件，TSI是在探索阶段形成的候选；实际应用前需要用
  SODA4、ORAS5全三维温度/流速或未来事件做冻结公式验证。

## 文件

- 图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_operational_transition_predictor.pdf`
- 月度候选表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_operational_predictor_monthly.csv`
- 相关筛选：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_operational_predictor_screening.csv`
- 留一预测：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_operational_predictor_loeo_predictions.csv`
- 留一技巧：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_operational_predictor_loeo_skill.csv`
- SODA3/ORAS5 D20走廊：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_oras5_d20_predictive_corridor.csv`
- ORAS5检查点技巧：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/oras5_d20_checkpoint_loeo_skill.csv`
