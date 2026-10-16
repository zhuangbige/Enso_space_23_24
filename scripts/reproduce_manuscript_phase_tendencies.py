#!/usr/bin/env python3
"""Reconstruct manuscript Fig. 3a: observed paths and local RO tendencies.

The linear arrows are evaluated AT observed states, not on freely integrated
forecasts. All groups share one normalization, one RO and one arrow scale.
"""
from pathlib import Path
import os
import json
import hashlib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/ro_pmm_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
import paper_ro_slim as slim

SOURCE = ROOT / 'outputs/research_2026/manuscript_RO_exact_period_20261014'
OUT = ROOT / 'outputs/research_2026/manuscript_phase_tendencies_20261014'
GROUPS = {
    'EN': [2002, 2004, 2006, 2009, 2014, 2015, 2018, 2023],
    'FY_LN': [2005, 2007, 2010, 2016, 2020, 2024],
    'MY_LN': [2008, 2011, 2017, 2021, 2022],
}
LABELS = {'EN': 'El Niño', 'FY_LN': 'First-year La Niña', 'MY_LN': 'Consecutive La Niña'}
COLORS = {'EN': '#CA6653', 'FY_LN': '#257CB0', 'MY_LN': '#20865C'}
EPISODES = [[2008], [2011], [2017], [2021, 2022]]
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
ARROW_MONTHS = 0.8
COMPONENTS = ['obs_T', 'obs_H', 'ro_T', 'ro_H']


def jsonable(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    raise TypeError(type(x))


def rms_vector(x):
    return float(np.sqrt(np.mean(np.sum(np.asarray(x) ** 2, axis=-1))))


def diagnostics(a, model):
    scale = np.asarray(model['scale'])
    z = a.to_numpy() / scale
    # Differentiate continuous observations before event compositing. January
    # and December are NOT connected into an artificial periodic 12-month loop.
    obs = np.gradient(z, axis=0, edge_order=2)
    lt = np.einsum('nk,kij->nij', slim.basis(slim.decimal_time(a.index), model['order']), model['coef'])
    ro = np.einsum('nij,nj->ni', lt, z) / 12.0
    physical_l = lt * scale[None, :, None] / scale[None, None, :]
    physical_ro = np.einsum('nij,nj->ni', physical_l, a.to_numpy()) / 12
    np.testing.assert_allclose(ro, physical_ro / scale, rtol=1e-12, atol=1e-12)
    # Same calculation in dimensionful space verifies the derivative units.
    np.testing.assert_allclose(obs, np.gradient(a.to_numpy(), axis=0, edge_order=2) / scale, atol=1e-12)
    frame = pd.DataFrame(np.c_[z, obs, ro], index=a.index,
                         columns=['T', 'H'] + COMPONENTS)
    events = []
    for group, years in GROUPS.items():
        for year in years:
            event = frame.loc[str(year)].copy()
            assert len(event) == 12 and np.isfinite(event.to_numpy()).all()
            event['year'] = year
            event['month'] = event.index.month
            event['group'] = group
            events.append(event)
    events = pd.concat(events).rename_axis('time').reset_index()
    composites = events.groupby(['group', 'month'], sort=False)[['T', 'H'] + COMPONENTS].mean().reset_index()
    composites['res_T'] = composites.obs_T - composites.ro_T
    composites['res_H'] = composites.obs_H - composites.ro_H
    composites['residual_norm'] = np.hypot(composites.res_T, composites.res_H)
    composites['obs_speed'] = np.hypot(composites.obs_T, composites.obs_H)
    composites['ro_speed'] = np.hypot(composites.ro_T, composites.ro_H)
    dot = composites.obs_T * composites.ro_T + composites.obs_H * composites.ro_H
    denom = composites.obs_speed * composites.ro_speed
    composites['angle_deg'] = np.degrees(np.arccos(np.clip(dot / denom, -1, 1)))
    composite_error = 0.0
    for group in GROUPS:
        q = composites[composites.group.eq(group)]
        calendar_l = np.einsum('nk,kij->nij', slim.basis((q.month.to_numpy() - .5) / 12, model['order']), model['coef'])
        check = np.einsum('nij,nj->ni', calendar_l, q[['T', 'H']].to_numpy()) / 12
        # Linear evaluation and equal-weight averaging must commute.
        composite_error = max(composite_error, float(abs(check - q[['ro_T', 'ro_H']].to_numpy()).max()))
    assert composite_error < 1e-10
    return events, composites, dict(physical_normalized_tendency_consistency=True,
                                    local_RO_composite_commutation_max_error=composite_error,
                                    n_event_months=len(events))


def summarize(composites):
    rows = []
    for group in GROUPS:
        q = composites[composites.group.eq(group)]
        for period, select in [('Jan-Jun', q.month.le(6)), ('Jul-Dec', q.month.ge(7))]:
            v = q[select]
            obs = v[['obs_T', 'obs_H']].to_numpy()
            ro = v[['ro_T', 'ro_H']].to_numpy()
            rows.append(dict(group=group, period=period, residual_RMS=rms_vector(obs-ro),
                             observed_speed_RMS=rms_vector(obs), RO_speed_RMS=rms_vector(ro),
                             relative_residual=rms_vector(obs-ro)/rms_vector(obs)))
    return pd.DataFrame(rows)


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 12, 'axes.labelsize': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#66717D', 'axes.labelcolor': '#24313E',
                         'xtick.color': '#384554', 'ytick.color': '#384554',
                         'savefig.facecolor': 'white', 'svg.fonttype': 'none'})


