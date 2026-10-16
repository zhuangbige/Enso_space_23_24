"""Matched Niño3.4 fixed-layer tendencies and process-resolved sLIM moments.

This is a partial local heat-budget diagnosis, not a closed mixed-layer budget.
The response projection uses precisely the same segmented, lagged seasonal
moments as the state sLIM. Linearity is checked including the unresolved term.
"""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd
import three_event_segmented_slim as slim
import paper_ro_slim as original

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data/raw/chen2015_reanalysis_20261014'
PREV = ROOT/'outputs/research_2026/three_event_slim_baseline_20261014'
OUT = ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015'
EVENTS = (1997, 2015, 2023)
EXCLUDED = [y for e in EVENTS for y in range(e-1, e+2)]
DATES = pd.date_range('1982-01-01', '2024-12-01', freq='MS')
MASK = ~DATES.year.isin(EXCLUDED)
R, RHO, CP = 6371000., 1025., 3990.
YEAR = 365.25*86400
MONTH = YEAR/12
TERMS = ['mean_u_Tprime', 'u_prime_meanT', 'mean_v_Tprime',
         'v_prime_meanT', 'nonlinear_hadv', 'surface_flux_proxy']


def dump(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
        default=lambda x: x.tolist() if isinstance(x,np.ndarray) else x.item()), encoding='utf-8')


def protocol():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'protocol_before_run.txt').write_text('''Frozen before viewing new local-process results, 2026-10-15.
Primary diagnostic: Niño3.4, 5S--5N, 170W--120W, fixed 0--50m potential
temperature. This follows the 50m Niño3.4 convention in Chen & Jin (2022),
doi:10.1029/2021GL097603, section 2.3. 0--30/75m are thickness sensitivities.
WWV26 remains the separate ocean-storage index, with its established +/-9deg
three-box geometry. Layer temperature must not be renamed SST or warm volume.
Use SODA3.15.2 monthly temperature, native B-grid u/v, and net_heating.
Velocity is averaged from the four surrounding B-grid points to tracer centers;
horizontal gradients use spherical metric distances and a one-cell halo.
Use canonical 2024 sw_ocean layer boundaries with exact partial-layer overlap.
All local terms use the same time-invariant finite ocean mask and volume.

Process decomposition: -ubar*dTprime/dx, -uprime*dTbar/dx and meridional analogs;
retain the nonlinear horizontal anomaly as a closure audit, not a new claimed
mechanism. Net surface heating/(rho*Cp*H) is a proxy: penetrating shortwave below
H is unavailable. Monthly products omit submonthly covariance. No full-year w,
mixing or assimilation tendencies are available in the selected annual cache.
The remaining tendency includes these, numerical error, and averaging mismatch;
it MUST NOT be labeled vertical advection, thermocline feedback or heat loss.
This partial local budget is distinct from the earlier two open-gate PW terms.

Training excludes 1996--1998, 2014--2016, 2022--2024, leaving 34 years/408 months.
Compute field climatologies from training only. Display training-climatology
anomalies without trend removal; show all 24 months per case and common quarters.
Monthly display derivative uses actual midmonth elapsed seconds. No causal
significance testing on selected months or just these three events.

For coefficient mapping, use T_H plus west/central/east WWV26 (primary) and T_H
plus total WWV26 (compression sensitivity). Same training-only preprocessing
as prior sLIM: monthly means then optional common linear trend, standardized.
Interpolate each continuous training segment to 72 steps/year. Response terms
are linearly interpolated in C/year; derivative is computed from that same
interpolated T_H, exactly as in the existing sLIM. Residual is defined on this
fine grid, never approximated by interpolating a monthly residual. Fit every
response with the same lag6 annual-mean / lag1 seasonal moment operator; annual
and semiannual harmonics, perturb2 and exact. Component coefficients including
residual must sum to the temperature row of the independently fitted state
operator. This identity verifies numerical bookkeeping, NOT physical closure.
Process states and coefficients use layer T_H, so they are not identical to
the earlier OISST-based coefficients. Compare OISST with T_H explicitly.
Do not pick the layer, states, or estimator by success in these three events.
No new initial-state swaps until native evolution is adequate.
''', encoding='utf-8')


