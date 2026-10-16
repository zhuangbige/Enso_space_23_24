"""Assemble existing forecast and process evidence; no new model fits."""
from pathlib import Path
import os, json, hashlib, html
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/maryland_three_events_mpl')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/research_2026/pmm_advection_bridge_20261015'
OUT.mkdir(parents=True, exist_ok=True)
F = ROOT/'outputs/interview_redesign_20261014/source_data'
P = ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015'
W = ROOT/'outputs/research_2026/three_event_process_followup_20261015'
files = [F/'RO_PMM_three_event_metrics.csv', F/'RO_PMM_three_event_trajectories.csv',
         P/'case_monthly_tendencies.csv', P/'summer_zonal_advection_robustness.csv',
         P/'primary_season_result_table.csv', W/'all_month_evidence.csv']
metrics, forecasts, monthly, robust, seasons, winds = [pd.read_csv(p) for p in files]
years = [1997, 2015, 2023]
colors = ['#2878a6', '#d58a24', '#bd493c']
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11,
                    'axes.spines.top':False,'axes.spines.right':False,
                    'pdf.fonttype':42, 'svg.fonttype':'none'})
rows=[]
for y in years:
    a=metrics[metrics.year.eq(y)].set_index('model')
    t=forecasts[forecasts.year.eq(y)&forecasts.lead_center.between(1,5)]
    p=t.pivot(index=['init','center','lead_center'],columns='method',values='value')
    assert len(p)==25 and p[['RO','RO_SST']].notna().all().all()
    obs=t.drop_duplicates(['init','center','lead_center']).set_index(['init','center','lead_center']).observed
    for name in ['RO','RO_SST']:
        error=p[name]-obs
        assert np.isclose(np.sqrt(np.mean(error**2)), a.loc[name,'RMSE'],atol=1e-10)
    correction=(p.RO_SST-p.RO).mean()
    assert np.isclose(correction,a.loc['RO_SST','bias']-a.loc['RO','bias'])
    r=robust[robust.event.eq(y)&robust.depth_m.eq(50)].set_index('background')
    s=seasons[seasons.event.eq(y)&seasons.quarter.eq(3)].iloc[0]
    m=monthly[monthly.event.eq(y)&monthly.depth_m.eq(50)&monthly.relative_month.between(7,9)]
    assert np.isclose(m.u_prime_meanT.mean(),r.loc['mean','JAS_zonal_advective_contribution'])
    rows.append(dict(event=y,RMSE_RO=a.loc['RO','RMSE'],RMSE_PMM=a.loc['RO_SST','RMSE'],
        skill_percent=100*(1-a.loc['RO_SST','RMSE']/a.loc['RO','RMSE']),
        mean_forecast_correction=correction,bias_RO=a.loc['RO','bias'],bias_PMM=a.loc['RO_SST','bias'],
        advection_mean=r.loc['mean','JAS_zonal_advective_contribution'],
        advection_detrend=r.loc['detrend','JAS_zonal_advective_contribution'],
        horizontal_total=s.mean_flow+s.anomalous_flow+s.nonlinear_hadv,
        surface_proxy=s.surface_flux_proxy,unresolved=s.unresolved,net_tendency=s.tendency))
summary=pd.DataFrame(rows).set_index('event')
summary.to_csv(OUT/'bridge_summary.csv')

def style(ax):
    ax.axhline(0,color='#777777',lw=.7)
    ax.grid(axis='y',alpha=.15)
    ax.set_axisbelow(True)

def save(fig,name):
    for ext in ['png','pdf','svg']:
        fig.savefig(OUT/f'{name}.{ext}',dpi=180,bbox_inches='tight',facecolor='white')
    plt.close(fig)

