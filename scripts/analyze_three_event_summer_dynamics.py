#!/usr/bin/env python3
"""Finite, observation-constrained summer-current diagnosis; no fitted model."""
from pathlib import Path
import argparse, gc, hashlib, json
import numpy as np
import pandas as pd
import gsw
import xarray as xr

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/three_event_summer_current_dynamics_20261015'
RAW=ROOT/'data/raw/chen2015_reanalysis_20261014'
OLD=ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015'
DATES=pd.date_range('1982-01-01','2024-12-01',freq='MS')
MID=DATES+pd.Timedelta(days=14)
SEC=(MID-MID[0]).total_seconds().to_numpy()
MI=DATES.month.to_numpy()-1
EVENTS=(1997,2015,2023)
R=6371000.;RHO=1025.;G=9.81;OMEGA=7.292115e-5;MONTH=365.25/12*86400
MOM=['wind','pressure_ssh','pressure_density','coriolis','horizontal_advection','metric']
ADV=['mean_u_Tprime','u_prime_meanT','mean_v_Tprime','v_prime_meanT','nonlinear_hadv']

def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda a:a.item() if isinstance(a,np.generic) else a.tolist() if isinstance(a,np.ndarray) else str(a)))

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def climate(a):
    return np.stack([np.mean(a[MI==i],axis=0) for i in range(12)])

def anomalies(a):return a-climate(a)[MI]

def detrend(a):
    x=np.arange(len(DATES),dtype=float);x-=x.mean()
    return a-x.reshape((-1,)+(1,)*(a.ndim-1))*np.tensordot(x,a,axes=(0,0))/(x@x)

def gradient(a,lat,lon):
    shape=(1,)*(a.ndim-2)+(len(lat),1)
    dx=np.gradient(a,np.deg2rad(lon),axis=-1)/(R*np.cos(np.deg2rad(lat)).reshape(shape))
    dy=np.gradient(a,np.deg2rad(lat),axis=-2)/R
    return dx,dy

def hydrostatic_geopotential(theta,salt,depth,bottom,lat,lon):
    p=gsw.p_from_z(-depth[None,:,None,None],lat[None,None,:,None])
    sa=gsw.SA_from_SP(salt,p,lon[None,None,None,:],lat[None,None,:,None])
    rho=gsw.rho(sa,gsw.CT_from_pt(sa,theta),p)
    return density_integral(rho,depth,bottom),rho

def density_integral(rho,depth,bottom):
    dz=np.diff(np.r_[0,bottom]);a=rho-RHO
    return G/RHO*(np.cumsum(a*dz[None,:,None,None],axis=1)-a*(bottom-depth)[None,:,None,None])

def match(values,targets):
    values=np.round(values,6);targets=np.round(targets,6)
    ix=np.array([int(np.argmin(abs(values-v))) for v in targets])
    np.testing.assert_allclose(values[ix],targets,atol=1e-6,rtol=0)
    return ix

def symmetric_split(u,h,uc,hc):
    return (u-uc)*(h+hc)/2,(h-hc)*(u+uc)/2

