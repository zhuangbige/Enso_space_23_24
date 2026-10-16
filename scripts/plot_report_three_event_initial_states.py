"""Figures and bilingual report for the common-parameter initial-state experiment."""
import os
import argparse
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/maryland_three_events_mpl')
import json
from html import escape
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from experiment_three_event_initial_states import OUT, SOURCE, ROOT, PRIMARY, EVENTS, MODELS

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none',
                     'figure.dpi':130,'savefig.dpi':220})
COLORS={1997:'#246b9b',2015:'#c85449',2023:'#32836c'}
LABELS={'sst_only':'SST only (2)','total_volume':'SST + total WWV (3)',
        'three_volumes':'SST + W/C/E WWV (5)','volume_temperature':'+ W/C/E subsurface T (8)',
        'with_deep_west':'+ deep western T (9)'}
FIGURES=[]


def save(fig,stem,caption):
    for ext in ('png','pdf','svg'):fig.savefig(OUT/f'{stem}.{ext}',bbox_inches='tight',facecolor='white')
    plt.close(fig);FIGURES.append((stem,caption))


def time_axis(ax):
    ax.set_xticks([1,4,7,10,12],['Jan','Apr','Jul','Oct','Dec'])
    ax.set_xlim(1,12);ax.axhline(0,color='.7',lw=.7);ax.grid(axis='y',alpha=.15)


