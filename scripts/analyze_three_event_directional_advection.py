"""Bounded zonal/meridional temperature-advection extension, using frozen arrays."""
from pathlib import Path
import gc
import hashlib
import json
import numpy as np
import pandas as pd
import xarray as xr

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/three_event_directional_advection_20261015'
DYN=ROOT/'outputs/research_2026/three_event_summer_current_dynamics_20261015'
CACHE=ROOT/'outputs/research_2026/three_event_temperature_tendency_20261015/local_fields_cache.npz'
DATES=pd.date_range('1982-01-01','2024-12-01',freq='MS')
MI=DATES.month.to_numpy()-1
EVENTS=[1997,2015,2023]
DEPTHS=[30,50,75]
BGS=['mean','detrend']
SEASONS={'AMJ':[4,5,6],'JAS':[7,8,9]}
R=6371000.;MONTH=365.25/12*86400
COMPONENTS=[f'{d}_{c}' for d in ['x','y'] for c in ['temperature','velocity','nonlinear','total']]


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()


def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')


def climatology(a):return np.stack([a[MI==m].mean(0) for m in range(12)])
def anomaly(a):return a-climatology(a)[MI]


def detrend(a):
    x=np.arange(len(DATES),dtype=float);x-=x.mean()
    return a-x.reshape((-1,)+(1,)*(a.ndim-1))*np.tensordot(x,a,axes=(0,0))/(x@x)


def gradient(a,lat,lon):
    cs=np.cos(np.deg2rad(lat)).reshape((1,)*(a.ndim-2)+(len(lat),1))
    return (np.gradient(a,np.deg2rad(lon),axis=-1)/(R*cs),
            np.gradient(a,np.deg2rad(lat),axis=-2)/R)


def save_cases(df,prefix):
    df.to_csv(OUT/f'{prefix}_monthly.csv',index=False)
    case=df[df.time.dt.year.isin(EVENTS)].copy();case['event']=case.time.dt.year
    case.to_csv(OUT/f'{prefix}_case_monthly.csv',index=False)
    keys=[c for c in ['event','depth_m','background','region'] if c in case]
    numeric=[c for c in case if c not in keys+['time']]
    seas=[]
    for s,months in SEASONS.items():
        q=case[case.time.dt.month.isin(months)].groupby(keys)[numeric].mean().reset_index()
        q['season']=s;seas.append(q)
    season=pd.concat(seas,ignore_index=True)
    season.to_csv(OUT/f'{prefix}_case_seasons.csv',index=False)
    pair=[]
    keys=[c for c in ['depth_m','background','season','region'] if c in season]
    for control in EVENTS[:2]:
        a=season[season.event.eq(2023)].set_index(keys)[numeric]
        b=season[season.event.eq(control)].set_index(keys)[numeric]
        d=a-b;d['control']=control;pair.append(d.reset_index())
    pd.concat(pair,ignore_index=True).to_csv(OUT/f'{prefix}_pair_seasons.csv',index=False)
    return season


