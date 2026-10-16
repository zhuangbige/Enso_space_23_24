"""Publication figure design review. Replots saved diagnostics; never refits models.

Run with bundled Python and PYTHONPATH=/private/tmp/maryland-climate-deps.
The delivered source_data folder makes a subsequent run independent of temp caches.
"""
from pathlib import Path
import os, json, shutil, hashlib, argparse, importlib.util
import numpy as np
import pandas as pd
import xarray as xr
from scipy.integrate import cumulative_trapezoid
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/maryland-figure-review/mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from PIL import Image, ImageOps, ImageDraw, ImageFont

WORK = Path('/Users/daiyue/Documents/Maryland')
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=WORK/'outputs/research_2026/figure_review_20261014')
args = parser.parse_args()
OUT = args.output
SRC = OUT/'source_data'
FIG = OUT/'figures'
for p in (OUT,SRC,FIG): p.mkdir(parents=True,exist_ok=True)
CACHE=Path('/private/tmp/maryland-2026-work/outputs/research_2026')
sources={
 'atmospheric_hovmoller.nc':CACHE/'main_figure_selection_20261014/04_source_data/atmospheric_hovmoller.nc',
 'three_event_D26_hovmoller.nc':CACHE/'main_figure_selection_20261014/04_source_data/three_event_D26_hovmoller.nc',
 'atmospheric_spatial.nc':Path('/private/tmp/maryland-figure-review/atmospheric_spatial.nc'),
 'monthly_anomalies.csv':CACHE/'chen2015_reanalysis_20261014/monthly_anomalies.csv',
 'event_volume_budget.csv':CACHE/'chen2015_reanalysis_20261014/event_volume_budget.csv',
 'two_term_heat_monthly.csv':CACHE/'chen2015_reanalysis_20261014/two_term_heat_monthly.csv',
 'main_event_comparison.csv':CACHE/'chen2015_reanalysis_20261014/main_event_comparison.csv',
 'overall_metrics.csv':CACHE/'forecast_skill_multimetric_20261014/overall_metrics.csv',
 'RO_PMM_seasonal_full_trajectories.csv':CACHE/'IRI_RO_PMM_Maryland_bridge_20261014/RO_PMM_seasonal_full_trajectories.csv',
 'observations.csv':CACHE/'IRI_RO_PMM_Maryland_bridge_20261014/observations.csv',
}
for name,p in sources.items():
 if not (SRC/name).exists(): shutil.copy2(p,SRC/name)

# Read the cached Natural Earth coastline once. Store coordinates with the delivery.
if not (SRC/'coastline.npz').exists():
 module=WORK/'.venv/lib/python3.12/site-packages/shapefile.py'
 spec=importlib.util.spec_from_file_location('shapefile',module)
 shp=importlib.util.module_from_spec(spec);spec.loader.exec_module(shp)
 reader=shp.Reader('/Users/daiyue/.local/share/cartopy/shapefiles/natural_earth/physical/ne_110m_coastline.shp')
 segments=[]
 for shape in reader.shapes():
  pts=np.asarray(shape.points); ids=list(shape.parts)+[len(pts)]
  for a,b in zip(ids[:-1],ids[1:]):
   seg=pts[a:b].copy();seg[:,0]%=360
   cuts=np.r_[0,np.where(np.abs(np.diff(seg[:,0]))>180)[0]+1,len(seg)]
   for i,j in zip(cuts[:-1],cuts[1:]):
    if j-i>1: segments.append(seg[i:j])
 np.savez_compressed(SRC/'coastline.npz',**{f's{i}':x for i,x in enumerate(segments)})
coast=list(np.load(SRC/'coastline.npz').values())

YRS=[1997,2015,2023]
BLACK='#20242A'; BLUE='#0072B2'; ORANGE='#D55E00'; GREY='#747C86'; TEAL='#00866A'; PURPLE='#8A6EAE'
EVENT={1997:GREY,2015:BLUE,2023:ORANGE}
REGION={'west':PURPLE,'central':'#B58B32','east':TEAL}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.2,'axes.labelsize':8.2,
 'axes.titlesize':9,'axes.titleweight':'bold','legend.fontsize':7.2,'legend.frameon':False,
 'axes.linewidth':.65,'xtick.labelsize':7.4,'ytick.labelsize':7.4,'xtick.direction':'out',
 'ytick.direction':'out','xtick.major.size':2.7,'ytick.major.size':2.7,
 'svg.fonttype':'none','savefig.facecolor':'white'})
