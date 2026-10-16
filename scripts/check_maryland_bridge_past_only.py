"""Separate past-only sensitivity; never replaces the authorized manuscript fit."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'tmp/iri_comparison_mpl'))
import json
import numpy as np
import pandas as pd
import paper_ro_slim as slim
import run_paper_ro_pmm as base
from analyze_2023_forecast_maryland_bridge import OUT, NEW, V, metric


def main():
    raw=pd.read_csv(NEW/'observed_raw_indices.csv',index_col=0,parse_dates=True)[V]
    p=pd.read_csv(ROOT/'data/raw/ro_pmm_2026_update_20261014/PMM_uw.txt',sep=r'\s+')
    p.index=pd.to_datetime(dict(year=p.Year,month=p.Mo,day=1))
    p=p[['SST','Wind']].rename(columns={'SST':'PMM_SST','Wind':'PMM_wind'})
    clim=raw.loc['1991':'2020'].groupby(raw.loc['1991':'2020'].index.month).mean()
    obs=(raw-clim.reindex(raw.index.month).set_axis(raw.index))
    obs_season=obs.Nino34.rolling(3,center=True,min_periods=3).mean()
    rows=[];scores=[];models={}
    for year in [2015,2023]:
        for start in [2002,1982]:
            # Climatology, detrending and PMM centering are estimated only before event year.
            a,meta=base.prepare(raw,p,f'{start}-01-01',f'{year-1}-12-01',paper=False)
            protocol=f'past_{start}_{year-1}'
            models[protocol]=dict(preprocessing=meta,fits={})
            for name,cols in [('RO',V),('RO_SST',V+['PMM_SST'])]:
                model=slim.fit(a.loc[f'{start}':f'{year-1}',cols])
                models[protocol]['fits'][name]=model
                preds=[];truth=[];spred=[];struth=[]
                for month in range(2,7):
                    init=pd.Timestamp(year,month,1);dates=pd.date_range(init,periods=10,freq='MS')
                    initial=a.loc[init,cols].to_numpy()
                    f=slim.predict(model,initial,month,months=9)
                    np.testing.assert_allclose(f[0],initial,atol=1e-12)
                    restored=base.restore(f,dates,meta)
                    ssta=restored[:,0]-clim.Nino34.reindex(dates.month).to_numpy()
                    truth_m=obs.Nino34.reindex(dates).to_numpy()
                    preds.extend(ssta[1:]);truth.extend(truth_m[1:])
                    smooth=pd.Series(ssta,index=dates).rolling(3,center=True,min_periods=3).mean().iloc[1:6]
                    spred.extend(smooth);struth.extend(obs_season.reindex(smooth.index))
                    for lead,date in enumerate(dates):
                        rows.append(dict(year=year,protocol=protocol,model=name,init=init,target=date,
                                         lead=lead,SSTA=ssta[lead],obs_SSTA=truth_m[lead]))
                for sample,pr,ob in [('monthly_leads_1_9',preds,truth),('season_center_leads_1_5',spred,struth)]:
                    scores.append(dict(year=year,protocol=protocol,model=name,sample=sample,
                                       **metric(np.array(pr),np.array(ob))))
    pd.DataFrame(rows).to_csv(OUT/'past_only_sensitivity_forecasts.csv',index=False)
    s=pd.DataFrame(scores);s.to_csv(OUT/'past_only_sensitivity_scores.csv',index=False)
    (OUT/'past_only_sensitivity_models.json').write_text(json.dumps(models,default=base.jsonable,indent=2))
    print(s[s['sample'].eq('season_center_leads_1_5')].to_string(index=False))


if __name__=='__main__':main()
