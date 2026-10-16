"""Curate and re-layout existing, validated results; no model fitting or new attribution."""
from pathlib import Path
import os,json,hashlib,shutil,html,zipfile
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'tmp/chen2015_reanalysis_mpl'))
import numpy as np,pandas as pd,xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.integrate import cumulative_trapezoid
import plot_chen2015_reanalysis as phys
OUT=ROOT/'outputs/research_2026/main_figure_selection_20261014'
PAPER=OUT/'01_paper_main';PPT=OUT/'02_ppt_main';SUP=OUT/'03_supplementary';DATA=OUT/'04_source_data'
for p in [PAPER,PPT,SUP,DATA]:p.mkdir(parents=True,exist_ok=True)
PHYS=ROOT/'outputs/research_2026/chen2015_reanalysis_20261014';FORE=ROOT/'outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014';SKILL=ROOT/'outputs/research_2026/forecast_skill_multimetric_20261014'
ATMOS=DATA/'atmospheric_hovmoller.nc'
if not ATMOS.exists():ATMOS=ROOT/'data/derived/research_2026/jiang_1997_2015_2023_mar_oct_sst_precip_stress_hovmoller.nc'
YRS=[1997,2015,2023];FYRS=[2015,2023,2026]
BLACK='#191919';CORAL='#DC7D69';BLUE='#397EAA';GOLD='#B3996A';GREY='#999999'
MODELS=['RO','RO_SST','NCEP CFSv2','NASA GMAO','CMC CANSIP','JMA']
MCOL=[GREY,CORAL,BLUE,'#9467BD','#379B8A','#BA914C']
MLAB=['RO','RO +\nPMM','NCEP\nCFSv2','NASA\nGMAO','CMC\nCanSIPS','JMA']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'axes.titleweight':'bold','axes.labelsize':11,'legend.fontsize':9,'legend.frameon':False,'axes.linewidth':1,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,'savefig.facecolor':'white'})
d,e,t=phys.getdata()
summary=pd.read_csv(PHYS/'main_event_comparison.csv').set_index('event_year')
heat=pd.read_csv(PHYS/'event_two_term_heat.csv')
scores=pd.read_csv(SKILL/'overall_metrics.csv')
ro=pd.read_csv(FORE/'RO_PMM_seasonal_full_trajectories.csv',parse_dates=['center','init'])
obs=pd.read_csv(FORE/'observations.csv',index_col=0,parse_dates=True).seasonal_1991_2020
atm=xr.open_dataset(ATMOS).load()
assert atm.attrs['anomaly_reference']=='1982-2022 same-calendar-month linear expectation'
assert list(atm.event_year.values)==YRS
records=[]

def save(fig,folder,stem,title,claim,notes):
    for ext in ['png','svg']:fig.savefig(folder/f'{stem}.{ext}',dpi=300)
    records.append(dict(file=str((folder/f'{stem}.png').relative_to(OUT)),vector=str((folder/f'{stem}.svg').relative_to(OUT)),title=title,claim=claim,notes=notes))
    plt.close(fig)

def header(fig,title,sub,footer,left=.075,foot_y=.027):
    fig.suptitle(title,fontsize=20,fontweight='bold',y=.975)
    fig.text(.5,.913,sub,ha='center',fontsize=11,color='#A74D3F')
    fig.text(left,foot_y,footer,fontsize=9,linespacing=1.5)

def month_axis(ax):
    ax.set(xlim=(.7,17.3),xticks=[1,4,7,10,13,17],xticklabels=['Jan','Apr','Jul','Oct','Jan +1','May +1'])
    ax.axhline(0,color='.55',lw=.7);ax.axvline(12.5,color=CORAL,lw=.8,ls='--')

