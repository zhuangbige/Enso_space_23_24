"""Isolate the unspecified pentad interpolation choice, holding periods fixed."""
import pandas as pd,numpy as np,json
import run_paper_ro_pmm as r
import reproduce_manuscript_fig4 as fig4
raw,p,clim=r.load();raw=raw.loc[:'2025-04-01'];p=p.loc[:'2025-04-01']
a,meta=r.prepare(raw,p,'2002-01-01','2024-12-01',True,trend_end='2025-04-01');a=a[r.V].loc['2002-01':'2025-04']
rows=[];forecasts=[];models={}
for interpolation in ['linear','cubic']:
 for method in ['perturb2','exact']:
  name=interpolation+'_'+method;m=r.slim.fit(a.loc['2002':'2024'],method=method,interpolation=interpolation);models[name]=m
  for year in fig4.YEARS:
   pp=[];tt=[]
   for month in range(2,7):
    ini=pd.Timestamp(year,month,1);dates=pd.date_range(ini,periods=13,freq='MS');v=r.slim.predict(m,a.loc[ini].to_numpy(),month)
    for lead in range(1,10):
     pp.append(v[lead,0]);tt.append(a.Nino34.loc[dates[lead]])
    for lead in range(13):
     if dates[lead]>a.index[-1]:continue
     forecasts.append(dict(configuration=name,year=year,month=month,init=ini,target=dates[lead],lead=lead,T=v[lead,0],H=v[lead,1]))
   rows.append(dict(configuration=name,year=year,r=np.corrcoef(pp,tt)[0,1],RMSE=np.sqrt(np.mean((np.array(pp)-tt)**2)),paper_r=fig4.PRINTED[fig4.YEARS.index(year)]))
s=pd.DataFrame(rows);s.to_csv(fig4.OUT/'interpolation_event_scores.csv',index=False);pd.DataFrame(forecasts).to_csv(fig4.OUT/'interpolation_forecasts.csv',index=False)
(fig4.OUT/'interpolation_models.json').write_text(json.dumps(models,default=r.jsonable,indent=2))
for name,g in s.groupby('configuration'):print(name,'2015',g[g.year.eq(2015)].r.iloc[0],'2002',g[g.year.eq(2002)].r.iloc[0],'MAE',abs(g.r-g.paper_r).mean(),'pattern',g[['r','paper_r']].corr().iloc[0,1])