def crop_inputs():
    cache=OUT/'local_fields_cache.npz'
    if cache.exists():
        with np.load(cache) as z: return {k:z[k] for k in z.files}
    vals={k:[] for k in ['temp','u','v','q']}; manifest=[]
    for year in range(1982,2025):
        p=RAW/f'soda3_sigma26_inputs_{year}.npz'
        with np.load(p) as z:
            # Classic/HDF5 caches differ by floating-point coordinate tails.
            # Match their documented half-degree grid, not literal <= endpoints.
            lat=np.round(z['lat_t'],6);lon=np.round(z['lon_t'],6);depth=z['depth'][:8]
            np.testing.assert_allclose(lat,z['lat_t'],rtol=0,atol=1e-6)
            np.testing.assert_allclose(lon,z['lon_t'],rtol=0,atol=1e-6)
            iy=np.flatnonzero((lat>=-5.25)&(lat<=5.25))
            ix=np.flatnonzero((lon>=189.75)&(lon<=240.25))
            sy=slice(iy[0],iy[-1]+1);sx=slice(ix[0],ix[-1]+1)
            assert len(iy)==22 and len(ix)==102,(year,len(iy),len(ix))
            uy=slice(iy[0],iy[-1]+2);ux=slice(ix[0],ix[-1]+2)
            np.testing.assert_allclose((z['lat_u'][uy][:-1]+z['lat_u'][uy][1:])/2,lat[sy])
            np.testing.assert_allclose((z['lon_u'][ux][:-1]+z['lon_u'][ux][1:])/2,lon[sx])
            vals['temp'].append(z['temp'][:,:8,sy,sx])
            vals['q'].append(z['net_heating'][:,sy,sx])
            for name in ['u','v']:
                a=z[name][:,:8,uy,ux]
                vals[name].append((a[:,:,:-1,:-1]+a[:,:,1:,:-1]+a[:,:,:-1,1:]+a[:,:,1:,1:])/4)
        manifest.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size))
        if year%5==0:print('loaded',year,flush=True)
    result={k:np.concatenate(v,axis=0) for k,v in vals.items()}
    result.update(lat=lat[sy],lon=lon[sx],depth=depth,
        bottom=np.array(json.loads((RAW/'metadata_2024.json').read_text())['coords']['sw_ocean'])[:8])
    np.savez_compressed(cache,**result)
    pd.DataFrame(manifest).to_csv(OUT/'source_files.csv',index=False)
    return result


