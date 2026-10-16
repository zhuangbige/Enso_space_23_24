#!/usr/bin/env python3
"""Figure 4 reconstruction with the manuscript's actual data and fitting windows.
No PMM, no 2026, no out-of-sample claim, no optimized event-dependent parameters.
Time-processing alternatives retained; closest figure does not establish author intent.
"""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from PIL import Image
import run_paper_ro_pmm as r
import matplotlib.pyplot as plt
ROOT=r.ROOT;OUT=ROOT/'outputs/research_2026/manuscript_RO_exact_period_20261014'
YEARS=[2002,2004,2006,2009,2014,2015,2018,2023,2005,2007,2010,2016,2020,2024,2008,2011,2017,2021,2022]
PRINTED=[.66,-.38,.63,.64,.71,.47,.83,.91,-.03,.73,.52,.81,.62,.98,.32,-.53,-.18,-.57,.10]
COLOR={y:('#D97661' if i<8 else '#238DB6' if i<14 else '#139969') for i,y in enumerate(YEARS)}

def score(v,obs):return float(np.corrcoef(v,obs)[0,1]),float(np.sqrt(np.mean((np.asarray(v)-np.asarray(obs))**2)))

def main():
    OUT.mkdir(parents=True,exist_ok=True);r.style()
    raw,p,clim=r.load()
    # Explicitly restrict all analyzed observations before processing. The
    # 1991--2020 reference is still available outside the displayed interval.
    raw=raw.loc[:'2025-04-01'];p=p.loc[:'2025-04-01']
    a,meta=r.prepare(raw,p,'2002-01-01','2024-12-01',True,trend_end='2025-04-01')
    a=a[r.V].loc['2002-01-01':'2025-04-01']
    assert len(a)==280 and a.index.min()==pd.Timestamp('2002-01-01') and a.index.max()==pd.Timestamp('2025-04-01')
    assert len(a.loc['2002':'2024'])==276
    # Smoothing hypothesis from the visibly smoother black line and §2.1's
    # three-month ENSO definition. Never use digitized observations for fit.
    variants={'monthly_states':a,'T_3mo_H_monthly':a.assign(Nino34=a.Nino34.rolling(3,center=True).mean()),'both_3mo':a.rolling(3,center=True).mean()}
    rows=[];models={}
    for name,aa in variants.items():
        # Centered smoothed series loses first Jan observation: fit only its
        # valid months in the stated period; no exterior 2001 state imported.
        training=aa.loc['2002':'2024'].dropna()
        m=r.slim.fit(training);models[name]=dict(model=m,train_start=str(training.index[0].date()),train_end=str(training.index[-1].date()),n_fit_months=len(training))
        for year in YEARS:
            for month in range(1,7):
                ini=pd.Timestamp(year,month,1)
                if aa.loc[ini].isna().any():continue
                pred=r.slim.predict(m,aa.loc[ini].to_numpy(),month)
                dates=pd.date_range(ini,periods=13,freq='MS')
                for lead,t in enumerate(dates):
                    if t>a.index[-1]:continue
                    rows.append(dict(variant=name,year=year,state_month=month,init=ini,target=t,lead=lead,T=pred[lead,0],H=pred[lead,1],obs_T=aa.Nino34.get(t,np.nan),obs_H=aa.WWV.get(t,np.nan)))
    f=pd.DataFrame(rows);f.to_csv(OUT/'RO_forecasts_exact_period.csv',index=False)
    # Same physical coefficients, alternative unreported issue/lead mapping.
    rules={
      'state_FebJun_monthly_lead1_9':dict(variant='monthly_states',state_months=range(2,7),leads=range(1,10),smooth_pred=False,smooth_truth=False),
      'state_FebJun_centered3mo_targets':dict(variant='monthly_states',state_months=range(2,7),leads=range(1,10),smooth_pred=True,smooth_truth=True),
      'issue_FebJun_forward3mo_targets':dict(variant='monthly_states',state_months=range(1,6),leads=range(2,11),smooth_pred=True,smooth_truth=True),
      'state_FebJun_lead0_8_INCLUDES_INITIAL':dict(variant='monthly_states',state_months=range(2,7),leads=range(0,9),smooth_pred=False,smooth_truth=False),
      'T_smoothed_state_FebJun':dict(variant='T_3mo_H_monthly',state_months=range(2,7),leads=range(1,10),smooth_pred=False,smooth_truth=True),
      'both_smoothed_state_FebJun':dict(variant='both_3mo',state_months=range(2,7),leads=range(1,10),smooth_pred=False,smooth_truth=True),
    }
    event=[];scored={}
    for rule,cfg in rules.items():
        rule_rows=[]
        for year in YEARS:
            pairs=[]
            for month in cfg['state_months']:
                v=f[f.variant.eq(cfg['variant'])&f.year.eq(year)&f.state_month.eq(month)].set_index('lead')
                if cfg['smooth_pred']:v['T']=v['T'].rolling(3,center=True).mean()
                for lead in cfg['leads']:
                    if lead not in v.index:continue
                    q=v.loc[lead];t=q.target
                    obs=a.Nino34.rolling(3,center=True).mean().get(t,np.nan) if cfg['smooth_truth'] else a.Nino34.get(t,np.nan)
                    if np.isfinite([q['T'],obs]).all():pairs.append(dict(year=year,init=q.init,month=month,lead=lead,target=t,T=q['T'],obs_T=obs))
            z=pd.DataFrame(pairs);rr,rm=score(z['T'],z.obs_T)
            event.append(dict(rule=rule,year=year,n=len(z),r=rr,RMSE=rm,manuscript_r=PRINTED[YEARS.index(year)]));rule_rows+=pairs
        scored[rule]=pd.DataFrame(rule_rows)
    e=pd.DataFrame(event);e.to_csv(OUT/'time_definition_event_scores.csv',index=False)
    summary=[]
    for rule,g in e.groupby('rule'):
        summary.append(dict(rule=rule,event_pattern_correlation=float(g[['r','manuscript_r']].corr().iloc[0,1]),mean_absolute_r_difference=float(abs(g.r-g.manuscript_r).mean()),max_absolute_r_difference=float(abs(g.r-g.manuscript_r).max()),r2015=float(g[g.year.eq(2015)].r.iloc[0]),min_pairs=int(g.n.min())))
    ss=pd.DataFrame(summary);ss.to_csv(OUT/'time_definition_summary.csv',index=False)
    print(ss.to_string(index=False),flush=True)
    # Preserve main monthly convention; no switch to a best-scoring variant.
    primary='state_FebJun_monthly_lead1_9';g=scored[primary]
    ep=e[e.rule.eq(primary)].set_index('year').loc[YEARS]
    def plume(ax):
        ax.plot(a.index,a.Nino34,color='#202020',lw=2.2,zorder=4)
        for ini,v in g.groupby('init'):ax.plot(v.target,v['T'],color=COLOR[ini.year],lw=1.15,alpha=.75)
        for y in YEARS:ax.axvline(pd.Timestamp(y+1,1,1),color=COLOR[y],ls='--',alpha=.45,lw=.9)
        for z in [0,.5,-.5]:ax.axhline(z,color='.2',lw=.65,ls='-' if z==0 else '--')
        ticks=pd.date_range('2002-01-01','2025-01-01',freq='YS')
        ax.set_xticks(ticks,[str(t.year)[2:] for t in ticks]);ax.set_xlim(pd.Timestamp('2001-02-01'),pd.Timestamp('2025-11-01'));ax.set_ylim(-2.6,3.2)
        ax.set_ylabel('Niño3.4 SSTA (°C)');ax.set_xlabel('Year');ax.tick_params(axis='x',labelsize=9)
    def bars(ax):
        x=np.arange(len(YEARS));ax.bar(x-.19,PRINTED,.38,color=[COLOR[y] for y in YEARS],alpha=.4,label='Manuscript printed values')
        ax.bar(x+.19,ep.r,.38,color=[COLOR[y] for y in YEARS],label='Reconstruction')
        ax.set_xticks(x,[str(y)[2:] for y in YEARS]);ax.set_ylim(-.8,1.15);ax.set_ylabel('Event forecast correlation');ax.set_xlabel('Year');ax.axhline(0,color='.4',lw=.7);ax.grid(axis='y',alpha=.13)
        for i,v in enumerate(ep.r):ax.text(i+.19,v+(.025 if v>=0 else -.04),f'{v:.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=8)
        ax.legend(ncol=2,loc='upper left',fontsize=9,frameon=False)
    fig,axes=plt.subplots(2,1,figsize=(13,8),gridspec_kw={'height_ratios':[1.2,1]});fig.subplots_adjust(top=.85,bottom=.19,hspace=.48)
    plume(axes[0]);axes[0].set_title('(a) Same observation and fitting periods as the manuscript',loc='left',fontsize=12)
    bars(axes[1]);axes[1].set_title('(b) Same 19 event years; original values versus reconstruction',loc='left',fontsize=12)
    fig.suptitle('Manuscript RO Figure 4 reconstruction',fontsize=18,y=.98)
    fig.text(.5,.92,'Observations: Jan 2002–Apr 2025  |  Fit: Jan 2002–Dec 2024  |  Climatology: 1991–2020',ha='center',fontsize=11)
    fig.text(.06,.055,'Monthly-state baseline: February–June initializations, leads 1–9; no PMM and no 2026 data.\n'
             'Linear detrending over Jan 2002–Apr 2025; deterministic sLIM with annual + semiannual harmonics.\n'
             'Transparent reconstruction, not an exact author-code replication. Original panel (c) requires the IRI ensemble forecast archive.',fontsize=9,color='#4c5560',linespacing=1.6)
    fig.savefig(OUT/'figure4_reconstruction.png',dpi=220,bbox_inches='tight');fig.savefig(OUT/'figure4_reconstruction.svg',bbox_inches='tight');plt.close(fig)
    # Direct visual comparison: original extracted image is not modified,
    # only its Fig.4a panel is displayed for a like-for-like time-axis view.
    im=Image.open(ROOT/'tmp/pdfs/manuscript_audit_20261014/original_fig4_Image70.jpg')
    fig=plt.figure(figsize=(14,11))
    original_ax=fig.add_axes([.02,.535,.96,.417]);original_ax.imshow(np.asarray(im)[0:430,0:1260]);original_ax.axis('off')
    ax=fig.add_axes([.099,.14,.861,.30]);plume(ax)
    ax.set_title('Reconstruction | same dates, fitting window and 19 event years',loc='left',fontsize=13,pad=12)
    fig.suptitle('Original manuscript (top) versus RO reconstruction (bottom)',fontsize=18,y=.995)
    fig.text(.10,.035,'Observation period: Jan 2002–Apr 2025. Calibration: Jan 2002–Dec 2024. Climatology: 1991–2020.\n'
             'Same time-axis limits, y-axis limits and event groups. Original: extracted Figure 4a, supplied PDF p. 12.\n'
             'Remaining curve and event-score differences mean exact replication has not yet been achieved.',fontsize=10,color='#4c5560',linespacing=1.6)
    fig.savefig(OUT/'figure4_original_vs_reconstruction.png',dpi=220,bbox_inches='tight');plt.close(fig)
    # Focused observation audit; curves retain physically computed anomalies.
    digitized=pd.read_csv(OUT/'digitized_observed_curve_diagnostic.csv',index_col=0,parse_dates=True)
    fig,axes=plt.subplots(1,2,figsize=(13,4.5));fig.subplots_adjust(top=.80,bottom=.23,wspace=.22)
    for ax,year in zip(axes,[2002,2015]):
        z=digitized.loc[f'{year}-01':f'{year+1}-06']
        ax.scatter(z.index,z.figure_observation_approx_C,color='#202020',s=16,label='Approx. digitized original black curve',zorder=4)
        ax.plot(z.index,z.detrend_2002_2025_monthly,color='#2878B5',label='ERSSTv5 monthly')
        ax.plot(z.index,z.detrend_2002_2025_3mo,color='#D55E00',lw=2,label='ERSSTv5 centered 3-month mean')
        ax.set_title(str(year),loc='left');ax.set_ylabel('Niño3.4 SSTA (°C)');ax.grid(alpha=.15);ax.tick_params(axis='x',rotation=35)
    fig.suptitle('Check the observed reference before interpreting forecast differences',fontsize=16,y=.98)
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=3,loc='upper center',bbox_to_anchor=(.5,.94),frameon=False,fontsize=9)
    fig.text(.06,.04,'Digitization is approximate (raster resolution and date alignment limit precision). It is used only as a diagnostic.\n'
             'No model parameter, trend or amplitude was fitted to these pixel-derived points.',fontsize=9,color='#4c5560')
    fig.savefig(OUT/'observed_reference_check.png',dpi=220,bbox_inches='tight');plt.close(fig)
    # Exact artifacts, named by model input hypothesis.
    (OUT/'models_exact_period.json').write_text(json.dumps(dict(periods=dict(observation_start='2002-01',observation_end='2025-04',fit_start='2002-01',fit_end='2024-12',climatology='1991-2020'),models=models,preprocessing=meta),default=r.jsonable,indent=2))
    a.to_csv(OUT/'observations_detrended_2002Jan_2025Apr.csv')
    lines=['原稿图4同时间段复现核查（2026-10-14）','',
           '本轮只检验原稿RO基准，不使用PMM、不分析2026。',
           '时间严格对应：观测2002年1月—2025年4月（280月），拟合2002年1月—2024年12月（276月），异常参考1991—2020。线性去趋势在原稿分析时段2002年1月—2025年4月估计。',
           '图4a只显示原稿图4b列出的19个事件及原稿相同的3类颜色、2—6月起报、1—9月提前期；没有额外加入2012/2013/2019等中性年份预报。',
           '原稿未明确RO初值月与签发月关系、RO月值与季平均关系，因此保留六种有明确含义的时间处理核查；没有按最接近原图的一组改写主结果。包含lead0的组有实况初值，不属于独立提前1个月预报；平滑状态可能包含初值后的实况，均只作原图定义诊断。',
           '',
           '各时间处理与原稿19个印刷评分的对比：',ss.to_string(index=False),
           '',
           '主结果还不能称为严格复现。2015数值较接近，但2002等事件仍有明显差异；应同时看图4a曲线幅度和图4b全部事件评分。',
           '黑色观测线的像素核查更接近三个月平均而非纯月值，但受原图分辨率、月份定位及数据版本影响，此证据不能单独确认作者的平滑定义。像素提取没有进入模型拟合、气候态、趋势或振幅校正。',
           '图4c是RO与IRI多模式技能的比较，缺少作者使用的IRI集合预报档案，不能只靠RO计算复现；没有制造IRI数据。',
           '',
           '额外插值敏感性：固定时段、只将五天插值改为cubic spline，2015相关从0.452变为0.404，2002仍约0.147。改整块协方差解后2002也仅约0.17，未解决最大偏差。详见interpolation_event_scores.csv。',
           '需要作者资料才能闭合的差距：原始处理后T/h序列、季节RO系数、初值/提前期/季平均的日期对应、五天插值和季节估计细节。',
           '来源：用户提供manuscript.pdf第4–6页方法、第12页图4；sLIM按其引用Chen & Jin (2021)附录A5–A7实现。',
           '主要对照图：figure4_original_vs_reconstruction.png；纯重画图：figure4_reconstruction.png；观测核查：observed_reference_check.png。',
           '数值：time_definition_event_scores.csv（逐事件）、time_definition_summary.csv（总体）、RO_forecasts_exact_period.csv（逐预报）。',
           '代码：scripts/reproduce_manuscript_fig4.py；scripts/diagnose_manuscript_observation_curve.py。',
           ]
    (OUT/'comparison_cn.txt').write_text('\n'.join(lines)+'\n')
    print('Completed original-period figure audit',OUT,flush=True)
if __name__=='__main__':main()
