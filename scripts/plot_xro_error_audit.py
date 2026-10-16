#!/usr/bin/env python3
"""Diagnostic figures; no ranking of preprocessing choices by target event."""
import json
import numpy as np
import pandas as pd
import run_xro_npmm_ablation as exp
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT=exp.OUT/'audit_20261014'
f=pd.read_csv(OUT/'preprocessing_and_data_forecasts.csv',parse_dates=['target'])
s=pd.read_csv(OUT/'preprocessing_and_data_scores.csv')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'pdf.fonttype':42})
colors={'obs':'#202833','full':'#D55E00','no_NPMM':'#2878B5'}
labels={'obs':'Observed','full':'Full XRO','no_NPMM':'Without NPMM (refit)'}
handles=[Line2D([0],[0],lw=2.4,color=colors[k],label=labels[k],ls='--' if k=='no_NPMM' else '-') for k in colors]
cases=['quadratic_all','ORAS5_reference_fit_through_2014']
titles=['Original experiment: ERSSTv5 + PMEL','Reference diagnostic: supplied ORAS5 indices']
units=[r'WWV anomaly ($10^{14}$ m$^3$)','WWV proxy: mean D20 anomaly (m)']
note=('Both fits: January 1980–December 2014; same official XRO core and nonlinear terms; 12-month zero-noise forecasts.\n'
      'LEFT: past-only monthly climatology and quadratic detrending. RIGHT: author-supplied, already preprocessed indices.\n'
      'The ORAS5 preprocessing may use later data: this is an implementation/data diagnostic, not a leakage-free skill comparison.\n'
      'Each panel uses its own anomaly baseline. WWV definitions and units differ; compare trajectories within each panel.')
def save(fig,name):
    for ext in ['png','pdf']:
        fig.savefig(OUT/f'{name}.{ext}',dpi=210,bbox_inches='tight',facecolor='white')
    plt.close(fig)

for month in [1,3,5]:
    g=f[f.month==month]
    fig,axes=plt.subplots(2,2,figsize=(12.5,8.2),sharex=True)
    fig.subplots_adjust(top=.80,bottom=.23,hspace=.35,wspace=.24)
    fig.suptitle(f'2015 XRO audit | {exp.MONTHS[month-1]} initialization',y=.98,fontsize=17)
    fig.legend(handles=handles,ncol=3,loc='upper center',bbox_to_anchor=(.5,.93),frameon=False)
    for col,case in enumerate(cases):
        c=g[g.case==case]
        base=c[c.model=='full'].sort_values('lead')
        for row,var in enumerate(['T','H']):
            ax=axes[row,col]
            for name in colors:
                d=base if name=='obs' else c[c.model==name].sort_values('lead')
                ax.plot(d.lead,d['obs_'+var] if name=='obs' else d[var],color=colors[name],
                        ls='--' if name=='no_NPMM' else '-',lw=2.4,marker='o' if name=='obs' else None,ms=3.5)
            ax.scatter(0,base['obs_'+var].iloc[0],s=95,marker='*',color=colors['obs'],zorder=10)
            ax.axhline(0,color='.55',lw=.7);ax.grid(alpha=.16)
            ax.set(xlim=(-.2,12.2),ylabel='Niño3.4 anomaly (°C)' if row==0 else units[col])
            ax.set_xticks([0,3,6,9,12],[f'{exp.MONTHS[(month-1+k)%12]}\n{2015+(month-1+k)//12}' for k in [0,3,6,9,12]])
            if row==0:
                ax.set_title(titles[col],fontsize=10.5,pad=13)
                ax.set_ylim(-.15,3.6)
                rmse=s[(s.case==case)&(s.month==month)&(s.model=='full')].T_RMSE.iloc[0]
                ax.text(.03,.91,f'Full XRO RMSE: {rmse:.2f} °C',transform=ax.transAxes,fontsize=9,
                        bbox={'facecolor':'white','edgecolor':'none','alpha':.85})
    fig.text(.055,.035,note,fontsize=8.8,color='#4e5660',linespacing=1.55,va='bottom')
    save(fig,f'audit_time_series_init_{month:02d}')

    fig,axes=plt.subplots(1,2,figsize=(12.5,7.4),sharex=True)
    fig.subplots_adjust(top=.80,bottom=.28,wspace=.24)
    fig.suptitle(f'2015 XRO phase-space audit | {exp.MONTHS[month-1]} initialization',y=.98,fontsize=16)
    fig.legend(handles=handles,ncol=3,loc='upper center',bbox_to_anchor=(.5,.93),frameon=False)
    for col,case in enumerate(cases):
        ax=axes[col];c=g[g.case==case];base=c[c.model=='full'].sort_values('lead')
        for name in colors:
            d=base if name=='obs' else c[c.model==name].sort_values('lead')
            x=d.obs_T.to_numpy() if name=='obs' else d['T'].to_numpy()
            y=d.obs_H.to_numpy() if name=='obs' else d['H'].to_numpy()
            ax.plot(x,y,color=colors[name],lw=2.3,marker='o',ms=3.2,ls='--' if name=='no_NPMM' else '-')
            for k in [3,6,9,12]:
                ax.annotate('',xy=(x[k],y[k]),xytext=(x[k-1],y[k-1]),
                            arrowprops={'arrowstyle':'->','color':colors[name],'lw':1.8})
                if name=='obs':
                    ax.annotate(exp.MONTHS[(month-1+k)%12]+(' 2016' if month-1+k>=12 else ''),
                                (x[k],y[k]),xytext=(6,5),textcoords='offset points',fontsize=8.5,color=colors[name])
        ax.scatter(base.obs_T.iloc[0],base.obs_H.iloc[0],s=140,marker='*',color=colors['obs'],zorder=10)
        ax.axhline(0,color='.55',lw=.7);ax.axvline(0,color='.55',lw=.7);ax.grid(alpha=.16)
        ax.set(title=titles[col],xlabel='Niño3.4 anomaly (°C)',ylabel=units[col],xlim=(-.05,3.65))
        ax.margins(y=.20)
    fig.text(.055,.035,'Star: shared initial state within each experiment. Arrows: forward in time.\n'+note,
             fontsize=8.6,color='#4e5660',linespacing=1.55,va='bottom')
    save(fig,f'audit_phase_space_init_{month:02d}')

