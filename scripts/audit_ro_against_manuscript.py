#!/usr/bin/env python3
"""Controlled baseline audit; not an exact reproduction of the supplied paper.

Hold raw ORAS5 T/H fixed while changing one methodological choice at a time.
No PMM and no outcome-dependent coefficient selection. Explicitly label every
2015 experiment that uses post-2014 fitting or preprocessing as retrospective.
"""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import redo_ro_pmm_on_oras5 as base
from XRO import XRO
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT=base.ROOT/'outputs/research_2026/manuscript_RO_baseline_audit_20261014'
OUT.mkdir(parents=True,exist_ok=True)
VARS=['Nino34','WWV']


def prepare(raw,kind):
    if kind=='past_only':return base.make_anomalies(raw,2015,1)
    # Manuscript states 1991–2020 climatology and linear detrending, but does
    # not disclose every detrending detail. Use its stated calibration years
    # for this clearly labeled diagnostic; do not call it an exact replica.
    climatology=raw.loc['1991':'2020'].groupby(raw.loc['1991':'2020'].index.month).mean()
    a=raw.to_numpy()-climatology.loc[raw.index.month].to_numpy()
    train=raw.index.year.to_numpy();mask=(train>=2002)&(train<=2024)
    t=np.arange(len(raw))/12;t-=t[mask].mean()
    design=np.column_stack([np.ones(len(t)),t])
    beta=np.linalg.lstsq(design[mask],a[mask],rcond=None)[0]
    return pd.DataFrame(a-design@beta,index=raw.index,columns=VARS)


def fit_model(a,window,estimator):
    start,end={'past_long':('1982-01','2014-12'),'past_short':('2002-01','2014-12'),
               'paper_window':('2002-01','2024-12')}[window]
    mask=(a.index>=pd.Timestamp(start))&(a.index<=pd.Timestamp(end))
    if estimator=='original_monthly_ridge':
        model,diag=base.old.fit_model(a.to_numpy(),a.index,mask,alpha=1,seasonal=True)
        return ('old',model),diag
    # Official XRO package exposes both zero-lag forward-difference and
    # lagged-covariance centered-difference sLIM estimators. Use a purely
    # linear two-state configuration; no nonlinear terms and no forcing.
    forward=estimator.startswith('forward')
    order=1 if estimator.endswith('ac1') else 2
    kernel=XRO(ncycle=12,ac_order=order,is_forward=forward)
    fit=kernel.fit_matrix(base.xro.as_dataset(a.loc[mask]),maskb=[],maskc=[],maskNT=[],maskNH=[])
    return ('core',kernel,fit),dict(training_months=int(mask.sum()),ac_order=order,
                                  forward=forward,taus=kernel.taus.tolist())


def forecast(m,initial,month,nstep=10):
    if m[0]=='old':return base.old.integrate(m[1],initial,month)
    return m[1]._integration_forecast(m[2],initial,month-1,n_month=12,nstep=nstep,ncopy=1,noise_type='zero').isel(member=0).values.T