fig,axs=plt.subplots(2,2,figsize=(13,8.5))
fig.subplots_adjust(top=.88,bottom=.16,hspace=.48,wspace=.26)
fig.suptitle('PMM forecast changes and the observed advection contrast',fontsize=19,y=.97)
fig.text(.5,.925,'Parallel evidence across 1997, 2015 and 2023; the causal link remains to be tested',ha='center',color='#555555')
x=np.arange(3);width=.32
ax=axs[0,0]
ax.bar(x-width/2,summary.RMSE_RO,width,color='#9caab4',label='RO')
ax.bar(x+width/2,summary.RMSE_PMM,width,color='#326b8e',label='RO + PMM')
for i,y in enumerate(years):
    ax.text(i,max(summary.loc[y,['RMSE_RO','RMSE_PMM']])+.045,
        f"Skill {summary.loc[y,'skill_percent']:+.1f}%",ha='center',fontsize=10)
ax.set(title='(a) Retrospective SST forecast error',ylabel='RMSE (°C)',ylim=(0,.98))
ax.legend(frameon=False,ncol=2,loc='upper left')
ax=axs[0,1]
ax.bar(x,summary.mean_forecast_correction,.5,color=colors)
for i,v in enumerate(summary.mean_forecast_correction):
    ax.text(i,v+(.012 if v>0 else -.012),f'{v:+.3f}',ha='center',va='bottom' if v>0 else 'top')
ax.set(title='(b) Mean SST correction: RO + PMM minus RO',ylabel='Paired forecast difference (°C)',ylim=(-.17,.20))
ax.text(.03,.95,'All three RO baselines underestimate SST',transform=ax.transAxes,va='top',fontsize=10,color='#555555')
ax=axs[1,0]
ax.bar(x-width/2,summary.advection_mean,width,color='#6e92aa',label='Monthly-mean background')
ax.bar(x+width/2,summary.advection_detrend,width,color='#c08b4d',label='Process trend also removed')
ax.set(title=r'(c) JAS anomalous zonal advection: $-u^\prime\partial_x\overline{T}$',ylabel='0–50 m tendency (°C / standard month)',ylim=(-.09,.24))
ax.legend(frameon=False,fontsize=9,loc='upper left')
ax=axs[1,1]
ax.bar(x-.22,summary.horizontal_total,.22,color='#2878a6',label='Total horizontal')
ax.bar(x,summary.surface_proxy,.22,color='#69a38e',label='Surface flux proxy')
ax.bar(x+.22,summary.unresolved,.22,color='#a6a0ab',label='Unresolved')
ax.scatter(x,summary.net_tendency,color='black',marker='_',s=350,zorder=5,label='Net tendency')
ax.set(title='(d) JAS process context: weaker cooling in 2023',ylabel='0–50 m tendency (°C / standard month)',ylim=(-.55,.64))
ax.legend(frameon=False,fontsize=9,ncol=2,loc='upper left')
for ax in axs.flat: style(ax);ax.set_xticks(x,years)
fig.text(.07,.075,'Forecast: 25 overlapping start–season pairs/event, February–June starts, common center leads 1–5.\n'
         'Frozen 2002–2024 fits: 1997 is backward-applied; 2015/2023 are in sample. Model differences include refitted coefficients.\n'
         'Process: Niño3.4, 0–50 m, target-excluded training background. Surface flux is a proxy; unresolved terms remain substantial.',
         fontsize=9,color='#555555',va='center')
save(fig,'Bridge01_skill_correction_advection')

