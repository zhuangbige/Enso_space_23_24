"""Render the saved 2026 experiment using the user's 2015 figure style.

Only saved forecasts, scores, processed states and model metadata are read.
No fitting, source-data processing, or score selection occurs during rendering.
"""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/slim_RO_PMM_2026_manuscript_style_20261014'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/ro_pmm_mpl_2026'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd

BLACK = '#171717'
CORAL = '#DC7D69'
MONTH_COLORS = {2: '#EDAF9D', 3: '#E79783', 4: '#DC7D69', 5: '#C76C5C', 6: '#B35B4E'}
PROTOCOL = 'consistent_reconstruction'
STEM = 'figure_2026_RO_vs_reconstructed_PMM'


def style():
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 10.5,
        'axes.titlesize': 13, 'axes.titleweight': 'bold', 'axes.labelsize': 11,
        'axes.linewidth': 1.0, 'axes.spines.top': True, 'axes.spines.right': True,
        'xtick.direction': 'in', 'ytick.direction': 'in',
        'xtick.top': True, 'ytick.right': True,
        'xtick.major.size': 4, 'ytick.major.size': 4,
        'savefig.facecolor': 'white', 'svg.fonttype': 'none', 'pdf.fonttype': 42,
    })


def arrows(ax, xy, color, positions, lw=1.3, size=10):
    for i in positions:
        if i + 1 >= len(xy):
            continue
        delta = xy[i + 1] - xy[i]
        ax.annotate('', xy=xy[i] + .83 * delta, xytext=xy[i] + .15 * delta,
                    arrowprops=dict(arrowstyle='-|>', color=color, lw=lw,
                                    mutation_scale=size, shrinkA=0, shrinkB=0), zorder=5)


def limits(values, step=.5, pad=.18):
    values = np.asarray(values)
    return (float(step * np.floor((np.nanmin(values) - pad) / step)),
            float(step * np.ceil((np.nanmax(values) + pad) / step)))


