#!/usr/bin/env python3
"""Matched two/three-state RO rerun, with raw ORAS5 and reference diagnostics.

The original linear model is retained exactly. The official nonlinear RO
core is a separately labeled robustness experiment. The preprocessing order
is selected ONLY using two-state linear RO validation completed before 2015.
"""
from pathlib import Path
import os
import json
import hashlib
import time
import numpy as np
import pandas as pd
import xarray as xr
import run_xro_npmm_ablation as xro
import forecast_ro_pmm_2015_2026 as old
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=xro.ROOT
OUT=ROOT/'outputs/research_2026/ro_pmm_redo_oras5_20261014'
OUT.mkdir(exist_ok=True)
RAW=ROOT/'data/derived/research_2026/oras5_ro_raw_indices/oras5_ro_raw_indices_1979_latest.nc'
REF=Path('/Users/daiyue/Documents/New project_XRO/XRO/data/XRO_indices_oras5.nc')
VARIABLES=['Nino34','WWV','NPMM']
MONTHS=old.MONTHS
MODELS={'RO':['Nino34','WWV'], 'RO_NPMM':VARIABLES,
        'RO_jointPMM':['Nino34','WWV','jointPMM']}
COLORS={'Observed':'#202833','RO':'#2878B5','RO_NPMM':'#D55E00','RO_jointPMM':'#009E73'}
LABELS={'Observed':'Observed','RO':'RO: 2 states','RO_NPMM':'RO + regional SST proxy (NPMM)',
        'RO_jointPMM':'RO + joint EOF proxy (SST + winds)'}
FAMILIES={'linear':'Original linear seasonal RO','nonlinear':'Nonlinear RO (XRO core)'}

def fit(a,variables,year,family):
    train=a.index.year<year
    if family=='linear':
        m,diag=old.fit_model(a[variables].to_numpy(),a.index,train,alpha=1,seasonal=True)
    else:
        m=xro.fit_model(a.loc[train,variables]);diag={}
    return m,diag

def predict(model,initial,month,family):
    initial=np.asarray(initial,dtype=float)
    fc=old.integrate(model,initial,month) if family=='linear' else xro.forecast(model,initial,month)
    assert np.isfinite(fc).all()
    assert np.allclose(fc[0],initial)
    return fc

def make_anomalies(raw,year,order):
    return xro.anomalies(raw,year,order=order)

def validation_select(raw):
    rows=[]
    # Fixed before examining event forecasts: all monthly initializations from
    # 2000–2013, leads 1–12. Latest verifying observation is December 2014.
    for year in range(2000,2014):
        base=make_anomalies(raw,year,0)
        scale=base.loc[base.index.year<year,['Nino34','WWV']].std().to_numpy()
        for order in [0,1,2]:
            a=make_anomalies(raw,year,order)
            m,_=fit(a,MODELS['RO'],year,'linear')
            for ini in a.index[a.index.year==year]:
                targets=pd.date_range(ini,periods=13,freq='MS')
                assert targets[-1]<pd.Timestamp('2015-01-01')
                fc=predict(m,a.loc[ini,MODELS['RO']].to_numpy(),ini.month,'linear')
                err=(fc[1:,:2]-a.reindex(targets)[MODELS['RO']].to_numpy()[1:])
                rows.append({'year':year,'month':ini.month,'order':order,
                             'normalized_joint_mse':np.mean((err/scale)**2),
                             'T_mse':np.mean(err[:,0]**2),'H_mse':np.mean(err[:,1]**2)})
    df=pd.DataFrame(rows)
    df.to_csv(OUT/'pre2015_preprocessing_validation_details.csv',index=False)
    agg=df.groupby('order')[['normalized_joint_mse','T_mse','H_mse']].mean()
    agg['T_rmse_C']=np.sqrt(agg.T_mse);agg['H_rmse_m']=np.sqrt(agg.H_mse)
    agg['normalized_joint_rmse']=np.sqrt(agg.normalized_joint_mse)
    chosen=int(agg.normalized_joint_mse.idxmin())
    agg.to_csv(OUT/'pre2015_preprocessing_validation.csv')
    print('Pre-2015 validation:',agg.to_string(),'selected order',chosen,flush=True)
    return chosen