VARS=[('sst_anomaly_c','sst_lon','ERSSTv5 SST','°C','RdBu_r',2.5),('precip_anomaly_mm_day','precip_lon','GPCP precipitation','mm day⁻¹','BrBG',6),('eastward_stress_anomaly_nm2','stress_lon','ERA5 eastward stress','N m⁻²','RdBu_r',.05)]
def atmos_figure(years,folder,stem,ppt=False):
    fig,axs=plt.subplots(len(years),3,figsize=(16,9 if ppt else 11.8),sharey=True)
    fig.subplots_adjust(left=.075,right=.98,top=.86,bottom=.19,hspace=.22,wspace=.14)
    for j,(key,lon,title,unit,cmap,lim) in enumerate(VARS):
        for i,y in enumerate(years):
            ax=axs[i,j];a=atm[key].sel(event_year=y)
            im=ax.pcolormesh(a[lon],a.month,a,cmap=cmap,vmin=-lim,vmax=lim,shading='nearest')
            ax.set(ylim=(10.5,2.5),xlim=(120,280),xticks=[120,180,220,280],xticklabels=['120°E','180°','140°W','80°W'],yticks=[3,5,7,10],yticklabels=['Mar','May','Jul','Oct'])
            for x in [180,220]:ax.axvline(x,color='.3',lw=.7,ls='--')
            ax.set_title(f'({chr(97+i*3+j)}) {y} | {title}',loc='left',fontsize=11.5)
            if j==0:ax.set_ylabel('Developing year')
        box=axs[-1,j].get_position();cax=fig.add_axes([box.x0,.112,box.width,.016]);fig.colorbar(im,cax=cax,orientation='horizontal',extend='both',label=unit)
    header(fig,'SST, Convection and Wind: Different Event Evolution','10°S–5°N | March–October | 1982–2022 same-month linear expectation',
           'Physical fields retain their own units; positive stress denotes eastward/westerly anomalies. Atmospheric baseline is stated separately from WWV26.\nThese panels establish timing and spatial correspondence; they do not establish a causal chain or a new coupling index.')
    save(fig,folder,stem,'海温、降水与风应力的共同演变','2023东部先暖，中部降水与西风响应较晚、较弱。','大气图沿用1982—2022同月线性期望；不与WWV26同月均值基准混称。')

# F02: a common physical reference and the same three historical events.
with xr.open_dataset(PHYS/'WWV26_monthly_1980_2024.nc') as nc:
    a=nc.d26_anomaly.where((nc.lat>-9)&(nc.lat<9)&(nc.lon>120)&(nc.lon<280),drop=True)
    hov=a.weighted(np.cos(np.deg2rad(a.lat))).mean('lat').load()
    for y in YRS:
        g=d[d.time.between(f'{y}-01-01',f'{y+1}-05-31')]
        np.testing.assert_allclose(nc.wwv26_anomaly.sel(box='chen_basin',time=g.time.to_numpy()).values,g.chen_basin_wwv_m3,rtol=1e-12)
HOV_LIM=float(np.ceil(max(float(abs(hov.sel(time=slice(f'{y}-01',f'{y+1}-05'))).max()) for y in YRS)/10)*10)
BAS_LIM=phys.common_limits(np.concatenate([d[d.time.between(f'{y}-01-01',f'{y+1}-05-31')].chen_basin_wwv_m3.values/1e14 for y in YRS]),.13)

def reservoir_figure(folder,stem,ppt=False):
    fig,axs=plt.subplots(2,3,figsize=(16,9 if ppt else 10.2),gridspec_kw={'height_ratios':[.8,1.15]})
    fig.subplots_adjust(left=.075,right=.915,top=.855,bottom=.145,hspace=.39,wspace=.23)
    for j,y in enumerate(YRS):
        g=d[d.time.between(f'{y}-01-01',f'{y+1}-05-31')];xx=(g.time.dt.year-y)*12+g.time.dt.month
        ax=axs[0,j];ax.plot(xx,g.chen_basin_wwv_m3/1e14,'-o',color=BLACK,lw=2,ms=3);month_axis(ax);ax.set_ylim(BAS_LIM)
        ax.set_title(f'({chr(97+j)}) {y}/{str(y+1)[-2:]}: basin reserve',loc='left')
        if j==0:ax.set_ylabel('WWV26′ (10¹⁴ m³)')
        h=hov.sel(time=slice(f'{y}-01',f'{y+1}-05'));ax=axs[1,j]
        im=ax.pcolormesh(h.lon,np.arange(1,18),h,cmap='RdBu_r',vmin=-HOV_LIM,vmax=HOV_LIM,shading='nearest')
        ax.set(ylim=(17.5,.5),xlim=(120,280),xticks=[120,180,220,280],xticklabels=['120°E','180°','140°W','80°W'],yticks=[1,4,7,10,13,17],yticklabels=['Jan','Apr','Jul','Oct','Jan +1','May +1'])
        ax.axhline(12.5,color='.35',lw=.7,ls='--')
        for x in [180,220]:ax.axvline(x,color='.4',lw=.7,ls=':')
        ax.set_title(f'({chr(100+j)}) Warm-layer thickness',loc='left')
    cax=fig.add_axes([.94,.19,.014,.32]);fig.colorbar(im,cax=cax,label='D26 anomaly (m)')
    header(fig,'Warm-Water Reserve and Spatial Evolution','Chen geometry: 9°S–9°N, 120°E–80°W | SODA3.15.2 | Instantaneous σθ = 26',
           'WWV26 and D26 use the 1980–2022 calendar-month mean, without detrending or filtering. D26 is the wet-area-weighted latitude mean.\nStorage is a volume; D26 is warm-layer thickness, including bottom-limited coastal columns. Neither is temperature or heat content.')
    save(fig,folder,stem,'暖水储备与空间演变','比较三事件充放电时序，并展示暖层空间结构。','不是水团轨迹证明；D26不是D20或OHC。')

