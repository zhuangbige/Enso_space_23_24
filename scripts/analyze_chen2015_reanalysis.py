#!/usr/bin/env python3
"""Chen2015 WWV26 + regional extension, common monthly baseline and windows.
No enforced horizontal volume balance. Two-term heat diagnostics stay separate.
"""
from pathlib import Path
import json,hashlib,sys,warnings
import numpy as np,pandas as pd,xarray as xr,gsw
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/raw/chen2015_reanalysis_20261014';OUT=ROOT/'outputs/research_2026/chen2015_reanalysis_20261014';OUT.mkdir(parents=True,exist_ok=True)
R=6371000.;RHO=1025.;CP=3990.;BASE=(1980,2022)
BOXES={'chen_basin':(120,280,-9,9),'west':(160,180,-10,5),'central':(180,220,-10,5),'east':(220,280,-10,5)}
EVENTS=[1982,1986,1991,1994,1997,2002,2004,2006,2009,2015,2018,2019,2023]
QA={}

def load_inputs(year):
 a=dict(np.load(RAW/f'soda3_sigma26_inputs_{year}.npz'))
 e=dict(np.load(RAW/f'soda3_deep_west_{year}.npz'))
 last_sigma=sigma(a['temp'][:,-1:],a['salt'][:,-1:],a['depth'][-1:],a['lat_t'],a['lon_t'])[:,0]
 extended=(a['lat_t'][:,None]>=e['lat_t'].min()-1e-5)&(a['lon_t'][None,:]>=e['lon_t'].min()-1e-5)&(a['lon_t'][None,:]<=e['lon_t'].max()+1e-5)
 if np.any(np.isfinite(last_sigma)&(last_sigma<26)&~extended):raise ValueError(f'{year}: deep density extension insufficient outside west region')
 for key in ['temp','salt','u','v']:
  tag='u' if key in ['u','v'] else 't'
  extra=np.full((12,26,a[key].shape[2],a[key].shape[3]),np.nan,dtype='float32')
  iy=np.array([int(np.argmin(abs(a['lat_'+tag]-v))) for v in e['lat_'+tag]])
  ix=np.array([int(np.argmin(abs(a['lon_'+tag]-v))) for v in e['lon_'+tag]])
  assert np.allclose(a['lat_'+tag][iy],e['lat_'+tag]) and np.allclose(a['lon_'+tag][ix],e['lon_'+tag])
  extra[:,:,iy[:,None],ix]=e[key]
  a[key]=np.concatenate([a[key],extra],axis=1)
 a['depth']=np.r_[a['depth'],e['depth']]
 ref=json.loads((RAW/'metadata_2024.json').read_text())['coords']
 np.testing.assert_allclose(a['depth'],ref['st_ocean'],rtol=0,atol=1e-8)
 canonical=np.array(ref['sw_ocean'])
 np.testing.assert_allclose(canonical[:-1],.5*(a['depth'][:-1]+a['depth'][1:]),rtol=0,atol=.0003)
 if not np.all(np.r_[0.,canonical[:-1]]<a['depth']) or not np.all(a['depth']<canonical):raise ValueError('Layer centers are not inside layer interfaces')
 a['layer_bottom']=canonical
 return a

def sigma(theta,salt,depth,lat,lon):
 # inputs time,z,y,x or time,z,x with broadcast-ready lat/lon.
 p=gsw.p_from_z(-np.asarray(depth)[None,:,None,None],np.asarray(lat)[None,None,:,None])
 sa=gsw.SA_from_SP(salt,p,np.asarray(lon)[None,None,None,:],np.asarray(lat)[None,None,:,None])
 return gsw.sigma0(sa,gsw.CT_from_pt(sa,theta))

