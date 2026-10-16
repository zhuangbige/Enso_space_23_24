#!/usr/bin/env python3
"""Same-source manuscript RO reconstruction and past-only canonical PMM ablations.
Run only after build_paper_ro_indices.py. Protocol frozen in output directory.
"""
from pathlib import Path
import os,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'tmp/ro_pmm_mpl'))
import numpy as np,pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import paper_ro_slim as slim
OUT=ROOT/'outputs/research_2026/paper_ro_pmm_20261014'
SOURCE=ROOT/'data/derived/research_2026/paper_ro_baseline_20261014'
PMM=ROOT/'data/raw/climate_indices/standard_pmm_20261014/PMM_uw.txt'
V=['Nino34','WWV'];P=['PMM_SST','PMM_wind']
MODELS={'RO':V,'RO_SST':V+[P[0]],'RO_wind':V+[P[1]],'RO_both':V+P}
LABELS={'RO':'RO','RO_SST':'+ PMM-SST','RO_wind':'+ PMM-wind','RO_both':'+ both PMM','cut_both':'Both: PMM → T/h cut'}
COLORS={'RO':'#2878B5','RO_SST':'#D55E00','RO_wind':'#009E73','RO_both':'#8B55A2','cut_both':'#888888'}
STYLES={'RO':'--','RO_SST':'-','RO_wind':'-.','RO_both':':','cut_both':'--'}


def load():
    raw=pd.read_csv(SOURCE/'raw_indices.csv',parse_dates=['time']).set_index('time')[V]
    p=pd.read_csv(PMM,sep=r'\s+');p.index=pd.to_datetime(dict(year=p.Year,month=p.Mo,day=1))
    p=p[['SST','Wind']].rename(columns={'SST':P[0],'Wind':P[1]})
    assert np.isfinite(p.to_numpy()).all()
    clim=raw.loc['1991':'2020'].groupby(raw.loc['1991':'2020'].index.month).mean()
    return raw,p,clim


def prepare(raw,p,start,end,paper=False,trend_end=None):
    train=raw.loc[start:end,V];assert train.notna().all().all()
    ref=raw.loc['1991':'2020',V] if paper else train
    clim=ref.groupby(ref.index.month).mean()
    anom=raw-clim.loc[raw.index.month].set_axis(raw.index)
    tx=slim.decimal_time(raw.index);mask=(raw.index>=pd.Timestamp(start))&(raw.index<=pd.Timestamp(trend_end or end))
    center=tx[mask].mean();design=np.column_stack([np.ones(len(tx)),tx-center])
    beta=np.linalg.lstsq(design[mask],anom.loc[mask].to_numpy(),rcond=None)[0]
    processed=pd.DataFrame(anom.to_numpy()-design@beta,index=raw.index,columns=V)
    pm=p.loc[start:end].mean()
    processed[P]=p.reindex(raw.index)-pm
    meta=dict(clim=clim.to_numpy(),beta=beta,center=center,pmm_mean=pm.to_numpy(),start=start,end=end,paper=paper)
    return processed,meta


def restore(values,dates,meta):
    bg=meta['clim'][dates.month.to_numpy()-1]+np.column_stack([np.ones(len(dates)),slim.decimal_time(dates)-meta['center']])@meta['beta']
    return values[:,:2]+bg


