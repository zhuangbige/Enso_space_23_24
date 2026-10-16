"""Figures and auditable tables for the matched local-process diagnosis."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/maryland_three_events_mpl')
import json, html, hashlib, base64
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_three_event_temperature_tendency import OUT,PREV,ROOT,EVENTS,TERMS,DATES,MASK,MONTH

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
    'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','savefig.dpi':190})
PRIMARY='50m_three_wwv_detrend_perturb2'
COLORS=['#2c7fb8','#d95f45','#69a38e','#a779aa','#aa8a35','#757575']
FIGS=[]


def save(fig,stem,caption):
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{stem}.{ext}',bbox_inches='tight',facecolor='white')
    plt.close(fig);FIGS.append((stem,caption))


def axis(ax,context=False):
    ax.axhline(0,color='.65',lw=.7);ax.grid(axis='y',alpha=.15)
    if context:
        ax.set_xticks([-11,-5,1,7,12],['Jan −1','Jul −1','Jan 0','Jul 0','Dec 0'])
        ax.axvline(.5,color='.5',ls=':',lw=.8);ax.set_xlim(-11,12)
    else:
        ax.set_xticks([1,4,7,10,12],['Jan','Apr','Jul','Oct','Dec']);ax.set_xlim(1,12)


def figures(cases,quarters,coef,recon,native):
    raw=pd.read_csv(PREV/'inputs_absolute.csv',parse_dates=['time']).set_index('time')
    ss=raw.nino34.copy()
    for m in range(1,13):ss.loc[DATES.month==m]-=raw.loc[MASK&(DATES.month==m),'nino34'].mean()
    fig,axs=plt.subplots(3,3,figsize=(13.5,9.6),sharex=True,sharey='row',layout='constrained')
    for j,e in enumerate(EVENTS):
        a=cases[cases.event.eq(e)&cases.depth_m.eq(50)].sort_values('time');xx=a.relative_month
        axs[0,j].plot(xx,a.temperature_anomaly,color='black',lw=2,label='SODA3 T(0–50 m)')
        axs[0,j].plot(xx,ss.loc[a.time],color=COLORS[0],ls='--',label='OISST')
        for name,col,label in [('mean_u_Tprime',COLORS[0],'Mean u × zonal T′ gradient'),('u_prime_meanT',COLORS[1],'u′ × mean zonal gradient'),('surface_flux_proxy',COLORS[2],'Surface flux proxy')]:
            axs[1,j].plot(xx,a[name],color=col,lw=1.6,label=label)
        axs[2,j].plot(xx,a.tendency,color='black',lw=2,label='Layer T tendency')
        axs[2,j].plot(xx,a.horizontal_total,color=COLORS[0],lw=1.7,label='Full horizontal anomaly')
        axs[2,j].plot(xx,a.unresolved,color=COLORS[5],ls='--',lw=1.5,label='Unresolved')
        for i,title in enumerate(['Layer T and SST','Selected local process terms','Tendency and partial closure']):
            axs[i,j].set_title(f'({chr(97+3*i+j)}) {e}: {title}',loc='left',fontsize=10);axis(axs[i,j],True)
    axs[0,0].set_ylabel('Temperature anomaly (°C)')
    for i in [1,2]:axs[i,0].set_ylabel('Temperature tendency (°C/month)')
    for i in range(3):axs[i,0].legend(fontsize=7.5,loc='upper left')
    fig.suptitle('Matched Niño3.4 diagnostics retain the preceding-year context\n5°S–5°N, 170°W–120°W; training climatology; fixed 0–50 m layer',fontsize=14)
    save(fig,'Fig24_matched_local_process_history','三例均展示前一年1月至发展年12月。上行为同区域层平均温度与OISST，两者不能互换；中、下行单位均为°C/标准月（365.25/12天）。实际月份温度导数用月中时间差计算。均相对于排除目标及邻年后的34年同月背景，区别于前阶段1982—2022背景。未解析项包括缺失垂向输送、混合、同化、次月尺度协方差和数值/时间平均误差，不能命名为其中某一项。')

    fig,axs=plt.subplots(2,3,figsize=(13,7.3),sharey=True,layout='constrained')
    labels=['Mean-flow\nadvection','Anomalous-flow\nadvection','Nonlinear\nhorizontal','Surface\nproxy','Unresolved']
    for i,quarter in enumerate([2,3]):
        for j,e in enumerate(EVENTS):
            a=quarters[(quarters.depth_m==50)&(quarters.event==e)&(quarters.quarter==quarter)].iloc[0]
            vals=[a.mean_u_Tprime+a.mean_v_Tprime,a.u_prime_meanT+a.v_prime_meanT,a.nonlinear_hadv,a.surface_flux_proxy,a.unresolved]
            ax=axs[i,j];ax.bar(np.arange(5),vals,color=[COLORS[k] for k in [0,1,3,2,5]],width=.67)
            ax.axhline(a.tendency,color='black',ls='--',lw=1.2,label='Diagnosed net T tendency')
            ax.set_xticks(np.arange(5),labels,rotation=35,ha='right',fontsize=8)
            ax.axhline(0,color='.5',lw=.8);ax.grid(axis='y',alpha=.15)
            ax.set_title(f'({chr(97+3*i+j)}) {e}: '+('AMJ' if i==0 else 'JAS'),loc='left')
            if j==0:ax.set_ylabel('Temperature tendency (°C/month)')
    axs[0,0].legend(fontsize=8,loc='upper left')
    fig.suptitle('Common spring and summer windows: process signs and compensation\nBars sum to the diagnosed tendency; this identity does not establish physical closure',fontsize=14)
    save(fig,'Fig25_common_season_process_comparison','AMJ与JAS为月平均倾向的三个月简单平均，不是月中到月中的积分。平均流与异常流项分别合并经向和纬向分量；非线性水平项用于核对两项线性分解的遗漏，不能预设为零。虚线表示总温度距平变化率。大幅抵消时，不用各项除以净增暖计算百分比。海表项假定净通量全部作用于固定层，是未扣除穿透层底短波的代理量。')

    fig,axs=plt.subplots(2,2,figsize=(12,8),sharex=True,layout='constrained')
    labels={'temperature':'T(0–50 m)','west_wwv':'Western WWV26','central_wwv':'Central WWV26','east_wwv':'Eastern WWV26'}
    for j,state in enumerate(labels):
        ax=axs.flat[j];p=coef[(coef.key==PRIMARY)&(coef.state==state)].pivot(index='month',columns='process',values='coefficient')
        for vals,col,label,style in [(p.total,'black','Total','-'),(p.mean_u_Tprime+p.mean_v_Tprime,COLORS[0],'Mean-flow term','-'),(p.u_prime_meanT+p.v_prime_meanT,COLORS[1],'Anomalous-flow term','-'),(p.surface_flux_proxy,COLORS[2],'Surface proxy','-'),(p.unresolved,COLORS[5],'Unresolved','--')]:
            ax.plot(p.index,vals,color=col,label=label,ls=style,lw=1.8)
        ax.set_title(f'({chr(97+j)}) Coefficient multiplying '+labels[state],loc='left',fontsize=11)
        ax.set_ylabel('month$^{-1}$' if j==0 else '°C month$^{-1}$ / ($10^{14}$ m$^3$)');axis(ax)
    handles,labels_legend=axs[0,0].get_legend_handles_labels()
    fig.legend(handles,labels_legend,loc='outside lower center',ncol=5,fontsize=8)
    fig.suptitle('Local processes mapped onto the same seasonal sLIM operator\nPrimary: T(0–50 m) + three WWV26 boxes; detrended, second-order estimator',fontsize=14)
    save(fig,'Fig26_seasonal_process_coefficients','主设置四状态的温度方程系数分解；第一格是乘温度状态的系数，其余是乘各区WWV26的系数。非线性水平项另存完整CSV，未在该图单独画线，总系数包含它。四状态模型的三个储备系数不等同于经典二变量西部温跃层深度模型唯一的F系数。未知项系数有数值定义但没有已识别的物理过程含义。')

    fig,axs=plt.subplots(2,3,figsize=(13.5,7.4),sharex=True,sharey='row',layout='constrained')
    for j,e in enumerate(EVENTS):
        for i,proc in enumerate(['u_prime_meanT','total']):
            ax=axs[i,j];q=recon[(recon.key==PRIMARY)&(recon.event==e)&(recon.process==proc)]
            ax.plot(q.month,q.diagnosed,color='black',lw=2.1,label='Diagnosed')
            ax.plot(q.month,q.reconstructed,color=COLORS[1],lw=1.9,label='sLIM process projection')
            alt_rows=recon[recon.key.str.startswith('50m_three_wwv_')&(recon.event==e)&(recon.process==proc)].copy()
            # Compare sensitivity curves in the primary response coordinates.
            # A no-trend process and a detrended process have different origins.
            alt_rows['aligned']=alt_rows.reconstructed+alt_rows.month.map(q.set_index('month').diagnosed)-alt_rows.diagnosed
            alt=alt_rows.groupby('month').aligned.agg(['min','max'])
            ax.fill_between(alt.index,alt['min'],alt['max'],color=COLORS[1],alpha=.16,label='4 method/background settings')
            ax.set_title(f'({chr(97+3*i+j)}) {e}: '+('Anomalous zonal advection' if i==0 else 'Total T tendency'),loc='left',fontsize=10);axis(ax)
            if j==0:ax.set_ylabel('Temperature tendency (°C/month)')
    fig.legend(*axs[0,0].get_legend_handles_labels(),loc='outside lower center',ncol=3,fontsize=8)
    fig.suptitle('Coefficient decomposition must also reconstruct the diagnosed processes\nUses observed monthly states; shaded ranges are sensitivity ranges, not confidence intervals',fontsize=14)
    save(fig,'Fig27_process_projection_check','使用各月实际状态重建过程，属于条件诊断而不是初始化预报。黑线是经过相同月背景/趋势处理的诊断过程；下行总倾向是模型等间隔月份的中心差分，区别于Fig24的实际秒数导数。阴影含趋势/不去趋势与perturb2/exact四种设置，各曲线先换回主设置的过程背景坐标再比较，不是置信区间。过程投影能否解释个例必须看这些误差，不能仅看系数求和恒等式。')

    fig,axs=plt.subplots(1,3,figsize=(13.5,4.2),sharey=True,layout='constrained')
    for j,e in enumerate(EVENTS):
        q=native[(native.key==PRIMARY)&(native.event==e)]
        ax=axs[j];ax.plot(q.month,q.observed,color='black',lw=2,label='Diagnosed layer T')
        ax.plot(q.month,q.predicted,color=COLORS[0],lw=1.9,label='January-initialized sLIM')
        alt=native[native.key.str.startswith('50m_three_wwv_')&(native.event==e)].groupby('month').predicted.agg(['min','max'])
        ax.fill_between(alt.index,alt['min'],alt['max'],color=COLORS[0],alpha=.16)
        ax.set_title(f'({chr(97+j)}) {e}',loc='left');axis(ax)
    axs[0].set_ylabel('0–50 m temperature anomaly (°C)');axs[0].legend(fontsize=8)
    fig.suptitle('Native evolution remains a separate check before any initial-state swaps\nSame parameters across events; only January observations initialize each trajectory',fontsize=13)
    save(fig,'Fig28_native_layer_temperature_check','层温度版sLIM的原生案例检查。用同一套历史训练参数，从各年1月实际状态自由积分，恢复统一训练气候态距平。阴影为四种估计/背景敏感性。模型拟合使用目标之后的非目标年份，属于回顾性机制检验而非严格历史实时预报。层温度结果不与旧版OISST原生模拟混称同一个试验。')

    fig,axs=plt.subplots(1,2,figsize=(11.5,4.8),sharey=True,layout='constrained')
    rr=recon[recon.process.eq('u_prime_meanT')&recon.month.between(7,9)]
    for i,background in enumerate(['mean','detrend']):
        ax=axs[i]
        for j,h in enumerate([30,50,75]):
            key=f'{h}m_three_wwv_{background}_perturb2'
            vals=rr[rr.key.eq(key)].groupby('event').diagnosed.mean().loc[list(EVENTS)]
            ax.bar(np.arange(3)+(j-1)*.23,vals,width=.21,color=[COLORS[0],COLORS[1],COLORS[2]][j],label=f'0–{h} m')
        ax.set_xticks(np.arange(3),[str(e) for e in EVENTS]);ax.axhline(0,color='.5',lw=.8);ax.grid(axis='y',alpha=.15)
        ax.set_title(f'({chr(97+i)}) '+('Monthly-mean reference' if i==0 else 'Monthly mean + linear trend removed'),loc='left',fontsize=11)
    axs[0].set_ylabel('Anomalous zonal advection (°C/month)');axs[0].legend(fontsize=9,ncol=3)
    fig.suptitle('2023 summer zonal advective contribution is weaker under both backgrounds\nJAS means; the sign of the 2023 contribution depends on the reference',fontsize=13)
    save(fig,'Fig29_zonal_advection_robustness','7—9月的−u′∂xT̄，比较三种固定层厚和两种背景处理。两图都使用训练期同月平均流/温度梯度定义过程，右图另外去除该过程由训练期拟合的线性趋势，并非随年份重算背景梯度的另一种物理分解。2023小于两个对照的排序在六种诊断设置中一致；2023绝对正负号对背景敏感。事件个数仍为3，六种设置不是六个独立样本，不报告显著性。')


def tables_and_report(cases,q,co,recon,native):
    primary=q[(q.depth_m==50)&q.quarter.isin([2,3])].copy()
    primary['mean_flow']=primary.mean_u_Tprime+primary.mean_v_Tprime
    primary['anomalous_flow']=primary.u_prime_meanT+primary.v_prime_meanT
    small=primary[['event','quarter','tendency','mean_flow','anomalous_flow','nonlinear_hadv','surface_flux_proxy','unresolved']]
    small.to_csv(OUT/'primary_season_result_table.csv',index=False)
    # Exact endpoint storage differences and trapezoidal process integrals are separate from quarterly rates.
    intervals=[]
    for h in [30,50,75]:
        for e in EVENTS:
            a=cases[(cases.depth_m==h)&(cases.event==e)&cases.time.dt.year.eq(e)].set_index('time')
            for start,end in [(1,4),(4,7),(7,10),(10,12),(1,12)]:
                z=a.loc[f'{e}-{start:02}-01':f'{e}-{end:02}-01']
                tt=((z.index-z.index[0]).total_seconds()/MONTH).to_numpy()
                row=dict(depth_m=h,event=e,start_month=start,end_month=end,storage_change_C=z.temperature_anomaly.iloc[-1]-z.temperature_anomaly.iloc[0])
                for term in TERMS:row[term]=float(np.trapz(z[term],tt))
                row['unresolved']=row['storage_change_C']-sum(row[x] for x in TERMS)
                intervals.append(row)
    pd.DataFrame(intervals).to_csv(OUT/'midmonth_interval_tendency_integrals.csv',index=False)
    n=[]
    for (key,e),a in native.groupby(['key','event']):
        n.append(dict(key=key,event=e,ond_predicted=a[a.month>=10].predicted.mean(),ond_observed=a[a.month>=10].observed.mean(),
            rmse_feb_dec=np.sqrt(np.mean((a[a.month>1].predicted-a[a.month>1].observed)**2))))
    ns=pd.DataFrame(n);ns.to_csv(OUT/'native_layer_temperature_scores.csv',index=False)
    skill=pd.read_csv(OUT/'process_projection_skill.csv')
    sk=skill[(skill.key==PRIMARY)&skill['sample'].eq('held_out_three_windows')][['process','correlation','mse_skill_vs_zero','rmse']]
    sk.to_csv(OUT/'primary_held_out_process_skill.csv',index=False)
    robustness=[]
    for h in [30,50,75]:
        for bg in ['mean','detrend']:
            selected=recon[recon.key.eq(f'{h}m_three_wwv_{bg}_perturb2')&recon.process.eq('u_prime_meanT')&recon.month.between(7,9)]
            for e,val in selected.groupby('event').diagnosed.mean().items():robustness.append(dict(depth_m=h,background=bg,event=e,JAS_zonal_advective_contribution=val))
    pd.DataFrame(robustness).to_csv(OUT/'summer_zonal_advection_robustness.csv',index=False)
    # Report text is amended with the interpreted result after inspection of these tables.
    prose=(OUT/'结果解读.txt').read_text() if (OUT/'结果解读.txt').exists() else '解释性正文待数值核验后补充。'
    citations='''<p>理论参照：<a href="https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2021GL097603">Chen &amp; Jin (2022), Dynamics of ENSO Phase–Locking and Its Biases in Climate Models</a>，用于固定层定义及过程向季节系数投影的思路。暖水储备继续遵循<a href="https://doi.org/10.1175/JCLI-D-14-00134.1">Chen et al. (2015)</a>的σθ=26体积定义。本文的三案例结论来自本项目数据计算，并非直接引自这些论文。</p>'''
    body='<h1>三案例局地增暖过程与sLIM系数：定量结果</h1><p>2026-10-15 · Niño3.4 · SODA3.15.2 · 0—50m主设置</p><div class="lead">'+html.escape(prose).replace('\n','<br>')+'</div>'
    body+='<h2>同季节过程对照</h2><p>单位°C/标准月。背景为排除三个目标及邻年的34年同月均值。quarter=2为AMJ，3为JAS。mean_flow、anomalous_flow均含纬向及经向；单独纬向项见原始CSV。未解析项不是已识别热源。</p>'+small.round(4).to_html(index=False,border=0)
    body+='<h2>过程投影的外样本误差</h2><p>评价样本为剔除的三个三年窗口，不是三个案例各有独立的大样本。MSE skill=1−模型MSE/零异常MSE，负值表示比零异常重建更差；使用当月实际状态，不是预报技巧。</p>'+sk.round(4).to_html(index=False,border=0)
    ols_path=OUT/'ols_same_state_process_skill.csv'
    if ols_path.exists():
        ols=pd.read_csv(ols_path)
        os=ols[ols.key.eq('50m_three_wwv_detrend_ols_diagnostic')&ols['sample'].eq('held_out_three_windows')][['process','correlation','mse_skill_vs_zero','rmse']]
        body+='<h2>同状态普通最小二乘交叉诊断</h2><p>在看到异常纬向平流投影较弱后追加的探索性检查：保持状态、谐波和训练年份，改用直接过程回归。它不是新的动力模型，也不用于挑选预报模型。</p>'+os.round(4).to_html(index=False,border=0)
    body+='<h2>原生案例模拟检查</h2>'+ns[ns.key.eq(PRIMARY)].round(4).to_html(index=False,border=0)
    for stem,caption in FIGS:
        encoded=base64.b64encode((OUT/f'{stem}.png').read_bytes()).decode()
        body+=f'<figure><img src="data:image/png;base64,{encoded}"><figcaption>{html.escape(caption)}</figcaption></figure>'
    body+='<h2>方法与解释边界</h2><pre>'+html.escape((OUT/'protocol_before_run.txt').read_text())+'</pre>'+citations
    body+='<h2>验证记录</h2><pre>'+html.escape((OUT/'validation_results.json').read_text() if (OUT/'validation_results.json').exists() else '尚未运行')+'</pre>'
    css='body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;max-width:1300px;margin:40px auto;padding:0 24px;line-height:1.75;color:#243340}h1{font-size:30px}h2{margin-top:40px}.lead{background:#f1f6fa;padding:24px;border-left:5px solid #2875a2}table{border-collapse:collapse;font-size:13px;width:100%}td,th{padding:7px 9px;border-bottom:1px solid #ddd;text-align:right}img{width:100%;height:auto}figure{margin:35px 0}figcaption{color:#53636e;font-size:14px}pre{white-space:pre-wrap;background:#f7f7f7;padding:18px;font-size:13px}'
    (OUT/'局地增暖与季节系数_结果.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>局地增暖与季节系数</title><style>'+css+'</style><body>'+body+'</body></html>')
    dump={stem:caption for stem,caption in FIGS};(OUT/'figure_captions.json').write_text(json.dumps(dump,ensure_ascii=False,indent=2))
    print(small.round(4).to_string(index=False));print(sk.round(4).to_string(index=False));print(ns[ns.key.eq(PRIMARY)].round(4).to_string(index=False))


def main():
    cases=pd.read_csv(OUT/'case_monthly_tendencies.csv',parse_dates=['time'])
    q=pd.read_csv(OUT/'case_quarter_tendencies.csv');co=pd.read_csv(OUT/'seasonal_process_coefficients.csv')
    recon=pd.read_csv(OUT/'case_process_reconstructions.csv');native=pd.read_csv(OUT/'native_layer_temperature_forecasts.csv')
    figures(cases,q,co,recon,native);tables_and_report(cases,q,co,recon,native)


if __name__=='__main__':main()