atm=xr.open_dataset(SRC/'atmospheric_hovmoller.nc').load()
sp=xr.open_dataset(SRC/'atmospheric_spatial.nc').load()
hov=xr.open_dataset(SRC/'three_event_D26_hovmoller.nc').d26_latmean_anomaly.load()
d=pd.read_csv(SRC/'monthly_anomalies.csv',parse_dates=['time'])
e=pd.read_csv(SRC/'event_volume_budget.csv')
t=pd.read_csv(SRC/'two_term_heat_monthly.csv',parse_dates=['time'])
s=pd.read_csv(SRC/'main_event_comparison.csv').set_index('event_year')
metrics=pd.read_csv(SRC/'overall_metrics.csv')
ro=pd.read_csv(SRC/'RO_PMM_seasonal_full_trajectories.csv',parse_dates=['center','init'])
obs=pd.read_csv(SRC/'observations.csv',index_col=0,parse_dates=True).seasonal_1991_2020
assert atm.attrs['anomaly_reference']=='1982-2022 same-calendar-month linear expectation'
assert sp.attrs['reference']=='1982-2022 same-calendar-month linear expectation'
assert list(atm.event_year.values)==YRS and list(sp.event_year.values)==YRS
assert list(sp.month.values)==[5,6,7]
manifest=[]; checks={'no_model_refit':True,'no_new_significance_test':True,'source_hashes':{},'budget_sum_errors':{},'arrival_errors':{}}
for name in sources: checks['source_hashes'][name]=hashlib.sha256((SRC/name).read_bytes()).hexdigest()

def save(fig,name,title):
 for ext in ('png','svg'):fig.savefig(FIG/f'{name}.{ext}',dpi=300)
 manifest.append({'file':f'figures/{name}.png','svg':f'figures/{name}.svg','title':title})
 plt.close(fig)
def clean(ax):
 ax.spines[['top','right']].set_visible(False)
def title(ax,letter,txt):ax.set_title(f'{letter}  {txt}',loc='left',pad=6)
def lonax(ax):
 ax.set_xlim(120,280);ax.set_xticks([120,180,220,280],['120°E','180°','140°W','80°W'])
 labels=ax.get_xticklabels()
 if labels:labels[0].set_ha('left');labels[-1].set_ha('right')
def coastline(ax):
 for pts in coast:ax.plot(pts[:,0],pts[:,1],color='.38',lw=.45,zorder=5)
def foot(fig,text):fig.text(.09,.025,text,fontsize=7,color='#4B5563',va='bottom')
def discrete(name,lim,steps=12):
 levels=np.linspace(-lim,lim,steps+1);cm=plt.get_cmap(name,steps)
 return cm,BoundaryNorm(levels,cm.N),levels

# Figure 1: put events in columns throughout the paper.
fig,axs=plt.subplots(3,3,figsize=(7.25,7.15),sharex=True,sharey=True)
fig.subplots_adjust(left=.10,right=.85,top=.94,bottom=.11,wspace=.12,hspace=.30)
variables=[('sst_anomaly_c','sst_lon','SST′ (°C)','RdBu_r',2.5),
 ('precip_anomaly_mm_day','precip_lon','Rainfall′ (mm day⁻¹)','BrBG',6),
 ('eastward_stress_anomaly_nm2','stress_lon','Eastward stress′ (N m⁻²)','RdBu_r',.05)]
for i,(key,lon,label,cmap,lim) in enumerate(variables):
 cm,norm,levels=discrete(cmap,lim,10 if i!=1 else 12)
 for j,y in enumerate(YRS):
  ax=axs[i,j];a=atm[key].sel(event_year=y)
  im=ax.pcolormesh(a[lon],a.month,a,cmap=cm,norm=norm,shading='nearest',rasterized=True)
  lonax(ax);ax.set(ylim=(10.5,2.5),yticks=[3,5,7,9,10],yticklabels=['Mar','May','Jul','Sep','Oct'])
  for x in (180,220):ax.axvline(x,color='.35',ls=':',lw=.55)
  title(ax,chr(97+i*3+j),str(y) if i==0 else label.split(' (')[0])
  if j==0:ax.set_ylabel('Developing year')
 pos=axs[i,-1].get_position();cax=fig.add_axes([.883,pos.y0,.018,pos.height])
 cb=fig.colorbar(im,cax=cax,extend='both',ticks=np.linspace(-lim,lim,5));cb.set_label(label,labelpad=5)