arr_vals=[];fate_vals=[]
for y in YRS:
    g=d[d.time.dt.year.eq(y)&d.time.dt.month.le(6)]
    arr_vals.extend(g[[b+'_wwv_m3' for b in ['west','central','east']]].values.ravel()/1e14)
    cum=cumulative_trapezoid(g.east_west_q_sv,(g.time-g.time.iloc[0]).dt.total_seconds(),initial=0)/1e8
    arr_vals.extend(cum);assert np.isclose(cum[-1],summary.loc[y,'arrival_west_in_1e14m3'])
    r=e[e.event_year.eq(y)&e.phase.eq('decay')&e.box.eq('east')&e.baseline_method.eq('monthly_mean')].iloc[0]
    fate_vals.extend(-r[['west_in_1e14m3','north_in_1e14m3','south_in_1e14m3','east_in_1e14m3','unresolved_1e14m3','storage_change_1e14m3']].to_numpy(float))
ARR_LIM=phys.common_limits(arr_vals,.20);FATE_LIM=phys.common_limits(fate_vals,.20)

def surface(ax):
    vals=summary.loc[YRS,'decay_surface_loss_zj']
    bars=ax.bar(range(3),vals,color=[GOLD,BLUE,CORAL],width=.53,edgecolor='.4',lw=.6)
    for i,v in enumerate(vals):ax.text(i,v+.1,f'{v:.2f}',ha='center',fontsize=12)
    ax.set(xticks=range(3),xticklabels=['1998','2016','2024'],ylim=(0,float(vals.max())*1.22),ylabel='Surface heat-loss anomaly (ZJ)')
    ax.axhline(0,color='.5',lw=.7)

def pathways_figure():
    fig=plt.figure(figsize=(16,12));gs=fig.add_gridspec(3,3,left=.07,right=.98,top=.87,bottom=.16,hspace=.57,wspace=.24,height_ratios=[1,1,.62])
    for j,y in enumerate(YRS):
        ax=fig.add_subplot(gs[0,j]);phys.volume_arrival(ax,d,y,ARR_LIM);ax.set_title(f'({chr(97+j)}) Arrival: {y}',loc='left')
        if j==0:ax.legend(ncol=2,fontsize=8,loc='upper left')
        ax=fig.add_subplot(gs[1,j]);phys.volume_fate(ax,e,y,FATE_LIM);ax.set_title(f'({chr(100+j)}) Discharge: {y+1}',loc='left');ax.tick_params(axis='x',labelsize=9)
        if j:ax.set_ylabel('')
    ax=fig.add_subplot(gs[2,:]);surface(ax);ax.set_title('(g) Surface energy exchange, reported separately',loc='left')
    header(fig,'Arrival, Redistribution and Surface Heat Loss','Regional σ26 application: 10°S–5°N | West / central / east = 160°E–180° / 180°–140°W / 140°W–80°W',
           '1980–2022 same-month mean. Arrival: Jan 15–Jun 15; discharge: next Jan 15–May 15. All volume panels use 10¹⁴ m³.\nPositive signed loss denotes export; negative denotes input. Unresolved = storage change minus integrated horizontal convergence.\nSurface heat loss in (g) uses ZJ and is not an additive term in the volume budget. Horizontal volume balance is not forced to zero.')
    save(fig,PAPER,'Fig03_arrival_and_fate','暖水到达、水平转移与海表散热','三事件都有东向输入；向西返回为主要已识别水平输出。','储量变化、边界转移、未解析项和海表能量分开；不作闭合去向百分比。')

