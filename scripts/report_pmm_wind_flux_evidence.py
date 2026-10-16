"""Plot ERA5 wind and NCEP-NCAR R1 latent-heat evidence for eight events."""
from pathlib import Path
import hashlib
import json
import os
import sys
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/maryland_enso_strength_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
import xarray as xr
import cartopy.crs as ccrs
import cartopy.io.shapereader as shapereader

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/research_2026/enso_strength_screenshot_D20_2002_2024_20261015'
OUT = BASE / 'pmm_wind_flux_evidence'
ORDER = [2009, 2014, 2015, 2023, 2002, 2018, 2004, 2006, 2019]
GROUP = {2009:'Strong',2014:'Strong',2015:'Strong',2023:'Strong',2002:'Moderate',2018:'Moderate',2004:'Weak',2006:'Weak',2019:'Weak'}
NAVY = '#052D50'
GREY = '#546777'
SEASONS = ['MAM', 'JJA', 'SON', 'DJF']


def save(fig, stem):
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(OUT / f'{stem}.{ext}', dpi=220, facecolor='white')
    plt.close(fig)


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11,
        'axes.spines.top':False,'axes.spines.right':False,
        'legend.frameon':False,'pdf.fonttype':42,'svg.fonttype':'none'})


def maps(fields, seasonal, season, kind, number):
    projection = ccrs.PlateCarree(central_longitude=180)
    geo = ccrs.PlateCarree()
    coast_path = Path('/Users/daiyue/.local/share/cartopy/shapefiles/natural_earth/physical/ne_110m_coastline.shp')
    coast = list(shapereader.Reader(coast_path).geometries()) if coast_path.exists() else None
    fig, axes = plt.subplots(3, 3, figsize=(15, 10.6), subplot_kw={'projection':projection})
    fig.subplots_adjust(left=.055, right=.96, top=.85, bottom=.15, hspace=.32, wspace=.12)
    months = [3,4,5] if season == 'MAM' else [6,7,8]
    sst = kind == 'sst'
    limit = 2 if sst else 40
    levels = np.linspace(-limit, limit, 17)
    for i, (ax, year) in enumerate(zip(axes.flat, ORDER)):
        dates = pd.to_datetime([f'{year}-{m:02d}-01' for m in months])
        data = fields.sel(time=dates).mean('time')
        values = data.sst_anomaly_c if sst else data.latent_down_anomaly_wm2
        x, y = (data.sst_lon, data.sst_lat) if sst else (data.flux_lon, data.flux_lat)
        image = ax.contourf(x, y, values, levels=levels, cmap='RdBu_r', extend='both', transform=geo)
        if coast:
            ax.add_geometries(coast, crs=geo, facecolor='none', edgecolor='#4F5961', linewidth=.7)
        ax.set_extent([190,260,0,30], crs=geo)
        ax.set_xticks([200,220,240,260], crs=geo)
        ax.set_xticklabels(['160°W','140°W','120°W','100°W'], fontsize=9)
        ax.set_yticks([0,10,20,30], crs=geo)
        ax.set_yticklabels(['0°','10°N','20°N','30°N'], fontsize=9)
        ax.gridlines(xlocs=[200,220,240,260], ylocs=[0,10,20,30], linewidth=.4, color='#71808C', alpha=.28)
        ax.add_patch(Rectangle((205,10),40,20,facecolor='none',edgecolor='#1A2026',lw=1.3,transform=geo,zorder=5))
        u = data.u10_anomaly_ms.isel(lat=slice(2,None,4),lon=slice(2,None,5))
        v = data.v10_anomaly_ms.isel(lat=slice(2,None,4),lon=slice(2,None,5))
        quiver = ax.quiver(u.lon.values,u.lat.values,u.values,v.values,transform=geo,scale=22,width=.0032,headwidth=3.4,color='#222930')
        if i == 8:
            ax.quiverkey(quiver,.77,-.24,1,'1 m/s',labelpos='E',coordinates='axes',fontproperties={'size':9})
        row = seasonal[(seasonal.development_year == year) & (seasonal.season == season)].iloc[0]
        event_note = ' · yr 1' if year == 2014 else (' · yr 2' if year == 2015 else '')
        ax.set_title(f'{year}{event_note} · {GROUP[year]} | PMM {row.pmm:+.2f}',loc='left',fontsize=11,weight='bold',color=NAVY,pad=9)
        value = row.sst_anomaly_c if sst else row.latent_down_anomaly_wm2
        label = f'Box SST {value:+.2f} °C' if sst else f'Box LH {value:+.1f} W/m²'
        ax.text(.02,.03,label,transform=ax.transAxes,fontsize=9,color='#142C3D',
                bbox=dict(facecolor='white',edgecolor='none',alpha=.88,pad=2))
    cax = fig.add_axes([.25,.105,.48,.018])
    fig.colorbar(image,cax=cax,orientation='horizontal').set_label(
        'SST anomaly (°C)' if sst else 'Latent heat flux anomaly (W/m²) · positive downward = less ocean heat loss')
    title = 'SST and 10 m wind anomalies' if sst else 'Latent heat flux and 10 m wind anomalies'
    fig.suptitle(f'{season} · {title}',fontsize=21,weight='bold',color=NAVY,y=.975)
    fig.text(.5,.923,'8 El Niño events / 9 development years · ERSSTv5 SST · ERA5 wind · NCEP-NCAR R1 latent heat flux',ha='center',fontsize=12,color=GREY)
    fig.text(.055,.025,'1991–2020 calendar-month anomalies; no detrending or ENSO removal. Box: 10–30°N, 155–115°W (ocean only).\n'
        'Arrows show wind anomalies, not actual wind. 2014 and 2015 belong to one event. Identical scales across MAM and JJA.',fontsize=10,color=GREY,linespacing=1.5)
    stem = f'Fig{number}_{season}_{"SST_wind" if sst else "latent_heat_wind"}'
    save(fig,stem)
    return stem