def main():
    raw=xr.open_dataset(base.RAW)[VARS].to_dataframe().loc['1982-01':]
    display_clim=raw.loc['1982':'2014'].groupby(raw.loc['1982':'2014'].index.month).mean()
    displayed=raw.to_numpy()-display_clim.loc[raw.index.month].to_numpy()
    truth=pd.DataFrame(displayed,index=raw.index,columns=VARS)
    rows=[];diags={};qa={};fits={}
    # A staged attribution sequence, specified before running the diagnostics.
    cases={
      'A_original':('past_only','past_long','original_monthly_ridge'),
      'B_forward_ac1':('past_only','past_long','forward_ac1'),
      'C_forward_ac2':('past_only','past_long','forward_ac2'),
      'D_center_lag1_ac1':('past_only','past_long','center_ac1'),
      'E_center_lag1_ac2':('past_only','past_long','center_ac2'),
      'F_recent_past_fit':('past_only','past_short','center_ac2'),
      'G_paper_fit_window':('past_only','paper_window','center_ac2'),
      'H_paper_like_preprocessing':('paper_like','paper_window','center_ac2'),
      'I_original_paper_fit':('past_only','paper_window','original_monthly_ridge'),
    }
    for case,(preproc,window,estimator) in cases.items():
        a=prepare(raw,preproc)
        m,diag=fit_model(a,window,estimator);fits[case]=(m,a)
        diag.update(preprocessing=preproc,fit_window=window,estimator=estimator)
        if m[0]=='core':
            m[2].to_netcdf(OUT/f'{case}_fit.nc',engine='netcdf4')
            diag['annual_mean_L']=m[2].Lac.mean('cycle').values.tolist()
        diags[case]=diag
        for month in range(1,7):
            ini=pd.Timestamp(2015,month,1);targets=pd.date_range(ini,periods=13,freq='MS')
            fc=forecast(m,a.loc[ini].to_numpy(),month)
            assert np.isfinite(fc).all()
            # Restore only the preprocessing background: identical display
            # zero and observed curve in every panel; no event-amplitude scaling.
            background=truth.reindex(targets).to_numpy()-a.reindex(targets).to_numpy()
            fc+=background
            for k,target in enumerate(targets):
                rows.append(dict(case=case,month=month,lead=k,target=target,T=fc[k,0],H=fc[k,1],
                                 obs_T=truth.loc[target,'Nino34'],obs_H=truth.loc[target,'WWV']))
        print('Audit case',case,flush=True)
    f=pd.DataFrame(rows);f.to_csv(OUT/'controlled_forecasts_2015.csv',index=False)
    archived=pd.read_csv(base.OUT/'all_forecasts.csv',parse_dates=['init','target'])
    archived=archived[archived.protocol.eq('raw_oras5')&archived.family.eq('linear')&archived.year.eq(2015)&archived.model.eq('RO')&archived.month.between(1,6)]
    joined=f[f.case.eq('A_original')].merge(archived,on=['month','lead','target'])
    qa['original_reproduction_max_difference']=float(np.max(abs(joined[['T_x','H_x']].to_numpy()-joined[['T_y','H_y']].to_numpy())))
    assert len(joined)==78 and qa['original_reproduction_max_difference']<1e-10
    # Check submonthly integration convergence for the centered estimator.
    m,a=fits['E_center_lag1_ac2'];initial=a.loc['2015-03-01'].to_numpy()
    diff=forecast(m,initial,3,10)-forecast(m,initial,3,20)
    qa['center_integration_10_vs_20_Tmax']=float(abs(diff[:,0]).max())
    qa['center_integration_10_vs_20_Hmax']=float(abs(diff[:,1]).max())
    metrics=[]
    for case,g in f.groupby('case'):
        for month,v in g[g.lead.gt(0)].groupby('month'):
            metrics.append(dict(case=case,window=f'month_{month:02d}_lead1_12',n=len(v),
                                T_rmse=np.sqrt(np.mean((v['T']-v.obs_T)**2)),H_rmse=np.sqrt(np.mean((v['H']-v.obs_H)**2)),
                                T_correlation=np.corrcoef(v['T'],v.obs_T)[0,1],T_max=v['T'].max(),obs_T_max=v.obs_T.max()))
        v=g[g.month.between(2,6)&g.lead.between(1,9)]
        metrics.append(dict(case=case,window='Feb_Jun_lead1_9_monthly',n=len(v),
                            T_rmse=np.sqrt(np.mean((v['T']-v.obs_T)**2)),H_rmse=np.sqrt(np.mean((v['H']-v.obs_H)**2)),
                            T_correlation=np.corrcoef(v['T'],v.obs_T)[0,1],T_max=v['T'].max(),obs_T_max=v.obs_T.max()))
    summary=pd.DataFrame(metrics);summary.to_csv(OUT/'controlled_scores.csv',index=False)
    (OUT/'configuration_and_QA.json').write_text(json.dumps(dict(cases=diags,qa=qa,raw_source=str(base.RAW),raw_sha256=hashlib.sha256(base.RAW.read_bytes()).hexdigest()),indent=2)+'\n')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(13,9),sharex=True,sharey=True)
    fig.subplots_adjust(top=.88,bottom=.20,hspace=.37,wspace=.12)
    titles=[('A_original',[1],'(a) Previous baseline: January start, 12 months'),
            ('A_original',list(range(2,7)),'(b) Same baseline: February–June starts, 9 months'),
            ('E_center_lag1_ac2',list(range(2,7)),'(c) Lagged-covariance RO; fit ends 2014'),
            ('I_original_paper_fit',list(range(2,7)),'(d) Original estimator; fit 2002–2024 (in sample)')]
    colors={1:'#2878B5',2:'#F6B582',3:'#E68B48',4:'#D55E00',5:'#AF3B18',6:'#78281F'}
    obs=truth.loc['2015-01':'2016-06','Nino34']
    for ax,(case,months,title) in zip(axes.ravel(),titles):
        ax.plot(obs.index,obs,color='#202833',lw=2.6,label='Observed')
        for month in months:
            maxlead=12 if month==1 else 9
            g=f[f.case.eq(case)&f.month.eq(month)&f.lead.le(maxlead)]
            ax.plot(g.target,g['T'],color=colors[month],lw=1.9,label=base.MONTHS[month-1])
            ax.scatter(g.target.iloc[0],g['T'].iloc[0],s=24,color=colors[month])
        ax.set(title=title,xlim=(pd.Timestamp('2015-01-01'),pd.Timestamp('2016-04-01')),ylim=(-.8,3.6))
        ax.set_xticks(pd.to_datetime(['2015-01-01','2015-04-01','2015-07-01','2015-10-01','2016-01-01','2016-04-01']),['Jan\n2015','Apr','Jul','Oct','Jan\n2016','Apr'])
        ax.axhline(0,color='.5',lw=.7);ax.grid(alpha=.15)
        window='month_01_lead1_12' if months==[1] else 'Feb_Jun_lead1_9_monthly'
        s=summary[summary.case.eq(case)&summary.window.eq(window)].iloc[0]
        ax.text(.03,.94,f'r = {s.T_correlation:.2f}; RMSE = {s.T_rmse:.2f} °C',transform=ax.transAxes,va='top',fontsize=10)
    for ax in axes[:,0]:ax.set_ylabel('Niño3.4 anomaly (°C)')
    fig.suptitle('Why the manuscript and our earlier RO figures differ | 2015 baseline audit',fontsize=16,y=.975)
    handles=[Line2D([0],[0],color='#202833',lw=2.5,label='Observed')]+[Line2D([0],[0],color=colors[m],lw=2,label=base.MONTHS[m-1]+' start') for m in range(2,7)]
    fig.legend(handles=handles,ncol=6,loc='upper center',bbox_to_anchor=(.5,.945),frameon=False,fontsize=9)
    fig.text(.055,.025,'Controlled diagnostic: all panels use identical raw ORAS5 T/H and a common 1982–2014 display climatology. No PMM.\n'
             'Panel (c): centered derivative, 1-month lagged covariance, annual + semiannual harmonics, official XRO linear core.\n'
             'Panel (d) changes ONLY the coefficient fitting window relative to (b); includes 2015 and is NOT an independent forecast.\n'
             'Monthly targets shown; manuscript IRI targets are 3-month seasons. This audit is not an exact reproduction of its Fig. 4.',
             fontsize=9,color='#4e5660',linespacing=1.6)
    fig.savefig(OUT/'baseline_comparison_2015.png',dpi=220,bbox_inches='tight');plt.close(fig)
    print(summary[summary.window.isin(['month_03_lead1_12','Feb_Jun_lead1_9_monthly'])].to_string(index=False),flush=True)
    print('QA',qa,flush=True)
    notes=[
        '论文与当前RO结果的差异核查（2026-10-14）',
        '',
        '所读稿件：Asymmetry in ENSO Prediction Skill within the IRI Real-Time Forecast System；18页；用户提供的2025年9月稿件。',
        '来源：/Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/manuscript.pdf',
        '',
        '论文图形的实际含义：',
        '第11页图3a：观测ENSO类别的标准化相轨迹，黑箭头为观测趋势，灰箭头为RO在观测状态处计算的线性趋势。并不是一次初值自由积分的预测轨迹。',
        '图3b、3c、3d：RO长时间随机模拟及对模拟序列的预报；图3c黑线不是实际历史观测。',
        '第12页图4才是对实际观测事件的RO预报。图4a叠加2–6月起报、1–9个月提前期；2015年图4b所示相关系数为0.47，并非接近1。部分预报明显低估2015峰值。',
        '',
        '已确认的方法差异：',
        '论文第4–6页：ERSSTv5海温和GODAS D20/面积平均WWV；异常参考1991–2020；线性去趋势；2002–2024拟合sLIM季节RO；确定性预报去掉随机强迫。',
        '我们的主实验：原始ORAS5 T/H；1982至起报前一年拟合气候态、线性趋势及系数；月差分+年度正余弦+ridge alpha=1；单次起报最长12个月。',
        '论文写明的2002–2024系数拟合窗口包含2015。所提供正文未写逐年留出或2015事件剔除；不能把该图直接当作与我们完全相同的样本外预报。',
        '论文IRI指标是连续三个月季平均，正文又称对应月指数；RO图是否进行了相同平滑、签发月份与初值月份的精确对应、sLIM滞后选择和积分细节未完全写清。这些仍需补充材料或作者代码才能严格复现。',
        '',
        '本次控制实验：',
        '所有组都固定同一原始ORAS5 T/H，不加入PMM；只逐步改变估计器、系数拟合窗口或预处理。统一1982–2014显示气候态，没有乘任何追随观测的振幅系数。',
        '1. A_original准确重现上次RO；原来的2015年1月起报、1–12月预报RMSE=2.173°C。',
        '2. 同一模型仅改为2–6月起报、1–9月目标汇总，45个起报-目标对，RMSE=1.314°C，相关系数=0.492。',
        '3. 保持第2项输入和预处理，仅将系数拟合改为2002–2024（I_original_paper_fit），RMSE=0.975°C，相关系数=0.645。该结果使用2015及以后数据，仅作样本内诊断。',
        '4. 保持截至2014拟合，仅换用XRO核心提供的中心差分、1个月滞后协方差及年/半年谐波线性RO（E_center_lag1_ac2），RMSE=1.422°C，相关系数=0.335；单改该估计方法未解决问题。',
        '5. 对照图(b)所有预报的最大Niño3.4为1.747°C，(d)为2.217°C；相同目标观测最大2.845°C。即使采用包含2015的窗口，仍有低估。',
        '以上为月值控制实验，尚未换成论文的ERSSTv5/GODAS，也未复现其签发日和季平均定义，不能用相关系数接近0.47宣称复现成功。',
        '',
        '结论：',
        '当前图中的偏离是真实的大预报误差，不能仅展示相对基准的小幅PMM增益来回避。此前未先完成论文RO基准复现就扩展PMM，证据顺序不充分。',
        '已定量确认起报窗口和系数拟合时段能解释相当一部分视觉/数值差异；不能断言它们解释全部误差，也不能据当前结果断言标准PMM没有预报价值。',
        '下一阶段应先按论文同源资料与完整sLIM设定复现图4，再保持验证事件完全不参与拟合，对RO/RO+PMM作公平配对评估。本文未把样本内改善替换成正式PMM技能结果。',
        '',
        '数值核查：',json.dumps(qa,ensure_ascii=False,indent=2),
        '',
        '文件：baseline_comparison_2015.png；controlled_scores.csv；controlled_forecasts_2015.csv；configuration_and_QA.json。',
        '参考sLIM方法：https://journals.ametsoc.org/abstract/journals/clim/34/12/JCLI-D-20-0874.1.xml',
    ]
    (OUT/'audit_notes_cn.txt').write_text('\n'.join(notes)+'\n')


if __name__=='__main__':main()