def render_main(f, score, a, qa, scale, output=OUT):
    style()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    q = f[f.protocol.eq(PROTOCOL) & f.month.between(2, 6) & f.model.isin(['RO', 'RO_SST'])]
    metrics = score[score.protocol.eq(PROTOCOL)].set_index('model').loc[['RO', 'RO_SST']]
    obs = a.loc['2026', ['Nino34', 'WWV']]
    joint = obs.dropna() / scale
    xy_all = np.concatenate([joint.values, q[['T', 'H']].values / scale])
    phase_limits = [limits(xy_all[:, i]) for i in range(2)]
    t_limits = limits(np.r_[obs.Nino34.dropna().values, q['T'].values], pad=.2)
    last_joint = min(pd.Timestamp(qa['latest_T']), pd.Timestamp(qa['latest_H']))
    last_sst = pd.Timestamp(qa['latest_T'])

    # Match the reference: square phase panels above a wide time plot and skill bar.
    fig = plt.figure(figsize=(12, 9.6))
    gs = fig.add_gridspec(2, 4, left=.08, right=.975, top=.865, bottom=.18,
                          height_ratios=[1.35, 1], hspace=.48, wspace=.95)
    axa = fig.add_subplot(gs[0, :2])
    axb = fig.add_subplot(gs[0, 2:])
    axc = fig.add_subplot(gs[1, :3])
    axd = fig.add_subplot(gs[1, 3])

    for ax, model, panel in [(axa, 'RO', 'a'), (axb, 'RO_SST', 'b')]:
        ax.plot(joint.Nino34, joint.WWV, '-o', color=BLACK, lw=2.3, ms=3.5, zorder=4)
        arrows(ax, joint.values, BLACK, [1, 3, 6], 1.4, 11)
        for month, g in q[q.model.eq(model)].groupby('month'):
            g = g.sort_values('lead')
            xy = g[['T', 'H']].values / scale
            seen = g.target.le(last_joint).to_numpy()
            end = int(np.flatnonzero(seen)[-1])
            ax.plot(xy[:end + 1, 0], xy[:end + 1, 1], '-o', color=MONTH_COLORS[month],
                    lw=1.35, ms=2, alpha=.92, zorder=2)
            ax.plot(xy[end:, 0], xy[end:, 1], ':o', color=MONTH_COLORS[month],
                    lw=1.25, ms=2, alpha=.92, zorder=2)
            ax.scatter(*xy[0], s=25, facecolors='white', edgecolors=MONTH_COLORS[month], zorder=6)
            arrows(ax, xy, MONTH_COLORS[month], [3, 7], .95, 8)
        for month, label, offset in [(1, 'Jan 2026', (6, -15)), (4, 'Apr', (-28, 10)),
                                      (6, 'Jun', (7, 8)), (8, 'Aug', (7, 3))]:
            point = joint.loc[pd.Timestamp(2026, month, 1)].values
            ax.annotate(label, point, xytext=offset, textcoords='offset points',
                        fontsize=9, color=BLACK, zorder=7,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=.8, pad=.4))
        ax.axhline(0, color='.35', ls='--', lw=.7)
        ax.axvline(0, color='.35', ls='--', lw=.7)
        ax.set(xlim=phase_limits[0], ylim=phase_limits[1],
               xlabel='Normalized Niño3.4 SSTA', ylabel='Normalized WWV')
        ax.set_box_aspect(1)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.yaxis.set_major_locator(MultipleLocator(1))
        model_label = 'RO' if model == 'RO' else 'RO + PMM'
        ax.set_title(f'({panel})  SST–WWV Phase Diagram ({model_label})', pad=10)
    axa.legend(handles=[Line2D([0], [0], color=BLACK, lw=2, label='Observed'),
                        Line2D([0], [0], color=CORAL, lw=2, label='Forecasts: Feb–Jun starts')],
               loc='lower left', fontsize=8, frameon=False)

    # Every trajectory is retained through lead 9; shading separates unavailable truth.
    boundary = last_sst + (last_sst + pd.offsets.MonthBegin(1) - last_sst) / 2
    axc.axvspan(boundary, pd.Timestamp('2027-04-01'), color='.95', zorder=0)
    axc.axvline(boundary, color='.65', lw=.65, ls=':', zorder=1)
    observed_t = obs.Nino34.dropna()
    axc.plot(observed_t.index, observed_t.values, color=BLACK, lw=2.5, zorder=5)
    for model, ls, color, width in [('RO', '--', '#999999', 1.1), ('RO_SST', '-', CORAL, 1.5)]:
        for _, g in q[q.model.eq(model)].groupby('month'):
            g = g.sort_values('lead')
            axc.plot(g.target, g['T'], color=color, ls=ls, lw=width, alpha=.90, zorder=3)
    axc.axhline(0, color='.25', lw=.75)
    for threshold in [-.5, .5]:
        axc.axhline(threshold, color='.3', lw=.7, ls='--')
    axc.axvline(pd.Timestamp('2027-01-01'), color=CORAL, ls='--', lw=1, alpha=.8)
    ticks = pd.to_datetime(['2026-01-01', '2026-04-01', '2026-07-01', '2026-10-01',
                            '2027-01-01', '2027-04-01'])
    axc.set_xticks(ticks, ['Jan\n2026', 'Apr', 'Jul', 'Oct', 'Jan\n2027', 'Apr'])
    axc.set(xlim=(ticks[0], ticks[-1]), ylim=t_limits, ylabel='Niño3.4 SSTA (°C)')
    axc.yaxis.set_major_locator(MultipleLocator(.5))
    axc.set_title('(c)  Observed and Predicted Niño3.4 Index', pad=10)
    axc.legend(handles=[Line2D([0], [0], color=BLACK, lw=2, label='Observed'),
                        Line2D([0], [0], color='#999999', ls='--', lw=1.5, label='RO'),
                        Line2D([0], [0], color=CORAL, lw=2, label='RO + PMM')],
               loc='upper left', fontsize=8.5, frameon=False)
    axc.text(.98, .955, 'No observations yet', ha='right', va='top',
             transform=axc.transAxes, color='.45', fontsize=8.5)

    values = metrics.T_r.to_numpy()
    axd.bar([0, 1], values, width=.55, color=['#EAB5A8', CORAL], edgecolor='.25', lw=.8)
    for x, value in enumerate(values):
        axd.text(x, value + .035, f'{value:.2f}', ha='center', va='bottom', fontsize=10)
    axd.axhline(0, color='.35', lw=.7)
    axd.set(xlim=(-.6, 1.6), ylim=(-.9, 1.12), ylabel='Correlation coefficient',
            xticks=[0, 1], xticklabels=['RO', 'RO +\nPMM'])
    axd.set_title('(d)  Prediction Skill\n(2026)', pad=10)
    axd.text(.05, .045, f'RMSE (°C)\n{metrics.T_RMSE.iloc[0]:.2f} → {metrics.T_RMSE.iloc[1]:.2f}',
             transform=axd.transAxes, fontsize=9, linespacing=1.4)

    fig.suptitle('2026 El Niño: Seasonal RO and Reconstructed PMM',
                 fontsize=17, fontweight='bold', y=.98)
    fig.text(.5, .938, 'Fit: 2002–2024 | 2026 excluded from parameter fitting',
             ha='center', fontsize=11, color='#9B4335')
    pairs = int(metrics.T_n.iloc[0])
    assert (metrics.T_n == pairs).all()
    fig.text(.08, .023,
             f'February–June monthly-state initializations; leads 1–9 months. Skill uses {pairs} observed Niño3.4 pairs; lead 0 is not scored.\n'
             'PMM = ERSSTv5 SST projection onto the fixed R1 MCA mode (1950–2005); reconstructed extension beyond official PMM.\n'
             'Path arrows indicate time; all states, including PMM, evolve freely. Dotted phase segments extend beyond observed WWV.\n'
             'Observed SST through Sep 2026; WWV through Aug 2026. Shaded time range is unverified and excluded from skill.\n'
             f'WWV proxy: GODAS mean D20. Shared scales: σT = {scale[0]:.3f} °C; σh = {scale[1]:.3f} m. Detrended manuscript coordinates.',
             fontsize=8.3, linespacing=1.5)
    for ext in ['png', 'svg', 'pdf']:
        fig.savefig(output / f'{STEM}.{ext}', dpi=250, bbox_inches='tight')
    plt.close(fig)
    return {'phase_xlim': phase_limits[0], 'phase_ylim': phase_limits[1],
            'sst_ylim': t_limits, 'sst_skill_pairs': pairs,
            'correlations': dict(zip(metrics.index, values)),
            'rmse_degC': metrics.T_RMSE.to_dict(),
            'rendering_only': True, 'reference': 'User-provided 2015 manuscript-style figure'}


def main():
    names = ['forecasts_2026.csv', 'event_scores_2026.csv',
             'processed_states_consistent_reconstruction.csv', 'models_and_preprocessing.json', 'numerical_QA.json']
    hashes = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in names}
    f = pd.read_csv(OUT / names[0], parse_dates=['init', 'target'])
    s = pd.read_csv(OUT / names[1])
    a = pd.read_csv(OUT / names[2], index_col=0, parse_dates=True)
    models = json.loads((OUT / names[3]).read_text())
    qa = json.loads((OUT / names[4]).read_text())
    scale = np.asarray(models[PROTOCOL]['fits']['RO']['scale'])
    info = render_main(f, s, a, qa, scale)
    info['input_sha256'] = hashes
    for name, digest in hashes.items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest
    (OUT / 'figure_style_provenance.json').write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