def extract():
    """Only local salt and the already-defined 140W section need new extraction."""
    import analyze_chen2015_reanalysis as chen
    dest=OUT/'inputs';dest.mkdir(parents=True,exist_ok=True)
    canonical=np.asarray(json.loads((RAW/'metadata_2024.json').read_text())['coords']['sw_ocean'])[:24]
    records=[]
    for year in range(1982,2025):
        source=RAW/f'soda3_sigma26_inputs_{year}.npz'
        output=dest/f'ocean_{year}.npz';meta=dest/f'ocean_{year}_source.json'
        if output.exists() and meta.exists():
            records.append(json.loads(meta.read_text()));continue
        with np.load(source) as z:
            lat=np.round(z['lat_t'],6);lon=np.round(z['lon_t'],6)
            iy=np.flatnonzero((lat>=-5.25)&(lat<=5.25));ix=np.flatnonzero((lon>=189.75)&(lon<=240.25))
            a={k:z[k] for k in ['temp','salt','u','lat_t','lon_t','lat_u','lon_u','depth']}
            a['lat_t']=lat;a['lon_t']=lon
            a['lat_u']=np.round(a['lat_u'],6);a['lon_u']=np.round(a['lon_u'],6)
            gate=chen.section(a,'u',220.,-9.,9.)
            sigma=chen.section_density(gate,a['depth'])
            # Require both event velocities wherever the face might be active.
            sigma=np.where(np.isfinite(gate['flow']),sigma,np.nan)
            z26,qa,_=chen.d26(sigma,a['depth'],canonical)
            assert not np.any((z26>0)&~np.isfinite(z26))
            active=chen.weights(z26,canonical)
            assert np.isfinite(gate['flow'][active>0]).all()
            local_salt=a['salt'][:,:8,iy[:,None],ix]
            assert local_salt.shape==(12,8,22,102)
            np.savez_compressed(output, salt=local_salt,
                section_u=gate['flow'],section_h=active,section_z26=z26,
                section_width=gate['width'],section_lat=gate['lat'],section_depth=a['depth'],section_bottom=canonical)
        rec=dict(year=year,source=str(source.relative_to(ROOT)),source_sha256=sha(source),
            extracted_sha256=sha(output),section_QA=qa)
        meta.write_text(json.dumps(rec,indent=2));records.append(rec)
        del a,gate,local_salt;gc.collect()
        print('extracted salt/section',year,flush=True)
    dump('ocean_source_manifest.json',records)

def section_analysis():
    us=[];hs=[]
    for y in range(1982,2025):
        with np.load(OUT/f'inputs/ocean_{y}.npz') as z:
            us.append(z['section_u'].astype(float));hs.append(z['section_h'].astype(float))
            bottom=z['section_bottom'];width=z['section_width'];lat=z['section_lat'];depth=z['section_depth']
    u=np.concatenate(us);h=np.concatenate(hs);top=np.r_[0,bottom[:-1]]
    # An active layer in ANY event/reference must have valid flow throughout.
    active=np.any(h>0,axis=0)
    if not np.isfinite(u[:,active]).all():raise ValueError('Missing section velocity on a common active cell')
    u=np.where(active[None],u,0.)
    masks={}
    for band,(a,b) in {'0_50':(0,50),'50_150':(50,150),'150_sigma26':(150,np.inf),'all':(0,np.inf)}.items():
        # Original h is overlap of sigma26 with each full cell.
        z=top[None,:,None]+h
        masks[band]=np.maximum(0,np.minimum(z,b)-np.maximum(top[None,:,None],a))
    rows=[];contrasts=[];reference=[];qc=[];error=0.
    for band,hb in masks.items():
        raw=np.sum(u*hb*width[None,None,:],axis=(1,2))/1e6
        ua,ha=climate(u)[MI],climate(hb)[MI]
        rv,rh=symmetric_split(u,hb,ua,ha)
        v=np.sum(rv*width[None,None,:],axis=(1,2))/1e6
        t=np.sum(rh*width[None,None,:],axis=(1,2))/1e6
        ref=np.sum(ua*ha*width[None,None,:],axis=(1,2))/1e6
        error=max(error,float(np.max(abs(v+t-(raw-ref)))))
        for i,date in enumerate(DATES):rows.append(dict(time=date,band=band,transport_raw_sv=raw[i],transport_anomaly_sv=anomalies(raw)[i],transport_detrend_sv=detrend(anomalies(raw))[i]))
        for bg,fn in [('mean',anomalies),('detrend',lambda x:detrend(anomalies(x)))]:
            vr,hr,qr=fn(v),fn(t),fn(raw)
            for control in [1997,2015]:
                ia=DATES.year==2023;ib=DATES.year==control
                for i in range(12):reference.append(dict(control=control,month=i+1,band=band,background=bg,
                    current_sv=(vr[ia]-vr[ib])[i],thickness_sv=(hr[ia]-hr[ib])[i],total_sv=(qr[ia]-qr[ib])[i]))
        for control in [1997,2015]:
            ia=DATES.year==2023;ib=DATES.year==control
            vc,hc=symmetric_split(u[ia],hb[ia],u[ib],hb[ib])
            cv=np.sum(vc*width[None,None,:],axis=(1,2))/1e6
            ch=np.sum(hc*width[None,None,:],axis=(1,2))/1e6
            total=raw[ia]-raw[ib]
            error=max(error,float(np.max(abs(cv+ch-total))))
            for i in range(12):contrasts.append(dict(control=control,month=i+1,band=band,current_sv=cv[i],thickness_sv=ch[i],total_sv=total[i]))
    pd.DataFrame(rows).to_csv(OUT/'section_monthly.csv',index=False)
    c=pd.DataFrame(contrasts);c.to_csv(OUT/'section_pair_monthly.csv',index=False)
    ref=pd.DataFrame(reference);ref.to_csv(OUT/'section_reference_sensitivity_monthly.csv',index=False)
    seas=[]
    for name,months in [('AMJ',[4,5,6]),('JAS',[7,8,9])]:
        ss=c[c.month.isin(months)].groupby(['control','band'])[['current_sv','thickness_sv','total_sv']].mean().reset_index();ss['season']=name;seas.append(ss)
    pd.concat(seas).to_csv(OUT/'section_pair_seasons.csv',index=False)
    old=pd.read_csv(ROOT/'outputs/research_2026/three_event_ocean_preconditioning_20261014/ocean_monthly_absolute.csv',parse_dates=['time'])
    old=old.set_index(old.time.dt.to_period('M').dt.to_timestamp()).reindex(DATES)
    current=pd.DataFrame(rows).query('band == "all"').transport_raw_sv.to_numpy()
    olderr=float(np.max(abs(current-old.u220_q_sv.to_numpy())))
    assert olderr<1e-7,olderr
    assert error<1e-10,error
    np.savez_compressed(OUT/'section_fields.npz',u=u,h=h,lat=lat,depth=depth,bottom=bottom,width=width)
    qa=dict(symmetric_identity_max_sv=error,previous_raw_transport_max_error_sv=olderr,
        common_active_cells=int(active.sum()),surface_to_sigma26=True)
    dump('section_QA.json',qa);print('section checks',qa,flush=True)

