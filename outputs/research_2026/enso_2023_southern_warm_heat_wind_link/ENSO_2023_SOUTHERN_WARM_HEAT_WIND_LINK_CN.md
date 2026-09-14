# 2023年风异常与暖量南偏：动力诊断

## 结论先行

2023年1—2月的南侧风异常与次表层暖量南偏存在明确对应，但证据不支持把它写成“整层暖量被净输送到南边”。更准确的过程图景是：

1. 暖核南侧5°—10°S出现强异常偏东风应力，产生直接向南的表层Ekman分量；
2. 同期`−∂τx/∂y`为正，在南半球对应偏下沉的风应力结构，有利于温跃层加深和次表层暖异常形成；
3. SODA3跨5°S的0—300 m总Q20异常仍为向北，说明非Ekman环流抵消了表层风驱南向分量；
4. 跨10°S的质量守恒整层焓输送在1—2月平均也为向北（南向符号下为 **-0.099 PW**）。

因此，报告中的“暖量偏南”首先是一个**温度/热含量空间配置和温跃层位移**，不能等同于整层暖水的净南向出口。

## 1. 1997、2015与2023的同口径对照（1—2月平均）

| 事件 | 南偏指数 (MJ m⁻³) | τx′ (N m⁻²) | 南向Ekman代理 (m² s⁻¹) | −∂τx/∂y (10⁻⁸ N m⁻³) | 5°S总Q20南向 (PW) | 5°S Ekman Q20南向 (PW) |
|---|---:|---:|---:|---:|---:|---:|
| 1997 | +1.90 | -0.011 | +0.58 | -0.74 | -0.003 | +0.055 |
| 2015 | +2.65 | -0.006 | +0.29 | -0.27 | -0.046 | +0.031 |
| 2023 | +6.56 | -0.034 | +1.89 | +2.42 | -0.084 | +0.219 |

2023的南偏指数约为1997的 **3.5 倍**、2015的 **2.5 倍**。在1982—2024年的2023暖核经度窗中，2023年1—2月南偏指数的平均百分位为 **100.0%**，南向Ekman代理为 **87.2%**。

固定120°E—80°W全盆地平均时，2023年1—2月南偏指数只有 **+1.80 MJ m⁻³**，明显小于暖核随动窗口的 **+6.56 MJ m⁻³**。因此风—暖量关系应解释为暖核附近的局地过程，而不是整个热带太平洋同步南移。

## 2. 时间关系

- 1月南向Ekman代理领先2月南偏指数：Pearson `r=+0.47`，原始`p=0.001`，FDR `q=0.010`，bootstrap 95%区间`[+0.23, +0.66]`。
- 2月南向Ekman代理领先3月南偏指数：Pearson `r=+0.43`，原始`p=0.004`，FDR `q=0.016`，bootstrap 95%区间`[+0.22, +0.61]`。
- 2023年3月以后τx′转为偏西，但南偏指数仍在3月达到峰值，支持“早期风建立、随后海洋结构维持”，不支持逐月同步平流解释。

## 3. 5°S输送分解

2023年1—2月平均：

- 直接Ekman Q20南向分量：**+0.219 PW**；
- 0—300 m总Q20南向异常：**-0.084 PW**；
- 非Ekman剩余：**-0.303 PW**。

正值表示向南。风驱分量确实向南，但总输送为负，表明次表层/非Ekman北向补偿更强。这里的5°S总输送使用流速面赤道侧4.75°S温度；正式论文应增加5.25°S温度居中敏感性。

## 4. 固定2023温度的风应力反事实

1—2月平均南向Ekman Q20：

- 2023控制：**+0.127 PW**；
- 去除2023风应力异常：**-0.084 PW**；
- 替换为1997风应力异常：**-0.047 PW**；
- 替换为2015风应力异常：**-0.120 PW**。

该试验只改变Ekman公式中的风应力并固定2023温度场，因此可以说明2023风异常对直接表层南向分量的贡献，但不能代表耦合海洋在风被替换后会如何重新调整。

## 5. 最稳妥的机制表述

> 2023年1—2月，暖核南侧异常偏东风应力产生了显著的南向表层Ekman分量，并伴随南半球偏下沉的纬向应力梯度结构；这可能参与建立或加强南侧温跃层加深和150—250 m暖异常。然而，跨5°S和10°S的整层总热输送并未同步转为净南向，说明2023的“暖量南偏”主要表现为垂向/经向结构重组，而不是整层暖水的单向南逃。

## 数据和口径

- SODA3.15.2：暖核随动纬度—深度剖面、5°S总流速和风应力、三箱10°S质量守恒焓输送；
- ERA5：月平均纬向湍流表面应力；
- 暖量南偏：150—250 m、5°—15°S减5°—15°N，暖核中心±10°经度；
- 距平：剖面1980—2024；SODA3输送1980—2022外推；ERA5风应力1982—2024；均为同历月线性去趋势；
- `−∂τx/∂y`只是完整风应力旋度的纬向应力分量。当前缺少2023年同域τy，因此没有把它称为完整Ekman pumping。

## 产物

- 主图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/enso_2023_southern_warm_heat_wind_link/enso_2023_southern_warm_heat_wind_mechanism.png`
- 滞后与反事实图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/enso_2023_southern_warm_heat_wind_link/enso_2023_southern_warm_heat_lag_and_counterfactual.png`
- 全年份月表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_2023_southern_warm_heat_wind_all_years.csv`
- 全盆地敏感性：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_2023_southern_warm_heat_full_pacific_sensitivity.csv`
- 三事件月表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_1997_2015_2023_southern_warm_heat_wind_monthly.csv`
- 滞后统计：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_2023_southern_warm_heat_lag_relations.csv`
- 10°S输送表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_1997_2015_2023_south_10s_transport_monthly.csv`
- 反事实表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_2023_south_5s_wind_counterfactual.csv`
