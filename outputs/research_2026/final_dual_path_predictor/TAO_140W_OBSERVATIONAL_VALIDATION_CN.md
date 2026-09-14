# TAO 0°N, 140°W 对 SODA3 关键量的独立观测核验

## 核验问题

SODA3 的 140°W、5°S–5°N 截面上层暖水输送 `Q20`，以及赤道
`D20`，是否只是再分析产品内部的统计信号？本检验改用 NOAA/PMEL
TAO 锚系的日资料。所有比较都只用共同可用的 3–4 月，并分别去掉
日历月平均和线性趋势，再按年平均；显著性通过整年标签置换评估。

## 主要结果

- **TAO current-meter local Q20 proxy**：r = +0.91，95% bootstrap CI [+0.75, +0.97]，逐年置换 p = 0.0000，n = 23 年（1983–2020）。
- **TAO ADCP local Q20 proxy**：r = +0.86，95% bootstrap CI [+0.71, +0.94]，逐年置换 p = 0.0000，n = 27 年（1992–2022）。
- **TAO current-meter upper current**：r = +0.57，95% bootstrap CI [+0.35, +0.76]，逐年置换 p = 0.0033，n = 23 年（1983–2020）。
- **TAO ADCP upper current**：r = +0.63，95% bootstrap CI [+0.38, +0.83]，逐年置换 p = 0.0001，n = 30 年（1991–2022）。
- **TAO D20**：r = +0.91，95% bootstrap CI [+0.83, +0.95]，逐年置换 p = 0.0000，n = 36 年（1983–2022）。

## 怎样解释

1. **若两套流速仪的局地热权重代理都与 SODA3 Q20 同号且显著**，
   就说明 SODA3 捕捉到的至少不是纯粹的模式伪信号：赤道 140°W
   上层东向流及其携带的 20°C 以上暖水确实有独立观测对应。
2. **这仍不等于完整验证 Q20**。TAO 是 0°N 单点，SODA3 Q20 是
   5°S–5°N、0–300 m 截面积分。单点观测不能恢复经向结构，也不能
   排除 SODA3 对断面宽度、深层流或缺测期的偏差。
3. **D20 是更直接的同变量核验**：若 TAO 与 SODA3 D20 一致，
   可以把“储存/热跃层深度”证据等级放得高于只有产品间比较的量。

## 暖事件子样本（只作描述）

- TAO ADCP local Q20 proxy：只有 9 个暖事件有可用观测；TAO量与成熟型指数 r = +0.90，SODA3对应量 r = +0.91。
- TAO ADCP upper current：只有 10 个暖事件有可用观测；TAO量与成熟型指数 r = +0.19，SODA3对应量 r = +0.87。
- TAO D20：只有 11 个暖事件有可用观测；TAO量与成熟型指数 r = +0.47，SODA3对应量 r = +0.73。
- TAO current-meter local Q20 proxy：只有 7 个暖事件有可用观测；TAO量与成熟型指数 r = +0.94，SODA3对应量 r = +0.96。
- TAO current-meter upper current：只有 7 个暖事件有可用观测；TAO量与成熟型指数 r = +0.03，SODA3对应量 r = +0.93。

事件子样本很小且缺测不是随机的，因此不能把这里的事件相关当作新的
预测技巧检验。预测性能仍以严格的留一事件、时间顺序和全年度走步检验
为准。

## 证据等级

- **可写成观测支持**：3–4 月 140°W 赤道上层流/局地暖水输送代理与
  SODA3 Q20 的共同变化；TAO 与 SODA3 D20 的共同变化。
- **只能写成再分析诊断**：完整 5°S–5°N Q20 断面及其绝对量值。
- **仍不能写成业务模型**：TAO 缺测多、事件样本小，而且该量只在已知
  暖事件条件下用于类型更新，不能单独预测厄尔尼诺是否发生。

## 数据来源与可复现文件

- TAO 日流速（current meter 与 ADCP）、温度剖面及 D20：NOAA/PMEL
  ERDDAP，质量标志 1–3；每个深度每月不少于 5 个有效日，D20 每月
  不少于 10 个有效日。
- 局地 Q20 代理：在可用流速层上积分
  `u × max(T−20°C, 0)`，上限 120 m；它没有乘密度、热容或断面宽度，
  因而只比较异常的共同变化。
- 月度代理：`data/derived/research_2026/tao_140w_monthly_observation_proxies.csv`
- 配对异常：`data/derived/research_2026/tao_140w_pairwise_anomalies.csv`
- 统计汇总：`data/derived/research_2026/tao_140w_soda3_agreement.csv`
- 暖事件描述：`data/derived/research_2026/tao_140w_event_checkpoint.csv`
- 图：`output/pdf/tao_140w_observational_checkpoint.pdf`
