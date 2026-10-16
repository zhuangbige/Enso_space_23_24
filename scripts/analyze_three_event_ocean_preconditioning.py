"""Three-case paper diagnostics; no model fitting or event-specific tuning.

Reuses the audited Chen-2015 density/section geometry routines, but recomputes
all regional budgets for the new common +/-9 degree partition. Historical data
define anomalies and the SST-conditioned wind reference, not extra case studies.
"""
from pathlib import Path
import argparse
import calendar
import gc
import hashlib
import json
import os
import sys
import warnings

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/maryland_three_events_mpl')
import numpy as np
import pandas as pd
import xarray as xr
from scipy.integrate import cumulative_trapezoid
import analyze_chen2015_reanalysis as geometry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/research_2026/three_event_ocean_preconditioning_20261014'
CACHE = OUT / 'cache'
OLD = ROOT / 'outputs/research_2026/chen2015_reanalysis_20261014'
EVENTS = (1997, 2015, 2023)
CASE_YEARS = (1996, 1997, 2014, 2015, 2022, 2023)
BASE = (1982, 2022)
REGIONS = {'west': (120., 180.), 'central': (180., 220.), 'east': (220., 280.)}
# Gates are calculated once; adjacent boxes share exactly the same transport.
GATES = {'u120': ('u', 120., -9., 9.), 'u180': ('u', 180., -9., 9.),
         'u220': ('u', 220., -9., 9.), 'u280': ('u', 280., -9., 9.)}
for region, (lo, hi) in REGIONS.items():
    GATES[f'{region}_south'] = ('v', -9., lo, hi)
    GATES[f'{region}_north'] = ('v', 9., lo, hi)
EDGES = {'west': ('u120', 'u180'), 'central': ('u180', 'u220'), 'east': ('u220', 'u280')}
EXCLUDE_REFERENCE = set(y for e in EVENTS for y in (e-1, e, e+1))
QA = {}


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def normalise(a):
    names = {k: v for k, v in [('latitude', 'lat'), ('longitude', 'lon'), ('valid_time', 'time')] if k in a.coords}
    a = a.rename(names)
    return a.assign_coords(lon=a.lon % 360).sortby('lon').sortby('lat')


def latmean(a, width=5):
    a = a.sel(lat=slice(-width, width))
    return a.weighted(np.cos(np.deg2rad(a.lat))).mean('lat')


def boxmean(a, lo, hi):
    return latmean(a.sel(lon=slice(lo, hi))).mean('lon')


def detrended_anomaly(frame):
    result = frame[['time']].copy()
    years, months = frame.time.dt.year.to_numpy(), frame.time.dt.month.to_numpy()
    for col in frame.columns.drop('time'):
        y = frame[col].to_numpy()
        pred = np.full(len(y), np.nan)
        for m in range(1, 13):
            use = (months == m) & (years >= BASE[0]) & (years <= BASE[1])
            assert use.sum() == 41
            coeff = np.polyfit(years[use] - 2002, y[use], 1)
            pred[months == m] = np.polyval(coeff, years[months == m] - 2002)
        result[col] = y - pred
    return result


def anomalies(frame):
    result = frame.copy()
    b = frame.loc[frame.time.dt.year.between(*BASE)]
    clim = b.groupby(b.time.dt.month).mean(numeric_only=True)
    assert b.groupby(b.time.dt.month).size().eq(41).all()
    for col in frame.columns.drop('time'):
        result[col] = frame[col].to_numpy() - clim.loc[frame.time.dt.month, col].to_numpy()
    return result


