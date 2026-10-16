"""Saved-data figures for the 2023 extension and the 2015/2023 physical bridge."""
from pathlib import Path
import os
import json
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/IRI_RO_PMM_Maryland_bridge_20261014'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/bridge_mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MultipleLocator
from analyze_2023_forecast_maryland_bridge import MODELS, METHODS
from plot_ro_pmm_2026_manuscript_style import style, arrows, limits, MONTH_COLORS
import plot_iri_observed_2015_2026 as iri_plot

BLACK = '#171717'; CORAL = '#DC7D69'; BLUE = '#397EAA'; GREY = '#969696'
FIGURES = []


def save(fig, stem, book=None):
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(OUT / f'{stem}.{ext}', dpi=240, bbox_inches='tight')
    if book is not None:
        book.savefig(fig, bbox_inches='tight')
    FIGURES.append(stem)
    plt.close(fig)


def load():
    return dict(
        f=pd.read_csv(OUT / 'forecasts_2015_2023.csv', parse_dates=['init', 'target']),
        a=pd.read_csv(OUT / 'processed_states_official_PMM.csv', index_col=0, parse_dates=True),
        ms=pd.read_csv(OUT / 'monthly_event_scores.csv'),
        iri=pd.read_csv(OUT / 'iri_values_2015_2023_2026.csv', parse_dates=['init', 'center']),
        ro=pd.read_csv(OUT / 'RO_PMM_seasonal_full_trajectories.csv', parse_dates=['init', 'center']),
        obs=pd.read_csv(OUT / 'observations.csv', index_col=0, parse_dates=True).seasonal_1991_2020,
        scores=pd.read_csv(OUT / 'seasonal_skill_common_pairs.csv'),
        paired=pd.read_csv(OUT / 'common_seasonal_forecasts.csv', parse_dates=['init', 'center']),
        budgets=pd.read_csv(OUT / 'Maryland_event_bridge.csv').set_index('event_year'),
        ocean=pd.read_csv(OUT / 'Maryland_monthly_bridge.csv', parse_dates=['time']),
        coupling=pd.read_csv(OUT / 'Maryland_atmospheric_coupling.csv', parse_dates=['time']),
        pmm=pd.read_csv(OUT / 'official_PMM.csv', index_col=0, parse_dates=True).SST,
        model=json.loads((OUT / 'frozen_models_and_preprocessing.json').read_text()))


