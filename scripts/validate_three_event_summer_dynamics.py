"""Independent reconstructions from frozen arrays and checks on delivered tables."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import gsw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/three_event_summer_current_dynamics_20261015'
R=6371000.;G=9.81;RHO=1025.
MOM=['wind','pressure_ssh','pressure_density','coriolis','horizontal_advection','metric']

def main():
    for year in range(1982,2025):
        original=json.loads((ROOT/f'data/raw/chen2015_reanalysis_20261014/metadata_{year}.json').read_text())
        surface=json.loads((OUT/f'inputs/surface_{year}_metadata.json').read_text())
        assert original['url']==surface['url']
        with np.load(OUT/f'inputs/surface_{year}.npz') as z:
            np.testing.assert_allclose(z['source_time'],original['coords']['time'],rtol=0,atol=0)
            assert z['source_time'].shape==(12,)
    d=pd.read_csv(OUT/'local_monthly.csv',parse_dates=['time'])
    assert len(d)==516*3*2 and not d.duplicated(['time','depth_m','background']).any()
    assert np.isfinite(d.select_dtypes('number')).all().all()
    component=sum(d[k+'_m_s2'] for k in MOM)+d.unresolved_m_s2
    identity=float(np.max(abs(component-d.tendency_m_s2)))
    assert identity<1e-18
    np.testing.assert_allclose(d.advection_mean+d.advection_horizontal_cov+d.advection_vertical_cov,d.u_prime_meanT,atol=1e-12)
    sec=pd.read_csv(OUT/'section_pair_monthly.csv')
    np.testing.assert_allclose(sec.current_sv+sec.thickness_sv,sec.total_sv,atol=1e-10)
    byband=sec[sec.band!='all'].groupby(['control','month'])[['current_sv','thickness_sv','total_sv']].sum()
    allband=sec[sec.band=='all'].set_index(['control','month'])[['current_sv','thickness_sv','total_sv']]
    np.testing.assert_allclose(byband.sort_index(),allband.sort_index(),atol=1e-10)
    ref=pd.read_csv(OUT/'section_reference_sensitivity_monthly.csv')
    np.testing.assert_allclose(ref.current_sv+ref.thickness_sv,ref.total_sv,atol=1e-10)
    # Separate the changed climatology from the slightly narrower common mask.
    audit=pd.read_csv(OUT/'common_mask_process_audit.csv',parse_dates=['time'])
    prev=pd.read_csv(ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015/monthly_local_tendencies.csv',parse_dates=['time'])
    prev=prev.melt(id_vars=['time','depth_m'],value_vars=['mean_u_Tprime','u_prime_meanT','mean_v_Tprime','v_prime_meanT','nonlinear_hadv'],var_name='term',value_name='old_34yr_original_mask')
    bridge=audit.merge(prev,on=['time','depth_m','term'],validate='one_to_one')
    bridge=bridge.rename(columns={'value':'new_43yr_original_mask','common_mask_value':'new_43yr_common_mask'})
    bridge['background_change']=bridge.new_43yr_original_mask-bridge.old_34yr_original_mask
    bridge['mask_change']=bridge.new_43yr_common_mask-bridge.new_43yr_original_mask
    bridge.to_csv(OUT/'background_and_mask_bridge_monthly.csv',index=False)
    bg=bridge[bridge.time.dt.year.isin([1997,2015,2023])&bridge.time.dt.month.isin([7,8,9])].copy()
    bg['event']=bg.time.dt.year
    bg.groupby(['event','depth_m','term']).mean(numeric_only=True).reset_index().to_csv(OUT/'background_and_mask_bridge_JAS.csv',index=False)
    robust=pd.read_csv(OUT/'case_seasons.csv').query('season == "JAS"')
    checks={}
    for (h,b),ss in robust.groupby(['depth_m','background']):
        ss=ss.set_index('event')
        checks[f'{h}_{b}']={k:bool(ss.loc[2023,k]<min(ss.loc[1997,k],ss.loc[2015,k])) for k in ['u_m_s','u_prime_meanT','wind_m_s2']}
    assert all(all(v.values()) for v in checks.values()),checks
    season=pd.read_csv(OUT/'section_pair_seasons.csv')
    for s,months in [('AMJ',[4,5,6]),('JAS',[7,8,9])]:
        manual=sec[sec.month.isin(months)].groupby(['control','band'])[['current_sv','thickness_sv','total_sv']].mean().sort_index()
        saved=season[season.season.eq(s)].set_index(['control','band'])[manual.columns].sort_index()
        np.testing.assert_allclose(manual,saved,atol=1e-12)
    # Independently calculate the 2023 raw pressure forces and surface input.
    support=dict(np.load(OUT/'grid_support.npz'));wet=support['wet'];area=support['area'];depth=support['depth'];bottom=support['bottom']
    with np.load(ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015/local_fields_cache.npz') as z:
        theta=z['temp'][(2023-1982)*12:(2024-1982)*12].astype(float);lat=z['lat'];lon=z['lon']
    salt=np.load(OUT/'inputs/ocean_2023.npz')['salt'].astype(float)
    pressure=gsw.p_from_z(-depth[None,:,None,None],lat[None,None,:,None])
    sa=gsw.SA_from_SP(salt,pressure,lon[None,None,None,:],lat[None,None,:,None])
    density=gsw.rho(sa,gsw.CT_from_pt(sa,theta),pressure)
    phi=np.zeros_like(density);tops=np.r_[0,bottom[:-1]]
    for k in range(len(depth)):
        for j in range(k):phi[:,k]+=(density[:,j]-RHO)*(bottom[j]-tops[j])
        phi[:,k]+=(density[:,k]-RHO)*(depth[k]-tops[k])
    phi*=G/RHO
    dx=R*np.cos(np.deg2rad(lat[1:-1]))[:,None]*np.deg2rad(1.)
    density_force=-(phi[:,:,1:-1,2:]-phi[:,:,1:-1,:-2])/dx
    with np.load(OUT/'inputs/surface_2023.npz') as z:
        # Coordinates are verified explicitly, not relying on matching array lengths.
        ix=np.array([np.argmin(abs(z['lon_ssh']-v)) for v in lon]);iy=np.array([np.argmin(abs(z['lat_ssh']-v)) for v in lat])
        np.testing.assert_allclose(z['lon_ssh'][ix],lon,atol=1e-6)
        ssh=z['ssh'][:,iy[:,None],ix].astype(float)
        sshforce=-G*(ssh[:,1:-1,2:]-ssh[:,1:-1,:-2])/dx
        xu=np.array([np.argmin(abs(z['lon_taux']-(x-.25))) for x in lon[1:-1]])
        yu=np.array([np.argmin(abs(z['lat_taux']-(y-.25))) for y in lat[1:-1]])
        # Match float32 collocation rounding used by frozen cache extraction.
        stress=sum(z['taux'][:,(yu+dy)[:,None],xu+dx_] for dy,dx_ in [(0,0),(1,0),(0,1),(1,1)])/4
    errors={}
    for h in [30,50,75]:
        dz=np.maximum(0,np.minimum(bottom,h)-tops);w=dz[:,None,None]*area[None]*wet;w/=w.sum()
        avg=lambda a:np.sum(np.where(wet,a,0)*w[None],axis=(1,2,3))
        x=d[(d.depth_m==h)&(d.background=='mean')&d.time.dt.year.eq(2023)]
        for name,a in [('pressure_density',density_force),('pressure_ssh',np.broadcast_to(sshforce[:,None],density_force.shape)),('wind',np.broadcast_to(stress[:,None],density_force.shape)/(RHO*h))]:
            errors[f'{h}_{name}']=float(np.max(abs(avg(a)-x[name+'_raw_m_s2'].to_numpy())))
    assert max(errors.values())<1e-13,errors
    # Actual-time derivative independently using the three-point nonuniform rule.
    derivative=[]
    for _,x in d.groupby(['depth_m','background']):
        x=x.sort_values('time');s=(x.time-x.time.iloc[0]).dt.total_seconds().to_numpy();a=x.u_m_s.to_numpy()
        left=np.diff(s)[:-1];right=np.diff(s)[1:]
        deriv=-right/(left*(left+right))*a[:-2]+(right-left)/(left*right)*a[1:-1]+left/(right*(left+right))*a[2:]
        derivative.append(float(np.max(abs(deriv-x.tendency_m_s2.to_numpy()[1:-1]))))
    assert max(derivative)<1e-18
    ints=pd.read_csv(OUT/'momentum_pair_intervals.csv')
    np.testing.assert_allclose(ints[MOM+['unresolved','integration_mismatch']].sum(axis=1),ints.delta_u,atol=1e-12)
    np.testing.assert_allclose(ints.initial_u+ints.delta_u,ints.final_u,atol=1e-12)
    protected=json.loads((OUT/'protected_artifacts_before.json').read_text())
    unchanged={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in protected.items()}
    assert all(unchanged.values())
    result=dict(status='PASS',source_calendar_checks=43,rows=len(d),case_rows=int(d.time.dt.year.isin([1997,2015,2023]).sum()),
        momentum_identity_error_m_s2=identity,independent_pressure_wind_max_error_m_s2=errors,
        independent_current_derivative_error_m_s2=max(derivative),six_setting_JAS_ranking_checks=checks,protected_artifacts=unchanged,
        meaning='Numerical and source consistency only; residual closure does not establish physical attribution.')
    (OUT/'validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
