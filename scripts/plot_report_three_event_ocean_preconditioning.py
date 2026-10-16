"""Publication-style figures and a Chinese results draft for the three cases."""
from pathlib import Path
import argparse
import html
import json
import os
import re
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/maryland_three_events_mpl')
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from analyze_three_event_ocean_preconditioning import OUT, ROOT, EVENTS, CASE_YEARS, REGIONS, EDGES, BASE

COLORS = {'west': '#527a9a', 'central': '#d29239', 'east': '#b85554', 'basin': '#242933'}
BLUE, RED, GRAY = '#2878a4', '#bc584f', '#8b9299'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 11,
                     'axes.labelsize': 10, 'legend.fontsize': 8, 'legend.frameon': False,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': .75,
                     'savefig.facecolor': 'white', 'svg.fonttype': 'none'})
FIGURES = []


def save(fig, stem, caption):
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(OUT/f'{stem}.{ext}', dpi=220, bbox_inches='tight')
    FIGURES.append((stem, caption))
    plt.close(fig)


def month_axis(ax, event, ylabel=None):
    ax.set_xlim(0, 23)
    ax.set_xticks([0, 6, 12, 18, 23], [f'Jan {event-1}', 'Jul', f'Jan {event}', 'Jul', 'Dec'])
    ax.axvline(12, color='.45', lw=.8, ls=':')
    ax.axhline(0, color='.65', lw=.6)
    if ylabel: ax.set_ylabel(ylabel)
    ax.tick_params(axis='x', labelsize=8)


def longitude_axis(ax):
    ax.set_xlim(120, 280)
    ax.set_xticks([120, 160, 180, 220, 260, 280], ['120°E', '160°E', '180°', '140°W', '100°W', '80°W'])
    ax.tick_params(axis='x', labelsize=8)
    for x in (180, 220): ax.axvline(x, color='.45', ls=':', lw=.65)


def event_slice(frame, event):
    return frame.loc[frame.time.dt.year.between(event-1, event)].sort_values('time')


def fig_airsea(ds, atm):
    sensitivity_path = OUT/'wind_reference_sensitivity_monthly.csv'
    sensitivity = pd.read_csv(sensitivity_path, parse_dates=['time']) if sensitivity_path.exists() else None
    fig, ax = plt.subplots(2, 3, figsize=(13.5, 9), layout='constrained')
    for j, e in enumerate(EVENTS):
        s = ds.sel(time=slice(f'{e-1}-01-01', f'{e}-12-31'))
        assert s.sizes['time'] == 24
        for i, key, lon, limit, unit in [(0, 'sst_anomaly', 'sst_lon', 3, '°C'), (1, 'tau_anomaly', 'tau_lon', .12, 'N m⁻²')]:
            im = ax[i,j].pcolormesh(s[lon], np.arange(24), s[key], shading='auto', cmap='RdBu_r', vmin=-limit, vmax=limit)
            longitude_axis(ax[i,j])
            ax[i,j].set_ylim(23.5, -.5)
            ax[i,j].set_yticks([0, 6, 12, 18, 23], [f'Jan {e-1}', 'Jul', f'Jan {e}', 'Jul', 'Dec'])
            ax[i,j].axhline(12, color='.2', ls='--', lw=.8)
            ax[i,j].set_title(f'({chr(97+i*3+j)}) {e-1}–{e} | '+('SST' if i==0 else 'Zonal wind stress'), loc='left')
            if j == 2:
                fig.colorbar(im, ax=ax[i,:], shrink=.85, label=unit, pad=.02, extend='both')
    fig.suptitle('1 | SST and surface wind-stress evolution\n5°S–5°N means · 1982–2022 monthly anomalies', fontsize=15)
    save(fig, 'Fig01_airsea_evolution', '图1：OISST 海温与 ERA5 纬向风应力的连续24个月经度—时间演变。海气剖面取赤道±5°，与用于储备收支的±9°区域区分；三事件共用色标。虚线标记发展年1月。此图展示对应与先后，不单独证明闭合反馈。')
    fig, ax = plt.subplots(2, 3, figsize=(13.5, 7.4), sharey='row', layout='constrained')
    for j,e in enumerate(EVENTS):
        d = event_slice(atm, e)
        x = np.arange(24)
        ax[0,j].fill_between(x, d.tau_expected_lo.to_numpy(), d.tau_expected_hi.to_numpy(), color=BLUE, alpha=.16)
        ax[0,j].plot(x, d.tau, color='#232a35', lw=1.8, label='Actual anomaly')
        ax[0,j].plot(x, d.tau_expected, color=BLUE, lw=1.8, ls='--', label='SST-conditioned expectation')
        ax[1,j].plot(x, d.tau_residual_z, color=RED, lw=1.8, label='Reference with trend')
        if sensitivity is not None:
            ss = event_slice(sensitivity.loc[sensitivity.reference.eq('full_no_trend')],e)
            if len(ss)==24: ax[1,j].plot(x,ss.residual_z,color=BLUE,lw=1.5,ls='--',label='Reference without trend')
        ax[1,j].axhspan(-1, 1, color='.9', alpha=.5)
        for i in range(2):
            month_axis(ax[i,j], e)
            ax[i,j].set_title(f'({chr(97+i*3+j)}) {e-1}–{e}', loc='left')
        if j==0:
            ax[0,j].legend(loc='upper left')
            ax[1,j].legend(loc='upper left')
    ax[0,0].set_ylabel('West-central Pacific τx′ (N m⁻²)')
    ax[1,0].set_ylabel('Actual − expected / reference residual SD')
    fig.suptitle('2 | Wind response relative to SST amplitude and pattern\nMonthly reference excludes all three event blocks; band = uncertainty of expected mean', fontsize=14)
    save(fig, 'Fig02_sst_conditioned_wind', '图2：160°E—140°W、±5°的实际风应力与海温条件下的预期响应。上排参考逐月考虑Niño3.4、Niño3−Niño4和线性时间项，排除1996—1998、2014—2016、2022—2024。蓝带为500次两年块自助法的预期均值95%区间，不是个例预测区间。下排并列含趋势与不含趋势的参考残差，各自按训练残差标准差归一；±1阴影不是显著性界限。±9°纬带敏感性另存表格。')