def save(fig, stem):
    for suffix in ['png', 'svg']:
        fig.savefig(OUT / f'{stem}.{suffix}', dpi=230, bbox_inches='tight')
    plt.close(fig)


def phase_axes(ax):
    ax.axhline(0, color='#89939E', lw=.85)
    ax.axvline(0, color='#89939E', lw=.85)
    ax.grid(alpha=.15, lw=.7)
    ax.set(xlim=(-1.75, 2.0), ylim=(-1.9, 1.7), xlabel='Niño3.4 anomaly (SD)', ylabel='WWV / mean D20 anomaly (SD)')
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks(np.arange(-1.5, 2.1, .5))
    ax.set_yticks(np.arange(-1.5, 1.6, .5))


def phase(ax, q, group, labels=False, arrows=True):
    color = COLORS[group]
    ax.plot(q['T'], q['H'], color=color, lw=2.4, alpha=.9, zorder=2)
    ax.scatter(q['T'], q['H'], s=24, color=color, edgecolors='white', linewidth=.45, zorder=3)
    if arrows:
        # Identical origin, units, scale and aspect for both vector sets.
        gray = ax.quiver(q['T'], q['H'], q.ro_T, q.ro_H, color='#969B9F',
                         angles='xy', scale_units='xy', scale=1 / ARROW_MONTHS,
                         width=.008, headwidth=3.7, headlength=4.5, zorder=4)
        ax.quiver(q['T'], q['H'], q.obs_T, q.obs_H, color='#202932',
                  angles='xy', scale_units='xy', scale=1 / ARROW_MONTHS,
                  width=.0045, headwidth=4.2, headlength=5.0, zorder=5)
    ax.scatter(q['T'].iloc[0], q['H'].iloc[0], marker='*', s=120, color=color,
               edgecolors='white', linewidth=.7, zorder=6)
    if labels:
        offsets = {
            'EN': {1: (-34, -17), 4: (-30, 13), 7: (-12, -25), 10: (8, 12), 12: (8, -10)},
            'FY_LN': {1: (5, 10), 4: (2, -22), 7: (-25, 15), 10: (0, -23), 12: (-33, 7)},
            'MY_LN': {1: (-33, 1), 4: (-31, 12), 7: (6, 10), 10: (5, -20), 12: (-34, -5)},
        }
        for mo, offset in offsets[group].items():
            row = q[q.month.eq(mo)].iloc[0]
            ax.annotate(MONTHS[mo-1], (row['T'], row['H']), xytext=offset,
                        textcoords='offset points', fontsize=9, color=color, zorder=8,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.85, pad=.7))
    return gray if arrows else None