foot(fig,'10°S–5°N; March–October. Anomalies: 1982–2022 same-month linear expectation.\nRed stress = eastward anomaly. The three fields retain their own units.')
save(fig,'Fig01_air_sea_evolution','海气演变：事件列、变量行')

# Figure 2: basin geography and common-axis storage plus D26 evolution.
fig=plt.figure(figsize=(7.25,6.7));gs=fig.add_gridspec(2,6,left=.10,right=.89,top=.94,bottom=.13,hspace=.48,wspace=.65,height_ratios=[1,1.15])
ax=fig.add_subplot(gs[0,:3]);coastline(ax)
ax.add_patch(Rectangle((120,-9),160,18,fill=False,color=BLACK,lw=1.1))
ax.text(200,11.5,'Chen WWV26 basin',ha='center',fontsize=8)
for name,x,w in [('west',160,20),('central',180,40),('east',220,60)]:
 ax.add_patch(Rectangle((x,-10),w,15,fill=False,edgecolor=REGION[name],ls='--',lw=1.1))
 ax.text(x+w/2,-16,name[0].upper(),ha='center',color=REGION[name],fontweight='bold',fontsize=8)
lonax(ax);ax.set(ylim=(-24,25),yticks=[-10,0,10],yticklabels=['10°S','0°','10°N'])
title(ax,'a','Integration domains');ax.set_xlabel('Solid: ±9° basin; dashed: 10°S–5°N boxes',fontsize=7)
ax=fig.add_subplot(gs[0,3:])
for y,ls in zip(YRS,[':','-','--']):
 g=d[d.time.between(f'{y}-01-01',f'{y+1}-05-31')];x=(g.time.dt.year-y)*12+g.time.dt.month
 ax.plot(x,g.chen_basin_wwv_m3/1e14,color=EVENT[y],ls=ls,lw=1.65,label=f'{y}/{str(y+1)[-2:]}')
ax.axhline(0,color='.5',lw=.55);ax.axvline(12.5,color='.65',lw=.6,ls=':')
basin_vals=np.concatenate([d[d.time.between(f'{y}-01-01',f'{y+1}-05-31')].chen_basin_wwv_m3.values/1e14 for y in YRS])
basin_pad=np.ptp(basin_vals)*.08
ax.set(xlim=(1,17),ylim=(basin_vals.min()-basin_pad,basin_vals.max()+basin_pad),xticks=[1,7,13,17],xticklabels=['Jan','Jul','Jan +1','May +1'])
ax.legend(loc='lower left');clean(ax);title(ax,'b','Basin WWV26′ (10¹⁴ m³)')
cm,norm,lev=discrete('RdBu_r',120,12)
for j,y in enumerate(YRS):
 ax=fig.add_subplot(gs[1,j*2:j*2+2]);h=hov.sel(time=slice(f'{y}-01',f'{y+1}-05'))
 im=ax.pcolormesh(h.lon,np.arange(1,18),h,cmap=cm,norm=norm,shading='nearest',rasterized=True)
 lonax(ax);ax.set(ylim=(17.5,.5),yticks=[1,4,7,10,13,17],yticklabels=['Jan','Apr','Jul','Oct','Jan +1','May +1'])
 if j:ax.tick_params(labelleft=False)
 for x in (180,220):ax.axvline(x,color='.4',lw=.6,ls=':')
 ax.axhline(12.5,color='.4',lw=.6,ls=':');title(ax,chr(99+j),f'{y}/{str(y+1)[-2:]}')
pos=ax.get_position();cb=fig.colorbar(im,cax=fig.add_axes([.925,pos.y0,.018,pos.height]),extend='both',ticks=[-120,-60,0,60,120]);cb.set_label('D26′ (m)')
foot(fig,'SODA3; surface to instantaneous σθ = 26. 1980–2022 monthly means; no detrending.\nD26 is warm-layer thickness (±9° latitude mean), not temperature or heat content.')
save(fig,'Fig02_WWV26_domains_evolution','暖水储备：区域定义与充放电时序')