def fig_ocean(volume, ds):
    fig, ax = plt.subplots(2, 3, figsize=(13.5, 8), sharey='row', layout='constrained')
    for j,e in enumerate(EVENTS):
        d = event_slice(volume, e)
        for r in ['basin', *REGIONS]:
            ax[0,j].plot(np.arange(24), d[r+'_wwv_m3']/1e14, color=COLORS[r], lw=2 if r=='basin' else 1.5, label=r.capitalize())
        month_axis(ax[0,j], e)
        ax[0,j].set_title(f'({chr(97+j)}) {e-1}–{e}: WWV26′', loc='left')
        if j==0: ax[0,j].legend(ncol=2)
        q = ds.d26_anomaly.sel(time=f'{e}-01-15', lat=slice(-9, 9), lon=slice(120, 280))
        im = ax[1,j].pcolormesh(q.lon, q.lat, q, cmap='RdBu_r', vmin=-70, vmax=70, shading='auto')
        longitude_axis(ax[1,j]); ax[1,j].set_ylim(-9, 9)
        ax[1,j].set_yticks([-9, 0, 9], ['9°S', 'EQ', '9°N'])
        ax[1,j].set_title(f'({chr(100+j)}) January {e}: D26′', loc='left')
    ax[0,0].set_ylabel('Warm-water volume anomaly (10¹⁴ m³)')
    fig.colorbar(im, ax=ax[1,:], label='D26 anomaly (m)', pad=.02, shrink=.9, extend='both')
    fig.suptitle('3 | Ocean reserve and January spatial configuration\n9°S–9°N, 120°E–80°W · surface to instantaneous σθ = 26', fontsize=15)
    save(fig, 'Fig03_wwv26_configuration', '图3：统一±9°区域的全盆地与西/中/东三区WWV26异常，以及发展年1月D26厚度异常分布。三区边界为180°、140°W，三区体积之和等于全盆地。1月是共同季节参照，不自动表示三次事件共同的反馈启动前。')
    snapshots = [(0, 1, 'Previous January'), (0, 7, 'Previous July'), (1, 1, 'Development January'), (1, 7, 'Development July')]
    fig, ax = plt.subplots(4, 3, figsize=(13.5, 13), sharex=True, sharey=True, layout='constrained')
    for i,(offset,m,label) in enumerate(snapshots):
        for j,e in enumerate(EVENTS):
            y = e-1+offset
            q = ds.sel(time=f'{y}-{m:02d}-15')
            im = ax[i,j].pcolormesh(q.lon, q.depth, q.temperature_anomaly, shading='auto', cmap='RdBu_r', vmin=-3, vmax=3)
            for key, ls, color in [('d26', '-', '#292d33'), ('d26_climatology', '--', '#676c70')]:
                f = q[key] if key=='d26' else ds[key].sel(month=m)
                f = f.sel(lat=slice(-9,9)).weighted(np.cos(np.deg2rad(f.sel(lat=slice(-9,9)).lat))).mean('lat')
                ax[i,j].plot(f.lon, f, ls=ls, color=color, lw=1)
            ax[i,j].set_ylim(350,0)
            longitude_axis(ax[i,j])
            ax[i,j].set_title(f'({chr(97+i*3+j)}) {y}-{m:02d}', loc='left')
            if j==0: ax[i,j].set_ylabel(label+'\nDepth (m)')
    fig.colorbar(im, ax=ax, label='Potential-temperature anomaly (°C)', shrink=.65, pad=.015, extend='both')
    fig.suptitle('4 | Vertical structure before and during development\n9°S–9°N mean · solid / dashed: actual / climatological D26', fontsize=15)
    save(fig, 'Fig04_temperature_vertical_structure', '图4：前一年1月、7月及发展年1月、7月的纬向—深度位温异常。±9°纬向平均；实线/虚线分别为实际/气候态D26。图只显示上350m，WWV26仍积分到真实密度面，没有改成固定350m储备。剖面揭示暖异常所在深度，但不是混合层升温收支。')


