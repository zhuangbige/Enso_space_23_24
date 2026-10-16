#!/usr/bin/env python3
from pathlib import Path
import json, hashlib
import numpy as np,pandas as pd,xarray as xr
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/raw/godas/ro_baseline_20261014'
OUT=ROOT/'data/derived/research_2026/paper_ro_baseline_20261014'
OUT.mkdir(parents=True,exist_ok=True)

def d20(temp,z):
    # (time,level,lat,lon), interpolate first downward 20C crossing.
    crossing=(temp[:,:-1]>=20)&(temp[:,1:]<20)
    k=crossing.argmax(axis=1); exists=crossing.any(axis=1)
    t0=np.take_along_axis(temp,k[:,None],axis=1)[:,0]
    t1=np.take_along_axis(temp,(k+1)[:,None],axis=1)[:,0]
    with np.errstate(divide='ignore',invalid='ignore'):
        h=z[k]+(20-t0)/(t1-t0)*(z[k+1]-z[k])
    h=np.where(exists,h,np.nan)
    h=np.where(np.isfinite(temp[:,0])&(temp[:,0]<20),0,h)
    return h

def sst_index(path):
    with xr.open_dataset(path) as ds:
        s=ds.sst.where((abs(ds.lat)<=5)&(ds.lon>=190)&(ds.lon<=240),drop=True).sel(time=slice('1980',None)).load()
        return s.weighted(np.cos(np.deg2rad(s.lat))).mean(['lat','lon']).to_series()

def main():
    rows=[];qa={};mask0=None;grids=[]
    for year in range(1980,2027):
        file=SOURCE/f'pottmp_{year}_5S5N_120E80W.nc'
        with xr.open_dataset(file) as ds:
            # NCSS rounds outward; enforce exact definition by cell centers.
            a=ds.pottmp.where((abs(ds.lat)<=5)&(ds.lon>=120)&(ds.lon<=280),drop=True).load()
            z=ds.level.values.astype(float)
            assert a.attrs['units']=='K'
            h=d20(a.values.astype(float)-273.15,z)
            mask=np.isfinite(h)
            if mask0 is None:mask0=mask[0]
            assert np.all(mask==mask0),'ocean mask varies; diagnose before aggregation'
            w=np.cos(np.deg2rad(a.lat.values.astype(float)))[:,None]*np.ones((1,a.sizes['lon']))
            # GODAS equatorial latitude spacing is uniform (~1/3 degree).
            assert np.max(abs(np.diff(a.lat.values)-1/3))<1e-4
            weights=np.where(mask0,w,0);den=weights.sum()
            avg=np.nansum(h*weights,axis=(1,2))/den
            area=den*np.deg2rad(1/3)*np.deg2rad(1)*6371000**2
            assert abs(np.sum(np.ones_like(h[0])*weights)/den-1)<1e-14
            assert np.nanmin(h)>=0 and np.nanmax(h)<500
            for t,v in zip(pd.DatetimeIndex(a.time.values),avg):rows.append(dict(time=t,WWV=v,volume_m3=v*area))
            if year in [1980,2015,2026]:
                qa[str(year)]=dict(months=len(a.time),lat_range=a.lat.values[[0,-1]].tolist(),lon_range=a.lon.values[[0,-1]].tolist(),valid_cells=int(mask0.sum()),area_m2=area,d20_min=float(np.nanmin(h)),d20_max=float(np.nanmax(h)),last=str(a.time.values[-1]))
                grids.append(xr.DataArray(h,dims=['time','lat','lon'],coords={k:a.coords[k] for k in ['time','lat','lon']},name='D20'))
        print('computed D20',year,flush=True)
    h=pd.DataFrame(rows).set_index('time')
    old=sst_index(ROOT/'data/raw/ersstv5_sst_monthly_full.nc')
    new=sst_index(SOURCE/'ersstv5_nino34_2026.nc')
    overlap=pd.concat([old.rename('old'),new.rename('new')],axis=1).dropna()
    qa['ersst_update_overlap_max_C']=float(abs(overlap.old-overlap.new).max())
    sst=pd.concat([old.loc[old.index<new.index.min()],new]).rename('Nino34')
    result=pd.concat([sst,h],axis=1)
    result.index.name='time';result.to_csv(OUT/'raw_indices.csv')
    assert result.dropna().index.equals(pd.date_range(result.dropna().index[0],result.dropna().index[-1],freq='MS'))
    qa['latest_T']=str(sst.index[-1].date());qa['latest_H']=str(h.index[-1].date())
    (OUT/'input_QA.json').write_text(json.dumps(qa,indent=2))
    xr.concat(grids,dim='time').to_netcdf(OUT/'D20_sample_grids.nc')
    print(json.dumps(qa,indent=2),flush=True)
if __name__=='__main__':main()