def d26(s,depth,bottom):
 finite=np.isfinite(s);wet=finite[:,0]
 cross=(s[:,:-1]<26)&(s[:,1:]>=26)
 found=cross.any(axis=1);idx=cross.argmax(axis=1)
 lo=np.take_along_axis(s,idx[:,None],1)[:,0];hi=np.take_along_axis(s,idx[:,None]+1,1)[:,0]
 with np.errstate(invalid='ignore',divide='ignore'):
  z=depth[idx]+(26-lo)/(hi-lo)*(depth[idx+1]-depth[idx])
 surface=wet&(s[:,0]>=26)
 last=np.maximum(finite.sum(axis=1)-1,0)
 # Only true shelf columns ending before the downloaded bottom get bottom cap.
 shelf=wet&~found&~surface&(last<len(depth)-1)
 unresolved=wet&~found&~surface&~shelf
 z=np.where(found,z,np.nan);z=np.where(surface,0,z);z=np.where(shelf,bottom[last],z)
 if unresolved.any():raise ValueError(f'D26 unresolved at download bottom: {unresolved.sum()}')
 # Detect internal vertical holes, not a simple bottom land mask.
 interior_holes=finite[:,1:]&~finite[:,:-1]
 if interior_holes.any():raise ValueError('Noncontiguous vertical wet mask')
 info={'wet_profiles':int(wet.sum()),'shelf_capped_profiles':int(shelf.sum()),'multiple_crossings':int((cross.sum(axis=1)>1).sum()),'surface_outcrop':int(surface.sum()),'unresolved':int(unresolved.sum()),'min_m':float(np.nanmin(z)),'max_m':float(np.nanmax(z))}
 return z,info,shelf

def weights(z,bottom,start=0):
 top=np.r_[0,bottom[:-1]]
 shape=(1,len(bottom))+ (1,)*(z.ndim-1)
 w=np.maximum(0,np.minimum(bottom.reshape(shape),z[:,None])-np.maximum(top.reshape(shape),start))
 w=np.nan_to_num(w,nan=0)
 assert np.allclose(w.sum(axis=1),np.nan_to_num(np.maximum(z-start,0)),rtol=1e-12,atol=1e-8)
 return w

def select(x,lo,hi):return (x>lo)&(x<hi)
def avg(a,b):
 # Both sides must be available at an open face; a coastal masked face is closed.
 return .5*(a+b)

def section(a,axis,boundary,lo,hi):
 yt,xt,yu,xu=[a[k] for k in ['lat_t','lon_t','lat_u','lon_u']]
 if axis=='v':
  j=np.flatnonzero(np.isclose(yu,boundary))[0];j0=np.flatnonzero(yt<boundary)[-1];j1=j0+1
  sel=select(xt,lo,hi);x=xt[sel];ix=np.array([np.argmin(abs(xu-(v-.25))) for v in x])
  out={k:avg(a[k][:,:,j0,sel],a[k][:,:,j1,sel]) for k in ['temp','salt']}
  out['flow']=avg(a['v'][:,:,j,ix],a['v'][:,:,j,ix+1]);out['lat']=np.full(len(x),boundary);out['lon']=x
  out['width']=np.full(len(x),R*np.cos(np.deg2rad(boundary))*np.deg2rad(.5))
 else:
  j=np.flatnonzero(np.isclose(xu,boundary))[0];j0=np.flatnonzero(xt<boundary)[-1];j1=j0+1
  sel=select(yt,lo,hi);y=yt[sel];iy=np.array([np.argmin(abs(yu-(v-.25))) for v in y])
  out={k:avg(a[k][:,:,sel,j0],a[k][:,:,sel,j1]) for k in ['temp','salt']}
  out['flow']=avg(a['u'][:,:,iy,j],a['u'][:,:,iy+1,j]);out['lat']=y;out['lon']=np.full(len(y),boundary)
  out['width']=np.full(len(y),R*np.deg2rad(.5))
 return out

def section_density(a,z):
 p=gsw.p_from_z(-z[None,:,None],a['lat'][None,None,:]);sa=gsw.SA_from_SP(a['salt'],p,a['lon'][None,None,:],a['lat'][None,None,:])
 return gsw.sigma0(sa,gsw.CT_from_pt(sa,a['temp']))