def pathway_ppt(row,stem,title):
    fig,axs=plt.subplots(1,3,figsize=(16,9));fig.subplots_adjust(left=.075,right=.98,top=.80,bottom=.22,wspace=.23)
    for j,y in enumerate(YRS):
        if row==0:phys.volume_arrival(axs[j],d,y,ARR_LIM)
        else:phys.volume_fate(axs[j],e,y,FATE_LIM)
        axs[j].set_title(str(y if row==0 else y+1),fontsize=17)
        if row==1:axs[j].tick_params(axis='x',labelsize=9)
        if j:axs[j].set_ylabel('')
    if row==0:axs[0].legend(fontsize=10,ncol=1,loc='upper left')
    header(fig,title,'Instantaneous σθ = 26 | Common 1980–2022 monthly baseline',
           'Arrival: Jan 15–Jun 15; discharge: next Jan 15–May 15. Regional boxes span 10°S–5°N.\nPositive loss denotes export; negative loss denotes input. The unresolved volume term is not identified as surface heat loss.')
    save(fig,PPT,stem,title,'一次只解释到达或后续转移。','与论文Fig03相同数据、时间窗与共用量程。')

HEAT_KEYS=['vbar_Tprime_pw','vprime_Tbar_pw','linear_sum_pw']
HEAT_LABELS=[r'$\overline{v}T^\prime$',r'$v^\prime\overline{T}$','Two-term sum']
HEAT_COL=[BLUE,CORAL,BLACK]
heat_subset=t[t.time.dt.year.isin([1998,2016,2024])&t.time.dt.month.le(5)&t.gate.eq('east_north')&t.geometry.eq('instantaneous_sigma26')]
HLIM=phys.common_limits(heat_subset[HEAT_KEYS].values.ravel(),.15)
HBAR_LIM=(0,float(summary.loc[YRS,'decay_linear_sum_zj'].max())*1.22)

def heat_bars(ax,y):
    r=summary.loc[y];vals=r[['decay_vbar_Tprime_zj','decay_vprime_Tbar_zj','decay_linear_sum_zj']].values.astype(float)
    ax.bar(range(3),vals,color=HEAT_COL,width=.6,edgecolor='.4',lw=.6)
    for i,v in enumerate(vals):ax.text(i,v+.12,f'{v:.2f}',ha='center',fontsize=11)
    ax.set(xticks=range(3),xticklabels=HEAT_LABELS,ylim=HBAR_LIM,ylabel='Integrated contribution (ZJ)')
    r2=heat[heat.event_year.eq(y)&heat.phase.eq('decay')&heat.gate.eq('east_north')&heat.geometry.eq('instantaneous_sigma26')].iloc[0]
    assert r2.minimum_section_coverage==1 and np.isclose(vals.sum()-vals[-1],vals[-1])

def heat_figure(folder,stem,ppt=False):
    fig,axs=plt.subplots(1 if ppt else 2,3,figsize=(16,9 if ppt else 10),squeeze=False)
    fig.subplots_adjust(left=.075,right=.98,top=.85,bottom=.19,hspace=.40,wspace=.22)
    for j,y in enumerate(YRS):
        if not ppt:
            ax=axs[0,j];g=heat_subset[heat_subset.time.dt.year.eq(y+1)]
            for k,label,c in zip(HEAT_KEYS,HEAT_LABELS,HEAT_COL):ax.plot(g.time.dt.month,g[k],label=label,color=c,ls='--' if k==HEAT_KEYS[-1] else '-',lw=2,marker='o',ms=3)
            phys.setmonth(ax,1,5);ax.set_ylim(HLIM);ax.set_title(f'({chr(97+j)}) {y+1}: monthly contributions',loc='left')
            if j==0:ax.set_ylabel('Northward heat contribution (PW)');ax.legend(loc='best',fontsize=9)
        ax=axs[-1,j];heat_bars(ax,y);ax.set_title(f'({chr(97+j+(0 if ppt else 3))}) {y+1}: Jan 15–May 15',loc='left')
        if j:ax.set_ylabel('')
    header(fig,'Two Contributions to Northward Heat Transport','5°N, 140°W–80°W | Surface to instantaneous σθ = 26 | 1980–2022 same-month field means',
           'ρ = 1025 kg m⁻³, cp = 3990 J kg⁻¹ K⁻¹; potential temperature relative to 0°C. Section coverage is complete for these cases.\nOnly mean-flow × temperature-anomaly and anomalous-flow × mean-temperature terms are retained.\nTheir sum is not the complete heat-flux anomaly; moving-area background and nonlinear terms are not included.')
    save(fig,folder,stem,'北向热输送的温度项与流速项','在保留的两项中，异常流速项占主要贡献；2016和2024的月际时序不同。','不称纯风驱归因，不称完整热预算；开放断面温度参照已固定。')