def phase_figure(d):
    q = d['f'][d['f'].year.eq(2023) & d['f'].model.isin(['RO', 'RO_SST'])]
    obs = d['a'].loc['2023-01':'2024-03', ['Nino34', 'WWV']]
    scale = np.asarray(d['model']['fits']['RO']['scale'])
    # One physical normalization across 2015 and 2023; limits enclose both cases.
    both = d['a'].loc['2015-01':'2016-03', ['Nino34', 'WWV']]
    xy_all = np.r_[obs.to_numpy()/scale, both.to_numpy()/scale,
                   d['f'][d['f'].model.isin(['RO', 'RO_SST'])][['T', 'H']].to_numpy()/scale]
    xlim, ylim = limits(xy_all[:, 0]), limits(xy_all[:, 1])
    fig = plt.figure(figsize=(12, 9.6))
    gs = fig.add_gridspec(2, 4, left=.08, right=.975, top=.865, bottom=.19,
                         height_ratios=[1.35, 1], hspace=.49, wspace=.95)
    axes = [fig.add_subplot(gs[0, :2]), fig.add_subplot(gs[0, 2:]),
            fig.add_subplot(gs[1, :3]), fig.add_subplot(gs[1, 3])]
    joint = obs.to_numpy()/scale
    for i, method in enumerate(['RO', 'RO_SST']):
        ax = axes[i]
        ax.plot(*joint.T, '-o', color=BLACK, lw=2.2, ms=3.5)
        arrows(ax, joint, BLACK, [2, 6, 10], 1.4, 10)
        for month, g in q[q.model.eq(method)].groupby('month'):
            xy = g.sort_values('lead')[['T', 'H']].to_numpy()/scale
            ax.plot(*xy.T, '-o', color=MONTH_COLORS[month], lw=1.35, ms=2)
            ax.scatter(*xy[0], s=27, facecolors='white', edgecolors=MONTH_COLORS[month], zorder=7)
            arrows(ax, xy, MONTH_COLORS[month], [3, 7], .9, 8)
        for date, label, offset in [('2023-01-01', 'Jan 2023', (7,8)),
                                    ('2023-09-01', 'Sep', (7,5)),
                                    ('2023-12-01', 'Dec', (7,5)),
                                    ('2024-03-01', 'Mar 2024', (7,-3))]:
            ax.annotate(label, obs.loc[date].values/scale, xytext=offset, textcoords='offset points', fontsize=9)
        ax.axhline(0, ls='--', color='.4', lw=.7); ax.axvline(0, ls='--', color='.4', lw=.7)
        ax.set(xlim=xlim, ylim=ylim, xlabel='Normalized Niño3.4 SSTA', ylabel='Normalized mean D20')
        ax.set_box_aspect(1)
        ax.set_title(f'({chr(97+i)})  SST–D20 Phase Diagram ({"RO" if i == 0 else "RO + PMM"})', pad=10)
        ax.xaxis.set_major_locator(MultipleLocator(1)); ax.yaxis.set_major_locator(MultipleLocator(1))
    axes[0].legend(handles=[Line2D([],[],c=BLACK,lw=2,label='Observed'),
                           Line2D([],[],c=CORAL,lw=1.5,label='Forecasts: Feb–Jun starts')],
                   loc='lower left', fontsize=8, frameon=False)
    ax = axes[2]
    ax.plot(obs.index, obs.Nino34, c=BLACK, lw=2.5, label='Observed')
    for method, color, ls in [('RO', GREY, '--'), ('RO_SST', CORAL, '-')]:
        for j, (_, g) in enumerate(q[q.model.eq(method)].groupby('month')):
            ax.plot(g.target, g['T'], c=color, ls=ls, lw=1.4,
                    label=('RO' if method == 'RO' else 'RO + PMM') if j == 0 else None)
    ax.axhline(0, color='.4', lw=.7); ax.axhline(.5, color='.5', ls='--', lw=.7)
    ax.axvline(pd.Timestamp('2024-01-01'), color=CORAL, ls='--', lw=.8)
    ticks = pd.to_datetime(['2023-01-01','2023-04-01','2023-07-01','2023-10-01','2024-01-01','2024-04-01'])
    ax.set_xticks(ticks, ['Jan\n2023','Apr','Jul','Oct','Jan\n2024','Apr'])
    ax.set(xlim=(ticks[0],ticks[-1]), ylim=(-1,3.5), ylabel='Detrended Niño3.4 SSTA (°C)')
    ax.set_title('(c)  Observed and Predicted Niño3.4 Index', pad=10)
    ax.legend(frameon=False, fontsize=8.5)
    score = d['ms'][d['ms'].year.eq(2023)].set_index('model').loc[['RO','RO_SST']]
    ax = axes[3]
    ax.bar([0,1], score.T_r, width=.55, color=['#EAB5A8', CORAL], edgecolor='.3')
    for i, v in enumerate(score.T_r): ax.text(i,v+.04,f'{v:.2f}',ha='center',fontsize=10)
    ax.axhline(0,c='.4',lw=.7)
    ax.set(xticks=[0,1],xticklabels=['RO','RO +\nPMM'],ylim=(-.9,1.12),ylabel='Correlation coefficient')
    ax.set_title('(d)  Prediction Skill\n(2023)',pad=10)
    ax.text(.04,.045,f'RMSE (°C)\n{score.T_RMSE.iloc[0]:.2f} → {score.T_RMSE.iloc[1]:.2f}',transform=ax.transAxes,fontsize=9)
    fig.suptitle('2023 El Niño: Seasonal RO and Standard PMM', fontsize=17,fontweight='bold',y=.98)
    fig.text(.5,.938,'Fit: 2002–2024 | Retrospective fit includes 2023',ha='center',fontsize=11,color='#9B4335')
    fig.text(.08,.03,'February–June monthly-state initializations; monthly leads 1–9 (45 pairs). Lead 0 is shown but not scored.\n'
             'PMM = official canonical MCA SST index. Every state, including PMM, evolves freely after initialization.\n'
             'Ocean state: GODAS area-mean D20 (m), a WWV proxy; it is not the Maryland 0–300 m heat-content budget.\n'
             f'Shared 2015/2023 scales: σT = {scale[0]:.3f} °C; σh = {scale[1]:.3f} m. Detrended manuscript coordinates.\n'
             'Monthly-state initialization uses a completed month; this is not a historical real-time issue-date experiment.',
             fontsize=8.3, linespacing=1.5)
    save(fig,'figure_2023_RO_vs_standard_PMM')


