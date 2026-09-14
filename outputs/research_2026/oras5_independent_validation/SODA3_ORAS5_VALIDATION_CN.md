# SODA3 结论的 ORAS5 独立验证

## 预先指定的主检验

从 SODA3 暖事件留一结果出发，只指定一个 ORAS5 确认性问题：
**5 月日界线以东的 D20 暖水体积占比越高，成熟 DJF 是否越偏 EP 型？**

- ORAS5 全 13 事件：r=+0.72，单侧事件置换
  p=0.010，n=13。
- 只保留 2015 年以前统一 consolidated 产品的 9 个事件：
  r=+0.74，单侧 p=0.026。

## 交叉再分析结果

- 7 个匹配指标的 SODA3–ORAS5 逐月异常相关平均为
  **+0.95**；每个相关的显著性使用整年成块置换，保留
  1–6 月的季节内结构。
- ORAS5 13 事件中绝对相关最高的是 **Eastern OHC tendency**：
  r=+0.77，
  p=0.001，
  q=0.006。
- 通过 ORAS5 事件族 BH-FDR 的量为：Eastern OHC tendency (r=+0.77, q=0.006)、D20-volume centroid (r=+0.77, q=0.013)、East D20-volume fraction (r=+0.77, q=0.015)、Eastern MLD 0.03 (r=+0.76, q=0.006)、D20 east minus west (r=+0.68, q=0.021)、SSH east minus west (r=+0.66, q=0.021)、OHC300 east minus west (r=+0.55, q=0.048)。

## 能否加强原结论

主检验在全部 13 事件和统一 consolidated 历史产品中都为正且 p<0.05，
因此 ORAS5 对“暖水向东再分配”提供了**跨再分析的方向性支持**。
这使结论从“单套 SODA3 支持的工作假说”加强为
“两套不同模式/同化架构一致支持的机制结论”。

但这仍不是完全独立观测或因果证明：
ORAS5 与 SODA3 都同化海洋观测，只是模式、资料同化系统和大气强迫不同。

ORAS5 time-series 产品没有温度定义的等温层深度，也没有垂向速度，因此本轮不能
独立复核 SODA3 的障碍层厚度和垂直平流。这两项仍需要 ORAS5 全三维温盐/流速、
SODA4，或五日资料的混合层热收支。

## 数据口径

- ORAS5：4°S、赤道、4°N，130°E–80°W，每 5° 一个点，1980–2024。
- ORAS5 consolidated 覆盖到 2014，operational 从 2015 开始；异常回归显式
  移除 2015 产品流平均跃变，并移除同月线性趋势。
- SODA3：沿用 1980–2024 同月去趋势异常。
- 事件：相同的 13 个 NOAA ONI 暖事件；成熟目标为 OISST DJF
  Niño-3−Niño-4。

## 来源

- CDS ORAS5 数据说明：<https://cds.climate.copernicus.eu/datasets/reanalysis-oras5>
- Zuo et al. (2019), *Ocean Science*, 15, 779–808：
  <https://doi.org/10.5194/os-15-779-2019>

## 输出

- ORAS5 指标：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/oras5_transition_indices_1980_2024.csv`
- 月度一致性：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_oras5_monthly_consistency.csv`
- 事件表：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/oras5_transition_event_summary_1982_2023.csv`
- 事件相关：`/Users/daiyue/Documents/Maryland/data/derived/research_2026/soda3_oras5_event_correlations.csv`
- 对照图：`/Users/daiyue/Documents/Maryland/output/pdf/soda3_oras5_independent_validation.pdf`
