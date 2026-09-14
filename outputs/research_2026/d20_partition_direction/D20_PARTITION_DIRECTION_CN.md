# D20与暖量空间分配：谁领先谁？

## 结论

**当前13事件交叉滞后检验没有证明“早期D20单向驱动后续暖量偏北分配”，也没有证明相反方向。D20与partition更像共享同一春季调整过程；其中partition是距离后续海气响应更近的统计表征。**

主窗口Jan—Feb → Mar—Apr中，D20预测后期partition、同时控制早期partition后的偏相关为r=-0.32（p=0.290）；反向partition预测后期D20、控制早期D20后为r=-0.15（p=0.614）。两者都不稳健。
但Jan—Apr partition在控制Jan—Feb D20、早期partition和Mar—Apr到达量后，仍对应较弱的MJJ风应力响应（r=-0.68, p=0.011）。因此早期D20并未替代partition对后续耦合效率的信息。

## 三组交叉滞后窗口

| 方向 | partial r | permutation p | 95% CI |
|---|---:|---:|---:|
| D20 JF -> partition Jan-Apr | partition Jan-Feb | -0.32 | 0.290 | [-0.75, +0.28] |
| Partition Jan-Feb -> D20 MA | D20 JF | -0.15 | 0.614 | [-0.80, +0.48] |
| D20 FM -> partition Jan-May | partition Jan-Mar | -0.16 | 0.592 | [-0.73, +0.41] |
| Partition Jan-Mar -> D20 AM | D20 FM | -0.62 | 0.021 | [-0.88, +0.03] |
| D20 MA -> partition Jan-Jun | partition Jan-Apr | +0.45 | 0.123 | [-0.30, +0.90] |
| Partition Jan-Apr -> D20 MJ | D20 MA | -0.46 | 0.110 | [-0.84, +0.22] |

如果D20是稳定上游原因，三组D20→partition关系应连续同号且强于反向路径；实际结果没有出现这种结构。个别反向窗口较强，但也不跨窗口稳定，因此不能据此改写成partition驱动D20。

## 探索性D20中介路径

路径D20(JF) → partition(Jan—Apr) → wind(MJJ)得到a=-0.25、b=-0.65、间接效应ab=+0.16，95% bootstrap CI [-0.14, +0.64]。区间跨零，因此D20→partition→大气的中介链尚未闭合。

## 三事件的时间位置

| 事件 | D20 JF | partition Jan→Feb | D20 MA | partition Jan→Apr | MJJ风应力响应 |
|---:|---:|---:|---:|---:|---:|
| 1997 | +1.61 SD | -1.32 SD | +1.89 SD | -1.36 SD | +1.94 |
| 2015 | +0.85 SD | +0.54 SD | +1.82 SD | -1.02 SD | +2.13 |
| 2023 | +0.07 SD | +0.53 SD | +0.38 SD | +0.84 SD | -0.58 |

2023早期D20并不深，但到Mar—Apr有所增加，同时累计partition由中等正值进一步发展为明显正异常。1997则是D20很深、partition持续偏南/偏赤道；2015的早期partition为正，但到4月转为负。三个案例符合D20与partition共同演化，但不足以决定因果箭头。

## 论文中应如何写

推荐：空间分配效应与大尺度温跃层结构并不独立；交叉滞后检验尚未识别稳定单向关系，表明D20和partition可能是同一春季海洋调整的相互关联表现。partition在控制早期D20后仍保留对后续风应力响应的信息，因此可作为温跃层动力状态映射到海气接通效率上的近端可观测表征。

不推荐：D20已经被证明通过北向暖量分配造成海气响应减弱。

## 下一步

观测统计已经接近样本上限。下一步最有增量的不是继续换窗口，而是用海洋动力诊断分解D20—partition共同变化：检查SSH/压力梯度、地转经向输送、风驱Ekman输送和边界波传播；决定性因果证据仍需要耦合模式中独立扰动D20斜率与暖量南北分配。
