#!/usr/bin/env python3
"""RO ablations with the published, canonical MCA PMM-SST and PMM-wind.

Use the original author's two expansion coefficients, not local proxy indices.
Keep the existing ORAS5 T/H preprocessing and both RO estimators unchanged.
The published index is a current-vintage product: this is a retrospective
forecast experiment, not a reconstruction of data releases available in 2015.
"""
from pathlib import Path
import hashlib
import json
import time
import numpy as np
import pandas as pd
import xarray as xr
import redo_ro_pmm_on_oras5 as previous
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=previous.ROOT
OUT=ROOT/'outputs/research_2026/ro_standard_pmm_20261014'
SOURCE=ROOT/'data/raw/climate_indices/standard_pmm_20261014'
OUT.mkdir(parents=True,exist_ok=True)
P=['PMM_SST','PMM_wind']
TH=['Nino34','WWV']
MODELS={'RO':TH,'RO_SST':TH+[P[0]],'RO_wind':TH+[P[1]],'RO_both':TH+P}
LABELS={'Observed':'Observed','RO':'RO (2 states)','RO_SST':'RO + PMM-SST (3 states)',
        'RO_wind':'RO + PMM-wind (3 states)','RO_both':'RO + both PMM indices (4 states)'}
COLORS={'Observed':'#202833','RO':'#2878B5','RO_SST':'#D55E00','RO_wind':'#009E73','RO_both':'#8C56A2'}
STYLES={'Observed':'-','RO':'--','RO_SST':'-','RO_wind':'-.','RO_both':':'}
FAMILIES=previous.FAMILIES
ORDER=1  # Frozen in the prior pre-2015 two-state RO validation.


def load_sources():
    p=pd.read_csv(SOURCE/'PMM_uw.txt',sep=r'\s+')
    p.index=pd.to_datetime(dict(year=p.Year,month=p.Mo,day=1))
    p=p[['SST','Wind']].rename(columns={'SST':P[0],'Wind':P[1]})
    p.index.name='time'
    assert p.index.is_unique and p.index.equals(pd.date_range(p.index[0],p.index[-1],freq='MS'))
    assert np.isfinite(p.to_numpy()).all() and (p.abs()<90).all().all()
    cross=[]
    for variable,filename in zip(P,['pmm_sst_noaa.data','pmm_wind_noaa.data']):
        rows=[]
        for line in (SOURCE/filename).read_text().splitlines():
            vals=line.split()
            if len(vals)!=13 or not vals[0].isdigit():continue
            year=int(vals[0])
            for month,value in enumerate(vals[1:],1):
                if float(value)>-90:rows.append((pd.Timestamp(year,month,1),float(value)))
        noaa=pd.Series(dict(rows)).sort_index()
        joined=pd.concat([p[variable],noaa.rename('NOAA')],axis=1).dropna()
        diff=(joined[variable]-joined.NOAA).abs()
        cross.append(dict(variable=variable,overlap_months=len(joined),
                          noaa_last=str(noaa.index[-1].date()),max_absolute_difference=float(diff.max())))
        assert diff.max()<1e-8, 'Investigate provider vintage differences before mixing indices'
    raw=xr.open_dataset(previous.RAW)[TH].to_dataframe()[TH].astype(float).loc['1982-01':]
    assert np.isfinite(raw.to_numpy()).all()
    assert raw.index.equals(pd.date_range(raw.index[0],raw.index[-1],freq='MS'))
    p.to_csv(OUT/'published_standard_pmm_indices.csv')
    raw.to_csv(OUT/'raw_oras5_T_H.csv')
    return raw,p,cross


def model_states(raw,p,year):
    a=previous.make_anomalies(raw,year,ORDER)
    # Published PMM is already deseasonalized, detrended and CTI-adjusted.
    # Only recenter its training mean for the no-intercept RO; do not remove
    # another ENSO index or estimate another EOF/MCA on the event period.
    train=p.loc[(p.index>=raw.index[0])&(p.index.year<year),P]
    assert train.index.equals(raw.index[raw.index.year<year])
    means=train.mean()
    a[P]=p.reindex(a.index)[P]-means
    assert np.isfinite(a.loc[a.index.year<year].to_numpy()).all()
    return a,means


