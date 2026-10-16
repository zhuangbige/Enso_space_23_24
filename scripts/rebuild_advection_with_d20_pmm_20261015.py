"""Rebuild local-process responses using the same SST/D20(+PMM) forecast states."""
from pathlib import Path
import os,json,hashlib,html
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/maryland_three_events_mpl')
import numpy as np
import pandas as pd
import paper_ro_slim as original
import three_event_segmented_slim as slim
from analyze_three_event_temperature_tendency import project
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/d20_pmm_process_bridge_20261015'
OUT.mkdir(parents=True,exist_ok=True)
PREV=ROOT/'outputs/research_2026/wwv26_pmm_replacement_20261015'
PROCESS=ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015'
EVENTS=[1997,2015,2023]
TERMS=['u_prime_meanT','surface_flux_proxy']
PROTOCOL='''2026-10-15: user correction: retain D20 forecasts and use D20 for process reconstruction.
States: [ERSST Niño3.4, GODAS mean D20] vs [ERSST Niño3.4, GODAS mean D20, standard PMM-SST].
No WWV26 predictor in this experiment. Retain original diagnosed local q=-u' dTbar/dx,
Niño3.4 fixed 0--50m; 30/75m sensitivities. Surface flux proxy is a comparison process.
Shared 1982--2024 monthly chronology and exclusion of 1996--98, 2014--16, 2022--24.
408 training months/108 held-out months. Reuse saved D20 state operators, preprocessing,
scales and forecast trajectories from the matched-control calculation. They do not
depend on WWV26; verify all state columns and freshly estimated operators.
Response preprocessing: training-only monthly mean, then optional linear trend.
Project each response with identical segmented lag6 mean/lag1 seasonal sLIM moments,
annual+semiannual harmonics. Response units C/standard-month throughout; not d(SST)/dt.
Primary perturb2+detrend+50m. Exact solution, no trend, other depths are retained.
Same-state OLS diagnostic is predeclared sensitivity, not a new dynamical forecast.
Use observed states for conditional reconstruction. It is not an initialized forecast.
Restore response background for plotted physical monthly-mean process anomalies.
Report RMSE and MSE skill against zero of the processed response, separately from
forecast RMSE skill. No sum-to-SST-derivative or full-budget closure is imposed.
Score training, all held-out windows, each development year, and each JAS separately.
Do not infer significance from three events or three summer months.
Conditional difference decomposes into direct PMM term and changed SST/D20 coefficients;
this algebra is not causal mediation. Forecast PMM-path cuts remain model-internal tests.
No post-hoc variant selection, new WWB analysis, or physical causal attribution.
'''
(OUT/'protocol_before_run.txt').write_text(PROTOCOL)

def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x.item()))

def response_moments(a,response,scale,mask):
    sums={lag:[np.zeros((5,response.shape[1],a.shape[1])),0] for lag in [1,6]}
    for ids in slim.segments(a.index,mask):
        grid=np.arange((len(ids)-1)*6+1)/6
        x=np.column_stack([np.interp(grid,np.arange(len(ids)),a.iloc[ids,j]/scale[j]) for j in range(a.shape[1])])
        r=np.column_stack([np.interp(grid,np.arange(len(ids)),response.iloc[ids,j]/scale[0]) for j in range(response.shape[1])])
        first=a.index[ids[0]];tt=first.year+(first.month-.5)/12+grid/12
        for lag,acc in sums.items():
            ii=np.arange(lag,len(grid)-1);phi=original.basis(tt[ii],2)
            acc[0]+=np.einsum('nk,np,nj->kpj',phi,r[ii],x[ii-lag],optimize=True);acc[1]+=len(ii)
    return {lag:s[0]/s[1] for lag,s in sums.items()}

def scores(y,p):
    return dict(n=len(y),RMSE=float(np.sqrt(np.mean((y-p)**2))),bias=float(np.mean(p-y)),
        r=float(np.corrcoef(y,p)[0,1]),MSE_skill_vs_zero=float(1-np.mean((y-p)**2)/np.mean(y*y)))