def phase_figure(composites, stats):
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.2))
    fig.subplots_adjust(top=.80, bottom=.20, wspace=.26, left=.065, right=.985)
    for ax, group in zip(axes, GROUPS):
        phase_axes(ax)
        q = composites[composites.group.eq(group)]
        gray = phase(ax, q, group, labels=True)
        ax.set_title(f'{LABELS[group]}  |  n = {len(GROUPS[group])}', color=COLORS[group], loc='left', pad=12)
        s = stats[stats.group.eq(group)].set_index('period')
        early, late = s.loc['Jan-Jun', 'residual_RMS'], s.loc['Jul-Dec', 'residual_RMS']
        metric_y = .85 if group == 'FY_LN' else .025
        ax.text(.02, metric_y, f'Tendency mismatch: {early:.3f} → {late:.3f}\nJan–Jun → Jul–Dec  (SD/month)',
                transform=ax.transAxes, fontsize=9, color='#4C5662',
                bbox=dict(facecolor='white', edgecolor='none', alpha=.95, pad=2))
    fig.suptitle('Observed ENSO paths and local linear RO tendencies', fontsize=19, y=.985)
    fig.text(.5, .918, 'January–December composites  •  Same observed state for both arrows  •  One scale for every panel', ha='center', fontsize=11)
    legend = [Line2D([0], [0], color='#202932', lw=2, label='Black arrows: observed time derivative'),
              Line2D([0], [0], color='#969B9F', lw=3, label='Gray arrows: linear RO at the observed state'),
              Line2D([0], [0], marker='*', color='white', markerfacecolor='#4C5662', markersize=11, label='January')]
    fig.legend(handles=legend, ncol=3, loc='upper center', bbox_to_anchor=(.5, .883), frameon=False, fontsize=10)
    axes[2].quiverkey(gray, .66, -.28, .4, '0.4 SD/month', labelpos='E', coordinates='axes', fontproperties={'size': 9})
    fig.text(.065, .045, 'ERSSTv5 + GODAS  |  Climatology: 1991–2020  |  Detrend: Jan 2002–Apr 2025  |  RO fit / SD: 2002–2024\n'
             'WWV uses area-mean 20°C isotherm depth; all vectors are in SD/month (display length = 0.8 month × tendency).\n'
             'Same-sample mechanism diagnostic. The arrows are local rates; the colored lines are observations.', fontsize=9, color='#55616D', linespacing=1.5)
    save(fig, 'figure3a_phase_tendencies')


def tendency_figure(composites, stats):
    fig, axes = plt.subplots(3, 3, figsize=(13.5, 9.0), sharex=True, sharey='row')
    fig.subplots_adjust(top=.82, bottom=.14, left=.075, right=.98, hspace=.17, wspace=.19)
    for col, group in enumerate(GROUPS):
        q = composites[composites.group.eq(group)]
        for row, component in enumerate(['T', 'H']):
            ax = axes[row, col]
            ax.plot(q.month, q[f'obs_{component}'], '-o', color='#202932', lw=1.8, ms=4, label='Observed')
            ax.plot(q.month, q[f'ro_{component}'], '--s', color='#969B9F', lw=2, ms=3.5, label='Linear RO')
            ax.axhline(0, color='#85909B', lw=.65)
        ax = axes[2, col]
        ax.plot(q.month, q.residual_norm, '-o', color=COLORS[group], lw=2.3, ms=4)
        s = stats[stats.group.eq(group)].set_index('period')
        for x, p in [(np.array([1, 6]), 'Jan-Jun'), (np.array([7, 12]), 'Jul-Dec')]:
            ax.plot(x, [s.loc[p, 'residual_RMS']]*2, color=COLORS[group], ls=':', lw=1.5)
        axes[0, col].set_title(LABELS[group], loc='left', color=COLORS[group], pad=13)
        ax.set_xlabel('Calendar month')
        for ax in axes[:, col]:
            ax.axvspan(6.5, 12.5, color='#E8D8AF', alpha=.28, zorder=0)
            ax.set_xlim(.7, 12.3)
            ax.set_xticks([1, 3, 5, 7, 9, 11], ['Jan', 'Mar', 'May', 'Jul', 'Sep', 'Nov'])
            ax.grid(alpha=.13)
    axes[0, 0].set_ylabel('d(Niño3.4) / dt\n(SD/month)')
    axes[1, 0].set_ylabel('d(WWV) / dt\n(SD/month)')
    axes[2, 0].set_ylabel('|Observed − RO|\n(SD/month)')
    axes[0, 0].set_ylim(-.53, .53)
    axes[1, 0].set_ylim(-.56, .56)
    axes[2, 0].set_ylim(0, .46)
    fig.suptitle('Where does the linear RO miss the observed evolution?', fontsize=19, y=.982)
    fig.text(.5, .93, 'The consecutive La Niña mismatch grows in July–December; both Niño3.4 and WWV contribute.', ha='center', fontsize=11)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, frameon=False, loc='upper center', bbox_to_anchor=(.5, .91))
    fig.text(.075, .043, 'Shading: July–December. Dotted segments: half-year RMS vector mismatch. Rates are derivatives of the monthly composites.\n'
             'Continuous monthly derivatives are calculated before compositing; no artificial December-to-January closure is imposed.\n'
             'A residual can include omitted forcing, noise and coefficient error; it does not by itself identify nonlinear dynamics.', fontsize=9, color='#55616D', linespacing=1.5)
    save(fig, 'monthly_tendency_comparison')