def matrix(seasonal):
    fig, axes = plt.subplots(1,3,figsize=(15.4,8.6))
    fig.subplots_adjust(left=.12,right=.97,top=.79,bottom=.23,wspace=.31)
    specs = [('pmm','PMM-SST','Mode amplitude (°C)',8),
        ('wind_weakening_ms','Background-wind weakening','Opposing-wind projection (m/s)',1.2),
        ('latent_down_anomaly_wm2','Reduced latent heat loss','Downward flux anomaly (W/m²)',30)]
    labels = [f'{y} · {GROUP[y]}' for y in ORDER]
    for j,(ax,(column,title,unit,limit)) in enumerate(zip(axes,specs)):
        values = seasonal.pivot(index='development_year',columns='season',values=column).reindex(index=ORDER,columns=SEASONS).values
        limit = max(limit,float(np.ceil(np.max(np.abs(values))))) if column != 'wind_weakening_ms' else max(limit,float(np.ceil(np.max(np.abs(values))/.2)*.2))
        im = ax.imshow(values,cmap='RdBu_r',norm=TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit),aspect='auto')
        ax.set(xticks=range(4),xticklabels=SEASONS,yticks=range(9),yticklabels=labels if j == 0 else [])
        ax.set_title(title,color=NAVY,fontsize=13,weight='bold',pad=16)
        for (r,c),v in np.ndenumerate(values):
            ax.text(c,r,f'{v:+.2f}' if j < 2 else f'{v:+.1f}',ha='center',va='center',fontsize=11,
                color='white' if abs(v) > limit*.55 else '#142C3D')
        ax.axhline(3.5,color='white',lw=3);ax.axhline(5.5,color='white',lw=3)
        pos = ax.get_position()
        cax = fig.add_axes([pos.x0,.14,pos.width,.021])
        fig.colorbar(im,cax=cax,orientation='horizontal',extend='both').set_label(unit,fontsize=10)
    fig.suptitle('Do PMM, weaker winds and reduced evaporation agree?',fontsize=21,color=NAVY,weight='bold',y=.97)
    fig.text(.5,.90,'Red: positive PMM / wind anomaly opposing the mean flow / less latent heat loss; blue: opposite.',ha='center',fontsize=11,color=GREY)
    fig.text(.12,.015,'ERA5 wind + NCEP-NCAR R1 flux: ocean means over 10–30°N, 155–115°W, relative to 1991–2020.\n'
        'Wind is a vector projection, not scalar wind speed. Different products; phase agreement does not establish WES causality.\n'
        '2014 and 2015 are two development years of the same event: 8 events, 9 development years.',fontsize=10,color=GREY,linespacing=1.6)
    save(fig,'Fig5_seasonal_PMM_wind_flux')
    return 'Fig5_seasonal_PMM_wind_flux'


