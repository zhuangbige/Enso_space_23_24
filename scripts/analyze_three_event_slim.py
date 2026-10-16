"""Target-excluded sLIM baseline and minimum WWV26 spatial extension.

This script deliberately does not tune models on the three held-out events.
The deterministic native runs are a prerequisite for event attribution.
"""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import paper_ro_slim as original
import three_event_segmented_slim as slim

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/three_event_slim_baseline_20261014'
EVENTS=(1997,2015,2023)
EXCLUDED={e+k for e in EVENTS for k in (-1,0,1)}
VOLUME=['west_wwv','central_wwv','east_wwv']
THERMAL=['west_t50_150','central_t50_150','east_t50_150']
STATES={'legacy_d20':['ersst','d20'], 'bridge_d20':['nino34','d20'],
        'total_wwv':['nino34','basin_wwv'], 'three_wwv':['nino34']+VOLUME,
        'three_wwv_pattern':['nino34','pattern']+VOLUME,
        'thermal_sensitivity':['nino34','pattern']+VOLUME+THERMAL}


def dump(name,obj):
    def convert(x):
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,np.generic):return x.item()
        raise TypeError(type(x))
    (OUT/name).write_text(json.dumps(obj,default=convert,ensure_ascii=False,indent=2),encoding='utf-8')


def load():
    source=ROOT/'outputs/research_2026/three_event_initial_state_experiment_20261014/model_inputs_absolute.csv'
    old=ROOT/'data/derived/research_2026/paper_ro_baseline_20261014/raw_indices.csv'
    a=pd.read_csv(source,parse_dates=['time']).set_index('time')
    a.index=a.index.to_period('M').to_timestamp()
    b=pd.read_csv(old,parse_dates=['time']).set_index('time')
    a['ersst']=b.Nino34.reindex(a.index);a['d20']=b.WWV.reindex(a.index)
    assert a.index.equals(pd.date_range('1982-01-01','2024-12-01',freq='MS'))
    assert np.isfinite(a.to_numpy()).all()
    np.testing.assert_allclose(a[VOLUME].sum(axis=1),a.basin_wwv,atol=1e-10)
    return a,[source,old]


