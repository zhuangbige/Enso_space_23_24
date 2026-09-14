# Peng式JJA预期响应与早期OHC展宽

## 一句话结果

把时间固定在我们关心的JJA发展期，只采用Peng等人的“一元SST预期响应”算法后，JFM离赤道OHC展宽与随后JJA三项综合大气响应残差的相关为 **r=-0.52**（13次事件，置换p=0.068，bootstrap 95%区间[-0.83, +0.22]）。方向仍然是“越宽，后续响应越弱”，但强度和稳健性明显弱于此前控制SST强度、EP–CP型态和趋势的版本（此前约r=-0.81）。

更重要的是，这个相关主要来自降水，而不是风和气压三者共同提供同等强度的证据。因此它适合写成**补充敏感性检验**，不适合替代当前主结果。

## 这是不是Peng原文的时间平均

不是。本版本按你的要求使用JJA，不采用Peng原文的6月至次年1月。保留下来的只有核心计算形式：

\[
A_{\mathrm{JJA},y}=a+b\,\mathrm{Ni\tilde{n}o3}_{\mathrm{JJA},y}+\epsilon_y.
\]

其中回归样本为1982—2023年全部42年，和Peng公开代码一样使用整段样本直接拟合，不做EP–CP型态控制、长期趋势控制或逐年留一预测。

## 月异常和季节平均

1. 对Niño-3及每个大气量，先减去1982—2022年各同历月气候态；
2. 对6、7、8月异常取平均，得到每年的JJA异常；
3. 用42个年份拟合上式；
4. 预期响应为 \(\hat A_y=a+b\,\mathrm{Ni\tilde{n}o3}_y\)；
5. 用于跨事件相关的量为标准化差值：

\[
R_y=\frac{A_y-\hat A_y}{\sigma_\epsilon}.
\]

\(R_y>0\) 表示大气响应强于相同JJA Niño-3条件下的线性预期，\(R_y<0\) 表示弱于预期。它表示相对响应效率，不表示该年没有形成El Niño耦合。

## 三项主响应

- GPCP赤道太平洋降水；
- ERA5西减东海平面气压驱动；
- ERA5中西太平洋纬向风应力。

三项分别回归并标准化后等权平均：

\[
C_{\mathrm{Peng-JJA}}=\frac{R_{P}+R_{SLP}+R_{\tau}}{3}.
\]

这就是主散点图的纵轴。横轴仍是原来的JFM 0—300 m离赤道OHC残差：先用南、北两侧OHC平均表示离赤道暖量，再剔除三纬带总OHC的线性影响。因此本轮没有在纵轴上再控制一次总OHC。

## 42年预期响应拟合系数

- Equatorial Pacific rainfall：斜率 +1.1442 mm day-1/°C，截距 -0.0252 mm day-1，残差标准差 0.5666 mm day-1。
- West-minus-east SLP drive：斜率 +1.0047 hPa/°C，截距 -0.0177 hPa，残差标准差 0.4184 hPa。
- Central-western Pacific zonal wind stress：斜率 +0.0096 N m-2/°C，截距 -0.0003 N m-2，残差标准差 0.0085 N m-2。
- NCEP central-western Pacific near-surface wind：斜率 +0.7527 m s-1/°C，截距 -0.0385 m s-1，残差标准差 0.7978 m s-1。
- NCEP minus-SOI-like pressure response：斜率 +1.0816 standardized index/°C，截距 -0.0254 standardized index，残差标准差 0.9258 standardized index。

## 跨13次事件的结果

