"""Paired sLIM ocean-state replacement, retaining the original SST and PMM sources."""
from pathlib import Path
import os,json,hashlib,copy,html
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/maryland_three_events_mpl')
import numpy as np
import pandas as pd
import paper_ro_slim as original
import three_event_segmented_slim as slim
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/wwv26_pmm_replacement_20261015'
OUT.mkdir(parents=True,exist_ok=True)
EVENTS=[1997,2015,2023]
EXCLUDED={y+k for y in EVENTS for k in [-1,0,1]}
SOURCE=ROOT/'outputs/research_2026/three_event_slim_baseline_20261014/inputs_absolute.csv'
PMM=ROOT/'outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014/official_PMM.csv'
PROTOCOL='''2026-10-15: user-requested D20 -> total WWV26 replacement. Written before new fits.
RO-WWV26=[ERSST Niño3.4, total WWV26]; RO-WWV26+PMM adds standard PMM-SST.
Retain [ERSST Niño3.4, GODAS D20] +/- PMM as matched controls, not the main ocean state.
Total WWV26=sum of west/central/east original density-layer volumes; unit 1e14 m3;
instantaneous sigma_theta=26 interface, 9S--9N, 120E--80W. Do not sum total and
three boxes as independent predictors. No new spatial-WWV model this round.
Retain ERSST, the original PMM forecast SST source, rather than change to OISST.
Official PMM-SST is only centered on training samples; no second ENSO removal.
Data common span 1982--2024, 516 months. Primary: all nine target/adjacent years
1996--98, 2014--16, 2022--24 excluded from all fitted means/trends/scales/operators.
408 training months, disjoint segments; never interpolate or lag across gaps.
Secondary: common 2002--2024 training period, retrospective (1997 backward;
2015/2023 in sample). Both use training-only monthly means, optional linear trend.
This secondary is a new matched control, not an exact replication of the old
1991--2020 climatology/trend-through-April-2025 setup. Do not splice its scores.
Primary preprocessing detrended; no-trend retained. Estimator perturb2 primary,
exact moment solution sensitivity. Annual+semiannual harmonics, 72 steps/year,
existing sLIM mean lag6/seasonal lag1. No tuning, regularization or event scaling.
Display: source-specific 1982--2022 monthly climatology, does not enter fitting.
Five starts February--June per event; 9 months deterministic free integration.
Centered seasonal forecasts center leads 1--8; score common center leads 1--5,
25 overlapping pairs and 9 unique target centers. Month leads1--9 scored separately.
Full model vs outgoing PMM->SST/ocean coefficient cut; all other coefficients and
initial states fixed. Report separately from refitted no-PMM model comparison.
QA: state identity/units, held-out preprocessing and parameter exclusion, RK4,
unit scaling, cut behavior, initial states, saved score reconstruction.
No new advection fit or PMM causal attribution. Existing process figures unchanged.
All results retained even if previous three-event skill signs fail to reproduce.
Not real-time validation: future non-event data and published fixed PMM pattern used.
'''
(OUT/'protocol_before_run.txt').write_text(PROTOCOL)

def dump(path,obj):
    def convert(a):
        if isinstance(a,np.ndarray):return a.tolist()
        if isinstance(a,np.generic):return a.item()
        raise TypeError(type(a))
    (OUT/path).write_text(json.dumps(obj,default=convert,ensure_ascii=False,indent=2))

def prepare(raw,mask,detrend):
    a,meta=slim.preprocess(raw,mask.astype(float),detrend)
    j=raw.columns.get_loc('pmm');mu=float(raw.loc[mask,'pmm'].mean())
    a['pmm']=raw.pmm-mu;meta['clim'][:,j]=mu;meta['trend'][:,j]=0
    return a,meta

def metric(g,pred='T',obs='obs_T'):
    d=g[pred].to_numpy()-g[obs].to_numpy()
    return dict(n=len(g),n_unique_targets=g.target.nunique(),RMSE=float(np.sqrt(np.mean(d*d))),
        bias=float(d.mean()),r=float(np.corrcoef(g[pred],g[obs])[0,1]))

