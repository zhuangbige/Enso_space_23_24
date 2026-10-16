"""Data-backed oblique map/section composites for the final paper figures.

The front face is explicitly a latitude-band mean, not a geometric section at
the front-edge latitude. Projection changes display geometry, never field values.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap, LinearSegmentedColormap, Normalize

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'outputs/research_2026'
OUT = BASE/'three_event_scientific_figures_20261015/source_data'
RAW = ROOT/'data/raw/chen2015_reanalysis_20261014'
EVENTS = [1997, 2015, 2023]
CHEN_PAPER = ROOT/'data/raw/literature/chen2015_20261014/Chen_etal_2015_STC_recharge_discharge.pdf'


def jfm_color_scales():
    """Two signed, discrete scales; every event uses the same physical intervals."""
    # A white zero interval separates shallower and deeper isopycnal anomalies.
    top_levels = np.r_[np.arange(-50, 0, 5), np.arange(5, 51, 5)]
    top_colors = [
        '#43246f', '#434ca0', '#2c6eae', '#177cae', '#1498c1',
        '#25b0d3', '#5ac6df', '#91dbe8', '#c2edf2', '#ffffff',
        '#fff3aa', '#ffe35a', '#ffca2c', '#ffab20', '#f5821a',
        '#eb5c17', '#d93812', '#b91d13', '#8d0912']
    front_levels = np.r_[np.arange(-4, 0, .5), -.25, .25, np.arange(.5, 4.01, .5)]
    front_colors = [
        '#242066', '#39358a', '#504ba8', '#6763bd', '#8580cf',
        '#a7a1df', '#c6c0ed', '#e3dff5', '#ffffff',
        '#ffe0dc', '#ffb1a8', '#ff8074', '#f55045', '#e72729',
        '#c80d20', '#a90018', '#790012']
    top_cmap = ListedColormap(top_colors, name='isopycnal_blue_white_gold')
    front_cmap = ListedColormap(front_colors, name='temperature_violet_white_red')
    for cm in [top_cmap, front_cmap]:
        cm.set_bad('white'); cm.set_under(cm.colors[0]); cm.set_over(cm.colors[-1])
    return (top_cmap, BoundaryNorm(top_levels, top_cmap.N),
            front_cmap, BoundaryNorm(front_levels, front_cmap.N))


def current_color_scale():
    """A more saturated shared current palette; retain the linear +/-0.5 m/s scale."""
    values=np.array([-.5,-.4,-.3,-.2,-.1,-.05,0,.05,.1,.2,.3,.4,.5])
    colors=['#103565','#154b8a','#1369b2','#439ce0','#acd8fa','#d9efff',
            '#ffffff','#ffe0db','#ffb5a8','#f85b49','#dc2325','#a61120','#750015']
    cm=LinearSegmentedColormap.from_list('current_blue_white_red',list(zip(values+.5,colors)),N=257)
    cm.set_bad('white');cm.set_under(colors[0]);cm.set_over(colors[-1])
    return cm,Normalize(-.5,.5)


def edges(x):
    x = np.asarray(x)
    return np.r_[x[0]-(x[1]-x[0])/2, (x[:-1]+x[1:])/2, x[-1]+(x[-1]-x[-2])/2]


def lonlabel(x):
    return '180°' if x == 180 else f'{int(x)}°E' if x < 180 else f'{int(360-x)}°W'


def block(ax, lon, lat, top, depth, front, *, lonlim, latlim,
          topnorm, frontnorm, top_label, front_label, depthmax=300,
          top_contours=None, levels=None, lon_ticks=None, mark_layers=False,
          top_cmap='RdBu_r', front_cmap='RdBu_r', label_longest_contour_only=False,
          section_longitudes=None):
    """Oblique top map + latitude-mean vertical face, drawn without resampling."""
    x0, x1 = lonlim; y0, y1 = latlim
    skew, rise, seam, height = .17, .26, .77, .67
    xe = (edges(lon)-x0)/(x1-x0)
    ve = (edges(lat)-y0)/(y1-y0)
    xx, vv = np.meshgrid(xe, ve)
    mesh_top = ax.pcolormesh(xx+skew*vv, seam+rise*vv, np.ma.masked_invalid(top),
                             cmap=top_cmap, norm=topnorm, shading='flat', rasterized=True)
    # Clip first/last cell edges to the physical display boundaries only.
    de = edges(depth); de[0] = 0; de[-1] = min(de[-1], depthmax)
    xx, dd = np.meshgrid(xe, de)
    mesh_front = ax.pcolormesh(xx, seam-height*dd/depthmax, np.ma.masked_invalid(front),
                               cmap=front_cmap, norm=frontnorm, shading='flat', rasterized=True)
    if top_contours is not None:
        xc, vc = np.meshgrid((np.asarray(lon)-x0)/(x1-x0), (np.asarray(lat)-y0)/(y1-y0))
        cs = ax.contour(xc+skew*vc, seam+rise*vc, top_contours,
                        levels=levels, colors='#111111', linewidths=.5, linestyles='dashed')
        if label_longest_contour_only:
            # One label per level, located on the longest connected contour.
            positions=[]
            for segments in cs.allsegs:
                paths=[p for p in segments if len(p)>1 and np.isfinite(p).all()]
                if not paths:continue
                p=max(paths,key=lambda p:np.linalg.norm(np.diff(p,axis=0),axis=1).sum())
                distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
                positions.append(p[np.argmin(abs(distance-distance[-1]/2))])
            ax.clabel(cs,inline=True,fontsize=6.5,fmt='%.1f',manual=positions)
        else:
            ax.clabel(cs, inline=True, fontsize=6.5, fmt='%.1f')
    for longitude in section_longitudes or []:
        x=(longitude-x0)/(x1-x0)
        assert 0<=x<=1
        ax.plot([x,x+skew],[seam,seam+rise],color='white',lw=2.4,zorder=6)
        ax.plot([x,x+skew],[seam,seam+rise],color='black',lw=1.,zorder=7)
    outline = [(0,seam), (skew,seam+rise), (1+skew,seam+rise),
               (1,seam), (0,seam), (0,seam-height), (1,seam-height), (1,seam)]
    ax.plot(*np.array(outline).T, color='black', lw=.65, clip_on=False)
    for d in [0, 50, 150, 300]:
        y = seam-height*d/depthmax
        ax.plot([-.015,0], [y,y], c='black', lw=.6)
        ax.text(-.025,y,str(d),ha='right',va='center',fontsize=7,color='black')
        if mark_layers and d in [50,150]:
            ax.plot([0,1],[y,y],c='black',ls='--',lw=.65)
    ax.text(-.165, seam-height/2, 'Depth (m)', rotation=90, ha='center',va='center',fontsize=7.5)
    for x in lon_ticks or [x0, (x0+x1)/2, x1]:
        xx = (x-x0)/(x1-x0)
        ax.plot([xx,xx], [seam-height,seam-height-.014], c='black',lw=.6)
        ax.text(xx,seam-height-.027,lonlabel(x),ha='center',va='top',fontsize=7)
    for y in [y0, 0, y1]:
        v = (y-y0)/(y1-y0)
        lab = '0°' if y == 0 else f'{abs(int(y))}°'+('S' if y<0 else 'N')
        ax.text(skew*v-.025,seam+rise*v+(.05 if y==y0 else .012),lab,ha='right',va='center',fontsize=6.8)
    ax.text(.57,1.065,top_label,ha='center',va='bottom',fontsize=7.5,color='black')
    ax.text(.5,.115,front_label,ha='center',va='bottom',fontsize=7.1,color='black',
            bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1})
    ax.set_xlim(-.21,1.19); ax.set_ylim(-.01,1.13); ax.set_axis_off()
    return mesh_top, mesh_front


def folded_current_block(ax, lon, lat, top, depth, front, side_lat, side, layer_bottom,
                         *, cmap, norm, top_contours):
    """Fold three diagnostics into one object, without claiming geographic continuity.

    The right face is a relocated 140W section, not the 120W map boundary.
    The front remains the latitude-band mean. All native values are retained.
    """
    assert np.shape(top)==(len(lat),len(lon))
    assert np.shape(front)==(len(depth),len(lon))
    assert np.shape(side)==(len(depth),len(side_lat))
    skew, rise, seam, height = .62, .37, .88, .79
    xe=(edges(lon)-190)/50; ve=(edges(lat)+5)/10
    de=np.r_[0,np.asarray(layer_bottom)].copy();de[-1]=300
    assert len(de)==len(depth)+1 and np.all(np.diff(de)>0)
    xx,vv=np.meshgrid(xe,ve)
    mesh=ax.pcolormesh(xx+skew*vv,seam+rise*vv,np.ma.masked_invalid(top),
                       cmap=cmap,norm=norm,shading='flat',rasterized=True)
    xx,dd=np.meshgrid(xe,de)
    ax.pcolormesh(xx,seam-height*dd/300,np.ma.masked_invalid(front),
                  cmap=cmap,norm=norm,shading='flat',rasterized=True)
    # The full 9S-9N section is folded onto the right face for comparison.
    vv,dd=np.meshgrid((edges(side_lat)+9)/18,de)
    ax.pcolormesh(1+skew*vv,seam+rise*vv-height*dd/300,
                  np.ma.masked_invalid(side),cmap=cmap,norm=norm,
                  shading='flat',rasterized=True)
    xc,vc=np.meshgrid((np.asarray(lon)-190)/50,(np.asarray(lat)+5)/10)
    cs=ax.contour(xc+skew*vc,seam+rise*vc,top_contours,
                   levels=[-1.,-.5],colors='black',linewidths=.55,linestyles='dashed')
    positions=[]
    for segments in cs.allsegs:
        paths=[p for p in segments if len(p)>1 and np.isfinite(p).all()]
        if not paths:continue
        p=max(paths,key=lambda p:np.linalg.norm(np.diff(p,axis=0),axis=1).sum())
        distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        positions.append(p[np.argmin(abs(distance-distance[-1]/2))])
    ax.clabel(cs,inline=True,fontsize=7.5,fmt='%.1f',manual=positions)
    ax.plot([.6,.6+skew],[seam,seam+rise],color='white',lw=2.6,zorder=6)
    ax.plot([.6,.6+skew],[seam,seam+rise],color='black',lw=1.,zorder=7)
    ax.text(.6+skew,seam+rise+.035,'140°W',fontsize=8,ha='center',va='bottom')
    bottom=seam-height
    outline=[(0,seam),(skew,seam+rise),(1+skew,seam+rise),
             (1+skew,bottom+rise),(1,bottom),(0,bottom),(0,seam),
             (1,seam),(1+skew,seam+rise)]
    ax.plot(*np.asarray(outline).T,color='black',lw=.85,clip_on=False)
    ax.plot([1,1],[bottom,seam],color='black',lw=.85)
    for d in [0,50,150,300]:
        y=seam-height*d/300
        ax.plot([-.015,0],[y,y],color='black',lw=.7)
        ax.text(-.027,y,str(d),fontsize=8,ha='right',va='center')
        if d in [50,150]:
            ax.plot([0,1],[y,y],color='black',ls='--',lw=.65)
            ax.plot([1,1+skew],[y,y+rise],color='black',ls='--',lw=.65)
    ax.text(-.16,seam-height/2,'Depth (m)',rotation=90,fontsize=9,ha='center',va='center')
    for longitude in [190,220,240]:
        x=(longitude-190)/50
        ax.plot([x,x],[bottom,bottom-.018],color='black',lw=.6)
        ax.text(x-(.012 if longitude==240 else 0),bottom-.035,lonlabel(longitude),
                fontsize=8,ha='right' if longitude==240 else 'center',va='top')
    for latitude in [-5,0,5]:
        v=(latitude+5)/10
        label='0°' if latitude==0 else f'{abs(latitude)}°'+('S' if latitude<0 else 'N')
        ax.text(skew*v-.025,seam+rise*v+(.045 if latitude==-5 else .012),
                label,fontsize=8,ha='right',va='center')
    for latitude in [-9,-5,0,5,9]:
        v=(latitude+9)/18;x=1+skew*v;y=bottom+rise*v
        if abs(latitude)==5:
            ax.plot([x,x],[y,y+height],color='black',ls='--',lw=.65)
        elif latitude==0:
            ax.plot([x,x],[y,y+height],color='black',ls=':',lw=.55)
        ax.plot([x,x+.012],[y,y-.017],color='black',lw=.6)
        label='0°' if latitude==0 else f'{abs(latitude)}°'+('S' if latitude<0 else 'N')
        ax.text(x+.022,y-.027,label,fontsize=7.5,ha='left',va='top')
    ax.text(.55,1.39,'0–50 m zonal current difference',fontsize=9,ha='center',va='bottom')
    ax.text(.5,bottom+.026,'5°S–5°N mean',fontsize=8,ha='center',va='bottom',
            bbox={'facecolor':'white','edgecolor':'none','alpha':.9,'pad':1.4})
    # Face titles stay outside the data to preserve the equatorial core.
    ax.text(1.72,.86,'140°W section (folded out)',fontsize=8.5,ha='center',va='center',rotation=90)
    ax.set_xlim(-.21,1.83);ax.set_ylim(-.13,1.5);ax.set_axis_off()
    return mesh


def prepare_jfm(ocean, monthly, quarters):
    OUT.mkdir(parents=True,exist_ok=True)
    fields=[]; rows=[]
    for e in EVENTS:
        q=ocean.sel(time=(ocean.time.dt.year==e)&ocean.time.dt.month.isin([1,2,3]))
        assert q.sizes['time']==3
        fields.append(q[['temperature_anomaly','d26_anomaly']].mean('time',skipna=False).expand_dims(event=[e]))
        q=monthly[(monthly.event==e)&(monthly.year==e)&monthly.month.isin([1,2,3])]
        assert len(q)==3
        row={'event':e,'season':'JFM','background':'1982-2022 monthly mean'}
        for reg in ['basin','west','central','east']:
            row[reg+'_wwv_1e14m3']=q[reg+'_wwv_m3'].mean()/1e14
            check=quarters[(quarters.event==e)&(quarters.quarter==1)].iloc[0][reg+'_wwv_m3']/1e14
            np.testing.assert_allclose(row[reg+'_wwv_1e14m3'],check,rtol=0,atol=1e-12)
        np.testing.assert_allclose(row['basin_wwv_1e14m3'],sum(row[r+'_wwv_1e14m3'] for r in ['west','central','east']),atol=1e-12)
        rows.append(row)
    ds=xr.concat(fields,dim='event')
    ds.attrs.update(season='JFM, equal mean of January February March monthly anomalies',
                    baseline='1982-2022 monthly climatology; unchanged from original M2',
                    front_face='temperature anomaly, 9S-9N cosine-weighted mean',
                    top_face='26-sigma_theta isopycnal depth anomaly (m)',
                    terminology_reference='Chen et al. (2015), Fig. 16; doi:10.1175/JCLI-D-14-00134.1')
    ds.to_netcdf(OUT/'JFM_ocean_configuration.nc',engine='scipy')
    pd.DataFrame(rows).to_csv(OUT/'JFM_WWV26.csv',index=False)
    return ds,pd.DataFrame(rows)


def plot_jfm(base, ocean, monthly, quarters, pdf):
    ds, volumes=prepare_jfm(ocean,monthly,quarters)
    fig=plt.figure(figsize=(7.2,6.6))
    panels=[fig.add_axes([.095,.55,.38,.37]),fig.add_axes([.55,.55,.38,.37]),
            fig.add_axes([.095,.14,.38,.37])]
    top_cmap, topnorm, front_cmap, frontnorm = jfm_color_scales()
    depth=ds.depth.where(ds.depth<300,drop=True)
    color_qa={}
    for j,(e,ax) in enumerate(zip(EVENTS,panels)):
        q=ds.sel(event=e,lon=slice(120,280),lat=slice(-9,9))
        im1,im2=block(ax,q.lon.values,q.lat.values,q.d26_anomaly.values,depth.values,
                      q.temperature_anomaly.sel(depth=depth).values,
                      lonlim=(120,280),latlim=(-9,9),topnorm=topnorm,frontnorm=frontnorm,
                      top_label=r'26-$\sigma_\theta$ isopycnal depth anomaly',front_label='T′: 9°S-9°N mean',
                      lon_ticks=[120,180,220,280],mark_layers=True,
                      top_cmap=top_cmap,front_cmap=front_cmap)
        ax.set_title(f'({"abc"[j]}) {e} JFM',loc='left',fontsize=8.2,pad=9,color='black')
        color_qa[str(e)]={}
        for name,values,limit in [('isopycnal_depth_anomaly_m',q.d26_anomaly.values,50),
                                  ('temperature_anomaly_C',q.temperature_anomaly.sel(depth=depth).values,4)]:
            finite=values[np.isfinite(values)]
            color_qa[str(e)][name]={'min':float(finite.min()),'max':float(finite.max()),
                'display_limit':limit,'fraction_beyond_limits':float(np.mean(np.abs(finite)>limit))}
    ax=fig.add_axes([.57,.22,.35,.24]);x=np.arange(4)
    for j,e in enumerate(EVENTS):
        q=volumes[volumes.event==e].iloc[0]
        y=[q[r+'_wwv_1e14m3'] for r in ['basin','west','central','east']]
        ax.plot(x+(j-1)*.15,y,ls='none',marker=base.MARKERS[e],ms=5,color=base.COLORS[e],label=str(e))
    base.zero(ax);ax.set_xticks(x,['Basin','West','Central','East']);ax.set_xlim(-.4,3.4)
    ax.set_ylabel(r'WWV26 anomaly ($10^{14}$ m$^3$)')
    base.panel(ax,'d','JFM warm-water volume anomalies')
    ax.legend(ncol=3,fontsize=7,loc='lower left',bbox_to_anchor=(-.04,-.35),columnspacing=.9,handletextpad=.3)
    cb=fig.colorbar(im1,cax=fig.add_axes([.125,.075,.32,.017]),orientation='horizontal',
                   extend='both',spacing='proportional',ticks=[-50,-25,0,25,50])
    cb.set_label(r'26-$\sigma_\theta$ isopycnal depth anomaly (m)',fontsize=7.5)
    cb=fig.colorbar(im2,cax=fig.add_axes([.59,.075,.32,.017]),orientation='horizontal',
                   extend='both',spacing='proportional',ticks=[-4,-2,0,2,4])
    cb.set_label('Temperature anomaly (°C)',fontsize=7.5)
    base.QA['JFM_configuration']={'events':EVENTS,'months':[1,2,3],
        'seasonal_volume_matches_existing_quarter_table':True,'regional_sum_equals_basin':True,
        'baseline':'1982-2022 unchanged','map_is_isopycnal_depth_anomaly_not_SST':True,
        'block_front_is_latitude_mean_not_front_edge_latitude':True,
        'terminology_reference':'Chen et al. 2015, Fig. 16, p. 3802',
        'reference_doi':'10.1175/JCLI-D-14-00134.1',
        'shared_scales_across_events':True,'colorbar_extensions_mark_out_of_range_values':True,
        'top_levels_m':topnorm.boundaries.tolist(),'front_levels_C':frontnorm.boundaries.tolist(),
        'top_colors':top_cmap.colors,'front_colors':front_cmap.colors,'color_ranges_by_event':color_qa}
    base.save(fig,'M2_JFM_configuration','JFM前期暖水配置：水平位置与垂向温度结构',
        'a—c分别为1997、2015、2023发展年1—3月等权平均。顶面为9°S—9°N、120°E—80°W的26-σθ等密度面深度异常，命名参照Chen等（2015）图16；σθ为位势密度异常，所选等密度面为26.0 kg m⁻³。黄—橙色表示等密度面加深、暖水层增厚，蓝色表示变浅。'
        '前侧为9°S—9°N余弦加权平均的温度异常剖面，红色表示偏暖，蓝紫色表示偏冷；展示0—300m，虚线标记50和150m。前侧是纬带平均剖面，不是顶面南边缘的实际切面。'
        '两种物理量分别采用独立配色，三事件共用同一组分级和色标，色标尖端表示范围外值；原格点数值不作平滑或增密。d为同一JFM窗口全盆地及西（120°E—180°）、中（180°—140°W）、东（140°W—80°W）三区WWV26异常，三区之和等于全盆地。'
        '所有异常均相对于1982—2022同月平均，再对1、2、3月等权平均；WWV26积分至瞬时σθ=26面，300m只是剖面展示深度。参考文献：Chen等（2015），Journal of Climate，28，3786—3805，doi:10.1175/JCLI-D-14-00134.1。',
        'January-March mean ocean anomalies in 1997, 2015 and 2023. The top face shows 26-sigma_theta isopycnal depth anomalies, following the terminology of Chen et al. (2015, Fig. 16; doi:10.1175/JCLI-D-14-00134.1). '
        'The isopycnal is defined by a potential-density anomaly of 26.0 kg m-3. Yellow-orange colors indicate deepening and blue colors indicate shoaling. The front face shows 9S-9N cosine-weighted temperature anomalies: red for warming and blue-violet for cooling. '
        'It is a latitude-band mean, not a slice at the southern map edge. Dashed lines mark 50 and 150 m. Separate palettes distinguish the two fields; each scale is shared across all three events, with extended ends for out-of-range values. Native fields are shown without smoothing or grid refinement. '
        'Regional JFM WWV26 anomalies for 120E-180, 180-140W and 140W-80W sum to the basin total. Monthly anomalies retain the 1982-2022 climatology and are averaged equally across JFM; 300 m is a display limit rather than the WWV26 integration boundary.',
        [base.FILES[1],base.FILES[3],base.FILES[4],OUT/'JFM_ocean_configuration.nc',OUT/'JFM_WWV26.csv',CHEN_PAPER],'main',pdf)
    ds.close()


def meridional_current_sections():
    """Actual 140W velocity faces, using the same native section as transport diagnostics."""
    source=BASE/'three_event_summer_current_dynamics_20261015'
    flows=[];thickness=[];hashes={};errors={}
    table=pd.read_csv(source/'section_monthly.csv',parse_dates=['time'])
    pairs=pd.read_csv(source/'section_pair_seasons.csv')
    for e in EVENTS:
        path=source/f'inputs/ocean_{e}.npz'
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        provenance=source/f'inputs/ocean_{e}_source.json'
        record=json.loads(provenance.read_text())
        assert record['year']==e and digest==record['extracted_sha256']
        hashes[str(path.relative_to(ROOT))]=digest
        hashes[str(provenance.relative_to(ROOT))]=hashlib.sha256(provenance.read_bytes()).hexdigest()
        with np.load(path) as z:
            u=z['section_u'].astype(float);h=z['section_h'].astype(float)
            lat=z['section_lat'];depth=z['section_depth'];bottom=z['section_bottom'];width=z['section_width']
            assert u.shape==h.shape==(12,24,36)
            assert np.all(np.diff(lat)>0) and np.all(np.diff(depth)>0)
            np.testing.assert_allclose(edges(lat),np.arange(-9,9.01,.5),atol=1e-10)
            assert np.isfinite(u[h>0]).all()
            actual=np.sum(np.where(h>0,u,0)*h*width[None,None,:],axis=(1,2))/1e6
            target=table[(table.band=='all')&(table.time.dt.year==e)].sort_values('time').transport_raw_sv.values
            np.testing.assert_allclose(actual,target,rtol=0,atol=1e-10)
            errors[str(e)]=float(np.max(abs(actual-target)))
            grid=(lat,depth,bottom,width)
            if flows:
                for a,b in zip(grid,first_grid):np.testing.assert_array_equal(a,b)
            else:first_grid=tuple(a.copy() for a in grid)
            flows.append(u[6:9]);thickness.append(h[6:9])
    u=np.stack(flows);h=np.stack(thickness)
    common=np.isfinite(u).all(axis=(0,1))
    contrasts=np.stack([np.mean(u[2]-u[j],axis=0) for j in [0,1]])
    contrasts=np.where(common[None],contrasts,np.nan)
    # Reproduce the existing velocity contribution before temporal averaging.
    tops=np.r_[0,bottom[:-1]];contribution_errors={}
    for j,control in enumerate(EVENTS[:2]):
        for band,(lo,hi) in {'0_50':(0,50),'50_150':(50,150),
                            '150_sigma26':(150,np.inf),'all':(0,np.inf)}.items():
            ha=np.maximum(0,np.minimum(tops[None,:,None]+h[2],hi)-np.maximum(tops[None,:,None],lo))
            hb=np.maximum(0,np.minimum(tops[None,:,None]+h[j],hi)-np.maximum(tops[None,:,None],lo))
            pair_h=(ha+hb)/2
            assert np.isfinite((u[2]-u[j])[pair_h>0]).all()
            value=np.sum(np.where(pair_h>0,u[2]-u[j],0)*pair_h*width[None,None,:],axis=(1,2)).mean()/1e6
            ref=float(pairs[(pairs.control==control)&(pairs.season=='JAS')&(pairs.band==band)].iloc[0].current_sv)
            np.testing.assert_allclose(value,ref,rtol=0,atol=1e-10)
            contribution_errors[f'{control}_{band}']=float(abs(value-ref))
    ds=xr.Dataset({
        'current_difference':(('control','depth','lat'),contrasts),
        'monthly_current':(('event','month','depth','lat'),u),
        'active_warm_layer_thickness':(('event','month','depth','lat'),h),
        'common_valid':(('depth','lat'),common.astype('i1')),
        'layer_bottom':(('depth',),bottom),'face_width':(('lat',),width)},
        coords={'control':EVENTS[:2],'event':EVENTS,'month':[7,8,9],'depth':depth,'lat':lat})
    ds.current_difference.attrs.update(units='m s-1',definition='JAS mean u(2023)-u(control); eastward positive')
    ds.monthly_current.attrs.update(units='m s-1',grid='native 220E velocity face, B-grid latitude interpolation to tracer latitude')
    for name in ['active_warm_layer_thickness','layer_bottom','face_width']:ds[name].attrs['units']='m'
    ds.attrs.update(longitude_degrees_east=220.,latitude_bounds_degrees='-9, 9',
        section_kind='actual longitude section, not a zonal or latitudinal average',
        common_monthly_background='1982-2024; cancels exactly in paired calendar-month differences',
        display_depth_m='0-300; full warm-layer transport is checked separately using the original active thickness',
        missing_data='common finite mask across all three events and JAS months; no zero filling',
        source_note='input section_u, not the budget-only array with zeros below inactive layers')
    dest=OUT/'JAS_140W_meridional_current_sections.nc'
    ds.to_netcdf(dest,engine='scipy')
    check_depth=depth<300
    qa={'source_sha256':hashes,'events':EVENTS,'months':[7,8,9],'longitude_degrees_east':220,
        'latitude_edges_degrees':[-9,9],'local_latitude_markers_degrees':[-5,5],
        'native_velocity_face_matches_transport_definition':True,
        'source_provenance_hashes_match':True,'raw_monthly_transport_max_error_sv':errors,
        'JAS_velocity_contribution_errors_sv':contribution_errors,
        'common_valid_fraction_0_300m':float(common[check_depth].mean()),
        'difference_formed_before_monthly_mean':True,'no_filling_no_smoothing':True,
        'color_limit_m_s':.5,'fraction_beyond_color_limit':{
            str(control):float(np.mean(abs(contrasts[j,check_depth][common[check_depth]])>.5))
            for j,control in enumerate(EVENTS[:2])}}
    (OUT/'JAS_140W_meridional_current_sections_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
    return ds,qa


def current_sections():
    dest=OUT/'JAS_current_vertical_sections.npz'
    if dest.exists(): return dict(np.load(dest))
    fields=[];sources={};qa={}
    with np.load(BASE/'three_event_temperature_tendency_20261015/local_fields_cache.npz') as z:
        cached=z['u'];clat=z['lat'];clon=z['lon']
    for e in EVENTS:
        p=RAW/f'soda3_sigma26_inputs_{e}.npz'
        with np.load(p) as z:
            lat=np.round(z['lat_t'],6);lon=np.round(z['lon_t'],6)
            iy=np.flatnonzero((lat>-5)&(lat<5));ix=np.flatnonzero((lon>190)&(lon<240))
            sy=slice(iy[0],iy[-1]+2);sx=slice(ix[0],ix[-1]+2)
            a=z['u'][6:9,:,sy,sx]
            u=(a[:,:,:-1,:-1]+a[:,:,1:,:-1]+a[:,:,:-1,1:]+a[:,:,1:,1:])/4
            old=cached[(e-1982)*12+6:(e-1982)*12+9,:,1:-1,1:-1]
            err=float(np.nanmax(abs(u[:,:8]-old)))
            np.testing.assert_allclose(u[:,:8],old,rtol=0,atol=0,equal_nan=True)
            np.testing.assert_allclose(lat[iy],clat[1:-1],atol=1e-6)
            np.testing.assert_allclose(lon[ix],clon[1:-1],atol=1e-6)
            depth=z['depth'];fields.append(u.astype(float));qa[str(e)]=err
        sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    fields=np.stack(fields)
    valid=np.isfinite(fields).all(axis=(0,1))
    w=np.cos(np.deg2rad(lat[iy]))[None,:,None]*valid
    sections=[]
    for j in [0,1]:
        delta=(fields[2]-fields[j]).mean(axis=0)
        num=np.sum(np.where(valid,delta,0)*w,axis=1);den=w.sum(axis=1)
        sections.append(np.divide(num,den,out=np.full_like(num,np.nan),where=den>0))
    result={'controls':np.array([1997,2015]),'depth':depth,'lon':lon[ix],
            'current_difference':np.stack(sections)}
    np.savez_compressed(dest,**result)
    (OUT/'JAS_current_vertical_sections_QA.json').write_text(json.dumps({
        'existing_upper_8_levels_max_error_m_s':qa,'source_sha256':sources,
        'latitude_band':'5S-5N cosine-weighted; joint finite mask for all 3 events and JAS months',
        'definition':'JAS mean u(2023)-u(control); common monthly climatology cancels exactly',
        'depth_display':'native centers to 300m; no new layer-integrated budget'},indent=2)+'\n')
    return result


def update_jfm_only():
    """Refresh the JFM figure and gallery metadata, preserving the other six figures."""
    import build_three_event_scientific_figures as base
    from matplotlib.backends.backend_pdf import PdfPages
    base.style()
    meta=json.loads((base.OUT/'figure_manifest.json').read_text())
    base.QA=json.loads((base.OUT/'validation.json').read_text())
    base.META=[]
    preserved={str(p.relative_to(base.OUT)):base.sha(p)
        for m in meta if m['stem']!='M2_JFM_configuration'
        for p in [*(base.OUT/f"{m['stem']}.{ext}" for ext in ['png','pdf','svg']),
                  base.OUT/'presentation'/f"{m['stem']}.png"]}
    with xr.open_dataset(OUT/'JFM_ocean_configuration.nc',engine='scipy') as old:
        old_fields=old.load().copy(deep=True)
    old_volumes=pd.read_csv(OUT/'JFM_WWV26.csv')
    inputs=[base.FILES[1],base.FILES[3],base.FILES[4]]
    hashes={str(p.relative_to(ROOT)):base.sha(p) for p in inputs}
    tmp=ROOT/'tmp/pdfs/jfm_color_review';tmp.mkdir(parents=True,exist_ok=True)
    with xr.open_dataset(base.FILES[1],engine='scipy') as ocean:
        with PdfPages(tmp/'rebuilt_JFM.pdf') as pdf:
            plot_jfm(base,ocean,pd.read_csv(base.FILES[3]),pd.read_csv(base.FILES[4]),pdf)
    with xr.open_dataset(OUT/'JFM_ocean_configuration.nc',engine='scipy') as new:
        for variable in old_fields.data_vars:
            np.testing.assert_array_equal(old_fields[variable].values,new[variable].values)
    pd.testing.assert_frame_equal(old_volumes,pd.read_csv(OUT/'JFM_WWV26.csv'),check_exact=True)
    assert all(base.sha(ROOT/p)==h for p,h in hashes.items())
    assert all(base.sha(base.OUT/p)==h for p,h in preserved.items())
    m=base.META[0]
    assert 'D26' not in m['caption_cn']+m['caption_en']+m['title']
    base.META=[m if item['stem']==m['stem'] else item for item in meta]
    base.QA['JFM_color_revision']={'plotted_field_values_unchanged':True,
        'JFM_volumes_unchanged':True,'source_inputs_unchanged':True,
        'other_figure_files_unchanged':len(preserved),'other_figure_sha256':preserved,
        'only_updated_figure':'M2_JFM_configuration',
        'paper_checked':'Chen et al. 2015, Fig. 16, p. 3802',
        'reference_url':'https://coda.oc.ntu.edu.tw/research/papers/2015_Chen_STC.pdf'}
    base.QA['visual_pdf_review']={'status':'Pending review of revised page 2; other six figure files unchanged',
        'page_numbers':[2]}
    (base.OUT/'figure_manifest.json').write_text(json.dumps(base.META,ensure_ascii=False,indent=2)+'\n')
    (base.OUT/'validation.json').write_text(json.dumps(base.QA,ensure_ascii=False,indent=2)+'\n')
    manifest=json.loads((base.OUT/'input_manifest.json').read_text())
    manifest[str(CHEN_PAPER.relative_to(ROOT))]=base.sha(CHEN_PAPER)
    (base.OUT/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    base.gallery()
    print('PASS: JFM field values and volumes unchanged; other 24 figure files unchanged.',flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-jfm-only',action='store_true',required=True)
    parser.parse_args()
    update_jfm_only()
