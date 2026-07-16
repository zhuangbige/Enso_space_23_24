# 2026 当前 ENSO/FEP 快速诊断

生成日期：2026-06-16  
分析范围：截至当前可通过 NOAA PSL OPeNDAP 取得的 2026 年资料。  
分析目的：沿用前期 2023/24 研究中的 **observed / regression-expected response** 逻辑，并借鉴 Jiang et al. 2026 GRL 的 **FEP residual** 思路，对 2026 年当前海温发展和大气响应同步性做第一版快速诊断。

## 一、当前数据可用性

这不是完整 2026 年季节分析，而是当前资料可用范围内的 quick-look。

| 数据 | 当前可用到 | 本次用途 | 本地输出 |
|---|---:|---|---|
| ERSSTv5 SST | 2026-05 | Niño-3.4、Niño-3、FEP、Niño1+2、外海盆 SST 指数 | `data/interim/research_2026/current_2026_monthly_indices.csv` |
| OISST v2.1 SST | 2026-05 | 交叉验证 Niño-3 SST | `data/interim/research_2026/oisst_nino3_monthly_1982_2026m05.csv` |
| GPCP precipitation | 2026-03 | 中太平洋/中西太平洋降水响应 | `data/interim/research_2026/current_2026_monthly_indices.csv` |
| NCEP/NCAR SLP | 2026-02 | Tahiti-Darwin SOI-like SLP 响应 | `data/interim/research_2026/current_2026_monthly_indices.csv` |
| NCEP/NCAR sigma995 u | 2026-02 nominal | 2026 年最新两个月为 NaN，暂不用于结论 | 同上 |
| CPC OLR | 待补 | 对流独立验证 | 本次未纳入 |
| ERA5 2026 | 待补 | 论文级 u10/u850/SLP/Walker 诊断 | 本次未纳入 |

## 二、方法口径

### 1. 海温异常

所有 SST 月异常均相对于 **1982-2022 月气候态** 计算。Niño 区域和 FEP 区域为：

- Niño-3.4：170°W-120°W，5°S-5°N。
- Niño-3：150°W-90°W，5°S-5°N。
- FEP：90°W-80°W，5°S-5°N。
- Niño1+2：90°W-80°W，10°S-0°。

### 2. FEP residual

借鉴 Jiang et al. 2026 GRL 的思路，将 FEP SST 分成 Niño-3.4 线性相关部分和 residual FEP 部分：

```text
FEP(t) = a × Niño3.4(t) + residual_FEP(t)
```

其中 `a` 由 1982-2022 每个月或每个短季节的历史回归得到。  
`residual_FEP > 0` 表示：在给定 Niño-3.4 强度下，FEP 比历史关系预期更暖。

### 3. 大气响应预期

对 GPCP 降水和 NCEP SOI-like SLP，沿用前期 Peng-style 逻辑：

```text
Atmospheric response = b × Niño3 + residual
```

用 1982-2022 的历史关系估计给定 Niño-3 SST 下的预期大气响应，再比较 2026 实际值和预期值。  
本阶段不重点使用 observed/expected ratio，因为 2026 初期 Niño-3 接近零时，预期值可能很小，比例会被不合理放大。

## 三、第一版结果

### 1. 2026 年春季 SST 已经明显转暖，而且东太平洋/FEP 更突出

ERSSTv5 结果显示，2026 年 1-5 月 SST 异常从冷态快速转为暖态：

| 月份 | Niño-3.4 | Niño-3 | FEP | Niño1+2 |
|---|---:|---:|---:|---:|
| Jan | -0.54 | -0.60 | -0.36 | -0.25 |
| Feb | -0.23 | -0.06 | +0.29 | +0.71 |
| Mar | +0.04 | +0.25 | +0.65 | +0.90 |
| Apr | +0.39 | +0.51 | +1.02 | +1.28 |
| May | +0.92 | +1.14 | +1.55 | +1.82 |

OISST v2.1 对 Niño-3 的交叉验证也显示同样趋势，2026 年 5 月 Niño-3 达到约 **+1.27°C**，与 ERSSTv5 的 **+1.14°C** 接近。