def fig_transports(budget, heat):
    fig, ax = plt.subplots(3,3, figsize=(13.5, 10.5), sharey='row', layout='constrained')
    for i,r in enumerate(REGIONS):
        for j,e in enumerate(EVENTS):
            d = budget.loc[budget.event.eq(e)&budget.region.eq(r)&budget.baseline_method.eq('anomalies')&budget.window.eq('full_window')].sort_values('time')
            for k,label,color,ls in [('storage_change','Storage change','#242933','-'), ('zonal_input','Zonal convergence',BLUE,'-'),
                                      ('meridional_input','Meridional convergence',RED,'-'),('unresolved','Unresolved',GRAY,'--')]:
                ax[i,j].plot(np.arange(24), d[k], color=color, ls=ls, lw=1.8 if k=='storage_change' else 1.4, label=label)
            month_axis(ax[i,j], e)
            ax[i,j].set_title(f'({chr(97+i*3+j)}) {e}: {r.capitalize()}', loc='left')
            if j==0: ax[i,j].set_ylabel('Cumulative anomaly (10¹⁴ m³)')
    ax[0,0].legend(ncol=1, fontsize=8)
    fig.suptitle('5 | Horizontal redistribution and storage change\nCumulative from Jan 15 of the previous year; no imposed budget closure', fontsize=15)
    save(fig, 'Fig05_volume_transport_and_storage', '图5：自前一年1月15日起累计的纬向辐合、经向辐合与暖水体积异常变化。未解析项=储量变化−水平辐合，包含跨等密度面转化及资料/离散误差，不能命名为散热或已识别物理通道。图中不同事件共用区域内纵轴。')
    fig, ax = plt.subplots(3,3, figsize=(13.5, 10.5), sharey='row', layout='constrained')
    output=[]
    for i,r in enumerate(REGIONS):
        west,east = EDGES[r]
        for j,e in enumerate(EVENTS):
            d = heat.loc[heat.time.dt.year.between(e-1,e)&heat.geometry.eq('instantaneous')]
            coverage=[]
            for term,color in [('mean_flow_temperature_anomaly_pw',BLUE), ('anomalous_flow_mean_temperature_pw',RED)]:
                tab=d.pivot(index='time',columns='gate',values=term).sort_index()
                for direction, plus,minus,ls in [('Zonal',west,east,'-'),('Meridional',r+'_south',r+'_north','--')]:
                    val=tab[plus]-tab[minus]
                    label=direction+(' mean flow × T′' if color==BLUE else ' flow′ × mean T')
                    ax[i,j].plot(np.arange(24),val,color=color,ls=ls,lw=1.4,label=label)
                    for t,v in val.items(): output.append({'event':e,'region':r,'time':t,'direction':direction,'term':term,'convergence_pw':v})
            cv=d.loc[d.gate.isin([west,east,r+'_south',r+'_north'])&d.active_area_m2.gt(0),'area_coverage'].min()
            month_axis(ax[i,j],e)
            ax[i,j].set_title(f'({chr(97+i*3+j)}) {e}: {r.capitalize()} | coverage ≥{cv:.0%}',loc='left',fontsize=10)
            if j==0: ax[i,j].set_ylabel('Two-term heat convergence (PW)')
    handles,labels=ax[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=2,fontsize=9)
    fig.suptitle('6 | Mean-flow and anomalous-flow heat contributions\nMoving σ26 sections · temperature reference 0°C · separate from volume budget',fontsize=14)
    save(fig,'Fig06_two_term_heat_transport','图6：三区边界上的两项热输送辐合，实线为东西向，虚线为南北向。蓝色为平均流携带温度异常，红色为异常流携带背景温度。只在基期41年完整有效的格点计算；各面有效面积比例保存在原始表，覆盖不足的净贡献不能当成完整区域热收支。移动断面背景变化和非线性项未包含；异常流项也不是纯风驱因果贡献。')
    pd.DataFrame(output).to_csv(OUT/'regional_two_term_heat_convergence.csv',index=False)