def run():
    raw=pd.read_csv(PREV/'inputs_absolute.csv',parse_dates=['time']).set_index('time')[['sst','d20','pmm']]
    process=pd.read_csv(PROCESS/'monthly_local_tendencies.csv',parse_dates=['time'])
    mask=~raw.index.year.isin({e+k for e in EVENTS for k in [-1,0,1]})
    models=json.loads((PREV/'models_and_preprocessing.json').read_text())
    assert len(raw)==516 and mask.sum()==408
    raw.to_csv(OUT/'inputs_SST_D20_PMM.csv',index_label='time')
    rows=[];sr=[];allfits={};qa={'state_operator_max_error':0.,'excluded_response_parameter_error':0.,'difference_decomposition_error':0.}
    phi=original.basis(original.decimal_time(raw.index),2)
    samples={'training':mask,'heldout_windows':~mask}
    for e in EVENTS:samples[str(e)]=raw.index.year==e;samples[str(e)+'_JAS']=(raw.index.year==e)&raw.index.month.isin([7,8,9])
    for depth in [50,30,75]:
        d=process[process.depth_m.eq(depth)].set_index('time').loc[raw.index,TERMS]
        for detrend in [True,False]:
            response,rmeta=slim.preprocess(d,mask.astype(float),detrend)
            bg=slim.background_at(rmeta,raw.index)
            for method in ['perturb2','exact','ols']:
                reconstructed={};physcoef={};states={}
                for name,cols in [('D20',['sst','d20']),('D20_PMM',['sst','d20','pmm'])]:
                    mkey=f'heldout34_{"detrend" if detrend else "mean"}_{"perturb2" if method=="ols" else method}_{"d20" if name=="D20" else "d20_PMM"}'
                    info=models[mkey];m=info['model'];meta=info['preprocessing']
                    assert m['columns']==cols
                    for k in ['coef','scale']:m[k]=np.asarray(m[k])
                    for k in ['clim','trend']:meta[k]=np.asarray(meta[k])
                    a=raw[cols]-slim.background_at(meta,raw.index);scale=m['scale']
                    pooled,s,di=slim.pool_moments(a,mask)
                    np.testing.assert_allclose(s,scale,atol=1e-12)
                    fitted,_=slim.estimate_pooled(pooled,'perturb2' if method=='ols' else method)
                    err=float(abs(fitted-m['coef']).max());qa['state_operator_max_error']=max(qa['state_operator_max_error'],err)
                    if method=='ols':
                        design=np.einsum('nk,nd->nkd',phi,a.to_numpy()/scale).reshape(len(raw),-1)
                        co,_,rank,_=np.linalg.lstsq(design[mask],response.to_numpy()[mask]/scale[0],rcond=None)
                        assert rank==design.shape[1]
                        pc=co.reshape(5,len(cols),len(TERMS)).transpose(0,2,1)
                    else:
                        gs=response_moments(a,response,scale,mask);pc=project(pooled,gs,method)
                    physical=np.einsum('nk,kpj->npj',phi,pc)*scale[0]/scale[None,None,:]
                    pred=np.einsum('npj,nj->np',physical,a.to_numpy())
                    restored=pred+bg
                    key=f'{depth}m_{"detrend" if detrend else "mean"}_{method}_{name}'
                    allfits[key]=dict(columns=cols,coef=pc,scale=scale,response_preprocessing=rmeta,method=method)
                    for j,term in enumerate(TERMS):
                        for sample,use in samples.items():sr.append(dict(depth_m=depth,detrend=detrend,method=method,model=name,process=term,sample=sample,**scores(response.to_numpy()[use,j],pred[use,j])))
                        for i,date in enumerate(raw.index):
                            rows.append(dict(depth_m=depth,detrend=detrend,method=method,model=name,process=term,time=date,event=date.year,month=date.month,
                                diagnosed=d.iloc[i,j],reconstructed=restored[i,j],diagnosed_processed=response.iloc[i,j],reconstructed_processed=pred[i,j],
                                PMM_direct=physical[i,j,2]*a.iloc[i,2] if name=='D20_PMM' else 0))
                    reconstructed[name]=pred;physcoef[name]=physical;states[name]=a
                    if depth==50 and detrend and method=='perturb2':
                        altered=d.copy();altered.loc[~mask]+=10000
                        rr,mm=slim.preprocess(altered,mask.astype(float),detrend)
                        p2=project(pooled,response_moments(a,rr,scale,mask),method)
                        err=float(abs(p2-pc).max());qa['excluded_response_parameter_error']=max(qa['excluded_response_parameter_error'],err)
                diff=reconstructed['D20_PMM']-reconstructed['D20']
                direct=physcoef['D20_PMM'][:,:,2]*states['D20_PMM'].pmm.to_numpy()[:,None]
                refit=np.einsum('npj,nj->np',physcoef['D20_PMM'][:,:,:2]-physcoef['D20'],states['D20'].to_numpy())
                qa['difference_decomposition_error']=max(qa['difference_decomposition_error'],float(abs(diff-direct-refit).max()))
                print(depth,detrend,method,flush=True)
    out=pd.DataFrame(rows);sk=pd.DataFrame(sr)
    for i,r in sk.iterrows():
        base=sk[(sk.depth_m==r.depth_m)&(sk.detrend==r.detrend)&(sk.method==r.method)&(sk.model=='D20')&(sk.process==r.process)&(sk['sample']==r['sample'])].iloc[0]
        sk.loc[i,'PMM_RMSE_skill_percent']=100*(1-r.RMSE/base.RMSE)
    out.to_csv(OUT/'monthly_process_reconstructions.csv',index=False);sk.to_csv(OUT/'process_scores.csv',index=False)
    primary=sk[sk.depth_m.eq(50)&sk.detrend&sk.method.eq('perturb2')]
    primary.to_csv(OUT/'primary_process_scores.csv',index=False)
    assert max(qa.values())<1e-8
    # Export only D20 forecast products so the current directory has no WWV state.
    for fn in ['monthly_forecasts.csv','seasonal_forecasts.csv','scores_all_settings.csv']:
        df=pd.read_csv(PREV/fn);df=df[(df.ocean=='d20')&(df.protocol=='heldout34')]
        df.to_csv(OUT/('D20_'+fn),index=False)
    dump('process_models.json',allfits);dump('numerical_QA.json',qa)
    dump('source_manifest.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [PREV/'inputs_absolute.csv',PREV/'models_and_preprocessing.json',PROCESS/'monthly_local_tendencies.csv',Path(__file__)]})
    report(out,sk)
    print(primary[primary.process.eq('u_prime_meanT')][['model','sample','RMSE','MSE_skill_vs_zero','PMM_RMSE_skill_percent']].to_string(index=False))

def report(out,sk):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    def save(fig,name):
        for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=180,bbox_inches='tight',facecolor='white')
        plt.close(fig)
    pr=out[out.depth_m.eq(50)&out.detrend&out.method.eq('perturb2')]
    ps=sk[sk.depth_m.eq(50)&sk.detrend&sk.method.eq('perturb2')]
    fig,axs=plt.subplots(2,3,figsize=(14,8.1),sharex=True,sharey='row')
    fig.subplots_adjust(top=.85,bottom=.15,hspace=.28,wspace=.13)
    fig.suptitle('Local-process reconstruction using SST + D20, with and without PMM',fontsize=17,y=.97)
    fig.text(.5,.91,'Observed states; all three event windows excluded. Restored monthly-mean process background.',ha='center',color='#555')
    for i,term in enumerate(TERMS):
        for j,e in enumerate(EVENTS):
            ax=axs[i,j];g=pr[pr.event.eq(e)&pr.process.eq(term)]
            for name,c,ls in [('D20','#287da6','--'),('D20_PMM','#c3673f','-')]:
                a=g[g.model==name].sort_values('month');ax.plot(a.month,a.reconstructed,color=c,ls=ls,lw=1.7,label='SST + D20' if name=='D20' else 'SST + D20 + PMM')
            a=g[g.model.eq('D20')].sort_values('month');ax.plot(a.month,a.diagnosed,color='#222',lw=2,label='Diagnosed process')
            ax.axvspan(6.5,9.5,color='#ead598',alpha=.22);ax.axhline(0,color='#999',lw=.7);ax.grid(axis='y',alpha=.15)
            score=ps[ps.model.eq('D20_PMM')&ps.process.eq(term)&ps['sample'].eq(str(e))].iloc[0]
            ax.set_title(f'{e} | PMM RMSE skill change: {score.PMM_RMSE_skill_percent:+.1f}%')
            ax.set_xticks([1,4,7,10,12],['Jan','Apr','Jul','Oct','Dec']);ax.set_xlim(1,12)
    axs[0,0].set_ylabel('Anomalous zonal advection\n(°C / standard month)')
    axs[1,0].set_ylabel('Surface flux proxy\n(°C / standard month)')
    axs[1,0].legend(frameon=False,fontsize=9,loc='lower left')
    fig.text(.065,.055,'Layer: 0–50 m, Niño3.4. Predictor SST remains ERSST; the response is a layer-temperature process, not the SST derivative.\n'
        'Scores use the same 12 development months per event; JAS shaded. Positive skill change = lower reconstruction RMSE.\n'
        'Primary: detrended, second-order sLIM response moments. This conditional reconstruction is not a free forecast or causal attribution.',fontsize=9,color='#555')
    save(fig,'D1_D20_PMM_process_reconstruction')
    sf=pd.read_csv(OUT/'D20_seasonal_forecasts.csv');fs=pd.read_csv(OUT/'D20_scores_all_settings.csv')
    fig,axs=plt.subplots(1,3,figsize=(14,5.5),sharey=True)
    fig.subplots_adjust(top=.79,bottom=.24,wspace=.14)
    fig.suptitle('D20 retained: matched event-excluded seasonal forecasts',fontsize=18,y=.97)
    fig.text(.5,.89,'Same SST/D20/PMM states, training windows and preprocessing as the process reconstruction',ha='center',color='#555')
    for j,e in enumerate(EVENTS):
        ax=axs[j];g=sf[sf.detrend&sf.estimator.eq('perturb2')&sf.event.eq(e)].copy()
        g['x']=(pd.to_datetime(g.target).dt.year-e)*12+pd.to_datetime(g.target).dt.month
        for name,c,ls in [('d20','#929fa8','--'),('d20_PMM','#287da6','-'),('d20_PMM_cut','#c3673f',':')]:
            for k,(_,a) in enumerate(g[g.model.eq(name)].groupby('init')):
                ax.plot(a.x,a['T'],color=c,ls=ls,lw=1.2,label=({'d20':'No PMM','d20_PMM':'+ PMM','d20_PMM_cut':'PMM path cut'}[name]) if k==0 else None)
        o=g.groupby('x')['obs_T'].first();ax.plot(o.index,o.values,color='#222',lw=2,label='Observed')
        s=fs[fs.detrend&fs.estimator.eq('perturb2')&fs.event.eq(e)&fs.target_type.eq('seasonal')].set_index('model')
        ax.set_title(f'{e} | skill {s.loc["d20_PMM","PMM_skill_percent"]:+.1f}%\nRMSE {s.loc["d20","RMSE"]:.3f} → {s.loc["d20_PMM","RMSE"]:.3f} °C')
        ax.axhline(0,color='#999',lw=.6);ax.grid(axis='y',alpha=.15);ax.set_xticks([3,6,9,12,14],['Mar','Jun','Sep','Dec','Feb +1']);ax.set_xlim(2,14)
    axs[0].set_ylabel('Seasonal Niño3.4 SSTA (°C)');axs[0].legend(frameon=False,fontsize=9,loc='upper left')
    fig.text(.065,.085,'34 training years; exclude 1996–1998, 2014–2016, 2022–2024. February–June starts; common center leads 1–5.\n'
        '25 overlapping start–season pairs/event, 9 distinct targets. Future non-event training data and published PMM pattern are used.\n'
        'Event-excluded retrospective test; differs from the original 2002–2024 in-sample display. No later observed forcing.',fontsize=9,color='#555')
    save(fig,'D0_D20_PMM_forecasts')
    # All specified estimator/background/depth results, not a chosen winner.
    fig,axs=plt.subplots(1,2,figsize=(13,5.5),sharey=True)
    fig.subplots_adjust(top=.82,bottom=.26,wspace=.15)
    fig.suptitle('Does PMM improve the local-process reconstruction?',fontsize=18,y=.97)
    categories=['heldout_windows','1997','2015','2023'];labs=['Held-out\n108 months','1997','2015','2023']
    for j,term in enumerate(TERMS):
        ax=axs[j]
        for k,(detr,method,col,marker) in enumerate([(True,'perturb2','#287da6','o'),(True,'exact','#c3673f','s'),(False,'perturb2','#659678','^'),(False,'exact','#987ba7','D'),(True,'ols','#777777','x')]):
            g=sk[sk.depth_m.eq(50)&sk.detrend.eq(detr)&sk.method.eq(method)&sk.model.eq('D20_PMM')&sk.process.eq(term)].set_index('sample').loc[categories]
            ax.plot(np.arange(4)+(k-2)*.04,g.PMM_RMSE_skill_percent,marker=marker,lw=1.1,color=col,label=('Detrend' if detr else 'Mean')+' / '+method)
        ax.axhline(0,color='#777',lw=.8);ax.set_xticks(range(4),labs);ax.grid(axis='y',alpha=.15)
        ax.set_title('Anomalous zonal advection' if j==0 else 'Surface flux proxy')
    axs[0].set_ylabel('PMM reconstruction RMSE skill change (%)');axs[1].legend(frameon=False,fontsize=9,loc='best')
    fig.text(.07,.075,'Positive = lower conditional reconstruction RMSE with PMM; not initialization forecast skill.\n'
        '0–50 m shown; all 30/50/75 m settings in CSV. OLS is a diagnostic sensitivity, not a replacement dynamical model.',fontsize=9,color='#555')
    save(fig,'D2_process_skill_sensitivity')
    # Joint result table deliberately separates SST forecast and conditional process metrics.
    summary=[]
    for e in EVENTS:
        f=fs[fs.detrend&fs.estimator.eq('perturb2')&fs.event.eq(e)&fs.model.eq('d20_PMM')&fs.target_type.eq('seasonal')].iloc[0]
        q=ps[ps.model.eq('D20_PMM')&ps.process.eq('u_prime_meanT')&ps['sample'].eq(str(e))].iloc[0]
        su=ps[ps.model.eq('D20_PMM')&ps.process.eq('surface_flux_proxy')&ps['sample'].eq(str(e))].iloc[0]
        a=pr[pr.event.eq(e)&pr.process.eq('u_prime_meanT')&pr.month.between(7,9)].groupby('model')[['diagnosed','reconstructed']].mean()
        summary.append(dict(event=e,SST_forecast_skill_pct=f.PMM_skill_percent,advection_reconstruction_skill_pct=q.PMM_RMSE_skill_percent,surface_reconstruction_skill_pct=su.PMM_RMSE_skill_percent,
            JAS_diagnosed_q=a.loc['D20','diagnosed'],JAS_D20_q=a.loc['D20','reconstructed'],JAS_D20_PMM_q=a.loc['D20_PMM','reconstructed']))
    summary=pd.DataFrame(summary);summary.to_csv(OUT/'bridge_summary.csv',index=False)
    note='D20平流重建与PMM桥接｜2026-10-15\n\n预报与平流响应统一使用ERSST Niño3.4、GODAS D20及标准PMM；不含WWV26。\n'+summary.to_string(index=False)+'\n\n表中SST是初始化自由预报技巧，平流/海表是实际月状态条件重建技巧，样本窗口分别为季节配对和发展年12个月。二者不能当同一种技巧相减。\nJAS重建已恢复原固定同月过程背景，与Fig24/29同量纲。q不等于SST导数，因此不构造系数和等于SST趋势的闭合证明。\n已完成状态统一、过程响应投影及方法敏感性。是否支持PMM—平流桥梁，应同时看有无PMM的过程误差、季节符号和方法稳定性，不由SST技巧符号单独决定。\n'
    (OUT/'D20重建结果说明.txt').write_text(note)
    body=''.join(f'<h2>{title}</h2><a href="{name}.png"><img src="{name}.png"></a><p><a href="{name}.pdf">PDF</a></p>' for name,title in [('D0_D20_PMM_forecasts','1. 同口径D20预报'),('D1_D20_PMM_process_reconstruction','2. D20平流与海表项重建'),('D2_process_skill_sensitivity','3. PMM增量是否稳定')])
    (OUT/'index.html').write_text('''<!doctype html><html lang="zh"><meta charset="utf-8"><title>D20平流重建</title><style>body{font-family:system-ui,sans-serif;max-width:1300px;margin:35px auto;padding:0 24px;line-height:1.8;color:#26384a}img{width:100%}table{font-size:12px;border-collapse:collapse}td,th{padding:5px;border:1px solid #ddd}pre{white-space:pre-wrap}a{color:#246b96}</style><h1>预报和平流重建统一用D20</h1><p>两组状态为[SST, D20]与[SST, D20, PMM]。平流物理诊断没有改变；本轮改变的是重建它的状态变量。预报与过程响应共享34年训练期及三个留出窗口。</p>'''+body+'<h2>连接两组结果</h2>'+summary.round(4).to_html(index=False)+'<p>正百分比表示RMSE下降。预报与条件重建属于不同问题，不能直接比较百分比大小来分配因果贡献。</p><p><a href="D20重建结果说明.txt">结果说明</a> · <a href="process_scores.csv">全部过程评分</a></p><details><summary>方法与边界</summary><pre>'+html.escape(PROTOCOL)+'</pre></details></html>')

if __name__=='__main__':run()
