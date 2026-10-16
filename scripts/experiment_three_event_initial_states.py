"""Common-parameter, target-excluded seasonal linear initial-state experiment.

This is a regularized discrete monthly state model, inspired by recharge/LIM
ideas, not a numerical reproduction of Jin (1997) or an identified heat budget.
No observations or event-specific noise are supplied after January initialization.
"""
from pathlib import Path
import argparse
import json
import warnings
import numpy as np
import pandas as pd
from scipy.linalg import solve

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'outputs/research_2026/three_event_ocean_preconditioning_20261014'
OUT = ROOT/'outputs/research_2026/three_event_initial_state_experiment_20261014'
EVENTS = (1997, 2015, 2023)
EXCLUDED = {y for e in EVENTS for y in (e-1,e,e+1)}
SST = ['nino34','pattern']
VOLUME = ['west_wwv','central_wwv','east_wwv']
THERMAL = ['west_t50_150','central_t50_150','east_t50_150']
MODELS = {'sst_only':SST, 'total_volume':SST+['basin_wwv'],
          'three_volumes':SST+VOLUME, 'volume_temperature':SST+VOLUME+THERMAL,
          'with_deep_west':SST+VOLUME+THERMAL+['west_t150_300']}
PRIMARY = 'volume_temperature'
RIDGES = np.array([0., .001, .003, .01, .03, .1, .3, 1., 3.])
REGIONS = {'west':(120,180),'central':(180,220),'east':(220,280)}