def atmosphere():
    target = OUT / 'atmosphere_monthly.nc'
    if target.exists() and (OUT / 'wind_reference_QA.json').exists():
        QA['wind_reference'] = json.loads((OUT / 'wind_reference_QA.json').read_text())
        print('Atmospheric cache ready', flush=True)
        return
    rows, hov_sst, hov_tau, times = [], [], [], []
    for m in range(1, 13):
        tag = calendar.month_abbr[m].lower()
        paths = sorted((ROOT / 'data/interim/research_2026/pmm_inputs').glob(f'oisst_sst_pmm_1deg_{tag}_1982_*.nc'))
        if not paths:
            raise FileNotFoundError(tag)
        with xr.open_dataset(paths[-1], engine='scipy') as ds:
            sst = normalise(ds.sst).sel(time=slice('1982-01-01', '2024-12-31')).load()
        parts = []
        for part in ('part01', 'part02'):
            p = ROOT / f'data/raw/era5/coupling_monthly_1deg/era5_coupling_{part}_m{m:02d}_1982_2025_1p0deg.nc'
            with xr.open_dataset(p, engine='h5netcdf') as ds:
                parts.append(normalise(ds.avg_iews).sel(time=slice('1982-01-01', '2024-12-31')).load())
        tau = xr.concat(parts, dim='lon').sortby('lon')
        _, unique = np.unique(tau.lon, return_index=True)
        tau = tau.isel(lon=np.sort(unique))
        sy, ty = sst.time.dt.year.values, tau.time.dt.year.values
        np.testing.assert_array_equal(sy, np.arange(1982, 2025))
        np.testing.assert_array_equal(sy, ty)
        indices = {'nino34': boxmean(sst, 190, 240).values, 'nino3': boxmean(sst, 210, 270).values,
                   'nino4': boxmean(sst, 160, 210).values, 'tau': boxmean(tau, 160, 220).values,
                   'tau_9deg': tau.sel(lon=slice(160, 220), lat=slice(-9, 9)).weighted(np.cos(np.deg2rad(tau.sel(lat=slice(-9, 9)).lat))).mean(('lat', 'lon')).values}
        for i, y in enumerate(sy):
            rows.append({'time': pd.Timestamp(int(y), m, 15), **{k: float(v[i]) for k, v in indices.items()}})
        bs = sst.isel(time=np.flatnonzero((sy >= BASE[0]) & (sy <= BASE[1]))).mean('time')
        bt = tau.isel(time=np.flatnonzero((sy >= BASE[0]) & (sy <= BASE[1]))).mean('time')
        hs = latmean((sst-bs).sel(lon=slice(120, 280)))
        ht = latmean((tau-bt).sel(lon=slice(120, 280)))
        hov_sst.extend(hs.values)
        hov_tau.extend(ht.values)
        times.extend(pd.Timestamp(int(y), m, 15) for y in sy)
        slon, tlon = hs.lon.values, ht.lon.values
        print('Atmosphere', m, flush=True)
    raw = pd.DataFrame(rows).sort_values('time').reset_index(drop=True)
    anom = anomalies(raw)
    raw.to_csv(OUT / 'atmosphere_absolute.csv', index=False)
    anom['pattern'] = anom.nino3 - anom.nino4
    anom['year'], anom['month'] = anom.time.dt.year, anom.time.dt.month
    reference_rows = []
    rng = np.random.default_rng(199720152023)
    excluded = sorted(EXCLUDE_REFERENCE)
    # Each bootstrap resamples two-calendar-year blocks jointly across months.
    years = [y for y in range(1982, 2025) if y not in EXCLUDE_REFERENCE]
    blocks = [[y, y+1] for y in years if y+1 in years]
    boot_years = []
    for _ in range(500):
        draw = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), size=(len(years)+1)//2)])[:len(years)]
        boot_years.append(draw)
    for response in ('tau', 'tau_9deg'):
        for m in range(1, 13):
            g = anom.loc[anom.month.eq(m)].copy()
            train = g.loc[~g.year.isin(EXCLUDE_REFERENCE)]
            x = np.column_stack([np.ones(len(g)), (g.year-2003)/10, g.nino34, g.pattern])
            use = ~g.year.isin(EXCLUDE_REFERENCE).to_numpy()
            xt, yt = x[use], train[response].to_numpy()
            beta, _, rank, _ = np.linalg.lstsq(xt, yt, rcond=None)
            assert rank == 4 and len(train) == 34
            scale = np.sqrt(np.sum((yt-xt@beta)**2)/(len(yt)-4))
            yhat = x@beta
            mapping = {y: i for i, y in enumerate(train.year)}
            boot = []
            for draw in boot_years:
                ii = np.array([mapping[int(y)] for y in draw])
                b = np.linalg.lstsq(xt[ii], yt[ii], rcond=None)[0]
                boot.append(x@b)
            lo, hi = np.quantile(boot, [.025, .975], axis=0)
            for col, vals in [('expected', yhat), ('residual', g[response].to_numpy()-yhat),
                              ('residual_z', (g[response].to_numpy()-yhat)/scale), ('expected_lo', lo), ('expected_hi', hi)]:
                anom.loc[g.index, f'{response}_{col}'] = vals
            # Leave-one-year-out predictive check on reference years only.
            loo = []
            for j in range(len(train)):
                keep = np.arange(len(train)) != j
                b = np.linalg.lstsq(xt[keep], yt[keep], rcond=None)[0]
                loo.append(xt[j]@b)
            reference_rows.append({'response': response, 'month': m, 'n_years': len(train),
                                   'rank': int(rank), 'condition_number': float(np.linalg.cond(xt)),
                                   'training_residual_sd': scale, 'loo_rmse': float(np.sqrt(np.mean((yt-np.array(loo))**2))),
                                   **dict(zip(['intercept', 'trend_per_decade', 'nino34_coefficient', 'pattern_coefficient'], beta))})
    pd.DataFrame(reference_rows).to_csv(OUT / 'wind_reference_coefficients.csv', index=False)
    anom.to_csv(OUT / 'atmosphere_anomaly_and_reference.csv', index=False)
    ordered = np.argsort(pd.DatetimeIndex(times).values)
    d = xr.Dataset({'sst_anomaly': (('time', 'sst_lon'), np.array(hov_sst)[ordered]),
                    'tau_anomaly': (('time', 'tau_lon'), np.array(hov_tau)[ordered])},
                   coords={'time': pd.DatetimeIndex(times)[ordered], 'sst_lon': slon, 'tau_lon': tlon})
    d.sst_anomaly.attrs['units'] = 'degC'
    d.tau_anomaly.attrs['units'] = 'N m-2'
    d.attrs.update(baseline='1982-2022 calendar-month mean', latitude_band='5S-5N; distinct from the 9S-9N ocean volume domain',
                   reference_excluded_years=','.join(map(str, excluded)), interpretation='SST-conditioned statistical wind expectation, not causal forcing')
    d.to_netcdf(target, engine='scipy')
    qa = {'reference_years': years, 'excluded_years': excluded, 'n_reference_years_per_month': 34,
          'bootstrap': '500 paired two-year-block resamples; intervals for expected mean only, not prediction intervals',
          'no_target_window_in_fit': not bool(set(CASE_YEARS)&set(years)),
          'tau_sign': 'ERA5 avg_iews eastward surface stress, positive eastward; native units N m-2',
          'source_sst': 'NOAA OISST local 1-degree subsets', 'source_wind': 'ERA5 avg_iews monthly means'}
    save_json(OUT / 'wind_reference_QA.json', qa)
    QA['wind_reference'] = qa


