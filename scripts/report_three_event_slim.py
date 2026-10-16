"""Scientific figures, diagnostic error timing, and report for segmented sLIM."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/maryland_three_events_mpl')
from pathlib import Path
import json,hashlib,html,platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from analyze_three_event_slim import ROOT,OUT,EVENTS,STATES,VOLUME
import three_event_segmented_slim as slim

PRIMARY='three_wwv_detrend_perturb2'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none',
                     'figure.dpi':120,'savefig.dpi':220})
BLUE='#286b9d';ORANGE='#c57b22';GREEN='#458774';BLACK='#242e38'
FIGS=[]


def save(fig,stem,caption):
    for ext in ('png','pdf','svg'):
        fig.savefig(OUT/f'{stem}.{ext}',bbox_inches='tight',facecolor='white')
    plt.close(fig);FIGS.append((stem,caption))


def timeaxis(ax):
    ax.set_xticks([1,4,7,10,12],['Jan','Apr','Jul','Oct','Dec'])
    ax.set_xlim(1,12);ax.axhline(0,color='.7',lw=.7);ax.grid(axis='y',alpha=.15)


def error_timing(fits,forecasts):
    model=fits[PRIMARY]['model']
    for k in ('scale','coef'):model[k]=np.array(model[k])
    cols=model['columns'];one={m:slim.propagators(model,m,1)[1] for m in range(1,13)}
    rows=[];qa={}
    for year in EVENTS:
        z=forecasts[(forecasts.key==PRIMARY)&(forecasts.year==year)]
        obs=z.pivot(index='month',columns='variable',values='observed_model')[cols].to_numpy()
        fc=z.pivot(index='month',columns='variable',values='predicted_model')[cols].to_numpy()
        total=0.
        for i in range(1,12):
            residual=obs[i]-one[i]@obs[i-1]
            influence=np.zeros(len(cols))
            for target in (9,10,11):
                if i>target:continue
                propagator=np.eye(len(cols))
                for origin in range(i,target):propagator=one[origin+1]@propagator
                influence+=propagator[0]*residual/3
            total+=influence.sum()
            for j,col in enumerate(cols):
                rows.append(dict(year=year,target_month=i+1,variable=col,residual=residual[j],
                                 contribution_to_ond_sst=influence[j]))
        error=float((obs[9:,0]-fc[9:,0]).mean())
        qa[str(year)]=dict(ond_observed_minus_free=error,residual_sum=total,closure_error=abs(error-total))
        assert abs(error-total)<1e-8
    r=pd.DataFrame(rows);r.to_csv(OUT/'native_error_timing_by_state.csv',index=False)
    monthly=r.groupby(['year','target_month']).contribution_to_ond_sst.sum().reset_index()
    monthly.to_csv(OUT/'native_error_timing.csv',index=False)
    (OUT/'native_error_identity_QA.json').write_text(json.dumps(qa,indent=2))
    return monthly


def figures(f,s,d,boot,coef,bcoef,timing):
    p=s[s.key.eq(PRIMARY)].set_index('year')
    fig,axes=plt.subplots(1,3,figsize=(14,5),sharey=True)
    fig.subplots_adjust(top=.78,bottom=.18,wspace=.12)
    for j,(ax,year) in enumerate(zip(axes,EVENTS)):
        q=f[(f.key==PRIMARY)&(f.year==year)&(f.variable=='nino34')]
        spread=boot[boot.year.eq(year)].groupby('month').sst.quantile([.025,.975]).unstack()
        ax.fill_between(spread.index,spread[.025],spread[.975],color=BLUE,alpha=.15)
        ax.plot(q.month,q.observed,color=BLACK,lw=2.5,marker='o',ms=3)
        for key,c,ls in [('bridge_d20_detrend_perturb2',GREEN,':'),('total_wwv_detrend_perturb2',ORANGE,'--'),
                         (PRIMARY,BLUE,'-'),('three_wwv_detrend_exact',BLUE,'-.')]:
            z=f[(f.key==key)&(f.year==year)&(f.variable=='nino34')]
            ax.plot(z.month,z.predicted,color=c,ls=ls,lw=1.9)
        ax.set_title(f'({chr(97+j)}) {year}',loc='left')
        ax.text(.04,.96,f'OND: {p.loc[year,"ond_pred"]:.2f} / {p.loc[year,"ond_obs"]:.2f} °C\nmodel / observed',
                transform=ax.transAxes,va='top',fontsize=9)
        timeaxis(ax)
    axes[0].set_ylabel('Niño3.4 anomaly (°C)');axes[0].set_ylim(-1.2,3.2)
    fig.suptitle('January initial states do not reproduce the observed late-year warming',y=.98,fontsize=15)
    handles=[Line2D([],[],color=BLACK,lw=2.5,label='OISST observed'),Line2D([],[],color=GREEN,ls=':',label='T + D20'),
             Line2D([],[],color=ORANGE,ls='--',label='T + total WWV26'),Line2D([],[],color=BLUE,label='T + W/C/E WWV26'),
             Line2D([],[],color=BLUE,ls='-.',label='W/C/E: exact solver'),Patch(color=BLUE,alpha=.15,label='Parameter-weight spread')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.92),ncol=3,frameon=False,fontsize=9)
    fig.text(.5,.04,'1982–2022 monthly display climatology; target events excluded from fitting; no forcing after January.',ha='center',fontsize=9)
    save(fig,'Fig13_slim_native_sst','原配海温自由模拟。主模型保留三区WWV26。阴影为200次两年块正权重参数敏感性的2.5—97.5百分位，不含发展期随机扰动，不是完整预测区间。所有主图海温均为OISST；D20对照在这里也换为OISST，ERSST旧基准另列表。')

    fig,axes=plt.subplots(3,3,figsize=(13.4,9.5),sharex=True,sharey=True,layout='constrained')
    z=f[f.key.eq(PRIMARY)&f.variable.isin(VOLUME)]
    low=float(z[['predicted','observed']].min().min());high=float(z[['predicted','observed']].max().max())
    for i,(col,label) in enumerate(zip(VOLUME,['West','Central','East'])):
        for j,year in enumerate(EVENTS):
            ax=axes[i,j];q=z[(z.year==year)&(z.variable==col)]
            ax.plot(q.month,q.observed,color=BLACK,lw=2.3,marker='o',ms=2.8)
            ax.plot(q.month,q.predicted,color=BLUE,lw=2)
            ax.set_title(f'({chr(97+i*3+j)}) {label} | {year}',loc='left',fontsize=11)
            if j==0:ax.set_ylabel('WWV26 anomaly ($10^{14}$ m$^3$)')
            timeaxis(ax);ax.set_ylim(low-.3,high+.3)
    fig.suptitle('The same four-state model also misses parts of the ocean evolution\nBlack: SODA3 diagnosis; blue: free sLIM; 1982–2022 monthly display climatology',fontsize=14)
    save(fig,'Fig14_slim_native_wwv','与海温同一原配模拟的三区WWV26。各面板使用共同体积单位和纵轴；黑线为SODA3诊断，并非直接观测。WWV26为瞬时σθ=26面以上体积，区域统一9°S—9°N。')

    fig,axes=plt.subplots(2,2,figsize=(12.5,8),sharex=True,layout='constrained')
    volume_ranges=[]
    for j,(ax,col,title) in enumerate(zip(axes.flat,STATES['three_wwv'],['SST self-coefficient','Western volume → SST','Central volume → SST','Eastern volume → SST'])):
        q=coef[(coef.key==PRIMARY)&(coef.predictor==col)]
        ex=coef[(coef.key=='three_wwv_detrend_exact')&(coef.predictor==col)]
        spread=bcoef[bcoef.predictor.eq(col)].groupby('month').value.quantile([.025,.975]).unstack()
        ax.fill_between(spread.index,spread[.025],spread[.975],color=BLUE,alpha=.15)
        ax.plot(q.month,q.coefficient_to_sst_per_month,color=BLUE,lw=2)
        ax.plot(ex.month,ex.coefficient_to_sst_per_month,color=BLACK,ls='--',lw=1.5)
        ax.set_title(f'({chr(97+j)}) {title}',loc='left')
        ax.set_ylabel('month$^{-1}$' if j==0 else '°C / ($10^{14}$ m$^3$ month)')
        timeaxis(ax)
        if j>0:volume_ranges.extend([spread[.025].min(),spread[.975].max(),ex.coefficient_to_sst_per_month.min(),ex.coefficient_to_sst_per_month.max()])
    extent=max(abs(np.array(volume_ranges)))*1.1
    for ax in list(axes.flat)[1:]:ax.set_ylim(-extent,extent)
    fig.suptitle('Seasonal coefficients are conditional statistical relationships\nBlue: second-order sLIM; dashed: exact moments; shading: parameter-weight spread',fontsize=14)
    save(fig,'Fig15_slim_seasonal_coefficients','四状态模型海温方程的季节系数及估计器敏感性。蓝线为二阶扰动估计，虚线为同一组矩方程的精确求解。这些是给定其他状态后的统计系数，尚不能命名为独立输送过程的物理反馈；不宜把大系数直接解释为强因果作用。')

    names=['legacy_d20','bridge_d20','total_wwv','three_wwv','three_wwv_pattern','thermal_sensitivity']
    labels=['ERSST + D20 (2)','OISST + D20 (2)','T + total WWV (2)','T + W/C/E WWV (4)','+ SST pattern (5)','+ subsurface T (8)']
    fig,axes=plt.subplots(1,3,figsize=(14.2,5.5),sharey=True,sharex=True)
    fig.subplots_adjust(top=.77,bottom=.17,left=.19,wspace=.13)
    for j,(ax,year) in enumerate(zip(axes,EVENTS)):
        for i,name in enumerate(names):
            q=s[(s.model==name)&(s.year==year)]
            ax.plot([q.ond_pred.min(),q.ond_pred.max()],[i,i],color='.68',lw=4)
            value=q[q.detrend&q.method.eq('perturb2')].ond_pred.iloc[0]
            ax.scatter(value,i,c=BLUE if name=='three_wwv' else ORANGE,s=45,zorder=3)
        actual=s[(s.key==PRIMARY)&(s.year==year)].ond_obs.iloc[0]
        ax.axvline(actual,color=BLACK,lw=1.6,ls='--')
        ax.set_title(f'({chr(97+j)}) {year}',loc='left');ax.set_xlabel('OND Niño3.4 anomaly (°C)')
        ax.grid(axis='x',alpha=.15);ax.axvline(0,color='.75',lw=.7);ax.set_xlim(-.6,3.0)
    axes[0].set_yticks(range(len(labels)),labels);axes[0].invert_yaxis()
    fig.suptitle('Changing estimator, background, or state count does not close the SST gap',y=.98,fontsize=14)
    fig.legend(handles=[Line2D([],[],color='.68',lw=4,label='Range: detrend/mean × perturbative/exact'),
                        Line2D([],[],color=ORANGE,marker='o',ls='',label='Detrended perturbative estimate'),
                        Line2D([],[],color=BLACK,ls='--',label='OISST observed')],
               loc='upper center',bbox_to_anchor=(.57,.92),frameon=False,ncol=1,fontsize=9)
    fig.text(.5,.04,'Legacy ERSST observations differ slightly: 2.41 / 2.64 / 1.99 °C for 1997 / 2015 / 2023.',ha='center',fontsize=9)
    save(fig,'Fig16_slim_representation_sensitivity','每条灰线覆盖预先指定的去趋势/不去趋势与扰动/精确求解四种设置，圆点为主预处理和估计器；并非置信区间。全部状态方案仍低估年底海温。旧ERSST基准与OISST真值略有不同，分别评分并保留在表中。')

    fig,axes=plt.subplots(1,3,figsize=(13.5,4.5),sharey=True,layout='constrained')
    for ax,year in zip(axes,EVENTS):
        q=timing[timing.year.eq(year)]
        ax.bar(q.target_month,q.contribution_to_ond_sst,color=np.where(q.contribution_to_ond_sst>=0,ORANGE,BLUE))
        timeaxis(ax);ax.set_xlim(1.5,12.5);ax.set_title(str(year),loc='left')
    axes[0].set_ylabel('Contribution to OND SST gap (°C)')
    fig.suptitle('When does the unexplained evolution enter the native trajectory?\nResidual propagation is an accounting identity, not an identified physical forcing',fontsize=14)
    save(fig,'Fig17_slim_error_timing','把每个月原配状态方程的残差传播到OND，按月份加总可严格重建观测与自由模拟之差。月份表示残差进入的目标月。该分解只定位后续诊断时段，不将残差直接称为西风爆发、海表热通量或外强迫。未来残差未喂入自由模拟。')


def reports(f,s,d,boot,timing,qa):
    primary=s[s.key.eq(PRIMARY)].set_index('year')
    audit=d[d.key.eq(PRIMARY)].iloc[0]
    native_table=primary[['january','ond_pred','ond_obs','rmse_feb_dec','persistence_rmse']].rename(columns={
        'january':'1月距平','ond_pred':'OND模拟','ond_obs':'OND观测','rmse_feb_dec':'2—12月RMSE','persistence_rmse':'持续性RMSE'})
    native_table.to_csv(OUT/'primary_result_table.csv')
    ranking=[]
    for year in EVENTS:
        q=timing[timing.year.eq(year)].nlargest(3,'contribution_to_ond_sst')
        ranking.append(f'{year}年：'+ '、'.join(f'{int(v.target_month)}月（{v.contribution_to_ond_sst:+.2f}°C）' for v in q.itertuples()))
    ont=boot[boot.month.ge(10)].groupby(['replicate','year']).sst.mean().groupby('year').quantile([.025,.975]).unstack()
    text=f'''三案例 sLIM 基准与最小空间扩展：当前结果与下一步

本轮确实恢复了项目已有的 Chen & Jin (2021) sLIM 估计器。上一轮直接月传播ridge模型仍单独保留，不能称为sLIM结果。本轮没有重复解释其3×3替换矩阵，也没有在原配不足时新增实际事件归因。

模型层次：
旧基准是ERSST Niño3.4 + GODAS平均D20；资料桥接为OISST Niño3.4 +同一D20；暖水基准为OISST Niño3.4 +总WWV26；最小空间主模型为 x=[T,V_W,V_C,V_E]。它保留全部三区配置，总量是三区之和，不能再作为独立状态重复加入。Niño3−Niño4及三区50—150m温度只作预先指定的复杂度敏感性。本轮没有增加PMM。
dx/dt=L(t)x；L(t)=L0+Lc1 cos(2πt)+Lc2 cos(4πt)+Ls1 sin(2πt)+Ls2 sin(4πt)，t单位为年。无外加随机扰动的积分，只检验给定初态后的确定性演变。海温—风关系未在本轮作为独立动力状态重新拟合，因此结果不能自动代表完整风反馈。

训练为1982—2024剔除1996—1998、2014—2016、2022—2024后的34年408个月。分别在1982—1995、1999—2013、2017—2021三段内部插值、求导、计算滞后矩，再按有效点数汇总。不能跨缺口插值，72步/年的插值点也不是独立观测。气候态、趋势、尺度全部在训练样本中估计；主方案沿用旧sLIM的先同月去均值、后单条线性去趋势顺序。展示恢复为1982—2022同月距平。所有案例用同一参数；输入为已知整月1月均值，1月以后没有观测风或海洋强迫。训练含非目标事件的较晚年份，所以是目标排除的回溯研究，非当年实时预报。

四状态主模型结果（海温单位°C）：
{native_table.to_string(float_format=lambda x:f'{x:.3f}')}

1997/2023能模拟从冷到暖的方向，却远低于实际幅度；2015从1月到OND反而减弱，其RMSE劣于1月距平持续性。把总WWV换成三区WWV，在1997/2023没有一致改善。不能宣称“空间配置已经解释事件差异”。精确矩求解、仅年周期、不去趋势、增加SST型态和次表层温度，均未恢复三个案例的年末强增暖。负结果不证明海洋初态没有作用，也不否定sLIM用于季节系数估计；它说明当前初态—线性确定性系统不足以独立解释这些极端事件的具体演变。

估计器和数值诊断：
连续样本上，新分段实现与原有代码的系数最大差为{qa['continuous_equivalence_perturb2']:.2g}；排除年份任意扰动后系数变化为{qa['excluded_value_coefficient_change']:.1f}。单位变换、完整配置坐标变换、积分步长收敛均通过。主模型滞后协方差条件数{audit.lag_cov_condition:.1f}，完整矩系统条件数{audit.full_moment_condition:.1f}，全年传播谱半径{audit.annual_radius:.3f}。这些数值检查不等于物理机制已验证。
二阶修正/一阶季节项的范数比约{audit.second_first_norm_ratio:.2f}，扰动估计对完整矩方程的相对残差约{audit.relative_moment_residual:.2f}；精确解仍显著改变部分季节系数与预报。因此不能把本轮季节系数当作无误差的过程常数。增加至8状态后，滞后协方差条件数约312，尚未换来原配演变改善。
主模型月残差的1/2/3月海温相关为{audit.residual_ac1:.2f}/{audit.residual_ac2:.2f}/{audit.residual_ac3:.2f}。这只是训练样本内诊断，未证明所有状态的残差为白噪声。
200次两年块正指数权重重新估计预处理与参数，全年谱半径范围{boot.annual_radius.min():.3f}—{boot.annual_radius.max():.3f}。OND海温的2.5—97.5百分位为：
{ont.to_string(float_format=lambda x:f'{x:.3f}')}
此范围是有限样本参数敏感性，不含发展期随机扰动、模式误差或初态观测误差，不能据此声称观测事件概率为零。论文中的随机RO用于长期统计与季节锁相；本轮确定性原配检验承担的是不同问题，不把两者的成功标准混同。

下一步应优先解释原配失配时段，而不是继续按目标结果挑状态或给每个事件换参数。向OND传播后的最大三个净正残差进入月份：
{chr(10).join(ranking)}
这个恒等分解只定位时段，不能据此直接归因为西风爆发。沿用已选路线，先核对这些阶段的海温—西风关系，再结合三区WWV26、垂直温度结构及输送判断哪些过程当前状态没有表达。对流诊断留给海温—风关系仍解释不清的阶段。过程系数分解还需把输送转换为与海温区域、层次一致的温度倾向；PW/Sv不能直接代入°C/月方程。

本阶段完成的是基准、最小空间扩展与适用性检查。四状态可以作为保留三区信息的最简参照，但当前不是已经验证的因果实验平台。初态替换的物理归因保持待检验；上一阶段探索性替换结果保留，不因换用sLIM而自动获得验证。

参考：Chen & Jin (2021), 10.1175/JCLI-D-20-0874.1；Chen & Jin (2022), 10.1029/2021GL097603；Chen et al. (2015), 10.1175/JCLI-D-14-00134.1。
'''
    (OUT/'sLIM基准与空间扩展_结果.txt').write_text(text,encoding='utf-8')
    paragraphs='\n'.join('<p>'+html.escape(p).replace('\n','<br>')+'</p>' for p in text.split('\n\n') if p.strip())
    gallery=''.join(f'<figure><img src="{stem}.png"><figcaption>{html.escape(caption)}</figcaption></figure>' for stem,caption in FIGS)
    refs='<p>理论方法：<a href="https://doi.org/10.1175/JCLI-D-20-0874.1">Chen &amp; Jin 2021</a>；<a href="https://doi.org/10.1029/2021GL097603">Chen &amp; Jin 2022</a>；<a href="https://doi.org/10.1175/JCLI-D-14-00134.1">Chen等2015</a>。</p>'
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>sLIM基准与空间扩展</title><style>
body{max-width:1120px;margin:40px auto;padding:0 28px;font:17px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#243542;background:#f8fafc}
h1{font-size:29px;line-height:1.4}p{white-space:normal}table{border-collapse:collapse;margin:22px 0;width:100%;background:white}th,td{padding:9px;border-bottom:1px solid #d5dce4;text-align:right}th:first-child{text-align:left}
figure{margin:38px 0;background:white;padding:18px;border-radius:10px}img{width:100%;height:auto}figcaption{color:#4a5c6c;font-size:15px}a{color:#226a9d}.callout{padding:20px;border-left:5px solid #c57b22;background:#fff8ec}
</style><h1>已恢复sLIM，但当前初态仍不足以重现三次事件</h1>
<p class="callout">保留西、中、东三区WWV26的四状态模型能够表达空间配置，但明显低估年末海温，尤其未重现2015年的持续增强。下一步应定位未解释过程；目前不能将初态替换解释为已成立的事件归因。</p>'''
    doc+=native_table.round(3).to_html()+gallery+paragraphs+refs+'</html>'
    (OUT/'sLIM基准与空间扩展_结果.html').write_text(doc,encoding='utf-8')
    notes='''REPRODUCTION AND INTERPRETATION
Run from repository root:
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python scripts/analyze_three_event_slim.py
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python scripts/report_three_event_slim.py
MPLCONFIGDIR=/private/tmp/maryland_three_events_mpl OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python scripts/validate_three_event_slim.py

The historical paper_ro_slim.py is unchanged. three_event_segmented_slim.py
pools its identical moment estimator over disconnected chronological segments.
Training excludes all target +/-1 years. This is retrospective, not a real-time
forecast. Monthly means are labeled by month start only for calendar alignment;
initialization uses the complete January monthly mean. Harmonic phase and RK4
use mid-month as in the original implementation. Lag 6 = one month; lag 1 = 1/6
month on the interpolation grid. No independent data are created by interpolation.

WWV26 input is a previously validated SODA3 derived diagnostic; D20 input is
GODAS and its historical CSV column was misleadingly named WWV. This script
renames it d20 and never uses volume_m3 for WWV26. Source domains differ. OISST
and ERSST are scored against their own observations and display climatologies.
The model coefficients operate in years; plotted SST coefficients divide by 12
and rescale to physical coordinates. They are conditional statistical tendencies,
not closed process-budget contributions. No direct SST--wind coupling estimation
is added here. No replacement initial-state causal claim is made.

Parameter sensitivities: 200 deterministic-seed (20261014) draws of positive
Exp(1) weights shared within original chronological two-year blocks. Segments
are not concatenated; interpolation/lag/derivatives use original trajectories.
Climatology/trend/scale are reestimated with these weights. Evaluation moment
weights use the original month bin; boundaries may involve the adjacent original
block, which is retained. There are short terminal blocks at segment ends.
These are weighted-estimating-equation sensitivities, not calibrated predictive
intervals. Innovations, observation error and structural uncertainty are absent.

Native error timing computes e_t = x_obs(t)-Phi(t,t-1)x_obs(t-1) in model
coordinates, propagates each e_t to Oct/Nov/Dec and averages. Its sum exactly
equals observed-minus-free OND SST. The identity does not identify forcing.
Validation confirms excluded values cannot enter coefficients. All numeric QA
addresses implementation, not the scientific sufficiency of the state vector.
'''
    notes+=f'\nRuntime: Python {platform.python_version()}, numpy {np.__version__}, pandas {pd.__version__}, matplotlib {matplotlib.__version__}.\n'
    (OUT/'methods_and_reproduction.txt').write_text(notes,encoding='utf-8')


def main():
    f=pd.read_csv(OUT/'native_forecasts.csv');s=pd.read_csv(OUT/'native_scores.csv')
    d=pd.read_csv(OUT/'fit_diagnostics.csv');boot=pd.read_csv(OUT/'parameter_weight_native_forecasts.csv')
    coef=pd.read_csv(OUT/'seasonal_sst_coefficients.csv');bcoef=pd.read_csv(OUT/'parameter_weight_coefficients.csv')
    fits=json.loads((OUT/'models_and_preprocessing.json').read_text());qa=json.loads((OUT/'numerical_QA.json').read_text())
    timing=error_timing(fits,f)
    figures(f,s,d,boot,coef,bcoef,timing);reports(f,s,d,boot,timing,qa)
    print('Wrote',len(FIGS),'figures and reports to',OUT,flush=True)


if __name__=='__main__':main()
