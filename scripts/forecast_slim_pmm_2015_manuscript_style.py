#!/usr/bin/env python3
"""2015 standard-PMM extension of the audited seasonal RO, in manuscript style.

Keep paper-period fitting separate from past-only hindcasts. Colored paths are
free forecasts from February--June observed states, NOT local-tendency arrows.
"""
from pathlib import Path
import os
import sys
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
from matplotlib.ticker import MultipleLocator
import run_paper_ro_pmm as base
import paper_ro_slim as slim

OUT = ROOT / 'outputs/research_2026/slim_RO_PMM_2015_manuscript_style_20261014'
EXACT = ROOT / 'outputs/research_2026/manuscript_RO_exact_period_20261014'
PROTOCOLS = {
    'paper_2002_2024': dict(start='2002-01-01', end='2024-12-01', paper=True,
                            title='Fit: 2002–2024 | Retrospective fit includes 2015',
                            short='2002–2024 (includes 2015)'),
    'past_2002_2014': dict(start='2002-01-01', end='2014-12-01', paper=False,
                           title='Fit: 2002–2014 | 2015 excluded from fitting',
                           short='2002–2014 (past only)'),
    'past_1982_2014': dict(start='1982-01-01', end='2014-12-01', paper=False,
                           title='Fit: 1982–2014 | Longer-record sensitivity',
                           short='1982–2014 (past only)'),
}
MODELS = {'RO': ['Nino34', 'WWV'], 'RO_SST': ['Nino34', 'WWV', 'PMM_SST'],
          'RO_wind': ['Nino34', 'WWV', 'PMM_wind'],
          'RO_both': ['Nino34', 'WWV', 'PMM_SST', 'PMM_wind']}
LABELS = {'RO': 'RO', 'RO_SST': 'RO + PMM-SST', 'RO_wind': 'RO + PMM-wind',
          'RO_both': 'RO + both', 'RO_SST_cut': 'PMM-SST coupling cut',
          'RO_both_cut': 'Both PMM couplings cut'}
CORAL = '#DC7D69'
MONTH_COLORS = {2: '#EDAF9D', 3: '#E79783', 4: '#DC7D69', 5: '#C76C5C', 6: '#B35B4E'}
BLACK = '#171717'
DISPLAY_DATES = pd.date_range('2015-01-01', '2016-03-01', freq='MS')
TICKS = pd.to_datetime(['2015-01-01', '2015-04-01', '2015-07-01', '2015-10-01', '2016-01-01', '2016-04-01'])
TICKLABELS = ['Jan\n2015', 'Apr', 'Jul', 'Oct', 'Jan\n2016', 'Apr']
MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(raw, pmm, cfg):
    return base.prepare(raw, pmm, cfg['start'], cfg['end'], cfg['paper'],
                        trend_end='2025-04-01' if cfg['paper'] else None)


def score(frame, scale):
    a = frame[['T', 'H']].to_numpy()
    b = frame[['obs_T', 'obs_H']].to_numpy()
    assert len(a) and np.isfinite(a).all() and np.isfinite(b).all()
    err = a - b
    return dict(n=len(a), T_RMSE=float(np.sqrt(np.mean(err[:, 0]**2))),
                H_RMSE=float(np.sqrt(np.mean(err[:, 1]**2))),
                T_r=float(np.corrcoef(a[:, 0], b[:, 0])[0, 1]),
                H_r=float(np.corrcoef(a[:, 1], b[:, 1])[0, 1]),
                TH_normalized_RMSE=float(np.sqrt(np.mean((err / scale)**2))),
                max_predicted_T=float(a[:, 0].max()), max_observed_T=float(b[:, 0].max()))


