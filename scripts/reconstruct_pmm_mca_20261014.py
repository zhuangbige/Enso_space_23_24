"""Fixed 1950–2005 R1 MCA patterns; separately calibrated ERA5 projections.

Provider method: https://www.aos.wisc.edu/dvimont/MModes/Background.html
All fitted spatial/preprocessing/calibration parameters end in 2005. Monthly
projections are unsmoothed, so an initialization never needs the following month.
ERA5-derived indices are a research reconstruction, not official PMM updates.
"""
from pathlib import Path
import argparse
import json
import os
import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree
from scipy.linalg import svd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/pmm_mca_reconstruction_20261014'
OUT = ROOT / 'outputs/research_2026/pmm_mca_reconstruction_20261014'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/ro_pmm_mpl'))


def official():
    p = pd.read_csv(ROOT/'data/raw/ro_pmm_2026_update_20261014/PMM_uw.txt', sep=r'\s+')
    p.index = pd.to_datetime(dict(year=p.Year, month=p.Mo, day=1))
    return p[['SST','Wind']]


def r1_fields():
    ds = xr.merge([xr.open_dataset(RAW/name)[[var]].load() for var,name in
        [('skt','r1_skt.sfc.mon.mean.nc'),('uwnd','r1_uwnd.10m.mon.mean.nc'),
         ('vwnd','r1_vwnd.10m.mon.mean.nc')]])
    ds = ds.rename({'skt':'sst','uwnd':'u10','vwnd':'v10'})
    assert ds.sst.attrs['units'] in ['K','degK','degC']
    if ds.sst.attrs['units'] != 'degC': ds['sst'] = ds.sst - 273.15
    mask = xr.open_dataset(RAW/'r1_land.sfc.gauss.nc').land.squeeze(drop=True).load()
    # Retain complete global 2-latitude by 3-longitude blocks only.
    iy = np.where(np.isin(mask.lat.values, ds.lat.values))[0]
    ix = np.where(np.isin(mask.lon.values, ds.lon.values))[0]
    iy = iy[(iy >= int(np.ceil(iy.min()/2)*2)) & (iy < ((iy.max()+1)//2)*2)]
    ix = ix[(ix >= int(np.ceil(ix.min()/3)*3)) & (ix < ((ix.max()+1)//3)*3)]
    ds = ds.sel(lat=mask.lat.values[iy], lon=mask.lon.values[ix])
    ocean = mask.sel(lat=ds.lat, lon=ds.lon) < .5
    return ds, ocean


def era5_fields(template):
    cache = RAW/'era5_on_r1_grid_1950_2026.nc'
    if cache.exists(): return xr.open_dataset(cache).load()
    parts = []
    for month in range(1,13):
        file = RAW/f'era5_sst_uv10_month{month:02d}_1950_2026.grib'
        assert file.exists(), file
        import cfgrib
        groups = cfgrib.open_datasets(str(file), backend_kwargs={'indexpath':''})
        d = xr.merge([g for g in groups], compat='no_conflicts')
        d = d.rename({'latitude':'lat','longitude':'lon'})
        d = d.assign_coords(lon=d.lon % 360).sortby('lon').sortby('lat')
        # Some global products repeat the cyclic longitude endpoint.
        _, ind = np.unique(d.lon.values, return_index=True); d = d.isel(lon=ind)
        d = d.sel(lon=slice(168,277))
        times = pd.DatetimeIndex(d.time.values).to_period('M').to_timestamp()
        assert (times.month == month).all() and times.is_unique
        d = d.assign_coords(time=times)[['sst','u10','v10']].load()
        for v in d:
            d[v] = d[v].transpose('time','lat','lon')
        assert d.sst.attrs['units'] == 'K'
        d['sst'] = d.sst - 273.15
        # ERA5 SST is missing over land. Fill those cells by the nearest ocean
        # value before interpolation; the fixed R1 ocean mask is applied later.
        # This handles different coastline grids, not missing ocean observations.
        arr = d.sst.values.copy()
        valid = np.isfinite(arr).all(axis=0)
        assert np.all(np.isfinite(arr) == valid[None]), 'changing SST mask'
        lat2,lon2 = np.meshgrid(d.lat.values,d.lon.values,indexing='ij')
        points = np.column_stack([lat2.ravel(),lon2.ravel()])
        good = np.where(valid.ravel())[0]; bad = np.where(~valid.ravel())[0]
        near = cKDTree(points[good]).query(points[bad])[1]
        flat = arr.reshape(len(times),-1); flat[:,bad] = flat[:,good[near]]
        d['sst'].values[:] = flat.reshape(arr.shape)
        out = d.interp(lat=template.lat,lon=template.lon).drop_vars(
            [k for k in d.coords if k not in ['time','lat','lon']], errors='ignore')
        parts.append(out)
        print('read ERA5 month', month, flush=True)
    result = xr.concat(parts,dim='time').sortby('time')
    assert result.time.to_index().equals(pd.date_range('1950-01-01','2026-09-01',freq='MS'))
    for v in result: assert np.isfinite(result[v]).all()
    result.to_netcdf(cache)
    return result


def ersst_fields(template):
    """Use continuous ERSSTv5 to extend the SST side of the frozen MCA mode."""
    ds=xr.open_dataset(RAW/'ersstv5_pmm_sst_1950_2026.nc')[['sst']].load()
    assert ds.sst.attrs['units'] in ['degC','degree_C','degrees_C']
    ds=ds.sortby('lat').sortby('lon')
    x=ds.sst.values.copy();goodmask=np.isfinite(x).all(axis=0)
    assert np.all(np.isfinite(x)==goodmask[None]),'changing ERSST ocean mask'
    lat,lon=np.meshgrid(ds.lat.values,ds.lon.values,indexing='ij')
    pts=np.column_stack([lat.ravel(),lon.ravel()])
    good=np.where(goodmask.ravel())[0];bad=np.where(~goodmask.ravel())[0]
    near=cKDTree(pts[good]).query(pts[bad])[1]
    xx=x.reshape(len(x),-1);xx[:,bad]=xx[:,good[near]]
    ds['sst'].values[:]=xx.reshape(x.shape)
    return ds.interp(lat=template.lat,lon=template.lon)


def coarse_fields(ds, ocean):
    s = ds.sst.where(ocean)
    cti = s.where((abs(ds.lat)<=6)&(ds.lon>=180)&(ds.lon<=270),drop=True)
    cti = cti.weighted(np.cos(np.deg2rad(cti.lat))).mean(['lat','lon']).values
    coarse = ds.where(ocean).coarsen(lat=2,lon=3,boundary='exact').mean()
    coarse = coarse.where((coarse.lat>=-21)&(coarse.lat<=32)&
                          (coarse.lon>=175)&(coarse.lon<=265), drop=True)
    fixed = np.isfinite(coarse.sst.isel(time=0).values)
    vals = [coarse[v].values[:,fixed].astype(float) for v in ['sst','u10','v10'] if v in coarse]
    assert all(np.isfinite(v).all() for v in vals)
    lat2 = np.broadcast_to(coarse.lat.values[:,None],fixed.shape)[fixed]
    weight = np.sqrt(np.cos(np.deg2rad(lat2)))
    return pd.DatetimeIndex(ds.time.values), vals, cti, weight, coarse, fixed


def residualize(values, cti, times):
    train = (times.year>=1950)&(times.year<=2005)
    combined = np.column_stack([cti, *values])
    month = times.month.to_numpy()-1
    clim = np.stack([combined[train & (month==i)].mean(axis=0) for i in range(12)])
    x = combined-clim[month]
    tt = times.year.to_numpy()+(times.month.to_numpy()-.5)/12
    center = tt[train].mean()
    design = np.column_stack([np.ones(len(tt)),tt-center])
    trend = np.linalg.lstsq(design[train],x[train],rcond=None)[0]
    x -= design@trend
    # Centered smoothing is confined to the 1950–2005 mode-estimation sample.
    smooth = pd.DataFrame(x[train]).rolling(3,center=True,min_periods=3).mean().dropna().to_numpy()
    reg = np.linalg.lstsq(np.column_stack([np.ones(len(smooth)),smooth[:,0]]),smooth[:,1:],rcond=None)[0]
    smooth = smooth[:,1:]-np.column_stack([np.ones(len(smooth)),smooth[:,0]])@reg
    unsmoothed = x[:,1:]-np.column_stack([np.ones(len(x)),x[:,0]])@reg
    n = values[0].shape[1]
    return unsmoothed[:,:n],unsmoothed[:,n:],smooth[:,:n],smooth[:,n:],dict(
        climatology=clim,trend=trend,time_center=center,cti_regression=reg,
        reference_start='1950-01',reference_end='2005-12',smoothed_training_n=len(smooth))


def calibrate(scores, times, observed):
    ref = observed.reindex(times).to_numpy()
    train = (times.year<=2005)&np.isfinite(ref).all(axis=1)
    coef = []
    for j in range(scores.shape[1]):
        a = np.column_stack([np.ones(len(scores)),scores[:,j]])
        beta = np.linalg.lstsq(a[train],ref[train,j],rcond=None)[0]
        coef.append(beta)
    coef = np.asarray(coef)
    return scores*coef[:,1]+coef[:,0],coef


def diagnostics(frame, observed, source):
    a = frame.join(observed,lsuffix='_reconstruction',rsuffix='_official')
    rows=[]
    for name,lo,hi in [('calibration_1950_2005','1950','2005'),
                        ('heldout_2006_2024','2006','2024'),
                        ('heldout_2025_2026Feb','2025','2026-02')]:
        sub = a.loc[lo:hi].dropna()
        for v in frame.columns:
            x,y=sub[v+'_reconstruction'].values,sub[v+'_official'].values
            e=x-y
            rows.append(dict(source=source,period=name,component=v,n=len(x),
                r=float(np.corrcoef(x,y)[0,1]),RMSE=float(np.sqrt(np.mean(e**2))),
                bias=float(e.mean()),normalized_RMSE=float(np.sqrt(np.mean(e**2))/y.std()),
                sign_agreement=float(np.mean(np.sign(x)==np.sign(y)))))
    return rows


def save_npz(path, **items): np.savez_compressed(path, **items)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--r1-only',action='store_true')
    parser.add_argument('--extension',choices=['ersst','era5'],default='ersst');args=parser.parse_args()
    obs=official();r1,ocean=r1_fields()
    times,values,cti,w,coarse,mask=coarse_fields(r1,ocean)
    x,y,xs,ys,pre=residualize(values,cti,times)
    ww=np.tile(w,2)
    covariance=(xs*w).T@(ys*ww)/(len(xs)-1)
    u,s,vt=svd(covariance,full_matrices=False)
    # A single sign convention applies to both sides of the coupled mode.
    orient=np.sign(np.corrcoef((x*w)@u[:,0],obs.reindex(times).SST)[0,1])
    mode_sst=u[:,0]*orient;mode_wind=vt[0]*orient
    projected=np.column_stack([(x*w)@mode_sst,(y*ww)@mode_wind])
    p,cal=calibrate(projected,times,obs)
    fr=pd.DataFrame(p,index=times,columns=['SST','Wind']);fr.index.name='time'
    fr.to_csv(OUT/'r1_mca_monthly_reconstruction.csv')
    qa=dict(mode_reference='1950-2005',covariance_fraction=float(s[0]**2/np.sum(s*s)),
        second_to_first_singular_value=float(s[1]/s[0]),ocean_grid_points=int(mask.sum()),
        actual_lat_centers=coarse.lat.values.tolist(),actual_lon_centers=coarse.lon.values.tolist(),
        R1_latest=str(times[-1].date()),projection_smoothing=False,
        calibration_end='2005-12',source_switch='NCEP/NCAR R1 to ERA5',
        caveat='Research reconstruction; original-source R1 stopped in March 2026. Not official PMM.')
    save_npz(OUT/'fixed_r1_mca_mode_1950_2005.npz',sst_mode=mode_sst,wind_mode=mode_wind,
        latitude=coarse.lat.values,longitude=coarse.lon.values,ocean_mask=mask,weight=w,
        singular_values=s,calibration=cal,**pre)
    diag=diagnostics(fr,obs,'R1_original_source')
    full=fr.add_prefix('R1_').join(obs.add_prefix('official_'),how='outer')
    if not args.r1_only:
        era=era5_fields(r1) if args.extension=='era5' else ersst_fields(r1)
        te,vals,ce,we,coe,me=coarse_fields(era,ocean)
        np.testing.assert_array_equal(me,mask);np.testing.assert_allclose(we,w)
        ex,ey,_,_,epre=residualize(vals,ce,te)
        scores=np.column_stack([(ex*w)@mode_sst,(ey*ww)@mode_wind]) if args.extension=='era5' else ((ex*w)@mode_sst)[:,None]
        pe,ecal=calibrate(scores,te,obs)
        label='ERA5' if args.extension=='era5' else 'ERSSTv5'
        columns=['SST','Wind'] if args.extension=='era5' else ['SST']
        fe=pd.DataFrame(pe,index=te,columns=columns);fe.index.name='time'
        fe.to_csv(OUT/f'{args.extension}_fixed_r1_mca_monthly_reconstruction.csv')
        save_npz(OUT/f'{args.extension}_projection_preprocessing_1950_2005.npz',calibration=ecal,**epre)
        diag+=diagnostics(fe,obs,label+'_fixed_R1_mode')
        full=full.join(fe.add_prefix(label+'_'),how='outer')
        qa[label+'_latest']=str(te[-1].date())
        qa['source_switch']='NCEP/NCAR R1 to '+label
        qa['extended_components']=columns
    full.to_csv(OUT/'official_and_reconstructed_pmm.csv')
    dd=pd.DataFrame(diag);dd.to_csv(OUT/'historical_validation.csv',index=False)
    (OUT/'reconstruction_QA.json').write_text(json.dumps(qa,indent=2))
    print(dd.to_string(index=False),flush=True)
    print(full.loc['2026'].to_string(),flush=True)


if __name__=='__main__': main()
