#!/usr/bin/env python3
"""Past-only, monthly RO / RO+PMM pilot; never assimilate future PMM.

This is a new empirical seasonally varying *linear* recharge oscillator,
not the project's diagnostic DGRO surfaces or the published nonlinear XRO.
The original joint SST/wind EOF PMM-like definition is re-estimated per fold.
No model selection is performed on the highlighted events.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/ro_pmm_forecast_2015_2026'
CACHE = OUT / 'cache'
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp/ro_pmm_mpl'))
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
sys.path.insert(0, str(ROOT / 'scripts'))

import numpy as np
import pandas as pd
import xarray as xr
from scipy.linalg import eigh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import plot_pmm_index_eof as pmm_source

ALPHA = 1.0  # sum squared standardized tendency error + alpha * ||B||^2
LEADS = 12
FIRST_FOLD, LAST_FOLD = 2000, 2026
CONFIG = 'v2_trainonly_joint_eof_seasonal_ridge1'
DATA_FINGERPRINT = None
COLORS = {'Observed': '#242830', 'RO': '#2878B5', 'RO+PMM': '#D55E00'}
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def load_data():
    global DATA_FINGERPRINT
    pmm_source.open_netcdf = lambda p: xr.open_dataset(p, engine='netcdf4')
    sst = pmm_source.load_sst().load()
    wind = pmm_source.load_wind(sst.lat, sst.lon).load()
    dates = pd.DatetimeIndex(sst.time.values)
    assert np.array_equal(wind.time.values, sst.time.values)
    assert dates.equals(pd.date_range(dates[0], dates[-1], freq='MS'))
    assert sst.attrs.get('units') in ('degC', 'degree_C', 'degrees C', 'C', 'degree_Celsius')
    assert wind.u10.attrs.get('units') in ('m s**-1', 'm/s', 'm s-1')
    lat, lon = sst.lat.values, sst.lon.values
    arrays = [a.transpose('time', 'lat', 'lon').values.astype(float)
              for a in (sst, wind.u10, wind.v10)]
    flat = [a.reshape(len(dates), -1) for a in arrays]
    weights = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], arrays[0].shape[1:]).ravel()
    n34mask = ((lat[:, None] >= -5) & (lat[:, None] <= 5)
               & (lon[None, :] >= 190) & (lon[None, :] <= 240)).ravel()
    nemask = ((lat[:, None] >= 10) & (lat[:, None] <= 25)
              & (lon[None, :] >= 200) & (lon[None, :] <= 250)).ravel()
    boxmask = ((lat[:, None] >= 15) & (lat[:, None] <= 25)
               & (lon[None, :] >= 210) & (lon[None, :] <= 240)).ravel()
    rows = []
    wwvpath = ROOT / 'data/raw/godas/authoritative_recharge_sections/pmel_tao_wwv.dat'
    for line in wwvpath.read_text().splitlines():
        cols = line.split()
        if len(cols) == 3 and len(cols[0]) == 6 and cols[0].isdigit():
            rows.append((pd.to_datetime(cols[0], format='%Y%m'), float(cols[1]) / 1e14,
                         float(cols[2]) / 1e14))
    wwv = pd.DataFrame(rows, columns=['time', 'total', 'official_anomaly']).set_index('time')
    assert wwv.index.is_unique and wwv.total.between(15, 40).all()
    h = wwv.total.reindex(dates).to_numpy()
    assert np.isfinite(h).all()
    t_raw = area_mean(flat[0], weights, n34mask)
    p_box_raw = area_mean(flat[0], weights, boxmask)
    pd.DataFrame({'time': dates, 'nino34_raw_c': t_raw, 'wwv_total_1e14m3': h,
                  'npmm_box_raw_c': p_box_raw}).to_csv(OUT / 'raw_monthly_indices.csv', index=False)
    files = sorted(pmm_source.INPUT.glob('oisst_sst_pmm_1deg_*.nc'))
    files += [pmm_source.ERA5_HISTORY, pmm_source.ERA5_CURRENT, wwvpath]
    manifest = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size,
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
    DATA_FINGERPRINT = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    info = {'sst_units': sst.attrs.get('units'), 'wind_units': wind.u10.attrs.get('units'),
            'common_start': str(dates[0].date()), 'common_end': str(dates[-1].date()),
            'wwv_end': str(wwv.index[-1].date()), 'n_months': len(dates), 'files': manifest}
    return dates, flat, weights, n34mask, nemask, boxmask, h, info


def area_mean(field, weights, mask):
    f = field[:, mask]
    w = weights[mask]
    valid = np.isfinite(f)
    return np.nansum(f * w, axis=1) / np.sum(valid * w, axis=1)


def preprocess(array, dates, train):
    """Original monthly climatology then linear trend, both fitted on train."""
    a = np.asarray(array, dtype=float)
    if a.ndim == 1:
        a = a[:, None]
    # Grid selection itself uses only the training period.
    valid = np.isfinite(a[train]).all(axis=0)
    f = a[:, valid]
    climate = np.stack([f[train & (dates.month == m)].mean(axis=0) for m in range(1, 13)])
    anom = f - climate[dates.month - 1]
    t = np.arange(len(dates), dtype=float) / 12
    t -= t[train].mean()
    mean = anom[train].mean(axis=0)
    slope = (t[train, None] * (anom[train] - mean)).sum(axis=0) / np.sum(t[train]**2)
    result = np.full_like(a, np.nan)
    result[:, valid] = anom - mean - t[:, None] * slope
    return result


def build_fold(year, dates, fields, weights, n34mask, nemask, boxmask, h, use_cache=True):
    cache = CACHE / f'{CONFIG}_{year}.npz'
    if use_cache and cache.exists():
        with np.load(cache) as z:
            details = json.loads(str(z['details']))
            if details.get('input_fingerprint') == DATA_FINGERPRINT:
                return z['states'], z['box'], details
    train = dates.year < year
    processed = [preprocess(f, dates, train) for f in fields]
    t = area_mean(processed[0], weights, n34mask)
    hv = preprocess(h, dates, train)[:, 0]
    matrices = []
    residual_sst = None
    for j, field in enumerate(processed):
        valid = np.isfinite(field[train]).all(axis=0)
        f = field[:, valid]
        beta = t[train] @ f[train] / (t[train] @ t[train])
        residual = f - t[:, None] * beta
        if j == 0:
            residual_sst = np.full_like(field, np.nan)
            residual_sst[:, valid] = residual
        scale = residual[train].std()
        matrix = residual * np.sqrt(weights[valid]) / scale
        matrix -= matrix[train].mean(axis=0)
        matrices.append(matrix)
    x = np.concatenate(matrices, axis=1)
    assert np.isfinite(x).all(), 'Missing projected predictors must not be silently imputed'
    xt = x[train]
    # Apple's BLAS may raise a spurious floating-point flag for finite dot
    # products. Verify the result and independent explicit row sums below.
    with np.errstate(invalid='ignore'):
        gram = xt @ xt.T
    assert np.isfinite(gram).all()
    assert np.allclose(np.diag(gram), np.einsum('ij,ij->i', xt, xt), rtol=1e-11)
    for row in [0, len(xt)//2, len(xt)-1]:
        assert np.allclose(gram[row], np.sum(xt * xt[row], axis=1), rtol=1e-9, atol=1e-8)
    # Temporal covariance eigenvectors avoid the costly full spatial SVD.
    eig, vec = eigh(gram, subset_by_index=(len(xt)-2, len(xt)-1), check_finite=False)
    eof = xt.T @ vec[:, -1] / np.sqrt(eig[-1])
    pc = x @ eof
    pc = (pc - pc[train].mean()) / pc[train].std(ddof=1)
    ne = area_mean(residual_sst, np.ones_like(weights), nemask)
    sign = 1 if np.dot(pc[train], ne[train]) >= 0 else -1
    pc *= sign
    box = area_mean(processed[0], weights, boxmask)
    states = np.column_stack([t, hv, pc])
    details = {'year': year, 'training_start': str(dates[train][0].date()),
               'input_fingerprint': DATA_FINGERPRINT,
               'training_end': str(dates[train][-1].date()), 'training_months': int(train.sum()),
               'eof_variance_fraction': float(eig[-1] / np.trace(gram)),
               'eof_first_second_eigenvalue_ratio': float(eig[-1] / eig[-2]),
               'pmm_train_correlation_nino34': float(np.corrcoef(pc[train], t[train])[0, 1]),
               'positive_ne_pacific_sign': sign}
    assert abs(details['pmm_train_correlation_nino34']) < 1e-7
    if use_cache:
        np.savez_compressed(cache, states=states, box=box, details=json.dumps(details))
    return states, box, details


def features(z, month, seasonal=True):
    z = np.atleast_2d(z)
    if not seasonal:
        return z
    phase = 2 * np.pi * (np.atleast_1d(month) - 1) / 12
    return np.concatenate([z, z * np.sin(phase[:, None]), z * np.cos(phase[:, None])], axis=1)


def fit_model(states, dates, train, alpha=ALPHA, seasonal=True):
    sd = states[train].std(axis=0, ddof=1)
    z = states / sd
    pair = train[:-1] & train[1:]
    x = features(z[:-1][pair], dates.month[:-1][pair], seasonal)
    delta = (z[1:] - z[:-1])[pair]
    b = np.linalg.solve(x.T @ x + alpha * np.eye(x.shape[1]), x.T @ delta)
    # Check annual-mean recharge/discharge signs rather than impose skill.
    d = states.shape[1]
    annual = np.eye(d)
    for m in range(1, 13):
        transition = np.eye(d) + features(np.eye(d), np.repeat(m, d), seasonal) @ b
        annual = annual @ transition
    diag = {'scale': sd.tolist(), 'tendency_coefficients': b.tolist(),
            'mean_H_to_T': float(b[1, 0]), 'mean_T_to_H': float(b[0, 1]),
            'mean_H_self_tendency': float(b[1, 1]),
            'annual_transition_spectral_radius': float(max(abs(np.linalg.eigvals(annual)))),
            'alpha': alpha, 'seasonal': seasonal, 'n_training_transitions': int(pair.sum())}
    return (sd, b, seasonal), diag


def integrate(model, initial, month, leads=LEADS):
    sd, b, seasonal = model
    z = initial / sd
    out = [z * sd]
    for lead in range(leads):
        m = (month - 1 + lead) % 12 + 1
        z = z + (features(z, m, seasonal) @ b)[0]
        out.append(z * sd)
    return np.asarray(out)


def metrics(frame):
    rows = []
    historical = frame[(frame.init_year.between(2000, 2024)) & (frame.lead > 0)]
    for (model, lead), group in historical.groupby(['model', 'lead']):
        for var in ['T', 'H']:
            g = group.dropna(subset=[f'obs_{var}'])
            y, p = g[f'obs_{var}'].to_numpy(), g[f'pred_{var}'].to_numpy()
            rows.append({'model': model, 'lead': lead, 'variable': var, 'n': len(g),
                         'rmse': np.sqrt(np.mean((p-y)**2)),
                         'mae': np.mean(abs(p-y)),
                         'correlation': np.corrcoef(y, p)[0, 1] if np.std(p) > 1e-12 else np.nan})
    skill = pd.DataFrame(rows)
    skill.to_csv(OUT / 'historical_skill_2000_2024_initializations.csv', index=False)
    eventrows = []
    for year in [2015, 2026]:
        for m in [1, 3, 5]:
            for window, maxlead in [('lead1_4', 4), ('lead1_6', 6), ('lead1_12', 12)]:
                for model in frame.model.unique():
                    g = frame[(frame.init_year == year) & (frame.init_month == m)
                              & (frame.model == model) & frame.lead.between(1, maxlead)]
                    for var in ['T', 'H']:
                        a = g.dropna(subset=[f'obs_{var}'])
                        if a.empty:
                            continue
                        err = a[f'pred_{var}'] - a[f'obs_{var}']
                        eventrows.append({'year': year, 'init_month': m, 'window': window,
                                          'model': model, 'variable': var, 'n_verified_months': len(a),
                                          'complete_window': len(a) == maxlead,
                                          'last_verified_target': a.target.max(),
                                          'rmse': np.sqrt(np.mean(err**2)), 'mae': np.mean(abs(err)),
                                          'bias': err.mean()})
    event = pd.DataFrame(eventrows)
    event.to_csv(OUT / 'event_skill.csv', index=False)
    # Paired error reduction, preserving a clear distinction between available
    # 2026 months and the full 12-month evaluation for 2015.
    keys = ['year', 'init_month', 'window', 'variable', 'n_verified_months',
            'complete_window', 'last_verified_target']
    pivot = event.pivot(index=keys, columns='model', values='rmse').reset_index()
    pivot['pmm_rmse_reduction_percent'] = 100*(1-pivot['RO+PMM']/pivot['RO'])
    pivot['box_rmse_reduction_percent'] = 100*(1-pivot['RO+NPMMbox']/pivot['RO'])
    pivot.to_csv(OUT / 'event_rmse_reduction.csv', index=False)
    # Standardized joint-state distance evaluates the phase-space trajectory.
    joint = []
    for year in [2015, 2026]:
        for m in [1, 3, 5]:
            for model in frame.model.unique():
                g = frame[(frame.init_year == year) & (frame.init_month == m)
                          & (frame.model == model) & (frame.lead > 0)].dropna(subset=['obs_T', 'obs_H'])
                if len(g):
                    mse = (((g.pred_T-g.obs_T)/g.train_sd_T)**2
                           + ((g.pred_H-g.obs_H)/g.train_sd_H)**2).mean()
                    joint.append({'year': year, 'init_month': m, 'model': model,
                                  'n_verified_months': len(g), 'phase_space_rmse_sd': np.sqrt(mse)})
    pd.DataFrame(joint).to_csv(OUT / 'event_phase_space_skill.csv', index=False)
    # Contiguous 3-year block bootstrap of paired hindcast errors; samples are
    # not treated as independent monthly forecasts. Descriptive intervals.
    rng = np.random.default_rng(20261014)
    bootrows = []
    for var in ['T', 'H']:
        for lead in [1, 3, 6, 9, 12]:
            g = historical[(historical.lead == lead) & historical.model.isin(['RO', 'RO+PMM'])].copy()
            g['sq_error'] = (g[f'pred_{var}'] - g[f'obs_{var}'])**2
            means = g.groupby(['init_year', 'model']).sq_error.mean().unstack()
            vals = means[['RO', 'RO+PMM']].to_numpy()
            n = len(vals)
            samples = []
            for _ in range(4000):
                starts = rng.integers(0, n, size=int(np.ceil(n/3)))
                idx = ((starts[:, None] + np.arange(3)) % n).ravel()[:n]
                mse = vals[idx].mean(axis=0)
                samples.append(100*(1-np.sqrt(mse[1]/mse[0])))
            mse = vals.mean(axis=0)
            lo, hi = np.percentile(samples, [2.5, 97.5])
            bootrows.append({'variable': var, 'lead': lead, 'n_init_years': n,
                             'rmse_reduction_percent': 100*(1-np.sqrt(mse[1]/mse[0])),
                             'ci95_low_percent': lo, 'ci95_high_percent': hi,
                             'block_length_years': 3})
    pd.DataFrame(bootrows).to_csv(OUT / 'historical_paired_block_bootstrap.csv', index=False)
    return skill, pivot


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 11, 'axes.labelsize': 10,
                         'xtick.labelsize': 9, 'ytick.labelsize': 9,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.dpi': 220, 'pdf.fonttype': 42})


def save(fig, name):
    for ext in ['png', 'pdf']:
        fig.savefig(OUT / f'{name}.{ext}', bbox_inches='tight', facecolor='white')
    plt.close(fig)


def legend(fig, names=('Observed', 'RO', 'RO+PMM')):
    handles = [Line2D([0], [0], color=c, lw=2.3, label=n,
                      linestyle='-' if n == 'Observed' else '--' if n == 'RO' else '-')
               for n, c in COLORS.items() if n in names]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, .925),
               ncol=3, frameon=False)


def plot_events(frame):
    style()
    main = frame[frame.model.isin(['RO', 'RO+PMM'])]
    # Fixed axes across years AND initialization dates.
    focus = main[main.init_year.isin([2015, 2026]) & main.init_month.isin([1, 3, 5])]
    limits = {}
    for v in ['T', 'H']:
        vals = np.r_[focus[f'pred_{v}'], focus[f'obs_{v}'].dropna()]
        lo, hi = np.nanmin(vals), np.nanmax(vals)
        pad = .13*(hi-lo)
        limits[v] = (min(lo-pad, -.2), hi+pad)
    for month in [1, 3, 5]:
        fig, axes = plt.subplots(2, 2, figsize=(12, 8.0), sharex='col', sharey='row')
        fig.subplots_adjust(top=.81, bottom=.23, hspace=.31, wspace=.14)
        fig.suptitle(f'RO vs RO + PMM | {MONTHS[month-1]} initialization', y=.982, fontsize=17)
        legend(fig)
        for col, year in enumerate([2015, 2026]):
            g = main[(main.init_year == year) & (main.init_month == month)]
            base = g[g.model == 'RO'].sort_values('lead')
            for row, var in enumerate(['T', 'H']):
                ax = axes[row, col]
                if year == 2026:
                    last = base.loc[base[f'obs_{var}'].notna(), 'lead'].max()
                    ax.axvspan(last+.18, LEADS+.2, facecolor='#edf0f3', zorder=-2)
                    if row == 0:
                        ax.text((max(last, 0)+LEADS)/2, .96, 'No local observations',
                                transform=ax.get_xaxis_transform(), ha='center', va='top',
                                color='#626a73', fontsize=8.5)
                ax.plot(base.lead, base[f'obs_{var}'], color=COLORS['Observed'],
                        lw=2.3, marker='o', ms=3.6, zorder=4)
                for model in ['RO', 'RO+PMM']:
                    p = g[g.model == model].sort_values('lead')
                    ax.plot(p.lead, p[f'pred_{var}'], color=COLORS[model], lw=2.2,
                            ls='--' if model == 'RO' else '-', zorder=3)
                ax.scatter([0], [base[f'obs_{var}'].iloc[0]], marker='*', s=105,
                           color='#242830', zorder=6)
                ax.axhline(0, color='.5', lw=.65, zorder=-1)
                ax.grid(axis='y', alpha=.17)
                ax.set(xlim=(-.2, LEADS+.2), ylim=limits[var])
                ax.set_title(f'{chr(97+row*2+col)}) {year} — '+('Niño3.4' if var == 'T' else 'WWV'), loc='left')
                ax.set_xticks(range(0, 13, 2), [MONTHS[(month-1+l)%12]+("\n+1 yr" if month-1+l >= 12 else '')
                                              for l in range(0, 13, 2)])
                if col == 0:
                    ax.set_ylabel('Niño3.4 anomaly (°C)' if var == 'T' else r'WWV anomaly ($10^{14}$ m$^3$)')
                if row == 1:
                    ax.set_xlabel('Target month')
        fig.text(.06, .025, 'Past-only training: 1982–2014 for 2015; 1982–2025 for 2026. Anomalies and trends fitted within each training window.\n'
                 '2026 SST/PMM observed through May; WWV through July. Forecast states evolve freely after initialization.\n'
                 'PMM = project joint SST–wind EOF, re-fitted before each event (not the official MCA index). Linear seasonal RO pilot.\n'
                 'Star: monthly-mean initial state, available after the labeled month. All forecasts have a 12-month horizon.',
                 fontsize=8.6, color='#4e5660', va='bottom', linespacing=1.6)
        save(fig, f'time_series_init_{month:02d}')

        fig, axes = plt.subplots(1, 2, figsize=(12, 6.4), sharex=True, sharey=True)
        fig.subplots_adjust(top=.79, bottom=.27, wspace=.14)
        fig.suptitle(f'Forecast phase space | {MONTHS[month-1]} initialization', y=.98, fontsize=17)
        legend(fig)
        for ax, year in zip(axes, [2015, 2026]):
            g = main[(main.init_year == year) & (main.init_month == month)]
            base = g[g.model == 'RO'].sort_values('lead')
            for label in ['RO', 'RO+PMM', 'Observed']:
                d = base if label == 'Observed' else g[g.model == label].sort_values('lead')
                prefix = 'obs' if label == 'Observed' else 'pred'
                d = d.dropna(subset=[f'{prefix}_T', f'{prefix}_H'])
                x, y = d[f'{prefix}_T'].to_numpy(), d[f'{prefix}_H'].to_numpy()
                leads = d.lead.to_numpy()
                ax.plot(x, y, color=COLORS[label], lw=2.1,
                        ls='--' if label == 'RO' else '-', marker='o', ms=3.5,
                        zorder=5 if label == 'Observed' else 3)
                for k in range(1, len(d)):
                    if leads[k] % 3 == 0 or k == len(d)-1:
                        ax.annotate('', xy=(x[k], y[k]), xytext=(x[k-1], y[k-1]),
                                    arrowprops={'arrowstyle': '->', 'color': COLORS[label], 'lw': 1.4})
                        if label == 'Observed' or k == len(d)-1:
                            txt = MONTHS[(month-1+leads[k])%12]
                            if month-1+leads[k] >= 12:
                                txt += ' +1'
                            ax.annotate(txt, (x[k], y[k]),
                                        xytext=(-44, 8) if label == 'RO' else (6, 7 if label == 'Observed' else 9),
                                        textcoords='offset points', fontsize=8, color=COLORS[label])
            ax.scatter(base.obs_T.iloc[0], base.obs_H.iloc[0], s=130, marker='*',
                       color='#242830', zorder=9)
            ax.axvline(0, lw=.75, color='.5')
            ax.axhline(0, lw=.75, color='.5')
            ax.grid(alpha=.14)
            ax.set(xlim=limits['T'], ylim=limits['H'], xlabel='Niño3.4 anomaly (°C)')
            ax.set_title(f'{year} | observed through '+('May 2026' if year == 2026 else f'{MONTHS[month-1]} 2016'), loc='left')
        axes[0].set_ylabel(r'WWV anomaly ($10^{14}$ m$^3$)')
        fig.text(.065, .028, 'Star: shared initial Niño3.4–WWV state. Arrows: time direction. Monthly points; forecasts extend 12 months.\n'
                 '2026 observed phase trajectory ends in May because paired SST is unavailable afterwards.\n'
                 'Fold-specific past-only climatology/trend; physical units retained. RO+PMM predicts future PMM internally.',
                 fontsize=9, color='#4e5660', linespacing=1.7, va='bottom')
        save(fig, f'phase_space_init_{month:02d}')


def plot_skill(skill):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    fig.subplots_adjust(top=.77, bottom=.21, wspace=.3)
    fig.suptitle('Historical forecast errors | 2000–2024 monthly initializations', fontsize=15)
    legend(fig, names=('RO', 'RO+PMM'))
    for ax, var in zip(axes, ['T', 'H']):
        for model in ['RO', 'RO+PMM']:
            g = skill[(skill.model == model) & (skill.variable == var)].sort_values('lead')
            ax.plot(g.lead, g.rmse, color=COLORS[model], ls='--' if model == 'RO' else '-', lw=2.3)
        ax.set(xlabel='Lead time (months)', ylabel='RMSE (°C)' if var == 'T' else r'RMSE ($10^{14}$ m$^3$)',
               title='Niño3.4' if var == 'T' else 'WWV', xticks=[1,3,6,9,12], xlim=(1,12))
        ax.grid(alpha=.2)
    fig.text(.07, .065, 'Annual expanding-window fits; preprocessing/EOF learned before each initialization year. 300 forecasts per lead.\n'
             'No future observations are assimilated. Same seasonal structure and ridge penalty in both models.', fontsize=9, color='#4e5660')
    save(fig, 'historical_skill')


def write_notes(event):
    lines = [
        'RO 与 RO+PMM：2015 / 2026 初步预报对照（2026-10-14）',
        '',
        '这是重新建立的季节性线性经验 RO 及三变量扩展，不是已有双门诊断模型的预报结果，也不是非线性 XRO 复现。',
        '主图：time_series_init_01/03/05 和 phase_space_init_01/03/05，均有 PNG、矢量 PDF。',
        '',
        '模型：',
        '令 T=Niño3.4，H=WWV 异常，P=项目的 SST–风联合 EOF PMM-like 指数。',
        '每个变量按训练期标准差缩放为 z；离散月倾向 Δz = B0*z + Bs*z*sin(2π(m−1)/12) + Bc*z*cos(2π(m−1)/12)。',
        'RO 的状态为 (T,H)，RO+PMM 为 (T,H,P)，其三个变量均自由向前积分；未来 PMM 不取实测值。',
        '同样的训练月份、季节基函数和 ridge alpha=1；未用两次事件挑选超参数。全年平均 H→T 为正、T→H 为负。',
        '',
        '输入与预处理：',
        'Niño3.4 为 OISST 的 5S–5N、170W–120W 加权平均，WWV 为 PMEL 的 5S–5N、120E–80W、20℃等温面以上体积。',
        '每个检验年只用 1982 至前一年12月估计月气候态、趋势、标准差、ENSO 线性回归和 PMM EOF。',
        'WWV 从总体积重新计算训练期异常，单位 10^14 m³；不是直接绘制 PMEL 使用另一气候态的官方异常列。',
        '2015 使用 1982–2014 年训练；2026 使用 1982–2025 年训练。两年零点基准不同，但每年观测与两个模型完全一致。',
        '本地 SST/PMM 截至 2026年5月，WWV 截至7月；相空间的成对观测只能到5月。',
        '1/3/5月起报使用相应整月平均，只有该月结束后才可获得；未模拟产品发布时滞和历史数据版本修订，属于历史截断回报试验。',
        '',
        '事件结果（正百分比表示 RMSE 下降，负值表示恶化；不包含起报月）：',
    ]
    selected = event[(event.window == 'lead1_12')].sort_values(['year', 'init_month', 'variable'])
    for r in selected.itertuples():
        unit = '℃' if r.variable == 'T' else '10^14 m³'
        # Column names containing '+' are sanitized by itertuples, so use
        # the table directly for model values below.
        row = selected.loc[r.Index]
        lines.append(f'{r.year}年{r.init_month}月起报，{r.variable}：验证 {r.n_verified_months} 个月至 {r.last_verified_target:%Y-%m}，'
                     f'RO {row["RO"]:.3f} → RO+PMM {row["RO+PMM"]:.3f} {unit}，RMSE 下降 {r.pmm_rmse_reduction_percent:.1f}%。')
    lines += [
        '',
        '解读限制：',
        '2015年1月起报的两模型都严重低估增长，RO+PMM 的 Niño3.4 误差仍高于持续性预报；相对改善不能写成已成功预报强事件。',
        '2015年3/5月起报的全年 WWV 误差反而增大；SST 改善不等价于整个充放电过程均被改进。',
        '2026年1月起报仅有4个月 SST 和6个月 WWV 检验；3月起报仅有2个月 SST；5月起报尚无后续 SST 检验。不能估计2026全年或冬季峰值技巧。',
        '历史检验使用2000–2024年全部月份起报，每个提前期300个样本，观测目标延伸至2025。',
        '提前6个月的 Niño3.4 RMSE 由0.669降至0.612℃（8.5%），WWV由0.836降至0.746×10^14 m³（10.8%）。',
        '三年连续块自助区间记录在 historical_paired_block_bootstrap.csv；12个月 SST 增益区间跨零，不能宣称所有提前期均有稳定增益。',
        '相空间误差先分别除以训练期 T、H 标准差，再计算二维平方距离的均方根，见 event_phase_space_skill.csv。',
        '补充使用 15–25N、150–120W 区域 SST 作为 NPMM 代理，并输出持续性、零异常气候态参考；没有用结果反选 PMM 定义。',
        '',
        '验证：改变所有2015年1月以后的原始输入，1月起报曲线保持不变；零新增耦合的三状态积分器与二状态积分器一致。',
        '2026训练窗重新提取的联合 EOF 与早期存档 PMM 的最大差约1.9e-7，说明沿用了此前指数定义。',
        '完整方程系数、文件哈希、资料截止日和质量检查见 model_coefficients.json、methods_and_validation.json。',
        '',
        '相关原始研究（本脚本不宣称复现其完整模型）：',
        'Zhao et al. 2024, Explainable El Niño predictability from climate mode interactions: https://www.nature.com/articles/s41586-024-07534-6',
        'XRO 原始代码归档: https://zenodo.org/records/10681114',
        'Lin et al. 2025, NPMM/2015/2023研究: https://www.nature.com/articles/s41612-025-01013-z',
    ]
    (OUT / 'experiment_notes_cn.txt').write_text('\n'.join(lines)+'\n')


def main():
    started = time.time()
    print('Loading OISST, ERA5 and raw PMEL WWV', flush=True)
    dates, fields, weights, nmask, nemask, bmask, h, info = load_data()
    predictions, coefficients, folds, checks = [], {}, [], {}
    # WWV can be verified beyond the last available SST/PMM month.
    wwv = pd.read_csv(ROOT / 'data/raw/godas/authoritative_recharge_sections/pmel_tao_wwv.dat',
                      sep=r'\s+', skiprows=6, names=['date', 'total', 'official_anomaly'])
    hdates = pd.DatetimeIndex(pd.to_datetime(wwv.date.astype(str), format='%Y%m'))
    hseries = pd.Series(wwv.total.to_numpy()/1e14, index=hdates)
    for year in range(FIRST_FOLD, LAST_FOLD+1):
        before = time.time()
        states, box, detail = build_fold(year, dates, fields, weights, nmask, nemask, bmask, h)
        folds.append(detail)
        train = dates.year < year
        # Same training-only WWV transformation, extended to every available H.
        hfull_dates = pd.date_range(dates[0], hdates[-1], freq='MS')
        hfull = preprocess(hseries.reindex(hfull_dates).to_numpy(), hfull_dates, hfull_dates.year < year)[:, 0]
        assert np.allclose(hfull[:len(dates)], states[:, 1], atol=1e-10)
        if year in [2015, 2026]:
            pd.DataFrame({'time': dates, 'T': states[:, 0], 'H': states[:, 1],
                          'PMM_joint': states[:, 2], 'NPMM_box': box,
                          'is_training': train}).to_csv(OUT / f'processed_indices_training_before_{year}.csv', index=False)
        configs = {'RO': states[:, :2], 'RO+PMM': states,
                   'RO+NPMMbox': np.column_stack([states[:, :2], box])}
        for name, data in configs.items():
            model, diagnostic = fit_model(data, dates, train)
            coefficients[f'{year}_{name}'] = diagnostic
            for i in np.flatnonzero(dates.year == year):
                initial = dates[i]
                forecast = integrate(model, data[i], initial.month)
                assert np.allclose(forecast[0], data[i])
                for lead in range(LEADS+1):
                    j = i+lead
                    predictions.append({'init': initial, 'init_year': year, 'init_month': initial.month,
                                        'target': initial+pd.DateOffset(months=lead), 'lead': lead,
                                        'model': name, 'pred_T': forecast[lead, 0], 'pred_H': forecast[lead, 1],
                                        'pred_P': forecast[lead, 2] if forecast.shape[1] == 3 else np.nan,
                                        'obs_T': states[j, 0] if j < len(dates) else np.nan,
                                        'obs_H': hfull[j] if j < len(hfull) else np.nan,
                                        'train_sd_T': model[0][0], 'train_sd_H': model[0][1],
                                        'training_end': dates[train][-1]})
        if year == 2026:
            old = pd.read_csv(pmm_source.INDEX_CSV)
            err = np.max(abs(states[:, 2]-old.pmm_joint_sst_wind.to_numpy()))
            checks['2026_refit_vs_archived_joint_index_max_absolute_error'] = float(err)
            assert err < 1e-4, err
        print(f'Fold {year}: trained through {year-1}; {time.time()-before:.1f}s', flush=True)
    frame = pd.DataFrame(predictions)
    # Zero-anomaly and persistence references reveal whether a relative
    # improvement also beats elementary forecasts.
    base = frame[frame.model == 'RO'].copy()
    initial_by_date = base[base.lead == 0].set_index('init')[['obs_T', 'obs_H']]
    for name in ['Persistence', 'Climatology']:
        reference = base.copy()
        reference['model'] = name
        for var in ['T', 'H']:
            reference[f'pred_{var}'] = (reference.init.map(initial_by_date[f'obs_{var}'])
                                         if name == 'Persistence' else 0.0)
            reference.loc[reference.lead == 0, f'pred_{var}'] = reference.loc[reference.lead == 0, f'obs_{var}']
        frame = pd.concat([frame, reference], ignore_index=True)
    assert (frame.training_end < frame.init).all()
    assert not frame[['pred_T', 'pred_H']].isna().any().any()
    assert frame.loc[frame.lead > 0, 'target'].gt(frame.loc[frame.lead > 0, 'init']).all()
    frame.to_csv(OUT / 'all_monthly_forecasts.csv', index=False)
    pd.DataFrame(folds).to_csv(OUT / 'fold_preprocessing_audit.csv', index=False)
    (OUT / 'model_coefficients.json').write_text(json.dumps(coefficients, indent=2))
    # A genuine leakage check: perturb EVERY post-Jan-2015 observation, then
    # re-fit from raw grids. Training coefficients and the January forecast
    # must remain numerically unchanged, including EOF preprocessing.
    original_states, _, _ = build_fold(2015, dates, fields, weights, nmask, nemask, bmask, h)
    future = dates > pd.Timestamp('2015-01-01')
    changed = [f.copy() for f in fields]
    for f in changed:
        f[future] += 3.0
    changed_h = h.copy()
    changed_h[future] += 5.0
    changed_states, _, _ = build_fold(2015, dates, changed, weights, nmask, nemask, bmask, changed_h, use_cache=False)
    train = dates.year < 2015
    i = int(np.flatnonzero(dates == pd.Timestamp('2015-01-01'))[0])
    old_model, _ = fit_model(original_states, dates, train)
    new_model, _ = fit_model(changed_states, dates, train)
    old_fc = integrate(old_model, original_states[i], 1)
    new_fc = integrate(new_model, changed_states[i], 1)
    checks['future_perturbation_jan2015_forecast_max_difference'] = float(np.max(abs(old_fc-new_fc)))
    assert np.allclose(old_fc, new_fc, atol=1e-10)
    # Three-state integrator must reduce exactly to the same two-state model
    # when all added couplings are zero.
    two, _ = fit_model(original_states[:, :2], dates, train)
    full_b = np.zeros((9, 3))
    for block in range(3):
        full_b[block*3:block*3+2, :2] = two[1][block*2:block*2+2]
    reduced = (np.r_[two[0], 1.0], full_b, True)
    fc2 = integrate(two, original_states[i, :2], 1)
    fc3 = integrate(reduced, np.r_[original_states[i, :2], 0.8], 1)[:, :2]
    checks['zero_added_coupling_integrator_difference'] = float(np.max(abs(fc2-fc3)))
    assert np.allclose(fc2, fc3, atol=1e-12)
    checks['all_models_mean_H_to_T_positive'] = all(d['mean_H_to_T'] > 0 for d in coefficients.values())
    checks['all_models_mean_T_to_H_negative'] = all(d['mean_T_to_H'] < 0 for d in coefficients.values())
    checks['max_annual_spectral_radius'] = max(d['annual_transition_spectral_radius'] for d in coefficients.values())
    skill, event = metrics(frame)
    write_notes(event)
    plot_events(frame)
    plot_skill(skill)
    info.update({'configuration': CONFIG, 'ridge_alpha': ALPHA,
                 'forecast_equation': 'z(t+1)=z(t)+[z(t),z(t)*sin(2pi*(m-1)/12),z(t)*cos(2pi*(m-1)/12)] @ B',
                 'variables': {'T': 'OISST Nino3.4, 5S–5N, 170W–120W, cosine-latitude mean',
                               'H': 'PMEL total WWV, above 20C isotherm, 5S–5N,120E–80W; anomalies re-computed',
                               'P': 'joint EOF1 of detrended, Nino3.4-residual SST/u10/v10;20S–30N,120E–80W;project PMM-like definition'},
                 'preprocessing': 'Each fold: 1982 to prior December; monthly climatology, linear trend, ENSO removal, EOF, scaling all train-only',
                 'future_P': 'Freely predicted as third state; no observed future PMM provided',
                 'model_scope': 'Seasonally varying linear empirical RO and 3-state extension; not a reproduction of nonlinear XRO',
                 'initialization': 'Monthly mean for labeled month, available only after that month; publication latency and vintage revisions not simulated',
                 'sensitivity': 'Fixed 15N–25N,150W–120W box SST NPMM proxy; not official MCA',
                 'historical_skill': '300 monthly initializations, 2000–2024, target observations through 2025; no model tuning on 2015/2026',
                 'uncertainty': 'Paired circular moving-block bootstrap, 3 initialization years, 4000 samples; descriptive, no multiplicity correction',
                 'checks': checks, 'runtime_seconds': time.time()-started,
                 'sources': ['https://www.nature.com/articles/s41586-024-07534-6',
                             'https://zenodo.org/records/10681114',
                             'https://www.nature.com/articles/s41612-025-01013-z']})
    (OUT / 'methods_and_validation.json').write_text(json.dumps(info, indent=2, ensure_ascii=False))
    print(json.dumps(checks, indent=2), flush=True)
    print(event[(event.init_month == 1) & (event.window == 'lead1_12')].to_string(index=False), flush=True)
    print(f'Finished in {time.time()-started:.1f}s: {OUT}', flush=True)


if __name__ == '__main__':
    main()
