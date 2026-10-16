"""Approximate digitization for auditing the manuscript's black observed curve.
Pixel-derived values are diagnostics, never model training data or rescaling targets.
"""
from pathlib import Path
import numpy as np,pandas as pd
from PIL import Image
import run_paper_ro_pmm as r
ROOT=r.ROOT;OUT=ROOT/'outputs/research_2026/manuscript_RO_exact_period_20261014';OUT.mkdir(parents=True,exist_ok=True)
im=np.asarray(Image.open(ROOT/'tmp/pdfs/manuscript_audit_20261014/original_fig4_Image70.jpg').convert('RGB')).astype(float)
# Calibrated against visible Jan 2002/2025 ticks and -2,-1,0,1,2,3 ticks.
dates=pd.date_range('2002-01-01','2025-04-01',freq='MS');pixels=145+np.arange(len(dates))*(1190-145)/(23*12)
vals=[]
for x in pixels:
 col=im[78:350,int(round(x))]
 gray=(col.max(axis=1)-col.min(axis=1)<12)&(col.mean(axis=1)<85)
 ys=np.arange(78,350)
 gray &= (abs(ys-235)>3)&(abs(ys-208)>3)&(abs(ys-261)>3)
 cand=ys[gray]
 vals.append((235-np.median(cand))/53.5 if len(cand) else np.nan)
ref=pd.Series(vals,index=dates,name='figure_observation_approx_C')
raw,p,clim=r.load();a0=raw-clim.loc[raw.index.month].set_axis(raw.index)
a,meta=r.prepare(raw,p,'2002-01-01','2024-12-01',True,trend_end='2025-04-01')
cases={'raw_anomaly_monthly':a0.Nino34,'raw_anomaly_3mo':a0.Nino34.rolling(3,center=True).mean(),
       'detrend_2002_2025_monthly':a.Nino34,'detrend_2002_2025_3mo':a.Nino34.rolling(3,center=True).mean()}
allseries=pd.concat([ref,pd.DataFrame(cases)],axis=1).loc[dates]
rows=[]
for name in cases:
 q=allseries[[ref.name,name]].dropna();diff=q[ref.name]-q[name]
 t=r.slim.decimal_time(q.index);A=np.column_stack([np.ones(len(t)),t-2013]);beta=np.linalg.lstsq(A,diff,rcond=None)[0]
 rows.append(dict(case=name,n=len(q),RMSE_against_digitized=float(np.sqrt(np.mean(diff**2))),mean_diff=diff.mean(),difference_trend_per_year=beta[1],residual_after_removing_difference_trend=float(np.std(diff-A@beta))))
allseries.to_csv(OUT/'digitized_observed_curve_diagnostic.csv');pd.DataFrame(rows).to_csv(OUT/'observed_curve_diagnostic_scores.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False))
print(allseries.loc['2015-09':'2016-02'].to_string())