# Figure 3: shared axes and horizontal dot comparisons rather than 18 budget bars.
fig=plt.figure(figsize=(7.25,7.3));gs=fig.add_gridspec(3,3,left=.10,right=.96,top=.94,bottom=.13,hspace=.65,wspace=.34,height_ratios=[1,1.2,.65])
for j,y in enumerate(YRS):
 ax=fig.add_subplot(gs[0,j]);g=d[d.time.dt.year.eq(y)&d.time.dt.month.le(6)]
 for name in REGION:ax.plot(g.time.dt.month,g[name+'_wwv_m3']/1e14,color=REGION[name],lw=1.1,label=name.capitalize()+' WWV26′')
 cum=cumulative_trapezoid(g.east_west_q_sv,(g.time-g.time.iloc[0]).dt.total_seconds(),initial=0)/1e8
 checks['arrival_errors'][str(y)]=float(cum[-1]-s.loc[y,'arrival_west_in_1e14m3'])
 assert abs(checks['arrival_errors'][str(y)])<1e-10
 ax.plot(g.time.dt.month,cum,'--',color=BLACK,lw=1.5,label='140°W input′')
 ax.set(xlim=(1,6),ylim=(-1.6,4.3),xticks=[1,3,6],xticklabels=['Jan','Mar','Jun'])
 ax.axhline(0,color='.6',lw=.5);title(ax,chr(97+j),f'Arrival: {y}');clean(ax)
 if j==0:ax.set_ylabel('Volume (10¹⁴ m³)')
 ax.text(.97,.94,f'Input: {cum[-1]:.2f}',ha='right',va='top',transform=ax.transAxes,fontsize=7.4)
 if j==0:handles,labels=ax.get_legend_handles_labels()
fig.legend(handles,labels,ncol=4,loc='upper center',bbox_to_anchor=(.54,.711),fontsize=7,columnspacing=1.0,handlelength=1.8)
ax=fig.add_subplot(gs[1,:]);keys=['west','north','south','east','unresolved','storage_change']
names=['West return','North (5°N)','South (10°S)','East edge','Unresolved','Storage loss']
for j,y in enumerate(YRS):
 row=s.loc[y];vals=np.array([-row['decay_'+k+('_in' if k in ['west','north','south','east'] else '')+'_1e14m3'] for k in keys])
 checks['budget_sum_errors'][str(y)]=float(sum(vals[:-1])-vals[-1]);assert abs(checks['budget_sum_errors'][str(y)])<1e-9
 yy=np.arange(6)+(j-1)*.22
 ax.scatter(vals,yy,color=EVENT[y],marker=['s','o','^'][j],s=25,label=str(y+1),zorder=4)
 for val,yv in zip(vals,yy):ax.annotate(f'{val:+.2f}',(val,yv),xytext=(5,0),textcoords='offset points',va='center',fontsize=6.7,color=EVENT[y])
ax.axvline(0,color='.25',lw=.8);ax.axhspan(3.6,4.4,color='.94',zorder=0);ax.axhline(4.5,color='.6',lw=.65)
ax.set(yticks=range(6),yticklabels=names,ylim=(5.5,-.6),xlim=(-2,4.65),xlabel='Signed loss contribution (10¹⁴ m³)   [negative = input]')
ax.grid(axis='x',color='.91',lw=.5);clean(ax);title(ax,'d','East-box redistribution: Jan 15–May 15, following year')
ax.legend(ncol=3,loc='center right',bbox_to_anchor=(.99,.46),fontsize=7.4)
ax=fig.add_subplot(gs[2,:]);vals=s.loc[YRS,'decay_surface_loss_zj'].values
for j,(y,val) in enumerate(zip(YRS,vals)):
 ax.plot([0,val],[j,j],color=EVENT[y],lw=1.4);ax.scatter(val,j,c=EVENT[y],marker=['s','o','^'][j],s=28)
 ax.text(val+.1,j,f'{val:.2f}',va='center',fontsize=7.5)
ax.set(yticks=range(3),yticklabels=[str(y+1) for y in YRS],ylim=(2.5,-.5),xlim=(0,5.7),xlabel='Surface heat-loss anomaly (ZJ)');clean(ax)
title(ax,'e','Separate energy diagnostic: same decay window')
foot(fig,'1980–2022 monthly means. Arrival integrates Jan 15–Jun 15; decay uses next Jan 15–May 15.\nUnresolved is a volume residual. Surface heat loss (ZJ) is not an additive volume term.')
save(fig,'Fig03_arrival_redistribution','到达与去向：横向点图明确输入、输出与残差')