def original_joint(year):
    path=old.CACHE/f'{old.CONFIG}_{year}.npz'
    with np.load(path) as z:
        states=z['states'];details=json.loads(str(z['details']))
    assert details['training_end']==f'{year-1}-12-01'
    dates=pd.date_range('1982-01',periods=len(states),freq='MS')
    return pd.Series(states[:,2],index=dates,name='jointPMM'),details

def display_background(raw,year,order,targets,display_clim):
    train=raw.index.year<year
    clima=raw.loc[train].groupby(raw.index[train].month).mean()
    an=raw.to_numpy()-clima.loc[raw.index.month].to_numpy()
    idx=np.arange(len(raw));center=idx[train].mean()
    t=(idx-center)/12
    design=np.column_stack([t**k for k in range(order+1)])
    beta=np.linalg.lstsq(design[train],an[train],rcond=None)[0]
    ti=((targets.year-raw.index[0].year)*12+targets.month-raw.index[0].month-center)/12
    pred_design=np.column_stack([np.asarray(ti)**k for k in range(order+1)])
    back=clima.loc[targets.month].to_numpy()+pred_design@beta-display_clim.loc[targets.month].to_numpy()
    return pd.DataFrame(back,index=targets,columns=raw.columns)

def make_rows(a,year,family,protocol,months,order=None,raw=None,display_clim=None,models=None):
    rows=[];fits={}
    for name,variables in (models or MODELS).items():
        m,diag=fit(a,variables,year,family);fits[name]=m
        for month in months:
            ini=pd.Timestamp(year,month,1)
            if ini not in a.index or a.loc[ini,variables].isna().any():continue
            targets=pd.date_range(ini,periods=13,freq='MS')
            fc=predict(m,a.loc[ini,variables].to_numpy(),month,family)
            truth=a.reindex(targets)[['Nino34','WWV']].to_numpy()
            sd=a.loc[a.index.year<year,['Nino34','WWV']].std().to_numpy()
            offset=np.zeros((13,2))
            if raw is not None:
                offset=display_background(raw,year,order,targets,display_clim)[['Nino34','WWV']].to_numpy()
                expected=raw.reindex(targets)[['Nino34','WWV']].to_numpy()-display_clim.loc[targets.month,['Nino34','WWV']].to_numpy()
                assert np.allclose(truth+offset,expected,equal_nan=True,atol=1e-10)
            for lead,target in enumerate(targets):
                rows.append(dict(protocol=protocol,family=family,model=name,year=year,month=month,
                                 init=ini,target=target,lead=lead,order=order,
                                 T=fc[lead,0]+offset[lead,0],H=fc[lead,1]+offset[lead,1],
                                 obs_T=truth[lead,0]+offset[lead,0],obs_H=truth[lead,1]+offset[lead,1],
                                 residual_T=fc[lead,0],residual_H=fc[lead,1],
                                 sd_T=sd[0],sd_H=sd[1],training_end=f'{year-1}-12-01'))
    return rows,fits

def score(f):
    rows=[]
    for keys,g in f[f.lead.gt(0)&f.year.isin([2015,2026])&f.month.isin([1,3,5])].groupby(['protocol','family','year','month','model']):
        for var in ['T','H']:
            v=g.dropna(subset=['obs_'+var])
            if not len(v):continue
            err=v[var]-v['obs_'+var]
            rows.append(dict(zip(['protocol','family','year','month','model'],keys),variable=var,
                             n=len(v),verified_end=v.target.max(),rmse=np.sqrt(np.mean(err**2)),bias=err.mean()))
    scores=pd.DataFrame(rows);scores.to_csv(OUT/'event_scores.csv',index=False)
    p=scores.pivot(index=['protocol','family','year','month','variable','n','verified_end'],columns='model',values='rmse').reset_index()
    for name in ['RO_NPMM','RO_jointPMM']:
        p[name+'_gain_percent']=100*(1-p[name]/p.RO)
    p.to_csv(OUT/'event_incremental_skill.csv',index=False)
    phases=[]
    for keys,g in f[f.lead.gt(0)&f.year.isin([2015,2026])&f.month.isin([1,3,5])].groupby(['protocol','family','year','month','model']):
        v=g.dropna(subset=['obs_T','obs_H'])
        if len(v):
            err2=((v['T']-v.obs_T)/v.sd_T)**2+((v['H']-v.obs_H)/v.sd_H)**2
            phases.append(dict(zip(['protocol','family','year','month','model'],keys),n=len(v),normalized_phase_rmse=np.sqrt(err2.mean())))
    pd.DataFrame(phases).to_csv(OUT/'event_phase_space_skill.csv',index=False)
    return p