def all_gates(a):
 gates={}
 # Full north/south segments are explicit, including marginal-sea segments.
 for name,lat in [('chen_north',9),('chen_south',-9)]:
  gates[name]=section(a,'v',lat,120,280)
 for name,lat,west in [('chen_north_interior',9,140),('chen_south_interior',-9,160)]:
  gates[name]=section(a,'v',lat,west,280)
 for hemi,lat,edge in [('north',9,140),('south',-9,160)]:
  full=gates['chen_'+hemi]
  wet=np.isfinite(full['temp'][:,0]).all(axis=0)&np.isfinite(full['flow'][:,0]).all(axis=0)
  dry=full['lon'][(~wet)&(full['lon']<edge)]
  coast=float(dry.max()+.25) if len(dry) else 120.
  gates['chen_'+hemi+'_wbc']=section(a,'v',lat,coast,edge)
 gates['chen_itf']=section(a,'v',-9,120,140)
 for box,(west,east,south,north) in BOXES.items():
  for face,b,lo,hi,axis in [('west',west,south,north,'u'),('east',east,south,north,'u'),('south',south,west,east,'v'),('north',north,west,east,'v')]:
   key=f'{box}_{face}'
   if key not in gates:gates[key]=section(a,axis,b,lo,hi)
 return gates

def integrate_gate(g,depth,bottom):
 ss=section_density(g,depth)
 # A transport face is open only where both tracers and velocity are wet.
 # Tracer interpolation alone must not create flow through the coastal seabed.
 ss=np.where(np.isfinite(g['flow']),ss,np.nan)
 z,info,shelf=d26(ss,depth,bottom);w=weights(z,bottom)*g['width'][None,None,:]
 active=w>0;missing=active&~np.isfinite(g['flow'])
 info['missing_velocity_active_area_fraction']=float(w[missing].sum()/w.sum()) if w.sum() else 0.
 if info['missing_velocity_active_area_fraction']>0.001:raise ValueError(info)
 q=np.sum(np.where(np.isfinite(g['flow']),g['flow'],0)*w,axis=(1,2))/1e6
 interior=np.sum(np.nan_to_num(g['flow'])*weights(z,bottom,50)*g['width'][None,None,:],axis=(1,2))/1e6
 return q,interior,z,w,info

def year_diagnostics(year):
 file=RAW/f'soda3_sigma26_inputs_{year}.npz';a=load_inputs(year);z=a['depth'];bot=a['layer_bottom']
 sd=sigma(a['temp'],a['salt'],z,a['lat_t'],a['lon_t']);interface,info,shelf=d26(sd,z,bot)
 lat,lon=a['lat_t'],a['lon_t'];area=R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat+.25))-np.sin(np.deg2rad(lat-.25)))[:,None]*np.ones((1,len(lon)))
 data={'time':pd.to_datetime([f'{year}-{m:02d}-15' for m in range(1,13)])};sections=all_gates(a)
 for box,(west,east,south,north) in BOXES.items():
  mask=select(lat,south,north)[:,None]&select(lon,west,east)[None,:];ar=area*mask
  data[box+'_wwv_m3']=np.nansum(interface*ar,axis=(1,2));data[box+'_shelf_volume_m3']=np.nansum(np.where(shelf,interface,0)*ar,axis=(1,2))
  data[box+'_surface_pw']=np.nansum(a['net_heating']*ar,axis=(1,2))/1e15
 for name,g in sections.items():
  q,qi,zg,w,ig=integrate_gate(g,z,bot);data[name+'_q_sv']=q;data[name+'_q50_sv']=qi
  info[name]=ig
 for left,right in [('west','central'),('central','east')]:
  np.testing.assert_allclose(data[left+'_east_q_sv'],data[right+'_west_q_sv'],rtol=0,atol=1e-10)
 # Store full D26 for climatology, longitudinal structure and land masks.
 np.savez_compressed(OUT/f'd26_{year}.npz',d26=interface.astype('float32'),lat=lat,lon=lon,shelf=shelf)
 return pd.DataFrame(data),info

