"""IRI-only forecast/observation figures, using the verified archived plume values."""
from pathlib import Path
import hashlib
import json
import os
import shutil
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/IRI_RO_PMM_2015_2026_20261014'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/iri_comparison_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

MODELS = ['NCEP CFSv2', 'NASA GMAO', 'CMC CANSIP', 'JMA']
LABELS = {'NCEP CFSv2': 'NCEP CFSv2', 'NASA GMAO': 'NASA GMAO',
          'CMC CANSIP': 'CMC CanSIPS', 'JMA': 'JMA'}
COLORS = {2: '#EDAF9D', 3: '#E79783', 4: '#DC7D69', 5: '#C76C5C', 6: '#B35B4E'}


def observed_reference(observed, year, issue_month):
    """Reference observation, not an unavailable model analysis/initial state.

    A February issue can reference NDJ ending in January (centered December).
    A centered February observation would include March and must not be used.
    """
    issue = pd.Timestamp(year, issue_month, 1)
    center = issue - pd.DateOffset(months=2)
    end = center + pd.DateOffset(months=1)
    assert end < issue
    value = float(observed.loc[center])
    assert np.isfinite(value)
    return center, value


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5,
                         'axes.titlesize': 13, 'axes.titleweight': 'bold', 'axes.labelsize': 11,
                         'axes.linewidth': 1, 'xtick.direction': 'in', 'ytick.direction': 'in',
                         'xtick.top': True, 'ytick.right': True, 'svg.fonttype': 'none',
                         'pdf.fonttype': 42, 'savefig.facecolor': 'white'})


def legend():
    return [Line2D([], [], color='#171717', lw=2.4, label='Observed')] + [
        Line2D([], [], color=COLORS[m], marker='o', ms=3, lw=1.6,
               label=pd.Timestamp(2000, m, 1).strftime('%b') + ' issue') for m in range(2, 7)]


def panel(ax, iri, observed, year, model, ylim, compact=False):
    dates = pd.to_datetime([f'{year-1}-12-01', f'{year}-04-01', f'{year}-07-01',
                            f'{year}-10-01', f'{year+1}-01-01', f'{year+1}-04-01'])
    obs = observed.loc[dates[0]:dates[-1] - pd.offsets.MonthBegin(1)].dropna()
    if year == 2026:
        boundary = obs.index[-1] + pd.Timedelta(days=15)
        ax.axvspan(boundary, dates[-1], color='.95', zorder=0)
        ax.axvline(boundary, color='.65', lw=.65, ls=':')
        ax.text(.98, .95, 'Unverified seasons', transform=ax.transAxes,
                ha='right', va='top', color='.45', fontsize=8.5 if compact else 9.5)
    ax.plot(obs.index, obs.values, color='#171717', lw=2.5, zorder=6)
    for month, g in iri[iri.year.eq(year) & iri.iri_model.eq(model)].groupby('issue_month'):
        g = g.sort_values('center')
        anchor_date, anchor_value = observed_reference(observed, year, month)
        assert g.center.iloc[0] == pd.Timestamp(year, month, 1) + pd.DateOffset(months=1)
        # This dashed guide is never included in forecast values or skill scores.
        ax.plot([anchor_date, g.center.iloc[0]], [anchor_value, g.IRI.iloc[0]],
                '--', color=COLORS[month], lw=1.15, alpha=.85, zorder=3)
        ax.plot(g.center, g.IRI, '-o', color=COLORS[month], lw=1.65, ms=2.8, zorder=4)
        ax.scatter(anchor_date, anchor_value, s=31, facecolors='white',
                   edgecolors=COLORS[month], linewidths=1.1, zorder=7)
    ax.axhline(0, color='.3', lw=.8)
    for level in [-.5, .5]: ax.axhline(level, color='.4', ls='--', lw=.7)
    ax.axvline(dates[-2], color='#DC7D69', ls='--', lw=.9, alpha=.8)
    ax.set(xlim=(dates[0] - pd.Timedelta(days=10), dates[-1]), ylim=ylim,
           ylabel='Seasonal Niño3.4 SSTA (°C)')
    ax.set_xticks(dates, [f'Dec\n{year-1}', f'Apr\n{year}', 'Jul', 'Oct', f'Jan\n{year+1}', 'Apr'])
    ax.yaxis.set_major_locator(MultipleLocator(.5 if not compact else 1))


def caption(year, nasa=False):
    text = ('Open circles: latest observed season ending before the issue month. Dashed links are visual guides, not model forecasts.\n'
            'Example: February issue uses NDJ (Dec center) as its reference; the first forecast is FMA (Mar center). IRI values are unchanged.\n'
            'Three-month means at their central month. Observed: ERSSTv5 (1991–2020); IRI retains provider anomaly baselines.\n')
    text += ('Observed through JAS 2026 (Jul–Sep); shaded seasons are unverified. Source: official IRI vector plumes (CC BY 4.0).'
             if year == 2026 else 'The reference observation is not the model initial state. Source: official IRI vector plumes (CC BY 4.0).')
    if year == 2026 and nasa:
        text += '\nNASA archive labels: GMAO in Feb–Apr; GMAOv3 in May–Jun 2026.'
    return text