def figures():
    tr=pd.read_csv(OUT/'initial_swap_trajectories.csv')
    boot=pd.read_csv(OUT/'bootstrap_trajectories.csv')
    clim=pd.read_csv(OUT/'display_climatology_1982_2022.csv').set_index('month')
    native=pd.read_csv(OUT/'native_initialization_skill.csv')
    main=tr.loc[tr.model.eq(PRIMARY)&~tr.detrend&tr.swap.eq('direct')]
    fig,ax=plt.subplots(2,3,figsize=(13.6,7.6),sharex=True,sharey='row',layout='constrained')
    for j,event in enumerate(EVENTS):
        f=main.loc[main.sst_year.eq(event)&main.ocean_year.eq(event)]
        sensitivity=tr.loc[tr.model.eq(PRIMARY)&tr.detrend&tr.swap.eq('direct')&tr.sst_year.eq(event)&tr.ocean_year.eq(event)]
        b=boot.loc[boot.sst_year.eq(event)&boot.ocean_year.eq(event)]
        for i,(variable,label,absolute) in enumerate([('nino34','Nino3.4 anomaly (°C)','nino34_absolute'),('tau','Zonal stress anomaly (N m$^{-2}$)','tau_absolute')]):
            a=ax[i,j]
            ci=b.groupby('month')[absolute].quantile([.025,.975]).unstack()
            lo=ci[.025].to_numpy()-clim.loc[np.arange(1,13),variable].to_numpy()
            hi=ci[.975].to_numpy()-clim.loc[np.arange(1,13),variable].to_numpy()
            a.fill_between(np.arange(1,13),lo,hi,color='#246b9b',alpha=.15,label='95% parameter range')
            a.plot(f.month,f[variable+'_observed'],color='#242a30',lw=2.2,label='Observed')
            a.plot(f.month,f[variable+'_predicted'],color='#246b9b',lw=2,label='Free model, monthly means')
            a.plot(sensitivity.month,sensitivity[variable+'_predicted'],color='#ba7826',ls='--',lw=1.4,label='Trend sensitivity')
            if variable=='tau':a.plot(f.month,f.tau_from_observed_sst,color='.55',ls=':',label='Wind closure with observed SST')
            time_axis(a)
            a.set_title(f'({chr(97+i*3+j)}) {event}' if i==0 else f'({chr(97+i*3+j)}) Diagnosed wind')
            if j==0:a.set_ylabel(label)
        metric=native.loc[native.model.eq(PRIMARY)&~native.detrend&native.event.eq(event)].iloc[0]
        ax[0,j].text(.03,.96,f'Feb–Dec RMSE = {metric.feb_dec_rmse_C:.2f}°C',transform=ax[0,j].transAxes,va='top',fontsize=9)
    handles,labels=ax[1,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,fontsize=8.5,frameon=False)
    fig.suptitle('7 | Native January states fail to reproduce full event growth\nOne common 8-state model; no observations supplied after January',fontsize=14)
    save(fig,'Fig07_native_initialization',
         '图7：原配1月初态的自由模拟，黑线为观测，蓝线为8状态主模型，橙虚线为训练期去趋势敏感性。三事件及前后一年均排除于训练。阴影为300次两年块重采样的参数区间，未包含未来天气扰动和模型误差，不能当作事件预测区间。下排风由同一海温—风统计关系诊断；灰点线把观测海温代入同一关系，帮助区别海温模拟误差与风关系本身的偏差。所有异常仅在展示时采用1982—2022同月基准。')

    fig,axes=plt.subplots(1,3,figsize=(13.4,4.3),sharey=True,layout='constrained')
    for ax,sy in zip(axes,EVENTS):
        for oy in EVENTS:
            f=main.loc[main.sst_year.eq(sy)&main.ocean_year.eq(oy)]
            ax.plot(f.month,f.nino34_predicted,lw=2,color=COLORS[oy],label=f'{oy} ocean')
        f=main.loc[main.sst_year.eq(sy)&main.ocean_year.eq(sy)]
        ax.plot(f.month,f.nino34_observed,color='.25',lw=1.6,ls='--',label='Observed native event')
        ax.set_title(f'Fixed {sy} SST initial state');time_axis(ax)
    axes[0].set_ylabel('Nino3.4 anomaly (°C)');axes[0].legend(fontsize=8,frameon=False)
    fig.suptitle('8 | Ocean initialization sensitivity under common parameters\nExploratory within-model results: native event reproduction is inadequate',fontsize=14)
    save(fig,'Fig08_ocean_initialization_trajectories',
         '图8：每个面板固定一个案例的1月海温强度和东西型态，分别换入1997、2015、2023的海洋初态。海洋初态包括三区WWV26和三区50—150m温度；所有组合使用相同参数与风诊断关系。模型初态替换的效果仅是内部敏感性；由于原配模拟不足，不能解释为真实事件的因果贡献。')

    eff=pd.read_csv(OUT/'swap_seasonal_effects.csv')
    ef=eff.loc[eff.model.eq(PRIMARY)&~eff.detrend&eff.swap.eq('direct')]
    ci=pd.read_csv(OUT/'bootstrap_OND_swap_effect.csv').set_index(['sst_year','ocean_year'])
    support=pd.read_csv(OUT/'initial_state_support.csv')
    support=support.loc[support.swap.eq('direct')].set_index(['sst_year','ocean_year'])
    fig,axes=plt.subplots(1,2,figsize=(12.5,5.7),layout='constrained')
    for j,(column,title) in enumerate([('nino34_OND_C','Simulated OND Nino3.4'),('nino34_OND_C_change_from_native','Change relative to native ocean')]):
        a=ef.pivot(index='sst_year',columns='ocean_year',values=column).loc[list(EVENTS),list(EVENTS)]
        im=axes[j].imshow(a,cmap='RdBu_r',vmin=-1.2 if j==0 else -.7,vmax=1.2 if j==0 else .7)
        for r,sy in enumerate(EVENTS):
            for c,oy in enumerate(EVENTS):
                val=a.loc[sy,oy];flag=' †' if support.loc[(sy,oy),'outside_reference_95pct'] else ''
                s=f'{val:+.2f}{flag}'
                if j==1 and sy!=oy:s+=f'\n[{ci.loc[(sy,oy),"lo"]:+.2f}, {ci.loc[(sy,oy),"hi"]:+.2f}]'
                axes[j].text(c,r,s,ha='center',va='center',fontsize=10,color='white' if abs(val)>(.8 if j==0 else .5) else '#151b22')
        axes[j].set_xticks(range(3),EVENTS);axes[j].set_yticks(range(3),EVENTS)
        axes[j].set_xlabel('Ocean initial state');axes[j].set_ylabel('Fixed SST initial state');axes[j].set_title(title)
        fig.colorbar(im,ax=axes[j],shrink=.68,label='°C')
    fig.suptitle('9 | January initial-state exchange matrix\nBrackets: paired 95% parameter range; † outside January statistical support',fontsize=14)
    save(fig,'Fig09_initialization_matrix',
         '图9：左为3×3组合的10—12月平均Niño3.4距平，右为相对同一行原配海洋初态的变化，括号为参数重采样95%区间。†表示该组合超出参考年份1月联合状态的留一年距离95%范围；这只是统计支持度，不是物理可行性的充分检验。线性模型规定海洋替换差值对海温行初态呈可加性，九个格点不代表九个独立的非线性反馈检验。')

    selection=pd.read_csv(OUT/'model_selection.csv')
    fig,axes=plt.subplots(1,2,figsize=(13.8,5.5),layout='constrained',gridspec_kw={'width_ratios':[1.2,1]})
    names=list(MODELS);ys=np.arange(len(names))
    for trend,color,offset,label in [(False,'#246b9b',-.1,'Monthly means'),(True,'#ba7826',.1,'Monthly trend removed')]:
        vals=[];scores=[];ses=[]
        for name in names:
            row=eff.loc[eff.model.eq(name)&eff.detrend.eq(trend)&eff.swap.eq('direct')&eff.sst_year.eq(2023)&eff.ocean_year.eq(1997)].iloc[0]
            vals.append(row.nino34_OND_C_change_from_native)
            sel=selection.loc[selection.model.eq(name)&selection.detrend.eq(trend)].iloc[0]
            scores.append(sel.cv_score);ses.append(sel.cv_se)
        axes[0].scatter(vals,ys+offset,color=color,label=label,s=45,zorder=3)
        axes[1].errorbar(scores,ys+offset,xerr=ses,fmt='o',color=color,ms=5,capsize=3,label=label)
    bound=ci.loc[(2023,1997)]
    value=ef.loc[ef.sst_year.eq(2023)&ef.ocean_year.eq(1997),'nino34_OND_C_change_from_native'].iloc[0]
    axes[0].plot([bound.lo,bound.hi],[2.9,2.9],color='#246b9b',lw=1.4)
    adjusted=eff.loc[eff.model.eq(PRIMARY)&~eff.detrend&eff.swap.eq('conditioned')&eff.sst_year.eq(2023)&eff.ocean_year.eq(1997)].iloc[0]
    axes[0].scatter([adjusted.nino34_OND_C_change_from_native],[5],marker='D',color='#6d5592',label='SST-conditioned swap (8)',s=45)
    axes[0].set_yticks(range(6),[LABELS[x] for x in names]+['Conditioned ocean departure'])
    axes[1].set_yticks(ys,[LABELS[x] for x in names])
    for a in axes:a.invert_yaxis();a.grid(axis='x',alpha=.2)
    axes[0].axvline(0,color='.55',lw=.8);axes[0].set_xlabel('OND response: 1997 ocean minus native 2023 ocean (°C)')
    axes[0].set_title('Fixed 2023 SST; donor effect is model-sensitive')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,fontsize=8.5,frameon=False)
    axes[1].set_xlabel('Internal tuning score: normalized SST MSE ± fold SE')
    axes[1].set_title('Non-target years, guarded time blocks')
    fig.suptitle('10 | State choice and background treatment change the inferred response',fontsize=14)
    save(fig,'Fig10_model_and_background_sensitivity',
         '图10：左为固定2023海温、换入1997海洋初态的年底海温变化，比较状态数与趋势处理。8状态主模型的横线为参数重采样95%区间；紫菱形另外调整海洋相对给定海温的条件偏差，它改变了替换定义。右为五个连续时间块、两侧一年缓冲的调参得分及跨折标准误；用于选择正则化强度，不能当作嵌套独立验证或模型差异显著性。')

    dec=pd.read_csv(OUT/'within_model_initial_state_decomposition.csv').set_index(['sst_year','ocean_year'])
    bb=pd.read_csv(OUT/'bootstrap_initial_state_decomposition.csv')
    bb=bb.loc[bb.sst_year.eq(2023)&bb.ocean_year.eq(1997)]
    keys=['total_volume_at_fixed_fraction','volume_redistribution_at_fixed_total','subsurface_temperature','all_ocean']
    labels=['Total WWV change\n(fixed climatological fractions)','W/C/E redistribution\n(zero total-volume change)','Subsurface temperature\n(W/C/E, 50–150 m)','Combined ocean-state change']
    vals=dec.loc[(2023,1997),keys].to_numpy(float)
    fig,ax=plt.subplots(figsize=(9.3,4.7),layout='constrained')
    for k,key in enumerate(keys):
        low,high=bb[key].quantile([.025,.975]);ax.plot([low,high],[k,k],color='#246b9b' if k<3 else '.2',lw=2)
        ax.scatter(vals[k],k,color='#246b9b' if k<3 else '.2',s=45,zorder=3)
        ax.text(high+.025,k,f'{vals[k]:+.2f}°C',va='center',fontsize=9)
    ax.axvline(0,color='.6',lw=.8);ax.set_yticks(range(4),labels);ax.invert_yaxis()
    ax.set_xlim(float(bb[keys].quantile(.025).min())-.04,float(bb[keys].quantile(.975).max())+.12)
    ax.set_xlabel('OND Nino3.4 change (°C); fixed 2023 SST, 1997 ocean donor')
    ax.grid(axis='x',alpha=.2)
    ax.set_title('11 | Algebraic contributions within the SAME 8-state model\nParameter ranges; components are correlated and are not physical budget terms',fontsize=13)
    save(fig,'Fig11_within_model_state_decomposition',
         '图11：在同一8状态模型内，把2023→1997海洋初态差分解为总WWV变化、固定总量的东西再分配、次表层温度变化。总量项按1982—2022年1月三区气候态WWV份额分配，其余体积差为零总量的配置项；三项严格相加为整体替换差值。横线是配对参数区间。分解依赖所选坐标与份额，不是独立物理过程、输送收支或因果归因。')

    timing=pd.read_csv(OUT/'native_forecast_error_timing.csv')
    fig,axes=plt.subplots(1,3,figsize=(13.8,4.7),sharey=True,layout='constrained')
    for ax,event in zip(axes,EVENTS):
        f=timing.loc[timing.event.eq(event)].pivot(index='source_month',columns='state_group',values='OND_nino34_error_contribution_C')
        ax.bar(f.index-.18,f.sst,width=.35,color='#c85449',label='SST-equation residuals')
        ax.bar(f.index+.18,f.ocean,width=.35,color='#246b9b',label='Ocean-equation residuals')
        ax.axhline(0,color='.5',lw=.8);ax.set_xticks([2,4,6,8,10,12],['Feb','Apr','Jun','Aug','Oct','Dec'])
        ax.set_title(f'{event}: total missing OND = {f.to_numpy().sum():.2f}°C')
        ax.set_xlabel('Month when the one-step error enters');ax.grid(axis='y',alpha=.15)
    axes[0].set_ylabel('Propagated contribution to OND SST error (°C)');axes[0].legend(fontsize=8,frameon=False)
    fig.suptitle('12 | When does the free model lose the observed growth?\nRetrospective error identity only; future residuals are NOT used in forecasts or swaps',fontsize=14)
    save(fig,'Fig12_native_error_timing',
         '图12：用观测状态计算每一步统计模型残差，再通过固定传播矩阵追踪其对10—12月海温误差的贡献。按海温方程与海洋方程分组，所有月份贡献之和严格等于观测减自由模拟的年底差值。这是定位模型失配的回溯恒等式；残差不等于已识别的西风爆发、外强迫或热收支项，也没有回填到自由模拟或替换试验。')


