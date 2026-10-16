"""Audit saved directional products and write the bounded Chinese interpretation."""
from pathlib import Path
import html
import json
import hashlib
import numpy as np
import pandas as pd
import xarray as xr

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/research_2026/three_event_directional_advection_20261015'
DYN=ROOT/'outputs/research_2026/three_event_summer_current_dynamics_20261015'
TERMS=['x_temperature','x_velocity','x_nonlinear','x_total',
       'y_temperature','y_velocity','y_nonlinear','y_total','horizontal_total']
NAMES={'control':'对照年','depth_m':'层厚(m)','background':'背景处理','season':'季节','region':'区域',
       'x_temperature':'纬向温度结构项','x_velocity':'纬向异常流项','x_nonlinear':'纬向非线性项','x_total':'纬向净项',
       'y_temperature':'经向温度结构项','y_velocity':'经向异常流项','y_nonlinear':'经向非线性项','y_total':'经向净项',
       'horizontal_total':'水平合计'}
REGIONS={'S_5_2':'5°S—2°S','EQ_2_2':'2°S—2°N','N_2_5':'2°N—5°N',
         'north':'0—5°N','south':'5°S—0','all':'Niño3.4'}


def main():
    pair=pd.read_csv(OUT/'directional_pair_seasons.csv')
    regions=pd.read_csv(OUT/'regional_pair_seasons.csv')
    cases=pd.read_csv(OUT/'directional_case_seasons.csv')
    monthly=pd.read_csv(OUT/'directional_case_monthly.csv',parse_dates=['time'])
    main=pair.query('depth_m==50 and background=="mean" and season=="JAS"').set_index('control')
    sens=pair.query('season=="JAS"')
    checks={}
    for d in ['x','y']:
        checks[d+'_three_components']=float(abs(pair[[d+'_temperature',d+'_velocity',d+'_nonlinear']].sum(1)-pair[d+'_total']).max())
    checks['xy_sum']=float(abs(pair.x_total+pair.y_total-pair.horizontal_total).max())
    original=pd.read_csv(DYN/'case_seasons.csv')
    merged=cases.merge(original,on=['event','depth_m','background','season'],suffixes=('_new','_old'),validate='one_to_one')
    checks['original_horizontal_total']=float(abs(merged.horizontal_total_new-merged.horizontal_total_old).max())
    checks['original_nonlinear_total']=float(abs(merged.x_nonlinear+merged.y_nonlinear-merged.nonlinear_hadv_old).max())
    for season,months in [('AMJ',[4,5,6]),('JAS',[7,8,9])]:
        q=monthly[monthly.time.dt.month.isin(months)].groupby(['event','depth_m','background'])[TERMS].mean().sort_index()
        saved=cases[cases.season.eq(season)].set_index(['event','depth_m','background'])[TERMS].sort_index()
        checks['season_'+season]=float(np.max(abs(q.to_numpy()-saved.to_numpy())))
    with xr.open_dataset(OUT/'directional_spatial.nc',engine='h5netcdf') as ds:
        weights=ds.area*ds.effective_layer_thickness
        for h in [30,50,75]:
            for bg in ['mean','detrend']:
                for season in ['AMJ','JAS']:
                    for control in [1997,2015]:
                        ref=pair.query('depth_m==@h and background==@bg and season==@season and control==@control').iloc[0]
                        w=weights.sel(depth_m=h)
                        for key in TERMS[:-1]:
                            field=ds[key].sel(depth_m=h,background=bg,season=season)
                            difference=field.sel(event=2023)-field.sel(event=control)
                            value=float((difference*w).sum()/w.sum())
                            checks.setdefault('saved_spatial_integral',0.)
                            checks['saved_spatial_integral']=max(checks['saved_spatial_integral'],abs(value-ref[key]))
        # Region values are whole-domain contributions; check the six-cell partition independently.
        for control in [1997,2015]:
            field=ds.y_total.sel(depth_m=50,background='mean',season='JAS')
            difference=field.sel(event=2023)-field.sel(event=control);w=weights.sel(depth_m=50)
            for band,latmask in [('S_5_2',ds.lat<-2),('EQ_2_2',abs(ds.lat)<2),('N_2_5',ds.lat>2)]:
                for half,lonmask in [('west',ds.lon<220),('east',ds.lon>220)]:
                    name=band+'_'+half
                    value=float((difference*w).where(latmask&lonmask).sum()/w.sum())
                    ref=regions.query('depth_m==50 and background=="mean" and season=="JAS" and control==@control and region==@name').iloc[0].y_total
                    checks.setdefault('saved_six_region_integral',0.)
                    checks['saved_six_region_integral']=max(checks['saved_six_region_integral'],abs(value-ref))
    assert max(checks.values())<1e-9,checks
    result={'status':'PASS','saved_product_checks_max_C_month':checks,
            'JAS_y_negative_in_all_settings':bool((sens.y_total<0).all()),
            'JAS_y_larger_magnitude_than_x':int((abs(sens.y_total)>abs(sens.x_total)).sum()),
            'setting_comparisons':len(sens),'settings_are_not_independent_samples':True}
    regional_sensitivity={}
    for control in [1997,2015]:
        for region,key in [('north','y_velocity'),('south','y_temperature')]:
            values=regions.query('season=="JAS" and control==@control and region==@region')[key]
            regional_sensitivity[f'{control}_{region}_{key}']={'min':float(values.min()),'max':float(values.max()),
                'negative_settings':int((values<0).sum()),'settings':len(values)}
    result['regional_sensitivity']=regional_sensitivity
    (OUT/'independent_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    a,b=main.loc[1997],main.loc[2015]
    paper=(f'在Niño3.4上层50m、1982—2024全部43年同月背景下，2023年JAS水平平流增暖较1997、2015年分别减少'
           f'{-a.horizontal_total:.3f}和{-b.horizontal_total:.3f}°C/标准月。其中，经向净平流差为{a.y_total:+.3f}和{b.y_total:+.3f}，'
           f'纬向净平流差为{a.x_total:+.3f}和{b.x_total:+.3f}°C/标准月，主设置中经向差异贡献更大。'
           '异常纬向流作用于背景温度梯度的负差仍然明显，但被纬向非线性项的正差部分抵消。'
           '经向差异同时涉及温度异常的南北梯度与异常经向流：相对1997，温度结构线性项较大；相对2015，异常经向流线性项较大；非线性交互单独保留。'
           '经向净增暖在30、50、75m及过程去趋势/不去趋势的全部设置中均低于两个对照。'
           '因此，140°W暖水体积输送主要由纬向流变化解释，而局地水平平流增暖差异必须同时考虑经、纬向过程；纬向风动量诊断仅对应纬向流，不能直接作为经向差异的动力归因。')
    (OUT/'正文建议段落.txt').write_text(paper+'\n')
    main_table=main.reset_index()[['control']+TERMS]
    latregions=regions.query('depth_m==50 and background=="mean" and season=="JAS" and region in ["S_5_2","EQ_2_2","N_2_5"]').copy()
    latregions['region']=latregions.region.map(REGIONS)
    northsouth=regions.query('depth_m==50 and background=="mean" and season=="JAS" and region in ["south","north"]').copy()
    northsouth['region']=northsouth.region.map(REGIONS)
    six=regions.query('depth_m==50 and background=="mean" and season=="JAS"').copy()
    six=six[six.region.str.endswith(('_west','_east'))]
    comparison=pair.query('depth_m==50 and background=="mean"')[['control','season','x_total','y_total','horizontal_total']]
    sensitivity=sens[['control','depth_m','background','x_total','y_total','horizontal_total']]
    sections=[
        ('结果：完整经向项在主设置中贡献更大',paper,main_table),
        ('经向差异来自什么',
         '三项分别为−v̄∂yT′（温度异常梯度在背景流作用下的变化）、−v′∂yT̄（异常经向流在背景温度梯度上的作用），以及中心化后的−v′∂yT′交互项。'
         '相对1997分别为−0.1034、−0.0668、+0.0256；相对2015分别为−0.0934、−0.1480、+0.1105°C/标准月。'
         '不能把它们统一简化为“2023经向流速较小”，也不把正交互项解释为某个已识别的混合机制。',
         main_table[['control','y_temperature','y_velocity','y_nonlinear','y_total']]),
        ('空间位置：南北两侧及赤道带均有负贡献',
         '固定三纬带的经向净项对两个对照均为负。下表是对整个Niño3.4均值的贡献，三纬带之和精确复现全区；不是把三个子区均值相加。',
         latregions[['control','region','y_temperature','y_velocity','y_nonlinear','y_total']]),
        ('南北半区：北侧异常流项、南侧温度结构项较突出',
         '北半区的异常经向流项贡献分别为−0.0846、−0.1123°C/标准月；南半区温度结构项分别为−0.0646、−0.0792。'
         '两组对照中，这两类区域贡献在全部六设置下均为负。这里的作用由流速与温度梯度逐格相乘确定，不能从区域平均v的大小直接推断。',
         northsouth[['control','region','y_temperature','y_velocity','y_nonlinear','y_total']]),
        ('AMJ与JAS同口径比较','两季均采用逐月诊断后等权平均；数据保留三个发展年的全部12个月。',comparison),
        ('六种设置：经向负差方向一致',
         '两个对照的经向净项在全部六设置中均为负。相对1997为−0.161至−0.095，相对2015为−0.135至−0.104°C/标准月。'
         '纬向净差对去趋势更敏感；相对1997的75m去趋势设置中，纬向正差略大于经向负差，水平合计接近零（+0.0059）。'
         '因此“经向净项较弱”的方向稳定，但“水平总平流在所有设置都较弱”或“经向幅度在每个设置都最大”均不应写。设置不作独立样本或显著性检验。',sensitivity),
        ('东西位置补充','west=170°W—140°W，east=140°W—120°W；与三纬带构成六个不重叠区域，全部数值按全区有效体积归一化。',
         six[['control','region','y_temperature','y_velocity','y_nonlinear','y_total']])]
    lines=['三事件完整经纬向平流补充诊断','']
    for title,text,table in sections:
        lines += [title,text,table.rename(columns=NAMES).round(6).to_string(index=False),'']
    lines += ['方法与核验',
              '仅用已冻结温度/u/v和原共同掩膜。逐格计算球面水平梯度与乘积，采用真实层界、有效层厚及球面面积积分。'+
              '非线性项减去自身同月背景；去趋势作用于完成定义的过程序列。全部单位为°C/标准月（365.25/12天）。',
              f'全43年旧水平总量及原五项均复现；保存地图积分、分区相加与月季平均独立核验通过，最大误差{max(checks.values()):.3g}°C/标准月。',
              '结论边界：本轮为局地温度平流诊断，不等同于南北边界热输送，不新增经向动量归因。输入、原动量诊断与模型不改；主图M4平流面板及当前汇报正文更新，M5仍解释纬向流。',
              '本轮完成即停止，不扩大资料范围或追加变量。']
    (OUT/'结果与解释.txt').write_text('\n'.join(lines)+'\n')
    parts=[]
    for title,text,table in sections:
        parts.append('<section><h2>'+html.escape(title)+'</h2><p>'+html.escape(text)+'</p><div class="table">'+
                     table.rename(columns=NAMES).round(4).to_html(index=False,border=0)+'</div></section>')
    development=monthly.query('depth_m==50 and background=="mean"').copy()
    development['month']=development.time.dt.month
    development=development[['event','month','x_total','y_total','horizontal_total']].sort_values(['event','month'])
    parts.append('<section><h2>发展年1—12月：50m主设置</h2><p>列出三个事件的完整年内演变，不只筛选AMJ/JAS；另外五种设置保存在月表中。</p><details><summary>展开36个月的完整经、纬向平流</summary><div class="table">'+
                 development.rename(columns={**NAMES,'event':'事件年','month':'月份'}).round(4).to_html(index=False,border=0)+'</div></details></section>')
    links=['结果与解释.txt','正文建议段落.txt','protocol_before_run.txt','directional_case_monthly.csv',
           'directional_case_seasons.csv','directional_pair_seasons.csv','regional_pair_seasons.csv',
           'region_volume_fractions.csv','directional_spatial.nc','validation.json','independent_validation.json','input_manifest.json','reproduce.txt']
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>三事件经纬向平流补充诊断</title><style>body{font:16px/1.8 Arial,"PingFang SC",sans-serif;background:#f5f7f8;color:#182b39;margin:0}main{max-width:1140px;padding:35px 24px;margin:auto}h1{font-size:29px}h2{font-size:21px}section{background:white;padding:24px;margin:24px 0;border:1px solid #dce4e9}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px 12px;border-bottom:1px solid #dce4e9;text-align:right;white-space:nowrap}.table{overflow:auto}a{color:#006e9b}.lead{font-size:20px;font-weight:bold;border-left:5px solid #0072b2;padding:15px 20px;background:white}</style><main>
<h1>局地水平平流差异：经向贡献需要进入主线</h1><p class="lead">完整拆分后，经向净平流是50m主设置中更大的差异来源；纬向异常流的负贡献受到非线性补偿。</p>
<p>1997、2015、2023；Niño3.4；AMJ/JAS；0—30/50/75m；1982—2024全部43年背景。表中平流单位统一为°C/标准月。</p>
<p><a href="../three_event_scientific_figures_20261015/index.html#M4_transport_current_advection">查看更新后的主图4</a> · <a href="../three_event_summer_current_dynamics_20261015/index.html">原纬向流专项诊断（历史结果）</a></p>'''+''.join(parts)+'''
<section><h2>来源与复现</h2><p>仅使用已存温度和u/v，原海洋掩膜、梯度算法和过程去趋势口径保持。非线性项先减同月背景，逐格乘积后积分。所有数值核验通过；完整方法和哈希保存在下列文件。</p><ul>'''+''.join(f'<li><a href="{n}">{n}</a></li>' for n in links)+'''</ul><p>本轮完成，不追加资料或经向动量模式。完整经、纬向温度平流是运动学分解；北南边界热输送与因果动力归因不由这些数值直接给出。</p></section></main></html>'''
    (OUT/'index.html').write_text(page)
    scripts=['analyze_three_event_directional_advection.py','report_three_event_directional_advection.py']
    runtime={'data':'SODA3.15.2, existing local cache; no new download',
        'numpy':np.__version__,'pandas':pd.__version__,'xarray':xr.__version__,
        'scripts_sha256':{n:hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest() for n in scripts},
        'input_manifest':'input_manifest.json','protocol':'protocol_before_run.txt'}
    (OUT/'source_and_runtime_manifest.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n')
    (OUT/'reproduce.txt').write_text('''Analysis (preserves original inputs):
OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python -B scripts/analyze_three_event_directional_advection.py
OPENBLAS_NUM_THREADS=1 /opt/anaconda3/bin/python -B scripts/report_three_event_directional_advection.py

Update the current M4 after archiving it:
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/private/tmp/maryland_story_mpl /opt/anaconda3/bin/python -B scripts/update_three_event_mechanism_figures.py --m4-only

Render and visually inspect the updated PDF before recording its review:
/Users/daiyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B scripts/package_three_event_figure_gallery.py --record-directional-visual-review
''')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