def surface_fields(lat,lon):
    sh=[];st=[]
    for y in range(1982,2025):
        with np.load(OUT/f'inputs/surface_{y}.npz') as z:
            iy=match(z['lat_ssh'],lat);ix=match(z['lon_ssh'],lon)
            sh.append(z['ssh'][:,iy[:,None],ix])
            # Native B-grid stress: four surrounding points to tracer centers.
            sy=match(z['lat_taux'],lat-.25);sx=match(z['lon_taux'],lon-.25)
            a=z['taux']
            st.append((a[:,sy[:,None],sx]+a[:,(sy+1)[:,None],sx]+a[:,sy[:,None],sx+1]+a[:,(sy+1)[:,None],sx+1])/4)
    return np.concatenate(sh).astype(float),np.concatenate(st).astype(float)

def weighted_covariance_parts(u,g,w):
    """Decompose -<u*g> into product of means, horizontal and vertical covariances."""
    wn=w/w.sum();a=wn.sum(0);valid=a>0
    col=np.divide(wn,a[None],out=np.zeros_like(wn),where=valid[None])
    uc=np.sum(u*col[None],axis=1);gc=np.sum(g*col[None],axis=1)
    um=np.sum(uc*a[None],axis=(1,2));gm=np.sum(gc*a[None],axis=(1,2))
    mean=-um*gm
    horizontal=-np.sum(uc*gc*a[None],axis=(1,2))-mean
    actual=-np.sum(u*g*wn[None],axis=(1,2,3))
    vertical=actual-mean-horizontal
    return actual,mean,horizontal,vertical