def weighted_profile(temp, lat):
    mask = (lat > -9) & (lat < 9)
    t = temp[:, :24, mask, :]
    w = np.cos(np.deg2rad(lat[mask]))[None, None, :, None]
    den = np.sum(np.isfinite(t)*w, axis=2)
    return np.divide(np.nansum(t*w, axis=2), den, out=np.full(den.shape, np.nan), where=den>0)


def ocean():
    if (OUT / 'ocean_QA.json').exists():
        QA['ocean'] = json.loads((OUT / 'ocean_QA.json').read_text())
        print('Ocean cache ready', flush=True)
        return
    pieces, profiles, interfaces, dsums, dcounts = [], [], [], {}, {}
    coords = None
    # Only section climatologies are accumulated: avoids storing full 3-D history.
    cache_clim = CACHE / 'section_climatology_1982_2022.npz'
    need_clim = not cache_clim.exists()
    for year in range(1982, 2025):
        tab = CACHE / f'volume_{year}.csv'
        pro = CACHE / f'profiles_{year}.npz'
        a = None
        if not tab.exists() or not pro.exists() or (need_clim and year <= BASE[1]):
            a = geometry.load_inputs(year)
        zdata = np.load(OLD / f'd26_{year}.npz')
        lat, lon = zdata['lat'], zdata['lon']
        z = zdata['d26'].astype('float64')
        area = geometry.R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat+.25))-np.sin(np.deg2rad(lat-.25)))[:, None]*np.ones((1, len(lon)))
        if not tab.exists():
            values = {'time': [pd.Timestamp(year, m, 15) for m in range(1, 13)]}
            for name, (lo, hi) in REGIONS.items():
                ar = area*((lat>-9)&(lat<9))[:, None]*((lon>lo)&(lon<hi))[None, :]
                values[f'{name}_wwv_m3'] = np.nansum(z*ar, axis=(1, 2))
            ar = area*((lat>-9)&(lat<9))[:, None]*((lon>120)&(lon<280))[None, :]
            values['basin_wwv_m3'] = np.nansum(z*ar, axis=(1, 2))
        for name, spec in GATES.items():
            if a is None:
                break
            g = geometry.section(a, *spec)
            if not tab.exists():
                values[f'{name}_q_sv'] = geometry.integrate_gate(g, a['depth'], a['layer_bottom'])[0]
            if need_clim and year <= BASE[1]:
                if name not in dsums:
                    dsums[name], dcounts[name] = {}, {}
                for key in ('temp', 'salt', 'flow'):
                    val = g[key]
                    if key not in dsums[name]:
                        dsums[name][key] = np.zeros_like(val, dtype='float64')
                        dcounts[name][key] = np.zeros_like(val, dtype='int16')
                    dsums[name][key] += np.nan_to_num(val, nan=0)
                    dcounts[name][key] += np.isfinite(val)
                for key in ('lat', 'lon', 'width'):
                    dsums[name][key] = g[key]
        if not tab.exists():
            pd.DataFrame(values).to_csv(tab, index=False)
        if not pro.exists():
            np.savez_compressed(pro, temp=weighted_profile(a['temp'], lat), depth=a['depth'][:24],
                                lon=lon, lat=lat, layer_bottom=a['layer_bottom'][:24])
        piece = pd.read_csv(tab, parse_dates=['time'])
        pieces.append(piece)
        p = dict(np.load(pro))
        profiles.append(p['temp'])
        interfaces.append(z)
        if coords is None:
            coords = {k: p[k] for k in ('depth', 'lon', 'lat', 'layer_bottom')}
        del a, zdata
        gc.collect()
        print('Ocean baseline and volume', year, flush=True)
    if need_clim:
        cc = {}
        for name in GATES:
            for key in ('temp', 'salt', 'flow'):
                count = dcounts[name][key]
                cc[name+'__'+key] = np.divide(dsums[name][key], count, out=np.full_like(dsums[name][key], np.nan), where=count==41)
                cc[name+'__'+key+'_count'] = count
            for key in ('lat', 'lon', 'width'):
                cc[name+'__'+key] = dsums[name][key]
        np.savez_compressed(cache_clim, **cc)
    raw = pd.concat(pieces, ignore_index=True)
    anom, trend = anomalies(raw), detrended_anomaly(raw)
    for name, frame in [('absolute', raw), ('anomalies', anom), ('trend_sensitivity', trend)]:
        frame.to_csv(OUT / f'ocean_monthly_{name}.csv', index=False)
    diff = raw.basin_wwv_m3 - raw[[r+'_wwv_m3' for r in REGIONS]].sum(axis=1)
    assert np.max(abs(diff)/raw.basin_wwv_m3) < 1e-12
    tprof = np.concatenate(profiles)
    dfield = np.concatenate(interfaces)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        tclim = np.stack([np.nanmean(tprof[:41*12][m::12], axis=0) for m in range(12)])
        dclim = np.stack([np.nanmean(dfield[:41*12][m::12], axis=0) for m in range(12)])
    idx = raw.time.dt.month.to_numpy()-1
    case = raw.time.dt.year.isin(CASE_YEARS).to_numpy()
    export = xr.Dataset({'temperature': (('time', 'depth', 'lon'), tprof[case]),
                         'temperature_anomaly': (('time', 'depth', 'lon'), (tprof-tclim[idx])[case]),
                         'temperature_climatology': (('month', 'depth', 'lon'), tclim),
                         'd26': (('time', 'lat', 'lon'), dfield[case]),
                         'd26_anomaly': (('time', 'lat', 'lon'), (dfield-dclim[idx])[case]),
                         'd26_climatology': (('month', 'lat', 'lon'), dclim)},
                        coords={'time': raw.time[case], 'month': np.arange(1, 13), 'depth': coords['depth'],
                                'lat': coords['lat'], 'lon': coords['lon']})
    for key in ('temperature', 'temperature_anomaly', 'temperature_climatology'):
        export[key].attrs.update(units='degC', latitude_average='9S-9N cosine-weighted on available wet cells')
    for key in ('d26', 'd26_anomaly', 'd26_climatology'):
        export[key].attrs['units'] = 'm'
    export.attrs.update(baseline='1982-2022 monthly climatology, no filtering', source='SODA3.15.2 official annual subsets',
                        vertical_plot_warning='Temperature profile display depth does not define the WWV26 lower boundary',
                        domain='WWV26: 9S-9N, 120E-80W. Internal boundaries 180 and 140W.')
    export.to_netcdf(OUT / 'ocean_case_fields.nc', engine='scipy')
    rows = []
    cc = dict(np.load(cache_clim))
    coverage_min = {}
    for year in CASE_YEARS:
        a = geometry.load_inputs(year)
        for name, spec in GATES.items():
            g = geometry.section(a, *spec)
            b = {key: cc[name+'__'+key] for key in ('temp', 'salt', 'flow', 'lat', 'lon', 'width')}
            _, _, _, w, _ = geometry.integrate_gate(g, a['depth'], a['layer_bottom'])
            _, _, _, wc, _ = geometry.integrate_gate(b, a['depth'], a['layer_bottom'])
            t1 = b['flow']*(g['temp']-b['temp'])
            t2 = (g['flow']-b['flow'])*b['temp']
            valid = np.isfinite(t1) & np.isfinite(t2)
            for geom, weight in [('instantaneous', w), ('climatological', wc)]:
                area = np.sum(weight, axis=(1, 2))
                used = np.sum(np.where(valid, weight, 0), axis=(1, 2))
                cov = np.divide(used, area, out=np.full(12, np.nan), where=area>0)
                vals = [np.sum(np.where(valid, t, 0)*weight, axis=(1, 2))*geometry.RHO*geometry.CP/1e15 for t in (t1, t2)]
                for m in range(12):
                    rows.append({'time': pd.Timestamp(year, m+1, 15), 'gate': name, 'geometry': geom,
                                 'mean_flow_temperature_anomaly_pw': vals[0][m], 'anomalous_flow_mean_temperature_pw': vals[1][m],
                                 'area_coverage': cov[m], 'active_area_m2': area[m]})
                if geom == 'instantaneous':
                    coverage_min[name] = min(coverage_min.get(name, 1), float(np.nanmin(cov))) if np.any(np.isfinite(cov)) else None
        del a
        gc.collect()
        print('Two-term transports', year, flush=True)
    pd.DataFrame(rows).to_csv(OUT / 'two_term_heat_transport.csv', index=False)
    qa = {'three_region_sum_max_relative_error': float(np.max(abs(diff)/raw.basin_wwv_m3)),
          'shared_internal_gates': 'one calculation used with opposite signs by adjacent regions',
          'case_months': int(case.sum()), 'baseline_years': list(BASE), 'section_minimum_coverage': coverage_min,
          'd26_source': 'audited full-density-surface cached fields, not old regional volume tables',
          'heat_reference_temperature_C': 0., 'heat_terms_complete_anomaly': False}
    save_json(OUT / 'ocean_QA.json', qa)
    QA['ocean'] = qa