| JJA响应量 | Pearson r | 置换p | bootstrap 95%区间 | 逐事件剔除r范围 |
|---|---:|---:|---:|---:|
| 三项综合 | -0.518 | 0.0684 | [-0.825, +0.217] | [-0.624, -0.330] |
| 降水 | -0.695 | 0.0106 | [-0.894, +0.161] | [-0.749, -0.561] |
| SLP驱动 | -0.380 | 0.1976 | [-0.791, +0.117] | [-0.472, -0.227] |
| 风应力 | -0.277 | 0.3585 | [-0.720, +0.395] | [-0.443, -0.089] |
| NCEP风与-SOI近似综合 | -0.178 | 0.5666 | [-0.626, +0.355] | [-0.309, -0.017] |

其中降水单项关系最强（r=-0.69）；SLP和风应力只有同方向的弱到中等关系。最接近Peng原始变量的NCEP近地面风与-SOI综合仅为r=-0.18，没有形成稳健的跨事件支撑。

只保留JJA Niño-3已达到0.5°C的6次事件，三项综合相关为r=-0.78（置换p=0.083）。这个结果方向更强，但样本只有6个，应只作为预先可解释的阈值敏感性，不宜作为主证据。

## 2023年的具体结果

- JJA Niño-3异常：+1.73°C；
- JFM离赤道OHC展宽残差：+0.030 GJ m⁻²；
- 三项综合预期响应残差：-1.75 z；
- NCEP风与-SOI近似综合残差：-1.55 z。

各分量：

- Equatorial Pacific rainfall：观测/预期 = +47.3%，残差 = -1.82 z。
- West-minus-east SLP drive：观测/预期 = +58.0%，残差 = -1.73 z。
- Central-western Pacific zonal wind stress：观测/预期 = +12.1%，残差 = -1.69 z。
- NCEP central-western Pacific near-surface wind：观测/预期 = -24.7%，残差 = -1.98 z。
- NCEP minus-SOI-like pressure response：观测/预期 = +43.6%，残差 = -1.13 z。

2023在所有五个大气量上都弱于该JJA Niño-3对应的线性预期。因此，这一算法仍支持“2023发展期的海气响应效率偏低”；它不等于说2023成熟期仍处于脱耦状态。

## 为什么跨事件不用观测/预期比值

Peng原文的观测/预期百分比适合其筛选出的强事件和较长平均窗，但在本研究13个事件的JJA中，有些年份Niño-3接近零甚至为负，回归预期值也接近零。此时哪怕很小的观测异常也会产生几十倍、上千倍的比值。例如2004年JJA Niño-3仅约+0.05°C，所以比值会数值爆炸。

因此图a保留2023的Peng式百分比以便直观解释；跨事件图b—d统一使用 \(A-\hat A\) 的标准化残差。这里不是改变物理问题，而是避免零分母造成的统计伪信号。

## 当前汇报建议

主文仍保留此前的型态调整后结果，并把本轮结果放在稳健性或方法对照页：

> When the expected JJA atmospheric response is estimated using a Peng-style univariate Niño-3 regression, the cross-event relationship remains negative but weakens (r=-0.52) and is dominated by rainfall. Thus, meridional OHC spreading is consistent with reduced development-stage response efficiency, although the evidence is sensitive to how the atmospheric expectation is defined.

不要把本轮写成“复现了Peng原文结论”，应写成“Peng-style JJA adaptation”，因为时间窗、响应区域和资料并不完全相同。

## 输出文件

- 英文图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/enso_3d_warm_heat_spreading_decoupling/enso_peng_style_jja_broadening_response_en.png`
- 矢量图：`/Users/daiyue/Documents/Maryland/outputs/research_2026/enso_3d_warm_heat_spreading_decoupling/enso_peng_style_jja_broadening_response_en.pdf`
- 13事件完整量：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_peng_style_jja_broadening_event_table.csv`
- 统计检验：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_peng_style_jja_broadening_statistics.csv`
- 42年拟合系数：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_peng_style_jja_expected_response_fits.csv`
- 诊断信息：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/enso_peng_style_jja_broadening_diagnostics.json`
- 计算代码：`/Users/daiyue/Documents/Maryland/scripts/analyze_peng_style_jja_broadening_response.py`