def run_forecasts(raw,p):
    clim=raw.loc['1982':'2014'].groupby(raw.loc['1982':'2014'].index.month).mean()
    rows=[];p_rows=[];audit=[];qa={};event_fits={}
    # Fixed MCA patterns use 1950–2005: do not report pre-2006 forecasts as OOS.
    for year in range(2006,2027):
        a,means=model_states(raw,p,year)
        months=a.index[(a.index.year==year)&a[P].notna().all(axis=1)].month.tolist()
        for family in FAMILIES:
            new,fits=previous.make_rows(a,year,family,'published_standard_PMM',months,
                                      ORDER,raw,clim,models=MODELS)
            rows.extend(new)
            if year in [2015,2026]:
                a.to_csv(OUT/f'processed_states_before_{year}.csv')
                event_fits[(family,year)]=fits
                for name,fit in fits.items():
                    if family=='linear':
                        sd,b,seasonal=fit
                        artifact=dict(variables=MODELS[name],scale=sd.tolist(),coefficients=b.tolist(),seasonal=seasonal,
                                      pmm_training_mean=means.to_dict(),training_end=f'{year-1}-12-01')
                        (OUT/f'fit_{family}_{name}_{year}.json').write_text(json.dumps(artifact,indent=2)+'\n')
                    else:fit.to_netcdf(OUT/f'fit_{family}_{name}_{year}.nc',engine='netcdf4')
                    for month in months:
                        ini=pd.Timestamp(year,month,1)
                        fc=previous.predict(fit,a.loc[ini,MODELS[name]].to_numpy(),month,family)
                        for j,variable in enumerate(MODELS[name][2:],2):
                            for lead,target in enumerate(pd.date_range(ini,periods=13,freq='MS')):
                                p_rows.append(dict(family=family,model=name,init=ini,target=target,lead=lead,
                                                   variable=variable,predicted=fc[lead,j]+means[variable],
                                                   observed=p[variable].get(target,np.nan)))
        audit.append(dict(year=year,training_start=str(raw.index[0].date()),training_end=f'{year-1}-12-01',
                          training_months=int((a.index.year<year).sum()),initialization_months=months,
                          pmm_sst_training_mean=means[P[0]],pmm_wind_training_mean=means[P[1]]))
        print('Completed standard PMM fold',year,'months',months,flush=True)
    f=pd.DataFrame(rows)
    f.to_csv(OUT/'all_forecasts.csv',index=False)
    pd.DataFrame(p_rows).to_csv(OUT/'event_PMM_component_forecasts.csv',index=False)
    pd.DataFrame(audit).to_csv(OUT/'training_audit.csv',index=False)
    # Verify the two-state baseline stayed exactly the same on common cases.
    archived=pd.read_csv(previous.OUT/'all_forecasts.csv',parse_dates=['init','target'])
    archived=archived[archived.protocol.eq('raw_oras5')&archived.model.eq('RO')]
    matched=f[f.model.eq('RO')].merge(archived,on=['family','init','target','lead'],suffixes=('_new','_old'))
    assert len(matched)==len(f[f.model.eq('RO')])
    qa['baseline_RO_max_difference']=float(np.max(np.abs(matched[['T_new','H_new']].to_numpy()-matched[['T_old','H_old']].to_numpy())))
    assert qa['baseline_RO_max_difference']<1e-9
    assert np.isfinite(f[['T','H']].to_numpy()).all()
    qa['max_initial_state_difference']=float(np.max(abs(f.loc[f.lead.eq(0),['T','H']].to_numpy()-f.loc[f.lead.eq(0),['obs_T','obs_H']].to_numpy())))
    assert qa['max_initial_state_difference']<1e-9
    # A meaningful no-future-input check: modify all post-initial raw T/H and
    # published P values; repeat preprocessing, fitting and integration.
    for year in [2015,2026]:
        ini=pd.Timestamp(year,1,1)
        changed_raw=raw.copy();changed_raw.loc[changed_raw.index>ini]+=100
        changed_p=p.copy();changed_p.loc[changed_p.index>ini]+=100
        alt,_=model_states(changed_raw,changed_p,year)
        a,_=model_states(raw,p,year)
        for family in FAMILIES:
            errors=[]
            for name,variables in MODELS.items():
                ref=previous.predict(event_fits[(family,year)][name],a.loc[ini,variables].to_numpy(),1,family)
                fit,_=previous.fit(alt,variables,year,family)
                check=previous.predict(fit,alt.loc[ini,variables].to_numpy(),1,family)
                errors.append(float(np.max(abs(ref-check))))
            qa[f'post_init_perturbation_{family}_{year}_max_difference']=max(errors)
            assert max(errors)<1e-9
    # All models must be scored on identical target dates, without lead zero.
    counts=f.groupby(['family','init','model']).size().unstack()
    assert counts.eq(13).all().all()
    qa['matched_model_target_dates']=True
    qa['forecast_values_finite']=True
    return f,qa,archived