fig,axs=plt.subplots(3,3,figsize=(15,10),sharex='col',sharey='row')
fig.subplots_adjust(top=.89,bottom=.13,hspace=.23,wspace=.12)
fig.suptitle('From forecast changes to wind stress and local advection',fontsize=19,y=.97)
fig.text(.5,.93,'Common event calendar; shaded months mark JAS. No PMM-attributed wind or current has been estimated.',ha='center',color='#555555')
for j,y in enumerate(years):
    t=forecasts[forecasts.year.eq(y)].copy()
    t['month']=pd.to_datetime(t.center).dt.month
    t=t[pd.to_datetime(t.center).dt.year.eq(y)]
    for k,(name,col,ls) in enumerate([('RO','#8e9aa3','--'),('RO_SST','#326b8e','-')]):
        for n,(init,g) in enumerate(t[t.method.eq(name)].groupby('init')):
            g=g.sort_values('month')
            axs[0,j].plot(g.month,g.value,color=col,ls=ls,lw=1,alpha=.7,label=('RO' if name=='RO' else 'RO + PMM') if n==0 else None)
    obs=t.groupby('month')['observed'].first()
    axs[0,j].plot(obs.index,obs.values,color='black',lw=2.2,label='Observed')
    axs[0,j].set_title(f'{y}  |  skill change {summary.loc[y,"skill_percent"]:+.1f}%')
    w=winds[winds.event.eq(y)&winds.relative_month.between(1,12)].sort_values('relative_month')
    axs[1,j].plot(w.relative_month,w.tau,color=colors[j],lw=2)
    m=monthly[monthly.event.eq(y)&monthly.depth_m.eq(50)&monthly.relative_month.between(1,12)].sort_values('relative_month')
    axs[2,j].plot(m.relative_month,m.u_prime_meanT,color=colors[j],lw=2,label='Anomalous zonal advection')
    axs[2,j].plot(m.relative_month,m.surface_flux_proxy,color='#69a38e',ls='--',lw=1.6,label='Surface flux proxy')
    for ax in axs[:,j]:
        ax.axvspan(6.5,9.5,color='#e4c884',alpha=.19); style(ax)
        ax.set_xticks([1,3,5,7,9,11],['Jan','Mar','May','Jul','Sep','Nov']);ax.set_xlim(1,12)
axs[0,0].set_ylabel('Seasonal Niño3.4 SSTA (°C)')
axs[1,0].set_ylabel('Zonal wind stress anomaly (Pa)')
axs[2,0].set_ylabel('0–50 m tendency\n(°C / standard month)')
axs[0,0].legend(frameon=False,fontsize=9)
axs[2,0].legend(frameon=False,fontsize=9,loc='lower left')
fig.text(.07,.055,'Top: all five February–June forecasts, retained within development year; scoring remains common center leads 1–5.\n'
 'Middle: ERA5 monthly stress, 5°S–5°N, 160°E–140°W, inherited 1982–2022 anomaly baseline. Positive = eastward anomaly.\n'
 'Bottom: Niño3.4 process terms, target-excluded monthly-mean background. Distinct baselines/variables are not quantitatively equated.',fontsize=9,color='#555555')
save(fig,'Bridge02_forecast_wind_advection_timing')

assets=[
 ('Bridge01_skill_correction_advection.png','1. 桥接总图（新增）','预报误差 → 海温修正方向 → 夏季异常纬向平流 → 其他温度倾向。上排为既有预报表，下排为最新过程表。'),
 ('Bridge02_forecast_wind_advection_timing.png','2. 逐月桥接图（新增）','三列固定1997、2015、2023；上排预报轨迹，中排赤道风应力，下排局地平流与海表项。阴影为7—9月。逐月对应是机制线索，尚未构成PMM→风→流的归因。'),
 (os.path.relpath(W/'Fig18_airsea_space_time_context.png',OUT),'3. 已有 Fig18：海温—风应力经度时间图','展示风应力的空间位置和持续性，可置于预报结果与平流诊断之间。月平均不能识别西风爆发。'),
 (os.path.relpath(P/'Fig24_matched_local_process_history.png',OUT),'4. 已有 Fig24：局地温度与过程完整时序','展示前一年到发展年，检查春季建立、夏季减弱及未解析倾向。'),
 (os.path.relpath(P/'Fig25_common_season_process_comparison.png',OUT),'5. 已有 Fig25：春夏温度倾向分解','说明2023平流偏弱同时海表冷却较弱；未解析项较大，不能将弱增暖归结为单一过程。'),
 (os.path.relpath(P/'Fig29_zonal_advection_robustness.png',OUT),'6. 已有 Fig29：平流结果稳健性','30/50/75 m与两种趋势处理均保留2023相对偏弱。绝对正负号不稳健。')]