# Controlled preprocessing sensitivity on one common DISPLAY baseline. Each
# model is trained on its specified residuals, then its removed trend is added
# back to display all forecasts as 1980–2014 monthly climatology anomalies.
raw=pd.read_csv(exp.OUT/'raw_xro_indices_1980_2026.csv',index_col=0,parse_dates=True)
base=exp.anomalies(raw,2015,order=0)
quad=exp.anomalies(raw,2015,order=2)
linear=exp.anomalies(raw,2015,order=1)
mixed=quad.copy();mixed.WWV=linear.WWV
mixclim=quad.copy();mixclim.WWV=base.WWV
transforms={'quadratic_all':quad,'quadratic_SST_linear_H':mixed,'quadratic_SST_climatology_H':mixclim}
styles={'quadratic_all':('Original: quadratic trend for all states','#D55E00','-'),
        'quadratic_SST_linear_H':('Change only H: linear trend','#009E73','--'),
        'quadratic_SST_climatology_H':('Change only H: climatology only','#7b62a3','-.')}
fig,axes=plt.subplots(1,2,figsize=(12.5,6.3))
fig.subplots_adjust(top=.74,bottom=.25,wspace=.25)
fig.suptitle('WWV preprocessing changes the March 2015 forecast',y=.98,fontsize=16)
hh=[Line2D([0],[0],color=colors['obs'],lw=2.4,label='Observed')]
hh.extend(Line2D([0],[0],color=c,ls=ls,lw=2.2,label=label) for label,c,ls in styles.values())
fig.legend(handles=hh,ncol=2,loc='upper center',bbox_to_anchor=(.5,.94),frameon=False,fontsize=9.5)
target=pd.date_range('2015-03',periods=13,freq='MS')
for ax,var,outvar in zip(axes,['Nino34','WWV'],['T','H']):
    ax.plot(np.arange(13),base.reindex(target)[var],color=colors['obs'],lw=2.4,marker='o',ms=3.5)
    for case,(label,color,ls) in styles.items():
        d=f[(f.case==case)&(f.model=='full')&(f.month==3)].sort_values('lead')
        correction=base.reindex(target)[var]-transforms[case].reindex(target)[var]
        y=d[outvar].to_numpy()+correction.to_numpy()
        assert np.isclose(y[0],base.loc[target[0],var])
        ax.plot(np.arange(13),y,color=color,ls=ls,lw=2.4)
    ax.axhline(0,color='.55',lw=.7);ax.grid(alpha=.16)
    ax.set(xlim=(-.2,12.2),ylabel='Niño3.4 anomaly (°C)' if var=='Nino34' else r'WWV anomaly ($10^{14}$ m$^3$)')
    ax.set_xticks([0,3,6,9,12],['Mar\n2015','Jun','Sep','Dec','Mar\n2016'])