**初步判断**：  
2026 年截至 5 月已经出现明显的东太平洋增暖。它和 Jiang et al. 2026 所强调的 FEP/coastal-warming 视角有可比性，值得继续监测 AMJ/JJA。

### 2. FEP residual 从 2 月开始持续为正

FEP residual 结果如下：

| 时段 | Niño-3.4 | FEP observed | FEP expected from Niño-3.4 | FEP residual |
|---|---:|---:|---:|---:|
| Jan | -0.54 | -0.36 | -0.33 | -0.03 |
| Feb | -0.23 | +0.29 | -0.13 | +0.41 |
| Mar | +0.04 | +0.65 | +0.03 | +0.62 |
| Apr | +0.39 | +1.02 | +0.39 | +0.63 |
| May | +0.92 | +1.55 | +1.20 | +0.35 |
| MAM | +0.45 | +1.07 | +0.46 | +0.61 |
| Apr-May | +0.66 | +1.28 | +0.78 | +0.50 |

**初步判断**：  
2026 年春季 FEP 增暖并不只是 Niño-3.4 增暖的被动表现。尤其是 2-4 月，FEP 比历史 Niño-3.4-FEP 线性关系预期更暖约 **+0.4 到 +0.6°C**。这与 Jiang et al. 2026 的 FEP residual 机制非常相关。

### 3. GPCP 显示中太平洋降水仍偏弱，没有跟随 SST 同步增强

GPCP 中太平洋降水异常：

| 月份 / 时段 | Observed CP precipitation | Expected from Niño-3 | Observed - Expected |
|---|---:|---:|---:|
| Jan | -2.14 mm/day | -1.69 mm/day | -0.46 mm/day |
| Feb | -2.08 mm/day | -0.21 mm/day | -1.87 mm/day |
| Mar | -2.55 mm/day | +0.74 mm/day | -3.29 mm/day |
| JFM | -2.26 mm/day | -0.42 mm/day | -1.84 mm/day |

**初步判断**：  
尽管 SST 在 2026 年春季开始转暖，GPCP 中太平洋降水仍显著偏弱。尤其 3 月，在 Niño-3 已转为正异常时，历史回归预期中太平洋降水应偏正，但实际仍为强负异常。这说明 2026 年早春存在明显的 **SST warming 与降水/对流响应不同步**。

### 4. SOI-like SLP 仍偏 La Niña-like

NCEP Tahiti-Darwin SLP anomaly：

| 月份 | Observed SOI-like SLP | Expected from Niño-3 | Observed - Expected |
|---|---:|---:|---:|
| Jan | +1.70 hPa | +0.95 hPa | +0.76 hPa |
| Feb | +2.64 hPa | +0.12 hPa | +2.52 hPa |

**初步判断**：  
2026 年 1-2 月的 SOI-like pressure gradient 仍偏正，表现为更接近 La Niña-like 的气压梯度。由于 NCEP 低层风在 2026 最新月份为 NaN，当前还不能判断低层风是否也存在同样的不同步。

## 四、和 2023/24 研究主线的关系

目前 2026 的信号不能直接说成“另一个 2023/24 El Niño”，但它已经出现几个值得跟踪的相似点：

1. **东太平洋/FEP 增暖先行或偏强。**  
   2026 年 2-5 月 FEP residual 为正，说明 FEP 暖异常相对于 Niño-3.4 偏强。

2. **降水/对流没有同步跟上。**  
   2026 年 1-3 月 GPCP 中太平洋降水持续偏弱，和 SST 春季转暖不同步。

3. **气压仍残留 La Niña-like 背景。**  
   2026 年 1-2 月 SOI-like SLP 为正，说明大气压力梯度尚未转入典型 El Niño 响应。

这使 2026 成为一个很好的“实时检验场”：  
如果后续 AMJ/JJA 中 Niño-3 或 Niño-3.4 继续增暖，但 u10/u850、SLP、GPCP、OLR 仍不跟随，那么它可以和 2023/24 的“发展季海气不同步”形成非常有价值的对比。

