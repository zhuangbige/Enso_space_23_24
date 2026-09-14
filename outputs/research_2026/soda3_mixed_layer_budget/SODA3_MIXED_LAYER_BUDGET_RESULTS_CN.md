# SODA3 春季混合层热收支与日界线暖水闸门

## 结论

本阶段把“西太平洋有多少暖水”推进为“暖水是否真正跨过日界线，并在
中东太平洋被保留下来”。全部量采用 SODA3.15.2、1980–2024 年同月
气候态和同月线性趋势。

13 个暖事件的 5–6 月检验中，通过本组 BH-FDR q<0.10 的量为：

- 140°W warm-heat transport：r=+0.76，p=0.0030，q=0.020。
- Eastern warm-content tendency：r=+0.71，p=0.0038，q=0.020。
- Eastern mixed-layer warming：r=+0.72，p=0.0050，q=0.020。
- Eastern barrier-layer thickness：r=+0.75，p=0.0071，q=0.021。
- Mixed-layer horizontal advection：r=+0.68，p=0.0123，q=0.024。
- Mixed-layer vertical advection：r=+0.66，p=0.0137，q=0.024。
- Unresolved/entrainment residual：r=+0.67，p=0.0138，q=0.024。
- 180°–140°W zonal convergence：r=-0.64，p=0.0181，q=0.027。
- Eastern density mixed-layer depth：r=+0.59，p=0.0315，q=0.042。
- Mixed-layer surface heating：r=-0.57，p=0.0475，q=0.057。
- 200°E warm-heat transport：r=+0.51，p=0.0727，q=0.079。

这组结果应与上一阶段的暖水质心、日界线以东暖水比例、D20、SSH 和
ORAS5 独立验证共同解释。日界线输送本身的相关只有
r=+0.17
（q=0.582），而 200°E/160°W
输送提高到 r=+0.51
（q=0.079），140°W输送进一步
达到 r=+0.76
（q=0.020）。180°–140°W
“纬向辐合”的相关为
r=-0.64
（q=0.027）；负号表示 EP
事件中 140°W 的向东输出常强于日界线入口，即暖水不是停留在中部，
而是继续穿过 140°W 进入东部。

因此真正的“转变点”不是暖水第一次越过 180°，而是春季输送能否向
160°W–140°W 继续推进，并伴随东部暖含量增长、垂向平流和障碍层建立。
残差虽然与事件类型相关，但其幅度很大，只能说明月平均收支遗漏的夹卷、
混合、高频协方差和同化增量重要，不能把“残差”当作一种已识别机制。

## 月份定位

- Dateline transport：Mar，r=+0.50，q=0.136。
- 140°W transport：Apr，r=+0.82，q=0.009。
- Zonal convergence：Mar，r=+0.25，q=0.467。
- Eastern warm-content tendency：Jun，r=+0.77，q=0.011。
- Vertical advection：May，r=+0.66，q=0.045。
- Barrier layer：Jun，r=+0.84，q=0.011。

星号检验在 5 个过程量 × 5 个月共 25 个检验上统一控制 FDR，因此比逐图
挑选显著月份更严格。

## 代表事件

- 1994：类型指数-0.24 °C；日界线热输送+0.237 PW；纬向辐合+35.7 W m⁻²；东部暖含量倾向+24.7 W m⁻²。
- 1997：类型指数+2.18 °C；日界线热输送+0.492 PW；纬向辐合-125.8 W m⁻²；东部暖含量倾向+121.4 W m⁻²。
- 2004：类型指数-0.53 °C；日界线热输送-0.098 PW；纬向辐合+15.7 W m⁻²；东部暖含量倾向+3.6 W m⁻²。
- 2015：类型指数+1.07 °C；日界线热输送-0.271 PW；纬向辐合-119.3 W m⁻²；东部暖含量倾向+36.9 W m⁻²。
- 2019：类型指数-0.61 °C；日界线热输送-0.425 PW；纬向辐合-20.8 W m⁻²；东部暖含量倾向-49.6 W m⁻²。
- 2023：类型指数+0.59 °C；日界线热输送+0.413 PW；纬向辐合-59.6 W m⁻²；东部暖含量倾向+49.0 W m⁻²。

## 计算定义

- 日界线暖水热输送：
  `rho*Cp*integral[u*max(T-20°C,0) dz dy]`，5°S–5°N、0–300 m，
  正值表示向东；这里报告去趋势的同月异常。
- 180°–140°W 纬向辐合：180°入口输送减去 140°W 出口输送，再除以
  区域水平面积。它只表示纬向分量，不包含 5°S/5°N 边界的经向输送。
- 混合层热收支：月际混合层温度倾向减去月平均水平平流、垂直平流和
  表面净热通量贡献，剩余记为残差。
- 残差不是单一物理过程；它包含夹卷、垂向/侧向混合、月平均遗漏的
  高频协方差、数值效应以及资料同化增量。

## 仍需的高频验证

SODA 官方提供 5 日资料。下一步只需针对代表事件下载区域子集，验证
月平均结果是否由少数西风爆发/Kelvin 波过程主导；不宜直接下载每个
约 285 MB 的完整全球文件。

## 文件

- 过程指标：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_mixed_layer_budget_indices_1980_2024.csv`
- 经度输送：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_warm_transport_longitude_1980_2024.csv`
- 事件表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_mixed_layer_budget_event_summary_1982_2023.csv`
- 相关检验：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_mixed_layer_budget_event_correlations.csv`
- 月份检验：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_mixed_layer_budget_monthly_event_correlations.csv`
- 主图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_mixed_layer_budget_transition_evidence.pdf`
- 经度—月份图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_dateline_warm_transport_hovmoller.pdf`