def local_diagnostics(f):
    t,u,v,q=[f[k].astype(float) for k in ['temp','u','v','q']]
    lat,lon=f['lat'],f['lon']
    assert t.shape==(516,8,22,102)
    assert np.all((f['depth']>np.r_[0,f['bottom'][:-1]])&(f['depth']<f['bottom']))
    def clim(a):return np.stack([a[MASK&(DATES.month==m)].mean(axis=0) for m in range(1,13)])
    tc,uc,vc=clim(t),clim(u),clim(v)
    def gradients(a):
        dx=np.gradient(a,np.deg2rad(lon),axis=-1)/(R*np.cos(np.deg2rad(lat))[None,None,:,None])
        dy=np.gradient(a,np.deg2rad(lat),axis=-2)/R
        return dx[:,:,1:-1,1:-1],dy[:,:,1:-1,1:-1]
    tx,ty=gradients(t);cx,cy=gradients(tc)
    mi=DATES.month-1
    cut=lambda a:a[:,:,1:-1,1:-1]
    u,v,ub,vb=cut(u),cut(v),cut(uc)[mi],cut(vc)[mi]
    actual=-(u*tx+v*ty)
    actual_anom=actual-clim(actual)[mi]
    parts={
        'mean_u_Tprime':-ub*(tx-cx[mi]),
        'u_prime_meanT':-(u-ub)*cx[mi],
        'mean_v_Tprime':-vb*(ty-cy[mi]),
        'v_prime_meanT':-(v-vb)*cy[mi],
    }
    parts['nonlinear_hadv']=actual_anom-sum(parts.values())
    # Independently verify that the remainder is precisely the anomaly of u'T' advection.
    nonlinear=-(u-ub)*(tx-cx[mi])-(v-vb)*(ty-cy[mi])
    err=float(np.nanmax(abs(parts['nonlinear_hadv']-(nonlinear-clim(nonlinear)[mi]))))
    assert err<1e-12
    t=cut(t);q=q[:,1:-1,1:-1]
    lat=lat[1:-1];lon=lon[1:-1]
    area=R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat+.25))-np.sin(np.deg2rad(lat-.25)))[:,None]*np.ones((1,len(lon)))
    wet=np.isfinite(t).all(axis=0)&np.isfinite(actual).all(axis=0)&np.isfinite(q).all(axis=0)[None]
    for a in parts.values():wet&=np.isfinite(a).all(axis=0)
    rows=[];coverage={}
    mid=DATES+pd.Timedelta(days=14)
    sec=(mid-mid[0]).total_seconds().to_numpy()
    for h in [30,50,75]:
        dz=np.maximum(0,np.minimum(f['bottom'],h)-np.r_[0,f['bottom'][:-1]])
        assert abs(dz.sum()-h)<1e-10
        w=dz[:,None,None]*area[None]*wet
        coverage[h]=float(w.sum()/(h*area.sum()))
        assert coverage[h]>.995,coverage
        avg=lambda a:np.nansum(np.where(wet,a,0)*w[None],axis=(1,2,3))/w.sum()
        temp=avg(t);temp_anom=temp-clim(temp)[mi]
        # Surface proxy on the same volume-supported horizontal columns.
        q3=np.broadcast_to(q[:,None],t.shape)
        surf=avg(q3)/(RHO*CP*h)*MONTH
        surf-=clim(surf)[mi]
        d=pd.DataFrame({'time':DATES,'depth_m':h,'temperature':temp,
            'temperature_anomaly':temp_anom,'tendency':np.gradient(temp_anom,sec,edge_order=2)*MONTH})
        for name,a in parts.items():d[name]=avg(a)*MONTH
        d['surface_flux_proxy']=surf
        d['horizontal_total']=avg(actual_anom)*MONTH
        d['unresolved']=d.tendency-d[TERMS].sum(axis=1)
        rows.append(d)
    data=pd.concat(rows,ignore_index=True)
    data.to_csv(OUT/'monthly_local_tendencies.csv',index=False)
    cases=pd.concat([data[data.time.dt.year.isin([e-1,e])].assign(event=e) for e in EVENTS])
    cases['relative_month']=(cases.time.dt.year-cases.event)*12+cases.time.dt.month
    cases.to_csv(OUT/'case_monthly_tendencies.csv',index=False)
    dev=cases[cases.time.dt.year.eq(cases.event)].copy();dev['quarter']=(dev.time.dt.month-1)//3+1
    dev.groupby(['depth_m','event','quarter'])[list(data.columns[2:])].mean().to_csv(OUT/'case_quarter_tendencies.csv')
    dump('grid_and_units_QA.json',dict(coverage=coverage,area_m2=area.sum(),layer_bottoms=f['bottom'],
        nonlinear_decomposition_error_K_s=err,constant_mask=True,rate_unit='C per 365.25/12 day month',
        monthly_derivative='centered, actual elapsed midmonth seconds',rho=RHO,cp=CP))
    return data


def response_moments(a, responses, scale):
    """Response covariance, with identical chronology to slim.pool_moments."""
    k=5;d=a.shape[1];p=responses.shape[1]+2
    sums={lag:[np.zeros((k,p,d)),0.] for lag in [1,6]}
    for ids in slim.segments(a.index,MASK):
        z=a.iloc[ids].to_numpy()/scale
        grid=np.arange((len(ids)-1)*6+1)/6
        x=np.column_stack([np.interp(grid,np.arange(len(ids)),z[:,j]) for j in range(d)])
        y=np.gradient(x,1/72,axis=0,edge_order=2)[:,0]
        known=np.column_stack([np.interp(grid,np.arange(len(ids)),responses.iloc[ids,j]) for j in range(responses.shape[1])])/scale[0]
        values=np.column_stack([known,y-known.sum(axis=1),y])
        first=a.index[ids[0]];time=first.year+(first.month-.5)/12+grid/12
        for lag,acc in sums.items():
            ii=np.arange(max(lag,1),len(x)-1)
            phi=original.basis(time[ii],2)
            acc[0]+=np.einsum('nk,np,nj->kpj',phi,values[ii],x[ii-lag],optimize=True)
            acc[1]+=len(ii)
    return {lag:s[0]/s[1] for lag,s in sums.items()}