def forecast_figure(folder,stem,ppt=False):
    fig,axs=plt.subplots(1,3,figsize=(16,9 if ppt else 7.5),sharey=True)
    fig.subplots_adjust(left=.065,right=.98,top=.79,bottom=.23,wspace=.16)
    for j,y in enumerate(FYRS):
        ax=axs[j];o=obs.loc[f'{y}-01':f'{y+1}-03'].dropna();x=(o.index.year-y)*12+o.index.month
        if y==2026:
            last=float(max(x));ax.axvspan(last+.5,15.5,color='.94',zorder=-5);ax.axvline(last+.5,color='.65',lw=.7,ls=':');ax.text(.96,.07,'No complete\nobserved seasons',ha='right',transform=ax.transAxes,color='.45',fontsize=10)
        ax.plot(x,o,color=BLACK,lw=2.5,label='Observed',zorder=5)
        for m,color,ls,label in [('RO',GREY,'--','RO'),('RO_SST',CORAL,'-','RO + PMM')]:
            for k,(issue,g) in enumerate(ro[ro.year.eq(y)&ro.method.eq(m)].groupby('issue_month')):
                g=g.sort_values('center');xx=(g.center.dt.year-y)*12+g.center.dt.month
                ax.plot(xx,g.value,color=color,ls=ls,lw=1.5,label=label if k==0 else None)
        ax.axhline(0,color='.5',lw=.7);ax.axhline(.5,color='.6',ls='--',lw=.7);ax.axvline(12.5,color=CORAL,ls='--',lw=.7)
        ax.set(xlim=(1,15.5),ylim=(-1,3.5),xticks=[1,4,7,10,13,15],xticklabels=['Jan','Apr','Jul','Oct','Jan +1','Mar'])
        ax.set_title(f'({chr(97+j)}) {y}'+(' | partial verification' if y==2026 else ''),loc='left')
    axs[0].set_ylabel('Three-month mean Niño3.4 SSTA (°C)');axs[0].legend(loc='upper left',fontsize=10)
    header(fig,'Observed and Predicted ENSO Evolution','All February–June starts | Seasonal means plotted at their center month | Original forecasts retained',
           'Observations and RO use the 1991–2020 SST reference, with the removed trend restored. Longer trajectories are shown than the scored leads.\n2015/2023 main fits use 2002–2024 and include event years; 2026 is a parameter-out-of-sample retrospective case with reconstructed PMM.\nRO ocean state remains mean D20. Updating WWV26 physical diagnostics does not refit the forecast model.')
    save(fig,folder,stem,'观测与RO／RO＋PMM预报轨迹','展示五个起报的误差方向和幅度，以及2026验证的截止位置。','季节均值坐标；不要与原四联图的去趋势逐月r、RMSE混用。')

