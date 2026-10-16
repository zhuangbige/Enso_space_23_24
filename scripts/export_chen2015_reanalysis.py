from pathlib import Path
import json,numpy as np,pandas as pd,xarray as xr
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/research_2026/chen2015_reanalysis_20261014'
raw=pd.read_csv(OUT/'monthly_absolute.csv',parse_dates=['time']);anom=pd.read_csv(OUT/'monthly_anomalies.csv',parse_dates=['time'])
boxes=['chen_basin','west','central','east'];gates=[c[:-5] for c in raw.columns if c.endswith('_q_sv')]
a=np.load(OUT/'d26_1980.npz');depth=np.concatenate([np.load(OUT/f'd26_{y}.npz')['d26'] for y in range(1980,2025)],axis=0);shelf=np.concatenate([np.load(OUT/f'd26_{y}.npz')['shelf'] for y in range(1980,2025)],axis=0)
clim=[]
for m in range(12):
 a0=depth[:43*12][m::12];n=np.isfinite(a0).sum(axis=0);clim.append(np.divide(np.nansum(a0,axis=0),n,out=np.full_like(a0[0],np.nan),where=n>0))
clim=np.stack(clim)
d=xr.Dataset({'d26':(('time','lat','lon'),depth),'d26_anomaly':(('time','lat','lon'),depth-clim[np.arange(540)%12]),'d26_climatology':(('month','lat','lon'),clim),'bottom_limited':(('time','lat','lon'),shelf.astype('int8')),
'wwv26':(('time','box'),raw[[b+'_wwv_m3' for b in boxes]].to_numpy()),'wwv26_anomaly':(('time','box'),anom[[b+'_wwv_m3' for b in boxes]].to_numpy()),
'volume_transport':(('time','gate'),raw[[g+'_q_sv' for g in gates]].to_numpy()),'volume_transport_anomaly':(('time','gate'),anom[[g+'_q_sv' for g in gates]].to_numpy()),
'surface_heat_flux_anomaly':(('time','box'),anom[[b+'_surface_pw' for b in boxes]].to_numpy())},coords={'time':raw.time,'lat':a['lat'],'lon':a['lon'],'month':range(1,13),'box':boxes,'gate':gates},attrs={'method':'Chen et al. (2015) sigma0=26 definition applied to SODA3.15.2; regional Maryland extension separately identified','baseline':'1980-2022 calendar-month mean, unfiltered, no detrending','time_assignment':'Official annual filename year + 12 monthly-record order, represented at day 15; see source_calendar_QA.csv','density':'TEOS-10 sigma0 from salinity and potential temperature','coordinates':'Includes tracer halo needed to interpolate regional and basin boundaries','vertical_interfaces':'Common valid 2024 sw_ocean interfaces; historical sw_ocean is not a layer-edge coordinate','closure':'No forced zero horizontal volume convergence; unresolved terms are not separately identified physical pathways'})
for v in ['d26','d26_anomaly','d26_climatology']:d[v].attrs['units']='m'
for v in ['wwv26','wwv26_anomaly']:d[v].attrs['units']='m3'
for v in ['volume_transport','volume_transport_anomaly']:d[v].attrs.update(units='Sv',positive='northward on meridional-velocity sections, eastward on zonal-velocity sections')
d.surface_heat_flux_anomaly.attrs.update(units='PW',positive='into ocean');d.bottom_limited.attrs.update(flag_values=[0,1],flag_meanings='density_surface_resolved_or_land bottom_limited_warm_column')
enc={v:{'zlib':True,'complevel':4} for v in d.data_vars};p=OUT/'WWV26_monthly_1980_2024.nc';d.to_netcdf(p,encoding=enc)
with xr.open_dataset(p) as check:
 np.testing.assert_allclose(check.wwv26.values,d.wwv26.values);assert check.sizes['time']==540
print('NetCDF verified',p,p.stat().st_size)