def monthly_anomalies(df,detrend=False):
 out=df[['time']].copy();years=df.time.dt.year.to_numpy();months=df.time.dt.month.to_numpy();baseline=(years>=BASE[0])&(years<=BASE[1]);metrics=[c for c in df if c!='time']
 for c in metrics:
  y=df[c].to_numpy();expected=np.full(len(df),np.nan)
  for month in range(1,13):
   train=baseline&(months==month);test=months==month
   if train.sum()!=43:raise ValueError('Incomplete baseline')
   if detrend:
    b=np.polyfit(years[train]-2001,y[train],1);expected[test]=np.polyval(b,years[test]-2001)
   else:expected[test]=np.mean(y[train])
  out[c]=y-expected
 return out

def make_climatology():
 p=RAW/'field_climatology_1980_2022_complete_wet_mask.npz'
 if p.exists():return dict(np.load(p))
 sums={};counts={};coords={}
 for year in range(1980,2023):
  a=load_inputs(year)
  if not coords:coords={k:a[k] for k in ['lat_t','lon_t','lat_u','lon_u','depth','layer_bottom']}
  for key in ['temp','salt','u','v']:
   if key not in sums:sums[key]=np.zeros_like(a[key],dtype='float64');counts[key]=np.zeros_like(a[key],dtype='int16')
   valid=np.isfinite(a[key]);sums[key]+=np.where(valid,a[key],0);counts[key]+=valid
 means={k:np.divide(sums[k],counts[k],out=np.full_like(sums[k],np.nan),where=counts[k]==43).astype('float32') for k in sums}
 QA['clim_min_wet_count']={k:int(counts[k][counts[k]>0].min()) for k in sums}
 QA['clim_non43_wet_cells']={k:int(((counts[k]>0)&(counts[k]<43)).sum()) for k in sums}
 np.savez_compressed(p,**means,**coords);return {**means,**coords}

def two_terms(clim):
 cg=all_gates(clim);rows=[]
 for year in sorted(set(EVENTS+[y+1 for y in EVENTS])):
  if year>2024:continue
  a=load_inputs(year);ag=all_gates(a)
  for name,g in ag.items():
   b=cg[name];q,qi,z,w,info=integrate_gate(g,a['depth'],a['layer_bottom'])
   _,_,zc,wc,_=integrate_gate(b,a['depth'],a['layer_bottom'])
   t1=b['flow']*(g['temp']-b['temp']);t2=(g['flow']-b['flow'])*b['temp']
   for geometry,ww in [('instantaneous_sigma26',w),('climatological_sigma26',wc)]:
    valid=np.isfinite(t1)&np.isfinite(t2)
    fraction=np.sum(np.where(valid,ww,0),axis=(1,2))/np.sum(ww,axis=(1,2))
    values=[np.sum(np.where(valid,t,0)*ww,axis=(1,2))*RHO*CP/1e15 for t in [t1,t2]]
    for m in range(12):rows.append({'time':pd.Timestamp(year,m+1,15),'gate':name,'geometry':geometry,'vbar_Tprime_pw':values[0][m],'vprime_Tbar_pw':values[1][m],'linear_sum_pw':values[0][m]+values[1][m],'included_section_area_fraction':fraction[m]})
 return pd.DataFrame(rows)

