"""Descriptive multi-metric comparison on the existing common verification pairs."""
from pathlib import Path
import json, hashlib, shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014'
OUT = ROOT / 'outputs/research_2026/forecast_skill_multimetric_20261014'
OUT.mkdir(parents=True, exist_ok=True)
MODELS = ['RO', 'RO_SST', 'NCEP CFSv2', 'NASA GMAO', 'CMC CANSIP', 'JMA']
LABELS = ['RO', 'RO + PMM', 'NCEP CFSv2', 'NASA GMAO', 'CMC CanSIPS', 'JMA']
SHORT = ['RO', 'RO +\nPMM', 'NCEP\nCFSv2', 'NASA\nGMAO', 'CMC\nCanSIPS', 'JMA']
COLORS = ['#939393', '#DF7E69', '#377EB8', '#9467BD', '#379B8A', '#BA914C']
YEARS = [2015, 2023, 2026]

data = pd.read_csv(SOURCE / 'common_seasonal_forecasts.csv', parse_dates=['init', 'center', 'season_end'])
assert not data.duplicated(['year', 'init', 'center']).any()
assert data.lead_center.between(1, 5).all()
assert data.issue_month.between(2, 6).all()
assert np.array_equal(data.verified.to_numpy(), data.observed.notna().to_numpy())
valid = data.loc[data.verified].copy()
assert np.isfinite(valid[MODELS + ['observed']].to_numpy()).all()
assert valid.groupby('year').size().to_dict() == {2015: 25, 2023: 25, 2026: 19}
assert valid.loc[valid.year.eq(2026), 'season_end'].max() == pd.Timestamp('2026-09-01')

def metrics(g, model):
    p, o = g[model].to_numpy(), g.observed.to_numpy()
    e, er = p-o, g.RO.to_numpy()-o
    mse, ref = np.mean(e**2), np.mean(er**2)
    bias = np.mean(e)
    centered = np.sqrt(np.mean((e-bias)**2))
    r = np.corrcoef(p, o)[0, 1] if len(g) > 2 and np.std(p) > 1e-12 and np.std(o) > 1e-12 else np.nan
    result = dict(n=len(g), n_unique_targets=g.center.nunique(), r=r, RMSE=np.sqrt(mse),
                  MAE=np.mean(np.abs(e)), bias=bias, centered_RMSE=centered,
                  MSSS_vs_RO=1-mse/ref if ref > 0 else np.nan,
                  amplitude_ratio=np.std(p)/np.std(o) if np.std(o) > 0 else np.nan)
    assert np.isclose(result['RMSE']**2, bias**2+centered**2, atol=1e-12)
    return result

overall = pd.DataFrame([dict(year=y, model=m, **metrics(g,m)) for y,g in valid.groupby('year') for m in MODELS])
by_lead = pd.DataFrame([dict(year=y, lead_center=l, model=m, **metrics(g,m))
                       for (y,l),g in valid.groupby(['year','lead_center']) for m in MODELS])
by_issue = pd.DataFrame([dict(year=y, issue_month=l, model=m, **metrics(g,m))
                        for (y,l),g in valid.groupby(['year','issue_month']) for m in MODELS])
old = pd.read_csv(SOURCE/'seasonal_skill_common_pairs.csv')
check = old.merge(overall, on=['year','model'], suffixes=('_old','_new'), validate='one_to_one')
errors = {}
for k in ['n','r','RMSE','bias']:
    errors[k] = float(np.max(np.abs(check[k+'_old']-check[k+'_new'])))
    assert errors[k] < 1e-10
for df,name in [(overall,'overall_metrics.csv'), (by_lead,'metrics_by_lead.csv'), (by_issue,'metrics_by_issue.csv'), (valid,'verified_common_pairs.csv')]:
    df.to_csv(OUT/name, index=False)

plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'axes.titlesize':14,
                     'axes.titleweight':'bold', 'axes.labelsize':12, 'axes.linewidth':1.1,
                     'xtick.direction':'in', 'ytick.direction':'in', 'savefig.dpi':240})