# Figure 4: six geographic panels; no smoothing, invented vectors or significance.
fig,axs=plt.subplots(3,2,figsize=(7.25,6.45),sharex=True,sharey=True)
fig.subplots_adjust(left=.08,right=.96,top=.89,bottom=.235,wspace=.15,hspace=.34)
cm,norm,levels=discrete('BrBG',6,12)
for i,y in enumerate(YRS):
 for j,month in enumerate([5,6]):
  ax=axs[i,j];g=sp.sel(event_year=y,month=month)
  im=ax.pcolormesh(g.precip_lon,g.precip_lat,g.precip_anomaly_mm_day,cmap=cm,norm=norm,shading='nearest',rasterized=True)
  for lv,ls in [([-.05,-.03,-.01],'dashed'),([.01,.03,.05],'solid')]:
   cs=ax.contour(g.stress_lon,g.stress_lat,g.eastward_stress_anomaly_nm2,levels=lv,colors=BLACK,linewidths=.6,linestyles=ls)
   ax.clabel(cs,levels=[lv[1]],inline=True,inline_spacing=2,fmt='%+.2f',fontsize=5.5)
  coastline(ax);ax.axhline(0,lw=.5,color='.5',ls=':')
  ax.add_patch(Rectangle((180,-10),40,15,fill=False,ec='#4B5563',lw=.9,ls='--'))
  ax.add_patch(Rectangle((220,-10),60,15,fill=False,ec='#4B5563',lw=.9))
  lonax(ax);ax.set(ylim=(-14,14),yticks=[-10,0,10],yticklabels=['10°S','0°','10°N'])
  title(ax,chr(97+i*2+j),f'{y} | '+('May' if month==5 else 'June'))
cb=fig.colorbar(im,cax=fig.add_axes([.25,.16,.55,.017]),orientation='horizontal',extend='both',ticks=[-6,-3,0,3,6]);cb.set_label('Rainfall anomaly (mm day⁻¹)',labelpad=3)
fig.text(.08,.965,'Development-stage convection and momentum forcing',fontweight='bold',fontsize=11)
fig.text(.08,.933,'Contours: eastward stress′ at ±0.01, ±0.03, ±0.05 N m⁻²; solid + / dashed −',fontsize=7.5)
foot(fig,'1982–2022 same-month linear expectation. Boxes: central (dashed), east (solid), 10°S–5°N.\nMay–June is common to all events; July and the full chronology remain in supporting figures.\nThis is spatial correspondence, not proof of the subsequent discharge mechanism.')
save(fig,'Fig04_convection_stress_maps','新增空间证据：降水底色与稀疏风应力等值线')

# Figure 5: two-term magnitude AND timing. Keep 1998 on shared axes and add a labeled zoom.
fig=plt.figure(figsize=(7.25,6.3));gs=fig.add_gridspec(2,3,left=.10,right=.97,top=.91,bottom=.14,hspace=.47,wspace=.36,height_ratios=[1,1.05])
heatkeys=['vbar_Tprime_pw','vprime_Tbar_pw','linear_sum_pw']
heatlabels=[r'$\bar v T^{\prime}$',r'$v^{\prime}\bar T$','Two-term sum']
for j,y in enumerate(YRS):
 ax=fig.add_subplot(gs[0,j]);g=t[t.time.dt.year.eq(y+1)&t.time.dt.month.le(5)&t.gate.eq('east_north')&t.geometry.eq('instantaneous_sigma26')]
 assert len(g)==5;np.testing.assert_allclose(g[heatkeys[0]]+g[heatkeys[1]],g[heatkeys[2]],atol=1e-12)
 for k,c,ls,lbl in zip(heatkeys,[BLUE,ORANGE,BLACK],['-','-','--'],heatlabels):ax.plot(g.time.dt.month,g[k],color=c,lw=1.25,ls=ls,label=lbl)
 ax.set(xlim=(1,5),ylim=(-.5,2.9),xticks=[1,3,5],xticklabels=['Jan','Mar','May']);ax.axhline(0,lw=.6,color='.5');clean(ax);title(ax,chr(97+j),str(y+1))
 if j==0:ax.set_ylabel('Northward heat contribution (PW)');hh,ll=ax.get_legend_handles_labels()