def timeline(curves):
    fig,axes=plt.subplots(3,3,figsize=(15,10),sharex=True)
    fig.subplots_adjust(left=.065,right=.95,top=.84,bottom=.16,hspace=.43,wspace=.34)
    wind_limit=max(1.,float(np.ceil(curves.wind_weakening_ms.abs().max()*1.1/.2)*.2))
    flux_limit=max(20.,float(np.ceil(curves.latent_down_anomaly_wm2.abs().max()*1.1/5)*5))
    for ax,year in zip(axes.flat,ORDER):
        p=curves[curves.development_year.eq(year)].sort_values('relative_month')
        twin=ax.twinx()
        ax.axhline(0,color='#73808A',lw=.7);ax.axvspan(2,6,color='#E2E9EF',alpha=.7)
        ax.plot(p.relative_month,p.wind_weakening_ms,color='#0075BE',lw=2,label='Wind weakening')
        twin.plot(p.relative_month,p.latent_down_anomaly_wm2,color='#B54B1D',lw=2,ls='--',label='Reduced LH loss')
        ax.set(xlim=(1,15),ylim=(-wind_limit,wind_limit),xticks=[1,3,6,9,12,15],xticklabels=['Jan','Mar','Jun','Sep','Dec','Mar+1'])
        twin.set_ylim(-flux_limit,flux_limit)
        ax.set_ylabel('Weakening proj. (m/s)',color='#0075BE',fontsize=9)
        twin.set_ylabel('ΔLH↓ (W/m²)',color='#B54B1D',fontsize=9)
        ax.tick_params(labelsize=9);twin.tick_params(labelsize=9)
        ax.set_title(f'{year} · {GROUP[year]}',loc='left',fontsize=12,weight='bold',color=NAVY)
    fig.suptitle('Monthly wind and latent-heat evidence through each event',fontsize=20,color=NAVY,weight='bold',y=.97)
    fig.text(.5,.91,'Blue solid: weaker winds (+) · Orange dashed: less latent heat loss (+) · Shaded: February–June starts',ha='center',fontsize=11,color=GREY)
    fig.text(.065,.05,'ERA5 wind projection + NCEP-NCAR R1 flux. Separate physical axes; shared scales across events. 1991–2020 anomalies.\n'
        'Two development years are shown for the 2014–16 event. These observed fields are not inputs to the existing forecasts.',fontsize=10,color=GREY,linespacing=1.6)
    save(fig,'Fig6_monthly_wind_flux')
    return 'Fig6_monthly_wind_flux'


