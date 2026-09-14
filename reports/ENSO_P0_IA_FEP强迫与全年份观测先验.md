# ENSO P0：IA×residual-FEP强迫文件与全年份观测先验

## 结论先行

已经把2023年3—8月的Indo–Atlantic总海温异常与residual-FEP空间分量拆成四组可移植的CF-NetCDF海温边界场；同时附加只保留IA独立残差的四格敏感性试验。两套四格都严格闭合到同一个观测场。

但1982—2024全年份观测先验并没有自动把IA×FEP确认为稳定因果交互。正Niño3.4发展年份中出现了“IA越暖，FEP对大气接通越不利”的负交互候选，但年份bootstrap区间仍跨零；最终仍以动力模式四格交互对比为准。

## 1. 强迫如何构造

- SST源：NOAA ERSSTv5月平均，2°网格。
- 时段：2023年3—8月；回归背景为1982—2024，逐月且排除2023。
- 主试验IA分量是2023相对逐月气候态的总异常，直接对应“保留/移除观测外海盆异常”；敏感性试验IAR只保留移除趋势、Niño3.4和E/C型态后的独立残差。
- FEP仍定义为5°S–5°N、90°W–80°W；用其独立残差回归得到热带东太平洋空间足迹，而不是改变FEP定义。
- 两个空间分量使用余弦边缘渐变，避免强迫边界产生数值跳变。

| 格点 | SST边界 |
|---|---|
| AG_IA0_FEP0 | 观测2023 − IA分量 − FEP分量 |
| AG_IA0_FEP1 | 上式 + FEP分量 |
| AG_IA1_FEP0 | 上式 + IA分量 |
| AG_IA1_FEP1 | 完整观测2023 |
| AG_IAR0/1_FEP0/1 | 同样四格，但IA改为独立残差分量 |

四格交互量：

`(IA1_FEP1 − IA1_FEP0) − (IA0_FEP1 − IA0_FEP0)`

## 2. NetCDF一致性检查

- 完整观测场重构最大误差：0.000e+00 °C。
- 因子对比恒等式最大误差：0.000e+00 °C。
- 独立IA敏感性试验重构/因子恒等式误差：0.000e+00 / 0.000e+00 °C。
- IA与FEP掩膜最大重叠：0.000e+00。
- 四组边界场海洋格点范围：-1.80 至 34.33 °C。

月度分量：

| 月 | residual-FEP种子 | 印度洋IA总异常 | 北大西洋IA总异常 | 印度洋IA独立残差 | 北大西洋IA独立残差 |
|---:|---:|---:|---:|---:|---:|
| 3 | +0.22 | -0.03 | +0.27 | -0.26 | +0.01 |
| 4 | +0.67 | +0.20 | +0.36 | -0.08 | +0.05 |
| 5 | +0.20 | +0.14 | +0.54 | -0.20 | +0.21 |
| 6 | +0.28 | +0.25 | +0.68 | -0.18 | +0.43 |
| 7 | +0.59 | +0.25 | +0.65 | -0.10 | +0.51 |
| 8 | +0.49 | +0.35 | +0.65 | -0.09 | +0.42 |

## 3. 1982—2024全年份观测交互

响应量为MJJ降水、SLP梯度和中西太平洋纬向风应力；每个年份都用排除该年的逐月回归移除同期Niño3.4、E/C型态和趋势，再将三条支路平均为综合接通量。交互模型同时控制4月早期型态、FMA NPMM、3—4月SODA3东部海洋门控和多年La Niña记忆。

| 响应 | n | IA×FEP系数(SD) | 95% bootstrap | Freedman–Lane p | FDR q |
|---|---:|---:|---:|---:|---:|
| Precipitation | 43 | -0.18 | [-0.50, +0.20] | 0.214 | 0.285 |
| SLP gradient | 43 | -0.34 | [-0.85, +0.12] | 0.043 | 0.171 |
| Zonal stress | 43 | -0.16 | [-0.67, +0.29] | 0.334 | 0.334 |
| Composite connection | 43 | -0.25 | [-0.66, +0.17] | 0.107 | 0.214 |