def historical_skill(f):
    h=f[f.protocol.eq('raw_oras5')&f.year.between(2000,2024)&f.lead.gt(0)].copy()
    rows=[]
    for (family,model,lead),g in h.groupby(['family','model','lead']):
        for var in ['T','H']:
            v=g.dropna(subset=['obs_'+var]);err=v[var]-v['obs_'+var]
            rows.append(dict(family=family,model=model,lead=lead,variable=var,n=len(v),
                             rmse=np.sqrt(np.mean(err**2)),correlation=np.corrcoef(v[var],v['obs_'+var])[0,1]))
    pd.DataFrame(rows).to_csv(OUT/'historical_skill_2000_2024.csv',index=False)
    # Preprocessing selection used targets through 2014. Assess significance on
    # untouched post-selection starts 2015–2024, not on reused selection years.
    boot=[];rng=np.random.default_rng(20261014)
    for family in FAMILIES:
        for var in ['T','H']:
            for lead in [3,6,9,12]:
                g=h[h.family.eq(family)&h.year.between(2015,2024)&h.lead.eq(lead)].copy()
                g['e2']=(g[var]-g['obs_'+var])**2
                e=g.groupby(['year','model']).e2.mean().unstack()
                for alt in ['RO_NPMM','RO_jointPMM']:
                    values=e[['RO',alt]].to_numpy();n=len(values)
                    starts=rng.integers(0,n,size=(4000,int(np.ceil(n/3))))
                    ix=((starts[:,:,None]+np.arange(3))%n).reshape(4000,-1)[:,:n]
                    v=values[ix].mean(axis=1)
                    gains=100*(1-np.sqrt(v[:,1]/v[:,0]));lo,hi=np.percentile(gains,[2.5,97.5])
                    base=values.mean(axis=0)
                    boot.append(dict(family=family,variable=var,lead=lead,model=alt,
                                     gain_percent=100*(1-np.sqrt(base[1]/base[0])),ci95_low=lo,ci95_high=hi,
                                     init_years=n,init_start_year=2015,init_end_year=2024))
    pd.DataFrame(boot).to_csv(OUT/'postselection_2015_2024_paired_bootstrap.csv',index=False)

def reference_and_controls():
    ref=xr.open_dataset(REF).drop_vars('month').to_dataframe()[xro.VARS].astype(float).loc['1982-01':]
    joint,_=original_joint(2015);ref['jointPMM']=joint.reindex(ref.index)
    rows=[]
    for family in FAMILIES:
        r,_=make_rows(ref,2015,family,'supplied_ORAS5_diagnostic',[1,3,5]);rows+=r
    # Attribute the difference while preserving the ORIGINAL linear estimator.
    old_a=pd.read_csv(old.OUT/'processed_indices_training_before_2015.csv',index_col='time',parse_dates=True)
    old_a=old_a.rename(columns={'T':'Nino34','H':'WWV','PMM_joint':'jointPMM'}).loc[:'2024-12']
    for case,cols in [('old_inputs',[]),('replace_H',['WWV']),('replace_T_H',['Nino34','WWV']),
                      ('replace_T_H_P',['Nino34','WWV','jointPMM'])]:
        a=old_a.copy()
        for c in cols:a[c]=ref['NPMM' if c=='jointPMM' else c].reindex(a.index)
        r,_=make_rows(a,2015,'linear',case,[1,3,5],models={'RO':MODELS['RO'],'RO_jointPMM':MODELS['RO_jointPMM']})
        rows+=r
    return rows

def save(fig,name):
    for ext in ['png','pdf']:fig.savefig(OUT/f'{name}.{ext}',dpi=220,bbox_inches='tight',facecolor='white')
    plt.close(fig)