def run_models():
    raw, pmm, _ = base.load()
    raw = raw.loc[:'2025-04-01']
    pmm = pmm.loc[:'2025-04-01']
    assert raw.index.is_unique and pmm.index.is_unique
    old = json.loads((EXACT / 'models_exact_period.json').read_text())
    old_a = pd.read_csv(EXACT / 'observations_detrended_2002Jan_2025Apr.csv', index_col=0, parse_dates=True)
    forecasts, prepared_rows, all_models, qa, scores, per_start = [], [], {}, {}, [], []
    states = {}
    for protocol, cfg in PROTOCOLS.items():
        a, meta = prepare(raw, pmm, cfg)
        fits = {name: slim.fit(a.loc[cfg['start']:cfg['end'], cols]) for name, cols in MODELS.items()}
        if cfg['paper']:
            np.testing.assert_allclose(a.loc[old_a.index, base.V], old_a, atol=1e-12)
            np.testing.assert_allclose(fits['RO']['coef'], old['models']['monthly_states']['model']['coef'], atol=1e-12)
        scale = fits['RO']['scale'].copy()
        states[protocol] = dict(a=a, scale=scale, meta=meta)
        saved = a.loc[cfg['start']:('2025-04-01' if cfg['paper'] else '2016-03-01')].copy().rename_axis('time').reset_index()
        saved['protocol'] = protocol
        prepared_rows.append(saved)
        all_models[protocol] = dict(config=cfg, preprocessing=meta, fits=fits)
        diagnostics = dict(training_months=len(a.loc[cfg['start']:cfg['end']]),
                           initial_state_max_error=0., restored_error_max_difference=0.,
                           rk4_24_vs_48_max_difference=0.)
        for name, cols in MODELS.items():
            np.testing.assert_allclose(fits[name]['scale'][:2], scale, atol=1e-12)
        for name in list(MODELS) + ['RO_SST_cut', 'RO_both_cut']:
            cut = name.endswith('_cut')
            fitname = name[:-4] if cut else name
            m = fits[fitname]
            cols = MODELS[fitname]
            for month in range(2, 7):
                ini = pd.Timestamp(2015, month, 1)
                dates = pd.date_range(ini, periods=10, freq='MS')
                x0 = a.loc[ini, cols].to_numpy()
                fc = slim.predict(m, x0, month, months=9, cut_pmm=cut)
                obs = a.loc[dates, base.V].to_numpy()
                assert fc.shape == (10, len(cols)) and np.isfinite(fc).all()
                init_error = float(abs(fc[0] - x0).max())
                assert init_error < 1e-12
                diagnostics['initial_state_max_error'] = max(diagnostics['initial_state_max_error'], init_error)
                rawfc = base.restore(fc, dates, meta)
                physical_error_diff = float(abs((fc[:, :2] - obs) - (rawfc - raw.loc[dates, base.V].to_numpy())).max())
                assert physical_error_diff < 1e-11
                diagnostics['restored_error_max_difference'] = max(diagnostics['restored_error_max_difference'], physical_error_diff)
                if not cut:
                    fc48 = slim.predict(m, x0, month, months=9, steps=48)
                    convergence = float(abs(fc48 - fc).max())
                    assert convergence < 1e-5
                    diagnostics['rk4_24_vs_48_max_difference'] = max(diagnostics['rk4_24_vs_48_max_difference'], convergence)
                for lead, target in enumerate(dates):
                    assert target == ini + pd.DateOffset(months=lead)
                    row = dict(protocol=protocol, model=name, init=ini, month=month,
                               lead=lead, target=target, T=fc[lead, 0], H=fc[lead, 1],
                               obs_T=obs[lead, 0], obs_H=obs[lead, 1],
                               raw_T=rawfc[lead, 0], raw_H=rawfc[lead, 1])
                    row.update({'pred_' + col: fc[lead, j] for j, col in enumerate(cols[2:], start=2)})
                    forecasts.append(row)
        # Causal test on every displayed start, for every actual model. Replace
        # all post-initialization input values: coefficients and forecasts must
        # not change. It intentionally does NOT apply to full-period fitting.
        if not cfg['paper']:
            future_max = 0.
            for month in range(2, 7):
                ini = pd.Timestamp(2015, month, 1)
                changed_raw = raw.copy(); changed_pmm = pmm.copy()
                changed_raw.loc[changed_raw.index > ini, base.V] += 999
                changed_pmm.loc[changed_pmm.index > ini, :] -= 999
                aa, mm = prepare(changed_raw, changed_pmm, cfg)
                for name, cols in MODELS.items():
                    m2 = slim.fit(aa.loc[cfg['start']:cfg['end'], cols])
                    f1 = slim.predict(fits[name], a.loc[ini, cols].to_numpy(), month, months=9)
                    f2 = slim.predict(m2, aa.loc[ini, cols].to_numpy(), month, months=9)
                    future_max = max(future_max, float(abs(f1 - f2).max()))
            assert future_max < 1e-10
            diagnostics['post_initialization_input_perturbation_max_difference'] = future_max
        # Independent unit transform verifies normalization of the extended model.
        factors = np.array([3., 100., .2, 10.])
        cols = MODELS['RO_both']
        scaled = a.loc[cfg['start']:cfg['end'], cols] * factors
        m_scaled = slim.fit(scaled)
        ini = pd.Timestamp('2015-03-01')
        f_scaled = slim.predict(m_scaled, a.loc[ini, cols].to_numpy() * factors, 3, months=9) / factors
        f_ref = slim.predict(fits['RO_both'], a.loc[ini, cols].to_numpy(), 3, months=9)
        unit_error = float(abs(f_scaled - f_ref).max())
        assert unit_error < 1e-8
        diagnostics['state_unit_invariance_max_difference'] = unit_error
        qa[protocol] = diagnostics
        print('Completed fit / forecasts / QA:', protocol, flush=True)
    f = pd.DataFrame(forecasts)
    assert len(f) == 900 and not f.duplicated(['protocol', 'model', 'init', 'lead']).any()
    for (protocol, model), g in f[f.lead.between(1, 9)].groupby(['protocol', 'model'], sort=False):
        assert len(g) == 45
        scores.append(dict(protocol=protocol, model=model, **score(g, states[protocol]['scale'])))
        for month, v in g.groupby('month'):
            assert len(v) == 9
            per_start.append(dict(protocol=protocol, model=model, init_month=month, **score(v, states[protocol]['scale'])))
    s = pd.DataFrame(scores)
    for protocol in PROTOCOLS:
        ref = s[s.protocol.eq(protocol) & s.model.eq('RO')].iloc[0]
        mask = s.protocol.eq(protocol)
        for v in ['T', 'H', 'TH_normalized']:
            s.loc[mask, v + '_RMSE_improvement_pct'] = 100 * (1 - s.loc[mask, v + '_RMSE'] / ref[v + '_RMSE'])
    f.to_csv(OUT / 'forecasts_2015.csv', index=False)
    s.to_csv(OUT / 'event_scores_2015.csv', index=False)
    pd.DataFrame(per_start).to_csv(OUT / 'scores_by_initialization.csv', index=False)
    pd.concat(prepared_rows, ignore_index=True).to_csv(OUT / 'processed_states.csv', index=False)
    (OUT / 'models_and_preprocessing.json').write_text(json.dumps(all_models, default=base.jsonable, indent=2))
    (OUT / 'numerical_QA.json').write_text(json.dumps(qa, indent=2))
    return f, s, states, qa


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5,
                         'axes.titlesize': 13, 'axes.titleweight': 'bold',
                         'axes.labelsize': 11, 'axes.linewidth': 1.0,
                         'axes.spines.top': True, 'axes.spines.right': True,
                         'xtick.direction': 'in', 'ytick.direction': 'in',
                         'xtick.top': True, 'ytick.right': True,
                         'xtick.major.size': 4, 'ytick.major.size': 4,
                         'savefig.facecolor': 'white', 'svg.fonttype': 'none'})