fig.legend(hh,ll,ncol=3,loc='upper center',bbox_to_anchor=(.53,.99),fontsize=8)
ax=fig.add_subplot(gs[1,:2])
for j,y in enumerate(YRS):
 vals=s.loc[y,['decay_vbar_Tprime_zj','decay_vprime_Tbar_zj','decay_linear_sum_zj']].values.astype(float)
 ax.barh(j,vals[0],height=.52,color=BLUE);ax.barh(j,vals[1],left=vals[0],height=.52,color=ORANGE)
 ax.scatter(vals[2],j,c=BLACK,s=24,marker='D',zorder=4);ax.text(vals[2]+.15,j,f'{vals[2]:.2f}',va='center',fontsize=8)
 ax.text(.04,j+.34,f'{vals[0]:.2f} + {vals[1]:.2f}',fontsize=7,color='.3')
ax.set(yticks=range(3),yticklabels=['1998','2016','2024'],ylim=(2.65,-.6),xlim=(0,10),xlabel='Two retained contributions (ZJ)');clean(ax);title(ax,'d','Jan 15–May 15 integrals')
ax=fig.add_subplot(gs[1,2])
for y,ls in [(2015,'-'),(2023,'--')]:
 g=t[t.time.dt.year.eq(y+1)&t.time.dt.month.le(5)&t.gate.eq('east_north')&t.geometry.eq('instantaneous_sigma26')]
 ax.plot(g.time.dt.month,g.vprime_Tbar_pw,c=EVENT[y],ls=ls,lw=1.5,label=str(y+1))
ax.axhline(0,lw=.6,color='.5');ax.set(xlim=(1,5),ylim=(-.5,1.05),xticks=[1,3,5],xticklabels=['Jan','Mar','May'],ylabel=r'$v^{\prime}\bar T$ (PW)');ax.legend(loc='upper right');clean(ax);title(ax,'e','Timing: expanded scale')
foot(fig,'5°N, 140°W–80°W; instantaneous σ26 layer; 1980–2022 monthly means; T reference = 0°C.\nOnly the two requested terms are retained. Their sum is not the complete heat-flux anomaly.\nPanel e expands the scale explicitly; no attribution of v′ to wind alone is made.')
save(fig,'Fig05_two_term_heat_timing','两项输送：累计量与月际时序并重')

MODELS=['RO','RO_SST','NCEP CFSv2','NASA GMAO','CMC CANSIP','JMA']
MLAB=['RO','RO + PMM','NCEP CFSv2','NASA GMAO','CMC CanSIPS','JMA']
MCOL=[BLUE,ORANGE,GREY,GREY,GREY,GREY]
MARK=['o','s','^','D','v','P']
def trajectory(ax,y,letter):
 o=obs.loc[f'{y}-01':f'{y+1}-03'].dropna();xx=(o.index.year-y)*12+o.index.month
 if y==2026:ax.axvspan(max(xx)+.5,15.5,color='.94');ax.text(.97,.06,'Unverified',transform=ax.transAxes,ha='right',fontsize=7,color='.4')
 ax.plot(xx,o,color=BLACK,lw=1.7,label='Observed',zorder=5)
 for m,c,ls,lbl in [('RO',BLUE,'--','RO'),('RO_SST',ORANGE,'-','RO + PMM')]:
  for k,(issue,g) in enumerate(ro[ro.year.eq(y)&ro.method.eq(m)].groupby('issue_month')):
   g=g.sort_values('center');xx=(g.center.dt.year-y)*12+g.center.dt.month
   ax.plot(xx,g.value,color=c,ls=ls,lw=.95,alpha=.85,label=lbl if k==0 else None)
   ax.scatter(xx.iloc[0],g.value.iloc[0],s=11,facecolor='white',edgecolor=c,lw=.7,zorder=6)
 ax.axhline(0,color='.6',lw=.6);ax.axvline(12.5,color='.6',ls=':',lw=.6)
 ax.set(xlim=(1,15.5),ylim=(-1,3.5),xticks=[1,4,7,10,13,15],xticklabels=['Jan','Apr','Jul','Oct','Jan +1','Mar'])
 clean(ax);title(ax,letter,f'{y}: February–June starts')