fig,axs=plt.subplots(2,3,figsize=(16,9),sharey='row')
for col,y in enumerate(YEARS):
    g=overall[overall.year.eq(y)].set_index('model').loc[MODELS]
    x=np.arange(len(MODELS))
    for row,key in enumerate(['r','bias']):
        ax=axs[row,col]
        ax.bar(x,g[key],color=COLORS,width=.65,edgecolor='#555555',linewidth=.7)
        ax.axhline(0,color='.4',lw=.8)
        for xx,v in zip(x,g[key]):
            ax.text(xx,v+(0.023 if key=='r' or v>=0 else -.025),f'{v:.3f}',ha='center',va='bottom' if key=='r' or v>=0 else 'top',fontsize=9)
        ax.set_xticks(x,SHORT); ax.tick_params(top=True,right=True)
        ax.set_title(f'({chr(97+row*3+col)}) {y} | n = {int(g.n.iloc[0])}',pad=10)
    axs[0,col].set_ylim(0,1.13)
    axs[1,col].set_ylim(-1.02,.24)
axs[0,0].set_ylabel('Forecast–observation correlation r')
axs[1,0].set_ylabel('Mean error (°C; forecast − observed)')
fig.suptitle('ENSO Forecast Skill: Correlation and Systematic Bias',fontsize=21,fontweight='bold',y=.97)
fig.text(.5,.922,'RO, RO + PMM and four IRI dynamical models | Identical verified pairs within each year',ha='center',color='#BC5443',fontsize=12)
fig.subplots_adjust(left=.065,right=.985,top=.86,bottom=.22,hspace=.39,wspace=.12)
fig.text(.065,.045,'February–June initializations; three-month means; season-center leads 1–5 months. n counts issue–season pairs, not independent samples.\nCorrelation pools leads and starts within each event; it is not a multi-year fixed-lead ACC. Negative mean error denotes underprediction.\n2015/2023: retrospective fit includes event years. 2026: partial verification and reconstructed PMM. IRI retains provider baselines and issue timing.',fontsize=10,linespacing=1.5)
for ext in ['png','pdf','svg']:fig.savefig(OUT/f'forecast_correlation_bias_2015_2023_2026.{ext}')
plt.close(fig)

fig,axs=plt.subplots(3,3,figsize=(15,11.5),sharex=True,sharey='row')
for col,y in enumerate(YEARS):
    counts=valid[valid.year.eq(y)].groupby('lead_center').size()
    for row,key in enumerate(['r','bias','MSSS_vs_RO']):
        ax=axs[row,col]
        for m,label,color in zip(MODELS,LABELS,COLORS):
            g=by_lead[(by_lead.year.eq(y)) & (by_lead.model.eq(m))].sort_values('lead_center')
            ax.plot(g.lead_center,g[key],'-o',color=color,label=label,lw=2 if m in MODELS[:2] else 1.5,ms=4)
        ax.axhline(0,color='.6',lw=.7)
        ax.set_xticks(range(1,6)); ax.set_xlim(.8,5.2); ax.tick_params(top=True,right=True)
        ax.set_title(f'({chr(97+row*3+col)}) {y}',pad=9)
    axs[0,col].text(.02,.035,'n by lead: '+', '.join(str(int(counts.loc[l])) for l in range(1,6)),transform=axs[0,col].transAxes,fontsize=9)
    axs[2,col].set_xlabel('Season-center lead (months)')
axs[0,0].set_ylabel('Correlation r')
axs[1,0].set_ylabel('Mean error (°C)')
axs[2,0].set_ylabel('MSE skill relative to RO')
axs[0,0].set_ylim(-1.05,1.10)
mn=float(by_lead.MSSS_vs_RO.min());axs[2,0].set_ylim(min(-.1,mn-.1),1.1)
handles,labels=axs[0,0].get_legend_handles_labels()
fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.53,.929),ncol=6,frameon=False,fontsize=10)
fig.suptitle('ENSO Forecast Skill by Lead',fontsize=21,fontweight='bold',y=.97)
fig.subplots_adjust(left=.075,right=.985,top=.855,bottom=.19,hspace=.32,wspace=.13)
fig.text(.075,.048,'Same issue–season pairs for all six methods at each lead. MSE skill = 1 − MSE(model) / MSE(RO); positive values improve on RO.\nOnly 2–5 pairs per lead; r omitted for n < 3. Curves are descriptive, with no significance or skill-horizon claim. Seasons overlap.\nCenter lead 1 is a three-month mean starting in the issue month. Fit periods, information timing and IRI baselines differ as documented.',fontsize=10,linespacing=1.5)
for ext in ['png','pdf','svg']:fig.savefig(OUT/f'forecast_skill_by_lead_2015_2023_2026.{ext}')
plt.close(fig)