def dump(name, obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def prepare():
    path = OUT/'model_inputs_absolute.csv'
    if path.exists():
        return pd.read_csv(path,parse_dates=['time']).set_index('time')
    a=pd.read_csv(SOURCE/'atmosphere_absolute.csv',parse_dates=['time']).set_index('time')
    v=pd.read_csv(SOURCE/'ocean_monthly_absolute.csv',parse_dates=['time']).set_index('time')
    f=a[['nino34','tau']].copy()
    f['pattern']=a.nino3-a.nino4
    for r in ['basin',*REGIONS]:f[r+'_wwv']=v[r+'_wwv_m3']/1e14
    for year in range(1982,2025):
        p=np.load(SOURCE/'cache'/f'profiles_{year}.npz')
        bottom=p['layer_bottom']; top=np.r_[0.,bottom[:-1]]
        for r,(lo,hi) in REGIONS.items():
            # Same latitudinal profile and depth-layer geometry as stage one.
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',RuntimeWarning)
                t=np.nanmean(p['temp'][:,:,(p['lon']>lo)&(p['lon']<hi)],axis=2)
            for zlo,zhi in [(0,50),(50,150),(150,300)]:
                w=np.maximum(0,np.minimum(bottom,zhi)-np.maximum(top,zlo))
                val=np.nansum(t*w[None,:],axis=1)/np.sum(np.isfinite(t)*w[None,:],axis=1)
                f.loc[f.index.year==year,f'{r}_t{zlo}_{zhi}']=val
    assert len(f)==516 and np.isfinite(f.to_numpy()).all()
    f.to_csv(path,index_label='time')
    # Display anomalies retain the original common baseline; NOT used in fitting.
    clim=f.loc['1982':'2022'].groupby(f.loc['1982':'2022'].index.month).mean()
    clim.to_csv(OUT/'display_climatology_1982_2022.csv',index_label='month')
    (f-clim.loc[f.index.month].set_axis(f.index)).to_csv(OUT/'display_anomalies.csv',index_label='time')
    return f


def preprocessor(raw, dates, weights, trend=False):
    """Estimate all seasonal means/trends/scales using training observations only."""
    beta=np.zeros((12,2,raw.shape[1]))
    for m in range(1,13):
        use=(dates.month==m)&(weights>0)
        x=np.column_stack([np.ones(use.sum()),(dates.year[use].to_numpy()-2003)/10])
        w=weights[use]
        if trend:
            beta[m-1]=np.linalg.lstsq(x*np.sqrt(w[:,None]),raw[use]*np.sqrt(w[:,None]),rcond=None)[0]
        else:beta[m-1,0]=np.average(raw[use],weights=w,axis=0)
    background=background_at({'background':beta},dates)
    residual=raw-background
    scale=np.sqrt(np.average(residual**2,weights=weights,axis=0))
    assert np.isfinite(scale).all() and (scale>1e-10).all()
    return beta,scale,residual/scale


def background_at(model,dates):
    b=model['background'][dates.month.to_numpy()-1]
    return b[:,0]+b[:,1]*((dates.year.to_numpy()-2003)/10)[:,None]


def harmonic(months):
    phase=2*np.pi*(np.asarray(months)-1)/12
    return np.column_stack([np.ones(len(phase)),np.cos(phase),np.sin(phase)])


def fit(raw,dates,weights,ridge,trend=False):
    bg,scale,z=preprocessor(raw,dates,weights,trend)
    pair=(weights[:-1]>0)&(weights[1:]>0)
    ii=np.flatnonzero(pair)
    # A repeated year weights its monthly transition; no artificial time stitching.
    w=np.minimum(weights[ii],weights[ii+1]); w=w/w.sum()
    phi=harmonic(dates.month.to_numpy()[ii])
    aug=np.column_stack([z[ii],np.ones(len(ii))])
    x=np.einsum('nk,ni->nki',phi,aug).reshape(len(ii),-1)
    y=z[ii+1]-z[ii]
    gram=x.T@(w[:,None]*x)
    penalty=np.eye(x.shape[1])*ridge
    # Intercepts are nuisance terms, not part of feedback regularization.
    penalty[np.arange(raw.shape[1],x.shape[1],raw.shape[1]+1),np.arange(raw.shape[1],x.shape[1],raw.shape[1]+1)]=1e-9
    coeff=np.linalg.lstsq(gram+penalty,x.T@(w[:,None]*y),rcond=None)[0]
    coeff=coeff.reshape(3,raw.shape[1]+1,raw.shape[1])
    monthly=np.einsum('mk,kij->mij',harmonic(np.arange(1,13)),coeff)
    matrix=np.eye(raw.shape[1])[None,:,:]+monthly[:,:-1,:]
    product=np.eye(raw.shape[1])
    for mat in matrix:product=product@mat
    pred=z[ii]@np.eye(raw.shape[1])+np.einsum('ni,nij->nj',aug,monthly[dates.month.to_numpy()[ii]-1])
    residual=z[ii+1]-pred
    # Eddy/noise autocorrelation is diagnostic, never silently assumed white.
    residual_full=np.full_like(z,np.nan); residual_full[ii]=residual
    ac=[]
    for lag in (1,2,3):
        ok=np.isfinite(residual_full[:-lag,0])&np.isfinite(residual_full[lag:,0])
        ac.append(float(np.corrcoef(residual_full[:-lag,0][ok],residual_full[lag:,0][ok])[0,1]))
    return {'background':bg,'scale':scale,'matrix':matrix,'intercept':monthly[:,-1,:],
            'ridge':float(ridge),'trend':trend,'coefficients':coeff,
            'annual_radius':float(max(abs(np.linalg.eigvals(product)))),
            'condition':float(np.linalg.cond(gram+penalty)),
            'effective_dof_per_response':float(np.trace(np.linalg.pinv(gram+penalty)@gram)),
            'n_pairs':len(ii),'nino34_residual_autocorrelation_1_2_3':ac,
            'training_pair_indices':ii}


def forecast(model,initial,dates):
    dates=pd.DatetimeIndex(dates)
    z=(np.asarray(initial)-background_at(model,dates[:1])[0])/model['scale']
    out=[np.asarray(initial).copy()]
    bg=background_at(model,dates)
    for k in range(len(dates)-1):
        m=dates[k].month-1
        z=z@model['matrix'][m]+model['intercept'][m]
        out.append(z*model['scale']+bg[k+1])
    return np.array(out)


def initial_response(model):
    """Exact physical-unit derivative of Jan--Dec Nino3.4 wrt January state."""
    p=np.eye(len(model['scale']));gains=[p[:,0].copy()]
    for month in range(11):
        p=p@model['matrix'][month]
        gains.append(p[:,0]*model['scale'][0]/model['scale'])
    return np.array(gains)


def decomposition(model,frame):
    """Algebraic within-model split, not a heat-budget or causal decomposition."""
    cols=model['columns'];gain=initial_response(model)[9:].mean(axis=0)
    base=frame.loc['1982':'2022']
    allocation=base.loc[base.index.month==1,VOLUME].mean().to_numpy()
    allocation=allocation/allocation.sum()
    rows=[]
    for sy in EVENTS:
        for oy in EVENTS:
            delta=(frame.loc[pd.Timestamp(oy,1,15),cols]-frame.loc[pd.Timestamp(sy,1,15),cols]).to_numpy()
            total=delta[2:5].sum()*allocation
            parts={'total_volume_at_fixed_fraction':float(total@gain[2:5]),
                   'volume_redistribution_at_fixed_total':float((delta[2:5]-total)@gain[2:5]),
                   'subsurface_temperature':float(delta[5:]@gain[5:]),
                   'all_ocean':float(delta[2:]@gain[2:])}
            rows.append({'sst_year':sy,'ocean_year':oy,**parts})
    return pd.DataFrame(rows)


def folds(dates):
    # Contiguous validation blocks; a full calendar-year guard on either side.
    out=[]
    for i,years in enumerate(np.array_split(np.arange(1982,2025),5)):
        valid=set(years)-EXCLUDED
        held=set(range(int(years[0])-1,int(years[-1])+2))|EXCLUDED
        train=~np.isin(dates.year,list(held))
        starts=[k for k in range(len(dates)-11) if dates[k].month==1 and dates[k].year in valid]
        assert not set(dates.year[train])&valid
        out.append((i,train.astype(float),starts,sorted(valid)))
    return out


def cv_score(raw,dates,model,starts):
    err=[]; persistence=[]; clim=[]
    for k in starts:
        ds=dates[k:k+12]; obs=raw[k:k+12]
        p=forecast(model,raw[k],ds)
        # Score February--December, never the exact initialization point.
        bg=background_at(model,ds)
        persist=raw[k]-bg[0]+bg
        err.append(((p[1:,:2]-obs[1:,:2])/model['scale'][:2])**2)
        persistence.append(((persist[1:,:2]-obs[1:,:2])/model['scale'][:2])**2)
        clim.append(((bg[1:,:2]-obs[1:,:2])/model['scale'][:2])**2)
    return np.mean(err),np.mean(persistence),np.mean(clim)


def select_models(frame):
    dates=frame.index; rows=[]; saved={}; selections=[]
    for trend in (False,True):
        for name,cols in MODELS.items():
            # Deep west is a state-size sensitivity only; both backgrounds are checked.
            raw=frame[cols].to_numpy()
            for fi,weights,starts,valid in folds(dates):
                for ridge in RIDGES:
                    model=fit(raw,dates,weights,ridge,trend)
                    score,persist,clim=cv_score(raw,dates,model,starts)
                    rows.append({'model':name,'detrend':trend,'fold':fi,'ridge':ridge,
                                 'normalized_sst_mse':score,'persistence_mse':persist,'climatology_mse':clim,
                                 'annual_radius':model['annual_radius'],'n_validation_years':len(starts)})
            sub=pd.DataFrame(rows)
            sub=sub.loc[sub.model.eq(name)&sub.detrend.eq(trend)]
            tab=sub.groupby('ridge').agg(score=('normalized_sst_mse','mean'),se=('normalized_sst_mse',lambda x:x.std(ddof=1)/np.sqrt(len(x))))
            # Select on non-target cross-validation only; check full-fit stability separately.
            best=float(tab.score.idxmin())
            weights=(~np.isin(dates.year,list(EXCLUDED))).astype(float)
            model=fit(raw,dates,weights,best,trend)
            model['columns']=cols
            saved[(name,trend)]=model
            selections.append({'model':name,'detrend':trend,'states':len(cols),'ridge':best,
                               'cv_score':float(tab.loc[best,'score']),'cv_se':float(tab.loc[best,'se']),
                               'cv_persistence_score':float(sub.loc[sub.ridge.eq(best),'persistence_mse'].mean()),
                               'cv_climatology_score':float(sub.loc[sub.ridge.eq(best),'climatology_mse'].mean()),
                               **{k:model[k] for k in ['annual_radius','n_pairs','effective_dof_per_response','condition']}})
            print('Fitted',name,'detrend',trend,'ridge',best,'CV',tab.loc[best,'score'],'annual',model['annual_radius'],flush=True)
    pd.DataFrame(rows).to_csv(OUT/'blocked_cross_validation.csv',index=False)
    pd.DataFrame(selections).to_csv(OUT/'model_selection.csv',index=False)
    serial={name+('_detrended' if trend else '_mean'):{k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in mod.items()} for (name,trend),mod in saved.items()}
    dump('fitted_models.json',serial)
    return saved


def wind_closure(frame,trend=False,year_weights=None):
    train=~np.isin(frame.index.year,list(EXCLUDED))
    weights=train.astype(float) if year_weights is None else year_weights
    co=[]
    for month in range(1,13):
        sel=(frame.index.month==month)&(weights>0)
        x=np.column_stack([np.ones(sel.sum()),frame.loc[sel,SST].to_numpy(),(frame.index.year[sel]-2003)/10])
        if not trend:x=x[:,:3]
        w=np.sqrt(weights[sel])
        beta=np.linalg.lstsq(x*w[:,None],frame.loc[sel,'tau'].to_numpy()*w,rcond=None)[0]
        co.append(np.r_[beta,0.] if not trend else beta)
    return np.array(co)


def diagnose_wind(coeff,sst,dates):
    x=np.column_stack([np.ones(len(dates)),sst,(dates.year.to_numpy()-2003)/10])
    return np.einsum('ni,ni->n',x,coeff[dates.month.to_numpy()-1])


def support_check(frame,columns):
    from sklearn.covariance import LedoitWolf
    ref=frame.loc[(frame.index.month==1)&~np.isin(frame.index.year,list(EXCLUDED)),columns].to_numpy()
    scale=ref.std(axis=0);mean=ref.mean(axis=0);z=(ref-mean)/scale
    loo=[]
    for i in range(len(z)):
        others=ref[np.arange(len(ref))!=i]
        sc=others.std(axis=0);mu=others.mean(axis=0)
        cov=LedoitWolf().fit((others-mu)/sc)
        loo.append(float(cov.mahalanobis(((ref[i]-mu)/sc)[None,:])[0]))
    cov=LedoitWolf().fit(z);cut=float(np.quantile(loo,.95))
    # Conditional compatibility sensitivity: swap departures from E[ocean|SST].
    x=np.column_stack([np.ones(len(z)),z[:,:2]])
    beta=np.linalg.solve(x.T@x/len(x)+np.diag([0.,.1,.1]),x.T@z[:,2:]/len(x))
    initial={e:frame.loc[pd.Timestamp(e,1,15),columns].to_numpy() for e in EVENTS}
    adjusted={};rows=[]
    for receive in EVENTS:
        for donate in EVENTS:
            original=initial[receive].copy(); original[2:]=initial[donate][2:]
            zr=(initial[receive]-mean)/scale;zd=(initial[donate]-mean)/scale
            zz=zr.copy();zz[2:]=np.r_[1.,zr[:2]]@beta+zd[2:]-np.r_[1.,zd[:2]]@beta
            conditioned=zz*scale+mean
            adjusted[(receive,donate)]=conditioned
            for kind,value in [('direct',original),('conditioned',conditioned)]:
                dist=float(cov.mahalanobis(((value-mean)/scale)[None,:])[0])
                rows.append({'sst_year':receive,'ocean_year':donate,'swap':kind,
                             'january_joint_mahalanobis2':dist,'reference_loo_95pct':cut,
                             'outside_reference_95pct':dist>cut,
                             'minimum_regional_volume_1e14m3':float(np.min(value[2:5]))})
    pd.DataFrame(rows).to_csv(OUT/'initial_state_support.csv',index=False)
    dump('support_method.json',{'reference_years':[int(x.year) for x in frame.index[(frame.index.month==1)&~np.isin(frame.index.year,list(EXCLUDED))]],
         'reference_loo_distances':loo,'shrinkage':float(cov.shrinkage_),
         'interpretation':'Statistical support and positive volume checks only; not a 3D density/salinity/velocity balance test. 95% is descriptive, not a causal significance cutoff.'})
    return adjusted


def experiments(frame,models):
    cl=pd.read_csv(OUT/'display_climatology_1982_2022.csv').set_index('month')
    rows=[];metrics=[]
    adjusted=support_check(frame,MODELS[PRIMARY])
    for (name,trend),model in models.items():
        cols=model['columns'];coeff=wind_closure(frame,trend)
        for sy in EVENTS:
            dates=pd.date_range(f'{sy}-01-01',periods=12,freq='MS')+pd.Timedelta(days=14)
            actual=frame.loc[dates,cols].to_numpy(); base=cl.loc[dates.month,cols].to_numpy()
            for oy in EVENTS:
                initial=actual[0].copy()
                initial[2:]=frame.loc[pd.Timestamp(oy,1,15),cols].to_numpy()[2:]
                kinds=[('direct',initial)]
                if name==PRIMARY:kinds.append(('conditioned',adjusted[(sy,oy)]))
                for kind,start in kinds:
                    p=forecast(model,start,dates);tau=diagnose_wind(coeff,p[:,:2],dates)
                    for k,t in enumerate(dates):
                        row={'model':name,'detrend':trend,'swap':kind,'sst_year':sy,'ocean_year':oy,'month':k+1,'time':t,
                             'nino34_observed':actual[k,0]-base[k,0],'pattern_observed':actual[k,1]-base[k,1],
                             'tau_observed':frame.loc[t,'tau']-cl.loc[t.month,'tau'],
                             'tau_predicted':tau[k]-cl.loc[t.month,'tau'],
                             'tau_from_observed_sst':diagnose_wind(coeff,actual[:,:2],dates)[k]-cl.loc[t.month,'tau']}
                        for j,col in enumerate(cols):row[col+'_predicted']=p[k,j]-base[k,j]
                        rows.append(row)
                    if sy==oy and kind=='direct':
                        bg=background_at(model,dates);pers=actual[0]-bg[0]+bg
                        observed=actual[:,0]-base[:,0];pred=p[:,0]-base[:,0]
                        metrics.append({'model':name,'detrend':trend,'event':sy,
                            'feb_dec_rmse_C':float(np.sqrt(np.mean((p[1:,0]-actual[1:,0])**2))),
                            'persistence_rmse_C':float(np.sqrt(np.mean((pers[1:,0]-actual[1:,0])**2))),
                            'climatology_rmse_C':float(np.sqrt(np.mean((bg[1:,0]-actual[1:,0])**2))),
                            'observed_OND_C':float(observed[9:].mean()),'predicted_OND_C':float(pred[9:].mean()),
                            'observed_Jan_to_OND_C':float(observed[9:].mean()-observed[0]),
                            'predicted_Jan_to_OND_C':float(pred[9:].mean()-pred[0]),
                            'wind_feb_dec_rmse_Nm2':float(np.sqrt(np.mean((tau[1:]-frame.loc[dates[1:],'tau'].to_numpy())**2))),
                            'observed_SST_wind_rmse_Nm2':float(np.sqrt(np.mean((diagnose_wind(coeff,actual[:,:2],dates)[1:]-frame.loc[dates[1:],'tau'].to_numpy())**2)))})
    f=pd.DataFrame(rows);f.to_csv(OUT/'initial_swap_trajectories.csv',index=False)
    pd.DataFrame(metrics).to_csv(OUT/'native_initialization_skill.csv',index=False)
    summary=f.groupby(['model','detrend','swap','sst_year','ocean_year']).apply(lambda x:pd.Series({
        'nino34_OND_C':x.loc[x.month>=10,'nino34_predicted'].mean(),
        'nino34_AMJ_C':x.loc[x.month.between(4,6),'nino34_predicted'].mean(),
        'tau_AMJ_Nm2':x.loc[x.month.between(4,6),'tau_predicted'].mean(),
        'tau_JAS_Nm2':x.loc[x.month.between(7,9),'tau_predicted'].mean()}),include_groups=False).reset_index()
    for col in ['nino34_OND_C','nino34_AMJ_C','tau_AMJ_Nm2','tau_JAS_Nm2']:
        natives=summary.loc[summary.sst_year.eq(summary.ocean_year)].set_index(['model','detrend','swap','sst_year'])[col]
        summary[col+'_change_from_native']=[value-natives.loc[(name,tr,kind,sy)] for name,tr,kind,sy,value in zip(summary.model,summary.detrend,summary.swap,summary.sst_year,summary[col])]
    summary.to_csv(OUT/'swap_seasonal_effects.csv',index=False)
    decomposition(models[(PRIMARY,False)],frame).to_csv(OUT/'within_model_initial_state_decomposition.csv',index=False)
    pd.DataFrame(initial_response(models[(PRIMARY,False)]),columns=MODELS[PRIMARY],index=np.arange(1,13)).to_csv(OUT/'initial_state_response_kernel.csv',index_label='month')
    return f


def bootstrap(frame,model,n=300):
    dates=frame.index;cols=model['columns'];raw=frame[cols].to_numpy()
    years=[y for y in range(1982,2025) if y not in EXCLUDED]
    blocks=[[y,y+1] for y in years if y+1 in years]
    rng=np.random.default_rng(199720152023);results=[];radii=[];parts=[]
    for b in range(n):
        sampled=np.array(blocks)[rng.integers(len(blocks),size=(len(years)+1)//2)].ravel()[:len(years)]
        # Both endpoints must occur in the resample, without creating new adjacent dates.
        weights=np.array([np.sum(sampled==y) for y in dates.year],float)
        mod=fit(raw,dates,weights,model['ridge'],False)
        radii.append(mod['annual_radius']);wind=wind_closure(frame,False,weights)
        mod['columns']=cols
        part=decomposition(mod,frame);part['sample']=b;parts.append(part)
        for sy in EVENTS:
            ds=pd.date_range(f'{sy}-01-01',periods=12,freq='MS')+pd.Timedelta(days=14)
            start=frame.loc[ds[0],cols].to_numpy()
            native=forecast(mod,start,ds);wn=diagnose_wind(wind,native[:,:2],ds)
            for oy in EVENTS:
                a=start.copy();a[2:]=frame.loc[pd.Timestamp(oy,1,15),cols].to_numpy()[2:]
                p=forecast(mod,a,ds);w=diagnose_wind(wind,p[:,:2],ds)
                for k in range(12):results.append({'sample':b,'sst_year':sy,'ocean_year':oy,'month':k+1,
                    'nino34_absolute':p[k,0],'nino34_change_C':p[k,0]-native[k,0],
                    'tau_absolute':w[k],'tau_change_Nm2':w[k]-wn[k]})
        if (b+1)%50==0:print('Parameter bootstrap',b+1,flush=True)
    data=pd.DataFrame(results);data.to_csv(OUT/'bootstrap_trajectories.csv',index=False)
    seasonal=data.loc[data.month>=10].groupby(['sample','sst_year','ocean_year']).mean(numeric_only=True).reset_index()
    summary=seasonal.groupby(['sst_year','ocean_year']).nino34_change_C.agg(
        mean='mean',median='median',lo=lambda x:x.quantile(.025),hi=lambda x:x.quantile(.975),fraction_positive=lambda x:(x>0).mean()).reset_index()
    summary.to_csv(OUT/'bootstrap_OND_swap_effect.csv',index=False)
    pd.concat(parts,ignore_index=True).to_csv(OUT/'bootstrap_initial_state_decomposition.csv',index=False)
    dump('bootstrap_QA.json',{'samples':n,'block_length_years':2,'max_annual_radius':float(max(radii)),
         'unstable_fraction':float(np.mean(np.array(radii)>1)),
         'interpretation':'Conditional parameter uncertainty with fixed selected state and ridge; no innovations and no model-form uncertainty. Unstable draws retained and reported.'})


def diagnose_native_errors(frame,model):
    """Propagate observed one-step residuals to locate, not attribute, model failure.

    These future residuals are used only for this retrospective error identity.
    They are never supplied to the free forecasts or to initial-state swaps.
    """
    cols=model['columns'];rows=[];checks=[]
    for event in EVENTS:
        ds=pd.date_range(f'{event}-01-01',periods=12,freq='MS')+pd.Timedelta(days=14)
        obs=frame.loc[ds,cols].to_numpy()
        free=forecast(model,obs[0],ds)
        residuals=[]
        for k in range(11):
            one=forecast(model,obs[k],ds[k:k+2])[1]
            residuals.append((obs[k+1]-one)/model['scale'])
        total=np.zeros((12,len(cols)))
        for k,r in enumerate(residuals):
            for group,ids in [('sst',[0,1]),('ocean',list(range(2,len(cols))))]:
                z=np.zeros(len(cols));z[ids]=r[ids]
                history=np.zeros((12,len(cols)));history[k+1]=z*model['scale']
                for step in range(k+1,11):
                    z=z@model['matrix'][step]
                    history[step+1]=z*model['scale']
                total+=history
                rows.append({'event':event,'source_month':k+2,'state_group':group,
                             'one_step_nino34_residual_C':float(r[0]*model['scale'][0]) if group=='sst' else 0.,
                             'OND_nino34_error_contribution_C':float(history[9:,0].mean()),
                             'interpretation':'Propagated statistical model error; not identified external forcing or physical heat-budget term'})
        err=float(np.max(abs(total-(obs-free))))
        assert err<1e-10
        checks.append({'event':event,'full_state_error_identity_max_error':err})
    pd.DataFrame(rows).to_csv(OUT/'native_forecast_error_timing.csv',index=False)
    dump('error_timing_QA.json',checks)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bootstrap',type=int,default=300)
    parser.add_argument('--reuse-models',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    dump('analysis_contract.json',{'primary':PRIMARY,'states':MODELS,'primary_chosen_from_previous_diagnostics_not_target_fit':True,
        'model':'Monthly affine linear transition; constant plus annual sin/cos, ridge on tendency coefficients',
        'exclusions':sorted(EXCLUDED),'selection':'Five contiguous time blocks with one-year guards; Jan-start Feb-Dec normalized errors for Nino3.4 and Nino3-Nino4; minimum average fold MSE',
        'primary_background':'Training-only monthly means; training-only monthly trend is a sensitivity',
        'display_background':'1982-2022 monthly mean, as in stage one, used only in presentation',
        'initialization':'Actual January SST entries from row and ocean entries from column; no future observations',
        'detrended_swap':'Absolute donor ocean values transplanted into recipient year, then standardized against recipient trend background',
        'wind':'Same monthly SST diagnostic closure in every combination; not an independent prognostic wind state',
        'linear_limitation':'Ocean swap differences must be additive and independent of row SST in the direct linear experiment. No state-dependent feedback interaction can be inferred.',
        'interpretation_gate':'Inspect all native combinations and held-out baseline skill before interpreting any swap; failure remains a result, not a reason for event-specific refitting.'})
    frame=prepare()
    if args.reuse_models:
        serial=json.loads((OUT/'fitted_models.json').read_text());models={}
        for key,mod in serial.items():
            trend=key.endswith('_detrended');name=key.removesuffix('_detrended' if trend else '_mean')
            for k in ['background','scale','matrix','intercept','coefficients','training_pair_indices']:mod[k]=np.array(mod[k])
            models[(name,trend)]=mod
    else:models=select_models(frame)
    experiments(frame,models)
    diagnose_native_errors(frame,models[(PRIMARY,False)])
    if args.bootstrap:bootstrap(frame,models[(PRIMARY,False)],args.bootstrap)
    print('Completed',OUT,flush=True)


if __name__=='__main__':main()