正Niño3.4发展年份敏感性：

| 响应 | n | IA×FEP系数(SD) | 95% bootstrap | FDR q |
|---|---:|---:|---:|---:|
| Precipitation | 23 | -0.45 | [-1.13, +0.42] | 0.042 |
| SLP gradient | 23 | -0.50 | [-1.46, +0.49] | 0.042 |
| Zonal stress | 23 | -0.58 | [-1.59, +0.32] | 0.026 |
| Composite connection | 23 | -0.54 | [-1.37, +0.37] | 0.026 |

IA总异常定义的稳健性对照：

| 样本 | 响应 | IA×FEP系数(SD) | 95% bootstrap | FDR q |
|---|---|---:|---:|---:|
| 全部年份 | Precipitation | -0.16 | [-0.41, +0.19] | 0.260 |
| 全部年份 | SLP gradient | -0.33 | [-0.73, +0.13] | 0.140 |
| 全部年份 | Zonal stress | -0.22 | [-0.71, +0.25] | 0.202 |
| 全部年份 | Composite connection | -0.26 | [-0.59, +0.16] | 0.158 |
| 正Niño3.4发展年份 | Precipitation | -0.33 | [-1.00, +0.63] | 0.084 |
| 正Niño3.4发展年份 | SLP gradient | -0.40 | [-1.21, +0.74] | 0.083 |
| 正Niño3.4发展年份 | Zonal stress | -0.52 | [-1.41, +0.56] | 0.036 |
| 正Niño3.4发展年份 | Composite connection | -0.43 | [-1.17, +0.63] | 0.056 |

解释：独立IA定义下，全43年样本的负交互未通过FDR。只保留MJJ Niño3.4为正的23年时，Freedman–Lane检验和留一年技巧给出较一致的负交互线索；然而年份bootstrap区间仍跨零。总异常定义给出相同的负号和相近的留一年改进，风应力交互通过FDR、综合接通量接近FDR阈值，但bootstrap同样跨零。因此符号并非只由IA定义造成，强度不确定性却仍很大。

## 4. 印度洋还是热带北大西洋

为避免联合IA指数掩盖两个海盆的相反作用，又在同一个模型中同时加入TIO×FEP与TNA×FEP。下表为23个正Niño3.4发展年份；模型仍控制相同四个背景量和两个海盆的主效应。

| 响应 | 海盆交互 | 系数(SD) | 95% bootstrap | FDR q |
|---|---|---:|---:|---:|
| Precipitation | Tropical Indian Ocean × residual FEP | -0.12 | [-1.05, +0.93] | 0.493 |
| Precipitation | Tropical North Atlantic × residual FEP | -0.55 | [-1.79, +1.45] | 0.209 |
| SLP gradient | Tropical Indian Ocean × residual FEP | -0.33 | [-1.49, +1.04] | 0.209 |
| SLP gradient | Tropical North Atlantic × residual FEP | -0.27 | [-1.85, +1.91] | 0.493 |
| Zonal stress | Tropical Indian Ocean × residual FEP | -0.36 | [-1.49, +0.60] | 0.209 |
| Zonal stress | Tropical North Atlantic × residual FEP | -0.49 | [-1.95, +1.38] | 0.209 |
| Composite connection | Tropical Indian Ocean × residual FEP | -0.26 | [-1.29, +0.86] | 0.214 |
| Composite connection | Tropical North Atlantic × residual FEP | -0.49 | [-1.93, +1.55] | 0.209 |

两个海盆拆开后，只有在系数符号、bootstrap区间与FDR三者同时一致时才允许指定主导海盆。若仍不一致，AGCM主四格应保持联合IA；只有主四格出现效应后，才进入TIO-only与TNA-only拆分。
正Niño3.4年份中加入两个海盆交互后，综合接通量的留一年相关增量为+0.05，RMSE改进为-0.062。