def main():
    style()
    seasonal=pd.read_csv(OUT/'development_year_seasonal_evidence.csv')
    curves=pd.read_csv(OUT/'event_monthly_evidence.csv')
    fields=xr.open_dataset(OUT/'spatial_evidence.nc',engine='scipy')
    figures=[]
    for season,kind,number in [('MAM','sst',1),('MAM','latent',2),('JJA','sst',3),('JJA','latent',4)]:
        figures.append(maps(fields,seasonal,season,kind,number))
    fields.close()
    figures.extend([matrix(seasonal),timeline(curves)])
    primary=seasonal[seasonal.season.eq('Feb_Jun')].set_index('development_year').loc[ORDER]
    table=pd.DataFrame({'发展年':ORDER,'PMM':primary.pmm.round(2).values,
        '区域SST距平°C':primary.sst_anomaly_c.round(2).values,
        '背景风减弱投影m/s':primary.wind_weakening_ms.round(2).values,
        '减少潜热散失W/m²':primary.latent_down_anomaly_wm2.round(2).values,
        '风与通量均同PMM符号':np.where(primary.both_same_sign_as_pmm,'是','否'),
        '去趋势后均同号':np.where(primary.both_same_sign_detrended,'是','否'),
        '原Niño3.4_RMSE变化%':primary.rmse_change_percent.round(2).values})
    table.to_csv(OUT/'primary_comparison_cn.csv',index=False)
    nwind=int(primary.wind_same_sign_as_pmm.sum());nflux=int(primary.flux_same_sign_as_pmm.sum())
    nboth=int(primary.both_same_sign_as_pmm.sum());ndetrend=int(primary.both_same_sign_detrended.sum())
    notes=[
        '补充资料为ERA5 10米风矢量、NOAA提供的NCEP-NCAR R1月平均潜热通量，SST用ERSSTv5。CDS仅完成1月后限制排队，本轮改用完整NCEP通量；没有把零散ERA5通量拼进NCEP时间序列。属于再分析/观测分析证据，不是独立直接通量观测。',
        '区域在看结果前固定为10—30°N、155—115°W，所有事件相同。1991—2020完整同月气候态；月值不平滑、不回归去除ENSO。官方PMM经过其自身的去趋势/CTI处理，两者不要求逐值等同。',
        '背景风减弱投影=−(u′ū+v′v̄)/sqrt(ū²+v̄²)，每个格点按常年同月风向投影后区域平均；正值表示异常抵消背景风，并非月平均标量风速变化。NCEP原LHTFL向上为正，先取负再求距平；因此正值表示海洋少散热。单位已是W/m²，不再除以86400。',
        f'2—6月起报窗口，9个发展年中风投影与PMM同号{nwind}/9，潜热通量同号{nflux}/9，两者同时同号{nboth}/9；区域距平去掉1982—2024线性趋势后，两者同时同号为{ndetrend}/9。这些是符号计数，不是显著性或因果检验。',
        '2014/2015是同一次2014—16事件，以上9行不是9个独立事件；事件表先在持续事件内部平均，分组表再按事件等权。',
        '总潜热通量受风速、海气湿度差、海温和交换系数共同影响；风与总通量来自不同再分析，分辨率也不同。不一致可能包含真实物理差异和产品差异，不能直接归为某一项。没有计算固定湿度/交换系数下的反事实通量，不能把总通量当作风速造成的WES分量。',
        '地图和逐月曲线可检查异常位置及演变，但同步符号一致不能证明海温反馈到风，也不能证明副热带信号传播至赤道。没有用少数事件相关系数作因果或显著性结论。',
        '现有RO与RO＋PMM的D20 sLIM系数、初态、预测、评分全部未改；新增资料只作证据比较。原RMSE变化为季节中心提前1—5月评分，负数改善，且是全时段拟合的回溯比较。'
    ]
    def record(year,season):
        return seasonal[(seasonal.development_year==year)&(seasonal.season==season)].iloc[0]
    a,b=record(2023,'MAM'),record(2023,'JJA')
    c,d=record(2015,'JJA'),record(2018,'JJA')
    e=record(2014,'MAM')
    conclusions=[
        f'2023春季与负PMM的简单WES图景不一致：PMM {a.pmm:+.2f}，区域海温{a.sst_anomaly_c:+.2f}°C，背景风减弱投影{a.wind_weakening_ms:+.2f}m/s，潜热散失减少{a.latent_down_anomaly_wm2:+.2f}W/m²。冷异常存在，但同期风与通量方向都不是强化该冷异常的方向。',
        f'2023夏季才出现与负PMM同向的配合：背景风减弱投影{b.wind_weakening_ms:+.2f}m/s（即增强背景风），向下潜热通量距平{b.latent_down_anomaly_wm2:+.2f}W/m²（即海洋散热增加）。不能把春夏合起来写成持续增强散热。',
        f'2015、2018夏季较符合正PMM的典型配合：风减弱投影分别{c.wind_weakening_ms:+.2f}/{d.wind_weakening_ms:+.2f}m/s，潜热散失减少{c.latent_down_anomaly_wm2:+.2f}/{d.latent_down_anomaly_wm2:+.2f}W/m²。但春季并非两年都如此，须保留季节差异。',
        f'物理方向相符并不等于预测一定改善。2014春季风减弱{e.wind_weakening_ms:+.2f}m/s、潜热散失减少{e.latent_down_anomaly_wm2:+.2f}W/m²，而该发展年加入PMM后的Niño3.4 RMSE仍增加{e.rmse_change_percent:.2f}%。2014单年和2014—16整个事件不可混用。',
        '这些结果支持逐事件、逐季节解释，不能据此说PMM正负必然通过蒸发反馈控制Niño3.4，也不能把总潜热通量作为已分离的风致WES项。'
    ]
    text='2002—2024年8次事件：PMM的风与潜热通量证据\n\n'+'\n\n'.join(conclusions)+'\n\n方法与边界：\n'+'\n\n'.join(notes)+'\n\n2—6月窗口：\n'+table.to_string(index=False)+'\n'
    (OUT/'results_cn.txt').write_text(text)
    html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PMM风与潜热通量证据</title><style>body{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;line-height:1.8;margin:0;background:#f3f5f6;color:#203646}main{max-width:1450px;margin:auto;padding:28px}section{background:white;padding:24px;margin:24px 0}img{width:100%;height:auto}table{border-collapse:collapse;font-size:14px;width:100%}th,td{padding:8px;border-bottom:1px solid #dde3e8;text-align:right}.scroll{overflow:auto}a{color:#216c94}</style><main><h1>PMM：补充风与潜热通量证据</h1><p><a href="../pmm_comparison/index.html">PMM事件比较</a> · <a href="../index.html">原sLIM预报比较</a></p>'
    html+='<section><h2>新增证据说明了什么</h2>'+''.join(f'<p>{n}</p>' for n in conclusions)+'</section>'
    html+='<section><h2>统一口径与结果</h2>'+''.join(f'<p>{n}</p>' for n in notes[:5])+'<div class="scroll">'+table.to_html(index=False,border=0)+'</div></section>'
    titles=['春季海温与风','春季潜热通量与风','夏季海温与风','夏季潜热通量与风','逐事件季节对应关系','逐月风与潜热通量']
    for stem,title in zip(figures,titles):
        html+=f'<section><h2>{title}</h2><img src="{stem}.png" alt="{title}"><p><a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></p></section>'
    html+='<section><h2>证据边界</h2>'+''.join(f'<p>{n}</p>' for n in notes[5:])+'</section>'
    links=['results_cn.txt','event_monthly_evidence.csv','initialization_evidence_45.csv','development_year_seasonal_evidence.csv','event_equal_weight_seasonal_evidence.csv','group_equal_weight_seasonal_evidence.csv','monthly_regional_evidence_1982_2024.csv','protocol.json','QA.json','source_manifest.json']
    html+='<section><h2>数据与复现</h2><p>'+' · '.join(f'<a href="{p}">{p}</a>' for p in links)+'</p><p>运行 scripts/analyze_pmm_wind_flux_evidence.py，再运行 scripts/report_pmm_wind_flux_evidence.py。</p><p>区域参考：<a href="https://doi.org/10.1029/2024GL108924">Li et al. (2024)</a>；<a href="https://psl.noaa.gov/data/gridded/data.ncep.reanalysis.html">NOAA PSL NCEP-NCAR Reanalysis 1</a>。Data provided by NOAA PSL, Boulder, Colorado, USA.</p></section></main></html>'
    (OUT/'index.html').write_text(html)
    manifest=json.loads((OUT/'source_manifest.json').read_text())
    manifest['sha256'][str(Path(__file__).resolve().relative_to(ROOT))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (OUT/'source_manifest.json').write_text(json.dumps(manifest,indent=2))
    for target in [BASE/'pmm_comparison/index.html',BASE/'index.html']:
        page=target.read_text()
        marker='id="pmm-wind-flux-evidence-link"'
        if marker not in page:
            relative='../pmm_wind_flux_evidence/index.html' if target.parent.name=='pmm_comparison' else 'pmm_wind_flux_evidence/index.html'
            page=page.replace('</main>',f'<section {marker}><h2>补充：风与潜热通量证据</h2><p><a href="{relative}">查看8次事件的风、潜热通量和PMM对照</a></p></section></main>')
            target.write_text(page)
    print(text,flush=True)


if __name__=='__main__':
    main()
