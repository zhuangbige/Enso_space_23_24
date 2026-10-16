"""Matched-timing process figures and evidence report; no new fitting."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/maryland_three_events_mpl')
import json,html,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from analyze_three_event_process_followup import ROOT,SOURCE,MODEL,OUT,EVENTS,PRIMARY,REGIONS

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
    'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','figure.dpi':120,'savefig.dpi':210})
BLUE='#2875a2';RED='#c85d45';GREEN='#3c8a73';BLACK='#28333e';GOLD='#bf8c2f'
FIGURES=[]


def save(fig,stem,caption):
    for ext in ('png','pdf','svg'):fig.savefig(OUT/f'{stem}.{ext}',bbox_inches='tight',facecolor='white')
    plt.close(fig);FIGURES.append((stem,caption))


def monthaxis(ax,context=False):
    ax.axhline(0,color='.65',lw=.7);ax.grid(axis='y',alpha=.12)
    if context:
        ax.set_xticks([-11,-5,1,7,12],['Jan −1','Jul −1','Jan 0','Jul 0','Dec 0'])
        ax.set_xlim(-11,12);ax.axvline(.5,color='.55',ls=':',lw=.8)
    else:
        ax.set_xticks([1,4,7,10,12],['Jan','Apr','Jul','Oct','Dec']);ax.set_xlim(1,12)


def figures(monthly,focus,replay,heat,volume):
    with xr.open_dataset(SOURCE/'atmosphere_monthly.nc',engine='scipy') as ds:
        fig,axes=plt.subplots(2,3,figsize=(13.8,9.6),sharey=True,layout='constrained')
        for j,event in enumerate(EVENTS):
            q=ds.sel(time=slice(f'{event-1}-01',f'{event}-12')).load()
            yy=np.arange(-11,13)
            for i,(var,lon,limit,cbar) in enumerate([('sst_anomaly','sst_lon',3.5,'SST anomaly (°C)'),('tau_anomaly','tau_lon',.06,'Eastward stress anomaly (N m$^{-2}$)')]):
                ax=axes[i,j];v=q[var].values
                im=ax.pcolormesh(q[lon],yy,v,cmap='RdBu_r',vmin=-limit,vmax=limit,shading='nearest',rasterized=True)
                ax.set_xticks([120,160,180,220,260,280],['120E','160E','180','140W','100W','80W']);ax.tick_params(axis='x',labelsize=8)
                ax.set_ylim(-11.5,12.5);ax.set_yticks([-11,-5,1,7,12],['Jan −1','Jul −1','Jan 0','Jul 0','Dec 0'])
                ax.axhline(.5,color=BLACK,lw=.9,ls='--')
                for m in focus[focus.event.eq(event)].month:
                    ax.plot([120,280],[m,m],color='black',lw=.55,alpha=.4)
                ax.set_title(f'({chr(97+i*3+j)}) {event}: '+('SST' if i==0 else 'surface stress'),loc='left')
                if j==2:fig.colorbar(im,ax=list(axes[i,:]),shrink=.82,pad=.02,label=cbar)
        fig.suptitle('SST and wind evolve across different longitudes and seasons\n5°S–5°N; 1982–2022 anomalies; year 0 = panel year, year −1 = preceding year',fontsize=14)
        save(fig,'Fig18_airsea_space_time_context','海温与纬向表面应力的24个月经度—时间演变。共用纵轴标相对年份：0为面板所示发展年，−1为前一年。上、下行分别共用色标；正应力距平表示向东异常，不一定表示绝对西风。细线只标记上一阶段选出的误差月份，不是显著性标记，也不能从月平均识别日尺度西风爆发。海气纬带±5°，区别于海洋体积±9°。')

    fig,axes=plt.subplots(3,3,figsize=(13.5,10),sharex=True,sharey='row',layout='constrained')
    for j,event in enumerate(EVENTS):
        q=monthly[monthly.year.eq(event)&monthly.event.eq(event)]
        ax=axes[0,j]
        ax.plot(q.month,q.tau,color=BLACK,lw=2,label='ERA5 anomaly')
        ax.plot(q.month,q.wind_expected_full_with_trend,color=BLUE,lw=1.6,label='Expected: trend')
        ax.plot(q.month,q.wind_expected_full_no_trend,color=RED,lw=1.6,ls='--',label='Expected: no trend')
        ax.set_title(f'({chr(97+j)}) {event}: wind response',loc='left')
        ax=axes[1,j]
        ax.plot(q.month,q.wind_z_full_with_trend,color=BLUE,lw=1.8,label='Trend reference')
        ax.plot(q.month,q.wind_z_full_no_trend,color=RED,lw=1.8,ls='--',label='No-trend reference')
        ax.set_title(f'({chr(100+j)}) SST-conditioned wind residual',loc='left',fontsize=10)
        ax=axes[2,j];z=q[q.month.gt(1)]
        ax.bar(z.month,z.residual_nino34,color=BLUE,alpha=.65,label='One-step SST residual')
        ax.plot(z.month,z.ond_propagated_residual,color=GOLD,marker='o',ms=3,lw=1.5,label='All-state residual → OND')
        ax.set_title(f'({chr(103+j)}) Distinct model residuals',loc='left',fontsize=10)
        for ax in axes[:,j]:
            for m in focus[focus.event.eq(event)].month:ax.axvspan(m-.12,m+.12,color='.5',alpha=.08,zorder=0)
            monthaxis(ax)
    axes[0,0].set_ylabel('Stress anomaly (N m$^{-2}$)');axes[1,0].set_ylabel('Wind residual / training SD')
    axes[2,0].set_ylabel('SST residual / OND contribution (°C)')
    for i in range(3):axes[i,0].legend(fontsize=8,loc='upper left')
    fig.suptitle('Wind-reference departures and model errors are different diagnostics\nAll development months shown; gray marks identify prior error-based focus months',fontsize=14)
    save(fig,'Fig19_wind_and_model_residuals','上行实际应力距平与同海温强度/型态下的统计预期；中行含趋势和不含趋势的风残差。它们不是独立大气强迫。下行蓝柱是观测状态出发的一步海温误差，金线是全部状态残差传播到OND的贡献，两者含义不同。1997年3月一步海温残差为负，而全部状态向OND传播贡献为正，不能把选出的月份直接称为缺失的瞬时增暖或西风热源。')

    fig,axes=plt.subplots(3,3,figsize=(13.8,10),sharex=True,sharey='row',layout='constrained')
    for j,event in enumerate(EVENTS):
        q=monthly[monthly.event.eq(event)]
        for region,col in zip(REGIONS,[BLUE,GOLD,RED]):
            axes[0,j].plot(q.relative_month,q[region+'_wwv_m3']/1e14,color=col,lw=1.8,label=region.title())
        for layer,col,label in [('0_50',RED,'0–50 m'),('50_150',BLUE,'50–150 m'),('150_300',GREEN,'150–300 m')]:
            axes[1,j].plot(q.relative_month,q['east_t'+layer],color=col,lw=1.8,label=label)
        for gate,col,label in [('u180',BLUE,'180°'),('u220',RED,'140°W')]:
            axes[2,j].plot(q.relative_month,q[gate+'_q_sv'],color=col,lw=1.6,label=label)
        for i,title in enumerate(['WWV26 configuration','Eastern temperature structure','Eastward volume transport anomaly']):
            ax=axes[i,j];ax.set_title(f'({chr(97+i*3+j)}) {event}: {title}',loc='left',fontsize=10);monthaxis(ax,True)
    axes[0,0].set_ylabel('WWV26 anomaly ($10^{14}$ m$^3$)')
    axes[1,0].set_ylabel('Eastern profile T anomaly (°C)')
    axes[2,0].set_ylabel('Volume transport anomaly (Sv)')
    for i in range(3):axes[i,0].legend(fontsize=8,loc='upper left',ncol=3 if i<2 else 2)
    fig.suptitle('Warm-water transport, storage, and vertical structure need separate evidence\nSODA3, 9°S–9°N; eastern box 140°W–80°W; year −1 precedes the development year',fontsize=14)
    save(fig,'Fig20_ocean_configuration_and_transport','三区暖水体积、东区不同深度温度异常与两道内部边界的暖水体积输送。三类量分别为体积、温度、体积输送；不把某断面东向输送等同为东区净储量增长。所有行均保留前一年并在案例间共用尺度。东区剖面不是Niño3.4混合层热收支。')

    fig,axes=plt.subplots(2,3,figsize=(13.5,7),sharex=True,sharey=True,layout='constrained')
    for j,event in enumerate(EVENTS):
        for i,gate in enumerate(['u180','u220']):
            ax=axes[i,j]
            for term,col,label in [('mean_flow_temperature_anomaly_pw',BLUE,'Mean flow × T′'),('anomalous_flow_mean_temperature_pw',RED,'Flow′ × mean T')]:
                for geom,ls in [('instantaneous','-'),('climatological',':')]:
                    q=heat[heat.year.eq(event)&heat.gate.eq(gate)&heat.geometry.eq(geom)].sort_values('month')
                    ax.plot(q.month,q[term],color=col,ls=ls,lw=1.8 if ls=='-' else 1.1,label=label if ls=='-' else None)
            ax.set_title(f'({chr(97+i*3+j)}) {event}: '+('180°' if i==0 else '140°W'),loc='left');monthaxis(ax)
            if j==0:ax.set_ylabel('Eastward heat contribution (PW)')
    axes[0,0].legend(fontsize=9)
    fig.suptitle('Two heat-transport terms at the internal boundaries\nSolid: instantaneous σ26 section; dotted: climatological section; both gates have complete effective coverage',fontsize=14)
    save(fig,'Fig21_two_term_heat_transport','按草稿纸指定的两项分解展示内部断面的热输送贡献，正值向东。两个内部断面有效覆盖率均为100%，但两项之和仍不含全部热输送距平，异常流项也不等于纯风驱贡献。所用温度参考为0°C，不将PW直接转换或命名为海温增长率。')

    fig,axes=plt.subplots(3,3,figsize=(13.5,9.5),sharex=True,sharey=True,layout='constrained')
    windows=['0115_to_0415','0415_to_0715','0715_to_1015','1015_to_1215']
    positions=np.arange(4)
    for i,reg in enumerate(REGIONS):
        for j,event in enumerate(EVENTS):
            ax=axes[i,j];q=volume[(volume.event==event)&(volume.region==reg)&volume.baseline.eq('monthly_mean')].set_index('window').loc[windows]
            horizontal=q.zonal_input+q.meridional_input
            ax.bar(positions-.25,q.storage_change,width=.24,color=BLACK,label='Storage change')
            ax.bar(positions,horizontal,width=.24,color=BLUE,label='Horizontal input')
            ax.bar(positions+.25,q.unresolved,width=.24,color=GOLD,label='Unresolved')
            ax.axhline(0,color='.5',lw=.7);ax.set_xticks(positions,['Jan–Apr','Apr–Jul','Jul–Oct','Oct–Dec'],rotation=15)
            ax.set_title(f'({chr(97+i*3+j)}) {event}: {reg.title()}',loc='left');ax.grid(axis='y',alpha=.12)
            if j==0:ax.set_ylabel('Interval change ($10^{14}$ m$^3$)')
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Horizontal transport does not close every regional volume change\nIntervals run from the 15th to the 15th; Oct–Dec is two months; unresolved = storage − horizontal input',fontsize=14)
    save(fig,'Fig22_interval_volume_budget','共同月中到月中区间的体积变化、水平输入与未解析项。Jan—Apr、Apr—Jul、Jul—Oct均跨三个月中点，Oct—Dec只有两个月，不作为完整OND积分。每柱单位相同，不将累计量直接比较为平均强度。未解析项不能命名为海表热损失或已识别混合。')

    fig,axes=plt.subplots(2,3,figsize=(13.5,7.6),sharex=True,sharey='row',layout='constrained')
    for j,event in enumerate(EVENTS):
        for i,(var,exp) in enumerate([('nino34','observed_ocean_replay'),('east_wwv','observed_sst_replay')]):
            ax=axes[i,j];q=replay[(replay.key==PRIMARY)&(replay.year==event)&(replay.variable==var)]
            observed=q[q.experiment.eq('free')]
            ax.plot(observed.month,observed.observed,color=BLACK,lw=2.4,label='Observed / SODA3')
            ax.plot(observed.month,observed.predicted,color=BLUE,lw=1.8,label='Free sLIM')
            sub=q[q.experiment.eq(exp)]
            ax.plot(sub.month,sub.predicted,color=RED,lw=1.8,label='Observed-state replay')
            ax.set_title(f'({chr(97+i*3+j)}) {event}: '+('SST, given observed ocean' if i==0 else 'Eastern WWV, given observed SST'),loc='left',fontsize=10)
            monthaxis(ax)
    axes[0,0].set_ylabel('Niño3.4 anomaly (°C)');axes[1,0].set_ylabel('East WWV26 anomaly ($10^{14}$ m$^3$)')
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Observed-state replay localizes the model limitation\nRetrospective monthly state replacement; fixed parameters; these are not independent forecasts',fontsize=14)
    save(fig,'Fig23_observed_state_replay','上行每次积分前把三个海洋状态替换为该月诊断值，只让海温逐月延续；下行把该月海温替换为观测，延续海洋状态，图示东区。每步只使用上一月输入，但整个轨迹多次读取发展期观测，不能计入独立预报技巧或理解为物理干预。所有状态及参数敏感性另存CSV。')


def report(monthly,focus,replay,scores,volume,heat):
    d=scores[(scores.key==PRIMARY)&scores.variable.eq('nino34')]
    table=d.pivot(index='year',columns='experiment',values='ond_pred')[['free','observed_ocean_replay']]
    table['observed']=d.groupby('year').ond_obs.first()
    table=table.rename(columns={'free':'自由模拟','observed_ocean_replay':'实际海洋逐月输入','observed':'观测'})
    table.to_csv(OUT/'primary_replay_table.csv')
    q=pd.read_csv(OUT/'common_quarter_evidence.csv')
    # Derived primary-source evidence used in the text, retained as reviewable tables.
    air=q[q.quarter.isin([2,3])][['event','quarter','tau','wind_z_full_with_trend','wind_z_full_no_trend','u220_q_sv','east_t0_50','east_t50_150']]
    air.to_csv(OUT/'spring_summer_evidence_table.csv',index=False)
    ss=scores[scores.variable.eq('nino34')&scores.experiment.eq('observed_ocean_replay')]
    ranges=ss.groupby('year').ond_pred.agg(['min','max'])
    ranges.to_csv(OUT/'replay_estimator_background_ranges.csv')
    structural=monthly[monthly.year.eq(monthly.event)&monthly.month.eq(1)][['event','west_wwv_m3','central_wwv_m3','east_wwv_m3','west_t50_150','east_t50_150']]
    focus_small=focus[['event','month','tau','wind_z_full_with_trend','wind_z_full_no_trend','residual_nino34','ond_propagated_residual','u180_q_sv','u220_q_sv']]
    focus_small.to_csv(OUT/'focus_evidence_table.csv',index=False)
    summary='''三案例过程追溯：暖水到达、海温增暖与西风响应未形成一条已验证的单因果链

本轮完成了上一阶段sLIM失配后的过程对照。沿用原模型和统一物理口径，没有重新拟合、没有按三个目标结果挑选参数。所有24个月记录与发展年各月均展示，选出的误差月份只作探索性重点，不开展选择后显著性检验。

一、当前最清楚的共同对比
2023年4—6月，Niño3.4平均距平约0.65°C，160°E—140°W、5°S—5°N平均向东表面应力距平为−0.0030 N/m²；1997、2015同期分别为+0.0275、+0.0164 N/m²。2023年7—9月应力距平为+0.0056 N/m²，仍小于1997、2015的+0.0323、+0.0303 N/m²。这是明确的月/季节平均响应差异，不能直接命名为日尺度西风爆发频次差异。
相同SST强度与型态下的风参考仍有趋势敏感性。2023年AMJ/JAS平均风残差：含趋势约+0.07/+0.09个训练残差标准差，不含趋势约−1.00/−1.16。因此可写“2023春夏西风响应弱于1997/2015”，但不宜无条件写“2023显著偏离同海温下预期、已经脱耦”。这些标准差也不是个例显著性阈值。

二、2023春季并不是没有东向暖水输送
140°W的暖水体积东向输送距平在2023年4—6月平均为19.55 Sv，高于2015的11.07 Sv，低于1997的38.91 Sv。2023年4月15日至7月15日东区WWV26增加1.309×10^14 m³；纬向输入为1.132×10^14 m³，经向输入为−0.655×10^14 m³，未解析项为+0.832×10^14 m³。已有输送与东区增长同时存在，但完整体积闭合还不能由水平项给出。
2023年4—6月东区0—50m温度距平为1.18°C，50—150m为0.35°C；2015对应1.32/1.26°C，1997对应1.09/1.49°C。2023的近表层和次表层暖异常垂直配置不同，不能用总暖水体积或一层温度互相替代。它提供“储备如何与近表面增暖连接”的结构线索，尚未证明哪一种垂直过程造成该差异。

三、2023夏季输送与储量演变又发生变化
2023年7—9月140°W东向体积输送距平降为2.35 Sv，180°为−8.49 Sv；对应2015为10.38/+1.92 Sv，1997为13.72/+16.00 Sv。负距平表示相对气候态减弱或向西异常，不代表绝对流向必然向西。2023年7月15日至10月15日东区WWV26只增加0.042×10^14 m³，而1997/2015分别增加1.955/1.043×10^14 m³。
2023的该区间纬向输入为+0.225，经向输入为−0.634，未解析项+0.450，单位均10^14 m³。因此“夏季东部储量增长接近停滞、东向输入减弱”得到支持，但不能说已闭合地证明由某一道水平输送单独造成。西区同段未解析项为−1.738×10^14 m³，也不能直接命名为海表散热。
两个内部断面的两项热输送有效覆盖率都是100%。2023年AMJ的140°W平均流×温度异常、异常流×平均温度贡献为+0.274/+1.900 PW，JAS降为+0.002/+0.464 PW。这个时序与暖水输送减弱相容，但两项不是完整热输送距平，开放断面也不是Niño3.4区域热收支。异常流项较大并不自动等于已证明风驱主导。

四、风残差、一步海温误差和传播到年底的误差不能混用
1997年3月含趋势风残差为+2.54个标准差，一步海温残差却为−0.21°C，而全部状态残差向OND传播贡献为+0.39°C。2015年2月风残差接近零（−0.02个标准差），一步海温残差约+0.36°C。2023年6月一步海温残差约+0.45°C，同期应力距平为−0.0041 N/m²、含趋势风残差为−0.70个标准差。
这些对照不支持把所有遗漏增暖统一叫作“缺少西风强迫”。完整状态残差包括海洋变化，它传播到未来的贡献可以与当月海温残差异号；风与海温在不同空间和时间尺度发生响应。本轮也没有通过三个已选事件的滞后相关来替代物理归因。

五、实际暖水配置逐月输入，仍不能让当前模型解释增暖
固定sLIM参数，每个月从上一月实际三区WWV26和延续的模拟海温出发。年底海温结果（OND，°C）：
'''+table.to_string(float_format=lambda x:f'{x:.3f}')+'''

2023在四种预先已有的估计/背景设置下，实际海洋输入都比相应自由模拟更冷；重放的OND范围为−0.506至+0.269°C，仍远低于观测1.922°C。2015重放范围0.272—1.061°C，也未恢复观测2.615°C。1997为0.616—1.110°C，未恢复2.231°C。这说明局限不只是“模型没走出实际暖水配置”，还包括WWV26到海温演变的统计表示及其遗漏过程。绝不能把2023重放变冷解释成“真实海洋抑制了厄尔尼诺”。
反向每月输入实际海温时，模拟东区WWV26有所改善：2023年OND从自由模拟−0.271升为1.282×10^14 m³，SODA3为1.492×10^14 m³；但是中区RMSE反而增加，其他案例东区仍低估。它是同一模型的条件诊断，不证明海温是海洋变化的唯一原因。因多次使用发展期观测，重放不属于独立预报，不可与初始化自由预报混排技巧。

六、对论文主线和下一步的约束
目前可以写：2023年虽有前期西部暖水储备和春季向东输送，其东部垂直温度结构、夏季暖水输送持续性及海温—西风响应均与1997/2015不同。不能写成“总暖水不足”“暖水未向东到达”或“已由海洋初态唯一决定反馈差异”。共同1月只是季节参照，尚不能据这些对照证明三次事件共同的因果起点或严格的海洋领先顺序。
优先补充的证据是Niño3.4区域、统一上层深度内的实际温度倾向及输送贡献，先聚焦2023年春季到夏季，同时保留1997/2015同季节参照。已有断面PW不能直接作为这个方程的°C/月项，也不能通过除以任意暖水体积就冒称混合层增长率。垂直配置线索支持更细的加热过程诊断；在其区域、层次和残差明确之后，再估计这些过程与sLIM季节系数的联系。对流诊断仍按原约定，仅对海温—风关系解释不清的具体阶段补充。

所有新结果只用于这三个案例的过程比较与模型局限定位。本轮未扩展历史事件、未拟合新状态、未改变WWV26定义、未新增初态替换的因果结论。
'''
    (OUT/'过程追溯_中文结果.txt').write_text(summary,encoding='utf-8')
    # Preserve a compact manuscript-ready paragraph with inference boundaries.
    paragraph='''2023年厄尔尼诺发展期呈现暖水输送与海气响应之间的阶段性差异。春季（4—6月）140°W东向暖水体积输送距平达到19.55 Sv，高于2015年同期，东区暖水储量亦增加，但中西太平洋纬向表面应力距平仍为负。同期东区近表层已明显增暖，而50—150m暖异常弱于1997和2015。进入7—9月，140°W东向输送距平减弱至2.35 Sv，7月中至10月中东区储量增长接近停滞，西风响应仍较两个对照事件弱。上述结果表明，只以暖水总量或春季输入强度描述2023年发展条件并不充分；暖水的垂直配置及输送持续性需要同时考虑。但风响应偏离历史预期的程度依赖趋势处理，体积收支也存在显著未解析项，因此这些过程对应尚不能确认为闭合的因果机制。'''
    (OUT/'论文结果候选段落.txt').write_text(paragraph,encoding='utf-8')
    content=''.join('<p>'+html.escape(p).replace('\n','<br>')+'</p>' for p in summary.split('\n\n'))
    gallery=''.join(f'<figure><img src="{stem}.png"><figcaption>{html.escape(caption)}</figcaption></figure>' for stem,caption in FIGURES)
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>三案例海气与海洋过程追溯</title><style>
body{max-width:1140px;margin:42px auto;padding:0 28px;font:17px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;background:#f8fafb;color:#253642}h1{font-size:29px;line-height:1.4}.lead{padding:20px;border-left:5px solid #c85d45;background:#fff5ef}figure{background:white;margin:36px 0;padding:16px;border-radius:10px}img{width:100%;height:auto}figcaption{font-size:15px;color:#4e6070}table{width:100%;border-collapse:collapse;background:white}td,th{padding:8px;text-align:right;border-bottom:1px solid #dbe1e7}a{color:#2875a2}</style>
<h1>2023春季已有东向暖水输送，但海温—西风响应与后续输送持续性不同</h1>
<p class="lead">实际暖水配置逐月输入后，当前四状态sLIM仍不能重现三次事件的增暖。新的过程证据支持检查垂直温度结构、夏季输送持续性及实际温度倾向；尚不支持把模型残差直接叫作西风强迫。</p>'''
    doc+=table.round(3).to_html()+gallery+content+'</html>'
    (OUT/'海气与海洋过程追溯_结果.html').write_text(doc,encoding='utf-8')
    methods='''REPRODUCTION AND INTERPRETATION
Run from the repository root, using the installed Anaconda Python:
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python scripts/analyze_three_event_process_followup.py
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python scripts/report_three_event_process_followup.py
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python scripts/validate_three_event_process_followup.py

No fitting or event-specific adjustments are introduced. Source diagnostics,
units, latitude bands and baseline are inherited from the audited stage-one
products. Dynamic coefficients are read from the preceding sLIM stage. The four
predeclared exact/perturbative and mean/detrended variants are all retained.

Monthly diagnostic replay uses Phi_m (four-state monthly propagator):
T_replay(m+1) = Phi_TT(m)*T_replay(m) + Phi_TH(m)*H_observed(m).
Reverse replay advances H_replay with SST_observed at each step. The starting
January state is observed. Stored values are one-step predictions BEFORE the
next reset. All calculations use each fixed fit's model anomalies, and outputs
are restored to source 1982--2022 monthly display anomalies. This is neither an
independent forecast nor an exogenous causal intervention. The reverse-replay
SST is repeatedly reset, so its apparent SST skill must not be promoted as free
SST prediction. Compare its ocean states only. Analogously compare ocean-replay
SST only, not ocean states which were reset every previous month.

For each transition, e_m=x_obs(m)-Phi_(m-1)*x_obs(m-1) has state units. This
one-step SST residual differs from the previous full-state error propagated to
OND, and from the contemporaneous wind regression residual. No lag correlation
or selected-month p-value is used to attribute these residuals to wind.

Interval volume anomaly budgets integrate (west-east) and (south-north) gate
anomalies by the trapezoid rule between adjacent monthly 15ths using actual
seconds. Sv*seconds/1e8 gives units of 1e14 m3. WWV storage changes use endpoint
differences. Unresolved=storage-zonal-meridional, without physical naming. This
midmonth treatment is a discrete approximation of monthly-mean data, not daily
resolved tendency. Common quarter means are simple arithmetic monthly means;
Jan15-Apr15 etc. integrals are separate and not mislabeled as full quarters.

The two heat terms at 180 and 140W have complete effective coverage in existing
diagnostics. Instantaneous and climatological density sections are both shown.
Mean-flow*T' and flow'*mean-T omit nonlinear/background geometry contributions;
their sum is not a complete heat-transport anomaly or closed SST budget. They
cannot be converted into a local SST tendency without a matching heat budget.

Target exclusions and reference uncertainty remain as in the prior stage:
1996--98, 2014--16, 2022--24 omitted from fitting; wind-reference trend sensitivity
shown explicitly. Diagnostics may use target observations, as intended. Prior
top-three months are exploratory focus only; all months and quarters are saved.
No new convection result, vertical heat budget, or initial-state causal claim.
'''
    (OUT/'methods_and_reproduction.txt').write_text(methods,encoding='utf-8')
    (OUT/'figure_captions.json').write_text(json.dumps(dict(FIGURES),ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    monthly=pd.read_csv(OUT/'all_month_evidence.csv',parse_dates=['time']);focus=pd.read_csv(OUT/'previously_selected_error_months.csv')
    replay=pd.read_csv(OUT/'observed_state_replay.csv');scores=pd.read_csv(OUT/'replay_scores.csv')
    volume=pd.read_csv(OUT/'volume_interval_summaries.csv');heat=pd.read_csv(OUT/'internal_gate_heat_terms.csv')
    figures(monthly,focus,replay,heat,volume);report(monthly,focus,replay,scores,volume,heat)
    print('Wrote',len(FIGURES),'figure groups and Chinese/English reports',flush=True)


if __name__=='__main__':main()