def iri_figures(d):
    iri, obs = d['iri'], d['obs']
    iri_plot.OUT = OUT
    ylim = (-1.5, 3.5)
    with PdfPages(OUT/'IRI_2023_four_models_and_RO_PMM.pdf') as book:
        for model in MODELS:
            fig, ax = plt.subplots(figsize=(12,5.6))
            fig.subplots_adjust(left=.075,right=.975,top=.775,bottom=.27)
            iri_plot.panel(ax, iri, obs, 2023, model, ylim)
            ax.legend(handles=iri_plot.legend(),loc='upper left',ncol=3,frameon=False,fontsize=9)
            fig.suptitle(f'2023 El Niño: {iri_plot.LABELS[model]} Forecasts and Observations',fontsize=16,fontweight='bold',y=.97)
            fig.text(.5,.90,'IRI dynamical plume | February–June issues | Three-month mean Niño3.4 SSTA',ha='center',fontsize=10.5,color='#9B4335')
            fig.text(.075,.03,iri_plot.caption(2023),fontsize=8.5,linespacing=1.5)
            save(fig,f'IRI_only_{model.replace(" ","_")}_2023',book)
            fig = plt.figure(figsize=(14,6))
            gs = fig.add_gridspec(1,2,left=.065,right=.975,top=.79,bottom=.32,width_ratios=[4.4,1.2],wspace=.27)
            ax = fig.add_subplot(gs[0,0]); sk = fig.add_subplot(gs[0,1])
            dates = pd.to_datetime(['2022-12-01','2023-04-01','2023-07-01','2023-10-01','2024-01-01','2024-04-01'])
            truth = obs.loc[dates[0]:dates[-1]-pd.offsets.MonthBegin(1)]
            ax.plot(truth.index,truth,c=BLACK,lw=2.4,label='Observed')
            for method, color, ls in [('RO',GREY,'--'),('RO_SST',CORAL,'-')]:
                for j,(_,g) in enumerate(d['ro'][d['ro'].year.eq(2023)&d['ro'].method.eq(method)].groupby('issue_month')):
                    ax.plot(g.center,g.value,c=color,ls=ls,lw=1.4,label=('RO' if method=='RO' else 'RO + PMM') if j==0 else None)
            for j,(month,g) in enumerate(iri[iri.year.eq(2023)&iri.iri_model.eq(model)].groupby('issue_month')):
                t,v = iri_plot.observed_reference(obs,2023,month)
                ax.plot([t,g.center.iloc[0]],[v,g.IRI.iloc[0]],'--',c=BLUE,lw=.9,alpha=.6)
                ax.scatter(t,v,s=22,facecolors='white',edgecolors=BLUE,zorder=7)
                ax.plot(g.center,g.IRI,'-o',c=BLUE,lw=1.4,ms=2.5,label=f'IRI: {model}' if j==0 else None)
            ax.axhline(0,c='.4',lw=.7);ax.axhline(.5,c='.5',ls='--',lw=.7)
            ax.axvline(pd.Timestamp('2024-01-01'),c=CORAL,ls='--',lw=.8)
            ax.set(xlim=(dates[0]-pd.Timedelta(days=10),dates[-1]),ylim=ylim,ylabel='Seasonal Niño3.4 SSTA (°C)')
            ax.set_xticks(dates,['Dec\n2022','Apr\n2023','Jul','Oct','Jan\n2024','Apr'])
            ax.set_title('(a)  Observed and Predicted Niño3.4 Index',pad=10)
            ax.legend(frameon=False,fontsize=8.5,loc='upper left')
            score=d['scores'][d['scores'].year.eq(2023)].set_index('model').loc[['RO','RO_SST',model]]
            sk.bar(range(3),score.r,color=[GREY,CORAL,BLUE],width=.56,edgecolor='.3')
            for i,v in enumerate(score.r):sk.text(i,v+.035,f'{v:.2f}',ha='center',fontsize=10)
            sk.axhline(0,c='.4',lw=.7)
            sk.set(ylim=(-.78,1.13),xticks=[0,1,2],xticklabels=['RO','RO +\nPMM',model.replace(' ','\n')],ylabel='Correlation coefficient')
            sk.set_title('(b)  Prediction Skill\n(2023; n = 25)',pad=10)
            sk.text(.04,.22,'RMSE (°C)',transform=sk.transAxes,fontsize=9)
            for i,v in enumerate(score.RMSE):sk.text(i,-.49,f'{v:.2f}',ha='center',fontsize=10)
            fig.suptitle(f'2023 El Niño: RO, RO + PMM and {model}',fontsize=17,fontweight='bold',y=.97)
            fig.text(.5,.906,'Fit: 2002–2024 | Retrospective fit includes 2023',ha='center',fontsize=11,color='#9B4335')
            fig.text(.065,.028,'Three-month means at their central month; February–June issues / monthly-state initializations.\n'
                     'Skill: the same 25 issue–season pairs across all six methods, center leads 1–5. Longer curves are displayed but not scored.\n'
                     'RO / observations: ERSSTv5 SSTA (1991–2020), with trend restored. IRI retains provider baselines; information dates differ.\n'
                     'IRI open circles are prior observed-season references, not model initial states. Dashed links are guides and are not scored.\n'
                     'Standard PMM-SST; frozen manuscript model. IRI values extracted from official vector plumes (CC BY 4.0).',
                     fontsize=8.3,linespacing=1.5)
            save(fig,f'IRI_{model.replace(" ","_")}_2023_RO_PMM',book)
    fig, axes = plt.subplots(2,2,figsize=(12.8,9.7))
    fig.subplots_adjust(left=.07,right=.975,top=.81,bottom=.155,hspace=.38,wspace=.22)
    for i,(ax,model) in enumerate(zip(axes.flat,MODELS)):
        iri_plot.panel(ax,iri,obs,2023,model,ylim,compact=True)
        ax.set_title(f'({chr(97+i)})  {iri_plot.LABELS[model]}',pad=10)
        if i%2:ax.set_ylabel('')
    fig.suptitle('2023 El Niño: IRI Dynamical Forecasts and Observations',fontsize=17,fontweight='bold',y=.97)
    fig.text(.5,.925,'February–June issues | Three-month mean Niño3.4 SSTA',ha='center',fontsize=11,color='#9B4335')
    fig.legend(handles=iri_plot.legend(),loc='upper center',bbox_to_anchor=(.5,.90),ncol=6,frameon=False,fontsize=9.5)
    fig.text(.07,.018,iri_plot.caption(2023),fontsize=8.5,linespacing=1.5)
    save(fig,'IRI_only_four_models_2023_obs_reference')
    anchors=[]
    for m in range(2,7):
        t,v=iri_plot.observed_reference(obs,2023,m)
        anchors.append(dict(issue_month=m,observed_center=str(t.date()),value=v,error_vs_obs=float(v-obs.loc[t])))
    (OUT/'IRI_2023_observed_reference_QA.json').write_text(json.dumps(dict(
        anchors=anchors,model_initial_state=False,forecast_values_adjusted=False,connectors_scored=False),indent=2))