def plot_family(f,protocol,family,years,order=None):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'pdf.fonttype':42})
    g=f[f.protocol.eq(protocol)&f.family.eq(family)&f.year.isin(years)&f.month.isin([1,3,5])]
    names=['Observed','RO','RO_jointPMM','RO_NPMM']
    handles=[Line2D([0],[0],color=COLORS[n],lw=2.2,label=LABELS[n],ls='--' if n=='RO' else '-.' if n=='RO_jointPMM' else '-') for n in names]
    limits={}
    for var in ['T','H']:
        vals=np.r_[g[var],g['obs_'+var].dropna()];lo,hi=np.min(vals),np.max(vals)
        limits[var]=(lo-.12*(hi-lo),hi+.16*(hi-lo))
    cols=len(years)
    if protocol=='raw_oras5':
        note=(f'Raw ORAS5 regional means; training: 1982–2014 / 1982–2025. Trend order {order} fixed using validation ending in 2014.\n'
              'All curves displayed relative to the SAME 1982–2014 monthly climatology; removed background restored after forecasting.\n'
              'H: mean D20 (m). Orange: regional SST NPMM proxy. Green: joint EOF of SST + u10 + v10, not canonical MCA PMM.\n'
              'Future PMM evolves internally. Stars: monthly-mean initial state, available after that month; gray: observations unavailable.')
    else:
        note=('Same 1982–2014 coefficient training; same author-supplied ORAS5 T/H inputs in all models. No extra re-detrending.\n'
              'The supplied indices are already processed and may include later information: reference diagnostic only.\n'
              'H: mean D20 (m). Orange: regional SST NPMM proxy. Green: joint EOF of SST + u10 + v10, not canonical MCA PMM.\n'
              'This is a 2-state versus 3-state comparison; the full 10-state XRO is not represented by either of these models.')
    for month in [1,3,5]:
        fig,axes=plt.subplots(2,cols,figsize=(12.6 if cols==2 else 11,8),squeeze=False,sharex='col',sharey='row')
        fig.subplots_adjust(top=.78,bottom=.24,hspace=.28,wspace=.16)
        fig.suptitle(f'{FAMILIES[family]} | {MONTHS[month-1]} start',y=.98,fontsize=16)
        fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.5,.94),frameon=False,fontsize=9.5)
        for col,year in enumerate(years):
            c=g[g.year.eq(year)&g.month.eq(month)];base=c[c.model.eq('RO')].sort_values('lead')
            for row,var in enumerate(['T','H']):
                ax=axes[row,col]
                last=int(base.loc[base['obs_'+var].notna(),'lead'].max())
                if last<12:ax.axvspan(last+.15,12.2,color='#edf0f3',zorder=-3)
                for name in names:
                    d=base if name=='Observed' else c[c.model.eq(name)].sort_values('lead')
                    ax.plot(d.lead,d['obs_'+var] if name=='Observed' else d[var],color=COLORS[name],
                            ls='--' if name=='RO' else '-.' if name=='RO_jointPMM' else '-',lw=2.3,
                            marker='o' if name=='Observed' else None,ms=3.5)
                ax.scatter(0,base['obs_'+var].iloc[0],marker='*',s=105,color=COLORS['Observed'],zorder=10)
                ax.axhline(0,lw=.7,color='.5');ax.grid(alpha=.15)
                ax.set(xlim=(-.2,12.2),ylim=limits[var],title=f'{year} | '+('Niño3.4' if var=='T' else 'WWV proxy'))
                ax.set_xticks([0,3,6,9,12],[MONTHS[(month-1+k)%12]+('\n+1 year' if month-1+k>=12 else '') for k in [0,3,6,9,12]])
                if col==0:ax.set_ylabel('Niño3.4 anomaly (°C)' if var=='T' else 'WWV proxy: D20 anomaly (m)')
        fig.text(.055,.025,note,fontsize=8.5,linespacing=1.6,color='#4e5660',va='bottom')
        stem=f'{protocol}_{family}'
        save(fig,f'{stem}_time_series_init_{month:02d}')
        fig,axes=plt.subplots(1,cols,figsize=(12.6 if cols==2 else 11,7.4),squeeze=False,sharex=True,sharey=True)
        fig.subplots_adjust(top=.78,bottom=.29,wspace=.14)
        fig.suptitle(f'Niño3.4–WWV forecast | {FAMILIES[family]} | {MONTHS[month-1]}',y=.985,fontsize=15)
        fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.5,.94),frameon=False,fontsize=9.5)
        for ax,year in zip(axes.ravel(),years):
            c=g[g.year.eq(year)&g.month.eq(month)];base=c[c.model.eq('RO')].sort_values('lead')
            for name in names:
                d=base if name=='Observed' else c[c.model.eq(name)].sort_values('lead')
                pre='obs_' if name=='Observed' else '';d=d.dropna(subset=[pre+'T',pre+'H'])
                xx,yy=d[pre+'T'].to_numpy(),d[pre+'H'].to_numpy()
                ax.plot(xx,yy,color=COLORS[name],lw=2.2,ls='--' if name=='RO' else '-.' if name=='RO_jointPMM' else '-',marker='o',ms=3)
                for k in range(1,len(d)):
                    lead=int(d.lead.iloc[k])
                    if lead%3==0 or k==len(d)-1:
                        ax.annotate('',xy=(xx[k],yy[k]),xytext=(xx[k-1],yy[k-1]),arrowprops={'arrowstyle':'->','color':COLORS[name],'lw':1.5})
                        if name=='Observed':
                            label=MONTHS[(month-1+lead)%12]+(' +1' if month-1+lead>=12 else '')
                            ax.annotate(label,(xx[k],yy[k]),xytext=(5,6),textcoords='offset points',fontsize=8)
            ax.scatter(base.obs_T.iloc[0],base.obs_H.iloc[0],s=130,marker='*',color=COLORS['Observed'],zorder=10)
            ax.axhline(0,color='.5',lw=.7);ax.axvline(0,color='.5',lw=.7);ax.grid(alpha=.15)
            ax.set(xlim=limits['T'],ylim=limits['H'],xlabel='Niño3.4 anomaly (°C)',title=str(year))
        axes[0,0].set_ylabel('WWV proxy: mean D20 anomaly (m)')
        fig.text(.055,.025,note,fontsize=8.5,linespacing=1.6,color='#4e5660',va='bottom')
        save(fig,f'{stem}_phase_space_init_{month:02d}')