def scores(f):
    rows=[]
    for keys,g in f[f.lead.gt(0)&f.year.isin([2015,2026])].groupby(['family','year','month','model']):
        for var in ['T','H']:
            v=g.dropna(subset=['obs_'+var]);err=v[var]-v['obs_'+var]
            rows.append(dict(zip(['family','year','month','model'],keys),variable=var,n=len(v),
                             verified_end=v.target.max(),rmse=float(np.sqrt(np.mean(err**2))),bias=float(err.mean())))
        v=g.dropna(subset=['obs_T','obs_H'])
        e2=((v['T']-v.obs_T)/v.sd_T)**2+((v['H']-v.obs_H)/v.sd_H)**2
        rows.append(dict(zip(['family','year','month','model'],keys),variable='phase',n=len(v),
                         verified_end=v.target.max(),rmse=float(np.sqrt(e2.mean())),bias=np.nan))
    s=pd.DataFrame(rows)
    s.to_csv(OUT/'event_scores.csv',index=False)
    table=s.pivot(index=['family','year','month','variable','n','verified_end'],columns='model',values='rmse').reset_index()
    for model in list(MODELS)[1:]:table[model+'_gain_percent']=100*(1-table[model]/table.RO)
    table.to_csv(OUT/'event_incremental_skill.csv',index=False)
    history=[];boot=[];rng=np.random.default_rng(20261014)
    for family in FAMILIES:
        for var in ['T','H']:
            for lead in range(1,13):
                g=f[f.family.eq(family)&f.year.between(2015,2024)&f.lead.eq(lead)].dropna(subset=['obs_'+var]).copy()
                for model,v in g.groupby('model'):
                    history.append(dict(family=family,variable=var,lead=lead,model=model,n=len(v),
                                        rmse=np.sqrt(np.mean((v[var]-v['obs_'+var])**2)),
                                        correlation=np.corrcoef(v[var],v['obs_'+var])[0,1]))
                if lead not in [3,6,9,12]:continue
                g['e2']=(g[var]-g['obs_'+var])**2
                e=g.groupby(['year','model']).e2.mean().unstack()
                assert len(e)==10 and not e.isna().any().any()
                n=len(e);starts=rng.integers(0,n,size=(4000,int(np.ceil(n/3))))
                ix=((starts[:,:,None]+np.arange(3))%n).reshape(4000,-1)[:,:n]
                for model in list(MODELS)[1:]:
                    pairs=e[['RO',model]].to_numpy();v=pairs[ix].mean(axis=1)
                    gains=100*(1-np.sqrt(v[:,1]/v[:,0]));lo,hi=np.percentile(gains,[2.5,97.5])
                    means=pairs.mean(axis=0)
                    boot.append(dict(family=family,variable=var,lead=lead,model=model,
                                     gain_percent=100*(1-np.sqrt(means[1]/means[0])),ci95_low=lo,ci95_high=hi,
                                     initialization_years=n,block_years=3,replicates=4000))
    pd.DataFrame(history).to_csv(OUT/'historical_skill_2015_2024.csv',index=False)
    pd.DataFrame(boot).to_csv(OUT/'paired_bootstrap_2015_2024.csv',index=False)
    # Sensitivity against the previous proxy experiment on exactly shared dates.
    old=pd.read_csv(previous.OUT/'all_forecasts.csv',parse_dates=['init','target'])
    old=old[old.protocol.eq('raw_oras5')&old.year.isin([2015,2026])&old.month.isin([1,2])&old.lead.gt(0)]
    comparison=[]
    for name,frame in [('standard',f),('previous_proxy',old)]:
        frame=frame[frame.year.isin([2015,2026])&frame.month.isin([1,2])&frame.lead.gt(0)]
        for keys,g in frame.groupby(['family','year','month','model']):
            for var in ['T','H']:
                v=g.dropna(subset=['obs_'+var])
                comparison.append(dict(zip(['family','year','month','model'],keys),definition=name,variable=var,n=len(v),
                                       rmse=np.sqrt(np.mean((v[var]-v['obs_'+var])**2))))
    pd.DataFrame(comparison).to_csv(OUT/'standard_vs_previous_proxies_same_starts.csv',index=False)
    return table