def save(fig, stem):
    fig.savefig(OUT / (stem + '.png'), dpi=250, bbox_inches='tight')
    fig.savefig(OUT / (stem + '.svg'), bbox_inches='tight')
    plt.close(fig)


def nice_limits(values, step, pad=.1):
    a = np.asarray(values)
    return (step * np.floor((a.min() - pad) / step), step * np.ceil((a.max() + pad) / step))


def common_limits(f, states):
    ts, hs, xs, ys = [], [], [], []
    for protocol in PROTOCOLS:
        a = states[protocol]['a'].loc[DISPLAY_DATES, base.V].to_numpy()
        v = f[f.protocol.eq(protocol) & f.model.isin(MODELS)][['T', 'H']].to_numpy()
        a = np.concatenate([a, v])
        ts.extend(a[:, 0]); hs.extend(a[:, 1])
        z = a / states[protocol]['scale']
        xs.extend(z[:, 0]); ys.extend(z[:, 1])
    return dict(T=nice_limits(ts, .5), H=nice_limits(hs, 5, .7),
                x=nice_limits(xs, .5), y=nice_limits(ys, .5))


def arrows(ax, xy, color, positions, lw=1.3, size=10):
    for i in positions:
        if i + 1 >= len(xy):
            continue
        start = xy[i] + .15 * (xy[i+1] - xy[i])
        end = xy[i] + .83 * (xy[i+1] - xy[i])
        ax.annotate('', xy=end, xytext=start,
                    arrowprops=dict(arrowstyle='-|>', color=color, lw=lw,
                                    mutation_scale=size, shrinkA=0, shrinkB=0), zorder=5)