fig=plt.figure(figsize=(7.25,7.1));gs=fig.add_gridspec(3,2,left=.17,right=.96,top=.94,bottom=.13,hspace=.50,wspace=.24,height_ratios=[1.35,1,1])
for j,y in enumerate([2015,2023]):
 ax=fig.add_subplot(gs[0,j]);trajectory(ax,y,chr(97+j))
 if j==0:ax.set_ylabel('Niño3.4 SSTA (°C)');ax.legend(loc='upper left',fontsize=7)
 for i,(key,xlim,label) in enumerate([('r',(.7,1.0),'Event-pooled correlation r'),('RMSE',(0,.9),'RMSE (°C)')]):
  ax=fig.add_subplot(gs[i+1,j]);q=metrics[metrics.year.eq(y)].set_index('model').loc[MODELS]
  for k,(m,c,mk) in enumerate(zip(MODELS,MCOL,MARK)):
   v=q.loc[m,key];ax.scatter(v,k,s=27,c=c,marker=mk,zorder=4)
   leftward=key=='r' and v>.95
   ax.annotate(f'{v:.3f}',(v,k),xytext=(-5 if leftward else 5,0),textcoords='offset points',ha='right' if leftward else 'left',va='center',fontsize=6.8,color=c)
  ax.plot(q[key].iloc[:2],[0,1],color='.6',lw=.8,zorder=1)
  ax.axhline(1.5,color='.75',lw=.6);ax.set(yticks=range(6),yticklabels=MLAB if j==0 else ['']*6,ylim=(5.5,-.5),xlim=xlim,xlabel=label)
  ax.grid(axis='x',color='.9',lw=.5);clean(ax);title(ax,chr(99+i*2+j),f'{y} | 25 pairs, 9 targets')
foot(fig,'Seasonal means at center month; scores use common leads 1–5. All five starts are shown.\n2015/2023 fits include the event years (2002–2024 training); event-pooled r is not multi-year ACC.\nIRI keeps provider baselines and issue timing. RO state remains D20; no operational ranking.')
save(fig,'Fig06_forecasts_correlation_RMSE','预报合并图：观测轨迹、相关系数与RMSE')

# 2026 is retained in a separate figure, with its partial verification marked.
fig=plt.figure(figsize=(7.25,5.3));gs=fig.add_gridspec(2,3,left=.18,right=.97,top=.94,bottom=.20,hspace=.54,wspace=.38,height_ratios=[1.3,1])
ax=fig.add_subplot(gs[0,:]);trajectory(ax,2026,'a');ax.set_ylabel('Niño3.4 SSTA (°C)');ax.legend(ncol=3,loc='upper left')
q=metrics[metrics.year.eq(2026)].set_index('model').loc[MODELS]
for i,(key,label,lim) in enumerate([('r','Correlation r',(.65,1.0)),('RMSE','RMSE (°C)',(0,1.1)),('bias','Bias (°C)',(-1,.1))]):
 ax=fig.add_subplot(gs[1,i])
 for k,(c,mk) in enumerate(zip(MCOL,MARK)):ax.scatter(q.iloc[k][key],k,c=c,marker=mk,s=25)
 ax.set(yticks=range(6),yticklabels=MLAB if i==0 else ['']*6,ylim=(5.5,-.5),xlim=lim,xlabel=label);ax.grid(axis='x',color='.9',lw=.5);clean(ax);title(ax,chr(98+i),f'2026 | n = 19')
foot(fig,'Partial verification through JAS 2026 (center: August). PMM is reconstructed, not the official extension.\nParameter-out-of-sample retrospective analysis; training ends in 2024. Nine-month paths are displayed;\nonly available common lead-1–5 seasonal pairs are scored. These pairs are not independent samples.')
save(fig,'Supp01_2026_extension','补充：2026独立展示观测截止与重建PMM')