def project(pooled, gs, method):
    c0,_,b0=pooled[6];c,_,blocks=pooled[1]
    g0=gs[6];g=gs[1];k,d=c.shape[:2];p=g.shape[1]
    if method=='exact':
        cc=np.empty((k*d,k*d));gg=np.empty((p,k*d))
        for j in range(k):
            bj=b0 if j==0 else blocks;gj=g0 if j==0 else g
            gg[:,j*d:(j+1)*d]=gj[j]
            for m in range(k):cc[m*d:(m+1)*d,j*d:(j+1)*d]=bj[m,j]
        flat=np.linalg.solve(cc.T,gg.T).T
        return np.stack([flat[:,j*d:(j+1)*d] for j in range(k)])
    inv=np.linalg.inv(c[0]);mean=g0[0]@np.linalg.inv(c0[0])
    first=np.zeros_like(g)
    for j in range(1,k):first[j]=2*(g[j]-mean@c[j])@inv
    second=np.zeros_like(first)
    second[0]=-sum(first[m]@c[m] for m in range(1,k))@inv
    for j in range(1,k):second[j]=-2*(sum(first[m]@blocks[m,j] for m in range(1,k))-.5*first[j]@c[0])@inv
    coef=first+second;coef[0]+=mean
    return coef


def coefficient_mapping(data):
    raw=pd.read_csv(PREV/'inputs_absolute.csv',parse_dates=['time']).set_index('time')
    coefrows=[];predrows=[];skills=[];models={};checks=[];native=[]
    weights=MASK.astype(float)
    for h in [30,50,75]:
        d=data[data.depth_m.eq(h)].set_index('time')
        for detrend in [True,False]:
            for scheme,cols in [('three_wwv',['west_wwv','central_wwv','east_wwv']),('total_wwv',['basin_wwv'])]:
                inp=pd.concat([d[['temperature']],raw[cols]],axis=1)
                a,meta=slim.preprocess(inp,weights,detrend)
                # Remove the same kind of fitted background from each process response.
                resp,rmeta=slim.preprocess(d[TERMS]*12,weights,detrend)
                pooled,scale,di=slim.pool_moments(a,MASK)
                gs=response_moments(a,resp,scale)
                for method in ['perturb2','exact']:
                    key=f'{h}m_{scheme}_{"detrend" if detrend else "mean"}_{method}'
                    co,diag=slim.estimate_pooled(pooled,method)
                    pc=project(pooled,gs,method)
                    err=float(abs(pc[:,-1]-co[:,0,:]).max())
                    closure=float(abs(pc[:,:-1].sum(axis=1)-pc[:,-1]).max())
                    assert max(err,closure)<1e-8
                    checks.append(dict(key=key,state_operator_error=err,component_sum_error=closure,**di,**diag))
                    model=dict(coef=co,scale=scale,order=2,method=method,columns=list(inp.columns))
                    models[key]=dict(model=model,process_coef=pc,preprocessing=meta,response_preprocessing=rmeta,
                        process_names=TERMS+['unresolved','total'])
                    phi=original.basis((np.arange(1,13)-.5)/12,2)
                    # Physical coefficient units: (C/month) per C, or per 1e14 m3.
                    physical=np.einsum('mk,kpj->mpj',phi,pc)*scale[0]/scale[None,None,:]/12
                    for m in range(12):
                        for p,name in enumerate(TERMS+['unresolved','total']):
                            for j,state in enumerate(inp.columns):
                                coefrows.append(dict(key=key,month=m+1,process=name,state=state,coefficient=physical[m,p,j]))
                    fit=np.einsum('npd,nd->np',physical[DATES.month-1],a.to_numpy())
                    total=np.gradient(a.to_numpy()[:,0],1/12,edge_order=2)/12
                    truth=np.column_stack([resp.to_numpy()/12,total-resp.to_numpy().sum(axis=1)/12,total])
                    for p,name in enumerate(TERMS+['unresolved','total']):
                        # Do not infer process skill from the fine-grid closure identity.
                        for group,use in [('training',MASK),('held_out_three_windows',~MASK)]:
                            if name in ['total','unresolved']:
                                # Monthly centered derivatives at boundaries can cross excluded windows.
                                use=use.copy();use[0]=use[-1]=False
                                use[1:]&=MASK[1:]==MASK[:-1];use[:-1]&=MASK[:-1]==MASK[1:]
                            yy=truth[use,p];pp=fit[use,p]
                            skills.append(dict(key=key,process=name,sample=group,n=int(use.sum()),
                                correlation=float(np.corrcoef(yy,pp)[0,1]),rmse=float(np.sqrt(np.mean((yy-pp)**2))),
                                zero_rmse=float(np.sqrt(np.mean(yy**2))),
                                mse_skill_vs_zero=float(1-np.mean((yy-pp)**2)/np.mean(yy**2))))
                    for event in EVENTS:
                        ids=np.flatnonzero(DATES.year==event)
                        fc=slim.forecast(model,a.iloc[ids[0]].to_numpy())
                        bg=slim.background_at(meta,DATES[ids])[:,0]
                        # Restore the training climatology anomaly for comparison.
                        dispclim=np.array([inp.loc[MASK&(DATES.month==m),'temperature'].mean() for m in range(1,13)])
                        for i,idx in enumerate(ids):
                            native.append(dict(key=key,event=event,month=i+1,predicted=fc[i,0]+bg[i]-dispclim[i],observed=d.iloc[idx].temperature_anomaly))
                            for p,name in enumerate(TERMS+['unresolved','total']):
                                predrows.append(dict(key=key,event=event,month=i+1,process=name,diagnosed=truth[idx,p],
                                    reconstructed=fit[idx,p],sst_state_part=physical[i,p,0]*a.iloc[idx,0],
                                    ocean_state_part=float(physical[i,p,1:]@a.iloc[idx,1:].to_numpy())))
    pd.DataFrame(coefrows).to_csv(OUT/'seasonal_process_coefficients.csv',index=False)
    pd.DataFrame(predrows).to_csv(OUT/'case_process_reconstructions.csv',index=False)
    pd.DataFrame(skills).to_csv(OUT/'process_projection_skill.csv',index=False)
    pd.DataFrame(native).to_csv(OUT/'native_layer_temperature_forecasts.csv',index=False)
    dump('coefficient_mapping_QA.json',checks)
    dump('process_models_and_preprocessing.json',models)
    # Explicit bridge from layer temperature to OISST; correlation is not identity.
    bridge=[]
    for h in [30,50,75]:
        d=data[data.depth_m.eq(h)].set_index('time')
        ss,_=slim.preprocess(raw[['nino34']],weights,False)
        for name,mask in [('training',MASK)]+[(str(e),DATES.year==e) for e in EVENTS]:
            x=d.temperature_anomaly.to_numpy()[mask];y=ss.nino34.to_numpy()[mask]
            bridge.append(dict(depth_m=h,sample=name,correlation=np.corrcoef(x,y)[0,1],rmse=np.sqrt(np.mean((x-y)**2))))
    pd.DataFrame(bridge).to_csv(OUT/'layer_temperature_OISST_bridge.csv',index=False)
    print('mapping done; max operator error',max(q['state_operator_error'] for q in checks),flush=True)


def main():
    protocol();f=crop_inputs();data=local_diagnostics(f);coefficient_mapping(data)
    print(pd.read_csv(OUT/'case_quarter_tendencies.csv').query('depth_m==50 and quarter in [2,3]').round(4).to_string(index=False),flush=True)


if __name__=='__main__': main()