def local_analysis():
    with np.load(OLD/'local_fields_cache.npz') as z:f={k:z[k] for k in z.files}
    lat=np.round(f['lat'],6);lon=np.round(f['lon'],6);bottom=f['bottom'];depth=f['depth']
    t,u,v=[f[k].astype(float) for k in ['temp','u','v']]
    salt=np.concatenate([np.load(OUT/f'inputs/ocean_{y}.npz')['salt'] for y in range(1982,2025)]).astype(float)
    ssh,stress=surface_fields(lat,lon)
    phi,rho=hydrostatic_geopotential(t,salt,depth,bottom,lat,lon)
    px,_=gradient(phi,lat,lon);sx,_=gradient(ssh,lat,lon)
    ux,uy=gradient(u,lat,lon);tx,ty=gradient(t,lat,lon)
    cut=lambda a:a[...,1:-1,1:-1]
    tc,uc,vc=climate(t),climate(u),climate(v)
    gx,gy=gradient(tc,lat,lon)
    u,v,t,ux,uy,tx,ty,px=[cut(a) for a in [u,v,t,ux,uy,tx,ty,px]]
    ub,vb,gx,gy=[cut(a)[MI] for a in [uc,vc,gx,gy]]
    sx,stress=cut(sx),cut(stress);q=cut(f['q']).astype(float)
    la,lo=lat[1:-1],lon[1:-1]
    area=R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(la+.25))-np.sin(np.deg2rad(la-.25)))[:,None]*np.ones((1,len(lo)))
    original_wet=np.isfinite(t).all(0)&np.isfinite(u*tx+v*ty).all(0)&np.isfinite(q).all(0)[None]
    wet=original_wet.copy()
    for a in [u,v,ux,uy,px]:wet &= np.isfinite(a).all(0)
    wet &= np.isfinite(sx).all(0)[None]&np.isfinite(stress).all(0)[None]
    np.savez_compressed(OUT/'grid_support.npz',wet=wet,original_wet=original_wet,area=area,lat=la,lon=lo,depth=depth,bottom=bottom)
    rawmom=dict(pressure_density=-px,pressure_ssh=-G*np.broadcast_to(sx[:,None],u.shape),
        coriolis=2*OMEGA*np.sin(np.deg2rad(la))[None,None,:,None]*v,
        horizontal_advection=-u*ux-v*uy,metric=u*v*np.tan(np.deg2rad(la))[None,None,:,None]/R)
    adv=dict(mean_u_Tprime=-ub*(tx-gx),u_prime_meanT=-(u-ub)*gx,
        mean_v_Tprime=-vb*(ty-gy),v_prime_meanT=-(v-vb)*gy)
    total_adv=anomalies(-(u*tx+v*ty))
    adv['nonlinear_hadv']=total_adv-sum(adv.values())
    qa=dict(coverage={},rho_min=float(np.nanmin(rho)),rho_max=float(np.nanmax(rho)),
        old_and_new_masks_equal=bool(np.array_equal(wet,original_wet)),
        momentum_units='m s-2',process_units='C per standard month')
    rows=[];maps={};origrows=[];structure_error=0.
    for h in [30,50,75]:
        dz=np.maximum(0,np.minimum(bottom,h)-np.r_[0,bottom[:-1]])
        w=dz[:,None,None]*area[None]*wet
        oldw=dz[:,None,None]*area[None]*original_wet
        avg=lambda a:np.sum(np.where(wet,a,0)*w[None],axis=(1,2,3))/w.sum()
        qa['coverage'][h]=float(w.sum()/(h*area.sum()))
        if qa['coverage'][h]<.99:raise ValueError(f'Common mask coverage low: {h}, {qa["coverage"][h]}')
        # Winds are surface input to the layer mean; bottom stress is unresolved.
        forces={k:avg(a) for k,a in rawmom.items()}
        forces['wind']=avg(np.broadcast_to(stress[:,None],u.shape))/(RHO*h)
        means=avg(u);tendency=np.gradient(means,SEC,edge_order=2)
        data={'time':DATES,'depth_m':h,'u_raw_m_s':means,'tendency_raw_m_s2':tendency,
            'tendency_m_s2':np.gradient(anomalies(means),SEC,edge_order=2),'u_m_s':anomalies(means),
            'taux_raw_N_m2':forces['wind']*RHO*h,'horizontal_total':avg(total_adv)*MONTH}
        for k,a in forces.items():data[k+'_raw_m_s2']=a;data[k+'_m_s2']=anomalies(a)
        data['unresolved_raw_m_s2']=tendency-sum(forces.values())
        data['unresolved_m_s2']=data['tendency_m_s2']-sum(data[k+'_m_s2'] for k in MOM)
        for k,a in adv.items():data[k]=avg(a)*MONTH
        ua=np.where(wet,u-ub,0);gg=np.where(wet,gx,0)
        ac,me,ho,ve=weighted_covariance_parts(ua,gg,w)
        structure_error=max(structure_error,float(np.max(abs(ac*MONTH-data['u_prime_meanT']))))
        data.update(advection_mean=me*MONTH,advection_horizontal_cov=ho*MONTH,advection_vertical_cov=ve*MONTH,
            mean_u_prime=avg(u-ub),mean_background_Tx=avg(gx))
        df=pd.DataFrame(data)
        numeric=[c for c in df if c not in ['time','depth_m']]
        # Every diagnostic is detrended with the same linear projection.
        for bg in ['mean','detrend']:
            d=df.copy();d['background']=bg
            if bg=='detrend':
                for k in numeric:
                    if '_raw_' not in k:d[k]=detrend(d[k].to_numpy())
                d['tendency_m_s2']=np.gradient(d.u_m_s.to_numpy(),SEC,edge_order=2)
                d['unresolved_m_s2']=d.tendency_m_s2-sum(d[k+'_m_s2'] for k in MOM)
            rows.append(d)
        # Independent check against the already-saved all-43-year process chain.
        for k,a in adv.items():
            oldavg=np.sum(np.where(original_wet,a,0)*oldw[None],axis=(1,2,3))/oldw.sum()*MONTH
            for i in range(len(DATES)):origrows.append(dict(time=DATES[i],depth_m=h,term=k,value=oldavg[i],common_mask_value=data[k][i]))
        if h==50:
            zweight=dz[:,None,None]*wet
            colsum=zweight.sum(0)
            colavg=lambda a:np.divide(np.sum(np.where(wet,a,0)*zweight[None],axis=1),colsum[None],out=np.full((len(DATES),len(la),len(lo)),np.nan),where=colsum[None]>0)
            for k,a in {'u_anomaly':u-ub,'u_prime_meanT':adv['u_prime_meanT']*MONTH,
                'background_Tx':gx*1e6,'pressure_density':rawmom['pressure_density'],
                'pressure_ssh':rawmom['pressure_ssh']}.items():
                val=colavg(a)
                if k.startswith('pressure'):val=anomalies(val)*1e7
                maps[k]=np.stack([val[(DATES.year==e)&DATES.month.isin([7,8,9])].mean(0) for e in EVENTS])
    qa['covariance_identity_max_C_month']=structure_error
    assert structure_error<1e-10
    d=pd.concat(rows,ignore_index=True)
    finite=[c for c in d if c not in ['time','background']]
    assert np.isfinite(d[finite]).all().all()
    d.to_csv(OUT/'local_monthly.csv',index=False)
    oldcalc=pd.DataFrame(origrows);oldcalc.to_csv(OUT/'common_mask_process_audit.csv',index=False)
    previous=pd.read_csv(ROOT/'outputs/research_2026/external_background_process_bridge_20261015/monthly_local_tendencies.csv',parse_dates=['time'])
    prevlong=previous.melt(id_vars=['time','depth_m'],value_vars=ADV,var_name='term',value_name='previous')
    cmp=oldcalc.merge(prevlong,on=['time','depth_m','term'],validate='one_to_one')
    qa['existing_43yr_process_max_error_C_month']=float(np.max(abs(cmp.value-cmp.previous)))
    qa['common_mask_change_max_C_month']=float(np.max(abs(cmp.value-cmp.common_mask_value)))
    assert qa['existing_43yr_process_max_error_C_month']<1e-9,qa
    cases=d[d.time.dt.year.isin(EVENTS)].copy();cases['event']=cases.time.dt.year
    cases.to_csv(OUT/'case_monthly.csv',index=False)
    seas=[]
    for season,months in [('AMJ',[4,5,6]),('JAS',[7,8,9])]:
        ss=cases[cases.time.dt.month.isin(months)].groupby(['event','depth_m','background']).mean(numeric_only=True).reset_index();ss['season']=season;seas.append(ss)
    pd.concat(seas).to_csv(OUT/'case_seasons.csv',index=False)
    xr.Dataset({k:(('event','lat','lon'),a) for k,a in maps.items()},coords={'event':list(EVENTS),'lat':la,'lon':lo},
        attrs={'season':'JAS','background':'1982-2024 all 43 years','layer':'0-50m','pressure_units':'1e-7 m s-2','u_prime_meanT_units':'C per standard month','background_Tx_units':'C per 1000km'}).to_netcdf(OUT/'spatial_diagnostics.nc',engine='h5netcdf')
    dump('local_QA.json',qa);print('local checks',qa,flush=True)
    intervals(d)
    era5_compare(d)