report='''预报技巧补充：相关、偏差及相对RO技巧

本次直接使用已交付的共同季节验证表，未重拟合模型、调整IRI初值或修改任何预报值。
目标为Niño3.4三个月平均，2—6月五个起报、季节中心提前期1—5个月；2015/2023各25对、2026共19对已完整观测配对。2026观测截至JAS、中心8月。

指标：
r：预报与观测的Pearson相关，描述变化对应程度；同一事件合并起报/提前期的r不等同跨年固定提前期ACC，也不能代替幅度误差检验。
RMSE：均方根误差；MAE：平均绝对误差；bias：预报减观测的均值，负值为低估。
centered_RMSE：扣除本验证样本平均误差后的误差离散度，仅作诊断，不是业务偏差订正结果。RMSE²=bias²+centered_RMSE²。
amplitude_ratio：预报标准差/观测标准差，描述本事件变化幅度。
MSSS_vs_RO = 1 - MSE(model)/MSE(RO)。0等于RO、正值优于RO、负值劣于RO。该指标是MSE的相对表达，不是独立于RMSE的新证据，也不是相对于气候态或持续性预报的技巧。

总体结果：
'''+overall.to_string(index=False,float_format=lambda x:f'{x:.4f}')+'''

解释：2015/2026加入PMM后相关提高、平均低估减轻；2023相关下降且平均低估加重，与RMSE变化方向一致。
JMA的事件合并相关在三个事件均最高，但2026 NASA GMAO的RMSE最小，说明相关最高不等于幅度最准确；这是当前样本的描述，不作一般业务排名。
分提前期表/图每点仅2—5个起报；n<3不报告相关系数，不能据此断言显著性或可靠提前期上限。已另存按起报月指标，便于检查结果是否由单一起报驱动。
重叠起报与季节不是独立样本，无常规独立样本p值或置信区间。2015/2023主模型2002—2024拟合含事件，2026参数样本外但属回溯且PMM为重建扩展。既有事件前训练对照保留在原报告，未混入主表。
IRI使用提供方距平、不同发布时间与模型版本，不能保证与RO等信息量；本比较不称严格业务竞赛。仅有确定性均值轨迹，未计算概率技巧/可靠度或集合离散度。
技巧评估与WWV26物理分析是两个独立步骤；此处RO海洋状态仍是D20，本次不把换暖水定义说成重拟合预报。
'''
(OUT/'methods_and_results_cn.txt').write_text(report)
qa=dict(source=str(SOURCE/'common_seasonal_forecasts.csv'),source_sha256=hashlib.sha256((SOURCE/'common_seasonal_forecasts.csv').read_bytes()).hexdigest(),
        old_metric_max_abs_errors=errors,verified_pairs={str(y):len(g) for y,g in valid.groupby('year')},
        n_by_lead=valid.groupby(['year','lead_center']).size().reset_index(name='n').to_dict('records'),
        numerical_identity='RMSE² = bias² + centered_RMSE²',all_methods_share_mask=True)
(OUT/'QA.json').write_text(json.dumps(qa,indent=2))
dest=Path('/Users/daiyue/Documents/Maryland')
delivered=[]
for p in [q for q in OUT.iterdir() if q.name != 'delivery_manifest.json']+[Path(__file__)]:
    rel=p.relative_to(ROOT);q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    digest=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(q.read_bytes()).hexdigest()==digest
    delivered.append(dict(path=str(rel),sha256=digest))
(OUT/'delivery_manifest.json').write_text(json.dumps(delivered,indent=2))
shutil.copy2(OUT/'delivery_manifest.json',dest/OUT.relative_to(ROOT)/'delivery_manifest.json')
print(overall.to_string(index=False),flush=True)
print('DELIVERED',dest/OUT.relative_to(ROOT),flush=True)