def save(fig,name):
    for ext in ['png','pdf']:fig.savefig(OUT/f'{name}.{ext}',dpi=230,bbox_inches='tight',facecolor='white')
    plt.close(fig)


def plot_events(f,family,month,years):
    g=f[f.family.eq(family)&f.month.eq(month)&f.year.isin(years)]
    names=['Observed',*MODELS]
    handles=[Line2D([0],[0],color=COLORS[n],ls=STYLES[n],lw=2.3,label=LABELS[n]) for n in names]
    limits={}
    for var in ['T','H']:
        vals=np.r_[g[var],g['obs_'+var].dropna(),0];lo,hi=vals.min(),vals.max()
        limits[var]=(lo-.13*(hi-lo),hi+.15*(hi-lo))
    note=('Published UW MCA PMM-SST and PMM-wind; fixed 1950–2005 patterns. Forecast coefficients use 1982–previous December.\n'
          'T/H: raw ORAS5, past-only linear detrending; display anomalies relative to 1982–2014 monthly climatology. H: mean D20 (m).\n'
          'Future PMM evolves internally. Current-vintage retrospective experiment; historical data-release delays are not reproduced.\n'
          'Published PMM ends Feb 2026; T/H observations end Sep 2026. Stars: monthly-mean initialization, available after month end.')
    cols=len(years)
    fig,axes=plt.subplots(2,cols,figsize=(13 if cols==2 else 10.8,8.5),squeeze=False,sharex='col',sharey='row')
    fig.subplots_adjust(top=.77,bottom=.245,hspace=.28,wspace=.14)
    fig.suptitle(f'Standard PMM ablation | {FAMILIES[family]} | {previous.MONTHS[month-1]} start',fontsize=15,y=.985)
    fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.5,.95),frameon=False,fontsize=10)
    for col,year in enumerate(years):
        c=g[g.year.eq(year)];base=c[c.model.eq('RO')].sort_values('lead')
        for row,var in enumerate(['T','H']):
            ax=axes[row,col]
            last=int(base.loc[base['obs_'+var].notna(),'lead'].max())
            if last<12:ax.axvspan(last+.12,12.2,color='#edf0f3',zorder=-3)
            for name in names:
                d=base if name=='Observed' else c[c.model.eq(name)].sort_values('lead')
                ax.plot(d.lead,d['obs_'+var] if name=='Observed' else d[var],color=COLORS[name],ls=STYLES[name],lw=2.2,
                        marker='o' if name=='Observed' else None,ms=3.5)
            ax.scatter(0,base['obs_'+var].iloc[0],s=110,marker='*',color=COLORS['Observed'],zorder=10)
            ax.set(title=f'{year} | '+('Niño3.4' if var=='T' else 'WWV proxy'),xlim=(-.2,12.2),ylim=limits[var])
            ax.set_xticks([0,3,6,9,12],[previous.MONTHS[(month-1+k)%12]+('\n+1 year' if month-1+k>=12 else '') for k in [0,3,6,9,12]])
            ax.axhline(0,color='.5',lw=.7);ax.grid(alpha=.15)
            if col==0:ax.set_ylabel('Niño3.4 anomaly (°C)' if var=='T' else 'WWV proxy: D20 anomaly (m)')
    fig.text(.055,.025,note,fontsize=8.5,linespacing=1.6,color='#4e5660',va='bottom')
    save(fig,f'{family}_standard_pmm_time_series_init_{month:02d}')
    fig,axes=plt.subplots(1,cols,figsize=(13 if cols==2 else 10.8,8),squeeze=False,sharex=True,sharey=True)
    fig.subplots_adjust(top=.76,bottom=.28,wspace=.15)
    fig.suptitle(f'Niño3.4–WWV | Standard PMM ablation | {FAMILIES[family]} | {previous.MONTHS[month-1]}',fontsize=14,y=.985)
    fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.5,.95),frameon=False,fontsize=10)
    for ax,year in zip(axes.ravel(),years):
        c=g[g.year.eq(year)];base=c[c.model.eq('RO')].sort_values('lead')
        for name in names:
            d=base if name=='Observed' else c[c.model.eq(name)].sort_values('lead')
            pre='obs_' if name=='Observed' else '';d=d.dropna(subset=[pre+'T',pre+'H'])
            xx,yy=d[pre+'T'].to_numpy(),d[pre+'H'].to_numpy()
            ax.plot(xx,yy,color=COLORS[name],ls=STYLES[name],lw=2.1,marker='o',ms=3)
            for k in range(1,len(d)):
                if int(d.lead.iloc[k])%3==0 or k==len(d)-1:
                    ax.annotate('',xy=(xx[k],yy[k]),xytext=(xx[k-1],yy[k-1]),arrowprops=dict(arrowstyle='->',color=COLORS[name],lw=1.3))
                    if name=='Observed':
                        absolute=month-1+int(d.lead.iloc[k]);lab=previous.MONTHS[absolute%12]+(' +1' if absolute>=12 else '')
                        ax.annotate(lab,(xx[k],yy[k]),xytext=(5,6),textcoords='offset points',fontsize=8)
        ax.scatter(base.obs_T.iloc[0],base.obs_H.iloc[0],s=120,marker='*',color=COLORS['Observed'],zorder=10)
        ax.set(title=str(year),xlabel='Niño3.4 anomaly (°C)',xlim=limits['T'],ylim=limits['H'])
        ax.axhline(0,color='.5',lw=.7);ax.axvline(0,color='.5',lw=.7);ax.grid(alpha=.15)
    axes[0,0].set_ylabel('WWV proxy: mean D20 anomaly (m)')
    fig.text(.055,.025,note,fontsize=8.5,linespacing=1.6,color='#4e5660',va='bottom')
    save(fig,f'{family}_standard_pmm_phase_space_init_{month:02d}')