def intervals(data):
    """Endpoint identity with a separate derivative-integration error."""
    rows=[]
    for (h,bg),df in data.groupby(['depth_m','background']):
        for e in EVENTS:
            a=df[df.time.dt.year.eq(e)].sort_values('time')
            seconds=(a.time+pd.Timedelta(days=14)-MID[0]).dt.total_seconds().to_numpy()
            for start,end in [(1,7),(4,7),(7,10),(1,12)]:
                sub=a[a.time.dt.month.between(start,end)];s=seconds[(a.time.dt.month>=start)&(a.time.dt.month<=end)]
                result=dict(event=e,depth_m=h,background=bg,start_month=start,end_month=end,
                    initial_u=float(sub.u_m_s.iloc[0]),final_u=float(sub.u_m_s.iloc[-1]),
                    delta_u=float(sub.u_m_s.iloc[-1]-sub.u_m_s.iloc[0]))
                for k in MOM+['unresolved','tendency']:
                    result[k]=float(np.trapz(sub[k+'_m_s2'],s))
                # Tendency is the actual-time derivative of the displayed u;
                # its trapezoidal quadrature still has a separate endpoint error.
                result['integration_mismatch']=result['delta_u']-result['tendency']
                rows.append(result)
    d=pd.DataFrame(rows);d.to_csv(OUT/'momentum_event_intervals.csv',index=False)
    out=[]
    keys=['depth_m','background','start_month','end_month']
    for control in [1997,2015]:
        x=d[d.event.eq(2023)].set_index(keys);y=d[d.event.eq(control)].set_index(keys)
        delta=x.drop(columns='event')-y.drop(columns='event')
        delta['control']=control;out.append(delta.reset_index())
    pd.concat(out).to_csv(OUT/'momentum_pair_intervals.csv',index=False)