## 5. 留一年增量技巧

| 响应 | 主效应r | 加交互r | Δr | RMSE改进 |
|---|---:|---:|---:|---:|
| Precipitation | +0.43 | +0.40 | -0.03 | -0.024 |
| SLP gradient | +0.11 | +0.16 | +0.04 | -0.006 |
| Zonal stress | +0.18 | +0.14 | -0.04 | -0.030 |
| Composite connection | +0.29 | +0.28 | -0.01 | -0.015 |

## 6. 2023在新坐标中的位置

- Indo–Atlantic独立加热：+0.46 SD。
- Indo–Atlantic总异常：+0.92 SD。
- 印度洋/热带北大西洋独立残差：-0.80 / +1.59 SD。
- residual FEP：+1.37 SD。
- 综合大气接通残差：-0.28 SD。

## 7. 科学解释边界

这一步只回答“IA与FEP的联合状态在历史逐年样本中是否与额外大气响应同现”。它不能回答把IA海温人为移除后风是否一定改变；后者必须由30成员四格AGCM集合的因子主效应与交互量回答。

即使AGCM中交互显著，它也只能解释给定SST后大气为何接上；EP/CP是否真正翻型仍需下一阶段耦合模式的海洋门控×风场矩阵。

## 8. 与权威研究的关系

- Peng et al. (2025, Nature Geoscience)用AGCM表明2023年印度洋、大西洋增暖和慢变SST背景削弱了热带太平洋表面风响应；本阶段两种IA定义都得到负交互候选，方向一致，但观测不确定性更大：https://www.nature.com/articles/s41561-025-01700-9
- 2025年Communications Earth & Environment的三海盆AGCM实验显示，印度洋主要驱动跨太平洋东风，而大西洋产生东西不同号的风型；这解释了为什么本阶段把TIO与TNA拆开后不能简单期待同一个回归系数：https://www.nature.com/articles/s43247-025-02584-8
- Kim, Tian & Yu (2025)把2023年的减速联系到多年La Niña后持续的西中太平洋东风、东西SST梯度和NPMM/D20背景；这说明IA×FEP不是唯一上游控制：https://www.nature.com/articles/s41612-024-00890-0
- Jiang et al. (2026)提供residual-FEP及其大气响应机制；本阶段检验的是该局地FEP强迫是否会被外海盆背景调制，不是重复证明FEP自身存在：https://doi.org/10.1029/2026GL123227

因此，本阶段没有声称发现一个全新的单因子规律。新增贡献是把已有“FEP局地响应”和“外海盆抑制”两条文献链预注册成同一个四格交互试验，并给出全年份观测先验和可直接重映射的边界场。

## 9. 文件

- 强迫NetCDF：`experiments/enso_type_transition_matrix/forcing/ersstv5_2023_agcm_ia_fep_factorial_mar_aug.nc`
- 240成员运行清单：`experiments/enso_type_transition_matrix/p0_agcm_run_manifest.csv`
- 强迫月表：`data/derived/research_2026/enso_p0_agcm_forcing_monthly_summary.csv`
- 全年份表：`data/derived/research_2026/enso_p0_all_year_ia_fep_event_table.csv`
- 交互结果：`data/derived/research_2026/enso_p0_all_year_ia_fep_interaction.csv`
- 留一年技巧：`data/derived/research_2026/enso_p0_all_year_ia_fep_loyo_skill.csv`
- 分海盆交互：`data/derived/research_2026/enso_p0_basin_specific_fep_interactions.csv`
- 分海盆留一年技巧：`data/derived/research_2026/enso_p0_basin_specific_fep_loyo_skill.csv`
- 强迫图：`outputs/research_2026/p0_agcm_prior/fig6_p0_agcm_forcing_components.pdf`
- 观测先验图：`outputs/research_2026/p0_agcm_prior/fig7_p0_all_year_interaction_prior.pdf`