def plot_pmm(p):
    reference=p.loc['1982':'2014']
    z=(p-reference.mean())/reference.std()
    fig,axes=plt.subplots(2,1,figsize=(10.5,7),sharex=True,sharey=True)
    fig.subplots_adjust(top=.88,bottom=.20,hspace=.38)
    fig.suptitle('Published standard PMM | SST and wind components',fontsize=16)
    for ax,variable,title in zip(axes,P,['PMM-SST: ocean surface temperature','PMM-wind: near-surface winds']):
        for year,color in [(2015,'#D55E00'),(2026,'#2878B5')]:
            v=z.loc[str(year),variable]
            ax.plot(v.index.month,v,marker='o',color=color,lw=2,label=str(year))
        ax.set(title=title,ylabel='Standard deviations\n(1982–2014)',xlim=(.7,12.3))
        ax.axhline(0,color='.5',lw=.7);ax.grid(alpha=.15);ax.legend(frameon=False,ncol=2)
    axes[-1].set_xticks(range(1,13),previous.MONTHS)
    fig.text(.09,.03,'Source: Dan Vimont / University of Wisconsin published MCA expansion coefficients; no local proxy substitution.\n'
             'Standardization is for display only. Published 2026 observations stop in February; no interpolation beyond that date.\n'
             'The SST coefficient represents the coupled mode; the wind coefficient also contains external atmospheric forcing.',
             fontsize=9,color='#4e5660',linespacing=1.6)
    save(fig,'standard_pmm_SST_wind_2015_2026')


def plot_skill():
    h=pd.read_csv(OUT/'historical_skill_2015_2024.csv')
    for family in FAMILIES:
        fig,axes=plt.subplots(1,2,figsize=(11.8,5.6))
        fig.subplots_adjust(top=.75,bottom=.23,wspace=.25)
        fig.suptitle(f'Standard PMM | 2015–2024 monthly starts | {FAMILIES[family]}',fontsize=14,y=.98)
        handles=[Line2D([0],[0],color=COLORS[m],ls=STYLES[m],lw=2,label=LABELS[m]) for m in MODELS]
        fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.5,.91),frameon=False,fontsize=9)
        for ax,var in zip(axes,['T','H']):
            for name in MODELS:
                g=h[h.family.eq(family)&h.variable.eq(var)&h.model.eq(name)].sort_values('lead')
                ax.plot(g.lead,g.rmse,color=COLORS[name],ls=STYLES[name],lw=2.2)
            ax.set(xlabel='Lead (months)',ylabel='Niño3.4 RMSE (°C)' if var=='T' else 'WWV proxy RMSE (m)',xlim=(1,12))
            ax.grid(alpha=.15)
        fig.text(.065,.045,'120 monthly starts per lead; same dates and training windows for all four models. Lead zero excluded.\n'
                 'Current-vintage retrospective indices. This 10-year period is short; see paired block-bootstrap intervals in the results table.',
                 fontsize=9,color='#4e5660',linespacing=1.6)
        save(fig,f'{family}_historical_skill_2015_2024')