def report():
    native=pd.read_csv(OUT/'native_initialization_skill.csv')
    n=native.loc[native.model.eq(PRIMARY)&~native.detrend].copy()
    effects=pd.read_csv(OUT/'swap_seasonal_effects.csv')
    effect=effects.loc[effects.model.eq(PRIMARY)&~effects.detrend&effects.swap.eq('direct')&effects.sst_year.eq(2023)&effects.ocean_year.eq(1997)].iloc[0]
    ci=pd.read_csv(OUT/'bootstrap_OND_swap_effect.csv').set_index(['sst_year','ocean_year']).loc[(2023,1997)]
    timing=pd.read_csv(OUT/'native_forecast_error_timing.csv')
    tops=[]
    for event in EVENTS:
        f=timing.loc[timing.event.eq(event)].groupby('source_month').OND_nino34_error_contribution_C.sum().sort_values(ascending=False)
        tops.append(f'{event}年最大的三个正贡献月份为'+ '、'.join(f'{int(m)}月（{v:+.2f}°C）' for m,v in f.iloc[:3].items()))
    nt=n[['event','observed_OND_C','predicted_OND_C','feb_dec_rmse_C','persistence_rmse_C']].copy()
    nt.columns=['年份','观测OND海温','模拟OND海温','2—12月RMSE','持续性基准RMSE']
    nt['年份']=nt['年份'].astype(int)
    selection=pd.read_csv(OUT/'model_selection.csv')
    support=pd.read_csv(OUT/'initial_state_support.csv')
    flagged=support.loc[support.swap.eq('direct')&support.outside_reference_95pct]
    paragraphs=[
    ('本轮结论',[
    '已完成统一参数的三个原配初态检验、3×3海洋初态替换、状态维数和背景趋势敏感性，以及参数重采样。主模型保留海温强度/型态、三区WWV26和三区50—150m温度。',
    '原配试验未能重现三个强事件的完整增暖，尤其2015年模拟未能重现从1月到年底的增强。因此目前不能用初态替换结果支持“海洋初态差异已经解释海气反馈差异”，也不能由模型失败反推海洋初态没有作用。',
    f'在8状态主模型中，固定2023年海温、将海洋换成1997年初态，OND Niño3.4变化为{effect.nino34_OND_C_change_from_native:+.3f}°C；条件于这套模型的95%参数区间为[{ci.lo:+.3f}, {ci.hi:+.3f}]°C。区间跨零，且状态选择/趋势处理改变效应大小和符号。不能声称“换成1997海洋，2023就会发展得更强”。']),
    ('模型与训练约定',[
    '这是受充电振子和季节性线性逆模型启发的经验动力试验，采用直接估计的月传播矩阵，不是Jin1997方程的逐式复现，也不是从完整温度收支独立推导的物理模型。保存的参数采用行向量约定：z(t+1)=z(t)[I+C0+Cc cos(2πm/12)+Cs sin(2πm/12)]+b(m)，其中m为零起始的日历月份。所有组合共享同一套矩阵和季节项。',
    '主状态为[Niño3.4, Niño3−Niño4, WWV26西/中/东, 温度50—150m西/中/东]，共8维。WWV26沿用Chen等2015的方法，定义为海面至瞬时σθ=26等密度面的水体体积；不是热含量，也不是20°C等温面深度。海洋三区仍为9°S—9°N，120°E—180°、180°—140°W、140°W—80°W。温度使用上阶段相同的纬向剖面平均和部分层厚权重，不把它改称OHC。另比较2维海温、3维总WWV、5维三区WWV，以及增加西部150—300m温度的9维模型。',
    '原始资料沿用OISST、SODA3.15.2和ERA5。从1982—2024中排除1996—1998、2014—2016、2022—2024，共34年、408个月、405对连续月转移；断开的年份不拼接。季节均值、趋势和标准化尺度都在各训练样本内估计。1982—2022共同气候态只用于最终图表展示，与训练预处理区分。',
    '每种状态方案均在五个连续时间块中选正则化强度，验证块两侧再排除一年，评分只看1月起报后2—12月的两类海温标准化误差。这里的交叉验证得分用于调参，不是嵌套独立技巧估计；三个目标事件没有参与调参。对1997的拟合使用了其后的非目标年份，故这是回溯机制试验，不是历史实时预报。',
    '1月之后不再输入任何观测状态、未来风或事件特定噪声。主试验仅使用训练季节均值；趋势敏感性由训练期逐月趋势去除后拟合，仍交换绝对海洋初值，并按接收年份的背景初始化和还原。各方案内参数统一，不能跨方案把差值理解为单一物理贡献。',
    '风是由共同的逐月海温—风关系诊断出来的，既不是独立风状态，也不是额外独立证据。海洋对海温的作用通过经验传播矩阵表达；本轮没有识别新的风驱/温跃层物理系数。']),
    ('先检查原配初态',[
    '下表单位均为°C。持续性基准保留1月相对于训练背景的异常，随相同季节背景演变。主模型1997和2023优于这一基准，但2015更差；三个案例的OND振幅均明显偏低，2015的事件排序也没有重现。模型的逐年稳定性、数值一致性与这些物理/事件适用性是不同检查。',
    '图7下排也提示，模拟风看起来更接近某个事件，不一定代表正确机制；偏低的模拟海温可能抵消风关系的偏差，必须同时对照灰色的“观测海温代入风关系”。参数区间未覆盖全部未解析扰动，不能据此作事件置信判断。']),
    ('替换结果及适用边界',[
    '每行固定来自该案例的两个1月海温指标，每列换入该案例的全部六个海洋指标，对角线为原配。图8—9保留所有九种组合，作为模型内部敏感性结果。在线性、共同参数的前提下，同一对海洋初态造成的差值必然不依赖海温行初态，故该设计不能检验状态依赖的非线性反馈门槛。',
    '只保留总WWV时，2023换入1997海洋的年底效应约+0.25°C；保留三区储量后主均值方案约+0.08°C；再加三区次表层温度后约−0.07°C；加入西部深层温度约−0.27°C。不同模型都重新估计参数，因此这些模型间差异本身不能直接当作某个过程的贡献。图11另给同一模型内严格可加的坐标分解，但仍不是物理收支。',
    f'直接交换中，{len(flagged)}个组合超出参考1月状态的经验支持范围：2015海温配2023海洋。另做“固定给定海温的条件均值，只替换海洋偏差”的敏感性，改变了初态定义，也改变了响应。所有组合体积均为正；统计支持和正体积只是必要检查，尚未构造/验证三维温盐流场的动力和密度一致性。']),
    ('模型从何时开始漏掉增暖',[
    '固定已拟合参数，逐月把观测状态与模型一步推进比较，再将残差传播到OND。该分解精确加总为观测与自由模拟之差，目的在于定位误差产生时段；残差只称为“模型未解释的演变”，不命名为外强迫或某个物理机制。',
    '；'.join(tops)+'。这里的月份是残差进入模型的月份，其影响经过后续传播，不是当月实际海温增量本身。',
    '下一步应先围绕这些时段检查海温增暖与西风变化的对应，并利用现有温度/输送诊断判断遗漏状态或过程。若再补对流诊断，应针对这些具体失配阶段。当前不应通过给每个事件换参数来“修好”原配模拟后再宣称初态解释成功。'])]
    references=[
    ('Chen, Sui, Tseng & Huang (2015), Journal of Climate','https://doi.org/10.1175/JCLI-D-14-00134.1','WWV26的储备定义来源；当前SODA3资料、三区状态与初态模型属于本项目扩展，不继承原文的机制结论。'),
    ('Jin (1997), An Equatorial Ocean Recharge Paradigm for ENSO. Part I','https://journals.ametsoc.org/view/journals/atsc/54/7/1520-0469_1997_054_0811_aeorpf_2.0.co_2.xml','为海温—海洋储备耦合与海洋记忆提供概念依据；本试验的状态和估计器为另行定义。'),
    ('Shin et al. (2021), Impact of Annual Cycle on ENSO Variability and Predictability','https://doi.org/10.1175/JCLI-D-20-0291.1','支持在经验动力模型中显式考虑季节变化，并把海洋状态与海温联合建模；本文使用SSH，当前试验使用WWV26和温度指标，不继承其预报技巧。'),
    ('Lien et al. (2025), On cyclostationary linear inverse models','https://www.frontiersin.org/journals/complex-systems/articles/10.3389/fcpxs.2025.1563687/full','区分月区间传播与连续时间瞬时动力的估计问题；本试验只声明离散月传播，不将其系数直接解释为瞬时物理反馈。')]
    body=[];plain=['海洋初态替换试验：结果与适用边界','研究阶段；2026-10-14']
    for title,paras in paragraphs:
        body.append(f'<h2>{escape(title)}</h2>');plain.extend(['',title,'',*paras])
        body.extend(f'<p>{escape(p)}</p>' for p in paras)
        if title=='先检查原配初态':body.append(nt.to_html(index=False,float_format=lambda x:f'{x:.3f}',border=0));plain.append(nt.to_string(index=False,float_format=lambda x:f'{x:.3f}'))
    for stem,caption in FIGURES:
        body.append(f'<figure><a href="{stem}.png"><img src="{stem}.png" alt="{escape(caption)}"></a><figcaption>{escape(caption)} <a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></figcaption></figure>')
    body.append('<h2>理论依据与数据交付</h2>')
    for title,url,why in references:body.append(f'<p><a href="{url}">{title}</a>：{why}</p>');plain.append(f'{title}\n{url}\n{why}')
    for fn,title in [('native_initialization_skill.csv','全部原配模型检验'),('swap_seasonal_effects.csv','全部初态替换效应'),('initial_state_support.csv','初态支持范围'),('native_forecast_error_timing.csv','模型误差进入时段'),('fitted_models.json','参数与训练索引'),('validation_results.json','数值与排除检查'),('methods_and_reproduction.txt','英文方法与复现说明')]:body.append(f'<p><a href="{fn}">{title}</a></p>')
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>海洋初态替换试验</title><style>body{font:17px/1.8 system-ui,-apple-system,"PingFang SC",sans-serif;max-width:1120px;margin:40px auto;padding:0 28px;color:#202b36;background:#fbfcfd}h1{font-size:30px}h2{font-size:22px;margin-top:36px;color:#215b76}figure{margin:38px 0;background:white;padding:16px;border:1px solid #dce5eb;border-radius:10px}img{width:100%;height:auto}figcaption{font-size:14px;color:#465965}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:10px;border-bottom:1px solid #d9e1e7;text-align:right}a{color:#176b91}header p{color:#556b7b}.notice{background:#eef4f8;border-left:4px solid #397d9d;padding:15px 20px}</style><header><h1>海洋初态替换试验：结果与适用边界</h1><p>1997 · 2015 · 2023｜统一参数｜三个案例均不参与训练</p></header><div class="notice">已完成首轮试验。原配模拟尚不能重现完整事件增长，因此替换结果仅用于模型内部敏感性，不作为已成立的因果归因。</div>'''+''.join(body)+'</html>'
    (OUT/'海洋初态替换试验_结果与适用边界.html').write_text(html,encoding='utf-8')
    (OUT/'海洋初态替换试验_中文结果.txt').write_text('\n\n'.join(plain+[c for _,c in FIGURES]),encoding='utf-8')
    technical='''Three-event initial-state experiment, 2026-10-14

Sources: audited stage-one OISST, ERA5 and SODA3.15.2 indices/profiles.
Primary state: Nino3.4, Nino3-Nino4, west/central/east WWV26 (1e14 m3),
and west/central/east 50-150 m profile-mean potential temperatures (degC).
Ocean boxes: 9S-9N, 120E-180, 180-140W, 140W-80W.
WWV26 is volume from the surface to instantaneous sigma-theta=26, following
the definition in Chen et al. (2015), doi:10.1175/JCLI-D-14-00134.1.
This is NOT a reproduction of a published estimator or a closed heat budget.

Fitting: affine monthly linear tendency regression with an annual sine/cosine
operator, ridge-regularized tendency coefficients and effectively unpenalized
harmonic intercepts. Standardization and calendar-month means/trends are learned
within each training set. No temporal interpolation, no gap stitching.
Saved matrices use row-vector convention: z_next = z @ A_month + b_month.
1982-2024 except 1996-1998, 2014-2016, 2022-2024: 408 months and 405 pairs.
Five contiguous calendar blocks with +/-1-year guards select ridge strength from
the predefined grid using Jan-start Feb-Dec normalized SST errors. Internal CV
scores are tuning scores, not nested estimates or significance tests. Target
events are untouched by tuning, but later non-target years are used, so this is
retrospective analysis, not a past-only operational forecast.

All row/column combinations share coefficients, scaling and background treatment.
Only the initial ocean entries are exchanged. The detrended sensitivity exchanges
absolute donor values into the recipient-year trend background. Future observed
states/winds/noise are NOT supplied to free forecasts or swaps. Wind is diagnosed
with one training-only monthly SST relationship, not independently prognosed.

300 paired two-year-block parameter resamples reestimate preprocessing and model
coefficients at fixed ridge/state choice. Intervals exclude innovation, data-source
and model-form uncertainty. Unstable draws are retained and counted.
January statistical support uses leave-one-year-out Ledoit-Wolf distances and a
descriptive 95th-percentile cutoff. Positive volumes are checked; complete balanced
3D temperature/salinity/velocity initializations are NOT constructed. The
conditioned-swap sensitivity exchanges ocean deviations from a regularized January
ocean-given-SST relationship and therefore changes the intervention definition.

Linear direct-swap effects must be additive across SST rows. An exact response
kernel decomposes volume change into a fixed-climatological-fraction total-volume
component and zero-sum redistribution, plus temperature changes. This is a
coordinate-dependent algebraic split, NOT independent physical pathway attribution.
Native one-step residuals are separately propagated to locate free forecast errors;
this is a retrospective identity, NOT a new forecast or identified forcing.

Interpretation: native runs underestimate event growth, especially 2015. The
1997-for-2023 ocean substitution is not a robust warming effect across state and
background choices. Numerical checks and periodic stability do not establish
physical adequacy. No claim that ocean initial states are unimportant follows.

Reproduce from project root using /opt/anaconda3/bin/python:
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 \\
  /opt/anaconda3/bin/python scripts/experiment_three_event_initial_states.py --bootstrap 300
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 \\
  /opt/anaconda3/bin/python scripts/plot_report_three_event_initial_states.py
OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python scripts/validate_three_event_initial_states.py

Use --reuse-models only to regenerate diagnostics from saved fits. Stage-one data,
the historical RO/D20 forecasts and earlier results are not overwritten.
'''
    (OUT/'methods_and_reproduction.txt').write_text(technical,encoding='utf-8')
    (OUT/'figure_captions.json').write_text(json.dumps(FIGURES,ensure_ascii=False,indent=2),encoding='utf-8')
    print(nt.to_string(index=False,float_format=lambda x:f'{x:.3f}'))
    print('\n'.join(tops))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report-only',action='store_true');args=parser.parse_args()
    if args.report_only:FIGURES.extend(json.loads((OUT/'figure_captions.json').read_text()))
    else:figures()
    report();print('Figures and report complete',OUT,flush=True)
