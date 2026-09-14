# 完全基于标准OHC的三个问题复算结果

主定义为0—300 m固定深度OHC与标准 $\rho_0c_p\int vT\,dA$ 热输送；正文结果不使用H20。

## 问题一：热量是否进入140°W以东？

单断面 $vT$ 依赖参考温度，因此主证据采用东部OHC变化和全边界净水平辐合；断面值只报告0、10、20°C参考范围。

| 事件 | 东部OHC变化（ZJ） | 140°W东向vT范围（ZJ） | 净水平热辐合范围（ZJ） |
|---|---:|---:|---:|
| 1997 | +14.79 | +15.92—+36.36 | +16.15—+28.06 |
| 2015 | +5.77 | -9.41—+8.69 | +3.29—+10.27 |
| 2023 | +6.08 | -1.32—+9.02 | +8.63—+11.77 |

## 问题二：成熟后热量去了哪里？

以下为Jan(+1)—May(+1)。OHC减少和净水平辐合为负表示东部箱体放热；5°N与海表项为正表示向北输出或向大气失热。

| 事件 | 东部OHC变化 | 5°N总vT范围 | 5°N Ekman范围 | 海表热损失 | 净水平辐合范围 |
|---|---:|---:|---:|---:|---:|
| 1997 | -16.53 | +7.04—+8.67 | +3.27—+9.43 | +4.37 | -54.67—-14.19 |
| 2015 | -18.51 | -3.22—+3.73 | +2.49—+5.85 | +1.17 | -26.44—-10.02 |
| 2023 | -16.12 | -9.12—+1.58 | +1.59—+2.91 | +0.40 | -21.88—-7.18 |

## 问题三：为什么2015与2023没有形成相同耦合？

| 指标 | 2015 | 2023 |
|---|---:|---:|
| 发展期东部OHC增加（ZJ） | 5.77 | 6.08 |
| 次年5°N Ekman范围（ZJ） | +2.49—+5.85 | +1.59—+2.91 |
| 5°N西风应力异常（N m⁻²） | 0.0063 | 0.0024 |
| 海表异常热损失（ZJ） | 1.17 | 0.40 |
| 强度耦合残差（z） | 1.39 | -0.29 |
| SLP→风应力残差（z） | 1.40 | -0.16 |

2015与2023的OHC到达量只差约5%，但2015的西风应力、Ekman热输出和海表热损失均更强；2023的最弱环节位于SLP→风应力。该结果支持海气接通差异，但不证明单向因果。

### 离线换风实验（固定海洋状态）

固定目标事件的5°N温度和非Ekman输送，只替换去趋势的5°N风应力异常。控制试验与直接计算的闭合误差小于 $4\times10^{-9}$ ZJ。

| 固定海洋状态 | 1997风 | 2015风 | 2023风 |
|---|---:|---:|---:|
| 1997 | +8.67 | +4.69 | +1.87 |
| 2015 | +0.87 | -3.22 | -6.07 |
| 2023 | -2.26 | -6.31 | -9.12 |

上表是标准 $vT$、$T_{ref}=0$°C的重构总出口。总值受参考温度与未闭合体积输送影响，2015/2023的绝对正负号不稳健；因此换风实验的稳健证据应读成风造成的增量，而不是某一参考温度下的总值。

| 换风效应 | Tref=0°C | Tref=10°C | Tref=20°C |
|---|---:|---:|---:|
| 2015海洋：换成2023风 | -2.85 | -1.82 | -0.80 |
| 2023海洋：换成2015风 | +2.81 | +1.79 | +0.77 |

三个参考温度下方向完全一致：2023风都会削弱固定2015海洋状态下的北向热输送，2015风都会增强固定2023海洋状态下的北向热输送。由此可保留‘局地风应力是2015—2023 Ekman差异的重要贡献者’，但OHC版不支持‘总出口状态几乎完全互换’这一更强表述。

## 与H20结果相比

| 事件 | 发展期OHC/H20储量比 | 衰减期OHC/H20储量比 |
|---|---:|---:|
| 1997 | 1.59 | 1.70 |
| 2015 | 1.64 | 1.67 |
| 2023 | 1.57 | 1.76 |

OHC给出的储量变化幅度约为H20的1.6—1.8倍，但三事件排序和2015≈2023的结论不变。真正发生变化的是开放断面的输送值：2015、2023的140°W和5°N总vT可能随参考温度换号，不能像Qwarm,20那样直接给出唯一的暖水通道量。

## 输出文件

- 月资料：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_only_monthly_1980_2024.csv`
- 13事件阶段表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_only_phase_summary_13events.csv`
- CT/CP合成：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_only_ct_cp_summary.csv`
- CT/CP同窗OHC/H20对比：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_vs_h20_ct_cp_comparison.csv`
- 三事件OHC/H20比较：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_vs_h20_comparison.csv`
- 参考温度敏感性：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_only_reference_temperature_sensitivity.csv`
- 耦合相关：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_only_coupling_correlations.csv`
- 全指标OHC/H20对比：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_vs_h20_all_metric_comparison.csv`
- 稳健性审计：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_only_robustness_audit.csv`
- 三事件海气链：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_only_three_event_coupling_chain.csv`
- OHC离线换风汇总：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_2015_2023_wind_swap_summary.csv`
- OHC/H20换风对比：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_ohc_vs_h20_wind_swap_comparison.csv`
- 图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/ohc_only_three_questions/soda3_ohc_only_three_questions_comparison.png`
- 对比图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/ohc_only_three_questions/soda3_ohc_vs_h20_all_data_comparison.png`
- OHC离线换风图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/ohc_only_three_questions/soda3_ohc_2015_2023_wind_swap.png`