def jsonable(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    raise TypeError(type(x))


def single_rows(raw,clim,a,meta,model,init,protocol,name,cut=False):
    dates=pd.date_range(init,periods=13,freq='MS')
    fc=slim.predict(model,a.loc[init,model['columns']].to_numpy(),init.month,cut_pmm=cut)
    restored=restore(fc,dates,meta)
    disp=clim.loc[dates.month].to_numpy()
    truth=raw.reindex(dates).to_numpy()-disp;fcdisp=restored-disp
    truth_model=a.reindex(dates)[V].to_numpy()
    assert np.isfinite(fcdisp).all()
    assert abs(fcdisp[0]-truth[0]).max()<1e-9
    return [dict(protocol=protocol,model=name,year=init.year,month=init.month,init=init,target=t,lead=j,
                 T=fcdisp[j,0],H=fcdisp[j,1],obs_T=truth[j,0],obs_H=truth[j,1],
                 T_model=fc[j,0],H_model=fc[j,1],obs_T_model=truth_model[j,0],obs_H_model=truth_model[j,1]) for j,t in enumerate(dates)]


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    raw,p,clim=load();qa=slim.numerical_qa();rows=[];audits=[];save_fits={}
    # First reconstruct the baseline only. These configurations were fixed
    # before any same-source result was inspected; no PMM in this stage.
    cases={'paper_main':dict(order=2,method='perturb2'),
           'paper_exact':dict(order=2,method='exact'),
           'paper_annual':dict(order=1,method='perturb2'),
           'paper_three_harmonics':dict(order=3,method='perturb2'),
           'paper_trend_to_Apr2025':dict(order=2,method='perturb2',trend_end='2025-04-01')}
    for case,kw0 in cases.items():
        kw=kw0.copy();trend_end=kw.pop('trend_end',None)
        a,meta=prepare(raw,p,'2002-01-01','2024-12-01',True,trend_end)
        m=slim.fit(a.loc['2002':'2024',V],**kw)
        for year in (range(2002,2025) if case=='paper_main' else [2015]):
            for month in range(1,7):
                rows+=single_rows(raw,clim,a,meta,m,pd.Timestamp(year,month,1),case,'RO')
        save_fits[case]=dict(model=m,preprocessing=meta)
        print('baseline completed',case,flush=True)
    # Causal folds. All twelve start months; one frozen model per start year.
    for protocol,start,years in [('past_1982','1982-01-01',range(2006,2027)),('past_2002','2002-01-01',range(2012,2027))]:
        for year in years:
            end=f'{year-1}-12-01';a,meta=prepare(raw,p,start,end)
            fits={name:slim.fit(a.loc[start:end,cols]) for name,cols in MODELS.items()}
            initdates=a.index[(a.index.year==year)&a.notna().all(axis=1)]
            for name,m in fits.items():
                for init in initdates:rows+=single_rows(raw,clim,a,meta,m,init,protocol,name)
                audits.append(dict(protocol=protocol,year=year,model=name,train_start=start,train_end=end,n_months=len(a.loc[start:end]),n_states=len(MODELS[name]),max_init_month=max(initdates.month),**m['diag']))
            for init in initdates:rows+=single_rows(raw,clim,a,meta,fits['RO_both'],init,protocol,'cut_both',True)
            if year in [2015,2026]:
                for name,m in fits.items():save_fits[f'{protocol}_{year}_{name}']=dict(model=m,preprocessing=meta)
                if protocol=='past_1982':
                    init=pd.Timestamp(year,1,1);changed_raw=raw.copy();changed_p=p.copy()
                    changed_raw.loc[changed_raw.index>init]+=999;changed_p.loc[changed_p.index>init]+=999
                    aa,mm=prepare(changed_raw,changed_p,start,end)
                    for name,m in fits.items():
                        m2=slim.fit(aa.loc[start:end,MODELS[name]])
                        f1=slim.predict(m,a.loc[init,MODELS[name]].to_numpy(),1)
                        f2=slim.predict(m2,aa.loc[init,MODELS[name]].to_numpy(),1)
                        diff=float(abs(f1-f2).max());assert diff<1e-10
                        qa[f'future_perturbation_{year}_{name}']=diff
                        conv=float(abs(f1-slim.predict(m,a.loc[init,MODELS[name]].to_numpy(),1,steps=48)).max())
                        assert conv<1e-5;qa[f'rk4_convergence_{year}_{name}']=conv
                    # Test coordinate-unit invariance, including normalization.
                    transformed=a.loc[start:end,MODELS['RO_both']]*[3,100,.2,10]
                    ms=slim.fit(transformed);fscaled=slim.predict(ms,a.loc[init,MODELS['RO_both']].to_numpy()*[3,100,.2,10],1)/[3,100,.2,10]
                    ref=slim.predict(fits['RO_both'],a.loc[init,MODELS['RO_both']].to_numpy(),1)
                    qa[f'unit_invariance_{year}']=float(abs(fscaled-ref).max());assert abs(fscaled-ref).max()<1e-8
            print('independent fold',protocol,year,'starts',len(initdates),flush=True)
    f=pd.DataFrame(rows);f.to_csv(OUT/'monthly_forecasts.csv',index=False)
    pd.DataFrame(audits).to_csv(OUT/'fit_audit.csv',index=False)
    (OUT/'models_and_preprocessing.json').write_text(json.dumps(save_fits,default=jsonable,indent=2))
    (OUT/'numerical_QA.json').write_text(json.dumps(qa,indent=2))
    seasonal=[]
    for keys,g in f.groupby(['protocol','model','init']):
        g=g.sort_values('lead');ini=pd.Timestamp(keys[2]);issue=ini+pd.offsets.MonthBegin(1)
        for lead in range(1,10):
            block=g[g.lead.between(lead,lead+2)]
            assert len(block)==3
            vals={c:float(block[c].mean()) if block[c].notna().all() else np.nan for c in ['T','H','obs_T','obs_H','T_model','H_model','obs_T_model','obs_H_model']}
            seasonal.append(dict(protocol=keys[0],model=keys[1],init=ini,issue=issue,year=issue.year,month=issue.month,lead=lead,target=issue+pd.offsets.MonthBegin(lead),**vals))
    s=pd.DataFrame(seasonal);s.to_csv(OUT/'seasonal_forecasts.csv',index=False)
    score_all(f,s);plot_all(f,s,raw,clim)
    print('QA',json.dumps(qa),flush=True)


def metrics(g):
    ret={}
    for var in ['T','H']:
        a=g[[var,'obs_'+var]].dropna();err=a[var]-a['obs_'+var]
        ret.update({var+'_n':len(a),var+'_RMSE':float(np.sqrt(np.mean(err**2))),var+'_r':float(a.corr().iloc[0,1]) if len(a)>2 else np.nan})
    return ret


def bootstrap(g,base,var):
    keys=['init','lead','target'];m=g[keys+[var,'obs_'+var]].merge(base[keys+[var]],on=keys,suffixes=('','_RO')).dropna()
    m['year']=m.init.dt.year;m['sq']=(m[var]-m['obs_'+var])**2;m['sq0']=(m[var+'_RO']-m['obs_'+var])**2
    sums=m.groupby('year')[['sq','sq0']].sum();counts=m.groupby('year').size()
    rng=np.random.default_rng(20261014);n=len(sums);vals=[]
    for i in range(2000):
        starts=rng.integers(0,n,size=int(np.ceil(n/3)))
        ids=np.concatenate([(v+np.arange(3))%n for v in starts])[:n]
        ss=sums.to_numpy()[ids].sum(axis=0)
        vals.append(100*(1-np.sqrt(ss[0]/ss[1])))
    point=100*(1-np.sqrt(m.sq.mean()/m.sq0.mean()))
    return dict(variable=var,improvement_pct=point,CI_low=np.percentile(vals,2.5),CI_high=np.percentile(vals,97.5),n_years=n,n_pairs=len(m))


def score_all(f,s):
    records=[]
    for label,frame in [('monthly',f),('seasonal',s)]:
        if label=='monthly':frame=frame[frame.lead.between(1,9)]
        for (protocol,model,year),g in frame.groupby(['protocol','model','year']):
            records.append(dict(target_type=label,protocol=protocol,model=model,window=f'year_{year}_all_starts',**metrics(g)))
            if protocol.startswith('paper'):
                z=g[g.month.between(2,6)]
                records.append(dict(target_type=label,protocol=protocol,model=model,window=f'year_{year}_FebJun',**metrics(z)))
                native=z.drop(columns=['T','H','obs_T','obs_H']).rename(columns={v+'_model':v for v in ['T','H','obs_T','obs_H']})
                records.append(dict(target_type=label+'_detrended',protocol=protocol,model=model,window=f'year_{year}_FebJun',**metrics(native)))
        for (protocol,model),g in frame.groupby(['protocol','model']):
            for low,high in [(2006,2024),(2012,2024),(2015,2024)]:
                z=g[g.year.between(low,high)]
                if len(z) and z.year.min()==low and z.year.max()==high:records.append(dict(target_type=label,protocol=protocol,model=model,window=f'{low}_{high}',**metrics(z)))
    for (protocol,model,year,month),g in f[f.lead.between(1,12)&f.year.isin([2015,2026])].groupby(['protocol','model','year','month']):
        records.append(dict(target_type='monthly',protocol=protocol,model=model,window=f'{year}_init_{month:02d}_lead1_12',**metrics(g)))
    pd.DataFrame(records).to_csv(OUT/'scores.csv',index=False)
    lead=[];ci=[]
    hist=f[f.protocol.str.startswith('past')&f.year.between(2006,2024)&f.lead.between(1,9)]
    for (protocol,model,k),g in hist.groupby(['protocol','model','lead']):lead.append(dict(protocol=protocol,model=model,lead=k,**metrics(g)))
    pd.DataFrame(lead).to_csv(OUT/'skill_by_lead.csv',index=False)
    for protocol,gg in hist.groupby('protocol'):
        for low,high in [(2006,2024),(2012,2024),(2015,2024)]:
            sub=gg[gg.year.between(low,high)]
            if not len(sub) or sub.year.min()!=low or sub.year.max()!=high:continue
            for name,g in sub.groupby('model'):
                if name=='RO':continue
                for var in ['T','H']:ci.append(dict(protocol=protocol,model=name,period=f'{low}_{high}',**bootstrap(g,sub[sub.model.eq('RO')],var)))
    pd.DataFrame(ci).to_csv(OUT/'PMM_improvement_block_bootstrap.csv',index=False)


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'medium','savefig.facecolor':'white'})