def era5_compare(data):
    source=ROOT/'outputs/research_2026/three_event_ocean_preconditioning_20261014/atmosphere_monthly.nc'
    with source.open('rb') as f:magic=f.read(4)
    with xr.open_dataset(source,engine='scipy' if magic[:3]==b'CDF' else 'h5netcdf') as ds:
        info={k:dict(dims=list(v.dims),shape=list(v.shape),attrs=dict(v.attrs)) for k,v in ds.data_vars.items()}
        tau=ds.tau_anomaly.sel(tau_lon=slice(190,240)).load()
        weights=np.ones(tau.sizes['tau_lon']);weights[[0,-1]]=.5
        assert tau.sizes['tau_lon']==51 and tau.sizes['time']==516
        era_n34=(tau.to_numpy()*weights).sum(1)/weights.sum()
    dump('era5_cache_structure.json',info)
    # Stored ERA5 scalar uses 160E-140W, 5S-5N; never present this as collocated.
    raw=pd.read_csv(ROOT/'outputs/research_2026/three_event_ocean_preconditioning_20261014/atmosphere_absolute.csv',parse_dates=['time'])
    raw=raw.set_index(raw.time.dt.to_period('M').dt.to_timestamp()).reindex(DATES)
    a=data[(data.depth_m==50)&(data.background=='mean')].copy()
    a['era5_cwp_taux_anomaly']=anomalies(raw.tau.to_numpy())
    a['era5_nino34_taux_anomaly']=anomalies(era_n34)
    a['soda_nino34_taux_anomaly']=anomalies(a.taux_raw_N_m2.to_numpy())
    a[['time','era5_cwp_taux_anomaly','era5_nino34_taux_anomaly','soda_nino34_taux_anomaly']].to_csv(OUT/'wind_product_comparison.csv',index=False)
    dump('wind_product_comparison_metadata.json',dict(soda_region='Nino3.4, common volume-supported mask',era5_nino34='5S-5N latitude-averaged native 1deg Hovmoller; longitude trapezoid 190-240E',
        era5_cwp='160E-140W, 5S-5N; contextual only, not collocated',background='1982-2024, all years',
        independence='SODA3.15.2 is forced with ERA5: agreement is product consistency, not independent causal validation'))