def skill_figure(folder,stem,ppt=False):
    keys=['r','RMSE'] if ppt else ['r','RMSE','bias']
    fig,axs=plt.subplots(len(keys),3,figsize=(16,9 if ppt else 12),sharey='row')
    fig.subplots_adjust(left=.075,right=.985,top=.86,bottom=.18,hspace=.44,wspace=.14)
    lims={'r':(0,1.13),'RMSE':(0,1.12),'bias':(-1.04,.24)}
    ylabels={'r':'Correlation r','RMSE':'RMSE (°C)','bias':'Mean error (°C)'}
    for j,y in enumerate(FYRS):
        g=scores[scores.year.eq(y)].set_index('model').loc[MODELS]
        for i,key in enumerate(keys):
            ax=axs[i,j];ax.bar(range(6),g[key],width=.65,color=MCOL,edgecolor='.4',lw=.6)
            ax.axhline(0,color='.5',lw=.7)
            for k,v in enumerate(g[key]):ax.text(k,v+(.025 if v>=0 else -.025),f'{v:.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=9)
            ax.set(ylim=lims[key],xticks=range(6),xticklabels=MLAB);ax.tick_params(axis='x',labelsize=9)
            ax.set_title(f'({chr(97+i*3+j)}) {y} | n = {int(g.n.iloc[0])}',loc='left')
            if j==0:ax.set_ylabel(ylabels[key])
    header(fig,'Forecast Skill on Common Verification Pairs','RO / RO + PMM / four IRI dynamical models | Same pairs within each event | Season-center leads 1–5',
           'n counts overlapping issue–season pairs, not independent samples. Event-pooled r is not a multi-year fixed-lead ACC.\n2015/2023 are retrospective fits including the events; 2026 is partially verified and uses reconstructed PMM.\nIRI retains provider baselines and issue timing. These are descriptive case comparisons, not an equal-information operational ranking.')
    save(fig,folder,stem,'六种方法的预报技巧比较','相关、幅度误差和系统偏差共同评估；PMM增益因事件而异。','同一事件共用样本，2026仅19对；不做独立样本显著性声明。')

atmos_figure(YRS,PAPER,'Fig01_SST_precipitation_wind')
reservoir_figure(PAPER,'Fig02_WWV26_spatial_evolution')
pathways_figure()
heat_figure(PAPER,'Fig04_two_term_heat_transport')
forecast_figure(PAPER,'Fig05_forecasts')
skill_figure(PAPER,'Fig06_forecast_skill')
print('PAPER FIGURES DONE',flush=True)
atmos_figure([2015,2023],PPT,'PPT01_atmospheric_context',True)
reservoir_figure(PPT,'PPT02_WWV26_evolution',True)
pathway_ppt(0,'PPT03_arrival','Warm Water Reaches the Eastern Pacific')
pathway_ppt(1,'PPT04_volume_fate','Westward Return Is the Largest Resolved Horizontal Outflow')
fig,ax=plt.subplots(figsize=(16,9));fig.subplots_adjust(left=.12,right=.94,top=.80,bottom=.20);surface(ax)
header(fig,'Surface Heat Loss: A Separate Energy Diagnostic','Eastern box: 10°S–5°N, 140°W–80°W | Next Jan 15–May 15',
       '1980–2022 same-month mean. Positive values indicate anomalous heat loss from ocean to atmosphere.\nZJ is an energy unit; these bars are not added to the m³ volume budget or converted to a WWV26-loss percentage.',left=.12)
save(fig,PPT,'PPT05_surface_heat_loss','海表散热作为独立能量诊断','三事件海表热损失不同，和体积转移分开解释。','不与体积柱图直接相加。')
heat_figure(PPT,'PPT06_two_term_heat',True)
forecast_figure(PPT,'PPT07_forecasts',True)
skill_figure(PPT,'PPT08_forecast_skill',True)
print('PPT FIGURES DONE',flush=True)

# Required supplementary support: event-before-training controls.
past=pd.read_csv(FORE/'past_only_sensitivity_scores.csv');past=past[past['sample'].eq('season_center_leads_1_5')]
fig,axs=plt.subplots(2,2,figsize=(12,9),sharey='row');fig.subplots_adjust(left=.085,right=.98,top=.85,bottom=.21,hspace=.35,wspace=.20)
for j,y in enumerate([2015,2023]):
    protocols=['main',f'past_2002_{y-1}',f'past_1982_{y-1}']
    for i,key in enumerate(['r','RMSE']):
        ax=axs[i,j]
        for m,c,label,offset in [('RO',GREY,'RO',-.18),('RO_SST',CORAL,'RO + PMM',.18)]:
            vals=[float(scores[scores.year.eq(y)&scores.model.eq(m)][key].iloc[0])]+[float(past[past.year.eq(y)&past.model.eq(m)&past.protocol.eq(p)][key].iloc[0]) for p in protocols[1:]]
            ax.bar(np.arange(3)+offset,vals,width=.34,color=c,label=label)
            for x,v in zip(np.arange(3)+offset,vals):ax.text(x,v+.025,f'{v:.2f}',ha='center',fontsize=9)
        ax.set_xticks(range(3),['2002–2024\nmain',f'2002–{y-1}\npast only',f'1982–{y-1}\npast only']);ax.set_title(f'{y}: {key}',loc='left');ax.set_ylim((0,1.12) if key=='r' else (0,1.6));ax.set_ylabel('Correlation r' if key=='r' else 'RMSE (°C)')
axs[0,0].legend(loc='upper right')
header(fig,'Sensitivity to Training Only Before Each Event','Identical 25 seasonal verification pairs per event; no change to the manuscript main protocol',
       'Past-only controls estimate model coefficients and input preprocessing from the stated pre-event period.\nCurrent-version historical data and completed-month initialization still make these retrospective experiments, not original real-time forecasts.')
save(fig,SUP,'FigS01_past_only_training','事件前训练敏感性','2015改善、2023变差的方向在事件前训练中保留。','是主文预报结论必须配套的补充证据。')

COPY_SUP=[(PHYS/'Chen2015_STC_2015_2023','FigS02_STC_geometry'),(SKILL/'forecast_skill_by_lead_2015_2023_2026','FigS03_skill_by_lead'),(ROOT/'outputs/research_2026/slim_RO_PMM_2026_manuscript_style_20261014/figure_PMM_reconstruction_validation','FigS04_PMM_reconstruction'),(FORE/'IRI_only_four_models_2023_obs_reference','FigS06_IRI_2023'),(ROOT/'outputs/research_2026/IRI_RO_PMM_2015_2026_20261014/IRI_only_four_models_2015_obs_reference','FigS05_IRI_2015'),(ROOT/'outputs/research_2026/IRI_RO_PMM_2015_2026_20261014/IRI_only_four_models_2026_obs_reference','FigS07_IRI_2026'),(PHYS/'Maryland_forecast_WWV26_bridge_2015_2023','FigS08_full_bridge')]
for src,stem in COPY_SUP:
    for ext in ['png','svg']:
        p=src.with_suffix('.'+ext)
        if p.exists():shutil.copy2(p,SUP/(stem+'.'+ext))
    records.append(dict(file=str((SUP/(stem+'.png')).relative_to(OUT)),title=stem,claim='补充或汇报备份，不与正文重复整图。',notes='沿用对应源报告的方法、基准和限制。'))
for p in [PHYS/'main_event_comparison.csv',PHYS/'event_volume_budget.csv',PHYS/'event_two_term_heat.csv',PHYS/'method_contract_cn.txt',PHYS/'results_and_methods_cn.txt',SKILL/'overall_metrics.csv',SKILL/'metrics_by_lead.csv',FORE/'past_only_sensitivity_scores.csv',ATMOS]:
    if p.resolve()!=(DATA/p.name).resolve():shutil.copy2(p,DATA/p.name)
# Save the exact small arrays rendered here, including the already calculated Hovmoller field.
hov.sel(time=np.concatenate([pd.date_range(f'{y}-01-01',periods=17,freq='MS').values+np.timedelta64(14,'D') for y in YRS])).to_dataset(name='d26_latmean_anomaly').to_netcdf(DATA/'three_event_D26_hovmoller.nc')
records_path=OUT/'figure_manifest.json';records_path.write_text(json.dumps(records,ensure_ascii=False,indent=2))

# A visual index is a composition of scientific output figures, with no changes to their data panels.
fig,axs=plt.subplots(3,2,figsize=(14,19));fig.subplots_adjust(left=.02,right=.98,top=.95,bottom=.02,hspace=.15,wspace=.05)
for ax,r in zip(axs.flat,[r for r in records if r['file'].startswith('01_')]):
    ax.imshow(plt.imread(OUT/r['file']));ax.set_axis_off();ax.set_title(Path(r['file']).stem,fontsize=12,pad=8)
fig.suptitle('Main Figure Selection | 2026-10-14',fontsize=21,fontweight='bold',y=.985)
fig.savefig(OUT/'main_figures_contact_sheet.png',dpi=150);plt.close(fig)

qa={'no_refit':True,'main_figures':6,'ppt_figures':8,'all_rendered_from_existing_results':True,'physical_events':YRS,'forecast_events':FYRS,'physical_baseline':'1980-2022 same-month mean','atmospheric_baseline':'1982-2022 same-month linear expectation','forecast_verification_counts':scores.groupby('year').n.first().to_dict(),'required_support':['FigS01_past_only_training','FigS04_PMM_reconstruction'],'source_atmos_sha256':hashlib.sha256(ATMOS.read_bytes()).hexdigest(),'new_13event_causal_regression_claimed':False}
(OUT/'numerical_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
print('COMPLETE',OUT,flush=True)
