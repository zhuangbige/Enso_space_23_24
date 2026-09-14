# 2023 SSTA--OHC vertical mismatch verification

- Independent 0--300 m recomputation RMSE on stable full columns: 5.79557e-07 GJ m-2.
- Independent recomputation maximum absolute difference on stable full columns: 2.304e-06 GJ m-2.
- Independent recomputation correlation on stable full columns: 1.000000000000.
- 0--80 m plus 80--300 m closure maximum error: 1.024e-06 GJ m-2.
- OISST and harmonized SODA anomalies use the same 1982--2024 calendar-month linear baseline.
- Matched-footprint SSTA is interpolated to the SODA grid and restricted to cells with a complete 0--300 m column.

## 2023 eastern-region monthly values

| month | region | oisst_ssta_matched_ohc_footprint_c | soda_5m_ta_c | ohc_0_80_gj_m2 | ohc_80_300_gj_m2 | ohc_0_300_common_gj_m2 | ohc_0_300_original_gj_m2 | surface_positive_common_ohc_negative |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | east_140W_80W | -0.465 | -0.469 | -0.135 | -0.123 | -0.258 | -0.254 | False |
| 2 | east_140W_80W | 0.036 | -0.013 | 0.005 | -0.038 | -0.034 | -0.029 | True |
| 3 | east_140W_80W | 0.450 | 0.356 | 0.200 | 0.041 | 0.241 | 0.251 | False |
| 4 | east_140W_80W | 0.614 | 0.663 | 0.402 | 0.203 | 0.605 | 0.605 | False |
| 5 | east_140W_80W | 1.113 | 1.291 | 0.573 | 0.238 | 0.811 | 0.807 | False |
| 6 | east_140W_80W | 1.337 | 1.498 | 0.682 | 0.304 | 0.986 | 0.975 | False |
| 1 | fep_90W_80W | -0.500 | -0.500 | -0.287 | -0.068 | -0.356 | -0.371 | False |
| 2 | fep_90W_80W | 0.230 | 0.134 | -0.008 | -0.037 | -0.044 | -0.059 | True |
| 3 | fep_90W_80W | 0.980 | 0.576 | 0.435 | 0.062 | 0.497 | 0.480 | False |
| 4 | fep_90W_80W | 1.929 | 1.828 | 0.795 | 0.163 | 0.957 | 0.950 | False |
| 5 | fep_90W_80W | 1.813 | 2.107 | 0.990 | 0.312 | 1.301 | 1.303 | False |
| 6 | fep_90W_80W | 2.107 | 2.176 | 0.938 | 0.457 | 1.395 | 1.383 | False |

## Interpretation rule

A row is a region-mean sign mismatch only when matched-footprint OISST SSTA is positive and common-baseline 0--300 m OHC is negative. The 0--80 m and 80--300 m columns show whether vertical compensation causes that sign difference.