def write_report(raw,p,cross,qa,table,elapsed):
    meta=dict(pmm_source='https://www.aos.wisc.edu/dvimont/MModes/RealTime/PMM.txt',
              method_source='https://www.aos.wisc.edu/dvimont/MModes/PMM.html',
              pmm_definition='Published canonical MCA SST/wind expansion coefficients; NCEP-NCAR SST and 10m wind; fixed 1950–2005 patterns; not PMM_RAW.',
              pmm_source_sha256=hashlib.sha256((SOURCE/'PMM_uw.txt').read_bytes()).hexdigest(),
              pmm_observed_end=str(p.index[-1].date()),oras5_observed_end=str(raw.index[-1].date()),noaa_crosscheck=cross,
              pmm_model_preprocessing='Subtract each prior-year training mean only. Existing linear RO scales all states by their training standard deviation. No extra ENSO removal, smoothing, or trend subtraction of the published PMM.',
              th_preprocessing='Unchanged prior experiment: monthly climatology and linear trend from training years, display background restored to 1982–2014 climatology.',
              model_training='1982–previous December, refit annually, all model variants use the same T/H and dates',
              coefficient_models=MODELS,
              historical_evaluation='Available folds 2006–2026; aggregate and bootstrap 2015–2024 starts, after frozen preprocessing selection; 120 monthly starts per lead.',
              limitations=['Published PMM stops February 2026: no March/May 2026 initialization.',
                           'Current-vintage reanalysis and published indices; historical release delays and all upstream preprocessing vintages were not reconstructed.',
                           'Fixed MCA pattern period includes years through 2005, so no earlier forecasts are presented as out of sample.',
                           'Post-selection uncertainty uses only ten initialization years; overlapping targets and multiple lead/component tests limit significance claims.',
                           'Nonlinear results use the XRO numerical core for 2/3/4-state models, not the complete ten-state XRO.'],
              qa=qa,runtime_seconds=elapsed)
    (OUT/'methods_and_validation.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    lines=['标准PMM（MCA）替换及RO消融实验：2026-10-14','',
           '数据与定义：',
           '直接使用Dan Vimont / University of Wisconsin发布的PMM.txt，分别读取SST和Wind列。它们是标准MCA展开系数，不是此前联合EOF或区域SST代理指标，也不是PMM_RAW。',
           '作者说明：使用NCEP-NCAR的SST及10米风，范围21S–32N、175E–95W；先去季节循环、趋势及冷舌指数CTI影响，使用面积权重；MCA空间模态固定为1950–2005。估计模态时使用三个月滑动平均，但发布的月度投影指数不做这一步平滑。',
           '方法：https://www.aos.wisc.edu/dvimont/MModes/PMM.html',
           '数据：https://www.aos.wisc.edu/dvimont/MModes/RealTime/PMM.txt',
           f'实际下载文件截至{p.index[-1]:%Y-%m}；NOAA镜像截至2025-04。两列共同月份逐值相同，最大绝对差为{max(c["max_absolute_difference"] for c in cross):.2g}。下载时间、响应元数据和SHA256均已归档。',
           'PMM-SST体现海温耦合模态；PMM-wind既包含耦合风响应，也包含外部大气强迫，不能将二者视为完全独立的物理驱动。','',
           '四组实验：',
           'RO=[T,H]；RO+PMM-SST=[T,H,Ps]；RO+PMM-wind=[T,H,Pw]；RO+both=[T,H,Ps,Pw]。',
           '主实验保留原线性季节RO：月差分回归、年度正余弦、训练期标准差缩放、ridge alpha=1。另列相同输入的非线性RO（XRO核心）稳健性结果；不是完整十状态XRO。',
           '各模型均在1982年至起报前一年的12月拟合。T/H沿用前次原始ORAS5、训练期月气候态及线性趋势；趋势阶数已在2015年前的二状态RO验证中固定，本次不重新挑选。',
           '标准PMM已在源端预处理，模型仅减去训练期均值，不再次回归剔除Niño3.4、不再做EOF/MCA、不进行额外趋势或滑动平均。起报之后Ps/Pw由模型状态方程积分，不喂入未来实测值。',
           '模型多一个或两个状态会改变拟合系数；这是配对重拟合消融，不能把所有差异都等同于独立的因果贡献。','',
           '可用时段：',
           '2015和2026可共同比较1、2月起报。另提供2015年3、5月起报图。标准PMM缺少2026年3月以后数值，因此没有构造2026年3、5月实测初值，也没有用代理指标补齐。',
           'ORAS5 T/H可检验到2026年9月：2026年1月起报验证8个月、2月起报验证7个月；后面的预报可画出但没有验证实况。每个起报月使用整月平均，至少到月底以后才可用。',
           '本实验使用当前修订资料做回报，未重建当年的数据发布时滞或全部源端预处理版本，因此不称为完全实时预报。','',
           '主线性模型的同月份结果（RMSE，越小越好；括号为相对RO下降百分比）：']
    for _,row in table[table.family.eq('linear')&table.month.isin([1,2,3,5])&table.variable.isin(['T','H'])].iterrows():
        unit='°C' if row.variable=='T' else 'm'
        lines.append(f'{int(row.year)}年{int(row.month)}月，{row.variable}，{int(row.n)}个验证月：RO={row.RO:.3f}{unit}；'
                     f'SST={row.RO_SST:.3f}（{row.RO_SST_gain_percent:+.1f}%）；wind={row.RO_wind:.3f}（{row.RO_wind_gain_percent:+.1f}%）；'
                     f'both={row.RO_both:.3f}（{row.RO_both_gain_percent:+.1f}%）。')
    lines+=['','结果解释：',
            '标准PMM-SST改善了2015年1、2、3月起报的温度预报，但各组仍明显低估事件发展；2015年3月起报的H误差反而增大。',
            '2026年1、2月起报中，标准PMM-SST的温度增益仅约1–3%，风分量没有改善；同时加入两个分量也没有稳定超过只加海温。非线性RO对这两个2026起报的温度改善同样很小。',
            '不能把这些结果写成“加入标准PMM已经显著解决2015/2026的预报问题”。2026年后续月份缺少发布的PMM实测指数，不能推断春季起报的标准PMM增益。','',
            '历史检验与限制：',
            'MCA模态固定期包含2005年，历史起报从2006年开始；用于汇总技能与区间的是预处理选择之后的2015–2024年全部月起报。',
            '每个提前期包含120个起报；采用按年份配对、连续三年循环块、4000次重采样估计相对RO的RMSE增益95%区间。仅10年样本且检验多个分量和提前期，不用两个事件或单个显著格点证明普遍提升。',
            '各模型T/H实况和绘图零点完全一致。WWV纵轴采用平均D20异常（m），不是总体积WWV。','',
            '数值核查：',json.dumps(qa,ensure_ascii=False,indent=2),'',
            '主要文件：linear_standard_pmm_time_series_init_01/02；linear_standard_pmm_phase_space_init_01/02；standard_pmm_SST_wind_2015_2026；event_incremental_skill.csv；paired_bootstrap_2015_2024.csv。',
            '新结果保存在独立目录；先前代理指标实验保留，用于同起报月份对照，不作为标准PMM结果引用。']
    (OUT/'experiment_notes_cn.txt').write_text('\n'.join(lines)+'\n')


def main():
    start=time.time()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    raw,p,cross=load_sources()
    print('Sources:',cross,'published end',p.index[-1],flush=True)
    f,qa,_=run_forecasts(raw,p)
    table=scores(f)
    for family in FAMILIES:
        for month,years in [(1,[2015,2026]),(2,[2015,2026]),(3,[2015]),(5,[2015])]:
            plot_events(f,family,month,years)
    plot_pmm(p);plot_skill()
    write_report(raw,p,cross,qa,table,time.time()-start)
    print(table[table.family.eq('linear')&table.month.isin([1,2,3])&table.variable.isin(['T','H'])].to_string(index=False),flush=True)
    print('Finished',OUT,flush=True)


if __name__=='__main__':main()