def report():
    initial=pd.read_csv(OUT/'january_ocean_initial_states.csv')
    quarterly=pd.read_csv(OUT/'development_quarterly_airsea_summary.csv')
    ends=pd.read_csv(OUT/'budget_window_summary.csv')
    qa=json.loads((OUT/'numerical_QA.json').read_text())
    co=pd.read_csv(OUT/'descriptive_sst_wind_cooccurrence.csv')
    sensitivity=pd.read_csv(OUT/'wind_reference_sensitivity_quarterly.csv')
    nt=sensitivity.loc[sensitivity.reference.eq('full_no_trend')&sensitivity.event.eq(2023)].set_index('quarter')
    jan=initial.loc[initial.baseline_method.eq('anomalies')].set_index('event')
    jan_trend=initial.loc[initial.baseline_method.eq('trend_sensitivity')].set_index('event')
    def nums(col): return '、'.join(f'{y}年 {jan.loc[y,col]:+.2f}' for y in EVENTS)
    def qnums(phase,col):
        q=quarterly.loc[quarterly.phase.eq(phase)].set_index('event')
        return '、'.join(f'{y}年 {q.loc[y,col]:+.2f}' for y in EVENTS)
    ordering={r: {'monthly_mean':jan[r+'_wwv_1e14m3'].sort_values(ascending=False).index.tolist(),
                  'monthly_trend':jan_trend[r+'_wwv_1e14m3'].sort_values(ascending=False).index.tolist()} for r in ['basin',*REGIONS]}
    changed=[r for r,v in ordering.items() if v['monthly_mean']!=v['monthly_trend']]
    pre=ends.loc[ends.baseline_method.eq('anomalies')&ends.window.eq('preconditioning')]
    dev=ends.loc[ends.baseline_method.eq('anomalies')&ends.window.eq('development')]
    d23=dev.loc[dev.event.eq(2023)].set_index('region')
    thermal=pd.read_csv(OUT/'january_thermal_structure.csv',parse_dates=['time'])
    residual_ratio=(abs(ends.unresolved)/(abs(ends.zonal_input)+abs(ends.meridional_input)).replace(0,np.nan))
    co05=co.loc[co.sst_threshold_C.eq(.5)].set_index('event')
    ctext='；'.join(f'{y}年共{int(co05.loc[y,"months_joint_positive"])}个月、最长连续{int(co05.loc[y,"longest_run_months"])}个月' for y in EVENTS)
    paragraphs = [
        ('1. 三次事件海温—西风演变及相对于海温的响应差异',[
          '以1996—1997、2014—2015及2022—2023连续月序列进行比较。图1显示海温与风应力的时空对应，图2进一步控制海温强度、东西向型态和背景趋势。风应力残差仅表示偏离统计预期，不等同于外部强迫，也不是整个海气反馈强度。',
          f'发展年AMJ的Niño3.4异常（°C）分别为：{qnums("AMJ","nino34")}；同期风应力残差（参考标准差）为：{qnums("AMJ","tau_residual_z")}。JAS残差为：{qnums("JAS","tau_residual_z")}；OND残差为：{qnums("OND","tau_residual_z")}。因此需按季节比较，不宜用一个全年标签代替阶段演变。',
          f'这一判断对参考关系是否包含趋势项敏感：不含趋势项时，2023年AMJ/JAS/OND残差分别为{nt.loc[2,"residual_z"]:+.2f}/{nt.loc[3,"residual_z"]:+.2f}/{nt.loc[4,"residual_z"]:+.2f}个参考标准差。因此不能无条件断言2023“正常”或“异常不足”。较稳定的比较是1997/2015春夏的风响应残差高于2023；模型定义对绝对归类的影响必须与物理机制区分。',
          f'采用仅用于描述的“月Niño3.4>0.5°C且中西太平洋风应力异常>0”共同条件，发展年的共现情况为：{ctext}。0.3/0.8°C阈值敏感性见附表；这不是ENSO事件判据，也不据此认定闭合反馈开始。',
          '图2置信带只反映预期均值的重采样不确定度，不能按是否越出蓝带判定单个月异常显著。拟合参考年逐年留出误差、逐月系数和±9°纬带敏感性均另存。']),
        ('2. 共同1月参照下的暖水储备与空间配置',[
          f'按统一±9°、120°E—80°W、瞬时σθ=26下边界重算，发展年1月全盆地WWV26异常（10¹⁴ m³）为：{nums("basin_wwv_1e14m3")}。西区为：{nums("west_wwv_1e14m3")}；中区为：{nums("central_wwv_1e14m3")}；东区为：{nums("east_wwv_1e14m3")}。',
          '图3同时给出体积曲线和1月密度面厚度异常，图4检查温度异常的垂直位置。总量、东西向配置和温度结构是不同信息；WWV26是体积，不能直接换算为热含量或海表温度。',
          '在当前统一口径下，2023年1月全盆地储备异常高于2015年，主要正异常集中在西区，而东区为负；1997年三区均为正异常。这一对比不支持仅用“2023总储备不足”解释后续差异，而把空间配置提出为需要进一步检验的因素。密度面位置受温盐共同影响，不能只凭其加深就判为温度升高。',
          '温度剖面提供了进一步区分：2023年1月西区50—150m剖面平均温度异常约+1.98°C，而中区0—50m约−0.70°C、东区50—150m约−0.77°C，体现出西部次表层暖异常与中东部上层条件的差异。这些量是剖面温度诊断，既不是OHC，也不与标准Niño海温指数直接等同。',
          ('改用逐月线性趋势基准后，1月事件排序发生变化的区域为：'+ '、'.join(changed)+'；相关强弱结论必须保留基准依赖。') if changed else '改用逐月线性趋势基准后，全盆地及三区1月异常的三事件排序均保持；幅度仍会变化。',
          '1月用于相同季节下的状态比较；特别是已有前期暖事件演变的案例，不能将其统一称为反馈发生之前。本阶段尚未完成独立的混合层温度收支，垂直结构仅提供热异常接近海表的结构证据。']),
        ('3. 前期形成与发展期重新分配的输送诊断',[
          '分别积分前一年1月15日至发展年1月15日，以及发展年1月15日至12月15日。体积通量取西入减东出、南入减北出；先逐月计算异常再按实际秒数积分，明确它不是完整自然年的1月1日至12月31日积分。',
          '表中分别列出储量变化、纬向净输入、经向净输入和未解析项。图5保留完整24个月累计轨迹，避免只用端点比较忽略中途的储备转移。',
          f'2023年发展期中区储量变化为{d23.loc["central","storage_change"]:+.2f}×10¹⁴m³，纬向净输入{d23.loc["central","zonal_input"]:+.2f}、经向净输入{d23.loc["central","meridional_input"]:+.2f}、未解析项{d23.loc["central","unresolved"]:+.2f}，在这个区域与窗口内水平输送与储量变化接近对应。同期西区储量变化{d23.loc["west","storage_change"]:+.2f}，水平净输入合计{(d23.loc["west","zonal_input"]+d23.loc["west","meridional_input"]):+.2f}，未解析项{d23.loc["west","unresolved"]:+.2f}；因此西区损失不能直接解释成水平向东输出。以上单位均为10¹⁴m³，所有其他案例与区域同时列出，不能将中区的近似闭合推广到全盆地。',
          '图6将两项热输送作为独立诊断：平均流携带温度异常，以及异常流携带背景温度。比较其时间变化可以提出流场或温度场作用的候选解释，但不能把两项直接等同于体积变化，也不能把异常流项自动归因于风。',
          '未解析项保留移动密度面跨面转化、同化、重网格和离散误差的共同影响。本分析没有将水平输送强制修正到闭合，也没有将残差命名为海表散热。']),
        ('4. 当前证据对海洋先分化假说的约束及模型下一步',[
          '目前完成的是三个案例的统一过程诊断。1月海洋差异及其前一年形成过程可用于构建海洋初态假说，但“存在差异”本身尚不能证明其导致后续西风响应不同。需结合全部时空演变识别具体分化阶段。',
          '不预先把1997和2015归为一类，也不将2023概括为暖水未到达。只要部分阶段或区域呈相反证据，均保留在结果中。',
          '尚未实施3×3动力模型试验。下一步选择能保留关键空间信息的最小海洋状态，在统一参数下固定海温初态、替换海洋状态；先检验三个原事件组合，再解释替换差值。不同海洋状态与给定海温的物理一致性需要单独检查。'])]
    sections=[]
    figure_map={0:[0,1],1:[2,3],2:[4,5]}
    for i,(title,ps) in enumerate(paragraphs):
        block=f'<section><h2>{html.escape(title)}</h2>'+''.join(f'<p>{html.escape(p)}</p>' for p in ps)
        if i==0:
            table=quarterly[['event','phase','nino34','tau','tau_expected','tau_residual_z']].rename(columns={'event':'事件','phase':'季节','nino34':'Niño3.4 (°C)','tau':'实际τ′ (N m⁻²)','tau_expected':'预期τ′ (N m⁻²)','tau_residual_z':'残差 (SD)'})
            block+=table.to_html(index=False,float_format=lambda x:f'{x:.3f}',classes='data')
        if i==1:
            block+=jan.drop(columns='baseline_method').rename(columns={'basin_wwv_1e14m3':'全盆地','west_wwv_1e14m3':'西区','central_wwv_1e14m3':'中区','east_wwv_1e14m3':'东区'}).to_html(float_format=lambda x:f'{x:.3f}',classes='data')
            block+='<h3>逐月趋势基准敏感性（10¹⁴ m³）</h3>'+jan_trend.drop(columns='baseline_method').rename(columns={'basin_wwv_1e14m3':'全盆地','west_wwv_1e14m3':'西区','central_wwv_1e14m3':'中区','east_wwv_1e14m3':'东区'}).to_html(float_format=lambda x:f'{x:.3f}',classes='data')
            tt=thermal.copy();tt['事件']=tt.time.dt.year;tt['层段']=tt.layer_top_m.astype(int).astype(str)+'–'+tt.layer_bottom_m.astype(int).astype(str)+' m'
            tt=tt.pivot(index=['事件','region'],columns='层段',values='profile_mean_temperature_anomaly_C')
            block+='<h3>1月垂直结构辅助诊断（温度异常，°C）</h3>'+tt.to_html(float_format=lambda x:f'{x:.3f}',classes='data')
        if i==2:
            for label,table in [('前期形成窗口（10¹⁴ m³）',pre),('发展期窗口（10¹⁴ m³）',dev)]:
                block+='<h3>'+label+'</h3>'+table[['event','region','storage_change','zonal_input','meridional_input','unresolved']].rename(columns={'event':'事件','region':'区域','storage_change':'储量变化','zonal_input':'纬向输入','meridional_input':'经向输入','unresolved':'未解析'}).to_html(index=False,float_format=lambda x:f'{x:.3f}',classes='data')
        for n in figure_map.get(i,[]):
            stem,cap=FIGURES[n]
            block+=f'<figure><a href="{stem}.png"><img src="{stem}.png" alt="{html.escape(cap)}"></a><figcaption>{html.escape(cap)} <a href="{stem}.pdf">PDF</a> · <a href="{stem}.svg">SVG</a></figcaption></figure>'
        sections.append(block+'</section>')
    methods='''主分析仅包含1997、2015、2023三个案例；每例前一年1月至发展年12月。SODA3.15.2官方年度温盐流速子集用于WWV26和输送，沿用已核对的年度12个月顺序、TEOS-10密度、分层部分厚度与湿掩膜处理。基期为1982—2022逐月平均，不带通、不平滑；体积另给逐月趋势基准敏感性。全盆地和三区均为9°S—9°N，三区120°E—180°、180°—140°W、140°W—80°W；西部边缘海沿用原盆地掩膜保留，不能称为纯内部STC。海气指数采用标准±5°Niño海区，风应力为±5°、160°E—140°W，并给±9°敏感性。统计参照使用1982—2024，排除三个事件的前一年、发展年和次年，共34年；气候态与参考关系训练样本是两个不同用途的样本集合。两项热通量使用温度参照0°C、ρ=1025 kg m⁻³、cp=3990 J kg⁻¹ K⁻¹；单断面净体积流不为零时热通量依赖温度参照。线性两项不包含完整背景和非线性变化，不能称作闭合热收支。'''
    links=['january_ocean_initial_states.csv','january_thermal_structure.csv','january_spatial_partition_diagnostic.csv','development_quarterly_airsea_summary.csv','budget_window_summary.csv','two_term_heat_transport.csv','wind_reference_coefficients.csv','wind_reference_sensitivity_quarterly.csv','evidence_table.csv','ocean_case_fields.nc','atmosphere_monthly.nc','numerical_QA.json','validation_results.json']
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>三次ENSO事件：海洋预置与海气响应</title><style>
body{margin:0;background:#f3f5f7;color:#202c38;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1200px;margin:auto;padding:44px 28px 70px}header{border-top:5px solid #2878a4;padding:24px 0}h1{font-size:32px;line-height:1.4}h2{font-size:24px;color:#183e56}h3{font-size:18px}section{background:white;margin:24px 0;padding:28px;border:1px solid #dbe3e8;border-radius:8px}p{max-width:1000px}figure{margin:30px 0}img{width:100%;height:auto}figcaption{font-size:14px;color:#4d5f6d;line-height:1.7}a{color:#17608c}table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow:auto}th,td{padding:8px 13px;border-bottom:1px solid #dae2e8;white-space:nowrap;text-align:right}th{background:#eff4f7}small{color:#526776}.note{border-left:4px solid #b98c38;padding:12px 18px;background:#fff9ec}@media print{body{background:white}section{border:0;break-inside:auto}figure{break-inside:avoid}main{padding:0}}
</style><main><header><small>研究阶段 · 论文结果初稿 · 2026-10-14</small><h1>三次 ENSO 事件的海洋预置、输送与海气响应</h1><p>1996—1997 / 2014—2015 / 2022—2023 · 统一WWV26定义与三区收支</p><div class="note">本版完成结果1—3的数据诊断。优先假说为“海洋条件先分化”，但尚未作因果定论，也未运行简化动力模型。</div></header>'''
    page+=''.join(sections)+f'<section><h2>方法、复现与证据边界</h2><p>{html.escape(methods)}</p>'
    page+='<p>理论方法来源：<a href="https://doi.org/10.1175/JCLI-D-14-00134.1">Chen et al. (2015)</a>，并结合用户草稿纸的输送乘积分解。这里的统一三区及三事件24个月对比属于本项目扩展。</p>'
    page+='<p>数值检查：三区相加的最大相对误差 '+f'{qa["ocean"]["three_region_sum_max_relative_error"]:.2e}'+'；所有72个案例月齐全；目标事件未进入风响应参考拟合。体积收支代数闭合只是残差定义检查，不等于物理收支闭合。</p>'
    page+='<p>'+' · '.join(f'<a href="{p}">{p}</a>' for p in links)+'</p></section></main></html>'
    (OUT/'论文结果初稿_海洋预置与海气响应.html').write_text(page,encoding='utf-8')
    text='三次ENSO事件：海洋预置、输送与海气响应\n论文结果初稿；研究阶段；2026-10-14\n\n'
    for title,ps in paragraphs: text+=title+'\n\n'+'\n\n'.join(ps)+'\n\n'
    text+='方法\n'+methods+'\n\n图注\n'+'\n\n'.join(cap for _,cap in FIGURES)
    (OUT/'论文结果文字与图注.txt').write_text(text,encoding='utf-8')
    (OUT/'methods_and_reproduction.txt').write_text('Three-case research diagnostics, not a replication of all Chen (2015) results.\nRun analyze_three_event_ocean_preconditioning.py, then plot_report_three_event_ocean_preconditioning.py.\nUse the existing scientific Python runtime with numpy, pandas, xarray, scipy, gsw, h5netcdf and matplotlib.\nOcean geometry routines imported from analyze_chen2015_reanalysis.py; regional definitions, baseline and reference exclusions are newly calculated.\nNo historical output is overwritten. NetCDF exports use the scipy engine.\nCommon 1982-2022 anomalies; wind reference uses 1982-2024 minus 1996-98, 2014-16, 2022-24.\nMonthly-center volume integration uses actual elapsed seconds. Shared gates cancel by construction; unresolved budget terms remain explicit.\nNo new dynamical model has been run.\n',encoding='utf-8')
    save={'january_event_order_sensitivity':ordering,'figures':[s for s,_ in FIGURES], 'draft_claims_are_causal':False}
    (OUT/'report_QA.json').write_text(json.dumps(save,ensure_ascii=False,indent=2),encoding='utf-8')
    evidence=[
        {'question':'2023是否只有较少总储备？','status':'本次1月比较不支持','evidence':f'2023/2015全盆地WWV26异常={jan.loc[2023,"basin_wwv_1e14m3"]:.3f}/{jan.loc[2015,"basin_wwv_1e14m3"]:.3f}×10^14m3','limit':'只限指定1月与WWV26定义；不是热含量'},
        {'question':'2023是否存在西部偏多、东部偏少的配置？','status':'当前资料支持','evidence':'西区正、东区负；逐月趋势基准保持该符号组合','limit':'配置差异不自动证明后续海气作用'},
        {'question':'2023风响应是否异常低于海温预期？','status':'参考模型依赖','evidence':'加入趋势后春夏残差近零，不加趋势约−1 SD','limit':'不将一种参考设定当作唯一真实反馈'},
        {'question':'水平输送是否完整解释储量变化？','status':'区域依赖，整体未闭合','evidence':f'2023发展期中/西区未解析项={d23.loc["central","unresolved"]:.3f}/{d23.loc["west","unresolved"]:.3f}×10^14m3','limit':'未解析项不是已识别的散热或水团转化'},
        {'question':'海洋初态是否导致后续响应分化？','status':'尚待模型检验','evidence':'已有统一空间、垂直与输送诊断；3×3动力模型尚未运行','limit':'三个案例的时序与相关不能替代因果检验'}]
    pd.DataFrame(evidence).to_csv(OUT/'evidence_table.csv',index=False)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report-only',action='store_true')
    args=parser.parse_args()
    captions=OUT/'figure_captions.json'
    if args.report_only:
        if captions.exists():
            FIGURES.extend(json.loads(captions.read_text()))
        else:
            old=(OUT/'论文结果初稿_海洋预置与海气响应.html').read_text()
            FIGURES.extend((name,html.unescape(cap)) for name,cap in re.findall(r'<figure><a href="([^\"]+)\.png">.*?<figcaption>(.*?) <a href=',old))
        assert len(FIGURES)==6
        captions.write_text(json.dumps(FIGURES,ensure_ascii=False,indent=2),encoding='utf-8')
        report()
        print('Results text and evidence table updated',flush=True)
        return
    atm=pd.read_csv(OUT/'atmosphere_anomaly_and_reference.csv',parse_dates=['time'])
    vol=pd.read_csv(OUT/'ocean_monthly_anomalies.csv',parse_dates=['time'])
    budget=pd.read_csv(OUT/'cumulative_volume_budget.csv',parse_dates=['time'])
    heat=pd.read_csv(OUT/'two_term_heat_transport.csv',parse_dates=['time'])
    with xr.open_dataset(OUT/'atmosphere_monthly.nc',engine='scipy') as d:
        fig_airsea(d.load(),atm)
    print('Figures 1-2 ready',flush=True)
    with xr.open_dataset(OUT/'ocean_case_fields.nc',engine='scipy') as d:
        fig_ocean(vol,d.load())
    print('Figures 3-4 ready',flush=True)
    fig_transports(budget,heat)
    captions.write_text(json.dumps(FIGURES,ensure_ascii=False,indent=2),encoding='utf-8')
    report()
    print('Six figures and paper results draft ready:',OUT,flush=True)


if __name__=='__main__': main()