def reference_sensitivity():
    f = pd.read_csv(OUT / 'atmosphere_anomaly_and_reference.csv')
    rows = []
    for label, end, trend, pattern in [('full_with_trend',2024,True,True), ('full_no_trend',2024,False,True),
                                      ('early_with_trend',2013,True,True), ('amplitude_only',2024,True,False)]:
        for m, g in f.groupby('month'):
            use = (g.year<=end)&~g.year.isin(EXCLUDE_REFERENCE)
            columns = [np.ones(len(g))]
            if trend: columns.append((g.year.to_numpy()-2003)/10)
            columns.append(g.nino34.to_numpy())
            if pattern: columns.append(g.pattern.to_numpy())
            x, y = np.column_stack(columns), g.tau.to_numpy()
            beta = np.linalg.lstsq(x[use], y[use], rcond=None)[0]
            scale = np.sqrt(np.sum((y[use]-x[use]@beta)**2)/(use.sum()-x.shape[1]))
            for i, (_, r) in enumerate(g.iterrows()):
                if int(r.year) in CASE_YEARS:
                    rows.append({'reference':label,'year':int(r.year),'month':int(m),'time':r.time,
                                 'tau':r.tau,'expected':float(x[i]@beta),'residual_z':float((y[i]-x[i]@beta)/scale)})
    result = pd.DataFrame(rows)
    result.to_csv(OUT / 'wind_reference_sensitivity_monthly.csv', index=False)
    result = result.loc[result.year.isin(EVENTS)].copy()
    result['quarter'] = (result.month-1)//3+1
    result = result.groupby(['reference','year','quarter'])[['tau','expected','residual_z']].mean().reset_index().rename(columns={'year':'event'})
    result.to_csv(OUT / 'wind_reference_sensitivity_quarterly.csv', index=False)