def phase_panel(ax, f, states, protocol, model, limits, panel):
    a = states[protocol]['a'].loc[DISPLAY_DATES, base.V].to_numpy()
    scale = states[protocol]['scale']
    obs = a / scale
    ax.plot(obs[:, 0], obs[:, 1], '-o', color=BLACK, lw=2.3, ms=3.5, zorder=4)
    arrows(ax, obs, BLACK, [2, 5, 8, 11], 1.4, 11)
    q = f[f.protocol.eq(protocol) & f.model.eq(model)]
    for month, g in q.groupby('month'):
        xy = g.sort_values('lead')[['T', 'H']].to_numpy() / scale
        ax.plot(xy[:, 0], xy[:, 1], '-o', color=MONTH_COLORS[month], lw=1.35,
                ms=2.0, alpha=.92, zorder=2)
        ax.scatter(*xy[0], s=25, facecolors='white', edgecolors=MONTH_COLORS[month], zorder=6)
        arrows(ax, xy, MONTH_COLORS[month], [4, 7], .95, 8)
    # Labels sit on observations; all forecast start dates are also explicit
    # in the caption. Path arrows are time directions, not tendency estimates.
    for i, label, offset in [(0, 'Jan 2015', (-44, 17)), (8, 'Sep', (7, 2)),
                              (11, 'Dec', (7, 2)), (14, 'Mar 2016', (6, 7))]:
        ax.annotate(label, obs[i], textcoords='offset points', xytext=offset,
                    fontsize=9, color=BLACK, zorder=7,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.8, pad=.4))
    ax.axhline(0, color='.35', ls='--', lw=.7)
    ax.axvline(0, color='.35', ls='--', lw=.7)
    ax.set(xlim=limits['x'], ylim=limits['y'], xlabel='Normalized Niño3.4 SSTA', ylabel='Normalized WWV')
    ax.set_box_aspect(1)
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.yaxis.set_major_locator(MultipleLocator(1))
    model_title = 'RO' if model == 'RO' else 'RO + PMM'
    ax.set_title(f'({panel})  SST–WWV Phase Diagram ({model_title})', pad=10)


def time_axes(ax, variable, limits):
    ax.set_xlim(pd.Timestamp('2015-01-01'), pd.Timestamp('2016-04-01'))
    ax.set_xticks(TICKS, TICKLABELS)
    ax.set_ylim(limits[variable])
    ax.axhline(0, color='.25', lw=.75)
    if variable == 'T':
        ax.axhline(.5, color='.3', lw=.7, ls='--')
        ax.axhline(-.5, color='.3', lw=.7, ls='--')
    ax.axvline(pd.Timestamp('2016-01-01'), color=CORAL, ls='--', lw=1.0, alpha=.8)
    ax.set_ylabel('Niño3.4 SSTA (°C)' if variable == 'T' else 'WWV proxy anomaly (m)')


def combined_time(ax, f, states, protocol, limits):
    obs = states[protocol]['a'].loc[DISPLAY_DATES]
    ax.plot(obs.index, obs.Nino34, color=BLACK, lw=2.5, zorder=5)
    for model, ls, color, width in [('RO', '--', '#999999', 1.1), ('RO_SST', '-', CORAL, 1.5)]:
        q = f[f.protocol.eq(protocol) & f.model.eq(model)]
        for month, g in q.groupby('month'):
            ax.plot(g.target, g['T'], color=color, ls=ls, lw=width, alpha=.90, zorder=3)
    time_axes(ax, 'T', limits)
    ax.set_title('(c)  Observed and Predicted Niño3.4 Index', pad=10)
    ax.legend(handles=[Line2D([0], [0], color=BLACK, lw=2, label='Observed'),
                       Line2D([0], [0], color='#999999', ls='--', lw=1.5, label='RO'),
                       Line2D([0], [0], color=CORAL, lw=2, label='RO + PMM')],
              loc='upper left', fontsize=8.5, frameon=False)