fig.text(.055,.04,'Same ERSSTv5 SST inputs, NPMM definition, training period and XRO equations; only WWV detrending is changed and models re-fitted.\n'
         'All curves are shown on the SAME 1980–2014 monthly-climatology baseline by restoring each model\'s removed trend.\n'
         'These are sensitivity experiments, not a choice of the best preprocessing after viewing the 2015 outcome.',
         fontsize=8.8,color='#4e5660',linespacing=1.6,va='bottom')
save(fig,'audit_WWV_preprocessing_sensitivity')

notes='''2015年XRO大误差核查（2026-10-14）

结论：没有发现相图的横纵坐标互换、月份错配或WWV单位缩放错误。原图忠实显示了那一套试验输出，但这套“ERSSTv5 + PMEL、逐训练期二次去趋势”的输入方案尚未验证为可靠基准。
此前没有先做作者数据的基准核查，就对NPMM消融增益及路径作较强解释，证据不足。原图和消融百分比保留为试验记录，不能当作标准XRO性能或稳健PMM贡献。

3月起报核查（模型系数统一用1980–2014年拟合）：
1. 原方案：Niño3.4十二个月RMSE 1.543°C；11月预测0.898°C，同基准观测3.078°C。
2. 官方已预处理ORAS5示例：RMSE 0.369°C；11月预测2.343°C，同基准观测2.760°C。
3. 将ORAS5示例也按训练期重新二次去趋势，RMSE增为0.876°C。说明不能把第1、2项差别全部归因于数据产品；前处理也很关键。
4. 原方案中仅将WWV改为训练期线性去趋势、保持SST处理不变，11月Niño3.4预测1.479°C，RMSE1.131°C。
5. 原方案中仅将WWV改为只去训练期月气候态，11月Niño3.4预测1.743°C，RMSE0.941°C。
第4、5项是受控敏感性试验，不是根据2015实况选定新的最佳方案。

初始状态：
PMEL自带的2015年3月WWV异常为+0.955×10^14 m³；基于1980–2014月气候态为+0.766；再线性去趋势为+0.466；再二次去趋势为-0.315。
这些是不同异常基准，正负号变化本身不能证明哪一个错误；但它实质改变了模型所见的充电状态，必须检验其预测稳定性。
官方示例变量名WWV，实际单位是m、表示5S–5N,120E–80W区域平均D20异常。它不是PMEL总体积。对照图分别标注单位，不能直接比较两图纵坐标数值。

数值与绘图验证：
原预报初值与对应观测一致，目标月=起报月+提前期；调用官方公开API与积分核心结果一致。
将WWV换成100倍单位、重新拟合并换回原单位，预报最大差异约7.3e-15，排除了简单单位缩放错误。
积分步数10增至20，2015年3月起报Niño3.4最大差别约0.0023°C，不足以解释原误差。
原图展示二次去趋势残差；WWV敏感性新图则把各自趋势加回，统一在1980–2014月气候态异常坐标上比较；两者标签有明确区别。

参考试验的限制：
ORAS5示例文件已经预处理且覆盖1979–2024。虽然重新拟合的动力系数只用2014年及以前数据，不能排除示例指数原有前处理使用后来信息。
因此参考图用于检查代码和数据方案，不应宣称为严格样本外的0.369°C预报技巧，也不能与原方案做公平胜负排名。
另保留训练至2022年的Cookbook诊断，但它把2015年纳入了训练，不在主对照图中作为预报结果展示。

后续正式消融的前提：
先取得未经预处理、定义一致的ORAS5十状态输入，恢复完整数据来源；气候态与趋势仅用各起报时点以前的数据估计。
用2015之前的历史起报窗检验预处理选择，再冻结方案评价2015和2026；不能按这两年的拟合效果挑参数。
该本地官方ORAS5示例只到2024年12月，不能用它伪造2026年的标准XRO对照。2026现有ERSST/PMEL结果仅保留为敏感性试验。

文件：
audit_time_series_init_01/03/05.png/pdf：原试验与官方数据参考的时间序列对照。
audit_phase_space_init_01/03/05.png/pdf：同上，横轴Niño3.4、纵轴WWV/明确标注的D20代理量。
audit_WWV_preprocessing_sensitivity.png/pdf：同一显示基准下的WWV前处理敏感性。
preprocessing_and_data_forecasts.csv、preprocessing_and_data_scores.csv：逐月数值和评分。

参考：https://github.com/senclimate/XRO
'''
(OUT/'audit_notes_cn.txt').write_text(notes)
print('Saved audit figures and notes:',OUT)