def summarise():
    reference_sensitivity()
    atm = pd.read_csv(OUT / 'atmosphere_anomaly_and_reference.csv', parse_dates=['time'])
    volume_rows, january_rows, phase_rows, cooccurrence_rows = [], [], [], []
    for method in ('anomalies', 'trend_sensitivity'):
        ocean = pd.read_csv(OUT / f'ocean_monthly_{method}.csv', parse_dates=['time'])
        for e in EVENTS:
            event = ocean.loc[ocean.time.dt.year.between(e-1, e)].copy()
            jan = event.loc[event.time.eq(pd.Timestamp(e, 1, 15))].iloc[0]
            january_rows.append({'event': e, 'baseline_method': method, **{r+'_wwv_1e14m3': jan[r+'_wwv_m3']/1e14 for r in ['basin', *REGIONS]}})
            for region in REGIONS:
                gw, ge = EDGES[region]
                for window, lo, hi in [('preconditioning', f'{e-1}-01-15', f'{e}-01-15'),
                                       ('development', f'{e}-01-15', f'{e}-12-15'),
                                       ('full_window', f'{e-1}-01-15', f'{e}-12-15')]:
                    s = event.loc[event.time.between(lo, hi)].copy()
                    sec = (s.time-s.time.iloc[0]).dt.total_seconds().to_numpy()
                    zonal = (s[gw+'_q_sv']-s[ge+'_q_sv']).to_numpy()
                    meridional = (s[region+'_south_q_sv']-s[region+'_north_q_sv']).to_numpy()
                    zi = cumulative_trapezoid(zonal, sec, initial=0)/1e8
                    mi = cumulative_trapezoid(meridional, sec, initial=0)/1e8
                    storage = (s[region+'_wwv_m3']-s[region+'_wwv_m3'].iloc[0]).to_numpy()/1e14
                    residual = storage-zi-mi
                    for i, t in enumerate(s.time):
                        volume_rows.append({'event': e, 'region': region, 'baseline_method': method, 'window': window,
                                            'time': t, 'storage_change': storage[i], 'zonal_input': zi[i], 'meridional_input': mi[i],
                                            'unresolved': residual[i]})
            a = atm.loc[atm.year.eq(e)]
            if method == 'anomalies':
                for name, lo, hi in [('JFM', 1, 3), ('AMJ', 4, 6), ('JAS', 7, 9), ('OND', 10, 12)]:
                    s = a.loc[a.month.between(lo, hi)]
                    phase_rows.append({'event': e, 'phase': name, **{k: s[k].mean() for k in ['nino34', 'pattern', 'tau', 'tau_expected', 'tau_residual', 'tau_residual_z', 'tau_9deg_residual_z']}})
                # Descriptive co-occurrence only; not an objective closed-loop onset.
                for threshold in (.3, .5, .8):
                    flag = (a.nino34.to_numpy()>threshold)&(a.tau.to_numpy()>0)
                    lengths, start = [], None
                    for i, active in enumerate(np.r_[flag, False]):
                        if active and start is None:
                            start = i
                        if not active and start is not None:
                            lengths.append((start+1, i, i-start)); start = None
                    cooccurrence_rows.append({'event': e, 'sst_threshold_C': threshold, 'positive_tau_threshold_Nm2': 0,
                                              'months_joint_positive': int(flag.sum()), 'longest_run_months': max([x[2] for x in lengths], default=0),
                                              'runs_start_end_length': json.dumps(lengths), 'interpretation': 'descriptive co-occurrence; not causal coupling onset'})
    budget = pd.DataFrame(volume_rows)
    budget.to_csv(OUT / 'cumulative_volume_budget.csv', index=False)
    ends = budget.sort_values('time').groupby(['event','region','baseline_method','window'], as_index=False).tail(1)
    ends.to_csv(OUT / 'budget_window_summary.csv', index=False)
    pd.DataFrame(january_rows).to_csv(OUT / 'january_ocean_initial_states.csv', index=False)
    pd.DataFrame(phase_rows).to_csv(OUT / 'development_quarterly_airsea_summary.csv', index=False)
    pd.DataFrame(cooccurrence_rows).to_csv(OUT / 'descriptive_sst_wind_cooccurrence.csv', index=False)
    # A profile-mean temperature diagnostic, deliberately not another heat-content definition.
    thermal_rows = []
    with xr.open_dataset(OUT / 'ocean_case_fields.nc', engine='scipy') as ds:
        bottom = np.array(json.loads((geometry.RAW/'metadata_2024.json').read_text())['coords']['sw_ocean'])[:24]
        top = np.r_[0., bottom[:-1]]
        for r, (west, east) in REGIONS.items():
            f = ds.temperature_anomaly.sel(lon=slice(west,east)).mean('lon', skipna=True).values
            for lo, hi in [(0.,50.),(50.,150.),(150.,300.)]:
                w = np.maximum(0., np.minimum(bottom,hi)-np.maximum(top,lo))
                den = np.sum(np.isfinite(f)*w[None,:], axis=1)
                mean = np.divide(np.nansum(f*w[None,:],axis=1),den,out=np.full(len(f),np.nan),where=den>0)
                for t,val in zip(pd.to_datetime(ds.time.values),mean):
                    thermal_rows.append({'time':t,'region':r,'layer_top_m':lo,'layer_bottom_m':hi,'profile_mean_temperature_anomaly_C':val})
    thermal = pd.DataFrame(thermal_rows)
    thermal.to_csv(OUT/'thermal_structure_monthly.csv',index=False)
    thermal.loc[thermal.time.dt.year.isin(EVENTS)&thermal.time.dt.month.eq(1)].to_csv(OUT/'january_thermal_structure.csv',index=False)
    partition_rows = []
    with xr.open_dataset(OUT/'ocean_case_fields.nc',engine='scipy') as ds:
        lat,lon = ds.lat.values,ds.lon.values
        area = geometry.R**2*np.deg2rad(.5)*(np.sin(np.deg2rad(lat+.25))-np.sin(np.deg2rad(lat-.25)))[:,None]*np.ones((1,len(lon)))
        for e in EVENTS:
            z = ds.d26_anomaly.sel(time=f'{e}-01-15').values
            for label,lo,hi in [('far_west',120,140),('west_pacific',140,180),('central',180,220),('east',220,280)]:
                for band,s,n in [('all9',-9,9),('equatorial5',-5,5),('south',-9,-5),('north',5,9)]:
                    mask = ((lat>s)&(lat<n))[:,None]*((lon>lo)&(lon<hi))[None,:]
                    partition_rows.append({'event':e,'segment':label,'latitude_band':band,'wwv_anomaly_1e14m3':float(np.nansum(z*area*mask)/1e14)})
    pd.DataFrame(partition_rows).to_csv(OUT/'january_spatial_partition_diagnostic.csv',index=False)
    error = abs(budget.storage_change-budget.zonal_input-budget.meridional_input-budget.unresolved).max()
    assert error < 1e-10
    QA['budget_accounting_error_1e14m3'] = float(error)
    QA['scope'] = 'Results 1-3; no new dynamical model simulations, no multi-event generalisation'
    QA['model_next_step'] = 'Use diagnostics to choose a minimal ocean state; 3x3 SST/ocean initialisation with common parameters, checking physical consistency'
    save_json(OUT / 'numerical_QA.json', QA)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    p = argparse.ArgumentParser()
    p.add_argument('--part', choices=['all', 'atmosphere', 'ocean', 'summary'], default='all')
    arg = p.parse_args()
    if arg.part in ('all', 'atmosphere'):
        atmosphere()
    if arg.part in ('all', 'ocean'):
        ocean()
    if arg.part in ('all', 'summary'):
        for name, key in [('wind_reference_QA.json', 'wind_reference'), ('ocean_QA.json', 'ocean')]:
            if (OUT/name).exists(): QA[key] = json.loads((OUT/name).read_text())
        summarise()
    print('Completed', arg.part, OUT, flush=True)


if __name__ == '__main__':
    main()