def skill_panel(ax, s, protocol):
    q = s[s.protocol.eq(protocol)].set_index('model').loc[['RO', 'RO_SST']]
    values = q.T_r.to_numpy()
    ax.bar([0, 1], values, width=.55, color=['#EAB5A8', CORAL], edgecolor='.25', lw=.8)
    for x, v in enumerate(values):
        ax.text(x, v + (.035 if v >= 0 else -.035), f'{v:.2f}', ha='center',
                va='bottom' if v >= 0 else 'top', fontsize=10)
    ax.axhline(0, color='.35', lw=.7)
    ax.set(xlim=(-.6, 1.6), ylim=(-.9, 1.12), ylabel='Correlation coefficient',
           xticks=[0, 1], xticklabels=['RO', 'RO +\nPMM'])
    ax.set_title('(d)  Prediction Skill\n(2015)', pad=10)
    ax.text(.05, .045, f'RMSE (°C)\n{q.T_RMSE.iloc[0]:.2f} → {q.T_RMSE.iloc[1]:.2f}',
            transform=ax.transAxes, fontsize=9, linespacing=1.4)


def main_figure(f, s, states, protocol, limits):
    fig = plt.figure(figsize=(12, 9.4))
    gs = fig.add_gridspec(2, 4, left=.08, right=.975, top=.88, bottom=.14,
                          height_ratios=[1.35, 1], hspace=.48, wspace=.95)
    axa = fig.add_subplot(gs[0, :2]); axb = fig.add_subplot(gs[0, 2:])
    axc = fig.add_subplot(gs[1, :3]); axd = fig.add_subplot(gs[1, 3])
    phase_panel(axa, f, states, protocol, 'RO', limits, 'a')
    phase_panel(axb, f, states, protocol, 'RO_SST', limits, 'b')
    axa.legend(handles=[Line2D([0], [0], color=BLACK, lw=2, label='Observed'),
                        Line2D([0], [0], color=CORAL, lw=2, label='Forecasts: Feb–Jun starts')],
               loc='lower left', fontsize=8, frameon=False)
    combined_time(axc, f, states, protocol, limits)
    skill_panel(axd, s, protocol)
    fig.suptitle('2015 El Niño: Seasonal RO and Standard PMM', fontsize=17, fontweight='bold', y=.99)
    fig.text(.5, .948, PROTOCOLS[protocol]['title'], ha='center', fontsize=11,
             color='#9B4335' if protocol.startswith('paper') else BLACK)
    scale = states[protocol]['scale']
    fig.text(.08, .035,
             'February–June monthly-state initializations; leads 1–9 months (45 pairs). PMM = canonical MCA SST index.\n'
             'Path arrows indicate time; every colored trajectory is freely integrated after initialization, including PMM.\n'
             f'WWV proxy: GODAS mean D20. Shared phase scales: σT = {scale[0]:.3f} °C; σh = {scale[1]:.3f} m. '
             'Lead 0 is shown but not scored.\n'
             'Figure design follows manuscript Fig. 3; the forecasts are for the observed 2015 event, not a synthetic simulation.',
             fontsize=8.5, linespacing=1.5)
    save(fig, protocol + '_manuscript_style')