def bridge_figure(d):
    """Time-ordered juxtaposition, not a fitted causal chain or heat-fate forecast."""
    fig,axes=plt.subplots(5,2,figsize=(14.2,17.2))
    fig.subplots_adjust(left=.075,right=.97,top=.91,bottom=.105,hspace=.67,wspace=.23)
    pmm_mean=float(d['model']['preprocessing']['pmm_mean'][0])
    pmm_scale=float(d['model']['fits']['RO_SST']['scale'][2])
    dates_axis=[1,4,7,10,13,16]
    labels_axis=['Jan','Apr','Jul','Oct','Jan +1','Apr +1']
    pm_colors=[GREY,CORAL]
    for col,year in enumerate([2015,2023]):
        # An April example is fixed identically for both years; all five starts are evaluated elsewhere.
        ax=axes[0,col]
        truth=d['obs'].loc[f'{year}-01':f'{year+1}-03']
        x=(truth.index.year-year)*12+truth.index.month
        ax.plot(x,truth,c=BLACK,lw=2.3,label='Observed')
        for method,color,ls in [('RO',GREY,'--'),('RO_SST',CORAL,'-')]:
            g=d['ro'][d['ro'].year.eq(year)&d['ro'].issue_month.eq(4)&d['ro'].method.eq(method)]
            ax.plot((g.center.dt.year-year)*12+g.center.dt.month,g.value,c=color,ls=ls,lw=1.9,label='RO' if method=='RO' else 'RO + PMM')
        ir=d['iri'][d['iri'].year.eq(year)&d['iri'].issue_month.eq(4)]
        full=ir.pivot(index='center',columns='iri_model',values='IRI').dropna(subset=MODELS)
        xx=(full.index.year-year)*12+full.index.month
        ax.fill_between(xx,full.min(axis=1),full.max(axis=1),color=BLUE,alpha=.18,label='Four IRI models: min–max')
        ax.plot(xx,full.mean(axis=1),c=BLUE,lw=1.4,ls=':',label='Four-model mean')
        ax.set(xlim=(1,16),ylim=(-1,3.4),ylabel='Seasonal Niño3.4 SSTA (°C)')
        ax.set_xticks(dates_axis,labels_axis)
        ax.set_title(f'({chr(97+col)})  {year}: April forecasts',loc='left',pad=9)
        ax.axhline(0,c='.5',lw=.7)
        if col==0:ax.legend(frameon=False,fontsize=8,ncol=2,loc='upper left')
        ax=axes[1,col]
        g=d['paired'][d['paired'].year.eq(year)&d['paired'].issue_month.eq(4)].sort_values('center')
        xx=g.center.dt.month.to_numpy()
        for method,color,ls in [('RO',GREY,'--'),('RO_SST',CORAL,'-')]:
            ax.plot(xx,g[method]-g.observed,ls=ls,marker='o',ms=3,c=color,lw=1.7,label='RO' if method=='RO' else 'RO + PMM')
        errors=g[MODELS].sub(g.observed,axis=0)
        ax.fill_between(xx,errors.min(axis=1),errors.max(axis=1),color=BLUE,alpha=.18,label='IRI min–max')
        ax.axhline(0,c=BLACK,lw=.8)
        ax.set(xlim=(4.7,9.3),ylim=(-1.55,.65),ylabel='Forecast − observed (°C)')
        ax.set_xticks([5,6,7,8,9],['May','Jun','Jul','Aug','Sep'])
        ax.set_title(f'({chr(99+col)})  April errors: common leads 1–5',loc='left',pad=9)
        inc=(g.RO_SST-g.RO).mean()
        ax.text(.04,.08,f'Mean (RO + PMM) − RO: {inc:+.2f} °C',transform=ax.transAxes,fontsize=9,color='#9B4335')
        if col==0:ax.legend(frameon=False,fontsize=8,ncol=3,loc='upper left')
        ax=axes[2,col]
        pp=d['pmm'].loc[str(year)]
        ax.plot(pp.index.month,(pp-pmm_mean)/pmm_scale,c=CORAL,lw=2,marker='o',ms=2.7,label='PMM-SST state')
        c=d['coupling'][d['coupling'].year.eq(year)]
        ax.plot(c.month,c.tau_pattern_residual_z,c=BLUE,lw=1.7,marker='s',ms=2.7,label='SST-adjusted wind-stress residual')
        ax.axhline(0,c='.4',lw=.7)
        ax.axvspan(4.5,7.5,color='.92',zorder=0)
        ax.text(.49,.93,'MJJ',transform=ax.transAxes,ha='center',va='top',fontsize=8,color='.4')
        ax.set(xlim=(1,12),ylim=(-3,4.5),ylabel='Standardized value')
        ax.set_xticks([1,4,7,10,12],['Jan','Apr','Jul','Oct','Dec'])
        ax.set_title(f'({chr(101+col)})  Development: PMM and wind response',loc='left',pad=9)
        if col==0:ax.legend(frameon=False,fontsize=8,loc='upper left')
        ax=axes[3,col]
        g=d['ocean'][d['ocean'].event_year.eq(year)&d['ocean'].year.eq(year)&d['ocean'].month.le(6)]
        for box,color in [('west','#B3996A'),('central',BLUE),('east',CORAL)]:
            ax.plot(g.month,g[f'{box}_ohc300_anom_zj'],'-o',c=color,ms=3,lw=1.7,label=f'{box.capitalize()} OHC′')
        sec=(g.time-g.time.iloc[0]).dt.total_seconds().to_numpy()
        cum=cumulative_trapezoid(g.east_west_theta_heat_in_corr_anom_pw,x=sec,initial=0)/1e6
        ax.plot(g.month,cum,'--',c=BLACK,lw=1.6,label='Cumulative 140°W input')
        ax.axhline(0,c='.5',lw=.7)
        ax.set(xlim=(.85,6.15),ylim=(-4,15),ylabel='OHC′ / cumulative input (ZJ)')
        ax.set_xticks(range(1,7),['Jan','Feb','Mar','Apr','May','Jun'])
        ax.set_title(f'({chr(103+col)})  Arrival and subsurface configuration',loc='left',pad=9)
        ax.text(.97,.08,f'140°W input: {cum[-1]:.2f} ZJ',transform=ax.transAxes,ha='right',fontsize=9)
        if col==0:ax.legend(frameon=False,fontsize=8,ncol=2,loc='upper left')
        ax=axes[4,col]
        row=d['budgets'].loc[year]
        keys=['decay_westward_return_zj','decay_northward_output_zj','decay_southward_output_zj',
              'decay_surface_loss_zj','decay_eastward_export_zj','decay_residual_sink_zj','decay_storage_loss_zj']
        vals=row[keys].to_numpy(dtype=float)
        bars=ax.bar(range(7),vals,color=[BLUE,CORAL,'#B3996A','#EAB5A8','#94BDC6','.7',BLACK],width=.66,edgecolor='.3',lw=.7)
        bars[-2].set_hatch('//')
        for i,v in enumerate(vals):
            ax.text(i,v+(.45 if v>=0 else -.45),f'{v:.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=8.8)
        ax.axhline(0,c='.4',lw=.7)
        ax.set(ylim=(-3,23),ylabel='Signed loss from east box (ZJ)',xticks=range(7),
               xticklabels=['West\nreturn','North','South','Surface','East\nedge','Residual','Storage\nloss'])
        ax.tick_params(axis='x',labelsize=8.5)
        ax.set_title(f'({chr(105+col)})  Heat fate: Jan–May {year+1}',loc='left',pad=9)
    fig.suptitle('From ENSO Forecasts to Heat Fate: 2015 and 2023',fontsize=20,fontweight='bold',y=.982)
    fig.text(.5,.953,'Frozen RO fit: 2002–2024 | Both events are retrospective | Physical diagnostics are not forecast inputs',
             ha='center',fontsize=11,color='#9B4335')
    fig.text(.075,.018,
             '(a–d) April illustrates both events; all Feb–Jun starts are retained in the accompanying figures and scores. IRI range is not a probability interval.\n'
             'Forecasts: ERSSTv5 anomalies (1991–2020), with RO trend restored; IRI provider baselines and information dates are not harmonized.\n'
             '(e–f) PMM: official SST index, standardized on 2002–2024. Wind: ERA5 stress residual conditional on Niño3.4 and Niño3−Niño4; 1982–2014 reference.\n'
             '(g–j) SODA3 0–300 m; 10°S–5°N; west / central / east = 160°E–180° / 180°–140°W / 140°W–80°W. Monthly trends: 1980–2022.\n'
             'Fluxes use mass balance and expected boundary-temperature reference. Integrals join monthly centers (Jan 15–Jun 15; next Jan 15–May 15).\n'
             'Negative loss means anomalous input. Residual closes the budget but does not identify a physical pathway. RO mean D20 is not this heat budget.\n'
             'These panels establish temporal and physical correspondence; they do not demonstrate that PMM caused the event or the subsequent heat partition.',
             fontsize=8.5,linespacing=1.5)
    save(fig,'Maryland_forecast_heat_fate_bridge_2015_2023')


def comparison_overview(d):
    fig,axes=plt.subplots(1,3,figsize=(15,5.3),sharey=True)
    fig.subplots_adjust(left=.06,right=.98,top=.78,bottom=.29,wspace=.22)
    labels=['RO','RO +\nPMM','NCEP','NASA','CMC','JMA']
    for ax,year in zip(axes,[2015,2023,2026]):
        s=d['scores'][d['scores'].year.eq(year)].set_index('model').loc[METHODS]
        ax.bar(range(6),s.RMSE,color=[GREY,CORAL]+[BLUE]*4,edgecolor='.3',lw=.6,width=.67)
        for x,v in enumerate(s.RMSE):ax.text(x,v+.035,f'{v:.2f}',ha='center',fontsize=9)
        ax.set(xticks=range(6),xticklabels=labels,ylim=(0,1.15))
        ax.tick_params(axis='x',labelsize=9)
        ax.set_title(f'{year} | {int(s.n.iloc[0])} common pairs',pad=10)
        delta=100*(s.loc['RO_SST','RMSE']/s.loc['RO','RMSE']-1)
        ax.text(.5,.93,f'PMM changes RO RMSE by {delta:+.1f}%',ha='center',transform=ax.transAxes,fontsize=9,color='#9B4335')
    axes[0].set_ylabel('Seasonal Niño3.4 RMSE (°C)')
    fig.suptitle('PMM Forecast Contribution Differs Across Events',fontsize=18,fontweight='bold',y=.97)
    fig.text(.5,.89,'Same six-method mask within each event | February–June starts | Season-center leads 1–5',ha='center',fontsize=11,color='#9B4335')
    fig.text(.06,.045,'2015 and 2023: official PMM; fit 2002–2024 includes the verification events. 2026: reconstructed PMM; event excluded from fitting.\n'
             '2026 has fewer verified seasons; its sample differs from the historical cases. These are descriptive event scores, not independent sample counts.\n'
             'IRI is an as-published benchmark: provider anomaly baselines, issue dates and model versions differ. Bars do not establish a general skill ranking.',fontsize=9,linespacing=1.5)
    save(fig,'forecast_skill_2015_2023_2026_overview')


def main():
    style();d=load()
    phase_figure(d);iri_figures(d);bridge_figure(d);comparison_overview(d)
    (OUT/'figure_index.json').write_text(json.dumps(FIGURES,indent=2))
    print('Rendered',len(FIGURES),'figures:',OUT)


if __name__=='__main__':main()