def tests():
    rng=np.random.default_rng(281);u=rng.normal(size=(5,3,4));h=rng.uniform(0,10,u.shape);v=rng.normal(size=u.shape);k=rng.uniform(0,10,u.shape)
    a,b=symmetric_split(u,h,v,k);np.testing.assert_allclose(a+b,u*h-v*k,atol=1e-14)
    lat=np.arange(-5.25,5.26,.5);lon=np.arange(189.75,240.26,.5)
    field=np.ones((2,3,len(lat),len(lon)))*7
    gx,gy=gradient(field,lat,lon);np.testing.assert_allclose(gx,0,atol=1e-17);np.testing.assert_allclose(gy,0,atol=1e-17)
    # Height increasing eastward must accelerate westward, finite at the equator.
    height=np.broadcast_to(np.deg2rad(lon)[None,:]*.1,(len(lat),len(lon)))
    gx,gy=gradient(height,lat,lon)
    np.testing.assert_allclose(gx,.1/(R*np.cos(np.deg2rad(lat)))[:,None]*np.ones((1,len(lon))),atol=1e-18)
    assert np.all(-G*gx<0)
    # Analytic velocity linear in latitude: du/dy has known constant value.
    vel=np.broadcast_to(2*np.deg2rad(lat)[:,None],height.shape)
    dx,dy=gradient(vel,lat,lon);np.testing.assert_allclose(dy,2/R,atol=1e-18)
    ar=rng.normal(size=(12,3,4,5));gr=rng.normal(size=ar.shape);w=rng.uniform(.2,1,(3,4,5))
    actual,me,ho,ve=weighted_covariance_parts(ar,gr,w)
    np.testing.assert_allclose(actual,me+ho+ve,atol=1e-14)
    depth=np.array([5.,15.,25.]);bottom=np.array([10.,20.,30.])
    density=np.broadcast_to(RHO+.1*np.deg2rad(lon)[None,None,None,:],(2,3,len(lat),len(lon)))
    phi=density_integral(density,depth,bottom)
    force=-gradient(phi,lat,lon)[0]
    exact=-G/RHO*depth[None,:,None,None]*.1/(R*np.cos(np.deg2rad(lat))[None,None,:,None])*np.ones_like(force)
    np.testing.assert_allclose(force,exact,atol=1e-17)
    dump('analytic_tests.json',{'status':'PASS','tests':['symmetric transport split','constant field gradients','linear SSH force sign','analytic meridional shear','weighted mean/horizontal/vertical covariance','analytic hydrostatic density-gradient force']})

def main():
    p=argparse.ArgumentParser();p.add_argument('--extract',action='store_true');p.add_argument('--section-only',action='store_true');p.add_argument('--tests-only',action='store_true');a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);tests()
    if a.tests_only:return
    if a.extract:extract();return
    section_analysis()
    if not a.section_only:local_analysis()

if __name__=='__main__':main()
