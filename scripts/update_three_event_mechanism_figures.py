"""Replace the last gallery group with two styled summer-mechanism figures.

Only reads the completed diagnostics. Does not recompute climate statistics.
The first five figures remain byte-for-byte unchanged in update mode.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import zipfile
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.integrate import cumulative_trapezoid

ROOT = Path(__file__).resolve().parents[1]
DYN = ROOT / 'outputs/research_2026/three_event_summer_current_dynamics_20261015'
DIRECTIONAL = ROOT / 'outputs/research_2026/three_event_directional_advection_20261015'
KEEP = ['M1_air_sea_evolution', 'M2_JFM_configuration',
        'M3_transport_persistence', 'S1_wind_reference', 'S2_local_process_limits']
NEW = ['M4_transport_current_advection', 'M5_wind_current_momentum']
DATA = ['section_pair_monthly.csv', 'section_pair_seasons.csv',
        'section_reference_sensitivity_monthly.csv', 'case_monthly.csv',
        'case_seasons.csv', 'momentum_pair_intervals.csv',
        'wind_product_comparison.csv', 'spatial_diagnostics.nc',
        'background_and_mask_bridge_JAS.csv', 'protocol_before_run.txt',
        'validation.json', 'source_and_runtime_manifest.json']
FORCE = ['wind', 'pressure_ssh', 'pressure_density', 'coriolis',
         'advection', 'unresolved']
FC = ['#0072B2', '#B98200', '#77549A', '#21847B', '#8C654C', '#B65C80']
FL = ['Wind', 'Sea-level pressure', 'Density pressure', 'Coriolis',
      'Horizontal advection + metric', 'Unresolved']


def months(ax, base):
    base.months(ax)
    ax.axvspan(3.5, 6.5, color='#DBEAF0', alpha=.6, zorder=-2)
    ax.axvspan(6.5, 9.5, color='#FAEBD1', alpha=.65, zorder=-2)


def case(df, year):
    return df[(df.depth_m == 50) & (df.background == 'mean') &
              (df.time.dt.year == year)].sort_values('time').reset_index(drop=True)


def force_values(df, key):
    if key == 'advection':
        return df.horizontal_advection_m_s2 + df.metric_m_s2
    return df[key + '_m_s2']


def render_figures(base, pdf, *, m4_only=False):
    """Also called by the complete figure builder, to preserve the new selection."""
    base.style()
    local = pd.read_csv(DYN / 'case_monthly.csv', parse_dates=['time'])
    seasonal = pd.read_csv(DYN / 'case_seasons.csv')
    sec = pd.read_csv(DYN / 'section_pair_seasons.csv')
    wind = pd.read_csv(DYN / 'wind_product_comparison.csv', parse_dates=['time'])
    seas = seasonal[(seasonal.depth_m == 50) & (seasonal.background == 'mean') &
                    (seasonal.season == 'JAS')].set_index('event')

    fig = base.figbase(9.4, 'Upper-ocean currents explain the summer transport contrast',
        'SODA3.15.2; 1982-2024 monthly background. All contrasts: 2023 minus control.\n'
        'Section: 140°W, 9°S-9°N, surface to σθ = 26. Local: Niño3.4, 0-50 m.\n'
        'AMJ / JAS shading marks the seasonal windows. No additional smoothing.')
    fig.set_size_inches(10.4,9.4)
    plt.rcParams.update({'font.size':9,'axes.labelsize':9,'xtick.labelsize':8.5,'ytick.labelsize':8.5})
    axes=np.array([
        [fig.add_axes([left,.79,.35,.16]) for left in [.085,.565]],
        [fig.add_axes([left,.285,.445,.425]) for left in [.035,.515]],
        [fig.add_axes([left,.055,.35,.16]) for left in [.085,.565]]])
    bands = ['0_50', '50_150', '150_sigma26', 'all']
    for j, control in enumerate([1997, 2015]):
        ax = axes[0, j]
        q = sec[(sec.control == control) & (sec.season == 'JAS')].set_index('band').loc[bands]
        x = np.arange(4)
        ax.bar(x-.17, q.current_sv, .31, color='#0072B2', label='Velocity')
        ax.bar(x+.17, q.thickness_sv, .31, color='#B98200', label='Warm-layer thickness')
        ax.scatter(x, q.total_sv, marker='D', s=17, color=base.BLACK, label='Total', zorder=3)
        base.zero(ax)
        ax.set_xticks(x, ['0-50', '50-150', '>150', 'All'])
        ax.set_xlabel('Warm-layer depth band (m)')
        ax.set_ylim(-12.8, 4.5)
        ax.set_ylabel('Transport difference (Sv)')
        base.panel(ax, 'ab'[j], f'JAS transport difference: 2023 − {control}')
        ax.text(.98, .94, f'Total: {q.loc["all", "total_sv"]:+.2f} Sv',
                ha='right', va='top', transform=ax.transAxes, fontsize=8.5)
    hh, ll = axes[0, 0].get_legend_handles_labels()
    fig.legend(hh, ll, loc='center', bbox_to_anchor=(.50, .738), ncol=3,
               fontsize=8, columnspacing=1.6, handlelength=1.5)
    from paper_figure_blocks import folded_current_block, current_sections, current_color_scale, meridional_current_sections
    current_cmap,current_norm=current_color_scale()
    vertical = current_sections()
    gate,gate_qa=meridional_current_sections()
    ds = xr.open_dataset(DYN/'spatial_diagnostics.nc', engine='h5netcdf')
    kk = vertical['depth'] < 300
    gate_depth=gate.depth<300
    np.testing.assert_allclose(vertical['depth'][kk],gate.depth.values[gate_depth],rtol=0,atol=1e-6)
    for j, control in enumerate([1997, 2015]):
        ax = axes[1, j]
        delta = ds.u_anomaly.sel(event=2023)-ds.u_anomaly.sel(event=control)
        mesh = folded_current_block(ax, ds.lon.values, ds.lat.values, delta.values,
            vertical['depth'][kk], vertical['current_difference'][j, kk],
            gate.lat.values,gate.current_difference.sel(control=control).values[gate_depth],
            gate.layer_bottom.values[gate_depth],cmap=current_cmap,norm=current_norm,
            top_contours=ds.background_Tx.sel(event=2023).values)
        base.panel(ax, 'cd'[j], f'JAS Δu: 2023 − {control}')
    cb = fig.colorbar(mesh,cax=fig.add_axes([.36,.268,.28,.012]),orientation='horizontal',
                      extend='both',ticks=[-.5,-.25,0,.25,.5])
    cb.set_label('Zonal current difference, Δu (m/s)',fontsize=8.5,labelpad=3)
    cb.ax.tick_params(labelsize=8,pad=2)
    base.QA['M4_current_color_scale']={'limits_m_s':[-.5,.5],'normalization':'linear; unchanged',
        'palette':'current_blue_white_red','same_palette_and_norm_for_all_six_fields':True,
        'background_gradient_contours_C_per_1000km':[-1.,-.5],
        'contour_labels_per_level_per_panel':1,'depth_boundaries_m':[50,150]}
    ds.close()
    base.QA['M4_140W_section']=gate_qa
    base.QA['M4_folded_geometry']={'layout':'joined top/front/right folded diagnostic faces',
        'front':'5S-5N mean, not a boundary slice',
        'right':'140W, 9S-9N, relocated for display; not the 120W boundary',
        'all_face_values_preserved':True,'shared_native_vertical_edges':True,
        'full_170W_120W_map_and_front_preserved':True,'figure_inches':[10.4,9.4]}
    gate.close()
    direction=pd.read_csv(DIRECTIONAL/'directional_pair_seasons.csv')
    direction=direction.query('depth_m==50 and background=="mean" and season=="JAS"').set_index('control')
    labels=['Temperature structure','Anomalous current','Nonlinear interaction']
    for j,control in enumerate([1997,2015]):
        ax=axes[2,j];q=direction.loc[control];positive=np.zeros(2);negative=np.zeros(2)
        for component,color,label in zip(['temperature','velocity','nonlinear'],['#B98200','#0072B2','#77549A'],labels):
            value=np.array([q['x_'+component],q['y_'+component]])
            ax.bar([0,1],value,.42,bottom=np.where(value>=0,positive,negative),color=color,label=label)
            positive+=np.maximum(value,0);negative+=np.minimum(value,0)
        np.testing.assert_allclose(positive+negative,[q.x_total,q.y_total],rtol=0,atol=1e-12)
        ax.scatter([0,1],[q.x_total,q.y_total],color=base.BLACK,marker='D',s=22,label='Net',zorder=5)
        for x,value in enumerate([q.x_total,q.y_total]):
            ax.text(x+.25,value,f'{value:+.3f}',ha='left',va='center',fontsize=8)
        base.zero(ax);ax.set_xticks([0,1],['Zonal','Meridional']);ax.set_xlim(-.5,1.65)
        ax.set_ylim(-.285,.185);ax.set_yticks([-.2,-.1,0,.1])
        ax.set_ylabel('Advection difference\n(°C per standard month)')
        ax.text(.98,.97,f'Horizontal: {q.horizontal_total:+.3f}',transform=ax.transAxes,
                ha='right',va='top',fontsize=8.5)
        base.panel(ax,'ef'[j],f'JAS 0–50 m advection: 2023 − {control}')
    hh,ll=axes[2,0].get_legend_handles_labels()
    fig.legend(hh,ll,loc='lower center',bbox_to_anchor=(.50,.006),ncol=4,
               fontsize=8,columnspacing=1.8,handlelength=1.5)
    base.QA['directional_advection_extension']={
        'validation':json.loads((DIRECTIONAL/'validation.json').read_text()),
        'independent_validation':json.loads((DIRECTIONAL/'independent_validation.json').read_text()),
        'main_JAS_pair_values':direction.to_dict(orient='index'),
        'old_transport_and_current_fields_unchanged':True,
        'bottom_panels':'complete zonal/meridional temperature-advection anomalies, three centered components',
        'monthly_and_spatial_results_in_source_tables':True}
    for ax in axes.flat:ax._left_title.set_fontsize(9.5)
    base.save(fig, NEW[0], '夏季输送由纬向流变化主导，局地平流差异须计入经向贡献',
        'a—b：JAS 2023分别减1997和2015，对140°W暖水体积输送作逐格精确对称分解，分开流速与有效暖水层厚度，并按0—50、50—150、150m以下暖层及全层展示。'
        '输送差分别为−11.38、−8.03 Sv，其中流速项为−10.41、−6.14 Sv，最大单层流速贡献位于0—50m。'
        'c—d：JAS纬向流速差的三面折叠组合。顶面保留完整Niño3.4上层50m平均水平场，虚线为共同背景温度梯度（−1.0、−0.5°C/1000km，每级标注一次），黑实线标出140°W。正面为5°S—5°N余弦加权平均的经度—深度剖面；右侧拼入同一140°W原生输送断面的纬度—深度剖面，范围9°S—9°N，竖虚线为±5°，赤道为点线。'
        '此为三个诊断面的折叠排版，不是地理连续的海水方块：右侧为移置展示的140°W断面，并非顶面120°W东边界；正面是纬带平均，而非南边界实际切面。两个垂向面采用原生层界，显示0—300m，50/150m虚线在折线处接续。所有格点值保留，不平滑或填零。六个场共用蓝—白—红配色和±0.5m/s线性色标，蓝色为负差、红色为正差，色标尖端表示范围外值。'
        '流速差先逐月相减再作JAS等权平均，共同月背景严格抵消；300m为展示范围，a—b仍积分至瞬时σθ=26面。'
        'e—f：Niño3.4 0—50m完整纬向与经向温度平流差。每方向分为温度结构项−w̄∂T′、异常流项−w′∂T̄及非线性交互项异常[−w′∂T′]，其中w依方向为u或v，梯度取对应方向；非线性项减去自身同月平均。正负项分别堆叠，菱形为三项净和。全部逐格先乘再积分。'
        '2023相对1997/2015的纬向净差为−0.052/−0.054，经向净差为−0.145/−0.131，水平总差为−0.196/−0.185°C/标准月，主设置中经向贡献更大。全部采用1982—2024同月背景，包含目标年。'
        '三个发展年的全部月值、AMJ/JAS、南北分区、30/75m及过程去趋势见源表；经向净差在六设置中均低于两个对照，纬向净差和水平合计的符号依设置变化。该结果不能将局地温度平流等同于140°W体积输送或经向动量归因。',
        'JAS contrasts (2023 minus each control) separate velocity and active-thickness contributions to 140°W warm-water transport exactly before integration. '
        'Folded three-face composites (c,d) join the full Nino3.4 0-50 m map (top), the 5S-5N cosine-weighted longitude-depth mean (front), and the actual native 140W latitude-depth section spanning 9S-9N (right). '
        'These are folded diagnostic faces, not a geographically continuous cuboid: the right face relocates 140W and does not represent the eastern 120W boundary, while the front is a latitude mean. A solid line locates 140W on the top map; dashed contours show background temperature gradients (-1.0, -0.5 C per 1000 km). '
        'Both vertical faces use native layer boundaries and connected 50/150 m depth lines. On the right face, vertical dashed lines delimit 5S-5N and the equator is dotted. All six fields retain native values and share a linear +/-0.5 m/s blue-white-red scale with extended ends. '
        'Differences are formed for matched months before equal JAS averaging. The 300-m limit is only for display; transport in (a,b) retains the instantaneous sigma_theta=26 boundary. '
        'Panels (e,f) decompose full zonal and meridional temperature-advection contrasts into background flow acting on anomalous temperature gradients, anomalous flow acting on background gradients, and the monthly-centered nonlinear interaction. Positive and negative components are stacked separately; diamonds mark their signed sum. Products are formed before spatial integration. '
        'Zonal net contrasts are -0.052/-0.054 and meridional net contrasts -0.145/-0.131 C per standard month, yielding horizontal totals -0.196/-0.185 for the two controls. Meridional differences dominate the main 50-m setting. '
        'Monthly, AMJ/JAS, regional and six-setting sensitivity data are retained. Meridional net contrasts remain negative in every setting, whereas zonal and total signs can vary. The section transport and local temperature-advection budgets have different domains and meanings. '
        'All 1982-2024 years define the monthly background; these are kinematic decompositions, not causal fractions.',
        [DYN/x for x in DATA[:5]]+[DYN/'spatial_diagnostics.nc',base.OUT/'source_data/JAS_current_vertical_sections.npz',
            base.OUT/'source_data/JAS_140W_meridional_current_sections.nc',
            base.OUT/'source_data/JAS_140W_meridional_current_sections_QA.json',
            DIRECTIONAL/'directional_pair_seasons.csv',DIRECTIONAL/'directional_case_monthly.csv',
            DIRECTIONAL/'regional_pair_seasons.csv',DIRECTIONAL/'directional_spatial.nc',
            DIRECTIONAL/'independent_validation.json',DIRECTIONAL/'结果与解释.txt'], 'main', pdf)
    for name in ['directional_case_monthly.csv','directional_case_seasons.csv','directional_pair_seasons.csv','directional_spatial.nc']:
        shutil.copy2(DIRECTIONAL/name,base.OUT/'source_data'/name)
    for name in ['regional_pair_seasons.csv','region_volume_fractions.csv','validation.json','independent_validation.json',
                 'input_manifest.json','source_and_runtime_manifest.json','reproduce.txt',
                 'protocol_before_run.txt','结果与解释.txt','正文建议段落.txt']:
        shutil.copy2(DIRECTIONAL/name,base.OUT/'source_data'/('directional_'+name))

    if m4_only:return
    base.style()

    fig = base.figbase(7.6, 'Weaker eastward wind input accompanies weaker upper-ocean currents',
        'SODA3.15.2 / ERA5; Niño3.4, 0-50 m; 1982-2024 monthly anomalies.\n'
        'Positive stress anomaly = eastward momentum input anomaly. SSH includes atmospheric loading.\n'
        'Cumulative terms are diagnostic integrals; initial contrast and integration error are separate.')
    gs = fig.add_gridspec(3, 2, left=.10, right=.95, bottom=.16, top=.95,
                         height_ratios=[.95, 1.04, 1.1], hspace=.55, wspace=.40)
    axes = np.array([[fig.add_subplot(gs[i, j]) for j in range(2)] for i in range(3)])
    for e in base.EVENTS:
        q = case(local, e)
        base.eventline(axes[0, 0], q.time.dt.month, q.u_m_s, e)
        w = wind[wind.time.dt.year == e]
        base.eventline(axes[0, 1], w.time.dt.month, w.soda_nino34_taux_anomaly*100, e)
        axes[0, 1].plot(w.time.dt.month, w.era5_nino34_taux_anomaly*100,
                        c=base.COLORS[e], ls='--', lw=.8)
    for ax in axes[0]: months(ax, base)
    axes[0, 0].set_ylabel('Current anomaly (m/s)')
    axes[0, 1].set_ylabel(r'Stress anomaly ($10^{-2}$ N m$^{-2}$)')
    base.panel(axes[0, 0], 'a', '0–50 m zonal current anomaly')
    base.panel(axes[0, 1], 'b', 'Niño3.4 zonal wind-stress anomaly')
    event_handles, event_labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(event_handles, event_labels, loc='center', bbox_to_anchor=(.52, .715),
               fontsize=7, ncol=3, handlelength=1.6, columnspacing=2.)
    axes[0, 1].plot([], [], color='#333', label='SODA')
    axes[0, 1].plot([], [], color='#333', ls='--', label='ERA5')
    axes[0, 1].legend(handles=axes[0, 1].get_lines()[-2:], fontsize=6.5,
                      ncol=2, handlelength=1.4)
    for j, control in enumerate([1997, 2015]):
        ax = axes[1, j]
        vals = [(force_values(seas.loc[2023], k)-force_values(seas.loc[control], k))*1e7
                for k in FORCE]
        ax.bar(np.arange(6), vals, color=FC, width=.7)
        tendency = (seas.loc[2023, 'tendency_m_s2']-seas.loc[control, 'tendency_m_s2'])*1e7
        ax.axhline(tendency, color='#222', lw=.9, ls='--', label='Actual tendency difference')
        base.zero(ax); ax.set_ylim(-4.4, 2.6)
        ax.set_xticks(np.arange(6), ['Wind', 'SSH', 'Density', 'Coriolis', 'H. adv.\n+ metric', 'Unres.'])
        ax.tick_params(axis='x', labelsize=6)
        ax.set_ylabel(r'Acceleration difference ($10^{-7}$ m s$^{-2}$)')
        base.panel(ax, 'cd'[j], f'JAS zonal acceleration difference\n2023 − {control}')
        ax.legend(loc='lower left', fontsize=6.2)
        ax = axes[2, j]
        a, b = case(local, 2023), case(local, control)
        seconds = (a.time-a.time.iloc[0]).dt.total_seconds().to_numpy()
        month = a.time.dt.month
        for key, color, label in zip(FORCE, FC, FL):
            integ = cumulative_trapezoid(force_values(a, key)-force_values(b, key), seconds, initial=0)
            ax.plot(month, integ, c=color, lw=1.1,
                     ls='--' if key == 'unresolved' else '-', label=label)
        delta = (a.u_m_s-b.u_m_s).to_numpy()
        actual = delta-delta[0]
        integ_tendency = cumulative_trapezoid(a.tendency_m_s2-b.tendency_m_s2, seconds, initial=0)
        mismatch = actual-integ_tendency
        ax.plot(month, actual, color='#111', lw=1.7, label='Actual change in current contrast')
        ax.plot(month, mismatch, color='#888', lw=.9, ls=':', label='Integration error')
        ax.text(.02, .04, f'Jan 15 contrast: {delta[0]:+.3f} m/s', transform=ax.transAxes,
                fontsize=7.0, color='black', bbox={'facecolor':'white', 'alpha':.8, 'edgecolor':'none', 'pad':1.5})
        months(ax, base); ax.set_ylim(-10.7, 5.1)
        ax.set_ylabel('Cumulative contribution (m/s)')
        base.panel(ax, 'ef'[j], f'Cumulative zonal acceleration difference\n2023 − {control}')
    hh, ll = axes[2, 0].get_legend_handles_labels()
    fig.legend(hh, ll, loc='center', bbox_to_anchor=(.53, .055), ncol=3,
               fontsize=6.2, handlelength=1.6, columnspacing=1.3, labelspacing=.45)
    base.save(fig, NEW[1], '2023向东风动量输入较弱，与上层流速差异相对应',
        'a—b：Niño3.4上层50m异常纬向流及同名区域风应力的全年演变，颜色/点形固定区分1997、2015、2023；实线为SODA模式应力，虚线为ERA5核对。'
        'JAS应力异常分别为+0.01950、+0.01429、+0.00077 N/m²，平均异常流为+0.1387、+0.0951、+0.0079 m/s。'
        'c—d：2023分别减两个对照的夏季动量项，虚线为实际倾向差；风应力通过τx′/(ρ0H)给出表面动量输入，压力由有效SSH与原位密度重建。'
        '相对1997，海面压力项补偿部分风输入不足；相对2015，海面压力项接近。e—f：自1月15日起的累计受力贡献、实际流速差变化及单列积分误差，期初流速差写在图内。'
        '较弱的风输入提供动力解释线索；各项存在大幅抵消，未解析项包含层底应力、垂向输送、高频协方差、同化及重网格误差，不指定单一机制或给出风致因果百分比。'
        '正应力距平不等于绝对西风。SODA使用ERA5强迫，二者为资料一致性核对；全43年背景与旧图口径分别标示。',
        'Monthly 0-50 m current anomalies and same-region wind-stress anomalies show weaker eastward momentum input in 2023. '
        'JAS force contrasts include surface stress, effective sea-level and in-situ density pressure gradients, Coriolis, horizontal advection plus metric terms, and an unresolved term. '
        'Cumulative diagnostics separate the initial current contrast, subsequent actual change and numerical integration error. '
        'Large compensating terms preclude causal percentages; ERA5 is the atmospheric forcing of SODA and is not an independent validation product.',
        [DYN/x for x in ['case_monthly.csv', 'case_seasons.csv', 'momentum_pair_intervals.csv',
                        'wind_product_comparison.csv', 'protocol_before_run.txt']], 'main', pdf)
    copy_sources(base)


def copy_sources(base):
    target = base.OUT/'source_data'
    target.mkdir(exist_ok=True)
    for name in DATA:
        shutil.copy2(DYN/name, target/('summer_'+name))


def update_m4_only():
    """Refresh M4 and its 140W section without regenerating any other figure."""
    import build_three_event_scientific_figures as base
    out=base.OUT
    meta=json.loads((out/'figure_manifest.json').read_text())
    base.META=[]
    base.QA=json.loads((out/'validation.json').read_text())
    preserved={str(p.relative_to(out)):base.sha(p)
        for m in meta if m['stem']!=NEW[0]
        for p in [*(out/f"{m['stem']}.{ext}" for ext in ['png','pdf','svg']),
                  out/'presentation'/f"{m['stem']}.png"]}
    paths=[DYN/n for n in ['case_monthly.csv','case_seasons.csv','section_pair_seasons.csv',
                          'wind_product_comparison.csv','spatial_diagnostics.nc']]
    paths.append(out/'source_data/JAS_current_vertical_sections.npz')
    paths.append(out/'source_data/JAS_140W_meridional_current_sections.nc')
    paths.extend(DYN/f'inputs/ocean_{e}.npz' for e in base.EVENTS)
    paths.extend(DIRECTIONAL/n for n in ['directional_pair_seasons.csv','directional_case_monthly.csv',
        'regional_pair_seasons.csv','directional_spatial.nc','validation.json','independent_validation.json','结果与解释.txt'])
    sources={str(p.relative_to(ROOT)):base.sha(p) for p in paths}
    review=ROOT/'tmp/pdfs/directional_advection_review';review.mkdir(parents=True,exist_ok=True)
    with PdfPages(review/'rebuilt_M4.pdf') as pdf:
        render_figures(base,pdf,m4_only=True)
    assert all(base.sha(out/p)==h for p,h in preserved.items())
    assert all(base.sha(ROOT/p)==h for p,h in sources.items())
    updated=base.META[0]
    base.META=[updated if m['stem']==NEW[0] else m for m in meta]
    base.QA['M4_color_revision']={'only_updated_figure':NEW[0],
        'source_fields_and_diagnostics_unchanged':True,'source_sha256':sources,
        'other_figure_files_unchanged':len(preserved),'other_figure_sha256':preserved}
    base.QA['M4_section_revision']={'only_updated_figure':NEW[0],
        'source_fields_and_diagnostics_unchanged':True,
        'other_figure_files_unchanged':len(preserved),'other_figure_sha256':preserved,
        'panel_count':6,'integrated_section_faces':['c','d'],'actual_section_longitude_degrees_east':220}
    base.QA['M4_folded_revision']={'only_updated_figure':NEW[0],
        'source_fields_and_diagnostics_unchanged':True,'source_sha256':sources,
        'other_figure_files_unchanged':len(preserved),'other_figure_sha256':preserved,
        'panel_count':6,'figure_inches':[10.4,9.4]}
    base.QA['M4_directional_revision']={'only_updated_figure':NEW[0],
        'original_inputs_unchanged':True,'other_figure_files_unchanged':len(preserved),
        'other_figure_sha256':preserved,'updated_panels':['e','f'],'panel_count':6}
    base.QA['visual_pdf_review']={'status':'Pending review of revised page 6; other six figures unchanged',
                                'page_numbers':[6]}
    (out/'figure_manifest.json').write_text(json.dumps(base.META,ensure_ascii=False,indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(base.QA,ensure_ascii=False,indent=2)+'\n')
    inputs=json.loads((out/'input_manifest.json').read_text())
    inputs.update(sources);inputs.update(base.QA['M4_140W_section']['source_sha256'])
    inputs.update(json.loads((DIRECTIONAL/'input_manifest.json').read_text()))
    (out/'input_manifest.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2)+'\n')
    base.gallery()
    print('PASS: 140W transport reproduced; M4 source fields and other 24 figure files unchanged.',flush=True)


def main():
    import build_three_event_scientific_figures as base
    out = base.OUT
    archive = out/'archive/before_summer_mechanisms_20261015'
    archive.mkdir(parents=True, exist_ok=True)
    names = ['index.html', 'figure_manifest.json', 'input_manifest.json', 'validation.json',
             'three_event_figure_book.pdf', 'figure_data.zip']
    names += [f'S3_attribution_limits.{ext}' for ext in ['png', 'pdf', 'svg']]
    for name in names:
        if not (archive/name).exists(): shutil.copy2(out/name, archive/name)
    preserved = {str(p.relative_to(out)):base.sha(p) for stem in KEEP
                 for p in [out/f'{stem}.{e}' for e in ['png', 'pdf', 'svg']]+[out/'presentation'/f'{stem}.png']}
    old_meta = json.loads((out/'figure_manifest.json').read_text())
    base.META[:] = [m for m in old_meta if m['stem'] in KEEP]
    base.QA.clear(); base.QA.update(json.loads((out/'validation.json').read_text()))
    base.QA['scope'] = '5 main + 2 supporting figures; former final S3 group replaced by M4/M5'
    base.QA['text_outside_page'].pop('S3_attribution_limits', None)
    with PdfPages('/private/tmp/three_event_new_mechanisms.pdf') as pdf:
        render_figures(base, pdf)
    assert not any(base.QA['text_outside_page'][s] for s in NEW), base.QA['text_outside_page']
    assert all(base.sha(out/p) == h for p, h in preserved.items())
    base.QA['figures'] = len(base.META)
    base.QA['summer_update'] = {'preserved_figure_hashes':preserved,
        'preserved_first_five_figures':True, 'replacement_stems':NEW,
        'diagnostic_validation':json.loads((DYN/'validation.json').read_text())['status'],
        'no_model_or_statistics_recomputed':True}
    (out/'figure_manifest.json').write_text(json.dumps(base.META, ensure_ascii=False, indent=2)+'\n')
    (out/'validation.json').write_text(json.dumps(base.QA, ensure_ascii=False, indent=2)+'\n')
    inputs = json.loads((out/'input_manifest.json').read_text())
    inputs.update({str((DYN/n).relative_to(ROOT)):base.sha(DYN/n) for n in DATA})
    (out/'input_manifest.json').write_text(json.dumps(inputs, indent=2)+'\n')
    base.gallery()
    bundled = '/Users/daiyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
    subprocess.run([bundled, str(ROOT/'scripts/package_three_event_figure_gallery.py')], check=True)
    print('Updated final figure group: M4 + M5; first five figures unchanged.', flush=True)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m4-only',action='store_true')
    args=parser.parse_args()
    update_m4_only() if args.m4_only else main()
