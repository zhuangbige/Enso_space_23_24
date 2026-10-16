#!/usr/bin/env python3
from pathlib import Path
import os,json
import numpy as np,pandas as pd
from scipy.integrate import cumulative_trapezoid
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/research_2026/chen2015_reanalysis_20261014';OLD=ROOT/'outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014'
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'tmp/chen2015_reanalysis_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
BLACK='#181818';CORAL='#DC7D69';BLUE='#397EAA';GREY='#999999';GOLD='#B3996A'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.titlesize':12.2,'axes.titleweight':'bold','axes.labelsize':10.5,'axes.linewidth':1,'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,'legend.frameon':False,'legend.fontsize':8.5,'savefig.facecolor':'white'})

def save(fig,name):
 for ext in ['png','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=240,bbox_inches='tight')
 plt.close(fig)
def getdata():return (pd.read_csv(OUT/'monthly_anomalies.csv',parse_dates=['time']),pd.read_csv(OUT/'event_volume_budget.csv'),pd.read_csv(OUT/'two_term_heat_monthly.csv',parse_dates=['time']))
def setmonth(ax,start=1,end=6):
 ax.set_xlim(start-.12,end+.12);ax.set_xticks(range(start,end+1),['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][start-1:end]);ax.axhline(0,color='.5',lw=.7)
def volume_arrival(ax,d,year,ylim=None):
 g=d.loc[d.time.dt.year.eq(year)&d.time.dt.month.le(6)]
 for box,c in [('west',GOLD),('central',BLUE),('east',CORAL)]:ax.plot(g.time.dt.month,g[box+'_wwv_m3']/1e14,'-o',c=c,ms=3,lw=1.7,label=box.capitalize()+" WWV26′")
 sec=(g.time-g.time.iloc[0]).dt.total_seconds().to_numpy();cum=cumulative_trapezoid(g.east_west_q_sv,sec,initial=0)/1e8
 ax.plot(g.time.dt.month,cum,'--',c=BLACK,lw=1.7,label='Cumulative 140°W input′');setmonth(ax)
 ax.set_ylabel('Volume anomaly / input (10¹⁴ m³)');ax.text(.97,.07,f'140°W: {cum[-1]:+.2f} × 10¹⁴ m³',transform=ax.transAxes,ha='right',fontsize=9)
 if ylim:ax.set_ylim(ylim)
 return cum[-1]
def volume_fate(ax,e,year,ylim=None):
 r=e.loc[e.event_year.eq(year)&e.phase.eq('decay')&e.box.eq('east')&e.baseline_method.eq('monthly_mean')].iloc[0]
 keys=['west_in_1e14m3','north_in_1e14m3','south_in_1e14m3','east_in_1e14m3','unresolved_1e14m3','storage_change_1e14m3'];v=-r[keys].to_numpy(float)
 bars=ax.bar(range(6),v,color=[BLUE,CORAL,GOLD,'#94BDC6','.72',BLACK],edgecolor='.3',lw=.6,width=.65);bars[4].set_hatch('//')
 for i,x in enumerate(v):ax.annotate(f'{x:+.2f}',(i,x),xytext=(0,4 if x>=0 else -4),textcoords='offset points',ha='center',va='bottom' if x>=0 else 'top',fontsize=9)
 ax.set_xticks(range(6),['West\nreturn','North','South','East\nedge','Unresolved','Storage\nloss']);ax.set_ylabel('Signed volume loss (10¹⁴ m³)');ax.axhline(0,color='.5',lw=.7)
 if ylim:ax.set_ylim(ylim)
def common_limits(values,pad=.15):
 v=np.asarray(values);lo=min(0,float(np.nanmin(v)));hi=max(0,float(np.nanmax(v)));margin=(hi-lo)*pad or 1
 return lo-margin,hi+margin

def mainfig(d,e,t):
 fig,axes=plt.subplots(4,2,figsize=(14,14.6));fig.subplots_adjust(left=.085,right=.976,top=.92,bottom=.11,hspace=.56,wspace=.25)
 av=[];fates=[];bvals=[];tv=[]
 for y in [2015,2023]:
  g=d.loc[d.time.dt.year.eq(y)&d.time.dt.month.le(6)];av.extend(g[[b+'_wwv_m3' for b in ['west','central','east']]].to_numpy().ravel()/1e14);av.extend(cumulative_trapezoid(g.east_west_q_sv,(g.time-g.time.iloc[0]).dt.total_seconds(),initial=0)/1e8)
  r=e.loc[e.event_year.eq(y)&e.phase.eq('decay')&e.box.eq('east')&e.baseline_method.eq('monthly_mean')].iloc[0];fates.extend(-r[['west_in_1e14m3','north_in_1e14m3','south_in_1e14m3','east_in_1e14m3','unresolved_1e14m3','storage_change_1e14m3']].to_numpy(float))
  g=d.loc[d.time.between(f'{y}-01-01',f'{y+1}-05-31')];bvals.extend(g.chen_basin_wwv_m3/1e14)
  g=t.loc[t.time.dt.year.eq(y+1)&t.time.dt.month.le(5)&t.gate.eq('east_north')&t.geometry.eq('instantaneous_sigma26')];tv.extend(g[['vbar_Tprime_pw','vprime_Tbar_pw','linear_sum_pw']].to_numpy().ravel())
 for col,y in enumerate([2015,2023]):
  ax=axes[0,col];g=d.loc[d.time.between(f'{y}-01-01',f'{y+1}-05-31')];x=(g.time.dt.year-y)*12+g.time.dt.month
  ax.plot(x,g.chen_basin_wwv_m3/1e14,'-o',c=BLACK,lw=2,ms=3);ax.axhline(0,c='.5',lw=.7);ax.axvline(13,c=CORAL,ls='--',lw=.8)
  ax.set(xlim=(.8,17.2),ylim=common_limits(bvals),ylabel='Basin WWV26′ (10¹⁴ m³)',xticks=[1,4,7,10,13,17],xticklabels=['Jan','Apr','Jul','Oct','Jan +1','May +1']);ax.set_title(f'({chr(97+col)})  {y}/{str(y+1)[-2:]}: Chen basin reserve',loc='left')
  ax.text(.035,.06,'9°S–9°N, 120°E–80°W',transform=ax.transAxes,fontsize=9,color='.35')
  ax=axes[1,col];volume_arrival(ax,d,y,common_limits(av,.20));ax.set_title(f'({chr(99+col)})  Regional arrival: Jan–Jun {y}',loc='left')
  if col==0:ax.legend(loc='upper left',ncol=2)
  ax=axes[2,col];volume_fate(ax,e,y,common_limits(fates,.22));ax.set_title(f'({chr(101+col)})  East-box discharge: Jan–May {y+1}',loc='left')
  ax=axes[3,col];g=t.loc[t.time.dt.year.eq(y+1)&t.time.dt.month.le(5)&t.gate.eq('east_north')&t.geometry.eq('instantaneous_sigma26')]
  for c,label,color,ls in [('vbar_Tprime_pw',r'$\overline{v}\,T^\prime$',BLUE,'-'),('vprime_Tbar_pw',r'$v^\prime\,\overline{T}$',CORAL,'-'),('linear_sum_pw','Two-term sum',BLACK,'--')]:ax.plot(g.time.dt.month,g[c],ls=ls,marker='o',ms=3,lw=1.8,color=color,label=label)
  setmonth(ax,1,5);ax.set_ylim(common_limits(tv,.18));ax.set_ylabel('Northward heat contribution (PW)');ax.set_title(f'({chr(103+col)})  5°N two-term heat diagnostic: {y+1}',loc='left')
  if col==0:ax.legend(ncol=3,loc='upper right')
 fig.suptitle('Warm-Water Recharge and Discharge: Chen (2015) Definition',fontsize=19,fontweight='bold',y=.985)
 fig.text(.5,.953,'SODA3.15.2 | Instantaneous σθ = 26 surface | Common 1980–2022 monthly climatology',ha='center',color='#9B4335',fontsize=11)
 fig.text(.085,.024,'(a–b) Chen basin volume; (c–h) Maryland regional extension: 10°S–5°N, west / central / east = 160°E–180° / 180°–140°W / 140°W–80°W.\n'
 'Cumulative windows join monthly centers: Jan 15–Jun 15 (arrival), next Jan 15–May 15 (discharge). Anomalies are unfiltered and not detrended.\n'
 '(e–f) Negative loss denotes anomalous input. Unresolved = storage change minus horizontal convergence; it is not identified as surface heat loss.\n'
 '(g–h) Only the requested two heat terms are retained, on the moving warm-layer section; T reference = 0°C. Their sum is not the complete flux anomaly.\n'
 'Volume (m³) and heat (PW/ZJ) are separate diagnostics. Coastal wet masks and partial layers are retained; no artificial horizontal mass closure is imposed.',fontsize=8.6,linespacing=1.55)
 save(fig,'Chen2015_WWV26_2015_2023')

def stcfig(d):
 fig,axes=plt.subplots(3,2,figsize=(14,11.4));fig.subplots_adjust(left=.08,right=.98,top=.885,bottom=.15,hspace=.58,wspace=.25)
 for col,y in enumerate([2015,2023]):
  g=d.loc[d.time.between(f'{y}-01-01',f'{y+1}-05-31')];x=(g.time.dt.year-y)*12+g.time.dt.month
  for row,hemi,sgn in [(0,'north',-1),(1,'south',1)]:
   ax=axes[row,col]
   for key,label,c,ls in [(f'chen_{hemi}_interior_q50_sv','Interior: 50 m–σ26',BLUE,'-'),(f'chen_{hemi}_interior_q_sv','Interior + surface: 0–σ26',CORAL,'-'),(f'chen_{hemi}_wbc_q_sv','Western boundary: 0–σ26',GREY,'--')]:ax.plot(x,g[key]*sgn,lw=1.6,c=c,ls=ls,label=label)
   ax.set_ylabel('Equatorward transport anomaly (Sv)');ax.set_title(f'({chr(97+row*2+col)})  {y}: {"9°N" if hemi=="north" else "9°S"}',loc='left')
   if col==0:ax.legend(ncol=1,loc='upper left',fontsize=8)
  ax=axes[2,col];interior=g.chen_south_interior_q50_sv-g.chen_north_interior_q50_sv;total=g.chen_south_interior_q_sv-g.chen_north_interior_q_sv;wbc=g.chen_south_wbc_q_sv-g.chen_north_wbc_q_sv
  ax.plot(x,interior,c=BLUE,lw=1.7,label='Interior convergence');ax.plot(x,total+wbc,c=BLACK,lw=1.9,label='Total STC + WBC convergence');ax.plot(x,wbc,c=GREY,ls='--',lw=1.4,label='WBC convergence');ax.set_ylabel('Volume convergence anomaly (Sv)');ax.set_title(f'({chr(101+col)})  Convergence during {y}/{str(y+1)[-2:]}',loc='left')
  if col==0:ax.legend(loc='upper left',fontsize=8)
  for ax in axes[:,col]:ax.axhline(0,c='.5',lw=.7);ax.axvline(13,c=CORAL,ls='--',lw=.8);ax.set(xlim=(.8,17.2),xticks=[1,4,7,10,13,17],xticklabels=['Jan','Apr','Jul','Oct','Jan +1','May +1'])
 for row in range(3):
  lim=common_limits([v for ax in axes[row] for l in ax.lines[:3] for v in l.get_ydata()],.2)
  for ax in axes[row]:ax.set_ylim(lim)
 fig.suptitle('Chen Geometry: Interior and Western Boundary Transports',fontsize=19,fontweight='bold',y=.97)
 fig.text(.5,.925,'SODA3 extension | Same monthly baseline as WWV26 | Positive toward the equator',ha='center',color='#9B4335',fontsize=11)
 fig.text(.08,.035,'Interior longitude ranges: 9°N, 140°E–80°W; 9°S, 160°E–80°W. Western boundary segments start at the Pacific-facing coastal wet mask.\n'
 'Surface-to-σ26 transport includes the upper 50 m; it is distinct from the interior 50 m–σ26 transport. No 2–8 year bandpass is applied to these event curves.\n'
 'Western marginal-sea/ITF segments and the 120°E edge are not folded into the Pacific western boundary current. Full rectangular-box accounting is saved separately.\n'
 'Transport convergence is a diagnostic; it is not forced to equal the WWV26 tendency in this assimilating, regridded product.',fontsize=8.7,linespacing=1.6)
 save(fig,'Chen2015_STC_2015_2023')

def hovfig():
 cl=[]
 for y in range(1980,2023):cl.append(np.load(OUT/f'd26_{y}.npz')['d26'])
 stack=np.stack(cl);n=np.isfinite(stack).sum(axis=0);clim=np.divide(np.nansum(stack,axis=0),n,out=np.full_like(stack[0],np.nan),where=n>0);p=np.load(OUT/'d26_2016.npz');lat,lon=p['lat'],p['lon'];sel=(lat>-9)&(lat<9);xs=(lon>120)&(lon<280)
 area=np.cos(np.deg2rad(lat[sel]));fields=[]
 for year in [2015,2023]:
  arr=np.concatenate([np.load(OUT/f'd26_{year}.npz')['d26']-clim,(np.load(OUT/f'd26_{year+1}.npz')['d26']-clim)[:5]],axis=0)[:,sel][:,:,xs]
  mean=np.nansum(arr*area[None,:,None],axis=1)/np.sum(np.isfinite(arr)*area[None,:,None],axis=1);fields.append(mean)
 lim=float(np.ceil(max(np.nanmax(abs(a)) for a in fields)/10)*10)
 fig,axes=plt.subplots(1,2,figsize=(13.8,6.7),sharex=True,sharey=True);fig.subplots_adjust(left=.075,right=.89,top=.84,bottom=.2,wspace=.17)
 for ax,y,a in zip(axes,[2015,2023],fields):
  m=ax.pcolormesh(lon[xs],np.arange(1,18),a,shading='nearest',cmap='RdBu_r',vmin=-lim,vmax=lim);ax.set_ylim(17.5,.5);ax.axhline(12.5,c='.3',ls='--',lw=.8);ax.axvline(180,c='.4',ls=':',lw=.8);ax.axvline(220,c='.4',ls=':',lw=.8);ax.set(xticks=[120,160,180,220,260,280],xticklabels=['120°E','160°E','180°','140°W','100°W','80°W'],yticks=[1,4,7,10,13,17],yticklabels=['Jan','Apr','Jul','Oct','Jan +1','May +1']);ax.set_title(f'{y}/{str(y+1)[-2:]}',pad=12)
 cax=fig.add_axes([.915,.25,.018,.53]);fig.colorbar(m,cax=cax,label='9°S–9°N mean D26 anomaly (m)')
 fig.suptitle('Longitude–Time Evolution of the Warm-Water Layer',fontsize=19,fontweight='bold',y=.96)
 fig.text(.5,.895,'Instantaneous σθ = 26 depth | Shared 1980–2022 monthly reference and color scale',ha='center',fontsize=11,color='#9B4335')
 fig.text(.075,.05,'Latitude average uses wet-cell area weights. D26 includes bottom-limited warm columns in coastal and marginal seas.\n'
 'This is warm-layer thickness, not temperature anomaly or OHC. The transport and basin-volume calculations retain the full latitude–longitude fields.',fontsize=9,linespacing=1.6)
 save(fig,'Chen2015_D26_longitude_time_2015_2023')

def bridge(d,e):
 # Keep the already verified forecast rows; replace the two physical rows and their units/captions.
 import plot_2023_forecast_maryland_bridge as old
 data=old.load();capture=[];old.save=lambda fig,*args,**kwargs:capture.append(fig)
 old.bridge_figure(data);fig=capture[0];axes=np.asarray(fig.axes).reshape(5,2)
 vals=[];fates=[]
 for y in [2015,2023]:
  g=d.loc[d.time.dt.year.eq(y)&d.time.dt.month.le(6)];vals.extend(g[[b+'_wwv_m3' for b in ['west','central','east']]].to_numpy().ravel()/1e14);vals.extend(cumulative_trapezoid(g.east_west_q_sv,(g.time-g.time.iloc[0]).dt.total_seconds(),initial=0)/1e8)
  r=e.loc[e.event_year.eq(y)&e.phase.eq('decay')&e.box.eq('east')&e.baseline_method.eq('monthly_mean')].iloc[0];fates.extend(-r[['west_in_1e14m3','north_in_1e14m3','south_in_1e14m3','east_in_1e14m3','unresolved_1e14m3','storage_change_1e14m3']].to_numpy(float))
 for j,y in enumerate([2015,2023]):
  ax=axes[3,j];ax.clear();volume_arrival(ax,d,y,common_limits(vals,.2));ax.set_title(f'({chr(103+j)})  σ26 regional reserve and arrival',loc='left',pad=9)
  if j==0:ax.legend(loc='upper left',ncol=2,fontsize=8)
  ax=axes[4,j];ax.clear();volume_fate(ax,e,y,common_limits(fates,.22));ax.set_title(f'({chr(105+j)})  Volume fate: Jan–May {y+1}',loc='left',pad=9)
 for txt in list(fig.texts):txt.remove()
 fig.suptitle('From ENSO Forecasts to Warm-Water Fate: 2015 and 2023',fontsize=19,fontweight='bold',y=.982)
 fig.text(.5,.953,'Forecasts retained | Physical rows recomputed using the Chen σθ = 26 warm-layer definition',ha='center',fontsize=11,color='#9B4335')
 fig.text(.075,.017,'(a–d) Original April forecast comparison; all Feb–Jun starts are scored elsewhere. Fit 2002–2024 includes both events; IRI shading is a four-model range.\n'
 '(e–f) PMM standardized on 2002–2024; ERA5 SST-adjusted wind residual referenced to 1982–2014. These retain their original definitions.\n'
 '(g–j) SODA3.15.2 regional extension: 10°S–5°N, 160°E–80°W; same three longitude boxes. Storage and fluxes use the actual monthly σ26 surface.\n'
 'Unified physical baseline: 1980–2022 calendar-month mean, no detrending/filtering. Integrals: Jan 15–Jun 15, next Jan 15–May 15.\n'
 'Unresolved volume includes unmeasured cross-isopycnal transformation, assimilation and discretization; it is not labelled as surface heat loss.\n'
 'The basin WWV26 / ±9° STC results and the two heat-transport contributions are provided in separate companion figures.\n'
 'RO still uses its original mean-D20 state; replacing the physical diagnostics does not refit the forecast model.',fontsize=8.5,linespacing=1.5)
 save(fig,'Maryland_forecast_WWV26_bridge_2015_2023')

def main():
 d,e,t=getdata();mainfig(d,e,t);stcfig(d);hovfig();bridge(d,e)
 print('Rendered four PNG/SVG figure pairs',OUT)
if __name__=='__main__':main()