## 五、当前不能下的结论

目前还不能说：

- 2026 已经形成强 El Niño；
- 2026 已经复现 2023/24 的完整海气脱耦；
- 低层风响应已经偏弱；
- Walker circulation 已经异常；
- OLR 对流响应已经被独立验证。

原因是：

- 2026 年 AMJ 还没有完整月平均资料，JJA/SON/DJF 尚未发生或尚无数据。
- GPCP 只到 2026 年 3 月。
- NCEP SLP 只到 2026 年 2 月。
- NCEP sigma995 u 在 2026 年最新两个月为 NaN，低层风需要 ERA5 或其它资料补充。
- CPC OLR 和 ERA5 pressure-level 还未接入本次 quick-look。

## 六、下一步建议

### 1. 立即补 ERA5 2026 月平均 single-levels

优先变量：

- 10 m u wind；
- mean sea level pressure；
- total precipitation 可作为对 GPCP 的辅助；
- surface fluxes 可后置。

目标时段：

- 2025-12 至 2026-06，先补 DJF、MAM 和 AMJ-to-date；
- 后续每月滚动更新。

### 2. 补 CPC OLR 2026 当前月份

不需要一开始跑全历史日资料。可以先只抽 2026 年 1-5 月 current OLR，再和已有历史 OLR 月序列拼接，减少 OPeNDAP 时间。

### 3. 做 Jiang et al. 2026 风格的空间图

优先图型：

- 2026 MAM / AMJ-to-date SST anomaly；
- FEP residual-related SST / precipitation / wind pattern；
- 2026 minus historical month/season mean；
- 2026 与 2023、pre-1980 FEP-dominant events 的简化对比。

### 4. 等 2026 年 6 月月平均出来后，正式做 AMJ

届时可生成与前期 2023/24 完全同口径的矩阵：

```text
SST forcing:
Niño-3.4 / Niño-3 / FEP residual / Niño1+2

Atmospheric response:
ERA5 u10 / u850 / SOI-like SLP / GPCP precip / CPC OLR

Period:
DJF(2025/26), MAM(2026), AMJ(2026), JJA(2026)
```

## 七、输出文件

| 类型 | 路径 |
|---|---|
| 月度指数表 | `data/interim/research_2026/current_2026_monthly_indices.csv` |
| FEP residual 表 | `data/derived/research_2026/current_2026_fep_residual.csv` |
| 大气 observed-vs-expected 表 | `data/derived/research_2026/current_2026_regression_expected_response.csv` |
| 快速诊断图 PNG | `outputs/research_2026/current_2026_quicklook_diagnostics.png` |
| 快速诊断图 PDF | `outputs/research_2026/current_2026_quicklook_diagnostics.pdf` |
| 数据来源记录 | `docs/data_source_log.md` |

![2026 quick-look](/Users/daiyue/Documents/Maryland/outputs/research_2026/current_2026_quicklook_diagnostics.png)

## 八、数据和文献来源

- Jiang et al. 2026, *Geophysical Research Letters*, DOI: [10.1029/2026GL123227](https://doi.org/10.1029/2026GL123227)。本地 PDF：`/Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/grl72759.pdf`。
- NOAA ERSSTv5: [NOAA NCEI ERSST](https://www.ncei.noaa.gov/products/extended-reconstructed-sst)，OPeNDAP: `https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.ersst.v5/sst.mnmean.nc`。
- NOAA OISST v2.1: [NOAA OISST](https://www.ncei.noaa.gov/products/optimum-interpolation-sst)，OPeNDAP: `https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc`。
- GPCP Monthly Precipitation: [NOAA PSL GPCP](https://psl.noaa.gov/data/gridded/data.gpcp.html)，OPeNDAP: `https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc`。
- NCEP/NCAR Reanalysis: [NOAA PSL Reanalysis](https://www.psl.noaa.gov/data/reanalysis/)，OPeNDAP files: `uwnd.sig995.mon.mean.nc` and `slp.mon.mean.nc` under NOAA PSL THREDDS.

