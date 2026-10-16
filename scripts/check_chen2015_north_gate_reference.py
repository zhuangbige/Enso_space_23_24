"""Independent narrow-section cache check of the new native-layer two terms."""
import numpy as np,pandas as pd,xarray as xr,json
import analyze_chen2015_reanalysis as a
root=a.ROOT/'data/raw/chen2015_linear_transport_20261014'
# Independently average already-interpolated narrow sections from the CURRENT
# official annual inputs; the full-field path averages before interpolation.
acc={k:[] for k in ['temp','salt','flow']}
for year in range(1980,2023):
 p=np.load(a.RAW/f'soda3_sigma26_inputs_{year}.npz')
 x={k:p[k] for k in ['temp','salt','v','lat_t','lon_t','lat_u','lon_u']}
 g=a.section(x,'v',5,220,280)
 for key in acc:acc[key].append(g[key][:5,:20].astype('float64'))
bmean={key:np.mean(np.stack(vals),axis=0) for key,vals in acc.items()};rows=[]
for y in [2016,2024]:
 d=a.load_inputs(y);g=a.section(d,'v',5,220,280)
 for k in ['temp','salt','flow']:g[k]=g[k][:5,:20].astype('float64')
 b={**g,**bmean}
 for geometry,src in [('instantaneous_sigma26',g),('climatological_sigma26',b)]:
  q,qi,z,w,info=a.integrate_gate(src,d['depth'][:20],d['layer_bottom'][:20]);t1=b['flow']*(g['temp']-b['temp']);t2=(g['flow']-b['flow'])*b['temp'];v1=np.nansum(t1*w,axis=(1,2))*a.RHO*a.CP/1e15;v2=np.nansum(t2*w,axis=(1,2))*a.RHO*a.CP/1e15
  dates=pd.to_datetime([f'{y}-{m:02d}-15' for m in range(1,6)]);seconds=(dates-dates[0]).total_seconds().to_numpy()
  for col,x in [('vbar_Tprime_pw',v1),('vprime_Tbar_pw',v2),('linear_sum_pw',v1+v2)]:
   rows.append({'year':y,'geometry':geometry,'term':col,'Jan15_May15_zj':np.trapezoid(x,seconds)/1e6,'full_Jan_May_zj':np.sum(x*dates.days_in_month*86400)/1e6})
df=pd.DataFrame(rows);df.to_csv(a.OUT/'independent_north_gate_reference.csv',index=False);print(df.to_string(index=False))