body=''.join(f'<section><h2>{title}</h2><p>{desc}</p><a href="{html.escape(path)}"><img src="{html.escape(path)}" alt="{title}"></a></section>' for path,title,desc in assets)
table=summary.round(4).to_html()
report='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>PMM与平流：证据桥梁</title><style>body{font-family:system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;color:#203040;line-height:1.8;background:#f6f8fa}section{background:white;padding:24px;margin:28px 0;border-radius:10px}img{width:100%}h1{font-size:30px}h2{font-size:22px}table{font-size:11px;border-collapse:collapse}td,th{padding:5px;border:1px solid #ddd}.data{overflow:auto}.claim{border-left:5px solid #326b8e;padding:10px 22px;background:#eaf1f5}</style>
<h1>PMM预报结果与异常纬向平流：现有证据如何连接</h1>
<p>2026-10-15｜整合已有数据和图件，未重新拟合模型，也未新增因果归因。</p>
<div class="claim"><b>核心桥梁：</b>PMM扩展模型对1997/2015上调海温并改善回报，对2023下调并加重低估；实际诊断中2023夏季异常纬向平流增暖较弱。两者支持检验PMM相关风场对动力增暖的调制，但平流偏弱本身不能解释预报技巧为何下降。后者还取决于基准偏差、修正量级以及其他过程的抵消。</div>
<h2>可以直接用于结果之间的过渡段</h2><p>加入PMM后，1997、2015事件的回报RMSE分别下降13.0%和19.2%，2023则增加30.2%。这一差异对应于模型对前两次事件的海温上调及对2023的下调。为识别这些修正可能对应的海洋过程，我们进一步比较三次事件的局地温度倾向。结果显示，2023年7—9月异常纬向平流增暖贡献稳健地弱于1997和2015，但海表冷却代理项也较弱。因此，PMM扩展模型中的降温修正与较弱动力增暖在方向上相容，其预报技巧下降则提示仍需检验模型是否过度抑制增暖，或未充分表示其他过程的抵消；现有结果尚不能判定是哪一种。</p>
<h2>证据边界与下一步</h2><p>三事件预报采用冻结的2002—2024参数：1997为后期参数回推，2015/2023在拟合期内，是回顾性个例技巧。加入PMM也重新估计T/h子矩阵，模型间差值不能全称为PMM直接效应。每事件25个重叠配对仅有9个不同目标季节。过程量是Niño3.4固定层温度倾向，预报量是季节SST，两者不直接相减或用净倾向比例归因。</p>
<p>最小后续检验：固定增广模型的其他系数，比较完整模型与切断PMM→T/h的逐月差异；另用同一背景下的PMM、风应力、异常流速和平流项检验时序。直接诊断模型是否恢复平流过程，并比较海表项和未解析项；当前没有PMM归因风场、流场或平流反事实，不拟合只有三个事件的相关线。</p>'''+body+'<h2>桥接汇总数据</h2><p>skill_percent = 100 × (1 − RMSE_PMM / RMSE_RO)；正值为改善。mean_forecast_correction为25个配对平均，非JAS单季修正。过程单位°C/标准月。</p><div class="data">'+table+'</div><p><a href="bridge_summary.csv">下载CSV</a> · <a href="Bridge01_skill_correction_advection.pdf">总图PDF</a> · <a href="Bridge02_forecast_wind_advection_timing.pdf">时序图PDF</a></p></html>'
(OUT/'index.html').write_text(report)
(OUT/'source_manifest.json').write_text(json.dumps({'sources':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files], 'validation':'Recomputed each event RMSE from 25 original pairs; mean correction matches bias difference; JAS monthly advection matches robustness table. All assertions passed.','script':str(Path(__file__).resolve())},ensure_ascii=False,indent=2))
print(summary.to_string())
print(OUT/'index.html')