def plume_figure(f, s, states, protocol, limits):
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey='row')
    fig.subplots_adjust(left=.085, right=.975, top=.79, bottom=.17, hspace=.32, wspace=.18)
    obs = states[protocol]['a'].loc[DISPLAY_DATES]
    for col, model in enumerate(['RO', 'RO_SST']):
        q = f[f.protocol.eq(protocol) & f.model.eq(model)]
        ss = s[s.protocol.eq(protocol) & s.model.eq(model)].iloc[0]
        for row, (var, column) in enumerate([('T', 'Nino34'), ('H', 'WWV')]):
            ax = axes[row, col]
            ax.plot(obs.index, obs[column], color=BLACK, lw=2.5, zorder=5)
            for month, g in q.groupby('month'):
                ax.plot(g.target, g[var], color=MONTH_COLORS[month], lw=1.65, zorder=3)
                ax.scatter(g.target.iloc[0], g[var].iloc[0], s=16, facecolors='white', edgecolors=MONTH_COLORS[month], zorder=6)
            time_axes(ax, var, limits)
            letter = 'abcd'[row * 2 + col]
            ax.set_title(f'({letter})  {"Niño3.4" if var == "T" else "WWV"}: {LABELS[model]}', pad=10)
            units = '°C' if var == 'T' else 'm'
            ax.text(.03, .96, f'r = {ss[var + "_r"]:.2f}; RMSE = {ss[var + "_RMSE"]:.2f} {units}',
                    transform=ax.transAxes, va='top', fontsize=10,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.8))
    handles = [Line2D([0], [0], color=BLACK, lw=2.3, label='Observed')]
    handles += [Line2D([0], [0], color=MONTH_COLORS[m], lw=2, label=MONTH_LABELS[m-1] + ' start') for m in range(2, 7)]
    fig.suptitle('Observed and Predicted Niño3.4 / WWV: 2015', fontweight='bold', fontsize=17, y=.99)
    fig.text(.5, .935, PROTOCOLS[protocol]['title'], ha='center', fontsize=11)
    fig.legend(handles=handles, ncol=6, loc='upper center', bbox_to_anchor=(.5, .906), frameon=False, fontsize=9)
    fig.text(.085, .047, 'Manuscript Fig. 4 plume convention: observed black line; coral El Niño forecasts from February–June.\n'
             'Monthly leads 1–9; no future PMM observations. Each row shares its y-axis across both models and all fitting protocols.\n'
             'T and h are shown in their protocol-specific detrended anomaly coordinates. PMM denotes the standard MCA SST coefficient.',
             fontsize=8.5, linespacing=1.5)
    save(fig, protocol + '_T_WWV_plumes')


def ablation_figure(s):
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 7), sharey='row')
    fig.subplots_adjust(left=.075, right=.98, top=.82, bottom=.18, hspace=.31, wspace=.23)
    model_order = list(MODELS)
    labels = ['RO', '+ SST', '+ Wind', '+ Both']
    colors = ['#E6C0B7', '#DC7D69', '#DC7D69', '#DC7D69']
    for col, protocol in enumerate(PROTOCOLS):
        q = s[s.protocol.eq(protocol)].set_index('model').loc[model_order]
        for row, variable in enumerate(['T', 'H']):
            ax = axes[row, col]
            values = q[variable + '_RMSE'].to_numpy()
            bars = ax.bar(range(4), values, color=colors, edgecolor='.25', width=.67, lw=.8)
            bars[2].set_hatch('//'); bars[3].set_hatch('..')
            for x, value in enumerate(values):
                ax.text(x, value + (.04 if variable == 'T' else .08), f'{value:.2f}', ha='center', fontsize=9,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.95, pad=.5))
            ax.axhline(values[0], color='.35', lw=.8, ls='--')
            ax.set_xticks(range(4), labels)
            ax.set_ylim(0, 2.45 if variable == 'T' else 5.65)
            ax.grid(axis='y', alpha=.13)
            if col == 0:
                ax.set_ylabel('Niño3.4 RMSE (°C)' if variable == 'T' else 'WWV proxy RMSE (m)')
        axes[0, col].set_title(PROTOCOLS[protocol]['short'], fontsize=11, pad=13)
    fig.suptitle('2015 PMM Ablation: Matched Forecast Targets', fontweight='bold', fontsize=17, y=.985)
    fig.text(.5, .923, 'Same seasonal sLIM for every model | Lower RMSE is better | No variant selected by 2015 skill', ha='center', fontsize=10)
    fig.text(.075, .045, 'Standard PMM-SST and PMM-wind are the two canonical MCA expansion coefficients, not regional proxy indices.\n'
             'All models are refitted within the labeled training period; PMM evolves freely after initialization.\n'
             'Five overlapping starts and nine monthly leads represent one event, so these bars have no independent-event confidence intervals.',
             fontsize=9, linespacing=1.5)
    save(fig, 'PMM_ablation_all_protocols')