def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=220,bbox_inches='tight')
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight')
    plt.close(fig)


def plot_all(f,s,raw,clim):
    style();obs=raw-clim.loc[raw.index.month].set_axis(raw.index)
    handles=[Line2D([0],[0],color='#222C38',lw=2.6,label='Observed')]+[Line2D([0],[0],color=COLORS[n],ls=STYLES[n],lw=2,label=LABELS[n]) for n in MODELS]
    # User-requested free forecasts: shared initial conditions, no resets.
    for year,months in [(2015,[1,2,3]),(2026,[1,2])]:
        for month in months:
            init=pd.Timestamp(year,month,1);dates=pd.date_range(init,periods=13,freq='MS')
            g=f[f.protocol.eq('past_1982')&f.init.eq(init)&f.model.isin(MODELS)]
            fig,axes=plt.subplots(1,3,figsize=(16.2,5.2),gridspec_kw={'width_ratios':[1,1,1.2]})
            fig.subplots_adjust(top=.79,bottom=.24,wspace=.29)
            for j,var in enumerate(['T','H']):
                ax=axes[j];vv=V[j];oo=obs.reindex(dates)[vv]
                ax.plot(dates,oo,color='#222C38',lw=2.7,marker='o',ms=3)
                last=obs[vv].last_valid_index()
                for name,v in g.groupby('model'):
                    seen=v.target<=last
                    ax.plot(v.target[seen],v[var][seen],color=COLORS[name],ls=STYLES[name],lw=2)
                    future=v.target>=last
                    if future.any():ax.plot(v.target[future],v[var][future],color=COLORS[name],ls=STYLES[name],lw=1.6,alpha=.35)
                ax.set_ylabel('Niño3.4 anomaly (°C)' if j==0 else 'WWV / mean D20 anomaly (m)')
                ax.set_xticks(dates[[0,3,6,9,12]],[d.strftime('%b\n%Y') for d in dates[[0,3,6,9,12]]])
                ax.set_title('(a) SST forecast' if j==0 else '(b) Recharge forecast',loc='left')
                ax.axhline(0,color='.6',lw=.7);ax.grid(alpha=.15)
            ax=axes[2];oo=obs.reindex(dates)
            ax.plot(oo.Nino34,oo.WWV,color='#222C38',lw=2.7,marker='o',ms=3)
            ax.scatter(oo.Nino34.iloc[0],oo.WWV.iloc[0],color='#222C38',marker='*',s=130,zorder=7)
            last=min(obs[v].last_valid_index() for v in V)
            for name,v in g.groupby('model'):
                seen=v.target<=last
                ax.plot(v['T'][seen],v.H[seen],color=COLORS[name],ls=STYLES[name],lw=2)
                future=v.target>=last
                if future.any():ax.plot(v['T'][future],v.H[future],color=COLORS[name],ls=STYLES[name],lw=1.6,alpha=.35)
                # Final verified point marked; future endpoint never shown as truth.
                end=v[seen].iloc[-1];ax.scatter(end['T'],end.H,s=26,color=COLORS[name])
            for k in [3,6,9,12]:
                if oo.iloc[k].notna().all():
                    ax.annotate(dates[k].strftime('%b %Y') if k==12 else dates[k].strftime('%b'),(oo.Nino34.iloc[k],oo.WWV.iloc[k]),xytext=(5,5),textcoords='offset points',fontsize=9)
                    prev=oo.iloc[k-1];cur=oo.iloc[k]
                    ax.annotate('',xy=(cur.Nino34,cur.WWV),xytext=(prev.Nino34,prev.WWV),arrowprops=dict(arrowstyle='->',color='#222C38',lw=1.8))
            ax.set(xlabel='Niño3.4 anomaly (°C)',ylabel='WWV / mean D20 anomaly (m)')
            ax.set_title('(c) Free forecast in phase space',loc='left');ax.axhline(0,color='.6',lw=.7);ax.axvline(0,color='.6',lw=.7);ax.grid(alpha=.15)
            # Same physical axes across events; include every forecast point.
            for ax,var in [(axes[0],'T'),(axes[1],'H')]:
                allvals=f[f.protocol.eq('past_1982')&f.year.isin([2015,2026])&f.month.isin([1,2,3])&f.model.isin(MODELS)][[var,'obs_'+var]].to_numpy()
                lo,hi=np.nanmin(allvals),np.nanmax(allvals);pad=(hi-lo)*.08;ax.set_ylim(lo-pad,hi+pad)
            axes[2].set_xlim(axes[0].get_ylim());axes[2].set_ylim(axes[1].get_ylim())
            fig.suptitle(f'{year} | {init.strftime("%B")} monthly-state initialization | past-only fit through {year-1}',fontsize=17,y=.99)
            fig.legend(handles=handles,ncol=5,loc='upper center',bbox_to_anchor=(.5,.94),frameon=False)
            fig.text(.06,.055,'ERSSTv5 + GODAS; canonical MCA PMM. Forecasts use no future observed PMM. Stars mark the shared initial state.\n'
                     'Common display climatology: 1991–2020. Faint segments extend beyond available observations and are not scored.\n'
                     f'Each model is re-fitted on 1982–{year-1}; current-vintage retrospective hindcast. Monthly-state dates are not issue dates.',fontsize=9,color='#4c5560',linespacing=1.5)
            save(fig,f'event_{year}_init_{month:02d}')
    # Transparent reproduction of the supplied paper, both time conventions.
    colors=plt.cm.Oranges(np.linspace(.35,.9,5))
    fig,axes=plt.subplots(2,2,figsize=(13,8.7),sharex=True,sharey=True)
    fig.subplots_adjust(top=.87,bottom=.18,hspace=.34,wspace=.16)
    for row,protocol in enumerate(['paper_main','past_1982']):
        for col,(frame,target_type) in enumerate([(f,'monthly'),(s,'seasonal')]):
            ax=axes[row,col];g=frame[frame.protocol.eq(protocol)&frame.model.eq('RO')&frame.year.eq(2015)&frame.month.between(2,6)&frame.lead.between(1,9)]
            truth=obs.Nino34 if col==0 else obs.Nino34.rolling(3,center=True).mean()
            oo=truth.loc['2015-01':'2016-05'];ax.plot(oo.index,oo,color='#222C38',lw=2.7)
            for color,(month,v) in zip(colors,g.groupby('month')):ax.plot(v.target,v['T'],color=color,lw=1.8,label=pd.Timestamp(2015,month,1).strftime('%b'))
            m=metrics(g);ax.text(.03,.92,f'r = {m["T_r"]:.2f}; RMSE = {m["T_RMSE"]:.2f} °C',transform=ax.transAxes,va='top',fontsize=10)
            title=('Paper-window fit: 2002–2024' if row==0 else 'Past-only fit: 1982–2014')+'\n'+('Feb–Jun monthly states → monthly leads 1–9' if col==0 else 'Feb–Jun issues → 3-month seasons, leads 1–9')
            ax.set_title(title,fontsize=11,loc='left');ax.grid(alpha=.15);ax.axhline(0,color='.6',lw=.7)
            ax.set_xticks(pd.to_datetime(['2015-01-01','2015-04-01','2015-07-01','2015-10-01','2016-01-01','2016-04-01']),['Jan\n2015','Apr','Jul','Oct','Jan\n2016','Apr'])
            if col==0:ax.set_ylabel('Niño3.4 anomaly (°C)')
    axes[0,0].legend(ncol=5,loc='lower right',fontsize=8,frameon=False)
    fig.suptitle('RO baseline reconstruction | ERSSTv5 + GODAS | 2015',fontsize=17,y=.98)
    fig.text(.065,.035,'Top row uses 2015 and later data in fitting: it is a reproduction diagnostic, not independent forecast skill.\n'
             'sLIM: pentad interpolation, lagged covariances, annual + semiannual cycles, second-order perturbation solution.\n'
             'The manuscript does not fully specify RO date alignment or preprocessing; both conventions are reported without selecting the better result.',fontsize=9,color='#4c5560',linespacing=1.5)
    save(fig,'baseline_2015_reconstruction')
    # Lead-dependent validation skill, identical sample sets per model.
    lead=pd.read_csv(OUT/'skill_by_lead.csv');fig,axes=plt.subplots(1,2,figsize=(12,4.6));fig.subplots_adjust(top=.77,bottom=.23,wspace=.25)
    for j,var in enumerate(['T','H']):
        ax=axes[j]
        for name in MODELS:
            g=lead[lead.protocol.eq('past_1982')&lead.model.eq(name)]
            ax.plot(g.lead,g[var+'_RMSE'],color=COLORS[name],ls=STYLES[name],marker='o',ms=4,lw=2)
        ax.set(xlabel='Monthly lead',ylabel='RMSE (°C)' if j==0 else 'RMSE (m)',title='Niño3.4' if j==0 else 'WWV / mean D20');ax.grid(alpha=.15);ax.set_xticks(range(1,10))
    fig.suptitle('Independent hindcasts | 2006–2024 | all monthly starts',fontsize=16,y=.99)
    fig.legend(handles=handles[1:],ncol=4,loc='upper center',bbox_to_anchor=(.5,.93),frameon=False)
    fig.text(.07,.035,'Training expands from 1982 to December before each initialization year; preprocessing is fitted on past data only.\n'
             'Current-vintage ERSSTv5, GODAS and canonical PMM; 1991–2020 display zero has no effect on RMSE.',fontsize=9,color='#4c5560')
    save(fig,'independent_skill_by_lead')
    # Aggregate PMM improvements with year-block uncertainty.
    ci=pd.read_csv(OUT/'PMM_improvement_block_bootstrap.csv');fig,axes=plt.subplots(1,2,figsize=(12,4.8));fig.subplots_adjust(top=.82,bottom=.25,wspace=.32)
    for j,var in enumerate(['T','H']):
        ax=axes[j]
        for i,name in enumerate(['RO_SST','RO_wind','RO_both']):
            r=ci[ci.protocol.eq('past_1982')&ci.period.eq('2006_2024')&ci.model.eq(name)&ci.variable.eq(var)].iloc[0]
            ax.plot([r.CI_low,r.CI_high],[i,i],color=COLORS[name],lw=3);ax.scatter(r.improvement_pct,i,color=COLORS[name],s=50)
        ax.set_yticks(range(3),[LABELS[x] for x in ['RO_SST','RO_wind','RO_both']]);ax.invert_yaxis();ax.axvline(0,color='.5',lw=1);ax.grid(axis='x',alpha=.2)
        ax.set(xlabel='RMSE reduction relative to RO (%)',title='Niño3.4' if j==0 else 'WWV / mean D20')
    fig.suptitle('Does canonical PMM improve independent forecasts?',fontsize=17,y=.98)
    fig.text(.07,.055,'2006–2024, all 12 starts, monthly leads 1–9. Positive means improvement; negative means degradation.\n'
             '95% intervals: 2,000 paired circular block bootstrap draws of 3 consecutive initialization years.\n'
             'All overlapping leads remain grouped; only three pre-specified PMM extensions are compared.',fontsize=9,color='#4c5560',linespacing=1.5)
    save(fig,'independent_PMM_improvement')

if __name__=='__main__':run()