def main():
    start=time.time()
    raw=xr.open_dataset(RAW).to_dataframe()[VARIABLES].astype(float).loc['1982-01':]
    assert np.isfinite(raw).all().all()
    assert raw.index.equals(pd.date_range(raw.index[0],raw.index[-1],freq='MS'))
    selected=validation_select(raw)
    display_clim=raw.loc['1982':'2014'].groupby(raw.loc['1982':'2014'].index.month).mean()
    rows=reference_and_controls();qa={};audit=[]
    for year in range(2000,2027):
        a=make_anomalies(raw,year,selected);joint,detail=original_joint(year)
        a['jointPMM']=joint.reindex(a.index)
        months=sorted(set(a.index[a.index.year==year].month))
        for family in FAMILIES:
            r,fits=make_rows(a,year,family,'raw_oras5',months,selected,raw,display_clim);rows+=r
            if year in [2015,2026]:
                a.to_csv(OUT/f'processed_model_states_before_{year}.csv')
                for name,m in fits.items():
                    if family=='nonlinear':m.to_netcdf(OUT/f'fit_{family}_{name}_{year}.nc',engine='netcdf4')
                    else:
                        sd,b,seasonal=m
                        (OUT/f'fit_{family}_{name}_{year}.json').write_text(json.dumps({'scale':sd.tolist(),'coefficients':b.tolist(),'seasonal':seasonal},indent=2))
            if year==2015 and family=='linear':
                changed=raw.copy();changed.loc[changed.index>pd.Timestamp('2015-01-01')]+=50
                alt=make_anomalies(changed,year,selected)
                m2,_=fit(alt,VARIABLES,year,family)
                ini=pd.Timestamp('2015-01-01')
                delta=predict(fits['RO_NPMM'],a.loc[ini,VARIABLES].to_numpy(),1,family)-predict(m2,alt.loc[ini,VARIABLES].to_numpy(),1,family)
                qa['post_init_raw_perturbation_forecast_max_difference']=float(np.max(abs(delta)))
                assert np.max(abs(delta))<1e-10
                # A disconnected third state must reproduce the 2-state model.
                sd,b,seasonal=fits['RO'];sc3=np.r_[sd,1.0];bb=np.zeros((9,3))
                for block in range(3):bb[block*3:block*3+2,:2]=b[block*2:block*2+2,:]
                initial=a.loc[ini,['Nino34','WWV']].to_numpy()
                delta=old.integrate((sc3,bb,True),np.r_[initial,2.0],1)[:,:2]-predict(fits['RO'],initial,1,family)
                qa['disconnected_third_state_max_difference']=float(np.max(abs(delta)))
                assert np.max(abs(delta))<1e-10
        audit.append({'year':year,'train_start':str(a.index[0].date()),'train_end':f'{year-1}-12-01','trend_order':selected,
                      'original_PMM_training_end':detail['training_end']})
        print('Completed fold',year,flush=True)
    f=pd.DataFrame(rows)
    # Match the archived original experiment before interpreting input changes.
    archived=pd.read_csv(old.OUT/'all_monthly_forecasts.csv',parse_dates=['init','target'])
    errors=[]
    for new_name,old_name in [('RO','RO'),('RO_jointPMM','RO+PMM')]:
        current=f[f.protocol.eq('old_inputs')&f.model.eq(new_name)]
        original=archived[archived.init_year.eq(2015)&archived.init_month.isin([1,3,5])&archived.model.eq(old_name)]
        joined=current.merge(original,on=['init','target','lead'])
        assert len(joined)==39
        errors.append(float(np.max(abs(joined['T']-joined.pred_T))))
        errors.append(float(np.max(abs(joined['H']-joined.pred_H))))
    qa['unchanged_linear_model_vs_archived_forecasts_max_difference']=max(errors)
    assert max(errors)<1e-8
    # Simple forecast references are scored, but omitted from the main plots.
    baselines=[]
    for name in ['Persistence','Zero_model_anomaly']:
        b=f[f.protocol.eq('raw_oras5')&f.model.eq('RO')].copy()
        for _,ix in b.groupby(['family','init']).groups.items():
            block=b.loc[ix].sort_values('lead')
            for var in ['T','H']:
                b.loc[ix,var]=block[var].iloc[0] if name=='Persistence' else b.loc[ix,var]-b.loc[ix,'residual_'+var]
        b['model']=name
        baselines.append(b)
    pd.concat(baselines,ignore_index=True).to_csv(OUT/'simple_baseline_forecasts.csv',index=False)
    f.to_csv(OUT/'all_forecasts.csv',index=False)
    pd.DataFrame(audit).to_csv(OUT/'training_audit.csv',index=False)
    p=score(pd.concat([f,*baselines],ignore_index=True));historical_skill(f)
    for family in FAMILIES:
        plot_family(f,'raw_oras5',family,[2015,2026],selected)
        plot_family(f,'supplied_ORAS5_diagnostic',family,[2015],None)
    metadata={'raw_source':str(RAW),'raw_sha256':hashlib.sha256(RAW.read_bytes()).hexdigest(),
              'reference_source':str(REF),'reference_sha256':hashlib.sha256(REF.read_bytes()).hexdigest(),
              'raw_data_end':str(raw.index[-1].date()),'trend_order_selected':selected,
              'selection':'2-state original linear RO; all monthly starts 2000–2013, leads 1–12; targets end December 2014; minimum T/H standardized joint MSE, candidate trends 0/1/2',
              'display_baseline':'1982–2014 monthly climatology; model-removed background restored on both forecasts and observations',
              'linear_model':'unchanged original standardized monthly delta regression; annual sine/cosine; ridge alpha=1',
              'nonlinear_model':'separate XRO core; annual/semiannual coefficients; T^2 and T*H in SST equation; zero noise',
              'PMM':'Two proxies tested separately: regional ORAS5 SST NPMM (10–25N, 160–120W), and train-only OISST SST + ERA5 u10 + v10 joint EOF. Neither is a separate canonical MCA PMM-SST or PMM-wind expansion coefficient.',
              'limitations':['Reanalysis vintages and reporting latency not simulated.','Official preprocessed reference is diagnostic, not strict out-of-sample skill.','Postselection aggregate evaluation uses only 2015–2024 starts; short sample.'],
              'qa':qa,'runtime_seconds':time.time()-start}
    (OUT/'methods_and_validation.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False))
    print(p[p.month.eq(3)&p.protocol.isin(['raw_oras5','supplied_ORAS5_diagnostic'])].to_string(index=False),flush=True)
    print('Finished',OUT,flush=True)

if __name__=='__main__':main()