def summaries(raw,anom,trend,two):
 rows=[]
 for label,df in [('monthly_mean',anom),('monthly_linear_trend',trend)]:
  for event in EVENTS:
   for phase,year,m0,m1 in [('arrival',event,1,6),('post_arrival',event,7,12),('decay',event+1,1,5)]:
    d=df.loc[df.time.dt.year.eq(year)&df.time.dt.month.between(m0,m1)].sort_values('time')
    sec=(d.time-d.time.iloc[0]).dt.total_seconds().to_numpy()
    for box in BOXES:
     r={'event_year':event,'phase':phase,'box':box,'baseline_method':label,'window_start':str(d.time.iloc[0].date()),'window_end':str(d.time.iloc[-1].date()),'elapsed_days':float(sec[-1]/86400)}
     r['storage_change_1e14m3']=(d[box+'_wwv_m3'].iloc[-1]-d[box+'_wwv_m3'].iloc[0])/1e14
     net=0.
     for face,sign in [('west',1),('east',-1),('south',1),('north',-1)]:
      q=np.trapezoid(d[box+'_'+face+'_q_sv'],sec)/1e8*sign;r[face+'_in_1e14m3']=q;net+=q
     r['horizontal_in_1e14m3']=net;r['unresolved_1e14m3']=r['storage_change_1e14m3']-net
     r['surface_loss_zj']=-np.trapezoid(d[box+'_surface_pw'],sec)/1e6
     rows.append(r)
 summary=pd.DataFrame(rows);summary.to_csv(OUT/'event_volume_budget.csv',index=False)
 rows=[]
 for event in EVENTS:
  for phase,year,m0,m1 in [('arrival',event,1,6),('decay',event+1,1,5)]:
   for (gate,geometry),d in two.loc[two.time.dt.year.eq(year)&two.time.dt.month.between(m0,m1)].groupby(['gate','geometry']):
    d=d.sort_values('time');sec=(d.time-d.time.iloc[0]).dt.total_seconds().to_numpy();r={'event_year':event,'phase':phase,'gate':gate,'geometry':geometry,'window_start':str(d.time.iloc[0].date()),'window_end':str(d.time.iloc[-1].date())}
    r['minimum_section_coverage']=float(d.included_section_area_fraction.min());r['complete_section']=bool(r['minimum_section_coverage']>=.999999)
    for col in ['vbar_Tprime_pw','vprime_Tbar_pw','linear_sum_pw']:r[col.replace('_pw','_zj')]=np.trapezoid(d[col],sec)/1e6
    rows.append(r)
 pd.DataFrame(rows).to_csv(OUT/'event_two_term_heat.csv',index=False)
 return summary

def main():
 missing=[y for y in range(1980,2025) if not (RAW/f'soda3_sigma26_inputs_{y}.npz').exists() or not (RAW/f'soda3_deep_west_{y}.npz').exists()]
 if missing:raise FileNotFoundError(f'Missing years: {missing}')
 pieces=[]
 for year in range(1980,2025):
  p=OUT/f'monthly_raw_{year}.csv';q=OUT/f'qa_{year}.json'
  if p.exists() and q.exists():d=pd.read_csv(p,parse_dates=['time']);info=json.loads(q.read_text())
  else:d,info=year_diagnostics(year);d.to_csv(p,index=False);q.write_text(json.dumps(info,indent=2))
  QA[str(year)]=info;pieces.append(d);print('WWV/volume',year,flush=True)
 raw=pd.concat(pieces,ignore_index=True);anom=monthly_anomalies(raw);trend=monthly_anomalies(raw,True)
 raw.to_csv(OUT/'monthly_absolute.csv',index=False);anom.to_csv(OUT/'monthly_anomalies.csv',index=False);trend.to_csv(OUT/'monthly_anomalies_trend_sensitivity.csv',index=False)
 clim=make_climatology();QA['two_term_field_climatology_required_years']=43;two=two_terms(clim);two.to_csv(OUT/'two_term_heat_monthly.csv',index=False)
 summaries(raw,anom,trend,two)
 # Numerical QC. Anomalies sum to zero within every baseline calendar month.
 hist=anom.loc[anom.time.dt.year.le(2022)];res=hist.groupby(hist.time.dt.month).mean(numeric_only=True)
 QA['baseline_max_relative_zero_error']=float((abs(res).max()/raw.drop(columns='time').abs().max().replace(0,np.nan)).max())
 QA['source_files']=[{'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(list(RAW.glob('soda3_sigma26_inputs_*.npz'))+list(RAW.glob('soda3_deep_west_*.npz')))]
 (OUT/'numerical_QA.json').write_text(json.dumps(QA,indent=2));print('DONE',OUT,flush=True)
if __name__=='__main__':main()