def run():
    raw0=pd.read_csv(SOURCE,parse_dates=['time']).set_index('time')
    pm=pd.read_csv(PMM,parse_dates=['time']).set_index('time')
    np.testing.assert_allclose(raw0.basin_wwv,raw0[['west_wwv','central_wwv','east_wwv']].sum(axis=1),atol=1e-10)
    raw=raw0[['ersst','d20','basin_wwv']].rename(columns={'ersst':'sst','basin_wwv':'wwv26'})
    raw['pmm']=pm.SST.reindex(raw.index)
    assert raw.index.equals(pd.date_range('1982-01-01','2024-12-01',freq='MS'))
    assert np.isfinite(raw.to_numpy()).all()
    raw.to_csv(OUT/'inputs_absolute.csv',index_label='time')
    masks={'heldout34':~raw.index.year.isin(EXCLUDED),'fit2002_2024':raw.index.year>=2002}
    assert masks['heldout34'].sum()==408
    pd.DataFrame(masks,index=raw.index).to_csv(OUT/'training_masks.csv',index_label='time')
    display=raw.loc['1982':'2022'].groupby(raw.loc['1982':'2022'].index.month).mean()
    display.to_csv(OUT/'display_climatology.csv',index_label='month')
    fits={};forecasts=[];qa={'training_months':{k:int(v.sum()) for k,v in masks.items()},'initial_error':0.,'rk4_error':0.,'heldout_parameter_error':0.,'unit_error':0.};audit=[]
    for protocol,mask in masks.items():
        for detrend in [True,False]:
            a,meta=prepare(raw,mask,detrend)
            for estimator in ['perturb2','exact']:
                for ocean in ['d20','wwv26']:
                    for has_pmm in [False,True]:
                        cols=['sst',ocean]+(['pmm'] if has_pmm else [])
                        name=ocean+('_PMM' if has_pmm else '')
                        key=f'{protocol}_{"detrend" if detrend else "mean"}_{estimator}_{name}'
                        m=slim.fit(a[cols],mask,method=estimator)
                        ids=[raw.columns.get_loc(c) for c in cols]
                        submeta={k:(v[:,ids] if k in ['clim','trend'] else v) for k,v in meta.items()}
                        fits[key]=dict(model=m,preprocessing=submeta)
                        rho=float(max(abs(np.linalg.eigvals(slim.propagators(m)[-1]))))
                        audit.append(dict(key=key,protocol=protocol,ocean=ocean,has_pmm=has_pmm,detrend=detrend,estimator=estimator,annual_radius=rho,**{k:v for k,v in m['diag'].items() if k!='segments'}))
                        for cut in ([False,True] if has_pmm else [False]):
                            modelname=name+('_cut' if cut else '')
                            for year in EVENTS:
                                for month in range(2,7):
                                    ini=pd.Timestamp(year,month,1);dates=pd.date_range(ini,periods=10,freq='MS')
                                    initial=a.loc[ini,cols].to_numpy()
                                    fc=original.predict(m,initial,month,months=9,cut_pmm=cut)
                                    qa['initial_error']=max(qa['initial_error'],float(abs(fc[0]-initial).max()))
                                    pred=fc+slim.background_at(submeta,dates)-display.loc[dates.month,cols].to_numpy()
                                    obs=raw.loc[dates,cols].to_numpy()-display.loc[dates.month,cols].to_numpy()
                                    assert np.isfinite(pred).all()
                                    for i,date in enumerate(dates):
                                        forecasts.append(dict(protocol=protocol,detrend=detrend,estimator=estimator,model=modelname,ocean=ocean,event=year,init=ini,init_month=month,lead=i,target=date,
                                            T=pred[i,0],obs_T=obs[i,0],H=pred[i,1],obs_H=obs[i,1],T_model=fc[i,0],H_model=fc[i,1],PMM_model=fc[i,2] if has_pmm else np.nan))
                        # Checks target model changes, rather than only file formats.
                        if protocol=='heldout34' and detrend and estimator=='perturb2':
                            changed=raw.copy();changed.loc[~mask]+=1234
                            aa,mm=prepare(changed,mask,detrend);fit2=slim.fit(aa[cols],mask,method=estimator)
                            err=float(abs(fit2['coef']-m['coef']).max());qa['heldout_parameter_error']=max(qa['heldout_parameter_error'],err)
                            for field in ['clim','trend']:assert np.allclose(mm[field],meta[field],atol=1e-10)
                            initial=a.loc['2023-03-01',cols].to_numpy()
                            ref=original.predict(m,initial,3,months=9)
                            conv=float(abs(ref-original.predict(m,initial,3,months=9,steps=48)).max())
                            qa['rk4_error']=max(qa['rk4_error'],conv)
                            factors=np.array([3.,100.]+([.2] if has_pmm else []))
                            scaled=slim.fit(a[cols]*factors,mask,method=estimator)
                            unit=float(abs(ref-original.predict(scaled,initial*factors,3,months=9)/factors).max())
                            qa['unit_error']=max(qa['unit_error'],unit)
                            if has_pmm:
                                cutmodel=copy.deepcopy(m);cutmodel['coef'][:,:2,2:]=0
                                p1=original.predict(cutmodel,initial,3,months=9)
                                newinit=initial.copy();newinit[2]+=100
                                p2=original.predict(cutmodel,newinit,3,months=9)
                                assert np.max(abs(p1[:,:2]-p2[:,:2]))<1e-10
                        print(key, 'annual_radius',round(rho,3),flush=True)
    f=pd.DataFrame(forecasts)
    assert not f.duplicated(['protocol','detrend','estimator','model','event','init','lead']).any()
    f.to_csv(OUT/'monthly_forecasts.csv',index=False)
    seasonal=[]
    keys=['protocol','detrend','estimator','model','ocean','event','init','init_month']
    for key,g in f.groupby(keys,sort=False):
        g=g.sort_values('lead')
        for lead in range(1,9):
            v=g[g.lead.between(lead-1,lead+1)];assert len(v)==3
            seasonal.append({**dict(zip(keys,key)),'lead':lead,'target':pd.Timestamp(key[6])+pd.DateOffset(months=lead),
                **{c:float(v[c].mean()) for c in ['T','obs_T','H','obs_H']}})
    sf=pd.DataFrame(seasonal);sf.to_csv(OUT/'seasonal_forecasts.csv',index=False)
    score=[]
    for level,df,limit in [('seasonal',sf,5),('monthly',f,9)]:
        for key,g in df[df.lead.between(1,limit)].groupby(keys[:6],sort=False):
            score.append({**dict(zip(keys[:6],key)),'target_type':level,**metric(g),
                'H_RMSE':metric(g,'H','obs_H')['RMSE']})
    scores=pd.DataFrame(score)
    for i,row in scores.iterrows():
        base=scores[(scores.protocol==row.protocol)&(scores.detrend==row.detrend)&(scores.estimator==row.estimator)&(scores.model==row.ocean)&(scores.event==row.event)&(scores.target_type==row.target_type)].iloc[0]
        scores.loc[i,'PMM_skill_percent']=100*(1-row.RMSE/base.RMSE)
        scores.loc[i,'mean_T_correction']=row.bias-base.bias
    scores.to_csv(OUT/'scores_all_settings.csv',index=False)
    primary=scores[(scores.protocol=='heldout34')&scores.detrend&(scores.estimator=='perturb2')&(scores.target_type=='seasonal')]
    primary.to_csv(OUT/'primary_scores.csv',index=False)
    audits=pd.DataFrame(audit);audits.to_csv(OUT/'fit_diagnostics.csv',index=False)
    assert qa['initial_error']<1e-10 and qa['heldout_parameter_error']<1e-9 and qa['rk4_error']<1e-5 and qa['unit_error']<1e-8
    # Independent score round trip from saved paired forecasts.
    read=pd.read_csv(OUT/'seasonal_forecasts.csv');saved=pd.read_csv(OUT/'scores_all_settings.csv')
    for _,r in saved[saved.target_type.eq('seasonal')].iterrows():
        g=read[(read.protocol==r.protocol)&(read.detrend==r.detrend)&(read.estimator==r.estimator)&(read.model==r.model)&(read.event==r.event)&read.lead.between(1,5)]
        assert len(g)==25 and g.target.nunique()==9
        assert abs(metric(g)['RMSE']-r.RMSE)<1e-10
    qa.update(fits=len(fits),monthly_forecast_rows=len(f),seasonal_forecast_rows=len(sf),score_rows=len(scores),saved_score_check='passed',no_future_observed_forcing=True)
    dump('models_and_preprocessing.json',fits);dump('numerical_QA.json',qa)
    dump('source_manifest.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE,PMM,Path(__file__),Path(original.__file__),Path(slim.__file__)]})
    report(sf,scores,qa)
    print(primary[['model','event','RMSE','PMM_skill_percent','mean_T_correction']].to_string(index=False))

def report(sf,scores,qa):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    def save(fig,name):
        for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=180,bbox_inches='tight',facecolor='white')
        plt.close(fig)
    for protocol in ['heldout34','fit2002_2024']:
        fig,axs=plt.subplots(2,3,figsize=(14,8.3),sharex=True,sharey=True)
        fig.subplots_adjust(top=.86,bottom=.15,hspace=.34,wspace=.13)
        fig.suptitle('WWV26 replaces D20 in paired seasonal LIM forecasts',fontsize=18,y=.97)
        subtitle='All three event windows excluded: 34 training years' if protocol=='heldout34' else 'Matched 2002–2024 fits: 1997 backward; 2015/2023 in sample'
        fig.text(.5,.92,subtitle+' | ERSST and standard PMM-SST unchanged',ha='center',color='#555')
        for i,ocean in enumerate(['d20','wwv26']):
            for j,year in enumerate(EVENTS):
                ax=axs[i,j]
                g=sf[(sf.protocol==protocol)&sf.detrend&(sf.estimator=='perturb2')&(sf.event==year)&(sf.ocean==ocean)].copy()
                g['month']=(pd.to_datetime(g.target).dt.year-year)*12+pd.to_datetime(g.target).dt.month
                for name,col,ls in [(ocean,'#9aa5af','--'),(ocean+'_PMM','#2c78a1','-'),(ocean+'_PMM_cut','#c17c43',':')]:
                    label='No PMM' if name==ocean else ('+ PMM' if name.endswith('_PMM') else 'PMM path cut')
                    for n,(_,a) in enumerate(g[g.model.eq(name)].groupby('init')):
                        ax.plot(a.month,a['T'],color=col,ls=ls,lw=1.15,alpha=.85,label=label if n==0 else None)
                obs=g.groupby('month')['obs_T'].first();ax.plot(obs.index,obs.values,color='#222222',lw=2,label='Observed')
                sc=scores[(scores.protocol==protocol)&scores.detrend&(scores.estimator=='perturb2')&(scores.event==year)&(scores.target_type=='seasonal')].set_index('model')
                a,b=sc.loc[ocean],sc.loc[ocean+'_PMM']
                ax.set_title(f'{year} | {"D20 control" if ocean=="d20" else "WWV26 main"}\nRMSE {a.RMSE:.3f} → {b.RMSE:.3f} | skill {b.PMM_skill_percent:+.1f}%')
                ax.axhline(0,color='#999',lw=.6);ax.grid(axis='y',alpha=.15);ax.set_xlim(2,14)
                ax.set_xticks([3,6,9,12,14],['Mar','Jun','Sep','Dec','Feb +1'])
                if j==0:ax.set_ylabel('Seasonal Niño3.4 SSTA (°C)')
        axs[0,0].legend(frameon=False,fontsize=8,loc='upper left')
        fig.text(.065,.055,'February–June starts; nine-month free integrations. Scores: common seasonal center leads 1–5, 25 overlapping pairs/event.\n'
            'Main estimator: perturb2; annual + semiannual harmonics; training-only trends. Display anomalies: 1982–2022.\n'
            'D20 is GODAS depth; WWV26 is SODA3 density-layer volume. Different domains/products; no claim of pure definition causality.',fontsize=9,color='#555')
        save(fig,'W1_forecasts_'+protocol)
    fig,axs=plt.subplots(1,2,figsize=(13,5.6),sharey=True)
    fig.subplots_adjust(top=.80,bottom=.20,wspace=.13)
    fig.suptitle('Does the PMM skill change survive the ocean-state replacement?',fontsize=17,y=.97)
    fig.text(.5,.89,'Positive = lower RMSE with PMM; all predefined settings shown',ha='center',color='#555')
    labels=[]
    for j,protocol in enumerate(['heldout34','fit2002_2024']):
        ax=axs[j]
        for k,(detrend,method) in enumerate([(True,'perturb2'),(True,'exact'),(False,'perturb2'),(False,'exact')]):
            label=('Trend removed' if detrend else 'Monthly mean')+' / '+method
            g=scores[(scores.protocol==protocol)&(scores.detrend==detrend)&(scores.estimator==method)&(scores.model=='wwv26_PMM')&(scores.target_type=='seasonal')].set_index('event').loc[EVENTS]
            ax.plot(np.arange(3)+(k-1.5)*.065,g.PMM_skill_percent,marker=['o','s','^','D'][k],lw=1.3,label=label,alpha=.9)
        ax.axhline(0,color='#777',lw=.8);ax.grid(axis='y',alpha=.15);ax.set_xticks(range(3),EVENTS)
        ax.set_title('Event-excluded (34 years)' if j==0 else 'Matched fit (2002–2024)')
    axs[0].set_ylabel('PMM RMSE skill change (%)');axs[1].legend(frameon=False,fontsize=9)
    fig.text(.07,.065,'Method/background variants are sensitivities, not independent samples or confidence intervals.\nNo setting is selected using event performance. Historical real-time prediction skill is not established here.',fontsize=9,color='#555')
    save(fig,'W2_WWV26_skill_sensitivity')
    cols=['protocol','model','event','RMSE','bias','r','PMM_skill_percent','mean_T_correction']
    primary=scores[scores.detrend&(scores.estimator=='perturb2')&(scores.target_type=='seasonal')][cols]
    text='D20已替换为全盆地WWV26｜2026-10-15\n\n'+PROTOCOL+'\n主估计结果（RMSE为°C，skill为相对各自无PMM基准的RMSE下降百分比）：\n'+primary.to_string(index=False)+'\n\n图件安排：W1的WWV26行作为新的预报主图；D20行仅作为同口径对照。旧+13/+19/−30%属于旧D20设定，不自动继承到WWV26。已有局地平流诊断保持不变。\n最后一步：用同一ERSST、总WWV26、PMM状态及事件剔除训练口径，比较有/无PMM对实际平流项的条件重建；再核对模型内部PMM通道修正的时序。本轮只完成海洋状态替换与预报检验，未运行这一过程桥接试验。\n'
    (OUT/'替换结果与下一步.txt').write_text(text)
    body=''.join(f'<h2>{title}</h2><a href="{name}.png"><img src="{name}.png"></a><p><a href="{name}.pdf">PDF</a></p>' for name,title in [('W1_forecasts_heldout34','1. 事件剔除主检验：上排D20对照，下排WWV26'),('W1_forecasts_fit2002_2024','2. 共同2002—2024拟合期的配对参照'),('W2_WWV26_skill_sensitivity','3. WWV26下的预处理与估计方法敏感性')])
    (OUT/'index.html').write_text('''<!doctype html><html lang="zh"><meta charset="utf-8"><title>WWV26＋PMM替换结果</title><style>body{font-family:system-ui,sans-serif;max-width:1300px;margin:35px auto;padding:0 24px;line-height:1.8;color:#26384a}img{width:100%}table{font-size:12px;border-collapse:collapse}td,th{padding:5px;border:1px solid #ddd}pre{white-space:pre-wrap}a{color:#246b96}</style><h1>D20 → WWV26：两组模型已统一替换</h1><p>无PMM：[ERSST Niño3.4, 总WWV26]；有PMM：[ERSST Niño3.4, 总WWV26, 标准PMM-SST]。单位：WWV26为10¹⁴ m³。标准PMM与SST来源保持一致。</p><p><b>旧D20的技巧符号不预设为WWV26结果。</b>本轮采用共同训练口径重算D20对照与WWV26方案，并保留所有敏感性。事件剔除检验仍使用未来非事件资料和公开PMM固定模态，属于回顾性机制检验。</p>'''+body+'<h2>主估计数值</h2>'+primary.round(4).to_html(index=False)+'<p><a href="scores_all_settings.csv">全部评分CSV</a> · <a href="替换结果与下一步.txt">结果与下一步</a></p><details><summary>实验设置</summary><pre>'+html.escape(PROTOCOL)+'</pre></details></html>')

if __name__=='__main__':run()