def report(s, qa, limits):
    lines = ['2015：季节 sLIM–RO 加入标准 PMM，按原稿图式呈现', '',
             '本次新增：在图3a/图4复现所用RO基准上，重估加入标准PMM的联合动力矩阵，预报真实2015年事件。',
             'PMM扩展不是原稿已有结果。未按2015效果调整参数、事件振幅或去趋势方式。', '',
             '图式：主图上排为横轴Niño3.4/纵轴WWV的RO与RO+PMM相图；下排为黑色观测、灰虚线RO、珊瑚红PMM羽状预报，以及相关系数柱状图。',
             '遵循原稿图3的四面板布局、闭合边框和向内刻度；时间序列延续图4的黑实况/红暖事件预报。',
             '原稿图3a是观测状态上的局地趋势；本次相图是实际向前积分的预报轨迹，箭头只表示时间方向。',
             '相图和时间序列都使用2015年2—6月五个起报，1—9个月提前期。没有沿途重置至实况。',
             '起报月份指月均初始状态月份，不是IRI签发月份。初值月lead0仅绘图，不计分；每组45个起报—目标对。', '',
             'PMM定义：主方案固定为作者公开标准MCA SST系数。提供者说明SST系数通常更代表耦合模态；同时保留标准风系数和两者同时加入的消融。',
             'PMM仅去训练均值并按训练标准差缩放，不额外回归剔除ENSO、不做三月平滑、不使用区域代用指标。',
             'PMM与T/h全部作为状态向前自由积分；不输入起报后的PMM实况。', '',
             '三种拟合：',
             'paper_2002_2024：完全复用上一轮T/h预处理，气候态1991—2020，去趋势2002年1月—2025年4月，拟合2002—2024。包含2015，属于样本内重建/扩展。',
             'past_2002_2014：与原稿相同训练起点，但气候态、趋势和全部系数只用2002—2014，2015不参与拟合。独立事件回报的主方案。',
             'past_1982_2014：仅将历史训练起点延长至1982，作为训练长度敏感性；没有因表现更好而替换短训练主方案。',
             '这些回报使用当前版本再分析/PMM，属于伪业务回报，并未重建2015年的实时发布版本。PMM空间模态固定期1950—2005早于验证事件；产品原有历史预处理不可完全控制。', '',
             '模型：二阶季节扰动sLIM，年周期和半年周期；月序列六步线性插值，均值算子滞后六步、季节修正滞后一步，中心差分。',
             '原始RO与加入PMM的模型均用同样估计器和时段；扩展模型会重新估计T/h内部系数。',
             'RO_SST_cut / RO_both_cut仅在完整模型中切断PMM→T/h系数，用于机制检查，和重新拟合的RO不是同一种消融。', '',
             '汇总（同一模型坐标内的相关系数；RMSE等价于恢复原始物理量后的误差）：',
             s[s.model.isin(MODELS)][['protocol', 'model', 'T_RMSE', 'T_r', 'H_RMSE', 'H_r',
                                       'T_RMSE_improvement_pct', 'H_RMSE_improvement_pct']].to_string(index=False), '']
    for protocol in PROTOCOLS:
        q = s[s.protocol.eq(protocol)].set_index('model')
        a, b = q.loc['RO'], q.loc['RO_SST']
        lines += [f'{protocol}：T RMSE {a.T_RMSE:.3f} → {b.T_RMSE:.3f} °C（{b.T_RMSE_improvement_pct:+.2f}%）；'
                  f'h RMSE {a.H_RMSE:.3f} → {b.H_RMSE:.3f} m（{b.H_RMSE_improvement_pct:+.2f}%）。',
                  f'所有匹配预报中的T最大值：RO {a.max_predicted_T:.3f}、+PMM {b.max_predicted_T:.3f}、匹配观测 {a.max_observed_T:.3f} °C。']
    lines += ['', '结论与限制：',
              '论文拟合窗口下PMM-SST能改善本个例T和h；但该拟合已经包含2015，不能用它证明独立预报增益。',
              '仅用2002—2014训练时，PMM-SST降低T误差，但h误差增加；两模型仍明显低估2015的增暖。',
              '长训练同样降低T误差，仍未改善h；2015单个事件不支持稳定的整体预报提升结论。',
              '三种协议的预处理与标准差不同：比较PMM贡献应在各协议内部进行，不能只横比标准化相图位置或相关系数。',
              '所有图的轴范围统一；每个协议内RO和PMM共享T/h标准差、初值和观测线。WWV使用GODAS区域平均D20代理，物理单位m。',
              '不显示显著性或虚构误差条：五个起报×九个目标是重叠预报，不是45个独立事件。', '',
              '验证：已核对与上一轮原稿RO系数和处理后指数一致；检查初值、日期、无缺测、未来输入扰动不改变独立回报、积分加密收敛、状态单位不变性及物理误差还原。',
              json.dumps(qa, ensure_ascii=False, indent=2), '',
              '主图：paper_2002_2024_manuscript_style.png/svg；past_2002_2014_manuscript_style.png/svg；past_1982_2014_manuscript_style.png/svg。',
              'T和WWV单独羽状预报：三个协议各自的*_T_WWV_plumes.png/svg。',
              'PMM_SST/wind/两者消融：PMM_ablation_all_protocols.png/svg；切断耦合结果见event_scores_2015.csv。',
              '逐预报数值forecasts_2015.csv；逐起报评分scores_by_initialization.csv；处理后状态processed_states.csv。',
              '代码scripts/forecast_slim_pmm_2015_manuscript_style.py；模型models_and_preprocessing.json；核查numerical_QA.json；固定方案protocol_before_run.txt。', '',
              '方法与图式来源：用户提供manuscript.pdf第4—6、11—12页；sLIM Chen & Jin (2021), DOI 10.1175/JCLI-D-20-0874.1。',
              '标准PMM及说明：https://www.aos.wisc.edu/dvimont/MModes/PMM.html；https://www.aos.wisc.edu/dvimont/MModes/RealTime/PMM.txt。']
    (OUT / 'results_cn.txt').write_text('\n'.join(lines) + '\n')
    manifest = dict(code=dict(path=str(Path(__file__)), sha256=sha(__file__)),
                    input_files=[dict(path=str(path), sha256=sha(path)) for path in
                                 [base.SOURCE / 'raw_indices.csv', base.PMM,
                                  EXACT / 'observations_detrended_2002Jan_2025Apr.csv',
                                  ROOT / 'scripts/paper_ro_slim.py', OUT / 'protocol_before_run.txt']],
                    plotting_limits=limits, lead0_excluded_from_scores=True,
                    paper_like_does_not_mean_author_exact_replication=True,
                    pmm_main_choice='standard MCA SST index; retained before run')
    (OUT / 'provenance.json').write_text(json.dumps(manifest, indent=2))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert (OUT / 'protocol_before_run.txt').exists()
    style()
    if '--plot-only' in sys.argv:
        f = pd.read_csv(OUT / 'forecasts_2015.csv', parse_dates=['init', 'target'])
        s = pd.read_csv(OUT / 'event_scores_2015.csv')
        models = json.loads((OUT / 'models_and_preprocessing.json').read_text())
        # Rebuild saved display states from the already frozen preprocessing.
        # No coefficient estimation or QA reruns are needed for layout edits.
        raw, pmm, _ = base.load()
        states, rows = {}, []
        for protocol, cfg in PROTOCOLS.items():
            a, meta = prepare(raw.loc[:'2025-04-01'], pmm.loc[:'2025-04-01'], cfg)
            states[protocol] = dict(a=a, scale=np.asarray(models[protocol]['fits']['RO']['scale']), meta=meta)
            saved = a.loc[cfg['start']:('2025-04-01' if cfg['paper'] else '2016-03-01')].copy().rename_axis('time').reset_index()
            saved['protocol'] = protocol
            rows.append(saved)
        pd.concat(rows, ignore_index=True).to_csv(OUT / 'processed_states.csv', index=False)
        qa = json.loads((OUT / 'numerical_QA.json').read_text())
    else:
        f, s, states, qa = run_models()
    limits = common_limits(f, states)
    for protocol in PROTOCOLS:
        main_figure(f, s, states, protocol, limits)
        plume_figure(f, s, states, protocol, limits)
    ablation_figure(s)
    report(s, qa, limits)
    print(s[s.model.isin(MODELS)].to_string(index=False), flush=True)
    print('OUTPUT:', OUT, flush=True)


if __name__ == '__main__':
    main()
