#!/usr/bin/env python3
"""Summarize the rerun and show why a 3-state RO differs from full XRO."""
import json
import pandas as pd
import numpy as np
import xarray as xr
import redo_ro_pmm_on_oras5 as redo
import run_xro_npmm_ablation as xro
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT=redo.OUT
f=pd.read_csv(OUT/'all_forecasts.csv',parse_dates=['init','target'])
scores=pd.read_csv(OUT/'event_incremental_skill.csv')
meta=json.loads((OUT/'methods_and_validation.json').read_text())
rawmeta=json.loads((redo.RAW.parent/'source_and_validation.json').read_text())
validation=pd.read_csv(OUT/'pre2015_preprocessing_validation.csv')
ref=xr.open_dataset(redo.REF).drop_vars('month').to_dataframe()[xro.VARS].astype(float).loc['1982-01':]
fit=xro.fit_model(ref.loc[:'2014-12'])
fc=xro.forecast(fit,ref.loc['2015-03-01'].to_numpy(),3)
dates=pd.date_range('2015-03',periods=13,freq='MS')
truth=ref.reindex(dates)
ref_rows=f[f.protocol.eq('supplied_ORAS5_diagnostic')&f.family.eq('nonlinear')&f.month.eq(3)]
curves={
    'Observed':(truth[['Nino34','WWV']].to_numpy(),'#202833','-'),
    'RO: 2 states':(ref_rows[ref_rows.model.eq('RO')].sort_values('lead')[['T','H']].to_numpy(),'#2878B5','--'),
    'RO + NPMM: 3 states':(ref_rows[ref_rows.model.eq('RO_NPMM')].sort_values('lead')[['T','H']].to_numpy(),'#009E73','-.'),
    'Full XRO: 10 states':(fc[:,:2],'#D55E00','-'),
}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
fig,axes=plt.subplots(1,2,figsize=(12.6,6.6))
fig.subplots_adjust(top=.77,bottom=.25,wspace=.25)
fig.suptitle('RO + NPMM is a smaller model than full XRO | March 2015',y=.98,fontsize=16)
handles=[Line2D([0],[0],color=c,ls=ls,lw=2.4,label=name) for name,(_,c,ls) in curves.items()]
fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.5,.93),frameon=False)
for name,(v,color,ls) in curves.items():
    axes[0].plot(np.arange(13),v[:,0],color=color,ls=ls,lw=2.4)
    axes[1].plot(v[:,0],v[:,1],color=color,ls=ls,lw=2.4,marker='o',ms=3)
    for k in [3,6,9,12]:
        axes[1].annotate('',xy=v[k,:2],xytext=v[k-1,:2],arrowprops={'arrowstyle':'->','color':color,'lw':1.4})
    if name=='Observed':
        for k in [3,6,9,12]:
            axes[1].annotate(['Jun','Sep','Dec','Mar +1'][k//3-1],v[k,:2],xytext=(6,4),textcoords='offset points',fontsize=8)
axes[0].set(ylabel='Niño3.4 anomaly (°C)',xlim=(0,12),xticks=[0,3,6,9,12],xticklabels=['Mar\n2015','Jun','Sep','Dec','Mar\n2016'])
axes[1].set(xlabel='Niño3.4 anomaly (°C)',ylabel='WWV proxy: mean D20 anomaly (m)')
axes[1].margins(x=.15,y=.15)
axes[1].scatter(truth.Nino34.iloc[0],truth.WWV.iloc[0],s=120,marker='*',color='#202833',zorder=10)
for ax in axes:ax.grid(alpha=.15);ax.axhline(0,color='.5',lw=.7)
fig.text(.055,.035,'All models use the same supplied ORAS5 indices, 1982–2014 coefficient training and official nonlinear XRO core.\n'
         'The 3-state model adds only NPMM. The 10-state model additionally includes SPMM, Indian Ocean and Atlantic modes.\n'
         'Reference diagnostic only: supplied indices were already preprocessed and may use later information.',
         fontsize=8.8,linespacing=1.6,color='#4e5660',va='bottom')
redo.save(fig,'reference_2state_3state_10state_march2015')
complexity=[]
for name,(v,_,_) in curves.items():
    if name=='Observed':continue
    err=v[1:,:2]-truth[['Nino34','WWV']].to_numpy()[1:]
    complexity.append({'model':name,'T_rmse_C':float(np.sqrt(np.mean(err[:,0]**2))),
                       'H_rmse_m':float(np.sqrt(np.mean(err[:,1]**2)))})
pd.DataFrame(complexity).to_csv(OUT/'reference_2state_3state_10state_scores.csv',index=False)

lines=[
'RO 与 RO＋PMM 重做及核查（2026-10-14）',
'',
'已完成内容：',
'1. 保留旧版线性RO的方程、年度正余弦项、训练期标准差缩放、ridge alpha=1与月积分方法；没有为了追随2015实况更换这套估计器。',
'2. 在相同模型中分别替换WWV、Niño3.4及PMM输入，复现旧预报以核对来源。',
'3. 取得未经去气候态/去趋势的ORAS5区域月均值。原始资料1979年1月–2026年9月；模型统一从1982年开始，以便保留早期SST–风PMM的完整训练期。',
'4. 对不去趋势/线性/二次去趋势三个选项，使用2000–2013每月起报、1–12月提前期、仅截至2014年12月的实况检验；依据二状态RO的T/H标准化联合均方误差选择。',
f'5. 选择阶数{meta["trend_order_selected"]}，即线性去趋势；方案冻结后重跑2015、2026和历史起报。选择过程中没有看2015/2026预测效果或PMM增益。',
'6. 额外采用官方XRO核心的非线性RO作为独立对照；两状态与三状态使用相同非线性项和季节结构。它不是对旧线性模型的悄悄替换。',
'7. 两年均完成1/3/5月起报的时间序列及横轴Niño3.4、纵轴WWV代理量相图，提供PNG和矢量PDF。',
'',
'旧模型核查：',
'旧RO确实使用线性而非二次去趋势，不能把上次XRO的二次趋势问题直接套到它身上。',
'原有绘图时间和积分没有发现错位；问题是换用OISST/PMEL及自定义PMM后，未先建立与ORAS5一致的数据基准就解释增益。',
f'用旧输入重新执行旧模型，与存档预报的最大差为{meta["qa"]["unchanged_linear_model_vs_archived_forecasts_max_difference"]:.3g}，确认没有悄悄修改模型来追求好看的曲线。',
'2015年3月起报，保持旧SST–风PMM与线性估计器：旧输入Niño3.4 RMSE 1.211°C，仅替换官方示例WWV为1.060°C；再替换Niño3.4为0.827°C；再改用区域NPMM为0.915°C。',
'这些是参考数据诊断，不能把改变多个输入后的改善都解释为PMM贡献。官方示例已预处理，可能包含后期信息。',
'',
'正式重跑的输入和含义：',
'T=ORAS5 5S–5N、170W–120W SST；H=ORAS5 5S–5N、120E–80W平均D20；区域NPMM=ORAS5 10–25N、160W–120W SST。',
'H是WWV代理量，单位m，并非PMEL的总体积10^14 m³；图中已明确注明，不能直接比较两者数值大小。',
'原来的PMM分支仍用先前的OISST/ERA5联合SST–风EOF，在每个训练期内重新估计，并回归剔除Niño3.4影响。它与区域SST型NPMM、标准MCA PMM都不是同一个指数。',
'PMM定义澄清：联合EOF分支输入为海温SST、10米纬向风u10和经向风v10，海洋表层信息已经包含；称为“风PMM”不准确。区域NPMM分支仅使用区域SST。两者均为代理指标，本实验未分别构建标准MCA的PMM-SST和PMM-wind两个展开系数。',
'标准PMM包含海温与近地面风的耦合，NOAA分别提供PMM SST及PMM Wind指数：https://psl.noaa.gov/data/timeseries/month/PMM/ 。H则表示赤道次表层充放电状态，与PMM的海温部分不是同一个量。',
'RO只含T/H；RO+PMM或RO+NPMM分别含T/H/P。两模型都重新拟合，训练期、预处理和方程结构一致。起报后P自己演化，不使用未来实测P。',
'训练：2015用1982–2014；2026用1982–2025。起报值为该月整月平均，仅在月底以后可用；历史数据发布时滞和修订版本未模拟。',
'CDS consolidated产品用于2014年及以前，operational用于2015年以后，沿用上游实时XRO数据接口的产品拼接；产品强迫/同化系统差异是资料限制。',
'',
'图形异常基准：',
'模型在只用训练期估计的月气候态和线性趋势残差上拟合。绘图时把所移除背景加回，统一到1982–2014年月气候态异常，2015和2026使用同一显示零点。',
'预测和验证实况使用同一可逆变换，RMSE不因显示零点而改变。旧图内部观测与预报也使用相同基准；这次主要把两年及不同模型的显示基准统一，不能把原问题说成坐标画错。',
'2026年T/H均已验证至9月；起报后的验证长度：1月起报8个月、3月起报6个月、5月起报4个月，不能把它当作完整12个月或冬季峰值验证。',
'',
'保留旧线性RO，新的原始ORAS5输入下：',
]
for row in scores[scores.protocol.eq('raw_oras5')&scores.family.eq('linear')].itertuples():
    unit='°C' if row.variable=='T' else 'm'
    lines.append(f'{row.year}年{row.month}月起报 {row.variable}，验证{row.n}个月：RO RMSE={row.RO:.3f}{unit}；'
                 f'RO+原PMM={row.RO_jointPMM:.3f}{unit}（下降{row.RO_jointPMM_gain_percent:.1f}%）；'
                 f'RO+区域NPMM={row.RO_NPMM:.3f}{unit}（下降{row.RO_NPMM_gain_percent:.1f}%）。')
lines += [
'',
'如何解释：',
'加入PMM对两年3月起报的温度预测有帮助，但2015年的H误差增大；不能把温度RMSE下降写成整个充放电过程都预测成功。',
'两状态和三状态RO在春季起报后仍显著低估2015与2026增暖。正确对齐数据并不保证简单模型能达到完整XRO的技巧。',
'用户截图是十状态完整XRO与删除NPMM后九状态XRO的对照，保留了其他海盆模态；它不是RO和RO+PMM。已用完全一致的官方参考数据、1982–2014训练期、同一非线性核心重新比较2/3/10状态，见reference_2state_3state_10state_march2015。',
'对预处理选择之外的2015–2024起报进行三年连续块自助检验：原PMM分支的温度及H增益区间均跨零；区域NPMM的H在3/6个月提前期出现正增益区间，但只有10个起报年份、且检验多个提前期，不能夸大为普遍规律。',
'',
'验证：',json.dumps(meta['qa'],ensure_ascii=False,indent=2),
'气候态、趋势、缩放与动力系数按起报年截断；源数据月份连续、单位正确、海洋格点掩膜稳定。全部输出均有限值；不按观测结果调整轨迹或剔除差的起报。',
'原始数据来源、区域边界、样本数、SHA256见data/derived/research_2026/oras5_ro_raw_indices/source_and_validation.json。',
'',
'文件索引：',
'raw_oras5_linear_time_series_init_01/03/05.png/pdf：保留旧线性模型、统一原始数据的两年时间序列。',
'raw_oras5_linear_phase_space_init_01/03/05.png/pdf：对应相图。',
'raw_oras5_nonlinear_*：独立非线性RO对照。',
'supplied_ORAS5_diagnostic_*：作者预处理示例资料上的参考诊断。',
'event_incremental_skill.csv / event_phase_space_skill.csv：事件误差与二维相空间误差。',
'pre2015_preprocessing_validation.csv：完全在2015之前完成的前处理选择。',
'postselection_2015_2024_paired_bootstrap.csv：未参与前处理选择的起报年增益区间。',
'simple_baseline_forecasts.csv：持续性和模型零异常参考。',
'',
'复现：使用scripts/fetch_oras5_ro_raw_indices.py取得原始区域指数；执行scripts/redo_ro_pmm_on_oras5.py，再执行scripts/finalize_ro_pmm_redo.py。',
'',
'来源：',
'https://github.com/senclimate/XRO',
'https://raw.githubusercontent.com/senclimate/XRO/main/XRO/state.py',
'https://cds.climate.copernicus.eu/datasets/reanalysis-oras5',
'https://www.nature.com/articles/s41586-024-07534-6',
]
(OUT/'experiment_notes_cn.txt').write_text('\n'.join(lines)+'\n')
oldnote=redo.old.OUT/'experiment_notes_cn.txt'
notice=('【2026-10-14重做说明】本文件记录旧OISST/PMEL输入方案，保留用于追溯；新的同源ORAS5重跑、'
        '两种PMM定义和原模型复现核查见 ../ro_pmm_redo_oras5_20261014/experiment_notes_cn.txt。\n\n')
text=oldnote.read_text()
if not text.startswith('【2026-10-14重做说明】'):oldnote.write_text(notice+text)
print(pd.DataFrame(complexity).to_string(index=False))
print('Wrote',OUT/'experiment_notes_cn.txt')