def protocol():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol_before_run.txt').write_text('''2026-10-14: target-excluded Chen--Jin sLIM test, frozen before inspecting this stage's fits.
Aim: restore the existing sLIM estimator, check a baseline, and determine whether
the minimum representation retaining all three WWV26 boxes supports native runs.
Not a real-time hindcast: all non-target years from 1982--2024 are eligible.
Exclude 1996--1998, 2014--2016, 2022--2024 from climatology/trend/scale/operator.
Three chronological segments are pooled without crossing missing intervals.
Monthly data are interpolated to 72 steps/year. These are NOT independent samples.
Use existing sLIM mean lag 6 interpolated steps, seasonal lag 1; annual and
semiannual harmonics; second-order perturbative estimator. Exact moment solution
is an estimator sensitivity; annual-only is a harmonic sensitivity, not selected.
Primary preprocessing: training-only monthly means, then a single linear trend,
matching the historical sLIM preprocessing sequence. No-trend sensitivity retained.
No ridge tuning or choosing variants by performance on the three target cases.
Hierarchy: ERSST+D20 legacy baseline; OISST+D20 data bridge; OISST+total WWV26;
OISST+three WWV26 boxes (primary minimal spatial model); +SST pattern sensitivity;
old eight-state thermal representation is a complexity sensitivity only.
GODAS D20 is mean depth (m), 5S--5N 120E--80W. SODA3 WWV26 is volume (1e14 m3),
9S--9N 120E--80W, three boundaries 120E/180/140W/80W. They are distinct variables,
domains, and datasets: no performance difference is a pure definition experiment.
All forecasts start with complete January monthly means, integrate through Dec,
and receive no later observations, wind forcing, or event-specific parameter.
Display SST uses source-specific 1982--2022 monthly climatology, restoring the
training-only trend/background. This display baseline never enters fitting.
Diagnostics: original-fit equivalence on continuous data, no gap/future leakage,
units, RK4 convergence, conditioning, perturbation size, exact sensitivity,
annual propagator spectral radius, monthly residual serial correlation,
native SST/WWV trajectories, persistence RMSE, and 200 two-year block-weighted
parameter sensitivities for the primary spatial model (including preprocessing).
Block sensitivities use chronological original trajectories and random positive
exponential block weights; they are NOT independent innovations or forecast bands.
No physical process decomposition: boundary PW/Sv do not directly equal an SST
tendency. No causal initial-state conclusion unless native runs are adequate.
Do not change model after viewing target performance to manufacture agreement.
References: Chen & Jin 2021 doi:10.1175/JCLI-D-20-0874.1;
Chen & Jin 2022 doi:10.1029/2021GL097603;
Chen et al. 2015 doi:10.1175/JCLI-D-14-00134.1.
''',encoding='utf-8')


def monthly_residuals(model,a,mask):
    mats={m:slim.propagators(model,m,1)[1] for m in range(1,13)}
    z=np.full_like(a.to_numpy(),np.nan)
    ids=np.flatnonzero(mask[:-1]&mask[1:])
    for i in ids:z[i]=a.iloc[i+1].to_numpy()-mats[a.index[i].month]@a.iloc[i].to_numpy()
    ac=[]
    for lag in (1,2,3):
        ok=np.isfinite(z[:-lag,0])&np.isfinite(z[lag:,0])
        ac.append(float(np.corrcoef(z[:-lag,0][ok],z[lag:,0][ok])[0,1]))
    return ac


def main():
    protocol()
    raw,paths=load(); raw.to_csv(OUT/'inputs_absolute.csv',index_label='time')
    mask=~raw.index.year.isin(EXCLUDED);weights=mask.astype(float)
    pd.DataFrame({'time':raw.index,'training':mask}).to_csv(OUT/'training_mask.csv',index=False)
    clim=raw.loc['1982':'2022'].groupby(raw.loc['1982':'2022'].index.month).mean()
    clim.to_csv(OUT/'display_climatology_1982_2022.csv',index_label='month')
    qa={'training_months':int(mask.sum()),'original_data_months':len(raw),
        'training_years':sorted(set(raw.index.year[mask])),
        'excluded_years':sorted(EXCLUDED),'original_estimator_qa':original.numerical_qa()}
    # Verify exact identity with the historical code on a continuous interval.
    sample=raw.loc['1982':'1995',['nino34','d20']]
    an,meta=slim.preprocess(sample,np.ones(len(sample)))
    for method in ['perturb2','exact']:
        old=original.fit(an,method=method)
        new=slim.fit(an,np.ones(len(an),bool),method=method)
        err=float(abs(old['coef']-new['coef']).max())
        assert err<1e-8;qa['continuous_equivalence_'+method]=err
    fits={};audits=[];forecasts=[];scores=[];coefficients=[]
    for detrend in (True,False):
        a,meta=slim.preprocess(raw,weights,detrend)
        for name,cols in STATES.items():
            for method in ('perturb2','exact'):
                key=f'{name}_{"detrend" if detrend else "mean"}_{method}'
                model=slim.fit(a[cols],mask,method)
                prop=slim.propagators(model)
                rho=float(max(abs(np.linalg.eigvals(prop[-1]))))
                ac=monthly_residuals(model,a[cols],mask)
                audit=dict(key=key,model=name,detrend=detrend,method=method,n_states=len(cols),
                           annual_radius=rho,residual_ac1=ac[0],residual_ac2=ac[1],residual_ac3=ac[2],**model['diag'])
                audit.pop('segments');audits.append(audit)
                model_meta={k:(v[:,[raw.columns.get_loc(c) for c in cols]] if k in ('clim','trend') else v) for k,v in meta.items()}
                fits[key]=dict(model=model,preprocessing=model_meta)
                # Coefficients in physical units per year; convert output to /month.
                lm=np.einsum('nk,kij->nij',original.basis((np.arange(1,13)-.5)/12,2),model['coef'])
                lm=lm*model['scale'][None,:,None]/model['scale'][None,None,:]/12
                for month in range(1,13):
                    for j,col in enumerate(cols):
                        coefficients.append(dict(key=key,month=month,predictor=col,coefficient_to_sst_per_month=lm[month-1,0,j]))
                for year in EVENTS:
                    dates=pd.date_range(f'{year}-01-01',periods=12,freq='MS')
                    initial=a.loc[dates[0],cols].to_numpy()
                    fc=np.einsum('nij,j->ni',prop[:12],initial)
                    bg=slim.background_at(model_meta,dates)
                    display=clim.loc[dates.month,cols].to_numpy()
                    pred=fc+bg-display;obs=raw.loc[dates,cols].to_numpy()-display
                    for i,date in enumerate(dates):
                        for j,col in enumerate(cols):
                            forecasts.append(dict(key=key,year=year,time=date,month=i+1,variable=col,
                                predicted=pred[i,j],observed=obs[i,j],predicted_model=fc[i,j],observed_model=a.loc[date,col]))
                    rmse=float(np.sqrt(np.mean((pred[1:,0]-obs[1:,0])**2)))
                    pers=float(np.sqrt(np.mean((obs[0,0]-obs[1:,0])**2)))
                    scores.append(dict(key=key,model=name,detrend=detrend,method=method,year=year,
                        rmse_feb_dec=rmse,persistence_rmse=pers,ond_pred=pred[9:,0].mean(),ond_obs=obs[9:,0].mean(),
                        january=obs[0,0],predicted_gain=pred[9:,0].mean()-obs[0,0],observed_gain=obs[9:,0].mean()-obs[0,0]))
                print(key,'rho',round(rho,3),'condition',round(model['diag']['lag_cov_condition'],1),flush=True)
    # Annual-only sensitivity is specified in advance, never substituted for primary.
    a,meta=slim.preprocess(raw,weights,True)
    annual=[]
    for method in ('perturb2','exact'):
        m=slim.fit(a[STATES['three_wwv']],mask,method,order=1)
        for year in EVENTS:
            dates=pd.date_range(f'{year}-01-01',periods=12,freq='MS')
            idx=[raw.columns.get_loc(c) for c in STATES['three_wwv']]
            fc=slim.forecast(m,a.loc[dates[0],STATES['three_wwv']].to_numpy())
            pred=fc+slim.background_at(meta,dates)[:,idx]-clim.loc[dates.month,STATES['three_wwv']].to_numpy()
            obs=raw.loc[dates,'nino34'].to_numpy()-clim.loc[dates.month,'nino34'].to_numpy()
            annual.append(dict(method=method,year=year,ond_pred=pred[9:,0].mean(),ond_obs=obs[9:].mean(),
                rmse_feb_dec=np.sqrt(np.mean((pred[1:,0]-obs[1:])**2)),annual_radius=max(abs(np.linalg.eigvals(slim.propagators(m)[-1])))))
    pd.DataFrame(annual).to_csv(OUT/'annual_only_sensitivity.csv',index=False)
    pd.DataFrame(audits).to_csv(OUT/'fit_diagnostics.csv',index=False)
    pd.DataFrame(forecasts).to_csv(OUT/'native_forecasts.csv',index=False)
    pd.DataFrame(scores).to_csv(OUT/'native_scores.csv',index=False)
    pd.DataFrame(coefficients).to_csv(OUT/'seasonal_sst_coefficients.csv',index=False)
    dump('models_and_preprocessing.json',fits)
    # QA targets failure modes introduced by disjoint fitting and state changes.
    primary=fits['three_wwv_detrend_perturb2']['model'];cols=STATES['three_wwv']
    qa['segments']=primary['diag']['segments']
    changed=raw.copy();changed.loc[~mask]=changed.loc[~mask]+10000
    ac,mc=slim.preprocess(changed,weights,True);altered=slim.fit(ac[cols],mask)
    qa['excluded_value_coefficient_change']=float(abs(primary['coef']-altered['coef']).max())
    assert qa['excluded_value_coefficient_change']<1e-10
    units=np.array([3.,100.,.2,10.]);scaled=slim.fit(a[cols]*units,mask)
    ini=a.loc['2023-01-01',cols].to_numpy()
    ref=slim.forecast(primary,ini)
    qa['units_forecast_error']=float(abs(ref-slim.forecast(scaled,ini*units)/units).max())
    qa['rk4_24_48_error']=float(abs(slim.propagators(primary,steps=24)-slim.propagators(primary,steps=48)).max())
    qa['original_integrator_error']=float(abs(ref-original.predict(primary,ini,1,months=11)).max())
    assert qa['units_forecast_error']<1e-8 and qa['rk4_24_48_error']<1e-5 and qa['original_integrator_error']<1e-10
    # A coordinate transformation retains the complete three-box information.
    # [total, west-east, central-(west+east)/2] must give identical trajectories.
    h=np.eye(4);h[1:,1:]=[[1,1,1],[1,0,-1],[-.5,1,-.5]]
    transform=pd.DataFrame(a[cols].to_numpy()@h.T,index=a.index,columns=['sst','total','w_minus_e','central_excess'])
    alt=slim.fit(transform,mask)
    qa['full_configuration_coordinate_invariance']=float(abs(ref-slim.forecast(alt,h@ini)@np.linalg.inv(h).T).max())
    assert qa['full_configuration_coordinate_invariance']<1e-8
    dump('numerical_QA.json',qa)
    # Positive block weights preserve phase, temporal adjacency and all segments.
    rng=np.random.default_rng(20261014);block=np.full(len(raw),-1);nblock=0
    for ids in slim.segments(raw.index,mask):
        yy=raw.index.year[ids]
        local=(yy-yy.min())//2
        block[ids]=local+nblock;nblock+=int(local.max())+1
    pd.DataFrame({'time':raw.index,'block':block}).to_csv(OUT/'parameter_blocks.csv',index=False)
    boot=[];bcoef=[]
    for rep in range(200):
        ww=np.zeros(len(raw));ww[mask]=rng.exponential(1.,nblock)[block[mask]]
        ab,mb=slim.preprocess(raw,ww,True);mm=slim.fit(ab[cols],mask,weights=ww)
        pp=slim.propagators(mm);rho=float(max(abs(np.linalg.eigvals(pp[-1]))))
        ids=[raw.columns.get_loc(c) for c in cols]
        for year in EVENTS:
            dates=pd.date_range(f'{year}-01-01',periods=12,freq='MS')
            f=np.einsum('nij,j->ni',pp[:12],ab.loc[dates[0],cols].to_numpy())
            f=f+slim.background_at(mb,dates)[:,ids]-clim.loc[dates.month,cols].to_numpy()
            for i in range(12):boot.append(dict(replicate=rep,year=year,month=i+1,sst=f[i,0],annual_radius=rho))
        lm=np.einsum('nk,kij->nij',original.basis((np.arange(1,13)-.5)/12,2),mm['coef'])
        lm=lm*mm['scale'][None,:,None]/mm['scale'][None,None,:]/12
        for month in range(1,13):
            for j,col in enumerate(cols):bcoef.append(dict(replicate=rep,month=month,predictor=col,value=lm[month-1,0,j]))
        if (rep+1)%50==0:print('parameter block sensitivities',rep+1,flush=True)
    pd.DataFrame(boot).to_csv(OUT/'parameter_weight_native_forecasts.csv',index=False)
    pd.DataFrame(bcoef).to_csv(OUT/'parameter_weight_coefficients.csv',index=False)
    sourcepaths=paths+[Path(__file__),Path(slim.__file__),Path(original.__file__)]
    dump('input_code_sha256.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sourcepaths})
    print(pd.DataFrame(scores).query('detrend and method == "perturb2"').to_string(index=False),flush=True)


if __name__=='__main__':main()
