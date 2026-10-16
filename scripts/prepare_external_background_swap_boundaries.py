"""Prepare CF SST boundary scenarios; does not launch an atmospheric/ocean model."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import xarray as xr

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/external_background_process_bridge_20261015'
SOURCE=ROOT/'data/raw/ersstv5_sst_monthly_full.nc'


def taper_axis(x,lo,hi,width=5.):
    x=np.asarray(x)
    left=np.clip((x-(lo-width))/width,0,1)
    right=np.clip(((hi+width)-x)/width,0,1)
    return (0.5-0.5*np.cos(np.pi*left))*(0.5-0.5*np.cos(np.pi*right))


def main():
    out=OUT/'boundary_inputs';out.mkdir(exist_ok=True)
    with xr.open_dataset(SOURCE,engine='h5netcdf') as ds:
        data=ds.sst.sel(time=slice('1982','2024')).sortby('lat').load()
    assert data.shape==(516,89,180)
    x=data.values.astype(float);dates=pd.DatetimeIndex(data.time.values)
    wet=np.isfinite(x).all(axis=0);mi=dates.month.to_numpy()-1
    climatology=np.stack([np.mean(x[mi==m],axis=0) for m in range(12)])
    anomaly=x-climatology[mi]
    t=np.arange(516,dtype=float);t-=t.mean()
    trend=np.einsum('t,tij->ij',t,np.where(wet,anomaly,0))/(t@t)
    residual=anomaly-t[:,None,None]*trend[None]
    lat,lon=data.lat.values,data.lon.values
    # These are frozen regional interventions, not isolated climate-mode changes.
    rect=lambda s,n,w,e: taper_axis(lat,s,n)[:,None]*taper_axis(lon,w,e)[None,:]
    a=np.maximum(rect(-20,20,40,110),rect(0,20,300,340))*wet
    # Full intervention 15--45N, 130--250E; cosine taper to 10--50N, 125--255E.
    b=rect(15,45,130,250)*wet
    assert np.max(abs(a*b))==0
    pacific_equator=(abs(lat[:,None])<=9)&(lon[None,:]>=120)&(lon[None,:]<=280)
    assert not np.any((a+b)[pacific_equator])
    target_dates=pd.date_range('2023-01-01','2024-01-01',freq='MS')
    target_ix=dates.get_indexer(target_dates);assert (target_ix>=0).all()
    base=x[target_ix];base_res=residual[target_ix]
    # Identical January/February history; replacement from March onward.
    active=np.asarray(target_dates>=pd.Timestamp('2023-03-01'),dtype=float)[:,None,None]
    fields=[base];names=['ctrl_2023'];rows=[dict(case='ctrl_2023',donor_year=2023,replace_A=False,replace_B=False)]
    audit={}
    for year in [1997,2015]:
        donor_dates=pd.date_range(f'{year}-01-01',f'{year+1}-01-01',freq='MS')
        ix=dates.get_indexer(donor_dates);assert (ix>=0).all()
        delta=residual[ix]-base_res
        donor_fields={}
        for group,mask in [('a',a),('b',b),('ab',a+b)]:
            # Keep recipient background/trend and replace same-calendar-month residual only.
            new=base+np.where(wet,delta,0)*mask[None]*active
            name=f'{group}_donor_{year}'
            fields.append(new);names.append(name);donor_fields[group]=new
            rows.append(dict(case=name,donor_year=year,replace_A=group in ['a','ab'],replace_B=group in ['b','ab']))
            d=new-base
            assert np.nanmax(abs(d[:2]))==0
            assert np.nanmax(abs(d[:,pacific_equator]))==0
            assert np.nanmax(abs(d[:,mask==0]))==0
            assert np.array_equal(np.isfinite(new),np.isfinite(base))
            audit[name]={'max_abs_change_K':float(np.nanmax(abs(d))),
                         'unchanged_tropical_pacific':True,'unchanged_jan_feb':True}
        err=float(np.nanmax(abs(donor_fields['ab']-donor_fields['a']-donor_fields['b']+base)))
        assert err<1e-10
        audit[f'factorial_{year}_identity_error_K']=err
    dataset=xr.Dataset(
        {'sst':(('case','time','lat','lon'),np.stack(fields)+273.15),
         'sst_change':(('case','time','lat','lon'),np.stack(fields)-base),
         'mask_A':(('lat','lon'),a),'mask_B':(('lat','lon'),b)},
        coords={'case':names,'time':target_dates,'lat':lat,'lon':lon},
        attrs={'title':'Prescribed-SST candidate experiments; no model integrations performed',
               'source':str(SOURCE),'anomaly_reference':'1982-2024 calendar-month means and linear trend',
               'recipient':'2023 background and trend preserved at every grid point',
               'A':'TNA plus tropical Indian Ocean, cosine-tapered regional SST replacement',
               'B':'Extratropical North Pacific regional SST replacement, not a pure PMM or ENP mode',
               'months':'January-February identical; March onward replacement; following January is interpolation guard',
               'land_policy':'Source missing ocean/land cells remain missing; requires model-specific land fill and regridding',
               'scope':'Atmospheric forcing only; prescribed Pacific SST cannot respond, so this is not an ENSO ocean experiment'})
    dataset.sst.attrs={'units':'K','standard_name':'sea_surface_temperature'}
    dataset.sst_change.attrs={'units':'K','long_name':'SST scenario minus 2023 control'}
    dataset.lat.attrs={'units':'degrees_north'};dataset.lon.attrs={'units':'degrees_east'}
    path=out/'sst_background_swap_scenarios.nc'
    dataset.to_netcdf(path,engine='h5netcdf',encoding={v:{'zlib':True,'complevel':2} for v in dataset.data_vars})
    with xr.open_dataset(path,engine='h5netcdf') as check:
        assert check.sizes==dataset.sizes
        assert float(abs(check.sst-dataset.sst).max())==0
    pd.DataFrame(rows).to_csv(out/'experiment_matrix.csv',index=False)
    audit.update(cases=7,months=13,model_runs_completed=0,
                 native_grid_only=True,model_adapter_complete=False)
    (out/'boundary_validation.json').write_text(json.dumps(audit,indent=2))
    with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    (out/'sha256.txt').write_text(f'{sha}  {path.name}\n')
    print(json.dumps(audit,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
