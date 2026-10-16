#!/usr/bin/env python3
"""Audit the unexpectedly small March 2015 XRO forecast. No outcome tuning."""
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
import xarray as xr
import run_xro_npmm_ablation as exp

ROOT=exp.ROOT
OUT=exp.OUT/'audit_20261014'
OUT.mkdir(exist_ok=True)
raw=pd.read_csv(exp.OUT/'raw_xro_indices_1980_2026.csv',index_col=0,parse_dates=True)
pmel=pd.read_csv(ROOT/'data/raw/godas/authoritative_recharge_sections/pmel_tao_wwv.dat',sep=r'\s+',skiprows=6,names=['date','total','official_anomaly'])
pmel.index=pd.to_datetime(pmel.date.astype(str),format='%Y%m')
reference=xr.open_dataset('/Users/daiyue/Documents/New project_XRO/XRO/data/XRO_indices_oras5.nc').drop_vars('month').to_dataframe()[exp.VARS].astype(float)

rows=[]
summary=[]
qa={}
def run_case(case,a,train_end='2014-12',start='1980-01',interpretation='past-only local preprocessing'):
    train=a.loc[start:train_end]
    for name,variables in {'full':exp.VARS,'no_NPMM':[v for v in exp.VARS if v!='NPMM']}.items():
        fit=exp.fit_model(train[variables])
        for month in [1,3,5]:
            ini=pd.Timestamp(2015,month,1)
            fc=exp.forecast(fit,a.loc[ini,variables].to_numpy(),month)
            target=pd.date_range(ini,periods=13,freq='MS')
            truth=a.reindex(target)
            for l,t in enumerate(target):
                rows.append(dict(case=case,model=name,month=month,lead=l,target=t,
                                 T=fc[l,0],H=fc[l,1],obs_T=truth.Nino34.iloc[l],obs_H=truth.WWV.iloc[l],
                                 train_start=start,train_end=train_end,interpretation=interpretation))
            summary.append(dict(case=case,model=name,month=month,T0=fc[0,0],H0=fc[0,1],
                                P0=a.loc[ini,'NPMM'],T_Nov=fc[11-month,0],obs_T_Nov=a.loc['2015-11-01','Nino34'],
                                T_RMSE=np.sqrt(np.mean((fc[1:,0]-truth.Nino34.iloc[1:].to_numpy())**2)),
                                H_RMSE=np.sqrt(np.mean((fc[1:,1]-truth.WWV.iloc[1:].to_numpy())**2))))
        if case=='quadratic_all' and name=='full':
            # Same anomalies with H measured in 100x larger units, refit and
            # convert the forecast back: should not change the ENSO trajectory.
            scaled=train.copy(); scaled.WWV*=100
            sf=exp.fit_model(scaled)
            ini=a.loc['2015-03-01',variables].to_numpy().copy()
            base=exp.forecast(fit,ini,3)
            ini[1]*=100
            sfc=exp.forecast(sf,ini,3); sfc[:,1]/=100
            qa['H_units_rescaling_max_difference']=float(np.max(abs(base-sfc)))
            assert np.allclose(base,sfc,atol=1e-8)
    print(case,flush=True)

variants={f'{name}_all':exp.anomalies(raw,2015,order=order) for name,order in [('climatology',0),('linear',1),('quadratic',2)]}
for case,a in variants.items():
    run_case(case,a)
# Change only H detrending relative to the original quadratic run to isolate it.
for order,label in [(0,'climatology'),(1,'linear')]:
    a=variants['quadratic_all'].copy()
    a.WWV=variants[label+'_all'].WWV
    run_case('quadratic_SST_'+label+'_H',a)
run_case('ORAS5_reference_fit_through_2014',reference,interpretation='Already preprocessed official sample: future preprocessing cannot be excluded; benchmark only')
run_case('ORAS5_cookbook_fit_through_2022',reference,train_end='2022-12',start='1979-01',interpretation='IN-SAMPLE cookbook diagnostic; 2015 is in training, NOT a forecast skill estimate')
for order,label in [(1,'linear'),(2,'quadratic')]:
    # Matched fold preprocessing as an additional diagnostic. The source file
    # is already processed: these are not recovered raw ORAS5 observations.
    a=exp.anomalies(reference.loc['1980-01':],2015,order=order)
    run_case('ORAS5_reprocessed_'+label,a,interpretation='Official preprocessed sample, processed again on the past fold; diagnostic only')

pd.DataFrame(rows).to_csv(OUT/'preprocessing_and_data_forecasts.csv',index=False)
s=pd.DataFrame(summary);s.to_csv(OUT/'preprocessing_and_data_scores.csv',index=False)
inputs=pd.DataFrame({'PMEL_published_WWV':pmel.official_anomaly/1e14})
for case,a in variants.items():
    inputs[case+'_H']=a.WWV
    inputs[case+'_T']=a.Nino34
inputs.loc['2014':'2016'].to_csv(OUT/'anomaly_baseline_comparison.csv')
(OUT/'numerical_audit.json').write_text(json.dumps(qa,indent=2))
print(s[(s.month==3)&(s.model=='full')].to_string(index=False))
print(qa)