def save(fig, stem):
    for ext in ['png', 'svg', 'pdf']:
        fig.savefig(OUT / f'{stem}.{ext}', dpi=250, bbox_inches='tight')
        if stem.startswith('IRI_only_four_models_'):
            shutil.copyfile(OUT / f'{stem}.{ext}', OUT / f'{stem}_obs_reference.{ext}')


def main():
    style()
    input_names = ['iri_values_from_official_vector_plumes.csv', 'observations.csv',
                   'seasonal_skill_common_pairs.csv', 'common_seasonal_forecasts.csv']
    before = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in input_names}
    iri = pd.read_csv(OUT / 'iri_values_from_official_vector_plumes.csv', parse_dates=['init', 'center'])
    obs = pd.read_csv(OUT / 'observations.csv', index_col=0, parse_dates=True).seasonal_1991_2020
    shown = pd.concat([obs.loc[f'{y-1}-12-01':f'{y+1}-03-01'] for y in [2015, 2026]]).dropna()
    values = np.r_[iri.IRI, shown]
    ylim = (.5 * np.floor((values.min() - .15) / .5), .5 * np.ceil((values.max() + .2) / .5))
    index = []
    with PdfPages(OUT / 'IRI_vs_observed_all_8_figures.pdf') as book:
        for year in [2015, 2026]:
            for model in MODELS:
                fig, ax = plt.subplots(figsize=(12, 5.6))
                fig.subplots_adjust(left=.075, right=.975, top=.775, bottom=.27)
                panel(ax, iri, obs, year, model, ylim)
                ax.legend(handles=legend(), loc='upper left', ncol=3, frameon=False, fontsize=9.5)
                fig.suptitle(f'{year} El Niño: {LABELS[model]} Forecasts and Observations',
                             fontsize=16, fontweight='bold', y=.97)
                fig.text(.5, .90, 'IRI dynamical plume | February–June issues | Three-month mean Niño3.4 SSTA',
                         ha='center', color='#9B4335', fontsize=10.5)
                fig.text(.075, .03, caption(year, model == 'NASA GMAO'), fontsize=8.5, linespacing=1.5)
                stem = f'IRI_only_{model.replace(" ", "_")}_{year}'
                save(fig, stem); book.savefig(fig, bbox_inches='tight'); plt.close(fig)
                index.append(dict(year=year, model=model, stem=stem))
    shutil.copyfile(OUT / 'IRI_vs_observed_all_8_figures.pdf',
                    OUT / 'IRI_vs_observed_all_8_figures_obs_reference.pdf')
    for year in [2015, 2026]:
        fig, axes = plt.subplots(2, 2, figsize=(12.8, 9.7))
        fig.subplots_adjust(left=.07, right=.975, top=.81, bottom=.155, hspace=.38, wspace=.22)
        for i, (ax, model) in enumerate(zip(axes.flat, MODELS)):
            panel(ax, iri, obs, year, model, ylim, compact=True)
            ax.set_title(f'({chr(97+i)})  {LABELS[model]}', pad=10)
            if i % 2: ax.set_ylabel('')
        fig.suptitle(f'{year} El Niño: IRI Dynamical Forecasts and Observations',
                     fontsize=17, fontweight='bold', y=.97)
        fig.text(.5, .925, 'February–June issues | Three-month mean Niño3.4 SSTA',
                 ha='center', color='#9B4335', fontsize=11)
        fig.legend(handles=legend(), loc='upper center', bbox_to_anchor=(.5, .90),
                   ncol=6, frameon=False, fontsize=9.5)
        fig.text(.07, .018, caption(year, nasa=True), fontsize=8.5, linespacing=1.5)
        stem = f'IRI_only_four_models_{year}'
        save(fig, stem); plt.close(fig)
        index.append(dict(year=year, model='four-panel overview', stem=stem))
    (OUT / 'IRI_only_figure_index.json').write_text(json.dumps(index, indent=2))
    anchors = []
    for year in [2015, 2026]:
        for month in range(2, 7):
            center, value = observed_reference(obs, year, month)
            anchors.append(dict(year=year, issue_month=month, observed_center=str(center.date()),
                                observed_season_end=str((center + pd.DateOffset(months=1)).date()),
                                value=value, error_vs_obs=float(value - obs.loc[center])))
    for name, digest in before.items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest
    (OUT / 'IRI_observed_reference_QA.json').write_text(json.dumps(
        dict(anchors=anchors, input_sha256=before, plotted_reference_is_model_initial_state=False,
             connectors_used_in_scores=False, forecast_values_shifted=False), indent=2))
    print('IRI-only figures complete:', OUT)


if __name__ == '__main__':
    main()