# Full r/RMSE/bias dot plot preserves all six models and three events.
fig,axs=plt.subplots(3,3,figsize=(7.25,7.0),sharey=True)
fig.subplots_adjust(left=.18,right=.97,top=.94,bottom=.12,hspace=.36,wspace=.25)
for j,y in enumerate([2015,2023,2026]):
 q=metrics[metrics.year.eq(y)].set_index('model').loc[MODELS]
 for i,(key,label,lim) in enumerate([('r','Correlation r',(.7,1.0)),('RMSE','RMSE (°C)',(0,1.15)),('bias','Bias (°C)',(-1,.2))]):
  ax=axs[i,j]
  for k,(c,mk) in enumerate(zip(MCOL,MARK)):
   value=q.iloc[k][key];leftward=key=='r' and value>.94
   ax.scatter(value,k,c=c,marker=mk,s=24);ax.annotate(f'{value:.2f}',(value,k),xytext=(-4 if leftward else 4,0),textcoords='offset points',ha='right' if leftward else 'left',va='center',fontsize=6.5,color=c)
  ax.set(yticks=range(6),yticklabels=MLAB,ylim=(5.5,-.5),xlim=lim,xlabel=label);ax.axhline(1.5,color='.7',lw=.6);ax.grid(axis='x',color='.9',lw=.5);clean(ax);title(ax,chr(97+i*3+j),f'{y} | n = {int(q.n.iloc[0])}')
foot(fig,'All six methods use the same pairs within each event. Correlation is event-pooled, not fixed-lead ACC.\nNo confidence intervals or significance marks are inferred from overlapping forecast pairs.')
save(fig,'Supp02_all_metrics','补充：三事件相关、RMSE与系统偏差完整比较')

# Palette and rendering rules as a visual artifact.
fig=plt.figure(figsize=(7.25,4.6));fig.text(.08,.94,'Figure palette and encoding',fontsize=13,fontweight='bold')
groups=[('Forecast models',[('Observed',BLACK),('RO',BLUE),('RO + PMM',ORANGE),('IRI context',GREY)]),
 ('Event comparison',[('1997/98',GREY),('2015/16',BLUE),('2023/24',ORANGE)]),
 ('Regional storage',[('West',REGION['west']),('Central',REGION['central']),('East',REGION['east'])])]
for i,(name,items) in enumerate(groups):
 yy=.81-i*.16;fig.text(.08,yy,name,fontsize=9,fontweight='bold')
 for j,(label,c) in enumerate(items):
  x=.30+j*.165;fig.add_artist(Rectangle((x,yy-.01),.045,.033,transform=fig.transFigure,facecolor=c,edgecolor='none'))
  fig.text(x+.052,yy+.005,label,fontsize=7.5,va='center');fig.text(x,yy-.045,c,fontsize=7,color='.4')
for i,(cmap,label) in enumerate([('RdBu_r','SST / D26 / eastward stress: negative → positive'),('BrBG','Rainfall: dry anomaly → wet anomaly')]):
 ax=fig.add_axes([.30,.23-i*.095,.60,.033]);ax.imshow(np.linspace(-1,1,256)[None,:],cmap=cmap,aspect='auto');ax.set_axis_off();fig.text(.30,.28-i*.095,label,fontsize=8)
fig.text(.08,.035,'Zero-centered field colors; common limits across events.\nUse line styles / marker shapes as well as color. Meanings are fixed within each comparison.',fontsize=8,color='.35')
save(fig,'Palette_guide','统一配色与编码规则')

# Contact sheet is an overview only, not a publication image.
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',24)
sheet=Image.new('RGB',(1900,2510),'white');draw=ImageDraw.Draw(sheet)
draw.text((50,20),'Recommended six-figure sequence | 14 October 2026',font=font,fill='black')
for i,m in enumerate(manifest[:6]):
 im=Image.open(OUT/m['file']).convert('RGB');im.thumbnail((895,740))
 x=40+(i%2)*945;y=80+(i//2)*805
 draw.text((x,y),Path(m['file']).stem,font=font,fill=BLACK)
 sheet.paste(im,(x+(895-im.width)//2,y+40))
sheet.save(OUT/'recommended_six_contact_sheet.png')
checks['figures']=manifest;checks['d26_exceeds_120m_cells']=int((abs(hov)>120).sum())
checks['physical_baseline']='1980–2022 calendar-month mean, no detrending'
checks['atmospheric_baseline']='1982–2022 same-calendar-month linear expectation'
checks['selected_map_months']=[5,6]
checks['selection_reason']='Shared development months before the June arrival integral endpoint; July retained in original full matrix.'
checks['visual_QA']='Pending final image inspection'
(OUT/'figure_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(OUT/'numerical_QA.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
print(json.dumps({'output':str(OUT),'figure_count':len(manifest),'max_budget_error':max(abs(x) for x in checks['budget_sum_errors'].values())}))