def original_comparison(composites, mean_preserved):
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.4), gridspec_kw={'width_ratios': [1.16, 1, 1]})
    fig.subplots_adjust(top=.82, bottom=.27, left=.02, right=.985, wspace=.24)
    im = np.asarray(Image.open(ROOT / 'tmp/pdfs/manuscript_audit_20261014/original_fig3_Image67.jpg'))
    axes[0].imshow(im[:480, :552])
    axes[0].axis('off')
    axes[0].set_title('Supplied manuscript: Figure 3a', fontsize=13, pad=13)
    for ax, data, title in [(axes[1], composites, 'Reconstruction: mean removed'),
                            (axes[2], mean_preserved, 'Sensitivity: mean retained')]:
        phase_axes(ax)
        for group in GROUPS:
            phase(ax, data[data.group.eq(group)], group)
        ax.set_title(title, fontsize=12, pad=14)
    fig.suptitle('Figure 3a: original and transparent reconstructions', fontsize=20, y=.978)
    fig.text(.5, .908, 'The loop and weakening RO tendency are recovered; point-by-point agreement is incomplete.', ha='center', fontsize=12)
    fig.text(.05, .048, 'Right: remove the fitted slope but retain the 1991–2020-referenced anomaly mean, then refit the same RO.\n'
             'This shifts WWV by +0.238 SD and Niño3.4 by −0.016 SD; these are data-derived offsets, not corrections fitted to the image.\n'
             'The manuscript does not specify the detrending intercept or normalization details. Neither convention is asserted to be the author’s.\n'
             'Source panel: supplied manuscript.pdf, p. 11. Reconstruction uses the 19 event years shown in its Figure 4.', fontsize=10, color='#55616D', linespacing=1.5)
    save(fig, 'figure3a_original_vs_reconstruction')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    a = pd.read_csv(SOURCE / 'observations_detrended_2002Jan_2025Apr.csv', index_col=0, parse_dates=True)
    metadata = json.loads((SOURCE / 'models_exact_period.json').read_text())
    assert list(a.columns) == ['Nino34', 'WWV']
    assert a.index.equals(pd.date_range('2002-01-01', '2025-04-01', freq='MS'))
    intercept = np.asarray(metadata['preprocessing']['beta'])[0]
    all_stats, all_events, all_composites, models, qa = [], [], [], {}, {}
    for variant, x in [('mean_removed', a), ('mean_retained', a + intercept)]:
        model = slim.fit(x.loc['2002':'2024'])
        if variant == 'mean_removed':
            prior = metadata['models']['monthly_states']['model']
            np.testing.assert_allclose(model['coef'], prior['coef'], rtol=1e-11, atol=1e-11)
        events, composites, checks = diagnostics(x, model)
        stats = summarize(composites)
        for obj in [events, composites, stats]:
            obj['variant'] = variant
        all_events.append(events); all_composites.append(composites); all_stats.append(stats)
        models[variant] = model; qa[variant] = checks
    events = pd.concat(all_events, ignore_index=True)
    composites = pd.concat(all_composites, ignore_index=True)
    stats = pd.concat(all_stats, ignore_index=True)
    events.to_csv(OUT / 'event_monthly_states_and_tendencies.csv', index=False)
    composites.to_csv(OUT / 'composite_monthly_states_and_tendencies.csv', index=False)
    stats.to_csv(OUT / 'halfyear_tendency_metrics.csv', index=False)
    # Leave one full La Niña episode out of the composite. Keep the fitted
    # operator fixed: this probes composite dependence, NOT validation skill.
    sensitivity = []
    for variant in models:
        for omitted in EPISODES:
            keep = events[events.variant.eq(variant) & events.group.eq('MY_LN') & ~events.year.isin(omitted)]
            q = keep.groupby('month')[COMPONENTS].mean()
            error = q[['obs_T', 'obs_H']].to_numpy() - q[['ro_T', 'ro_H']].to_numpy()
            early, late = rms_vector(error[:6]), rms_vector(error[6:])
            sensitivity.append(dict(variant=variant, omitted_event_years=','.join(map(str, omitted)),
                                    remaining_n_events=keep.year.nunique(), early_RMS=early,
                                    late_RMS=late, late_over_early=late/early))
    sens = pd.DataFrame(sensitivity)
    sens.to_csv(OUT / 'leave_one_LaNina_episode_out.csv', index=False)
    primary = composites[composites.variant.eq('mean_removed')]
    primary_stats = stats[stats.variant.eq('mean_removed')]
    phase_figure(primary, primary_stats)
    tendency_figure(primary, primary_stats)
    original_comparison(primary, composites[composites.variant.eq('mean_retained')])
    provenance = dict(
        source_pdf='/Users/daiyue/Library/Containers/com.tencent.qq/Data/Downloads/manuscript.pdf',
        source_pages=[4, 5, 6, 10, 11, 12], target='Figure 3a and section 3.3',
        observations='ERSSTv5 Niño3.4; GODAS area-mean D20 as WWV proxy',
        observation_period=['2002-01', '2025-04'], fit_period=['2002-01', '2024-12'],
        climatology='1991–2020 monthly climatology', event_groups=GROUPS,
        event_group_note='Years taken from manuscript Figure 4; Fig.3-specific inclusion is not supplied.',
        detrending='OLS slope and intercept removed over 2002-01 to 2025-04; retaining intercept is a separate sensitivity.',
        standardization='Each variable divided by its own 2002–2024 population SD; shared by all groups.',
        derivative='Centered two-month-span finite difference, one-month step; initial Jan 2002 second-order forward difference.',
        tendency='L(calendar month) @ observed normalized state / 12; L is in year^-1.',
        early_late_definition='Jan–Jun versus Jul–Dec, an explicit diagnostic choice; manuscript does not define early/late months.',
        residual_metric='sqrt(mean_month(||mean_event(observed tendency) − mean_event(RO tendency)||²))',
        sensitivity='Mean-retaining detrend + complete model refit; omit one complete La Niña episode from composite with model fixed.',
        normalization_scale= models['mean_removed']['scale'], mean_retained_offset_SD=intercept/models['mean_removed']['scale'],
        observed_states_sha256=hashlib.sha256((SOURCE / 'observations_detrended_2002Jan_2025Apr.csv').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        primary_matches_previously_audited_coefficients=True, QA=qa, models=models)
    (OUT / 'methods_models_and_QA.json').write_text(json.dumps(provenance, default=jsonable, indent=2))
    cn = [
        '原稿图3a：相空间与观测/线性RO趋势复现', '',
        '结论：定性复现了连续拉尼娜后期的偏离与线性RO趋势减弱，但不是逐点、逐箭头的严格复现。',
        '本图是观测状态上的动力诊断，不是预报轨迹，也不能据此计算PMM的预报增益。', '',
        '1. 图和方法',
        'figure3a_phase_tendencies.png：三类事件分别显示，横轴Niño3.4，纵轴WWV（面积平均D20代理），单位均为标准差。',
        'monthly_tendency_comparison.png：逐月Niño3.4趋势、WWV趋势和二维趋势残差；浅色标出7—12月。',
        'figure3a_original_vs_reconstruction.png：原稿图3a、主复现、保留异常均值的敏感性对照。',
        '数据时段2002年1月—2025年4月；RO拟合和标准差2002—2024年；异常参考1991—2020月气候态。',
        '标准差：Niño3.4 = %.8f °C，WWV代理 = %.8f m。所有事件共用，未逐事件或逐类重新归一化。' % tuple(models['mean_removed']['scale']),
        '彩色线是各类事件1—12月的观测合成；黑箭头是观测导数，灰箭头是同一观测状态下L(t)X。',
        '观测导数先在连续序列上作中心差分，再进行合成；不将12月和1月强行首尾相连。仅2002年1月使用二阶单边差分。',
        '线性RO采用前轮已核查的季节sLIM（年周期+半年周期，二阶扰动法），系数由年^-1换成月^-1。',
        '事件年份取原稿图4所列：EN '+str(GROUPS['EN'])+'；首年LN '+str(GROUPS['FY_LN'])+'；连续LN '+str(GROUPS['MY_LN'])+'。',
        '原稿未提供图3独立事件清单，按图4同一清单重建，是本次明确的实现假设。', '',
        '2. 定量结果',
        '以下是合成趋势的二维RMS残差，单位SD/月；不是逐事件残差RMS的平均。',
        '“早期/后期”操作定义为1—6月/7—12月；原稿没有给出明确分界月。',
        primary_stats.to_string(index=False), '',
    ]
    for variant in models:
        s = stats[stats.variant.eq(variant) & stats.group.eq('MY_LN')].set_index('period')
        ratio = s.loc['Jul-Dec', 'residual_RMS'] / s.loc['Jan-Jun', 'residual_RMS']
        speed = s.loc['Jul-Dec', 'RO_speed_RMS'] / s.loc['Jan-Jun', 'RO_speed_RMS']
        ss = sens[sens.variant.eq(variant)]
        cn.append(f'{variant}：连续LN后期/早期残差比={ratio:.3f}；RO趋势速度比={speed:.3f}；依次剔除整次事件后的残差比范围={ss.late_over_early.min():.3f}—{ss.late_over_early.max():.3f}。')
    cn += ['', '3. 可以解释到什么程度',
           '连续LN合成在年初冷状态下补充海洋热量，春末转入WWV下降，夏后Niño3.4重新变冷，形成局部回环。',
           '后半年观测仍在变化，而线性RO给出的趋势减弱，方向也在部分月份偏离；由此可解释RO对继续发展/持续的拉尼娜描述不足。',
           'EN和首年LN的半年度残差没有同样增加；但EN若干月份仍有明显方向差异，不能把“其他事件完全由线性RO解释”当作已复现结论。',
           '未解释趋势可能包含外部强迫、随机过程、系数误差和非线性，不能仅凭残差将其全部归因于非线性，更不能直接归因于PMM。', '',
           '4. 原稿一致性与不确定性',
           '原稿未明确归一化窗口、去趋势是否保留均值、差分细节及图3事件筛选。作者的处理后序列和系数未提供。',
           '保持1991—2020参考异常的均值，仅去斜率，会使WWV整体平移+0.238 SD、Niño3.4平移−0.016 SD；重新拟合后，后期偏离结论仍保留。',
           '该偏移由输入数据决定，未按图片调整；它使部分轨迹位置更接近原稿，但仍不足以确认作者方法或解决全部差异。',
           '按四次连续拉尼娜过程分组，每次剔除一个过程：2008、2011、2017、2021/2022。此处只检查合成的事件依赖性，模型保持固定，不是独立验证。',
           '样本仅五个连续LN事件年、四次过程；未报告显著性，也未将此诊断作为独立预报技能。',
           '主结果保留此前使用的均值去除约定，没有依据接近原图程度改选主方法。', '',
           '5. 产物',
           'event_monthly_states_and_tendencies.csv：19×12事件月，两个处理版本。',
           'composite_monthly_states_and_tendencies.csv：三类逐月轨迹、两类趋势、残差及夹角。',
           'halfyear_tendency_metrics.csv：半年度残差、观测速度、RO速度。',
           'leave_one_LaNina_episode_out.csv：剔除整次过程的敏感性。',
           'methods_models_and_QA.json：方法、系数、事件定义、数据哈希和单位/线性合成检查。',
           '复现代码：scripts/reproduce_manuscript_phase_tendencies.py。',
           '来源：用户提供manuscript.pdf第4—6页、第10页3.3节、第11页图3以及第12页图4。']
    (OUT / 'reproduction_report_cn.txt').write_text('\n'.join(cn) + '\n')
    print(primary_stats.to_string(index=False), flush=True)
    print(sens.to_string(index=False), flush=True)
    print('Completed:', OUT, flush=True)


if __name__ == '__main__':
    main()