def main():
    OUT.mkdir(exist_ok=True)
    protocol='''经纬向平流补充诊断：预先固定的范围与方法
目标：在现有三个事件中量化完整经、纬向温度平流差异，并判断经向线性流速项、温度结构项和非线性交互及空间位置。
只复用local_fields_cache及原动量诊断的共同海洋掩膜；不新增数据、事件、动量方程、边界热输送或预测变量。
区域Niño3.4，主0—50m，30/75m敏感性。1982—2024全部43年同月背景，目标年份纳入。去趋势仅对已定义的过程时间序列进行。
对d=x,y，A_d=异常[-w_d ∂dT]。三项为B_d=-w̄_d∂dT′，V_d=-w′_d∂dT̄，N_d=异常[-w′_d∂dT′]。必须逐格先乘再按有效层厚与面积积分。
N_d需减去自身同月平均，不能直接将未中心化的异常乘积当成非线性异常。B+V+N=A_d；A_x+A_y复现原水平总平流。交互项单列，不任意分配给流速或温度，也不作因果百分比。
固定南北带：5S—2S、2S—2N、2N—5N；东西界140W，组成六块互不重叠的子区。同时保存南北半区。区域贡献以全Niño3.4有效体积归一化，保证子区贡献之和等于全区，不用子区均值直接相加。
展示发展年1—12月，比较AMJ/JAS及2023分别减1997、2015；全部六设置保留，不将月份/设置作为独立样本。
使用原生0.5度格点及外围一格算梯度，共同掩膜不变，缺测不填零。标准月=365.25/12天。
核验：常量和线性解析场、独立中心差分、全43年旧五项/水平总量重现、三项相加、经纬向相加、分区相加、地图积分、输入哈希。
交付：独立结果目录、输入哈希、月季表、地图源场、中文报告；仅更新现有M4平流面板、图注及当前汇报正文，保留原诊断和其余六图。完成即结束。
'''
    path=OUT/'protocol_before_run.txt'
    if not path.exists():path.write_text(protocol)
    inputs=[CACHE,DYN/'grid_support.npz',DYN/'local_monthly.csv',DYN/'case_seasons.csv']
    frozen={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    dump('input_manifest.json',frozen)
    print('Input hashes and fixed protocol saved.',flush=True)
    with np.load(CACHE) as z:
        lat=np.round(z['lat'],6);lon=np.round(z['lon'],6)
        depth=z['depth'];bottom=z['bottom'];temp=z['temp'].astype(float)
    support=dict(np.load(DYN/'grid_support.npz'))
    wet=support['wet'];area=support['area'];la=lat[1:-1];lo=lon[1:-1]
    assert temp.shape==(516,8,22,102) and np.all(np.diff(lat)>0) and np.all(np.diff(lon)>0)
    for name,a in [('lat',la),('lon',lo),('depth',depth),('bottom',bottom)]:
        np.testing.assert_allclose(a,support[name],rtol=0,atol=0)
    assert wet.shape==(8,20,100) and np.all(area>0)
    expected_area=R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(la+.25))-np.sin(np.deg2rad(la-.25)))[:,None]*np.ones((1,len(lo)))
    np.testing.assert_array_equal(area,expected_area)
    # Analytic gradients and the sign of northward advection.
    yy,xx=np.meshgrid(np.deg2rad(lat),np.deg2rad(lon),indexing='ij')
    gx,gy=gradient(3+2*yy+4*xx,lat,lon)
    np.testing.assert_allclose(gy,2/R,rtol=0,atol=1e-18)
    np.testing.assert_allclose(gx,4/(R*np.cos(yy)),rtol=0,atol=2e-18)
    assert np.all(-.1*gy<0)
    for g in gradient(np.ones_like(xx),lat,lon):np.testing.assert_allclose(g,0,atol=1e-18)
    gradients=gradient(temp,lat,lon);clim_gradients=gradient(climatology(temp),lat,lon)
    cut=lambda a:a[...,1:-1,1:-1]
    independent={}
    for name,g,manual in [('x',gradients[0],(temp[...,1:-1,2:]-temp[...,1:-1,:-2])/(R*np.cos(np.deg2rad(la))[None,None,:,None]*np.deg2rad(1.))),
                         ('y',gradients[1],(temp[...,2:,1:-1]-temp[...,:-2,1:-1])/(R*np.deg2rad(1.)))]:
        independent[name]=float(np.max(np.abs(cut(g)[:,wet]-manual[:,wet])))
        assert independent[name]<1e-17
    del temp,manual,g;gc.collect()
    # All masks are declared before inspecting event results.
    regions={'all':np.ones(area.shape,bool),
             'south':np.broadcast_to((la<0)[:,None],area.shape),
             'north':np.broadcast_to((la>0)[:,None],area.shape)}
    for name,mask in [('S_5_2',la<-2),('EQ_2_2',abs(la)<2),('N_2_5',la>2)]:
        regions[name]=np.broadcast_to(mask[:,None],area.shape)
        for zonal,zmask in [('west',lo<220),('east',lo>220)]:regions[name+'_'+zonal]=mask[:,None]&zmask[None,:]
    partitions=[['south','north'],['S_5_2','EQ_2_2','N_2_5'],[n+'_'+s for n in ['S_5_2','EQ_2_2','N_2_5'] for s in ['west','east']]]
    for partition in partitions:np.testing.assert_array_equal(sum(regions[n].astype(int) for n in partition),np.ones_like(area))
    table={};regional={};maps={};coverage={};volumes=[];component_errors={};map_errors=[]
    for h in DEPTHS:
        dz=np.maximum(0,np.minimum(bottom,h)-np.r_[0,bottom[:-1]])
        w=dz[:,None,None]*area[None]*wet
        coverage[str(h)]=float(w.sum()/(h*area.sum()))
        table[h]={};regional[h]={name:{} for name in regions}
        for name,mask in regions.items():
            frac=(w*mask[None]).sum()/w.sum()
            volumes.append({'depth_m':h,'region':name,'volume_fraction':frac})
    for direction,velocity in [('x','u'),('y','v')]:
        with np.load(CACHE) as z:flow=cut(z[velocity].astype(float))
        grad=cut(gradients[0 if direction=='x' else 1]);gbar=cut(clim_gradients[0 if direction=='x' else 1])[MI]
        fbar=climatology(flow)[MI];fp=flow-fbar;gp=grad-gbar
        fields={direction+'_temperature':-fbar*gp*MONTH,
                direction+'_velocity':-fp*gbar*MONTH,
                direction+'_nonlinear':anomaly(-fp*gp)*MONTH,
                direction+'_total':anomaly(-flow*grad)*MONTH}
        identity=fields[direction+'_temperature']+fields[direction+'_velocity']+fields[direction+'_nonlinear']-fields[direction+'_total']
        component_errors[direction]=float(np.max(abs(identity[:,wet])))
        assert component_errors[direction]<1e-10
        fields.update({velocity+'_anomaly':fp,'T'+direction+'_anomaly':gp*1e6,
                       velocity+'_background':fbar,'T'+direction+'_background':gbar*1e6})
        for key,a in fields.items():
            assert np.isfinite(a[:,wet]).all(),key
            maps[key]=np.full((3,2,3,2,len(la),len(lo)),np.nan)
            for ih,h in enumerate(DEPTHS):
                dz=np.maximum(0,np.minimum(bottom,h)-np.r_[0,bottom[:-1]])
                w=dz[:,None,None]*area[None]*wet
                zweight=dz[:,None,None]*wet;column=zweight.sum(0)
                val=np.sum(np.where(wet,a,0)*w[None],axis=(1,2,3))/w.sum()
                table[h][key]=val
                for name,mask in regions.items():
                    regional[h][name][key]=np.sum(np.where(wet,a,0)*(w*mask[None])[None],axis=(1,2,3))/w.sum()
                spatial=np.divide(np.sum(np.where(wet,a,0)*zweight[None],axis=1),column[None],
                    out=np.full((516,len(la),len(lo)),np.nan),where=column[None]>0)
                for ib,bg in enumerate(BGS):
                    a2=spatial if bg=='mean' else detrend(spatial)
                    v2=val if bg=='mean' else detrend(val)
                    check=np.nansum(a2*(column*area)[None],axis=(1,2))/w.sum()
                    map_errors.append(float(np.max(abs(check-v2))))
                    for ie,e in enumerate(EVENTS):
                        for isea,months in enumerate(SEASONS.values()):
                            use=(DATES.year==e)&DATES.month.isin(months)
                            maps[key][ih,ib,ie,isea]=a2[use].mean(0)
        print(direction,'complete; gridpoint product identity max',component_errors[direction],flush=True)
        del flow,grad,gbar,fbar,fp,gp,fields,identity,a,spatial;gc.collect()
    frames=[];rframes=[];partition_errors=[]
    for h in DEPTHS:
        for bg in BGS:
            data={k:(v if bg=='mean' else detrend(v)) for k,v in table[h].items()}
            data['horizontal_total']=data['x_total']+data['y_total']
            data['nonlinear_hadv']=data['x_nonlinear']+data['y_nonlinear']
            data.update(time=DATES,depth_m=h,background=bg)
            frames.append(pd.DataFrame(data))
            for name in regions:
                rd={k:(v if bg=='mean' else detrend(v)) for k,v in regional[h][name].items()}
                rd['horizontal_total']=rd['x_total']+rd['y_total']
                rd.update(time=DATES,depth_m=h,background=bg,region=name)
                rframes.append(pd.DataFrame(rd))
        for partition in partitions:
            for k in COMPONENTS:
                partition_errors.append(float(np.max(abs(sum(regional[h][r][k] for r in partition)-table[h][k]))))
    df=pd.concat(frames,ignore_index=True)
    rdf=pd.concat(rframes,ignore_index=True)
    old=pd.read_csv(DYN/'local_monthly.csv',parse_dates=['time'])
    keys=['time','depth_m','background']
    joined=df.merge(old,on=keys,suffixes=('_new','_old'),validate='one_to_one')
    comparisons={'x_temperature':'mean_u_Tprime','x_velocity':'u_prime_meanT',
                 'y_temperature':'mean_v_Tprime','y_velocity':'v_prime_meanT',
                 'nonlinear_hadv_new':'nonlinear_hadv_old','horizontal_total_new':'horizontal_total_old'}
    errors={k:float(np.max(abs(joined[k]-joined[v]))) for k,v in comparisons.items()}
    assert max(errors.values())<1e-9,errors
    assert max(partition_errors+map_errors)<1e-9
    save_cases(df,'directional')
    # Only the three cases are retained for regional monthly data, keeping the output compact.
    save_cases(rdf[rdf.time.dt.year.isin(EVENTS)].copy(),'regional')
    pd.DataFrame(volumes).to_csv(OUT/'region_volume_fractions.csv',index=False)
    ds=xr.Dataset({k:(('depth_m','background','event','season','lat','lon'),v) for k,v in maps.items()},
        coords={'depth_m':DEPTHS,'background':BGS,'event':EVENTS,'season':list(SEASONS),'lat':la,'lon':lo})
    for key in maps:
        ds[key].attrs['units']='C per standard month' if key in COMPONENTS else 'C per 1000 km' if key.startswith('T') else 'm s-1'
    ds['area']=(('lat','lon'),area);ds.area.attrs['units']='m2'
    ds['effective_layer_thickness']=(('depth_m','lat','lon'),np.stack([
        (np.maximum(0,np.minimum(bottom,h)-np.r_[0,bottom[:-1]])[:,None,None]*wet).sum(0) for h in DEPTHS]))
    ds.effective_layer_thickness.attrs['units']='m'
    ds.attrs.update(baseline='1982-2024 all 43 years, target events included',
        detrend='Linear trend removed from each defined process time series, not from input fields before products',
        nonlinear='Anomaly of the anomaly-flow times anomaly-temperature-gradient product; monthly mean removed',
        averaging='Native grid products, effective depth overlap and spherical cell area; no smoothing',
        regional_normalization='All regional contributions normalized by whole Nino3.4 valid volume',
        standard_month_seconds=MONTH)
    ds.to_netcdf(OUT/'directional_spatial.nc',engine='h5netcdf',encoding={k:{'zlib':True,'complevel':4} for k in ds.data_vars})
    assert all(sha(ROOT/p)==h for p,h in frozen.items())
    dump('validation.json',{'status':'PASS','rows':len(df),'case_rows':int(df.time.dt.year.isin(EVENTS).sum()),
        'inputs_unchanged':True,'same_common_ocean_mask':True,'coverage':coverage,
        'analytic_tests':['constant gradients','linear spherical gradients','northward-flow sign'],
        'independent_centered_gradient_max_C_m':independent,
        'gridpoint_three_term_identity_max_C_month':component_errors,
        'previous_all_43_year_process_max_C_month':errors,
        'regional_sum_max_C_month':max(partition_errors),'map_integral_max_error':max(map_errors),
        'settings':'30/50/75 m x mean/detrend; not independent samples',
        'interpretation':'Kinematic temperature-advection decomposition, not a v-momentum or causal attribution'})
    (OUT/'reproduce.txt').write_text('OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python -B scripts/analyze_three_event_directional_advection.py\n')
    print('PASS: directional components reproduce all original processes and regional/map integrals.',flush=True)


if __name__=='__main__':main()
